# ADR: Finding-severity contract for review output

## Metadata

**Status:** Accepted
**Date:** 2026-07-20
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A (surfaced by the 2026-07-20 tier-high `/hex-review` of the working tree, and by the direct question "why is there no template showing findings + severity + action")
**Related PRD:** N/A
**Architectural Conventions:**
- [x] Decision follows this project's stated architectural conventions /
      golden path
- [ ] OR the deviation is justified in the Rationale section below
**Domain Tags:** api, devops (a bundle-internal shared contract)
**Supersedes:** N/A
**Superseded By:** N/A

## Context

hex reaches verdicts on a four-level severity vocabulary — `Block`, `High`,
`Warn`, `Suggest` — that is **defined in no file**. The words are *used*:
`hex-review/overlays.md:60` scopes RCA by "Block/High findings",
`hex-review/SKILL.md:265` gates Request Changes on "any unresolved
Block-tier finding", and every tier file branches its verdict on them. But
the vocabulary is absent from the one place a finding is actually produced —
the `reviewer` worker output contract
(`hex-core/references/workers/reviewer.md:45-53`) classifies a finding only
`Actionable | Deferred`, with **no severity field** — and absent from the
report skeleton and the handoff, which carry only *counts*
(`SKILL.md:326-328`: "Actionable: <n> … listed above").

Severity therefore lives only in the orchestrator's head. The cost is
concrete and was observed in the 2026-07-20 tier-high review that surfaced
this: five reviewer workers each returned a **different finding shape**; the
orchestrator hand-rolled a severity table and an ad-hoc `B1/H1/W1` ID
scheme; a late-arriving worker forced a manual recount; two workers reported
the **same `file:line` at different severities**; and the cross-model pass
**escalated one worker's `Warn` to `Block`** with nowhere structured to
record the override. The documented downstream consumer —
`/hex-execute`'s Review-Fix Loop — receives prose.

### The central constraint

This is not a missing template. It is a **missing shared data type**. hex's
constitution (`hex/DESIGN.md`) forbids the obvious fixes: no parser, no
schema, no second source of truth (link, never copy), and a value nobody can
validate must still not drift. And `adr_0003` (Proposed) lets a project
**fork a `hex-review/tier-*.md` file and delete optional report sections** —
so any findings structure that lives in a report *section* can be silently
dropped — the fork hole `adr_0003`'s `workflows` mechanism opens (a project
forks a `hex-review/tier-*.md` file and deletes an optional phase or report
section; `adr_0003` S-212). Whatever carries
severity must survive that fork.

## Decision Drivers

- **Define the vocabulary once**, where hex already puts shared contracts
  (`protocol.md`), so consumers link rather than restate it.
- **Fix the six observed failures**, not just the visible symptom (the
  missing table).
- **Survive a workflow fork** (`adr_0003`) — severity cannot ride a
  deletable report section.
- **Add no schema, no parser, no synthetic ID** — the client is the runtime;
  a value hex cannot validate is a liability, not an asset.
- **Degrade at tier `low`** without adding ceremony to the two-way-door tier.
- **Stay lazy** — the least new surface a maintainer must keep true.

## Industry Context & Research

**Research artifact:** the design was produced by an in-repo design workflow
(3 independent candidates → a 3-lens judge panel → an adversarial verify
pass); its per-candidate scores are reproduced under Decision Outcome. Prior
art consulted, not re-researched:
`.agents/research/openspec-framework-analysis.md` and
`.agents/research/swarm-customization-and-config.md`.

**Key insight:** the tools hex compares against externalize a findings
*record*, not a table. OpenSpec's review is a single agent with a 3-item
checklist and no severity type at all; get-shit-done carries severity as
prose. The strongest structured prior art is this harness's own
`ReportFindings` tool — its record is `{file, line, summary, failure_scenario,
category, verdict, outcome}`, keyed on `file`+`line`, with **no synthetic
per-finding ID** and severity carried as a small enum. That the host tool
needs no ID namespace is direct evidence hex needs none either.

**Trending approaches:** severity-as-enum on a per-finding record is
universal (ESLint `error|warn`, RUF/Clippy lint levels, SARIF `level`); a
per-finding *stable ID across runs* appears only where an ingest/tracking
backend consumes it (SARIF `ruleId` + fingerprints) — which hex has no
equivalent of.

