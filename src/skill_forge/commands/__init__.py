"""CLI command groups.

Importing this package has the side effect of registering every command on the
shared ``skill_forge.cli.app`` (and its ``identity`` / ``lineage`` sub-apps).
``skill_forge.cli`` imports it at the bottom, after ``app`` and the shared
helpers exist, so the back-import each module does resolves cleanly.
"""

from __future__ import annotations

from skill_forge.commands import (  # noqa: F401  (imported for registration side effects)
    identity,
    imports,
    inspect,
    lifecycle,
    lineage,
    refine,
    serve,
)
