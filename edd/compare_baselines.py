"""Compare Layer 1 and Layer 2 reports across named EDD baselines.

Examples:
    .venv/bin/python -m edd.compare_baselines transportation
    .venv/bin/python -m edd.compare_baselines transportation \
      --baseline transportation-before --baseline transportation-after
    .venv/bin/python -m edd.compare_baselines --all
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BASELINE_ROOT = Path(__file__).resolve().parent / "baselines"


class BaselineComparisonError(ValueError):
    """Raised when baseline reports cannot be compared."""


@dataclass(frozen=True, slots=True)
class Report:
    """One validated immutable report artifact."""

    path: Path
    payload: Mapping[str, Any]

    @property
    def created_at(self) -> str:
        return str(self.payload.get("created_at", ""))

    @property
    def report_id(self) -> str:
        return str(self.payload.get("report_id", self.path.stem))


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    """The selected L1 and L2 artifacts for one baseline/model run."""

    baseline_name: str
    model_arm: str
    run_id: str | None
    l1: Report | None
    l2: Report | None


def default_baseline_root() -> Path:
    """Return the configured durable-baseline directory."""
    return Path(
        os.environ.get("EDD_BASELINE_DIR", str(DEFAULT_BASELINE_ROOT))
    ).expanduser()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _load_reports(reports_dir: Path, layer: str, warnings: list[str]) -> list[Report]:
    reports = []
    for path in sorted(reports_dir.glob(f"{layer}-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"Ignored unreadable report {path}: {exc}")
            continue
        if not isinstance(payload, dict) or payload.get("layer") != layer:
            warnings.append(f"Ignored invalid {layer.upper()} report {path}")
            continue
        reports.append(Report(path=path, payload=payload))
    return reports


def _report_arms(report: Report) -> list[tuple[str, str | None]]:
    run_refs = _mapping(report.payload.get("run_refs"))
    if not run_refs:
        return [("all", None)]
    return [(str(name), str(run_id)) for name, run_id in sorted(run_refs.items())]


def _select_report(
    reports: Iterable[Report],
    model_arm: str,
    run_id: str | None,
    *,
    baseline_name: str,
    layer: str,
    warnings: list[str],
) -> Report | None:
    candidates = []
    for report in reports:
        run_refs = _mapping(report.payload.get("run_refs"))
        if not run_refs and model_arm == "all":
            candidates.append(report)
        elif run_refs.get(model_arm) == run_id:
            candidates.append(report)
    if not candidates:
        return None
    selected = max(candidates, key=lambda report: (report.created_at, report.path.name))
    if len(candidates) > 1:
        warnings.append(
            f"{baseline_name}/{model_arm}: found {len(candidates)} {layer.upper()} "
            f"reports; using latest {selected.path.name}"
        )
    return selected


def collect_component_rows(
    baseline_root: Path,
    component: str,
    baseline_names: list[str] | None = None,
) -> tuple[list[ComparisonRow], list[str]]:
    """Load comparable L1/L2 rows for one component's named baselines."""
    component_dir = baseline_root / component
    if not component_dir.is_dir():
        raise BaselineComparisonError(
            f"No baseline directory for component {component!r}: {component_dir}"
        )

    available = {
        directory.name: directory
        for directory in component_dir.iterdir()
        if directory.is_dir()
    }
    if baseline_names:
        selected_names = baseline_names
        missing = [name for name in selected_names if name not in available]
        if missing:
            raise BaselineComparisonError(
                f"Unknown {component} baseline(s): {', '.join(missing)}"
            )
    else:
        selected_names = sorted(available)

    rows = []
    warnings = []
    for baseline_name in selected_names:
        reports_dir = available[baseline_name] / "reports"
        if not reports_dir.is_dir():
            warnings.append(f"{component}/{baseline_name}: no reports directory")
            continue
        l1_reports = _load_reports(reports_dir, "l1", warnings)
        l2_reports = _load_reports(reports_dir, "l2", warnings)
        arms = {
            arm for report in (*l1_reports, *l2_reports) for arm in _report_arms(report)
        }
        if not arms:
            warnings.append(f"{component}/{baseline_name}: no L1 or L2 reports")
            continue
        for model_arm, run_id in sorted(arms, key=lambda arm: (arm[0], arm[1] or "")):
            rows.append(
                ComparisonRow(
                    baseline_name=baseline_name,
                    model_arm=model_arm,
                    run_id=run_id,
                    l1=_select_report(
                        l1_reports,
                        model_arm,
                        run_id,
                        baseline_name=baseline_name,
                        layer="l1",
                        warnings=warnings,
                    ),
                    l2=_select_report(
                        l2_reports,
                        model_arm,
                        run_id,
                        baseline_name=baseline_name,
                        layer="l2",
                        warnings=warnings,
                    ),
                )
            )
    if not rows:
        raise BaselineComparisonError(
            f"No L1 or L2 reports found for component {component!r}"
        )
    return rows, warnings


