# Research: OSS Projects with Strict Pre-Landing Git History Conventions

## Metadata

**Date:** 2026-08-29
**Domain:** devops
**Triggered by:** /hex-discuss "finalize phase"
**Expires:** 2027-02-28

## Direct Answer

Nine major OSS projects document explicit, written rules for what a
contribution's git history must look like before it lands (commit
granularity, message format, sign-off, rebase/squash policy, who rewrites
history and when). Ranked by richness of "finalize a branch/series before
landing" guidance specifically (not just message-format style guides):

1. **Linux kernel** — richest: a standalone maintainer-facing doc devoted
   entirely to rebase/merge policy, plus per-patch bisectability requirements.
2. **Rust (rustc-dev-guide)** — explicit no-merge-commits-except-bors rule,
   with timing rules for when to squash vs. keep incremental commits.
3. **Node.js** — most detailed landing mechanics: self-contained/bisectable
   commit rule, banned merge-button paths, required pre-land metadata.
4. **Chromium (Gerrit)** — amend-in-place revision model instead of new
   commits per round, enforced via Change-Id identity.
5. **Zephyr** — DCO-enforced sign-off + explicit "interactive-rebase to
   squash before submitting" instruction.
6. **Kubernetes** — squash-to-one-commit-before-merge rule with a named,
   narrow exception.
7. **Git (the project itself)** — richest on message-format micro-conventions,
   thinner on rebase/squash policy than kernel/Rust.
8. **PostgreSQL** — contrast case: history finalization happens off-platform
   (email + `git format-patch`/`git am`), not via long-lived PR branches.

curl was also checked; its `CONTRIBUTE.md` recommends squashing after review
but available evidence on its specifics is thin (see Sources — worth a
direct fetch in a depth lane, not confirmed rich enough to rank).

## Ranked Candidates

