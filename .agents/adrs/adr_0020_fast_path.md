# ADR: Fast path — parallel pipelines, counted gates, no waiting

## Metadata

**Status:** Proposed
**Date:** 2026-10-04
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A
**Related:** `.agents/research/hex-inner-loop-overhaul.md` (proposal v5) · `.agents/research/handover-ocx-interface-contract-loop.md` · `adr_0010`, `adr_0012`, `adr_0013`, `adr_0015` (superseded in part) · `adr_0001` (class names) · `adr_0016` (adversary and checklist stand)
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions
- [x] OR the deviation is justified in the Rationale section below (three named deviations)
**Domain Tags:** devops
**Supersedes:** `adr_0010` (per-merge scoped verification, checkpoints), `adr_0012` (per-WP effective tier), `adr_0013` (heartbeats, heavy semaphore, decomposing coordinator), `adr_0015` (review by join level) — each in part, execute-side only

## Context

The ocx interface-contract run (108 transcripts) shows the execute loop
spending its time on its own checks, not on the work:

- compile/test parallelism **1.0**: 17 waves of 45 work packages never built
  in parallel;
- builders spent **36 %** of their lifetime in lock, verify and wait calls;
- **89 of 107** spawns ran on the deep class;
- **41** full verifies plus **21** merge gates;
- **33** leaf reviews plus **28** fix passes.

Root cause: every gate is eager and local. It is decided per change by an
agent that sees one change and none of the cost. Asked "might this matter?" N
times, a cautious agent answers yes N times, and locks turn the DAG into a
queue. Reclassifying only moves the threshold the agent then crosses on every
change. The decision is **who decides, and how often**.

## Decision Drivers

- Gates must be fixed by count, not triggered by per-change judgment.
- Parallelism must be real: pipelines build concurrently inside one build's
  resource budget.
- Cost-raising decisions belong to the orchestrator, which sees the whole run.
- Keep what earns its cost: `/hex-review` panel and codex, `/hex-finalize`,
  contract-first TDD, the last-reviewed anchor.
- Style: single-source contracts, thin dispatchers, delete before adding.

## Considered Options

### Option 1: Reclassify (tune the per-WP tier and flags)

**Description:** Keep the machinery; move thresholds so fewer WPs reach the
heavy gates.

| Pros | Cons |
|------|------|
| Smallest change | Agents cross any threshold on every change; the diagnosis is unchanged |
| | Locks and per-merge gates remain |

**Rejected.**

### Option 2: Remove the inner review entirely

**Description:** No review until the end; steps just build.

| Pros | Cons |
|------|------|
| Fastest | Rejected by the owner: a review of the whole range is wanted before landing |
| | Loses the seam check between pipelines |

**Rejected by the owner.**

### Option 3: One main pipeline

**Description:** One serial pipeline, no parallelism, no contract wave.

| Pros | Cons |
|------|------|
| Simplest, no merges | Gives up parallelism the plan can safely buy where contracts are fixed |

**Rejected.** It survives as the small-task case.

### Option 4: v5 — pipelines and counted gates (chosen)

**Description:** A few pipelines cut along contracts, run in parallel;
steps inside a pipeline are serial fresh agents. Step feedback is the only
inner check. Exactly two full gates per run, one review (at most 3 calls),
workers never wait, escalation by the orchestrator only.

| Pros | Cons |
|------|------|
| Gates fixed by count; no per-change judgment | Contract wave is up-front cost; a wrong contract re-briefs pipelines |
| Real build parallelism at one build's budget | Defects surface at integration, not per merge |
| `standard` class by default | |

## Decision Outcome

**Chosen Option:** Option 4.

**Rationale:** it changes who decides and how often. The resolved decisions,
the removed machinery and the constitution numbers are in `hex/DESIGN.md`
round 25: **2** full gates per run, **<= 3** review calls, workers **never**
wait, escalation **orchestrator only, on repeated failure**. Changing a
number takes an ADR backed by a measured run.

### Rationale — named deviations from `hex/DESIGN.md`

| Deviation | Why | Bound |
|---|---|---|
| `hex-execute` is no longer a tiered orchestrator (rounds 17, 22) | Tier files and overlays were the per-WP threshold machinery | `hex-plan`, `hex-review`, `hex-architect` keep their tiers |
| Capability classes `light` / `standard` / `standard-high` / `deep` replace `fast-balanced` / `deep-reasoning` (`adr_0001`) | One default class plus a counted escalation ladder | Shipped files name classes only; literal names only in an "e.g. on a Claude harness" line in `models.md` |
| `--no-verify` on hex-owned branches, overriding project verify-before-commit lines | Those lines are injected into every subagent and would put the full gate back per commit | Hex-owned branches only; the step brief states the run's two exit gates satisfy them; the release gate runs hooks and lint over the final range |

### Quantified Impact

| Metric | ocx run | v5 |
|---|---|---|
| Shape | 45 WPs, 17 waves | ~6 pipelines x ~6 steps, contract wave + one fan-out |
| Deep-class spawns | 89 | plan design only |
| Full verifies | 41 + 21 merge gates | 2 |
| Review | 33 leaf reviews + 28 fix passes | 1 (<= 3) `/hex-review` calls |
| Build parallelism | 1.0 | live pipelines, at one build's RAM |

### Consequences

**Positive:** parallel builds; two full gates; cheap default class; fewer
instruction bytes (tier files, overlays, join levels, semaphore deleted).

**Negative:** a contract-wave miss costs a re-brief; regressions are found at
integration, not per merge; a project that wants per-merge verification loses
it.

**Risks:** a red integration gate after a large run, mitigated by one fix pass
and a cap of 2 before handing to the user. A pipeline split along a wrong
contract, mitigated by the contract tests committed in the wave and the
`git diff` check at each step's return.

## Non-Functional Requirements

| Axis | Impact |
|---|---|
| Scalability | Live pipelines x jobs per pipeline <= one build's jobs |
| Availability | No worker waits on a lock, gate or poll |
| Latency | Gates by count (2) instead of per merge |
| Security | Review panel and codex kept; `--no-verify` bounded to hex-owned branches |
| Cost | `standard` default; `deep` for design and last-resort escalation |
| Operability | Orchestrator two levels, event-driven, >= 20 min fallback |

## Rollout / Migration

1. Ship the rewritten `hex-execute`, `hex-core` references, `hex-init`,
   `hex-loop` (`paused` state), `hex-review`, DESIGN round 25, CHANGELOG
   `[Unreleased]`, README, `hex.toml`.
2. Update the global `~/.claude/CLAUDE.md` routing table to the four classes.
3. Validate on the next real run against the ocx numbers above.

## Compliance

`grim build` for every changed hex skill and rule; `task publish --
--dry-run`.

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-10-04 | Michael Herwig / Claude | Initial draft (Proposed) |
