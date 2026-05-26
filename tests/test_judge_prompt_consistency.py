"""Cross-prompt consistency for judge rubric — prevent drift across providers.

The three judge prompts (Anthropic system, Claude Code header, Ollama system)
each spell out the rubric axes. If they drift, providers will score
inconsistently and the user won't notice until totals look weird.
"""

from __future__ import annotations

from skill_forge.models import JUDGE_AXES, JUDGE_SEVERITIES
from skill_forge.providers._prompts import JUDGE_SYSTEM_PROMPT
from skill_forge.providers.claude_code import _JUDGE_PROMPT_HEADER
from skill_forge.providers.ollama import _JUDGE_SYSTEM


def test_every_axis_named_in_every_judge_prompt() -> None:
    """Each axis name must appear literally in every judge prompt."""
    for prompt_label, prompt in [
        ("anthropic JUDGE_SYSTEM_PROMPT", JUDGE_SYSTEM_PROMPT),
        ("claude_code _JUDGE_PROMPT_HEADER", _JUDGE_PROMPT_HEADER),
        ("ollama _JUDGE_SYSTEM", _JUDGE_SYSTEM),
    ]:
        for axis in JUDGE_AXES:
            assert axis in prompt, (
                f"{prompt_label} is missing the axis name {axis!r} — "
                f"will drift from the model's understanding of the rubric"
            )


def test_every_severity_named_in_every_judge_prompt() -> None:
    """Each severity level must be named in every judge prompt."""
    for prompt_label, prompt in [
        ("anthropic JUDGE_SYSTEM_PROMPT", JUDGE_SYSTEM_PROMPT),
        ("claude_code _JUDGE_PROMPT_HEADER", _JUDGE_PROMPT_HEADER),
        ("ollama _JUDGE_SYSTEM", _JUDGE_SYSTEM),
    ]:
        for severity in JUDGE_SEVERITIES:
            assert severity in prompt, f"{prompt_label} doesn't mention severity {severity!r}"
