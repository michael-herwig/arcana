---
name: hex-discuss
description: Use when the user says "let's just discuss this, don't edit anything yet", wants to think a fuzzy problem out loud, or asks to talk something through before a plan or ADR starts. Pre-plan discussion mode — elaborates the ask one question at a time, researches disputed facts in the background while the conversation continues, pushes back with a structured grill, and captures what was settled in a discussion artifact.
license: Apache-2.0
metadata:
  keywords: discuss,discussion,clarify,elicit,interview,pre-plan,grill,research
  repository: https://github.com/michael-herwig/arcana
  summary: Pre-plan discussion mode — talk a problem through before deciding
user-invocable: true
---

# hex-discuss — Pre-Plan Discussion Mode

`hex-discuss` talks a problem through before anything is decided: it elaborates
the ask, argues with the answers, checks disputed facts in the background while
the conversation keeps going, and keeps what was settled in a discussion
artifact. It builds nothing and writes no plan, ADR, or spec — the run ends at
a **drain**, the explicit handoff that closes the discussion and names the
command to run next.

It is a hex skill, not a fifth orchestrator: no `classify.md`, no
`overlays.md`, no `tier-*.md`, and no tier vocabulary of its own. The
dispatcher/tier-file split is vacuous here, not deviated from — there are no
tier files to dispatch to.

Shared contracts:
[`protocol.md`](../hex-core/references/protocol.md) ·
[`workers.md`](../hex-core/references/workers.md) ·
[`models.md`](../hex-core/references/models.md) ·
[`memory.md`](../hex-core/references/memory.md).
If `hex-core` is not installed: `grim add ghcr.io/michael-herwig/arcana/hex-core:latest`.

## Argument syntax

