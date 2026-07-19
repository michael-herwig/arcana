---
name: hex-execute
description: Tiered multi-agent execution orchestrator — implements an approved hex-plan artifact (or a free-text task) through contract-first TDD (stub, specify, implement, bounded review-fix loop), then commits. Runs file-disjoint work packages in parallel git worktrees and merges onto a feature branch in serialized topological order. Use to execute, implement, build, or run an approved plan, resume an interrupted execution, or turn a design into tested, reviewed, committed code. Tier (low|medium|high, auto by default) scales review breadth, review-fix loop rounds, and the cross-model code-diff gate.
license: Apache-2.0
metadata:
  summary: Tiered swarm execution — plan artifact to tested, reviewed commit
  keywords: execution,swarm,multi-agent,tdd,implementation,review-fix,worktrees
  repository: https://github.com/michael-herwig/arcana
---

# hex-execute — Execution Orchestrator

Thin dispatcher. It parses arguments, resolves the target plan, classifies
its tier, resolves overlays, runs the single meta-plan approval gate,
announces the resolved config, and hands off to the matching tier file. The
phase plans live in `tier-low.md`, `tier-medium.md`, and `tier-high.md`; the
shared vocabulary (tiers, the Review-Fix Loop, worker roles, model classes,
the memory file) lives in the `hex-core` reference library and is **linked
here, never copied**.

Shared contracts:
[`protocol.md`](../hex-core/references/protocol.md) ·
[`workers.md`](../hex-core/references/workers.md) ·
[`models.md`](../hex-core/references/models.md) ·
[`memory.md`](../hex-core/references/memory.md).
If `hex-core` is not installed: `grim add ghcr.io/michael-herwig/hex-core:latest`.

## Argument syntax

```
/hex-execute [tier] [target] [flags]
```

