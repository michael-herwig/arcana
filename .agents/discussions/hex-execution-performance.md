# Discussion: hex execution performance — true DAG dispatch, per-WP verification budgets, delta-scoped review

State: handed-off → architect · Updated: 2026-08-30
Ratified: 2026-08-30 → architect
Confidence: Michael ratified at the restate-gate; decisions backed by
research vintage 2026-08-30 (10 artifacts
`research/discuss-exec-perf-*.md`, expire 2027-02-28) plus a 3-seat
blind council (premortem · operability · simplicity, returned inline).

## Intent

Hex runs take far too long in practice. Four complaints (TODO.md: "wave
based execution", "meta/tiny-loop skill … smarter review loops"):

1. Plans declare a DAG but execution barriers in waves — a WP waits for
   its whole wave, not just its deps. Suspected: waves are encoded at
   plan time and hex-execute honors them.
2. No per-item/per-task verification budget — full test suite per loop
   round; 5–6 min suites in bigger repos make large plans take days.
3. Wanted: sub-orchestrators (possibly nested) running their own tiny
   implement→review→verify loop with bounded effort.
4. hex-review re-reviews the entire branch every round; wanted:
   delta-since-last-review scope + side-finding expansion, full-branch
   pass only at the final gate.

Outcome shape: ADR (drain → architect, next claims C-9xx). Goal is
performance; correctness backstops (final full verify/review) stay.

## Research

- `research/discuss-exec-perf-priorart.md` — entry wave, 4 axes
  (scheduling, verification scoping, review scoping, hierarchy).
- `research/discuss-exec-perf-community-reviewloops.md` — community
  lane: iterative AI review loops. Key: full-diff re-review per round
  is the reported default failure mode (Copilot re-flags same lines
  across rounds); CodeRabbit ships the exact incremental precedent
  (`review` = since-last-review, `full review` = from scratch);
  named **oscillation** failure (fix A introduces B, fix B
  reintroduces A) mitigated by iteration budget + convergence
  detection; review **non-determinism** on unchanged code undermines
  delta-only strategies that assume a stable baseline — a real
  counter to pure delta review.
- `research/discuss-exec-perf-community-orchestration.md` — community
  lane: orchestration latency. Key: practitioners name
  verification/review, not generation, as the dominant sink (4 min
  generate vs 55 min review cited); review/integration is the real
  serialization point, so capping concurrency beats scaling agent
  count; serialized pipelines sometimes a deliberate legibility
  trade; runaway loops compound cost. All single-practitioner
  anecdote, no controlled benchmarks.
- `research/discuss-exec-perf-adjacent-cidag.md` — adjacent lane: CI
  DAG vs stages. Key: DAG (`needs:`) exists precisely because stages
  are wave barriers; gains real but never isolated in benchmarks;
  **fail-fast defaults** — every DAG engine (GH Actions, Argo,
  Airflow) defaults to cascade-stop on mid-graph failure with
  per-edge opt-out, which staged execution gets for free. Hex's
  ready-set needs an explicit failure-cascade rule (WP `failed` →
  what happens to dependents) — currently unspecified territory for
  the ADR.
- `research/discuss-exec-perf-adjacent-increview.md` — adjacent lane:
  incremental review mechanics. Key: tools re-review full base→head
  because a reliable reviewed-commit delta is hard (GitHub's
  since-last-review anchor breaks on force-push — SHA-keyed, not
  content-keyed). Hex is better positioned: execution appends
  commits serially, no mid-run rewrite, so a last-reviewed-SHA
  anchor is stable (finalize's rewrite happens after convergence).
  Documented miss class: **semantic conflicts** — two independently
  correct changes combine broken with zero textual overlap; the
  documented backstop is CI/verification against the final tree, not
  a full re-review pass (no source mandates one).
- `research/discuss-exec-perf-community-testtime.md` — community
  lane: test time in agentic loops. Key: static path/graph selection
  has documented escapes (Jest alias blindness, Nx over/under
  detection); Fowler names the broken core assumption (unchanged
  code ⇒ still-passing tests fails under state/config/timing);
  Azure TIA's documented mitigation = full suite on protected
  branches. Tiered test sizes (Bazel small/medium/large with
  RAM+timeout budgets) is the reference pattern for effort classes.
- `research/discuss-exec-perf-adjacent-buildsystems.md` — adjacent
  lane: build-system scheduling + selection at scale. Key: Buck2
  removes phases by construction (single incremental graph); TAP =
  fast speculative cycles + periodic comprehensive cycles (85%
  recall at 25% budget, p50 detection 107→37 min); 84% of test
  transitions are flakiness — the dominant noise a selector must
  filter; Chromium's backstop is structural (mirrored post-submit
  CI), not a re-run policy.
- `research/discuss-exec-perf-competitive-products.md` — competitive
  lane: agent products. Key: Cursor Bugbot reviews **incremental by
  default** (full-PR is the opt-in) with a priced reasoning-effort
  knob; Copilot coding agent's only hard bound is wall-clock (59
  min); Cursor caps subagent nesting at **one level deep** — a
  concrete depth-1 data point; no vendor publishes a test-selection
  algorithm; OpenAI verifier research: most high-severity catches at
  a small fraction of generator token spend (precision over recall
  by design).
