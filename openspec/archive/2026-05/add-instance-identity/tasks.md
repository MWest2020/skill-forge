# Tasks — add-instance-identity

## Dependency

- [x] `uv add cryptography` — Ed25519 implementation (boring & audited choice over `pynacl`)

## Identity module (`src/skill_forge/identity.py`)

- [x] Failing test: `Identity.get_or_create(tmp_path)` persists keypair to `{home}/identity/`
- [x] `Identity` dataclass with `instance_id`, `public_key`, `private_key`, `home`
- [x] `get_or_create(home: Path)` — generate on first call, load on subsequent calls
- [x] `from_seed(home, seed)` — deterministic test helper
- [x] Instance ID format: `forge-<8-hex>` derived from `sha256(public_key_bytes)`
- [x] `sign(payload: bytes) -> str` returns base64 signature; `verify(payload, sig) -> bool`
- [x] Private key file mode `0600` (refuse to load otherwise, with actionable error)
- [x] `canonical_payload(skill) -> bytes` — JSON dump with sorted keys, excludes `signature` and `body`, includes `body_sha256`
- [x] `SignatureMismatchError` exception class

## Skill model (`src/skill_forge/models.py`)

- [x] Add `origin: str | None = None` (format `<instance_id>:<slug>:<version>`)
- [x] Add `signature: str | None = None` (base64-encoded Ed25519)
- [x] Round-trip preserves both fields when set; both default to `None` for backward compat
- [x] Body validator normalizes trailing newline — needed so sign-then-write-then-read produces the same `body_sha256`

## Storage hooks (`src/skill_forge/storage/filesystem.py`)

- [x] `write_skill(root, skill, *, draft, identity=None, overwrite=False)` — stamps `origin` + `signature` when supplied identity owns the origin
- [x] `read_skill(root, slug, *, identity=None)` — verifies signature when origin starts with identity's instance_id; mismatch raises `SignatureMismatchError`
- [x] Foreign-origin skills load without verification (federation handles foreign keys later)
- [x] Frontmatter serialization is deterministic (`sort_keys=True`)

## CLI (`src/skill_forge/cli.py`)

- [x] `forge identity show [--home PATH]` — print `instance_id`, public-key PEM, private-key path
- [x] `forge identity backfill [--root PATH] [--home PATH] [--dry-run]` — stamp missing fields, idempotent, preserves foreign origins
- [x] `_run_extract` threads identity through to `storage.write_skill`
- [x] `SKILL_FORGE_HOME` env var override

## Tests

- [x] `tests/test_identity.py`: 14 tests — keypair persistence, perms enforcement, deterministic from seed, sign/verify round-trip, tampered body/origin/identity all detected, canonical_payload stability
- [x] `tests/test_storage_filesystem.py`: 5 new tests — write_skill stamps when identity supplied, leaves fields None without identity, read_skill rejects tampered body, skips verify for foreign origin, preserves existing signature
- [x] `tests/test_cli_identity.py`: 7 tests — identity show generates + reloads, backfill stamps + idempotent + skips foreign + dry-run, extract threads identity through

## Validate

- [x] `ruff check` clean
- [x] `mypy --strict` clean (24 source files)
- [x] `pytest` green (116 tests)
- [x] **Live smoke**:
  - `forge identity show` → real `forge-f0d71089` instance + PEM public key
  - `forge extract file:///tmp/sample-final.html` → produced `systemd-timer-for-unreliable-jobs` draft with `origin: forge-f0d71089:...:1` and a valid signature
  - Read-back verify: PASS
  - After appending "TAMPER" to the file: `SignatureMismatchError` raised as expected
