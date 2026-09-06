# ADR: Parallel adversary, review checklist, reviewer configuration

## Metadata

**Status:** Proposed
**Date:** 2026-09-06
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A — raised by the owner on reading `adr_0015`
(PR #4): the adversary still runs in sequence, a single seat now reviews
several aspects with no checklist, and reviewer configuration is only
half-plumbed
**Related PRD:** N/A
**Architectural Conventions:**
- [x] Decision follows this project's stated architectural conventions /
      golden path (`hex/DESIGN.md`: single-source contracts, thin
      dispatchers, capability classes, load only what runs, frozen phase
      headings)
- [ ] OR the deviation is justified in the Rationale section below
**Domain Tags:** infrastructure
**Supersedes:** the serial adversary placement in every orchestrator's
tier files and the "fixes it, then re-runs one affected perspective"
triage line of the adversary contract; the "checklist breadth" prose that
named no checklist
**Superseded By:** N/A

## Context

`adr_0015` keyed review depth on join level: `L0` evidence table, `L1`
one fast delta-only leaf reviewer, `L2` one deep-reasoning aggregate seat
at `N ≥ 2`, `L3` the opt-in trunk pass. Three gaps remained.

1. **The cross-model adversary still ran in sequence.** `/hex-execute`'s
   tier files said "after the `L2` seat returns"; `/hex-review` ran it as
   Phase 5 after Stages 1–2 and RCA; `/hex-plan` and `/hex-architect`
   "after the panel converges". One more serial round-trip on the wall
   clock the ADR exists to cut — and the adversary is an external skill
   whose bound hex cannot shorten, so it was the longest single tail.
2. **A single seat reviewed several aspects at once with no checklist.**
   `L1` folds `spec` and `quality` into one brief; `L2` carries up to seven
   aspects under the `--review` axis; the old per-focus seats had a
   one-line focus description each and nothing more. A seat asked for
   "quality" with no list answers whatever it happens to notice.
3. **Configurability was half-plumbed.** `review.<level>.{seats, class,
   rounds, budget-minutes, delta-only}` existed (config v3) and
   `perspectives.always` wired project personas, but `/hex-init` Step 4½
   still assembled "vocabulary v2" and never proposed `review`; Step 4
   told the user to pin `reviewer:security` through `models.overrides`,
   which C-985 had superseded; there was no per-level *which aspects*
   knob; and the Upkeep → Memory → `/hex-init` route named no
   review-config or checklist candidate.

## Decision Drivers

- Wall clock: the adversary's cost must hide under the native seat's.
- A single seat must be told what to look for, item by item, and must
  answer every item — verified or not applicable.
- Every review knob lives in one vocabulary, is seeded at init with
  consent, and can be proposed by a run through the existing route.
- Nothing restated: one home per contract (`hex/DESIGN.md` C-923), the
  reviewer persona still opens `severity.md` only, phase headings frozen
  (C-220).

## Considered Options

### Option 1: Keep the adversary serial, shorten its bound

Cap the adversary at a few minutes so the tail is small. Rejected: hex
cannot terminate an external skill, only stop waiting, and a short bound
turns every slow adversary into a skipped review — the failure `adr_0013`
round 13 documented.

### Option 2: Launch the adversary in the join's batch, one merged fix pass (chosen)

The adversary is a member of the batch that launches the native seat of
the join it gates, last in that batch; both clocks run independently;
the join waits for both; actionable findings from both sources fold into
the one builder fix pass the join already has. Wall clock becomes
`max(native, adversary)`.

### Option 3: Drop the adversary from `/hex-execute`, keep it in `/hex-review`

Rejected: the owner's doctrine is that the cross-model pass is a default
part of the flow at the top tier; removing it from execution moves the
cost to a trunk review `adr_0015` made opt-in.

### Checklist placement

A separate project file `.agents/review-checklist.md` was considered and
rejected as a third surface for what `perspectives.always` and the
project's own rules (universal rule 1) already reach. The shipped
checklist is one topic file the orchestrator composes from; a project
extends it through its own rules and personas.

## Decision Outcome

### Concurrent launch (C-987)

When `adversary=on`, the adversary launches **in the same batch as the
native seat of the join it gates**: the `L2` aggregate seat, or the sole
leaf's `L1` at `N = 1`, in `/hex-execute`; the Stage 2 batch in
`/hex-review`; the Round 1 panel batch in `/hex-plan` and
`/hex-architect`. Batch order is native seats first, adversary last, so a
mode-(c) blocking call blocks only after every native seat is running.
Where the harness cannot batch the call, the launch degrades to
sequential as the suffix `; launched sequentially` on the existing
`Degraded: blocking adversary call …` line. The adversary occupies no
`max-workers` slot. The two clocks are orthogonal:
`review.<level>.budget-minutes` bounds the native seat only, the adversary
contract's resolved bound bounds the adversary only. The join waits for
both. Defined once in `adversary.md`; every tier file links it.

### Merged triage (C-988)

Adversary actionable findings join the join's single builder fix pass,
one re-verify by the join's resolved verification. A finding naming the
same defect as a native finding merges into it with attribution, never
counted twice. If the merged pass fails verification: revert it, re-run
it native-only, promote every adversary finding to deferred — the
adversary is never re-invoked. This replaces `tier-high`'s blanket
revert, which under a merged pass would have discarded native fixes. In
`/hex-review` findings are reported, never fixed.

### The shipped checklist (C-989)

New topic file `hex-core/references/checklist.md`: eight sections —
`spec`, `quality`, `security`, `performance`, `docs`, `architecture`,
`pitfalls`, `user-feedback` — each item "defect class — verify by a grep
or read on the diff". Composition by join level: `L0` none (a mechanical
gate takes no judgement list); the inline orchestrator at tier `low`
answers `spec` + `quality` itself; `L1` `spec` + `quality`; `L2` per the
`--review` axis (`minimal` spec + quality; `full` adds security,
performance, docs on their triggers; `adversarial` adds architecture and
pitfalls), risk forcing security and performance on; `L3` each panel
seat carries its own focus section. The orchestrator inlines the composed
sections into the brief's new `Checklist:` slot; a `reviewer` spawn never
opens the file (load map unchanged: `severity.md` only). A seat answers
every item — verified, or not applicable with the reason — and its
self-check refuses a return that skipped one. Every composed brief also
names the project's own quality rules via `hex.md › Pointers`.

