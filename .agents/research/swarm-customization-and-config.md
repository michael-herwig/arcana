# Research: swarm customization and config carriers

**Axis:** configuration / customization surface (user request, multi-axis)
**Date:** 2026-07-20
**Domain:** cli / packaging
**Triggered by:** user request — align hex with openspec.dev; YAML config,
deep customization, multi-repo
**Expires:** 2027-01-31
**Decision it informs:** whether `hex.md › Preferences` gains a fixed key
vocabulary (and in what carrier), and what `/hex-init` elicits.
**Produced by:** hex swarm, 16-axis dossier + adversarial verification
pass + a gap-fill pass that **executed** the OpenSpec CLI under a pty and
opened the two previously-unread competitors. Sources: OpenSpec clone
@ v1.6.0 (`@fission-ai/openspec`), spec-kitty clone, get-shit-done clone,
hex bundle @ 3745eac.

## Direct answer

Go partway, and keep one file. hex's real defect today is not "no YAML" —
it is that `hex.md › Preferences` names knobs (`max-workers`,
`loop rounds`, `artifact loop rounds`, always-on perspectives) with **no
defined key vocabulary and no written enforcement semantics**: nothing in
`protocol.md` says how a stored `max-workers 6` interacts with the
hardcoded "at most 8 workers" cap (protocol.md:200), and nothing says
whether the stored `loop rounds` is a ceiling on `--loop-rounds`, a
default, or advice. A schema does not fix that; writing the resolution
rule does. Adopt a **frozen ~5-key vocabulary rendered as one fenced
YAML block inside `hex.md › Preferences`** — a hybrid, not a second file,
not frontmatter, no JSON Schema, no `$schema` modeline. Publish no
schema: hex has no code layer to derive one from, so a hand-written
schema would itself be the second source of truth DESIGN.md:63 rejects.
Cut tier redefinition, per-phase panel composition, and same-role
reviewer counts — the last is contradicted by hex's own performance
research (reviewers plateau ~5 same-kind; grow role diversity, not
count — `hierarchical-execution-performance.md:72-92`).

