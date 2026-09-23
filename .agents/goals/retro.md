# Goal: "retro — agent friction capture and a retrospective skill"

Source: .agents/discussions/retro.md · Written: 2026-09-23 by /hex-loop

## Definition of done

- [x] "Hybrid capture: agent self-reports plus objective trajectory signals" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [x] "Capture reaches every subagent via a published rule; retro works without it" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [x] "Lock-free capture: one file per entry, temp-then-rename" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [x] "Entries written from a worktree survive its removal" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [x] "Every entry attributed to an artifact+version or the project" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [x] "Retro proposes; nothing auto-applied outside a gate" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [x] "Retro turns the dogfood seed into landed-change proposals" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [x] "Every proposed edit carries its rationale" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [x] "Findings valued over time in a retro-kept ledger (recurrence x cost)" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [x] "Retro feeds the Upkeep to hex.md Memory to /hex-init path" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [ ] PR merge-ready (DONE block only) — evidence: the PR URL, and the
  PR is not a draft.
- [ ] CI green per job (DONE block only) — evidence: every check run on
  the PR head SHA with its conclusion; every skipped job states its
  skip reason (its `if:` or path filter).
  A skip with no reason is not green.
- [ ] Deep verify passed (DONE block only) — evidence: the full documented verification result.

## Autonomy

- Prompting: never — no question waits for a human; a doubt runs
  § Issue resolution.
- Granted acts (authority: the pasted prompt): none
- Forbidden or narrowed acts: none

## Issue resolution

Every doubt — an ambiguous requirement, a design question, a failure
with an unclear cause — runs this protocol:

1. Delegate the research to a sub-orchestrator.
2. Record question → research → decision in this file or in the PR.
3. Defer to a GitHub issue only in hard cases — the research ends with no
   decision, or the decision needs an act outside the grants; the issue
   link is the recorded decision.
4. Every doubt not deferred ends in an action.
5. A pre-existing failure that blocks done is in scope and runs this
   protocol.
6. Findings outside this goal's scope become follow-up issues.
7. Secrets and credential-bearing logs are never written to any committed
   file, commit message, PR text, PR comment or review comment, or issue.
   Security findings are never filed as issues:
   this file records them by reference only — location and class, no
   secret value or exploit detail — and only the DONE block reports them
   in full.

## Loop shape

- Entry point: Run the /hex-plan skill on "retro — agent friction capture and a retrospective skill, per .agents/discussions/retro.md".
- Refinement rounds: 3 — counts outer cycles: each review ⇄ execute
  pass is one, and so is every failed repair or retry cycle — a local
  verify failure, an execute or finalize retry, a post-finalize CI fix ⇄
  re-finalize pass. Inner review-fix rounds do not count, and their limit
  is untouched.
  Past `3`, the DONE block reports every remaining criterion `not met`
  and the run stops.
- Ticks: /hex-loop commits nothing. The session creates or switches to
  the branch the pasted prompt's I9 names and commits this file first on
  it. A box is ticked only between hex-mode runs, never during one, and
  each tick is committed at once; every tick lands before the final
  /hex-finalize, none after it. The `(DONE block only)` criteria are
  evidenced only in the closing DONE block, never ticked.

## Rules

None.

## Emphasis

"The consume-to-fix leg is the bottleneck, not capture: retro is judged by findings turned into landed changes, not entries collected." · "The objective duration channel is load-bearing: recurring costs such as days of acceptance-test runs are invisible to per-agent self-report." · "The always-on capture rule stays a few lines; hex-loop's 4,000-character paste budget must still hold with retro checkpoints."

## Context

- Source discussion (decisions, scope of change, open questions, verification): `.agents/discussions/retro.md`
- Research: `.agents/research/discuss-retro-recon.md`, `.agents/research/discuss-retro-priorart.md`, `.agents/research/discuss-retro-community.md`, `.agents/research/discuss-retro-vendor.md`, `.agents/research/discuss-retro-archaeology.md`
- Seed corpus: `.agents/handover_dogfood_findings.md` (untracked; F-001..F-012)
- Constitution: `hex/DESIGN.md`

<!-- Run decision log (§ Issue resolution step 2) -->
- 2026-09-23 — Q: an untracked `State: active` discussion
  (`.agents/discussions/nox-hex-init-state-split.md`, last updated
  2026-09-06) arms the hex-state no-edit freeze repo-wide. Decision: parked
  it (the rule's documented release for a stale artifact); file stays
  untracked.
- 2026-09-23 — Q: trunk for `hex/retro`. Local `main` is one commit ahead of
  `origin/main` (`9299de8`, installs hex-loop into `.claude/skills/`).
  Decision: branch from local `main` so the run uses the installed hex-loop;
  the PR therefore carries that commit.
- 2026-09-23 — /hex-plan converged: `.agents/plans/plan_retro.md`
  (`eef94fb`, tier high, 6 WPs). `adr_0019_retro.md` stays Proposed —
  acceptance is the owner's. Plan narrows two ratified points (loop edits
  only inside this repo's skill/rule source dirs; inbox resolved via
  `git worktree list`) — narrowing, accepted. Hook channel follow-up lives
  in the grimoire repo (outside grants) → recorded as an issue on this
  repo at finalize.
- 2026-09-23 — /hex-review (`3caa292`): Needs Work, 0 Block / 3 High /
  7 Warn. Outer cycle 1 of 2: /hex-execute WP 7 applies the 3 High, the
  actionable Warns (incl. forgeable trusted cost via tracked state file,
  inbox-not-ignored refusal) and closes criterion j's quoted evidence.
  Deferred to issues: interactive-decline routing of project conventions
  (owner design call); byte digest for trusted cost.
- 2026-09-23 — /hex-review round 2 (`ae22e5e`): round-1 findings closed;
  delta Needs Work, 0 High / 2 Warn (submodule exit-128 trust; empty
  assignment secret leak, 78–100 % of probes) + 1 actionable Low. Outer
  cycle 2 of 2: one-line fixes applied — a secret leak is not left as a
  ceiling — then a delta-only re-validation (precedent: plan_hex_loop
  "2 review rounds + re-validation"). Remaining Lows deferred to an issue.
- 2026-09-23 — re-validation (`5f9e502`): round-2 findings closed in code;
  1 Warn — the deep-nested `.mine-state.json` selftest vector
  (`hex/hex-retro/scripts/retro.py:1466`) does not exercise the fix at
  `retro.py:296` (move the deep row under `files`). Fixing it needs a third
  review ⇄ execute pass; I8 cap (2) is spent → run stops per § Loop shape.
  Criteria a–j ticked on review evidence; PR / CI / deep verify not met.
- 2026-09-23 — owner (in session): raise Refinement rounds to 3; cycle 3
  applies the re-validation Warn (selftest vector under `files`) plus the
  #11 decision — declined proposals stay `deferred`, the ledger row stamps
  `declined_at`, and retro re-proposes only on occurrences after it — then
  /hex-finalize. PR body closes #11.
