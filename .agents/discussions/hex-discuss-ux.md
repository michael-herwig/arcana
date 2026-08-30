# Discussion: hex-discuss UX — faster dispatch, explicit-only drain, eager research

State: handed-off → plan · Updated: 2026-08-30
Ratified: 2026-08-30 → plan
Confidence: Michael ratified at the restate-gate; decisions backed by
research vintage 2026-08-30 (discuss-ux-{sota,community,adjacent}.md,
expire 2027-02-28) plus adr_0008 dogfood experience.

## Intent

hex-discuss feels slow and naggy in practice. Three complaints, one vision:
the mode should be an *interactive* discussion — on entry it immediately
dispatches background subagents (codebase recon, web research) from the
information already given, then interviews; as results land it informs and
re-asks. Ceremony before the first substantive answer, unprompted
"ready to drain?" nudges, and research locked behind the disputed-fact
trigger are the defects.

Touches: `hex/hex-discuss/SKILL.md` (+ `references/reach.md`), possibly
adr_0008 contract amendments (C-7xx). Out of scope: other hex modes'
research triggers.

## Decisions

- Answer-first ordering; shared-contract reads (`protocol.md`, `workers.md`,
  `models.md`) lazy — at first spawn, not entry.
- Drain is user-initiated only. Stop rule reworded: user ends the interview;
  restate-gate remains the completeness check at that moment. One affordance
  line at entry, never repeated.
- Entry fires a default recon wave automatically from intake slot 1 —
  no waiting for a disputed fact. Fits the existing quick-check gear
  (≤3 concurrent) — no new approval gate.
- Research expansion is opt-in multi-select over method lanes (community
  threads/blogs · adjacent fields · SOTA · competitive/vendor · repo
  archaeology), reusing the deep-sweep spend-confirmation model.
  Researcher blindness holds per lane.
- Interactive fold-in: a landed result that changes a live thread feeds the
  next question, not just a one-line aside.
- Entry wave composition: fixed 2 lanes — codebase recon + prior-art web
  scan — always; leaves 1 slot of the default 3-gear for the first
  disputed-fact spawn. (Michael, 2026-08-30, via chips.)
- Stub stays at entry: with an automatic entry wave there is always
  imminent content, so deferral buys nothing; stub also arms the
  hex-state freeze.
- Researcher spawn contract becomes a shipped reference: a prompt
  preamble + structured return schema the skill dispatches with. Return
  schema carries, beyond findings+sources: `negative:` (what didn't pan
  out, dead ends, contradicting evidence — reported, never silently
  dropped) and `leads:` (adjacent fields/topics worth a follow-up lane,
  one line each). `leads:` entries are the feedstock for later
  multi-select expansion offers — the lane menu grows from research, not
  a static list. Home: new `hex-discuss/references/` file (SKILL.md body
  is at ~397/400 of the C-701 ceiling — inline impossible); extends
  `workers.md` researcher role, links never copies (DESIGN.md
  single-source rule).
- Expansion offer timing: once, right after entry-wave dispatch, seeded
  with default lanes; afterwards only on user demand or when a new
  `leads:` lane arrives — always with running spend total. Never
  skill-judged re-offers. (Michael, 2026-08-30, via chips.)
- The multi-select subsumes the quick-check/deep-sweep binary — a sweep
  is just a wide lane selection; hard total cap 12 and
  spend-in-chip-text survive unchanged. Two-gear vocabulary goes
  entirely, no named preset. (Michael, 2026-08-30.)
- Question cadence UPDATED on research evidence: design questions may
  ship in small dependency-batched sets (cap ~3, recommendation per
  option stays mandatory), replacing strictly-one-per-turn. Sources:
  Nielsen, Cursor capped-batch tool, ChainBuddy study, grill-me
  dependency-level batching [discuss-ux-community.md, discuss-ux-sota.md].
- Fold-in refinement: background results surface at the next natural
  turn boundary, flagged as new — never spliced mid-turn; the artifact
  is the durable "visible surface" for observations (Horvitz
  bounded-deferral) [discuss-ux-adjacent.md].
- Drain nuance confirmed: reflexive continue/wrap-up offers are the
  complaint; a substantive terminal summary is welcomed — restate +
  terminal report stay, unprompted offering goes
  [discuss-ux-community.md].
- Council lane (working position, from karpathy/llm-council): an opt-in
  multi-select lane for judgment-heavy disputed points — N models answer
  the same design question, anonymized mutual ranking, chairman
  synthesis returned as one aside. Scopes an exception into "never spawn
  on an opinion": rule holds for skill-initiated spawns; user-opted
  council lanes target opinions by design, spend confirmation covers it.
  Degraded on single-provider harnesses (diversity is the value; full
  value needs the cross-model path, e.g. codex plugin). Cost 2N+1 calls,
  rides spend-in-chip-text.
- Entry-wave guardrail from split community sentiment: proactive
  research is praised for grounding/catching real issues, resented when
  it takes over reasoning the user wanted — entry wave stays
  facts-and-grounding only, never position-taking (blindness rule
  extends to it) [discuss-ux-community.md].

## Research

- `.agents/research/discuss-ux-sota.md` — termination ownership,
  dispatch timing, pacing across spec-kit/OpenSpec/Kiro/Task Master/
  aider/plan modes/Devin/grill-me (14 findings). Expires 2027-02-28.
- `.agents/research/discuss-ux-community.md` — practitioner sentiment
  on cadence, ceremony, wrap-up prompts, proactive research. Expires
  2027-02-28.
- `.agents/research/discuss-ux-adjacent.md` — mixed-initiative HCI
  (Horvitz) + requirements-elicitation interview structure and failure
  modes (9 findings). Expires 2027-02-28.

## Related

- `.agents/adrs/adr_0008_pre_plan_discussion_mode.md` — the contracts
  (C-7xx) these changes amend; drain target: → plan, amending in place
  (adr_0009 errata-fold precedent; Michael, 2026-08-30, via chips).
- `hex/hex-discuss/SKILL.md` (~397/400 body) + `references/reach.md` —
  the files touched; new `references/` spawn-contract file added.
- `hex/hex-core/references/workers.md` § Role index — researcher role
  the spawn contract extends, never copies.
- `.agents/discussions/hex-discuss-skill.md` — the original discussion
  that produced adr_0008 (drained → architect).
- https://github.com/karpathy/llm-council — council pattern source
  (anonymized cross-review + chairman synthesis); also queued in
  `TODO.md:20`.

## Verification

- `grim build hex/hex-discuss` green; SKILL.md body ≤400 lines (C-701);
  full sweep `task publish -- --dry-run` exit 0.
- adr_0008 § Validation re-derived for every amended contract (stop
  rule, research trigger, cadence, announce form) — the round-2 lesson:
  never left stale after a fix pass.
- Dogfood: one real /hex-discuss run on a fresh topic exercising entry
  wave, a landed-result-fed question, a leads-fed expansion offer, and a
  user-called drain — no unprompted drain offer observed across the run.
