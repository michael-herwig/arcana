# Research: Agent-maintained lesson logs / retro skills (community lane)

## Metadata

**Date:** 2026-09-23
**Domain:** cli / ai-config
**Triggered by:** discuss-retro (nox bundle: capture step + periodic retro/consolidation skill for CLAUDE.md/AGENTS.md-style instruction files)
**Expires:** 2027-03-23

## Direct Answer

Practitioners overwhelmingly favor a two-stage pattern that matches the
proposed design: (1) lightweight, often automatic capture of friction/
corrections during a session, and (2) a separate, human-gated consolidation
step (manual `/retro`-style command, not cron) that proposes — never
auto-applies — edits, routed to a specific destination file by a taxonomy.
Unbounded auto-growth of CLAUDE.md/AGENTS.md is the dominant reported failure
mode, with peer-reviewed evidence that instruction files triple in size
(+226%) over their lifetime and resist pruning because the *rationale* for an
instruction decays faster than the instruction itself, making deletion feel
risky. The most credible countermeasure across sources is not a numeric
threshold but preserving *why* (rationale/provenance) at write time, a
per-proposal human approval gate, and destination-based routing instead of
dumping everything into one file.

## Key Findings

1. **Capture, then separate consolidation, is the emerging standard.**
   [giannimassi/agent-retro](https://github.com/giannimassi/agent-retro) and
   [netresearch/retro-skill](https://github.com/netresearch/retro-skill) both
   run post-session, not continuously: `/agent-retro` or `/retro` is invoked
   manually "at the end of a session," analyzes the full transcript, and
   proposes *specific edits to skills, rules, or config* — it does not write
   directly. [BayramAnnakov/claude-reflect](https://github.com/BayramAnnakov/claude-reflect)
   splits the same way: Stage 1 is an automatic hook that *queues* candidate
   corrections/positive-feedback/explicit "remember:" markers in real time
   during the session (regex-based); Stage 2 is a manual `/reflect` command
   that does semantic validation, dedup, and presents items for human
   approve/edit/skip before anything syncs to a file.

2. **Consolidation trigger is manual invocation, not cron, in every skill
   found.** No shipped skill auto-runs consolidation on a schedule. Martin
   Alderson's post floats "could run as a scheduled task every day/week" as
   an *aspiration*, not something built —
   [martinalderson.com](https://martinalderson.com/posts/self-improving-claude-md-files/).
   netresearch/retro-skill does offer an optional disabled-by-default
   `SessionEnd` hook that only *prints a reminder* past 1000 words of
   transcript; it still requires the human to type `/retro`.

3. **Destination-routing taxonomy (owner: project vs. tool/skill vs. user
   preference) exists and is the clearest prior art for the "route lessons
   to owner" question.** netresearch/retro-skill routes each finding to one
   of seven destinations by authority: `canonical-source` (external
   docs/schemas), `personal-rule` (→ `~/.claude/CLAUDE.md`), `project-rule`
   (→ `<project>/AGENTS.md`), `skill-update` (PR to an existing skill),
   `new-skill` (scaffold a new one), `checkpoint` (→ `checkpoints.yaml`
   quality gates), `harness-artefact` (hooks/CI/templates) —
   [netresearch/retro-skill](https://github.com/netresearch/retro-skill).
   Its pipeline is layered: Layer A = 18 deterministic mechanical signals
   (tool errors, retry clusters, permission denials, protected-branch
   writes), Layer B = LLM enrichment adding 14 inferential signals and
   filtering false positives, Layer C = cross-session pattern scan against
   project memory, plus a skill-discovery match against installed skills'
   descriptions. claude-reflect syncs to a narrower set of four targets:
   global `CLAUDE.md`, project `CLAUDE.md`, `.claude/commands/*.md` (skill
   files), and `AGENTS.md` if present.

4. **Reported failure modes, evidenced (not just anecdotal):**
   - **Unbounded growth / "catastrophic remembering."** A controlled study
     (n=247,694 instruction lifetimes across popular repos) found agentic
     instruction files grow without bound: +226% over lifetime, +4.9 net
     instructions per commit, 64.3% of repos growing monotonically, median
     39 instructions / 90th-percentile 131 —
     [arxiv.org/html/2608.11095v1](https://arxiv.org/html/2608.11095v1)
     (flag: preprint, mechanism section may be revised). The paper's causal
     finding: deletion hazard *decreases* with instruction age (−0.032/commit)
     — the opposite of normal staleness decay — because the rationale for why
     an instruction was added is lost faster than the instruction itself, so
     nobody dares delete it. Multi-author files show even steeper resistance
     to deleting old instructions (attributed to authorship turnover erasing
     institutional memory).
   - **Contextual/lint/skill leakage.** A June 2026 audit of 100 popular
     repos found lint-related leakage in 62%, context bloat in 42%, skill
     leakage in 35% of instruction files, per
     [Addy Osmani, "Audit your Agent files"](https://addyo.substack.com/p/audit-your-agent-files).
   - **Auto-memory preserving one-off corrections as permanent rules,
     producing contradictions** — same source.
   - **Bloated files cause wholesale-ignore behavior**, not selective
     filtering: HN discussion reports that once files exceed a rough
     50-line/rule budget, agents stop reliably following them, and
     preemptive ("anticipatory") rules written from scratch are usually
     ignored — only rules distilled from an actual observed failure stick —
     [HN: "Do you still spend time maintaining Claude.md/AGENTS.md files?"](https://news.ycombinator.com/item?id=48160604).
     Same thread: negative framing ("don't do X") underperforms positive,
     action-oriented phrasing.
   - **Session-log friction data exists but has no feedback loop today**:
     Claude Code already collects per-session friction facets (a 42% friction
     rate across 144 sessions in one analysis) but nothing routes that data
     back into memory automatically, so agents repeat the same mistakes —
     cited in search summary from
     [anthropics/claude-code#24796](https://github.com/anthropics/claude-code/issues/24796)
     (flag: unverified issue-tracker claim, read the issue directly before
     relying on the 42% figure).

5. **Countermeasures reported as working:**
   - **Human review gate on every proposed edit**, not batch auto-apply —
     used by agent-retro, retro-skill, and claude-reflect alike; retro-skill
     explicitly caps a single sweep at "at most ten actionable proposals" to
     avoid a firehose.
   - **Confidence scoring + semantic dedup before surfacing a candidate**
     (claude-reflect: 0.60–0.95 confidence band, `/reflect --dedupe` merges
     near-duplicate entries, filters out questions/one-off/vague feedback).
   - **Preserve rationale, not just the rule.** The arxiv study's strongest
     result: encoding *why* an instruction was added (failure addressed,
     hypothesis, outcome) as an inline comment cut excess-instruction growth
     by 99.3% in controlled tests and improved instruction-following up to
     23.1% in real-world tests — because reviewers can then safely delete an
     instruction once its rationale is confirmed resolved/obsolete, instead
     of hoarding it out of uncertainty.
   - **Periodic "earn its place again" pruning pass** — Osmani recommends
     running `/doctor` every few weeks and separately auditing `/memory`,
     and testing whether tasks still succeed with a rule/skill temporarily
     removed before keeping it (a rough replay/eval-before-promote pattern,
     though not a formal eval harness).
   - **Anthropic's own precedent**: removing over 80% of Claude Code's system
     prompt caused no measured performance loss, cited by Osmani as evidence
     that most accumulated instruction content is low-value and safe to cut.
   - **Size ceiling as a soft convention, not enforced budget**: repeated
     "200 lines" guidance is referenced as the line past which files degrade,
     but no source describes an automated enforcement mechanism — it's a
     human review heuristic.

6. **No source describes a formal eval/replay-before-promotion gate** (i.e.,
   testing a candidate lesson against a held-out task set before writing it
   permanently) — the closest analogue is Osmani's manual "does the task
   still succeed without this rule" spot-check. This looks like an open gap
   between what practitioners want and what's built.

## Negative

- No skill or thread found that runs consolidation on a cron/scheduled
  trigger in production — every real implementation is manual-invoke,
  despite it being a commonly wished-for feature.
- No source documents a quantitative "recurrence threshold" (e.g., "promote
  a friction pattern only after it's seen N times") as an implemented
  mechanism; retro-skill's Layer C cross-session scan is the closest but its
  threshold logic wasn't visible in the fetched material — worth confirming
  directly against the skill's source if this precision matters for design.
- Reddit-specific threads were not surfaced distinctly from HN/blog content
  in this pass (search results skewed toward GitHub/Substack/arxiv); treat
  "Reddit" coverage here as thin.

## Leads

- **capture-mechanism lane**: pull the actual hook/regex implementation from
  [BayramAnnakov/claude-reflect](https://github.com/BayramAnnakov/claude-reflect)
  (correction/positive-feedback pattern matching) — most concrete prior art
  for "subagents record friction entries while working."
- **routing-taxonomy lane**: read
  [netresearch/retro-skill](https://github.com/netresearch/retro-skill)'s
  source directly (not just its README) for the exact destination-decision
  logic (7-way routing, Layer A/B/C signal lists) — closest match to the
  project-vs-tool/skill-vs-user-preference routing question in the design
  brief.
- **rationale-preservation lane**: read
  [arxiv.org/html/2608.11095v1](https://arxiv.org/html/2608.11095v1) in full
  — its "prompt comments" countermeasure (99.3% growth reduction) is the
  single most evidenced fix found and should inform whether the retro skill
  writes rationale comments alongside rule edits, not just the rule text.
- **audit-cadence lane**: read
  [Addy Osmani's "Audit your Agent files"](https://addyo.substack.com/p/audit-your-agent-files)
  in full for the specific `/doctor`-cadence and pruning checklist, since it's
  the most actionable existing "periodic pruning pass" process found.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| [giannimassi/agent-retro](https://github.com/giannimassi/agent-retro) | Repo | 2025/2026 (undated in fetch) | Post-session retro skill, capture→propose→approve flow |
| [netresearch/retro-skill](https://github.com/netresearch/retro-skill) | Repo | 2025/2026 (undated in fetch) | 7-destination routing taxonomy, layered signal detection, human gate, proposal cap |
| [BayramAnnakov/claude-reflect](https://github.com/BayramAnnakov/claude-reflect) | Repo | 2025/2026 (undated in fetch) | Real-time capture hook + manual consolidation, confidence scoring, dedup |
| [accidentalrebel/claude-skill-session-retrospective](https://github.com/accidentalrebel/claude-skill-session-retrospective) | Repo | 2025/2026 (unverified in this pass) | Sibling session-retrospective skill, not deep-fetched |
| [martinalderson.com — Self-improving CLAUDE.md files](https://martinalderson.com/posts/self-improving-claude-md-files/) | Blog | 2025/2026 (undated in fetch) | Manual log-analysis approach, floats but doesn't build cron consolidation |
| [Addy Osmani — Audit your Agent files](https://addyo.substack.com/p/audit-your-agent-files) | Blog | 2026 | Bloat/leakage stats (62%/42%/35%), `/doctor` cadence, pruning heuristic, Anthropic 80%-removal precedent |
| [HN: Do you still spend time maintaining Claude.md/AGENTS.md files?](https://news.ycombinator.com/item?id=48160604) | Forum | 2026 | Categorized rule effectiveness, 50-line rule-of-thumb, anticipatory-rules-ignored finding |
| [arxiv.org/html/2608.11095v1 — Why Does CLAUDE.md Keep Growing? Catastrophic Remembering](https://arxiv.org/html/2608.11095v1) | Preprint | 2026-08 (flag: <18mo, but preprint — re-verify before citing hard numbers) | Quantitative growth study, rationale-decay mechanism, prompt-comments countermeasure |
| [anthropics/claude-code#24796](https://github.com/anthropics/claude-code/issues/24796) | GitHub issue | 2025/2026 (undated in fetch) | Claims Claude Code already logs session friction facets with no memory feedback loop (unverified, re-check issue directly) |
| [joshwand1.substack.com — AGENTS.md gets it wrong in 2 ways](https://joshwand1.substack.com/p/agentsmd-gets-it-wrong-in-2-ways) | Blog | 2025/2026 (found, not deep-fetched) | Additional critique of AGENTS.md design, not yet mined |
