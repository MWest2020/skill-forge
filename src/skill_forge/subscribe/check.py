"""check-updates: refetch every subscribed URL, diff sha256."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.extraction.fetcher import FetchError, fetch
from skill_forge.models import RunEvent

from .subscriptions import (
    Subscription,
    SubscriptionsFile,
    read_subscriptions,
    write_subscriptions,
)


@dataclass(frozen=True)
class CheckResult:
    slug: str
    url: str
    status: str  # "unchanged" | "changed" | "unreachable"
    new_sha256: str | None = None
    error: str | None = None


def check_updates(root: Path) -> list[CheckResult]:
    """Re-fetch every watched URL, compare sha256, update subscriptions.yml."""
    subs = read_subscriptions(root)
    if not subs.subscriptions:
        return []
    now = datetime.now(UTC)
    run_id = next_run_id(root)
    results: list[CheckResult] = []
    new_entries: list[Subscription] = []
    for sub in subs.subscriptions:
        result = _check_one(sub, now=now)
        results.append(result)
        if result.status == "changed" and result.new_sha256 is not None:
            new_entries.append(
                sub.model_copy(update={"last_sha256": result.new_sha256, "last_checked": now})
            )
        elif result.status == "unchanged":
            new_entries.append(sub.model_copy(update={"last_checked": now}))
        else:
            new_entries.append(sub)  # leave unchanged on unreachable
        append_run_event(
            root,
            RunEvent(
                run_id=run_id,
                event="checked",
                timestamp=now,
                skill_slug=sub.slug,
                metadata={
                    "url": sub.url,
                    "status": result.status,
                    "changed": "true" if result.status == "changed" else "false",
                },
            ),
        )
    write_subscriptions(root, SubscriptionsFile(subscriptions=new_entries))
    return results


def _check_one(sub: Subscription, *, now: datetime) -> CheckResult:
    try:
        content = fetch(sub.url, follow_next=False)
    except FetchError as exc:
        return CheckResult(slug=sub.slug, url=sub.url, status="unreachable", error=str(exc))
    body = b"".join(page.body for page in content.pages)
    new_sha = hashlib.sha256(body).hexdigest()
    if new_sha == sub.last_sha256:
        return CheckResult(slug=sub.slug, url=sub.url, status="unchanged")
    return CheckResult(slug=sub.slug, url=sub.url, status="changed", new_sha256=new_sha)
