# ADR: Model-matrix capability vocabulary and harness-capability representation

## Metadata

**Status:** Accepted
**Date:** 2026-07-19
**Deciders:** Michael Herwig
**Issue/Ticket:** grimoire-rs/grimoire#26 (related — install-time capability templating; not owned here)
**Related PRD:** N/A
**Architectural Conventions:**
- [x] Decision follows this project's stated architectural conventions /
      golden path (single definition site, pointers-not-copies,
      destination-of-knowledge, portability across four harnesses)
- [ ] OR the deviation is justified in the Rationale section below
**Domain Tags:** integration, infrastructure
**Supersedes:** N/A
**Superseded By:** N/A

## Context

The hex model matrix ([`hex-core/references/models.md`](../../../hex/hex-core/references/models.md))
is the bundle's sole model-guidance site: every other file references its
capability classes by pointer (~20 sites; none redefine). Cells hold
**capability classes, never literal model names**, so the shipped bundle
stays portable across harnesses. Today there are two classes:
`fast-balanced` and `strongest`.

Three pressures make the current vocabulary wrong or incomplete:

- **(a) `strongest` is now a false superlative.** Anthropic shipped a model
  tier *above* Opus — Mythos-class (Fable 5 / Mythos 5, 2026-06-09),
  positioned as an orchestrator seat, not a fungible leaf worker. Claude
  Code's subagent schema lists `fable` as a distinct routing alias beside
  `opus`/`sonnet`/`haiku`. So the literally-strongest model is one hex must
  **never spawn as a worker** — yet the class named `strongest` maps to
  Opus precisely because it excludes that tier. The name now fights its own
  definition, and the decider finds it misleading.

- **(b) Harness capabilities have no representation.** hex's behavior
  depends on what the running harness can do (per-spawn model override,
  subagent spawning, an orchestrator tier). One such gate already exists —
  degraded mode when subagent spawning is unavailable
  ([`protocol.md`](../../../hex/hex-core/references/protocol.md) § Worker
  coordination). But `per_spawn_model_override=false` (verified absent on
  GitHub Copilot) makes the **entire per-role matrix inapplicable** — all
  workers share the session model — and hex has no gate for it. That is a
  live portability gap for one of the four vendors hex claims to support,
  not a speculative feature.

- **(c) The install-time / runtime split is undefined.** grimoire#26 will
  add install-time restricted-Jinja conditionals over capability *booleans*
  on the Vendor trait, rendered at materialize and then frozen until
  reinstall. hex must decide which knowledge that mechanism owns and which
  stays in hex's runtime (hex-init instantiation + per-run detection),
  given that model names churn quarterly and must never be baked frozen.

This is **one decision** — how the matrix represents vendor-dependent model
capability — with three facets. It is time-sensitive: `hex/` is untracked
and unpublished (v0.1.0, `ghcr.io/michael-herwig`, no release yet). Class
names are free to change **now**; after the first `grim release` they are a
semi-frozen contract that instantiated `arcana:hex` files in consumer
projects reference. See the one-way-door flag in Decision Outcome.

## Decision Drivers

- **Name honesty** — a class name must not require a disclaimer to be
  correct; a name that needs "strongest does not mean the strongest model"
  is the wrong name.
- **Single definition site** — `models.md` defines classes; ~20 other sites
  reference by pointer. The decision must keep exactly one definition site.
- **Portability across four harnesses** — Claude, Codex, Copilot, OpenCode.
  Shipped defaults must work unconfigured (no `.agents.md`), and must
  not silently misbehave where a capability is absent.
- **Pointers-not-copies / destination-of-knowledge** — every fact has one
  home; a stored copy of a live-harness property drifts. `arcana:hex` holds
  swarm preferences, not detected facts.
- **Resilience to model churn** — model rosters change quarterly; a new tier
  above today's strongest is now precedented. The vocabulary must survive
  the *next* tier without another rename.
- **Alignment with grimoire#26** — hex's split must fit #26's Vendor-trait
  boolean design, not redesign it. Whatever #26 bakes is frozen until
  reinstall.
- **Reversibility window** — renames are free before first release, a
  breaking contract change after. Spend the diff now.
