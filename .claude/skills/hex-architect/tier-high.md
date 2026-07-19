# Tier: high

The full treatment for **one-way-door-high** decisions — a public API
shape, a wire protocol, an auth boundary redesign, a data model migration
with no rollback. Mandatory architect, mandatory 3-axis research with
user-selected axes, an adversarial design panel, and cross-model design
review as a default gate before handoff. Five phases, not six —
hex-architect never decomposes into executable tasks; that is `/hex-plan`'s
job once it consumes the ADR.

`Read` this file from [`SKILL.md`](SKILL.md) after the config is announced.
Shared vocabulary is linked, not restated: roles in
[`workers.md`](../hex-core/references/workers.md), model classes in
[`models.md`](../hex-core/references/models.md), and the outer contracts in
[`protocol.md`](../hex-core/references/protocol.md).

**Meta-plan preview is mandatory.** At `high`, the gate in
[`SKILL.md`](SKILL.md) step 4 always blocks for explicit approval — this tier
is expensive, and the preview catches a misclassification, and confirms the
research-axis selection, before workers launch.

## Phase 1: Discover (single worker, full)

Launch **1** `architecture-explorer` covering every area the decision
touches — its dependency-graph step already traces what an area imports and
what imports it, so cross-module reach is covered by one worker, not a
per-area fleet. In parallel, read directly the project's architectural
conventions for every area touched, and all prior ADRs/plans/research in the
convention-resolved artifact home for the whole domain.

**Gate** — a full architecture map is produced; every prior decision record
in the domain is enumerated.

## Phase 2: Research (3 axes, gate-selected — mandatory)

[`classify.md`](classify.md) proposes at least 3 ranked candidate axes
(folding in any `hex.md › Preferences` research axes of interest and the
project's product knowledge — keywords/comparable tools, located via
`hex.md › Pointers`; a researcher assigned the product/competitive-landscape
axis runs focus `competitive-research`); at the meta-plan
gate the user **selects 3** — this is the defining interaction of
hex-architect at this tier, always presented as an explicit choice even
though the rest of the gate is a blocking approval regardless. Default on
plain approval: the classifier's top 3. Launch **3** `researcher` workers in
a single concurrent batch, one per selected axis. Each returns an
opinionated recommendation with trend analysis, adoption signals, and
citations. Persist each as a research artifact — mandatory at this tier;
substantial findings are expected.

**Gate** — three research artifacts persisted; axis choices recorded with
their source (classifier default or user pick).

## Phase 3: Classify (sequential)

Confirm **one-way-door high** in the record header. If the classification
fails (the decision is actually medium), **downgrade and re-run** as
`/hex-architect medium "…"` — never silently over-specify a medium decision
or under-specify a large one.

Required artifacts this tier:

- the **ADR** (mandatory);
- a **system-design doc** (when blast radius is cross-area or
  external-contract, per [`classify.md`](classify.md) / [`overlays.md`](overlays.md));
- **persisted research** (from Phase 2).

**Gate** — blast radius, reversibility, and all required artifacts listed in
the record header.

## Phase 4: Reason & Design (architect mandatory, ADR + system-design)

Launch **1** `architect` worker; its model class is `deep-reasoning`
([`models.md`](../hex-core/references/models.md)). A downward override is
honored but never silent — the announce block flags it. Produce the ADR
and, when scope warrants, the system-design doc.

Design must include everything the `medium` tier requires, plus:

- **Trade-off matrix** — at least **3** options (not 2), weighted criteria,
  risks, reversibility, and a recommendation with rationale.
- **Migration / rollout plan** — how existing code, data, and consumers move
  to the new shape without breakage, or with explicit breakage communicated.
- **Full C4** — Context, Container, Component, and Code-level detail when the
  decision is significant enough to warrant it.

**Gate** — the ADR (and system-design doc, when produced) is written, the
migration plan is present, and the contracts are testable.

## Phase 5: Review (adversarial design panel + mandatory cross-model)

Run the [Review-Fix Loop](../hex-core/references/protocol.md#the-review-fix-loop)
on the design artifact — **plan-artifact scope: one panel round**; fix
application, conditional re-validation, and escalation follow the
canonical loop's artifact-scope rule, never restated here.

**Round 1** — launch concurrently:

- `reviewer` (focus `spec`) — are the contracts testable? Internally
  consistent with the stated decision?
- `reviewer` (focus `quality`, prompted adversarially) — steelman every
  rejected option; is the reversibility claim honest; does the design
  introduce a boundary or convention violation?
- `researcher` — does the design miss a trending pattern, a known pitfall,
  or a state-of-the-art approach the research axes didn't surface?
- `reviewer` (focus `security`) — mandatory when
  [`classify.md`](classify.md) fired the compliance/security-touch signal or
  `hex.md › Preferences` names the touched area as always-security-sensitive.

**Cross-model design review — a default part of this tier's flow.** After
the panel converges, run the configured adversary skill once in
`plan-artifact` scope on the ADR (and system-design doc, if produced).
One-shot, no loop; 4-way triage (actionable / deferred / stated-convention /
trivia); actionable fixes re-validated by a single `reviewer` (focus `spec`)
pass
([adversary contract](../hex-core/references/protocol.md#adversary-contract)).
If the skill is unavailable, log
`Cross-model design review skipped: <reason>` and continue — but **surface
the skip prominently in the handoff**, since one review layer was missed.

**Gate** — the design artifact is ready for handoff; both panel and
cross-model deferred findings are documented. Then run the
[upkeep step](../hex-core/references/protocol.md#upkeep-step) and emit the
handoff from [`SKILL.md`](SKILL.md).
