# System Design: Execution scheduling and recursive orchestration

**Companion to** [`adr_0002_execution_scheduling_recursion.md`](adr_0002_execution_scheduling_recursion.md).
That ADR holds the decision, options, and trade-offs; **this doc is the
buildable spec** — full C4, the evolved contracts in full (exact table
shapes, pseudocode, announce formats, per-file changes), and the
migration/rollout plan. Date 2026-07-19. Status tracks the ADR (Accepted).

Contracts are numbered `C-1xx` (the ADR summarizes them; here they are in
full). Terms: **orchestrator** = the session-level skill (hex-execute);
**coordinator** = a spawned worker that fans out one level within a WP;
**leaf** = a terminal worker (builder/tester/reviewer) that never spawns.
Recursion chain, hex-capped: orchestrator → coordinator → leaf.

*`deep-reasoning` (used below) is adr_0001 C-001's renamed class (from
`strongest`; both ADRs Proposed). If adr_0002 lands first, read it as
`strongest`.*

---

## 1. C4 — Context

```
                        ┌─────────────────────────────────────────┐
                        │  Harness (Claude / Codex / Copilot /      │
                        │  OpenCode)                                │
                        │  provides: subagent spawn · nested spawn  │
                        │  · programmatic orchestration · model     │
                        │  tiers (worker classes + orchestrator     │
                        │  class, per adr_0001)                     │
                        └───────────────┬───────────────────────────┘
                                        │ capabilities detected per run
                                        ▼
   grim registry ──ships──►  hex bundle (hex-execute + hex-core contracts)
                                        │ reads/writes
                                        ▼
                        project: plan Parallelization table (state of
                        record) · .agents.md · feature branch
                                        │ one approval gate · lands branch
                                        ▼
                                     human (Michael)
```

The only new Context edges versus today: hex-execute now *reads* two more
harness capabilities (nested spawn, programmatic orchestration) and adapts —
it never stores them (adr_0001 pointers-not-copies).

## 2. C4 — Container

```
┌──────────────────────── hex-execute (session orchestrator) ────────────────┐
│  Dispatch → Schedule (internal) → per-WP launch loop → serialized merge gate│
│  · owns the single approval gate · owns the Parallelization table           │
│  · spawns coordinators (top-level WPs only) and leaves                       │
└───────────┬───────────────────────────────────────────────┬────────────────┘
            │ spawns (0..1 level)                              │ spawns (leaves)
            ▼                                                  ▼
┌──────── coordinator (worker) ────────┐              ┌──── leaf workers ─────┐
│  owns ONE WP · one worktree/branch   │              │ builder · tester ·    │
│  splits into dotted sub-WPs          │              │ reviewer · doc-       │
│  fans out leaves (parallel impl +    │─── spawns ──►│ reviewer · architect  │
│  parallel review) · tiny join loop   │   leaves     │ (NEVER spawn workers) │
│  · central verify · 1 summary out    │              └───────────────────────┘
└──────────────────────────────────────┘

shared state:  plan Parallelization table  (leaf rows → branch+worktree;
               parent rows → computed rollup, no branch)
integration:   ONE feature branch · serialized merge · verify before each
               fast-forward  (unchanged safety model)
```

Container-level invariants:
- Coordinators are spawned by the **orchestrator only**, for **top-level WPs
  only**. A coordinator spawns **leaves only** — never another coordinator.
  This is how the one-level cap is *hex-enforced* rather than
  harness-inherited (constraint: OpenCode allows unbounded nesting; the cap
  holds because the spawn prompts forbid deeper fan-out, not because the
  harness stops it).
- Merge integration is unchanged: frozen-base feature branch, serialized
  merge in a valid topological order, verify before fast-forward (bors/homu
  model). DAG changes *launch* timing, never *merge* discipline.

## 3. C4 — Component