- **Decider preference** — would not spawn orchestrator-class (Fable) agents
  as workers; finds `strongest` irritating/misleading. Weighed, not mandated.

## Industry Context & Research

**Research artifact:**
[`../research/harness-capability-landscape.md`](../research/harness-capability-landscape.md)
(technology/tooling axis, 2026-07-19).

**Trending approaches:** vendor model rosters and orchestration primitives
are churning faster than capability booleans. Anthropic's orchestrator-class
tier is ~6 weeks old; Claude Code's `Workflow`/"ultracode" primitive was
renamed within its own lifetime (`workflow` → `ultracode`, v2.1.160);
Copilot dropped Gemini as a first-class option (2026-05). Stable across the
same window: per-spawn model override, background execution, subagent spawn.

**Key insights driving this decision (from the artifact):**

- The `AgentDefinition.model` alias list (`fable`, …) is concrete evidence
  the harness already treats orchestrator-class as a **distinct routing
  target** — the exact ambiguity `strongest` blurs, already resolved in the
  harness schema. (code.claude.com/docs/en/agent-sdk/subagents)
- Fable 5 is "a Mythos-class model made safe for general use," whose safety
  classifiers can **silently fall back to Opus 4.8** on some requests — the
  orchestrator-tier model can downgrade mid-session. A naive "just use the
  orchestrator model as strongest" hides this; the exclusion rule sidesteps
  it entirely by keeping worker classes off that tier.
  (anthropic.com/news/claude-fable-5-mythos-5)
- Copilot docs **explicitly** state no per-agent model override in a session
  — a verified capability gap, not merely undocumented.
  (docs.github.com/en/copilot/how-tos/copilot-sdk/features/custom-agents)
- **MCP's `initialize` handshake** (each side declares features; effective
  set = intersection) is working prior art for boolean-capability +
  conditional-behavior — the pattern grimoire#26 wants, at protocol level.
  (modelcontextprotocol.info/specification/draft/basic/versioning)
- **No "caniuse for harnesses" exists.** AGENTS.md (60k+ projects, Linux
  Foundation Agentic AI Foundation) is context-sharing, not
  capability-declaration. grimoire's capability matrix fills a real gap —
  which means hex should keep its own needs minimal and let #26 generalize.

**Churn ratings used below:** per-spawn override, background exec, subagent
spawn — *stable*; nested-spawn depth — volatile detail; programmatic
orchestration, orchestrator-class tier — *volatile* (single-vendor, renamed
within own lifetime).

## Considered Options

Each option bundles a **vocabulary stance** and a **capability stance** —
they interact (the exclusion rule only reads cleanly under a non-superlative
name), so they are weighed together.

### Option A: Rename `strongest` → `deep-reasoning`; orchestrator-class as an exclusion rule; capability split by churn (runtime-first)

**Description:** Keep two classes. Rename `strongest` → `deep-reasoning`
(role-descriptive, non-superlative), keep `fast-balanced`. Add an explicit
**rule** to `models.md` that matrix cells never resolve to an
orchestrator-class model — those run the session, they are not spawn
targets. Represent harness capabilities by **runtime detection + announce**
(extending the existing degraded-mode gate) for the one capability hex uses
today and lacks a gate for (`per_spawn_model_override`); defer the three
speculative capabilities; keep model names in runtime instantiation. When
grimoire#26 ships, migrate the stable `per_spawn_model_override` gate to
install-time matrix-section baking.

| Pros (genuine A-vs-B/C differentiators) | Cons |
|------|------|
| Name honesty — the class stops lying and survives the next tier above Opus without a re-rename (A only; B keeps the false name) | 15 mechanical rename sites + 4 semantic edits (free now, one-way after release) |
| Orchestrator exclusion is a formal Rule + numbered contract with a validation gate, not B's informal prose note | Two representation mechanisms (rule for orchestrator-class, runtime gate for override) — slightly more to hold in the head |
| Two classes, one definition site — no new matrix row (vs C) | |

**Shared with B, not A-exclusive:** both A and B fix the Copilot portability
gap (matrix advisory when no override) and hand #26 exactly one boolean. A's
margin over B rests on name honesty, the decider preference, and free-now
timing — not on these.

