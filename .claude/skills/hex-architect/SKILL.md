---
name: hex-architect
description: Tiered architecture-decision orchestrator — evaluates trade-offs and produces ADRs or system designs through discover, research, design, and adversarial-review phases. Use for architecture decisions, ADRs, system design, trade-off analysis between approaches, one-way-door decisions, C4-level design, or NFR evaluation (scalability, availability, latency, security, cost, operability). Tier (low|medium|high, auto by default) scales research-axis count and selection, whether the design is delegated to an architect worker, and review breadth.
license: Apache-2.0
metadata:
  summary: Swarm-backed architecture design - ADRs, C4, trade-off matrices
  keywords: architecture,adr,design,swarm,trade-off,one-way-door,c4
  repository: https://github.com/michael-herwig/arcana
---

# hex-architect — Architecture Orchestrator

Thin dispatcher. It parses arguments, classifies the decision's tier, resolves
overlays, runs the single meta-plan approval gate, announces the resolved
config, and hands off to the matching tier file. The phase plans live in
`tier-low.md`, `tier-medium.md`, and `tier-high.md`; the shared vocabulary
(tiers, the Review-Fix Loop, worker roles, model classes, the memory file)
lives in the `hex-core` reference library and is **linked here, never
copied**.

Shared contracts:
[`protocol.md`](../hex-core/references/protocol.md) ·
[`workers.md`](../hex-core/references/workers.md) ·
[`models.md`](../hex-core/references/models.md) ·
[`memory.md`](../hex-core/references/memory.md).
If `hex-core` is not installed: `grim add ghcr.io/michael-herwig/hex-core:latest`.

## Argument syntax

```
/hex-architect [tier] <decision> [flags]
```

