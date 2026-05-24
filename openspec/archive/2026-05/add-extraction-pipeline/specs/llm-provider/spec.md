# Spec — LLM provider

Abstract base + Anthropic implementation. Ollama lands in change #5.

## Types

```python
class DistilledDraft(BaseModel):
    """The structured output extract_draft must return."""
    name: str          # slug-shaped; validated identically to Skill.name
    description: str   # one paragraph "when to use"
    body: str          # markdown body, no frontmatter

class LLMProvider(ABC):
    @abstractmethod
    def extract_draft(
        self,
        *,
        source_url: str,
        source_text: str,   # raw HTML or text passed straight from the fetcher
    ) -> DistilledDraft: ...
```

`DistilledDraft.name` reuses `models.SLUG_RE`. Description and body are
free-text but body must be non-empty after strip.

## AnthropicProvider

```python
class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str | None = None,   # falls back to $ANTHROPIC_API_KEY
        model: str = "claude-opus-4-7",
        max_tokens: int = 4096,
    ): ...
```

### Behavior

- Calls `messages.create` once per `extract_draft`.
- `system` is a **list** containing a single text block with
  `cache_control={"type": "ephemeral"}` — the extraction instructions are
  identical across calls, so caching wins after the second call inside
  the 5-minute TTL window.
- Forces structured output via `tools=[EMIT_DRAFT_TOOL]` and
  `tool_choice={"type": "tool", "name": "emit_draft"}`. The tool's
  `input_schema` mirrors `DistilledDraft`.
- The single user message is:

  ```
  Source URL: <url>

  ---

  <source_text, truncated to 180 000 chars to stay under context>
  ```

- Inspects the response: first `tool_use` block with name `emit_draft`
  becomes a `DistilledDraft` via `model_validate(block.input)`.
- If the model returns text instead of a tool call (shouldn't happen with
  forced tool choice, but defensive): raise `LLMProviderError("model did
  not emit emit_draft")`.
- On any `anthropic.APIError`, wrap as `LLMProviderError` with the
  exception message but **no** API key fragment. The original exception
  chains via `__cause__` for debugging.

### System prompt (sketch)

```
You distill a single source page into a reusable Anthropic SKILL.md.
Output ONLY via the `emit_draft` tool.

Rules:
- name: short kebab-case slug (a-z, 0-9, -). Specific to the topic.
- description: one paragraph that answers "when should an agent use
  this skill?". No marketing.
- body: markdown. Required sections in order: "When to use",
  "Procedure", "Failure modes". Add others as useful. Paraphrase the
  source — never quote verbatim. Cite specific commands/flags/config
  keys when present in the source.
```

The full prompt lives in `providers/_prompts.py`.

## Failure modes

- `LLMProviderError(message)` — wraps any provider-side failure.
  Subclasses: `LLMProviderError.NetworkError`, `.RateLimited`,
  `.InvalidResponse`. The original exception chains via `raise from`.
- The provider never returns `None`. Either a `DistilledDraft` or raises.

## Non-goals

- No streaming.
- No multi-turn refinement (change #6).
- No fallback to a different model on failure.
