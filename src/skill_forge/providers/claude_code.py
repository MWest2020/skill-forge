"""Claude Code (`claude -p`) implementation of LLMProvider.

Uses the user's Claude Code subscription instead of an API key. Spec:
openspec/changes/add-claude-code-provider/specs/claude-code-provider/spec.md
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from pydantic import ValidationError

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
        prompt = (
            f"{_EXTRACTION_PROMPT_HEADER}\n"
            f"Source URL: {source_url}\n\n---\n\n{source_text}\n"
        )

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
            raise LLMProviderError(
                f"`{self._binary} -p` timed out after {self._timeout}s"
            ) from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()[:500]
            raise LLMProviderError(
                f"`{self._binary} -p` exited {result.returncode}: {stderr}"
            )

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
