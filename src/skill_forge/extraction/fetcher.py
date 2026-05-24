"""Fetch source content, with robots.txt + optional rel=next pagination.

Specs: openspec/changes/add-extraction-pipeline/specs/fetcher/spec.md
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

DEFAULT_UA = "skill-forge/0.1 (+https://github.com/MWest2020/skill-forge)"
DEFAULT_MAX_PAGES = 50
_TIMEOUT = httpx.Timeout(15.0)


@dataclass(frozen=True)
class Page:
    url: str
    body: bytes
    content_type: str
    fetched_at: datetime
    sha256: str


@dataclass(frozen=True)
class FetchedContent:
    pages: tuple[Page, ...]
    blocked: tuple[str, ...] = ()


class FetchError(Exception):
    """Base for all fetcher errors."""


class RobotsBlockedError(FetchError):
    def __init__(self, url: str) -> None:
        super().__init__(f"robots.txt forbids {url}")
        self.url = url


class FetchFailedError(FetchError):
    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"{url} returned HTTP {status}")
        self.url = url
        self.status = status


class FetchTimeoutError(FetchError):
    def __init__(self, url: str) -> None:
        super().__init__(f"timeout fetching {url}")
        self.url = url


def fetch(
    url: str,
    *,
    follow_next: bool = False,
    max_pages: int = DEFAULT_MAX_PAGES,
    user_agent: str = DEFAULT_UA,
) -> FetchedContent:
    """Fetch one page (or a rel=next chain). See spec for details."""
    if url.startswith("file://"):
        return _fetch_file(url)

    state = _ChainState(user_agent=user_agent, max_pages=max_pages)
    return state.run(url, follow_next=follow_next)


# --- internals ----------------------------------------------------------------


@dataclass
class _ChainState:
    user_agent: str
    max_pages: int
    visited: set[str] = field(default_factory=set)
    blocked: list[str] = field(default_factory=list)
    robots: dict[str, RobotFileParser] = field(default_factory=dict)

    def run(self, start_url: str, *, follow_next: bool) -> FetchedContent:
        with httpx.Client(
            timeout=_TIMEOUT,
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": self.user_agent},
        ) as client:
            pages: list[Page] = []
            current = start_url
            while True:
                if not self._robots_allows(client, current):
                    if not pages:
                        raise RobotsBlockedError(current)
                    self.blocked.append(current)
                    break
                page = self._fetch_one(client, current)
                pages.append(page)
                self.visited.add(_normalize(current))
                if not follow_next or len(pages) >= self.max_pages:
                    break
                next_url = _find_next(page.body, page.url)
                if next_url is None:
                    break
                if _normalize(next_url) in self.visited:
                    self.blocked.append(next_url)
                    break
                if not _same_origin(page.url, next_url):
                    self.blocked.append(next_url)
                    break
                current = next_url
        return FetchedContent(pages=tuple(pages), blocked=tuple(self.blocked))

    def _fetch_one(self, client: httpx.Client, url: str) -> Page:
        try:
            response = client.get(url)
        except httpx.TimeoutException as exc:
            raise FetchTimeoutError(url) from exc
        if response.status_code >= 400:
            raise FetchFailedError(url, response.status_code)
        body = response.content
        return Page(
            url=str(response.url),
            body=body,
            content_type=(response.headers.get("content-type") or "").split(";")[0].strip().lower(),
            fetched_at=datetime.now(UTC),
            sha256=hashlib.sha256(body).hexdigest(),
        )

    def _robots_allows(self, client: httpx.Client, url: str) -> bool:
        origin = _origin(url)
        if origin not in self.robots:
            self.robots[origin] = _load_robots(client, origin)
        return self.robots[origin].can_fetch(self.user_agent, url)


def _fetch_file(url: str) -> FetchedContent:
    path = Path(url.removeprefix("file://"))
    body = path.read_bytes()
    page = Page(
        url=url,
        body=body,
        content_type="text/html" if path.suffix.lower() in {".html", ".htm"} else "text/plain",
        fetched_at=datetime.now(UTC),
        sha256=hashlib.sha256(body).hexdigest(),
    )
    return FetchedContent(pages=(page,))


def _load_robots(client: httpx.Client, origin: str) -> RobotFileParser:
    parser = RobotFileParser()
    parser.set_url(f"{origin}/robots.txt")
    try:
        response = client.get(f"{origin}/robots.txt")
    except httpx.HTTPError:
        parser.parse([])
        return parser
    if response.status_code >= 400:
        parser.parse([])
    else:
        parser.parse(response.text.splitlines())
    return parser


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)


def _normalize(url: str) -> str:
    return urldefrag(url)[0]


_REL_NEXT_LINK_RE = re.compile(
    r'<link\s+[^>]*rel=["\']next["\'][^>]*>',
    re.IGNORECASE | re.DOTALL,
)
_REL_NEXT_A_RE = re.compile(
    r'<a\s+[^>]*rel=["\']next["\'][^>]*>',
    re.IGNORECASE | re.DOTALL,
)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def _find_next(body: bytes, base_url: str) -> str | None:
    """Return the next URL via rel="next" (link in head preferred over a)."""
    text = body.decode("utf-8", errors="replace")
    head_match = _REL_NEXT_LINK_RE.search(text)
    if head_match:
        href = _HREF_RE.search(head_match.group(0))
        if href:
            return str(urljoin(base_url, href.group(1)))
    parser = _NextLinkParser()
    try:
        parser.feed(text)
    except Exception:
        pass
    if parser.next_href:
        return str(urljoin(base_url, parser.next_href))
    return None


class _NextLinkParser(HTMLParser):
    """Find the first `<a rel="next" href="...">` in the document."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.next_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.next_href is not None or tag != "a":
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        rel_values = attr_map.get("rel", "").lower().split()
        if "next" in rel_values and attr_map.get("href"):
            self.next_href = attr_map["href"]
