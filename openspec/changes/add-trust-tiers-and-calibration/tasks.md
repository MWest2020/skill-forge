# Tasks — add-trust-tiers-and-calibration

One commit per task. TDD: red test first. C1 (gold/tier) lands green before C2
(calibrate/silver) starts; each task is its own green commit.

## C1 — gold attestation + derived tier

- [x] **1. Models + `derive_tier`.** Add `Tier` (untiered|bronze|silver|gold),
  `GoldAttestation`, and `CalibrationRecord` to `models.py`; add a pure
  `derive_tier(judged, *, gold_valid, calibration, total_min, axis_min) -> Tier`
  (gold > silver > bronze > untiered, per spec). Tests: full truth-table
  including version/rubric/time mismatches → no upgrade.
- [x] **2. Gold key + attestation sign/verify.** In `identity.py`: load/create a
  **gold keypair** at a distinct path (`--gold-home`, default
  `~/.config/skill-forge/gold/`), 0600 hygiene; `sign_gold`/`verify_gold` over
  canonical `(origin, version, "gold")` bytes, reusing Ed25519. Tests: round
  trip; tampered/version-mismatched attestation fails verify.
- [x] **3. `forge gold` + `forge tier` + `ls` Tier column.** `forge gold <slug>`
  writes a `GoldAttestation` into `sources/{slug}.yml`; `forge tier <slug>`
  prints the derived tier + evidence; `ls` gains a Tier column. Tier reads the
  latest judged event + attestation (calibration None until C2). Tests via
  `CliRunner`: gold a judged skill → tier gold; refine lapses gold; unjudged →
  untiered.

## C2 — calibration + silver

- [x] **4. `forge calibrate`.** Collect the gold set (+ optional
  `calibrate.weak_dir` fixtures); abort < `calibrate.min_gold` (exit 2); judge
  each (median-of-N); `passed = golds≥threshold and weak<threshold`; write a
  `CalibrationRecord` (`event=="calibrated"`) to the audit trail; print summary.
  Config: `calibrate.min_gold` (3), `calibrate.weak_dir` (null). Tests: abort
  below min_gold; pass/fail classification; record persisted + readable.
- [x] **5. Silver derivation wired in.** `forge tier`/`ls` pass the latest
  passing `CalibrationRecord` into `derive_tier`, so a bronze skill judged under
  a passing same-version calibration reports silver. Tests: bronze→silver on a
  passing calibration; lapses on rubric bump or stale calibration.
- [ ] **6. Docs.** README: tiers (derived, verifiable, informational) + `gold`/
  `calibrate`/`tier`; #16 status row.

## Validate (gate before archive)

- [ ] All tasks checked; specs match code; `ruff`, `mypy --strict`, `pytest`
  green; files ≤ ~200 lines.
- [ ] Live smoke: `forge gold <a judged live skill>` then `forge tier <slug>`
  shows **gold**; tamper the attestation → drops below gold. No mocks.