def _metrics(report: Report | None) -> Mapping[str, Any]:
    return _mapping(report.payload.get("metrics")) if report else {}


def _context(report: Report | None) -> Mapping[str, Any]:
    return _mapping(report.payload.get("context")) if report else {}


def _rate_value(value: Any) -> float | None:
    metric = _mapping(value)
    rate = _number(metric.get("rate"))
    if rate is not None:
        return rate
    passed = _number(metric.get("passed"))
    scored = _number(metric.get("scored"))
    return passed / scored if passed is not None and scored else None


def _format_rate(value: Any) -> str:
    metric = _mapping(value)
    rate = _rate_value(metric)
    if rate is None:
        return "n/a"
    passed = _number(metric.get("passed"))
    scored = _number(metric.get("scored"))
    counts = (
        f" ({int(passed)}/{int(scored)})"
        if passed is not None and scored is not None
        else ""
    )
    return f"{rate * 100:.1f}%{counts}"


def _mean_value(value: Any) -> float | None:
    return _number(_mapping(value).get("mean"))


def _format_rubric(value: Any) -> str:
    metric = _mapping(value)
    mean = _mean_value(metric)
    if mean is None:
        return "n/a"
    scored = _number(metric.get("scored"))
    suffix = f" (n={int(scored)})" if scored is not None else ""
    return f"{mean:.2f}{suffix}"


def _outcomes(row: ComparisonRow) -> Mapping[str, Any]:
    return _mapping(
        _metrics(row.l1).get("task_outcomes") or _metrics(row.l2).get("task_outcomes")
    )


def _outcome_total(row: ComparisonRow) -> int | None:
    for report in (row.l1, row.l2):
        total = _number(_context(report).get("dataset_case_count"))
        if total is not None:
            return int(total)
    total = sum(
        int(count) for count in _outcomes(row).values() if _number(count) is not None
    )
    return total or None


def _format_outcome(row: ComparisonRow, outcome: str) -> str:
    count = _number(_outcomes(row).get(outcome))
    if count is None:
        return "-"
    total = _outcome_total(row)
    return f"{int(count)}/{total}" if total is not None else str(int(count))


def _delta(
    current: float | None,
    reference: float | None,
    suffix: str,
    *,
    scale: float = 1.0,
) -> str:
    if current is None or reference is None:
        return "n/a"
    change = (current - reference) * scale
    return f"{change:+.2f}{suffix}"


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def format_row(values: list[str]) -> str:
        return " | ".join(
            value.ljust(widths[index]) for index, value in enumerate(values)
        )

    separator = "-+-".join("-" * width for width in widths)
    return "\n".join(
        [format_row(headers), separator, *(format_row(row) for row in rows)]
    )


def _baseline_labels(rows: list[ComparisonRow]) -> list[str]:
    return [row.baseline_name for row in rows]


