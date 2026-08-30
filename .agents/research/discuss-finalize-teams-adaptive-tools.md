# Research: Preference-Adaptive Developer Tooling

<!--
Technology-landscape research. Discovery lane (breadth pass): candidates
and detection mechanisms with sources, not deep analysis.
Owner: hex researcher (sweep W1). Handoff to: depth-lane researchers.
-->

## Metadata

**Date:** 2026-08-29
**Domain:** devops
**Triggered by:** `/hex-discuss "finalize phase"`
**Expires:** 2027-02-28

## Direct Answer

Yes — several categories of developer tooling detect a team's existing
git/repo conventions instead of imposing their own, but the mechanisms
cluster into three tiers of strength: (1) **history/content analysis**
(pattern-match git log or file contents against known styles — Renovate,
Dependabot, release-please), (2) **API read of platform-native settings**
(pull an already-configured GitHub setting and translate it — Mergify), and
(3) **filesystem/directory-presence sniffing** (detect what's already on
disk and default to matching it — jj colocation, husky's non-destructive
hook install, gh CLI's PR-template lookup). Detection is overwhelmingly
**silent-by-default with an explicit override**, not interactive — no tool
found asks the user a question before deciding; all either apply the
detected convention automatically or fall back to a hardcoded default when
nothing is detected. The one clear failure mode found across the set:
detection silently *not firing* in the code path a user actually exercises
(gh CLI's PR template; see #10).

## Candidates and Mechanisms

### 1. Renovate — commit-message convention (semantic/conventional commits)

- **Detects:** whether the repo uses semantic/conventional commit messages,
  and which dialect (Angular-style conventional commits specifically).
- **Mechanism:** git-history analysis. Renovate's docs state detection
  inspects the last commits on the base branch, **ignoring merge commits**,
  using logic "inspired by" the `conventional-commits-detector` package.
  (Note: the docs page and a GitHub search summary disagree on window size —
  docs say 20, a discussion thread says 10; not resolved in this pass.)
- **Fallback:** repo's `semanticCommits` config stays `"auto"`; when no
  convention is detected, commits/PR titles are left unprefixed.
- **Asks or decides silently:** silently decides. `semanticCommits: "auto"`
  is the default — no prompt. A documented pain point: on repos with
  *inconsistent* semantic-commit usage, auto-detection flip-flops run to
  run; the fix offered in the issue thread is to pin an explicit
  `true`/`false` once, not to make detection itself interactive.
- **Sources:** [Renovate semantic-commits docs](https://docs.renovatebot.com/semantic-commits/), [flip-flop discussion #39444](https://github.com/renovatebot/renovate/discussions/39444), [auto-detection problem #8](https://github.com/renovatebot/presets/issues/8)

### 2. conventional-commits-detector — the library several of the above lean on

- **Detects:** which of 6 known commit-message conventions a repo's log
  matches: Angular, Atom, Ember, ESLint, jQuery, JSHint.
- **Mechanism:** pulls N recent commit messages via `git-raw-commits` and
  pattern-matches against each convention's signature. Exact matching logic
  isn't documented on the README; would need source-diving to go deeper.
- **Fallback:** returns no convention when nothing matches (last publish:
  6 years ago — effectively unmaintained, per the npm page).
- **Asks or decides silently:** it's a library, not a UX — silent by
  construction; callers decide whether/how to surface the result.
- **Sources:** [GitHub repo](https://github.com/conventional-changelog/conventional-commits-detector), [npm page](https://www.npmjs.com/package/conventional-commits-detector)

### 3. Dependabot — commit-message/PR-title prefix

- **Detects:** commit-message prefix preferences.
- **Mechanism:** undocumented in detail on GitHub's own docs beyond one
  line: "By default, Dependabot attempts to detect your commit message
  preferences and use similar patterns." No history-window or algorithm
  specifics published (unlike Renovate, which names its detection window
  and inspiration library).
- **Fallback:** presumably an unprefixed commit message when nothing is
  detected (not explicitly stated).
- **Asks or decides silently:** silently decides by default; an explicit
  `commit-message: { prefix, prefix-development }` block in
  `.github/dependabot.yml` overrides detection outright.
- **Sources:** [Customizing Dependabot PRs](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/customizing-dependabot-prs), [Dependabot options reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)

### 4. Mergify — branch protection / repository rulesets

- **Detects:** a repo's own GitHub branch-protection rules and rulesets
  (required-review counts, required status checks, etc.) on the PR's
  target branch.
- **Mechanism:** API read. Per-PR, Mergify reads the branch protection/
  ruleset settings GitHub already enforces and auto-translates each into an
  equivalent merge-queue condition — e.g. "require 1 approval" becomes
  `#approved-reviews-by >= 1`. This is the strongest "reads an existing
  platform-native convention and adapts to it" example found: it's not
  file-sniffing a Mergify-specific artifact, it's importing GitHub's own
  settings.
- **Fallback:** no rulesets configured → no conditions injected; queue
  rules apply exactly as authored in `.mergify.yml`.
- **Asks or decides silently:** fully automatic/silent. A
  `branch_protection_injection_mode` setting (`queue` default / `merge` /
  `none`) controls *when* the injected conditions are checked, not whether
  the user is asked — there is no interactive step in any mode.
- **Sources:** [GitHub rulesets compatibility](https://docs.mergify.com/merge-queue/github-rulesets/), [Mergify config file format](https://docs.mergify.com/configuration/file-format/)

### 5. Kodiak — contrast case (no detection found)

- Kodiak's `.kodiak.toml` (repo root or `.github/`) is entirely explicit
  config — no evidence of reading GitHub's branch-protection/ruleset state
  the way Mergify does. Included as a same-category contrast: two merge-
  queue tools, only one of which imports the platform's existing rules.
- **Source:** [Kodiak config reference](https://kodiakhq.com/docs/config-reference)

### 6. husky — preserves rather than infers

- **Detects/preserves:** hooks a developer already has in place.
- **Mechanism:** file/config sniffing at install time. Sets
  `core.hooksPath` to `.husky/`; documented as non-destructive toward
  existing hooks. v9+ dropped husky's own separate config file in favor of
  reading directly from `package.json` scripts — adapting to whatever
  script-invocation convention the project already has rather than adding a
  husky-specific config surface.
- **Fallback / asking:** silent, install-time only (`npm install` /
  `prepare` script), no interactive step.
- **Caveat:** weaker fit than the others — this is "don't clobber what's
  there," not "infer the team's convention and match it." Sourced only
  from secondary write-ups (Medium, pistack.xyz); no primary husky docs
  page was fetched in this pass, so confidence is lower than the other
  entries.
- **Sources:** [pistack.xyz comparison](https://www.pistack.xyz/posts/2026-04-26-pre-commit-vs-lefthook-vs-husky-git-hooks-management-guide-2026/), [jellybeanz Medium writeup](https://jellybeanz.medium.com/comparing-pre-commit-alternatives-and-applying-git-hooks-with-husky-9863c2e9fb4c)

### 7. release-please — version state, not release "type"

- **Detects:** the current version to bump from, and the size of the next
  bump.
- **Mechanism:** two-part. (a) File read: `.release-please-manifest.json`
  tracks the version each package in the repo is currently on (must exist,
  can be empty `{}` on first run). (b) Git history analysis: commits since
  the last release tag are parsed for Conventional Commits markers
  (`feat:`, `fix:`, `BREAKING CHANGE`) to compute the semver bump.
- **Fallback:** none — the manifest is a hard prerequisite; if it's
  missing entirely (not even empty), release-please won't run.
- **Asks or decides silently:** the version-bump computation from commit
  history is fully automatic — it opens a release PR without asking. But
  note the limit: the release **type** (`node`, `python`, `simple`, …) is
  *not* auto-detected from repo contents — it's declared explicitly in
  `release-please-config.json`. A later PR allowed setting it once at the
  manifest root instead of repeating it per-package, which reduces
  repetition but still isn't inference.
- **Sources:** [manifest-releaser docs](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md), [release-type-at-root commit](https://github.com/googleapis/release-please/commit/fc73b6dd3f5f7ed449b9d304e53bada911e3190f)

### 8. jujutsu (jj) — colocation detection (different axis: VCS-store choice, not team convention)

- **Detects:** whether the target directory already has a `.git/`
  directory (i.e., this is an existing Git repo) at `jj git init`/`jj git
  clone` time.
- **Mechanism:** directory-presence sniffing. When true, jj defaults to
  **colocated mode** (`git.colocate = true`) — sharing the working copy
  between the Git repo and the jj workspace — rather than imposing its own
  separate store layout.
- **Fallback:** `--no-colocate` flag or `git.colocate = false` config opts
  out and forces jj's own layout.
- **Asks or decides silently:** silently decides at init/clone time; no
  prompt.
- **Caveat:** this adapts to *"is Git already here"*, not to a team's
  authored conventions (commit style, branch naming) — a different kind of
  adaptation than the others in this list, included because it's a clean
  example of the directory-sniffing mechanism.
- **Sources:** [jj Git compatibility docs](https://github.com/martinvonz/jj/blob/main/docs/git-compatibility.md), [jj config docs](https://jj-vcs.github.io/jj/v0.15.1/config/)

### 9. GitButler — claimed, not confirmed

- Marketing/blog material claims a design philosophy of layering onto
  whatever workflow already exists ("start using GitButler on your own
  without asking permission or changing team conventions"; teammates
  without GitButler see standard branches/commits). No evidence of an
  actual detection mechanism (no file sniffing or history analysis)
  surfaced for team conventions specifically — this is an
  interoperability/compatibility claim, not a documented adaptive-detection
  feature. Flag as weak/unconfirmed; would need source-diving or product
  docs beyond blog posts to substantiate.
- **Sources:** [GitButler "Simplifying Git" blog](https://blog.gitbutler.com/simplifying-git), [GitButler docs overview](https://docs.gitbutler.com/overview)

### 10. gh CLI — PR-template detection, but only on one code path (negative example)

- **Detects (when it works):** the repo's PR template file, via file
  sniffing of documented locations (`.github/pull_request_template.md`,
  `.github/PULL_REQUEST_TEMPLATE/*.md`, repo root, `docs/`).
- **Mechanism:** file sniffing, but gated by *how* the PR is created.
- **Fallback:** the template is **silently skipped** — not applied and not
  flagged — when a PR is created non-interactively via `gh pr create` with
  title/body supplied directly and submitted without `--template` or
  browser preview. It only fires via `--template <name>` (explicit) or the
  "Preview in browser" step (documented in [cli/cli#388](https://github.com/cli/cli/issues/388)).
- **Asks or decides silently:** silently *doesn't* apply detected
  convention in the common non-interactive path — the clearest example
  found of detection existing but not firing where users most expect it.
  Useful negative/contrast data point.
- **Sources:** [cli/cli#388](https://github.com/cli/cli/issues/388), [GitHub PR template docs](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository)

### 11. Graphite — reacts to history mutation, not a declared convention

- What search surfaced is weaker than the original framing: Graphite's
  merge strategy (squash/rebase/fast-forward) is a **setting the team
  configures inside Graphite**, not something Graphite reads out of
  GitHub's own repo settings the way Mergify reads branch protection.
- The genuinely adaptive mechanism here is different in kind: Graphite
  tracks stacked-branch identity across a squash-merge (which rewrites the
  commit hash and would otherwise break stack tracking) and automatically
  rebases the upstack PRs after a partial merge — a runtime reaction to
  what the merge operation actually did, not an inference from a declared
  team convention.
- **Sources:** [Graphite merge PRs docs](https://graphite.com/docs/merge-pull-requests), [stacked diffs on GitHub guide](https://graphite.com/guides/stacked-diffs-on-github)

## Sources

| Source | Type | Relevance |
|--------|------|-----------|
| [Renovate semantic-commits docs](https://docs.renovatebot.com/semantic-commits/) | Docs | Detection window, algorithm inspiration, override precedence |
| [Renovate discussion #39444](https://github.com/renovatebot/renovate/discussions/39444) | Issue/Discussion | Flip-flop failure mode on inconsistent repos |
| [conventional-commits-detector](https://github.com/conventional-changelog/conventional-commits-detector) | Repo | Underlying detection library, 6 supported conventions |
| [Customizing Dependabot PRs](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/customizing-dependabot-prs) | Docs | Silent-by-default detection claim, override mechanism |
| [Mergify GitHub rulesets](https://docs.mergify.com/merge-queue/github-rulesets/) | Docs | API-read detection of branch protection, translation to conditions |
| [Kodiak config reference](https://kodiakhq.com/docs/config-reference) | Docs | Contrast case, explicit-only config |
| [husky vs pre-commit vs Lefthook (2026)](https://www.pistack.xyz/posts/2026-04-26-pre-commit-vs-lefthook-vs-husky-git-hooks-management-guide-2026/) | Blog | Non-destructive hook preservation, secondary source |
| [release-please manifest-releaser docs](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md) | Docs | Manifest + history-based version detection |
| [jj Git compatibility](https://github.com/martinvonz/jj/blob/main/docs/git-compatibility.md) | Docs | Colocation auto-detection |
| [GitButler blog](https://blog.gitbutler.com/simplifying-git) | Blog | Unconfirmed interoperability claim |
| [cli/cli#388](https://github.com/cli/cli/issues/388) | Issue | PR-template detection failing on the common `gh pr create` path |
| [Graphite merge PRs docs](https://graphite.com/docs/merge-pull-requests) | Docs | Merge-strategy config vs. squash-identity tracking |
