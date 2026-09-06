# ADR: Five-tier grammar — inline low, xhigh, max

## Metadata

**Status:** Proposed
**Date:** 2026-09-06
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A — owner request during `adr_0016`'s planning:
"add a new xhigh and max review level where every existing is shifted
once higher, the new low is a faster inline variant and the max variant
spawns multiple adversaries, includes more research and also simulates
usage with different user patterns"
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below —
      this ADR **reopens the frozen tier vocabulary** (`hex/DESIGN.md`
      2026-07-19 rename, "`xhigh` and `max` are reserved") and **breaks the
      `hex.md › Preferences` tier segment** (config v4). Both are handled
      by a read-side shift, never a rewrite; see Migration.
**Domain Tags:** infrastructure
**Supersedes:** the three-tier grammar `low | medium | high` and its
reserved-tier clause everywhere it appeared
**Superseded By:** N/A

## Context

hex's tier vocabulary was `low | medium | high` plus `auto`, with `xhigh`
and `max` reserved words that announced "reserved, running high". The
owner's reading after `adr_0015` and `adr_0016`: the three tiers were one
step too coarse at both ends. At the bottom, `low` still spawned an
explorer, a builder and a reviewer for a one-line change that the
orchestrator could make itself in a minute. At the top, `high` had no
room above it for the run that should buy every adversary, wider
research and a simulated user — the run that justifies its cost by the
size of the door it walks through.

`protocol.md` § Tier grammar is one vocabulary shared by all four
orchestrators, and a plan's `Tier:` is `/hex-execute`'s ceiling and
`/hex-review`'s floor. A review-only tier set would desync the two.

## Decision Drivers

- One grammar for every orchestrator; a plan's tier means the same to
  the skill that wrote it and the skills that read it.
- A trivial change costs zero spawns.
- A `max` run is a deliberate purchase, never a classifier outcome.
- Existing plans and config blocks keep meaning what they meant, with no
  rewrite and no refusal.
- Phase headings stay byte-identical inside renamed files (C-220).

## Considered Options

### Option 1: Shift every skill's tiers one step up, insert inline `low` and `max` (chosen)

Rename per skill (`tier-high → tier-xhigh`, `tier-medium → tier-high`,
`tier-low → tier-medium`), write two new tier files per skill, shift the
literals, and read old plans and config blocks under the grammar they
were written in.

### Option 2: Add `xhigh` and `max` to review only

Rejected: the plan's `Tier:` is execute's ceiling and review's floor;
two vocabularies make `max(classified, ceiling)` undefined.

### Option 3: Keep three tiers, stack overlays for the new behaviour

`--inline`, `--adversaries=all`, `--simulate`. Rejected: the reserved
words were a stated promise of tiers, not overlays; and an overlay stack
that every `max` run must remember is what a tier exists to name.

## Decision Outcome

### Grammar (C-991)

`low < medium < high < xhigh < max` plus `auto`. The classifier emits
`low` … `xhigh`; **`max` is explicit only** — `--tier=max` or a plan's
`Tier: max`. Reserved-tier text deleted everywhere.

### The shift (C-992)

Old `low` → `medium`, old `medium` → `high`, old `high` → `xhigh`; per
skill, three `git mv` in a renames-only commit, then the literal shift.
Headings inside renamed files are preserved byte-for-byte. Classifier
signal tables shift one row; a new `low` row (one file, ≤30 lines, no
structural marker, no security-sensitive or hot path) sits below; `max`
is "never emitted". Overlay per-tier defaults gain a `low` and a `max`
row. `models.md` gains two columns: `low` all `—`, `max` = `xhigh` plus
the `simulator` row.

### The effective tier (C-993)

`S` ⇒ `medium` (the collapsed builder, byte-identical to what old `low`
ran), `M` ⇒ `high`, `L` ⇒ `T`; the `hub` and coordinator floors are
`min(T, high)`; the collapse fires at effective `medium`. **Effective
`low` is never derived** — a WP reaches inline `low` only through a plan
ceiling `Tier: low`, which is a single-WP plan. `coordinator` has no cell
at `low` or `medium`.

### Inline `low` (C-994)

Zero spawns; the orchestrator is the worker. `/hex-execute low`: read the
target and the area's rules, stub and commit, specify and commit,
implement, scoped check; write the `L0` evidence table and answer the
`spec` + `quality` checklist inline; spawn **one `L1` reviewer only when a
non-doc file changed** (author≠verifier backstop); adversary off unless
`--adversary`, then batched with that `L1` or alone; final gate; commit.
`/hex-review low`: the orchestrator reviews the diff itself against
`spec` + `quality`, severity omitted. `/hex-plan low`: a single-WP plan
written inline, self-checked against the `spec` section. `/hex-architect
low`: an inline decision note with a two-option table. Anything Discover
reveals to be larger stops and re-runs at `medium`.

