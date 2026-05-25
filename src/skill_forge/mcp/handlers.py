"""MCP JSON-RPC handlers for skill-forge. Read-only v1.

The Model Context Protocol exchanges JSON-RPC 2.0 messages. We implement
just enough to surface promoted skills as `resources`: `initialize`,
`resources/list`, `resources/read`.

Spec: openspec/changes/add-mcp-server-mode/proposal.md
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from skill_forge.models import SLUG_RE
from skill_forge.storage import filesystem as storage

log = logging.getLogger(__name__)

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
        # Log the full traceback for local debugging; wire only carries the
        # message so we don't leak internals to remote clients.
        log.exception("MCP handler error in %s", method)
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
    if method == "federation/peer-info":
        return _federation_peer_info(root)
    if method == "federation/manifest":
        return _federation_manifest(root)
    if method == "federation/skill":
        return _federation_skill(root, params)
    raise McpError(-32601, f"method not found: {method}")


def _list_resources(root: Path) -> list[dict[str, str]]:
    """List skills visible to MCP clients. Excludes drafts AND non-public
    skills — `unlisted` is callable-by-slug but not enumerable, matching
    federation/manifest semantics."""
    out: list[dict[str, str]] = []
    for entry in storage.list_skills(root):
        if entry.draft:
            continue
        try:
            skill = storage.read_skill(root, entry.slug)
        except (FileNotFoundError, ValueError):
            continue
        if skill.visibility != "public":
            continue
        out.append({
            "uri": f"{RESOURCE_PREFIX}{entry.slug}",
            "name": skill.name,
            "description": skill.description,
            "mimeType": RESOURCE_MIME,
        })
    return out


def _federation_peer_info(root: Path) -> dict[str, Any]:
    """Return this instance's ID + public key (PEM). Read by peers on first contact."""
    from cryptography.hazmat.primitives import serialization

    from skill_forge.identity import get_or_create

    home = _identity_home()
    identity = get_or_create(home)
    pem = identity.public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return {"instance_id": identity.instance_id, "public_key_pem": pem}


def _federation_manifest(root: Path) -> dict[str, Any]:
    """Return only `public` skills with their basic metadata. Private + unlisted hidden."""
    out: list[dict[str, Any]] = []
    for entry in storage.list_skills(root):
        if entry.draft:
            continue
        try:
            skill = storage.read_skill(root, entry.slug)
        except (FileNotFoundError, ValueError):
            continue
        if skill.visibility != "public":
            continue
        out.append({
            "slug": skill.name,
            "description": skill.description,
            "judge_score": skill.judge_score,
            "origin": skill.origin,
        })
    return {"skills": out}


def _federation_skill(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Return one skill's full record (frontmatter + body + signature) by slug.

    Honors visibility: `private` never served, `unlisted` served if asked
    by exact slug, `public` always served.
    """
    slug = params.get("slug")
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise McpError(-32602, f"invalid slug: {slug!r}")
    try:
        skill = storage.read_skill(root, slug)
    except FileNotFoundError as exc:
        raise McpError(-32602, f"unknown skill: {slug!r}") from exc
    if skill.visibility == "private":
        raise McpError(-32602, f"unknown skill: {slug!r}")
    return {"skill": skill.model_dump(mode="json")}


def _identity_home() -> Path:
    import os

    env = os.environ.get("SKILL_FORGE_HOME")
    return Path(env) if env else Path.home() / ".config" / "skill-forge"


def _read_resource(root: Path, params: dict[str, Any]) -> dict[str, Any]:
    uri = params.get("uri")
    if not isinstance(uri, str) or not uri.startswith(RESOURCE_PREFIX):
        raise McpError(-32602, f"uri must start with {RESOURCE_PREFIX}")
    slug = uri[len(RESOURCE_PREFIX):]
    # Validate against the canonical slug shape — anything else (path
    # traversal, draft-tree probing, .iterations/ access) gets rejected
    # before we touch the filesystem.
    if not SLUG_RE.fullmatch(slug):
        raise McpError(-32602, f"invalid slug in uri: {uri}")
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
