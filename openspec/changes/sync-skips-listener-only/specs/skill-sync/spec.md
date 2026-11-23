## ADDED Requirements

### Requirement: Listener-only skills are never synced

`forge sync` SHALL NOT mount a live skill tagged `listener-only` into any
target, for a sync of all skills and for a sync of one tag. A tagged sync that
leaves nothing to mount SHALL be an error.

#### Scenario: A full sync

- **WHEN** the live skills are `alpha` and `mail-mark`, and `mail-mark` is
  tagged `listener-only`
- **THEN** `forge sync claude-code` mounts `alpha` only

#### Scenario: A tagged sync

- **WHEN** `read-state` and `mail-mark` both carry the tag `ratatoskr`, and
  `mail-mark` is also tagged `listener-only`
- **THEN** `forge sync claude-code --tag ratatoskr` mounts `read-state` only
