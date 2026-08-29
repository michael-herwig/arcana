# Always-on rule context budgets

Researched: 2026-08-28. Expires: 2027-02-28.

## Research: always-on rule context budgets

### Direct answer

An always-on "discussion mode" rule should carry only a trigger phrase and a
one-line stance/pointer (roughly 5-10 lines, well under ~100 tokens) — full
elaboration belongs in an on-demand skill. Two independent bodies of evidence
converge on this: (1) every major agent vendor caps always-loaded instruction
files far below what they allow for on-demand files, because degradation is
about *instruction count competing for a fixed attention budget*, not raw
token cost; and (2) conditional logic embedded in already-loaded text ("do X
only when Y") is one of the most failure-prone instruction patterns in
current models, so stuffing a big conditional stance into the permanent
prefix pays a reliability cost without buying a corresponding benefit — a
skill's description-match gate (evaluated *before* the body ever enters
context) is the mechanically correct place for that logic.

### Trends

- **Official vendor guidance is qualitative, not numeric.** Anthropic's
  Claude Code docs give a heuristic ("for each line, ask: would removing this
  cause a mistake?") rather than a line count, and explicitly route anything
  "only relevant sometimes" to skills, which load on demand.
  [code.claude.com/docs/en/best-practices](https://code.claude.com/docs/en/best-practices)
- **Community/practitioner numbers converge in a narrow band** across
  independent tools: ~200 lines for CLAUDE.md, ~500 lines per Cursor `.mdc`
  rule file (and ≤2,000 tokens total across all `alwaysApply: true` rules),
  ~500 lines per `SKILL.md` body, ~1,000 lines for GitHub Copilot's
  `copilot-instructions.md`. None of these are Anthropic/Cursor/GitHub
  official numbers; they're practitioner consensus, but the *order of
  magnitude* agreement across unrelated ecosystems is itself signal.
- **The mechanism behind the budget is instruction count, not file size.**
  A July 2026 study found perfect-compliance rate collapses to zero by ~80
  simultaneous instructions regardless of format or placement; a companion
  study on stacked instructions found compliance fall from 96% (1
  instruction) to ~20% (20 stacked instructions), with format/length
  constraints collapsing hardest and lexical instructions surviving best.
  This is the real ceiling a "budget in lines" is a proxy for.
- **Skills and rules occupy different context regions, which changes the
  cost math.** CLAUDE.md/rules sit in the system prefix and are
  architecturally exempt from conversation-history compaction — they persist
  verbatim for the whole session. A skill's body, once invoked, enters as
  conversation content and *is* subject to summarization on compaction. So a
  rule is the "durable but permanently-taxed" region; a skill is
  "ephemeral-but-protected-from-dilution-until-called."
- **Conditional/gated instructions are a known weak point**, independent of
  length: research on instruction-following distinguishes "Triggering Error"
  (wrong rule fires, or the right one doesn't) from "Execution Error" (right
  rule recognized but not correctly applied) — both apply directly to a
  rule that says "only take this stance when the user says X." Cursor's own
  "Agent Requested" activation (matched by description, same shape as a
  Claude skill) has multiple forum-reported failure threads even though its
  match happens *before* load, which is the easier case.

### Key findings (links)

- Anthropic: CLAUDE.md has no required format, but "keep it concise... if
  your CLAUDE.md is too long, Claude ignores half of it because important
  rules get lost in the noise." Domain knowledge "only relevant sometimes"
  → skills, loaded on demand.
  [code.claude.com/docs/en/best-practices](https://code.claude.com/docs/en/best-practices)
- Anthropic skill authoring: keep `SKILL.md` body under ~500 lines; bundled
  reference files cost zero tokens until opened — the progressive-disclosure
  mechanism this whole split depends on.
  [docs.claude.com/.../best-practices](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices)
- Cursor: keep individual rule files under ~500 lines; total `alwaysApply`
  rules under ~2,000 tokens combined (≈ lines × 4); beyond ~5,000 words
  dilution starts.
  [morphllm.com/cursor-rules-best-practices](https://www.morphllm.com/cursor-rules-best-practices)
- Cursor forum: "Agent Requested" rules are matched purely on the
  `description` field — no description means the rule silently never
  surfaces; users report the agent pulling rules "randomly."
  [forum.cursor.com — Agent Requested reliability](https://forum.cursor.com/t/allow-rules-to-auto-attach-and-be-agent-requested-at-the-same-time/64319),
  [dev.to — why Cursor rules never fire](https://dev.to/rulestack/why-your-cursor-rules-never-fire-globs-alwaysapply-and-description-explained-b33)
- GitHub Copilot: cap a single instructions file around ~1,000 lines /
  ~2 pages; start minimal, iterate; shorter files are more reliably
  fully-processed.
  [smartscope.blog — Copilot custom instructions guide](https://smartscope.blog/en/generative-ai/github-copilot/github-copilot-custom-instructions-guide/)
- opencode: `AGENTS.md` files at every directory level up to home are
  concatenated (not merged/deduped) into the system prompt — every level
  you add is pure addition to the always-on budget, no override semantics.
  [opencode.ai/docs/rules](https://opencode.ai/docs/rules/)
- Chroma, "Context Rot" (2025): 18 frontier models incl. Claude Opus,
  GPT-4.1, Gemini 2.5 all degrade with input length even on simple
  retrieval, independent of hitting the context-window limit — degradation
  is continuous, not a cliff at the limit.
  [trychroma.com/research/context-rot](https://www.trychroma.com/research/context-rot)
- Liu et al., "Lost in the Middle" (2023, foundational but 3 yrs old —
  flag as dated): relevant info in the middle of a long context is used far
  worse than info at the start/end; 30%+ accuracy drop. Later work refines
  this: the U-shape only holds below ~50% context fill — past that, recency
  dominates over position.
  [arxiv.org/abs/2307.03172](https://arxiv.org/abs/2307.03172)
- "Prompt Design at Scale" (Jul 2026): perfect-response rate → 0 by N=80
  simultaneous system-prompt instructions, across every model/format/
  placement tested.
  [arxiv.org/abs/2607.19257](https://arxiv.org/abs/2607.19257)
- "Instruction Stacking Collapse" (Aug 2026, brand new): compliance 96%→~20%
  from 1 to 20 stacked instructions on Claude Sonnet 4.6/GPT-5-mini/Gemini
  2.5 Flash; format/length constraints fail hardest, lexical rules survive
  best — directly relevant to a "trigger + stance" rule, which is exactly a
  format/conditional constraint.
  [arxiv.org/html/2608.02639](https://arxiv.org/html/2608.02639)
- Claude Code compaction: system prompt/CLAUDE.md is architecturally outside
  the conversation history that gets summarized — it survives verbatim.
  Conversation-injected content (a skill body once invoked) is exactly what
  compaction condenses/drops first unless the user pins it via
  `/compact <instructions>`.
  [code.claude.com/docs/en/context-window](https://code.claude.com/docs/en/context-window),
  [platform.claude.com/.../compaction](https://platform.claude.com/docs/en/build-with-claude/compaction)
- Prompt caching cost math: 5-min TTL cache write = 1.25× base input, reads
  = 0.10× base — break-even after one hit; every turn after that in a
  session is near-free for a static always-on block. The real cost of a
  200-line rule isn't dollars per turn, it's the instruction-count ceiling
  above.
  [platform.claude.com/.../prompt-caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching),
  [respan.ai — Claude prompt caching pricing](https://www.respan.ai/articles/claude-prompt-caching)

### Sources

All linked inline above; primary/official sources (Anthropic docs, Cursor
docs, GitHub docs, opencode docs, arXiv preprints) preferred over aggregator
blog posts, which are cited only where they supply consensus numbers no
official doc states.

### Recommendation (rationale)

**Split point: trigger phrase + ≤1-line stance in the always-on rule; the
actual stance content, examples, and edge cases in an on-demand skill the
trigger phrase points to.** Rationale:

1. The binding constraint on always-on text isn't dollars (caching makes
   repeat turns near-free) or even raw context-window room — it's the
   instruction-count ceiling where compliance measurably collapses (N≈80
   total, and format/conditional instructions fail first among the stack).
   A 200-line rule isn't "expensive," it's *several dozen instructions*
   competing with everything else already in the prefix for the rest of the
   session, on every task, whether or not the trigger ever fires.
2. Conditional dormancy inside already-loaded text is not a solved
   pattern — it's the specific failure mode the instruction-stacking
   research names (triggering error, execution error). A skill's
   description-match gate sidesteps this by not loading the body at all
   until matched, which is a stronger guarantee than "an LLM will ignore
   this paragraph unless condition X holds."
3. Compaction makes the asymmetry sharper: the rule survives every long
   session verbatim (good for the trigger phrase, which is cheap and must
   never be forgotten), but a large stance blob parked in the same
   permanent region gets *no* protection benefit from that placement it
   wouldn't already have as a skill — while a skill body, loaded only when
   needed, is exactly the kind of content compaction is designed to be
   allowed to summarize away once the immediate task is done.
4. Every vendor's numeric ceiling for "on-demand" content (500-1000 lines)
   is far more generous than for "always-on" content (implicitly ~150-200
   lines' worth of budget before adherence measurably drops) — the
   ecosystem has already converged on on-demand being the right home for
   anything beyond a short pointer.
