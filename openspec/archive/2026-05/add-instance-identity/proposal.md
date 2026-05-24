# add-instance-identity

## Why

Federation, lineage attribution, and signed exports all need a stable answer to "which instance produced this skill". Adding instance identity now — before any skill carries it — avoids retroactively re-stamping every existing skill when federation lands. It is the cheapest foundation work skill-forge has left.

Identity also makes lineage in change #3 (refinement loop) machine-verifiable: a skill refined on instance A and synced to instance B carries a verifiable chain back to its origin.

## What

- On first invocation of any `forge` command, generate an Ed25519 keypair and a human-readable instance ID. Store both under `~/.config/skill-forge/identity/`.
- Add an `origin` field to the `Skill` frontmatter: `{instance_id}:{slug}:{version}`. Populated automatically by `write_skill` for new skills; preserved verbatim for imported skills.
- Add a `signature` field to the `Skill` frontmatter: detached Ed25519 signature over a canonical serialization of the rest of the frontmatter + body sha256. Verifiable without the public key (the key is fetched out of band).
- Expose the public key via `forge identity show`. No CLI command yet for verifying foreign skills — that lands with federation.
- Existing skills (created before this change) get their `origin` and `signature` filled in by a one-off migration command: `forge identity backfill`.

## Scope

- New module `src/skill_forge/identity/` with key generation, storage, signing, verification.
- New `Identity` model in `models.py`.
- `Skill` model gains two optional fields: `origin: str | None` and `signature: str | None`. They are optional only for backward compatibility during backfill; new skills always have both.
- `write_skill` populates `origin` and `signature` on write when not already set.
- `read_skill` verifies `signature` against the body sha256 + frontmatter (excluding signature itself) when present. Mismatches raise `SignatureMismatchError`.
- New CLI commands: `forge identity show`, `forge identity backfill`.
- Tests cover: keypair generation determinism (same input → same key), signing round-trip, verification of valid + tampered skills, backfill idempotency.

## Out of scope

- Federation. No network code in this change.
- Key rotation. Mark one key, use one key. Rotation is a separate change once we know what breaks when it happens.
- Per-skill author identity within an instance. One instance, one identity. Multi-user comes later if ever.
- Submitting the public key to any directory. Manual sharing only.
- Hardware-backed keys (YubiKey, TPM). The key sits in a file with `0600` permissions. Hardware backing is a hardening change for later.
- Encrypted skill bodies. Signatures cover integrity, not confidentiality.

## Risks

- **Key loss = lost ability to sign new versions of existing skills.** Mitigation: print a clear "back up `~/.config/skill-forge/identity/` now" message after first generation. Document recovery path: regenerate, accept new instance ID, re-sign skills as the new identity. Lineage breaks at that point — that is the cost of losing your key, and the cost is visible in the lineage.
- **Backfill changes every existing skill file.** Mitigation: backfill is opt-in via explicit command. Without it, signatures stay missing and old skills still load (validation tolerates `None`).
- **Frontmatter canonicalization is fiddly.** Sorted YAML keys, fixed line endings, no trailing whitespace. Mitigation: round-trip test forces a stable representation.
- **People will ask whether this is a blockchain.** It is not. Mitigation: explicitly say so in the README.
