# ADR: Retro — friction capture in the one hex rule, and a script-folded findings ledger

## Metadata

**Status:** Proposed
**Date:** 2026-09-23
**Deciders:** Michael Herwig (ratified discussion); drafted by /hex-plan (tier high, architect)
**Issue/Ticket:** N/A
**Related:** `.agents/discussions/retro.md` (ratified 2026-09-23 → loop) · goal `.agents/goals/retro.md` · research `.agents/research/retro-{technology,patterns,domain}.md`, `discuss-retro-*.md` · `adr_0008` (C-719, rule is hardening) · `adr_0014` (instruction diet) · `adr_0018` (goal loop; session-commit deviation extended here)
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions
- [x] OR the deviation is justified in the Rationale section below (five named deviations, one stated bounded growth)
**Domain Tags:** devops | security (untrusted agent-written input)

## Context

Agents trip over the same skill defects repeatedly, and nothing turns that
into landed fixes: the Upkeep step has produced one `hex.md › Memory` entry
ever, and none of the twelve hand-logged dogfood findings
(`.agents/handover_dogfood_findings.md`, F-001..F-012) has a fix in `hex/`
except F-001. The ratified discussion asks for hybrid capture (agent
self-report plus objective trajectory signals), a lock-free per-entry inbox
that survives worktree removal, attribution to artifact+version or the
project, a ledger valued by recurrence × cost over days-long loops, and a
`/hex-retro` skill that proposes — never silently applies — edits with their
rationale. Two decisions are load-bearing and one-way-ish: **where the
capture instruction lives** (always-on cost, reach) and **who writes the
ledger** (correctness of the arithmetic that decides "big value").

## Decision Drivers

- **Rule singularity** (`hex/DESIGN.md` round 9): the always-on surface is
  one artifact that grows by single lines, never by artifacts; the rule is a
  hardening, never a precondition (`adr_0008` C-719).
- **Mechanical ledger:** "maintained by retro mechanically, never by agents
  by hand" (ratified). Occurrence counts, cost sums and reopen flips decide
  unattended routing, so they must be arithmetic, not model recall.
- **Consume→fix is the bottleneck**, not capture: success = findings turned
  into landed changes.
- **Portability:** capture must work from any client with a file-write
  capability; the objective channel may be client-specific and degrade.
- **Untrusted input:** 2026 memory-poisoning evidence (OWASP ASI06;
  content screening detects 0/360) — the human/merge gate is the only
  defense with evidence, so no classifier gate.
- **Budgets:** capture rule a few lines; `hex-loop` paste ≤ 4,000 chars.

## Considered Options

### Decision A — capture surface

**A1: a new `hex-retro-capture` rule artifact.** Clean ownership, own
install toggle. Con: breaks rule singularity outright (a rule per feature),
doubles the always-on artifact count. **Rejected.**

**A2: one three-line paragraph appended to `hex/hex-state.md` (chosen).**
One artifact grows by lines, the round-9 contract — though by three lines,
not round 9's "single concrete line per shipped mode" (stated below).
Reaches every subagent on rule-capable clients, not only hex spawns. Con:
+953 B always-on plus +15 B keywords (1,502 → 2,470 B, measured) paid in
every session; standalone text must echo the required field names
(single-source tension, bounded below).

**A3: a `workers.md` duty in every hex spawn brief.** Zero always-on cost.
Con: reaches only hex workers, never ad-hoc subagents — the ratified
decision is "a published rule only, no `workers.md` duty". **Rejected.**

### Decision B — ledger shape and write authority

**B1: agent-edited markdown ledger with a fixed per-finding shape (the
dogfood file, disciplined).** Zero code, readable in any client, no
`python3`, and the model already writes detailed findings — the dogfood
file's twelve entries each carry a tell and a proposed change. Con: occurrence counts, cost sums and
reopen flips — the numbers that decide unattended routing — are model
recall across days-long loops; one file conflicts across loop branches;
that file's record is twelve findings, one fix. **Rejected** on the
ratified mechanical-ledger requirement, not on writing quality.

**B2: one committed JSON file per finding, written only by a stdlib script
from model-tagged decisions (chosen).** The model judges (cluster: match an
existing id first, else create; route; propose); `retro.py fold` does the
bookkeeping (occurrences, first/last seen, cost sums, status flips,
idempotent consumption). Changelog-fragment layout: two branches touching
different findings never conflict. Con: hex's first shipped executable;
needs `python3`.

