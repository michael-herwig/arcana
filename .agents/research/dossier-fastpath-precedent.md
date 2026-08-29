# Dossier fast-path precedent

Researched: 2026-08-28. Expires: 2027-02-28.

Handover for the design of a "discussion → hex-architect" fast path: how much
of Discover/Research/Design a downstream orchestrator may skip when the input
is a pre-made discussion dossier instead of a bare decision string, and which
phase can never be skipped regardless.

## Research: dossier fast-path precedent

### Direct answer

No shipped pipeline (spec-kit, OpenSpec, BMAD) implements the exact bundle
this decision needs — "trust a pre-made dossier, shrink discovery/research,
never skip adversarial review" isn't a named pattern anywhere surveyed. The
three tools split the trust question three incompatible ways: spec-kit
refuses to distinguish provenance at all (everything re-checked alike);
OpenSpec refuses to *persist* the upstream artifact at all (nothing to trust
or distrust — propose always re-derives from live context); BMAD *does* trust
an upstream artifact wholesale (architect never re-derives the PRD) but its
review step is optional/consultative, not mandatory. None pairs "skip
re-derivation" with "keep review mandatory" — that combination has to be
designed, not copied.

### Trends

- 2026 ADR tooling is generation/retrieval-focused (Codex CLI ADR skill,
  "conversational architecture copilots"), not staged-pipeline focused — no
  discovery/research/design staging to skip in the first place. A
  discussion-drains-into-ADR pipeline *with* skippable staged phases is a
  genuine gap, not a crowded space.
- Staleness is handled today by **refusal to persist** (OpenSpec), not by
  freshness metadata — sidesteps the problem rather than solving it; not a
  model to imitate for an artifact that must survive a session boundary.
- Adversarial review is hardening, not softening: "maker shouldn't grade the
  checker" is now a named pattern, spec-kit's own community wants a
  *stronger* final gate than `/speckit.analyze` already gives them, and the
  most-often-skipped checkpoint in staged pipelines is called out as the most
  underrated one.

### Key findings (links)

