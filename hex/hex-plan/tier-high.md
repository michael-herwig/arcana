# Tier: high

The **default** planning tier — medium-scope, one-way-door-medium work: a new
command, a new index or storage layout, a change spanning 1–2 areas. This is
the baseline any caller gets without an explicit tier.

`Read` this file from [`SKILL.md`](SKILL.md) after the config is announced.
Shared vocabulary is linked, not restated: roles in
[`workers.md`](../hex-core/references/workers.md), model classes in
[`models.md`](../hex-core/references/models.md), and the outer contracts in
[`protocol.md`](../hex-core/references/protocol.md).

## Phase 1: Discover (parallel)

Launch in a **single batch** so they run concurrently
([`protocol.md`](../hex-core/references/protocol.md#worker-coordination)):

- **1** `architecture-explorer` — map the current architecture, trace
  dependencies, find reusable code and active patterns.
- **2–4** `explorer` workers — one per involved area. Identify the areas from
  the project's own rules and structure (project context, cached in
  `hex.md › Pointers`), not a hardcoded table.

In parallel, read directly: the project rules for the areas touched, and any
prior plans/ADRs/research in the convention-resolved artifact home (project
conventions, else `.agents/`,
[`memory.md`](../hex-core/references/memory.md#location-and-resolution)) for
overlap.

This step also reads any `Federation:` bullets under `hex.md › Pointers`,
alongside every other pointer (C-314). When they are present, an `explorer`
scoped to a satellite's area reads **that repo's** rules by explicit
`Read` — ambient context covers the lead only, and `--add-dir` does not
load a satellite's `CLAUDE.md` (C-306, C-318). Absent `Federation:`
bullets, this step is unchanged.

GitHub: when the target resolved to a PR/issue, use its fetched context in
place of a broad scan; a PR's file list is the explicit scope for the
`architecture-explorer`. Fall back to the client's GitHub MCP list tools or
`gh` only when the target is free text.

**Gate** — worker reports are in; the architecture is mapped, reusable
components are identified, prior artifacts are checked for overlap.

## Phase 2: Research (parallel, 1 axis)

Launch **1** `researcher` on the single most relevant axis (technology *or*
patterns *or* domain), paired with at least one explorer's output so
external findings stay grounded in local code. The project's product
knowledge (research keywords, comparable tools — located via
`hex.md › Pointers`) seeds the axis choice and search terms when present.
Findings longer than a paragraph **must** persist as a research artifact in
the convention-resolved location for reuse.

Override: `--research=3` launches all three axes in a single concurrent batch.
The researcher's model class is `standard`
([`models.md`](../hex-core/references/models.md)).

**Gate** — research findings persisted (or an explicit "no new signals"
note); adoption trends and recent work checked.

## Phase 3: Classify (sequential)

Determine reversibility and scope; record it in the plan header:

| Scope | Reversibility | Artifacts |
|---|---|---|
| Small (1–3 days) | Two-way door | plan |
| Medium (1–2 weeks) | One-way door (medium) | plan + ADR (when a boundary decision is made) |
| Large (2+ weeks) | One-way door (high) | plan + ADR + persisted research |

Artifact formats follow the project's documented conventions; the templates
shipped with `/hex-init` are the fallback. If this resolves to Large, **stop
and re-run** as `/hex-plan xhigh "…"` — no silent upgrade mid-pipeline.

**Gate** — scope and reversibility documented in the plan header.

## Phase 4: Design (delegated for one-way-door, inline otherwise)

For **one-way-door medium** or cross-area work, launch an `architect`
(`--architect=on`) to produce an ADR or system design; its model class is
`deep` ([`models.md`](../hex-core/references/models.md)). For two-way-door
scope, design inline in the plan.

Design must include:

- **Component contracts** — public API (types, signatures) with expected
  behavior per component.
- **User-experience scenarios** — action → expected outcome → error cases for
  each user-facing behavior.
- **Error taxonomy** — documented failure modes with remediation guidance.
- **Edge cases** — boundary and corner cases enumerated.
- **Trade-off analysis** — at least 2 options, weighted criteria, risks,
  reversibility, and a recommendation with rationale.

When project context names a constitution (cached in `hex.md › Pointers`),
check the design against it and record every deviation in the plan's
Constitution Deviations table
([constitution gate](../hex-core/references/protocol.md#constitution-gate)).

Write design artifacts to the convention-resolved location. **Gate** — the
contracts are testable: a tester could write failing tests from them without
reading any code.

## Phase 5: Decompose (sequential)

Cut the design into **pipelines** and **steps** — the cutting rules are
[`decompose.md`](../hex-core/references/decompose.md#parallel-by-default-decomposition)'s,
the plan's shape [`SKILL.md`](SKILL.md#the-plan-artifact)'s; neither is
restated here:

- Write the contract wave: the stubs and contract tests every pipeline
  starts from.
- Fill the Parallelization table, the steps of each pipeline, the
  wave-grouped mermaid `graph TD`, the critical path and the "Shippable
  after wave: N — <what ships>" line
  ([`worktree.md`](../hex-core/references/worktree.md#pipeline-worktree-mechanics)).
- Marks only where the author knows better than the defaults — rare.
- **Federation:** when `hex.md › Pointers` carries `Federation:` bullets,
  offer **per-repo pipelines** — a pipeline whose scope lies in a satellite
  gets that satellite's key in the plan's `Repo` column — and add the
  mandatory integration pipeline that depends on every satellite pipeline it
  joins (C-311). Disjointness compares `(Repo, path)` pairs, not bare paths
  (C-316). `/hex-plan` never runs the C-303 pre-flight and never writes into
  a satellite — it only proposes the column (C-314). Absent `Federation:`
  bullets, no offer, no column, plan unchanged.

**Gate** — the plan holds a contract wave and pipelines whose steps
`/hex-execute` can run without further decomposition, and the
Parallelization section shows the widest wave structure the contracts
permit.

## Phase 6: Review (one reviewer; panel for a one-way door)

Run the [Review-Fix Loop](../hex-core/references/loop.md#the-review-fix-loop)
on the draft plan — **plan-artifact scope: one round**; fix application,
conditional re-validation, and escalation follow the canonical loop's
artifact-scope rule, never restated here.

**No ADR (two-way-door scope)** — launch **1** `reviewer` (focus `spec`,
phase `post-stub`), `standard` class, alone.

**One-way-door / ADR** — launch the panel concurrently:

- `reviewer` (focus `spec`, phase `post-stub`) — are the contracts testable?
  Do they match the user-experience section? Mechanically verifies every
  C-/S- ID maps to at least one pipeline Scope cell and at least one test
  step; an uncovered ID is an actionable finding
  ([traceability IDs](../hex-core/references/protocol.md#traceability-ids)).
- `architect` — are the trade-offs honest, the alternatives considered, any
  boundary violations introduced?
- `researcher` — does the plan miss a trending pattern, a known pitfall, or a
  state-of-the-art approach?

Either way the reviewer flags an unjustified constitution violation as an
actionable finding
([constitution gate](../hex-core/references/protocol.md#constitution-gate)).

**Cross-model plan review** (when `adversary=on` — auto-on for one-way-door
signals, or explicit `--adversary`): launched **in the Round 1 panel batch,
last** — never after the panel — and run once in `plan-artifact` scope
(`adr_0016` C-987). One-shot, 4-way triage; its actionable findings join
the same fix application as the panel's and are re-validated by the same
single `reviewer` (focus `spec`) pass; graceful skip when unavailable
([adversary contract](../hex-core/references/adversary.md#adversary-contract)).

**Gate** — the plan is ready for `/hex-execute`; deferred findings are
documented. Then run the
[upkeep step](../hex-core/references/protocol.md#upkeep-step) and emit the
handoff from [`SKILL.md`](SKILL.md).
