"""Tests for skill_forge.extraction.fetcher — change #2."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pytest_httpserver import HTTPServer

from skill_forge.extraction.fetcher import (
    FetchFailedError,
    RobotsBlockedError,
    fetch,
)

# Default robots.txt: allow everything.
_ROBOTS_ALLOW_ALL = "User-agent: *\nAllow: /\n"


def _serve_robots(httpserver: HTTPServer, body: str = _ROBOTS_ALLOW_ALL) -> None:
    httpserver.expect_request("/robots.txt").respond_with_data(body, content_type="text/plain")


# --- file:// ------------------------------------------------------------------


def test_fetch_file_scheme(tmp_path: Path) -> None:
    target = tmp_path / "sample.html"
    target.write_text("<html><body><h1>Hi</h1></body></html>", encoding="utf-8")
    content = fetch(f"file://{target}")
    assert len(content.pages) == 1
    page = content.pages[0]
    assert page.url == f"file://{target}"
    assert b"<h1>Hi</h1>" in page.body
    assert page.sha256 == hashlib.sha256(page.body).hexdigest()
    assert page.fetched_at.tzinfo is not None


def test_fetch_file_ignores_follow_next(tmp_path: Path) -> None:
    target = tmp_path / "p.html"
    target.write_text('<link rel="next" href="http://x/2">', encoding="utf-8")
    content = fetch(f"file://{target}", follow_next=True)
    assert len(content.pages) == 1
    assert content.blocked == ()


# --- http: single page --------------------------------------------------------


def test_fetch_http_single_page(httpserver: HTTPServer) -> None:
    _serve_robots(httpserver)
    httpserver.expect_request("/one").respond_with_data(
        "<html><body>page one</body></html>", content_type="text/html"
    )
    content = fetch(httpserver.url_for("/one"))
    assert len(content.pages) == 1
    assert b"page one" in content.pages[0].body
    assert content.pages[0].content_type == "text/html"


def test_fetch_http_404_raises(httpserver: HTTPServer) -> None:
    _serve_robots(httpserver)
    httpserver.expect_request("/missing").respond_with_data("nope", status=404)
    with pytest.raises(FetchFailedError) as exc:
        fetch(httpserver.url_for("/missing"))
    assert exc.value.status == 404


def test_fetch_robots_disallow(httpserver: HTTPServer) -> None:
    _serve_robots(httpserver, "User-agent: *\nDisallow: /forbidden\n")
    httpserver.expect_request("/forbidden").respond_with_data("secret")
    with pytest.raises(RobotsBlockedError):
        fetch(httpserver.url_for("/forbidden"))


def test_fetch_robots_missing_treats_as_allow(httpserver: HTTPServer) -> None:
    # No /robots.txt route; server will 404 it.
    httpserver.expect_request("/page").respond_with_data("hi")
    content = fetch(httpserver.url_for("/page"))
    assert len(content.pages) == 1


# --- http: rel=next follow ----------------------------------------------------


def test_follow_next_link_in_head(httpserver: HTTPServer) -> None:
    _serve_robots(httpserver)
    next_url = httpserver.url_for("/p2")
    httpserver.expect_request("/p1").respond_with_data(
        f'<html><head><link rel="next" href="{next_url}"></head><body>1</body></html>',
        content_type="text/html",
    )
    httpserver.expect_request("/p2").respond_with_data(
        "<html><body>2</body></html>", content_type="text/html"
    )
    content = fetch(httpserver.url_for("/p1"), follow_next=True)
    assert [p.url.rsplit("/", 1)[-1] for p in content.pages] == ["p1", "p2"]


def test_follow_next_anchor_in_body(httpserver: HTTPServer) -> None:
    _serve_robots(httpserver)
    httpserver.expect_request("/p1").respond_with_data(
        f'<html><body>1<a rel="next" href="{httpserver.url_for("/p2")}">go</a></body></html>',
        content_type="text/html",
    )
    httpserver.expect_request("/p2").respond_with_data(
        "<html><body>2</body></html>", content_type="text/html"
    )
    content = fetch(httpserver.url_for("/p1"), follow_next=True)
    assert len(content.pages) == 2


def test_follow_next_stops_at_max_pages(httpserver: HTTPServer) -> None:
    _serve_robots(httpserver)
    for i in range(1, 6):
        next_url = httpserver.url_for(f"/p{i + 1}")
        httpserver.expect_request(f"/p{i}").respond_with_data(
            f'<link rel="next" href="{next_url}">page {i}',
            content_type="text/html",
        )
    httpserver.expect_request("/p6").respond_with_data("end", content_type="text/html")
    content = fetch(httpserver.url_for("/p1"), follow_next=True, max_pages=3)
    assert len(content.pages) == 3
    assert content.blocked == ()


def test_follow_next_blocks_cross_origin(httpserver: HTTPServer) -> None:
    _serve_robots(httpserver)
    httpserver.expect_request("/p1").respond_with_data(
        '<link rel="next" href="https://other.example.com/p2">one',
        content_type="text/html",
    )
    content = fetch(httpserver.url_for("/p1"), follow_next=True)
    assert len(content.pages) == 1
    assert content.blocked == ("https://other.example.com/p2",)


def test_follow_next_detects_loop(httpserver: HTTPServer) -> None:
    _serve_robots(httpserver)
    httpserver.expect_request("/p1").respond_with_data(
        f'<link rel="next" href="{httpserver.url_for("/p2")}">',
        content_type="text/html",
    )
    httpserver.expect_request("/p2").respond_with_data(
        f'<link rel="next" href="{httpserver.url_for("/p1")}">',
        content_type="text/html",
    )
    content = fetch(httpserver.url_for("/p1"), follow_next=True)
    assert len(content.pages) == 2
    assert content.blocked[0].endswith("/p1")


def test_follow_next_stops_when_no_next(httpserver: HTTPServer) -> None:
    _serve_robots(httpserver)
    httpserver.expect_request("/only").respond_with_data(
        "<html><body>nothing here</body></html>", content_type="text/html"
    )
    content = fetch(httpserver.url_for("/only"), follow_next=True)
    assert len(content.pages) == 1
    assert content.blocked == ()
