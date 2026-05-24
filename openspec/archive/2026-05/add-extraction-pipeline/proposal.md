# Change: add-extraction-pipeline

## Why

Change #1 landed the data layer. Now we need the first half of the pipeline:
turn a URL (or local file) into a draft `SKILL.md` plus a populated
`sources/{slug}.yml`. Until this lands, `forge extract` raises
`NotImplementedError`.

Documentation sites are paginated. A useful "extract" needs an opt-in
`--all` to follow `rel="next"` so a series like
`docs.foo.com/guide/intro` → `/guide/setup` → `/guide/usage` becomes
one coherent skill instead of three half-skills.

## What

- `LLMProvider` abstract base + `AnthropicProvider` implementation, with
  prompt caching on the (large, reused) extraction system prompt.
- A `DistilledDraft` Pydantic model that Claude is forced to emit via
  tool-use — structured output, no fragile parsing.
- `fetcher.fetch(url, *, follow_next, max_pages)` returning a
  `FetchedContent` of one or more `Page`s. Supports `http(s)://` and
  `file://`. Respects `robots.txt` per origin. Follows `rel="next"` from
  HTML head or body when `follow_next=True`. Stops on cross-origin, loop,
  or page cap.
- `distiller.distill(content, *, provider)` takes the fetched content, calls
  the provider, and returns a `Skill` (draft, version=1, judge_score=None)
  plus the matching `list[Source]` so the caller can write both.
- `forge extract <url>` wired up. New `--all` and `--max-pages N` flags.
  Output is always written to `skills/_draft/{slug}/SKILL.md` and
  `sources/{slug}.yml`. Live promotion is change #3.

## Scope

- `src/skill_forge/extraction/{fetcher,distiller}.py`
- `src/skill_forge/providers/{base,anthropic}.py`
- `src/skill_forge/cli.py` — wire `extract`
- `pyproject.toml` — add `anthropic` runtime dep
- Tests: `test_fetcher.py`, `test_distiller.py`, `test_provider_anthropic.py`,
  `test_cli_extract.py`
- A small local HTML fixture under `tests/fixtures/` for fetcher tests
  (no live HTTP in CI)

## Out of scope

- Web/GitHub discovery (`forge discover`) — change #4.
- Judge + promotion (`forge judge`, automatic move to live) — change #3.
- Ollama provider — change #5.
- JavaScript-rendered pages. Static HTML only; document the limit. If a
  page needs JS to render its content, the skill draft will be empty/noisy
  and the judge stage (change #3) will reject it.
- Following non-`rel="next"` "Next" links (text/class heuristics). Too
  fragile for an auditable default.

## Risks

- **Cost runaway with `--all`.** A misclassified pagination chain could
  fetch a domain's entire archive. Mitigation: `max_pages` cap (default
  50, configurable), strict same-origin check, loop detection.
- **Bad input → garbage skill.** A page that's mostly nav/footer becomes
  a low-quality skill that still gets written to drafts. Acceptable for
  this change — the judge (#3) is the quality gate. We just need to make
  sure the draft is *parseable* and survives `Skill.model_validate`.
- **API key leakage in error paths.** AnthropicProvider must not echo the
  key on failure; only log a redacted hint.
- **License detection isn't part of this change** — `extract <url>` will
  set `license: "unknown"` on the Source until change #4 adds detection.
  Documented in spec.
