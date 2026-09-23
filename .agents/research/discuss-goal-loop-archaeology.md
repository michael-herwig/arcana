# Research: past autonomous run archaeology

## Metadata

**Date:** 2026-09-22
**Domain:** devops
**Triggered by:** hex-discuss session on a `/goal` meta-orchestrator skill — repo
archaeology of past hand-written autonomous loop runs (examples in
`.tmp/examples/loops/*.md`) across ocx, ocx-mirror, ocx-contrib, arcana
**Expires:** 2027-03-22

## Direct Answer

Failure modes cluster around three mechanisms, all with concrete repro
evidence: (1) session-limit kills that leave state files silently stale, (2)
shared-mutable-state races between parallel cargo/docker sub-orchestrators
(target dirs, /tmp scratch, container bind-mounts), (3) CI "green" that isn't
— skipped matrix jobs or gameable probes concluding `success`. Every one of
these has a guard already built and used somewhere in this repo set (stall
watchdog, per-agent `CARGO_TARGET_DIR`, durable scratch path, per-job CI JSON
inspection). Deferral-to-GitHub-issue is demonstrably useful, not a dumping
ground: issues opened by review rounds get fixed fast (ocx#466, closed same
day) or get revisited and pruned in place (ocx#311). No run in this set was
caught explicitly claiming "done" over a red pipeline; the closest is a
matrix-skip false-green the *next* run's guard caught on its own.

## Q1 — stuck, drifted, cut scope, over-looped, lost state, left mess

**Already known, not re-derived** (per instructions): arcana sub-orchestrator
background-spawn deadlock (~2h lost) and a 5-round review blowup (~6h) — see
`.agents/research/discuss-goal-loop-recon.md`.

- **Session-limit kill, silent.** `~/.claude/projects/-home-mherwig-dev-ocx-contrib/memory/overnight-run-2026-08-04.md`:
  the 2026-08-04 overnight run left **14 of 63** packages as "session-limit
  survivors" — workers killed mid-job with no error surfaced, just a state
  file that stopped updating. `ocx-contrib/.claude/state/run-2026-08-04/followup-a-watch.py`
  was written specifically because "axodotdev's predecessor died that way":
  poll every 600s, flag `STALL` at 45 min of silence on an `in_progress`/`pending`
  status. This is the concrete implementation of the example prompts' "pull
  any subagent that goes idle without reporting" clause.
- **Session scratchpad wiped mid-run, twice.** `~/.claude/projects/-home-mherwig-dev-ocx-mirror/memory/session-scratchpad-can-vanish-midrun.md`
  (2026-08-14): the whole `/tmp/claude-<uid>/.../scratchpad` tree was emptied
  mid-session, destroying a 25-minute background job's log *and* its live
  CWD — an already-open fd kept writing, but any *new* file failed `ENOENT`,
  so the job looked healthy and was silently doomed ("worse than crashing").
  Root cause: parallel `cargo build --release` from other agents filled the
  16G tmpfs. Repeated 2026-09-16 (`ocx-contrib-fleet-roll-2026-09-16.md`):
  "the session scratchpad vanished mid-finalize and took the commit-message
  files with it."
- **Shared build-cache races (false green / phantom red).** `~/.claude/projects/-home-mherwig-dev-ocx-mirror/memory/mutation-copy-needs-renamed-package.md`
  and `mutation-copy-shared-target-false-green.md` (2026-08-14): parallel
  agents sharing `CARGO_TARGET_DIR` resolved to the same build artifact.
  Observed on ocx-mirror: ~14 phantom test failures over ~40 minutes,
  misdiagnosed twice as another agent's real breakage, plus a mutation-testing
  guard reading "survived" (false GREEN) because a concurrent unmutated build
  overwrote the artifact. Fix (now policy): one `CARGO_TARGET_DIR` per parallel
  agent. Matches arcana's own `[[mutation-sweep-snapshot-hazard]]` memory —
  same failure family, independently hit in a second repo.
- **Cross-agent hidden dependency on a removed worktree.** `~/.claude/projects/-home-mherwig-dev-ocx/memory/reference_container_stack_pinned_to_deleted_worktree.md`
  (2026-09-17): the shared sigstore/registry test container stack bind-mounted
  paths inside whichever worktree started it first (`wp-43`); merge cleanup
  removed that worktree per the "whoever creates it removes it" rule, and the
  containers kept mounting the dead path for hours, surfacing later as mass
  phantom reds in unrelated signing tests. Docker also recreated the missing
  bind source as a **root-owned** directory, which `shutil.rmtree` cannot
  remove — "a leftover agent worktree that refuses to delete" is the tell.
- **Guard-forced false drift.** `~/.claude/projects/-home-mherwig-dev-ocx/memory/project_guard_forced_spec_drift.md`
  (2026-07-29): adding a new validation guard mid-run made an already-published,
  correct artifact look "drifted," and the guard's own signposted remedy
  (`patch --metadata-only`) would have silently broken it if auto-applied.
  Caught only because that remedy path required a manual `workflow_dispatch`,
  never a cron — a containment property, not a design guarantee.
- **Rebase-conflict resolution silently regressing sibling commits.** `~/.claude/projects/-home-mherwig-dev-ocx/memory/feedback_subagent_per_rebase_conflict.md`:
  inline conflict resolution on `feat/mirror-pipeline-describe` dropped a
  `use_zigbuild` build step from a prior commit, the same wrong resolution
  repeated across **three** sibling rebases, invisible until CI broke with
  `E0463: can't find crate for core`. Now codified: one subagent per conflict
  + a post-rebase "every file in `git show --stat` must match the commit
  subject" audit.
- **Governance override at goal-close.** ocx commit
  [`5261643a`](https://github.com/ocx-sh/ocx/commit/5261643a) ("post-close
  wave"): the meta-orchestrator **overrode** a sub-orchestrator's own NO-GO
  verdict (WP-24 aborted because a measured 173.5s missed its own 240s bar)
  because the owner's goal had phrased that lane swap as a hard stop
  condition rather than a target the sub-orchestrator could veto — a real
  authority conflict between a bound-but-unratified threshold and a hard
  owner mandate, resolved in the owner's favor after the fact.
- **A landed "win" that a later self-measurement reversed.** ocx's Bazel
  lane swap (`8a8546f8`, `02ff88f0`) landed and was treated complete, but
  `../ocx/.claude/artifacts/measurement_bazel_r2.md` (cited in
  `ocx-mirror/.claude/artifacts/research_bazel_crate_split_lessons.md`)
  later recorded **NO-GO on wall-clock grounds**: the win was only 66.6s
  against a ≥240s bar, because 58% of the workflow (`cargo nextest list` +
  release build) wasn't replaced by Bazel at all. The same landed change also
  shipped a test-report regression (deleted the JUnit consumers, so the PR
  publisher named 34 targets and zero individual tests).

## Q2 — guards that demonstrably helped

- **Idle/stall watchdog** (`followup-a-watch.py`, ocx-contrib 2026-08-04):
  600s poll, 45-min-silence stall flag, explicitly built from a prior
  session-limit-kill death. Used successfully across the 61/63-shipped
  follow-up run.
- **Bounded review-fix rounds.** Real mandates used ≤2 rounds
  (`feedback_autonomous_mode_extra_ca_448.md`, ocx#448→PR#465) or ≤3
  (`feedback_autonomous_mode_crate_split.md`; ocx-mirror's in-flight
  `bazel-crate-split` goal ledger, phase R). Matches — and independently
  corroborates in a second and third repo — arcana's own
  `[[review-round-cap-two]]` lesson born from the 5-round/6h blowup. No
  mandate in this set exceeded 5 rounds; 5 is the one known bad outlier.
- **LOC-bounded deferral threshold, and it worked.** The extra-CA-roots run
  (ocx#448 → [PR#465](https://github.com/ocx-sh/ocx/pull/465)) opened
  follow-up issues #466–#471 from round-2 findings outside scope.
  [ocx#466](https://github.com/ocx-sh/ocx/issues/466) (unbounded read before
  a size check, CWE-400) was real, fixed, and **closed the same day**
  (2026-09-15) — the deferral mechanism produced an actionable, quickly
  resolved issue, not noise.
- **Durable scratch outside `/tmp`.** Adopted after the two scratchpad-wipe
  incidents: `~/.cache/hex/` for long-running fleet jobs
  (`ocx-contrib-fleet-roll-2026-09-16.md`), `<repo>/.tmp/` for
  session-scoped drafts per every autonomous-mode mandate seen
  (`feedback_autonomous_mode_extra_ca_448.md`,
  `feedback_autonomous_mode_crate_split.md`).
- **Per-job CI inspection over top-level `conclusion`.**
  `~/.claude/projects/-home-mherwig-dev-ocx/memory/reference_ci_matrix_skip_reports_success.md`:
  a `verify-deep` run concluded `success` with its entire platform matrix
  `skipped` (unexpanded `${{ matrix.job.name }}` was the tell), hiding a real
  cross-platform bug. Companion finding same file: two consecutive **red**
  required PR checks went unread for two cycles even though nothing was
  hiding them. Fix in active use: `gh run view <id> --json jobs`, treat
  unexpected `skipped` as a red, never stop at top-level conclusion.
- **`/hex-finalize`'s pre-flight halt, used correctly.** ocx commit
  [`ed2e0fcd`](https://github.com/ocx-sh/ocx/commit/ed2e0fcd) (2026-09-22):
  finalize detected it was running from a non-primary linked worktree and
  halted rather than rewrite a branch it didn't open — "nothing was
  rewritten, no backup ref armed" — then recorded that reasoning in the
  plan's status block instead of silently proceeding or silently stopping.
- **Explicit spawn log + owner-actions-collected + divergences-with-reasons
  sections** in the run ledger itself (ocx-mirror
  `.agents/goal/bazel-crate-split.md`, in flight as of this research,
  started from its own prior-lessons research file). Structural descendant
  of the failure modes above, not yet provable as "helped" since the run
  hasn't concluded — noted as current best-practice template, not evidence.

## Q3 — deferral GitHub issues: created, and useful?

Yes, on both populations found:

- **Review-round deferrals.** ocx#465 → #466–#471. #466 (real CWE-400, see
  above) fixed and closed within a day. This is the LOC/scope-deferral
  pattern from the example prompts (loop 4/5/6) working as designed.
- **Research-sub-orchestrator "doubt" deferrals.** The `fork —` prefixed
  issues in ocx-sh/ocx (vendored `rust-oci-client` fork gaps): e.g.
  [ocx#311](https://github.com/ocx-sh/ocx/issues/311) "a redirect to an IP
  literal bypasses the SSRF guard" is a fully-researched, decision-ready
  writeup — code citations, a "for comparison" section showing the correct
  pattern elsewhere in the same codebase, explicit statement of what's
  *not* wrong ("nothing is republished, no credential leaks"). It was later
  **revised in place** (2026-08-29 update: "premise 1 is dead, premise 2
  stands," re-verified against a newer commit) rather than left stale —
  evidence these issues get revisited, not just filed and forgotten. Several
  siblings (#270, #271, #312, #414, #419, #455) remain open, consistent with
  "hard circumstances only" escalation producing a real backlog rather than
  everything auto-resolving.
- ocx-mirror's own tracker shows the same split: mechanical/scoped issues
  close fast (#84, #78, #81 — all closed within the week they were filed,
  Sept 2026), while larger feature asks (#5, #11, #13 — mirror daemon) stay
  open since June, looking like deliberately-scoped-out product decisions
  rather than deferral debt.

## Q4 — how was "done" verified, and any false claims?

- **Stated bar, every real mandate:** green pipeline **and** the manual
  "Verify Deep"/"Deep Verify" workflow, explicitly named as part of the gate
  (not assumed from default CI) — `feedback_autonomous_mode_extra_ca_448.md`,
  `feedback_autonomous_mode_crate_split.md`, and the in-flight
  `bazel-crate-split` ledger's own "Oracle" gate (a pinned-tag worktree
  running its *unmodified* test suite against the new binary, at each phase
  boundary, plus e2e tier 2 — deliberately stronger than CI because the
  ocx post-close wave's own DX-75 finding showed CI-green is gameable: an
  auth probe returned 403 identically for a valid, missing, and wrong
  credential, so "not-401" would have reported an edge-block as success).
- **False-done, demonstrated:** the matrix-skip `success` (Q2, ocx
  `reference_ci_matrix_skip_reports_success.md`) is the clearest case — a
  run was green while running nothing, for an unknown span of history, and
  it hid a real bug until a different branch happened to run the workflow
  "for real."
- **Landed-but-wrong, self-corrected:** the Bazel lane-swap "win" (Q1) —
  shipped and treated as complete, reversed in verdict by a later
  self-measurement that the whole initiative's justifying metric was NO-GO.
  Not a knowing false claim; a claim later runs verified was wrong.
- **No example found** in this repo set of a run *explicitly* asserting
  "done"/finalized over a pipeline it knew was red. The closest near-miss is
  the matrix-skip false-green, which the guard itself (a later run) caught —
  i.e. the failure mode exists, but nothing here shows an agent overriding a
  known-red pipeline to claim completion.

## negative

- Did not find a case of silent scope-cutting under the "cutting features to
  save time is NOT accepted" rule being violated — but this was not checked
  via exhaustive per-PR diff review, only via memory/commit-message search;
  absence of evidence is weak here.
- Could not confirm a second compaction-triggered incident distinct from
  arcana's own known background-spawn deadlock; no other repo's memory or
  commit log names compaction as a trigger.
- ocx-mirror's `bazel-crate-split` goal (started 2026-09-22, same day as
  this research) is **live right now** — three `claude --model opus --effort
  high` processes running, one with cwd `ocx-mirror` — and could not be
  assessed for stuck/drift/false-done; it is cited above only as a
  structural artifact (ledger template), not as concluded evidence.
- ocx-contrib has no `.git` (not a git repo at this path), so its history
  could not be searched directly; relied on `.claude/state/run-2026-08-04/*`
  files and Claude project memory instead, which is likely why it reads as
  the cleanest run in this set (state-file evidence, not commit archaeology).
- Did not exhaustively read every memory file under `ocx`/`ocx-mirror`
  (~85 files) — grepped for failure/success keywords and read matches; a
  relevant note filed under an unmatched name would have been missed.
- `gh issue list --search` was run only against ocx-sh/ocx and
  ocx-sh/ocx-mirror, as scoped; did not check whether the 2026-08-04
  ocx-contrib wave itself opened issues in any `mirror-*` repo.
- The apparent duplicate commits in `ocx`'s log (e.g. `baaf14cd` /
  `35bb0617` / `2aa4f027` with identical subjects) were not investigated —
  likely artifacts of the `wp-01`/rebased worktree branches visible in
  `git worktree list`, not confirmed.

## leads

- goal-loop skill: adopt an idle/stall watchdog matching
  `followup-a-watch.py`'s shape (poll interval + N-minute-silence flag) as a
  first-class guard — the only working implementation found, built from a
  real session-limit-kill death.
- goal-loop skill: mandate per-agent `CARGO_TARGET_DIR` (and any shared
  build-cache dir) isolation for parallel cargo-based sub-orchestrators — two
  independent false-green/phantom-red incidents trace to a shared target
  dir, in the same repo, months apart.
- goal-loop skill: require Deep-Verify gates to inspect per-job CI status
  (`gh run view --json jobs`), never top-level `conclusion` — demonstrated
  false-green from a fully-skipped matrix reading `success`.
- goal-loop skill: mandate a durable scratch path outside `/tmp` for
  anything expected to outlive a few tool calls — two independent
  scratchpad-wipe incidents, 2026-08-14 and 2026-09-16, same tmpfs
  mechanism both times.
- goal-loop skill: worktree-removal checklist should include "any
  container/process bind-mounting a path inside this worktree" before
  delete — hit once in ocx, produces root-owned dirs that resist normal
  cleanup and silently break unrelated tests for hours.
- hex-execute: consider promoting ocx's per-conflict-subagent rebase rule
  (spawn one subagent per conflict + post-rebase stat-vs-subject audit) —
  the failure it guards against (silently dropped step, repeated identically
  across sibling rebases, invisible until CI) is exactly the class
  hex-execute's own merge/rebase step could hit.
- goal-loop skill: no new guard needed for round caps or LOC-bounded
  deferral — both are already validated across three independent repos
  (arcana, ocx, ocx-mirror) at ≤2/≤3 rounds and ~500–1200 LOC; just carry
  the numbers forward.

## Sources

- `.agents/research/discuss-goal-loop-recon.md` (arcana; prior known findings)
- `~/.claude/projects/-home-mherwig-dev-arcana/memory/autonomous-spec-superiority-program.md`
- `~/.claude/projects/-home-mherwig-dev-ocx-contrib/memory/overnight-run-2026-08-04.md`
- `ocx-contrib/.claude/state/run-2026-08-04/{followup-a-watch.py,followup-a-agents.json,run-notes.md,worker-guardrails.md,wave-2-brief.md,wave-6-brief.md}`
- `~/.claude/projects/-home-mherwig-dev-ocx-mirror/memory/{session-scratchpad-can-vanish-midrun,mutation-copy-needs-renamed-package,mutation-copy-shared-target-false-green,ocx-contrib-fleet-roll-2026-09-16}.md`
- `~/.claude/projects/-home-mherwig-dev-ocx/memory/{feedback_autonomous_mode_extra_ca_448,feedback_autonomous_mode_crate_split,project_overnight_followups,project_overnight_mirror_initiative,reference_container_stack_pinned_to_deleted_worktree,reference_ci_matrix_skip_reports_success,feedback_subagent_per_rebase_conflict,project_guard_forced_spec_drift}.md`
- ocx-mirror `.agents/goal/bazel-crate-split.md`, `.claude/artifacts/research_bazel_crate_split_lessons.md` (in-flight run, cited as artifact not as concluded evidence)
- ocx commits: [`ed2e0fcd`](https://github.com/ocx-sh/ocx/commit/ed2e0fcd0515124bcb6ee2505effd1dc5a7c137b) (finalize halt), [`5261643a`](https://github.com/ocx-sh/ocx/commit/5261643a) (post-close wave / governance override)
- GitHub issues: [ocx-sh/ocx#466](https://github.com/ocx-sh/ocx/issues/466), [ocx-sh/ocx#311](https://github.com/ocx-sh/ocx/issues/311), plus `#270`, `#271`, `#312`, `#414`, `#419`, `#455` (open, unread bodies); [ocx-sh/ocx-mirror#84](https://github.com/ocx-sh/ocx-mirror/issues/84), `#78`, `#81`, `#5`, `#11`, `#13`
- `ps aux` snapshot confirming the in-flight `bazel-crate-split` run's concurrency (three `opus --effort high` processes, one cwd `ocx-mirror`)
