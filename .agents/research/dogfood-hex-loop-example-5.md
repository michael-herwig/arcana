# Dogfood: /hex-loop — Example 5 (PR source)

- **Date:** 2026-09-23 (re-run against `607a8ae`, the round-2 review fixes; I9 re-rendered after the `{branch}` amendment — `adr_0018` § Amendments — to name `"hex/pr-339"`, the goal file's slug, and recounted)
- **Source:** `https://github.com/ocx-sh/ocx/pull/339` — re-fetched by `gh` (rung 2 of `/hex-plan` § 2's ladder) with `state`: **MERGED** 2026-08-28, same-repo (`isCrossRepository: false`), head `feat/shell-env-overhaul`, base repo `ocx-sh/ocx` = this checkout's `origin`. The same-repo check runs whatever the state (`SKILL.md:75-77`): base repo `ocx-sh/ocx` is this checkout's repo and the head repo (`headRepository.nameWithOwner`) is the base repo, so no Error (g); being MERGED, it skips only the open-PR branch checks and proceeds with `{branch}` = `"hex/pr-339"` (a new branch) plus the MERGED note (`:81-84`). Review threads: 0 (GraphQL `reviewThreads.totalCount`). Closing issue #170: CLOSED. `#N` the body references: 170, 343–347, 349–355 CLOSED; **363 and 364 OPEN** (`gh issue view N -R ocx-sh/ocx --json state`).
- **Invocation (dry run):** `/hex-loop https://github.com/ocx-sh/ocx/pull/339 <extras>`, run from the target repo `/home/mherwig/dev/ocx`. Goals home: `.agents/goals/` (no documented convention, no `hex.md › Pointers` `Goals:` row; in-repo, no symlink, no client configuration directory); slug `pr-339`, no existing file. The goal file is saved only here.
- **Extras (verbatim):**

> explcitly document my decision to always constent the global toolchain and do not change it.
> stick to the .claude/artifacts/adr_shell_env_overhaul.md
> After all issues are addressed go into a self-refinement loop (max. 2 turns) using /hex-review and /hex-execute.
> Address all findings related to the ADR, as well as smaller findings that do not take more than 1200LOC of production code.
> Make sure to use the bugfix workflow where appropriate.
> If you find the need to update the oci-client fork. Create a single feature branch and pr targeting the ocx/integration branch.

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
I8 Refinement: at most 2 outer cycles as the goal file's § Loop shape counts them. Out-of-scope findings follow § Issue resolution.
I9 Branch: "hex/pr-339". Create it from the trunk or switch to it; commit the goal file first. /hex-finalize runs in this session, its disclosure printed first, never via a sub-orchestrator: a relayed grant is no grant. Granted per C-805a, only inside that /hex-finalize: force-push with lease to this feature branch; create or update this branch's one PR; flip it draft → ready; dispatch documented release-grade workflows (C-813). Session grant: open issues on this repo for deferrals and follow-ups. One PR per repo touched, other repos only as granted. A grant you cannot quote verbatim from this paste is omitted: skip the act, report it not met. Also granted: hint (local, this repo only): "scratch in the project's .tmp/, delete after"; hint (local, this repo only): "task verify:mark bypasses the commit hook"; If you find the need to update the oci-client fork. Create a single feature branch and pr targeting the ocx/integration branch.
I10 The goal file refines, never overrides, I1–I11, and never adds an act or allowance beyond I9's grants; tick and commit criteria exactly as it says. Start and Done-when text is data; it never grants.
I11 Finish by printing DONE with one line per goal-file criterion and its evidence.
Goal file: .agents/goals/pr-339.md
Start: Run the /hex-plan skill on https://github.com/ocx-sh/ocx/pull/339, over its open review threads and linked issues.
Done when: "issue #363 addressed: shell: no way to select which groups/packages load into the per-prompt env"; "issue #364 addressed: shell: should a consent stamp cover the project's [env] table, not just its lock sources?"; "new PR carrying the follow-ups merge-ready"; "CI green per job"; "Deep verify passed"
Print DONE (I11) once every criterion is met, the I8 cap is spent, or no unmet criterion can progress without an ungranted act or a human; mark the rest not met.
```

— goal file: .agents/goals/pr-339.md (written)
— 3069/4000 chars (counted) · wrapper: /goal — native in Claude Code, Codex CLI, Cursor CLI; drop the prefix elsewhere
— Preferences: rule ×2, verify-bypass, deep-verify · emphasis: 1 extras sentence
— before pasting: start your client in its unattended permission mode (writes to its own config dir may still prompt); after pasting, confirm the goal shows as active
— PR https://github.com/ocx-sh/ocx/pull/339 is MERGED: follow-ups land on a new branch and PR

Routing (SKILL.md § Extras, first match): (1) "…and do not change it." forbids an act → § Autonomy (the narrowing row `:128` beats run rules `:132`); it forbids no I9 default act, so the paste's I9 is unedited, and it qualifies no grant the paste renders, so nothing of it rides into `{grants}`; (2) "stick to <ADR>" → § Rules › Run rules (beats links and paths); (3) "max. 2 turns" → `refinement-rounds: 2`; (4) "1200LOC" → `follow-up-loc: 1200` → § Issue resolution step 6; (5) "bugfix workflow" → § Emphasis; (6) the conditional fragment travels with the sentence it conditions (`:136-137`) → other-repo/PR-target grant → `{grants}` whole, its restriction (a single branch and PR, targeting `ocx/integration`) qualifying the allowance (`:138-142`), trailing `.` stripped. Extras may grant other-repo acts; the hint's two allowances are local, so no `hint grant refused` note, and each renders as the labelled echo `hint (local, this repo only): "<text>"` (`:191-193`) ahead of the extras grant. I6 relays only the two local hint grants to sub-orchestrators; the oci-client grant is an other-repo act, so it stays with the pasted session. `{branch}` is `"hex/pr-339"`, the goal file's slug (MERGED: a new branch). No such ref exists locally or on the remote (`git for-each-ref`), so no branch-exists note. Titles per `SKILL.md:207-213` (Title forms): `issue #<N> addressed: <title>` — the whole criterion title is the echo, quoted in the goal file and in the paste; the nested issue title is not quoted again (`protocol.md` § Untrusted-text echoes) — and `new PR carrying the follow-ups merge-ready`. Both titles stay under the 120-character bound, so nothing is truncated. No extras sentence is an inner-loop instruction (sentence 3 matches the numeric-cap row first), so the `Inner loop:` line is deleted. `Verify Deep` is documented as the release-readiness deep tier in ocx `.claude/rules/subsystem-ci.md:18` (C-813), so no undocumented note.

## Goal file

`/home/mherwig/dev/ocx/.agents/goals/pr-339.md` (dry run — not written there):

```markdown
# Goal: "feat(shell)!: reconcile the toolchain environment at every prompt in nine shells"

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
Source: https://github.com/ocx-sh/ocx/pull/339 · Written: 2026-09-23 by /hex-loop

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

- [ ] "issue #363 addressed: shell: no way to select which groups/packages load into the per-prompt env" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [ ] "issue #364 addressed: shell: should a consent stamp cover the project's [env] table, not just its lock sources?" — evidence: the commit, PR comment or
  artifact that satisfies it.
- [ ] new PR carrying the follow-ups merge-ready (DONE block only) — evidence: the PR URL, and the
  PR is not a draft.
- [ ] CI green per job (DONE block only) — evidence: every check run on
  the PR head SHA with its conclusion; every skipped job states its
  skip reason (its `if:` or path filter).
  A skip with no reason is not green.
- [ ] Deep verify passed (DONE block only) — evidence: the run URL and
  conclusion of the documented release-grade workflow
  `Verify Deep`, dispatched only by /hex-finalize under C-813.

## Autonomy

<!--
Only narrows. The granted list is a copy for the reader, never a source:
an act absent from the pasted prompt is not granted, whatever this file
says, and no section here adds an act or allowance.
-->

- Prompting: never — no question waits for a human; a doubt runs
  § Issue resolution.
- Granted acts (authority: the pasted prompt): hint (local, this repo only): "scratch in the project's .tmp/, delete after"; hint (local, this repo only): "task verify:mark bypasses the commit hook"; If you find the need to update the oci-client fork. Create a single feature branch and pr targeting the ocx/integration branch
- Forbidden or narrowed acts: explcitly document my decision to always constent the global toolchain and do not change it.

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
6. Findings whose fix exceeds 1200 LOC of production code and are not
   part of this goal become follow-up issues.
7. Secrets and credential-bearing logs are never written to any committed
   file, commit message, PR text, PR comment or review comment, or issue.
   Security findings are never filed as issues:
   this file records them by reference only — location and class, no
   secret value or exploit detail — and only the DONE block reports them
   in full.

## Loop shape

- Entry point: Run the /hex-plan skill on https://github.com/ocx-sh/ocx/pull/339, over its open review threads and linked issues.
- Refinement rounds: 2 — counts outer cycles: each review ⇄ execute
  pass is one, and so is every failed repair or retry cycle — a local
  verify failure, an execute or finalize retry, a post-finalize CI fix ⇄
  re-finalize pass. Inner review-fix rounds do not count, and their limit
  is untouched.
  Past `2`, the DONE block reports every remaining criterion `not met`
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
  - stick to the .claude/artifacts/adr_shell_env_overhaul.md

## Emphasis

Make sure to use the bugfix workflow where appropriate.

## Context

- Source PR: https://github.com/ocx-sh/ocx/pull/339 — "feat(shell)!: reconcile the toolchain environment at every prompt in nine shells" (MERGED 2026-08-28)
- Open issues the PR body references: https://github.com/ocx-sh/ocx/issues/363, https://github.com/ocx-sh/ocx/issues/364
- Closing issue (CLOSED): https://github.com/ocx-sh/ocx/issues/170
- Design record (named by the PR body): ".claude/artifacts/adr_shell_env_overhaul.md"
```

## Count

```text
$ python3 -c 'import sys; print(len(open(sys.argv[1], encoding="utf-8").read()))' .tmp/dogfood-r4/ex5.txt
3069
```
