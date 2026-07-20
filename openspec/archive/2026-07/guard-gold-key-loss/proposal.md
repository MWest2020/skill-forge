# Guard against silent gold-key loss

## Why

The gold signing key that vouched all three golds was created silently by
`forge gold` (first run mints via `get_or_create`), never surfaced, never
backed up, and is now unrecoverable (2026-07-20 — searched agent LXC + alma,
gone; likely lived in a volatile path wiped on reboot). Gold is the one tier
that hinges on a single private key a human must hold; losing it silently is
the worst-possible failure and it happened with zero signal.

`forge gold` gives no indication when it is *minting a new gold identity*
(vs loading the existing one), and no warning when the gold home is on a
volatile path. Both would have caught this.

## What

Add a pre-flight guard to `forge gold`, emitted to stderr before attesting:

- **Minting a new gold identity** (no key at the gold home): warn loudly that
  a NEW voucher is being created, that existing attestations were signed by a
  different key, and that it MUST be backed up off-box or its attestations can
  never be reissued.
- **Volatile gold-home path** (`/tmp`, `/var/tmp`, `/dev/shm`): warn that the
  key will not survive a reboot; recommend a persistent `--gold-home`.

Warn-only — never blocks (a test/CI run may legitimately use a temp home).
The point is that key creation can never again be silent.

## Out of scope

- Automatic backup/escrow of the gold key (the human must hold it — automating
  it off-box would undermine what gold means).
- Recovering the lost key or re-attesting the existing golds (Mark's manual
  step with the freshly-created persistent key).
- Any change to how attestations verify (`gold_valid_for` unchanged).

## Risks

- **Warning fatigue / false positive on legitimate temp use.** Mitigated:
  stderr-only, does not block; CI can ignore. The mint warning only fires on
  genuine first-creation, which is rare and exactly when you want it.
