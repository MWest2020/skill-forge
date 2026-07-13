"""Lock-in test: `_KNOWN_SKILL_FIELDS` must mirror the Skill model.

Without this test, adding a new field to Skill silently drops it on
import because `normalize_skill_md` strips anything not in the whitelist.
"""

from __future__ import annotations

from skill_forge.import_skill.normalize import _KNOWN_SKILL_FIELDS
from skill_forge.models import Skill


def test_known_skill_fields_matches_model() -> None:
    """The whitelist must equal Skill's frontmatter fields exactly.

    `body` is excluded because it's content, not frontmatter — it
    survives the normalizer untouched. Fields with an alias (e.g.
    `allowed-tools`) appear in frontmatter under the alias, so the
    whitelist carries the alias, not the Python name.
    """
    expected = {
        field.alias or name
        for name, field in Skill.model_fields.items()
        if name != "body"
    }
    assert _KNOWN_SKILL_FIELDS == expected, (
        f"drift detected: Skill fields = {expected}, "
        f"whitelist = {_KNOWN_SKILL_FIELDS}. "
        f"Missing from whitelist: {expected - _KNOWN_SKILL_FIELDS}. "
        f"Extra in whitelist: {_KNOWN_SKILL_FIELDS - expected}."
    )
