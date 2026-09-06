# hex — Generalization Design Notes

Working notes for generalizing the OCX swarm skills into the public hex
bundle. Not published; v0.1 content is in progress — this file remains
the source of truth for decisions as it lands in the skills.

## Origin

Generalized from `~/dev/ocx/.claude/skills/{swarm-plan,swarm-execute,swarm-review,architect}`
plus `workflow-swarm.md` (shared worker vocabulary, Review-Fix Loop,
tier/overlay grammar). Inventory + analysis: session 2026-07-19.

## Shared shape (all orchestrators)

parse args → classify tier (`low|medium|high|xhigh|max`, `auto` default; `max` explicit only) → resolve
overlays → single meta-plan approval gate (never mid-flow questions) →
announce resolved config with per-axis source attribution → dispatch to
tier file.

Skill layout: `SKILL.md` dispatcher + `classify.md` + `overlays.md` +
`tier-{low,medium,high,xhigh,max}.md`.

**Tier rename (locked 2026-07-19):** grammar is now `low | medium | high`
(+ `auto` default), mapped from the OCX-era `low | high | max`: old low →
low, old high → medium (the new default tier), old max → high. `xhigh`
and `max` are reserved for future overlay stacks — documented, never
emitted by the classifier; an explicit request for either announces
"reserved, running high" and runs `high`. **Superseded by round 22
(2026-09-06, `adr_0017`):** the grammar is now five tiers,
`low | medium | high | xhigh | max`, every 2026-07-19 tier shifted one step
up and a zero-spawn inline `low` inserted below.

## Two-layer knowledge model (revised 2026-07-19, round 2)

Principle: **hex is the outer loop.** Anything that is knowledge about
the PROJECT (how to verify, where specs live, what format they take,
which rules matter) lives in project context — CLAUDE.md / AGENTS.md /
project rules — where every agent already reads it. hex never duplicates
it into its own config; a second source of truth would drift and rot.
`hex-init`'s job is to AUDIT project context for the knowledge the
orchestrators need and help write it there (best practice), not to
capture it in hex config.

### Layer 1 — project context (owned by project, bootstrapped by hex-init)

| Knowledge | Where | How hex uses it |
|---|---|---|
| How to verify (build/test/lint) | CLAUDE.md / AGENTS.md section | tier files say "run the project's documented verification"; if undocumented, detect once, suggest `/hex-init` to persist |
| Spec/plan/ADR conventions: location, format, template (the RST/Sphinx case) | concise conventions block in CLAUDE.md / AGENTS.md (or a doc it points to) | artifact-writing phases follow it; shipped default templates are only the fallback when nothing is documented |
| Arch/quality rules | project's own rules | Discover phase + worker prompts reference them |

### Layer 2 — `.agents/memory/hex.md` — AI-maintained swarm memory

> **Revision — memory relayout (2026-07-20).** The old shared
> `.agents/arcana.md` carried an `arcana:product` section, but product
> and project knowledge is useful to any agent — parking it in a
> swarm-only file broke this chapter's own destination-of-knowledge rule
> (and the file was named after a personal grimoire). New layout: a
> per-bundle memory file, `.agents/memory/hex.md`, holding only a
> self-managed pointer cache (`hex.md › Pointers`, verify-on-consumption),
> user-owned swarm preferences (`hex.md › Preferences`), and working
> memory (`hex.md › Memory`); product/project knowledge is provisioned
> into project context by `/hex-init`. Normative contract:
> `hex-core/references/memory.md`.

Design pivot (round 3): the only consumer of this layer is an LLM — no
parser ever reads it. So no TOML: **one markdown memory file per bundle,
structured by plain headings, maintained by the skills themselves.** It holds cached pointers, swarm preferences, and working
memory — never a second copy of project truth. Each arcana bundle owns
its own file under `.agents/memory/<bundle>.md`; hex owns
`hex.md` outright, no section sharing across bundles.

```
.agents/memory/hex.md   # per-bundle swarm memory (hex owns it)
  ## Pointers    # SKILL-MANAGED cache of locations discovered
                 #   from project context: where verification is
                 #   documented, where spec/plan/ADR conventions
                 #   live, doc + product-knowledge homes, key
                 #   rule files, any worktree-location deviation,
                 #   the constitution (optional). Never
                 #   authoritative — project context wins; a stale
                 #   pointer means re-detect and re-point.
  ## Preferences # USER-OWNED swarm preferences (all optional):
                 #   per-role model literals (architect: opus, …)
                 #   cross-model adversary: skill name + tier models
                 #   limits: max-workers, loop-rounds
                 #   perspectives/research axes of interest (prose,
                 #     e.g. "security review mandatory under src/auth/**",
                 #     "research axes: OCI spec, registry ecosystems")
                 #   written only by /hex-init with consent
  ## Memory      # SKILL-MANAGED working memory: active plan
                 #   pointer, artifact index (what lives where),
                 #   learned facts

.agents/            # overflow: plans/, research/ — DEFAULT artifact
                           #   home, used only when project conventions
                           #   don't name a better one (RST shop: specs go
                           #   to docs/specs/, hex.md › Pointers just points there)
```

Product and project knowledge do NOT live here — they belong in project
context. `/hex-init` provisions them: short facts as sections in the
client context file (CLAUDE.md / AGENTS.md), larger bodies as their own
doc (a de-facto home when one exists, else a provisioned file such as
`.agents/product.md`) with a one-line index entry in the context file so
every agent discovers them ambiently — then seeds `hex.md › Pointers` to
where they landed.

Resolution: search upward from CWD; missing file normal (skills fall
back to shipped defaults + suggest /hex-init). Sections are conventions,
not schema — skills read the whole file (small by contract, pointers not
prose-dumps) and edit sections in place, respecting per-section
ownership: skills maintain `hex.md › Pointers` and `hex.md › Memory`
freely; `hex.md › Preferences` changes only through `/hex-init` with
consent.

**Federation (round 8, below).** Layer 2 stays **one file per repo**; there
is no third layer and no cross-repo memory. A federated run (`adr_0004`)
resolves exactly the **lead's** `hex.md` and reaches each satellite through
Layer 1 — that repo's own project context, read by explicit `Read` — never
through the satellite's swarm memory (C-318). The C-308 satellite
back-pointer halts any orchestrator that would resolve a satellite's memory
as the plan's, so `memory.md`'s single upward search and no-section-sharing
posture are untouched.

### Spawn selection (which workers/perspectives, which models)

Three inputs, priority bottom-up (later wins):

1. **Shipped tier defaults** — tier files define the baseline perspective
   set per tier (unchanged tier methodology); workers.md defines roles
   with capability-class model defaults (architect: deep-reasoning
   class, always; explorer/researcher/builder/tester/reviewer:
   fast-balanced class); tier files escalate specific spawns (max-tier
   builder → deep-reasoning class).
2. **Project hints** — `hex.md › Preferences`: perspectives that always
   matter here, research axes of interest, path-triggered escalations,
   per-role model literals. Classifier folds these into its suggestion.
3. **User, at the meta-plan gate** — the single approval point also
   offers perspective/researcher selection (esp. hex-architect: pick
   research axes). Flags stay for non-interactive override.

Skills never hardcode a spawn list beyond the tier baseline; the
announcement always shows the resolved set with per-item source
(tier default / project hint / user).

### Worktrees (hex-execute parallel work packages)

- Default: one worktree per file-disjoint WP under `.agents/worktrees/`
  (convention over config — nothing persisted when default is used).
- Deviation (different location) is repo layout, not hex behavior: its
  home is project context, cached in `hex.md › Pointers` so any run
  spawning worktrees resolves it without re-discovery.
- hex-init audit: chosen worktree path MUST be gitignored — check,
  offer to add the ignore line. Note: ignore `.agents/worktrees/`
  specifically, never `.agents/` wholesale — `.agents/memory/hex.md`
  is team-shared memory and belongs in version control.
- **Destination is the user's choice** (general hex-init principle, not
  worktree-specific): for every piece of knowledge it persists, hex-init
  proposes a destination but the user can redirect — e.g. "put the
  worktree convention in CLAUDE.md so every subagent and tool always
  uses it, not just the swarm." Rule of thumb offered by init: knowledge
  useful to ANY agent (worktree location, verification) → project
  context (CLAUDE.md/AGENTS.md, ambient for all); knowledge only the
  swarm consumes (perspectives, model overrides, tier prefs) →
  `hex.md › Preferences`. Whatever lands in project context is NOT
  repeated in swarm memory — ambient loading already covers it;
  `hex.md › Pointers` records only where it lives.
