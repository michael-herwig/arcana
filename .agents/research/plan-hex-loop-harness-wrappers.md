# Research: cross-harness /goal wrapper and skill-invocation syntax for hex-loop

## Metadata

**Date:** 2026-09-23
**Domain:** cli
**Triggered by:** hex-loop skill design (`/goal <body>` wrapper where a goal
command exists, else plain prompt); fills gaps left by
`discuss-goal-loop-priorart.md`/`-community.md`/`-recon.md` (Claude Code
`/goal` mechanics, Ralph-loop prior art — not repeated here)
**Expires:** 2027-03-23

## Direct Answer

Three harnesses ship a native `/goal`-shaped stop-condition command today:
Claude Code, OpenAI Codex CLI, and Cursor CLI (gated rollout). Copilot CLI,
Gemini CLI, and OpenCode do not — only open feature requests or third-party
plugins. No harness documents that `/goal <text>` parses an embedded
skill/slash invocation inside the condition string; Claude Code's own docs
are silent on it (per priorart), and Codex's cookbook says goal text is a
plain outcome description, not a prompt-invocation framework. Skill
phrasing inside the body is harness-specific: only Claude Code and Copilot
CLI officially document a natural-language `/skill-name`-mention pattern
that reliably triggers a named skill.

## Per-Harness Table

| Harness | Goal/stop-condition command | Char cap | Skill invocation syntax in prompt text |
|---|---|---|---|
| Claude Code | `/goal <condition>`, session-scoped, evaluator-driven | ≤4,000 chars (official docs, see priorart) | `/skill-name` as leading slash command; "use the X skill" also works |
| OpenAI Codex CLI | `/goal <outcome>` + `pause`/`resume`/`clear`; shipped 0.128.0 (2026-04-30) | No documented cap | Deprecated custom prompts via `/prompts:<name>` (`$CODEX_HOME/prompts/`); current Skills auto-discovered/description-matched — explicit `/skill-name` invocation **unverified** |
| Cursor CLI | `/goal`, gated rollout since 2026-08-11, active/paused status, independent of skills | Not documented | Skills picked from `/` menu (Enter = one-shot, Option+Enter = pinned Custom Mode); free-text `/skill-name` mention outside menu **unverified** |
| GitHub Copilot CLI | None native. "Autopilot" runs until Copilot itself judges done (no user condition text). `.copilot/goals.md` open request, unshipped ([#3364](https://github.com/github/copilot-cli/issues/3364)) | N/A | Docs-confirmed: name skill after `/` in a sentence, e.g. *"Use the /frontend-design skill to ..."* ([docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)) |
| Gemini CLI | None found in official docs or search | N/A | No explicit `/skill-name` invocation confirmed; auto-activates via description-match (`activate_skill` tool); `/skills list\|link\|reload` manage only. Naming in prose plausible, **unverified** |
| OpenCode | None native; 3 open requests ([#31762](https://github.com/anomalyco/opencode/issues/31762), [#49205](https://github.com/anomalyco/opencode/issues/49205), [#29721](https://github.com/anomalyco/opencode/issues/29721)); 3rd-party plugins fill gap | N/A | Skills invoked via agent, not TUI slash; needs `.opencode/commands/*.md` wrapper for real `/command-name` |

## Recommendation

**Wrapper rule** (harness-neutral, matches the task's stated design):
emit `/goal <body>` when the target harness is Claude Code, Codex CLI, or
Cursor CLI (all three confirmed to ship a real `/goal`); emit the bare
prompt body otherwise (Copilot CLI, Gemini CLI, OpenCode, and anything
unlisted) — those harnesses either lack the concept entirely or gate it
behind an unstable rollout.

**Neutral skill-invocation phrasing**: an imperative sentence naming the
skill with a leading slash — `Run the /hex-plan skill to <action>.` —
mirrors the one pattern Claude Code and Copilot CLI both document as
reliable. It degrades gracefully elsewhere: Claude Code parses the leading
`/hex-plan` as a slash command; Codex CLI and Gemini CLI fall back to
description/name-matching skill discovery using the visible name; OpenCode
and undocumented harnesses at least get the name as a strong hint. No
source confirms one phrasing is guaranteed across all six — best-effort
common denominator, not a proven universal trigger.

## Sources (all accessed 2026-09-23)

| Source | Type | Relevance |
|--------|------|-----------|
| [Codex cookbook — Using Goals](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex) | Official | `/goal` syntax/lifecycle, no cap, no skill framing |
| [simonwillison.net — Codex 0.128.0 adds /goal](https://simonwillison.net/2026/Apr/30/codex-goals/) | Blog | Ship date 2026-04-30 |
| [Codex slash-commands](https://developers.openai.com/codex/guides/slash-commands/) / [custom-prompts](https://developers.openai.com/codex/custom-prompts) | Official | `/prompts:<name>`, `$CODEX_HOME/prompts`, deprecated for Skills |
| [Cursor CLI changelog](https://cursor.com/docs/cli/changelog) | Official | `/goal` shipped 2026-08-11, gated, no cap |
| [Cursor CLI usage docs](https://cursor.com/docs/cli/using) | Official | Skill via `/` menu, Option+Enter Custom Mode |
| [Copilot CLI — agent skills](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) | Official | Documented `/skill-name`-in-sentence pattern |
| [Copilot CLI — autopilot](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/autopilot) | Official | Autopilot has no user-set condition text |
| [github/copilot-cli#3364](https://github.com/github/copilot-cli/issues/3364) | GH issue | `.copilot/goals.md` request, unshipped |
| [Gemini CLI — Agent Skills](https://geminicli.com/docs/cli/skills/) | Official | Discovery/activation mechanism, `/skills list\|link\|reload`; no invocation-by-name |
| [anomalyco/opencode#31762](https://github.com/anomalyco/opencode/issues/31762)/[#49205](https://github.com/anomalyco/opencode/issues/49205)/[#29721](https://github.com/anomalyco/opencode/issues/29721) | GH issues | No native `/goal`, all open |
| [devgenius.io — Commands/skills/agents in OpenCode](https://blog.devgenius.io/no-commands-skills-and-agents-in-opencode-whats-the-difference-cf16c950b592) | Blog | Skills via agent; `.opencode/commands/*.md` wrapper |
