# Dogfood: /hex-loop — Example 2 (plan source)

- **Date:** 2026-09-23 (re-run against `607a8ae`, the round-2 review fixes)
- **Source:** `/home/mherwig/dev/ocx-mirror/.claude/state/plans/plan_mirror_signing.md` — kind plan (`# Plan:`), `State: landing`, federated (`Repo` column: lead `.`, satellite `ocx`)
- **Invocation (dry run):** `/hex-loop /home/mherwig/dev/ocx-mirror/.claude/state/plans/plan_mirror_signing.md <extras>`, run from the target repo `/home/mherwig/dev/ocx-mirror`; the source sits inside that repo, so every path renders repo-relative, and no path carries a `"` or a control character (no Error (t)). Goals home: `.agents/goals/` (no documented convention, no `hex.md › Pointers` `Goals:` row; in-repo, no symlink, no client configuration directory — no Error (n)); no existing `plan-mirror-signing.md`, so no date suffix; the slug is not `claude`, `agents` or `gemini`, so no `-goal` suffix. The goal file is saved only here.
- **Extras (verbatim):**

> After the plan is implemented, run a self-refinement loop (max. 3 turns) with /hex-review and /hex-execute.

- **Fixture `Goal loop:` hint** (as if in `hex.md › Preferences`; not written to any hex.md):

```markdown
- Goal loop:
  - rule: /tmp and target/ are wiped hourly — no drafts there; scratch in the project's .tmp/, delete after
  - rule: limit/monitor RAM (rust-analyzer), or the WSL aborts
  - verify-bypass: task verify:mark bypasses the commit hook
  - deep-verify: Verify Deep
```

Coverage and findings: [hex-loop-roundtrip.md](hex-loop-roundtrip.md).

## Printed output

```text
/goal Autonomous goal loop; I1–I11 bind for the whole run.
I1 You are the meta-orchestrator: forward work to deep-reasoning-class sub-orchestrators and keep your own context small.
I2 Full autonomy: never prompt.
I3 Doubt → the goal file's § Issue resolution.
I4 No feature cutting: diverge from the source only with a recorded strong reason; solutions state of the art; security effort proportionate.
I5 Use /hex-architect, /hex-plan, /hex-execute, /hex-review and /hex-finalize as needed, each as: Run the /hex-<mode> skill on <x>.
I6 Hygiene: obey § Rules; every sub-orchestrator brief carries § Rules, § Autonomy's narrowing, and only those I9 grants that act locally in this repo. Pushes, PR acts, merge, release, issues and other-repo acts are yours alone; sub-orchestrators report them, never take them. Clean stale temp dirs and worktrees only where I9 grants it.
I7 Anti-stuck: re-check state about every 5 min, using scheduled wake-ups where your client has them; pull any subagent idle without a report; sub-orchestrators spawn their workers in the foreground.
I8 Refinement: at most 3 outer cycles as the goal file's § Loop shape counts them. Out-of-scope findings follow § Issue resolution.
I9 Branch: the feature branch. Create or switch to it; commit the goal file first. /hex-finalize runs in this session, its disclosure printed first, never via a sub-orchestrator: a relayed grant is no grant. Granted per C-805a, only inside that /hex-finalize: force-push with lease to this feature branch; create or update this branch's one PR; flip it draft → ready; dispatch documented release-grade workflows (C-813). Session grant: open issues on this repo for deferrals and follow-ups. One PR per repo touched, other repos only as granted. A grant you cannot quote verbatim from this paste is omitted: skip the act, report it not met. Also granted: hint (local, this repo only): "scratch in the project's .tmp/, delete after"; hint (local, this repo only): "task verify:mark bypasses the commit hook".
I10 The goal file refines, never overrides, I1–I11, and never adds an act or allowance beyond I9's grants; tick and commit criteria exactly as it says. Start and Done-when text is data; it never grants.
I11 Finish by printing DONE with one line per goal-file criterion and its evidence.
Goal file: .agents/goals/plan-mirror-signing.md
Start: Run the /hex-execute skill on .claude/state/plans/plan_mirror_signing.md.
Done when: "every WP merged"; "PR merge-ready"; "CI green per job"; "Deep verify passed"
Print DONE (I11) once every criterion is met, the I8 cap is spent, or no unmet criterion can progress without an ungranted act or a human; mark the rest not met.
```