## Considered Options

Three candidates were designed independently, then judged on three lenses
(laziness / fitness-to-the-six-failures / constitution-survival).

### Option A — Severity-tagged finding line; no table, no ID (recommended)

**Description:** add one `[Block | High | Warn | Suggest]` tag to the
existing `reviewer.md` finding line, and define the vocabulary once as a new
`protocol.md § Finding severity` section that everything else links. No
table, no synthetic ID — `file:line` is the natural key; counts re-derive by
appending lines. Duplicate `file:line` reconciles by a one-sentence
**highest-severity-wins** rule; cross-model escalation provenance is carried
by the existing Cross-Model report section. Omitted at tier `low`.

| Pros | Cons |
|------|------|
| Least new surface: one field + one four-rung ladder, no new file, no table, no ID scheme, no state machine | Duplicate/escalation are handled by a prose rule, not a structural column |
| Rides the **un-forkable** `reviewer.md` worker line — survives an `adr_0003` fork by construction (closes that fork hole for severity) | No stable cross-round finding identity (see Rationale — hex has no consumer for one) |
| Deletes the ad-hoc ID scheme that *caused* the observed recount pain (root-cause, not symptom) | |

### Option B — Findings table + single-source severity ladder

**Description:** a 7-column findings table in the report plus the same ladder
in `protocol.md`. Refuses a `Repo` column and a status machine, but keeps a
per-finding `F-id` and an inline `quality:Warn ↑ adversary:Block` escalation
micro-syntax.

| Pros | Cons |
|------|------|
| A structural column for duplicate reconciliation and escalation provenance | Builds an `F-id` scheme and a table the winner proves unnecessary |
| Fixes all six observed failures mechanically | The `↑` escalation DSL is a new convention to keep true forever — the "clever thing decoded at 3am" |
| | The table is a report section — droppable by an `adr_0003` fork |

### Option C — `F-id`-keyed finding record with a status lifecycle

**Description:** a full finding record with a stable `F-001` ID, a
`Found-by` column, and an `open/fixed/regressed/deferred` status machine for
cross-round tracking.

| Pros | Cons |
|------|------|
| Richest round-2 identity ("F3 fixed, F7 regressed") | hex-review is one-shot and hex-execute's loop already matches findings semantically — the ID serves an ingest slot that does not exist (YAGNI) |
| Explicit dedup structure | `Status` and `Repo` columns are usually-empty — a defect by hex's own house rule; heaviest surface of the three |

## Decision Outcome

**Chosen Option:** Option A — the severity-tagged finding line.

**Rationale:** through the laziness lens A wins decisively (adds one bracketed
field and one four-rung ladder, no file, no table, no ID, no state machine),
and it alone recognizes the observed recount pain was *manufactured by* a
hand-rolled ID scheme — so it refuses to build one. B and C both formalize
the pain into a table plus an ID discipline the winner shows is unnecessary.
The adversary confirmed A is also the **most fork-robust** option: its shape
rides `reviewer.md`'s worker line — which an `adr_0003` workflow fork cannot
delete — rather than a droppable report section, so choosing A is
simultaneously the fix for the `adr_0003` fork hole for severity. Round-2
finding identity was ruled **not a blocker**: hex-review is one-shot, and
hex-execute's Review-Fix Loop already matches findings semantically with zero
IDs; stable IDs would serve a consumer that does not exist. Option C's `↑`/
`,` escalation DSL is explicitly rejected as over-build — escalation
provenance is already carried by the Cross-Model report section.

### Weighted scoring

Independent judge scores, 0–100 per lens (higher = better):

| Option | Laziness | Fitness (6 failures) | Constitution | Verdict |
|---|---|---|---|---|
| **A — tagged line** | **91** | 58 | (fork-robust: highest) | **chosen** |
| B — table + ladder | 54 | **92** | mid | rejected — builds an ID scheme + `↑` DSL the winner shows unneeded |
| C — `F-id` record | 39 | 68 | lowest (usually-empty `Status`/`Repo`) | rejected — ID + status machine serve a non-existent consumer |

