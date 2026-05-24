# Spec — audit trail (`runs/*.jsonl`)

The pipeline writes one line per significant action to a JSONL file under
`runs/`. The trail is append-only, intended for forensic review and for
later changes (lineage, federation conflict reporting).

## File layout

```
runs/
└── {run_id}.jsonl
```

Where `run_id = "run-YYYY-MM-DD-NNN"`. Each *invocation* of a CLI command
(import, import-dir, judge, promote, demote) gets one run_id. A bulk
command like `import-dir` shares one run_id across all its child events.

The counter `NNN` is the lowest unused 3-digit integer for that date
(scan existing `runs/run-YYYY-MM-DD-*.jsonl`, take `max + 1`, default 001).
**Not** intended for high-frequency use — at >999 runs/day we revisit.

## Line format

Each line is a JSON object — one `RunEvent`:

```python
class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str                   # matches the filename
    event: Literal["imported", "judged", "promoted", "demoted"]
    timestamp: datetime           # tz-aware UTC
    skill_slug: str
    scores: JudgeScore | None     # set on event="judged"
    promoted: bool                # True on promoted, False elsewhere
    metadata: dict[str, Any] = {} # free-form (e.g. {"reason": "..."})
```

(The existing `Run` model is repurposed as a per-run aggregate; `RunEvent`
is the per-line shape that lands in JSONL.)

Encoding: `model_dump(mode="json")` + `json.dumps(separators=(",",":"))` +
`"\n"`. UTF-8.

## Write semantics

```python
def append_run_event(root: Path, event: RunEvent) -> Path: ...
```

- File created on first write of the day.
- Each call opens, appends one line, flushes, closes.
- Concurrent writes from a single user are tolerated via O_APPEND
  (POSIX guarantees atomicity for writes ≤ PIPE_BUF, which our lines
  comfortably are).
- File mode `0o644`. Directory mode `0o755`.

## `RunSummary` snapshot inside `sources/{slug}.yml`

The `judged` event also writes a `RunSummary` into the existing `runs:`
list inside `sources/{slug}.yml` so `forge ls` and `forge show` can
display the latest score without scanning JSONL files.

```yaml
slug: ...
sources: [...]
runs:
  - run_id: run-2026-05-24-003
    judge_score: 0.87
    promoted: false
  - run_id: run-2026-05-24-007
    judge_score: 0.91
    promoted: true
```

Newest at the end. Capped at the last 20 entries per skill (older ones
stay in the JSONL audit log).

## Failure semantics

- If JSONL append fails (disk full, permissions), the CLI command fails
  with a clear error and the pipeline action is not committed (the
  caller's filesystem mutation rolls back where reasonable; the spec for
  each action lists what "rolls back" means concretely).
- If the directory doesn't exist, it's created on first append (mode 0755).

## Out of scope

- Rotation / pruning. `forge runs prune` is a separate change.
- Cross-skill query (`forge runs filter --since ...`). Out.
- Encryption at rest. The audit trail is plaintext — same trust boundary
  as the rest of the user's home directory.
