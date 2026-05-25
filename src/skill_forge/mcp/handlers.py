"""MCP JSON-RPC handlers for skill-forge. Read-only v1.

The Model Context Protocol exchanges JSON-RPC 2.0 messages. We implement
just enough to surface promoted skills as `resources`: `initialize`,
`resources/list`, `resources/read`.

Spec: openspec/changes/add-mcp-server-mode/proposal.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skill_forge.storage import filesystem as storage

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "skill-forge"
SERVER_VERSION = "0.1.0"
RESOURCE_PREFIX = "skill-forge://skill/"
RESOURCE_MIME = "text/markdown"


class McpError(Exception):
    """JSON-RPC error wrapper. .code is the JSON-RPC error code."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def dispatch(root: Path, request: dict[str, Any]) -> dict[str, Any] | None:
    """Dispatch one JSON-RPC request. Returns the response dict, or None for notifications."""
    if request.get("jsonrpc") != "2.0":
        raise McpError(-32600, "request must be JSON-RPC 2.0")
    method = request.get("method")
    req_id = request.get("id")
    is_notification = req_id is None
    params = request.get("params") or {}
    if not isinstance(method, str):
        raise McpError(-32600, "method missing")

    try:
        result = _handle(root, method, params if isinstance(params, dict) else {})
    except McpError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise McpError(-32603, f"internal error in {method}: {exc}") from exc

    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _handle(root: Path, method: str, params: dict[str, Any]) -> dict[str, Any]:
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "capabilities": {"resources": {"subscribe": False, "listChanged": False}},
        }
    if method == "notifications/initialized":
        return {}
    if method == "resources/list":
        return {"resources": _list_resources(root)}
    if method == "resources/read":
        return _read_resource(root, params)
    raise McpError(-32601, f"method not found: {method}")


def _list_resources(root: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for entry in storage.list_skills(root):
        if entry.draft:
            continue  # drafts are work-in-progress; consumers shouldn't see them
        try:
            skill = storage.read_skill(root, entry.slug)
        except (FileNotFoundError, ValueError):
            continue
        out.append({
            "uri": f"{RESOURCE_PREFIX}{entry.slug}",
            "name": skill.name,
            "description": skill.description,
            "mimeType": RESOURCE_MIME,
        })
    return out


def _read_resource(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    uri = params.get("uri")
    if not isinstance(uri, str) or not uri.startswith(RESOURCE_PREFIX):
        raise McpError(-32602, f"uri must start with {RESOURCE_PREFIX}")
    slug = uri[len(RESOURCE_PREFIX):]
    skill_md = root / "skills" / slug / "SKILL.md"
    if not skill_md.is_file():
        raise McpError(-32602, f"unknown resource: {uri}")
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": RESOURCE_MIME,
                "text": skill_md.read_text(encoding="utf-8"),
            }
        ]
    }
