# Research: Automating feature-branch finalization before merge

<!--
Technology-landscape research. Filename and location: this project's
documented research convention; `.agents/research/research_[topic].md`
if undocumented.
Owner: a researcher worker. Handoff to: /hex-architect, /hex-plan.

Purpose: persist landscape findings that inform ADRs, plans, and design
decisions. Findings decay - check the Expires date before trusting them.
-->

## Metadata

**Date:** 2026-08-29
**Domain:** devops
**Triggered by:** /hex-discuss "finalize phase"
**Expires:** 2027-02-28

## Direct Answer

Six mechanisms recur across tooling for turning a WIP branch into a mergeable
one, each automating a narrower slice than teams often assume:

1. **History curation** (fixup!/squash! + `rebase -i --autosquash`,
   `git-absorb`, stacked-diff tools) automates *reordering and merging*
   marked commits, but never automates the judgment of *which* commits should
   exist or what their final messages say — a human (or agent) still decides
   commit boundaries.
2. **Rebase-vs-merge at merge time** (GitHub's Merge/Squash/Rebase buttons)
   automates the mechanical history shape on the target branch, but each
   strategy has different, non-obvious side effects on authorship, commit
   SHAs, and signature validity — none is a strict superset of the others.
3. **Quality gating** (required status checks, rulesets, merge queues)
   automates *blocking* the merge on check results, but a `workflow_dispatch`
   -triggered workflow generally cannot be selected as a required check
   unless it has already reported a status on that branch — manual-trigger
   workflows and required-check gating are in tension by default.
4. **Draft→ready transitions** automate *review-request fan-out*
   (documented) and are commonly wired via `if:` conditions to also gate
   *CI execution* (community pattern, not a GitHub guarantee) — but GitHub's
   own docs describe only the review-request side.
5. **Force-push safety** is not automated by any of the above: rewriting
   history on an open PR does not delete review comments, but does detach
   them from the current diff ("commented on an outdated diff"), and can
   silently drop GPG/SSH signatures unless the rebase explicitly re-signs.
6. **AI-agent frameworks** (GitHub's Claude/Codex/Copilot cloud agents,
   OpenSpec, spec-kit-style pipelines, and community Claude Code skills) treat
   "finalize" as an explicit, separate pipeline stage — usually opening a PR
   in **draft** state by convention and gating archive/merge on CI plus an
   explicit readiness check — rather than inventing new Git mechanics beyond
   what's listed above.

## Technology Landscape

### Trending (gaining momentum)

| Tool/Pattern | Adoption Signal | Key Benefit | Relevance |
|--------------|------------------|-------------|-----------|
| GitHub merge queue (rulesets-based) | GitHub's own docs now steer teams toward repository rulesets over classic branch protection for this | Serializes merges, re-validates each PR against the *latest* target + queue-ahead PRs before landing | Automates the "still green after rebase" check that manual finalize steps often skip |
| `git-absorb` | Actively covered in 2026 dev blogs/HN threads as the automatic counterpart to `git commit --fixup` | Infers *which* prior commit a staged hunk belongs to, skipping manual `--fixup <sha>` lookup | Could automate part of "curate WIP into reviewable commits" without agent judgment about commit *boundaries* |
| Jujutsu (jj) w/ `jj arrange` (0.39, March 2026) | 27k+ GitHub stars, production use at Google (jj's creator's employer) | Native, safe history-rewrite UX (undo-able rebases/reorders) replacing `rebase -i` entirely | Relevant as a longer-horizon alternative substrate for "curate history" if the repo ever migrates off plain Git workflows |
| Stacked-diff PR tooling (Graphite, git-machete, Revset for jj) | Multiple maintained, VC-backed (Graphite) and independent (git-machete, Revset) tools targeting this specifically | Automates keeping a chain of dependent PRs in sync as lower PRs merge/rebase | Only relevant if the target workflow is stacked PRs rather than one branch → one PR |

### Established (proven, widely accepted)

| Tool/Pattern | Status | Notes |
|--------------|--------|-------|
| `fixup!`/`squash!` commit-message convention + `git rebase -i --autosquash` | Standard, built into Git since 1.7 (fixup) / documented widely since | Git auto-reorders todo list entries whose subject starts with `squash!`/`fixup!`/`amend!` and matches an earlier commit; changes their action from `pick` to `squash`/`fixup`/`fixup -C` |
| GitHub "Squash and merge" | Default recommendation for short-lived feature branches | Loses individual commit detail; risky if the branch keeps being reused after merge (later PRs can re-include already-squashed commits, per GitHub's own docs) |
| GitHub "Rebase and merge" | Mature, widely used for teams wanting linear history with per-commit detail preserved | **GitHub's rebase-and-merge always creates new commit SHAs and rewrites committer info**, unlike a local `git rebase` onto an unchanged ancestor, which normally preserves author/committer identity when no conflicts require edits |
| GitHub "Create a merge commit" | Default GitHub option | Full fidelity: every original commit preserved, explicit merge point; makes bisection/history noisier |
| Required status checks (branch protection) | Long-established | A check is only selectable as *required* once it has reported a result on that branch within the last 7 days — this is why ad-hoc/manual workflows are awkward to gate on (see below) |
| `gh pr ready` / `gh pr ready --undo` | Stable CLI since 2020 | Documented to trigger code-owner review requests on transition to ready; CI-triggering behavior is an Actions-side convention (`ready_for_review` event + `draft == false` guard), not a GitHub Docs guarantee |
| `gh pr merge --merge\|--squash\|--rebase [--auto] [--delete-branch]` | Stable, scriptable | Requires an explicit strategy flag for non-interactive use; `--auto` defers the actual merge until required checks pass, effectively self-gating |

### Emerging (early but promising)

| Tool/Pattern | Signal | Worth Watching Because |
|--------------|--------|-------------------------|
| Repository **rulesets** (vs. classic branch protection) | GitHub actively documents rulesets as the direction of travel, with layered/multiple rulesets and per-actor bypass | Finer-grained gating (e.g., different rules for agent-authored branches vs. human branches) becomes possible without one monolithic protection rule |
| `merge_group` event for merge-queue CI | Explicitly required by GitHub docs for queue-time re-validation; a common misconfiguration (missing this event) silently breaks required checks for queued PRs | If a finalize automation relies on a merge queue, this is a concrete gotcha to encode |
| jj-based stacked-PR review tools (Revset) that survive force-pushes without losing comments | New (2026), narrowly scoped to jj users | Suggests the "force-push loses review context" failure mode is being treated as fixable at the VCS/tooling layer, not just avoided by policy |

### Declining (losing mindshare)

| Tool/Pattern | Signal | Avoid Because |
|--------------|--------|-----------------|
| Manual, ad hoc `git rebase -i` history cleanup with hand-reordered TODO lists | Multiple 2026 blog posts frame this as the "old way" superseded by autosquash/git-absorb | Error-prone, non-reproducible, doesn't scale to agent-driven or high-frequency finalize steps |
| Classic branch protection rules (as opposed to rulesets) | GitHub's own docs and third-party guides now recommend rulesets first | Less granular; being positioned as the legacy path, though still fully supported |

## Design Patterns Worth Considering

- **Fixup-then-autosquash as a two-phase commit convention** — WIP commits
  never get hand-edited; instead new commits are tagged `fixup!`/`squash!`
  against an earlier target, and a single `git rebase -i --autosquash`
  (or `git rebase --autosquash` non-interactively with `GIT_SEQUENCE_EDITOR`
  set to a no-op) collapses them mechanically. Used broadly in PR workflows
  where reviewers want to see "what changed since last review" as discrete
  fixup pushes rather than amended force-pushes.
  [Andrew Lock: Smoother rebases with auto-squashing](https://andrewlock.net/smoother-rebases-with-auto-squashing-git-commits/)
- **Absorb-don't-target** — `git-absorb` inspects the staged diff, walks
  recent commits, and infers which one each hunk belongs to, generating the
  `fixup!` commits automatically instead of requiring the author to name a
  target SHA. Explicitly pitched as "`git commit --fixup`, but automatic."
  [git-absorb on Lobsters](https://lobste.rs/s/nprldj/git_absorb_git_commit_fixup_automatic)
- **Draft-PR-as-explicit-gate** — treat "draft" as the state machine's
  not-ready marker and wire CI (`ready_for_review` event + a
  `github.event.pull_request.draft == false` guard) so expensive checks don't
  run until a human or agent explicitly promotes the PR — used as a cost- and
  noise-control pattern, not just a review-request signal.
  [w3tutorials: trigger Actions on ready-for-review](https://www.w3tutorials.net/blog/only-run-actions-on-non-draft-pull-request/)
- **Merge-queue re-validation** — required checks are evaluated *again*
  against the queue's simulated merge state (base + already-queued PRs), not
  just the PR's own branch tip, catching the "passed in isolation, breaks
  combined" class of failure that a plain required-status-check setup misses.
  [GitHub Docs: managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
- **AI-agent draft-PR convention** — GitHub's own Claude/Codex/Copilot cloud
  agents open pull requests in **draft** state on task completion by default,
  positioning "finalize" as a human-in-the-loop promotion (draft → ready)
  rather than something the agent does unilaterally.
  [GitHub Blog: Claude and Codex in public preview](https://github.blog/changelog/2026-02-04-claude-and-codex-are-now-available-in-public-preview-on-github/)
- **Spec-driven git discipline gates** — OpenSpec's documented team workflow
  enforces preconditions at each pipeline stage (clean tree before propose,
  commit after apply/verify, target-branch CI green before archive), and
  requires the PR body to name-match the spec's change directory so an
  automated archive action can locate and close it out — an example of
  "finalize" gated on artifact/naming consistency, not just Git state.
  [OpenSpec: Team Workflow](https://openspec.dev/docs/team-workflow)

## Key Findings

1. Git's autosquash mechanism is purely mechanical: it matches a commit
   subject prefix (`squash!`, `fixup!`, `amend!`) plus the referenced
   commit's subject text, then reorders/relabels the interactive-rebase TODO
   list — it performs no semantic judgment about whether the grouping is
   correct. [r.va.gg: git "fixup!" commits](https://r.va.gg/git-fixup-commits.html)
2. GitHub's three merge-button strategies are not interchangeable on
   metadata: "Rebase and merge" **always** produces new commit SHAs and
   updated committer info on GitHub (unlike a conflict-free local
   `git rebase`, which preserves the original author/committer), while
   "Squash and merge" discards per-commit messages/authorship entirely, and
   "Create a merge commit" preserves everything but adds a merge node.
   [GitHub Docs: About merge methods](https://docs.github.com/articles/about-merge-methods-on-github)
3. A workflow can only be *selected* as a required status check once it has
   already run and reported on the target branch (or the PR) within the past
   7 days — a purely `workflow_dispatch`-triggered workflow that has never
   run on a given branch/PR combination will not appear as a selectable
   required check, which is a structural obstacle to gating merges on
   manually-triggered jobs without also giving them an automatic trigger.
   [GitHub Docs: Troubleshooting required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks)
4. Merge queues require workflows to explicitly listen for the `merge_group`
   event (in addition to `pull_request`) and to run against the
   `gh-readonly-queue/{base_branch}/...` ref; omitting this is a documented,
   common misconfiguration that causes queued PRs to hang or fail because no
   check ever reports for the queue merge ref.
   [Tenki: GitHub Merge Queue in 2026](https://tenki.cloud/blog/github-merge-queue-setup)
5. Force-pushing to a branch with an open PR does not delete existing review
   comments, but detaches them from the live diff — GitHub marks the prior
   review "commented on an outdated diff," and the comment remains reachable
   via the Files Changed/Commits tab filtered to the original commit; this is
   explicitly called out across multiple GitHub Community discussions as
   confusing-but-not-destructive.
   [GitHub Community #142466: Impact of force-pushing on existing PRs](https://github.com/orgs/community/discussions/142466)
6. GPG-signed commits are invalidated by rebase because the commit's parent
   pointer (part of the signed payload) changes; Git performs the rebase
   anyway without erroring, silently leaving the rewritten commits unsigned
   or with a now-invalid signature unless the rebase explicitly re-signs
   (`git rebase --exec 'git commit --amend --no-edit -S'`, or
   `commit.gpgsign=true` combined with a rebase that touches every commit).
   [rollen.io: Re-signing git commits](https://rollen.io/blog/resigning-git-commits/)
7. `gh pr ready` is documented by GitHub to trigger review requests from code
   owners on transition to ready-for-review; GitHub's docs stop there and do
   not describe CI-triggering as a guaranteed side effect — teams that want
   CI gated on draft status implement it themselves via the `ready_for_review`
   activity type plus an `if: github.event.pull_request.draft == false`
   condition, which is a workflow-authoring convention, not a platform
   guarantee.
   [GitHub Docs: Changing the stage of a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/changing-the-stage-of-a-pull-request)
8. `gh pr merge` requires an explicit `--merge`/`--squash`/`--rebase` flag to
   run non-interactively (unattended in a script/CI job); `--auto` defers
   the actual merge action until required checks pass rather than failing
   immediately, letting a finalize automation queue the merge before CI
   completes. [gh pr merge manual](https://cli.github.com/manual/gh_pr_merge)
9. GitHub's own cloud coding agents (Claude, Codex, Copilot) submit **draft**
   pull requests on task completion; promotion to ready-for-review is left
   as an explicit, separate step (human or `@mention`-triggered follow-up),
   which several sources describe as keeping "all agent output as draft,
   reviewable artifacts within your existing pull request workflow."
   [GitHub Blog: Pick your agent — Agent HQ](https://github.blog/news-insights/company-news/pick-your-agent-use-claude-and-codex-on-agent-hq/)
10. Community-built Claude Code skills for this exact step exist and scope
    themselves narrowly to the mechanical squash — validating a clean source
    branch, checking for uncommitted changes, confirming divergence from the
    target, then running a non-interactive squash-merge — explicitly framed
    as "clean WIP commits before a PR" / "prepare a branch for merge," not as
    a judgment call about commit content.
    [git-squash-merge skill](https://skills.rest/skill/git-squash-merge)

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| https://andrewlock.net/smoother-rebases-with-auto-squashing-git-commits/ | Blog | — | fixup!/squash! + autosquash mechanics and PR workflow use |
| https://r.va.gg/git-fixup-commits.html | Blog | — | How Git matches fixup!/squash! subjects to target commits |
| https://blog.gitbutler.com/git-autosquash/ | Blog | — | Autosquash walkthrough |
| https://lobste.rs/s/nprldj/git_absorb_git_commit_fixup_automatic | Discussion | — | git-absorb positioning vs. manual `--fixup` |
| https://github.com/VirtusLab/git-machete | Repo | — | Stacked-PR rebase/merge automation tool |
| https://www.kunalganglani.com/blog/jujutsu-jj-git-version-control | Blog | 2026 | jj adoption signal, Google production use |
| https://docs.jj-vcs.dev/latest/changelog/ | Docs | 2026 | `jj arrange` (0.39, March 2026) |
| https://revset.dev/ | Product site | 2026 | Stacked PRs for jj surviving force-pushes without comment loss |
| https://docs.github.com/articles/about-merge-methods-on-github | Docs | — | Authoritative semantics of merge/squash/rebase-and-merge |
| https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue | Docs | — | Merge queue mechanics, `merge_group` requirement |
| https://tenki.cloud/blog/github-merge-queue-setup | Blog | 2026 | Merge queue setup pitfalls, flaky required checks |
| https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks | Docs | — | Required-check selectability constraints (must have run on branch) |
| https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/changing-the-stage-of-a-pull-request | Docs | — | Draft→ready documented behavior (review requests) |
| https://www.w3tutorials.net/blog/only-run-actions-on-non-draft-pull-request/ | Blog | — | `ready_for_review` event + `draft == false` guard convention |
| https://cli.github.com/manual/gh_pr_ready | Docs | — | `gh pr ready` / `--undo` |
| https://cli.github.com/manual/gh_pr_merge | Docs | — | `gh pr merge` flags, `--auto`, non-interactive requirements |
| https://github.com/orgs/community/discussions/142466 | Discussion | — | Force-push effect on existing PR review comments |
| https://rollen.io/blog/resigning-git-commits/ | Blog | — | Rebase breaking GPG signatures; re-signing methods |
| https://gitlab.com/gitlab-org/gitlab/-/issues/241509 | Issue | — | Force-push context loss on merge requests (GitLab analog) |
| https://github.blog/changelog/2026-02-04-claude-and-codex-are-now-available-in-public-preview-on-github/ | Changelog | 2026-02-04 | GitHub cloud agents (Claude/Codex/Copilot) draft-PR convention |
| https://github.blog/news-insights/company-news/pick-your-agent-use-claude-and-codex-on-agent-hq/ | Blog | 2026 | Agent HQ multi-agent draft PR workflow |
| https://openspec.dev/docs/team-workflow | Docs | — | OpenSpec git discipline: branch/PR mapping, archive gating on naming match |
| https://skills.rest/skill/git-squash-merge | Skill listing | — | Community Claude Code skill scoping squash-merge narrowly |
