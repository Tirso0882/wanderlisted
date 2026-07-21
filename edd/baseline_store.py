"""Shared cache and immutable-baseline storage for component EDD runs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from edd.harness import Trajectory

BASELINE_SCHEMA_VERSION = 1
_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_BASELINE_ROOT = Path(__file__).resolve().parent / "baselines"
_BASELINE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
_SECRET_KEY_RE = re.compile(
    r"(?:api[_-]?key|access[_-]?token|token|secret|password|credential)",
    re.IGNORECASE,
)
_SECRET_QUERY_PARAM_RE = re.compile(
    r"([?&](?:key|api[_-]?key|token|access_token)=)[^&\s)\]]+",
    re.IGNORECASE,
)
_INELIGIBLE_OUTCOMES = frozenset({"blocked_external", "infra_error"})


class BaselineConflictError(RuntimeError):
    """Raised when an existing immutable baseline would be changed."""


@dataclass(frozen=True, slots=True)
class BaselineConfig:
    """Agent-specific inputs for the shared trajectory and baseline store."""

    component: str
    dataset_version: str
    source_files: tuple[Path, ...]
    cache_env_var: str
    default_cache_dir: Path
    secret_env_vars: tuple[str, ...] = ()
    display_name: str = ""

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", self.component):
            raise ValueError(f"invalid EDD component name: {self.component!r}")
        if not self.dataset_version.strip():
            raise ValueError("dataset_version must not be empty")


@dataclass(frozen=True, slots=True)
class BaselineRunRef:
    """Stable reference to one preserved component/model trajectory run."""

    component: str
    baseline_name: str
    run_id: str
    path: Path


def _json_default(value: Any) -> Any:
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    if isinstance(value, Path):
        return value.as_posix()
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_json_default,
    )


def _pretty_json(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            default=_json_default,
        )
        + "\n"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def content_sha256(value: Any) -> str:
    """Return a stable digest for JSON-like evaluation data."""
    return _sha256_text(_canonical_json(value))


def redact_text(text: str, secret_env_vars: Sequence[str] = ()) -> str:
    """Remove configured credentials and credential-like URL parameters."""
    redacted = _SECRET_QUERY_PARAM_RE.sub(r"\1<REDACTED>", text)
    for variable in secret_env_vars:
        secret = os.environ.get(variable, "")
        if secret:
            redacted = redacted.replace(secret, "<REDACTED>")
    return redacted


def redact_value(value: Any, secret_env_vars: Sequence[str] = ()) -> Any:
    """Recursively redact secrets before cache or baseline persistence."""
    if isinstance(value, str):
        return redact_text(value, secret_env_vars)
    if isinstance(value, dict):
        return {
            key: (
                "<REDACTED>"
                if _SECRET_KEY_RE.search(str(key))
                else redact_value(item, secret_env_vars)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item, secret_env_vars) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item, secret_env_vars) for item in value)
    return value


def _source_records(config: BaselineConfig) -> list[dict[str, str]]:
    return source_hashes((Path(__file__).resolve(), *config.source_files))


def source_hashes(source_files: Sequence[Path]) -> list[dict[str, str]]:
    """Return repository-relative SHA-256 records for provenance sources."""
    records = []
    seen: set[Path] = set()
    for source_file in source_files:
        resolved = source_file.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.is_file():
            raise FileNotFoundError(f"EDD baseline source does not exist: {resolved}")
        try:
            display_path = resolved.relative_to(_ROOT).as_posix()
        except ValueError:
            display_path = resolved.as_posix()
        records.append(
            {
                "path": display_path,
                "sha256": _sha256_bytes(resolved.read_bytes()),
            }
        )
    return records


def run_fingerprint(
    config: BaselineConfig,
    queries: list[str],
    model_config: Mapping[str, Any],
) -> str:
    """Identify exactly one dataset/model/behavior-source combination."""
    identity = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "component": config.component,
        "dataset_version": config.dataset_version,
        "queries": queries,
        "model_config": redact_value(dict(model_config), config.secret_env_vars),
        "sources": _source_records(config),
    }
    return _sha256_text(_canonical_json(identity))[:16]


def trajectory_cache_path(
    config: BaselineConfig,
    queries: list[str],
    model_config: Mapping[str, Any],
) -> Path:
    """Return the disposable cache path for one run fingerprint."""
    cache_dir = Path(
        os.environ.get(config.cache_env_var, str(config.default_cache_dir))
    ).expanduser()
    return (
        cache_dir
        / f"trajectories-{run_fingerprint(config, queries, model_config)}.json"
    )


def load_trajectories(path: Path, queries: list[str]) -> list[Trajectory] | None:
    """Load a complete trajectory batch, accepting the legacy cache shape."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("queries") != queries:
        return None
    trajectories = []
    for raw_item in payload.get("trajectories", []):
        item = dict(raw_item)
        item["tool_outputs"] = [tuple(output) for output in item["tool_outputs"]]
        trajectories.append(Trajectory(**item))
    return trajectories if len(trajectories) == len(queries) else None


