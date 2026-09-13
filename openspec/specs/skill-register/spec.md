# skill-register Specification

## Purpose

Het manifest: één machine-leesbare lijst van de skills die écht live staan, zodat
iets anders dan de mens kan weten wat er in de bibliotheek zit.

Zonder dit moet elke consument door `skills/` lopen en zelf raden wat telt. Dan
gaat er onvermijdelijk een draft mee, want op schijf zien een draft en een
gepromoveerde skill er hetzelfde uit — en een halfaf bestand dat gemonteerd wordt
alsof het af is, is precies de fout die deze hele pijplijn moet voorkomen. Het
manifest trekt die grens op één plek: promotie is wat je erin zet, niets anders.

De dragende eis is de **deterministische ordening**. Een manifest dat bij elke
regeneratie in een andere volgorde staat, geeft een diff vol ruis, en een diff
vol ruis wordt niet gelezen — waarna niemand meer ziet dat er stilletjes een
skill bij kwam of verdween. Alfabetisch op slug kost niets en maakt het bestand
juist bruikbaar als bestaans-bron: je leest het, je weet wat er is, en je ziet
wanneer dat verandert.

## Requirements
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

