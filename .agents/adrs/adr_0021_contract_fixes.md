# ADR: Contract fixes — a CI job that proves the full suite, an opt-in issue grant, and artifact commits on ask

## Metadata

**Status:** Accepted (Michael, 2026-11-27, implemented in `1a74e4a`, `01e7853`, `07e0e6f`; `3de71ab`, `27cfbca` and `1f2ccc1` carry the rest of the series)
**Date:** 2026-11-27
**Deciders:** Michael Herwig
**Issue/Ticket:** [#16](https://github.com/michael-herwig/arcana/issues/16), [#17](https://github.com/michael-herwig/arcana/issues/17)
**Related:** [`adr_0020_fast_path.md`](adr_0020_fast_path.md) (amended: the wording "2 full gates per run") · [`adr_0018_goal_loop_prompt.md`](adr_0018_goal_loop_prompt.md) (amended: the issue grant) · [`adr_0005_archive_fold_back.md`](adr_0005_archive_fold_back.md) (fold consent, related) · [`../discussions/verification-levels.md`](../discussions/verification-levels.md) (parked; declined a hex-owned level vocabulary) · `hex/DESIGN.md` round 26
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions
- [x] OR the deviation is justified in the Rationale section below (three named amendments; the evidence for the first is a field report, not a measured run)
**Domain Tags:** devops | security (consent)
**Supersedes:** none; amends `adr_0020` and `adr_0018` in part, as stated below

## Context

Issue #16 is a retro report from one unattended `/hex-loop` run, discuss
through finalize, on a mid-sized repository whose full test suite runs only in
CI. Issue #17 reports that the `/hex-execute` to `/hex-finalize` path never
marked a plan done. Both came out of the same external series, which was
merged and then reworked once the reasons below showed up. Three of its
changes depart from a decision already recorded:

- the release gate read the documented verification literally and ran a
  CI-only suite locally, and `adr_0020` fixes "2 full gates per run";
- the paste's issue grant let unattended runs file issues nobody asked for,
  and `adr_0018` made that grant a shipped default;
- a loop branch kept a dirty tree because no skill committed the artifacts the
  planning, architecture and discussion modes wrote, and `hex/DESIGN.md` says
  "hex never commits outside execution".

A fourth change is deliberately not an amendment: the review-call budget.

## Decision Drivers

- The constitution numbers stay numbers: gates and review calls are fixed by
  count, never by a per-change judgment (`adr_0020`).
- hex adds no vocabulary the project must learn when a pointer to a project
  fact does the job (two-layer model; the parked discussion declined a
  fourth axis beside tiers, join levels and budgets).
- A remote act is on only when a human turned it on, and a malformed setting
  fails closed (`adr_0018`, `C-815`/`C-816`).
- Approval stays where a human exercises it: `adr_0005` leaves a fold
  unstaged so that approval is the `git add`.
- A gate's reported result never claims more than what ran.

## Considered Options

### Decision 1 — how a project whose full suite cannot run locally is gated

#### Option 1a: Status quo — both gates run the full documented verification locally

| Pros | Cons |
|------|------|
| No change to the constitution wording | Runs a CI-only suite locally: about 1,500 tests, 30 minutes and some 360 failures by design in the reporter's run, then a further cycle to isolate failures that were not real |

Rejected: the cost lands on every run of such a project, and the failures are
noise the gate cannot tell from a regression.

#### Option 1b: A gate level axis, `full` or `targeted` (the form first merged)

**Description:** a `Gate level:` setting. Under `targeted`, both gates run the
selective command locally and a named CI job proves the full suite.

| Pros | Cons |
|------|------|
| Names the behaviour wanted | A fourth axis beside tier `low..max`, join level and review budget `scoped\|full` |
| | Every project must learn a level and its default value |
| | The parked discussion `verification-levels` declined a hex-owned level vocabulary, three seats of three |

Rejected.

#### Option 1c: A Pointers row naming the CI job that proves the full suite (chosen)

**Description:** `Full suite: <CI workflow or job>` in `hex.md › Pointers`.
The row means that job, green on the pushed head, is the full suite's proof.
There is no level and no value to spell; absent, nothing changes.

| Pros | Cons |
|------|------|
| Names the project fact, not a hex vocabulary | A gate's "full" now has two meanings, which the report must keep apart |
| Absent row is today's behaviour exactly | Needs a forge whose run hex can read |
| Degrades to the full local run when it cannot be proven | |

### Decision 2 — which hint value turns a remote act on in `/hex-loop`

#### Option 2a: Keep the issue grant as a shipped default

Rejected: unattended runs filed issues nobody asked for; the grant is a remote
act and `adr_0018` says a human must turn a remote act on.

#### Option 2b: Remove the issue grant; only a per-run widening extra can grant it

| Pros | Cons |
|------|------|
| Smallest surface | A project that always wants issues re-types the extra on every run |

Rejected as the only route: it stays available, but a standing project
preference is a legitimate use of the hint.

#### Option 2c: `issues: on` under `Goal loop:` as the single hint value that grants a remote act, default off (chosen)

| Pros | Cons |
|------|------|
| A project opts in once, in a committed preference | The hint now has one exception to "grants only local acts" |
| Fails closed: any value other than exactly `on` or `off` reads as off and is disclosed | A breaking change for projects that relied on the old default |
| By default deferrals become would-be issues in the goal file, listed paste-ready in the closing block | |

### Decision 3 — whether the artifact modes commit what they write

#### Option 3a: Status quo — hex never commits outside execution

Rejected: a loop branch kept a dirty tree, and finalize halts on it.

#### Option 3b: `/hex-plan` alone commits its plan when a loop brief asks (the form first merged)

Rejected: `/hex-architect` and `/hex-discuss` write artifacts a loop branch
needs the same way, so the same defect stayed for them.

#### Option 3c: The artifact modes always commit what they write

Rejected: it removes the human's approval at `git add` that `adr_0005`
relies on for a fold, and commits without any ask.

#### Option 3d: One rule — the artifact modes commit exactly their own artifacts, staged by name, never push, only on an explicit ask (chosen)

| Pros | Cons |
|------|------|
| One rule in one place (`memory.md` § Version control) covers `/hex-plan`, `/hex-architect` and `/hex-discuss` | Narrows a long-restated clause, so `hex/DESIGN.md` needs a pointer instead of thirteen edits |
| No ask, no commit: a run with no ask behaves as before | A drain to `/hex-loop` commits only on the trunk, since the loop branch starts there |
| The ask is a line in a loop brief, the human's own words, or the yes at `/hex-discuss`'s restate-gate | |

## Decision Outcome

**Chosen:** 1c, 2c and 3d.

### Rationale — named amendments

| Amendment | Why | Bound |
|---|---|---|
| `adr_0020` and round 25: "2 full gates per run" now allows a gate's "full" to be the selective command run locally plus a declared CI job that proves the full suite | The gate cost was the CI-only suite run locally; the count stays two | Takes effect only with a documented selective test command, the named job and a forge whose run can be read; otherwise both gates run the full verification locally and the gate rows say so. A selective run is never reported as the full suite; the suite counts as proven only on a green read of the named job. `/hex-finalize` reads the job and never dispatches it, and holds the draft → ready flip until it is green |
| `adr_0018` and round 23: a `Goal loop:` hint grants only local acts, except `issues: on` | The grant was a shipped default that nobody asked for | The one hint value that turns a remote act on; default off; a value other than exactly `on` or `off` reads as off and is disclosed; a goal file written before the change has no would-be issues section and re-print flags it. The rule is stated once, in `hex-loop/SKILL.md` § Preferences hint |
| "hex never commits outside execution" (rounds 10–23) narrows | The loop branch needs its artifacts committed | Exactly the run's own artifacts, staged by name, never pushed, only on an explicit ask. On the same ask `/hex-execute` commits the plan's later Status and fold writes before it hands off. `/hex-review` and `/hex-retro` still never commit. `adr_0005`'s fold consent and "finalize never commits a fold" still hold for a run with no ask; on an asked loop run `/hex-execute`'s commit takes the `git add` step |

### Evidence for Decision 1

`adr_0020` and round 25 say that changing a constitution number takes an ADR
backed by a measured run. This change keeps the number and amends what
"full" means for a gate, which is a change to constitution wording, so the
bar applies.

The evidence is the reporter's run in
[#16](https://github.com/michael-herwig/arcana/issues/16): the release gate
ran the full suite locally on a CI-only suite, about 1,500 tests, 30 minutes,
and roughly 360 failures by design, then spent another cycle isolating
unexplained failures. That is a field report from a consuming project. **It is
not a measured hex run:** no one ran this repository's tooling before and
after the change on a fixed workload. The maintainer accepted the change on
that evidence on 2026-11-27, and a follow-up to back it with a measured run
is recorded under Validation.

### Not an amendment — the review-call budget stays

The fix for #17 changed how a plan reaches `done`, and the series first
shipped it by making each fix-round re-check its own `/hex-review` call and
adding an exit call, all declared to run beside the three. Options:

- **Uncounted calls (as first merged).** A clean run always made two calls and
  a run with fix rounds could make six, while round 25 fixes the count at
  three. It would have needed an amendment to the constitution number
  without a measured run.
- **Rounds inside a call (chosen).** A review call is round 1 plus its fix
  rounds. `/hex-review` runs every round and records its verdict; a re-check
  is `/hex-review --fix-round --base=<sha>` and belongs to its call. The round
  that leaves no actionable finding, with the gate green and the convergence
  check Converged, is the exit round, and its Approve writes the terminal
  review state. A clean round 1 is that round in one invocation.

Review calls per run stay at most three, counted as before. `--round` and
`--exit` are gone. Nothing in this ADR amends that number.

### Consequences

**Positive:** a project with a CI-only suite gates in the time of its
selective command; the gate report says what ran; one source for forge facts
and one for what hex commits; a goal-loop run no longer files issues unasked.

**Negative:** a gate's "full" has two meanings the reader must keep apart;
`issues: on` is a breaking change for a project that relied on the old default
(its changelog entry says how to keep it); the "never commits" clause is now
read together with a pointer, not as one sentence.

**Risks:** a selective command that misses a regression, mitigated by the
named job's proof gating the draft → ready flip. A forge the run cannot be
read from, mitigated by the degrade ladder: the full suite is named unproven
rather than assumed.

## Non-Functional Requirements

| Axis | Impact |
|---|---|
| Latency | Gate time for a CI-only suite falls to the selective command's time; not measured here |
| Security | Remote acts stay opt-in and fail closed; the artifact commit never pushes |
| Cost | Fewer local full-suite minutes for a declaring project |
| Operability | One Pointers row, one hint value, one ask line; absent each, behaviour is unchanged |

## Validation

- [ ] A measured run backs Decision 1: a fixed workload on a project that
  declares `Full suite:`, gate time and escaped failures compared with the
  full local run. Until it exists, this ADR rests on the field report above.
- [x] `grim build` of every changed skill and `task publish -- --dry-run`.
- [x] Round 25's text is unchanged; only its amendment pointer changed, and
  `Review calls per run: <= 3` keeps its wording.

## Links

- Related ADR: [adr_0020_fast_path.md](adr_0020_fast_path.md), [adr_0018_goal_loop_prompt.md](adr_0018_goal_loop_prompt.md), [adr_0005_archive_fold_back.md](adr_0005_archive_fold_back.md)
- Discussion: [verification-levels.md](../discussions/verification-levels.md)
- Constitution record: `hex/DESIGN.md` round 26
- Issues: [#16](https://github.com/michael-herwig/arcana/issues/16), [#17](https://github.com/michael-herwig/arcana/issues/17)

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-11-27 | Michael Herwig / Claude | Recorded after implementation; accepted on the field report in #16, measured run to follow |
