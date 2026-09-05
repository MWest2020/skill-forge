---
status: actief
last_reviewed: 2026-09-04
---

# Curatiebesluit 2026-09-04 — obsidian-skills + graphify

Intake van clips 1–2 sep (kepano/obsidian-skills, Graphify-Labs/graphify).
Beoordeeld langs de tweetraps-regel (Mark, 2026-08-31): *gat vullen mag ook
onder 0.90; overlap met eigen suites alleen ≥ 0.90; bij twijfel niet.*
Scores: `forge judge`, 3× met per-as-mediaan, rubric v2.

## Gepromoveerd (in deze PR)

| Skill | Score | Besluit |
|---|---|---|
| defuddle | 0.86 | **live** — gat + direct nut: web → schone markdown in de zettelkast-capture-flow |
| obsidian-markdown | 0.87 | **live** — gat + direct nut: de zettelkast ís een Obsidian-vault (wikilinks, callouts, properties) |

Beide getagd als skillset `obsidian` en gemount via `forge sync claude-code`.

## Niet gepromoveerd (blijven gescoorde drafts)

| Skill | Score | Reden |
|---|---|---|
| obsidian-cli | 0.89 | gat, maar geen workflow die hem nu gebruikt — bij twijfel niet |
| json-canvas | 0.89 | idem: geen `.canvas`-bestanden in gebruik |
| obsidian-bases | 0.88 | idem: geen `.base`-bestanden in gebruik |
| graphify | 0.73 | onder de kwaliteitsbodem (0.75); monoliet van 1144 regels. Wie het wil proberen: standalone (`pipx install graphifyy`), niet via forge-mount. Wiki-note: zettelkast `graphify-kennisgraph` |

Drafts staan bewust niet in git (alleen live skills worden getrackt); dit
document is het reviewbare spoor van het hele besluit, inclusief de afwijzingen.

## Context

- Leen-oordelen per bron: zettelkast `journal/2026-09-03.md`
- VoltAgent/awesome-agent-skills (zelfde clip-batch): geen intake — directory,
  genoteerd als discovery-bron voor `forge discover`
