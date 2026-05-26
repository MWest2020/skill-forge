"""Tests for OllamaProvider — change #5."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest

from skill_forge.models import JUDGE_AXES, Skill, SourceRef
from skill_forge.providers import ollama as ol_mod
from skill_forge.providers.base import LLMProviderError
from skill_forge.providers.ollama import OllamaProvider

_WEIGHTS = {
    "schema_compliance": 0.20,
    "clarity": 0.20,
    "actionability": 0.25,
    "gap_coverage": 0.20,
    "provenance_quality": 0.15,
}


def _envelope(content: str) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"message": {"content": content}}
    return response


def _http_error_response(status: int = 500, text: str = "boom") -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = text
    return response


def _patch_post(monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> MagicMock:
    fake = MagicMock(**kwargs)
    monkeypatch.setattr(ol_mod.httpx, "post", fake)
    return fake


def _skill() -> Skill:
    return Skill(
        name="demo",
        description="Use when X.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="## When to use\nA\n## Procedure\nB\n## Failure modes\nC\n",
    )


# --- extract_draft -----------------------------------------------------------


def test_extract_returns_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {
            "name": "demo-skill",
            "description": "Use this skill when X.",
            "body": "## When to use\nX\n## Procedure\nY\n## Failure modes\nZ",
        }
    )
    _patch_post(monkeypatch, return_value=_envelope(payload))
    draft = OllamaProvider().extract_draft(source_url="https://x", source_text="hi")
    assert draft.name == "demo-skill"


def test_extract_bad_shape_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, return_value=_envelope('{"name": "Bad Slug!"}'))
    with pytest.raises(LLMProviderError, match="validation"):
        OllamaProvider().extract_draft(source_url="https://x", source_text="hi")


# --- judge -------------------------------------------------------------------


def test_judge_returns_score(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {
            **{axis: 0.7 for axis in JUDGE_AXES},
            "findings": [
                {"axis": "clarity", "observation": "could be tighter", "severity": "warning"}
            ],
        }
    )
    _patch_post(monkeypatch, return_value=_envelope(payload))
    score, findings = OllamaProvider().judge(_skill(), weights=_WEIGHTS)
    assert score.total == pytest.approx(0.7)
    assert findings[0].axis == "clarity"


def test_judge_missing_axis_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"schema_compliance": 0.8, "findings": []})
    _patch_post(monkeypatch, return_value=_envelope(payload))
    with pytest.raises(LLMProviderError, match="validation"):
        OllamaProvider().judge(_skill(), weights=_WEIGHTS)


# --- refine ------------------------------------------------------------------


def test_refine_returns_body(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, return_value=_envelope('{"body": "## refined"}'))
    body = OllamaProvider().refine(_skill(), findings=[])
    assert "refined" in body


def test_refine_missing_body_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, return_value=_envelope('{"other": "field"}'))
    with pytest.raises(LLMProviderError, match="body"):
        OllamaProvider().refine(_skill(), findings=[])


# --- error paths -------------------------------------------------------------


def test_unreachable_server(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(
        monkeypatch,
        side_effect=httpx.ConnectError("connection refused"),
    )
    with pytest.raises(LLMProviderError, match="unreachable"):
        OllamaProvider(host="http://localhost:65535").extract_draft(
            source_url="https://x", source_text="hi"
        )


def test_http_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, return_value=_http_error_response(500, "server died"))
    with pytest.raises(LLMProviderError, match="500"):
        OllamaProvider().extract_draft(source_url="https://x", source_text="hi")


def test_unparseable_content(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, return_value=_envelope("not json at all"))
    with pytest.raises(LLMProviderError, match="parseable JSON"):
        OllamaProvider().extract_draft(source_url="https://x", source_text="hi")


def test_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    draft_json = '{"name": "demo", "description": "Use this skill when X.", "body": "ok"}'
    fake = _patch_post(monkeypatch, return_value=_envelope(draft_json))
    OllamaProvider(host="http://host:11434/", model="custom-model").extract_draft(
        source_url="https://x", source_text="hi"
    )
    args = fake.call_args
    assert args.args[0] == "http://host:11434/api/chat"
    body = args.kwargs["json"]
    assert body["model"] == "custom-model"
    assert body["format"] == "json"
    assert body["stream"] is False
