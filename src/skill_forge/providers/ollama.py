"""Ollama implementation of LLMProvider (change #5)."""

from __future__ import annotations

from .base import LLMProvider


class OllamaProvider(LLMProvider):
    """Calls a local Ollama host. Useful for judge stage."""

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        raise NotImplementedError("OllamaProvider.complete: implemented in change #5")
