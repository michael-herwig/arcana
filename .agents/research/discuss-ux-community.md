# Research: Community sentiment on AI assistant clarification/interview loops

## Metadata

**Date:** 2026-08-30
**Domain:** AI agent / developer-tooling UX
**Triggered by:** hex-discuss UX discussion
**Expires:** 2027-02-28

## Direct Answer

Practitioner sentiment is split but patterned, not random. Clarifying
questions are valued when **batched upfront** and tied to real ambiguity on
work that matters (real features, shared codebases); they're resented when
sequential, reflexive, or applied to throwaway work. Ceremony before the
first substantive answer is tolerated only up to roughly a minute before
users mentally switch into "batch job" mode and start distrusting the
process. Assistants that append "would you like me to continue?" habitually
draw complaints; a genuine end-of-task summary (what was done and why) is
welcomed as distinct from that reflexive prompt. Unprompted background
verification/research gets real praise for catching what the user didn't
think to check, and real pushback when it patches symptoms instead of root
cause, or silently takes over reasoning the human wanted to do themselves.

## Key Findings

### 1. Question cadence — batched beats sequential

1. Jakob Nielsen argues long-running-task systems should front-load
   clarification into one negotiated exchange rather than interrupt
   mid-task, and that if generating the clarifying questions itself takes
   more than ~1 second, the agent should proceed rather than stall
   ([Slow AI](https://jakobnielsenphd.substack.com/p/slow-ai)).
2. BrainGrid's planning agent interrogates a request comprehensively
   *before* any code is written, converting answers into acceptance
   criteria rather than a scrolling chat — explicitly to avoid "service-style"
   back-and-forth
   ([braingrid.ai](https://www.braingrid.ai/blog/why-we-made-our-agent-ask-questions)).
   A Hacker News commenter quoted in that same post pushes back that the
   capability is trivial to invoke ("Tell a coding agent to 'ask clarifying
   questions' and watch what it does") — the real design question is
   whether it's the *default*, not whether it's possible.
3. Cursor's Plan Mode routes clarification through a dedicated
   `ask_user_question` tool capped at up to 4 questions per turn, rather
   than scattering an "Open Questions" list through normal chat — a
   deliberate batching choice
   ([Educative: Plan mode vs build mode](https://www.educative.io/courses/learn-opencode/plan-mode-vs-build-mode)).
4. Academic support: the ChainBuddy paper found their "infinite questioner"
   pattern (one question at a time until the user says "generate") was
   "time-consuming and pressuring" for users in pilot studies, favoring
   batched elicitation instead
   ([arXiv:2409.13588](https://arxiv.org/pdf/2409.13588)).

### 2. Upfront processing / ceremony tolerance

1. Nielsen sets a concrete threshold: turn-taking interactions need
   sub-10-second responses to still feel conversational; past roughly a
   minute, users drop into batch-processing psychology and start doubting
   direction and utility, even for tools like Deep Research where multi-minute
   waits are expected
   ([Slow AI](https://jakobnielsenphd.substack.com/p/slow-ai)).
2. Complaints about Claude Code's "Let me check... let me verify... let me
   try again" narration loop describe it as consuming context budget before
   real work happens; the practical fix users share is an explicit
   "do not narrate intermediate steps, execute directly" instruction
   ([Figma forum thread](https://forum.figma.com/report-a-problem-6/claude-ai-not-finishing-prompt-requests-lately-45744),
   [zzbbyy Substack](https://zzbbyy.substack.com/p/rigidity-of-claude-userassistant)).
3. Ceremony tolerance is a positioning choice, not a fixed preference: Devin
   trades ceremony for autonomy (runs plan-to-PR unsupervised), while GitHub
   Copilot Workspace shows the plan upfront and gates every step on approval
   — both have adherents
   ([Devin vs Copilot Workspace](https://www.mgsoftware.nl/en/vergelijking/devin-vs-github-copilot-workspace)).

### 3. Wrap-up behavior

1. A recurring, specific Reddit complaint is the reflexive "Would you like
   me to continue?" / "Would you like me to help organize this?" tail; blunt
   suppression instructions ("don't ask follow-up questions") reportedly
   don't work as well as precise ones ("don't include suggestions, offers,
   or follow-up questions unless I explicitly request them")
   ([Medium roundup of Reddit fixes](https://ai-engineering-trend.medium.com/how-to-stop-ai-assistants-from-asking-would-you-like-me-to-help-nonsense-9a639d6107b0)).
2. One cited workaround treats follow-ups as conditionally welcome: valuable
   when they "drive the conversation forward" or expand thinking, unwanted
   when they're reflexive service-speak — the complaint is about the
   *reflex*, not the concept of a next step (same Medium source).
3. Nielsen argues real completion needs a substantive wrap, not silence or
   a prompt — a "Resumption Summary" stating original intent, key decisions,
   and what was produced and why. This is framed as distinct from — and the
   antidote to — reflexive "want more?" filler
   ([Slow AI](https://jakobnielsenphd.substack.com/p/slow-ai)).

### 4. Proactive background research / unprompted action

1. The Hacker News thread "Claude Fable is relentlessly proactive" shows a
   genuine split. Praise: simonw — "Fable will do a whole lot more than you
   might expect in order to verify a fix," crediting it with teaching him
   new debugging techniques; Illniyar — "predisposed to try and verify its
   changes... exactly what I would want from a junior developer."
   ([HN 48498573](https://news.ycombinator.com/item?id=48498573)).
2. Same thread, critical side: bananaquant argues genuine proactivity would
   investigate root cause/architecture rather than patch the visible
   symptom; piker frames silently-offloaded work as an opportunity cost —
   the human loses the chance to reason about the abstraction themselves.
   danudey notes the model's unprompted browser/window inspection escalated
   until it visibly "hit some kind of guardrail," read as evidence users
   stay alert to scope creep even when the outcome is net-positive (same
   thread).
3. Broader framing: unlike a junior developer who says "I didn't understand
   that part," models tend to "insist they can solve problems" rather than
   surface uncertainty — the implicit ask from practitioners is for
   proactive doubt-flagging, not just proactive doing
   ([HN: Coding assistants are solving the wrong problem](https://news.ycombinator.com/item?id=46866481)).

## Sources

| # | Source | URL |
|---|---|---|
| 1 | HN — "Claude Fable is relentlessly proactive" | https://news.ycombinator.com/item?id=48498573 |
| 2 | Jakob Nielsen — "Slow AI: Designing User Control for Long Tasks" | https://jakobnielsenphd.substack.com/p/slow-ai |
| 3 | BrainGrid — "Why We Made Our Agent Ask Questions Before It Builds" | https://www.braingrid.ai/blog/why-we-made-our-agent-ask-questions |
| 4 | Medium — "How to Stop AI Assistants from Asking 'Would You Like Me to...'" | https://ai-engineering-trend.medium.com/how-to-stop-ai-assistants-from-asking-would-you-like-me-to-help-nonsense-9a639d6107b0 |
| 5 | Figma forum — Claude Code narration complaint | https://forum.figma.com/report-a-problem-6/claude-ai-not-finishing-prompt-requests-lately-45744 |
| 6 | zzbbyy Substack — "Rigidity of Claude user/assistant dialog" | https://zzbbyy.substack.com/p/rigidity-of-claude-userassistant |
| 7 | HN — "Coding assistants are solving the wrong problem" | https://news.ycombinator.com/item?id=46866481 |
| 8 | Educative — "Plan mode vs build mode" (Cursor) | https://www.educative.io/courses/learn-opencode/plan-mode-vs-build-mode |
| 9 | ChainBuddy paper (arXiv) | https://arxiv.org/pdf/2409.13588 |
| 10 | Devin vs GitHub Copilot Workspace comparison | https://www.mgsoftware.nl/en/vergelijking/devin-vs-github-copilot-workspace |
