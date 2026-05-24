# Spec — `forge identity` commands

## `forge identity show`

Loads (or generates) the instance identity and prints:

```
Instance ID: forge-a1b2c3d4
Public key:  ssh-ed25519 AAAAC3Nz...
Private key: /home/<user>/.config/skill-forge/identity/private_key.pem
              (mode 0600 — back this file up; losing it breaks signing)
```

- Uses `~/.config/skill-forge/` as `{home}` by default. Override via
  `--home PATH` (also honors `SKILL_FORGE_HOME` env var).
- If generation just happened, prepends a one-line banner:
  `Generated new identity. Back up the private key now.`
- Exit code: 0 always (unless the home directory cannot be created /
  written to — then exit 1 with the path that failed).

## `forge identity backfill`

Walks all skills under `{root}/skills/` (both live and draft) and stamps
`origin` + `signature` on any skill where either field is `None`.

```
forge identity backfill [--root PATH] [--home PATH] [--dry-run]
```

Output (one line per skill touched):

```
stamped: skills/_draft/resize-statefulset-pvc/SKILL.md  origin=forge-a1b2c3d4:resize-statefulset-pvc:1
skipped: skills/foo/SKILL.md                              already signed
```

Behavior:

- **Stamps only when missing.** Skills with both fields already set are
  skipped. Skills with one but not the other get the missing one filled in
  (origin without signature is the common case for previously-imported
  skills).
- **Preserves foreign origins.** If `origin` is already set and does not
  start with our `instance_id`, the skill is skipped entirely (we cannot
  sign on behalf of another instance).
- **Idempotent.** Re-running stamps nothing on the second invocation.
- **`--dry-run`** prints the plan but writes nothing.

Exit codes:

- `0` — success (whether or not anything was stamped).
- `1` — at least one skill failed to re-serialize (e.g., model validation
  rejected the round-trip). Surfaces the offending path in stderr.

## CLI surface (after this change)

The full command tree gains one subcommand group:

```
forge
├── extract
├── judge        (NotImplementedError until change #2)
├── promote      (NotImplementedError until change #2)
├── demote       (NotImplementedError until change #2)
├── ls
├── show
├── discover     (NotImplementedError until change #4)
├── run          (NotImplementedError until change #4)
└── identity
    ├── show
    └── backfill
```

Typer's nested `typer.Typer()` pattern; the existing top-level `app`
gains `app.add_typer(identity_app, name="identity")`.

## Threading identity through write callers

`_run_extract` (and any future write entrypoint) loads the identity once
per command run and passes it to `storage.write_skill`. The CLI layer
owns the identity lifecycle; the storage layer takes it as an argument.

## Out of scope

- `forge identity rotate`, `forge identity verify-foreign`, `forge identity export-pubkey`. All later.
