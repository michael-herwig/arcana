# Discussion: nox as a bundle — core contract, dispatch, init, and the team/user/detected state split

State: active · Updated: 2026-10-03

## Intent

Owner's words: the nox skills are very limited; hex-init is "more like a user
configuration — which adversaries are there". Split the state that is local
to the user from team configuration and from what is merely *available* on
this machine. hex-init and a nox init should find each other, or at least
know about each other. Setup should be interactive: which harnesses are
available, which models to select. nox init must be re-entrant. Drain target
chosen at intake: **ADR** (`/hex-architect`, `high` floor).

Scope widened mid-discussion (owner): nox should be a *bundle*. The core
idea is "execute a different harness with a specific prompt"; `nox-review`
is one application. Wanted next: `nox dispatch` — run a work item on a
different harness/model (e.g. a cheaper GLM) as part of an execution
strategy. Owner's observations: no visible contract ("I would have expected
a JSON spec the harness has to comply to"); `--scope code-diff|plan-artifact`
is review-only yet sits on the core; a `nox-init` skill should help set up.

Why now: `~/.local/state/nox/calls.jsonl` on the owner's machine carries 48
runs refused `invalid_config` for "no harness configured" — the missing setup
surface is already costing runs. `.agents/memory/hex.md › Preferences` is
team-committed yet stores literal model names "for this harness" and a
per-host resource profile.

## Requirements

Provisional prose, no IDs.

- Three state layers, each with exactly one home: **team** (committed),
  **user** (per user; global and per clone), **detected** (probed, never
  authoritative, never a trust source).
- A machine-readable probe of what is available on this host — per
  registered nox adapter: present, version vs `verified_against`,
  authenticated, resolved model, containment capabilities, launcher in
  effect — usable by any init without re-implementing detection.
- nox setup is interactive and re-entrant: re-runs show `[current]`, diff
  before write, separate apply consent (the hex-init wizard shape).
- hex-init and nox setup discover each other. The nox *library* stays
  hex-blind (adr_0011 C-1001); only skill-layer files may read `hex.md`.
- Nothing per-user or per-host is written into a committed file.
- A published, application-neutral contract: a *job* the caller hands nox
  and a *result envelope* nox returns, both as JSON Schema files shipped
  with the skill; each application (review, dispatch) names its own
  `output` payload schema. Review's current `WIRE_SCHEMA`
  (`nox/src/nox/prompt.py`) becomes one such payload.
- Core verb that runs a job under a named harness; review and dispatch as
  sugar over it. `--scope` belongs to review only.
- Dispatch: a harness that *writes* — a work item executed on another
  harness/model, result returned as a patch or applied in place — without
  breaking review's read-only guarantee (adr_0011 C-1003 stays true for
  review jobs).
- hex may route a worker role to another harness/model through nox
  dispatch; literals live only in the local overlay.

## Decisions

Working positions, taken with the owner on 2026-09-06.

- **nox per-user-per-clone config home: `<git-common-dir>/nox.toml`** — git's
  own local-config layer. Moves with the clone, shared across worktrees,
  not branch-authorable, trusted like the user-level file. Cost accepted:
  one carve-out to nox's "no nox directory inside the tree under review"
  rule (`nox/src/nox/config.py` `_xdg`), resolved only under the plain git
  env nox already builds (`nox/src/nox/workspace.py` resolves
  `--git-common-dir` there), refusing any result inside the toplevel other
  than `<toplevel>/.git`. Guards against a branch-set `GIT_DIR`.
- **hex per-user/per-host overlay: `.agents/memory/hex.local.md`,
  gitignored.** Merges over `hex.md › Preferences` via
  `hex/hex-core/references/config.md` merge rules. hex-init owns the
  `.gitignore` line (it already audits that file for worktrees).
- **Facts that leave the committed `hex.md` for the overlay:** literal model
  instantiation (per harness), host resource profile (per host), **and the
  `adversary:` skill pin** — the pin follows the install, and skills install
  per user; a committed pin to an uninstalled skill is the dangling-pin
  drift the audit already reports. Review settings and limits stay team.
- **Primitive both inits consume: a nox CLI probe verb** (working name
  `doctor`, `--json`) exposing what `probe_harness` / `HarnessInfo` /
  `resolve_model` / `version_warning` already compute. Zero new stored
  state; nox's `ProbeCache` stays in-memory by its own documented reasoning
  (`nox/src/nox/harness.py`).
- **"Which harness am I running as"** (`--exclude`): hex passes its own
  client, never stores it. A nox-only caller gets a config key in the
  user layers (per-clone over user-global), CLI flag wins; the skill still
  tells the calling agent to pass `--exclude`.
