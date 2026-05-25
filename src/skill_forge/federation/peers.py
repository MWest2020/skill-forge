"""Peer registry: peers.yml at repo root."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

_PEER_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TRUST_MODES = {"reference-only", "review-queue"}  # auto-import not yet supported


class PeerError(Exception):
    """Peer-management errors."""


class Peer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    url: str
    token: str | None = None  # bearer for the peer's MCP HTTP endpoint
    instance_id: str | None = None  # cached on first contact
    public_key_pem: str | None = None  # cached on first contact
    trust_mode: str = "reference-only"

    @field_validator("name")
    @classmethod
    def _name_shape(cls, v: str) -> str:
        if not _PEER_NAME_RE.fullmatch(v):
            raise ValueError(f"Peer.name must be slug-shaped, got {v!r}")
        return v

    @field_validator("trust_mode")
    @classmethod
    def _trust_allowed(cls, v: str) -> str:
        if v == "auto-import":
            raise ValueError("auto-import trust mode not yet supported")
        if v not in _TRUST_MODES:
            raise ValueError(f"trust_mode must be one of {sorted(_TRUST_MODES)}, got {v!r}")
        return v


class PeersFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    peers: list[Peer] = []


def read_peers(root: Path) -> PeersFile:
    path = _peers_path(root)
    if not path.is_file():
        return PeersFile()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PeersFile(**data)


def write_peers(root: Path, peers_file: PeersFile) -> Path:
    path = _peers_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = peers_file.model_dump(mode="json")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def add_peer(root: Path, peer: Peer) -> None:
    peers = read_peers(root)
    if any(p.name == peer.name for p in peers.peers):
        raise PeerError(f"peer {peer.name!r} already registered; remove it first")
    peers.peers.append(peer)
    write_peers(root, peers)


def remove_peer(root: Path, name: str) -> bool:
    peers = read_peers(root)
    before = len(peers.peers)
    peers.peers = [p for p in peers.peers if p.name != name]
    if len(peers.peers) == before:
        return False
    write_peers(root, peers)
    return True


def list_peers(root: Path) -> list[Peer]:
    return read_peers(root).peers


def _peers_path(root: Path) -> Path:
    return root / "peers.yml"
