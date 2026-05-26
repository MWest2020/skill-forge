"""Tests for MCP server mode — change #7 add-mcp-server-mode."""

from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pytest

from skill_forge.mcp.handlers import (
    PROTOCOL_VERSION,
    SERVER_NAME,
    McpError,
    dispatch,
)
from skill_forge.mcp.server import _build_handler, serve_http, serve_stdio
from skill_forge.models import Skill, SourceRef
from skill_forge.storage import filesystem as fs


def _skill(name: str = "demo") -> Skill:
    return Skill(
        name=name,
        description=f"Use this skill when {name}.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="## When to use\n...\n## Procedure\n...\n## Failure modes\n...\n",
    )


def _seed_promoted(tmp_path: Path, *names: str) -> None:
    """Seed PUBLIC skills so they show up in resources/list."""
    for name in names:
        fs.write_skill(
            tmp_path,
            _skill(name).model_copy(update={"visibility": "public"}),
            draft=False,
        )


def _req(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    body: dict = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params is not None:
        body["params"] = params
    return body


# --- handlers ----------------------------------------------------------------


def test_initialize_response(tmp_path: Path) -> None:
    response = dispatch(tmp_path, _req("initialize"))
    assert response is not None
    assert response["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert response["result"]["serverInfo"]["name"] == SERVER_NAME
    assert "resources" in response["result"]["capabilities"]


def test_resources_list_returns_promoted(tmp_path: Path) -> None:
    """resources/list filters to public-visibility live skills."""
    pub = _skill("alpha")
    fs.write_skill(tmp_path, pub.model_copy(update={"visibility": "public"}), draft=False)
    fs.write_skill(
        tmp_path, pub.model_copy(update={"name": "beta", "visibility": "public"}), draft=False
    )
    # Private + unlisted shouldn't be enumerable
    fs.write_skill(
        tmp_path, pub.model_copy(update={"name": "secret"}), draft=False
    )  # default private
    fs.write_skill(
        tmp_path, pub.model_copy(update={"name": "hidden", "visibility": "unlisted"}), draft=False
    )
    fs.write_skill(tmp_path, _skill("draft-only"), draft=True)

    response = dispatch(tmp_path, _req("resources/list"))
    assert response is not None
    uris = sorted(r["uri"] for r in response["result"]["resources"])
    assert uris == ["skill-forge://skill/alpha", "skill-forge://skill/beta"]


def test_resources_read_returns_body(tmp_path: Path) -> None:
    # Make the skill explicitly public so the read path returns it.
    pub = _skill("alpha").model_copy(update={"visibility": "public"})
    fs.write_skill(tmp_path, pub, draft=False)
    response = dispatch(
        tmp_path,
        _req("resources/read", {"uri": "skill-forge://skill/alpha"}),
    )
    assert response is not None
    contents = response["result"]["contents"]
    assert len(contents) == 1
    assert contents[0]["mimeType"] == "text/markdown"
    assert "## When to use" in contents[0]["text"]


def test_resources_read_unknown_uri(tmp_path: Path) -> None:
    with pytest.raises(McpError, match="unknown resource"):
        dispatch(
            tmp_path,
            _req("resources/read", {"uri": "skill-forge://skill/ghost"}),
        )


def test_resources_read_bad_uri_prefix(tmp_path: Path) -> None:
    with pytest.raises(McpError, match="must start with"):
        dispatch(tmp_path, _req("resources/read", {"uri": "https://x"}))


def test_resources_read_rejects_path_traversal(tmp_path: Path) -> None:
    """The slug must match SLUG_RE — no ../ or _draft/ probing allowed."""
    for bad in (
        "skill-forge://skill/../../etc/passwd",
        "skill-forge://skill/../secrets",
        "skill-forge://skill/_draft/some-draft",
        "skill-forge://skill/foo/.iterations/v1",
        "skill-forge://skill/UPPER",
        "skill-forge://skill/",
    ):
        with pytest.raises(McpError, match="invalid slug"):
            dispatch(tmp_path, _req("resources/read", {"uri": bad}))


def test_unknown_method(tmp_path: Path) -> None:
    with pytest.raises(McpError, match="method not found"):
        dispatch(tmp_path, _req("tools/list"))


def test_non_jsonrpc_request(tmp_path: Path) -> None:
    with pytest.raises(McpError, match="JSON-RPC 2.0"):
        dispatch(tmp_path, {"method": "x", "id": 1})


def test_notification_returns_none(tmp_path: Path) -> None:
    # Notifications have no `id` field
    response = dispatch(tmp_path, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert response is None


# --- stdio transport ---------------------------------------------------------


def test_stdio_round_trip(tmp_path: Path) -> None:
    _seed_promoted(tmp_path, "alpha")
    stream_in = io.StringIO(
        json.dumps(_req("initialize")) + "\n" + json.dumps(_req("resources/list", req_id=2)) + "\n"
    )
    stream_out = io.StringIO()
    serve_stdio(tmp_path, stream_in=stream_in, stream_out=stream_out)
    lines = [json.loads(line) for line in stream_out.getvalue().splitlines() if line]
    assert lines[0]["id"] == 1
    assert "protocolVersion" in lines[0]["result"]
    assert lines[1]["id"] == 2
    assert lines[1]["result"]["resources"][0]["uri"].endswith("/alpha")


def test_stdio_parse_error(tmp_path: Path) -> None:
    stream_in = io.StringIO("not valid json\n")
    stream_out = io.StringIO()
    serve_stdio(tmp_path, stream_in=stream_in, stream_out=stream_out)
    err = json.loads(stream_out.getvalue().strip())
    assert err["error"]["code"] == -32700


def test_stdio_mcp_error_responds(tmp_path: Path) -> None:
    stream_in = io.StringIO(json.dumps(_req("tools/list", req_id=42)) + "\n")
    stream_out = io.StringIO()
    serve_stdio(tmp_path, stream_in=stream_in, stream_out=stream_out)
    err = json.loads(stream_out.getvalue().strip())
    assert err["error"]["code"] == -32601
    assert err["id"] == 42


# --- HTTP transport ----------------------------------------------------------


def _start_http_server(
    tmp_path: Path, *, token: str | None = None
) -> tuple[str, threading.Thread, object]:
    """Start serve_http in a thread on a random port. Returns (base_url, thread, server)."""
    from http.server import HTTPServer

    handler_cls = _build_handler(tmp_path, token)
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{port}", thread, server


def _post_json(url: str, payload: dict, *, headers: dict | None = None) -> tuple[int, dict | None]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body) if body else None


def test_http_resources_list(tmp_path: Path) -> None:
    _seed_promoted(tmp_path, "alpha")
    url, _t, server = _start_http_server(tmp_path)
    try:
        status, body = _post_json(f"{url}/mcp", _req("resources/list"))
        assert status == 200
        assert body is not None
        assert body["result"]["resources"][0]["uri"].endswith("/alpha")
    finally:
        server.shutdown()  # type: ignore[attr-defined]


def test_http_requires_token_when_configured(tmp_path: Path) -> None:
    _seed_promoted(tmp_path, "alpha")
    url, _t, server = _start_http_server(tmp_path, token="secret-token")
    try:
        # No auth header → 401
        status, body = _post_json(f"{url}/mcp", _req("resources/list"))
        assert status == 401

        # Wrong token → 401
        status, body = _post_json(
            f"{url}/mcp",
            _req("resources/list"),
            headers={"Authorization": "Bearer wrong"},
        )
        assert status == 401

        # Right token → 200
        status, body = _post_json(
            f"{url}/mcp",
            _req("resources/list"),
            headers={"Authorization": "Bearer secret-token"},
        )
        assert status == 200
    finally:
        server.shutdown()  # type: ignore[attr-defined]


def test_http_refuses_non_loopback_without_token(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-loopback"):
        serve_http(tmp_path, host="0.0.0.0", port=0, token=None)


def test_http_returns_404_for_other_paths(tmp_path: Path) -> None:
    url, _t, server = _start_http_server(tmp_path)
    try:
        status, _ = _post_json(f"{url}/wrong", _req("resources/list"))
        assert status == 404
    finally:
        server.shutdown()  # type: ignore[attr-defined]