**B3: single committed table (JSON/TOML/markdown), script-folded.**
Mechanical, one file to read. Con: every fold rewrites one anchor — merge
conflicts across loop branches; `merge=union` does not run server-side.
**Rejected.**

**B4: model-written strict-format ledger, checked by a validator script.**
Keeps the model as the writer and a script only as a gate. Con: the
validator can check shape, not arithmetic — a wrong occurrence count or
cost sum is well-formed; the ratified requirement is a mechanical ledger,
and model arithmetic is exactly what the dogfood file shows failing.
**Rejected.**

### Decision C — objective channel

**C1: `retro.py mine` over Claude Code transcripts, shape-guarded
(chosen).** Stdlib only, same script as the fold. Con: undocumented,
changing format; Claude Code only.

**C2: no miner in v1 (self-reports only).** Smallest ship. Con: the
ratified objective channel is load-bearing for recurring cost — agents do
not notice (or report) a gate that costs ten minutes every run, and
self-estimated cost is never trusted. **Rejected.**

**C3: `jq`-based miner.** Terse JSONL filters. Con: `jq` is not guaranteed
installed; `python3` is already required (by `hex-loop`), so a second tool
adds a dependency for no capability. **Rejected.**

## Decision Outcome

**Chosen: A2 + B2 + C1.** Summary of the shape (contracts in the plan,
`C-1420`–`C-1454`):

1. **Capture.** Three lines in `hex/hex-state.md`: on real friction, write
   one JSON entry (`v, ts, kind, scope, artifact, what, tell`; optional
   `proposed_change, severity, evidence`) to `inbox/` under the Pointers
   `Retro:` home, else `.agents/retro/inbox/`, in the **main checkout**
   (first `git worktree list` entry), a plain in-repo dir — temp
   `.<name>.tmp` then rename to `<UTC ts>-<8 random hex>.json`; no lock;
   never edit a skill or rule for it. The recipe is the writer — no writer
   script; the inbox ignores itself (`inbox/.gitignore` `*`, created by
   the first run).
2. **Objective channel.** `retro.py mine` reads Claude Code transcripts
   (undocumented schema → shape-guarded; known non-tool record types
   skipped; unknown shape → a `Degraded:` line, never a guess): recurring
   command cost (program + a lowercase subcommand only), repeated tool
   errors, attributed to the most recent skill invocation else `project`,
   replayed per changed file against machine-local emitted totals (deltas,
   no timestamp watermark). Only entries `mine` itself wrote carry
   trusted cost. No transcripts (other clients) → `Degraded:`.
   `/insights` rejected (no schema, no attribution). **No hooks in v1**;
   once grim publishes hooks, a follow-up plan replaces the miner, not the
   rule.
3. **Ledger.** `.agents/retro/ledger/<id>.json`, sorted keys, committed;
   raw inbox gitignored, consumed entries moved to `inbox/consumed/`.
   Lifecycle `open | deferred | fixed | reopened`; a `fixed` row reopens on
   an occurrence **after** the fix **from a version not seen before it**
   (Sentry's regression rule; `version` stamped at mine time for
   trajectory entries, at fold time for self entries, from `grimoire.lock`
   `pinned`/`hash`; `unknown` is never stale). Big value: cumulative
   objective cost ≥ 10 % of the loop's wall time, or ≥ 3 occurrences across
   ≥ 2 folds; constants live once in `hex-retro/SKILL.md` § Thresholds,
   which the script parses at runtime. Fold is crash-safe: a filename in
   any row is never assigned again, and `folded_at` lets the next run
   re-propose rows a crash left unreported.