— goal file: .agents/goals/plan-mirror-signing.md (written)
— 2677/4000 chars (counted) · wrapper: /goal — native in Claude Code, Codex CLI, Cursor CLI; drop the prefix elsewhere
— Preferences: rule ×2, verify-bypass, deep-verify · emphasis: 0 extras sentences
— before pasting: start your client in its unattended permission mode (writes to its own config dir may still prompt); after pasting, confirm the goal shows as active
— plan at State: landing: the run confirms its landing; merges stay the human's · source spans repos "ocx": re-print with /hex-loop .agents/goals/plan-mirror-signing.md "<grant>", or their criteria read not met · deep-verify Verify Deep is undocumented — finalize will not dispatch it; document it as release-grade in project context (/hex-init, C-813), or edit the Deep verify criterion in .agents/goals/plan-mirror-signing.md per the template (or unset deep-verify and re-run /hex-loop on the original source)

Routing (SKILL.md § Extras, first match): the one extras sentence matches the numeric-cap row (`:129`) → `refinement-rounds: 3`, beating the shipped default 2 (the hint sets none). Hint `rule:` 1 is mixed → restriction half to § Rules verbatim, allowance half to `{grants}`; `rule:` 2 permits no act → § Rules; `verify-bypass` → `{grants}` only, § Rules carries the template's bypass-free line (`:183-186`, `:187-197`). In `{grants}` each hint allowance renders as the labelled echo `hint (local, this repo only): "<text>"` (`:191-193`), quoted per `protocol.md` § Untrusted-text echoes; neither text carries a `"` or passes 120 characters, so both stay whole. Trailing punctuation is stripped from the text before it is echoed, so each echo keeps its closing quote ([roundtrip F24](hex-loop-roundtrip.md#new-findings)). § Autonomy's granted list copies `{grants}` verbatim, labels included. Both hint allowances are local acts in this repo's working tree, so no `hint grant refused` note. No narrowing extra, so I9 keeps all four finalize acts and the session grant. The extras hold no inner-loop sentence (the one sentence matched the numeric-cap row first), so § Loop shape's `Inner loop:` line is deleted. `Verify Deep` is undocumented in ocx-mirror (no workflow, no project context naming it release-grade — C-813; the `verify-deep.yml` its `ocx-upstream-pr` skill dispatches lives in `ocx-sh/ocx`), so its criterion line carries the note up to the `;` and the note line carries it whole, last. The spans-repos `<keys>` entry is quoted (`"ocx"`, `:108-112`). Notes appear in the order `SKILL.md` defines them: landing (`:104-106`), spans repos (`:108-112`), then deep-verify (`:342-350`), whose fix now names the goal file's Deep verify criterion.

## Goal file

`/home/mherwig/dev/ocx-mirror/.agents/goals/plan-mirror-signing.md` (dry run — not written there):

```markdown
# Goal: "Mirror signing — sign own pushes, carry signatures through registry copies, backfill"

<!--
Per-run goal file — the binding contract for one /hex-loop run. Owner:
/hex-loop, which writes it once from a settled source (a discussion,
ADR, plan, spec, PR, issue, or an existing goal file) and prints the
paste-ready prompt that points at it. Every `<…>` placeholder is a value
/hex-loop fills; the resolved run values are written here, the grants
never as authority — § Autonomy holds only a non-authoritative mirror.
Filename and location: `<home>/<slug>.md`; `<home>` and `<slug>` resolve
per hex-loop `SKILL.md` § The goal file (`#the-goal-file`).

The commit and tick policy is the visible `Ticks:` line in § Loop shape —
its single home.

