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

from skill_forge.audit import append_run_event, next_run_id
from skill_forge.identity import Identity
from skill_forge.import_skill.normalize import normalize_skill_md
from skill_forge.models import RunEvent, Skill, Source, SourcesFile
from skill_forge.storage import filesystem as storage

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
    blob_paths = _walk_blobs(owner, repo, actual_ref)
    skill_paths = sorted(p for p in blob_paths if p.endswith("SKILL.md"))
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
        normalized = normalize_skill_md(content, source_url=blob_url)
        try:
            skill = _import_normalized(
                root,
                normalized=normalized, raw_sha256=raw_sha, blob_url=blob_url,
                origin_tag=effective_tag, identity=identity, run_id=run_id,
            )
        except (ValueError, OSError) as exc:
            skipped.append((path, str(exc)))
            continue
        skipped.extend(
            _fetch_bundled_files(
                root, owner=owner, repo=repo, ref=actual_ref,
                skill_path=path, slug=skill.name, blob_paths=blob_paths,
            )
        )
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


def _walk_blobs(owner: str, repo: str, ref: str) -> list[str]:
    """Return every blob path in the tree."""
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
        if isinstance(path, str):
            paths.append(path)
    return sorted(paths)


# Helper dirs a skill may bundle next to its SKILL.md. Copied verbatim into
# the draft so body references like `scripts/foo.py` resolve locally.
_BUNDLED_DIRS = ("scripts", "references", "assets")
_MAX_BUNDLED_FILES = 40


def _fetch_bundled_files(
    root: Path,
    *,
    owner: str,
    repo: str,
    ref: str,
    skill_path: str,
    slug: str,
    blob_paths: list[str],
) -> list[tuple[str, str]]:
    """Copy the skill's sibling scripts/references/assets into its draft dir.

    Per-file failures never fail the skill import — they come back as
    (path, reason) skip entries.
    """
    base = skill_path.removesuffix("SKILL.md")
    prefixes = tuple(f"{base}{d}/" for d in _BUNDLED_DIRS)
    bundled = [p for p in blob_paths if p.startswith(prefixes)]
    skipped: list[tuple[str, str]] = []
    if len(bundled) > _MAX_BUNDLED_FILES:
        skipped.extend(
            (p, f"bundled-file cap ({_MAX_BUNDLED_FILES}) reached")
            for p in bundled[_MAX_BUNDLED_FILES:]
        )
        bundled = bundled[:_MAX_BUNDLED_FILES]
    draft_dir = root / "skills" / "_draft" / slug
    for path in bundled:
        try:
            payload = _fetch_file_bytes(owner, repo, path, ref)
        except RepoImportError as exc:
            skipped.append((path, str(exc)))
            continue
        target = draft_dir / path.removeprefix(base)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return skipped


def _fetch_file_bytes(owner: str, repo: str, path: str, ref: str) -> bytes:
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
        return base64.b64decode(content)
    except ValueError as exc:
        raise RepoImportError(f"{path}: decode failed: {exc}") from exc


def _fetch_file_content(owner: str, repo: str, path: str, ref: str) -> str:
    try:
        return _fetch_file_bytes(owner, repo, path, ref).decode("utf-8")
    except UnicodeDecodeError as exc:
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
