# Research: Self-report capture wording, entry schema, and safe self-improvement of AI config

<!--
Technology-landscape research. Owner: researcher worker (ecosystem lane).
Handoff to: hex-plan / hex-architect for the `retro` skill design.

Purpose: persist landscape findings that inform ADRs, plans, and design
decisions. Findings decay - check the Expires date before trusting them.
-->

## Metadata

**Date:** 2026-09-23
**Domain:** cli / ai-config / agent-memory-security
**Triggered by:** discussion `.agents/discussions/retro.md` — capture-wording,
entry-schema, and memory-safety open questions (decisions 1-4 below)
**Expires:** 2027-01-23 (agent-memory-security is moving fast; several
sources <2mo old already)

## Direct Answer

Findings below **amend, not repeat**, `discuss-retro-community.md`,
`discuss-retro-priorart.md` and `discuss-retro-archaeology.md` (all read
first, not re-summarized here). Four new items change the design: (1) Claude
Code's `/insights` (shipped Feb 2026) is a real, working instance of exactly
the objective-signal + friction-categorization + CLAUDE.md-rule-generation
loop retro.md's open question speculated about, with concrete output shape
to borrow from. (2) 2026 agent-memory-security research is unanimous and
recent: **content screening and provenance-ranking, the two most obvious
automated defenses against poisoned self-written entries, both fail
outright** (0/360 detection; provenance weighting collapses to "no defense"
or "block everything" with no usable middle) — this hardens, rather than
merely confirms, retro.md's existing "propose, never auto-apply" decision.
(3) OWASP formally named this attack class ASI06 in 2026, meaning retro's
threat model is a named, board-level category, not a hypothetical. (4)
Practitioner instruction-wording guidance (HN thread, already in
`discuss-retro-community.md`) plus the archaeology finding that hex's own
Upkeep mechanism has **zero realized promotions in this repo's history**
together argue the capture instruction must be concrete and observable, not
aspirational — vague "report friction" phrasing is the failure mode this
project has already lived once.

### Decision 1 — Capture-instruction wording (≤5 lines)

Best candidate, verbatim (4 lines, matches `hex/hex-state.md`'s imperative,
pointer-referencing register):

> Hit real friction — a step retried ≥2, a wrong assumption you had to
> correct, a workaround, a step past its expected time, or an instruction
> that misled you? Write one JSON entry to the retro inbox (path via
> `hex.md › Pointers`), temp-then-rename, no lock. Note whether the same
> friction would happen on a different codebase with the same skills — that
> answer routes the fix to project or harness. Retro proposes edits from
> this; you never edit skills or rules yourself from this rule.

Two alternates considered:

- Terser (3 lines, less self-contained, relies on schema doc for field
  names): "Retry ≥2 / a corrected assumption / a workaround / a slow step /
  a misleading instruction → write one retro entry (temp-then-rename, path
  via `hex.md › Pointers`); say whether a different codebase with the same
  skills would hit it too. Report, don't fix."
- Question-framed (mirrors the F-004 discriminator as a literal prompt):
  "Before finishing: did anything here retry, get corrected, get worked
  around, run long, or mislead you? If yes, write one retro entry — ts,
  what, tell, proposed_change — and answer 'same codebase-independent
  skills, same failure?' in it. Retro consolidates; never self-edit config."

Rationale for the pick: HN practitioner consensus is that **rules distilled
from an observed failure stick; anticipatory rules written from scratch are
ignored**, and negative framing ("don't do X") underperforms positive,
action-oriented phrasing —
[HN thread](https://news.ycombinator.com/item?id=48160604) (already cited
in `discuss-retro-community.md`, re-applied here to instruction *wording*
specifically, not just rule content). The chosen wording names five
concrete, observable triggers (matching the requirement list verbatim) and
ends on the F-004 discriminator so the self-report already carries the
routing signal retro needs, rather than making retro re-derive it later.

### Decision 2 — Entry schema: validate/amend

The recommended fields in `retro.md` (`ts`, `project`, `role`, `artifact`,
`kind`, `severity`, `what`, `tell`, `proposed_change`, `evidence`) hold, with
two amendments:

