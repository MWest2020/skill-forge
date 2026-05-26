"""Extraction system prompt + emit_draft tool schema (change #2)."""

from __future__ import annotations

EXTRACTION_SYSTEM_PROMPT = """\
You distill a single source page (or a small chain of related pages) into a \
reusable Anthropic-style SKILL.md draft.

Output ONLY via the `emit_draft` tool. No prose, no preamble, no commentary \
outside the tool call.

Rules:
- name: short kebab-case slug, lowercase, digits and hyphens only, matching \
  `^[a-z0-9][a-z0-9-]*$`. Specific to the topic — not generic.
- description: one paragraph (1-3 sentences) that answers \
  "when should an agent use this skill?". Start with "Use this skill when ...". \
  No marketing language.
- body: markdown body, no frontmatter. Include these sections in order:
    ## When to use
    ## Procedure
    ## Failure modes
  Add other sections (e.g. "## References", "## Examples") when useful. \
  Paraphrase the source — never reproduce long passages verbatim. When the \
  source names specific commands, flags, config keys, file paths, or error \
  messages, cite them exactly in inline code.

If the input contains multiple pages separated by `--- next page: <url> ---` \
markers, synthesize one coherent skill across all of them. Do not emit \
per-page sections.
"""


JUDGE_SYSTEM_PROMPT = """\
You judge a single SKILL.md against the skill-forge rubric.

Output ONLY via the `score_skill` tool. No prose, no preamble.

Score each of the five axes from 0.0 to 1.0:

- schema_compliance — frontmatter valid, expected sections present in order
  ("## When to use", "## Procedure", "## Failure modes"). Missing/extra
  sections lose points proportionally.
- clarity — the "when to use" hint is unambiguous; no unexplained jargon;
  procedure steps are concrete.
- actionability — an agent could follow this end-to-end without external
  guesswork. Cites specific commands, flags, paths.
- gap_coverage — adds something distinct versus typical skills on this
  topic. Generic content scores low.
- provenance_quality — body has a `## Source` section with human-readable
  URLs (mandatory); description reads as paraphrased, not verbatim quotation;
  `sources` field non-empty. Missing `## Source` section is a hard penalty
  (score this axis at 0.4 or below).

For each axis below 1.0, write one `findings` entry with:
- axis: the axis name
- observation: 1-3 sentences naming the specific gap or fix
- severity: "info" (cosmetic), "warning" (would lower agent effectiveness),
  "blocker" (the skill is unsafe or unusable as-is)

Do NOT output a `total` — the caller computes it from your per-axis scores
and the configured weights.
"""


REFINEMENT_SYSTEM_PROMPT = """\
You refine an existing SKILL.md to address specific judge findings.

Output ONLY via the `emit_refinement` tool. No prose, no preamble.

Rules:
- Produce ONLY the markdown body — no frontmatter, no metadata.
- Keep the existing section structure ("## When to use", "## Procedure",
  "## Failure modes", "## Source") unless a finding explicitly asks you to
  restructure.
- The `## Source` section is mandatory. If the input body already has one,
  PRESERVE its URLs verbatim. If the input body is missing the section, ADD
  it with the source URLs from the additional source material (if provided)
  or the URL implied by the procedure references.
- Address each finding precisely. Don't globally rewrite — surgical edits
  that target lost points score better than wholesale rewrites.
- If `extra_source` is supplied, paraphrase relevant material from it into
  the body AND add its URL to `## Source`. Never quote verbatim.
- If `hint` is supplied, treat it as a user-priority overlay on top of
  the findings. If hint contradicts a finding, prefer the hint and note
  the trade-off in a brief inline comment.
- Preserve specific commands, flags, config keys, and file paths verbatim.
"""


EMIT_REFINEMENT_TOOL = {
    "name": "emit_refinement",
    "description": "Emit a refined SKILL.md body addressing the supplied findings.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "body": {
                "type": "string",
                "description": (
                    "The refined markdown body, no frontmatter. Must keep "
                    "the existing section structure unless a finding asks "
                    "you to restructure."
                ),
            },
        },
        "required": ["body"],
    },
}


SCORE_SKILL_TOOL = {
    "name": "score_skill",
    "description": "Emit per-axis scores and findings for one SKILL.md.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_compliance": {"type": "number", "minimum": 0, "maximum": 1},
            "clarity": {"type": "number", "minimum": 0, "maximum": 1},
            "actionability": {"type": "number", "minimum": 0, "maximum": 1},
            "gap_coverage": {"type": "number", "minimum": 0, "maximum": 1},
            "provenance_quality": {"type": "number", "minimum": 0, "maximum": 1},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "axis": {
                            "type": "string",
                            "enum": [
                                "schema_compliance",
                                "clarity",
                                "actionability",
                                "gap_coverage",
                                "provenance_quality",
                            ],
                        },
                        "observation": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["info", "warning", "blocker"],
                        },
                    },
                    "required": ["axis", "observation", "severity"],
                },
            },
        },
        "required": [
            "schema_compliance",
            "clarity",
            "actionability",
            "gap_coverage",
            "provenance_quality",
            "findings",
        ],
    },
}


EMIT_DRAFT_TOOL = {
    "name": "emit_draft",
    "description": "Emit one distilled SKILL.md draft for the provided source content.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {
                "type": "string",
                "description": (
                    "Kebab-case slug for the skill, e.g. 'kubernetes-pvc-resize'. "
                    "Matches ^[a-z0-9][a-z0-9-]*$."
                ),
            },
            "description": {
                "type": "string",
                "description": (
                    "One paragraph (1-3 sentences) explaining when an agent "
                    "should use this skill. Start with 'Use this skill when ...'."
                ),
            },
            "body": {
                "type": "string",
                "description": (
                    "Markdown body, no frontmatter. Must contain '## When to use', "
                    "'## Procedure', and '## Failure modes' sections."
                ),
            },
        },
        "required": ["name", "description", "body"],
    },
}
