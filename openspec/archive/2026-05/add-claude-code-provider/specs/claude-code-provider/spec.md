# Spec — ClaudeCodeProvider

## API

```python
class ClaudeCodeProvider(LLMProvider):
    def __init__(
        self,
        *,
        binary: str = "claude",
        timeout: float = 120.0,
    ): ...
    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft: ...
```

## Behavior

- Builds a prompt using the same rules as `AnthropicProvider`
  (`name` slug, `description`, `body` with required sections), but
  instructs the model to **output ONLY a single JSON object** with
  keys `name`, `description`, `body`. No fences, no prose.
- Invokes `subprocess.run([binary, "-p"], input=prompt, ...)`:
  - `input=` passes the prompt via stdin (avoids argv length limits).
  - `text=True`, `capture_output=True`, `timeout=self._timeout`.
  - `check=False`; we inspect `returncode` ourselves to surface stderr
    in the error message.
- Parses stdout:
  1. `json.loads(stdout.strip())` first.
  2. On failure, look for the first `{` and last `}` and parse the slice.
  3. If neither works, raise `LLMProviderError("claude did not return parseable JSON")`.
- Validates the parsed dict via `DistilledDraft.model_validate`. On
  `ValidationError`, raise `LLMProviderError("claude output failed validation: ...")`.

## Failure modes

| Error | Cause |
|---|---|
| `LLMProviderError("\`claude\` not found on PATH")` | Binary not installed |
| `LLMProviderError("claude exited <n>: <stderr>")` | Non-zero exit (auth missing, internal error) |
| `LLMProviderError("claude timed out after <s>s")` | `subprocess.TimeoutExpired` |
| `LLMProviderError("claude did not return parseable JSON")` | Output had no `{...}` block |
| `LLMProviderError("claude output failed validation: ...")` | Parsed dict didn't match `DistilledDraft` |

Original exceptions chain via `raise ... from`.

## Source truncation

Same cap as `AnthropicProvider`: 180 000 characters. Larger inputs are
truncated before being passed to the CLI.