### Option B: Keep `strongest`, add a definition note

**Description:** Leave the vocabulary and all ~20 sites untouched; add a
sentence to `models.md` — "`strongest` = deepest-reasoning *worker*-
appropriate class; orchestrator-class models excluded." Handle the Copilot
gap the same way (a note). Minimal diff.

| Pros | Cons |
|------|------|
| Smallest possible diff; zero rename churn | The name still fights its definition — every future reader re-hits the confusion |
| No contract-name change to freeze | A name needing a disclaimer is a smell; the note is load-bearing forever |
| | The decider's stated objection is unaddressed |
| | Post-release, "fix it properly later" is a breaking change — the window is now |

### Option C: Keep `strongest` = best worker quality; add a distinct `orchestrator` concept in the matrix

**Description:** The researcher's shape. Keep `strongest` meaning best
single-model worker quality; introduce an `orchestrator` capability
present only where the harness has the tier, falling back to `strongest`
otherwise — expressed as a matrix element (cell/row/column).

| Pros | Cons |
|------|------|
| Explicitly names the orchestrator tier as a first-class concept | **Incoherent in this matrix**: rows are spawn targets; the orchestrator is the session *reading* the matrix, never spawned by it |
| Keeps `strongest` unchanged (no rename) | Retains the false-superlative name |
| | Adds a concept that, placed anywhere in the matrix, is misused; placed as a rule it *is* Option A's rule |
| | The Fable→Opus silent fallback makes an "orchestrator cell" doubly ill-defined |
| | Reversibility: the new matrix element also freezes at first release — reverting it later is as breaking as A's rename, but for a concept that should not have shipped |

## Decision Outcome

**Chosen Option: A**, with the orchestrator-class insight from C absorbed as
a **rule** (not a matrix element), and the capability split resolved
runtime-first.

Per facet:

- **(a) Vocabulary — rename `strongest` → `deep-reasoning`.** Two classes;
  `fast-balanced` unchanged. Non-superlative and role-descriptive, so it
  survives the next tier above Opus without another rename. Alternative name
  `deliberate` considered (tighter System-1/System-2 parallel with `fast`);
  `deep-reasoning` chosen for clarity and closer form-parallel with the
  hyphenated `fast-balanced`. Final name is the decider's to veto (see Open
  Questions Q1).
- **Orchestrator-class — an exclusion rule in `models.md`, not a cell.**
  C's *insight* (orchestrator ≠ strongest worker) is correct; C's
  *mechanism* (a matrix element) is incoherent because every matrix row is a
  spawn target and the orchestrator is never spawned via the matrix. The
  rule doubles as the entire representation of the `orchestrator_tier_model`
  capability — no stored boolean, no tier-file consultation. This also
  honors the decider's "never spawn Fable as a worker" preference by
  construction.
