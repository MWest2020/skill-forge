"""Tests for skill_forge.models — change #1."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from skill_forge.models import (
    JUDGE_AXES,
    TIERS,
    CalibrationRecord,
    GoldAttestation,
    JudgeProvenance,
    JudgeRun,
    JudgeScore,
    Run,
    RunEvent,
    RunSummary,
    Skill,
    Source,
    SourceRef,
    SourcesFile,
    derive_tier,
)

_HEX64 = "a" * 64


def _judged(total: float, rubric_version: str = "2") -> RunEvent:
    axes = {a: total for a in JUDGE_AXES}
    prov = JudgeProvenance(
        provider="x", model_id="x:y", rubric_version=rubric_version, prompt_sha256=_HEX64,
        temperature=0.0, runs=1, raw_axes=[axes], median_axes=axes,
    )
    return RunEvent(
        run_id="run-2026-06-17-001", event="judged",
        timestamp=datetime(2026, 6, 17, tzinfo=UTC), skill_slug="demo",
        scores=JudgeScore(**axes, total=total), judge_provenance=prov,
    )


def _calibration(passed: bool = True, rubric_version: str = "2") -> CalibrationRecord:
    return CalibrationRecord(
        rubric_version=rubric_version, model_id="x:y", gold_set_sha256=_HEX64,
        results=[], agreement=1.0, passed=passed,
        calibrated_at=datetime(2026, 6, 17, 12, tzinfo=UTC),
    )


def test_derive_tier_gold_beats_all() -> None:
    assert derive_tier(_judged(0.9), gold_valid=True, calibration=None,
                       total_min=0.75, axis_min=0.50) == "gold"


def test_derive_tier_untiered_when_unjudged() -> None:
    assert derive_tier(None, gold_valid=False, calibration=None,
                       total_min=0.75, axis_min=0.50) == "untiered"


def test_derive_tier_bronze_when_judged_no_calibration() -> None:
    assert derive_tier(_judged(0.9), gold_valid=False, calibration=None,
                       total_min=0.75, axis_min=0.50) == "bronze"


def test_derive_tier_silver_on_passing_same_version_calibration() -> None:
    assert derive_tier(_judged(0.9), gold_valid=False, calibration=_calibration(),
                       total_min=0.75, axis_min=0.50) == "silver"


def test_derive_tier_no_silver_on_rubric_mismatch() -> None:
    # calibration is for rubric v1; the judged run is v2 → no silver
    assert derive_tier(_judged(0.9, "2"), gold_valid=False,
                       calibration=_calibration(rubric_version="1"),
                       total_min=0.75, axis_min=0.50) == "bronze"


def test_derive_tier_no_silver_on_failed_calibration() -> None:
    assert derive_tier(_judged(0.9), gold_valid=False, calibration=_calibration(passed=False),
                       total_min=0.75, axis_min=0.50) == "bronze"


def test_derive_tier_untiered_below_threshold() -> None:
    assert derive_tier(_judged(0.40), gold_valid=False, calibration=None,
                       total_min=0.75, axis_min=0.50) == "untiered"


def test_tiers_constant() -> None:
    assert TIERS == ("untiered", "bronze", "silver", "gold")


def test_gold_attestation_rejects_bad_signature() -> None:
    with pytest.raises(ValidationError):
        GoldAttestation(
            skill_origin="forge-abcd1234:demo:1", version=1,
            gold_public_key="-----BEGIN PUBLIC KEY-----\nx\n-----END PUBLIC KEY-----",
            signature="not-base64!!", attested_at=datetime(2026, 6, 17, tzinfo=UTC),
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


def test_skill_tags_default_empty() -> None:
    assert _skill().tags == []


def test_skill_tags_deduped_and_sorted() -> None:
    skill = _skill(tags=["web", "security", "web"])
    assert skill.tags == ["security", "web"]


def test_skill_tags_reject_non_slug() -> None:
    with pytest.raises(ValidationError):
        _skill(tags=["Security"])  # uppercase is not slug-shaped


def _axes(v: float = 0.8) -> dict[str, float]:
    return {axis: v for axis in JUDGE_AXES}


def test_judge_run_valid() -> None:
    run = JudgeRun(axes=_axes(), findings=[], model_id="anthropic:x", prompt_sha256=_HEX64)
    assert run.axes["clarity"] == 0.8


def test_judge_run_rejects_out_of_range_axis() -> None:
    with pytest.raises(ValidationError):
        JudgeRun(axes=_axes(1.5), model_id="x", prompt_sha256=_HEX64)


def test_judge_run_rejects_unknown_axis_key() -> None:
    with pytest.raises(ValidationError):
        JudgeRun(axes={"bogus": 0.5}, model_id="x", prompt_sha256=_HEX64)


def test_judge_run_rejects_bad_prompt_hash() -> None:
    with pytest.raises(ValidationError):
        JudgeRun(axes=_axes(), model_id="x", prompt_sha256="not-a-hash")


def test_judge_provenance_valid_and_runs_floor() -> None:
    prov = JudgeProvenance(
        provider="anthropic", model_id="anthropic:x", rubric_version="1",
        prompt_sha256=_HEX64, temperature=0.0, runs=3,
        raw_axes=[_axes(0.7), _axes(0.8), _axes(0.9)], median_axes=_axes(0.8),
    )
    assert prov.runs == 3
    with pytest.raises(ValidationError):
        JudgeProvenance(
            provider="anthropic", model_id="x", rubric_version="1",
            prompt_sha256=_HEX64, temperature=0.0, runs=0,
            raw_axes=[], median_axes=_axes(),
        )


def test_run_event_carries_judge_provenance() -> None:
    prov = JudgeProvenance(
        provider="claude_code", model_id="claude_code:claude", rubric_version="1",
        prompt_sha256=_HEX64, temperature=0.0, runs=1,
        raw_axes=[_axes()], median_axes=_axes(),
    )
    ev = RunEvent(
        run_id="run-2026-06-15-001", event="judged",
        timestamp=datetime(2026, 6, 15, tzinfo=UTC), skill_slug="demo",
        judge_provenance=prov,
    )
    assert RunEvent.model_validate(ev.model_dump(mode="json")).judge_provenance == prov


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
    return {axis: 1 / len(JUDGE_AXES) for axis in JUDGE_AXES}


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
