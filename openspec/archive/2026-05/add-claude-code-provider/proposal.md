# Change: add-claude-code-provider

## Why

`AnthropicProvider` requires `ANTHROPIC_API_KEY` and bills pay-per-token.
Mark already has a Claude subscription via Claude Code (`claude` CLI is on
PATH, authenticated). For personal use, running extractions against the
subscription is preferable: no key to manage, no per-token billing.

The `LLMProvider` abstraction added in change #2 was designed for exactly
this — a second concrete implementation, no other code changes.

## What

- `ClaudeCodeProvider`: invokes `claude -p <prompt>` via `subprocess`,
  parses a JSON object out of stdout, validates against the
  `DistilledDraft` schema.
- Tiny `config` loader (stdlib `yaml`) that reads
  `{root}/config/default.yml` and falls back to bundled defaults.
- Provider factory in the CLI: reads `providers.extract` from config,
  instantiates the matching provider.
- API-key guard on `forge extract` fires only when the selected
  provider is `anthropic`.
- Default flips: `providers.extract: claude_code` (subscription-first).
  `anthropic` is still one-line away in config.

## Scope

- `src/skill_forge/providers/claude_code.py`
- `src/skill_forge/config.py` (new)
- `src/skill_forge/cli.py` — provider factory + conditional key guard
- `config/default.yml` — default to `claude_code`
- `tests/test_provider_claude_code.py`
- `tests/test_config.py`
- Updates to `tests/test_cli_extract.py` for the provider-selection path

## Out of scope

- Claude Agent SDK (Python). The subprocess route is simpler and uses the
  exact same auth; we can revisit if we need typed events or MCP later.
- Provider switching per skill/per command. One global default for now.
- Cost telemetry. The subscription path has no per-call billing surface.

## Risks

- **Output drift.** `claude -p` returns prose; the model may wrap the
  JSON in fences or add commentary. Mitigation: explicit JSON-only
  prompt + tolerant parser that extracts the first balanced `{...}`
  block when direct parse fails. Validation against `DistilledDraft`
  catches structural drift.
- **Quotation / shell-escaping.** Large source bodies in argv risk
  hitting `ARG_MAX`. Mitigation: pass the prompt via stdin, not argv.
- **Subprocess timeouts / hangs.** Mitigation: default 120s timeout,
  raise `LLMProviderError` on timeout.
- **Recursion if invoked from inside Claude Code.** A `claude -p` call
  from within a Claude Code session is supported by the CLI; the parent
  session and the subprocess are independent. No code-path concern, but
  worth documenting.