def _group_rows_by_arm(rows: list[ComparisonRow]) -> dict[str, list[ComparisonRow]]:
    grouped: dict[str, list[ComparisonRow]] = defaultdict(list)
    for row in rows:
        grouped[row.model_arm].append(row)
    return dict(grouped)


def _summary_table(rows: list[ComparisonRow]) -> str:
    values = []
    for row in rows:
        l1 = _metrics(row.l1)
        rubric_scores = _mapping(_metrics(row.l2).get("rubric_scores"))
        values.append(
            [
                row.baseline_name,
                row.run_id[:8] if row.run_id else "-",
                _format_rate(l1.get("decision_accuracy")),
                _format_rubric(rubric_scores.get("faithfulness")),
                _format_rubric(rubric_scores.get("helpfulness")),
                _format_outcome(row, "completed"),
            ]
        )
    return _render_table(
        ["Baseline", "Run", "L1 exact", "Faithfulness", "Helpfulness", "Completed"],
        values,
    )


def _l1_table(rows: list[ComparisonRow]) -> str | None:
    checks = {
        str(name)
        for row in rows
        for name in _mapping(_metrics(row.l1).get("per_check"))
    }
    if not checks:
        return None
    first, last = rows[0], rows[-1]

    def sort_key(name: str) -> tuple[bool, float, str]:
        rate = _rate_value(_mapping(_metrics(last.l1).get("per_check")).get(name))
        return rate is None, rate if rate is not None else float("inf"), name

    headers = ["L1 check", *_baseline_labels(rows)]
    if len(rows) > 1:
        headers.append(f"Delta vs {first.baseline_name}")
    values = []
    for check in sorted(checks, key=sort_key):
        current = _mapping(_metrics(last.l1).get("per_check")).get(check)
        reference = _mapping(_metrics(first.l1).get("per_check")).get(check)
        line = [
            check,
            *[
                _format_rate(_mapping(_metrics(row.l1).get("per_check")).get(check))
                for row in rows
            ],
        ]
        if len(rows) > 1:
            line.append(
                _delta(
                    _rate_value(current),
                    _rate_value(reference),
                    " pp",
                    scale=100,
                )
            )
        values.append(line)
    return _render_table(headers, values)


def _l2_table(rows: list[ComparisonRow]) -> str | None:
    rubric_names = {
        str(name)
        for row in rows
        for name in _mapping(_metrics(row.l2).get("rubric_scores"))
    }
    if not rubric_names:
        return None
    first, last = rows[0], rows[-1]

    def sort_key(name: str) -> tuple[bool, float, str]:
        mean = _mean_value(_mapping(_metrics(last.l2).get("rubric_scores")).get(name))
        return mean is None, mean if mean is not None else float("inf"), name

    headers = ["L2 rubric", *_baseline_labels(rows)]
    if len(rows) > 1:
        headers.append(f"Delta vs {first.baseline_name}")
    values = []
    for rubric in sorted(rubric_names, key=sort_key):
        current = _mapping(_metrics(last.l2).get("rubric_scores")).get(rubric)
        reference = _mapping(_metrics(first.l2).get("rubric_scores")).get(rubric)
        line = [
            rubric,
            *[
                _format_rubric(
                    _mapping(_metrics(row.l2).get("rubric_scores")).get(rubric)
                )
                for row in rows
            ],
        ]
        if len(rows) > 1:
            line.append(_delta(_mean_value(current), _mean_value(reference), " pts"))
        values.append(line)
    return _render_table(headers, values)


def _outcomes_table(rows: list[ComparisonRow]) -> str | None:
    outcome_names = {str(name) for row in rows for name in _outcomes(row)}
    if not outcome_names:
        return None
    values = [
        [outcome, *[_format_outcome(row, outcome) for row in rows]]
        for outcome in sorted(outcome_names)
    ]
    return _render_table(["Task outcome", *_baseline_labels(rows)], values)


