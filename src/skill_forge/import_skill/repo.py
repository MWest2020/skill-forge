"""Bulk-import SKILL.md files from a GitHub repository tree.

Spec: openspec/changes/add-import-repo/proposal.md
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import yaml

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.identity import Identity
from skill_forge.models import RunEvent, Skill, Source, SourcesFile
from skill_forge.storage import filesystem as storage

_GITHUB_URL_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/?#]+)")
_KNOWN_SKILL_FIELDS = {
    "name", "description", "version", "sources", "judge_score",
    "created", "origin", "signature", "visibility",
}


@dataclass(frozen=True)
class RepoImportResult:
    imported: list[Skill]
    skipped: list[tuple[str, str]]  # (path, reason)


class RepoImportError(Exception):
    """Wraps gh CLI failures and URL parse errors during repo import."""


def import_github_repo(
    root: Path,
    repo_url: str,
    *,
    identity: Identity | None = None,
    origin_tag: str | None = None,
    ref: str | None = None,
    max_skills: int = 50,
) -> RepoImportResult:
    """Walk `repo_url`'s tree, import every SKILL.md found."""
    owner, repo = _parse_github_url(repo_url)
    actual_ref = ref or _default_branch(owner, repo)
    skill_paths = _walk_for_skill_md(owner, repo, actual_ref)
    if len(skill_paths) > max_skills:
        raise RepoImportError(
            f"{owner}/{repo} contains {len(skill_paths)} SKILL.md files; "
            f"max_skills={max_skills}. Raise the cap or narrow the ref."
        )

    effective_tag = origin_tag or f"external/{owner}/{repo}"
    run_id = next_run_id(root)
    imported: list[Skill] = []
    skipped: list[tuple[str, str]] = []
    for path in skill_paths:
        blob_url = f"https://github.com/{owner}/{repo}/blob/{actual_ref}/{path}"
        try:
            content = _fetch_file_content(owner, repo, path, actual_ref)
        except RepoImportError as exc:
            skipped.append((path, str(exc)))
            continue
        # Raw-bytes sha256 of the upstream file. This is what provenance
        # should record (so re-fetching the blob URL and hashing yields the
        # same value), NOT the post-normalization sha.
        raw_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        normalized = _normalize_external_skill_md(content, blob_url=blob_url)
        try:
            skill = _import_normalized(
                root,
                normalized=normalized, raw_sha256=raw_sha, blob_url=blob_url,
                origin_tag=effective_tag, identity=identity, run_id=run_id,
            )
        except (ValueError, OSError) as exc:
            skipped.append((path, str(exc)))
            continue
        imported.append(skill)

    return RepoImportResult(imported=imported, skipped=skipped)


# --- internals ----------------------------------------------------------------


def _import_normalized(
    root: Path,
    *,
    normalized: str,
    raw_sha256: str,
    blob_url: str,
    origin_tag: str,
    identity: Identity | None,
    run_id: str,
) -> Skill:
    """Parse normalized SKILL.md text and land it directly — no temp file.

    Differs from the regular `import_file` path: provenance carries the
    upstream blob URL and the raw-upstream sha256 (not the normalized
    sha), and the audit event references the blob URL, so both surfaces
    agree on where the bytes came from.
    """
    parsed = storage.parse_skill_text(normalized, Path("<github-repo-import>"))
    slug = storage.free_slug(root, parsed.name)
    if slug != parsed.name:
        parsed = parsed.model_copy(update={"name": slug})

    now = datetime.now(UTC)
    src = Source(
        id=f"src-{raw_sha256[:6]}",
        url=blob_url,
        license="unknown",
        fetched_at=now,
        sha256=raw_sha256,
        contribution=f"imported from {origin_tag}",
    )
    storage.write_skill(root, parsed, draft=True, identity=identity)
    storage.write_sources(root, slug, SourcesFile(slug=slug, sources=[src]))
    append_run_event(
        root,
        RunEvent(
            run_id=run_id,
            event="imported",
            timestamp=now,
            skill_slug=slug,
            metadata={"source_url": blob_url, "origin_tag": origin_tag},
        ),
    )
    return parsed


