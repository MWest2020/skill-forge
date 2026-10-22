## ADDED Requirements

### Requirement: The manifest carries each skill's tools

Every manifest entry SHALL carry `tools`: the skill's `allowed-tools` from its
`SKILL.md` front matter, as a list, and an empty list when the skill declares
none. A consumer SHALL be able to derive from the manifest alone which tools a
set of skills needs.

#### Scenario: A skill that needs a tool

- **WHEN** a live skill declares `allowed-tools: Bash(python3 agents/readshell.py:*)`
- **THEN** its manifest entry has `tools: ["Bash(python3 agents/readshell.py:*)"]`

#### Scenario: A skill that needs nothing extra

- **WHEN** a live skill declares no `allowed-tools`
- **THEN** its manifest entry has `tools: []`