### `max` (C-995, C-996)

`xhigh` plus three additions. **Every adversary**: the `adversary` key
widens to `string | list of strings`; at `max` every entry launches in
the terminal join's batch under `adr_0016` C-987, findings union-triaged
with duplicate merge; below `max` the first entry only; one entry at
`max` announces `max: 1 adversary configured`. **Wider research**:
`/hex-plan` and `/hex-architect` run five axes with one
`competitive-research` axis mandatory; `/hex-execute` and `/hex-review`
add one `researcher` (known-pitfall framing) to the `L2` / Stage 2 batch.
**Usage simulation** (C-996): new persona
`hex-core/references/workers/simulator.md` takes one user pattern —
`first-time`, `power-user`, `adversarial`, `automation`, plus any
project `.agents/workers/simulator-<pattern>.md` — writes its scenario
first, then exercises the built artifact in a scratch worktree (execute,
review) or walks the plan's or design's user-facing section (plan,
architect); returns actionable and deferred findings with repros, never
edits. `/hex-execute max` adds `## Phase 8: Usage simulation` after merge:
four parallel simulators, one merged fix pass, re-verified by the final
gate. `/hex-review max` reports a "Usage simulation" section. `/hex-plan`
and `/hex-architect max` turn simulator findings into proposed changes at
the review gate. Registered in `workers.md`, `models.md` and the load map
(`simulator` opens `verify.md` only).

### Migration on read (C-997)

`/hex-plan` writes `- Tier-grammar: 5` into the Status block. A plan
**without** that line has its `Tier:` shifted one step up on read
(low→medium, medium→high, high→xhigh), disclosed on the `Tier:` line's
own source: `Tier: medium (plan, pre-adr_0017) → high`. The same rule
reads `hex.md › Preferences`: a block whose vocabulary comment is `v3` or
lower has every `tiers.<skill>.<tier>` and `workflows.<skill>.<tier>`
segment shifted on read, announced once at the gate. **Config v4** is the
five-value tier segment plus the list-valued `adversary`; no new
top-level key, merge rule 8's enumeration unchanged. Never a rewrite,
never a refusal.

### Classifier (C-998)

`xhigh` takes old `high`'s signals; `max` is never auto-emitted. Overlay
`--review` per-tier defaults: `low` minimal (inline), `medium` minimal,
`high` full, `xhigh` adversarial, `max` adversarial. The gate blocks for
explicit approval at `xhigh` and `max`; `low`, `medium` and `high`
announce and proceed when confident.

### Consequences

- A one-file change runs with zero spawns, in minutes, on the feature
  branch; the `L1` backstop keeps author≠verifier for code.
- Every pre-existing tier keeps its behaviour under a new name; a user
  who typed `medium` yesterday and gets `high` today sees the shift on
  the `Tier:` line.
- `max` is a purchase: every adversary, five axes, four simulated users;
  its cost is the reason it is never classified into.
- Twelve tier files renamed, eight added, one persona added; the
  `.claude/skills/` copies in this repository refresh on the next
  `grim` sync.

## Validation

- `grim build` for all six skill directories; `task publish -- --dry-run`.
- Anchor sweep resolves every link, the new files included; no literal
  model name in any shipped file.
- Structural: `git diff` of the renamed tier files shows no `## Phase`
  heading change; only the new `low`/`max` files add headings.
- Grep gates: zero live hits for "reserved for future", "never emits
  `xhigh`", "no fourth value", "one of the three", "Three tiers",
  "running high", `tier-{low,medium,high}.md` outside `DESIGN.md`,
  `CHANGELOG.md` and this ADR.
- Literal-shift audit: severity `High`, `max-workers`, `limits.heavy`,
  "highest" unchanged; `min(T, …)` shifted only where it names a tier.
- Dogfood: one `/hex-execute low` on a one-file change (expect 0–1
  spawns) and one `/hex-execute max` with two adversaries configured.

## Open Questions

- Whether `first-time` and `automation` simulators should share one
  scratch worktree — separate until a resource measurement says
  otherwise.
- Whether the classifier's new `low` row should read `hex-review`'s
  metrics (one file, ≤30 lines) for `/hex-execute` free-text targets, or
  `/hex-plan`'s signal words — both ship; a measured misclassification
  reopens it.

## Links

- `adr_0016` — parallel adversary, checklist, reviewer configuration
  (the batch rule `max`'s multi-adversary launch uses)
- `adr_0015` — review by join level (unchanged: review depth is keyed on
  join level at every one of the five tiers)
- `adr_0012` — per-WP effective tier (its derivation is renamed, not
  changed)
- `hex/DESIGN.md` round 22

## Changelog

- 2026-09-06 — Proposed.
