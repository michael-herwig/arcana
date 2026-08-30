# Research: Security surface of an agent holding remote-rights (finalize)

## Metadata

**Date:** 2026-08-29
**Domain:** security
**Triggered by:** /hex-architect .agents/discussions/finalize-phase.md
**Expires:** 2027-02-28

## Direct Answer

The remote rights `/hex-finalize` needs (force-push one branch, dispatch one
workflow, mutate one PR) map cleanly to three GitHub fine-grained-PAT scopes
and one GitLab role/scope pair, but **the token that actually executes them in
practice is the ambient `gh`/`glab` CLI credential the human already
authenticated**, not a purpose-minted one — that credential is scoped to the
whole account (`repo`, `read:org`, `gist` by default for `gh`), an order of
magnitude broader than the task. Force-push containment is not a credential
property at all: `--force-with-lease --force-if-includes` plus branch-
protection "restrict force pushes" is the only real backstop, and both are
bypassable by identical means (a background fetch defeats the lease; an admin
bypass defeats protection). Convention discovery reads attacker-writable
files by design — CONTRIBUTING.md, commitlint configs — which is the same
class of untrusted input that has already produced real prompt-injection
incidents against coding agents with repo write access. DCO sign-off is a
first-person legal certification; an agent adding it is sound only when it
faithfully mirrors a human attestation the human can see before the push
lands, not when it is a mechanical git flag. No vendor (GitHub, Anthropic,
OpenAI) documents finalize-shaped remote rights directly, but the nearest
precedent — GitHub Copilot's coding agent — converges on the same answer this
ADR already reached: branch-prefix/single-branch restriction as the
structural containment, not trust in the model.

## 1. Minimal credential scopes

### GitHub fine-grained PAT — what each right actually needs

| Right | Fine-grained PAT permission | What it over-grants |
|---|---|---|
| Force-push the feature branch | `Contents: Read and write` | Write to **every** file in the repo, on **every** branch the token can reach — not just the feature branch. Notably it does *not* cover `.github/workflows/*`; pushing changes to workflow files needs the separate `Workflows: Read and write` permission even with Contents granted [GitHub Docs: fine-grained PAT permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens) — a real, if incidental, blast-radius limiter for finalize since it should never need to touch CI config. |
| Trigger `workflow_dispatch` (`gh workflow run` / `POST .../dispatches`) | `Actions: Read and write` | Covers **all** workflows in the repo and **any** ref, not just the one workflow/branch finalize cares about — including cancelling or re-running other users' in-flight runs and deleting artifacts/logs. `workflow_dispatch` also requires the workflow **file to exist on the default branch** before it is API-dispatchable at all (even when dispatched *against* a feature-branch ref) — a discovery gotcha the ADR's Threads already name (`hex.md`/discussion, "required-check gotcha"). |
| Create/edit the PR, flip draft→ready | `Pull requests: Read and write` | Covers editing, closing, reopening, and re-labelling **any** PR in the repo, not just finalize's own. `Contents: read` is also implied for PR metadata reads. |

No fine-grained permission distinguishes a normal push from a force-push —
GitHub's server-side check for that is branch protection, not token scope
(see §2). So minimal-scope design here is entirely about *which* three
permissions to grant and at *repository* (never organization) selection,
not about a special "may-force" bit.

