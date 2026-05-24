"""Abstract LLMProvider + the DistilledDraft model providers must return."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, field_validator

from skill_forge.models import SLUG_RE


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
    """Minimal interface — providers turn raw source text into a draft."""

    @abstractmethod
    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
        """Return a draft for the given source. Raises LLMProviderError on failure."""
