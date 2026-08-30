# Research: Pre-plan clarification/elaboration phases across spec-driven dev tools

## Metadata

**Date:** 2026-08-30
**Domain:** Developer tooling / AI agent UX
**Triggered by:** hex-discuss UX discussion
**Expires:** 2027-02-28

## Direct Answer

Tools split into three patterns. (1) **Fixed-budget, user-paced**: spec-kit's
`/clarify` and Kiro's Feature Specs ask a capped batch of questions per turn
and require the *user* to explicitly approve/re-invoke before moving on — no
tool-side "done" judgment. (2) **Front-loaded, then autonomous**: Kiro Quick
Spec and Devin's default mode collect what they need once (or opportunistically
mid-plan) and then proceed without further gates. (3) **Frontier/round-based
with background research**: the `grill-me` skill (used as OpenSpec's
clarification step in at least one documented integration) is the only
mechanism found that both dispatches background sub-agents for factual
lookups *while the interview continues* and batches questions by dependency
level rather than by a fixed count — but even it ends only on explicit user
confirmation, never unilateral AI judgment. No tool surveyed lets the AI
silently decide clarification is "done" and proceed uninterrupted; every
approach either caps questions and hands control back to the user, or
requires an explicit approval/confirm step.

## Key Findings

1. **spec-kit `/clarify` is on-demand, not automatic research** — it reads the existing spec text and flags ambiguity; it does not fetch new context. Capped at "up to five targeted questions" per invocation; docs say "run it as many times as needed before planning," so the user decides when clarification is sufficient and must explicitly invoke `/speckit.plan` next — no auto-progression. [github/spec-kit agentic-sdd](https://github.github.com/spec-kit/reference/agentic-sdd.html)
2. **spec-kit answers are folded back immediately** into a dated `## Clarifications` section of the spec as each question resolves, rather than held until the end of a batch. [github/spec-kit agentic-sdd](https://github.github.com/spec-kit/reference/agentic-sdd.html)
3. **Kiro Feature Specs use a 3-phase gate** (requirements → design → tasks); the agent must call a `userInput` tool and receive explicit "yes/approved" before advancing each phase — termination of each phase is 100% user-controlled by design, "preventing runaway automation." [Kiro spec agent prompt gist](https://gist.github.com/notdp/19822831b54190bd9c6b34f6b69fadeb), [Kiro Feature Specs docs](https://kiro.dev/docs/specs/feature-specs/)
4. **Kiro also ships an alternate "Quick Spec" mode** that inverts the pattern: all clarifying questions are front-loaded up front, then all three phases run autonomously with no per-phase approval gates — an explicit trade of control for speed on well-understood features. [Kiro Quick Spec docs](https://kiro.dev/docs/specs/quick-spec/)
5. **Task Master (`eyaltoledano/claude-task-master`) has no clarification interview at all.** It expects a pre-written PRD in `.taskmaster/docs/` and runs `parse-prd` directly on it; "research" (live web sources) is opt-in per-command via a `--research` flag (`expand --research`, `update --research`), never automatic and never part of a Q&A phase. [Task Master tutorial](https://github.com/eyaltoledano/claude-task-master/blob/main/docs/tutorial.md), [PRD quick-start](https://docs.task-master.dev/getting-started/quick-start/prd-quick)
6. **aider has no dedicated clarify phase**; the documented workaround is a manual mode switch — `/ask` (consults, never edits) then `/architect` (a separate model proposes a plan, another model implements it) — clarification is a user-driven back-and-forth across modes, not a structured interview the tool runs. [aider chat modes docs](https://aider.chat/docs/usage/modes.html)
7. **Claude Code plan mode interleaves read-only codebase research with clarifying questions**; neither question count nor depth is fixed by the tool — it's steered by user prompting (e.g. "ask at least 5 questions") or left to model judgment. The user iterates on a drafted `plan.md` and must explicitly exit plan mode to unlock edits. [Zenva plan mode guide](https://academy.zenva.com/claude-code-plan-mode/), [Build This Now planning modes](https://www.buildthisnow.com/blog/guide/mechanics/planning-modes)
8. **Cursor Plan Mode (2.1+) auto-triggers clarifying questions** when it detects ambiguity in the request, rather than running every time; the agent researches the codebase and produces a reviewable, user-editable plan before build — termination is the user approving/editing that plan, not a question-count limit. [Cursor Plan Mode docs](https://cursor.com/docs/agent/plan-mode), [Digital Applied on Cursor 2.1](https://www.digitalapplied.com/blog/cursor-2-1-clarifying-questions-plans)
9. **Devin asks clarifying questions opportunistically during planning** when it judges details are missing, but has no mandatory interview gate by default; a separate `megaplan` command explicitly triggers a heavier clarify-before-plan pass reserved for large/ambiguous tasks. [Devin agents101](https://devin.ai/agents101), [CrabTalk plans vs tasks](https://crabtalk.ai/blog/plans-vs-tasks-agent-design)
10. **The `grill-me` skill dispatches background sub-agents for facts, not decisions** — "when a frontier question needs something the environment can settle, it dispatches a sub-agent to go and find out rather than asking you," and does not block on that: only questions *downstream* of a running exploration wait. This is the one mechanism found that runs research concurrently with an ongoing interview rather than as a separate blocking step. [mattpocock/skills grilling.md](https://github.com/mattpocock/skills/blob/main/docs/productivity/grilling.md)
11. **`grill-me` paces questions by dependency "frontier," not a fixed count or one-at-a-time**: "each round asks the whole frontier: every decision whose prerequisites are already settled, and nothing else... two questions never share a round if one depends on the other" — roughly 13 questions land in ~3 rounds, each with a recommended answer attached. [mattpocock/skills grilling.md](https://github.com/mattpocock/skills/blob/main/docs/productivity/grilling.md)
12. **`grill-me` terminates only on explicit user confirmation**: "the session ends when the frontier is empty, and it will not act on what you agreed until you confirm you have reached a shared understanding" — the empty frontier is necessary but not sufficient; the AI never unilaterally starts work. [mattpocock/skills grilling.md](https://github.com/mattpocock/skills/blob/main/docs/productivity/grilling.md)
13. **OpenSpec's core docs do not mandate any clarification mechanic** — they frame the workflow as flexible "actions," not rigid phase gates, and describe proposals as capturing "intent, scope, and approach" supplied by the human. The `grill-me`-powered interview is a practitioner integration (documented on a third-party blog), not built into stock OpenSpec's `/opsx:propose`. [OpenSpec concepts.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md), [intent-driven.dev on OpenSpec+OpenCode](https://intent-driven.dev/blog/2026/05/10/spec-driven-development-openspec-opencode/)
14. **A comparable lightweight community pattern (`snarktank/ai-dev-tasks` `create-prd.md`)** caps questions at "3-5 critical gaps," batches them all at once in lettered multiple-choice form (answerable as "1A, 2C, 3B"), and lets the *AI* decide when core problem/goal/scope/success-criteria gaps are closed enough to write the PRD — the one surveyed case of AI-judged (not user-judged) termination, at the cost of a much smaller question budget. [snarktank/ai-dev-tasks create-prd.md](https://github.com/snarktank/ai-dev-tasks/blob/main/create-prd.md)

## Sources

| Source | Date accessed |
|---|---|
| [github/spec-kit — Agentic SDD reference](https://github.github.com/spec-kit/reference/agentic-sdd.html) | 2026-08-30 |
| [github/spec-kit repo](https://github.com/github/spec-kit) | 2026-08-30 |
| [Kiro — Feature Specs docs](https://kiro.dev/docs/specs/feature-specs/) | 2026-08-30 |
| [Kiro — Quick Spec docs](https://kiro.dev/docs/specs/quick-spec/) | 2026-08-30 |
| [Kiro spec agent system prompt (gist)](https://gist.github.com/notdp/19822831b54190bd9c6b34f6b69fadeb) | 2026-08-30 |
| [eyaltoledano/claude-task-master — tutorial.md](https://github.com/eyaltoledano/claude-task-master/blob/main/docs/tutorial.md) | 2026-08-30 |
| [Task Master — PRD quick-start docs](https://docs.task-master.dev/getting-started/quick-start/prd-quick) | 2026-08-30 |
| [aider — Chat modes docs](https://aider.chat/docs/usage/modes.html) | 2026-08-30 |
| [Zenva Academy — Claude Code Plan Mode](https://academy.zenva.com/claude-code-plan-mode/) | 2026-08-30 |
| [Build This Now — Planning Modes guide](https://www.buildthisnow.com/blog/guide/mechanics/planning-modes) | 2026-08-30 |
| [Cursor — Plan Mode docs](https://cursor.com/docs/agent/plan-mode) | 2026-08-30 |
| [Digital Applied — Cursor 2.1 clarifying questions](https://www.digitalapplied.com/blog/cursor-2-1-clarifying-questions-plans) | 2026-08-30 |
| [Devin — agents101](https://devin.ai/agents101) | 2026-08-30 |
| [CrabTalk — Plans vs tasks](https://crabtalk.ai/blog/plans-vs-tasks-agent-design) | 2026-08-30 |
| [mattpocock/skills — grilling.md](https://github.com/mattpocock/skills/blob/main/docs/productivity/grilling.md) | 2026-08-30 |
| [Fission-AI/OpenSpec — concepts.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md) | 2026-08-30 |
| [intent-driven.dev — OpenSpec + OpenCode](https://intent-driven.dev/blog/2026/05/10/spec-driven-development-openspec-opencode/) | 2026-08-30 |
| [snarktank/ai-dev-tasks — create-prd.md](https://github.com/snarktank/ai-dev-tasks/blob/main/create-prd.md) | 2026-08-30 |