- **(b)/(c) Capability representation — hybrid split by churn, runtime-first**
  (refining the research artifact's recommendation). *Sourcing note:* the
  artifact is internally inconsistent on its first axis — its capability
  table's first column measures *nested* spawn (a subagent spawning
  subagents: Claude's 5-level cap, Codex "unclear beyond one level"), while
  its recommendation glosses the same axis's boolean `subagent_spawn` as
  plain delegated spawn (spawning a worker *at all*). Those are two distinct
  axes. This ADR splits them — coining the name `nested_subagents` for the
  nested case (this ADR's term, not the source's) — and accounts for six
  capabilities:
  - **Plain delegated spawn** (spawn a worker at all) — hex's pre-existing
    gate: **already gated** (degraded mode → inline workers, protocol.md §
    Worker coordination). No change.
  - Of the five researched axes, **two** drive new representation:
    - `per_spawn_model_override` — **add a degraded-mode variant now**
      (runtime detect + announce; the matrix is advisory when false). Real
      gap today on Copilot; stable, so it is the one boolean handed to #26.
    - `orchestrator_tier_model` — represented by the exclusion **rule**
      above, applied once at instantiation; not a runtime gate.
  - The other **three** researched axes — `nested_subagents` (the table's
    first column, renamed here), `programmatic_orchestration`,
    `background_execution` — **deferred (YAGNI).** hex forbids nested spawn
    outright (single level only); orchestration and background exec are
    synchronous by protocol. Represent when a hex behavior needs one.
  - **Model names** (not a capability axis) — always runtime (hex-init
    instantiation, re-verified on re-entrant runs). Never install-time baked
    (quarterly churn).

  **Correction — capability booleans are not stored in `arcana:hex`** (contra
  the offered "record them as `arcana:hex` bullets" approach). A harness
  capability is a property of the live harness (it changes when the user
  switches client or the vendor ships a feature); storing it in a
  team-shared, committed file is a copy that drifts — a pointers-not-copies
  violation. The existing degraded gate got this right: **detect per run,
  announce, do not store.**

  *Why the class→model mapping is exempt, though it is also a stored harness
  property:* the two fail differently. A stale **model name** fails
  **loud** — the harness rejects an unknown model at spawn time,
  immediately. A stale **capability boolean** fails **silent** — it
  mis-selects a code path with no error. The mapping also already carries
  correction machinery a boolean would not: the resolution-order fallback to
  shipped class defaults (models.md § Rules, resolution order) and hex-init's
  re-audit of pointers on re-entrant runs (memory.md § Staleness). So the
  mapping's stored-ness is safe where a boolean's is not. (Promoting the
  mapping to runtime-verified as well is a viable future hardening — see
  Risks.) `arcana:hex` therefore keeps only the mapping and user
  *preferences* — an intentional policy to force a capability off would be a
  preference and could live there; none exists today (YAGNI).

**Rationale:** Option A is the only shape that makes the name honest, and
name honesty is the decider's stated need and a driver. The rename is not
gold-plating: it removes confusion (a deletion), adds no new concept (still
two classes), and is a **mechanical global replace that is free before
release and breaking after**. Spending it now, inside the reversibility
window, is exactly correct sequencing. B leaves a permanent load-bearing
disclaimer and defers a breaking change past the free window. C adds an
incoherent matrix element; its one good idea is captured as A's rule at
lower cost. The capability split follows the research churn ratings and the
bundle's own pointers-not-copies principle, and asks #26 for the minimum —
one proven boolean — rather than a speculative laundry list.

### One-way-door flag

**The class name becomes a frozen contract at the first `grim release`.**
Instantiated `arcana:hex` files in consumer projects reference class names
literally; renaming after release breaks every consumer's stored mapping.
The rename's cost is **zero now** — `hex/` is untracked, not even committed —
and increases monotonically: higher once committed and shared, breaking once
published. Do it now because this is the cheapest it will ever be, not
because a release is scheduled (none is). The `per_spawn_model_override`
boolean handed to #26 is a softer, grim-side-versioned contract — starting
with one and adding later is a two-way door.

### Quantified Impact

Not applicable — this is a vocabulary/config decision with no runtime metric
(latency, throughput, SLO) to move. Impact is on operability and
correctness, covered in NFRs.

### Consequences

**Positive:**
- The vocabulary stops lying and survives the next tier above Opus.
- The Copilot portability gap becomes explicit (announced) instead of a
  silent attempt to honor an inapplicable matrix.
- Security reviewers can no longer be accidentally routed to the
  silent-fallback orchestrator tier (exclusion rule); on Copilot, the loss
  of independent security-reviewer escalation is surfaced, not hidden.
- #26 receives a minimal, justified capability ask.

**Negative:**
- ~16–20 edit sites for the rename (mechanical, one-time, pre-release).
- Two representation mechanisms coexist (rule vs runtime gate) — documented,
  but more than one concept.

**Risks:**
- *Rename misses a site* → a dangling `strongest` reference. Mitigation: the
  files-changed list in Contracts is exhaustive; a post-edit
  `grep -rn strongest hex/` must return zero (or only historical CHANGELOG).
- *Deferred capability turns out needed sooner* (e.g. hex adopts the
  `Workflow` primitive). Mitigation: the runtime-detect-and-announce pattern
  is already established; adding a gate is additive, not a redesign.
- *Future hardening (not adopted now):* the class→model mapping could itself
  be runtime-verified each run rather than only re-audited by hex-init,
  making its staleness handling symmetric with the capability booleans.
  Deferred — the mapping's loud failure mode and existing resolution-order
  fallback make this low-value today (see the Decision Outcome derivation).

## Non-Functional Requirements

| Axis | Impact of this decision |
|---|---|
| Scalability | Not affected — no runtime scaling path changes. |
| Availability | Not affected. |
| Latency | Not affected at runtime (the rename is static text). Marginal: the `per_spawn_model_override=false` gate avoids dispatching per-role model pins the harness would ignore. |
| Security | **Affected, positively.** The exclusion rule keeps `reviewer:security` on the strongest *worker* model (e.g. Opus), never the orchestrator tier that can silently fall back mid-session. On Copilot, the gate announces that security review shares the session model and cannot be independently escalated — a real limitation made visible rather than silently under-delivered. |
| Cost | **Affected, marginally positive.** The exclusion rule prevents accidentally spawning the most expensive (orchestrator) tier as leaf workers at fan-out scale. Rename itself is cost-neutral. |
| Operability | **Affected, mixed.** Gains: the one-time pre-release rename churn buys clearer names; one added announce-line variant; hex-init re-verifies the instantiated mapping on re-entrant runs. Cost: two representation mechanisms coexist (exclusion rule vs runtime gate — see Consequences, Negative), a standing comprehension overhead. Net: modestly more operable. |

## Technical Details

### C4 sketch

```
Context
  grim registry ──ships──> hex bundle ──installed into──> project
       harness (Claude | Codex | Copilot | OpenCode)
         provides: model roster + capabilities (per-spawn override,
                    subagent spawn, orchestrator tier)

Container
  hex-core/references/  (shared contracts: models.md, protocol.md,
                         memory.md, workers.md)
  the four orchestrator skills  (hex-plan/execute/review/architect —
                         consume the contracts, print announce blocks)
  .agents.md     (per-project: instantiated class→model mapping
                         + swarm preferences — NOT capability booleans)

Component
  models.md  ──sole class-definition site + exclusion rule──┐
      │ pointer                                             │
  hex-init Step 4  ──instantiate: class→model mapping,      │
      │              apply exclusion rule, detect override──┤
  protocol.md degraded gate  ──per-run capability adapt,    │
      │                        announce (not store)─────────┤
  arcana:hex  <── stores mapping + prefs only ──────────────┘
  grimoire#26 (future)  ──install-time bake: per_spawn_model_override
                          gates the matrix section per vendor
```

### Contracts

Numbered `C-###` so a `/hex-plan` run can decompose this without
re-deriving the design (protocol.md § Traceability IDs). Each is testable.

**C-001 — Vocabulary (one definition site).** Two capability classes,
defined only in `models.md` § Capability classes:
- `fast-balanced` — *unchanged* — the capable default workhorse.
- `deep-reasoning` — *renamed from `strongest`* — the deliberate-reasoning
  class for one-way-door design, novel reasoning, and security-critical
  judgment. **Not a superlative:** it is the strongest *worker-appropriate*
  class, distinct from any orchestrator-class model that runs the session.

**C-002 — Exclusion rule** (new, `models.md` § Rules). Exact intended text:

> **Cells never resolve to an orchestrator-class model.** Some harnesses
> expose a model tier above their strongest *worker* model — an orchestrator
> seat that runs the session (e.g. Claude's Mythos-class: Fable / Mythos,
> above Opus). Those models are never spawn targets; the matrix governs
> spawned workers only. `deep-reasoning` maps to the strongest
> *worker-appropriate* model (e.g. Opus), never the orchestrator tier. The
> session/orchestrator model is the user's or harness's choice, outside this
> matrix.

**C-003 — Capability gate** (`protocol.md` § Worker coordination). Add a
degraded-mode variant alongside the existing subagent-spawn one:

> **Degraded mode (no per-spawn model override).** On a harness where all
> agents in a session share one model (e.g. Copilot), the per-role matrix is
> **advisory only** — every worker runs the session model. Announce at the
> gate as `Degraded: single session model — no per-spawn override; matrix
> advisory`. Escalation recommendations (e.g. `reviewer:security →
> deep-reasoning`) are still *shown* so the user sees what would escalate,
> but they are not independently routable.

Capability is **detected per run and announced, never stored** — same
pattern as the existing subagent-spawn gate. **Axes compose:** each gated
capability contributes its own `Degraded:` line; a harness lacking both
subagent spawning and per-spawn override prints both (inline workers *and*
single session model). The gate stacks one line per degraded axis rather
than defining a combined state. Line format is `Degraded: <state> —
<reason>`, extending protocol.md's base `Degraded: inline workers` line with
a reason suffix.

**C-004 — Instantiation** (`hex-init` SKILL.md Step 4). Step 4:
1. Presents the two classes as `fast-balanced` / `deep-reasoning`.
2. When mapping `deep-reasoning` → a literal model, applies C-002 — picks
   the strongest *worker-appropriate* model, never the orchestrator tier
   (Claude: Opus, not Fable).
3. Detects `per_spawn_model_override`; when false, records that the matrix is
   advisory (does not attempt a per-class mapping that cannot be honored).
4. Stores the resulting class→model **mapping** (and any per-row/cell
   overrides) in `arcana:hex`. **Never stores capability booleans.**

**C-005 — Storage + announce formats.**

`arcana:hex` instantiated mapping (concrete block):

```markdown
<!-- arcana:hex -->
## hex
- Models (instantiated for this harness): fast-balanced → Sonnet,
  deep-reasoning → Opus. Override: reviewer:security → Opus at every tier.
  (deep-reasoning never maps to the orchestrator-class tier — see models.md.)
- Cross-model adversary: `codex-adversary` skill.
- Limits: max-workers 6, loop rounds 3.
<!-- /arcana:hex -->
```

Orchestrator announce block, Models + Degraded lines (all four skills):

```
Models: fast-balanced default; architect + reviewer:security → deep-reasoning
        (arcana:hex instantiated — see models.md)
Degraded: no — subagent spawning + per-spawn model override available
```

…or, on a harness degraded on one or both axes — one `Degraded:` line per
degraded axis (C-003), here showing both:

```
Degraded: inline workers — no subagent spawning
Degraded: single session model — no per-spawn override; matrix advisory
```

**C-006 — grimoire#26 boundary.** Install-time baking (frozen until
reinstall) is limited to `per_spawn_model_override` gating the *rendering of
the matrix section* per vendor: a Copilot materialization replaces the
matrix with the advisory one-liner; Claude/Codex/OpenCode render the full
matrix. Install-time baking **never** touches class names (the frozen
contract — a rename is a hex bundle version bump, not a per-vendor render) or
model names (quarterly churn) or the volatile capabilities. Until #26 ships,
C-003 handles this at runtime; migration is optional and non-blocking.

