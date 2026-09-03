## ADDED Requirements

### Requirement: Manifest van gepromoveerde skills

`forge register` SHALL een machine-leesbaar manifest schrijven van uitsluitend de
live (gepromoveerde) skills, met per skill ten minste `slug`, een één-regel
`description` en `origin`; draft-skills SHALL NOT in het manifest staan. De
uitvoer SHALL deterministisch geordend zijn (alfabetisch op slug) zodat een diff
alleen echte wijzigingen toont.

#### Scenario: Alleen live skills

- **WHEN** er zowel live skills (`skills/<slug>/`) als drafts
  (`skills/_draft/<slug>/`) zijn
- **THEN** bevat het manifest elke live slug één keer, geen enkele draft, en is de
  lijst alfabetisch op slug

#### Scenario: Bruikbaar als bestaans-bron

- **WHEN** een consument het manifest leest
- **THEN** kan 'ie voor een gegeven slug bepalen of die bestaat, met de bijhorende
  `description` en `origin`, zonder de skill-inhoud te hoeven lezen
