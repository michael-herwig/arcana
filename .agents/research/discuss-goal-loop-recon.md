# Research: goal-loop codebase fit

## Metadata

**Date:** 2026-09-22
**Domain:** devops | cli
**Triggered by:** hex-discuss session on a possible new skill for autonomous
end-to-end goal execution by chaining hex modes (architect → plan → execute
→ review/fix → finalize), meta-orchestrator over sub-orchestrators — user's
hand-written prompts in `.tmp/examples/loops/*.md`
**Expires:** 2027-03-22

## Direct Answer

The gap is already named and speced: `.agents/adrs/adr_0007_milestone_driver.md`
(Status: Proposed, unaccepted, unimplemented) proposes a fifth orchestrator,
`/hex-milestone`, defined as exactly "an outer loop that invokes
`/hex-architect`, then `/hex-plan`, then `/hex-execute`, then `/hex-review`
as separate runs, N times, carrying a cursor between them" — and
`hex-core/references/config.md` explicitly states this capability is **not**
expressible as config (§ "What config cannot express: milestone autonomy",
`config.md:611-624`). A near-identical prior run (2026-07-22, "autonomous
spec-superiority program") is the ADR's own existence proof — it ran a
manual version of the exact loop the example prompts ask for, and is
recorded in `.agents/memory/hex.md` and
`~/.claude/projects/-home-mherwig-dev-arcana/memory/autonomous-spec-superiority-program.md`.

## 1. What hex already covers, per part of the example prompts

| Example-prompt element | Hex status | Evidence |
|---|---|---|
| Chaining architect→plan→execute→review→finalize across multiple invocations, cursor/resume | **Absent** (Proposed, unimplemented) | `adr_0007_milestone_driver.md` C-601–C-608; `config.md:611-624` "the outer autonomous loop across many hex invocations … is categorically a new orchestrator, not configuration" |
| Meta-orchestrator delegating to Opus sub-orchestrators, depth cap | **Partially** (worker/coordinator nesting exists at depth 1; the ADR proposes depth 3) | `protocol.md` Worker coordination, `DESIGN.md` coordinator rounds (17/19); adr_0007 C-603 "Depth is capped at three levels: milestone (L0) → issue sub-orchestrator (L1) → workers … L2. Nothing at L2 spawns further" — this is Proposed, not shipped |
| One approval gate, then full autonomy | **Already a contract, but per-run, not per-loop** | `protocol.md:108-129` "The meta-plan approval gate" — "Exactly one approval point, before any work starts… never asks mid-flow questions." Each of hex-plan/execute/review/architect has its own gate; adr_0007 C-608 proposes making sub-runs "pre-approved / non-interactive," carried by "the non-interactive flags DESIGN.md already keeps for override" — that override mechanism's shipped state was not independently verified in this pass |
| Post-run handoff naming a next command | **Already shipped** | `protocol.md:804-826` Handoff contract: "Every orchestrator run ends with its skill's handoff block… After emitting it, the orchestrator MAY ask one optional proceed question" and a `Next:` command line. This is a suggestion for a human to act on, not an automatic chain — nothing dispatches the next skill itself |
| Resume after interruption | **Shipped, at single-plan grain** | plan `Status:` column + `State:` values (`executing`/`done`/`landing`) in `.agents/memory/hex.md` entries throughout; adr_0002's WP Status/Depends-on reused verbatim. Milestone-grain resume (a cursor across *many* plans) is adr_0007 C-601's `## Cursor` block — Proposed only |
| Wake-up polling / pulling idle subagents every 5 min | **Absent as a hex contract**; grep for "wake-up", "idle subagent pull" in `protocol.md` returns nothing | `hex/hex-core/references/protocol.md` has `### Worker liveness` (heartbeat files, escalation ladder, `protocol.md:471-737`) but no user-facing "wake-up every 5 min" cadence; that vocabulary is the example prompts' own, not hex's |
| Review-fix loop caps (`max N turns` self-refinement) | **Already a contract, differently shaped** | `loop.md:100-115`, `config.md:69-70`: `limits.loop-rounds` is a **ceiling never a floor**, hard max 3 by default vocabulary, shipped default 1 (per `.agents/memory/hex.md › Preferences: loop rounds 1`); user's own memory note `review-round-cap-two` independently states Michael wants review loops capped at **2** rounds. Example prompts ask for "max 3," "max 5," "at most 2/3 times" — these numbers are ad hoc per invocation and one (5) exceeds the shipped hard ceiling of 3 |
| Deferral to a GitHub issue when a finding's fix exceeds a LOC budget, or "bugfix workflow" | **Absent from hex** — no hits for "bugfix workflow," "follow-up issue," or a LOC-budget deferral rule anywhere under `hex/` | `grep -rn "bugfix" hex/` and `grep -rn "follow-up issue" hex/` both empty. Hex's only deferral vocabulary is the Review-Fix Loop's own auto-defer-on-oscillation (`loop.md:89,97,102`) and the constitution/adversary "escalates to the user" language — never to a tracker |
| "If in serious doubt, spawn a subagent orchestrator … question, research, decision, all recorded. Only in hard circumstances defer to a GitHub issue" | **Absent** as a named hex contract | No hits for "GitHub issue" outside one unrelated hex-architect line (`hex/hex-architect/SKILL.md:41`, about not resolving GitHub issues/PRs itself, i.e. the opposite direction). `hex-discuss` has research lanes and a council pattern (`DESIGN.md` round 9/11) but that's pre-plan discussion, not a mid-run doubt-resolution primitive |
| Force-push, draft PR, deep-verify manual workflow dispatch, merge-ready gate | **Already a full contract, in `/hex-finalize`** | `hex-core/references/finalize.md` — act set, force-push (branch-scoped, lease-pinned), draft→ready flip (`finalize.md:104-105`), `workflow_dispatch` dispatch and gating (`finalize.md:345-427`), backup-ref armed/inert lifecycle |
| "hex never pushes" outside finalize | Already the constitution | `protocol.md:408`-equivalent restated in `DESIGN.md:165` and reused verbatim by adr_0007 C-605: "the milestone stops before the PR — the one place swarm-x differs from hex is removed" |

## 2. `hex/DESIGN.md` resolved decisions that would constrain a new skill

- **Thin dispatcher + per-tier phase files, contracts linked never copied.**
  "Considered and not deviated: thin dispatchers + per-tier phase…"
  (`DESIGN.md:2320`); every prior amendment round explicitly re-affirms
  "single-source rule … upheld" (`DESIGN.md:1085,1210,1270,1998,2210,2265`).
  A new skill must be `SKILL.md` + `classify.md` + `overlays.md` +
  `tier-*.md`, linking into `hex-core/references/*`, never restating.
- **Capability classes, never literal model names, in any shipped file.**
  Restated at nearly every DESIGN round (`DESIGN.md:599,678,1934,2143-2144,
  2215,2273`); adr_0007 C-603 names this explicitly for the milestone
  driver's per-issue sub-orchestrator ("a `deep-reasoning`-class
  coordinator; capability class, never a literal model").
- **Single meta-plan approval gate, before any work starts, never mid-flow
  questions** (`protocol.md:108-129`) — scoped to a **closed list** of
  exempted skills, each with its own named ground (`hex-init`, `hex-discuss`,
  `hex-finalize`); "a fourth member is added by amending this sentence,
  never by analogy" (`protocol.md:127-129`). A new autonomous-loop skill
  either fits inside this closed list (with its own argued exemption) or
  keeps exactly one gate per invocation — adr_0007's own answer is "one
  master-plan gate, then autonomy" (C-608), consistent with the rule, not
  an exemption.
- **`hex never pushes`**, amended in exactly one place
  (`/hex-finalize`'s scoped force-push, `DESIGN.md` round 10) — any new
  orchestrator stops before the PR, per adr_0007 C-605.
- **Client is the runtime; markdown only, no engine/scheduler/new file
  format** (`DESIGN.md:320-322`, restated by adr_0007's own Decision
  Drivers). A goal-loop skill cannot introduce a state machine outside the
  plan Status-block discipline.
- **Two-layer knowledge model**: project-specific facts belong in project
  context (CLAUDE.md/AGENTS.md), never duplicated into hex config or
  `hex.md`. Directly answers Q3 below.
- **Worker coordination's concurrency cap counts recursively across all
  live levels**, `min(8, max-workers)` (`config.md limits.max-workers`) —
  adr_0007 C-603 flags a **new** depth-3 nesting (milestone→issue→worker)
  that the existing cap's accounting has to be extended to cover; this is
  an open, unresolved constraint on any meta-orchestrator design, not
  something already solved.
- **Skills invoking other skills**: no other hex file does this today.
  `hex-review`'s "hand off to `/hex-execute` if the caller wants it
  applied" (`hex-review/overlays.md:85`) is a *textual* handoff, not an
  invocation. adr_0007 is the only place in the repo that proposes one hex
  skill programmatically driving another as a sub-run.

## 3. Where project/machine-specific rules belong

Confirmed against `hex-core/references/memory.md` and
`.agents/memory/hex.md`:

- `hex.md › Pointers` is **skill-managed**, holds only *locations*
  discovered from project context — never facts like "/tmp wiped hourly"
  (`DESIGN.md` Two-layer knowledge model, `.agents/memory/hex.md:6-26`
  shows only pointer rows: Verification, Plan/ADR conventions, Spec home,
  Product knowledge, Key rules, Worktrees, Discussions home, Constitution).
- `hex.md › Preferences` is **user-owned, written only by `/hex-init` with
  consent**, and is explicitly bounded to the **frozen `config.md` key
  vocabulary** (`DESIGN.md:371-379` round 6: "still one file, still no
  TOML… no schema" but keys are frozen, not arbitrary prose beyond the
  vocabulary). Current file (`.agents/memory/hex.md:27-35`) holds only
  Models, Cross-model adversary, Limits — no free-form project facts.
  "/tmp wiped hourly," "limit RAM for rust-analyzer," and "`task
  verify:mark` bypass hack" do not match any key in `config.md`'s frozen
  vocabulary (checked `config.md:32-93` Key vocabulary / Dotted keys) —
  they are **not** `hex.md › Preferences` material.
- The two-layer model's explicit rule: "Anything that is knowledge about
  the PROJECT … lives in project context — CLAUDE.md / AGENTS.md / project
  rules" (`DESIGN.md:35-39`). `/tmp` wipe cadence, RAM limits for
  rust-analyzer, and the `task verify:mark` bypass are all
  machine/repo-specific operational facts about *that* project (ocx /
  ocx-mirror), not about hex or arcana — they belong in **that target
  repo's own CLAUDE.md/AGENTS.md**, discovered and pointed at by
  `/hex-init`, exactly the pattern `resources.md`'s "per-ecosystem knob
  sheet" already generalizes for verification-command knowledge
  (`hex-core/references/resources.md`, cited in `hex-core/SKILL.md:38`).
- `hex-core/references/resources.md` — "the resource knob sheet — the
  measured resource profile, the heavy semaphore, the per-run scratch
  environment, the containment ladder, the per-ecosystem knob sheet,
  teardown" — is the closest existing hex mechanism to "limit RAM for
  rust-analyzer" and "/tmp is periodically wiped": it is explicitly the
  sole definition site, and "hex never defines how to verify a project"
  (`hex-core/SKILL.md:38`), i.e. such knobs are read from project context,
  never hardcoded in hex.

## 4. Prior autonomous/meta-orchestrated runs and failure modes

- **2026-07-22 "autonomous spec-superiority program"** — a full-autonomy
  run with almost identical constraints to the example prompts (do not
  prompt, meta-orchestrator forwards to subagents, edit only this repo,
  tier-high review/fix loop bounded ≤5 iterations, land locally never
  push). Recorded: `.agents/memory/hex.md` "AUTONOMOUS PROGRAM" entry
  (~line 526-573 in the truncated read) and
  `~/.claude/projects/-home-mherwig-dev-arcana/memory/autonomous-spec-superiority-program.md`.
  **Completed successfully**: 23 commits, 3 ADRs implemented + converged
  in 4 review rounds, codex adversary caught 2 real fail-closed gaps,
  landed locally (never pushed, per constraint). This run is also the
  literal author of `adr_0007_milestone_driver.md` — "This ADR was
  authored by exactly such a manual run, which is the existence proof of
  both the demand and the gap" (`adr_0007_milestone_driver.md:30-31`).
- **Sub-orchestrator idle/stuck failure mode**, dated 2026-09-06:
  `~/.claude/projects/.../memory/subagent-results-route-to-top-session.md`
  — "When a sub-orchestrator spawns its own workers with
  `run_in_background`, or resumes a finished worker via SendMessage, the
  worker's task-notification arrives in MY session, never in the
  sub-orchestrator's transcript. The sub-orchestrator then sleeps in wait
  loops forever." Cost ~2h across three exec runs; the fix (foreground
  spawning only, never background/resume) is the direct answer to the
  example prompts' "pull any subagent that goes idle without reporting" —
  the mechanism that causes stuck sub-orchestrators is a background/resume
  spawn pattern.
- **Review-round blowup failure mode**, dated 2026-09-06:
  `~/.claude/projects/.../memory/review-round-cap-two.md` — "Wave 0's
  review ran 5 rounds (~6h) because every fix pass on protocol.md prose
  spawned new findings." This directly contradicts example prompts asking
  for "max 5 turns" self-refinement (example `6.md`) — the recorded
  practical experience is that 5-round panels on prose contracts don't
  converge and Michael's fix was capping at 2, delta-only.
  `hex.md › Preferences` currently ships `loop rounds 1`.
- **tmpfs-full-blocks-bash-output** memory
  (`~/.claude/projects/.../memory/tmpfs-full-blocks-bash-output.md`,
  referenced from the above two) — directly on point for the example
  prompts' "/tmp wiped hourly" rule; independent evidence this is a real,
  previously-hit operational hazard, not hypothetical.
- **mutation-sweep-snapshot-hazard** memory — a different autonomous-run
  hazard (snapshot-restoring a file another agent concurrently edited)
  not directly named in the example prompts but adjacent to the
  "monitor RAM, don't let concurrent rust-analyzer / worktree ops abort
  WSL" concern.
- No discussion, plan, ADR, or memory file found describing a prior
  **rejected** or **abandoned** attempt at a goal-loop/milestone-driver
  skill — adr_0007 is Proposed, never actioned since 2026-07-22 (per
  `.agents/memory/hex.md`'s deferred-items list: "(c) adr_0007 milestone
  driver is Proposed — accept/reject" still outstanding as of the most
  recent memory entries read).

## negative:

- No hits anywhere in `hex/` for "meta orchestrator," "wake-up routine,"
  "bugfix workflow," "follow-up issue," or "GitHub issue" as a deferral
  target — none of these are hex vocabulary; they are entirely the user's
  own prompt-authoring convention, imported from the (unread in this pass)
  OCX-family projects the example prompts target.
- `config.md`'s "Reproducing a role/phase swarm as config" section
  (`config.md:547-624`) was checked in full for a milestone-adjacent key —
  none exists; the section's own final subsection is the pointer to
  adr_0007 as the acknowledged gap, so a "just add a config key" shape is
  explicitly foreclosed by the codebase's own reasoning, not merely
  unexplored.
- The Handoff contract's post-run "one optional proceed question"
  (`protocol.md:809-813`) is not a chaining mechanism — it is a
  human-facing offer, and nothing in the codebase auto-dispatches the
  named `Next:` command. A goal-loop skill that just relied on handoff
  blocks chaining themselves would be reading a capability into the
  contract that is not there.
- adr_0007's own Option B (extend `/hex-execute` with a `--milestone`
  mode) was already considered and rejected in the ADR itself, with
  stated reasons (re-scopes hex-execute's one-plan contract into
  many-plans, forces it to embed the other three skills, inverting
  composition direction) — evidence against the "extension of an existing
  hex skill" shape, from inside the codebase's own prior analysis.

## leads:

- **adr_0007 acceptance status** — the ADR is Proposed and unimplemented;
  whether this discussion converges on "implement adr_0007 as-is,"
  "implement a lighter version," or something else is itself the open
  decision — worth a direct compare between adr_0007's C-601–C-608 and the
  example prompts' actual asks (e.g. adr_0007 assumes **one active issue
  at a time**, no intra-milestone parallelism in v1; example prompts 4 and
  6 explicitly ask for parallel inner loops on file-disjoint subsets).
- **Concurrency-cap accounting at depth 3** — adr_0007 C-603 flags this as
  new/unresolved; a follow-up lane could check whether `protocol.md`'s
  current recursive `min(8, max-workers)` counting mechanism (as amended
  through DESIGN rounds 17/19, coordinator gate split) already generalizes
  to a third level or needs its own amendment.
- **Non-interactive gate answering** — adr_0007 C-608 asserts sub-runs are
  "pre-approved / non-interactive… carried by the non-interactive flags
  `DESIGN.md` already keeps for override," but this pass did not
  independently verify which flags exist today per orchestrator or
  whether they cover every gate question a chained run would hit — worth
  a dedicated check of each `tier-*.md`'s flag surface before assuming
  the override machinery is complete.
- **"Doubt escalates to GitHub issue" vs. hex's existing escalate-to-user
  vocabulary** — `loop.md`'s auto-defer-on-oscillation and the constitution
  gate's Request Changes both escalate to a human in the running session,
  never to an external tracker; a lane comparing this to adr_0007's silence
  on doubt-resolution (it has no analog to the example prompts' "spawn a
  subagent orchestrator to reach a decisive recommendation… defer into a
  GitHub issue") would surface a second, independent gap the ADR doesn't
  cover.
- **hex-discuss's council/research-lane pattern as the doubt-resolution
  primitive** — `DESIGN.md` rounds 9/11 describe a blind-council,
  synthesis-without-ranking research pattern already shipped in
  `hex-discuss`; unexplored in this pass whether that pattern is reusable
  as the "spawn a subagent orchestrator to reach a decisive
  recommendation by research" mechanism the example prompts ask for,
  rather than inventing a new one.
