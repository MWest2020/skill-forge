"""Fetch source content, respecting robots.txt (change #2)."""

from __future__ import annotations


def fetch(source_url: str) -> str:
    """Return raw content for a source URL after robots.txt check."""
    raise NotImplementedError("fetcher.fetch: implemented in change #2")
