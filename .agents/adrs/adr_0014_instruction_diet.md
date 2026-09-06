# ADR: Instruction diet — split `protocol.md` by consumer set

## Metadata

**Status:** Proposed
**Date:** 2026-09-06
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A — raised from the execution-runtime program
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below —
      this ADR **amends** the constitution's single-source rule, which
      today names `protocol.md` as the home of canonical text. The
      amendment is stated in full under *Decision Outcome › What
      `hex/DESIGN.md` round 19 records*.
**Domain Tags:** infrastructure
**Supersedes:** N/A
**Superseded By:** N/A

## Context

Every hex orchestrator run pays for `hex-core/references/protocol.md`
before it does any work. The file is **123,031 bytes / 1,979 lines**
across 19 `##` sections. Measured against the current tree
(`hex/execution-runtime-program`), it is between **43% and 54% of the
total instruction bytes any mode pulls into context**:

| Mode | Total instruction bytes loaded | `protocol.md` share |
|---|---:|---:|
| hex-plan (medium) | 228,464 | 53.9% |
| hex-execute (medium) | 281,166 | 43.8% |
| hex-review (medium) | 272,399 | 45.2% |
| hex-architect (medium) | 244,871 | 50.2% |
| hex-finalize | 245,781 | 50.1% |

Three facts make this worth a decision rather than a cleanup commit.

**1. Nothing in the bundle actually mandates the load.** No `SKILL.md`
and no tier file anywhere writes an imperative "Read `protocol.md`".
Every hex-core citation is a link — `(see protocol.md#anchor)`,
"defined in `protocol.md`" — while only `classify.md` and
`tier-{medium,high}.md` carry an explicit `Read` verb. The 123 KB is
paid because an agent that follows a link opens a **file**, not a
section. The unit of reading is the file, so the file is the only place
the cost can be controlled.

**2. Two worker personas pay the full file for a rule of a few
kilobytes.** `references/workers/reviewer.md` sends every reviewer to
`../protocol.md#finding-severity` — a **2,094-byte** section inside a
**123,031-byte** file. `references/workers/builder.md` sends every
builder to `../protocol.md#scoped-check` — **13,175 bytes** of
`## Verification`, same file. The RCA
(`.agents/research/rca-review-fix-loop-wall-clock.md`) establishes that
review-fix wall clock is proportional to serial worker round-trips.
Builder and reviewer are the two personas on that serial path, and each
spawn re-reads the whole file.

**3. The file grows monotonically, by rule.** `hex/DESIGN.md`'s
single-source rule names `protocol.md` specifically as the destination
for shared text. Round 17 (`§ Per-WP effective-tier round`) states it:

> **Thin dispatchers + per-tier phase files** — upheld **outside
> `hex-execute`'s tier files**: canonical text lands once in
> `protocol.md` and every consumer takes a link or a one-clause
> qualifier — the repair round 13 named when it recorded that nine
> restatements turned a one-line contract change into a ten-file diff.

Round 13 (`§ Adversary no-review round`) named that repair in the same
terms — "the repair is for `protocol.md` to own the sentence and the
tier files to link it". The rule is correct and this ADR does not
weaken it. But it is written with a **file name where it means a
property**, and so every correctly-executed round adds to one file.
Wave 0/1 of the current program added roughly 30% more prose to
`protocol.md` (per-WP effective tier, adversary stall bound), and
`adr_0013`'s liveness and resources sections land there next.

The rule the diet needs already exists and already ships — for workers
only. `hex-core/references/workers.md`, in its opening section above
`## Universal worker protocol`:

> Full personas — mission, focus modes, spawn-prompt template, output
> contract — live one file per role under [`workers/`](workers/).
> **Load only what runs**: the orchestrator always reads this index; it
> reads a persona file only for roles in the resolved spawn set.

Nine personas were split out of one index on exactly this reasoning.
This ADR extends the same rule one layer up, to the contracts
orchestrators read.

`hex/DESIGN.md` carries **no decision at all** on file size, context
budget, or load scoping — the strings "context budget", "file size" and
"load only what runs" appear nowhere in it. This is a gap in the
constitution, not a contradiction of it.

## Decision Drivers

- **Wall clock.** Every serial worker round-trip on the review-fix path
  re-reads instruction bytes; the two personas on that path each pay
  123 KB for ≤13 KB of contract.
- **Monotonic growth.** The single-source rule, as written, guarantees
  the file only gets bigger. Three more ADRs are queued against it.
- **No rule may gain a second home.** Any split that copies text to
  serve two consumers reintroduces the drift the single-source rule
  exists to prevent — round 13's "nine restatements" failure.
