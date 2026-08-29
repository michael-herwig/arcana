# Discussion: hex-discuss — pre-plan discussion mode for the hex bundle

State: handed-off → architect &nbsp; Updated: 2026-08-28
Ratified: 2026-08-28 → architect
Participants: Michael + orchestrator, ~12 turns, 2026-08-27/28.

This artifact is self-contained: an architect (or planner) consuming it
needs no access to the source conversation.

## Intent

Michael — and now coworkers adopting the hex skills — open most sessions
with "let's just discuss, do not edit anything": an interactive
elaboration/research phase *before* any plan mode or architect call. Wanted:
the agent grills back (pushes on design ideas, checks them against
state-of-the-art), spawns background research while the conversation
continues, offers ready-to-pick options, keeps async threads, and leaves a
documented outcome. Sometimes the discussion nearly replaces the architect —
"an on-demand architect, but discussing with me instead of shaping alone."
For less-expert coworkers it must *feel like a discussion, not a background
process*. Outcome shape: new hex bundle member(s) — a discuss skill plus a
discussion-artifact convention — published via grim like the rest of hex.

## Requirements

Functional:

- Session-opening **mode**, entered by explicit invocation/trigger phrase;
  stance must survive 50+ turns; exits only on explicit user handoff.
- **Intake protocol** — one composite opening ask, three slots: (1) the
  problem in the user's words, (2) source-material inventory (tickets,
  example apps, references, code — "dump anything"), (3) outcome shape
  (plan? ADR? just clarity?). Slot 3 pre-sets the drain target; slot 2
  seeds `## Related` and grounds researchers.
- **Dual question cadence**: inventory questions batch (composite ask, any
  subset answerable); design questions strictly one per turn, each with an
  attached recommendation.
- **Chips default**: design questions ship as selectable options + free-text
  escape ("harness interactive prompts where available"); open prose
  questions allowed but exceptional.
- **Grill ruleset**: (a) rebuttal gate — categorize user pushback as new
  evidence (update, state what changed) vs repeated opinion (hold, restate
  evidence); (b) anti-theater — never manufacture objections; agreement on a
  decision-relevant point names the strongest remaining counter-argument
  once; (c) scoped elicitation menu — pick ≤2 fitting techniques per thread
  (premortem, inversion, first-principles, force-rank), never a catalog;
  (d) researcher blindness — research prompts state questions neutrally,
  never which side user/orchestrator favors.
- **Background research, two gears**: default ≤3 concurrent lightweight
  researchers, spawned on decision-relevant disputed facts (not opinions,
  not repo-answerable questions), results woven in as one-line asides; plus
  an on-demand **deep sweep** (discover→dedup→analyze fan-out, ~12 workers,
  artifacts persisted per lane). Chips moment when a topic looks
  sweep-worthy: quick check / deep sweep / skip.
- **Discussion artifact** (this document is the reference instance):
  lazy materialization — file appears on first research landing, first
  captured requirement, or user's "capture"; sections materialize on first
  content ("never scaffold an empty section"); menu: Intent, Requirements,
  Decisions, Threads, Research, Related, Open questions. Doubles as async
  thread board and enables cross-session re-entry.
- **Coverage-based stop rule** — interview until covered, never a question
  count. **Restate-gate** before drain: explicit yes to a structured restate
  (Outcome / User / Why now / Success / Constraint / Out of scope); soft
  confirmation ("sounds good") is not consent.
- **Four-target drain** at handoff: → plan (/hex-plan), → ADR (via
  /hex-architect), → spec fold (`.agents/specs/`), → *promote to project
  context* with consent (a remark that is actually a durable convention goes
  to CLAUDE.md/hex.md instead of dying with the discussion). Terminal
  states: `active | parked | handed-off → plan|architect|dropped` —
  `dropped` is a valid success (field evidence: discussions legitimately
  talk users out of building).
- **Tone rule**: reads as conversation — researchers surface as one-line
  asides, artifact grows silently, no phase announcements or thread-board
  recitals unless asked.

Non-functional / constraints:

- **Scoped writes only**: `.agents/research/` artifacts + its own
  discussion file. Never code, config, or other artifacts.
- **Persistence within grim's shippable surface** (skills/rules/agents — no
  hooks): tiny always-on rule (trigger + stance, compaction-proof) + skill
  (full protocol). Optional hardening: hex-init *provisions* a
  UserPromptSubmit hook with consent. Native plan mode is unusable as
  enforcement (skills cannot enter it — open FR — and it blocks the scoped
  writes).
- **Cheap to skip**: no artifact obligation for small discussions (OpenSpec
  precedent; OpenAI guidance treats extended clarification as an
  anti-pattern for simple tasks).
- Cross-client: shipped files use capability classes, never harness-specific
  tool or model names (house rule, hex/DESIGN.md).
- Artifact drain-readiness quality bar: self-contained, names
  files/interfaces, states out-of-scope, ends with a verification step.

## Decisions (working — taken with Michael during the discussion)

- Writes: **scoped** over fully-ephemeral — re-entrancy across sessions won.
- Home: **`.agents/discussions/`** — new convention, provisioned by
  hex-init (dir + pointer in `hex.md › Pointers`). Distinct artifact class:
  not research (evidence, expires), not ADR (ratified), not plan
  (execution). Upstream buffer that drains and closes.
- **No C-/S-IDs in discussion artifacts** — requirements stay provisional
  prose; IDs assigned at plan/spec time (no collision with fold-back).
