# Research: How AI Coding Agents Handle Branch-Landing/Finalization and Team Git Conventions

<!--
Technology-landscape research. Filename and location: this project's
documented research convention (.agents/research/).
Owner: a researcher worker. Handoff to: /hex-architect, /hex-plan.

Purpose: persist landscape findings that inform ADRs, plans, and design
decisions. Findings decay - check the Expires date before trusting them.
-->

## Metadata

**Date:** 2026-08-29
**Domain:** devops (git workflow / agentic finalization)
**Triggered by:** `/hex-discuss "finalize phase"`
**Expires:** 2027-02-28

## Direct Answer

No surveyed tool or framework treats "finalize/land a branch" as a distinct,
consent-gated phase with its own name. The behavior splits into three
patterns:

1. **Incremental-commit, draft-PR, human-cleans-up** (GitHub Copilot coding
   agent, OpenAI Codex cloud agent by default): the agent commits as it goes,
   opens/updates a PR early, and leaves history curation and merge to the
   human.
2. **Batch-commit-at-completion** (Cursor cloud/background agents, per
   community docs): the agent suppresses per-step commits and produces one
   commit representing the finished task, still leaving PR creation as an
   explicit, reviewable step.
3. **Local auto-commit with an escape hatch** (aider): commits after every
   edit by default, but exposes a flag/config/prompt to turn it off or
   reshape the message convention — the team decides, per-repo, once.

Spec-driven frameworks (OpenSpec, github/spec-kit) do not specify this step
at all — their artifact pipeline (propose/specify → plan → tasks → implement,
or propose → apply → archive) ends at "code + updated spec exist"; landing
that onto `main` is left to whatever git/GitHub flow the team already uses.
Any git discipline (clean tree before starting, a commit per lifecycle
phase, a main-branch check before archiving) is a **community add-on layer**
(skills/blog posts), not a documented core behavior of either framework.

Convention discovery converges on one mechanism across tools: a checked-in
instructions file (`CLAUDE.md`, `AGENTS.md`, or a repo-specific
`COMMIT_CONVENTION.md`) that the agent reads at session start; the emerging
`AGENTS.md` standard formalizes "nearest file wins, explicit prompt
overrides file" as a cross-tool discovery rule. No tool auto-detects
conventions by, e.g., statistically inspecting `git log` — discovery is
declarative (a file), not inferred.

Consent for the destructive end of the spectrum (force-push, amend,
squash/rebase) is uniformly opt-in and explicit. Claude Code's own git
safety protocol (observed directly in this session's system instructions,
consistent across published best-practice guides) is the most fully
specified: never `push --force`, never skip hooks, never amend an existing
commit — always create a new one — unless the user explicitly asks; prefer
naming files over `git add -A`/`git add .`. No other surveyed tool documents
an equivalently explicit "never do X unless asked" list; Copilot and Codex
describe *what* they do (push commits, open PRs) without documenting a
negative list of what they withhold consent for.

## Technology Landscape

### Trending (gaining momentum)

| Tool/Pattern | Adoption Signal | Key Benefit | Relevance |
|--------------|------------------|-------------|-----------|
| `AGENTS.md` as cross-tool convention file | Adopted by Claude Code, Codex, Cursor per community guides; positioned as the shared alternative to per-tool `.cursorrules`/`CLAUDE.md` | One file, every agent respects the same branch/commit/PR rules | Directly answers "how is team git-convention preference discovered" — declarative, nearest-file-wins |
| Batch-commit-at-completion (`commitAfterEachStep: false`) | Cursor cloud agent design choice, documented in community deep-dives (official docs page fetched did not confirm the setting name) | Avoids 30 exploratory commits polluting history; one commit = one reviewable unit | Precedent for a "squash-on-finalize" default rather than curate-after-the-fact |
| Draft PR + incremental WIP commits, human iterates via PR comments | Copilot coding agent (official GitHub docs), described as core UX | Full visibility into agent progress; cheap to abandon | Precedent for *not* curating — draft state signals "not yet a landing candidate" |

### Established (proven, widely accepted)

