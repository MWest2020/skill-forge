"""License classification for candidate sources (change #4).

Four classes:
- permissive: extract + attribute
- copyleft: extract + attribute + share-alike note
- restrictive: extract for personal use only, do not share
- forbidden: skip, log to discovery_blocked.log
"""

from __future__ import annotations


def classify(source_url: str) -> str:
    """Return one of: permissive | copyleft | restrictive | forbidden."""
    raise NotImplementedError("license_check.classify: implemented in change #4")
