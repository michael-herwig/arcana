# Tier: high

The full treatment for **one-way-door-high** plans — a new module or
package, a breaking API, a cross-area refactor, a protocol or
storage-layout change. Preserves contract-first TDD, and adds mandatory
`adversarial` review breadth (architect + researcher perspectives) and a
mandatory cross-model code-diff gate before commit.

`Read` this file from [`SKILL.md`](SKILL.md) after the config is announced.
Shared vocabulary is linked, not restated: roles in
[`workers.md`](../hex-core/references/workers.md), model classes in
[`models.md`](../hex-core/references/models.md), work-package mechanics in
[`SKILL.md`](SKILL.md#work-packages), and the outer contracts in
[`protocol.md`](../hex-core/references/protocol.md).

**Meta-plan preview is mandatory.** At `high`, the gate in
[`SKILL.md`](SKILL.md) step 5 always blocks for explicit approval — this
tier is expensive, and the preview catches a misclassification before
workers launch.

## Phase 1: Discover

Read the plan artifact in full: Status block, the linked ADR (if the plan
references one), component contracts, and every work package. In parallel,
read the project rules for **every** area the plan's work packages touch,
and any linked research artifacts.
**Federation — a plan carrying a `Repo` column:** "every area" resolves **per
owning repo** — a satellite WP's rules are read by an explicit `Read` of **that
repo's** project context, never ambient, since `--add-dir` does not load a
satellite's `CLAUDE.md` (C-306, C-318). Absent a `Repo` column, unchanged.

When the plan defines 2+ file-disjoint work packages, WPs launch
dependency-ready per [`SKILL.md`](SKILL.md#schedule)'s Schedule step:
resolve the feature branch, prepare the ready-set's worktrees before Stub
begins, and run each WP's Phases 2–7 as its dependencies allow.

**Resume.** When the Status block already reads `State: executing` (a
prior run was interrupted), resume at the WP level from the table's
`Status` column rather than re-deriving from branches
([`SKILL.md`](SKILL.md#work-packages)); preparing a ready WP's worktree sets
it to `active`.

**Gate** — the plan, its ADR (if any), and every touched area's project
rules are read.

## Phase 2: Stub

For each work package, launch **1** `builder` (focus `stub`); model class
resolves through [`models.md`](../hex-core/references/models.md)
(`builder:stub` — the fast-balanced baseline, escalated on judgment for
cross-area or new-module scaffolding, announced with its reason).

**Gate** — the project's compile/type check passes **across the whole
workspace**, not just the touched work packages — cross-area implications
must surface immediately. In a federated run "the whole workspace" is the
workspace of the repo the gate runs in, never a cross-repo aggregate (C-321).

## Phase 3: Verify-Architecture (reviewer + architect)

Launch **in a single concurrent batch**, per work package (a `self`-budget
WP — rare at this tier — skips this phase per the budget rule):

- **1** `reviewer` (focus `spec`, phase `post-stub`).
- **1** `architect` — validates stubs against the plan's ADR: are the
  boundaries honored, the trade-offs implemented as decided, any area
  boundary violated?

Architect findings here are first-class: if stubs diverge from the ADR,
**stop and re-stub** before writing any tests.

**Gate** — both report pass; ADR compliance confirmed.

## Phase 4: Specify

For each work package, launch **1** `tester` (focus `specification`); model
class resolves through
[`models.md`](../hex-core/references/models.md) (`tester` — deep-reasoning class
at this tier). Cover edge cases exhaustively: boundary conditions,
concurrent access, failure modes, cross-area interactions. Unit and
acceptance tests both required, each citing the `C-`/`S-` IDs it covers
([`protocol.md`](../hex-core/references/protocol.md#traceability-ids)).

**Gate** — tests compile/parse, fail with not-implemented against the
stubs; coverage matches the plan's documented edge-case list; every plan
ID has at least one failing test.

## Phase 5: Implement

For each work package, launch **1** `builder` (focus `implement`); model
class deep-reasoning at this tier
([`models.md`](../hex-core/references/models.md)).

**Gate** — the project's documented verification succeeds across the whole
workspace, not just the touched work packages. In a federated run "the whole
workspace" is the workspace of the repo the gate runs in, never a cross-repo
aggregate (C-321).

## Phase 6: Review-Fix Loop (up to 3 rounds, adversarial breadth)

Run the [Review-Fix Loop](../hex-core/references/protocol.md#the-review-fix-loop)
— capped at **3 rounds**, `review=adversarial` breadth (mandatory). Each WP
runs at its declared Review budget (`self`/`light` lower the set below per
WP; `panel` = this tier's full set) — rare at this tier, and never on
security- or hot-path work
([`protocol.md`](../hex-core/references/protocol.md#the-review-fix-loop)).

**Round 1** — launch concurrently: `reviewer` (focus `quality`), `reviewer`
(focus `spec`, phase `post-implementation`), `reviewer` (focus `security`)
when security-sensitive paths are touched, `reviewer` (focus `performance`)
when a hot path or async code is touched, `doc-reviewer` when doc-drift
triggers match, `architect` (ADR-compliance / boundary check), `researcher`
(SOTA-gap / known-pitfall check), or when a `perspectives.always` rule
matches. A `perspectives.always` addition on top of this round is what
merge rule 6's phase ceiling displaces first
([`config.md` § Merge rules](../hex-core/references/config.md#merge-rules)).

A finding that oscillates between `architect` and `reviewer` two rounds
running auto-defers, per the canonical loop's oscillation rule.

**Cross-model code-diff review — a default part of this tier's flow.** After
the loop converges, invoke the configured adversary skill once in
`code-diff` scope against the branch diff. One-shot, no loop; 4-way triage
(actionable / deferred / stated-convention / trivia); actionable findings
get one `builder` (focus `implement`) fix pass, re-verified. If that one-shot
fix pass fails verification, **revert it** and promote all cross-model
findings to deferred rather than looping
([adversary contract](../hex-core/references/protocol.md#adversary-contract)).
If the skill is unavailable, log
`Cross-model review skipped: <reason>` and continue — but **surface the skip
prominently in the handoff**, since one review layer was missed.

**Gate** — the project's documented verification passes on the final state;
both panel and cross-model deferred findings are documented.

## Phase 7: Merge and commit

Merge work packages onto the plan's feature branch, serialized in a valid
topological order per [`SKILL.md`](SKILL.md#work-packages) — one WP at a
time. Before each merge, run the merge-time file-set re-validation; the
project's
documented verification runs after every merge, and a merge conflict or a
failed post-merge verification follows the merge-conflict /
post-merge-failure playbook
([`protocol.md`](../hex-core/references/protocol.md#worktree-work-package-mechanics)).
Set the table's `Status` column to `merged` on a successful merge, `failed`
on a playbook halt; ephemeral branch deleted and worktree removed once its
WP merges. Commit per completed work package with conventional-commit
messages on the feature branch. Never push — landing the feature branch on
the trunk is the human's step.

**Federation — a WP whose `Repo` is a satellite key (C-306/C-307).** Its merge
is `git -C <repo> merge` onto **that repo's** `hex/<plan-slug>`; the commit
carries the `Hex-Plan:` trailer, and the post-merge verification is the **owning
repo's**, read by an explicit `Read` of that repo's project context — never
ambient ([`SKILL.md` § Work packages](SKILL.md#work-packages)). Merge order is
one global topological sequence across all repos, one at a time
([`protocol.md`](../hex-core/references/protocol.md#worktree-work-package-mechanics)).
Absent a `Repo` column this is inert.

Surface prominently in the handoff:

- whether the cross-model gate ran or skipped (with reason);
- any ADR-compliance concern the `architect` flagged as deferred;
- any SOTA gap the `researcher` flagged as deferred.

## Upkeep and handoff

Run the [upkeep step](../hex-core/references/protocol.md#upkeep-step):
re-point any `hex.md › Pointers` entry this run revealed as drifted, and
update `hex.md › Memory` with anything worth persisting.
**Federation — a plan carrying a `Repo` column:** upkeep additionally offers to
confirm each `Repos:`-ledger row's landing, advancing a
`landing` plan to `done` only when every row is landed (C-324), and on `done`
removes the plan's slug from each satellite's `Federation lead:` bullet —
deleting the bullet, and the file if it held nothing else (C-313). Both are
defined in full in [`protocol.md` § Upkeep step](../hex-core/references/protocol.md#upkeep-step).
Mutate the plan's Status block: `State: review`, `Updated` refreshed,
`Next: /hex-review <plan path>` (see
[`SKILL.md`](SKILL.md#the-plan-artifact)). Then emit the handoff from
[`SKILL.md`](SKILL.md) with:

```
- Tier: high
- Overlays: review=adversarial, loop-rounds=3, adversary=on
```

Required artifacts: the plan (Status block advanced to `review`), the
commit(s) on the feature branch, and — if implementation revealed a decision
the original ADR didn't cover — a follow-up ADR request escalated to
`/hex-plan high` rather than inlined here.