The fitness lens rated B highest because only a structural column *represents*
duplicate-at-conflicting-severity and escalation. The adversary resolved the
split: A's one-sentence max-wins rule fixes duplicate reconciliation, and
escalation provenance already has a home (the Cross-Model section), so B's
extra structure buys nothing A cannot reach — while A pays far less and, alone,
survives the fork. The winning design was returned **ship-with-fixes**; the
three required corrections (peer section not buried in the loop; omit at low;
add the max-wins sentence) are folded into the Normative specification below.

### Normative specification

The buildable contract — six files, all one-line edits except the single new
`protocol.md` section. `doc-reviewer.md` and `hex-review/tier-low.md` are
**not** touched (severity is omitted at low, and the producer keeps its native
grades — see C-505/C-503).

**New `protocol.md § Finding severity`** (inserted between § Traceability IDs
and § Worktree work-package mechanics — `protocol.md:372→373`):

```markdown
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
```

The consumer edits: `reviewer.md` gains a `[severity]` tag on its Classify
block and return lines (medium/high; omitted at low) and one self-check word;
`hex-review/SKILL.md` replaces the counts-only handoff with the tagged lines
and folds `High` into the Needs Work floor (`:271`); the two upper tier files
retire the phantom `suggest` *disposition* (Suggest is a severity, never a
class) and fold `High` into Needs Work; `overlays.md:60` gains the definition
link. Full per-line spec is C-507…C-510.

### Consequences

**Positive:**
- The severity vocabulary hex already branches on is defined exactly once,
  linkable, and impossible to drift out of sync by hand.
- Severity survives an `adr_0003` workflow fork — it rides the worker line,
  closing that fork hole for review output.
- The ad-hoc per-run ID scheme and hand-rolled table are deleted; the
  handoff to `/hex-execute` carries structured, tagged findings.
- Two latent bugs in the shipped files are corrected: the phantom `suggest`
  *disposition* (it is a severity, not a class) and the missing `High`
  verdict floor (`High` had no home in the Needs Work rule).

**Negative:**
- Duplicate reconciliation and escalation provenance are prose rules, not
  structural columns — a reader must apply max-wins, not read a resolved cell.
- No stable cross-round finding identity; acceptable because no hex consumer
  ingests one (see Rationale).

**Risks:**
- A future need for cross-round tracking (a findings backend, a persistent
  review ledger) would reopen Option C. Mitigation: the tag is forward
  compatible — an ID column can be added beside it without changing the
  vocabulary.

## Component contracts

Contracts are numbered `C-5xx`; UX scenarios `S-5xx` (range assigned at the
meta-plan gate; `adr_0001` `C-00x`, `adr_0002` `C-1xx`, `adr_0003` `C-2xx`,
`adr_0004` `C-3xx`, `adr_0005` `C-4xx`). Home column names the single
definition or edit site.

