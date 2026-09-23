# Research: friction capture + retro skill — existing mechanisms and constraints

## Metadata

**Date:** 2026-09-23
**Domain:** cli (hex skill bundle architecture, subagent protocol)
**Triggered by:** proposed feature — subagents record "friction" as structured
entries during skill use; a new `retro` skill later summarizes them into
proposed skill/config improvements
**Expires:** 2026-12 (re-verify against `hex/DESIGN.md` and `protocol.md`
after any further ADR touches Worker coordination, Upkeep, or `hex.md`
Memory)

## Direct Answer

A working, git-untracked instance of this exact feature already exists:
`.agents/handover_dogfood_findings.md` — a manually-maintained, append-only,
numbered (`F-001`…`F-012`) friction log — and its own `F-004` entry *proposes
a `/hex-retro` skill* in language close to this task's spec. A `hex-discuss`
artifact at `.agents/discussions/retro.md` is `State: active` and
git-untracked right now, on this exact topic — per `.claude/rules/hex-state.md`
this session must not make code/config edits and must re-read that artifact
before acting (this task is read-only recon, so it is not itself blocked, but
whoever picks up design work next is). hex has three existing "learn and
route" mechanisms (Upkeep step, `hex.md › Memory`, hex-init audit/promotion)
that already cover the "improvement gets proposed back to config" half of
this feature; none of them capture *in-flight friction during a run* — they
run at end-of-run or at `/hex-init` re-audit. The nearest concurrency
precedent for structured per-agent writes is the heartbeat file contract
(one file per agent, temp-then-rename, exactly-one-writer) — not a shared
append-only log. Attribution to an installed artifact + version is
mechanically available via `grim status --format json` (`pinned` digest or
local `hash`) but nothing in hex reads it today. Any capture mechanism must
clear the multi-client reach bar `hex-state.md`/`reach.md` document: several
clients hex ships to have no rule surface and no hook surface at all.

## Key findings

1. **Existing "learn and route" mechanisms, and how they'd overlap.**
   - Upkeep step (`hex/hex-core/references/protocol.md:840-862`): every
     orchestrator's final phase updates `hex.md › Memory` with "learned
     facts," and explicitly enumerates **three candidate classes** a run
     should record for later promotion: a perspective that should become
     an always-on hint, a `review.<level>.*` tuning value, and "a finding
     class that recurred across seats or runs and belongs in the project's
     own rules as a checklist item" (`protocol.md:855-862`). This third
     class is near-identical in intent to "friction the retro summarizes
     into a config change" — but it fires once, at end-of-run, from the
     orchestrator's own synthesis of worker returns, not as a structured
     per-worker entry written mid-run.
   - `hex.md › Memory` / `› Preferences` (`hex/hex-core/references/memory.md:179-199,
     271-299`): `Memory` is skill-owned working memory (active plan
     pointer, artifact index, learned facts); `Preferences` is user-owned,
     **only** `/hex-init` writes it, with consent
     (`memory.md:189,257-263`). A friction log that wants to *propose* a
     preference change must route through this same user-consent gate —
     it cannot write `Preferences` directly, on pain of violating the
     ownership rule the whole file design rests on.
   - hex-init re-audit / promotion (`hex/hex-init/references/audit.md:269-287`,
     "Review settings tuned?"): explicitly reads `hex.md › Memory` for "a
     budget expiry, a residue line, a round count, or a finding class that
     recurred" and proposes it as a `review.<level>.*` key or checklist
     item, folded into a single consent-gated diff. This is the existing
     **destination** a friction-derived improvement would need to reach —
     a retro skill's output plausibly writes into `hex.md › Memory` as
     promotion candidates, for `/hex-init` to pick up next run, exactly
     the same lane `Upkeep step`'s class 3 already uses.
   - "Retro"/"lessons"/"friction"/"dogfood" as explicit concepts: **no
     hits inside `hex/`** (protocol.md, workers.md, memory.md, archive.md,
     config.md, checklist.md — none of the words appear). They exist only
     in the two untracked files found in this repo's working tree:
     `.agents/handover_dogfood_findings.md` (a hand-authored friction log,
     12 entries) and `.agents/discussions/retro.md` (a `hex-discuss`
     artifact, `State: active`, 111 bytes — a stub, not yet elaborated).
   - **Overlap verdict:** a structured friction-entry mechanism duplicates
     the Upkeep step's class-3 candidate unless it is explicitly scoped as
     that class's *feeder* (per-worker raw signal → orchestrator synthesis
     → Memory candidate → hex-init promotion), rather than a parallel path
     that also writes `hex.md` or proposes config changes directly.

