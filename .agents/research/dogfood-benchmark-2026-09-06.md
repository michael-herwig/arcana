# Dogfood benchmark: WP-1-class change under Wave 0 + Wave 1

**Date:** 2026-09-06 · **Owner:** dogfood-bench sub-orchestrator
**Measures:** waves plan item 11 · **Reference:** `rca-review-fix-loop-wall-clock.md`

## Verdict

**Target met, at the boundary: execute+review loop 30m01s vs the RCA's 3h06
(6.2x).** The win is structural: serial round trips fell 7 → 4 (collapsed
builder, concurrent minimal review batch, 1-round cap). Per-worker latency is
unchanged and now *is* the wall clock — 26m47s of the 30m01s is three turnarounds.

## Setup

- **arcana** `2b87734` (branch `hex/execution-runtime-program`); **clone base**
  `43536771` at `.tmp/dogfood/ocx-sion`, no remote, branch `bench/wp1-class`.
- **Installed** project-scoped (`grim install`, dev): hex-core, hex-init, hex-plan, hex-execute, hex-review, `hex-state.md -k rule` — byte-identical.
- **hex.md limits written**: `max-workers: 3`, `loop-rounds: 1`, `adversary-timeout: 5`, `heavy: 18`. **Profile**: peak RSS 1.26 GB · wall 1m21s · class `heavy` · ceiling 18 (RAM 31 GB, headroom 7.75 GB, nproc 32).
- **Deviations**, flagged in the clone's `hex.md`: `/hex-init` ran **narrow**
  (model matrix, `limits`, profile pointer only), and the profile measured the
  **WP-scoped** `cargo check -p ocx --all-targets`, not ocx-sion's full
  `task verify` (≈ 25 min per its own `hex.md › Memory`) — `Degraded: scoped
  proxy measurement`. The clone's submodules were empty and blocked every cargo
  call; copied in read-only from the original tree first.
- **The change:** normalize `--keywords` before it becomes the
  `sh.ocx.keywords` annotation, in `crates/ocx_lib/src/package/description.rs`
  and `crates/ocx_cli/src/command/package_description_push.rs`. Diff **2 files,
  +147/−3** vs the reference's +78/−3; source churn alone is ~35 lines.
- **Plan** `.claude/artifacts/plan_normalize_keywords.md`, tier `low`, 1 WP,
  marker `Effective-tier: derived`, cells Size `S` · Review `light` · Verify
  `scoped`. **Effective tier `low`** (derived: S, no risk flag), histogram
  `effective tier: low 1 (ceiling low)` — that derivation put the builder on
  `fast-balanced`, the run's largest single saving.

## Timeline (UTC, 2026-09-06)

| Time | Event | Model class | Elapsed |
|---|---|---|---|
| 08:14:20 | bench start; clone, remote removed, 6 artifacts installed | — | 20s |
| ~08:15 | **plan start** — Discover: 1 explorer | fast-balanced | ~6m |

| 08:23:56 | plan drafted inline; review round 1 of 1; 7 findings applied (2 Major, no Block) | deep-reasoning | 2m59s |
| 08:28:08 | **plan end / execute start** — committed, worktree created | | plan ≈ 13m |
| 08:28:10 | collapsed builder (Stub+Specify+Implement, one spawn) | fast-balanced | 11m08s |
| 08:40:53 | two-commit protocol verified: 9 tests FAIL at `6b229e01` | orchestrator | 50s |
| 08:41:00 | Review-Fix R1: `quality` + `spec`, concurrent | deep-reasoning ×2 | 10m02s |
| 08:52:00 | 1 fix pass (1-round cap; no second review round) | fast-balanced | 5m37s |
| 08:57:43 | scoped merge gate | — | 34s |
| 08:58:09 | **WP 1 merged** `21f25d18` | | **execute 30m01s** |

Verify-Architecture skipped (tier low). Adversary **skipped** (`adversary: off`
at tier low) — the stall bound never armed, so the RCA's 95-minute adversary hole
cannot recur here; no observation mode applies. The plan's schedule log below
matches my own timestamps; the orchestrator wrote it, since nothing in the
shipped text makes a phase emit its own line.

```
- 2026-09-06T08:39:16Z · phase WP1/collapsed-builder · model fast-balanced · work 11m08s · rounds 1
- 2026-09-06T08:51:38Z · phase WP1/review-fix-r1 · model deep-reasoning · work 10m02s · rounds 1
- 2026-09-06T08:57:35Z · phase WP1/fix · model fast-balanced · work 5m37s · rounds 1
- 2026-09-06T08:58:09Z · merged WP1 @ 21f25d18 · verify scoped [34s] · ready: — · blocked: —
```

## Per-phase vs the RCA reference

| Stage | RCA (WP-1, tier high) | This run (effective low) | Delta |
|---|---|---|---|
| stub → specify → implement | 3 spawns, 45m, all opus | 1 collapsed spawn, 11m08s, sonnet | −34m, −2 trips |
| review round 1 | 3× opus, 11m | 2× opus concurrent, 10m02s | −1m |
| fix + round 2 | 39m (incl. a 30m dead worker) | 5m37s, no round 2 | −33m |
| merge + verify tail | 69m idle (single-threaded orchestrator) | 34s | −68m |
| **total** | **3h06** | **30m01s** | **6.2x** |