**C-007 — Rename churn (files changed).** Exhaustive; a post-edit
`grep -rn 'strongest' hex/` must return zero non-historical hits.

*Semantic edits (definition + new rule/gate):*

| File | Gains | Loses |
|---|---|---|
| `hex-core/references/models.md` | renamed class + non-superlative definition (C-001); exclusion rule (C-002); note that no-override makes the matrix advisory | the false superlative |
| `hex-core/references/protocol.md` | degraded-mode variant (C-003); announce example (line 64) updated | nothing |
| `hex-core/references/memory.md` | arcana:hex example (lines 55–56) updated | nothing |
| `hex-init/SKILL.md` | Step 4 presents `deep-reasoning`, applies exclusion + override detection (C-004) | `strongest` references |

*Mechanical rename only (`strongest` → `deep-reasoning`, no semantic change).*
The 15 pointer sites, verified against `grep -rno strongest hex/`:
`workers.md:283`; `hex-plan/{SKILL.md:138, overlays.md:29, tier-high.md:72, tier-medium.md:74}`;
`hex-execute/{SKILL.md:150, tier-high.md:72,85}`;
`hex-review/{SKILL.md:156, tier-high.md:55,83}`;
`hex-architect/{SKILL.md:128,139, tier-high.md:69, tier-medium.md:65}`;
plus `DESIGN.md:87,90` (internal notes — update for consistency, not
load-bearing). **Do not touch the `fast-balanced` sites** that sit beside
these (`hex-plan/overlays.md:50`, `hex-plan/tier-medium.md:48`,
`hex-architect/overlays.md:40`, `hex-architect/tier-medium.md:42`,
`hex-execute/tier-high.md:47`) — `fast-balanced` is unchanged (Open
Questions Q1). Within `models.md` itself, `strongest` also appears across the
matrix cells and both examples (lines 30–37, 44–45, 59, 62) — all covered by
the C-001/C-002 semantic edit of that file, not a separate mechanical pass.