- **Hundreds of live links.** 313 `protocol.md#anchor` links across 38
  files in `hex/` source, plus ~418 prose `§`-citations repo-wide, plus
  `adr_0010`/`adr_0012`/`adr_0013` citing sections by heading and
  quote. All must keep resolving.
- **Zero runtime semantics change.** This is a relocation. Any option
  that alters what a rule *says* is out of scope.

## Industry Context & Research

**Research artifact:** N/A — no external axis ran. The evidence base is
three internal measurement passes over the current tree, reported
inline above and under *Technical Details*. The relevant prior art is
in-repo and in-harness rather than industry-wide.

**Trending approaches:** Progressive disclosure is the shipped pattern
for agent instruction files in this harness — a small always-loaded
entry point (`SKILL.md`) plus a `references/` tree the agent opens on
demand. hex already applies it twice: `SKILL.md` → `tier-*.md`
dispatch, and `workers.md` → `workers/<role>.md`. `protocol.md` is the
one file in the bundle that opted out of it.

**Key insight:** The measured need map shows the split is **naturally
per-topic, not per-consumer**. Three of the four largest sections have
two or more real consumers — `## The Review-Fix Loop` (execute 22
links, review 7), `## Parallel-by-default decomposition` (execute 26,
plan 12), `## Worktree work-package mechanics` (execute 16, plan 4). A
literal per-consumer file set would have to copy those three sections
into two files each, which the "no second home" constraint forbids
outright.

## Considered Options

### Option 1: Per-consumer files

**Description:** `protocol-execute.md` (loop + worktree +
verification), `protocol-review.md` (loop + convergence + adversary),
`protocol-plan.md` (decomposition), as originally sketched.

| Pros | Cons |
|------|------|
| Each mode reads exactly one file | The Review-Fix Loop, decomposition and worktree mechanics each have 2+ consumers — the file set requires copying them |
| Simplest possible load rule | Copying breaks the single-source rule; a shared-residue file to avoid copying turns this into Option 2 with worse names |
| Names map to commands | A rule's home would depend on who reads it, so every new consumer moves text |

### Option 2: Per-topic files at `##` boundaries + a load map (chosen)

**Description:** Cut `protocol.md` only at existing `##` section
boundaries. Each moved section keeps its heading and its anchor slug
verbatim. `protocol.md` retains the sections every mode reads and gains
a load-map table saying which file each mode opens and when. Six new
sibling files in `hex-core/references/`.

| Pros | Cons |
|------|------|
| No rule is copied — each keeps exactly one home | Six new files instead of one |
| Headings unchanged ⇒ every ADR heading+quote citation survives untouched | A mode that runs many phases opens several files |
| Anchors unchanged and all files are siblings ⇒ link migration is a basename swap | Load discipline is prose, not enforced by a tool |
| The load map is itself single-source | `hex-execute` gets little relief (see *Consequences*) |

### Option 3: Index-only — keep one file, add a per-mode section index

**Description:** No split. Add a table at the top of `protocol.md`
listing which sections each mode needs, and instruct ranged reads.

| Pros | Cons |
|------|------|
| Zero link churn | Does not reduce bytes — an agent opening `protocol.md#anchor` still loads the file |
| One commit | Ranged reads by line offset are exactly the fragile pin `adr_0010`'s and `adr_0013`'s drifted line citations already demonstrate |
| No new files | Leaves the monotonic-growth driver entirely unaddressed |

## Decision Outcome

**Chosen Option:** Option 2 — per-topic files at `##` boundaries plus a
load map.

**Rationale:** The measured consumer map, not a naming preference,
forces it. Per-consumer files (Option 1) cannot express a contract with
two consumers without copying it, and "no rule gains a second home" is
the one hard constraint. Option 3 does not move any bytes. Option 2
cuts at boundaries that already exist, which is what makes the
migration mechanical: **every heading is preserved verbatim, so every
anchor slug is preserved, and every new file is a sibling of
`protocol.md`, so every relative link prefix is preserved too.** The
only thing that changes in ~313 links is a basename.

### The split (C-970)

Cut points are `##` boundaries only. **No `##` section is split
internally**, and no heading text changes. This is the rule that keeps
`adr_0010`/`adr_0012`/`adr_0013`'s heading-and-quote citations valid
without editing a single one of them.

