"""Pull a skill from a peer: fetch manifest / fetch one skill / verify / land."""

from __future__ import annotations

import base64
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.identity import canonical_payload
from skill_forge.models import RunEvent, Skill, Source, SourcesFile
from skill_forge.storage import filesystem as storage

from .peers import Peer, read_peers, write_peers


class PullError(Exception):
    """Federation pull errors (peer unreachable, signature mismatch, etc.)."""


def fetch_manifest(peer: Peer) -> list[dict[str, Any]]:
    """Hit federation/manifest on the peer; return the list of skill summaries."""
    response = _rpc(peer, "federation/manifest", {})
    skills = response.get("skills", [])
    if not isinstance(skills, list):
        raise PullError(f"peer {peer.name!r} returned non-list manifest")
    return skills


def fetch_peer_info(peer: Peer) -> tuple[str, str]:
    """Hit federation/peer-info; return (instance_id, public_key_pem)."""
    response = _rpc(peer, "federation/peer-info", {})
    iid = response.get("instance_id")
    pem = response.get("public_key_pem")
    if not isinstance(iid, str) or not isinstance(pem, str):
        raise PullError(f"peer {peer.name!r} returned malformed peer-info")
    return iid, pem


def pull_skill(root: Path, peer: Peer, slug: str) -> Skill:
    """Pull one skill by slug from a peer, verify its signature, land it as draft."""
    # 1. Ensure we have the peer's pubkey (cached or fresh).
    peer = _ensure_peer_identity(root, peer)
    public_key = _load_pubkey(peer.public_key_pem)
    assert peer.instance_id is not None  # _ensure_peer_identity guarantees this

    # 2. Fetch the skill itself.
    response = _rpc(peer, "federation/skill", {"slug": slug})
    raw = response.get("skill")
    if not isinstance(raw, dict):
        raise PullError(f"peer {peer.name!r} returned malformed skill payload")
    try:
        skill = Skill.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        raise PullError(f"peer's skill {slug!r} failed model validation: {exc}") from exc

    # 3. Verify the skill is actually from this peer.
    if skill.origin is None or not skill.origin.startswith(f"{peer.instance_id}:"):
        raise PullError(
            f"peer {peer.name!r} served a skill with origin {skill.origin!r}, "
            f"which doesn't match its instance_id {peer.instance_id!r}"
        )
    if skill.signature is None:
        raise PullError(f"peer's skill {slug!r} has no signature")
    payload = canonical_payload(skill)
    try:
        public_key.verify(base64.b64decode(skill.signature), payload)
    except InvalidSignature as exc:
        raise PullError(f"peer's skill {slug!r} signature does not verify with peer's key") from exc

    # 4. Land it as a draft. Preserve foreign origin + signature verbatim.
    landed_slug = storage.free_slug(root, skill.name)
    if landed_slug != skill.name:
        # Renaming the slug would invalidate the foreign signature. Refuse;
        # caller can manually rename the local copy.
        raise PullError(
            f"local slug {skill.name!r} already exists; rename or remove it before pulling"
        )
    storage.write_skill(root, skill, draft=True, overwrite=False)

    # 5. Record provenance. Source.id uses sha256[:6] of the signed payload.
    payload_sha = _payload_sha256(payload)
    src = Source(
        id=f"src-{payload_sha[:6]}",
        url=f"federation:{peer.name}:{peer.url}",
        license="unknown",
        fetched_at=datetime.now(UTC),
        sha256=payload_sha,
        contribution=f"pulled from peer {peer.name!r} ({peer.instance_id})",
    )
    storage.write_sources(
        root,
        skill.name,
        SourcesFile(slug=skill.name, sources=[src]),
    )

    # 6. Audit.
    append_run_event(
        root,
        RunEvent(
            run_id=next_run_id(root),
            event="imported",
            timestamp=datetime.now(UTC),
            skill_slug=skill.name,
            metadata={"source": f"federation:{peer.name}"},
        ),
    )
    return skill


# --- internals ----------------------------------------------------------------


def _rpc(peer: Peer, method: str, params: dict[str, Any]) -> dict[str, Any]:
    """One JSON-RPC call against the peer's /mcp endpoint."""
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if peer.token:
        headers["Authorization"] = f"Bearer {peer.token}"
    url = peer.url.rstrip("/") + "/mcp"
    req = urllib.request.Request(url, data=payload, method="POST", headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            body = resp.read().decode("utf-8")
    except Exception as exc:
        raise PullError(f"peer {peer.name!r} unreachable at {url}: {exc}") from exc
    try:
        envelope = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PullError(f"peer {peer.name!r} returned non-JSON: {exc}") from exc
    if "error" in envelope:
        err = envelope["error"]
        raise PullError(f"peer {peer.name!r} returned error: {err.get('message', err)}")
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise PullError(f"peer {peer.name!r} returned malformed result")
    return result


def _ensure_peer_identity(root: Path, peer: Peer) -> Peer:
    """Fetch + cache peer's instance_id and public key on first contact."""
    if peer.instance_id and peer.public_key_pem:
        return peer
    iid, pem = fetch_peer_info(peer)
    peer = peer.model_copy(update={"instance_id": iid, "public_key_pem": pem})
    # Persist back into peers.yml — but only if the peer still exists there.
    # If the user removed it between pull start and now, don't silently
    # re-add a peer the user explicitly removed.
    peers = read_peers(root)
    if not any(p.name == peer.name for p in peers.peers):
        raise PullError(f"peer {peer.name!r} was removed while pulling; re-add it and retry")
    peers.peers = [peer if p.name == peer.name else p for p in peers.peers]
    write_peers(root, peers)
    return peer


def _load_pubkey(pem: str | None) -> Ed25519PublicKey:
    if not pem:
        raise PullError("peer has no cached public key")
    key = serialization.load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise PullError("peer public key is not Ed25519")
    return key


def _payload_sha256(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()
