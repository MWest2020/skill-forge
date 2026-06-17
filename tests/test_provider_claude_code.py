"""Tests for ClaudeCodeProvider — change #2.1.

Mocks subprocess.run so we don't shell out to a real `claude` binary.
"""

from __future__ import annotations

import subprocess
from datetime import date
from unittest.mock import MagicMock

import pytest

from skill_forge.models import JUDGE_AXES, Skill, SourceRef
from skill_forge.providers import claude_code as cc_mod
from skill_forge.providers._judge import extract_json_object
from skill_forge.providers.base import DistilledDraft, LLMProviderError
from skill_forge.providers.claude_code import ClaudeCodeProvider

VALID_JSON = (
    '{"name": "demo-skill", "description": "Use this skill when X.", '
    '"body": "## When to use\\nX.\\n## Procedure\\nY.\\n## Failure modes\\nZ."}'
)


def _ok_completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["claude", "-p"], returncode=0, stdout=stdout, stderr=""
    )


def _failed_completed(stderr: str, returncode: int = 2) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["claude", "-p"], returncode=returncode, stdout="", stderr=stderr
    )


def _patch_run(monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> MagicMock:
    fake = MagicMock(**kwargs)
    monkeypatch.setattr(cc_mod.subprocess, "run", fake)
    return fake


# --- happy paths --------------------------------------------------------------


def test_extract_draft_parses_clean_json(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch_run(monkeypatch, return_value=_ok_completed(VALID_JSON))
    draft = ClaudeCodeProvider().extract_draft(source_url="https://x", source_text="hi")
    assert isinstance(draft, DistilledDraft)
    assert draft.name == "demo-skill"
    # prompt was passed via stdin, not argv
    kwargs = fake.call_args.kwargs
    assert kwargs["input"].startswith("You distill")
    assert "Source URL: https://x" in kwargs["input"]
    assert kwargs["text"] is True
    assert kwargs["capture_output"] is True


def test_extract_draft_tolerates_fenced_json(monkeypatch: pytest.MonkeyPatch) -> None:
    fenced = f"Sure — here's the draft:\n\n```json\n{VALID_JSON}\n```\nHope this helps."
    _patch_run(monkeypatch, return_value=_ok_completed(fenced))
    draft = ClaudeCodeProvider().extract_draft(source_url="https://x", source_text="hi")
    assert draft.name == "demo-skill"


# --- failure paths ------------------------------------------------------------


def test_extract_draft_raises_on_unparseable(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, return_value=_ok_completed("no JSON in this response"))
    with pytest.raises(LLMProviderError, match="parseable JSON"):
        ClaudeCodeProvider().extract_draft(source_url="https://x", source_text="hi")


def test_extract_draft_raises_on_bad_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = '{"name": "Bad Slug!", "description": "x", "body": "y"}'
    _patch_run(monkeypatch, return_value=_ok_completed(bad))
    with pytest.raises(LLMProviderError, match="failed validation"):
        ClaudeCodeProvider().extract_draft(source_url="https://x", source_text="hi")


def test_extract_draft_raises_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, return_value=_failed_completed("not authenticated", returncode=2))
    with pytest.raises(LLMProviderError, match="exited 2"):
        ClaudeCodeProvider().extract_draft(source_url="https://x", source_text="hi")


def test_extract_draft_raises_on_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, side_effect=FileNotFoundError("claude"))
    with pytest.raises(LLMProviderError, match="not found on PATH"):
        ClaudeCodeProvider(binary="claude").extract_draft(source_url="https://x", source_text="hi")


def test_extract_draft_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(
        monkeypatch,
        side_effect=subprocess.TimeoutExpired(cmd="claude -p", timeout=1.0),
    )
    with pytest.raises(LLMProviderError, match="timed out"):
        ClaudeCodeProvider(timeout=1.0).extract_draft(source_url="https://x", source_text="hi")


def test_extract_draft_truncates_long_source(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch_run(monkeypatch, return_value=_ok_completed(VALID_JSON))
    ClaudeCodeProvider().extract_draft(source_url="https://x", source_text="x" * 250_000)
    prompt = fake.call_args.kwargs["input"]
    # 180k char source cap + the prompt header (~1k chars)
    assert len(prompt) < 182_000


# --- extract_json_object helper ---------------------------------------------


def test_extract_json_direct() -> None:
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_from_prose() -> None:
    assert extract_json_object('Sure: {"a": 1, "b": 2} done.') == {"a": 1, "b": 2}


def test_extract_json_fenced() -> None:
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_none_when_no_object() -> None:
    assert extract_json_object("no braces here") is None


def test_extract_json_none_when_array() -> None:
    # Top-level arrays are not valid drafts
    assert extract_json_object("[1, 2, 3]") is None


# --- judge --------------------------------------------------------------------


_WEIGHTS = {axis: 1 / len(JUDGE_AXES) for axis in JUDGE_AXES}


def _skill() -> Skill:
    return Skill(
        name="demo",
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="## When to use\nA\n## Procedure\nB\n## Failure modes\nC\n",
    )


def _judge_json(value: float = 0.8) -> str:
    payload = {axis: value for axis in JUDGE_AXES}
    payload["findings"] = []
    return __import__("json").dumps(payload)


def test_claude_code_judge_parses_clean_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, return_value=_ok_completed(_judge_json(0.9)))
    run = ClaudeCodeProvider().judge(_skill())
    assert run.axes["schema_compliance"] == pytest.approx(0.9)
    assert run.findings == []
    assert run.model_id.startswith("claude_code:")
    assert len(run.prompt_sha256) == 64


def test_claude_code_judge_passes_skill_via_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch_run(monkeypatch, return_value=_ok_completed(_judge_json()))
    ClaudeCodeProvider().judge(_skill())
    prompt = fake.call_args.kwargs["input"]
    assert "## When to use" in prompt
    assert "demo" in prompt


def test_claude_code_judge_raises_on_unparseable(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, return_value=_ok_completed("not JSON"))
    with pytest.raises(LLMProviderError, match="parseable JSON"):
        ClaudeCodeProvider().judge(_skill())


def test_claude_code_judge_raises_on_missing_axis(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = '{"schema_compliance": 0.8, "clarity": 0.8, "findings": []}'
    _patch_run(monkeypatch, return_value=_ok_completed(bad))
    with pytest.raises(LLMProviderError, match="axis"):
        ClaudeCodeProvider().judge(_skill())
