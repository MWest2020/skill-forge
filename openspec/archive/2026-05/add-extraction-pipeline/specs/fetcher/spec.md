# Spec — fetcher

Pure I/O over the web. No LLM, no business logic.

## Types

```python
@dataclass(frozen=True)
class Page:
    url: str
    body: bytes          # raw response body (HTML or whatever the server sent)
    content_type: str    # from response, lowercased, no params
    fetched_at: datetime # tz-aware UTC
    sha256: str          # of body

@dataclass(frozen=True)
class FetchedContent:
    pages: tuple[Page, ...]  # always >=1
    blocked: tuple[str, ...] # URLs the chain wanted to visit but was denied
```

## API

```python
def fetch(
    url: str,
    *,
    follow_next: bool = False,
    max_pages: int = 50,
    user_agent: str = DEFAULT_UA,
) -> FetchedContent: ...
```

`DEFAULT_UA` matches the `discovery.user_agent` setting in
`config/default.yml`.

## Behavior

- `file://` URLs: read from disk, no robots check, no pagination follow
  (even with `follow_next=True`). Used for tests and offline fixtures.
- `http(s)://` URLs:
  - Fetch `<origin>/robots.txt` once per origin and cache for the run.
    Parse with `urllib.robotparser`. If the path is disallowed for our
    UA, raise `RobotsBlocked(url)`. Do **not** silently skip — caller
    decides what to do.
  - `GET` the URL with `httpx`, timeout 15s, `follow_redirects=True`,
    max redirect chain 5. Send `User-Agent: {user_agent}`.
  - On any 4xx/5xx response: raise `FetchFailed(url, status)`.
- When `follow_next=True`:
  - Parse the response as HTML. Find the next URL in this order:
    1. `<link rel="next" href="...">` in `<head>`
    2. `<a rel="next" href="...">` anywhere
  - Resolve relative URLs against the current page URL.
  - If no next link is found, stop with the pages collected so far.
  - If the next URL is on a **different origin** (scheme+host+port), stop
    and record it in `blocked`.
  - If the next URL was already visited in this chain, stop and record
    it in `blocked`.
  - If `len(pages) >= max_pages`, stop (no record in `blocked` — this is
    a configured cap, not a denial).
  - Each followed page goes through the same robots.txt check.
- Returns `FetchedContent` with all successfully-fetched pages in order.

## Failure modes

- `RobotsBlocked(url)` — robots.txt forbids the URL. Always the first
  page would raise this; following pages contribute to `blocked` instead.
- `FetchFailed(url, status)` — non-2xx response.
- `FetchTimeout(url)` — httpx timeout exceeded.
- File scheme: standard `FileNotFoundError` / `PermissionError` bubble up.

## Non-goals

- No JavaScript rendering. Static HTML only.
- No content extraction (no readability, no html→text). Raw bytes go to
  the distiller; Claude handles HTML directly.
- No retry-on-503. Operator can re-run.
