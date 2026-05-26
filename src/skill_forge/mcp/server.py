"""MCP server transports: stdio + HTTP.

stdio framing is the standard MCP shape — one JSON-RPC object per line on
stdin, one per line on stdout. HTTP follows the Streamable-HTTP profile
loosely: POST /mcp with a JSON-RPC object, returns a single JSON-RPC
response. Bearer auth required when binding to a non-loopback host.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from .handlers import McpError, dispatch


def serve_stdio(root: Path, *, stream_in: Any = None, stream_out: Any = None) -> None:
    """Read JSON-RPC objects line-by-line from stdin, write responses to stdout."""
    inp = stream_in if stream_in is not None else sys.stdin
    out = stream_out if stream_out is not None else sys.stdout
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _write_error(out, None, -32700, f"parse error: {exc}")
            continue
        try:
            response = dispatch(root, request)
        except McpError as exc:
            _write_error(out, request.get("id"), exc.code, exc.message)
            continue
        if response is not None:
            out.write(json.dumps(response) + "\n")
            out.flush()


def serve_http(
    root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    token: str | None = None,
) -> None:
    """Block on a JSON-RPC HTTP server. Token required when host != loopback."""
    if host not in ("127.0.0.1", "localhost", "::1") and not token:
        raise ValueError(
            f"refusing to bind to non-loopback host {host!r} without --token; "
            "set --token or SKILL_FORGE_MCP_TOKEN"
        )
    handler_cls = _build_handler(root, token)
    server = HTTPServer((host, port), handler_cls)
    server.serve_forever()


def _write_error(out: Any, req_id: Any, code: int, message: str) -> None:
    err = {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }
    out.write(json.dumps(err) + "\n")
    out.flush()


def _build_handler(root: Path, token: str | None) -> type[BaseHTTPRequestHandler]:
    env_token = os.environ.get("SKILL_FORGE_MCP_TOKEN") or token

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass  # quiet — caller controls logging

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/mcp":
                self._error(404, "not found")
                return
            if env_token is not None:
                auth = self.headers.get("Authorization", "")
                expected = f"Bearer {env_token}"
                # Constant-time comparison removes any timing-oracle surface
                # if the server is ever exposed beyond loopback.
                if not hmac.compare_digest(auth, expected):
                    self._error(401, "unauthorized")
                    return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                self._error(400, "empty body")
                return
            body = self.rfile.read(length)
            try:
                request = json.loads(body)
            except json.JSONDecodeError as exc:
                self._error(400, f"parse error: {exc}")
                return
            try:
                response = dispatch(root, request)
            except McpError as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"code": exc.code, "message": exc.message},
                }
            if response is None:
                # Notification — return 204 No Content
                self.send_response(204)
                self.end_headers()
                return
            payload = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _error(self, status: int, message: str) -> None:
            payload = json.dumps({"error": {"code": status, "message": message}}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return _Handler
