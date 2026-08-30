# Discussion: finalize phase

State: handed-off → architect · Updated: 2026-08-29
Ratified: 2026-08-29 → architect
Confidence: Michael (owner) ratified at the restate-gate; decisions backed by 9 research artifacts, vintage 2026-08-29 (expire 2027-02-28)

## Intent

A hex run today ends at review/landing with no defined "finalize" step. The
owner's problem, in his words (2026-08-29, lightly cleaned from speech):

> We have different test qualities and in the finalize we want to fulfill the
> best test quality. And we want a ready-to-merge, ready-to-release pull
> request on a single branch where commits are squashed. For the squashing —
> maybe conventional commits, maybe other frameworks for generating
> changelogs — but in general the fragments should be reconsidered as the
> entire feature branch as a whole, so that no commits exist that fix issues
> on the branch for the things the branch just introduced. It's a user-facing
> idea: rebase on the main branch (or the PR's target branch), then make
> commits that are reasonable chunks to be in the git history forever — we
> always want a linear KISS history. We should also take care of different
> quality statuses — maybe even write that, e.g. that specific manual
> workflows should pass in CI. Maybe a draft merge/pull request gets set to
> ready, things like that.

Trigger: the adr_0008 landing (2026-08-29) did this by hand — 32 scaffolding
commits recomposed into 1 feat + 2 chores, rebase-free ff onto main — and the
owner flagged the missing method then (`hex.md › Memory`, /hex-discuss
candidate).

## Requirements

Provisional prose — IDs originate downstream.

- Finalize takes a converged, review-approved feature branch and: rebases it
  onto the target branch, then recomposes the whole branch diff into a
  minimal set of changelog-worthy conventional commits. No commit may fix or
  adjust something the branch itself introduced — scaffolding history never
  survives.
- Linear KISS history: the result fast-forwards (or cleanly rebases) onto
  the target; no merge commits leave the branch.
- Chunking principle: one commit per user-facing change; unrelated riders
  that hitchhiked on the branch split into their own chore/docs commits
  (adr_0008 precedent: 1 feat + 2 rider chores).
- Commit requirements are discovered per project and satisfied during the
  rewrite: DCO `Signed-off-by` where required, re-signing with the
  committer's configured key where signed commits are required.
- Verification runs at the strictest documented level before any push:
  local verification plus remote manual workflows (`workflow_dispatch`)
  triggered via the forge CLI and polled to green.
- Remote acts, all scoped to the feature branch + its PR: force-push the
  rewritten branch (consent = the invocation itself), trigger manual
  checks, flip the PR draft→ready once the quality bar holds. Never push
  the target branch, never merge.
- Forge-portable: `gh` and `glab` both first-class; the forge is discovered
  from project context. No forge CLI → degrade to local-only finalize and
  report what stays manual.
- A quality status is recorded ("maybe even write that") — home undecided
  (Open questions).
- Git-area behavior is team preference, not doctrine: merge-vs-rebase,
  squash policy, commit conventions differ per team — finalize must
  discover and respect the team's documented conventions rather than
  impose one style ("a lot of teams preference… double check how we can
  do that in a nice manner"). Discovery surfaces are an open research
  thread.
- Workspace invariant (owner preference, 2026-08-29): the checkout where
  the session was opened always reflects the long-living feature branch
  that becomes the PR. Parallel plan/WP work happens in agent worktrees;
  finalize operates on/against the primary workspace's branch.
- hex protocol conventions apply: single approval gate, one-line
  disclosures, capability classes not literal models in shipped files.

## Decisions

Working positions (2026-08-29, with the owner):

- **Mode surface: a new `/hex-finalize` command** (owner, chips,
  2026-08-29). Seventh command, not a phase of review or execute — the
  explicit invocation is what carries the force-push consent, and
  hex-review's never-commits / hex-execute's build-only contracts stay
  untouched. Review's Approve handoff emits `Next: /hex-finalize`.
- **Force-push is consented by invocation.** Invoking finalize is itself the
  explicit grant to force-push the feature branch after the rewrite. Scope:
  the feature branch only — the target branch is never pushed; merging the PR
  stays the owner's act (finalize delivers "ready-to-merge", it does not
  merge).
- **DCO / signing handled on the fly.** The rewrite detects the project's
  commit requirements and satisfies them while recomposing: `--signoff`
  where DCO is required, re-signing (committer's configured key) where
  signed commits are required — rebase silently invalidates signatures
  otherwise (see Research). Discovery/configuration of these requirements
  belongs to `/hex-init`'s surface (recorded in `hex.md`).
- **Manual CI workflows invoked via forge CLI.** `workflow_dispatch`-only
  workflows are triggered explicitly (`gh workflow run` / `glab` equivalent)
  so they report on the branch — resolving the required-check gotcha — then
  polled for results.
- **Outcome shape: ADR** (owner, chips, 2026-08-29). Drain → `/hex-architect`
  on this artifact — the change adds to hex's command surface and amends the
  never-push contract, the adr_0008 class of change. Next free claim range:
  C-8xx. The → ADR fast path floors at tier medium.
- **Expensive-test strategy is discovered, not invented.** Which
  higher-cost suites (integration etc.) count as release-grade is the
  project's own documented verification convention (project context /
  `hex.md › Pointers`); finalize runs the strictest documented level.

## Threads

- Open: chunking rule — when riders split out, when >1 commit is earned
  (adr_0008 precedent: 1 feat + 2 rider chores, judgment not rule).
  Research (D1) narrows it: three universals across all six convention-heavy
  projects (commit boundary = logical/independent change, never size;
  fixup/WIP/review-response commits never survive; message structure
  enforced not advisory) + two genuine team-preference axes (default commit
  count per PR: squash-to-one vs bisectable series; squash trigger test:
  topological "layers vs sausage" / empirical bisectability / temporal).
  Candidate shape: universals baked into finalize, the two axes discovered
  per team with a documented default.
- Open: audit-trail rule for pre-rewrite history — backup ref kept /
  deleted-on-land / never made. Research (D2) adds a second use: the
  backup ref is the anchor for `git range-diff <backup>..<rewritten>` —
  the reviewer-continuity evidence GitHub lacks natively (Rust built a
  triagebot range-diff bot to compensate; Gerrit/mailing-list flows get it
  natively). Candidate: keep ref until land, publish the range-diff in the
  PR quality ledger.
- Open: quality-status ledger — owner wants passed-checks status possibly
  *written* somewhere; where it lives is undecided.
- Open: remote-rights precision beyond force-push — PR create/mutate,
  draft→ready flip implied by the gh/glab position, not yet ratified.
- Answered by research (candidate position, ratify at gate):
  team-preference discovery. Finalize bakes in the three universals (D1),
  discovers the two preference axes + commit requirements per repo via the
  D3 recipe (files + non-admin forge reads), cross-checks declared vs
  enforced (B2), treats an empty/unreadable enforcement read as *unknown,
  never unenforced* (D3 pitfall: GitHub's rulesets endpoint silently omits
  legacy branch protection — `200 OK` empty array on a classic-protected
  repo), and — hex culture over field norm — detects silently but
  *discloses* the resolved conventions at the single gate, asking only on
  ambiguous signal (B3: the field is silent-with-override; Renovate's
  flip-flop shows why ambiguity needs the ask).
- Closed: end-to-end automation precedent — none exists; commit-boundary
  judgment is the un-automated part and hex's value-add (see Research).

## Research

- `.agents/research/discuss-finalize-changelog-frameworks.md` — changelog /
  commit-convention landscape (2026-08-29). Three families: enforcers
  (Conventional Commits + semantic-release/release-please — full automation,
  but standing CI push/tag rights and strict per-commit conformance that
  squash-merges break unless the squash message is enforced), format-agnostic
  generators (git-cliff, cocogitto — clean output on curated linear history,
  no repo permissions, lowest maintenance), and convention-free (Changesets /
  towncrier change-files per PR; GitHub `.github/release.yml` keyed on PR
  titles/labels — indifferent to history shape). Manual Keep-a-Changelog fine
  at low cadence, drifts as cadence rises; most-cited middle ground: automate
  generation, human reviews notable entries.
- `.agents/research/discuss-finalize-branch-automation.md` — branch-finalize
  automation precedent (2026-08-29). No end-to-end mechanism exists: six
  narrow layers (history curation via autosquash/git-absorb/stacked-diff
  tools; merge-time strategy buttons with non-interchangeable
  authorship/SHA/signature side effects — GitHub rebase-and-merge always
  mints new SHAs; required checks/rulesets/merge queues; draft→ready
  transitions; failure modes; agent workflows). Deciding commit boundaries
  and content is the one part nothing automates. Gotchas: a
  `workflow_dispatch`-only workflow can't be a required check until it has
  reported on the branch; merge queues need `merge_group` or checks silently
  never report; force-push detaches (not deletes) PR review comments as
  "outdated"; rebase silently invalidates GPG/SSH signatures unless
  re-signed. AI-agent workflows (GitHub cloud agents, OpenSpec, community
  Claude Code skills) converge on draft-PR-then-explicit-promotion as the
  finalize pattern.

- `.agents/research/discuss-finalize-teams-oss-landscape.md` — sweep W1/B1
  (2026-08-29): OSS landing-convention landscape, ranked. Kernel (dedicated
  rebase/merge maintainer doc + per-patch bisectability), Rust (bors-only
  merges, squash-timing rule during review), Node.js (self-contained
  bisectable commits, banned merge-button paths, required metadata),
  Chromium/Gerrit (amend-in-place single CL), Zephyr (DCO-rejected
  commits + squash-before-submit), Kubernetes (squash-to-one with layered
  exception), git itself (message micro-conventions), PostgreSQL (contrast:
  email/format-patch, no PR branch).

- `.agents/research/discuss-finalize-teams-policy-surfaces.md` — sweep
  W1/B2 (2026-08-29): where team git preferences are codified. Load-bearing:
  forge branch-protection/rulesets API (only truly authoritative surface),
  merge-strategy repo settings (cheapest single-call read), convention-tool
  configs (commitlint et al. — advisory unless a CI step or live hook runs
  them), bot/queue configs (authoritative only for the path they gatekeep),
  DCO/signing (lives in the forge required-checks list, not own config).
  Cross-cutting: config *presence* never implies enforcement — reliable
  signal is cross-referencing declared convention against forge
  required-checks/CI steps.

- `.agents/research/discuss-finalize-teams-agent-field.md` — sweep W1/B4
  (2026-08-29): AI-agent field. No agent product curates history after the
  fact: Copilot pushes WIP commits and lets draft→ready be the human
  finalize signal; Cursor batches one commit at completion; aider
  auto-commits conventionally with a config escape hatch; spec-driven
  frameworks (OpenSpec, spec-kit) are silent on git finalization entirely —
  a field gap, not a precedent. Claude Code's git safety protocol is the
  most explicit consent model found (never force-push/amend without
  explicit ask). Convention discovery converges on declarative checked-in
  files (CLAUDE.md/AGENTS.md, nearest-wins).

- `.agents/research/discuss-finalize-teams-adaptive-tools.md` — sweep W1/B3
  (2026-08-29): 11 preference-adaptive tools. Strongest patterns: Renovate's
  git-history dialect match (last ~20 commits, merges excluded; flip-flops
  on inconsistent repos), Mergify importing the repo's own
  branch-protection settings into merge conditions (platform-native read,
  not file sniffing), Dependabot's silent prefix detection with explicit
  config override, jj's directory-presence colocation switch. gh CLI PR
  templates the contrast case (sniffs correctly, silently skips applying on
  the common path). Universal: every tool detects silently-with-override;
  none ask the user before deciding.

- `.agents/research/discuss-finalize-series-shape-rules.md` — sweep W2/D1
  (2026-08-29): final series-shape rules across kernel, Node.js, Kubernetes,
  Rust, Zephyr, curl. Three universals (logical-change commit boundary;
  no fixup/WIP/review-response commits survive; enforced message
  structure) vs two conflict axes (default commit count per PR; what test
  triggers the squash decision — topological, bisectability, temporal).

- `.agents/research/discuss-finalize-rewrite-timing.md` — sweep W2/D2
  (2026-08-29): five rewrite-timing models — amend-in-place per round
  (Gerrit, Change-Id), squash-once-at-end (Rust bors squash; K8s/Node/
  Zephyr policy), fixup-then-single-autosquash (author's discretion),
  never-rewrite-once-exposed (kernel; names invalidated CI as the cost),
  new-artifact-per-revision (PostgreSQL email flow) — plus rule-less
  GitHub Flow as baseline, whose missing force-push diff-of-diff is why
  Rust built a range-diff bot. Finalize = the squash-once-at-end model;
  rewrite must precede check-triggering (checks must report on final SHAs).

- `.agents/research/discuss-finalize-detection-recipe.md` — sweep W2/D3
  (2026-08-29): concrete convention-read recipe. Non-admin-readable: all
  checked-in files, GitHub merge-strategy fields + rulesets/
  rules-for-branch (`Metadata: read`; unauthenticated on public repos),
  GitLab base merge-method/squash fields. Admin-gated: GitHub legacy
  branch-protection endpoint, GitLab `push_rule`. Biggest pitfall: the
  readable rulesets endpoint returns rules from rulesets ONLY — a repo
  protected via classic branch protection returns `200 OK` + empty array,
  which a naive tool misreads as "nothing enforced".

## Related

- `.agents/adrs/adr_0008_pre_plan_discussion_mode.md` — precedent class
  (command-surface ADR); this discussion is a dogfood run of its mode.
- `.agents/memory/hex.md` › Memory, adr_0008 landing note — the hand-run
  finalize (32 scaffolding commits → 1 feat + 2 chores) that triggered this.
- `hex/hex-core/references/protocol.md` — handoff contract; home of the
  conventions a remote-rights amendment must reconcile with (hex today
  never pushes).
- `hex/DESIGN.md` — constitution; a new mode needs a dated round.
- Research: the two artifacts above.

Files/interfaces the eventual work touches: new `hex/hex-finalize/` member;
`hex/hex-core/references/protocol.md` (scoped remote-rights amendment);
`hex/hex-init` (audit items: DCO, signing, forge/CLI); `hex/hex.toml` +
`hex/publish.toml` (member row); `hex/DESIGN.md`, `hex/README.md`,
`hex/CHANGELOG.md`; the ADR itself at
`.agents/adrs/adr_0009_finalize_phase.md` (claims C-8xx — C-7xx taken by
adr_0008).

Out of scope: merging/landing on the target branch; changelog file
generation; inventing test tiers hex would own.

## Open questions

- [NEEDS CLARIFICATION: keep a backup ref of the pre-rewrite history?]
  Recommended: create `backup/<branch>-pre-finalize` before the force-push,
  delete after the PR merges — adr_0008 precedent, zero cost, reversible
  until land.
- [NEEDS CLARIFICATION: where does the quality-status ledger live?]
  Recommended: a quality section in the PR body — forge-native, visible at
  review time, no new artifact class; one-line mirror in the plan's Status
  block when a plan exists.
- [NEEDS CLARIFICATION: is changelog generation in scope?] Recommended:
  no — finalize shapes history to be generator-friendly (the git-cliff
  family reads curated linear history cleanly, per Research); generation
  stays a release-time concern.
- [NEEDS CLARIFICATION: exact PR-mutation rights?] Recommended: create the
  PR when absent, edit its title/body, flip draft→ready — never merge,
  never touch branch protection or the target branch.

## Verification

- Eventual work checked by the arcana convention: `grim build` per changed
  member + `task publish -- --dry-run` green.
- Dogfood: run `/hex-finalize` on its own implementation branch — observe
  recomposed changelog-worthy commits, DCO/signature status intact, linear
  ff onto main; where a remote exists, observe `workflow_dispatch` trigger
  via forge CLI and the draft→ready flip.