```
Dispatch (unchanged: parse · resolve target · classify · overlays · GATE · announce)
   │
   ▼
Schedule  [C-102]  ── internal, non-gating ────────────────────────────────┐
   │  · reads Parallelization table                                         │
   │  · free-text target → builds mini-table inline                         │
   │  · computes ready-set = { leaf WP | all Depends-on are `merged` }       │
   │  · capability detector [C-107] picks fan-out mechanism / flatten        │
   │  · feeds the EXISTING announce block (no new gate)                      │
   ▼                                                                         │
Launch loop  [C-101]                                                         │
   │  while unfinished WPs:                                                  │
   │    launch ready-set (≤ concurrency cap); a WP meeting the granularity   │
   │    gate → coordinator [C-103]; else → leaf builder                      │
   │    on each merge → recompute ready-set                                  │
   ▼                                                                         │
Coordinator [C-103] (per qualifying WP)                                      │
   │  split → fan out leaves → tiny join loop [C-106] → central verify →     │
   │  one per-WP summary                                                     │
   ▼                                                                         │
Merge gate (serialized) → Status rollup [C-105] → convergence append [C-109]─┘
```

Only two components carry non-trivial logic and warrant code-level detail
(§ 4). Everything else is a prose contract (§ 5). *ponytail: pseudocode only
for the ready-set loop and the rollup — the two places a wrong implementation
silently misbehaves; the rest is unambiguous as prose.*

## 4. C4 — Code-level (only where warranted)

### 4.1 Ready-set launch loop (C-101)

Replaces the wave-barrier "run wave, wait, run next wave". Language-neutral:

```
launched = {}                      # WP ids dispatched this run
while any WP with Status in {pending, active} remains:
    ready = [ wp for wp in leaf_WPs
              if wp.Status == pending
              and wp.id not in launched
              and all(dep.Status == "merged" for dep in wp.depends_on) ]
    ready.sort(key=remaining_critical_path_len, reverse=True)  # CP-first
    batch = ready[: concurrency_cap - count_running()]  # count_running counts
                                             # leaves inside coordinators too
    for wp in batch:
        base = feature_branch_tip   # holds every merged dep (serialized integration)
        prepare_worktree(wp, base); wp.Status = active; launched.add(wp.id)
        if qualifies(wp):
            dispatch(coordinator, wp, fanout_budget=slot_share(concurrency_cap))
        else:
            dispatch(leaf_builder, wp)
    on_merge(wp):                  # serialized, one at a time
        run_verify(); wp.Status = "merged"; recompute_parent_rollup(wp)
    # loop re-evaluates `ready` after every merge — dep-ready WPs start at once
```

Two properties fall out for free: (a) a linear or all-wave-1 plan schedules
*identically* to wave-barrier (the ready-set equals wave membership when deps
align with waves) — backward compatible; (b) resume recomputes `ready` from
`merged` rows, so an interrupted run relaunches strictly more, never fewer,
WPs than wave-barrier resume.

**Base selection** reconciles with protocol.md's frozen-base rule (:213–215,
:220–221): under DAG launch a WP is eligible only once every dep is `merged`
— already on the feature branch — so its base is the current feature-branch
tip, which by serialized integration holds every merged dep. Wave-1 WPs base
on the frozen initial tip; later WPs on the tip after their deps merged.
protocol.md:220–221's "or on a dependency WP's tip" clause covers basing on
an *unmerged* dependency (pipelining), which DAG launch never does (eligibility
requires `merged`) — leave it a documented, unused option.

**Cap & priority:** `count_running()` counts leaves inside coordinators too,
so recursion never exceeds the global cap; the orchestrator gives each
coordinator a fan-out budget ≤ its slot's share (3 coordinators under an
8-cap get ~2 leaf slots each, not 4). `ready` is sorted critical-path-first
(longest remaining dependency chain first), so a shallow WP never starves the
critical path — the starvation the barrier prevented structurally; the plan
already marks the critical path.

### 4.2 Parent Status rollup (C-105) — the drift-avoidance rule

Parent Status is **never written directly**; it is recomputed on every child
write. This is the one genuinely new algorithm the schema needs (the GitLab
parent/child drift failure mode):

```
def rollup(parent):                          # called on every child status write
    kids = parent.children
    if any(k.Status == "failed" for k in kids):        return "failed"
    if all(k.Status == "merged" for k in kids)
       and join_check(parent):                          return "merged"
    if any(k.Status in {"active", "merged"} for k in kids): return "active"
    return "pending"                          # all children pending
```

`join_check(parent)` is the real integration-work gate: if a WP has genuine
join work (not just the sum of its children), that work is an **ordinary
sibling sub-WP row** (`WP3.3`, `Depends-on` the other children) with the same
4 statuses — no 5th status, no `.join` suffix. A parent with zero children
(every old plan) rolls up to its own literal status — the rule is vacuous,
old plans unchanged.

