"""Read-only MCP transport for the curated skill library.

Lets containerized agents pull a specific skillset over stdio without a shared
filesystem. Read-only by contract: no intake/curation tools are exposed.
"""

from skill_forge.mcp.server import build_server

__all__ = ["build_server"]
