# OpenSpec workflow — skill-forge

OpenSpec is the lightweight spec-driven workflow used in this repo. Every
non-trivial change lives as a folder under `openspec/changes/` and goes through
four phases. The folder is the source of truth for **why** and **what**; the
code is the **how**.

## Phases

### 1. Propose

Create `openspec/changes/{change-id}/proposal.md`. Answer:

- **Why** — what problem, what motivates this now.
- **What** — capabilities added or changed, in plain language.
- **Scope** — what this change touches.
- **Out of scope** — what it explicitly does **not** touch (often the more
  useful list).
- **Risks** — what could go wrong, what we'd notice first.

Then write specs under `specs/{capability}/spec.md` for each capability the
change introduces or modifies. Specs describe **contracts**, not implementation:
what something does, what its inputs are, what it guarantees on output, what it
fails on.

Lastly write `tasks.md` — concrete checkboxes a future Claude session can pick
up. Keep tasks small enough that each one maps to one commit.

### 2. Apply

Open the change folder, work through `tasks.md` top to bottom. Each task = one
commit referencing the change ID. Update specs in place when an assumption
turns out wrong — do **not** silently drift between code and spec.

The change folder is mutable during Apply. Anything in `openspec/changes/`
overrides anything elsewhere in the repo.

### 3. Validate

Acceptance gate before archiving:

- All tasks checked off.
- All specs match the code: a fresh reader can re-derive behavior from the
  spec without reading the source.
- Tests cover the contracts described in the specs.
- `ruff check`, `mypy --strict`, `pytest` all green.
- Live smoke: the CLI command introduced by the change runs end-to-end on at
  least one real input (no mocks).

### 4. Archive

Move the change folder to `openspec/archive/{YYYY-MM}/{change-id}/` once
Validate passes. The archive is read-only history — when behavior changes
later, a new change proposal supersedes the old one rather than editing it.

## Change folder layout

```
openspec/changes/{change-id}/
├── proposal.md                  why + what + scope
├── tasks.md                     ordered checkbox list, one per commit
└── specs/
    ├── {capability-1}/spec.md   contract for capability 1
    ├── {capability-2}/spec.md   contract for capability 2
    └── ...
```

Change IDs are kebab-case verbs: `add-core-models-and-storage`,
`add-extraction-pipeline`, `refactor-storage-to-sqlite`, etc.

## Conventions

- Specs are written in present tense ("the model validates X"), not future
  ("will validate"). They describe the system **after** the change applies.
- Keep `proposal.md` short — half a page is usually plenty.
- Update `tasks.md` as work progresses; check boxes off; leave a one-line note
  beside any task that turned out to be more or less than expected.
- If a change grows beyond ~10 tasks, split it. Bigger changes review badly.
- One change per topic; don't bundle unrelated work.

## TDD bias

Each capability spec should land with at least one failing test in `tests/`
**before** the implementation. The Apply phase turns red into green, not the
other way around.
