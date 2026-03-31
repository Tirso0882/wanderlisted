"""Centralised config loader — reads config/config.yaml once at import time."""

from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"

_cache: dict[str, Any] | None = None


def load_config() -> dict[str, Any]:
    """Load and cache the YAML configuration."""
    global _cache
    if _cache is None:
        with open(_CONFIG_PATH) as f:
            _cache = yaml.safe_load(f)
    return _cache


def get(section: str, key: str | None = None, default: Any = None) -> Any:
    """Convenience accessor: ``config.get("rag", "chunk_size", 2000)``."""
    cfg = load_config()
    section_data = cfg.get(section, {})
    if key is None:
        return section_data if section_data else default
    return section_data.get(key, default)