- Mechanics inherited from OCX workflow-swarm, revised 2026-07-19
  (round 4 — parallel-by-default): **one feature branch per plan**
  (existing non-trunk branch, else `hex/<plan-slug>` from trunk; its tip
  at execution start is the frozen base), **one ephemeral branch +
  worktree per WP** (`hex/<plan-slug>--<wp-slug>`), disjoint declared
  file sets, merge back **onto the feature branch, serialized, in a
  valid topological order** with verification after every merge, delete
  branch + worktree after merge; feature branch → trunk is the human's
  PR. hex never pushes, except `/hex-finalize`'s force-push of the one
  feature branch it was invoked on, consented by that invocation and
  approved at its gate — see
  [`finalize.md`](hex-core/references/finalize.md#scope).
- **Parallel-by-default decomposition (locked 2026-07-19):** plans
  maximize parallelism — decompose by structural boundary (never feature
  slice), every WP declares its expected file set at plan time
  (plan-time set-intersection check, not merge-time conflict discovery),
  waves computed as topological levels (WP in wave N iff all deps in
  earlier waves, N minimal), critical path marked,
  under-parallelization justified in one line, never silent. Perf pass
  (2026-07-20) added the counterweight: no WP below its own overhead
  (~≤50 expected lines folds into a sibling; isolation needs a
  justification) and a per-WP Review budget (`self | light | panel`,
  lower-only vs the tier baseline, missing = panel) — review breadth now
  scales with WP size, not plan tier alone; artifact-scope Review-Fix
  loops (plan/ADR) default to one panel round with Block-conditional
  re-validation. Research
  basis: Anthropic worktree/agent-teams docs, getautonoma
  frozen-base/serialized-merge guidance, ATM pre-write admission
  (arXiv 2607.00041), LLMCompiler DAG scheduling.
- **Plan visualization (locked 2026-07-19):** WP table is the canonical
  artifact (id, scope, expected files, size, wave, depends-on — plus
  status since round 5, the review budget since the perf pass (C-905),
  `Repo` in second position since round 8 (C-302), and `Verify`
  immediately after `Review` since round 12 (C-905)); one mermaid
  `graph TD` with a subgraph per wave as a visual index (gantt and
  gitGraph rejected — brittle syntax, silent render failures); plan
  stays fully actionable from the table alone.

**Erratum pointer (2026-08-30):** round 12 (§ Execution-performance round, below) amends this section by pointer, bytes intact: it supersedes round 4's "verification after every merge" (`:172`) — the per-merge default is now the scoped check, with full verification at the checkpoints round 12 names — and retro-claims the 2026-07-20 Review-budget addendum (`:187-189`) under C-905, semantics unchanged, joined by a `Verify` sibling; and (2026-09-06) round 17 (§ Per-WP effective-tier round, below) supersedes that same addendum's "lower-only vs the tier baseline, missing = panel" (`:188`) — in a plan carrying the `- Effective-tier: derived` marker the per-WP `Review` budget is raise-only against an effective tier each work package derives, the plan tier is a ceiling rather than the baseline, `self` / `light` are inert, and a missing column or blank `Review` cell reads that derived breadth, not `panel`.

### Staleness (how memory stays true)

The hard part, made cheap instead of impossible:

- **Pointers, not copies** — a stale pointer degrades to "detect again
  and re-point", never to wrong behavior. This is why `hex.md` holds
  locations, not contents.
- **Verify on consumption** — a skill that acts on a `hex.md › Pointers`
  entry first checks the target still exists and still covers what the
  pointer claims; on a miss it re-discovers from project context,
  re-points in the same run, and proceeds — stale memory is repaired
  where it is found, never silently trusted or deferred.
- **Upkeep step in every orchestrator** — each hex skill's final phase:
  if this run revealed drift (verification changed, new artifact home,
  new perspective that mattered), re-point the relevant
  `hex.md › Pointers` entry and update `hex.md › Memory` in the same
  run. Portable (no hooks needed — it's part of the flow).
- **hex-init re-audit** — re-entrant runs verify each pointer and each
  context-file index line still resolves (meta-validate-context pattern:
  check the pointed-at files/sections exist), report drift, fix with
  consent.

Decisions:
- Per-bundle memory file `.agents/memory/<bundle>.md`; hex owns
  `hex.md` outright (no section sharing across bundles); `.agents/`
  as default artifact overflow.
- Model defaults = capability-class prose in workers.md; literal model
  names only as user-set overrides in `hex.md › Preferences`.
- Tier methodology unchanged; project hints + gate selection layer on
  top of it, never replace it.

## Adversary contract (cross-model reviews)

hex defines the contract, config names the implementation — symmetric
across clients (a Codex-client user points at a Claude-adversary skill):

- Scopes: `code-diff` (branch diff vs base) and `plan-artifact` (markdown file).
- One-shot, never loops (prevents two-family stylistic thrash).
- 4-way triage: actionable / deferred / stated-convention / trivia.
- Graceful skip whenever the adversary **produced no review** — the named
  skill is unavailable, or it ran and did not complete one; gate, not
  blocker; skip surfaced prominently at tier=high. An empty finding list is
  never a clean pass (amended in place by round 13, 2026-09-04).

## De-OCX-ification checklist (applies across skills)

| OCX coupling | Generalized to |
|---|---|
| Hardcoded subsystem→rule tables | project rules discovered from project context (Layer 1) |
| `task verify` / `task rust:verify` | project-documented verification (Layer 1); hex-init audits it exists |
| Codex plugin specifics | pluggable adversary skill named in `hex.md › Preferences` |
| Worker agent files + model policy ADRs | workers.md prompt registry in skill tree; capability-class defaults, literal overrides in `hex.md › Preferences` |
| OCX code anchors in reviewer prompts | project-rule driven |
| Security-path overlay triggers | classify.md generic markers + project-context hints |
| `.claude/state/` plan-status protocol | conventions block names artifact locations (Layer 1); self-contained Status block spec |
| product-context update protocol | provisioned into project context (README / product doc / provisioned file, indexed from the context file); `hex.md › Pointers` records where (memory relayout, 2026-07-20) |

## spec-kit learnings (analyzed 2026-07-19, repo @ v0.13.0)

github/spec-kit = GitHub's spec-driven-development toolkit (122k stars,
34 client integrations, MIT). Validates hex's shape; adopt:

1. **Dash naming validated** — spec-kit skills-mode ships
   `speckit-<name>/SKILL.md` (dots only for slash-command clients);
   Codex invokes `$speckit-plan`. Dashes everywhere sidesteps the
   per-client separator rewriting spec-kit needs
   (`__SPECKIT_COMMAND_X__` token pipeline).
2. **`.agents/` validated** — Codex + Zed install skills to
   `.agents/skills/`; client-neutral dir is real, arcana.toml fits.
3. **Copy-only-if-absent** — spec-kit materializes constitution from
   template only when the file doesn't exist; hex-init templates same.
   (spec-kit's fancier SHA-256 manifest tracking = overkill for us.)
4. **Minimal discovery note** — spec-kit's agent-context extension
   writes a marker-fenced block that only POINTS at plan.md instead of
   duplicating content. hex-init note: point at
   `.agents/memory/hex.md` + commands, nothing more. Markers:
   `<!-- hex:start --> … <!-- hex:end -->`.
5. **Constitution gate (optional adopt)** — governance file checked as
   hard gate at plan time, violations require justification table
   (Complexity Tracking), conflicts auto-CRITICAL at analyze time.
   hex analog: optional constitution entry in `hex.md › Pointers`
   (cached from project context); hex-plan gates against it when set,
   deferred-findings style justification when violated.
6. **`[NEEDS CLARIFICATION]` markers, hard cap 3** — bounded-ambiguity
   convention inside spec templates; consolidated single clarify
   interaction. Same philosophy as hex meta-plan gate; adopt marker
   convention in default plan template.
7. **Structured handoffs** — spec-kit commands declare `handoffs:`
   frontmatter forming the command graph. hex keeps prose handoff
   sections (portable), but mirror the graph explicitly.

Differentiation: spec-kit = workflow scaffolding for a SINGLE agent
executing sequentially; no tiers, no multi-agent fan-out, no
adversarial panel, no cross-model gate. hex's value = the swarm layer.
Interop idea (later): hex-execute could consume spec-kit artifacts
(`specs/<feature>/plan.md`, `tasks.md`) as plan input.

## Spec-kit comparison round (2026-07-19, round 5)

Second research pass: spec-kit deep-dive @ v0.13.0 (commit 57cc518,
2026-07-17 — extensions/presets/workflow-engine/`/converge` era) + SOTA
landscape scan (ATM arXiv 2607.00041, CoAgent arXiv 2606.15376, wit,
GSD, OpenSpec, BMAD). Confirmed hex's lead on core parallelism (spec-kit
core `/implement` stays single-agent sequential; worktree/DAG execution
lives only in unreviewed community extensions) and adopted nine items:

1. **Merge-time file-set re-validation** (ATM write-time admission) —
   protocol.md § Worktree work-package mechanics.
2. **Merge-conflict / post-merge failure playbook** (CoAgent semantic
   repair: judge semantically, one fix pass, halt + escalate) — same
   section.
3. **Convergence contract** (spec-kit `/converge`, improved: gaps append
   as new WP rows, wave derives) — protocol.md § Convergence contract;
   run by hex-review. Decision: hex-review's "read-only" re-scoped to "never
   edits code or the diff"; plan-artifact writes = Status block +
   append-only convergence rows. Plan is the durable state — a chat-only
   gap report evaporates.
4. **Traceability IDs** (C-###/S-###, coverage mechanical at three
   gates) — protocol.md § Traceability IDs; IDs originate in the spec
   when one exists.
5. **Recommend-then-confirm clarifications** (spec-kit `/clarify` UX) —
   protocol.md § meta-plan gate; markers carry `Recommended:` answers,
   plain approval accepts all.
6. **Constitution gate** — protocol.md § Constitution gate; optional
   `hex.md › Pointers` entry, deviations table, unjustified violation =
   Request Changes. hex never ships a constitution.
7. **WP Status column** (`pending|active|merged|failed`) — the WP-level
   state of record; branches are evidence; resume reads the column.
8. **MVP boundary** — "Shippable after wave: N" in the plan template.
9. **Template diet** — Files-to-Modify + Testing-Strategy tables deleted
   (duplicated Expected Files and ID'd contracts/scenarios — drift
   surface); Dependencies/Rollback/Risks marked tier-scaled.

Non-adopts, with reasons: spec-kit's workflow engine / presets /
extension-hook stack (hex ships markdown, the client is the runtime —
portability is the moat); wit-style Tree-sitter symbol-level locking
(unlocks intra-file parallelism but needs a daemon — future candidate);
GSD fresh-context-per-task (already inherent — every worker spawn is a
fresh subagent).

## Resolved questions (v0.1)

- **hex-architect**: full 3-tier grammar, not collapsed — low/medium/high
  as defined above, same methodology as every other orchestrator.
- **Worker definitions**: markdown prompt blocks inside tier files
  (portable across clients), not shipped agent artifacts — already how
  this document describes them throughout.
- **Security-path globs**: classify.md generic markers (auth/crypto/
  signing paths, new package manifests, CI workflows, dependency
  manifests) + `hex.md › Preferences` path hints — no separate config
  table.
- **Constitution gate** (spec-kit learning #5): ~~deferred post-v0.1~~ —
  superseded, adopted in the spec-kit comparison round (round 5, below).

## Config surface round (2026-07-20, round 6)

`adr_0003` (configuration and customization surface — the
`hex.md › Preferences` yaml block; vocabulary, merge rules, and carrier
contract now live in `hex-core/references/config.md`) amends four
decisions resolved above. Full adjudication and rejected alternatives:
`adr_0003` § Constitution deviations.

1. **No external config file → a fenced yaml block inside `hex.md`.**
   Supersedes the Two-layer knowledge model's original pivot, above:
   "the only consumer of this layer is an LLM… So no TOML: one markdown
   memory file, structured by plain headings." That premise — no parser
   validates this layer — is a reason a schema can't be *checked*, not a
   reason keys can't exist; plain prose can't express a `never` list, a
   path-scoped rule, or a count. The block stays *inside* `hex.md`, under
   `## Preferences`: still one file, still no TOML, still no second
   config file, still no schema.
2. **Security-path globs move into the `perspectives` table.** Supersedes
   the Resolved questions bullet above ("classify.md generic markers +
   `hex.md › Preferences` path hints — no separate config table").
   `classify.md`'s generic markers stay; `perspectives.always`/`never`
   with `when:` globs layers on top with a stated resolution and a
   stated displacement rule — the shipped mechanism had no subtractive
   lever at all and no stated resolution for its additive one.
3. **"Tier methodology unchanged" → `tiers`/`workflows` rewrite spawn
   layer 1.** Supersedes the Staleness decisions bullet above. `inherits`
   is a full replacement of the layer-1 baseline, not a merge on top of
   it, and a `workflows` fork swaps the phase plan outright — distinct
   from the three-input spawn-selection precedence above, which is
   unchanged (no fourth input added; only layer 1's own content is now
   project-rewritable). What the old rule guarded — a reader never
   silently misled about which methodology ran — survives via mandatory
   disclosure (`[project-redefined: …]`, printed even when the resolved
   counts match the shipped ones) instead of via uniformity; only the
   uniformity is given up. Tier *vocabulary* (`low|medium|high`+`auto`)
   is unaffected — see Resolved questions, above.
4. **Single-gate rule re-scoped to the four orchestrators; `hex-init`
   exempt.** Shared shape's "single meta-plan approval gate (never
   mid-flow questions)," above, never literally named `hex-init` — it has
   no tiers and spawns no workers, so the stranded-swarm risk the rule
   guards against doesn't apply to it. The exemption is narrow and named:
   ~~`hex-init` only, because it spawns nothing; no skill that spawns
   workers gets it~~ — superseded, widened to a closed list of two named
   skills by `protocol.md` § The meta-plan approval gate, ratified as
   `adr_0008`'s `protocol.md` deviation 1.
   `hex-init`'s current batched-consent shape (Step 2)
   is unchanged by this round — a later wave upgrades it to a validated,
   per-question wizard (`adr_0003` C-212), not built yet.

`memory.md`'s "keep it small — pointers, not prose dumps" rule (Layer 2,
above) is **honoured, not deviated**: the `Preferences` block is bounded
by the frozen vocabulary, and the one thing that would genuinely bloat
the file — workflow DAGs — lives in its own file behind a one-line
pointer, exactly as the rule prescribes.

**Erratum (2026-09-05, review):** `adr_0003`'s frozen v1 vocabulary types
`limits.loop-rounds` as `int 1–3`. What ships is `int ≥ 1`, the tier
default standing as the key's ceiling: a higher value clamps and announces
under merge rule 9 rather than being rejected as malformed, so the `Type`
column no longer restates a bound the ceiling owns. The vocabulary is not
reopened — no key is added, renamed or given new meaning. The ADR is frozen
and stays as written; the live type is
[`config.md` § Key vocabulary](hex-core/references/config.md#key-vocabulary).
That record's rendered gate block is superseded too: it prints `Limits:
max-workers 6 (hex.md), loop-rounds 3 (tier baseline)`, where the shipped
`<name>` derivation — the leaf key with `limits.` dropped, hyphens read as
spaces, `max-workers` shortening to `workers` — renders `workers 6` and
`loop rounds 3`
([`protocol.md` § The meta-plan approval gate](hex-core/references/protocol.md#the-meta-plan-approval-gate)).

## Archive & fold-back round (2026-07-22, round 7)

`adr_0005` (terminal archive and spec fold-back — a Fold-Back phase in
`/hex-review` that folds a converged, approved plan's `## Spec Deltas`
into the project's documented spec home) amends **two resolved positions
and one shipped-template rule**. Full adjudication, the worked options,
and the scored A-vs-B/C/D/E/F comparison: `adr_0005` § Constitution
deviations and § Considered Options. The justification below leans on the
**rejected-alternative** grounds — per `adr_0005`'s deferred finding D-5
the "why needed" framing of amendment 2 is circular (amendment 3's is
independently sound), and the sound justification is which simpler route was
rejected and why — a lean applied to all three for uniformity.

1. **`hex-review`'s write surface grows the fold write — and only that.**
   The never-writes contract (SKILL.md description + `## Constraints`
   bullet) previously bounded hex-review's writes to the plan's Status
   block and the append-only convergence rows; the Fold-Back phase adds a
   write to the resolved spec file plus the fold receipt appended to the
   plan. Rejected alternatives: **Option C** (a fifth `/hex-archive`
   skill) keeps the contract textually intact but scored **35 points
   behind** — it buys that purity with a whole new install surface and
   makes the lifecycle's most important step optional by omission, the
   very mechanism by which `done` became a dead end; **Option B** (fold
   inside `hex-execute`) folds *unreviewed* work into truth, before the
   convergence gate that decides whether the work is correct. The
   amendment is the minimum that admits a write path: it names the new
   write and its four preconditions and nothing else. **The never-commits
   half is NOT amended and is load-bearing** — every fold lands unstaged
   in the working tree, which is what makes it reviewable at `git diff`
   and revertible by `git checkout --` (C-401/C-409). This re-scopes the
   same contract the spec-kit comparison round (round 5, above) already
   moved from "read-only" to "never edits code or the diff", for the same
   reason: the durable state — there the plan, here the spec — must be
   written or it evaporates.

2. **`spec.md` shipped template: a spec is amended, never produced, by an
   orchestrator.** The line "A human-authored pre-plan artifact - no hex
   orchestrator produces one" becomes "human-authored; amended by
   hex-review's fold-back phase, never created by it." Rejected
   alternative: keeping specs strictly human-authored is **Option E**, the
   null option — it closes the never-cleared-pointer gap and nothing else,
   leaving truth permanently stale, no diff-shaped vocabulary. The
   amendment is deliberately narrow: hex **amends** a spec, never
   **produces** one — it creates no spec file, no spec directory, invents
   no section (C-403 rule 5), and does nothing at all when the project
   documents no spec home (C-407).

3. **Project-knowledge-is-the-project's / destination-is-the-user's-choice
   admits a post-gate orchestrator write, with consent relocated to
   `/hex-init`.** The two-layer model (above) established `/hex-init` as
   the only writer into project context, always with consent; fold-back
   writes into a project's layer-1 spec home from an orchestrator, after
   every gate, with no consent point of its own. Rejected alternatives:
   the **Handoff post-completion carve-out** (`protocol.md` § Handoff
   contract) was evaluated as the closest sanctioned consent point and
   rejected on two mechanical grounds — position (it fires after Upkeep
   has already cleared the active-plan pointer and written the artifact
   index, so a "no" leaves the run's own bookkeeping describing a fold
   that did not happen) and, decisively, that it buys nothing: the diff is
   printed either way (C-411) and left uncommitted either way (C-409), so
   a yes/no on an unread printed diff is consent theater, weaker than an
   unstaged diff the human must actively `git add`. A **pre-gate "may I
   fold?"** at the meta-plan gate was also rejected — it asks about a diff
   whose content does not exist yet (the deltas are produced three phases
   later, by execution). Consent instead moves to **where the destination
   is chosen**: `/hex-init` records the spec home with consent (C-407),
   and that recording *is* the standing permission; the fold then stays
   inside the recorded location (C-418), announces every write (C-411),
   and leaves it uncommitted (C-409) so approval is exercised at `git add`
   — the same place every other hex change is approved.

**Considered and not deviated** (unchanged by this round): the two-layer
knowledge model is *upheld* — hex writes into the project's layer-1 home
and ships no layer-2 spec store (Option D rejected at the gate). The
single meta-plan gate (`protocol.md` § meta-plan gate) is preserved — the
phase asks nothing, ever, and halts instead. Traceability IDs are the
fold's join key, unchanged. `hex never pushes` is untouched, and **the
never-commits half of hex-review's contract is affirmed unchanged** — it
is what makes every fold reviewable and revertible.

## Federation round (2026-07-22, round 8)

`adr_0004` (cross-repo federation — the lead repo owns a change spanning
multiple git repos: Option D+E, with pointer-only Option C as substrate)
amends **four resolved decisions** and introduces **one new class of write**.
Full adjudication, the scored A/A′/B/C/D+E/F comparison and the rejected
alternatives: `adr_0004` § Constitution deviations and § Considered Options.
Every amendment is **vacuous without a `Repo` column** — a single-repo project
runs byte-identically, the same no-marker discipline `adr_0002` C-105 set.

1. **"One feature branch per plan" (§ Worktrees, above) generalizes to one
   feature branch *per participating repo*, sharing a slug.** Branches are
   per-repo objects; a single branch cannot span repos, and the plan is one
   decision. The shared `<plan-slug>` is the only join key git can express
   across a repo boundary — it is what makes C-306's global merge order and
   C-309's union diff addressable by one name. Rejected alternative: keeping
   literally one branch strands the satellites' work on their default or
   ad-hoc branch names — no join key, no addressable union diff, no resume.
   The rule's intent (one integration target per plan) is preserved: still
   exactly one target per repo per plan, and the slug makes the set of them
   one named thing.

2. **The satellite branch-origin clause is suspended.** "Existing non-trunk
   branch, else `hex/<plan-slug>` from trunk" (§ Worktrees) holds for the
   lead; a **satellite always branches from its own trunk**, discovered never
   assumed. Verified on the real cluster: `ocx-mirror` sits on
   `feat/pypi-mirror` while `ocx` and `ocx-mcp` sit on `main`, so applying the
   rule per repo yields three branch names for one change and the slug join
   key ceases to exist. Rejected alternative: honouring the clause and
   recording per-repo branch names in the plan turns one join key into an
   N-row lookup that must be kept in sync with git — a second source of truth
   for something git already names, the drift the two-layer model forbids. The
   checked-out branch is not discarded silently: it is announced at the gate
   as unrelated in-flight work.

3. **Plan visualization (locked 2026-07-19, above) gains a `Repo` column** in
   second position (C-302). The lock's intent is that the plan "stays fully
   actionable from the table alone"; a federated plan is *not* actionable from
   the locked column set, because nothing in it says which repo a WP's
   `Expected Files` are relative to, so worktree creation and merge-time
   re-validation have no addressable target. Adding the column preserves the
   intent where honouring the letter would break it. Rejected alternatives:
   encoding the repo inside `Scope` or as a path prefix on `Expected Files`
   makes it a substring parsed out of free prose that sub-WP rows cannot
   inherit the way a column is; a separate repo→WP lookup table is a second
   place to keep in sync. A plan without the column renders and reads exactly
   as today.

4. **Parallel-by-default's plan-time set-intersection check (locked
   2026-07-19, above) compares `(Repo, path)` pairs, not bare file sets**
   (C-316). `Expected Files` are repo-relative, so satellites in one language
   ecosystem declare textually identical paths as a matter of course
   (`Cargo.toml`, `src/**`); read as bare paths those sets intersect, the WPs
   may not share a wave, and FM5's stated upside — cross-repo work is disjoint
   for free — is destroyed by a string comparison. The lock's intent (parallel
   eligibility decided at plan time by set intersection, never by merge-time
   discovery) is preserved exactly; only the element type is qualified.
   Rejected alternatives: lead-relative paths (`../ocx-mirror/Cargo.toml`)
   break merge-time re-validation, which runs inside the satellite and reports
   satellite-relative paths; declaring paths unique by convention is an
   unenforceable authoring rule guarding a mechanical check. A plan with no
   `Repo` column compares `(., p)` pairs — exactly as today.

**New class of write.** hex now writes in a repo the session did not start in
— a worktree, commits, one `Federation lead:` back-pointer bullet, the
self-undoing C-303 pre-flight write probe, and (on a C-303 (vi) miss) an
offered `.agents/worktrees/` ignore line. No prior rule forbade it, but every
mechanism before this ADR assumed a single repo, so it is stated as a deviation
rather than claimed as conformance. Rejected alternative: read-only satellites
(plan the change, let a human execute it there) re-split execution across
sessions, none of which can run the post-merge verification the plan orders,
reopening FM5 and FM8. The write is bounded by four structural limits:
**explicit paths only** (never a glob, scan or discovered sibling), a
**halting pre-flight barrier** (a partially readable or writable cluster
produces no writes), **hex never pushes** (every effect local and revertible),
and a **two-item persistent footprint** (the back-pointer bullet and commit
trailers).

