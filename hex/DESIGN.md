# hex — Generalization Design Notes

Working notes for generalizing the OCX swarm skills into the public hex
bundle. Not published; v0.1 content is in progress — this file remains
the source of truth for decisions as it lands in the skills.

## Origin

Generalized from `~/dev/ocx/.claude/skills/{swarm-plan,swarm-execute,swarm-review,architect}`
plus `workflow-swarm.md` (shared worker vocabulary, Review-Fix Loop,
tier/overlay grammar). Inventory + analysis: session 2026-07-19.

## Shared shape (all orchestrators)

parse args → classify tier (`low|medium|high`, `auto` default) → resolve
overlays → single meta-plan approval gate (never mid-flow questions) →
announce resolved config with per-axis source attribution → dispatch to
tier file.

Skill layout: `SKILL.md` dispatcher + `classify.md` + `overlays.md` +
`tier-{low,medium,high}.md`.

**Tier rename (locked 2026-07-19):** grammar is now `low | medium | high`
(+ `auto` default), mapped from the OCX-era `low | high | max`: old low →
low, old high → medium (the new default tier), old max → high. `xhigh`
and `max` are reserved for future overlay stacks — documented, never
emitted by the classifier; an explicit request for either announces
"reserved, running high" and runs `high`.

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
  status since round 5 and the review budget since the perf pass); one
  mermaid `graph TD` with a subgraph per wave as a visual index (gantt
  and gitGraph rejected — brittle syntax, silent render failures); plan
  stays fully actionable from the table alone.

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
- Graceful skip when unavailable — gate, not blocker; skip surfaced
  prominently at tier=high.

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
