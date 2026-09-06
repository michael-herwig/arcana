# RCA: hex 0.2.0/0.3.0 review-fix loop wall clock on small code changes

**Date:** 2026-09-05 · **Owner:** hex meta-orchestrator · **Feeds:** plan_wave0_quick_wins, adr_0012, adr_0013
**Evidence:** `~/dev/*/.claude/state/subagents.jsonl` spawn logs (hook-written), plan artifacts, git history in `ocx`, `ocx-sion`.

## Verdict

Wall clock scales with **serial worker round-trips**, not LOC. adr_0010's delta scoping cut *bytes read per round*; on an 80-LOC diff that was already ~0. Round-trip count went **up** (extra stages, all-opus, adversary gate without deadline, unscoped full-verify gates) while per-worker latency stayed flat: median opus batch→next-batch 14.7 min before 2026-08-30 (858 batches) vs 11.8 min after (221 batches). Docs-only WPs finish in ~15 min because they take 1–2 round trips; the same law.

## Traced case

`ocx-sion`, plan `.claude/artifacts/plan_index_claim_command.md` (Tier **high**, 19 WPs, 16 `panel`), WP-1 "exit code 86" → commit [19251402](https://github.com/ocx-sh/ocx/commit/19251402): **2 files, +78/−3**. Plan row: size **S**, Review **panel**, Verify scoped. Execute sub-orchestrator spawned 01:33 UTC, commit 04:39 → **3h06**.

| UTC | WP-1 stage | model | wait to next |
|---|---|---|---|
| 01:38 | "edge-case hunt" reviewer (in no hex file; from ocx `workflow-swarm.md` max row) | opus | 17m |
| 01:55 | stub | sonnet | 18m |
| 02:13 | specify | opus | 15m |
| 02:28 | implement | opus | 12m |
| 02:40 | R1: quality + spec reviewers + architect ADR check | 3× opus | 11m |
| 02:51 | round-2 fix; worker died silently, re-spawned 03:20 | opus | 29m + 10m |
| 03:30 | R2 quality | opus | 16m |
| 03:46→04:39 | no WP-1 spawn; single sub-orchestrator busy on WP-4/WP-5, then merge + verify | | 69m |

Second case: `ocx` session 2026-08-31 (2h51 total): codex adversary pass 17:59 → retry 19:35 = **95 min** hole, no deadline.

## Root causes, ranked

1. **Pipeline depth constant.** Stub→Specify→Implement→R1→fix→R2→converged pass→merge ≥ 7 serial round trips at every tier (`tier-low.md`: "keep the skeleton unchanged"). ~12 min/opus trip → 90 min floor before the first finding.
2. **Tier is plan-global; the only per-WP dial is `Review`, set wrong.** Tier high forces opus tester/builder + adversarial breadth on all 19 WPs. Heuristic (protocol.md § Parallel-by-default decomposition) says ≤50 lines, no security → `self`; WP-1 got `panel`. Plan-side guard exists only upward (`self` on security WP = defect). Merge-time re-validation only escalates. Budget never lowers phases or model class.
3. **All-opus + unspecced stages.** ocx `hex.md` overrides pin all reviewer roles to deep-reasoning at every tier; CLAUDE.md model policy pushes builder/tester to opus for "exit-code semantics". Opus share 69% → 76% after 08-30.
4. **Single-threaded sub-orchestrator.** One opus orchestrator serialized 5 WPs; WP-1 idle ~1h after its loop ended. Dead worker cost 30 min; hex has no worker liveness/timeout.
5. **Adversary gate has no deadline.** `adversary=on` auto-fires on tier high or any security signal (always true in ocx); `codex:rescue` has no timeout; nox's 900 s default not in play.
6. **Unscoped gates.** Implement gate and Review-Fix exit gate run full documented verification ("whole workspace" at high); ocx `task verify` ≈ 25 min (ocx `hex.md` Memory). Only the merge gate is scoped (1m32s logged). Inferred for the 69-min tail.

## Not the cause

- Per-worker latency (flat before/after).
- Skill file growth alone (protocol.md 46 KB → 82 KB; orchestrator cold-load, not per-round cost) — a Wave 2 diet item, not the 6x.
- RAM/serena: ocx's OOM kills were build parallelism (see `parallel-resource-pitfalls.md`).

## Targets

WP-1-class (S, no risk flag): ≤ 30 min. Wave 0 alone: ~halve. Wave 1 (per-WP effective tier + per-WP sub-orchestration + liveness): reach target.