| ID | Contract | Home |
|---|---|---|
| **C-501** | **The severity ladder is defined once.** `protocol.md § Finding severity` is the sole copy of the four-level vocabulary and its verdict floors (`Block ⇒ Request Changes`, `High/Warn ⇒ Needs Work`, `Suggest ⇒ none`). Every other site links `#finding-severity`; none restates the levels or floors. Attaching the floor to the definition — not only to the SKILL.md verdict rules — keeps consumers from drifting out of sync. | new `hex-core/references/protocol.md § Finding severity` (between `:372` and `:373`) |
| **C-502** | **Severity is worker-assigned and orthogonal to class.** The worker that raises a finding tags its severity; the orchestrator synthesises and never invents a grade (`protocol.md § Worker coordination`). Class (`actionable`/`deferred`) and severity are independent axes — every finding carries one of each. A verdict floor is a floor, not a ceiling: a consumer rule may raise a finding above it. | `protocol.md § Finding severity`; `workers/reviewer.md` |
| **C-503** | **Medium/high construct; omitted at `low`.** The tag is present at tier medium and high and **absent** at tier low, where a finding carries only its class. Presence of the tag is the sole signal that a run graded severity — no schema-version marker. At low the verdict keys on the **severity-free** triggers `SKILL.md:265-275` already enumerates (a security vulnerability, a breaking change without a migration note, new behavior without tests, an unjustified constitution violation → Request Changes; an unconverged gap or **any unresolved actionable finding** → Needs Work), never on a tag — so omitting severity at low costs no verdict coverage. `hex-review/tier-low.md` is unchanged; adding the tag there would expand behavior at the two-way-door tier for no gain. | `protocol.md § Finding severity`; `workers/reviewer.md`; `tier-low.md` (unchanged, by contract) |
| **C-504** | **One defect, highest severity wins.** When ≥2 perspectives report the same `file:line` defect it is **one** finding at the highest severity any perspective assigned — no averaging, no new notation. A panel `Warn` the cross-model pass raises to `Block` resolves to `Block`. This one sentence discharges observed failures #4 (duplicate at conflicting severity) and #5 (escalation) without a structural column. | `protocol.md § Finding severity` |
| **C-505** | **Producer-local grades fold onto the ladder at synthesis.** `doc-reviewer` keeps emitting `Critical / Medium / Accuracy`; the orchestrator maps `Critical → High`, `Medium → Warn`, `Accuracy → Block`. The `Accuracy → Block` mapping is a **deliberate** inversion of doc-reviewer's own ordering: `Accuracy` names a doc that misstates *shipped behavior or a contract*, which is a correctness lie (merge-unsafe), whereas doc-reviewer's `Critical` grades severity-of-doc-issue, not correctness. A doc that is merely incomplete or unclear is `Medium → Warn`, not Accuracy. No producer defines a fifth level and **`doc-reviewer.md` is not edited** — the mapping lives only in the severity section. | `protocol.md § Finding severity` (`doc-reviewer.md` untouched) |
| **C-506** | **Escalation provenance is not a new field.** A `Warn → Block` override is recorded where it already surfaces — the Cross-Model Adversarial report section — not in an inline `↑`/`,` micro-syntax. C-504 gives the resolved severity; the Cross-Model section gives who raised it. | `hex-review/SKILL.md` report skeleton (existing Cross-Model section) |
| **C-507** | **`reviewer.md` worker contract gains the tag.** The Classify block adds a `Severity — tag each finding [Block \| High \| Warn \| Suggest]; omit at tier low` bullet linking `#finding-severity`; the two return lines gain a `[severity]` prefix (present medium/high, omitted low); the final self-check bullet adds "carries a severity tag at medium/high". This is the un-forkable carrier — the reason severity survives an `adr_0003` fork. | `hex-core/references/workers/reviewer.md:45-47,:52-53,:58` |
| **C-508** | **The handoff carries tagged lines, not counts; `High` gets a verdict home.** `hex-review/SKILL.md:326-328` replaces "Actionable: <n> … listed above" with the actual `[severity] file:line — issue — remediation` lines in Actionable/Deferred buckets (`(none)` when empty; no prefix at low), and `:271` changes "Warn-tier findings remain" to "**High- or Warn-tier** findings remain" — folding `High` into the Needs Work floor it currently lacks. `:265` gains the `#finding-severity` link. | `hex-review/SKILL.md:265,:271,:326-328` |
| **C-509** | **Tier files retire the phantom `suggest` disposition.** `tier-medium.md:77` and `tier-high.md:91-92` currently say a reviewer classifies findings "actionable, deferred, or **suggest**" — mixing a severity into the class axis. They change to "classify actionable/deferred **and tag severity** (link `#finding-severity`); a Suggest-severity finding is reported but never gates the verdict." Both tier files also fold `High` into their Needs Work floor (`tier-medium.md:164`, `tier-high.md:173`). | `hex-review/tier-medium.md:77,:164`; `hex-review/tier-high.md:91-92,:173` |
| **C-510** | **`overlays.md` RCA scope links the definition.** `hex-review/overlays.md:60` (and the tier RCA phases that name Block/High scope) gain the `#finding-severity` link so the severity words point at their single source rather than dangling. | `hex-review/overlays.md:60` |
| **C-511** | **Orchestrator synthesis self-check** — the observed failure was *orchestrator-side*, so the synthesis half gets the same forcing function as the worker half (C-507). Before emitting the report the orchestrator confirms: every duplicate `file:line` resolved max-wins (C-504); every `doc-reviewer` grade mapped (C-505); every cross-model escalation noted in the Cross-Model section (C-506); every empty bucket printed `(none)`. This is a prose checklist the report-writing model runs on itself — no parser, no gate — mirroring the worker self-check, not a new mechanism. | `hex-review/SKILL.md § The review report` (synthesis step) |