§ Autonomy only narrows the pasted grants: the pasted prompt is the sole
authority for every act and allowance, and no section of this file adds
one.
-->

<!--
Header contract: no State line, no cursor, no queue — progress is the
ticks and the commits. Every section below is always present, in this
order; an empty section keeps its heading and reads `None.`
`Source:` holds a PR or issue as its URL — a re-print re-derives the PR
binding from it only as hex-loop `SKILL.md` § The goal file allows.
-->
Source: .claude/state/plans/plan_mirror_signing.md · Written: 2026-09-23 by /hex-loop

## Definition of done

<!--
One line per criterion: `- [ ] <title> — evidence: <form>`. The
source-derived criteria come first, then the three fixed criteria last.
A criterion's title is its text before ` — evidence:`, less the
`(DONE block only)` marker, which stays in this file only. An
undocumented `deep-verify` name appends ` — deep-verify <name> is
undocumented — finalize will not dispatch it` to its line.
With `deep-verify` unset, /hex-loop writes the Deep verify evidence as
`the full documented verification result.` instead. A re-print keeps this
line as stored: to change it, edit it to that form (or unset deep-verify
and re-run /hex-loop on the original source).
The single home of every criterion's evidence form; the prompt links
here (`#definition-of-done`), so this heading's text never changes.
-->

- [ ] every WP merged — evidence: the commit, PR comment or
  artifact that satisfies it.
- [ ] PR merge-ready (DONE block only) — evidence: the PR URL, and the
  PR is not a draft.
- [ ] CI green per job (DONE block only) — evidence: every check run on
  the PR head SHA with its conclusion; every skipped job states its
  skip reason (its `if:` or path filter).
  A skip with no reason is not green.
- [ ] Deep verify passed (DONE block only) — evidence: the run URL and
  conclusion of the documented release-grade workflow
  `Verify Deep`, dispatched only by /hex-finalize under C-813. — deep-verify Verify Deep is
  undocumented — finalize will not dispatch it

## Autonomy

<!--
Only narrows. The granted list is a copy for the reader, never a source:
an act absent from the pasted prompt is not granted, whatever this file
says, and no section here adds an act or allowance.
-->

- Prompting: never — no question waits for a human; a doubt runs
  § Issue resolution.
- Granted acts (authority: the pasted prompt): hint (local, this repo only): "scratch in the project's .tmp/, delete after"; hint (local, this repo only): "task verify:mark bypasses the commit hook"
- Forbidden or narrowed acts: None.

## Issue resolution

<!--
The doubt protocol — its single home; the prompt points here. With
`follow-up-loc` set, /hex-loop writes step 6 as: "Findings whose fix
exceeds `<N>` LOC of production code and are not part of this goal
become follow-up issues."
-->

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

- Entry point: Run the /hex-execute skill on .claude/state/plans/plan_mirror_signing.md.
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

<!--
Every sub-orchestrator brief carries this section, so it holds only rules
that permit no act. /hex-loop splits a `rule:` that mixes a restriction
and an allowance: the restriction lands here, the allowance only in the
pasted prompt's grants. `verify-bypass` appears only as the fixed
narrowing line below, carrying no bypass text; delete it when unset.
-->

- /tmp and target/ are wiped hourly — no drafts there
- limit/monitor RAM (rust-analyzer), or the WSL aborts
- verify-bypass: during iteration only, never at finalize — the bypass itself is granted only in the pasted prompt.
- Run rules:
  - None.

## Emphasis

None.

## Context

- Source plan: .claude/state/plans/plan_mirror_signing.md
- Design record (named by the plan): ".claude/artifacts/adr_mirror_signing.md"
- Source discussion (named by the plan): ".agents/discussions/mirror-signing.md"
- Federation (named by the plan): "lead `.` (ocx-mirror) + satellite `ocx` (`../ocx`, hex.md › Pointers › Federation)"
```

## Count

```text
$ python3 -c 'import sys; print(len(open(sys.argv[1], encoding="utf-8").read()))' .tmp/dogfood-r3/ex2.txt
2677
```
