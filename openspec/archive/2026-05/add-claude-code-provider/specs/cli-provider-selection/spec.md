# Spec — CLI provider selection

## Provider factory

```python
def _build_provider(name: str, cfg: dict) -> LLMProvider: ...
```

Maps a provider name to a concrete `LLMProvider`:

| `name` | Returns | Config keys read |
|---|---|---|
| `"anthropic"` | `AnthropicProvider(model=..., max_tokens=...)` | `cfg["anthropic"]` |
| `"claude_code"` | `ClaudeCodeProvider(binary=..., timeout=...)` | `cfg["claude_code"]` |

Unknown name → exit 2 with `"unknown provider: <name>"`.

## API-key guard

In `forge extract`, the existing `ANTHROPIC_API_KEY` check fires
**only when the selected provider is `anthropic`**. For `claude_code`,
auth is managed by `claude login` outside skill-forge.

## Resolution order

1. Load merged config via `skill_forge.config.load(root)`.
2. `provider_name = cfg["providers"]["extract"]`.
3. Build provider via the factory.
4. (For `anthropic` only) verify `ANTHROPIC_API_KEY`.

## Out of scope

- Per-command provider override (no `--provider` flag on `extract`).
  Add later if needed; one global default is enough now.
- Per-skill provider selection.