1. **spec-kit re-derives every phase, ignores provenance.**
   `/speckit.analyze` is a read-only, independent cross-artifact consistency
   pass — genuinely adversarial in effect but generic, treating
   human-clarified and AI-drafted content identically. Only `/specify` gates
   `/plan`; clarify/checklist/analyze are opt-in
   ([Agentic SDD](https://github.github.com/spec-kit/reference/agentic-sdd.html)).
   [#1323](https://github.com/github/spec-kit/issues/1323) is a live signal
   that a generic consistency pass isn't felt sufficient as a final gate.

2. **OpenSpec's explore→propose boundary is an anti-precedent for trust.**
   Explore is artifact-free by design; propose doesn't consume a file, it
   relies on same-session context, with no staleness tracking anywhere
   ([commands.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md)).
   OpenSpec considered persist-and-trust and declined it. The reusable idea
   sits next door: this repo's own OpenSpec deep-dive already rates OpenSpec's
   MODIFIED-scenario **stale-base guard** (diff incoming claims against live
   state, halt on drift) **Adopt**
   (`.agents/research/openspec-framework-analysis.md:1077`, `:962`).

3. **BMAD trusts but doesn't guard.** The architect accepts the PRD as
   canonical, layers an `ARCHITECTURE-SPINE.md` of invariants rather than
   re-deriving requirements
   ([DeepWiki: Planning Workflows](https://deepwiki.com/bmad-code-org/BMAD-METHOD/4.4-phase-2:-planning-workflows)).
   Structural PASS/REVISE/FAIL validation exists but is one of three optional
   workflows, not mandatory, and no adversarial/independent-reviewer
   mechanism is documented at the handoff
   ([DeepWiki: Testing and Validation](https://deepwiki.com/bmad-code-org/BMAD-METHOD/14.3-testing-and-validation)).
   The shape to avoid: trust with no compensating mandatory check.

4. **Two-party consensus is not a substitute for an independent reviewer** —
   the strongest, most transferable finding. Same-session self-review is
   structurally blind ("the same assumptions that produced the defect also
   produce the blind spot in the review"); its case study is an artifact that
   passed every prior check — both parties satisfied — and still hid a defect
   only a fresh-session critic caught
   ([ASDLC.io](https://asdlc.io/patterns/adversarial-code-review/)). A
   discussion two people already agreed on is the same shape of blind spot.
   Nothing surveyed supports weakening the gate because input already carries
   agreement; several sources argue consensus is a bias signal, not a safety
   one, and should weight the gate *more*.

5. **Failure modes, named and current.** Stale dossier consumed: ~1/3 of
   long-horizon agent failures attributed to context/goal drift that "fails
   quietly," confident reasoning from outdated ground truth
   ([tianpan.co](https://tianpan.co/blog/2026-04-10-stale-world-model-long-running-agents)).
   Skipped discovery missing a code-level constraint: named directly as the
   "findings review gate" failure ("a missing migration, an undocumented
   dependency, a function called from three places") — the most commonly
   skipped, most underrated checkpoint
   ([codeongrass](https://codeongrass.com/blog/where-to-gate-your-ai-coding-agent-3-checkpoint-framework/)).
   Rubber-stamp review of a pre-agreed design: both ASDLC.io and spec-kit's
   own community (#1323) converge — a review too generic or too deferential
   to prior agreement stops catching anything.

6. **Provenance/confidence tagging — the one concrete input-contract idea
   found.** Codex ADR governance recommends every AI-touched ADR record an
   "Agent Context" block (model, reasoning effort, confidence) plus a
   human-review status field, because scan-derived ADRs "capture *what* was
   decided but may fabricate the *why*"
   ([codex.danielvaughan.com](https://codex.danielvaughan.com/2026/04/28/codex-cli-architecture-decision-records-adr-automated-governance/)).
   Directly portable: provenance, confidence, and an explicit "not yet
   verified" field belong in the dossier's shape, not just its prose.

### Sources

- [github/spec-kit#1391](https://github.com/github/spec-kit/issues/1391) · [Agentic SDD](https://github.github.com/spec-kit/reference/agentic-sdd.html) · [Quick Start](https://github.github.com/spec-kit/quickstart.html) · [#1323](https://github.com/github/spec-kit/issues/1323)
- [OpenSpec explore](https://openspec.dev/docs/explore) *(404 at fetch time, cross-checked via commands.md + search)* · [commands.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md)
- [BMAD Planning Workflows](https://deepwiki.com/bmad-code-org/BMAD-METHOD/4.4-phase-2:-planning-workflows) · [BMAD Testing/Validation](https://deepwiki.com/bmad-code-org/BMAD-METHOD/14.3-testing-and-validation)
- [ASDLC.io adversarial code review](https://asdlc.io/patterns/adversarial-code-review/)
- [codeongrass 3-checkpoint framework](https://codeongrass.com/blog/where-to-gate-your-ai-coding-agent-3-checkpoint-framework/)
- [Codex CLI ADR governance](https://codex.danielvaughan.com/2026/04/28/codex-cli-architecture-decision-records-adr-automated-governance/)
- [tianpan.co stale world model](https://tianpan.co/blog/2026-04-10-stale-world-model-long-running-agents)
- This repo: [`openspec-framework-analysis.md`](openspec-framework-analysis.md) (lines 962, 1077 — stale-base guard, Adopt)

### Recommendation (rationale)

Design the fast path as **trust-scoped, not phase-scoped**: let Discover
*shrink* (bounded diff of the dossier's code-level claims against current
repo state — reuse the stale-base-guard shape already rated Adopt in this
repo, rather than a full architecture-explorer sweep) and let Research *skip
conditionally* (only axes the dossier already cites sourced findings for) —
those are re-derivation costs a well-formed dossier genuinely pays down.
Never shrink adversarial Review — weight it *more* when a dossier is present,
since every source surveyed treats pre-existing agreement as a bias signal
the independent gate exists to catch, not grounds to relax it. The one clear
gap worth hex being early on: no surveyed tool marks dossier
provenance/staleness/confidence as first-class input fields — model that on
hex's existing `[NEEDS CLARIFICATION: ...]` marker convention plus the Codex
"Agent Context" idea, so a stale or under-verified dossier fails loud at
Discover instead of silently draining into an unearned Accepted ADR.
