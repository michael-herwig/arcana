# ADR: Terminal archive and spec fold-back

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
      decision amends `hex-review`'s never-writes contract and the
      "no hex orchestrator produces a spec" rule)
**Domain Tags:** developer-experience, data-integrity, integration
**Supersedes:** N/A
**Superseded By:** N/A

## Context

hex produces truth-shaped artifacts and never folds them back into
truth. Verified against the shipped bundle:

- The plan Status block has five states — `planning → plan-approved →
  executing → review → done` (`hex-init/assets/templates/plan.md:24`,
  `hex-plan/SKILL.md:216`).
- `hex-review` is the **only** writer of `done`: "on verdict, set
  `State` to `done` with `Next` cleared (Approve), or leave
  `State: executing` and set `Next` to `/hex-execute <plan path>`"
  (`hex-review/SKILL.md:230-233`). `hex-execute` writes `executing` and
  `review`, never `done`.
- `done` is a dead end. The single consumer treats it as a stop
  condition — "`review` or `done` means this plan already passed
  execution — **stop and report**" (`hex-execute/SKILL.md:100-102`) —
  and nothing else in the bundle reads it. `grep -rn 'archive'` across
  `hex/` returns three unrelated hits (an archive-extraction security
  marker, a fixture example, a CWE list). No plan is ever archived.
- The `hex.md › Memory` active-plan pointer is written
  (`hex-plan/SKILL.md:207,:265,:296`) and read
  (`hex-execute/SKILL.md:45,:70,:80,:233`; `hex-review/SKILL.md:228`)
  and **never cleared** by any file in the bundle.
- No orchestrator writes a spec. The shipped template states it
  outright: "A human-authored pre-plan artifact - no hex orchestrator
  produces one" (`hex-init/assets/templates/spec.md:8`). IDs travel one
  way only — "assigned when the artifact is written (in the spec when
  one exists, carried into the plan unchanged)"
  (`protocol.md:341-344`). The nearest existing write-back is
  `hex-execute`'s Living design record
  (`hex-execute/SKILL.md:259-262`), which updates the **plan**.

