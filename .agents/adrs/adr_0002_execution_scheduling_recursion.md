# ADR: Execution scheduling and recursive orchestration

## Metadata

**Status:** Accepted
**Date:** 2026-07-19
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A
**Related PRD:** N/A
**Architectural Conventions:**
- [x] Decision follows this project's stated architectural conventions /
      golden path (single-source contracts, pointers-not-copies,
      parallel-by-default, capability detect-and-announce, portability across
      four harnesses)
- [ ] OR the deviation is justified in the Rationale section below
**Domain Tags:** infrastructure, integration
**Supersedes:** N/A (relates to
[`adr_0001`](adr_0001_model_matrix_capability_classes.md); does not supersede)
**Superseded By:** N/A

**Companion:** the full C4, migration/rollout plan, and the contract bodies
(exact table shapes, pseudocode, announce formats) live in
[`adr_0002_system_design.md`](adr_0002_system_design.md). This ADR holds the
decision, the options, and the contract summaries; the system-design doc is
the buildable spec. Each fact has one home.

## Context

hex-execute runs a plan's work packages (WPs) in parallel git worktrees and
merges them onto one feature branch. Today two things bound how much parallel
work happens and how deep it goes:

- **Wave-barrier launch.** WPs launch a whole wave at a time: "a wave's WPs
  run concurrently; the next wave starts once the WPs it depends on have
  merged" (hex-execute tier-medium.md:26–27, tier-high.md:31–32). A WP whose
  own dependencies have merged still waits for its slowest wave-mate. The
  wave is *already* a derived topological level (protocol.md:171–177, "waves
  are computed, not asserted") — but it currently gates launch.
- **Single-level workers.** "Workers never share state and never spawn
  workers (single level only)" (protocol.md:144–145). A WP that is really 3+
  independent sub-tasks is executed by one builder, serially inside the WP.

Michael wants execution parallelized further: DAG-driven launch, an internal
scheduling step (not a second user gate), fork-join with tiny review loops at
small joins and swarm review at large joins, and recursion mapped to each
harness's capability. The research (four artifacts, below) says the DAG win
is near-free and the recursion win is real but only above a concrete
granularity threshold.

This is **one decision** — how hex schedules and (optionally) recurses during
execution — with five coupled facets: (1) DAG-driven launch; (2) an internal
Schedule step; (3) a `coordinator` worker role that fans out within a WP;
(4) a join-scoped review hierarchy; (5) promotion of adr_0001's deferred
`nested_subagents` + `programmatic_orchestration` capabilities to
detect-and-announce gates. Facet 1 is separable and strictly-better; facets
3–5 are coupled and gated. Reversibility window: `hex/` is untracked and
unpublished — the same free-now window adr_0001 relies on (see One-way-door
flag).

## Decision Drivers

- **Parallelize execution** (Michael's explicit want) without adding
  coordination risk the research warns of.
- **No second user gate** — the single meta-plan approval gate stays the only
  approval point (protocol.md § meta-plan gate). Scheduling is internal.
- **Perf-safety** — coordination cost grows superlinearly with fan-out;
  recursion must be gated, not default (see Industry Context).
- **Single-source contracts** — one definition site per rule; ~9 dependent
  sites reference it. The wave-barrier has one true source (protocol.md) and
  9+ operationally dependent sites; the change must keep one source.
- **Backward compatibility** — old plans execute byte-identical; interrupted
  runs resume unchanged.
- **Portability across four harnesses** — nesting depth differs per harness
  (Claude 5, Codex 1, OpenCode unbounded/buggy); the depth cap must be
  hex-enforced, not harness-inherited.
- **adr_0001 compatibility** — the new role is a spawned *worker* (worker-tier
  model class, never orchestrator-class); new capability gates reuse
  adr_0001's C-003 stacked-`Degraded` format; design against capability
  *class*, not a named primitive (adr_0001's churn rating).
- **Reversibility window** — contract changes are free before first release,
  breaking after.

## Industry Context & Research

Four research artifacts inform this decision (all in
[`../research/`](../research/), 2026-07-19):

- **[`hierarchical-execution-performance.md`](../research/hierarchical-execution-performance.md)**
  — *the perf gate.* Coordination cost is superlinear (USL crosstalk term
  quadratic in N; a Google preprint measures coordination turns ~N^1.7 and
  error amplification 1.0x single → 4.4x centralized → 17.2x independent).
  **DAG launch is near-free** (coordination unchanged, only wait discipline
  changes) — adopt without hedging. **Recursion pays only above a granularity
  threshold**: ≥3 independent WP-grain sub-tasks AND decomposable work; below
  it, single-agent wins under equal budget (Stanford), spawn overhead
  (4–15x tokens) dominates. **Every sub-orchestrator funnels through the same
  centralized verify gate** — empirically the 4.4x-vs-17.2x difference.
  Reviewers plateau at ~5 same-role; grow role diversity, not count.
- **[`hierarchical-orchestration-precedent.md`](../research/hierarchical-orchestration-precedent.md)**
  — *the pattern.* Every mature precedent (OTP/Akka supervision, ForkJoin,
  Buck2/GitLab `needs`, LangGraph subgraphs, Linux maintainer tree) converges
  on: launch-on-dependency-ready beats wave barriers with no correctness
  cost; recursive fan-out is safe only when depth is hard-capped and
  granularity-gated; review scopes small at the leaf and widens only on local
  failure. A sub-orchestrator is the **manager / agent-as-tool** shape (one
  aggregated result to one join point), **not handoff**; child state scoped so
  it can't leak upward. **ffwll guardrail** (Linux "Maintainers Don't Scale"):
  each review level's reviewable unit must stay small (per-WP summaries, not
  raw piles) or the level rubber-stamps.
- **[`nested-execution-tooling.md`](../research/nested-execution-tooling.md)**
  — *the mechanics.* Git ref collision is hard: branch `hex/plan/wp` blocks
  `hex/plan/wp/sub` ("cannot lock ref"). Recommendation: within-WP fan-out
  runs on **programmatic-orchestration primitives inside the WP's single
  worktree/branch — no sub-refs ever**. Cross-harness nesting differs
  (Claude 5, Codex 1, OpenCode unbounded bug) → **hex-enforced depth cap**.
  Harness capability surface is version-volatile (this session exposes a
  one-level nesting primitive the public docs the researcher read do not) →
  design against the capability class.
- **[`plan-schema-evolution.md`](../research/plan-schema-evolution.md)**
  — *the data model.* Extend by ID string alone: dotted sub-WP IDs (`WP3.1`)
  in the **same table, same columns, same 4 statuses**, no schema-version
  marker. Parent Status = **computed rollup, never independently mutable**
  (GitLab hit real parent/child status drift storing them separately). Only
  leaf rows get branch+worktree (Dagster: a group is never itself
  schedulable). Wave column becomes derived reporting (GitLab `needs` vs
  `stages`). Old plans with zero sub-rows are byte-identical.

**Key insight:** the DAG win and the recursion win have opposite risk
profiles — DAG is strictly better and unconditional; recursion is upside-only
*above a threshold* and negative below it. The right shape adopts DAG
unconditionally and gates recursion behind the research's own threshold, so
the perf-conservative position is reached structurally rather than by
forbidding recursion.

## Considered Options

Each option is scored on the same criteria in the Trade-off matrix below.

### Option A: Full adoption — DAG launch + coordinator + join hierarchy + capability gates

**Description:** Adopt all five facets. DAG-driven launch (a WP is eligible
the instant its *own* declared deps have merged; waves demoted to derived
reporting). An internal Schedule step computes the ready-set and builds a
mini-table for free-text targets — never a user gate. A `coordinator` worker
role fans out parallel implement + parallel review **within** a WP, gated by
the ≥3-independent-sub-task threshold, capped at **one** extra recursion
level, funnelling through the same centralized verify gate, returning one
aggregated result (manager shape). Review is join-scoped (tiny loop at the
WP join, panel at the branch-level merge, swarm `/hex-review` at the end).
The two nesting capabilities become detect-and-announce gates with degraded
flattening.

| Pros | Cons |
|------|------|
| Gets the free DAG win *and* the gated recursion upside | Largest change: ~9 contract sites + a new role + schema rule |
| Granularity gate + centralized verify encode B's perf-caution structurally (recursion off by default, fires only above threshold) | Amends the single-level invariant — a semi-one-way contract change |
| Coordinator resumes as flat sub-WP rows for free (sub-WPs are ordinary table rows) | Two new capability gates to detect per run |
| Wave-1 of the migration = Option B, a coherent shippable MVP | |

### Option B: DAG launch only — recursion stays forbidden

**Description:** Adopt facets 1 and 2 (DAG launch + the Schedule step, which
DAG needs anyway). Keep the single-level invariant; no coordinator, no
sub-WPs. The perf-conservative option.

| Pros | Cons |
|------|------|
| Captures the strictly-better, near-free DAG win with zero new coordination risk | Forecloses the recursion upside permanently — a WP that is 3+ independent sub-tasks stays serial |
| Smallest diff; no invariant amendment; no new role | Leaves Michael's fork-join / tiny-loop want unmet |
| Honestly half-supported by the data (coding a poor multi-agent fit; single-context wins on sequential work under equal budget) | The caution it buys, A already buys via the granularity gate — B pays for it by giving up the upside |

### Option C: Recursion-in-worktree only — waves stay

**Description:** Add the coordinator but keep wave-barrier launch (no DAG).

| Pros | Cons |
|------|------|
| Minimal change to launch machinery | Adds the *risky* part (recursion) and skips the *free* part (DAG) — inverts the risk/reward the research establishes |
| Delivers the fork-join want | Wave barrier still strands dep-ready WPs, now including sub-WPs — the barrier bites harder with more nodes |
| | Reversibility: same invariant amendment as A, without A's DAG payoff |

## Decision Outcome

**Chosen Option: A**, with DAG adopted unconditionally and recursion gated.

Per facet, one-line rationale each:

1. **DAG-driven launch — adopt unconditionally.** Near-free win, no new
   coordination risk; generalizes the existing "waves are computed"
   stance (protocol.md:171–177) from the *reporting* view to the *launch*
   discipline. Merge stays serialized (verify before fast-forward) — DAG
   changes launch timing only, never merge safety. Below the perf artifact's
   ~30%-off-critical-path threshold the ready-set equals wave membership, so
   DAG degenerates to wave-equivalent scheduling — "unconditional" is never
   *worse* than the barrier even when it buys nothing.
2. **Internal Schedule step — adopt, non-gating.** Folds into Discover;
   computes the ready-set, feeds the *existing* announce block, and builds a
   mini-table for free-text targets (their one genuinely new capability). Not
   a second gate (Michael's explicit constraint).
3. **`coordinator` role — adopt, gated.** Manager/agent-as-tool shape, gated
   by ≥3 independent WP-grain sub-tasks + decomposable work, one extra
   recursion level (hex-enforced), centralized verify mandatory, one
   aggregated result, scoped child state. Worker-tier `deep-reasoning`
   model class — never orchestrator-class (adr_0001 C-002).
4. **Join-scoped review hierarchy — adopt; mostly existing behavior.** The
   branch-level panel *is* today's per-WP Review-Fix Loop; the swarm level
   *is* today's end-of-branch `/hex-review`. Only the coordinator's internal
   tiny loop is new. The ffwll small-unit guardrail maps onto hex's existing
   "synthesize, never dump raw output" rule (protocol.md:149–150).
5. **Capability gates — adopt, detect-and-announce.** `nested_subagents` and
   `programmatic_orchestration` move from adr_0001's deferred-YAGNI bucket to
   C-003-format gates, exactly as adr_0001 anticipated ("represent when a hex
   behavior needs one"). Degraded flattening when nesting is unavailable.

**Rationale:** Read the matrix honestly — on the seven shipped-state
criteria **B wins or ties A on every one**: B is smaller, safer, more
reversible, and less capability-dependent, because it simply does less. A's
case does **not** rest on out-scoring B cell-by-cell; it rests on one fact
captured only by the eighth row (**preserved option value**): **A's migration
wave 1 IS Option B**, so choosing A costs nothing B saves — wave 1 is
shippable alone — while keeping the recursion option B forecloses permanently.
And A's recursion is not a general speedup: plan-time parallel-by-default
already splits file-disjoint work into separate WPs, so the coordinator only
reaches the file-grain sub-parallelism a WP was deliberately kept
module-grained to hide, or that surfaces only during implementation. So A = B
plus a gated, niche upside for the WPs that clear the granularity threshold,
at no cost to the wave-1 increment. A dominates C because C takes recursion's
cost while skipping DAG's free benefit — the worst trade on the frontier. The
migration makes A safe to adopt incrementally: if recursion proves
troublesome, hex stops after wave 1 having already banked the DAG win.

### One-way-door flag

Two contract changes freeze at first `grim release`, not before:

- **The single-level invariant amendment** (protocol.md:144–145) + the
  `coordinator` role in workers.md. Once consumers' plans carry dotted
  sub-WP IDs, removing the role orphans those rows. **Mitigation is narrow:**
  dotted IDs are additive and *inert for pre-existing plans* (a plan with
  zero sub-rows is byte-identical). That is **not** reversibility — once any
  consumer plan carries dotted sub-WP IDs, reverting the role/schema orphans
  those rows. Additive-for-old-plans buys a clean introduction, not a clean
  retreat; that is exactly why the "land it now" window (untracked `hex/`)
  matters. Per adr_0001's window logic.
- **DAG launch** is a two-way door: it is a launch-timing change over the
  same table; reverting to wave-barrier is a prose change (waves are still
  computed either way). Low risk.

Cost of both is **zero now** (`hex/` untracked) and increases monotonically
from first commit, then first publish — the adr_0001 framing.

### Quantified Impact

Not applicable as hard metrics — hex ships markdown contracts, and wall-clock
/ token effects are workload-dependent (the research gives *directional*
exponents, not hex-specific numbers; inventing figures would violate the
no-fabricated-metrics rule). Directionally: DAG launch removes straggler wait
on the critical path's off-path WPs; gated recursion trades 4–15x sub-tree
token cost for wall-clock only where ≥3 sub-tasks parallelize. Covered
qualitatively in NFRs.

### Consequences

**Positive:**
- Dep-ready WPs stop waiting on slow wave-mates; critical path bounds
  wall-clock, not the widest wave.
- WPs that are genuinely 3+ independent sub-tasks parallelize internally
  instead of running serial — a **niche** win: plan-time parallel-by-default
  already exposes file-disjoint work as separate WPs, so the coordinator only
  reaches the file-grain sub-parallelism a WP was deliberately kept
  module-grained to hide, or that surfaces only during implementation.
- Free-text targets gain the same DAG machinery via the mini-table.
- Interrupted coordinators resume as flat sub-WP execution for free (schema
  design: sub-WPs are ordinary rows).
- adr_0001's deferred capabilities get a clean, anticipated promotion.

**Negative:**
- The single-level invariant, a load-bearing simplicity, gains an exception
  (bounded to one level, gated, hex-capped).
- More nodes in the plan table (sub-WP rows) and a computed-rollup rule to
  maintain.
- Two more capabilities to detect and announce per run.

**Risks:**
- *Recursion fires below its useful grain* → wasted spawn cost. Mitigation:
  the granularity gate is a hard precondition checked at Schedule time; below
  it, one builder runs the WP (no coordinator).
- *Parent/child Status drift* (the GitLab failure mode). Mitigation: parent
  Status is a computed rollup, recomputed on every child write, never set
  directly (C-105).
- *Coordinator hides a large diff behind one summary* (rubber-stamp).
  Mitigation: the ffwll rule — the coordinator returns a per-WP summary; the
  branch-level panel still reviews the WP diff, not the coordinator's prose.
- *Harness nesting surface churns.* Mitigation: gate on capability class,
  detect per run, degraded-flatten — never store, never name the primitive
  (adr_0001 C-003's degraded-gate format + its pointers-not-copies correction).

## Trade-off matrix

Weighted qualitative scoring (`++` strong, `+` positive, `0` neutral, `−`
negative). No fabricated numbers — weights are relative importance, not
measured.

The first seven rows score the two as **shipped states** — where B, doing
less, wins or ties throughout. The eighth row is the one the shipped-state
criteria cannot capture and the actual reason A is chosen. It weights the
*irreversibility of the door*, not the size of the payoff — which is why it
carries high weight despite recursion's merely niche wall-clock gain.

| Criterion (weight) | A: full | B: DAG-only | C: recursion+waves |
|---|---|---|---|
| Perf-safety / error amplification (high) | `+` gate + centralized verify hold 4.4x | `++` no recursion at all | `−` recursion without DAG's off-path relief |
| Wall-clock upside (high) | `+` DAG + a niche within-WP gain | `+` DAG | `+` fan-out, but barrier strands WPs |
| Diff / complexity cost (med) | `−` largest | `++` smallest | `0` medium, worst-placed |
| Reversibility (med) | `0` inert for old plans, but not reversible once adopted | `++` two-way door | `−` invariant amend, no DAG payoff |
| Alignment w/ research thresholds (high) | `+` DAG + *conditionally*-supported recursion, gated | `+` adopts the uncontested DAG finding | `−` ignores the DAG finding |
| adr_0001 compatibility (med) | `++` worker-tier role, C-003 gates | `++` untouched | `+` role added, gates same |
| Resilience to capability churn (med) | `+` class-gated, detect-and-announce | `++` no nesting dependency | `+` class-gated |
| **Preserved option value** — recursion for above-threshold WPs (high) | `++` keeps it, gated | `−` forecloses it until first release (re-adoption after is a breaking change, not impossible) | `+` keeps it, worse-scheduled |
| **Verdict** | **Chosen — for the option value, at wave-1=B cost** | Strong MVP (= A wave 1) | Rejected |

## Component contracts (summary)

Numbered `C-1xx` to avoid colliding with adr_0001's `C-00x` when both are
cited downstream. Full bodies (exact table shapes, pseudocode, announce
formats, per-file gains/loses) are in
[`adr_0002_system_design.md`](adr_0002_system_design.md) § Contracts.

*Class-name note:* `deep-reasoning` below is adr_0001 C-001's renamed class
(from `strongest`; both ADRs are Proposed). adr_0002 presumes adr_0001 lands
first — if it lands second, read `deep-reasoning` as the then-current name
(`strongest`) and let adr_0001's rename sweep it.

| ID | Contract | Home / changed file |
|---|---|---|
| **C-101** | **DAG launch rule** — a leaf WP is eligible when every WP in its `Depends-on` is `merged`; the orchestrator maintains a ready-set, launches ready WPs immediately, **critical-path-first**, within the concurrency cap (counted **recursively** across coordinators), recomputes on each merge. A launching WP bases on the current feature-branch tip (it contains all merged deps). Waves become derived topological reporting, not a launch gate. | protocol.md § Parallel-by-default (sole source) |
| **C-102** | **Schedule step** — an orchestrator-internal, non-gating step in hex-execute: computes the ready-set, prepares ready WPs' worktrees, and for free-text targets builds an inline mini Parallelization table. Feeds the existing announce block; never a second gate. | hex-execute SKILL.md § Work packages |
| **C-103** | **`coordinator` role** — a spawned worker owning one WP; splits it into dotted sub-WPs, fans out parallel implement + parallel review within the WP's single worktree, funnels through the centralized verify gate, returns one aggregated per-WP summary (manager shape). Preconditions: ≥3 independent WP-grain sub-tasks AND decomposable. One extra recursion level, hex-enforced. Scoped child state. | workers.md (new role) |
| **C-104** | **Single-level invariant amendment** — "workers never spawn workers" gains one bounded exception: a `coordinator` fans out one level of leaf workers; leaves never spawn. Depth chain orchestrator → coordinator → leaf, hex-capped at one level — uniform across harnesses (nesting caps vary; OpenCode is unbounded) and because a second level rarely clears the granularity gate while compounding 4–15x spawn/error cost. **Lands atomically with C-103.** | protocol.md § Worker coordination |
| **C-105** | **Sub-WP schema** — dotted IDs (`WP3.1`) in the same table, same columns, same 4 statuses; parent Status = computed rollup (never set directly); only leaf rows get branch+worktree; `Depends-on` inherits parent's when absent; no schema-version marker; old plans byte-identical. | plan.md template; protocol.md § Worktree mechanics |
| **C-106** | **Join-scoped review hierarchy** — tiny loop (1 round, spec+quality) at the WP join inside the coordinator; the tier's role-diverse panel at the branch-level merge (existing Review-Fix Loop); swarm `/hex-review` at the end. ffwll rule: each level reviews a small unit (per-WP summary), never a raw pile. | workers.md (C-103 tiny loop) + hex-execute pointer; branch/swarm levels existing — no edit (distinct from C-107/#11's protocol verify carve-out) |
| **C-107** | **Capability gates** — `programmatic_orchestration` (preferred fan-out mechanism) and `nested_subagents` (fallback) detected per run, announced in C-003's stacked `Degraded: <state> — <reason>` format. Neither → degraded flattening, announced in C-003 format (exact string is normative in the system-design C-107). Never stored; gate on class, not primitive name. | protocol.md § Worker coordination (degraded mode) |
| **C-108** | **models.md `coordinator` row** — `deep-reasoning` where it runs (medium/high), never at low, never orchestrator-class — reinforcing adr_0001 C-002. | models.md matrix |
| **C-109** | **Convergence append under DAG** — `/hex-review` appends convergence gaps as new WP *rows* (their wave derives as the next topological level), replacing "append as one new wave" now that waves are derived. | protocol.md § Convergence contract; hex-review SKILL.md:231–235 |

## C4 sketch

Full diagrams in the system-design doc. In brief:

```
Context   harness (nesting + orchestration capabilities + model tiers)
          → hex bundle → project (plan table + arcana.md) → human (one gate,
          lands the branch)
Container hex-execute orchestrator (session) · coordinator workers (spawned,
          one level) · leaf workers · plan Parallelization table (state of
          record) · feature branch + worktrees (serialized integration)
Component Schedule (ready-set) · DAG launcher (per-WP dep-ready) · coordinator
          (WP fan-out + join + tiny loop) · merge gate (serialized, central
          verify) · capability detector (announce) · convergence append
```

## Non-Functional Requirements

| Axis | Impact |
|---|---|
| Scalability | **Affected, positive & bounded.** DAG lifts throughput to the critical path; the coordinator lifts within-WP parallelism. Both bounded by the existing concurrency cap and the hex-enforced one-level depth cap — fan-out cannot runaway (contrast OpenCode's unbounded-nesting bug). |
| Availability | Not affected — no runtime service. |
| Latency (wall-clock) | **Affected: positive (DAG), niche (recursion).** DAG removes straggler wait on off-critical-path WPs — the general win. The coordinator's within-WP parallelism is a bounded, niche gain (only the sub-module file-grain work plan-time decomposition left inside a WP). Merge remains serialized (unchanged critical section). |
| Security | **Affected, neutral-to-positive.** The coordinator resolves to a worker-tier model, never orchestrator-class (no silent-fallback tier for security-sensitive fan-out). Each sub-WP's diff still passes the same review perspectives; the ffwll small-unit rule prevents a large security-relevant diff being rubber-stamped behind one summary. |
| Cost (tokens) | **Affected, gated.** Recursion adds 4–15x sub-tree token cost — spent only above the granularity gate, where it buys wall-clock. DAG is cost-neutral. |
| Operability | **Affected, mixed.** Gains: one scheduling model, waves as pure reporting, coordinator-resume falling back to flat sub-WP rows. Costs — the full new surface to reason about: the `coordinator` role, the granularity-gate judgment, the 3-level join hierarchy, DAG re-basing and topological-order merge logic, the parent-rollup rule, and two capability gates. The centralized verify gate is unchanged — one place to look when a merge fails. |

## Open Questions

`[NEEDS CLARIFICATION: Should the WP-join tiny loop's breadth be fixed
(spec+quality, 1 round) or tier-scaled like the branch panel?]` Recommended:
**fixed at spec+quality, 1 round.** The tiny loop exists only to converge a WP
before the coordinator returns; role-diversity scaling belongs at the larger
branch join (the ~5-role panel), per the perf finding that diversity — not
count — is where review value lives. Keeps the coordinator cheap.

`[NEEDS CLARIFICATION: For free-text targets, should Schedule attempt
multi-WP decomposition or run them as a single WP?]` Recommended: **single WP
by default; decompose only if the free-text target plainly names ≥3 disjoint
areas.** Free-text has no reviewed plan, so aggressive auto-decomposition
risks wrong file-set boundaries with no plan-review gate to catch them. Keep
the un-planned path conservative.

`[NEEDS CLARIFICATION: coordinator model cell — deep-reasoning at both medium
and high, or fast-balanced at medium?]` Recommended: **deep-reasoning wherever
it runs (medium + high), never at low.** The coordinator performs bounded
within-WP fan-out decomposition (splitting sub-tasks + synthesizing their
results) — a reasoning-heavy *worker* task, distinct from the session-level
orchestration that defines adr_0001's excluded tier. Revisit if medium
coordinators prove over-powered.

## Implementation Plan

Decomposition is left to `/hex-plan`; the C-1xx contracts are the inputs. Two
waves (full sequence and ordering in the system-design doc § Migration):
- **Wave 1 (DAG, independent, strictly-better = Option B):** C-101, C-102,
  C-109, C-105 schema rows in the template, and the "wave by wave" /
  "wave order" → "topological order" restatements across the tier files and
  the merge-order sites (full site list in the system-design § 6.1).
- **Wave 2 (recursion, coupled, gated):** C-103 + C-104 **atomic**, C-108,
  C-106, C-107, the coordinator spawn conditions in hex-execute § Work
  packages. Shippable-after-wave-1 is a real MVP boundary.
All of it is cheapest now (`hex/` untracked) and should land before first
`grim release`.

## Validation

- [ ] A plan with zero sub-WP rows is byte-identical under the new rules
      (every rollup vacuous) and executes as today.
- [ ] A linear/all-wave-1 plan schedules identically under DAG and wave-barrier.
- [ ] A WP below the granularity gate spawns one builder, no coordinator.
- [ ] A coordinator interrupted mid-fan-out resumes via its sub-WP rows.
- [ ] `grep -rnE "wave by wave|wave[ -]order" hex/` returns zero after the
      tier-file and merge-order rewrites (`[ -]` catches hyphenated `wave-order`).
- [ ] A no-nesting harness announces the flat-execution `Degraded` line and
      runs every WP without a coordinator.
- [ ] parent Status is never written directly — only recomputed from children.

## Links

- Companion system design: [`adr_0002_system_design.md`](adr_0002_system_design.md)
- Related: [`adr_0001_model_matrix_capability_classes.md`](adr_0001_model_matrix_capability_classes.md) (C-002 exclusion rule, C-003 degraded format, deferred-capability bucket)
- Research: [`../research/hierarchical-execution-performance.md`](../research/hierarchical-execution-performance.md) · [`../research/hierarchical-orchestration-precedent.md`](../research/hierarchical-orchestration-precedent.md) · [`../research/nested-execution-tooling.md`](../research/nested-execution-tooling.md) · [`../research/plan-schema-evolution.md`](../research/plan-schema-evolution.md)

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-07-19 | hex-architect (architect worker) | Initial draft — Proposed |
| 2026-07-19 | hex-architect (architect worker) | Review round 1 — 28 panel findings: option-value reframe (matrix honest, 8th row), niche-scoped wall-clock, reversibility distinction, depth-cap rationale corrected, cite fixes, critical-path-first + recursive cap, contract-summary corrections |
| 2026-07-19 | hex-architect (architect worker) | Review round 3 — C-106 home cell corrected (workers.md, not protocol.md); grep → `wave[ -]order`; polish: B option-value = foreclosed-until-release, option-value weights door-irreversibility not payoff size |
| 2026-07-19 | Michael Herwig (via hex-execute gate) | Status Proposed → Accepted |