- **tier** (optional): `low | medium | high | auto`. Default `auto` — the
  classifier picks one of the three. `xhigh` and `max` are **reserved**
  (see [`protocol.md`](../hex-core/references/protocol.md#tier-grammar)): the
  classifier never emits them, and an explicit reserved tier is announced as
  "`<tier>` reserved, running high" and run as `high`.
- **decision** — free text: a question to decide, a component or feature
  that needs a design, or a one-way-door choice to evaluate. Unlike
  `/hex-plan`, hex-architect does not resolve GitHub issues or PRs itself —
  paste the relevant discussion into the prompt when the decision originates
  there.
- **flags** (before the decision, by convention):
  - `--research=skip|1|3` — override the research-axis count (see
    [`overlays.md`](overlays.md)).
  - `--axes=<comma-separated>` — name the research axes explicitly, skipping
    the interactive picker at the gate (still shown there for confirmation).
  - `--adversary` / `--no-adversary` — force the cross-model design-artifact
    pass on or off.
  - `--artifact=inline|adr|system-design` — override the artifact form.
  - `--dry-run` — make the meta-plan gate block for explicit approval and
    stop there (preview only, no workers launched).

## Dispatch

The outer loop every hex orchestrator shares
([`protocol.md`](../hex-core/references/protocol.md#shared-shape)):

### 1. Parse arguments and resolve memory

Parse the tier, decision, and flags. Locate
`.agents/memory/hex.md` by searching upward from the working
directory; a missing file is normal
([`memory.md`](../hex-core/references/memory.md#location-and-resolution)) —
fall back to shipped defaults and note that `/hex-init` can create one. When
present, read the whole file: `hex.md › Pointers` for where ADR conventions
and architectural rules are documented, `hex.md › Preferences` for the
instantiated model matrix, the adversary skill name, limits, and research
axes of interest, the project's product knowledge (located via
`hex.md › Pointers`) for product context (users, constraints, research
keywords, comparable tools — it seeds axis candidates and gate
clarifications, [`classify.md`](classify.md)) when present, and
`hex.md › Memory` for any prior ADR covering the same ground.

If the resolved `hex.md` carries a `Federation lead:` bullet, **halt** per
[`memory.md` § Location and resolution](../hex-core/references/memory.md#location-and-resolution)
— this repo is a federation satellite and its memory is not the plan's.

### 2. Classify (only when tier is `auto`)

Read [`classify.md`](classify.md). It scores the decision on four
decision-weight signals — reversibility, blast radius, novelty, and
compliance/security touch — and emits a candidate tier (**only** `low`,
`medium`, or `high`), a confidence flag, and a ranked list of candidate
research axes. Low confidence forces the gate in step 4. Never ask a
mid-flow question during classification — ambiguity is resolved at the
single gate.

### 3. Resolve overlays

Final config = the tier's baseline from [`overlays.md`](overlays.md) +
classifier-inferred overlays + `hex.md › Preferences` hints + user
flags. Later wins; **user flags always override** (see
[`protocol.md`](../hex-core/references/protocol.md#spawn-selection-precedence)).

### 4. Meta-plan gate (the single approval point)

Exactly one gate, before any worker launches
([`protocol.md`](../hex-core/references/protocol.md#the-meta-plan-approval-gate)).
Its weight scales:

- **Confident `low` / `medium`** (an explicit user tier always counts as
  confident — the classifier never ran) — announce the resolved config (step 5) and
  proceed; the user can still abort.
- **`high` tier, low-confidence classification, or `--dry-run`** — block for
  explicit approval.

For hex-architect, **research-axis selection is the primary lever at this
gate** — more so than in any other hex skill. The announce block lists the
classifier's ranked candidate axes and the count the tier requires (`medium`
1, `high` 3); a plain approval defaults to the top-ranked candidates, but the
gate is where the user swaps one out, names an axis the classifier missed, or
drops research entirely. On a client with a **native plan-approval
mechanism**, use it. Otherwise present the announce block as **one
structured question** (approve / adjust / cancel). On adjust, re-resolve and
re-present once. Never split this into sequential questions.

### 5. Announce the resolved config

Print the resolved config with per-axis source attribution before loading the
tier file (format:
[`protocol.md`](../hex-core/references/protocol.md#the-meta-plan-approval-gate)):

```
hex-architect
  Tier:      medium                          (auto — classifier: one-way-door medium, internal contract)
  Overlays:  research=1                       (tier baseline)
             axes=[technology/tooling]        (user — picked from 3 classifier candidates)
             adversary=off                    (tier baseline)
             artifact=adr                     (tier baseline)
  Spawn set:
    architecture-explorer                     (tier baseline)
    researcher ×1                             (overlay research=1, axis: technology/tooling)
    architect                                 (tier baseline — design delegate)
    reviewer: spec, quality                   (tier baseline — adversarial design panel)
  Models:    fast-balanced default; architect → deep-reasoning   (models.md)
  Adversary: off                              (tier baseline)
  Degraded:  no — subagent spawning available
```

Every spawn line carries its source (`tier baseline` / `classifier` /
`hex.md preference` / `user flag`) per
[spawn-selection precedence](../hex-core/references/protocol.md#spawn-selection-precedence).
Model names above are class placeholders — shipped files never hardcode
literals; the running orchestrator resolves and prints each spawn's
literal model per the
[Models line contract](../hex-core/references/protocol.md#the-meta-plan-approval-gate). The `architect` row
recommends `deep-reasoning` at every tier — a downward override is honored
but announced loudly. On a client that cannot spawn subagents, announce
`Degraded: inline workers` and run each worker prompt inline and sequentially
([`protocol.md`](../hex-core/references/protocol.md#worker-coordination)).

The announce block prints one config-disclosure line per change a
`hex.md › Preferences` block makes; the full trigger set is defined once in
[`protocol.md` § the meta-plan approval gate](../hex-core/references/protocol.md#the-meta-plan-approval-gate).
For this skill, for example:

```
  [project-redefined: Review.reviewer:security 0→1 (hex.md tiers)]
  [researcher dropped — phase ceiling 2 reached]
  [Review batched 2+1 — concurrency cap 2 (hex.md)]
  Error: never [reviewer:security] refused (hex.md preference)
  Fix:   see config.md#merge-rules for the attestation requirement
```

### 6. Dispatch to the tier file

Read `workflows.hex-architect.<tier>` from the resolved config first. When set
and the named file passes the seven validation checks
([`config.md` § Workflows](../hex-core/references/config.md#workflows)), `Read`
that forked file in place of the shipped one; on validation failure or when
unset, `Read` the matching `tier-{low,medium,high}.md` — config.md owns the
check list and the on-failure fallback. Announce which ran: `Workflow: shipped
tier-<tier>.md`, or for a fork, `Workflow: <path> (forked from <shipped tier
file> @ <stamped version>)`. Execute the loaded file's phase plan; no phase
content is duplicated in this file.

## Worker assignment (shared across tiers)

Roles are indexed in [`workers.md`](../hex-core/references/workers.md);
the orchestrator loads a full persona (spawn-prompt template, output
contract) only for roles in the resolved spawn set
([spawn-selection precedence](../hex-core/references/protocol.md#spawn-selection-precedence)).
The model class for each role × tier is in
[`models.md`](../hex-core/references/models.md). This table maps roles to
design phases; the tier files set the actual counts.

| Phase | Role | Count | Purpose |
|---|---|---|---|
| Discover | `architecture-explorer` | 0–1 | Map current architecture, dependency graph, reusable code, precedent (`medium`/`high`) |
| Discover | `explorer` | 0–1 | Lightweight single-area discovery (`low` only) |
| Research | `researcher` | 0–3 | Axis research — technology, pattern precedent, performance, security, operability, or data/compatibility, per axis picked at the gate |
| Design | `architect` | 0–1 | ADR or system design (delegated `medium`/`high`; inline at `low` — no worker) |
| Review | `reviewer` | 1–3 | Adversarial design panel: contract consistency (`spec`), trade-off honesty (`quality`, adversarial framing), security (conditional) |
| Review | `researcher` | 0–1 | SOTA / known-pitfall gap check against the drafted design |
| Adversary | configured adversary skill (`plan-artifact`) | 0–1 | Cross-model review of the ADR / system-design file |

A project's `tiers.hex-architect.<tier>.counts` can override any Count cell
above against the baseline this table sets
([`config.md` § Merge rules](../hex-core/references/config.md#merge-rules)).

Concurrency cap and degraded mode:
[`protocol.md`](../hex-core/references/protocol.md#worker-coordination). The
adversary skill name comes from `hex.md › Preferences`
([adversary contract](../hex-core/references/protocol.md#adversary-contract));
`codex-adversary` is only an example value.

## Tool preferences (optional, feature-detected)

None of these are required — hex-architect works from read/write/grep alone.
When the client exposes them, prefer:

- **Structured-reasoning tool** (e.g. a sequential-thinking MCP) for building
  the trade-off matrix — plain step-by-step prose is the fallback.
- **Library/API-docs tool** (e.g. a Context7-style MCP) when a decision
  hinges on a dependency's current shape — training-data knowledge of a
  library's API decays; fall back to fetching its official docs site.
- **Issue/PR lookup tool** (a GitHub MCP or the `gh` CLI) when the decision
  references an issue or PR the user names — fall back to asking the user to
  paste the relevant text.

Detect availability once at the start of Discover; never assume a specific
client.

## Project rules and conventions

hex-architect never carries a hardcoded rule or subsystem table. Every phase
that needs the project's architectural conventions, golden-path tech
choices, or NFR baselines discovers them from **project context** (the
client's ambient instructions / project rules), cached in the Pointers
section of `.agents/memory/hex.md`
([`memory.md`](../hex-core/references/memory.md#the-three-sections)).
"Verify" anywhere below means **run the project's documented verification**
([`protocol.md`](../hex-core/references/protocol.md#verification)) — relevant
when a design phase spikes a prototype, or Review checks a claim against real
code.

## The design artifact

**Location.** Write the ADR (and system-design doc, when one is produced)
where the project's documented ADR conventions say (discovered from project
context, cached in `hex.md › Pointers`). When nothing is documented, use the
default `.agents/adrs/adr_NNNN_[topic].md`
([`memory.md`](../hex-core/references/memory.md#location-and-resolution)).
Record the artifact's location in `hex.md › Memory`. The ADR
template shipped with `/hex-init` (MADR-based) is the scaffold; the
project's own format wins when it has one.

**Status.** A standard ADR status field, not a plan Status block: the run
writes `Proposed` and leaves it there. Flipping to `Accepted` is the
decider's call — a human step taken after the handoff, typically once the
open `[NEEDS CLARIFICATION]` markers are resolved; an orchestrator never
accepts its own design. Later lifecycle states (`Deprecated`, `Superseded`)
belong to the project going forward, not this run.

**Required content** (`medium` and `high` — `low` stays inline, see
[`tier-low.md`](tier-low.md)):

- **Component contracts** — the public surface the decision touches (types,
  signatures, API/data contracts), precise enough that `/hex-plan` could
  decompose it without re-deriving the design.
- **NFR coverage** — scalability, availability, latency, security, cost,
  operability: a line on each the decision affects, silence on the ones it
  doesn't.
- **Trade-off matrix** — at least 2 options at `medium`, at least 3 at
  `high`; weighted criteria, risks, reversibility, and a recommendation with
  rationale.
- **Industry / prior-art context** — findings from the research axis/axes
  that ran, citing sources.
- **Open questions** — unresolved ambiguities as `[NEEDS CLARIFICATION: …]`
  markers, hard cap 3.

## Constraints

- **No implementation code** — hex-architect produces design records, not
  code; implementation is `/hex-execute`'s job downstream.
- **No task decomposition** — hex-architect does not break a design into
  executable Stub → Specify → Implement → Review tasks; that is `/hex-plan`'s
  job once it consumes the ADR. Five phases per tier, not six: Discover,
  Research, Classify, Design, Review — no Decompose phase.
- **Discover runs at every tier** — never assume context; ground the
  decision in real code before reasoning about it.
- **Never skip the trade-off analysis** — even at `low`, a two-option table
  is mandatory; a single unweighed opinion is not a design.
- **Verify assumptions about existing code** — grep/read before asserting a
  pattern exists or a constraint applies; never design from memory of other
  codebases.
- **Persist substantial research** (more than a paragraph) as a research
  artifact in the convention-resolved location.
- **Never commit and never push** — this skill designs only.
- **Upkeep** ([`protocol.md`](../hex-core/references/protocol.md#upkeep-step)):
  as the final phase, re-point any `hex.md › Pointers` entry this run
  revealed as drifted (a changed ADR location), and note in
  `hex.md › Memory` any research axis that mattered enough to propose
  as a `hex.md › Preferences` hint at the next `/hex-init` run.

## Handoff

The [handoff contract](../hex-core/references/protocol.md#handoff-contract)
applies: this block is the run's required final message; one optional
proceed question may follow it.

```markdown
## Design Complete: <decision title>

### Classification
- Blast radius: single area | cross-area | external contract
- Reversibility: two-way | one-way (medium) | one-way (high)
- Tier: low | medium | high
- Overlays: research=<skip|1|3> axes=[...], adversary=<on|off>, artifact=<inline|adr|system-design>

### Artifacts
- <ADR path> (Status: Proposed | Accepted)
- <system-design path> (one-way-door high, when produced)
- <research artifact path(s)>

### Trade-off summary
- Recommended: <option> — <one-line rationale>
- Rejected: <option(s)> — <one-line why>

### Deferred findings (need human judgment)
- Design panel: …
- Cross-model review: …

### Next step
    /hex-plan medium "<decision title>, per <ADR path>"
```

Consumers: `/hex-plan` (the design feeds a plan) or the human directly, when
the decision doesn't need a follow-on plan.

$ARGUMENTS
