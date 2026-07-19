# Tier: low

Minimal execution for **two-way-door** plans — a flag or option, a doc edit
plus code, a single-area tweak of ≤3 files. Keep the contract-first TDD
skeleton (Stub → Specify → Implement → Review-Fix) unchanged; only scale the
worker count, review breadth, and loop rounds down.

`Read` this file from [`SKILL.md`](SKILL.md) after the config is announced.
Shared vocabulary is linked, not restated: roles in
[`workers.md`](../hex-core/references/workers.md), model classes in
[`models.md`](../hex-core/references/models.md), work-package mechanics in
[`SKILL.md`](SKILL.md#work-packages), and the outer contracts in
[`protocol.md`](../hex-core/references/protocol.md).

## Phase 1: Discover

Read the plan artifact (or, for a free-text target, the task description
directly) and its Parallelization table — low tier is normally a single work
package. In parallel, read the project rules for the area touched (project
context, cached in `hex.md › Pointers`,
[`memory.md`](../hex-core/references/memory.md#the-three-sections)) and the
specific code region the plan or prompt names. On resume (`State:
executing`), read the table's `Status` column for the WP's progress
([`SKILL.md`](SKILL.md#work-packages)).
**Federation — a plan carrying a `Repo` column:** the area touched resolves
**per owning repo** — a satellite WP's rules are read by an explicit `Read` of
**that repo's** project context, never ambient, since `--add-dir` does not load
a satellite's `CLAUDE.md` (C-306, C-318). Absent a `Repo` column, unchanged.

**Gate** — the target files are identified; the work package (if the plan
defines one) is confirmed single.

## Phase 2: Stub

Launch **1** `builder` (focus `stub`) to create the public surface — types,
signatures, error variants — with not-implemented bodies. No business logic.

**Gate** — the project's compile/type check passes.

## Phase 3: Verify-Architecture — skipped

Two-way door, ≤3 files: skip the `reviewer` architecture pass. If Discover
revealed a larger scope, **stop and re-run** as `/hex-execute medium <target>`
rather than silently upgrading mid-flow.

**Gate** — the skip is logged in the announcement; proceed to Specify.

## Phase 4: Specify

Launch **1** `tester` (focus `specification`) to write unit tests from the
plan's component contracts (or, free-text, from the stated behavior),
citing the `C-`/`S-` IDs each test covers
([`protocol.md`](../hex-core/references/protocol.md#traceability-ids)).
Acceptance tests are optional at this tier — add one only when the change is
user-visible. Tests MUST fail against the stubs.

**Gate** — tests compile/parse and fail with not-implemented against the
stubs; every plan ID is covered by at least one failing test.

## Phase 5: Implement

Launch **1** `builder` (focus `implement`) to fill stub bodies until the
specification tests pass.

**Gate** — the project's documented verification succeeds for the changed
files.

## Phase 6: Review-Fix Loop (1 round, minimal breadth)

Run the [Review-Fix Loop](../hex-core/references/protocol.md#the-review-fix-loop)
— capped at **1 round** (`loop-rounds=1` baseline), `review=minimal` breadth:
**1** `reviewer` (focus `quality`) + **1** `reviewer` (focus `spec`, phase
`post-implementation`), launched concurrently. The 1-round cap means at most
one `builder` fix pass and a re-verification — never a second review round.
The WP's Review budget lowers this further: `self` drops both reviewers
(builder self-check + verification only), `light` runs the spec reviewer
alone ([`protocol.md`](../hex-core/references/protocol.md#the-review-fix-loop)).

**Gate** — no actionable findings remain, or the single fix pass is done;
the project's documented verification passes on the final state.

## Phase 7: Cross-model review — skipped

Two-way door: skip (`adversary: off` at this tier). If the user passes
`--adversary` explicitly, run it anyway (user override); otherwise log
`Cross-model review skipped: tier=low default` and continue.

## Phase 8: Merge and commit

Single work package — no worktree to merge. Commit the change on the plan's
feature branch
([`SKILL.md`](SKILL.md#work-packages)) with a conventional-commit message.
Never push. The merge-time file-set re-validation and merge-conflict /
post-merge-failure playbook apply only when a worktree merge happens — n/a
on this tier's single-WP direct path
([`protocol.md`](../hex-core/references/protocol.md#worktree-work-package-mechanics)).
Print the Deferred Findings summary even when empty — it confirms the
pipeline ran to completion.

**Federation — a WP whose `Repo` is a satellite key (C-306/C-307).** Commit and
merge run in the owning repo via `git -C <repo>`, onto that repo's
`hex/<plan-slug>`; the commit carries the `Hex-Plan:` trailer, and the
post-merge verification is the **owning repo's**, read by an explicit `Read` of
that repo's project context — never ambient
([`SKILL.md` § Work packages](SKILL.md#work-packages);
[`protocol.md`](../hex-core/references/protocol.md#worktree-work-package-mechanics)).
Absent a `Repo` column this is inert.

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
When the target is a plan artifact, mutate its Status block:
`State: review`, `Updated` refreshed, `Next: /hex-review <plan path>` (see
[`SKILL.md`](SKILL.md#the-plan-artifact)); a free-text target has no Status
block to mutate — note that instead. Then emit the handoff from
[`SKILL.md`](SKILL.md) with:

```
- Tier: low
- Overlays: (none)
```

Its only required artifacts are the commit itself and, when a plan exists,
its advanced Status block. No ADR or research artifact at this tier — if the
pipeline reveals a need for either, stop and re-route through
`/hex-plan medium`.
