"""Tests for forge subscribe + check-updates — change #9."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.models import Source, SourcesFile
from skill_forge.storage import filesystem as fs
from skill_forge.subscribe import (
    Subscription,
    SubscriptionError,
    add_subscription,
    check_updates,
    list_subscriptions,
    remove_subscription,
)
from skill_forge.subscribe import check as check_mod

runner = CliRunner()
_NOW = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _sub(slug: str = "demo", last_sha256: str = "a" * 64) -> Subscription:
    return Subscription(
        slug=slug,
        url="https://example.com/article",
        last_sha256=last_sha256,
        last_checked=_NOW,
    )


def _seed_skill_with_http_source(tmp_path: Path, slug: str = "demo") -> str:
    """Create the minimum disk state needed for `forge subscribe <slug>` to work."""
    from datetime import date

    from skill_forge.models import Skill, SourceRef

    body_bytes = b"<html>article body</html>"
    sha = hashlib.sha256(body_bytes).hexdigest()
    fs.write_skill(
        tmp_path,
        Skill(
            name=slug,
            description="Use when X.",
            version=1,
            sources=[SourceRef(id="src-abc123")],
            created=date(2026, 5, 26),
            body="## When to use\nX\n## Procedure\nY\n## Failure modes\nZ\n## Source\n- https://example.com/article\n",
        ),
        draft=False,
    )
    fs.write_sources(
        tmp_path,
        slug,
        SourcesFile(
            slug=slug,
            sources=[
                Source(
                    id="src-abc123",
                    url="https://example.com/article",
                    license="unknown",
                    fetched_at=_NOW,
                    sha256=sha,
                    contribution="single page",
                )
            ],
        ),
    )
    return sha


# --- Subscription model + CRUD ----------------------------------------------


def test_subscription_round_trip(tmp_path: Path) -> None:
    add_subscription(tmp_path, _sub())
    subs = list_subscriptions(tmp_path)
    assert len(subs) == 1
    assert subs[0].slug == "demo"


def test_subscription_rejects_non_http() -> None:
    with pytest.raises(ValueError, match="http"):
        Subscription(
            slug="demo",
            url="local-author:forge-12345678",
            last_sha256="a" * 64,
            last_checked=_NOW,
        )


def test_subscription_duplicate_raises(tmp_path: Path) -> None:
    add_subscription(tmp_path, _sub())
    with pytest.raises(SubscriptionError, match="already subscribed"):
        add_subscription(tmp_path, _sub())


def test_remove_subscription(tmp_path: Path) -> None:
    add_subscription(tmp_path, _sub())
    assert remove_subscription(tmp_path, "demo") is True
    assert remove_subscription(tmp_path, "demo") is False


# --- check_updates -----------------------------------------------------------


def test_check_updates_reports_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sha = _seed_skill_with_http_source(tmp_path)
    add_subscription(tmp_path, _sub(last_sha256=sha))

    # Mock fetch to return the same bytes
    fake_content = MagicMock()
    fake_page = MagicMock()
    fake_page.body = b"<html>article body</html>"
    fake_content.pages = (fake_page,)
    monkeypatch.setattr(check_mod, "fetch", MagicMock(return_value=fake_content))

    results = check_updates(tmp_path)
    assert len(results) == 1
    assert results[0].status == "unchanged"


def test_check_updates_detects_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    add_subscription(tmp_path, _sub(last_sha256="a" * 64))  # subscribed with old sha
    fake_content = MagicMock()
    fake_page = MagicMock()
    fake_page.body = b"<html>new content</html>"
    fake_content.pages = (fake_page,)
    monkeypatch.setattr(check_mod, "fetch", MagicMock(return_value=fake_content))

    results = check_updates(tmp_path)
    assert results[0].status == "changed"
    assert results[0].new_sha256 == hashlib.sha256(b"<html>new content</html>").hexdigest()

    # last_sha256 in subscriptions.yml was updated to the new value
    subs = list_subscriptions(tmp_path)
    assert subs[0].last_sha256 == results[0].new_sha256


def test_check_updates_handles_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    add_subscription(tmp_path, _sub())
    from skill_forge.extraction.fetcher import FetchFailedError

    monkeypatch.setattr(
        check_mod,
        "fetch",
        MagicMock(side_effect=FetchFailedError("https://example.com/article", 503)),
    )
    results = check_updates(tmp_path)
    assert results[0].status == "unreachable"
    # Subscription's last_sha256 untouched
    subs = list_subscriptions(tmp_path)
    assert subs[0].last_sha256 == "a" * 64


def test_check_updates_appends_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    add_subscription(tmp_path, _sub())
    fake_content = MagicMock()
    fake_page = MagicMock()
    fake_page.body = b"new"
    fake_content.pages = (fake_page,)
    monkeypatch.setattr(check_mod, "fetch", MagicMock(return_value=fake_content))

    check_updates(tmp_path)
    run_files = sorted((tmp_path / "runs").glob("*.jsonl"))
    assert len(run_files) == 1
    event = json.loads(run_files[0].read_text().splitlines()[0])
    assert event["event"] == "checked"
    assert event["metadata"]["status"] == "changed"


# --- CLI ---------------------------------------------------------------------


def test_cli_subscribe_from_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_skill_with_http_source(tmp_path)
    result = runner.invoke(app, ["subscribe", "demo", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "Subscribed: demo" in result.output


def test_cli_subscribe_refuses_local_author(
    tmp_path: Path,
) -> None:
    from datetime import date

    from skill_forge.models import Skill, SourceRef

    fs.write_skill(
        tmp_path,
        Skill(
            name="local-only",
            description="Use when X.",
            version=1,
            sources=[SourceRef(id="src-abc123")],
            created=date(2026, 5, 26),
            body="## When to use\nX\n## Procedure\nY\n## Failure modes\nZ\n## Source\n- author\n",
        ),
        draft=False,
    )
    fs.write_sources(
        tmp_path,
        "local-only",
        SourcesFile(
            slug="local-only",
            sources=[
                Source(
                    id="src-abc123",
                    url="local-author:forge-12345678",
                    license="unknown",
                    fetched_at=_NOW,
                    sha256="b" * 64,
                    contribution="manual",
                )
            ],
        ),
    )
    result = runner.invoke(app, ["subscribe", "local-only", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "no http(s) source" in (result.stderr or result.output)


def test_cli_subscribe_list(tmp_path: Path) -> None:
    add_subscription(tmp_path, _sub())
    result = runner.invoke(app, ["subscribe", "--list", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "demo" in result.output


def test_cli_subscribe_remove(tmp_path: Path) -> None:
    add_subscription(tmp_path, _sub())
    result = runner.invoke(app, ["subscribe", "demo", "--remove", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "Unsubscribed" in result.output