## 5. Contracts in full

### C-101 — DAG launch rule

**Home:** protocol.md § Parallel-by-default decomposition (sole source; the
"Waves are computed, not asserted" paragraph, protocol.md:171–177, is
extended). Full intended text to add:

> **Launch on dependency-ready, not wave.** A leaf WP is eligible the instant
> every WP in its `Depends-on` has Status `merged` — not when its whole wave
> is ready. The orchestrator maintains a ready-set and launches eligible WPs
> immediately, within the concurrency cap, recomputing on every merge.
> **Waves are a derived reporting view** (topological level, GitLab `needs`
> vs `stages`): shown in the table and the mermaid index for readability,
> never a launch gate. Merge stays serialized in a valid topological order —
> DAG changes launch timing, not merge discipline. A launching WP bases on the
> **current feature-branch tip** (it holds every merged dep by serialized
> integration); wave-1 WPs base on the frozen initial tip. protocol.md:220–221's
> "dependency WP's tip" clause is the never-taken pipelining option under DAG
> launch (deps are always `merged` at launch) — see § Worktree mechanics.

**Gains:** dep-ready WPs stop waiting on slow wave-mates. **Loses:** nothing —
waves were already computed, not asserted.

**Progress surface (what the barrier used to make implicit).** With no wave
barrier, surface live DAG state from the Status column (data already there):
a compact rollup line per coordinator (`WP3 [coordinator]: 2/4 sub-WPs
merged`, GitLab/Nx live-DAG precedent), and a **staleness flag** on any WP
`active` far beyond its peers (a hung WP no longer blocks anything visibly).
Surface only — no speculative re-execution (that would violate hex's one-pass
philosophy).

### C-102 — Schedule step

**Home:** hex-execute SKILL.md § Work packages (the centralizing site;
tier files point here). An orchestrator-internal step, folded into Discover,
**never a user gate**. Behavior:

1. Read the Parallelization table (or, for a **free-text target**, build a
   mini table inline — the free-text path's one new capability: give it the
   same `WP | Scope | Expected Files | Size | Wave | Depends on | Status`
   shape so it can use the DAG launcher; default to a single WP unless the
   target plainly names ≥3 disjoint areas — Open Question 2).
2. Compute the ready-set (C-101) and prepare ready WPs' worktrees.
3. Invoke the capability detector (C-107); pick the fan-out mechanism or
   decide to flatten.
4. Emit the resolved schedule into the **existing** announce block — no new
   question. Announce additions (extending hex-execute SKILL.md:150–156):

```
  Work packages: 5 WPs, DAG launch — ready now: WP1, WP2, WP4
             critical path WP1 → WP3 → WP5      (plan table)
  Recursion:  WP3 → coordinator (4 sub-tasks, decomposable)   (granularity gate)
              others → single builder                          (below gate)
  Models:    fast-balanced default; coordinator + architect → deep-reasoning  (models.md)
  Degraded:  no — nested spawn + programmatic orchestration available
```

### C-103 — `coordinator` role

**Home:** workers.md (new role, after `architect`). Full entry:

