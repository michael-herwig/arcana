# Research: Detection recipe for reading a team's git/landing preferences

## Metadata

**Date:** 2026-08-29
**Domain:** devops
**Triggered by:** /hex-discuss "finalize phase"
**Expires:** 2027-02-28

## Direct Answer

Readability splits sharply along a line that has nothing to do with the
discovery lane's advisory→authoritative ordering: **GitHub's newer rulesets
API (`Metadata: read` — the baseline permission every token gets, including
unauthenticated reads on public repos) is readable by any non-admin
contributor; the legacy branch-protection API (`Administration: read`) is
admin-only and returns `404` — not `403` — to everyone else**, which a naive
detection tool misreads as "no protection configured" rather than "I can't
see it." GitLab shows the same shape: push rules need Maintainer+ (Developer
read-only access is an open GitLab feature request, not yet shipped);
protected-branch listing is more permissive (Reporter+, by convention rather
than an explicit documented statement — see confidence note below).
Convention-tooling config files (Section B: commitlint, gitlint, mergify,
DCO) are always file-readable regardless of role — the permission question
only bites on the forge-side enforcement check, never on the declared
intent. The single biggest detection pitfall: **the readable surface
(rulesets) and the unreadable surface (classic branch protection) are not
interchangeable views of the same data** — `GET
/repos/{owner}/{repo}/rules/branches/{branch}` returns rules sourced *only*
from rulesets and silently omits anything configured via legacy branch
protection, so a repo that protects `main` exclusively through the classic
UI will make a non-admin caller of the readable endpoint see an empty rule
list. That is a false-negative on the exact question ("is anything
enforced?") that matters most, and it happens with a `200 OK`, not an error
a caller would think to catch.

## Per-Surface Detection Recipe

### A. Human-readable docs — no permission gate, ever

| Surface | Read command | Sample fields / output shape |
|---|---|---|
| `CONTRIBUTING.md` | `find . -maxdepth 2 -iregex '.*/\(CONTRIBUTING\|CONTRIBUTING\.md\)' ; cat CONTRIBUTING.md` (also check `.github/CONTRIBUTING.md`, `docs/CONTRIBUTING.md`) | Prose — no fields, requires text parsing/LLM read |
| PR template | `cat .github/PULL_REQUEST_TEMPLATE.md` or `ls .github/PULL_REQUEST_TEMPLATE/` | Checkbox list, headings |
| `CODEOWNERS` | `cat .github/CODEOWNERS \|\| cat CODEOWNERS \|\| cat docs/CODEOWNERS` | `<path-glob> @owner1 @team2` lines |

No forge API involved — plain file reads via the already-cloned working
tree, or `gh api repos/{owner}/{repo}/contents/{path}` (base64 content,
readable at whatever level the repo itself is readable — public repos need
no auth) if the repo isn't cloned locally.

### B. Convention-tooling config — file-readable at any permission level

| Surface | Read command | Sample fields |
|---|---|---|
| commitlint | `cat commitlint.config.{js,cjs,mjs,ts} 2>/dev/null; jq .commitlint package.json 2>/dev/null` | `extends: ['@commitlint/config-conventional']`, `rules` |
| gitlint | `cat .gitlint 2>/dev/null; python -c "import tomllib,sys; print(tomllib.load(open('pyproject.toml','rb')).get('tool',{}).get('gitlint'))"` | INI sections `[general]`, `[title-match-regex]` |
| pre-commit | `yq '.repos[].hooks[] \| select(.stages[]? == "commit-msg")' .pre-commit-config.yaml` | hook `id`, `stages` |
| Husky | `cat .husky/commit-msg 2>/dev/null; jq .husky package.json 2>/dev/null` | shell script invoking `npx commitlint` |
| semantic-release | `cat .releaserc* release.config.* 2>/dev/null; jq .release package.json 2>/dev/null` | `plugins`, commit-analyzer preset name |
| Mergify | `cat .mergify.yml .mergify/config.yml .github/mergify.yml 2>/dev/null` (check all three paths — the tool itself only honors these three, `.github/.mergify.yml` is silently ignored) | `pull_request_rules[].conditions`, `queue_rules` |
| DCO app config | `cat .github/dco.yml 2>/dev/null` | `require.members`, `allowRemediationCommits` |

All of B is a plain `cat`/parse — no forge API call, no permission gate.
The permission question is entirely deferred to the cross-check in the next
section: presence here is intent, never proof.

### C. Forge-level settings — this is where permission diverges sharply

| Surface | Read command | Sample fields | Min permission (verified) |
|---|---|---|---|
| GitHub repo merge-strategy settings | `gh api repos/{owner}/{repo} --jq '{allow_merge_commit,allow_squash_merge,allow_rebase_merge,allow_auto_merge,delete_branch_on_merge,squash_merge_commit_title}'` or `gh repo view --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed,deleteBranchOnMerge` | booleans + enum strings | Base repo metadata — public repos need **no auth**; private repos need only read/`Contents: read` access, same level as cloning |
| GitHub classic branch protection | `gh api repos/{owner}/{repo}/branches/{branch}/protection` | `required_status_checks.contexts[]`, `required_pull_request_reviews.required_approving_review_count`, `enforce_admins.enabled`, `required_signatures` | **`Administration: read`** — admin-only. Confirmed via GitHub community discussion [#24582](https://github.com/orgs/community/discussions/24582): non-admin authenticated collaborators get **`404`**, not `403`, on a branch that genuinely has protection configured. A caller cannot distinguish "unprotected" from "protected but I lack Administration" from the status code alone. |
| GitHub repository rulesets — list | `gh api repos/{owner}/{repo}/rulesets` | array of `{id, name, target, enforcement, source_type}` | **`Metadata: read`** — the baseline permission every fine-grained token carries; works for **unauthenticated requests on public repos**. Per [GitHub Docs: permissions required for fine-grained PATs](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens) |
| GitHub rules-for-a-branch (effective, layered) | `gh api repos/{owner}/{repo}/rules/branches/{branch}` | array of `{type, parameters}` — `type` values incl. `required_status_checks`, `pull_request`, `required_signatures`, `non_fast_forward` | **`Metadata: read`**, same as above. **Caveat (verified):** per [GitHub Docs: REST API endpoints for rules](https://docs.github.com/en/rest/repos/rules), this endpoint returns rules sourced *only* from rulesets ("evaluate"/"disabled" enforcement excluded) — it does **not** merge in anything configured via the legacy branch-protection UI/API. A repo using only classic protection returns `[]` here even though checks are genuinely required. |
| GitLab merge method + squash | `glab api projects/:id --jq '{merge_method,squash_option}'` | `merge_method` ∈ {merge, rebase_merge, ff}; `squash_option` ∈ {never, always, default_on, default_off} | Part of base project GET — readable at whatever level the project itself is visible (public projects: no auth; private: Guest/Reporter typically sufficient, not verified to endpoint-specific granularity) |
| GitLab protected branches | `glab api projects/:id/protected_branches` | `name`, `push_access_levels[]`, `merge_access_levels[]`, `allow_force_push` | Not explicitly stated as a standalone permission row in GitLab's docs (checked [docs.gitlab.com/api/protected_branches](https://docs.gitlab.com/api/protected_branches/) and [docs.gitlab.com/user/permissions](https://docs.gitlab.com/user/permissions/) — neither states a minimum role for the *read* verb explicitly, only for manage/unprotect actions). Treat as **Reporter+, unconfirmed** — verify empirically per-instance before depending on it. |
| GitLab push rules | `glab api projects/:id/push_rule` | `commit_message_regex`, `reject_unsigned_commits`, `member_check`, `branch_name_regex` | **Maintainer+**, confirmed by an open GitLab feature request to *add* Developer read-only access ([gitlab-org/gitlab work item 592146](https://gitlab.com/gitlab-org/gitlab/-/work_items/592146) — "Allow Developer role read-only access to push_rule API endpoint"), i.e. as of writing Developer/Reporter get `403`. Also Premium/Ultimate-tier gated — free tier returns an error regardless of role, must not be conflated with "no rule configured." |

### D. Merge-bot/queue configs — file-readable; enforcement is the C cross-check

Same read mechanics as Section B (`cat .mergify.yml`, `cat bors.toml`, `cat
.kodiak.toml` — no forge API, no permission gate on the read itself). What
differs is *interpreting* the file: none of these tools' presence is
meaningful without the Section C cross-check below, because whether the bot
gatekeeps the actual merge path is a branch-protection/ruleset fact, not
something the bot's own config file can assert about itself.

### E. DCO / signing — file read (optional config) + status-check name lookup

- Config, if customized: `cat .github/dco.yml` (Section B mechanics, no gate).
- Enforcement: the literal string `"DCO"` must appear in the required-checks
  list from Section C — same asymmetry applies (readable via rulesets
  endpoint at `Metadata: read`, admin-only via classic branch protection).
- GitHub required signed commits: `required_signatures` field/rule — appears
  in both branch-protection sub-resource (`.../protection/required_signatures`,
  admin-gated) and as a rule `type` in the rulesets endpoint (`Metadata: read`)
  — prefer the rulesets read for the same reason as above.
- GitLab: `push_rule.reject_unsigned_commits` — same Maintainer+/Premium gate
  as push rules generally (Section C).

## Advisory-vs-Enforced Cross-Check Algorithm

Given a locally-declared convention (Section B) and a required-checks read
(Section C), decide enforced / advisory-only / unknown:

1. **Derive the candidate's check name(s).** For a CI-wired tool, the status
   context is the GitHub Actions job name (`jobs.<id>.name`, defaulting to
   `<id>` if unset) or, for a reusable/composite workflow, the pattern
   `<workflow-name> / <job-name>`. Grep `.github/workflows/*.yml` for the
   `uses:`/`run:` line invoking the tool (`commitlint`,
   `wagoid/commitlint-friendly-action`, `amannn/action-semantic-pull-request`,
   `dcoapp` webhook implies status name `"DCO"`, `gitlint`,
   `pre-commit/action`) to get the exact job id/name string. For Mergify,
   the relevant string is whatever check name the `pull_request_rules[].conditions`
   entries reference (e.g. `check-success=<name>`), read straight from the
   Section D file.
2. **Fetch the required-checks list**, preferring the readable surface:
   `gh api repos/{o}/{r}/rules/branches/{branch}` → collect every rule where
   `type == "required_status_checks"`, flatten `parameters.required_status_checks[].context`.
   Only if that call is unauthenticated/empty *and* admin access is available,
   also read `gh api repos/{o}/{r}/branches/{branch}/protection --jq
   '.required_status_checks.contexts'` to catch legacy-only setups (Section C
   caveat) — do not skip this when the ruleset read comes back `[]`, since
   `[]` there is ambiguous between "genuinely nothing required" and "only
   legacy protection is used and I can't see it."
3. **Exact string match** (GitHub check names are matched verbatim, case-
   sensitive) between step 1's candidate name(s) and step 2's list.
4. **Classify:**
   - Match found → **enforced**.
   - Config exists (Section B), no match, but a local hook installs it
     (Husky `.husky/commit-msg`, `pre-commit install` documented in
     CONTRIBUTING) → **locally enforced, forge-bypassable** (skippable with
     `--no-verify` or a direct API commit).
   - Config exists, no match, no local hook → **advisory-only**, no
     different in effect from CONTRIBUTING.md prose.
   - Step 2's read itself failed with a permission error (see cost table
     below) → **unknown** — never collapse this into "advisory-only".
5. **GitLab equivalent:** cross-reference `.gitlab-ci.yml` job names against
   `only_allow_merge_if_pipeline_succeeds` (a project-level boolean, part of
   the base `GET /projects/:id` response — same visibility as the merge-method
   read in Section C, not gated like push_rule) rather than a discrete
   required-checks list; GitLab has no per-job "required check" concept
   outside of Premium+ merge request approval rules and pipeline-must-succeed
   is binary (all jobs in the pipeline must pass, not a named subset).

## Fallback Ladder When Reads Fail

When there is no forge CLI, no network, or no auth (unauthenticated on a
private repo, or a local-only clone), the only remaining signals are
git-native and describe **observed practice, not policy** — weaker than any
of the five surface classes above, but the only class guaranteed available:

1. `git log --format='%s' -n 200 | grep -cE '^(feat|fix|chore|docs|refactor|test)(\(.+\))?:'` against total commit count — statistical adoption rate of Conventional-Commits-shaped subjects in *merged* history, independent of whether any linter ever ran.
2. `git log --merges --format='%s' -n 100 | wc -l` vs total commit count on the default branch — near-zero merge commits with a linear history implies squash-or-rebase workflow is tolerated/enforced in practice; GitHub's squash-merge default appends `(#123)` to the subject, so `git log --format='%s' | grep -cE '\(#[0-9]+\)$'` is a strong GitHub-specific squash-merge fingerprint.
3. `find . -maxdepth 2 -iname 'CONTRIBUTING*' -o -iname '.gitmessage'` then read directly (Section A mechanics, no gate ever needed).
4. `git config --get commit.template` — only informative if the repo was cloned via a documented bootstrap script that sets it locally; absence proves nothing about the remote convention.
5. `git log --format='%b' -n 200 | grep -c '^Signed-off-by:'` against commit count — DCO adoption-in-practice signal when the DCO app/branch-protection facts are unreadable.

Every item in this ladder answers "what did contributors actually do,"
which can diverge in both directions from "what is currently enforced": a
convention can be religiously followed out of habit after its enforcement
was removed, or contributors can happen to write clean conventional commits
on a repo that enforces nothing at all. Treat ladder findings as a prior to
be overridden the moment any Section C/D/E read becomes available, never as
a substitute once one is.

## Cost of a Wrong Read

| Surface / failure mode | Wrong read | What it costs |
|---|---|---|
| Classic branch protection, non-admin gets `404` | Read as **false-advisory** ("nothing enforced") | A contributor/agent skips writing the changelog fragment, force-pushes, or bypasses review believing nothing gates it — then the actual merge is rejected by the forge, wasting the cycle the detection was meant to save. |
| Rulesets endpoint returns `[]` because the repo uses only legacy protection | Read as **false-advisory** — this is the single biggest pitfall (see Direct Answer) | Same failure mode as above, but silent — no error to catch, a `200 OK` with an empty array looks identical to "genuinely nothing required." |
| GitLab `push_rule` `403` (non-Maintainer) or tier-gated error | Read as **false-advisory** if the error is swallowed as "no rule" | A generated commit message that violates `commit_message_regex` gets rejected at push time despite the tool reporting no constraint. |
| DCO/Mergify config file present, treated as proof of enforcement without the Section C string-match | Read as **false-enforced** | An agent adds ceremony (sign-off trailers, waits for a bot check) the forge never actually requires — wasted effort in the safe direction, but still a wrong model of the repo. |
| `.github/settings.yml` present, treated as live state | Read as **false-enforced or false-advisory**, direction depends on drift | The syncing GitHub App can be uninstalled or the file can be stale; the file states *declared* intent, and only the live API call (Section C) confirms current reality. |

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| [GitHub community discussion #24582 — "GET branch protection returning 404"](https://github.com/orgs/community/discussions/24582) | Community Q&A, GitHub-staff-adjacent | current | Confirms non-admin reads of classic branch protection return `404`, not `403`; "viewing branch protection required an authorized [admin] user" |
| [GitHub Docs: Permissions required for fine-grained personal access tokens](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens?apiVersion=2022-11-28) | Docs | current | Per-endpoint permission table: branch-protection GET needs `Administration: read`; rulesets GET/rules-for-branch GET need only `Metadata: read` |
| [GitHub Docs: REST API endpoints for rules](https://docs.github.com/en/rest/repos/rules?apiVersion=2022-11-28) | Docs | current | Confirms "Get rules for a branch" returns ruleset-sourced rules only, excludes legacy branch-protection-sourced rules |
| [GitLab: Allow Developer role read-only access to push_rule API endpoint (work item 592146)](https://gitlab.com/gitlab-org/gitlab/-/work_items/592146) | Open feature request, GitLab issue tracker | current | Confirms current state: Developer/Reporter roles get `403` on `GET /projects/:id/push_rule` today; only Maintainer+ can read it |
| [GitLab Docs: Protected branches API](https://docs.gitlab.com/api/protected_branches/) | Docs | current | Endpoint shapes; does not state an explicit minimum role for the read verb — flagged as unconfirmed above |
| [GitLab Docs: Roles and permissions](https://docs.gitlab.com/user/permissions/) | Docs | current | General role/permission matrix; push-rule "Manage" listed at Maintainer, no separate view-only row |
| [GitLab Docs: Merge request approval rules](https://docs.gitlab.com/user/project/merge_requests/approvals/rules/) | Docs | current | Confirms custom approval rules are Premium/Ultimate-gated |
| Prior artifact: `.agents/research/discuss-finalize-teams-policy-surfaces.md` | Internal research | 2026-08-29 | Discovery lane's five-surface-class inventory and file-path/endpoint list this recipe verifies permissions against |