| File | `##` sections it owns | Bytes | Consumers that run it |
|---|---|---:|---|
| `protocol.md` (spine) | Shared shape · Tier grammar · Overlay grammar · The meta-plan approval gate · Spawn-selection precedence · Worker coordination · Traceability IDs · Untrusted-text echoes · Constitution gate · Handoff contract · Upkeep step | 27,171 | every orchestrator |
| `loop.md` | The Review-Fix Loop (+ its 4 `###`) · Convergence contract | 21,784 | execute, review |
| `decompose.md` | Parallel-by-default decomposition (+ `### The effective tier`) | 29,146 | plan, execute |
| `worktree.md` | Worktree work-package mechanics | 19,405 | execute |
| `verify.md` | Verification (+ `### Scoped check`, `### Checkpoints`) | 13,175 | execute, finalize, **builder worker** |
| `adversary.md` | Adversary contract | 10,256 | any mode with `adversary=on` |
| `severity.md` | Finding severity | 2,094 | review, **reviewer worker** |

Sections sum to 123,031 — the current file exactly. The spine gains one
new table (the load map, below); nothing else is authored.

`severity.md` at 2,094 bytes is the smallest file in the set and the
highest-leverage one: it is what every reviewer worker reads, on the
serial path the RCA measures.

### The load map (C-971)

The spine carries one table — the single definition site for what each
mode opens. It is a **budget rule, not a permission**: a mode may
follow any link, but it opens a topic file when a phase it is running
executes against that contract, never because prose mentions it. This
is the workers.md rule quoted verbatim in *Context*, one layer up.

| Mode | Opens beyond the spine |
|---|---|
| `/hex-plan` | `decompose.md` |
| `/hex-execute` | `decompose.md`, `worktree.md`, `loop.md`, `verify.md` |
| `/hex-review` | `loop.md`, `severity.md` |
| `/hex-architect` | — |
| `/hex-finalize` | `verify.md` |
| any of the above with `adversary=on` | `+ adversary.md` |
| `builder` worker | `verify.md` only |
| `reviewer` worker | `severity.md` only |
| every other worker persona | — |

### Anchor migration (C-972)

Three citation surfaces, three answers:

1. **`#anchor` markdown links (313 in `hex/` source, 38 files).**
   Mechanical rewrite: the anchor slug and the relative directory
   prefix are both unchanged, so each of the 24 live anchors maps to
   exactly one basename substitution. One `sed -E` per anchor, driven
   off the table above. **Acceptance: zero occurrences of
   `protocol.md#<moved-anchor>` remain, and every `#anchor` in the
   bundle resolves to a heading in the file it names** — a grep loop,
   run as part of the WP's verification.
2. **Prose `§` citations naming a heading (~418 repo-wide, incl.
   `adr_0010` 20, `adr_0012` 28, `adr_0013` 47).** Headings are
   preserved verbatim, so every one of these stays *semantically*
   correct; only the file name in the sentence goes stale. Shipped
   `hex/` prose is corrected in the same change. **Past ADRs and plans
   are not edited** — they are records of decisions taken against the
   file as it stood.
3. **Line-number pins (`adr_0010` 8, `adr_0013` 3).** Already drifted
   before this ADR, by the project's own record. Not repaired here.

The compatibility record for (2) and (3) is a **single old→new mapping
table in `hex/DESIGN.md` round 19**, plus a short "what moved where"
pointer at the top of the spine. One table, two placements, no
per-ADR errata.

### What `hex/DESIGN.md` round 19 records (C-973)

Round 18 belongs to `adr_0013` and is in flight; round 19 is this
ADR's, appended after it.

1. **One amendment.** The single-source rule's *destination* is
   generalised: canonical text lands once **in `hex-core/references/`,
   in the topic file whose consumer set it serves** — not, as round 17
   and round 13 both wrote it, in `protocol.md` specifically. The rule
   itself — one home per contract, consumers link and never restate —
   is unchanged and unweakened. Only the sentence's file name becomes a
   property.
2. **One new binding rule.** "Load only what runs", quoted verbatim
   from `workers.md`, extends from worker personas to orchestrators,
   with the load map as its table. `hex/DESIGN.md` has no prior
   position on context budget, so this adds one rather than amending
   one.
3. **The old→new section mapping table**, as the compatibility record.
4. **Considered and not deviated:** thin dispatchers + per-tier phase
   files (unchanged — the spine and topic files are all Layer-0
   reference, not dispatchers); capability classes never literal model
   names (no model name appears in any moved or authored text); the
   two-layer knowledge model (untouched — every moved section is
   Layer-0 hex protocol and nothing crosses into project context);
   `config.md` gains no key; no runtime semantics change anywhere.

### Rollout order (C-974)

