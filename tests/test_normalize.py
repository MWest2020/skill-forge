"""Tests for normalize_skill_md — preserve-tool-and-source-fidelity."""

from __future__ import annotations

import yaml

from skill_forge.import_skill.normalize import normalize_skill_md
from skill_forge.models import Skill

_VANILLA = """---
name: demo-skill
description: A demo.
allowed-tools:
  - Read
  - Bash
unknown-field: dropped
---

# Demo
"""


def _frontmatter(content: str) -> dict[str, object]:
    _, fm, _ = content.split("---", 2)
    return yaml.safe_load(fm)


def test_allowed_tools_survives_normalization() -> None:
    fm = _frontmatter(normalize_skill_md(_VANILLA, source_url=None))
    assert fm["allowed-tools"] == ["Read", "Bash"]
    assert "unknown-field" not in fm


def test_repo_import_sources_ref_carries_url() -> None:
    url = "https://github.com/anthropics/skills/blob/main/demo/SKILL.md"
    fm = _frontmatter(normalize_skill_md(_VANILLA, source_url=url))
    assert fm["sources"][0]["url"] == url


def test_local_import_sources_ref_has_no_url() -> None:
    fm = _frontmatter(normalize_skill_md(_VANILLA, source_url=None))
    assert "url" not in fm["sources"][0]


def test_normalized_output_parses_into_skill_model() -> None:
    content = normalize_skill_md(_VANILLA, source_url="https://example.com/s")
    fm = _frontmatter(content)
    skill = Skill(**fm, body="# Demo\n")
    assert skill.allowed_tools == ["Read", "Bash"]
    assert skill.sources[0].url == "https://example.com/s"


def test_comma_separated_allowed_tools_becomes_list() -> None:
    skill = Skill(
        name="demo-skill",
        description="A demo.",
        version=1,
        sources=[{"id": "src-abc123"}],
        created="2026-07-13",
        body="x",
        **{"allowed-tools": "Read, Bash, Write"},
    )
    assert skill.allowed_tools == ["Read", "Bash", "Write"]