## Review rounds and findings

- **Plan review** — 1 round, 7 findings (2 Major, 4 Minor, 1 Nit),
  request-changes. Both Majors real: no contract routed the deserializer through
  the shared helper the plan's own Key Decision promised, and the named test
  filter matched zero tests.
- **Code review R1** — 2 reviewers, 4 findings (1 Major found independently by
  both, 2 Minor, 1 Nit), both request-changes. The Major was proven by mutation:
  both deleted the production normalization and the suite stayed green, because
  the tests recomputed the production expression instead of calling it.
  **Minimal breadth at tier low still caught a real defect.**
- **Resource / liveness** — max 2 workers concurrent against a ceiling of 3, no
  OOM. Sole contention: cargo's own target-dir lock serialized the background
  measurement against the builder, what `limits.heavy` models but taken by
  cargo, not a hex slot. **No liveness ladder rung ever fired**, see defect 1.

## Defects and friction in the new hex text
1. **The liveness ladder cannot run under a blocking spawn primitive.**
   `hex-core/references/protocol.md` rung 3: "turn-boundary checks → glob the
   whole heartbeat directory, unfiltered … at each turn the orchestrator takes
   anyway … **zero added turns**". When spawning blocks until the worker returns
   the orchestrator takes no turns, so detection latency equals the worker's own
   completion. The 11m08s builder and 10m02s batch were unobservable throughout.
   Needs a fourth degrade line.
2. **A tier-low plan authored strictly from `hex-plan/tier-low.md` is refused,
   and the cell it does name is inert.** `protocol.md` § the effective tier:
   "**A marker on a plan with no `Verify` column is a refusal**". Phase 5 of
   `hex-plan/tier-low.md` says only "The WP still carries a Review budget —
   typically `self` or `light` at this tier": it never mentions `Verify`, and
   under the marker `self`/`light` are inert no-ops. `hex-execute/tier-low.md`
   flags that flip ("In a plan carrying the generation marker that direction is
   flipped"); its plan-side twin does not.
3. **The scoped check's test half has no non-empty assertion.** A name-filtered
   `cargo test` matching zero tests exits 0. It happened twice: the plan reviewer
   caught it in the drafted gate, and my own background gate reported
   `0 passed; 0 filtered out` and looked green. `protocol.md` § Scoped check
   requires half (b) assembly proof but never requires the test half to prove it
   matched anything. The fastest green available is a filter matching nothing.
4. **`models.overrides` is tier-blind, so Wave 1's win stops at the builder.**
   `config.md`: `models.overrides` → "Per-role class override **at every tier**".
   ocx-sion pins four reviewer roles to deep-reasoning, so the derived `low`
   lowered the builder (the −34m win) while review still ran two opus workers for
   10m02s, a third of the window. RCA root cause 3 survives Wave 1 intact; the
   vocabulary has no per-tier override spelling.
5. **`.agents/` gitignored makes `hex.md` uncommittable.** Its header says
   "Team-shared — commit it", and hex-init's audit asks "Is the worktree path
   (default `.agents/worktrees/`) gitignored…?" but never the converse, whether
   the rule stays narrow enough to leave `hex.md` committable. ocx-sion carries
   a bare `.agents/` line, so `git add .agents/memory/hex.md` is refused.
6. **A stale global install silently shadows the artifact under test.**
   `grim install` warns "skill 'hex-core' is also installed at global scope for
   claude; both copies are visible to that client" — and the global copies here
   are the *published*, pre-Wave-1 version. A harness preferring global scope
   would have benchmarked the old bundle with no symptom; I drove the clone's
   files directly instead. Not hex text, but the trap that makes a dogfood
   benchmark lie.
7. **The collapsed builder's ordering check is unbounded.** `protocol.md` § the
   collapse: "the orchestrator runs the project's test command at that commit and
   requires it to fail" — a checkout plus a test run at an older commit, 50s warm
   here, a full rebuild cold. No budget is set for it.

## Top 3 remaining time sinks
1. **Collapsed builder, 11m08s (37%).** One round trip, but stub, tests,
   implementation and the two-half gate run serially *inside* it — the collapse
   removed the trips between those stages, not the work.
2. **Review batch, 10m02s (33%).** Two deep-reasoning workers concurrent, so the
   slower sets the pace. Defect 4 is the lever — at effective `low` the shipped
   matrix wants fast-balanced here.
3. **Fix pass, 5m37s (19%).** Irreducible at one round, and it exists only
   because R1 found a real defect. The 50s commit-1 check and 34s merge gate are
   noise beside these.

Together 26m47s of 30m01s: 89% is worker turnaround. The RCA's law holds — wall
clock is serial round trips times per-worker latency. Wave 1 bought 6.2x by
cutting trips 7 → 4; the next factor needs either fewer trips again or a lower
model class on the review batch. Nothing else is left in the window.