**Considered and not deviated** (unchanged by this round): **no new file
format** — federation rides `hex.md › Pointers` bullets, one plan-table
column, git branches and a git trailer, and `memory.md`'s "three sections"
survive intact. **One Status block, one ID space** — link-never-copy holds; no
plan copy in any satellite. **The self-contained Status block** — C-324's
`Repos:` ledger and `landing` State live *inside* it, so there is no external
state file; `DESIGN.md` locks no Status-block field list or plan-State
vocabulary, so neither addition is a fifth deviation — the count stays four.
**Capability classes** — untouched; no literal model name appears. **Single
meta-plan gate** — no new gate and no mid-flow prompt; federation is announced
and consented at the existing gate. C-303's write probe precedes it but
consents to nothing (self-undoing) and is disclosed *in* the gate echo —
declared as its own `protocol.md § The meta-plan approval gate` deviation in
`adr_0004`, not a `DESIGN.md` round. **hex never pushes**, in every repo.

## Discussion-mode round (2026-08-28, round 9)

`adr_0008` (pre-plan discussion mode — the `hex-discuss` skill, the
`.agents/discussions/` artifact class, and the bundle's first rule
artifact) amends **two resolved positions**. Full adjudication and the
scored A/B/C/D/E comparison: `adr_0008` § Constitution deviations and
§ Considered Options.

1. **"Shared shape (all orchestrators)" scopes to the four orchestrators;
   `hex-discuss` is a fifth *skill* with its single gate at the exit.**
   The shape above — parse args → classify tier → resolve overlays →
   single meta-plan approval gate → announce the resolved config →
   dispatch to a tier file, laid out as `SKILL.md` + `classify.md` +
   `overlays.md` + `tier-{low,medium,high}.md` — was written for skills
   that resolve a whole swarm before launching it. `hex-discuss` resolves
   nothing at turn zero: its spawn set is discovered *through* the
   conversation, and its two knobs (research on/off, the deep-sweep gear)
   are conversational moments, not config. Rejected alternative:
   **giving `hex-discuss` tiers and an entry gate** (Option D's shape,
   and the conforming route) forces an approval block that announces a
   config nobody has yet chosen, in front of a mode whose premise is that
   nothing is committed — an entry gate that guards nothing while
   destroying the mode's opening turn. What the rule protects is
   preserved exactly: there is still **exactly one approval gate per
   run**, and the reader is still never misled about what will happen —
   the gate simply sits where the irreversible act is, at the drain
   (`adr_0008` C-710), and the announce block is replaced by **one line
   per mandated disclosure** (C-712) rather than dropped. One further
   user-facing confirmation is declared here rather than left implicit,
   and it is **not a gate**: the deep-sweep offer (C-707) asks before
   spending up to twelve workers. It is a bounded, user-initiated
   **spend** confirmation — a conversation is not a swarm, so nothing
   strands when the user declines and no state advances when they
   accept; it exists only because a twelve-worker spend mid-conversation
   must never be silent. The approval-gate count is still one. Tier
   *vocabulary* is untouched; `hex-discuss` has no tiers to name, so
   `config.md`'s `tiers.<skill>` segment stays closed to the four and the
   frozen v1 vocabulary gains no key.

2. **The bundle ships a rule artifact — a second install surface, with
   declared degradation.** Every resolved decision above assumes hex ships
   skills; the closest neighbour, "Worker definitions: markdown prompt
   blocks inside tier files, not shipped agent artifacts," chose *against*
   a second artifact kind on portability grounds. A rule reaches Claude,
   Cursor, Copilot and Kiro natively, is degraded on OpenCode and Junie,
   and is absent elsewhere. Rejected alternative: **keeping the stance in
   the skill body alone** (Option B) is the portable route and loses on
   the single requirement the mode exists for — a skill body is
   conversation content, condensed first at compaction, so the stance
   lapses on exactly the long discussions that need it. The
   portability the old decision protects is preserved by a contract, not
   by abstinence: the rule is **strictly a hardening** and no hex file may
   make its presence a condition of any behavior (`adr_0008` C-719), so a
   client without a rule surface loses persistence convenience and never
   capability — Option B is not a rejected design but `hex-discuss`'s own
   degraded mode. The surface is also **singular by design**: the one
   bundle-generic `hex-state` rule carries a single concrete line per
   shipped mode, and a future mode amends that same file through its own
   ADR rather than adding a rule per feature — the always-on cost stays
   one artifact and grows by single lines, never by artifacts.

