"""Core domain models: Skill, Source, JudgeScore, Run + helpers.

Specs: openspec/changes/add-core-models-and-storage/specs/models/spec.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VISIBILITY_VALUES = ("private", "unlisted", "public")
SOURCE_ID_RE = re.compile(r"^src-[a-f0-9]{6}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
RUN_ID_RE = re.compile(r"^run-\d{4}-\d{2}-\d{2}-\d{3}$")
ORIGIN_RE = re.compile(r"^forge-[a-f0-9]{8}:[a-z0-9][a-z0-9-]*:\d+$")
SIGNATURE_B64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")

JUDGE_AXES = (
    "schema_compliance",
    "clarity",
    "actionability",
    "gap_coverage",
    "provenance_quality",
)

_STRICT = ConfigDict(extra="forbid")


def _check_unit(value: float, field: str) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} must be in [0.0, 1.0], got {value}")
    return value


class SourceRef(BaseModel):
    """Lightweight pointer to a Source — full record lives in sources/{slug}.yml."""

    model_config = _STRICT
    id: str

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not SOURCE_ID_RE.fullmatch(v):
            raise ValueError(f"SourceRef.id must match 'src-XXXXXX' (6 hex), got {v!r}")
        return v


class Skill(BaseModel):
    """A SKILL.md document: frontmatter fields + the markdown body."""

    model_config = _STRICT
    name: str
    description: str
    version: int = Field(ge=1)
    sources: list[SourceRef]
    judge_score: float | None = None
    created: date
    body: str
    origin: str | None = None
    signature: str | None = None
    visibility: str = "private"

    @field_validator("name")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.fullmatch(v):
            raise ValueError(f"Skill.name must be slug-shaped [a-z0-9][a-z0-9-]*, got {v!r}")
        return v

    @field_validator("sources")
    @classmethod
    def _nonempty(cls, v: list[SourceRef]) -> list[SourceRef]:
        if not v:
            raise ValueError("Skill.sources must contain at least one SourceRef")
        return v

    @field_validator("judge_score")
    @classmethod
    def _score_range(cls, v: float | None) -> float | None:
        return None if v is None else _check_unit(v, "Skill.judge_score")

    @field_validator("origin")
    @classmethod
    def _origin_shape(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not ORIGIN_RE.fullmatch(v):
            raise ValueError(f"Skill.origin must match '<instance_id>:<slug>:<version>', got {v!r}")
        return v

    @field_validator("signature")
    @classmethod
    def _signature_shape(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not SIGNATURE_B64_RE.fullmatch(v):
            raise ValueError("Skill.signature must be base64-encoded ASCII")
        return v

    @field_validator("visibility")
    @classmethod
    def _visibility_allowed(cls, v: str) -> str:
        if v not in VISIBILITY_VALUES:
            raise ValueError(
                f"Skill.visibility must be one of {VISIBILITY_VALUES}, got {v!r}"
            )
        return v

    @field_validator("body")
    @classmethod
    def _body_normalize(cls, v: str) -> str:
        # Why: storage's _split_frontmatter does lstrip("\n") on read and
        # _render_skill appends "\n" on write. Signatures cover body_sha256,
        # so the body we sign must equal the body we read back. Normalize
        # both ends here (the one place that touches body validation).
        v = v.lstrip("\n")
        if v and not v.endswith("\n"):
            v += "\n"
        return v


class Source(BaseModel):
    """Full provenance record for one source used during extraction."""

    model_config = _STRICT
    id: str
    url: str
    license: str
    fetched_at: datetime
    sha256: str
    contribution: str

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not SOURCE_ID_RE.fullmatch(v):
            raise ValueError(f"Source.id must match 'src-XXXXXX' (6 hex), got {v!r}")
        return v

    @field_validator("sha256")
    @classmethod
    def _sha_shape(cls, v: str) -> str:
        if not SHA256_RE.fullmatch(v):
            raise ValueError("Source.sha256 must be 64 lowercase hex chars")
        return v

    @field_validator("fetched_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("Source.fetched_at must be timezone-aware")
        return v


class JudgeScore(BaseModel):
    """Per-axis judge scores plus a weighted total.

    When a `weights` dict is supplied via Pydantic context, the stored
    `total` is verified to match the weighted sum (tolerance 1e-9). Without
    context (e.g., during round-trip from dict), the consistency check is
    skipped — callers that care should pass context explicitly.
    """

    model_config = _STRICT
    schema_compliance: float
    clarity: float
    actionability: float
    gap_coverage: float
    provenance_quality: float
    total: float

    @field_validator(*JUDGE_AXES, "total")
    @classmethod
    def _axis_range(cls, v: float, info: ValidationInfo) -> float:
        return _check_unit(v, f"JudgeScore.{info.field_name}")

    @model_validator(mode="after")
    def _total_matches_weights(self, info: ValidationInfo) -> JudgeScore:
        ctx = info.context or {}
        weights = ctx.get("weights") if isinstance(ctx, dict) else None
        if not weights:
            return self
        expected = sum(weights[axis] * getattr(self, axis) for axis in JUDGE_AXES)
        if abs(expected - self.total) > 1e-9:
            raise ValueError(
                f"JudgeScore.total ({self.total}) does not match weighted sum ({expected})"
            )
        return self


class RunSummary(BaseModel):
    """Compact run record stored inside sources/{slug}.yml."""

    model_config = _STRICT
    run_id: str
    judge_score: float
    promoted: bool

    @field_validator("run_id")
    @classmethod
    def _shape(cls, v: str) -> str:
        if not RUN_ID_RE.fullmatch(v):
            raise ValueError(f"run_id must match 'run-YYYY-MM-DD-NNN', got {v!r}")
        return v

    @field_validator("judge_score")
    @classmethod
    def _range(cls, v: float) -> float:
        return _check_unit(v, "RunSummary.judge_score")


class Run(BaseModel):
    """Full audit record for one pipeline run (used by change #3 onwards)."""

    model_config = _STRICT
    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    topic: str | None = None
    skill_slug: str
    scores: JudgeScore | None = None
    promoted: bool

    @field_validator("run_id")
    @classmethod
    def _shape(cls, v: str) -> str:
        if not RUN_ID_RE.fullmatch(v):
            raise ValueError(f"Run.run_id must match 'run-YYYY-MM-DD-NNN', got {v!r}")
        return v

    @field_validator("started_at", "finished_at")
    @classmethod
    def _tz_aware(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("Run timestamps must be timezone-aware")
        return v

    @field_validator("skill_slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.fullmatch(v):
            raise ValueError(f"Run.skill_slug must be slug-shaped, got {v!r}")
        return v


JUDGE_SEVERITIES = ("info", "warning", "blocker")

ITERATION_KINDS = ("imported", "extracted", "refined", "accepted")
ITERATION_STATUSES = ("current", "superseded", "pending", "rejected")
ITERATION_FILE_RE = re.compile(
    r"^v(\d+)-(imported|extracted|refined|accepted)-(\d{4}-\d{2}-\d{2})\.md$"
)


class Iteration(BaseModel):
    """One snapshot of a skill's body, with its place in the lineage."""

    model_config = _STRICT
    version: int = Field(ge=1)
    kind: str  # imported | extracted | refined | accepted
    created: date
    judge_score: float | None = None
    status: str  # current | superseded | pending | rejected
    reject_reason: str | None = None

    @field_validator("kind")
    @classmethod
    def _kind_allowed(cls, v: str) -> str:
        if v not in ITERATION_KINDS:
            raise ValueError(f"Iteration.kind must be one of {ITERATION_KINDS}, got {v!r}")
        return v

    @field_validator("status")
    @classmethod
    def _status_allowed(cls, v: str) -> str:
        if v not in ITERATION_STATUSES:
            raise ValueError(
                f"Iteration.status must be one of {ITERATION_STATUSES}, got {v!r}"
            )
        return v

    @field_validator("judge_score")
    @classmethod
    def _score_range(cls, v: float | None) -> float | None:
        return None if v is None else _check_unit(v, "Iteration.judge_score")

    @model_validator(mode="after")
    def _reject_reason_required(self) -> Iteration:
        if self.status == "rejected" and not (self.reject_reason and self.reject_reason.strip()):
            raise ValueError("Iteration.reject_reason is required when status='rejected'")
        if self.status != "rejected" and self.reject_reason is not None:
            raise ValueError("Iteration.reject_reason must be None unless status='rejected'")
        return self


class Lineage(BaseModel):
    """Per-skill iteration index. Lives at `skills/{slug}/lineage.yml`."""

    model_config = _STRICT
    slug: str
    current_version: int = Field(ge=1)
    iterations: list[Iteration]

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.fullmatch(v):
            raise ValueError(f"Lineage.slug must be slug-shaped, got {v!r}")
        return v

    @field_validator("iterations")
    @classmethod
    def _nonempty(cls, v: list[Iteration]) -> list[Iteration]:
        if not v:
            raise ValueError("Lineage.iterations must contain at least one entry")
        return v

    @model_validator(mode="after")
    def _coherent(self) -> Lineage:
        versions = [it.version for it in self.iterations]
        if versions != sorted(set(versions)):
            raise ValueError(
                "Lineage.iterations versions must be strictly monotonic starting at 1"
            )
        current = [it for it in self.iterations if it.status == "current"]
        if len(current) != 1:
            raise ValueError(
                f"Lineage must have exactly one 'current' iteration, got {len(current)}"
            )
        if current[0].version != self.current_version:
            raise ValueError(
                f"Lineage.current_version ({self.current_version}) does not match "
                f"the version of the 'current' iteration ({current[0].version})"
            )
        return self


class JudgeFinding(BaseModel):
    """One per-axis observation produced by the judge (especially for lost points)."""

    model_config = _STRICT
    axis: str
    observation: str
    severity: str

    @field_validator("axis")
    @classmethod
    def _axis_allowed(cls, v: str) -> str:
        if v not in JUDGE_AXES:
            raise ValueError(f"JudgeFinding.axis must be one of {JUDGE_AXES}, got {v!r}")
        return v

    @field_validator("severity")
    @classmethod
    def _severity_allowed(cls, v: str) -> str:
        if v not in JUDGE_SEVERITIES:
            raise ValueError(f"JudgeFinding.severity must be one of {JUDGE_SEVERITIES}, got {v!r}")
        return v


class RunEvent(BaseModel):
    """One line in `runs/{run_id}.jsonl`."""

    model_config = _STRICT
    run_id: str
    event: str  # imported | judged | promoted | demoted
    timestamp: datetime
    skill_slug: str
    scores: JudgeScore | None = None
    findings: list[JudgeFinding] = Field(default_factory=list)
    promoted: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("run_id")
    @classmethod
    def _run_id_shape(cls, v: str) -> str:
        if not RUN_ID_RE.fullmatch(v):
            raise ValueError(f"RunEvent.run_id must match 'run-YYYY-MM-DD-NNN', got {v!r}")
        return v

    @field_validator("event")
    @classmethod
    def _event_allowed(cls, v: str) -> str:
        allowed = {"imported", "judged", "promoted", "demoted", "refined"}
        if v not in allowed:
            raise ValueError(f"RunEvent.event must be one of {sorted(allowed)}, got {v!r}")
        return v

    @field_validator("skill_slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.fullmatch(v):
            raise ValueError(f"RunEvent.skill_slug must be slug-shaped, got {v!r}")
        return v

    @field_validator("timestamp")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("RunEvent.timestamp must be timezone-aware")
        return v


class SourcesFile(BaseModel):
    """The shape of `sources/{slug}.yml` on disk."""

    model_config = _STRICT
    slug: str
    sources: list[Source]
    runs: list[RunSummary] = []

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.fullmatch(v):
            raise ValueError(f"SourcesFile.slug must be slug-shaped, got {v!r}")
        return v


@dataclass(frozen=True)
class SkillEntry:
    """Listing row returned by storage.list_skills."""

    slug: str
    draft: bool
    judge_score: float | None


def model_to_jsonable(model: BaseModel) -> dict[str, Any]:
    """Round-trip helper: dump to JSON-compatible dict (dates as ISO strings)."""
    return model.model_dump(mode="json")
