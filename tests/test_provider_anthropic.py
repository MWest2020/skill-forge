"""Tests for AnthropicProvider — change #2.

Mocks the anthropic.Anthropic client so we don't hit the live API.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import anthropic
import pytest

from skill_forge.models import JUDGE_AXES, Skill, SourceRef
from skill_forge.providers import anthropic as anth_module
from skill_forge.providers.anthropic import AnthropicProvider, _redact
from skill_forge.providers.base import DistilledDraft, LLMProviderError


def _fake_tool_use_response(draft: dict[str, str]) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_draft"
    block.input = draft
    response = MagicMock()
    response.content = [block]
    return response


def _install_fake_client(monkeypatch: pytest.MonkeyPatch, client: MagicMock) -> None:
    monkeypatch.setattr(anth_module.anthropic, "Anthropic", lambda **_: client)


def test_extract_draft_returns_validated_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.messages.create.return_value = _fake_tool_use_response(
        {
            "name": "foo-bar",
            "description": "Use this skill when X.",
            "body": "## When to use\n...\n## Procedure\n...\n## Failure modes\n...",
        }
    )
    _install_fake_client(monkeypatch, fake)

    draft = AnthropicProvider(api_key="sk-ant-test").extract_draft(
        source_url="https://example.com/post",
        source_text="hello world",
    )
    assert isinstance(draft, DistilledDraft)
    assert draft.name == "foo-bar"
    assert "## When to use" in draft.body


def test_extract_draft_uses_forced_tool_choice_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.messages.create.return_value = _fake_tool_use_response(
        {"name": "foo", "description": "Use this skill.", "body": "body."}
    )
    _install_fake_client(monkeypatch, fake)

    AnthropicProvider().extract_draft(source_url="https://x", source_text="hi")

    kwargs = fake.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-7"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "emit_draft"}
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kwargs["tools"][0]["name"] == "emit_draft"


def test_extract_draft_raises_when_no_tool_use(monkeypatch: pytest.MonkeyPatch) -> None:
    block = MagicMock()
    block.type = "text"
    response = MagicMock()
    response.content = [block]
    fake = MagicMock()
    fake.messages.create.return_value = response
    _install_fake_client(monkeypatch, fake)

    with pytest.raises(LLMProviderError, match="did not emit"):
        AnthropicProvider().extract_draft(source_url="https://x", source_text="hi")


def test_extract_draft_raises_on_bad_draft_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.messages.create.return_value = _fake_tool_use_response(
        {"name": "Bad Slug!", "description": "...", "body": "..."}
    )
    _install_fake_client(monkeypatch, fake)

    with pytest.raises(LLMProviderError, match="failed validation"):
        AnthropicProvider().extract_draft(source_url="https://x", source_text="hi")


def test_extract_draft_wraps_api_error_and_redacts_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubAPIError(anthropic.APIError):
        def __init__(self, msg: str) -> None:
            Exception.__init__(self, msg)
            self.message = msg

    fake = MagicMock()
    fake.messages.create.side_effect = StubAPIError("upstream rejected key sk-ant-abc_123-XYZ")
    _install_fake_client(monkeypatch, fake)

    with pytest.raises(LLMProviderError) as exc:
        AnthropicProvider().extract_draft(source_url="https://x", source_text="hi")
    msg = str(exc.value)
    assert "sk-ant-***" in msg
    assert "sk-ant-abc_123-XYZ" not in msg


def test_extract_draft_truncates_long_source(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.messages.create.return_value = _fake_tool_use_response(
        {"name": "foo", "description": "Use this skill.", "body": "body."}
    )
    _install_fake_client(monkeypatch, fake)

    very_long = "x" * 250_000
    AnthropicProvider().extract_draft(source_url="https://x", source_text=very_long)
    user_content = fake.messages.create.call_args.kwargs["messages"][0]["content"]
    # 180k truncation + ~50 chars of header
    assert len(user_content) < 181_000


def test_redact_helper() -> None:
    assert _redact("oops sk-ant-foo_bar-123 here") == "oops sk-ant-*** here"
    assert _redact("no key in this string") == "no key in this string"


# --- judge --------------------------------------------------------------------


_WEIGHTS = {axis: 1 / len(JUDGE_AXES) for axis in JUDGE_AXES}


def _fake_score_response(payload: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "score_skill"
    block.input = payload
    response = MagicMock()
    response.content = [block]
    return response


def _skill() -> Skill:
    return Skill(
        name="demo",
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="## When to use\nA\n## Procedure\nB\n## Failure modes\nC\n",
    )


def test_anthropic_judge_returns_score_and_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.messages.create.return_value = _fake_score_response(
        {
            **{axis: 0.8 for axis in JUDGE_AXES},
            "findings": [
                {"axis": "clarity", "observation": "could be tighter", "severity": "warning"}
            ],
        }
    )
    _install_fake_client(monkeypatch, fake)

    run = AnthropicProvider().judge(_skill(), temperature=0.0)
    assert run.axes["clarity"] == pytest.approx(0.8)
    assert len(run.findings) == 1
    assert run.findings[0].axis == "clarity"
    assert run.model_id.startswith("anthropic:")
    assert len(run.prompt_sha256) == 64

    # Forced tool_choice + cache_control + temperature passed through
    kwargs = fake.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "score_skill"}
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kwargs["temperature"] == 0.0


def test_anthropic_judge_raises_when_no_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    block = MagicMock()
    block.type = "text"
    response = MagicMock()
    response.content = [block]
    fake = MagicMock()
    fake.messages.create.return_value = response
    _install_fake_client(monkeypatch, fake)

    with pytest.raises(LLMProviderError, match="did not emit"):
        AnthropicProvider().judge(_skill())


def test_anthropic_judge_raises_on_bad_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    # Missing one axis
    fake.messages.create.return_value = _fake_score_response(
        {
            "schema_compliance": 0.8,
            "clarity": 0.8,
            "actionability": 0.8,
            "gap_coverage": 0.8,
            # provenance_quality missing
            "findings": [],
        }
    )
    _install_fake_client(monkeypatch, fake)
    with pytest.raises(LLMProviderError, match="axis"):
        AnthropicProvider().judge(_skill())