**Considered and not deviated** (unchanged by this round): the **two-layer
knowledge model** is upheld — `hex-discuss` writes no project context; a
durable convention it surfaces is recorded in `hex.md › Memory` post-gate and
proposed into project context at the next `/hex-init` **re-audit**, with
consent (`hex-init/references/audit.md`) — the route for *project* knowledge,
distinct from § Upkeep step's route for surfaced *preferences*, and named
separately here so the two do not merge into one claim.
**`adr_0005`'s fold path is untouched** — the spec drain target
emits a `/hex-plan` command and a pointer to `/hex-review`'s Fold-Back;
`hex-discuss` writes no spec and invokes no fold, so `archive.md`'s safety
envelope remains the only fold mechanism. **Capability classes** — no
literal model name appears in any shipped file (`DESIGN.md`'s own rule) and
no harness tool name either (`protocol.md` § Worker coordination's
capability-class-not-primitive-name rule, which is where that half of the
house rule actually lives). The researcher's shipped default is
`fast-balanced`, its matrix cell at every tier, so `hex-discuss` escalates
nothing on its own judgment; a `models.overrides` escalation is possible and
is disclosed by the resolved-literal-model line like any other. **A new
directory under `.agents/` is not a
deviation** — `.agents/` is the stated default artifact overflow home and
`specs/`, `workers/`, `workflows/` were each added without an amendment.
**`hex never pushes`, `hex never commits` outside execution** — unchanged.

**Erratum (2026-08-29, review):** the round-9 always-on cost sentence
undercounts — a shipped skill's frontmatter description is a second
permanent always-on surface alongside the rule body. Corrected: the
always-on cost is the rule body plus each shipped member's description
line; a description carries entry triggers only and never duplicates body
prose; a future member's ADR budgets both.

**Erratum pointer (2026-08-30):** deviation 1's turn-zero premise and its two-gear sentences are re-argued and superseded by the discussion-rework round (round 11) below; round 9's own text is unchanged.

## Finalize round (2026-08-29, round 10)

`adr_0009` (the finalize phase — the `/hex-finalize` command, the scoped
remote-rights amendment, and the convention-discovery contract) amends
**two resolved positions**. Full adjudication and the scored A/B/C/D
comparison, including its stated sensitivity: `adr_0009` § Constitution
deviations and § Considered Options.

1. **`hex never pushes` scopes to everything except `/hex-finalize`'s
   force-push of the one feature branch it was invoked on.** The rule
   above — "feature branch → trunk is the human's PR. hex never pushes"
   (§ Worktrees) — made every hex effect local and revertible, and that
   remains true of every other skill: `hex-plan`, `hex-execute`,
   `hex-review` and `hex-architect` are unchanged, and `hex-execute`'s
   own "Never push to remote" is untouched. The amendment is **one
   branch wide**: `/hex-finalize` may force-push the branch it was
   invoked on, fetch that branch and its target once to pin the lease
   and rebase onto real remote state, dispatch the project's own
   **documented** release workflows against the pushed SHA, and create
   or mutate that branch's one pull request. It **never** pushes the
   target branch, never merges, never touches branch protection, and
   never mints or stores a credential. Rejected alternative: **keeping
   the rule absolute and printing the remote commands for the human to
   run** (`adr_0009` Option D) scores within three points and is the
   design's own bottom rung — but the two steps it hands back are
   precisely the two that cannot be performed correctly outside the
   run. A `--force-with-lease` value must be pinned to the SHA *this
   run* fetched, or a background fetch silently degrades it to a plain
   force; and the checks must be dispatched against the SHAs the
   rewrite just minted, because a rewrite invalidates testing done
   against the SHAs it replaced. What the old rule protected — that a
   hex run leaves nothing a human cannot undo — is preserved by a
   mechanic rather than by abstinence: every rewrite is anchored by an
   armed `backup/<branch>-pre-finalize` ref taken before the first
   history-modifying operation and renamed inert on **every** terminal
   outcome, and a lease rejection is a hard stop rather than a retry.
   The **sole definition site** is `hex-core/references/finalize.md`;
   the four bundle-wide restatement sites gain a one-clause qualifier
   pointing there, and every skill-, worker- and federation-scoped
   restatement is **unchanged, because it remains true**.

2. **The single approval gate's *position* clause admits a third named
   member.** The shared shape puts one gate "before any work starts."
   `/hex-finalize` keeps **exactly one** approval gate and moves it to
   the local/remote boundary, on every degrade rung. Rejected
   alternative: **a conforming entry gate** would have to announce a
   commit plan that does not yet exist — the recomposed series is
   derived by reading the branch diff, so an entry gate asks the human
   to consent to a rewrite whose shape is unknown, which is the consent
   theater `adr_0005` rejected for the fold. What the rule protects is
   preserved exactly: one approval per run, no mid-flow questions, and
   the reader never misled — the gate sits where the irreversible act
   is and carries what only that position can carry, the exact
   recomposed commit list with its `Signed-off-by` lines and its
   literal signing identity. Everything before the gate is local and is
   reversed by one command against the backup ref. The exemption list
   in `protocol.md` § The meta-plan approval gate stays a **closed list
   of named skills with stated grounds**, gaining a third name and
   never a criterion to interpret.

**One `adr_0008` contract is amended, in the open.** C-718's rule-body cap
reads "≤10 lines" with no measure qualifier, and `hex-state.md`'s body is
exactly ten physical lines today. A second mode line is about three more.
Rather than redefine the measure to "non-blank" and claim headroom that
does not exist, `adr_0009` **raises the cap to ≤14 physical lines**, on the
ground that the cap bounds always-on instruction budget and that two modes
plus the generic frame is fourteen with nothing spare. The next mode's ADR
compresses or amends again, and — per this round's own erratum — budgets
the **description-line** surface alongside the rule body.

**Considered and not deviated** (unchanged by this round): the **two-layer
knowledge model** is upheld — every git convention, commit requirement,
release workflow and release-grade suite is a Layer-1 project fact,
discovered by `/hex-init` and pointed at, never authored as hex config;
`config.md` gains no key and its `<skill>` enumeration stays closed to the
four orchestrators. **`adr_0005`'s fold path is untouched** — finalize
never commits a fold; it halts on the uncommitted fold write with a named
fix, so `git add` remains where a human approves a fold. **Capability
classes** — untouched, and vacuously so: `/hex-finalize` spawns no workers.
**Plan lifecycle** — no new `State:` value; finalize appends one line to an
already-archived plan's Status block. **Federation** — `adr_0004` is
unchanged and federated finalize is deferred; the one amendment is that
`/hex-finalize` joins the satellite halt's scope, with its own `Fix:`
variant, because its blast radius is a rewritten branch rather than a
report. **`hex never commits` outside execution** — amended with the push.
Round 9 stated both clauses unchanged; `/hex-finalize`'s recomposition
(C-807, C-808) commits outside `/hex-execute`, on the one branch it was
invoked on, after the gate, anchored by the same backup ref. Rejected
alternative: having `/hex-execute` commit the recomposed series would put
the rewrite behind a different skill's gate and re-open the two-command
surface `adr_0009` Option C rejected.

## Discussion-rework round (2026-08-30, round 11)

The `hex-discuss` interactive rework (`adr_0008`, amended in place
2026-08-30; plan `.agents/plans/plan_hex_discuss_ux_rework.md`) **re-argues
one round-9 premise and supersedes two of its sentences**. Round 9's text is
left as it was written and carries a pointer to this round.

1. **Round 9's "resolves nothing at turn zero" premise is replaced, and the
   conclusion it carried is re-derived on other ground.** Round 9 grounded
   `hex-discuss`'s exemption from § Shared shape on the claim that "its spawn
   set is discovered *through* the conversation." That premise no longer
   holds literally: entry now fires an **automatic entry wave** of two fixed
   lanes — codebase recon and a prior-art web scan, seeded from the opening
   turn's own text — so part of the spawn set is fixed before the first
   answer arrives, and that fixing is **two-path, not unconditional**: slot 1
   present dispatches the wave that same turn; slot 1 absent defers it to
   fire once slot 1 lands. **The exemption survives on a different ground**:
   a fixed two-lane wave inside the default gear is **grounding, not
   turn-zero config**. It resolves no tier, no overlays, and no spend the
   user could be asked to approve; it reads the ground the first answer will
   be discussed against, and it is dispatched *after* that answer is emitted,
   never in front of it (`adr_0008` C-701's answer-first entry). **Dispatch,
   once it happens, is non-repeatable** — a resume never re-fires an
   already-dispatched wave — but a discussion parked before slot 1 ever
   landed still gets its wave when slot 1 does. What round 9 rejected is
   still rejected — an approval block announcing a config nobody has yet
   chosen, in front of a mode whose premise is that nothing is committed —
   and there is still **exactly one approval gate per run**, at the drain.
   Rejected alternative: **an opt-out knob for the wave** (a flag, or a
   `hex.md › Preferences` key) reintroduces precisely the turn-zero
   configuration this position exists to keep out; it was considered and
   declined at the plan round, so `config.md` gains no key and the wave has
   no knob.

2. **The spend threshold is stated, and it supersedes round 9's two-gear
   sentences.** Round 9 declared one non-gate user-facing confirmation — the
   two-gear offer of `adr_0008` C-707 — before spending up to twelve workers.
   That offer is **retired**: C-707 is now a **lane multi-select**, offered
   once after the entry wave dispatches and re-offered only on user demand or
   on a new lane surfaced by a returning researcher's `leads:`, keeping the
   same hard cap of 12 and the same batch-split disclosure. The general rule
   underneath it is stated here rather than left implicit in a contract:
   **automatic spend never exceeds the default gear and is always announced;
   anything above the default gear is user-initiated.** The entry wave is the
   automatic half — two lanes inside the three-concurrent default, disclosed
   on the combined entry line — and the lane multi-select is the
   user-initiated half, a bounded spend confirmation and **not a second
   approval gate**, exactly as round 9 said of the offer it replaces. Round
   9's sentences naming that retired offer, and its "two knobs (research
   on/off, …)" clause, are **superseded by this round**; their bytes stay as
   round 9 wrote them.

**Considered and not deviated** (unchanged by this round): the single
**approval** gate, its count and its position at the drain — the multi-select
is a spend confirmation, as round 9 already established for the offer it
replaces. **Capability classes** — the wave's two lanes and the council
lane's perspective seats all spawn at the researcher row's pinned class, and
no shipped file names a literal model or a harness tool; the second
`references/` split (`hex-discuss/references/research-lanes.md`) is held to
that rule, not excused from it. **Thin dispatcher + reference files** —
`hex-discuss` still ships one body under its budget with contracts linked,
never copied. The **two-layer knowledge model**, `adr_0005`'s fold path, and
`hex never pushes` / `hex never commits` stand as round 10 left them.

## Execution-performance round (2026-08-30, round 12)

`adr_0010` (scoped per-merge verification, checkpointed backstops,
delta-scoped review rounds, and the failure cascade) amends **three
positions in § Worktrees** — two from round 4 and its 2026-07-20 perf pass,
and one from the *Plan visualization* lock. The first two supersede by
pointer: their text is left as written and the `### Worktrees` region gains
one erratum pointer, per round 11's convention. The third is a live lock
and is amended in place — its enumeration has been amended twice in place
before (`status`, round 5; the review budget, the 2026-07-20 perf pass) and
once by round 8's standalone addendum bullet (`Repo`, C-302), which this
round folds into the base text. Full adjudication and the two scored
five-option comparisons: `adr_0010` § Considered Options.

1. **"Verification after every merge" becomes "a scoped check after every
   merge, with full verification on three policy triggers plus two override
   paths."** The round-4 rule above — "merge back onto the feature
   branch, serialized, in a valid topological order **with verification
   after every merge**" (§ Worktrees, emphasis added) — made the tree
   provably good after each merge, and the reason it gave remains
   correct: cross-file interactions surface only post-merge. **The
   amendment keeps that reason and bounds its cost rather than discarding
   it.** A full verification still runs — on **three policy triggers** (a
   coordinator join, a checkpoint, the final gate) and on **two override
   paths** (a `Verify: full` cell or `Verify-default: full` line; a
   degrade when no assembly gate or no runner-addressable test set can be
   resolved) — and the **final gate is unchanged, mandatory, and
   un-lowerable by any per-WP budget**. What changes is the ordinary
   merge, which pays the WP's own contract tests plus the project's
   cheapest assembly gate. The cadence is a **dual
   trigger with a risk override** — `M = 3` merges since any full
   verification, or a cleared dependency level, or a high-risk merge,
   whichever fires first, each firing resetting the counter — because the
   checkpoint literature's own 2024 survey reports Young/Daly does not
   transfer to DAG-of-tasks workloads, and because every production
   checkpoint policy surveyed (Postgres, CI tiering) is a dual trigger
   rather than a computed optimum. Rejected alternative: **relaxing the
   verify/merge coupling instead** — overlapping a merge's verification with
   the next merge's launch. It scores **within six points on a 102-point
   scale, close enough that the arithmetic does not carry the choice**, and
   preserves the correctness property this amendment trades. Its apparent
   licence is C-306's own text in `protocol.md` § Worktree
   work-package mechanics (from `adr_0004`), which calls global
   one-at-a-time "an operability choice … the first rule to relax if
   merge wall-clock ever dominates" — but **that sentence is
   federation-scoped** and governs the cross-repo order, not the
   single-repo coupling the same section's serialized-merge rule states
   ("each merge changes the base under the next"), which is grounded in
   correctness and carries no such invitation. It loses on bundle surface
   and legibility: an overlapped verification reports against a tree that
   no longer exists, the merge-failure playbook grows a concurrency
   story, and resume must reconstruct which verification was in flight.
   **C-306's lever is therefore not spent — it is explicitly left
   available** for the federated case it actually governs, and is the
   right next move if scoped checks land and cross-repo merge wall-clock
   still dominates. Also rejected: **selective checks with only the final
   gate as backstop**, which is the premortem seat's named failure mode
   made policy and has no production precedent in the survey. **The sole
   definition site is `protocol.md` § Verification**; § Worktree
   work-package mechanics carries the amended sentence and links there,
   six further sites take a one-clause qualifier or an amended sentence,
   and **every site whose sentence stays true is untouched** — including
   three of the four glossary sites, because the merge gate now names a
   *different* check rather than redefining "Verify". The fourth,
   `hex-plan/SKILL.md:225`, takes a one-clause qualifier because that
   same file now carries a column literally named `verify`.

2. **The 2026-07-20 Review-budget addendum becomes a two-member family with
   a stated direction rule, and its unowned contract surface is claimed.**
   That perf pass added "a per-WP Review budget (`self | light |
   panel`, lower-only vs the tier baseline, missing = panel)" and shipped it
   with **no contract ID at all** — pre-`adr_0003` debt. `adr_0010`
   **retro-claims it under C-905 with its semantics unchanged in every
   byte**, and adds a sibling: **`Verify` (`scoped | full`, raise-only,
   missing = `scoped`)**. The rule underneath both is stated here rather than
   left implicit: **a budget column moves a WP away from the shipped default
   in exactly one direction, fixed per column and stated in shipped text, and
   each column's baseline sits at the unsafe end of its own range so the
   unsafe direction is unreachable** — `Review`'s baseline is the full panel,
   so only down exists; `Verify`'s baseline is the scoped check, so only up
   exists. Rejected alternative: **leaving the `Review` column unowned and
   numbering only `Verify`** would have shipped two columns governed by one
   unwritten rule, with one of them still unciteable — the exact condition
   that let the direction rule stay implicit for a year. Also rejected: **a
   `config.md` key for either column.** The v1 vocabulary froze at six
   (C-223); both columns are **plan-artifact cells**, so the freeze is not
   reopened, and `M = 3` ships as text with no knob for the same reason.

3. **The *Plan visualization* lock's column enumeration admits a fourth
   amendment: `Verify`.** "Plan visualization (locked 2026-07-19)" fixes the
   WP table's canonical column set, and it is a **live lock, not historical
   round text** — which is why this is an amendment in place rather than a
   supersede-by-pointer. It has been amended by explicit act three times
   already — twice in place (`status`, round 5; the review budget, the
   2026-07-20 perf pass) and once as round 8's standalone addendum bullet
   (`Repo` in second position, `adr_0004` C-302, whose deviation row is the
   shape this one follows); this round folds that addendum's outcome into
   the base enumeration, which had never absorbed it, alongside `Verify`.
   `adr_0010` adds **`Verify`, immediately after `Review`**, keeping the
   two budget columns adjacent. The lock's stated intent is that the plan
   "stays fully actionable from the table alone", and that intent is what
   forces the column rather than tolerating it: under amendment 1 the
   merge gate is per-WP, so a table without `Verify` cannot say what
   check a given merge will run, and the plan stops being sufficient on
   its own. Rejected alternative: **encoding
   the raise inside `Scope` prose, or inferring it entirely from C-903's
   merge-time high-risk predicate.** Prose makes a mechanical value a
   substring to be parsed and cannot be inherited by sub-WP rows the way a
   column is — the same objection `adr_0004` raised against encoding `Repo`
   in `Expected Files`. Inference alone drops the author-judgment cases the
   predicate cannot see (a changed default, a schema, a config value nothing
   textually references), which is the column's entire reason to exist. The
   optional **`Verify-default:` Status line** rides the same amendment: it
   is a table-wide default, not a fourth column, and the mermaid index is
   unaffected. **A plan without either renders and reads exactly as today.**

**Considered and not deviated** (unchanged by this round): the **single
approval gate** — its count and its position are untouched; a checkpoint
is a *check*, never a gate, and asks nothing. The **depth-1 coordinator
invariant** is not merely untouched but **reaffirmed as a hard
requirement** (`adr_0010` C-914): no recursion ≥ 2, no new orchestrator
role, and state stays the one flat Parallelization table with computed
rollups — the new schedule log is held to it explicitly, one section per
plan and never one per coordinator. **Capability classes** — vacuously
upheld: this round adds no spawn, no role and no `models.md` row, and no
shipped file it touches names a literal model or a harness tool. **`hex
never pushes` / `hex never commits` outside execution** — untouched;
round 10's scoping stands as written. **The two-layer knowledge model**
is upheld: the selective-test command is Layer-1 project context with a
`hex.md › Pointers` row (it is "how to verify", the model's own worked
example), and the sensitive-path convention is a Layer-1 project fact
reached through a `hex.md › Pointers` row — hex authors neither as its
own config, and C-917 records where each lives rather than what either
says. **`adr_0005`'s fold path** is untouched: `hex-review` still writes
only the Status block, the convergence check, and — on an approved
converged fold — the spec file and receipt; C-401 and C-412 are unchanged
and C-410's exclusive ownership of the terminal review state — `done`, or
`landing` for a plan carrying a `Repo` column — gains one precondition (a
run with stranded WPs does not reach it) rather than a second writer.
**`adr_0004`'s federation contracts** are unchanged: per-repo
verification (C-321) and global merge serialization (C-306) both apply to
the scoped check verbatim. **Thin dispatchers + per-tier phase files** —
no tier file gains a rule; two take a one-clause qualifier and the rest
are untouched. **`config.md` gains no key** and its `<skill>` enumeration
is not reopened.

**Erratum pointer (2026-09-05):** round 14 (§ Execution-performance quick-wins round, below) amends this round by pointer, bytes intact: amendment 2's `Verify` cell now sets the Review-Fix-Loop exit gate that immediately precedes the merge it already governs as well (`adr_0010` C-905 → C-924), the Implement-phase gate amendment 1's contract declared unchanged becomes the scoped check at every tier (`adr_0010` C-901 → C-925), and the closing "`config.md` gains no key" audit clause is superseded by C-921's additive `limits.adversary-timeout` — true as of this round's date, and left as written. Amendment 1's final-gate clause is unchanged and is preserved verbatim by C-926.

## Adversary no-review round (2026-09-04, round 13)

`adr_0011` (nox — multi-harness adversarial review) amends **one position
in § Adversary contract**, in place. The bullet's enumeration is a live
lock — every tier file and overlay in the bundle restates it — so this is
an in-place amendment rather than an erratum pointer, following round 12's
adjudication for the *Plan visualization* lock.

The change was **already shipped** by that plan's WP13 and is recorded here
retroactively; § Process defect below is the more important half of this
round.

1. **"Graceful skip when the named skill is unavailable" becomes
   "graceful skip whenever the adversary produced no review."** The
   round-1 rule above named one cause — the skill is not installed — and
   `hex/hex-core/references/protocol.md` § Adversary contract now names
   two: unavailable, **or** it ran and did not complete a review (could
   not reach its harness, was refused credentials or quota, ran out of
   time, or returned something it could not itself classify). Each
   adversary skill states its own outcome vocabulary; the contract reads
   it there rather than enumerating one centrally, which is what keeps
   this symmetric across clients.

   **The reason for the widening is that the narrow clause was
   exploitable by accident** (`adr_0011` E45): a cross-model adversary
   that runs and fails reports zero findings, and zero findings read as
   agreement. The skip path — the one thing that makes a missed review
   *visible* at tier `high` — fired only for the one cause the operator
   was least likely to hit. Every other cause degraded silently into a
   clean pass. The widened clause is strictly safer: it can only convert
   a silent pass into a logged skip, never the reverse.

2. **New normative rule: an empty finding list is never a clean pass.**
   A "triage is complete" gate is satisfied by exactly two things — the
   triage of a review that completed, or a logged skip — and never by an
   untriaged emptiness. This is the enforcement half of (1); without it
   the widened clause is advice a reader can decline to take, because
   nothing downstream distinguishes "reviewed, found nothing" from "did
   not review".

**Restated across the bundle, unchanged in substance**, because the
degrade clause is quoted rather than referenced in the per-tier files:
`hex-plan/{overlays,tier-high}.md`, `hex-execute/{overlays,tier-high}.md`,
`hex-review/{overlays,tier-high,tier-medium}.md`,
`hex-architect/{overlays,tier-high}.md`. Ten files in total including
`protocol.md`, which owns the contract; the nine restatements say
"produces no review" where they said "is unavailable" and change nothing
else.

### Process defect (the reason this round exists)

The widening reached `main` with `adr_0011`'s `## Constitution
Deviations` block still reading "None" and this file unamended. The
mechanism was not an oversight in the deviations block itself — it was
**an undeclared file set upstream of it**. WP13's `Expected Files` cell
declared two `hex/` paths; the merge carried thirteen. Nothing compares
a work package's declared file set against the diff it lands, so a
change that touches the constitution can arrive inside a work package
scoped to something else, and the block that would have caught it is
never consulted because nothing said the constitution was in play.

The general rule this round establishes: **a work package whose landed
diff touches a path outside its declared `Expected Files` set has not
been reviewed against the constitution, whatever its review budget
says.** Declaring the set is not bookkeeping; it is the trigger for the
deviations check.

**Upholds.** **The one-hop spawn requirement** (`adr_0010` C-914) —
vacuously upheld: no spawn, no role, no `models.md` row. **Capability
classes** — upheld; no shipped file this round touches names a literal
model or a harness tool (the widened clause deliberately delegates the
outcome vocabulary to the adversary skill rather than enumerating one,
which is the same generalization the De-OCX checklist applies to
"pluggable adversary skill named in `hex.md › Preferences`").
**`hex never pushes` / `hex never commits` outside execution** —
untouched. **The two-layer knowledge model** — untouched; the contract
is Layer-0 hex protocol, and nothing moves into or out of project
context. **`adr_0005`'s fold path** — untouched; `hex-review` still
writes only the Status block, the convergence check, and — on an
approved converged fold — the spec file and receipt. **Thin dispatchers
+ per-tier phase files** — upheld in shape and weakened in practice: the
nine restatements are exactly the copy this constitution's
single-source rule exists to prevent, and they are why a one-line
contract change became a ten-file diff. Recorded as a known cost, not
repaired here — the repair is for `protocol.md` to own the sentence and
the tier files to link it, which is a `hex/` change outside `adr_0011`'s
scope. **`config.md` gains no key.**

## Execution-performance quick-wins round (2026-09-05, round 14)

The Wave 0 quick-wins plan
(`.agents/plans/plan_wave0_quick_wins.md`) amends **three positions
recorded above** — two of round 12's and the standing frozen-vocabulary
audit clause — and lands **one repair round 13 prescribed**. There is no
ADR: every item amends a decision `adr_0010` or `adr_0003` already
adjudicated, none opens a new door, and the plan's own
§ Constitution Deviations carries the full adjudication. All three
amendments supersede **by pointer**: round 12's text is left as written
and its region gains one erratum pointer, per round 11's convention, and
the `config.md` gains no key clause — stated across rounds 9 through
13, grounded in round 6's frozen v1 vocabulary — is amended here rather
than at each of those five sites, each of which is true as of its own
date and stays as written. The wall-clock cost this round exists to cut
is measured in
`.agents/research/rca-review-fix-loop-wall-clock.md`.

1. **The `Verify` cell's reach widens by exactly one adjacent gate.**
   Round 12's amendment 2 shipped the budget-column family, whose
   `Verify` member "sets the WP's **merge gate** (C-901) and nothing
   else" (`adr_0010` C-905, shipped in `protocol.md` § Parallel-by-default
   decomposition). C-924 replaces "and nothing else" with **one
   verification budget for one merge boundary**: the cell sets that WP's
   merge gate **and the Review-Fix-Loop exit gate that immediately
   precedes it**, and nothing beyond those two. The superseded clause was
   written when the merge gate was the only scoped-check site; running the
   project's full documented verification at the loop exit and then a
   scoped check at the merge moments later is incoherent, and that pair is
   exactly where the RCA measures the cost. **What round 12 actually
   defends is preserved verbatim** — "the final gate is unchanged,
   mandatory, and un-lowerable by any per-WP budget" — because C-926
   separates two gates that clause was being read across: the loop's exit
   gate fires **once per work package, in that WP's own worktree, before
   merge**, while the plan's terminal verification is a separate gate,
   mandatory, un-lowerable, and reached by every run that completes. No
   budget cell can lower it, and none could before. Rejected alternative:
   **coupling the Implement-phase gate to the same cell**, which makes a
   `Verify: full` work package pay three full documented runs for one WP —
   Implement, loop exit, merge — where the one at the merge boundary is
   the check that matters; the Implement gate is deliberately left
   uncoupled (item 2), which is what holds this amendment to one adjacent
   gate rather than two. Also rejected: **a second per-WP verification
   column** for the loop gate, which would reopen the live *Plan
   visualization* column lock a fourth time for no gain in expressiveness,
   and **inferring the budget from WP size**, which round 12 already
   settled — inference "drops the author-judgment cases the predicate
   cannot see". **The sole definition site is `protocol.md`
   § Parallel-by-default decomposition** (the cell's grammar and its two
   gates), with § Verification › Scoped check enumerating the sites that
   run the check; the `hex-execute` tier files **link** both and restate
   neither (C-927), and every site whose sentence stays true is untouched.

2. **The Implement-phase gate becomes the scoped check, unconditionally
   at every tier.** `adr_0010` C-901 states "**The Implement-phase
   verification is not this gate and does not change**", and grounds it in
   `protocol.md` § The Review-Fix Loop phase 3 "already reads *for changed
   files*". C-925 changes it: phase 3 runs the **scoped check** — the WP's
   own contract tests plus the project's cheapest documented assembly gate
   — at every tier, replacing all three shipped phrasings ("for changed
   files", "each work package's changed files", "across the whole
   workspace") with one vocabulary. **The reason C-901 gave is preserved
   and sharpened, not discarded**: "for changed files" was the scoped idea
   without a name, and naming it retires two competing phrasings rather
   than adding a fourth. The superseded sentence is a scope statement
   about `adr_0010`'s own delta — what that ADR did not touch — never a
   policy that the Implement gate must stay as it was. The
   leaf-under-coordinator compile-only carve-out is unchanged. **What tier
   `high` gives up is stated, and its backstop is named rather than
   assumed**: it loses its only pre-merge whole-workspace proof, and what
   catches a defect in a module no work package touched is checkpoint
   trigger (ii) — `M = 3` merges, a cleared dependency level, or a
   high-risk merge, whichever fires first — with `adr_0010` C-904's
   bounded bisection attributing the failure across at most three merges,
   trigger (i) at a coordinator join, and the terminal final gate.
   Rejected alternative: **keeping the tier-conditional Implement gate**
   (whole workspace at `high`, changed files below), which pays the full
   workspace at the phase that repeats most often in a run and is the
   three-phrasing drift the rewrite exists to end. Also rejected:
   **making the Implement gate follow the `Verify` cell**, item 1's
   rejected coupling, for the same arithmetic. **The sole definition
   site is `protocol.md` § Verification › Scoped check**, which now
   enumerates its three gate sites; § The Review-Fix Loop phase 3 links
   it, and the three `hex-execute` tier files link rather than restate
   (C-927).

3. **The frozen six-key config vocabulary admits one additive key:
   `limits.adversary-timeout`.** `adr_0003` C-203 owns the key vocabulary
   and C-223 froze its v1 at six top-level keys at the first
   `grim release`, and five rounds above state "`config.md` gains no
   key". C-921 adds
   `limits.adversary-timeout` — integer minutes ≥ 1, default per liveness
   class (`semantic` 2, `byte_activity` 5), **ceiling semantics like every
   other limit** (a project value below the resolved class default lowers
   the window; above it clamps to that default and the clamp prints on the
   gate's `Limits:` line) — carrying the stall bound C-920 states in
   § Adversary contract. **The freeze's stated harm is renaming** —
   "renaming a frozen key is a silent no-op in every consumer `hex.md`" —
   and this is **additive under an existing frozen top-level key**,
   neither a rename nor a seventh key: a reader predating it meets an
   unknown key under `limits` and degrades correctly by merge rule 8
   (warn once, ignore, continue) to the resolved liveness-class default, so
   no consumer `hex.md` breaks and **`config.md`'s
   `# hex config, vocabulary vN` comment is unchanged**. Rejected
   alternative: **a fixed bound with no escape**, which leaves a project
   whose adversary is genuinely slow — a large diff, a cold harness, a
   rate-limited account — no way out except unpinning the skill, turning a
   tunable into an abandonment. Also rejected: **Preferences prose**, the
   carrier C-918 chose for `M = 3`: that posture fits a shipped constant no
   project is expected to vary, while a stall window against a
   third-party harness is precisely the value that varies by project and
   machine. And **a new top-level key**, which would bump the vocabulary
   version for a value that already has a home. **The sole definition
   site is `config.md` § Key vocabulary**; `memory.md`'s Preferences row
   enumerates it, and the bound itself is defined once in `protocol.md`
   § Adversary contract, which every tier file links and none restates
   (C-923).

**Round 13's prescribed repair, landed — not a fourth deviation.** Round
13 recorded the single-source rule as "upheld in shape and weakened in
practice" and named the repair: "for `protocol.md` to own the sentence and
the tier files to link it". C-928 does exactly that for the review-budget
guard, and states it in **both directions** with the WP's declared
`Expected Files` set as the discriminator in each: **upward** — `self` or
`light` on a security-sensitive, hot-path, large or cross-area WP is a
plan defect, unchanged in substance — and **downward** — `panel` on a size
S or M, single-area WP whose file set carries no security-sensitive and no
hot-path file is equally a plan defect. Both are raised as actionable
findings at the Decompose gate, never at merge time, where the existing
budget re-validation only escalates a budget the actual diff outgrew.
**This is not a fourth deviation from a locked position**: the `Review`
column is still lower-only against the tier's panel baseline and the
direction rule is untouched — what is new is that *leaving* the baseline
where the file set does not warrant it is now nameable, which the
2026-07-20 perf pass already implied in shipping review breadth that
"scales with WP size, not plan tier alone" and never wrote down. The three
`hex-plan` tier files' two byte-identical restatements and tier-low's
narrower one-direction sentence are deleted in favour of a link (C-929),
and the same discipline lands for the adversary bound (C-923) and the two
verification gates (C-927).

**Considered and not deviated** (unchanged by this round): the **single
approval gate** — its count and its position are untouched; nothing here
asks the user anything, and the budget histogram prints inside gates that
already exist. **Capability classes** — vacuously upheld: no spawn, no
role, no `models.md` row, and no shipped file this round touches names a
literal model or a harness tool; the stall bound is stated in minutes
against the *pluggable* adversary skill named in `hex.md › Preferences`,
never against a named harness, and the reason vocabulary stays the
skill's own. **The two-layer knowledge model** — untouched:
`limits.adversary-timeout` bounds hex's own waiting, which is Layer-0
protocol and not a project fact, and the budget guard's discriminator is
the plan's own `Expected Files` cell rather than anything hex authors
about the project. **`hex never pushes` / `hex never commits` outside
execution** — untouched; round 10's scoping stands as written. **The
depth-1 coordinator invariant and one-hop spawn** (`adr_0010` C-914) —
vacuously upheld: no new role, no recursion ≥ 2, no per-coordinator state;
the brief-excerpt rule constrains what a leaf is *handed*, never who may
spawn it. **`adr_0004`'s federation contracts** are unchanged: per-repo
verification (C-321) and global merge serialization (C-306) apply to the
scoped check verbatim at both of its new in-worktree sites. **`adr_0005`'s
fold path** — untouched: `hex-review` still writes only the Status block,
the convergence check, and — on an approved converged fold — the spec file
and receipt; C-401, C-410 and C-412 are unchanged. **The *Plan
visualization* lock** — not reopened: no column is added, renamed or
moved, and the canonical enumeration is byte-identical. Only the `Verify`
**cell's** reach widens (item 1), which is why this round is not a fifth
amendment to that lock. **The adversary contract's graceful skip** —
unchanged as round 13 left it: the stall bound adds a new *cause*
routed into the existing skip rather than a second skip path, an empty
finding list is still never a clean pass, and C-922 keeps the passthrough
rule intact — a skill that names its own outcome is logged with the
skill's word, and `deadline` is written only where hex saw the stall window
pass with no progress signal.

**Touched, and recorded above** — five positions, and the direction each
moves: the `Verify` cell's merge-gate scope (item 1) and the
Implement-phase gate (item 2), both amendments to `adr_0010`; the frozen
config vocabulary (item 3), amended additively; and the
parallel-by-default lock's budget guard together with the **single-source
rule** (the repair paragraph), the one pair this round moves *toward*
rather than away from — three restatement families become links, no tier
file gains a rule, and round 13's recorded cost is paid down rather than
merely noted again.

**Erratum pointer (2026-09-05):** round 15 (§ Adversary liveness round,
below) amends this round by pointer, bytes intact: C-921's per-class
default enumeration ("`semantic` 2, `byte_activity` 5") is widened to three
classes with `process_only` — the default and fail-safe class — taking a
**20-minute total wall-clock backstop** the same key governs, and the
*Considered and not deviated* clause scoping `deadline` to "where hex saw
the stall window pass with no progress signal" is widened to whichever
bound the resolved class takes. Both are true as of this round's date and
are left as written; C-923's single-source rule for the bound is unchanged,
and this round's ceiling semantics and additive-key adjudication carry over
verbatim.

## Adversary liveness round (2026-09-05, round 15)

The Wave 0 quick-wins plan's WP 17 amends **one position recorded above** —
round 14's C-921 and the `deadline` scoping that accompanies it. There is
no ADR: the change repairs C-920 / C-922 against a capability hex does not
have, inside a contract `adr_0003` and `adr_0010` already adjudicated, and
opens no new door. Like round 13, the change was **already shipped** by WP
17 and is recorded here retroactively; the amendment supersedes **by
pointer** — round 14's text is left as written and its region gains one
erratum pointer.

1. **`process_only` is the default class, and it takes a backstop, not a
   stall window.** Round 14 enumerated two classes and was silent on a
   third, which the contract it recorded held outside the key as a fixed
   15-minute fallback. What ships is three classes — `semantic` (2 min
   stall window), `byte_activity` (5 min stall window), `process_only`
   (**no stall window; a 20-minute total wall clock over the whole call**)
   — and **`limits.adversary-timeout` governs whichever bound the resolved
   class takes, `process_only` included**, under the same ceiling semantics
   round 14 adjudicated. The superseded shape was written on the assumption
   that hex could observe an adversary's progress. It cannot: an adversary
   is a pluggable external skill, not a hex worker; it writes no heartbeat,
   and a one-shot skill call returns once, so between the call and the
   return there is nothing to poll. **A class above `process_only`
   therefore resolves only where the skill's own docs or outcome vocabulary
   name *both* the class and the progress surface hex reads to observe it;
   absent either it is `process_only`** — a bare class claim with no named
   surface would have hex counting silence it cannot hear. `adr_0013`
   (execution runtime contracts, **Proposed**) § A. The liveness contract
   weighed reading a child's output stream and demoted it; its heartbeat
   contract governs hex's **own** workers and this is the external-skill
   case it cannot reach. The accepted cost is stated: a truly hung
   adversary is abandoned at the backstop rather than at a stall window.
   **No shipped file classifies any adversary skill by name** — the class
   is resolved per run from the pinned skill's own docs, never asserted
   about it in hex's text.

2. **`deadline` follows the bound, and `process_only` is a disclosed
   race.** Round 14 recorded `deadline` as written "only where hex saw the
   stall window pass with no progress signal". It is written on the elapse
   of **whichever bound the class resolved to** — stall window or backstop.
   C-922's passthrough rule is otherwise intact: a skill that names its own
   outcome is logged with the skill's word, and neither bound launders the
   other **where hex has a stall window**. `process_only` is the **one
   disclosed exception**: with no progress signal its backstop measures the
   same quantity a skill's own timeout measures, so the two genuinely race,
   and a `deadline` logged under that class asserts only that **hex stopped
   waiting** — never that the adversary failed, timed out, or found
   nothing. Naming the exception is the deviation-free move; pretending to
   orthogonality hex cannot deliver is not.

**Announce site.** The `process_only` backstop is a total wall clock rather
than a stall bound, so it is **disclosed on the gate's `Limits:` line even
at its shipped default** — the third trigger for that line, alongside a
stored `hex.md` limit and a batched phase. The **single approval gate** is
untouched in count and position: the disclosure prints inside a gate that
already exists.

**Considered and not deviated** (unchanged by this round): **capability
classes** — vacuously upheld; the bound is stated in minutes against the
*pluggable* adversary skill named in `hex.md › Preferences`, never against
a named harness, and the reason vocabulary stays the skill's own. **The
two-layer knowledge model** — untouched: the bound governs hex's own
waiting, Layer-0 protocol, not a project fact. **The frozen config
vocabulary** — not reopened: no key is added, renamed or retyped;
`limits.adversary-timeout` gains a third class default under the meaning
round 14 already adjudicated. **Single-source contracts (C-923)** — upheld
and relied on: `protocol.md` § Adversary contract stays the sole definition
site, and `config.md`, `memory.md` and every tier file link rather than
restate. **The adversary contract's graceful skip** — unchanged as round 13
left it: the backstop routes a new *cause* into the existing skip rather
than adding a second skip path, and an empty finding list is still never a
clean pass. **`hex never pushes` / `hex never commits` outside execution**
and **`adr_0004`'s federation contracts** — untouched.

**Touched, and recorded above** — one position: round 14's C-921 per-class
default and the `deadline` scoping beside it, both widened rather than
reversed. The direction is *toward* the single-source rule, not away from
it: the classes, their defaults, how a class resolves and the `deadline`
condition all live at one site, and the record catch-up this round
necessitates is the removal of the restatements that had drifted.

**Erratum pointer (2026-09-05):** round 16 (§ Adversary observation-mode
round, below) amends this round by pointer, bytes intact: the *liveness
class* this round made the carrier of the bound is replaced by the
**observation mode of the call**. Item 1's three-class enumeration and its
`process_only` total wall clock become (a) skill-enforced, (b) pollable
background and (c) foreground blocking, whose fixed 15-minute backstop sits
**outside** `limits.adversary-timeout` — the key narrows to (b)'s stall
window, measured from last output growth rather than from invocation. Item
2's disclosed race is rescoped from a class to mode (c), and the *Announce
site* paragraph's `Limits:`-line disclosure becomes a `Degraded:` line.
Round 15's rule that **no shipped file classifies any adversary skill by
name** narrows to what it was defending — a *liveness class* asserted about
a skill's internals. Naming a skill to illustrate how hex *invokes* it
falls outside that rule, which is why round 16's contract may say
`codex:rescue`
is mode (c) as a foreground subagent and mode (b) when the orchestrator
backgrounds it. Both are true as of this round's date and are left as
written; C-923's single-source rule and round 14's ceiling semantics carry
over verbatim.

## Adversary observation-mode round (2026-09-05, round 16)

The Wave 0 quick-wins plan's WP 17b amends **one position recorded
above** — round 15's item 1, the `deadline` scoping in its item 2 and its
*Announce site* paragraph — on an owner override of round 15's concession.
There is no ADR: the change repairs C-920 / C-921 / C-922 inside a contract
`adr_0003` and `adr_0010` already adjudicated, opens no new door, and moves
no gate. The amendment supersedes
**by pointer**, per round 11's convention: round 15's text is left as
written and its region gains one erratum pointer.

1. **The bound comes from the adversary's own published contract where it
   states one, and otherwise from how hex invoked the call — never from a
   class the skill claims.** Round 15 conceded that hex can observe nothing
   between call and return and therefore made `process_only` the default
   with a 20-minute total wall clock the key governed. The concession is
   too broad: it is true of a *blocking* call and false of a background
   one. What ships is three observation modes, resolved per run — **(a)
   skill-enforced**, where the skill runs under its own liveness policy and
   reports the outcome (`nox-review`'s published contract bounds a review
   at 900 s of wall clock and 120 s of silence and reports `reason:
   timed_out`), so hex trusts that verdict and keeps only the same fixed
   15-minute backstop, **started by the elapse of the skill's own published
   bound rather than at invocation**, against a skill *process* that never
   returned after that bound should have fired; **(b) pollable
   background**, where the call runs as a background task whose output the
   orchestrator reads
   without blocking, so hex observes `byte_activity` and the stall window
   runs from the **last output growth, never from invocation**; and **(c)
   foreground blocking**, where silence genuinely is unobservable, so a
   fixed **15-minute** wall clock stands in and the contract tells the
   orchestrator to prefer (b) wherever the harness offers it. **The rule is
   a stall bound wherever silence is observable, and a total wall clock
   only where it is not.** Rejected alternative: **keeping round 15's
   single `process_only` default**, which prices every adversary at the
   worst harness hex might be running on and makes the pollable case pay
   for the blocking one. Also rejected: **a per-skill class table in
   shipped text**, which round 15 removed for good reason — a mode is
   a property of the *call*, which hex knows, so classifying `codex:rescue`
   as (c) today, or (b) when the orchestrator backgrounds it, asserts
   nothing about the skill's internals. Also rejected: **running (a)'s
   backstop from invocation**, which is what "never double-count" cannot
   survive — a skill whose own wall clock is 15 minutes, or any project that
   raises it, would have hex stop waiting at or before the skill's own bound
   and write `deadline` over the verdict the skill was about to report,
   which is the laundering this round exists to prevent. Starting hex's
   clock at that bound's elapse makes the backstop reach only a process that
   never returned when it should have. **The sole definition site is
   `protocol.md` § Adversary contract** (C-923 unchanged); every tier file
   and reference links it and restates none of it.

2. **`limits.adversary-timeout` narrows to the mode-(b) stall window.**
   Round 14 gave the key two per-class defaults and round 15 widened it to
   govern "whichever bound the resolved class takes, `process_only`
   included". C-921 now scopes it to one thing — the stall window hex
   measures over a pollable background call, default **5** — and states
   that mode (c)'s backstop is **fixed and not this key**, because there is
   nothing to observe and therefore nothing to tune. **The frozen config
   vocabulary is not reopened**: no key is added, renamed or retyped, and
   round 14's ceiling semantics and additive-key adjudication carry over
   verbatim — a value below 5 lowers the window, a value above it clamps,
   and the clamp prints under the existing clamp grammar. Rejected
   alternative: **a second key for the (c) backstop**, which would be a
   knob over an unobservable quantity and would bump the vocabulary for a
   value no project can usefully vary.

3. **`deadline` follows the mode, and only mode (c) is the disclosed
   race.** Round 15 scoped orthogonality to "where hex has a stall window"
   and named `process_only` the exception. Under the modes: **(a)** hex
   defers to the skill's verdict outright and writes no `deadline` for a
   call the skill's own bound reached, hex's clock not starting until that
   bound has elapsed unheard; **(b)** is genuinely orthogonal — a
   skill's own `timed_out` bounds its run from the inside, hex's `deadline`
   is silence hex *actually observed* over the output, so neither launders
   the other; **(c)** is the race — with no observable output the backstop
   measures the same quantity a skill's own timeout would, so a `deadline`
   logged there asserts only that **hex stopped waiting**, never that the
   adversary failed, timed out, or found nothing. C-922's passthrough rule
   is otherwise intact: an outcome the skill reported is logged with the
   skill's own word in every mode.

**Announce site.** Round 15 disclosed the backstop on the gate's `Limits:`
line as that line's third trigger. It is a degrade, not a limit, so it
moves to a **`Degraded:` line** — `Degraded: blocking adversary call — no
pollable output; process_only backstop 15 min` — under the rule already
shipped for every other gated capability: one line per degraded axis, and
they stack. The `Limits:` line returns to its two triggers, and its
closed attribution-source list drops the `shipped default` entry added
solely for the withdrawn item. The **single approval gate** is untouched in
count and position: the disclosure prints inside a gate that already
exists, and no new mechanism is introduced.

**Considered and not deviated** (unchanged by this round): **capability
classes** — upheld and, on the narrow reading, strengthened: the modes are
capability classes of the *call* (blocking versus pollable background),
never harness primitive names, and `codex:rescue` appears only as an
example of how hex invokes a skill, with both readings stated. Round 15's
**no shipped file classifies any adversary skill by name** is upheld for
`nox-review` too: the shipped contract cites its published § How long a
review takes and states none of its figures, so no shipped file asserts
that skill's internals or pins a number a project can retune. The figures
appear in this record and in the plan, dated, which is what a record does. **The
two-layer knowledge model** — untouched: the bound governs hex's own
waiting, Layer-0 protocol, not a project fact. **Single-source contracts
(C-923)** — upheld and relied on: `protocol.md` § Adversary contract stays
the sole definition site; `config.md`, `memory.md`, the four `overlays.md`
enumerations and every tier file link or name rather than restate, and the
overlay enumerations gain the second bound's *name* and no substance.
**The adversary contract's graceful skip** — unchanged as round 13 left
it: both kinds of bound route the same cause into the existing skip, and
an empty finding list is still never a clean pass. **The frozen config
vocabulary** — not reopened (item 2). **`hex never pushes` / `hex never
commits` outside execution** and **`adr_0004`'s federation contracts** —
untouched.

**Touched, and recorded above** — one position: round 15's item 1, the
`deadline` scoping beside it and its *Announce site* paragraph, narrowed
rather than reversed. The direction
is *toward* honesty about what hex can see: round 15 removed a claim hex
could not support, and this round removes the over-correction it left —
a total wall clock applied where silence is in fact observable.

**Erratum (2026-09-05, review):** this round's item 1 states mode (a)'s and
mode (c)'s fixed 15-minute backstop unconditionally; item 2 and the
*Announce site* paragraph carry that framing forward, as does round 15's
erratum pointer above. The backstop binds only where the invocation itself
carries a **settable timeout** — a spawn hex handed a deadline it can
enforce. Where the spawn carries none, hex regains control only when the
call returns and the backstop is **nominal**: a bound hex documents but
cannot enforce. This is a consequence of the round's own *terminates
nothing* position rather than a new one, and it narrows the worked example
rather than the rule — `codex:rescue` as a foreground subagent is mode (c)
*and* the nominal case. The accepted cost is stated: an adversary that
hangs under such a call blocks the run until it returns. Corrected here
once rather than at each of the four sites above, each true as of its own
date and left as written; the shipped condition and its render live at
[`protocol.md` § Adversary contract](hex-core/references/adversary.md#adversary-contract).

## Per-WP effective-tier round (2026-09-06, round 17)

`adr_0012` (the per-WP effective tier — plan tier becomes a ceiling, each
work package derives its own) makes **four amendments — items 1, 2, 4 and
5 below**: **one position in § Worktrees**, **one canonical phase list in
`protocol.md`**, **one presence-checks-not-a-version-field rule in
`protocol.md`**, and **the thin-dispatcher / sole-definition rule as it
applies to `hex-execute`'s three tier files** (`adr_0010` C-916's *"No tier
file gains a rule"*). It **adds one new binding rule — item 3 — which
amends no existing position above**: the mandatory ceiling-tier branch
review as a precondition on the terminal review state. And it explicitly
**declines to amend two further positions** — the *Plan visualization*
lock, and `protocol.md`'s *"and nothing beyond those two"* on the `Verify`
cell. The § Worktrees amendment supersedes **by pointer**: the 2026-07-20
perf-pass addendum's bytes are left as written and the `### Worktrees`
region's existing erratum pointer gains one clause, per round 11's
convention and following the precedent that **round 12 already superseded
that same addendum by pointer** when it retro-claimed the Review budget
under `adr_0010` C-905. Full adjudication and the scored five-option
comparison: `adr_0012` § Considered Options.

1. **The per-WP Review budget's direction flips, and the plan tier becomes
   a ceiling rather than a baseline.** The 2026-07-20 addendum above added
   *"a per-WP Review budget (`self | light | panel`, **lower-only vs the
   tier baseline, missing = panel**) — review breadth now scales with WP
   size, not plan tier alone."* Its stated intent stands and is what this
   amendment completes; its mechanism does not. **Each work package now
   resolves an *effective tier* — derived from its declared size class, a
   closed set of four risk flags, and nothing else; never authored, never
   above the plan's tier — and the effective tier, not the plan tier,
   drives four axes: which phases run, which `models.md` cell each
   WP-scoped spawn reads, review breadth, and the loop-round cap.** The
   `Review` column survives with its **direction flipped**: `adr_0010`
   C-905's invariant — *a column whose baseline is the maximum may only
   lower; a column whose baseline is the minimum may only raise* — is
   **preserved by the flip, not broken by it**, because the derivation
   moved `Review`'s baseline off the maximum. `Review` is now raise-only
   against the derived breadth, capped at the ceiling; `panel` raises the
   WP to the ceiling and is the one explicit escape hatch; `self` and
   `light` are inert in a plan carrying the generation marker. **A risk
   flag whose source is absent, unreadable, or malformed reads `true`,
   never `false`** — fail-closed, on the AWS-IAM-implicit-deny /
   SELinux-enforcing precedent, and against GitHub CODEOWNERS' silent
   fail-open, which is the exact failure this forecloses. **`sec`
   additionally reads hex's own shipped triggers** — the `classify.md`
   structural markers for auth/crypto/signing paths, dependency manifests
   and CI workflows — as an independent disjunct: **a project may widen
   hex's security sensitivity, never subtract from it**, because at
   effective `low` the review set is `minimal` and the conditional
   `reviewer:security` cannot spawn at all. **The same `hex.md › Pointers`
   row feeds two consumers, and this round records the consequence rather
   than leaving it to be discovered: an attestation of an empty
   security-sensitive set buys tier reduction *and* silently disarms
   `adr_0010` C-903's high-risk checkpoint trigger.** The two absence
   semantics for that one row are reconciled by **residual risk, not by
   direction** — three independent backstops survive C-903's vacuous
   clause, one survives a fail-open reduction here. The consequence the
   round's compatibility rests on: **a project that has attested no
   security-sensitive or hot-path convention runs at the ceiling on every
   WP**, byte-identically to before this round **for plans whose `Review`
   cells are absent or `panel`** — where such a plan carries `self` or
   `light`, those cells go inert and it runs *more* review, never less.
   So the safe default costs nothing in coverage and the speedup is an
   opt-in bought with one attested line. Rejected alternative: **keeping
   the column authored and binding the four axes to it** — the downward
   guard (`panel` on a small flag-free WP declared a plan defect,
   `plan_wave0_quick_wins` C-928, which ships regardless) plus the phase
   collapse, model-class drop and round cap bound to `Review: self`. It
   **ties on wall clock** — both options need the phase collapse, which is
   the dominant lever — and loses by **fourteen points on a 125-point
   scale**, a margin resting entirely on two criteria: an authored cell
   that drives phases, model class, breadth and rounds **is a per-WP
   `Tier` column with a misleading header**, and binding new meaning to a
   cell already present in approved plans either reinterprets them
   silently or needs the same generation marker. **The choice is a
   judgment call and is recorded as one** (`adr_0012` § Judgment calls 8).
   Also rejected: **a per-WP authored `Tier` column** — author error is the
   traced root cause, and a fifth *Plan visualization* amendment for a
   value derivable from existing cells is a cost with no return. **The sole
   definition site is `protocol.md` § Parallel-by-default decomposition ›
   The effective tier**; `models.md`, `hex-execute/overlays.md`,
   `hex-review/classify.md` and the plan template link or take a
   one-clause qualifier, and **every site whose sentence stays true is
   untouched**. **The three `hex-execute` tier files are the stated
   exception, and this round files it as its own amendment rather than as
   a footnote here — item 5.**

2. **The canonical four-phase contract-first TDD list collapses to one
   spawn at effective tier `low`, against a check the builder cannot
   write.** `protocol.md` § The Review-Fix Loop's phases 1–3 (Stub,
   Specify, Implement) become a single `builder` spawn that **commits the
   stubs and the specification tests as its first commit on the WP branch,
   before the implementation commit**, and **the orchestrator runs the
   project's test command at that commit and requires failure**. A
   self-reported red→green transcript was the first draft's form and was
   **rejected on review**: it is produced by the same worker whose claim it
   checks, nothing re-runs it, and it is satisfied by writing the
   implementation first and stashing it — leaving the deviation with no
   defence, since its whole justification is that the property becomes
   checkable. The committed-stub form costs no round trip (the builder
   already commits; merge-time re-validation already shells out to `git`).
   `hex-execute/tier-low.md`'s *"Keep the contract-first TDD skeleton
   … unchanged"* becomes false and is amended. This is the round's largest
   wall-clock lever: three serial round trips become one, and pipeline
   depth stops being constant at every tier for the first time since round
   4. **The phases' properties are preserved and one of them is
   strengthened:** the surface is still written before the tests and the
   tests before the implementation, and *"they MUST fail against the
   stubs"* becomes **demonstrated by output** rather than assured by the
   fact that a separate `tester` could not see an implementation that did
   not exist. **What is given up is stated rather than argued away:
   author≠verifier at the work-package level.** The check recovers the
   temporal property, not independence; the backstops are the
   `review=minimal` batch's spec reviewer and the branch-level pass below.
   The collapse exists **only** at effective `low`. **The single spawn
   resolves all three source cells and reads the highest** — the shipped
   matrix has `builder:stub`, `builder:implement` and `tester` all
   `fast-balanced` at `low`, but `models.md` Rule 2 puts an instantiated
   `hex.md` matrix **above** the shipped default, so a project pinning any
   one of the three makes them disagree; taking the highest means
   collapsing never silently revokes a pin, and the raise is disclosed at
   the gate. No matrix row is added. Rejected alternative: **collapsing
   Stub into Specify only** — one trip of three, keeping the costliest
   hand-offs. Also rejected: **collapsing against the builder's own
   transcript**, above.

