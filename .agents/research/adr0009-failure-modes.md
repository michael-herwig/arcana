# Research: Finalize-Phase Failure Modes & Recovery Patterns

## Metadata

**Date:** 2026-08-29
**Domain:** devops
**Triggered by:** /hex-architect .agents/discussions/finalize-phase.md
**Expires:** 2027-02-28

## Direct Answer

Finalize (rewrite → force-push → trigger CI → poll → draft→ready) has five
independent failure surfaces, and each has an established, narrow answer —
none require inventing new machinery. Interrupted rewrites recover via an
explicit pre-rewrite backup ref, not `ORIG_HEAD` or reflog alone, because
both are one-destructive-operation-fragile and a retried finalize runs
several. Force-push races need the *pinned* form of `--force-with-lease`
plus `--force-if-includes`, because the bare form has a documented
stale-lease hole that a background-fetching editor triggers in practice.
Check orchestration should use `gh run watch` (not a hand-rolled poll loop)
against a run ID captured directly from the trigger call, with
`gh run rerun --failed` reserved for genuine flakes — GitHub caps total
reruns per run at 50, so blind auto-retry is a real budget to protect.
Idempotent re-entry splits cleanly by step: rewrite is not blindly
re-runnable, push and the draft→ready flip are, workflow-trigger needs a
check-before-trigger guard — and the right progress ledger is the git
repo and PR state themselves, not a new state file, matching two
competing patterns seen in comparable tools (explicit journal vs.
derive-from-source-of-truth). Verification ordering is fixed by a single
fact only the Linux kernel's own docs state explicitly: a rewrite
invalidates testing already run against the pre-rewrite SHAs — so local
verification runs before the rewrite, the rewrite runs before any push,
and remote/CI verification runs exactly once, after push, against final
SHAs.

## 1. Interrupted Rewrite Recovery

| Mechanism | What it captures | Failure mode |
|---|---|---|
| `.git/rebase-merge/` (interactive) or `.git/rebase-apply/` (apply-based) | Live rebase session: remaining todo list, current patch, original branch name | Corruptible if the process is killed mid-write; a missing `head-name` file is a documented symptom |
| `ORIG_HEAD` | Pre-operation `HEAD`, set by rebase/reset/merge | Overwritten by the *next* destructive Git command — useless once a retry has run another rebase or reset |
| reflog | Every ref update, default expiry 90 days (reachable) / 30 days (unreachable) | Requires knowing which `HEAD@{N}` to reset to; not a fixed, nameable anchor |
| Explicit backup branch/ref (e.g. `git branch backup`) | A stable, human-nameable snapshot taken *before* the rewrite starts | None of the above's fragility — survives any number of subsequent destructive operations until deliberately deleted |

