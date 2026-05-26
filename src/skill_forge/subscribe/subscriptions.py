"""subscriptions.yml at repo root — tracks watched source URLs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from skill_forge.models import SLUG_RE


class SubscriptionError(Exception):
    """Subscription-management errors."""


class Subscription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    url: str
    last_sha256: str
    last_checked: datetime

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.fullmatch(v):
            raise ValueError(f"Subscription.slug must be slug-shaped, got {v!r}")
        return v

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(
                f"Subscription.url must be http(s)://; got {v!r}. "
                "Local-author and federation sources aren't refetchable."
            )
        return v

    @field_validator("last_checked")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Subscription.last_checked must be timezone-aware")
        return v


class SubscriptionsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscriptions: list[Subscription] = []


def read_subscriptions(root: Path) -> SubscriptionsFile:
    path = _path(root)
    if not path.is_file():
        return SubscriptionsFile()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SubscriptionsFile(**data)


def write_subscriptions(root: Path, subs: SubscriptionsFile) -> Path:
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = subs.model_dump(mode="json")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def add_subscription(root: Path, sub: Subscription) -> None:
    subs = read_subscriptions(root)
    if any(s.slug == sub.slug for s in subs.subscriptions):
        raise SubscriptionError(f"{sub.slug!r} is already subscribed; remove first to re-subscribe")
    subs.subscriptions.append(sub)
    write_subscriptions(root, subs)


def remove_subscription(root: Path, slug: str) -> bool:
    subs = read_subscriptions(root)
    before = len(subs.subscriptions)
    subs.subscriptions = [s for s in subs.subscriptions if s.slug != slug]
    if len(subs.subscriptions) == before:
        return False
    write_subscriptions(root, subs)
    return True


def list_subscriptions(root: Path) -> list[Subscription]:
    return read_subscriptions(root).subscriptions


def _path(root: Path) -> Path:
    return root / "subscriptions.yml"
