# Research: Where teams codify git/landing preferences in and around a repo

## Metadata

**Date:** 2026-08-29
**Domain:** devops
**Triggered by:** /hex-discuss "finalize phase"
**Expires:** 2027-02-28

## Direct Answer

A team's git/landing preferences (commit format, merge strategy, review/status
gates, signing, changelog cadence) are codified across five surface classes,
in increasing order of enforcement strength: (1) human-readable docs — advisory
only, no mechanism reads them; (2) convention-tooling config files — encode
intent, enforced only if wired into a CI job or a real git hook, not by their
mere presence; (3) forge-level repo/branch settings — read via the forge API
or CLI, authoritative because the forge itself blocks non-conforming merges;
(4) merge-bot/queue configs — authoritative only for the merge path that bot
actually gatekeeps, and only if the forge's branch protection requires the
bot's check; (5) DCO/signing enforcement — a specific case of (3)/(4), same
rule applies. The single strongest per-repo detection signal a tool can use is
cross-referencing a locally-declared convention (a commitlint config, a
mergify rule, a DCO app) against whether its check name appears in the forge's
*required* status checks / rulesets — presence without that cross-reference is
intent, not enforcement.

## Surface Inventory

### A. Human-readable docs (advisory — no mechanical enforcement)

| Surface | Preference encoded | Machine-readable? | How to read |
|---|---|---|---|
| `CONTRIBUTING.md` (repo root, `.github/`, or `docs/`) | Commit message format, branch naming, PR process, expected merge strategy, DCO sign-off instructions | No (prose) | Read file; GitHub/GitLab both special-case this path and surface a banner linking it from the PR/MR creation UI |
| `docs/development.md` / `docs/CONTRIBUTING.md` | Same as above, project-specific location | No | Read file; no forge convention for this path, must search |
| PR template — `.github/PULL_REQUEST_TEMPLATE.md` or `.github/PULL_REQUEST_TEMPLATE/*.md` (multiple templates) | Expected PR description shape, checklists (tests, changelog entry, DCO sign-off) | Partially — checkbox structure is parseable, but nothing enforces it's filled in | Read file(s); GitHub auto-populates the PR body from these paths |
| README "Contributing"/"Development" section | Same as CONTRIBUTING.md, informal | No | Read file, look for heading |
| `.github/CODEOWNERS` (or `docs/`, root) | Required reviewers by path — interacts with, but isn't itself, a merge-strategy preference | Yes (simple glob-owner syntax) | Read file; only takes effect if branch protection has "Require review from Code Owners" enabled |

### B. Convention-tooling config (encodes intent — enforced only if wired into CI/hooks)

| Surface | Preference encoded | Machine-readable? | How to read |
|---|---|---|---|
| commitlint — `commitlint.config.{js,cjs,mjs,ts}`, `.commitlintrc{.json,.yml,.yaml,.js}`, or `commitlint` key in `package.json` | Commit message format (conventional-commits rules, allowed types/scopes) | Yes | Read file; check whether a `commit-msg` hook or CI job actually invokes `commitlint` |
| commitizen (JS) — `.cz.json`, `.czrc`, `cz-config.js`, or `config.commitizen` in `package.json` | Interactive commit message prompts matching a convention | Yes | Read file |
| commitizen (Python) — `[tool.commitizen]` in `pyproject.toml` | Commit convention + version bump rules | Yes | Parse TOML section |
| gitlint — `.gitlint` (INI) or `[tool.gitlint]` in `pyproject.toml` | Commit message linting rules | Yes | Read file; only enforced if run as a hook or CI step |
| pre-commit framework — `.pre-commit-config.yaml` | May include a commit-msg-stage hook (gitlint, commitizen check, conventional-pre-commit) among general hooks | Yes | Parse YAML `repos[].hooks[]`; check `stages: [commit-msg]` to isolate commit-convention hooks from unrelated ones |
| Husky — `.husky/` dir (v5+, e.g. `.husky/commit-msg` script calling commitlint) or `husky` key in `package.json` (v4, legacy) | Local git hook wiring — turns another tool's config from advisory into locally-enforced (but bypassable with `--no-verify`) | Partially (script content is readable, but hook install itself is a `postinstall` side effect) | Read `.husky/commit-msg` / `package.json` `husky.hooks` |
| `.gitmessage` commit template + `commit.template` git config | Suggested commit message skeleton | Yes (the template file), but the git config pointing to it is usually local/uncommitted | Read `.gitmessage` if present; local `commit.template` setting isn't repo-visible unless a setup script sets it (e.g. `git config commit.template .gitmessage` in a documented bootstrap step) |
| `cliff.toml` (git-cliff changelog generator) | Commit-group taxonomy implies an expected conventional-commit-like structure | Yes | Parse TOML `[git.commit_parsers]` |
| release-please — `release-please-config.json` + `.release-please-manifest.json` | Assumes Conventional Commits for changelog/version bump; `release-type`, per-package config | Yes | Parse JSON |
| semantic-release — `.releaserc(.json/.yml/.yaml/.js/.cjs)`, `release.config.{js,cjs}`, or `release` key in `package.json` | Same assumption, plugin pipeline (commit-analyzer preset, e.g. `angular`, `conventionalcommits`) | Yes | Parse config; preset name signals which convention |
| Changesets — `.changeset/config.json` (+ presence of `.changeset/*.md` files signals active use) | Per-PR changeset file requirement instead of commit-message convention; baseBranch, access, changelog generator | Yes | Parse JSON; enforcement usually via a CI job checking a changeset file was added (e.g. `changeset-bot` or a workflow step) |
| towncrier — `[tool.towncrier]` in `pyproject.toml` or `towncrier.toml` | Per-PR "news fragment" file requirement (similar pattern to Changesets, Python ecosystem) | Yes | Parse TOML |

