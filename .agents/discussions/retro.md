# Discussion: retro — agent friction capture and a retrospective skill

State: handed-off → loop · Updated: 2026-09-23
Ratified: 2026-09-23 → loop
Confidence: ratified by Michael Herwig in-session; research vintage 2026-09-23 (recon, priorart, community, vendor, archaeology)

## Intent

Make the AI configuration improve itself. Every subagent that hits friction
while using skills — something took too long, was inconvenient, or was a
pitfall worth persisting in AI configuration — records a structured entry
with context. A new hex skill, `retro`, later consolidates those entries into
proposed improvements to the skills involved or to the project's own config.

Why now: `.agents/handover_dogfood_findings.md` (untracked, F-001..F-012) is
a hand-maintained instance of exactly this, and its F-004 already proposes a
`/hex-retro` skill; its findings were all noticed "in passing". Nothing asks
an agent to separate project defects from harness defects.

Out of scope (user, 2026-09-23 — future, not this work):

- A dedicated hex Go executable that owns capture/state scripts.
- Progress and ETA visibility for running plans; a CLI managing plan state as
  a DAG; a background daemon serving plan state visually over a web server.

## Requirements

- Capture is **hybrid**: agent self-reports plus objective trajectory signals
  (retries, failed tool calls, slow steps) as corroboration. Self-report alone
  is weak signal (prior-art: verbal confidence ~AUROC 0.63 for failure).
- Capture reaches **every subagent**, not only hex spawns, via a published
  rule — and, because a rule is hardening never precondition (`hex/DESIGN.md`)
  and is absent on several clients, retro must still work without it.
- Concurrent-safe with no lock: one file per entry, written temp-then-rename
  (maildir shape; hex heartbeat precedent). A shared JSONL with `flock` is
  rejected — dogfood F-001 shows a lock fd leaking into `sccache` and
  deadlocking.
- Entries written from a worktree under `.agents/worktrees/` must survive
  worktree removal (dogfood F-005 is the same gap for gate evidence).
- Every entry is attributable: the installed artifact and version it concerns
  (available from `grimoire.lock` / `grim status --format json`) or the
  project, so retro routes a fix to its owner — upstream skill source vs
  project config. F-004's discriminator: *would this have happened on a
  different codebase with the same skills?*
- Retro proposes, never auto-applies: no surveyed product applies a
  self-proposed config edit without human approval (Windsurf, and possibly
  Amp, are the counter-examples; Claude Code `/insights` emits rules with no
  gate and the community bolted one on).
- The consume→fix leg is the bottleneck, not capture: the Upkeep step has
  produced exactly one `hex.md › Memory` entry ever, and none of the twelve
  dogfood F-findings has a matching fix in `hex/` (archaeology). Retro is
  judged by findings turned into landed changes, not by entries collected.
- Every proposed edit carries its rationale (why the instruction exists) —
  the strongest reported countermeasure to instruction-file bloat
  (community lane).
- Findings are valued over time, not per run (user, 2026-09-23): loops run
  for days and are dominated by recurring costs (e.g. acceptance tests), so
  retro keeps a **ledger** of clustered findings — occurrences, first/last
  seen, cumulative cost (wall time lost), status (open | deferred | fixed |
  reopened). Value is recurrence × cost, not raw count. A deferred finding
  accrues value on every recurrence and becomes "big value" at a later
  checkpoint once it crosses the bar; a `fixed` finding that recurs is
  reopened (the fix is verified by absence). The ledger is maintained by
  retro mechanically, never by agents by hand. Recurring-cost findings are
  only visible through the objective channel (step durations aggregated
  across a run), which makes it load-bearing, not corroboration only.
- Retro feeds the existing Upkeep step → `hex.md › Memory` promotion
  candidate → `/hex-init` re-audit path for project conventions rather than
  duplicating it (`hex/hex-core/references/protocol.md` Upkeep step,
  `hex/hex-init/references/audit.md`).

## Decisions

- Drain target: loop (user, 2026-09-23; plan considered first).
- Capture mode: hybrid (user).
- Capture reach: a published rule only, now (user). No `workers.md` duty.
  Accepted gap: hex workers on clients without rule support (Codex, Gemini,
  Zed, Amp) produce no self-reports until hooks land.
- Hooks, once grim can publish them, **replace the objective channel**
  (transcript mining → tool-failure / subagent-stop / duration hooks), not
  the rule: a deterministic hook cannot judge "this was a pitfall" without a
  model call per event. The rule stays the self-report channel.
- Inbox: gitignored `.agents/retro/inbox/` at the main checkout, resolved
  via `git rev-parse --git-common-dir`, so worktree writes survive teardown
  and stay inside sandbox write roots (user).
- Retro output: clustered report split project vs harness (F-004
  discriminator); concrete proposed edits, local ones applied only on the
  user's yes; upstream-skill fixes drafted as issue text the user files;
  consumed raw entries fold into the ledger (user).
- Seed: retro v1 imports `.agents/handover_dogfood_findings.md`
  (F-001..F-012) as inbox entries and retires the handwritten file; the
  first retro run over that seed is the acceptance test (user).
- Pruning: retro proposes additions **and** deletions — instructions the
  evidence contradicts or no entry has touched — each with its rationale
  (user).
- Trigger: `/hex-retro` by hand, and callable from a meta-orchestrator.
  The goal is recursive self-improvement: long loops alternate work phases
  with retro phases that improve the AI config or the project, then
  continue (user).
- Loop placement: `hex-loop` goal files declare retro checkpoints between
  milestones, so findings improve the next phase (user).
