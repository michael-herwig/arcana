# ADR: Milestone-driver orchestrator — an autonomous loop across many hex runs

## Metadata

**Status:** Proposed
**Date:** 2026-07-22
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A
**Related PRD:** N/A
**Architectural Conventions:**
- [x] Decision follows this project's stated architectural conventions /
      golden path
- [ ] OR the deviation is justified in the Rationale section below
**Domain Tags:** developer-experience, integration, infrastructure
**Supersedes:** N/A (reuses [`adr_0002`](adr_0002_execution_scheduling_recursion.md)'s
`Depends-on` DAG and `Status` column at **issue** granularity, interacts
with [`adr_0004`](adr_0004_cross_repo_federation.md) federation and
[`adr_0005`](adr_0005_archive_fold_back.md) fold-back — see § Interaction
contracts)
**Superseded By:** N/A

## Context

The four hex orchestrators each deliver **one unit**: `/hex-architect` one
decision, `/hex-plan` one plan, `/hex-execute` one plan's worth of tested
code, `/hex-review` one diff. A feature that is a *milestone* — many
dependency-ordered issues that must all land coherently on one branch — has
no hex home. Today it is driven by a human (or an ad-hoc agent) invoking the
four skills in a loop by hand, per issue, keeping the issue order and the
branch state in their own head. **This ADR was authored by exactly such a
manual run**, which is the existence proof of both the demand and the gap.

**This capability exists, but only in the private OCX bundle hex was
generalized from** (`DESIGN.md:9`). Two OCX skills that were *not*
generalized carry it:

- **`swarm-loop`** (`ocx-soraka/.claude/skills/swarm-loop/SKILL.md`) — the
  inner primitive: delivers **one** issue end-to-end on a throwaway branch
  cut from a long-living branch (design → plan → TDD build → bounded
  review-fix loop → merge-commit → one-shot consistency pass), inside one
  subagent, returning only a compact report. This is what `/hex-execute`
  plus a per-issue `/hex-architect`/`/hex-plan`/`/hex-review` already cover
  between them.
- **`swarm-x`** (`ocx-soraka/.claude/skills/swarm-x/SKILL.md`) — the **outer
  loop**: splits a milestone into a dependency-ordered issue set, delivers
  each by repeating `swarm-loop` on a **single long-living feature branch**,
  runs a bounded milestone-completion review, and prepares a merge-ready PR.
  It holds only the master plan, the issue queue, and a cursor in context,
  delegating each issue's heavy work to a per-issue subagent.

