# Spec — config loader

## API

```python
def load(root: Path | None = None) -> dict: ...
```

Returns a merged config dict. Layering, lowest precedence first:

1. **Bundled defaults** (Python literal in `skill_forge.config`)
2. **Project config** at `{root}/config/default.yml` (if file exists)

`root` defaults to `Path.cwd()`. Missing project file is **not** an error
— the bundled defaults stand alone.

## Bundled defaults (authoritative)

```python
DEFAULTS = {
    "rubric": {
        "weights": {
            "schema_compliance": 0.20,
            "clarity": 0.20,
            "actionability": 0.25,
            "gap_coverage": 0.20,
            "provenance_quality": 0.15,
        },
    },
    "promotion": {"total_min": 0.75, "axis_min": 0.50},
    "providers": {
        "extract": "claude_code",   # anthropic | claude_code
        "judge":   "claude_code",
    },
    "anthropic": {"model": "claude-opus-4-7", "max_tokens": 4096},
    "claude_code": {"binary": "claude", "timeout_s": 120},
    "discovery": {
        "max_candidates": 10,
        "user_agent": "skill-forge/0.1 (+https://github.com/MWest2020/skill-forge)",
        "respect_robots_txt": True,
    },
    "paths": {
        "skills": "skills",
        "drafts": "skills/_draft",
        "sources": "sources",
        "runs": "runs",
    },
}
```

## Merge semantics

Deep merge per top-level section (one level deep is enough for the
current schema). Lists are replaced, not concatenated. Project file
values override bundled defaults at the leaf level.

## Failure modes

- Malformed YAML: bubbles up as `yaml.YAMLError`. Caller decides how
  to surface to the user.
- Schema validation is **not** the loader's job — callers read keys
  they care about and validate inline.
