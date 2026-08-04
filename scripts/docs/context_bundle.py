#!/usr/bin/env python3
"""Resolve a bounded ordered documentation bundle for paths and task triggers."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from ._common import ROOT, load_yaml, matches_any, parse_frontmatter
except ImportError:  # Direct script execution.
    from _common import ROOT, load_yaml, matches_any, parse_frontmatter

PRIORITIES = ("Critical", "Recommended", "Optional")


@dataclass(frozen=True)
class BundleItem:
    path: str
    bytes: int
    category: str
    reason: str


@dataclass(frozen=True)
class ContextBundle:
    items: list[BundleItem]
    omitted: list[BundleItem]
    matched_routes: list[str]
    automatic_instruction_bytes: int
    routing_control_bytes: int
    task_document_bytes: int
    total_bytes: int
    task_document_budget_bytes: int


def _size(root: Path, relative: str) -> int:
    return (root / relative).stat().st_size


def _nearest_scoped_agents(root: Path, paths: list[str]) -> list[str]:
    found: list[str] = []
    for raw in paths:
        candidate = root / raw
        directory = candidate if candidate.is_dir() else candidate.parent
        try:
            directory = directory.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        current = root / directory
        while current != root:
            agent_file = current / "AGENTS.md"
            if agent_file.exists():
                relative = agent_file.relative_to(root).as_posix()
                if relative not in found:
                    found.append(relative)
                break
            current = current.parent
    return found


def _active_task_files(root: Path, paths: list[str], triggers: set[str]) -> list[str]:
    result: list[str] = []
    for task in sorted((root / "docs/tasks/active").glob("*/TASK.md")):
        metadata, _ = parse_frontmatter(task)
        if metadata.get("status") != "active":
            continue
        applies_to = metadata.get("applies_to", [])
        load_when = {str(value).lower() for value in metadata.get("load_when", [])}
        if not (
            any(matches_any(path, applies_to) for path in paths)
            or bool(triggers & load_when)
        ):
            continue
        for name in ("TASK.md", "EXECUTION.md", "HANDOFF.md"):
            packet_file = task.parent / name
            if packet_file.exists():
                result.append(packet_file.relative_to(root).as_posix())
    return result


def build_bundle(
    paths: list[str],
    triggers: list[str],
    *,
    include_optional: bool = False,
    budget_bytes: int | None = None,
    root: Path = ROOT,
) -> ContextBundle:
    """Build a context bundle without reading application source files."""
    agent_map = load_yaml(root / "docs/agent-map.yaml")
    budgets = agent_map["budgets"]
    task_budget = budget_bytes or budgets["default_task_documents_bytes"]
    normalized_paths = [path.replace("\\", "/").lstrip("./") for path in paths]
    normalized_triggers = {trigger.strip().lower() for trigger in triggers if trigger}

    items: list[BundleItem] = []
    seen: set[str] = set()

    def add(relative: str, category: str, reason: str) -> None:
        if relative in seen:
            return
        seen.add(relative)
        items.append(BundleItem(relative, _size(root, relative), category, reason))

    add("AGENTS.md", "instruction", "root instructions")
    for scoped in _nearest_scoped_agents(root, normalized_paths):
        add(scoped, "instruction", "nearest scoped instructions")
    instruction_bytes = sum(item.bytes for item in items)
    if instruction_bytes > budgets["automatic_instruction_bytes"]:
        raise ValueError(
            f"automatic instruction budget exceeded: {instruction_bytes} > "
            f"{budgets['automatic_instruction_bytes']}"
        )

    add("docs/agent-map.yaml", "routing", "routing control plane")
    routing_bytes = _size(root, "docs/agent-map.yaml")

    task_candidates = _active_task_files(root, normalized_paths, normalized_triggers)
    selected_task_items: list[BundleItem] = [
        BundleItem(path, _size(root, path), "task", "matching active task packet")
        for path in task_candidates
    ]

    matched_routes: list[str] = []
    candidates: dict[str, list[BundleItem]] = {priority: [] for priority in PRIORITIES}
    priority_rank = {priority: index for index, priority in enumerate(PRIORITIES)}
    candidate_order: list[str] = []
    candidate_by_path: dict[str, BundleItem] = {}
    for route in agent_map.get("routes", []):
        path_match = any(
            matches_any(path, route.get("paths", [])) for path in normalized_paths
        )
        route_triggers = {str(value).lower() for value in route.get("triggers", [])}
        trigger_match = bool(normalized_triggers & route_triggers)
        if not (path_match or trigger_match):
            continue
        matched_routes.append(route["id"])
        for priority in PRIORITIES:
            for document in route.get("documents", {}).get(priority, []):
                item = BundleItem(
                    document,
                    _size(root, document),
                    priority,
                    f"route {route['id']}",
                )
                current = candidate_by_path.get(document)
                if current is None:
                    candidate_order.append(document)
                    candidate_by_path[document] = item
                elif priority_rank[priority] < priority_rank[current.category]:
                    candidate_by_path[document] = item

    for document in candidate_order:
        item = candidate_by_path[document]
        candidates[item.category].append(item)

    selected_docs: list[BundleItem] = []
    omitted: list[BundleItem] = []
    used = sum(item.bytes for item in selected_task_items)
    for priority in PRIORITIES:
        if priority == "Optional" and not include_optional:
            omitted.extend(candidates[priority])
            continue
        for item in candidates[priority]:
            if used + item.bytes <= task_budget:
                selected_docs.append(item)
                used += item.bytes
            elif priority == "Critical":
                raise ValueError(
                    f"Critical task documents exceed {task_budget} bytes at {item.path}"
                )
            else:
                omitted.append(item)

    for item in selected_task_items + selected_docs:
        add(item.path, item.category, item.reason)

    return ContextBundle(
        items=items,
        omitted=omitted,
        matched_routes=matched_routes,
        automatic_instruction_bytes=instruction_bytes,
        routing_control_bytes=routing_bytes,
        task_document_bytes=used,
        total_bytes=sum(item.bytes for item in items),
        task_document_budget_bytes=task_budget,
    )


def _print_text(bundle: ContextBundle) -> None:
    for index, item in enumerate(bundle.items, start=1):
        print(f"{index:02d}. {item.path} ({item.bytes} bytes; {item.category})")
    print(f"matched routes: {', '.join(bundle.matched_routes) or 'none'}")
    print(
        "bytes: "
        f"instructions={bundle.automatic_instruction_bytes}, "
        f"routing={bundle.routing_control_bytes}, "
        f"task-docs={bundle.task_document_bytes}/"
        f"{bundle.task_document_budget_bytes}, total={bundle.total_bytes}"
    )
    if bundle.omitted:
        print("omitted by budget/priority:")
        for item in bundle.omitted:
            print(f"- {item.path} ({item.bytes} bytes; {item.category})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", nargs="*", default=[])
    parser.add_argument("--triggers", nargs="*", default=[])
    parser.add_argument("--include-optional", action="store_true")
    parser.add_argument("--budget-bytes", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        bundle = build_bundle(
            args.paths,
            args.triggers,
            include_optional=args.include_optional,
            budget_bytes=args.budget_bytes,
        )
    except (KeyError, OSError, ValueError) as exc:
        print(f"context bundle error: {exc}")
        return 1
    if args.json:
        print(json.dumps(asdict(bundle), indent=2))
    else:
        _print_text(bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