def _focus_items(rows: list[ComparisonRow]) -> list[str]:
    latest = rows[-1]
    per_check = _mapping(_metrics(latest.l1).get("per_check"))
    rates = [
        (name, _rate_value(value), _mapping(value))
        for name, value in per_check.items()
        if _rate_value(value) is not None
    ]
    items = []
    if rates:
        name, rate, metric = min(rates, key=lambda item: (item[1], item[0]))
        items.append(f"L1 lowest check: {name} at {_format_rate(metric)}.")
    rubrics = _mapping(_metrics(latest.l2).get("rubric_scores"))
    scores = [
        (name, _mean_value(value), _mapping(value))
        for name, value in rubrics.items()
        if _mean_value(value) is not None
    ]
    if scores:
        name, _mean, metric = min(scores, key=lambda item: (item[1], item[0]))
        items.append(f"L2 lowest rubric: {name} at {_format_rubric(metric)}.")
    if len(rows) > 1:
        first = rows[0]
        first_checks = _mapping(_metrics(first.l1).get("per_check"))
        regressions = [
            (name, _rate_value(value) - _rate_value(first_checks.get(name)))
            for name, value in per_check.items()
            if _rate_value(value) is not None
            and _rate_value(first_checks.get(name)) is not None
            and _rate_value(value) < _rate_value(first_checks.get(name))
        ]
        if regressions:
            name, change = min(regressions, key=lambda item: item[1])
            items.append(
                f"Largest L1 regression vs {first.baseline_name}: {name} "
                f"({change * 100:+.2f} pp)."
            )
    return items


def render_component_comparison(component: str, rows: list[ComparisonRow]) -> str:
    """Render a terminal-friendly comparison for one component."""
    sections = [f"{component.title()} baseline comparison"]
    for model_arm, arm_rows in _group_rows_by_arm(rows).items():
        run_hint = arm_rows[-1].run_id[:8] if arm_rows[-1].run_id else "unlinked"
        sections.append(f"\nModel arm: {model_arm} (latest run: {run_hint})")
        sections.append(_summary_table(arm_rows))
        l1 = _l1_table(arm_rows)
        if l1:
            sections.extend(["\nL1 decision checks", l1])
        l2 = _l2_table(arm_rows)
        if l2:
            sections.extend(["\nL2 quality rubrics", l2])
        outcomes = _outcomes_table(arm_rows)
        if outcomes:
            sections.extend(["\nTask outcomes", outcomes])
        focus_items = _focus_items(arm_rows)
        if focus_items:
            sections.append("\nFocus next")
            sections.extend(f"- {item}" for item in focus_items)
    return "\n".join(sections)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare immutable EDD L1/L2 reports across named baselines."
    )
    parser.add_argument(
        "component",
        nargs="?",
        help="Component directory under the baseline root, for example transportation.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Compare every component under the baseline root.",
    )
    parser.add_argument(
        "--baseline",
        action="append",
        dest="baselines",
        help="Baseline name to include; repeat to control comparison order.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Baseline root; defaults to EDD_BASELINE_DIR or edd/baselines.",
    )
    args = parser.parse_args(argv)
    if bool(args.component) == args.all:
        parser.error("provide exactly one component or --all")
    if args.all and args.baselines:
        parser.error("--baseline can only be used with one component")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    baseline_root = (args.root or default_baseline_root()).expanduser()
    if args.all:
        if not baseline_root.is_dir():
            print(f"No baseline root directory: {baseline_root}", file=sys.stderr)
            return 2
        components = sorted(
            path.name for path in baseline_root.iterdir() if path.is_dir()
        )
    else:
        components = [args.component]
    if not components:
        print(
            f"No component baseline directories under {baseline_root}", file=sys.stderr
        )
        return 2

    rendered = []
    warnings = []
    try:
        for component in components:
            rows, component_warnings = collect_component_rows(
                baseline_root, component, args.baselines
            )
            rendered.append(render_component_comparison(component, rows))
            warnings.extend(component_warnings)
    except BaselineComparisonError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print("\n\n".join(rendered))
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
