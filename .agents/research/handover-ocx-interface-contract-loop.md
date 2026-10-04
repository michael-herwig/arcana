# Handover: ocx interface-contract run took far too long and too many agents

Written: 2026-10-04, from the ocx session that ran it (`ocx-sh/ocx`, branch
`hex/adr-ocx-interface-contract`). Audience: the next hex-performance pass
(prior round: `discussions/hex-execution-performance.md`, handed off to
architect 2026-08-30. This run shows its goals did not take effect in practice).

Owner verdict: "the idea is a very fast DAG based implementation with minor
review loops". The skills turn a problem of about 4 hours into one of about 3 days. The run used
roughly 30% of a weekly 20x-plan budget and was paused by the owner at wave 12 of 17.

## The run in numbers

All figures come from the session transcripts (main session plus 107 subagents).

| | |
|---|---|
| Entry | `/hex-loop` → `/hex-execute`, plan at **tier xhigh**, 45 WPs (40 in-repo, 5 cross-repo) |
| Wall clock | 2026-10-03 06:37 → 2026-10-04 11:00 (≈28.5 h) for 28 of 40 WPs; extrapolates to about 3 days with finalize |
| Branch size | 176 commits, 703 files, +91.5k / −9.3k |
| Subagents | 107 in total: 38 builders, **33 L1 reviews, 28 fix passes**, 4 plan reviews, 2 sub-orchestrators, 2 others |
| Models | 89 opus, 18 sonnet. Almost every builder brief justified opus as "wire-format" or "exit-code semantics" |
| Tokens (cache read) | subagents 2.46 B (builders 1.75 B = 71%, fix 0.29 B, review 0.26 B, orchestrators 0.11 B); main loop 0.23 B |
| Builder turns | 7,995 turns over 38 builders (about 210 each, up to 515). About 700 of their Bash calls were sleep/poll/wait loops; `build.lock` appears 642 times |
| Merge gates | 21 merge verifies, 1–42 min each, about 5 h serialized; 41 full `task verify` calls from inside subagents |
| Main-loop heartbeat | 5-min cron, about 230 wakeups, 214 `ListAgents` calls, 0.23 B cache read, nearly all of it "no change" |

## Where it got out of control

1. **The plan-level tier was applied to every WP.** The ADR was a "one-way door",
   so the whole plan resolved to xhigh. As a result every WP, mechanical ones
   included (env-read migrations, renames, root emission), got an opus L1 review
   and an opus fix pass. That is 61 review and fix agents for 28 WPs, so review
   overhead was about 2× the WP count. `Effective-tier: derived` was set but did
   not bring any WP below the review floor.
2. **Builders are the real cost, and they mostly wait.** 71% of tokens went to
   builders that ran 200 to 500 turns each. Each builder ran the project's
   heavy gates itself (Bazel, cargo test, acceptance tests). All of those queue
   on one host build lock, so parallel builders spent their turns polling,
   and every poll re-reads a growing context. Cost therefore grows with
   (turns × context), not with work done. In this setup a parallel DAG turns
   into a serial queue with expensive waiting.
3. **Opus by default.** The model-routing rule lets a builder justify opus with a
   one-line rationale. Every WP touches a "contract", so 36 of 48 builders were
   opus, including fully mechanical WPs.
4. **The merge gate came before throughput.** The shipped default is one full
   project verify per WP merge. A project rule then also refused a scoped mark
   while `MERGE_HEAD` existed. Together they forced a full gate per merge, and
   the run invented octopus merges per wave (D-38) to cope. The owner had to step in
   ("what is taking so long?") to get one full verify per wave plus scoped checks
   inside WPs. That should have been the default from the start.
5. **Three orchestration levels.** The levels were the meta loop, then the
   hex-execute sub-orchestrator teammate, then the workers. Worker completion
   notices were sent to the meta loop instead of the sub-orchestrator, so every
   one had to be relayed by hand. The sub-orchestrator ignored a pause three
   times and dispatched WP-27, WP-28 and a WP-30 spike. The meta loop added
   nothing except about 230 heartbeat wakeups.
6. **A heavy plan phase before any code.** There were 4 plan reviewers
   (architect, spec, pitfall/SOTA, cross-model) plus a spec re-validation pass, all
   before WP-00.
7. **No disk budget.** Each worktree's cargo target grew past 15 GB and each
   Bazel output base was several GB. With 3 to 4 parallel builders the disk ran
   out twice (down to 102 MB). That cost hours, and the loop stopped on a disk
   floor that it was not allowed to clear itself. `git worktree remove` left the
   Bazel output bases orphaned; 41 of them had to be deleted by hand.
8. **The goal loop cannot be paused.** After the owner paused the run, the stop
   hook kept firing I1–I11 "violation" complaints (I2 never prompt, I8 cycles,
   I11 DONE) on every turn. Pause is not a state the contract recognises.

## Direction the owner asked for

- **Fast DAG, minimal review.** No per-WP review unless the WP is security- or
  wire-critical *by its own content*. One review per phase, run on the merged
  delta. One full verify at finalize.
- **Tier per WP, not per plan.** A one-way-door ADR must not raise mechanical
  WPs to xhigh.
- **Builders do not run heavy gates.** A builder runs scoped checks only. The
  orchestrator runs one gate per wave. Never poll a lock; return and let the
  orchestrator queue the work.
- **Sonnet is the default builder.** Use opus only when the design is still
  open, and not on the strength of a rationale the builder writes about itself.
- **At most two orchestration levels.** Heartbeat of at least 20 min, or
  event-driven only.
- **Disk budget per wave.** Expunge the Bazel output base when removing a
  worktree. The run may delete its own build caches.
- **Pause is a first-class loop state**, honoured by the stop hook.
- **Escape hatches stay unconditional.** The ocx-side `verify:mark` had been made
  "verified legal" (it was refused during a merge). That kills the hatch. Hex
  must never route around a project hatch or demand that one be justified.

## Evidence pointers (ocx repo)

- Transcript: `~/.claude/projects/-home-mherwig-dev-ocx/6ddea4dc-5a85-4466-894c-71934b44ac7b{.jsonl,/subagents/}`
- Plan: `.claude/artifacts/plan_ocx_interface_contract.md` (decisions D-37…D-49 record the in-flight cuts)
- Goal file: `.agents/goals/adr-ocx-interface-contract.md`
- Retro inbox: `.agents/retro/inbox/20261004T033610Z-5e1000d9.json` (disk), `20261004T051551Z-f1e5ec13.json` (loop autonomy gap)
- Merge-gate logs: `target/ic-merge-*.log`
