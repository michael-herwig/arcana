# Research: OpenSpec v1.6.0 — anatomy and head-to-head vs hex

## Metadata

**Date:** 2026-07-20
**Domain:** cli | ai-tooling
**Triggered by:** user request — align hex with openspec.dev; YAML config,
deep customization, multi-repo
**Expires:** 2027-01-31

Source of truth: `Fission-AI/OpenSpec` clone at v1.6.0 (npm
`@fission-ai/openspec@1.6.0`, published 2026-07-10). All bare paths below
(`src/…`, `docs/…`, `schemas/…`, `skills/…`) are relative to that clone.
Where the dossier feeding this artifact disagreed with the code, the code
wins and the correction is stated inline.

**Modality:** static source and doc reading, plus a live execution pass on
2026-07-20. The CLI **was run end-to-end** under a real pty — `init`
(fresh + idempotent re-run), `config profile`, `workset create`, `doctor`
(happy path and no-root error), `context`, `new change`, and
`instructions` — against throwaway projects in a scratchpad. Everything in
"Live CLI behaviour" below is transcript-observed; everything else remains
code-read. Two competitor repos (GSD, Spec Kitty) were cloned and read for
the architectural comparison that previous passes could not make. Adoption
figures (stars, forks, contributors, open issues, npm publish date) come
from `gh api` / npmjs.org calls made 2026-07-20 and are not re-verifiable
from the clones; treat them as a single dated snapshot.

**Install name:** the package is `@fission-ai/openspec`. Bare `openspec`
on npm is a defunct `0.0.0` placeholder — `npx openspec@1.6.0` fails with
`ETARGET`. Any hex doc or precedent note citing `npx openspec` is wrong.

## Direct Answer

OpenSpec is not a competitor to hex; it is the other half of the problem.
It is a deterministic TypeScript CLI that owns a **file format** (spec /
delta-spec markdown) plus a parser, validator, and merge engine — and it
delegates 100% of the thinking to an LLM through generated skill files. It
has **no orchestration at all**: one conditional, sequential subagent call
in the entire codebase (`src/core/templates/workflows/archive-change.ts:71`),
zero parallel agents, and its one "AI review" step
(`skills/openspec-verify-change/SKILL.md`) is a single agent walking a
three-item checklist — not a reviewer panel. hex is the inverse: no
runtime, no parser, no artifact grammar, but a real multi-agent execution
model (worktree work packages, DAG launch, staged reviewer panels, cross-
model adversary).

Three things are worth taking, in descending order of value:

1. **A validated delta-spec format** (`ADDED/MODIFIED/REMOVED/RENAMED`
   requirement sections, header-text-as-identity, apply-order RENAMED →
   REMOVED → MODIFIED → ADDED, validate-before-write) — hex has traceability
   IDs but no archive/fold-back-into-truth step at all.
2. **A YAML project-config surface** (`schema`, `context`, `rules`, `store`,
   `references`) injected as *separate prompt blocks*, never concatenated
   into the template — the cleanest answer found to "deep customization
   without touching shipped files".
3. **Stores** — a standalone planning repo referenced read-only by N code
   repos, with an explicit "no sync, ever" rule. Weaker than it sounds
   (beta, no cross-repo change application) but the right shape.

What to **reject**: its config *format choice* is not the lesson (hex.md is
prose because no parser reads it); its tool-count breadth (34 clients) is
a maintenance tax hex should not pay; and its review/verification model is
strictly weaker than hex's.

## What OpenSpec is

Mental model, verbatim from its own overview: "the entire idea in five
words: agree first, then build confidently" (`docs/overview.md:5`). Two
directories: `openspec/specs/` is truth, `openspec/changes/` is proposed
diffs. Five concepts, stated as the whole model on one screen
(`docs/overview.md:11-26`): specs are the truth; a change is one unit of
work; delta specs describe what's changing, not the whole world; artifacts
build on each other; archiving folds the change back into the truth.

Artifact chain (`docs/overview.md:20-23`):

```
proposal ──► specs ──► design ──► tasks ──► implement
   why       what       how       steps      do it
```

Dependencies are **"enablers, not gates"** (`docs/concepts.md:455`,
`docs/glossary.md:73`) — the order shows what becomes *possible* next, not
what is *required* next. Nothing locks; any artifact is editable at any
time. This is the single most repeated positioning phrase on every doc
surface.

On-disk layout created by `openspec init` (`docs/getting-started.md:54-68`):

```
openspec/
├── specs/              # source of truth
│   └── <domain>/spec.md
├── changes/            # one folder per change
│   └── <change-name>/
│       ├── proposal.md      # why and what
│       ├── design.md        # how
│       ├── tasks.md         # checklist
│       ├── .openspec.yaml   # change metadata (optional)
│       └── specs/<domain>/spec.md   # delta specs
│   └── archive/YYYY-MM-DD-<name>/
└── config.yaml         # project configuration (optional)
```

**Lifecycle vocabulary — what is and is not real.** Specs, changes, delta
specs, and archive are shipped and CLI-native. *Initiatives* and
*explorations* are **not** part of the shipped model: `docs/glossary.md`
has no "initiative" entry, and its only mention in the instructed doc set
is `docs/agent-contract.md:98`'s error code `initiative_option_removed`.
`/opsx:explore` is explicitly a chat-only thinking partner "creating no
artifacts and writing no code" (`docs/glossary.md:49`). The clone's own
`openspec/initiatives/` and `openspec/explorations/` trees are self-
dogfooded abandoned beta — their README says "Status: transition evidence /
beta history… not the active product roadmap"
(`openspec/initiatives/context-store-and-initiatives/README.md:1-9`). The
maintainers have since moved to an experimental `openspec/work/` (goal →
roadmap → slice → result) that is explicitly not CLI-native
(`openspec/work/README.md:81-83`). Do not port either vocabulary.

Slash-command lifecycle (core profile, `docs/getting-started.md:36-38`):
`/opsx:explore` → `/opsx:propose` → `/opsx:apply` → `/opsx:sync` →
`/opsx:archive`. Expanded profile splits propose into `/opsx:new` →
`/opsx:ff | /opsx:continue` → `/opsx:apply` → `/opsx:verify` →
`/opsx:archive`.

Archive is a mechanical 3-step act (`docs/concepts.md:544-548`): merge each
delta section into the matching main spec, move the folder to
`changes/archive/YYYY-MM-DD-<name>/`, preserve all artifacts for audit.

## Deterministic core vs prompt layer

This is the central architectural difference from hex, and OpenSpec states
it plainly: "The CLI is the engine. It knows the rules… The slash commands
are the steering wheel" (`docs/how-commands-work.md:66-68`).

**Real TypeScript (deterministic, no LLM anywhere):**

| Component | Where | What it actually does |
|---|---|---|
| CLI dispatch | `src/cli/index.ts:106-579` | ~20 Commander v14 command groups |
| Markdown parser | `src/core/parsers/markdown-parser.ts:81-219` | hand-rolled header-stack tree, fence-aware line mask, inline delta regex |
| Delta parser | `src/core/parsers/change-parser.ts:57-171` | recursive `specs/**/spec.md` discovery, FROM/TO rename pairs |
| Validator | `src/core/validation/validator.ts` (543 lines) | zod schemas + hand-written rules zod can't express |
| Merge engine | `src/core/specs-apply.ts` | delta → main spec fold, validate-before-write |
| Archiver | `src/core/archive.ts` (573 lines) | state machine, idempotent date prefix, EPERM/EXDEV copy fallback |
| Artifact graph | `src/core/artifact-graph/` | schema.yaml → DAG, cycle detection, `requires` resolution |
| Agent contract | `src/cli/index.ts:56-80` | "every `--json` failure leaves exactly one JSON document on stdout" |

There is **no LLM client in the dependency tree**: `package.json` deps are
`@inquirer/core`, `@inquirer/prompts`, `chalk`, `commander`, `cross-spawn`,
`fast-glob`, `ora`, `posthog-node`, `yaml`, `zod`. The only network clients
are PostHog telemetry and a `gh` shell-out for `openspec feedback`.

**ID allocation is not a thing.** `src/core/id.ts` (41 lines) is grammar
validation only — one kebab regex `/^[a-z0-9]+(?:-[a-z0-9]+)*$/u` shared by
store ids, change ids, and legacy initiative ids. Change identity is the
directory name; requirement identity is the `### Requirement: <Name>`
header text after `trim()`. Uniqueness is a filesystem existence check at
operation time (`src/core/archive.ts:500-513`), not a reserved-ID table.

**Delegated to the LLM:** every word of prose. `openspec instructions
<artifact> --json` is the hinge — it returns template + context + rules +
dependencies as XML-tagged blocks and the *agent* writes the file
(`src/commands/workflow/instructions.ts:172-289`). The guardrail is stated
in the skill itself: "context and rules are constraints for YOU, not
content for the file — Do NOT copy `<context>`, `<rules>`,
`<project_context>` blocks into the artifact"
(`skills/openspec-propose/SKILL.md:104-105`).

The consequence worth internalising for hex: OpenSpec's determinism buys
it exactly one thing hex cannot have today — *a merge that cannot silently
lose content*. And it partially threw that away (see finding 12).

## Live CLI behaviour (observed 2026-07-20)

Everything in this section is verbatim from captured transcripts, not
inferred from code.