| Tool/Pattern | Status | Notes |
|--------------|--------|-------|
| aider auto-commit per edit, Conventional Commits by default, `--no-auto-commits` / `AIDER_AUTO_COMMITS` / `.aider.conf.yml` escape hatch | Mature, long-shipped | Oldest of the surveyed tools on this axis; the "auto-commit is default, team turns it off" model is the most battle-tested consent pattern found |
| Claude Code git safety protocol (never force-push/amend/skip-hooks without explicit ask; new commits preferred over amend) | Established, documented in this project's own CLAUDE.md instructions and consistent with public best-practice write-ups | Sets the bar for explicitness other tools' public docs don't match |
| GitHub Copilot coding agent: ephemeral GitHub Actions sandbox, push-as-you-go, checklist-tracked PR description | Mature, GA feature | Human stays "in control throughout" via PR review comments, not via a separate finalize step |

### Emerging (early but promising)

| Tool/Pattern | Signal | Worth Watching Because |
|--------------|--------|-------------------------|
| Community "git discipline" skill layered onto OpenSpec (clean tree before Propose, commit after Apply/Verify, main-branch check before Archive) | Described in a third-party deep-dive (redreamality.com), not in Fission-AI's own `docs/concepts.md` | Shows the market wants a git-aware finalize gate that spec-driven frameworks don't ship — a gap a hex-side discussion-mode/finalize design could fill natively instead of bolting on |
| `git-squash-clean`-style community skills for Claude Code (history cleanup before merge) | Listed on third-party skill marketplaces; page fetch 429'd, unverified beyond title/description | Independent evidence that "clean up my mess before I open the PR" is a wanted, currently third-party-only capability |

### Declining (losing mindshare)

None identified — this is a newly forming practice area, not one with legacy approaches being displaced.

## Design Patterns Worth Considering

- **Draft-PR-as-provisional-state** — open the PR in draft immediately, push
  incremental commits, let draft→ready-for-review be the human's explicit
  "this is finalized" signal. Used by: GitHub Copilot coding agent
  ([GitHub Docs](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-on-github)).
  Claude Code's review workflow already special-cases this by skipping
  draft PRs for automated review.
