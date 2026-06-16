"""Shared SKILL.md normalization.

Adapts a foreign/vanilla SKILL.md to the Skill schema so every import path —
`import`, `import-dir`, `import-repo` — and `advise` accept the same inputs.
The field whitelist lives here (single source of truth; the drift test pins it
to the Skill model).
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

import yaml

_KNOWN_SKILL_FIELDS = {
    "name", "description", "version", "sources", "judge_score",
    "created", "origin", "signature", "visibility", "tags",
}


def normalize_skill_md(content: str, *, source_url: str | None = None) -> str:
    """Keep only known frontmatter fields and inject the required ones
    (version, created, sources) when missing, so a vanilla `name`+`description`
    skill parses. The body is untouched — except that when `source_url` is given
    a `## Source` section is ensured (the provenance invariant for repo
    imports). Pass `source_url=None` for local imports, which have no canonical
    URL and should not get a synthetic one.

    Returns the input unchanged if it has no parseable YAML frontmatter (the
    strict parser then reports the real problem).
    """
    fm_match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    if not fm_match:
        return content
    body = content[fm_match.end():]
    try:
        loaded = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError:
        return content
    if not isinstance(loaded, dict):
        return content

    fm: dict[str, object] = {k: v for k, v in loaded.items() if k in _KNOWN_SKILL_FIELDS}
    if "version" not in fm:
        fm["version"] = 1
    if "created" not in fm:
        fm["created"] = datetime.now(UTC).date().isoformat()
    if "sources" not in fm or not fm["sources"]:
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        fm["sources"] = [{"id": f"src-{sha[:6]}"}]

    if source_url is not None:
        body = _ensure_source_section(body, source_url)
    return f"---\n{yaml.safe_dump(fm, sort_keys=True)}---\n\n{body.lstrip(chr(10))}"


def _ensure_source_section(body: str, url: str) -> str:
    if "## Source" in body:
        return body
    if not body.endswith("\n"):
        body += "\n"
    return body + f"\n## Source\n\n- {url}\n"