> ## coordinator
>
> **Mission** — own one work package that is itself 3+ independent
> sub-tasks; decompose it, run parallel implementation and parallel review
> *within* the WP, and return one aggregated result. The manager /
> agent-as-tool shape — the orchestrator keeps control and consumes one
> summary; this is **not** a handoff.
>
> **Preconditions (all required; else the orchestrator runs the WP with a
> single builder):** the WP holds **≥3 independent, WP-grain sub-tasks**, the
> work is **decomposable** (not tightly sequential / state-dependent), and no
> single sub-task touches >8–12 distinct files (split the WP instead). Grain
> and thresholds: [`hierarchical-execution-performance.md`](../research/hierarchical-execution-performance.md).
> The gate is orchestrator judgment, not a mechanical count — the conservative
> default is a single builder; spawn a coordinator only when the
> ≥3-independent-sub-task split is clear (mirrors free-text Open Q2).
>
> **Fan-out** — split the WP into dotted sub-WPs (`WP3.1`, `WP3.2`, …) as
> ordinary rows in the plan table (C-105), inside the WP's **single**
> worktree/branch — **no sub-branches** (git ref collision). Spawn **leaf**
> workers only (builder/tester/reviewer) via the mechanism the orchestrator
> passed in (C-107); **never spawn another coordinator**. A sub-task needing
> true filesystem isolation → a sibling worktree on a hyphenated leaf branch
> `hex/<plan>/<wp>--<sub>`, never a deeper slash path.
> At split time, **topologically sort** the sub-WP DAG; a cycle means the
> split is not decomposable → fall back to a single builder (the
> granularity-gate fallback), no new failure path. Before spawning, **re-run
> the plan-time file-set intersection check** on the sub-WPs (protocol.md §
> parallel-by-default): sub-WPs sharing a file become sequential steps of one
> sub-WP, never concurrent leaves — in one shared worktree there is no
> branch-isolation net, so this check is mandatory. Stay within the **fan-out
> budget** the orchestrator passed (≤ the WP's share of the global concurrency
> cap), so concurrent leaves never push the recursive total over the cap.
>
> **Join** — run the tiny review loop (C-106), funnel every sub-WP through
> **the same centralized verify gate** the orchestrator uses (mandatory —
> the 4.4x-vs-17.2x error-amplification difference), then return **one per-WP
> summary** (the ffwll small-unit rule — never a raw pile of sub-worker
> output). Child state is scoped to the coordinator; it never leaks upward
> beyond the summary. Leaf verification follows the amended Implement-phase
> rule (protocol.md § Review-Fix Loop — migration #11, the single source):
> a leaf under a coordinator runs a scoped compile check only, never concurrent
> full verification in the shared worktree (concurrent test runs race on shared
> build artifacts); the coordinator runs the one authoritative verify at the
> join. **Commit on the WP's branch after each
> sub-WP join** — a reset point (extends hex-execute's commit-per-WP rule to
> sub-WP grain); on re-run, reset to the last committed sub-WP boundary so a
> killed coordinator never resumes into a half-edited tree.
>
> **Tools** — read, spawn leaf workers, run the project's verification. No
> direct edits (leaves edit). **Model** — [`models.md`](models.md) row
> `coordinator` — worker-tier `deep-reasoning`, **never orchestrator-class**
> ([`adr_0001` C-002](adr_0001_model_matrix_capability_classes.md)).
>
> ```
> Role: coordinator — own work package <WP-id>.
>
> Work package: <id, scope C-/S- IDs, declared file set>.
> Sub-tasks: <the ≥3 independent sub-tasks; their disjoint file subsets>.
> Fan-out mechanism: <programmatic-orchestration | nested-subagent> (from the orchestrator).
> Contract / design record: <plan sections to satisfy>.
>
> Split into dotted sub-WPs (disjoint file subsets), fan out leaf builders +
> testers in parallel, run a 1-round spec+quality review at the join, funnel
> every sub-WP through the project's documented verification, and return ONE
> summary. Never spawn another coordinator. Never leave a sub-WP unverified.
>
> Return:
> Summary: <pass | needs work | fail> for the whole WP
> Sub-WPs: <id — status — one line each>
> Deferred: <findings needing human judgment>
> Files changed: <union of sub-WP file sets — must stay inside the WP's declared set>
> ```

### C-104 — Single-level invariant amendment

**Home:** protocol.md § Worker coordination (protocol.md:144–145). **Lands
atomically with C-103** — never a state where workers.md ships a coordinator
but protocol.md still forbids nesting, or vice versa. Replacement text:

> The orchestrator decomposes work, dispatches workers using the spawn-prompt
> templates in [`workers.md`](workers.md), and synthesizes their structured
> returns. Workers never share state, and never spawn workers — **with one
> bounded exception: a `coordinator` (spawned by the orchestrator for a
> qualifying work package) fans out exactly one level of leaf workers within
> its work package.** Leaves never spawn. The depth chain is fixed at
> orchestrator → coordinator → leaf and is **hex-enforced** (the spawn
> prompts, not the harness, bound it — harness nesting caps vary and one is
> unbounded). The cap is one level because hex enforces it uniformly (Claude
> caps 5, Codex 1, OpenCode unbounded), and because spawn cost and error
> amplification compound 4–15x per level: a second level of fan-out rarely
> clears the granularity gate and risks the 17.2x uncoordinated-error regime
> the centralized verify gate exists to avoid.

### C-105 — Sub-WP schema

**Home:** plan.md template § Parallelization (add a dotted example row +
rollup note); protocol.md § Worktree mechanics (leaf-only branching). Same
columns, same 4 statuses, dotted IDs, one table:

| WP | Scope | Expected Files | Size | Wave | Depends on | Status |
|----|-------|----------------|------|------|------------|--------|
| WP3 | C-004, S-001 | `src/api/*.rs` | L | 2\* | WP1, WP2 | active *(rollup — computed)* |
| WP3.1 | C-004 | `src/api/handlers.rs` | M | 2 | *(inherits WP3's)* | merged |
| WP3.2 | S-001 | `src/api/routes.rs` | S | 3 | WP3.1 | active |

WP3.2 is **Wave 3**: it depends on WP3.1 (Wave 2), and the topological rule
(protocol.md:171–173) puts a WP one wave past its latest dependency. (The
source artifact `plan-schema-evolution.md:57` shows WP3.2 at Wave 2 — an
error; the topological rule makes it 3.) `2\*` on the parent = the min of its
children's waves — see the Parent Wave rule below.

Rules (all generalize an existing hex rule to a richer ID space):
- **Wave** — sub-WPs join the same global topological numbering; a derived
  reporting column (C-101), no wave-within-a-WP.
- **Parent Wave** — the **min** of its children's waves; cosmetic/reporting
  only (a parent row is never launched), marked (`2*`). Min because a parent
  is `active` as soon as any child starts, matching the rollup.
- **Depends-on inheritance** — absent → inherit the parent's; override for a
  tighter edge.
- **Branching** — **only leaf rows get a branch + worktree**; a parent with
  children is never itself branched (Dagster rule). Sub-WPs live in the
  parent WP's single worktree (C-103) unless they declare a true-isolation
  need.
- **Parent Status = computed rollup** (§ 4.2) — recomputed on every child
  write, never set directly.
- **IDs never renumbered** — next sibling = next integer (append-only,
  extends the C-00x discipline). **No schema-version marker** — the presence
  of dotted IDs is the signal.

### C-106 — Join-scoped review hierarchy

**Home:** the tiny-loop level is defined in the `coordinator` role (C-103,
workers.md), with a mapping pointer from hex-execute § Work packages; the
branch-level and swarm levels are **existing** behavior, no edit. Three scopes
by join size; **only the first is new** — the other two name existing behavior:

| Join | Scope | Breadth | New? |
|---|---|---|---|
| **WP join** (sub-WPs → WP result, inside a coordinator) | the sub-WP diffs | tiny loop: 1 round, spec + quality (Open Q1) | **new** |
| **Branch-level join** (a WP merges onto the feature branch) | the WP diff | the tier's role-diverse Review-Fix panel | existing (today's per-WP loop) |
| **Swarm** (feature branch → trunk) | the whole branch | `/hex-review` full staged panel | existing (the execute→review handoff) |

**ffwll guardrail:** each level reviews a **small unit** — the coordinator
returns a per-WP summary, and the branch-level panel reviews the *WP diff*,
never the coordinator's prose. This is the existing "orchestrator
synthesizes, never dumps raw worker output" rule (protocol.md:149–150)
applied to the new level. **Reviewer scaling:** grow role *diversity* across
levels (tiny → panel → staged), never same-role *count* (the ~5-role
plateau).

### C-107 — Capability gates

**Home:** protocol.md § Worker coordination (degraded mode). Promotes
[`adr_0001`](adr_0001_model_matrix_capability_classes.md)'s two deferred
capabilities to detect-and-announce gates, in C-003's stacked
`Degraded: <state> — <reason>` format (one line per degraded axis). Detected
per run, **never stored**, gated on **capability class, not primitive name**
(the harness surface churns — public docs and this session's surface already
disagree on nesting primitives). Mechanism selection at Schedule time:

1. `programmatic_orchestration` available → coordinator fans out via
   orchestration primitives inside the WP's single worktree (**preferred** —
   no sub-refs, documented budget).