- **Squash-at-completion, not squash-after-the-fact** — suppress per-step
  commits during execution rather than rewriting history later; avoids
  ever needing a destructive rebase. Used by: Cursor cloud agents (per
  community docs, unconfirmed against Cursor's own automations page).
- **Convention-as-checked-in-file, nearest-wins** — discover team
  preferences by reading a file at session start rather than inferring from
  history; explicit user prompt always overrides the file. Used by:
  AGENTS.md spec, Claude Code (`CLAUDE.md`), aider (`.aider.conf.yml` +
  `--commit-prompt`).
- **Escape-hatch-not-negotiation** — ship a safe default (auto-commit on,
  Conventional Commits) but make the override a single flag/config key
  rather than a conversation the agent has to infer. Used by: aider
  (`--no-auto-commits`, `AIDER_AUTO_COMMITS`).

## Key Findings

1. None of the eight surveyed systems document a named "finalize" phase
   distinct from "keep committing" / "open a PR" — the landing step is
   either implicit (Copilot, Codex: PR review IS the finalize gate) or
   externalized entirely to standard git/GitHub (OpenSpec, spec-kit).
2. Every tool that commits autonomously treats force-push and history
   rewrite as opt-in-only; Claude Code is the only one with a fully
   documented negative list (what it will never do without being asked).
   [Claude Code GitHub Actions docs](https://code.claude.com/docs/en/github-actions),
   this session's own system instructions.
3. Team git-convention discovery has converged on a single mechanism
   (declarative file, nearest-wins, prompt overrides file) rather than
   per-tool bespoke config — see the AGENTS.md spec discussion
   ([morphllm.com guide](https://www.morphllm.com/agents-md-guide)).
4. Spec-driven frameworks (OpenSpec, spec-kit) are silent on git
   finalization in their own docs; what git discipline exists around them
   is a third-party skill/blog layer, not a first-party feature
   ([Fission-AI/OpenSpec concepts.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md)
   vs. [redreamality.com deep-dive](https://redreamality.com/garden/notes/openspec-guide/)).
5. Cloud/background agents (Copilot, Codex, Cursor) all push directly to a
   branch they control and treat "open the PR" as the point where a human
   is expected to look — none of the three official-docs pages fetched
   describe an explicit force-push or history-rewrite capability, i.e. by
   default their write scope stops short of destructive git operations.

## Recommendation

Not in scope for a neutral discovery survey — deferred to depth-lane
analysis and the ADR itself.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| [code.claude.com/docs/en/github-actions](https://code.claude.com/docs/en/github-actions) | Docs (fetched) | 2026-08-29 | Claude Code GitHub Action: permissions, push/PR behavior, CLAUDE.md as source of standards |
| Claude Code system instructions, "Git Safety Protocol" (this session) | First-party, observed directly | 2026-08-29 | Explicit consent model: no force-push/amend/skip-hooks without ask |
| [docs.github.com — Use Copilot cloud agent on GitHub](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-on-github) | Docs | 2026-08-29 | Draft PR opened immediately, incremental WIP commits, checklist in PR description |
| [github.blog — coding agent 101](https://github.blog/ai-and-ml/github-copilot/github-copilot-coding-agent-101-getting-started-with-agentic-workflows-on-github/) | Blog (official) | 2026-08-29 | Copilot coding agent workflow overview |
| [openai.com — Introducing Codex](https://openai.com/index/introducing-codex/) | Blog (official) | 2026-08-29 | Codex cloud agent: sandbox commit, review/open-PR/integrate choice |
| [community.openai.com — Improve how Codex commits and pushes](https://community.openai.com/t/improve-how-codex-commits-and-pushes-to-branches/1363321) | Forum | 2026-08-29 | Signals Codex's commit/push behavior is a live pain point for users, not fully documented |
| learn.chatgpt.com/docs/cloud (Codex cloud docs) | Docs (fetched, thin) | 2026-08-29 | Confirms "review → follow-up or open PR" flow; no documented squash/consent detail |
| [aider.chat/docs/git.html](https://aider.chat/docs/git.html) | Docs | 2026-08-29 | Auto-commit default, Conventional Commits, `--no-auto-commits`, `--commit-prompt` |
| [cursor.com/blog/agent-best-practices](https://cursor.com/blog/agent-best-practices) | Blog (official) | 2026-08-29 | Cursor agent workflow guidance |
| [cursor.com/docs/cloud-agent/automations](https://cursor.com/docs/cloud-agent/automations) | Docs (fetched) | 2026-08-29 | PR-opening tool enabled by default for automations; did not confirm `commitAfterEachStep` |
| [stevekinney.net — Cursor background agents](https://github.com/stevekinney/stevekinney.net/blob/main/courses/ai-development/cursor-background-agents.md) / madewithlove.com blog | Community docs | 2026-08-29 | Source for `commitAfterEachStep: false` / squash-at-completion pattern (unconfirmed by official docs) |
| [github.com/Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) + [docs/concepts.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md) | Repo + docs (fetched) | 2026-08-29 | Propose→apply→archive lifecycle; archive folds specs.md back, no git discipline documented in core |
| [redreamality.com — OpenSpec deep dive](https://redreamality.com/garden/notes/openspec-guide/) | Blog (community) | 2026-08-29 | Describes a third-party skill enforcing git discipline around OpenSpec phases |
| [github.com/github/spec-kit](https://github.com/github/spec-kit) + [reference/workflows.html](https://github.github.io/spec-kit/reference/workflows.html) | Repo + docs | 2026-08-29 | Command pipeline constitution→specify→clarify→plan→tasks→analyze→implement; no finalize/commit step documented |
| [morphllm.com — AGENTS.md guide](https://www.morphllm.com/agents-md-guide) | Guide (community) | 2026-08-29 | AGENTS.md nearest-file-wins discovery convention, cross-tool adoption |
| [mcpmarket.com/tools/skills/git-squash-clean](https://mcpmarket.com/tools/skills/git-squash-clean) | Skill listing | 2026-08-29 | Community skill for pre-merge history cleanup; fetch returned HTTP 429, content unverified beyond title |
| [gist.github.com/rvanbaalen — conventional-commits skill](https://gist.github.com/rvanbaalen/50769263f3b96f58c27aed4d4e11dc54) | Gist (community) | 2026-08-29 | Example of convention encoded as an installable skill rather than a plain instructions file |
| [awattar/claude-code-best-practices — COMMIT_CONVENTION.md](https://github.com/awattar/claude-code-best-practices/blob/main/.github/COMMIT_CONVENTION.md) | Repo (community) | 2026-08-29 | Example of a repo-specific convention file pattern, parallel to CLAUDE.md/AGENTS.md |