def _normalize_external_skill_md(content: str, *, blob_url: str) -> str:
    """Adapt a foreign SKILL.md to our Skill schema.

    Foreign files (e.g. Claude Code's `.claude/skills/*/SKILL.md`) often:
    - Lack our required fields (version, created, sources) → inject defaults.
    - Carry extra fields (aligned, allowed_tools, …) that our `extra="forbid"`
      model rejects → strip them at the import boundary. The body survives
      untouched.

    Body invariant from change #9: ensure a `## Source` section pointing
    at the GitHub blob URL.
    """
    text = content
    fm_match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not fm_match:
        return text
    body = text[fm_match.end():]
    try:
        fm: dict[str, object] = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError:
        return text
    if not isinstance(fm, dict):
        return text

    fm = {k: v for k, v in fm.items() if k in _KNOWN_SKILL_FIELDS}
    if "version" not in fm:
        fm["version"] = 1
    if "created" not in fm:
        fm["created"] = datetime.now(UTC).date().isoformat()
    if "sources" not in fm or not fm["sources"]:
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        fm["sources"] = [{"id": f"src-{sha[:6]}"}]

    body = _ensure_source_section(body, blob_url)
    return f"---\n{yaml.safe_dump(fm, sort_keys=True)}---\n\n{body.lstrip(chr(10))}"


def _ensure_source_section(body: str, url: str) -> str:
    if "## Source" in body:
        return body
    if not body.endswith("\n"):
        body += "\n"
    return body + f"\n## Source\n\n- {url}\n"


def _parse_github_url(url: str) -> tuple[str, str]:
    match = _GITHUB_URL_RE.match(url.strip())
    if not match:
        raise RepoImportError(
            f"not a GitHub repo URL: {url!r} (expected https://github.com/<owner>/<repo>)"
        )
    return match.group(1), match.group(2).removesuffix(".git")


def _default_branch(owner: str, repo: str) -> str:
    branch = _gh_api(f"repos/{owner}/{repo}", "--jq", ".default_branch").strip()
    if not branch:
        raise RepoImportError(
            f"could not determine default branch for {owner}/{repo} "
            f"(is the repo private? check `gh auth status`)"
        )
    return branch


def _walk_for_skill_md(owner: str, repo: str, ref: str) -> list[str]:
    """Return every tree path ending in SKILL.md."""
    raw = _gh_api(f"repos/{owner}/{repo}/git/trees/{ref}?recursive=1")
    data = json.loads(raw)
    if data.get("truncated"):
        raise RepoImportError(
            f"{owner}/{repo}@{ref}: GitHub tree response is truncated "
            "(>100k entries or >7MB). Pin to a sub-tree via --ref or narrow scope."
        )
    tree = data.get("tree", [])
    if not isinstance(tree, list):
        raise RepoImportError(f"{owner}/{repo}: malformed tree response")
    paths: list[str] = []
    for entry in tree:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "blob":
            continue
        path = entry.get("path", "")
        if isinstance(path, str) and path.endswith("SKILL.md"):
            paths.append(path)
    return sorted(paths)


def _fetch_file_content(owner: str, repo: str, path: str, ref: str) -> str:
    # URL-quote the path so filenames with ?/# don't break the query.
    quoted = quote(path, safe="/")
    raw = _gh_api(f"repos/{owner}/{repo}/contents/{quoted}?ref={ref}")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("type") != "file":
        raise RepoImportError(f"{path}: GitHub returned non-file content")
    encoding = data.get("encoding")
    content = data.get("content")
    if encoding != "base64" or not isinstance(content, str):
        raise RepoImportError(f"{path}: unexpected encoding {encoding!r}")
    try:
        return base64.b64decode(content).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise RepoImportError(f"{path}: decode failed: {exc}") from exc


def _gh_api(endpoint: str, *extra_args: str) -> str:
    try:
        result = subprocess.run(
            ["gh", "api", endpoint, *extra_args],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except FileNotFoundError as exc:
        raise RepoImportError(
            "`gh` CLI not found; install from https://cli.github.com/"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RepoImportError(f"`gh api {endpoint}` timed out") from exc
    if result.returncode != 0:
        raise RepoImportError(
            f"`gh api {endpoint}` exited {result.returncode}: "
            f"{result.stderr.strip()[:300]} (check `gh auth status`)"
        )
    return result.stdout