### Configurability (C-990)

New key `review.<level>.checklist: [<focus>…]` (v3 leaf) replaces the
derived section set; an explicit `--review` flag still wins under the
ordinary later-wins precedence; it is the only breadth knob `L1` has.
`/hex-init` Step 4½ seeds vocabulary v3, adding the six `review.<level>.*`
keys, consent-gated, never clobbering an untouched block; Step 4 states
that `review.<level>.class` supersedes a `models.overrides`
`reviewer[:focus]` entry for review seats. The Upkeep step names three
Memory candidate classes proposed at the next `/hex-init`: an always-on
perspective, a `review.<level>.*` value the run's residue or expiry
argued for, and a finding class that recurred and belongs in the
project's rules as a checklist item. New audit item "Review settings
tuned?".

### Consequences

- The adversary's wall clock overlaps the aggregate seat's; the terminal
  join costs `max(native, adversary)` instead of their sum.
- Every review seat, and the inline orchestrator, answers a concrete
  list; a skipped item is a self-check failure, not an omission.
- Seats, class, rounds, budget, input scope and aspects are per-level
  config, seeded at init, proposed by runs.
- A duplicate finding is one finding with two attributions; the handoff's
  counts stop double-counting cross-model hits.

## Validation

- `grim build` for `hex-core`, `hex-execute`, `hex-review`, `hex-plan`,
  `hex-architect`, `hex-init`; `task publish -- --dry-run`.
- Anchor sweep: every `](…#anchor)` in the bundle resolves; no literal
  model name in any shipped file; no `## Phase` heading renamed.
- Grep gates: zero live hits for ``after the `L2` seat returns``, "after
  the Review-Fix Loop converges", "after the panel converges", "re-runs
  one affected perspective" outside `DESIGN.md`, `CHANGELOG.md` and this
  ADR.
- Dogfood: one `/hex-execute high --adversary` run recording that the
  adversary's wall clock overlaps the aggregate seat's.

## Open Questions

- Whether a seat that marks more than half its items not applicable
  should be flagged in the handoff — deferred until a run shows it.
- Whether the `docs` section should fire at `L1` when the diff touches a
  doc path — the `L1` knob (`review.l1.checklist`) covers it per project.

## Links

- `adr_0015` — review by join level (the levels this ADR composes for)
- `adr_0013` — adversary observation modes (the bound this ADR keeps)
- `hex/DESIGN.md` round 21

## Changelog

- 2026-09-06 — Proposed.
