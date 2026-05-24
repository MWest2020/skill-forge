"""Instance identity: Ed25519 keypair, instance ID, sign/verify for skills.

Spec: openspec/changes/add-instance-identity/specs/identity/spec.md
"""

from __future__ import annotations

import base64
import hashlib
import json
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

if TYPE_CHECKING:
    from skill_forge.models import Skill

_PRIV_MODE = 0o600
_PUB_MODE = 0o644
_DIR_MODE = 0o700


class IdentityError(Exception):
    """Base class for identity-module errors."""


class IdentityKeyPermissionError(IdentityError):
    """Private key file has incorrect filesystem permissions."""


class SignatureMismatchError(IdentityError):
    """A skill's signature does not match its canonical payload."""


@dataclass(frozen=True)
class Identity:
    instance_id: str
    public_key: Ed25519PublicKey
    private_key: Ed25519PrivateKey
    home: Path

    def sign(self, payload: bytes) -> str:
        return base64.b64encode(self.private_key.sign(payload)).decode("ascii")

    def verify(self, payload: bytes, signature_b64: str) -> bool:
        try:
            self.public_key.verify(base64.b64decode(signature_b64), payload)
        except InvalidSignature:
            return False
        return True


def get_or_create(home: Path) -> Identity:
    """Load identity from `{home}/identity/`, generating on first call."""
    identity_dir = home / "identity"
    priv_path = identity_dir / "private_key.pem"
    if priv_path.is_file():
        return _load(identity_dir)
    return _generate(identity_dir, Ed25519PrivateKey.generate())


def from_seed(home: Path, seed: bytes) -> Identity:
    """Deterministic identity from a 32-byte seed (test helper)."""
    if len(seed) != 32:
        raise ValueError(f"seed must be 32 bytes, got {len(seed)}")
    identity_dir = home / "identity"
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    return _generate(identity_dir, private_key, overwrite=True)


def canonical_payload(skill: Skill) -> bytes:
    """Stable byte representation of the skill's signed surface."""
    body_sha256 = hashlib.sha256(skill.body.encode("utf-8")).hexdigest()
    payload = skill.model_dump(mode="json", exclude={"signature", "body"})
    payload["body_sha256"] = body_sha256
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_skill(skill: Skill, identity: Identity) -> str:
    return identity.sign(canonical_payload(skill))


def verify_skill(skill: Skill, identity: Identity) -> bool:
    if skill.signature is None:
        return False
    return identity.verify(canonical_payload(skill), skill.signature)


# --- internals ----------------------------------------------------------------


def _generate(
    identity_dir: Path, private_key: Ed25519PrivateKey, *, overwrite: bool = False
) -> Identity:
    identity_dir.mkdir(parents=True, exist_ok=True)
    identity_dir.chmod(_DIR_MODE)

    public_key = private_key.public_key()

    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    instance_id = _derive_instance_id(public_key)

    priv_path = identity_dir / "private_key.pem"
    pub_path = identity_dir / "public_key.pem"
    id_path = identity_dir / "instance_id.txt"
    if not overwrite and priv_path.exists():
        return _load(identity_dir)
    priv_path.write_bytes(priv_pem)
    priv_path.chmod(_PRIV_MODE)
    pub_path.write_bytes(pub_pem)
    pub_path.chmod(_PUB_MODE)
    id_path.write_text(instance_id, encoding="utf-8")

    return Identity(
        instance_id=instance_id,
        public_key=public_key,
        private_key=private_key,
        home=identity_dir,
    )


def _load(identity_dir: Path) -> Identity:
    priv_path = identity_dir / "private_key.pem"
    _enforce_permissions(priv_path)
    private_key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise IdentityError(f"{priv_path} is not an Ed25519 private key")
    public_key = private_key.public_key()
    instance_id = _derive_instance_id(public_key)
    return Identity(
        instance_id=instance_id,
        public_key=public_key,
        private_key=private_key,
        home=identity_dir,
    )


def _enforce_permissions(priv_path: Path) -> None:
    mode = stat.S_IMODE(priv_path.stat().st_mode)
    if mode != _PRIV_MODE:
        raise IdentityKeyPermissionError(
            f"{priv_path} mode is {mode:o}, expected {_PRIV_MODE:o}. "
            f"Run `chmod 600 {priv_path}` after verifying nobody else accessed it."
        )


def _derive_instance_id(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return f"forge-{hashlib.sha256(raw).hexdigest()[:8]}"
