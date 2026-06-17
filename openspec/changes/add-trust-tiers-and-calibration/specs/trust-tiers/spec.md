# Spec — trust tiers + calibration

## Tier (derived, never stored)

`Tier = bronze | silver | gold` (plus "untiered" for not-yet-judged /
below-threshold). Computed by `derive_tier`, a pure function of three inputs —
the latest judged `RunEvent` (for total + `rubric_version`), the matching
`GoldAttestation` (if any), and the latest passing `CalibrationRecord`:

```
gold    valid GoldAttestation for the skill's current (origin, version)
silver  else: latest judged total ≥ total_min AND a passing CalibrationRecord
        exists with the same rubric_version and calibrated_at ≥ judged_at
bronze  else: latest judged total ≥ total_min (and every axis ≥ axis_min)
untiered otherwise
```

No `tier` frontmatter field exists; if one is present in an imported skill it is
stripped (not in `_KNOWN_SKILL_FIELDS`) and ignored.

## Gold attestation — `forge gold <slug> [--gold-home PATH]`

- Loads/creates the **gold keypair** at `--gold-home` (default
  `~/.config/skill-forge/gold/`), distinct from the instance identity. Same
  0600 key hygiene as the instance key.
- Signs a `GoldAttestation` over the canonical bytes of `(skill_origin,
  version, "gold")` and stores it in `sources/{slug}.yml`.
- Re-running for a new version replaces the attestation; an attestation for an
  older version no longer matches (gold lapses on refine until re-attested).
- Exit 1 if the skill is not live or not yet judged.

Verification (in `derive_tier` / `forge tier`): the stored `gold_public_key`
must verify the signature over the recomputed canonical bytes, and `version`
must equal the skill's current version. Any mismatch → not gold (no error;
just a lower tier).

## `forge calibrate [--root PATH]`

- Gold set = live skills carrying a valid gold attestation. Weak fixtures =
  SKILL.md files under the configured `calibrate.weak_dir` (optional).
- If `len(gold_set) < calibrate.min_gold` (default 3) → exit 2,
  `insufficient gold set: N < min_gold`.
- Judges every sample under the current rubric (median-of-N). Expected: golds
  `total ≥ total_min`; weak samples `< total_min`.
- Writes a `CalibrationRecord` (`event == "calibrated"`) to the audit trail and
  prints a summary: agreement, pass/fail, per-sample line. Exit 0 even when
  `passed` is false (a failed calibration is a valid, recorded result — it
  means the grader drifted, which the operator must see).

## `forge tier <slug>` / `forge ls`

- `forge tier <slug>` prints the derived tier and the evidence (judged total +
  rubric_version; calibration id if silver; attestation date if gold).
- `forge ls` gains a `Tier` column.

## Config

```
calibrate:
  min_gold: 3                 # refuse to calibrate below this many golds
  weak_dir: null              # optional dir of known-weak SKILL.md fixtures
```

## Guarantees

- **Tier is verifiable, not declarative.** Gold requires a signature that
  verifies; silver requires a recorded passing calibration; neither can be
  asserted by editing frontmatter.
- **The judge never confers gold.** Only `forge gold` (human + gold key) does;
  `calibrate` only measures the judge against the human-set gold set.
- **Version-pinned.** Attestations and the silver citation are tied to the
  skill version / rubric version that produced them; a refine or rubric bump
  lapses the claim until re-established.

## Non-goals

- No tier-based auto-promotion or auto-deploy (tier is informational).
- No attestation exchange between instances (the gold key is local).
- No new judge axes or weight changes (that was rubric v2).