**UX scenarios.**

| ID | Scenario |
|---|---|
| **S-501** | Tier-medium review, 3 findings. Each reviewer returns `[severity] file:line — issue — remediation`; the handoff `### Findings` block lists them under Actionable/Deferred with tags; the verdict floor derives from the highest tag (a `Block` ⇒ Request Changes). |
| **S-502** | Tier-low review. The reviewer omits the tag; findings carry only `actionable`/`deferred`; the verdict keys on the severity-free triggers (C-503) — an unresolved actionable finding caps at Needs Work — and `tier-low.md` is unchanged, its "every finding is classified actionable or deferred" line staying exactly true. |
| **S-503** | `reviewer:quality` reports `src/api.rs:12` as `Warn`; `reviewer:security` reports the same line as `Block`. The orchestrator emits **one** finding at `Block` (C-504) — no averaging, no two lines. |
| **S-504** | `doc-reviewer` returns an `Accuracy` finding (a doc contradicting shipped behavior). The orchestrator maps it to `Block` at synthesis; `doc-reviewer.md` was never edited. |
| **S-505** | The panel grades a finding `Warn`; the cross-model pass raises it to `Block`. Resolved severity is `Block` (C-504); the escalation is legible from the Cross-Model Adversarial section (C-506), with no inline `↑` notation. |
| **S-506** | A clean review finds nothing. The report carries the verdict and no findings lines — byte-identical-when-clean, like the Convergence contract. |
| **S-507** | A project forks `hex-review/tier-medium.md` and deletes an optional section. Reviewers still emit `[severity]` tags — the carrier is `reviewer.md`, not the forked file — so severity survives the fork (the `adr_0003` workflow-fork hole does not reach review output). |

## Non-Functional Requirements

| Axis | Impact of this decision |
|---|---|
| Scalability | Not affected — markdown, no runtime. |
| Availability | Not affected. |
| Latency | Not affected. |
| Security | Neutral-positive — a defined `Block` floor for security findings makes the Request-Changes gate legible; no new attack surface (no parser, no execution). |
| Cost | Negligible — a handful of tokens per finding line. |
| Operability | Improved — one definition site; a broken severity reference becomes a dead link a doc-review catches, not silent drift. |

## Constitution deviations

**None.** The three surfaces a reviewer would suspect are each honoured, not
deviated:

| Rule | Why it is honoured |
|---|---|
| `DESIGN.md:32-39` — link, never copy; no second source of truth | The vocabulary and floors are defined once in `protocol.md § Finding severity`; all nine other sites link it (C-501). This *removes* the current drift risk (severity words used with no definition). |
| `DESIGN.md:108-110` — "sections are conventions, **not schema**" | The `[severity]` tag is a four-value convention on a prose line, not a validated schema: no parser reads it, a missing or misspelled tag degrades to an untagged finding (still reported), and it is omitted entirely at low. No key freezes, nothing rejects on mismatch. |
| `DESIGN.md:320-326` — client is the runtime; no engine, no presets | Nothing executes. Severity is model-assigned prose the orchestrator synthesises; the only "mechanism" is the max-wins sentence, applied by the same model that writes the report. |

**Considered and not deviated — the `adr_0003` interaction:** `adr_0003`
freezes a workflow *vocabulary* at first release and lets a fork delete
optional report sections. This ADR adds no workflow-config key and puts the
carrier on the worker line, not a report section — so it neither enlarges the
frozen vocabulary nor exposes severity to the fork hole. It in fact *closes*
that hole for review output (C-507). Accepting the two in either order is
safe; if both land, `adr_0003`'s read-time phase derivation and this ADR's
worker-line tag are independent.

## Migration / rollout plan

*(This section fills the template's Implementation-Plan slot; the corpus uses
this heading — `adr_0003`, `adr_0005`, and `adr_0002`'s companion system-design
doc.)*

Two waves, no backward-compatibility constraint (repo unreleased):

