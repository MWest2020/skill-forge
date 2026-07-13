# Tasks — preserve tool and source fidelity

## 1. Models

- [x] 1.1 `SourceRef.url: str | None = None`
- [x] 1.2 `Skill.allowed_tools: list[str] | None` — alias `allowed-tools`, validator accepts list or comma-separated string, round-trips to frontmatter as a hyphenated list
- [x] 1.3 Model tests: round-trip both fields; old frontmatter without them still parses

## 2. Normalize

- [x] 2.1 Add `allowed-tools` to `_KNOWN_SKILL_FIELDS` (drift test updated)
- [x] 2.2 Injected sources ref carries `url` when `source_url` is given
- [x] 2.3 Normalize tests: allowed-tools survives; sources ref has url on repo import, no url on local import

## 3. import-repo bundled files

- [x] 3.1 Copy sibling `scripts/`, `references/`, `assets/` dirs into the draft skill dir
- [x] 3.2 Test: repo fixture with bundled dir → files land in draft; skills without them unaffected

## 4. Backfill live skills (curation ops)

- [x] 4.1 Fetch upstream anthropics/skills (shallow clone)
- [x] 4.2 Restore `allowed-tools` from upstream frontmatter where declared
- [x] 4.3 Add upstream URL to every imported skill's sources ref
- [x] 4.4 Copy bundled dirs for docx, pptx, xlsx, pdf, webapp-testing, web-artifacts-builder, skill-creator
- [x] 4.5 Re-sign touched skills via the normal write path

## 5. Refine weak tool_declaration

- [x] 5.1 Refine brand-guidelines (0.60) — name the tools explicitly
- [x] 5.2 Refine doc-coauthoring (0.75) — same
- [x] 5.3 Review diffs, accept or reject

## 6. Verify & close

- [x] 6.1 Re-judge all touched skills (median-of-3)
- [x] 6.2 `forge calibrate` — must pass, dated after the re-judges
- [x] 6.3 `forge sync claude-code`
- [x] 6.4 Gate: pytest + ruff + mypy + live smoke
- [x] 6.5 Commit(s) + archive this change