4. **Gate.** Interactive: report + proposals; local edits applied to the
   working tree only on one explicit yes; never commits. Loop
   (`/hex-retro --loop <goal file>` at each checkpoint — after an outer
   cycle and **before** the closing `/hex-review`, never the last act
   before `/hex-finalize`): an **allow-list** is checked before size —
   only proposals whose every target lies inside a path-sourced skill or
   rule source dir may be applied (small: unasked, the **session** commits
   them) or routed in-loop (large: `/hex-plan`→`/hex-execute` only inside
   the goal's scope and over the bar, one I8 cycle, reason in the commit,
   allow-list carried into the briefs); every other target → Memory
   candidate + Deferred; upstream → issue draft. Gate: the loop branch's
   closing `/hex-review` (retro's commits fall inside its range) plus the
   human's PR merge. Cap: ≤ 10 proposals applied or asked per run; every
   over-cap row is still recorded under Deferred.
5. **Outputs feed existing paths.** The report
   (`.agents/retro/reports/<date>[-n].md`, `# Retro:` heading) is a valid
   `/hex-plan` path and a new `/hex-loop` source kind; project-convention
   and tuning findings become `hex.md › Memory` candidate lines that the
   existing `/hex-init` re-audit promotes with consent.
6. **Nudge.** Orchestrator handoffs end with `Retro inbox: <N> entries —
   /hex-retro` at ≥ 5 top-level entries — counted, never parsed (no
   `severity` arm: untrusted JSON). The inbox location is a link to
   `hex-retro` § Entry, the first hex-core → member link; without
   `hex-retro` installed it dangles harmlessly and no nudge prints.

### Rationale — named deviations from `hex/DESIGN.md`

| Deviation | Why | Bound |
|---|---|---|
| **"hex ships markdown, the client is the runtime"** (round 5) — first executable in the hex bundle (`hex-retro/scripts/retro.py`) | Ratified "ledger maintained mechanically"; transcript parsing and cost arithmetic are unreliable as model work | stdlib-only `python3` ≥ 3.11 (`tomllib`; `hex-loop` (o) already requires `python3`); capture needs no script; no `python3` → `Error:`+`Fix:`, nothing written. A compiled hex binary stays out of scope (discussion) |
| **Single-source contracts** — the rule echoes the required field names that `hex-retro` § Entry owns (thresholds are not mirrored: the script parses § Thresholds at runtime) | The always-on line is read by agents that never load the skill, so it must be standalone | The acceptance sweep greps the seven required names in both the rule and § Entry |
| **"hex commits only in execute/finalize"** — loop-mode retro edits are committed | Ratified loop gate: retro edits land on the loop branch like any work | `/hex-retro` itself never commits; the pasted session commits, extending `adr_0018`'s session-commit deviation by one act |
| **Ratified "small — retro edits" route, narrowed to an allow-list** — loop mode applies (small) or routes in-loop (large) only when every target path lies inside a path-sourced skill or rule source dir (`grim status` `source: path:` in the repo), checked before size; `CLAUDE.md`, `AGENTS.md`, client config dirs, `hex.md`, the goal file, plans, Taskfile/noxfile/verification scripts, CI workflows, `grimoire.toml` and every other project file are excluded | The ratified "isolation is free" holds only for installed-from-source skills: a project-context edit changes every later sub-orchestrator of the same run before review (ASI06), and a planted row targeting a verification script could no-op the gate that reviews it; a deny-list misses every file it does not name | Excluded findings become `hex.md › Memory` candidates (`/hex-init` promotes with consent) and Deferred report rows; the allow-list rides into every delegated brief |
| **Ratified inbox resolution** ("via `git rev-parse --git-common-dir`") replaced by the first `git worktree list --porcelain` entry | Inside a submodule the common dir is `.git/modules/<x>`, whose parent is not the checkout | Same survival property; bare first entry still survives worktree removal |

**Amendments in the open (not deviations):** `protocol.md`'s closed
gate-exemption list gains a fifth named member (`/hex-retro`: spawns
nothing; its gate is one question at the apply point, or in loop mode the
branch's closing `/hex-review` — its edits land before it — plus the
human merge); § Upkeep step's non-orchestrator write
carve-out gains a second named case (retro's candidate lines, modeled on
C-708); `memory.md` places `hex-retro` **outside** the federation halt
(no plan/federation state, no remote act).

**Considered and not deviated:** **rule singularity** — upheld as one
artifact, with a stated, bounded growth: capture is three lines where
round 9 says "a single concrete line per shipped mode" (one paragraph for
one mode, as the discuss paragraph already is; one line would drop the
discriminator or the plain-dir clause); **C-719** — upheld: retro runs fully without the rule
(objective channel, seed import, whatever entries exist); **heartbeat
out-of-tree rule** (`protocol.md` § Worker liveness) — not contradicted:
the heartbeat dir is a *control surface* whose fields are interpolated into
re-spawn prompts; the inbox is *data* that only ever becomes a gated
proposal, echoed per § Untrusted-text echoes; tracked (planted) inbox
files and symlinks are skipped; **capability classes** — no literal model
or harness tool name in prose; client tool names appear only as parsed
data constants inside `retro.py`; **thin SKILL.md** — report template in
`assets/`, bookkeeping in the script.

### Consequences

**Positive:** every friction source lands in one ledger with objective
cost; recurring costs (days of acceptance runs) become visible; loops
improve their own harness between cycles; findings route to their owner.

**Negative:** +968 B always-on (lines + keywords) in every session on
rule-capable clients; a Python ≥ 3.11 dependency for consolidation; the
miner tracks an undocumented, changing transcript format; one retro run
per checkout at a time (no lock).

**Risks:** planted ledger rows steer loop-mode edits → bounded by the
path-sourced allow-list (no project file, verification script or CI
workflow is edited unasked), forged trajectory cost ignored, retro
commits landing before the closing `/hex-review`, and the human PR merge.
Transcript drift → shape guard + `Degraded:`, plus an acceptance run on
real transcripts. "Big value" drifts a goal into harness work → scope
condition, recorded reason, I8 cap.

## Non-Functional Requirements

| Axis | Impact |
|---|---|
| Scalability | One file per entry/finding; fold is O(entries); `mine` re-reads only transcript files whose mtime changed. `consumed/` grows unbounded (gitignored) |
| Availability | Capture never blocks (no lock); miner/fold degrade, never fatal on bad entries |
| Latency | Rule adds ~240 tokens always-on; `hex-loop` paste +154 chars (retro goal: 3,176 → 3,330 / 4,000) |
| Security | Entries untrusted data; miner copies no arguments beyond program + a lowercase `^[a-z][a-z-]{0,15}$` subcommand, no tool output; no secrets in entries; fold accepts bare basenames only; symlinks refused below the checkout root; loop edits allow-listed to path-sourced skill/rule dirs |
| Cost | No model calls in capture/mine/fold; judgment only in the retro run |
| Operability | `retro.py selftest`; ledger diffs reviewable per finding |

## Rollout / Migration

1. Ship rule lines, skill, script, hex-init item, hex-loop row and I8
   sentence, DESIGN round 24 (including the first hex-core → member link
   and its degradation), CHANGELOG, README, `.gitignore`; then `grim lock`
   and `grim install` (the changed `grimoire.toml` invalidates the lock's
   declaration hash).
2. **Seed:** `/hex-retro --import .agents/handover_dogfood_findings.md`
   converts F-001..F-012 into `source: seed` inbox entries; the first run is
   the acceptance test (all twelve covered with edit + rationale + owning
   artifact, ≥ 1 prune considered, ledger rows written, real-transcript
   `mine` entries folded in the same run); a throwaway `--loop` probe
   shows the allow-list routing (`applied` for a path-sourced skill,
   `candidate` for `CLAUDE.md`); the executing WP then `git rm`s the
   handwritten file.
3. **Consumers without `python3` ≥ 3.11:** capture still works;
   `/hex-retro` refuses with `Error:`+`Fix:`. **Without `hex-retro`
   installed:** capture still works; no nudge prints. **Without rule support** (Codex, Gemini,
   Zed, Amp): no self-reports (accepted gap); objective channel only where
   Claude Code transcripts exist.
4. **Hooks follow-up:** once grim's hook artifact kind ships (branch
   `hex/hooks-artifact-kind`, undated), a new plan replaces `mine` with
   tool-failure / subagent-stop / duration hooks writing trajectory entries
   through the same recipe; the rule stays.

## Compliance

`grim build` for `hex/hex-retro`, `hex/hex-state.md` and every changed hex
skill; `task publish -- --dry-run`; `python3 hex/hex-retro/scripts/retro.py
selftest`; the seed acceptance run; the one-off probes (16 parallel
writers, worktree survival, real-transcript `mine`, `--loop` routing).

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-09-23 | /hex-plan architect | Initial draft (Proposed) |
| 2026-09-23 | /hex-plan review-fix | Allow-list replaces deny-list; three-line capture; checkpoint before the closing review; thresholds parsed at runtime; count-only nudge; Python 3.11; options B4, C1–C3 added (Proposed) |