def trajectory_payload(
    config: BaselineConfig,
    queries: list[str],
    trajectories: list[Trajectory],
) -> dict[str, Any]:
    """Build the redacted, stable payload shared by caches and baselines."""
    return redact_value(
        {
            "schema_version": BASELINE_SCHEMA_VERSION,
            "queries": queries,
            "trajectories": [asdict(trajectory) for trajectory in trajectories],
        },
        config.secret_env_vars,
    )


def save_trajectories(
    path: Path,
    config: BaselineConfig,
    queries: list[str],
    trajectories: list[Trajectory],
) -> None:
    """Persist a redacted disposable trajectory cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _pretty_json(trajectory_payload(config, queries, trajectories)),
        encoding="utf-8",
    )


def requested_baseline_name() -> str | None:
    """Return and validate the optional ``EDD_BASELINE`` run label."""
    name = os.environ.get("EDD_BASELINE", "").strip()
    if not name:
        return None
    if not _BASELINE_NAME_RE.fullmatch(name):
        raise ValueError(
            "EDD_BASELINE must be 1-80 letters, digits, dots, underscores, or hyphens"
        )
    return name


def _baseline_root() -> Path:
    return Path(
        os.environ.get("EDD_BASELINE_DIR", str(_DEFAULT_BASELINE_ROOT))
    ).expanduser()


def _git_metadata() -> dict[str, Any]:
    def run_git(*args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=_ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""

    return {
        "commit": run_git("rev-parse", "HEAD") or None,
        "branch": run_git("branch", "--show-current") or None,
        "dirty": bool(run_git("status", "--porcelain")),
    }


def _verify_existing_run(
    run_dir: Path,
    *,
    run_id: str,
    expected_trajectory_sha256: str,
) -> None:
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        trajectory_sha256 = _sha256_bytes((run_dir / "trajectories.json").read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineConflictError(
            f"baseline run is incomplete or unreadable: {run_dir}"
        ) from exc
    if (
        manifest.get("run_id") != run_id
        or manifest.get("trajectories_sha256") != expected_trajectory_sha256
        or trajectory_sha256 != expected_trajectory_sha256
    ):
        raise BaselineConflictError(
            f"immutable baseline run conflicts with current content: {run_dir}"
        )


def preserve_baseline_run(
    config: BaselineConfig,
    queries: list[str],
    model_config: Mapping[str, Any],
    trajectories: list[Trajectory],
    *,
    cache_path: Path | None = None,
) -> BaselineRunRef | None:
    """Preserve a named, content-addressed run when ``EDD_BASELINE`` is set."""
    baseline_name = requested_baseline_name()
    if baseline_name is None:
        return None

    run_id = run_fingerprint(config, queries, model_config)
    run_dir = _baseline_root() / config.component / baseline_name / "runs" / run_id
    trajectories_text = _pretty_json(trajectory_payload(config, queries, trajectories))
    trajectories_sha256 = _sha256_text(trajectories_text)
    if run_dir.exists():
        _verify_existing_run(
            run_dir,
            run_id=run_id,
            expected_trajectory_sha256=trajectories_sha256,
        )
        print(f"{config.display_name or config.component} baseline: EXISTS ({run_id})")
        return BaselineRunRef(config.component, baseline_name, run_id, run_dir)

    source_records = _source_records(config)
    prompt_record = next(
        (
            record
            for record in source_records
            if record["path"].endswith("src/agent/prompts/agent_prompt.py")
        ),
        None,
    )
    manifest = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "kind": "edd-component-run",
        "baseline_name": baseline_name,
        "component": config.component,
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_version": config.dataset_version,
        "dataset_case_count": len(queries),
        "model_config": redact_value(dict(model_config), config.secret_env_vars),
        "provider": os.environ.get("LLM_PROVIDER", "azure_openai"),
        "git": _git_metadata(),
        "sources": source_records,
        "prompt_sha256": prompt_record["sha256"] if prompt_record else None,
        "cache_file": cache_path.name if cache_path else None,
        "cache_sha256": (
            _sha256_bytes(cache_path.read_bytes())
            if cache_path is not None and cache_path.is_file()
            else None
        ),
        "trajectories_sha256": trajectories_sha256,
    }

    runs_root = run_dir.parent
    runs_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=runs_root))
    try:
        trajectories_file = temporary / "trajectories.json"
        manifest_file = temporary / "manifest.json"
        trajectories_file.write_text(trajectories_text, encoding="utf-8")
        manifest_file.write_text(_pretty_json(manifest), encoding="utf-8")
        trajectories_file.chmod(0o444)
        manifest_file.chmod(0o444)
        try:
            temporary.rename(run_dir)
        except FileExistsError:
            _verify_existing_run(
                run_dir,
                run_id=run_id,
                expected_trajectory_sha256=trajectories_sha256,
            )
        else:
            run_dir.chmod(0o555)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)

    print(
        f"{config.display_name or config.component} baseline: SAVED "
        f"({baseline_name}/{run_id})"
    )
    return BaselineRunRef(config.component, baseline_name, run_id, run_dir)


def record_baseline_report(
    *,
    component: str,
    layer: str,
    metrics: Mapping[str, Any],
    run_refs: Mapping[str, str] | None = None,
    context: Mapping[str, Any] | None = None,
) -> Path | None:
    """Write one immutable metrics report for a named baseline identity."""
    baseline_name = requested_baseline_name()
    if baseline_name is None:
        return None
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", component):
        raise ValueError(f"invalid EDD component name: {component!r}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", layer):
        raise ValueError(f"invalid EDD layer name: {layer!r}")

    identity = redact_value(
        {
            "schema_version": BASELINE_SCHEMA_VERSION,
            "component": component,
            "layer": layer,
            "run_refs": dict(run_refs or {}),
            "context": dict(context or {}),
        }
    )
    report_id = _sha256_text(_canonical_json(identity))[:16]
    payload = {
        **identity,
        "kind": "edd-metrics-report",
        "baseline_name": baseline_name,
        "report_id": report_id,
        "created_at": datetime.now(UTC).isoformat(),
        "git": _git_metadata(),
        "metrics": redact_value(dict(metrics)),
    }
    payload["metrics_sha256"] = content_sha256(payload["metrics"])
    reports_dir = _baseline_root() / component / baseline_name / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{layer}-{report_id}.json"

    if report_path.exists():
        try:
            existing = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BaselineConflictError(
                f"baseline report is unreadable: {report_path}"
            ) from exc
        if existing.get("metrics") != payload["metrics"]:
            raise BaselineConflictError(
                "immutable baseline report already exists with different metrics: "
                f"{report_path}"
            )
        print(f"{component} {layer} baseline report: EXISTS ({report_path.name})")
        return report_path

    try:
        with report_path.open("x", encoding="utf-8") as report_file:
            report_file.write(_pretty_json(payload))
    except FileExistsError:
        return record_baseline_report(
            component=component,
            layer=layer,
            metrics=metrics,
            run_refs=run_refs,
            context=context,
        )
    report_path.chmod(0o444)
    print(f"{component} {layer} baseline report: SAVED ({report_path.name})")
    return report_path


def record_component_report(
    config: BaselineConfig,
    *,
    layer: str,
    metrics: Mapping[str, Any],
    queries: list[str],
    model_configs: Mapping[str, Mapping[str, Any]],
    context: Mapping[str, Any] | None = None,
    report_source_files: Sequence[Path] = (),
) -> Path | None:
    """Record metrics linked to the exact component run for every model arm."""
    baseline_name = requested_baseline_name()
    if baseline_name is None:
        return None
    run_refs = {
        name: run_fingerprint(config, queries, model_config)
        for name, model_config in model_configs.items()
    }
    missing_runs = [
        run_id
        for run_id in run_refs.values()
        if not (
            _baseline_root() / config.component / baseline_name / "runs" / run_id
        ).is_dir()
    ]
    if missing_runs:
        print(
            f"{config.component} {layer} baseline report: NOT SAVED "
            f"(missing preserved run(s): {', '.join(missing_runs)})"
        )
        return None
    report_context = {
        "dataset_version": config.dataset_version,
        "dataset_case_count": len(queries),
        "model_configs": redact_value(
            {name: dict(value) for name, value in model_configs.items()},
            config.secret_env_vars,
        ),
        "report_sources": source_hashes(report_source_files),
        **dict(context or {}),
    }
    return record_baseline_report(
        component=config.component,
        layer=layer,
        metrics=metrics,
        run_refs=run_refs,
        context=report_context,
    )


async def run_cached_dataset(
    *,
    config: BaselineConfig,
    queries: list[str],
    model_config: Mapping[str, Any],
    agent_cls,
    classify_outcome: Callable[[Trajectory], str],
    run_agent_fn: Callable[..., Awaitable[Trajectory]],
    max_concurrency: int,
    timeout: float,
) -> list[Trajectory]:
    """Run, cache, and optionally preserve one component dataset snapshot."""
    cache_path = trajectory_cache_path(config, queries, model_config)
    if os.environ.get("EDD_REFRESH") != "1":
        cached = load_trajectories(cache_path, queries)
        if cached is not None:
            print(
                f"{config.display_name or config.component} trajectory cache: "
                f"HIT ({cache_path.name})"
            )
            preserve_baseline_run(
                config,
                queries,
                model_config,
                cached,
                cache_path=cache_path,
            )
            return cached

    print(
        f"{config.display_name or config.component} trajectory cache: "
        f"MISS ({cache_path.name}); capturing live"
    )
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run_one(query: str) -> Trajectory:
        async with semaphore:
            return await run_agent_fn(
                agent_cls,
                query,
                timeout=timeout,
                **dict(model_config),
            )

    trajectories = await asyncio.gather(*(run_one(query) for query in queries))
    outcomes = {classify_outcome(trajectory) for trajectory in trajectories}
    if outcomes.isdisjoint(_INELIGIBLE_OUTCOMES):
        save_trajectories(cache_path, config, queries, trajectories)
        print(
            f"{config.display_name or config.component} trajectory cache: "
            f"SAVED ({cache_path.name})"
        )
        preserve_baseline_run(
            config,
            queries,
            model_config,
            trajectories,
            cache_path=cache_path,
        )
    else:
        print(
            f"{config.display_name or config.component} trajectory cache: "
            f"NOT SAVED (outcomes={sorted(outcomes)})"
        )
        if requested_baseline_name() is not None:
            print(
                f"{config.display_name or config.component} baseline: NOT SAVED "
                "(external/infrastructure failure)"
            )
    return trajectories