| Rank | Project | Governing document(s) | Regulates |
|---|---|---|---|
| 1 | Linux kernel | [submitting-patches.rst](https://docs.kernel.org/process/submitting-patches.html), [rebasing-and-merging](https://docs.kernel.org/maintainer/rebasing-and-merging.html) | Series shape (each patch must build/boot for bisectability), message format ("area: summary", imperative mood), Signed-off-by chain, explicit "reparenting" (rebase onto new base) vs. "history modification" (rewrite/reorder existing patches) distinction and who is allowed to do which |
| 2 | Rust | [rustc-dev-guide git.md](https://github.com/rust-lang/rustc-dev-guide/blob/main/src/git.md) | Rebase/squash policy (no merge commits except bors'), squash timing (incremental during review, squash only at the end or on reviewer request), `git rebase --autosquash` workflow, `--force-with-lease` + comment etiquette on rewrite |
| 3 | Node.js | [collaborator-guide.md](https://github.com/nodejs/node/blob/main/doc/contributing/collaborator-guide.md), [commit-queue.md](https://github.com/nodejs/node/blob/main/doc/contributing/commit-queue.md) | Squash-vs-multi-commit landing rule (commits must be self-contained/bisectable), explicit ban on GitHub's "Merge pull request" and "Squash and merge" buttons (pollutes title with PR#), required commit-message metadata (PR link, reviewer names) added before landing, who lands (collaborator via `git-node`, not the author) |
| 4 | Chromium | [commit_checklist.md](https://chromium.googlesource.com/chromium/src/+/refs/tags/80.0.3977.1/docs/commit_checklist.md), [CL footer syntax](https://www.chromium.org/developers/contributing-code/-bug-syntax/) | Message format + trailer/footer syntax (`Change-Id`, `Bug=`, `R=` — valid only in the last paragraph), amend-in-place revision model (Gerrit tracks a CL by Change-Id, so `git commit --amend` replaces rather than adds a commit), pre-upload checklist gate |
| 5 | Zephyr | [CONTRIBUTING.rst](https://github.com/zephyrproject-rtos/zephyr/blob/main/CONTRIBUTING.rst), [contributor guidelines](https://docs.zephyrproject.org/latest/contribute/guidelines.html) | DCO enforcement (commit rejected without `Signed-off-by`, added via `-s`), explicit instruction to interactive-rebase and squash "small, incomplete commits" before submitting, convention for flagging a rebase-only push in a PR comment |
| 6 | Kubernetes | [pull-requests.md](https://github.com/kubernetes/community/blob/master/contributors/guide/pull-requests.md) | Squash-to-one-commit-before-merge rule, with a named exception for independent layered changes (e.g. munger / apply / precommit-check as 3 commits), bot-automated squash path (`tide/merge-method-squash` label) vs. manual `git rebase -i` |
| 7 | Git (the project) | [Documentation/SubmittingPatches](https://git-scm.com/docs/SubmittingPatches) | Message format micro-conventions (50-char subject soft limit, `area: ` prefix, no capitalization/full-stop on subject, imperative mood body), `Signed-off-by:` trailer capitalization rule, multi-part series threaded as email replies |
| 8 | PostgreSQL | [Committing with Git](https://wiki.postgresql.org/wiki/Committing_with_Git), [Submitting a Patch](https://wiki.postgresql.org/wiki/Submitting_a_Patch) | Patch-by-email workflow via `git format-patch`/`git am` (no long-lived PR branch to "finalize" — the committer's own commit is the finalization step), separate "Commit Message Guidance" referenced for committers |

## Key Findings

1. Two distinct finalization models recur across all eight: **PR-branch
   squash/rebase-before-merge** (Kubernetes, Node.js, Zephyr, Rust) vs.
   **Gerrit-style amend-in-place single CL** (Chromium — and by the same
   Change-Id mechanism, other Gerrit-hosted projects such as OpenStack and
   Wikimedia, not independently verified here). PostgreSQL and the Linux
   kernel use a third model — email/`git am` — where there is no PR branch
   to finalize at all; the mailing-list patch *is* the artifact, and history
   shaping happens via `git format-patch`/interactive rebase before sending.
2. "Who rewrites history and when" is answered most explicitly by Rust (only
   bors writes merge commits; contributors rebase, never merge) and by the
   Linux kernel's reparenting/history-modification split (maintainers do
   reparenting during a release cycle; contributors do history modification
   before initial submission).
   [rustc-dev-guide git.md](https://github.com/rust-lang/rustc-dev-guide/blob/main/src/git.md),
   [rebasing-and-merging](https://docs.kernel.org/maintainer/rebasing-and-merging.html)
3. Several projects treat "one commit per PR" as a default with a named,
   narrow escape hatch for genuinely independent changes, rather than an
   unconditional rule — Kubernetes' "munger / apply / precommit-check" example
   and Node.js' "self-contained subsystem commits" clause both carve out the
   same shape of exception.
   [pull-requests.md](https://github.com/kubernetes/community/blob/master/contributors/guide/pull-requests.md),
   [collaborator-guide.md](https://github.com/nodejs/node/blob/main/doc/contributing/collaborator-guide.md)
4. Bisectability is the stated *reason*, not just a stylistic preference, in
   both the Linux kernel (git bisect during a patch-series split) and
   Node.js (self-contained commits "much easier when bisecting to find a
   breaking change") — the same justification independently reached in two
   otherwise very different landing models.
5. Node.js explicitly forbids GitHub's native merge UI because "Squash and
   merge" injects the PR number into the commit title — a concrete instance
   of a project overriding a platform default to protect its message-format
   convention.
   [collaborator-guide.md](https://github.com/nodejs/node/blob/main/doc/contributing/collaborator-guide.md)

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| https://docs.kernel.org/process/submitting-patches.html | Docs | current | Kernel patch series/message conventions |
| https://docs.kernel.org/maintainer/rebasing-and-merging.html | Docs | current | Kernel-specific reparenting vs. history-modification policy |
| https://github.com/rust-lang/rustc-dev-guide/blob/main/src/git.md | Docs (repo) | current | Rust bors/rebase/squash workflow |
| https://github.com/nodejs/node/blob/main/doc/contributing/collaborator-guide.md | Docs (repo) | current | Node.js landing rules, metadata, merge-button ban |
| https://github.com/nodejs/node/blob/main/doc/contributing/commit-queue.md | Docs (repo) | current | Node.js automated commit queue |
| https://chromium.googlesource.com/chromium/src/+/refs/tags/80.0.3977.1/docs/commit_checklist.md | Docs | current | Chromium pre-upload checklist |
| https://www.chromium.org/developers/contributing-code/-bug-syntax/ | Docs | current | Chromium CL footer/trailer syntax |
| https://github.com/zephyrproject-rtos/zephyr/blob/main/CONTRIBUTING.rst | Docs (repo) | current | Zephyr DCO + rebase/squash instructions |
| https://github.com/kubernetes/community/blob/master/contributors/guide/pull-requests.md | Docs (repo) | current | Kubernetes squash policy + exception |
| https://git-scm.com/docs/SubmittingPatches | Docs | current | Git project's own message-format conventions |
| https://wiki.postgresql.org/wiki/Committing_with_Git | Wiki | current | PostgreSQL committer workflow |
| https://wiki.postgresql.org/wiki/Submitting_a_Patch | Wiki | current | PostgreSQL email-based patch submission |
| https://github.com/curl/curl/blob/master/docs/CONTRIBUTE.md | Docs (repo) | current | curl squash recommendation — thin evidence, needs direct fetch for depth lane |