3. **A new binding rule, not an amendment — the collapsed path's backstop
   is made mechanical, reusing the one writer that already exists.** This
   item **amends no existing position above**; it adds one. It is numbered
   here with the amendments because it belongs to the same round, and it
   is classed separately because calling a new rule an amendment would
   leave the round's count wrong at three of its four statement sites.
   `protocol.md` already declares the branch-level `/hex-review` mandatory
   for any plan containing a `self` WP — as prose enforced by nothing.
   This round binds it: **a plan containing any WP whose effective tier
   fell below its ceiling does not reach its terminal review state
   (`done`, or `landing` when a `Repo` column is present) until a
   branch-level `/hex-review` has run at no less than the plan's ceiling
   tier**, the ceiling acting as a floor on the review's own classified
   tier and never as a cap. `/hex-review` is already the sole writer of
   that state (`adr_0005` C-410) and already carries one precondition of
   this shape (`adr_0010` C-913(f)), so this is a second precondition on
   the same write, not a second writer. **The ceiling floors an explicit
   `--tier` flag too** — `overlays.md` § Precedence would otherwise let a
   user flag lower it and remove the backstop with one argument — and the
   ceiling `T` is read from the plan's Status-block `Tier:`, never from
   `/hex-execute`'s run tier. This borrows the **discipline** every
   surveyed system pairs with a fast path (Zuul's gate re-testing
   regardless of the check pipeline, Gerrit's `Verified` submit
   requirement, CI smoke as pre-filter and never substitute) and **not
   their enforcement, which hex does not have**: hex never pushes outside
   `/hex-finalize`, whose gate is a human approval, so what this
   precondition blocks is a plan reaching `done` / `landing` — a markdown
   Status field, not a merge. Recorded plainly rather than left as an
   implied equivalence. The **runtime** half rides `adr_0010`'s existing
   merge-time budget re-validation, which becomes an effective-tier
   re-derivation against the actual diff — **including `hub`, re-derived
   from the actual changed-file list**, since a declared file set is
   repaired by widening it and therefore does not bound the actual one.