## Open Questions

`[NEEDS CLARIFICATION: Should `fast-balanced` also be renamed for parallel
structure with `deep-reasoning`?]` Recommended: **No** — keep
`fast-balanced`. It is not a superlative, collides with no tier, and
renaming it doubles the churn for zero honesty gain. Rename only what is
broken.

`[NEEDS CLARIFICATION: Is `deep-reasoning` the right class name, vs
`deliberate` or another?]` Recommended: **`deep-reasoning`** — clearest and
form-parallel with `fast-balanced`; `deliberate` is a viable
System-1/System-2 alternative. Decider's veto; cheap to settle now, frozen
at first release.

`[NEEDS CLARIFICATION: When #26 bakes the matrix section behind
`per_spawn_model_override`, should Copilot get a blank or an advisory
stub?]` Recommended: **advisory stub** ("matrix advisory only; all workers
share the session model") — preserves which roles *would* escalate; only
actionability is lost, not information. This is a #26-side rendering detail,
flagged for coordination.

## Implementation Plan

Left to a `/hex-plan` decomposition; the contracts above are the inputs. In
brief: (1) C-001/C-002 in `models.md`; (2) C-007 mechanical rename across the
15 pointer sites; (3) C-003 gate in `protocol.md`; (4) C-004 in `hex-init`
Step 4; (5) C-005 example updates in `memory.md`; (6) verify
`grep -rn 'strongest' hex/` is clean. C-006 is a coordination note for
grimoire#26, not hex code. All of it is cheapest now (`hex/` is untracked)
and should land before the first `grim release`, after which class-name
changes break consumers.

## Validation

- [ ] `grep -rn 'strongest' hex/` returns zero non-historical hits after the
      rename.
- [ ] `models.md` has exactly one class-definition site; every other site
      still references by pointer.
- [ ] A dry-run `hex-init` on a Claude harness maps `deep-reasoning` → Opus
      (never Fable) and stores mapping, not capability booleans.
- [ ] A Copilot-harness run announces the single-session-model degraded line.
- [ ] Security review of the routing change (reviewer:security path) — the
      exclusion rule does not weaken security-reviewer model selection.

## Links

- Research: [`../research/harness-capability-landscape.md`](../research/harness-capability-landscape.md)
- Definition site under decision: [`../../../hex/hex-core/references/models.md`](../../../hex/hex-core/references/models.md)
- Protocol precedent (degraded mode): [`../../../hex/hex-core/references/protocol.md`](../../../hex/hex-core/references/protocol.md)
- Related: grimoire-rs/grimoire#26 (install-time capability templating)
- Amended by [`adr_0002_execution_scheduling_recursion.md`](adr_0002_execution_scheduling_recursion.md): this ADR deferred `nested_subagents` partly because "hex forbids nested spawn outright" — adr_0002 introduces a bounded one-level exception (the `coordinator`) and promotes `nested_subagents` + `programmatic_orchestration` to detect-and-announce gates.

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-07-19 | hex-architect (architect worker) | Initial draft — Proposed |
| 2026-07-19 | hex-architect (architect worker) | Revision round 1 — 9 review findings addressed (counts corrected, A-vs-B Pros de-inflated, mapping-exemption derivation, degraded-axis composition, capability arithmetic, roman-numeral cross-refs removed) |
| 2026-07-19 | hex-architect (architect worker) | Revision round 3 — sourcing honesty: own the plain-vs-nested spawn split (research artifact conflates them under `subagent_spawn`); `nested_subagents` marked as this ADR's coined term; degraded line-format clause added |
| 2026-07-19 | hex-architect (architect worker) | Added Links forward-pointer — the `nested_subagents` deferral reason is amended by adr_0002 (bounded one-level coordinator exception) |
| 2026-07-19 | Michael Herwig (via hex-execute gate) | Status Proposed → Accepted |
