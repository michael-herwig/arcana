# Pre-Implementation Discussion Phase: Vendor Mechanics

Researched: 2026-08-28. Expires: 2027-02-28.

## Sources

- https://cursor.com/docs/agent/plan-mode — primary vendor docs, Cursor Plan Mode mechanics
- https://cursor.com/blog/plan-mode — primary vendor launch post, rationale + editor UX
- https://www.digitalapplied.com/blog/cursor-2-1-clarifying-questions-plans — third-party writeup with quantified claims (unverified)
- https://docs.devin.ai/desktop/cascade/modes (redirected from docs.windsurf.com) — primary vendor docs, Cascade Plan mode
- https://windsurf.com/university/general-education/intro-planning-mode — SKIPPED, redirect chain returned HTTP 429
- https://github.blog/changelog/2026-01-21-github-copilot-cli-plan-before-you-build-steer-as-you-go/ — primary vendor changelog, Copilot CLI ask_user tool
- https://learn.microsoft.com/en-us/visualstudio/ide/copilot-plan-agent?view=visualstudio — primary vendor docs, VS Copilot plan agent
- https://docs.devin.ai/work-with-devin/ask-devin — primary vendor docs, Ask Devin interactive scoping

## Findings

### 1. What's praised / demonstrably works

- Cursor (vendor claim): "Most new features at Cursor now begin with Agent writing a plan. We've seen this significantly improve the code generated" — internal dogfooding cited as validation, no external metric given.
- Cursor frames the core value as separating the hard problem from the easy one: "the hard part is often figuring out **what** change should be made" — planning targets requirements ambiguity, not code-writing difficulty.
- Copilot plan agent (MS Learn) is explicitly read-only during planning — "doesn't edit files or run implementation steps while you're planning" — praised implicitly as a safety property: nothing changes until explicit handoff.
- Devin's "context-rich prompt" generation — the discussion phase auto-produces a tailored prompt for the follow-on agent session, removing manual prompt transcription.
- Third-party (DigitalApplied, unverified) claims for Cursor 2.1 clarifying questions: "reduce implementation errors by 34%" and "cut back-and-forth iteration cycles by 42%" — presented as vendor-adjacent marketing metrics, not independently sourced or reproducible.

### 2. What fails / annoys / gets abandoned

- None of the 7 successfully-fetched sources contain direct user complaints, GitHub issue threads, or forum pushback — all are vendor docs/blogs or a vendor-adjacent feature writeup, so no organic negative signal surfaced in this pass. (Complaint-mining would need HN/Reddit/GitHub-issue sources, out of scope for this lane.)
- Implicit friction point: Copilot's plan agent is a *separate mode* from "Planning in agent mode" (MS Learn draws this distinction explicitly) — two similarly-named features in the same product is a documented source of user confusion the vendor itself felt the need to disambiguate with a comparison table.
- Windsurf University tutorial (secondary how-to guidance) was unreachable (429 after redirect) — a gap, not a finding.

### 3. Concrete mechanics

**Question cadence / format**
- Cursor 2.1 (third-party account): 3–5 targeted questions before plan generation; mixed multiple-choice-with-tradeoffs plus free-text plus skip-to-let-AI-decide; context-adaptive (e.g., React/Redux → state-management questions, Next.js → server/client component questions).
- Cascade (Windsurf/Devin docs): explicitly "often asks multiple choice questions." Keywords `megaplan`/`ultraplan`/`masterplan` force deeper planning with *mandatory* clarifying questions (opt-in escalation).
- Copilot CLI: `ask_user` tool presents questions "alongside a list of possible options," used to confirm scope assumptions and design decisions, not just requirements gaps.
- VS Copilot plan agent: clarification is conditional — "If the task is ambiguous, it asks clarifying questions before it drafts a plan... For straightforward requests, Copilot might draft the plan immediately without asking follow-up questions." Ambiguity-gated, not mandatory.

**Background research while conversing**
- Cursor: researches codebase to "find relevant files, review docs" as part of the same turn that produces questions/plan.
- VS Copilot plan agent: "explores your codebase by using read-only tools" before drafting, explicitly no edits during this phase.
- Devin: Ask Devin gives "detailed, accurately cited answers" with inline code citations — research is conversational/answer-form, not a separate artifact.

**Artifacts produced and structure**
- Cursor: markdown plan, default save location is the **home directory**, with an explicit "Save to workspace" opt-in for team visibility; contains file paths and code references; editable via chat or direct markdown edit; supports revert.
- Cascade: `plan.md` saved **outside the repo**, at `~/.windsurf/plans` or `~/.devin/plans`; persists for the session so "planning can span several messages."
- VS Copilot plan agent: markdown saved **inside the repo** by default at `.copilot/plans/plan-{title}.md` (configurable path); manual edits to the file are detected and re-synced into chat state — bidirectional sync between file and chat, unlike Cursor's home-dir default.
- Copilot CLI: "structured implementation plan" reviewed in a "dedicated panel" (not markdown-file-first in the changelog's framing).
- Devin: no separate plan file — the discussion produces a "context-rich prompt" consumed directly by the next Agent session; continuity tracked in-thread.

**Handoff to implementation**
- Cursor: explicit user action — "Click to build the plan when ready."
- VS Copilot plan agent: explicit — select "Implement plan," which hands off to a *different* mode (agent mode) to execute; "No implementation changes happen until you explicitly choose."
- Cascade: **four** paths — click "Implement" on the plan file; approve agent's own request to leave Plan mode; manually switch mode selector; or fully automatic switch when Cascade "detects that you're ready to implement." Only vendor here documenting an automatic (non-confirmed) handoff path.
- Devin: handoff is starting an Agent session directly from the Ask Devin thread, carrying the generated prompt; original conversation remains as a status-visible parent thread.
- Copilot CLI: mode toggle via Shift+Tab cycles between plan/build states in the same session.

**Mode entry**
- Cursor and Copilot CLI both use the identical **Shift+Tab** chord to cycle into plan mode, and Cursor additionally auto-suggests Plan Mode on detecting "keywords that indicate complex tasks."

### 4. Hard numbers

- Cursor 2.1 (third-party, DigitalApplied — not corroborated by any primary source fetched): 34% fewer implementation errors, 42% fewer back-and-forth iteration cycles, 3–5 questions per planning pass, 30–60 seconds suggested response time per question.
- No star/upvote/HN-point data present in any of the 7 fetched sources — all are documentation/changelog/blog pages, not community-discussion platforms.