**The practical gap:** finalize is specified to drive `gh`/`glab` as CLIs,
which by default authenticate with the human's own long-lived OAuth session —
`gh auth login`'s default scope set is `repo, read:org, gist`
([`gh auth login` scope discussion](https://github.com/cli/cli/discussions/7762)),
where classic `repo` alone already grants full read/write control of the
repo (contents, PRs, Actions dispatch, everything) and the token has **no
expiry**. That single scope already covers all three rights finalize needs,
plus everything it doesn't (delete branches anywhere, manage webhooks, read
private repo metadata org-wide). A fine-grained PAT scoped to exactly the
three permissions above, restricted to the one repository, is materially
tighter — but requires the project to provision it and point `gh`/`glab` at
it (`GH_TOKEN`/`GITLAB_TOKEN` env var) instead of the ambient login. This is
a genuine, addressable finding, not a theoretical one.

### GitHub Actions `GITHUB_TOKEN` (if finalize ever runs inside a workflow)

The default `GITHUB_TOKEN` cannot itself trigger new workflow runs from
events like `push`/`pull_request` (anti-recursion guard), but
`workflow_dispatch`/`repository_dispatch` are explicit exceptions — it works
if the workflow's `permissions:` block grants `actions: write`
([GitHub Docs: use GITHUB_TOKEN](https://docs.github.com/en/actions/how-tos/security-for-github-actions/security-guides/use-github_token-in-workflows), [GitHub changelog](https://github.blog/changelog/2022-09-08-github-actions-use-github_token-with-workflow_dispatch-and-repository_dispatch/)). This is the same
containment shape as the PAT case: repo-scoped, no-org, but still an
all-workflows/all-refs grant.

### GitLab equivalents

- **Force-push + PR-equivalent (MR) rights:** a **project access token**
  scoped to `write_repository` (repository) is the minimal token scope;
  the token's bot user still needs at least the **Developer** role (Guest/
  Reporter cannot push to protected branches at all), and the *branch*'s
  protected-branch rule must separately list that role/user in
  `allowed_to_push` / `allowed_to_force_push`
  ([GitLab Docs: protected branches](https://docs.gitlab.com/user/project/repository/branches/protected/), [GitLab Docs: token overview](https://docs.gitlab.com/security/tokens/)).
- **Pipeline trigger:** `CI_JOB_TOKEN` only exists inside a running job and
  inherits the *triggering user's* own permissions — it is not a
  separately-scoped credential, so the acting user/bot must already hold
  Developer+ on the target project ([GitLab Docs: CI/CD job token](https://docs.gitlab.com/ci/jobs/ci_job_token/)). For an
  out-of-band trigger (the `glab`-CLI equivalent of `gh workflow run`), a
  project access token with `api` scope is the practical minimum — GitLab
  has no permission as narrow as GitHub's per-area fine-grained PAT; `api`
  is the same over-grant problem as `gh`'s default `repo` scope, one level
  worse since GitLab has no fine-grained token product yet for this path.
- **glab CLI default auth** mirrors `gh`: an OAuth/PAT session scoped to
  `api` (full account API access), same practical-gap finding as above.

## 2. Force-push containment

- **`--force-with-lease` alone is not safe under background fetch.** Any
  tool that fetches on its own (IDEs, git maintenance, a long-running agent
  session) can silently update the remote-tracking ref; the lease check then
  compares against that stale-but-fresh-looking ref and passes even though
  the agent never actually integrated the commit it's about to overwrite —
  `--force-with-lease` degrades to plain `--force` in that window
  ([Adam Johnson: force push safely](https://adamj.eu/tech/2023/10/31/git-force-push-safely/)).
- **`--force-if-includes` (git ≥2.30) closes that gap** by additionally
  requiring the remote tip be reachable from the local branch's own history
  (i.e., actually merged/integrated), not merely fetched. It is a no-op
  without `--force-with-lease` — the two must always be issued together:
  `git push --force-with-lease --force-if-includes`
  ([Adam Johnson, same], [git-push docs referenced therein]). Finalize's
  rewrite-then-push should use this pair unconditionally; the ADR's Threads
  already anchor the pre-rewrite state via a backup ref, which independently
  gives a human a recovery path even if the lease is somehow stale.
- **Branch protection is the real backstop, and it's the same mechanism the
  agent's own scope can't bypass.** GitHub: a ruleset/classic rule with
  "restrict force pushes" blocks the push outright regardless of token
  scope (`Contents: write` does not imply "may force-push a protected
  branch") — GitHub Docs confirm force-push and other protections compose
  additively, most-restrictive-wins
  ([GitHub Docs: available rules for rulesets](https://docs.github.com/en/enterprise-server@3.18/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)). If the feature
  branch itself is unprotected (the common case — protection usually targets
  the default/target branch, not feature branches), there is **no
  forge-side backstop at all** for finalize's force-push; the lease pair
  above is the only defense.
- **Blast radius of force-pushing the wrong ref:** git's reflog is the
  recovery path — `git reflog show origin/<branch>` on a fresh clone that
  still has the pre-force state, or the pusher's own local reflog — but
  entries for unreachable commits expire in 30 days (90 for reachable ones),
  and GitHub's own server-side reflog-equivalent for a force-pushed branch
  is a short, undocumented window
  ([GitHub Community: recovering from force push](https://github.com/orgs/community/discussions/64693), [Graphite: recovering lost commits with reflog](https://graphite.com/guides/recovering-lost-commits-git-reflog)). This is exactly why the ADR's Threads
  treat the pre-rewrite backup ref as load-bearing, not optional — it is
  the only blast-radius control that doesn't depend on someone noticing
  within the reflog window. The scope restriction ("only the invoking
  branch, never the target branch") is the other half: it bounds *which*
  ref can be force-pushed at all, independent of any recovery mechanism.

## 3. Convention discovery as attack surface

Finalize's own design (already decided upstream, see B2/D3 in the linked
Threads) reads two classes of input to decide behavior:

- **Untrusted (checked-in, attacker-writable):** CONTRIBUTING.md, commitlint/
  commitizen/gitlint configs, `.mergify.yml`, PR templates, CODEOWNERS —
  anything that arrives as file content on a branch. On a repo that accepts
  external PRs (public OSS, or an internal repo where a compromised
  dependency/contributor can open one), any of these files is attacker-
  controlled the moment it's read by an agent as instruction rather than
  data.
- **Trusted (forge-side, admin-gated):** branch protection/rulesets,
  required-status-check lists, repo Settings merge-strategy fields — these
  require a privileged mutation (not a PR) to change, so they carry real
  provenance.

This is not a hypothetical risk class for coding agents specifically:
- A security researcher opened a GitHub PR and typed an injected instruction
  into the **PR title alone**; Anthropic's own Claude Code Security Review
  GitHub Action, Google's Gemini CLI Action, and GitHub Copilot's Agent were
  all shown posting secrets back as a PR comment as a result
  ([Cequence: prompt injection exposes AI agent credentials](https://www.cequence.ai/blog/ai/even-the-best-ai-agents-leak-secrets-prompt-injection-is-why/), [VentureBeat: three AI coding agents leaked secrets](https://venturebeat.com/security/ai-agent-runtime-security-system-card-audit-comment-and-control-2026)).
- A prompt-injected **issue title** against a Claude-Code-Action-based triage
  workflow let an attacker steal an npm publish token and push an
  unauthorized release of the `cline` package itself
  ([Cequence, same article]).
- Wiz documented "prt-scan," a campaign of 500+ malicious PRs opened
  specifically to trigger GitHub Actions workflows and harvest cloud
  credentials from CI ([Cequence, same article synthesizing Wiz's findings]).
- A systematic study (GitInject) and an independent Unit 42 field study both
  found every evaluated coding agent vulnerable to some form of indirect
  prompt injection from repo/web content, with adaptive-attack success rates
  reported above 85% in the former
  ([GitInject, arXiv](https://arxiv.org/html/2606.09935v1), [Unit 42: fooling AI agents](https://unit42.paloaltonetworks.com/ai-agent-prompt-injection/)).

None of these are finalize-specific incidents (no product does branch-
rewrite-and-force-push automation today per the ADR's own precedent
research), but they establish the general pattern precisely: a file the
agent reads *as configuration* is functionally *code* if the agent's next
action is a privileged one (force-push, workflow trigger, credential use).
The mitigating design already decided upstream — treat forge settings as
authoritative and checked-in files as declared-but-unverified intent,
cross-reference the two, never let a config file's mere presence expand what
finalize is willing to do (only narrow it, e.g. a stricter commit-message
regex) — is the correct shape and should be stated explicitly as a security
property, not just a convention-discovery nicety: **a hostile CONTRIBUTING.md
can make finalize behave more strictly than its defaults, never less, and
never grant it an action outside its already-consented scope (force-push
this branch, dispatch named workflows, mutate this PR).**

## 4. Signing & DCO semantics

- **DCO `Signed-off-by` is a first-person legal certification**, not a
  formatting convention. Developer Certificate of Origin 1.1's operative
  text is "By making a contribution to this project, **I** certify that..."
  followed by four numbered attestations about authorship/rights and
  awareness that the contribution and sign-off are public and retained
  indefinitely ([developercertificate.org](https://developercertificate.org/)). It is deliberately structured as a
  personal oath, distinct from a corporate CLA which *can* be signed by an
  employer on an employee's behalf
  ([LF DCO guidance](https://bestpractices.linuxfoundation.org/ip/contribution-mechanisms-dco.html)).
- **An agent adding `--signoff` is sound only under specific conditions:**
  the identity attached must be the human's own configured git identity
  (never a bot/service identity — that would misattest authorship), the
  content being signed must be substantively the human's own work merely
  *recomposed* (finalize squashes/reorders scaffolding the human already
  authored across the branch — it does not introduce new authorship), and
  the human must have visibility into what is being signed before it lands
  irreversibly. The ADR's own decisions already satisfy the first two
  (finalize operates on the invoking human's branch, and DCO is applied
  during recomposition of their own commits) and partially satisfy the
  third via the single-approval-gate/disclosure culture already decided —
  but that gate is described as happening *before* finalize runs (at
  review's Approve step), not as a second look at the exact rewritten
  commits' sign-off lines immediately before push. Recommendation below
  addresses this gap directly.
- **Rebase silently breaks GPG/SSH signatures** — a signature covers the
  commit object including its parent hash, so any rewrite (rebase, amend,
  cherry-pick) invalidates prior signatures even when content is unchanged;
  this is exactly why the ADR already commits to re-signing during rewrite
  rather than assuming signatures survive
  ([codegenes.net: verified signatures gone after rebase](https://www.codegenes.net/blog/verified-signatures-are-gone-after-i-pressed-rebase-and-merge/)). Mechanically, re-signing is
  `git rebase --exec 'git commit --amend --no-edit -n -S'` or equivalent
  per-commit re-sign during the recompose step, using whatever signing
  method (`user.signingkey`, `gpg.format = ssh`) the human's git config
  already specifies — finalize should never provision or choose a signing
  key itself, only invoke the human's existing configuration.
- **Key-custody threat model for the agent process:** a well-behaved
  finalize does not read the private key material at all — `git commit -S`
  talks to `gpg-agent`/`ssh-agent` over a local socket, which acts as a
  *signing oracle* (sign this exact byte string) rather than exposing the
  key. The material risk is therefore not exfiltration of the key by a
  compromised agent process, it's **unbounded use of that oracle for the
  duration of the agent's session** (bounded by whatever passphrase-cache
  TTL the human's `gpg-agent.conf`/`ssh-agent` already has — commonly hours)
  — a prompt-injected finalize run could, in principle, sign arbitrary
  attacker-chosen content with the human's key during that window. This
  argues for the same containment posture Anthropic documents generally
  (credentials/signing sockets available only inside the sandboxed
  execution, network egress restricted, no path for the *result* of a
  signing operation to leave except as the intended git object) rather than
  for any finalize-specific key-handling code
  ([Anthropic: how we contain Claude](https://www.anthropic.com/engineering/how-we-contain-claude)).

## 5. Known incidents/guidance

- **No vendor documents finalize-shaped rights** (rewrite history + force-
  push + CI trigger + PR-state mutation as one bundled grant) — confirmed
  by both this search and the ADR's own precedent research (no end-to-end
  branch-finalize automation exists in the field).
- **GitHub Copilot's coding agent is the closest applicable precedent**, and
  it converges on the same structural answer this ADR already chose:
  containment by **branch-name restriction**, not by trusting the model.
  Copilot's cloud agent can push code but "has no write access to main,
  develop, or any other branch" outside its own `copilot/`-prefixed
  branches, and any GitHub Actions workflow triggered by its PRs requires a
  human with write access to approve the run before it executes
  ([GitHub Docs: risks and mitigations for Copilot cloud agent](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations), [itnext.io architecture writeup](https://itnext.io/github-copilot-coding-agent-the-complete-architecture-behind-agentic-devops-at-enterprise-scale-1f42c1c132aa)). Finalize's
  "never push the target branch, only the invoking branch" design is the
  same pattern, one branch narrower (a single named branch rather than a
  prefix class) since finalize acts on a specific existing feature branch
  rather than creating its own.
- **OpenAI's Codex GitHub Action is documented vendor guidance for exactly
  this problem class:** "short-lived, least-privilege GitHub App
  installation tokens for each operation," respecting the user's existing
  branch protection, with an explicit recommendation to route any
  privileged action through a narrowly-scoped local MCP server rather than
  widening the agent's own credential
  ([OpenAI Developers: Codex admin setup](https://developers.openai.com/codex/enterprise/), [openai/codex-action](https://github.com/openai/codex-action)). This is the strongest available
  argument, from a vendor with production experience in exactly this
  problem class, for provisioning finalize a dedicated scoped credential
  rather than reusing the ambient `gh`/`glab` login (see §1's gap finding).
- **Anthropic's own system-card-level risk framing predicted this class of
  incident before it was observed in the wild** in production coding-agent
  deployments — the VentureBeat piece on the three-agent secret-leak
  incident specifically frames it as a predicted-then-confirmed risk, and
  Anthropic's general containment engineering post treats "credentials
  never enter the sandbox" and "match isolation strength to the user's
  capacity for oversight" as the load-bearing principles rather than
  per-tool permission lists
  ([VentureBeat](https://venturebeat.com/security/ai-agent-runtime-security-system-card-audit-comment-and-control-2026), [Anthropic: how we contain Claude](https://www.anthropic.com/engineering/how-we-contain-claude)). Neither source gives git/GitHub-specific
  permission guidance; both support the general shape (narrow the
  environment, don't rely on the model declining a bad instruction).

## Recommendation

**Grant finalize three narrowly-scoped rights and treat the credential that
carries them as a first-class design decision, not an implementation
detail — do not assume the ambient `gh`/`glab` login is an acceptable
credential by default.**

1. **Scope on paper:** `Contents: write` + `Actions: write` +
   `Pull requests: write`, single repository, no organization-wide grant
   (GitHub); `write_repository` + Developer role, or `api`-scoped project
   token if `glab` needs it (GitLab). This is necessary but not sufficient —
   see point 2.
2. **Scope in practice:** treat "which credential actually executes this"
   as an audit item finalize's `hex-init` surface should surface (mirroring
   the ADR's own decision to push DCO/signing discovery to `hex-init`) —
   specifically, flag when `gh`/`glab`'s ambient auth is broader than the
   three permissions above, and document that as an accepted, disclosed
   trade-off rather than a silent one. OpenAI's own Codex guidance argues
   for going further (a dedicated least-privilege token/App installation
   per operation) where a project is willing to provision one; finalize
   should support that path without requiring it.
3. **Force-push:** always `--force-with-lease --force-if-includes` together,
   never bare `--force`; keep the pre-rewrite backup ref (already decided
   in Threads) as the actual blast-radius control, since branch protection
   on a feature branch is the exception, not the rule, and the reflog
   recovery window is short and non-guaranteed.
4. **Convention discovery:** codify explicitly (not just as an emergent
   property) that checked-in files can only ever *narrow* finalize's
   behavior (stricter message format, additional required sign-off), never
   *widen* it (no file content can grant a new remote action or target a
   different branch/PR) — this is the concrete security property underneath
   the "declared vs. enforced" distinction the discussion already settled.
5. **DCO/signing:** re-sign with the human's own configured key/identity
   during rewrite (never a bot identity), and make the exact recomposed
   commit list — including which commits carry a new `Signed-off-by` —
   part of what's disclosed at the single approval gate, immediately before
   the force-push, not only at review's earlier Approve step. This closes
   the one real gap found in §4: the human currently reviews *semantic*
   correctness at Approve, but nothing in the decided design puts the final
   *rewritten commit list with its attestations* in front of them before it
   becomes an irreversible, legally-attesting, signed public record.
6. **Structural containment over behavioral trust:** adopt Copilot's
   pattern explicitly in the spec text — finalize's remote actions are
   scoped by branch identity (the one invoking branch and its one PR), not
   by hoping the model declines an out-of-scope instruction it read from a
   file. This is the one finding every vendor precedent in §5 agrees on.

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| [GitHub Docs: Permissions required for fine-grained PATs](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens) | Docs | current | Contents/Actions/Pull requests permission definitions and endpoint mapping |
| [GitHub Docs: Use GITHUB_TOKEN in workflows](https://docs.github.com/en/actions/how-tos/security-for-github-actions/security-guides/use-github_token-in-workflows) | Docs | current | workflow_dispatch/repository_dispatch exception to the anti-recursion guard |
| [GitHub changelog: GITHUB_TOKEN with workflow_dispatch](https://github.blog/changelog/2022-09-08-github-actions-use-github_token-with-workflow_dispatch-and-repository_dispatch/) | Vendor blog | 2022 (still current) | Confirms the exception and required `actions: write` permission |
| [`gh auth login` scopes discussion](https://github.com/cli/cli/discussions/7762) | Vendor forum | current | Default `repo, read:org, gist` scope, no expiry |
| [Adam Johnson: Git force push safely](https://adamj.eu/tech/2023/10/31/git-force-push-safely/) | Blog | 2023-10-31 | `--force-with-lease` stale-ref failure mode; `--force-if-includes` fix |
| [GitHub Docs: Available rules for rulesets](https://docs.github.com/en/enterprise-server@3.18/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) | Docs | current | Force-push restriction composes additively across protection sources |
| [GitHub Community: recovering from a force push](https://github.com/orgs/community/discussions/64693) | Vendor forum | current | Reflog-based recovery and its time limits |
| [Graphite: recovering lost commits with reflog](https://graphite.com/guides/recovering-lost-commits-git-reflog) | Guide | current | 30/90-day reflog expiry detail |
| [GitLab Docs: Protected branches](https://docs.gitlab.com/user/project/repository/branches/protected/) | Docs | current | Role + `allowed_to_force_push` model |
| [GitLab Docs: Token overview](https://docs.gitlab.com/security/tokens/) | Docs | current | Project access token scopes incl. `write_repository` |
| [GitLab Docs: CI/CD job token](https://docs.gitlab.com/ci/jobs/ci_job_token/) | Docs | current | `CI_JOB_TOKEN` inherits triggering user's permissions, session-scoped |
| [Cequence: prompt injection exposes AI agent credentials](https://www.cequence.ai/blog/ai/even-the-best-ai-agents-leak-secrets-prompt-injection-is-why/) | Security research blog | 2026 | PR-title injection against Claude/Gemini/Copilot; cline npm-token incident; Wiz prt-scan campaign |
| [VentureBeat: three AI coding agents leaked secrets](https://venturebeat.com/security/ai-agent-runtime-security-system-card-audit-comment-and-control-2026) | Journalism | 2026 | Same incident, framed against a vendor system card that predicted it |
| [GitInject (arXiv 2606.09935)](https://arxiv.org/html/2606.09935v1) | Academic paper | 2026 | Real-world prompt-injection attacks against AI CI/CD pipelines, adaptive-attack success rates |
| [Unit 42: Fooling AI agents](https://unit42.paloaltonetworks.com/ai-agent-prompt-injection/) | Security research | 2026 | Independent indirect-prompt-injection field study |
| [developercertificate.org](https://developercertificate.org/) | Primary source | v1.1 | Full DCO attestation text |
| [LF: DCO guidance](https://bestpractices.linuxfoundation.org/ip/contribution-mechanisms-dco.html) | Foundation guidance | current | DCO vs. CLA distinction (personal vs. employer-signable) |
| [codegenes.net: signatures gone after rebase](https://www.codegenes.net/blog/verified-signatures-are-gone-after-i-pressed-rebase-and-merge/) | Blog | current | Mechanics of signature invalidation on rewrite, re-sign commands |
| [Anthropic: How we contain Claude](https://www.anthropic.com/engineering/how-we-contain-claude) | Vendor engineering post | 2026 | Sandbox/credential-isolation principles applicable to a signing-oracle threat model |
| [GitHub Docs: Risks and mitigations for Copilot cloud agent](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations) | Docs | current | Branch-prefix write restriction, human-approval gate on triggered workflows |
| [OpenAI Developers: Codex admin setup](https://developers.openai.com/codex/enterprise/) | Docs | current | Short-lived least-privilege GitHub App tokens per operation; local-MCP-server pattern for privileged actions |
