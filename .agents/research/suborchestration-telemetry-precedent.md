# Research: hierarchical per-task sub-orchestration and run telemetry

<!--
Technology-landscape research. Filename and location: this project's
documented research convention (.agents/research/).
Owner: a researcher worker. Handoff to: /hex-architect, /hex-plan.

Purpose: persist landscape findings that inform ADRs, plans, and design
decisions. Findings decay - check the Expires date before trusting them.
-->

## Metadata

**Date:** 2026-09-05
**Domain:** multi-agent orchestration, observability
**Triggered by:** proposal to move from one orchestrator serially running every
work package's phase pipeline to one sub-orchestrator per ready work package
(parent only schedules, merges serially, and runs gates), plus per-phase run
telemetry so wall-clock regressions are measured, not anecdotal. Extends
`hierarchical-orchestration-precedent.md` and
`hierarchical-execution-performance.md` (2026-07-19) rather than repeating
them — this pass covers concurrency-budget allocation policy, the
blocked-parent failure mode, and telemetry schema, which those did not.
**Expires:** 2027-03-05 (6 months — OTel GenAI semconv is explicitly
"Development" status and Claude Code's own subagent nesting limits changed
three times between June and August 2026; re-verify both before relying on
exact numbers)

## Direct Answer

One sub-orchestrator per ready work package is the same shape every mature
hierarchical scheduler converges on (OTP supervisor-of-supervisors, Temporal
parent/child, YARN's hierarchical queues, hex's own existing
orchestrator→coordinator→leaf chain) — the fix is sound. Two things make or
break it, both about the shared concurrency pool: (1) **allocate budget as a
static hierarchical reservation with borrowing (HTB/YARN-style), never as a
shared blocking pool** that a waiting coordinator and its own children both
draw from — that shared-pool shape is exactly the Airflow SubDAG deadlock and
the Python `ThreadPoolExecutor` nested-submit deadlock; (2) **a sub-orchestrator
that is only waiting on its own children must not count against the
concurrency cap** — it is doing no compute, and charging it anyway is what
turns "coordinator idle" into "pool exhausted." hex's current design already
does the first part right (schedule-time budget slices, not a runtime
semaphore); it should make the second part explicit. For telemetry: append
one JSONL line per phase start/end, kept under 4096 bytes so POSIX `O_APPEND`
keeps concurrent multi-process writes atomic with no lock, carrying explicit
`queue_wait_ms` separate from `work_ms` — the queue/wait split is the single
most commonly-missing field in build and delivery telemetry, and it is what
would have made the RCA's "WP-1 idle ~1h" finding a number instead of an
after-the-fact trace reconstruction.

## Technology Landscape

### Trending (gaining momentum)

| Tool/Pattern | Adoption Signal | Key Benefit | Relevance |
|--------------|------------------|-------------|-----------|
| Manager / agent-as-tool orchestration (OpenAI Agents SDK, LangGraph supervisor) | Became the default multi-agent shape across 2025-2026 SDKs | Orchestrator keeps control and aggregates one result per join, vs. handoff's control transfer | This is the shape a hex sub-orchestrator already takes — confirms the direction, not a change |
| Per-phase / per-span GenAI observability (`gen_ai.*` OTel attributes) | New GitHub org spun out mid-2025 (`open-telemetry/semantic-conventions-genai`), actively adding attributes through 2026 | Vendor-neutral schema for agent/model/token spans | Directly usable as the field-naming convention for hex's telemetry lines even without a full OTel pipeline |

### Established (proven, widely accepted)