Executes **after `hex/adr-0013-integration` merges**. That branch adds
liveness and resources sections to `protocol.md`; they are assigned to
a file by the same `##`-boundary rule at Stub time, and every byte
figure in this ADR is **re-measured against the merged `protocol.md`
before the first cut**. The figures here are a baseline for the
decision, not an acceptance criterion. Round 19 cannot be appended
until round 18 exists.

### Quantified Impact

Protocol-family bytes per mode. Today every row is 123,031.

| Mode | Before | After | % of today | Notes |
|---|---:|---:|---:|---|
| `/hex-architect` | 123,031 | 27,171 | **22%** | spine only |
| `/hex-finalize` | 123,031 | 40,346 | **33%** | + `verify.md` |
| `/hex-review` | 123,031 | 51,049 | **41%** | + `loop.md`, `severity.md` |
| `/hex-plan` | 123,031 | 56,317 | **46%** | + `decompose.md` |
| `/hex-execute` | 123,031 | 110,681 | **90%** | runs nearly every contract |
| `builder` worker | 123,031 | 13,175 | **11%** | per spawn, on the serial path |
| `reviewer` worker | 123,031 | 2,094 | **1.7%** | per spawn, on the serial path |
| `+ adversary=on` | — | +10,256 | — | conditional, all modes |

**Target budget (C-975):** ≤50% of today's protocol-family bytes for
every orchestrator **except `/hex-execute`**, and ≤15% for every worker
persona. Both are met by the table above.

**`/hex-execute` is an explicit non-goal of this ADR, and the ≤40%
target it was given is not achievable by splitting `protocol.md`.**
Execute genuinely runs decomposition, worktree mechanics, the
review-fix loop and verification — 90% of the file is contract it
executes, not prose it passes over. Its instruction diet is a different
file: `hex-execute/SKILL.md` is 38,543 bytes, the largest `SKILL.md` in
the bundle by 9 KB, and round 17 already recorded its three tier files
as the one place the thin-dispatcher rule is knowingly deviated from.
That is a separate ADR. Stating this rather than hitting the number by
splitting a `##` section internally is deliberate: an internal split
would break the heading citations in all three prior ADRs to buy
`/hex-execute` 13 percentage points it still would not clear.

### Consequences

**Positive:**
- The two personas on the serial review-fix path drop from 123 KB to
  13 KB and 2 KB per spawn.
- Four of five orchestrators land at or under half of today.
- Growth is bounded per topic: `adr_0015` adding to the loop grows
  `loop.md`, and every mode that does not run the loop is unaffected.
