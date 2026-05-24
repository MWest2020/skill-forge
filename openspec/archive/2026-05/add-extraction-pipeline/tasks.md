# Tasks — add-extraction-pipeline

## Fetcher

- [x] Failing test for HTTP fetch of a single page (pytest-httpserver)
- [x] Implement `Page` and `FetchedContent` dataclasses
- [x] Implement `fetch(url)` for `http(s)` and `file://` schemes
- [x] Implement robots.txt check (cached per origin, `urllib.robotparser`)
- [x] Implement `rel="next"` detection (head `<link>` + body `<a>`, head preferred)
- [x] Implement `follow_next` loop with same-origin guard, loop detection, `max_pages` cap
- [x] Tests with local HTTP server (`pytest-httpserver`) — no live network

## LLM provider

- [x] `LLMProvider` ABC + `DistilledDraft` pydantic model + `LLMProviderError`
- [x] `AnthropicProvider.extract_draft` using `tool_use` with forced tool choice
- [x] Cache the extraction system prompt with `cache_control: ephemeral`
- [x] Redact API key in error paths
- [x] Provider tests with mocked `anthropic.Anthropic.messages.create`

## Distiller

- [x] `distill(content, *, provider) -> tuple[Skill, list[Source]]`
- [x] Source id derived from `sha256[:6]` of the page bytes
- [x] `license="unknown"` until change #4
- [x] Slug derived from `DistilledDraft.name` (validated by both prompt + model)

## CLI

- [x] Wire `forge extract <url>` to fetcher + distiller + storage
- [x] `--all` and `--max-pages` flags
- [x] Drafts always written to `skills/_draft/`, sources to `sources/`
- [x] Slug collision: auto-suffix `-N` until free
- [x] Exit codes: 0 ok, 1 fetch fail, 2 missing API key, 3 provider error
- [x] CLI test with fake provider + local HTML fixture

## Validate

- [x] `ruff check` clean
- [x] `mypy --strict` clean (21 source files)
- [x] `pytest` green (70 tests)
- [x] CLI binary smoke: `forge extract --help` shows --all/--max-pages, missing-key path exits 2 with clear message
- [ ] **Live LLM smoke**: pending an `ANTHROPIC_API_KEY` in `.env`. Then run:
      `uv run forge extract file://$(pwd)/some-small-page.html`
      and verify a draft lands at `skills/_draft/<slug>/SKILL.md`.
