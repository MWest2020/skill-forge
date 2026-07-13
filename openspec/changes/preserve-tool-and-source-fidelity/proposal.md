# Preserve tool and source fidelity through import

## Why

The mission is agents that use **only the right tools** and carry **readable
references**. The import pipeline currently damages both, and the judge data
proves it:

1. **`allowed-tools` is stripped on import.** Claude Code's own enforcement
   field for which tools a skill may invoke is not in
   `_KNOWN_SKILL_FIELDS` (`import_skill/normalize.py`), so every import path
   silently deletes it. Upstream skills that declared their tool surface lost
   it in our library.
2. **Source references are opaque.** `normalize_skill_md` injects
   `sources: [{id: src-<sha6>}]` — meaningless outside forge — while the
   human-readable URL lands only in the `## Source` body section. The v2 judge
   flagged `provenance_quality` on 10 live skills (0.55–0.65) with the same
   observation each time: "'src-…' is an opaque identifier".
3. **Bundled helper files are never imported.** `import-repo` takes SKILL.md
   only. Seven live skills (docx, pptx, xlsx, pdf, webapp-testing,
   web-artifacts-builder, skill-creator) instruct the agent to run
   `scripts/…` / read `references/…` that do not exist locally — an agent
   following them dead-ends. The files are MIT-licensed in the upstream repo;
   nothing forces this loss.

## What

**Code (src/ + tests):**

- `models.Skill` gains `allowed_tools: list[str] | None` (frontmatter key
  `allowed-tools`, accepted as YAML list or comma-separated string,
  serialized back as a list under the hyphenated key). `SourceRef` gains
  `url: str | None`.
- `normalize_skill_md`: `allowed-tools` joins the whitelist; when
  `source_url` is given the injected sources ref becomes
  `{id: src-…, url: <source_url>}`.
- `import-repo`: sibling `scripts/`, `references/`, `assets/` directories of
  a found SKILL.md are copied into the draft skill directory (and travel to
  live on promote; `sync` already mirrors whole skill dirs).

**Curation ops (gitignored working data + committed live skills):**

- Backfill the imported live skills from upstream `anthropics/skills`:
  restore `allowed-tools` where upstream declares it, add the upstream URL to
  each `sources` ref, fetch bundled dirs for the seven skills that reference
  them.
- Refine `brand-guidelines` (tool_declaration 0.60) and `doc-coauthoring`
  (0.75) to name their tools explicitly.
- Re-judge every touched skill, then `calibrate` (silver requires a passing
  calibration dated on/after the judge run), then `sync claude-code`.

## Out of scope

- No new rubric axes or weight changes — the existing
  `tool_declaration` / `provenance_quality` axes already measure this.
- No enforcement that a skill's *body* only mentions tools listed in
  `allowed-tools` (a future lint, possibly in `advise`).
- No re-import of dropped skills (template-skill, theme-factory stay out).
- The parked verbatim/token-fidelity change stays parked; this change copies
  bundled *files*, it does not alter body-paraphrasing policy.

## Risks

- **Strict models reject existing frontmatter.** Both new fields are
  optional with `None` defaults; existing SKILL.md files parse unchanged.
- **Signature invalidation.** Patching live frontmatter changes content →
  instance signature must be re-stamped; promote/import paths already
  re-sign, and the backfill uses the same write path.
- **Bundled scripts are executable content from an external repo.** They are
  copied verbatim, MIT-licensed, provenance-tracked in
  `sources/{slug}.yml`; they are not executed by forge (no-skill-execution
  non-goal holds). The trust decision stays with the consumer.
- **`allowed-tools` semantics differ per consumer** (Claude Code honors it;
  others may not). We preserve, not interpret.