- The single-source rule gets stronger, not weaker — its destination
  becomes a property a reviewer can check ("does this contract's
  consumer set match its file?") instead of one hardcoded file name.

**Negative:**
- Six more files in `hex-core/references/`, and a reader looking for a
  contract must consult the spine's pointer table first.
- Load discipline is prose. Nothing prevents a mode from opening every
  file; the budget is a review criterion, not an enforced limit.
- `/hex-execute` gets almost nothing.

**Risks:**
- *A link is missed and silently resolves to a heading that no longer
  exists there.* Mitigated by the acceptance check in C-972: a grep
  loop proving every `#anchor` in the bundle resolves in the file it
  names. There are zero dead anchors today, so the check has a clean
  baseline to hold.
- *`adr_0013`'s sections land between the measurement and the cut.*
  Mitigated by C-974: the inventory is re-measured at Stub time and the
  ADR's figures are explicitly a baseline, not an acceptance criterion.
- *The `.claude/skills/` mirror drifts.* It is a `grim`-installed copy,
  regenerated on install, and is not edited by this change.

## Non-Functional Requirements

| Axis | Impact of this decision |
|---|---|
| Scalability | Positive — per-topic growth replaces monotonic growth of one file; a contract's size now affects only the modes that run it. |
| Availability | Not affected. |
| Latency | The direct target. Instruction bytes per worker spawn drop 89% (builder) and 98% (reviewer) on the serial path the review-fix RCA measures; four of five orchestrators drop ≥54%. Wall-clock effect is proportional to spawn count, not measured here. |
| Security | Not affected — no rule's text changes, including `§ Untrusted-text echoes`, which stays in the spine. |
| Cost | Positive and proportional to the latency line: fewer input tokens per spawn, at every spawn. |
| Operability | Mixed. Finding a contract needs one indirection through the spine's pointer table; changing a contract touches one smaller file instead of one large one. |

## Technical Details

### Architecture

```
hex/hex-core/references/
  protocol.md    27,171   spine: gate, spawn precedence, worker coordination,
                          tier/overlay grammar, traceability, echoes,
                          constitution gate, handoff, upkeep
                          + the load map + the what-moved-where pointer
  loop.md        21,784   Review-Fix Loop (+4 ###), Convergence contract
  decompose.md   29,146   Parallel-by-default decomposition (+ effective tier)
  worktree.md    19,405   Worktree work-package mechanics
  verify.md      13,175   Verification (+ Scoped check, Checkpoints)
  adversary.md   10,256   Adversary contract
  severity.md     2,094   Finding severity
                 -------
                123,031   = today's protocol.md, byte for byte
```

### API Contract

The migration rule, in full — this is the whole mechanical surface:

```
For each of the 24 live anchors:
  <prefix>protocol.md#<slug>   ->   <prefix><newfile>#<slug>

  <prefix> is preserved verbatim (all new files are siblings of
           protocol.md, so every relative path already resolves)
  <slug>   is preserved verbatim (no heading text changes)
  <newfile> comes from the split table, and only from it

Acceptance:
  grep -rE 'protocol\.md#(the-review-fix-loop|convergence-contract|
    parallel-by-default-decomposition|the-effective-tier|
    worktree-work-package-mechanics|verification|scoped-check|
    checkpoints|adversary-contract|finding-severity|
    the-last-reviewed-anchor|anchor-validation|delta-round-scope|
    the-diminishing-returns-stop)' hex/   ==>  no matches

  every '<file>.md#<slug>' link in hex/ resolves to a heading in <file>
```

### Data Model

N/A — no persisted state, no config key, no schema.

## Implementation Plan

1. [ ] Re-measure `protocol.md`'s `##` inventory against merged
       `hex/adr-0013-integration`; assign its new sections to files by
       the `##`-boundary rule.
2. [ ] Cut the six topic files; verify byte-for-byte reconstruction
       against the pre-cut file.
3. [ ] Author the load map and the what-moved-where pointer in the
       spine.
4. [ ] Rewrite the anchor links across `hex/`; run the acceptance grep.
5. [ ] Correct shipped `hex/` prose `§` citations that name the file.
6. [ ] Re-home the two worker personas: `builder.md` → `verify.md`,
       `reviewer.md` → `severity.md`.
7. [ ] Append `hex/DESIGN.md` round 19 with the amendment, the new
       binding rule and the old→new mapping table.
8. [ ] `grim build` every changed skill directory; `CHANGELOG.md` entry.

## Validation

- [ ] Acceptance grep from *API Contract* returns no matches, and every
      `#anchor` in `hex/` resolves to a heading in the file it names.
- [ ] Concatenating the seven files reproduces the pre-cut
      `protocol.md` content with no text added or removed beyond the
      load map and the pointer table.
- [ ] Per-mode byte figures re-measured post-cut meet C-975 (≤50%
      orchestrators except execute, ≤15% workers).
- [ ] `grim build` exits 0 for every changed skill directory.
- [ ] No literal model name appears in any moved or authored text.

## Open Questions

- [NEEDS CLARIFICATION: does `## Verification` belong in the spine
  rather than `verify.md`? Every mode links it, but only execute,
  finalize and the builder worker run it.] **Recommended:**
  `verify.md`, as tabled — *Recommended:* the builder worker is on the
  serial path and moving it is what takes that persona from 123 KB to
  13 KB; the modes that merely link it pay one file open.
- [NEEDS CLARIFICATION: should `/hex-execute`'s 90% figure block this
  ADR until its own diet is designed?] **Recommended:** no —
  *Recommended:* the worker-spawn saving is independent of execute's
  orchestrator load and is where the wall-clock evidence points; a
  separate ADR for `hex-execute/SKILL.md` and its tier files is the
  right shape for that problem.
- [NEEDS CLARIFICATION: is one commit the right granularity for the
  313-link rewrite, or should the cut and the rewrite be separate
  commits?] **Recommended:** one commit per topic file, each carrying
  its own link rewrite and passing the acceptance grep — *Recommended:*
  a half-migrated tree has broken links, so no commit may leave one.

## Links

- Related ADR: `adr_0010_execution_performance.md`,
  `adr_0012_per_wp_effective_tier.md`,
  `adr_0013_runtime_contracts.md` — all three cite `protocol.md`
  sections by heading and quote; C-970 preserves every heading so none
  needs editing.
- Constitution: `hex/DESIGN.md` — round 13 `§ Adversary no-review
  round`, round 17 `§ Per-WP effective-tier round` (the single-source
  rule this ADR amends); round 19 is this ADR's.
- Prior art in-repo: `hex/hex-core/references/workers.md`
  § opening — the "Load only what runs" rule this ADR extends.
- Evidence: `.agents/research/rca-review-fix-loop-wall-clock.md`.

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-09-06 | /hex-architect (medium) | Initial draft |
