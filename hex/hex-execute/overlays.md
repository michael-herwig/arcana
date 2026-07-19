# Overlay Axis Definitions

Overlays are single-axis adjustments layered on the tier
[`classify.md`](classify.md) chose. They let `auto` mode assemble a mixed
config (e.g. a `medium` base that still runs `adversarial` review breadth for
a security-sensitive diff) without compound tier names. [`classify.md`](classify.md)
decides *when* an overlay fires from signals; this file defines *what each
axis means* and how it changes the pipeline. Grammar only lives here — the
shared overlay rules are in
[`protocol.md`](../hex-core/references/protocol.md#overlay-grammar).

## Axis grammar (flag values)

Matches the [`SKILL.md`](SKILL.md) parser:

```
--review=minimal|full|adversarial
--loop-rounds=1|2|3
--adversary / --no-adversary
```

## review axis

Controls which reviewer perspectives populate Round 1 of the
[Review-Fix Loop](../hex-core/references/protocol.md#the-review-fix-loop).

| Value | Effect |
|---|---|
| `minimal` | `reviewer` (focus `quality`) + `reviewer` (focus `spec`, phase `post-implementation`). Nothing else. |
| `full` | the `minimal` set, plus `reviewer` (focus `security`) when the diff touches security-sensitive paths (auth/crypto/signing, a new dependency manifest, a CI workflow file), `reviewer` (focus `performance`) when the diff touches a hot path or async code, and `doc-reviewer` when doc-drift triggers match. |
| `adversarial` | the `full` set, plus `architect` (ADR-compliance / boundary check) and `researcher` (SOTA-gap / known-pitfall check). |

Per-tier defaults:

| Tier | review default |
|---|---|
| low | `minimal` |
| medium | `full` |
| high | `adversarial` (mandatory) |

## loop-rounds axis

Controls the [Review-Fix Loop](../hex-core/references/protocol.md#the-review-fix-loop)
round cap.

| Value | Effect |
|---|---|
| `1` | Single round: one perspective batch, one builder fix pass, one re-verification. No iteration. |
| `2` | Up to two rounds. |
| `3` | Up to three rounds — the loop's canonical cap at `medium` and `high`. |

Per-tier defaults: low → `1`, medium → `3`, high → `3`. This axis lets a run
tighten or loosen the tier's baseline cap without changing tier — but a
stored `loop rounds` limit in `hex.md › Preferences` is a **ceiling** on it:
the flag may loosen only up to the stored value, never past it
([`protocol.md`](../hex-core/references/protocol.md#the-review-fix-loop)).

Both the `review` and `loop-rounds` axes are **ceilings**: a WP's `Review`
budget in the plan table lowers them per WP — `self` and `light` also force
a 1-round loop for that WP regardless of this axis
([`protocol.md`](../hex-core/references/protocol.md#the-review-fix-loop)).

## adversary axis (code-diff scope)

Controls whether the configured cross-model adversary skill runs against the
branch diff after the Review-Fix Loop converges. The skill name is read from
the Preferences section of `.agents/memory/hex.md`
(`codex-adversary` is only an example value); the full contract — scopes,
one-shot rule, 4-way triage, graceful skip — is in
[`protocol.md`](../hex-core/references/protocol.md#adversary-contract). This
is the `code-diff` scope; `/hex-plan` runs the same skill in `plan-artifact`
scope.

| Value | Effect |
|---|---|
| `off` | No cross-model diff review. |
| `on` | After the Review-Fix Loop converges, invoke the adversary skill once in `code-diff` scope against the branch diff versus base. One-shot, no loop. Triage its findings 4-way (actionable / deferred / stated-convention / trivia); actionable findings get one `builder` (focus `implement`) fix pass, re-verified. |

Per-tier defaults:

| Tier | adversary default |
|---|---|
| low | `off` (two-way door — cost outweighs value) |
| medium | `off`, auto-on when [`classify.md`](classify.md) fires `adversary=on` for one-way-door signals; explicit via `--adversary` |
| high | `on` (a default part of the flow; a skip is surfaced prominently) |

When the named skill is unavailable, log
`Cross-model review skipped: <reason>` and continue — a gate, not a blocker
([`protocol.md`](../hex-core/references/protocol.md#adversary-contract)).

## Precedence

User-supplied flags always override classifier-inferred overlays, which in
turn fold in `hex.md › Preferences` hints on top of the tier baseline —
later wins
([spawn-selection precedence](../hex-core/references/protocol.md#spawn-selection-precedence)).
When [`classify.md`](classify.md) infers `review=adversarial` but the user
passes `--review=full`, the user wins — including at `high` tier, where
`review=adversarial` and `adversary=on` are the defaults. A downward
override there is honored but never silent: the announce block flags it
("high tier recommends adversarial review — running `full` per user flag")
so the risk the tier signalled stays visible at the gate.
`tiers.hex-execute.<tier>.overlays` sets a per-project default for an
overlay axis — it rewrites this axis's tier baseline (a layer-1 rewrite, not a project hint — see [`config.md` § tiers](../hex-core/references/config.md#tiers)), below any user flag.
[`SKILL.md`](SKILL.md) step 6 prints the final resolved config with each
axis's source.
