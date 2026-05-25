"""Ollama implementation of LLMProvider.

Local LLM via Ollama's HTTP API. Useful for the judge stage where
latency/cost matter and Claude-quality structured output is overkill.

Spec: openspec/changes/add-ollama-provider/proposal.md
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import ValidationError

from skill_forge.models import JudgeFinding, JudgeScore, Skill

from ._judge import (
    build_judge_score,
    parse_findings,
    serialize_skill_for_judge,
    serialize_skill_for_refine,
)
from .base import DistilledDraft, LLMProvider, LLMProviderError
from .claude_code import _extract_json_object  # reuse tolerant parser

MAX_SOURCE_CHARS = 180_000


class OllamaProvider(LLMProvider):
    """Posts to /api/chat with `format: json` for structured output."""

    def __init__(
        self,
        *,
        host: str | None = None,
        model: str = "llama3.1",
        timeout: float = 120.0,
    ) -> None:
        self._host = (host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        self._model = model
        self._timeout = timeout

    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
        if len(source_text) > MAX_SOURCE_CHARS:
            source_text = source_text[:MAX_SOURCE_CHARS]
        data = self._chat(
            system=_EXTRACT_SYSTEM,
            user=f"Source URL: {source_url}\n\n---\n\n{source_text}",
        )
        try:
            return DistilledDraft.model_validate(data)
        except ValidationError as exc:
            raise LLMProviderError(f"ollama extract output failed validation: {exc}") from exc

    def judge(
        self, skill: Skill, *, weights: dict[str, float]
    ) -> tuple[JudgeScore, list[JudgeFinding]]:
        data = self._chat(system=_JUDGE_SYSTEM, user=serialize_skill_for_judge(skill))
        return _parse_judge_payload(data, weights)

    def refine(
        self,
        skill: Skill,
        *,
        findings: list[JudgeFinding],
        hint: str | None = None,
        extra_source: str | None = None,
    ) -> str:
        data = self._chat(
            system=_REFINE_SYSTEM,
            user=serialize_skill_for_refine(skill, findings, hint, extra_source),
        )
        body = data.get("body") if isinstance(data, dict) else None
        if not isinstance(body, str) or not body.strip():
            raise LLMProviderError("ollama refine output missing non-empty `body`")
        return body

    def _chat(self, *, system: str, user: str) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self._host}/api/chat",
                json={
                    "model": self._model,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"ollama at {self._host} unreachable: {exc}. "
                f"Is `ollama serve` running?"
            ) from exc
        if response.status_code >= 400:
            raise LLMProviderError(
                f"ollama returned HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            envelope = response.json()
        except ValueError as exc:
            raise LLMProviderError(f"ollama returned non-JSON envelope: {exc}") from exc
        content = (envelope.get("message") or {}).get("content")
        if not isinstance(content, str):
            raise LLMProviderError("ollama response missing message.content")
        parsed = _extract_json_object(content)
        if parsed is None:
            raise LLMProviderError(
                f"ollama did not return parseable JSON; first 200 chars: {content.strip()[:200]!r}"
            )
        return parsed


def _parse_judge_payload(
    data: dict[str, Any], weights: dict[str, float]
) -> tuple[JudgeScore, list[JudgeFinding]]:
    findings_raw = data.get("findings", [])
    if not isinstance(findings_raw, list):
        raise LLMProviderError("ollama judge `findings` must be a list")
    try:
        axes = {axis: float(data[axis]) for axis in (
            "schema_compliance", "clarity", "actionability",
            "gap_coverage", "provenance_quality",
        )}
        findings = parse_findings(findings_raw)
        score = build_judge_score(axes, weights)
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise LLMProviderError(f"ollama judge payload failed validation: {exc}") from exc
    return score, findings


_EXTRACT_SYSTEM = """\
You distill a source page into a reusable SKILL.md draft.

Output ONLY a single JSON object with keys: name, description, body.

- name: short kebab-case slug, matching ^[a-z0-9][a-z0-9-]*$
- description: one paragraph starting with "Use this skill when ..."
- body: markdown body (no frontmatter). Required sections in order:
    ## When to use
    ## Procedure
    ## Failure modes
"""


_JUDGE_SYSTEM = """\
You judge a SKILL.md against the skill-forge rubric. Output ONLY a
single JSON object with these keys:

  schema_compliance, clarity, actionability, gap_coverage, provenance_quality: each 0.0-1.0
  findings: list of {axis, observation, severity} objects (severity in info|warning|blocker)

Do NOT compute a `total` — the caller weights the axes.
"""


_REFINE_SYSTEM = """\
You refine a SKILL.md body to address judge findings. Output ONLY a
single JSON object: {"body": "<refined markdown>"}.

- Keep the existing section structure (When to use / Procedure / Failure modes).
- Address each finding precisely. Don't globally rewrite.
- If the input includes "additional source material", paraphrase from it.
  Never quote verbatim.
- If a "user hint" is present, treat it as priority over generic improvements.
- Preserve specific commands, flags, file paths verbatim.
"""
