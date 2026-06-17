# Design — trust tiers + calibration

## 1. Two keys, two meanings (gold ≠ instance auto-sig)

The instance Ed25519 key (#1b) signs **every** skill on write — it answers
"which instance produced this," automatically, with no human judgement. Gold
must mean *more*: a human, deliberately, vouching after use. So gold uses a
**separate key**:

- **Instance key** — `~/.config/skill-forge/identity/` (or `--home`). Auto-applied
  on every write. Purpose: provenance/tamper-evidence.
- **Gold key** — `~/.config/skill-forge/gold/` (distinct path; `--gold-home`
  override). Used *only* by `forge gold <slug>`, never automatically. Purpose:
  human attestation.

Both are Ed25519 (reuse the existing sign/verify). The distinction is purpose +
path + the fact that gold is a manual command, not a write-time side effect. A
skill signed by the instance key is *not* thereby gold; gold requires the gold
key over the gold attestation.

`GoldAttestation` (stored in `sources/{slug}.yml`, not skill frontmatter):

```
skill_origin: str        # the skill's origin (instance:slug:version) it vouches for
version: int             # the skill version vouched for
gold_public_key: str     # PEM of the gold key, so a reader can verify offline
signature: str           # gold-key signature over canonical (origin, version, "gold")
attested_at: datetime
```

`tier` is **derived**, never stored as a writable field. `derive_tier` is pure:

```
gold   if a valid GoldAttestation matches the skill's current origin+version
silver elif the latest judged run cites a passing calibration for its rubric_version
bronze elif the latest judged total ≥ threshold
(none)  otherwise   # not yet judged / below threshold
```

A gold attestation for v3 does **not** confer gold on v4 — re-attest after a
refine. (Same invariant as signatures: vouching is version-pinned.)

## 2. Silver = "the grader was in-spec when it scored"

Silver is not a per-skill score; it's a property of the *judging event*. A
bronze skill is silver iff:
- its latest `event=="judged"` run has `judge_provenance.rubric_version == V`, and
- there exists a `CalibrationRecord` with `rubric_version == V`, `passed == true`,
  and `calibrated_at` on/after that judge run's time.

So silver says: "this score was produced by a judge we had just shown still
ranks the human-vouched golds correctly." Re-calibrate after a rubric bump (V
changes) or the silver claim lapses — exactly the auditable behaviour we want.

## 3. Calibration: measure the grader, never create golds

`forge calibrate`:
1. Collect the **gold set** (live skills with a valid gold attestation) and
   optional known-weak fixtures (`tests/fixtures/weak/*` or a configured dir).
2. If `len(gold_set) < calibrate.min_gold` (default 3) → **abort with
   "insufficient gold set"** (exit 2). A calibration over 0–1 golds is
   meaningless; don't fake it.
3. Judge each sample (median-of-N, current rubric). Check: every gold ranks
   `total ≥ total_min` and every weak sample `< total_min`.
4. `passed = (all golds pass) and (all weak samples fail)`. Compute a simple
   agreement metric (fraction correctly classified).
5. Write a `CalibrationRecord` to the audit trail (`runs/` JSONL, `event ==
   "calibrated"`) with rubric_version, model, gold-set hash, per-sample
   results, agreement, passed.

The judge never confers gold — a human does (§1). Calibration only asks "does
the grader still agree with the humans?" The circularity is broken because the
ground truth (gold) is human-set and the grader is the thing under test.

`CalibrationRecord`:

```
rubric_version: str
model_id: str
gold_set_sha256: str       # hash of the sorted gold slug+version list
results: list[{slug, version, total, expected: "pass"|"fail", correct: bool}]
agreement: float           # fraction correct
passed: bool
calibrated_at: datetime
```

## 4. Tier is informational, not a gate

`tier` shows in `ls` and `forge tier <slug>`; it does **not** change promotion
(still total + axis floor). Gold/silver are trust signals for a human (or a
downstream consumer reading provenance over MCP), not an auto-promote lever.
This keeps `promoter` unchanged and avoids "gold skills auto-deploy" footguns.

## 5. Sequencing

Build order within the change: tier-derivation + gold key/attestation first
(self-contained), then calibrate + silver-citation on top (silver needs the
calibration record). Tasks reflect this. If review wants to split, the natural
seam is C1 = gold/tier, C2 = calibrate/silver.