- `research/discuss-exec-perf-competitive-sdd.md` — competitive lane:
  SDD frameworks. Key: **no SDD tool runs the full test suite per
  task by default** — hex's verify-after-every-merge is stricter than
  the whole surveyed field; most tools are sequential (spec-kit's
  `[P]` tags advisory only); Spec Kitty (worktree lanes) does
  per-WP incremental review + one whole-change gate at the end —
  the same shape converging here; Tessl publishes the field's only
  numeric effort budget (~7 tasks/batch, fresh author≠verifier run
  once at the end).
- `research/discuss-exec-perf-competitive-swarm.md` — competitive
  lane: swarm orchestrators. Key: OSS Claude-Code swarms converge on
  topo-**waves** (parallel within, serial across) — the barrier hex's
  ready-set contract already surpasses on paper; only metaswarm
  claims true sub-orchestrator recursion (no depth data; per-unit
  implement→validate→adversarial-review→commit with a 3-iteration
  cap then human escalation); all effort budgets found are flat
  (dollar/tool-call caps) — **no project scales verification effort
  by task complexity**, so a per-WP verify budget is unclaimed
  territory.

Recon findings (2026-08-30, hex source read in full):

- **Ready-set dispatch is already contractual** — `protocol.md`
  § Parallel-by-default decomposition: waves are a derived reporting
  view, "never a launch gate"; a WP is eligible the instant its
  `Depends-on` are `merged`, ready-set recomputed per merge,
  critical-path-first. Complaint 1 is therefore runtime non-compliance
  (or stale installed copies in the *target* repo — arcana's verified
  in sync 2026-08-30), not a missing contract.
- **Structural serial floor**: merges are serialized one-at-a-time and
  the project's documented verification runs in full after EVERY merge
  (`protocol.md:539-543`) plus per-Implement. No test-selection
  concept exists anywhere in the bundle. With a 5–6 min suite and N
  WPs, that is a ≥ N×6 min serial floor regardless of dispatch — the
  likely real wall-clock culprit.
- **Per-WP effort knob exists only for review**: `Review` column
  `self|light|panel` (lowers breadth, never raises). Precedent to
  mirror for a `Verify` budget.
- **hex-review**: full diff vs baseline per invocation; no
  last-reviewed-SHA or delta mechanism anywhere; the review-fix loop
  shrinks *perspectives* between rounds, never the diff.
- **Prior art**: selective testing always pairs with a full-run
  backstop (Meta ~2× cost cut, >99.9% faulty-change catch; Chromium
  next-tier backstop); stage barriers are pure efficiency cost across
  every build system surveyed; delta review in Gerrit/GitHub/Graphite
  always keeps the full view one click away; hierarchy consensus
  depth 2 practical, deeper "usually indicates a problem".

## Council (2026-08-30, 3 seats: premortem · operability · simplicity)

Question: flat ready-set + per-WP verify budgets (A) vs recursive
sub-orchestrators (B) vs depth-1 hybrid (C).

- **Unanimous: reject B.** Multiplicative re-verification across
  levels, LLM over-decomposition as default tendency, unbounded
  resume/crash tree-walks; premortem: inverts the wall-clock goal on
  the very plans motivating it.
- Divergence A-vs-C: simplicity → A now, C only on a measured
  residual; operability → C with a hard requirement (state stays one
  flat table with computed rollups, never nested state files);
  premortem → C most tolerable, A fails via distant bisection when
  the single final gate fails 30 merges late.
- **Synthesis**: hex already ships depth-1 (`orchestrator →
  coordinator → leaf`, dotted WP rows, flat Parallelization table,
  coordinator runs the authoritative verification at the join — the
  two-tier verify precedent in-house). So the real decision is
  policy, not topology: scope per-merge checks, bound the bisection
  radius (checkpoint full-verifies, TAP comprehensive-cycle
  pattern), keep coordinators as the only nesting, no recursion.

