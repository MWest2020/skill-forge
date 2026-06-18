# skill-forge — strategy update (May 2026)

> **Update — June 2026 (read this first).** The **curation-first pivot** below
> held and is the shipped reality: import → judge → promote → refine, with
> lineage, provenance, and Ed25519 signatures. What did **not** survive is the
> **distribution endgame**. The whole sharing layer — federation (change #8),
> subscriptions, the broad MCP-over-HTTP server (change #7), and signed release
> bundles — was built in May 2026 and then **deliberately removed** in
> `strip-to-curation-core`: this is one person's curated library, not a network,
> and that layer was the part most likely to be superseded by first-party skill
> tooling. MCP later returned in `add-skillsets-and-mcp`, but **narrow**:
> read-only, stdio-only, three tools, scoped to a *skillset* (a `tags` query) so
> a containerized agent can pull a vetted subset — explicitly **not** the
> federation transport. So in the sections below, **"MCP server mode (change
> #7)", "Federation (change #8)", landscape point 3, and the federation-related
> non-goals/risks/deferred-decisions are historical** — read them as the
> thinking at the time, superseded by the two changes named above. The pivot,
> positioning, "what stays", and curation non-goals remain accurate.

## Why this document exists

`project.md` describes skill-forge as an extraction pipeline (sources → SKILL.md → judge → promote). After surveying the ecosystem (ClawHub, Skills.sh, SkillsDirectory, agentskills/agentskills, tech-leads-club/agent-skills, microsoft/skills, SkillFlow), this framing is too close to what already exists. This document records a deliberate scope pivot and the resulting roadmap change.

## What already exists (landscape, May 2026)

| Tool / project | What it does | Differentiator |
|---|---|---|
| ClawHub / Skills.sh / SkillsDirectory | Marketplace distribution of community skills | Browse + install |
| agentskills/agentskills | SKILL.md specification + docs | Standard authoring format |
| tech-leads-club/agent-skills | Curated registry with Snyk Agent Scan | Security-vetted distribution |
| microsoft/skills | 174 hand-authored skills for Azure/Foundry | First-party vendor library |
| SkillFlow (arxiv 2504.06188) | Multi-stage retrieval over ~36K SKILL.md | Skill discovery as IR |
| Claude Code / OpenCode / Codex | Native skill loading from `.claude/skills/`, `.agents/skills/`, `.opencode/skills/` | Local skill consumption |

What no one does, that fits skill-forge's audit/sovereignty framing:

1. **Treat skills as artifacts that improve over time.** Marketplaces ship `latest`; curated lists ship `vetted`. Nobody publishes a deliberate refinement loop where each skill carries its iteration lineage.
2. **Pull provenance through the chain.** Source → extraction → refinement → publication, all with sha256, license, judge score, and instance signature. Today, provenance is mostly "trust the marketplace".
3. **Federation between self-hosted instances.** All current registries are centralized. There is no Mastodon-equivalent for skill libraries.

### Adjacent format — OKF (June 2026)

Google Cloud released the **Open Knowledge Format** (OKF v0.1): a vendor-neutral
markdown + YAML-frontmatter spec for *curated knowledge/context* (the "LLM-wiki"
pattern — schemas, metrics, runbooks, metadata catalogs). Structurally it is a
sibling of SKILL.md (markdown dir, frontmatter, git-diffable, no SDK), but it is
**a different layer: knowledge an agent reads, not a capability it runs.** OKF
is *not* a skills/agents standard and not a competitor to the Anthropic Skill
format — it is complementary (kennis vs. kunde). Decision: **do not build for it
now** (it lacks the skills layer and is pre-1.0). The durable lesson is
architectural — skill-forge's value (rubric scoring, trust tiers, calibration,
provenance) must stay **decoupled from the SKILL.md frontmatter schema**, so
adding OKF / MCP / a future format is an adapter, not a rewrite. For real
*skills* interop, track Anthropic's Agent Skills format and MCP, not OKF.

## The pivot

**Old framing:** skill-forge is an extraction pipeline producing fresh SKILL.md files from arbitrary sources.

**New framing:** skill-forge is a **curation and improvement** tool for an owned skill library. Extraction stays as one of several intake paths, but the value lives in the *iterate* loop: import → score → refine → score again → publish, with full lineage.

This affects positioning, roadmap, and what we build first.

## Positioning (one-liner candidates)

- `skill-forge — curate and refine your agent skills` (preferred)
- `skill-forge — owned, audited, federated skill libraries`
- `skill-forge — provenance for your SKILL.md`

The verb is **curate**, not harvest, discover, register, or distribute.

## What stays from the original plan

- License-aware intake (intake is still risky, regardless of source).
- LLM-backed judging against a rubric.
- Filesystem-as-database; git is the audit log.
- Flat-file storage under `skills/`, `sources/`, `runs/`.
- The completed work (`add-core-models-and-storage`, `add-extraction-pipeline`) is sound and stays.

## What changes

### Roadmap (new order)

The roadmap as written in `project.md` (changes #3 – #6) is **superseded** by:

1. **add-instance-identity** — Ed25519 keypair per install, instance ID, signature surface on Skill model. Foundation for federation and lineage attribution. (~1 day of work, no dependencies.)
2. **add-import-and-judge** — Manual import of an existing SKILL.md plus the judge-with-rubric capability. Replaces the old `add-judge-and-promotion` change. Promotion stays manual for now (`forge promote <slug>`). This unlocks the refinement loop.
3. **add-refinement-loop** — The core of the pivot. Take a skill + judge feedback (+ optionally a second source), produce a refined draft. Track every iteration. Side-by-side diff, human approve/reject.
4. **add-discovery** *(unchanged in scope, demoted in priority)* — Useful, not central. Pulled in once the curation loop is proven.
5. **add-ollama-provider** *(unchanged)* — Cost/latency for the judge stage. Stays where it is.
6. **add-plugin-bridges** *(new, see below)* — Make skill-forge useful inside the tools people already use.
7. **add-mcp-server-mode** *(new, see below)* — Expose skill-forge as an MCP server.
8. **add-federation** *(new, see below)* — Instance-to-instance trust + signed manifest exchange.

### Why "import" before "extraction continues"

The fetcher + distiller already work end-to-end. But the refinement loop needs the simplest possible intake: take an existing SKILL.md (hand-written, from another repo, exported from Claude Code), validate it, register provenance for it. That intake path is the input every other capability builds on.

Extraction is one way to produce an importable artifact. There are others: manual authoring, copying a skill from `.claude/skills/`, pulling from a peer instance. All of them land in the same import port.

## New strategic surfaces

### Plugin bridges (change #6)

Bidirectional integration with existing skill consumers. Two directions, both shallow:

**skill-forge → consumer:**
- `forge sync claude-code [--target ~/.claude/skills]` — copy promoted skills into a target directory the consumer reads natively.
- `forge sync opencode` / `forge sync codex` — same pattern, different conventional path.
- Symlinks where possible (changes propagate), copies otherwise.
- Per-target manifest of what was synced, so unsync is precise.

**consumer → skill-forge:**
- `forge import-dir ~/.claude/skills` — bulk-import existing skills with `origin: external/claude-code/<name>` provenance.
- Treat each imported skill as a draft until judged.

Out of scope for first pass: deep integration (running as a Claude Code plugin, exposing custom commands inside the consumer). Those are separate, larger changes.

### MCP server mode (change #7)

> **Superseded (June 2026).** Built then stripped; rebuilt narrow in
> `add-skillsets-and-mcp` — read-only, **stdio only** (no HTTP/token), three
> tools, no registry publishing. The HTTP/auth/registry surface below was cut.

Expose the skill library as an MCP server so any MCP-aware client (Claude Desktop, Claude Code, any agent) can read skills on demand instead of via filesystem sync.

- Transport: stdio (local) and Streamable HTTP (remote).
- Resources: `resources/list` returns slug + description; `resources/read` returns full SKILL.md.
- No tools in v1 — read-only. Tools (e.g., `refine_skill`) come later if useful.
- Auth: bearer token for HTTP. mTLS / Tailscale documented as recommended deployment, not enforced in code.
- Submission to the official MCP Registry (`io.github.MWest2020/skill-forge`) under `add-mcp-registry-publishing` (a sub-change inside this one or its own).

### Federation (change #8)

> **Descoped (June 2026).** Built in May 2026, removed in
> `strip-to-curation-core`. skill-forge is a single-person curated library, not
> a federation; do not reintroduce without a fresh proposal. The rest of this
> section is historical.

Peer instances exchange opt-in skills via signed manifests. Mastodon-style, not blockchain.

Three sub-decisions deferred until this change is actually started:

- **Protocol**: candidates are MCP-over-HTTP (eat own dog food), custom REST, or ActivityPub. Recommendation: MCP-over-HTTP, since (a) we already speak MCP after change #7, (b) `resources/list` is the natural federation endpoint, (c) it avoids inventing a second protocol.
- **Trust mode**: default to *reference-only* (peer skills visible in `forge ls --peer`, never copied without explicit pull). `auto-import` is dangerous; `review-queue` is the second-most permissive.
- **Visibility tiers per skill**: `private` / `unlisted` / `public`. Added to the frontmatter via change #1 (`add-instance-identity`) so we don't reissue every skill later.

## Non-goals (re-affirmed and expanded)

In addition to the existing non-goals (no scraping, no redistribution, no multi-user, no web UI):

- **No central registry.** Federation is peer-to-peer. We will not run skill-forge-hub.com.
- **No blockchain, no IPFS, no CRDT.** Signed manifests over HTTP. Conflicts resolved by humans.
- **No skill execution.** skill-forge stores and refines skills; it does not run them. That stays the consumer's job. **This non-goal is the sister-repo boundary** (see below).
- **No multi-tenant per instance.** One instance = one identity = one human's library. Multi-user comes via federation, not via in-instance accounts.

## When to spin out a sister-repo (not bloat skill-forge)

North star: **the best possible agents.** skill-forge is instrumental — the
trust/quality layer over curated context artifacts (skills first; the
rubric/tier/calibration/provenance machinery is format-independent). The natural
growth direction is trust shifting from **intrinsic** (does the rubric think the
SKILL.md looks good?) to **extrinsic** (does the artifact measurably make the
agent better on a task?). Extrinsic trust requires *running agents*, and the
`no skill execution` non-goal is the hard line.

So: the moment work must **execute agents**, not just store + judge artifacts,
it belongs in a **sister-repo** (e.g. `skill-eval` / `agent-bench`), not here.
Triggers:

1. It needs to **execute** agents against task suites.
2. It needs its own non-artifact data model/lifecycle (task suites, runs over
   time, outcome statistics).
3. Adding it would force skill-forge's core to take a runtime / eval-framework
   dependency it otherwise wouldn't.

The connection stays thin: the eval repo *consumes* vetted skills from
skill-forge; skill-forge *consumes* effectiveness scores back as one more judge
input. Two repos, one interface — do not merge them. Not a roadmap item now;
this is the signal to recognize it when it arrives.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Scope creep into a full marketplace | High | Strategy doc + explicit non-goals; every change proposal references this. |
| LLM-driven refinement degrades skill quality over iterations | Medium | Judge score is gated; refinement must strictly improve. Lineage makes regression visible. |
| Federation builds before curation is proven | Medium | Hard ordering: change #3 (refinement) must work end-to-end before #8 (federation) starts. |
| Naming collision with existing tools | Low | "skill-forge" is currently unclaimed on PyPI and the major MCP registries (checked May 2026). |
| Sovereignty framing reads as ideological, not technical | Low | EUPL-1.2 + technical artifacts (signatures, audit logs) make it concrete, not posturing. |

## Decisions deferred (do not block on these)

- Whether the EUPL-1.2 license stays once federation lands. Some federation patterns push toward AGPL-style copyleft for the server component. Re-evaluate at change #8 start.
- Whether `forge sync claude-code` should symlink or copy by default. Decide during change #6 implementation, based on Claude Code's actual filesystem-watching behavior.
- Whether to submit to community registries (mcp.so, Smithery, Glama) in parallel with the official MCP Registry. Decide during change #7.

## Decisions made

- The pivot from extraction-first to curation-first is final for this iteration.
- `add-instance-identity` is the next change. Everything else waits on it.
- The completed extraction-pipeline work is not regressed. It becomes one of several intake paths.
