# Design — rubric v2

The contentious decisions, resolved before specs.

## 1. structural_clarity vs schema_compliance (don't double-count)

They sound alike; they must measure different things.

- **schema_compliance** (unchanged): does it *parse* and are the *expected
  sections present*? Valid frontmatter, `## When to use` / `## Procedure` /
  `## Failure modes` present and ordered. Binary-ish, structural correctness.
- **structural_clarity** (new): given the sections exist, is the content
  *delimited where delimiting helps an agent parse it* — and is it free of
  ceremony? Rewards: a long procedure broken into labelled steps; XML/fenced
  blocks around content an agent must extract verbatim (commands, payloads).
  Penalizes: **over-tagging** — a short skill wrapped in XML scaffolding, tags
  that add nesting without aiding extraction. A 12-line skill with no tags can
  score 1.0; a 12-line skill drowning in `<section>` wrappers scores low.

Litmus: schema asks "are the parts there?", structural asks "are the parts
*shaped* so a machine finds them, without ceremony?" A skill can pass schema
and fail structural (right sections, wall of undifferentiated prose) or pass
structural and fail schema (beautifully delimited but missing `## Source`).

## 2. Conditional axes: N/A → 1.0 in the prompt, NOT a floor exemption

`tool_declaration` and `example_grounding` don't apply to every skill:
- a skill with no tool/command in its procedure has nothing to declare;
- a pure reference/lookup card (e.g. `ponytail-help`) needs no worked example.

If such a skill scored low there, the per-axis promotion floor (`axis_min`,
0.50) would **block a legitimate skill**. Two ways out:

- **(A) Exempt the new axes from the floor** — gate = total ≥ total_min AND the
  *original 5* axes ≥ axis_min. Clean conceptually, but splits the gate logic
  (some axes floored, some not) and leaks rubric structure into `promoter`.
- **(B) N/A → 1.0 in the prompt** (chosen) — the judge scores a non-applicable
  axis at 1.0 ("no tools to call → tool_declaration = 1.0"; "a clean reference
  card needs no example → example_grounding = 1.0"). The gate stays uniform
  (all 8 axes floored); the nuance lives in the rubric prose where it's
  tunable, not in code.

(B) keeps `promoter` dumb and the gate honest. The cost: it leans on the judge
following the N/A rule — mitigated by median-of-N and explicit prompt wording.

## 3. Weights (proposed; tunable in config)

8 axes must re-sum to 1.0. The new axes are quality *nudges*, not co-equal with
actionability. Proposed:

| axis | v1 | v2 |
|---|---|---|
| actionability | 0.25 | 0.22 |
| clarity | 0.20 | 0.15 |
| gap_coverage | 0.20 | 0.15 |
| schema_compliance | 0.20 | 0.12 |
| provenance_quality | 0.15 | 0.12 |
| structural_clarity | — | 0.10 |
| example_grounding | — | 0.08 |
| tool_declaration | — | 0.06 |
| **sum** | 1.00 | **1.00** |

Rationale: actionability stays the heaviest; the three new axes together carry
0.24 — enough to move a borderline score, not enough to sink a strong skill on
a single nudge. With N/A→1.0, a tool-less reference card simply banks
0.06+0.08 rather than losing it.

## 4. Re-judge ripple — stale, not wrong; no auto-demote

Bumping to v2 makes every recorded score a v1 artifact. We do **not** rescore
the library automatically and we do **not** demote anything. Behaviour:
- `forge ls` shows the last recorded (v1) score until a skill is re-judged.
- `forge judge <slug>` / `forge advise <slug>` produce a v2 score; the
  provenance records `rubric_version: "2"`, so v1 vs v2 scores are
  distinguishable in the audit trail.
- A future bulk re-judge is an operator action (and a natural fit for the
  `calibrate` sweep in group C). Out of scope here.

This is the honest ISO-grade position: a score is always tagged with the rubric
version that produced it; mixing is visible, not silent.

## 5. Examples stay out of the SKILL.md body

`example_grounding` rewards guidance *grounded in* a concrete example — it does
**not** require pasting large examples into the top-level SKILL.md (that bloats
the body and worsens the known refine-timeout). A compact inline example or a
reference to one satisfies the axis. skill-forge does not (yet) manage separate
example files; this change adds no such machinery — the axis judges the body as
written.
