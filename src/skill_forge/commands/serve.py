"""`forge serve mcp` — read-only MCP server over stdio.

Lets a containerized agent pull a specific skillset (`get_skillset`) without a
shared filesystem. Read-only: no intake/curation tools are exposed.
"""

from __future__ import annotations

from skill_forge.cli import RootOpt, _resolve_root, serve_app


@serve_app.command(name="mcp")
def serve_mcp(root: RootOpt = None) -> None:
    """Start a read-only MCP server (stdio) over the live skill library.

    Run it from a container to pull skillsets: it exposes `list_skills`,
    `get_skill`, and `get_skillset` — nothing that mutates state.
    """
    from skill_forge.mcp import build_server

    base = _resolve_root(root)
    build_server(base).run()
