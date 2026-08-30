# ADR: hex execution performance — scoped per-merge verification, checkpointed backstops, delta-scoped review rounds, and the failure cascade

## Metadata

**Status:** Accepted (Michael, 2026-08-30, at the /hex-plan gate — plain approval; all three open-question recommendations stand)
**Date:** 2026-08-30
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A (originated in the 2026-08-30 discussion, persisted as [`.agents/discussions/hex-execution-performance.md`](../discussions/hex-execution-performance.md))
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below
      (one `DESIGN.md` round with three amendments — two to § Worktrees, one
      to the live *Plan visualization* column lock — one
      `protocol.md` playbook amendment, and one retro-claim of an
      unowned contract surface — see
      [Constitution deviations](#constitution-deviations))
**Domain Tags:** performance, devops (the bundle's first wall-clock-motivated decision)
**Supersedes:** N/A
**Superseded By:** N/A

*Template slots deliberately omitted: **Quantified Impact** as a standalone
section (the numbers are the substance of § Decision Outcome › The arithmetic,
and a second copy would drift), **Technical Details › Data Model** (no
entities; the durable objects are one markdown table column, one Status-block
line, and one append-only plan section), and **Trending approaches** as a
standalone line (it is § Industry Context).*

## Context

Hex runs take too long, and the owner named four complaints. Three of them
resolved on inspection into one shape and one non-issue.

The **non-issue** is complaint 1 (plans declare a DAG but execution barriers
in waves). Ready-set dispatch is already contractual — `protocol.md`
§ Parallel-by-default decomposition states that waves are "a derived reporting
view … never a launch gate", that a WP "becomes eligible the instant every WP
in its `Depends-on` has Status `merged`", and that the ready-set is recomputed
on every merge, critical-path-first. Observed wave behaviour is therefore
runtime non-compliance or a stale installed copy in the affected repo, not a
missing contract. **This ADR does not redesign dispatch.** It adds the two
things that section is missing — *observability*, so barrier behaviour becomes
visible drift rather than a suspicion, and an explicit *failure-cascade* rule,
which is genuinely unspecified territory today.

The **shape** the other three share is that hex verifies and reviews far more
than the work that changed, on a serial path:

- Merges are serialized one at a time, and `protocol.md` § Worktree
  work-package mechanics runs **the project's documented verification after
  every merge**. With a 5–6 minute suite and N work packages that is a
  ≥ N × 6 min serial floor, independent of how well dispatch parallelizes. No
  test-selection concept exists anywhere in the bundle.
- The Review-Fix Loop's subsequent rounds shrink the **perspective set**,
  never the **diff**. Round 3 re-reads everything round 1 read. There is no
  last-reviewed anchor anywhere in the bundle.
- The per-WP effort knob that does exist — the `Review` column
  (`self | light | panel`) — covers review breadth only, and has no owning
  contract ID at all; it predates `adr_0003`.

The intent, the five owner-ratified decisions, the ten discussion-phase
research artifacts, and the three-seat blind council are in the dossier. This
ADR does not restate them. **The five decisions are treated as constraint, not
as positions to re-litigate**: scoped check per WP merge with full
verification at joins, checkpoints and the final gate; the scoped check's
default source is the WP's own contract tests plus a build check, with a
project-documented selective-test command as the escape hatch; review-fix
round N reads `anchor..HEAD` plus finding-adjacent files with one full-branch
pass at the converged gate; nesting stays capped at the existing depth-1
coordinator with **one flat Parallelization table**; and a `failed` WP blocks
its dependents while independent siblings keep flowing, the run ending with a
stranded-WP list.

Where this design departs from a dossier **recommendation** — as distinct from
a ratified decision — the departure is named as a departure rather than
smoothed over. There are three, all in § Decision Outcome › Departures from
dossier recommendations.

### The central tension

The rule being replaced is not arbitrary. "Verify after every merge" exists
because **cross-file interactions surface only post-merge** — that sentence is
in `protocol.md` today, and it is correct. Every merge changes the base under
the next one, so the only tree that has ever been proven good is the one the
last full verification ran against. Scoping the per-merge check trades that
property away, and what it buys back has to be worth it.

What makes the trade defensible is that the property was never as strong as it
reads. A green full suite after merge k proves nothing about merge k+1, and
the run's actual correctness gate has always been the final one. The
industry's answer to exactly this trade is uniform and is quoted in
§ Industry Context: **selective checks plus a periodic comprehensive backstop**
— never selective checks alone, and never comprehensive checks every time.
This ADR's whole job is to place the backstops so the bisection radius stays
small enough that a failure is still cheap to localize.

## Decision Drivers

1. **Wall-clock, honestly measured.** The point of the change. A saving that
   evaporates on a build-dominated project must be stated as such, not
   averaged away.
2. **The correctness backstop is not negotiable.** The final gate stays a full
   documented verification, mandatory, and no per-WP budget can lower it.
3. **Bisection radius.** The council's premortem seat named the failure mode:
   a single final gate that fails thirty merges late. Whatever replaces
   per-merge full verification must bound how far back a failure can hide.
4. **Zero new tooling and zero new config vocabulary.** `config.md`'s v1 key
   set froze at six (`adr_0003` C-223). Hex must not learn nine test runners'
   CLIs, and must not grow a key for a value a plan-table cell can carry.
5. **One flat state surface.** The operability seat made this a hard
   requirement: state stays the one Parallelization table with dotted WP rows
   and computed rollups. No nested state files, at any depth.
6. **Additive compatibility.** An already-approved plan must execute, and an
   already-shipped skill file must stay true or take a one-clause qualifier —
   never a silent reinterpretation.
7. **Sole definition sites.** `DESIGN.md` round 10's pattern binds: canonical
   text lands once in `protocol.md`; every other site links or qualifies.
   Twenty-odd files mention verification; twenty-odd copies of a new rule is
   the failure this constraint exists to prevent.

## Industry Context & Research

Three targeted research artifacts were commissioned for this ADR
([`adr0010-compat.md`](../research/adr0010-compat.md),
[`adr0010-operability.md`](../research/adr0010-operability.md),
[`adr0010-tooling.md`](../research/adr0010-tooling.md)), on top of the ten
discussion-phase artifacts (`research/discuss-exec-perf-*.md`). All are dated
2026-08-30 and expire 2027-02-28.

**Selective checks always ship with a comprehensive backstop — nobody runs
selection alone, and nobody runs everything every time.** Meta's TAP pairs
fast speculative cycles with periodic comprehensive cycles, reporting 85%
recall at 25% of the budget and p50 detection moving 107 → 37 minutes; Meta's
selection work reports roughly 2× cost reduction at >99.9% faulty-change
catch; Azure's Test Impact Analysis documents the full suite on protected
branches as its mitigation; Chromium's backstop is structural — a mirrored
post-submit CI tier — rather than a re-run policy
([`discuss-exec-perf-adjacent-buildsystems.md`](../research/discuss-exec-perf-adjacent-buildsystems.md),
[`discuss-exec-perf-community-testtime.md`](../research/discuss-exec-perf-community-testtime.md)).
Fowler's objection is quoted in the same artifact and is the one this design
must answer: the assumption "unchanged code ⇒ still-passing tests" fails under
state, config and timing. It is answered by the backstop, not by better
selection.

**Hex's current policy is stricter than the entire surveyed spec-driven-dev
field.** No SDD tool surveyed runs the full project test suite per task by
default: spec-kit bakes TDD ordering into a template rather than a per-task
budget and executes tasks sequentially with `[P]` tags advisory only; OpenSpec
works a checklist one item at a time; Spec Kitty — the only surveyed tool with
real worktree-lane concurrency — does **per-work-package incremental review
plus one whole-change validation at the end**, which is the same shape
converging here; Tessl publishes the field's only numeric effort budget (~7
tasks per batch, a fresh author≠verifier run once at the end)
([`discuss-exec-perf-competitive-sdd.md`](../research/discuss-exec-perf-competitive-sdd.md)).

**Incremental-by-default review is shipped commercial practice, and full-diff
re-review is the named failure mode.** Cursor's Bugbot reviews only the
changes since the previous Bugbot review by default, with full-PR review the
opt-in toggle ([Cursor Bugbot docs](https://cursor.com/docs/bugbot)).
CodeRabbit ships the distinction as two commands (`review` = incremental,
`full review` = from scratch). Against them, Copilot's per-push full re-scan
produced a documented five-round PR with counts 10 → 6 → 4 → 2 → 2 and the
practitioner complaint "if Copilot can find an issue on round 3, it should
find it on round 1"
([`discuss-exec-perf-community-reviewloops.md`](../research/discuss-exec-perf-community-reviewloops.md),
[GitHub community #189767](https://github.com/orgs/community/discussions/189767)).
The same artifact supplies the counter this design must absorb: **review
non-determinism on unchanged code** undermines delta-only strategies that
assume a stable baseline, and **oscillation** (fix A introduces B, fix B
reintroduces A) is mitigated by an iteration budget plus convergence
detection.

**A reliable delta anchor is hard elsewhere and easy here.** Tools re-review
full base→head because GitHub's since-last-review anchor is SHA-keyed and
breaks on force-push. Hex execution appends commits serially with no mid-run
rewrite, so a last-reviewed-SHA anchor is stable *during* a run
([`discuss-exec-perf-adjacent-increview.md`](../research/discuss-exec-perf-adjacent-increview.md)).
The same artifact names the documented miss class delta review cannot cover —
**semantic conflicts**, two independently correct changes that combine broken
with zero textual overlap — and reports that the documented backstop for it is
CI against the final tree, not a full re-review pass.

**Failure blast radius must be computed eagerly from the static graph, never
propagated per node.** This is the strongest single finding in
[`adr0010-operability.md`](../research/adr0010-operability.md): every DAG
runner that derived "which downstream nodes are affected" node-by-node has
years of bug history from it — GitLab `needs` skip-propagation inconsistencies
open since 2019
([#31526](https://gitlab.com/gitlab-org/gitlab/-/issues/31526),
[#281878](https://gitlab.com/gitlab-org/gitlab/-/issues/281878),
[#213080](https://gitlab.com/gitlab-org/gitlab/-/issues/213080)); Airflow
mapped tasks marked `upstream_failed` with no failed ancestor
([apache/airflow#27449](https://github.com/apache/airflow/issues/27449));
Bazel's "indirect incompatible target skipping can have highly non-local
silent effects" ([bazelbuild/bazel#18707](https://github.com/bazelbuild/bazel/issues/18707));
Argo steps depending on an omitted step vanishing from the rendered graph
([argoproj/argo-workflows#9852](https://github.com/argoproj/argo-workflows/issues/9852)).
Temporal takes the opposite approach — render from a durable event history
rather than infer live from per-node trigger state — and does not have the bug
class. GitHub Actions is the clean reference for the default itself: a job
runs only if every needed job succeeded, and the failure applies to the whole
dependency chain onward.

**Batching a check and bisecting the failure is the merge queue's whole
design, and it is the closest structural analogue to what this ADR does.** A
merge queue speculatively batches N pull requests, verifies the batch once
instead of N times, and — on a red batch — **splits it and re-verifies to
localize the culprit** rather than rejecting the whole batch or blaming the
last entry. Mergify's queue documents batch size as the direct
cost-versus-localization dial and bisects a failing batch to find the offender
([Mergify merge queue](https://docs.mergify.com/merge-queue/)); GitLab merge
trains build each merge on the cumulative result of the ones ahead and drop
the specific failing entry rather than the train
([GitLab merge trains](https://docs.gitlab.com/ci/pipelines/merge_trains/));
Zuul's gating pipeline is the oldest form of the same idea, testing speculative
future states and re-testing behind a failure
([Zuul gating](https://zuul-ci.org/docs/zuul/latest/gating.html)). This is the
same trade in a different domain — defer per-item verification, then pay a
bounded localization cost when the deferred check fails — and it supplies
C-904's answer directly: bisect, do not report a window.

**Checkpoint cadence should not be computed.** The Young/Daly optimum
(`T_c ≈ √(2δ(M+R)) − δ`) assumes a single process with i.i.d. exponential
failures. Its own research community disavows the extension: the 2024 survey
*Should we always checkpoint à la Young/Daly?*
([DOI 10.1016/j.future.2024.07.022](https://www.sciencedirect.com/science/article/abs/pii/S0167739X24003777))
extends the question to "workflow applications represented as a graph of
tasks" and reports the optimal period comes out "of a different order" than
the formula predicts. Every production checkpoint policy surveyed is a **dual
trigger** instead: Postgres fires on `checkpoint_timeout` **or**
`max_wal_size`, whichever comes first; CI converges independently on
fast-scoped-per-commit plus full-on-a-schedule-or-gate.

**Additive-optional-with-a-default is the industry-converged rule for a change
of exactly this shape, and a version field is the over-engineered answer.**
protobuf, Kubernetes CRDs and OpenAPI state it almost verbatim; Terraform's
`SchemaVersion` + `StateUpgraders` chain and k8s conversion webhooks exist for
the *non-additive* case and both ecosystems document "if you're only adding
optional fields, you don't need this"
([`adr0010-compat.md`](../research/adr0010-compat.md)). The same artifact
notes that hex's closest sibling, spec-kit, has not solved artifact-schema
migration at all — so there is no established convention to deviate from.

**A selective-test convention cannot normalize tool flags.** Across nine
ecosystems the input shape does not converge: Nx and Turborepo want a git ref
and compute their own diff; Jest's `--findRelatedTests` and a Cargo/Go glue
script want a file list; bazel-diff wants two hash snapshots; pytest-testmon
and a warm-cache `go test ./...` want **neither** and are stateful and
self-scoping. Fallback-to-full is equally non-uniform — Turborepo and
AffectedModuleDetector build it in and document it ("if the checkout is too
shallow, then all packages will be considered changed"), while Nx, Jest,
Vitest and bazel-diff document no automatic degrade at all
([`adr0010-tooling.md`](../research/adr0010-tooling.md)).

**Depth-1 is the field's converged ceiling.** Cursor caps subagent nesting at
one level deep; OSS Claude-Code swarms converge on topological waves; only
metaswarm claims true sub-orchestrator recursion, with no depth data. No
project found scales verification effort by task complexity — a per-WP verify
budget is unclaimed territory
([`discuss-exec-perf-competitive-swarm.md`](../research/discuss-exec-perf-competitive-swarm.md),
[`discuss-exec-perf-competitive-products.md`](../research/discuss-exec-perf-competitive-products.md)).

## Considered Options

Two axes carry real design freedom. Nesting (decision 4) and the failure
cascade (decision 5) do not: the council was unanimous against recursion ≥2,
and every surveyed DAG engine defaults to cascade-stop with per-edge opt-out.
Both are recorded as ratified and are designed, not re-compared.

### Axis 1 — the per-merge verification policy

| | Option |
|---|---|
| **A1** | **Status quo** — the project's full documented verification after every merge. |
| **A2** | **Scoped check per merge + dual-trigger checkpoints + full at coordinator joins and the final gate.** *(ratified)* |
| **A3** | **Scoped check per merge, backstop only at the final gate** — no checkpoints, no periodic full run. |
| **A4** | **Keep full verification per merge, but pipeline it** — relax `adr_0004` C-306's global one-at-a-time so merge *k*'s verification overlaps merge *k+1*'s launch. |
| **A5** | **Content-addressed incremental verification** — require or wrap a caching test runner (the Buck2 / `go test` model) so unchanged inputs are skipped by the tool, not by hex. |

Criteria and weights. *Wall-clock* is the point of the exercise; *correctness
residual* and *bisection radius* are what the change spends to get it;
*bundle surface* and *project prerequisite* are what the house constitution
prices most heavily (rung 4 of the drivers, and `DESIGN.md`'s two-layer rule).

| Criterion | Weight | A1 | A2 | A3 | A4 | A5 |
|---|---|---|---|---|---|---|
| Wall-clock reduction | 5 | 1 | 4 | 5 | 3 | 5 |
| Correctness residual (lower risk = higher score) | 5 | 5 | 4 | 2 | 5 | 4 |
| Bisection radius | 4 | 5 | 4 | 1 | 5 | 3 |
| Bundle surface added | 4 | 5 | 3 | 4 | 2 | 2 |
| Project-tooling prerequisite (none = 5) | 4 | 5 | 5 | 5 | 5 | 1 |
| Operability / legibility of a failure | 3 | 4 | 4 | 2 | 2 | 3 |
| **Weighted total** | | **102** | **100** | **81** | **94** | **78** |

**A1 scores highest and is still rejected — the scoring model is doing its job
here, not failing.** Every criterion but the first is a *cost* criterion, and
the status quo pays none of them; a weighted sum will always flatter it. The
decision driver that breaks the tie is not on the table: A1 is the option the
owner filed the complaint about, and "change nothing" is not an available
answer to "runs take days". Read the table as ranking the *changes*.

**Stated sensitivity: A2 beats A4 by six points on a 102-point scale, which is
inside the noise of any weighting anyone could defend.** Two of the six
criteria would have to move by one point to flip it. The choice is therefore
not carried by the arithmetic and is not claimed to be: A2 is the ratified
decision, A4 is the alternative the ratification declined, and the substantive
tiebreaker is in the prose below. A2's genuine margin is over A3 (19 points)
and A5 (22) — it buys four-fifths of A3's wall-clock for two points of
correctness residual and three of bisection radius, and it does so without
A5's project prerequisite.

**Why A3 loses.** It is the premortem seat's named failure mode made policy: a
single gate thirty merges late, with the whole run as the bisection range.
`adr0010-operability.md`'s survey has no example of a production system that
does selection with only a terminal backstop.

**Why A4 loses — the six-point call, argued rather than scored.**
`protocol.md` § Worktree work-package mechanics — C-306's own text, carried by `adr_0004` (also
`adr_0004:1346`) — says global one-at-a-time merge serialization "is an
operability choice … and is the first rule to relax if merge wall-clock ever
dominates", so this option has explicit standing in shipped contract text and
had to be scored seriously. **Two qualifications on that standing, because the
sentence is narrower than it first reads.** C-306 is **federation-scoped**: it
governs the global order across repos in a plan carrying a `Repo` column, and
is vacuous single-repo. So what A4 would relax on an ordinary run is not C-306
but the **verify/merge coupling** of `protocol.md` § Worktree work-package mechanics — "each merge
changes the base under the next", plus the verification after it — which is
grounded in *correctness* rather than operability and carries none of C-306's
invitation. A4 also preserves the correctness property A2 trades away,
completely. It loses on
bundle surface and operability: overlapping a verification with the next
merge means a failure arrives attributed to a tree that no longer exists, the
merge-conflict playbook's "apply at most one fix pass and re-verify" has to
grow a concurrency story, and resume has to reconstruct which verification was
in flight. That is a genuinely larger change than scoping a check, for a
saving bounded by the merge critical path rather than by the suite. **C-306's
lever is not spent — it is explicitly left available** for the federated case
it actually governs, and is the right next move if scoped checks land and
cross-repo merge wall-clock still dominates.

**Why A5 loses.** It is the fastest option on paper and the only one that
needs the project to bring tooling hex cannot supply. `go test` gets this free
from a content-addressed cache, Buck2 by construction — and Maven, Cargo and
plain pytest do not. Requiring it would put a Layer-1 prerequisite in front of
a Layer-0 hex behaviour, which inverts the two-layer model. It survives as
**the escape hatch inside A2** (C-906): a project that has such a runner
points hex at it and gets A5's economics for its own scoped checks.

### Axis 2 — review-round scoping

| | Option |
|---|---|
| **B1** | **Status quo** — every round re-reads the full diff; only the perspective set shrinks. |
| **B2** | **Delta rounds from a persisted last-reviewed anchor, plus a mandatory full-branch pass at the converged gate.** *(ratified)* |
| **B3** | **Delta rounds only** — no full pass (pure CodeRabbit-incremental). |
| **B4** | **Keep the full diff, bound the cost** — shrink perspectives (today) plus an explicit per-round token budget. |
| **B5** | **Content-keyed review cache** — hash each file's post-round content, re-review only files whose hash changed since any prior round. |

| Criterion | Weight | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|
| Token / latency reduction per round | 5 | 1 | 4 | 5 | 2 | 5 |
| Miss risk on unchanged code (lower = higher score) | 5 | 5 | 4 | 1 | 5 | 3 |
| Robustness to a history rewrite | 4 | 5 | 4 | 2 | 5 | 5 |
| Durable state added (none = 5) | 4 | 5 | 4 | 4 | 5 | 1 |
| Implementation complexity (lower = higher) | 3 | 5 | 4 | 4 | 5 | 2 |
| **Weighted total** | | **85** | **84** | **66** | **90** | **70** |

**B2 places third, one point below the pure status quo and six below B4, and
this is reported rather than re-weighted.** What the model is saying is
correct and worth reading: the correctness residual and durable state B2 pays
almost exactly cancel its token saving, so on cost-weighted grounds alone
delta review is close to a wash. The tiebreaker is again outside the table.
B1 and B4 are the do-nothing rows — B4 in particular shrinks each round's
*cost* without shrinking the *work*, which is not an answer to "round 3
re-reads everything round 1 read". Among the options that actually change the
scope, **B2 leads B5 by 14 and B3 by 18**, and it is the ratified decision.
The near-parity with B1 is the honest reason D-1 exists: outside the
repeated-invocation case, this half of the change is a small win.

**Why B4 loses — the top scorer, argued rather than scored, symmetrically with
A4.** A per-round token budget shrinks each round's *cost* without shrinking
the *work*: round 3 still re-reads everything round 1 read, just with less
budget to think about it, so the practitioner complaint that motivated this
axis ("if Copilot can find an issue on round 3, it should find it on round 1")
is untouched — and a budget that truncates a full-diff read is strictly worse
than a smaller read done properly. It scores highest because every criterion
but the first is a cost criterion it does not pay, exactly as A1 does on the
other axis. **Flip sensitivity, stated:** B2 overtakes B4 if its token
reduction is worth 5 rather than 4 — which is the single score the R = 2
finding below argues *against* raising, since inside a per-WP loop the delta
saving is smaller than the score already assumes. So the honest reading is
that B4's lead is real on the arithmetic and is overridden on grounds the
arithmetic does not carry: it is not an answer to the complaint.

**Why B3 loses.** `discuss-exec-perf-community-reviewloops.md` supplies the
direct counter: review non-determinism on unchanged code means a delta-only
strategy assumes a stable baseline it does not have. Gerrit, GitHub and
Graphite all keep the full view one click away. Dropping the converged pass
saves one review of a diff that has already been reviewed piecewise, and gives
up the only pass that can catch the semantic-conflict class.

**Why B5 loses, and what it was right about.** It is the strongest answer to
the fragility that motivates the whole anchor design — a content hash survives
the rewrite that invalidates a SHA. It loses on the house's hardest
constraint: a per-file hash map is a **durable state file**, and driver 5
forbids one at any depth. The property it was protecting is recovered for free
by C-908 instead: a rewritten history fails `git merge-base --is-ancestor` and
falls back to a full review, which is the safe direction. Recorded as
considered, and as the right shape if a future decision ever needs
review-state that outlives a branch's history.

## Decision Outcome

**Chosen: A2 + B2**, implemented as nineteen contracts, `C-901`–`C-919`, with
scenarios `S-901`–`S-910`.

The shape in one paragraph: **every WP merge pays a scoped check; a full
documented verification runs at coordinator joins, at dual-trigger
checkpoints, and at the final gate, which is mandatory and un-lowerable. A
`Verify` plan column lets an author raise a single WP's merge check to full.
Review rounds read from a last-reviewed anchor persisted in the plan's Status
block, guarded by an ancestry test that fails safe to a full review; one
full-branch pass is mandatory at the converged gate. A failed WP blocks its
dependents without halting the run, and strandedness is derived at report
time from the static DAG rather than stored per node. One append-only
`## Schedule log` section in the plan records, per merge, what became ready,
what stayed blocked, and which check was paid.**

### The arithmetic, and its sensitivity

Let `N` = merge count, `F` = full-verification wall-clock, `S` = scoped-check
wall-clock, `J` = coordinator joins, and `L`/`H` = level-clear and high-risk
checkpoints that do not coincide with the `M`-counter (C-903 resets the
counter on every full verification, so coincident triggers cost nothing).

- **Today:** `(N + 1) · F`.
- **After:** `(⌈N/M⌉ + J + L + H + 1) · F + (N − full-count) · S`.

With `M = 3`, `F = 6 min`, and a 12-WP plan:

| Case | Plan shape | `S/F` | `J+L+H` | Today | After | Cut |
|---|---|---|---|---|---|---|
| Suite-dominated | all-parallel (`L = 0`) | 0.25 | 0 | 78 min | 42 min | **46%** |
| Suite-dominated | all-parallel, typical overrides | 0.25 | 3 | 78 min | 55.5 min | **29%** |
| Build-dominated | all-parallel (`L = 0`) | 0.50 | 0 | 78 min | 54 min | **31%** |
| Ceiling (`S → 0`) | all-parallel (`L = 0`) | 0 | 0 | 78 min | 30 min | **62%** |
| **Linear chain** | **12 levels of 1 (`L = 12`)** | any | 12 | 78 min | 78 min | **0%** |

**Two sensitivities govern this, not one, and the second is plan shape.**

*`S/F` — how much a scoped check costs.* The saving is bounded above by
`(1 − S/F) · (1 − 1/M)`, so a project whose build costs half its suite cannot
save more than half of what a suite-dominated project saves.

*`L` — how wide the plan is.* Every row above but the last assumes `L = 0`,
the all-parallel best case, and that assumption is doing as much work as
`S/F`. Trigger (ii) fires when a dependency level clears, so a **fully linear
plan clears a level on every merge**, `L = N`, every merge runs full, and the
saving is **exactly zero** — the degenerate case C-903 already names, here
with its cost attached. Real plans sit between: a plan of `N` WPs in `k`
levels contributes at most `k` level-clear checkpoints, so the win scales with
`N/k`, the plan's average level width. **A plan hex could not parallelize is a
plan this ADR cannot speed up**, which is the honest statement and follows
directly from the backstop being level-shaped.

The brief's framing — "full-suite runs drop from O(N) to ~N/3 + joins + 1" —
is the *run-count* statement for a wide plan, and it is right there; the
*wall-clock* statement is the table above, more modest, because the scoped
checks are not free, the overrides are additive, and narrow plans forfeit the
saving entirely. Stating the run count without both ratios would overclaim.

**Review-side arithmetic is smaller still, and one reachable case is a net
loss.** For a branch diff `D`, `R` rounds, and `δ` the mean delta-round read:
today `R · D`; after, `D + (R−1)·δ + D`.

- **`R = 1`** (tier low): `2D` after against `D` today if the converged pass
  is counted as a second read — in practice the single round *is* that pass,
  so it is a wash. **No saving.**
- **`R = 2`**: `2D + δ` after against `2D` today. **A net loss of `δ`** — the
  mandatory converged pass costs a full read that today's second round already
  was. Two of the three reachable `R` values therefore save nothing or less
  than nothing *inside a single loop*.
- **`R = 3`**: `2D + 2δ` against `3D` — "about a third" **only as `δ → 0`**,
  and `δ` is not small when a round's fixes touch several files and drag their
  finding-adjacent neighbours in whole. At `δ = 0.3D` the saving is 13%, not
  33%.

**Where this half actually pays is across invocations, and the bound is worth
stating plainly: roughly one full read per `/hex-review` invocation, against
`R · D` today.** On a long-lived branch, invocation 2's round 1 starts from the
anchor rather than the base instead of re-reading everything invocation 1
already read — which is exactly the Copilot complaint quoted in § Industry
Context. Inside one loop, the mandatory converged pass eats most of the
delta saving by design, and that is the price of the correctness backstop
rather than an accident.

### Departures from dossier recommendations

Each is a departure from a *recommendation* or an open item, never from a
ratified decision.

1. **Checkpoint cadence is `M = 3`, not the dossier's suggested every-5th
   merge.** The dossier explicitly left the number to the architect ("architect
   tunes against suite cost").
   [`adr0010-operability.md`](../research/adr0010-operability.md) recommends 3
   on the ground that it bounds worst-case undetected rework to two WPs
   between checkpoints while still amortizing the full-suite cost across
   multiple cheap merges. At `M = 5` the bisection range is four WPs and the
   marginal saving over `M = 3` is one further full run per fifteen merges —
   the wrong side of the premortem seat's concern for a small gain.
2. **The ready-set log is its own append-only plan section, not entries in the
   Status table.** The dossier recommended logging "in the Status table". The
   Status table's rows are **per-WP and mutable**; a log is **per-event and
   append-only**. Writing events into mutable per-WP rows would overwrite the
   history the log exists to preserve — which is the exact mistake
   `adr0010-operability.md` finds in every runner that reconstructs state live
   instead of recording it when it is known.
3. **The oscillation stop is stated as a count comparison, not as "no new
   findings class two rounds running".** "Findings class" is not a defined term
   in the bundle and is not mechanically checkable. C-911 uses the
   `Block`/`High` actionable count, which is already a number every round
   produces.
4. **The oscillation stop ships at all.** The dossier left it conditional —
   "one contract line adding diminishing-returns stop … **else defer to the
   architect**" — so C-911 is a decision this ADR takes, not one it inherits,
   and it is named here rather than presented as ratified. **Ground:** the
   evidence for the failure it stops is direct and quantified.
   `discuss-exec-perf-community-reviewloops.md` records both halves —
   **oscillation** (fix A introduces B, fix B reintroduces A) named as a
   failure mode whose documented mitigation is "iteration budget **plus
   convergence detection**", and the Copilot round-count series
   (10 → 6 → 4 → 2 → **2**) whose terminal flat pair is exactly the shape the
   rule fires on. Hex today ships the iteration budget and **not** the
   convergence detection, which is half the documented mitigation. The cost of
   being wrong is one round of budget, and C-911's failure direction is
   deliberately late rather than early.

### Judgment calls made inside the ratified decisions

Three places where the ratified text underdetermined the design and this ADR
resolved it rather than escalating:

1. **A missing `Verify` column means the new default, not the old behaviour.**
   The compat research's "pin in-flight artifacts to old behaviour forever"
   rule (Airflow AIP-63) governs **artifact schema** changes. This is a **tool
   behaviour** change with a per-artifact override: a plan approved last week
   never stated a verification policy — `protocol.md` did — exactly as
   `adr_0002`'s ready-set dispatch changed launch timing for every existing
   plan without any column. Hex plans are re-read fresh on every run by a
   centrally-upgraded interpreter, which is the GitLab-CI shape the compat
   research itself carves out. So: old plans run under the new policy, and the
   column is an override, never the policy switch. The presence-check rule
   (C-915) still governs *reading* the column.
2. **The anchor has two scopes and only one is persisted.** Within a
   Review-Fix Loop the anchor is the SHA the previous round reviewed — it
   lives in the loop's own session state and never outlives its worktree, so
   persisting it would create state for something that cannot go stale. Across
   `/hex-review` invocations on the feature branch it must survive the session,
   so it lands in the Status block. One rule, one grammar, one persistence
   carve-out with a stated reason (C-907).
3. **The `Verify` column is raise-only, the mirror image of `Review`'s
   lower-only rule — and the symmetry is not "both go up".** Each column's
   baseline is set at the *unsafe* end of its own range so the unsafe
   direction is unreachable: `Review`'s baseline is the tier's full panel, so
   only down exists; `Verify`'s baseline is the scoped check, so only up
   exists. Stated as one invariant in C-905.

### Consequences

**Good.** The dominant serial cost in a large run drops by the table above.
Ready-set compliance becomes an artifact fact rather than a suspicion — the
schedule log makes a wave barrier visible in the committed plan. A failed WP
no longer halts a run that still has independent work to do. The `Review`
column stops being unowned debt. The bundle gains a per-WP verification budget
that no surveyed project ships.

**Bad, and accepted.** A regression introduced by merge *k* and caught at the
checkpoint after merge *k+2* is localized by C-904's bisection at a cost of
one extra full run, rather than pointing at one WP for free. Delta review can
miss a finding a full re-read of unchanged code would have surfaced
non-deterministically; the converged-gate pass is the answer and it is
mandatory. A project-documented selective-test command that silently
under-selects makes scoped checks weaker than advertised; the checkpoints and
the final gate are the only backstop, and C-906's post-failure fallback
catches a command that *fails*, never one that quietly selects too little.
**A flaky failure is treated exactly like a real regression, and this is a
stated v1 limit.** A flake at a checkpoint burns the fix pass, burns the
bisection (where it reproduces at all — where it does not, it surfaces as
C-904's "failure did not bisect", which is at least an honest diagnosis), and
can strand a WP that was never broken. Meta's data puts **84% of test
transitions down to flakiness**, so this is the common case, not the corner.
No retry machinery ships here: the obvious fix is the merge-queue pattern of
**one rerun of the failed tests before accepting a failure** — the same
single-rerun ceiling `adr_0009` C-813 already ships for remote checks — and
it is deliberately left to a follow-up rather than smuggled into a
performance ADR, since it is a correctness-policy change with its own budget
question.

**Deferred findings.** None of the five ratified decisions contains a defect
requiring re-ratification. Two limitations are recorded rather than fixed:
**(D-1)** the review half of this change is a wash at `R = 1`, a **net loss of
one delta read at `R = 2`**, and worth about a third only at `R = 3` with a
small `δ` — inside a single loop the mandatory converged pass eats the saving
by design. The bound worth quoting is **roughly one full read per invocation
against `R · D` today**, so if review wall-clock is the owner's actual
complaint the lever is the branch-level `/hex-review` across invocations, not
the loop. **(D-2)** the scoped check does not run a merged WP's *dependents'*
contract tests, so a dependent broken by this merge can go undetected **until
the next checkpoint or the final gate** — up to `M − 1` further merges. The
widening was declined on cost, not on coverage (open question 2); an earlier
draft justified the decline by claiming the last checkpoint had already
covered those dependents, which is false — the last checkpoint verified the
tree *before* this merge and says nothing about what this merge broke. The
backstop is the *next* checkpoint, and the residual is that gap.

## Component contracts

Contracts are numbered `C-9xx`; UX scenarios `S-9xx` — the next free range,
after `adr_0009`'s `C-8xx` (verified free: no `C-9xx` or `S-9xx` token exists
anywhere in the repository, and the scenario range currently ends at `S-813`).
Predecessors: `adr_0001` `C-00x`, `adr_0002` `C-1xx`, `adr_0003` `C-2xx`,
`adr_0004` `C-3xx`, `adr_0005` `C-4xx`, `adr_0006` `C-5xx`, `adr_0007`
`C-6xx`, `adr_0008` `C-7xx`/`S-7xx`, `adr_0009` `C-8xx`/`S-8xx`. Home names
the single definition or edit site; "(sole source)" marks a definition every
other file links to rather than restates.

### A. The verification budget

| ID | Contract | Home |
|---|---|---|
| **C-901** | **The merge gate is a scoped check; full verification runs on three policy triggers plus two override paths.** The sentence "Run the project's documented verification **after every merge**" is replaced by: *after each WP merge onto the feature branch, run the **scoped check** (C-902).* The project's full documented verification runs on **three policy triggers** — **(i)** the merge of a **coordinator-owned WP**, which pays a full post-merge verification rather than a scoped check — the `join` trigger, and the one place a merge's gate is decided by *who owns the WP* rather than by a counter; **(ii)** a **checkpoint** (C-903); **(iii)** the **final gate** — the Review-Fix Loop's exit gate and the plan's terminal verification — which is **mandatory, un-lowerable, and reached by every run that completes** — and on **two override paths**: **(iv)** a `Verify: full` cell or a `Verify-default: full` Status line (C-905), and **(v)** a **degrade** to full under C-902 (no discoverable assembly gate, no runner-addressable WP tests) or C-906 (shallow-clone pre-flight, or a selective command that failed). **Four of the five appear in the schedule log's `<trigger>` vocabulary** (C-912) as `join`, `counter`, `level-clear`, `high-risk`, `column`, `degrade` — (i), (ii) contributing three of its own, (iv) and (v). **The final gate (iii) has no `<trigger>` value**: it is not a merge, so it produces no log entry at all. Nothing else changes about merging: serialization, topological order, the frozen base, merge-time file-set re-validation and `(Repo, path)` disjointness are untouched. **The rationale the old sentence carried is preserved, not deleted** — cross-file interactions still surface only post-merge, which is precisely why (ii) exists and why its cadence is bounded rather than left to the end of the run. **The Implement-phase verification is not this gate and does not change**: `protocol.md` § The Review-Fix Loop phase 3 already reads "for changed files", and the leaf-under-coordinator compile-only carve-out is unchanged. **Sub-WP merges are not merge-gate sites at all** — a coordinator's dotted sub-WPs merge into the coordinator's own **shared worktree**, never onto the feature branch, so they run neither a scoped check nor a counter increment, and they produce no log entry. The coordinator's own in-worktree join check (`coordinator.md`, unchanged) stays the coordinator's business. **The parent WP's merge onto the feature branch is the one gate site the subtree produces**, and trigger (i) makes it a full post-merge verification — which is what the two-tier precedent actually needs, since the in-worktree join proves nothing about the feature branch it has not yet merged into. | `protocol.md` § Worktree work-package mechanics (the amended sentence) → links to § Verification (sole source) |
| **C-902** | **What a scoped check is — a floor, a default source, and a never-invent rule.** A scoped check is **two things, both required**: **(a)** the WP's **own contract tests** — the Specify-phase tests naming the `C-`/`S-` IDs in that WP's `Scope` cell; and **(b)** the project's **cheapest documented gate that proves the merged tree assembles** — its build, parse, or type check. Both run against the **post-merge feature branch**, never against the WP branch: the check exists to catch what merging changed. **How (a) is invoked, and the one path-passing convention hex may use:** run the project's documented verification **restricted to the WP's declared test files** — the paths its Specify phase created, which the plan's `Expected Files` already names — passed as trailing path arguments where the runner accepts them (`pytest <paths>`, `go test <pkgs>`, `cargo nextest run -E …`, `npx jest <paths>`). hex appends paths; it **never rewrites the documented command, invents a flag, or maps a path to a runner-specific selector**. **Where the runner does not accept paths, or the WP's test files cannot be resolved, (a) degrades to the full documented verification for that merge** — the same degrade shape as (b). **Where the project documents a selective-test command (C-906), it is run *in addition to* (a) and (b), never instead of them** — the two-part floor is a floor. A selective runner widens what a merge check catches (it reaches tests the WP's own contract tests do not name); it cannot certify that the WP's own contracts still hold, which is the one thing (a) exists to prove. Where a stateful zero-placeholder tool (`pytest --testmon`) re-runs some of the same tests, **the redundancy is accepted and cheap** — that tool selects on its own dependency data and skips what it can, so the overlap costs near nothing and is not worth a rule to avoid. **hex never invents either half.** § Verification's standing rule binds unchanged: discover from project context, cached in `hex.md › Pointers`, verify the pointer on consumption, re-detect on a miss; where nothing is documented, detect once for this run and suggest `/hex-init`. **Where no build/parse gate can be discovered, (b) degrades to the full documented verification for that merge** and the degrade is announced once — a scoped check with no assembly proof is not a scoped check. **Both degrades are logged as `full(degrade)`** (C-912) so a run that silently stopped being scoped is visible in the artifact rather than only in a suite bill. **Scope: only merges onto the feature branch.** A coordinator's sub-WP merges land in the coordinator's shared worktree and are **not** scoped-check sites (C-901). | `protocol.md` § Verification › Scoped check (new subsection, sole source) |
| **C-903** | **Checkpoint cadence — a dual trigger with a risk override, and a testable high-risk predicate.** A **checkpoint** is a full documented verification run after a merge. It fires when **any** of three conditions holds, whichever comes first: **(i)** `M = 3` merges have completed since the last full verification **of any kind** — a coordinator join resets the counter exactly as a checkpoint does, so a join-dense plan never double-pays; **(ii)** the merge just completed **cleared a dependency level** — every WP in the level that was the shallowest unfinished one before this merge now has Status `merged` **or `failed`**; **(iii)** the merge just completed was **high-risk**. **`failed` counts as cleared for this trigger and only for this trigger**, because a failed WP never reaches `merged` and the level would otherwise be permanently unclearable, silently killing (ii) for the rest of the run (C-913). **"Dependency level" deliberately avoids the word *wave***: `protocol.md`'s wave is a plan-time reporting assignment and this ADR's whole premise is that waves do not gate launch. The tension is acknowledged rather than hidden — a level-shaped *checkpoint* trigger inside an ADR that de-barriers levels is defensible only because it gates a **check**, never a **launch**: nothing waits for it, and the ready-set is untouched. **Firing on any trigger resets the counter**, so coincident triggers cost one full run, not two — the Postgres `checkpoint_timeout OR max_wal_size` shape. **`M = 3` is shipped text, not a knob**; `config.md` gains no key (C-918). **High-risk is evaluated at merge time against the WP's actual merge diff — the file list `git diff --name-only <base>..<wp-branch>` already produces for merge-time file-set re-validation, so this adds no command** — and holds when that list contains **either** *(1)* a path the project documents as security-sensitive or hot-path, **or** *(2)* a **`(Repo, path)` pair** that appears in **any other WP's** `Expected Files` anywhere in the plan — a file two WPs touch across levels is a hub, and hubs are where merge-order-dependent breakage lives. **The key is `(Repo, path)`, not the bare path, for the same reason the parallelism check uses it** (`protocol.md:375-384`, C-316): satellites routinely declare textually identical repo-relative paths (`Cargo.toml`, `src/**`) that are disjoint across repos, and a bare-path comparison would mark half a federated plan high-risk and run the full suite on every merge. With no `Repo` column every pair is `(., p)` and the test is byte-identical to a path comparison. The run-count arithmetic in § The arithmetic is therefore **per repo**, as verification itself already is (C-321). **Clause (1)'s source is the `hex.md › Pointers` row C-917 establishes, and until that row exists clause (1) is vacuous.** It is **not** inherited from the Review-budget heuristic, which names those words (`protocol.md:387-388`) but **cites no source for them** — a gap this ADR records rather than papers over. The shape and timing precedent is the sibling that *is* specified: `protocol.md:392-397`'s merge-time budget re-validation, which likewise re-tests a plan-time judgment against the actual diff immediately before the merge. **The degenerate case is stated: if every merge fires a trigger, the run performs exactly today's behaviour** — correct, merely not faster. | `protocol.md` § Verification › Checkpoints (sole source) |
| **C-904** | **A checkpoint or final-gate failure is bisected to a culprit WP before it escalates — never reported as a window.** Today's merge-conflict / post-merge-failure playbook marks "the WP" `failed` after one fix pass, which was sound when every merge was fully verified. Under C-901 a checkpoint failure implicates **any** merge since the last full verification. The playbook gains a **window variant**, and only for a failure detected at a full verification: **(1)** the orchestrator applies **at most one** fix pass on the feature branch and re-verifies, exactly as today; **(2)** still failing, it **bisects the window** — *when there is a window to bisect*. The window is the ordered list of merges since the last full verification, and **every one of them recorded its post-merge feature-branch SHA in the `## Schedule log` (C-912)**, so the bisection needs no new bookkeeping and no `git bisect` invocation: check out an already-recorded intermediate SHA, run the same full verification, and halve. **Cost is bounded at `⌈log₂ M⌉` extra full runs — two, at `M = 3`.** With a known-good base and a known-bad tip, `M` merges leave `M − 1` unknown SHAs to probe, so three candidates take two probes in the worst case and one in the best; the earlier draft's "one" was the best case quoted as the bound. **(3)** The culprit WP is named and marked `failed`; from there the cascade governs (C-913(b)) — **the run does not halt**, it continues while any WP is eligible — and the end-of-run escalation names **the culprit, not the window**. **Two cases have no window and therefore no bisection**, and both route to the ordinary root-cause path the Review-Fix Loop already owns rather than claiming a localization this contract cannot deliver: **(i)** an **empty window** — the failing verification is the final gate and the last full verification already covered the last merge, so nothing merged since; **(ii)** a **post-review-fix failure**, where the change under suspicion is an edit made on the feature branch rather than a merge, so it has no WP to attribute and no recorded SHA to probe. **A third case has a window but does not localize**: a non-deterministic or order-dependent failure that does not reproduce at an intermediate SHA. That one is reported as *"failure did not bisect"* over the window, which is itself the diagnosis. **No WP is marked `failed` on a non-bisecting failure**, because naming the last-merged one would be a guess the four-status column then presents as fact. This is the merge-queue pattern: batched speculative merges plus bisection of a failing batch is how Mergify's queue batches, GitLab merge trains, and Zuul's gating pipeline all localize a failure they deliberately deferred — the same trade this ADR makes, with the same answer. A scoped-check failure is unchanged: it implicates exactly the merge that just ran, and the existing playbook applies verbatim. | `protocol.md` § Worktree work-package mechanics (playbook amendment) |
| **C-905** | **The plan table's budget columns — one grammar, two instances, and a retro-claim.** A **budget column** scales one axis of per-WP effort away from the shipped default **in exactly one direction, fixed per column and stated in shipped text**. The direction is chosen so the *unsafe* direction is unreachable: a column whose baseline is the maximum may only lower; a column whose baseline is the minimum may only raise. Two instances: **`Review` (`self \| light \| panel`) — retro-claimed by this ADR.** It has shipped since the 2026-07-20 perf pass with no owning contract ID, which is pre-`adr_0003` debt this ADR closes rather than leaves for a third budget column to trip over. Its semantics, heuristic and merge-time re-validation escalation are **unchanged in every byte**; it is lower-only against the tier's panel baseline; a missing column or cell means `panel`. **`Verify` (`scoped \| full`) — new, and it sits immediately after `Review`**, the two budget columns adjacent so the family reads as one — the same positional discipline `adr_0004` C-302 applied in fixing `Repo` at the second position. It sets the WP's **merge gate** (C-901) and nothing else: `full` runs the project's full documented verification after this WP's merge and **resets C-903's counter like any other full run**; `scoped` is the default and is written only for readability. It is **raise-only** — there is deliberately no value below `scoped`, because a merge check with neither contract tests nor an assembly proof is not a check. A missing column or cell means the plan's `Verify-default:`, else `scoped`. **Assignment is plan-time and justified in one line when used**: `full` declares author judgment the merge-time high-risk predicate cannot see — a WP that changes a default, a schema, or a config value nothing textually references. **One plan-level escape, so reverting the policy is one edit rather than N cells:** an optional Status-block line **`- Verify-default: full`** sets the default every empty `Verify` cell inherits, restoring pre-`adr_0010` behaviour for that plan; individual cells still override it, absence means `scoped`, and it is presence-checked like every other new field (C-915). This is the mechanism the rollback path leans on (§ Migration) — without it, "put it back" on a 30-WP plan means thirty cells. Both columns and the default line are **plan-artifact fields, not config**: `config.md`'s frozen six-key vocabulary (C-223) is untouched, and this is why. | `protocol.md` § Parallel-by-default decomposition (assignment, sole source); § The Review-Fix Loop (`Review` consumption, unchanged); § Verification (`Verify` consumption); plan template's table + comment |
| **C-906** | **The selective-test convention — an opaque template, two placeholders, and a post-failure fallback.** Where a project has a selective test runner, `/hex-init` records **one opaque shell-command template** in **project context** — Layer 1, because "how to verify" is project knowledge by `DESIGN.md`'s two-layer rule — with a `hex.md › Pointers` row to where it landed. hex substitutes **textually and never interprets**, and translates nothing into any tool's flag dialect. **Two optional named placeholders, and no others:** `{base}` — one git ref, resolved to the WP's recorded base; `{files}` — the WP's changed file list, **shell-quoted**, space-separated. **A template may use zero, one, or both.** Zero-placeholder templates are **valid and expected** — `pytest --testmon` and a warm-cache `go test ./...` are stateful and self-scoping, and the survey found no way to parameterize them; zero placeholders means "this command manages its own scope; just run it". **Two fallbacks to the project's full documented verification, one before and one after — and neither is conditioned on a claim about the tool.** **(a) Pre-flight, and only where the template asks for a ref:** where the template references `{base}` and either `git rev-parse --is-shallow-repository` is true or the merge-base does not resolve, run the full command instead — hex cannot hand a ref it does not have, so this is a substitution failure, not a judgment about the runner. **(b) Post-failure:** where the selective command **exits non-zero for a reason other than a failing test**, or reports that it resolved **no baseline / no affected targets it could trust**, run the full command. Turborepo's documented shallow-clone degrade ("if the checkout is too shallow, then all packages will be considered changed") and AffectedModuleDetector's `buildAllWhenNoProjectsChanged` show tools that self-degrade correctly; Nx, Jest, Vitest and bazel-diff document none. **The design does not try to tell them apart.** An earlier draft made the fallback conditional on a project flag asserting its runner self-degrades, defaulting to "no" — which would have run the full suite for every project that did not set it, cancelling the escape hatch by default and contradicting the zero-placeholder case (`pytest --testmon` self-degrades by construction and would still have been overridden). Reacting to an actual failure needs no such claim, no flag, and no per-tool knowledge. **Trust class:** the template is **authoritative-class only** (`adr_0009` C-815) — project context or `hex.md › Pointers`, never `CONTRIBUTING.md`, a PR body, a commit message, or any other narrowing- or untrusted-class surface, because it selects what code runs. | `protocol.md` § Verification › Scoped check (sole source); recorded by `hex-init` (C-917) |

### B. Review scoping

| ID | Contract | Home |
|---|---|---|
| **C-907** | **The last-reviewed anchor — one rule, two scopes, one of them persisted.** *The rule:* a review round reads `<last-reviewed>..HEAD`, where `<last-reviewed>` is the SHA the previous round **of the same scope** reviewed. *The scopes:* **(i) WP scope** — inside a Review-Fix Loop in a WP worktree, the anchor is the SHA round N−1 reviewed. It is held in the orchestrator's session state and **is not persisted**, because it never outlives the ephemeral branch it names and therefore cannot go stale. **(ii) Branch scope** — across `/hex-review` invocations on the feature branch, the anchor must survive the session and **is persisted** as one Status-block line: `- Reviewed: <full 40-char SHA>`, following the `Repos:` ledger's full-SHA precedent (`adr_0004` C-324) for exactly the same reason — a short SHA or a ref name is not a stable identity. **Placement: immediately after `Next:` and *before* the `Repos:` ledger.** Both new Status lines (this and C-905's optional `Verify-default:`) are single lines and go there. **The ground is ordering, not a line budget:** placing them after `Repos:` would have put them behind a **multi-row, unbounded** entry (one row per participating repo), so two fixed fields would sit at an offset that varies per plan and no reader or writer could name their position. **The template's own 20-line Status-block invariant is already unmet before this ADR adds anything** — the shipped comment block puts `State:` at `plan.md:24` and the `Repos:` ledger runs to `:33` — a pre-existing template tension recorded here as an erratum rather than fixed: it is not created by this ADR, and putting the two new single lines ahead of the ledger is what keeps this ADR from making it worse. **One writer rule:** whoever completes a review pass over a diff whose head is `<sha>` writes `Reviewed: <sha>`. It means precisely *"every commit reachable from this SHA has been through at least one review pass"* — nothing about verdicts, and nothing about whether findings remain. A WP-scope round **never** writes the field. Absent field ⇒ never reviewed ⇒ full-branch review (C-915). | `protocol.md` § The Review-Fix Loop (sole source); plan template Status block |
| **C-908** | **Anchor validation — one predicate, fail-safe, and the finalize interaction it exists for.** Before a persisted anchor is used, assert that it lies **inside the range this review is about** — reachability alone is not enough. **Two tests, both required:** `git merge-base --is-ancestor <anchor> <HEAD>` **must pass** (the anchor is reachable), **and** `git merge-base --is-ancestor <anchor> <resolved-base>` **must fail** (the anchor is not already behind the baseline). The second test is what closes a fail-open hole the first cannot: a trunk SHA, or any common ancestor, is a perfectly good ancestor of HEAD, so a one-test check would accept it and review only `trunk..HEAD` **minus the feature-branch commits that precede it** — silently omitting reviewed-looking work nobody reviewed. An anchor **equal to the merge-base** fails the second test and is treated as valid-and-degenerate: its range is the whole branch, which is a full review anyway. On a miss of either test the anchor is invalid: **fall back to a full-branch review**, announce the fallback with its reason, and rewrite the anchor at the end. This is a degrade, never a halt — a redundant full review costs time, while a wrong-scope review silently reports on a diff it did not read. **A missing object is a miss, not a crash**: where the anchor SHA no longer resolves (garbage-collected after a rewrite), the command's failure is treated as a failed ancestry test. **This is the sole staleness predicate, and it is sufficient by construction.** `/hex-finalize`'s recomposition is explicitly **not SHA-stable** (`adr_0009` C-807/C-808: `reset --soft` plus re-signing mints fresh ids), and finalize is explicit-invocation-only rather than gated on plan State — so a finalize run **will** invalidate a stored anchor with no signal in the plan. A rebase, a reset and a force-push all manifest identically as a failed reachability test, and an out-of-range anchor as a failed range test; enumerating causes separately would add predicates that can disagree. **What is deliberately *not* claimed is that an anchor from another branch always fails** — one that happens to be a shared ancestor passes reachability, which is precisely why the range test exists rather than the reachability test alone. **The `backup/<branch>-…` ref is a diagnostic, never a second predicate:** an *inert* ref for this branch explains *why* the ancestry test failed and is named in the fallback announcement; an *armed* ref means `hex-state.md`'s existing rule already forbids acting on the branch at all, so there is no interaction left to design. | `protocol.md` § The Review-Fix Loop (sole source) |
| **C-909** | **Delta round scope, and the mandatory full pass that makes it safe.** Round N ≥ 2 reads **`<last-reviewed>..HEAD` plus finding-adjacent files** — the files named by the prior round's actionable findings, in full, even where the delta does not touch them, because a fix's correctness is judged against its surroundings. Round 1 reads the anchor's range where one is valid, the full diff otherwise — **except at tier `low`, where a valid anchor never narrows round 1**: the 1-round cap makes that single round the whole loop, so it reads the full scope and *is* the mandatory converged pass. **One full pass is mandatory at the converged gate** — after actionable findings reach zero and before the exit gate — **never delta-scoped, never skipped, not lowerable by any budget column.** **"Full" resolves per C-907's two scopes and is not the feature branch in both:** a **WP-scope** loop's converged pass reads **the WP branch's own full diff against its recorded base** — the scope that loop has reviewed all along — and a **branch-scope** pass reads the **whole feature branch**. Reading the feature branch at the end of every per-WP loop would re-review every already-merged WP once per subsequent WP, which is `O(N²)` and is the opposite of this ADR. It absorbs **two documented misses and one derived from first principles** that delta scoping cannot: the documented pair are **review non-determinism on unchanged code** and **semantic conflicts** (two independently correct changes combining broken with zero textual overlap); the third, **collateral breakage through a shared symbol** — a fix that changes a signature, contract or invariant and breaks an *unchanged* caller — is **not corpus-attested and is not claimed to be**: it follows from the scoping rule itself, since such a caller is in neither the delta nor the finding-adjacent set, being neither touched nor named by the finding. **Two clauses the `Review` budget forces, stated operatively rather than left to rationale:** a converging round that **already read the full scope** satisfies the mandatory pass rather than paying a second one, and a **`self` WP has no Review-Fix Loop and therefore no WP-level converged gate** — the branch-level `/hex-review` pass is its backstop. The existing per-finding oscillation rule ("a finding that surfaces two rounds running auto-defers") is unchanged, and the round-N perspective-shrinking rule is unchanged — **delta scoping shrinks the diff *in addition to*, never instead of, shrinking the perspective set**. | `protocol.md` § The Review-Fix Loop (sole source) |
| **C-910** | **`/hex-review`'s baseline may be the anchor; full-branch stays the default.** Baseline resolution gains one step, inserted **after** an explicit `--base` and **before** a PR's fetched base ref: where the traced plan carries a valid `Reviewed:` anchor (C-908) **and** the invocation is a review round continuing that plan's loop, the anchor is the baseline. **Every other invocation resolves the baseline exactly as today** — a standalone "review this branch" is a full-branch review, because a human asking for a review of a branch is asking about the branch. `--base` always wins, which is also how a human forces a full re-read. **An empty `anchor..HEAD` diff does not take the clean exit** (`hex-review/SKILL.md:106`, "an empty diff reports 'nothing to review' and exits clean"): that exit is correct for a genuinely empty *target*, and wrong for a delta round that simply found nothing new since the anchor while the mandatory converged-gate pass (C-909) is still owed. An empty delta means **proceed to the converged pass**, not exit; the clean exit still applies where the *baseline-to-HEAD* diff is empty with no pass outstanding. **`hex-review` still never loops on its own output**, still never edits the code or diff under review, and still never commits; `adr_0005`'s fold-back contracts are untouched — C-401 and C-412 are unchanged, and C-410's exclusive ownership of plan State `done` is unchanged, with the one added constraint in C-913. Writing the anchor is a Status-block write, the class of write `hex-review` already performs. | `hex-review/SKILL.md` § Resolve the target and baseline |
| **C-911** | **The diminishing-returns stop — a second exit condition, severity-aware, with the cap's existing behaviour.** Let `A(N)` be the count of **actionable findings graded `Block` or `High`** at the end of round N, after the per-finding auto-defer rule has been applied. **Severity is orthogonal to the actionable/deferred class** (`adr_0006` C-502, `protocol.md` § Finding severity), so the stop must name both axes or it counts a naming nit against a data-loss bug. `Warn` and `Suggest` are excluded: a round that converts one `Block` into three `Warn`s has converged, and a count blind to that would call it oscillation. **At tier low the severity ladder is not applied** and the tag is absent, so `A(N)` there counts all actionable findings — the same degrade `protocol.md` already defines for every severity consumer. **The stop fires when both hold:** `A(N) ≥ A(N−1)` for `N ≥ 2` — the `Block`/`High` count did not **strictly** shrink — **and** round N introduced **no new `Block` or `High`** that was not present in round N−1. The second clause is what keeps the stop from firing on genuine progress: a round that surfaces a *new* serious defect is doing its job, and stopping there would escalate a loop that had just found something. When it fires the loop **stops and escalates to the user with the outstanding list**, byte-for-byte the terminal behaviour hitting the loop cap already produces. No new escalation path, no new message shape. **Ground, stated at the strength the evidence supports:** the strictly-decreasing expectation was derived from the observed constant-input case — the documented Copilot round counts (10 → 6 → 4 → 2 → 2) re-read the *same* full diff every round. Under delta scoping the input shrinks too, so part of any observed decrease is an artifact of the scope, not of convergence, and the rule is an **expectation, not a law**. It is shipped anyway because **its failure direction is benign**: a decrease that is scope-artifact makes the stop fire **late** — the loop runs to its cap, which is today's behaviour — never early, and the severity floor further biases it toward late. `A(N) = 0` is the **exit gate**, not this stop. The stop can only fire **earlier** than the loop cap and never raises it; the `hex.md › Preferences` `loop rounds` ceiling is untouched. | `protocol.md` § The Review-Fix Loop (sole source) |

### C. Scheduling observability and the failure cascade

| ID | Contract | Home |
|---|---|---|
| **C-912** | **The schedule log — one append-only plan section, one entry per merge, five facts.** The plan gains **`## Schedule log`**: append-only, one bullet per merge, never edited or reordered. Grammar, one line: `- <ISO-8601 UTC> · merged <WP> @ <post-merge SHA> · verify <scoped \| full(<trigger>)> [<elapsed>] · ready: <ids \| —> · blocked: <id (<blocker>), … \| —>`, where `<trigger>` is one of `join`, `counter`, `level-clear`, `high-risk`, `column`, `degrade` (C-901). **The post-merge SHA is mandatory** — it is what makes C-904's bisection free, and recording it costs the `git rev-parse HEAD` the merge already implies. **Capture is deliberately cheap and best-effort:** the orchestrator brackets each merge-plus-check with `date -u +%FT%TZ`, and `<elapsed>` is the difference — **wall-clock only, never CPU, never a benchmark**, and **optional**: a step that lost its start stamp writes the entry without it rather than omitting the entry or inventing a number. Nothing in this ADR gates on `<elapsed>`; § Validation's wall-clock check measures externally and treats the field as corroboration. **It lives in the plan, not in a state file.** The plan is already the WP-level state of record (`adr_0002` C-105) and is already mutated per merge by the Status column, so this is the existing writer touching the existing artifact; a second durable location would split the record, need a gitignore audit item, need a cleanup lifecycle, and make resume read two files — against driver 5, which forbids nested or additional state at any depth. Being committed is a feature: the drift evidence lands in the PR and survives the session. **Five facts, one line, on purpose.** `ready:` and `blocked:` make a wave barrier visible as drift — a ready-set that never widens is the symptom complaint 1 described. `verify` and `<elapsed>` make the dogfood's full-run count and the phase attribution mechanically checkable **from the artifact rather than from a transcript**. Bounded by construction: entries = feature-branch merges — dotted sub-WP rows produce none (C-901). **It replaces the plan template's `## Progress Log` in place** (`plan.md:400`) — a free-prose `Date \| Update` table no contract has ever written to or read — and that is its one and only home in the template. Two logs of the same events, one structured and one not, is the drift the sole-definition rule exists to prevent; the unwired one is **retired, not kept alongside**. **Absent section ⇒ a pre-`adr_0010` run**, never an error (C-915), and a plan carrying a hand-written `## Progress Log` keeps it untouched. | `protocol.md` § Parallel-by-default decomposition (sole source); plan template's new section, replacing `## Progress Log`; written at `hex-execute/SKILL.md`'s "Recompute the ready-set after every merge" step |
| **C-913** | **Failure cascade — derived strandedness, one eager pass, no fifth status, and a run that drains before it reports.** *(a) Dispatch needs no new mechanism.* The ready-set rule already makes a WP eligible only when every `Depends-on` is `merged`, so a dependent of a `failed` WP simply never becomes eligible, and independent siblings keep flowing. Nothing about dispatch changes. *(b) The barrier goes.* The playbook's "**halt the wave** … and escalate to the user" is amended: a `failed` WP is marked `failed` as today, and **the run continues while any WP is eligible**, escalating **at the end** rather than immediately. The state summary that escalation carries becomes the stranded report. *(c) Strandedness is **derived, never stored**.* The four statuses (`pending \| active \| merged \| failed`) are unchanged and no fifth is added; a stranded WP is `pending`, which is already true and already correct. The stranded set is computed **once, eagerly, in a single pass over the plan table's own static `Depends-on` edges**, at report time. This is the direct fix for the bug class every surveyed runner shipped by materializing an `upstream_failed` state per node — GitLab's decade of skip-propagation issues, Airflow's `upstream_failed` with no failed ancestor, Bazel's "highly non-local silent effects", Argo's vanishing steps. It also leaves `adr_0002` C-105's parent rollup rule untouched, which a fifth status would have broken. *(d) Report shape:* the failed WP(s) named first, then one line per stranded WP naming its **direct** blocker — `WP7 — blocked by WP4 (stranded) ← WP2 (failed)` — plus what did complete, read from the plan's existing `Shippable after wave` line. *(e) One interaction with C-903, stated at both ends:* a `failed` WP never reaches `merged`, so its dependency level would be permanently unclearable and checkpoint trigger (ii) would go **silently dead** for the rest of the run. C-903 therefore counts `failed` as cleared for level purposes — the one place in this ADR where `failed` is treated like a terminal-and-done status, and only for a *check* trigger, never for eligibility, rollup, or the terminal rule below. *(f) Terminal rule:* a run that ends with a non-empty stranded set **never presents a green final gate as plan completion** and **never reaches the plan's terminal review state — `done`, or `landing` for a plan carrying a `Repo` column** (`adr_0004` C-324), since a federated plan reaches `landing` rather than `done` and a precondition bound to `done` alone would not hold there. `hex-review` remains the sole writer of that state (`adr_0005` C-410) and gains this one precondition. | `protocol.md` § Worktree work-package mechanics (playbook) + § Parallel-by-default decomposition (sole source); the `done` precondition qualifies `archive.md` |
| **C-914** | **Depth-1 and the flat state surface — a stated non-change, now load-bearing.** Nesting stays capped at the existing `orchestrator → coordinator → leaf` chain. **No new orchestrator role, no recursion ≥ 2, no per-coordinator state.** The council was unanimous against recursion on three grounds (multiplicative re-verification across levels, LLM over-decomposition as a default tendency, unbounded resume tree-walks), and hex already ships the "tiny loop" the complaint asked for: a coordinator runs a local scoped implement→review→verify per subtree and the authoritative verification at the join — the two-tier verify precedent this ADR generalizes rather than replaces. **The hard requirement is restated here because this ADR is the first that could have broken it:** state is **one flat Parallelization table** with dotted WP rows and computed rollups. C-912's schedule log is held to it explicitly — **one section per plan, never one per coordinator**, and a coordinator's sub-WP merges appear in it **not at all** — they land in the coordinator's shared worktree, are not merge-gate sites, and increment nothing (C-901, C-902). The parent WP's merge onto the feature branch is the one entry the subtree produces. | this ADR (a stated non-change); `protocol.md` § Worker coordination unchanged |

### D. Compatibility

| ID | Contract | Home |
|---|---|---|
| **C-915** | **Presence-check compatibility — a permanently valid legacy shape, and no version field.** Every reader branches on **field presence**, never on a compared version number. **Absent `Verify` column or cell ⇒ the plan's `Verify-default:`, else `scoped`** (C-905). **Absent `Verify-default:` line ⇒ `scoped`.** **Absent `Reviewed:` line ⇒ never reviewed ⇒ full-branch review** (C-907), never an error. **Absent `## Schedule log` ⇒ a pre-`adr_0010` run**, never an error. **No `Plan-Schema:` field is added, and none may be inferred** — this change is purely additive-optional, which protobuf, Kubernetes CRDs and OpenAPI all treat as a non-event, and Terraform's `SchemaVersion`+`StateUpgraders` and k8s conversion webhooks both document as *not* needing their machinery. The existing precedent in the bundle is followed verbatim: dotted sub-WP IDs and the `Repo` column each state "no schema-version marker — the presence of the column is the signal", and these four fields say the same. Both no-marker sentences live in `protocol.md` § **Worktree work-package mechanics** (`:580` dotted IDs, `:608` the `Repo` column), which is where this rule joins them. **A plan without them is a permanently valid shape, not a migration backlog** — a markdown table has no storage or index cost, so unlike a database expand-contract there is no forcing function to ever deprecate it, and this ADR states that rather than implying a future cleanup pass. **The banked trigger, stated once so the next author does not re-derive it:** the day a plan-format change is *not* additive — a column renamed, removed, or the table restructured — **that** is when a real version marker plus a migration step earns its keep, modelled on Terraform's `SchemaVersion` + one-step-at-a-time `StateUpgraders` chain. A second forward pointer: if a plan is ever parsed through a strict JSON-Schema path (`additionalProperties: false`), presence-checking stops being free and the bump is required at that point. | this ADR; the rule restated once in `protocol.md` § Worktree work-package mechanics, beside the two existing no-marker sentences (`:580`, `:608`) |

### E. Bundle amendments, provisioning, and wiring

| ID | Contract | Home |
|---|---|---|
| **C-916** | **Sole definition sites, and the site table — eight shipped sentences become false, one live lock is amended, and the rest are deliberately not touched.** All canonical text lands in `protocol.md` under **existing** headers: § Verification (C-902, C-903, C-906), § Worktree work-package mechanics (C-901's amended sentence, C-904, C-913's playbook half), § The Review-Fix Loop (C-907–C-909, C-911), § Parallel-by-default decomposition (C-905's assignment, C-912, C-913's cascade half). **No tier file gains a rule**; per `DESIGN.md` round 10, a site either links or takes a one-clause qualifier, and **a site whose sentence stays true is not touched at all** — a qualifier on a true sentence is drift. **Three of the four glossary sites** are the worked example: `hex-review/SKILL.md:268`, `hex-architect/SKILL.md:392` and `hex-execute/SKILL.md:342` each define *"Verify" means run the project's documented verification* — which stays true there, because the merge gate now names a **different** check ("scoped check"), rather than redefining this one. **`hex-plan/SKILL.md:225` is the exception**: delta 2 puts a column literally named `verify`, whose `scoped` value is *not* the documented verification, inside that sentence's "anywhere below" scope, so it takes a one-clause qualifier rather than staying untouched. **The one site that is neither a link nor a qualifier is `DESIGN.md`'s *Plan visualization* column lock**, which is amended in place as a constitutional act (§ Constitution deviations), not treated as historical text. Site table below. | `protocol.md` (sole source); the sites below |
| **C-917** | **`hex-init` gains one audit item and two Pointers rows — including the sensitive-path source no shipped file has ever named.** A new top-level item, **"Selective test command documented?"**, in the standard four-part shape. *Look for:* a command that runs the tests affected by a change. *Where:* project context and checked-in files only — no network read, so `audit.md`'s "nothing here reaches the network" stays true verbatim. *Documented looks like:* a runnable template with its placeholders — `nx affected -t test --base={base}`, `pytest --testmon`, `npx jest --findRelatedTests {files}` — not "we use Nx". *De-facto discovery:* `nx.json`, `turbo.json`, a `.testmondata` in `.gitignore`, an `affected`-shaped CI job. A found command is proposed for **adoption via pointer**, never invented. **The item records nothing about the tool's own fallback behaviour** — C-906's post-failure fallback needs no such claim, so there is no self-degrade flag to record, get wrong, or default. **Two `hex.md › Pointers` rows**, both following the Spec-home pattern: **where the selective-test command is documented**, and **where the project's security-sensitive / hot-path convention is documented** — the second establishes the source C-903 clause (1) reads, which no shipped file has ever named despite the Review-budget heuristic assuming it; recording it is offered with consent, and its absence leaves clause (1) vacuous rather than broken. The `## Pointers` enumeration in `memory.md` gains both (C-916's site table). | `hex-init/references/audit.md`; `hex-init/SKILL.md` Steps 1/2/5; `hex-core/references/memory.md` § the three sections |
| **C-918** | **Zero config *key* — and the carriers, named.** `config.md` is **not touched**: no new key, and the frozen v1 vocabulary of six (`adr_0003` C-223) stays frozen. Every new value has a carrier that costs no vocabulary: the **`Verify` column** and the **`Review` column** are plan-table cells; the **`Reviewed:` anchor** is a Status-block line; the **schedule log** is a plan section; the **selective-test command** is Layer-1 project context with a Pointers row; the **sensitive-path convention** is a Layer-1 project fact reached through a second Pointers row (C-917) — hex records where it lives, never what it says. `M = 3` is shipped text with no knob, following `adr_0009` C-825's posture that a single default does not reopen a closed key set. **The one thing that would need a key — a per-project `M` — is explicitly declined** (open question 3); if field evidence ever demands it, the carrier is Preferences prose, following `adr_0004`/`adr_0005`/`adr_0009`, never a seventh key. | (no edit — a stated non-change) |
| **C-919** | **Bundle wiring and release.** (a) `hex/publish.toml` bumps `version` to **`0.4.0`** — a minor bump: additive plan-artifact fields, one changed default policy, no member added, no breaking change, no `deprecated`, no `replaced-by`; (b) `hex/CHANGELOG.md` gains an `## [0.4.0]` section with `### Added` (the `Verify` column, the `Reviewed:` anchor, the schedule log, the selective-test convention, the stranded-WP report) and `### Changed` (the per-merge gate, the failure cascade's non-halting behaviour) — **the changed default is a `### Changed` entry, not an `### Added` one**, because a user upgrading gets it without editing a plan; (c) `hex/DESIGN.md` gains **round 12**; (d) `hex/README.md` gains one line in the execution flow stating that per-merge verification is scoped with periodic full backstops — the user-visible behaviour change; (e) the `hex-core` amendments of C-901–C-913, **`memory.md`'s `## Pointers` row gaining C-917's two entries**, and the plan-template amendments of C-905, C-907 and C-912 (including retiring `## Progress Log`). No `hex.toml` / `grimoire.toml` change: no member is added. | `hex/publish.toml`; `hex/CHANGELOG.md`; `hex/DESIGN.md`; `hex/README.md`; `hex-core/references/memory.md` |

#### C-916's site table

Line numbers are **pre-`adr_0010` locations** — verified against the branch
base (`6d8bba0`) on 2026-08-30, before this ADR's own edits shifted them; the
anchoring sentence is quoted so each site stays identifiable in the shipped
tree without the pin.

| File · line | Statement | Becomes false? | Action |
|---|---|---|---|
| `protocol.md:542` | "Run the project's documented verification **after every merge**" | **yes** | **Canonical amendment** (C-901) — replaced in place, links to § Verification |
| `protocol.md:552-559` | merge-conflict / post-merge-failure playbook: "halt the wave, mark the WP `failed`… escalate" | **yes** | **Canonical amendment** (C-904 bisect-then-name-the-culprit, C-913 non-halting cascade) |
| `hex-execute/tier-medium.md:114` | "the project's documented verification runs after every merge" | **yes** | Rewritten as a **byte-identical pair** with `tier-high.md`: the **scoped check** becomes the sentence's subject and the full documented verification is named only on the triggers, + link to § Worktree work-package mechanics (where the trigger enumeration lives) |
| `hex-execute/tier-high.md:141` | "documented verification runs after every merge" | **yes** | Rewritten as a **byte-identical pair** with `tier-medium.md`: the **scoped check** becomes the sentence's subject and the full documented verification is named only on the triggers, + link to § Worktree work-package mechanics (where the trigger enumeration lives) |
| `hex-execute/SKILL.md:444` | "serialized in a valid topological order, verification after every merge" | **yes** | One-clause qualifier + link (the surrounding "Mechanics … never restated here" already points at `protocol.md`) |
| `hex-init/assets/templates/plan.md`, the `**Merge order:**` note | "with the project's documented verification after each merge onto the feature branch" | **yes** | Amended to name the scoped check + link |
| `hex-plan/SKILL.md:225`, `hex-review/SKILL.md` (the glossary sentence quoted opposite), `hex-architect/SKILL.md:392`, `hex-execute/SKILL.md:342` | *"Verify" anywhere below means run the project's documented verification* | **no — except at `hex-plan/SKILL.md:225`** | Untouched at three sites — still true there; the merge gate names a different check. `hex-plan/SKILL.md:225` takes a **one-clause qualifier**: delta 2 puts a column literally named `verify` inside the same file's "anywhere below" scope, and its `scoped` value is explicitly *not* the project's documented verification, so the glossary sentence needs bounding (C-905) |
| `protocol.md:202-206` | Implement phase: "verification for changed files"; leaf-under-coordinator compile-only carve-out | **no** | Untouched — this is not the merge gate |
| `workers/builder.md:13, :34, :43` | "run the project's documented verification for the changed files" | **no** | Untouched — Implement-phase, unchanged |
| `workers/coordinator.md:53, :68` | "funnel every sub-WP through the project's documented verification" at the join | **no** | Untouched — joins stay full, and this is the two-tier precedent C-901 generalizes |
| `hex-execute/tier-low.md:65, :80`; `tier-medium.md:78, :105`; `tier-high.md:93, :132` | Implement gates and final-state gates | **no** | Untouched — Implement gates and the final gate are unchanged |
| `hex-execute/SKILL.md:564` | "Every phase gates on the project's documented verification" | **no** | Untouched — phase gates are unchanged; the per-merge check is a step inside Phase 7 |
| `hex-init/assets/templates/plan.md:356` | Before-Merge checklist: "The project's documented verification passes" | **no** | Untouched — this is the final gate |
| `DESIGN.md:172, :184-190` | § Worktrees round-4 text: "verification after every merge"; the 2026-07-20 perf pass's Review-budget addendum | **historical round text** | **Not rewritten.** Round 12 supersedes by pointer, per round 11's convention; the `### Worktrees` region (`:144-200`) gains one erratum pointer and its bytes stay |
| `DESIGN.md:195-200` | "**Plan visualization (locked 2026-07-19)**", enumerating the WP table's canonical column set | **yes — a live lock, not historical text** | **Constitutional amendment, not an erratum.** The enumeration is amended by explicit act to admit `Verify`. Precedent: it has been amended twice in place (`status`, round 5; the review budget, the perf pass) and once as round 8's standalone addendum bullet (`Repo`, `adr_0004` C-302) that the base enumeration never absorbed — round 12 folds that outcome in alongside `Verify`. Recorded as round 12 amendment 3 with `adr_0004:1425`'s three-column deviation shape |
| `hex-plan/SKILL.md:271-272` | a second, independent enumeration of the WP table's columns, omitting `Repo` | **incomplete, not false** | **Additive** — gains `repo` and `verify`, so all four column enumerations list the same set: the plan template header, the `DESIGN.md` lock, this one, and `hex-execute/SKILL.md`'s free-text mini-table — which carries the same set minus the federation-only `Repo` (nine columns), since a free-text target is never federated |
| `memory.md:188` (`## Pointers` row) | the enumeration of what the Pointers cache holds | **incomplete, not false** | **Additive** — gains the selective-test-command home and the sensitive-path-convention home (C-917) |
| `protocol.md:406-434` | § Parallel-by-default decomposition, ready-set dispatch (`adr_0002` C-101) | **no** | **Additive only** — C-912's log and C-913's cascade are added to the section; the dispatch rule is not redesigned |
| `hex-execute/SKILL.md` § Schedule, the "Recompute the ready-set after every merge" step | "Recompute the ready-set after every merge" | **no** | **Additive** — gains the schedule-log write (C-912) |
| `hex-review/SKILL.md:92-107` | baseline resolution (`--base` > PR base > `main`) | **no** | **Additive** — one step inserted (C-910) |
| `hex-review/SKILL.md`, the **Review-only contract** paragraph and the **Constraints** bullet quoted opposite | the Review-only contract and the Constraints bullet: "its writes are the plan-artifact Status block, the append-only convergence rows, and — under the Fold-Back phase's four preconditions only — the one resolved spec file and the fold receipt" | **incomplete, not false** | **Additive** — the Status-block write set gains the `Reviewed:` anchor line (C-907, one-writer rule, branch scope only); nothing already enumerated stops being true |
| `hex-review/SKILL.md:282-285` | the verdict write: "on verdict, set `State` to `done` with `Next` cleared (Approve — or `State: landing`…)" | **yes** | One-clause qualifier + link — a run ending with a non-empty stranded set never reaches the terminal review state (`done`, or `landing` for a plan carrying a `Repo` column) under C-913(f); `adr_0005` C-410's exclusive ownership of that write is unchanged |

**UX scenarios.**

| ID | Scenario |
|---|---|
| **S-901** | A 12-WP plan, 6-minute suite, no `Verify` cells. Merges 1 and 2 pay the scoped check (WP contract tests + build, ~90s). Merge 3 trips the counter and runs the full suite. Merge 4 clears dependency level 1, so it runs full and **resets the counter** — merge 5 and 6 are scoped, not merge 5 alone. The schedule log shows `verify full(level-clear)` with merge 4's post-merge SHA, and the counter's next fire is at merge 7. |
| **S-902** | WP6's merge diff touches `src/auth/token.rs`, a path the project's documented sensitive-path convention names (the `hex.md › Pointers` row C-917 records). The high-risk trigger fires from the file list merge-time re-validation already computed — no extra command — and the full suite runs regardless of where the counter stood. |
| **S-903** | A checkpoint after merge 9 fails. One fix pass on the feature branch does not clear it, so the run **bisects the window** — WP7, WP8, WP9, whose post-merge SHAs the schedule log already recorded, with merge 6's SHA as the known-good base. Probe 1 at WP8's SHA: **fails**, so WP9 is exonerated and the culprit is WP7 or WP8. Probe 2 at WP7's SHA: passes, so WP8 is the culprit — **two extra full runs, the worst case at `M = 3`** (`⌈log₂ 3⌉`). WP8 is marked `failed`, the run **continues while any WP is eligible** (C-913(b)), and the end-of-run escalation names **the culprit, not the window** (C-904). Had probe 1 passed, WP9 would have been the culprit after **one** run — the best case, not the bound. Had neither probe reproduced the failure, the run would report *"failure did not bisect"* over the window and mark no WP `failed`. |
| **S-904** | The project documents `pytest --testmon` — a zero-placeholder template. hex runs it verbatim, substituting nothing, **on top of** the scoped check's build gate and the WP's own contract tests (C-902's floor). The first run pays the full suite to seed `.testmondata`, which is testmon's own documented behaviour and needs no special case (C-906). |
| **S-905** | The project documents `nx affected -t test --base={base}` and the checkout is shallow. The pre-flight guard (`git rev-parse --is-shallow-repository`) fires **before** the selective command runs, and hex runs the **full** documented verification instead, announcing the fallback — hex has no ref to substitute, which is a substitution failure rather than a judgment about Nx (C-906 (a)). |
| **S-906** | Review round 2 reads `Reviewed:..HEAD` plus the three files round 1's actionable findings named, in full. Round 3's actionable `Block`/`High` count is 3 against round 2's 3, and round 3 introduced no new `Block` or `High` — both clauses hold, so the loop **stops and escalates** with the outstanding list, before the tier's 3-round cap, using the cap's existing message shape (C-911). |
| **S-907** | `/hex-finalize` recomposed and force-pushed the branch yesterday; a later `/hex-review` finds a `Reviewed:` anchor whose SHA is no longer an ancestor of HEAD. The run **falls back to a full-branch review**, names the inert `backup/hex/foo-<sha>` ref as the reason in the announcement, and rewrites the anchor at the end. No halt, and no wrong-scope review (C-908). |
| **S-908** | WP2 fails after its one fix pass. WP5 and WP7 depend on it transitively; WP3, WP4 and WP6 do not. The run **keeps going** — the ready-set never offers WP5 or WP7, and the three independent WPs merge normally. At the end the run reports `WP2 — failed`, then `WP5 — blocked by WP2 (failed)` and `WP7 — blocked by WP5 (stranded) ← WP2 (failed)`, computed in one pass from the table's edges. WP5 and WP7 are still `pending`; **no fifth status exists**, and the plan does not reach `done` (C-913). |
| **S-909** | A plan authored before `adr_0010` — no `Verify` column, no `Reviewed:` line, no `## Schedule log` — executes on the new bundle. Each reader branches on presence: `scoped` merge gates, a full-branch first review, and the log section created on first write. No version field is read, no migration step runs, and the plan is never rewritten to add the fields (C-915). |
| **S-910** | A coordinator owns WP3 with sub-WPs WP3.1–WP3.3. The three sub-WPs merge into the **coordinator's own shared worktree**, so none of them runs a scoped check against the feature branch and **none increments C-903's counter** — the subtree's single full verification is the join. When WP3 itself merges onto the feature branch, **that merge runs the full documented verification because WP3 is coordinator-owned** (C-901 trigger (i)) and appends the subtree's one log entry, `verify full(join)` with WP3's post-merge SHA, which resets the counter. The dotted rows stay ordinary rows in the one Parallelization table; there is no per-coordinator log and no nested state file (C-901, C-902, C-912, C-914). |

## Non-Functional Requirements

Only affected axes; silence means not affected.

| Axis | Impact of this decision |
|---|---|
| Latency | **The point of the change, and the honest band is 29–46% of merge-gate wall-clock on a 12-WP plan**, with a 62% ceiling as `S/F → 0` — see § The arithmetic. **Two sensitivities govern it**: `S/F` (a build-dominated project saves proportionally less) and **plan shape** — a fully linear plan clears a dependency level on every merge and saves **zero**, so the win scales with the plan's average level width. Review-side: a wash at `R = 1`, a **net loss at `R = 2`**, about a third at `R = 3` only as `δ → 0`; the real win is across repeated `/hex-review` invocations on a long-lived branch, bounded at roughly one full read per invocation (D-1). |
| Cost | Token cost tracks latency: fewer full verification runs and smaller review diffs. No new spawns, no new role, no new research phase — C-914 adds no worker and C-919 adds no member. The always-on cost is **zero new always-on surface**: no rule-file line, no new skill description, no `config.md` key. |
| Correctness / reliability | **The residual is stated, not mitigated away.** Scoped checks accept that a regression can hide for up to `M−1` merges, or longer if a project's selective command under-selects; the bisection radius is bounded by C-903's cadence and resolved to a culprit by C-904's bounded bisection. A **flaky** failure is indistinguishable from a real one in v1 and is a stated accepted limit (§ Consequences). Delta review accepts the non-determinism and semantic-conflict classes, absorbed by C-909's mandatory converged-gate pass. The **final gate is unchanged, mandatory and un-lowerable** — every backstop this design leans on already existed. |
| Operability | Four new operational objects, all in the plan artifact: the `Verify` column, the optional `Verify-default:` line, the `Reviewed:` line, and the `## Schedule log` (which retires the unwired `## Progress Log`). **No new state file, at any depth** (C-914). The genuinely new thing an operator must learn is the schedule-log line grammar, which is one line and carries the five facts a stuck or slow run needs: what became ready, what stayed blocked, which check was paid, at which SHA, and how long it took — the SHA being what makes C-904's bisection free. The stranded-WP report is computed eagerly in one pass rather than propagated per node, which is what keeps hex out of the bug class GitLab, Airflow, Bazel and Argo have each shipped. |
| Security | **One boundary, small but real — not "none".** The selective-test command is an **opaque shell template hex executes**, so it is fixed as **authoritative-class only** (project context or `hex.md › Pointers`, never `CONTRIBUTING.md`, a PR body, or any narrowing- or untrusted-class surface), because it selects what code runs — the same class rule `adr_0009` C-815 applies to the workflow list, for the same reason. `{files}` is **shell-quoted** at substitution; hex substitutes textually and interprets nothing. No credential is read, no network call is made, and `hex-init`'s "nothing here reaches the network" stays true verbatim (C-917). Nothing else in this ADR touches a trust boundary. |
| Scalability | Improved along the axis that mattered: the serial merge-verify floor was `O(N)` full suites and becomes `O(N/M)` plus joins and overrides. Concurrency is unchanged — the cap is untouched, dispatch is not redesigned, and **no recursion level is added** (C-914). |
| Compatibility | **Purely additive at the artifact level** (C-915): four optional fields, each with a defined absent-default, no version marker, and no migration step. **One behaviour default changes** — the per-merge gate — and it changes for old plans too, on the stated ground that hex plans are re-read fresh by a centrally-upgraded interpreter, exactly as `adr_0002`'s ready-set dispatch changed launch timing for every plan without a column. `config.md` untouched (C-918); `adr_0005`'s fold path untouched; `adr_0004`'s federation contracts untouched — the per-repo verification rule (C-321) and global merge serialization (C-306) both apply to the scoped check unchanged — C-306 is not relaxed here, and § Considered Options records why. |

## Constitution deviations

`hex/DESIGN.md` is binding. This decision adds **one dated round with three
amendments** — two superseding § Worktrees positions by pointer, and **one
amending the live *Plan visualization* column lock in place** — makes **one
`protocol.md` playbook amendment** (C-904/C-913, recorded inside amendment 1
because round 4 owns the sentence it derives from), and **retro-claims one
unowned contract surface** (C-905's `Review` column). Following `adr_0005`'s
deferred finding D-5, each justification is stated as *which simpler route was
rejected and why*.

**The one deviation from a live lock, in `adr_0004`'s three-column shape:**

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **`DESIGN.md:195-200`** — "**Plan visualization (locked 2026-07-19)**", which enumerates the WP table's canonical column set (id, scope, expected files, size, wave, depends-on, plus status since round 5 and the review budget since the perf pass (C-905); `Repo` lives in round 8's standalone addendum bullet, never folded into this enumeration). C-905 adds a **`Verify`** column immediately after `Review`, plus an optional table-wide `Verify-default:` Status line. | The lock's stated intent is that the plan "stays fully actionable from the table alone". Under C-901 the merge gate is **per-WP**, so a table without `Verify` cannot say which check a given merge will run — the plan stops being sufficient on its own, and the lock's intent is broken by honouring its letter. This is the fourth amendment to the same enumeration by explicit act — twice in place (`status`, the review budget) and once as round 8's standalone addendum bullet (`Repo`, `adr_0004` C-302), which round 12 folds into the base text — not a new class of change. | Encoding the raise in `Scope` prose was rejected for the reason `adr_0004` rejected encoding `Repo` in `Expected Files`: it makes a mechanical value a substring to be parsed out of free text, and it cannot be inherited by sub-WP rows the way a column is. Inferring it entirely from C-903's merge-time high-risk predicate was rejected because the predicate sees only paths — it cannot see the author-judgment cases (a changed default, a schema, a config value nothing textually references) that are the column's whole reason to exist. A second lookup table below the plan was rejected as a second place to keep in sync, the drift `DESIGN.md:36` exists to prevent. The mermaid index is unaffected and a plan without the column renders exactly as today. |

### DESIGN.md amendment round — 2026-08-30, round 12

Proposed text, to be appended to `hex/DESIGN.md` (implementation is
downstream; this ADR does not edit the file):

> ## Execution-performance round (2026-08-30, round 12)
>
> `adr_0010` (scoped per-merge verification, checkpointed backstops,
> delta-scoped review rounds, and the failure cascade) amends **three
> positions in § Worktrees** — two from round 4 and its 2026-07-20 perf pass,
> and one from the *Plan visualization* lock. The first two supersede by
> pointer: their text is left as written and the `### Worktrees` region gains
> one erratum pointer, per round 11's convention. The third is a live lock
> and is amended in place — its enumeration has been amended twice in place
> before (`status`, round 5; the review budget, the 2026-07-20 perf pass) and
> once by round 8's standalone addendum bullet (`Repo`, C-302), which this
> round folds into the base text. Full adjudication and the two scored
> five-option comparisons: `adr_0010` § Considered Options.
>
> 1. **"Verification after every merge" becomes "a scoped check after every
>    merge, with full verification on three policy triggers plus two override
>    paths."** The round-4 rule above — "merge back onto the feature
>    branch, serialized, in a valid topological order **with verification
>    after every merge**" (§ Worktrees, emphasis added) — made the tree
>    provably good after each merge, and the reason it gave remains
>    correct: cross-file interactions surface only post-merge. **The
>    amendment keeps that reason and bounds its cost rather than discarding
>    it.** A full verification still runs — on **three policy triggers** (a
>    coordinator join, a checkpoint, the final gate) and on **two override
>    paths** (a `Verify: full` cell or `Verify-default: full` line; a
>    degrade when no assembly gate or no runner-addressable test set can be
>    resolved) — and the **final gate is unchanged, mandatory, and
>    un-lowerable by any per-WP budget**. What changes is the ordinary
>    merge, which pays the WP's own contract tests plus the project's
>    cheapest assembly gate. The cadence is a **dual
>    trigger with a risk override** — `M = 3` merges since any full
>    verification, or a cleared dependency level, or a high-risk merge,
>    whichever fires first, each firing resetting the counter — because the
>    checkpoint literature's own 2024 survey reports Young/Daly does not
>    transfer to DAG-of-tasks workloads, and because every production
>    checkpoint policy surveyed (Postgres, CI tiering) is a dual trigger
>    rather than a computed optimum. Rejected alternative: **relaxing the
>    verify/merge coupling instead** — overlapping a merge's verification with
>    the next merge's launch. It scores **within six points on a 102-point
>    scale, close enough that the arithmetic does not carry the choice**, and
>    preserves the correctness property this amendment trades. Its apparent
>    licence is C-306's own text in `protocol.md` § Worktree
>    work-package mechanics (from `adr_0004`), which calls global
>    one-at-a-time "an operability choice … the first rule to relax if
>    merge wall-clock ever dominates" — but **that sentence is
>    federation-scoped** and governs the cross-repo order, not the
>    single-repo coupling the same section's serialized-merge rule states
>    ("each merge changes the base under the next"), which is grounded in
>    correctness and carries no such invitation. It loses on bundle surface
>    and legibility: an overlapped verification reports against a tree that
>    no longer exists, the merge-failure playbook grows a concurrency
>    story, and resume must reconstruct which verification was in flight.
>    **C-306's lever is therefore not spent — it is explicitly left
>    available** for the federated case it actually governs, and is the
>    right next move if scoped checks land and cross-repo merge wall-clock
>    still dominates. Also rejected: **selective checks with only the final
>    gate as backstop**, which is the premortem seat's named failure mode
>    made policy and has no production precedent in the survey. **The sole
>    definition site is `protocol.md` § Verification**; § Worktree
>    work-package mechanics carries the amended sentence and links there,
>    six further sites take a one-clause qualifier or an amended sentence,
>    and **every site whose sentence stays true is untouched** — including
>    three of the four glossary sites, because the merge gate now names a
>    *different* check rather than redefining "Verify". The fourth,
>    `hex-plan/SKILL.md:225`, takes a one-clause qualifier because that
>    same file now carries a column literally named `verify`.
>
> 2. **The 2026-07-20 Review-budget addendum becomes a two-member family with
>    a stated direction rule, and its unowned contract surface is claimed.**
>    That perf pass added "a per-WP Review budget (`self | light |
>    panel`, lower-only vs the tier baseline, missing = panel)" and shipped it
>    with **no contract ID at all** — pre-`adr_0003` debt. `adr_0010`
>    **retro-claims it under C-905 with its semantics unchanged in every
>    byte**, and adds a sibling: **`Verify` (`scoped | full`, raise-only,
>    missing = `scoped`)**. The rule underneath both is stated here rather than
>    left implicit: **a budget column moves a WP away from the shipped default
>    in exactly one direction, fixed per column and stated in shipped text, and
>    each column's baseline sits at the unsafe end of its own range so the
>    unsafe direction is unreachable** — `Review`'s baseline is the full panel,
>    so only down exists; `Verify`'s baseline is the scoped check, so only up
>    exists. Rejected alternative: **leaving the `Review` column unowned and
>    numbering only `Verify`** would have shipped two columns governed by one
>    unwritten rule, with one of them still unciteable — the exact condition
>    that let the direction rule stay implicit for a year. Also rejected: **a
>    `config.md` key for either column.** The v1 vocabulary froze at six
>    (C-223); both columns are **plan-artifact cells**, so the freeze is not
>    reopened, and `M = 3` ships as text with no knob for the same reason.
>
> 3. **The *Plan visualization* lock's column enumeration admits a fourth
>    amendment: `Verify`.** "Plan visualization (locked 2026-07-19)" fixes the
>    WP table's canonical column set, and it is a **live lock, not historical
>    round text** — which is why this is an amendment in place rather than a
>    supersede-by-pointer. It has been amended by explicit act three times
>    already — twice in place (`status`, round 5; the review budget, the
>    2026-07-20 perf pass) and once as round 8's standalone addendum bullet
>    (`Repo` in second position, `adr_0004` C-302, whose deviation row is the
>    shape this one follows); this round folds that addendum's outcome into
>    the base enumeration, which had never absorbed it, alongside `Verify`.
>    `adr_0010` adds **`Verify`, immediately after `Review`**, keeping the
>    two budget columns adjacent. The lock's stated intent is that the plan
>    "stays fully actionable from the table alone", and that intent is what
>    forces the column rather than tolerating it: under amendment 1 the
>    merge gate is per-WP, so a table without `Verify` cannot say what
>    check a given merge will run, and the plan stops being sufficient on
>    its own. Rejected alternative: **encoding
>    the raise inside `Scope` prose, or inferring it entirely from C-903's
>    merge-time high-risk predicate.** Prose makes a mechanical value a
>    substring to be parsed and cannot be inherited by sub-WP rows the way a
>    column is — the same objection `adr_0004` raised against encoding `Repo`
>    in `Expected Files`. Inference alone drops the author-judgment cases the
>    predicate cannot see (a changed default, a schema, a config value nothing
>    textually references), which is the column's entire reason to exist. The
>    optional **`Verify-default:` Status line** rides the same amendment: it
>    is a table-wide default, not a fourth column, and the mermaid index is
>    unaffected. **A plan without either renders and reads exactly as today.**
>
> **Considered and not deviated** (unchanged by this round): the **single
> approval gate** — its count and its position are untouched; a checkpoint
> is a *check*, never a gate, and asks nothing. The **depth-1 coordinator
> invariant** is not merely untouched but **reaffirmed as a hard
> requirement** (`adr_0010` C-914): no recursion ≥ 2, no new orchestrator
> role, and state stays the one flat Parallelization table with computed
> rollups — the new schedule log is held to it explicitly, one section per
> plan and never one per coordinator. **Capability classes** — vacuously
> upheld: this round adds no spawn, no role and no `models.md` row, and no
> shipped file it touches names a literal model or a harness tool. **`hex
> never pushes` / `hex never commits` outside execution** — untouched;
> round 10's scoping stands as written. **The two-layer knowledge model**
> is upheld: the selective-test command is Layer-1 project context with a
> `hex.md › Pointers` row (it is "how to verify", the model's own worked
> example), and the sensitive-path convention is a Layer-1 project fact
> reached through a `hex.md › Pointers` row — hex authors neither as its
> own config, and C-917 records where each lives rather than what either
> says. **`adr_0005`'s fold path** is untouched: `hex-review` still writes
> only the Status block, the convergence check, and — on an approved
> converged fold — the spec file and receipt; C-401 and C-412 are unchanged
> and C-410's exclusive ownership of the terminal review state — `done`, or
> `landing` for a plan carrying a `Repo` column — gains one precondition (a
> run with stranded WPs does not reach it) rather than a second writer.
> **`adr_0004`'s federation contracts** are unchanged: per-repo
> verification (C-321) and global merge serialization (C-306) both apply to
> the scoped check verbatim. **Thin dispatchers + per-tier phase files** —
> no tier file gains a rule; two take a one-clause qualifier and the rest
> are untouched. **`config.md` gains no key** and its `<skill>` enumeration
> is not reopened.

### The `protocol.md` playbook amendment

The merge-conflict / post-merge-failure playbook's "halt the wave … escalate
to the user" is amended twice — C-904's bisect-then-name-the-culprit variant
and C-913's non-halting cascade. Both derive from round 4's own merge
mechanics rather than from an independent constitutional position, so they are
recorded inside round 12's amendment 1 rather than as a fourth deviation. The
simpler route rejected: **leaving the playbook alone and letting a `failed` WP
halt the run** would have made decision 5 unimplementable — independent
siblings cannot keep flowing through a halt — and would have left a checkpoint
failure blaming whichever WP merged last, which is a guess the four-status
column then presents as fact.

## Migration / rollout plan

**Every change is additive at the artifact level and no migration step
exists.** There is no plan rewriter, no `--upgrade` flag, and no version
comparison anywhere in the design (C-915).

**What an existing plan does on the new bundle.** It executes. Absent `Verify`
column and `Verify-default:` ⇒ scoped merge gates; absent `Reviewed:` ⇒ a
full-branch first review; absent `## Schedule log` ⇒ the section is created on
the first merge. The one behaviour a user notices without editing anything is
the merge gate, which is why C-919 files it under `### Changed` rather than
`### Added`. **On carrying a behaviour change in a minor bump:** hex is
pre-1.0 and publishes no compatibility policy, so `0.4.0` is a judgement, not
a rule being followed. The nearest in-house precedent is `adr_0006`, which
changed how findings gate a verdict inside a minor release and announced it in
the changelog — cited as an **analogy**, since no documented policy exists to
cite. The mitigations are the changelog callout and the per-plan escape below,
not a version number.

**Edit-site classes, in dependency order.** The classes are file-disjoint
except where noted, which is what makes them decomposable:

1. **`protocol.md` canonical text** — § Verification (scoped check,
   checkpoints, selective-test convention), § Worktree work-package mechanics
   (merge gate, playbook bisection variant, cascade), § The Review-Fix Loop
   (anchor, delta scope, converged pass, diminishing-returns stop),
   § Parallel-by-default decomposition (`Verify` assignment, schedule log,
   cascade, the no-marker sentence). **One file, four sections; it is the
   critical path and everything else links to it.**
2. **Plan template** — Status block `Reviewed:` line, Parallelization table
   `Verify` column + comment, the amended merge-order sentence, the new
   `## Schedule log` section with its grammar comment.
3. **Qualifier sites (five)** — the `tier-medium.md`/`tier-high.md` pair, the
   `hex-execute/SKILL.md` merge clause, the plan template's `**Merge order:**`
   note, plus `hex-execute/SKILL.md`'s "Recompute the ready-set after every
   merge" step and its additive schedule-log write.
4. **`hex-review/SKILL.md`** — one baseline-resolution step (C-910).
5. **`hex-init` + `memory.md`** — one audit item, and two `## Pointers` rows
   added to both the audit item and `memory.md:188`'s enumeration (C-917).
6. **`DESIGN.md`** — round 12 appended; the `### Worktrees` region
   (`:144-200`) gains one erratum pointer with its bytes unchanged, and the
   *Plan visualization* lock (`:195-200`) is **amended in place** to admit
   `Verify` — the one edit in this class that is not append-only.
7. **Release** — `publish.toml` `0.4.0`, `CHANGELOG.md` `## [0.4.0]`,
   `README.md` one line.

**One class-3 note for the implementing plan:** this repo dogfoods its own
bundle, so the installed copies under `.claude/skills/hex-*` go stale the
moment these edits land. Refreshing them is a **separate chore commit** after
the merge, not part of any WP — mixing a bundle edit with its own reinstall in
one WP makes the diff unreadable and the file-set check meaningless.

**Rollback, at two grains.** *The bundle:* every change is a markdown edit on a
feature branch, reverted by discarding it, and a plan authored with the new
fields still parses under the old bundle, which ignores unknown columns and
Status-block lines. No state is written that outlives a plan. *One plan, under
the new bundle:* the escape is **one line** — `- Verify-default: full` in the
Status block (C-905) restores pre-`adr_0010` merge gates for that plan.
Without it, "put it back" would mean editing a `Verify` cell per row — thirty
edits on a thirty-WP plan — which is why the default line exists rather than
the column alone. There is nothing to un-migrate at either grain.

## Validation

Re-derived after the fix pass, per the house norm from `adr_0008`'s RCA.

**Static, before execution.**

- `grim build <skill-dir>` for every changed skill; `task publish -- --dry-run`
  for the full sweep.
- **Contract coverage:** every `C-9xx` maps to at least one WP and one test in
  the implementing plan; every `S-9xx` maps to at least one WP. **C-914 and
  C-918 are exempt from both halves** — they are stated non-changes whose whole
  content is that no file is edited, so a WP or a test for either would be a
  WP that edits nothing. Their check is the negative one below (`config.md`
  diff empty; no new state file, no new role) and they carry it explicitly
  rather than being silently skipped.
- **Site-table check:** for each row marked "no", the quoted sentence is still
  literally true after the amendment. For each row marked "yes", the sentence
  no longer appears unqualified anywhere in the bundle. **Two greps, because
  the sentence has two spellings, and both are counted wrap-tolerantly** —
  `grep -Pzo '(?i)after\s+every\s+merge' <file> | tr -cd '\0' | wc -c` (and
  the same with `each`) per changed file, because a hard wrap splits an
  occurrence a single-line `grep -rn` never sees: the single-line count is a
  floor, the wrap-tolerant count is the authority, and a gap between them
  locates a wrapped hit rather than excusing one.
  - `grep -rn "after every merge" hex/` — **zero `protocol.md` hits**, because
    C-901's replacement sentence reads *after each WP merge onto the feature
    branch*, so neither spelling survives in that file. **Pinned by phrase,
    not by line, because this ADR's own diff shifts every one of them.** The
    allowed set is the two qualified tier lines (`tier-medium.md` and
    `tier-high.md`, byte-identical, each reading *"a **scoped check** runs
    after every merge"*), `hex-execute/SKILL.md`'s qualified *"verification
    after every merge — a **scoped check** except on the triggers"* line,
    **`hex-execute/SKILL.md`'s *"Recompute the ready-set after every merge"*,
    which is about dispatch, not verification, so it is a
    correct hit that must stay**, `hex/CHANGELOG.md`'s `0.4.0` Notes clause,
    whose *"the project's full documented verification after every merge"* is
    qualified as what `Verify-default: full` restores,
    `DESIGN.md:172`'s historical round-4 text,
    and **every occurrence round 12 introduces into `DESIGN.md`, wherever in
    the file it lands** — the three round-12 quotations inside the round's own
    section, *plus the `### Worktrees` erratum pointer's quoted "verification
    after every merge"*, which sits in § Worktrees rather than in the round.
    `DESIGN.md`'s wrap-tolerant total is therefore **five**: `:172`, three in
    round 12, and the erratum pointer's one.
  - `grep -rn "after each merge" hex/` — **zero `protocol.md` hits**, for the
    same reason. The allowed set is the plan template's amended
    `**Merge order:**` note **only if its
    rewritten wording still carries the phrase** — it is amended to name the
    scoped check and point at § Worktree work-package mechanics, and either
    outcome is allowed —
    plus round 12's own prose sentence, which says round 4's rule "made the
    tree provably good after each merge" and which this ADR requires round 12
    to write. Any other unqualified occurrence in shipped contract text fails.
- **Single-source check:** `grep -rn "scoped check" hex/` shows exactly one
  defining occurrence (in `protocol.md` § Verification); every other hit is a
  link or a one-clause qualifier. Mechanically:
  `grep -c 'A scoped check is' hex/hex-core/references/protocol.md` = **1**.
- **C-913 terminal-state qualifier landed:**
  `grep -c 'stranded-WP set never reaches its terminal review state' hex/hex-core/references/archive.md`
  = **1** — phrase-pinned, never line-pinned.
- **No new key:** `git diff hex/hex-core/references/config.md` is empty.
- **No literal model name** in any changed shipped file.
- **Range check:** `C-901`–`C-919` and `S-901`–`S-910` are contiguous and
  collide with nothing.

**Dogfood on a multi-WP plan** — the five checks the dossier named, each now
readable off an artifact rather than a transcript:

1. **Ready-set timing** — a dependency-ready WP launches before its level
   completes: the `## Schedule log`'s `ready:` field widens at a merge that
   did not clear a dependency level.
2. **Full-run count** — **partition** the schedule log's `full(<trigger>)`
   entries **by tag**. The partition is disjoint by construction: coincident
   triggers write **one** entry, tagged with the **first matching token**
   (C-912), so every full entry falls in exactly one class. That same
   coincidence rule is why this is a **bound, not an equation** — a merge that
   is a coordinator join *and* trips the counter spends one full run and
   writes one `join` entry, so a per-class `==` would be false on a correct
   run. Two halves, both required:
   - **Each class is bounded above by its structural expectation** — `join` ≤
     coordinator-owned WP merges; `column` ≤ `Verify: full` cells plus, where
     `Verify-default: full` is set, the merges inheriting it; `degrade` ≤ the
     degrade events the run logged — C-902's two halves can both degrade at
     one merge, which is two events and one entry (C-902/C-906); `counter`, `level-clear`
     and `high-risk` ≤ the trigger opportunities the plan's shape and merge
     order make derivable (C-903).
   - **Every structural full-verify obligation is covered by some full
     entry** — a merge that satisfies several obligations covers all of them
     with its one entry. An **uncovered** obligation is the failure this
     check exists to catch; a class count below its bound is coincidence, not
     drift.
   Every remaining merge carries a `scoped` entry, and the final gate is
   outside this count entirely — it is not a merge and writes no entry
   (C-901). **This is
   the primary acceptance check for decision 1**, and a run whose `full(…)`
   entries are dominated by `degrade` is the signal that C-902's discovery
   failed rather than that the policy did not work.
3. **Delta review** — round N's announced scope is `anchor..HEAD` plus
   finding-adjacent files; the converged gate's scope is the full branch.
4. **Failure cascade** — a deliberately failed WP leaves independent siblings
   completing, and the run ends with the stranded list naming direct blockers.
   No WP carries a status outside the four.
5. **Wall-clock** — total run time against a pre-change baseline run,
   **measured externally** (the run's own start and end), reported alongside
   the measured `S/F` ratio **and the plan's level count `k`**, because the
   headline number is meaningless without both sensitivities. The schedule
   log's per-merge `<elapsed>` is corroboration, not the measurement: it is
   best-effort and optional (C-912), so nothing here gates on it.

**Anchor fail-safe, forced.** Run `/hex-finalize` on a branch carrying a
`Reviewed:` anchor, then invoke `/hex-review`: it must announce the fallback
to a full-branch review and name the inert backup ref as the reason — never
review a partial range, and never halt.

## Open Questions

Hard cap 3, each with a recommendation. A plain approval at the meta-plan gate
accepts all three.

- **[NEEDS CLARIFICATION: which phase actually burned the wall-clock in the
  observed slow runs — serialized merge-verify, review rounds, or ready-set
  non-compliance?]** *Recommended:* carried from the dossier because it needs
  evidence this ADR cannot manufacture, but **half of it is resolved by
  design**: C-912's schedule-log line carries `verify <scoped|full(trigger)>`,
  a best-effort `<elapsed>`, and `ready:`/`blocked:`, so merge-verify cost and
  ready-set compliance both fall out of the committed artifact on the first
  dogfood run. What remains is review-round attribution. Capture one slow-run
  transcript during the dogfood, and diff the installed hex copies in the
  affected larger repos first — arcana's were verified in sync 2026-08-30, and
  an older install would still barrier regardless of anything here.
- **[NEEDS CLARIFICATION: should a scoped check also run the merged WP's
  *dependents'* contract tests?]** *Recommended:* **no for v1.** It is the
  cheapest available widening against the semantic-conflict class (D-2) and
  costs one static lookup over the plan's own edges. **The decline is on cost,
  not coverage**: at merge time a WP's dependents are usually unbuilt, so the
  only dependents with tests to run are already-merged ones — and running
  their suites on every merge walks back toward the full suite this ADR is
  removing. The residual is real and is stated in D-2: a dependent this merge
  broke goes undetected until the next checkpoint or the final gate. **What is
  *not* the reason is that the last checkpoint covered it** — that checkpoint
  verified the tree *before* this merge and says nothing about it. Revisit if
  dogfood shows checkpoint failures clustering on dependent WPs; the change is
  then one clause in C-902, not a design round.
- **[NEEDS CLARIFICATION: should `M` be project-tunable?]** *Recommended:*
  **no.** `M = 3` ships as text with no knob, per C-918 — a tunable `M` is the
  seventh `config.md` key `adr_0003` C-223 froze the vocabulary to prevent,
  and the dual trigger's other two conditions already adapt the cadence to the
  plan's own shape (a narrow plan checkpoints on level clears, a risky plan on
  the high-risk override) — which is also why a narrow plan cannot be tuned
  faster by lowering `M`. If field evidence ever shows a project's suite cost
  makes 3 wrong, the carrier is `hex.md › Preferences` prose, following
  `adr_0004`/`adr_0005`/`adr_0009` — never a key.

## Links

- Dossier (ratified decisions): [`.agents/discussions/hex-execution-performance.md`](../discussions/hex-execution-performance.md)
- Commissioned research: [`adr0010-compat.md`](../research/adr0010-compat.md) · [`adr0010-operability.md`](../research/adr0010-operability.md) · [`adr0010-tooling.md`](../research/adr0010-tooling.md)
- Discussion-phase research: [`discuss-exec-perf-priorart.md`](../research/discuss-exec-perf-priorart.md) · [`-community-reviewloops`](../research/discuss-exec-perf-community-reviewloops.md) · [`-community-orchestration`](../research/discuss-exec-perf-community-orchestration.md) · [`-community-testtime`](../research/discuss-exec-perf-community-testtime.md) · [`-adjacent-cidag`](../research/discuss-exec-perf-adjacent-cidag.md) · [`-adjacent-increview`](../research/discuss-exec-perf-adjacent-increview.md) · [`-adjacent-buildsystems`](../research/discuss-exec-perf-adjacent-buildsystems.md) · [`-competitive-products`](../research/discuss-exec-perf-competitive-products.md) · [`-competitive-sdd`](../research/discuss-exec-perf-competitive-sdd.md) · [`-competitive-swarm`](../research/discuss-exec-perf-competitive-swarm.md)
- Constitution: [`hex/DESIGN.md`](../../hex/DESIGN.md) — § Worktrees round-4 text and its 2026-07-20 perf pass (both superseded by pointer), the *Plan visualization* lock at `:195-200` (amended in place), round 10 (sole-definition-site pattern), round 11 (supersede-by-pointer convention)
- Predecessors this ADR depends on and does not disturb: `adr_0002` (C-101 ready-set, C-105 statuses and rollups), `adr_0003` (C-223 key freeze), `adr_0004` (C-302 column-lock amendment precedent, C-306 merge serialization — federation-scoped, cited not spent, C-316, C-321, C-324), `adr_0005` (C-401, C-410, C-412), `adr_0006` (C-502 severity ⊥ class, the floor C-911 counts on), `adr_0009` (C-807/C-808 non-SHA-stable recomposition, C-813 single-rerun ceiling, C-815 trust classes, C-819 sole-definition-site precedent)

## Changelog

| Date | Change |
|---|---|
| 2026-08-30 | Initial draft. `C-901`–`C-919`, `S-901`–`S-910`; DESIGN round 12 proposed with two amendments to round 4; `Review` column retro-claimed under C-905. |
| 2026-08-30 | Panel round-1 fix pass. Contract text amended in place, nothing renumbered. Corrected: the "three places and only three" overclaim (C-901 now names three policy triggers plus two override paths, matching C-912's log vocabulary); C-906's pre-flight self-degrade flag replaced by a post-failure fallback, shrinking C-917; C-306 reattributed to `protocol.md:665-667` and scoped to federation; the *Plan visualization* lock recognized as live and amended in place as round-12 amendment 3. Added: C-902's test-invocation convention and degrade, C-904's bounded bisection, C-905's `Verify-default:` line and column position, C-909's per-scope full pass and third miss class, C-911's severity floor, C-912's post-merge SHA. Arithmetic gained plan shape as a second sensitivity and the `R = 2` review regression. |
| 2026-08-30 | Cross-model adversary pass (7 actionable). Corrected: coordinator joins are now ordinary feature-branch merge entries — trigger `join` fires on a **coordinator-owned WP's merge**, so the log keeps one entry per merge and the validation equation closes (C-901, C-912, S-910); bisection bound corrected to `⌈log₂ M⌉` = **two** at `M = 3` and scoped to a non-empty attributed window, with empty-window and post-review-fix failures routed to ordinary RCA (C-904, S-903); the anchor check gained a **range** test beside the reachability test, closing a fail-open on a trunk or common-ancestor anchor (C-908); the selective-test command now **augments** the two-part scoped-check floor rather than replacing it (C-902, C-906); the hub predicate keys on `(Repo, path)` (C-903). **Supersedes the earlier S4 placement:** `Reviewed:` and `Verify-default:` sit after `Next:` and *before* the multi-row `Repos:` ledger, so both count inside the first 20 lines; the ledger's own overflow is recorded as a pre-existing template erratum (C-907). |
| 2026-08-30 | Erratum — the *Plan visualization* lock's amendment history was miscounted as three in-place amendments. Ground truth: the enumeration was amended in place **twice** (`status`, round 5; the review budget, the 2026-07-20 perf pass) and once by round 8's **standalone addendum bullet** (`Repo`, `adr_0004` C-302, `DESIGN.md:524-535`), which the base enumeration never absorbed. Corrected at all four sites that asserted otherwise — the Constitution-deviations row, round 12's preamble, round 12's amendment 3, and C-916's `DESIGN.md:195-200` site row. Round 12 folds `Repo` into the base text alongside `Verify`, so the shipped lock enumerates ten columns. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — one definition site C-916's table missed, and one home stated too narrowly. `hex-plan/SKILL.md:271-272` carries a **second independent column enumeration** that omits `Repo`; it gains `repo` and `verify`. C-917's home reads "`hex-init/SKILL.md` Step 1/2", but the Pointers rows are written in **Step 5** (Bootstrap), so the home widens to Steps 1/2/**5**; consent mechanics unchanged. The same delta also falsifies the glossary row's "stays true everywhere the word appears" ground at **`hex-plan/SKILL.md:225`** — a column literally named `verify`, whose `scoped` value is *not* the project's documented verification, now sits inside that sentence's "anywhere below" scope — so the glossary row carves `:225` out and the one-clause qualifier is landed there. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-916's site table missed two `hex-review/SKILL.md` sites this ADR's own contracts create, and both rows are added. The Review-only contract and its Constraints bullet (`:420-429`, `:433-437`) enumerate the write set and are **incomplete, not false**: the enumeration gains the `Reviewed:` anchor line (C-907). The verdict write at `:282-285` **becomes false** under C-913(f) and takes a one-clause qualifier plus link — a run ending with a non-empty stranded set never reaches `done`, and `adr_0005` C-410's exclusive ownership is unchanged. **C-916's headline count is re-derived with them**: "six shipped sentences become false" becomes **eight**, and the glossary worked example is qualified to three of the four sites — `hex-plan/SKILL.md:225` is the exception, since delta 2 puts a column literally named `verify` inside that sentence's "anywhere below" scope. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-907's placement justification was false against the shipped template. The claim that both new Status lines are counted inside the first 20 lines does not hold: the template's own comment block already puts `State:` at `plan.md:24` and the `Repos:` ledger runs to `:33`, so that invariant is unmet before this ADR adds anything. The line-budget ground and its `plan.md:18` citation are dropped; the surviving rationale is **ordering** — immediately after `Next:`, before the unbounded `Repos:` ledger — and the template's pre-existing overflow stays recorded as an erratum rather than fixed. **This row supersedes the cross-model-adversary-pass row at `:1076`**, whose closing clause records what that pass concluded at the time and is left byte-unchanged as history. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-912 named two homes for the schedule log: one clause placed the section below § Parallelization, another had it replace the plan template's `## Progress Log`. Reconciled to **one home** — it replaces `## Progress Log` in place (`plan.md:400`) — and the placement clause is dropped. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — § Validation's two allowed-hit lists re-derived. Both greps now state **zero `protocol.md` hits** (C-901's replacement sentence reads *after each WP merge onto the feature branch*, so neither spelling survives in that file); both enumerate their allowed set instead of deferring to one named file; the `after every merge` set admits **every occurrence round 12 introduces into `DESIGN.md`, wherever in the file it lands** — the three quotations inside the round plus the `### Worktrees` erratum pointer's quoted phrase, five wrap-tolerant hits in that file counting `:172`; the template's `**Merge order:**` note is conditional on whether its rewritten wording retains the phrase; and round 12's own "tree provably good after each merge" prose sentence is admitted. Both counts are **wrap-tolerant** — a hard wrap splits an occurrence a single-line `grep -rn` never sees, so the single-line count is a floor and the wrap-tolerant count is the authority. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-901's schedule-log-vocabulary claim was false. It read "All five appear in the schedule log's `<trigger>` vocabulary (C-912) as `join`, `counter`, `layer-clear`, `high-risk`, `column`, `degrade` — the three policy triggers, (ii) contributing three of its own." Only **four of the five** can appear: log entries are one per feature-branch merge, and the final gate (iii) is not a merge, so it produces no entry and has no `<trigger>` value at all. Corrected in C-901's cell. `protocol.md`'s **merge-gate text** carries the same semantics in its own phrasing and links C-912 as the vocabulary's owner rather than re-listing the six tokens (the sole-definition-site rule — the token list's one home is `protocol.md`'s schedule-log grammar line, C-912's own definition site, which does list them), so this row records the semantic correction — all-five to four-of-five, final gate logs nothing — not either file's exact bytes. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-913(f)'s stranded-set precondition was bound to plan State `done` alone, which a **federated plan never reaches**: under `adr_0004` C-324 its terminal review state is `landing`, so the precondition would not have held there. Widened at both ends — C-913(f) and C-916's `hex-review/SKILL.md:282-285` row now bind it to **the terminal review state: `done`, or `landing` for a plan carrying a `Repo` column** — and `archive.md`'s shipped qualifier is written to that binding. `adr_0005` C-410's exclusive ownership of the write is unchanged. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-909's interplay with the `Review` budget column was settled only in rationale prose (`:477-479`), never as an operative clause, leaving the shipped text to re-derive it. Promoted to shipped `protocol.md` text: a converging round that **already read the full scope** satisfies the mandatory converged pass rather than paying a second one, and a **`self` WP has no Review-Fix Loop and therefore no WP-level converged gate** — the branch-level `/hex-review` pass is its backstop. No contract substance changes; the rationale becomes the rule. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-904 clause (3) contradicted C-913(b). It read "The culprit WP is named, marked `failed`, and the run halts and escalates with **the culprit, not the window**", while C-913(b) removes exactly that barrier ("the run continues while any WP is eligible", escalating at the end). The halt is dropped: the culprit is named and marked `failed`, the cascade governs from there, and the end-of-run escalation names the culprit rather than the window. Shipped `protocol.md` carries the non-halting form. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — S-903 restated the same contradiction in the scenario table: "WP8 is marked `failed` and the run halts naming **the culprit, not the window** (C-904)". Corrected to the non-halting walk — WP8 is marked `failed`, the run continues while any WP is eligible (C-913(b)), and the end-of-run escalation names the culprit. The bisection arithmetic and the "failure did not bisect" branch are unchanged. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-909's anchored round 1 and the mandatory converged pass are jointly unsatisfiable at tier `low`. The 1-round cap leaves no round 2 to carry a pass that is "never delta-scoped, never skipped", while a valid anchor would have narrowed the only round there is. The tier-low arithmetic the ADR already runs for the unanchored case — the single round *is* that pass — is extended to the anchored one and **promoted to shipped `protocol.md` text**: at tier `low` a valid anchor never narrows round 1; that round reads the full scope and is itself the mandatory converged pass. C-909's cell carries the same clause. No contract substance changes; the anchor stays valid and is still rewritten at the end. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* — codex cross-model find |
| 2026-08-30 | Erratum — C-905's `Verify` cell stated the absent-cell default twice and disagreed with itself: "A missing column or cell means `scoped`" unconditionally, then the correct chain (cell > `Verify-default:` > `scoped`) two sentences later, which is what shipped `protocol.md` already carries. The first sentence is aligned to the chain — "means the plan's `Verify-default:`, else `scoped`". Cell prose only; no shipped file and no round-12 byte changes. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* — codex cross-model find |
| 2026-08-30 | Erratum — § Validation's dogfood check 2 ("Full-run count") was an equation that cannot close. It required `full(…)` entries to **equal** checkpoints + coordinator-owned WP merges + `Verify: full` cells + degrades, but C-912's coincidence rule writes **one** entry for a merge that trips several triggers, tagged with the first matching token — so on a correct run the equality is false, not the policy. Re-derived as a **tag partition** of the log's `full(<trigger>)` entries, disjoint by construction, checked in two halves: each tag class is bounded **above** by its structural expectation (`join` ≤ coordinator-owned WP merges; `column` ≤ `Verify: full` cells plus inherited `Verify-default: full`; `degrade` ≤ logged degrade events; `counter`/`level-clear`/`high-risk` ≤ derivable trigger opportunities), and every structural full-verify obligation must be **covered by some** full entry — one entry covers every obligation its merge satisfies. An uncovered obligation is the failure; a class below its bound is coincidence. The final gate stays outside the count: it is not a merge and writes no entry (C-901). *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* — codex cross-model find |
| 2026-08-30 | Erratum — the `after every merge` allowed set omitted `hex/CHANGELOG.md`. The `0.4.0` Notes clause spells the phrase in full — "the project's full documented verification after every merge" — as what `Verify-default: full` restores, and the grep's scope is `hex/`, so it is a **qualified hit that must be admitted**, not a failure. Added to the allowed set. Both allowed sets are also **re-pinned by phrase rather than by line**, because this ADR's own diff shifts every line it had cited. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — the schedule log's third trigger token read `layer-clear`, while § Checkpoints names the thing it fires on a **dependency level**. Renamed to `level-clear` for vocabulary parity at every live site: `protocol.md`'s grammar line, C-901's and C-912's cells, S-901's walk-through, and the arithmetic's `L` gloss. DESIGN round 12 carries no token, so there is no lockstep edit; the erratum row above that quotes the pre-rename C-901 sentence keeps its historical bytes. Vocabulary only — no semantics change. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-916's tier rows pointed the trigger link at the wrong section. The qualifier sentence says the section *names* the triggers, but the enumeration lives in **§ Worktree work-package mechanics**; § Verification defines the scoped check. Both tier rows retarget the link and now record that the pair is **rewritten byte-identically**, with the scoped check as the sentence's subject rather than a trailing qualifier hung on a false clause; the same retarget lands at `hex-execute/SKILL.md`'s qualifier and the plan template's `**Merge order:**` note, whose rows never quoted the anchor. The `hex-plan/SKILL.md:271-272` row also counted **three** column enumerations: `hex-execute/SKILL.md`'s free-text mini-table is a **fourth** and gains `Verify` — nine columns, the same set minus the federation-only `Repo`, since a free-text target is never federated. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
| 2026-08-30 | Erratum — C-916's site table pinned four rows by line number, and this ADR's own diff moved all of them: the `hex-review/SKILL.md` glossary sentence, the `hex-execute/SKILL.md` ready-set recompute step, the plan template's `**Merge order:**` note, and the `hex-review/SKILL.md` Review-only contract / Constraints pair. Converted to **quoted-phrase anchors** — the row's Statement column already carries the sentence, so the pin is redundant as well as fragile. The same conversion is applied to C-912's home cell, which named `hex-execute/SKILL.md:522` for the schedule-log write, and to § Migration's qualifier-site enumeration. The three glossary pins that did **not** drift (`hex-plan/SKILL.md:225`, `hex-architect/SKILL.md:392`, `hex-execute/SKILL.md:342`) are left as written — `:225` is cited by name elsewhere in this ADR. Locations only; no contract substance changes. *plan_adr_0010 discovery, 2026-08-30; Status: Accepted, unchanged* |
