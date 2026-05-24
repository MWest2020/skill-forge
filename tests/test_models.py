"""Tests for skill_forge.models — change #1."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from skill_forge.models import (
    JUDGE_AXES,
    JudgeScore,
    Run,
    RunSummary,
    Skill,
    Source,
    SourceRef,
    SourcesFile,
)


def _skill(**overrides: object) -> Skill:
    base: dict[str, object] = {
        "name": "demo-skill",
        "description": "Use when X.",
        "version": 1,
        "sources": [SourceRef(id="src-abc123")],
        "created": date(2026, 5, 24),
        "body": "# Body\n",
    }
    base.update(overrides)
    return Skill(**base)  # type: ignore[arg-type]


def _source() -> Source:
    return Source(
        id="src-abc123",
        url="https://example.com/post",
        license="Apache-2.0",
        fetched_at=datetime(2026, 5, 24, 14, 30, tzinfo=UTC),
        sha256="a" * 64,
        contribution="patch sequence",
    )


# --- Skill --------------------------------------------------------------------


def test_skill_model_requires_name() -> None:
    with pytest.raises(ValidationError):
        Skill()  # type: ignore[call-arg]


def test_skill_round_trip() -> None:
    s = _skill()
    assert Skill(**s.model_dump()) == s


def test_skill_rejects_bad_slug() -> None:
    with pytest.raises(ValidationError):
        _skill(name="Bad Name")


def test_skill_rejects_uppercase_slug() -> None:
    with pytest.raises(ValidationError):
        _skill(name="DemoSkill")


def test_skill_requires_at_least_one_source() -> None:
    with pytest.raises(ValidationError):
        _skill(sources=[])


def test_skill_judge_score_range() -> None:
    _skill(judge_score=0.5)
    with pytest.raises(ValidationError):
        _skill(judge_score=1.5)


def test_skill_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Skill(  # type: ignore[call-arg]
            name="x",
            description="d",
            version=1,
            sources=[SourceRef(id="src-abc123")],
            created=date(2026, 5, 24),
            body="",
            surprise="boom",
        )


def test_skill_version_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _skill(version=0)


# --- Source -------------------------------------------------------------------


def test_source_round_trip() -> None:
    s = _source()
    assert Source(**s.model_dump()) == s


def test_source_rejects_bad_id() -> None:
    with pytest.raises(ValidationError):
        Source(
            id="srcabc123",
            url="https://x",
            license="MIT",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            sha256="b" * 64,
            contribution="c",
        )


def test_source_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        Source(
            id="src-abc123",
            url="https://x",
            license="MIT",
            fetched_at=datetime(2026, 1, 1),  # naive
            sha256="b" * 64,
            contribution="c",
        )


def test_source_rejects_bad_sha256() -> None:
    with pytest.raises(ValidationError):
        Source(
            id="src-abc123",
            url="https://x",
            license="MIT",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            sha256="short",
            contribution="c",
        )


# --- JudgeScore ---------------------------------------------------------------


def _axes(value: float = 0.8) -> dict[str, float]:
    return {axis: value for axis in JUDGE_AXES}


def _weights() -> dict[str, float]:
    return {
        "schema_compliance": 0.20,
        "clarity": 0.20,
        "actionability": 0.25,
        "gap_coverage": 0.20,
        "provenance_quality": 0.15,
    }


def test_judge_score_axis_range() -> None:
    with pytest.raises(ValidationError):
        JudgeScore(**_axes(value=1.1), total=0.5)


def test_judge_score_total_matches_weights() -> None:
    JudgeScore.model_validate(
        {**_axes(0.8), "total": 0.8},
        context={"weights": _weights()},
    )


def test_judge_score_total_mismatch_rejected_with_context() -> None:
    with pytest.raises(ValidationError):
        JudgeScore.model_validate(
            {**_axes(0.8), "total": 0.5},
            context={"weights": _weights()},
        )


def test_judge_score_total_unchecked_without_context() -> None:
    # Round-trip should not require weights.
    JudgeScore(**_axes(0.8), total=0.5)


# --- Run ----------------------------------------------------------------------


def test_run_id_format() -> None:
    Run(
        run_id="run-2026-05-24-001",
        started_at=datetime(2026, 5, 24, tzinfo=UTC),
        skill_slug="demo-skill",
        promoted=False,
    )
    with pytest.raises(ValidationError):
        Run(
            run_id="run-2026-5-24-1",
            started_at=datetime(2026, 5, 24, tzinfo=UTC),
            skill_slug="demo-skill",
            promoted=False,
        )


def test_run_summary_round_trip() -> None:
    rs = RunSummary(run_id="run-2026-05-24-001", judge_score=0.87, promoted=True)
    assert RunSummary(**rs.model_dump()) == rs


# --- SourcesFile --------------------------------------------------------------


def test_sources_file_round_trip() -> None:
    sf = SourcesFile(slug="demo-skill", sources=[_source()], runs=[])
    assert SourcesFile(**sf.model_dump()) == sf


def test_sources_file_rejects_bad_slug() -> None:
    with pytest.raises(ValidationError):
        SourcesFile(slug="Bad Slug", sources=[_source()])


# --- body normalization (regression for sign/read round-trip bug) -------------


def test_body_validator_normalizes_leading_and_trailing_newlines() -> None:
    # Body of just newlines collapses to empty (matches read-back behavior).
    s = _skill(body="\n\n\n")
    assert s.body == ""

    # Leading newlines stripped, trailing newline ensured.
    s = _skill(body="\n\nactual content")
    assert s.body == "actual content\n"

    # Already-normalized body unchanged.
    s = _skill(body="content\n")
    assert s.body == "content\n"
