"""Watch source URLs for changes; re-fetch + diff sha256 on demand."""

from .check import CheckResult, check_updates
from .subscriptions import (
    Subscription,
    SubscriptionError,
    SubscriptionsFile,
    add_subscription,
    list_subscriptions,
    read_subscriptions,
    remove_subscription,
    write_subscriptions,
)

__all__ = [
    "CheckResult",
    "Subscription",
    "SubscriptionError",
    "SubscriptionsFile",
    "add_subscription",
    "check_updates",
    "list_subscriptions",
    "read_subscriptions",
    "remove_subscription",
    "write_subscriptions",
]
