# Tasks — add-claude-code-provider

## Provider

- [x] `ClaudeCodeProvider.extract_draft` shells to `claude -p`, prompt via stdin
- [x] JSON-only prompt (no tool_use available via the CLI); explicit "ONLY emit JSON" instruction
- [x] Tolerant JSON extractor: try direct parse, fall back to first balanced `{...}` block
- [x] Validate parsed dict against `DistilledDraft`
- [x] Wrap `FileNotFoundError` / non-zero exit / `TimeoutExpired` as `LLMProviderError`

## Config loader

- [x] `skill_forge.config.load(root)` returns a dict; merges `config/default.yml` with bundled defaults
- [x] Bundled defaults live in `skill_forge.config` so the loader works even without `config/default.yml`

## CLI

- [x] Provider factory: maps `providers.extract` → `LLMProvider` instance
- [x] API-key guard fires only for `anthropic`
- [x] `config/default.yml` flips `providers.extract` to `claude_code`

## Tests

- [x] `test_provider_claude_code.py`: subprocess mocked end-to-end (happy, fenced, non-JSON, bad shape, non-zero exit, missing binary, timeout, truncation)
- [x] `test_config.py`: loader returns bundled defaults when no file / empty / non-dict, merges when file exists, doesn't mutate DEFAULTS
- [x] `test_cli_extract.py`: API-key guard only fires for anthropic; claude_code skips guard; unknown provider exits 2

## Validate

- [x] `ruff check` clean
- [x] `mypy --strict` clean (23 source files)
- [x] `pytest` green (90 tests)
- [x] **Live LLM smoke**: `forge extract file:///tmp/sample.html` produced
      `skills/_draft/resize-statefulset-pvc/SKILL.md` via `claude -p` in 17s,
      no API key. Output had all three required sections, preserved inline
      code citations, and even extrapolated a fourth failure mode not in
      the source.
