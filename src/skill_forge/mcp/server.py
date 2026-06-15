"""Read-only MCP server exposing the live skill library.

Three tools — `list_skills`, `get_skill`, `get_skillset` — let a consumer pull
a skillset over stdio. Everything here is read-only and live-only: draft skills
are invisible, and no tool imports, judges, promotes, or runs a provider. The
tool bodies delegate to small pure functions so the logic is testable without
standing up an MCP transport.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from skill_forge.models import Skill
from skill_forge.storage import filesystem as storage


def _read_live(root: Path, slug: str) -> Skill | None:
    """The live Skill for `slug`, or None if it is not promoted (drafts are
    invisible over MCP)."""
    path = root / "skills" / slug / "SKILL.md"
    if not path.is_file():
        return None
    return storage.read_skill_file(path)


def _skill_payload(slug: str, skill: Skill) -> dict[str, Any]:
    return {
        "slug": slug,
        "body": skill.body,
        "tags": skill.tags,
        "origin": skill.origin,
        "version": skill.version,
    }


def list_skills(root: Path, tag: str | None = None) -> list[dict[str, Any]]:
    """Live skills (slug + description + tags), optionally filtered to `tag`.

    Sorted by slug. No bodies — this is the cheap listing. Unknown/absent tag
    with no matches yields an empty list.
    """
    out: list[dict[str, Any]] = []
    for entry in storage.list_skills(root):
        if entry.draft:
            continue
        if tag is not None and tag not in entry.tags:
            continue
        skill = _read_live(root, entry.slug)
        if skill is None:
            continue
        out.append({"slug": entry.slug, "description": skill.description, "tags": entry.tags})
    return out


def get_skill(root: Path, slug: str) -> dict[str, Any]:
    """One live skill: body + tags + provenance. Raises on unknown/draft-only
    slug (FastMCP surfaces it as a tool error)."""
    skill = _read_live(root, slug)
    if skill is None:
        raise ValueError(f"skill not found: {slug}")
    return _skill_payload(slug, skill)


def get_skillset(root: Path, tag: str) -> dict[str, Any]:
    """Every live skill carrying `tag`, bodies included — the bundle a consumer
    mounts. Empty skillset yields `{tag, skills: []}` (not an error)."""
    skills = [get_skill(root, slug) for slug in storage.live_skills_with_tag(root, tag)]
    return {"tag": tag, "skills": skills}


def build_server(root: Path) -> FastMCP:
    """Build the read-only MCP server bound to `root`'s live library."""
    server = FastMCP("skill-forge")

    @server.tool(name="list_skills")
    def list_skills_tool(tag: str | None = None) -> list[dict[str, Any]]:
        """List live skills (slug, description, tags), optionally filtered by tag."""
        return list_skills(root, tag)

    @server.tool(name="get_skill")
    def get_skill_tool(slug: str) -> dict[str, Any]:
        """Fetch one live skill's SKILL.md body, tags, and provenance."""
        return get_skill(root, slug)

    @server.tool(name="get_skillset")
    def get_skillset_tool(tag: str) -> dict[str, Any]:
        """Fetch every live skill carrying `tag` as a bundle (bodies included)."""
        return get_skillset(root, tag)

    return server
