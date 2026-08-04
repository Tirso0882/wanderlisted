"""Shared helpers for documentation tooling."""

from __future__ import annotations

import fnmatch
import glob
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
FRONTMATTER_BOUNDARY = "---"


def load_yaml(path: Path) -> dict[str, Any]:
    """Load one YAML mapping."""
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return value


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Return YAML frontmatter and body from a Markdown document."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_BOUNDARY:
        return {}, text
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == FRONTMATTER_BOUNDARY
        )
    except StopIteration as exc:
        raise ValueError(f"{path.relative_to(ROOT)} has unclosed frontmatter") from exc
    raw = "\n".join(lines[1:end])
    metadata = yaml.safe_load(raw) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"{path.relative_to(ROOT)} frontmatter must be a mapping")
    return metadata, "\n".join(lines[end + 1 :]).lstrip("\n")


def first_heading(body: str, fallback: str) -> str:
    """Extract the first H1 title."""
    match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    return match.group(1).strip() if match else fallback


def matches_any(value: str, patterns: list[str]) -> bool:
    """Match a repository-relative value against shell-style patterns."""
    normalized = value.replace("\\", "/").lstrip("./")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def resolve_declared_path(root: Path, declared: str) -> list[Path]:
    """Resolve an exact path or glob without reading file contents."""
    if any(character in declared for character in "*?["):
        return [
            Path(value) for value in glob.glob(str(root / declared), recursive=True)
        ]
    candidate = root / declared
    return [candidate] if candidate.exists() else []
