# Spec — refine-accept and refine-reject

After `refine` writes a new iteration to `iterations/` as `pending`,
the user decides what happens next. There is exactly one promotion
mechanism, so accidental activation requires intent.

## API

```python
def accept_iteration(
    root: Path,
    slug: str,
    *,
    version: int,
    identity: Identity | None = None,
) -> Path: ...

def reject_iteration(
    root: Path,
    slug: str,
    *,
    version: int,
    reason: str,
) -> None: ...
```

## `accept_iteration` behavior

1. Verify the lineage via `lineage.verify` (cross-checks files vs
   index). Raise `LineageMismatchError` on disagreement.
2. Load the target iteration's body from
   `iterations/v{version}-*.md`. Raise `FileNotFoundError` if missing
   or `MultipleIterationsAtVersionError` if more than one file has
   that version number (shouldn't happen, but worth catching).
3. Construct a `Skill` from the current SKILL.md's frontmatter +
   the new body. (Frontmatter fields like `description`, `sources`,
   `created` are preserved; `body` swaps in; `version` is bumped via
   storage layer's stamp on next signing.)
4. Re-sign via `write_skill(..., identity=identity, overwrite=True)`.
5. Update `lineage.yml`:
   - The previously-current iteration becomes `status: superseded`.
   - The accepted iteration becomes `status: current`.
   - `current_version = version`.
6. Append `promoted` Run event (re-using existing event vocabulary).

After accept, `SKILL.md` byte-equals the accepted iteration file.

## `reject_iteration` behavior

1. Verify the iteration exists and has `status: pending`.
2. Set `status: rejected` and `reject_reason: reason` in
   `lineage.yml`. `current_version` unchanged.
3. The iteration file stays on disk — audit, not deletion.
4. Append `demoted` Run event with `metadata.reason`.

## CLI

```
forge refine-accept <slug> --iteration N [--root PATH]
forge refine-reject <slug> --iteration N --reason TEXT [--root PATH]
```

Exit codes: `0` ok, `1` lineage/IO failure, `2` iteration not pending
(already current, already rejected, or already superseded).

## Out of scope

- Accepting multiple pending iterations atomically.
- Reverting `SKILL.md` to an old iteration via a path other than
  `refine-accept`. There is one promotion mechanism.
