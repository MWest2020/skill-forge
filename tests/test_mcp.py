"""Tests for the read-only MCP server — add-skillsets-and-mcp #5-8."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import pytest

from skill_forge.mcp.server import build_server
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