- Lazy materialization for file *and* sections; template documents the full
  menu (lives in `hex/hex-init/assets/templates/` beside the others).
- Persistence = rule + skill split (see NFR above).
- Architect fast-path: discuss never authors ADRs; /hex-architect accepts a
  discussion artifact as input, skips its own Design phase, runs adversarial
  review + ADR authoring. (Proposed, unchallenged in discussion.)
- Lean: **no tiers** for discuss — scales naturally with conversation; at
  most a research on/off + deep-sweep gear. (Deviates from house tier
  pattern; needs ratification.)

## Threads

- Writes contract — closed (scoped writes).
- Artifact taxonomy & home — closed (`.agents/discussions/`).
- Grill ruleset — closed (4 rules above, research-backed).
- Adaptive structure — closed (lazy sections, single-precedent field-wise,
  own design call).
- Intake/cadence/chips/tone — closed (Anthropic "start with the problem /
  name the outcome" guidance folded in).
- Persistence mechanics — closed as lean (rule + skill), boundary detail open.
- Reddit evidence lane — closed dead: unreachable by every route (WebFetch,
  proxy, search backend, JSON API); community signal rests on HN/
  practitioners lane; gap documented in research artifacts.
- All remaining open points — handed to architect (below).

## Research

Persisted in `.agents/research/` (all Expires 2027-02-28):

- `.agents/research/discuss-skills-field.md` — named-tool deep pass:
  superpowers, spec-kit clarify, OpenSpec explore, plan mode, grill-me. Law:
  one design question at a time; background-research-while-discussing has
  **no shipped prior art anywhere** — greenfield differentiator.
- `.agents/research/discuss-mode-mechanics.md` — persistence ranking
  (hooks > rules > skills > output styles), skill-writes/hook-reads pattern,
  plan-mode entry FR, background-subagent caps. Grounds the rule+skill split.
- `.agents/research/discuss-grill-mechanics.md` — pushback wording: rebuttal
  categorization, anti-theater, independence gate, BMAD menu, forced-critique
  templates; MADR "More Information" as Related-section phrasing.
- Two-wave sweep (46 unique sources, 11 workers):
  `.agents/research/discuss-anthropic.md`,
  `.agents/research/discuss-openai.md`,
  `.agents/research/discuss-github.md`,
  `.agents/research/discuss-practitioners.md`,
  `.agents/research/discuss-vendors.md`. Highlights: coverage-based stop rule + AskUserQuestion
  interview prompt + fresh-session handoff (Anthropic); clarification as
  anti-pattern for simple tasks (OpenAI); soft-confirmation rejection +
  6-part restate + one-question+guessed-answer convergence (GitHub);
  spec/brainstorm stage praised while plan documents rated low-value,
  plan-mode's regenerate-not-edit complaint (practitioners); vendor artifact
  homes diverge, explicit-handoff uniform (vendors).
- Resolved conflict: Anthropic's fresh-session handoff vs grill-me's
  Q&A-is-the-context → the artifact reconciles both (same-session keeps the
  conversation; a quality-bar artifact makes fresh-session lossless). This
  conflict is the argument for the artifact's existence.

## Related

Links to other decisions and resources:

- `hex/DESIGN.md` — binding constitution; announce-block house style (this
  skill's tone rule diverges), capability classes, single-source contracts.
- `.agents/adrs/adr_0005_archive_fold_back.md` — spec fold-back; the drain's
  spec target must not create a second fold path.
- `.agents/adrs/adr_0003_configuration_customization_surface.md` — frozen v1
  config keys; any discuss knob (research on/off, sweep) must fit or extend it.
- `.agents/adrs/adr_0004_cross_repo_federation.md` — sibling-repo link
  conventions for `## Related`.
- `hex/hex-core/references/memory.md` — artifact taxonomy rules; gets the
  "discussion state → discussion artifact, never hex.md" sibling rule.
- `hex/hex-init/SKILL.md` + `hex/hex-init/assets/templates/` — provisioning
  home for the new convention + template.
- Out of scope (parked TODO siblings, separate discussions): greenfield
  init, meta-loop/adr_0007 milestone driver, security settings,
  finer-grained settings, state-file gitignore complaint.

## Open questions (the architect's docket)

1. Rule-vs-skill text boundary: exactly what lives in the always-on rule
   (context budget!) vs the skill body.
2. First **rule artifact** in the hex bundle — grim packaging, bundle TOML,
   install-surface implications.
3. Tone rule vs DESIGN.md announce-block convention — ratify the exception
   or find a conforming quiet form.
4. Architect fast-path — exact amendment shape to /hex-architect (input
   contract, which phases skip, where adversarial review still bites).
5. Deep-sweep gear in shipped files — express multi-wave fan-out via
   capability classes without naming harness tools.
6. No-tiers deviation — ratify or map onto the house tier pattern.
7. Optional hook provisioning by hex-init (claude-specific) — cross-client
   stance and consent flow.
8. Next ADR takes **C-7xx** (0007 holds C-6xx).

## Verification

For the architect run: the resulting ADR must gate against `hex/DESIGN.md`
resolved decisions and answer docket items 1–8 explicitly. For the eventual
implementation: `grim build` green on every changed skill/rule; a dogfood
discussion (like this one) exercised end-to-end — mode entry, one background
research pass, chips, restate-gate, drain to plan — before release.
