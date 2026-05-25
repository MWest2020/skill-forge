"""Tests for federation — change #8 add-federation.

Two local instances exchange a skill: instance A signs and publishes,
instance B pulls and verifies.
"""

from __future__ import annotations

import threading
from datetime import date
from http.server import HTTPServer
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.federation import Peer, PeerError, PullError, add_peer
from skill_forge.federation.peers import (
    PeersFile,
    list_peers,
    read_peers,
    remove_peer,
    write_peers,
)
from skill_forge.federation.pull import fetch_manifest, pull_skill
from skill_forge.identity import from_seed
from skill_forge.mcp.handlers import dispatch
from skill_forge.mcp.server import _build_handler
from skill_forge.models import Skill, SourceRef
from skill_forge.storage import filesystem as fs

runner = CliRunner()


def _skill(name: str, visibility: str = "public") -> Skill:
    return Skill(
        name=name, description=f"Use this skill when {name}.", version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="## When to use\n...\n## Procedure\n...\n## Failure modes\n...\n",
        visibility=visibility,
    )


# --- peers.yml model + CRUD ---------------------------------------------------


def test_peer_round_trip(tmp_path: Path) -> None:
    pf = PeersFile(peers=[Peer(name="alice", url="http://a.example")])
    write_peers(tmp_path, pf)
    loaded = read_peers(tmp_path)
    assert loaded.peers[0].name == "alice"


def test_peer_name_validation() -> None:
    with pytest.raises(ValueError):
        Peer(name="Bad Name", url="http://x")


def test_peer_trust_auto_import_refused() -> None:
    with pytest.raises(ValueError, match="auto-import"):
        Peer(name="x", url="http://x", trust_mode="auto-import")


def test_add_peer_duplicate_refused(tmp_path: Path) -> None:
    add_peer(tmp_path, Peer(name="alice", url="http://a"))
    with pytest.raises(PeerError, match="already registered"):
        add_peer(tmp_path, Peer(name="alice", url="http://a"))


def test_remove_peer(tmp_path: Path) -> None:
    add_peer(tmp_path, Peer(name="alice", url="http://a"))
    assert remove_peer(tmp_path, "alice") is True
    assert remove_peer(tmp_path, "alice") is False  # second call no-op


def test_list_peers_empty(tmp_path: Path) -> None:
    assert list_peers(tmp_path) == []


# --- federation/* MCP methods -------------------------------------------------


def test_federation_manifest_filters_visibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Set up an identity so peer-info works
    home = tmp_path / "id"
    monkeypatch.setenv("SKILL_FORGE_HOME", str(home))
    from_seed(home, b"\x01" * 32)

    fs.write_skill(tmp_path, _skill("alpha", visibility="public"), draft=False)
    fs.write_skill(tmp_path, _skill("beta", visibility="private"), draft=False)
    fs.write_skill(tmp_path, _skill("gamma", visibility="unlisted"), draft=False)

    response = dispatch(tmp_path, {"jsonrpc": "2.0", "method": "federation/manifest", "id": 1})
    assert response is not None
    slugs = sorted(s["slug"] for s in response["result"]["skills"])
    assert slugs == ["alpha"]


def test_federation_peer_info_returns_id_and_pem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "id"
    monkeypatch.setenv("SKILL_FORGE_HOME", str(home))
    identity = from_seed(home, b"\x02" * 32)

    response = dispatch(tmp_path, {"jsonrpc": "2.0", "method": "federation/peer-info", "id": 1})
    assert response is not None
    assert response["result"]["instance_id"] == identity.instance_id
    assert "BEGIN PUBLIC KEY" in response["result"]["public_key_pem"]


def test_federation_skill_refuses_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "id"
    monkeypatch.setenv("SKILL_FORGE_HOME", str(home))
    from_seed(home, b"\x03" * 32)
    fs.write_skill(tmp_path, _skill("private-one", visibility="private"), draft=False)

    from skill_forge.mcp.handlers import McpError

    with pytest.raises(McpError, match="unknown skill"):
        dispatch(
            tmp_path,
            {"jsonrpc": "2.0", "method": "federation/skill", "id": 1,
             "params": {"slug": "private-one"}},
        )


def test_federation_skill_serves_unlisted_by_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "id"
    monkeypatch.setenv("SKILL_FORGE_HOME", str(home))
    from_seed(home, b"\x04" * 32)
    fs.write_skill(tmp_path, _skill("hidden", visibility="unlisted"), draft=False)

    response = dispatch(
        tmp_path,
        {"jsonrpc": "2.0", "method": "federation/skill", "id": 1,
         "params": {"slug": "hidden"}},
    )
    assert response is not None
    assert response["result"]["skill"]["name"] == "hidden"