4. **The presence-checks-not-a-version-field rule takes one named
   exception.** `protocol.md` § Worktree work-package mechanics states
   *"there is no schema-version marker, the presence of the field is the
   signal"*, and it holds for every field it covers, each of which carries
   one meaning. **`- Effective-tier:` does not: it has a value space
   (`derived` in v1) and a hard refusal on anything else**, including a
   present-but-empty value, because a marker whose value hex cannot read
   means a plan written against a generation hex cannot execute. That is a
   version marker under another name and this round says so rather than
   burying it in prose. **What survives verbatim is the half the rule
   exists for: absence is never a version comparison** — an absent line is
   legacy semantics, permanently, with no prompt, no error, no migration
   and no rewrite. The value is a **literal, not a number to compare**, and
   a future generation takes a new literal rather than redefining
   `derived` — Go's own directive walk-back is the cited reason. The
   marker is read line-initial, above the first `##`, to the first field
   separator, trimmed and matched exactly, on `hex-architect/SKILL.md`'s
   shipped `State:` discipline; **a marker on a plan carrying no `Verify`
   column is refused**, because such a plan's blank `Review` cells would
   otherwise flip in bulk from `panel` to derived — the one unsafe
   direction of the flip.

5. **The thin-dispatcher / sole-definition rule takes one scoped
   amendment: `hex-execute`'s three tier files gain a rule, not a
   qualifier.** Round 12's *"no tier file gains a rule; two take a
   one-clause qualifier and the rest are untouched"*, round 13's repair
   (*"the repair is for `protocol.md` to own the sentence and the tier
   files to link it"*), and `adr_0010` **C-916's *"No tier file gains a
   rule"*** all say the same thing, and round 10 is where it starts, in
   that round's own words: *"the four bundle-wide restatement sites gain a
   one-clause qualifier pointing there, and every skill-, worker- and
   federation-scoped restatement is **unchanged, because it remains
   true**."* (The often-quoted *"a site either links or takes a one-clause
   qualifier"* is `adr_0010` C-916's **paraphrase** of that sentence, not
   this file's own words; it is cited here as C-916's and is not adopted
   as a self-quotation.) This round breaks the rule in exactly one place.
   `tier-low.md`'s *"Keep the contract-first TDD skeleton … unchanged"*
   becomes false and is rewritten (amendment 2); `tier-medium.md` and
   `tier-high.md` must **condition their phase sections on the *WP's*
   effective tier** rather than on the file they live in — **a behavioural
   rule, not a qualifier**, because a tier file's phase list stops being a
   property of the file. **It is filed as an amendment rather than as a
   note under "considered and not deviated", where the first draft put it:
   a rule is a deviation whatever heading it sits under.** **The intent is
   upheld while the letter is broken** — the function is defined **once**,
   in `protocol.md`, and the tier files carry only the conditioning, never
   a second copy. It is the one place this round spends dispatcher
   thinness, and it is spent because the phase list is exactly what the
   round exists to scale. `adr_0010` C-916's sentence takes an erratum
   (`adr_0012` § Interaction, erratum row 9).

