"""Abstract LLMProvider + the DistilledDraft model providers must return."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, field_validator

from skill_forge.models import SLUG_RE, JudgeFinding, JudgeScore, Skill


class DistilledDraft(BaseModel):
    """Structured output that `extract_draft` must return."""

    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    body: str

    @field_validator("name")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.fullmatch(v):
            raise ValueError(
                f"DistilledDraft.name must be kebab-case slug [a-z0-9][a-z0-9-]*, got {v!r}"
            )
        return v

    @field_validator("body")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("DistilledDraft.body must be non-empty")
        return v


class LLMProviderError(Exception):
    """Wraps any provider-side failure (network, rate limit, invalid response).

    Subclasses chain the original exception via `raise ... from`.
    """


class LLMProvider(ABC):
    """Minimal interface — providers turn raw source text into a draft, and judge."""

    @abstractmethod
    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
        """Return a draft for the given source. Raises LLMProviderError on failure."""

    @abstractmethod
    def judge(
        self, skill: Skill, *, weights: dict[str, float]
    ) -> tuple[JudgeScore, list[JudgeFinding]]:
        """Score `skill` against the rubric. Findings explain lost points.

        The provider returns per-axis floats and findings; total is computed
        client-side from `weights` to avoid model/weight drift, so the returned
        `JudgeScore.total` always matches the weighted sum exactly.
        """

    @abstractmethod
    def refine(
        self,
        skill: Skill,
        *,
        findings: list[JudgeFinding],
        hint: str | None = None,
        extra_source: str | None = None,
    ) -> str:
        """Return a refined markdown body addressing the supplied findings.

        Only the body is produced — slug/description/sources/version are
        managed by the caller. `hint` is a user-supplied free-form steer,
        `extra_source` is paraphrasable raw text (HTML or markdown) to fold
        in.
        """