**`init` is one continuous flow, not a wizard.** Animated welcome screen →
searchable multi-select tool picker → deterministic scaffold generation →
`config.yaml` write → success summary. There are **no numbered steps** in
`init`; the `[1/3]` pattern belongs to `workset create` (below). The
welcome screen states the deliverable and the next three commands before
asking anything:

```
Welcome to OpenSpec
This setup will configure:
  • Agent Skills for AI tools
  • /opsx:* slash commands
Quick start after setup:
  /opsx:new      Create a change
  /opsx:continue Next artifact
  /opsx:apply    Implement tasks
Press Enter to select tools...
```

The picker is a hand-rolled `searchable-multi-select.ts` (221 lines) built
on `@inquirer/core` primitives (`createPrompt`/`useState`/`useKeypress`),
not a library prompt: message line, `Selected:` chips, `Search: [type to
filter]`, an instruction line `↑↓ navigate • Space toggle • Backspace
remove • Enter confirm`, a paginated `◉/○` list with a `(page/total)`
indicator. With 31 selectable tools a flat checkbox would be unusable —
search-to-filter is what makes the list scale. That component is the
copy-adaptable pattern if hex ever picks from a long enumerable set.

**Idempotency splits scaffold from config.** Re-running `init` in a
configured project prints `OpenSpec configured: Claude Code
(pre-selected)` before prompting, pre-selects the configured tools
(labelled `(refresh)` rather than `(selected)`), reports `Refreshed:` not
`Created:`, and reports `Config: openspec/config.yaml (exists)` instead of
`(schema: spec-driven)`. Skill and command files are **unconditionally
regenerated**; `config.yaml` is **never rewritten once it exists**. That
split — regenerate deterministic scaffolding always, never clobber the one
user-owned file — is the clean rule for hex's own `/hex-init` re-audit.

**Every interactive path has a non-interactive escape hatch, named in the
failure message.** `init` takes `--tools <all|none|csv>`, `--force`,
`--profile <core|custom>`; non-interactive mode is entered on no-TTY, on
`--tools`, or on `CI` being set. Failing with none of them dumps the full
valid-value list inline so the fix is copy-pasteable without re-running
`--help`:

```
✖ Error: No tools detected and no --tools flag provided. Valid tools:
  amazon-q
  antigravity
  …31 ids…
Use --tools all, --tools none, or --tools claude,cursor,...
```

`config profile` refuses non-TTY the same way: "Interactive mode required.
Use `openspec config profile core` or set config via environment/flags."
The only confirm gate in `init` is scoped to a destructive-adjacent step —
"Upgrade and clean up legacy files?" (default true), and declining prints
"Run with `--force` to skip this prompt, or manually remove legacy files."
One well-placed confirm, not a battery of yes/no prompts.

**`config profile` shows current state, then a computed diff, then offers
to apply.** Three-question drill-down (what to configure → delivery mode,
current value suffixed `[current]` → checkbox workflow list), preceded by a
`Current profile settings` block that explains what each axis *means*, and
followed by an explicit pre-write diff:

```
Config changes:
  profile: core -> custom
  workflows: removed propose
? Apply changes to this project now? (Y/n)
```

Answering yes runs `openspec update` immediately rather than leaving the
user a follow-up command to remember. Show-state → show-diff → offer-to-
apply is the three-beat pattern worth copying wholesale for any hex gate
that mutates `hex.md`.

**`workset create` is the real `[1/3]` wizard**, and its step labels
explain *why* the step matters instead of naming a field:

```
[1/3] Name the workset
[2/3] Add member folders (the first one is the primary - sessions start there)
[3/3] Choose your tool
```

Defaults are aggressive: first folder path defaults to `.`, the label is
auto-derived from the basename and only prompted for on collision, the
add-another select defaults to `Finish`, and the tool list is populated
from what is actually on `PATH` (VS Code was auto-detected). Worksets are
**100 % local machine state** — `${XDG_DATA_HOME:-~/.local/share}/openspec/
worksets/worksets.yaml` plus a generated `.code-workspace`, never under the
project's `openspec/`, never in git (`src/core/worksets.ts:26-33`:
"purely local… nothing is ever written into a member folder"). Global
config lives beside it at `~/.config/openspec/config.json`. Two-tier
config — machine-wide defaults vs per-repo specifics — is a clean
separation hex can reuse if a personal-preference layer ever appears.

**The deterministic/agent boundary, demonstrated.** `openspec new change
add-rate-limiting` creates exactly one file:

```
openspec/changes/add-rate-limiting/.openspec.yaml
  schema: spec-driven
  created: 2026-07-20
```

No `proposal.md`, no `tasks.md`, no spec content. The CLI's job ends at
"create an addressable, timestamped, schema-tagged empty container".
Content generation is then handed to the agent by a *command*, not by
prompt text baked into a skill file — `openspec instructions proposal
--change add-rate-limiting` emits a structured block naming the exact
output path and the required shape:

```
<artifact id="proposal" change="add-rate-limiting" schema="spec-driven">
<task>Create the proposal artifact for change "add-rate-limiting".</task>
<output>Write to: …/changes/add-rate-limiting/proposal.md</output>
<instruction>… The Capabilities section is critical. It creates the
contract between proposal and specs phases. …</instruction>
<template><!-- Fill in the sections. --> ## Why …</template>
```

This is the single cleanest precedent in the CLI for hex: the deterministic
layer computes *where* and *what shape*, the model writes 100 % of the
prose, and the cross-artifact contract is stated inline in the instruction.

**Two operational notes, both cost real time to discover.** (1) Driving
these prompts over a raw pty **without setting a window size** makes the
inquirer renderer spin in an unbounded re-render loop — the first scripted
`init` emitted 57 MB of ANSI in 150 s and never completed; after
`ioctl(TIOCSWINSZ, 40×120)` the identical flow finished in 7.7 KB. This is
a property of the library class, not an OpenSpec bug, and applies to any
future scripted test of an interactive hex surface. (2) With telemetry left
on and egress blocked, the first `init` outlived a 60 s budget; the PostHog
client is configured `requestTimeout: 1000ms` and fails soft, but the
sandbox still stalled until `OPENSPEC_TELEMETRY=0` was exported. The CLI's
own first-run banner is the only hint ("Opt out: `OPENSPEC_TELEMETRY=0`").

## The YAML configuration surface

Three YAML surfaces plus one JSON, all zod-validated, **no JSON Schema
published**.

### 1. `openspec/config.yaml` — per-project (`src/core/project-config.ts:19-54`)

| Field | Type | Default | Effect |
|---|---|---|---|
| `schema` | string, min 1 | `spec-driven` (written by `init`) | which workflow schema drives the artifact graph |
| `context` | string, optional | unset | injected as `<project_context>` into every artifact instruction; **50 KB hard cap**, oversized content is warned and dropped, not an error (`:130`, `:151-200`) |
| `rules` | `Record<string, string[]>`, optional | unset | per-artifact-ID rules, injected as `<rules>`; keys validated against the union of artifact IDs across *all* schemas, unknown keys warn once (`:278`) |
| `store` | string, optional | unset | store id used as root when this `openspec/` is config-only; a fallback, never an override |
| `references` | string \| `{id, remote}` list | unset | **hand-parsed, deliberately absent from the zod schema** (`:42-45`); read-only cross-store spec index |

Verbatim, the clone's own config:

```yaml
schema: spec-driven

context: |
  Tech stack: TypeScript, Node.js (≥20.19.0), ESM modules
  Package manager: pnpm
  CLI framework: Commander.js
  ...
rules:
  specs:
    - Include scenarios for Windows path handling when dealing with file paths
    - Requirements involving paths must specify cross-platform behavior
  tasks:
    - Add Windows CI verification as a task when changes involve ...
```

`openspec init` writes only `schema: spec-driven` plus commented-out
examples — no live `context`/`rules` values (`src/core/config-prompts.ts`
`serializeConfig`, called from `src/core/init.ts:766`; `DEFAULT_SCHEMA` at
`:69`).

**How far `rules:` reaches — the verify checklist is *not* extensible.**
Settled from the prompt-assembly source, not from docs. Rules injection
lives entirely in `src/core/artifact-graph/instruction-loader.ts:304-336`:
it reads `projectConfig.rules[artifactId]`, validates every key against the
union of schema artifact IDs (`validateConfigRules`), and injects only a
non-empty list. So `rules:` can only ever reach a **schema-declared
artifact** — for `spec-driven` that is `proposal`, `specs`, `design`,
`tasks`. `verify` is not an artifact ID. The verify workflow's prompt is
built by `src/core/templates/workflows/verify-change.ts` (347 lines) as one
static template literal interpolating a single constant
(`STORE_SELECTION_GUIDANCE`, at `:16` and `:188`) — it never imports
`instruction-loader`, never touches `projectConfig`. **A user cannot
extend, reweight, or override the Completeness/Correctness/Coherence
checklist through `openspec/config.yaml`, or through anything else short of
forking the package.** That is a deliberate asymmetry worth naming: content
generation is configurable, the verification rubric is fixed. hex's
equivalent question — can a user add a reviewer perspective or a rubric
item without editing shipped files — currently has the same answer (no),
and OpenSpec is precedent that shipping it that way is defensible, not that
it is right.

### 2. `schemas/<name>/schema.yaml` — the workflow definition (`src/core/artifact-graph/types.ts:4-31`)

