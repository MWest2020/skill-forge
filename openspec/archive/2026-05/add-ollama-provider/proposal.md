# add-ollama-provider

## Why

Judging happens many times per skill across the curation loop (initial
judge, post-refine re-judge, post-accept verify). With `claude_code` it's
cheap (subscription); with `anthropic` it adds up. Ollama lets latency-
and cost-sensitive stages run against a local model — same `LLMProvider`
interface, swap via config.

## What

- `OllamaProvider` implementing all three LLMProvider methods
  (`extract_draft`, `judge`, `refine`) against an Ollama HTTP API at
  `http://localhost:11434` (configurable).
- JSON-only prompts (same shape as `ClaudeCodeProvider`) — no tool_use
  because Ollama models don't reliably do forced function calling.
- Config: existing `ollama:` block in `config/default.yml` gains the
  fields it needs (model, timeout). Provider factory in `cli.py` wires
  it up when `providers.{extract,judge}` is set to `ollama`.

## Scope

- `src/skill_forge/providers/ollama.py` — fill in from placeholder
- `cli.py` `_build_provider` — add the `ollama` branch
- `config/default.yml` — populate the `ollama:` block
- Tests: mocked httpx for happy/error paths
- README note about needing a running Ollama instance

## Out of scope

- Streaming responses.
- Multi-model judge ensemble.
- Pulling models — assume the user has run `ollama pull` themselves.
- Anthropic-Bedrock-style auth shims.

## Risks

- **Model output is much less structured than Claude.** Mitigation:
  prompt tightly for JSON-only, reuse `_extract_json_object` from
  `claude_code.py` to tolerate fences/prose, validate strictly via
  Pydantic.
- **Local Ollama not running.** Mitigation: clear `LLMProviderError`
  with the host URL and "start `ollama serve` then retry" message.
