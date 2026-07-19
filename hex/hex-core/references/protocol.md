# hex Swarm Protocol

The shared vocabulary and contracts for every hex orchestrator. Roles are
defined in [`workers.md`](workers.md); model classes in
[`models.md`](models.md); the memory file in [`memory.md`](memory.md).

## Shared shape

Every orchestrator runs the same outer loop:

> parse args → classify tier → resolve overlays → **single meta-plan
> approval gate** (never mid-flow questions) → announce the resolved config
> with per-axis source attribution → dispatch to the tier's phases.

Each skill ships this as a `SKILL.md` dispatcher plus `classify.md`,
`overlays.md`, and `tier-{low,medium,high}.md` files.

## Tier grammar

Three tiers plus `auto`:

| Tier | Intent | Typical spawns | Gate depth |
|---|---|---|---|
| `low` | Two-way door: flag/option change, doc edit, ≤3 files, one area | 1 explorer; inline design; 1 reviewer, single pass | 1 approval; 1 review round; no adversary |
| `medium` | One-way-door medium: new command, new storage/index layout, 1–2 areas | architecture-explorer + 2–4 explorers; 1 researcher; architect; review panel | 1 approval; up to 3 review rounds; adversary on one-way-door signals |
| `high` | One-way-door high: new module/package, breaking API, cross-area, protocol change | medium set + mandatory architect, mandatory multi-axis research | 1 approval; up to 3 rounds; adversary a default part of the flow |
| `auto` (default) | Classifier picks low / medium / high from signals | — | — |

`auto` is the default; the classifier resolves it to one of the three real
tiers and shows its reasoning at the gate.

