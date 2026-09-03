# Change: add-skill-register

## Why

Consumenten buiten skill-forge (de handbook-agent-registry) willen kunnen checken
of een skill die een agent claimt ("agent X gebruikt skill Y") écht bestaat. Nu is
die kennis alleen impliciet in de `skills/`-map. Er is geen machine-leesbaar,
gezaghebbend manifest van gepromoveerde skills dat een andere repo kan consumeren.
Zonder zo'n bron kan de handbook-gate een `skills:`-entry niet valideren en blijft
elke skill-naam een onverifieerbare bewering.

## What

- Een `forge register`-commando dat een manifest schrijft van de **live
  (gepromoveerde)** skills: per skill `slug`, `description` (één regel) en `origin`.
- Het manifest is de gezaghebbende catalogus "welke skills bestaan"; de binding
  "welke agent welke skill" blijft bij de consument (handbook-agent-defs).

## Scope

- Nieuw: `register`-commando + `register`-module + spec `skill-register`.
- Leest de bestaande live-skill-tree; schrijft `register.yml` (of `--out`).

## Out of scope

- De consumptie in de handbook (mirror + gate) — aparte change in die repo.
- Draft-skills, lineage, judge-scores — het register bevat alleen wat gepromoveerd
  is (de bodem voor "bestaat").
- Signature-verificatie bij het bouwen (het register is een index, geen trust-bron;
  `origin` staat erin zodat een consument het desgewenst kan naslaan).

## Risks

- Manifest raakt achter op de tree → we regenereren het in `sync`/CI en de
  consument mirror't het (drift-gate), net als de importlijst. Handmatig bewerken
  is geen bron.
