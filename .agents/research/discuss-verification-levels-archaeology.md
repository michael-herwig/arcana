# Research: hex verification cadence — repo archaeology

## Metadata

Date: 2026-09-24
Lane: repo archaeology
Discussion: .agents/discussions/verification-levels.md

## Direct answer

"Verify after every merge" became "scoped check after every merge" in one
squash-merged plan, `adr_0010` (execution performance), commit
[`bd5ca8514f1401e5d5365819a73ac318d8560fe7`](../../adrs/adr_0010_execution_performance.md)
(2026-08-31, shipped hex 0.2.0). It replaced full-suite-per-merge with a
scoped check (the WP's own contract tests + cheapest build gate) plus full
verification at coordinator joins, an `M=3`/level-clear/high-risk-diff
checkpoint, and the mandatory final gate. Since then hex has only ever
*narrowed further* (adr_0012's per-WP effective tier, 2026-09-05/06) or
*reverted a sibling mechanism* (adr_0015 superseded adr_0012's review-budget
half the same release) — nothing has widened verification scope beyond
scoped/full, and no diff-content/path-class skip, docs-only exemption, or
verified-tree memoization has ever shipped. Both are on record as explicitly
considered and declined, with reasons, inside `adr_0010` and `adr_0012`.

## Key findings

1. **The scoped-check design landed whole, not incrementally.** Commit
   `bd5ca85` (2026-08-31) added `adr_0010_execution_performance.md` (1161
   lines), the originating discussion
   [`hex-execution-performance.md`](../../discussions/hex-execution-performance.md),
   its plan, 13 research artifacts, and a `DESIGN.md` round-12 amendment, all
   in one commit — this was an already-executed, already-reviewed plan being
   committed as a unit (per the commit message: "Executed plan (done, 7/7
   WPs, three review rounds to Approve)").

2. **Five decisions were ratified in the discussion before the ADR was even
   drafted** (`hex-execution-performance.md` § Decisions, 2026-08-30): scoped
   check per merge; full verify at joins/checkpoints/final gate; WP's own
   contract tests + build as the scoped-check default, with a
   project-documented selective-test command as escape hatch; delta-scoped
   review rounds; depth-1 nesting only; fail-fast cascade. The ADR explicitly
   states these five are "treated as constraint, not as positions to
   re-litigate" (`adr_0010_execution_performance.md:64`).

3. **Five options were scored on Axis 1 (per-merge verification policy)** —
   `adr_0010_execution_performance.md:270-350`:
   - A1 status quo (full verify every merge) — scored *highest* (102 pts) but
     rejected anyway: "A1 is the option the owner filed the complaint about,
     and 'change nothing' is not an available answer" (line ~292).
   - **A2 scoped + dual-trigger checkpoints + full at joins/final** —
     ratified, 100 pts.
   - A3 scoped + backstop only at final gate (no checkpoints) — rejected, 81
     pts: "the premortem seat's named failure mode made policy: a single gate
     thirty merges late... no example of a production system that does
     selection with only a terminal backstop" (adr0010-operability.md
     survey, cited line ~314).
   - A4 keep full verify per merge but pipeline/overlap it — rejected by a
     6-point margin the ADR calls "inside the noise of any weighting anyone
     could defend"; loses on operability (a failure would attribute to a
     tree that no longer exists, concurrency story for merge-conflict
     playbook) — but is explicitly **left available**, not killed: "the right
     next move if scoped checks land and cross-repo merge wall-clock still
     dominates" (line ~339).
   - **A5 content-addressed incremental verification (Buck2/`go test`-style
     caching)** — rejected as a *default* (needs project tooling hex cannot
     supply — Maven/Cargo/pytest don't have it) but **survives as the escape
     hatch inside A2**, contract C-906: a project with such a runner points
     hex at it.

4. **Two limitations were deferred on the record, not fixed** (D-1/D-2,
   `adr_0010_execution_performance.md:600-611`):
   - D-1: delta-scoped review is "a wash at R=1, a net loss of one delta read
     at R=2" — the mandatory full converged pass eats the saving inside a
     single loop; the real lever is cross-invocation `/hex-review`, not the
     loop.
   - D-2: the scoped check does not run a merged WP's *dependents'* contract
     tests, so a dependent broken by this merge can go undetected "until the
     next checkpoint or the final gate." An open question explicitly asked
     "should a scoped check also run the merged WP's dependents' contract
     tests?" and the recommendation was **no for v1** — "at merge time a WP's
     dependents are usually unbuilt... running their suites on every merge
     walks back toward the full suite this ADR is removing" (Open Questions,
     line ~1108). Declined on cost, explicitly not on coverage, and an
     earlier draft's wrong justification (claiming the last checkpoint
     already covered it) is called out and corrected in the same paragraph.
   - A third open question asked whether checkpoint cadence `M` should be
     project-tunable — **no**: "`M=3` ships as text with no knob... a tunable
     M is the seventh `config.md` key `adr_0003` C-223 froze the vocabulary
     to prevent" (line ~1122).

