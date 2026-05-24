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
