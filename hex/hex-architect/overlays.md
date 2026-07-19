# Overlay Axis Definitions

Overlays are single-axis adjustments layered on the tier
[`classify.md`](classify.md) chose. [`classify.md`](classify.md) decides
*when* an overlay fires from signals; this file defines *what each axis
means* and how it changes the pipeline. Grammar only lives here — the shared
overlay rules are in
[`protocol.md`](../hex-core/references/protocol.md#overlay-grammar).

## Axis grammar (flag values)

Matches the [`SKILL.md`](SKILL.md) parser:

```
--research=skip|1|3
--axes=<comma-separated>
--adversary / --no-adversary
--artifact=inline|adr|system-design
```

## research axis

Controls the Research phase worker count. The axis **count** is set here;
the axis **selection** is a gate interaction, not a flag default — see
[`SKILL.md`](SKILL.md) step 4.

| Value | Effect |
|---|---|
| `skip` | No `researcher` launched. The orchestrator may still make a brief inline check against project context or a feature-detected docs tool. |
| `1` | One `researcher` on the single axis picked at the gate from [`classify.md`](classify.md)'s ranked candidates (default: the top-ranked candidate on plain approval). |
| `3` | Three `researcher` workers in parallel, one per axis picked at the gate (default: the top-3 candidates). |

Per-tier defaults: `low` → `skip`, `medium` → `1`, `high` → `3` (mandatory).
`--research=3` at `medium` promotes research breadth alone — the rest of the
tier (single architect worker, ADR-only artifact, bounded review) stays at
`medium`'s rules. `--axes=<a,b,c>` names axes explicitly, bypassing the
interactive picker; it is still echoed at the gate for confirmation, and its
length must match the resolved count (extra names beyond the count are
dropped with a note, fewer names fall back to classifier candidates for the
remainder). Researcher model class is `fast-balanced` at every tier
([`models.md`](../hex-core/references/models.md)); literal model choices
live in `hex.md › Preferences`, never in a flag.

## adversary axis (plan-artifact scope)

Controls whether the configured cross-model adversary skill runs against the
**design artifact** (the ADR, or the ADR + system-design doc) as a final gate
after the native design panel converges. Distinct from the *adversarial
design panel* itself (in-harness `reviewer` perspectives, a tier-baseline
behavior described in each tier file's Review phase) — this axis is only the
cross-model pass. The skill name is read from the Preferences section of
`.agents/memory/hex.md` (`codex-adversary` is only an example
value); the full contract — scopes, one-shot rule, 4-way triage, graceful
skip — is in
[`protocol.md`](../hex-core/references/protocol.md#adversary-contract). This
is the `plan-artifact` scope; `/hex-execute` runs the same skill in
`code-diff` scope on implementation later.

| Value | Effect |
|---|---|
| `off` | No cross-model design review. |
| `on` | After the design panel converges, invoke the adversary skill once in `plan-artifact` scope on the ADR (and system-design doc, if produced). One-shot, no loop. Triage its findings 4-way (actionable / deferred / stated-convention / trivia); re-run a single `reviewer` (focus `spec`) pass to validate any actionable fix. |

Per-tier defaults:

| Tier | adversary default |
|---|---|
| low | `off` (two-way door — cost outweighs value; no design panel either) |
| medium | `off`, auto-on when [`classify.md`](classify.md) fires `adversary=on` for one-way-door signals; explicit via `--adversary` |
| high | `on` (a default part of the flow; a skip is surfaced prominently) |

When the named skill is unavailable, log
`Cross-model design review skipped: <reason>` and continue — a gate, not a
blocker ([`protocol.md`](../hex-core/references/protocol.md#adversary-contract)).

## artifact axis

Controls what the design produces.

| Value | Effect |
|---|---|
| `inline` | Trade-off table and recommendation written directly in the conversation and the handoff block; no design-record file. |
| `adr` | An Architecture Decision Record is produced at the convention-resolved location ([`SKILL.md`](SKILL.md) › The design artifact). |
| `system-design` | A fuller system-design section (C4 levels, NFR detail, migration plan) is produced **in addition to** the ADR, not instead of it — for high-blast-radius or new-module decisions. |

Per-tier defaults:

| Tier | artifact default |
|---|---|
| low | `inline` (an ADR is written only if the user asks — `--artifact=adr`) |
| medium | `adr` |
| high | `adr`, with `system-design` added when [`classify.md`](classify.md)'s cross-area / external-contract / new-module signal fires |

## Precedence

User-supplied flags always override classifier-inferred overlays, which in
turn fold in `hex.md › Preferences` hints on top of the tier
baseline — later wins
([spawn-selection precedence](../hex-core/references/protocol.md#spawn-selection-precedence)).
When [`classify.md`](classify.md) infers `adversary=on` but the user passes
`--no-adversary`, the user wins. `tiers.hex-architect.<tier>.overlays` sets a
per-project default for an overlay axis — it rewrites this axis's tier baseline (a layer-1 rewrite, not a project hint — see [`config.md` § tiers](../hex-core/references/config.md#tiers)),
below any user flag.
[`SKILL.md`](SKILL.md) step 5 prints the final resolved config with each
axis's source.
