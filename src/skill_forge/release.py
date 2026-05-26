"""Bundle skills into a signed, version-pinned release archive.

Spec: openspec/changes/add-release/proposal.md

A release freezes N skills + their sources.yml into a tarball, alongside
a signed manifest. The point: anyone downstream can pin to "v1" and re-
verify the exact bytes they received, even if the live instance keeps
churning.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.identity import Identity
from skill_forge.models import (
    SLUG_RE,
    ReleaseManifest,
    ReleaseSkillEntry,
    RunEvent,
)
from skill_forge.storage import filesystem as storage


class ReleaseError(Exception):
    """Anything that prevents creating, listing, or verifying a release."""


@dataclass(frozen=True)
class ReleaseSummary:
    version: str
    created: datetime
    identity_fingerprint: str
    skill_count: int
    manifest_path: Path
    tarball_path: Path


def create_release(
    root: Path,
    version: str,
    *,
    identity: Identity,
    include: Iterable[str] | None = None,
    message: str | None = None,
    force: bool = False,
) -> ReleaseSummary:
    """Snapshot N promoted skills into releases/<version>.{yml,tar.gz}.

    `include=None` means "every promoted skill"; otherwise just the named
    slugs (raises if any don't exist or are draft).
    """
    if not SLUG_RE.fullmatch(version):
        raise ReleaseError(
            f"version {version!r} must be slug-shaped (a-z0-9, hyphens). "
            "Try `v1`, `v2026-05-26`, or `1-0-0`."
        )
    releases_dir = root / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = releases_dir / f"{version}.yml"
    tarball_path = releases_dir / f"{version}.tar.gz"
    if manifest_path.exists() and not force:
        raise ReleaseError(
            f"release {version!r} already exists at {manifest_path}. "
            "Pass --force to overwrite, or pick a new version."
        )

    slugs = _resolve_slugs(root, include)
    if not slugs:
        raise ReleaseError(
            "no skills to release. Promote a draft first (or pass --include with explicit slugs)."
        )

    # Build the tarball first so the manifest can record its sha256.
    skill_entries = _build_tarball(root, tarball_path, slugs, identity=identity)
    tarball_sha = _file_sha256(tarball_path)

    manifest = ReleaseManifest(
        version=version,
        created=datetime.now(UTC),
        identity_fingerprint=identity.instance_id,
        skills=skill_entries,
        tarball_sha256=tarball_sha,
        signature=None,
    )
    manifest = manifest.model_copy(update={"signature": _sign_manifest(manifest, identity)})
    _write_manifest(manifest_path, manifest)

    append_run_event(
        root,
        RunEvent(
            run_id=next_run_id(root),
            event="released",
            timestamp=manifest.created,
            skill_slug=slugs[0],  # at least one — required field
            metadata={
                "version": version,
                "skill_count": str(len(skill_entries)),
                "tarball_sha256": tarball_sha,
                "message": message or "",
            },
        ),
    )
    return ReleaseSummary(
        version=version,
        created=manifest.created,
        identity_fingerprint=identity.instance_id,
        skill_count=len(skill_entries),
        manifest_path=manifest_path,
        tarball_path=tarball_path,
    )


def list_releases(root: Path) -> list[ReleaseManifest]:
    """Return every release manifest, oldest first."""
    releases_dir = root / "releases"
    if not releases_dir.is_dir():
        return []
    manifests: list[ReleaseManifest] = []
    for path in sorted(releases_dir.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        manifests.append(ReleaseManifest(**data))
    manifests.sort(key=lambda m: m.created)
    return manifests


def verify_release(
    root: Path,
    version: str,
    *,
    identity: Identity,
) -> None:
    """Re-hash the tarball + every skill inside and check the manifest signature.

    Raises ReleaseError on any mismatch — clear enough that the caller can
    surface "file X was tampered with" to the user.
    """
    releases_dir = root / "releases"
    manifest_path = releases_dir / f"{version}.yml"
    tarball_path = releases_dir / f"{version}.tar.gz"
    if not manifest_path.is_file():
        raise ReleaseError(f"no manifest at {manifest_path}")
    if not tarball_path.is_file():
        raise ReleaseError(f"no tarball at {tarball_path}")

    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    manifest = ReleaseManifest(**data)

    # Bind requested version to manifest contents. Without this, an attacker
    # who can swap files in releases/ (rename v1.yml→v2.yml + v1.tar.gz→
    # v2.tar.gz) would produce a "verified v2" success against v1's bytes —
    # both the inner sha and signature still match each other, just not the
    # version the user typed. The signature covers `version` in the payload,
    # so the check is cheap and bullet-proof.
    if manifest.version != version:
        raise ReleaseError(
            f"manifest at {manifest_path} claims version "
            f"{manifest.version!r}, expected {version!r}. "
            "Refusing to verify under a different name (file substitution?)."
        )

    if manifest.identity_fingerprint != identity.instance_id:
        raise ReleaseError(
            f"manifest signed by {manifest.identity_fingerprint!r}, "
            f"current identity is {identity.instance_id!r}. Can't verify."
        )

    # Signature first — if the manifest itself was tampered with, nothing
    # else we check is trustworthy.
    if manifest.signature is None:
        raise ReleaseError(f"manifest at {manifest_path} has no signature")
    if not identity.verify(_canonical_manifest_payload(manifest), manifest.signature):
        raise ReleaseError(
            f"manifest signature INVALID for {version!r}. Tampering detected, or wrong identity."
        )

    # Now the tarball as a whole.
    actual_tarball_sha = _file_sha256(tarball_path)
    if actual_tarball_sha != manifest.tarball_sha256:
        raise ReleaseError(
            f"tarball sha256 mismatch for {version!r}: "
            f"manifest says {manifest.tarball_sha256}, actual {actual_tarball_sha}"
        )

    # And each skill inside. We check both directions: every member must
    # appear in the manifest (no surprise files), and every manifest entry
    # must appear in the tarball (no silently-missing skills). The tarball-
    # level sha256 above blocks tampering, but this catches builder bugs
    # and makes the verify-passes-iff-manifest-matches-bytes contract
    # explicit rather than implicit.
    expected_by_slug = {entry.slug: entry for entry in manifest.skills}
    seen: set[str] = set()
    with tarfile.open(tarball_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile() or not member.name.endswith("/SKILL.md"):
                continue
            slug = member.name.split("/")[-2]
            entry = expected_by_slug.get(slug)
            if entry is None:
                raise ReleaseError(f"tarball contains unexpected skill {slug!r} (not in manifest)")
            fileobj = tf.extractfile(member)
            if fileobj is None:
                raise ReleaseError(f"could not read {member.name} from tarball")
            actual = hashlib.sha256(fileobj.read()).hexdigest()
            if actual != entry.sha256:
                raise ReleaseError(
                    f"SKILL.md sha256 mismatch for {slug!r}: "
                    f"manifest says {entry.sha256}, actual {actual}"
                )
            seen.add(slug)
    missing = set(expected_by_slug) - seen
    if missing:
        raise ReleaseError(
            f"manifest lists skills not present in tarball: {sorted(missing)!r}"
        )


# --- internals ----------------------------------------------------------------


def _resolve_slugs(root: Path, include: Iterable[str] | None) -> list[str]:
    """Return the (sorted, deduped) slug list to include in the release."""
    if include is None:
        return sorted(e.slug for e in storage.list_skills(root) if not e.draft)
    requested = sorted(set(include))
    available = {e.slug for e in storage.list_skills(root) if not e.draft}
    missing = [s for s in requested if s not in available]
    if missing:
        raise ReleaseError(
            f"refusing to release: not promoted (or not found): {missing!r}. "
            "Promote them first (`forge promote <slug>`) or drop them from --include."
        )
    return requested


def _build_tarball(
    root: Path, tarball_path: Path, slugs: list[str], *, identity: Identity
) -> list[ReleaseSkillEntry]:
    """Write the gzipped tarball; return per-skill entries for the manifest."""
    entries: list[ReleaseSkillEntry] = []
    with tarfile.open(tarball_path, "w:gz") as tf:
        for slug in slugs:
            skill = storage.read_skill(root, slug, identity=identity)
            skill_path = root / "skills" / slug / "SKILL.md"
            sources_path = root / "sources" / f"{slug}.yml"
            skill_bytes = skill_path.read_bytes()
            entries.append(
                ReleaseSkillEntry(
                    slug=slug,
                    sha256=hashlib.sha256(skill_bytes).hexdigest(),
                    signature=skill.signature,
                    origin=skill.origin,
                )
            )
            tf.add(skill_path, arcname=f"skills/{slug}/SKILL.md")
            if sources_path.is_file():
                tf.add(sources_path, arcname=f"sources/{slug}.yml")
    return entries


def _canonical_manifest_payload(manifest: ReleaseManifest) -> bytes:
    """Stable bytes to sign — order-independent, signature-excluded."""
    payload = manifest.model_dump(mode="json", exclude={"signature"})
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_manifest(manifest: ReleaseManifest, identity: Identity) -> str:
    return identity.sign(_canonical_manifest_payload(manifest))


def _write_manifest(path: Path, manifest: ReleaseManifest) -> None:
    data = manifest.model_dump(mode="json")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
