# ADR: Configuration and customization surface

## Metadata

**Status:** Accepted
**Date:** 2026-07-20
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below
      (see [Constitution deviations](#constitution-deviations) — this
      decision knowingly amends four resolved decisions in
      [`hex/DESIGN.md`](../../../hex/DESIGN.md))
**Domain Tags:** integration, developer-experience, infrastructure
**Supersedes:** N/A (amends `DESIGN.md` resolved questions — see the
deviations table)
**Superseded By:** N/A

## Context

hex ships four orchestrators plus an initializer as markdown. The client
is the runtime: no hex-authored parser reads any hex file, and the only
consumer of the persistent layer (`.agents/memory/hex.md`) is an
LLM (`DESIGN.md:63-65`). Customization today has three tiers — per-run
flags, prose bullets under `hex.md › Preferences`, and project-local
persona files at `.agents/workers/*.md` — and every worker count,
phase sequence, and reviewer trigger is prose inside twelve
`tier-{low,medium,high}.md` files.

**What a project cannot express today** (research § D, verified against
the shipped files):

1. **Per-path reviewer selection.** `Preferences` documents *always-on*
   perspectives but no *never* list, and the only subtractive lever is
   lowering `--breadth` wholesale, which drops security and performance
   with it. The one structured path→reviewer mechanism in the bundle is
   `hex-review/classify.md:49-64`, a shipped table of generic markers;
   project paths fold in only as free prose
   (`hex-review/classify.md:51-53`).
2. **Explicit worker counts.** Counts are prose numerals inside tier
   files — `hex-plan/tier-medium.md:19-24` ("1 architecture-explorer",
   "2–4 explorer workers"), `hex-plan/tier-high.md:37` ("3 researcher
   workers") — duplicated at looser granularity in each SKILL.md worker
   table (`hex-plan/SKILL.md:172-181`). No override field exists.
3. **Per-project tier meaning.** Tier→count mapping lives only in tier
   files; `memory.md:36` has no field for it. "My medium means 3
   researchers" requires editing a shipped skill.
4. **User-defined phase sequences.** All four orchestrators dispatch
   identically — "Read the matching `tier-{low,medium,high}.md` and
   execute its phase plan" (`hex-plan/SKILL.md:157-160`;
   `hex-execute/SKILL.md:178-181`; `hex-review/SKILL.md:174-177`;
   `hex-architect/SKILL.md:150-153`) — with the sequence hardcoded in
   the target file. hex-architect already runs five phases, not six
   (`hex-architect/tier-low.md:7-8`), so phase sequences are already
   non-uniform across skills; there is simply no way for a project to
   participate.
5. **Enforcement semantics of the knobs that already exist.**
   `Preferences` names `max-workers` and `loop rounds`
   (`memory.md:36,:64`) and nothing in the bundle says how a stored
   `max-workers 6` interacts with the hardcoded "at most 8 workers"
   (`protocol.md:200-204`), or whether a stored `loop rounds` is a
   ceiling on `--loop-rounds`, a default, or advice
   (`hex-execute/overlays.md:41-58`). This is a *spec* gap, not a format
   gap, and it exists today with zero new syntax.

Two further facts constrain any answer. `hex-review` at `high` already
spawns 2 + 6 = 8 workers (`hex-review/tier-high.md:83`), exactly the
global cap — so any additive reviewer rule needs a stated displacement
rule, not an assumption of headroom. And `.agents/workers/*.md`
personas can already add a whole new role (`workers.md:65-75`) with no
documented way to get that role into a launch list — hex's deepest
existing customization surface is unwired at the invocation end.

**The user's drivers, stated at the meta-plan gate:** align hex's
customization depth with what OpenSpec users expect (forkable workflow
definitions); make the four capabilities above expressible; and turn
`/hex-init` into a real interactive wizard rather than a batched
approval.

**The override on record.** The primary research artifact
([`swarm-customization-and-config.md`](../research/swarm-customization-and-config.md))
recommends a frozen five-key vocabulary and explicitly *cuts* items 2, 3
and 4 (§ Deliberately cut). The user read that recommendation and chose
all four anyway. This ADR does not re-argue the cut; it designs the
maximal surface, and records the research's predicted costs and the
mitigations in [Consequences](#consequences).

## Decision Drivers

- **hex ships markdown and the client is the runtime.** No parser will
  ever read this config. Validation is therefore impossible in the
  ordinary sense, and every rule must be one an *LLM* can apply while
  reading a small file. A published JSON Schema would be a second source
  of truth with no code layer to derive it from.
- **The repo is unreleased.** `hex/` is v0.1.0 with no `grim release`
  yet — the same reversibility window `adr_0001` keyed its one-way-door
  flag to. Key names freeze into a compatibility contract at the first
  release, because instantiated `hex.md` files in consumer projects
  reference them. A breaking redesign is free *now* and expensive after.
- **Silent failure is the worst failure.** A misspelled key today does
  nothing and says nothing. Any surface adopted must make its own
  misreadings visible in the announce block.
- **Context budget is the real cost.** Every key is doc surface, and
  every doc line is context in skills that must stay small.
  `memory.md:82-84` is binding: a section that wants to grow moves its
  content into a pointed-at file.
- **The three-input precedence is load-bearing**
  (`DESIGN.md:114-133`; `protocol.md:94-109`). Nothing here may add a
  fourth input or bypass the announce-with-source rule.
- **LLM adherence is the binding constraint, not expressiveness.** GSD
  ships ~90 keys on hex's exact architecture and pays for it with a
  1,111-line reference and the phrase "absent key = enabled, explicit
  `false` = disabled" restated verbatim in four separate agent files —
  because each agent must independently remember to honour each toggle.
  A key nobody honours is worse than a key that does not exist.
- **Portability across four harnesses.** Whatever ships must work
  unconfigured, and must not assume a harness capability
  (`adr_0001` C-003).

## Industry Context & Research

**Research artifacts:**
[`swarm-customization-and-config.md`](../research/swarm-customization-and-config.md)
(primary — spawn baseline Tables 1–3, cannot-express list, Form A/B
proposal, GSD and Spec Kitty teardowns, executed OpenSpec transcripts),
[`openspec-framework-analysis.md`](../research/openspec-framework-analysis.md)
(OpenSpec anatomy, 27-item adopt/adapt/reject table),
[`hierarchical-execution-performance.md`](../research/hierarchical-execution-performance.md)
(reviewer plateau, error amplification).

Prior art, with the specific lesson each carries:

- **OpenSpec v1.6.0** — the framework the user is aligning to. Its
  per-project config is **four zod fields** (`schema`, `context`,
  `rules`, `store`) plus one deliberately hand-parsed outside the schema
  (`project-config.ts:19-54`). Its customization story is three levels
  and all of it is *content*: project context, per-artifact `rules`, and
  a **forkable `schema.yaml`** naming artifacts, their templates, their
  instruction blocks, and `requires:` DAG edges
  (`artifact-graph/types.ts:4-31`). Beyond zod it applies exactly three
  structural checks — duplicate IDs, dangling `requires`, cycles
  (`artifact-graph/schema.ts`). **There is no agent, model, or reviewer
  concept anywhere in `src/`**, and the one AI review it ships takes a
  fixed, non-extensible checklist (`verify-change.ts`, a static template
  literal that never reads `projectConfig`). So the forkable artifact
  DAG is a real precedent to copy; a configurable reviewer panel is
  genuinely new ground, not a gap hex is behind on. It also ships **no
  JSON Schema and no `$schema` modeline** for its own files despite
  having a full validator — editor completion is not table stakes.
- **get-shit-done (~64.8k stars)** — the maximal answer *inside hex's
  exact architecture*: markdown agents, LLM-as-runtime, config a prompt
  reads with the Read tool. It went to ~90 keys in 16 groups, including
  `parallelization.max_concurrent_agents` (hex's `max-workers`) and
  `agent_skills`, an agent-type → skill-dir map injected as an
  `<agent_skills>` block at spawn and **emitted as nothing when
  unconfigured** — precisely the persona→panel wiring hex has unwired.
  Proof that "no parser exists" is not a reason a config cannot be
  large; only a reason it cannot be validated. The bill: a 1,111-line
  configuration reference and per-key precedence prose re-explained per
  key.
- **Spec Kitty** — the negative control. The full agent roster hex is
  being asked for (per-agent `roles`/`priority`/`max_concurrent`/
  `custom_flags`, ordered fallback chains, a `fallback.strategy` enum)
  was written as `research/sample-agents.yaml`, 367 lines, and
  **nothing in `src/` reads it**. What shipped is
  `{available, auto_commit, lint_on_edit}`. Where it *did* go
  declarative is the rule layer — `activated_directives` (25),
  `activated_tactics` (110), `activated_procedures` (18) — flat opt-in
  lists, i.e. `perspectives.always` at 170-entry scale.
- **Claude Code**, the harness hex primarily targets, keeps
  phase→agent assignment out of config entirely: subagent frontmatter
  has **no `phase` field**, and its first-party multi-agent primitive
  (`.claude/workflows/*.js`) keeps phase imperative — `agent(prompt,
  {label, phase})` — with a single up-front approval and explicitly no
  mid-run input.
- **CrewAI** is the one real declarative phase→agent precedent
  (per-task `"agent": "researcher"`, `"context": ["research"]`) and it
  works because a Python runtime parses it; it also moved its default
  from YAML to JSONC recently, so "CrewAI uses YAML" is already stale.
- **GitLab Duo Agent Platform `fileFilters`** — the closest *shipping*
  analog to `perspectives.always[].when:`, and closer in shape than any
  of the four frameworks above: glob-scoped (with union patterns like
  `{rb,ts}`), LLM-interpreted, per-path AI review instructions with no
  hard parser enforcing them. This axis of the design is therefore
  **SOTA-aligned, not novel or risky**. GitLab's own docs carry the
  counter-lesson hex adopts in merge rule 5: "Custom review instructions
  are guidance for the AI reviewer, not enforced policies… Do not rely
  on custom instructions for security controls, compliance obligations,
  or other requirements where consistent enforcement is needed."
- **Array-merge traps.** GitLab `include` cannot merge `rules:` arrays
  (top-level replaces wholesale); Ruff resets the `ignore` baseline once
  `select` is given; ESLint reintroduced `extends` in March 2026 because
  raw ordered-array composition proved unpredictable. Any list-valued
  key must state replace-vs-append explicitly, and hex's per-item source
  attribution in the announce block is already doing what `extends` was
  added to make legible.
- **Resilient parse** (OpenSpec `project-config.ts:130,:151-200,:278-295`):
  an oversized `context` is warned and dropped, unknown `rules` keys
  warn once — a bad field never fails a run. Paired with `doctor`'s
  `{message, fix}` finding shape, the shipped posture is: never block on
  config trouble, and ship the remediation string next to the complaint.

## Considered Options

Five options. Each is shown configuring the **same project** — this
repo — with the same four wants: always run a security reviewer under
`hex/hex-core/**`; never run the doc reviewer; make `hex-plan` medium
run 3 researchers instead of 1; and run a `hex-execute` flow that skips
Verify-Architecture on this docs-shaped repo.

### Option A — Minimal: write the semantics, add no syntax

Change nothing about the carrier. Add two paragraphs to `protocol.md`
closing the Finding-1 gap, and one sentence to `memory.md` naming the
prose bullets that count.

```markdown
## Preferences

- Limits: max-workers 6, loop rounds 3.
- Security review mandatory under `hex/hex-core/**` — the contract
  files, not the prose.
```

Wants 3 and 4 are simply not expressible; wants 1 and 2 remain prose an
orchestrator interprets. In exchange, `protocol.md` gains: *effective
concurrency cap = `min(8, max-workers)`*, and *a stored `loop rounds` is
a ceiling on both the per-tier default and on `--loop-rounds`*. This is
the null option, and it is the highest-value single change on the list —
it fixes the one defect that exists today with certainty, costs eight
lines of doc surface, and cannot break a consumer.

### Option B — Middle: the research's frozen five-key block

One fenced `yaml` block inside `hex.md › Preferences`; five top-level
keys (`models`, `adversary`, `limits`, `perspectives`, `research-axes`);
everything else stays a prose bullet below the block.

```yaml
models:
  fast-balanced: <fast model>
  deep-reasoning: <deep model>
adversary: codex:rescue
limits: {max-workers: 6, loop-rounds: 3, artifact-loop-rounds: 1}
perspectives:
  always:
    - role: reviewer:security
      when: "hex/hex-core/**"
  never: [doc-reviewer]
research-axes: [registry ecosystems, OCI spec evolution]
```

Wants 1 and 2-partially land (`never` and `when:` are the two genuinely
new capabilities); wants 3 and 4 do not. Smallest surface that closes
the largest number of cannot-express items per key spent.

### Option C — Maximal, monolithic: everything in one expanded block

All four capabilities as one grown vocabulary in the same fenced block —
the GSD shape, at hex scale. `perspectives`, `counts`, `tiers`,
`phases`, plus the five above.

```yaml
limits: {max-workers: 6, loop-rounds: 3}
perspectives:
  always: [{role: reviewer:security, when: "hex/hex-core/**"}]
  never: [doc-reviewer]
counts:
  hex-plan: {medium: {Research.researcher: 3}}
tiers:
  hex-plan: {medium: {inherits: high}}
phases:
  hex-execute:
    medium:
      - {id: Stub, roles: [builder:stub], depends-on: []}
      - {id: Specify, roles: [tester], depends-on: [Stub]}
      - {id: Implement, roles: [builder:implement], depends-on: [Specify]}
      - {id: Review-Fix, roles: [reviewer:quality, reviewer:spec],
         depends-on: [Implement], gate: verification}
      - {id: Merge, roles: [], depends-on: [Review-Fix]}
```

Everything is expressible and everything is in one place. The phase list
alone is ~10 lines per skill per tier; a project customizing two skills
puts 40+ lines of DAG inside a file whose own spec says "small by
contract, pointers not prose-dumps" (`memory.md:82-84`), read in full by
every orchestrator on every run.

### Option D — Layered: frozen core block + forked tier files (recommended)

Two tiers with different carriers, chosen by size and by who reads them.

**Tier A, always present when configured at all** — one fenced `yaml`
block in `hex.md › Preferences`. Option B's five keys plus **one** new
key, `tiers`, whose dotted sub-keys carry both per-phase counts (want 2)
and per-project tier redefinition (want 3). Extension is by key
convention alone, no new columns and no version marker — the same
discipline `adr_0002` C-105 adopted for dotted sub-WP IDs.

**Tier B, optional, and most projects never create it** — a user-defined
phase sequence is **a fork of a shipped tier file**, not a new grammar.
It is a markdown file under `.agents/workflows/`, in exactly the
shape `hex-execute/tier-medium.md` already has (phase sections with
gates), plus a header table making the DAG legible at a glance. A single
`workflows:` pointer in the Tier A block routes the dispatch step to it.

```yaml
limits: {max-workers: 6, loop-rounds: 3}
perspectives:
  always: [{role: reviewer:security, when: "hex/hex-core/**"}]
  never: [doc-reviewer]
tiers:
  hex-plan.medium:
    counts: {Research.researcher: 3}
workflows:
  hex-execute.medium: .agents/workflows/exec-docs.md
```

```markdown
<!-- .agents/workflows/exec-docs.md -->
# hex-execute — medium (project workflow)

Forked from hex-execute/tier-medium.md @ hex 0.1.0.

| Phase | Depends on | Roles | Count | Gate |
|---|---|---|---|---|
| Stub | — | builder:stub | 1×WP | compile |
| Specify | Stub | tester | 1×WP | tests fail |
| Implement | Specify | builder:implement | 1×WP | verification |
| Review-Fix | Implement | reviewer:quality, reviewer:spec | 1×WP each | loop exit |
| Merge | Review-Fix | — | — | verification |

## Phase: Stub
…prose identical to the shipped file, minus Verify-Architecture…
```

Every want lands. The 40 lines of DAG live in a file only the projects
that want it ever create, and only the runs that need it ever read. The
node schema is not invented: it is the phase shape the tier files
already use, which is why a fork is a copy-and-edit rather than a
translation.

### Option E — Overrides on shipped tier files, no config block

No new config vocabulary at all. Customization is *only* file shadowing:
a project-local `.agents/tiers/hex-plan/tier-medium.md` shadows
the shipped file wholesale, exactly as `.agents/workers/*.md`
already shadows nothing but adds roles (`workers.md:65-75`).

```markdown
<!-- .agents/tiers/hex-plan/tier-medium.md -->
# hex-plan — medium (project override)
## Phase 2: Research
Launch **3** researcher workers…
```

Conceptually the smallest possible mechanism — one convention, zero
keys, everything expressible because the whole phase file is yours. Its
defect is total: a fork carries every line of the shipped file including
the ones the project did not mean to change, so every hex upgrade
silently strands it. Reviewer-path rules become a per-project rewrite of
`classify.md` prose. There is no announce-block source attribution
possible because there is no per-item layering — the whole tier is one
item.

## Decision Outcome

**Chosen: Option D — layered, frozen core block plus forked tier files.**

### Weighted scoring

**Feasibility gate, applied before scoring.** The requirement set —
per-path reviewer selection, explicit worker counts, per-project tier
redefinition, user-defined phase sequences, and enforcement semantics
for the existing knobs — is settled by the decider and is not a
criterion to be traded off. An option that cannot express a required
capability at all is **infeasible**, and its weighted total is
informational only. **Option A is infeasible**: requirements 2, 3 and 4
are not expressible in prose bullets under any reading, which its own
1/5 expressiveness score records. Options B is likewise infeasible
(requirements 3 and 4 unexpressible). C, D and E are the feasible set.

Weights reflect the drivers: adherence and expressiveness dominate
because a surface that is not honoured is worse than none. Scores 1–5,
higher is better.

| Criterion | W | A† | B† | C | D | E |
|---|--:|--:|--:|--:|--:|--:|
| Expressiveness vs the five requirements | 25 | 1 | 3 | 5 | 5 | 4 |
| LLM adherence (will a reader honour it) | 25 | 5 | 4 | 2 | 4 | 3 |
| Doc surface / context budget | 15 | 5 | 4 | 1 | 3 | 4 |
| Drift risk vs shipped files | 10 | 5 | 4 | 2 | 3 | 1 |
| Authoring cost (project side) | 10 | 5 | 4 | 2 | 3 | 2 |
| Portability across harnesses | 10 | 5 | 5 | 4 | 5 | 5 |
| Reversibility after first release | 5 | 5 | 4 | 2 | 4 | 3 |
| **Weighted total (max 500)** | | *400* | *385* | **280** | **400** | **330** |

† Infeasible against the settled requirement set; total shown in italics
for comparison only and **not** treated as co-optimal with D. A's 400 is
a refusal to spend, and it would be the right answer if the requirement
set were negotiable. It is not.

Within the feasible set, D leads E by 70 and C by 120, and every one of
those 120 points is doc surface, adherence and drift risk that C spends
and D does not. E is rejected outright: an un-layered fork has no
upgrade story and no source attribution, and it would be the second
source of truth `DESIGN.md:36` exists to prevent.

**Option A is not discarded — it is folded in as work item 1.** The
`max-workers`/`loop-rounds` semantics land in `protocol.md` whether or
not anything else does, and they land first.

### Normative specification

Everything below is the adopted spec. It is complete: an implementer
needs no other source for the key set, defaults, effects, merge rules,
or failure behaviour.

#### Carrier and placement

One fenced ```` ```yaml ```` block, first content under
`## Preferences` in `.agents/memory/hex.md`. Prose bullets
continue below the block and continue to carry nuance the keys cannot
("security review means the token-exchange path, not the CRUD
handlers"). A missing file, a missing section, or a missing block is
**normal** — shipped defaults apply and skills suggest `/hex-init`
(`memory.md:9-24`). The block is written only by `/hex-init` with
consent; orchestrators read it and never edit it
(`memory.md:36,:79-81`). Not frontmatter: `hex.md` has three sections
with three different owners (`memory.md:33-37`), and frontmatter would
hoist user-owned config above skill-managed sections and make the whole
file read as machine-owned.

#### Key vocabulary

**Two vocabulary versions, and only one of them freezes at first
release.** `workflows` (Tier B) is implemented in Wave 3, which is
explicitly not release-blocking. A key cannot be frozen and unbuilt at
the same time: freezing advertises a contract that no shipped file yet
honours, and the first consumer `hex.md` to reference it would encode a
no-op. Therefore:

- **Vocabulary v1 — the six Tier A keys** (`models`, `adversary`,
  `limits`, `perspectives`, `research-axes`, `tiers`). Ships in Wave 2
  and **freezes at the first `grim release`**.
- **Vocabulary v2 — v1 plus `workflows`.** Ships in Wave 3 and freezes
  at whichever `grim release` follows it. Until then `workflows` is a
  provisional key: a v1-era reader treats it as an unknown key (merge
  rule 8 — warn once, ignore, continue), which is the correct behaviour
  because the dispatch interception it names does not exist yet.

The block's `# hex config, vocabulary vN` comment states which version
the file was written against; merge rule 8's "valid top-level keys"
enumeration lists the version the *reader* implements. The version bump
is cheap precisely because it happens while unreleased.

| Key | v1 | Type | Default | Effect |
|---|:--:|---|---|---|
| `models.fast-balanced` | ✅ | string (literal model name) | unset → shipped class prose | Instantiates the class for this harness. |
| `models.deep-reasoning` | ✅ | string | unset | As above. Never an orchestrator-class model (`adr_0001` C-002). |
| `models.overrides` | ✅ | map `role[:focus]` → capability class | `{}` | Per-role class override at every tier. Escalation above the shipped cell still requires the announced reason (`models.md:47-57`). |
| `adversary` | ✅ | string skill name, or `none` | unset → adversary contract's per-tier default | Names the cross-model adversary skill (`protocol.md` § Adversary contract). |
| `limits.max-workers` | ✅ | int ≥ 1 | 8 | **A concurrency ceiling, never a floor and never a panel size.** Effective cap = `min(8, max-workers)`, counted recursively (`protocol.md:200-204`). A value > 8 is announced as clamped. A phase whose resolved spawn set exceeds the cap **batches**; it never drops a perspective for the cap alone (C-216). |
| `limits.loop-rounds` | ✅ | int 1–3 | tier default (low 1, medium/high 3) | Ceiling on the code-diff Review-Fix cap **and** on `--loop-rounds`. Never raises above the tier default. |
| `limits.artifact-loop-rounds` | ✅ | int ≥ 1 | 1 | Plan/ADR-scope loop rounds. Opt-in only; `1` is shipped behaviour (`protocol.md:150-159`). |
| `perspectives.always` | ✅ | list of rule objects | `[]` | Adds a perspective to the resolved panel. See rule object below. |
| `perspectives.never` | ✅ | list of `role[:focus]` | `[]` | Removes a perspective from the resolved panel. Applied last. `reviewer:security` additionally requires the attestation key below (merge rule 5). |
| `perspectives.security-sensitive-paths` | ✅ | the literal `none`, or unset | unset | **Attestation, required to suppress the security reviewer.** `none` asserts this project has no security-sensitive path. Any other value, or absence, makes `never: [reviewer:security]` fail closed (merge rule 5). |
| `research-axes` | ✅ | list of strings | `[]` | Pre-seeds hex-architect's and hex-plan's candidate axis list; never auto-selects. |
| `tiers.<skill>.<tier>.inherits` | ✅ | one of `low\|medium\|high` | unset | This project's `<tier>` starts from the shipped `<inherits>` baseline instead of its own. Resolved **first**, before `counts` and `overlays` (C-219). |
| `tiers.<skill>.<tier>.counts` | ✅ | map `<Phase>.<role[:focus]>` → int ≥ 0 | `{}` | Sets the spawn count for that role in that phase, **against the baseline `inherits` already resolved**. `0` removes the spawn. `<Phase>` is a phase identifier per C-220. |
| `tiers.<skill>.<tier>.overlays` | ✅ | map axis → value | `{}` | Per-project default for an overlay axis (e.g. `review: full`), below a user flag in precedence. Applied last within `tiers`. |
| `workflows.<skill>.<tier>` | **v2** | path to a markdown file | unset | Dispatch reads this file instead of the shipped `tier-<tier>.md`. Provisional until Wave 3 ships; a v1 reader warns and ignores it. |

**`perspectives.always` rule object.**

| Field | Type | Default | Effect |
|---|---|---|---|
| `role` | `role[:focus]`, required | — | A shipped role (`workers.md:51-63`) or a project-local persona (`.agents/workers/<role>.md`). **This is the documented persona→panel wiring** — naming a project persona here is how it enters a launch list. |
| `when` | path glob (see below) | unset = every run | Rule fires only when at least one path in the run's **target file set** matches. |
| `skills` | list of skill names | all four orchestrators | Limits the rule's scope. |
| `phase` | phase identifier (C-220) | the skill's review phase | Which phase the spawn joins. |

**Glob semantics (C-217).** The glob is not a regex and not a shell
expansion; it is the gitignore-style subset every one of hex's four
harnesses already reads:

- Paths are **repository-relative**, `/`-separated, with no leading `/`
  or `./`. The repository root is the git worktree root of the run —
  inside `hex-execute`, that is the work package's worktree, whose
  paths are identical to the main tree's.
- `?` matches one character within a segment. `*` matches zero or more
  characters within one segment and **never crosses `/`**. `**` matches
  zero or more whole segments, including none — `a/**/b` matches `a/b`.
  `{x,y}` is alternation, `[abc]` and `[a-z]` are character classes.
- A pattern with no wildcard matches that exact path. A pattern ending
  in `/` or `/**` matches the directory's entire subtree. A pattern
  naming a directory with no trailing marker (`src/ui`) is read as
  `src/ui/**`.
- Matching is **case-sensitive**, and dotfiles are ordinary: `*` and
  `**` match a leading `.` with no opt-in.
- **Symlinks match by their own path, never their target's.**
- Anything else — an unterminated class, a `!` negation, a `..`
  segment, an absolute path — is an unparseable glob and falls to merge
  rule 9 (ignore that rule, warn, continue).

**The target file set, per skill.** `when:` needs a path set, and only
two of the four skills have a diff. The set is:

| Skill | Target file set |
|---|---|
| `hex-review` | Every path added, modified or deleted in the diff under review. A **rename contributes both** the old and the new path; a deletion contributes its path. |
| `hex-execute` | The union of the plan's work-package file lists, plus every path the run has written so far. Evaluated per phase, so a rule can fire once the diff exists that makes it relevant. |
| `hex-plan` | The file lists named by the input issue/PR/task, plus every path Discover read, plus every path named in a drafted work package. |
| `hex-architect` | Every path named in the decision input plus every path Discover read. |

An **empty target file set** — a green-field plan naming no files —
makes every rule carrying a `when:` not fire. A rule with no `when:` is
unaffected. This is a normal outcome, not a warning.

**Key spelling: nested and flat are one key (C-222).** `tiers: {hex-plan:
{medium: …}}` and `tiers: {hex-plan.medium: …}` denote the same leaf
path; a reader normalizes every dotted segment to the nested form
**before** any merge rule runs, so `models.overrides` written flat and
nested merge as one map (merge rule 2). If normalization produces two
declarations of the *same leaf* with different values, that is a
duplicate key: the **later declaration in block order wins** and the
collision prints `Error: duplicate key 'tiers.hex-plan.medium.counts'
declared as both nested and flat. Fix: keep one spelling; the later one
(line N) was used.` A flat key that collides with a nested *map* — say
`tiers.hex-plan.medium` given a scalar while `tiers: {hex-plan: {medium:
{counts: …}}}` exists — is a type conflict and falls to merge rule 9:
the scalar is dropped, the map is kept, warned. Never a silent merge of
two shapes.

The `<skill>` segment is `hex-plan`/`hex-execute`/`hex-review`/
`hex-architect`; the `<tier>` segment is `low`/`medium`/`high` (never
`auto` — `auto` is a classifier input, not a tier).

#### Phase identifiers (C-220)

`tiers.*.counts` keys and `perspectives.always[].phase` both name a
phase, so "what is a valid phase name" must be answerable by a reader
with the files already in front of it. It is:

> **A phase identifier is the text of a tier file's `## Phase N:`
> heading, taken after the colon and cut at the first `(` or ` — `,
> then trimmed.** The identifier set for a `<skill>.<tier>` pair is
> exactly the identifiers of that tier file's headings, in file order.

`## Phase 3: Verify-Architecture — skipped` → `Verify-Architecture`.
`## Phase 6: Review-Fix Loop (up to 3 rounds, full breadth)` →
`Review-Fix Loop`. `## Phase 2: Stage 1 — Correctness (2 workers)` →
`Stage 1`. Matching is case-insensitive and whitespace-normalized;
identifiers are unique within a tier file by construction (they are
already, across all twelve shipped files).

**hex ships no phase index file, deliberately.** A shipped
`phases.md` enumerating the twelve tier files' phases would be a second
source of truth for a fact the tier file already states in its own
headings — precisely the failure `DESIGN.md:36` exists to prevent, and
it would go stale the first time a tier file is edited. The heading *is*
the index. The cost is that a reader must open the tier file to
validate a `counts` key, which it is already opening to dispatch.

**Phase identifiers are per skill and per tier, and are not portable.**
`tiers.hex-plan.medium.counts` keys are validated against
`hex-plan/tier-medium.md` only. A key naming a phase absent from that
file is a malformed value (merge rule 9): dropped, warned, siblings
unaffected —
`Error: unknown phase 'Reserch' in tiers.hex-plan.medium.counts. Fix:
valid phases for hex-plan medium are Discover, Research, Classify,
Design, Decompose, Review.`

**Under an active workflow fork, the fork is the phase index (C-220).**
When `workflows.<skill>.<tier>` resolves to a valid workflow file, every
phase identifier for that skill/tier pair — in `tiers.*.counts` and in
`perspectives.always[].phase` alike — resolves against the **workflow
file's** `Phase` column, not the shipped tier file's. A fork that
deletes or renames a phase therefore invalidates any preference still
naming it, and the specified result is:

- The offending entry alone is **ignored**, per merge rule 9. There is
  no fallback to the shipped phase (the shipped phase is not running)
  and no fallback to a neighbouring phase (silently relocating a
  security reviewer is worse than not running it, because the announce
  block would attest to a phase the user did not choose).
- It is warned once per entry, naming the workflow file as the
  authority: `Error: perspectives.always[1].phase 'Verify-Architecture'
  is not a phase of .agents/workflows/hex-execute-medium.md.
  Fix: use one of Discover, Stub, Specify, Implement, Review-Fix Loop,
  Merge and commit — or drop the phase: field to use the skill's review
  phase.`
- The run continues. A stale phase reference never aborts and never
  silently relocates a spawn.

When a workflow file **fails** validation, dispatch falls back to the
shipped tier file (C-209), and phase identifiers fall back with it — the
shipped file is the index again for that run.

#### Complete, copy-pasteable example

````markdown
## Preferences

```yaml
# hex config, vocabulary v2. Unknown keys warn once and are ignored.
# (v1 = these keys minus `workflows`; see Key vocabulary.)
models:
  fast-balanced: <this harness's fast-balanced model>
  deep-reasoning: <this harness's deep-reasoning model>
  overrides:
    reviewer:security: deep-reasoning
adversary: codex:rescue

limits:
  max-workers: 6            # effective cap = min(8, 6) = 6
  loop-rounds: 3            # ceiling on --loop-rounds, code-diff scope
  artifact-loop-rounds: 1   # 1 = shipped behaviour

perspectives:
  always:
    - role: reviewer:security
      when: "hex/hex-core/**"
    - role: reviewer:accessibility     # .agents/workers/ persona
      when: "src/ui/**"
      skills: [hex-review, hex-execute]
  never:
    - doc-reviewer

research-axes:
  - registry ecosystems
  - OCI spec evolution

tiers:
  hex-plan.medium:
    counts:
      Research.researcher: 3           # shipped baseline is 1
      Discover.explorer: 2             # shipped baseline is 2-4
    overlays:
      adversary: on
  hex-review.high:
    inherits: medium                   # this repo's "high" is medium's panel

workflows:
  hex-execute.medium: .agents/workflows/exec-docs.md
```

- Security review means the contract files under `hex-core/references/`,
  not the prose in the skill dispatchers.
````

#### Resolution and merge rules

The three-input precedence is **unchanged** (`DESIGN.md:114-133`;
`protocol.md:94-109`). `tiers` and `workflows` do not add a fourth
input — they *rewrite layer 1* before layers 2 and 3 apply. Layer 1
reads: "the shipped tier baseline, as amended by `tiers`/`workflows`".

1. **Scalars** (`adversary`, all `limits.*`, all `models.*` leaves,
   `inherits`, and `workflows.<skill>.<tier>` — a path string) — later
   layer replaces earlier. A `workflows` entry never composes or
   merges across layers: the last-declared path for a given
   `<skill>.<tier>` wins outright, and there is no notion of stacking
   two workflow files.
2. **Maps** (`models.overrides`, `tiers.*.counts`, `tiers.*.overlays`) —
   merged per key. An override for one key never disturbs another.
3. **Lists** (`perspectives.always`, `perspectives.never`,
   `research-axes`) — **replace wholesale across layers, never append**
   (GitLab's `rules:` lesson). Within a layer the panel resolves once:
   `baseline ∪ always(matching) − never`.
4. **`never` cannot remove `reviewer:spec`.** The traceability check is
   a contract gate, not a perspective (`protocol.md` § Traceability IDs).
5. **`never: [reviewer:security]` is fail-closed.** It is honoured
   **only** when both hold: (a) the block declares
   `perspectives.security-sensitive-paths: none`, and (b) no
   security-sensitive path matched in this run — no
   `perspectives.always` rule whose `when:` glob names a security path,
   and no hit on `classify.md`'s shipped security markers. Every other
   case, **including the ambiguous one where the reader is unsure
   whether a path is sensitive**, is a refusal: the security reviewer
   runs, and the announce block prints the reason.
   - Missing attestation → `Error: never [reviewer:security] refused —
     no perspectives.security-sensitive-paths attestation. Fix: add
     'security-sensitive-paths: none' to assert this project has no
     security-sensitive path, or drop the never entry.`
   - Attestation present but a path matched → `Error: never
     [reviewer:security] refused — <glob> matched, contradicting
     security-sensitive-paths: none. Fix: narrow the always rule's
     when: glob, or drop the attestation and the never entry.`
   - Both conditions met → honoured, printed as a **warning line**,
     never a quiet omission.

   *Why an attestation rather than a bare `never`.* The refusal branch
   is the branch a reader must not forget, and a bare `never` puts the
   forgetful path on the permissive side: a reader that skips rule 5
   entirely suppresses the reviewer. Requiring a second, explicit key
   inverts that — the forgetful path now lacks the attestation and
   refuses. The user must state the belief that makes suppression safe,
   in the config, where `/hex-init`'s re-audit can later contradict it.
   *Precedent and its limit:* GitLab Duo's `fileFilters` — the nearest
   shipped analog (glob-scoped, LLM-read review instructions, no hard
   parser) — documents that such instructions are "guidance for the AI
   reviewer, not enforced policies" and must not be relied on for
   security controls. hex cannot escape that; it can only choose which
   way an unreliable reader fails, and this rule chooses *toward
   running the reviewer*. The Security NFR states the residual honestly.
6. **The concurrency cap batches; the phase ceiling displaces.** These
   are two different limits and the design previously conflated them.
   - **`min(8, max-workers)` is a concurrency cap — the number of
     workers running *at once*, not the size of a panel**
     (`protocol.md:200-204`, "at most 8 workers at once"; the degraded
     mode that runs every worker inline one at a time is the same rule
     at cap 1). A phase whose resolved spawn set exceeds the cap runs
     in **sequential batches of at most the cap**, in declaration
     order, and its gate holds until the last batch returns.
     Consequently **a reduced `max-workers` never drops a baseline
     perspective**: `hex-review` high's 8 baseline workers under
     `max-workers: 3` run as 3 + 3 + 2, not as five deleted reviewers.
     Batching is announced, not silent.
   - **The phase ceiling is what preferences may not exceed.** For each
     phase, `ceiling = max(shipped phase baseline total,
     min(8, max-workers))`. The baseline term is why a saturated
     shipped phase stays runnable; the cap term is why a project that
     raised `counts` on a small phase still gets its headroom. Only
     **preference-added** spawns are ever displaced — `always` entries,
     and `counts` values *above* their baseline. `counts` values below
     baseline (including `0`) are the project's own reduction and are
     never restored.
   - **The reduction procedure**, run when a phase's resolved total
     exceeds its ceiling:
     1. `overshoot = resolved total − ceiling`.
     2. While `overshoot > 0` and any `always`-added spawn remains in
        this phase: drop the **last-declared** such spawn (reverse
        declaration order within `perspectives.always`), decrement
        `overshoot` by 1, announce the drop with `— phase ceiling N
        reached`.
     3. While `overshoot > 0`: among `counts` entries in this phase
        currently **above** their shipped baseline, pick the one with
        the largest absolute excess; reduce it by **one**, decrement
        `overshoot` by 1. Ties break by the fully-qualified key
        `<Phase>.<role[:focus]>` in ascending ASCII order. Re-evaluate
        after every single step — never reduce an entry to its baseline
        in one move.
     4. Stop. Termination is guaranteed: steps 2 and 3 each strictly
        decrease `overshoot` by 1, and their combined supply is exactly
        the preference-added spawn count, after which the resolved set
        equals the shipped baseline, whose total is ≤ ceiling by the
        `max(…)` definition.
   - **Never** silently exceed the ceiling, and **never** reduce a
     baseline spawn below its shipped value to make room for a
     preference. There is no protected-subset carve-out because there
     is no case in which baseline is touched at all; `reviewer:spec`'s
     unremovability (rule 4) is a separate and stronger guarantee that
     also survives an explicit `counts: 0` (rule 7).
7. **`counts` of `0`** removes a spawn — except for a role the tier file
   marks mandatory, where it is refused with a warning naming the file.
8. **Unknown key** — warn once in the announce block, ignore, continue.
   The warning pairs complaint and remedy, OpenSpec's `doctor`
   convention: `Error: unknown key 'perspective.always'. Fix: did you
   mean 'perspectives.always'? Valid top-level keys: models, adversary,
   limits, perspectives, research-axes, tiers.` The enumeration lists
   the vocabulary version the **reader** implements — a v1 reader omits
   `workflows` and treats it as unknown; a v2 reader appends it.
9. **Malformed value** (wrong type, unparseable glob, unknown role,
   unknown skill/tier/phase segment, **or a `workflows` path that names
   no readable file**) — ignore that key only, keep the shipped default
   for it, warn with the same shape. A `workflows` pointer to a
   nonexistent path is therefore the same failure as a workflow file
   that fails validation: `Error:`/`Fix:`, fall back to the shipped
   `tier-<tier>.md`, run. A bad field never blocks a run, and never
   invalidates its siblings.
10. **Unparseable YAML block** — the whole block is skipped, announced
    once, prose bullets in the section still apply, run continues on
    shipped defaults.

#### `tiers` resolution order (C-219)

`inherits`, `counts` and `overlays` may all appear in one
`tiers.<skill>.<tier>` block, and their order is **fixed and total**:

1. **`inherits` first.** The layer-1 baseline for `<skill>.<tier>`
   becomes the *shipped* `<skill>.<inherits>` tier file **in full** —
   its phase set, its phase identifiers, its roles, its counts and its
   overlay defaults. The declaring tier's own shipped file contributes
   nothing; this is a replacement, not a merge. `hex-review.high:
   {inherits: medium}` resolves to `hex-review/tier-medium.md`'s
   baseline, and `high`'s six shipped phases are not consulted.
2. **`counts` second, against the result of step 1** — never against
   the declaring tier's own shipped file. Under `inherits: medium`, a
   `counts` key is validated against *medium's* phase identifiers, its
   deltas are computed against *medium's* baseline numbers, and a
   phase that exists only in `high` is an unknown phase (merge rule 9:
   dropped, warned). This is the whole reason the order is stated: the
   two readings differ in both which keys are valid and what delta is
   announced.
3. **`overlays` third**, applied to the result of steps 1–2, and still
   below any user flag in precedence.
4. Then the panel resolution of merge rule 3 (`baseline ∪
   always(matching) − never`), then merge rule 6's phase ceiling.

**`inherits` is not transitive and never chains.** It may name only a
*shipped* tier, and that tier's own project redefinition — if the same
`hex.md` also declares `tiers.hex-review.medium.counts` — is **not**
applied to the inheriting tier. A redefinition is therefore always
describable in one sentence: "high here = shipped medium, plus these
deltas." An `inherits` naming the declaring tier itself, or a value
outside `low|medium|high`, is malformed (merge rule 9): ignored,
warned, the shipped baseline stands.

The announce block prints both facts — the inherit line and every
`counts` delta *relative to the inherited baseline* — per C-207.

#### Announce block

The announce block is the enforcement surface: a rule that is not
printed did not fire. Per-item source attribution is already required
(`protocol.md:51-79`); these lines extend it.

```
Tier: medium (classifier — 9 files, 340 lines)
      [project-redefined: Research.researcher 1→3 (hex.md tiers)]
Workflow: shipped hex-execute/tier-medium.md
Spawn: builder×3, tester×3, reviewer:quality, reviewer:spec,
       reviewer:security (hex.md preference — hex/hex-core/** matched)
       [doc-reviewer suppressed — hex.md preference `never`]
       [reviewer:performance dropped — phase ceiling 8 reached]
       [Review-Fix batched 6+2 — concurrency cap 6 (hex.md)]
Models: fast-balanced default; reviewer:security → deep-reasoning (hex.md)
Adversary: codex:rescue (hex.md preference)
Research axes: registry ecosystems, OCI spec evolution
       (hex.md preference — pre-seeded, not auto-selected)
Limits: max-workers 6 (hex.md), loop-rounds 3 (tier baseline)
Error: unknown key 'perspective.always'. Fix: did you mean
       'perspectives.always'?
```

**Every top-level key the reader implements has a line** — the six v1
keys always, plus `Workflow` once `workflows` ships in v2. `Tier`/`Spawn`
carry `tiers` and `perspectives`, `Workflow` carries `workflows`,
`Models`, `Adversary`, `Research axes` and `Limits` carry the rest. A
key with no line in this spec would be a key with no enforcement
signal, which is the failure the driver "a key nobody honours is worse
than a key that does not exist" names. `Adversary` and `Research axes`
print only when the key is set; the other lines print always, with
`(tier baseline)` as the source when unconfigured.

**Self-check before printing.** The announce block is generated by the
same reader that applied the rules, so it can print a well-formed line
for a rule it applied wrongly. Before emitting the block, the
orchestrator re-verifies merge rules 4–7 explicitly — spec not removed;
security suppression refused unless *both* rule-5 conditions hold;
every drop made by the rule-6 procedure in order, with `overshoot`
recomputed after each single step and no baseline spawn touched; every
phase over the cap shown as a batch split rather than a drop; every
`counts: 0` checked against the tier file's mandatory-role list — and
prints the block only after that pass. This is a re-ask, not an
independent verification (see Consequences).

**Tier-redefinition disclosure is mandatory.** Any run whose tier
baseline was amended by `tiers` prints the `[project-redefined: …]`
line with every changed count, and prints it *even when the resolved
counts happen to equal the shipped ones*. This is the whole mitigation
for "the tier label stops meaning the same thing across projects": the
label is never allowed to travel without its deltas.

#### Workflow files — node schema, edges, validation, forking

A workflow file is a **fork of a shipped tier file**. It is markdown,
in the shape tier files already use, with one added header table.

**Node schema** — one table row plus one `## Phase: <id>` section per
node:

| Column | Type | Required | Meaning |
|---|---|---|---|
| `Phase` | identifier per C-220, unique in file | yes | Node id; matches its `## Phase: <id>` heading verbatim. |
| `Depends on` | comma-separated phase ids, or `—` | yes | Incoming edges. |
| `Roles` | `role[:focus]` list, or `—` | yes | Spawn set for the phase. |
| `Count` | one of the three forms below | yes | Per-role spawn count. |
| `Gate` | free text | yes | What must hold before the next phase starts. |

**`Count` grammar — three forms, no others.** A workflow header table is
executed, not read for guidance, so every cell must resolve to a
definite integer before the phase runs:

| Form | Resolves to | Available in |
|---|---|---|
| `<int>` | Exactly that many spawns **of each role** in `Roles`. `0` is not a legal `Count`; delete the row instead. | all skills |
| `<int>×WP` | `<int>` spawns of each role **per work package eligible in this phase** — eligibility per the WP-level DAG (`adr_0002` C-101). A coordinator's leaves count recursively toward the concurrency cap, exactly as `protocol.md:200-204` requires. Resolves once the plan's work-package list is known, which is before dispatch. | `hex-execute` only |
| `—` | No spawns; the phase runs inline in the orchestrator. `Roles` must also be `—`. | all skills |

**Ranges are not a `Count`.** Shipped tier files write ranges ("2–4
explorer workers") as *prose guidance to a classifier*; a workflow table
is the resolved answer. A range in a `Count` cell is a malformed value:
it is read as its **lower bound** and warned —
`Error: Count '2-4' in phase Discover is a range, not a count. Fix:
write one integer; 2 was used.` The run continues on the lower bound
because that is the choice that cannot exceed the phase ceiling.

`<int>×WP` outside `hex-execute`, a non-integer, or a negative value is
likewise malformed: the row's phase falls back to the **shipped tier
file's** count for the same phase identifier if one exists, and to `1`
otherwise, warned either way.

**Edge semantics.** `Depends on` is a happens-before edge. A phase is
eligible when every phase it depends on has passed its gate. Phases
with no unmet dependency run concurrently, within the concurrency cap.
Edges are within one workflow file only — no cross-file or cross-skill
edges. This DAG is the *phase*-level graph and is orthogonal to
hex-execute's existing WP-level DAG (`adr_0002` C-101); the WP DAG runs
inside whichever phase declares the builder roles, and neither may
reference the other's ids.

**Validation rules a skill applies** (a reader, not a parser — each is
a check an LLM performs while reading the file, in this order; the
first three mirror OpenSpec's only three structural checks):

1. Every `Phase` id is unique.
2. Every `Depends on` target names a declared phase.
3. No cycle — walk the edges; report the full cycle path.
4. Every `Roles` entry resolves to `workers.md`'s role index or a file
   under `.agents/workers/`.
5. **Every `Count` cell resolves to a definite integer** under the
   grammar above, and every phase's resolved total is finite. The
   concurrency cap is *not* checked here — merge rule 6 handles it at
   run time by batching, and a phase over the ceiling is displaced by
   the rule-6 procedure, not rejected as an invalid file.
6. **Skill invariants hold — checked against required phase identifiers
   and required observable duties, not against a paraphrase.** The
   check is: every **required** identifier below is present as a
   `Phase` row *and* as a `## Phase: <id>` section whose body is
   non-empty and states the duty in the right-hand column. A renamed
   phase is a missing phase (identifiers are exact, case-insensitive).
   An empty or duty-less section fails even when the row exists.
   Optional identifiers may be deleted freely; forbidden ones may not
   appear at all.

   | Skill | Required identifiers (in this dependency order) | Required duty of each | Optional | Forbidden |
   |---|---|---|---|---|
   | `hex-execute` | Discover → Stub → Specify → Implement → Review-Fix Loop → Merge and commit | Stub: signatures/types that compile with no implementations. Specify: tests that **fail** against the stub. Implement: makes those tests pass. Review-Fix Loop: ≥1 reviewer role, a bounded round count, and an exit gate. Merge and commit: merges the worktree and commits. | Verify-Architecture, Cross-model review | — |
   | `hex-review` | Discover → Stage 1 → Verdict & Output → Fold-Back (required when `adr_0005` is accepted) | Stage 1: ≥1 reviewer role producing classified findings. Verdict & Output: emits the verdict and **writes nothing** but the plan Status block and convergence rows (`hex-review/SKILL.md:3,:278-282`). Fold-Back: resolves one fold target, applies the delta set or states why not, prints the Fold-Back block (reconciles with `adr_0005`, which adds this phase — a fork must not drop it once that ADR is accepted). | Stage 2, Root-cause analysis, Cross-model | any phase that writes a file outside the contracts named in `hex-review/SKILL.md` § Constraints (the plan artifact, convergence rows, and — when `adr_0005` is accepted — the resolved fold target) |
   | `hex-plan` | Discover → Classify → Design → Decompose → Review | Decompose: emits work packages with file lists. Review: ≥1 reviewer role. | Research | — |
   | `hex-architect` | Discover → Classify → Reason & Design → Review | Reason & Design: emits the ADR or system design. Review: ≥1 reviewer role. | Research | Decompose (`hex-architect/tier-low.md:7-8`) |

   The required sets are the intersection of the three shipped tier
   files per skill, which is why `Verify-Architecture` (absent from
   `hex-execute/tier-low.md` except as a "skipped" marker) is optional
   and `Stub` is not — S-212's fork deleting Verify-Architecture is
   legal precisely because of that derivation, and a fork deleting
   `Specify` is not.
7. **No phase declares a user gate.** The single meta-plan approval
   gate is the only approval point (`protocol.md:45-49`); a `Gate` cell
   is a machine/verification condition, never a question.

**On any validation failure**: announce `Error: <what>. Fix: <where>`,
**fall back to the shipped tier file for that skill and tier**, and run.
A broken workflow file degrades to shipped behaviour; it never aborts a
run and never runs half-applied.

**Forking a shipped workflow, end to end.**

1. `/hex-init workflows` lists the four skills × three tiers and the
   phase list of each, marking which are already forked.
2. On selection, it copies `hex-<skill>/tier-<tier>.md` to
   `.agents/workflows/<skill>-<tier>.md`, prepends the header
   table derived from the shipped phases, and stamps
   `Forked from hex-<skill>/tier-<tier>.md @ hex <version>`.
3. The user edits the copy — delete a phase row and its section, add a
   role, re-point an edge.
4. `/hex-init` prints the diff (phases added/removed/re-pointed) and
   asks for consent, then writes the `workflows.<skill>.<tier>` pointer
   into the Tier A block.
5. Every subsequent run announces `Workflow: <path> (forked from
   <shipped> @ <version>)`.
6. A later `/hex-init` re-audit compares the stamped version against
   the installed one; on a mismatch it **reports drift and shows what
   changed in the shipped file** — it never auto-merges, and never
   rewrites the fork.

#### `/hex-init` as an interactive wizard

**Scope amendment to the single-gate rule.** The text being changed is
`hex-init/SKILL.md:76-77` ("Present every proposal in one batched
approval — never one gap at a time, and never as a mid-flow
interruption"). `DESIGN.md:13-21` and `protocol.md:45-49` forbid
mid-flow questions for *orchestrators* and are the principle hex-init's
line inherited, not a rule that bound hex-init directly
(`hex-core/SKILL.md` itself distinguishes the four orchestrators **and**
`/hex-init`). That rule exists because
the *orchestrators* run long autonomous swarms where an interruption
strands parallel workers. **hex-init runs no swarm.** The rule is
hereby re-scoped: *the single-gate rule governs the four orchestrators;
`/hex-init` is a configuration wizard and is exempt.* The exemption is
narrow and named — it does not extend to any skill that spawns workers.

The wizard's shape, transcribed from `openspec config profile`,
`openspec init` and `openspec workset create` (research § Interactive
init design):

- **Flag-provided answers are validated BEFORE any prompting.** "A bad
  flag cannot discard a finished wizard walk." Everything already known
  is checked first.
- **`[n/N]` progress headers**, and each step label says why the step
  matters inline, not just its field name.
- **Per-question validation that re-prompts in place** — the validator
  returns the error string; the question re-asks without losing prior
  answers. Answers already supplied echo back
  (`Added 'reviewer:accessibility' (.agents/workers/)`).
- **Questions are skipped when the answer is detectable or inferable** —
  the harness in use, whether `.agents/worktrees/` is gitignored,
  whether a project persona file exists, the verification command,
  anything answered on a previous run and unchanged. Asking a
  detectable thing is the tell of a badly designed init. Conditional
  questions fire only on a trigger: the perspectives question only when
  Step 1's audit found a security-sensitive path or a project persona;
  the research-axes question only when research artifacts exist.
- **Current state is printed before the first question**, values carry a
  `[current]` label as well as being the default, and multi-selects are
  pre-checked from current state.
- **A diff is printed before the write**, one line per changed key, old
  → new, naming derived keys alongside touched ones.
- **Apply is a separate consent** after the write.
- **Cancellation is documented**, and every refusal pairs
  `Error:` with `Fix:`.
- **Non-interactive twin, documented**: `--yes` accepts every
  recommendation without prompting; `-d key=value` (repeatable) sets one
  key; both are hex's existing "flags stay for non-interactive
  override" (`DESIGN.md:114-133`). No TTY, or `-d` given, or `CI` set →
  non-interactive. A non-interactive refusal enumerates the accepted
  values inline so the fix is paste-able.
- **Idempotency split**, from OpenSpec's observed re-run: regenerate
  deterministic scaffolding always, **never clobber the user-owned
  block**. Keys the user did not touch keep their values *and their
  comments*; a key dropped from the vocabulary in a later hex version is
  reported as deprecated in the summary, never silently deleted.

### One-way-door flag

**Key names freeze at the first `grim release`** — the same door
`adr_0001` flagged for capability-class names. Once a consumer project
has an instantiated `hex.md` referencing `limits.max-workers` or
`tiers.hex-plan.medium.counts`, renaming any of them breaks that project
silently (the LLM reads a key it has no rule for, and does nothing). The
vocabulary is free to change **now** and semi-frozen after. Everything
in the Migration section marked *before release* is there for this
reason.

**What freezes, layer by layer** — the section previously named only
"key names", which left the semantics unstated:

| Layer | Frozen at first release? |
|---|---|
| Top-level v1 key names (`models`, `adversary`, `limits`, `perspectives`, `research-axes`, `tiers`) | **Yes.** A rename is a silent no-op in every consumer. |
| `workflows` (v2) | **Not at the first release** — it is unimplemented until Wave 3, so there is nothing for a consumer to reference. It freezes at the release that follows Wave 3. |
| Nested key names (`limits.max-workers`, `tiers.*.counts`, `perspectives.security-sensitive-paths`, …) | **Yes**, same reason, for the v1 keys. |
| `perspectives.always` rule-object field names (`role`, `when`, `skills`, `phase`) | **Yes** — a renamed field is read as an unknown field and dropped by merge rule 9, silently narrowing or widening the rule. |
| Merge-rule **semantics and order** (rules 1–10) | **Yes.** See below. |
| Workflow file format (C-208) | No — degrades loudly. |
| Wizard question order (C-212) | No — pure UX. |

**Merge-rule semantics are the subtler door, and they freeze too.** A
renamed key at least fails visibly-ish (nothing happens). A changed
merge rule needs no edit to an existing `hex.md` to take effect: rule
6's reverse-declaration-order tie-break could be reversed in a hex
upgrade and every consumer's next run would drop a different reviewer,
with an announce block that looks correct because it faithfully
describes the new rule. There is no signal that the *rule*, not the
input, changed. Two mitigations, both required:

- The announce block names the vocabulary version in effect
  (`# hex config, vocabulary v1` in the block is the input side; the
  announce line is the resolver side), so two runs that resolved
  differently are distinguishable after the fact.
- **A behaviour-changing edit to rules 1–10 requires a major hex
  version bump and a `DESIGN.md` round**, exactly as a key rename
  would. Clarifying wording that cannot change a resolved panel is not
  a behaviour change.

### Quantified Impact

| Measure | Before | After |
|---|---|---|
| Cannot-express items closed (research § D, 8 items) | 0 | 6 (D-1 partially, D-2, D-3, D-5, D-6, D-8; D-4 and D-7 stay open) |
| Top-level config keys | 0 (prose only) | 6 frozen at first release (vocabulary v1) + `workflows` in v2 = 7 |
| New reference files in the bundle | — | 1 (`hex-core/references/config.md`) |
| Orchestrator-side always-loaded cost of `config.md` | — | **0** — conditional-load: read only when a fenced block exists in `hex.md › Preferences`. Budget when it *is* read: ≤ 200 lines, the same ceiling the other `hex-core/references/*.md` contracts hold to. |
| Files touched | — | **23** unique files across Waves 1–2 (the release-blocking set); **26** across all three waves (see Migration) |
| Config lines a *default* project writes | 0 | 0 — the block is optional and absent is normal |
| Doc surface added to `hex.md` per fully-configured project | ~6 prose lines | **~36 non-blank block lines** (counted against the copy-pasteable example above; ~41 including blanks, ~28 excluding comments) + an optional forked tier file |

### Consequences

**Good.**

- The two enforcement gaps that exist *today* close, independent of
  everything else (Option A, folded in as work item 1).
- The persona mechanism at `workers.md:65-75` finally has an invocation
  end: `perspectives.always` naming a project persona is the wiring.
- Two shipped coverage holes become closable by a project:
  hex-architect never spawns `reviewer:performance` or
  `reviewer:user-feedback` at any tier, and hex-plan never spawns plain
  `reviewer:quality` (research Table 2).
- Failure is loud. Today a misspelled preference does nothing silently;
  after this, it prints a complaint and a fix.

**Bad — the research's predicted costs, recorded as the decider was
warned of them.**

- **Requirement 2 (explicit counts) is the one hex's own performance
  research argues against.** Same-kind reviewers plateau at ~5, and
  error amplification runs 1.0× single-agent → 4.4× centralized → 17.2×
  independent/uncoordinated
  (`hierarchical-execution-performance.md:9-19,:72-92`). A project that
  sets `Review-Fix.reviewer:security: 3` is buying the flat part of the
  curve and paying tokens for it. *Mitigation:* `counts` is capped by
  `min(8, max-workers)` (merge rule 6), every count that deviates from
  the shipped baseline is announced with its delta, and the shipped
  guidance in `config.md` states the plateau explicitly next to the key.
  hex still never *recommends* a same-role count above 1; it only stops
  refusing one.
- **Requirement 3 (tier redefinition) makes announce blocks
  project-relative.** "medium" stops meaning the same thing in two
  repos, which is exactly the objection the research raised.
  *Mitigation:* the mandatory `[project-redefined: …]` line — the label
  never travels without its deltas — plus the constraint that
  `inherits` may only name another shipped tier, so a redefinition is
  always describable as "medium here = shipped high, minus these".
- **Requirement 4 (workflow DAGs) is the GSD bill.** GSD paid a
  1,111-line configuration reference and per-key precedence prose for
  ~90 keys; Spec Kitty drafted the full agent roster (367 lines) and
  never shipped it. *Mitigation:* the DAG is not a new grammar — it is
  a forked tier file, so the doc for it is the tier file that already
  exists, and the config cost is **one pointer key**. The reference
  cost lands in one new file (`config.md`), and the fork lives outside
  `hex.md` so it never enters an unconfigured project's context.
- **Fork drift is now hex's problem.** A project that forks
  `tier-medium.md` stops receiving improvements to it. *Mitigation:*
  the version stamp plus `/hex-init` re-audit drift reporting. hex
  never auto-merges a fork.
- **Seven keys is seven things every orchestrator must remember to
  honour**, and hex has no test that they do — the GSD "absent key =
  enabled" restatement problem in miniature. *Mitigation:* the rules
  live in exactly one file (`config.md`), linked never copied; the
  announce block is the mechanical check (a rule that did not print did
  not fire); and `hex-review`'s consistency pass gets the announce block
  as a reviewable artifact.
- **The announce block is self-reported, not independent
  verification** — and this is the design's weakest link, stated
  plainly. It is produced by the same instruction-following pass whose
  reliability the whole risk is about, so the caught failure is "a rule
  did not print"; the *uncaught* failure is a rule misapplied and then
  described in a well-formed, plausible-looking line — merge rule 6
  dropping the wrong `always` entry, or dropping in the wrong order,
  printed as a confident `[… dropped — concurrency cap reached]`. That
  is strictly worse than the unknown-key case the design already
  handles loudly. The instruction-count literature puts this squarely
  in the fallible regime rather than the near-perfect one: IFScale
  (arXiv:2507.11538) measures frontier models degrading well before
  their ~68%-at-500-instructions ceiling, with a documented bias toward
  earlier instructions, and the "curse of instructions" (Harada et al.
  2024) shows all-instructions-satisfied rates decaying roughly
  exponentially in instruction count — and Tier A alone asks a reader
  to hold 7 keys and 10 merge rules simultaneously, with Tier B adding
  7 more checks. *Mitigation:* the explicit pre-print self-check in the
  announce-block spec (re-verify rules 4–7 before emitting). Re-ask and
  checklist verification is the cheapest measured lever in that same
  literature, and it strengthens the existing mitigation rather than
  adding config surface. It does not make the block trustworthy on its
  own; a real check needs a code layer hex does not have.

**Neutral.**

- Unconfigured projects are byte-identical to today, **including
  context cost**: `config.md` is a conditional-load reference, read only
  when `hex.md › Preferences` actually contains a fenced block, so the
  new file adds zero tokens to a default run. Absence of the block is
  the signal, exactly as absence of dotted sub-WP IDs is the signal in
  `adr_0002` C-105 — no version marker, no detection.
- No JSON Schema, no `$schema` modeline, no second config file for
  Tier A. OpenSpec, with a real validator, ships neither.

## Component contracts

Numbered `C-2xx` to avoid colliding with `adr_0001`'s `C-00x` and
`adr_0002`'s `C-1xx` when all three are cited downstream. UX scenarios
`S-2xx` per `protocol.md` § Traceability IDs.

| ID | Contract | Home / changed file |
|---|---|---|
| **C-201** | **Enforcement semantics of the existing limits** — effective concurrency cap = `min(8, limits.max-workers)`, counted recursively; a stored `loop-rounds` is a ceiling on both the per-tier default and on `--loop-rounds`, never a raise; `artifact-loop-rounds` stays opt-in with `1` = shipped behaviour. Independently shippable; no new syntax. | `protocol.md` § Worker coordination + § Review-Fix Loop (sole source) |
| **C-202** | **Config carrier** — one fenced `yaml` block, first content under `## Preferences` in `hex.md`; prose bullets continue below it; missing file/section/block is normal; written only by `/hex-init` with consent; orchestrators read, never write. | `memory.md` § The three sections, § Editing rules |
| **C-203** | **Key vocabulary** — the top-level keys, their types, defaults and effects exactly as tabulated in the Decision. **v1 is the six Tier A keys and is frozen at the first `grim release`; `workflows` is v2 and is not** (C-223). `config.md` is a **conditional-load** reference — read only when `hex.md › Preferences` contains a fenced `yaml` block, so an unconfigured project pays nothing for it. | new `hex-core/references/config.md` (sole definition site) |
| **C-204** | **Merge and resolution rules** — the ten numbered rules: scalars replace, maps merge per key, lists replace wholesale, `never` cannot remove `reviewer:spec`, security suppression is fail-closed behind an attestation plus a no-match test (C-218), the cap batches while the phase ceiling displaces preference-added spawns by a terminating procedure (C-216), mandatory-role `0` refused, unknown key warns once with `Error:`/`Fix:`, malformed value ignored per-key, unparseable block skipped whole. Three-input precedence unchanged — `tiers`/`workflows` rewrite layer 1, never add a layer. | `config.md`; pointer from `protocol.md` § Spawn-selection precedence |
| **C-205** | **`perspectives.always` / `never`** — the rule object (`role`, `when`, `skills`, `phase`), the resolution `baseline ∪ always(matching) − never`, and the documented persona→panel wiring: naming a `.agents/workers/<role>.md` persona in `always` is how it enters a launch list. | `config.md`; `workers.md` § Project-local personas gains the pointer |
| **C-206** | **`tiers.<skill>.<tier>`** — `inherits` (a shipped tier name only), `counts` (`<Phase>.<role[:focus]>` → int, `0` removes, mandatory roles refuse `0`), `overlays` (per-project axis defaults, below user flags). Rewrites the layer-1 baseline. Tier *vocabulary* stays `low\|medium\|high` + `auto`; only tier *content* is redefinable. | `config.md`; `protocol.md` § Tier grammar gains one qualifying sentence |
| **C-207** | **Mandatory tier-redefinition disclosure** — any run whose baseline was amended by `tiers` prints `[project-redefined: <phase>.<role> <shipped>→<resolved>]` for every delta, and prints the line even when resolved counts equal shipped ones. A redefinition that is not announced is a spec violation, in the same shape as `models.md:47-57`. All seven top-level keys have a printed line (`Adversary` and `Research axes` print when set), and the block is emitted only after the pre-print self-check re-verifying merge rules 4–7. | `protocol.md` § The meta-plan approval gate (announce-block contract) |
| **C-208** | **Workflow file format** — markdown fork of a shipped tier file: header table (`Phase \| Depends on \| Roles \| Count \| Gate`) plus one `## Phase: <id>` section per node, plus a `Forked from <file> @ <version>` stamp. Edges are happens-before, within one file only, orthogonal to the WP-level DAG (`adr_0002` C-101). | new `hex-core/references/config.md` § Workflows (sole source) |
| **C-209** | **Workflow validation, skill-applied** — the seven checks in order (unique ids; edge targets exist; no cycle; roles resolve; cap respected; skill invariants hold — the required phase identifiers are **read at validation time from the shipped tier file's own `## Phase N:` headings** (per C-220/C-221), not a list copied into `config.md`: hex-execute keeps Stub→Specify→Implement→Review-Fix, hex-review declares no write phase, hex-architect declares no Decompose; no phase declares a user gate). On any failure: `Error:`/`Fix:`, **fall back to the shipped tier file**, run. Never abort, never half-apply. | `config.md` |
| **C-210** | **Dispatch interception** — dispatch step 7 in all four orchestrators reads `workflows.<skill>.<tier>` first and the shipped `tier-<tier>.md` otherwise; the announce block always names which was used and, for a fork, its source and stamped version. | the four `SKILL.md` dispatch steps (`hex-plan:157-160`, `hex-execute:178-181`, `hex-review:174-177`, `hex-architect:150-153`) |
| **C-211** | **Single-gate rule re-scoped** — the rule governs the four orchestrators; `/hex-init` is a configuration wizard and is exempt. The exemption is named, and does not extend to any skill that spawns workers. | `DESIGN.md` (new dated round); `protocol.md:45-49` gains the scope sentence |
| **C-212** | **`/hex-init` wizard** — flags validated before any prompting; `[n/N]` headers with why-it-matters labels; per-question validation re-prompting in place; questions skipped when detectable or inferable; conditional questions gated on audit findings; `[current]` labelling and pre-checked multi-selects; printed diff before the write; separate apply consent; `Error:`/`Fix:` on every refusal; documented cancellation. | `hex-init/SKILL.md` (Steps 4½ and the flow preamble) |
| **C-213** | **Non-interactive twin** — `--yes` accepts every recommendation; `-d key=value` (repeatable) sets one key; triggered by no TTY, `-d`, or `CI`. Refusals enumerate accepted values inline. | `hex-init/SKILL.md` § arguments |
| **C-214** | **Fork lifecycle** — `/hex-init workflows` lists forkable skill×tier pairs, copies, stamps, diffs, consents, writes the pointer; a re-audit compares stamps, reports drift with what changed upstream, and never auto-merges or rewrites a fork. | `hex-init/SKILL.md`; `hex-init/references/audit.md` (new audit item + copy-ready block) |
| **C-215** | **Idempotent re-run** — untouched keys keep values *and* comments; a key dropped from the vocabulary is reported deprecated, never silently deleted; deterministic scaffolding regenerates, the user-owned block is never clobbered. | `hex-init/SKILL.md` § Re-entrancy |
| **C-216** | **Concurrency cap ≠ panel size.** `min(8, max-workers)` bounds workers running *at once*; a phase exceeding it runs in sequential batches in declaration order and holds its gate until the last batch returns, so a reduced cap **never** drops a baseline perspective. Separately, `ceiling = max(shipped phase baseline total, min(8, max-workers))` bounds what preferences may add, and the merge-rule-6 procedure (drop last-declared `always` spawns one at a time, then reduce the `counts` entry with the largest excess above baseline by one, ties by ascending `<Phase>.<role[:focus]>`, re-evaluating each step) is the only displacement mechanism. It terminates at the shipped baseline and never goes below it. | `config.md` § Merge rules; `protocol.md` § Worker coordination gains the "at once, batches otherwise" sentence |
| **C-217** | **Glob and target-file-set semantics** — repository-relative `/`-separated paths; gitignore-style `?`/`*`(intra-segment)/`**`(cross-segment, matches zero segments)/`{a,b}`/`[a-z]`; bare directory ≡ `dir/**`; case-sensitive; dotfiles ordinary; symlinks match their own path; anything else is an unparseable glob (merge rule 9). The target file set is defined per skill — hex-review: the diff's added/modified/deleted paths with renames contributing **both** paths; hex-execute: WP file lists plus paths written so far, re-evaluated per phase; hex-plan: input file lists + Discover reads + drafted WP paths; hex-architect: decision-input paths + Discover reads. An empty set means `when:` rules do not fire, silently and normally. Under a plan carrying a `Repo` column (`adr_0004`), `when:` globs evaluate against **lead-repo paths only** — a satellite repo's paths never enter the target file set and never match — so this frozen, repo-less field set stays valid across federation without a repo dimension; a future repo-qualified glob syntax is the widening path if a satellite ever needs its own path-scoped rule. | `config.md` § Perspectives |
| **C-218** | **Fail-closed security suppression** — `never: [reviewer:security]` is honoured only when `perspectives.security-sensitive-paths: none` is declared **and** no sensitive path matched; every other case, including ambiguity, refuses and runs the reviewer with an `Error:`/`Fix:` pair. Enforcement is self-reported, not a control: the Security NFR states this and disclaims compliance use, matching GitLab Duo's own `fileFilters` caveat. | `config.md` § Merge rules; NFR § Security |
| **C-219** | **`tiers` resolution order** — `inherits` (full replacement by the *shipped* named tier, non-transitive, never chaining a sibling project redefinition), then `counts` validated and delta-computed **against the inherited baseline**, then `overlays`, then panel resolution, then the C-216 ceiling. A `counts` phase absent from the inherited baseline is malformed (merge rule 9). | `config.md` § tiers |
| **C-220** | **Phase identifiers are derived, not indexed** — the identifier is a tier file's `## Phase N:` heading text, cut at the first `(` or ` — `, trimmed, matched case-insensitively; the tier file is the sole index and hex ships **no** phase-index file (it would be a second source of truth). Identifiers are per skill *and* per tier. Under an active workflow fork the **fork's** `Phase` column is the index; a preference naming a phase the fork removed is ignored per entry and warned, never relocated to a neighbouring phase and never aborting. | `config.md` § Phase identifiers; the twelve `tier-*.md` headings are the authority |
| **C-221** | **Workflow `Count` grammar and invariant evidence** — `Count` is `<int>`, `<int>×WP` (hex-execute only, resolved from the plan's WP list, leaves counting recursively toward the cap), or `—`; a range is malformed and read as its lower bound with a warning. Validation check 6 is evaluated against the **required phase identifier set and required observable duty** per skill. The required identifier set is **derived at validation time from the shipped tier files' own `## Phase N:` headings** (per C-220), read from the file the fork's `Forked from <file> @ hex <version>` stamp anchors on — never a static list copied into `config.md`, which would invert the hex-core→consumer dependency and go stale the first time a tier file changes. Its value at time of writing is: hex-execute Discover→Stub→Specify→Implement→Review-Fix Loop→Merge and commit; hex-review Discover→Stage 1→Verdict & Output→Fold-Back (Fold-Back required once `adr_0005` is accepted and its phase reaches the shipped hex-review tier files — the derivation then picks it up with no edit here); hex-plan Discover→Classify→Design→Decompose→Review; hex-architect Discover→Classify→Reason & Design→Review, Decompose forbidden. The optional set is the same derivation's by-product — the intersection of the skill's three shipped tier files' headings. A renamed or empty phase fails the check. | `config.md` § Workflows |
| **C-222** | **Dotted-key aliasing** — nested and flat spellings normalize to one leaf path *before* any merge rule; a duplicate leaf resolves last-declared-wins with an `Error:`/`Fix:` naming both spellings; a scalar/map type conflict drops the scalar and keeps the map (merge rule 9). | `config.md` § Key vocabulary |
| **C-223** | **Two vocabulary versions** — v1 is the six Tier A keys and freezes at the first `grim release`; `workflows` is v2, ships in Wave 3, and freezes at the release after it. A v1 reader treats `workflows` as an unknown key (merge rule 8), which is correct because the dispatch interception it names does not exist yet. Merge rule 8's key enumeration lists the reader's version. | `config.md`; the block's `# hex config, vocabulary vN` comment |

**UX scenarios.**

| ID | Scenario |
|---|---|
| **S-201** | A repo with no `hex.md` runs `/hex-plan`. No block, no warnings, shipped defaults, announce block identical to today. |
| **S-202** | `perspectives.always` names `reviewer:security` with `when: "hex/hex-core/**"`; a diff touches that path under `hex-review` medium. The reviewer is added and the announce block attributes it to the hex.md preference and names the matched glob. |
| **S-203** | The same rule fires under `hex-review` **high**, whose Stage 2 phase is already at its shipped baseline of 6 (2 + 6 = 8 across the two stage phases). The phase ceiling is `max(6, min(8, max-workers))`; with `max-workers` unset it is 8, so the added reviewer fits. With `max-workers: 6` the ceiling is 6 and the `always` entry — the only preference-added spawn — is dropped by merge rule 6 step 2, announced as `[reviewer:security dropped — phase ceiling 6 reached]`. No baseline perspective is displaced in either case. |
| **S-204** | `perspectives.never: [reviewer:security]` while a security path matched. The suppression is **refused** — the security reviewer runs, and the announce block prints the `Error:`/`Fix:` pair naming the matched glob (merge rule 5, collision case). |
| **S-204b** | The same `never: [reviewer:security]` on a run where no security path matched. The suppression is honoured and printed as a warning line, not omitted quietly (merge rule 5, no-match case). |
| **S-205** | `tiers.hex-plan.medium.counts: {Research.researcher: 3}`. A medium plan run spawns 3 researchers and prints `[project-redefined: Research.researcher 1→3 (hex.md tiers)]`. |
| **S-206** | A typo — `perspective.always`. One warning line pairing complaint and fix; the rest of the block applies; the run proceeds. |
| **S-207** | `workflows.hex-execute.medium` points at a fork with a cycle. `Error:`/`Fix:` naming the cycle path, fall back to the shipped `tier-medium.md`, run completes. |
| **S-208** | `/hex-init` on a repo with a project persona under `.agents/workers/`. The perspectives question fires (trigger met); the harness question does not (detected); the diff is printed; apply is a separate consent. |
| **S-209** | `/hex-init --yes -d limits.max-workers=6` in CI. No prompts, the flag validated before anything else, the resulting block written, a three-list summary printed. |
| **S-210** | A fork stamped `@ hex 0.1.0` on a repo running hex 0.2.0 where the shipped `tier-medium.md` changed. Re-audit reports the drift and what changed upstream; the fork is untouched; runs continue on the fork. |
| **S-211** | `tiers.hex-review.high: {inherits: medium}`. A high-tier review run resolves to medium's panel and phase baseline, and the announce block prints the mandatory `[project-redefined: high inherits medium (hex.md tiers)]` line **even though every resolved count happens to equal medium's shipped ones** — C-207's print-even-when-identical clause. Covers C-206's `inherits` half. |
| **S-212** | Workflow fork, happy path, end to end. `/hex-init workflows` lists the twelve skill×tier pairs and forks `hex-execute/tier-medium.md` to `.agents/workflows/hex-execute-medium.md` with the header table and the `@ hex 0.1.0` stamp; the user deletes the Verify-Architecture row and its section; `/hex-init` prints the phase diff, takes consent, and writes `workflows.hex-execute.medium`. The next `hex-execute` medium run passes all seven validation checks, announces `Workflow: .agents/workflows/hex-execute-medium.md (forked from hex-execute/tier-medium.md @ hex 0.1.0)`, and **actually runs without the Verify-Architecture phase**. Covers C-208/C-210/C-214 in their working, not failing, mode. |
| **S-213** | `limits.max-workers: 3` on a `hex-review` **high** run with no preferences at all. The Stage 2 phase's 6 baseline reviewers are **not** reduced to 3: they run as two sequential batches of 3, the phase gate holds until the second returns, and the announce block prints `[Stage 2 batched 3+3 — concurrency cap 3 (hex.md)]`. Every shipped perspective still runs. Covers C-216's batching half and closes the "cap below baseline is unsatisfiable" case. |
| **S-214** | `tiers.hex-review.high.counts: {Stage 2.reviewer:security: 3, Stage 2.reviewer:performance: 2}` (baselines 1 and 1) with `max-workers` unset. Resolved Stage 2 total = 6 baseline + 2 + 1 = 9; ceiling = `max(6, 8)` = 8; overshoot 1. No `always` entries exist, so step 2 supplies nothing; step 3 picks the entry with the largest excess (`reviewer:security`, +2 vs `reviewer:performance` +1) and reduces it by **one**, to 2. Overshoot 0, procedure stops. The announce block prints `[project-redefined: Stage 2.reviewer:security 1→3, clamped 3→2 — phase ceiling 8; Stage 2.reviewer:performance 1→2]`. Covers C-216's procedure, its one-unit step and its tie-break input. |
| **S-215** | `perspectives.never: [reviewer:security]` with **no** `security-sensitive-paths` attestation, on a run where nothing obviously security-shaped matched. The suppression is **refused** anyway — the security reviewer runs and the announce block prints the missing-attestation `Error:`/`Fix:` pair. The permissive outcome is unreachable without the user having written the attestation down. Covers C-218's fail-closed default; S-204b is the same key *with* the attestation and no match, where the suppression is honoured and warned. |
| **S-216** | `tiers.hex-review.high: {inherits: medium, counts: {Stage 2.reviewer:docs: 2}}`. The baseline becomes `hex-review/tier-medium.md` in full; `Stage 2` and `reviewer:docs` are validated against *medium's* phase set and *medium's* baseline count, and the delta announced is against medium, not high. A sibling `counts` key naming a phase that exists only in `high` would be dropped with an unknown-phase warning. Covers C-219's ordering, which S-211 (inheritance without counts) cannot reach. |
| **S-217** | An active `workflows.hex-execute.medium` fork has deleted the Verify-Architecture phase (as in S-212), while `perspectives.always[1]` still carries `phase: Verify-Architecture`. That one entry is **ignored** — not relocated to Stub or Review-Fix — and warned with the fork's valid phase list; every other `always` entry and every `counts` key still applies, and the run completes. Covers C-220's stale-reference clause. |
| **S-218** | A block declares both `tiers: {hex-plan: {medium: {counts: {Research.researcher: 2}}}}` and, later, `tiers: {hex-plan.medium: {counts: {Research.researcher: 3}}}`. Both spellings normalize to one leaf; the later declaration wins (3), and the announce block prints the duplicate-key `Error:`/`Fix:` naming both spellings and the line used. Covers C-222. |

## Non-Functional Requirements

| Axis | Impact |
|---|---|
| Cost (tokens) | **Affected, bounded and opt-in.** Tier A adds ~36 non-blank lines to a fully-configured `hex.md` (the ADR's own example, comments included), read once per run by an orchestrator that already reads the whole file. Tier B adds nothing to a project that does not fork, and a fork *replaces* the shipped tier file rather than adding to it. The counter-pressure is real, though: `counts` lets a project buy the flat part of the reviewer-returns curve, and hex will not stop it — only announce it. |
| Operability | **Affected, mixed — the main cost.** Gains: enforcement semantics that today are undefined; a single definition site (`config.md`); a failure mode that prints rather than vanishes. Costs: seven keys, ten merge rules, seven workflow checks and a fork-drift lifecycle are all new surface a reader must hold, and hex has no automated test that any of it is honoured. The announce block is the only mechanical check, which is why C-207's disclosure requirement is normative rather than advisory — and it is self-reported, so it catches "a rule did not print", never "a rule printed a plausible wrong answer" (see Consequences). |
| Security | **Affected. Fail-closed by construction, self-reported in enforcement — and the second half is not a caveat on the first, it is the ceiling.** `perspectives.never` can suppress the security reviewer, the one genuinely risky capability added here. Two structural guards: `reviewer:spec` is unremovable (merge rule 4), and suppressing `reviewer:security` requires **two** independent conditions — an explicit `perspectives.security-sensitive-paths: none` attestation *and* no matched sensitive path — with **every other case, including the ambiguous one, refusing** (merge rule 5). The attestation exists so that the *forgetful* branch is the safe one: a reader that never reaches rule 5 finds no attestation and runs the reviewer, where a bare `never` would have suppressed it. **What this is not:** an enforced policy. There is no parser, so the guard is executed by the same instruction-following pass whose reliability is the risk — a reader can misclassify a path as non-sensitive, honour a `never`, and print a plausible warning line, and nothing in hex catches that. This is the identical failure mode the Consequences section names for the announce block, and it is the vendor caveat GitLab Duo publishes for `fileFilters`, the nearest shipped analog: "guidance for the AI reviewer, not enforced policies… Do not rely on custom instructions for security controls, compliance obligations, or other requirements where consistent enforcement is needed." **hex makes the same disclaimer its own: a project with a compliance obligation must not treat `perspectives` as satisfying it.** What this design buys is a strictly better default failure direction than the shipped status quo (where lowering `--breadth` silently drops security coverage with no line printed at all), not a control. A real control needs the code layer `DESIGN.md` declines to build. Model resolution is unchanged and still never orchestrator-class (`adr_0001` C-002). |
| Portability | **Not degraded.** No harness capability is assumed; markdown and a fenced block work identically on all four. `models.*` remains the only place literal model names appear, and only as user-set overrides (`DESIGN.md:216-217`). |
| Scalability | Not meaningfully affected — no runtime, no service. The concurrency cap is unchanged in value and now explicitly separated from panel size: it bounds simultaneity (phases batch), while the per-phase ceiling bounds what preferences may add (merge rule 6). Wall-clock time can therefore rise on a low `max-workers` where it previously would have silently lost coverage. |
| Availability | Not affected. |

## Constitution deviations

`hex/DESIGN.md` is the constitution. Four resolved decisions are
amended, plus one `memory.md` rule; each amendment needs a new dated
round appended to `DESIGN.md` in the same change (C-211 covers the
single-gate one explicitly).

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **`DESIGN.md:63-65`** — "the only consumer of this layer is an LLM… So no TOML: one markdown memory file, structured by plain headings." A fenced YAML block is structured config in a file that was to hold only headings. | The pivot's premise ("no parser reads it") is a reason a schema cannot be *validated*, not a reason keys cannot exist — GSD proves the point on hex's exact architecture. The actual defect is that prose has no key an orchestrator can look for: two readers of `Limits: max-workers 6` can disagree about whether it binds (research Finding 2), and a misspelling fails silently. | Prose bullets with written semantics (Option A) close the two *existing* gaps but cannot express a `never` list, a path-scoped rule, or a count, which is the requirement set. The block stays *inside* the markdown file, under its owning heading, so the rest of the pivot holds: one file, no TOML, no second config file, no schema. |
| **`DESIGN.md:335-338`** — "Security-path globs: classify.md generic markers + `hex.md › Preferences` path hints — **no separate config table**." `perspectives.always` with `when:` globs is precisely a config table. | Requirement 1. The shipped mechanism has no subtractive lever at all (`never` does not exist) and its additive lever is prose the classifier "folds in" (`hex-review/classify.md:51-53`) with no stated resolution. `hex-review` high being saturated at 8 makes an unstated fold-in rule actively unsafe — something must be dropped, and today nothing says what. | Keeping globs in `classify.md` only means every project edits a shipped skill to state its own paths — the second-source-of-truth failure `DESIGN.md:36` exists to prevent, at four files per project. The generic markers **stay**; the table layers on top with a stated resolution and a stated displacement rule (merge rule 6). |
| **`DESIGN.md:218-219`** — "Tier methodology unchanged; project hints + gate selection layer on top of it, never replace it." `tiers`/`workflows` **rewrite layer 1** rather than layering on top of it: `inherits` is "a replacement, not a merge" — a project's `high` resolves to shipped `medium` *in full*, `high`'s six shipped phases "not consulted" — and a `workflows` fork swaps the shipped phase plan outright. (This is distinct from the three-input precedence `DESIGN.md:114-133`, which *is* preserved — no fourth input is added; it is the *methodology-unchanged* half of the tier rule that is amended.) | The rule exists so a tier label carries **one methodology across every project** — "medium" means the same phase plan, counts and gates everywhere it is read. Requirements 2, 3 and 4 are exactly the ability to make it not: per-project counts, per-project tier content, per-project phase sequences. C-207 retires the reason the rule protects. Its mandatory `[project-redefined: …]` disclosure prints every delta at **every** gate — and prints it *even when the resolved counts equal the shipped ones* — so the label is never allowed to travel without its divergence made visible. What the rule actually guards (a reader is never silently misled about which methodology ran) survives via disclosure rather than via uniformity; only the uniformity itself is given up. | Leaving tier methodology literally unchanged is Option A/B, which cannot express requirements 3 and 4 under any reading (the Decision's feasibility gate). The residual is **priced honestly, not waved away**: a `counts`/`inherits` delta is enumerated in full in the announce block, but a `workflows` fork's divergence is disclosed as a `Workflow: <path> (forked from <shipped> @ <version>)` *pointer* — "a fork ran", not a line-by-line phase diff. A reader must open the fork to see what changed; the label's divergence is *named at every gate* but not *expanded* for the Tier B case. That residual is accepted, and the version stamp plus `/hex-init` re-audit drift report (C-214) is the only tool that narrows it. |
| **`hex-init/SKILL.md:76-77`** — "Present every proposal **in one batched approval** — never one gap at a time, and never as a mid-flow interruption." That is the text this decision actually changes; `DESIGN.md:13-21` / `protocol.md:45-49` ("single meta-plan approval gate, never mid-flow questions") are scoped to the orchestrators and never literally bound hex-init — they are the nearest constitutional principle, extended to hex-init by practice. The wizard asks up to five questions in sequence. | Requirement 5, and the rule's own rationale does not reach hex-init: the prohibition exists because an interruption strands a running swarm, and hex-init spawns no workers. `openspec config profile`, `init` and `workset create` all ship multi-step interactive flows in exactly this position. | A single batched approval (today's Step 2) is what hex-init already does, and it cannot do conditional questions, per-question validation, or a pre-write diff — the three things that make a wizard better than a form. The exemption is **narrow and named**: it applies to hex-init alone and to no skill that spawns workers. |
| **`memory.md:82-84`** — "Keep it small — pointers, not prose dumps. If a section wants to grow, move the content into a file… and point at it." A ~30-line block grows `Preferences`. | Tier A is the smallest carrier that expresses requirements 1–3, and it must be co-located with the prose that qualifies it. | This rule is **honoured, not deviated, for the largest item**: workflow DAGs — the one thing that would genuinely bloat the file — live in their own file behind a one-line pointer, which is exactly what the rule prescribes. The block itself is bounded by the frozen vocabulary; if it ever needs more than a screen, that is the signal hex grew a runtime. |

**Considered and *not* deviated**, to be explicit: the 3-tier grammar
(`DESIGN.md:330-331`, "hex-architect keeps the full 3-tier grammar, not
collapsed") is preserved — `tiers.<skill>.<tier>.inherits` redefines
tier *content*, never the tier *vocabulary*: `low|medium|high` + `auto`
stay the only values, classifiers still emit only those, `xhigh`/`max`
stay reserved, `inherits` may name only a shipped tier, and C-207's
mandatory disclosure means the label never travels without its deltas.
(Refusing `inherits` and allowing only `counts` was considered and
rejected: it forces a project to restate a whole tier's counts to say
"high here is medium" — more config for the same effect.) The
three-input spawn precedence (`DESIGN.md:114-133`) is preserved — `tiers` and `workflows`
rewrite layer 1 rather than adding a layer; the capability-class rule
(`DESIGN.md:216-217`, `adr_0001` C-001/C-002) is preserved — literal
model names appear only under `models.*` as user overrides, never in a
shipped file; the concurrency cap (`protocol.md:200-204`) is preserved
and strengthened; `hex-review`'s never-writes contract
(`hex-review/SKILL.md:3`) is preserved **in its never-commits half** by
workflow validation check 6 — its *only-writes-the-plan-artifact* half
is **not** preserved here but **amended by `adr_0005`**, which sanctions
the resolved fold target as one additional write in its new Fold-Back
phase (check 6's FORBIDDEN cell and C-221 reconcile with that);
worker definitions stay markdown prompt blocks (`DESIGN.md:332-334`).

## Migration / rollout plan

*(This section fills the MADR template's `## Implementation Plan` slot:
the waves below are the ordered implementation steps, framed as a
release-gated rollout because the key-name freeze at the first
`grim release` makes wave ordering load-bearing.)*

The repo is unreleased (`hex/` v0.1.0, no `grim release`). **Nothing
breaks**: absence of the block is the signal, absence of a workflow
pointer is the signal, and a project with neither runs byte-identically
to today. There is no version marker and no detection step — the same
discipline as `adr_0002` C-105.

**Wave 1 — semantics only (independently shippable, = Option A).**

| File | Change |
|---|---|
| `hex-core/references/protocol.md` | § Worker coordination gains `min(8, max-workers)` (C-201) **and the one sentence separating concurrency from panel size — "the cap bounds workers at once; a phase with more resolved workers batches, it does not drop perspectives" (C-216)**; § Review-Fix Loop gains the `loop-rounds` ceiling sentence (C-201). |

Ship this even if everything below is rejected.

**Wave 2 — Tier A, vocabulary v1. MUST land before the first `grim
release`** (the six v1 key names freeze there; see the one-way-door
flag). `workflows` is deliberately **not** in this wave and not in v1.

| File | Change |
|---|---|
| `hex-core/references/config.md` | **New.** Sole definition site for C-203/C-204/C-205/C-206, and later C-208/C-209. Every other file points at it, never restates it. |
| `hex-core/SKILL.md:21-28` | Add the `config.md` row to the references table, **marked conditional-load**: "read only when `hex.md › Preferences` contains a fenced `yaml` block." Unlike `protocol.md`/`workers.md`/`models.md`/`memory.md`, which every skill builds on, `config.md` is dead weight in an unconfigured project — it gets the same lazy-load carve-out `workers/<role>.md` personas already have ("load only what runs"). The trigger is cheap and already paid: `memory.md` is read every run, and the presence of the block is visible in it. |
| `hex-core/references/memory.md:33-38,:59-75,:79-113` | Preferences row points at `config.md`; the example file gains the block; the destination-of-knowledge rule keeps routing swarm-only facts here. |
| `hex-core/references/protocol.md:94-116` | § Spawn-selection precedence gains: `tiers`/`workflows` rewrite layer 1, not a fourth layer. § Tier grammar gains the one qualifying sentence for C-206. § The meta-plan approval gate gains C-207's disclosure requirement. |
| `hex-core/references/workers.md:65-75` | § Project-local personas gains the invocation-end pointer (C-205). |
| `hex-core/references/models.md:59-73` | Note that `models.overrides` is the layer-2 form of the resolution order already documented. |
| `hex-plan/SKILL.md`, `hex-execute/SKILL.md`, `hex-review/SKILL.md`, `hex-architect/SKILL.md` | Announce-block steps gain the new source tags and the drop/warning lines; worker-assignment tables gain a one-line pointer to `config.md` for count overrides. |
| `hex-plan/overlays.md`, `hex-execute/overlays.md`, `hex-review/overlays.md`, `hex-architect/overlays.md` | Precedence sections gain `tiers.*.overlays` as a per-project default below user flags. |
| `hex-review/classify.md:49-64` | The `hex.md › Preferences` path-hint row now points at the `perspectives` rules instead of describing prose fold-in. |
| `hex-review/tier-medium.md:55-71`, `hex-review/tier-high.md:62-90`, `hex-execute/tier-medium.md:87-92`, `hex-execute/tier-high.md:100-105` | The "fires when" prose gains "…or when a `perspectives.always` rule matches"; high-tier files gain the displacement rule pointer (merge rule 6). |
| `hex-init/SKILL.md:116-161` | New Step 4½ writes the block; Step 5 unchanged in shape. |
| `.agents/memory/hex.md:21-29` | This repo's own instance gains a block — the dogfood example. |
| `hex/README.md:39-56` | Qualify the public "one shared grammar" claim: the vocabulary is shared, the per-tier content is project-overridable and always announced. |
| `hex/DESIGN.md` | New dated round recording the four amendments and what they supersede. |

**Wave 3 — Tier B workflows and the wizard. Not release-blocking, and
therefore a vocabulary bump: this wave introduces `workflows` as
vocabulary v2** (C-223). The freeze and the wave order are consistent
only this way — a key cannot be advertised as frozen in Wave 2 while
its dispatch semantics ship in Wave 3. The bump is free because it
happens before the release that would freeze it.

| File | Change |
|---|---|
| `hex-core/references/config.md` | § Workflows: node schema, `Count` grammar, edge semantics, the seven validation checks — check 6's required-phase invariant reads the shipped tier file's own `## Phase N:` headings at validation time (C-220/C-221), not a static list restated here — with C-221's required duties, and the fork lifecycle (C-208/C-209/C-214/C-221). Key vocabulary section gains `workflows` and the v1→v2 note (C-223). |
| `hex-plan/SKILL.md:157-160`, `hex-execute/SKILL.md:178-181`, `hex-review/SKILL.md:174-177`, `hex-architect/SKILL.md:150-153` | Dispatch step reads the workflow pointer first, shipped tier file otherwise (C-210). |
| `hex-init/SKILL.md` | The wizard (C-212), non-interactive twin (C-213), `workflows` positional concern added to the list at `:200-204`, re-entrancy extended (C-215). |
| `hex-init/references/audit.md` | New audit items — block present and parseable, workflow forks resolve, fork stamps match the installed version — plus copy-ready blocks. |
| `hex/hex.toml:7-13`, `hex/publish.toml:16-33` | Register `config.md` if the manifests enumerate reference files (verify at implementation time; they enumerate skill paths today). |

**Rollback.** Wave 1 is unconditional. Wave 2 rolls back by deleting
`config.md` and the block; every consumer degrades to prose. Wave 3
rolls back by deleting the `workflows` key; every fork degrades to the
shipped tier file, which is already the failure path.

## Validation

This decision ships no code and no parser (`DESIGN.md:63-65`), so its
verification surface is markdown-shaped and mostly in-band:

- [ ] `grim build` passes on every changed skill dir and on the new
      `config.md` reference file, and on any forked workflow file a
      consumer or the dogfood `hex.md` adds — the packer's validation is
      the only mechanical gate hex has.
- [ ] The **S-2xx scenarios** (S-201 … S-218) act as the acceptance
      cases: each is a concrete run whose announced outcome must match
      the scenario text. S-201 (unconfigured = byte-identical to today),
      S-213/S-214 (cap-batching and the merge-rule-6 procedure), and
      S-204/S-215 (fail-closed security suppression) are load-bearing.
- [ ] The **announce block is the runtime validation surface** — a rule
      that did not print did not fire (C-207) — and the pre-print
      self-check re-verifying merge rules 4–7 is the check on the check.
      Its stated weakness (self-reported, not independent — Consequences)
      is the accepted residual, not a gap this ADR closes.
- [ ] The **seven workflow-validation checks** (C-209) are themselves the
      validation of a fork: a fork failing any check degrades to the
      shipped tier file loudly, never runs half-applied, and — per the
      C-221 reframe — its required-phase check is re-derived from the
      shipped headings at read time, so it cannot certify against a stale
      copied list.
- [ ] A source sweep confirms the single-source-of-truth invariants: **no
      phase-index file ships** (C-220), `config.md` is the sole
      definition site every other file only points at
      (C-203/C-204/C-205/C-206/C-208/C-209), and literal model names
      appear only under `models.*` (`adr_0001` C-002).

## Open Questions

1. **[NEEDS CLARIFICATION: does `tiers` reach classifier thresholds
   (research D-4, "classify anything touching `migrations/` as high")?]**
   *Recommended:* **no, not in v1** — thresholds are tier-file- and
   classify.md-coupled in three different shapes across the four skills
   (`hex-plan/classify.md:15-26` keyword table,
   `hex-review/classify.md:37-48` numeric diff metrics,
   `hex-architect/classify.md:15-42` decision-weight scoring), so one
   key cannot mean the same thing in all four. A `when:` glob on a
   perspective covers most motivating cases without letting a project
   redefine tiering itself. Revisit if `perspectives.when` demonstrably
   fails to cover them.

2. **[NEEDS CLARIFICATION: workflow file naming and location once more
   than one arcana bundle ships tier files.]** *Recommended:*
   `.agents/workflows/<skill>-<tier>.md` — flat, bundle-prefixed
   by the skill name (`hex-execute-medium.md`), matching the existing
   flat `.agents/workers/<role>.md` convention rather than
   inventing a nested per-bundle tree for a directory most projects
   will never create.

3. **[NEEDS CLARIFICATION: should a fork stamp record the shipped file's
   content hash rather than the hex version?]** *Recommended:* **hex
   version only** — a hash detects drift more precisely but requires a
   reader to compute one, which is exactly the parser hex does not have;
   a version string is comparable by reading two lines. Accept the
   false-positive drift reports (a hex release that did not touch that
   tier file still reports drift) as the cheaper failure.

## Deferred review findings

Raised by the review panel on this ADR, triaged as non-blocking, and
recorded here rather than fixed. Each is actionable as written; none
changes the decision. Source perspective in brackets.

1. **[reviewer:consistency] `Files touched` (22) disagrees with the
   Migration tables.** Extracting every File-column entry from Waves
   1–3 gives 23 unique files across Waves 1–2 and 26 across all three.
   *Fix:* recompute, and state explicitly whether the number means
   release-blocking waves only (23) or the full rollout (26). The
   per-file tables are the operative artifact and are complete, but the
   normative spec's self-certifying "It is complete" should not sit
   next to a wrong summary count. **Resolved in the cross-model
   revision** — the row now states 23 (Waves 1–2) / 26 (all waves).

2. **[reviewer:consistency] `~30 block lines` undercounts the ADR's own
   example.** The copy-pasteable Preferences block is 36 non-blank
   lines, 41 with blanks. *Fix:* recount against the shipped example in
   both the Quantified Impact row and the Cost NFR row, or state that
   the estimate excludes comments and blank lines. **Resolved in the
   cross-model revision** — both rows now read ~36 non-blank.

3. **[reviewer:spec] Merge rule 6 names no clamp algorithm.** "Clamp
   counts toward their shipped baselines" does not say which of several
   `counts` entries reduces first, by how much per step, or how ties
   break. *Fix:* state it — e.g. reduce the count furthest above its
   shipped baseline first, one unit at a time, re-checking the cap after
   each step. Only reachable when `counts` and the cap collide in one
   run, hence deferred, but an implementer would otherwise invent it
   silently. **Resolved in the cross-model revision** — merge rule 6
   now carries the four-step procedure, its one-unit granularity, its
   ASCII tie-break and its termination argument (C-216), and the
   underlying cap-vs-baseline impossibility is gone because the
   concurrency cap batches rather than displaces.

4. **[reviewer:spec] C-215 has no covering `S-2xx` scenario.** The
   idempotent-re-run contract (untouched keys keep values *and*
   comments; a deprecated key is reported, never deleted) is untested by
   the scenario table. *Fix:* add a scenario for a re-entrant
   `/hex-init` against an existing block that both preserves an
   untouched key's inline comment and reports a since-deprecated key in
   the summary.

5. **[reviewer:quality] `perspectives.always[].when:` globs may become a
   second copy of "which paths are sensitive".** `DESIGN.md`'s
   two-layer knowledge model assigns that fact to Layer 1 (project
   context), not to swarm-only Preferences. The rule object as a whole
   is correctly swarm-only — "which reviewer runs" genuinely is — but
   the glob's *value* may already be documented as a project arch rule
   elsewhere, and nothing checks the two for drift when a project later
   adds a sensitive directory without updating the glob. *Fix
   (non-blocking):* have `/hex-init`'s re-audit flag a
   `perspectives.always` glob naming no directory mentioned in the
   project's documented arch/security rules, the same way it already
   flags drifted Pointers entries.

6. **[reviewer:docs] The single-gate deviation's citation is one level
   off.** `DESIGN.md:13-21` / `protocol.md:45-49` are scoped to "all
   orchestrators", and `hex-core/SKILL.md` itself distinguishes "the
   orchestrator skills (/hex-plan, /hex-execute, /hex-review,
   /hex-architect) **and** /hex-init" — so the literal rule never bound
   hex-init. The text actually being changed is
   `hex-init/SKILL.md:76-77` ("Present every proposal in one batched
   approval — never one gap at a time, and never as a mid-flow
   interruption"). *Fix:* cite that line as the prior text, and frame
   `DESIGN.md`'s contribution as the nearest constitutional principle
   extended by practice rather than a rule that directly bound
   hex-init. The outcome and the exemption's reasoning are unaffected.
   **Resolved in the cross-model revision** — both the deviation row
   and the wizard section now cite `hex-init/SKILL.md:76-77` as the
   text being changed.

7. **[researcher:precedent] Microsoft Foundry Agent Service multi-agent
   Workflows is a newer, larger declarative phase→agent precedent than
   CrewAI.** Public-preview YAML workflows with kept-in-sync visual
   editing, if/else branching and human-in-the-loop approval steps,
   backed by the Microsoft Agent Framework runtime — which *reinforces*
   hex's no-parser premise (they had to build a runtime) while being a
   materially bigger example than CrewAI. Separately, Foundry is
   consolidating its split `agent.yaml`/`agent.manifest.yaml` into one
   `azure.yaml` — a caution about config fragmenting across many small
   files, directly relevant to Option D spreading config across `hex.md`
   plus per-skill-per-tier forked workflow files. *Fix (non-blocking):*
   add as a research citation alongside CrewAI, and note the
   fragmentation caution in Consequences if the workflow-file-per-fork
   design is ever revisited.

8. **[researcher:precedent] A live counter-position to the constitution's
   no-parser premise exists in the 2026 literature.** "A Deterministic
   Control Plane for LLM Coding Agents" (arXiv:2606.26924) argues that
   LLM-interpreted declarative workflow configuration for coding agents
   — hex's exact model, and the exact target of C-209's "a reader, not a
   parser" — produces inconsistent execution, coordination failures and
   insufficient audit trails, and advocates enforced state machines
   instead. Not blocking this ADR: the premise belongs to `DESIGN.md`,
   not `adr_0003`. *Fix:* a one-line acknowledgment that the
   counter-position exists, for whoever next revisits `DESIGN.md`'s
   markdown-only premise.

9. **[researcher:precedent] The `when:` glob mechanism is
   well-precedented, not novel** — GitLab Duo `fileFilters`, GitHub
   Actions `paths:`. **Addressed in this revision** (Industry Context
   bullet and merge rule 5's rationale); recorded here because the
   companion suggestion — auditing the other three surveyed frameworks
   for equally close analogs the teardown missed — is still open.

10. **[researcher:precedent] C-215's report-only deprecation policy
    diverges from its nearest cousins without saying why.** OpenCode
    auto-migrates deprecated `theme`/`keybinds`/`tui` keys; fast-agent
    auto-ignores legacy `thinking_enabled`/`thinking_budget_tokens`.
    Both are closer architectural cousins than OpenSpec, since both have
    config a coding-agent runtime consumes. hex genuinely lacks the code
    layer they use to safely auto-rewrite a user-owned block, so
    report-only is likely still right. *Fix:* one sentence in C-215 —
    "unlike OpenCode/fast-agent, hex has no code layer that can safely
    auto-rewrite the user-owned block, so deprecated keys are reported,
    never migrated."

11. **[cross-model review (codex)] `models.overrides` and
    `perspectives.never` encode role and focus as colon-delimited
    strings.** Adequate for v1 and consistent with `workers.md`'s own
    `role[:focus]` notation, but brittle as a *frozen* shape: if
    suppression later needs a path, phase or condition scope — the
    subtractive twin of `always`'s rule object — the string form has
    nowhere to put it and the key is already frozen. *Fix (non-blocking):*
    if it ever comes up, add a long form (`never: [{role: …, when: …}]`)
    alongside the string form rather than renaming the key; a list
    accepting both a string and an object is the cheapest widening that
    does not break an instantiated `hex.md`. Note that C-218's
    attestation deliberately went to a *sibling key* rather than a
    per-entry field for exactly this reason.

12. **[cross-model review (codex)] Workflow filename and location stay
    open for multiple bundles.** Open Question 2's recommendation
    (`.agents/workflows/<skill>-<tier>.md`, flat) is unambiguous
    only while hex is the sole bundle shipping tier files. *Fix:*
    resolve before a second arcana bundle ships tier files, not before
    this ADR is accepted — Wave 3 is the natural forcing point.

13. **[cross-model review (codex)] Version-only fork stamps produce
    false-positive drift.** Open Question 3's recommendation accepts
    that any hex release reports drift on every fork, including forks
    of tier files the release did not touch. Accepted for v1: the
    alternative needs a hash a reader cannot compute. *Fix:* revisit if
    the noise makes the re-audit's drift report ignorable, which is the
    failure mode that would matter.

14. **[cross-model review (codex)] C-215 does not define duplicate-key,
    ordering, quoting or comment-preservation behaviour on re-entry.**
    "Untouched keys keep their values *and* their comments" states the
    goal, not the rewrite rule: it does not say whether key order is
    preserved, which quoting style a rewritten scalar takes, or what
    happens when the user's hand-edited block already contains the
    duplicate spelling C-222 now tolerates on read. *Fix:* specify when
    `/hex-init` is implemented (Wave 3) — the read path is fully
    specified by C-222 and merge rule 9, so nothing is ambiguous for an
    orchestrator; this is a wizard-authoring gap only.

15. **[cross-model review (codex)] `perspectives.always[].when` globs
    can become a second copy of project security-path knowledge with no
    drift audit.** Distinct from deferred finding 5 in emphasis: 5 asks
    for a re-audit check, this one names the underlying duplication —
    the same fact ("these paths are sensitive") now lives in
    `classify.md`'s generic markers, the project's documented arch
    rules, and the glob, with nothing reconciling the three. Real, and
    not acceptance-blocking, because the fail-closed direction of C-218
    means a stale glob under-suppresses rather than under-protects.
    *Fix:* the re-audit check proposed in finding 5 covers it.

### Triaged, no change (cross-model review, codex)

Recorded so the next reader does not re-raise them:

- **The no-parser / no-runtime premise is a constitutional choice, not
  a defect of this ADR.** It belongs to `DESIGN.md:63-65`; deferred
  finding 8 already records the live counter-position
  (arXiv:2606.26924) for whoever revisits it. Everything in this ADR
  that reads as weak enforcement is downstream of that choice, and the
  Security NFR and Consequences both now say so in plain terms.
- **The `/hex-init` single-gate exemption is settled**, and its only
  defect was the citation, now corrected to `hex-init/SKILL.md:76-77`
  (deferred finding 6). The exemption's scope — hex-init alone, never a
  skill that spawns workers — is unchanged.
- **Merge rules 1–4 and 7–10 carry ordinary LLM-adherence risk, not
  contract ambiguity.** They are unambiguous as written; the risk that
  a reader forgets one is the design's stated weakest link
  (Consequences, announce-block bullet) and is mitigated by the
  pre-print self-check, not by more prose per rule.

## Links

- [`swarm-customization-and-config.md`](../research/swarm-customization-and-config.md)
  — primary research: spawn baseline, cannot-express list, GSD/Spec
  Kitty/OpenSpec teardowns, executed interactive transcripts.
- [`openspec-framework-analysis.md`](../research/openspec-framework-analysis.md)
  — OpenSpec anatomy and the adopt/adapt/reject table.
- [`hierarchical-execution-performance.md`](../research/hierarchical-execution-performance.md)
  — reviewer plateau and error-amplification figures behind the
  requirement-2 consequence.
- [`adr_0001_model_matrix_capability_classes.md`](adr_0001_model_matrix_capability_classes.md)
  — capability classes (C-001/C-002) and the identical name-freeze
  one-way door.
- [`adr_0002_execution_scheduling_recursion.md`](adr_0002_execution_scheduling_recursion.md)
  — the WP-level DAG this design's phase DAG must stay orthogonal to;
  C-105's extend-by-key-convention discipline.
- [`hex/DESIGN.md`](../../../hex/DESIGN.md) — the constitution amended
  by this decision.

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-07-20 | hex-architect (architect worker) | Initial draft — Proposed |
| 2026-07-20 | hex-review (fix pass) | Applied actionable review findings: `workflows` given a merge rule and a missing-path failure mode; merge rule 5 hardened to refuse a security suppression that collides with a matched security path (GitLab Duo `fileFilters` precedent cited); announce block gains `Adversary`/`Research axes` lines and a mandatory pre-print self-check; one-way-door section now freezes key names, rule-object fields and merge-rule semantics layer by layer; `config.md` made conditional-load; S-204b, S-211, S-212 added; the self-retracting `DESIGN.md:330-331` deviation row moved to "considered and not deviated" (four amendments → three). Deferred findings recorded in a new section. Status unchanged. |
| 2026-07-20 | hex-architect (cross-model adversary pass) | One-shot cross-model (codex) adversary pass, triaged 12 actionable / 5 deferred / 3 stated-convention / 2 trivia. **Three reopened decisions settled:** (1) the concurrency cap is a *batch size*, not a panel size — a reduced `max-workers` batches a phase instead of dropping perspectives, which removes the cap-vs-baseline impossibility entirely; displacement moves to a per-phase ceiling `max(baseline, min(8, max-workers))` acting only on preference-added spawns, with a four-step terminating reduction procedure (C-216). (2) `never: [reviewer:security]` is now fail-closed behind a required `perspectives.security-sensitive-paths: none` attestation, and the Security NFR states plainly that enforcement is self-reported and not a compliance control (C-218). (3) `workflows` leaves the frozen v1 vocabulary and becomes vocabulary v2 in Wave 3, so the freeze and the wave order agree (C-223). **Newly specified:** glob syntax and per-skill target file sets (C-217); `tiers` resolution order, inherits → counts → overlays, non-transitive (C-219); phase identifiers derived from `## Phase N:` headings with no shipped index, and the fork-invalidated-phase result (C-220); workflow `Count` grammar and the required-phase/duty index behind validation check 6 (C-221); dotted-key alias collisions (C-222). Option A marked infeasible against the settled requirement set rather than co-optimal with D; fold-in as work item 1 unchanged. S-213–S-218 added; file count corrected to 23/26 and the block estimate to ~36 non-blank lines. Deferred findings 11–15 and a triaged-no-change list appended. Status unchanged. |
| 2026-07-20 | hex-execute (fix pass) | Applied agreed cross-ADR review findings. **B2:** declared the `DESIGN.md:218-219` ("tier methodology unchanged") deviation as a new Constitution-deviations row — `tiers`/`workflows` rewrite layer 1; C-207's mandatory disclosure retires the reason the rule exists (one methodology per label) by making every divergence visible at every gate; residual priced honestly (a `Workflow:` line is a pointer, not an enumerated diff); deviation counts bumped 3→4. **B4:** added `Fold-Back` to the `hex-review` required-identifier set in both the validation table and C-221, guarded "(required when adr_0005 is accepted)", reconciling with adr_0005. **H2:** rewrote the check-6 hex-review FORBIDDEN cell to permit the adr_0005 fold-target write, and qualified the "considered and not deviated" never-writes claim (never-commits half preserved; only-writes-the-plan-artifact half amended by adr_0005). **H4:** added a forward-compatible sentence to C-217 — under an adr_0004 `Repo` column, `when:` globs evaluate against lead-repo paths only. **H5:** reframed C-221/C-209 and the config.md migration entry so validation check 6's required-phase invariant is derived at read time from the shipped tier files' `## Phase N:` headings (per C-220), not a static list copied into `config.md`. **Structural:** added a `## Validation` section and noted `## Migration / rollout plan` fills the template's Implementation-Plan slot. Status unchanged (Proposed). |
