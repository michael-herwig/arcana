# Tier: medium

The **default** execution tier — one-way-door-medium plans: a new command, a
new index or storage layout, work spanning 1–2 areas. Preserves the
contract-first TDD skeleton (Stub → Specify → Implement → Review-Fix) with
the full 3-round Review-Fix Loop and `full` review breadth.

`Read` this file from [`SKILL.md`](SKILL.md) after the config is announced.
Shared vocabulary is linked, not restated: roles in
[`workers.md`](../hex-core/references/workers.md), model classes in
[`models.md`](../hex-core/references/models.md), work-package mechanics in
[`SKILL.md`](SKILL.md#work-packages), and the outer contracts in
[`protocol.md`](../hex-core/references/protocol.md).

## Phase 1: Discover

Read the plan artifact in full: Status block, component contracts, UX
scenarios, and the Parallelization table (work packages, DAG, merge order).
In parallel, read the project rules for every area the plan's work packages
touch (project context, cached in `hex.md › Pointers`,
[`memory.md`](../hex-core/references/memory.md#the-three-sections)).
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

**Gate** — the plan's phases and work packages are parsed; project rules for
every touched area are read.

## Phase 2: Stub

For each work package (or the single implicit one), launch **1** `builder`
(focus `stub`) — in a single concurrent batch across the ready work
packages, each scoped to its own declared file set — to create the public
surface with not-implemented bodies. No business logic.

**Gate** — the project's compile/type check passes for every work package.

## Phase 3: Verify-Architecture

Launch **1** `reviewer` (focus `spec`, phase `post-stub`) per work package to
validate stubs against the plan's component contracts: signatures match,
module boundaries align, error variants cover the documented failure modes.
*Optional when the whole plan touches ≤3 files. Budget-gated: a `self`
WP skips this phase; `light` keeps it optional.*

**Gate** — every reviewer reports pass.

## Phase 4: Specify

For each work package, launch **1** `tester` (focus `specification`) to
write unit and acceptance tests from the plan's component-contracts and
user-experience sections — NOT from the stubs. Tests cite the `C-`/`S-`
IDs they cover
([`protocol.md`](../hex-core/references/protocol.md#traceability-ids)).
Tests MUST fail against the stubs.

**Gate** — tests compile/parse and fail with not-implemented against the
stubs, for every work package; every plan ID has at least one failing
test.

## Phase 5: Implement

For each work package, launch **1** `builder` (focus `implement`) to fill
stub bodies until its specification tests pass.

**Gate** — the project's documented verification succeeds for each work
package's changed files.

## Phase 6: Review-Fix Loop (up to 3 rounds, full breadth)

Run the [Review-Fix Loop](../hex-core/references/protocol.md#the-review-fix-loop)
— scoped to the branch diff (or, for parallel work packages, each WP's diff
before merge) — capped at **3 rounds**, `review=full` breadth. Each WP runs
at its declared Review budget: `self` = no reviewer spawns (builder
self-check + verification only), `light` = one spec reviewer × 1 round,
`panel` = the full set below; the budget lowers the tier baseline, never
raises it.

**Round 1** — launch concurrently: `reviewer` (focus `quality`), `reviewer`
(focus `spec`, phase `post-implementation`), `reviewer` (focus `security`)
when the diff touches security-sensitive paths (auth/crypto/signing, a new
dependency manifest, a CI workflow file), `reviewer` (focus `performance`)
when the diff touches a hot path or async code, `doc-reviewer` when
doc-drift triggers match, or when a `perspectives.always` rule matches.

**Cross-model code-diff review** (when `adversary=on` — auto-on for
one-way-door signals, or explicit `--adversary`): after the loop converges,
run the configured adversary skill once in `code-diff` scope against the
branch diff. One-shot, 4-way triage, actionable fixes get one `builder`
(focus `implement`) fix pass, re-verified; graceful skip when unavailable
([adversary contract](../hex-core/references/protocol.md#adversary-contract)).

**Gate** — the project's documented verification passes on the final state;
deferred findings (native-panel and cross-model) are documented.

## Phase 7: Merge and commit

When the plan ran 2+ work packages in worktrees: merge each onto the plan's
feature branch, serialized in a valid topological order per
[`SKILL.md`](SKILL.md#work-packages) — one WP at a time. Before each merge,
run the merge-time file-set re-validation; the project's documented
verification runs after every merge, and a merge conflict or a failed
post-merge verification follows the merge-conflict / post-merge-failure
playbook
([`protocol.md`](../hex-core/references/protocol.md#worktree-work-package-mechanics)).
Set the table's `Status` column to `merged` on a successful merge, `failed`
on a playbook halt; ephemeral branch deleted and worktree removed once its
WP merges. Commit per completed work package (or once, for a
single-package plan) with a conventional-commit message on the feature
branch. Never push — landing the feature branch on the trunk is the
human's step.

**Federation — a WP whose `Repo` is a satellite key (C-306/C-307).** Its merge
is `git -C <repo> merge` onto **that repo's** `hex/<plan-slug>`; the commit
carries the `Hex-Plan:` trailer, and the post-merge verification is the **owning
repo's**, read by an explicit `Read` of that repo's project context — never
ambient ([`SKILL.md` § Work packages](SKILL.md#work-packages)). Merge order is
one global topological sequence across all repos, one at a time
([`protocol.md`](../hex-core/references/protocol.md#worktree-work-package-mechanics)).
Absent a `Repo` column this is inert.

## Upkeep and handoff

Run the [upkeep step](../hex-core/references/protocol.md#upkeep-step):
re-point any `hex.md › Pointers` entry this run revealed as drifted (a
changed verification command, a new worktree location), and update
`hex.md › Memory` with anything worth persisting (e.g. a review
perspective that mattered).
**Federation — a plan carrying a `Repo` column:** upkeep additionally offers to
confirm each `Repos:`-ledger row's landing, advancing a
`landing` plan to `done` only when every row is landed (C-324), and on `done`
removes the plan's slug from each satellite's `Federation lead:` bullet —
deleting the bullet, and the file if it held nothing else (C-313). Both are
defined in full in [`protocol.md` § Upkeep step](../hex-core/references/protocol.md#upkeep-step).
When the target is a plan artifact, mutate its Status block:
`State: review`, `Updated` refreshed, `Next: /hex-review <plan path>` (see
[`SKILL.md`](SKILL.md#the-plan-artifact)). Then emit the handoff from
[`SKILL.md`](SKILL.md) with:

```
- Tier: medium
- Overlays: review=full, loop-rounds=3, adversary=<on|off>
```

Required artifacts: the plan (Status block advanced to `review`), the
commit(s) on the feature branch, and any research artifact Implement
uncovered a surprise worth persisting (rare at this tier — an ADR-level
surprise means the plan was underspecified; re-route through
`/hex-plan high` rather than inlining one here).
