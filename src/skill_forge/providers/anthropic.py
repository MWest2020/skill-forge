"""Anthropic implementation of LLMProvider (change #2)."""

from __future__ import annotations

from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Calls the Claude API. SDK dependency added in change #2."""

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        raise NotImplementedError("AnthropicProvider.complete: implemented in change #2")
