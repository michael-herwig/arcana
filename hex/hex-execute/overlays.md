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
[Review-Fix Loop](../hex-core/references/loop.md#the-review-fix-loop).

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

**In a plan carrying the generation marker** the breadth follows each WP's own
[effective tier](../hex-core/references/decompose.md#the-effective-tier) — the
table above, read per WP — and the run's resolved axis then applies as a `min`
cap over the result. **The order is part of the rule**, since `min` alone would
contradict the escape hatch: `Review: panel` raises the derived *tier* to the
ceiling first, the run's resolved axes cap the result second. So a `panel` WP
under `--review=full` runs the ceiling's phases and model cells with `full`
breadth.

## loop-rounds axis

Controls the [Review-Fix Loop](../hex-core/references/loop.md#the-review-fix-loop)
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
([`loop.md`](../hex-core/references/loop.md#the-review-fix-loop)).

**In a plan carrying the generation marker** the cap follows each WP's own
effective tier — the defaults above, read per WP — under the `min` cap
[`loop.md`](../hex-core/references/loop.md#the-review-fix-loop) states,
in the same order as the `review` axis.

**Both axes being lowered per WP by the `Review` cell is the pre-marker
reading, and the generation marker makes it false** — named here because it
sits outside both axis sections above. Without the marker it stands unchanged:
a WP's `Review` budget in the plan table lowers both axes per WP, and `self`
and `light` also force a 1-round loop for that WP regardless of this axis.
With the marker the cell is **raise-only** against the derived breadth — it
lowers neither axis, a cell at or below the derived value is inert, and
`self`/`light` force nothing
([`loop.md`](../hex-core/references/loop.md#the-review-fix-loop)).

## adversary axis (code-diff scope)

Controls whether the configured cross-model adversary skill runs against the
branch diff after the Review-Fix Loop converges. The skill name is read from
the Preferences section of `.agents/memory/hex.md` (`codex-adversary` is only
an example value); the full contract — scopes, one-shot rule, 4-way triage,
graceful skip, stall bound and backstop — is in
[`adversary.md`](../hex-core/references/adversary.md#adversary-contract). This is
the `code-diff` scope; `/hex-plan` runs the same skill in `plan-artifact`
scope.

**This axis reads the plan tier `T`, never a WP's effective tier.** A WP that
derived `low` inside a `high` plan **still runs the cross-model gate**: the pass
is a run-level assurance decision, and a per-WP size estimate must not become a
global skip switch
([the effective tier](../hex-core/references/decompose.md#the-effective-tier)).

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

When the adversary produces no review — the named skill is unavailable, or it
ran and did not complete one — log
`Cross-model review skipped: <reason>` and continue — a gate, not a blocker
([`adversary.md`](../hex-core/references/adversary.md#adversary-contract)).

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