| Field | Type | Default | Effect |
|---|---|---|---|
| `name` | string, min 1 | — | schema id |
| `version` | positive int | — | schema version |
| `description` | string, optional | — | shown by `openspec schemas` |
| `artifacts[]` | array, min 1 | — | the artifact graph |
| `artifacts[].id` | string | — | artifact id (also the `rules:` key) |
| `artifacts[].generates` | string | — | output filename (`proposal.md`) |
| `artifacts[].template` | string | — | markdown template file |
| `artifacts[].instruction` | string, optional | — | per-artifact prompt block |
| `artifacts[].requires` | string[] | `[]` | DAG edges |
| `apply.requires` | string[], min 1 | — | what must exist before implementation |
| `apply.tracks` | string \| null, optional | — | checklist file (`tasks.md`) |
| `apply.instruction` | string, optional | — | implementation prompt |

```yaml
name: spec-driven
version: 1
description: Default OpenSpec workflow - proposal → specs → design → tasks
artifacts:
  - id: proposal
    generates: proposal.md
    template: proposal.md
    instruction: |
      Create the proposal document that establishes WHY this change is needed.
    requires: []
apply:
  requires: [tasks]
  tracks: tasks.md
```

Beyond zod, `parseSchema` runs three structural checks: no duplicate
artifact IDs, all `requires` targets exist, no cycles (DFS reporting the
full cycle path) — `src/core/artifact-graph/schema.ts`.

### 3. `.openspec.yaml` — per-change metadata (`src/core/change-metadata/schema.ts:24-33`)

`schema` (required), `created` (`^\d{4}-\d{2}-\d{2}$`, optional), `goal`,
`affected_areas[]`, `initiative{store,id}`. Real files are two lines:

```yaml
schema: spec-driven
created: 2026-01-20
```

### 4. `~/.config/openspec/config.json` — machine-level, **JSON not YAML**

`featureFlags`, `profile` (`core|custom`), `delivery`
(`both|skills|commands`), `workflows[]`, `defaultStore`
(`src/core/config-schema.ts:7-31`); read/written as JSON via
`src/core/global-config.ts:6-7`, edited only through `openspec config`.

### Resolution orders

Which schema a change uses (`src/utils/change-metadata.ts:166-198`,
matching `docs/customization.md` "Schema Resolution Order" exactly):
`--schema` flag → change's `.openspec.yaml` → project `config.yaml` →
hardcoded `'spec-driven'`.

Which *directory* a schema name loads from
(`src/core/artifact-graph/resolver.ts:63-91`): project
`openspec/schemas/<name>/` → user
`${XDG_DATA_HOME:-~/.local/share}/openspec/schemas/<name>/` → package
built-in.

### Prompt injection order (`src/commands/workflow/instructions.ts:211-274`)

`<project_context>` → referenced-store index → `<rules>` →
`<dependencies>` → `<output>` → `<instruction>` → `<template>` →
`<success_criteria>`. Each context/rules block carries
`<!-- Do NOT include this in your output. -->`. **Customization is
composed as separate blocks, never concatenated into the template text** —
this is the single best idea on this axis.

### Is a JSON Schema published? No.

Repo-wide grep finds `$schema` only in third-party tool configs:
`.coderabbit.yaml:1` (yaml-language-server modeline pointing at
CodeRabbit's schema) and `.changeset/config.json:2`. (The dossier claimed
`.coderabbit.yaml` was the *only* reference — that is wrong; there are
two, both unrelated to OpenSpec.) No `zodToJsonSchema` / `json-schema`
usage exists anywhere in `src/`. Editor autocompletion for
`openspec/config.yaml` or `schema.yaml` is **not provided**, despite zod
schemas being right there to derive one from.

The whole `openspec schema` family (`init|fork|validate|which`) that
authors custom workflows prints an experimental warning on every
invocation (`src/commands/schema.ts:293,296-297`).

## Artifact format and validation rules

**Spec structure.** A `spec.md` needs `## Purpose` and `## Requirements`;
missing either throws before zod runs
(`src/core/parsers/markdown-parser.ts:27-52`). A requirement is
`### Requirement: <Name>` (regex `/^###\s*Requirement:\s*(.+)\s*$/i`) whose
**body line** must contain `SHALL` or `MUST` as a whole word — header-only
placement gets its own error message: "must contain SHALL or MUST in the
requirement body, not only in the header. Move the SHALL/MUST statement to
the line immediately after the `### Requirement: …` header"
(`src/core/validation/validator.ts:512-528`). Each requirement needs ≥1
scenario, where a scenario is **any** level-4 header — deliberately loose,
with a source comment warning not to tighten it on one path only
(`src/core/parsers/requirement-text.ts:73-79`).

```markdown
### Requirement: Session Timeout
The system SHALL expire a session after 30 minutes of inactivity.

#### Scenario: Idle timeout
- GIVEN an authenticated session
- WHEN 30 minutes pass with no activity
- THEN the session is invalidated and the user must re-authenticate
```

All structural detection runs over a shared code-fence mask
(`buildCodeFenceMask`, `requirement-text.ts:19-65`) so documentation
examples inside a spec never parse as real structure.

**Delta operations.** Exactly four section titles, matched
case-insensitively against literal text — `## ADDED Requirements`,
`## MODIFIED Requirements`, `## REMOVED Requirements`,
`## RENAMED Requirements`. Effects on archive
(`docs/concepts.md:391-395`, plus RENAMED from
`schemas/spec-driven/schema.yaml:58-63`): appended / replaces / deleted /
FROM:-TO: pair. REMOVED accepts a bare reference (bullet or header, no
restated body). Unpaired FROM/TO is silently dropped — a real gap.

**Conflict matrix.** `MODIFIED ∩ REMOVED`, `MODIFIED ∩ ADDED`,
`ADDED ∩ REMOVED` all error; a RENAMED-FROM appearing in MODIFIED, or a
RENAMED-TO colliding with ADDED, also error — forcing MODIFIED to reference
the new name after a rename (`validator.ts:262-285`, duplicated at apply
time in `specs-apply.ts:163-193`).

**Numeric thresholds** (`src/core/schemas/*.ts`): `why` 50–1000 chars, max
10 deltas per change, ≥1 requirement per spec, ≥1 scenario per requirement.
The "at least one delta" failure gets a long remediation guide appended at
render time only (`GUIDE_NO_DELTAS`), keeping the zod message terse.

**Traceability.** There is **no ID scheme**. `normalizeRequirementName` is
`trim()` and nothing else (`requirement-blocks.ts:17-19`); the header text
*is* the key used to match deltas against the current spec during both
validate and archive. Capability identity is the directory path, nestable
(`platform/session-layout`). This is the load-bearing decision of the whole
format: renames must go through RENAMED or traceability silently breaks.

**Strict mode.** `--strict` promotes warnings to failures
(`valid = errors===0 && warnings===0` vs default `errors===0`,
`validator.ts:474-492`). Bulk validation runs at bounded concurrency
(`OPENSPEC_CONCURRENCY`, default 6). `openspec validate --json` is the only
payload carrying a `version` field — OpenSpec's own agent contract lists
this as a known inconsistency (`docs/agent-contract.md:136`).

**Archive apply order** is fixed: RENAMED → REMOVED → MODIFIED → ADDED,
preserving the *original* spec's requirement ordering and appending new
ADDED blocks at the end (`specs-apply.ts:244-356`). MODIFIED carries an
extra guard: it diffs incoming scenario names against current ones and
throws if the modified block would silently drop a scenario the live spec
has. ADDED and RENAMED-TO have an "early-sync" no-op path when content is
byte-identical. The whole rebuild is prepare-all-then-write-all, with every
rebuilt spec re-validated before any file is touched
(`archive.ts:420-489`).

**RFC 2119 asymmetry worth knowing:** the docs prescribe MUST/SHALL/SHOULD/
MAY semantics (`docs/writing-specs.md:29-37`), but the validator only ever
checks `SHALL|MUST`. SHOULD/MAY are authoring convention, never parsed.

### A real, in-flight artifact chain (dogfooded, unmerged)

The clone carries 16 active change folders under `openspec/changes/` — the
project planning its own next version in its own format. Read as evidence
of what the format looks like when it is not a doc example:

- **Shape is not uniform.** `add-change-stacking-awareness/` is the fullest:
  `proposal.md`, `tasks.md`, `.openspec.yaml`, and **four** delta specs
  (`specs/{openspec-conventions,cli-change,change-stacking-workflow,
  change-creation}/spec.md`). `add-qa-smoke-harness/` is `proposal.md` +
  one delta spec + `.openspec.yaml` — **no `tasks.md` at all**, and it still
  sits in the active tree. `add-skill-cli-auto-approval/` has proposal,
  tasks and two delta specs but **no `.openspec.yaml`**, so it falls back to
  the project schema. The artifact graph is genuinely optional-by-default;
  incompleteness is a normal resting state, not an error state.
- **`.openspec.yaml` is two lines in practice** — `schema: spec-driven` and
  `created: <date>`. The per-change override slot exists but is, in the
  project's own tree, never used to override anything.
- **`proposal.md` is `## Why` + `## What Changes`** — the Why is a
  three-bullet problem statement, the What Changes is numbered sub-sections
  each naming a CLI surface. `tasks.md` is `## <N>. <Group>` headings over
  `- [ ] N.M` checkboxes, with test tasks written as their own checkbox
  lines beside the implementation task (e.g. `2.5 Add tests for cycle,
  missing dependency, overlap warning …`) — TDD is a *convention in the
  task list*, not a phase the tool enforces.
