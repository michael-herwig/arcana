# Classification Signals

Signal-to-tier map for `/hex-review` when `tier=auto`, plus the overlay
triggers that stack on the chosen tier. Unlike `/hex-plan` (classifies from
a prompt), hex-review classifies from **actual diff metrics** against the
resolved baseline. The classifier emits a tier — **only** `low`, `medium`,
or `high` — with zero or more overlays.

The classifier **never emits `xhigh` or `max`** (reserved; see
[`protocol.md`](../hex-core/references/protocol.md#tier-grammar)). When
signals split across adjacent tiers, or the overlay mix is unusual, mark
**low-confidence** — that forces the meta-plan gate in
[`SKILL.md`](SKILL.md) step 5. Never fire a mid-flow question; ambiguity is
resolved at the single gate.

## Primary signal: diff metrics

Computed once at classification start, against the baseline
[`SKILL.md`](SKILL.md) step 2 resolved:

```
git diff <base>...<target> --name-only    # → changed-file list
git diff <base>...<target> --shortstat    # → lines added/removed
```

Derive:

- **file_count** — count of the changed-file list.
- **lines_changed** — added + removed from `--shortstat`.
- **areas_touched** — match each changed path against the project's own
  module/area boundaries, discovered from project rules and structure
  (project context, cached in `hex.md › Pointers`) — **never** a hardcoded
  table.
- **structural_markers** — see the table below.
- **pr_labels** — only when the target resolved to a PR.

## Tier metric table

| Tier | file_count | lines_changed | areas_touched | structural markers |
|---|---|---|---|---|
| **low** | ≤3 | ≤100 | 1 | none from the escalating list below |
| **medium** | ≤15 | ≤500 | 1–2 | no one-way-door-high signal |
| **high** | >15, or any one-way-door-high signal | any | ≥2 or cross-area | any one-way-door-high signal |

A diff may match multiple rows — pick the **highest** tier with at least
one clear signal firing. A small file count does not demote a diff that
introduces a new package.

## Structural marker signals

Language-agnostic globs — never a hardcoded per-project path table. Project
hints in `hex.md › Preferences` (always-review paths, e.g. "security review
mandatory under `src/auth/**`") fold in on top of these before the gate.

| Marker | Tier impact |
|---|---|
| New package/crate manifest appears (`Cargo.toml`, `package.json`, `pyproject.toml`, `go.mod`, …) | → **high** (new module/package) |
| CI workflow changes (`.github/workflows/**`, `.gitlab-ci.yml`, …) | Adds `breadth=full` minimum |
| Dependency-manifest changes (lockfiles: `Cargo.lock`, `package-lock.json`, `poetry.lock`, `go.sum`, …) | Adds `breadth=full` (supply-chain scrutiny) |
| Auth / crypto / signing paths (path contains `auth`, `crypto`, `sign`, `token`, or `secret`) | Adds `adversary=on`; security perspective required |
| Generated-file churn (matches the project's documented generated-file markers) | Adds `breadth=full`; note in output as low review value — don't nitpick generated content |
| Public API surface files (exported/public entry points added, changed, or removed — from the project's own module boundaries) | → **high**, adds `adversary=on` |
| `hex.md › Preferences` `perspectives.always` / `never` rule | `always`: adds the named perspective when its `when:` glob matches; `never`: removes the named perspective (a role-name list, no glob — `reviewer:security` additionally fail-closed, merge rule 5) ([`config.md` § Perspectives](../hex-core/references/config.md#perspectives)) |

## PR label signals

When the target resolves to a PR, read its labels and apply:

| Label | Effect |
|---|---|
| `breaking-change` | → **high**; `adversary=on` |
| `security` | Adds `breadth=full` or `adversarial`; `adversary=on` |
| `epic` | → **high** |
| `small` | Hint toward **low** (metrics can still escalate) |
| `docs` | Hint toward **low** if no code paths are touched |
| `chore` | Hint toward **low** |

Labels never *demote* below what the metrics dictate — a `small` label on a
30-file diff still runs `high` (size beats label).

## Confidence rules

- **Confident** — one tier has ≥2 matching signals (metrics, markers, or
  labels), no competing signal from an adjacent tier. Announce and proceed.
- **Low-confidence** — signals split adjacent tiers (e.g. metrics say
  `low`, a structural marker says `high`), the diff is metadata-only (a
  rename), or the target is ambiguous. Flag it;
  [`SKILL.md`](SKILL.md) routes into the meta-plan gate.

Never manufacture a question when confident: *announce and proceed*, or
*let the gate handle it*.

## Overlay triggers

Overlays adjust a single axis on top of the chosen tier and stack — several
may fire. Axis definitions and per-tier defaults are in
[`overlays.md`](overlays.md).

| Overlay | Triggered by |
|---|---|
| `breadth=full` | tier `medium` default; CI-workflow, dependency-manifest, or generated-file markers at tier `low` (escalation) |
| `breadth=adversarial` | tier `high` default; a public-API marker or `security` label at tier `medium` |
| `rca=on` | tier `medium`+ (default) — scope differs per tier, see [`overlays.md`](overlays.md) |
| `adversary=on` | any one-way-door-high structural marker; `breaking-change` or `security` label; public API change; new package/module |

## Baseline interaction with `auto` tier

`--base` changes what the classifier sees — **baseline controls effort**:

| Invocation | Typical diff size | Typical auto tier |
|---|---|---|
| `/hex-review` (no target, no `--base` — long-lived branch vs `main`) | often large | `medium` or `high` |
| `/hex-review --base=HEAD~1` | ≤3 files | `low` |
| `/hex-review --base=<parent-branch>` | a few commits | `low` or `medium` |
| `/hex-review --base=<older-tag>` | an entire release delta | `high` |
| `/hex-review <PR>` (base auto-resolved to the PR base) | PR-sized diff | matches PR scope |

A quick re-check of the last commit: pass `--base=HEAD~1`. Reviewing a
release cut: let the default baseline expand scope.

## Plan and artifact targets

When the target is a markdown plan, ADR, or spec file (not a diff), skip
diff-metric classification entirely — there is no `<base>...<target>` to
measure. Default to tier `medium` unless the user passes an explicit tier
or flag; the tier's breadth and RCA defaults still apply. The adversary
axis, when it fires, runs in `plan-artifact` scope instead of `code-diff`
([adversary contract](../hex-core/references/protocol.md#adversary-contract)).
Confidence is always **confident** for an explicit artifact path — there is
no metric ambiguity to flag.

## Examples

1. `/hex-review` on a 2-commit branch, 5 files in one area → tier
   **medium**, default overlays, confident.
2. `/hex-review --base=HEAD~1` on a one-line flag change → tier **low**,
   `breadth=minimal`, `rca=off`, `adversary=off`, confident.
3. `/hex-review 143` where PR #143 carries `breaking-change` +
   `enhancement` and touches a new package manifest → tier **high**,
   `breadth=adversarial`, `adversary=on`, confident.
4. `/hex-review --base=v0.5.0` on a branch 30 commits ahead → tier **high**
   by metrics; the meta-plan gate fires (`high` auto-fires the gate).
5. `/hex-review` with 4 files changed across two areas → metrics say `low`
   (size) but `medium`-leaning-`high` (2 areas) — low-confidence; the gate
   fires.
6. `/hex-review docs/plans/2026-07-add-export.md` (a plan artifact, no
   diff) → skip diff metrics; tier defaults to **medium**; an `on`
   adversary axis runs in `plan-artifact` scope.
