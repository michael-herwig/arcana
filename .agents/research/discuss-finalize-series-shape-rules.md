# Research: Rules Governing the Shape of a Final Commit Series Before Landing

## Metadata

**Date:** 2026-08-29
**Domain:** devops
**Triggered by:** /hex-discuss "finalize phase"
**Expires:** 2027-02-28

## Direct Answer

Six convention-heavy projects were checked against primary sources (Linux
kernel, Node.js, Kubernetes, Rust, Zephyr, curl). All six agree on three
things: (1) a commit's boundary is a *logical change*, not a diff-size or
file-count boundary; (2) fixup/WIP/review-response commits must never survive
into the landed series — they get folded away by rebase/squash before or at
merge; (3) commit messages must carry a fixed structural shape (subject
line format, body, trailer/sign-off lines) that is enforced, not advisory.
They genuinely conflict on the *default* commit count for a PR: Kubernetes
and Node.js both default to squash-to-one with a named exception for
independent layered changes; Rust and the Linux kernel treat the *series* of
independent commits as the normal unit and only squash review-fixup noise,
never the logical commits themselves; curl sits in between, recommending
squash-after-review-feedback but preserving "each fix in its own commit"
for genuinely separate fixes.

## Series Shape Rules by Project

| Project | Unit of one commit | When multiple commits are correct | Ordering rule | Must never land | Message requirements |
|---|---|---|---|---|---|
| **Linux kernel** | One logical change ("Separate each logical change into a separate patch") | Default — a series is the norm; a single patch covering unrelated concerns (e.g. bug fix + perf enhancement to one driver) must be split | Each patch must build and boot correctly on its own — stated bisectability requirement: "take special care to ensure that the kernel builds and runs properly after each patch in the series," because `git bisect` "can end up splitting your patch series at any point" | WIP markers, fixup commits, patch-revision responses inside the series (these belong only below the `---` separator, outside the commit) | `[PATCH n/N]` subject with subsystem prefix + summary phrase (≤70-75 chars, imperative mood, no filename, no reused phrase across the series), body explains the underlying problem, `Signed-off-by:` trailer chain, `---` separator before diff/comments |
| **Node.js** | A self-contained, independently-passing-tests commit | "If a pull request has more than one self-contained subsystem commit, a collaborator may land it as several commits" — explicit named exception to the squash default | Not separately specified beyond self-containment; commit-queue's `commit-queue-rebase` path requires "all commits are self-contained, meaning every commit should pass all tests" | GitHub's native "Create a merge commit" / "Squash and merge" / "Rebase and merge" buttons are banned outright (pollute title with PR#, lose co-author metadata, or can't add metadata); unlabeled multi-commit PRs default to squash | `PR-URL:` line (full GitHub URL), optional `Fixes:` / `Refs:`, one `Reviewed-By: Name <email>` line per reviewing collaborator, message must "conform to the commit message guidelines" |
| **Kubernetes** | One commit = one pull request, by default | Named exception: "independent changes layered to achieve a single goal" — worked example given is a code munger (commit 1), applying it (commit 2), adding a precommit check (commit 3) | Not separately specified — the layering example implies dependency order (munger before its application) | Not explicitly enumerated beyond the squash default itself; the rule frame is binary — "sausage" (bugfix-on-bugfix, review-response noise) gets squashed, "layers" (independent steps) do not | Not detailed in the fetched section beyond the squash/don't-squash framing itself |
| **Rust (rustc-dev-guide)** | Not commit-count-prescriptive — the rule is about merge topology, not commit count | Incremental commits are the default during review; squashing happens only via `@bors squash` at merge time or `git rebase -i` locally, and is a landing-time operation, not a per-commit content rule | "Merge commits in PRs are not accepted" — linear history only, enforced via `merge.ff only`; the stated reason is bisecting and historical clarity | Merge commits (structurally rejected — bors requires linear history); accidental remote-overwrite from a bare `git push` after rebase (must use `--force-with-lease`) | Not message-format-prescriptive in the fetched section — the guide's rules are entirely about merge/rebase mechanics, not message content |
| **Zephyr** | "Small, controlled changes" — one logical change per commit, framed as what "simplifies review, makes merging and rebasing easier, and keeps the change history clear and clean" | Reviewer-requested fixes are handled by interactive-rebasing the *specific* offending commit(s), not by adding new fixup commits on top | Not separately specified | An empty commit message body ("not permitted... even for trivial changes"); force-push after rebase is expected practice but flagged as disruptive to review tooling ("Forced pushes can cause unexpected behavior, such as not being able to use 'View Changes' buttons except for the last one") | `[area]: [summary]` title, one line, <72 chars, followed by a blank line; non-empty body mandatory; `Signed-off-by: Name <email>` matching the commit's `Author:` field exactly (DCO) |
| **curl** | "Each fix that corrects a problem should be in its own patch/commit with its own description" | Genuinely separate fixes stay separate; review-iteration noise gets squashed on request: "consider squashing the commits so that we can review the full updated version more easily" | Not separately specified | A single "huge patch" bundling multiple unrelated fixes (explicitly warned against — complicates selective application/cherry-picking) | `[area]: [short line]` first line, imperative present tense ("change" not "changed"/"changes"), lowercase start, no trailing period, ≤72-column body explaining *why*; keyword trailers (`Fixes`, `Bug: URL`, `Closes #1234`, `Ref: #1234`, `Follow-up to {shorthash}`, `Reviewed-by:`/`Approved-by:`/`Authored-by:`/`Tested-by:`) |

## Key Findings

1. **Universal agreement — commit boundary is semantic, not mechanical.**
   Every project defines "one commit" by logical/independent change, never
   by size: kernel ("separate each logical change"), curl ("each fix... in
   its own patch/commit"), Zephyr ("small, controlled changes"), Node.js
   ("self-contained... subsystem commit"), Kubernetes' "layers" exception,
   Rust's incremental-commit norm during review.
2. **Universal agreement — no noise commits in the landed series.** Kernel
   bans WIP/fixup/response commits inside the series (pushed below the `---`
   separator instead); Node.js's commit queue explicitly recognizes
   `fixup!` commits only as input to `--autosquash`, never as a landed
   state; Zephyr and curl both fold review-response commits back into the
   original via interactive rebase; Rust squashes at merge via `@bors
   squash`. The mechanism differs (email separator vs. autosquash vs. bors
   command vs. manual rebase) but the destination state — no fixups visible
   in history — is identical across all six.
3. **Universal agreement — message structure is enforced, not advisory,
   though the exact grammar differs.** All six mandate a structured subject
   line (kernel: `subsystem: summary phrase`; Node.js/curl/Zephyr:
   `area: summary`), and four of six (kernel, Node.js, Zephyr, curl) mandate
   specific trailer lines (`Signed-off-by:`, `PR-URL:`, `Reviewed-By:`,
   `Fixes:`/`Bug:`). Rust's guide, in the fetched section, is silent on
   message content — its rules are entirely about merge topology.
4. **Genuine conflict — default commit count per unit of review.**
   Kubernetes and Node.js both start from squash-to-one as the *default* and
   treat multi-commit as a named, narrower exception requiring the commits
   to be independently meaningful ("layers", "self-contained subsystem
   commits"). The Linux kernel and Rust invert this: a multi-commit series
   is the *unqualified norm* — Rust never squashes logical commits, only
   review-iteration noise; the kernel actively penalizes cramming unrelated
   changes into one patch. curl sits closest to the kernel/Rust pole
   (separate fixes stay separate commits) but explicitly recommends
   squashing away review-round noise the way Kubernetes/Node.js recommend
   squashing the whole PR.
5. **Genuine conflict — what triggers the squash decision.** Kubernetes'
   test is topological ("layers" vs. "sausage" — are the changes
   independently reviewable steps toward one goal, or incremental patches
   on the same target). Node.js's test is empirical (does each commit pass
   tests standalone — bisectability). Rust's test is temporal/procedural
   (squash is a merge-time bors action, not a property of the commits
   themselves). These are different axes, not just different wording of the
   same rule — a PR could pass Node.js's bisectability test while failing
   Kubernetes' topology test, or vice versa.
6. **Partial-evidence caveat.** Zephyr's top-level `CONTRIBUTING.rst` only
   summarizes; the "squash small, incomplete commits" instruction the
   discovery lane flagged was not found verbatim in either fetched source
   (`CONTRIBUTING.rst` or `contribute/guidelines.html`) — the closest
   attested text is "you can interactively rebase commit(s) to fix review
   issues," which supports the same practical outcome (no visible fixup
   commits) without the stronger "squash before submitting" phrasing.
   Rust's fetched `git.md` section similarly had no explicit statement of
   "what a landed commit series must contain" beyond the no-merge-commit
   rule — its message-format expectations, if any, live elsewhere in the
   dev guide and were not confirmed here.

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| https://docs.kernel.org/process/submitting-patches.html | Docs | current | Kernel patch-series shape, bisectability, message format |
| https://docs.kernel.org/maintainer/rebasing-and-merging.html | Docs | current | Kernel reparenting vs. history-modification distinction |
| https://github.com/nodejs/node/blob/main/doc/contributing/collaborator-guide.md | Docs (repo) | current | Node.js self-contained-commit rule, merge-button ban, landing metadata |
| https://github.com/nodejs/node/blob/main/doc/contributing/commit-queue.md | Docs (repo) | current | Node.js automated squash/rebase queue rules |
| https://github.com/kubernetes/community/blob/master/contributors/guide/pull-requests.md | Docs (repo) | current | Kubernetes squash-to-one rule + "layers" exception with worked example |
| https://github.com/rust-lang/rustc-dev-guide/blob/main/src/git.md | Docs (repo) | current | Rust no-merge-commit rule, bors squash, rebase --autosquash, force-with-lease |
| https://github.com/zephyrproject-rtos/zephyr/blob/main/CONTRIBUTING.rst | Docs (repo) | current | Zephyr summary — DCO only; squash instruction not found here |
| https://docs.zephyrproject.org/latest/contribute/guidelines.html | Docs | current | Zephyr full guidelines — message format, DCO, interactive-rebase-on-review-request |
| https://github.com/curl/curl/blob/master/docs/CONTRIBUTE.md | Docs (repo) | current | curl one-fix-per-commit rule, squash-on-review-request, message format |
