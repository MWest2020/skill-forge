"""Tests for skill_forge.extraction.distiller — change #2."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from skill_forge.extraction.distiller import UNKNOWN_LICENSE, distill
from skill_forge.extraction.fetcher import FetchedContent, Page
from skill_forge.providers.base import DistilledDraft

from .fakes import FakeProvider


class _FakeProvider(FakeProvider):
    def __init__(self, draft: DistilledDraft) -> None:
        self.draft = draft
        self.calls: list[tuple[str, str]] = []

    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
        self.calls.append((source_url, source_text))
        return self.draft


def _page(url: str, body: bytes) -> Page:
    return Page(
        url=url,
        body=body,
        content_type="text/html",
        fetched_at=datetime(2026, 5, 24, 14, 30, tzinfo=UTC),
        sha256=hashlib.sha256(body).hexdigest(),
    )


def _draft() -> DistilledDraft:
    return DistilledDraft(
        name="demo-skill",
        description="Use this skill when X.",
        body="## When to use\n...\n## Procedure\n...\n## Failure modes\n...",
    )


def test_distill_single_page() -> None:
    page = _page("https://example.com/post", b"<html>hello</html>")
    content = FetchedContent(pages=(page,))
    provider = _FakeProvider(_draft())

    skill, sources = distill(content, provider=provider, now=datetime(2026, 5, 24, tzinfo=UTC))

    assert skill.name == "demo-skill"
    assert skill.version == 1
    assert skill.judge_score is None
    assert skill.created.isoformat() == "2026-05-24"
    assert [ref.id for ref in skill.sources] == [s.id for s in sources]

    assert len(sources) == 1
    assert sources[0].id == f"src-{page.sha256[:6]}"
    assert sources[0].url == page.url
    assert sources[0].license == UNKNOWN_LICENSE
    assert sources[0].sha256 == page.sha256
    assert sources[0].contribution == "single page"


def test_distill_multi_page_joins_with_markers_and_labels_contribution() -> None:
    p1 = _page("https://a/1", b"first page body")
    p2 = _page("https://a/2", b"second page body")
    content = FetchedContent(pages=(p1, p2))
    provider = _FakeProvider(_draft())

    skill, sources = distill(content, provider=provider)

    assert skill.name == "demo-skill"
    assert len(sources) == 2
    assert sources[0].contribution == "page 1 of 2"
    assert sources[1].contribution == "page 2 of 2"

    source_url_passed, source_text_passed = provider.calls[0]
    assert source_url_passed == "https://a/1"
    assert "--- next page: https://a/2 ---" in source_text_passed
    assert "first page body" in source_text_passed
    assert "second page body" in source_text_passed


def test_distill_requires_pages() -> None:
    with pytest.raises(ValueError):
        distill(FetchedContent(pages=()), provider=_FakeProvider(_draft()))


def test_distill_propagates_provider_errors() -> None:
    class _Boom(FakeProvider):
        def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
            raise RuntimeError("upstream broke")

    page = _page("https://x/y", b"hi")
    with pytest.raises(RuntimeError, match="upstream broke"):
        distill(FetchedContent(pages=(page,)), provider=_Boom())
