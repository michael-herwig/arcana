# ADR: Review by join level

## Metadata

**Status:** Proposed
**Date:** 2026-09-06
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A — raised from the execution-runtime program's dogfood
result (PR #3): a mid-sized MR took three days and a week of quota under
hex where six hours at a tenth of the cost was the pre-hex baseline
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below —
      this ADR **amends** `adr_0012`'s promise that a plan without the
      generation marker runs pre-`adr_0012` semantics byte-for-byte: the
      *review* axis now follows this ADR in every plan shape. Phases and
      model class keep `adr_0012`'s rule unchanged.
**Domain Tags:** infrastructure
**Supersedes:** the review-budget half of `adr_0012` (C-947 backstop,
`Review: panel` escape hatch, `self | light | panel` budget and its guard)
**Superseded By:** N/A

## Context

hex's review cost is a product of four factors — model round-trips ×
seats × rounds × work packages — and the current design multiplies all
four: every WP runs a per-tier perspective panel (2–7 seats) for up to 3
rounds, a plan containing any reduced WP then *requires* a branch-level
`/hex-review` at the plan's ceiling tier before it may reach its terminal
state (`adr_0012` C-947), and tier `high` adds a cross-model pass on top.
The `adr_0012` effective tier trimmed the first factor only for `S` WPs
at tier `low`; the benchmark's 3h06 → 30m01s held for exactly that case.
Everything else still pays the ladder.

The owner's verdict is that this is unusable, not slow: "minutes, not
hours", no extra full `/hex-review`, the inner review loops must read the
delta only and adopt project settings, and a bigger review loop is
justified only for a bigger merge — a sub-orchestrator of a
sub-orchestrator that has already run several bounded loops and now
joins them.

## Decision Drivers

- **Wall clock.** One leaf review must complete in minutes on a
  fast-balanced model; a deep-reasoning seat is spent once per aggregate,
  never once per WP.
- **Correctness over breadth.** A finding on a line the diff did not
  touch is noise that costs a fix round; reviewer input is the diff and
  the contract excerpt, nothing prose-shaped.
- **Reflexivity.** The same rule must hold at every nesting depth —
  orchestrator, coordinator, coordinator-of-coordinators — with the depth
  of review growing only where a join actually aggregates.
- **Project-tunable.** Seats, class, rounds and budget per level in
  `hex.md › Preferences`, overriding per level rather than per role.

## Considered Options

### Option 1: Tighten the existing ladder

Cap rounds at 2, make the trunk backstop opt-in, keep the per-WP panel.
Rejected: the panel seat count and the per-WP deep-reasoning spend are
the dominant term; "a little faster" was explicitly refused.

### Option 2: Review keyed on join level (chosen)

Tier scales execution only. Review depth is a function of *where a diff
joins*: `L0` inline evidence, `L1` one fast leaf reviewer at every leaf
join, `L2` one deep-reasoning seat over an aggregate when a node joins
two or more leaves, `L3` the trunk pass only on explicit `/hex-review`.

### Option 3: Single end-of-run review

No per-WP review at all; one panel over the branch at the end. Rejected:
loses the delta-scoped signal that makes fixes cheap, and one panel over
a large branch is the `O(N²)`-adjacent read the loop already refuses.

## Decision Outcome

Option 2. The contract lives once, in
[`hex-core/references/loop.md` § Review by join level](../../hex/hex-core/references/loop.md#review-by-join-level);
every other file links it. `hex/DESIGN.md` round 20 records the
constitutional consequences.

### Four levels (C-980)

| Level | Fires at | Seats | Class | Rounds | Budget | Input |
|---|---|---|---|---|---|---|
| `L0` inline | every builder return | 0 | — | 0 | — | the builder's evidence table, grep-verified by the orchestrator |
| `L1` leaf | a leaf's join (a WP or sub-WP branch lands) | 1 | fast-balanced | 1 | 10 min | `git diff <base>..<head>` + the contract excerpt |
| `L2` aggregate | a node joins **N ≥ 2** leaves | 1 | deep-reasoning | 1 | 20 min | the aggregate diff + the leaf verdicts |
| `L3` trunk | `/hex-review`, on invocation only | that skill's | that skill's | that skill's | — | the feature branch |

Every diff passes `L1` once, at the join nearest the builder that wrote
it; every aggregate passes `L2` once, at the node that assembled it. A
node whose child already ran `L2` takes the child's verdict as input and
does not re-run `L1` over the child's diff.

### The `N ≥ 2` rule (C-981)

`L2` exists only where there is an aggregate. A coordinator that split
its WP into one sub-WP, a plan with one WP, a run in which one WP landed
— each is `N = 1`, `L2` is skipped and the `L1` verdict stands. The
top-level orchestrator's `L2` fires once, at the end of the run, over
`<base>..HEAD` of the feature branch, with `N` = the WPs merged.

### Delta-only input (C-982)

A reviewer at `L1`/`L2` receives the diff and the WP's contract excerpt.
A finding must sit on a diff line or name a contradiction the diff
introduced; anything else is dropped, not deferred. A docs-only WP is
reviewed at `L0`: each requirement ID maps to a `path:line` the
orchestrator greps against the implementation — never a prose panel.

### Risk raises one level, never rounds (C-983)

`sec`, `hot` or `door` true — at spawn or at the merge-time re-derivation
over the actual diff — reviews one level above the join: `L0 → L1`,
`L1 → L2` (the one single-leaf `L2`), `L2 → L2` with the security and
performance checklists forced on. Never a round, never `L3`. The plan's
`Review` cell survives as an author-declared fifth source: `risk` raises
the same way; legacy `panel` reads `risk`; `self` and `light` are inert.

### Budget expiry ends the loop (C-984)

Each level carries `budget-minutes`. A seat that has not returned inside
it is stopped, `review budget expired: <level> <WP> — residue: <…>` goes
to the handoff's deferred list, and the WP proceeds. Expiry is a
deferred finding, never a failure and never a re-run.

### Configuration per level (C-985)

`review.<level>.{seats, class, rounds, budget-minutes, delta-only}` in
`hex.md › Preferences`, `<level>` ∈ `l1 | l2`. `review.<level>.class`
wins over `models.overrides` for review seats; `models.overrides` keeps
governing every non-review role. `limits.loop-rounds` becomes a ceiling
over every level's `rounds` (hard maximum 3). `perspectives.always` /
`never` act on the `L2` seat's checklist and on `L3`'s panel; the
`--review` overlay axis selects the `L2` checklist breadth (`minimal |
full | adversarial`), never a seat count.

### Retired (C-986)

The per-WP `self | light | panel` budget and both halves of its guard;
the `Review: panel` escape hatch (effective-tier resolution step 5); the
branch-review precondition and the `adr_0012 backstop` announce line
(C-947); the "review grows by diversity across join levels" three-scope
model in `hex-execute/SKILL.md`; per-tier round caps (1 / 3 / 3); tier-
scaled perspective panels in the execute tier files. The `Review` column
is not renamed and no plan is migrated: a legacy cell is read under
C-983 and every plan shape runs this review model.

### Consequences

- A mid-sized plan of `k` WPs costs `k` fast-balanced leaf reviews
  (parallel, ≤10 min each) plus one deep-reasoning aggregate (≤20 min)
  — bounded in minutes, independent of tier.
- The trunk pass is a user decision, informed by the handoff's deferred
  list and residue lines. Nothing in `/hex-execute` blocks on it.
- Author≠verifier at effective `low` is now backstopped by `L1`, which
  runs at every tier — a stronger guarantee than the `review=minimal`
  spec reviewer it replaces, at lower cost.
- The `perspectives.always` persona→panel wiring narrows from "a seat in
  the per-WP panel" to "a checklist item in the `L2` brief, a seat in
  `L3`". A project that relied on a per-WP custom persona keeps it at
  `L3`.

## Validation

- `grim build` for `hex-core`, `hex-execute`, `hex-review`, `hex-plan`,
  `hex-init`; `task publish -- --dry-run`.
- Anchor sweep: every `](…#anchor)` in the bundle resolves; no literal
  model name in any shipped file.
- Grep gates: zero live hits for `self | light | panel`, `adr_0012
  backstop`, `branch-review precondition`, `tiny review loop` outside
  `DESIGN.md`, `CHANGELOG.md` and this ADR.
- Dogfood: re-run the PR #3 benchmark plan (`.tmp/dogfood/ocx-sion`) and
  record per-WP review wall clock; target ≤10 min per leaf, ≤20 min for
  the aggregate.

## Open Questions

- Whether `L2`'s single seat should split into two on `N ≥ 6` — deferred
  until a measured miss says so.
- Whether `L1` should run on a `fast-balanced` seat at effective `high`
  for `sec`-flagged WPs, or the `L1 → L2` raise is enough — the raise
  ships; a measured miss reopens it.

## Links

- `adr_0012` — per-WP effective tier (its review half is superseded here)
- `adr_0013` — runtime contracts (coordinator join, unchanged)
- `adr_0014` — instruction diet (`loop.md` as the loop's single home)
- `hex/DESIGN.md` round 20

## Changelog

- 2026-09-06 — Proposed.
