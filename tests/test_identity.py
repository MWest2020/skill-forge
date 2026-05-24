"""Tests for skill_forge.identity — change add-instance-identity."""

from __future__ import annotations

import os
import stat
from datetime import date
from pathlib import Path

import pytest

from skill_forge.identity import (
    Identity,
    IdentityKeyPermissionError,
    canonical_payload,
    from_seed,
    get_or_create,
    sign_skill,
    verify_skill,
)
from skill_forge.models import Skill, SourceRef

SEED_A = b"\x01" * 32
SEED_B = b"\x02" * 32


def _identity(tmp_path: Path, seed: bytes = SEED_A) -> Identity:
    return from_seed(tmp_path, seed)


def _skill(name: str = "demo-skill", origin: str | None = None) -> Skill:
    return Skill(
        name=name,
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="# Body\n",
        origin=origin,
    )


# --- get_or_create + persistence ---------------------------------------------


def test_get_or_create_generates_on_first_call(tmp_path: Path) -> None:
    identity = get_or_create(tmp_path)
    assert identity.instance_id.startswith("forge-")
    assert len(identity.instance_id) == len("forge-") + 8
    assert (tmp_path / "identity" / "private_key.pem").is_file()
    assert (tmp_path / "identity" / "public_key.pem").is_file()
    assert (tmp_path / "identity" / "instance_id.txt").read_text() == identity.instance_id


def test_get_or_create_loads_on_second_call(tmp_path: Path) -> None:
    first = get_or_create(tmp_path)
    second = get_or_create(tmp_path)
    assert first.instance_id == second.instance_id


def test_private_key_has_0600_permissions(tmp_path: Path) -> None:
    get_or_create(tmp_path)
    priv = tmp_path / "identity" / "private_key.pem"
    assert stat.S_IMODE(priv.stat().st_mode) == 0o600


def test_get_or_create_rejects_loose_key_permissions(tmp_path: Path) -> None:
    get_or_create(tmp_path)
    priv = tmp_path / "identity" / "private_key.pem"
    os.chmod(priv, 0o644)
    with pytest.raises(IdentityKeyPermissionError, match="644"):
        get_or_create(tmp_path)


# --- from_seed (deterministic) -----------------------------------------------


def test_from_seed_is_deterministic(tmp_path: Path) -> None:
    a = from_seed(tmp_path / "a", SEED_A)
    b = from_seed(tmp_path / "b", SEED_A)
    assert a.instance_id == b.instance_id


def test_different_seeds_yield_different_ids(tmp_path: Path) -> None:
    a = from_seed(tmp_path / "a", SEED_A)
    b = from_seed(tmp_path / "b", SEED_B)
    assert a.instance_id != b.instance_id


def test_from_seed_rejects_wrong_length(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        from_seed(tmp_path, b"too short")


# --- sign / verify ------------------------------------------------------------


def test_sign_verify_round_trip(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    skill = _skill()
    sig = sign_skill(skill, identity)
    signed = skill.model_copy(update={"signature": sig})
    assert verify_skill(signed, identity) is True


def test_verify_returns_false_when_signature_missing(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    assert verify_skill(_skill(), identity) is False


def test_verify_detects_tampered_body(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    skill = _skill()
    sig = sign_skill(skill, identity)
    tampered = skill.model_copy(update={"body": "# Tampered\n", "signature": sig})
    assert verify_skill(tampered, identity) is False


def test_verify_detects_tampered_origin(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    skill = _skill(origin=f"{identity.instance_id}:demo-skill:1")
    sig = sign_skill(skill, identity)
    tampered = skill.model_copy(
        update={"origin": "forge-deadbeef:demo-skill:1", "signature": sig}
    )
    assert verify_skill(tampered, identity) is False


def test_verify_rejects_signature_from_different_identity(tmp_path: Path) -> None:
    id_a = _identity(tmp_path / "a", SEED_A)
    id_b = _identity(tmp_path / "b", SEED_B)
    skill = _skill()
    sig_a = sign_skill(skill, id_a)
    signed = skill.model_copy(update={"signature": sig_a})
    assert verify_skill(signed, id_b) is False


# --- canonical_payload --------------------------------------------------------


def test_canonical_payload_excludes_signature_and_body(tmp_path: Path) -> None:
    skill = _skill()
    payload_unsigned = canonical_payload(skill)
    skill_signed = skill.model_copy(update={"signature": "ZmFrZQ=="})
    payload_signed = canonical_payload(skill_signed)
    # Adding a signature must NOT change the canonical payload.
    assert payload_unsigned == payload_signed


def test_canonical_payload_is_stable_across_runs(tmp_path: Path) -> None:
    skill = _skill()
    assert canonical_payload(skill) == canonical_payload(skill)