5. **`adr_0012` (per-WP effective tier, 2026-09-05, Status: Proposed in the
   file but shipped in hex 0.4.1 per `CHANGELOG.md:54`) is the one later
   attempt at a graded/derived level beyond scoped/full — but it governs
   review breadth, phases and model class, not the `Verify` column itself**
   (except that its `door` flag reuses `Verify: full` as an input, never the
   other direction). Its risk-flag model (`sec`, `hot`, `hub`, `door`, all
   fail-closed except `door`) is exactly the "graded levels" idea, considered
   as five options (`adr_0012_per_wp_effective_tier.md:390`+):
   - O5, a **continuous risk score**, was explicitly rejected:
     "`adr0012-risk-scoring.md`: no numeric threshold available for
     churn/entropy/ownership/fan-in cutoffs in the surveyed literature...
     hex should implement them as boolean escalation flags... A percentile
     against repo history is a computation hex has nowhere to run at plan
     time and nowhere to store — driver 7 forbids the cache and `config.md`
     forbids the key." Also: "a score is not auditable in a sentence."
   - O1 (chosen): boolean flags, fail-closed, pure function, no
     config key, never authored above the ceiling.

6. **The `hub` flag/high-risk trigger is a documented, acknowledged
   degenerate case, not a bug** — `hex/hex-core/references/verify.md:210-240`
   (added in `adr_0010`'s split of `protocol.md`, commit `b5ecfe28...` for
   the effective-tier layer): clause 2 of the high-risk checkpoint predicate
   fires when a `(Repo, path)` pair appears in more than one WP's `Expected
   Files` — "a file two WPs touch across levels is a hub." The file states
   outright: **"if every merge fires a trigger, the run performs exactly
   today's behaviour — correct, merely not faster."** This is precisely what
   the current retro entry (`.agents/retro/inbox/20260924T061049Z-1e78816e.json`)
   flags as friction: "the hub-file high-risk checkpoint fires on every merge
   when WPs share taskfiles/scripts."

7. **`adr_0015` (review by join level, commit `ad41ca610e...`, 2026-09-06,
   same 0.4.1 release as `adr_0012`) supersedes half of `adr_0012` almost
   immediately** — its own Metadata states "Supersedes: the review-budget
   half of `adr_0012` (C-947 backstop...)". `hex/CHANGELOG.md:92-94`
   (`[0.4.1]` › Removed) confirms: the per-WP `self|light|panel` review
   budget, its `panel` escape hatch, the branch-review precondition, the
   three-scope review-diversity model, and every per-tier round cap were all
   removed in the same version they were added, replaced by join-level
   review (L0/L1/L2/L3). This is the one clear "shipped then reverted"
   mechanic in the family — but it is the *review-breadth* budget, not the
   *verification* (`Verify: scoped|full`) column, which `adr_0015` leaves
   untouched.

8. **No retro-ledger or CHANGELOG entry before 2026-09-24 names verification
   cost/cadence as friction.** The only retro entry on this topic is today's:
   `.agents/retro/inbox/20260924T061049Z-1e78816e.json` (kind: slow, scope:
   harness, artifact: hex-core, severity: high), proposing (a) a
   non-behavioural-path skip keyed off a `hex.md › Pointers` glob list, (b)
   forbidding reviewer seats from re-running the suite, (c) capping the
   hub-file high-risk trigger. This entry has not yet been triaged by
   `/hex-retro` into a ledger finding as of this research.

## Negative (dead ends, contradicting evidence)

- **No diff-class/path-based skip (e.g. "docs-only changes skip
  verification") has ever been proposed or shipped anywhere in the ADR/plan
  history.** `decompose.md`'s review-breadth heuristic mentions "docs-only or
  tiny low-risk work" as a `self`-review trigger (quoted at
  `adr_0012_per_wp_effective_tier.md:73`), but this governs **review
  breadth**, never verification — the recon lane's finding that "diff
  path/content class drives review depth, never verification" is confirmed
  by direct reading, not just by the recon artifact's own claim.
- **No verified-tree memoization / content-hash caching of verification
  results was ever designed as a hex-owned mechanism.** A5 (content-addressed
  incremental verification) was considered and explicitly kept out of hex's
  own responsibility — it survives only as an *escape hatch* pointing at a
  project's own caching test runner (C-906), never as a hex cache. The
  recon artifact's "one narrow `/hex-finalize` exception" was not
  independently re-verified in this pass (out of scope for the ADR/plan
  corpus searched) but no contradicting evidence was found either.
- **`M=3` tunability was raised and declined twice in substance** — once in
  `adr_0010`'s open questions ("should M be project-tunable? No), and the
  reasoning is not repeated or revisited in `adr_0012` or later; no
  discussion has reopened it since.
- **adr_0012's own Status field still reads "Proposed"** in the file despite
  `CHANGELOG.md` showing its features shipped in 0.4.1 and its Superseded-By
  field reading "N/A" despite `adr_0015` stating it supersedes half of it —
  a metadata inconsistency in the ADRs themselves, not a design finding, but
  worth flagging if this discussion cites adr_0012's status.

## Leads

- retro-ledger triage — the 2026-09-24 inbox entry is un-triaged; running
  `/hex-retro` on it (or reading it directly) is the fastest way to see if
  Michael has already reacted to today's exact friction.
- adr_0013 (runtime contracts) / plan_wave0_quick_wins — RCA
  (`rca-review-fix-loop-wall-clock.md`) attributed root causes 4-6 (worker
  liveness, missing adversary deadline, single-threaded sub-orchestration,
  unscoped Implement/loop-exit gates) to these, not to adr_0010/0012 — worth
  checking if any of those touch verification gating specifically.
- `resources.md` § 3 heavy semaphore — checkpoints "take a heavy slot
  wherever the project's gate is classed heavy" (verify.md:159); the
  semaphore's own history (one-heavy-at-a-time) traces to `adr_0004` C-306,
  referenced but not fully re-derived in this pass.
