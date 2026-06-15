"""Tests for the read-only MCP server — add-skillsets-and-mcp #5-8."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import pytest

from skill_forge.mcp.server import (
    build_server,
    get_skill,
    get_skillset,
    list_skills,
)
from skill_forge.models import Skill, SourceRef
from skill_forge.storage import filesystem as fs


def _skill(name: str, tags: list[str] | None = None) -> Skill:
    return Skill(
        name=name,
        description=f"Use {name} when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body=f"# {name}\n",
        tags=tags or [],
    )


def _seed(tmp_path: Path, name: str, tags: list[str], *, draft: bool = False) -> None:
    fs.write_skill(tmp_path, _skill(name, tags), draft=draft)


# --- task 5: skeleton + advertised tools -------------------------------------


def test_server_advertises_three_tools(tmp_path: Path) -> None:
    srv = build_server(tmp_path)
    names = {t.name for t in asyncio.run(srv.list_tools())}
    assert names == {"list_skills", "get_skill", "get_skillset"}


# --- task 6: list_skills + get_skill -----------------------------------------


def test_list_skills_live_only_with_tag_filter(tmp_path: Path) -> None:
    _seed(tmp_path, "sec", ["security"])
    _seed(tmp_path, "web", ["web"])
    _seed(tmp_path, "wip", ["security"], draft=True)  # draft is invisible

    all_live = list_skills(tmp_path)
    assert {s["slug"] for s in all_live} == {"sec", "web"}
    assert all_live[0]["description"]  # descriptions included, no body key
    assert "body" not in all_live[0]

    sec = list_skills(tmp_path, "security")
    assert {s["slug"] for s in sec} == {"sec"}  # draft 'wip' excluded
    assert list_skills(tmp_path, "nope") == []


def test_get_skill_returns_body_and_provenance(tmp_path: Path) -> None:
    _seed(tmp_path, "sec", ["security"])
    payload = get_skill(tmp_path, "sec")
    assert payload["slug"] == "sec"
    assert "# sec" in payload["body"]
    assert payload["tags"] == ["security"]
    assert payload["version"] == 1
    assert "origin" in payload


def test_get_skill_unknown_or_draft_raises(tmp_path: Path) -> None:
    _seed(tmp_path, "wip", ["security"], draft=True)
    with pytest.raises(ValueError, match="skill not found: nope"):
        get_skill(tmp_path, "nope")
    with pytest.raises(ValueError, match="skill not found: wip"):
        get_skill(tmp_path, "wip")  # draft is not reachable over MCP


# --- task 7: get_skillset ----------------------------------------------------


def test_get_skillset_bundles_live_tagged_skills(tmp_path: Path) -> None:
    _seed(tmp_path, "sec", ["security"])
    _seed(tmp_path, "auth", ["security"])
    _seed(tmp_path, "web", ["web"])
    _seed(tmp_path, "wip", ["security"], draft=True)

    bundle = get_skillset(tmp_path, "security")
    assert bundle["tag"] == "security"
    assert {s["slug"] for s in bundle["skills"]} == {"auth", "sec"}  # live only
    assert all("body" in s for s in bundle["skills"])


def test_get_skillset_empty_is_not_an_error(tmp_path: Path) -> None:
    assert get_skillset(tmp_path, "nope") == {"tag": "nope", "skills": []}