Tier **vocabulary** is fixed to the row above: `low` / `medium` / `high`
plus `auto`. Only tier **content** — a tier's phase counts and inherited
baseline — is project-redefinable, via the `tiers` key
([`config.md`](config.md#tiers)).

**Reserved tiers.** `xhigh` and `max` are reserved for future overlay
stacks. The classifier **never emits them.** If a user explicitly passes a
reserved tier, announce "`<tier>` reserved, running high" and run `high`.

## Overlay grammar

Overlays are single-axis modifiers layered on the resolved tier — each
adjusts exactly one axis (for example: research depth, force/skip the
adversary pass, the architect's model). Overlays stack. A user-supplied
overlay always overrides the classifier-inferred value for that axis. The
concrete axes are defined per skill in that skill's `overlays.md`; this
file defines only the grammar.

## The meta-plan approval gate

Exactly **one** approval point, before any work starts. The orchestrator
never asks mid-flow questions — ambiguity is resolved here or by a
documented default, never by interrupting a running swarm. **This
single-gate rule scopes to the four orchestrators** (`hex-plan`,
`hex-execute`, `hex-review`, `hex-architect`); `/hex-init` is a
configuration wizard, not an orchestrator, and is exempt — an exemption
that does not extend to any skill that spawns workers.

The gate announces the fully resolved config, each item attributed to its
source (`classifier` / `hex.md preference` / `user flag` / `tier baseline`):

```
Tier: medium            (auto — classifier: new subcommand, 2 areas)
Overlays: research=3     (user flag)
          adversary=on   (hex.md preference: one-way-door signals)
Spawn set:
  architecture-explorer  (tier baseline)
  explorer ×3            (tier baseline)
  researcher ×3          (overlay research=3)
  architect              (tier baseline)
  reviewer: quality, security, spec   (tier baseline + hex.md preference: src/auth/**)
Models: <fast-balanced model> default; architect + reviewer:security →
        <deep-reasoning model> (hex.md preference instantiated — see models.md)
Adversary: codex-adversary, plan-artifact scope   (hex.md preference)
Limits: workers 8 · loop rounds 3   (shipped 8 / tier default — a stored limit or a batched phase shows here with its source)
Degraded: no — subagent spawning available
```

The `Limits:` line appears at every orchestrator's gate whenever a
`hex.md › Preferences` limit is in force **or** a phase's resolved set
exceeds the effective worker cap (a batched phase — see [Worker
coordination](#worker-coordination)); it is omitted only when neither
applies and the shipped defaults run unmodified.

**Federation announce block.** When a plan carries a `Repo` column, the gate
gains one block **immediately after the `Degraded:` line**, in the same
`<label>: <resolved value> (<source>)` shape:

```
Federation: lead `.` + mirror, mcp — 3 repos, 4 WPs (2 satellite)
            ../acme-mirror on `feat/pypi-mirror` — unrelated in-flight work
            back-pointer to be written in: mirror, mcp   (hex.md Pointers)
```

Line 1 is mandatory (the lead, every distinct `Repo` value in table order,
then repo / WP / satellite-WP counts). Line 2 appears once per satellite found
on a non-trunk branch (C-304). Line 3 appears only when a back-pointer will be
written that does not already exist — the C-308 disclosure at the **existing**
gate, never a second gate. The C-303 pre-flight echo lines sit under this block
at execution. Absent a `Repo` column the whole block is absent and every other
line is unchanged. (C-315)

**Config-disclosure lines.** When a `hex.md › Preferences` config block
changes what the run does, the announce block prints one disclosure line per
change — this is the single statement of the trigger set; the four
orchestrator SKILL.md announce steps show a per-skill example and link here,
never restate it:

- `tiers` amended the layer-1 baseline → one `[project-redefined:
  <phase>.<role> <shipped>→<resolved>]` line per delta, **printed even when
  the resolved value equals the shipped one** (e.g. an `inherits` that happens
  to match). An amendment with no printed line is a spec violation, the same
  standard [`models.md`](models.md#rules) sets for a silent escalation.
- a preference-added spawn was displaced at the phase ceiling → one
  `[<role> dropped — phase ceiling N reached]` per drop
  ([`config.md`](config.md#merge-rules) rule 6).
- a reduced concurrency cap batched a phase → one
  `[<phase> batched N+M — concurrency cap C (hex.md)]`.
- a `never: [reviewer:security]` suppression failed closed → the
  `Error:` / `Fix:` refusal pair ([`config.md`](config.md#merge-rules) rule 5).

See [`config.md`](config.md#tiers).

(`codex-adversary` is only an example value — the adversary skill name
always comes from `hex.md › Preferences`; see the
[adversary contract](#adversary-contract).)

**Models line contract.** Shipped files name only capability classes and
placeholders; the **running orchestrator resolves each class to the
literal model** ([`models.md`](models.md) resolution order) and the
announce block prints the resolved literal per spawn, with every
escalation above a matrix cell carrying its announced reason — a silent
escalation is a spec violation ([`models.md`](models.md#rules)).

The user approves, adjusts, or cancels. On a client with native
plan-approval, use it; otherwise present the block as a single structured
question. The gate is also where the user can add or drop perspectives and
choose research axes.

Open questions travel with recommendations: every
`[NEEDS CLARIFICATION: <question>]` marker in the target or draft
artifacts carries a `Recommended: <answer> — <reason>` line, and the gate
presents each question together with its recommendation. A plain approval
accepts every recommendation as-is — the user spends attention only on
the ones they want to change. The hard cap of 3 open markers per artifact
is unchanged.

## Spawn-selection precedence

Three inputs decide which workers and perspectives run; later wins:

1. **Shipped tier baseline** — the tier file's default perspective set,
   with roles from [`workers.md`](workers.md) and class defaults from
   [`models.md`](models.md).
2. **Project hints** — the Preferences section of
   `.agents/memory/hex.md`: always-on perspectives, research axes,
   path-triggered escalations, model overrides. The classifier folds these
   into its suggestion.
3. **User, at the gate** — the single approval point offers perspective and
   researcher selection; non-interactive flags override.

Skills never hardcode a spawn list beyond the tier baseline. The announce
block always shows the resolved set with per-item source.

`tiers` (and, in v2, `workflows`) do not add a fourth input — they
**rewrite layer 1** before layers 2 and 3 above apply
([`config.md`](config.md#merge-rules)).

**Persona loading.** The orchestrator always reads the
[`workers.md`](workers.md) index; it loads a full persona file
(`workers/<role>.md`, or a project-local `.agents/workers/<role>.md`)
**only for roles in the resolved spawn set** — never the whole registry.
Project-local personas fold in as project hints (layer 2 above) and never
override a shipped role of the same name.

## The Review-Fix Loop

The canonical contract-first loop. **This is the only copy in the bundle —
every other file links here.** Diff-scoped, bounded, tier-scaled.

**Contract-first TDD phases:**

1. **Stub** — a builder (focus `stub`) creates the public surface; gate on
   the project's compile/type check.
2. **Specify** — a tester (focus `specification`) writes tests from the
   design record; they MUST fail against the stubs.
3. **Implement** — a builder (focus `implement`) fills bodies until the
   tests pass; run the project's documented verification for changed files.
   **Carve-out for a leaf under a coordinator:** it runs a scoped
   compile/parse check only — concurrent full verification in the
   coordinator's shared worktree would race on shared build artifacts — and
   the coordinator runs the one authoritative verification at the WP join.
4. **Review-Fix** — the loop below.

**The loop:**

- **Round 1** — run every tier-selected perspective on the diff,
  concurrently. Perspectives most likely to find blockers go first (spec,
  correctness). Classify each finding:
  - **Actionable** — a builder fixes it; re-run only the affected
    perspectives next round.
  - **Deferred** — surface it in the summary with context; never block the
    loop on it.
- **Subsequent rounds** — re-run only the perspectives with actionable
  findings from the prior round. A finding that surfaces two rounds running
  (oscillating) auto-defers.
- **Loop cap** — scales with tier and **scope**. Code-diff scope: 1 round
  at `low`, up to 3 at `medium` and `high`. **Plan-artifact scope** (a
  draft plan or ADR under review by its own orchestrator): **one** panel
  round → the orchestrator applies actionable fixes → **one** re-validation
  pass by `reviewer` (focus `spec`) *whenever any actionable fix was
  applied* (skipped only on a clean panel) → anything still actionable
  escalates to the user. Artifacts are re-checked downstream anyway
  (Specify and Verify-Architecture gates), so multi-round artifact loops
  buy little; re-enabling them takes an **explicit** `artifact loop
  rounds: N` limit in `hex.md › Preferences` — the generic loop-rounds
  ceiling does not. If actionable findings remain when a cap
  is hit, **stop and escalate to the user** with the outstanding list —
  do not loop past the cap.
- **A `loop rounds` value in `hex.md › Preferences` is a ceiling, never a
  default and never a raise.** It caps the code-diff scope's per-tier round
  count *and* any `--loop-rounds` flag: the effective cap is the **lower of
  the stored value and the run's resolved request** — `--loop-rounds` when
  passed, the tier default otherwise. The stored value never raises the tier
  default and never lifts `low` above 1 round; a `--loop-rounds` flag may
  still loosen a run up to (never past) the stored ceiling. `limits.*` sit
  **outside** the later-wins [spawn-selection
  precedence](#spawn-selection-precedence) — a user flag may lower a limit,
  never raise it past the stored ceiling. The stored value never affects
  plan-artifact scope — that scope moves only via the explicit `artifact
  loop rounds: N` limit named above. Both limits are announced at the gate
  with their source, like every other resolved axis.
- **Per-WP review budget** — when the plan's Parallelization table carries
  a `Review` column, it scales this loop per work package:
  - `self` — **no reviewer spawns in this loop, and the WP skips the
    Verify-Architecture reviewer**: the builder's self-check
    ([`workers.md`](workers.md) universal rule 7) plus the project's
    documented verification are the only WP-level checks. A `self` WP is
    deliberately un-reviewed at the WP level — which makes the
    branch-level `/hex-review` pass **mandatory before the feature branch
    lands on the trunk** for any plan containing one; the execution
    handoff records it.
  - `light` — one `reviewer` (focus `spec`, phase `post-implementation`),
    one round.
  - `panel` — the tier's full Round-1 set and round cap (the ceiling).

  The budget only **lowers** breadth below the tier baseline, never raises
  it. A missing column or cell means `panel` — pre-budget plans run
  unchanged.
- **Adversary gate** (optional, tier-scaled) — after the loop converges,
  one cross-model pass on the diff; see [Adversary contract](#adversary-contract).
  One-shot, never loops.
- **Exit gate** — no actionable findings remain, the project's documented
  verification passes on the final state, and deferred findings are
  documented for handoff.

## Worker coordination

The orchestrator decomposes work, dispatches workers using the
spawn-prompt templates in [`workers.md`](workers.md), and synthesizes their
structured returns. Workers never share state, and never spawn workers —
with one bounded exception: a `coordinator` (spawned by the orchestrator for
a qualifying work package) fans out exactly one level of leaf workers within
its work package. Leaves never spawn. The depth chain is fixed at
orchestrator → coordinator → leaf and is **hex-enforced** — the spawn
prompts bound it, not the harness (harness nesting caps vary, and one is
unbounded). One level because hex enforces it uniformly and because spawn
cost and error amplification compound per level: a second level of fan-out
rarely clears the granularity gate.

- **Concurrency cap: at most 8 workers at once.** Dispatch a concurrent
  batch in a single step. Keep prompts focused for fast startup. The cap
  counts **recursively** — leaves running inside a coordinator count toward
  it — so the orchestrator hands each coordinator a **fan-out budget** no
  larger than its slot's share, keeping the recursive total within the cap.
- **A `max-workers` value in `hex.md › Preferences` lowers the cap and
  never raises it**: the effective cap is `min(8, max-workers)`, counted
  recursively like the shipped 8. A value above 8 is honored as 8 and
  announced as clamped. The cap bounds **how many workers run at once, not
  how many a phase spawns** — a phase whose resolved set exceeds the
  effective cap runs in **sequential batches of at most the cap, in
  declaration order**, and the phase gate holds until the last batch returns
  (the same cap bounds WP launch — [Parallel-by-default
  decomposition](#parallel-by-default-decomposition)); it never silently
  drops a perspective the tier baseline calls for, and it announces the
  batch split and the cap's source. **Federated (a plan carrying a `Repo`
  column):** this cap counts **across all participating repos**, and the
  **lead's** `max-workers` is the only one read — a satellite's `hex.md` is
  never resolved (C-318, [`memory.md`](memory.md)), so the effective cap
  stays `min(8, lead's max-workers)`.
- **The phase ceiling is a separate limit from the cap above** — it
  bounds what preference-added spawns (`always` entries, `counts` above
  baseline) may add to a phase. Its displacement procedure is defined
  once, in [`config.md` § Merge rules, rule 6](config.md#merge-rules).
- Workers return structured results; the orchestrator does the synthesis —
  it never dumps raw worker output onward.
- **Federation adds no recursion level (C-319).** The orchestrator that owns
  a federated plan is *the* orchestrator; it drives satellites with `git -C`
  and ordinary leaf workers and **never spawns a per-repo `/hex-execute`** —
  that would put an orchestrator under an orchestrator and break the fixed
  `orchestrator → coordinator → leaf` chain. A `coordinator` may own a
  satellite WP under its unchanged gate, with sub-WPs in the parent's repo;
  the join hierarchy stays three levels. Vacuous without a `Repo` column.

**Degraded mode (no subagent spawning).** On a client that cannot spawn
subagents, the orchestrator runs each worker prompt block **inline, one at
a time**, in the same session — same perspectives, same contracts,
sequential instead of concurrent. Announce it at the gate as
`Degraded: inline workers — no subagent spawning`.

**Degraded mode (no per-spawn model override).** On a harness where all
agents in a session share one model (e.g. Copilot), the per-role matrix is
**advisory only** — every worker runs the session model. Announce at the
gate as `Degraded: single session model — no per-spawn override; matrix
advisory`, naming the one resolved literal all spawns will run.
Escalation recommendations (e.g. `reviewer:security →
deep-reasoning`) are still *shown* so the user sees what would escalate,
but they are not independently routable.

**Fan-out mechanism (coordinator recursion).** Two capabilities are detected
per run — **never stored** — and gated on the **capability class, not the
primitive name** (the harness surface churns). At Schedule time the
orchestrator picks the coordinator's fan-out mechanism:

1. **`programmatic orchestration`** available → the **preferred** mechanism:
   coordinators fan out via orchestration primitives inside the WP's single
   worktree (no sub-refs).
2. else **`nested subagent spawning`** available → the **fallback**:
   coordinators fan out via nested subagent spawns (watch session budget and
   ref collision; isolation only for true-isolation sub-WPs).
3. else **degraded flattening**: no coordinators — every WP runs a single
   builder plus the normal per-WP panel. Announce:

```
Degraded: flat execution — no nested spawn; coordinators inlined
```

This stacks with the other degraded lines; a harness with neither nesting
nor per-spawn override announces both:

```
Degraded: flat execution — no nested spawn; coordinators inlined
Degraded: single session model — no per-spawn override; matrix advisory
```

Capability is **detected per run and announced, never stored** — same
pattern as the existing subagent-spawn gate. **Axes compose:** each gated
capability contributes its own `Degraded:` line; a harness lacking both
subagent spawning and per-spawn override prints both (inline workers *and*
single session model). The gate stacks one line per degraded axis rather
than defining a combined state.

## Parallel-by-default decomposition

Plans are decomposed to **maximize parallel execution** — sequential is
the exception, not the default shape:

- **Decompose by structural boundary** (a directory, module, package, or
  data-model boundary), never by user-facing feature slice — two slices
  that touch the same file from different angles cannot parallelize.
- **Every WP declares its expected file set at planning time.** Parallel
  eligibility is a plan-time set-intersection check, not a merge-time
  discovery: two WPs may share a wave only if their file sets are
  disjoint. Two tasks that need the same file become sequential steps of
  **one** WP — never two parallel WPs. **When the plan carries a `Repo`
  column** the comparison is over `(Repo, path)` pairs, not bare paths
  (C-316) — satellites routinely declare textually identical repo-relative
  paths that are disjoint across repos; with no `Repo` column every pair is
  `(., p)` and the check is byte-for-byte as before (same key, worktree side:
  [Worktree work-package mechanics](#worktree-work-package-mechanics)).
- **Every WP declares its review budget at planning time.** The
  Parallelization table's `Review` column holds `self | light | panel`,
  assigned when the WP is cut: docs-only or tiny low-risk work (~≤50
  expected lines, no security-sensitive or hot-path files) → `self`;
  a single-area moderate change → `light`; large, cross-area, security-
  or hot-path-touching work → `panel`. Consumed by the
  [Review-Fix Loop](#the-review-fix-loop); a sub-WP inherits its parent's
  budget when absent; a missing column means `panel`. **Budgets are
  re-validated at merge time**: alongside the merge-time file-set
  re-validation, a WP whose actual diff outgrew its budget class (size
  well past the `self` heuristic, or any security-/hot-path file touched)
  escalates to the next budget and its review re-runs at that breadth
  before the merge — a plan-time estimate never caps review of what was
  actually built.
- **The counterweight: no WP below its own overhead.** Every WP pays a
  fixed cost — worktree, stub/specify/implement spawns, review, merge,
  verification. A WP whose whole scope is a single trivial concern (~≤50
  expected lines) **folds into its nearest sibling as sequential steps**;
  keeping it isolated needs a one-line justification, checked by the plan
  review. Maximize parallelism *between* right-sized WPs — never by
  slicing below the overhead floor.
- **Launch on dependency-ready; waves are a derived reporting view.** Waves
  stay computed — a WP is in wave N iff every WP it depends on sits in an
  earlier wave and N is minimal (topological levels), wave 1 = no
  dependencies — but a wave is a **derived reporting view**, shown in the
  table and the mermaid index for readability, never a launch gate. A WP
  becomes eligible the instant every WP in its `Depends-on` has Status
  `merged` — not when its whole wave is ready. The orchestrator maintains a
  **ready-set** and launches eligible WPs immediately, within the
  concurrency cap, recomputing on every merge. The ready-set is ordered
  **critical-path-first** (longest remaining dependency chain first), so a
  shallow WP never starves the critical path (marked in the plan). The
  concurrency cap still bounds fan-out
  ([Worker coordination](#worker-coordination)) — when the ready-set is
  wider than the cap allows, launch in ready-order batches. Merge stays
  serialized in a valid topological order — the DAG changes launch timing,
  not merge discipline. A linear or all-wave-1 plan schedules identically to
  the old barrier — its ready-set equals wave membership — so it is
  backward compatible.
- **Progress surface** — with no wave barrier, surface live state from the
  Status column (the data is already there): a compact rollup line per
  coordinator (e.g. `WP3 [coordinator]: 2/4 sub-WPs merged`), and a WP left
  `active` far beyond its peers carries a **staleness flag**, so a hung WP no
  longer blocks anything visibly. Surface only — never speculative
  re-execution.
- **The critical path** — the longest dependency chain — is identified
  and marked; it bounds wall-clock time no matter how wide the waves are.
- **Under-parallelization is justified, never silent**: a decomposition
  with fewer parallel WPs than its file-disjointness allows carries a
  one-line justification in the plan's Parallelization section.

## Traceability IDs

Plans and specs number their requirements so coverage is a mechanical
check, not a prose judgment:

- **Component contracts are numbered `C-001, C-002, …`; UX scenarios
  `S-001, S-002, …`** — assigned when the artifact is written (in the
  spec when one exists, carried into the plan unchanged), stable within
  the artifact, never renumbered.
- **Every ID maps to at least one WP and at least one test**: the
  Parallelization table's Scope column cites the IDs a WP delivers, and
  every Specify-phase test names the IDs it covers.
- **Coverage is checked at three gates**: the plan review
  (`reviewer:spec` — an ID with no covering WP or no covering test is an
  actionable finding), the Specify gate in execution (every ID has at
  least one failing test before Implement), and the convergence check in
  review ([Convergence contract](#convergence-contract) — one gap per
  unmet ID).

IDs are the join key convergence uses to name gaps; a requirement cannot
drift silently once it carries one. The same IDs key the **spec fold-back**
delta grammar (`ADDED`/`MODIFIED`/`REMOVED`) — see
[`archive.md`](archive.md#delta-grammar).

## Finding severity

The shared severity vocabulary for review findings. **This is the only copy
in the bundle — reviewer.md, the hex-review verdict and RCA rules,
overlays.md, and the tier files link here, never restate it.** Severity is
assigned by the worker that raises the finding (the orchestrator synthesises,
it never invents a grade).

Severity is orthogonal to a finding's actionable/deferred class: class says
who fixes it, severity says how bad it is; every finding carries one of each.
The floor is a floor, not a ceiling — a consumer's own rule may raise a
finding above the label's floor.

| Severity | What it is | Verdict floor |
|---|---|---|
| Block   | Merge-unsafe: correctness, security, data-loss, or contract break. | Request Changes |
| High    | A real defect that should not merge unfixed, not unsafe on its own. | Needs Work |
| Warn    | A minor defect or smell — naming, small duplication, a narrow edge case. | Needs Work |
| Suggest | An optional improvement; no defect. | none — reported, but never gates the verdict |

Medium/high construct: at tier low the ladder is not applied — a low finding
carries only its class, the tag is absent, and the low verdict runs off its
enumerated triggers. Presence of the tag is the signal that a run graded
severity; there is no schema-version marker.

One defect, highest severity wins: when more than one perspective reports the
same file:line defect it is one finding at the highest severity any
perspective gave it — no averaging. A panel Warn the cross-model pass raises
to Block resolves to Block; the escalation is already visible in the
Cross-Model section it was reported in.

Producer-local grades fold in here: doc-reviewer keeps emitting
Critical / Medium / Accuracy; the orchestrator maps them at synthesis —
Critical → High, Medium → Warn, Accuracy → Block (a doc now wrong about
shipped behavior is a contract defect). No producer defines a fifth level.

Nothing to report → no findings lines, just the verdict — the same
byte-identical-when-clean rule as the Convergence contract.

## Worktree work-package mechanics

Every plan integrates through **one feature branch**; each **work package
(WP)** runs on its own ephemeral branch in its own worktree:

- **One feature branch per plan** — the integration target for every WP.
  Resolve it once, at execution start: the non-trunk branch already
  checked out, else create `hex/<plan-slug>` from the trunk. Its tip at
  that moment is the **frozen base** every wave-1 WP branches from — never
  a moving baseline.
- **One ephemeral branch + worktree per WP** — branch
  `hex/<plan-slug>--<wp-slug>` (hyphenated, not `hex/<plan-slug>/<wp-slug>`:
  git refs are paths, so the feature branch `hex/<plan-slug>` cannot also be
  a ref *directory* holding a `<wp-slug>` child — a branch cannot be both a
  ref and a ref-directory), worktree `.agents/worktrees/<wp-slug>/`
  (the default; a deviation location is documented in project context
  (cached in `hex.md › Pointers`) — it describes repo layout, not hex
  behavior, so any bundle that spawns worktrees reads the same source). A
  launching WP bases on the **current feature-branch tip** — by serialized
  integration it already holds every merged dependency; wave-1 WPs base on
  the frozen initial tip. Basing on a
  dependency WP's tip instead is the never-taken pipelining option:
  dependency-ready launch requires every dep `merged` (already on the
  feature branch), so that clause would only apply to an *unmerged*
  dependency — documented, unused.
- Concurrently-running WPs **must own disjoint file sets** — never two WPs
  on the same file.
- **Merge back onto the feature branch, serialized, in a valid topological
  order** — one WP at a time, never a batch: each merge changes the base
  under the next.
  Run the project's documented verification **after every merge** —
  cross-file interactions surface only post-merge.
- **Merge-time file-set re-validation** — before merging a WP, run
  `git diff --name-only <base>..<wp-branch>` (`<base>` is that WP's
  recorded base — the feature-branch tip it launched from, the frozen
  initial tip for wave-1 WPs, never the trunk) and require every listed
  file to sit inside the
  WP's declared file set. Anything outside → do not merge; reconcile
  first: justify the extra files in the plan's table, or re-scope the
  WP.
- **Merge conflict / post-merge failure playbook** — on a merge conflict
  or a failed post-merge verification, the orchestrator judges the
  collision semantically (a real design conflict versus a textual
  overlap), applies at most **one** fix pass on the feature branch, and
  re-verifies. Still failing → halt the wave, mark the WP `failed` in
  the plan's table, and escalate to the user with a state summary.
  Never loop past the one pass, never force-push, never rebase a
  published ephemeral branch.
- **Delete the ephemeral branch and remove the worktree after its WP
  merges.** The feature branch is what survives; landing it on the trunk
  is the human's step (their PR or merge flow) — hex never pushes.
- **The plan table's Status column is the WP-level state of record**
  (`pending | active | merged | failed`): execution sets `active` when a
  WP's worktree is created, `merged` after its merge, `failed` per the
  playbook. Branches and worktrees are only its evidence — resume reads
  the column, not the refs.
- **Sub-WP rows (dotted IDs)** — a coordinator splits its WP into dotted
  sub-WPs (`WP3.1`, `WP3.2`, …) that are **ordinary table rows** — same
  columns, same four statuses. **Only leaf rows are branch- and
  worktree-eligible**; a parent with children is never itself branched. The
  default for sub-WPs is the parent WP's **single shared worktree, with no
  sub-branches**; a hyphenated leaf branch `hex/<plan>--<wp>--<sub>` (never a
  slash path) is created **only for a declared true-isolation need**. A
  sub-WP's `Depends-on` inherits the parent's when absent (override for a
  tighter edge). IDs are never renumbered — next sibling = next integer,
  append-only — and there is **no schema-version marker**: the presence of
  dotted IDs is the signal.
- **Parent Status is a computed rollup, never written directly** —
  recomputed on every child write: **failed** if any child failed;
  **merged** iff every child is merged *and* the parent's join check passes;
  **active** once any child has started (is active or merged); else
  **pending**. Genuine join work (more than the sum of the children) is an
  **ordinary sibling sub-WP row** that depends on the other children — no
  fifth status, no `.join` suffix. A parent with zero children (every old
  plan) rolls up to its own literal status — the rule is vacuous, old plans
  unchanged.

Ignore `.agents/worktrees/` specifically (transient checkouts); never
ignore `.agents/` wholesale — `.agents/memory/hex.md` is shared
memory (see [`memory.md`](memory.md)).

**Federation — a plan carrying a `Repo` column.** Everything above is
per repo; a federated plan spans the lead (`.`) and one or more satellite
repos named by the lead's `Federation:` pointers
([`memory.md`](memory.md#the-three-sections)). Absent a `Repo` column every
clause below is inert and single-repo behaviour is byte-identical.

- **`Repo` column (C-302)** — the plan table's second column names the repo
  each WP runs in: a Federation key, or `.` (the empty-cell default) for the
  lead. `Expected Files` are **repo-relative to that repo**, because
  merge-time re-validation runs `git -C <repo> diff --name-only`. Sub-WPs
  inherit the parent's `Repo` and never name a different repo than the parent
  (only leaf rows are worktree-eligible, so a cross-repo split is at WP
  grain). No schema-version marker — the column's presence is the signal.
- **Pre-flight access invariant (C-303)** — no cross-repo mutation (branch,
  worktree, commit, back-pointer) occurs until, for **every** Federation key
  the plan uses, six halting clauses pass. It is a **barrier over all keys,
  not a per-repo gate**: a partially accessible or partially writable cluster
  produces zero writes.
  - (i) `git -C <path> rev-parse --show-toplevel` **must equal `<path>`** —
    `git -C` walks *up*, so a non-repo path nested in another repo silently
    reports the enclosing repo (the one clause here whose omission is silent).
  - (ii) `git -C <path> rev-parse --path-format=absolute --git-common-dir`
    **must differ from the lead's** — equality means `<path>` is another
    *worktree of the lead*, not a separate repo.
  - (iii) `git -C <path> status --porcelain` must succeed (hex's own
    uncommitted back-pointer never counts as blocking).
  - (iv) a **non-destructive write probe** must succeed — a zero-byte file
    created and removed under `<path>/.agents/`, plus
    `update-ref refs/hex/write-probe HEAD` created and deleted — because
    (i)–(iii) prove readability only and every federated write comes later.
  - (v) the repo's trunk must resolve, per C-304's discovery order.
  - (vi) `git -C <path> check-ignore -q .agents/worktrees/` must succeed — a
    satellite may never have run `/hex-init` (exempt there), so nothing
    guarantees the path is ignored; on a miss, halt and offer to add
    `.agents/worktrees/` (never `.agents/` wholesale).

  Any failure **halts** with an `Error:`/`Fix:` pair carrying a pasteable
  `--add-dir` relaunch line — never degrade, never skip a repo. The outputs
  are **echoed per key** into the announce block so clause (i) is auditable.
  The step-by-step procedure is `/hex-execute`'s (Dispatch step 1) and
  cross-references this invariant; C-305 and C-306 depend on it.
- **Shared-slug branch rule (C-304)** — `<plan-slug>` is the git-level join
  key and is **identical in every participating repo**. The lead resolves its
  feature branch unchanged (above). A **satellite always creates
  `hex/<plan-slug>` from its own trunk, never from a checked-out non-trunk
  branch** — the checked-out-branch clause is suspended for satellites; a
  satellite found on a non-trunk branch is announced at the gate as unrelated
  in-flight work. **Trunk is discovered, never assumed to be `main`**, in the
  C-303 pre-flight, in order: (1)
  `git -C <path> symbolic-ref --short refs/remotes/origin/HEAD`, stripping
  the remote prefix, authoritative when present; (2) else the trunk documented
  in that repo's **project context**, read explicitly (C-318 forbids reading
  its swarm memory); (3) else **halt and ask**, naming the repo. Whatever (1)
  or (2) yields must exist as a local ref
  (`git -C <path> rev-parse --verify refs/heads/<trunk>`) or the same halt
  fires. The resolved trunk and its source are echoed in the pre-flight line.
- **Satellite worktree mechanics (C-305)** —
  `git -C <path> branch hex/<plan-slug> <base>` (the frozen base SHA from the
  plan's `Repos:` ledger, C-317/C-324 — never a branch name), then
  `git -C <path> worktree add .agents/worktrees/<wp-slug> hex/<plan-slug>--<wp-slug>`.
  The worktree lives under the **satellite's** own `.agents/worktrees/` — the
  owning repo records the checkout and already gitignores that path. Removal
  and branch delete after merge, as today. hex never fetches.
- **Merge serialization spans repos (C-306)** — **one global topological
  order over all WP rows regardless of repo, one merge in flight at a time.**
  *Correctness* needs only two things: per-repo serialization (unchanged —
  each merge moves the base under the next) and `Depends on` ordering wherever
  an edge crosses the boundary (the DAG already enforces it); two WPs in
  different repos with no edge between them have no correctness order. **Global
  one-at-a-time is an operability choice** — one sequential orchestrator, one
  halt-capable verification at a time, resume reconstructible from the Status
  column — and is the first rule to relax if merge wall-clock ever dominates.
  Each merge is `git -C <repo> merge` onto that repo's `hex/<plan-slug>`,
  followed by the **owning repo's** documented verification read by an
  **explicit `Read`** of that repo's project context (never ambient —
  `--add-dir` does not load a satellite's `CLAUDE.md`). Cross-repo
  `Depends on` edges are ordinary; the ready-set launcher and the merge
  playbook are unchanged; the concurrency cap counts across repos.
- **`Hex-Plan:` commit trailer (C-307)** — every commit hex makes in a
  satellite carries `Hex-Plan: <remote-slug>:<repo-relative plan path>` in the
  trailer block. Ordinary git-trailer syntax, no new format,
  `git interpret-trailers`-compatible, recoverable via
  `git -C <repo> log --grep`. The WP is derivable from the ephemeral branch
  name, not the trailer. This is the only satellite-side record of the plan —
  there is never a plan copy. Lead commits do not need it but may carry it
  harmlessly.
- **`(Repo, path)` disjointness key (C-316)** — the concurrent-WP invariant
  above ("disjoint file sets") compares **`(Repo, path)` pairs**, not bare
  paths: `Expected Files` are repo-relative, so satellites routinely declare
  textually identical paths (`Cargo.toml`, `src/**`) that are nonetheless
  disjoint across repos — FM5's free parallelism. Merge-time re-validation is
  unchanged and already repo-scoped (`git -C <repo> diff --name-only` against
  that WP's satellite-relative set). Vacuous single-repo: every pair is
  `(., p)`. The plan-time set-intersection check states the same key — see
  [Parallel-by-default decomposition](#parallel-by-default-decomposition).
- **One frozen base per participating repo (C-317)** — the frozen-base rule
  above is per feature branch, and C-304 gives a federated plan one feature
  branch per repo, so there are **N frozen bases**, one per participating
  repo, **all resolved together in the C-303 pre-gate step** — never lazily at
  first touch, which would branch a wave-1 satellite WP from a moving
  baseline. Each is **persisted as a full 40-character SHA in the plan's
  `Repos:` ledger** (C-324) so resume, review, merge-time re-validation and
  convergence all read the same `<base>` rather than re-resolving a trunk ref
  that may have moved. A WP's base is its own repo's row.

## Verification

**hex never defines how to verify a project.** Every gate above that says
"verify" means: run the project's documented verification, discovered from
project context (cached in `hex.md › Pointers`; verify the pointer on
consumption and re-detect on a miss). If none is documented, detect a
reasonable command **once** for this run and suggest `/hex-init` to persist
it — do not hardcode a command or re-guess it every phase.

**Federation — a plan carrying a `Repo` column.** "The project's documented
verification" means the **owning repo's**, read by an explicit `Read` of that
repo's project context — never a cross-repo aggregate, because no single
command spans a cluster and hex defines none (C-321). Tier gates worded
"across the whole workspace" mean the workspace of the repo the gate runs in.
The genuinely cross-repo check is a **mandatory integration WP** (one per plan,
depending on every satellite WP it joins) whose command is authored **inline in
the plan's Implementation Steps** (C-311), because it belongs to no repo and no
pointer resolves it; its shape is a **per-repo table** — one row per
participating repo (the lead plus every distinct `Repo` value), each naming the
exact state that repo must be at and the command proving it, each reported
pass/fail independently (an aggregate "integration green", a missing row, or
running the command only in the lead does not satisfy it). There is no implicit
federated verify gate.

## Constitution gate

An opt-in governance check. Active only when project context names a
constitution / governing-principles location (cached in
`hex.md › Pointers`, [`memory.md`](memory.md)). hex never ships a
constitution of its own, and an absent pointer skips the gate silently —
no output, no empty table.

When the pointer is set:

- **hex-plan's Design and Review phases check the plan against it.**
  Every violation requires a row in the plan's **Constitution
  deviations** table — `Violation | Why needed | Simpler alternative
  rejected because` — present only when at least one violation exists.
- **An unjustified violation is an automatic Request Changes in
  review.** A principle changes only through the project's own
  governance flow — never diluted or reinterpreted by an orchestrator.

**Federation — a plan carrying a `Repo` column.** The plan is the **lead's**
artifact, so the **lead's** constitution pointer governs it and its
`Constitution deviations` table, unchanged. A satellite's own constitution is
**never merged in** — merging governance documents is not hex's act; when a
satellite names one, the gate's federation announce block (C-315) names it as
**unapplied**, so the gap is visible rather than silently inherited (C-322).
No new gate, no new table.

## Adversary contract

A pluggable cross-model review, named in the `hex.md › Preferences` section.
The contract is symmetric across harnesses — a user on one model family
points at an adversary skill from another.

- **Scopes:** `code-diff` (the branch diff versus a base) and
  `plan-artifact` (a markdown plan or ADR file).
- **One-shot — never loops.** Two-family stylistic thrash is the failure
  mode it exists to avoid.
- **4-way triage** of its findings:
  - **actionable** — the orchestrator fixes it, then re-runs one affected
    perspective;
  - **deferred** — handed off with context;
  - **stated-convention** — dropped, counted;
  - **trivia** — dropped, counted.
- **Graceful skip** when the named skill is unavailable: log
  "Cross-model review skipped: `<reason>`" and continue — it is a gate, not
  a blocker. The skip is surfaced **prominently at tier `high`**, where the
  adversary pass is a default part of the flow.

## Convergence contract

The post-implementation drift check: does delivered code cover every
requirement ID the plan carries? Run by the review orchestrator when its
target traces to a plan artifact.

- **4-way gap taxonomy, keyed by [Traceability IDs](#traceability-ids):**
  **missing** (nothing delivered for the ID), **partial** (delivered but
  incomplete against the contract), **contradicts** (delivered behavior
  conflicts with the contract), **unrequested** (delivered behavior no ID
  asked for — the reverse gap).
- **Append-only growth**: the orchestrator appends gaps as new WP **rows**
  at the end of the plan's Parallelization table, with matching new
  Implementation Steps entries, `Depends on` the delivered WPs; their
  **wave derives** as the next topological level (no explicit wave to
  assert). Existing WPs, sub-WPs, steps, and IDs are never rewritten or
  renumbered.
- **Byte-identical when clean**: nothing unmet → the plan file is not
  touched at all and the report states "Converged".
- **Verdict interplay**: unconverged gaps cap the review verdict at
  Needs Work — never Approve — with `Next: /hex-execute <plan path>`.
- **Composition with fold-back (C-412)**: convergence runs **first and
  unconditionally**; the [spec fold-back](archive.md) phase runs **only** on
  a `Converged` result. They are mirrors on the same `C-###`/`S-###` join
  key — convergence asks *does the delivered code cover the plan's IDs* and
  appends to the plan (plan ← code), fold-back asks *does the spec describe
  what the plan delivered* and appends to the spec (spec ← plan); neither
  rewrites what the other wrote. A `Needs Work` verdict means fold-back never
  runs at all.
- **Federation — a plan carrying a `Repo` column (C-310):** the mechanism
  above is unchanged; coverage is evaluated against the **union diff** (the
  lead plus every distinct `Repo` value, `/hex-review`'s C-309 scope),
  satellite delivery is located via the `Hex-Plan:` commit trailer
  (`git -C <repo> log --grep`), and an appended gap row carries a `Repo` value
  like any other row. `C-`/`S-` IDs stay plan-scoped and are therefore global
  to the change. A gap delivered in a WP whose `Repo` is **not** `.` is
  **not** folded into the lead's spec — it is reported "delivered in
  `<repo>`, fold by hand" and left in the plan, because a fold has no correct
  destination across a repo boundary (the [fold-back](archive.md) phase is
  lead-scoped and never crosses it).

## Handoff contract

Every orchestrator run ends with its skill's handoff block — **the
required final message of the run, never omitted or summarized away**. A
degraded, escalated, or partially-completed run still emits it, stating
what stands. After emitting it, the orchestrator MAY ask **one** optional
proceed question (e.g. "run the `Next step` command now?") — the
single-gate rule governs *pre-work* approval and is not violated by a
post-completion offer. Never more than one question, and never a question
in place of the block.

## Upkeep step

Every orchestrator's **final phase** re-points any `hex.md › Pointers` entry
this run revealed as drifted — a verification command that changed, a new
artifact home, a moved rule file — and updates `hex.md › Memory` (active
plan pointer, artifact index, learned facts). On a review run reaching a
plan's **terminal review state** (`State: done`, or `landing` for a plan
carrying a `Repo` column), that update **clears** the active-plan pointer —
the first clear in the bundle; the archive mechanic and what is recorded are
defined in [`archive.md`](archive.md#plan-archive) (C-410).
Verify-on-consumption already
repaired whatever a phase acted on mid-run; upkeep sweeps the remainder.
`hex.md › Preferences` is user-owned and is **never edited here**: a
preference the run surfaced (a perspective that should become an always-on
hint) is recorded in `hex.md › Memory` and proposed at the next `/hex-init`
run. This is part of the flow (portable, no hooks needed); because the file
holds pointers rather than copies, upkeep is cheap. The section specs and
staleness rules are in [`memory.md`](memory.md).

**Federation — a plan carrying a `Repo` column.** Upkeep additionally makes
the **only** upkeep writes that leave the lead repo: for a plan in `landing`,
it offers to confirm each `Repos:`-ledger row from locally verifiable evidence
only — `git -C <repo> merge-base --is-ancestor hex/<plan-slug> <trunk>` (the
feature branch is contained in that repo's **local** trunk; hex never fetches
and never infers landing from anything weaker) — advancing the plan to `done`
only when **every** row is confirmed landed (C-324); a row's `landed` flag may
**also** be set by an explicit human override (C-324), not only by this
mechanical `--is-ancestor` check, so a satellite permanently unreachable from
this session is not a hard dead end; and, once a plan reaches
`done`, it removes that plan's slug from every participating satellite's
`Federation lead:` bullet, deleting the bullet — and the satellite's `hex.md`
file, if the bullet was its only content — when the slug list empties (C-313).
Removal on `done`, not `landing`, keeps the satellite lock across the
broken-integration window. The active-plan-pointer clear (above) is unchanged,
and `hex.md › Preferences` stays never-edited in every repo.
