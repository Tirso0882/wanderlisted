"""Hermetic contracts for the shared Copilot/Codex documentation plane."""

from pathlib import Path

import pytest

from scripts.docs.check_docs import EXPECTED_SKILLS, collect_errors
from scripts.docs.context_bundle import ROOT, build_bundle


def test_documentation_contract_is_valid() -> None:
    assert collect_errors(ROOT) == []


@pytest.mark.parametrize(
    ("path", "scoped_agents", "expected_document"),
    [
        (
            "src/budget/pipeline.py",
            "src/budget/AGENTS.md",
            "docs/features/budget/FEATURE.md",
        ),
        (
            "frontend/src/stores/chat-store.ts",
            "frontend/AGENTS.md",
            "docs/domain/delivery.md",
        ),
        (
            "infra/main.bicep",
            "infra/AGENTS.md",
            "docs/architecture/DEPLOYMENT_VIEW.md",
        ),
        (
            "src/readiness/pipeline.py",
            "src/readiness/AGENTS.md",
            "docs/features/travel-readiness/FEATURE.md",
        ),
        (
            "src/itinerary/pipeline.py",
            "src/itinerary/AGENTS.md",
            "docs/features/itinerary/FEATURE.md",
        ),
    ],
)
def test_context_routing_is_shared_and_bounded(
    path: str, scoped_agents: str, expected_document: str
) -> None:
    bundle = build_bundle([path], [])
    selected = [item.path for item in bundle.items]
    assert selected[:2] == ["AGENTS.md", scoped_agents]
    assert "docs/agent-map.yaml" in selected
    assert expected_document in selected
    assert bundle.automatic_instruction_bytes <= 8192
    assert bundle.task_document_bytes <= bundle.task_document_budget_bytes


def test_copilot_and_codex_share_one_skill_directory() -> None:
    skill_root = ROOT / ".agents/skills"
    assert {
        path.name for path in skill_root.iterdir() if path.is_dir()
    } == EXPECTED_SKILLS
    assert not (ROOT / ".github/skills").exists()
    assert ".agents/skills/" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert ".agents/skills/" in (ROOT / ".github/copilot-instructions.md").read_text(
        encoding="utf-8"
    )


def test_context_bundle_does_not_return_source_files() -> None:
    bundle = build_bundle(["src/budget/pipeline.py"], ["pricing"])
    allowed = ("AGENTS.md", "docs/", "src/budget/AGENTS.md")
    assert all(item.path.startswith(allowed) for item in bundle.items)
    assert all(Path(item.path).suffix in {".md", ".yaml"} for item in bundle.items)


def test_context_bundle_promotes_the_highest_matched_priority() -> None:
    bundle = build_bundle(["src/tools/tavily.py"], ["evaluation"])
    cost_control = next(
        item for item in bundle.items if item.path == "docs/operations/COST_CONTROLS.md"
    )
    assert cost_control.category == "Critical"
