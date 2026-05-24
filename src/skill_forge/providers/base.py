"""Abstract LLMProvider — providers implement complete() (change #2)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Minimal interface for the providers used across extraction and judge."""

    @abstractmethod
    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return a completion string for the given prompt."""