**Considered and not deviated** (unchanged by this round): the ***Plan
visualization* lock is explicitly NOT amended** — this round adds **no
column**, every input being a cell or pointer that already exists, and the
one new artifact field is a Status-block line, for which `adr_0010`'s
`Reviewed:` is the standing precedent. That enumeration has been amended by
explicit act four times and a fifth was avoidable, so it was avoided;
recorded here rather than left as an absence, because four prior amendments
make "no amendment" the surprising outcome. **`protocol.md`'s *"and nothing
beyond those two"* on the `Verify` cell is likewise NOT amended.** Round 14
spent a whole amendment widening that cell's reach from one gate to two,
and the shipped sentence now reads that the cell *"sets one verification
budget for one merge boundary — the WP's merge gate … and the Review-Fix
Loop's exit gate that immediately precedes it, and nothing beyond those
two"*. This round's `door` flag **reads** that cell. **The sentence bounds
what the cell *sets*, and `door` sets nothing**: it adds no gate, changes
no verification budget, and runs no command — it blocks a tier reduction.
So the sentence stays true; `door` is a **third reader**, never a third
gate. **The cost is real and is stated rather than hidden**: `Verify: full`
becomes the plan table's most expensive cell, and an author who wants only
the one-way-door signal now pays for two verification gates to get it —
priced in `adr_0012` § Judgment calls 2, not repaired here, because the
alternative is a fifth flag with its own cell, its own *Plan
visualization* lock amendment and its own way of being mis-authored. A
reviewer of the shipped diff who reads "third consumer" as "third gate" is
reading the wrong half of the sentence; if that reading ever prevails it
becomes this round's item 6, and the question is settled in the record
rather than at each reading. The **single approval gate** — count and
position untouched; the derivation is computed before the gate and
disclosed *at* it, and asks nothing. The **depth-1 coordinator invariant**
(`adr_0010` C-914) — untouched and reaffirmed: no recursion ≥ 2, no new
orchestrator role, and **nothing is persisted at all**, so the flat-state
requirement is met by construction rather than by discipline. **Capability
classes** — upheld: `models.md` gains one clause about *which tier column a
cell is read from* and no literal model name appears in any changed shipped
file. **`hex never pushes` / `hex never commits` outside execution** —
untouched; round 10's scoping stands. **The two-layer knowledge model** —
upheld and load-bearing: the security-sensitive / hot-path convention is a
**Layer-1 project fact** reached through a `hex.md › Pointers` row, and hex
records **where** it lives, never what it says — the row carries a
location, never an inline glob set and never the literal `none`, so the
attestation itself lives in project truth and the Pointers row stays the
cache `memory.md` classes "never authoritative"; the fail-closed degrade is
what keeps hex from inventing Layer-1 knowledge it does not have.
**`adr_0005`'s fold path** — untouched; `hex-review` still writes only the
Status block, the convergence check, and — on an approved converged fold —
the spec file and receipt, and C-410's exclusive ownership of the terminal
review state gains one precondition rather than a second writer.
**`adr_0004`'s federation contracts** — unchanged: `hub` keys on
`(Repo, path)` for C-316's reason, and the per-repo verification rule and
global merge serialization are untouched. **Thin dispatchers + per-tier
phase files** — upheld **outside `hex-execute`'s tier files**: canonical
text lands once in `protocol.md` and every consumer takes a link or a
one-clause qualifier — the repair round 13 named when it recorded that nine
restatements turned a one-line contract change into a ten-file diff. **The
three `hex-execute` tier files are *not* in this list: they gain a rule,
and that is amendment 5 above, not a non-deviation.** **`config.md` gains
no key** and its frozen key vocabulary is not reopened.

## Execution-runtime round (2026-09-06, round 18)

`adr_0013` (the execution runtime — worker liveness, resource limits,
per-work-package sub-orchestration and run telemetry) amends **eight
positions recorded above**. The items below are numbered by **the ADR's
own amendment ledger rather than by position**, so the sequence runs **2
through 9** and **number 1 is dead** — it was withdrawn at the ADR's
design panel and is recorded as withdrawn at the end of this round, its
number never reused. Numbers 2–8 are the ADR's own; **number 9 is added by
the implementing plan**
(`.agents/plans/plan_adr_0013_runtime_contracts.md` § Constitution
Deviations) for a deviation the ADR did not record. Full adjudication, the
four scored option axes and the deferred findings: `adr_0013` § Considered
Options, § Constitution deviations / DESIGN.md amendments, and § Open
Questions. The **`config.md` gains no key** clause — stated across rounds
9 through 13 and again at round 17, and already amended once at round 14
item 3 — is amended here rather than at any of those sites, each of which
is true as of its own date and stays as written.

2. **Amendment 2 — ephemeral runtime state.** Amends `adr_0010` driver 5
   (*"No nested state files, at any depth"*) and `C-914`'s *"no
   per-coordinator state"* clause: a run may hold live agent state outside
   the checkout. **Boundary — four conditions, all of them**: the state is
   **ephemeral** (deleted by teardown, outside every checkout, never
   committed), **never authoritative**, **never read by resume**, and
   lives in **one flat directory per run**. A silent death is only
   detectable if something outside the dead agent records that it was
   alive, which is the whole reason the position moves. `C-912`'s four
   objections are answered or dissolved by those conditions: no split
   record, **zero gitignore lines**, teardown already exists for the
   scratch root, and resume still reads only the plan. Rejected
   alternative: **keeping all state in the plan** — a plan is committed,
   and a per-beat commit is a write storm on the one durable record. Also
   rejected: **a per-coordinator directory** — driver 5's flat surface is
   preserved literally here, not by analogy.

3. **Amendment 3 — the concurrency cap counts live model-compute.** Amends
   `protocol.md` § Worker coordination's recursive counting so that an
   agent in state `blocked` does not occupy a slot. **Boundary:**
   `blocked` is a **declared** state carrying a `blocked_on` value, never
   an inference; recursive counting, the effective cap `min(8,
   max-workers)`, the clamp and the federated single-lead read are
   unchanged. This is deadlock avoidance, not an optimization — charging a
   coordinator that waits on its own children against the pool those
   children draw from is the Airflow `SubDagOperator` deadlock, and the
   ADR's sub-orchestration part deadlocks by construction without it.
   Rejected alternative: **raising the cap instead** — it removes the
   bound rather than fixing the accounting, and the OOM evidence says the
   bound is needed. Also rejected: **inferring blocked-ness** — an
   inference cannot be audited at a merge gate.

4. **Amendment 4 — the coordinator gate splits in two.**
   `hex-execute/SKILL.md` § Coordinator spawn's single gate becomes **Q1**
   (does this work package get a coordinator — yes when the ready set
   holds ≥ 2 work packages and the harness can nest) and **Q2** (does it
   further decompose — the existing ≥ 3-independent-sub-task judgment,
   unchanged). **Boundary:** no new role, no new orchestration level, and
   **no change to the join *rules* or the file-set intersection check**;
   the Mission, Fan-out, Join and Tools/Model clauses gain a kind
   qualifier and the spawn prompt gains input lines, and both of those
   ride amendments 6 and 8 rather than this one. One gate had been
   answering two unrelated questions — *is this work package internally
   decomposable?* and *should its pipeline run concurrently with its
   siblings'?* — and conflating them is what leaves a ready package queued
   behind a sibling's review round. Rejected alternative: **a new
   sub-orchestrator role** — it adds a level, a state and a persona for
   behaviour the coordinator already has. Also rejected: **widening Q2's
   threshold** — it would force decomposition on work packages that are
   not decomposable.

5. **Amendment 5 — one artifact enters the bundle's set:**
   `hex-core/references/resources.md`, conditional-load. **Boundary:** a
   **reference file inside the existing `hex-core` skill directory** —
   `hex.toml` and `grimoire.toml` are untouched and no bundle member is
   added — read only when a run will issue a heavy command, so a
   parse-only project pays nothing for the contract. The resource contract
   has nine sections of knob-sheet and ladder detail; putting it in
   `protocol.md` would load all of it on every run of every skill for a
   contract most runs never exercise. Rejected alternative: **folding it
   into `protocol.md`** — rejected on load cost. Also rejected: **a second
   bundle member** — the packaging surface buys nothing the reference
   directory does not already give.

6. **Amendment 6 — every `coordinator-owned` rider keys on the
   *decomposing* kind.** Amends `protocol.md` § Worktree work-package
   mechanics (the full-verification `join` trigger), § Checkpoints (the `M
   = 3` counter reset), **§ Verification › Scoped check** (gate site 3 and
   the merge-site scope bullet) and **§ The Review-Fix Loop** (the
   leaf-under-a-coordinator carve-out, restated at § Scoped check, in
   `workers/builder.md` and in `workers/coordinator.md` — four copies in
   all) to read **decomposing**-coordinator-owned. **This changes
   `adr_0010` `C-901`'s firing condition** and is stated as such at the
   site. **Boundary:** only the firing condition moves — the scoped/full
   distinction, `M = 3`, `C-901`'s other triggers and `C-904`'s bisection
   walk are unchanged. Under Q1 every ready work package gets a
   coordinator; unretargeted, the merge riders make every merge pay a full
   verification run and reset the counter, and **the leaf carve-out
   degrades every Implement gate to a compile-only check** whose stated
   backstop — *the coordinator runs the one authoritative verification at
   the work-package join* — is false for a pipeline coordinator, which has
   no join. Rejected alternative: **leaving the riders on any
   coordinator** — it charges the full gate to work that did not decompose
   and removes the Implement gate from work that has no join to
   compensate. Also rejected: **deleting the triggers** — a decomposing
   coordinator's join genuinely warrants both.

7. **Amendment 7 — review breadth is decoupled from coordinator
   existence.** Deletes from `hex-execute/SKILL.md` § Coordinator spawn's
   WP-merge bullet the clauses *"a coordinator WP is by definition
   `panel`"* and *"`self`/`light` WPs never qualify for a coordinator"*,
   **keeping** *"`panel` = the tier baseline"*. **Boundary:** the `Review`
   cell's semantics, its lower-only budget and `adr_0012` `C-1112`'s
   `Review: panel` escape hatch are unchanged; only the
   coordinator-implies-`panel` inference is removed. Under Q1 every ready
   work package gets a coordinator, so the first clause would raise
   **every** package to `panel` and invert `adr_0010` `C-905`'s lower-only
   budget, and the second contradicts Q1 head-on. Breadth is a property of
   the work, not of who spawns the phases. Rejected alternative:
   **exempting `self`/`light` packages from coordinators** — it
   re-serializes exactly the small cheap packages this part exists to
   overlap. Also rejected: **reading breadth from the coordinator kind** —
   a second competing source for a value `C-905` and `adr_0012` already
   resolve.

8. **Amendment 8 — a pipeline coordinator's capability class follows the
   work package.** Amends `models.md`'s `coordinator` row and its rule-5
   tier gate: the matrix gains a **pipeline** row resolving per the work
   package's own effective tier with **all three cells filled** (never
   `—`), while the **decomposing** row keeps `deep-reasoning` and the
   medium/high gate. **Boundary: capability classes only — no literal
   model name enters `models.md`**; the decomposing row is unchanged, and
   `C-1109`'s `min(T, medium)` floor stays scoped to the decomposing kind.
   Under Q1 a `low`-tier work package would otherwise resolve against a
   cell reading `—` (*never spawned at that tier*), which is the exact
   unresolvable state the amendment exists to remove. Rejected
   alternative: **keeping one row for both kinds** — it either over-spends
   on trivial packages or leaves the gate unresolvable. Also rejected: **a
   literal model name**, which the constitution forbids and which was
   never considered.

9. **Amendment 9 (plan-added) — the frozen six-key config vocabulary
   admits a *second* additive key: `limits.heavy`.** **Boundary:**
   additive under the existing frozen `limits` top-level key, **neither a
   rename nor a seventh key**; `config.md`'s `# hex config, vocabulary vN`
   comment is **unchanged** and the key is marked **v1**. This is the
   identical move to round 14 item 3 (`limits.adversary-timeout`) and it
   needs the same adjudication rather than riding that one. The freeze's
   stated harm is **renaming**, and this is not a rename: a reader
   predating the key meets an unknown key under `limits` and degrades
   correctly by merge rule 8 to today's unbounded behaviour. Rejected
   alternative: **a plan-table column** — a plan travels between machines
   and this value is a property of the host, not of the work. Also
   rejected outright: **renaming `limits.max-workers`** — renaming a
   frozen key is a silent no-op in every consumer `hex.md`.

**Amendment 1 — withdrawn, its number kept dead.** No client-specific
enforcement is proposed. The carve-out would have been the first time hex
writes executable configuration, for a mechanism nothing requires and
nothing measures; `C-1209` is withdrawn with it, implemented by nothing
and carrying a negative check in the implementing plan instead. The number
is not reused, so the ADR's metadata, its § Constitution deviations table
and this round all state one set: **numbered 1 through 9, eight live
(2–9), amendment 1 withdrawn with `C-1209`**. Preserved as the ADR's
deferred finding **D-4**.

**Considered and not deviated** (unchanged by this round): **capability
classes** — untouched, and no literal model name appears at any site this
round writes. **Thin dispatchers + per-tier phase files** — upheld: the
liveness contract has one home in `protocol.md` § Worker liveness and the
resource contract one home in `resources.md`, and every other file takes a
link rather than a restatement. **Single-source contracts** — upheld:
`protocol.md` still owns the Review-Fix Loop, and the leaf carve-out's
four copies are retargeted in place rather than multiplied. **`hex never
pushes` / `hex never commits` outside execution** — untouched. **The
two-layer knowledge model** — upheld and load-bearing: the measured
resource profile is a **Layer-1 project fact** reached through a `hex.md ›
Pointers` row, so hex records where it lives and never invents it. **The
single approval gate** — untouched: the profile is measured at `/hex-init`
inside the existing consent-gated diff and no new gate is added. **No new
state file inside a checkout** — upheld in the strongest form available,
since nothing this round writes enters a checkout at all and **no
`.gitignore` line is added anywhere**. **`adr_0004`'s federation
contracts** — unchanged. **Plan visualization** — untouched: the `##
Schedule log` gains a second line kind, never a table column.

## Instruction-diet round (2026-09-06, round 19)

`adr_0014` (the instruction diet — `protocol.md` splits into a spine plus
six sibling topic files under `hex-core/references/`) **amends one
position recorded above and adds one new binding rule**. It changes no
runtime semantics anywhere: every moved byte is moved verbatim, every
heading is preserved, and the only text authored into the bundle is the
spine's two pointer tables. The amendment generalises the single-source
rule's *destination*; the new rule is **"Load only what runs"**, promoted
from worker personas to the contracts orchestrators read. The rest of
this round is record-keeping — the old→new section map that keeps three
prior ADRs' heading citations resolvable, and one measured budget miss
stated rather than engineered away. Full adjudication, the scored option
comparison and the per-mode byte table: `adr_0014` § Considered Options
and § Quantified Impact.

