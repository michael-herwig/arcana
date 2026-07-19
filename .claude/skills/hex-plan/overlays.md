# Overlay Axis Definitions

Overlays are single-axis adjustments layered on the tier
[`classify.md`](classify.md) chose. They let `auto` mode assemble a mixed
config (e.g. a `medium` base that still delegates the architect for a weighty
design) without compound tier names. [`classify.md`](classify.md) decides
*when* an overlay fires from signals; this file defines *what each axis means*
and how it changes the pipeline. Grammar only lives here — the shared overlay
rules are in
[`protocol.md`](../hex-core/references/protocol.md#overlay-grammar).

## Axis grammar (flag values)

Matches the [`SKILL.md`](SKILL.md) parser:

```
--architect=inline|on
--research=skip|1|3
--adversary / --no-adversary
```

## architect axis

Controls the Design phase.

| Value | Effect |
|---|---|
| `inline` | The orchestrator drafts the design inline in the plan artifact. No `architect` worker launched. Fine for two-way-door changes. |
| `on` | Launch an `architect` worker to produce an ADR or system design. Its model class comes from [`models.md`](../hex-core/references/models.md) (row `architect` — **deep-reasoning** at every tier); a per-run bump or a per-cell override in `hex.md › Preferences` can adjust it, announced at the gate. Use for one-way-door decisions with real trade-offs. |

Per-tier defaults:

| Tier | architect default |
|---|---|
| low | `inline` |
| medium | `inline` for two-way-door scope; `on` for one-way-door medium |
| high | `on` (mandatory, with an ADR) |

## research axis

Controls the Research phase worker count.

| Value | Effect |
|---|---|
| `skip` | No `researcher` launched. The orchestrator may still make a brief inline check against project context. |
| `1` | One `researcher` on the single most relevant axis (technology *or* patterns *or* domain). |
| `3` | Three `researcher` workers in parallel, one per axis: technology / patterns / domain. |

Per-tier defaults: low → `skip`, medium → `1`, high → `3` (mandatory).
Researcher model class is `fast-balanced` at every tier
([`models.md`](../hex-core/references/models.md)); literal model choices and
per-role overrides live in `hex.md › Preferences`, never in a flag.

## adversary axis (plan-artifact scope)

Controls whether the configured cross-model adversary skill runs against the
plan artifact as a final gate after the native review panel converges.
The skill name is read from the Preferences section of
`.agents/memory/hex.md` (`codex-adversary` is only an example value);
the full contract — scopes, one-shot rule, 4-way triage, graceful skip — is in
[`protocol.md`](../hex-core/references/protocol.md#adversary-contract). This is
the `plan-artifact` scope; `/hex-execute` runs the same skill in `code-diff`
scope.

| Value | Effect |
|---|---|
| `off` | No cross-model plan review. |
| `on` | After the review panel converges, invoke the adversary skill once in `plan-artifact` scope on the plan file. One-shot, no loop. Triage its findings 4-way (actionable / deferred / stated-convention / trivia); re-run a single `reviewer` (focus `spec`) pass to validate any actionable fix. |

Per-tier defaults:

| Tier | adversary default |
|---|---|
| low | `off` (two-way door — cost outweighs value) |
| medium | `off`, auto-on when [`classify.md`](classify.md) fires `adversary=on` for one-way-door signals; explicit via `--adversary` |
| high | `on` (a default part of the flow; a skip is surfaced prominently) |

When the named skill is unavailable, log
`Cross-model plan review skipped: <reason>` and continue — a gate, not a
blocker ([`protocol.md`](../hex-core/references/protocol.md#adversary-contract)).

## Precedence

User-supplied flags always override classifier-inferred overlays, which in
turn fold in `hex.md › Preferences` hints on top of the tier baseline —
later wins
([spawn-selection precedence](../hex-core/references/protocol.md#spawn-selection-precedence)).
When [`classify.md`](classify.md) infers `architect=on` but the user passes
`--architect=inline`, the user wins. `tiers.hex-plan.<tier>.overlays` sets a
per-project default for an overlay axis — it rewrites this axis's tier baseline (a layer-1 rewrite, not a project hint — see [`config.md` § tiers](../hex-core/references/config.md#tiers)),
below any user flag.
[`SKILL.md`](SKILL.md) step 6 prints the final resolved config with each
axis's source.
