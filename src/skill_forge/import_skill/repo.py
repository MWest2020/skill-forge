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

import yaml

from skill_forge.identity import Identity
from skill_forge.models import Skill, Source

from .importer import SkillImportError, import_file

_GITHUB_URL_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/?#]+)")


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

    imported: list[Skill] = []
    skipped: list[tuple[str, str]] = []
    for path in skill_paths:
        blob_url = f"https://github.com/{owner}/{repo}/blob/{actual_ref}/{path}"
        try:
            content = _fetch_file_content(owner, repo, path, actual_ref)
        except RepoImportError as exc:
            skipped.append((path, str(exc)))
            continue

        # External SKILL.md (e.g. Claude Code's `.claude/skills/*/SKILL.md`
        # format) often has minimal frontmatter — just `name` + `description`.
        # Our Skill model requires version, created, sources. Inject sane
        # defaults so the foreign file parses without us needing to loosen
        # the model. The injected Source points at the GitHub blob URL.
        normalized = _normalize_external_skill_md(content, blob_url=blob_url)
        staged = root / ".tmp" / "import-repo" / path.replace("/", "__")
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(normalized, encoding="utf-8")
        try:
            skill, sources = import_file(
                root,
                staged,
                identity=identity,
                origin_tag=origin_tag or f"external/{owner}/{repo}",
            )
        except SkillImportError as exc:
            skipped.append((path, exc.reason))
            continue
        finally:
            # Don't leave temp files around — sources.yml records the real
            # GitHub URL below, not the temp path.
            staged.unlink(missing_ok=True)

        _rewrite_source_url(root, skill, sources, owner, repo, actual_ref, path)
        imported.append(skill)

    # Clean up the temp dir if empty.
    tmp_dir = root / ".tmp" / "import-repo"
    if tmp_dir.is_dir() and not any(tmp_dir.iterdir()):
        tmp_dir.rmdir()

    return RepoImportResult(imported=imported, skipped=skipped)


# --- internals ----------------------------------------------------------------


_KNOWN_SKILL_FIELDS = {
    "name", "description", "version", "sources", "judge_score",
    "created", "origin", "signature", "visibility",
}


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
    frontmatter_text = fm_match.group(1)
    body = text[fm_match.end():]
    try:
        fm: dict[str, object] = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError:
        return text
    if not isinstance(fm, dict):
        return text

    # Strip unknown fields. The foreign file's body still references them
    # via prose if they mattered; we just don't surface them as structured
    # metadata in our schema.
    fm = {k: v for k, v in fm.items() if k in _KNOWN_SKILL_FIELDS}

    if "version" not in fm:
        fm["version"] = 1
    if "created" not in fm:
        fm["created"] = datetime.now(UTC).date().isoformat()
    if "sources" not in fm or not fm["sources"]:
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        fm["sources"] = [{"id": f"src-{sha[:6]}"}]

    body = _ensure_source_section(body, blob_url)
    new_fm = yaml.safe_dump(fm, sort_keys=True)
    return f"---\n{new_fm}---\n\n{body.lstrip(chr(10))}"


def _ensure_source_section(body: str, url: str) -> str:
    if "## Source" in body:
        return body
    trailer = f"\n## Source\n\n- {url}\n"
    if not body.endswith("\n"):
        body += "\n"
    return body + trailer


def _parse_github_url(url: str) -> tuple[str, str]:
    match = _GITHUB_URL_RE.match(url.strip())
    if not match:
        raise RepoImportError(
            f"not a GitHub repo URL: {url!r} (expected https://github.com/<owner>/<repo>)"
        )
    owner = match.group(1)
    repo = match.group(2).removesuffix(".git")
    return owner, repo


def _default_branch(owner: str, repo: str) -> str:
    result = _gh_api(f"repos/{owner}/{repo}", "--jq", ".default_branch")
    branch = result.strip()
    if not branch:
        raise RepoImportError(f"could not determine default branch for {owner}/{repo}")
    return branch


def _walk_for_skill_md(owner: str, repo: str, ref: str) -> list[str]:
    """Return every tree path ending in SKILL.md."""
    raw = _gh_api(f"repos/{owner}/{repo}/git/trees/{ref}?recursive=1")
    data = json.loads(raw)
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
    raw = _gh_api(f"repos/{owner}/{repo}/contents/{path}?ref={ref}")
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
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RepoImportError("`gh` CLI not found; install from https://cli.github.com/") from exc
    except subprocess.TimeoutExpired as exc:
        raise RepoImportError(f"`gh api {endpoint}` timed out") from exc
    if result.returncode != 0:
        raise RepoImportError(
            f"`gh api {endpoint}` exited {result.returncode}: {result.stderr.strip()[:300]}"
        )
    return result.stdout


def _rewrite_source_url(
    root: Path,
    skill: Skill,
    sources: list[Source],
    owner: str,
    repo: str,
    ref: str,
    path: str,
) -> None:
    """Replace the temp-file URL in sources.yml with the real GitHub blob URL."""
    from skill_forge.models import SourcesFile
    from skill_forge.storage import filesystem as storage

    blob_url = f"https://github.com/{owner}/{repo}/blob/{ref}/{path}"
    new_sources = [src.model_copy(update={"url": blob_url}) for src in sources]
    sources_file = storage.read_sources(root, skill.name)
    sources_file = sources_file.model_copy(update={"sources": new_sources})
    # Direct write (overwrite=True) — we just wrote this file via import_file.
    storage.write_sources(root, skill.name, sources_file, overwrite=True)
    # Repoint the skill's-own sources list IDs would be in-memory only;
    # tests verify via reading sources.yml back.
    del new_sources
    # The SourcesFile parameter binding suppresses an unused-import lint
    # when this branch is exercised — keep the import local.
    _ = SourcesFile
