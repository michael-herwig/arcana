# hex next iteration: pipelines run free, checks are counted

Status: proposal v5 · 2026-10-04 · branch `hex/fast-path-overhaul`
Evidence: ocx interface-contract run (108 transcripts: compile/test
parallelism 1.0, builders 36 % of their lifetime in lock/verify/wait calls,
89/107 opus), `handover-ocx-interface-contract-loop.md`. v4 was red-teamed and
checked against the owner's statements; both findings are folded in.

## Diagnosis

Every hex gate is **eager and local**: decided per change, by an agent that
sees one change and none of the cost. Asked "might this matter?" N times, a
cautious agent says yes N times, and locks turn the DAG into a queue. New
classifications only move a threshold the agent then crosses on every change.
The fix changes **who decides and how often**: workers never raise cost, the
orchestrator raises it a few counted times per run, and the expensive gates
are fixed by count instead of triggered.

## 1. Parallel pipelines

- A plan is a few **pipelines** cut along contracts. A pipeline is an ordered
  chain of **steps** in one worktree, each step a fresh `standard` agent with a
  small brief. Inside a pipeline: serial, shared state, no merge, no review,
  no gate between steps. Across pipelines: parallel, sharing only contracts.
- Splitting into steps is cheap (it keeps contexts small). Splitting into
  pipelines buys parallelism, but only where a contract can be fixed up front.
  Nothing else.
- **Contract wave first**: stubs **plus contract tests** for every pipeline,
  committed once. Then all pipelines start together. A step that edits a
  contract-wave file is detected by `git diff` at its return, and the
  orchestrator re-briefs the affected pipelines. No review is triggered.
- **Small task = one pipeline**: no contract wave, one review, one gate.

## 2. Checks: only where consumed; full gates by count

- **Step feedback is the only inner check.** A step that changes behaviour
  runs the tests it wrote or touched, once, green, using the narrowest command
  it picks itself (`cargo test -p x`), never the project's gate wrapper. A step
  with no behavioural effect (docs, taskfiles, config, renames, comments) runs
  **nothing**. This is a principle about effect, not a file list: "will this
  be exercised later anyway?" → skip.
- **Every commit and merge on hex-owned branches uses `--no-verify`.** That
  is the preferred path. The step brief states that the run's exit gate
  satisfies the project's "verify before commit" lines (ocx `CLAUDE.md:139`,
  `AGENTS.md:109`), because those lines are injected into every subagent and
  would otherwise put the full gate back.
- **Exactly two full gates per run, fixed by count; no rule upgrades anything
  to one**:
  1. *Integration*: when all pipelines have landed, **concurrent with** the
     review. One fix pass serves both.
  2. *Release*: `/hex-finalize`, fresh with no cache (`/hex-init` records the
     project's switch), plus the project's hooks and lint over the final
     range. If it fails: one fix pass, then the gate again; still failing,
     stop and hand to the user.
- Pipelines never commit hub or generated files (lockfiles, baselines,
  goldens; `/hex-init` lists them). They are regenerated once at integration,
  minimally (no `cargo update`).

## 3. Review: one outer loop, chunked only when very big

- **Default: one `/hex-review` after all pipelines land**, with the staged
  panel and codex, autonomous. Seats are split per pipeline inside it, plus
  one seat for the seams between pipelines. Fixes run per pipeline in
  parallel; the re-check covers the fix delta only; cap 2 rounds.
- **Mid-run review is the orchestrator's call**, for a very big finished chunk
  with much still to come. Expect 0; at most 2 per run. Each call covers
  `anchor..HEAD`, so later edits to reviewed code are included next time.
- A pipeline reviews itself only when the plan marks it. That is rare.
- **Seats are `standard` at every tier.** Tier scales the seat count only.
  `deep` seats run only when the user asks. If codex is unavailable, log a
  skip line and never wait for its quota.

## 4. No waiting, no locks

- **Workers never wait** on a lock, a gate or a poll. A worker that would
  wait returns instead.
- **Parallel builds share one build's budget**: the number of live pipelines ×
  jobs per pipeline ≤ the project's single-build jobs (ocx: `jobs = 12`).
  RAM stays at about one build, with no measurement needed. Shared caches do
  not fix this; ocx already had them and still serialized.
- Heavy or exclusive tools (bazel servers, the docker acceptance project) are
  **gate-only**. A step that needs a one-off exclusive check hands it to the
  orchestrator in the background and does not wait for it.
- No shipped text and no learned project lesson may add a worker-side lock.
  `/hex-init` flags one (ocx `hex.md:439`, `.agents/ic/brief_common.md`).
- The orchestrator's main loop only dispatches and merges. Anything slow runs
  in the background. Event-driven, ≥ 20 min fallback, two levels.
  `/hex-loop` gains a `paused` state.

## 5. Model ladder

| Class | Claude | Use |
|---|---|---|
| `light` | Haiku | search, inventory, mechanical edits |
| `standard` | Sonnet | **default**: steps, fixers, review seats |
| `standard-high` | Sonnet at high effort | escalation; plan-marked hard steps |
| `deep` | Opus | architect and plan design; last-resort escalation |

- Only the orchestrator escalates, and only when the **same step fails
  repeatedly**. Failure means the step returned incomplete or its output was
  rejected. A red TDD phase is not a failure. The sequence: retry at the same
  class with the failure attached → one class up → defer as residue while the
  loop continues.
- Plan marks reach `standard-high` only, on at most 1 in 4 pipelines.
- `/hex-init` instantiates each class as an agent definition with `model` and
  `effort` frontmatter. Claude Code supports per-agent `effort`
  (`low`…`max`), but the Agent tool has no per-spawn effort, hence the
  definitions.
- The global `~/.claude/CLAUDE.md` routing table changes to match.

## 6. The numbers are constitution

Full gates per run: **2**. Review calls per run: **≤ 3**. Workers wait:
**never**. Escalation: **orchestrator only, on repeated failure**.
`DESIGN.md` records these. Changing one takes an ADR backed by a measured run.
That stops the drift that slowed every round since v0.1.

## Removed / kept

- **Removed**: per-WP tiers and risk flags, `L0`–`L2` join reviews, per-merge
  and checkpoint verifies, the heavy semaphore, Verify-Architecture per WP,
  the red-at-stub check, the decomposing coordinator, worker heartbeat beats,
  and `/hex-execute`'s tier files and overlays.
- **Kept**: `/hex-review` with its panel and codex, `/hex-finalize`,
  `/hex-loop`, contract-first TDD, ADR review for one-way doors, and the
  last-reviewed anchor.

## ocx run, same plan

| | ran | v5 |
|---|---|---|
| shape | 45 WPs, 17 waves | ~6 pipelines × ~6 steps, contract wave + one fan-out |
| opus spawns | 89 | plan design only |
| full verifies | 41 + 21 merge gates | 2 |
| review | 33 leaf reviews + 28 fix passes | 1 (≤ 3) `/hex-review` calls |
| build parallelism | 1.0 | live pipelines, at one build's RAM |
