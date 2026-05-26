# add-release

## Why

Today a forge instance is a live, ever-mutating directory: `skills/`
get edited, `sources.yml` accumulates new fetches, drafts get promoted,
peers subscribe and pull updates. Useful for the curator. Useless for
anyone downstream who wants to say "give me v3 of the Mark bundle"
and be confident they got the exact same bytes I had on 2026-05-26.

l-gevity solved this by tagging GitHub Releases on their skills repo
(`starterpack` tag), so a consumer can `git checkout v2025-11-skills`
and get a frozen tree. The mechanism — Git tags + release notes — is
already battle-tested by half the open-source world. We should adopt
it, but anchored to skill-forge's notion of "bundle" so a release
isn't "whatever was in the repo at HEAD" but "this signed manifest
of these N skills at these N signatures".

## What

- `forge release create <version> [--message MSG] [--include slug,slug,...]`
  - Default: every promoted (non-draft) skill in the instance.
  - With `--include`: just those slugs.
  - Computes a manifest: `{version, created, skills: [{slug, sha256,
    signature}], identity_fingerprint}`.
  - Writes `releases/<version>.yml` (manifest) and
    `releases/<version>.tar.gz` (the SKILL.md + sources.yml for every
    included skill, plus the manifest).
  - Signs the manifest with the active identity (Ed25519, reuses
    change #1).
  - Appends a `released` RunEvent to the audit trail.
- `forge release list` — show every release in chronological order
  with their version, fingerprint, and skill count.
- `forge release verify <version>` — re-hash every file in the tarball
  and check it matches the manifest; verify the manifest signature
  against the identity it claims.
- `forge release publish <version>` (optional, sub-only) — if the
  instance has a configured `github_repo` (peers.yml or a new
  `release_target`), `gh release create` with the tarball as an asset.

## Scope

- `src/skill_forge/release.py` (~250 LoC ceiling) with `create_release`,
  `list_releases`, `verify_release`.
- CLI: `forge release` sub-typer with `create`, `list`, `verify`,
  `publish`.
- `releases/` directory in the instance root.
- New `Release` and `ReleaseManifest` Pydantic models in `models.py`.
- Tests for: manifest build (deterministic ordering by slug), tarball
  round-trip, signature verification, version collision rejection,
  empty-instance rejection.
- Spec deltas in `openspec/specs/release-bundles/spec.md`.

## Out of scope

- Auto-bumping versions. The user supplies the version string.
- Hosting releases anywhere except local + GitHub (no S3, no IPFS).
- Cross-instance verification (signing across multiple identities).
  Releases are signed by the instance owner only.
- Diffing two releases. Maybe later, but YAGNI for v1.

## Open questions

- Version string format: free-form (`v2026-05-26`, `1.0.0`) or
  enforced semver? **Decision: free-form, but slugify** —
  `SLUG_RE.match(version)` so we can safely use it as a filename.
- Tarball content layout: flat (`alpha-skill.SKILL.md`) or
  nested (`skills/alpha-skill/SKILL.md`)?  **Decision: nested,
  mirroring the instance layout, so a consumer can `tar xzf` directly
  into a fresh instance root and have it work.**

## Acceptance criteria

1. `forge release create v1` on an instance with 3 promoted skills
   produces `releases/v1.yml` and `releases/v1.tar.gz`; the tarball
   contains exactly 3 nested skill directories plus the manifest.
2. `forge release verify v1` returns success on the just-created
   release; tampering with a single byte in the tarball causes it
   to fail with a clear message naming the corrupted file.
3. Re-running `forge release create v1` rejects the duplicate
   version (unless `--force`).
4. `forge release list` shows the release with fingerprint and
   skill count.
5. The manifest signature verifies against the active identity's
   public key.

## References

- l-gevity's release pattern: https://github.com/l-gevity/l-gevity-skills/releases
- Change #1 (add-instance-identity) — Ed25519 signing primitives reused here.