So a plan reaches `done` carrying delivered, reviewed, ID'd contracts,
and the project's durable spec still describes the world as it was
before the work. The next plan is authored against a stale spec. This
is the largest structural gap the OpenSpec teardown found
(`openspec-framework-analysis.md`, adopt/adapt/reject item 2: "hex's
biggest structural gap: a plan reaches `State: done` and nothing folds
back into truth").

**Settled at the meta-plan gate, not re-litigated here:** deltas fold
into **whatever the project already documents as its spec home**,
discovered through `hex.md › Pointers` exactly as verification commands
and ADR conventions are today (`memory.md:35,:50-51`;
`hex-init/references/audit.md:28-40`). hex ships the delta grammar and
the archive phase. **hex never ships the destination.** A hex-owned
`.agents/specs/` store is rejected; it is presented in the
options table with its evidence and scored, for the record only.

### The central constraint

**hex has no parser, and every guarantee OpenSpec gets from code, hex
must get from an instruction a model may skip.** The mechanics worth
porting — validate-before-write, the MODIFIED stale-base guard, the
cross-section conflict matrix — are
TypeScript in OpenSpec (`specs-apply.ts:163-193,:244-330,:305-310,
:410-443`; `archive.ts:420-489`; `validator.ts:262-285`). Here they are
prose. A prose rule that is skipped fails **silently while rewriting a
project's spec files**, which is strictly worse than having no
fold-back at all: today's failure is a stale spec the user knows is
stale; the new failure is a confident spec that quietly lost a shipped
requirement.

This is the design's central risk, and it is not hypothetical. OpenSpec
lived it: `openspec-parallel-merge-plan.md` documents a real
content-loss incident ("the archive completes successfully, and the
source-of-truth spec now omits a shipped scenario"), designed a
four-phase deterministic fix (SHA-256 requirement fingerprints, diff3
rebase, scenario-level directives, a spec graph), shipped **none** of
it, and instead released `skills/openspec-sync-specs/SKILL.md`, whose
entire safety story is "Use your judgment to merge changes sensibly."
That skill has no equivalent of the scenario-drop guard the CLI path
already had. **OpenSpec regressed a deterministic guarantee into a
prompt.** hex starts where OpenSpec ended up, by constitutional choice
(`DESIGN.md:63-65`), so the only lever available is *which* prose it
writes — and the answer is not "prose that says try harder", it is
**mechanical pre-pass, printed, then judgment only on the narrowed
remainder**, plus halt-and-escalate wherever OpenSpec would have
thrown.

Every mechanic below therefore carries three things: the rule, what its
failure looks like when the model does not apply it, and what makes
that failure **visible rather than silent**.

## Decision Drivers

- **Silent corruption of human-owned truth is the failure to design
  against.** Everything else — expressiveness, ergonomics, phase count
  — is subordinate. A refusal to fold is always acceptable; a wrong
  fold is not.
- **The destination is the project's, not hex's**
  (`DESIGN.md:32-39,:145-156`: "Anything that is knowledge about the
  PROJECT … lives in project context … hex never duplicates it into its
  own config"; "Destination is the user's choice"). A hex-owned spec
  store would be the second source of truth `DESIGN.md:36` exists to
  prevent.
- **hex has stronger identity than OpenSpec.** `C-###`/`S-###` are
  "assigned when the artifact is written … stable within the artifact,
  never renumbered" and are "the join key convergence uses"
  (`protocol.md:341-344,:355-356`). OpenSpec's identity is
  `normalizeRequirementName = name.trim()` — the mutable header text.
  hex should not port machinery that exists only to repair that
  weakness.
- **No parser, no runtime, no binary** (`DESIGN.md:63-65`). Markdown
  rules only.
- **`hex-review` never commits** (`hex-review/SKILL.md:3,:278-282`) and
  **hex never pushes** (`protocol.md:408`; `DESIGN.md:165`). Whatever
  this phase writes is left in the working tree.
- **Nothing may break at `done`.** Plans that already reached `done`
  without a fold-back must stay valid, un-retro-folded, and silent.

## Industry Context & Research

**Research artifacts:**
[`openspec-framework-analysis.md`](../research/openspec-framework-analysis.md)
(primary — adopt/adapt/reject items 1–6, 12, 20–22, verified in this
round against the OpenSpec clone itself, not only the write-up),
[`spec-federation-multi-repo.md`](../research/spec-federation-multi-repo.md),
[`plan-schema-evolution.md`](../research/plan-schema-evolution.md).

**OpenSpec's mechanics, verified in source.**

| Mechanic | Where it lives in OpenSpec | What it buys |
|---|---|---|
| Four delta sections `## ADDED/MODIFIED/REMOVED/RENAMED Requirements` | `requirement-blocks.ts:155-158`, matched case-insensitively | A diff-shaped authoring language |
| Cross-section conflict matrix (5 rules) | `validator.ts:262-285`, duplicated verbatim at apply time `specs-apply.ts:163-193` | Same ID cannot be added and removed in one change |
| Fixed apply order RENAMED→REMOVED→MODIFIED→ADDED, original ordering preserved, new entries appended | `specs-apply.ts:244-350` | Deterministic, minimal-diff output |
| MODIFIED stale-base scenario guard | `specs-apply.ts:305-310` + `findMissingCurrentScenarios` `:410-443` — throws if the **live** block carries a `#### Scenario:` the incoming block omits | Catches exactly the silent-drop class |
| Prepare-all → re-validate-all → write-all | `archive.ts:420-489` (source comment: "Validate every rebuilt spec before writing any of them, so a late validation failure really does leave all targets unchanged"), duplicated in `specs-apply.ts:487-513` | A late failure leaves every file unchanged — **not portable, not ported**: it needs a runtime that owns the writes (C-415) |
| Idempotent date-prefix guard on the archive dir name | `archive.ts:38,:496` (`/^\d{4}-\d{2}-\d{2}-/`), added for issue #1309 | Re-archiving does not stutter the name |
| Requirement identity | `normalizeRequirementName(name) { return name.trim(); }` (`requirement-blocks.ts:17-19`) | …and this is the weakness `RENAMED` exists to patch |

**OpenSpec's regression, and why it is the most important prior art
here.** `openspec-parallel-merge-plan.md` names the root causes
("Replace-only semantics", "Missing base fingerprint", "Lack of
conflict UX") and proposes Phase 0 fingerprints + Phase 1 diff3 rebase.
None of Phase 0/1/3 exists in `src/`. What shipped is
`skills/openspec-sync-specs/SKILL.md`: "This is an agent-driven
operation … This allows intelligent merging … The delta represents
intent, not a wholesale replacement; Use your judgment to merge changes
sensibly." Its safeguards are four prose bullets, none of which is the
scenario-drop guard the deterministic path already had. So the shipped
skill is **weaker than the code it bypasses**. hex must not copy the
framing; it must copy the *guard* and state it as an obligation.

**Also load-bearing:** the research found OpenSpec's own CI never runs
`openspec validate` on its own artifacts — a validator nobody runs is
the code-layer twin of a prose rule nobody applies. Having code is not
the same as having enforcement; this weakens the "hex is uniquely
unsafe because it lacks a parser" reading without excusing it.

**LLM-performed structured merges — the state of the art.** No named,
adopted pattern exists for whole-document LLM merging. Every credible
2025–2026 project pairs the model with a deterministic narrowing pass
first: `drewmccormack/Forked` issue #5 proposes an `LLMMerger` fed
*only* the conflicting hunks of an existing three-way merge; LLMinus
uses kernel patch machinery to isolate a conflict region before the
model sees it; ConGra (arXiv 2409.14121) exists because conflict
resolution is a measurable open sub-problem. The transferable shape is
**narrow mechanically first, judge only the remainder** — which hex can
do without a parser, because the narrowing is an ID-set comparison a
model can perform and *print*.

**Rejected on the evidence:** OpenSpec item 3 (idempotent date-prefix
guard on an archive directory) is **not applicable** to this design,
because this design does not move the plan file (see
[Plan archive](#plan-archive-what-archive-means-here-c-410)). The bug it
guards against only exists for implementations that rename into a
dated directory.

## Considered Options

All five are shown against the same worked case: plan
`.agents/plans/plan_export.md` finishes; `/hex-review` approves;
the plan delivered `C-004` (new export component), amended `C-002`, and
dropped `C-003`; the project documents its specs at `docs/specs/`.

### Option A — Fold into the project spec home; terminal phase in `/hex-review` (recommended)

A new final-but-one phase inside `hex-review`, gated on
verdict = Approve **and** convergence = Converged, running immediately
after the convergence check (`hex-review/SKILL.md:235-240`) and before
Upkeep (`hex-review/SKILL.md:303-306`). It resolves the spec home from
`hex.md › Pointers`, builds the delta set in-message, self-checks,
writes, prints a mandatory Fold-Back block, then clears the active-plan
pointer in Upkeep.

Its cost is exact and stated: `hex-review`'s write surface grows beyond
the plan artifact for the first time (`hex-review/SKILL.md:3,:278-282`).

### Option B — Fold into the project spec home; terminal phase in `/hex-execute`

`hex-execute` already ends the working lifecycle, holds the merge and
the commit, and has an existing write-back habit (Living design record,
`hex-execute/SKILL.md:259-262`), so no contract is re-scoped.

Its defect is decisive and structural: `hex-execute` sets
`State: review`, never `done`, and hands off to review. Folding there
writes **unreviewed** content into the project's durable truth, before
the convergence check has run at all. Convergence exists precisely to
say "the delivered code does not cover these IDs"
(`protocol.md:493-507`) and caps the verdict at Needs Work when it
fires. A fold in `hex-execute` would fold aspiration; a subsequent
Needs Work verdict would leave the spec ahead of reality with no
compensating write path.

### Option C — Fold into the project spec home; new `/hex-archive` skill

A fifth orchestrator, invoked explicitly after review. Clean separation:
review keeps its never-writes contract literally intact, and archiving
becomes independently invokable on an old plan.

Its cost is an install surface — a fifth `SKILL.md`, its own classify /
overlays / tier files by the shipped skill layout
(`DESIGN.md:20-21`), its own meta-plan gate, its own handoff block, its
own entry in every README, catalog and bundle manifest — for a phase
whose entire body is "resolve a path, diff two ID sets, write, print".
It also makes the fold **optional by omission**: the lifecycle's most
important step becomes the one a user forgets to run, which is how
`done` became a dead end in the first place.

### Option D — hex-owned `.agents/specs/` store (rejected by the gate)

hex ships the destination: `spec.md`'s stated fallback
(`hex-init/assets/templates/spec.md:7`) is promoted to the canonical
home and every fold lands there, regardless of what the project already
documents.

Evidence in its favour, stated fairly: it is what the research
sketched (item 2, "apply the plan's deltas into
`.agents/specs/`"); it makes the fold **unconditional** — no
resolution step, no missing-home case, no per-project format
negotiation; every guard below becomes simpler because hex owns the
file's shape, including the `S-###` scenario section the human-authored
template lacks; and it is the only option under which hex could
guarantee the destination's structure matches its delta grammar.

Against: it is a second source of truth for project specs
(`DESIGN.md:32-39`), which the two-layer knowledge model exists to
forbid; the RST/Sphinx shop named in `DESIGN.md:46` gets a parallel
markdown spec tree it never asked for; and it inverts the
destination-is-the-user's-choice rule (`DESIGN.md:145-156`). **Settled
against by the decider at the meta-plan gate.** Scored below for the
record; not selected.

### Option E — Plan-archive only; no spec fold (rejected)

The terminal phase archives the plan (index entry, active-plan pointer
cleared) and writes nothing to any spec. Deltas, if recorded at all,
stay in the plan.

This is the honest null option, and it is not worthless: it closes the
never-cleared-pointer gap, costs no new write surface, and carries zero
corruption risk — the whole risk profile of this ADR disappears. But it
leaves the stated gap open: truth is still never updated, the next plan
is still authored against a stale spec, and hex still has no
diff-shaped vocabulary. It is what the design already does, plus
bookkeeping.

### Option F — Propose-only; hex never writes the spec file (rejected)

The same phase, the same delta grammar, the same census and stale-base
guard — but the output is a **proposed patch printed in the review
report**, never applied. The human pastes or hand-applies it.

Stated fairly, because it is the strongest option on the dominant
criterion: it makes a silent wrong write **structurally impossible**
rather than merely guarded. There is no write surface to re-scope, so
all three [constitution deviations](#constitution-deviations) disappear.
It is also the natural next step of this ADR's own "narrow mechanically,
judge only the remainder" principle — narrow all the way down, and the
model never touches the file at all. A wrong proposal fails **visibly at
apply time** (the patch does not apply, or the human reads it) instead of
silently on disk. Step 4's cleanliness precondition and C-409's revert
story both become unnecessary.

Against, and it is decisive for the same reason Option C lost: it makes
the fold **optional by omission and manual by construction**. Every fold
becomes a copy-paste chore at the end of a review, and a chore at the end
of a long run is a chore skipped — which is the mechanism by which `done`
became a dead end in the first place. Worse than Option C, because C's
omission is one forgotten command while F's is a per-entry manual edit,
performed by a tired human against a file the model just read and they
have not. Hand-applying a multi-contract patch is itself a write into
human-owned truth with **none** of steps 1–5 protecting it — the
corruption risk is not removed, it is relocated onto the least-protected
actor. And a printed patch has no idempotence (C-408): re-running prints
the same patch, with no way to tell whether it was already applied.

The honest summary: F is the safest *mechanism* and the least reliable
*lifecycle*. A is chosen knowing this, and pays for it with the census,
the halt semantics, and the never-commit backstop — which together make A
approximately as reviewable as F at the moment the human reads `git diff`,
while remaining automatic.

## Decision Outcome

**Chosen: Option A — fold into the project-documented spec home, as a
terminal phase inside `/hex-review`'s Approve path.**

### Weighted scoring

**Feasibility gate, applied before scoring** (same discipline as
`adr_0003`): the destination decision is settled — deltas fold into the
project's documented spec home, and hex ships no store. **Option D is
therefore infeasible** (it ships the destination) and **Option E is
infeasible** (it does not fold). Their totals are informational.

Weights: corruption-safety dominates, because the whole design is a
write path into human-owned files.

| Criterion | W | A | B | C | F | D† | E† |
|---|--:|--:|--:|--:|--:|--:|--:|
| Corruption safety (no silent wrong write) | 30 | 4 | 2 | 4 | 5 | 4 | 5 |
| Correct lifecycle position (folds only reviewed, converged work) | 20 | 5 | 1 | 4 | 2 | 4 | 3 |
| Contract disruption (lower = fewer amended contracts) | 15 | 3 | 4 | 5 | 5 | 3 | 5 |
| Install / surface cost | 15 | 5 | 5 | 2 | 5 | 4 | 5 |
| Closes the stated gap | 10 | 5 | 4 | 4 | 2 | 5 | 1 |
| Portability + no-parser fit | 10 | 5 | 5 | 5 | 5 | 5 | 5 |
| **Weighted total (max 500)** | | **436** | *296* | 401 | 410 | *401* | *406* |

† Infeasible against the settled destination decision; shown for
comparison only. Option F is feasible — it neither ships a destination
nor invents one — and is scored as a live contender, not for the record.

A leads C by 35, and the entire gap is Option C's install surface plus
its optional-by-omission failure. C's one real advantage — leaving
`hex-review`'s never-writes contract untouched — is bought back in A by
naming the amendment explicitly (C-401) rather than pretending the
write does not happen. B is not close: it folds before the gate that
decides whether the work is correct.

A leads F by 26, and the trade is stated rather than hidden: **F wins
outright on the dominant criterion** (5 vs 4 on corruption safety, worth
30 points) and loses on lifecycle position and gap closure, because a
patch a human must hand-apply is a fold that mostly does not happen and,
when it does, happens with none of steps 1–5 in force. Choosing A over F
is a deliberate purchase of automation with a residual the
"honest residual" paragraph below and the Data-integrity
NFR both state as the ceiling. If that residual is later judged
unacceptable in practice, F is the designed fallback — same grammar, same
census, same halts, minus step 6.

**Where the numbers understate a cost.** "Install / surface cost" scores
file and skill count, and on that measure A (5) beats C (2) decisively.
It does not price **blast radius onto a hot path**: A lands eleven halt
conditions, a mandatory report block and a seven-step envelope
permanently inside `hex-review/SKILL.md`, already the bundle's largest
dispatcher and by far its most-invoked, whose "never edits, never
commits" contract is currently one of its simplest guarantees. C would
quarantine all of that in a rarely-invoked fifth skill. Read A's 5 as
"few new files", not as "no new conceptual load on the hot path" — the
conceptual load is real, is permanent, and is the strongest argument C
has that the score does not capture. It does not close a 35-point gap,
but it narrows it.

**The lifecycle argument is the decision.** Only `hex-review` reaches
`done` (`hex-review/SKILL.md:230-233`), and only `hex-review` knows
whether the plan converged. A fold-back is *by definition* the write
that happens when delivered work has been judged to match its
contracts, and exactly one skill holds that judgment.

### Normative specification

Everything below is the adopted spec.

#### Delta grammar (C-403)

**Adopt `ADDED` / `MODIFIED` / `REMOVED`. Reject `RENAMED` as an
operation.**

The delta block is authored into the plan under a new
`## Spec Deltas` section (append-only, same discipline as the
convergence rows, `protocol.md:498-503`), and is the fold's only input.
**Its producer is `hex-execute`, at merge time, per work package
(C-419), and a plan carries exactly one block naming exactly one target
file (C-415).**

```markdown
## Spec Deltas

Target: docs/specs/spec_export.md   <!-- exactly one target per plan (C-415) -->

### ADDED
- C-004 — Export component. Streams rows to a writer; back-pressure via
  the writer's own flow control.
  <!-- full body, exactly as it will appear in the spec -->

### MODIFIED
- C-002 — Title: "Row source" → "Row source (paged)".
  <!-- full replacement body for C-002, restating every part it keeps -->

### REMOVED
- C-003 — superseded by C-004; no consumer remained at merge.
```

Rules:

1. **Every entry is keyed by an ID**, never by header text. An entry
   whose ID is absent from both the plan and the spec is malformed:
   halt (C-406).
2. **A title change is an ordinary `MODIFIED` body edit.** hex's
   identity is the ID, "stable within the artifact, never renumbered"
   (`protocol.md:341-344`), so a rewording cannot break a join the way
   it breaks OpenSpec's `trim()`-keyed map. `RENAMED` is therefore
   **not an operation**: no apply-order slot, no conflict-matrix rules,
   no `FROM:`/`TO:` pairing, and none of the unpaired-drop failure mode
   that pairing carries (`requirement-blocks.ts:291-312` silently
   discards a `FROM` overwritten by a second `FROM`, and can
   mis-attribute an orphan `TO` to a later unrelated `FROM`). The
   human-readable half survives as the optional `Title: "<old>" →
   "<new>"` first line of a `MODIFIED` entry. This is research item 20
   ("Reject … adopt RENAMED only as a human-readable delta operation")
   and item 21 ("Make it an error in hex's equivalent") applied
   together: hex has no unpaired case to error on, because it has no
   pairs.
3. **`MODIFIED` bodies are complete replacements**, not patches — and
   two guards make that safe: the stale-base guard (C-405) for lost
   IDs, and the **no-shrink guard (C-416)** for lost prose under a
   retained ID. A partial `MODIFIED` is precisely the "intelligent
   merging" OpenSpec regressed into and is not permitted. A `MODIFIED`
   entry must restate the contract's full body, including every part it
   keeps unchanged; a body that comes out shorter than the live one is
   a halt, not a judgment call (C-416).
4. **`REMOVED` carries the ID plus a one-line reason.** A removal with
   no reason is malformed: halt.
5. **Scope: `C-###` only, plus `S-###` when and only when the
   destination already carries `S-###` rows** — "carries" meaning
   locatable under the recognized ID-marker convention (C-413), not
   merely mentioned in prose. The shipped spec
   template has no scenario section — `S-###` are "assigned by the
   plan's UX-scenario table"
   (`hex-init/assets/templates/spec.md:18-21`) — and **inventing a
   section in a human-authored file is the exact silent-restructuring
   this ADR exists to prevent**. Unfoldable `S-###` deltas are reported
   in the Fold-Back block as `not folded — destination carries no
   scenario section`, never written and never dropped from the plan.

#### Who authors the deltas (C-419)

**`hex-execute` authors the `## Spec Deltas` block, at merge time, per
work package.** This is normative, not an implementation choice: the
safety envelope's only input must describe **delivered truth**, not
intention.

Reasoning, stated once so the implementing plan does not re-open it:

- A plan-time delta is an intention authored before any code exists. It
  goes stale exactly the way OpenSpec's parallel-authored deltas did,
  and hex already ships the correction path for plan-time claims — the
  Living design record (`hex-execute/SKILL.md:259-262`) updates the plan
  when delivery diverges from the design. A delta written at plan time
  would be a second such claim with no correction path of its own.
- The reviewed-content objection ("execution output is unreviewed") does
  not hold, because the block is not reviewed at the plan gate under
  either producer: the fold runs *after* `/hex-review`, and the review
  that matters for it is the convergence check plus the human reading
  `git diff`. Convergence already checks delivered code against the
  plan's IDs (`protocol.md:493-507`), so an execution-time delta is
  checked against the same join key the fold uses — a plan-time delta
  is not checked against anything.
- Per work package, appended at merge, matches the append-only
  discipline the convergence rows already use
  (`protocol.md:498-503`), so a multi-WP plan accumulates its deltas in
  merge order without any WP rewriting another's entry. Two WPs
  touching the same `C-###` produce two entries for one ID, which
  C-406's conflict matrix catches as a duplicate-within-section hit —
  the correct outcome, since a contract delivered twice needs a human
  to say which body is final.

**Producer obligation (the base-enumeration rule).** Before restating a
contract in a `MODIFIED` entry, the producer **reads the live
destination body and enumerates its sub-IDs and its non-blank line
count into the entry**, as a `Base:` line:

```markdown
### MODIFIED
- C-002 — Base: live {C-002.1, C-002.2, C-002.3}, 14 lines.
  Title: "Row source" → "Row source (paged)".
  <!-- full replacement body for C-002, restating every part it keeps -->
```

Without it, C-405 and C-416 have no well-formed base to compare against
and would be reduced to re-deriving one at fold time from a file the
delta may already have been written against blind. A `MODIFIED` entry
with no `Base:` line is malformed: halt (C-406). `ADDED` and `REMOVED`
entries carry no `Base:` line — there is nothing live to enumerate for
an `ADDED`, and a `REMOVED` names the whole contract. Under a federated
plan the fold is lead-scoped (C-415): a `MODIFIED` that will fold into
the lead reads its `Base:` from the **lead repo's** destination, not
from the satellite worktree the WP ran in, and a satellite-delivered
entry (`Repo` ≠ `.`) defers rather than folding, so it needs no lead
base.

#### One destination per fold (C-415)

**A plan carries exactly one `## Spec Deltas` block, naming exactly one
`Target:` file. Multi-file folds are an explicit non-goal.**

This replaces the "prepare-all / write-all atomicity" mechanic ported
from `archive.ts:420-489`. That mechanic is **not portable**, and
claiming it here would have been false: OpenSpec gets atomicity from a
runtime that can prepare N buffers and then write them under its own
control, aborting before the first byte. hex has no runtime. Its
"write-all" is N separate tool calls issued by a model, and an
interruption, a tool failure, or a refusal between call one and call
two leaves target one rewritten and target two untouched — a **silent
partial fold**, which is the exact failure class this ADR exists to
prevent, arriving through the mechanic that was supposed to prevent it.

The two honest options were a recoverable protocol (record a target
manifest and the pre-fold state in the plan before writing, so a
resumed run can tell which targets were written) and this one. This one
is chosen because it removes the failure instead of documenting a
recovery from it, and because the recoverable protocol buys back
multi-file folds at the cost of a second state-of-record ledger, read
by a resumed run that may itself be the interrupted pass. Ponytail
reading: the multi-file case has no scenario in this ADR, no evidence of
demand, and one destination per plan is the shape a plan already has
(one `Related Spec:` field).

Consequently:

1. **The write is a single whole-file write.** Step 5 prepares the
   complete rebuilt body of the one target in-message; step 6 writes it
   in **one** call that replaces the file's full contents. There is no
   sequence to be interrupted halfway, so there is nothing to make
   atomic — the file is either the old body or the new one.
2. **More than one `## Spec Deltas` block, or a block naming more than
   one `Target:`, is a halt** (C-406), printed as `not folded — this
   plan targets N spec files; one destination per fold`. The fix line
   names the remedy: split the plan, or fold the extra targets by hand.
3. **A plan whose contracts genuinely belong to several spec files**
   folds into the one target it names and reports every delta entry
   whose ID lives elsewhere as `not folded — ID lives outside <target>`,
   the same graceful per-entry defer C-403 rule 5 gives an unfoldable
   `S-###`. Nothing is written outside the single target, ever.
4. **Interruption between the spec write and the plan update** — the
   one remaining seam — is recovered by re-running `/hex-review <plan
   path>`. The destination census is the state of record for what was
   written (it is the file itself, not a claim about it), and C-408's
   idempotence plus C-417's fold receipt classify the re-run as a
   completed fold, a retry, or an edited plan. A resumed run therefore
   never needs to trust a ledger.
5. **A federated plan folds lead-scoped.** Under a plan carrying a
   `Repo` column ([adr_0004](adr_0004_cross_repo_federation.md)), target
   resolution (C-404), containment (C-418) and the census (C-405, C-416)
   all run **in the lead repo**, against the lead's `hex.md › Pointers`
   — which adr_0004 C-318 makes the only `hex.md` a federated run
   resolves. The one `Target:` is therefore a lead file, and C-415's
   single-target rule is untouched. Every delta entry originating from a
   work package whose `Repo` ≠ `.` is reported `not folded — delivered
   in <repo>; fold by hand into that repo's spec` and left in the plan;
   only entries delivered in the lead (`Repo` = `.`) fold. This is the
   same graceful per-entry defer clause 3 gives an ID that lives outside
   the target, applied to the repo dimension — without it a
   satellite-delivered contract would either fold into the lead's spec
   with no repo attribution or, via clause 3, defer forever against a
   lead target that can never carry it.

#### Where the phase lives (C-402)

A new **Phase: Fold-Back** inside `hex-review`, positioned after the
convergence check and before Upkeep. It runs **only** when all four
hold; otherwise it does not run and says so in one line:

1. the target traces to a plan artifact (`hex-review/SKILL.md:227-233`);
2. the verdict is **Approve**;
3. the convergence check reported **Converged**
   (`protocol.md:504-507`);
4. the run is about to write the plan's **terminal review state** —
   `done`, or `landing` for a plan carrying a `Repo` column
   ([adr_0004](adr_0004_cross_repo_federation.md) C-324): at `landing`
   the work is merged, reviewed and converged and only trunk landing
   remains, so the deltas are final and safe to fold. Keying on `done`
   alone would strand every federated plan — adr_0004's Approve writes
   `landing`, never `done`, and `done` is reached later by
   `/hex-execute`'s upkeep, which has no Fold-Back phase — so the plan
   would never fold.

Order is not cosmetic: convergence is the mirror of this phase.
Convergence asks *does the delivered code cover the plan's IDs* and
appends gaps to the plan (plan ← code). Fold-back asks *does the spec
describe what the plan delivered* and appends deltas to the spec
(spec ← plan). Same join key, opposite direction. **Convergence runs
first, always**, because an unconverged plan cannot reach Approve at
all, and folding an incompletely delivered plan would write aspiration
into truth.

#### How an ID is recognized in the destination (C-413)

Every mechanic above and below — the census, the stale-base guard, the
self-check, the write's ordering rule — presumes the fold can **locate a
`C-###` inside the destination file**. hex ships a delta grammar, not a
destination format, so that presumption has to be discharged explicitly
rather than inherited from hex's own template. This is the "per-project
format negotiation" Option D avoids by owning the file; Option A owes it,
and this is where it is paid.

**The default marker shape.** A destination is fold-compatible when every
contract it carries is introduced by a markdown ATX heading whose text
begins with the bare ID, in the shape the shipped template already uses
(`hex-init/assets/templates/spec.md:56`):

```
### C-001 — [Title]
```

Concretely, a heading matching `^#{1,6}\s+(C|S)-[0-9]+\b`. The
contract's **body** is everything from that heading to the next heading
of the same or shallower depth, or end of file. That span is what a
`MODIFIED` replaces, what `REMOVED` deletes, and where an `ADDED`
contract is appended. Sub-IDs for the stale-base guard (C-405) are every
`C-###`/`S-###` occurring anywhere within that span, marker or inline.

**Project override.** A project whose specs use a different but still
mechanical marker records the regex plus its body-extent rule in
`hex.md › Preferences` — **user-owned** config, written only by
`/hex-init` with consent and **never edited by a run**
(`DESIGN.md:109-112`) — not in `hex.md › Pointers`, whose entries are a
skill-managed cache of *locations* that any Upkeep step rewrites freely
(`DESIGN.md:72-79`). An ID-marker regex is authoritative user
configuration, not a location: recording it in a cache a re-point may
clobber would silently delete it, and the fold would then fall back to
the default against a file that does not match it — the exact silent
restructuring this ADR exists to prevent. The Pointers spec-home entry
carries only a pointer to it:

```
# hex.md › Preferences  (user-owned; only /hex-init writes, runs never edit)
Spec ID marker: ^#{1,6}\s+(C|S)-[0-9]+\b
  (body = heading to next heading of same or shallower depth)

# hex.md › Pointers  (skill-managed location cache)
Spec home: docs/specs/ — ID marker: see Preferences › Spec ID marker
```

The recorded regex is the only alternative accepted. hex does not infer
one, does not relax the default on a near-miss, and does not fall back to
matching a bare ID in running prose — an ID mentioned in a sentence is a
cross-reference, not a contract boundary, and treating one as the other
is exactly the silent restructuring this ADR exists to prevent.

**Verification, before the census can run.** C-404 step 5 checks that
every ID the deltas touch which is expected to be live is locatable under
the resolved convention, and the Fold-Back block **prints the convention
it used and its source** (`default` or `hex.md › Preferences`). If the
destination is not fold-compatible — an RST/Sphinx spec tree
(`DESIGN.md:46`), an asciidoc file, a table-of-contracts with no
per-contract heading, or a markdown file whose contracts carry no IDs at
all — the fold **halts** with
`not folded — destination format not fold-compatible (<file>): no
recorded ID marker and no <depth># C-### headings found`, and the fix
line names both remedies: record an ID-marker regex in `hex.md ›
Preferences`, or fold by hand. hex never guesses at a destination's
structure, and never rewrites a file whose shape it cannot enumerate.

#### Destination resolution (C-404)

1. Read `hex.md › Pointers` for the spec/plan/ADR conventions entry
   (`memory.md:35,:47-57`).
2. **Verify on consumption** (`memory.md:122-124`): the pointed-at
   location exists and actually holds specs. On a miss, re-detect from
   project context — including `audit.md:36-40`'s de-facto glob
   (`docs/specs*`, `specs/`, an existing `.agents/` tree) — and
   re-point in the same run.
3. Select the target file, in this order:
   1. the spec the plan was planned from, when the plan's Overview names
      one in its `Related Spec:` field (added to `plan.md` by this
      decision, precisely so this path is reachable) **and that path
      passes the containment check (C-418)**;
   2. else the file in the spec home carrying the `C-###` the deltas
      touch;
   3. else — the **pure-`ADDED` case**, where no delta entry names an
      existing ID and rule 3.2 therefore yields zero candidates by
      construction — the file in the spec home whose name matches the
      plan's slug, when exactly one does (`plan_export.md` →
      `spec_export.md`); this is a name match, not a content guess, and
      the Fold-Back block prints it as `target: <file> (resolved by plan
      slug)` so a reader can reject it on sight.
4. **More than one candidate target is ambiguity: halt** (C-406). Never
   fold into a guess.
5. **Zero candidates degrades, it does not halt the run.** When rules
   3.1–3.3 all yield nothing — a brand-new component in a project with a
   documented spec home but no matching file, the single most common
   real-world plan — the phase reports
   `not folded — no destination file for a new component; name one with
   Related Spec: in the plan, or create <spec home>/spec_<slug>.md`,
   leaves the deltas in the plan exactly as C-407 does for a missing
   home, and keeps `State: done`. hex **creates no spec file**, so a new
   component's first spec file is a human's (or `/hex-init`'s) to
   materialize; the fold lands on the next `/hex-review` once it exists.
   This is the same graceful per-entry defer C-403 rule 5 gives an
   unfoldable `S-###`, applied to the structurally identical case rather
   than to a different one.
6. **Confirm the ID-marker convention (C-413)** for the resolved file and
   print it. Not fold-compatible → halt (C-406).
7. **Confirm containment (C-418)** for the resolved file, and confirm it
   again immediately before the write.

#### Containment: the resolved path never leaves the spec home (C-418)

Rule 3.1 reads a path out of the plan — a model-written field in a
model-written artifact. Without a boundary check, a malformed or
invented `Related Spec:` (`../../src/config.ts`, an absolute path, a
symlink pointing out of the tree) redirects the whole write into an
arbitrary project file, and every other guard in this design still
passes: the census greps *that* file, cleanliness checks *that* file,
the self-check compares *that* file. Containment is the one guard
standing between the fold and the rest of the repository, so it is a
**hard refusal**, never a warning, and it is not satisfied by the path
merely looking plausible.

**The check.** Let `home` be the spec home resolved and verified in
steps 1–2, and `target` the file selected in step 3. The fold proceeds
only when all of these hold:

1. `target` is **inside `home`** — after normalizing both to
   repository-relative paths, `target` begins with `home` plus a path
   separator. Equality is not containment: `home` is a directory, the
   target is a file within it.
2. `target` contains no `..` segment before or after normalization, and
   is not absolute.
3. `target` is a **regular file that already exists**, not a symlink and
   not a directory. hex creates no destination file (C-407), so a
   non-existent target is the zero-candidate defer, not a write.
4. `target` is **tracked by git** — discharged by the same evidence
   discipline as everything else mechanical (C-414), by pasting the
   output of:

   ```
   git ls-files --error-unmatch <target>
   ```

   run **in the lead repo** under a federated plan — the fold is
   lead-scoped and the target is a lead file (C-415). A file git does not
   track cannot be reviewed as a diff or reverted by `git checkout --`,
   so the entire revert story (C-409) does not hold for it.

**Re-verified at write time.** The check runs at resolution (step 7
above) **and again as the first action of step 6**, immediately before
the single whole-file write, in the same pass as D-4's cleanliness
re-check. Resolution and write are separated by four steps of model
work; re-confirming a one-line prefix comparison there costs nothing and
closes the window in which the target the model writes is no longer the
target it resolved.

**On failure: halt, and name what was refused.** Any containment failure
is a C-406 halt with the resolved path printed verbatim:

```
not folded — resolved target escapes the documented spec home
  target: ../../src/config.ts   (from plan § Overview Related Spec:)
  spec home: docs/specs/  (hex.md › Pointers)
  Fix: point Related Spec: at a file inside docs/specs/, or clear it
  and let resolution fall through to rule 3.2.
```

The Fold-Back block prints the containment verdict on **every** run, not
only on failure (C-411), so a reader sees `contained: docs/specs/
spec_export.md ✓ (git-tracked)` on the happy path and its absence is
itself the alarm.

#### The no-documented-spec-home case (C-407)

Fully specified, because it is the common case — this repo's own
`CLAUDE.md` documents plans, ADRs and research and **names no spec
location**, and `memory.md:50-51`'s own example Pointers entry says
"Plan / ADR conventions" with no spec path.

When step 2 above finds no documented spec home and de-facto discovery
finds no practiced one:

- **The fold does not happen, and no destination is invented.** hex does
  **not** create `.agents/specs/`, does not promote the
  template's fallback path (`spec.md:7`), and does not write to
  `README.md` or any doc that merely looks spec-shaped.
- **The deltas are preserved, not discarded.** The `## Spec Deltas`
  block already lives in the **plan**, written there at merge time by
  `hex-execute` (C-419) — a hex-owned artifact that already exists, so
  no new store is created and no new convention is introduced. The fold
  leaves it untouched and its `Target:` reads `unresolved`.
- **`State: done` is still written.** A missing spec home is a project
  configuration fact, not a review failure; it must not cap the
  verdict.
- **The handoff says so, in the shape `/hex-init` already uses**
  (research items 9 and 29 — name the fix and enumerate the accepted
  values):

  ```
  Fold-back: not performed — this project documents no spec home.
    Fix: run /hex-init to document one. It will propose an existing
    practiced location if it finds one (docs/specs/, specs/), and
    .agents/specs/ only as the last resort, with your consent.
    The deltas are recorded in <plan path> § Spec Deltas and fold on
    the next /hex-review <plan path> once a home is documented.
  ```

- **Recovery is one command and is idempotent.** After `/hex-init`
  records a spec home, `/hex-review <plan path>` re-runs the phase
  against the recorded deltas; C-408's idempotence makes a
  double-invocation a no-op.
- **Who creates the file's first byte: never fold-back.** The write step
  amends an existing file and nothing else — it creates no directory
  (stated above) and no file. When the recorded home is new and empty,
  the destination file is materialized by **`/hex-init`**, using the
  copy-only-if-absent mechanism it already uses for every shipped
  template: it writes `<spec home>/spec_<slug>.md` from
  `hex-init/assets/templates/spec.md`, with consent, as part of recording
  the home. Recording a home therefore has two outputs — the Pointers
  entry and, when the home is empty, a seeded spec file. Only then does
  the next `/hex-review` have a target to amend. If the user declines the
  seed, the fold reports C-404 rule 5's zero-candidate line and defers
  again; it never compensates by creating the file itself.
- `/hex-init` gains one audit item — "spec home documented?" — as a
  **conditional** question, asked only when a plan with an unresolved
  `## Spec Deltas` block exists or the conventions entry names plans
  and ADRs but no specs. Nothing is asked of a project that never
  planned anything.

#### The safety envelope

Written as an ordered procedure. **Steps 1–5 produce no writes.** The
first byte is written at step 6.

**Evidence is command output, not narration (C-414).** Steps 1, 4 and 5
are the mechanically expressible part of this envelope, and a step that
merely *says* it ran is produced by the same generative pass that could
have skipped it — a self-asserted compliance claim, which is precisely
the failure mode prose-only traceability is known for. Those three steps
are therefore discharged by **literal shell calls whose raw output is
pasted into the Fold-Back block**, not summarized in it. `git` and `grep`
are generic tools every harness already runs (`adr_0001` C-003; this
repo's own `grim build` verification step is the same pattern), so this
adds no parser, no runtime and no binary, and does not touch
`DESIGN.md:63-65`. It closes the residual for ID presence, ID counts and
dirty state — the subset that can be counted — and leaves every semantic
judgment (is this `MODIFIED` body a faithful edit) exactly where the rest
of this ADR puts it: on the model, backed by halt. A Fold-Back block
carrying a prose assertion where a command transcript belongs is a spec
violation (C-411), and unlike a skipped guard it is visible to a reader
at a glance.

1. **Census (mechanical, printed as command output).** Enumerate two ID
   sets: every `C-###`/`S-###` currently in the destination file
   (`live`), and every ID the delta block names (`incoming`). `live` is
   produced by a literal call, using the recognized marker convention
   (C-413):

   ```
   grep -nE '^#{1,6}[[:space:]]+(C|S)-[0-9]+\b' <target>
   ```

   and its **output is pasted verbatim** into the Fold-Back block, not
   restated. `incoming` is read from the delta block, which is in-message
   and needs no call. **Both sets appear before any write.** This is the
   narrowing pass the LLM-merge state of the art requires, and it is the
   single artifact that makes a later silent drop auditable.
2. **Conflict matrix (C-406).** An ID appearing in two delta sections
   is a conflict: `ADDED ∩ MODIFIED`, `ADDED ∩ REMOVED`,
   `MODIFIED ∩ REMOVED`, or twice within one section. hex needs four
   rules, not OpenSpec's five (`validator.ts:262-285`), because the
   fifth — `MODIFIED` referencing a `RENAMED` old name — cannot exist
   without `RENAMED`. Any hit: **halt**.
3. **Stale-base guard (C-405) — the ID-loss guard.** For every
   `MODIFIED` entry, compare the `live` sub-IDs the destination
   currently carries under that contract against those the incoming
   body restates. **Any live ID the incoming body drops halts the
   fold**, with both sets printed. This is
   `findMissingCurrentScenarios` (`specs-apply.ts:305-310,:410-443`)
   ported as an obligation, and it is the guard OpenSpec's own shipped
   skill dropped.

   **What it does not catch, and what does.** C-405 compares ID sets,
   so it detects *ID-presence loss* and nothing else. A `MODIFIED` body
   that names every live sub-ID while quietly weakening, narrowing or
   deleting the prose attached to them passes this guard cleanly — the
   census is ID-shaped and would show no difference. That case is not
   left to `git diff`; it is caught mechanically by the no-shrink guard
   below.

   **Step 3b — no-shrink guard (C-416), the prose-loss guard.** For every
   `MODIFIED` entry, compare the **non-blank line count of the live
   body** against that of the incoming body. Both are counted, not
   estimated, by a literal call over the body span established by C-413
   (heading to next heading of same or shallower depth):

   ```
   awk 'NR>=<start> && NR<=<end>' <target> | grep -c '[^[:space:]]'
   ```

   whose output is pasted into the Fold-Back block beside the incoming
   body's count (C-414, C-411).

   **The trigger is exact: `incoming < live` halts the fold.** Not
   "significantly shorter", not "materially weakened" — any reduction
   at all, by one line. There is no tolerance band and no judgment
   call, because a threshold a model estimates is a threshold a model
   can talk itself past, and the whole point of this guard is that it
   is countable. Equal or greater is a pass; C-405 has already
   established that no ID was dropped.

   **Why halt rather than confirm.** The alternative — print a
   before/after summary and ask the human — needs a consent point this
   design does not have and the single-gate rule
   (`protocol.md:45-49`) does not permit mid-run (see
   [Constitution deviations](#constitution-deviations), row 3). Halting
   is the available safe action, and it is cheap: halt means write
   nothing and keep the deltas in the plan (C-406), so nothing is lost.

   **A legitimate shrink is folded by hand.** A contract whose scope
   genuinely narrows — a requirement deleted on purpose, a paragraph
   correctly removed — cannot be expressed as a `MODIFIED` this phase
   will write. That is deliberate. The two supported routes are: model
   the deletion as a `REMOVED` of the sub-contract with its mandatory
   reason (which C-405 then expects and permits), or edit the spec by
   hand. The halt line names both:

   ```
   not folded — MODIFIED C-002 shrinks the requirement: live 14 lines →
     incoming 4 lines, no ID dropped
     Fix: restate the full body including the parts C-002 keeps, or
     express the deletion as REMOVED with a reason, or edit
     docs/specs/spec_export.md by hand.
   ```

   **The remaining ceiling, honestly.** Line count is a proxy. A body
   that keeps its length while inverting a requirement's meaning
   ("streams rows" → "buffers rows") passes both guards, and no
   count-based rule can see it. What is now excluded is the whole
   *deletion* class — the failure OpenSpec actually shipped — leaving
   only same-size semantic drift, which C-411's per-ID excerpt surfaces
   in the report and `git diff` catches on an uncommitted file. The
   Data-integrity NFR states that as the ceiling.
4. **Destination cleanliness (command output).** The target file must be
   unmodified relative to `HEAD`. Discharged by a literal call whose
   output is pasted into the block:

   ```
   git status --porcelain <target>
   ```

   Empty output is the pass; any output **halts**, and the output itself
   is the printed reason. Since hex-review never commits,
   revert-by-discard is the user's only undo, and discarding would
   destroy their uncommitted work along with hex's.
5. **Prepare and self-check the one target** (the portable half of
   `archive.ts:420-489`; the multi-file half is a non-goal, C-415).
   Build the complete rebuilt body of the single target in-message and
   self-check it — IDs unique, every `live` ID either present or
   explicitly `REMOVED`, ordering preserved. The ID half of that check
   is mechanical and is discharged by command output, not assertion:
   write the rebuilt body to a scratch path and run the **same** census
   command against it, then paste both transcripts adjacently so the
   reader compares two `grep` outputs rather than trusting a claim that
   they match. A scratch file is not a write to the destination and does
   not breach "steps 1–5 produce no writes"; it is deleted after the
   check. Any failure: **halt, write nothing.**
6. **Write, once.** Immediately before writing, re-run the two
   one-line checks whose truth may have changed since steps 3–4 —
   containment (C-418) and `git status --porcelain <target>` — and
   paste both transcripts; either failing is a halt with nothing
   written. Then write the prepared body in **exactly one whole-file
   write** that replaces the target's full contents (C-415): no
   incremental edits, no per-section passes, nothing that can stop
   halfway and leave the file part-folded. The rebuilt body is composed
   in fixed order `REMOVED → MODIFIED → ADDED` (`specs-apply.ts:244`,
   minus the `RENAMED` slot), **ordering preserved**: an existing
   contract keeps its position even when modified; new contracts append
   at the end in delta order. Then append the fold receipt to the
   plan's `## Spec Deltas` block (C-417).
7. **Print the Fold-Back block** — mandatory, emitted even when the
   phase did not run, in the shape of `adr_0003` C-207's disclosure
   requirement.

**Halt semantics (C-406).** Halt means: **write nothing, keep
`State: done`, keep the deltas in the plan, print the reason and the
fix, continue to Upkeep and the handoff.** A halted fold never fails
the review, never re-opens the verdict, and never attempts a repair
pass. The nearest precedent is the merge-conflict playbook
(`protocol.md:398-404`: judge semantically, at most **one** fix pass,
still failing → halt and escalate), and this phase deliberately allows
**zero** fix passes: there, the fix pass edits code hex just wrote on a
branch it owns; here, the target is human-authored truth in the working
tree, so the cheapest correct move is always to stop.

**Idempotence (C-408).** Re-running against the **same, unchanged**
plan produces a byte-identical destination. An `ADDED` whose ID is
already present with an identical body is a no-op; with a different
body it is a conflict → halt. A `REMOVED` whose ID is already absent is
a no-op. A `MODIFIED` whose body already matches is a no-op. No
date-stamping, no rename, no append-on-rerun — which is why OpenSpec's
date-prefix guard (`archive.ts:38,:496`) has no analog to port. What
makes "same, unchanged" checkable rather than assumed is the fold
receipt.

**Fold receipt, and what a re-run means (C-417).** C-408 alone defines
idempotence only for an *identical* delta. It says nothing about the
case that actually occurs: the plan is edited between runs — a
`MODIFIED` body rewritten, a paragraph added or cut — while every ID
stays the same. Replaying it would overwrite the spec with a body no
one folded and no one reviewed, and the destination would look
perfectly well-formed afterwards. A re-run must therefore be
*classified*, not replayed.

**The receipt.** On a successful write, step 6 appends one line per
touched ID to the plan's `## Spec Deltas` block — append-only, same
discipline as the convergence rows:

```markdown
Folded: 2026-07-20 → docs/specs/spec_export.md
  C-002 written: {C-002.1, C-002.2, C-002.3}, 17 lines
  C-004 written: {C-004}, 9 lines
  C-003 removed
```

This is the **base identity** a resumed run compares against. It is
deliberately not a hash: hex has no hasher, and a fingerprint a reader
cannot compute is the Phase 0 OpenSpec designed and never shipped. Sub-ID
set plus non-blank line count is comparable **by reading**, is produced
by the same two commands the census and C-416 already run, and — given
C-416 forbids any shrink — is sufficient to distinguish the three cases
that matter.

**The comparison rule.** On any run that finds a `Folded:` receipt for
the target, before step 5:

| Live destination vs. receipt | Incoming delta vs. receipt | Verdict |
|---|---|---|
| matches | matches | **Already folded.** No-op, `no change — already folded`, C-408's happy re-run (S-404). |
| does **not** match | matches | **Destination moved on** since the fold. Not a retry: re-derive against the current live body — C-405 and C-416 run normally against it and will halt if the delta is now stale. |
| matches | does **not** match | **The plan was edited after folding.** **Halt.** |
| does not match | does not match | **Halt** — both sides moved; nothing can be inferred. |

**On the edited-plan halt**, which is the case X3 names:

```
not folded — plan delta changed since the recorded fold
  C-002 receipt: {C-002.1, C-002.2, C-002.3}, 17 lines
  C-002 incoming: {C-002.1, C-002.2, C-002.3}, 11 lines
  A re-run replays a fold; it does not apply a revision.
  Fix: the spec is now the base. Author a fresh delta against the
  current docs/specs/spec_export.md under a new ## Spec Deltas block,
  or edit the spec by hand.
```

The rule this encodes: **a re-run is a retry, never a revision.** A
revision is a new fold against a new base, and the base it is authored
against is the spec as it now stands — which is exactly the state the
receipt lets a reader confirm. A plan with no receipt (every plan
before the first successful fold, and every legacy plan, S-410) is
unaffected: no receipt, no comparison, ordinary first fold.

**Ceiling, stated.** Two edits that preserve both the sub-ID set and the
non-blank line count are indistinguishable to the receipt and replay as
a retry. That is the same same-size-drift class C-416 leaves open, and
it is bounded by the same backstop: the write is uncommitted and the
Fold-Back block prints both counts.

**Revert (C-409), stated precisely.** hex-review never commits
(`hex-review/SKILL.md:3,:278-282`) and hex never pushes
(`protocol.md:408`). Therefore:

- Every spec write lands **unstaged in the working tree**. `git diff`
  is the review of the fold; `git checkout -- <spec file>` is the
  complete undo, exact because of step 4's cleanliness precondition.
- The plan's `## Spec Deltas` block and its `State: done` are ordinary
  working-tree edits to a tracked file, reverted the same way.
- **There is no hex command that undoes a fold.** Reverting is a git
  operation the human performs, and the handoff block says so. hex
  offering an "unfold" would be a second write path into the same
  human-owned file with none of steps 1–5 protecting it.

#### Plan archive: what "archive" means here (C-410)

The plan is **not moved and not renamed.** `State: done` is the archive
marker; Upkeep clears the `hex.md › Memory` active-plan pointer — the
first place in the bundle that ever clears it — and records the plan
plus its fold target in the artifact index (`memory.md:68-74`).

**Keyed on the terminal review state, not `done` literally.** The
pointer clear and the index write have the same `done`-only keying the
Fold-Back gate had, so the same extension applies: for a plan carrying a
`Repo` column ([adr_0004](adr_0004_cross_repo_federation.md) C-324) the
state `hex-review` writes is `landing`, and archive-marking, pointer
clear and index write happen then — the same terminal-review-state
condition C-402 precondition 4 resolves, so the phase and its Upkeep
stay together. The satellite `Federation lead:` locks are a **separate**
mechanism (adr_0004 C-313/C-324) that correctly persists past `landing`
to `done`; the active-plan pointer cleared here is not that lock and
does not gate trunk landing.

Moving the plan to `plans/archive/YYYY-MM-DD-<slug>/` was considered
and rejected: it breaks every link that points at the plan (Pointers,
Memory, ADR cross-links, prior handoff blocks) for a benefit —
directory tidiness — that a `State:` field already provides, and it
imports the double-date-prefix bug class OpenSpec had to patch
(`archive.ts:38`, issue #1309). No move, no guard needed.

#### Mechanic → failure → visibility

The required table. "Silent failure" is what happens when the model
skips the rule; "made visible by" is the only thing standing between
that and a corrupted spec.

| Mechanic | Silent failure if skipped | Made visible by |
|---|---|---|
| Census (step 1) | Model works from the delta alone, never reads the live file; a whole section is overwritten | The pasted `grep` transcript for `live` plus the `incoming` set — a missing transcript is itself the alarm, a present one is re-runnable in one line, and the pair lets a reader diff by eye |
| ID-marker convention (C-413, step 6 of C-404) | Model invents a structure for a destination whose shape it never established — treats a prose cross-reference as a contract boundary, or rewrites an RST file as markdown | The printed convention and its source (`default` / `hex.md › Preferences`), and the `grep` transcript from step 1: zero matched headings on a file that supposedly carries the IDs is unmissable |
| Malformed entry — no ID, or `REMOVED` with no reason (C-403 rules 1, 4) | An entry keyed by header text folds by fuzzy title match, reviving OpenSpec's `trim()`-keyed failure inside hex; an unexplained removal deletes a live contract with no record of why | Per-ID disposition in the block: an entry with no ID has no row to print, and a `REMOVED` row's reason field is mandatory and visibly empty when skipped |
| No invented `S-###` section (C-403 rule 5) | The fold adds a scenario section to a human-authored spec that never had one, silently restructuring the file it was asked to amend | The census transcript shows zero live `S-###` headings, so any `S-###` in the written diff is a structure the block's own evidence says did not exist |
| Conflict matrix (step 2) | An ID both added and removed resolves by apply order; the user sees a plausible file | Printed per-ID disposition (`C-002 modified`, `C-003 removed`) — a conflicting ID appears twice |
| Stale-base guard (step 3) | **The corruption case.** A `MODIFIED` body that forgets a live sub-requirement deletes it; the file still parses, still reads well, and nobody notices until the next plan is written against it | The printed dropped-ID list on halt; and, when the model skips even that, `git diff` on an uncommitted file — which is why never-commit is a safety property here, not just a contract |
| Destination cleanliness (step 4) | Fold mixes with the user's uncommitted edits; `git checkout --` then destroys their work | The pasted `git status --porcelain <target>` transcript — empty output *is* the pass, so there is no summary to fake, only output to omit |
| No-shrink guard (step 3b, C-416) | **The other corruption case.** A `MODIFIED` body keeps every sub-ID and guts the prose under them; C-405 passes, the file reads well, the requirement is gone | The two pasted `grep -c` counts, live and incoming — a reduction is arithmetic, not a judgment, and the halt is triggered by the counts themselves |
| Single destination + one whole-file write (step 5–6, C-415) | Multi-target fold interrupted between writes; file one folded, file two stale, report claims atomicity | More than one target halts before step 5; the write is one call, so there is no partial state to be silent about — and the block prints `targets: 1` |
| Containment re-verified at write time (C-418) | A malformed `Related Spec:` redirects the whole fold into an arbitrary project file, with every other guard passing against the wrong file | The printed containment verdict with the resolved path and its `git ls-files` transcript, on every run, not only on failure |
| Fold receipt (C-417) | An edited plan is replayed as a retry and overwrites the spec with an unreviewed body | The receipt in the plan vs. the live census — a three-line comparison a reader performs by reading, and a mismatch halts |
| Fixed apply order + ordering preserved (step 6) | Contracts reshuffle; diff noise hides the real change | The diff itself — a fold that reorders is immediately visible as a large diff on a small change |
| Idempotence (C-408) | A re-run duplicates `ADDED` entries | Duplicate IDs fail step 5's self-check; and the census shows the ID already `live` |
| Halt-and-escalate (C-406) | Model guesses at an ambiguous target and folds into the wrong file | Printed target resolution with its source (`hex.md › Pointers` / re-detected / unresolved) |

**The honest residual.** C-414 and C-416 narrow this materially but do
not eliminate it. Five checks — the census, destination cleanliness,
containment, the ID half of the self-check, and the live/incoming line
counts — are discharged by pasted `git`/`grep`/`awk` transcripts, so for
those a skipped step no longer produces a plausible sentence: it produces
either a missing transcript or a fabricated one,
and a fabricated command transcript is a categorically louder failure
than a fabricated summary (it is checkable by re-running one line). What
remains genuinely model-borne is a narrower semantic set: the conflict
matrix (step 2), same-size meaning drift in a `MODIFIED` body that
neither drops an ID (C-405) nor shortens the body (C-416), and ordering
preservation at step 6.
For those, every entry in the right column is *also* produced by the same
instruction-following pass that could skip the left column. A model that
skips the guard may also skip its printed line, and the Fold-Back block
would then simply be absent or optimistic. hex cannot close this without
the code layer `DESIGN.md` declines to build — the industry's answer,
separating edit *generation* from a differently-incentivized *application*
pass, needs exactly that layer. What it can do — and this design does — is
make
**git the backstop of last resort**: the phase never commits, so every
write it makes is a working-tree diff the human sees before it becomes
history. That is a weaker guarantee than validation and a stronger one
than OpenSpec's shipped skill offers, and the Data-integrity NFR states
it as the ceiling, not as a caveat.

### Consequences

**Positive:**
- **`done` stops being a dead end.** The terminal state finally does
  something: the active-plan pointer clears (C-410, the first clear in
  the bundle) and the delivered, reviewed, ID'd contracts fold into the
  project's durable spec instead of leaving it describing the
  pre-work world.
- **Spec truth tracks merged work.** The next plan is authored against a
  spec that reflects what shipped, not one the last plan silently
  outran — the largest structural gap the OpenSpec teardown named.
- hex gains a diff-shaped vocabulary (`ADDED`/`MODIFIED`/`REMOVED`) for
  spec change that it did not have before, reusable by anything later
  that needs to describe a delta.

**Negative:**
- **hex now writes a project-owned file outside `.agents/` — the
  highest-stakes write in the bundle.** `hex-review`'s once-simple
  "never edits, never commits" contract grows a write surface
  (C-401), landing on the bundle's hottest, most-invoked path.
  Mitigated, not eliminated: exactly one resolved target (C-415), a
  containment boundary re-verified immediately before the write
  (C-418), an existing git-tracked file only, and **never a commit**
  (C-409) so every write is a reviewable, revertible working-tree diff.
- Eleven halt conditions and a mandatory report block are new
  conceptual load a reader of `hex-review` must now hold.
- The residual is real: no count-based guard sees a same-size meaning
  inversion (the Data-integrity NFR states this as the ceiling).

**Neutral:**
- The fold is **deferred, not failed**, wherever it cannot land safely:
  no documented spec home (C-407), zero candidate targets (C-404 rule
  5), an unfoldable `S-###` (C-403 rule 5), and — for a federated plan
  (adr_0004) — every delta delivered in a satellite (`Repo` ≠ `.`),
  which is reported and left in the plan for a hand-fold into that
  repo's spec (C-415). A defer keeps `State` at its terminal review
  value and loses nothing; the deltas wait in the plan for the next
  `/hex-review`.

## Component contracts

Numbered `C-4xx` — the next free range (`adr_0001` used `C-00x`,
`adr_0002` `C-1xx`, `adr_0003` `C-2xx`, `adr_0004` `C-3xx`). UX scenarios
`S-4xx` per `protocol.md` § Traceability IDs.

| ID | Contract | Home / changed file |
|---|---|---|
| **C-401** | **hex-review's write surface is re-scoped, explicitly.** Its writes become: the plan Status block, the append-only convergence rows, the fold receipt it appends to the plan's `## Spec Deltas` block (C-417 — the block itself is authored by `hex-execute`, C-419), and — under the Fold-Back phase's four preconditions only — the resolved spec file. It still never edits the code or diff under review and still never commits. The description line and the Constraints bullet both change; a fold is never inferred from silence. | `hex-review/SKILL.md:3`, `:278-282`, `:303-306` (`:225-233` unchanged — the phase is inserted around it) |
| **C-402** | **Phase placement** — Fold-Back runs inside `hex-review`, after the convergence check and before Upkeep, gated on: target traces to a plan, verdict Approve, convergence Converged, `State` about to become its **terminal review state** — `done`, or `landing` for a plan carrying a `Repo` column (adr_0004 C-324), otherwise a federated plan never folds. Not in `hex-execute` (it never reaches `done` and folds pre-review), not a fifth skill (install surface, optional by omission). | `hex-review/SKILL.md` (new phase), the three `hex-review/tier-*.md` files |
| **C-403** | **Delta grammar** — `ADDED`/`MODIFIED`/`REMOVED`, keyed by `C-###`/`S-###`, authored into the plan's `## Spec Deltas` section. **No `RENAMED` operation**: hex's IDs are stable join keys (`protocol.md:341-344`), so a title change is an ordinary `MODIFIED` body edit carrying an optional `Title: "<old>" → "<new>"` line. `MODIFIED` bodies are complete replacements. `REMOVED` carries a reason. `S-###` folds only into a destination already carrying `S-###`. | new `hex-core/references/archive.md` (sole definition site); pointer from `protocol.md` § Traceability IDs |
| **C-404** | **Destination resolution** — `hex.md › Pointers` spec/plan/ADR conventions entry, verified on consumption, re-detected and re-pointed on a miss (`audit.md:36-40` de-facto globbing included). Target file resolves in order: the plan's `Related Spec:` field, else the file carrying the touched IDs, else a plan-slug name match. **Multiple candidates → halt** (C-406); **zero candidates → graceful defer**, not halt — deltas stay in the plan, `State: done` stands, the block names the fix (the pure-`ADDED` new-component case). Resolution completes only once C-413's marker convention **and C-418's containment check** are confirmed. hex never ships or creates a destination, and never creates a destination *file*. | `archive.md`; `memory.md:35` gains the fold-back consumer; `plan.md` gains `Related Spec:` |
| **C-405** | **Stale-base guard, ID-loss only** — before applying any `MODIFIED`, compare live sub-IDs under that contract against those the incoming body restates; any live ID the body drops **halts the fold** with both sets printed. Ported from `specs-apply.ts:305-310`, which OpenSpec's own shipped merge skill omits. Scope is explicit: it detects ID-presence loss only. Prose loss under a retained ID is **C-416's** job, not `git diff`'s. | `archive.md` § Safety envelope |
| **C-406** | **Halt-and-escalate, zero fix passes** — triggers: conflict-matrix hit, dropped live ID, **ambiguous** target (two or more candidates), **destination not fold-compatible** (no recognized ID-marker convention, C-413), malformed entry (no ID, `REMOVED` with no reason, `MODIFIED` with no `Base:` line), dirty destination, self-check failure, **shrinking `MODIFIED` body** (C-416), **more than one target** (C-415), **containment failure** (C-418), **plan edited since the recorded fold** (C-417). Not a trigger: zero candidates and no documented spec home, which defer per C-404 rule 5 and C-407. Halt = write nothing, keep `State: done`, keep the deltas in the plan, print reason + fix, continue to Upkeep and handoff. Never re-opens the verdict, never repairs. Precedent and its deliberate tightening: `protocol.md:398-404` allows one fix pass on code hex owns; this phase allows none, because the target is human-owned. | `archive.md`; `protocol.md` § Convergence contract gains the pointer |
| **C-407** | **No-documented-spec-home case** — no destination is invented, no store is created, deltas are written into the plan with `Target: unresolved`, `State: done` is still set, the handoff prints the `/hex-init` fix with its proposal order (practiced location → `.agents/specs/` last resort, with consent), and `/hex-review <plan path>` re-folds once a home exists. **File materialization is `/hex-init`'s, never fold-back's**: recording an empty home also seeds `<home>/spec_<slug>.md` from the shipped template, copy-only-if-absent, with consent. `/hex-init` gains a conditional "spec home documented?" audit item. | `archive.md`; `hex-init/references/audit.md:28-40`; `hex-init/SKILL.md:53` |
| **C-408** | **Idempotence for an unchanged plan** — a re-run against the same delta is byte-identical: `ADDED` with identical body is a no-op and with a differing body is a conflict; `REMOVED` of an absent ID and `MODIFIED` matching the live body are no-ops. No date stamping and no plan rename, so OpenSpec's date-prefix guard (`archive.ts:38,:496`) has nothing to guard here. A re-run whose plan **changed** is not idempotence's case at all — it is C-417's, and it halts. | `archive.md` |
| **C-409** | **Revert is git, and only git** — hex-review never commits (`hex-review/SKILL.md:278-282`), hex never pushes (`protocol.md:408`), so every fold write is an unstaged working-tree change; `git diff` reviews it and `git checkout -- <file>` undoes it exactly, guaranteed exact by the clean-destination precondition. hex ships no unfold command. The handoff states the revert command literally. | `archive.md`; `hex-review/SKILL.md` handoff block |
| **C-410** | **Archive without moving** — the terminal review state (`State: done`, or `landing` for a plan carrying a `Repo` column — adr_0004 C-324) is the archive marker; the plan file is never moved or renamed; Upkeep clears the `hex.md › Memory` active-plan pointer (the first clear in the bundle) and records the plan and its fold target in the artifact index, at the same terminal-review-state condition C-402 uses. The satellite Federation locks (adr_0004 C-313) are separate and persist to `done`. | `hex-review/SKILL.md` Upkeep; `memory.md:68-74`, `protocol.md:520-532` |
| **C-411** | **Mandatory Fold-Back block** — the review report always carries it, including when the phase did not run (`not performed — <reason>`). It prints: target and how it resolved, the ID-marker convention and its source (C-413), the `live` and `incoming` ID census **as pasted command output** (C-414), per-ID disposition, **a per-touched-ID content excerpt — first line and the pasted non-blank line count of the live body (C-416) beside the incoming body's** so prose loss is visible without leaving the report, the **containment verdict with the resolved path and its `git ls-files` transcript** (C-418, printed on every run), destination cleanliness as pasted `git status --porcelain` output **at step 4 and again at step 6**, `targets: 1` with prepared-then-written, the fold receipt it appended (C-417), and the revert command. An unannounced fold is a spec violation, in the same shape as `adr_0003` C-207; so is a prose assertion standing where a command transcript belongs. | `hex-review/SKILL.md` § The review report (skeleton) |
| **C-412** | **Convergence composes as the mirror** — convergence (plan ← code) runs first and unconditionally; fold-back (spec ← plan) runs only on its `Converged` result. Both key on `C-###`/`S-###`; neither rewrites what the other wrote; a `Needs Work` verdict means fold-back never runs at all. | `protocol.md` § Convergence contract gains the composition sentence |
| **C-413** | **Destination ID-marker convention** — a destination is fold-compatible only when its contracts are introduced by ATX headings matching `^#{1,6}\s+(C\|S)-[0-9]+\b` (the shipped template's own shape, `spec.md:56`), body = heading to next heading of same or shallower depth. A project may record an alternative regex plus body rule in `hex.md › Preferences` (user-owned, `/hex-init`-written, **never edited by a run** — `DESIGN.md:109-112`), with the Pointers spec-home entry carrying only a pointer to it; that recorded value is the only accepted alternative. It lives in Preferences, not Pointers, because Pointers is a skill-managed location cache Upkeep rewrites freely (`DESIGN.md:72-79`) and an authoritative regex parked there would be silently clobbered. hex never infers a marker, never matches a bare ID in prose, and halts with `destination format not fold-compatible` rather than guessing at structure. The convention and its source are printed. | `archive.md`; `memory.md` Preferences gains the `Spec ID marker`, the Pointers spec-home entry a pointer to it (`:47-57`); `hex-init/references/audit.md` asks for it with the spec home |
| **C-414** | **Mechanical evidence is command output** — the census (step 1), destination cleanliness (step 4) and the ID half of the self-check (step 5) are discharged by literal `grep -nE '^#{1,6}[[:space:]]+(C\|S)-[0-9]+\b' <target>` and `git status --porcelain <target>` calls whose **raw output is pasted** into the Fold-Back block, never summarized. No parser, no runtime, no binary (`DESIGN.md:63-65` untouched) — git and grep are generic tools already assumed (`adr_0001` C-003). Semantic judgment stays with the model, backed by halt. | `archive.md` § Safety envelope; `hex-review/SKILL.md` report skeleton |
| **C-415** | **One destination per fold; multi-file is a non-goal** — a plan carries exactly one `## Spec Deltas` block naming exactly one `Target:`, and step 6 writes it in a **single whole-file write**. OpenSpec's prepare-all/write-all atomicity (`archive.ts:420-489`) is **not ported and not claimed**: without a runtime, "write-all" is N model-issued calls that can stop between files, which is a silent partial fold. Two targets → halt (C-406); delta entries whose IDs live outside the single target are reported `not folded — ID lives outside <target>` and stay in the plan. **Under a federated plan** (a `Repo` column, adr_0004) the fold is **lead-scoped**: resolution, containment and the census run in the lead against the lead's `hex.md` (adr_0004 C-318), the one `Target:` is a lead file, and every delta from a WP with `Repo` ≠ `.` is deferred `not folded — delivered in <repo>; fold by hand into that repo's spec` and left in the plan. | `archive.md` § Safety envelope; `plan.md` § Spec Deltas |
| **C-416** | **No-shrink guard** — for every `MODIFIED`, the non-blank line count of the incoming body must be **≥** that of the live body span (C-413). Any reduction, by one line, **halts**. Both counts are pasted command output (C-414), never estimates, and the trigger is arithmetic, not "significant change". A deliberate narrowing is expressed as `REMOVED` with its reason or folded by hand. This closes the deletion class C-405 cannot see; same-size meaning drift remains the ceiling. | `archive.md` § Safety envelope; `hex-review/SKILL.md` report skeleton |
| **C-417** | **Fold receipt; a re-run is a retry, never a revision** — a successful write appends `Folded: <date> → <target>` plus, per touched ID, the sub-ID set and non-blank line count **as written** to the plan's `## Spec Deltas` block (append-only). A later run compares live-vs-receipt and incoming-vs-receipt: both match → no-op; destination moved on → re-derive against the current body; **incoming changed → halt** (`plan delta changed since the recorded fold`). The base identity is readable by a human rather than hashed, because hex has no hasher and an uncomputable fingerprint is the Phase 0 OpenSpec never shipped. | `archive.md`; `plan.md` § Spec Deltas |
| **C-418** | **Containment — the resolved target never leaves the spec home** — the target must normalize to a repository-relative path **inside** the verified spec home, carry no `..`, not be absolute, be an existing regular file (not a symlink, not a directory), and be git-tracked (`git ls-files --error-unmatch <target>`, pasted). Checked at resolution **and re-checked as the first action of step 6**, beside the cleanliness re-check. Failure is a **hard refusal**, never a warning: a model-written `Related Spec:` is otherwise sufficient to redirect the entire write into an arbitrary project file with every other guard passing against the wrong file. The verdict prints on every run. Under a federated plan the check and its `git ls-files` run in the lead repo (C-415). | `archive.md` § Destination resolution; `hex-review/SKILL.md` report skeleton |
| **C-419** | **`hex-execute` authors the deltas, at merge time, per work package** — normative, not deferred to implementation: the fold's only input must describe delivered truth, and only execution knows what was delivered. A plan-time delta is an intention the Living design record (`hex-execute/SKILL.md:259-262`) already exists to correct. **Producer obligation:** every `MODIFIED` entry carries a `Base:` line enumerating the live sub-IDs and non-blank line count it was authored against, so C-405 and C-416 have a well-formed base; a `MODIFIED` without it is malformed → halt. Two WPs touching one ID produce two entries, caught by C-406's duplicate-within-section rule. Under a federated plan a lead-folding `MODIFIED` reads its `Base:` from the lead repo's destination, not the satellite worktree (C-415). | `hex-execute/SKILL.md` (new merge-time step); `archive.md` § Delta grammar |

**UX scenarios.**

| ID | Scenario |
|---|---|
| **S-401** | Happy path. `plan_export.md` approves and converges; `hex.md › Pointers` names `docs/specs/`; the plan carries `ADDED C-004`, `MODIFIED C-002`, `REMOVED C-003`. The census prints live `{C-001, C-002, C-003}` and incoming `{C-002, C-003, C-004}`; `spec_export.md` is clean; the rebuilt body is prepared, self-checked, written with `C-001` and `C-002` in place and `C-004` appended; the Fold-Back block prints the disposition and `git checkout -- docs/specs/spec_export.md` as the undo. |
| **S-402** | This repo. `CLAUDE.md` names plans, ADRs and research and **no spec home**; de-facto discovery finds none. Nothing is written outside the plan; the deltas land in `plan_*.md § Spec Deltas` with `Target: unresolved`; `State: done` is set; the handoff prints the `/hex-init` fix. `.agents/specs/` is **not** created. |
| **S-403** | Stale base. `MODIFIED C-002` restates two sub-requirements; the live `C-002` carries three. The fold **halts**, prints the dropped ID, writes nothing, keeps `State: done`, and names the fix ("refresh the delta against the current spec, then re-run `/hex-review <plan path>`"). The exact case that silently corrupted an OpenSpec user's spec. |
| **S-404** | Re-run. `/hex-review <plan path>` is invoked again after a successful fold. Every entry resolves to a no-op; the destination is byte-identical; the Fold-Back block prints `no change — already folded`. |
| **S-405** | Dirty destination. The user has uncommitted edits in `docs/specs/spec_export.md`. The fold **halts** before step 5, because `git checkout --` would later destroy those edits; the handoff says commit or stash, then re-run. |
| **S-406** | Ambiguity. Two files under `docs/specs/` carry `C-002`. The target does not resolve; the fold **halts** and prints both candidates rather than picking one. |
| **S-407** | Not converged. The convergence check appends two gap WP rows and the verdict caps at Needs Work (`protocol.md:506-507`). Fold-back **does not run**; the block prints `not performed — verdict Needs Work`; `State` stays `executing` with `Next: /hex-execute <plan path>`. |
| **S-408** | Scenario IDs with no home. The plan delivered `S-004`; the destination spec has no scenario section. `C-###` deltas fold normally; `S-004` is reported `not folded — destination carries no scenario section` and stays in the plan. No section is invented. |
| **S-409** | Title change. `C-002`'s title changes and its body gains a paragraph. One `MODIFIED` entry with a `Title:` line — no `RENAMED`, no `FROM:`/`TO:` pair, no unpaired-drop failure mode. The ID never moves. |
| **S-410** | Legacy plan. A plan that reached `done` before this ADR shipped is re-reviewed. It carries no `## Spec Deltas` block, so the phase prints `not performed — plan carries no deltas` and writes nothing. No retro-fold, no migration. |
| **S-411** | Recovery, consistent with S-402. S-402 found **no** practiced location, so `/hex-init` has none to propose: it falls to the shipped last resort, proposes `.agents/specs/` **with consent**, records the home in Pointers (the default ID-marker convention is built-in, so nothing is written to Preferences), and — the home being empty — seeds `.agents/specs/spec_export.md` from `hex-init/assets/templates/spec.md`, copy-only-if-absent. Only now does a destination file exist. `/hex-review <plan path>` re-runs; the recorded deltas fold into the seeded file; C-408 makes a third invocation a no-op. Had discovery instead **found** a practiced `docs/specs/`, S-402 would not have applied at all and the ordinary S-401 path would have run. |
| **S-412** | Non-fold-compatible destination. `hex.md › Pointers` names `docs/specs/`, but the shop is the RST/Sphinx one `DESIGN.md:46` anticipates: `docs/specs/export.rst`, contracts under `C-004`-prefixed RST section titles, no markdown headings. `grep` matches nothing; no ID-marker regex is recorded. The fold **halts** with `not folded — destination format not fold-compatible (docs/specs/export.rst)`, writes nothing, keeps `State: done`, and names both fixes: record an ID-marker regex in `hex.md › Preferences`, or fold by hand. No structure is guessed and no markdown is written into an RST tree. |
| **S-413** | Pure `ADDED`, new component. `plan_billing.md` delivers only `ADDED C-007`, `C-008` — no existing ID to anchor on, no `Related Spec:` field filled, and no `spec_billing.md` in `docs/specs/`. Rule 3.2 yields zero candidates by construction and rule 3.3's slug match finds nothing. The phase **defers rather than halts**: `not folded — no destination file for a new component`, deltas stay in the plan, `State: done` is written, and the block names the two fixes (set `Related Spec:`, or create `docs/specs/spec_billing.md`). The next `/hex-review` folds once the file exists. |
| **S-414** | Recorded marker override. A project writes contracts as `## Contract C-004: Export` — bold-free, colon-separated, two-hash. The default regex requires the ID immediately after the hashes, so `Contract` preceding it means the default matches nothing. Rather than relaxing the default — which would start matching IDs in prose — the project records `Spec ID marker: ^#{1,6}\s+Contract\s+(C\|S)-[0-9]+\b` in `hex.md › Preferences` (user-owned), with a pointer to it in the Pointers spec-home entry. The census `grep` uses the recorded regex, prints its transcript, and the fold proceeds normally. The Fold-Back block prints `ID marker: recorded (hex.md › Preferences)`. |
| **S-415** | Prose loss under a retained ID. `MODIFIED C-002` restates all three live sub-IDs — so C-405 passes — but its body is 4 non-blank lines where the live body is 14, having dropped the back-pressure paragraph attached to `C-002.2`. C-416 fires on the arithmetic: the fold **halts**, writes nothing, keeps `State: done`, prints both pasted counts and the three fixes (restate the full body, express the deletion as `REMOVED` with a reason, or edit the spec by hand). The class OpenSpec shipped a corruption in is refused, not reported. |
| **S-416** | Escaped target. `plan_export.md` § Overview carries `**Related Spec:** ../../src/config.ts` — a malformed field, or an invented one. Rule 3.1 would select it; C-418's containment check refuses it before any census runs. The fold **halts** with the resolved path and the spec home printed side by side, writes nothing, and names the fix. Nothing outside `docs/specs/` is ever opened for writing. |
| **S-417** | Two targets. A plan's contracts belong to `spec_export.md` and `spec_billing.md`, so execution emitted two `## Spec Deltas` blocks. The fold **halts** before step 5 with `not folded — this plan targets 2 spec files; one destination per fold`, and names the remedy (split the plan, or fold the second by hand). No file is written, so there is no half-folded pair — the failure C-415 exists to make impossible. |
| **S-418** | Edited plan re-run. `plan_export.md` folded successfully yesterday; today `MODIFIED C-002`'s body has been rewritten from 17 lines to 11 while keeping all three sub-IDs, and `/hex-review` is invoked again. The live destination still matches the receipt, the incoming body does not: C-417 classifies this as a revision, not a retry, and **halts** with the receipt's counts beside the incoming ones. The fix line states that the spec is now the base and a fresh delta must be authored against it. Without the receipt this run would have silently overwritten a reviewed spec with an unreviewed body. |

## Non-Functional Requirements

| Axis | Impact |
|---|---|
| **Data integrity** | **The axis this ADR exists for, and the one it cannot fully secure.** Eleven halt conditions, a pre-write census, prepare-before-write, a clean-destination precondition re-checked at the write, and a containment boundary on the destination put every known corruption path behind a stated rule. Five of those — census, cleanliness, containment, the ID half of the self-check, and the live/incoming line counts — are discharged by pasted `git`/`grep`/`awk` output rather than by assertion (C-414, C-416, C-418), which makes their evidence re-runnable in one line instead of merely readable. The two failures that actually corrupted an OpenSpec user's spec are both refused rather than reported: a dropped ID (C-405) and a gutted body under a retained ID (C-416). Multi-file partial folds are removed by construction rather than guarded (C-415), and a replayed edited plan is halted rather than replayed (C-417). The rest are rules a model applies, not code that runs, so the residual is real and now narrow: a pass that skips the *semantic* guard may still skip its printed line, and no count-based rule sees a same-size meaning inversion (C-411's per-ID excerpt is the in-report defence against that). The backstop is structural rather than procedural: the phase **never commits**, so every write is a working-tree diff a human sees before it can enter history, and the destination was verified clean so the undo is exact. That is a weaker guarantee than a validator and a stronger one than OpenSpec's shipped `openspec-sync-specs`, which has neither the guard nor the never-commit property. A project treating its specs as a compliance artifact should not rely on this phase. |
| **Cost (tokens)** | Small and conditional. The phase reads one destination file and writes one Fold-Back block; it does not run at all unless a plan converged and approved. `archive.md` is a **conditional-load** reference — read only when a plan carries a `## Spec Deltas` block — matching the carve-out `adr_0003` C-203 gave `config.md`. |
| **Operability** | Mixed, honestly. Gains: `done` stops being a dead end, the active-plan pointer finally clears (C-410), and a stale spec becomes visible instead of assumed. Costs: one new phase, one new reference file, one new plan section, one new plan Overview field, and eleven halt conditions a reader must hold — all of it landing in `hex-review`, the bundle's hottest path (see the scoring note on blast radius). The Fold-Back block is the mechanical check; two of its lines are command transcripts a reader can re-run, the rest is self-reported and catches "the phase said nothing" better than "the phase said something plausible and wrong". |
| **Security** | Indirectly affected. The phase writes to project-owned files outside `.agents/`, which is a new blast radius for `hex-review`. Bounded by: exactly one resolved target per run (C-415), a **containment check that refuses any path outside the documented spec home, re-verified immediately before the write** (C-418), an existing git-tracked file only (no file creation, no directory creation), a destination whose structure was enumerable before the write (C-413), no commit, no push (`protocol.md:408`), and a halt on any ambiguity. It cannot write to code, CI configuration, or dependency manifests: a resolved path that names one fails containment and halts. |
| **Portability** | Not degraded. Markdown rules, git commands every harness already runs, no new binary and no harness capability assumed (`adr_0001` C-003). |
| **Scalability / Availability** | Not affected. No runtime, no service, one file per run. |

## Constitution deviations

`hex/DESIGN.md` is the constitution. Two of its resolved positions and
one shipped-template rule are amended; each needs a new dated round
appended to `DESIGN.md` in the same change.

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **`hex-review/SKILL.md:3,:278-282`** — "never edits the code or diff under review, and never commits — its only writes are the plan's Status block and an append-only convergence check". The Fold-Back phase writes a file that is neither the plan nor the diff. | Only `hex-review` reaches `done` (`:230-233`) and only it knows the plan converged. A fold-back is by definition the write that happens when delivered work has been judged correct, and exactly one skill holds that judgment. Note the precedent: `DESIGN.md:299-304` already re-scoped this contract once, from "read-only" to "never edits code or the diff", for exactly the same reason ("the plan is the durable state — a chat-only gap report evaporates"). Here the durable state is the spec. | Option C (a `/hex-archive` skill) preserves the contract literally and was scored 35 points behind: it buys textual purity with a fifth install surface and makes the lifecycle's most important step optional by omission. Option B (fold in `hex-execute`) preserves it too, and folds unreviewed work into truth. The narrow amendment names the new write and its four preconditions; **the never-commits half is not amended and is load-bearing** — it is what makes every fold reviewable and revertible (C-409). |
| **`hex-init/assets/templates/spec.md:8`** — "A human-authored pre-plan artifact - no hex orchestrator produces one." An orchestrator now amends one. | Without a write path there is no fold-back; the gap the decision exists to close stays open. | Keeping specs strictly human-authored is Option E, the null option — it closes the pointer gap and nothing else. The amendment is deliberately narrow: hex **amends** a spec, never **produces** one. It creates no spec file, creates no spec directory, invents no section (C-403 rule 5), and does nothing at all when the project documents no spec home (C-407). The template line changes to "human-authored; amended by hex-review's fold-back phase, never created by it." |
| **`DESIGN.md:32-39,:145-156`** — project knowledge lives in project context, and "Destination is the user's choice" — established with `/hex-init` as the only writer, always with consent. Fold-back writes into project context from an orchestrator, post-gate, with no consent point of its own. | The single-gate rule (`protocol.md:45-49`) forbids a mid-run question, and the fold happens after every gate has passed. Adding a consent prompt *inside the run* would violate a live constitutional rule to satisfy an implicit one. | **The Handoff contract's post-completion carve-out was evaluated and is the closest thing to a sanctioned consent point** (`protocol.md` § Handoff contract: "After emitting it, the orchestrator MAY ask **one** optional proceed question … the single-gate rule governs *pre-work* approval and is not violated by a post-completion offer"). A propose-then-ask shape — print the full rebuilt body in the Fold-Back block, emit the handoff, ask the one permitted question, write only on yes — needs **no** constitutional amendment for the question itself. It is rejected on two grounds, both mechanical rather than aesthetic. First, position: the carve-out fires *after* the handoff block, which by C-402 is after Upkeep, which by C-410 has already cleared the active-plan pointer and written the artifact index — so a "no" leaves the run's own bookkeeping describing a fold that did not happen, and a "yes" performs a write after the run's required final message, which the same section forbids ("never a question in place of the block" presumes the block is final). Second, and decisive: it buys nothing the design does not already have. The user is being asked to approve a diff that is printed either way (C-411), against a file that is left uncommitted either way (C-409), where the real approval gesture is `git add`. A yes/no on a printed diff the human has not yet read is consent theater — it converts a reviewable working-tree change into a reflexive keystroke, and a reflexive yes is weaker protection than an unstaged diff the human must actively stage. Note also that this carve-out is *optional* ("MAY"), so it is not a consent mechanism the constitution offers; it is permission to ask, which does not by itself constitute permission granted. A pre-gate "may I fold?" question at the meta-plan gate was also considered: it asks about a write whose content does not exist yet (the deltas are produced by execution, three phases later), so the user would be consenting to an unknown diff — worse than the alternative. Instead consent moves to **where the destination is chosen**: `/hex-init` records the spec home with consent (C-407), and recording it *is* the standing permission. The fold then stays inside the recorded location, announces every write (C-411), and leaves it uncommitted (C-409) so the human's approval is exercised at `git add` — the same place their approval of every other hex change is exercised. |

**Considered and *not* deviated:** the two-layer knowledge model
(`DESIGN.md:32-39`) is upheld, not breached, by the destination
decision — hex writes *into* the project's layer-1 home and ships no
layer-2 spec store (Option D rejected). The single meta-plan gate
(`protocol.md:45-49`) is preserved: the phase asks nothing, ever, and
halts instead. Traceability IDs (`protocol.md:336-356`) are unchanged
and are strengthened as the fold's join key. `hex never pushes`
(`protocol.md:408`) is untouched. The Convergence contract's
append-only discipline (`protocol.md:498-503`) is mirrored, not
modified.

## Migration / rollout plan

*This section fills the ADR template's `## Implementation Plan` slot
(`hex-init/assets/templates/adr.md`); it keeps the "Migration / rollout"
title its structural siblings `adr_0002`/`adr_0003` use, since the work
is a staged, backward-compatible rollout rather than a greenfield build.*

**Nothing breaks.** The phase triggers on the *transition* to `done`
inside a `hex-review` run and on the presence of a `## Spec Deltas`
block — never on the `done` value itself. A plan already at `done` is
never retro-folded (S-410); a plan with no deltas prints one line and
writes nothing; a project with no spec home writes nothing outside the
plan. There is no version marker and no detection step, the same
discipline as `adr_0002` C-105.

**Wave 1 — contracts (independently shippable, no behaviour change).**

| File | Change |
|---|---|
| `hex-core/references/archive.md` | **New.** Sole definition site for C-403–C-409 plus C-413–C-419: delta grammar, the destination ID-marker convention and its default regex, destination resolution (including the zero-candidate defer and the containment check), the safety envelope with its four required command invocations (`grep` census, `git status --porcelain`, `awk`+`grep -c` body counts, `git ls-files --error-unmatch`), the single-destination rule and its single whole-file write, halt semantics, idempotence, the fold receipt, revert. Every other file points at it. |
| `hex-core/SKILL.md` | Add the `archive.md` row to the references table, **marked conditional-load**: read only when a plan carries a `## Spec Deltas` block. |
| `hex-core/references/protocol.md` | § Convergence contract gains the C-412 composition sentence (convergence first, fold-back on `Converged` only, mirror directions, shared join key); § Traceability IDs gains the pointer to the delta grammar; § Upkeep step gains the active-plan-pointer clear (C-410). |

**Wave 2 — the phase.**

| File | Change |
|---|---|
| `hex-review/SKILL.md` | New Fold-Back phase between the convergence check (`:235-240`) and Upkeep (`:303-306`); description line and Constraints bullet re-scoped (C-401); report skeleton gains the mandatory Fold-Back block (C-411); handoff gains the revert line and the not-performed reasons. |
| `hex-review/tier-low.md`, `tier-medium.md`, `tier-high.md` | The phase is tier-invariant — it runs identically at every tier or not at all. State that once per file rather than duplicating the rules. |
| `hex-execute/SKILL.md` | **New merge-time step (C-419):** on merging a work package, append its delta entries to the plan's `## Spec Deltas` block — one block, one `Target:` (C-415) — each `MODIFIED` carrying its `Base:` enumeration read from the live destination. Same append-only discipline as the Living design record it sits beside (`:259-262`). |
| `hex-init/assets/templates/plan.md` | Optional `## Spec Deltas` section with its one-line comment — **exactly one block, one `Target:`** (C-415), `MODIFIED` entries carrying `Base:` (C-419), and the appended `Folded:` receipt (C-417); absence is normal. **Overview block gains `**Related Spec:** [Link to spec or N/A]`** beside the existing `Related PRD` / `Related ADR` fields (`:37-38`) — without it C-404 rule 3.1 has nothing to read and is unreachable. `hex-plan` fills it when planning from a spec (`/hex-plan <path-to-spec>` already knows the path); `N/A` otherwise. |
| `hex-init/assets/templates/spec.md:8` | "human-authored; amended by hex-review's fold-back phase, never created by it." |
| `hex-core/references/memory.md:35,:47-57,:68-74` | Pointers row names fold-back as a consumer of the spec/plan/ADR entry; the example Pointers entry (`:50-51`) gains a spec home with an optional `ID marker: see Preferences` pointer, and the example **Preferences** section gains the optional `Spec ID marker:` regex + body-extent line (C-413) — user-owned, `/hex-init`-written, never edited by a run; Memory row records the cleared active-plan pointer and the fold target in the artifact index. |
| `hex/DESIGN.md` | New dated round recording the three amendments. |

**Wave 3 — init support (not blocking).**

| File | Change |
|---|---|
| `hex-init/references/audit.md:28-40` | The conventions item gains an explicit spec-home sub-check and a copy-ready block; proposal order stated (practiced location → shipped default last, with consent). Two additions from this round: it also asks for the **ID-marker convention** when the practiced location's files do not match the default regex, recording it in `hex.md › Preferences` (user-owned) rather than Pointers (C-413), and, when the recorded home is empty, offers to **seed `<home>/spec_<slug>.md`** from `assets/templates/spec.md` copy-only-if-absent (C-407) — the only place in the bundle that creates a spec file. |
| `hex-init/SKILL.md:53,:104-108` | The conditional "spec home documented?" question, asked only on the C-407 triggers. |
| `.agents/memory/hex.md`, `CLAUDE.md` | Dogfood: this repo documents its own spec home, which today it does not. |

**Rollback.** Wave 3 rolls back by deleting the audit item. Wave 2 rolls
back by deleting the phase — plans keep their `## Spec Deltas` blocks
as inert documentation, and every already-folded spec is already in the
project's git history. Wave 1 rolls back by deleting `archive.md`.
Nothing in any wave is load-bearing for an existing run.

## Validation

How a fold is verified — the design's own check surface, not a separate
test harness, because the Fold-Back block **is** the audit trail:

- [ ] **The printed Fold-Back block (C-411) is the primary evidence.**
      Every run emits it, including when the phase did not run
      (`not performed — <reason>`); an absent block is itself the alarm.
      It carries the pasted `git`/`grep`/`awk` transcripts (C-414,
      C-416) so the census, cleanliness, containment and line counts are
      re-runnable in one line rather than merely asserted.
- [ ] **Containment holds on every run (C-418).** The block prints the
      resolved target, its `git ls-files` transcript and a
      `contained: <home>/<file> ✓` verdict; a resolved path outside the
      documented spec home halts before any census, and its absence from
      the block is visible.
- [ ] **Exactly one target is written (C-415).** The block prints
      `targets: 1` with prepared-then-written; more than one
      `## Spec Deltas` block or `Target:` halts before step 5, so no
      partial multi-file fold can exist.
- [ ] **The two corruption classes are refused, not reported.** A
      dropped live sub-ID halts (C-405, S-403) and a shrinking
      `MODIFIED` body halts (C-416, S-415) — both with their counts
      printed.
- [ ] **The write is reviewable and revertible.** It lands unstaged;
      `git diff` reviews it and `git checkout -- <file>` undoes it
      exactly (C-409), guaranteed exact by the clean-destination
      precondition (step 4).
- [ ] **The S-4xx scenarios are the acceptance cases.** S-401 (happy
      path), S-402 (no spec home), S-403/S-415 (the two corruption
      halts), S-404/S-418 (re-run and edited-plan classification),
      S-412/S-414 (marker convention), S-416 (escaped target),
      S-417 (two targets) each name an expected printed outcome that a
      reviewer or an implementing plan can assert against.

## Open Questions

1. *Resolved this round — the delta producer is normative:* see **C-419**
   (`hex-execute`, at merge time, per work package, with the `Base:`
   enumeration obligation). It is no longer an open question and no
   longer defers to the implementing plan.

2. *Resolved for the same tree; residual is cross-branch only.* A re-run
   against an **edited** plan is decided by **C-417**'s receipt
   comparison and halts. What remains open is two plans folding into the
   same spec from **different branches**: each fold is individually valid
   against its own base, and the collision surfaces at integration.
   *Recommended:* rely on C-405, C-416 and C-417 within a tree, and let
   git's own merge handle the branch case — the fold writes ordinary
   uncommitted markdown, so a divergent fold is an ordinary merge
   conflict on a spec file, not a hidden overwrite. A serialized fold
   gate is recorded as D-13 rather than specified here.

3. **[NEEDS CLARIFICATION: does fold-back extend to ADRs and other
   durable artifacts, or specs only?]** *Recommended:* **specs only, in
   v1.** ADRs are decision records with their own status lifecycle and
   are append-superseded rather than amended; folding a delta into one
   would mean rewriting history rather than updating truth. Revisit if
   a project asks, and only with a separate grammar.

## Deferred review findings

Raised in adversarial review, judged non-blocking for this ADR, recorded
here so they are actionable later rather than re-discovered. None changes
the decision; several belong to the implementing plan.

| # | Source perspective | Finding | Action when picked up |
|---|---|---|---|
| **D-1** | Consistency | *Resolved this round: C-401's Home column now marks `:225-233` "unchanged — the phase is inserted around it".* Original: C-401's Home column cited `hex-review/SKILL.md:225-233` (the "on verdict, set `State` to `done`" prose) as a changed location, but the Wave 2 migration row for that file never enumerates an edit there — only the description line, Constraints bullet, new phase, report skeleton and handoff. Plausibly the span is unchanged and cited only for context (the phase is inserted *around* it), but an implementer is left guessing. | Either drop `:225-233` from C-401's citation, or add one clause to the Wave 2 row stating what changes there — including "unchanged, cited for context only". |
| **D-2** | Spec completeness | *Resolved this round by C-415: one block, one target, multi-file is an explicit non-goal, extra targets halt. The plural "every target" language in the envelope is gone.* Original: Multi-target folds are underdetermined. The grammar's worked example shows one `Target:` per block ("one target per block") while the envelope speaks of preparing and writing "every target" (plural, inherited from OpenSpec's genuinely multi-file archive). Nothing states whether one plan may carry several `## Spec Deltas` blocks when its contracts belong to more than one pre-existing spec file, and no scenario (S-401…S-415) exercises the multi-target path. | State explicitly whether a plan may emit more than one `## Spec Deltas` block, and if so that C-404's resolution procedure runs once per block independently, with prepare-all spanning all of them. |
| **D-3** | Migration / rollback | The Wave 2 rollback story ("plans keep their `## Spec Deltas` blocks as inert documentation") is accurate for already-folded specs, which are in git history, but not for **pending** deltas: a plan holding `Target: unresolved` was promised a fold "on the next `/hex-review` once a home is documented", and deleting the phase silently makes that promise unfulfillable. | Add one line to Rollback: a rollback after Wave 2 orphans any pending unresolved deltas, accepted as a residual. |
| **D-4** | Concurrency | No atomicity between the destination-cleanliness check (step 4) and the write (step 6) — a TOCTOU window, since both are prose-executed steps in one pass rather than code. Low likelihood inside a single review invocation, but hex's own worktree/multi-agent model makes concurrent tree mutation real in general. | Either re-run `git status --porcelain <target>` immediately before the write and abort on non-empty output (cheap, one extra call, now that C-414 makes it a command anyway), or record it alongside the honest residual. |
| **D-5** | Argument quality | Constitution-deviation row 2's "Why needed" cell is circular — "without a write path there is no fold-back; the gap the decision exists to close stays open" restates the ADR's premise rather than justifying this specific template amendment. The row's "Simpler alternative rejected because" cell is sound on its own. | Re-tie the justification to the narrowness of the amendment itself (amend-not-produce is the minimum change that admits a write path) rather than to the ADR's existence. |
| **D-6** | Spec completeness | *Resolved this round by C-419 (`hex-execute`, merge time, per WP) and its `Base:` enumeration obligation — which is exactly the "enumerate the live sub-IDs before restating them" this row asked for. Kept for the record; nothing to pick up.* Original: Open Question 1 (who authors the `## Spec Deltas` block — `hex-plan` at plan time or `hex-execute` at merge) leaves the safety envelope's **sole input** unspecified. The consumption-side guards are producer-agnostic, so this does not block the mechanics decided here, but it must not reach implementation unresolved. | Must-resolve item for the implementing plan, not for this ADR's acceptance. Whichever producer is chosen should be required to enumerate the live sub-IDs of a contract before restating them, so C-405 has a well-formed base to compare against. |
| **D-7** | Consistency | Halt-vs-defer symmetry was inconsistent between an unfoldable `S-###` (graceful per-ID defer) and an unresolvable `C-###` target (blanket halt). **Partially addressed this round**: C-404 rule 5 now defers on zero candidates. What remains is the per-*entry* case — a delta set where some entries resolve and one does not — which still halts the whole set. | Decide whether a mixed delta set should fold the resolvable entries and defer the rest, or continue to halt wholesale. Halting wholesale is the safer default and may simply be affirmed. |
| **D-8** | Security / operability | C-409's revert story is exact only until the user's *next* touch to the same spec file. Step 4 protects the fold's entry; nothing protects its exit — if the file is dirtied again before the user runs `git diff`, `git checkout --` now also discards that later work. Inherent to the never-commits invariant this ADR correctly does not re-litigate, but the two mainstream 2025–2026 answers to keeping AI writes revertible both go further than "leave it unstaged and trust the user notices": frequent checkpoint commits (["Git Is Undo for AI", jpaul.me, 2026-07](https://www.jpaul.me/2026/07/version-control-safety-net/), on the growing blast radius of uncommitted work) and explicit per-task isolation (["Agent-safe Git with GitButler"](https://blog.gitbutler.com/agentic-safety), which names "bleed-through" — unrelated work tangled via a dirty tree — as a top agent-era git risk). | No mechanism change needed. Consider one line in the printed Fold-Back block nudging the user to commit or stash the touched spec file before their next edit to it. |
| **D-9** | Research / authoring quality | The delta grammar governs section structure and ID keys but imposes no **requirement-syntax discipline** on the free-text bodies it writes — nothing checks that a folded body is phrased unambiguously, only that it is structurally well-formed, so prose quality can drift across many individually-valid folds. 2026 SDD coverage repeatedly names EARS (Easy Approach to Requirements Syntax) as load-bearing for keeping LLM-authored requirements actionable ([SDD: The Definitive 2026 Guide, thebcms.com](https://thebcms.com/blog/spec-driven-development), "the secret weapon of SDD"). | Out of scope here — this ADR specifies the write pipeline, not authoring style. Forward pointer for whatever governs spec authoring quality generally. |
| **D-10** | Cross-model review (codex) — concurrency | TOCTOU between cleanliness verification and writing. **Narrowed this round**, not closed: step 6 now re-runs `git status --porcelain <target>` and the C-418 containment check immediately before the single write, so the window is one call wide rather than four steps wide. A window still exists, and hex's worktree/multi-agent model makes concurrent tree mutation real. Extends D-4. | If it ever bites: an explicit fold lock (a marker file, or serializing folds behind the merge queue `hex-execute` already owns). Not worth a mechanism today — the residual window is smaller than the human's own read-then-`git add` gap. |
| **D-11** | Cross-model review (codex) — spec completeness | Multi-target folds are now a stated non-goal (C-415), which resolves D-2 by removal rather than by specification. A project whose contracts genuinely span several spec files gets per-entry `not folded — ID lives outside <target>` defers and must split the plan. | Revisit only on evidence that split-plan-per-spec-file is a real burden. The recoverable protocol (target manifest + pre-fold state recorded in the plan) is the designed upgrade path if multi-file folds are ever wanted back. |
| **D-12** | Cross-model review (codex) — migration / rollback | Rollback after Wave 2 orphans **pending** deltas: a plan holding `Target: unresolved` was promised a fold on the next `/hex-review`, and deleting the phase makes that promise unfulfillable. Same shape as D-3. | **Accepted residual, stated here rather than mechanized**: after a Wave 2 rollback, unresolved `## Spec Deltas` blocks remain in their plans as inert, human-readable records of what was never folded. No migration, no cleanup, no retro-fold — consistent with S-410's treatment of legacy plans. |
| **D-13** | Cross-model review (codex) — concurrency | Concurrent plans on **separate branches** can each produce a valid fold that collides only at integration. C-417's receipt is per-tree, so it does not see the other branch. See Open Question 2. | A base fingerprint or a serialized fold gate would be stronger. Current position: a fold is uncommitted markdown, so a divergent fold surfaces as an ordinary git merge conflict on a spec file — visible, not silent. Revisit if fold-time collisions are observed in practice. |

## Links

- [`openspec-framework-analysis.md`](../research/openspec-framework-analysis.md)
  — items 1–6, 12, 20–22; the OpenSpec source verification and the
  `openspec-parallel-merge-plan.md` regression.
- [`adr_0003_configuration_customization_surface.md`](adr_0003_configuration_customization_surface.md)
  — the conditional-load reference carve-out and C-207's mandatory
  disclosure pattern, both reused here.
- [`adr_0002_execution_scheduling_recursion.md`](adr_0002_execution_scheduling_recursion.md)
  — C-105's extend-by-convention discipline (no version marker).
- [`hex/DESIGN.md`](../../../hex/DESIGN.md) — the constitution amended
  by this decision.

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-07-20 | hex-architect (architect worker) | Initial draft — Proposed |
| 2026-07-20 | hex-architect (review-fix worker) | Adversarial-review fixes, still Proposed. New: C-413 (destination ID-marker convention, default regex, recorded override, not-fold-compatible halt) and C-414 (census / cleanliness / self-check discharged by pasted `git`+`grep` output). C-404 gains an ordered resolution with a `Related Spec:` first path, a plan-slug fallback, and a zero-candidate **defer** replacing the blanket halt (pure-`ADDED` new-component case). C-407 states that `/hex-init`, never fold-back, materializes a first spec file. C-405 rescoped to ID-loss only; C-411 gains per-ID content excerpts. Option F (propose-only) added and scored. S-411 corrected to be consistent with S-402; S-412–S-415 added. Constitution row 3 now engages the Handoff contract's post-completion carve-out. Blast-radius caveat added to the scoring prose. Deferred review findings D-1…D-9 recorded. |
| 2026-07-20 | hex-architect (review-fix worker) | Cross-model adversarial pass (codex), triage 5 actionable / 4 deferred / 6 stated-convention / 2 trivia. Still Proposed. **Five new contracts, all substantive:** C-415 (one destination per fold, single whole-file write; OpenSpec's prepare-all/write-all atomicity is **not portable and no longer claimed**, multi-file is an explicit non-goal), C-416 (no-shrink guard — any reduction in a `MODIFIED` body's non-blank line count halts, closing the prose-loss class C-405 cannot see), C-417 (fold receipt in the plan; a re-run is a retry, never a revision — an edited plan halts), C-418 (containment — the resolved target must sit inside the verified spec home, git-tracked, re-verified immediately before the write; hard refusal), C-419 (`hex-execute` authors the deltas at merge time per WP, with a `Base:` enumeration obligation — Open Question 1 resolved and removed). Open Question 2 resolved for the same tree by C-417; its cross-branch residual moved to D-13. S-415 rewritten (now halts), S-416–S-418 added. Halt-condition count 7 → 11; mechanic/failure/visibility table, honest residual, Data-integrity and Security NFRs, and the Wave tables updated accordingly. D-1, D-2 and D-6 marked resolved; D-10…D-13 appended from this pass. |
| 2026-07-20 | hex-architect (upkeep) | **ID range renumbered `C-3xx`/`S-3xx` → `C-4xx`/`S-4xx`** (C-401–C-419, S-401–S-418). adr_0004 was drafted in the same session and independently claimed `C-301`–`C-324`; two Proposed ADRs sharing an ID space would make every downstream citation ambiguous, and `protocol.md` § Traceability IDs forbids renumbering once IDs are in use. Renumbered here while still Proposed, when it is free. No content change; the worked example's own `S-004` (a plan-scoped scenario ID, not one of this ADR's) is deliberately untouched. |
| 2026-07-20 | hex-execute (fix pass) | Cross-ADR review fixes, still Proposed. **B3 (block):** C-402 precondition 4 and C-410 now key the fold and its Upkeep on the plan's **terminal review state** — `done`, or `landing` for a federated plan (adr_0004 C-324) — so a federated plan folds instead of stranding at `landing`. **H3:** new C-415 clause 5 makes a federated fold **lead-scoped** (resolution, containment, census in the lead against the lead's `hex.md`, adr_0004 C-318); a delta from a WP with `Repo` ≠ `.` defers `not folded — delivered in <repo>`; C-418's `git ls-files` and C-419's `Base:` read qualified "in the lead repo". **H9:** the ID-marker convention (regex + body-extent rule) **moved from `hex.md › Pointers` to `hex.md › Preferences`** (user-owned, `/hex-init`-written, never edited by a run — `DESIGN.md:72-79`, `:109-112`), leaving only a pointer in the Pointers spec-home entry; C-413, S-412, S-414 and the memory.md/audit.md migration rows updated. **Structural:** added `### Consequences` (positive/negative/neutral) and `## Validation`; noted `## Migration / rollout plan` fills the template's `## Implementation Plan` slot. Two mechanical fixes already applied by upkeep: the `#…-c-410` anchor and the `C-4xx`/`S-4xx` contracts-section intro. |
