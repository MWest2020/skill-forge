"""Tiny config loader: bundled defaults overlaid by `config/default.yml`.

Spec: openspec/changes/add-claude-code-provider/specs/config/spec.md
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "rubric": {
        "weights": {
            "schema_compliance": 0.20,
            "clarity": 0.20,
            "actionability": 0.25,
            "gap_coverage": 0.20,
            "provenance_quality": 0.15,
        },
    },
    "promotion": {"total_min": 0.75, "axis_min": 0.50},
    "providers": {
        "extract": "claude_code",
        "judge": "claude_code",
    },
    "anthropic": {"model": "claude-opus-4-7", "max_tokens": 4096},
    "claude_code": {"binary": "claude", "timeout_s": 120},
    "discovery": {
        "max_candidates": 10,
        "user_agent": "skill-forge/0.1 (+https://github.com/MWest2020/skill-forge)",
        "respect_robots_txt": True,
    },
    "paths": {
        "skills": "skills",
        "drafts": "skills/_draft",
        "sources": "sources",
        "runs": "runs",
    },
}


def load(root: Path | None = None) -> dict[str, Any]:
    """Return the merged config dict for the given project root."""
    base = deepcopy(DEFAULTS)
    config_path = (root or Path.cwd()) / "config" / "default.yml"
    if not config_path.is_file():
        return base
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(parsed, dict):
        return base
    return _merge(base, parsed)


def _merge(into: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge `src` into `into` (returns `into`). Lists replace."""
    for key, value in src.items():
        if (
            key in into
            and isinstance(into[key], dict)
            and isinstance(value, dict)
        ):
            _merge(into[key], value)
        else:
            into[key] = value
    return into
