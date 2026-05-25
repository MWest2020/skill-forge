"""Web-search discovery. Out of scope for change #4 MVP.

Returns an empty list so the discover CLI can still call this without
special-casing. A future change can plug in DuckDuckGo, Google CSE, or
another backend behind the same `search(topic)` signature.
"""

from __future__ import annotations


def search(topic: str) -> list[str]:  # noqa: ARG001  # signature is the contract
    return []
