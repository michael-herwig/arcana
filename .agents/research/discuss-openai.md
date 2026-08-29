# Pre-Implementation Discussion — OpenAI/Codex Lane

Researched: 2026-08-28. Expires: 2027-02-28.

## Sources

- https://developers.openai.com/codex/learn/best-practices (redirects to learn.chatgpt.com/guides/best-practices) — primary Codex docs: Plan mode + "interview approach"
- https://developers.openai.com/blog/run-long-horizon-tasks-with-codex — primary OpenAI Developers blog: 4-artifact spec-driven workflow
- https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide — primary Cookbook: bias-to-action, when to skip planning
- https://developers.openai.com/cookbook/examples/gpt-5/gpt-5-2_prompting_guide — primary Cookbook, newest GPT-5.x guide: default-to-no-clarification stance
- https://developers.openai.com/codex/workflows (redirects to learn.chatgpt.com/docs/prompting) — primary Codex docs: `/plan` negotiation example
- https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide — primary Cookbook, original GPT-5 guide: tool-preamble pattern
- https://developers.openai.com/cookbook/examples/gpt-5/gpt-5-1_prompting_guide — primary Cookbook, GPT-5.1 guide: TODO/plan tool + urgency-conditional clarification
- https://developers.openai.com/codex/codex-manual.md (redirects to learn.chatgpt.com/docs/codex-manual.md) — primary Codex reference: Plan mode + AGENTS.md + 4-part prompt convention

## Findings

### 1. Praise / what demonstrably works

- Plan mode (`/plan` or Shift+Tab) is called "the easiest and most effective option" for complex tasks: it lets Codex "gather context, ask clarifying questions, and build a stronger plan before implementation" (best-practices doc, corroborated verbatim in codex-manual).
- The "interview approach" is offered as a named technique for fuzzy ideas: "ask Codex to question you first... challenge your assumptions and turn the fuzzy idea into something concrete before writing code." Framed as a deliberate alternative entry point, not a fallback.
- `/plan` supports live negotiation, not just accept/reject: the docs show a concrete user revision — "Revise the plan to: specify exactly which files move in each milestone; include a rollback strategy" — as the model interaction, before any implementation starts.
- The 4-artifact long-horizon workflow (Prompt.md → Plan.md → Implement.md → Documentation.md) is presented as the mechanism that keeps multi-session/async agent work from drifting; Prompt.md's stated purpose is explicit: "Freeze the target so the agent doesn't 'build something impressive but wrong.'"
- Once a plan is approved, Codex can hand it to a cloud/background environment that "carries over the existing chat context (including the plan and any local source changes)" — discussion and plan state survive the handoff to execution.

### 2. Failures / friction / abandoned patterns

- Cookbook guidance treats open-ended clarification as a failure mode to actively suppress: "do not end your turn with clarifications unless truly blocked" (repeated near-verbatim across the Codex prompting guide).
- Planning itself is gated to avoid overhead on easy work: "Skip using the planning tool for straightforward tasks (roughly the easiest 25%). Do not make single-step plans."
- Ending a turn with only a plan and no code is treated as an anti-pattern absent an explicit request: "Unless asked for a plan, never end the interaction with only a plan" — "the deliverable is working code."
- GPT-5.2 guide goes further than any other source pulled: default behavior is to never ask ("never ask clarifying or follow-up questions unless the user explicitly asks you to" is the implied policy behind "state your best-guess interpretation plainly, then comprehensively cover the most likely intent"), reserving clarification for legal/financial/compliance/safety-sensitive contexts only, capped at "1–3 precise clarifying questions, OR 2–3 plausible interpretations with clearly labeled assumptions."
- No hard numbers (stars/upvotes/HN points) appear in any of the eight sources — all are first-party OpenAI docs/blog/cookbook pages, not community discussion.

### 3. Concrete mechanics

- **Toggle**: Plan mode is entered via `/plan` slash command or the Shift+Tab keyboard shortcut; same two mechanisms confirmed on both best-practices and codex-manual pages.
- **4-part prompt convention** (codex-manual) for framing any non-trivial ask: Goal / Context / Constraints / Done-when — this is the structured input Plan mode and the interview approach work from.
- **Question cadence**: GPT-5.1 guide gives the most concrete rule found — "when key information (date, city, approximate headcount) is missing, pause and ask 1–3 brief clarifying questions before generating a detailed plan," but conditioned on user tone: "For users who sound rushed or decisive, minimize questions and instead move ahead with defaults." GPT-5.2 tightens this to legal/financial/safety domains only, same 1–3 cap.
- **Anti-sycophancy / pushback**: the interview approach is the explicit pushback mechanic — "challenge your assumptions" — rather than a separate rule; no distinct "disagree with the user" instruction appears in any source.
- **Progress narration substitute**: GPT-5.2's "user update" pattern replaces a discussion phase with brief (1–2 sentence) phase-change messages sent "only when: you start a new major phase of work, or you discover something that changes the plan," each carrying a concrete result ("Found X", "Confirmed Y").
- **Tool preamble** (original GPT-5 guide): "rephras[e] the user's goal... before calling any tools," then "immediately outline a structured plan," narrate steps as they execute, and "finish by summarizing completed work distinctly from your upfront plan" — a lightweight, always-on discussion→plan→execute→summary loop for every turn, separate from the heavier `/plan` mode.
- **Plan-artifact requirement** (GPT-5.1): "create and maintain a lightweight plan in the TODO/plan tool before your first code/tool action" for medium/large tasks — visible tracked state, not silent reasoning.
- **Closure rule** (Codex prompting guide): before finishing, "reconcile every previously stated intention/TODO/plan" as Done, Blocked (with reason + targeted question), or Cancelled — "do not end with in_progress/pending items."
- **Artifact structure** (long-horizon blog): Plan.md holds milestones sized for single-loop completion, per-milestone acceptance criteria + validation commands, a stop-and-fix rule, and decision notes "to prevent oscillation"; Documentation.md is explicitly framed as "shared memory and audit log" for async human oversight, tracking status, decisions+rationale, run/demo instructions, and known issues.

### 4. Hard numbers

None present in any of the eight sources — all first-party OpenAI documentation/blog/cookbook, no community engagement metrics available.
