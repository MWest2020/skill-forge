"""Claude Code (`claude -p`) implementation of LLMProvider.

Uses the user's Claude Code subscription instead of an API key. Spec:
openspec/changes/add-claude-code-provider/specs/claude-code-provider/spec.md
"""

from __future__ import annotations

import subprocess
from typing import Any

from pydantic import ValidationError

from skill_forge.models import JudgeFinding, JudgeRun, Skill

from ._judge import (
    extract_json_object,
    parse_judge_axes,
    prompt_sha256,
    serialize_skill_for_judge,
    serialize_skill_for_refine,
)
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
    ## Source
  Paraphrase the source — never reproduce long passages verbatim. When the \
  source names specific commands, flags, config keys, or file paths, cite \
  them exactly in inline code.
  The `## Source` section is mandatory: list source URL(s) as bullet points \
  with page titles when known (e.g. `- [Title](URL)`).

If the input contains `--- next page: <url> ---` markers, synthesize one \
coherent skill across all pages. List every page URL under `## Source`.
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

        data = extract_json_object(result.stdout)
        if data is None:
            preview = (result.stdout or "").strip()[:200]
            raise LLMProviderError(
                f"claude did not return parseable JSON; first 200 chars: {preview!r}"
            )

        try:
            return DistilledDraft.model_validate(data)
        except ValidationError as exc:
            raise LLMProviderError(f"claude output failed validation: {exc}") from exc

    def judge(self, skill: Skill, *, temperature: float = 0.0) -> JudgeRun:
        # `claude -p` exposes no temperature flag; the orchestrator records the
        # requested value, but it is not applied for this provider.
        prompt = f"{_JUDGE_PROMPT_HEADER}\n\n--- skill ---\n\n{serialize_skill_for_judge(skill)}\n"
        data = self._run_claude(prompt)
        if data is None:
            raise LLMProviderError("claude did not return parseable JSON for judge")
        axes, findings = parse_judge_axes(data)
        return JudgeRun(
            axes=axes,
            findings=findings,
            model_id=f"claude_code:{self._binary}",
            prompt_sha256=prompt_sha256(prompt),
        )

    def refine(
        self,
        skill: Skill,
        *,
        findings: list[JudgeFinding],
        hint: str | None = None,
        extra_source: str | None = None,
    ) -> str:
        prompt = (
            f"{_REFINE_PROMPT_HEADER}\n\n"
            f"{serialize_skill_for_refine(skill, findings, hint, extra_source)}\n"
        )
        data = self._run_claude(prompt)
        if data is None:
            raise LLMProviderError("claude did not return parseable JSON for refine")
        body = data.get("body")
        if not isinstance(body, str) or not body.strip():
            raise LLMProviderError("refine JSON must have a non-empty `body` string")
        return body

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
        return extract_json_object(result.stdout)


_REFINE_PROMPT_HEADER = """\
You refine an existing SKILL.md to address specific judge findings.

Output ONLY a single JSON object on stdout. No fences, no prose. Shape:

  {"body": "<refined markdown body, no frontmatter>"}

Rules:
- Keep the existing section structure (When to use / Procedure / Failure modes
  / Source) unless a finding explicitly asks you to restructure.
- `## Source` section is mandatory. Preserve its URLs if present in the input
  body. If absent, ADD it from the additional source material URL.
- Address each finding precisely. Surgical edits, not wholesale rewrites.
- If `additional source material` is provided, paraphrase relevant material
  AND add its URL to `## Source`. Never quote verbatim.
- If `user hint` is provided, treat it as priority over generic improvements.
- Preserve specific commands, flags, config keys, file paths verbatim.
"""


_JUDGE_PROMPT_HEADER = """\
You judge a single SKILL.md against the skill-forge rubric.

Output ONLY a single JSON object on stdout. No markdown fences, no prose.

Score each axis from 0.0 to 1.0:
- schema_compliance — required sections present in order
- clarity — unambiguous when-to-use, no unexplained jargon
- actionability — an agent could follow this without external guesswork
- gap_coverage — adds something distinct vs typical skills on this topic
- provenance_quality — body has a `## Source` section with human-readable
  URLs (mandatory; missing → score this axis at 0.4 or below), sources field
  meaningful, body paraphrased not quoted
- structural_clarity — delimited where it aids parsing; penalize over-tagging a
  short skill (distinct from schema_compliance, which only checks sections exist)
- example_grounding — grounded in a concrete example; a pure reference card
  that needs none scores 1.0
- tool_declaration — names how to invoke any tools the procedure uses; a skill
  that invokes no tools scores 1.0

For each axis below 1.0, add one findings entry:
{"axis": <axis name>, "observation": <1-3 sentences>, "severity": "info"|"warning"|"blocker"}

Output shape (no extra keys, no `total` — the caller computes it):

{
  "schema_compliance": 0.0,
  "clarity": 0.0,
  "actionability": 0.0,
  "gap_coverage": 0.0,
  "provenance_quality": 0.0,
  "structural_clarity": 0.0,
  "example_grounding": 0.0,
  "tool_declaration": 0.0,
  "findings": [{"axis": "...", "observation": "...", "severity": "..."}]
}
"""


# Judge payload parsing now lives in _judge.parse_judge_axes (shared across
# providers); extract_json_object likewise.
