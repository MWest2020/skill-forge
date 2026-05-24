# Spec — distiller

Glues `FetchedContent` → `(Skill, list[Source])` via an `LLMProvider`.

## API

```python
def distill(
    content: FetchedContent,
    *,
    provider: LLMProvider,
    now: datetime | None = None,   # injectable clock for tests
) -> tuple[Skill, list[Source]]: ...
```

## Behavior

- Concatenates every `Page.body` decoded as UTF-8 (with `errors="replace"`)
  into one source-text blob. Pages are separated by:

  ```
  --- next page: <url> ---
  ```

  so the LLM sees the boundaries.
- The `source_url` passed to the provider is `content.pages[0].url`
  (the entry point of the chain).
- Calls `provider.extract_draft(source_url=..., source_text=...)`.
- For each page, mints a `Source`:
  - `id = "src-" + page.sha256[:6]`
  - `url = page.url`
  - `license = "unknown"` (change #4 wires real detection)
  - `fetched_at = page.fetched_at`
  - `sha256 = page.sha256`
  - `contribution = "page {i} of {n}"` for chains, `"single page"` for one
- Builds a `Skill`:
  - `name`, `description`, `body` from the `DistilledDraft`
  - `version = 1`
  - `sources = [SourceRef(id=s.id) for s in sources]`
  - `judge_score = None`
  - `created = (now or datetime.now(UTC)).date()`
- Returns `(skill, sources)`. The caller is responsible for writing them
  via `storage.write_skill(..., draft=True)` and `storage.write_sources`.

## Failure modes

- If the provider returns a `DistilledDraft` whose `name` collides with
  an existing skill on disk, the distiller does **not** check — that's
  the CLI's job (it decides whether to suffix, prompt, or refuse).
- Anything the provider raises bubbles unchanged.

## Non-goals

- No quality scoring (change #3).
- No source license detection (change #4).
- No merging with an existing skill (change #6).
