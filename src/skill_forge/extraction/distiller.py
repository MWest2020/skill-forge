"""Glue FetchedContent + LLMProvider into a draft Skill + Sources.

Spec: openspec/changes/add-extraction-pipeline/specs/distiller/spec.md
"""

from __future__ import annotations

from datetime import UTC, datetime

from skill_forge.extraction.fetcher import FetchedContent
from skill_forge.models import Skill, Source, SourceRef
from skill_forge.providers.base import LLMProvider

UNKNOWN_LICENSE = "unknown"


def distill(
    content: FetchedContent,
    *,
    provider: LLMProvider,
    now: datetime | None = None,
) -> tuple[Skill, list[Source]]:
    """Return a draft Skill plus the Sources its pages contributed.

    The caller writes both via `storage.write_skill(..., draft=True)` and
    `storage.write_sources`. The distiller never touches the filesystem.
    """
    if not content.pages:
        raise ValueError("FetchedContent.pages must be non-empty")

    fetched_text = _join_pages(content)
    entry_url = content.pages[0].url

    draft = provider.extract_draft(source_url=entry_url, source_text=fetched_text)

    sources = _build_sources(content)
    skill = Skill(
        name=draft.name,
        description=draft.description,
        version=1,
        sources=[SourceRef(id=s.id) for s in sources],
        judge_score=None,
        created=(now or datetime.now(UTC)).date(),
        body=draft.body,
    )
    return skill, sources


def _join_pages(content: FetchedContent) -> str:
    parts: list[str] = []
    for i, page in enumerate(content.pages):
        if i > 0:
            parts.append(f"\n\n--- next page: {page.url} ---\n\n")
        parts.append(page.body.decode("utf-8", errors="replace"))
    return "".join(parts)


def _build_sources(content: FetchedContent) -> list[Source]:
    total = len(content.pages)
    sources: list[Source] = []
    for i, page in enumerate(content.pages, start=1):
        contribution = "single page" if total == 1 else f"page {i} of {total}"
        sources.append(
            Source(
                id=f"src-{page.sha256[:6]}",
                url=page.url,
                license=UNKNOWN_LICENSE,
                fetched_at=page.fetched_at,
                sha256=page.sha256,
                contribution=contribution,
            )
        )
    return sources