2. **Universal worker protocol — where a "record friction" duty could
   attach, and the budget pressure against it.**
   - `hex/hex-core/references/workers.md:21-91` lists 11 numbered rules
     every worker follows, copied into **every spawn prompt** (`workers.md:5-9`:
     "Workers are prompt blocks... the orchestrator copies a role's
     spawn-prompt template into a subagent it launches"). A one-line
     addition here is paid by every single worker spawn across every tier
     — the highest-leverage, also highest-cost, attachment point. Rule 4
     already covers the adjacent case ("Report deferred findings instead
     of oscillating... stop and report it deferred with the specific
     question") and rule 6 ("Return a structured result... so the
     orchestrator can synthesize across workers without re-reading your
     work") is the existing channel a friction field could ride on — i.e.
     extending the **output contract**, not adding a new write, costs
     nothing extra to load (it's prose already read) but does cost
     synthesis-time attention from the orchestrator on every return.
   - `adr_0014_instruction_diet.md` (`.agents/adrs/adr_0014_instruction_diet.md:24-60`)
     is a live, `Proposed` ADR whose entire premise is that
     `protocol.md`'s 123–149 KB is 43–54% of every mode's loaded
     instruction bytes, that "the unit of reading is the file," and that
     two worker personas (`builder`, `reviewer`) each pay the full file
     for a rule of a few KB. The companion plan
     (`.agents/plans/plan_adr_0014_instruction_diet.md`) is `State:
     executing` at time of writing (Status block: `Next: /hex-execute ...
     "WP 7 — C-975 remedy"`) — i.e. the split is **in flight right now**.
     Any friction-capture addition to `workers.md`'s universal protocol
     lands in the file this ADR does *not* touch (workers.md is separate
     from protocol.md and already applies "Load only what runs" — see
     `workers.md:9-14`), but the same cost logic applies: `workers.md`'s
     universal-protocol section is read by literally every spawn
     regardless of role, so it is exactly the section adr_0014's
     reasoning would flag if it grew.
   - **Budget-pressure numbers**: `protocol.md` alone measured
     123,031–149,072 bytes / 18-19 `##` sections
     (`adr_0014_instruction_diet.md:24-30`); `workers.md`'s universal
     protocol is currently ~70 lines (`workers.md:21-91`) — small in
     absolute terms, but its marginal cost is per-spawn, not per-mode, so
     it multiplies by spawn count (up to 8 concurrent, uncapped over a
     run's lifetime) rather than by the ~5 modes protocol.md multiplies
     by.

3. **Worktrees — path resolution and survival across worktree removal.**
   - Workers run in `.agents/worktrees/<wp-slug>/`
     (`hex/hex-core/references/worktree.md:16-24`), one ephemeral branch +
     worktree per WP, **deleted after merge**
     (`worktree.md:143-152`: "Delete the ephemeral branch and remove the
     worktree after its WP merges... Teardown is the *top* orchestrator's").
   - `hex.md` resolution is **upward filesystem search from cwd**
     (`hex/hex-core/references/memory.md:11-14`), so a worker running
     inside `.agents/worktrees/<wp>/` resolves the *worktree's own*
     `.agents/memory/hex.md` if the worktree checkout contains one at that
     relative path — since a git worktree shares the repository's tracked
     files at its checked-out ref, `.agents/memory/hex.md` (if committed)
     is present and resolves *inside* the worktree, not by crossing into
     the main checkout. This means **a write to a relative path from
     inside a worktree writes into the worktree's own working copy**, not
     the main checkout — and per worktree.md, that copy is deleted at
     teardown. A write there would **not survive worktree removal** unless
     committed on the WP's ephemeral branch (which itself is deleted post-merge,
     `worktree.md:143`) or merged onto the feature branch before teardown.
   - **No existing pattern for "write to the main checkout from a
     worktree"** was found in `worktree.md`, `protocol.md`, or
     `workers/coordinator.md`. The closest analogue is the back-pointer
     write in federation (`memory.md:37-55`): `/hex-execute` writes a
     bullet into a **satellite's own main checkout working tree**, "left
     uncommitted — memory resolution reads the filesystem, not git, so the
     guard is live the instant the file is written" — but that is a
     cross-*repo* write via `git -C <path>` from the orchestrator (which
     never itself runs inside a worktree), not a worker-inside-worktree
     writing back to its own repo's main checkout. No hex file addresses
     a worker (running with cwd inside `.agents/worktrees/<wp>/`) writing
     to `../../` (the main checkout) at all.
   - `.agents/handover_dogfood_findings.md:129-153` (finding F-005) is
     direct, lived evidence of this exact class of problem: "gate evidence
     has no agreed home: the scratchpad is private, `/tmp` is volatile."
     Quote: "An agent's session scratchpad is real storage that survives,
     and **no other agent can find it**... the obvious shared alternative,
     bare `/tmp`, is wiped hourly." F-005's fix was "a run-scoped directory
     **inside the repository** (`.tmp/<wp>/`)" — i.e. the project already
     converged, empirically, on "inside the repo, not the worktree, not
     /tmp" for supervisor-visible evidence, which is the same shape a
     friction log's capture location would need.

4. **Concurrency precedents — append-only vs. one-file-per-entry vs. lock.**
   - **Strongest precedent, one-file-per-agent, no lock**: the heartbeat
     contract (`protocol.md:475-553`, "Worker liveness"). One flat
     directory per run, **one JSON file per live agent**
     (`${XDG_CACHE_HOME}/hex/<run-id>/hb/<agent-id>.json`), written
     **temp-then-rename** (`protocol.md:540-543`), and "**Exactly one
     writer, always — the agent the filename names.** No parent, no
     sibling and no sweep ever writes into another agent's beat file."
     This sidesteps concurrent-write races entirely by construction
     (partition by agent id) rather than by locking a shared file — the
     closest hex has to "one file per entry," and it explicitly rejects a
     shared file for exactly the reason a friction log would hit it
     (races between concurrent workers).
   - **Append-only precedent, but single-writer-at-a-time by protocol
     position, not by lock**: the plan's `## Spec Deltas` block
     (`hex/hex-core/references/archive.md:25-29`: "append-only, same
     discipline as the convergence rows") and the fold receipt
     (`archive.md:416-428`: "every touched ID to the plan's `## Spec
     Deltas` block — append-only, same discipline as the convergence
     rows"). Both are written by a **single orchestrator-owned phase**
     (Review-Fix Loop convergence checks, hex-review's Fold-Back phase) —
     never by concurrently-running workers — so "append-only" here means
     "never rewritten," not "safe under N concurrent writers." No flock,
     no CAS, no file lock anywhere in `hex/hex-core/references/` (grep for
     `flock`/`lock directory` returns zero hits inside hex-core reference
     files — the only "lock" concept in the bundle is the worker-side
     heavy-command semaphore in `resources.md`, unrelated to file state).
   - **Real-world evidence against a naive shared file, from actual
     dogfooding**: `.agents/handover_dogfood_findings.md:14-60` (finding
     F-001) is a live incident of a **`flock`-based mutex deadlocking**
     because a spawned daemon (`sccache`) inherited the lock fd across a
     subshell boundary and never released it — "the next run blocks on
     `flock` forever." This is direct evidence *against* reaching for
     `flock` casually for a friction-log writer that might be invoked from
     inside build/verification subshells or heavy commands.
   - **`.agents/handover_dogfood_findings.md` itself** is a real,
     currently-in-use precedent for the append-only option: "Entries are
     appended, never rewritten — a finding that later proves wrong gets a
     follow-up entry saying so" (line ~9), numbered `F-001`…`F-012`,
     single markdown file, hand-maintained (not concurrent — one human/
     agent edits it at a time today). It has not been stress-tested under
     N-concurrent-worker writes; its current write pattern is serial
     (one supervisor appending after the fact).
   - No JSONL precedent exists **inside the hex bundle's own on-disk
     state**, but one exists in the **harness layer**: `~/.claude/settings.json`'s
     `PreToolUse` hook on matcher `Task|Agent` appends one JSON line per
     subagent spawn to `.claude/state/subagents.jsonl` via `jq -c ... >>
     "$d/subagents.jsonl"` (from the global `CLAUDE.md`'s Model Routing
     section, and confirmed live in `~/.claude/settings.json`). This is a
     **hook-authored**, not agent-authored, append-only JSONL log, using
     plain shell `>>` redirection (no flock) — i.e. the one append-only
     JSONL precedent available in this environment relies on hook
     atomicity assumptions (POSIX `O_APPEND` write, single small `jq -c`
     line) rather than an explicit lock, and it is client-specific
     (Claude Code hooks), not portable.

5. **Attribution to installed artifact + version.**
   - `grimoire.lock` (repo root) records, per skill: for registry-sourced
     skills, a content-addressed `pinned =
     "ghcr.io/.../<skill>@sha256:..."` digest plus `bundle`/`bundle_tag`;
     for path-sourced (local dev) skills — which is how every `hex-*`
     skill is declared in *this* repo — a `hash = "sha256:..."` of the
     source tree instead of a registry digest. Both forms are precise,
     content-addressed identifiers a friction entry could cite.
   - `grim status --format json` (confirmed by direct invocation) returns
     per-artifact `outputs[].path` — the exact materialized install path
     per client (e.g. `/home/mherwig/dev/arcana/.claude/skills/hex-core`)
     — alongside `state`, `deprecated`, `replaced_by`, `update_available`.
     This is enough to answer "which artifact+version caused this" purely
     by cross-referencing the friction entry's cwd/skill name against this
     JSON, with **no new metadata plumbing needed** — the data already
     exists, hex just doesn't read it anywhere today (zero references to
     `grim status` or `grimoire.lock` inside `hex/hex-core/references/`).
   - **Local edits are overwritten**: `plan_adr_0014_instruction_diet.md`'s
     Out of Scope section states plainly: "`.claude/skills/`. A
     `grim`-installed mirror, regenerated on install, never hand-edited."
     — confirming that any artifact under `.claude/skills/` is
     install-managed and a local edit there is not durable; the source of
     truth is the `hex/<skill>/` tree (or, for a consumer project, the
     registry-pinned artifact), never the installed mirror. A friction
     entry attributing a defect to "the skill at path X" must cite the
     **source** path/hash (`hex/<skill>/` + `grimoire.lock` hash), not the
     installed `.claude/skills/` mirror, to survive a `grim update`.

6. **Multi-client constraints (capability classes, hardening-never-
   precondition, portability).**
   - `hex/DESIGN.md:649-661`: the bundle's one shipped rule artifact
     (`hex-state.md`) is deliberately kept **singular** — "the one
     bundle-generic `hex-state` rule carries a single concrete line per
     shipped mode... the always-on cost stays one artifact and grows by
     single lines, never by artifacts" — and is governed by `adr_0008`
     C-719: "the rule is **strictly a hardening** and no hex file may make
     its presence a condition of any behavior... a client without a rule
     surface loses persistence convenience and never capability." A
     friction-capture rule (if it needed an always-on surface) would have
     to be additive to this *same* singular file, never a new one, and
     must not be load-bearing — any client lacking it must still work,
     just without the "reminder" convenience.
   - `hex/hex-discuss/references/reach.md:9-17`: the concrete reach table
     for that one rule — **Native** on Claude Code, Cursor, Kiro;
     **Degraded** on OpenCode (frontmatter stripped, registered as a
     "managed always-on glob") and Junie (project scope only); **Absent**
     on Codex, Gemini, Zed, Amp ("no ownable on-disk rule path"). Any
     friction-capture mechanism that leans on an always-on rule surface
     inherits this exact matrix — roughly half the clients hex ships to
     have no rule surface at all.
   - Protocol-level pattern for a similarly harness-dependent feature: the
     heartbeat/liveness ladder gates every mechanism on **capability
     classes**, never primitive names, and prints a `Degraded: ...` line
     per absent capability (`protocol.md:390-441,712-737`) — e.g.
     "Degraded: no agent messaging," "Degraded: single session model — no
     per-spawn override." This is the house style any friction-capture
     design would be expected to follow: define the capability class
     needed (e.g. "structured worker-return channel" — already universal,
     see finding 2 — versus "background hook capability" — Claude-Code
     only), and degrade-announce rather than hard-require it.

7. **Claude Code hooks — precedent and scope.**
   - **No hooks live inside the arcana repo itself** — `find` for
     `settings*.json` under the repo root turns up only `.vscode/settings.json`
     and files under `.tmp/dogfood/` (a scratch mirror of a *different*
     project, `ocx-sion`, not part of this repo's shipped config). hex
     ships no `.claude/settings.json` hook of its own; `hex/DESIGN.md`'s
     portability stance (finding 6) is consistent with this — a
     Claude-Code-only hook would not satisfy the bundle's cross-client
     goal.
   - `~/.claude/settings.json` (this user's global config, outside the
     repo) **does** carry a live precedent: a `PreToolUse` hook matching
     `Task|Agent` that appends one JSON line per subagent spawn to
     `.claude/state/subagents.jsonl`, including a `reason` field extracted
     from the spawn prompt via a `model\s*rationale:` regex capture. This
     is evidence that (a) hook-based structured capture at spawn time
     works today in this exact environment, (b) it is user/global-config
     owned, not shipped by hex, and (c) it already demonstrates the
     "extract a structured field out of free-text prompt via regex, write
     one JSON line per event, append with `>>`" shape a friction-capture
     hook could reuse — but it is a `SubagentStart`-equivalent capture
     (spawn-time), not a `SubagentStop`/`PostToolUse` capture of an
     in-flight friction report, and no `SubagentStop` or friction-specific
     hook exists anywhere in scope.

## negative:

- No `flock`, file-lock, or CAS-based write mechanism exists anywhere in
  `hex/hex-core/references/` — searching for it returns zero hits.
  Anything written up citing an in-bundle "lock precedent" for concurrent
  writes would be citing something that isn't there; the real precedent
  (heartbeat) avoids the need for a lock entirely via one-file-per-writer.
- The heartbeat file's atomic temp-then-rename pattern is **not** an
  append-only-log pattern — it replaces the whole small JSON object each
  beat. It is cited above as the nearest concurrency precedent, but it
  answers "how do N agents each safely write their own state" not "how do
  N agents safely append to one shared log," which is the harder version
  of the friction-capture question if entries are meant to interleave in
  one file.
- `.agents/discussions/retro.md` is a 111-byte stub (title + `State:
  active` line only) — it does not yet contain design content to mine;
  it signals an in-flight session claim on this exact topic, not
  additional evidence.
- `adr_0014`'s instruction-diet numbers are about `protocol.md`
  specifically, which a friction-capture addition to `workers.md` would
  *not* directly add to — citing adr_0014's byte figures as if they
  applied to `workers.md` would overstate the cost; `workers.md`'s own
  size was not separately measured in this pass.
- `grim status`/`grimoire.lock` attribution capability is unused by hex
  today — this is a capability gap being reported as "available if
  wired up," not an existing mechanism already in play. Treating it as
  "hex already attributes friction to artifact versions" would be wrong.

## leads:

- **archive.md destination-resolution / containment rules** (path
  conditions: no symlink, no directory, already-exists / git-tracked
  conditions) — worth a follow-up pass if a friction log's destination
  path needs the same safety envelope the spec-fold and discussion-home
  writes already use (`archive.md:92` onward, referenced from
  `hex-init/references/audit.md:134-144`).
- **`hex-discuss`'s post-gate hand-off record (C-708)** — the one
  non-orchestrator memory write hex already permits outside the halt/
  ownership rules (`protocol.md:864-867`, `memory.md:290-299`) — is the
  closest existing "a non-orchestrator skill is allowed to write
  something to memory" precedent; a `retro` skill's write path into
  `hex.md › Memory` should probably be modeled on this exact carve-out
  rather than invented fresh.
- **`resources.md` § 3 heavy semaphore** — not read in this pass; if a
  friction-log writer is ever invoked from inside a heavy/verification
  subshell (the F-001 `flock`+`sccache` deadlock scenario), its
  interaction with the heavy-command containment ladder is worth
  checking before picking a write mechanism.
- **`workers/coordinator.md`** — not read in this pass; since a
  coordinator is the one worker persona that itself spawns leaves and
  commits, it is the natural place to check whether "record friction"
  would need a *second* duty (one for leaves reporting up, one for the
  coordinator relaying/aggregating) rather than one universal-protocol
  line.
- **`hex-loop`'s goal-file convention** (`hex.md › Pointers` "Goals:"
  row, `/hex-loop` writes one goal file per run,
  `hex-init/references/audit.md:146-170`) — a close structural analogue
  to "one retro output per run": worth comparing its "written only by
  the one skill that owns it, read-only elsewhere" shape against
  whatever write pattern `retro` ends up with.
