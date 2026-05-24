# add-import-and-judge

## Why

skill-forge's pivot to curation/improvement (see `STRATEGY.md`) requires two capabilities the current code does not have:

1. **Import** an existing SKILL.md from outside the extraction pipeline. The fetcher → distiller path is one intake; manual authoring, copying from `.claude/skills/`, or accepting a skill from a peer are other intakes that must all land in the same `skills/_draft/` location with the same provenance treatment.
2. **Judge** an existing skill against the rubric. Today `forge judge` raises `NotImplementedError`. Until judging works, refinement (change #3) has no error signal to optimise against.

Together these unlock the refinement loop. Without them, refinement is a guess.

## What

### Import

A new `forge import` command that takes a SKILL.md path (or an inline string via stdin) and lands the skill in `skills/_draft/{slug}/` with:

- A `sources/{slug}.yml` provenance record. If the import declares a source URL or repo, that becomes a `Source` entry with `license=unknown` until manually annotated. If no source is declared, a single `Source` is recorded with `url=local-author` and the contributor's instance ID.
- A computed sha256 of the imported body, captured before any normalization, so the original bytes are auditable.
- Frontmatter validation: the imported file must parse cleanly as a Skill model. Missing required fields → reject with an actionable error.

Variants:

- `forge import <path>` — single file.
- `forge import-dir <dir>` — bulk, treats each subdirectory containing a `SKILL.md` as one skill. Useful for `~/.claude/skills/` or `microsoft/skills` clones.
- `--origin-tag <tag>` — annotate each imported source with an origin label (e.g., `external/claude-code`, `microsoft/skills`). Stored in the `Source.contribution` field for now; if `Source` ever gains a structured `origin_tag`, that field replaces the convention.

### Judge

A working `forge judge` command and a `judge` subroutine:

- Loads the skill, runs the rubric prompt against the configured judge provider (default: Anthropic).
- Returns a `JudgeScore` (existing model) plus a list of `JudgeFinding` (new) — per-axis observations, especially the ones that lost points. These are the input refinement needs.
- Writes a `Run` record to `runs/{run_id}.jsonl` (one line per run). This is the JSONL audit trail the original roadmap promised but the code does not yet write.
- Appends a `RunSummary` to `sources/{slug}.yml` runs list, so `forge ls` and `forge show` can display the latest score without reading the runs file.

### Promote / demote

The threshold logic from `project.md` is implemented:

- `forge promote <slug>` moves a draft to `skills/` if `judge_score >= total_min` and every axis `>= axis_min`. With `--force`, promotes regardless (overrules threshold, logged with reason).
- `forge demote <slug> --reason <reason>` moves a live skill back to draft. The reason is appended to the skill's `lineage.yml` (see change #3) or stored as a JSONL note for now if lineage is not yet present.

## Scope

- New CLI: `import`, `import-dir`, `judge` (implementation), `promote` (implementation), `demote` (implementation).
- New module `src/skill_forge/import_skill/` with a `import_file` and `import_directory` function. (Module name avoids shadowing the Python builtin `import`.)
- New module `src/skill_forge/evaluation/judge.py` filled out with real logic.
- New `JudgeFinding` model: `axis: str`, `observation: str`, `severity: Literal["info","warning","blocker"]`.
- Provider interface extension: `LLMProvider.judge(skill: Skill) -> tuple[JudgeScore, list[JudgeFinding]]`.
- A judge prompt under `src/skill_forge/providers/_prompts.py` (new section), reviewed for clarity and structured-output enforcement.
- Audit trail: `runs/{run_id}.jsonl` writing, one event per pipeline action (`imported`, `judged`, `promoted`, `demoted`).

## Out of scope

- Refinement. Generating a *new* version of the skill is change #3. Judging it is here.
- Discovery. No automatic source finding. Imports take a known path or URL.
- Federation, MCP server mode, plugin bridges. All later.
- Anything that changes the storage layout beyond writing `runs/{run_id}.jsonl` and one new optional field on `Source` (`origin_tag`).
- Bulk re-judging. Manual one-at-a-time judging is enough for the MVP. Bulk runs are easy to add once one works.

## Risks

- **Judge prompt drift over time.** Anthropic's outputs may shift slightly across model versions, changing scores for unchanged skills. Mitigation: pin the model name in `config/default.yml`; log model + version in every `Run` record; rejudging is cheap if scores need calibration.
- **Imported skills with invalid frontmatter clutter `_draft/`.** Mitigation: import rejects invalid skills before writing anything. Partial imports never land.
- **Promotion threshold is opinionated.** Some users will want a permissive threshold and some will want strict. Mitigation: threshold lives in `config/default.yml`, already configurable. Document the trade-off in README.
- **`runs/*.jsonl` grows unbounded.** Mitigation: out of scope for this change. Rotation is a maintenance concern handled by `forge runs prune` (separate change). For now, document growth and rely on git ignore.
- **The `JudgeFinding` shape leaks into prompts.** Mitigation: the prompt template asks for findings in a structured way (JSON Schema in the prompt); the parser is strict; malformed responses fail loudly with the raw response logged.