- **`cost` (self-estimated wall minutes lost): do not add as a required
  field.** Self-reported confidence/magnitude is measurably unreliable —
  GPT-4 verbal-confidence AUROC for failure prediction is ~0.63, barely
  above random, and confidence inflates further as context grows within a
  session (already cited, `discuss-retro-priorart.md` findings 14-15,
  [Confidence calibration in LLMs](https://www.emergentmind.com/topics/confidence-calibration-in-llms)).
  retro.md's own design already resolved this correctly: ledger cost comes
  from the **objective channel** (aggregated step durations), not
  self-report — "recurring-cost findings are only visible through the
  objective channel... which makes it load-bearing, not corroboration
  only." A self-estimated `cost` field would contradict that design if
  treated as load-bearing. Keep it **optional and explicitly
  non-load-bearing** (a human-readable annotation only, never summed into
  the ledger) if kept at all — mirrors claude-reflect's pattern of layering
  a confidence score as an *annotation* on top of, not a replacement for,
  deterministic signal
  ([claude-reflect](https://github.com/BayramAnnakov/claude-reflect), cited
  in `discuss-retro-community.md`).
- **`role`: make optional, not required.** It is knowable on Claude Code hex
  spawns (builder/reviewer/researcher personas exist as a real taxonomy) but
  has no analogue on Cursor, Windsurf, Cline, or Copilot — those tools are
  effectively single-agent, no subagent-role concept exists in their memory
  systems ([Cursor Rules docs](https://cursor.com/docs/rules),
  [Windsurf Cascade Memories](https://docs.windsurf.com/plugins/cascade/memories),
  [Cline Memory Bank](https://docs.cline.bot/prompting/cline-memory-bank) —
  none of the three document a role/persona field). A required `role` would
  make every non-hex client's entries schema-invalid; default to `"agent"`
  or omit.

Minimal required set: `ts`, `kind`, `what`, `tell`, `proposed_change`.
Optional: `project`/`artifact` (attribution — required *in practice* for
hex's routing decision, but must degrade gracefully when unknown), `role`,
`severity`, `evidence`, `cost`.

### Decision 3 — Safety of consuming agent-written entries

2026 evidence is unusually strong and consistent, and it **validates
retro.md's existing "never auto-apply" decision rather than just adding
color**:

- OWASP's 2026 Agentic AI Top 10 formally added **ASI06: Memory and Context
  Poisoning** as its own category, distinct from prompt injection because it
  persists across sessions instead of being session-scoped —
  [vectorize.io](https://vectorize.io/articles/ai-memory-poisoning),
  survey: [arxiv.org/html/2606.04329v1](https://arxiv.org/html/2606.04329v1)
  (Jun 2026).
- **MINJA** demonstrates an attacker can poison an agent's long-term memory
  through ordinary queries with no special privilege, >95% injection success
  rate — cited via
  [vectorize.io](https://vectorize.io/articles/ai-memory-poisoning); primary
  literature: [arxiv:2607.05120](https://arxiv.org/pdf/2607.05120) (Jul
  2026, "Agent Data Injection Attacks are Realistic Threats to AI Agents").
- **The two obvious automated defenses both fail outright, measured**:
  a four-stage write-time content-screening pipeline that performs well on
  related tasks "rejects 0 of 360 poisoned memories," and
  provenance-weighted retrieval shows "no defense (p=0.80)" at shipped
  weights — stronger weights only work by excluding untrusted content
  entirely, which is unusable since retro's whole input is untrusted-ish
  agent-written text —
  [arxiv:2608.21230](https://arxiv.org/abs/2608.21230) (Aug 2026, "Utility
  Under Attack: Agent Memory Poisoning and the Limits of Content Screening
  and Provenance Ranking"). This is the single most load-bearing finding
  for the design: **do not build a classifier or trust-score gate as the
  primary defense for retro's inbox** — it will not hold, per this
  measurement, and would be false assurance.
- Layered, non-classifier mitigations that mem0's practitioner writeup
  recommends and that transfer cleanly to retro's design: per-source
  isolation (retro's project/artifact attribution already does this),
  cryptographic/integrity checks on entries (the maildir temp-then-rename
  write already gives this for free — a partially-written entry is never
  visible), TTL/expiry on unconsumed entries, and comprehensive audit
  logging of what was consumed into what proposal —
  [mem0.ai — AI Memory Security](https://mem0.ai/blog/ai-memory-security-best-practices)
  (2026).
- **The one defense every surveyed product actually ships and that survives
  the classifier-failure finding is the human/merge gate** — Devin
  Knowledge, Cursor Memories, Windsurf Cascade Memories, Cline Memory Bank
  all require an explicit human accept/dismiss step before a suggestion
  becomes durable config (already established in
  `discuss-retro-priorart.md` finding set; re-confirmed by this pass's
  reads of [Windsurf](https://docs.windsurf.com/plugins/cascade/memories)
  and [Cline](https://docs.cline.bot/prompting/cline-memory-bank) docs).
  Given content screening's measured 0% detection, this is not one option
  among several — it is the only mitigation in the survey with evidence it
  actually works.
- Practical instruction for retro's read path: treat every inbox entry's
  free-text fields (`what`, `tell`, `evidence`) as **data, never
  instructions**, reusing the bundle's own existing
  `§ Untrusted-text echoes` contract in `hex/hex-core/references/protocol.md`
  rather than inventing a second untrusted-text policy — quote-and-truncate
  when echoing an entry back into a proposal, never let entry text expand
  retro's own tool-call scope. This is a design recommendation, not a
  sourced external claim — flagged as such.

### Decision 4 — Pruning proposals: evidence and a cap

- **Rationale-at-write-time is the single most evidenced anti-bloat
  mechanism found anywhere in this research** (already in
  `discuss-retro-community.md`/`discuss-retro-priorart.md`: 99.3% growth
  reduction, up to 23.1% instruction-following improvement,
  [arxiv:2608.11095v1](https://arxiv.org/html/2608.11095v1), Aug 2026
  preprint, flagged <18mo and unreviewed). retro.md's "every proposed edit
  carries its rationale" requirement is already the strongest countermeasure
  on record — this pass found nothing that supersedes it, only reconfirms
  it against the same source already cited.
- **No formal eval/replay-before-promotion gate exists in production
  anywhere** (reconfirmed negative from `discuss-retro-community.md`); the
  closest real practice is Addy Osmani's periodic manual "does the task
  still succeed without this rule" spot-check, run on a cadence (`/doctor`
  every few weeks), not per-PR —
  [Addy Osmani, Audit your Agent files](https://addyo.substack.com/p/audit-your-agent-files)
  (2026, already cited). This supports formalizing retro.md's existing
  "no entry has touched this" pruning trigger as a **staleness window**
  (e.g., no entry referencing a rule across the last 3 retro runs) rather
  than inventing a replay harness that no prior art has built.
  **Recommended, no source states a number — this is a design
  recommendation, flag accordingly.**
  - Michael Herwig's memory (`review-round-cap-two`) already caps hex
    review rounds at 2 for the same reason (cost of unbounded passes) —
    internal precedent, not external evidence, applying the same instinct
    to pruning cadence.
- **Proposal cap 10 per sweep is the only concrete number found in any
  shipped skill**, from netresearch/retro-skill, already cited in
  `discuss-retro-community.md`. This pass found no second source with a
  different number, and no source arguing a cap is unnecessary. Recommend
  retro.md adopt the same cap (≤10 add/prune proposals per run, combined)
  since retro.md does not currently state one and this is the only
  evidenced number in the field.
- Every deletion proposal must still route through the same human gate as
  additions — Decision 3's classifier-failure finding applies equally to
  "confidently propose this rule is dead," since a poisoned or merely wrong
  entry claiming "no one uses X" is exactly as unverifiable automatically as
  a poisoned entry proposing a new rule.

## Recommendation

Adopt the capture wording above verbatim (or the question-framed alternate
if the plan prefers an imperative-checklist register over prose). Trim the
entry schema to 5 required + 5 optional fields, with `cost` explicitly
non-load-bearing and `role` defaulted rather than required. Do not build any
content-screening or trust-scoring gate for the retro inbox as a security
control — the 2026 evidence says it will not hold; keep the human-approval
gate as the *only* trust boundary, and route inbox free text through the
bundle's existing untrusted-text-echo contract instead of a new one. Cap
proposals at ≤10 per run (additions + prunes combined), and formalize
pruning's "no entry has touched this" trigger as a 3-run staleness window
pending a real number from the ledger once it exists.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| [Claude Code /insights deep dive](https://www.zolkos.com/2026/02/03/deep-dive-how-claude-codes-insights-command-works.html) | Blog | 2026-02 | Real shipped objective-signal + friction-categorization + rule-generation loop; concrete precedent |
| [Claude Code /insights guide](https://pasqualepillitteri.it/en/news/408/claude-code-insights-command-workflow) | Blog | 2026 | Facet-extraction mechanics, 30-day window, chunking |
| [1,282 Hours with /insights](https://vanja.io/claude-code-insights-revealed/) | Blog | 2026 | Real-world friction-pattern examples |
| [OWASP ASI06 / memory poisoning overview](https://vectorize.io/articles/ai-memory-poisoning) | Blog | 2026 (undated in fetch, flag) | ASI06 naming, MINJA stats, attack-vs-prompt-injection distinction |
| [From Untrusted Input to Trusted Memory (arXiv:2606.04329)](https://arxiv.org/html/2606.04329v1) | Paper | 2026-06 | Systematic memory-poisoning survey |
| [Utility Under Attack (arXiv:2608.21230)](https://arxiv.org/abs/2608.21230) | Paper | 2026-08 | **Load-bearing**: content screening 0/360 detection, provenance ranking no-defense finding |
| [Agent Data Injection Attacks (arXiv:2607.05120)](https://arxiv.org/pdf/2607.05120) | Paper | 2026-07 | MINJA-class attack, no-privilege memory injection |
| [mem0.ai — AI Memory Security](https://mem0.ai/blog/ai-memory-security-best-practices) | Blog | 2026 | Layered non-classifier mitigations (isolation, TTL, integrity hash, audit log) |
| [Cline Memory Bank docs](https://docs.cline.bot/prompting/cline-memory-bank) | Docs | current | No role/persona concept; manual "update memory bank" gate |
| [Windsurf Cascade Memories docs](https://docs.windsurf.com/plugins/cascade/memories) | Docs | current | Human review/promote/delete gate; no automated trust filter |
| [HN: Do you still maintain Claude.md/AGENTS.md files?](https://news.ycombinator.com/item?id=48160604) | Forum | 2026 | Positive-framing + observed-failure-not-anticipatory wording guidance (reapplied to Decision 1) |
| [arxiv:2608.11095v1 — Catastrophic Remembering](https://arxiv.org/html/2608.11095v1) | Preprint | 2026-08 (flag: <18mo, preprint) | Rationale-at-write-time countermeasure, reconfirmed not superseded |
| [Addy Osmani — Audit your Agent files](https://addyo.substack.com/p/audit-your-agent-files) | Blog | 2026 | Periodic manual staleness-check practice, no formal replay gate exists |