**Why config cannot express this.** [`adr_0003`](adr_0003_configuration_customization_surface.md)
made the *inside* of one hex run project-configurable — the panel
(`perspectives`), the counts (`tiers.counts`), the routing
(`models.overrides`), the tier lineage (`tiers.inherits`), the adversary,
path-scoped roles (`when:` globs), and the phase plan itself
([`config.md § Workflows`](../../../hex/hex-core/references/config.md#workflows),
v2). Every one of those levers reshapes **a single invocation**: a
`workflows` fork rewrites one tier file's phase DAG *inside one run*
(`config.md` C-208 — "one header table, one `## Phase:` section per node"),
and that phase DAG is explicitly orthogonal to, and cannot reach across,
run boundaries (`config.md § Workflows` — edges are "within one file
only … no cross-file or cross-skill edges"). The milestone driver is
categorically the other thing: an **outer loop that invokes
`/hex-architect`, then `/hex-plan`, then `/hex-execute`, then `/hex-review`
as separate runs, N times, carrying a cursor between them**. No fork of a
tier file, and no key in the frozen v1/v2 vocabulary, can express a
multi-invocation loop. It is a new orchestrator or it is nothing —
[`config.md`](../../../hex/hex-core/references/config.md) is the wrong layer
by construction, and the swarm-to-config cookbook says so and defers here
(`config.md § Reproducing a role/phase swarm as config`).

So the milestone gap is the **one** swarm capability that survived
generalization unaddressed: not because it resisted config, but because it
lives one level above the layer config governs.

## Decision Drivers

- **Close the last generalization gap without breaking the four-skill
  contract.** `swarm-loop`'s work is already hex's; only `swarm-x`'s outer
  loop is missing. Whatever is added must *compose* the existing skills,
  not re-implement them.
- **State of record, not head-state.** The manual run's failure mode is that
  the issue order, cursor, and branch lifecycle live nowhere durable — an
  interrupted milestone cannot be resumed and a blocked issue is silently
  forgotten. The driver must externalize the cursor, exactly as
  `adr_0002`'s WP `Status` column externalizes work-package state
  (`adr_0002` C-107).
- **One gate, then autonomy.** `DESIGN.md`'s single meta-plan gate rule
  (`protocol.md § the meta-plan gate`) must hold at milestone scale: one
  human approval of the master plan, then the loop runs unattended — it must
  not stall waiting for N per-issue gates.
- **hex never pushes** (`protocol.md:408`; `DESIGN.md:165`). Unlike
  `swarm-x`, which opens a PR, the milestone driver stops **before** the PR,
  consistent with every other hex skill.
- **Bounded, always.** Every loop the driver runs — the per-issue review-fix
  loop and the milestone-completion loop — is capped
  (`config.md limits.loop-rounds`); no loop is unbounded, matching
  `swarm-x`'s `--max-review`/`--max-final` discipline.
- **Client is the runtime** (`DESIGN.md:320-322`). The driver ships as
  markdown (a `SKILL.md` dispatcher + tier files in the shipped layout,
  `DESIGN.md:20-21`); it invokes existing skills and `git`. No engine, no
  scheduler, no new file format — the milestone-plan is the existing plan
  Status-block discipline applied one level up.

## Industry Context & Research

Prior art is the OCX bundle itself: `swarm-x` (outer loop, cursor,
long-living branch, bounded completion review) and `swarm-loop` (per-issue
primitive), both cited above and read in full for this decision. The design
that follows is `swarm-x` re-expressed against hex's generalized contracts —
tiers, capability classes, the single gate, never-pushes — and reconciled
with the three ADRs that landed after generalization (`adr_0002` scheduling,
`adr_0004` federation, `adr_0005` fold-back), none of which existed when
`swarm-x` was written.

The relevant external landscape was already surveyed for the ADRs this one
builds on:
[`spec-federation-multi-repo.md`](../research/spec-federation-multi-repo.md)
(cross-repo coordination — Gerrit topics as the closest production analog to
a milestone spanning repos, and its explicit non-atomicity, feed `adr_0004`
and thus C-606 here) and
[`openspec-framework-analysis.md`](../research/openspec-framework-analysis.md)
(the fold-back gap C-607 keys on). No new research pass was run; this is a
composition decision over settled contracts, not a novel-mechanism one.

## Considered Options

The same worked example throughout: a milestone of five dependency-ordered
issues (`#1` a shared type, `#2`/`#3` two consumers depending on `#1`, `#4`
docs depending on `#2`/`#3`, `#5` an integration check depending on all),
delivered onto one long-living branch, reviewed as a whole, left for the
human to open the PR.

### Option A — New orchestrator skill `/hex-milestone` (recommended)

**Description:** a fifth orchestrator in the shipped skill layout
(`SKILL.md` dispatcher + `classify.md` + `overlays.md` + `tier-*.md`), the
generalized `swarm-x`. Phase A writes a master milestone-plan (issue-DAG +
cursor) and takes the single approval gate; Phase B loops per issue,
delegating each to a sub-orchestrator that runs the existing
architect→plan→execute→review-fix→merge sequence onto the long-living
branch; Phase C runs the bounded cross-issue acceptance review; Phase D
stops before the PR with a handoff.

| Pros | Cons |
|------|------|
| The outer-loop state (cursor, issue-DAG, long-living branch) gets a clear owner that none of the four existing skills can hold | A fifth orchestrator is a new install/README/catalog surface (`DESIGN.md:20-21`) |
| Composes the four skills unchanged — no contract re-scope; pure delegation | Adds a third recursion level (milestone→issue→worker) the concurrency cap must count (C-603) |
| Reuses `adr_0002` DAG/Status, `adr_0004` federation, `adr_0005` fold-back verbatim at issue grain | |

### Option B — Extend `/hex-execute` with a `--milestone` outer-loop mode

**Description:** no new skill; `/hex-execute` gains a mode that, given a
milestone, loops itself per issue on a long-living branch.

| Pros | Cons |
|------|------|
| No new install surface | Re-scopes `hex-execute`'s contract (one approved plan → tested code) into "many plans → a branch" — two different jobs in the bundle's second-largest dispatcher |
| | The outer loop must invoke `/hex-plan` and `/hex-review`, which `hex-execute` today never does — it would embed three other skills inside one, inverting the composition |
| | Milestone state (cursor, issue-DAG) has no home in a plan-scoped skill |

### Option C — Leave it to manual autonomous runs (do nothing)

**Description:** the status quo — a human or an ad-hoc agent invokes the four
skills per issue by hand, as this ADR was authored.

| Pros | Cons |
|------|------|
| Zero new surface; works today (existence proof: this document) | Unbounded, unresumable, no state of record — a blocked issue is silently dropped, an interrupted milestone cannot continue |
| Correct for a *loosely* coupled set of issues with no shared branch | Exactly the head-state failure the driver exists to remove; the single gate degrades into N ad-hoc approvals |

## Decision Outcome

**Chosen: Option A — a new `/hex-milestone` orchestrator.**

**Rationale.** The outer loop holds cross-invocation state — the issue-DAG,
the cursor, the long-living branch lifecycle — that is genuinely nobody's job
among the four existing skills, and giving it to `hex-execute` (Option B)
would fuse two contracts in the bundle's hot path and force one orchestrator
to embed the other three, inverting hex's composition direction. Option C is
today's reality: it works (this ADR proves it) but is unbounded,
unresumable, and stateless, which is precisely the gap. Option A pays a real
cost — a fifth orchestrator, and a third recursion level the concurrency cap
must account for — and buys the one thing config provably cannot express, by
composing the four skills rather than re-implementing any of them. The
milestone driver ships **no new mechanism**: the DAG and Status are
`adr_0002`'s, the federation column and `landing` state are `adr_0004`'s, the
fold is `adr_0005`'s, the loop bounds are `config.md`'s — the skill is the
loop that sequences them.

This is a **Proposed** decision. It is not implemented, and acceptance is the
decider's — the contracts below are the buildable spec if it is accepted.

### Consequences

**Positive:**
- The last un-generalized swarm capability gets a portable, client-neutral,
  tier-scaled home; a milestone becomes resumable and its cursor durable.
- The single meta-plan gate scales to milestone grain: one approval, then
  autonomy, with stop-and-report on genuine blocks.

**Negative:**
- A fifth orchestrator is permanent install/doc/catalog surface.
- A third recursion level raises the ceiling on concurrent live subagents;
  C-603 caps it, but the accounting is new.

**Risks:**
- An autonomous multi-issue loop compounds a wrong per-issue judgment across
  the branch. Mitigation: every per-issue merge is gated on its own converged
  Approve (C-602), and the cross-issue acceptance review (C-604) is the
  branch-level backstop before the human ever sees a PR.

## Normative specification — component contracts

Contracts are numbered `C-6xx`; UX scenarios `S-6xx` (range assigned at the
meta-plan gate; `adr_0001` `C-00x`, `adr_0002` `C-1xx`, `adr_0003` `C-2xx`,
`adr_0004` `C-3xx`, `adr_0005` `C-4xx`, `adr_0006` `C-5xx`). Home names the
single definition or edit site. Nothing below introduces a file format, a
parser, or a version marker.

| ID | Contract | Home |
|---|---|---|
| **C-601** | **The milestone-plan artifact and its cursor block.** `/hex-milestone` writes one master artifact (`.agents/plans/plan_milestone_<slug>.md` by default, project spec/plan conventions win — `memory.md`). Its issue table **reuses `adr_0002`'s `Depends on` and `Status` columns unchanged, one row per issue** (not per WP): `Issue \| Repo \| Scope \| Long-living branch \| Depends on \| Status`, with `Status ∈ {pending, active, merged, blocked}`. A `## Cursor` block names the active issue, the merged set, and any blocked issue with its reason. **The cursor is the state of record; branches are evidence** (the `adr_0002` C-107 discipline, one level up). A resumed `/hex-milestone <plan path>` reads the cursor and continues; it never re-derives progress from git alone. | new `hex-milestone/SKILL.md`; issue-table + cursor spec |
| **C-602** | **Issue-DAG → long-living-branch lifecycle.** One long-living feature branch per milestone (`hex/<milestone-slug>`, or the non-trunk branch already checked out — the `adr_0002`/`protocol.md` feature-branch rule, at milestone grain). Each `pending` issue whose deps are all `merged` is delivered on an **ephemeral child branch cut from the long-living branch**, then merged back with `--no-ff` **serialized in a valid topological order**, with the project's documented verification run after each merge (`protocol.md` merge discipline, reused verbatim at issue grain). Child branch deleted after merge; the long-living branch is never pushed. | `hex-milestone/SKILL.md` § Per-issue loop |
| **C-603** | **Per-issue delegation and the depth cap.** Each issue is delegated to **one** sub-orchestrator (a `deep-reasoning`-class coordinator; capability class, never a literal model — `models.md`) that runs the per-issue architect→plan→execute→review-fix→merge sequence and returns a compact report, keeping its tool output out of the milestone context. **Depth is capped at three levels: milestone (L0) → issue sub-orchestrator (L1) → workers, including `adr_0002`'s one level of coordinator sub-WP leaves (L2). Nothing at L2 spawns further.** The concurrency cap `min(8, max-workers)` (`config.md limits.max-workers` / `protocol.md` C-201) counts **recursively across all live levels**. Issues run in dependency order, **one `active` issue at a time by default** (see Open Questions); a blocked issue yields `active` to the next issue with satisfied deps rather than stalling the loop. | `hex-milestone/SKILL.md`; `models.md` (class, no literal) |
| **C-604** | **Cross-issue acceptance-review scope.** After the last issue merges, `/hex-milestone` runs **one** bounded milestone-completion review: `/hex-review` scoped to the **union diff of the whole milestone** — `<frozen-base>...<long-living-branch>` (under federation, the union across every participating repo — `adr_0004` C-309), **not** any single issue's diff — focused on milestone acceptance criteria and cross-issue coherence (shared contracts, naming, seams, docs). It is bounded by `config.md limits.loop-rounds`; oscillating findings auto-defer. This reuses `/hex-review` and `/hex-execute`'s fix loop unchanged; **only the scope generalizes** from one diff to the branch's union diff. | `hex-milestone/SKILL.md` § Completion review |
| **C-605** | **Stops before the PR; terminal state.** When the acceptance review passes (or its bound is hit), `/hex-milestone` runs the documented verification once more on the long-living branch, then **stops**. It **never opens, pushes, or merges a PR** (`protocol.md:408`). The handoff enumerates the branch(es) and the required landing order and hands off to the human (under federation, the per-repo branch list + landing order — `adr_0004` C-312). Terminal review state is `done` for a single-repo milestone, and **`landing` for a federated one** (`adr_0004` C-324), held open until the human lands every repo. | `hex-milestone/SKILL.md` § Handoff |
| **C-606** | **Federation interaction (`adr_0004`).** A milestone spanning repos is **lead-originated**: the `adr_0004` C-323 satellite halt applies to `/hex-milestone` too — run it from the lead, never a satellite. The issue table's `Repo` cell reuses `adr_0004` C-302's column grammar at issue grain (`.` = lead; an issue names the repo it lands in); the long-living branch is **one per repo sharing the milestone slug** (`adr_0004` C-304); the C-604 acceptance scope is the cross-repo union (C-309); the milestone stops at `landing` (C-605). **No new federation construct** — the driver consumes `adr_0004`'s entirely. A milestone with no `Repo` column is single-repo and every federation rule here is inert (`adr_0004`'s vacuous-when-absent discipline). | `hex-milestone/SKILL.md`; `adr_0004` (consumed, not extended) |
| **C-607** | **Fold-back interaction (`adr_0005`): per-issue fold, no milestone-terminal fold.** Each issue is its own plan reaching its own reviewed-and-converged terminal state, so **each issue folds its own `## Spec Deltas` at its per-issue terminal review, exactly per `adr_0005` C-402 — unchanged.** The C-604 milestone-completion review operates on the **branch**, carries **no `## Spec Deltas` block of its own**, and therefore **folds nothing**; a cross-issue coherence fix it surfaces is delivered as an ordinary follow-up issue whose own terminal review folds its deltas. This preserves `adr_0005`'s "fold only reviewed, converged work" invariant at issue grain and adds **no second fold path**. | `hex-milestone/SKILL.md`; `adr_0005` (consumed, not extended) |
| **C-608** | **One master-plan gate; sub-runs are non-interactive.** The single human approval is the **master-plan gate at the end of Phase A** (`protocol.md` the meta-plan gate, at milestone grain). Per-issue sub-orchestrators run **pre-approved / non-interactive** — the master gate is their approval, carried by the non-interactive flags `DESIGN.md` already keeps for override. A sub-orchestrator that would otherwise ask a mid-flow question **stops and reports to the milestone loop** (which marks the issue `blocked` and advances the cursor), and **never blocks the loop waiting for input**. No second gate, ever. | `hex-milestone/SKILL.md`; `protocol.md` the meta-plan gate |

**UX scenarios.**

| ID | Scenario |
|---|---|
| **S-601** | A 5-issue milestone. Phase A writes the issue-DAG + cursor and takes one approval; Phase B delivers `#1`, then `#2`/`#3`, then `#4`, then `#5` in dependency order onto `hex/<slug>`, updating the cursor after each merge; Phase C runs one bounded union-diff review; Phase D stops with a "open the PR yourself" handoff. |
| **S-602** | The milestone is interrupted after `#2` merges. Re-running `/hex-milestone <plan path>` reads the `## Cursor` (`merged: #1, #2`), resumes at `#3`, and never re-runs `#1`/`#2`. |
| **S-603** | `#3` hits a genuine block (unreachable dependency). The sub-orchestrator stops-and-reports; the loop marks `#3` `blocked`, advances to `#4` if its deps are met, and the handoff lists `#3` as unfinished with its reason — no fabricated completion (C-608). |
| **S-604** | A federated milestone spanning `ocx` (lead) + `ocx-mirror`. Run from the lead; issues carry `Repo` cells; two long-living branches share the slug; the acceptance review sees the cross-repo union; the milestone stops at `landing`, not `done` (C-605/C-606). |
| **S-605** | `#2` amends `C-002`; at `#2`'s per-issue terminal review the delta folds into the spec (adr_0005 C-402). The milestone-completion review writes no spec delta; a cross-issue naming fix it finds becomes follow-up issue `#6` (C-607). |
| **S-606** | Run from a satellite by mistake: `/hex-milestone` halts on the `adr_0004` C-323 satellite guard with the relaunch-from-lead fix line (C-606). |

## Non-Functional Requirements

| Axis | Impact of this decision |
|---|---|
| Scalability | Concurrency stays bounded by `min(8, max-workers)` counted recursively across the three levels (C-603); issues are sequential by default, so live-subagent count does not grow with milestone size. |
| Availability | Not affected — markdown, no runtime, no service. |
| Latency | A milestone is N sequential per-issue runs plus one completion review; wall-clock scales with issue count by construction, unchanged by this design. |
| Security | The autonomous loop delegates every diff to a sub-orchestrator whose own `reviewer:security` panel and the fold-back guards run unchanged; no new write surface beyond what `adr_0004`/`adr_0005` already price (federation writes, spec fold). No push, ever. |
| Cost | One extra orchestrator seat (L0) plus one coordinator per issue (L1); the marginal cost over the manual run is the milestone orchestrator itself, which holds only the cursor and delegates. |
| Operability | The cursor makes an interrupted milestone resumable and a blocked issue visible — the manual run's central operability gap, closed. |

## Constitution conformance

Read against `hex/DESIGN.md`, this decision is conformant, not deviating:

| Rule | Why it holds |
|---|---|
| Single meta-plan gate (`protocol.md`) | One master-plan gate, then autonomy; sub-runs non-interactive, stop-and-report on blocks (C-608). No mid-flow question, ever. |
| hex never pushes (`protocol.md:408`; `DESIGN.md:165`) | The milestone stops before the PR — the one place `swarm-x` differs from hex is removed (C-605). |
| Link, never copy; no second source of truth (`DESIGN.md:32-39`) | The driver consumes `adr_0002`/`adr_0004`/`adr_0005` verbatim and defines no parallel DAG, federation, or fold mechanism (C-601/C-606/C-607). |
| Capability classes, never literal model names (`models.md`) | The issue sub-orchestrator is named by class (`deep-reasoning` coordinator), never a model (C-603). |
| Client is the runtime; markdown only (`DESIGN.md:320-322`) | A `SKILL.md` dispatcher + tier files that invoke existing skills and `git`; no engine, no scheduler, no new file format (C-601). |
| Shipped skill layout (`DESIGN.md:20-21`) | Fifth orchestrator follows the same `SKILL.md`/`classify.md`/`overlays.md`/`tier-*.md` shape. |

## Open Questions

- [NEEDS CLARIFICATION: may unblocked *sibling* issues run in parallel —
  more than one `active` sub-orchestrator at once under the concurrency cap —
  or strictly one `active` issue at a time?] Recommended: **one `active`
  issue at a time in v1** — it matches `swarm-x`'s sequential cursor, keeps
  the recursive concurrency accounting (C-603) simple, and makes the merge
  serialization trivially correct; parallel independent issues are a later
  optimization gated on the same `(Repo, path)` disjointness check
  `adr_0004` C-316 already defines.
- [NEEDS CLARIFICATION: for a *federated* milestone, does a per-issue fold
  fire at that issue's own merge into the long-living branch, or wait for the
  milestone's `landing`?] Recommended: **at the issue's own converged Approve
  into the long-living branch** — the merge is the fold trigger (the work is
  reviewed and converged at that point, `adr_0005`'s precondition), and the
  milestone-level `landing` hold (C-605) governs only the trunk PR, not the
  spec fold. This keeps `adr_0005` C-402's keying intact and avoids batching
  N folds into one terminal step the completion review does not own.
- [NEEDS CLARIFICATION: must issues pre-exist in a tracker (a GitHub
  milestone, as `swarm-x` assumes), or may `/hex-milestone` split a free-text
  milestone into synthetic issue rows?] Recommended: **accept both** — a
  tracker milestone/issue list *or* a free-text milestone the Phase-A
  architect/plan pass splits into DAG rows; the **issue-table row is the unit
  of record either way**, with tracker issue numbers optional. hex is
  client-neutral (`DESIGN.md`) and must not hard-require GitHub the way
  `swarm-x` does.

## Links

- Related ADR: [adr_0002_execution_scheduling_recursion.md](adr_0002_execution_scheduling_recursion.md)
  — the `Depends-on` DAG and `Status` column this reuses at issue grain.
- Related ADR: [adr_0004_cross_repo_federation.md](adr_0004_cross_repo_federation.md)
  — the `Repo` column, shared-slug branches, cross-repo union scope, and
  `landing` state a federated milestone consumes (C-606).
- Related ADR: [adr_0005_archive_fold_back.md](adr_0005_archive_fold_back.md)
  — the per-issue spec fold the milestone does not duplicate (C-607).
- Config boundary: [config.md § Reproducing a role/phase swarm as config](../../../hex/hex-core/references/config.md)
  — the cookbook that defers the milestone capability here.
- Prior art: `ocx-soraka/.claude/skills/swarm-x/SKILL.md` (outer loop),
  `swarm-loop/SKILL.md` (per-issue primitive) — the un-generalized OCX
  skills this decision generalizes.

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-07-22 | hex-architect (autonomous milestone-authoring run) | Initial draft. Chosen Option A (new `/hex-milestone` orchestrator) over extending `hex-execute` (Option B) or the manual status quo (Option C). Contracts C-601…C-608, scenarios S-601…S-606, three open questions each with a recommended answer. Status **Proposed** — acceptance is the decider's. |