- **`nox doctor` probe depth:** static by default (binary reachable,
  version vs `verified_against`, launcher, resolved config layers);
  `--probe` opt-in spawns each harness once for auth, resolved model and
  containment. Init wizards pass `--probe`.
- **Overlay key scope:** `hex.local.md` may carry the full Preferences
  vocabulary; local wins; same merge rules and clamps. One vocabulary, one
  parser.
- **Dispatch workspace mode is a job field:** `in-place | ephemeral`,
  default `ephemeral` (nox-owned write-capable worktree, instruction files
  preserved, result = patch). hex passes `in-place` from its own WP worktree.
- **Published contract = job + result-envelope JSON Schemas**, payload per
  application (`review.output` = today's `WIRE_SCHEMA`, `dispatch.output`
  new). Adapters hand the payload schema natively where the harness
  validates one.
- **Bundle shape: `nox-core` + thin siblings.** `nox-core` = `.pyz` +
  `schemas/` + SKILL.md (verbs `run`, `doctor`, `init`; "find me" recipe:
  `grim status --format json` primary, `../nox-core/scripts/nox.pyz`
  relative to the caller's own SKILL.md as fallback). `nox-review` and
  `nox-dispatch` = thin SKILL.md each — own trigger description, own hex
  marker (`hex-adversary-scopes` today; a dispatch marker to be named),
  build a job, reference `nox-core` by name. No `.pyz` copies. `nox-review`
  as shipped today → `replaced-by` the bundle member of the same name.
  PyPI rejected: name `nox` taken, reintroduces skill↔package skew.
- **`nox-init` is a markdown skill sibling** — owner's decision, reaffirmed
  after the council's unanimous counter. Accepted cost: it restates the
  wizard doctrine (chips, `[current]` defaults, diff before write, separate
  apply consent, re-entrant) in its own words; it may not link hex-init
  (C-1001). Default taken: the skill fronts a non-interactive `nox init
  --yes …` verb in `nox-core` as its write primitive, so TOML merge is code.
- **Per-clone `<git-common-dir>/nox.toml`: designed in the ADR (trust class
  = user-level, precedence, `GIT_DIR` guard), built after `doctor`/`init`**
  — two council seats called it YAGNI on current evidence; shipped when the
  call log shows a per-repo need.
- **hex routing to nox dispatch: explicit override, no new class.**
  `models.overrides.<role[:phase]>: nox:<harness>/<model>` in
  `.agents/memory/hex.local.md`; the shipped matrix is unchanged and no
  literal ships (`hex/DESIGN.md`). hex spawns that role via `nox dispatch`
  (`in-place`, from its WP worktree) instead of the client's agent tool;
  nox `Heartbeat` kinds map onto the liveness modes in
  `hex/hex-core/references/adversary.md`. A capability class may be added
  later if a routing pattern emerges.
- **nox layer precedence:** CLI flag › per-clone `<git-common-dir>/nox.toml`
  › repo-local `nox.toml` (non-gated keys only) › user-global
  `~/.config/nox/nox.toml` › shipped defaults.

Taken with the owner on 2026-10-03.

- **Drain split: two ADRs, nox first.** (A) nox bundle — `nox-core`
  verbs `run`/`doctor`/`init`, job + result-envelope schemas, dispatch
  workspace and instruction-file fields, thin `nox-review`/`nox-dispatch`/
  `nox-init` siblings; amends `adr_0011`. (B) hex state split — the
  `hex.local.md` overlay and what moves into it, the per-clone
  `<git-common-dir>/nox.toml` design, the hex-init ↔ `nox doctor --json`
  join, the `models.overrides` → `nox dispatch` routing; amends `adr_0001`
  and `hex/hex-core/references/config.md`. B consumes A's `doctor` output,
  so A lands first.
- **Dispatch preserves instruction files, as an explicit job field.**
  Default for dispatch jobs: CLAUDE.md, AGENTS.md and hooks kept — a
  builder needs the conventions, and the caller already trusts the repo it
  dispatches from. Review jobs keep neutralizing; `adr_0011` C-1003
  unchanged. The field lives in the job schema, not the adapter.
  Strongest counter, named once: preserved hooks run under the dispatched
  harness's credentials, so the premise holds only when the dispatch base
  is a ref the caller trusts — the ADR states that premise.
- **Silent adversary skip at `high` is a separate hex-core erratum,** not
  part of either ADR: surface the skip line at every tier where the
  adversary axis is on (`hex/hex-core/references/adversary.md`, the
  graceful-skip bullet). Lands right after the drain.

## Threads

- **Closed — who owns the wizard:** council unanimous against a `nox-init`
  skill; owner reaffirmed the skill. Recorded under Decisions. hex-init's
  re-audit consumes `nox doctor --json` read-only and reports "adversary pin
  resolvable?" — within its audit charter.
- **Closed — dispatch as a hex spawn transport:** explicit override in
  `hex.local.md`; recorded under Decisions.
- **Closed — drain split:** two ADRs, nox first; recorded under Decisions.

## Research

- `.agents/research/discuss-nox-bundle-statemap.md` — codebase recon: every
  config/state home for harnesses and models across hex and nox.
- `.agents/research/discuss-nox-bundle-priorart.md` — config-layer splits
  (git, VS Code, Claude Code, Codex, mise, direnv, pre-commit, gh, cargo,
  uv, npm) and doctor/init idempotency (brew, flutter, npm, gh, terraform,
  rustup).
- `.agents/research/discuss-nox-bundle-council.md` — three blind seats on
  the setup surface; unanimous `doctor`, no `nox-init` skill; synthesis.

## Related

- `.agents/adrs/adr_0011_nox_multi_harness_adversary.md` — C-1001 (hex-blind
  library), C-1017 (trust gate, T4b), C-1033 (marker + hex-init detection),
  D-w (`nox trust` deferred).
- `.agents/adrs/adr_0001_model_matrix_capability_classes.md` — classes never
  literals in shipped files; `hex/DESIGN.md` binds the same.
- `.agents/adrs/adr_0017*.md` — `adversary` as a list (C-995/C-997).
- `.agents/discussions/nox-multi-harness-adversary.md` — the prior nox
  discussion (handed-off → architect, 2026-08-31).
- `hex/hex-init/SKILL.md`, `hex/hex-init/references/audit.md` — wizard
  shape, "Cross-model adversary skill installed?" item, resource profile item.
- `hex/hex-core/references/{config,models,memory,adversary}.md`.
- `nox/nox-review/SKILL.md`, `nox/src/nox/{config,harness,api,cli}.py`.

## Open questions

Carried to the receiving orchestrator's docket; none blocks the drain.

- [NEEDS CLARIFICATION: name and home of the "harness I run as" key nox-only
  callers set so `--exclude` need not be passed each time.]
  Recommended: `[review] self = "<adapter>"` in the user layers, CLI
  `--exclude` wins; the skill still tells the calling agent to pass it.
- [NEEDS CLARIFICATION: dispatch marker key for hex-init detection.]
  Recommended: `hex-dispatch-scopes` on `nox-dispatch`'s frontmatter,
  mirroring `hex-adversary-scopes`.
- [NEEDS CLARIFICATION: `.gitignore` ownership for `.agents/memory/hex.local.md`.]
  Recommended: hex-init writes the line under its existing gitignore audit
  item, with consent.

## Out of scope

- Publishing nox to PyPI; a `nox trust` command; Windows support.
- Any weakening of review's guarantees: read-only ephemeral worktree with
  neutralized instruction files stays exactly adr_0011 C-1003 for review jobs.
- hex-execute changes beyond the routing hook that lets a role spawn via
  `nox dispatch`; no new hex orchestrator, no change to join-level review.
- Cross-model council seats; nox reviewing or dispatching to itself.
- The silent-skip fix in `hex/hex-core/references/adversary.md` — a
  separate erratum (see Decisions).

## Verification

- `grim build <skill-dir>` exit 0 for every changed or new skill
  (`nox-core`, `nox-review`, `nox-dispatch`, `nox-init`, `hex-init`,
  `hex-core`); `task publish -- --dry-run` exit 0.
- `task nox:verify` green (format, lint, types, tests, 100% branch coverage
  on the Linux leg); `nox/CLAUDE.md` invariants hold: zero runtime deps,
  no `hex` reference under `nox/src/`.
- Contract: `nox … --json` output validates against
  `schemas/result.schema.json`; a review job's `output` validates against
  `review.output.schema.json`; a job file round-trips through
  `schemas/job.schema.json`. Contract-tier fixtures per adapter.
- `nox doctor --json` on the owner's host lists the four registered
  adapters with present/version/launcher; `--probe` adds auth and resolved
  model; the run writes nothing (`ls -la ~/.config/nox ~/.local/state/nox`
  unchanged except `calls.jsonl` if a probe spawned a harness).
- `nox init` run twice: second run shows `[current]` values and an empty
  diff; `--yes` is non-interactive.
- `/hex-init` re-audit on this repo: proposes moving literal models and the
  resource profile into `.agents/memory/hex.local.md`, proposes the
  `.gitignore` line, reports adversary-pin resolvability from
  `nox doctor --json`; `git status` shows `hex.local.md` untracked-ignored.
- Dispatch smoke: one small work item dispatched to `opencode` with a
  configured `model_literal`, `ephemeral` mode returns a patch that applies
  cleanly; `in-place` mode from a hex WP worktree leaves edits in that
  worktree only.