1. **Amendment — the single-source rule's destination becomes a property
   rather than a file name.** Round 17 states the rule as *"canonical
   text lands once in `protocol.md` and every consumer takes a link or a
   one-clause qualifier"*, and round 13 states the same repair in its own
   words (*"the repair is for `protocol.md` to own the sentence and the
   tier files to link it"*). It now reads: **canonical text lands once in
   `hex-core/references/`, in the topic file whose consumer set it
   serves**, and every consumer takes a link or a one-clause qualifier.
   **Boundary: the rule's substance is unchanged and unweakened** — one
   home per contract, consumers link and never restate, no contract
   gaining a second home. Only the sentence's hardcoded file name becomes
   a property of the contract. **This is a strengthening, not a
   loosening**: the destination stops being a name a reviewer can only
   memorize and becomes one they can check — *does this contract's
   consumer set match the file it lives in?* — which is the question the
   split itself was decided on. Rejected alternative: **one file per
   consumer** — it cannot express a two-consumer contract without copying
   it, which is the one thing the rule forbids. Also rejected: **leaving
   the destination hardcoded and moving nothing** — it keeps the name
   exact at the cost of the property the name was standing in for.
   **Rounds 13 and 17 are not edited.** A round is a record of what was
   decided when, and each of those sentences is true as of its own date;
   the amendment is stated here, once.

2. **New binding rule — "Load only what runs."** `hex/DESIGN.md` carries
   **no prior position at all** on file size, context budget or load
   scoping: the strings *"context budget"*, *"file size"* and *"load only
   what runs"* appear nowhere in rounds 1 through 18. **This round adds a
   position rather than amending one.** The rule already ships, for
   workers only, in `hex-core/references/workers.md` above `## Universal
   worker protocol`:

   > **Load only what runs**: the orchestrator always reads this index;
   > it reads a persona file only for roles in the resolved spawn set.

   Nine personas were split out of one index on exactly that reasoning.
   Round 19 extends it **one layer up, from worker personas to the
   contracts orchestrators read**, with the spine's load map as its
   table — the single definition site for what each mode opens.
   **Boundary: this is a budget rule, not a permission.** A mode may
   follow any link; it *opens* a topic file when a phase it is running
   executes against that contract, never because prose mentions it.
   Nothing enforces it — the budget is a review criterion, and that is
   recorded as its known cost, not repaired here.

3. **The old→new section map — the compatibility record.** Every heading
   below is preserved **byte-identical in text and in level**, which is
   why no past ADR needs an erratum and why every anchor slug survives
   the move; only the basename in front of the `#anchor` changes.

   | Heading (unchanged) | Now in |
   |---|---|
   | `## The Review-Fix Loop` | `loop.md` |
   | `### The last-reviewed anchor` | `loop.md` |
   | `### Anchor validation` | `loop.md` |
   | `### Delta round scope` | `loop.md` |
   | `### The diminishing-returns stop` | `loop.md` |
   | `## Convergence contract` | `loop.md` |
   | `## Parallel-by-default decomposition` | `decompose.md` |
   | `### The effective tier` | `decompose.md` |
   | `## Worktree work-package mechanics` | `worktree.md` |
   | `## Verification` | `verify.md` |
   | `### Scoped check` | `verify.md` |
   | `### Checkpoints` | `verify.md` |
   | `## Adversary contract` | `adversary.md` |
   | `## Finding severity` | `severity.md` |

   All six files are siblings of `protocol.md` in
   `hex-core/references/`. **What the table is for:** `adr_0010`,
   `adr_0012` and `adr_0013` cite these sections as *"`protocol.md` §
   <Heading>"* dozens of times between them, and `hex/CHANGELOG.md` does
   the same. **Those records are deliberately not edited**: they
   state what was decided against the file as it stood, and a record
   rewritten to match today's tree stops being a record. This table is
   how a reader resolves them. Line-number pins in `adr_0010` and
   `adr_0013` had already drifted before this ADR, by the project's own
   record, and are not repaired here either.

4. **This file's own citations are not rewritten either.** **Rounds 1
   through 18 cite a moved section as *"`protocol.md` § <Heading>"*
   eighteen times**, and every one of those lines stays as written, for
   the same reason the ADRs do: they are the record of what was decided
   when. The table in item 3 is their compatibility record — read them
   against it, not as drift. (The markdown link *targets* in those lines
   were repointed with the rest of the bundle, so nothing dead-ends; only
   the file name visible in past prose is historical.)

**The budget misses — known, bounded, and stated rather than engineered
away.** `adr_0014`'s target (C-975) is **≤50% of the pre-cut
protocol-family bytes for every orchestrator except `/hex-execute`**, and
≤15% for every worker persona. Measured against the merged tree, with each
closure walked from the mode's own files rather than read off the map,
**three rows miss**: `/hex-review` at 72.0%, `/hex-plan` at 70.5%, and the
`coordinator` persona at 70.5% against the ≤15% worker target — all three
only once the map was corrected to name what each mode really opens.

| Mode | Opens beyond the spine | Bytes | % of 149,072 |
|---|---|---:|---:|
| `/hex-architect` | `loop.md` | 73,012 | 49.0% |
| `/hex-finalize` | `verify.md` | 64,933 | 43.6% |
| `/hex-review` | `decompose.md`, `loop.md`, `severity.md` | 107,360 | **72.0%** |
| `/hex-plan` | `decompose.md`, `loop.md` | 105,158 | **70.5%** |
| `/hex-execute` | `decompose.md`, `worktree.md`, `loop.md`, `verify.md` | 140,076 | 94.0% |
| `builder` worker | `verify.md` only | 14,603 | 9.8% |
| `reviewer` worker | `severity.md` only | 2,202 | 1.5% |
| `coordinator` worker | the spine, `loop.md`, `decompose.md` | 105,158 | **70.5%** |

Conditionally: `adversary=on` adds 10,396 B to any row; a **federated**
`/hex-review` also opens `worktree.md` — 127,675 B / 85.6%.

Pre-cut, every row read 149,072 B. **Cause — two, not one.** `/hex-plan`
and `/hex-architect` each **run the Review-Fix Loop as a numbered phase at
every tier**, so both open `loop.md` (22,682 B); and `adr_0013` landed
`### Worker liveness` — 16,139 B, inside a `## Worker coordination` that
grew by ≈20 KB in all — **after** the target was set, and that section
stays in the spine, which every mode pays for. `/hex-review` opens both
plus `decompose.md`: its Approve cannot write the terminal review state
without deriving the **stranded set**, whose sole definition lives there.
The `coordinator` persona pays the same three: it opens the spine for
`§ Worker coordination` and `§ Worker liveness`, `loop.md` for the
leaf-verification carve-out, and `decompose.md` to re-run the file-set
intersection check.
**Why it is not fixed
here:** the split that would recover it promotes `### Worker liveness` to
its own topic file, and `adr_0014`'s own **C-970 forbids splitting any
`##` section internally** — the rule that keeps all three prior ADRs'
heading citations valid without editing one of them. Buying `/hex-plan`
≈10.8 points by breaking that is **the same trade the ADR already resolved
in `/hex-execute`'s favour**, where it states a 94.0% non-goal rather
than hitting a number by cutting inside a heading. `/hex-execute` remains
an **explicit non-goal**: it genuinely runs decomposition, worktree
mechanics, the loop and verification, and its diet is a different file
and a different ADR. **A follow-on round may promote `### Worker
liveness` to a seventh topic file** — `/hex-plan` and `coordinator` would
land at 59.7% and `/hex-review` at 61.2%, **still misses**, because
`loop.md` (22,682 B) is the larger of the two causes; closing them needs
the loop re-homed or the personas'
cited contracts moved, which is a follow-up ADR's call, not this round's.
The promotion is still the cheap kind of change the per-topic split was
decided for: one `##` boundary, one basename, no contract touched.

**Considered and not deviated** (unchanged by this round): **thin
dispatchers + per-tier phase files** — unchanged, and not even in scope:
the spine and all six topic files are Layer-0 reference text, not
dispatchers, and no `SKILL.md`, `classify.md`, `overlays.md` or tier file
gains or loses a rule. **Capability classes, never literal model names**
— upheld; no literal model name appears in any moved line or in any line
authored by this round. **The two-layer knowledge model** — untouched:
every moved section is Layer-0 hex protocol, nothing crosses into or out
of project context, and no Pointers row changes. **`config.md` gains no
key** and its frozen key vocabulary is not reopened. **No runtime
semantics change anywhere** — this is a relocation: no contract's text
changes, `§ Untrusted-text echoes` and every other spine section stay
where they are, and a run's behaviour before and after the cut is
identical.

## Review-by-join-level round (2026-09-06, round 20)

`adr_0015` (review by join level) **replaces the review half of round 17's
per-WP effective tier and retires two positions recorded above.** It
changes no execution semantics: phases and model class still scale with
the effective tier exactly as round 17 wrote them. What changes is *what
decides how deep a diff is reviewed*: no longer the tier, the per-WP
`Review` budget or a plan-wide ceiling, but **the join level** at which
the diff lands. Full adjudication and the option comparison: `adr_0015`
§ Considered Options; the contract itself is
[`loop.md` § Review by join level](hex-core/references/loop.md#review-by-join-level).

**The rule.** Four levels, closed and versioned (C-980). `L0` — every
builder return carries an evidence table (`<ID> → <path>:<line>`) the
orchestrator greps; no spawn. `L1` — one fast-balanced reviewer, delta-only,
one round, ten-minute budget, at every leaf join, at every tier. `L2` — one
deep-reasoning seat over the aggregate diff with the leaf verdicts as
inputs, **only where a node joins two or more leaves** (C-981); at `N = 1`
it is skipped and the `L1` verdict stands. `L3` — the trunk pass, only when
`/hex-review` is invoked. Risk (`sec`, `hot`, `door`, or an authored `risk`
cell) raises a WP **one level, never a round** (C-983). A level's wall-clock
budget ends its loop with residue recorded, never a failure (C-984). Seats,
class, rounds, budget and input scope are `review.<level>.*` keys — the
config vocabulary's v3 addition — overridden per level, never per role
(C-985).

**What it retires, by name** (C-986): the `self | light | panel` budget
column semantics and both halves of its guard (round 12, "a budget column
moves a WP away from the shipped default in exactly one direction" — the
`Verify` column keeps that discipline, `Review` leaves it and becomes a risk
hint); the `Review: panel`
escape hatch (round 17's resolution step 5); the branch-review precondition
and the `adr_0012 backstop` announce line (round 17, C-947); the "review
grows by diversity across join levels" three-scope model (round 18); and
every per-tier round cap and tier-scaled perspective panel in the execute
tier files. Nothing is renamed and no plan is migrated: a legacy cell is
read, `panel` as `risk`, `self` and `light` as nothing.

**The amendment to round 17's marker promise.** Round 17 wrote that a plan
without the generation marker runs pre-`adr_0012` semantics byte-for-byte,
forever. That promise now covers **execution** — phases, model class, the
collapse — and no longer covers review: every plan shape reviews by join
level. The reason is the one the round itself gave for the marker — a
review that silently changes depth in bulk is dangerous when it *reduces*;
this change reduces per-WP breadth but adds an `L1` where a `self` WP had
nothing and an `L2` where nothing aggregate existed, and the trunk pass it
removes was never a guarantee, only a precondition a human could satisfy
by running a lower tier.

**Why this and not "a little faster".** Wall clock was seats × rounds ×
WPs × round-trips, and every prior round trimmed one factor for one case.
Keying on join level bounds all four at once: `k` WPs cost `k`
parallel fast leaf reviews plus one deep aggregate, in minutes, at any
tier. The dogfood result that motivated it — a mid-sized merge request at
three days and a week of quota — is recorded in the ADR's Context.

**Considered and not deviated** (unchanged by this round): **single-source
contracts (C-923)** — upheld and strengthened: `loop.md` gains the one new
section and every other file links it; the retired text is deleted, not
paraphrased. **Thin dispatchers + per-tier phase files** — upheld: each
execute tier file's Phase 6 now states its checklist breadth and links the
level definitions. **Capability classes, never literal model names** —
upheld; `review.<level>.class` takes a class. **The two-layer knowledge
model** — untouched. **`config.md`'s frozen vocabulary** — v1 and v2 are
not reopened; `review` is the v3 addition and a v2 reader ignores it under
merge rule 8. **Load only what runs** (round 19) — upheld: a `reviewer`
spawn still reads `severity.md` only; the join-level table is the
orchestrator's to read.

## Parallel-adversary and checklist round (2026-09-06, round 21)

`adr_0016` (parallel adversary, review checklist, reviewer configuration)
**amends round 20 in one place and adds two things it left implicit.**
It changes no review level and no join rule: `L0`–`L3` stand as round 20
wrote them. Full adjudication: `adr_0016` § Considered Options; the
contracts are [`adversary.md`](hex-core/references/adversary.md#adversary-contract)
(launch and triage) and the new
[`checklist.md`](hex-core/references/checklist.md) (the shipped checklist
and its composition).

**The rule.** When `adversary=on`, the cross-model adversary **launches in
the same batch as the native seat of the join it gates** — the `L2`
aggregate seat, or the sole leaf's `L1` at `N = 1`, in `/hex-execute`; the
Stage 2 batch in `/hex-review`; the Round 1 panel batch in `/hex-plan` and
`/hex-architect` — native seats first, adversary last, no `max-workers`
slot, each under its own clock (C-987). Its actionable findings join that
join's **single builder fix pass**; duplicates merge with attribution; a
merged pass that fails verification is reverted, re-run native-only, and
the adversary findings deferred — never a re-invocation (C-988). Every
review brief carries a `Checklist:` slot the orchestrator composes from
`checklist.md`'s eight sections by join level — `L1` `spec` + `quality`,
`L2` per the `--review` axis, `L3` per seat focus, the inline orchestrator
`spec` + `quality` itself — and a seat answers every item or marks it not
applicable (C-989). `review.<level>.checklist` overrides the composition;
`/hex-init` seeds vocabulary v3 including the six `review.<level>.*` keys;
the Upkeep step names three Memory candidate classes a run may propose
(C-990).

**The amendment to round 20's bound.** Round 20 bounded the terminal join
at the aggregate seat's budget. It is now `max(aggregate, adversary)`: the
adversary's bound is the adversary contract's, orthogonal to
`review.<level>.budget-minutes`, and the join waits for both. Nothing
truncates either — hex can stop its own worker and cannot terminate an
external skill (round 13).

**Rejected: a project checklist file.** `.agents/review-checklist.md`
would be a third surface for what `perspectives.always` and the project's
own rules (universal rule 1) already reach through `hex.md › Pointers`.
Every composed brief names those rules; a project extends the checklist
there.

**Considered and not deviated** (unchanged by this round): **single-source
contracts (C-923)** — upheld: launch order and triage live in
`adversary.md`, the checklist in `checklist.md`, every tier file links.
**Thin dispatchers + per-tier phase files** — upheld; no heading renamed
(C-220). **Load only what runs** (round 19) — upheld and sharpened: the
load map gains one row, "any mode composing a review brief opens
`checklist.md`", and a `reviewer` spawn still opens `severity.md` only —
the orchestrator inlines the sections. **Capability classes, never
literal model names** — untouched. **`config.md`'s frozen vocabulary** —
v1 and v2 not reopened; `review.<level>.checklist` is a v3 leaf.

## Five-tier round (2026-09-06, round 22)

`adr_0017` (five-tier grammar) **supersedes the 2026-07-19 tier rename
recorded at the top of this file** and reopens the one thing that rename
froze: `xhigh` and `max` stop being reserved words. Full adjudication:
`adr_0017` § Considered Options; the grammar is
[`protocol.md` § Tier grammar](hex-core/references/protocol.md#tier-grammar).

**The shift map.** `low < medium < high < xhigh < max` plus `auto`. Old
`low` → `medium`, old `medium` → `high`, old `high` → `xhigh` — per skill
three `git mv` in a renames-only commit, headings byte-identical inside
each file, then the literal shift (C-992). Every pre-existing tier keeps
its behaviour under the new name. The effective-tier derivation is
renamed with it: `S` ⇒ `medium`, `M` ⇒ `high`, floors `min(T, high)`, the
collapse at effective `medium`; **effective `low` is never derived**
(C-993).

**Inline `low` (C-994).** Zero spawns — the orchestrator is the worker.
The classifier's new bottom row: one file, ≤30 lines, no structural
marker, no security-sensitive or hot path. `/hex-execute low` keeps the
stub-first commit ordering, writes its own `L0` evidence table, answers
the `spec` + `quality` checklist itself, and spawns one `L1` reviewer only
when a non-doc file changed — the author≠verifier backstop survives.
`/hex-review`, `/hex-plan` and `/hex-architect low` are the orchestrator's
own read, plan or decision note.

**`max` (C-995, C-996).** `xhigh` plus every configured adversary (the
`adversary` key widens to a list; below `max` the first entry runs),
five research axes with `competitive-research` mandatory, one extra
known-pitfall researcher on the aggregate join, and usage simulation by
the new `simulator` persona — four shipped patterns, `first-time`,
`power-user`, `adversarial`, `automation`, plus project
`.agents/workers/simulator-<pattern>.md` — as `/hex-execute`'s new
`## Phase 8: Usage simulation` and a report section in `/hex-review`.
**`max` is explicit only**; the classifier never lands there.

**Migration on read (C-997).** `/hex-plan` writes `- Tier-grammar: 5`; a
plan without it has its `Tier:` shifted one step up on read and disclosed
on the `Tier:` line. A `hex.md › Preferences` block at `v3` or lower has
its tier segments shifted the same way, once, at the gate. **Config v4**
is the five-value segment plus the list-valued `adversary`; no new
top-level key. Never a rewrite, never a refusal — the same posture as
round 17's generation marker.

**Considered and not deviated:** **thin dispatchers + per-tier phase
files** — upheld: `tier-max.md` is thin, every phase a link into
`tier-xhigh.md` with only the additions written out; headings exist so
`tiers.<skill>.max.counts` has identifiers (C-220). **Single-source
contracts** — upheld: the grammar and the read-side shift live in
`protocol.md` § Tier grammar; the list-valued adversary in `adversary.md`.
**Capability classes** — upheld; `simulator` takes `fast-balanced`, its
`adversarial` pattern `deep-reasoning`. **Review by join level (round
20)** — untouched: review depth is keyed on join level at every one of
the five tiers; the tiers scale phases, model class and, at `max`, who
else sits in the batch. **Load only what runs** — `simulator` opens
`verify.md` only.
