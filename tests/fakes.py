"""Shared test fakes — override only what each test needs."""

from __future__ import annotations

from skill_forge.models import JudgeFinding, JudgeRun, Skill
from skill_forge.providers.base import DistilledDraft, LLMProvider


class FakeProvider(LLMProvider):
    """Default-no-op LLMProvider. Override methods in subclasses as needed."""

    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
        raise NotImplementedError("FakeProvider.extract_draft not overridden")

    def judge(self, skill: Skill, *, temperature: float = 0.0) -> JudgeRun:
        raise NotImplementedError("FakeProvider.judge not overridden")

    def refine(
        self,
        skill: Skill,
        *,
        findings: list[JudgeFinding],
        hint: str | None = None,
        extra_source: str | None = None,
    ) -> str:
        raise NotImplementedError("FakeProvider.refine not overridden")
