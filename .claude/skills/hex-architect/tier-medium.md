# Tier: medium

The **default** architecture tier — one-way-door-medium decisions: a storage
layout, a caching strategy, an internal contract spanning a module or two.
Grounds the decision in a real architecture map, delegates the design to a
dedicated `architect` worker, and produces an ADR. Five phases, not six —
hex-architect never decomposes into executable tasks; that is `/hex-plan`'s
job once it consumes the ADR.

`Read` this file from [`SKILL.md`](SKILL.md) after the config is announced.
Shared vocabulary is linked, not restated: roles in
[`workers.md`](../hex-core/references/workers.md), model classes in
[`models.md`](../hex-core/references/models.md), and the outer contracts in
[`protocol.md`](../hex-core/references/protocol.md).

## Phase 1: Discover (single worker)

Launch **1** `architecture-explorer` covering the feature area(s) the
decision touches: module map, dependency graph, active patterns, reusable
code. In parallel, read directly the project's architectural conventions and
any prior ADRs in the convention-resolved artifact home (project
conventions, else `.agents/adrs/`,
[`memory.md`](../hex-core/references/memory.md#location-and-resolution)) for
overlap or conflict with this decision.

**Gate** — the architecture is mapped; prior decisions in the domain are
checked for overlap or conflict.

## Phase 2: Research (1 axis, gate-selected)

[`classify.md`](classify.md) proposes ranked candidate axes; a researcher
assigned the product/competitive-landscape axis runs focus
`competitive-research`. At the
meta-plan gate the user selects **1** (default: the top-ranked candidate on
plain approval — this is the signature interaction at this skill, see
[`SKILL.md`](SKILL.md) step 4). Launch **1** `researcher` on the selected
axis, paired with the architecture-explorer's output so external findings
stay grounded in local code. Findings longer than a paragraph **must**
persist as a research artifact in the convention-resolved location.

Override: `--research=3` launches all three top candidate axes in a single
concurrent batch — everything else in this tier (single `architect` worker,
ADR-only artifact, bounded review) stays as below. Researcher model class is
`fast-balanced` ([`models.md`](../hex-core/references/models.md)).

**Gate** — the axis choice is recorded with its source (classifier default
or user pick); the finding is persisted, or an explicit "no new signal" note
is logged.

## Phase 3: Classify (sequential)

Determine blast radius and reversibility; record it in the record header:

| Scope | Reversibility | Artifacts |
|---|---|---|
| Small decision | Two-way door | inline note only — should have been `low`; re-run if so |
| Medium decision | One-way door (medium) | ADR |
| Large decision | One-way door (high) | ADR + system-design + persisted research |

If this resolves to Large, **stop and re-run** as `/hex-architect high "…"`
— no silent upgrade mid-pipeline.

**Gate** — blast radius and reversibility documented in the record header.

## Phase 4: Reason & Design (architect worker, ADR mandatory)

Launch **1** `architect` worker; its model class is `deep-reasoning`
([`models.md`](../hex-core/references/models.md)) — this tier's
`--research` override does not touch it. Feed it: the decision, the
project's stated architectural conventions and NFR baselines, the
architecture-explorer findings, and the research axis finding.

Design must include:

- **Component contracts** — the public API (types, signatures) with expected
  behavior per component.
- **C4 sketch** — Context, Container, and Component levels for the area
  touched.
- **NFR coverage** — a line on each of scalability, availability, latency,
  security, cost, and operability this decision affects.
- **Trade-off matrix** — at least 2 options, weighted criteria, risks,
  reversibility, and a recommendation with rationale.
- **Industry / prior-art context** — the research axis finding, cited.

Write the ADR to the convention-resolved location
([`SKILL.md`](SKILL.md) › The design artifact). **Gate** — the contracts are
testable: a tester could write failing tests from them without reading any
code.

## Phase 5: Review (adversarial design panel, bounded loop)

Run the [Review-Fix Loop](../hex-core/references/protocol.md#the-review-fix-loop)
on the ADR — **plan-artifact scope: one panel round**; fix application,
conditional re-validation, and escalation follow the canonical loop's
artifact-scope rule, never restated here.

**Round 1** — launch concurrently:

- `reviewer` (focus `spec`) — are the contracts testable? Internally
  consistent with the stated decision?
- `reviewer` (focus `quality`, prompted adversarially) — steelman the
  rejected option(s): is the recommendation actually earned, or does the
  trade-off table favor the chosen option unfairly? Is the NFR coverage
  complete?
- `reviewer` (focus `security`) — **only** when [`classify.md`](classify.md)
  fired the compliance/security-touch signal, or `hex.md › Preferences`
  names this area as always-security-sensitive.

An actionable finding sends the `architect` worker back to revise the ADR;
the loop above governs re-runs, the cap, and escalation.

**Cross-model design review** (when `adversary=on` — auto-on for one-way-door
signals, or explicit `--adversary`): after the panel converges, run the
configured adversary skill once in `plan-artifact` scope on the ADR. One-shot,
4-way triage, actionable fixes re-validated by a single `reviewer` (focus
`spec`) pass; graceful skip when unavailable
([adversary contract](../hex-core/references/protocol.md#adversary-contract)).

**Gate** — the ADR is ready for handoff; deferred findings are documented.
Then run the [upkeep step](../hex-core/references/protocol.md#upkeep-step)
and emit the handoff from [`SKILL.md`](SKILL.md).
