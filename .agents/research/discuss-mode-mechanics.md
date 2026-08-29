# Multi-turn mode persistence in Claude Code — mechanics

Researched: 2026-08-27. Expires: 2027-02-28.
Question: how does a "discussion mode" stance survive 50+ turns, and what
can grim actually ship?

## Sources

- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/output-styles
- https://code.claude.com/docs/en/permission-modes
- https://code.claude.com/docs/en/sub-agents
- https://github.com/anthropics/claude-code/issues/37446 (open FR)

## Findings

- **Persistence ranking (drift-resistance, best→worst):**
  1. Hooks — UserPromptSubmit reinjects `additionalContext` fresh on every
     prompt; never ages. (The caveman/ponytail mechanism.)
  2. Rules / CLAUDE.md — system-prompt prefix, loaded once but NOT subject
     to conversation-history compaction. Static; no per-turn nudge.
  3. Skills — one-time injection into *compactable* history; not re-read on
     later turns; re-invoking yields "already loaded", not a fresh copy.
     Drifts AND can be summarized away on long sessions.
  4. Output styles — session-persistent but tone/format only; `/output-style`
     command removed v2.1.91; `keep-coding-instructions: true` gotcha.
- **Skill-writes-state + hook-reads is the documented pattern**: skill writes
  a state file on entry / deletes on exit; UserPromptSubmit hook checks it
  and conditionally injects "MODE ACTIVE". No native skill↔hook channel.
- **grim ships skills/rules/agents — not hooks.** Hook-based persistence is
  only reachable if an init-style skill *provisions* the hook into project
  settings with consent.
- **Plan mode**: tool-layer enforcement (Edit/Write/state-changing Bash
  blocked). A skill CANNOT enter it programmatically — open FR #37446
  (`mode: plan` frontmatter proposal). Entry is user/CLI only. Also
  incompatible with any mode that needs scoped writes (research artifacts).
- **Background subagents**: run background by default; results arrive as
  notifications on the next turn; permission prompts surface in the parent,
  attributed per subagent. Caps: 20 concurrent
  (CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS), 200/session lifetime, spawn-depth 3.
  Background agents lose Agent (except forks), AskUserQuestion, plan-mode
  tools — interactive chips are orchestrator-only.

## Implication recorded

Shippable-via-grim persistence = tiny always-on rule (stance, trigger) +
skill (full protocol), optionally hardened by an init-provisioned hook.