### C. Forge-level settings (authoritative — the forge itself blocks non-conforming merges)

| Surface | Preference encoded | Machine-readable? | How to read |
|---|---|---|---|
| GitHub repo merge-strategy settings | Which merge strategies are allowed (merge commit / squash / rebase), squash commit title/message default, auto-merge allowed, delete-branch-on-merge | Yes, via API | `gh api repos/{owner}/{repo}` (fields `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`, `allow_auto_merge`, `delete_branch_on_merge`, `squash_merge_commit_title`, `squash_merge_commit_message`) or `gh repo view --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed,deleteBranchOnMerge` |
| GitHub branch protection (classic, per-branch) | Required status checks, required PR reviews (count, code-owner review, dismiss stale), enforce-on-admins, required linear history, allow-force-pushes, required conversation resolution | Yes, via API | `gh api repos/{owner}/{repo}/branches/{branch}/protection`; signature requirement is a sub-resource: `gh api repos/{owner}/{repo}/branches/{branch}/protection/required_signatures` |
| GitHub repository rulesets (newer, layered, can be org- or repo-scoped, applies to branches and tags) | Superset of branch protection — adds `merge_queue`, `required_signatures`, `non_fast_forward`, `pull_request` (approval/codeowner rules), `required_status_checks` as discrete rule types that can layer across multiple rulesets | Yes, via API | `gh api repos/{owner}/{repo}/rulesets` (list) then `gh api repos/{owner}/{repo}/rulesets/{id}` (detail) — [GitHub Docs: REST API endpoints for rules](https://docs.github.com/en/rest/repos/rules) |
| GitHub merge queue config | Merge method used by the queue, min/max entries per group, required checks, check-response timeout | Yes, via API | Appears as a `merge_queue` rule inside rulesets (see above), or under branch protection in older configs |
| GitHub Settings-as-code (community "Settings" GitHub App, `probot/settings`) | Declarative source-of-truth for repo settings incl. merge options and branch protection, checked into the repo and synced to the API on merge | Yes | `.github/settings.yml` — read directly; treat as intended state, cross-check it actually matches the live API response (the app may be uninstalled/stale) |
| GitLab merge method + squash settings | `merge_method` (`merge` / `rebase_merge` / `ff`), `squash_option` (`never`/`always`/`default_on`/`default_off`) | Yes, via API | `GET /projects/:id` (or `glab api projects/:id`) — [GitLab Docs: Merge methods](https://docs.gitlab.com/user/project/merge_requests/methods/) |
| GitLab push rules (Premium/Ultimate) | `reject_unsigned_commits`, `commit_message_regex`, `member_check` (author must be a project member), branch name regex | Yes, via API (Premium+ only — 403/404 on lower tiers) | `GET /projects/:id/push_rule` — [GitLab Docs: Push rules](https://docs.gitlab.com/user/project/repository/push_rules/) |

### D. Bot/merge-queue configs (authoritative only for the path that bot gatekeeps)

| Surface | Preference encoded | Machine-readable? | How to read |
|---|---|---|---|
| Mergify | Merge conditions (required checks by name, label gates), queue rules, priority | Yes | File at repo root, checked in this order: `.mergify.yml`, `.mergify/config.yml`, `.github/mergify.yml` — [Mergify config file docs](https://docs.mergify.com/configuration/file-format/) |
| Bors (largely superseded by native GitHub/GitLab merge queues, still seen in older Rust-ecosystem repos) | Required status checks before a `bors r+` merge, branch to merge into, delete-merged-branches | Yes | `bors.toml` at repo root |
| Kodiak | Auto-merge trigger conditions (labels, required checks), update strategy (merge/rebase existing PRs against base) | Yes | `.kodiak.toml` at repo root |

Whether a bot config is authoritative depends on whether the forge's branch
protection/ruleset actually names that bot's status check as *required* — a
`.mergify.yml` with elaborate queue rules is inert if nothing stops a direct
merge outside the queue.

### E. DCO / signing enforcement (a specific case of C/D)

| Surface | Preference encoded | Machine-readable? | How to read |
|---|---|---|---|
| DCO GitHub App (`dcoapp/app`, formerly `probot/dco`) | Requires `Signed-off-by` trailer matching commit author on every commit in the PR | Enforcement is a required status check named `DCO`; optional config is YAML | Config (if customized): `.github/dco.yml` on the default branch — `require.members: false` to skip org members, `allowRemediationCommits` for rebase-fix exceptions. Enforcement check: look for `"DCO"` in the required-status-checks list from branch protection/rulesets (section C) |
| GitHub required commit signatures | Requires GPG/SSH-signed commits | Yes, via API | `required_signatures=true` in branch protection sub-resource, or a `required_signatures` rule in rulesets |
| GitLab reject unsigned commits | Same, GitLab-native | Yes, via API (Premium+) | `push_rule.reject_unsigned_commits` (see table C) |

### Additional detection surface: CI workflow files themselves

`.github/workflows/*.yml` (GitHub Actions) and `.gitlab-ci.yml` (GitLab CI) are
not a preference *source* but the most reliable place to confirm a preference
declared elsewhere is actually enforced rather than merely documented: grep
step `uses:`/`run:` values for `commitlint`, `wagoid/commitlint-friendly-action`,
`amannn/action-semantic-pull-request` (PR-title convention check),
`dcoapp/app` equivalents, `gitlint`, `pre-commit/action`, or a
`changeset-bot`/`towncrier check` invocation. A convention-tooling config file
(section B) with no matching CI step and no local hook wiring (Husky/pre-commit
install) is advisory only, indistinguishable in effect from CONTRIBUTING.md
prose.

## Key Findings

1. Enforcement strength is not implied by a config file's existence — a
   commitlint config, a `cliff.toml`, or a `.mergify.yml` can sit unused; the
   authoritative signal is whether the forge's branch protection/ruleset lists
   that tool's check as *required*, or whether a git hook (Husky/pre-commit)
   is actually installed to run it locally.
2. GitHub has two parallel, overlapping systems for branch-level rules: legacy
   per-branch "branch protection" (`/branches/{branch}/protection`) and the
   newer, layered "rulesets" (`/rulesets`) which can apply org-wide across
   many repos and include rule types branch protection lacks (e.g.
   `merge_queue`, `non_fast_forward`). A repo can have either, both, or
   rulesets inherited from the org level and invisible at the repo API alone.
   [GitHub Docs: REST API endpoints for rules](https://docs.github.com/en/rest/repos/rules)
3. `.github/settings.yml` (community "Settings" GitHub App) is the one surface
   that is simultaneously a checked-in file and a claim about forge-level
   state — read it as declared intent, but verify against the live API since
   the syncing app can be uninstalled or the file can drift from reality.
4. The DCO GitHub App's only checked-in artifact is optional
   (`.github/dco.yml`); its actual enforcement lives entirely in the forge's
   required-status-checks list under the literal string `"DCO"` — a repo can
   have the app installed (producing a status) without it being required to
   merge. [dcoapp/app README](https://github.com/dcoapp/app/blob/main/README.md)
5. Mergify's config file has three valid root-relative paths checked in
   priority order (`.mergify.yml`, `.mergify/config.yml`,
   `.github/mergify.yml`); a tool scanning for it must check all three, and a
   near-miss like `.github/.mergify.yml` (extra leading dot) is silently
   ignored by Mergify itself. [Mergify config file docs](https://docs.mergify.com/configuration/file-format/)
6. GitLab's push-rule surface (commit message regex, reject-unsigned-commits,
   member-only-push) requires Premium/Ultimate tier — a `GET
   /projects/:id/push_rule` call on a free-tier project returns an error, not
   an empty/default result, which a detection tool must distinguish from "no
   rule configured." [GitLab Docs: Push rules](https://docs.gitlab.com/user/project/repository/push_rules/)

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| [GitHub Docs: REST API endpoints for rules](https://docs.github.com/en/rest/repos/rules) | Docs | current | Rulesets endpoint (`/repos/{owner}/{repo}/rulesets`), rule types incl. merge_queue, required_signatures |
| [gh repo view manual](https://cli.github.com/manual/gh_repo_view) | Docs | current | `--json` field names for merge-strategy settings |
| [GitLab Docs: Merge methods](https://docs.gitlab.com/user/project/merge_requests/methods/) | Docs | current | `merge_method` values (merge/rebase_merge/ff) |
| [GitLab Docs: Squash and merge](https://docs.gitlab.com/user/project/merge_requests/squash_and_merge/) | Docs | current | `squash_option` values |
| [GitLab Docs: Push rules](https://docs.gitlab.com/user/project/repository/push_rules/) | Docs | current | `reject_unsigned_commits`, commit message regex, tier gating |
| [Mergify configuration file docs](https://docs.mergify.com/configuration/file-format/) | Docs | current | Valid config file paths and precedence |
| [dcoapp/app README](https://github.com/dcoapp/app/blob/main/README.md) | Repo docs | current | `.github/dco.yml` options (`require.members`, `allowRemediationCommits`); enforcement is via required status check name `DCO` |
