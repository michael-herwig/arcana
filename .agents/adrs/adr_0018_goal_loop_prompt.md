# ADR: Goal loop — `/hex-loop` writes a goal file and prints the autonomous-run prompt

## Metadata

**Status:** Accepted (Michael, 2026-09-23, after implementation merged in PR #7 at `41ffe21`)
**Date:** 2026-09-23
**Deciders:** Michael Herwig (ratified discussion + amendment); drafted by /hex-plan (tier high)
**Issue/Ticket:** N/A
**Related:** `.agents/discussions/autonomous-goal-loop.md` (ratified 2026-09-23 → plan, plus its 2026-09-23 amendment) · plan `.agents/plans/plan_hex_loop.md` · `.agents/adrs/adr_0007_milestone_driver.md` (untouched, still Proposed) · `.agents/adrs/adr_0008_pre_plan_discussion_mode.md` (amended in the open, below) · `.agents/adrs/adr_0009_finalize_phase.md` (C-805 gains a named clause, below)
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions
- [x] OR the deviation is justified in the Rationale section below (four named deviations)
**Domain Tags:** devops | security (consent)

## Context

The user drives large goals by pasting hand-written autonomous `/goal`
prompts. The six prompts are in `.agents/research/discuss-goal-loop-examples.md`.
About 70% of each prompt is the same invariant block, and its caps drift from
run to run. The ratified discussion asks for a hex skill that writes the
per-run contract and prints that prompt from one template. It must not add a
fifth orchestrator; adr_0007's heavier design stays where it is. The design
questions are how far this reaches into four places:

- hex's binding contracts: DESIGN's two-layer model;
- finalize's consent model (C-805) and trust classes (C-815/C-816);
- adr_0008's closed set of four drain targets;
- protocol.md's closed gate-exemption list.

## Decision Drivers

- **Ratified outcome:** a merge-ready PR with no prompting. All six
  hand-written runs already ran `/hex-finalize` autonomously.
- **No weaker consent:** the grant must be authored by the human and must
  never arrive as branch content (C-815/C-816).
- **Single source:** the invariants live in one template, and nothing
  restates a hex-core contract.
- **Least surface:** no config-vocabulary bump, no engine, no run state
  beyond checkboxes.
- **Portability:** the body names capabilities, not tools. Only the `/goal `
  wrapper differs by client.

## Considered Options

### Option 1: Prompt-only printer, no goal file (the original ratified shape)

Superseded by the user's amendment of 2026-09-23. It has no durable per-run
contract, and the done criteria live only in the transcript.

### Option 2: Goal file carries every grant, and the prompt says "follow the goal file" (first plan draft)

| Pros | Cons |
|------|------|
| Shortest prompt | The goal file is committed onto the feature branch. On a PR source that branch is writable by any contributor, so the grant would become branch content that widens the grant, which C-815/C-816 forbid. |

Rejected.

### Option 3: Grants rendered literally in the pasted prompt; the goal file only narrows (chosen)

| Pros | Cons |
|------|------|
| The human sees every grant and pastes it themselves, so authority stays in text the human pastes. A contributor-editable file can only narrow. | The grants cost prompt budget, so some prompts approach the 4,000-char cap. |

### Option 4: Pre-grant off by default; the run stops at the finalize gate with a draft PR

| Pros | Cons |
|------|------|
| C-805 stays untouched | The ratified done state becomes unreachable by default. Every run would flip the grant on, so the default protects nothing. |

Rejected.

## Decision

**Option 3.** `/hex-loop` is a hex bundle member, not an orchestrator. It
reads a source and the `Goal loop:` prose hint in `hex.md › Preferences`,
writes one goal file, and prints one prompt of at most 4,000 characters. It
starts nothing, pushes nothing, and commits nothing.

Normative amendments, each made in the open:

1. **adr_0008 closed set four → five.** `/hex-discuss` gains the drain
   target `→ loop`, which leads to `State: handed-off → loop` and
   `Next: /hex-loop <artifact path>`. It adds zero new write paths, and a
   `→ loop` drain always keeps its artifact, never draining inline. The
   "handoff fidelity" driver is widened by one route that leads to a new
   skill. adr_0008's own text is not edited, and `hex/DESIGN.md` round 23
   records the amendment.
2. **protocol.md gate exemption: a fourth named member.** The ground: `/hex-loop`
   spawns nothing and starts nothing. It writes one goal file inside its own
   home, and the user's paste is the approval.
3. **finalize.md C-805 gains a named autonomous-run clause (C-805a).** Both
   halves of the consent model are met by a **human-pasted prompt** — the test
   is pasted, not authored (the `/hex-loop` prompt is model-rendered and
   human-pasted):
   - the class grant, because the human typed or pasted the instruction to
     invoke `/hex-finalize`;
   - the instance gate, because the prompt names, for *this run's feature
     branch*, which post-gate acts of C-811 it grants — any of act 2
     (force-push under the lease), act 3 (dispatch of the documented
     release-grade workflows under C-813) and act 4 (PR create or update
     with the draft → ready flip), each in full, except that act 4's flip is
     granted or withheld on its own: withheld, the PR stays draft, and the
     flip is disclosed as withheld and reported not met.

   Under that clause (the shipped definition is
   `hex/hex-core/references/finalize.md` § Consent model, C-805a):
   - the gate prints its **full disclosure to the transcript** and proceeds;
   - the grant is the verbatim text of a human turn in the session that
     runs `/hex-finalize`. A relayed brief, a compaction summary or an
     earlier transcript is not a grant. Without a verbatim grant, a
     never-prompt session treats every remote act as omitted (fail-closed);
   - file content, the goal file included, **never widens** that grant.
     C-815/C-816 still hold word for word;
   - a pasted grant that omits an act has that act skipped, not asked:
     disclosed as withheld and reported not met;
   - workflow drift withholds act 3: on C-813's drift trigger — any file
     under the workflow directory differs, branch against trunk — act 3 is
     skipped, disclosed as withheld and reported not met — with no human
     reading the gate, a drift disclosure is no control.
4. **Preferences prose hint, not config.** The `Goal loop:` bullet is a
   `hex.md › Preferences` prose hint read only by `/hex-loop`. It follows the
   finalize series-shape precedent (C-815's Authoritative row). There is no
   config-vocabulary bump: config.md § "What config cannot express: milestone
   autonomy" still holds. Its grammar is defined in `hex/hex-loop/SKILL.md`,
   and memory.md's Preferences row links there.

### Rationale — named deviations from `hex/DESIGN.md`

| Deviation | Why | Bound |
|---|---|---|
| **Two-layer model.** Machine and project run rules (`rule:`, `verify-bypass:`, `deep-verify:`) sit in Preferences, not in project context. | Ratified decision. They are operator allowances for unattended runs on this host. | They are rendered verbatim — an allowance as a quoted echo labelled `hint (local, this repo only)` — and never interpreted. `deep-verify` only **names which already-documented release-grade run counts as evidence**, so it gains no dispatch power (C-813 is unchanged). Every sub-orchestrator brief carries the goal file's Rules verbatim. |
| **C-805 human-typed grant** | Covered by amendment 3 | The grant is a human-pasted prompt only; the test is pasted, not authored. |
| **"hex never merges / releases"** | A user's extras may grant merge or release (hand-written example 3 did). | The shipped template grants neither. A merge or release grant — like every remote act beyond I9's fixed defaults — comes only from the human's invocation extras, rendered into the pasted prompt; a `Goal loop:` hint grants only local acts in this repo's working tree. It stays with the pasted session and is never relayed into a sub-orchestrator brief. |
| **"hex commits only in execute/finalize"** | The session commits the goal file first on the feature branch, and commits progress ticks between hex-mode runs, so that `/hex-finalize`'s clean-tree halt holds. | `/hex-loop` itself commits nothing. The commits are the pasted session's own acts under the human's prompt. |

### Always-on budget (DESIGN.md round-9 erratum)

`hex-loop` ships **no rule**. Its only always-on surface is the frontmatter
description line: one trigger sentence of ≤ 300 characters that carries no
body prose. `claude.disable-model-invocation: "true"`, so on clients that
honor that key the line may cost nothing always-on.

## Consequences

- There is a new artifact class, goals, at `.agents/goals/<slug>.md` by
  default. Its template is `hex/hex-init/assets/templates/goal.md`, and
  `/hex-init` records the `Goals:` Pointers row with consent. It holds no
  `State:` line and no cursor.
- A finalize run started from a goal prompt is no longer interactive, and
  the disclosure in the transcript is its audit trail.
- The cross-model adversary pass has **not** run on this decision (see the
  plan's deferred findings). Run it before Accept.

## Compliance

`grim build` for `hex/hex-loop`, `hex/hex-core`, `hex/hex-discuss`,
`hex/hex-init`, `hex/hex-architect` and `hex/hex-finalize`, plus
`task publish -- --dry-run`. The round-trip evidence is
`.agents/research/hex-loop-roundtrip.md`.
