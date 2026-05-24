"""Tests for skill_forge.storage.filesystem — change #1."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from skill_forge.identity import SignatureMismatchError, from_seed
from skill_forge.models import Skill, Source, SourceRef, SourcesFile
from skill_forge.storage import filesystem as fs

_SEED = b"\x07" * 32


def _skill(name: str = "demo-skill", judge_score: float | None = 0.87) -> Skill:
    return Skill(
        name=name,
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        judge_score=judge_score,
        created=date(2026, 5, 24),
        body="# Body\n\n## Section\nContent.\n",
    )


def _sources(slug: str = "demo-skill") -> SourcesFile:
    return SourcesFile(
        slug=slug,
        sources=[
            Source(
                id="src-abc123",
                url="https://example.com/post",
                license="Apache-2.0",
                fetched_at=datetime(2026, 5, 24, 14, 30, tzinfo=UTC),
                sha256="a" * 64,
                contribution="patch sequence",
            )
        ],
    )


# --- list_skills --------------------------------------------------------------


def test_list_skills_empty(tmp_path: Path) -> None:
    assert fs.list_skills(tmp_path) == []


def test_list_skills_mixed_live_and_drafts(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("apple"), draft=False)
    fs.write_skill(tmp_path, _skill("zebra"), draft=False)
    fs.write_skill(tmp_path, _skill("banana", judge_score=None), draft=True)

    entries = fs.list_skills(tmp_path)
    assert [(e.slug, e.draft) for e in entries] == [
        ("apple", False),
        ("zebra", False),
        ("banana", True),
    ]
    assert entries[2].judge_score is None
    assert entries[0].judge_score == 0.87


def test_list_skills_skips_unparseable(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("good"), draft=False)
    bad_dir = tmp_path / "skills" / "broken"
    bad_dir.mkdir(parents=True)
    (bad_dir / "SKILL.md").write_text("no frontmatter here\n")

    entries = fs.list_skills(tmp_path)
    assert [e.slug for e in entries] == ["good"]


# --- read_skill ---------------------------------------------------------------


def test_read_skill_round_trip(tmp_path: Path) -> None:
    original = _skill()
    fs.write_skill(tmp_path, original, draft=False)
    loaded = fs.read_skill(tmp_path, original.name)
    assert loaded == original


def test_read_skill_prefers_live_over_draft(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("dual", judge_score=0.9), draft=False)
    fs.write_skill(tmp_path, _skill("dual", judge_score=0.4), draft=True)
    loaded = fs.read_skill(tmp_path, "dual")
    assert loaded.judge_score == 0.9


def test_read_skill_falls_back_to_draft(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("only-draft", judge_score=0.4), draft=True)
    assert fs.read_skill(tmp_path, "only-draft").judge_score == 0.4


def test_read_skill_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as exc:
        fs.read_skill(tmp_path, "nope")
    assert "nope" in str(exc.value)


def test_read_skill_bad_frontmatter(tmp_path: Path) -> None:
    slug_dir = tmp_path / "skills" / "broken"
    slug_dir.mkdir(parents=True)
    (slug_dir / "SKILL.md").write_text("no delimiter line\n")
    with pytest.raises(ValueError):
        fs.read_skill(tmp_path, "broken")


def test_read_skill_unclosed_frontmatter(tmp_path: Path) -> None:
    slug_dir = tmp_path / "skills" / "unclosed"
    slug_dir.mkdir(parents=True)
    (slug_dir / "SKILL.md").write_text("---\nname: x\n")
    with pytest.raises(ValueError):
        fs.read_skill(tmp_path, "unclosed")


# --- write_skill --------------------------------------------------------------


def test_write_skill_creates_dir(tmp_path: Path) -> None:
    target = fs.write_skill(tmp_path, _skill(), draft=False)
    assert target == tmp_path / "skills" / "demo-skill" / "SKILL.md"
    assert target.is_file()


def test_write_skill_draft_path(tmp_path: Path) -> None:
    target = fs.write_skill(tmp_path, _skill(), draft=True)
    assert target == tmp_path / "skills" / "_draft" / "demo-skill" / "SKILL.md"


def test_write_skill_refuses_overwrite_by_default(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(), draft=False)
    with pytest.raises(FileExistsError):
        fs.write_skill(tmp_path, _skill(), draft=False)


def test_write_skill_overwrite_explicit(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(judge_score=0.5), draft=False)
    fs.write_skill(tmp_path, _skill(judge_score=0.9), draft=False, overwrite=True)
    assert fs.read_skill(tmp_path, "demo-skill").judge_score == 0.9


# --- read/write sources -------------------------------------------------------


def test_sources_round_trip(tmp_path: Path) -> None:
    original = _sources()
    fs.write_sources(tmp_path, original.slug, original)
    loaded = fs.read_sources(tmp_path, original.slug)
    assert loaded == original


def test_read_sources_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        fs.read_sources(tmp_path, "nope")


def test_write_sources_refuses_overwrite(tmp_path: Path) -> None:
    fs.write_sources(tmp_path, "demo-skill", _sources())
    with pytest.raises(FileExistsError):
        fs.write_sources(tmp_path, "demo-skill", _sources())


# --- runs_path ----------------------------------------------------------------


def test_runs_path_shape(tmp_path: Path) -> None:
    p = fs.runs_path(tmp_path, "run-2026-05-24-001")
    assert p == tmp_path / "runs" / "run-2026-05-24-001.jsonl"


# --- identity hooks -----------------------------------------------------------


def test_write_skill_stamps_origin_and_signature_when_identity_supplied(
    tmp_path: Path,
) -> None:
    identity = from_seed(tmp_path / "id", _SEED)
    fs.write_skill(tmp_path, _skill(), draft=True, identity=identity)
    loaded = fs.read_skill(tmp_path, "demo-skill", identity=identity)
    assert loaded.origin == f"{identity.instance_id}:demo-skill:1"
    assert loaded.signature is not None


def test_write_skill_without_identity_leaves_fields_none(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill(), draft=True)
    loaded = fs.read_skill(tmp_path, "demo-skill")
    assert loaded.origin is None
    assert loaded.signature is None


def test_read_skill_rejects_tampered_body(tmp_path: Path) -> None:
    identity = from_seed(tmp_path / "id", _SEED)
    fs.write_skill(tmp_path, _skill(), draft=True, identity=identity)
    path = tmp_path / "skills" / "_draft" / "demo-skill" / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    with pytest.raises(SignatureMismatchError):
        fs.read_skill(tmp_path, "demo-skill", identity=identity)


def test_read_skill_rejects_foreign_origin_when_identity_supplied(
    tmp_path: Path,
) -> None:
    identity_a = from_seed(tmp_path / "a", _SEED)
    identity_b = from_seed(tmp_path / "b", b"\x08" * 32)
    fs.write_skill(tmp_path, _skill(), draft=True, identity=identity_a)
    with pytest.raises(SignatureMismatchError, match="foreign origin"):
        fs.read_skill(tmp_path, "demo-skill", identity=identity_b)


def test_read_skill_loads_foreign_origin_without_identity(tmp_path: Path) -> None:
    """No identity supplied => no verification, foreign origin loads silently."""
    identity_a = from_seed(tmp_path / "a", _SEED)
    fs.write_skill(tmp_path, _skill(), draft=True, identity=identity_a)
    loaded = fs.read_skill(tmp_path, "demo-skill")  # no identity
    assert loaded.origin is not None
    assert loaded.origin.startswith(identity_a.instance_id)


def test_read_skill_rejects_stripped_signature(tmp_path: Path) -> None:
    """Removing the signature field defeats verification if read_skill isn't strict."""
    identity = from_seed(tmp_path / "id", _SEED)
    fs.write_skill(tmp_path, _skill(), draft=True, identity=identity)
    path = tmp_path / "skills" / "_draft" / "demo-skill" / "SKILL.md"
    # Strip the signature line from frontmatter
    new = (
        "\n".join(
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("signature:")
        )
        + "\n"
    )
    path.write_text(new, encoding="utf-8")
    with pytest.raises(SignatureMismatchError, match="unsigned"):
        fs.read_skill(tmp_path, "demo-skill", identity=identity)


def test_read_skill_unsigned_loads_without_identity(tmp_path: Path) -> None:
    """Pre-change-#1 skills (no origin/signature) load when no identity is supplied."""
    fs.write_skill(tmp_path, _skill(), draft=True)  # no identity
    loaded = fs.read_skill(tmp_path, "demo-skill")
    assert loaded.origin is None
    assert loaded.signature is None


def test_write_skill_preserves_existing_signature(tmp_path: Path) -> None:
    identity = from_seed(tmp_path / "id", _SEED)
    pre_stamped = _skill().model_copy(
        update={
            "origin": f"{identity.instance_id}:demo-skill:1",
            "signature": "Y2FjaGVk",  # base64("cached") — placeholder
        }
    )
    # Make it through validation by using a real signature; sign it ourselves.
    from skill_forge.identity import sign_skill

    real_sig = sign_skill(
        _skill().model_copy(update={"origin": f"{identity.instance_id}:demo-skill:1"}),
        identity,
    )
    pre_stamped = pre_stamped.model_copy(update={"signature": real_sig})
    fs.write_skill(tmp_path, pre_stamped, draft=True, identity=identity)
    loaded = fs.read_skill(tmp_path, "demo-skill", identity=identity)
    assert loaded.signature == real_sig