## Decisions (Michael, 2026-08-30 — provisional prose, IDs are the ADR's)

1. **Verify policy**: scoped check per WP merge (the WP's own contract
   tests + build); full documented verification only at coordinator
   joins, periodic checkpoints, and the final gate. Replaces
   full-suite-after-every-merge. Rationale: selective+backstop is the
   universal pattern (TAP/Meta/Azure/Chromium); checkpoints bound the
   bisection radius premortem flagged; the whole SDD field already
   runs less than this.
2. **Scoped-check source**: default = the WP's own contract tests +
   build check (plan-time, zero tooling); escape hatch = a
   project-documented selective-test command recorded as a convention
   by `/hex-init` (nx affected, testmon, …) where the repo has one.
3. **Review scoping**: review-fix round N reads
   `last-reviewed-SHA..HEAD` plus finding-adjacent files; one
   full-branch pass at the converged gate. New Status-block field
   carries the anchor (stable — execution appends serially, no
   mid-run rewrite). Precedent: CodeRabbit/Cursor incremental-by-
   default; counter (review non-determinism on unchanged code) is
   absorbed by the full converged pass.
4. **Nesting**: depth-1 via the existing coordinator mechanism only —
   coordinators are the "tiny loop" home (local scoped
   implement→review→verify per subtree). Recursion ≥2 declined on
   council evidence (unanimous). Hard requirement: state stays one
   flat Parallelization table with dotted WP rows + computed
   rollups — never nested state files.
5. **Failure cascade**: WP `failed` → dependents block, independent
   siblings keep flowing, run ends listing stranded WPs. Matches
   every DAG engine's default; no per-edge opt-out in v1.

## Scope

Touches (repo-root-relative): `hex/hex-core/references/protocol.md`
(§ Parallel-by-default decomposition — failure cascade; § Worktree
work-package mechanics — scoped-verify-per-merge + checkpoints;
Review-Fix Loop — delta scoping; § Verification — scoped-check
definition + selective-command convention), `hex/hex-init/assets/
templates/plan.md` (Status block last-reviewed anchor; Parallelization
`Verify` column), `hex/hex-execute/` SKILL + tier files (merge gate,
cascade), `hex/hex-review/` SKILL + tier files (delta rounds, full
pass at converged gate), `hex/hex-init/` (record selective-test
convention), `hex/DESIGN.md` (new dated round), new
`adrs/adr_0010_*` (claims C-9xx).

Out of scope: recursion depth ≥2; any new orchestrator role;
ML/coverage-based test-selection tooling (convention pointer only);
review-noise/severity rework beyond adr_0006; `/hex-finalize`
changes.

## Open questions

- [NEEDS CLARIFICATION: which phase actually burned the wall-clock in
  the observed slow runs — serialized merge-verify, review rounds, or
  ready-set non-compliance?] Recommended: capture one slow-run
  transcript during the dogfood run, and diff the installed hex
  copies in the affected bigger repos first (arcana's verified in
  sync 2026-08-30; older installs would still wave-barrier).
- [NEEDS CLARIFICATION: checkpoint cadence M for full verifies]
  Recommended: coordinator joins + every 5th merge + final gate;
  architect tunes against suite cost.
- [NEEDS CLARIFICATION: ready-set compliance hardening — the contract
  is right but observed behavior waves] Recommended: make the
  Schedule step recompute and *log* the ready-set in the Status table
  on every merge, so barrier behavior becomes visible drift.
- Review-fix loop oscillation (fix A introduces B, fix B reintroduces
  A): loop-rounds ceiling exists; Recommended: one contract line
  adding diminishing-returns stop (no new findings class two rounds
  running → stop), else defer to the architect.

## Verification

- `grim build <skill-dir>` per changed skill; `task publish --
  --dry-run` full sweep.
- ADR § Validation re-derived after fix passes (house norm from
  adr_0008 RCA).
- Dogfood on a multi-WP plan: (a) a dependency-ready WP launches
  before its wave completes (ready-set timing observed in transcript);
  (b) full-suite run count = checkpoints + coordinator joins + final
  gate only; (c) review round N diff = delta anchor..HEAD, full
  branch only at converged gate; (d) failed-WP run ends with
  stranded-WP list, siblings completed; (e) wall-clock vs a
  pre-change baseline run recorded.
