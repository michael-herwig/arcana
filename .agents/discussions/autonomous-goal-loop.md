# Discussion: Autonomous goal loop — a skill for driving a very large goal end-to-end

State: handed-off → plan · Updated: 2026-09-23
Ratified: 2026-09-23 → plan
Confidence: ratified by Michael Herwig (ran the drained /hex-plan command); research vintage 2026-09-22

## Intent

The user drives large goals (implement an ADR/plan/spec end-to-end, address a
PR's open issues, adopt a breaking upstream release across repos) by posting
hand-written `/goal` prompts to Claude Code. Six examples live in
`.tmp/examples/loops/1.md`–`6.md`. Each one makes a meta-orchestrator chain
`/hex-architect` → `/hex-plan` → `/hex-execute` → `/hex-review` →
`/hex-finalize` without prompting, and ends in a merge-ready PR. The user wants a
skill that produces such a loop, so that a very large goal can be reached from a
short posted command.

Observed in the examples: about 70% of each prompt is the same invariant block.
It covers the meta-orchestrator role, no-prompt autonomy, the doubt protocol
(research → decide, or defer to a GitHub issue), the no-feature-cutting rule,
tmp/worktree hygiene, the anti-stuck 5-minute wake-ups and idle-subagent pulls,
a bounded review/execute refinement loop, and finalize into a merge-ready PR
with a green pipeline and the manual Deep Verify workflow. About 30% varies:
goal source, entry point, done criteria, explicit allowances, context links,
caps, and emphasis (edge-case tests, ASCII-cast docs). The caps drift between
prompts: refinement turns are 2, 3 or 5, and the follow-up threshold is 500 or
1200 LOC. The prompts also hard-code a literal model name.

## Requirements

Provisional. The receiving orchestrator assigns IDs.

- A new hex skill (name `hex-loop`) prints one self-contained `/goal`
  prompt for the user to paste into Claude Code. The skill starts nothing
  itself: no loop, no charter file, no new orchestrator.
- Intended flow: `/hex-discuss` settles the goal, then `/hex-loop <source>`
  prints the prompt. Input is a source to point at — a drained discussion
  artifact, ADR, plan, spec, PR, or issue path/URL — plus free-text extras. The skill drafts the prompt from that source and shows it
  once. The user pastes it as is or edits it first; that paste is the only
  confirmation.
- The invariant block — the meta-orchestrator role, no-prompt autonomy, the
  doubt→research→decide-or-defer-to-issue protocol, no feature cutting, anti-stuck
  wake-ups and idle-subagent pulls, the bounded review/execute refinement loop,
  finalize into a merge-ready PR — lives once, in the skill's own template. That
  single source is what stops drift between runs.
- Variable slots: goal source, entry point (architect/plan/inner loops), explicit
  allowances, context links, caps, emphasis (edge-case tests, use-case docs with
  ASCII casts), and done criteria.
- Project and machine rules are read from `hex.md › Preferences`: the /tmp wipe,
  RAM limits, verify-bypass tasks, the deep-verify workflow name, the
  refinement-round cap (default 2), and the follow-up LOC threshold. The skill
  never hard-codes them.
- The printed prompt ends with an explicit "Done when:" line whose criteria can
  be verified from the transcript: the PR URL, per-job CI results (not the
  top-level conclusion, because skipped matrix jobs have produced false greens),
  and the deep-verify run. The `/goal` evaluator reads only the transcript.
- The printed prompt stays under `/goal`'s 4,000-character cap. The hand-written
  examples ran 1.8–2.9 KB, so the invariant block has to stay terse.
- Shipped text names capability classes, never literal model names.
- Claude Code is the preferred harness, and the printed prompt must also work in
  other harnesses that have the hex skills installed. The prompt body is
  harness-neutral: it names capabilities, not tools. For example, "re-check
  state periodically; use scheduled wake-ups where your harness has them"
  replaces a hard-coded ScheduleWakeup. Only the wrapper differs per harness: a
  `/goal ` prefix where a goal command exists (Claude Code, Codex), otherwise a
  plain prompt. Skill-invocation syntax follows
  `hex/hex-discuss/references/reach.md`.

## Decisions

- **Amendment 2026-09-23 (user, after drain): dedicated goal files.**
  `/hex-loop` writes a goal file per run and prints a short prompt that
  references it. The goal file is the binding per-run contract:
  - Definition of done: acceptance criteria, each with the evidence that
    proves it.
  - Autonomy: prompting policy, allowed actions (force-push, merge, release),
    forbidden actions.
  - Issue resolution: the doubt protocol, when to defer to an issue, the
    follow-up LOC threshold.
  - Loop shape: entry point and refinement caps.
  - Emphasis, context links, and a source pointer.

  Home: a new artifact class `.agents/goals/<slug>.md`, with a template in
  `hex/hex-init/assets/templates/goal.md` and a `hex.md › Pointers` row.
  Precedence: `hex.md › Preferences` gives project defaults, and the goal file
  overrides them per run. The printed prompt stays ≤ 4,000 chars. It keeps
  the invariant core, the goal-file path and an inline "Done when:" list
  giving one short title per criterion. It must keep that list, because the
  `/goal` evaluator reads only the transcript; the run prints a DONE block
  with one evidenced line per goal-file criterion. Done-criteria checkboxes in
  the goal file show progress. There is no other run state (no cursor or
  queue). This partly revives the charter shape rejected earlier — without
  its ADR 0007 machinery.

- **Shape: a prompt-printing skill.** Earlier this run the choice was a protocol
  skill plus a charter file, folded into a revision of
  `.agents/adrs/adr_0007_milestone_driver.md`. That was reversed on new evidence:
  the user's six hand-written `/goal` runs worked in Claude Code as
  self-contained prompts. That removes the unconfirmed question of whether a
  skill named inside `/goal` gets invoked, and the ADR 0007 machinery is more
  than the ask needs. ADR 0007 stays as it is: untouched and still Proposed.
- **Drift is solved by single-sourcing the template in the skill,** not by
  moving state into a charter file.
- **Machine/project rules live in `hex.md › Preferences`.** They are written
  once per project and read by the skill when it prints.
- **Done judgment: an explicit "Done when:" line** that the transcript can
  prove. No scripted Stop hook.
- **`/hex-discuss` gets a fifth drain target, `→ loop`.** Its final `Next:`
  line becomes `/hex-loop <artifact path>`, and `State:` gains
  `handed-off → loop`. Files touched: `hex/hex-discuss/SKILL.md` (§ Handoff and
  the terminal-state list) and the State vocabulary in
  `hex/hex-init/assets/templates/discussion.md`, which is its single home. The
  restate gate stays the only approval gate.
- **Name `hex-loop`; it follows `/hex-discuss` and is portable across
  harnesses** (Claude Code preferred). This was confirmed by the user on
  2026-09-23 and supersedes the earlier "Claude Code only" scope.
- **Sequential by default.** The template may offer example 4's inner-loop
  wording as an option; it adds no concurrency machinery.

## Research

- `.agents/research/discuss-goal-loop-recon.md` — codebase fit.
  `.agents/adrs/adr_0007_milestone_driver.md` (Proposed, not implemented)
  already specifies this outer loop as a fifth orchestrator, `/hex-milestone`,
  and `hex/hex-core/references/config.md` says config cannot express it. Hex
  has no concept of a "meta orchestrator", wake-up routines, or deferring doubt
  to a GitHub issue. Past incidents: a sub-orchestrator background-spawn
  deadlock and a 5-round review blowup.
- `.agents/research/discuss-goal-loop-priorart.md` — prior art. `/goal
  <condition>` is a session-scoped, prompt-based Stop hook. The condition
  (≤4,000 chars) is both the first directive and the completion test. Its
  evaluator is a small model that judges only the transcript and cannot read
  files. The goal survives compaction and resume. It has an idle check-in
  after 30 minutes of background work and a spin guard. Whether a slash
  command inside `/goal` text is invoked is not documented (`/loop` documents
  that it is). In Ralph-style loops, state lives in files and each iteration
  starts with fresh context; vague done criteria cause drift.

- `.agents/research/discuss-goal-loop-community.md` — community practice.
  Practitioners converge on short, verifiable `/goal` conditions with evidence
  forced into the transcript. Open bug
  [anthropics/claude-code#93744](https://github.com/anthropics/claude-code/issues/93744):
  the evaluator may not see the condition text, so it loops and then declares
  the goal impossible. Permission prompts that break unattended runs are the
  most-reported pitfall. Nothing confirms that a skill named in `/goal` text
  gets invoked.
- `.agents/research/discuss-goal-loop-archaeology.md` — past runs in ocx,
  ocx-mirror, ocx-contrib and arcana. Failures: session-limit kills leaving
  state files stale, shared `target`/`/tmp` races between parallel
  sub-orchestrators, and false-green CI from skipped matrix jobs. Guards that
  worked: a stall watchdog, per-agent `CARGO_TARGET_DIR`, scratch outside
  `/tmp`, per-job CI inspection, and `/hex-finalize`'s worktree halt. Deferral
  to issues works (ocx#466 was closed the same day). A cap of ≤2–3 rounds is
  corroborated.
- `.agents/research/discuss-goal-loop-examples.md` — the six source prompts,
  verbatim.

## Related

- `.agents/adrs/adr_0007_milestone_driver.md` — Proposed milestone-driver
  orchestrator. It is a separate, heavier design; this discussion does not
  change it.
- `.agents/research/discuss-goal-loop-examples.md` — the user's six
  hand-written `/goal` prompts, copied verbatim from `.tmp/examples/loops/`
  (scratch that gets wiped). The template's invariant block is derived from
  them.
- `hex/DESIGN.md` — binding constitution (thin dispatcher, capability classes,
  single-source contracts).

## Open questions

- [NEEDS CLARIFICATION: Bundle placement of `hex-loop`.]
  Recommended: a member of the hex bundle — the printed prompt
  names hex modes, so it ships with them.

## Verification

- Round-trip: examples 2 (plan-driven) and 5 (PR-issues-driven), copied
  verbatim in `.agents/research/discuss-goal-loop-examples.md`, regenerated from their sources.
  Every instruction in the originals is present in the output or in
  `hex.md › Preferences`, and each output is ≤ 4,000 characters.
- One real paste of a generated prompt reaches a merge-ready PR, with the
  "Done when:" evidence visible in the transcript.
- A generated prompt is pasted into a second harness (Codex) and the hex skills
  are invoked from it.
- `grim build hex/hex-loop` passes, and `task publish -- --dry-run` passes.
- Shipped text is checked against `hex/DESIGN.md` (capability classes, thin
  `SKILL.md`).
