# Pre-Implementation Discussion Phase — Anthropic Primary Sources

Researched: 2026-08-28. Expires: 2027-02-28.

## Sources

- https://code.claude.com/docs/en/best-practices — official Claude Code best-practices reference; "Let Claude interview you" section is the canonical elicitation pattern; actively maintained
- https://code.claude.com/docs/en/permission-modes — official Plan Mode mechanics (v2.1.212–v2.1.247+ changelog notes throughout, actively revised)
- https://code.claude.com/docs/en/common-workflows — official recipe doc; condensed "Plan before editing" + subagent-delegation recipes
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents — Anthropic engineering blog; initializer-agent pattern for spec expansion
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — Anthropic engineering blog; canonical context-curation guidance (compaction, note-taking, sub-agents, JIT retrieval)
- https://code.claude.com/docs/en/sub-agents — official subagent doc; context-isolation rationale and built-in Explore/Plan research agents

## Findings

### 1. What's praised / demonstrably works

- The interview pattern is framed as high-leverage: "Time spent making the spec precise pays off more than time spent watching the implementation" (best-practices).
- Verification-closing-the-loop is praised as the mechanism that turns a watched session into an unattended one: give Claude "something that produces a pass or fail" (test, build exit code, screenshot diff) and "the loop closes on its own."
- Explore→Plan→Implement→Commit is presented as *the* recommended workflow for non-trivial changes, explicitly to "avoid solving the wrong problem."
- Subagent-delegated research is praised for keeping the interview/planning conversation itself uncluttered: "the subagent does that work in its own context and returns only the summary" (sub-agents doc); Explore and Plan built-in agents exist specifically so "exploration results" stay "out of your main conversation context."
- Plan Mode's editor handoff (`Ctrl+G`) is a concrete, praised mechanic: the human edits the plan file directly rather than re-prompting in chat.
- The initializer-agent pattern (harnesses post) is presented as solving a real failure mode — see below — by front-loading requirements expansion before any code exists.

### 2. What fails or annoys (named failure patterns)

- **"The kitchen sink session"**: task drift because unrelated asks pollute one conversation — fix is `/clear` between tasks, not more discussion.
- **"Correcting over and over"**: repeated wrong turns pollute context with failed approaches; official guidance caps this explicitly — after two failed corrections, `/clear` and rewrite the prompt rather than continuing to discuss.
- **"The infinite exploration"**: an unscoped "investigate X" during discussion fills context by reading "hundreds of files" — fix is scoping the investigation narrowly or delegating to a subagent.
- **"The trust-then-verify gap"**: a plausible-looking implementation that skipped edge cases — named as the reason verification, not more up-front discussion alone, is required.
- Named directly for autonomous/scheduled runs: "the task runs autonomously, so it can't ask clarifying questions" (common-workflows) — an explicit statement that the discussion phase's clarifying-question capability is a property of *interactive* sessions only, absent in scheduled/headless runs.
- Harness-post failure named as the reason the initializer pattern exists: "the problem of the agent one-shotting an app or prematurely considering the project complete" — i.e., without a pre-expanded feature spec, long-running agents under-scope and self-report done too early.
- Adversarial-review caveat (adjacent, not discussion-phase itself but same "don't over-trust one pass" theme): "A reviewer prompted to find gaps will usually report some, even when the work is sound... Chasing every finding leads to over-engineering."
- Context-engineering post names the core risk discussion-phase length must be managed against: "context rot" — accuracy degrades as token volume grows — and warns overly aggressive compaction of a long discussion "can result in the loss of subtle but critical context."

### 3. Concrete mechanics

- **Interview prompt (verbatim, best-practices doc)**:
  > "I want to build [brief description]. Interview me in detail using the AskUserQuestion tool. Ask about technical implementation, UI/UX, edge cases, concerns, and tradeoffs. Don't ask obvious questions, dig into the hard parts I might not have considered. Keep interviewing until we've covered everything, then write a complete spec to SPEC.md."
- **Cadence/stop rule**: no fixed question count — "keep interviewing until we've covered everything" is the only stated termination condition; anti-obviousness rule ("don't ask obvious questions, dig into the hard parts") is the only explicit quality filter, not an anti-sycophancy/pushback instruction per se.
- **Spec quality bar (verbatim)**: "self-contained: they name the files and interfaces involved, state what is out of scope, and end with an end-to-end verification step that proves the feature works."
- **Handoff rule (verbatim)**: "Once the spec is complete, start a fresh session to execute it. The new session has clean context focused entirely on implementation, and you have a written spec to reference." — discussion and implementation are deliberately different sessions, not phases of one context.
- **Background research during discussion**: "use subagents to investigate X" pattern — subagent gets its own context window, returns only a summary; explicitly recommended so research "doesn't consume your main context." Built-in **Explore** subagent (read-only tools, Write/Edit denied) handles codebase research at three thoroughness levels (quick/medium/very thorough). Built-in **Plan** subagent specifically handles research invoked *while in Plan Mode* so "exploration output stays in a separate context window while the main conversation remains read-only."
- **Plan Mode mechanics**: entered via `Shift+Tab` until status bar shows `⏸ plan mode on`, or `--permission-mode plan`. Claude reads files, runs read-only/classifier-approved commands, cannot edit source. On completion, three resolution choices are presented verbatim: **"Yes, and use auto mode"**, **"Yes, manually approve edits"**, **"No, keep planning."** `Ctrl+G` opens the plan in the user's default text editor for direct editing before proceeding. Approving exits plan mode and switches the permission mode; declining ("No, keep planning") stays in the loop.
- **Initializer-agent artifacts** (harness post): (1) a feature-requirements file — JSON preferred over Markdown because "the model is less likely to inappropriately change or overwrite JSON files"; example expanded to 200+ discrete features from a terse prompt, each with structured steps, initially marked failing; (2) `claude-progress.txt` for session logging; (3) an initial git commit as baseline. Protective instruction quoted: "It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality."
- **Context management during a long discussion** (context-engineering post): compaction is "the first lever," summarizing and reinitializing; "structured note-taking / agentic memory" persists progress outside the context window; "just in time" retrieval keeps lightweight identifiers and loads detail only when needed ("progressive disclosure").
- **When to skip discussion/planning entirely** (best-practices, verbatim): "For tasks where the scope is clear and the fix is small... ask Claude to do it directly... If you could describe the diff in one sentence, skip the plan." Planning is framed as warranted specifically when "uncertain about the approach," "modifies multiple files," or "unfamiliar with the code being modified."

### 4. Hard numbers

- 200+ discrete features cited as the scale of one initializer-agent spec-expansion example (claude.ai clone case study).
- Auto-mode fallback thresholds (mechanical, not discussion-specific but load-bearing for any autonomous phase): classifier pauses auto mode after 3 consecutive blocks or 20 total blocks in a session.
- No stars/upvotes/HN points — all six sources are first-party Anthropic documentation/engineering-blog pages, not community-voted content.
