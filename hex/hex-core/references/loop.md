# hex Review-Fix Loop

A topic file of the hex swarm protocol; the spine is
[`protocol.md`](protocol.md).

## The Review-Fix Loop

The canonical contract-first loop. **This is the only copy in the bundle —
every other file links here.** Diff-scoped, bounded, tier-scaled.

**Contract-first TDD phases:**

1. **Stub** — a builder (focus `stub`) creates the public surface; gate on
   the project's compile/type check.
2. **Specify** — a tester (focus `specification`) writes tests from the
   design record; they MUST fail against the stubs.
3. **Implement** — a builder (focus `implement`) fills bodies until the
   tests pass; run the [scoped check](verify.md#scoped-check) — the WP's own contract
   tests plus the project's cheapest documented assembly gate —
   **unconditionally, at every tier**. This gate is **not** coupled to the
   WP's `Verify` cell, which budgets the merge boundary only — that WP's
   Review-Fix-Loop exit gate and the merge that immediately follows it
   ([Parallel-by-default decomposition](decompose.md#parallel-by-default-decomposition)).
   **The backstop is stated:** tier `high` thereby gives up its pre-merge
   proof over untouched modules, and what catches a defect in a module no WP
   touched is [merge rule](worktree.md#worktree-work-package-mechanics) trigger (ii), a
   [checkpoint](verify.md#checkpoints) — `M = 3` merges, a cleared dependency level,
   or a high-risk merge, whichever fires first —
   with the bounded bisection of the post-merge-failure playbook (C-904,
   [Worktree work-package mechanics](worktree.md#worktree-work-package-mechanics))
   attributing the failure across at most three merges, trigger (i) at a
   coordinator join, and trigger (iii), the final gate.
   **Carve-out for a leaf under a decomposing coordinator:** it runs a
   scoped compile/parse check only — concurrent full verification in the
   coordinator's shared worktree would race on shared build artifacts — and
   the coordinator runs the one authoritative verification at the WP join.
   **The kind is load-bearing:** a pipeline coordinator splits its WP into no
   sub-WPs and holds no join, so the carve-out's own backstop does not
   exist there and a WP under one pays this gate in full.
4. **Review-Fix** — the loop below.

**The collapse at effective tier `low`.** The four-phase list above is the
shape at effective `medium` and `high`; at effective tier `low`, Stub +
Specify + Implement collapse into one builder spawn ([the effective
tier](decompose.md#the-effective-tier)). One builder writes the public surface, then the
failing tests, then the implementation, in a single turn, and
**Verify-Architecture does not run**. **The collapsed builder still pays the
Implement gate's scoped check** ([Scoped check](verify.md#scoped-check)) — that gate
is unconditional at every tier and nothing here removes it.

**The ordering is checked by the orchestrator, not reported by the
builder**: the collapsed builder commits the stubs and the specification
tests as its first commit on the WP branch, before the implementation
commit, the builder's output contract names that commit's SHA, and the
orchestrator runs the project's test command at that commit and requires it
to fail — a pass at that commit is a violation and the WP does not proceed,
and the builder's own prose is not evidence. **That check is budgeted**: it
runs the WP's [scoped check](verify.md#scoped-check) command **warm**, reusing the
tree already built, so it costs a test run rather than a build; where the
older commit forces a cold rebuild, that rebuild **runs once** and is
recorded in the schedule log
([Parallel-by-default decomposition](decompose.md#parallel-by-default-decomposition)).

**What is given up is stated**: the *temporal* property is recovered —
surface before tests, tests before implementation, read off the branch's
commit graph by a party that did not write it — but **author≠verifier is
not**, and the two backstops for it are the `review=minimal` batch's `spec`
reviewer and the ceiling-tier branch review below. **Model-cell
resolution**: the collapsed spawn resolves all three source cells
(`builder:stub`, `builder:implement`, `tester`) and reads the highest, never
the lowest, disclosed like any other override-driven raise
([`models.md`](models.md#rules)).

At effective `medium` and `high` the four-phase list is unchanged in every
byte.

**The loop:**

- **Round 1** — run every tier-selected perspective on the diff,
  concurrently. Perspectives most likely to find blockers go first (spec,
  correctness). Classify each finding:
  - **Actionable** — a builder fixes it; re-run only the affected
    perspectives next round.
  - **Deferred** — surface it in the summary with context; never block the
    loop on it.
- **Subsequent rounds** — re-run only the perspectives with actionable
  findings from the prior round. A finding that surfaces two rounds running
  (oscillating) auto-defers.
- **Loop cap** — scales with tier and **scope**. Code-diff scope: 1 round
  at `low`, up to 3 at `medium` and `high`. **Plan-artifact scope** (a
  draft plan or ADR under review by its own orchestrator): **one** panel
  round → the orchestrator applies actionable fixes → **one** re-validation
  pass by `reviewer` (focus `spec`) *whenever any actionable fix was
  applied* (skipped only on a clean panel) → anything still actionable
  escalates to the user. Artifacts are re-checked downstream anyway
  (Specify and Verify-Architecture gates), so multi-round artifact loops
  buy little; re-enabling them takes an **explicit** `artifact loop
  rounds: N` limit in `hex.md › Preferences` — the generic loop-rounds
  ceiling does not. If actionable findings remain when a cap
  is hit, **stop and escalate to the user** with the outstanding list —
  do not loop past the cap.
- **A `loop rounds` value in `hex.md › Preferences` is a ceiling, never a
  default and never a raise.** It caps the code-diff scope's per-tier round
  count *and* any `--loop-rounds` flag: the effective cap is the **lower of
  the stored value and the run's resolved request** — `--loop-rounds` when
  passed, the tier default otherwise. **In a plan carrying the generation
  marker that lower-of-two gains a third term**, and the cap is the lowest
  of the stored value, the run's resolved request, and the effective tier's
  per-tier default — `low` → 1, `medium` and `high` → 3, the shipped
  per-tier defaults read per WP ([the effective
  tier](decompose.md#the-effective-tier)). The stored value never raises the tier
  default and never lifts `low` above 1 round; a `--loop-rounds` flag may
  still loosen a run up to (never past) the stored ceiling. `limits.*` sit
  **outside** the later-wins [spawn-selection
  precedence](protocol.md#spawn-selection-precedence) — a user flag may lower a limit,
  never raise it past the stored ceiling. The stored value never affects
  plan-artifact scope — that scope moves only via the explicit `artifact
  loop rounds: N` limit named above. Both limits are announced at the gate
  with their source, like every other resolved axis.
- **Per-WP review budget** — when the plan's Parallelization table carries
  a `Review` column, it scales this loop per work package:
  - `self` — **no reviewer spawns in this loop, and the WP skips the
    Verify-Architecture reviewer**: the builder's self-check
    ([`workers.md`](workers.md) universal rule 7), the Implement gate's
    unconditional [scoped check](verify.md#scoped-check), and **the WP's resolved
    verification** at the exit gate below
    ([Parallel-by-default decomposition](decompose.md#parallel-by-default-decomposition))
    are the only WP-level checks. A
    `self` WP is deliberately un-reviewed at the WP level — which makes the
    branch-level `/hex-review` pass **mandatory before the feature branch
    lands on the trunk** for any plan containing one; the execution
    handoff records it.
  - `light` — one `reviewer` (focus `spec`, phase `post-implementation`),
    one round.
  - `panel` — the tier's full Round-1 set and round cap (the ceiling); in
    a plan carrying the generation marker "the tier" here is the **plan's
    ceiling**, never the WP's own effective tier, so the hatch below has
    something to raise to, under the `min` cap stated with that hatch.

  **In a plan without the generation marker** the budget only **lowers**
  breadth below the tier baseline, never raises it, and a missing column or
  cell means `panel` — pre-budget plans run unchanged. **In a plan carrying
  it** the derived breadth is the baseline instead ([the effective
  tier](decompose.md#the-effective-tier)), so the column reads **raise-only against the
  derived breadth, capped at the ceiling**: a cell naming a breadth at or
  below the derived one is inert — honoured as a no-op, never a defect —
  and a cell above it is honoured up to the ceiling. **`Review: panel`
  raises the WP's effective tier to the ceiling, all four axes, and is the
  one escape hatch**; the run's own resolved limits then apply as a `min`
  cap over the resulting per-axis values — the stored `loop rounds`
  ceiling, `limits.*`, and the run's resolved `review` breadth axis, never
  `/hex-execute`'s run-tier argument, and never the tier itself (C-948).
  In a `low`-tier plan the hatch is a no-op, because the ceiling is
  already `low`. **The column is not renamed.**

  **The branch-review precondition has two independent halves** — a legacy
  `self` WP or any WP whose effective tier fell below its ceiling ([the
  effective tier](decompose.md#the-effective-tier)) — and either alone arms it, so a
  plan with no `self` row still arms it whenever a WP was reduced. A plan
  that armed it **does not reach its terminal review state** — `done`, or
  `landing` for a plan carrying a `Repo` column — until a branch-level
  `/hex-review` has run at no less than the plan's ceiling tier.
  `/hex-review` is already the sole writer of that state, so this is a
  second precondition on the same write, never a second writer. **The
  ceiling floors, never caps**: the resolved tier is `max(classified,
  ceiling)`, so a large diff on a `medium`-ceiling plan is still reviewed
  at `high` when its own classifier says so, and a lower `--tier` flag is
  **honoured for the run and does not discharge this precondition** — the
  pass announces `ceiling high (plan) floors --tier low — this pass does
  not satisfy the adr_0012 backstop` and the precondition stays armed.
  **What it blocks is stated plainly:** a field in a markdown Status block,
  not a forge submit requirement — the borrowed property is *"no tier low
  enough to skip it"*, and the borrowed enforcement is not available and is
  not claimed.
- **Adversary gate** (optional, tier-scaled) — after the loop converges,
  one cross-model pass on the diff; see [Adversary contract](adversary.md#adversary-contract).
  One-shot, never loops.
- **Exit gate** — no actionable findings remain, the **WP's resolved
  verification** passes on the final state, and deferred findings are
  documented for handoff. The resolved verification is what that WP's
  `Verify` cell sets — grammar, defaults and the scoped/full determination
  live in [Parallel-by-default
  decomposition](decompose.md#parallel-by-default-decomposition), stated once there and
  linked, never restated, here. **This is not the run's final gate** — it
  fires **once per work package that runs the loop, in that WP's own
  worktree, before merge**; the plan's terminal verification is a
  separate, un-lowerable gate enumerated by the merge rule
  ([Worktree work-package mechanics](worktree.md#worktree-work-package-mechanics)).

### The last-reviewed anchor

**One rule, two scopes, one of them persisted.**
A review round reads `<last-reviewed>..HEAD`, where `<last-reviewed>` is the
SHA the previous round **of the same scope** reviewed.

- **WP scope** — inside a Review-Fix Loop in a WP worktree, the anchor is
  the SHA round N−1 reviewed. It is held in the orchestrator's session state
  and **is not persisted**, because it never outlives the ephemeral branch
  it names and therefore cannot go stale.
- **Branch scope** — across `/hex-review` invocations on the feature branch,
  the anchor must survive the session and **is persisted** as one
  Status-block line: `- Reviewed: <full 40-char SHA>`, following the
  `Repos:` ledger's full-SHA precedent (C-324) for exactly the same reason —
  a short SHA or a ref name is not a stable identity. **Placement:
  immediately after `Next:` and *before* the `Repos:` ledger** — this line and
  the optional `- Verify-default:` line alike, because the `Repos:` ledger is
  multi-row and unbounded, so a line placed behind it has no stable position.
- **One writer rule** — whoever completes a review pass over a diff whose
  head is `<sha>` writes `Reviewed: <sha>`. It means precisely *"every
  commit reachable from this SHA has been through at least one review
  pass"* — nothing about verdicts, and nothing about whether findings
  remain. A WP-scope round **never** writes the field. Absent field ⇒ never
  reviewed ⇒ full-branch review.

### Anchor validation

**One predicate, fail-safe.** Before a persisted anchor
is used, assert that it lies **inside the range this review is about**;
reachability alone is not enough. **Validation runs in two steps, in this
order:** the fallback baseline is resolved first — the PR's fetched base ref,
else `main` — the anchor is validated against *that* value, and only a valid
anchor then substitutes as the round's baseline. **Two tests, both required:**
`git merge-base --is-ancestor <anchor> <HEAD>` **must pass** (the anchor is
reachable), **and**
`git merge-base --is-ancestor <anchor> <resolved-baseline>`
**must fail** (the anchor is not already behind the baseline). The second
test closes a fail-open hole the first cannot: a trunk SHA, or any common
ancestor, is a perfectly good ancestor of HEAD, so a one-test check would
accept it and review only `trunk..HEAD` **minus the feature-branch commits
that precede it** — silently omitting reviewed-looking work nobody reviewed.
An anchor **equal to the merge-base** fails the second test and is treated
as valid-and-degenerate: its range is the whole branch, which is a full
review anyway. On a miss of either test the anchor is invalid: **fall back
to a full-branch review**, announce the fallback with its reason, and
rewrite the anchor at the end. This is a degrade, never a halt — a redundant
full review costs time, while a wrong-scope review silently reports on a
diff it did not read. **A missing object is a miss, not a crash**: where the
anchor SHA no longer resolves (garbage-collected after a rewrite), the
command's failure is treated as a failed ancestry test. **This is the sole
staleness predicate, and it is sufficient by construction** —
`/hex-finalize`'s recomposition is explicitly not SHA-stable
([`finalize.md`](finalize.md#re-entry)) and is explicit-invocation-only rather
than gated on plan State, so a finalize run **will** invalidate a stored
anchor with no signal in the plan; a rebase, a reset and a force-push all
manifest identically as a failed reachability test, and an out-of-range
anchor as a failed range test, so enumerating causes separately would add
predicates that can disagree. The `backup/<branch>-…` ref is a
**diagnostic, never a second predicate**: an *inert* ref for this branch
explains *why* the ancestry test failed and is named in the fallback
announcement, while an *armed* ref already forbids acting on the branch at
all under the shipped hex-state rule, so there is no interaction left to
design.

### Delta round scope

**The mandatory full pass is what makes it safe.**
Round N ≥ 2 reads **`<last-reviewed>..HEAD` plus finding-adjacent files** —
the files named by the prior round's actionable findings, in full, even
where the delta does not touch them, because a fix's correctness is judged
against its surroundings. Round 1 reads the anchor's range where one is
valid, the full diff otherwise — **except at tier `low`, where a valid anchor
never narrows round 1**: the 1-round cap makes that single round the whole
loop, so it reads the full scope and *is* the mandatory converged pass. **One
full pass is mandatory at the converged gate** — after actionable findings
reach zero and before the exit gate — **never delta-scoped, never skipped, not lowerable by any budget
column.** It is a pass, not a second read: a converging round that already
read the full scope **satisfies** it, and a further read is owed only where
that round was delta-scoped. A `self` WP runs no loop and therefore has no
WP-level converged gate at all — the mandatory branch-level `/hex-review` is
its backstop, as the review budget above already states. **"Full" resolves per the two scopes above and is not the feature
branch in both:** a **WP-scope** loop's converged pass reads
**the WP branch's own full diff against its recorded base** — the scope that
loop has reviewed all along — and a **branch-scope** pass reads the
**whole feature branch**. Reading the feature branch at the end of every
per-WP loop would re-review every already-merged WP once per subsequent WP,
which is `O(N²)`. The pass absorbs the three miss classes delta
scoping cannot: **review non-determinism on unchanged code**; **semantic
conflicts** (two independently correct changes combining broken with zero
textual overlap); and **collateral breakage through a shared symbol** — a
fix that changes a signature, contract or invariant and breaks an
*unchanged* caller, which is in neither the delta nor the finding-adjacent
set, since that caller is neither touched nor named by the finding. The
per-finding oscillation rule above is unchanged, and so is the round-N
perspective-shrinking rule — **delta scoping shrinks the diff *in addition
to*, never instead of, shrinking the perspective set**.

### The diminishing-returns stop

**A second exit condition, severity-aware.**
Let `A(N)` be the count of **actionable findings graded `Block` or `High`**
at the end of round N, after the per-finding auto-defer rule has been
applied. Severity is orthogonal to the actionable/deferred class
([Finding severity](severity.md#finding-severity)), so the stop names both axes or it
counts a naming nit against a data-loss bug. `Warn` and `Suggest` are
excluded: a round that converts one `Block` into three `Warn`s has
converged, and a count blind to that would call it oscillation. **At tier
low the severity ladder is not applied** and the tag is absent, so `A(N)`
there counts all actionable findings — the same degrade every other
severity consumer takes. **The stop fires when both hold:**
`A(N) ≥ A(N−1)` for `N ≥ 2` — the `Block`/`High` count did not **strictly**
shrink — **and** round N introduced **no new `Block` or `High`** that was
not present in round N−1. The second clause is what keeps the stop from
firing on genuine progress: a round that surfaces a *new* serious defect is
doing its job, and stopping there would escalate a loop that had just found
something. When it fires the loop **stops and escalates to the user with the
outstanding list**, byte-for-byte the terminal behaviour hitting the loop
cap already produces — no new escalation path, no new message shape. The
strictly-decreasing expectation was derived from the constant-input case,
where every round re-read the *same* full diff; under delta scoping the
input shrinks too, so part of any observed decrease is an artifact of the
scope, and the rule is an **expectation, not a law**. It ships anyway
because its failure direction is benign: a scope-artifact decrease makes the
stop fire **late** — the loop runs to its cap, which is the pre-existing
behaviour — never early, and the severity floor biases it later still.
`A(N) = 0` is the **exit gate**, not this stop; the stop can only fire
**earlier** than the loop cap and never raises it, and the
`hex.md › Preferences` `loop rounds` ceiling is untouched.

## Convergence contract

The post-implementation drift check: does delivered code cover every
requirement ID the plan carries? Run by the review orchestrator when its
target traces to a plan artifact.

- **4-way gap taxonomy, keyed by [Traceability IDs](protocol.md#traceability-ids):**
  **missing** (nothing delivered for the ID), **partial** (delivered but
  incomplete against the contract), **contradicts** (delivered behavior
  conflicts with the contract), **unrequested** (delivered behavior no ID
  asked for — the reverse gap).
- **Append-only growth**: the orchestrator appends gaps as new WP **rows**
  at the end of the plan's Parallelization table, with matching new
  Implementation Steps entries, `Depends on` the delivered WPs; their
  **wave derives** as the next topological level (no explicit wave to
  assert). Existing WPs, sub-WPs, steps, and IDs are never rewritten or
  renumbered.
- **Byte-identical when clean**: nothing unmet → the plan file is not
  touched at all and the report states "Converged".
- **Verdict interplay**: unconverged gaps cap the review verdict at
  Needs Work — never Approve — with `Next: /hex-execute <plan path>`.
- **Composition with fold-back (C-412)**: convergence runs **first and
  unconditionally**; the [spec fold-back](archive.md) phase runs **only** on
  a `Converged` result. They are mirrors on the same `C-###`/`S-###` join
  key — convergence asks *does the delivered code cover the plan's IDs* and
  appends to the plan (plan ← code), fold-back asks *does the spec describe
  what the plan delivered* and appends to the spec (spec ← plan); neither
  rewrites what the other wrote. A `Needs Work` verdict means fold-back never
  runs at all.
- **Federation — a plan carrying a `Repo` column (C-310):** the mechanism
  above is unchanged; coverage is evaluated against the **union diff** (the
  lead plus every distinct `Repo` value, `/hex-review`'s C-309 scope),
  satellite delivery is located via the `Hex-Plan:` commit trailer
  (`git -C <repo> log --grep`), and an appended gap row carries a `Repo` value
  like any other row. `C-`/`S-` IDs stay plan-scoped and are therefore global
  to the change. A gap delivered in a WP whose `Repo` is **not** `.` is
  **not** folded into the lead's spec — it is reported "delivered in
  `<repo>`, fold by hand" and left in the plan, because a fold has no correct
  destination across a repo boundary (the [fold-back](archive.md) phase is
  lead-scoped and never crosses it).

