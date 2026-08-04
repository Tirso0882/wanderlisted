#!/usr/bin/env python3
"""Validate Wanderlisted's AI-native documentation contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from ._common import ROOT, load_yaml, parse_frontmatter, resolve_declared_path
    from .build_indexes import render_index
    from .context_bundle import build_bundle
except ImportError:  # Direct script execution.
    from _common import ROOT, load_yaml, parse_frontmatter, resolve_declared_path
    from build_indexes import render_index
    from context_bundle import build_bundle

STATUS_VALUES = {"draft", "active", "deprecated", "superseded", "archived"}
AUTHORITY_VALUES = {"normative", "descriptive", "generated"}
PRIORITY_VALUES = {"Critical", "Recommended", "Optional"}
REQUIRED_METADATA = {
    "id",
    "doc_type",
    "status",
    "authority",
    "owners",
    "applies_to",
    "load_when",
    "source_paths",
}
RULE_PATTERN = re.compile(r"^##\s+(BR-[A-Z]+-\d{3})\b", re.MULTILINE)
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
EXPECTED_SCOPED_AGENTS = {
    "src/agent/AGENTS.md",
    "src/readiness/AGENTS.md",
    "src/budget/AGENTS.md",
    "src/itinerary/AGENTS.md",
    "src/tools/AGENTS.md",
    "frontend/AGENTS.md",
    "tests/AGENTS.md",
    "edd/AGENTS.md",
    "infra/AGENTS.md",
}
EXPECTED_SKILLS = {
    "agent-evaluation",
    "handbook-rendering",
    "hotelbeds-integration",
    "langgraph-stage4",
    "responses-api-reasoning",
}


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _validate_metadata(
    relative: str,
    metadata: dict[str, Any],
    schema_properties: set[str],
    doc_types: set[str],
    errors: list[str],
) -> None:
    missing = REQUIRED_METADATA - metadata.keys()
    if missing:
        errors.append(f"{relative}: missing metadata {sorted(missing)}")
        return
    unknown = metadata.keys() - schema_properties
    if unknown:
        errors.append(f"{relative}: unknown metadata {sorted(unknown)}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(metadata["id"])):
        errors.append(f"{relative}: invalid document id {metadata['id']!r}")
    if metadata["doc_type"] not in doc_types:
        errors.append(f"{relative}: invalid doc_type {metadata['doc_type']!r}")
    if metadata["status"] not in STATUS_VALUES:
        errors.append(f"{relative}: invalid status {metadata['status']!r}")
    if metadata["authority"] not in AUTHORITY_VALUES:
        errors.append(f"{relative}: invalid authority {metadata['authority']!r}")
    for field in ("owners", "applies_to", "load_when", "source_paths"):
        if not isinstance(metadata[field], list):
            errors.append(f"{relative}: {field} must be a list")
    if isinstance(metadata.get("owners"), list) and not metadata["owners"]:
        errors.append(f"{relative}: owners must not be empty")


def _validate_links(root: Path, paths: set[Path], errors: list[str]) -> None:
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        historical_superseded_adr = path.parent == root / "docs/adr" and bool(
            re.search(r"\*\*Status:\*\*\s*Superseded", text, re.IGNORECASE)
        )
        for match in LINK_PATTERN.finditer(text):
            raw = match.group(1).strip()
            target = raw.split(maxsplit=1)[0].strip("<>")
            if (
                not target
                or target.startswith(("#", "http://", "https://", "mailto:"))
                or "<" in target
                or ">" in target
            ):
                continue
            target_path = target.split("#", maxsplit=1)[0]
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    f"{_relative(root, path)}: link escapes repository: {target}"
                )
                continue
            if not resolved.exists():
                # Superseded immutable ADRs may retain links to code removed by
                # the decision that replaced them. Their ADR targets are
                # validated separately by the lifecycle check below.
                if historical_superseded_adr:
                    continue
                errors.append(f"{_relative(root, path)}: broken link {target}")


def _validate_agent_map(
    root: Path, agent_map: dict[str, Any], errors: list[str]
) -> set[Path]:
    canonical: set[Path] = set()
    documents = agent_map.get("documents", {})
    if not isinstance(documents, dict) or not documents:
        errors.append("docs/agent-map.yaml: documents must be a non-empty mapping")
        return canonical
    for relative, config in documents.items():
        path = root / relative
        canonical.add(path)
        if not path.is_file():
            errors.append(f"docs/agent-map.yaml: missing document {relative}")
            continue
        if config.get("priority") not in PRIORITY_VALUES:
            errors.append(f"docs/agent-map.yaml: invalid priority for {relative}")
        limit = config.get("byte_limit")
        if not isinstance(limit, int) or limit <= 0:
            errors.append(f"docs/agent-map.yaml: invalid byte_limit for {relative}")
        elif path.stat().st_size > limit:
            errors.append(
                f"{relative}: {path.stat().st_size} bytes exceeds declared {limit}"
            )
    route_ids: set[str] = set()
    for route in agent_map.get("routes", []):
        route_id = route.get("id")
        if not route_id or route_id in route_ids:
            errors.append(
                f"docs/agent-map.yaml: duplicate/missing route id {route_id!r}"
            )
        route_ids.add(route_id)
        if not route.get("paths") and not route.get("triggers"):
            errors.append(f"docs/agent-map.yaml: route {route_id} has no matcher")
        for priority, routed in route.get("documents", {}).items():
            if priority not in PRIORITY_VALUES:
                errors.append(
                    f"docs/agent-map.yaml: route {route_id} has invalid {priority}"
                )
            for relative in routed:
                if relative not in documents:
                    errors.append(
                        f"docs/agent-map.yaml: route {route_id} references "
                        f"unregistered {relative}"
                    )
    return canonical


def _validate_instructions_and_skills(
    root: Path, agent_map: dict[str, Any], errors: list[str]
) -> set[Path]:
    link_paths: set[Path] = set()
    budgets = agent_map["budgets"]
    root_agents = root / "AGENTS.md"
    if not root_agents.is_file():
        errors.append("AGENTS.md is missing")
        return link_paths
    link_paths.add(root_agents)
    if root_agents.stat().st_size > budgets["root_agents_max_bytes"]:
        errors.append("AGENTS.md exceeds root instruction budget")
    actual_scoped = {
        _relative(root, path)
        for path in root.rglob("AGENTS.md")
        if "node_modules" not in path.parts
        and ".venv" not in path.parts
        and path != root_agents
    }
    if actual_scoped != EXPECTED_SCOPED_AGENTS:
        errors.append(
            "scoped AGENTS.md set differs: "
            f"missing={sorted(EXPECTED_SCOPED_AGENTS - actual_scoped)}, "
            f"extra={sorted(actual_scoped - EXPECTED_SCOPED_AGENTS)}"
        )
    for relative in sorted(actual_scoped):
        path = root / relative
        link_paths.add(path)
        if path.stat().st_size > budgets["scoped_agents_max_bytes"]:
            errors.append(f"{relative}: exceeds scoped instruction budget")
        combined = path.stat().st_size + root_agents.stat().st_size
        if combined > budgets["automatic_instruction_bytes"]:
            errors.append(
                f"AGENTS.md + {relative}: {combined} exceeds automatic budget"
            )

    adapter = root / ".github/copilot-instructions.md"
    if not adapter.is_file():
        errors.append(".github/copilot-instructions.md is missing")
    else:
        link_paths.add(adapter)
        adapter_text = adapter.read_text(encoding="utf-8")
        if adapter.stat().st_size > budgets["copilot_adapter_max_bytes"]:
            errors.append("Copilot adapter exceeds byte budget")
        for marker in ("AGENTS.md", "docs/agent-map.yaml", ".agents/skills/"):
            if marker not in adapter_text:
                errors.append(f"Copilot adapter does not reference {marker}")
        if "src/" in adapter_text or "tests/" in adapter_text:
            errors.append("Copilot adapter duplicates repository policy")

    if (root / ".github/skills").exists():
        errors.append("legacy .github/skills must not exist")
    if (root / ".continue").exists():
        errors.append("unsupported .continue agent configuration must not exist")
    skill_root = root / ".agents/skills"
    actual_skills = {path.name for path in skill_root.iterdir() if path.is_dir()}
    if actual_skills != EXPECTED_SKILLS:
        errors.append(
            f"shared skill set differs: expected={sorted(EXPECTED_SKILLS)}, "
            f"actual={sorted(actual_skills)}"
        )
    for skill_name in sorted(actual_skills):
        skill = skill_root / skill_name / "SKILL.md"
        if not skill.is_file():
            errors.append(f".agents/skills/{skill_name}/SKILL.md is missing")
            continue
        link_paths.add(skill)
        metadata, body = parse_frontmatter(skill)
        if set(metadata) != {"name", "description"}:
            errors.append(
                f"{_relative(root, skill)}: frontmatter must contain name/description only"
            )
        if metadata.get("name") != skill_name:
            errors.append(f"{_relative(root, skill)}: name does not match directory")
        if not str(metadata.get("description", "")).strip():
            errors.append(f"{_relative(root, skill)}: description is empty")
        if skill.stat().st_size > budgets["skill_max_bytes"]:
            errors.append(f"{_relative(root, skill)}: exceeds skill byte budget")
        for heading in (
            "## Inputs",
            "## Workflow",
            "## Stop conditions",
            "## Output",
            "## Validation",
        ):
            if heading not in body:
                errors.append(f"{_relative(root, skill)}: missing {heading}")
        link_paths.update((skill.parent / "references").glob("*.md"))

    banned = [
        path
        for path in root.rglob("*")
        if "node_modules" not in path.parts
        and ".venv" not in path.parts
        and (
            path.name == "CLAUDE.md"
            or path.name in {".claude", ".cursor"}
            or ".claude" in path.parts
            or ".cursor" in path.parts
        )
    ]
    if banned:
        errors.append(
            f"unsupported agent artifacts exist: {[str(path) for path in banned]}"
        )
    if list((root / ".github").glob("instructions/*.instructions.md")):
        errors.append(".github/instructions adapters are not allowed")

    link_paths.update((root / ".github/agents").glob("*.md"))
    link_paths.update((root / ".github/prompts").glob("*.md"))
    return link_paths


def _validate_traceability(
    root: Path,
    canonical_metadata: dict[str, dict[str, Any]],
    rule_ids: set[str],
    errors: list[str],
) -> None:
    traceability = load_yaml(root / "docs/traceability.yaml")
    feature_ids: set[str] = set()
    traced_feature_documents: set[str] = set()
    for feature in traceability.get("features", []):
        feature_id = feature.get("id", "")
        if not re.fullmatch(r"FEAT-[A-Z]+", str(feature_id)):
            errors.append(f"traceability: invalid feature id {feature_id!r}")
        if feature_id in feature_ids:
            errors.append(f"traceability: duplicate feature id {feature_id}")
        feature_ids.add(feature_id)
        document = feature.get("document", "")
        traced_feature_documents.add(document)
        if canonical_metadata.get(document, {}).get("doc_type") != "feature":
            errors.append(f"traceability: {feature_id} has invalid feature document")
        for required in (
            "domains",
            "rules",
            "implementation",
            "tests",
            "edd",
            "runbooks",
        ):
            if not isinstance(feature.get(required), list):
                errors.append(f"traceability: {feature_id}.{required} must be a list")
        if not feature.get("implementation") or not feature.get("tests"):
            errors.append(f"traceability: {feature_id} needs implementation and tests")
        for rule_id in feature.get("rules", []):
            if rule_id not in rule_ids:
                errors.append(
                    f"traceability: {feature_id} references unknown {rule_id}"
                )
        for field in (
            "document",
            "domains",
            "implementation",
            "tests",
            "edd",
            "runbooks",
        ):
            values = [feature[field]] if field == "document" else feature.get(field, [])
            for declared in values:
                if not resolve_declared_path(root, declared):
                    errors.append(
                        f"traceability: {feature_id}.{field} missing path {declared}"
                    )

    feature_documents = {
        _relative(root, path) for path in (root / "docs/features").glob("*/FEATURE.md")
    }
    if feature_documents != traced_feature_documents:
        errors.append(
            "traceability: feature documents differ: "
            f"missing={sorted(feature_documents - traced_feature_documents)}, "
            f"extra={sorted(traced_feature_documents - feature_documents)}"
        )

    mapped_rules: set[str] = set()
    for mapping in traceability.get("rule_mappings", []):
        ids = mapping.get("ids", [])
        if not ids or not mapping.get("implementation") or not mapping.get("evidence"):
            errors.append(
                f"traceability: incomplete rule mapping {mapping.get('document')}"
            )
        for rule_id in ids:
            if rule_id in mapped_rules:
                errors.append(f"traceability: duplicate rule mapping {rule_id}")
            mapped_rules.add(rule_id)
        for field in ("document", "implementation", "evidence"):
            values = [mapping[field]] if field == "document" else mapping.get(field, [])
            for declared in values:
                if not resolve_declared_path(root, declared):
                    errors.append(
                        f"traceability: rule mapping {field} missing {declared}"
                    )
    if mapped_rules != rule_ids:
        errors.append(
            "traceability: rule coverage differs: "
            f"missing={sorted(rule_ids - mapped_rules)}, "
            f"extra={sorted(mapped_rules - rule_ids)}"
        )


def _validate_adrs(root: Path, errors: list[str]) -> None:
    adrs = sorted((root / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    numbers: dict[str, Path] = {}
    ids: set[str] = set()
    for path in adrs:
        number = path.name[:4]
        if number in numbers:
            errors.append(f"ADR duplicate number {number}")
        numbers[number] = path
        ids.add(f"adr-{number}")
        metadata, body = parse_frontmatter(path)
        text = body if metadata else path.read_text(encoding="utf-8")
        if not re.search(
            r"\*\*(?:ADR )?Status:\*\*\s*(Accepted|Superseded|Deprecated)",
            text,
            re.IGNORECASE,
        ):
            errors.append(f"{_relative(root, path)}: missing recognized ADR status")
    for path in adrs:
        metadata, _ = parse_frontmatter(path)
        for target in metadata.get("supersedes", []):
            if target not in ids:
                errors.append(f"{_relative(root, path)}: unknown supersedes {target}")
    readme = (root / "docs/adr/README.md").read_text(encoding="utf-8")
    for path in adrs:
        if path.name not in readme:
            errors.append(f"docs/adr/README.md: missing {path.name}")


def _validate_context_routes(root: Path, errors: list[str]) -> None:
    cases = {
        "src/budget/pipeline.py": "docs/features/budget/FEATURE.md",
        "frontend/src/stores/chat-store.ts": "docs/domain/delivery.md",
        "infra/main.bicep": "docs/architecture/DEPLOYMENT_VIEW.md",
        "src/readiness/pipeline.py": "docs/features/travel-readiness/FEATURE.md",
        "src/itinerary/pipeline.py": "docs/features/itinerary/FEATURE.md",
    }
    for path, expected in cases.items():
        try:
            bundle = build_bundle([path], [], root=root)
        except (KeyError, OSError, ValueError) as exc:
            errors.append(f"context route {path}: {exc}")
            continue
        selected = {item.path for item in bundle.items}
        if expected not in selected:
            errors.append(f"context route {path}: missing {expected}")
        if bundle.task_document_bytes > bundle.task_document_budget_bytes:
            errors.append(f"context route {path}: exceeds task document budget")


def collect_errors(root: Path = ROOT) -> list[str]:
    """Collect every deterministic documentation contract violation."""
    errors: list[str] = []
    schema_path = root / "docs/_schema/document.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"document schema cannot be read: {exc}"]
    schema_properties = set(schema["properties"])
    doc_types = set(schema["properties"]["doc_type"]["enum"])

    try:
        agent_map = load_yaml(root / "docs/agent-map.yaml")
    except (OSError, ValueError) as exc:
        return [f"agent map cannot be read: {exc}"]
    canonical_paths = _validate_agent_map(root, agent_map, errors)

    metadata_by_id: dict[str, str] = {}
    canonical_metadata: dict[str, dict[str, Any]] = {}
    metadata_paths = {
        path for path in (root / "docs").rglob("*.md") if "_templates" not in path.parts
    }
    link_paths: set[Path] = set(canonical_paths)
    for path in sorted(metadata_paths):
        try:
            metadata, _ = parse_frontmatter(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not metadata:
            continue
        relative = _relative(root, path)
        link_paths.add(path)
        _validate_metadata(relative, metadata, schema_properties, doc_types, errors)
        document_id = str(metadata.get("id", ""))
        if document_id in metadata_by_id:
            errors.append(
                f"duplicate document id {document_id}: "
                f"{metadata_by_id[document_id]} and {relative}"
            )
        metadata_by_id[document_id] = relative
        if path in canonical_paths:
            canonical_metadata[relative] = metadata
            for declared in metadata.get("source_paths", []):
                if not resolve_declared_path(root, declared):
                    errors.append(f"{relative}: missing source path {declared}")

    for path in canonical_paths:
        relative = _relative(root, path)
        if relative not in canonical_metadata:
            errors.append(f"{relative}: canonical document requires frontmatter")

    rules: dict[str, str] = {}
    for path in sorted((root / "docs/rules").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        found = RULE_PATTERN.findall(text)
        if not found:
            errors.append(f"{_relative(root, path)}: no business-rule IDs")
        for rule_id in found:
            if rule_id in rules:
                errors.append(
                    f"duplicate business-rule id {rule_id}: {rules[rule_id]} and "
                    f"{_relative(root, path)}"
                )
            rules[rule_id] = _relative(root, path)

    link_paths.update(_validate_instructions_and_skills(root, agent_map, errors))
    link_paths.update((root / "docs").rglob("*.md"))
    _validate_links(root, link_paths, errors)
    _validate_traceability(root, canonical_metadata, set(rules), errors)
    _validate_adrs(root, errors)
    _validate_context_routes(root, errors)

    index = root / "docs/INDEX.md"
    expected_index = render_index(root)
    current_index = index.read_text(encoding="utf-8") if index.exists() else ""
    if current_index != expected_index:
        errors.append("docs/INDEX.md is stale; run make docs-index")
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print(f"documentation contract failed with {len(errors)} error(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("documentation contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