- **Delta specs read exactly as the validator demands**: `## ADDED
  Requirements` → `### Requirement: <Name>` → body line with SHALL →
  `#### Scenario:` with GIVEN/WHEN/THEN bullets. Determinism language
  ("SHALL break ties lexicographically by change ID", "repeated runs over
  the same input SHALL return the same order") is carried in scenarios, not
  in prose.
- **`openspec/changes/IMPLEMENTATION_ORDER.md` is a hand-written file**, not
  a generated artifact: a phase list, an ASCII dependency graph, shared-code
  and file dependencies, and a "Parallel Work Opportunities" section. It is
  stale (it sequences `add-zod-validation` → `add-change-commands` →
  `add-spec-commands`, all long archived) and nothing validates it. The
  in-flight `add-change-stacking-awareness` proposal exists precisely to
  replace it with machine-readable metadata: `dependsOn` (the ordering
  source of truth), `provides`/`requires` (capability contracts that
  explicitly *do not* create implicit edges), `touches` (advisory overlap
  warning), `parent` (split work), plus `openspec change graph` /
  `change next` / `change split`. **This is OpenSpec independently arriving
  at hex's WP `Depends-on` / `Scope` columns** — and it is still a proposal,
  not shipped code, in v1.6.0.

**Worked example, with sizes.** `add-change-stacking-awareness/` measured
line-by-line (`wc -l`, 2026-07-20) — the fullest active change in the tree,
and it still has **no `design.md`**:

| File | Lines | Contents |
|---|---|---|
| `proposal.md` | 93 | Why / What Changes (5 sub-sections) / Capabilities (new + modified) / Impact |
| `tasks.md` | 39 | 6 numbered sections, ~19 checkboxes |
| `specs/change-stacking-workflow/spec.md` | 65 | 3 ADDED Requirements, 7 Scenarios |
| `specs/openspec-conventions/spec.md` | 29 | 1 ADDED Requirement, 4 Scenarios |
| `specs/cli-change/spec.md` | 27 | 2 ADDED Requirements, 3 Scenarios |
| `specs/change-creation/spec.md` | 15 | 1 ADDED Requirement, 2 Scenarios |
| `.openspec.yaml` | 2 | `schema: spec-driven` / `created: 2026-02-21` |
| `design.md` | — | **absent** |
| **total** | **270** | 4 capabilities touched |

Two calibration facts for hex fall straight out of that. First, a change
touching four capabilities lands in **~270 lines total** — delta specs stay
15–65 lines each because they restate only what moves. Second, `design.md`
is optional *in practice*, not merely in the schema: the project's most
structurally ambitious in-flight change skipped it. The closing section of
`tasks.md` is a `## 6. Verification` block whose two checkboxes are "run
targeted tests for change parsing, validation, and CLI commands" then "run
full test suite (`pnpm test`) and resolve regressions" — targeted-then-full
written as a task, never a tool-enforced gate.

**Change stacking already exists informally.** Before that proposal ships,
two mechanisms already cover part of it: `docs/workflows.md` documents a
*Parallel Changes* pattern, and bulk-archive detects when several changes
touch the same specs and resolves the overlap **agentically at archive
time** — its worked example has two changes both touching `specs/ui/`,
merged in chronological order. That is runtime conflict detection with no
persisted dependency graph, which is precisely the gap the proposal's Why
names: no machine-readable way to express sequencing, dependencies, or
expected merge order. hex's WP `Depends-on` column is the persisted version
OpenSpec is still writing a proposal about.

### How OpenSpec gates its own changes (CI)

`.github/workflows/ci.yml` is a conventional Node pipeline and is worth
noting mainly for what is *absent*: there is **no `openspec validate` job**.
The gates are `test_matrix` (vitest on ubuntu/macos/windows, `VITEST_MAX_WORKERS`
4/4/2, 15-min timeout, `fail-fast: false`), `lint` (`tsc --noEmit`, `pnpm
lint`, plus an explicit existence check on `dist/cli/index.js`),
`nix-flake-validate` (path-filtered via `dorny/paths-filter`, builds the
flake and runs the binary), and `validate-changesets` (only when the PR
touches `.changeset/*.md`). Two identical `required-checks-*` aggregator jobs
fan the results into a single required status. So the spec artifacts that
the whole product is about are **not** CI-enforced against the code — which
is the mechanical root of the "spec drift" criticism below, not merely a
cultural one.

Sharper than that: `docs/troubleshooting.md` **recommends** `openspec
validate --all --strict` as the CI invocation, and `ci.yml` does not run
it. OpenSpec does not dogfood its own validator in its own pipeline. Any
hex artifact-lint rule should assume the same failure mode by default — a
validator nobody wires into CI converges on a validator nobody runs.

### Diagnostics surface

Two read-only commands answer "is my setup coherent":
`openspec doctor` (`src/commands/doctor.ts`, 219 lines) is the *health*
surface — root-scoped relationship health, explicitly "never clones, syncs,
or repairs", reporting `{message, fix}` pairs per finding and store facts
(metadata present/valid, canonical remote vs `git origin`, tracking drift)
for store-backed roots. `openspec context` (`src/commands/context.ts`, 212
lines) is the *presentation* surface over the same Phase-3 relationship
data — the working set as an agent brief (`--json`), a human listing, or an
editor workspace (`--code-workspace`), with the workspace file as its only
possible write. The split is stated in-source: "doctor is the health
surface", context is "presentation over the Phase 3 relationship data". A
`{message, fix}` pair per finding is the pattern hex's announce block should
copy — every diagnostic ships its remediation inline.

Observed output confirms the split and exposes a naming problem. On a
normal single-repo project with no store and no `references:`, `doctor` is
near-empty:

```
Doctor

Root
  Location: …/live6
  OpenSpec root: ok

References
  (none declared)
```

`--json` gives `{"root":{…,"healthy":true,"status":[]},"store":null,
"references":[],"status":[]}`. **`doctor` is not a project-health linter** —
it answers only "are the roots this work relates to available on this
machine?", so on the common case it has nothing to say. A hex command named
`doctor` would inherit that expectation mismatch; either make it broader or
name it after what it checks. Outside any root, `doctor` and `context` fail
identically and exit 1, in the `Error:`/`Fix:` two-line shape the whole
codebase uses:

```
Error: No OpenSpec root found from the current directory.
Fix: Run openspec init to create a root here.
```

`docs/troubleshooting.md` extends the same discipline to prose: each entry
is symptom → one-sentence likely cause → an **ordered, fastest-to-check-
first** fix list (the "commands don't show up" entry is a six-step ladder
starting at "you're in the terminal, not the chat"). Ordering by check cost
rather than by likelihood is the detail worth copying.

## Tool integration model

Injection is **generated files only** — no marker-block editing of
CLAUDE.md/AGENTS.md. The `<!-- OPENSPEC:START -->` markers survive solely
in `src/core/legacy-cleanup.ts` to *strip* old blocks during migration, and
the file itself notes config files are never deleted (`:690`).

- **Registry.** `AI_TOOLS` in `src/core/config.ts:22-58` holds **34 entries
  with `available: true`** plus one `agents` pseudo-entry
  (`available: false`, no `skillsDir`) = 35 array entries. (The dossier said
  "33 + 1"; counted programmatically it is 34 + 1.) Each entry carries a
  `skillsDir` and optional `detectionPaths`/`setupNote`.
- **Adapters.** `CommandAdapterRegistry` statically registers **28**
  `ToolCommandAdapter{getFilePath, formatFile}` implementations
  (`src/core/command-generation/registry.ts:44-72`). The arithmetic checks
  out: 34 available tools − 6 documented skills-only tools (codex,
  codeartsagent, forgecode, hermes, kimi, vibe) = 28. Notably, only
  **codex** is carved out by name in code as `skills-invocable`
  (`src/core/command-surface.ts:6-15`); the other five reach the same
  outcome by simply being absent from the registry.
- **Claude Code specifically:** skills at
  `.claude/skills/openspec-*/SKILL.md`, commands at
  `.claude/commands/opsx/<id>.md`.
- **Syntax fragmentation is documented, not fought**
  (`docs/how-commands-work.md:76-88`): `/opsx:propose` (Claude Code),
  `/opsx-propose` (Cursor, Windsurf, Copilot IDE, Trae, Oh My Pi),
  `/openspec-propose` (CodeArts), `/skill:openspec-propose` (Kimi).
- **Three orthogonal axes:** *profile* (core = 5 workflows, expanded = 11)
  × *delivery* (`both|skills|commands`) × *per-tool* AI_TOOLS entry. Clean
  separation of "which workflows", "how delivered", "to which client"
  (`src/core/global-config.ts:11-12`, `src/core/command-surface.ts:1-32`).
- **SKILL.md frontmatter** is a fixed 6-field shape with
  `allowed-tools: Bash(openspec:*)` — framed in-source as pre-approval,
  not restriction, since non-honoring tools ignore the field
  (`src/core/shared/allowed-tools.ts:1-11`).

**Upgrade path.** Every generated SKILL.md embeds
`metadata.generatedBy: "<npm package version>"`. `openspec update` reads
the first installed skill per tool, regexes out that string, and sets
`needsUpdate = configured && (generatedBy === null || generatedBy !==
currentVersion)` (`src/core/shared/tool-detection.ts:130-200`). One
template source, N generated artifacts, drift caught by a parity test —
the repo-root `skills/` mirror for skills.sh is regenerated by
`scripts/generate-skillssh.mjs` and `skillssh-parity.test.ts` fails on
drift (`skills/README.md:9-19`).

**Multi-repo: Stores (beta, shipped v1.5.0, 2026-06-28).** A store is an
ordinary git repo holding a normal `openspec/` tree plus
`.openspec-store/store.yaml`. Root resolution
(`docs/stores-beta/user-guide.md:300-316`): `--store <id>` → nearest local
`openspec/` walking up → `store:` pointer in config.yaml → global
`defaultStore` → error with a selection hint. `references:` gives read-only
cross-store spec discovery. Two hard limits stated as design, not bugs:
"**No sync, ever — by design.** OpenSpec never clones, pulls, or pushes"
and one registered checkout per store id per machine (`:325-329`).
`docs/existing-projects.md` routes every multi-repo question straight here
("for work spanning multiple repositories… planning lives in its own
standalone repo that any code repo can reference") while flagging it beta
with evolving commands and state — so the brownfield doc and the stores doc
agree that this is the only answer on offer, and that it is provisional.

What Stores does **not** solve, per OpenSpec's own open issues: hierarchical
/ nested spec organisation (#662, #594), configurable `openspec/` directory
name (#581, #697), and a change spanning multiple code repos (#725). The
project's own dogfooded planning docs still list "How should monorepos map
capabilities, folders, and repo-local changes?" as an open question
(`openspec/initiatives/context-store-and-initiatives/questions.md:11`).

## Head-to-head vs hex

| Dimension | OpenSpec v1.6.0 | hex (current main) | Who's better |
|---|---|---|---|
| **Config format** | zod-validated YAML (`config.yaml`, `schema.yaml`, `.openspec.yaml`) + XDG JSON for machine settings; no JSON Schema published | prose markdown `hex.md › Preferences`, written only by `/hex-init` with consent; per-run CLI flags; no parser reads it | **OpenSpec** on validation & error messages; **hex** on zero-parser cost. Different problems |
| **Validation** | real parser + 543-line rule engine; fence-aware; precise, actionable error strings; `--strict` promotes warnings | no artifact validator at all; correctness enforced by reviewer workers reading prose | **OpenSpec**, decisively |
| **Artifact lifecycle** | proposal → specs → design → tasks → implement → archive; "enablers, not gates" | plan → execute → review; Status block `planning→plan-approved→executing→review→done` (`hex-plan/SKILL.md:211-220`) | Tie — same shape, hex adds explicit state |
| **Archiving / fold-back** | deterministic delta merge into `specs/`, date-stamped move, validate-before-write, prepare-all/write-all atomicity | **absent** — no fold-back step; a merged plan just sits at `State: done` | **OpenSpec** — this is hex's largest structural gap |
| **Traceability** | header-text-as-identity, no IDs; renames must go through RENAMED | `C-001…` contracts / `S-001…` scenarios, assigned once, never renumbered, coverage checked mechanically at 3 gates (`protocol.md:320-340`) | **hex** — synthetic IDs survive renames; OpenSpec's don't |
| **Parallelism** | none. Every "parallel" mention in docs means humans running separate change folders, or `--concurrency` on validation | file-disjoint work packages, one worktree per WP, dependency-ready DAG launch, serialized topological merge, cap 8 concurrent workers | **hex**, no contest |
| **Subagents** | exactly one call site: an optional `Task(subagent_type: "general-purpose")` in archive-change's sync step (`src/core/templates/workflows/archive-change.ts:71`) | 9 roles, coordinator fan-out one level deep, hex-enforced depth cap, per-role model matrix | **hex** |
| **Review model** | human reads proposal → deltas → code diff (`docs/team-workflow.md:41-47`); `/opsx:verify` is **one agent** scoring Completeness/Correctness/Coherence and never blocks archive | staged reviewer panel (spec, quality, security, performance, docs), bounded Review-Fix Loop, cross-model adversary gate | **hex** |
| **Tiering** | two rigor levels for specs only — Lite (default) vs Full for cross-team/API/migration/security (`docs/concepts.md:159-169`); no tiering of the *process* | low/medium/high + auto classifier scaling worker counts, research axes, review breadth, adversary | **hex** |
| **Memory / context** | `context:` (50 KB cap) + per-artifact `rules:` injected as discrete prompt blocks; `project.md` deliberately not auto-migrated | two-layer model: project context (CLAUDE.md) authoritative, `hex.md` holds pointers/preferences/working memory; pointers-not-copies + verify-on-consumption | **hex** on staleness discipline; **OpenSpec** on the per-artifact `rules:` granularity |
| **Multi-client portability** | 34 clients, 28 command adapters, per-client syntax documented not normalized | Claude Code only in practice; markdown skills are portable in principle | **OpenSpec** on reach; **hex** on maintenance cost avoided |
| **Multi-repo** | Stores beta: shared planning repo, read-only `references:`, explicit "no sync, ever"; nested specs / cross-repo change application are open issues | none; `.agents/` is per-repo; distribution via grim/OCI | **OpenSpec**, but only barely — its own issue tracker says the hard part is unsolved |
| **Distribution / install** | `npm i -g @fission-ai/openspec` then `openspec init`; a runtime binary must exist on the machine | `grim` pull from an OCI registry; markdown only, client is the runtime | **hex** — no runtime to install or version-skew |
| **Upgrade path** | `generatedBy` version stamp per generated file + `openspec update` diff; legacy marker-block cleanup that never deletes user files | `/hex-init` re-audit re-verifies pointers and index lines, reports drift, fixes with consent; copy-if-absent templates | Tie — same idea, different mechanism |
| **Cost profile** | one agent, sequential, ~57.7k tokens on a *third-party, unreproduced* comparison task (see caveat below); a dev.to case study found plain `instructions.md` cheaper still | up to 8 concurrent workers with a deep-reasoning tier — structurally far more expensive per run, bounded by tier | **OpenSpec** on raw cost; hex buys review depth with it |

> **Caveat on every number in the Cost profile row, restated here so a skim
> cannot miss it:** the ~57.7k vs ~120.9k token figures and the
> 12min / 90min / 5.5h task-time figures are third-party single-run blog
> measurements. They were not reproduced, the task was not held constant
> across tools by anyone we can verify, and no variance is reported. Treat
> them as *directional only* — they establish an order of magnitude, never
> a ranking. Nothing in this dossier's recommendations depends on them.

Where OpenSpec is *genuinely* better and hex should not pretend otherwise:
deterministic artifact merge, real validation with actionable errors, a
published archive step, and multi-client reach. Where hex is better:
everything about *execution* — parallelism, review depth, model routing,
traceability that survives renames, and no runtime dependency.

## Adoption and reception

Numbers verified via GitHub API on 2026-07-20 (star counts move daily):

| Metric | Value |
|---|---|
| Repo created | 2025-08-05 |
| Stars / forks / watchers | 61,688 / 4,276 / 268 |
| Open issues | 444 (63 labelled `bug` open) |
| Contributors | 74 |
| Releases | 41, v0.1.0 (2025-09-06) → v1.6.0 (2026-07-10) ≈ one per 8–9 days |
| License / language | MIT / TypeScript 98.7% |

Landscape position — **every star count in this paragraph is a single
`gh api` snapshot taken 2026-07-20, the same timestamp as the table above;
none is a trend line**: **trending** — OpenSpec and GSD (`gsd-build/
get-shit-done`, 64,779 stars @ 2026-07-20, created 2025-12-14, i.e. a
*steeper* curve) lead the SDD niche; **established** — GitHub Spec Kit (the
1:1 analog, greenfield-first), AWS Kiro (IDE lock-in); **emerging** —
Tessl's spec registry, Spec Kitty (1,429 stars @ 2026-07-20 — worktrees +
topological auto-merge + kanban, verified in source below, i.e. exactly
hex's territory);
**declining** — nothing measurable in-niche yet, though BMAD-METHOD's
reported $800–2,000/month API cost at scale is the cautionary end of the
spectrum.

### GSD and Spec Kitty, actually read

The previous pass could only cite star counts. Both repos have now been
cloned and read. The headline: **these two, not OpenSpec, are hex's real
architectural neighbours** — OpenSpec owns a file format and delegates all
thinking; GSD and Spec Kitty both ship agent rosters, model routing, and
(Spec Kitty) worktree parallelism, which is hex's exact problem space.

| Axis | GSD (`gsd-build/get-shit-done`) | Spec Kitty (`Priivacy-ai/spec-kitty`) | hex |
|---|---|---|---|
| Runtime | npm `get-shit-done-cc` v1.50.0-canary.0; markdown workflows + a TypeScript `gsd-sdk`/`gsd-tools` CLI + 13 hook scripts | `pipx install spec-kitty-cli`; ~315 k lines of Python under `src/` | markdown only, client is the runtime |
| Prompt surface | 33 agent definitions (`agents/gsd-*.md`, 4–48 KB each), ~65 slash commands under `commands/gsd/`, workflow files up to 85 KB (`execute-phase.md`) | slash commands + skills, plus a `charter`/`doctrine` governance corpus (`src/doctrine/{directives,paradigms,procedures,tactics}`) | 4 orchestrators, 9 worker roles, thin dispatchers + per-tier phase files |
| Config carrier | `.planning/config.json` — a real machine-written JSON settings file | `.kittify/config.yaml` + `.kittify/charter/charter.yaml` + `activated_directives:` list | `hex.md` prose, no parser |
| Model routing | **five named profiles** (`quality`/`balanced`/`budget`/`adaptive`/`inherit`) mapping each of 12 agents to opus/sonnet/haiku, plus a coarse per-phase-type `models` key (`references/model-profiles.md`) | `src/doctrine/model_task_routing/` (catalog + evaluator + loader) | two capability classes (fast-balanced, deep-reasoning), never literal model names |
| Parallelism | config-driven: `parallelization.{enabled, plan_level, task_level, max_concurrent_agents: 3, min_plans_for_parallel: 2}` | git worktrees under `.worktrees/`, `lanes/worktree_allocator.py` bases a dependent lane on its dependency's *approved* tip; `merge/ordering.py` does a real `topological_sort`; `merge/{preflight,conflict_classifier,conflict_resolver,executor}.py` | file-disjoint WPs, one worktree each, DAG launch, serialized topological merge, cap 8 |
| Gates | `gates.{confirm_project, confirm_phases, confirm_roadmap, confirm_breakdown, confirm_plan, execute_next_plan, issues_review, confirm_transition}` — every gate individually toggleable | lifecycle lanes `planned → in_progress → for_review → approved → done`, review/accept/merge/retrospective gates | tier-scaled phase gates, not individually toggleable |
| Visibility | statusline hook (`hooks/gsd-statusline.js`, 22 KB), context monitor, update banner | `spec-kitty dashboard` — a real local kanban server (`src/specify_cli/dashboard/{server,scanner,handlers,static}`) | announce blocks in the transcript |

Three specific corrections and lessons:

1. **The 64,779-star GSD repo is archived.** The clone's `main` HEAD is
   2026-05-31 and its `README.md` is a redirect stub: "This repository is
   no longer the active home for GSD development… continues as **GSD Core**
   in `open-gsd/gsd-core`". The star count is real but attaches to a
   redirected repo; the "steeper curve than OpenSpec" reading in the
   paragraph above should not be treated as a live signal without checking
   the successor repo.
2. **Spec Kitty's "worktrees + auto-merge" is code, not copy.** The
   previous pass hedged that as marketing. It is not: `merge/ordering.py`
   topologically sorts work packages, `worktree_allocator.py` reasons about
   dependency lanes whose approval landed late, and `merge/` carries a
   dedicated conflict classifier and resolver. Spec Kitty implements
   deterministically, in Python, roughly the merge discipline hex states as
   prose rules for an agent to follow. It is the closest thing to a prior
   art for hex's execution model that this research has found, and the
   right place to look next for edge cases hex's prose does not cover
   (late-approved dependencies, stale lane bases, push preflight).
3. **GSD is the precedent for user-tunable orchestration.** Every number
   hex hardcodes — concurrency cap, whether a reviewer runs, which model a
   role gets — GSD exposes as a config key with a default. `"verifier":
   true`, `"plan_check": true`, `"security_block_on": "high"`,
   `"max_concurrent_agents": 3`, `"models": {<phase-type>: …}`. Whether hex
   *should* is a separate question (`DESIGN.md` argues no parser, and a
   config surface that big is its own maintenance tax), but "nobody ships
   tunable agent rosters" is no longer available as an argument.

Neither repo was executed, and neither adoption number was re-measured
after cloning; both readings are static-source only.

Praised: delta-tracking scope control, zero API keys / no MCP, brownfield-
first onboarding, small output footprint (~250 lines vs Spec Kit's ~800 for
a comparable task). The brownfield claim is backed in-repo by
`docs/existing-projects.md`, which is explicitly delta-first ("Resist the
urge to back-fill everything… Writing specs for code you aren't changing
feels productive and usually isn't"), tells the reader to create a domain
folder only when their first change in that area needs one, and gives a
guided `onboard` path as the optional alternative. `docs/examples.md` is
seven recipes over the same loop (small feature, bug fix, explore-first,
two changes at once, no-behavior-change refactor, expanded step-by-step,
learn-the-loop) — the onboarding surface is recipe-shaped, not
reference-shaped.

Criticised, in order of how often it recurs:

1. **Spec drift.** Sync is advisory, never enforced; specs and code diverge.
   A practitioner quoted as abandoning it entirely: "maintaining the main
   specs is not worth it" (codemyspec.com/blog/openspec-explained). An
   often-repeated HN quote about drift **could not be located in the two
   most relevant threads and is therefore discarded as evidence, not merely
   caveated** — it is listed here only so a later reader does not go
   looking for it again. The claim stands without it: sync is advisory in
   the shipped skill, and CI does not run `openspec validate` (see above),
   which is verifiable in-repo.
2. **Validation is structural, not behavioural.** Scenarios are encouraged,
   not required; a change can archive with zero scenarios. Open issues #880
   ("`/opsx:validate` to check code against the living specs") and #381
   ("lightweight verification step") ask for exactly this.
3. **`/opsx:` naming friction** — issue #813 "is hard to remember and not
   intuitive" (13 reactions); #1129 (Codex still generating deprecated
   `/opsx:*` flows, 13 reactions); #863 "`/opsx:archive` does not invoke
   `openspec archive` CLI, unlike official docs" (17 reactions, open).
4. **Ceremony doesn't always pay.** A dev.to case study concluded "a simple
   Instructions.md approach was faster, cheaper, and easier to iterate on."
   Single anecdote, not a benchmark.

Top-reacted open issues are ecosystem asks, not workflow rejection: #780
distribute as a Superpowers skill pack (44), #662 hierarchical specs (41),
#689 standard `.agent/skills` folder (27), #1104 generic `.agents`
installer (23), #697 custom directory path (20).

Marketing tool counts are internally inconsistent across OpenSpec's own
site (FAQ "25+", supported-tools "40+" while listing 34 IDs, homepage
"30+"). Cite the 34-ID list, never a round number.

## Key findings

1. OpenSpec's CLI contains no LLM call of any kind; content generation is
   entirely delegated to generated SKILL.md files that shell out to
   `openspec instructions <artifact> --json`
   (`src/commands/workflow/instructions.ts:172-289`).
2. The prompt-block injection order is fixed and each customization block
   is separate, never concatenated into the template:
   `<project_context>` → references → `<rules>` → `<dependencies>` →
   `<output>` → `<instruction>` → `<template>` → `<success_criteria>`
   (`instructions.ts:211-274`).
3. `openspec/config.yaml` has exactly four zod-validated fields (`schema`,
   `context`, `rules`, `store`) plus one deliberately hand-parsed field
   (`references`), with a source comment explaining that "a schema entry
   nothing parses would only drift from the real behavior"
   (`src/core/project-config.ts:19-54`).
4. `context:` is capped at 50 KB and enforced by **warn-and-drop**, not
   error (`project-config.ts:130`, `:151-200`) — resilient parse over
   strict failure, consistently applied (unknown `rules` keys warn once,
   `:278`).
5. No JSON Schema or `yaml-language-server` modeline is published for any
   OpenSpec-owned YAML file. The only `$schema` occurrences repo-wide are
   third-party: `.coderabbit.yaml:1` and `.changeset/config.json:2`.
   Correction to the dossier, which claimed only one.
6. Schema resolution is a clean 4-step precedence — CLI flag → per-change
   metadata → project config → hardcoded default — and the docs and the
   implementation agree exactly (`src/utils/change-metadata.ts:166-198` vs
   `docs/customization.md` "Schema Resolution Order").
7. Requirement identity is the trimmed header text, full stop
   (`src/core/parsers/requirement-blocks.ts:17-19`). No numeric or UUID IDs
   exist anywhere in the format. Capability identity is the directory path
   and may nest arbitrarily.
8. The delta grammar is four literal section titles with a full cross-
   section conflict matrix (`validator.ts:262-285`) and a fixed apply order
   RENAMED → REMOVED → MODIFIED → ADDED (`specs-apply.ts:244-356`).
9. Archive validates every rebuilt spec before writing any of them, with an
   explicit source comment that "a late validation failure really does
   leave all targets unchanged" (`archive.ts:420-465`).
10. MODIFIED carries a stale-base guard: it throws if the live spec has a
    scenario the modified block would silently drop
    (`specs-apply.ts:291-312`, `:410-443`).
11. Errors are engineered as UX. "No delta sections found. Add headers such
    as `## ADDED Requirements`…" is distinct from "Delta sections {list}
    were found, but no requirement entries parsed…"
    (`validator.ts:291-304`); header-only SHALL gets its own message
    (`:512-528`).
12. **The deterministic merge was partly abandoned.** A root-level design
    doc `openspec-parallel-merge-plan.md` diagnoses replace-only semantics
    losing scenarios on parallel archives and proposes fingerprints +
    diff3 + scenario IDs. None of Phase 0/1/3 exists in `src/` (no hits for
    `fingerprint`, `meta.json`, `change sync`). What shipped instead is
    **LLM-judgment merging** in `skills/openspec-sync-specs/SKILL.md:119-124`
    ("Key Principle: Intelligent Merging… the delta represents intent, not
    a wholesale replacement"). The skill path delegates to the agent; the
    raw `openspec archive` CLI path still calls `buildUpdatedSpec` directly.
13. **No reviewer panel exists.** `skills/openspec-verify-change/SKILL.md`
    instructs one agent to fill in Completeness / Correctness / Coherence
    itself — grep for `Task tool` / `subagent` / `Skill tool` returns zero
    hits there, and likewise in `openspec-bulk-archive-change` and
    `openspec-sync-specs`. `/opsx:verify` never blocks archive
    (`docs/reviewing-changes.md:100-121`).
14. The entire codebase's subagent usage is one optional, sequential
    `Task(subagent_type: "general-purpose")` in archive-change
    (`src/core/templates/workflows/archive-change.ts:71,189`). It is emitted
    identically to all 34 clients regardless of whether they have a Task
    tool.
15. **Agent customization does not exist.** `docs/customization.md` (356
    lines) offers exactly three levels — project config, custom schemas,
    global overrides — all of which customize workflow/schema/prompt
    content. There is no OpenSpec-native concept of a configurable agent,
    reviewer roster, or model choice. The word "subagent" appears in that
    doc once, at line 348, describing a third-party community bridge to
    obra/superpowers.
16. Tool registry: 34 `available: true` entries + one `agents` pseudo-entry
    (`src/core/config.ts:22-58`); 28 registered command adapters
    (`registry.ts:44-72`); 34 − 6 skills-only = 28. Corrects the dossier's
    "33 tools" and "26 adapters" — both simple counting errors, not a stale
    snapshot.
17. Only `codex` is special-cased by name in `command-surface.ts:6-15` as
    skills-invocable; the other five skills-only tools reach the same
    outcome implicitly by being absent from the adapter registry.
18. Upgrade detection is a version string embedded in each generated file
    (`generatedBy`) compared against `package.json`
    (`tool-detection.ts:130-200`) — a pattern hex can copy verbatim for
    detecting drift between an installed skill copy and arcana's source.
19. Git is entirely out of scope: "OpenSpec reads and writes plain Markdown
    under `openspec/`. It never commits, branches, pushes, or pulls"
    (`docs/team-workflow.md:7-13`). Branch-per-change is convention only.
20. Stores explicitly refuse to sync (`docs/stores-beta/user-guide.md:327-329`)
    and permit one checkout per store id per machine. Cross-repo *change
    application* is unsolved and tracked as open issue #725 — which, note,
    was filed by the bot account `alfred-openspec` quoting a Discord user
    (Martin.KvL, rio.cloud), not authored by that user.
21. The `openspec view` "interactive dashboard" in the docs is a one-shot
    `console.log` render with no keypress loop (`src/core/view.ts:1-80` vs
    `docs/cli.md:420-429`) — an example of OpenSpec's own docs drifting from
    its code.
22. **The verify rubric is not user-extensible, proven from prompt
    assembly.** `config.yaml` `rules:` can only reach schema-declared
    artifact IDs (`instruction-loader.ts:304-336`); `verify-change.ts`
    (347 lines) is one static template literal interpolating only
    `STORE_SELECTION_GUIDANCE` and never imports that loader. Content
    generation is configurable; the verification rubric is fixed.
23. `init` regenerates skill/command files unconditionally but **never
    rewrites `config.yaml` once it exists** (observed: `Config:
    openspec/config.yaml (exists)`, `Refreshed:` vs `Created:`) — the clean
    split between owned scaffolding and user-owned config.
24. Every interactive path names its non-interactive escape hatch **in the
    failure message**, and the no-tools error dumps all 31 valid ids inline
    rather than referring the user to `--help` (observed).
25. `config profile` shows current state → computes and prints a diff →
    offers to apply the consequence immediately (`openspec update`) rather
    than leaving a follow-up command (observed).
26. `openspec new change <name>` writes exactly one 2-line `.openspec.yaml`
    and no content; `openspec instructions <artifact> --change <id>` is the
    handoff, emitting `<task>/<output>/<instruction>/<template>` with the
    literal target path. The deterministic layer owns *where* and *what
    shape*; the model owns 100 % of the prose (observed).
27. `docs/troubleshooting.md` recommends `openspec validate --all --strict`
    for CI while `ci.yml` runs no such job — OpenSpec does not dogfood its
    own validator.
28. `doctor` is relationship health only, not project health; on a normal
    repo it reports `OpenSpec root: ok` / `References (none declared)` and
    nothing else (observed). The name over-promises.
29. Competitor architecture (this pass, static read): Spec Kitty implements
    hex's execution model deterministically in Python — `merge/ordering.py`
    `topological_sort`, `lanes/worktree_allocator.py` basing dependent
    lanes on approved dependency tips, a dedicated conflict classifier and
    resolver. GSD exposes as `.planning/config.json` keys everything hex
    hardcodes: `max_concurrent_agents`, per-gate booleans, and five model
    profiles mapping 12 agents to opus/sonnet/haiku. The GSD repo carrying
    the 64,779-star count is archived (README is a redirect to
    `open-gsd/gsd-core`; clone `main` HEAD 2026-05-31).
30. Operational, for any scripted test of an interactive CLI: drive the pty
    **with a window size set** (`TIOCSWINSZ`) or an inquirer-class renderer
    re-renders unbounded and looks like a hang — 57 MB in 150 s before the
    ioctl, 7.7 KB after.
31. hex-side correction from the same review pass: `models.md:27-40` has
    **14** role rows, not 13; and
    `.agents/plans/plan_scheduling_recursion.md` has **8** WP rows,
    not 9. The staleness finding stands — that plan still reads
    `State: review` with every WP `merged` while the code is already on
    `main` (squash commit `3745eac`).

## Adopt / adapt / reject

| # | OpenSpec idea | Verdict | Rationale | Implementation sketch for hex |
|---|---|---|---|---|
| 1 | Delta vocabulary `ADDED/MODIFIED/REMOVED/RENAMED` | **Adopt** | Gives hex a diff-oriented artifact language it lacks; RENAMED is what makes header-identity survive edits | Add a delta section grammar to the shipped `spec.md` template; hex-plan emits deltas against an existing spec instead of a whole restatement |
| 2 | An archive / fold-back step | **Adopt** | hex's biggest structural gap: a plan reaches `State: done` and nothing folds back into truth | New terminal phase in hex-execute (or a `/hex-archive`): apply the plan's deltas into `.agents/specs/`, move the plan to `plans/archive/YYYY-MM-DD-<slug>/` |
| 3 | Idempotent date-prefix guard on archive | **Adopt** | One-line rule (`/^\d{4}-\d{2}-\d{2}-/`) that prevents a real double-prefix bug OpenSpec had to fix (#1309) | State it in the archive phase file |
| 4 | Fixed apply order RENAMED→REMOVED→MODIFIED→ADDED + stable ordering | **Adopt** | Deterministic, minimal-diff output; prevents order-dependent merges | Written as prose rules in the archive phase; the agent is the executor |
| 5 | Validate-before-write, prepare-all/write-all | **Adopt** | Atomicity across a multi-file rewrite; a late failure leaves everything unchanged | Archive phase: build all rebuilt spec bodies in memory, self-check each, only then write |
| 6 | MODIFIED stale-base scenario guard | **Adopt** | Catches the exact silent-regression class OpenSpec's own design doc calls its root cause | One rule in the archive phase: diff incoming scenario names against current, halt on drop |
| 7 | Separate prompt blocks for project context vs rules vs template | **Adopt** | Best idea on the config axis: customization composes instead of being pasted into the template | Formalize spawn-prompt structure in `protocol.md`: `<project context>` / `<project rules>` / `<task>` as distinct blocks, with the "these are constraints for you, not content" guardrail verbatim |
| 8 | Per-artifact `rules:` keyed by artifact ID | **Adopt** | Finer-grained than hex's current global always-on preferences | `hex.md › Preferences` gains per-artifact rule bullets (`plan:`, `adr:`, `spec:`), written by `/hex-init`, injected only for that artifact's worker |
| 9 | Precise, actionable error strings (header-vs-body, no-headers vs empty-headers) | **Adopt** | Cheapest quality win available; a reviewer worker can be told to emit these shapes | Add an error-message style rule to `workers/reviewer.md`: name the fix location, not just the fault |
| 10 | `generatedBy` version stamp + update diff | **Adopt** | Exactly the drift-detection hex needs between an installed bundle and arcana source | grim already versions artifacts; have `/hex-init` compare the installed bundle version against `hex.md › Pointers` and report drift |
| 11 | "Enablers, not gates" framing | **Adopt** | hex already behaves this way (overlays, optional phases) but never named it | One line in `DESIGN.md`; also add OpenSpec's honest "for a trivial fix the ceremony may not pay off" escape hatch |
| 12 | Code-fence masking before structural parsing | **Adopt** | Any hex artifact linting will false-positive on doc examples without it | Rule in whatever checks plan/ADR structure |
| 13 | Explicit non-goals section | **Adopt** | OpenSpec's non-goals are implicit and it costs them clarity; hex's `DESIGN.md` non-adopts are already half of this | Promote `DESIGN.md`'s non-adopt list into a named Non-goals section |
| 14 | Schema resolution precedence (flag → item metadata → project config → default) | **Adapt** | hex already has 3-input "later wins"; the 4th layer (per-*artifact* metadata) is the missing one | Allow a plan's Status block to pin tier/preferences for that plan, ranked between CLI flags and `hex.md` |
| 15 | YAML + zod config with a published schema | **Adapt, don't copy** | The lesson is *validated config with good errors*, not YAML. hex has no code layer to derive a JSON Schema from — publishing one would be a second source of truth | Keep `hex.md` prose; have `/hex-init` validate its own written sections on re-audit and report malformed entries |
| 16 | Stores (standalone planning repo, read-only `references:`, no sync) | **Adapt** | Right shape for arcana's multi-repo question, but beta and unable to apply a change across repos | If hex needs cross-repo plans: a planning repo with the same `.agents/` shape, pointed at from `hex.md › Pointers`, explicitly never auto-synced. Ship only when a real second repo needs it |
| 17 | Profile × delivery × tool 3-axis generation model | **Adapt** | Clean separation, but hex's equivalent axes are tier × overlays × client; only the naming discipline transfers | Note the analogy in `DESIGN.md`; no code change |
| 18 | Lite vs Full spec rigor | **Adapt** | Precedent that a 2-level rigor split is accepted practice — hex's low/medium/high already covers it | Cite as precedent in ADRs; no change |
| 19 | Loose scenario detection (any `####` counts) | **Adapt with caution** | Leniency is fine, but hex's traceability gates count scenarios mechanically | If hex counts S-IDs, require the literal `Scenario:` word; document the choice |
| 20 | Header-text-as-requirement-identity | **Reject** | hex already has `C-###`/`S-###` assigned once and never renumbered — strictly better under renames | Keep hex's IDs; adopt RENAMED only as a *human-readable* delta operation, not as identity repair |
| 21 | Unpaired RENAMED FROM/TO silently dropped | **Reject** | An acknowledged gap in OpenSpec, not a design | Make it an error in hex's equivalent |
| 22 | LLM-judgment spec merging (`openspec-sync-specs`) | **Reject as primary, adopt as fallback** | It is OpenSpec regressing a deterministic guarantee into a prompt; hex has no runtime so it must use agent judgment — but should pin the guard rails (finding 6) rather than trust "intelligent merging" | Archive phase: mechanical rules first, agent judgment only for genuine conflicts, and escalate rather than guess |
| 23 | 34-client adapter matrix | **Reject** | A maintenance tax paid in ~41 releases of ecosystem-chasing; hex ships markdown and the client is the runtime — that's the moat (`DESIGN.md`) | None |
| 24 | `/opsx:` command prefix distinct from skill-dir prefix | **Reject** | Real friction in their own tracker (#813, 13 reactions); `/hex-*` matching `hex-*` is already right | None |
| 25 | `initiatives` / `explorations` vocabulary | **Reject** | Confirmed abandoned beta inside OpenSpec itself | Do not port |
| 26 | Single-agent verify as a review model | **Reject** | Strictly weaker than hex's staged panel + adversary gate; and it never blocks | None — but note hex should not assume OpenSpec validates behaviour: it does not |
| 27 | Marker-block injection into CLAUDE.md/AGENTS.md | **Reject; keep the cleanup pattern** | OpenSpec deprecated it; but its legacy-cleanup ("detect stale markers, remove without deleting the user's file") is worth copying for hex's own `<!-- hex:start -->` discovery block | `/hex-init` re-audit removes only its own fenced block, never the host file |
| 28 | Gate shape: show current state → print computed diff → offer to apply the consequence now | **Adopt** | Observed in `config profile`; three beats, no follow-up command to forget. hex gates today ask before showing what would change | Any `/hex-init` or overlay gate that mutates `hex.md`: print current values, print the `old -> new` diff, then ask, then apply |
| 29 | Non-interactive escape hatch named in the failure message, with the full valid-value list inline | **Adopt** | Cheapest error-UX win observed; the fix is copy-pasteable without re-reading `--help` | Extend item 9's reviewer error-string rule: an error that rejects a value must enumerate the accepted ones |
| 30 | Regenerate scaffolding always, never rewrite user-owned config | **Adopt** | Observed `init` idempotency rule; exactly the ambiguity `/hex-init` re-audit has today | State the split in the init phase file: shipped files regenerate, `hex.md` is only ever amended with consent |
| 31 | `.planning/config.json`-style tunable orchestration (GSD: per-gate booleans, `max_concurrent_agents`, model profiles) | **Reject, but stop calling it unprecedented** | It exists and ships at scale; hex's reason to decline is the no-parser constraint and the maintenance surface, not novelty | None — but ADRs arguing against tunable rosters must cite GSD as the counter-example they are declining |

## Recommendation

Take the **format**, not the framework. Concretely, in priority order:

1. **Ship an archive/fold-back phase** (items 2–6). This is the one place
   OpenSpec is unambiguously ahead and the gap is structural, not
   cosmetic: hex currently produces truth-shaped artifacts and never folds
   them back into truth. Everything needed is prose rules in a new phase
   file plus a delta grammar in the shipped `spec.md` template.
2. **Formalize spawn-prompt block structure** (items 7–8). Separate
   `<project context>` / `<project rules>` / `<task>` blocks with the "these
   are constraints for you, not content for the artifact" guardrail, and
   per-artifact rules in `hex.md › Preferences`. Small edit to
   `protocol.md`, immediate quality effect on every worker.
3. **Do not adopt YAML.** `DESIGN.md`'s reasoning holds and OpenSpec is
   itself evidence: it built three YAML surfaces, zod-validated all of
   them, and still ships no JSON Schema for editor completion — so the
   payoff it bought (parse-time errors) is unavailable to hex, which has no
   parser and no code layer to derive a schema from. Cite finding 5 in the
   ADR as the considered-and-rejected alternative.
4. **Defer multi-repo.** OpenSpec's Stores is the best available shape and
   its own maintainers label it beta with "command names, flags, file
   formats… may still change". Cross-repo change application is an open
   issue there (#725), unsolved in spec-kit (one constitution per repo),
   unsolved in log4brains (ADR federation is roadmap-only), and unsolved in
   BMAD. arcana already has the industry's converged answer — a versioned
   registry (grim/OCI) — for *distributing* shared conventions. Build a
   planning-repo pointer only when a second real repo demands it.

Weakest evidence in this artifact: the third-party benchmark numbers
(12 min vs 90 min vs 5.5 h; ~57.7k vs ~120.9k tokens) come from
marketing-adjacent comparison blogs with unstated methodology — directional
only. The widely-quoted HN "drift" comment could not be located in the two
most relevant threads and is secondhand. Second-weakest: the GSD and Spec
Kitty comparison is a single static clone read each, neither executed, and
the GSD clone is of an archived repo whose active development has moved —
architecture claims about them are structural, not behavioural.

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| `Fission-AI/OpenSpec` clone @ v1.6.0 | Repo | 2026-07-10 | Primary; every `src/…`/`docs/…`/`skills/…` citation |
| https://openspec.dev/ + `/docs/*` | Docs | 2026-07-20 | Official positioning; docs pages are mechanically mirrored from repo `docs/*.md` via `website/docs.sync.config.mjs` |
| https://openspec.dev/docs/reference/agents | Docs | stamped 2026-06-11 | JSON agent contract, root-selection precedence |
| https://registry.npmjs.org/@fission-ai/openspec/latest | Registry | 2026-07-10 | v1.6.0 publish date |
| `gh api repos/Fission-AI/OpenSpec` + `/releases` + issue search | API | 2026-07-20 | Stars, forks, issues, contributors, 41 releases |
| Issues #662, #594, #581, #697, #725, #780, #813, #863, #880, #381, #1129 | Issues | open @ 2026-07-20 | Hierarchical specs, custom dir, multi-repo, naming, verification gaps |
| Discussions #176, #768 | Discussion | 2026 | Monorepo scaling consensus and naming-convention workaround |
| https://codemyspec.com/blog/openspec-explained | Blog | 2026 | Drift criticism, "maintaining the main specs is not worth it" |
| https://dev.to/incomplete_developer/… | Blog | 2026 | Negative case study vs plain `instructions.md` |
| `gh api repos/gsd-build/get-shit-done` | API | 2026-07-20 | Growth curve (64,779 stars) — note the repo is archived/redirected |
| `gsd-build/get-shit-done` clone (`main` @ 2026-05-31, v1.50.0-canary.0) | Repo | 2026-07-20 | `agents/gsd-*.md` (33), `commands/gsd/` (~65), `get-shit-done/templates/config.json`, `references/model-profiles.md`, `hooks/`, `sdk/` |
| `Priivacy-ai/spec-kitty` clone (`main` @ 2026-07-20) | Repo | 2026-07-20 | `src/specify_cli/{merge,lanes,dashboard}`, `.kittify/config.yaml`, `kitty-specs/`, `src/doctrine/model_task_routing/`; verifies the worktree + topological-merge claim |
| Live CLI transcripts — `init` (fresh + re-run), `config profile`, `workset create`, `doctor`, `context`, `new change`, `instructions` | Execution | 2026-07-20 | `@fission-ai/openspec@1.6.0` driven under a pty in a scratchpad; source of the "Live CLI behaviour" section |
| `src/core/templates/workflows/verify-change.ts`, `src/core/artifact-graph/instruction-loader.ts` | Repo | 2026-07-10 | Settles verify-checklist extensibility from prompt assembly |
| `docs/{troubleshooting,workflows,existing-projects}.md` in the clone | Docs | 2026-07-10 | Failure-mode structure, informal change stacking, brownfield/multi-repo routing |
| `openspec/changes/*` in the clone (16 active change folders) + `IMPLEMENTATION_ORDER.md` | Repo | 2026-02 → 2026-07 | Dogfooded in-flight artifact chains; shape variance; the stacking-metadata proposal |
| `.github/workflows/ci.yml` in the clone | Repo | 2026-07-10 | Self-gating pipeline; absence of an `openspec validate` job |
| `src/commands/doctor.ts`, `src/commands/context.ts` in the clone | Repo | 2026-07-10 | Health vs presentation split; `{message, fix}` diagnostics |
| `hex/DESIGN.md`, `hex/hex-core/references/{protocol,models,workers,memory}.md` | Repo | current main | hex side of every comparison row |
| `.agents/adrs/adr_0001*`, `adr_0002*` | ADR | Accepted 2026-07-19 | Binding constraints any adoption must respect |