- **tier** (optional): `low | medium | high | auto`. Default `auto` — the
  classifier picks one of the three from the plan's Status block or
  free-text signals. `xhigh` and `max` are **reserved** (see
  [`protocol.md`](../hex-core/references/protocol.md#tier-grammar)): the
  classifier never emits them, and an explicit reserved tier is announced as
  "`<tier>` reserved, running high" and run as `high`.
- **target** (optional; one of):
  - a plan artifact path — the product of `/hex-plan` or the project's own
    convention;
  - a free-text task description — no plan artifact; scoped inline (see
    [`classify.md`](classify.md#fallback-free-text-targets));
  - omitted — resolve the active-plan pointer from `hex.md › Memory`
    ([`memory.md`](../hex-core/references/memory.md#the-three-sections)).
- **flags** (before the target, by convention):
  - `--review=minimal|full|adversarial` — override Review-Fix Loop breadth.
  - `--loop-rounds=1|2|3` — override the loop's round cap.
  - `--adversary` / `--no-adversary` — force the cross-model code-diff pass
    on or off.
  - `--dry-run` — make the meta-plan gate block for explicit approval and
    stop there (preview only, no workers launched).

## Dispatch

The outer loop every hex orchestrator shares
([`protocol.md`](../hex-core/references/protocol.md#shared-shape)):

### 1. Parse arguments and resolve memory

Parse the tier, target, and flags. Locate `.agents/memory/hex.md` by
searching upward from the working directory; a missing file is normal
([`memory.md`](../hex-core/references/memory.md#location-and-resolution)) —
fall back to shipped defaults and note that `/hex-init` can create one. When
present, read the whole file: `hex.md › Pointers` for where verification is
documented, any worktree-location deviation, and where product knowledge
lives in project context; `hex.md › Preferences` for the instantiated model
matrix, the adversary skill name, limits, and always-on perspectives; and
`hex.md › Memory` for the active-plan pointer when no target argument was
given.

If the resolved `hex.md` carries a `Federation lead:` bullet, **halt** per
[`memory.md` § Location and resolution](../hex-core/references/memory.md#location-and-resolution)
— this repo is a federation satellite and its memory is not the plan's.

**Federation pre-flight (C-303) — the procedure.** When the target plan
resolved in step 2 carries a `Repo` column, run this in the pre-gate window —
after memory and target are resolved, **before the gate (step 5) and before any
branch, worktree, commit or back-pointer**. It *realizes* the pre-flight access
invariant defined once in
[`protocol.md` § Worktree work-package mechanics](../hex-core/references/protocol.md#worktree-work-package-mechanics)
(the barrier, and what each clause rules out); protocol.md owns that invariant —
the steps below are its executable realization, restating only the operational
minimum the procedure needs.
For **every** Federation key the plan's `Repo` column actually uses (resolved
against the lead's `Federation:` bullets in `hex.md › Pointers`), with `<path>`
the key's declared path, run:

```bash
git -C <path> rev-parse --show-toplevel                          # (i)   must equal <path>
git -C <path> rev-parse --path-format=absolute --git-common-dir  # (ii)  must differ from the lead's
git -C <path> status --porcelain                                 # (iii) must succeed
mkdir -p <path>/.agents && : > <path>/.agents/.hex-write-probe \
  && rm <path>/.agents/.hex-write-probe                          # (iv-a) working-tree writability
git -C <path> update-ref refs/hex/write-probe HEAD \
  && git -C <path> update-ref -d refs/hex/write-probe            # (iv-b) git-dir writability
git -C <path> symbolic-ref --short refs/remotes/origin/HEAD      # (v)   trunk discovery, step 1
git -C <path> check-ignore -q .agents/worktrees/                 # (vi)  worktree path must be ignored
```

- **(iv) the write probe** is why (i)–(iii) — readability only — is not enough:
  every federated write comes later, so the probe writes twice and undoes both
  immediately (a zero-byte file under `<path>/.agents/`, and a
  `refs/hex/write-probe` ref created from `HEAD` and deleted), leaving the repo
  byte-identical. A read-only grant fails here, not half-way through execution.
  Its `writable` outcome is disclosed in the gate echo; on `.agents/`
  pre-creation a declined run leaves only that inert directory.
- **(v) trunk discovery, in order — `main` is never assumed:** (1) `origin/HEAD`
  above, stripping the remote prefix, authoritative when present; (2) else the
  trunk documented in **that repo's project context**, read by an explicit
  `Read` (C-318 forbids reading its swarm memory); (3) else **halt and ask**,
  naming the repo, with the `git -C <path> remote set-head origin --auto` fix.
  Whatever (1) or (2) yields must exist as a local ref
  (`git -C <path> rev-parse --verify refs/heads/<trunk>`) or the same halt fires.
- **(vi)** on a miss, **halt and offer to add `.agents/worktrees/`** to that
  repo's ignore file — never `.agents/` wholesale
  (`.agents/memory/hex.md` is version-controlled). A satellite may never
  have run `/hex-init` (exempt there), so nothing else guarantees the path is
  ignored.
- **Barrier, not a per-repo gate.** Issue the run's first
  `git -C <satellite> branch` / `worktree` / commit / back-pointer write only
  after the **last** key has cleared all six clauses — a partially accessible or
  partially writable cluster produces **zero** writes. On any failure **halt**
  with an `Error:`/`Fix:` pair carrying a pasteable `--add-dir` relaunch line
  (print the narrowest form that works — one ancestor grant, e.g.
  `--add-dir /home/mherwig/dev`, covers a whole sibling cluster); never degrade,
  never skip a repo.
- **Freeze and record the bases here.** In this same pre-gate step, resolve each
  participating repo's frozen base (its trunk tip; the lead's is its resolved
  feature-branch tip) and trunk, and write them **once** into the plan's
  `Repos:` ledger (see [The plan artifact](#the-plan-artifact)) — never
  re-resolved later (C-317/C-324).
- **Echo per key.** Emit one pre-flight line per key into the step-6 announce
  block — `toplevel`, `common-dir`, `clean`, `writable`,
  `trunk=<branch> (<source>)` — so clause (i), the one whose omission is silent,
  is auditable:

  ```
  Pre-flight: mirror  ../acme-mirror  toplevel=/home/mherwig/dev/acme-mirror
                      common-dir=/home/mherwig/dev/acme-mirror/.git
                      clean  writable  trunk=main (origin/HEAD)
  ```

`/hex-plan` never runs this pre-flight (planning needs no satellite access);
`/hex-review` runs its read-only subset (C-320).

### 2. Resolve the target

Resolve to one of three modes:

1. **Explicit plan path** — the argument names a file; read it whole: the
   Status block (`State`, `Tier`, `Updated`, `Next`), component contracts,
   UX scenarios, and the Parallelization table.
2. **No argument** — resolve the active-plan pointer from `hex.md › Memory`
   ([`memory.md`](../hex-core/references/memory.md#the-three-sections)); if
   none is recorded, stop and ask for a target rather than guessing.
3. **Free-text task** — the argument is not a path; treat it as an ad-hoc
   target with no plan artifact. Component contracts and UX scenarios are
   scoped inline instead of read from a plan.

When a plan resolves, check its Status block `State`: `plan-approved` is the
expected entry state. `executing` means a prior run was interrupted —
WP-level resume reads the plan table's `Status` column (`pending | active |
merged | failed`); branches and worktrees are only its evidence (see Work
packages below). A `coordinator` interrupted mid-fan-out is **not**
rehydrated: its sub-WPs are ordinary table rows, so resume re-runs the WP's
unfinished sub-WP rows directly — flat — resetting to the last committed
sub-WP boundary (the [`coordinator`](../hex-core/references/workers/coordinator.md)
commits per sub-WP join as reset points); the sub-WP tiny loop is not
re-established on resume — the branch-level Review-Fix panel is its backstop
— announce that. When a plan lacks the column, fall back to re-deriving
progress from existing `hex/<plan-slug>--<wp-slug>` branches. The
Implementation Steps checkboxes (`- [ ]` / `- [x]`) stay the finer
within-WP progress, no separate state file to consult. `landing` — a
federated plan (carrying a `Repo` column) that `/hex-review` advanced past
execution and that awaits its satellite feature branches being landed into
their trunks — is a **finalize-only re-entry**: skip every execution phase
(all WPs are already `merged`) and run **only** the Federation
landing-confirmation
[upkeep step](../hex-core/references/protocol.md#upkeep-step) — the step that
advances the plan to `done` once every `Repos:` row is confirmed landed and
then releases the C-313 satellite locks. Upkeep cleared the active-plan
pointer at `landing`, so a no-argument re-run cannot resolve it: pass the
explicit plan path (mode 1). `review` or `done`
means this plan already passed execution — **stop and report** rather than
silently re-running; the human decides whether to re-execute.

**Federation refusal (C-323).** A run is federated only if its own resolved
`hex.md` carries `Federation:` bullets; if the resolved plan carries a `Repo`
column but this run's does not, **halt** per [`memory.md` § Location and
resolution](../hex-core/references/memory.md#location-and-resolution) — it
cannot address the plan's satellite repos and must not execute a partial
plan. Every `Repo` value must resolve to a declared Federation key, or halt
the same way.

### 3. Classify (only when tier is `auto`)

Read [`classify.md`](classify.md). Apply its plan Status-block signal
(primary) and free-text fallback (secondary) to the resolved target. It
emits a candidate tier (**only** `low`, `medium`, or `high`), a confidence
flag, and an overlay set. Low confidence forces the gate in step 5. Never ask
a mid-flow question during classification — ambiguity is resolved at the
single gate.

### 4. Resolve overlays

Final config = the tier's baseline from [`overlays.md`](overlays.md) +
classifier-inferred overlays + `hex.md › Preferences` hints + user flags.
Later wins; **user flags always override** (see
[`protocol.md`](../hex-core/references/protocol.md#spawn-selection-precedence)).

### 5. Meta-plan gate (the single approval point)

Exactly one gate, before any worker launches
([`protocol.md`](../hex-core/references/protocol.md#the-meta-plan-approval-gate)).
Its weight scales:

- **Confident `low` / `medium`** (an explicit user tier always counts as
  confident — the classifier never ran) — announce the resolved config (step 6) and
  proceed; the user can still abort.
- **`high` tier, low-confidence classification, or `--dry-run`** — block for
  explicit approval.

On a client with a **native plan-approval mechanism**, use it. Otherwise
present the announce block as **one structured question** (approve / adjust
/ cancel). The gate is also where the user can add or drop review
perspectives and adjust the loop-rounds cap. On adjust, re-resolve and
re-present once. Never split this into sequential questions.

### 6. Announce the resolved config

Print the resolved config with per-axis source attribution before loading
the tier file (format:
[`protocol.md`](../hex-core/references/protocol.md#the-meta-plan-approval-gate)):

```
hex-execute
  Tier:      medium                          (from plan Status block)
  Target:    .agents/plans/plan_cache.md
  Overlays:  review=full                     (tier baseline)
             loop-rounds=3                    (tier baseline)
             adversary=on                     (classifier: one-way-door signal)
  Spawn set:
    builder ×3 (stub, implement)              (tier baseline — 3 work packages)
    tester ×3                                 (tier baseline — 3 work packages)
    reviewer: spec (post-stub, post-implementation)   (tier baseline)
    reviewer: quality                         (tier baseline)
    reviewer: security                        (hex.md preference: src/auth/**)
  Models:    fast-balanced default; reviewer:security + coordinator → deep-reasoning  (models.md)
  Adversary: codex-adversary, code-diff scope             (hex.md preference)
  Work packages: 3 WPs, DAG launch — ready now: WP1, WP2
             review budgets: WP1 light, WP2 self, WP3 panel
             critical path WP1 → WP3          (plan Parallelization table)
  Recursion:  WP3 → coordinator (4 sub-tasks, decomposable)   (granularity gate)
              others → single builder                          (below gate)
  Branches:  feature hex/plan-cache; ephemeral hex/plan-cache--<wp> per WP
  Degraded:  no — nested spawn + programmatic orchestration available
```

The announce block prints one config-disclosure line per change a
`hex.md › Preferences` block makes; the full trigger set is defined once in
[`protocol.md` § the meta-plan approval gate](../hex-core/references/protocol.md#the-meta-plan-approval-gate).
For this skill, for example:

```
  [project-redefined: Review-Fix.reviewer:quality 1→2 (hex.md tiers)]
  [reviewer:performance dropped — phase ceiling 8 reached]
  [Review-Fix batched 4+4 — concurrency cap 4 (hex.md)]
  Error: never [reviewer:security] refused (hex.md preference)
  Fix:   see config.md#merge-rules for the attestation requirement
```

Every spawn line carries its source (`tier baseline` / `classifier` /
`hex.md preference` / `user flag`) per
[spawn-selection precedence](../hex-core/references/protocol.md#spawn-selection-precedence).
Model names above are class placeholders — shipped files never hardcode
literals; the running orchestrator resolves and prints each spawn's
literal model per the
[Models line contract](../hex-core/references/protocol.md#the-meta-plan-approval-gate). On a client that cannot spawn subagents, announce
`Degraded: inline workers` and run each worker prompt inline and sequentially
([`protocol.md`](../hex-core/references/protocol.md#worker-coordination)).

### 7. Dispatch to the tier file

Read `workflows.hex-execute.<tier>` from the resolved config first. When set
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
execution phases; the tier files set the actual counts and which
Review-Fix perspectives fire.

| Phase | Role | Count | Purpose |
|---|---|---|---|
| Stub | `builder` (focus `stub`) | 1 per work package | Public API surface only, not-implemented bodies |
| Verify-Architecture | `reviewer` (focus `spec`, phase `post-stub`) | 0–1 per WP | Stubs match the plan's component contracts |
| Verify-Architecture | `architect` | 0–1 | ADR / boundary compliance (high tier) |
| Specify | `tester` (focus `specification`) | 1 per work package | Tests from the plan's design record, must fail against stubs |
| Implement | `builder` (focus `implement`) | 1 per work package | Fill bodies until the specification tests pass |
| Implement | `coordinator` | 0–1 per qualifying WP | Fans out parallel leaves within a WP that meets the granularity gate ([`coordinator`](../hex-core/references/workers/coordinator.md)) |
| Review-Fix | `reviewer` (focus `spec`, phase `post-implementation`) | 1 | Full traceability, every tier |
| Review-Fix | `reviewer` (focus `quality`) | 1 | Every tier |
| Review-Fix | `reviewer` (focus `security`) | 0–1 | Security-sensitive paths touched |
| Review-Fix | `reviewer` (focus `performance`) | 0–1 | Hot-path / async paths touched |
| Review-Fix | `doc-reviewer` | 0–1 | Doc-drift triggers matched |
| Review-Fix | `architect` | 0–1 | ADR-compliance / boundary check (adversarial breadth) |
| Review-Fix | `researcher` | 0–1 | SOTA-gap / known-pitfall check (adversarial breadth) |
| Adversary | configured adversary skill (`code-diff`) | 0–1 | Cross-model review of the branch diff |

A project's `tiers.hex-execute.<tier>.counts` can override any Count cell
above against the baseline this table sets
([`config.md` § Merge rules](../hex-core/references/config.md#merge-rules)).

Concurrency cap and degraded mode:
[`protocol.md`](../hex-core/references/protocol.md#worker-coordination). The
adversary skill name comes from `hex.md › Preferences`
([adversary contract](../hex-core/references/protocol.md#adversary-contract));
`codex-adversary` is only an example value.

## Project rules and conventions

hex never carries a hardcoded rule or subsystem table. Every phase that needs
the project's invariants, verification command, or artifact conventions
discovers them from **project context** (the client's ambient instructions /
project rules) and the pointers in the Pointers section of
`.agents/memory/hex.md`
([`memory.md`](../hex-core/references/memory.md#the-three-sections)). "Verify"
anywhere below means **run the project's documented verification**
([`protocol.md`](../hex-core/references/protocol.md#verification)); if none
is documented, detect a reasonable command once for this run and suggest
`/hex-init` to persist it.

## The plan artifact

**Location and resolution.** As resolved in Dispatch step 2: an explicit
path, or the active-plan pointer in `hex.md › Memory`
([`memory.md`](../hex-core/references/memory.md#location-and-resolution)).
hex-execute never invents a plan location — it consumes what `/hex-plan` (or
the project's own convention) already wrote.

**Status-block mutations.** hex-execute is a co-owner of the plan's
self-contained Status block alongside `/hex-plan` and `/hex-review` — no
external state file:

```markdown
## Status
- State:   executing      <!-- planning → plan-approved → executing → review → done -->
- Tier:    medium
- Updated: 2026-07-19
- Next:    /hex-execute <this plan path>
```

On dispatch, after the gate passes: `State: executing`, `Updated` refreshed.
On completion of the tier's final phase (Review-Fix Loop converged,
verification green, work committed): `State: review`,
`Next: /hex-review <plan path>`. A free-text target with no plan artifact has
no Status block to mutate — note that in the handoff instead. Per-phase
resume progress lives in the plan's own Implementation Steps checkboxes
(`- [ ]` / `- [x]`), not in `State` — `State` only tracks the coarse phase
for other tools to read.

**The `Repos:` ledger (C-324).** A plan carrying a `Repo` column carries one
`Repos:` sub-block inside its Status block — one line per participating repo:
key, absolute path, resolved trunk (C-304), full 40-character base SHA (C-317)
and a `landed:` flag.

```markdown
- Repos:   <!-- frozen at execution start; bases are never re-resolved -->
  - `.`      /home/mherwig/dev/acme         trunk `main` base `a1b2c3d4…`  landed: yes (2026-07-21)
  - `mirror` /home/mherwig/dev/acme-mirror  trunk `main` base `e5f6a7b8…`  landed: no
```

- **Written once**, by hex-execute in the C-303/C-317 pre-gate step (Dispatch
  step 1), before any branch — the resolved trunk and full base SHA per repo,
  `landed: no`. Existing rows are never re-written.
- **Read, never re-resolved**, by resume, `/hex-review`, merge-time file-set
  re-validation and convergence: `<base>` for every diff is that SHA, never a
  trunk ref that may have moved since (C-317).
- **Resume halt.** A resumed run that finds the block **absent while the table
  carries a `Repo` column and any WP row is not `pending`** cannot recover its
  bases and **halts** — diffing against a moved baseline is silent corruption.
  With every WP still `pending`, the block is simply written fresh.

The field layout is the plan template's
([`plan.md`](../hex-init/assets/templates/plan.md)) and the persistence
invariant is protocol.md's (§ Worktree work-package mechanics, C-317); this
section owns only the write moment and the read-never-re-resolve rule.

**Living design record.** When execution reveals a behavior or edge case the
plan didn't specify, update the plan artifact first, then write the
corresponding test, then implement — never invent a requirement a test
alone documents.

**Spec-delta authoring (C-419).** On each WP merge, append that WP's delta
entries to the plan's single `## Spec Deltas` block — one `Target:` for the
whole plan (C-415). Each `MODIFIED` entry carries a `Base:` enumeration
(live sub-IDs + non-blank line count) read from the **live** destination — the
sub-ID set is the **pasted output** of archive.md's stale-base sub-ID scan
([C-405](../hex-core/references/archive.md#safety-envelope)) run over the live
destination body, not a narrated set, so the fold's C-405 diff has a
command-produced base to compare against. Under a federated plan the `Base:`
is read from the **lead repo's** destination, and a satellite-delivered entry
(`Repo` ≠ `.`) defers rather than folding (C-415 clause 5). Same append-only
discipline as the Living design record above — never rewrite another WP's
entry. The full grammar, `Base:` mechanics, guards and halts live in
[`archive.md` § Delta grammar](../hex-core/references/archive.md#delta-grammar).

## Work packages

Read the plan's Parallelization table (WP id, scope, expected files, size,
wave, depends-on, review, status) before Stub begins. A missing `Review`
column or cell defaults to **`panel`** at table-parse time — pre-budget
plans execute unchanged
([`protocol.md`](../hex-core/references/protocol.md#the-review-fix-loop)).
Then **resolve the feature branch** — the plan's single integration target: the non-trunk branch
already checked out, else create `hex/<plan-slug>` from the trunk
([`protocol.md`](../hex-core/references/protocol.md#worktree-work-package-mechanics)).
Two shapes:

- **Single work package** — normal at tier `low`; above it, only when the
  plan's justification line says why. Run Stub → Specify → Implement →
  Review-Fix directly on the feature branch; no worktree needed.
- **2+ work packages** — each WP launches the instant every WP in its
  `Depends-on` has merged (dependency-ready launch, per the [Schedule
  step](#schedule) and
  [`protocol.md`](../hex-core/references/protocol.md#parallel-by-default-decomposition)),
  each in its own ephemeral branch + worktree, each running its own Stub →
  Specify → Implement → Review-Fix cycle scoped to its declared file set;
  merge back onto the feature branch serialized in a valid topological
  order, verification after every merge. Mechanics — branch naming, frozen
  base, worktree location and cleanup — live in
  [`protocol.md`](../hex-core/references/protocol.md#worktree-work-package-mechanics),
  never restated here.

**Status-column mutations.** The table's `Status` column
(`pending | active | merged | failed`) is the per-WP state of record: set
`active` when a WP's worktree is created, `merged` after its merge onto the
feature branch, `failed` per the merge-conflict / post-merge-failure
playbook. This is a finer grain than the plan-level Status block: `State`
(step 2 above) is the coarse phase for other tools to read; the table's
`Status` column is per-WP.

**Federation — a WP whose `Repo` is a satellite key.** The mechanics are
protocol.md's (§ Worktree work-package mechanics — satellite worktrees, merge
serialization, the `Hex-Plan:` trailer); this section owns only what hex-execute
*does*. Absent a `Repo` column none of it fires.

- **Satellite worktree from the frozen SHA (C-305).** Create the branch and
  worktree in the owning repo:
  `git -C <path> branch hex/<plan-slug> <base>` — where `<base>` is that repo's
  **frozen base SHA read from the `Repos:` ledger**, never a trunk ref — then
  `git -C <path> worktree add .agents/worktrees/<wp-slug> hex/<plan-slug>--<wp-slug>`.
  The worktree lives under the **satellite's** own `.agents/worktrees/`.
- **Lazy back-pointer write (C-308).** At the **first** satellite worktree
  creation for this plan, append the plan slug to that satellite's
  `Federation lead:` bullet under `## Pointers` in
  `<path>/.agents/memory/hex.md` — the satellite's **main checkout
  working tree**, never the ephemeral WP worktree and never on the
  `hex/<plan-slug>` branch, because memory resolution reads the filesystem, not
  git, so the FM6 guard is live the instant the file is written. Create the file
  holding only this bullet if the satellite has none; the slug list never holds
  duplicates. Leave it **uncommitted** — hex does not commit it, and its
  presence never blocks the C-303 (iii) `status --porcelain` check. The write is
  disclosed at the **existing** meta-plan gate (C-315), never a second gate; the
  bullet grammar and the `Error:`/`Fix:` halt it later triggers are defined once
  in [`memory.md` § Location and resolution](../hex-core/references/memory.md#location-and-resolution).
- **`Hex-Plan:` trailer (C-307).** Every commit hex makes in a satellite carries
  `Hex-Plan: <remote-slug>:<repo-relative plan path>` in its trailer block — the
  only satellite-side record of the plan.

Merge-time file-set re-validation and the merge-conflict /
post-merge-failure playbook are defined in
[`protocol.md`](../hex-core/references/protocol.md#worktree-work-package-mechanics)
— never restated here.

A plan whose Parallelization section under-uses its own file-disjointness
(parallel-eligible WPs marked sequential, no justification) is a plan
defect — flag it at the gate rather than silently executing narrow.

Commit per completed phase or work package, as the project's own conventions
dictate (see Constraints below); never push.

### Schedule

One internal **Schedule** step connects the resolved target to the launch
machinery — orchestrator-internal, non-gating, never a second approval
point. Its ready-set computation runs in Dispatch (after the target
resolves) to feed the step-6 announce block; its worktree preparation is
the post-gate realization, in the tier file's Discover phase:

1. **Read the table.** Take the resolved plan's Parallelization table (WP
   id, scope, expected files, size, wave, depends-on, review, status) as the
   state of record. For a **free-text target** with no plan artifact, build
   an inline mini-table with the same eight columns
   (`WP | Scope | Expected Files | Size | Wave | Depends on | Review | Status`) so
   the free-text path drives the same launch machinery — Review assigned per
   the protocol heuristic
   ([`protocol.md`](../hex-core/references/protocol.md#parallel-by-default-decomposition)) — **a single WP by
   default**, decomposed into several only when the task plainly names ≥3
   disjoint areas. (A free-text `high` target still routes through
   `/hex-plan` — see
   [`classify.md`](classify.md#fallback-free-text-targets) — so a
   mini-table here is a `low`/`medium` shape.)
2. **Compute the ready-set** — the WPs whose every `Depends-on` is already
   `merged`, ordered critical-path-first — per protocol.md's
   dependency-ready launch rule
   ([`protocol.md`](../hex-core/references/protocol.md#parallel-by-default-decomposition)).
   Recompute the ready-set after every merge; ready WPs' worktrees are
   prepared post-gate (Discover) as each becomes eligible.
3. **Select the fan-out mechanism.** Detect the harness's fan-out
   capabilities for this run — never stored — and pick each qualifying WP's
   mechanism per protocol.md's fan-out-mechanism rule
   ([`protocol.md`](../hex-core/references/protocol.md#worker-coordination)):
   programmatic orchestration preferred, nested subagent spawning the
   fallback, else degraded flattening — no coordinators, a single builder per
   WP. Which WPs qualify is the granularity gate in
   [Coordinator spawn](#coordinator-spawn) below.
4. **Feed the announce block.** Emit the resolved schedule into the
   **existing** Dispatch announce block (step 6) — the `Work packages:`,
   `Recursion:`, and critical-path lines — never a new question.

### Coordinator spawn

A WP qualifies for a [`coordinator`](../hex-core/references/workers/coordinator.md) —
a worker that fans out parallel implementation and review *within* the WP —
only when it holds **≥3 independent, WP-grain sub-tasks** and the work is
**decomposable**. The gate is orchestrator judgment, not a mechanical count;
the conservative default is a **single builder**. The full preconditions and
the coordinator's internals live in
[`workers/coordinator.md`](../hex-core/references/workers/coordinator.md) —
never restated here.

Review grows by **diversity across join levels**, never same-role count at
one level. Three join scopes, by size:

- **Sub-WP join** (sub-WPs → WP result, inside a coordinator) — the tiny
  1-round spec+quality loop, defined in the coordinator role
  ([`workers/coordinator.md`](../hex-core/references/workers/coordinator.md)).
- **WP merge** (a WP lands on the feature branch) — the WP's **budgeted**
  Review breadth (`panel` = the tier baseline; a coordinator WP is by
  definition `panel` — `self`/`light` WPs never qualify for a
  coordinator), reviewing the **WP diff**, never the coordinator's
  summary prose
  ([`protocol.md`](../hex-core/references/protocol.md#the-review-fix-loop)).
- **Swarm** (feature branch → trunk) — `/hex-review`'s staged panel,
  unchanged.

## Constraints

- Every phase gates on the project's documented verification — never
  complete a phase without it passing.
- Never leave work uncommitted at the end of a completed phase or work
  package.
- Never exceed the concurrency cap
  ([`protocol.md`](../hex-core/references/protocol.md#worker-coordination)).
- **Never push to remote.**
- Stub and Specify never run concurrently — sequential only, each depends on
  the prior phase's output.
- **No mid-flow questions** — ambiguity is resolved at the single gate; a
  scope surprise mid-execution stops and re-routes to a higher tier rather
  than silently upgrading.
- Always validate the working tree shows only the intended diff before each
  commit.
- Always update the plan's design record before adding a test for a behavior
  the plan didn't specify — never invent a requirement.
- **Upkeep**
  ([`protocol.md`](../hex-core/references/protocol.md#upkeep-step)): as the
  final phase, re-point any `hex.md › Pointers` entry this run revealed as
  drifted (a changed verification command, a new worktree location), and
  update `hex.md › Memory` with anything worth persisting (e.g. a review
  perspective that mattered).

## Handoff

The [handoff contract](../hex-core/references/protocol.md#handoff-contract)
applies: this block is the run's required final message; one optional
proceed question may follow it.

```markdown
## Execution Complete: <feature | plan name>

### Classification
- Tier: low | medium | high
- Overlays: review=<minimal|full|adversarial>, loop-rounds=<1|2|3>, adversary=<on|off>

### Artifacts
- <plan path> (Status block advanced to `review`)
- <commit(s) on the feature branch>

### Deferred findings (need human judgment)
- Review-Fix Loop: …
- Cross-model review: …

### Next step
    /hex-review <plan path or branch>
```

**Federation — a plan carrying a `Repo` column.** The handoff additionally
enumerates the per-repo feature branches in required landing order and names the
window in which the satellites do not build against lead trunk (C-312); hex
never pushes and records no landing it did not observe locally. It also lists
the **uncommitted `Federation lead:` back-pointer files** written into each
satellite's main checkout (C-308) for the human to commit — until then the FM6
guard is machine-local.

```
Feature branches to land, in this order:
  1. acme-sh/acme          hex/acme-lib-v050
  2. acme-sh/acme-mirror   hex/acme-lib-v050
  3. acme-sh/acme-mcp      hex/acme-lib-v050
Between 1 and 2 the satellites do not build against acme trunk.

Uncommitted back-pointers to commit (working-tree change, not committed by hex):
  ../acme-mirror/.agents/memory/hex.md
  ../acme-mcp/.agents/memory/hex.md
```

Consumers: `/hex-review` (the plan artifact and branch diff); the human
(deferred findings).

$ARGUMENTS