# --- end-to-end pull between two local instances -----------------------------


def _start_server(root: Path) -> tuple[str, HTTPServer]:
    handler_cls = _build_handler(root, token=None)
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}", server


def test_pull_skill_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Instance A publishes a signed public skill; instance B pulls + verifies."""
    # Instance A: identity + repo with a public, signed skill
    a_home = tmp_path / "a-id"
    a_root = tmp_path / "a-repo"
    a_id = from_seed(a_home, b"\xaa" * 32)
    monkeypatch.setenv("SKILL_FORGE_HOME", str(a_home))
    fs.write_skill(a_root, _skill("shared-skill"), draft=False, identity=a_id)

    # Stand up instance A's HTTP server (no token — loopback)
    url, server = _start_server(a_root)
    try:
        # Instance B: register A as a peer, then pull
        b_root = tmp_path / "b-repo"
        peer = Peer(name="alpha", url=url)
        add_peer(b_root, peer)
        peer_obj = read_peers(b_root).peers[0]

        # Need instance B's environment for SKILL_FORGE_HOME so a_id is used
        # for the federation/peer-info call (the server uses the env at dispatch time).
        # The env is already set to a_home above, so peer-info returns A's identity.
        pulled = pull_skill(b_root, peer_obj, "shared-skill")
        assert pulled.name == "shared-skill"
        assert pulled.origin is not None
        assert pulled.origin.startswith(a_id.instance_id)
        # Landed in B's draft area
        assert (b_root / "skills" / "_draft" / "shared-skill" / "SKILL.md").is_file()
        # Source provenance points at the peer
        sources = fs.read_sources(b_root, "shared-skill")
        assert sources.sources[0].url.startswith("federation:alpha:")

        # Peer's identity got cached on B's side
        peers_after = read_peers(b_root)
        assert peers_after.peers[0].instance_id == a_id.instance_id
        assert "BEGIN PUBLIC KEY" in (peers_after.peers[0].public_key_pem or "")
    finally:
        server.shutdown()


def test_pull_refuses_peer_serving_foreign_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If A serves a skill whose origin doesn't match A's instance_id, pull rejects."""
    a_home = tmp_path / "a-id"
    a_root = tmp_path / "a-repo"
    from_seed(a_home, b"\xbb" * 32)
    monkeypatch.setenv("SKILL_FORGE_HOME", str(a_home))

    # Put a skill in A's repo whose origin claims a *different* peer.
    pem_id = "forge-deadbeef"  # not A's instance_id
    foreign_skill = _skill("foreign").model_copy(
        update={
            "origin": f"{pem_id}:foreign:1",
            "signature": "Zm9v",  # bogus, signature check will fail before this anyway
        }
    )
    fs.write_skill(a_root, foreign_skill, draft=False)

    url, server = _start_server(a_root)
    try:
        b_root = tmp_path / "b-repo"
        peer = Peer(name="alpha", url=url)
        add_peer(b_root, peer)
        peer_obj = read_peers(b_root).peers[0]
        with pytest.raises(PullError, match="doesn't match its instance_id"):
            pull_skill(b_root, peer_obj, "foreign")
    finally:
        server.shutdown()


def test_fetch_manifest_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a_home = tmp_path / "a-id"
    a_root = tmp_path / "a-repo"
    from_seed(a_home, b"\xcc" * 32)
    monkeypatch.setenv("SKILL_FORGE_HOME", str(a_home))
    fs.write_skill(a_root, _skill("pub1"), draft=False)
    fs.write_skill(a_root, _skill("priv1", visibility="private"), draft=False)

    url, server = _start_server(a_root)
    try:
        peer = Peer(name="alpha", url=url)
        skills = fetch_manifest(peer)
        assert [s["slug"] for s in skills] == ["pub1"]
    finally:
        server.shutdown()


# --- CLI ---------------------------------------------------------------------


def test_cli_peer_add_list_remove(tmp_path: Path) -> None:
    result = runner.invoke(app, ["peer", "add", "alice", "http://a.example", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "Added peer: alice" in result.output

    result = runner.invoke(app, ["peer", "list", "--root", str(tmp_path)])
    assert "alice" in result.output

    result = runner.invoke(app, ["peer", "remove", "alice", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "Removed peer" in result.output


def test_cli_peer_remove_unknown(tmp_path: Path) -> None:
    result = runner.invoke(app, ["peer", "remove", "ghost", "--root", str(tmp_path)])
    assert result.exit_code == 1