OpenSpec is a weak precedent for the config *carrier* question (its YAML
is parsed by zod in TypeScript; hex ships markdown and the client is the
runtime) but a strong precedent for three other things hex should copy: a
documented **4-step resolution precedence** stated identically in code
and docs, **resilient parse-with-warnings** so one bad field never
kills the config, and — the one this dossier initially under-read — the
mechanics of its own **interactive `openspec config profile` flow**, which
is a shipping analog of "ask the user which workflows they want": a
scope-selector question zero with an explicit no-op exit, `[current]`
labelling on top of defaults, a pre-checked multi-select whose *label* is
derived rather than asked, a printed diff before the write, and a separate
consent for applying the change (see
[Interactive init design](#interactive-init-design)).

The spawn baseline the whole question rests on is now extracted
mechanically rather than sampled — see
[Spawn baseline](#spawn-baseline--the-mechanical-extraction). Two things
it changes: hex-review's high tier is already *at* the concurrency cap
(2 + 6 = 8), so `perspectives.always` needs a stated displacement rule
rather than being purely additive; and two perspectives
(`reviewer:performance`, `reviewer:user-feedback`) never run in
hex-architect at any tier, which is the clearest thing `always` buys.

## Where hex customization stands today

### A. Ephemeral, per-invocation (CLI flags)

Exhaustive, per skill (flags precede the target; user flags beat
classifier overlays beat Preferences hints beat tier baseline):

| Skill | Flags |
|---|---|
| hex-plan | `--architect=inline\|on`, `--research=skip\|1\|3`, `--adversary/--no-adversary`, `--dry-run` (SKILL.md:45-53; overlays.md:16-20) |
| hex-execute | `--review=minimal\|full\|adversarial`, `--loop-rounds=1\|2\|3`, `--adversary/--no-adversary`, `--dry-run` (SKILL.md:47-53; overlays.md:17-20) |
| hex-review | `--base=<git-ref>` (pipeline input, not an axis), `--breadth=minimal\|full\|adversarial`, `--rca=on\|off`, `--adversary/--no-adversary`, `--dry-run` (SKILL.md:32-66; overlays.md:25-28) |
| hex-architect | `--research=skip\|1\|3`, `--axes=<csv>`, `--adversary/--no-adversary`, `--artifact=inline\|adr\|system-design`, `--dry-run` (SKILL.md:44-53; overlays.md:15-19) |
| hex-init | positional concern: `verification\|conventions\|worktrees\|models\|templates` (SKILL.md:200-204) |

Tier itself (`low|medium|high`, default `auto`; `xhigh`/`max` reserved →
run high with an announcement) is the universal overlay
(protocol.md:18-34). `hex-review` is the only skill that explicitly
forbids a literal-model flag (overlays.md:30-32).

### B. Persistent (`hex.md › Preferences`, written only by `/hex-init`)

Documented fields, all free prose bullets, no key schema
(memory.md:36, example at :59-66): instantiated model matrix +
per-row/per-cell overrides; cross-model adversary skill name; limits
(`max-workers`, `loop rounds`, and the separately-named
`artifact loop rounds: N`, protocol.md:156-159); always-on perspectives;
path-triggered escalations; research axes of interest. Orchestrators
read it and **never** write it — a preference a run surfaces is parked in
`hex.md › Memory` and only proposed at the next `/hex-init`
(protocol.md:504-516). Live arcana file uses three of the six
(`.agents/memory/hex.md:22-30`).

### C. Persistent, non-Preferences

- `hex.md › Pointers` — skill-managed location cache (verification doc,
  plan/ADR conventions, product doc, key rules, worktree-location
  deviation, constitution). Not a knob, but the *verification command*
  and *constitution gate* are effectively user-controlled through it,
  and the constitution gate is opt-in by pointer presence
  (protocol.md:432-448).
- `.agents/workers/*.md` — project-local personas. A user can add
  an entirely new role; it folds in as a layer-2 project hint, resolves
  to `fast-balanced` unless the file names a class, and never overrides a
  shipped role of the same name (workers.md:65-74). **This is hex's
  deepest existing customization surface and it is undocumented at the
  invocation end** — nothing says how a new persona gets into a tier's
  Stage-2 launch list.
- Plan-artifact knobs set at plan time, not by config: the WP table's
  `Review` column (`self|light|panel`, budget only lowers breadth, never
  raises; missing = `panel`, protocol.md:162-178) and the `Scope`/
  `Depends-on` cells.
- Meta-plan gate — one-shot, interactive: add/drop perspectives, pick
  research axes, adjust breadth (hex-review/SKILL.md:134-137).

### D. What a user cannot express today

1. **"Always run two security reviewers under `src/auth/**`."** Counts of
   the same role are not expressible anywhere — `--breadth` is a 3-value
   enum, not a count, and `--research` accepts only `skip|1|3`. (Also:
   should stay inexpressible — see Finding 6.)
2. **"Skip the doc reviewer in this repo."** Preferences has *always-on*
   perspectives but no *never* list; the only subtractive lever is
   lowering `--breadth` wholesale, which drops security and performance
   with it.
3. **"My medium tier means 3 researchers, not 1."** Tier→count mappings
   live in tier files as prose; no override field exists in the
   Preferences schema (memory.md:36).
4. **"Classify anything touching `migrations/` as high."** Tier-boundary
   thresholds are hardcoded in each `classify.md` (hex-review
   classify.md:37-47; hex-architect classify.md:31-42) with no override
   field — editing the shipped skill is the only path.
5. **"Use my custom `reviewer:accessibility` perspective in Stage 2."**
   The persona file mechanism exists (C above); the wiring does not.
6. **"Run hex-execute with `--review=full` by default here."** No
   per-project defaults for overlay axes; every non-default axis is
   either typed every run or must graduate into a Preferences prose hint.
7. **Verdict-rule severities** (what forces Request Changes vs Needs
   Work) — hardcoded per tier file, no field anywhere.
8. **Enforcement semantics of the two limits that *do* exist** —
   `max-workers` vs the hardcoded cap of 8, and `loop rounds` vs each
   skill's own `--loop-rounds` default, are unwired in every file in the
   bundle. This is the highest-value gap on the list.

## Spawn baseline — the mechanical extraction

The first-order question ("how many and which subagents per workflow, and
which of those numbers could a config file plausibly move") is answered
here rather than left implicit. Everything below is read off the shipped
files at 3745eac — `*/tier-{low,medium,high}.md`, `*/SKILL.md`,
`*/overlays.md`, `hex-core/references/{protocol,models,workers/*}.md` —
with no inference beyond what the text states.

Three reading rules for Table 1:

- Counts are worker **spawns**, not distinct roles.
- `×N` means "once per work package", where N is the plan's WP count —
  itself decided by the plan/classifier, never by the tier file. A 5-WP
  plan multiplies every hex-execute medium/high row by 5, which makes WP
  count the dominant driver of total spawn volume in that orchestrator,
  ahead of tier choice.
- `0–1` splits into two distinct mechanisms: **classifier-decided** (a
  signal fires — security path, hot path, doc-drift trigger) and
  **orchestrator-judgment-decided** (the coordinator gate, "skip the
  researcher if the diff clearly doesn't need it"). Only the first is a
  candidate for a `when:` glob.

### Table 1 — orchestrator × tier × phase

| Orchestrator | Tier | Phase | Role (focus) | Count | Type | Model class | Source |
|---|---|---|---|---|---|---|---|
| hex-plan | low | Discover | explorer | 1 | fixed | fast-balanced | tier-low.md:16; models.md:28 |
| hex-plan | low | Research | researcher | 0 | fixed (skip) | — | tier-low.md:29-31 |
| hex-plan | low | Design | architect | 0 | fixed (inline) | — | tier-low.md:47 |
| hex-plan | low | Review | reviewer:spec (post-stub) | 1 | fixed | fast-balanced | tier-low.md:73; models.md:37 |
| hex-plan | medium | Discover | architecture-explorer | 1 | fixed | fast-balanced | tier-medium.md:19; models.md:29 |
| hex-plan | medium | Discover | explorer | 2–4 | ranged (1 per area) | fast-balanced | tier-medium.md:20-23 |
| hex-plan | medium | Research | researcher | 1 (3 via `--research=3`) | fixed baseline / flag-ranged | fast-balanced | tier-medium.md:41,49 |
| hex-plan | medium | Design | architect | 0–1 | classifier (one-way-door / cross-area) | deep-reasoning | tier-medium.md:74-77; models.md:40 |
| hex-plan | medium | Review R1 | reviewer:spec (post-stub) | 1 | fixed | fast-balanced | SKILL.md:178; tier-medium.md:137 |
| hex-plan | medium | Review R1 | architect | 0–1 | classifier (required for one-way-door) | deep-reasoning | tier-medium.md:146 |
| hex-plan | medium | Review R1 | researcher | 0–1 | classifier | fast-balanced | tier-medium.md:148 |
| hex-plan | medium | Adversary | adversary skill | 0–1 | classifier (auto-on one-way-door) / flag | n/a | overlays.md:74-76; tier-medium.md:155-160 |
| hex-plan | high | Discover | architecture-explorer | 1 | fixed | fast-balanced | tier-high.md:23 |
| hex-plan | high | Discover | explorer | 2–4 | ranged | fast-balanced | tier-high.md:25 |
| hex-plan | high | Research | researcher | 3 | fixed (mandatory) | fast-balanced | tier-high.md:37 |
| hex-plan | high | Design | architect | 1 | fixed (mandatory) | deep-reasoning | tier-high.md:74 |
| hex-plan | high | Review R1 | reviewer:spec (post-stub) | 1 | fixed (mandatory) | deep-reasoning | tier-high.md:131-135 |
| hex-plan | high | Review R1 | architect | 0–1 | classifier (high expects it) | deep-reasoning | tier-high.md:140-141 |
| hex-plan | high | Review R1 | researcher | 0–1 | classifier | fast-balanced | tier-high.md:142-143 |
| hex-plan | high | Adversary | adversary skill | 1 | default-on, graceful skip | n/a | tier-high.md:149-157 |
| hex-execute | low | Stub | builder:stub | 1 | fixed | fast-balanced | tier-low.md:31; models.md:31 |
| hex-execute | low | Verify-Architecture | reviewer:spec | 0 | fixed (skipped) | — | tier-low.md:36-40 |
| hex-execute | low | Specify | tester | 1 | fixed | fast-balanced | tier-low.md:47; models.md:33 |
| hex-execute | low | Implement | builder:implement | 1 | fixed | fast-balanced | tier-low.md:59; models.md:32 |
| hex-execute | low | Review-Fix R1 | reviewer:quality + reviewer:spec | 1 + 1 | fixed, capped 1 round | fast-balanced | tier-low.md:68-73 |
| hex-execute | low | Cross-model | adversary skill | 0 (unless `--adversary`) | fixed-off | n/a | tier-low.md:78-82 |
| hex-execute | low | (any) | coordinator | 0 | never spawned at low | — | models.md:41 |
| hex-execute | medium | Stub | builder:stub | 1×N | ranged (= WP count) | fast-balanced | tier-medium.md:39 |
| hex-execute | medium | Verify-Architecture | reviewer:spec (post-stub) | 0–1×N | classifier/budget (optional ≤3-file plan; `self` skips) | fast-balanced | tier-medium.md:48-52 |
| hex-execute | medium | Specify | tester | 1×N | ranged | fast-balanced | tier-medium.md:58 |
| hex-execute | medium | Implement | builder:implement | 1×N | ranged | fast-balanced | tier-medium.md:71 |
| hex-execute | medium | Implement | coordinator | 0–1 per qualifying WP | orchestrator judgment (≥3 sub-tasks) | deep-reasoning | SKILL.md:201; coordinator.md:11-17 |
| hex-execute | medium | Review-Fix R1 | reviewer:quality, reviewer:spec | 1×N each | ranged, budget-lowered per WP | fast-balanced | tier-medium.md:87-88 |
| hex-execute | medium | Review-Fix R1 | reviewer:security | 0–1×N | classifier (security path) | deep-reasoning | tier-medium.md:89-90 |
| hex-execute | medium | Review-Fix R1 | reviewer:performance | 0–1×N | classifier (hot path/async) | fast-balanced | tier-medium.md:90-91 |
| hex-execute | medium | Review-Fix R1 | doc-reviewer | 0–1×N | classifier (doc-drift) | fast-balanced | tier-medium.md:91-92 |
| hex-execute | medium | Cross-model | adversary skill | 0–1 | classifier / flag | n/a | tier-medium.md:94-99 |
| hex-execute | high | Stub | builder:stub | 1×N | ranged | fast-balanced (escalatable) | tier-high.md:44-47 |
| hex-execute | high | Verify-Architecture | reviewer:spec + architect | 1×N each | fixed per WP (unless `self`) | deep-reasoning | tier-high.md:53-61 |
| hex-execute | high | Specify | tester | 1×N | ranged | deep-reasoning | tier-high.md:70-73 |
| hex-execute | high | Implement | builder:implement | 1×N | ranged | deep-reasoning | tier-high.md:84-86 |
| hex-execute | high | Implement | coordinator | 0–1 per qualifying WP | orchestrator judgment | deep-reasoning | SKILL.md:201; coordinator.md:11-17 |
| hex-execute | high | Review-Fix R1 | reviewer:quality, reviewer:spec | 1×N each | ranged, mandatory | deep-reasoning | tier-high.md:100-101 |
| hex-execute | high | Review-Fix R1 | reviewer:security | 0–1×N | classifier | deep-reasoning | tier-high.md:101-102 |
| hex-execute | high | Review-Fix R1 | reviewer:performance | 0–1×N | classifier | deep-reasoning | tier-high.md:102-103 |
| hex-execute | high | Review-Fix R1 | doc-reviewer | 0–1×N | classifier | fast-balanced | tier-high.md:103 |
| hex-execute | high | Review-Fix R1 | architect | 1×N | fixed (`review=adversarial`) | deep-reasoning | tier-high.md:104; overlays.md:31 |
| hex-execute | high | Review-Fix R1 | researcher | 1×N | fixed (`review=adversarial`) | fast-balanced | tier-high.md:104-105; overlays.md:31 |
| hex-execute | high | Cross-model | adversary skill | 1 | default-on, graceful skip | n/a | tier-high.md:111-120 |
| hex-review | low | Discover | (inline, no worker) | 0 | fixed | — | tier-low.md:16-18 |
| hex-review | low | Stage 1 | reviewer:spec (post-impl) | 1 | fixed | fast-balanced | tier-low.md:33 |
| hex-review | low | Stage 2 | (skipped) | 0 | fixed | — | tier-low.md:53-57 |
| hex-review | low | Cross-model | adversary skill | 0 (unless `--adversary`) | fixed-off | n/a | tier-low.md:69-72 |
| hex-review | medium | Discover | (inline, no worker) | 0 | fixed | — | tier-medium.md:17-19 |
| hex-review | medium | Stage 1 | reviewer:spec + reviewer:quality (test-coverage) | 1 + 1 | fixed | fast-balanced | tier-medium.md:32-42 |
| hex-review | medium | Stage 2 | reviewer:quality | 1 | fixed | fast-balanced | tier-medium.md:61 |
| hex-review | medium | Stage 2 | reviewer:security | 0–1 | classifier (security path) | deep-reasoning | tier-medium.md:63-65 |
| hex-review | medium | Stage 2 | reviewer:performance | 0–1 | classifier | fast-balanced | tier-medium.md:66-67 |
| hex-review | medium | Stage 2 | reviewer:user-feedback | 0–1 | classifier (user-facing surface) | fast-balanced | tier-medium.md:68-70 |
| hex-review | medium | Stage 2 | doc-reviewer | 0–1 | classifier (doc trigger) | fast-balanced | tier-medium.md:72-75 |
| hex-review | medium | (cap) | Stage 1 + Stage 2 | ≤6 | ranged ceiling | — | tier-medium.md:80-81 |
| hex-review | medium | Cross-model | adversary skill | 0–1 | classifier / flag | n/a | tier-medium.md:106-111 |
| hex-review | high | Discover | (inline, no worker) | 0 | fixed | — | tier-high.md:21-26 |
| hex-review | high | Stage 1 | reviewer:spec + reviewer:quality (test-coverage) | 1 + 1 | fixed | deep-reasoning | tier-high.md:36-51 |
| hex-review | high | Stage 2 | reviewer:quality **or** user-feedback | 1 | fixed count, focus swaps on trigger | deep-reasoning | tier-high.md:66-69 |
| hex-review | high | Stage 2 | reviewer:security | 1 | fixed ("always at high") | deep-reasoning | tier-high.md:70-71 |
| hex-review | high | Stage 2 | reviewer:performance | 1 | fixed ("always at high") | deep-reasoning | tier-high.md:72 |
| hex-review | high | Stage 2 | doc-reviewer | 1 | fixed ("always at high") | fast-balanced | tier-high.md:73-74 |
| hex-review | high | Stage 2 | architect | 1 | fixed | deep-reasoning | tier-high.md:75-76 |
| hex-review | high | Stage 2 | researcher | 0–1 | orchestrator judgment (skip → 7) | fast-balanced | tier-high.md:77-85 |
| hex-review | high | (cap) | Stage 1 (2) + Stage 2 (6) | 8 | at the global ceiling | — | tier-high.md:83 |
| hex-review | high | Cross-model | adversary skill | 1 | default-on, graceful skip | n/a | tier-high.md:111-120 |
| hex-architect | low | Discover | explorer | 1 | fixed | fast-balanced | tier-low.md:18 |
| hex-architect | low | Research | researcher | 0 | fixed (skip) | — | tier-low.md:29-31 |
| hex-architect | low | Design | architect | 0 (inline) | fixed | — | tier-low.md:49-51 |
| hex-architect | low | Review | reviewer:quality | 1 | fixed | fast-balanced | tier-low.md:66 |
| hex-architect | medium | Discover | architecture-explorer | 1 | fixed | fast-balanced | tier-medium.md:18 |
| hex-architect | medium | Research | researcher | 1 (3 via `--research=3`) | fixed baseline / flag-ranged, axis picked at gate | fast-balanced | tier-medium.md:33-44 |
| hex-architect | medium | Design | architect | 1 | fixed (mandatory) | deep-reasoning | tier-medium.md:67-68 |
| hex-architect | medium | Review R1 | reviewer:spec | 1 | fixed | fast-balanced | tier-medium.md:99 |
| hex-architect | medium | Review R1 | reviewer:quality (adversarial framing) | 1 | fixed | fast-balanced | tier-medium.md:101-104 |
| hex-architect | medium | Review R1 | reviewer:security | 0–1 | classifier (compliance signal / hex.md pref) | deep-reasoning | tier-medium.md:105-107 |
| hex-architect | medium | Cross-model | adversary skill | 0–1 | classifier / flag | n/a | tier-medium.md:112-117 |
| hex-architect | high | Discover | architecture-explorer | 1 | fixed | fast-balanced | tier-high.md:24 |
| hex-architect | high | Research | researcher | 3 | fixed (mandatory, user-selected axes) | fast-balanced | tier-high.md:34-47 |
| hex-architect | high | Design | architect | 1 | fixed (mandatory) | deep-reasoning | tier-high.md:72-73 |
| hex-architect | high | Review R1 | reviewer:spec | 1 | fixed | deep-reasoning | tier-high.md:98-99 |
| hex-architect | high | Review R1 | reviewer:quality (adversarial framing) | 1 | fixed | deep-reasoning | tier-high.md:100-102 |
| hex-architect | high | Review R1 | researcher | 1 | fixed | fast-balanced | tier-high.md:103-104 |
| hex-architect | high | Review R1 | reviewer:security | 0–1 | classifier (mandatory if triggered) | deep-reasoning | tier-high.md:105-107 |
| hex-architect | high | Cross-model | adversary skill | 1 | default-on, graceful skip | n/a | tier-high.md:109-118 |

### Table 2 — reviewer perspectives across the bundle

| Perspective | Defined | hex-plan | hex-execute | hex-review | hex-architect | Add/remove today |
|---|---|---|---|---|---|---|
| `reviewer:spec` | workers/reviewer.md:15-16,18-20 | all tiers, always | all tiers, always (Verify-Arch + Review-Fix) | Stage 1, all tiers; also runs the convergence check | medium, high; absent at low | Mandatory wherever it appears — no flag removes it; phase is orchestrator-set |
| `reviewer:quality` | workers/reviewer.md:11 | **never spawned** | all tiers — core of `minimal`/`full`/`adversarial` (overlays.md:29-31) | Stage 2, all tiers | low (sole reviewer), medium, high | `--review=` / `--breadth=`; hex-plan and hex-architect have only the gate |
| `reviewer:security` | workers/reviewer.md:12-13 | never | medium/high, classifier | medium classifier; **high fixed 1** (tier-high.md:70-71) | medium/high, classifier ("mandatory when signal fires" at high) | Auto-fires on auth/crypto/signing/token/secret paths; `hex.md › Preferences` path hints can force it on |
| `reviewer:performance` | workers/reviewer.md:14 | never | medium/high, classifier | medium classifier; high fixed 1 | **never** | Hot-path/async signal; no removal flag, only a breadth downgrade |
| `reviewer:user-feedback` | workers/reviewer.md:17,21-25 | never | **never** | medium classifier; at high substitutes for `quality` on a user-facing surface | **never** | CLI/API/UX diff trigger; grounded by `hex.md › Pointers` |
| `doc-reviewer` | workers/doc-reviewer.md | never | medium/high, classifier | medium classifier; high fixed 1 | never | Doc-trigger matrix (CLI/flags, config/env, schema, install docs, changelog) |
| `architect` as reviewer | workers/architect.md | medium/high, 0–1 classifier | high only, fixed 1 under `review=adversarial` | high only, fixed 1 | **never** — hex-architect does not re-spawn an architect to review its own ADR | Classifier signal or tier mandate; droppable at the gate |
| `researcher` as reviewer | workers/researcher.md | medium/high, 0–1 classifier | high only, fixed 1 under `review=adversarial` | high only, 0–1 judgment-skippable | high only, fixed 1 | As above |
| Root-cause (Five Whys) | hex-review/overlays.md:53-63 — an analysis *mode*, not a persona | n/a | n/a | low off; medium ≥High findings; high everything above Suggest | n/a | `--rca=on\|off`, hex-review only |
| Cross-model adversary | protocol.md:450-469 | low off / medium auto / high default-on | same | same | same | `--adversary`/`--no-adversary`; skill name from `hex.md › Preferences`, never hardcoded |

**Nothing in the bundle runs the same perspective twice in one pass by user
request.** The only repetition is structural: hex-execute spawns one
instance of each Review-Fix perspective *per work package*, and a
coordinator's internal join runs its own 1-round spec+quality loop
(coordinator.md:39-40) distinct from the WP-level panel. That is the shipped
design already agreeing with Finding 6.

### Table 3 — every hardcoded number a user might want to move

| Number | Value | Source |
|---|---|---|
| Global concurrency cap (recursive) | 8 | protocol.md:200-204 |
| hex-review high panel (hits the cap exactly) | 2 + 6 = 8 | hex-review/tier-high.md:83-85 |
| hex-review medium panel ceiling | ≤6 | hex-review/tier-medium.md:80-81 |
| Coordinator gate: minimum independent sub-tasks | ≥3 | coordinator.md:13 |
| Coordinator leaf file-touch limit (else split the WP) | 8–12 files | coordinator.md:14 |
| Coordinator join review loop | 1 round, spec + quality | coordinator.md:39-40 |
| Review-Fix Loop round cap (code-diff scope) | low 1, medium 3, high 3 | hex-execute/overlays.md:46-52 |
| Plan-artifact / ADR review loop cap | 1 panel round + 1 conditional re-validation | protocol.md:150-159 |
| Research-axis worker count | skip 0, medium 1, high 3 | hex-plan/overlays.md:49; hex-architect/overlays.md:33 |
| hex-plan Discover explorer count (medium/high) | 2–4 | hex-plan/tier-medium.md:20-23, tier-high.md:25 |
| `[NEEDS CLARIFICATION]` hard cap per artifact | 3 | hex-plan/SKILL.md:251-252; hex-architect/classify.md:91-102 |
| WP overhead floor (folds into sibling) | ~≤50 expected lines | protocol.md:271-273,283 |
| hex-execute Verify-Architecture "optional" threshold (medium) | plan touches ≤3 files | hex-execute/tier-medium.md:51 |
| hex-review tier thresholds | low ≤3 files/≤100 lines/1 area; medium ≤15/≤500/1–2 areas; high >15 | hex-review/classify.md:41-43 |
| hex-plan/hex-execute low-tier scope threshold | ≤3 files | hex-plan/classify.md:19; hex-execute/tier-low.md:4 |
| Researcher source-staleness flag | ~18 months | workers/researcher.md:34,48 |
| Coordinator recursion depth | 1 level (orchestrator → coordinator → leaf) | protocol.md:190-198 |
| Capability classes | 2 (fast-balanced, deep-reasoning) | models.md:9-19 |

### What the extraction changes about the proposal

1. **Panel growth is by role diversity, never duplication** — confirmed
   exhaustively, not sampled. Finding 6's "same-role counts should stay
   inexpressible" is the shipped design, not a new constraint.
2. **The conditional (`0–1` classifier) slots are the whole customization
   surface users actually want** — `security`/`performance`/`doc-reviewer`/
   `user-feedback` fire on signals today. `perspectives.always/never` with a
   `when:` glob is the minimal way to let a project state those conditions
   itself, which is why the proposal spends its one new capability there.
3. **Two coverage holes the tables expose, neither of which any flag
   closes.** hex-architect never uses `reviewer:performance` or
   `reviewer:user-feedback` at any tier — an architecture decision with
   latency or UX consequences gets no such review by default. And hex-plan
   never spawns plain `reviewer:quality`. `perspectives.always` is the
   cheapest fix for both; nothing else proposed here touches them.
4. **hex-review high is saturated.** 2 + 6 = 8 is the global cap, not
   headroom. Any `perspectives.always` entry that fires at hex-review high
   must displace an existing perspective or breach protocol.md:200 — so the
   resolution rules below must state which loses. This is a real
   consequence of the proposal that the earlier draft missed.
5. **Table 3 corrects an earlier overstatement.** The claim that "counts are
   almost never user-visible numbers" is only true of *worker counts*; the
   bundle carries ~18 other hardcoded numbers (thresholds, caps, budgets,
   staleness windows). `limits` covers exactly two of them by design —
   the rest stay tier-file-coupled, which is the cut recorded below.

## The markdown-vs-YAML question

DESIGN.md:63-67 (Design pivot, round 3): *"the only consumer of this
layer is an LLM — no parser ever reads it. So no TOML."* Both sides,
honestly:

**For a machine-checkable carrier.** (a) Editor completion is real and
free: `# yaml-language-server: $schema=<url>` in-file, or a SchemaStore
`fileMatch` catalog entry — the standard answer to "how do we get
autocomplete for our config." (b) Validation catches typos at write time
instead of at spawn time; hex's failure mode for a misspelled key today
is *silent* (the LLM just doesn't act on it), which is the worst class of
failure. (c) Deterministic merge: with a key vocabulary you can state
"scalars: later wins; lists: replace, never append" and have it mean
something — GitLab's `include` merge learned this the hard way (`rules:`
arrays replace wholesale, never append). (d) Diffability: a reviewer can
see `loop-rounds: 1 → 3` in a PR; a prose-bullet edit is a sentence
rewrite. (e) Two adjacent hex artifacts already carry parsed YAML
(skill frontmatter, `claude.disable-model-invocation` in
hex-core/SKILL.md:5-9), so the format is not foreign.

**Against.** (a) A schema is a second source of truth that drifts —
exactly what DESIGN.md's destination-of-knowledge rule exists to
prevent; Zod's `z.toJSONSchema()`/zod-to-json-schema make "define once,
derive both consumers" cheap *only if you have a code layer to derive
from*, and hex has none. (b) The LLM must interpret the values
regardless: `perspectives.always: [reviewer:security]` still becomes a
judgment about which phase and which prompt — schema-validating the
string buys nothing downstream. (c) Prose carries nuance a schema cannot:
"security review mandatory under `src/auth/**` — the token-exchange path,
not the CRUD handlers" is a legitimate Preferences line with no field to
put it in. (d) Cost of freezing: keys become a compatibility contract at
the first grim release, same one-way-door adr_0001 flags for the
capability-class names (adr_0001:274-284).

**How the ecosystem resolved the same tension.**

| System | Carrier | Resolution |
|---|---|---|
| OpenSpec | YAML (`openspec/config.yaml`), zod-validated | 4 fields only (`schema`, `context`, `rules`, `store`); `references` deliberately hand-parsed *outside* the zod schema (project-config.ts:19-54, comment :42-45). No JSON Schema, no `$schema` modeline for its own files — the only two `$schema` hits in the repo are third-party (`.coderabbit.yaml:1`, `.changeset/config.json:2`). Oversized `context` (>50 KB) warns and is dropped, never errors (project-config.ts:130, :151-200). Its whole "customization" story is prompt/workflow content — **there is no agent-roster concept anywhere in `src/`**. |
| **get-shit-done (GSD)** | JSON (`.planning/config.json`) + global `~/.gsd/defaults.json`; **read by the agents themselves with the Read tool**, plus an SDK reader | The closest architectural analog to hex there is: 33 markdown agents, no runtime of its own, config that a *prompt* consumes. And it went all the way — ~90 keys in 16 top-level groups (`workflow` alone has 30). Ships `parallelization.max_concurrent_agents: 3` (hex's `max-workers`), `gates.*` per-approval booleans, `agent_skills` (docs/CONFIGURATION.md:383-447 — a map of agent-type → skill dirs, injected as an `<agent_skills>` XML block at spawn, "omitted entirely when unconfigured"), and a **capability-class model matrix that resolves per runtime**: `model_profile` tiers named `opus`/`sonnet`/`haiku` that map to `gpt-5.4`/`gpt-5.3-codex`/`gpt-5.4-mini` under `runtime: codex`, with a stated 4-step precedence (`model_overrides[agent]` → runtime tier → `resolve_model_ids: "omit"` → Claude-native alias). Unknown keys ignored without error (`sdk/src/config.test.ts:146`). |
| **Spec Kitty** | YAML (`.kittify/config.yaml`), Python/`ruamel` + Pydantic | Two lessons, opposite directions. (1) **What shipped is tiny**: the `agents` key is `{available: [claude, codex], auto_commit, lint_on_edit}` — three fields (`src/specify_cli/core/agent_config.py:41-44`). (2) **The elaborate version was designed and not shipped**: `research/sample-agents.yaml` (367 lines) specifies per-agent `roles`/`priority`/`max_concurrent`/`custom_flags`, ordered `defaults.implementation`/`defaults.review` fallback lists, and a `fallback.strategy` enum — and nothing in `src/` reads `agents.yaml`. Where it *is* declarative is the doctrine layer: `activated_directives` (25), `activated_tactics` (110), `activated_procedures` (18), `activated_paradigms`/`styleguides`/`toolguides` — flat opt-in lists of review/behaviour rules, i.e. `perspectives.always` at 170-entry scale. Personas are `*.agent.yaml` with field-level merge across shipped → org → project (`.kittify/charter/agents/`), 18 shipped, each with `roles`, `capabilities`, `routing-priority`, `max-concurrent-tasks`. Model routing is a separate Pydantic catalog (`src/doctrine/model_task_routing/`) with cost/latency tiers, routing weights (quality/cost/risk/latency), `tier_constraints`, and an `OverridePolicy{mode, require_reason}` — `extra="forbid"` throughout, the strict opposite of OpenSpec's resilient parse. |
| Claude Code agent files | YAML frontmatter + markdown prose body, one file | The hybrid, shipping. Fields: `name`, `description`, `tools`, `model`, `permissionMode`, `maxTurns`, `skills`, `isolation`, … — and **no `phase` field at all**. Frontmatter exists because a parser reads it. |
| Claude Code workflows | JS script under `.claude/workflows/` | Phase stays imperative: `agent(prompt, {label, phase})`. Explicitly single up-front approval, "No mid-run user input… for sign-off between stages, run each stage as its own workflow." |
| CrewAI | YAML → now JSONC (`crew.jsonc` default; classic YAML behind `--classic`) | The one real declarative *which-agent-runs-which-task* precedent: per-task `"agent": "researcher"` + `"context": ["research"]`. Parsed by a Python runtime. |
| LangGraph / AutoGen | Python `StateGraph` / dumped JSON | Core API stays code. The YAML "AgentConfig" node/edge schema is third-party, not the vendor's. |
| GitHub Actions | YAML | Solves fan-out parameterization (`strategy.matrix`, reusable workflows with `with:`) but has **no** declarative "which persona handles job X" field beyond a static `runs-on:` label. |
| ESLint flat config | JS array | "Later wins" on array order — hex's exact rule — but users found raw ordered composition so unpredictable that `extends` was reintroduced in March 2026 as sugar. hex's per-item source attribution in the announce block is doing what `extends` was added to make legible. |

The vendor whose runtime hex targets keeps phase→agent assignment out of
config (no `phase` frontmatter field, phase-as-label in an imperative
script), and the frameworks that declare it declaratively — CrewAI,
Spec Kitty — do so because an interpreter reads the file. Hybrids are
normal and cheap: frontmatter + prose in one file is the dominant shape,
so the choice is not "YAML or markdown" but "does the structured part live
in its own file or inside the markdown one."

**GSD is the one counter-example and it deserves its weight.** It has
hex's exact architecture — markdown agents, LLM-as-runtime, config parsed
only by the prompt that reads it — and it still shipped ~90 keys. So "no
parser exists" is *not* a reason a config file cannot get large; it is
only a reason it cannot be validated. What GSD pays for that is visible in
its own docs: a 1,111-line configuration reference, `workflow.*` toggles
that each agent must remember to honour individually (the recurring
"absent key = enabled, explicit `false` = disabled" phrasing appears
verbatim in four different agent files), and a per-key precedence story
re-explained per key rather than stated once. That is the failure mode
hex's Finding 1 already has in miniature. GSD also proves two of the
proposals here are conventional in this exact architecture:
`parallelization.max_concurrent_agents` is `limits.max-workers`, and
`agent_skills` is precisely the persona→panel wiring hex has unwired
(Finding 12) — GSD keys it by agent type, injects at spawn, and emits
nothing when unconfigured.

**Spec Kitty is the negative control.** Someone drafted the full
agent-roster YAML hex is being asked for — roles, priorities, concurrency
caps, ordered fallback chains — and it stayed in `research/`. What shipped
is three fields. That is one data point, not a law, but it is the only
observed outcome of trying the maximal version.

## A concrete proposal

Frozen key vocabulary, five top-level keys, rendered as one fenced
`yaml` block inside `## Preferences`. Everything not in the vocabulary
stays a prose bullet in the same section, below the block.

### Form A — fenced block inside `hex.md › Preferences` (recommended)

````markdown
## Preferences

```yaml
models:
  fast-balanced: Sonnet
  deep-reasoning: Opus
  overrides:                  # role[:focus] → class, all tiers
    reviewer:security: deep-reasoning
adversary: codex:rescue       # skill name, or `none`
limits:
  max-workers: 6              # ceiling; effective = min(8, this)
  loop-rounds: 3              # ceiling on --loop-rounds, code-diff scope
  artifact-loop-rounds: 1     # opt-in only; 1 = shipped behaviour
perspectives:
  always:                     # added to every tier's baseline set
    - role: reviewer:security
      when: "src/auth/**"     # optional path glob; omitted = every run
    - role: reviewer:accessibility   # .agents/workers/ persona
      when: "src/ui/**"
  never: [doc-reviewer]       # subtracted last; never removes reviewer:spec
research-axes:                # pre-seeds hex-architect's candidate list
  - registry ecosystems
  - OCI spec evolution
```

- Security review means the token-exchange path, not the CRUD handlers.
- Worktrees stay on the default; deviations are a Pointers concern.
````

**Resolution.** Unchanged three inputs, later wins (protocol.md:94-109):
shipped tier baseline → this block → user flags / gate. Merge semantics,
which is the part that must be written down:

1. **Scalars** (`adversary`, every `limits.*`, every `models.*`) — later
   layer replaces earlier. `limits.max-workers` is a **ceiling, never a
   floor**: effective cap = `min(8, max-workers)`; a value above 8 is
   announced as clamped.
2. **`models.overrides`** — merged per key (an override for one role
   never disturbs another). Escalating above the shipped cell still
   requires the announced reason rule (models.md rule 1). Never resolves
   to an orchestrator-class model (adr_0001 C-002).
3. **Lists** (`perspectives.always`, `perspectives.never`,
   `research-axes`) — **replace wholesale, never append** across layers
   (GitLab's `rules:` lesson). Within a single layer, the resolved panel
   is computed once at the end: `baseline ∪ always(matching paths) −
   never`. `never` is applied last and cannot remove `reviewer:spec`
   (the traceability check is a contract gate, not a perspective).
   **The concurrency cap wins over `always`.** hex-review high already runs
   2 + 6 = 8, exactly the protocol.md:200 ceiling (Table 1), so an `always`
   entry firing there has nowhere to go. Rule: if the resolved panel exceeds
   the cap, drop `always` entries in reverse declaration order and announce
   each drop with its reason. Never silently exceed the cap, and never drop
   a baseline perspective to make room for a preference.
4. **Unknown keys** — warn once in the announce block, ignore, continue.
   Resilient-parse, OpenSpec's `validateConfigRules` pattern
   (project-config.ts:278-295) and its 50 KB context drop: a bad field
   never blocks a run.
5. **Missing file / missing block** — normal. Shipped defaults; a
   `/hex-init` suggestion, never an error (memory.md:9-24).

**Announce block** gains a source per item, as today:

```
Tier: medium (classifier — 9 files, 340 lines)
Spawn: builder×3, tester×3, reviewer:quality, reviewer:spec,
       reviewer:security (hex.md preference — src/auth/** matched)
       [doc-reviewer suppressed — hex.md preference `never`]
Models: fast-balanced default; reviewer:security → Opus (hex.md override)
Limits: max-workers 6 (hex.md), loop-rounds 3 (tier baseline)
Adversary: codex:rescue (hex.md) — fires on --adversary only at this tier
```

### Form B — YAML frontmatter on `hex.md` (same content, for comparison)

```markdown
---
models: {fast-balanced: Sonnet, deep-reasoning: Opus,
         overrides: {reviewer:security: deep-reasoning}}
adversary: codex:rescue
limits: {max-workers: 6, loop-rounds: 3, artifact-loop-rounds: 1}
perspectives:
  always: [{role: reviewer:security, when: "src/auth/**"}]
  never: [doc-reviewer]
research-axes: [registry ecosystems, OCI spec evolution]
---

# hex — swarm memory

## Pointers
…
## Preferences
- Security review means the token-exchange path, not the CRUD handlers.
## Memory
…
```

**Why A over B.** `hex.md` has three sections with three different
owners (memory.md:34-37). Frontmatter hoists user-owned config above
skill-managed sections and makes the whole file read as machine-owned,
which invites the exact autonomous edits `Preferences` is protected
against. The fenced block keeps ownership co-located with its section,
survives a skill rewriting `Pointers` underneath it, and leaves prose
nuance directly adjacent to the structured keys it qualifies. B's only
advantage — a parser could read it without locating a heading — is worth
nothing while no parser exists.

### Deliberately cut

| Asked for | Verdict |
|---|---|
| Same-role counts (`count: 2` security reviewers) | Cut. `hierarchical-execution-performance.md:72-92`: reviewers plateau at ~5 same-kind; grow role diversity, not count. The expressible equivalent is a model override plus a *different* perspective. |
| Tier redefinition (`medium: {researchers: 3}`) | Cut. Tier grammar is fixed vocabulary (protocol.md:18-34) and `--research=3` already covers the per-run case. Redefining a tier makes every announce block lie about what "medium" means. |
| Per-phase panel composition (`phase.stage2: [...]`) | Cut. Neither Claude Code's subagent schema nor its workflow runtime has a phase field; hex would be inventing a format with no ecosystem to align to. `perspectives.always/never` covers the real want. |
| Classifier threshold overrides | Cut for now. Real gap (D-4), but thresholds are tier-file-coupled; a `when:` path glob on a perspective covers most of the motivating cases without letting a project redefine tiering. |
| Per-project overlay-flag defaults (D-6) | Cut. `limits.loop-rounds` covers the one case with a documented ceiling; the rest is a flag away. |
| A published JSON Schema / `$schema` modeline | Cut. No code layer to derive it from → it becomes the drifting second source of truth. OpenSpec, with an actual TypeScript validator, still ships none. |

## Interactive init design

### The nearest precedent is OpenSpec's own — now observed, not inferred

OpenSpec ships **three** interactive flows and `openspec config profile` is
a near-exact analog of the "ask about workflows" half of the request. All
three were **run end-to-end under a pty** at `@fission-ai/openspec@1.6.0`;
the transcripts below are verbatim, and the source citations are secondary
confirmation of *why* each string appears.

Three operational facts from doing it, before the content:

- **The npm name is `@fission-ai/openspec`, not `openspec`.** Bare
  `openspec` on npm is a defunct `0.0.0` placeholder; `npx openspec@1.6.0`
  fails with `ETARGET`. Any hex doc or precedent note that writes
  `npx openspec` is citing a package that does not exist.
- **Driving an inquirer/ink prompt over a pty without setting a window size
  looks exactly like a hang.** The first scripted `init` emitted 57 MB of
  cursor-repositioning ANSI in 150 s, stuck re-rendering the tool picker;
  adding `ioctl(fd, TIOCSWINSZ, (40,120))` made the identical run finish in
  7.7 KB. Property of the library class, not an OpenSpec bug — but it is
  the thing to know before anyone tries to CI-test a hex init wizard.
- **Telemetry can stall a first run offline.** The PostHog client uses a
  1 s `requestTimeout` and fails soft, yet the un-opted-out first probe
  outlived a 60 s budget in this sandbox. Its own first-run banner is the
  only hint: `Note: OpenSpec collects anonymous usage stats. Opt out:
  OPENSPEC_TELEMETRY=0`.

**1. `openspec config profile` (`src/commands/config.ts:452-645`)** — the
workflow/delivery picker. Observed transcript, verbatim:

```
Current profile settings
  Delivery: both
  Workflows: 6 selected (core)
  Delivery = where workflows are installed (skills, commands, or both)
  Workflows = which actions are available (propose, explore, apply, etc.)

? What do you want to configure?
❯ Delivery and workflows
  Delivery only
  Workflows only
  Keep current settings (exit)
Update install mode and available actions together
↑↓ navigate • ⏎ select

? Delivery mode (how workflows are installed):
❯ Both (skills + commands) [current]
  Skills only
  Commands only

? Select workflows to make available:
❯[x] Propose change      [x] Explore ideas     [ ] New change
 [ ] Continue change     [x] Apply tasks       [x] update
 [ ] Fast-forward        [x] Sync specs        [x] Archive change
 [ ] Bulk archive        [ ] Verify change     [ ] Onboard
Space to toggle, Enter to confirm

Config changes:
  profile: core -> custom
  workflows: removed propose

? Apply changes to this project now? (Y/n) n
Config updated. Run `openspec update` in your projects to apply.
```

(The checkbox list renders one per line; wrapped to three columns here.)
Its shape, in order:

- **Refuses to guess when it can't ask**: `if (!process.stdout.isTTY)` →
  error `Interactive mode required. Use \`openspec config profile core\` or
  set config via environment/flags.`, exit 1. Non-interactive callers get a
  named non-interactive path, never a silent default.
- **Prints current state before the first question** — delivery, workflow
  summary, and two dimmed one-line glossary lines (`Delivery = where
  workflows are installed…`, `Workflows = which actions are available…`).
  The vocabulary is taught at the point of use, not in a doc.
- **Question 0 is a scope selector, not a setting**: "What do you want to
  configure?" → `Delivery and workflows` / `Delivery only` / `Workflows
  only` / **`Keep current settings (exit)`**. Every choice carries a
  one-line `description`. An explicit no-op exit is a first-class option.
- **Current values are labelled, not merely defaulted** — each delivery
  choice gets `' [current]'` appended to its name *and* `default:
  currentState.delivery` is set. Belt and braces, because a highlighted
  default is invisible in a transcript.
- **The workflow question is a `checkbox`, pre-checked from current state**
  (`checked: currentState.workflows.includes(workflow)`), with
  `instructions: 'Space to toggle, Enter to confirm'`, `pageSize` set to the
  full list so nothing scrolls out of view, and an ASCII `[x]`/`[ ]` theme
  override. The profile name is then **derived** from the selection
  (`deriveProfileFromWorkflowSelection`) — the user picks capabilities, the
  label is computed.
- **A diff is printed before the write**, and `if (!diff.hasChanges)` short-
  circuits to `No config changes.` — same string as the explicit-exit path.
  Observed form is two lines, one per changed key, old → new:
  `profile: core -> custom` / `workflows: removed propose`. Note the diff
  reports the *derived* key (`profile`) alongside the one the user touched.
- **Apply is a separate consent**: after `saveGlobalConfig`, if an
  `openspec/` dir exists, `confirm({message: 'Apply changes to this project
  now?', default: true})`; declining prints guidance instead of acting. A
  failed `openspec update` is caught and reported with "Please run it
  manually", exit 1 — never left ambiguous.
- **Cancellation is a documented exit code**: `isPromptCancellationError` →
  `Config profile cancelled.`, `process.exitCode = 130`.

**2. `openspec init` (`src/core/init.ts`, picker at
`src/prompts/searchable-multi-select.ts`)** — **not** a numbered wizard.
Observed: one continuous flow — animated welcome screen → searchable
multi-select → deterministic generation → success summary. The `[n/3]`
pattern belongs to `workset create`, not to init. Verbatim, fresh project,
typing `claude`, space, enter:

```
                        Welcome to OpenSpec
                        A lightweight spec-driven framework

                        This setup will configure:
                          • Agent Skills for AI tools
                          • /opsx:* slash commands

                        Quick start after setup:
                          /opsx:new      Create a change
                          /opsx:continue Next artifact
                          /opsx:apply    Implement tasks

                        Press Enter to select tools...

? Select tools to set up (31 available)
  Selected: (none selected)
  Search: [type to filter]
  ↑↓ navigate • Space toggle • Backspace remove • Enter confirm
  › ○ Amazon Q Developer
    ○ Antigravity
    ○ Auggie (Augment CLI)
    …
  (1/3)
…after typing 'claude'…
  Selected:  Claude Code
  Search: [claude]
  › ◉ Claude Code (selected)
✔ Select tools to set up (31 available) Claude Code
░░░ Creating OpenSpec structure...▌ OpenSpec structure created
⠋ Setting up Claude Code...✔ Setup complete for Claude Code

OpenSpec Setup Complete

Created: Claude Code
6 skills and 6 commands in .claude/
Config: openspec/config.yaml (schema: spec-driven)

Getting started:
  Start your first change: /opsx:propose "your idea"
…
Restart your IDE for slash commands to take effect.
```

Corrections to the earlier code-only reading: the picker offers **31**
tools, not 34 (`(31 available)` in every observed run, and the
non-interactive error dumps exactly 31 slugs), and the widget is
**hand-rolled** — `searchable-multi-select.ts`, 221 lines on `@inquirer/core`
primitives (`createPrompt`, `useState`, `useKeypress`, `usePrefix`), not a
library prompt. It renders message → `Selected:` chips → `Search:` box →
instruction line → paginated `◉`/`○` list with a `›` cursor → `(page/total)`.
At 31 items a flat checkbox would be unusable; the search-to-filter
affordance is what makes it scale, and the component is copy-adaptable.

Choices are **sorted by knowledge state** (configured →
detected-not-configured → the rest), pre-selection is computed
(`configured || (shouldPreselectDetected && detected)`), and the detection
result is *narrated* before the prompt. `validate: selected.length > 0 ||
'Select at least one tool'`.

**Idempotency, observed by diffing a first run against a re-run.** The
re-run auto-prints `OpenSpec configured: Claude Code (pre-selected)` before
the prompt, labels the entry `(refresh)` instead of `(selected)`, and the
summary changes two lines: `Refreshed: Claude Code` (not `Created:`) and
`Config: openspec/config.yaml (exists)` (not `(schema: spec-driven)`).
Skill and command files are **unconditionally regenerated**; `config.yaml`
is **never rewritten once it exists**. That split — regenerate deterministic
scaffolding always, never clobber the one user-owned file — is the whole
idempotency model, and it is exactly the rule hex's re-entrant `/hex-init`
needs for the Preferences block.

**Non-interactive.** `--tools all|none|<csv>`, `--force` (skip the legacy
confirm), `--profile core|custom`. Non-interactive mode triggers on no TTY,
or `--tools` given, or `CI` set. Its error is the one worth copying — it
dumps the entire valid-value list inline so the fix is paste-able without
re-running `--help`:

```
✖ Error: No tools detected and no --tools flag provided. Valid tools:
  amazon-q
  antigravity
  …31 slugs…
  windsurf

Use --tools all, --tools none, or --tools claude,cursor,...
```

Legacy cleanup asks once — `confirm({message: 'Upgrade and clean up legacy
files?', default: true})` (init.ts:296-306) — and **only when it can
prompt**: `if (this.force || !canPrompt)` auto-cleans, justified in a
comment ("legacy slash commands are 100% OpenSpec-managed, and config file
cleanup only removes markers (never deletes files)"). Declining prints
`Initialization cancelled.` / `Run with --force to skip this prompt, or
manually remove legacy files.` and exits **0**. One well-scoped confirm
gating a destructive-adjacent step, with the escape-hatch flag named in the
decline message — not a battery of yes/no prompts.

**3. `openspec workset create` (`src/commands/workset-prompts.ts:1-189`)** —
the only *wizard* (multi-step) flow, and the closest real precedent to a
hex-style `[1/3]` init. Observed in full:

```
[1/3] Name the workset
? Workset name: myworkset

[2/3] Add member folders (the first one is the primary - sessions start there)
? Folder path: (.) .
  Added 'live6' (/tmp/.../live6)
? Add another folder or finish:
❯ Finish
  Add another folder

[3/3] Choose your tool
? Open with:
❯ VS Code

Saved workset 'myworkset' (1 member) to your machine.
? Open it now in VS Code? (Y/n)
```

The step labels explain *why* the step matters inline ("the first one is
the primary - sessions start there") rather than being bare field names —
that alone is worth imitating. Three more details worth stealing outright:

- **Flag-provided answers are validated before any prompting** — comment
  in-source: "a bad flag or tool cannot discard a finished wizard walk."
  Validate everything you already know first, so the user never types five
  answers and then loses them to a typo in argument one.
- **Validation is per-question and re-prompts in place** (`validate` returns
  the error string; folder existence is checked async in the validator), and
  answers already supplied are echoed as `Added '<name>' (<path>)` so the
  transcript is self-documenting.
- **A follow-up question is asked only when it can't be inferred** — the
  member label is auto-derived from `path.basename`, and the "Name this
  member" prompt fires *only* on a collision or an invalid basename. Same
  rule as the "must NOT ask — detect instead" list below, implemented.
- **Graceful degradation instead of a dead end** — if no known tool is on
  PATH, it prints "not saving a preference" and continues rather than
  failing the wizard.

**What OpenSpec does *not* have, and hex therefore cannot copy:** any
question about agents, models, reviewers, or panel composition. Its
`serializeConfig` (`src/core/config-prompts.ts`, 39 lines) writes
`schema:` plus **commented-out examples** of `context:` and `rules:` — the
init flow never asks for either; it seeds a file whose optional sections are
teaching comments. That is a fourth pattern worth taking: for keys you
cannot recommend a value for, emit a commented example rather than a
question.

**Where the state lives, observed.** Worksets are **100% local machine
state** — `$XDG_DATA_HOME/openspec/worksets/worksets.yaml` plus a generated
`.code-workspace`, never under the project's `openspec/`, never in git
(`git status --short` after creating one shows only `.claude/` and
`openspec/`). Global config is a *third* location,
`~/.config/openspec/config.json`, holding `{featureFlags, profile,
delivery, telemetry, workflows}`; the project's `openspec/config.yaml`
holds only `schema:` plus commented-out `context:`/`rules:` examples. A
clean three-tier split: machine-wide defaults, per-repo specifics,
never-shared personal working views. hex's analogue exists but is
one-tier — everything is `hex.md`.

**`doctor` is narrower than its name.** Observed happy path is four lines:
`Doctor` / `Root` with `Location:` and `OpenSpec root: ok` / `References`
with `(none declared)`. `--json` returns
`{"root":{…,"healthy":true,"status":[]},"store":null,"references":[],"status":[]}`.
It checks *relationship health* between OpenSpec roots and registered
stores, not project health — its own doc comment says it "never clones,
syncs, or repairs". Outside a root, `doctor` and `context` fail identically:

```
Error: No OpenSpec root found from the current directory.
Fix: Run openspec init to create a root here.
```

Every error in this codebase pairs a one-line `Error:` with a one-line
`Fix:`. That convention is the actionable form of Finding 16 — and it is a
cheap rule for hex's announce block to adopt verbatim.

**Modality caveat, now narrow.** `init` (fresh + re-run), `config profile`,
`workset create`, `doctor` (happy path + no-root error), `context`,
`new change`, and `instructions` were all executed. Still unobserved: the
`--profile custom` init path, `store`/`references` in a non-empty state,
and anything about multi-user or CI behaviour beyond the `CI`-env
non-interactive branch.

**Net effect on the design below**: items 1–5 keep their order, but the
mechanics are now sourced from an executed shipping analog rather than from
Copier/create-next-app/cargo-generate alone — add the scope-selector
question zero, the `[current]` labelling, the pre-write diff naming the
derived key too, the separate apply consent, the commented-example seeding
for anything not asked, the regenerate-scaffolding-but-never-clobber-config
idempotency split, and the `Error:`/`Fix:` pairing on every refusal.

### The hex flow

`/hex-init` stays the sole writer, sole entry point, user-invoked only
(SKILL.md:9-16), and keeps its one batched approval (SKILL.md:72-77).
Preferences elicitation is Step 4½ — between matrix instantiation and
the `hex.md` write — and adds `preferences` to the positional concern
list (SKILL.md:200-204).

**Question order — general → specific** (create-vite's framework-then-
variant drill-down), each with a pre-filled Recommended value so plain
approval accepts everything (protocol.md:45-92's `Recommended: <answer>
— <reason>` convention):

1. **Model literals per class** — detected harness, proposed mapping.
   Existing Step 4.
2. **Cross-model adversary** — propose a skill only if one is detectable
   in the installed skill set; else propose `none`. Never ask
   open-endedly for a name the user would have to recall.
3. **Limits** — propose the shipped defaults verbatim (`max-workers 8`,
   `loop-rounds` per tier, `artifact-loop-rounds 1`) and say what each
   caps. Presenting them is how the semantics get taught.
4. **Always-on / never perspectives** — *conditional*, Copier's `when:`
   pattern: only ask when the Step-1 audit actually found a
   security-sensitive path (`auth`, `crypto`, `payment`, `migrations`)
   or a project-local persona under `.agents/workers/`. Skip
   silently otherwise.
5. **Research axes** — conditional on the project already having
   research artifacts or a product doc.

Five items maximum, one block, one approval. Anything declined is listed
as skipped in the closing three-list summary and never written — empty
Preferences remains the normal state (SKILL.md:147-150).

**Must NOT ask — detect instead.** The harness in use; whether
`.agents/worktrees/` is gitignored (read the file); the verification
command (audit project context first, propose only on a miss); plan/ADR
convention locations (audit item); whether a persona file exists (list
the directory); anything answered on a previous run and unchanged
(Copier: `copier update` skips already-answered questions). Asking a
detectable thing is the tell of a badly designed init.

**Non-interactive.** `--yes` accepts every recommendation without
prompting (create-next-app's `--yes` = "previous preferences or defaults
for all options not explicitly specified"); `-d key=value`, repeatable,
sets one key non-interactively (cargo-generate). Both are consistent
with hex's existing "flags stay for non-interactive override"
(DESIGN.md:114-133).

**Idempotent re-run.** Already specified and unchanged: re-entrant runs
update only what drifted or what the user changed, never rewrite the
whole file, never touch `Memory` (SKILL.md:153-161). Extend it to the
block: keys the user did not touch keep their values and their comments;
a key removed from the vocabulary in a later hex version is reported as
deprecated in the summary, not silently deleted. Users are told not to
hand-edit — same rule as Copier's `.copier-answers.yml` — but a
hand-edit must never corrupt a run, which is what rule 4 (unknown keys
warn and continue) buys.

## Key findings

1. hex's persistent-config layer names four knobs whose enforcement is
   written down nowhere: `max-workers` vs the hardcoded "at most 8"
   (protocol.md:200 vs memory.md:36,:64), and `loop rounds` vs each
   skill's `--loop-rounds` per-tier default
   (protocol.md:145-161 vs hex-execute/overlays.md:41-58). This is a
   spec gap, not a format gap.
2. `Preferences` is documented only by example — prose bullets under a
   heading (memory.md:59-66) — so there is no key an orchestrator can
   reliably look for. Two readers of the same file can disagree about
   whether `Limits: max-workers 6` is binding.
3. OpenSpec ships **no** JSON Schema and no `yaml-language-server`
   modeline for its own `config.yaml`/`schema.yaml` despite having a
   full zod validator; the repo's only two `$schema` references are
   third-party tool configs (`.coderabbit.yaml:1`,
   `.changeset/config.json:2`). Editor completion is not the table
   stakes it is assumed to be.
4. OpenSpec's customization is entirely *workflow/prompt* content —
   `context`, per-artifact `rules`, and replaceable `schema.yaml`
   workflows (docs/customization.md, 3 levels). There is **no
   agent-roster, model-choice, or reviewer-panel concept anywhere in
   `src/`**; the whole `openspec schema` family is still flagged
   experimental with a runtime warning on every invocation
   (src/commands/schema.ts:293,:296-297). Nothing in OpenSpec answers
   "which subagents staff this."
5. **No reviewer panel exists in OpenSpec, in any form.** Its one
   AI-driven review, `skills/openspec-verify-change/SKILL.md`, tells a
   *single* agent to fill in Completeness/Correctness/Coherence itself —
   no Task dispatch, no personas, no fan-out. The single Task-tool
   subagent call in the whole codebase is one optional, sequential
   delegation in archive-change
   (src/core/templates/workflows/archive-change.ts:71,:189). hex is not
   behind OpenSpec here; the two are not comparable.
   **And that one agent's checklist is not extensible by config.** The
   `rules:` map is keyed by *artifact ID* — `validateConfigRules` warns for
   any key that "matches no artifact in any available schema"
   (project-config.ts:270-295) — and the `<rules>` block is emitted only by
   `generateInstructions` for a named artifact
   (workflow/instructions.ts:225-231). The verify skill's own CLI call is
   `openspec instructions apply --change <name> --json`, whose payload is
   `{changeName, schemaName, contextFiles, progress, tasks, state,
   missingArtifacts, instruction}` (instructions.ts:341-425) — **no rules
   field**. So a user can add "Keep proposals under 500 words" to the
   proposal artifact, but there is no supported way to add a fourth
   dimension beside Completeness/Correctness/Coherence, or to say "always
   check X when verifying". Editing the generated SKILL.md is the only
   path, and `openspec update` will regenerate over it (`generatedBy`
   version stamp). **Confirmed from the prompt-assembly source, not only
   from the payload shape:** `src/core/templates/workflows/verify-change.ts`
   builds the skill's instructions as one static template literal
   interpolating exactly one value (`STORE_SELECTION_GUIDANCE`) across
   ~170 lines of steps 1–8; it never references `projectConfig` and never
   calls `instruction-loader.ts`, the only place `projectConfig?.rules
   ?.[artifactId]` is read. The checklist is *deliberately* fixed while
   artifact generation in the same tool is configurable — a clean
   precedent for hex keeping reviewer rubrics in shipped files while
   letting projects state *which* reviewers run. The lesson for hex is
   the inverse-existence proof: an
   extensible *reviewer checklist* has no precedent here either, so
   `perspectives.always/never` is not a feature hex is missing relative to
   OpenSpec — it is genuinely new ground.
6. hex's own research already forbids the most-requested missing knob:
   same-kind reviewers plateau at ~5 and error amplification runs
   1.0× single → 4.4× centralized → 17.2× independent
   (`hierarchical-execution-performance.md:9-19,:72-92`). "Two security
   reviewers" should stay inexpressible.
7. Claude Code's own subagent frontmatter has **no** `phase` field, and
   its first-party multi-agent primitive (`.claude/workflows/*.js`)
   keeps phase assignment in imperative code with a single up-front gate
   and explicitly no mid-run input. hex's tier-file-prose design matches
   the vendor's own answer to the identical problem.
   https://code.claude.com/docs/en/sub-agents ·
   https://code.claude.com/docs/en/workflows
8. CrewAI is the only real declarative phase→agent precedent
   (`{"name": "analysis", "agent": "analyst", "context": ["research"]}`)
   — and it recently moved its default from YAML to JSONC, so "CrewAI
   uses YAML" claims are already stale. It works because a Python
   runtime parses it. https://docs.crewai.com/en/concepts/crews
9. Array merge is the recurring trap: GitLab's `include` cannot merge
   `rules:` arrays (top-level replaces wholesale), Ruff resets the
   `ignore` baseline when `select` is specified, and ESLint had to
   reintroduce `extends` in March 2026 because raw ordered-array
   composition was too unpredictable. Any list-valued hex key must state
   replace-vs-append explicitly. https://docs.gitlab.com/ci/yaml/includes/ ·
   https://docs.astral.sh/ruff/configuration/ ·
   https://eslint.org/blog/2025/03/flat-config-extends-define-config-global-ignores/
10. Precedence chains are the well-trodden part: OpenSpec resolves
    `schema` as CLI flag → per-change `.openspec.yaml` → project
    `config.yaml` → hardcoded `'spec-driven'`, stated identically in
    `src/utils/change-metadata.ts:166-198` and docs/customization.md;
    Claude Code resolves a subagent's model as
    `CLAUDE_CODE_SUBAGENT_MODEL` env → per-invocation param → frontmatter
    → session model. Note the shape models.md:59-73 warns about is real
    and shipping: in Claude Code a *global* env var outranks the
    per-agent choice.
11. Resilient-parse-with-warnings is worth copying outright: OpenSpec
    drops an oversized `context` with a `console.warn` rather than
    failing (project-config.ts:130,:151-200) and warns once per session
    on unknown `rules` keys validated against the union of artifact IDs
    across *all* schemas (project-config.ts:278-295).
12. hex already has a customization surface deeper than anything
    proposed here and does not document its wiring: project-local
    personas at `.agents/workers/*.md` add whole new roles
    (workers.md:65-74), and `--axes=` accepts arbitrary axis names the
    researcher persona never validates against the 7-row catalog
    (workers/researcher.md:28). Documenting the persona→panel wiring
    is cheaper than any new field.
13. Config-file-per-directory federation is unsolved everywhere it
    matters: OpenSpec has flat specs only (issues #662, #581, #697 open),
    spec-kit punts to "run it at the top level," log4brains documents
    cross-repo ADR aggregation as roadmap-only, and Claude Code's own
    guidance once nested `CLAUDE.md` stops scaling is *plugins* — i.e.
    versioned registry distribution, which is what `grim` already is for
    arcana. Multi-repo config is a distribution problem, not a schema
    problem.
14. Adoption context for OpenSpec's model, since it is being held up as
    the target: 61,688 stars, 41 releases in ~10 months, and one
    dominant criticism across independent write-ups — *spec drift*,
    because sync is advisory rather than enforced, with practitioners
    reporting they abandoned the sync step. A config surface that is
    "written but never enforced" is precisely hex's Finding 1 defect,
    at a larger scale.
15. **OpenSpec's "which workflows" question is a shipped, interactive,
    two-profile switch — and it is the closest thing in the field to what
    hex is being asked for.** `docs/workflows.md:31-83` describes a 5-action
    `core` profile; the **shipped v1.6.0 picker shows 6 of 12** —
    `Propose change`, `Explore ideas`, `Apply tasks`, `update`, `Sync
    specs`, `Archive change` pre-checked, with `New change`, `Continue
    change`, `Fast-forward`, `Bulk archive`, `Verify change`, `Onboard`
    unchecked (observed transcript; the doc omits `update`). Opt-in is via
    `openspec config profile` + `openspec update`. Two facts hex should
    note: the default is
    deliberately *small* and the doc argues for one habit (`explore` first)
    rather than exposing the whole grammar, and enabling more workflows is
    a **two-command** operation — config write, then an explicit apply.
    hex's tier system is the analogous "how much machinery runs" dial, and
    it is already automatic; the missing piece is only the *stateable*
    per-project default, which `limits`/`perspectives` covers.
16. **`openspec doctor` is the shipped answer to "does it surface config
    problems interactively", and the answer is: no — it surfaces them
    *diagnostically*.** `src/commands/doctor.ts` (219 lines) is read-only by
    contract ("never clones, syncs, or repairs"), reports findings as
    `{message, fix}` pairs, and is a separate command from the presentation
    surface `openspec context` (212 lines) by explicit in-source design
    ("doctor is the health surface"). Combined with Finding 11's
    resilient-parse-with-warnings, the shipped posture is consistent:
    **never block a run on config trouble; make the trouble queryable, and
    ship the remediation string next to the complaint.** hex's equivalent is
    the announce block, and the actionable form of this finding is that a
    warned-and-ignored unknown key (proposal rule 4) must print its fix, not
    just its complaint.
17. **CI does not validate the artifacts.** `.github/workflows/ci.yml` gates
    on vitest ×3 platforms, `tsc --noEmit`, lint, a dist-artifact existence
    check, path-filtered Nix build, and changeset status — there is no
    `openspec validate` job. The tool that exists to keep specs and code in
    step does not enforce that on itself. If hex ever adds a verification
    command story, the precedent to *avoid* is this one: a validator nobody
    runs in CI is a validator that documents drift rather than preventing
    it.
18. **Both named competitors are now cloned and read, and they bracket the
    design space.** Spec Kitty (1,429 stars) and GSD (64,779 stars) were
    previously sized from marketing copy only; both have now been opened.
    - **GSD is the maximal answer and shares hex's architecture exactly**
      — markdown agents, LLM-as-runtime, config that only a prompt reads.
      It still shipped ~90 keys in 16 groups plus a 1,111-line reference
      doc. It independently invented two of this proposal's items:
      `parallelization.max_concurrent_agents` (= `limits.max-workers`) and
      `agent_skills` (= the persona→panel wiring of Finding 12, keyed by
      agent type, injected as an `<agent_skills>` block at spawn, emitted
      as nothing when unconfigured). It also solves models the way
      `models.md` does — abstract tiers (`opus`/`sonnet`/`haiku` as
      *names*) with a per-runtime resolution table, `runtime: codex`
      mapping them to `gpt-5.4`/`gpt-5.3-codex`/`gpt-5.4-mini` — which is
      independent confirmation that hex's capability-class abstraction is
      the right shape, and a warning that the *literal alias names* are a
      bad choice for those classes.
    - **Spec Kitty is the negative control.** The full agent-roster YAML —
      per-agent `roles`/`priority`/`max_concurrent`/`custom_flags`, ordered
      `defaults.implementation`/`defaults.review` fallback chains, a
      `fallback.strategy` enum — was written (`research/sample-agents.yaml`,
      367 lines) and **never shipped**; nothing in `src/` reads
      `agents.yaml`. What shipped is `{available, auto_commit,
      lint_on_edit}`. Where it did go declarative is the *rule* layer, not
      the roster: `activated_directives` (25), `activated_tactics` (110),
      `activated_procedures` (18) plus paradigms/styleguides/toolguides —
      flat opt-in lists, i.e. `perspectives.always` at 170-entry scale, and
      the shape hex should study if the vocabulary ever grows.
    Net: the two ends of the spectrum are both survivable, but the one that
    matches hex's architecture (GSD) pays for its size in doc surface and
    per-key precedence prose, and the one that tried the maximal roster
    (Spec Kitty) abandoned it. Nothing here changes the recommendation;
    both strengthen the "small frozen vocabulary" side of it.

19. **The cleanest deterministic-CLI / agent-authored boundary in the
    field, observed end to end.** `openspec new change add-rate-limiting`
    writes exactly one file — `changes/<name>/.openspec.yaml` containing
    `schema: spec-driven` and `created: 2026-07-20`, nothing else. No
    proposal.md, no tasks.md, no design.md. Content generation is handed
    over by a *separate command*: `openspec instructions proposal --change
    <id>` emits a structured block — `<artifact>`, `<task>`, `<output>`
    (the literal absolute path to write), `<instruction>`, `<template>`
    (fill-in Markdown with HTML-comment guidance) — whose instruction text
    names cross-artifact contracts explicitly ("The Capabilities section is
    critical. It creates the contract between proposal and specs phases.").
    The CLI computes *where* and *what shape*; the LLM writes 100% of the
    prose. Relevance to hex: hex bakes equivalent prompt text into skill
    markdown, which is fine while the client is the runtime — but
    `instructions`-as-a-command is the pattern to reach for if hex ever
    needs the same template consumed by more than one caller. It is also
    the reason OpenSpec's config surface can stay at four keys: everything
    a user would want to tune about *content* lives in the schema's
    instruction templates, not in `config.yaml`.

20. **Optionality is real in OpenSpec's own dogfooding.** The
    representative in-flight change `add-change-stacking-awareness` ships
    `proposal.md` (93 lines), `tasks.md` (39 lines, 6 numbered sections
    of flat GFM checkboxes ending in a Verification section that runs
    targeted tests then the full suite), four spec deltas (15–65 lines,
    `## ADDED Requirements` + WHEN/THEN/AND scenarios), a two-line
    `.openspec.yaml` — and **no `design.md` at all**, despite touching
    four capabilities. Optional-by-default is practised, not just
    declared. Its own Why section names the gap this dossier's Finding 13
    describes: "no machine-readable way to express sequencing,
    dependencies, or expected merge order" — while `docs/workflows.md`'s
    Parallel Changes pattern and bulk-archive already do an informal,
    archive-time, non-persisted version of it (detect two changes touching
    `specs/ui/`, resolve by checking what is actually implemented, merge
    chronologically). The formal metadata model is a proposal; the agentic
    workaround is what ships.

## Recommendation

**Ship the fenced-YAML-block-in-`hex.md` hybrid (Form A) with the frozen
five-key vocabulary, and write the merge/enforcement semantics into
`protocol.md` in the same change.** The semantics are the deliverable;
the block is just the shape that makes them stateable. Land it before
the first grim release — key names freeze as a contract exactly like the
capability-class names (adr_0001:274-284).

Order of work, smallest first:

1. **Fix Finding 1 without any new syntax.** One paragraph in
   protocol.md's Worker coordination section: `effective cap = min(8,
   hex.md max-workers)`; one in the Review-Fix Loop: the stored
   `loop rounds` is a ceiling on the per-tier default *and* on
   `--loop-rounds`. This is worth doing even if everything below is
   rejected.
2. **Freeze the vocabulary** (`models`, `adversary`, `limits`,
   `perspectives`, `research-axes`) in memory.md, replacing the
   example-only description at :36 and :59-66. Add the five resolution
   rules. Unknown keys warn and continue.
3. **Add `perspectives.never` and the `when:` path glob** — the two
   genuinely new capabilities, and the two that close the most items on
   the cannot-express list (D-1 partially, D-2, D-5).
4. **Document the persona→panel wiring** for
   `.agents/workers/*.md` — a named persona in
   `perspectives.always` is how it enters a Stage-2 launch list. Zero
   new mechanism; the mechanism already exists unwired.
5. **`/hex-init` Step 4½** with the five conditional questions and the
   `--yes` / `-d key=value` non-interactive pair.

Cut, explicitly and on the record: tier redefinition, per-phase panel
composition, same-role reviewer counts, classifier threshold overrides,
per-project overlay-flag defaults, a second config file, YAML
frontmatter, a published JSON Schema, and a `$schema` modeline. If the
block ever needs more than a screen, that is the signal that hex grew a
runtime — revisit then, not now.

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| OpenSpec clone @ v1.6.0 — `src/core/project-config.ts`, `src/core/artifact-graph/{types,schema,resolver}.ts`, `src/utils/change-metadata.ts`, `src/core/config-schema.ts`, `src/commands/schema.ts`, `src/commands/workflow/instructions.ts` | Repo | 2026-07-10 (v1.6.0) | zod config shapes, 4-step schema precedence, 3-tier schema-dir precedence, prompt-block injection order, experimental warning |
| OpenSpec clone @ v1.6.0 — `src/commands/config.ts:475-645`, `src/core/init.ts:270-500`, `src/commands/workset-prompts.ts:34-163`, `src/commands/workset-input.ts`, `src/core/config-prompts.ts` | Repo | 2026-07-10 (v1.6.0) | the three shipped `@inquirer/prompts` flows: scope-selector question zero, `[current]` labelling, pre-checked checkbox, pre-write diff, separate apply consent, exit 130 on cancel, `[n/3]` wizard headers, validate-flags-before-prompting, commented-example config seeding. Source-level *why* behind the observed transcripts |
| **Executed CLI transcripts** — `@fission-ai/openspec@1.6.0` driven under `pty.fork()` + `TIOCSWINSZ(40,120)`, `OPENSPEC_TELEMETRY=0`: `init` (fresh + idempotent re-run), `config profile`, `workset create`, `doctor` (happy + no-root), `context`, `new change`, `instructions proposal` | Live run | 2026-07-20 | verbatim prompt sequences, defaults, `[current]`/`(refresh)` labelling, pre-write diff, 31-tool picker, `Error:`/`Fix:` convention, non-interactive error text, three-tier state locations, npm package-name correction, pty window-size and telemetry operational traps |
| OpenSpec `src/prompts/searchable-multi-select.ts` (221 lines), `src/core/templates/workflows/verify-change.ts`, `src/core/artifact-graph/instruction-loader.ts`, `src/core/worksets.ts` | Repo | 2026-07 | hand-rolled `@inquirer/core` picker (copy-adaptable); proof the verify checklist takes no `rules` injection; worksets as machine-local, never-committed state |
| **get-shit-done clone** — `get-shit-done/templates/config.json`, `docs/CONFIGURATION.md` (1,111 lines), `sdk/src/{config,query/skills}.ts`, `agents/*.md` (33) | Repo | 2026-07-20 | the maximal config answer inside hex's exact architecture: ~90 keys / 16 groups, `parallelization.max_concurrent_agents`, `agent_skills` spawn-time injection, abstract model tiers with per-runtime resolution + 4-step precedence, unknown keys ignored |
| **spec-kitty clone** — `.kittify/config.yaml`, `src/specify_cli/core/agent_config.py`, `research/sample-agents.yaml` (367 lines, unreferenced), `src/doctrine/agent_profiles/`, `src/doctrine/model_task_routing/` | Repo | 2026-07-20 | the negative control: full agent-roster YAML designed and not shipped; `activated_*` flat opt-in lists (25/110/18); layered persona merge shipped→org→project; Pydantic `extra="forbid"` model-routing catalog with weights and `OverridePolicy` |
| OpenSpec `src/commands/doctor.ts`, `src/commands/context.ts` | Repo | 2026-07 | read-only health vs presentation split; `{message, fix}` finding shape; store metadata/remote/drift facts |
| OpenSpec `.github/workflows/ci.yml` | Repo | 2026-07 | self-gating: vitest ×3 platforms, tsc/lint, Nix path-filter, changesets — **no `openspec validate` job** |
| OpenSpec `openspec/changes/{add-change-stacking-awareness,add-tool-command-surface-capabilities,add-skill-cli-auto-approval,add-qa-smoke-harness}/`, `openspec/changes/IMPLEMENTATION_ORDER.md` | Repo | 2026-02 → 2026-07 | dogfooded in-flight artifact chains; optional-by-default shape; `dependsOn`/`provides`/`requires`/`touches`/`parent` as a *proposal*, not shipped |
| OpenSpec `docs/customization.md`, `docs/opsx.md`, `docs/supported-tools.md`, `docs/stores-beta/user-guide.md`, `docs/workflows.md`, `docs/existing-projects.md`, `docs/examples.md` | Docs | 2026-07 | the three customization levels; no agent concept; stores/multi-repo limits; `core` (5) vs expanded (11) workflow profiles and the two-command apply; monorepo = one root + domain folders; recipe-shaped onboarding |
| OpenSpec `skills/openspec-verify-change/SKILL.md`, `skills/openspec-sync-specs/SKILL.md`, `src/core/templates/workflows/archive-change.ts` | Repo | 2026-07 | single-agent verify (no panel); the one subagent call |
| https://code.claude.com/docs/en/sub-agents | Docs | 2026-07 | frontmatter field list (no `phase`), scope + model resolution chains |
| https://code.claude.com/docs/en/workflows | Docs | 2026-07 | phase-as-label in imperative JS, single up-front gate, no mid-run input |
| https://code.claude.com/docs/en/large-codebases | Docs | 2026 | "centralize into plugins when layering stops scaling" |
| https://docs.crewai.com/en/concepts/crews | Docs | 2026 | per-task `agent:` — the only declarative phase→agent precedent |
| https://copier.readthedocs.io/en/stable/{configuring,updating}/ | Docs | 2026 | `when:` conditional questions, answers file never hand-edited, update skips answered |
| https://nextjs.org/docs/app/api-reference/cli/create-next-app · https://vite.dev/guide/ · https://cargo-generate.github.io/cargo-generate/templates/template_defined_placeholders.html | Docs | 2026 | `--yes`/`--reset-preferences`, general→specific ordering, `-d key=value` |
| https://docs.gitlab.com/ci/yaml/includes/ · https://docs.astral.sh/ruff/configuration/ · https://eslint.org/blog/2025/03/flat-config-extends-define-config-global-ignores/ · https://editorconfig.org/ | Docs | 2025-2026 | array-merge traps, closest-wins vs cascade, upward search |
| https://github.com/redhat-developer/yaml-language-server · https://github.com/SchemaStore/schemastore/blob/master/CONTRIBUTING.md · https://zod.dev/json-schema | Docs | 2026 | the editor-completion path hex is declining, and why deriving a schema needs a code layer |
| GitHub Fission-AI/OpenSpec issues #662, #581, #697, #725 (bot-filed, quoting a Discord user) | Issues | 2026 | flat specs, configurable dir, multi-repo — all open |
| `hex/DESIGN.md`, `hex/hex-core/references/{protocol,memory,models,workers/*}.md`, `hex/hex-init/SKILL.md`, all four orchestrators' `SKILL.md` / `classify.md` / `overlays.md` / `tier-{low,medium,high}.md` @ 3745eac | Repo | 2026-07-20 | the current knob inventory *and* the mechanical spawn extraction — Tables 1–3, every count/role/model-class/tunable-number with file:line |
| `.agents/adrs/adr_0001*`, `.agents/research/hierarchical-execution-performance.md` | Repo | 2026-07-19 | class-name one-way-door; reviewer plateau + error-amplification figures |
