"""Anthropic implementation of LLMProvider.

Spec: openspec/changes/add-extraction-pipeline/specs/llm-provider/spec.md
"""

from __future__ import annotations

import re
from typing import Any, cast

import anthropic
from anthropic.types import (
    MessageParam,
    TextBlockParam,
    ToolChoiceToolParam,
    ToolParam,
)
from pydantic import ValidationError

from skill_forge.models import JudgeFinding, JudgeScore, Skill

from ._judge import (
    build_judge_score,
    parse_findings,
    serialize_skill_for_judge,
    serialize_skill_for_refine,
)
from ._prompts import (
    EMIT_DRAFT_TOOL,
    EMIT_REFINEMENT_TOOL,
    EXTRACTION_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    REFINEMENT_SYSTEM_PROMPT,
    SCORE_SKILL_TOOL,
)
from .base import DistilledDraft, LLMProvider, LLMProviderError

MAX_SOURCE_CHARS = 180_000
_API_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_-]+")


class AnthropicProvider(LLMProvider):
    """Calls the Claude API once per `extract_draft`.

    The extraction system prompt carries `cache_control: ephemeral`. The prompt
    is small today (well below the cacheable minimum on Opus 4.7), so the marker
    won't fire yet — it's there so caching kicks in automatically if the prompt
    grows or we move to a model with a lower threshold (Sonnet 4.6: 2048 tokens).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-opus-4-7",
        max_tokens: int = 4096,
    ) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key} if api_key else {}
        self._client = anthropic.Anthropic(**kwargs)
        self._model = model
        self._max_tokens = max_tokens

    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
        if len(source_text) > MAX_SOURCE_CHARS:
            source_text = source_text[:MAX_SOURCE_CHARS]
        user_content = f"Source URL: {source_url}\n\n---\n\n{source_text}"

        system_block: TextBlockParam = {
            "type": "text",
            "text": EXTRACTION_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
        tool = cast(ToolParam, EMIT_DRAFT_TOOL)
        tool_choice: ToolChoiceToolParam = {"type": "tool", "name": "emit_draft"}
        user_msg: MessageParam = {"role": "user", "content": user_content}

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=[system_block],
                tools=[tool],
                tool_choice=tool_choice,
                messages=[user_msg],
            )
        except anthropic.APIError as exc:
            raise LLMProviderError(_redact(str(exc))) from exc

        for block in response.content:
            if block.type == "tool_use" and block.name == "emit_draft":
                try:
                    return DistilledDraft.model_validate(block.input)
                except ValidationError as exc:
                    raise LLMProviderError(f"emit_draft input failed validation: {exc}") from exc

        raise LLMProviderError("model did not emit an emit_draft tool call")

    def judge(
        self, skill: Skill, *, weights: dict[str, float]
    ) -> tuple[JudgeScore, list[JudgeFinding]]:
        score_tool = cast(ToolParam, SCORE_SKILL_TOOL)
        tool_choice: ToolChoiceToolParam = {"type": "tool", "name": "score_skill"}
        system_block: TextBlockParam = {
            "type": "text",
            "text": JUDGE_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
        user_msg: MessageParam = {
            "role": "user",
            "content": serialize_skill_for_judge(skill),
        }

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=[system_block],
                tools=[score_tool],
                tool_choice=tool_choice,
                messages=[user_msg],
            )
        except anthropic.APIError as exc:
            raise LLMProviderError(_redact(str(exc))) from exc

        for block in response.content:
            if block.type == "tool_use" and block.name == "score_skill":
                return _parse_score_payload(block.input, weights)
        raise LLMProviderError("model did not emit a score_skill tool call")


    def refine(
        self,
        skill: Skill,
        *,
        findings: list[JudgeFinding],
        hint: str | None = None,
        extra_source: str | None = None,
    ) -> str:
        tool = cast(ToolParam, EMIT_REFINEMENT_TOOL)
        tool_choice: ToolChoiceToolParam = {"type": "tool", "name": "emit_refinement"}
        system_block: TextBlockParam = {
            "type": "text",
            "text": REFINEMENT_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
        user_msg: MessageParam = {
            "role": "user",
            "content": serialize_skill_for_refine(skill, findings, hint, extra_source),
        }
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=[system_block],
                tools=[tool],
                tool_choice=tool_choice,
                messages=[user_msg],
            )
        except anthropic.APIError as exc:
            raise LLMProviderError(_redact(str(exc))) from exc
        for block in response.content:
            if block.type == "tool_use" and block.name == "emit_refinement":
                payload = block.input
                if not isinstance(payload, dict) or "body" not in payload:
                    raise LLMProviderError("emit_refinement payload missing 'body'")
                body = payload["body"]
                if not isinstance(body, str) or not body.strip():
                    raise LLMProviderError("emit_refinement.body must be a non-empty string")
                return body
        raise LLMProviderError("model did not emit an emit_refinement tool call")


def _parse_score_payload(
    payload: object, weights: dict[str, float]
) -> tuple[JudgeScore, list[JudgeFinding]]:
    if not isinstance(payload, dict):
        raise LLMProviderError(f"score_skill payload was not a dict: {type(payload).__name__}")
    findings_raw = payload.get("findings", [])
    if not isinstance(findings_raw, list):
        raise LLMProviderError("score_skill findings must be a list")
    try:
        axes = {
            axis: float(payload[axis])
            for axis in (
                "schema_compliance",
                "clarity",
                "actionability",
                "gap_coverage",
                "provenance_quality",
            )
        }
        findings = parse_findings(findings_raw)
        score = build_judge_score(axes, weights)
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise LLMProviderError(f"score_skill payload failed validation: {exc}") from exc
    return score, findings


def _redact(message: str) -> str:
    """Strip any sk-ant-... key fragments from error messages."""
    return _API_KEY_RE.sub("sk-ant-***", message)
