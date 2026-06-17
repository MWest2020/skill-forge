# Trust tiers + judge calibration (group C)

## Why

The judge gate is binary: a skill is above threshold or not. But "passed the
LLM judge once" is a weaker claim than "a human vouched for this after using
it," and both are weaker if the judge itself has drifted. Three graded,
**cryptographically-grounded** trust levels make that explicit — the ISO-grade
version of "verified," where the tier is *derived from verifiable artifacts*,
never a field anyone can type:

- **bronze** — cleared the judge threshold. (What we have today.)
- **silver** — bronze *and* scored under a judge run that cites a **passing
  calibration**: evidence the grader itself was in-spec when it scored.
- **gold** — silver *and* carries a **human attestation**: a detached signature
  by a key the human controls, distinct from the instance auto-signature (#1b),
  placed deliberately after proven use.

Calibration closes the loop the rubric work opened: the **gold set is the
dataset**, the judge is the grader, and `forge calibrate` measures
grader-vs-ground-truth agreement. (The conceptual cousin of an external
eval-harness — but the ground truth is internal: skills humans have vouched
for.)

## What

- **A derived `tier`** (bronze | silver | gold), computed by `forge ls` / a new
  `forge tier <slug>` from verifiable inputs — **not** a writable frontmatter
  field. Typing `tier: gold` does nothing; only a valid gold attestation does.
- **Gold attestation** — `forge gold <slug>`: signs a detached attestation over
  `(origin, version, "gold")` with a **human gold key** (separate from the
  instance key). `forge tier`/`ls` verify it; a tampered or version-mismatched
  attestation does not confer gold.
- **`forge calibrate`** — runs the judge over the current gold set (+ optional
  known-weak fixtures), checks the golds rank at/above threshold and the weak
  samples below, and writes a **calibration record** (timestamp, rubric
  version, model, gold-set hash, per-sample pass/fail, agreement metric).
- **Silver derivation** — a bronze skill is reported silver iff its latest
  judged run was produced under a **passing calibration for the same
  `rubric_version`**. (The `rubric_version` already lives in judge provenance
  from make-judge-reproducible — this is the loop-closure.)

## Scope

- `models.py`: `GoldAttestation` + `CalibrationRecord`; a `Tier` enum and a
  pure `derive_tier(...)` that takes (judge provenance, calibration record,
  attestation) → tier. No writable tier field.
- `identity.py`: a second **gold keypair** (load/create at a distinct path) +
  sign/verify for attestations, reusing the existing Ed25519 machinery.
- `storage`/`audit`: persist attestations and calibration records (flat files,
  audit-trail-first, like everything else).
- `commands/`: `forge gold <slug>`, `forge calibrate`, `forge tier <slug>`;
  a Tier column on `ls`.
- Tests: tier derivation truth-table; attestation verify (tamper/version
  mismatch → not gold); calibration pass/fail + silver-citation.

## Out of scope

- Auto-promotion by tier (tier informs humans; it doesn't gate).
- Distributing/federating attestations (single-user; the gold key is local).
- The external eval-harness integration (ground truth is the internal gold set).
- Re-judging the whole library (operator action; orthogonal).

## Risks

- **Two-key confusion.** The instance auto-sig (provenance: "this instance
  wrote it") vs the gold key (attestation: "a human vouches"). Design §1 keeps
  them distinct in purpose, path, and verification; docs make it explicit.
- **Circular trust (gold set calibrates the judge that grades toward gold).**
  Real. Mitigated: gold is conferred by a *human*, not the judge; calibration
  only measures whether the judge still ranks the human-chosen golds correctly
  — it never *creates* golds. Design §3.
- **Tier as theatre.** The roadmap explicitly rejected a declarative "verified"
  badge. This is not that: tier is derived from a signature + a calibration
  record, both verifiable; a bare `tier:` field is ignored.
- **Calibration brittleness with a tiny gold set.** Early on there may be 0–1
  golds. `calibrate` must report "insufficient gold set (<N)" rather than
  produce a meaningless pass. Design §3.