- Loop gate: unattended retro commits its edits on the loop's branch like
  any other work; they pass normal review, and the human gate moves to the
  PR merge (`hex-finalize`: the merge stays the human's). Upstream-skill
  fixes found outside arcana queue as issue drafts. Isolation is free: a
  running loop executes the *installed* skills (`~/.claude/skills/…`), so an
  edit to `hex/` source cannot alter the running loop until published and
  reinstalled (user).
- Finding sizes (user): **small** (a few lines in a skill or project config)
  — retro edits and commits on the loop branch itself, reviewed by the
  loop's normal review pass. **Large** (multi-file or design open) — runs
  in-loop (`/hex-plan` → `/hex-execute`, counted as one I8 refinement
  cycle) only when it sits inside the goal's scope *and* carries big value
  for the goal's outcome; the loop records that reason in its commit.
  Otherwise deferred: retro writes a report that is itself a valid
  `/hex-plan` and `/hex-loop` source, so a dedicated improvement loop
  (`/hex-loop <retro report>`) picks it up later. **Upstream** (skill at
  fault, loop outside arcana) — issue draft, filed only under the loop's
  grants.
  Strongest counter, named once: "big value" is an unattended judgment and
  can drift a goal into harness work; the scope condition, the recorded
  reason, and the I8 cap bound it.

## Scope of change

Proposed surface for the plan (repo-root-relative; the plan decides final
names):

- `hex/hex-retro/` — new skill: consolidation (cluster, dedupe, split
  project vs harness, attribute to artifact+version, propose add/prune
  edits with rationale, gate per mode), transcript-mining for objective
  signals on Claude Code, seed import of the dogfood log, archive of
  consumed entries. Ships the entry writer script.
- New capture rule under `hex/` (sibling of `hex/hex-state.md`): on real
  friction, write one JSON entry to the inbox, temp-then-rename; registered
  in `hex/hex.toml` `[rules]`, skill in `[skills]`.
- `hex/hex-core/references/protocol.md` — one-line terminal-report nudge
  when the inbox holds entries past a threshold; relation to the Upkeep
  step's class-3 candidates.
- `hex/hex-loop/SKILL.md`, `hex/hex-loop/assets/goal-prompt.md` — retro
  checkpoints between milestones; the loop gate and finding-size routing
  above; the § The prompt source table gains a retro-report row.
- `hex/hex-init/` — gitignore line for `.agents/retro/`, a
  `hex.md › Pointers` row for the inbox.
- `hex/DESIGN.md` — new round recording these decisions.
- `.gitignore`, `hex/README.md`, `hex/CHANGELOG.md`,
  `.agents/handover_dogfood_findings.md` (import, then retire).

## Open questions

- [NEEDS CLARIFICATION: Entry schema — which fields?]
  Recommended: `ts`, `project`, `role`, `artifact` (grim ref + version or
  `project`), `kind` (slow | inconvenient | pitfall | defect), `severity`,
  `what`, `tell` (observable symptom), `proposed_change`, `evidence` —
  mirrors the F-entry shape that already works.
- [NEEDS CLARIFICATION: Reuse Claude Code `/insights` output for the
  objective channel instead of mining transcripts directly?]
  Recommended: mine directly — `/insights` has no stable machine-readable
  contract and no attribution field; revisit if one appears.
- [NEEDS CLARIFICATION: Does grim's hook artifact type have a date?]
  Recommended: not blocking — v1 ships without hooks; the hook channel is a
  follow-up plan.
- [NEEDS CLARIFICATION: Ledger committed or gitignored?]
  Recommended: committed (e.g. `.agents/retro/ledger.*`) while the raw
  inbox stays gitignored — small, derived, reviewable at the merge gate,
  and it survives machines and worktree teardown.
- [NEEDS CLARIFICATION: Promotion bar — the recurrence × cost threshold?]
  Recommended: start with cumulative wall time lost relative to the run
  (e.g. ≥ 10 % of a loop's wall time, or ≥ 3 occurrences across runs) and
  tune from the ledger itself.
- [NEEDS CLARIFICATION: Nudge threshold N?]
  Recommended: 5 entries or any `severity: high`.
- Rule context cost: the capture rule is always-on in every session — the
  plan must keep it to a few lines and measure it against
  `adr_0014_instruction_diet`.
- `hex-loop`'s 4,000-character `/goal` budget must still hold with retro
  checkpoints added.

## Verification

- `grim build hex/hex-retro`, `grim build` on the new rule and every
  changed hex skill; `task publish -- --dry-run` exits 0.
- Concurrency: N parallel writer invocations produce N intact, parseable
  entries; no lock is taken.
- Worktree survival: an entry written from inside a `.agents/worktrees/`
  worktree still exists after `git worktree remove --force`.
- Dogfood acceptance: `/hex-retro` over the imported F-001..F-012 seed
  yields a harness list covering all twelve, each with a concrete proposed
  edit, its rationale, and its owning artifact; at least one prune proposal
  is considered.
- Ledger: two retro runs over entries of the same recurring finding yield
  one ledger row with summed cost; a `fixed` row that recurs flips to
  `reopened`.
- Loop: a rendered `hex-loop` goal prompt carries the retro checkpoints and
  stays within 4,000 characters.

## Research

- `.agents/research/discuss-retro-recon.md` — codebase recon.
- `.agents/research/discuss-retro-priorart.md` — prior-art web scan.
- `.agents/research/discuss-retro-community.md` — practitioner practice;
  netresearch/retro-skill 7-way routing taxonomy, proposal cap 10.
- `.agents/research/discuss-retro-vendor.md` — vendor capture/gating; no
  product attributes friction to a skill+version, no upstream-author
  feedback channel exists anywhere.
- `.agents/research/discuss-retro-archaeology.md` — repo history of
  Upkeep / Memory / dogfood.
