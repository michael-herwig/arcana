# Research: Liveness / heartbeat protocol precedent for long-running distributed tasks

<!--
Technology-landscape research, hex research template. Owner: researcher
worker (ecosystem lane). Handoff to: /hex-architect (worker-liveness
contract ADR: heartbeat JSON schema, state enum, cadence rule, escalation
ladder).
Findings decay — check Expires before trusting them.
-->

## Metadata

**Date:** 2026-09-05
**Domain:** devops | observability | ci-cd
**Triggered by:** hex worker-liveness contract design — each agent writes a
small JSON heartbeat file, an orchestrator decides when a worker is dead.
Deepens item 10 of [parallel-resource-pitfalls.md](parallel-resource-pitfalls.md)
("No surveyed AI coding-agent platform publishes a liveness/heartbeat
protocol for its parallel fleet; Temporal, MCP progress notifications, and
A2A `TaskStatusUpdateEvent` do").
**Expires:** 2027-03-05

## Direct Answer

Every mature liveness protocol surveyed separates **two independent signals**
— "the process/session still exists" (a pulse) and "the work is still moving"
(a delta) — and escalates on a ladder, not a single threshold. Copy the shape
from Kafka's KIP-62 split (`session.timeout.ms` heartbeat thread vs
`max.poll.interval.ms` processing deadline), the field set from Temporal's
`RecordHeartbeat` + `heartbeat_details`, the state enum from A2A's
`TaskState`, the "I need longer" primitive from systemd's
`EXTEND_TIMEOUT_USEC=`, and the graduated-timeout structure from Kubernetes'
three-probe model. No surveyed AI-agent orchestration platform (Claude Code,
Cursor, Devin, Copilot agent) publishes a written heartbeat contract for its
own parallel fleet — hex would be filling a real gap, not reinventing one.

A monotonic sequence number in the heartbeat payload **is worth carrying**,
but as a torn-write guard and stale-writer guard, not as the primary
liveness signal — see the closing section.

## Technology Landscape

### Trending (gaining momentum)

| Tool/Pattern | Adoption Signal | Key Benefit | Relevance |
|--------------|------------------|-------------|-----------|
| A2A `TaskState` + SSE `TaskStatusUpdateEvent` | Google-seeded, now Linux Foundation project (a2a-protocol.org), rapid v0.2→v1.0 churn in 2025-2026 | A vendor-neutral state enum for exactly hex's problem (agent task lifecycle) | Direct precedent for hex's worker-status enum |
| MCP `notifications/progress` | Shipped in the 2025-03-26 spec, now default transport for agent tool calls across Claude, OpenAI, and others | Minimal, transport-agnostic progress signal with a monotonicity rule | Direct precedent for a hex heartbeat's `progress` field |

### Established (proven, widely accepted)

| Tool/Pattern | Status | Notes |
|--------------|--------|-------|
| Temporal Activity Heartbeats | Production standard since 2019 | `RecordHeartbeat` + `heartbeat_details` is the most complete prior art for "resume from checkpoint on retry" |
| systemd watchdog (`sd_notify`) | Standard on every systemd Linux distro since ~2012 | `WATCHDOG=1` / `WatchdogSec=` / `EXTEND_TIMEOUT_USEC=` is the closest primitive to a worker declaring "I need more time, here is my new deadline" |
| Kubernetes liveness/readiness/startup probes | Standard since Kubernetes 1.16 (startup probe GA) | Three-probe model is the standard reference for graduated timeout budgets |
| Kafka consumer heartbeat split (KIP-62) | Standard since Kafka 0.10.1 (2016) | Textbook precedent for pulse vs delta as two independently-tuned timeouts |
| Erlang/OTP supervisor `intensity`/`period` | Standard since OTP's inception, unchanged in OTP 29 (2026) | Escalation-ladder precedent: too many restarts too fast → stop restarting, propagate the failure up |

### Emerging (early but promising)

