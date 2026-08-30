# Research: How spec-driven-development frameworks execute their plans (competitive/vendor, neutral)

## Metadata
Date: 2026-08-30
Expires: 2027-02-28

## Scope
github/spec-kit, OpenSpec (openspec.dev / Fission-AI), Spec Kitty (spec-kitty.ai),
Get-Shit-Done / GSD (gsd-build), plus two frameworks surfaced as directly relevant
comparators: Tessl's `tlc-spec-driven` skill and BMAD-METHOD (+ community
extensions bmad-loop, bmad-autonomous-development). Strictly evidence-reporting,
no recommendation.

## Per-framework findings

### github/spec-kit
- **Scheduling**: `/speckit.tasks` emits `tasks.md` organized into dependency
  phases (Setup → Foundational → User Stories → Polish); independent tasks are
  tagged `[P]` as "safe for parallel." But `/speckit.implement` itself executes
  **all tasks sequentially in one continuous run** — the `[P]` markers are
  advisory, not enforced concurrency. Confirmed by a closed community feature
  request, [github/spec-kit#1008](https://github.com/github/spec-kit/issues/1008),
  asking for an `/speckit.execute-next` command to run one task at a time with
  resumable state; issue was closed "not planned" with no visible maintainer
  rationale in the retrievable thread.
- **Verification**: TDD ordering is baked into the implementation template
  itself, not a per-task scoped check: contracts → tests (contract → integration
  → e2e → unit, in that order) → tests confirmed to **fail** (Red phase) →
  only then implementation code. This is a whole-plan Red/Green gate expressed
  as file-creation order, not a per-task budget.
  Source: [spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md).
- **Review loop**: no discrete per-task review command found. Review is
  implicit at artifact boundaries (spec → plan → tasks), each meant for human
  sign-off before the next command runs; no whole-diff review step surfaced.

### OpenSpec (Fission-AI/OpenSpec, openspec.dev)
- **Scheduling**: `tasks.md` is a "living checklist" worked by `/opsx:apply`
  one item at a time, in list order; the agent checks items off and resumes
  from the first unchecked task across sessions. No parallel execution or
  worker fan-out is described anywhere in the docs.
- **Verification**: `/opsx:verify` (only in the opt-in "expanded" workflow
  profile, not the default) diffs proposal/spec/tasks against the actual code
  and flags divergence as CRITICAL/WARNING/SUGGESTION — and explicitly
  **does not block archiving**. It checks artifact-vs-code coherence, not
  project test-suite execution.
- **Review loop**: OpenSpec deliberately has **no discrete review phase/gate**.
  Maintainer framing: "there is no review phase to return to... review is
  something you can do at any point, including after implementation," via
  `openspec show <change> --diff` (a colorized per-requirement diff of what
  the change's spec delta alters). Review is on-demand, whole-change, and
  non-blocking by design — the one clear minority position in this survey.
  Sources: [Fission-AI/OpenSpec docs/concepts.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md),
  team-workflow.md, and syndicated docs summaries (primary
  `openspec.dev/docs/reviewing-changes` 404'd on direct fetch — see Negative).

### Spec Kitty (Priivacy-ai/spec-kitty, spec-kitty.ai)
- **Scheduling**: the only tool in this survey with **real concurrent
  execution** in its core product — each work package gets an isolated git
  worktree (`.worktrees/<feature>-lane-<id>/`), and `spec-kitty next --agent`
  assigns agents to work packages concurrently. Docs don't confirm whether a
  dependency graph gates which packages may start together, or whether it's
  purely lane-slot based.
- **Verification**: `/spec-kitty.analyze` runs cross-artifact consistency
  checks (spec vs plan vs tasks) at the mission level, after task generation.
- **Review loop**: incremental, per work package. `/spec-kitty.review`
  evaluates one completed work package (its prompt + diff) and moves it to
  "approved" (review passed) or back to "planned" (rework needed).  Only once
  **all** packages are approved does `/spec-kitty.accept` validate the whole
  mission and `/spec-kitty.merge` land it — i.e. per-unit review gates, then
  one whole-mission acceptance/merge gate. Default posture is explicitly
  "governed, human-in-loop"; a more autonomous "dark software factory" mode is
  opt-in per their own docs.
  Source: [docs.spec-kitty.ai/api/slash-commands.html](https://docs.spec-kitty.ai/api/slash-commands.html).

### Get-Shit-Done / GSD (gsd-build/get-shit-done)
- **Scheduling**: each subplan holds 2–3 atomic tasks; each task runs in a
  **fresh subagent** with a clean 200k-token context, explicitly to fight
  "context rot" (their stated rationale for long single-session agents
  degrading). Execution reads as sequential per subplan (spawn agent → do task
  → write summary → commit), not parallel.
- **Verification**: every plan embeds explicit measurable success criteria and
  "gates," plus human validation prompts where needed. A distinct
  `/gsd:verify-work` step performs human acceptance testing for things
  requiring manual confirmation (payment flows, UI smoke tests) — GSD pauses
  and asks rather than assuming automated coverage is sufficient.
- **Review loop**: cycle is discuss → plan → execute → verify → "learn" (a
  retro that folds back into the next spec). Verification reads as
  end-of-phase, not per-task; the fresh-context-per-task design targets
  execution quality, not incremental review.

## Adjacent comparators surfaced during the search

### Tessl `tlc-spec-driven` skill (tech-leads-club)
The clearest published **numeric effort/verification budget** found in this
search: tasks are grouped into "task-budgeted batches of ~7 tasks," one
worker per batch, whole phases never split across workers (20 tasks ≈ 3
batches, 40 ≈ 6 — scaling is linear, but batches run **strictly
sequentially**, so "workers" here means "batches," not concurrency). Per-task
loop: implement → gate (spec-derived acceptance tests must pass — "the test
runner decides, not self-assessment") → atomic commit (task marked complete
in `tasks.md` before commit). After the **last** task, a fresh Verifier agent
(author ≠ verifier) runs automatically, doing spec-anchored checks plus
mutation-testing-style validation. This is the only framework surveyed with
an explicit author/verifier separation and a stated batch-size number.
Source: [tessl.io/registry/.../tlc-spec-driven](https://tessl.io/registry/skills/github/tech-leads-club/agent-skills/tlc-spec-driven).

### BMAD-METHOD + community extensions
Core BMAD is role-based (PM/Architect/Scrum-Master/Dev/QA agents) producing
self-contained "story files" that a Dev agent executes **sequentially**.
True dependency-graph-driven parallelism is **not core** — it appears only in
a third-party extension, [stephenleo/bmad-autonomous-development](https://github.com/stephenleo/bmad-autonomous-development),
which explicitly runs "fully autonomous, parallel, multi-agent pipelines...
driven by your sprint backlog and dependency graph." A separate community
project, [bmad-code-org/bmad-loop](https://github.com/bmad-code-org/bmad-loop),
implements a per-story loop: pick story → implement → **adversarially
review** → verify → commit — the closest analog in this survey to an
incremental, per-task review loop with an explicit adversarial stance.

## Cross-cutting synthesis

1. **Scheduling**: spans a spectrum. OpenSpec and core GSD/BMAD are
   single-agent, strictly sequential (list/story order). Spec-kit and Tessl's
   skill use dependency/phase batching but still execute sequentially by
   default — spec-kit's `[P]` tags are advisory only, never enforced
   concurrency. Spec Kitty is the only *core, shipped* tool with real
   concurrent multi-agent execution (git-worktree lanes). True DAG-scheduled
   parallelism otherwise shows up only in a third-party BMAD extension, not in
   any core/default SDD tool surveyed.
2. **Verification**: none of the surveyed tools runs the full project test
   suite after every task by default. Distinct patterns seen: (a) TDD
   ordering baked into template file-creation order (spec-kit's Red-phase
   gate); (b) scoped, spec-derived acceptance-test "gates" per task (Tessl,
   GSD); (c) end-of-change artifact/code coherence checking with **no test
   execution and non-blocking** (OpenSpec's `/opsx:verify`); (d) a distinct
   verifier role/pass, separate from the author, only in Tessl's skill and in
   BMAD's adversarial-review step. Tessl's ~7-task batch is the only
   concrete numeric effort/verification budget found; GSD's "budget" language
   is about context tokens (200k/subagent), not verification effort.
3. **Review loops**: OpenSpec deliberately rejects a discrete review gate
   (on-demand diff only, non-blocking — a notable minority stance). Spec-kit
   reviews at artifact boundaries (spec/plan/tasks), not per code task. Spec
   Kitty and Tessl's skill both do incremental per-unit review (per work
   package / per batch) followed by one whole-change gate at the end (Spec
   Kitty's accept+merge; Tessl's final fresh-Verifier pass). GSD's review is
   an end-of-phase human-verification step plus a later retro, not per-task.
   BMAD core has no review loop until a later QA step; adversarial per-story
   review only exists in the community bmad-loop extension.

## negative
- Could not retrieve full primary-source text for three pages — WebFetch
  returned 403/404 on `openspec.dev/docs/reviewing-changes` (404),
  `zread.ai/github/spec-kit/15-task-breakdown-and-execution` (403), and
  `zread.ai/gsd-build/get-shit-done/28-verification-patterns` (403). Findings
  for OpenSpec's review stance and GSD's verification patterns rely on
  WebSearch snippet synthesis from secondary sources rather than fetched
  primary text — flag as lower-confidence.
- No evidence surfaced that any surveyed tool runs the **actual project test
  suite** per task by default; "scoped checks" is the best current read for
  GSD/Tessl, not confirmed exhaustively (their docs describe spec-derived
  acceptance gates, which may or may not equal the real test suite in
  practice).
- No maintainer rationale found for spec-kit closing
  [#1008](https://github.com/github/spec-kit/issues/1008) as "not planned" —
  thread content beyond the original post wasn't retrievable, so *why*
  spec-kit stays whole-plan-sequential is unconfirmed, not just absent.
- Kiro (AWS) appears repeatedly in third-party comparison articles alongside
  spec-kit/BMAD but was not investigated — out of the scope actually
  requested, and left as a lead below rather than covered thinly.

## leads
- Tessl's `tlc-spec-driven` author≠verifier separation + numeric batch budget
  is the strongest external precedent found for "effort budget per unit of
  work" — worth a dedicated look if that's a live design question elsewhere.
- bmad-loop / bmad-autonomous-development (community BMAD extensions) are the
  only place true dependency-graph-scheduled parallel execution appears
  outside Spec Kitty — a separate lane on DAG-scheduled parallelism
  specifically could dig into these two repos alone.
- OpenSpec's "no review phase by design" stance is worth flagging to whatever
  lane is weighing mandatory vs. optional/on-demand review gates.
- AWS Kiro was not covered here (named in surveys as a comparator to
  spec-kit/BMAD) — open lead if the swarm wants a fifth data point.
