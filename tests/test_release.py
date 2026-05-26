"""Tests for forge release — change #11 add-release."""

from __future__ import annotations

import tarfile
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.identity import Identity, from_seed
from skill_forge.models import ReleaseManifest, Skill, SourceRef
from skill_forge.release import (
    ReleaseError,
    create_release,
    list_releases,
    verify_release,
)
from skill_forge.storage import filesystem as fs

runner = CliRunner()


def _identity(tmp_path: Path, seed_byte: int = 1) -> Identity:
    return from_seed(tmp_path / "id", bytes([seed_byte] * 32))


def _skill(name: str) -> Skill:
    return Skill(
        name=name,
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 26),
        body="# Body of " + name + "\n",
    )


def _seed_promoted(root: Path, slug: str, identity: Identity) -> None:
    """Land a signed, promoted skill at root/skills/<slug>/SKILL.md."""
    fs.write_skill(root, _skill(slug), draft=False, identity=identity)


# --- create_release ----------------------------------------------------------


def test_create_release_default_includes_all_promoted(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    _seed_promoted(tmp_path, "beta", identity)

    summary = create_release(tmp_path, "v1", identity=identity)
    assert summary.skill_count == 2
    assert summary.manifest_path.is_file()
    assert summary.tarball_path.is_file()

    manifest = ReleaseManifest(**yaml.safe_load(summary.manifest_path.read_text()))
    assert [s.slug for s in manifest.skills] == ["alpha", "beta"]  # deterministic order
    assert manifest.identity_fingerprint == identity.instance_id
    assert manifest.signature is not None


def test_create_release_with_include_subset(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    _seed_promoted(tmp_path, "beta", identity)
    _seed_promoted(tmp_path, "gamma", identity)

    summary = create_release(tmp_path, "v1", identity=identity, include=["alpha", "gamma"])
    assert summary.skill_count == 2
    manifest = ReleaseManifest(**yaml.safe_load(summary.manifest_path.read_text()))
    assert [s.slug for s in manifest.skills] == ["alpha", "gamma"]


def test_create_release_include_unknown_slug_rejects(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    with pytest.raises(ReleaseError, match="not promoted"):
        create_release(tmp_path, "v1", identity=identity, include=["alpha", "nope"])


def test_create_release_empty_instance_rejects(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    with pytest.raises(ReleaseError, match="no skills to release"):
        create_release(tmp_path, "v1", identity=identity)


def test_create_release_bad_version_rejects(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    with pytest.raises(ReleaseError, match="slug-shaped"):
        create_release(tmp_path, "Version 1!", identity=identity)


def test_create_release_duplicate_version_rejects(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    create_release(tmp_path, "v1", identity=identity)
    with pytest.raises(ReleaseError, match="already exists"):
        create_release(tmp_path, "v1", identity=identity)


def test_create_release_force_overwrites(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    create_release(tmp_path, "v1", identity=identity)
    _seed_promoted(tmp_path, "beta", identity)
    summary = create_release(tmp_path, "v1", identity=identity, force=True)
    assert summary.skill_count == 2


def test_release_tarball_uses_nested_layout(tmp_path: Path) -> None:
    """A consumer should be able to tar xzf into a fresh instance root."""
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    summary = create_release(tmp_path, "v1", identity=identity)
    with tarfile.open(summary.tarball_path, "r:gz") as tf:
        names = tf.getnames()
    assert "skills/alpha/SKILL.md" in names


def test_release_skips_drafts(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    fs.write_skill(tmp_path, _skill("draftee"), draft=True, identity=identity)
    summary = create_release(tmp_path, "v1", identity=identity)
    assert summary.skill_count == 1
    manifest = ReleaseManifest(**yaml.safe_load(summary.manifest_path.read_text()))
    assert [s.slug for s in manifest.skills] == ["alpha"]


# --- verify_release ----------------------------------------------------------


def test_verify_release_happy_path(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    _seed_promoted(tmp_path, "beta", identity)
    create_release(tmp_path, "v1", identity=identity)
    verify_release(tmp_path, "v1", identity=identity)  # no exception


def test_verify_release_detects_tampered_tarball(tmp_path: Path) -> None:
    """Flip a byte in the tarball; verify must catch the file-level sha mismatch."""
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    summary = create_release(tmp_path, "v1", identity=identity)
    # Corrupt: append a byte to the tarball (changes its sha256).
    with summary.tarball_path.open("ab") as f:
        f.write(b"\x00")
    with pytest.raises(ReleaseError, match="tarball sha256 mismatch"):
        verify_release(tmp_path, "v1", identity=identity)


def test_verify_release_detects_tampered_manifest(tmp_path: Path) -> None:
    """Edit the manifest skills list; signature verification must fail."""
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    summary = create_release(tmp_path, "v1", identity=identity)
    data = yaml.safe_load(summary.manifest_path.read_text())
    data["skills"][0]["sha256"] = "0" * 64
    summary.manifest_path.write_text(yaml.safe_dump(data))
    with pytest.raises(ReleaseError, match="signature INVALID"):
        verify_release(tmp_path, "v1", identity=identity)


def test_verify_release_wrong_identity_rejects(tmp_path: Path) -> None:
    identity_a = _identity(tmp_path, seed_byte=1)
    identity_b = from_seed(tmp_path / "id2", bytes([2] * 32))
    _seed_promoted(tmp_path, "alpha", identity_a)
    create_release(tmp_path, "v1", identity=identity_a)
    with pytest.raises(ReleaseError, match="signed by"):
        verify_release(tmp_path, "v1", identity=identity_b)


def test_verify_release_missing_manifest(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    with pytest.raises(ReleaseError, match="no manifest at"):
        verify_release(tmp_path, "v1", identity=identity)


def test_verify_release_rejects_renamed_release(tmp_path: Path) -> None:
    """Regression: file-swap of v1.{yml,tar.gz} → v2.{yml,tar.gz} must fail verify.

    Without the version-binding check, an attacker who can write to
    releases/ could rename v1's files to v2's names. The inner manifest
    still says version=v1; the signature is still valid for v1; the
    tarball still matches its sha — but the user asked for v2.
    """
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    create_release(tmp_path, "v1", identity=identity)
    releases_dir = tmp_path / "releases"
    (releases_dir / "v1.yml").rename(releases_dir / "v2.yml")
    (releases_dir / "v1.tar.gz").rename(releases_dir / "v2.tar.gz")
    with pytest.raises(ReleaseError, match="claims version 'v1', expected 'v2'"):
        verify_release(tmp_path, "v2", identity=identity)


def test_verify_release_rejects_manifest_with_missing_tarball_entry(
    tmp_path: Path,
) -> None:
    """Regression: manifest must not list skills absent from the tarball.

    Without the manifest→tarball coverage check, verify would iterate
    tarball members and silently miss skills the manifest claims but
    the tarball doesn't contain. Tarball sha catches this for
    after-the-fact tampering, but not for builder bugs or for
    test-time hand-edits.
    """
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    summary = create_release(tmp_path, "v1", identity=identity)
    # Hand-craft a tampered manifest: extra ghost skill, re-sign with
    # the same identity (simulating a builder bug, not an attacker).
    from skill_forge.release import _canonical_manifest_payload

    data = yaml.safe_load(summary.manifest_path.read_text())
    data["skills"].append(
        {"slug": "ghost", "sha256": "0" * 64, "signature": None, "origin": None}
    )
    manifest = ReleaseManifest(**{k: v for k, v in data.items() if k != "signature"})
    data["signature"] = identity.sign(_canonical_manifest_payload(manifest))
    summary.manifest_path.write_text(yaml.safe_dump(data))
    # This version is fully self-consistent (sig + tarball sha both match).
    # The ONLY problem is the ghost skill, which the new coverage check must catch.
    with pytest.raises(ReleaseError, match="not present in tarball.*ghost"):
        verify_release(tmp_path, "v1", identity=identity)


# --- list_releases -----------------------------------------------------------


def test_list_releases_empty(tmp_path: Path) -> None:
    assert list_releases(tmp_path) == []


def test_list_releases_orders_by_created(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)
    create_release(tmp_path, "v1", identity=identity)
    _seed_promoted(tmp_path, "beta", identity)
    create_release(tmp_path, "v2", identity=identity)
    manifests = list_releases(tmp_path)
    assert [m.version for m in manifests] == ["v1", "v2"]


# --- CLI ---------------------------------------------------------------------


def test_cli_release_create_and_verify(tmp_path: Path) -> None:
    identity = _identity(tmp_path)
    _seed_promoted(tmp_path, "alpha", identity)

    create = runner.invoke(
        app,
        [
            "release", "create", "v1",
            "--root", str(tmp_path),
            "--home", str(tmp_path / "id"),
        ],
    )
    assert create.exit_code == 0, create.output
    assert "released v1 (1 skills)" in create.output

    verify = runner.invoke(
        app,
        ["release", "verify", "v1", "--root", str(tmp_path), "--home", str(tmp_path / "id")],
    )
    assert verify.exit_code == 0, verify.output
    assert "verified v1" in verify.output


def test_cli_release_list_empty(tmp_path: Path) -> None:
    result = runner.invoke(app, ["release", "list", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "no releases yet" in result.output


def test_cli_release_create_no_skills(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "release", "create", "v1",
            "--root", str(tmp_path),
            "--home", str(tmp_path / "id"),
        ],
    )
    assert result.exit_code == 1
    assert "no skills to release" in (result.stderr or result.output)