An active interactive rebase is recoverable with `git rebase --abort` while
`.git/rebase-merge` is intact; a killed or corrupted session (missing
`head-name`, stale lock) requires manually removing the `rebase-merge`/
`rebase-apply` directory and resetting to a known-good ref
([w3tutorials](https://www.w3tutorials.net/blog/how-to-fix-corrupted-interactive-rebase/),
[git-rebase docs](https://git-scm.com/docs/git-rebase/2.24.0)). `ORIG_HEAD`
is the documented first line of defense — "if no other major Git commands
have executed since the rebase began" — but that caveat is exactly the
failure case a *retried* finalize run creates: a second rebase attempt after
an interrupted first one overwrites `ORIG_HEAD` with the second attempt's
pre-state, silently discarding the anchor to the true original
([sqlpey](https://sqlpey.com/git/git-rebase-undo-recovery/)).

`git filter-repo` — the modern history-rewrite tool — takes this
fragility seriously enough to change its own safety posture: it refuses to
run on a repo that isn't a fresh clone specifically because it does *not*
provide a reliable built-in recovery mechanism, unlike `filter-branch`'s
`refs/original/` namespace, which the maintainer notes "does not provide a
user-friendly recovery mechanism" either
([git-filter-repo README](https://github.com/newren/git-filter-repo)).
That is direct precedent for finalize: don't rely on the rewrite tool's own
undo story.

**Verdict:** an explicit, named backup ref taken before any rewrite step —
the discussion's own candidate, `backup/<branch>-pre-finalize` — is the only
mechanism in this table that survives a retry loop. It also has a second
job beyond recovery: it is the anchor for `git range-diff` continuity
review (§5, and the discussion's D2 finding). Keep it until the PR lands,
delete after.

## 2. Force-Push Races

`--force-with-lease` (bare) compares the remote branch's current tip
against the *local remote-tracking ref* (`refs/remotes/origin/<branch>`)
cached at the last fetch — if they match, the push proceeds
([Atlassian](https://www.atlassian.com/blog/it-teams/force-with-lease)).
The documented hole: a **background fetch** — an IDE or editor that
periodically fetches on its own — updates that cached tracking ref without
merging anything into the local branch. The next `--force-with-lease` then
compares against the *freshly fetched* value, which matches the remote, and
the push sails through even though the local branch was never rebased onto
what actually landed there in between — silently discarding commits it
never saw
([Adam Johnson](https://adamj.eu/tech/2023/10/31/git-force-push-safely/)).

`--force-if-includes` (Git 2.30+) closes exactly this hole: it additionally
verifies, via reflog heuristics, that the remote-tracking ref's recorded
tip is actually an ancestor of the local branch's history before allowing
the push — if the local branch only ever *fetched* the remote change
without integrating it, the push is rejected
([Adam Johnson](https://adamj.eu/tech/2023/10/31/git-force-push-safely/)).

**Verdict:** use the *pinned* form,
`--force-with-lease=<branch>:<sha-fetched-at-finalize-start>`, combined with
`--force-if-includes`, not the bare flag alone. Pinning removes the
background-fetch race entirely (the comparison value is fixed at the moment
finalize began, not whatever the working tree's tracking ref says at push
time); `--force-if-includes` is defense in depth for the same class of
problem. A rejection here means a human pushed to the branch mid-finalize —
treat it as a hard stop requiring re-triage, never an automatic re-fetch-
and-retry (that would just re-open the same race one level up).

## 3. Check-Run Orchestration

`gh run watch` streams live status and exits automatically on completion —
GitHub's own guidance and community reports treat it as strictly better
than a hand-rolled poll loop, which risks exhausting API rate limits,
especially when multiple loops run in parallel
([anthropics/claude-code#65985](https://github.com/anthropics/claude-code/issues/65985)).
It is not unconditionally reliable, though: it has documented timeouts on
long-running or flaky connections (`HTTP 502` after an ~11s request in one
open issue) — a long or very-long CI suite needs a bounded retry around the
watch call itself, not an assumption that it always returns
([cli/cli#6560](https://github.com/cli/cli/issues/6560)).

For `workflow_dispatch` specifically, the historical pain point was
correlating the *triggering call* with the run it created — teams resorted
to passing a unique UUID input and then filtering `gh run list` by it. This
is now solved at the source: GitHub's workflow-dispatch API returns the run
ID directly, and current `gh` (2.87+) surfaces that ID/URL from
`gh workflow run` itself
([GitHub changelog](https://github.blog/changelog/2026-02-19-workflow-dispatch-api-now-returns-run-ids/)),
removing the need for a correlation-ID workaround on a current CLI. Poll
(or watch) that returned run ID directly rather than the older list-and-
guess pattern.

For flakes, `gh run rerun --failed` reruns only failed jobs, not the whole
run — but GitHub Actions caps total reruns (full + partial combined) at
**50 per workflow run**, a real, exhaustible budget: "if you've got two or
three flaky tests that each fail intermittently, you can burn through 50
reruns on a single PR in a bad week"
([oneuptime](https://oneuptime.com/blog/post/2026-01-25-github-actions-workflow-dispatch/view),
flaky-test tooling survey). An automatic re-run-on-failure policy inside
finalize needs a low, fixed retry ceiling (one or two attempts) rather than
looping to the platform limit.

**Expensive-suite strategy:** trigger once, at the end, against the final
rewritten SHA — not per intermediate push. This matches both the cost
argument here (reruns and CI minutes are a finite, shared budget) and the
ordering argument in §5 (checks against pre-rewrite SHAs are invalidated
work, per the kernel's own framing).

## 4. Idempotent Re-Entry

General pattern from durable-workflow literature: a resumable process
either (a) replays a journal of completed steps and continues from the
last recorded one, requiring each step to be idempotent or self-checking,
or (b) re-derives its progress from the state of the system it operates on,
with no separate journal at all
([arXiv:2608.03836](https://arxiv.org/html/2608.03836v1)). Both patterns
show up in comparable git/release tooling:

- **Journal pattern:** release-please-style release workflows are made
  explicitly idempotent per step — "bump" and "publish" tasks designed so
  re-running them on the same commit has no new effect and does not error
  ([projen#1033](https://github.com/projen/projen/pull/1033)).
- **Derive-from-source-of-truth pattern:** Graphite's own interruption
  recovery is `gt sync && gt restack && gt submit --stack` — it doesn't
  read a saved progress file, it re-inspects the current stack/PR state and
  continues from there
  (Graphite docs, merging-a-stack guide).

Mapped onto finalize's four remote-touching steps:

| Step | Safely re-runnable as-is? | Why |
|---|---|---|
| Rewrite (rebase + recompose commits) | **No** | Re-running a full interactive rewrite on top of an already-rewritten branch double-applies it. Must check first: does a backup ref already exist and does the current tip already look like a completed rewrite? |
| Force-push | **Yes** | Pushing identical content twice is a no-op after the first success; a lease rejection because the remote *already matches* is success, not failure |
| `workflow_dispatch` trigger | **No, needs a guard** | Each call queues a new run — re-entry must check for an existing queued/in-progress run against the exact target SHA before triggering again, or it burns CI minutes and rate limit on a duplicate |
| Draft→ready flip | **Yes** | Marking an already-ready PR ready again is a no-op on the forge side |

**Verdict:** git itself, plus the PR's current state (draft/ready, existing
backup ref, whether the branch tip matches the rewrite's expected shape),
is the natural progress ledger — this is the Graphite pattern, not the
journal pattern, and it fits hex's existing doctrine that state lives in
files/artifacts already on disk rather than a new bespoke store. Re-entry
should inspect: does `backup/<branch>-pre-finalize` exist (rewrite done or
in progress) → is the pushed tip's SHA the one last recorded as pushed
(push done) → is there a run already queued/running for that SHA (trigger
done) → is the PR already `ready` (flip done). No new state file is
justified by anything found here.

## 5. Verification Ordering

The only source in this research pass — across five failure-mode topics —
that states a *testing-invalidation* cost of rewriting explicitly, rather
than a reviewer-diff-visibility cost, is the Linux kernel's own maintainer
documentation:

> "Reparenting a patch series... changes the environment in which it was
> developed and, likely, invalidates much of the testing that was done. A
> reparented patch series should, as a general rule, be treated like new
> code and retested from the beginning."
> — [docs.kernel.org, Rebasing and merging](https://docs.kernel.org/maintainer/rebasing-and-merging.html)

That fixes the ordering unambiguously for a system with both local and
remote verification: **local verification runs first** (cheap, fast, safe
against work-in-progress SHAs that will be discarded anyway) → **rewrite
happens next** (rebase onto target, recompose commits) → **push** → **only
then does remote/CI verification run**, against the final SHAs that will
actually land. Triggering expensive remote checks *before* the rewrite
wastes the run entirely — those SHAs are gone the moment the rewrite
completes, and per the kernel's framing, the results wouldn't be trustworthy
evidence about the final tree even if they weren't.

One caveat this ordering doesn't fully resolve: rebasing *onto the target
branch* happens as part of the rewrite step, and target-branch state can
have moved since local verification ran, meaning local verification's
result technically predates the rebase it's meant to justify. The practical
middle ground — not found as a named pattern in any single source here, but
implied by combining the kernel's invalidation framing with the
squash-once-at-end model (this discussion's D2 finding) — is: run the full
local verification suite before the rebase-onto-target, then require a
*clean* rebase (no conflicts) as a fast, structural second check before
push; reserve the actual expensive suites for the single post-push remote
run, since that's the one whose result the PR will actually ship on.

## Key Findings

1. `ORIG_HEAD` and reflog are one-operation safety nets, not retry-loop-safe
   ones; an explicit named backup ref is the only mechanism here that
   survives a finalize run being killed and re-invoked.
   [sqlpey](https://sqlpey.com/git/git-rebase-undo-recovery/),
   [git-filter-repo README](https://github.com/newren/git-filter-repo)
2. Bare `--force-with-lease` has a real, documented hole — a background
   fetch from an editor/IDE — that a pinned lease value plus
   `--force-if-includes` closes; this is not a theoretical edge case, it's
   the primary reason Git 2.30 added the second flag.
   [Adam Johnson](https://adamj.eu/tech/2023/10/31/git-force-push-safely/)
3. `gh run watch` beats hand-rolled polling for both correctness (auto-exit
   on completion) and rate-limit safety, but is not unconditionally
   reliable on long/flaky connections — wrap it in a bounded retry, don't
   trust a single call.
   [cli/cli#6560](https://github.com/cli/cli/issues/6560),
   [anthropics/claude-code#65985](https://github.com/anthropics/claude-code/issues/65985)
4. GitHub Actions caps total reruns per workflow run at 50 — a shared,
   exhaustible budget across every flake on the branch, not a per-attempt
   allowance — so auto-retry-on-flake needs a small fixed ceiling, not an
   unbounded loop.
   [oneuptime](https://oneuptime.com/blog/post/2026-01-25-github-actions-workflow-dispatch/view)
5. Two competing idempotent-re-entry strategies exist in the wild (explicit
   step journal vs. derive-progress-from-current-repo/PR-state); the
   derive-from-source-of-truth pattern (Graphite's `sync && restack &&
   submit`) fits finalize better than a new journal file would, because git
   plus the PR already carry every signal re-entry needs.
   Graphite merging-a-stack guide,
   [arXiv:2608.03836](https://arxiv.org/html/2608.03836v1)
6. Only the Linux kernel's maintainer docs name invalidated testing as an
   explicit cost of rewriting — every other rewrite-etiquette source found
   across this and the sibling rewrite-timing research frames rewrite cost
   purely as reviewer-diff-visibility, not build/test validity. That's the
   fact that fixes finalize's verification ordering.
   [docs.kernel.org](https://docs.kernel.org/maintainer/rebasing-and-merging.html)

## Recommendation

Bake all five patterns into `/hex-finalize` as fixed mechanics, not
per-run choices: (1) take an explicit `backup/<branch>-pre-finalize` ref
before any rewrite step, keep it until the PR merges; (2) force-push with a
lease value pinned to the SHA fetched at finalize's start, plus
`--force-if-includes`, and treat a rejection as a hard stop, not a retry;
(3) trigger `workflow_dispatch` once against the final rewritten SHA,
capture the run ID directly from the trigger response, watch it via
`gh run watch` wrapped in a bounded retry, and cap flake reruns at a small
fixed number well under GitHub's 50-per-run ceiling; (4) make re-entry
inspect git and PR state directly (backup ref presence, pushed tip SHA,
queued-run-for-this-SHA, PR draft/ready) rather than maintaining a new
progress file — the repo and the PR already are the journal; (5) run local
verification before the rebase-onto-target, require a clean rebase as a
structural gate, and run the strictest remote/CI verification exactly once,
after push, against the SHAs that will actually ship. The strongest single
piece of evidence anchoring this whole ordering is the kernel's own
statement that reparenting "invalidates much of the testing that was
done" — it's the only source across this research pass that names a
testing cost (not just a review-visibility cost) for rewriting, and it is
what makes rewrite-before-push-before-remote-CI the only defensible order.

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| https://docs.kernel.org/maintainer/rebasing-and-merging.html | Docs | current | Testing-invalidation cost of reparenting; fixes verification ordering |
| https://sqlpey.com/git/git-rebase-undo-recovery/ | Blog | current | `ORIG_HEAD` recovery mechanics and its one-operation fragility |
| https://www.w3tutorials.net/blog/how-to-fix-corrupted-interactive-rebase/ | Blog | current | Recovering a corrupted/killed `.git/rebase-merge` session |
| https://github.com/newren/git-filter-repo | Repo/README | current | Why a rewrite tool refuses non-fresh clones; `refs/original/` recovery limits |
| https://www.atlassian.com/blog/it-teams/force-with-lease | Blog | current | `--force-with-lease` mechanics and remote-tracking-ref comparison |
| https://adamj.eu/tech/2023/10/31/git-force-push-safely/ | Blog | current | Stale-lease pitfall from background fetches; `--force-if-includes` fix |
| https://github.com/cli/cli/issues/6560 | Issue | 2022, open | `gh run watch` timeout/hang symptoms on long-running connections |
| https://github.com/anthropics/claude-code/issues/65985 | Issue | current | Why hand-rolled `gh run view` polling loops exhaust rate limits |
| https://github.blog/changelog/2026-02-19-workflow-dispatch-api-now-returns-run-ids/ | Changelog | 2026-02-19 | `workflow_dispatch` API/CLI now returns the created run's ID directly |
| https://oneuptime.com/blog/post/2026-01-25-github-actions-workflow-dispatch/view | Blog | 2026-01-25 | GitHub Actions' 50-rerun-per-run cap and its budget implications |
| https://arxiv.org/html/2608.03836v1 | Paper | current | Journal-replay vs. derive-from-state resume semantics in workflow engines |
| https://github.com/projen/projen/pull/1033 | PR | current | Making release-workflow steps explicitly idempotent (journal-adjacent pattern) |
| https://graphite.com/docs/merge-pull-requests | Docs | current | Graphite's `sync && restack && submit` interruption recovery (derive-from-state pattern) |