| Tool/Pattern | Signal | Worth Watching Because |
|--------------|--------|-------------------------|
| A2A `TaskState.PAUSED` proposal | Open GitHub discussion ([a2aproject/A2A#1858](https://github.com/a2aproject/A2A/discussions/1858)) | Distinguishes a caller-initiated "warm pause" from `INPUT_REQUIRED`/`AUTH_REQUIRED` (both currently mean "blocked, waiting on someone else") — relevant if hex ever needs a worker to self-report "idle by design" vs "blocked" |
| Fencing tokens for lease-based coordination | Long-standing pattern (Kleppmann, 2016), still the reference answer for distributed-lock GC-pause hazards | If two orchestrator instances ever race to declare the same worker dead, a fencing token — not just a timestamp — is what prevents a split-brain kill |

### Declining (losing mindshare)

| Tool/Pattern | Signal | Avoid Because |
|--------------|--------|-----------------|
| Single fixed timeout for both liveness and progress (pre-KIP-62 Kafka, pre-A2A ad hoc polling) | Kafka's own KIP documents users "faced an impossible choice: increase the timeout to allow processing... or reduce it... risking group removal during normal operations" | Forces every long task into either false-positive kills or slow crash detection; every protocol surveyed since 2016 has split the two concerns |

## Design Patterns Worth Considering

- **Pulse vs delta, always two knobs.** A background thread/process can keep
  beating while the actual work thread is deadlocked — Kafka hit this
  directly and KIP-62 exists because of it (see Key Finding 6). A heartbeat
  file's freshness alone (pulse) cannot prove the worker isn't stuck; it
  needs a second field that only advances when real work happens (delta).
- **Declare the next deadline, don't just report the last beat.** systemd's
  `EXTEND_TIMEOUT_USEC=` lets a service say "I know I'm about to do something
  slow, extend my deadline to X" *before* it goes quiet — this is a better
  fit for an agent about to enter a known-long tool call than a fixed
  interval. Used by: systemd services declaring extended startup/shutdown
  windows ([sd_notify(3)](https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html)).
- **Graduated timeout budgets, not one budget.** Kubernetes' startup probe
  exists because a container's cold-start budget and its steady-state
  deadlock-detection budget are different numbers, and conflating them
  either kills slow-starting containers or makes steady-state detection too
  slow ([Kubernetes probes](https://kubernetes.io/docs/concepts/workloads/pods/probes/)).
  Maps directly onto a "spawn/startup phase gets its own grace window"
  rule.
- **Checkpoint payload rides on the heartbeat, not a separate channel.**
  Temporal's `heartbeat_details` is returned to the *retried* activity
  automatically — the heartbeat *is* the checkpoint transport, no separate
  state store needed ([Temporal: detecting activity failures](https://docs.temporal.io/encyclopedia/detecting-activity-failures)).
- **Escalate by count-and-window, not by count alone.** OTP's
  `intensity`/`period` pair (default 1 restart per 5 seconds) means a
  supervisor tolerates occasional failures forever but gives up fast on a
  crash loop — count without a window either restarts forever or gives up
  on a single blip ([Erlang supervisor docs](https://www.erlang.org/doc/system/sup_princ.html)).
- **The liveness store should itself be atomically-written, or the reader
  must assume torn writes.** Kubernetes sidesteps the problem entirely by
  making the "file" an etcd-backed `Lease` object updated via a single
  atomic RPC ([Kubernetes node heartbeats](https://kubernetes.io/docs/concepts/architecture/leases/)).
  hex's plain-JSON-file design does not get that for free — see the
  sequence-number analysis below.

## Key Findings

1. **Temporal `RecordHeartbeat`/`heartbeat_details`**: "A Heartbeat can
   include an application layer payload that can be used to *save* Activity
   Execution progress. If an [Activity Task Execution] times out due to a
   missed Heartbeat, the next Activity Task can access and continue with
   that payload." On heartbeat timeout: "the Activity Task fails and a retry
   occurs if a [Retry Policy] dictates it" — the checkpoint is what makes
   that retry resumable rather than a restart from zero.
   [docs.temporal.io/encyclopedia/detecting-activity-failures](https://docs.temporal.io/encyclopedia/detecting-activity-failures)
2. **Temporal's actual "fraction of timeout" number is a throttle, not a
   cadence recommendation, and it is 0.8× not 2/3×**: "The throttle interval
   is the smaller of the following: If `heartbeatTimeout` is provided,
   `heartbeatTimeout * 0.8`; otherwise, `defaultHeartbeatThrottleInterval`"
   (30s default, 60s max). Application code may call `RecordHeartbeat` every
   loop iteration — the SDK, not the app, rate-limits the outbound RPC. No
   Temporal doc page states a "2/3 of timeout" rule explicitly; that framing
   is a community convention, not a spec number.
   [docs.temporal.io/encyclopedia/detecting-activity-failures](https://docs.temporal.io/encyclopedia/detecting-activity-failures)
3. **`HeartbeatTimeout` vs `StartToCloseTimeout`**: StartToCloseTimeout is
   "the maximum time allowed for a single Activity Task Execution";
   HeartbeatTimeout instead fires when "the Temporal Service does not
   receive a Heartbeat within a Heartbeat Timeout time period" — the former
   bounds total wall-clock, the latter bounds *silence*, and Temporal
   recommends setting both for long-running activities.
   [docs.temporal.io/develop/go/activities/timeouts](https://docs.temporal.io/develop/go/activities/timeouts)
4. **A2A `TaskState` enum, two eras**: the pre-1.0 JSON-RPC spec used
   lowercase-hyphenated string values — `submitted`, `working`,
   `input-required`, `completed`, `canceled`, `failed`, `rejected`,
   `auth-required`, `unknown` — grouped into Running (`submitted`,
   `working`), Paused (`input-required`, `auth-required`), and Finished
   (`completed`, `failed`, `canceled`, `rejected`). The v1.0 protobuf-based
   spec renamed these to SCREAMING_SNAKE_CASE with a prefix:
   `TASK_STATE_SUBMITTED`, `TASK_STATE_WORKING`, `TASK_STATE_INPUT_REQUIRED`,
   `TASK_STATE_COMPLETED`, `TASK_STATE_FAILED`, `TASK_STATE_CANCELED`,
   `TASK_STATE_REJECTED`, `TASK_STATE_AUTH_REQUIRED`,
   `TASK_STATE_UNSPECIFIED`. A `PAUSED` state (caller-initiated, distinct
   from input/auth blocking) is under discussion, not yet shipped.
   [a2a-protocol.org/latest/specification](https://a2a-protocol.org/latest/specification/),
   [a2aproject/A2A#1858](https://github.com/a2aproject/A2A/discussions/1858)
5. **`TaskStatusUpdateEvent` shape and `final`**: the event carries
   `taskId`, `contextId`, a `status` object (state + message + timestamp),
   and a `final` boolean; "The stream MUST close when the task reaches a
   terminal state (`TASK_STATE_COMPLETED`, `TASK_STATE_FAILED`,
   `TASK_STATE_CANCELED`, `TASK_STATE_REJECTED`)." The spec does **not**
   prescribe a stall-detection timeout — it names three detection
   mechanisms (poll `GetTask`, subscribe to the SSE stream, or receive a
   push-notification webhook) and leaves the staleness threshold to the
   client's own timestamp comparison.
   [a2a-protocol.org/latest/specification](https://a2a-protocol.org/latest/specification/)
6. **MCP progress is monotonic by rule, and MCP defines no liveness/timeout
   semantics at all.** "The `progress` value MUST increase with each
   notification, even if the total is unknown," and separately "Progress
   notifications MUST stop after completion" — but the spec never says how
   long a receiver should wait before treating silence as failure; that is
   left entirely to the implementation. The full notification is
   `{"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"abc123","progress":50,"total":100,"message":"Reticulating splines..."}}`.
   [modelcontextprotocol.io/specification/.../progress](https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress)
7. **systemd's half-interval rule is explicit and quotable**: "It is
   recommended that a daemon sends a keep-alive notification message to the
   service manager every half of the time returned here" (i.e., every half
   of `WATCHDOG_USEC`). `WATCHDOG=1` "is the keep-alive ping that services
   need to issue in regular intervals if `WatchdogSec=` is enabled."
   `STATUS=` "passes a single-line UTF-8 status string back to the service
   manager... fsck-like programs could pass completion percentages."
   `EXTEND_TIMEOUT_USEC=` "tells the service manager to extend the startup,
   runtime or shutdown service timeout... the service must send a new
   message" within that window "until the service startup status is
   finished by `READY=1`" — this is the literal "I will take longer, here is
   my new deadline" primitive the design question named.
   [sd_notify(3)](https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html),
   [sd_watchdog_enabled(3)](https://www.man7.org/linux/man-pages/man3/sd_watchdog_enabled.3.html)
8. **Kubernetes startup probe exists precisely to avoid conflating cold-start
   budget with steady-state deadlock detection**: "Rather than set a long
   liveness interval, you can configure a separate configuration for
   probing the container as it starts up, allowing a time longer than the
   liveness interval would allow... If your container usually starts in
   more than `initialDelaySeconds + failureThreshold × periodSeconds`, you
   should specify a startup probe." Once the startup probe passes once, it
   is never run again — liveness takes over for the rest of the container's
   life.
   [kubernetes.io/.../probes](https://kubernetes.io/docs/concepts/workloads/pods/probes/)
9. **KIP-62 is the cleanest documented pulse/delta split**, and it exists
   *because* of the anti-pattern the design question worries about: "the
   current approach puts all classes of consumer failures into the same
   bucket by trying to govern them all with the same timeout value." The
   fix: "a separate locally enforced timeout for record processing and a
   background thread to keep the session active until this timeout
   expires" — `session.timeout.ms` (heartbeat thread, detects a truly dead
   process) decoupled from `max.poll.interval.ms` (processing thread,
   detects a hung/stuck one). Before this, teams "faced an impossible
   choice: increase the timeout to allow processing... or reduce it...
   risking group removal during normal operations."
   [KIP-62](https://cwiki.apache.org/confluence/display/KAFKA/KIP-62:+Allow+consumer+to+send+heartbeats+from+a+background+thread)
10. **Hadoop/YARN and Spark speculative execution are progress-delta
    consumers, not pulse consumers** — they run entirely on the *rate* of
    the progress score (0.0–1.0 per task), not on whether the task process
    is merely alive: "the task estimated execution time equals the
    difference between the current time and the time at which the task is
    launched, divided by the reported progress score," and a straggler is a
    task whose progress rate is anomalously slow relative to its peers, not
    one that stopped reporting. Spark's `spark.speculation` re-launches a
    duplicate of that straggler on a different node and takes whichever
    copy finishes first. This is the precedent for "progress rate, not just
    presence, drives escalation."
    [Spark speculative execution internals](https://books.japila.pl/apache-spark-internals/speculative-execution-of-tasks/)
11. **Escalation ladders converge on count-within-a-window, then stop and
    surface.** OTP: "If more than `MaxR` restarts occur within `MaxT`
    seconds... the supervisor terminates all child processes and then
    itself" (defaults `MaxR=1`, `MaxT=5`) — deliberately tight enough that
    "setting intensity to 10 and period as low as 1 will allow child
    processes to keep restarting up to 10 times per second, forever, filling
    your logs." Nomad's `restart` stanza retries `attempts` times within an
    `interval`, then either keeps trying on the same node or (recommended,
    `mode = "fail"`) fails the task so the scheduler reschedules it
    elsewhere. Kubernetes Jobs use `backoffLimit` (default 6) counted across
    Pod failures. Temporal's `RetryPolicy` uses `maximumAttempts` with
    exponential `backoffCoefficient` (default 2) capped by
    `maximumInterval`. None of these differ in kind from a "3 strikes, then
    page a human" ladder — they differ only in whether the final action is
    "give up" (OTP, Temporal after `maximumAttempts`), "reschedule elsewhere"
    (Nomad, K8s), or both in sequence.
    [Erlang supervisor](https://www.erlang.org/doc/system/sup_princ.html),
    [Nomad restart](https://developer.hashicorp.com/nomad/docs/job-declare/failure/restart),
    [Kubernetes backoffLimit](https://www.baeldung.com/ops/kubernetes-backofflimit),
    [Temporal retry policy](https://docs.temporal.io/develop/activity-retry-simulator)
12. **Fencing tokens are the documented fix for "killed a worker that was
    merely slow," i.e. the split-brain hazard the design question names
    explicitly.** Kleppmann's canonical example: a lock/lease service hands
    out a monotonically increasing token on every grant; if a paused client
    resumes and writes with an old token after a new client has already
    acquired a higher one, "the storage server remembers that it has
    already processed a write with a higher token number... and so it
    rejects the request with the [stale] token" — the fix is enforced by the
    *resource being protected*, not by trusting the lock holder's own
    liveness judgment about itself.
    [martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
13. **Kubernetes sidesteps the heartbeat-file torn-write problem entirely by
    not using a file**: "every kubelet heartbeat is an update request to
    this `Lease` object, updating the `spec.renewTime` field... The
    Kubernetes control plane uses the time stamp of this field to determine
    the availability of this Node." The update is a single atomic etcd
    write; there is no reader-sees-half-written-JSON case because the
    storage layer guarantees atomicity. A plain-file heartbeat design (hex's
    case) does not inherit this guarantee for free.
    [kubernetes.io/.../leases](https://kubernetes.io/docs/concepts/architecture/leases/)
14. **No surveyed AI-agent orchestration platform documents a heartbeat
    contract for its own parallel worker fleet** — this remains true after
    the deeper pass; A2A, MCP, and Temporal are all *general* protocols
    hex can borrow from, not examples of another coding-agent orchestrator
    having already solved this. Confirms and extends
    parallel-resource-pitfalls.md Key Finding 10.

## Recommendation

**Adopt a two-signal heartbeat file, an A2A-shaped state enum, a
half-of-timeout cadence rule with an explicit extend primitive, and a
count-within-window escalation ladder that ends in "stop retrying, surface
to the human."**

**Field set** (JSON, one file per worker, write-temp-then-rename):

```json
{
  "seq": 42,
  "ts": "2026-09-05T14:32:07Z",
  "state": "working",
  "progress": { "value": 12, "total": 40, "message": "wp-3: running tests" },
  "expect_next_s": 90,
  "detail": null
}
```

- `ts` + `seq` — the pulse. `ts` is what a human reads; `seq` is what the
  orchestrator trusts (see below). Precedent: every protocol surveyed keeps
  a raw timestamp (systemd `WATCHDOG_USEC`, K8s `renewTime`), but only
  MCP/Temporal-style progress protocols and fencing-token designs add a
  counter, because a clock alone can't detect a torn or replayed write.
- `state` — an A2A-shaped enum, trimmed to what an orchestrator actually
  branches on: `spawning | working | blocked | finishing | done | failed`.
  `blocked` covers A2A's `input-required`/`auth-required` (worker is alive
  but waiting on someone else — do not kill it); `failed` is terminal like
  A2A's `failed`/`rejected`. This is a direct, deliberately-shrunk borrow
  from A2A's `TaskState` (Key Finding 4).
- `progress` — the delta signal, MCP-shaped (`progress`/`total`/`message`,
  monotonic `progress`). This is what makes `state: working` trustworthy —
  without it, a heartbeat only proves the writer process exists, not that
  it's making progress (Key Finding 6, 9, 10).
- `expect_next_s` — the systemd `EXTEND_TIMEOUT_USEC=` borrow: the worker
  declares its *own* next deadline before starting a known-long step
  (e.g. `heavy` build/test), rather than the orchestrator guessing one
  global timeout for every worker (Key Finding 7). Absent → orchestrator
  falls back to the profile default from `resources.md`.
- `detail` — free text, systemd `STATUS=`-shaped, for the last error or
  what the worker is blocked on; null when nothing to say.

**State enum:** `spawning | working | blocked | finishing | done | failed` —
`spawning` gets its own grace window (Kubernetes startup-probe borrow, Key
Finding 8: cold start and steady-state deadlock detection are different
budgets and must not share a timeout).

**Cadence rule:**
- Worker writes a heartbeat at **half of its current deadline**
  (`expect_next_s / 2`, systemd's exact rule, Key Finding 7), never less
  often than every 30s of active work.
- Orchestrator does **not** kill on a single missed beat. It applies two
  independent tests, matching KIP-62 (Key Finding 9):
  - **Pulse test**: `now - ts > 2 × expect_next_s` (or the profile default)
    → the process itself may be gone.
  - **Delta test**: `progress.value` unchanged across ≥ 3 consecutive
    heartbeats while `state == working` → the process is alive but stuck
    (Kafka's exact failure mode: a background thread beating while the work
    thread deadlocks).
  Either test failing moves the worker to `suspect`, not immediately dead —
  mirroring Kubernetes' `failureThreshold` (consecutive failures, not one)
  and avoiding the clock-skew/GC-pause false positive the design question
  flags.

**Escalation ladder** (count-within-window, Key Finding 11, terminating in
a human page, not an infinite retry):
1. **Suspect** (pulse or delta test fails once) → orchestrator polls/pings,
   no kill.
2. **Confirmed stalled** (fails again after one grace cycle) → soft
   reclaim: cancel and retry the work package on a fresh worker, carrying
   forward the last `progress`/checkpoint payload the same way Temporal's
   `heartbeat_details` rides the retry (Key Finding 1).
3. **Repeat failure within a window** (OTP-shaped: e.g. 3 stalls in one
   plan run, not 3 stalls ever) → stop auto-retrying that work package,
   mark it `failed`, continue the rest of the plan.
4. **Escalation exhausted** → surface to the human as a plan-blocking
   finding; never silently drop the work package. This is the point every
   ladder surveyed converges on — OTP's supervisor giving up and
   propagating, Temporal's `maximumAttempts`, Nomad/K8s's
   `backoffLimit`/reschedule-then-fail — "stop retrying and tell someone" is
   the universal terminal rung, not "retry forever."

**On the sequence-number question — yes, carry it, but as a write-tearing
and stale-writer guard, not as the primary liveness clock.** Three
independent lines of evidence converge:
- Kubernetes avoids the torn-write problem entirely by making the heartbeat
  an atomic etcd RPC (Key Finding 13) — hex's plain-JSON-file design does
  not get that guarantee for free, so it must earn it another way:
  write-temp-then-rename (POSIX rename is atomic on the same filesystem) so
  a reader never observes a half-written file, **and** a `seq` field so a
  reader that *does* somehow observe an old inode (a stale NFS/9P cache,
  the WSL2 cross-filesystem case already flagged in
  parallel-resource-pitfalls.md #25) can detect it went backwards.
- MCP's monotonic-`progress` rule (Key Finding 6) is exactly this
  discipline applied to progress instead of identity — the receiver's
  contract is "reject/ignore anything that doesn't increase."
- Fencing tokens (Key Finding 12) are the field's answer to "a worker I
  already declared dead wakes up and writes again" — without a counter the
  orchestrator has no way to tell a late, stale heartbeat from a fresh one
  if timestamps clock-skew or coincide. `seq` is the cheap, single-writer
  version of a fencing token: monotonic per worker, checked on read,
  costs one integer.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| [docs.temporal.io/encyclopedia/detecting-activity-failures](https://docs.temporal.io/encyclopedia/detecting-activity-failures) | Docs | current | `RecordHeartbeat`, `heartbeat_details`, throttle formula, timeout behavior |
| [docs.temporal.io/develop/go/activities/timeouts](https://docs.temporal.io/develop/go/activities/timeouts) | Docs | current | `HeartbeatTimeout` vs `StartToCloseTimeout` |
| [docs.temporal.io/develop/activity-retry-simulator](https://docs.temporal.io/develop/activity-retry-simulator) | Docs | current | `RetryPolicy`: `maximumAttempts`, `backoffCoefficient`, `maximumInterval` |
| [a2a-protocol.org/latest/specification](https://a2a-protocol.org/latest/specification/) | Spec | 2026 (v1.0 line) | `TaskState` enum (protobuf era), `TaskStatusUpdateEvent`, `final` |
| [github.com/a2aproject/A2A#1858](https://github.com/a2aproject/A2A/discussions/1858) | GitHub discussion | 2026 | proposed `PAUSED` state, pre-1.0 lowercase enum values |
| [modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress](https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress) | Spec | 2025-06-18 | `notifications/progress`, `progressToken`, monotonic rule, no liveness semantics |
| [freedesktop.org/.../sd_notify.html](https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html) | Man page | current | `WATCHDOG=1`, `STATUS=`, `EXTEND_TIMEOUT_USEC=` exact wording |
| [man7.org/.../sd_watchdog_enabled.3.html](https://www.man7.org/linux/man-pages/man3/sd_watchdog_enabled.3.html) | Man page | current | "every half of the time returned here" — the half-interval rule, `WATCHDOG_USEC` |
| [kubernetes.io/.../pods/probes](https://kubernetes.io/docs/concepts/workloads/pods/probes/) | Docs | current | liveness/readiness/startup probe distinction, `failureThreshold` formula |
| [kubernetes.io/.../architecture/leases](https://kubernetes.io/docs/concepts/architecture/leases/) | Docs | current | node heartbeat via atomic `Lease.spec.renewTime` update |
| [cwiki.apache.org KIP-62](https://cwiki.apache.org/confluence/display/KAFKA/KIP-62:+Allow+consumer+to+send+heartbeats+from+a+background+thread) | KIP (design doc) | 2016, still current API | pulse/delta split rationale, exact problem statement quotes |
| [erlang.org/doc/system/sup_princ.html](https://www.erlang.org/doc/system/sup_princ.html) | Docs | OTP 29, 2026 | `intensity`/`period` restart-storm ladder |
| [books.japila.pl Spark speculative execution](https://books.japila.pl/apache-spark-internals/speculative-execution-of-tasks/) | Community reference | rolling (Spark-version-tracked) | progress-rate-driven straggler detection, `spark.speculation` |
| [developer.hashicorp.com/nomad/.../restart](https://developer.hashicorp.com/nomad/docs/job-declare/failure/restart) | Docs | current | `attempts`/`interval`/`mode` restart-then-reschedule ladder |
| [baeldung.com/ops/kubernetes-backofflimit](https://www.baeldung.com/ops/kubernetes-backofflimit) | Blog (technical) | 2025-2026 | Kubernetes Job `backoffLimit` semantics and default |
| [martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) | Blog (canonical/widely cited) | 2016, still the reference | fencing-token concept — **flagged: >18 months old**, but this is the field's unrevised canonical source, still cited by Kubernetes' and etcd's own docs |
| [github.com/hashicorp/memberlist](https://github.com/hashicorp/memberlist) | Docs/repo | current | SWIM basis + Lifeguard extension pointer (incarnation-number refutation mechanism, referenced not quoted verbatim here) |
| `.agents/research/parallel-resource-pitfalls.md` | Internal | 2026-09-05 | prior shallow pass this file deepens (item 10, source links) |

**Age flags**: the Kleppmann fencing-token post (2016) and KIP-62 (2016) are
both far past 18 months, but both are cited *as the still-unrevised
canonical source* for a concept the rest of the industry (Kubernetes leases,
etcd, Kafka's still-shipping API) has not replaced — treat as "established,"
not "stale."