`/hex-discuss <topic | path | slug>`. Free text becomes intake slot 1 and is
**never re-asked**; a path into the resolved discussions home, or the slug of
an existing artifact, resumes that artifact
([The discussion artifact](#the-discussion-artifact)).

## Entry and exit

Entered only by explicit user invocation or by this skill's own description
match on a user's discuss request — **never self-triggered from another hex
skill's flow** (the `hex-init` precedent). The frontmatter leaves
`claude.disable-model-invocation` unset: the description match is the entry
path. Entry then resolves the discussion's home and either opens the existing
artifact or writes the stub
([The discussion artifact](#the-discussion-artifact)). Exit is only an explicit
drain ([Handoff](#handoff)) or an explicit user abort. There is no third exit:
no turn budget, no idle timeout, no "this looks finished" self-exit. An abort
leaves `State: parked`, re-enterable later under the same slug.

## Conversation

### Intake

The opening turn asks once, as one composite ask with three slots: (1) the
problem in the user's own words, not a restatement or a guess; (2) a
source-material inventory — "dump anything": tickets, example apps, references,
code; (3) the outcome shape — plan, ADR, spec, or just clarity. Any subset is
answerable: the run proceeds with what it has and never re-asks a skipped slot.
Slot 3 pre-sets the drain target ([Handoff](#handoff)); slot 2 seeds the
artifact's `## Related` section and grounds every researcher prompt.

**A second composite intake ask is a contract violation.** A gap an unanswered
slot leaves resurfaces later as a single design question with an attached
recommendation under the cadence below — never as a re-ask of the form.

### Question cadence

Inventory questions — facts the user simply has, like which service or which
branch — batch into one composite ask. Design questions — anything whose answer
is a choice — are strictly one per turn, and every one carries an attached
recommendation. **Never a numbered list of design questions, and never two
design questions in one turn.** Never spend a question on what the artifact or
the repo already answers.

A design question ships as **chips** — selectable options plus a free-text
escape, rendered through the client's native structured-choice prompt where one
exists and a numbered list otherwise, a capability and never a named harness
tool. An open prose question is the exception and justifies itself — used only
where an option set would prejudge the answer.

```
Where should the session cache live?
  1. Redis — recommended: the ops runbook covers it, TTL eviction is free.
  2. A Postgres table — one less service to run, but you own the sweeper.
  3. Something else (say what).
— checked that: Redis TTL eviction is amortized O(1) [redis.io/docs/expire]
```

### Grill ruleset

Four rules, all four normative — not a menu.

- **(a) Rebuttal gate.** Categorize every pushback before answering it. *New
  evidence* — a benchmark, a constraint, a fact not previously on the table —
  updates the position, and the update states what changed. *Repeated
  opinion* — the same argument again — holds, and restates the evidence the
  position rests on. **Never concede on repetition alone**: only a later
  message adding something new moves the position.
- **(b) Anti-theater.** **Never manufacture an objection** to look rigorous.
  On agreement about a decision-relevant point, name the strongest remaining
  counter-argument once and move on — neither a second invented objection nor
  a later re-raise of the same one.
- **(c) Scoped elicitation.** Pick at most two fitting techniques per thread
  from premortem, inversion, first-principles, and force-rank, and apply them
  inline. **Never present the catalog.** A third technique on the same thread
  is a contract violation. Force-rank rather than a red-team/blue-team debate.
- **(d) Researcher blindness.** A research prompt states the question
  neutrally — the evidence for and against each option on the named axis — and
  **never reveals which side the user or this skill favors**, including when
  the user has already stated a preference.

### Research

Research runs in the background while the conversation continues; a
conversational turn never waits on a researcher. A result lands as a one-line
aside ([Announce form](#announce-form)); a researcher returning nothing useful
is folded in with no aside; a researcher failing to return at all is a
different event, surfaced once as a one-line transport note, because **a dead
worker is never normalized into "no result found."** A spawn is permitted
**only on a decision-relevant disputed fact** — never on an opinion, and never
on a question the repo answers, which is read instead.

Default gear: at most 3 concurrent `researcher` spawns, the role defined in
[`workers.md`](../hex-core/references/workers.md#role-index), at model class
`fast-balanced` — the researcher's cell at every tier in
[`models.md`](../hex-core/references/models.md#the-matrix), so this skill
**never escalates on its own judgment**. Three concurrent is a default gear,
not a ceiling: only the deep sweep runs wider, never wider than § Worker
coordination's cap. A `models.overrides` escalation is disclosed like any other
([`models.md`](../hex-core/references/models.md#rules) rule 1,
[Announce form](#announce-form)). Spawning is bound by
[`protocol.md` § Worker coordination](../hex-core/references/protocol.md#worker-coordination)
— concurrency cap, sequential batching, per-axis degraded lines, no exemption.

The deep sweep is offered as a chips moment — quick check (up to 3 researchers)
/ deep sweep (up to 12 background researchers) / skip — when a topic looks
sweep-worthy, and is **never entered silently**. The spend rides in the option
text: a bounded, user-initiated spend confirmation, **not an approval gate** —
nothing strands on a decline, no state advances on an accept. Second and later
offers carry the running total in the chip text ("deep sweep — 12 more; 24
spent this discussion"). Under `Degraded: inline workers` there is no
background wave to buy: the sweep re-caps to the quick check's 3, and the chip
text drops "background".

A sweep is `researcher` spawns and nothing else — **no `coordinator`, no nested
spawning, no new role, no new capability class** — in two waves: breadth
(discover), orchestrator-side dedup, then depth (analyze), the dedup being the
orchestrator's own synthesis duty. Hard total cap: 12 researchers per sweep —
`max-workers` caps concurrency, not the total — and a demand above 12 truncates
to 12, announced once. Each wave is also bounded by § Worker coordination's
effective concurrency cap and, exceeding it, batches under that same section —
never restated here — with the split announced once, naming the cap's source.

The waves are asynchronous: each deduped depth lane is dispatched the moment
its wave-1 result lands, **not at a barrier the conversation waits on**. Dedup
is therefore incremental rather than global — each arriving result is deduped
against the depth lanes already dispatched, first seen wins, the duplicate lane
at the margin bounded by the hard cap. Findings longer than a paragraph persist
per lane as research artifacts in the convention-resolved research home, each
written against the header contract in
[`hex-init/assets/templates/research.md`](../hex-init/assets/templates/research.md)
— its title line and its `## Metadata` block — which is what a later reader
attributes a citation by.

### Stop rule

The interview ends when the [restate](#the-restate-gate) can be filled without
a gap — **never at a question count, and never at a turn budget**. A question
answered in a few turns drains inline, deleting the entry stub, so the run nets
zero files. **An inline drain is still gated** — it passes the restate-gate
like every other drain.

## The discussion artifact

Home: the project's documented convention if it names one, else
`.agents/discussions/<slug>.md` — the resolution order every hex artifact class
uses ([`memory.md`](../hex-core/references/memory.md#location-and-resolution)).
Creating that row in `hex.md › Pointers` is post-gate
([Constraints](#constraints)); one file per discussion, its slug derived from
the topic and stable for the discussion's life. Every write this skill makes —
the artifact and each per-lane research artifact alike — holds to the path
conditions of
[`archive.md` § Containment](../hex-core/references/archive.md#containment-the-resolved-path-never-leaves-the-spec-home-c-418):
inside the resolved home, no `..` segment, never absolute. **No silent
clobber:** entry with a slug already present at `State: active` or
`State: parked` resumes that artifact and **never overwrites it**; a slug
colliding with a drained (`handed-off`) artifact takes a date suffix instead.

Lazy materialization has one declared exception: entry on a new slug writes a
header-only stub — `State: active` plus `Updated:`, nothing else — disclosed
once as `— discussion notes: <path>` ([Announce form](#announce-form)). Entry
that resumes an existing `active` or `parked` artifact opens it and **never
re-stubs**, but does refresh the header: a fresh `Updated:` always, plus
`State:` back to `active` when resuming from `parked`. That refresh is a header
update, not a re-stub, and it re-arms the `hex-state` rule's
no-code-or-config-edits stance for the resumed conversation; an abort later
returns the artifact to `parked`. Everything below the header stays lazy: a
section appears on its first content — a research result landing, a captured
requirement, or the user saying "capture" — so `## Research` appears when the
first result lands, and **an empty section is never scaffolded**. Section order
is fixed, presence is not, and a small discussion draining inline deletes its
own stub. The section menu is documented in exactly one place, the template
[`../hex-init/assets/templates/discussion.md`](../hex-init/assets/templates/discussion.md);
this file **never restates the menu**. Fallback where `/hex-init` never ran and
no template exists: the header contract alone — `State:` and `Updated:` on one
line, an optional participants line, nothing else required.

**No `C-`/`S-` IDs in a discussion artifact** — a hard prohibition, not a style
note. Requirements stay provisional prose:
[`protocol.md` § Traceability IDs](../hex-core/references/protocol.md#traceability-ids)
makes IDs originate in the spec, and a second origin would collide with the
fold-back join key
[`archive.md`](../hex-core/references/archive.md#delta-grammar) depends on. A
consuming orchestrator assigns IDs; it never inherits them.

Drain-readiness bar, checked at the [restate-gate](#the-restate-gate). The
artifact must be self-contained (a fresh session needs no access to the source
conversation), name the files and interfaces it touches, state what is out of
scope, carry unresolved points under `## Open questions`, and end with a
`## Verification` section naming how the eventual work is checked. Every path
it names is repo-root-relative (`.agents/adrs/…`, `hex/hex-core/…`). An
artifact failing the bar is **not drained with a warning**: the gate names the
gap and returns to the conversation until it is closed.

`## Open questions` are carried, not blocking: they become the receiving
orchestrator's docket, and one left unanswered there is a review finding, not a
discuss defect. Each entry may carry the house marker pair —
`[NEEDS CLARIFICATION: <question>]` with a `Recommended: <answer> — <reason>`
line beneath it, the shape `hex-init`'s plan and spec templates already define
— a live question is answered in the room, a marker handed forward to a gate
its asker will not attend.

## The restate-gate

The single approval gate, sitting at the exit before any drain: at entry
nothing is yet committed, and the irreversible act is handing a downstream
orchestrator a mandate. The deep-sweep offer is a spend confirmation, not a
second approval gate — there is **exactly one approval gate per run**, and
**every drain passes it, inline drains included**.

Before any drain, emit a six-part structured restate — Outcome (what will be
built or decided) · User (who it is for) · Why now (the trigger) · Success (how
it is judged) · Constraint (what bounds it) · Out of scope (what it
deliberately is not). Name in the same message what has already been written —
the discussion artifact and every research artifact, by path, plus any
`hex.md › Pointers` re-point made this run — and what the drain will touch: the
proposed-artifact list, the artifact's own header update, the two `hex.md` rows
from [Constraints](#constraints), and, for an inline drain, the stub deletion.
A resumed artifact whose `Updated:` predates this session also gets a one-line
staleness note: recorded decisions may have drifted since, and the receiving
claim diff is the real check. The restate scales: a short inline drain
collapses each part to a clause on one line — no part dropped — but the
separate explicit yes is never skipped.

Then ask for a separate, explicit yes. **Answering a clarifying question is
never consent**, and **a soft confirmation is not consent**: on "sounds good"
or "yeah ok", do not drain — ask for the explicit yes, and name that you are
asking for it. The wording is hex's own and varies naturally between
discussions; **never recite a script**. A pattern of instant unqualified yeses
may be gently flagged once — never repeated, never a block. A "no" returns to
the conversation with the disputed part named, not a re-ask of the whole
restate.

Whenever an artifact survives the drain, the drain appends a `Ratified:` line —
date and drain target — to the header, the durable record of the consent event,
and fills the optional `Confidence:` line where the provenance exists: who
ratified, and which research vintages back the decisions. An inline drain
leaves no artifact and no `Ratified:` line, so its outcome can never be
fast-path input to `/hex-architect`.

## Handoff

The [handoff contract](../hex-core/references/protocol.md#handoff-contract)
applies in substance: every drain ends with the terminal-state report and,
where a next command exists, the `Next:` line. Its orchestrator-only fields —
classification, tier, overlays — do not apply.

Four drain targets, adding zero new write paths. After the yes:

- **→ plan** — `Next: /hex-plan "<title>, per <artifact path>"`
- **→ ADR** — `Next: /hex-architect <artifact path>`
- **→ spec** — emit the plan command above plus a line stating that the spec
  is reached by `/hex-review`'s Fold-Back on the converged plan. This skill
  **never writes a spec and never invokes a fold**, so
  [`archive.md`](../hex-core/references/archive.md#safety-envelope)'s envelope
  stays the only fold path.
- **→ project context** — a durable convention the discussion surfaced is
  recorded post-gate as a promotion candidate in `hex.md › Memory`
  ([Constraints](#constraints)), where the next `/hex-init` re-audit picks it
  up and proposes it against the matching audit item, with consent
  ([`audit.md`](../hex-init/references/audit.md)) — the drain sets
  `State: handed-off → context`, writes `Ratified: <date> → context`, and
  states that re-audit as its next step, `Next: /hex-init`. Not
  [`protocol.md` § Upkeep step](../hex-core/references/protocol.md#upkeep-step)'s
  mechanism, which routes a *preference* to `hex.md › Preferences`; a project
  convention belongs in project context, written only by `/hex-init`. This
  skill **never writes CLAUDE.md or AGENTS.md**.

Neither downstream command carries a tier: this skill has none of its own, so
the receiving orchestrator's classifier resolves it, and a tier appears only
when the user named one at the restate. The exception is the → ADR target,
whose fast path refuses the lowest tier on arrival — the restate states the
`medium` floor instead of emitting a dead-end command.

Terminal states: `parked`, or
`handed-off → plan | architect | context | dropped` — a `State:` vocabulary
whose single home is the template `hex-init/assets/templates/discussion.md`,
which defines it while this file only consumes it. **`dropped` is a valid
success** — a discussion concluding the thing should not be built is reported
as a successful outcome with the reasoning preserved, never as an abort, and
carries **no `Next:` line**: nothing runs next. Every drain closes on:

```markdown
## Discussion Complete: <topic>

- State: `handed-off → plan | architect | context | dropped`, or `parked`
- Written: <discussion artifact>, <research artifacts>, `hex.md` Memory and
  Pointers rows — every path this run touched
- Next: `/hex-plan "<title>, per <path>"` · `/hex-architect <path>` ·
  `/hex-init` (→ context); no `Next:` line for `dropped` or `parked`
```

## Announce form

This skill prints **no announce block**. The contract is a shape, not a
whitelist: every disclosure the shared contracts mandate renders as **one line,
never a block**, and none is repeated. Nothing mandatory is dropped — only the
block is, and a later mandated disclosure adds a line, never a block. The
currently known set, explicitly not closed:

1. A research aside when a result lands:
   `— checked that: <one-line finding> [<source>]`
2. `— discussion notes: <path>`, printed once when entry writes the stub — a
   mode pitched as "don't edit anything yet" writes no file silently.
3. The deep sweep's batch split, with the cap's source
   ([`protocol.md` § Worker coordination](../hex-core/references/protocol.md#worker-coordination)).
4. `Degraded: inline workers — no subagent spawning` — research then runs
   inline, so a check briefly pauses the conversation, the deep sweep re-caps
   to 3, and the mode loses its differentiator. Printed once at the first
   degraded spawn: § Worker coordination prints degraded lines "at the gate",
   and this mode's only gate is the drain — too late for a spend disclosure —
   so it lands where rule 1's model line does.
5. The resolved literal model at the first spawn of a role — the disclosure
   [`models.md`](../hex-core/references/models.md#rules) rule 1 mandates,
   carried under this quiet form, and where a `models.overrides` escalation
   becomes visible.
6. A `Limits:` line, printed once, when a `hex.md › Preferences` limit is in
   force.
7. The second degraded axis when it composes:
   `Degraded: single session model — no per-spawn override; matrix advisory`,
   as its own line, per `protocol.md`'s one-line-per-degraded-axis rule.
8. The transport note for a researcher that failed to return, surfaced once.

**No phase announcements, no thread-board recital, no resolved-config table** —
unless the user asks, which is always honored.

## Constraints

The write surface is four destinations — the discussion artifact, research
artifacts, `hex.md › Memory`, and `hex.md › Pointers` — across five writes, and
*when* is as binding as *what*. Pre-gate, only:

- the discussion artifact itself;
- research artifacts in the convention-resolved research home;
- re-pointing a `hex.md › Pointers` row found drifted on consumption —
  [`memory.md` § Staleness](../hex-core/references/memory.md#staleness)
  maintenance, made in the same run and never deferred, and named at the
  restate alongside the rest of what has already been written.

Post-gate, at the drain alongside the handoff:

- the drain's own header update — `State:` to its terminal value, plus the
  `Ratified:` line and, where the provenance exists, the optional
  `Confidence:` line ([the restate-gate](#the-restate-gate));
- `hex.md › Memory` — the discussion hand-off record, the artifact index, and
  promotion candidates from [Handoff](#handoff);
- `hex.md › Pointers` — creating the discussions-home row.

These are ordinary upkeep writes deferred past the gate: nothing outside the
discussion's footprint exists before consent. This skill writes **no code,
config, plan, ADR, or spec, and never `hex.md › Preferences`**, which is
user-owned.

Undoing an abandoned pre-gate discussion means deleting the discussion file and
the research artifacts it lists under `## Research`; the research home is
shared with every other hex skill and is **never removed wholesale**. The two
`hex.md` rows exist only after the gate and revert by deleting two lines.
Federation: this skill sits outside the satellite halt's scope
([`memory.md`](../hex-core/references/memory.md#federation-satellites)) — it
resolves no plan and writes no plan or federation state.

The rule is a hardening, never a precondition: `hex-discuss` must be complete
and correct with the rule absent, and the rule-less run is this skill's own
degraded mode, reached automatically. A client hosting no ownable rule file
loses persistence convenience, never capability — everything above is
skill-body behavior. After a lapse, recovery is re-reading the discussion
artifact — whose header carries the state, not the stance — plus this file and,
where the rule landed, its `hex-state` line; or a fresh session, and **never
re-invoking this skill**, which returns "already loaded" rather than a fresh
copy. **No hex file may make a rule's presence a condition of any other
behavior.**

Client portability: [references/reach.md](references/reach.md) (C-721).

$ARGUMENTS
