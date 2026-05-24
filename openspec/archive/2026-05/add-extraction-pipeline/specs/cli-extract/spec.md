# Spec — CLI `forge extract`

## Signature

```
forge extract <url> [--all] [--max-pages N] [--root PATH]
```

- `url`: positional. `http(s)://...` or `file://...`.
- `--all`: follow `rel="next"` chains. Off by default.
- `--max-pages N`: cap pages followed in the chain. Defaults to the
  `discovery.max_pages` (or fallback 50) from `config/default.yml`.
- `--root PATH`: project root, like `ls` and `show`. Defaults to cwd.

## Behavior

1. Build an `AnthropicProvider` from env (`ANTHROPIC_API_KEY` required;
   exit 2 with a clear message if missing).
2. Call `fetcher.fetch(url, follow_next=all, max_pages=max_pages)`.
3. Call `distiller.distill(content, provider=provider)`.
4. Write the skill to `skills/_draft/{slug}/SKILL.md` (always draft;
   promotion is change #3). If the slug already exists in `skills/` or
   `skills/_draft/`, suffix with `-N` until free.
5. Write `sources/{slug}.yml`.
6. Print a summary to stdout:

   ```
   Drafted: <slug>
     Pages fetched: 3
     Draft path:   skills/_draft/<slug>/SKILL.md
     Sources:      sources/<slug>.yml
     Blocked:      <url>  (cross-origin) — only if non-empty
   ```

## Exit codes

- `0` — success.
- `1` — fetch failed (robots-blocked, HTTP error, file not found).
- `2` — config error (missing API key).
- `3` — provider error (rate limit, invalid response).

## Non-goals

- No live promotion. Drafts only.
- No interactive confirmation on slug collision (auto-suffix).
- No `--out` flag to redirect output — the project structure is fixed.