| Tool/Pattern | Status | Notes |
|--------------|--------|-------|
| OTP supervision trees (`one_for_one`/`rest_for_one`/`one_for_all`) | Decades-old, unchanged core model | Restart intensity is explicitly warned to **not** be set equal at every level — it multiplies across levels |
| Kubernetes Indexed Jobs + CronJob `concurrencyPolicy` | GA, stable since ~1.24 | `Allow`/`Forbid`/`Replace` is a 3-value budget policy scoped per-CronJob, not hierarchical across CronJobs |
| YARN CapacityScheduler hierarchical queues | Mature, still the reference hierarchical scheduler design | `capacity` (guaranteed) + `maximum-capacity` (ceiling) + elasticity (borrow idle capacity from siblings) is the textbook answer to "avoid both starvation and oversubscription" |
| Linux HTB (`tc`) | Mature (kernel qdisc), unchanged core model | `rate` (guaranteed) + `ceil` (borrowing limit): a class borrows from its **parent** only while both ceils allow it — same shape as YARN, at the packet-scheduling layer |
| Temporal child workflows | Stable, current docs | Official guidance: "When in doubt, use an Activity"; child workflows only when the subtask needs its own state/history/independent lifecycle, and even then capped (documented soft limit: don't spawn >1,000 children from one parent — event-history cost) |

### Emerging (early but promising)

| Tool/Pattern | Signal | Worth Watching Because |
|--------------|--------|-------------------------|
| Claude Code nested subagent spawning w/ depth cap | Shipped, then pulled, then reshipped with a lower default (5 → disabled → 3) inside three months (Jun–Aug 2026) | The instability itself is evidence: even the vendor treats "how deep should nesting go" as unsettled, and settled lower than it started |
| Kubernetes Hierarchical Namespace Controller (HNC) for quota propagation | Sig-multicluster incubator project, not core K8s | Vanilla `ResourceQuota` has **no** hierarchy — contention is "first-come-first-served" with no borrowing, i.e., the naive policy this research recommends against |

### Declining (losing mindshare)

| Tool/Pattern | Signal | Avoid Because |
|--------------|--------|-----------------|
| Airflow `SubDagOperator` | Deprecated since Airflow 2.0 (~2020), still flagged deprecated in current docs, replaced by `TaskGroup` | **The canonical negative precedent for this decision.** A SubDagOperator task occupies a worker execution slot in the parent's pool and then *blocks* waiting for its child DAG's tasks to run — but those child tasks draw from the **same** shared worker pool, so under load the parent holds the slot the child needs to ever start. Fixed only by switching to `TaskGroup`, which is a pure UI/DAG grouping construct with **no** execution-slot semantics at all — it never enters the pool. |

## Design Patterns Worth Considering

- **Hierarchical fair-share with borrowing (HTB / YARN CapacityScheduler
  shape)** — every sub-orchestrator gets a guaranteed floor (its "rate"), can
  borrow unused floor from idle siblings up to a ceiling, and the top-level
  budget is the only hard wall. This is the allocation policy this research
  recommends hex adopt explicitly (see Recommendation). Used by: Linux `tc`,
  Hadoop YARN. [HTB](https://en.wikipedia.org/wiki/Token_bucket) ·
  [YARN CapacityScheduler](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/CapacityScheduler.html)
- **Reservation at schedule time, not a shared blocking semaphore** — hex's
  existing rule ("the orchestrator hands each coordinator a fan-out budget no
  larger than its slot's share") already does this; it is the structural
  reason hex does not yet have an Airflow-shaped deadlock, and should be
  named as a hard invariant rather than an implementation detail.
  [`protocol.md` § Worker coordination](/home/mherwig/dev/arcana/hex/hex-core/references/protocol.md)
- **Grouping construct vs. execution-slot construct are different types** —
  Airflow's TaskGroup fix and Temporal's Activity-vs-child-workflow guidance
  both boil down to: don't give a purely-organizational wrapper the same
  resource footprint as a real worker. A hex sub-orchestrator that is only
  waiting should look like a TaskGroup (free), not like a SubDagOperator
  (costed).
- **Structured single-source-of-truth log, human view rendered from it** — no
  framework was found that recommends hand-maintaining two independently
  written logs (structured + prose) in parallel; every precedent that ships
  both (Cargo's `--timings` HTML rendered from its own unit-timing data;
  systemd's journal — binary structured store, `journalctl` renders human
  text on demand) generates the human view **from** the machine record.
  [Cargo timings](https://doc.rust-lang.org/cargo/reference/timings.html)

## Key Findings

**Part A — hierarchical sub-orchestration**

1. OTP supervision: strategies are `one_for_one`, `one_for_all`,
   `rest_for_one` (+ `simple_one_for_one` for dynamic children); restart
   intensity is the one explicit depth-caution the docs give — **"If your
   application has multiple levels of supervision, do not set the restart
   intensities to the same values on all levels"** because failures
   compound multiplicatively up the tree (10×10 = 100 total restarts across
   two naively-configured levels). No stated numeric depth cap otherwise —
   depth is bounded by this compounding cost, not a hard limit.
   [erlang.org sup_princ](https://www.erlang.org/doc/system/sup_princ.html)
2. Temporal: **"When in doubt, use an Activity."** A Workflow (parent or
   child) models a *composition* of Activities/child-workflows; an Activity
   models one external operation. Child workflows exist for a subtask that
   needs its own durable state, independent lifecycle, or `ParentClosePolicy`
   (`ABANDON` / `REQUEST_CANCEL` / `TERMINATE`, default `TERMINATE`). Cost is
   explicit: every child workflow adds to the **parent's** Event History,
   and Temporal's own guidance is a soft ceiling of **~1,000 children per
   parent** before that history becomes the bottleneck.
   [Child Workflows](https://docs.temporal.io/child-workflows) ·
   [Parent Close Policy](https://docs.temporal.io/parent-close-policy)
3. Airflow `SubDagOperator` is deprecated in favor of `TaskGroup`
   specifically because of the deadlock described above (parent occupies a
   pool slot while blocking on children that need the same pool) — the
   documented workaround (`mode=reschedule`, periodically releasing the
   slot) was a patch, not a fix; the actual fix was making `TaskGroup` a
   zero-footprint grouping construct instead. This is the direct analogue
   of "a sub-orchestrator consuming the parent's concurrency budget."
   [SubDagOperator docs (deprecated)](https://airflow.apache.org/docs/apache-airflow/2.5.3/_api/airflow/operators/subdag/index.html) ·
   [deadlock writeup](https://medium.com/@team_24989/fixing-subdagoperator-deadlock-in-airflow-6c64312ebb10)
4. Kubernetes: Indexed Jobs give each pod a `JOB_COMPLETION_INDEX` to
   self-partition parallel work with **no** parent process blocking on
   children at all (the controller, not a running pod, tracks completion) —
   structurally immune to the SubDAG problem. CronJob `concurrencyPolicy`
   (`Allow`/`Forbid`/`Replace`) is a **per-schedule** budget of 1, not a
   general hierarchy. Nomad's `job → group → task` nests by *co-location*,
   not by *delegation* — no task in the hierarchy waits on another the way
   an orchestrator waits on a coordinator. Dagster's dynamic outputs
   fan a graph out at runtime without a supervising op blocking on a shared
   pool; Argo's `depends` field encodes result-conditioned DAG edges
   (`task.Succeeded`/`Failed`/`AnySucceeded`) but, like GitHub Actions
   `needs`, is pure dataflow-gating — again no agent occupies a slot while
   idle-waiting.
   [Indexed Jobs](https://v1-34.docs.kubernetes.io/blog/2025/09/05/kubernetes-v1-34-pod-replacement-policy-for-jobs-goes-ga) ·
   [CronJob concurrencyPolicy](https://v1-29.docs.kubernetes.io/docs/concepts/workloads/controllers/cron-jobs) ·
   [Nomad group spec](https://developer.hashicorp.com/nomad/docs/job-specification/group) ·
   [Dagster dynamic graphs](https://docs.dagster.io/guides/build/ops/dynamic-graphs) ·
   [Argo enhanced depends](https://argo-workflows.readthedocs.io/en/latest/enhanced-depends-logic/)
5. Multi-agent frameworks, concretely:
   - **LangGraph** — supervisor pattern + subgraphs; a compiled graph is
     itself callable, so nesting is "same shape, one level down," scoped
     checkpointing per subgraph (per prior research file finding 6).
   - **CrewAI** — `Process.hierarchical` with a `manager_llm`; **delegation
     is now disabled by default** (a 2026 change — "to give users explicit
     control"), bounded by a `max_iterations` cap; the docs do **not** state
     whether the manager blocks while a delegated agent runs (open question,
     flagged in prior research as a cautionary open-issues area for CrewAI).
     [CrewAI hierarchical process](https://docs.crewai.com/en/learn/hierarchical-process)
   - **AutoGen/AG2** — hierarchical GroupChat exists specifically to collapse
     O(n²) pairwise agent messaging to ~O(n) via one mediating manager (prior
     research finding 7).
   - **OpenAI Agents SDK** — explicitly names two non-interchangeable shapes:
     **handoff** (control transfers, receiving agent owns the rest of the
     turn) vs. **manager/agents-as-tools** (orchestrator keeps control,
     calls sub-agents as tools, aggregates). A hex sub-orchestrator is the
     manager shape, not a handoff.
     [Agent orchestration](https://openai.github.io/openai-agents-python/multi_agent/)
   - **Anthropic's multi-agent research system** — lead + subagents run
     ~15× the tokens of a single chat turn; that multiplier **compounds**
     when something misbehaves — "a subagent that recursively spawns more
     subagents... can multiply cost by another 10x or more." Anthropic
     names coding as a *poor* fit for this pattern (few truly parallelizable
     subtasks) — a caution directly relevant to hex, which *is* coding.
     [Anthropic engineering post](https://www.anthropic.com/engineering/multi-agent-research-system)
   - **Claude Code subagents** (current, fetched from official docs
     2026-09-05) — by default a subagent may spawn subagents **up to 3
     layers below the main conversation** (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`,
     default 3; set to 1 to disable nesting). At the depth limit, Claude Code
     **withholds the Agent tool** so the deepest layer must finish work
     itself and return one summary — the same "flatten instead of recursing
     further" shape hex already enforces at orchestrator→coordinator→leaf.
     Critically: **the parent conversation does not block** during subagent
     execution — with fork mode on (default), subagents run in the
     background. This is the non-blocking-parent precedent hex's design
     should point to directly.
     [code.claude.com/docs/en/sub-agents](https://code.claude.com/docs/en/sub-agents)
     (secondary corroboration, dated Jun–Aug 2026, on the churn:
     [nested sub-agents changelog analysis](https://readysolutions.ai/blog/2026-06-11-claude-code-nested-subagents/))
6. **Concurrency budgeting across a hierarchy** — the two textbook answers
   that avoid both starvation and oversubscription are **hierarchical token
   buckets (HTB)** and **YARN's CapacityScheduler**, and they're the *same*
   policy at two different layers: a guaranteed floor per branch (`rate` /
   `capacity`) that can never be taken away, plus a ceiling (`ceil` /
   `maximum-capacity`) up to which a branch may **borrow** currently-unused
   capacity from siblings. The naive alternative — Kubernetes vanilla
   `ResourceQuota` across namespaces with no hierarchy — is explicitly
   **first-come-first-served** with no borrowing semantics at all, which is
   the failure mode to avoid, not a competing design. Bazel's `--jobs` is a
   single flat worker-count cap with no sub-budgeting for nested actions
   (an action that spawns sub-actions still draws from the one flat pool) —
   i.e. Bazel doesn't solve this problem, it avoids it by not letting
   actions recurse.
   [HTB](https://en.wikipedia.org/wiki/Token_bucket) ·
   [YARN CapacityScheduler](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/CapacityScheduler.html) ·
   [K8s ResourceQuota](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
7. **The known failure mode, named precisely**: this is "pool starvation
   from nested/blocking tasks," and it has a canonical, verbatim
   documentation warning in **two** unrelated runtimes, which is strong
   convergent evidence it's a structural law, not an implementation bug:
   - **Python `ThreadPoolExecutor`** (official docs, current): *"Deadlocks
     can occur when the callable associated with a Future waits on the
     results of another Future."* Worked example: `max_workers=1`,
     a task submits another task to the same executor and calls
     `.result()` on it — "This will never complete because there is only
     one worker thread and it is executing this function." This is the
     exact shape of a sub-orchestrator occupying its own concurrency slot
     while waiting on children drawn from the same pool.
   - **Java `ForkJoinPool`**: tasks are advised **not** to block; if they
     must, they should go through `ForkJoinPool.managedBlock()` with a
     `ManagedBlocker`, which "arranges for a spare thread to be activated...
     to ensure sufficient parallelism while the current thread is blocked."
     The Javadoc is explicit that **"no such adjustments are guaranteed in
     the face of blocked I/O or other unmanaged synchronization"** —
     i.e. block without going through the managed-blocking API and the pool
     can starve exactly like Airflow's SubDAG.
   - **Standard fix, converging across all three (Airflow, ForkJoinPool,
     ThreadPoolExecutor):** either (a) run the blocking coordinator in a
     **separate pool** from the leaves it waits on (Airflow's real fix via
     TaskGroup removing pool occupancy entirely; a `newFixedThreadPool`
     dedicated to coordinators only), or (b) **don't count the blocked
     party against the cap at all** and instead activate a spare
     slot/thread while it waits (`ManagedBlocker`'s exact mechanism). There
     is no precedent anywhere for "let the blocked coordinator keep
     occupying a shared leaf-worker slot" as a working design — every
     source treats that as the bug.
     [ForkJoinPool Javadoc](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/concurrent/ForkJoinPool.html) ·
     [Python concurrent.futures](https://docs.python.org/3/library/concurrent.futures.html)

**Part B — run telemetry**

8. **OTel GenAI semantic conventions** (`open-telemetry/semantic-conventions-genai`,
   current attribute registry, fetched 2026-09-05) — the namespace is
   explicitly marked **maturity level "Development"**, i.e. still expected
   to change. Names that matter for hex: `gen_ai.operation.name`,
   `gen_ai.provider.name`, `gen_ai.agent.name`/`gen_ai.agent.id`,
   `gen_ai.request.model`, `gen_ai.response.model`,
   `gen_ai.usage.input_tokens`/`gen_ai.usage.output_tokens`,
   `gen_ai.usage.cache_read.input_tokens`, `gen_ai.tool.name`,
   `gen_ai.conversation.id`. These are adoptable as **field names in hex's
   own JSONL** right now without adopting OTel wire format or an SDK
   dependency — get the naming convention for free, stay unblocked on the
   spec's instability.
   [OTel GenAI attribute registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
9. **Structural answer to "which phase got slower in one pass"**: every
   build-observability format that answers this well shares the same shape
   — a flat sequence of **timestamped, named, start/end events**, each
   carrying a stable id and a duration, so a diff between two runs is a
   join on event name, not a parse of prose. Bazel's Build Event Protocol
   is literally a DAG of such events (`BuildEvent` = id + children +
   payload, root `BuildStarted` → leaf timing/metrics events, "not all
   parent events... must necessarily be posted before" a child — supports
   concurrent posting). Cargo's `--timings` records per-compilation-unit
   duration + codegen time + "which units became unblocked when this one
   finished," rendered as a Gantt-style unit graph plus a summary table
   that's directly diffable run-to-run. Chrome's Trace Event Format
   (consumed by `chrome://tracing`, and used by build tools that emit
   `-t trace`-style output) is the same idea at the OS-tracing layer: each
   event carries `name`, `ph` (phase: begin/end/instant), `ts`, `pid`/`tid`,
   and free-form `args` — the phase+timestamp pair is what makes "which
   span got longer" a query, not an investigation.
   [Bazel BEP](https://bazel.build/remote/bep) ·
   [Cargo timings](https://doc.rust-lang.org/cargo/reference/timings.html)
10. **JSONL as a telemetry substrate — the durability caveat has a hard
    number.** POSIX guarantees writes below `PIPE_BUF` are atomic — "the
    output data is written... as a contiguous sequence"; writes **above**
    `PIPE_BUF` "may be nonatomic: the kernel may interleave the data with
    data written by other processes." `PIPE_BUF` is at least 512 bytes
    under POSIX.1 and **4096 bytes on Linux**. Practical rule: **keep each
    JSONL telemetry line under 4096 bytes** and open the file with
    `O_APPEND`, and concurrent multi-process appends need no external lock;
    go over that and two concurrent sub-orchestrators writing to the same
    run log can corrupt each other's lines. This directly matters once
    per-WP sub-orchestration means N processes append to one run log
    concurrently instead of one orchestrator writing serially.
    [pipe(7)](https://man7.org/linux/man-pages/man7/pipe.7.html)
11. **Dual-write (human log + machine log) — precedent says "render, don't
    duplicate," not "write both by hand."** No source found recommends
    maintaining two independently-authored logs in parallel; every
    precedent that ships a human view alongside a machine one derives the
    human view **from** the structured record after the fact (Cargo's HTML
    timing report is generated from its own recorded unit-timing data,
    never hand-narrated; systemd's journal is a single binary structured
    store with `journalctl` rendering the human text on demand — nothing
    writes prose to disk independently of the structured entry). The
    anti-pattern is specifically writing prose and structured data as two
    separate write paths that can drift; the safe pattern is one
    structured write, one renderer.
12. **What to measure — queue/wait time vs. work time is the field
    everyone skips and the one that would have caught hex's own regression.**
    hex's own RCA (`rca-review-fix-loop-wall-clock.md`) already demonstrates
    this empirically without needing an external citation: of the 3h06 WP-1
    trace, roughly **69 of ~186 minutes (≈37%) was the WP sitting idle**
    while the single orchestrator was busy elsewhere — a number only
    reconstructible after the fact from spawn-log timestamps, because
    nothing recorded "waiting for a scheduling slot" as its own event.
    That is precisely the queue-time-vs-work-time split that Lean/Kanban
    flow-efficiency literature and build-observability tools (Bazel's BEP,
    Cargo's "which units became unblocked when this one finished") treat as
    a first-class field, and which naive activity logs (start/end of the
    *work* only) omit by construction. The minimum measurable set for this
    domain: total wall, per-WP wall, per-phase wall, `queue_wait_ms` vs.
    `work_ms` per phase, model class per phase, review rounds, retries. Of
    these, `queue_wait_ms` is the one most often missing and most often
    decisive — it's exactly the field whose absence forced the RCA to be a
    manual timestamp-table reconstruction instead of a one-query answer.
    [`rca-review-fix-loop-wall-clock.md`](/home/mherwig/dev/arcana/.agents/research/rca-review-fix-loop-wall-clock.md)

## Recommendation

**Adopt one sub-orchestrator per ready WP**, keeping hex's existing
orchestrator→coordinator→leaf depth as the hard cap (findings 1, 5, 6 all
independently converge on "shallow and hard-capped," and hex already enforces
this uniquely as a spec-level invariant, not a harness default like Claude
Code's own shifting 3-layer cap).

**Concurrency-budget allocation policy: hierarchical fair-share with
borrowing, HTB/YARN-shaped, not a shared blocking pool.** Give each active
sub-orchestrator a guaranteed floor of resolve to at least 1 concurrent leaf
worker; let it borrow up to the remaining unused ceiling from sibling
sub-orchestrators that are between phases or already converged. This is
strictly better than (a) Kubernetes `ResourceQuota`'s first-come-first-served
(starves late arrivals under load) and (b) a flat shared semaphore all
sub-orchestrators and their leaves draw from indiscriminately (reproduces the
Airflow SubDAG deadlock, finding 3, and the Python `ThreadPoolExecutor`
nested-submit deadlock, finding 7, verbatim). Concretely: keep hex's existing
schedule-time reservation ("hand each coordinator a fan-out budget no larger
than its slot's share") — that's already the HTB shape — and make explicit
that this is a **static partition decided once per wave**, never a runtime
semaphore a coordinator and its own leaves contend over.

**The blocked parent should NOT count against the cap.** A sub-orchestrator
that is merely waiting on its own children is doing no compute — charging it
a slot is the exact mechanism of the Airflow deadlock and the textbook
`ThreadPoolExecutor` nested-submit deadlock (finding 7). Claude Code's own
subagent model agrees: the parent conversation does not block, and background
subagents don't hold the parent's turn hostage (finding 5). Only count
actively-running leaf/coordinator **compute** (a live model call) against the
cap; a sub-orchestrator between phases, or blocked purely on `await`, is
free. This also matches Temporal's `ParentClosePolicy` framing — a waiting
parent and a running child are different resource classes and should never
share one budget line.

**Telemetry: one JSONL line per phase start/end, appended, under 4096 bytes,
with an explicit queue/work split.** Concretely, per phase-transition event:

```
{ts, run_id, wp_id, phase, event: "start"|"end",
 gen_ai.operation.name, gen_ai.request.model, model_class,
 tokens_in, tokens_out,
 queue_wait_ms, work_ms,
 review_round, retries, outcome}
```

Rationale: field names borrow the `gen_ai.*` convention (finding 8) so a
future migration to real OTel GenAI spans is a rename, not a redesign, while
not taking on OTel's "Development"-status instability today. One line per
event (not one line per WP) keeps each line well under `PIPE_BUF` (finding
10), so N concurrent sub-orchestrators can append to one shared run log with
zero locking and zero interleaving corruption — a requirement this design
newly introduces that the current single-orchestrator model never had.
`queue_wait_ms` is the field to add that doesn't exist today (finding 12) —
without it, the next regression is again a manual spawn-log archaeology
project like the RCA that motivated this research. Render the human-readable
run summary **from** this JSONL after the fact (finding 11); never
hand-maintain a second narrative log that can drift from it.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| [erlang.org — Supervision Principles](https://www.erlang.org/doc/system/sup_princ.html) | Docs | evergreen | OTP restart-intensity-compounds-across-levels warning |
| [Temporal — Child Workflows](https://docs.temporal.io/child-workflows) | Docs | current 2026 | "When in doubt, use an Activity"; ~1,000-child soft limit |
| [Temporal — Parent Close Policy](https://docs.temporal.io/parent-close-policy) | Docs | current 2026 | Abandon/RequestCancel/Terminate options |
| [Airflow — SubDagOperator (deprecated)](https://airflow.apache.org/docs/apache-airflow/2.5.3/_api/airflow/operators/subdag/index.html) | Docs | deprecated ~2020, still current guidance | Deprecation pointer to TaskGroup |
| [Fixing SubDagOperator Deadlock in Airflow](https://medium.com/@team_24989/fixing-subdagoperator-deadlock-in-airflow-6c64312ebb10) | Blog | undated, describes 2.x-era behavior | Verbatim deadlock mechanism |
| [K8s v1.34 — Indexed Jobs / Pod Replacement Policy GA](https://v1-34.docs.kubernetes.io/blog/2025/09/05/kubernetes-v1-34-pod-replacement-policy-for-jobs-goes-ga) | Docs/blog | 2025-09 | Indexed Jobs, no parent-blocks-on-child shape |
| [K8s v1.29 — CronJobs](https://v1-29.docs.kubernetes.io/docs/concepts/workloads/controllers/cron-jobs) | Docs | 2023-era, stable feature | `concurrencyPolicy` semantics |
| [Kubernetes — ResourceQuota](https://kubernetes.io/docs/concepts/policy/resource-quotas/) | Docs | current | First-come-first-served contention — the naive policy to avoid |
| [Nomad — group spec](https://developer.hashicorp.com/nomad/docs/job-specification/group) | Docs | current | job→group→task is co-location, not delegation |
| [Dagster — Dynamic graphs](https://docs.dagster.io/guides/build/ops/dynamic-graphs) | Docs | current | Runtime fan-out without a blocking supervisor op |
| [Argo Workflows — Enhanced Depends Logic](https://argo-workflows.readthedocs.io/en/latest/enhanced-depends-logic/) | Docs | current | Result-conditioned DAG edges, pure dataflow gating |
| [CrewAI — Hierarchical Process](https://docs.crewai.com/en/learn/hierarchical-process) | Docs | current 2026 | Manager LLM, delegation off by default, `max_iterations` |
| [OpenAI Agents SDK — Agent orchestration](https://openai.github.io/openai-agents-python/multi_agent/) | Docs | current | Handoff vs. manager/agents-as-tools, non-interchangeable |
| [Anthropic — Building a multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) | Blog/eng post | 2025-06 (~15 mo old — flag: approaching staleness window) | 15x token cost, compounding cost of recursive subagents, coding named a poor fit |
| [code.claude.com — Sub-agents](https://code.claude.com/docs/en/sub-agents) | Official docs | fetched 2026-09-05 | Depth-3 default nesting cap, non-blocking parent, background execution |
| [Claude Code nested sub-agents changelog analysis](https://readysolutions.ai/blog/2026-06-11-claude-code-nested-subagents/) | Blog (secondary) | 2026-06 | Corroborates cap churn (5→disabled→3) within 3 months |
| [Wikipedia — Token bucket / HTB](https://en.wikipedia.org/wiki/Token_bucket) | Reference | evergreen mechanism | `rate`/`ceil` borrowing-from-parent allocation policy |
| [Hadoop — YARN CapacityScheduler](https://hadoop.apache.org/docs/stable/hadoop-yarn/hadoop-yarn-site/CapacityScheduler.html) | Docs | current | `capacity`/`maximum-capacity`/elasticity, hierarchical queues |
| [Oracle — ForkJoinPool Javadoc (JDK 21)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/concurrent/ForkJoinPool.html) | Docs | current | `ManagedBlocker`, no progress guarantee for unmanaged blocking |
| [Python — concurrent.futures](https://docs.python.org/3/library/concurrent.futures.html) | Docs | current | Verbatim `ThreadPoolExecutor` nested-submit deadlock example |
| [OpenTelemetry — GenAI attribute registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/) | Spec | fetched 2026-09-05, "Development" maturity | `gen_ai.*` field-naming convention |
| [Bazel — Build Event Protocol](https://bazel.build/remote/bep) | Docs | current | Event-graph shape for phase-timing diagnosis |
| [Cargo — `--timings`](https://doc.rust-lang.org/cargo/reference/timings.html) | Docs | current | Per-unit duration + unblocked-by graph, diffable summary table |
| [man7.org — pipe(7)](https://man7.org/linux/man-pages/man7/pipe.7.html) | Man page | evergreen (POSIX) | `PIPE_BUF` = 4096 on Linux; atomicity boundary for concurrent appends |
| [`rca-review-fix-loop-wall-clock.md`](/home/mherwig/dev/arcana/.agents/research/rca-review-fix-loop-wall-clock.md) | Internal | 2026-09-05 | Empirical queue-time evidence (WP-1 idle ~69 of 186 min) motivating this research |
| [`hierarchical-orchestration-precedent.md`](/home/mherwig/dev/arcana/.agents/research/hierarchical-orchestration-precedent.md) | Internal | 2026-07-19 | Prior pass — depth caps, review-hierarchy precedent (not repeated here) |
| [`hierarchical-execution-performance.md`](/home/mherwig/dev/arcana/.agents/research/hierarchical-execution-performance.md) | Internal | 2026-07-19 | Prior pass — coordination-cost scaling laws, granularity thresholds (not repeated here) |
| [`protocol.md` § Worker coordination](/home/mherwig/dev/arcana/hex/hex-core/references/protocol.md) | Internal | current | hex's existing recursive-cap + fan-out-budget mechanism this research extends |
