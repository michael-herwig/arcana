# hex Model Matrix

The single source of model guidance for the whole hex bundle. No other
file recommends models — [`workers.md`](workers.md) and the tier files
link here.

## Capability classes

Cells hold **capability classes, never literal model names** — the actual
model behind a class differs per client harness, so the shipped file stays
portable. Two classes:

- **`fast-balanced`** — the capable default workhorse: fast, strong on
  single-pass review and mechanical work, the right choice unless deeper
  reasoning clearly earns its cost.
- **`deep-reasoning`** — the deliberate-reasoning class: for one-way-door
  design, novel reasoning, and security-critical judgment. **Not a
  superlative:** it is the strongest *worker-appropriate* class, distinct
  from any orchestrator-class model that runs the session.

## The matrix

Rows are worker purposes at focus-mode granularity; columns are the tiers
from [`protocol.md`](protocol.md#tier-grammar).

| Role / focus | low | medium | high |
|---|---|---|---|
| explorer | fast-balanced | fast-balanced | fast-balanced |
| architecture-explorer | fast-balanced | fast-balanced | fast-balanced |
| researcher | fast-balanced | fast-balanced | fast-balanced |
| builder:stub | fast-balanced | fast-balanced | fast-balanced |
| builder:implement | fast-balanced | fast-balanced | deep-reasoning |
| tester | fast-balanced | fast-balanced | deep-reasoning |
| reviewer:quality | fast-balanced | fast-balanced | deep-reasoning |
| reviewer:security | fast-balanced | deep-reasoning | deep-reasoning |
| reviewer:performance | fast-balanced | fast-balanced | deep-reasoning |
| reviewer:spec | fast-balanced | fast-balanced | deep-reasoning |
| reviewer:user-feedback | fast-balanced | fast-balanced | deep-reasoning |
| doc-reviewer | fast-balanced | fast-balanced | fast-balanced |
| architect | deep-reasoning | deep-reasoning | deep-reasoning |
| coordinator | — | deep-reasoning | deep-reasoning |

`—` = never spawned at that tier.

## Rules

1. **Cells are recommendations, not floors or ceilings — but never
   silently.** The orchestrator escalates on judgment and announces the
   reason at the meta-plan gate. Example: tier=low but the diff touches
   security-critical auth code — run `reviewer:security` at
   `deep-reasoning`, announced as
   "reviewer:security → deep-reasoning (security-critical diff)".
   A spawn that runs above its cell **without an announced reason is a
   spec violation** — silent escalation is the failure mode this rule
   exists to prevent. The announce block prints each spawn's **resolved
   literal model**
   ([`protocol.md`](protocol.md#the-meta-plan-approval-gate)).

2. **Resolution order**:
   1. **Instantiated matrix in `hex.md › Preferences`** — literal model
      names written by `/hex-init` for this harness, including any per-row
      or per-cell overrides. Wins over the shipped default when present.
   2. **Shipped class default** — this table, mapped through the harness's
      class→model mapping; applies when nothing is instantiated.
   3. **Judgment escalation** — the orchestrator's per-run bump on top of
      either, announced at the gate.

   This order also outranks any **harness-global model-routing policy**
   (a user- or client-level routing table): for hex spawns, the matrix
   decides; global routing applies outside hex runs. A global rule like
   "multi-file tasks → strongest model" must not silently override a
   cell — route around the matrix only via the instantiated table or an
   announced escalation.

   `models.overrides` ([`config.md`](config.md#key-vocabulary)) is the
   config-block form of step 1's per-cell override — a map `role[:focus]`
   → capability class merged into the instantiated matrix, not a separate
   resolution path.

3. **Instantiation.** `/hex-init` maps each class to the harness's literal
   models and stores the instantiated table in the Preferences section of
   `.agents/memory/hex.md` (see [`memory.md`](memory.md)). On a
   Claude harness, for example, fast-balanced → Sonnet and deep-reasoning →
   Opus. Skipping instantiation is fine — the shipped class defaults apply.
   Per-row or per-cell overrides live in `hex.md › Preferences` too (e.g.
   `reviewer:security` pinned to the deep-reasoning model at every tier).

4. **Cells never resolve to an orchestrator-class model.** Some harnesses
   expose a model tier above their strongest *worker* model — an
   orchestrator seat that runs the session (e.g. Claude's Mythos-class:
   Fable / Mythos, above Opus). Those models are never spawn targets; the
   matrix governs spawned workers only. `deep-reasoning` maps to the
   strongest *worker-appropriate* model (e.g. Opus), never the
   orchestrator tier. The session/orchestrator model is the user's or
   harness's choice, outside this matrix.

5. **`coordinator` is tier-gated.** It runs only at medium/high — recursion
   is a fan-out optimization, absent at low's single-WP shape — and
   resolves to the `deep-reasoning` **worker** class, never an
   orchestrator-class model (the exclusion rule, Rule 4 above). See the
   [`coordinator`](workers/coordinator.md) persona for the full role
   contract.
