# Research: Commit-Message Conventions and Changelog-Generation Frameworks (2025–2026 Landscape)

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

Survey of commit-message conventions and changelog-generation frameworks
current as of 2025–2026: Conventional Commits (+ semantic-release,
release-please, git-cliff, cocogitto, commitizen/commitlint), Changesets,
towncrier, Keep a Changelog (manual), and forge-native release notes
(GitHub, GitLab). No recommendation is made here — see per-option evidence
below, both for and against.

## Technology Landscape

### Trending (gaining momentum)

| Tool/Pattern | Adoption Signal | Key Benefit | Relevance |
|--------------|------------------|-------------|-----------|
| release-please | Google-maintained, PR-based release flow widely adopted 2024–2026 across Google OSS and beyond | Automated version calc + human review gate before publish | Middle ground between full automation and manual control |
| git-cliff | Active development, latest release Jan 2026, npm + cargo + PyPI distribution, GitHub/GitLab integration | Highly configurable regex/template-based changelog generation, works with or without strict Conventional Commits | Rust-based, works as a pure generator layered onto any history shape |
| Changesets | Standard in JS/TS monorepo tooling (Turborepo, many popular OSS libs) | Decouples "what changed" authoring from commit message discipline | Addresses the most-cited weakness of commit-driven changelogs: commit messages are a poor proxy for user-facing change descriptions |

### Established (proven, widely accepted)

| Tool/Pattern | Status | Notes |
|--------------|--------|-------|
| Conventional Commits spec | Standard, stable since ~2019 | `type(scope): description`; `feat`→minor, `fix`→patch, `BREAKING CHANGE`/`!`→major |
| semantic-release | Mature, widely used for single-package libraries | Fully automated: analyzes commits → determines bump → publishes → tags → writes changelog, on every merge to main, no human release step |
| commitlint + husky | Mature, standard enforcement pair in Node ecosystem | Git `commit-msg` hook rejects non-conforming messages at commit time |
| commitizen (cz-cli / Python commitizen) | Mature | Interactive prompt that constructs a conforming commit message, reduces guesswork on type/scope |
| Keep a Changelog (manual) | De facto standard *format* even when generation is automated | Human-curated `CHANGELOG.md` with Added/Changed/Fixed/etc. sections; many automated tools (including git-cliff) target this format as output |
| GitHub auto-generated release notes | Mature, built into github.com since 2021, still current in 2025–2026 docs | Operates on merged PR titles/labels via `.github/release.yml`, zero dependency on commit message format |

### Emerging (early but promising)

| Tool/Pattern | Signal | Worth Watching Because |
|--------------|--------|-------------------------|
| cocogitto | Active Rust project, positions itself as broader "GitOps toolbox" beyond just changelog generation (bump, hooks, compliance check on push) | Combines enforcement + versioning + changelog in one tool, rather than composing 3 separate tools (commitlint + semantic-release + git-cliff) |
| Hybrid "automate + human review" pattern | Cited across multiple 2025 sources as "best practice" | Splits the difference between full automation (semantic-release) and full manual curation (Keep a Changelog), addressed structurally by release-please's PR-gate and Changesets' PR-gate |

### Declining (losing mindshare)

| Tool/Pattern | Signal | Avoid Because |
|--------------|--------|-----------------|
| Fully manual changelog maintenance at scale | Multiple 2025 sources note it "becomes a bottleneck" as release cadence grows | Entries get skipped, changelog drifts from reality as team/repo scales — though still viable and low-overhead for small, infrequent-release repos |
| Mandatory strict Conventional Commits on every commit (as opposed to only gate/squash points) | Growing body of critical essays (2022–2026, see Key Findings) | Cited friction: wasted subject-line space, multi-scope commits, revert handling, categorization ambiguity, contributor barrier |

## Design Patterns Worth Considering

