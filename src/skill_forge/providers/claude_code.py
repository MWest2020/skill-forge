"""Claude Code (`claude -p`) implementation of LLMProvider.

Uses the user's Claude Code subscription instead of an API key. Spec:
openspec/changes/add-claude-code-provider/specs/claude-code-provider/spec.md
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from pydantic import ValidationError

from skill_forge.models import JudgeFinding, JudgeScore, Skill

from ._judge import build_judge_score, parse_findings, serialize_skill_for_judge
from .base import DistilledDraft, LLMProvider, LLMProviderError

MAX_SOURCE_CHARS = 180_000

_EXTRACTION_PROMPT_HEADER = """\
You distill a single source page (or a small chain of related pages) into a \
reusable Anthropic-style SKILL.md draft.

Output ONLY a single JSON object on stdout. No markdown fences, no prose, no \
preamble, no closing remarks. The object must have exactly these keys:

  {"name": "<slug>", "description": "<one paragraph>", "body": "<markdown>"}

Rules:
- name: short kebab-case slug, lowercase, digits and hyphens only, matching \
  `^[a-z0-9][a-z0-9-]*$`. Specific to the topic — not generic.
- description: one paragraph (1-3 sentences). Start with "Use this skill when ...".
- body: markdown body, NO frontmatter. Required sections in order:
    ## When to use
    ## Procedure
    ## Failure modes
  Paraphrase the source — never reproduce long passages verbatim. When the \
  source names specific commands, flags, config keys, or file paths, cite \
  them exactly in inline code.

If the input contains `--- next page: <url> ---` markers, synthesize one \
coherent skill across all pages.
"""


class ClaudeCodeProvider(LLMProvider):
    """Calls `claude -p` via subprocess; uses Claude Code's subscription auth."""

    def __init__(self, *, binary: str = "claude", timeout: float = 120.0) -> None:
        self._binary = binary
        self._timeout = timeout

    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
        if len(source_text) > MAX_SOURCE_CHARS:
            source_text = source_text[:MAX_SOURCE_CHARS]
        prompt = f"{_EXTRACTION_PROMPT_HEADER}\nSource URL: {source_url}\n\n---\n\n{source_text}\n"

        try:
            result = subprocess.run(
                [self._binary, "-p"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise LLMProviderError(f"`{self._binary}` not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise LLMProviderError(f"`{self._binary} -p` timed out after {self._timeout}s") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()[:500]
            raise LLMProviderError(f"`{self._binary} -p` exited {result.returncode}: {stderr}")

        data = _extract_json_object(result.stdout)
        if data is None:
            preview = (result.stdout or "").strip()[:200]
            raise LLMProviderError(
                f"claude did not return parseable JSON; first 200 chars: {preview!r}"
            )

        try:
            return DistilledDraft.model_validate(data)
        except ValidationError as exc:
            raise LLMProviderError(f"claude output failed validation: {exc}") from exc

    def judge(
        self, skill: Skill, *, weights: dict[str, float]
    ) -> tuple[JudgeScore, list[JudgeFinding]]:
        prompt = f"{_JUDGE_PROMPT_HEADER}\n\n--- skill ---\n\n{serialize_skill_for_judge(skill)}\n"
        data = self._run_claude(prompt)
        if data is None:
            raise LLMProviderError("claude did not return parseable JSON for judge")
        return _parse_judge_payload(data, weights)

    def _run_claude(self, prompt: str) -> dict[str, Any] | None:
        try:
            result = subprocess.run(
                [self._binary, "-p"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise LLMProviderError(f"`{self._binary}` not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise LLMProviderError(f"`{self._binary} -p` timed out after {self._timeout}s") from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()[:500]
            raise LLMProviderError(f"`{self._binary} -p` exited {result.returncode}: {stderr}")
        return _extract_json_object(result.stdout)


_JUDGE_PROMPT_HEADER = """\
You judge a single SKILL.md against the skill-forge rubric.

Output ONLY a single JSON object on stdout. No markdown fences, no prose.

Score each axis from 0.0 to 1.0:
- schema_compliance — required sections present in order
- clarity — unambiguous when-to-use, no unexplained jargon
- actionability — an agent could follow this without external guesswork
- gap_coverage — adds something distinct vs typical skills on this topic
- provenance_quality — sources field meaningful, body paraphrased not quoted

For each axis below 1.0, add one findings entry:
{"axis": <axis name>, "observation": <1-3 sentences>, "severity": "info"|"warning"|"blocker"}

Output shape (no extra keys, no `total` — the caller computes it):

{
  "schema_compliance": 0.0,
  "clarity": 0.0,
  "actionability": 0.0,
  "gap_coverage": 0.0,
  "provenance_quality": 0.0,
  "findings": [{"axis": "...", "observation": "...", "severity": "..."}]
}
"""


def _parse_judge_payload(
    data: dict[str, Any], weights: dict[str, float]
) -> tuple[JudgeScore, list[JudgeFinding]]:
    findings_raw = data.get("findings", [])
    if not isinstance(findings_raw, list):
        raise LLMProviderError("judge JSON `findings` must be a list")
    try:
        axes = {
            axis: float(data[axis])
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
        raise LLMProviderError(f"judge JSON failed validation: {exc}") from exc
    return score, findings


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object out of CLI stdout — tolerates fences and prose."""
    stripped = text.strip()
    if not stripped:
        return None
    # Direct parse: clean JSON only.
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    # Fallback: take the first balanced {...} slice.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