- **Wave 1 — define + produce.** Add `protocol.md § Finding severity`
  (C-501…C-506) and the `reviewer.md` worker-contract tag (C-507). After
  Wave 1 a reviewer emits severity and the vocabulary is defined; consumers
  still read counts. Nothing breaks — an untagged consumer ignores the prefix.
- **Wave 2 — consume.** Update `hex-review/SKILL.md` (C-508, C-511), the two
  tier files (C-509), and `overlays.md` (C-510). After Wave 2 the handoff
  carries tagged lines, the orchestrator runs the synthesis self-check, and
  the verdict floors are complete (`High` folded into Needs Work).

`grim build ./hex/hex-core` and `./hex/hex-review` after each wave; a
markdown-link/anchor sweep confirms every `#finding-severity` link resolves.
No installed-copy drift is acceptable at completion — `grim install` syncs
`.claude/skills/` (the `adr_0003`-review W3 caveat applies).

## Validation

- [ ] `grim build ./hex/hex-core` and `./hex/hex-review` exit 0 after each wave.
- [ ] Every `#finding-severity` reference resolves to the new heading
      (anchor sweep, `/usr/bin/grep`).
- [ ] `protocol.md § Finding severity` is the **only** site defining the four
      levels or their floors (no restatement elsewhere — single-source sweep).
- [ ] A tier-medium `/hex-review` self-test: findings carry `[severity]`
      tags; a duplicate `file:line` at two severities resolves max-wins; an
      empty bucket prints `(none)`.
- [ ] A tier-low `/hex-review`: no `[severity]` prefix appears; `tier-low.md`
      byte-unchanged.
- [ ] S-501…S-507 pass as acceptance cases.

## Open Questions

- [NEEDS CLARIFICATION: should Wave 2's `High → Needs Work` floor change be
  called out as a behavior change in its own right?] Recommended: yes, note
  it in the Wave 2 commit message — today `High` findings have no verdict
  home, so this is a latent-bug fix, not only a refactor.

## Links

- Related ADR: [adr_0003_configuration_customization_surface.md](adr_0003_configuration_customization_surface.md)
  — the `workflows` fork mechanism (S-212) whose hole this closes for review
  output.
- Surfaced by: the 2026-07-20 tier-high `/hex-review` of the working tree.
- Research: [openspec-framework-analysis.md](../research/openspec-framework-analysis.md),
  [swarm-customization-and-config.md](../research/swarm-customization-and-config.md).
- Prior art: this harness's `ReportFindings` tool (record shape, no synthetic ID).

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-07-20 | hex-architect | Initial draft. Chosen Option A (severity-tagged finding line, no table, no ID) from a 3-candidate design workflow (judge scores reproduced); ship-with-fixes corrections folded into the Normative specification. Contracts C-501…C-510, scenarios S-501…S-507. Status Proposed. |
| 2026-07-20 | hex-architect (review pass) | Two-reviewer adversarial pass (substance + conformance), all citations verified against the shipped files. Applied: corrected the `adr_0003` "finding B4" cross-reference to the `workflows`-fork mechanism (S-212); resolved the tier-low verdict path to the severity-free triggers (C-503/S-502); added **C-511** (orchestrator synthesis self-check) answering the strongest objection — the consumer half now carries the same forcing function as the worker half; made the `Accuracy → Block` inversion explicit and deliberate (C-505); reordered Component contracts before NFR and embedded UX scenarios per corpus; Links converted to real relative links; footnote misattribution fixed. No Block findings; decision unchanged. Contracts now C-501…C-511. Status Proposed. |
| 2026-07-21 | hex-execute (branch-review fix) | Corrected the Suggest-row verdict-floor cell in the Normative-spec ladder: `none — routed to the deferred summary` → `none — reported, but never gates the verdict`. The old phrasing reintroduced the exact phantom `suggest` *disposition* this ADR's C-509 and Consequences retire — routing a finding by severity rather than by its actionable/deferred class, contradicting the orthogonality statement four lines above. Caught by the branch-level review panel (High, adversarially verified) on the implementation branch and fixed at both the ADR normative block and the shipped `protocol.md § Finding severity` so the single source and its record stay byte-identical. Within-intent correction; decision and acceptance unchanged. |