- **Commit-driven automation (semantic-release)** — every commit conforms
  to Conventional Commits; a tool parses `git log` since the last tag,
  infers the semver bump from the highest-severity commit type present,
  and publishes unattended. Used by: many single-package npm libraries.
  [semantic-release.org](https://semantic-release.org/foundation/how-it-works/)
- **PR-gated commit-driven automation (release-please)** — same commit
  parsing as semantic-release, but instead of auto-publishing, opens and
  continuously updates a "Release PR" that accumulates the pending
  changelog/version bump; merging that PR triggers the actual release.
  Used by: Google OSS projects and many others. [oleksiipopov.com](https://oleksiipopov.com/blog/npm-release-automation/)
- **Change-file / news-fragment authoring (Changesets, towncrier)** —
  decouples the changelog entry from the commit message entirely; a
  contributor adds a small file (a "changeset" or a numbered "news
  fragment") alongside their code change describing the user-facing
  effect and intended bump, which is collected and rendered at release
  time. Used by: Changesets in many JS/TS monorepos; towncrier by
  Twisted, pytest, pip, Buildbot, attrs. [changesets.org](https://changesets.org/), [towncrier docs](https://towncrier.readthedocs.io/en/stable/tutorial.html)
- **Forge-metadata-driven notes (GitHub `.github/release.yml`, GitLab
  label-based generators)** — ignores commit messages and git history
  shape entirely; categorizes *merged PRs/MRs* by label into changelog
  sections. Requires labeling discipline on PRs, not commits. [GitHub docs](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes)
- **Pure changelog generation layered on existing history (git-cliff,
  cocogitto's `cog changelog`)** — a generator, not an enforcement tool;
  can run in strict mode (`require_conventional = true`, errors on any
  non-conforming commit) or lenient mode (`filter_unconventional =
  false` + catch-all parser groups unconventional commits into an
  "Other" bucket). Configurable per-repo without changing how anyone
  commits. [git-cliff.org](https://git-cliff.org/), [git-cliff configuration docs](https://git-cliff.org/docs/configuration/git/)

## Key Findings

1. **Every tool surveyed requires a *point of conformance*, but they
   differ on where it sits.** semantic-release/git-cliff (strict mode)
   /cocogitto need conformance on essentially every commit reachable in
   the history being scanned. release-please parses commits the same
   way but only cares about the commits since the last release tag.
   Changesets and towncrier require conformance not from commits but
   from a companion file added per change (a changeset or news
   fragment) — the commit message itself can be anything. GitHub/GitLab
   forge-native notes require conformance from *PR/MR titles and
   labels*, not from commit messages at all.
   [oleksiipopov.com](https://oleksiipopov.com/blog/npm-release-automation/), [changesets.org](https://changesets.org/), [towncrier tutorial](https://towncrier.readthedocs.io/en/stable/tutorial.html), [GitHub docs](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes)

2. **Squash-merge history interacts badly with strict Conventional
   Commits enforcement.** When a merge/pull request is squash-merged,
   the individual (possibly conforming) commits on the feature branch
   are collapsed into one commit that typically takes the PR title as
   its message — if the PR title isn't itself conformant, the squashed
   commit silently breaks the convention on the branch that actually
   matters (main). Sources explicitly recommend enforcing the
   convention *on the squash/merge commit message itself* rather than
   (or in addition to) on every feature-branch commit, since that
   squashed commit becomes "the single, well-formed record of each
   change." [DeployHQ conventional commits guide](https://www.deployhq.com/blog/conventional-commits-a-standardized-approach-to-commit-messages), [GitLab gitlab-ui issue #1562](https://gitlab.com/gitlab-org/gitlab-ui/-/issues/1562)

3. **git-cliff and cocogitto are format-agnostic generators, not
   history-shape-agnostic in outcome — they process whatever commits
   are reachable identically regardless of count, but the *quality* of
   the resulting changelog still depends on whether those commits are
   curated.** With few large curated commits (linear, squash-per-feature
   history), each commit maps roughly 1:1 to a changelog-worthy user
   change — clean output. With many small/WIP commits and no squashing,
   the raw commit-driven changelog gets noisy unless `filter_unconventional`
   or `commit_parsers` skip/group the noise (e.g. skip commits matching
   `^Merging`, `^wip`, `^typo`). git-cliff's `split_commits` option can
   even fan a single multi-line commit message into multiple synthetic
   changelog entries, which helps recover granularity in a "few large
   curated commits" repo when each commit's body lists multiple
   discrete changes. [git-cliff configuration docs](https://git-cliff.org/docs/configuration/git/), [git-cliff.org](https://git-cliff.org/)

4. **Maintenance cost for a small, single-maintainer repo differs
   sharply by tool.** semantic-release needs CI push access to the repo
   (tag + commit + changelog write-back), a designated release branch
   (fails with `ERELEASEBRANCHES` if absent), and coordination between
   CI job ordering, branch protection bypass for the release bot, and
   any commit-msg hooks — nontrivial config surface for a solo
   maintainer. release-please and Changesets both add a bot-maintained
   PR that must be reviewed/merged, which is lower CI-privilege risk
   (no direct push/tag from an unattended job) but adds a recurring PR
   the maintainer must attend to. git-cliff and cocogitto as *pure
   generators* (not full release automation) have the lowest ongoing
   cost — one config file, run on demand or in a release CI step, no
   standing bot permissions. Keep a Changelog (fully manual) has zero
   tooling cost but degrades as release cadence rises: "manual...is
   sustainable when your team is small and releases are infrequent...
   as your product scales... the manual process becomes a bottleneck."
   [semantic-release CI configuration](https://semantic-release.gitbook.io/semantic-release/usage/ci-configuration), [Depfu blog](https://depfu.com/blog/changelogs-to-write-or-to-generate)

5. **The strongest documented criticism of commit-message-driven
   changelogs (Conventional Commits + semantic-release/git-cliff strict
   mode) is an audience mismatch, not a tooling defect**: "commit
   messages and changelogs are meant for completely different
   audiences" — commit messages serve developers reading `git log`,
   changelogs serve end users deciding whether to upgrade. This is the
   structural argument for change-file approaches (Changesets,
   towncrier) and forge-metadata approaches (GitHub/GitLab), both of
   which let the contributor write end-user-facing prose separately
   from (and possibly more/less granular than) the commit itself, and
   is also the argument several critics raise against enforcing
   Conventional Commits repo-wide even where semantic parsing isn't
   used at all. [richvdh.org](https://richvdh.org/conventional-commits-considered-harmful.html), [Lobsters discussion](https://lobste.rs/s/szoe3m/conventional_commits_considered)

6. **Additional documented pitfalls of Conventional Commits specifically**:
   type/scope prefix consumes 20–30+ characters of the constrained
   50–72 char commit subject line, leaving little room for the actual
   description; commits frequently span multiple scopes, forcing an
   artificial choice between fragmenting the commit or violating the
   convention; categorizing a change (`fix` vs `chore` vs `refactor`)
   is often genuinely ambiguous and depends on the author's subjective
   read of severity; reverts are poorly handled by automated
   tooling (a reverted `feat` commit doesn't automatically un-appear
   from an already-generated changelog without extra logic); and
   several critics argue automating CI/release decisions off commit
   message text is inherently less reliable than automating off actual
   changed files/paths, since commit message accuracy is unenforced by
   anything except optional lint hooks that discipline can still route
   around (e.g., `--no-verify`, or a squash step that discards the
   individual messages). [richvdh.org](https://richvdh.org/conventional-commits-considered-harmful.html), [Sumner Evans — Stop Using Conventional Commits](https://sumnerevans.com/posts/software-engineering/stop-using-conventional-commits/), [Lobsters — Stop Using Conventional Commits](https://lobste.rs/s/oqlpna/stop_using_conventional_commits)

7. **GitHub and GitLab forge-native release notes require no commit
   convention at all** — GitHub's `.github/release.yml` categorizes
   *merged pull requests* by label (`changelog.categories[*].labels`,
   with `*` as catch-all, plus `changelog.exclude.labels` /
   `.exclude.authors`) and is driven entirely by PR titles/labels;
   commit message format inside the PR is irrelevant. This makes it the
   only surveyed option that works unmodified regardless of whether the
   underlying commit history is squashed, linear-curated, or noisy —
   the conformance burden shifts entirely to PR labeling discipline
   instead. GitLab has no single first-party equivalent as polished as
   GitHub's; the ecosystem instead has several third-party generators
   (e.g. gitlab-changelog-tool) that read MR titles and scoped labels
   (`type::feature`, `type::bugfix`, etc.) in a broadly similar pattern.
   [GitHub docs](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes), [gitlab-changelog-tool (PyPI)](https://pypi.org/project/gitlab-changelog-tool/1.0.1)

8. **The "hybrid" pattern is repeatedly cited in 2025 sources as the de
   facto best practice rather than any single tool**: automate
   generation from commits/PRs, then have a human review/edit the
   notable entries before publishing — which is structurally what
   release-please (PR gate) and Changesets (PR gate + free-text
   description per change) already enforce, versus semantic-release's
   fully unattended model which has no such gate by default. [Depfu blog](https://depfu.com/blog/changelogs-to-write-or-to-generate)

## Recommendation

Not provided — this research is explicitly neutral per its trigger (see
Metadata). No option is recommended over another here.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| [oleksiipopov.com/blog/npm-release-automation](https://oleksiipopov.com/blog/npm-release-automation/) | Blog | 2025/2026 | Direct semantic-release vs release-please vs Changesets comparison |
| [semantic-release.org/foundation/how-it-works](https://semantic-release.org/foundation/how-it-works/) | Docs | current | Canonical description of commit-driven automated release flow |
| [semantic-release.gitbook.io — CI Configuration](https://semantic-release.gitbook.io/semantic-release/usage/ci-configuration) | Docs | current | CI/push-access/branch requirements and failure modes |
| [git-cliff.org](https://git-cliff.org/) | Docs/Project site | 2026 (latest release Jan 2026) | git-cliff feature set, Keep a Changelog / GitHub / GitLab integration |
| [git-cliff.org/docs/configuration/git](https://git-cliff.org/docs/configuration/git/) | Docs | current | `split_commits`, `commit_parsers`, `filter_unconventional`, `require_conventional`, merge-commit skipping |
| [github.com/cocogitto/cocogitto](https://github.com/cocogitto/cocogitto) | Repo/Docs | current | cocogitto feature set (bump, commit compliance check, changelog) vs git-cliff |
| [docs.cocogitto.io/guide/commit](https://docs.cocogitto.io/guide/commit.html) | Docs | current | Conventional commit authoring/enforcement in cocogitto |
| [changesets.org](https://changesets.org/) | Docs/Project site | current | Changesets philosophy: change-file per PR, decoupled from commit messages |
| [brianschiller.com — Changesets vs Semantic Release](https://brianschiller.com/blog/2023/09/18/changesets-vs-semantic-release/) | Blog | 2023 (still cited 2025) | Core philosophy difference: intentional per-change description vs commit parsing |
| [towncrier.readthedocs.io — Tutorial](https://towncrier.readthedocs.io/en/stable/tutorial.html) | Docs | 25.8.0 (current) | News-fragment mechanics, used by Twisted/pytest/pip/Buildbot/attrs |
| [keepachangelog.com](https://keepachangelog.com/en/1.1.0/) | Spec/Docs | current | Keep a Changelog manual format spec |
| [depfu.com/blog/changelogs-to-write-or-to-generate](https://depfu.com/blog/changelogs-to-write-or-to-generate) | Blog | current | Manual-vs-automated tradeoffs, hybrid-approach argument |
| [docs.github.com — Automatically generated release notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes) | Docs | current | `.github/release.yml` config, PR-label-driven, commit-format-agnostic |
| [pypi.org/project/gitlab-changelog-tool](https://pypi.org/project/gitlab-changelog-tool/1.0.1) | Package/Docs | current | GitLab MR-label-driven changelog generation (third-party, no first-party equivalent) |
| [deployhq.com — Conventional Commits guide](https://www.deployhq.com/blog/conventional-commits-a-standardized-approach-to-commit-messages) | Blog | current | commitlint/husky enforcement, squash-merge interaction guidance |
| [gitlab.com/gitlab-org/gitlab-ui issue #1562](https://gitlab.com/gitlab-org/gitlab-ui/-/issues/1562) | Issue tracker | current | Real-world report of squash merge bypassing conventional commit convention |
| [richvdh.org — Conventional Commits, considered harmful](https://richvdh.org/conventional-commits-considered-harmful.html) | Blog | current | Primary criticism source: audience mismatch, terminology, space, reverts, multi-scope |
| [sumnerevans.com — Stop Using Conventional Commits](https://sumnerevans.com/posts/software-engineering/stop-using-conventional-commits/) | Blog | current | Additional criticism: categorization difficulty, contribution barrier |
| [lobste.rs/s/szoe3m — Conventional Commits considered harmful](https://lobste.rs/s/szoe3m/conventional_commits_considered) | Discussion | current | Community discussion/corroboration of criticism points |
| [lobste.rs/s/oqlpna — Stop Using Conventional Commits](https://lobste.rs/s/oqlpna/stop_using_conventional_commits) | Discussion | current | Community discussion/corroboration of criticism points |
