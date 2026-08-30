# Research: Incremental Code Review Mechanics in Mature Review Systems

## Metadata

Date: 2026-08-30
Expires: 2027-02-28

## Scope

Neutral evidence survey (no recommendation) covering: (1) Gerrit patchset
inter-diffs, (2) GitHub "changes since your last review", (3) Graphite /
stacked-diff per-commit scoping, (4) documented miss classes of delta-only
review and the backstops mature teams use.

## 1. Gerrit patchsets

- A Gerrit "Change" is identified by a stable `Change-Id`; every amended
  commit pushed under that Change-Id becomes a new numbered **patch set**
  (v1, v2, v3, ...). [Patch Sets — Gerrit docs](https://gerrit-review.googlesource.com/Documentation/concept-patch-sets.html)
- Reviewers scope re-review to the delta via **inter-patchset diffs**
  ("inter-diffs"): the UI's "Diff Against" dropdown lets a reviewer pick any
  prior patch set and see only what changed between that one and the
  current one, rather than re-reading the whole cumulative diff against the
  merge base. [Patch Sets — Gerrit docs](https://gerrit-review.googlesource.com/Documentation/concept-patch-sets.html)
- State recorded per patch set: the full commit snapshot (so any pair can be
  diffed later), plus an optional free-text "patch set description" (e.g.
  "Added more unit tests") distinct from the commit message, to orient a
  returning reviewer. [Patch Sets — Gerrit docs](https://gerrit-review.googlesource.com/Documentation/concept-patch-sets.html)
- Review labels/scores reset by default on every new patch set — Gerrit does
  not treat a prior "+2" as still valid once the diff changes, even if the
  net diff between old and new patch set is null (e.g. a trivial rebase).
  A `copyAllScoresOnTrivialRebase` project option exists specifically to
  preserve scores when the rebase introduces zero code delta.
  [Submitting a new patch set always resets review scores — repo-discuss](https://groups.google.com/g/repo-discuss/c/gQahYXAYxB8)
- Automated analyzer output ("robot comments") is a first-class structured
  comment type distinct from human comments, carrying a robot ID/run ID/URL,
  designed to be attached per patch set. [Robot Comments — Gerrit docs](https://gerrit.cloudera.org/Documentation/config-robot-comments.html)

## 2. GitHub "changes since your last review"

- Mechanic: when a reviewer returns to a PR after submitting a review,
  GitHub offers a view scoped to only what changed since that review,
  rather than the full base...head diff.
- **Failure mode — force-push/rebase**: this feature is keyed on **commit
  SHAs**, not content. A rebase (or squash) gives every commit a new SHA,
  so GitHub can no longer find the previously-reviewed commits in the new
  history and either shows nothing usable or throws "We went looking
  everywhere, but couldn't find those commits."
  [Allow changes since last review to work with rebased branches — GH community #141845](https://github.com/orgs/community/discussions/141845),
  [Improve workflow when force-pushing during code reviews — GH community #3478](https://github.com/orgs/community/discussions/3478)
- Root cause is explicit: GitHub's review-tracking anchors are commit
  hashes; a rebase severs that anchor even when the underlying code is
  byte-identical. The discussion's proposed fix is `git range-diff`, which
  compares commit *content* rather than hashes — not implemented by GitHub
  as of the discussion. [GH community #141845](https://github.com/orgs/community/discussions/141845)
- Current manual workarounds when this breaks: shift-click a commit range
  in the PR's commit list, hand-edit the PR URL to
  `pull/<n>/files/<sha>...HEAD`, or use local git tooling to find the first
  unreviewed commit. [GH community #141845](https://github.com/orgs/community/discussions/141845)
- A related, narrower per-file mechanic: pushing new commits only unchecks
  the "viewed" checkbox on files that actually changed, not the whole file
  list — and a file that changes again after being marked viewed gets a
  "Changed since last view" tag. This is unaffected by the rebase problem
  above since it doesn't need cross-push commit identity, only diff state
  within the current push. [Marking All Files in a GitHub PR as Viewed](https://ides.dev/notes/github-mark-all-files-viewed/)
- General community guidance converges on: force-pushing to a PR with an
  active reviewer is discouraged specifically because it destroys the
  "since last review" state and can detach existing inline comments from
  their original context. [Don't prematurely squash/rebase and force push your PRs — J. Tomlinson](https://jacobtomlinson.dev/posts/2022/dont-prematurely-squash/rebase-and-force-push-your-prs/)

## 3. Graphite / stacked-diff workflows

- Core model: a feature is decomposed into a stack of small, dependent
  branches/PRs, each reviewed (and often merged) independently, each
  layered on the previous one. [Stacked diffs — Graphite guide](https://graphite.com/guides/stacked-diffs)
- Per-commit/per-PR scoping is explicit in Graphite's own review guidance:
  "review a PR in a stack as though it was an independent change." If a PR
  can't be understood on its own merits, that's read as a signal the stack
  itself is decomposed wrong (not enough atomicity), not a cue to review
  the whole stack at once. [Best Practices For Reviewing Stacked PRs — Graphite docs](https://graphite.com/docs/best-practices-for-reviewing-stacks)
- Restacking mechanics: editing an earlier layer triggers an automatic
  cascade — Graphite rebases every dependent branch and force-pushes each
  one atomically (`gt modify` / `gt restack` / `gh stack sync`). Conflict
  resolutions are remembered across repeated rebases via integration with
  `git rerere`, so the same conflict isn't re-resolved by hand every
  restack. [How we built stacked PRs without a new git workflow — Mergify](https://mergify.com/blog/stacked-prs-without-a-new-git-workflow)
- Notable gap in Graphite's own documentation: no dedicated backstop is
  documented for cross-layer issues — no mention of a mandatory final
  full-stack review, a re-review pass after restack, or a whole-stack
  merge-time check. The stated mitigation is entirely upfront (better
  decomposition), not a closing verification gate.
  [Best Practices For Reviewing Stacked PRs — Graphite docs](https://graphite.com/docs/best-practices-for-reviewing-stacks)
- GitHub shipped a native stacked-PR feature (2026) with comparable
  per-layer review scoping (a "stack map" for navigating layers) plus two
  structural backstops: branch-protection rules apply against the final
  target branch (not each PR's immediate base), and CI runs each PR as if
  targeting main directly — so an intermediate PR can't merge without the
  full, final-state checks passing. A documented technical constraint:
  only standard merge commits work for intermediate PRs in the chain,
  because squash/rebase merges rewrite commit hashes and break the
  identity tracking between dependent branches (the same SHA-anchoring
  fragility as GitHub's non-stacked "since last review" feature, but
  fatal to the whole stack topology rather than just review continuity).
  [GitHub Targets Large Merge Problem with Stacked PRs — InfoQ](https://www.infoq.com/news/2026/04/github-stacked-prs/)

## 4. Documented miss classes of delta-only review, and backstops

- **Cross-commit / cross-delta interactions**: most tooling re-reviews the
  full base-to-head diff on each pass specifically *because* there is no
  reliable way to trace which commits a human already reviewed and compute
  a true incremental delta — the GitHub SHA-anchoring failure above is a
  concrete instance of this general problem. [SWE-Review paper, arXiv:2607.06065](https://arxiv.org/pdf/2607.06065)
- **Semantic conflicts** are the sharpest documented miss class: two
  changes that are each individually correct, reviewed and merged
  separately, combine to produce broken or unintended behavior with no
  textual (line-level) conflict at all — nothing in a diff-scoped review of
  either change in isolation would surface it. Research explicitly notes
  most semantic conflicts escape to end users despite code review and test
  suites. [Detecting Semantic Conflicts via Automated Behavior Change Detection](https://www.researchgate.net/publication/346591249_Detecting_Semantic_Conflicts_via_Automated_Behavior_Change_Detection),
  [Detecting Semantic Conflicts with Unit Tests, arXiv:2310.02395](https://arxiv.org/pdf/2310.02395)
- **Reviewer cognition under diff-scoping**: empirical research (Rigby &
  Bird; Bacchelli & Bird) found review effectiveness degrades with patch
  size, and reviewers already spend most of their cognitive budget on
  *comprehension* rather than defect-finding even at normal sizes. When
  pushed past their mental-model capacity, reviewers default to syntactic
  rather than semantic checking — i.e. delta-scoping that keeps each review
  small helps here, but only if the decomposition doesn't itself hide
  cross-cutting effects. [Expectations, Outcomes, and Challenges of Modern Code Review — Bacchelli](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/ICSE202013-codereview.pdf),
  [Modern Code Review: A Case Study at Google](https://dl.acm.org/doi/10.1145/3183519.3183525)
- **Backstops mature teams document**:
  - CI/merge gates that always evaluate the full, final-state diff/tree
    regardless of how review itself was scoped (GitHub's native stacked
    PRs run CI "as if targeting main directly" for every layer; Gerrit
    verification jobs re-run per patch set independent of human review
    state). [InfoQ — GitHub stacked PRs](https://www.infoq.com/news/2026/04/github-stacked-prs/)
  - Branch-protection evaluated against the final integration branch, not
    each intermediate PR's immediate base, closing the "reviewed the layer,
    not the landing" gap. [InfoQ — GitHub stacked PRs](https://www.infoq.com/news/2026/04/github-stacked-prs/)
  - Automated semantic-conflict/behavior-change detection as a distinct
    tooling category run at merge time, precisely because human review of
    each isolated delta does not reliably catch this class.
    [SAM / Detecting Semantic Conflicts with Unit Tests, arXiv:2310.02395](https://arxiv.org/pdf/2310.02395)
  - Widening the diff view to show surrounding (unchanged) lines during
    review, and explicit reviewer guidance to read all touched files when
    a PR is cross-cutting — a lighter, review-time mitigation rather than a
    merge-time gate. [Axolo — Common Code Review Mistakes](https://axolo.co/blog/p/common-code-review-mistakes-developers-make)
  - No source found that documents a *mandated final full re-review pass*
    as standard practice in any of the four systems studied — Graphite's
    own docs notably stop short of prescribing one (see §3). This looks
    like a documentation gap rather than confirmed absence of the practice
    in the wild.

## Negative (dead ends / contradicting evidence)

- Could not find Gerrit documentation describing exactly how (or whether)
  robot-comment state is explicitly "carried forward" or diffed across
  patch sets as a first-class chain — only that robot comments exist as a
  structured type attachable per patch set. Treat the "chain" framing as
  unconfirmed.
- Could not access primary documentation for Google's internal Critique
  tool (no public docs; only secondary references via *Software
  Engineering at Google* ch. 19 and tools inspired by it). Secondary
  sources claim Critique shows only new changes since last review by
  default with an option to see the full diff, but this is not confirmed
  against a primary source.
- Graphite's public docs contain no explicit statement on whether inline
  review comments survive a `gt restack` rebase (unlike Gerrit's explicit
  patch-set diffing or GitHub's explicit SHA-based failure mode) — this
  remains unconfirmed either way, not a documented gap.

## Leads (adjacent lanes, not pursued)

- Phabricator/Differential (Meta's originating stacked-diff tool) — likely
  has its own per-diff review-state mechanics and backstop conventions,
  not covered here.
- LLM-based / AI code review tools (SWE-Review, retrieval-augmented review)
  as a distinct emerging backstop for cross-delta and semantic-conflict
  misses — touched on only incidentally above.
- Chromium's CQ (Commit Queue) and OpenStack's Zuul as examples of
  verification-at-merge gates layered on top of Gerrit — not investigated.