2. else `nested_subagents` available → coordinator fans out via nested
   subagent spawns (**fallback** — watch session budget and the ref-collision
   rules; isolation only for true-isolation sub-WPs).
3. else → **degraded flattening**: no coordinators; the orchestrator runs
   every WP with a single builder + the normal per-WP panel. Announce:

```
Degraded: flat execution — no nested spawn; coordinators inlined
```

Stacks with adr_0001's other degraded lines, e.g. a harness with neither
nesting nor per-spawn override:

```
Degraded: flat execution — no nested spawn; coordinators inlined
Degraded: single session model — no per-spawn override; matrix advisory
```

### C-108 — models.md `coordinator` row

**Home:** models.md matrix. Add one row (`—` = never spawned at that tier):

| Role / focus | low | medium | high |
|---|---|---|---|
| coordinator | — | deep-reasoning | deep-reasoning |

Definition note under the matrix: "`coordinator` runs only at medium/high
(recursion is a fan-out optimization, absent at low's single-WP shape) and
resolves to the `deep-reasoning` **worker** class — never an
orchestrator-class model (adr_0001 § Rules, exclusion rule)." Reinforces
adr_0001 C-002.

### C-109 — Convergence append under DAG

**Home:** protocol.md § Convergence contract (protocol.md:316–318) and
hex-review SKILL.md:231–235. "Waves are derived" makes "append as one new
wave" ill-defined; the new primitive appends **rows**:

> **Append-only growth**: the orchestrator appends unmet-requirement gaps as
> new WP **rows** at the end of the Parallelization table, **with matching new
> Implementation Steps entries**, `Depends on` the delivered WPs; their **wave
> derives** as the next topological level (no explicit wave to assert).
> Existing WPs, sub-WPs, steps, and IDs are never rewritten or renumbered.
> Byte-identical when nothing is outstanding ("Converged").

hex-review SKILL.md:233 changes "appends any gap as one new wave" → "appends
any gap as new WP rows (their wave derives)".

## 6. Migration / rollout plan

`hex/` is untracked and unpublished — the free-now reversibility window
(adr_0001). The change lands in **two waves**; wave 1 is independently
shippable and *is* Option B (the perf-conservative MVP).

### 6.1 Edit sequence (the ~9 dependent sites)

Ordering rule (constraint): **C-104 and C-103 are one atomic change** — the
invariant amendment and the role addition land together. C-101 (DAG) is
independent and lands first.

| # | Site | Change | Wave | Depends on |
|---|---|---|---|---|
| 1 | protocol.md § Parallel-by-default (:171–177) | C-101 launch rule (sole source) | 1 | — |
| 1b | protocol.md § Worktree mechanics (:220–221) | annotate the "dependency WP's tip" base clause as the never-taken pipelining option under DAG (deps are `merged` at launch → base on feature-branch tip) | 1 | #1 |
| 2 | hex-execute SKILL.md § Work packages (:250–286) [Schedule step]; § Dispatch step 6 (:150–156) [announce additions] | C-102 (centralizing rewrite) | 1 | #1 |
| 3 | hex-execute tier-medium.md (:23–27), tier-high.md (:28–32) | replace "Phases run wave by wave" → "each WP launches once its own deps merge" (point at #1/#2) | 1 | #1,#2 |
| 4 | plan.md template § Parallelization (:130–134) | C-105 dotted example row + rollup note | 1 | — |
| 5 | protocol.md § Convergence (:316–318); hex-review SKILL.md (:233) | C-109 append-rows primitive | 1 | #1 |
| 5b | Merge-order sites → "valid topological order": protocol.md:224, hex-execute SKILL.md:3/:265, tier-medium.md:103, tier-high.md:123 (**"in wave / order" wraps across lines — join when editing**), plan.md:124/:154; + hex-plan tier-high.md:106 / tier-medium.md:111 / SKILL.md:237 ("wave-order merge plan") | restate merge order (waves derived) | 1 | #1 |
| 6 | protocol.md § Worker coordination (:144–145) | **C-104 invariant amendment** | 2 | #7 (atomic) |
| 7 | workers.md (after `architect`) | **C-103 coordinator role** | 2 | #6 (atomic) |
| 8 | models.md matrix | C-108 coordinator row | 2 | #7 |
| 9 | protocol.md § Worker coordination (degraded), § Worktree mechanics | C-107 capability gates + leaf-only branching | 2 | #6 |
| 10 | hex-execute SKILL.md § Work packages | coordinator spawn conditions + review-hierarchy pointers (C-106) | 2 | #7 |
| 11 | protocol.md § Review-Fix Loop, Implement phase (the canonical verify rule) | leaf-under-coordinator carve-out: scoped compile only; the coordinator's join verify is authoritative (closes G4) | 2 | #7 |

After the wave-1 rewrites, `grep -rnE "wave by wave|wave[ -]order" hex/` must
return zero (the `[ -]` also catches hyphenated `wave-order`).

### 6.2 Old plans (no sub-WP rows)

100% unchanged. Every new rule is vacuous on a childless plan: parent rollup
of zero children = the row's own literal status; DAG launch on a linear /
all-wave-1 plan is identical to wave-barrier; convergence still appends rows
(their derived wave = the old "one new wave"). No fallback, no version
detection — the absence of dotted IDs *is* the signal.

### 6.3 Interrupted runs (State: executing)

Resume is unchanged in shape and strictly more capable:
- Resume reads the table `Status` column (unchanged); DAG recomputes the
  ready-set from `merged` rows — relaunches more dep-ready WPs than
  wave-barrier resume would, never fewer.
- Sub-WP branches are just longer slugs; the existing branch-scan fallback
  finds them.
- **A coordinator interrupted mid-fan-out resumes for free**: its sub-WPs are
  ordinary table rows with their own status. Because programmatic-
  orchestration resume is same-session-only (tooling constraint), the
  orchestrator does not attempt to rehydrate the coordinator — it re-runs the
  WP's unfinished sub-WP rows directly (flat), since they are ordinary rows,
  resetting to the last committed sub-WP boundary (C-103). The schema design
  makes coordinator-resume a no-op over the normal WP-resume path. **The
  coordinator's WP-join tiny loop (C-106) is not re-established on resume** —
  accepted deliberately: the tiny loop is a convergence optimization, not a
  safety gate, and the branch-level panel (which always runs when the WP
  merges) is its backstop, so rebuilding coordinator state to recover a
  1-round pre-merge review is not worth it.

### 6.4 Reversibility & MVP boundary

- **Wave 1 alone is a coherent release** = Option B (DAG + Schedule). If
  recursion later proves troublesome, hex stops here having banked the free
  win. "Shippable after wave 1" is the MVP line.
- **Wave 2** adds recursion behind the granularity gate + capability detect;
  the sub-WP schema is additive (old plans byte-identical), so the only
  freezing contract is the `coordinator` role vocabulary + the invariant
  amendment — free to change until first `grim release`, breaking after.
- DAG launch itself is a two-way door (revert = a prose change; waves stay
  computed).

## 7. Open questions

Carried from the ADR (cap 3), each with a recommended answer that a plain
gate approval accepts:

1. WP-join tiny-loop breadth — **fixed spec+quality, 1 round** (diversity
   scales at the branch panel, not inside the coordinator).
2. Free-text decomposition — **single WP by default**; decompose only on ≥3
   plainly-disjoint named areas (no plan-review gate to catch bad boundaries).
3. Coordinator model cell — **deep-reasoning at medium+high, never low**
   (bounded within-WP fan-out decomposition — a worker task, not the
   session-level orchestration of adr_0001's excluded tier).

## 8. Links

- Decision: [`adr_0002_execution_scheduling_recursion.md`](adr_0002_execution_scheduling_recursion.md)
- adr_0001 (compatibility): [`adr_0001_model_matrix_capability_classes.md`](adr_0001_model_matrix_capability_classes.md)
- Research: [`../research/hierarchical-execution-performance.md`](../research/hierarchical-execution-performance.md) · [`../research/hierarchical-orchestration-precedent.md`](../research/hierarchical-orchestration-precedent.md) · [`../research/nested-execution-tooling.md`](../research/nested-execution-tooling.md) · [`../research/plan-schema-evolution.md`](../research/plan-schema-evolution.md)

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-07-19 | hex-architect (architect worker) | Initial draft — Proposed |
| 2026-07-19 | hex-architect (architect worker) | Review round 1 — 28 panel findings: DAG base-selection fix (feature-branch tip), critical-path-first + recursive cap, schema topological-wave correction + source note, parent-wave rule, depth-cap rationale corrected, acyclicity/disjointness/verify-contention/commit-boundary gaps, progress surface, merge-order migration completion, resume tiny-loop decision, casing + cite + home fixes |
| 2026-07-19 | hex-architect (architect worker) | Review round 3 — 4 residuals: verify carve-out amends the canonical protocol Implement-phase rule (single source, migration #11); C-101 add-text base = current feature-branch tip (consistent w/ pseudocode) + migration #1b; grep → `wave[ -]order` + row-5b line-wrap note |
| 2026-07-19 | Michael Herwig (via hex-execute gate) | Status Proposed → Accepted |
