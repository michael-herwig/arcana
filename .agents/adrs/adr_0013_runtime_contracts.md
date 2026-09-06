# ADR: hex execution runtime contracts — worker liveness, resource limits, per-work-package sub-orchestration, and run telemetry

## Metadata

**Status:** Proposed
**Date:** 2026-09-05
**Citations:** References into `hex/**` name a file and section heading,
never a line number — `hex/**` changes under active execution.
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A (originated in the 2026-09-05 execution-performance RCA follow-up; Wave 1 item 8 of [`.tmp/waves.md`](../../.tmp/waves.md))
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below —
      **seven proposed `DESIGN.md` amendments** (numbered 1–8; **amendment 1
      was withdrawn in review** and its number is kept dead so the rest stay
      stable), each with a stated boundary, in
      [Constitution deviations](#constitution-deviations--designmd-amendments).
      **Live: 2, 3, 4, 5, 6, 7, 8. Withdrawn: 1.** Amendment **2** amends
      `adr_0010` driver 5 and `C-914`'s "no per-coordinator state" clause;
      **3** amends `protocol.md`'s recursive concurrency count; **4** splits
      the coordinator gate; **5** adds one reference file to the bundle's
      artifact set; and **6, 7 and 8** — added in the 2026-09-05 fix round —
      retarget the behavioural riders the word "coordinator" carries today
      (`protocol.md` § Worktree work-package mechanics and § Checkpoints, which
      **changes `adr_0010` `C-901`'s firing condition**;
      `hex-execute/SKILL.md` § Coordinator spawn; `models.md` § The matrix and
      § Rules).
**Domain Tags:** infrastructure, devops
**Supersedes:** N/A
**Superseded By:** N/A

*Template slots deliberately omitted: **Related PRD** (none exists),
**Technical Details › Data Model** as a standalone section (the two durable
objects are one plan-section line kind and one config leaf; the two ephemeral
objects are given as file grammars in § Technical Details), and
**Implementation Plan** as a standalone checklist (it is § Migration /
rollout plan's wave order, and a second copy would drift).*

## Context

`adr_0010` bounded how much hex **verifies and reviews**. It did not touch
how hex **runs**, and the run is now the cost.

[`rca-review-fix-loop-wall-clock.md`](../research/rca-review-fix-loop-wall-clock.md)
traced one work package end to end: `ocx-sion`, plan
`plan_index_claim_command.md`, WP-1 "exit code 86" — **2 files, +78/−3** —
spawned 01:33 UTC, committed 04:39. **3 h 06 for an 80-line diff.** Two of its
six ranked root causes are runtime failures with no owning contract anywhere
in the bundle:

- **Root cause 4 — one single-threaded sub-orchestrator serialized five work
  packages.** WP-1's own loop ended at 03:46; its commit landed at 04:39
  because the single orchestrator was busy on WP-4 and WP-5. That tail is
  **03:46 → 04:39 = 53 of 186 minutes — roughly 28% — spent queued, not
  working**, and it was reconstructible only by hand from spawn-log
  timestamps because nothing recorded "waiting for a scheduling slot" as an
  event. (An earlier draft of this ADR carried **69** minutes for the same
  tail. That figure double-counted the 16-minute wait already charged to the
  preceding `03:30 R2 quality` row; it is corrected here and everywhere it
  was used — see § Quantified impact.) The same root cause records that
  **a worker died silently and cost 30 minutes** before anyone noticed:
  "hex has no worker liveness/timeout."
- **Root cause 5 — a gate with no deadline.** A second `ocx` session on
  2026-08-31 left a **95-minute hole** at the cross-model adversary gate.
  (Wave 0 fixes the deadline; this ADR fixes the class — nothing was watching.)

Separately,
[`parallel-resource-pitfalls.md`](../research/parallel-resource-pitfalls.md)
records that an agent process costs ~0 local RAM and that outages come from
**what the agent runs** in its worktree, multiplied by the worktree count:
**two OOM kills** on the `ocx` host root-caused to unbounded per-worktree
build parallelism (`ocx/.claude/rules/workflow-swarm.md:236-247`, 32 cores,
31 GB + 32 GB swap), and **61 GB of disk** held by four live wave-2 worktrees
at 10–18 GB of `target/` each. On that host `/tmp` is a **64 GB tmpfs on
31 GB of RAM**, so "the disk filled with test artifacts" is an out-of-memory
event wearing a disguise.

Against that, hex today ships:

- **no liveness signal.** `protocol.md` § Worker coordination defines the depth chain, the
  concurrency cap and
  the fan-out budget, and says nothing about a worker that stops answering.
- **no resource contract.** The only concurrency knob is
  `limits.max-workers`, whose effective cap is `min(8, max-workers)`
  (`protocol.md` § Worker coordination, *"the effective cap is
  `min(8, max-workers)`"*; `config.md` § Key vocabulary, the
  `limits.max-workers` row). It caps **agent spawns** — the
  thing that is free — and says nothing about the build, test and verify
  commands those agents run.
- **no per-WP parallel pipeline.** A coordinator exists, but its gate fires
  only when a WP "holds **≥3 independent, WP-grain sub-tasks**"
  (`hex-execute/SKILL.md` § Coordinator spawn,
  `workers/coordinator.md` § coordinator's Preconditions paragraph), and "the
  conservative default is a **single builder**" (`hex-execute/SKILL.md` §
  Coordinator spawn).
  Every WP's stub → specify → implement → review-fix pipeline therefore runs
  on the one parent orchestrator's turn.
- **no per-phase telemetry.** `adr_0010`'s `## Schedule log`
  (`protocol.md` § Parallel-by-default decomposition, the schedule-log
  bullet and its grammar line) records **one bullet per
  merge**, which is exactly the granularity that cannot see a WP sitting idle
  between its own phases. The *instrument* already exists — the orchestrator
  brackets each merge-plus-check with `date -u +%FT%TZ`
  (`protocol.md` § Parallel-by-default decomposition, the schedule-log
  bullet's "Capture is deliberately cheap and best-effort" clause) — it is
  only ever pointed at a merge.

This ADR decides all four.

### The central tension

Liveness, per-phase telemetry and a heavy-command semaphore all seem to
demand precisely what `adr_0010` forbids.

- **`C-912`** puts the schedule log "**in the plan, not in a state file**"
  because a second durable location "would split the record, need a gitignore
  audit item, need a cleanup lifecycle, and make resume read two files."
- **Driver 5** — "One flat state surface … **No nested state files, at any
  depth.**"
- **`C-914`** — "Nesting stays capped at the existing `orchestrator →
  coordinator → leaf` chain. **No new orchestrator role, no recursion ≥ 2, no
  per-coordinator state.**" Unanimous council position, on three grounds:
  multiplicative re-verification across levels, LLM over-decomposition as a
  default tendency, and unbounded resume tree-walks.

A heartbeat file is state. A lock directory is state. Read literally,
`adr_0010` closes the door on both.

**It does not, and the reason is in `C-912`'s own four objections: every one
of them is an objection to a *second durable record of what happened*. None
of them is an objection to a *transient view of what is happening now*.** The
resolution is a stated, bounded amendment — § Decision Outcome › The
ephemeral/durable split — not a reinterpretation.

## Decision Drivers

1. **Wall-clock, and specifically queue time.** The traced regression was
   28% queue (53 of 186 minutes) and a 30-minute silent death. A design that
   shortens work time without recording wait time cannot be checked against
   the thing that motivated it.
2. **Never provoke the outage the fleet is trying to avoid.** Two OOM kills
   and 61 GB of disk are the measured cost of unbounded heavy commands. Any
   throughput this ADR buys is void if the machine freezes.
3. **Portability is the moat.** `DESIGN.md` § Spec-kit comparison round (2026-07-19, round 5) non-adopts "spec-kit's
   workflow engine / presets / extension-hook stack (hex ships markdown, the
   client is the runtime)". **No shipped hex file may require a client hook,
   a background process, or a named client primitive** — the floor is prompt
   text an agent executes with one foreground tool call.
4. **Capability classes, never primitive names.** `protocol.md` § Worker
   coordination gates
   on "the **capability class, not the primitive name** (the harness surface
   churns)", detected per run, never stored, announced as a `Degraded:` line.
   Copied exactly.
5. **The depth cap holds.** `adr_0010` `C-914` is load-bearing and unanimous.
   No new role, no fourth level, no recursion ≥ 2.
6. **One flat state surface.** `adr_0010` driver 5. Whatever runtime state
   exists is **one flat directory per run**, never one per coordinator.
7. **Resume reads one file.** `hex-execute/SKILL.md` § 2. Resolve the
   target re-runs
   unfinished rows from the plan table and explicitly does **not** rehydrate a
   coordinator mid-fan-out. Nothing this ADR adds may be read on resume.
8. **Additive compatibility.** `adr_0010` `C-915`: presence checks, no schema
   version field, no plan rewrite. An already-approved plan executes
   unchanged; an already-shipped sentence stays true or takes a one-clause
   qualifier.
9. **Config vocabulary is expensive.** `adr_0003` `C-223` froze the six Tier A
   keys; `adr_0010` driver 4 forbids "a key for a value a plan-table cell can
   carry". A new key must justify itself against both.
10. **Sole definition sites.** `DESIGN.md` round 10: canonical text lands once
    — in `protocol.md`, or in the new `resources.md` — and every other site
    links or takes a one-clause qualifier.

## Industry Context & Research

Five artifacts were commissioned or inherited for this decision, all dated
**2026-09-05**, all expiring **2027-03-05** except the RCA (undated
expiry — it is evidence, not landscape).

| Artifact | What it supplies |
|---|---|
| [`rca-review-fix-loop-wall-clock.md`](../research/rca-review-fix-loop-wall-clock.md) | The traced 3 h 06 run; root causes 4 and 5; the 53-of-186-minute queue tail; the 30-minute silent death; the 95-minute gate hole; the 11.8–14.7 min median spawn round trip |
| [`parallel-resource-pitfalls.md`](../research/parallel-resource-pitfalls.md) | 26-row pitfall catalog, per-ecosystem knob sheet, preflight table, containment ladder, local OOM/disk evidence |
| [`liveness-heartbeat-precedent.md`](../research/liveness-heartbeat-precedent.md) | Temporal, A2A, MCP, systemd, Kubernetes probes, Kafka KIP-62, OTP, Spark speculation, fencing tokens |
| [`semaphore-containment-portability.md`](../research/semaphore-containment-portability.md) | `flock` semantics and crash-safety, the macOS and WSL2 gaps, exact detection probes, the sandbox interaction |
| [`suborchestration-telemetry-precedent.md`](../research/suborchestration-telemetry-precedent.md) | Airflow SubDAG deprecation, pool starvation, HTB/YARN budgeting, OTel GenAI naming, render-from-the-structured-source precedent |

**Trending approaches:** vendor-neutral agent-task state (A2A's `TaskState`,
now a Linux Foundation project), transport-agnostic progress signalling (MCP
`notifications/progress`), and per-phase GenAI span attributes
(`open-telemetry/semantic-conventions-genai`, spun out mid-2025 and still
adding attributes). All three are borrowable as *shapes and names* without
taking a dependency.

**Key insight:** *every mature liveness protocol escalates on a ladder, not on
a single threshold, and every rung's verdict is degradable.*
[`liveness-heartbeat-precedent.md`](../research/liveness-heartbeat-precedent.md)
finds this in every surveyed system since 2016 and finds **no AI-agent
orchestration platform that publishes a heartbeat contract for its own
parallel fleet at all**. hex is filling a real gap, not reinventing one.

The specific precedents each decision rests on:

**Liveness.** Kafka **KIP-62** is the cleanest documented pulse/delta split:
"the current approach puts all classes of consumer failures into the same
bucket by trying to govern them all with the same timeout value" — a
heartbeat thread keeps beating while the work thread deadlocks, so
`session.timeout.ms` (liveness) was split from `max.poll.interval.ms`
(progress). **That split is surveyed and deliberately not adopted**, and the
reason is a structural difference rather than a preference: Kafka's heartbeat
runs on a *separate thread* and keeps beating straight through a deadlock, so
a pulse there proves nothing about the work. A hex beat is a **foreground
tool call made by the agent itself** (C-1204), so a fresh beat already **is**
evidence that the agent is executing. A second, progress-only test bought
nothing the pulse did not already carry and fired on healthy long phases by
construction — it was drafted as C-1203 and **withdrawn in review**; the one
case it uniquely named (an agent looping with tool calls flowing) is graded
at C-1206's L2 discriminator as a logged protocol violation at `Warn`, which
is the correct severity for it. **Temporal**'s `RecordHeartbeat` +
`heartbeat_details` is the
most complete prior art for resume-from-checkpoint on retry: the payload "can
be used to save Activity Execution progress" and the *next* attempt reads it
— the heartbeat **is** the checkpoint transport, needing no second store.
**systemd**'s `sd_notify` supplies two primitives verbatim: the half-interval
cadence rule ("send a keep-alive notification … every half of the time
returned here") and `EXTEND_TIMEOUT_USEC=`, the literal "I will take longer,
here is my new deadline" message a worker sends *before* it goes quiet.
**Kubernetes**' startup probe exists precisely so that a cold-start budget
and a steady-state deadlock budget do not share a threshold. **A2A**'s
`TaskState` (`submitted`, `working`, `input-required`, `completed`, `failed`)
supplies the enum. **OTP** supervisors (`intensity`/`period`, defaults
`MaxR=1`/`MaxT=5`), **Nomad** `restart`, **Kubernetes** `backoffLimit`
(default 6) and **Temporal** `maximumAttempts` all converge on the same
terminal rung: *stop retrying and surface it*, never retry forever.
**Kubernetes** also supplies the negative lesson — it avoids torn heartbeat
reads entirely by making the beat an atomic etcd `Lease` update, a guarantee
a plain JSON file does not inherit for free.

**Resources.** **`flock`**'s crash-safety is a kernel guarantee, not a
convention: locks attach to the *open file description* and are released
"when all … file descriptors [referring to it] have been closed" — including
on `SIGKILL`, because the kernel closes a killed process's fds
unconditionally ([flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html)).
A `mkdir` lock survives its holder's death and needs a PID-file staleness
check with a PID-reuse race `flock` structurally cannot have. The one hazard
that survives is **fd inheritance**: a child that inherits the locked fd
holds the lock after the parent exits. **`flock(1)` is util-linux and absent
from stock macOS**; `python3 -c` with `fcntl.flock` gets the same kernel
semantics with no install. **WSL2's drvfs/9P mount (`/mnt/c`) is a documented
file-locking gap** ([microsoft/WSL#4689](https://github.com/microsoft/WSL/issues/4689))
— which is one more reason the slot directory is **host-global and outside
every checkout** (C-1212). That move takes the *checkout's* location out of
the question; it does not make the lock path structurally local. A user-set
`XDG_CACHE_HOME`, an NFS or SMB home, or a WSL2 `$HOME` under `/mnt/c` all
put `$HOME/.cache` somewhere `flock` is emulated rather than kernel-backed —
**over NFS `flock` is emulated as fcntl byte-range locks, which do not carry
the open-file-description release semantics the whole rung-1 choice rests
on.** C-1212 therefore keeps a **one-line mount probe on the resolved lock
directory** and announces a degrade. It does not restore a relocation rule: a
probe plus a `Degraded:` line is enough.
**Bazel** derives its local RAM budget as a fixed fraction of host RAM
(`HOST_RAM*.67`) and **its own tracker documents that fraction misfiring at
both 8 GB and 256 GB** ([bazel#3886](https://github.com/bazelbuild/bazel/issues/3886))
— which is why the derived value is clamped rather than trusted.
**`systemd-run --user --scope -p MemoryMax=`** needs a live user session bus,
absent by default on WSL2 and in almost every container;
`[ -d /run/systemd/system ]` is the man-page-blessed shell equivalent of
`sd_booted(3)`. **`RLIMIT_AS`/`ulimit -v` breaks rustc's parallel front end
and JVM/Go address reservation** ([rust#115021](https://github.com/rust-lang/rust/issues/115021));
cgroup `memory.max` is the correct bound, and `cgcreate`/libcgroup is the
deprecated v1-era tool. **Claude Code's own sandbox** (Seatbelt on macOS,
bubblewrap + seccomp on Linux/WSL2) is documented and independently reported
to impose **no** rlimit/cgroup/timeout containment itself — those are expected
to layer on top, which is exactly the ladder's shape. **`timeout(1)` is
absent on stock macOS**; the zero-dependency substitute is
`perl -e 'alarm shift; exec @ARGV'`, which ships on every target platform's
base install. **Jest's `--workerIdleMemoryLimit`** is the precedent for
recycling on a threshold rather than only capping at start.

**Sub-orchestration.** **Airflow's `SubDagOperator` is the canonical negative
precedent**: the parent task occupies a slot in the shared worker pool and
then *blocks* on children drawn from that same pool, so under load it holds
the slot the child needs to ever start. It was deprecated in favour of
`TaskGroup`, a pure grouping construct with **no execution-slot semantics at
all**. The same shape is documented verbatim in two unrelated runtimes:
Python's `ThreadPoolExecutor` ("Deadlocks can occur when the callable
associated with a Future waits on the results of another Future") and Java's
`ForkJoinPool`, whose `ManagedBlocker` exists to "arrange for a spare thread
to be activated … while the current thread is blocked" and whose Javadoc is
explicit that "no such adjustments are guaranteed in the face of blocked I/O
or other unmanaged synchronization." **Structured concurrency is the same
conclusion reached from the opposite direction and from a more current
source**: Python's `asyncio.TaskGroup`, Trio's nurseries and Kotlin's
`coroutineScope` all make a parent that awaits its children a *scope*, not a
*worker* — the scope holds no execution resource of its own, and the children
are the only things scheduled. That is precisely C-1211's rule (a blocked
parent occupies no slot) stated as a language primitive rather than as a
scheduler workaround. **There is no precedent anywhere for
letting the blocked party keep its slot.** For allocation, **Linux HTB**
(`rate` + `ceil`) and **YARN's CapacityScheduler** (`capacity` +
`maximum-capacity` + elasticity) are the same policy at two layers —
guaranteed floor plus borrowing from idle siblings — and the documented
anti-pattern is vanilla Kubernetes `ResourceQuota`, "first-come-first-served
with no borrowing semantics at all." On depth, every surveyed system agrees
with `C-914`: Claude Code's own nesting cap moved 5 → disabled → 3 inside
three months, and at the limit it **withholds the spawning tool** so the
deepest layer flattens — the same shape hex enforces as a spec-level
invariant rather than a harness default.

**Telemetry.** The research's `PIPE_BUF` line was the load-bearing premise of
an earlier draft's many-writer append spool, and **it does not hold for the
file that draft proposed**: POSIX scopes the `PIPE_BUF` contiguity guarantee
to **pipes and FIFOs** ([pipe(7)](https://man7.org/linux/man-pages/man7/pipe.7.html)),
while the regular-file guarantee is `O_APPEND`'s own atomic-offset rule,
which carries **no size bound** and is filesystem-dependent — open(2) warns
it is unsafe on NFS. The spool was cut in review for that reason and for a
better one: nothing needed it (C-1223). **No source recommends
hand-maintaining two logs**: every dual-output precedent renders the human
view *from* the structured one — Cargo's `--timings` HTML from its own
unit-timing data, `journalctl` from the binary journal. Here the structured
source is one the run **already has** — the orchestrator's own `date -u
+%FT%TZ` brackets (`protocol.md` § Parallel-by-default decomposition, the
schedule-log bullet's Capture clause) and the single synthesized result a
coordinator already returns (`workers/coordinator.md` § coordinator, the
Return template). **OTel GenAI attribute names**
(`gen_ai.operation.name`, `gen_ai.agent.id`, `gen_ai.request.model`) are
adoptable as field names today, but the namespace is explicitly maturity
level **"Development"** — borrow the names, not the wire format. And the
field that matters is named by hex's own evidence: **`wait_ms`**, the
queue/work split, "the one most often missing and most often decisive — it's
exactly the field whose absence forced the RCA to be a manual timestamp-table
reconstruction."

## Considered Options

Four axes, one per part. **Read every table as ranking the *changes*, not as
ranking the status quo.** On three of the four axes the status-quo row scores
at or near the top, for the reason `adr_0010` named on its own two axes:
every criterion but the first is a **cost** criterion, and doing nothing pays
none of them, so a weighted sum will always flatter it. The driver that
breaks each tie is not on the table — the status quo is the thing the RCA
filed a complaint about, and "change nothing" is not an available answer to
"3 h 06 for an 80-line diff." Where a *change* option outscores the chosen
one, that is argued in prose, not re-weighted away.

### Axis 1 — worker liveness

| | Option |
|---|---|
| **L1** | **Status quo** — no liveness signal at all. A dead worker is noticed when a human looks. |
| **L2** | **Orchestrator-polled transcript inspection, no worker-side signal** — the parent periodically reads each child's output through whatever the harness exposes and infers liveness from tool-call flow. |
| **L3** | **Worker-written heartbeat files graded on a four-rung L0–L3 ladder**, with the kill path gated behind a discriminator. *(chosen)* |
| **L4** | **Client-hook-enforced stamping as the sole mechanism** — the beat is written by a hook the client fires after every tool call; no prompt-level contract. |

| Criterion | Weight | L1 | L2 | L3 | L4 |
|---|---|---|---|---|---|
| Detection latency on a silent death | 5 | 1 | 3 | 4 | 5 |
| Portability / zero client prerequisite | 5 | 5 | 2 | 5 | 1 |
| False-positive-kill risk (lower = higher score) | 4 | 5 | 3 | 5 | 4 |
| Bundle surface added (none = 5) | 4 | 5 | 4 | 3 | 2 |
| Recovery quality (resume from a checkpoint) | 4 | 1 | 2 | 5 | 4 |
| Cost to a healthy run (orchestrator turns) | 3 | 5 | 2 | 4 | 5 |
| **Weighted total** | | **89** | **67** | **109** | **85** |

**Why L3 wins on the arithmetic and on the argument.** It is the only option
whose kill path requires silence at two consecutive rungs and whose every
ambiguous observation degrades to a ping, a `Warn` or a `Degraded:` line. It
leads L1 by 20, L4 by 24 and L2 by 42, and unlike the other axes the chosen
option also tops the table — because liveness is the one part where the
status quo has a *measured* cost (30 minutes, once, in one traced run) rather
than only an opportunity cost.

**The false-positive-kill score moved from 4 to 5 in the 2026-09-05 fix
round, and the reason is a deletion.** The drafted design carried a second,
progress-only "delta" test alongside the freshness test. It fired on healthy
long phases *by construction* — `step` is the phase name and a leaf's
`checkpoint` is its last durable artifact, so neither changes **inside** a
phase, while the cadence rule forces a beat every five minutes. Any phase
over roughly ten minutes tripped L1, and on a harness that exposes no output
surface L2 has no discriminator and promotes straight to L3. The test was
**withdrawn** (C-1203), and with it the only path by which this design could
kill a healthy agent.

**Why L2 loses, and it is the option a reader should want to like.** It adds
no worker-side contract at all, which is genuinely the smallest change. It
loses on two hard grounds. First, **portability**: it requires the harness to
expose a child's output to its parent, which is exactly the kind of surface
`protocol.md` § Worker coordination says "churns", and hex has no capability class for it —
inventing one to carry the *primary* mechanism inverts the rule that
capabilities gate *degrades*, never floors. Second, **it cannot see the
failure that matters**: tool calls still flowing proves the agent is alive,
not that it is progressing. L2 survives inside L3 as the **L2 rung's
discriminator** (C-1206) — the one place where reading output is the right
instrument, because there it distinguishes *dead* from *alive and violating
the contract*, and it is used only when the cheap signal has already fired.

**Why L4 loses, and why it was cut entirely rather than kept as a ceiling.**
A hook that fires after a tool call is **enforcement that is agent-executed
by construction** — it cannot beat on behalf of a dead agent, which is the
one structural weakness of a prompt contract. That is a real advantage and it
scores accordingly on detection. It loses on driver 3, decisively: making it
the sole mechanism puts a client-specific extension in the shipped contract,
which `DESIGN.md` § Spec-kit comparison round (2026-07-19, round 5)
non-adopts by name. A drafted C-1209 kept it as an
**optional ceiling** that `/hex-init` would generate into the project's own
client configuration. **That contract was withdrawn in the 2026-09-05 fix
round** and the constitutional carve-out it needed (amendment 1) with it: it
would have been the first time hex wrote *executable configuration* rather
than documentation, for a mechanism nothing requires and nothing measures,
paid for out of the one thing `DESIGN.md` § Spec-kit comparison round
(2026-07-19, round 5) names as the moat. Part 1's
portable floor is unaffected. The option stays on the table as deferred
finding **D-4** if the beat contract is ever *measured* to be unreliable in
practice.

**Why L1 loses.** It is the 30 minutes.

### Axis 2 — the resource contract

| | Option |
|---|---|
| **R1** | **Status quo** — cap agent spawns with `limits.max-workers`; say nothing about what they run. |
| **R2** | **Lower the single cap when the machine is loaded** — keep one knob, and reduce `max-workers` under memory or load pressure. |
| **R3** | **Two caps, plus a worker-side `flock` semaphore around heavy commands.** *(chosen)* |
| **R4** | **Full cgroup containment per command, as the required mechanism** — every heavy command runs under an enforced memory bound or does not run. |

| Criterion | Weight | R1 | R2 | R3 | R4 |
|---|---|---|---|---|---|
| Prevents the observed OOM / disk class | 5 | 1 | 3 | 4 | 5 |
| Portability / no host prerequisite | 5 | 5 | 5 | 4 | 1 |
| Throughput preserved (agents not throttled) | 4 | 5 | 1 | 5 | 4 |
| Config-vocabulary cost (none = 5) | 4 | 5 | 5 | 3 | 3 |
| Correct across concurrent agent sessions | 4 | 1 | 1 | 5 | 3 |
| Bundle surface added (none = 5) | 3 | 5 | 4 | 3 | 2 |
| **Weighted total** | | **89** | **80** | **101** | **76** |

**Why R2 loses — the option the RCA's own prompt reached for, and the reason
this axis exists.** `parallel-resource-pitfalls.md`'s triggering observation
is that "a RAM warning in the prompt cut *spawns* instead of *heavy
commands*." R2 is that mistake made policy. It throttles the resource that is
free — an agent process costs ~0 local RAM — to protect the resource that is
scarce, so it pays full throughput for partial protection: four agents
*reasoning* is harmless, and one agent running `cargo test -j 32` is the OOM.
It also cannot fix the cross-session case at all.

**Why R4 loses, and what survives of it.** It is the only option that
actually *bounds* memory rather than counting invocations, and on a systemd
Linux desktop it is strictly better than R3. It fails driver 3 on every other
target: `systemd-run --user` needs a live user session bus, absent by default
on WSL2 and in almost every container, and absent entirely on macOS, where
systemd does not exist. Making containment **required** would make hex
unrunnable on two of its three target platforms. It survives as the
**containment ladder's top rung** (C-1218), detected per run and announced
when it degrades.

**Why R3's `flock`-over-`mkdir` choice is argued rather than asserted.**
`mkdir` is POSIX-atomic everywhere with zero dependencies and would score
higher on portability. It is rejected on **crash-safety**, which is the one
property this use case cannot trade: a `flock` lock lives in kernel state
tied to the fd and is released on `SIGKILL`, so an OOM-killed build never
wedges a slot; a `mkdir` lock is a directory that persists until something
`rmdir`s it, so an OOM-killed build wedges that slot **for every future run**
until a human clears it. The documented repair — a PID file plus a
`kill -0` staleness check — reintroduces a PID-reuse race `flock`
structurally cannot have. An agent contract that can silently wedge itself
with no recovery path is worse than one with no semaphore, so `mkdir` is the
**third** rung (C-1212), reachable only when neither `flock(1)` nor a Python
interpreter exists, and it ships with the staleness check as a mandatory
companion rather than an optimization.

**Why R1 loses.** Two OOM kills and 61 GB.

### Axis 3 — per-work-package sub-orchestration

| | Option |
|---|---|
| **P1** | **Status quo** — the parent orchestrator runs every WP's whole phase pipeline itself, serially; a coordinator appears only for a WP with ≥ 3 sub-tasks. |
| **P2** | **A new per-WP orchestrator role and a second recursion level** — the parent spawns one sub-orchestrator per ready WP, which spawns coordinators, which spawn leaves. |
| **P3** | **Widen the existing coordinator's gate so it owns each ready WP's pipeline.** *(chosen)* |
| **P4** | **Phase-major interleaving without delegating** — the parent runs each phase across all ready WPs in one batch (all stubs, then all specifies, …) and never hands a pipeline to anyone. |

| Criterion | Weight | P1 | P2 | P3 | P4 |
|---|---|---|---|---|---|
| Removes the traced queue time | 5 | 1 | 4 | 4 | 3 |
| `C-914` compliance (constitution cost) | 5 | 5 | 1 | 5 | 5 |
| Context / token amplification (lower = higher) | 4 | 5 | 1 | 3 | 4 |
| Resume simplicity | 4 | 5 | 1 | 4 | 3 |
| Bundle surface added (none = 5) | 3 | 5 | 1 | 3 | 2 |
| Legibility of a failure | 3 | 4 | 2 | 4 | 2 |
| **Weighted total** | | **97** | **42** | **94** | **80** |

**P2 is the option a reader will most want, and it is worth steelmanning
before it is rejected.** Its genuine advantages are real and P3 pays for
declining them. A dedicated role gets a prompt written for *scheduling* —
ready-set arithmetic, budget partitioning, phase sequencing — rather than a
prompt written for *decomposing a work package* and stretched to cover
scheduling too. Reuse muddies an identity: `workers/coordinator.md` § coordinator's Mission line says
a coordinator's mission is to "own one work package that is itself 3+
independent sub-tasks", and P3 makes that sentence false for the common case.
A separate role would also let the two jobs carry different model classes and
different self-checks. And OTP's own supervision-tree guidance is that
supervisors-of-supervisors is a normal shape, not a smell.

**It is rejected on four grounds, in descending force.**

1. **It buys no additional parallelism.** The effective cap is
   `min(8, max-workers)` counted recursively (`protocol.md` § Worker
   coordination), and P2
   does not raise it. Both P2 and P3 run `min(|ready set|, effective cap)`
   work packages at once. P2's entire delta over P3 is a **level**, not
   throughput — which is why its wall-clock score is 4, the same as P3's, and
   not 5.
2. **It violates `C-914` literally and on all three of the council's stated
   grounds** — a new orchestrator role, recursion ≥ 2, and per-coordinator
   state a resume would have to walk. `C-914` is unanimous and load-bearing;
   overturning it would need its own ADR and its own council, not a clause in
   a runtime ADR.
3. **Token cost compounds per level.** Anthropic's own multi-agent report
   puts a lead-plus-subagents system at ~15× a single chat turn and warns
   that "a subagent that recursively spawns more subagents … can multiply
   cost by another 10x or more", naming coding specifically as a poor fit.
4. **Every surveyed system settled shallower, not deeper.** Claude Code's own
   nesting cap moved 5 → disabled → 3 in three months, and OTP's one explicit
   depth caution is that restart intensities compound multiplicatively across
   levels.

**Why P4 loses.** It is the honest minimal alternative and it does remove
some queue time by batching. It loses because a phase-major schedule
reintroduces the barrier `adr_0002` `C-101`'s ready-set dispatch exists to
remove: the slowest WP's stub gates every WP's specify, so a WP that is ready
to merge waits for a sibling that is not. It also concentrates every phase's
synthesis on the parent's single turn — the exact bottleneck root cause 4
names — and makes a failure illegible, because one batch return mixes N work
packages.

**What P3 costs, stated rather than smoothed.** The coordinator's mission
sentence becomes false and must be rewritten, and the single gate at
`hex-execute/SKILL.md` § Coordinator spawn has to split into two questions that happened to
share one gate: *does this WP get a coordinator* (new answer: yes, whenever
the ready set has ≥ 2 WPs and the harness can nest) and *does that
coordinator further decompose into sub-WPs* (unchanged: the ≥ 3-sub-task
judgment). **This is the single most reviewable claim in Part 3**, and it is
made explicitly in C-1219 rather than left to be inferred from a widened
gate.

**And the cost is larger than "one sentence", which the 2026-09-05 fix round
established and this ADR now states rather than discovers.** The word
*coordinator* is not a bare identity in the shipped tree; it carries **six
behavioural riders across four shipped files**, each of them verified text
(C-1219 enumerates all six and assigns each to Q1 or Q2):

1. `protocol.md` § Worktree work-package mechanics (*"the merge of a
   coordinator-owned WP … pays a full post-merge verification rather than a
   scoped check — the `join` trigger"*).
2. `protocol.md` § Checkpoints (*"a coordinator join resets the counter
   exactly as a checkpoint does"*) — the `M = 3` checkpoint counter.
3. `hex-execute/SKILL.md` § Coordinator spawn — a coordinator WP is "**by
   definition `panel`** — `self`/`light` WPs never qualify for a coordinator".
4. `workers/coordinator.md` § coordinator (the Tools/Model paragraph) — the
   role resolves to `deep-reasoning` and is **tier-gated to medium/high**;
   plus `workers/coordinator.md` § coordinator (the Join paragraph's 1-round
   spec+quality loop) and (the Join paragraph's leaf-compile-check sentence).

Reusing the identity for every ready WP would drag all of them in silently,
and **three of them re-create the RCA root causes this program exists to
remove** — every merge paying a ~25-minute full gate instead of the 1m32s
scoped check the RCA logged (root cause 6), every WP becoming `panel` (root
cause 2, and a reversal of `DESIGN.md` § Worktrees (hex-execute parallel work
packages)'s lower-only Review budget), and every WP gaining a deep-reasoning agent it did not have (root cause 3).
C-1219 therefore names **two kinds** of coordinator and gives them different
riders — **rider (iii) is deleted for both kinds; the other five key on Q2** —
and three new numbered amendments (6, 7, 8) carry the retargeting into
`protocol.md`, `hex-execute/SKILL.md` and `models.md`. That is the honest
price of P3, and it is not one sentence.

### Axis 4 — run telemetry

| | Option |
|---|---|
| **T1** | **Status quo** — `adr_0010`'s `## Schedule log`, one entry per merge, written by the parent. |
| **T2** | **Per-phase lines written directly into the plan by every agent** — each coordinator and leaf appends its own `## Schedule log` bullet. |
| **T3** | **Per-phase lines rendered into the plan by the parent, from instruments the run already has** — the parent's own `date -u +%FT%TZ` brackets and the single structured result each coordinator already returns. **No new file and no new writer.** *(chosen)* |
| **T4** | **Full OpenTelemetry export** — real `gen_ai.*` spans to a collector. |

| Criterion | Weight | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|
| Answers "where did the wall clock go" | 5 | 2 | 5 | 5 | 5 |
| Write correctness under concurrency | 5 | 5 | 1 | 5 | 5 |
| Durable-record integrity (`C-912`) | 4 | 5 | 2 | 5 | 3 |
| Portability / no dependency | 4 | 5 | 5 | 5 | 1 |
| Bundle surface added (none = 5) | 3 | 5 | 4 | 4 | 1 |
| Operator legibility | 3 | 4 | 4 | 4 | 3 |
| **Weighted total** | | **102** | **82** | **114** | **78** |

**T3's three top-row scores were 4 before the 2026-09-05 fix round, and they
moved because a mechanism was deleted, not because a weight was argued.** The
drafted T3 was an ephemeral many-writer JSONL spool at
`<run root>/.hex/run.jsonl`, whose stated correctness condition was
`PIPE_BUF` — which POSIX scopes to **pipes and FIFOs**, not to regular files,
so the premise was wrong; the applicable regular-file guarantee is
`O_APPEND`'s atomic-offset rule, which has no size bound and is
filesystem-dependent. The adversarial reviewer then showed the spool was not
needed at all: **the parent already holds both numbers.** It brackets what it
runs itself with the pattern `adr_0010` already ships
(`protocol.md` § Parallel-by-default decomposition, the schedule-log
bullet's Capture clause), and it already knows when a WP became runnable and
when its coordinator was spawned — which *is* `wait_ms` at work-package grain,
C-1225's single definition named coarser rather than a second one. A coordinator
already returns one synthesized structured result
(`workers/coordinator.md` § coordinator, the Return template), so per-phase
timings become fields in that existing
return. Deleting the spool made the chosen option **one writer, one place**:
write correctness and durable-record integrity become T1's (5 and 5), the
`O_APPEND` dependency disappears (portability 5), and the surface added drops
to a grammar and a handoff paragraph (4). T3 now tops the table on the
arithmetic as well as on the argument.

**Why T2 loses, and it is a correctness argument, not a taste one.** A
markdown section edit is **read-modify-write**. N concurrent coordinators
appending to one plan section is the textbook lost-update race: two writers
read the same section, both append, the second write erases the first. There
is no locking discipline available inside a markdown edit and no way to
detect the loss afterwards — the log simply comes out short, which is the
worst possible failure for an artifact whose job is to be believed. `C-912`'s
existing writer is already the parent, and it stays the only one.

**Why T4 loses.** It answers the question best and is the only option that
would survive contact with a real fleet. It fails driver 3 twice over: a
collector is a background process, and an SDK is a dependency. The
namespace's own maturity level is "Development". T3 takes what is portable
about it — **the field names** — and leaves the wire format, so a future
migration is a rename rather than a redesign.

**Why T1 loses.** One entry per merge cannot see a WP idle between its own
phases, which is the entire finding. It is not a smaller version of the
answer; it is a different granularity. T1 is otherwise the option T3 now most
resembles — same writer, same file, same append-only discipline — which is
why T3 costs so little: the delta is a second line kind and a render step,
not a second store.

## Decision Outcome

**Chosen: L3 + R3 + P3 + T3**, implemented as **twenty-four live contracts**
inside the numbered block `C-1201`–`C-1226` — **`C-1203` and `C-1209` were
withdrawn in the 2026-09-05 fix round** and are kept as explicitly withdrawn
rows so no ID moves — with scenarios `S-1201`–`S-1213`.

The shape in one paragraph: **every agent writes a small JSON heartbeat into
one flat per-run directory that lives outside every checkout, under
`${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/hb/`, carrying a state, a step,
a resume checkpoint and its own next deadline; the *top* orchestrator — the
one agent that reliably takes turns — runs a four-rung ladder over the whole
flat directory, and a dead agent is re-spawned from its checkpoint exactly
once per phase. Heavy commands — the build, the tests, the merge and
checkpoint verification gates — take one of `limits.heavy` `flock` slots in
one **host-global** lock directory outside every checkout, held
around the command rather than for the worker's lifetime, acquired
**fail-closed** so a timed-out wait never runs the command unlocked, sized
from a resource profile `/hex-init` measures once, behind a sub-two-second
three-check preflight that holds a spawn wave rather than provoking the
machine. A **pipeline coordinator** — the existing coordinator role, at the
existing depth, carrying **none** of the six behavioural riders the word drags in today
— is spawned per ready work package and runs that package's whole phase
pipeline; a **decomposing coordinator** additionally fans the package out
into sub-WPs and keeps every rider unchanged. The parent only schedules,
merges serially, and runs the gates, and a coordinator waiting on its own
children does not occupy a concurrency slot. **Telemetry adds no file and no
writer**: the parent times what it runs from its own `date -u +%FT%TZ`
brackets and reads per-phase timings out of the structured result each
coordinator already returns, renders one `phase` line per phase into the
plan's `## Schedule log` at merge time, and prints the rollup at handoff.**

### The ephemeral/durable split — answering `C-912` by name

`adr_0013` admits runtime state under **four conditions, and only under all
four**:

1. **Ephemeral, and outside every checkout** — created by the run, deleted by
   the run's teardown, and written at
   `${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/`, never inside a repository.
   There is nothing to gitignore and nothing that can be committed by
   accident.
2. **Never authoritative** — the plan's Parallelization table and
   `## Schedule log` remain the sole record of *what happened*. Runtime files
   record only *what is in flight*.
3. **Never read by resume** — resume re-runs unfinished rows from the plan
   exactly as today (`hex-execute/SKILL.md` § 2. Resolve the target). No
   rehydration, so
   `C-914`'s "unbounded resume tree-walks" cannot occur.
4. **One flat directory per run**, never one per coordinator — driver 5's
   flat state surface is preserved literally, not by analogy.

`C-912`'s four objections, each answered:

| `C-912` objection | Answer |
|---|---|
| "would **split the record**" | It does not. The runtime files are discarded; the plan is rendered into and committed. There remains exactly one durable record of what happened, written by exactly one writer (C-1223). |
| "need a **gitignore audit item**" | **None. Zero gitignore lines.** After the 2026-09-05 fix round nothing this ADR writes enters a checkout at all: the heartbeat directory moved out to `${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/hb/` (C-1201, C-1215), the telemetry spool that would have needed one was deleted outright (C-1223), and the heavy-slot tokens were always host-global (C-1212). This objection is not answered — it is **dissolved**. |
| "need a **cleanup lifecycle**" | Part 2 introduces one regardless: `parallel-resource-pitfalls.md` rows 21–22 make orchestrator-owned teardown mandatory for worktrees, redirected build directories, caches, daemons and containers, because `SIGKILL` skips a worker `trap`. The run's heartbeat directory is a sibling of the scratch root it already tears down, so it rides an owner that exists for other reasons (C-1216). |
| "make **resume read two files**" | It does not. Resume reads the plan. Condition 3 is a contract, not an intention: nothing under the run's runtime root is ever read by a resuming run, and § Validation greps for it. |

**This is a stated amendment to `adr_0010` driver 5 and to `C-914`'s "no
per-coordinator state" clause, narrowed to ephemeral, non-authoritative
runtime state**, with the four conditions as its boundary. It is recorded as
amendment 2 in [Constitution deviations](#constitution-deviations--designmd-amendments),
not as a reinterpretation.

### Quantified impact

**This table was recomputed from the RCA's traced timeline in the 2026-09-05
fix round. The earlier ~100-minute claim did not survive, and it is not
defended below — it is replaced.** Two arithmetic errors produced it: the
queue tail was carried as **69** minutes when the RCA's own rows give
`03:46 → 04:39` = **53** (69 double-counted the 16-minute wait already
charged to the preceding `03:30 R2 quality` row), and the added cost of a
pipeline coordinator was not charged at all.

The traced work package: spawned 01:33 UTC, committed 04:39 — **186 minutes**.
Its rows sum as 5 (spawn lead-in) + 89 (the six healthy round-trip waits:
17 + 18 + 15 + 12 + 11 + 16) + 39 (the silent death: 29 minutes of silence
plus a 10-minute re-spawn round trip) + 53 (the queued tail) = 186. ✓

| Metric | Before | After | Notes |
|---|---|---|---|
| Silent-death detection | ~30 min (measured, once) | **≤ 13 min** where a condition-waiting or scheduled-wake capability exists; **up to ~28 min** on the portable floor | `2 × expect_next_s` (600 s) + a 3-minute ping wait, **plus**, at C-1208 rung 3, the wait to the orchestrator's next turn boundary — ~12–15 min apart on this very run. A missed **startup** beat is caught at **2 min** (C-1204). |
| WP-1 queue tail | **53 min** (28% of wall) | **→ ~5 min** | Removed by C-1219, less the serialized merge lane that still runs: three near-simultaneous merges, each a scoped check the RCA logged at 1m32s. |
| Cost of the pipeline coordinator | — | **+12 to +15 min per WP** | One added spawn round trip, charged at the RCA's own median opus batch-to-batch latency (11.8 min after 2026-08-30, 14.7 min before). This is a real cost and it is charged, not absorbed. |
| **Traced WP wall clock** | **186 min** | **135–150 min** | Best case `186 − 48 − 17 + 12 = 133`; portable floor `186 − 48 − 2 + 15 = 151`. **Published as 135–150.** |
| Pipeline depth | ≥ 7 serial round trips | unchanged — a **~90-minute floor** | 7 trips × ~12 min. Root cause 1 is `adr_0012`'s lever (per-WP effective tier), not this one (C-1222). **No arrangement of this ADR's contracts can go below it.** |
| Orchestrator turns on a healthy run | — | **zero added** | The portable floor is one directory glob at a turn boundary the top orchestrator was taking anyway (C-1208). The figure holds because the evaluator is the *top* orchestrator, whose turn boundaries are real (C-1207). |
| OOM kills on a fleet run | 2 observed | bounded by construction | Concurrent heavy commands ≤ `limits.heavy`, derived from measured peak RSS with a clamp (C-1213), behind a preflight that holds rather than spawns (C-1214), and acquired **fail-closed** (C-1212). |

**The honest limit: this ADR removes *waiting*, not *working*.** Root cause 1
— the ≥ 7 serial round trips every WP pays at every tier — is untouched here
by design and puts a **~90-minute floor** under the traced run. 135–150
minutes is therefore roughly 45–60 minutes above a floor this ADR cannot
move, and **the RCA's ≤ 30 min target is not reachable without `adr_0012`**,
whose own arithmetic assumes both land ("Wave 1 (per-WP effective tier +
per-WP sub-orchestration + liveness): reach target"). An ADR that overstates
its own saving is exactly the failure this program was created to end, so the
larger number is published rather than the smaller one.

### Consequences

**Good.** A worker that dies is noticed in minutes rather than at the next
human glance, and is resumed from a checkpoint rather than restarted from
zero. A work package that is ready to run no longer waits behind a sibling's
review round. The machine stops being a shared resource nobody accounts for.
And the next wall-clock regression is a query against a run's own numbers
rather than a manual archaeology project against spawn logs — which is
precisely how this program started.

**Bad, and accepted.** Every agent now pays a small foreground tool call per
beat: one write at spawn, one per phase boundary, one per five minutes of
work, and one before a known-long call. On a healthy fast worker that is a
handful of writes; on a chatty phase boundary it is noise in the transcript,
and it is the price of not needing a background process. `limits.heavy`
**serializes work that used to run concurrently** — on a project whose
verification gate is heavy and whose host is small, `heavy` clamps to 1 and
the fleet's build step becomes a queue. That is the correct outcome (it is
the alternative to an OOM) but it is a real throughput cost and it is not
hidden. **The pipeline coordinator is a real extra agent, not a relabelled
one**: one added spawn per ready work package, at the RCA's own 11.8–14.7 min
median round trip, plus rules added to `workers.md` § Universal worker
protocol and fields added to every spawn prompt. `limits.heavy`'s own cost is
contention; the coordinator's is tokens and one round trip, and § Quantified
impact charges it rather than averaging it away. The coordinator's identity
widens, one shipped mission sentence becomes false, and **all six behavioural
riders the word carries have to be retargeted — five scoped to the decomposing
kind and one deleted outright** (C-1219, amendments 6–8) — including
`adr_0010` `C-901`'s `join` full-verification trigger and the `M = 3`
checkpoint-counter reset, which are **not** free changes and are not claimed
as such: `adr_0010`'s verification budget is amended here, not left untouched. Teardown becomes load-bearing: a run
killed hard enough to skip its own teardown leaves a scratch root and a run
heartbeat directory behind — both under
`${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/`, neither inside a repository
— which the next run's sweep **reports rather than deletes** (C-1216), so the
failure mode is a warning and some disk, never a wrong deletion.

**Deferred findings.**

- **(D-1) The semaphore is host-global, but "host" means "one shared
  `$HOME`".** Slots live at
  `${XDG_CACHE_HOME:-$HOME/.cache}/hex/locks/heavy-{1..N}` (C-1212), so every
  agent, every checkout and every independent agent session sharing that home
  directory contends on **one** slot set — which is the case the research
  names and the case that produced the two OOM kills. What is left uncovered
  is agent sessions on one physical host that do **not** share a home
  directory: separate containers, separate user accounts, a devcontainer
  beside a native session. Each of those sees its own slot directory, and the
  host can then run up to the sum of their caps. Closing it needs a path
  outside every home (`/run`, `/var/tmp`) with a cross-user permissions story
  hex does not want to own, so the residual is recorded, not mitigated. It is
  small: the containers that produce it usually carry their own memory bound.
- **(D-2) The ladder cannot see a worker that is progressing wrongly.** A
  fresh beat proves the agent is executing, not that the execution is useful;
  an agent looping through tool calls forever is graded at L2 as a live agent
  and is never killed. That is deliberate — killing it is the worse error —
  and the backstop is the orchestrator's own phase gates and the plan's
  terminal escalation, not the ladder. Spark-style progress-*rate* comparison
  against peers is the field's answer and is explicitly out of scope: it
  needs a per-phase duration corpus that C-1223's rendered `phase` lines
  would take several runs to accumulate.
- **(D-3) `expect_next_s` is worker-declared and therefore worker-trusted.**
  A worker that declares an enormous deadline before every call makes itself
  un-killable. This is systemd's identical exposure with
  `EXTEND_TIMEOUT_USEC=` and is accepted for the same reason: the alternative
  is one global timeout that either kills slow honest workers or never fires.
  The bound that survives is the heavy command's own wall-clock backstop
  (C-1212), which no declaration can extend.
- **(D-4) A prompt cannot compel a beat, and the enforcement that could was
  cut.** A client hook firing after every tool call is the one mechanism that
  is agent-executed by construction and therefore cannot beat on behalf of a
  dead agent. It was drafted as C-1209 with a constitutional carve-out
  (amendment 1) and **withdrawn in review**: it would have made hex write
  executable configuration for a mechanism nothing requires and nothing
  measures, against `DESIGN.md` § Spec-kit comparison round (2026-07-19,
  round 5). **The option stays available** and
  should be revisited only if the beat contract is *measured* to be
  unreliable in practice — the measurement, not the intuition, is the trigger.
- **(D-5) A coordinator that dies loses its unreturned phase timings.**
  C-1223's per-phase numbers ride the coordinator's existing structured
  return (`workers/coordinator.md` § coordinator, the Return template), so
  a coordinator killed at L3 before
  returning takes that work package's phase timings with it. **Telemetry
  only: merges, gates and the plan's Status column are unaffected**, and the
  parent's own brackets still time the merge. Recorded, not engineered for —
  a second store to survive it is exactly the spool this round deleted.
- **(D-6) The residual multi-host semaphore case.** Agents in separate
  containers with separate `$HOME`s still oversubscribe one physical host.
  Small and honest; see D-1 for the full statement.
- **(D-7) Sleep and suspend defeat the ladder, and would make it lie.** A
  laptop that sleeps mid-run suspends **every** agent at once, including the
  orchestrator. On wake, wall-clock time has advanced by hours while no agent
  advanced at all, so **every** beat is stale by `2 × expect_next_s` and the
  ladder would grade the entire fleet dead — killing and re-spawning healthy
  workers, which is exactly the false positive C-1206 is built to avoid. A
  fleet-wide staleness discriminator ("if *everyone* is stale, the host slept,
  not the fleet") is the obvious repair and is **deliberately not adopted**:
  it announces a diagnosis it cannot actually distinguish from the case where
  one shared dependency genuinely killed every worker, and the wrong
  announcement is worse than none. **What holds instead is the ladder's own
  shape:** the evaluator is the top orchestrator (C-1207), which was suspended
  too, so it takes its next turn *after* the wake — and L1's 3-minute wait,
  taken from that turn, gives every live agent a full beat interval to prove
  itself before anything is killed. **Recorded, not engineered for.** The
  honest statement is that a suspended run's first post-wake evaluation is
  unreliable and a human should re-read the plan's Status column rather than
  trust that pass.

## Component contracts

Contracts are numbered `C-12xx`; UX scenarios `S-12xx` — the next free block.
**The evidence is restated against the tree as it stands after the 2026-09-05
fix round, because the earlier statement was taken before `adr_0012` landed on
disk.** `.agents/adrs/adr_0012_per_wp_effective_tier.md` **now exists** and
claims **`C-1101`–`C-1124`** and **`S-1101`–`S-1111`** — the block this ADR
had reserved for it while it was in flight, taken exactly as reserved. Outside
it, the highest contract ID in the repository is `C-1044` (`adr_0011`) and the
highest scenario ID is `S-1015`. **No file outside this one *defines* a
`C-12xx` or `S-12xx`**; `adr_0012` *cites* `C-1206`, `C-1207`, `C-1219`,
`C-1220` and `C-1221` by id at its seam, which is a reference, not a claim. The
conclusion is therefore unchanged: `C-12xx`/`S-12xx` is free and
`C-11xx`/`S-11xx` is `adr_0012`'s and is not touched here.
Predecessors: `adr_0001` `C-00x`, `adr_0002`
`C-1xx`, `adr_0003` `C-2xx`, `adr_0004` `C-3xx`, `adr_0005` `C-4xx`,
`adr_0006` `C-5xx`, `adr_0007` `C-6xx`, `adr_0008` `C-7xx`, `adr_0009`
`C-8xx`, `adr_0010` `C-9xx`, `adr_0011` `C-10xx`. **Home** names the single
definition or edit site; "(sole source)" marks a definition every other file
links to rather than restates.

### A. The liveness contract

| ID | Contract | Home |
|---|---|---|
| **C-1201** | **The heartbeat file — one flat directory per run, outside every checkout, one JSON object per live agent, written temp-then-rename.** Every live agent maintains exactly one file at **`${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/hb/<agent-id>.json`** — a sibling of the per-run scratch root the run already creates and tears down (C-1215), and **outside every repository**. **The directory is not in the repository, and that is a security decision, not a tidiness one.** A fixed, guessable in-tree path that is *read as a control surface* is attacker-plantable by the repository under work: a hostile clone ships a beat with `{"parent":"orchestrator", …}`, ages it to L3, and its attacker-authored `checkpoint` string is interpolated into a re-spawn prompt as "where to resume"; a planted directory **symlink** redirects the temp-then-rename write out of the checkout entirely. Moving out of the tree removes the plantable surface, and `<run-id>` removes a second defect the in-tree path had: two runs in one checkout collided on `orchestrator.json`. A **worktree-local** directory is rejected for two further reasons — it is deleted with the worktree at exactly the moment a post-mortem needs it, and a parent cannot glob its children's beats across N worktrees in one read. **The orchestrator resolves every path under `${XDG_CACHE_HOME:-$HOME/.cache}/hex/` once, from its own unredirected environment, and passes each as an absolute path in every spawn prompt; a worker never expands `${XDG_CACHE_HOME:-…}` itself**, because C-1215 redirects `XDG_CACHE_HOME` into the per-run scratch and a worker's own expansion would land back inside that scratch. **This is the sole statement of that rule** — it governs the heartbeat directory here and the lock directory in C-1212, which references it rather than restating it. An agent that was passed no path writes no beat and is exempt from the ladder (C-1206 degrades to today's behaviour for it). **`<run-id>` and every `<agent-id>` are orchestrator-minted**, slugified to `[a-z0-9][a-z0-9-]{0,63}`, **never taken verbatim from a plan cell or a filename** — these strings reach an `rm -rf` target (C-1216) and a composed shell. **Minting is not the only line of defence: C-1216 additionally refuses any delete target that does not resolve under its own run-root prefix**, so a future caller that bypasses the minting rule still cannot direct a deletion outside the run's own subtree. **Fields, and no schema-version field** (`adr_0010` `C-915`: presence checks, never a version marker) — `seq` (int, monotonic from 1), `parent` (string or `null`; `null` for the top orchestrator), `state` (C-1202), `step` (short string: the phase or step name it is on now), `checkpoint` (string or `null` — a **path** for a leaf, a **join-commit SHA** for a coordinator, C-1205), `ts` (ISO-8601 UTC), `expect_next_s` (int: seconds until the next beat is due), and `blocked_on` (string, **present only in state `blocked`**; a `blocked` beat without it is a legible-but-unhelpful beat, never a graded violation). **There is deliberately no `id` field** — it would be byte-identical to the filename stem, which is the same rule that rejects a `children` field: a second copy that can disagree with the thing it names. **There is deliberately no `children` field.** The directory is flat and every file carries `parent`, so any agent reconstructs any subtree with one glob and a filter. **`seq` is the torn-write guard and nothing else: it is never used to grade liveness.** Only `ts` and file completeness grade an agent. An agent whose context is compacted and which restarts its counter at 1 must not be gradeable as dead for it, and this sentence is what prevents that. **Written temp-then-rename** — write `<agent-id>.json.tmp`, then `mv` it into place — so a reader never observes a partial object, `mv` within one directory being atomic on POSIX. Kubernetes avoids this problem entirely by making the beat an atomic `Lease` RPC; a plain JSON file does not inherit that guarantee and must earn it. **Exactly one writer, always — the agent the filename names.** No parent, no sibling and no sweep ever writes into another agent's beat file, not even to mark a child it has just stopped: a parent writing into a child's file races a child that may not in fact be dead. What that makes `failed` mean is C-1202; where a dead agent's terminal state is recorded instead is C-1206. **The file is ephemeral**: deleted by teardown (C-1216), never inside a repository, never read by resume. | `protocol.md` § Worker coordination › Worker liveness (new subsection, sole source) |
| **C-1202** | **The state enum — five values, two of them load-bearing.** `spawning \| working \| blocked \| done \| failed`. A deliberately trimmed borrow from A2A's `TaskState` (`submitted`, `working`, `input-required`, `completed`, `failed`), reduced to what an orchestrator actually branches on. **`spawning` carries the Kubernetes startup-probe rationale**: a cold-start budget and a steady-state deadlock budget are different numbers and must not share a threshold, which is the documented reason that probe exists. **`blocked` is load-bearing for exactly one thing, and it is contract, not convention: it exempts the agent from the concurrency cap** (C-1211), which is what keeps Part 3 from deadlocking. *(A drafted second job — suspending a progress-delta test — went away with C-1203, withdrawn; a blocked agent still has to beat, and a fresh beat is all the ladder ever asked of it.)* An agent in `blocked` sets `blocked_on` naming what it waits for. **A `blocked` beat with no `blocked_on` is not graded as anything** — not a violation, not a death; it is a less useful beat, and the ladder reads `ts`. **`failed` means "the agent reported its own failure before exiting" — never "the parent declared it dead".** This is stated in the enum, not only in the ladder, because the enum is where a reader looks: **every heartbeat file has exactly one writer, its own agent, always** (C-1201), so no parent ever stamps a terminal state into a child's beat. A dead agent's last beat simply stops being refreshed, and that **absence is the signal** the ladder reads (C-1206). The terminal state of the *work* lives where work state has always lived — the plan's Parallelization-table **Status** column, which the parent already owns and already writes. `done` and `failed` are terminal for the file: it stops advancing, and the parent may delete the stale file at teardown. | `protocol.md` § Worker coordination › Worker liveness (sole source) |
| **C-1203** | ~~**Delta, not pulse — two tests, evaluated independently.**~~ **WITHDRAWN in the 2026-09-05 fix round. Ships nothing; the ID is retained so no other contract moves.** The drafted contract added a progress test — a *changed* `step` or `checkpoint` between consecutive `working` beats — evaluated independently of freshness. **It fired on healthy long phases by construction**: `step` is the phase name and a leaf's `checkpoint` is its last durable artifact, so neither changes *inside* a phase, while C-1204 forces a beat every five minutes. Any phase over roughly ten minutes tripped L1, and where the harness exposes no output surface L2 has no discriminator and promotes straight to L3 — so the design's own claim that no failure in it kills a healthy agent was false while this contract stood. **Its precedent does not transfer.** Kafka KIP-62 splits pulse from progress because a Kafka heartbeat runs on a *separate thread* and keeps beating through a deadlock; a hex beat is a **foreground tool call by the agent itself** (C-1204), so a beat already **is** evidence the agent is executing. The one case the delta test uniquely named — an agent looping with tool calls flowing but making no progress — is graded at C-1206's L2 discriminator as a logged protocol violation at `Warn` (`adr_0006` `C-502`), which is the correct severity for it, and is recorded as D-2. **`checkpoint` is kept** — resume needs it (C-1205). | — (withdrawn; no landing site) |
| **C-1204** | **Cadence — four obligations, one default, and no background process.** An agent writes a beat: **(i) at spawn**, within **2 minutes**, in state `spawning`; **(ii) at every phase boundary**, with `step` changed; **(iii) at least every 5 minutes** while `working`; and **(iv) before any tool call it expects to exceed its current deadline** — a beat declaring a **new, larger `expect_next_s`**. Obligation (iv) is systemd's `EXTEND_TIMEOUT_USEC=` primitive: the worker moves its own deadline **before** it blows it, rather than the orchestrator guessing one global timeout for every worker. Where a worker is free to choose, it beats at **`expect_next_s / 2`** — systemd's exact `WATCHDOG_USEC` rule, quotable as "send a keep-alive notification … every half of the time returned here" — so a single lost beat is not a miss. **Default `expect_next_s` = 300.** **Every beat is one foreground tool call by the agent itself.** No background process, no timer, no daemon, no client hook appears anywhere in the shipped contract (driver 3). An agent that cannot write files has no beat and is exempt (C-1201). | `protocol.md` § Worker coordination › Worker liveness (sole source); `workers.md` § Universal worker protocol gains one rule pointing at it |
| **C-1205** | **The checkpoint — the resume anchor, reusing what already exists.** `checkpoint` is the anchor a **re-spawn** resumes from, and it names no new mechanism. **The field carries two different values and the contract says which agent writes which — one field with two unattributed meanings is how the contradiction below got in.** For a **coordinator**: **a commit SHA**, the SHA of its last sub-WP join commit — `workers/coordinator.md` § coordinator (the Join paragraph's commit-on-join sentence) already commits on the WP's branch after each sub-WP join and already calls it "a reset point; on re-run, reset to the last committed sub-WP boundary", so this form is true and exists today. For a **leaf**: **a path, never a SHA** — the path of the last durable artifact it produced. **A leaf has no commit to point at**: `workers.md` § Universal worker protocol rule 5 is "**Never auto-commit** — report status only", so offering a leaf the SHA form would put this field in direct contradiction with a universal worker rule. Where nothing durable exists yet: **`null`**, and a re-spawn restarts the phase from its beginning. The value is **advisory to the re-spawn prompt, never authoritative over the plan**: a re-spawned agent still reads the plan row for its scope, and the checkpoint only tells it where to pick up. Precedent: Temporal's `heartbeat_details`, whose entire purpose is resume-from-checkpoint on retry — the heartbeat is the checkpoint transport, so no second store is needed. **This is the whole of the "state" this ADR adds to a re-spawn**, and it is one string. | `protocol.md` § Worker coordination › Worker liveness (sole source); one-clause qualifier in `workers/coordinator.md` naming the join commit as the checkpoint value |
| **C-1206** | **The escalation ladder — four rungs, one retry per phase, and a discriminator that distinguishes death from contract violation.** **L0 fresh:** the last beat is within `expect_next_s` → nothing happens. **L1 stale:** `now − ts > 2 × expect_next_s` → wait **3 minutes**, and **best-effort ping the agent over the harness's agent-messaging capability**. **The wait is the rung; the ping is not a gate.** L1 proceeds on its timer whether or not the harness can deliver a message, whether or not a message is delivered, and whether or not one is answered — the capability class is kept because an answered ping short-circuits back to L0, but no rung depends on it. **L2 unresponsive:** no new beat after that wait → read the agent's output **if the harness exposes it**. **The discriminator: tool calls still flowing ⇒ the agent is alive and violating the beat contract — log a `Warn` finding (`adr_0006` `C-502`) and do NOT kill it.** Silent ⇒ L3. **Any worker text this rung reads or echoes is untrusted and is quoted and truncated per `protocol.md` § Untrusted-text echoes** — the bundle's single copy of that rule, linked (`#untrusted-text-echoes`), never restated. **L3 dead:** stop the agent over the harness's agent-termination capability and **re-spawn from `checkpoint`** (C-1205). **One retry per phase. A second death in the same phase marks the work package `failed` and surfaces it — never a third auto-retry.** **Nobody writes a dead agent's beat.** The evaluator stops the agent, retires its id from its own glob, and records the outcome **in the plan's Parallelization-table Status column** — the writer, the column and the vocabulary it already owns. It never writes `failed` into the child's heartbeat file: one writer per heartbeat file is absolute (C-1201), and the "dead" child may be alive enough to write the next beat. The stale file is left on disk for the post-mortem and removed by teardown (C-1216). The one-retry-then-surface shape is where OTP's `intensity`/`period` (defaults `MaxR=1`, `MaxT=5`), Nomad's `restart`, Kubernetes' `backoffLimit` and Temporal's `maximumAttempts` all converge: stop retrying, tell someone. **A missed startup beat (C-1204(i)) is the only L1 that skips straight to L2** — there is nothing to ping, because the agent never announced itself. **L3 on a coordinator stops its children first**, identified by the `parent` field (C-1201): orphaned agents holding worktrees, daemons and containers are the documented failure of every kill path that skips this (`parallel-resource-pitfalls.md` rows 21–22). **This needs no exception clause and no reach-past rule** — the evaluator is the top orchestrator (C-1207) and the directory is flat, so a dead coordinator's children are already in the glob it just read. **Capability classes, never primitive names — *agent messaging* and *agent termination*, detected per run, never stored, each degrade announced as a `Degraded:` line** exactly as `protocol.md` § Worker coordination requires. Where messaging is absent, L1 simply waits out its 3 minutes. Where termination is absent, **L3 does not kill**: it reports the dead agent, marks the work package `failed`, and lets `adr_0010` `C-913`'s cascade govern. | `protocol.md` § Worker coordination › Worker liveness (sole source) |
| **C-1207** | **One contract, one evaluator, every depth visible in one flat read.** A sub-orchestrator (a coordinator) is **a worker like any other for liveness purposes: it writes its own beat** (C-1201) **and runs no ladder.** **The top orchestrator is the sole ladder runner for the whole fleet, at every depth.** This is the correction the 2026-09-05 fix round made to a drafted rule that had each coordinator grade its own children, and the drafted rule was **inert by construction**: C-1211 requires a coordinator awaiting its children to be in state `blocked`, a blocked agent takes no turns, and on C-1208's rung 3 there is no condition-waiting and no scheduled-wake capability — so nobody would ever have evaluated, and the 30-minute silent death would have recurred unchanged. **The heartbeat directory is flat and every beat carries `parent`, so one glob gives the top orchestrator every agent's state at every depth**, and it is the one agent that reliably takes turns: it schedules, it merges, it runs the gates. `C-914` is preserved literally — the *contract* is uniform, the *spawn tree* is unchanged, and no second mechanism, no per-level tuning and no reach-past rule exists because none is needed. | `protocol.md` § Worker coordination › Worker liveness (sole source) |
| **C-1208** | **What a healthy run pays: zero orchestrator turns, on a three-rung ladder mirroring the fan-out ladder.** The **top** orchestrator resolves one of three mechanisms, per run, and **announces which**: **(1) condition-waiting capability** available → arm one wait per spawn wave that returns when the wave completes **or** a beat goes stale. Preferred. **(2) else scheduled-wake capability** → one wake per 5 minutes. **(3) else turn-boundary checks** → the orchestrator globs `${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/hb/*.json` — **the whole directory, unfiltered** — **at each phase boundary and at each turn it takes anyway**. Portable floor: one glob, no polling loop, no background process, **zero added turns**. **Both of those claims — zero added turns and the detection figure — depend on the evaluator being the top orchestrator, whose turn boundaries are real** (C-1207); they did not hold for the drafted per-coordinator evaluator, which was blocked whenever it had anything to evaluate. **On rung 3 the detection figure is bounded by the orchestrator's own turn cadence** and is honestly larger than the armed-capability figure — ~12–15 minutes apart on the RCA's traced run, so ≤ 13 minutes becomes up to ~28. § Quantified impact publishes both. **Rung 3 is not a failure mode**; it is the contract working with no client features at all, and it is what makes the whole of Part 1 satisfy driver 3. Capability classes only — the ladder is gated on *what a client can do*, never on a primitive's name, and each rung's resolution is announced in the same shape as the existing fan-out ladder's `Degraded:` lines. | `protocol.md` § Worker coordination › Worker liveness (sole source) |
| **C-1209** | ~~**The optional enforcement ceiling — offered by `/hex-init`, required by nothing.**~~ **WITHDRAWN in the 2026-09-05 fix round. Ships nothing; the ID is retained so no other contract moves, and constitutional amendment 1 is withdrawn with it.** The drafted contract had `/hex-init` generate an executable post-tool-call hook into the project's own client configuration, as an opt-in enforcement ceiling over the portable prompt floor. **It was cut because it would have been the first time hex writes executable configuration rather than documentation** — for a mechanism nothing requires and nothing measures, paid for with a constitutional carve-out into `DESIGN.md` § Spec-kit comparison round (2026-07-19, round 5), the one non-adopt the constitution names as the moat. **Part 1's portable floor is unaffected**: the beat is a foreground tool call the agent makes itself (C-1204), and no shipped file ever depended on the hook. The reasoning is preserved rather than discarded — the option is recorded as **D-4** and stays available if the beat contract is later *measured* to be unreliable in practice. | — (withdrawn; no landing site) |

### B. The resource contract

| ID | Contract | Home |
|---|---|---|
| **C-1210** | **Two caps, not one — and the API-bound one keeps its frozen name.** **API-bound: the existing `limits.max-workers`.** This ADR does **not** introduce `limits.workers`. `limits.max-workers` is a frozen v1 key (`config.md` § Key vocabulary, the
`limits.max-workers` row, `adr_0003` `C-223`) and **renaming a frozen key is a silent no-op in every consumer `hex.md`** — a rename would leave every configured project running the shipped default while its file appeared to say otherwise. **This is a correction to the sketch this ADR was commissioned from, and it is stated as one.** **Hardware-bound: `limits.heavy`**, a new **leaf under the existing `limits` key** — the same additive move `workflows` made for the v2 vocabulary, and it inherits that move's compatibility story verbatim: a v1 reader treats an unknown key under merge rule 8 (warn once, ignore, continue), which for `limits.heavy` degrades to today's unbounded behaviour rather than to an error. Ceiling-only like its siblings, **defaulting to the derived value in C-1213**, so an unconfigured project reads nothing and gets a measured number rather than a guess. **Justified against `adr_0010` driver 4 head-on:** driver 4 forbids "a key for a value a plan-table cell can carry", and a plan cell **cannot** carry this one — **a plan travels between machines and this value is a property of the host, not of the work.** A 32-core 31 GB desktop and an 8 GB laptop must not read the same number out of the same committed plan. That is precisely why it is config and not a column, and it is the one place in this ADR where a key is the correct carrier. | `config.md` § Key vocabulary (the `limits.heavy` row, v2); enforcement in `protocol.md` § Worker coordination (C-1211) |
| **C-1211** | **What takes a heavy slot, what a slot means, and the cap amendment Part 3 needs to not deadlock.** **Takes one:** `builder:implement`, `tester`, and the **merge and checkpoint verification gates**. **Never:** reviewers, explorers, researchers, doc-writers, architects, or a coordinator between phases. **The slot is held around the documented verification command, not for the worker's lifetime** — a builder *reasoning about code* costs nothing and takes no slot; a builder *running the build* costs a slot for the duration of that command. This is what keeps `limits.heavy` small without starving the fleet, and it is why the semaphore is worker-side (C-1212) rather than a spawn-time gate. **Amendment to `protocol.md` § Worker coordination's recursive counting.** The `min(8, max-workers)` cap counts **live model-compute — agents in state `working`**. **An agent in state `blocked` (waiting on children, on a heavy slot, or on a lock) does not occupy a slot.** Charging a blocked parent against the same pool its children need is the **Airflow `SubDagOperator` deadlock** — the documented reason SubDAGs were removed in favour of `TaskGroup`, a construct with no execution-slot semantics at all — and the identical shape of nested submission to a bounded `ThreadPoolExecutor` ("Deadlocks can occur when the callable associated with a Future waits on the results of another Future") and of unmanaged blocking in a `ForkJoinPool`. **Without this amendment Part 3 deadlocks by construction**, and there is no precedent anywhere for letting the blocked party keep its slot. The cap's other properties are untouched: it is still recursive, still `min(8, max-workers)`, still clamped and announced above 8, still counted across repos in a federated plan with only the lead's value read (`C-318`). | `protocol.md` § Worker coordination (the amended cap bullet, sole source); `workers.md` role index takes a one-clause qualifier naming the heavy roles |
| **C-1212** | **The semaphore — `flock` slots at a host-global path outside every checkout, worker-side, around the command, with a portability ladder and a mandatory wall-clock backstop.** N slot files at **`${XDG_CACHE_HOME:-$HOME/.cache}/hex/locks/heavy-{1..N}`**, `N = limits.heavy`. **Host-global: never worktree-local, and never run-root either.** The semaphore protects a **host** resource — RAM and cores — so its slots must be **host**-scoped, and any path inside a checkout scopes them to that checkout: a lock file inside `.agents/worktrees/<wp>/` is invisible to a sibling worktree, and a lock directory inside one clone is invisible to a second clone of the same project, so both silently become independent no-op locks — "worse than not having a semaphore because it looks correct." **Two projects deriving different `N` do not sum.** A project with `N = 2` only ever locks slots 1..2 and a project with `N = 4` locks 1..4, so a host's maximum concurrent heavy commands is **`max(N)` across live runs, never their sum** — which is the strict improvement the one-path change buys. The residual, sessions that do not share a `$HOME`, is D-1. **The path is resolved once by the orchestrator and passed absolute in every spawn prompt, and a worker never re-derives it — C-1201 states that rule once for every path under this root and it is referenced here, not restated.** What is specific to this contract is the *consequence* of breaking it: a worker expanding `${XDG_CACHE_HOME:-$HOME/.cache}` for itself would land inside its own run's scratch (C-1215) and get **per-run slots**, which is precisely the no-op semaphore this contract exists to prevent. The lock directory and the per-run scratch roots are siblings under `${XDG_CACHE_HOME:-$HOME/.cache}/hex/`; a run id is a timestamp-slug and never collides with `locks`. **Worker-side, acquired in the same shell invocation that runs the heavy command** (the `( flock -n 9 \|\| exit <code>; cmd 9>&- ) 9>slot` form), never in a wrapper that then backgrounds the real command. **The semaphore fails closed, and this is the contract's single most important sentence.** Every acquisition is checked: `flock -n 9 \|\| exit <busy code>` on the scan and **`flock -w "$QUEUE_WAIT" 9 \|\| exit <code>`** on the bounded wait. An unchecked `flock -w` followed by the command is the shipped idiom's original defect — a **timed-out wait would run the command unlocked**, so under exactly the saturation the semaphore exists for, every waiter falls through at once and the OOM class returns in full. **A failed acquisition must never reach the command.** Terminal outcome on expiry: the worker writes a `failed` beat naming the exhausted wait, returns the failure in its structured result, and the orchestrator surfaces it — **it never silently proceeds, and it never retries the command unlocked**. **The command runs with the lock descriptor closed for descendants (`9>&-` on the command, the subshell still holding it)**, so a build tool that daemonizes cannot inherit the descriptor and hold the slot after the run ends; with `heavy` clamped to 1 on a small host, one leaked slot wedges every later run sharing `$HOME`. **The recovery path is stated rather than left to be discovered:** a slot that no live agent reports holding is reclaimed by identifying the holder with `fuser`/`lsof` on the token and stopping it, never by unlinking the token (see below). **No lock convoy.** An overflow waiter uses a **short bounded `flock -w`**, and **on timeout it re-enters the full non-blocking 1..N scan** rather than continuing to block on one designated slot — a waiter pinned to slot 1 collapses N-way capacity to 1-way throughput under precisely the contention the semaphore exists to relieve. **`$WALL` and `$QUEUE_WAIT` ship stated defaults** so the idiom is runnable on a project with no measured profile: **`$WALL` = 4 × the measured gate wall time, floor 600 s, default 1800 s where no profile exists**; **`$QUEUE_WAIT` = 60 s per bounded attempt**, re-scanning between attempts, with a total queue budget of `$WALL`. **Write permission is not assumed:** a worker must be able to create files under the run's runtime root and under the lock directory; a failed token creation is announced as a `Degraded:` line and the run proceeds **without** heavy concurrency (`heavy` forced to 1 and the gate serialized), **never as a silent unlocked run**. **`flock` is the primary because its crash-safety is a kernel guarantee**: the lock attaches to the *open file description* and is released when the last referencing descriptor closes, **including on `SIGKILL`**, so an OOM-killed build never wedges a slot. A `mkdir` lock survives its holder's death and needs stale detection with a PID-reuse race `flock` structurally cannot have — that is the crux of the choice and it is argued in § Considered Options rather than asserted. **Portability ladder, each rung detected per run and each degrade announced:** **(1)** `flock(1)` present → use it; **(2)** else `python3` present → `python3 -c` with `fcntl.flock`, the same kernel guarantee at the cost of a process spawn; **(3)** else `mkdir` slot directories **plus a mandatory PID-file staleness check** (`kill -0`) — crash-unsafe, announced as a degrade, and shipped with the documented manual unwedge (`rm -rf` the slot directory) because a contract that can silently wedge itself with no recovery path is worse than one with no semaphore. **Two hazards written into the contract.** **(a) fd inheritance:** a child that inherits the locked descriptor holds the lock after the parent exits — heavy commands that spawn daemons (Gradle, testcontainers) must close the descriptor or run under a fresh one, which is why the knob sheet's `--no-daemon` and `gradlew --stop` entries are part of this contract's surface and not decoration. **(b) token lifetime:** the `heavy-{1..N}` files are **zero-byte and permanent — never deleted, by teardown or by any sweep** (C-1216). Unlinking a token another agent currently holds is a correctness bug, not a tidiness win: the holder's lock lives on the open file description of an inode that then has no name, the next `open()` of the same path creates a **fresh inode**, and two holders both believe they own that slot. Empty files cost nothing; deleting them costs mutual exclusion. **One filesystem probe on the resolved lock directory, and a degrade rather than a relocation.** Moving the slots out of every checkout removes the *checkout's* location from the question, but `$HOME/.cache` is not guaranteed local: a user-set `XDG_CACHE_HOME`, an NFS or SMB home, or a WSL2 `$HOME` under `/mnt/c` all defeat a "structurally unreachable" claim — and over NFS `flock` is emulated as **fcntl byte-range locks, which do not carry the open-file-description release semantics the whole rung-1 choice rests on**. The contract therefore keeps **one line: probe the resolved lock directory's mount type once, and where it is not a local filesystem, announce `Degraded: heavy semaphore on a non-local filesystem — crash-release not guaranteed`.** **No relocation rule is restored** — a probe plus a `Degraded:` line is enough, and a relocation rule would reintroduce the per-checkout scoping this contract exists to remove. **Always wrap the heavy command in a wall-clock backstop**: `timeout --kill-after=10s` → `gtimeout` → `perl -e 'alarm shift; exec @ARGV'`. **This is the one rung with no acceptable "unavailable" outcome** — Perl with `alarm` ships on every target platform's base install — and the Perl form loses the two-stage TERM-then-KILL escalation, which the contract states rather than claiming parity. | `resources.md` § Heavy-command semaphore (sole source); linked from `protocol.md` § Worker coordination |
| **C-1213** | **The measured resource profile — measured once, cached as a pointer, clamped, and never fabricated.** `/hex-init` runs **the project's documented verification gate once** under a peak-RSS measurement and records the result in `hex.md › Pointers`: **peak RSS, wall time, and a class of `light` or `heavy`**. `light` means parse-only — arcana's `grim build` is the worked example. **Portable measurement, detected not assumed:** `/usr/bin/time -v` (GNU, kbytes) → `/usr/bin/time -l` (macOS/BSD, bytes) → `gtime -v`, each **probed with a no-op first** (`/usr/bin/time -v true`) rather than branched on `uname`, because a minimal Linux image can carry only the BSD-flavoured binary. **Where none is reachable, no number is fabricated**: the profile is recorded absent, `limits.heavy` falls back to **1**, and the degrade is announced. **Derivation:** `heavy = clamp( floor( (RAM − headroom) / peakRSS ), 1, nproc )` with `headroom = max(2 GB, 25% of RAM)`. **`RAM` is cgroup-effective, not host-total, and the contract says so rather than leaving it to an implementer.** `RAM = min(hostRAM, cgroupLimit)`, where `cgroupLimit` is read from **`/sys/fs/cgroup/memory.max` (v2)** or **`/sys/fs/cgroup/memory/memory.limit_in_bytes` (v1)** where either is present **and finite** (`max`, or a v1 sentinel near `2^63`, means unlimited and the host total stands). Without this clamp the design reproduces the pre-container-aware-JVM bug class ([JDK-8146115](https://bugs.openjdk.org/browse/JDK-8146115)) **inside the devcontainers this ADR claims to support**: a 4 GB container on a 128 GB host would derive a `heavy` sized for the host and be OOM-killed by its own cgroup. `nproc` is read the same way where a CPU quota is set. **The clamp is not decoration.** Bazel derives its local RAM budget as a fixed fraction of host RAM and **its own tracker documents that fraction misfiring at both 8 GB and 256 GB** — a bare fraction is wrong at both ends of the range, which is exactly what the clamp bounds. **A `light` gate is unbounded**: it never takes a slot and `limits.heavy` is not consulted for it, so a parse-only project pays nothing for this contract. **The pointer is a cache, never authoritative**, and is re-measured at upkeep when it drifts, per `memory.md` § Staleness's verify-on-consumption rule. | `hex-init/references/audit.md` (new item, "Resource profile measured?"); `memory.md` § the three sections (the `## Pointers` enumeration gains the row); derivation in `resources.md` (sole source) |
| **C-1214** | **Preflight before every spawn wave — three checks, under 2 seconds, hold never spawn, and a missing check is never a passed check.** Before **every** spawn wave, the orchestrator runs **three** checks in under two seconds. **On any trip: hold, never spawn.** **(1) Disk available on the worktree and scratch volumes.** The threshold is **derived, not invented**: `max(5 GB, measured per-worktree artifact size × the wave's width)`, where the per-worktree size comes from the same `/hex-init` measurement as the resource profile (C-1213) and defaults to the research's own observed range (`parallel-resource-pitfalls.md`: **10–18 GB of `target/` per worktree**, 61 GB across four live worktrees) where nothing is measured. **A flat `< 5 GB` was invented and is demonstrably too low** — a three-WP wave passes it at 6 GB free and then fills the disk — so 5 GB survives only as a **floor**. **(2) Memory pressure**, `/proc/pressure/memory` `full avg10` — hold above **10%**. **(3) Stale worktrees** — hold on any worktree not in the plan's active set. **Three checks were cut in the 2026-09-05 fix round, each for a stated reason.** *Load average* is contradicted by this design's own research — an LTO/linker RSS spike of 7–30 GB happens while loadavg looks idle, so the check would pass at exactly the moment that matters and hold at moments that do not. *inotify watches and instances* has a real failure mode, but that failure mode is the **human's editor or indexer**, which a 60-second hold cannot relieve; it can only burn all three holds and surface, which is a slower way of reaching the same surfacing. (The underlying exhaustion is still worth telling a project about, and it is: it is an `/hex-init` audit item, not a per-wave gate.) *File-descriptor headroom* named **no threshold**, and a check with no threshold is not a check. **A hold waits 60 s and re-checks, at most 3 times, then surfaces to the human rather than holding forever** — an orchestrator that waits indefinitely on a machine the human is also using is a hang, not a safeguard. **Non-Linux hosts skip the checks whose sources do not exist** — `/proc/pressure` is Linux-only — **and announce the reduced set. A missing check is never reported as a passed check**, because the whole value of the preflight is that its output is believable. **Home: `protocol.md`, not `resources.md`.** Preflight is **scheduling, not a resource knob**, and `resources.md` is conditional-load "only when a run will issue a heavy command" — so leaving it there would mean a parse-only project never runs the disk or stale-worktree checks, which are exactly the two that do not care whether the gate is heavy. | `protocol.md` § Worker coordination (sole source, carrying the three-check table, beside the spawn-wave step); `resources.md` keeps the knob sheet and the containment ladder and links here |
| **C-1215** | **Per-run scratch environment — disk-backed, three variables, and neither `HOME` nor `XDG_CONFIG_HOME` among them.** `TMPDIR`, `XDG_CACHE_HOME` and `XDG_STATE_HOME` are redirected to a **disk-backed per-run root**, `${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/<wp>` — a sibling of the run's heartbeat directory `…/hex/<run-id>/hb/` (C-1201), both under the one run-scoped root the teardown already owns. **`XDG_CONFIG_HOME` was dropped from the set in the 2026-09-05 fix round, and the reason is supply-chain, not convenience.** Redirecting it silently detaches git and the package managers from the developer's own configuration: `credential.helper`, `commit.gpgsign`, and — the two that matter most — **`url.*.insteadOf` rewrites and registry/index pinning**. Losing `insteadOf` and index pinning means a run silently resolving dependencies from somewhere the developer deliberately redirected *away* from; that is a **supply-chain downgrade**, not merely a broken push, and it is not worth the handful of config-directory writes the redirect would contain. `TMPDIR`, `XDG_CACHE_HOME` and `XDG_STATE_HOME` carry the whole disk-and-tmpfs argument on their own. **Disk-backed is the point, not an implementation detail:** `/tmp` is commonly a tmpfs sized at 50% of RAM — on the measured host a **64 GB tmpfs on 31 GB of RAM** — so "the disk filled with test artifacts" is an out-of-memory event wearing a disguise. **`HOME` is not redirected by default.** Redirecting it breaks every tool that reads real credentials from it — git identity, `gh` auth, cargo registry tokens, ssh — and a run that fails to push because hex moved `HOME` is a worse outcome than a suite that writes a few files under the real one. **The trade-off runs in both directions and the contract states both.** Not redirecting `HOME` is availability-positive and **security-negative**: hex runs a possibly hostile repository's own documented verification command, N-way concurrent and unattended, with read access to `~/.ssh`, `~/.config/gh` and `~/.aws`. The default is judged right — breaking the common case for every project to contain the uncommon one is the worse error — but the exposure is **traded, not absent**. It is offered as a **per-project opt-in through a `/hex-init` audit item**, and that item names **two** reasons to take it: a suite known to write to `$HOME`, and **credential exposure to a verification command the project does not fully trust**. **This is a deliberate departure from the sketch's five-variable set and from `parallel-resource-pitfalls.md`'s own recommendation**, and the reason is stated rather than left implicit. **The scratch root is deleted by the orchestrator's teardown, never by a worker `trap`** — `SIGKILL` skips traps, which is the documented reason orphan cleanup must not live in the worker. | `resources.md` § Per-run scratch (sole source); `workers.md` § Universal worker protocol gains the "run under the per-run scratch env" rule; `hex-init/references/audit.md` for the `HOME` opt-in |
| **C-1216** | **Teardown ownership — the orchestrator owns everything the run produced, and sweeps rather than deletes on ambiguity.** The orchestrator's teardown owns: the **worktree**, **redirected build directories**, **caches**, the **scratch root** (C-1215), the run's **heartbeat directory** at `${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/hb/` (C-1201) — a sibling of the scratch root under the same run-scoped parent, and **outside every checkout** — **daemons** (`gradlew --stop`), **containers**, and **the process groups it recorded**. It never lives in a worker, for the reason above. **Three safety rules, because every one of them is a line an implementer will transcribe literally.** **(1) Containers: `docker container prune -f --filter label=<the run's own label>`, and nothing wider.** `docker system prune -f --volumes` is **not** used and is not a scoped command: it destroys every unused volume, network, dangling image and stopped container **on the machine**, including a developer's unrelated work, and "scoped to the run's own labels" had no mechanism behind it because nothing labelled anything. `system` and `--volumes` are dropped outright. **Container pruning happens only when the run itself set that label** on the containers it started; where it did not, **teardown reports the leftovers and deletes nothing**. **(2) Process groups: only groups this run created.** "Kills the process group" is undefined and dangerous — an agent's shell typically shares a process group with the harness, so `kill 0` or `kill -- -$$` kills the harness or the user's own shell. Instead: **every heavy command is started under its own process group (`setsid`), its group id is recorded at spawn, and teardown signals only recorded group ids.** **Teardown never signals a process group it did not create.** **(3) Every delete target is minted and prefix-checked.** `<run-id>`, `<agent-id>` and every slug reaching an `rm -rf` target or a composed shell are **orchestrator-minted**, slugified to `[a-z0-9][a-z0-9-]{0,63}`, and **never taken verbatim from a plan cell or a filename** (C-1201 states the minting half). **Teardown additionally refuses any delete target that does not resolve — after symlink resolution — under its own run-root prefix `${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/`, or under the worktree root the run created.** A target that resolves outside both is reported and skipped, never deleted; this is the backstop that holds even if the minting rule is bypassed by a future caller. **One explicit exception, and it is a correctness rule rather than an oversight: the heavy-slot token files at `${XDG_CACHE_HOME:-$HOME/.cache}/hex/locks/heavy-{1..N}` are never deleted — not by teardown, not by the start-of-run sweep, not by any cleanup this ADR or any later one adds.** They are zero-byte and permanent (C-1212). Unlinking a token another agent currently holds breaks mutual exclusion outright: that holder's lock lives on the open file description of an inode that now has no name, the next `open()` of the same path creates a **fresh inode**, and two agents then both hold "slot 3" and run their heavy commands together. A handful of empty files is the cheapest thing on the disk, and deleting them is the one teardown action that can corrupt a running fleet. **Sweep-and-warn on start, and the rule is now decidable rather than a judgment call:** **another run's directory is reported, never deleted; a run deletes only its own `<run-id>` subtree.** `<run-id>` is what makes this decidable — it is in the path (C-1201, C-1215), so "unambiguously this run's own" is a string comparison rather than an inference, which is precisely the second defect the in-tree path had. This is the same "never delete on ambiguity" rule the project already applies to worktrees. The cost of getting this wrong in the other direction is documented: orphaned agent, MCP and browser processes after crashes hold tens of GB, and Cursor's own forum records 140 GB per week of unpruned worktrees. **This is the cleanup lifecycle `C-912` said a second location would need** — it exists here for worktrees, daemons and containers regardless of the heartbeat directory, which rides it rather than motivating it. | `protocol.md` § Worktree work-package mechanics (teardown amendment); `resources.md` (the teardown checklist) |
| **C-1217** | **Worker output is a resource signal — triaged three ways, because only one of the three may move the cap.** A wait on a lock is not one situation but three, and grading them alike would collapse `heavy` to 1 on the first busy wave of **every** run, because hex's own semaphore produces lock waiting **by design**. **(1) Waiting on hex's own heavy slot — expected, and not a signal at all.** That wait *is* the semaphore working; the agent is already in state `blocked` with `blocked_on: heavy-slot` (C-1202). **No action, no log entry as a signal, `heavy` unchanged.** **(2) A build tool's own lock wait — a *configuration* fault, not a memory fault.** Cargo's `Blocking waiting for file lock`, a Gradle daemon lock (`parallel-resource-pitfalls.md` row 10) and their siblings mean **two agents are sharing one build directory**, which the per-worktree artifact rows of `resources.md`'s knob sheet exist to prevent. **Warn, naming the shared directory; do not lower `heavy`** — lowering concurrency does not un-share a target directory, it only makes the run slower while the misconfiguration stands, and it hides the actual fault behind a throughput loss. **(3) Resource-exhaustion evidence — the only class that moves the cap.** An out-of-memory kill, a V8 `heap out of memory`, a `dmesg` OOM line, inotify `ENOSPC` (watch exhaustion, which fewer concurrent heavy commands genuinely relieves), or **a heavy command exceeding its measured profile × 1.5** (C-1213). **Corroboration from a host source is required before `heavy` moves.** The classified token alone is not enough: the orchestrator additionally reads **`/proc/pressure/memory`, `dmesg`, or the measured-profile overshoot** — sources the *host* owns, not the repository — and lowers the cap only when one of them agrees. Without this, text a hostile repository plants in its own build output could walk a run's concurrency down to 1, which is a denial-of-service against every later work package for the cost of one string. Where no host source is readable (a platform with no `/proc/pressure`, no `dmesg` access), the evidence is **logged and surfaced, and `heavy` does not move** — a missing corroborator is never a passed one, the same rule C-1214 applies to preflight. On corroborated evidence the orchestrator **lowers `heavy` by one for the remainder of the run and logs it**; the floor is 1. **The distinction, stated once:** contention on hex's own semaphore is the design, contention on a build tool's lock is a misconfiguration, and memory exhaustion is the only thing that should move the cap. **None of the three is ever retried as a flake** — a retry under the same conditions reproduces the same exhaustion and burns a second full run to learn nothing. **The worker classifies; the orchestrator never re-parses raw build output.** Build output is **repository-controlled text**, and routing it into the orchestrator's context to key a control decision on is the exact shape `protocol.md` § [Untrusted-text echoes](#untrusted-text-echoes) exists to forbid — the bundle's single copy of that rule, linked here and at C-1206's L2 discriminator, never restated. So the **worker** decides which of the three classes it is in and returns **one bounded, classified token**: `oom-evidence: "<≤ 120 chars, quoted>"` for class 3, `lock-evidence: "<≤ 120 chars, quoted>"` naming the shared directory for class 2, and **nothing at all** for class 1. **Never raw output for the orchestrator to re-parse, and never an unbounded echo.** The triage still keys on which lock produced the wait — but that judgment is made where the output is, by the agent that ran the command, and only its verdict crosses the boundary. Precedent: Jest's `--workerIdleMemoryLimit` recycles on a threshold rather than only capping at start — the cap at start is a guess, the threshold is a measurement. **The lowered value is run-scoped and never written back to config**: `limits.heavy` is the user's, and a single bad run does not get to edit it. | `workers.md` § Universal worker protocol (classify and return a bounded token); `resources.md` § Output signals (the orchestrator's reaction and the host-corroboration rule, sole source); `protocol.md` § Untrusted-text echoes (linked, never restated) |
| **C-1218** | **The new reference file, conditionally loaded — and the artifact-set change it brings.** **`hex-core/references/resources.md`** is added: the **trimmed knob sheet** (per ecosystem: parallelism default, cap knob, per-worktree artifact, redirect, retention), the **preflight table** (C-1214), the **semaphore** (C-1212), the **scratch env** (C-1215), the **teardown checklist** (C-1216), the **output signals** (C-1217) and the **containment ladder**. **Conditional-load, in the shape `config.md` already uses**: read it **only when a run will issue a heavy command**, so a parse-only project never pays its bytes. Linked from `protocol.md` § Worker coordination. **It is a knob sheet, not a policy — hex still never defines how to verify a project**; every row records what a tool's knob is called, never which value a project should choose. **Containment ladder, detected per run, each degrade announced:** `systemd-run --user --scope -p MemoryMax=` (detected with `command -v systemd-run` **and** `[ -d /run/systemd/system ]` **and** a user-bus probe — the directory test is the man-page-blessed shell equivalent of `sd_booted(3)`) → **raw cgroup v2 writes on an already-delegated user subtree** → **`nice`/`ionice`** (blast-radius reduction, no cap) → **nothing but the wall-clock backstop**. **Never `ulimit -v`/`RLIMIT_AS` for compiled languages** — it breaks rustc's parallel front end and JVM/Go address reservation; cgroup `memory.max` is the correct bound. **Never `cgcreate`** (libcgroup is v1-only and deprecated under the unified hierarchy). **Artifact set and release:** `hex/publish.toml` takes a **minor** bump (additive reference file, one new config leaf, no member removed, no breaking change); `hex/CHANGELOG.md` gains a section with `### Added` (liveness contract, `limits.heavy`, `resources.md`, per-WP coordinator pipeline, run telemetry) and `### Changed` (the recursive concurrency count, the coordinator gate); `hex/DESIGN.md` gains one dated round; `hex/README.md` gains one line naming the liveness and resource contracts. **`hex.toml` / `grimoire.toml` are unchanged — `resources.md` is a reference inside the existing `hex-core` member, not a new member.** | `hex-core/references/resources.md` (new file, sole source); `hex/publish.toml`; `hex/CHANGELOG.md`; `hex/DESIGN.md`; `hex/README.md` |

### C. Per-work-package sub-orchestration

| ID | Contract | Home |
|---|---|---|
| **C-1219** | **The per-WP sub-orchestrator IS the existing coordinator — and the one gate splits into two questions.** **No new role. No new level. No new state.** The per-WP sub-orchestrator is the `coordinator` already defined in `workers/coordinator.md`. What changes is **when it is spawned** and **what it runs**. **Today:** a WP qualifies only when it holds "≥3 independent, WP-grain sub-tasks" and is decomposable (`hex-execute/SKILL.md` § Coordinator spawn, `workers/coordinator.md` §
coordinator's Preconditions paragraph), the conservative default is a
single builder, and the coordinator fans out **implementation**. **Under this ADR:** a coordinator **owns each ready work package** and runs **that package's whole phase pipeline** — stub → specify → implement → the review-fix loop — spawning leaves per phase. The parent orchestrator **only schedules, merges serially in topological order, and runs the gates**. **The ≥ 3-sub-task gate is not deleted; it is re-scoped.** It keeps deciding whether a coordinator **further decomposes its work package into dotted sub-WPs** — the second question, unchanged in every byte. **Two different questions that happened to share one gate, and this contract separates them explicitly:** *(Q1) does this WP get a coordinator?* — **yes when the ready set holds ≥ 2 WPs and the harness can nest** (C-1220 gives the exceptions); *(Q2) does that coordinator split into sub-WPs?* — the existing ≥ 3-independent-sub-task judgment, unchanged. **This is the single most reviewable claim in Part 3 and it is stated, not implied.** **`C-914` holds literally**: depth is still `orchestrator → coordinator → leaf`, there is still no new orchestrator role, and **no orchestration state is added** — the heartbeat is liveness, not state a resume walks (C-1201 condition 3). The coordinator's own unchanged rules continue to bind: sub-WPs are ordinary dotted rows in the one flat Parallelization table, inside the WP's single worktree with no sub-branches, the file-set intersection check is re-run at split time, and every sub-WP passes the centralized verify gate at the join. **The behavioural riders the word *coordinator* carries today are enumerated here, every one of them, and each is assigned to Q1 or to Q2 — reusing the identity is what would otherwise drag them in silently.** **(i) The `join` full post-merge verification trigger** (`protocol.md` §
Worktree work-package mechanics, `adr_0010` `C-901`) — **Q2 only**. A pipeline coordinator's merge pays the same scoped check any other WP's does; without this split every merge in the run would pay the ~25-minute full gate instead of the 1m32s scoped check the RCA logged. **Amendment 6.** **(ii) The `M = 3` checkpoint-counter reset on a coordinator join** (`protocol.md` § Checkpoints) — **Q2 only**. A pipeline coordinator
performs no join, and under Q1 the reset would fire on every work package, so `adr_0010`'s counter could never reach `M`. **Amendment 6.** **(iii) "A coordinator WP is by definition `panel` — `self`/`light` WPs never qualify for a coordinator"** (`hex-execute/SKILL.md` § Coordinator spawn) — **neither kind**. The rider is deleted outright: **review breadth stays the work package's own budgeted `Review` value** (`adr_0010` `C-905`, and `adr_0012`'s per-WP effective tier) whatever kind of coordinator owns it. **Amendment 7.** **(iv) The `deep-reasoning` capability class and the medium/high tier gate** (`workers/coordinator.md` § coordinator, the Tools/Model paragraph;
`models.md` § The matrix and § Rules, rule 5) — **Q2 only**. A **pipeline** coordinator resolves to **the work package's own effective tier** (`adr_0012` `C-1109`, `C-1110`); a **decomposing** coordinator keeps the deep-reasoning class and the medium/high gate unchanged. **Amendment 8.** **(v) The tiny 1-round spec+quality join loop** (`workers/coordinator.md` § coordinator, the Join paragraph's 1-round
spec+quality loop) — **Q2 only**; a pipeline coordinator has no join to run
it at. **(vi) Leaves run a scoped compile check rather than the documented verification** (`workers/coordinator.md` § coordinator, the Join paragraph's
leaf-compile-check sentence) — **Q2 only**; a pipeline coordinator's leaves
are ordinary phase leaves and run the phase's documented gate. **Seam with `adr_0012`, one-directional no longer.** `adr_0012` decides **which phases a work package runs and at what model class and review breadth**; `adr_0013` decides **how the workers running them are supervised, resourced and sub-orchestrated**. Concretely: **a pipeline (Q1) coordinator does not raise a work package's effective tier.** `adr_0012` `C-1109`'s coordinator floor (`min(T, medium)`) and the sub-WP inheritance of `C-1104` apply to the **decomposing (Q2)** kind only, so `adr_0012` `C-1108`'s collapse still fires on a `low` work package that has a pipeline coordinator — which it could not if Q1 raised the floor, since Q1 gives a coordinator to every ready WP. `C-1110`'s `min` cap over the result is untouched, and rider (iii)'s deletion is what keeps `C-1112`'s `Review: panel` escape hatch from re-raising every coordinator-owned WP to the ceiling. | `hex-execute/SKILL.md` § Coordinator spawn (the gate split, sole source for Q1); `workers/coordinator.md` — **Mission** (amended to name the pipeline), **Preconditions** (become Q2, otherwise unchanged byte for byte), **the Join paragraph's 1-round join loop and leaf-compile-check sentence** (scoped to Q2), **the Tools/Model paragraph** (scoped to Q2, amendment 8); `hex-core/references/models.md` — the `coordinator` row and its rule-5 tier gate (amendment 8) |
| **C-1220** | **When a coordinator is not spawned — two cases, both of which degrade to today's behaviour.** **(a) A ready set of exactly one work package** → the parent runs the pipeline **inline**. There is no parallelism to buy, and a level of indirection costs a spawn and a context copy for nothing. **(b) The fan-out ladder's degraded-flattening rung** (`protocol.md` §
Worker coordination) — the harness cannot nest at all → no coordinators, every WP runs a single builder plus the normal per-WP panel, announced with the existing `Degraded: flat execution — no nested spawn; coordinators inlined` line. **In that rung Part 3 becomes today's behaviour, which is the correct degradation, not a failure.** No new degrade line is invented: Part 3 is gated on a capability class hex already detects and already announces. **Where `adr_0012` `C-1108` collapses a small work package's pipeline to a single phase, C-1220(a)'s inline rule reads as covering that case too** — a one-phase pipeline is not worth a coordinator either. **The seam is stated by contract id, not by name.** `adr_0012` decides **which phases a work package runs and at what model class and review breadth** (`C-1104`, `C-1108`, `C-1109`, `C-1110`); this ADR decides **how the workers running them are supervised, resourced and sub-orchestrated**. Neither reads a field the other adds, and **the coordinator this contract declines to spawn is a *pipeline* coordinator, which never raises a work package's effective tier** — `adr_0012` `C-1109`'s floor is scoped to the decomposing (Q2) kind, so declining or spawning one changes nothing in `adr_0012`'s derivation (C-1219). | `hex-execute/SKILL.md` § Coordinator spawn |
| **C-1221** | **Concurrency allocation across the hierarchy — guaranteed floor plus borrowing, partitioned at schedule time.** Every live coordinator gets a **floor of 1 leaf slot** it can never be starved of. It may **borrow up to a ceiling** from the unused share of idle siblings. **Allocation is partitioned per wave at schedule time, never contended at runtime** — this is hex's existing rule ("the orchestrator hands each coordinator a **fan-out budget** no larger than its slot's share", `protocol.md` § Worker coordination) promoted from an implementation detail to a **named hard invariant**, because it is the structural reason hex does not already have an Airflow-shaped deadlock. **Blocked agents do not count** (C-1211). This is the shape hierarchical token buckets (`rate` + `ceil`) and YARN's CapacityScheduler (`capacity` + `maximum-capacity` + elasticity) independently converge on, and it is the **opposite** of first-come-first-served quota — vanilla Kubernetes `ResourceQuota`, explicitly "first-come-first-served with no borrowing semantics", is the documented starvation anti-pattern, not a competing design. **Effective parallel work-package count = `min(\|ready set\|, effective max-workers)`**, and **for phases whose leaves run heavy commands, additionally bounded by `limits.heavy`** — the two caps compose, they do not substitute for one another. | `protocol.md` § Worker coordination (sole source, beside the existing fan-out-budget rule) |
| **C-1222** | **What `adr_0013` does not decide — a stated boundary, so two in-flight ADRs do not collide.** **The ownership split in one line: `adr_0012` decides which phases a work package runs and at what model class and review breadth; `adr_0013` decides how the workers running them are supervised, resourced and sub-orchestrated.** This ADR decides **that a coordinator runs the work package's pipeline** and **how many run at once**; the **pipeline's shape** is `adr_0012`'s (`C-1104`, `C-1108`, `C-1109`, `C-1110`) and is referenced, never pre-empted. Concretely, nothing in Part 3 names a phase list, a model class per phase, a review breadth, or a round count — every such value is read from whatever `adr_0012` resolves for that work package, and **a pipeline (Q1) coordinator does not raise that resolution** (C-1219). **Nor does this ADR touch the pipeline *depth* that root cause 1 names**: the ≥ 7 serial round trips are `adr_0012`'s lever, which is why § Quantified impact's after-figure is **135–150 minutes** rather than the RCA's ≤ 30 min target. **The two ADRs are independently landable** in either order: Part 3 with today's phase list is a wall-clock win, and `adr_0012` with today's single-threaded parent is a wall-clock win, and neither reads a field the other adds. | this ADR (a stated boundary); `adr_0012` |

### D. Run telemetry

| ID | Contract | Home |
|---|---|---|
| **C-1223** | **One writer, one place — no new file, no new writer, no concurrency question.** **The parent orchestrator writes the plan's `## Schedule log`, and it is the only writer of anything this part adds.** It has both numbers already: it **brackets what it runs itself with `date -u +%FT%TZ`** — the pattern `adr_0010` already ships (`protocol.md` § Parallel-by-default
decomposition, the schedule-log bullet's Capture clause) — and it reads each work package's per-phase timings out of **the single synthesized structured result its coordinator already
returns** (`workers/coordinator.md` § coordinator, the Return template),
which gains fields rather than a file. The parent knows when a work package became runnable and when its coordinator was spawned, which is C-1225's `wait_ms` at work-package grain. **The drafted many-writer JSONL spool at `<run root>/.hex/run.jsonl` was deleted outright in the 2026-09-05 fix round**, for a wrong premise and then for a better reason. *Wrong premise:* its stated correctness condition was `pipe(7)`'s `PIPE_BUF` contiguity guarantee, which **POSIX scopes to pipes and FIFOs**, not to regular files; the applicable regular-file guarantee is `O_APPEND`'s own atomic-offset rule, which carries **no size bound** and is filesystem-dependent (open(2) warns it is unsafe on NFS). *Better reason:* **nothing needed it.** With it went the line-size rule, the truncation rule, the spool's failure modes, its `.gitignore` line, and the telemetry half of amendment 2 — **this part now adds no file to any checkout and no writer to any run**. **Concurrent markdown edits stay forbidden**: a markdown section edit is read-modify-write, N concurrent writers lose updates undetectably (axis 4, option T2), and `adr_0010`'s existing merge-entry writer is already the parent, so it simply stays the only one. **The parent renders one `phase` line per phase into `## Schedule log` at merge time**, keeping the plan the sole durable record exactly as `C-912` requires. **No hand-maintained second log:** every dual-output precedent surveyed renders the human view *from* the structured one — Cargo's `--timings` report from its own unit-timing data, `journalctl` from the journal — and here the structured source is one the run already has. **A coordinator that dies before returning takes its work package's unreturned phase timings with it.** That is **telemetry only**: merges, gates, the plan's Status column and the parent's own merge brackets are all unaffected, and the handoff says which figures are missing rather than estimating (C-1226, D-5). A second store to survive it is exactly the spool this round deleted. | `protocol.md` § Parallel-by-default decomposition › Schedule log (amended, sole source); `workers/coordinator.md` § coordinator, the Return template (the existing
structured return gains per-phase timing fields) |
| **C-1224** | **The extended `## Schedule log` grammar — a second line kind, discriminated by the first word after the first `·`, with the compatibility filter made explicit.** **Both line kinds are written by the parent orchestrator and by nobody else** (C-1223). **The existing line is unchanged, byte for byte:** `- <ISO-8601 UTC> · merged <WP> @ <post-merge SHA> · verify <scoped \| full(<trigger>)> [<elapsed>] · ready: <ids \| —> · blocked: <id (<blocker>), … \| —>`. **A second line kind is added**, discriminated by **the first word after the first `·`**: `- <ISO-8601 UTC> · phase <WP>/<phase> · model <class> · work <elapsed> · wait <elapsed> [· rounds <n>]`. **The discriminator is stated that way deliberately** — a whitespace tokenizer's *second token* is the ISO-8601 timestamp, so "the second token" would name the wrong field and any consumer implementing it literally would match nothing. **Compatibility is stated as a contract, not left implicit: existing consumers read only lines whose first word after the first `·` is `merged`.** `adr_0010` `C-904`'s bisection walk is the consumer that matters — it reads post-merge SHAs out of this section, and a `phase` line carries none — so **the filter is written into `protocol.md` beside the grammar rather than inferred from the fact that `phase` lines happen to look different.** `<class>` is a **capability class** (`fast-balanced` / `deep-reasoning`), **never a literal model name**, per `adr_0001` `C-002` and `models.md`. The section stays **append-only and never reordered**, as today. **Presence-checked, never versioned** (`adr_0010` `C-915`): a `## Schedule log` with no `phase` lines is a pre-`adr_0013` run, never an error, and no `Plan-Schema:` field is added or may be inferred. | `protocol.md` § Parallel-by-default decomposition › Schedule log (sole source); the plan template's grammar comment |
| **C-1225** | **The per-phase field set — and the one this design exists to capture.** The fields survive the spool's deletion unchanged in substance; **they now describe what the parent writes into the plan** (C-1223) and what a coordinator returns to it, not lines in a file. Per phase: `ts`, `run`, `wp`, `phase`, `event` (`start` \| `end`), `model` (**capability class, never a literal model name**), `agent`, `work_ms`, `wait_ms`, and `rounds` on review phases. **`wait_ms` — queue time separated from work time — is the field this design exists to capture.** The RCA reconstructed by hand that **53 of 186 minutes (≈ 28%)** of the traced work package's wall clock was *waiting* — the `03:46 → 04:39` tail — and **that reconstruction is what made root cause 4 visible at all**. (An earlier draft carried 69 minutes here; it double-counted the 16-minute wait already charged to the preceding `03:30 R2 quality` row. See § Quantified impact.) A telemetry design that records only work time cannot answer the question that motivated it, and the queue/work split is documented as "the one most often missing and most often decisive" across build and delivery telemetry. **`wait_ms` has exactly one definition and no other: the interval from *the phase became runnable* to *the phase's worker began work*.** Every other formulation in this ADR is that same interval named at a coarser grain — a work package's first phase becoming runnable and its coordinator beginning work is the work-package-grain instance of it, not a second meaning. Where the start is unknown the field is **absent, never zero** — a fabricated zero is worse than a gap, because it is indistinguishable from a real one. **Field naming may borrow OpenTelemetry's GenAI attribute names where they fit** (`gen_ai.agent.id`, `gen_ai.operation.name`), so a future migration to real spans is a rename rather than a redesign; **those conventions are still maturity level "Development", so borrow the names, not the wire format**, and take no SDK dependency. | `protocol.md` § Parallel-by-default decomposition › Schedule log (sole source); the field table in `resources.md` is **not** where this lives — telemetry is not a resource knob |
| **C-1226** | **The handoff prints six figures, from the plan the run just wrote.** The run's handoff reports **(1) total wall clock, (2) per-work-package wall clock, (3) per-phase wall clock, (4) the work/wait split — `work_ms` against `wait_ms`, summed per work package and across the run, (5) review rounds, and (6) adversary-gate time**. **Six, not five: the work/wait split is a figure of its own**, and C-1225 names it the field this whole design exists to capture — folding it into "per-phase wall clock" is how it went missing in the first place. **The source is the plan's own `## Schedule log` `phase` lines** (C-1223, C-1224), so **there is no teardown-ordering dependency at all**: the drafted contract had to compute before teardown deleted a spool, and with the spool gone the handoff reads a file that is committed rather than deleted. **Where a work package's phase lines are absent or partial** — an interrupted run, or a coordinator that died before returning its timings (D-5) — the handoff prints what it has and **names which figures are missing**, rather than omitting the section or estimating. **Without this contract the next regression is an anecdote again — which is precisely how this program started**, and it is the reason Part 4 exists at all rather than being deferred behind Parts 1–3. | `protocol.md` § Handoff contract |

### UX scenarios

| ID | Scenario |
|---|---|
| **S-1201** | **A silently dead worker, recovered from its checkpoint.** A builder leaf beats at 14:02 with `state: working`, `step: implement`, `checkpoint: src/index/claim.rs` — **a path, because a leaf never commits** (C-1205) — and `expect_next_s: 300`. It then dies without a word. At 14:12 the pulse test fires (`now − ts > 600 s`), so the orchestrator pings it over the agent-messaging capability and waits 3 minutes. At 14:15 there is no beat and no reply; the harness exposes no output, so L2 reads nothing and the agent is silent → **L3**. The orchestrator stops it over the agent-termination capability and re-spawns it from that path, which is the last artifact it durably wrote; the parent records the outcome in the plan's Status column and **never writes into the dead agent's beat file** (C-1202). **Detected and recovering in 13 minutes**, against the 30 minutes the RCA measured for exactly this failure (C-1204, C-1206). |
| **S-1202** | **Alive but not beating — the discriminator that prevents a wrong kill.** A tester leaf writes its last beat at 09:40 with `step: specify` and then works for twenty minutes without beating, because the phase never crossed a boundary and the worker forgot obligation (iii). At 09:50 the pulse test fires and the ping goes unanswered — the worker is deep in a tool call. At 09:53 **L2 reads its output and sees tool calls still flowing**. **The agent is alive and violating the beat contract**: a `Warn` finding is logged (`adr_0006` severity) and **nothing is killed**. Had L2 been unable to see any output, the same silence would have gone to L3 — which is why the discriminator, not the pulse test, is what makes L3 safe (C-1206). |
| **S-1203** | **A second death in the same phase — the run stops retrying and surfaces.** The worker re-spawned in S-1201 dies again during the same implement phase. The ladder reaches L3 a second time, and **the one-retry-per-phase rule forbids a third auto-retry**: the work package is marked `failed` and surfaced. `adr_0010` `C-913`'s cascade then governs — the run **continues while any work package is eligible**, dependents of the failed WP are never offered, and the end-of-run report names it with its stranded set. No third spawn, no infinite loop, and the shape is OTP's, Nomad's, Kubernetes' and Temporal's converged terminal rung (C-1206). |
| **S-1204** | **A coordinator blocked on its children does not consume a cap slot.** `effective max-workers = 3`. The parent spawns coordinators for WP2 and WP3. WP2's coordinator spawns two leaves and then waits, writing a beat with `state: blocked`, `blocked_on: leaves WP2.1, WP2.2`. **The count of agents in state `working` is 3 — two WP2 leaves and WP3's coordinator — and WP2's blocked coordinator is not among them**, so WP3's coordinator can spawn its own leaf when a WP2 leaf finishes. Under the pre-amendment recursive count the blocked coordinator would have held a slot its own children needed: the Airflow `SubDagOperator` deadlock, reproduced exactly. **The cap exemption is the whole of what `blocked` does here** — it is the state's one load-bearing job (C-1202) — and the coordinator keeps beating throughout: a fresh beat is all the ladder ever asks of it, so twenty minutes of waiting is graded L0 on freshness alone and no progress test exists to trip (C-1202, C-1211, C-1221). |
| **S-1205** | **A heavy-slot wait under `limits.heavy`.** A Rust project measures peak RSS 6 GB on a 31 GB host: `headroom = max(2 GB, 7.75 GB) = 7.75 GB`, `floor(23.25 / 6) = 3`, clamped to `[1, nproc]` → **`limits.heavy = 3`**. Four builders reach their implement verification at once. Three take slots `heavy-1..3`; the fourth scans all three with `flock -n`, finds none free, and **queues with a bounded `flock -w "$QUEUE_WAIT"` (60 s); on timeout it re-enters the full non-blocking 1..N scan** rather than staying pinned to one slot, so N-way capacity is not collapsed to 1-way throughput (C-1212). It beats with `state: blocked`, `blocked_on: heavy slot`, so it is **not charged against the concurrency cap** (C-1211) — and it is in no danger from the ladder, which reads only `ts`. **Every acquisition is checked**: had the bounded wait expired against its total `$WALL` budget, the builder would write a `failed` beat naming the exhausted wait and surface it, **never run the command unlocked**. The three running builds are wrapped in `timeout --kill-after=10s`, so a hung build frees its slot without a human. When the first finishes, the fourth's next scan acquires and runs (C-1212, C-1213). |
| **S-1206** | **A `light` gate never takes a slot.** arcana's documented verification is `grim build <skill-dir>` — parse-only. `/hex-init`'s measurement classes it **`light`**. Every builder runs it **without consulting `limits.heavy` and without touching a lock file**; eight work packages verify concurrently. `resources.md` is not even loaded, because no heavy command will be issued (C-1213, C-1218). |
| **S-1207** | **Preflight holds a wave three times, then surfaces.** The human is compiling in another window. Before wave 3, `/proc/pressure/memory` `full avg10` reads 18% — above the 10% threshold. The orchestrator **holds, does not spawn**, waits 60 s, re-checks: 15%. Holds again: 12%. Holds a third time: 14%. **The three-hold budget is spent, so it surfaces to the human** — naming the tripped check and its reading — rather than holding forever on a machine the human is also using (C-1214). |
| **S-1208** | **A macOS host: no `flock(1)`, no `systemd-run`, no `/proc/pressure`.** The run announces three degrades in one block. The semaphore detects `flock(1)` absent and falls to **rung 2**, `python3 -c` with `fcntl.flock` — **the same kernel guarantee**, so crash-safety is not lost and no stale-lock path is entered. The containment ladder finds no `systemd-run` (`[ -d /run/systemd/system ]` fails on Darwin) and falls to `nice`/`ionice` — blast-radius reduction, no cap — with the **wall-clock backstop still mandatory**: `timeout` is absent too, so `perl -e 'alarm shift; exec @ARGV'` carries it, and the announcement states that the Perl form loses the two-stage TERM-then-KILL escalation. Preflight **skips the memory-pressure check and announces the reduced set** rather than reporting a pass it did not perform. Peak RSS is measured with `/usr/bin/time -l`, probed with `-l true` rather than assumed from `uname` (C-1212, C-1213, C-1214, C-1218). |
| **S-1209** | **A harness with no nesting — Part 3 degrades to today's behaviour.** The fan-out ladder resolves to **degraded flattening**; the run announces the existing `Degraded: flat execution — no nested spawn; coordinators inlined` line and **invents no new one**. No coordinator is spawned, the parent runs every pipeline inline exactly as today, and Parts 1, 2 and 4 are unaffected — beats are still written, heavy slots are still taken, and the parent still renders `phase` lines into the plan from its own brackets (with no coordinator returns to read, because there are no coordinators). The only loss is the parallelism Part 3 buys, which is the correct degradation (C-1220). |
| **S-1210** | **A plan authored before `adr_0013` executes unchanged.** No `limits.heavy` in `hex.md`, no resource-profile pointer, no `phase` lines in its `## Schedule log`. Each reader branches on **presence**: `limits.heavy` is absent, so C-1213's derivation supplies it (or 1, where no measurement is reachable); the profile pointer is absent, so `/hex-init` is suggested and the run proceeds; the `## Schedule log` carries only `merged` lines, which is a pre-`adr_0013` run and never an error. **No version field is read, no migration step runs, and the plan is never rewritten.** A plan authored *with* the new fields also runs on the **old** bundle: an old `hex.md` reader hits `limits.heavy` under merge rule 8 and **warns once, ignores, continues**, which degrades to today's unbounded behaviour rather than to a failure (`adr_0010` `C-915`, `adr_0003` `C-223`, C-1210, C-1224). |
| **S-1211** | **Three ready work packages, three coordinators, one serial merge lane.** The ready set is WP4, WP5, WP6; `effective max-workers = 6`; the harness can nest. **Q1 answers yes for all three** (ready set ≥ 2, nesting available), so three coordinators are spawned, each owning its work package's whole pipeline. **Q2 answers no for all three** — none holds ≥ 3 independent sub-tasks — so each runs a single builder per phase rather than splitting into dotted sub-WPs. Each coordinator gets a floor of 1 leaf slot and borrows from the others between phases. **All three are *pipeline* coordinators, so none of the riders fires**: each merge pays its ordinary **scoped** check rather than the `join` full gate, the `M = 3` checkpoint counter is not reset, breadth stays each work package's own budgeted `Review` value, and each coordinator resolves to its work package's effective tier rather than to `deep-reasoning` (C-1219 riders (i)–(iv), amendments 6–8). `adr_0004` `C-306`'s merge serialization is untouched; **`adr_0010` `C-901`'s `join` trigger is *not* untouched — amendment 6 rescopes it to decomposing coordinators, which is exactly why these three merges stay scoped.** **WP4 does not wait for WP5's review round to finish** — which is the **53-minute** queue tail the RCA traced, less the serialized merge lane that still runs (C-1219, C-1220, C-1221). |
| **S-1212** | **The handoff prints where the wall clock went — from the plan, with no second file anywhere.** Each coordinator returned its work package's per-phase timings in **the one structured result it already returns**
(`workers/coordinator.md` § coordinator, the Return template); the parent
timed its own merges from its `date -u +%FT%TZ` brackets. At merge time **the parent — the only writer** — rendered one `phase` line per phase into the plan's `## Schedule log`; `adr_0010` `C-904`'s bisection walk read only the lines whose first word after the first `·` is `merged` and was unaffected. The handoff then prints **six figures** — total wall, per-WP wall, per-phase wall, **the work/wait split**, review rounds and adversary time — reporting that WP4 spent 4 minutes of `wait` against 71 of `work`, the number the RCA had to reconstruct by hand. **There is no ordering constraint against teardown**, because the numbers live in the committed plan rather than in a file teardown deletes. Teardown removes the run's out-of-tree heartbeat directory, the scratch root and the worktree — and **leaves the host-global lock tokens untouched**, the one thing it never deletes. **No file this part touches was ever inside the repository** (C-1223, C-1224, C-1225, C-1226, C-1216). |
| **S-1213** | **Three lock waits in one run, triaged three ways — and only one of them moves the cap.** A wave runs three work packages. **(1)** WP2's builder waits 40 s on `heavy-2`: it is already `blocked` with `blocked_on: heavy-slot`, so this is the semaphore working — **no signal, no log entry, `heavy` unchanged**. **(2)** WP3's tester hits `Blocking waiting for file lock on build directory`: the worker classifies it as a **build-tool lock wait**, returns `lock-evidence: "Blocking waiting for file lock…"` (quoted, ≤ 120 chars) naming the shared directory, and the orchestrator **warns and leaves `heavy` alone** — lowering concurrency would not un-share a target directory, it would only hide a misconfiguration behind a slower run. **(3)** WP1's builder is OOM-killed: the worker returns `oom-evidence: "signal 9 (SIGKILL) …"` — **a bounded classified token, never raw build output for the orchestrator to re-parse** — and the orchestrator **corroborates against a host source** before acting, finding `/proc/pressure/memory` `full avg10` at 34%. Only then does it lower `heavy` by one for the remainder of the run and log it, floor 1, **run-scoped and never written back to config**. Had the same string appeared in a repository file with no host corroboration, **nothing would have moved** — which is the point: planted text alone cannot walk a run's concurrency down to 1 (C-1217, C-1206, C-1213). |

## Non-Functional Requirements

| Axis | Impact of this decision |
|---|---|
| **Scalability** | **Improved along the axis that failed, and newly bounded along the axis that broke the host.** Work-package concurrency rises from an effective 1 (one parent running every pipeline serially) to `min(\|ready set\|, effective max-workers)`, with a per-branch floor of 1 leaf and borrowing from idle siblings. **No recursion level is added** (`C-914` preserved), so the token multiplier is unchanged — this is the same fleet running in parallel, not a bigger fleet. Heavy-command concurrency is newly bounded by `limits.heavy`, a *reduction* against today's unbounded behaviour, and that is deliberate: today's number is "as many as there are worktrees", which is what produced two OOM kills. |
| **Availability** | **This is the axis Part 1 exists for.** hex has no availability contract today: a dead worker stops a run until a human notices, measured at 30 minutes once. After: **≤ 13 minutes to detection at defaults, 2 minutes for a worker that never starts**, one automatic recovery from a checkpoint per phase, and a surfaced failure rather than a silent stall on the second death. **Preflight adds a deliberate availability cost**: a wave may be held for up to 3 minutes before it surfaces, which trades a small scheduled delay against the desktop freeze that precedes an OOM kill. |
| **Latency** | **135–150 minutes against 186 on the traced work package**, and the figure is the § Quantified impact table's, not a second estimate. **53 minutes of queue** removed by Part 3 (the RCA's `03:46 → 04:39` tail; the earlier 69 double-counted the 16-minute wait already charged to the preceding row), ~17 minutes of undetected death removed by Part 1, and **+12 to +15 minutes per work package charged back** for the pipeline coordinator's added spawn round trip. **The pipeline's own depth is untouched and is `adr_0012`'s lever** (C-1222) — a **~90-minute floor** this ADR cannot move — which is why this ADR does not claim the RCA's ≤ 30 min target and publishes the larger number rather than the smaller. Against it: a heavy-slot wait is *added* latency on a host whose `limits.heavy` clamps low, and a beat is a foreground tool call per five minutes of work. |
| **Security** | **One new boundary, plus two named risks the fix round closed and one traded exposure stated in both directions.** `resources.md` carries **knob names, never commands hex composes**; the heavy command hex wraps is **the project's own documented verification**, already an authoritative-class value under `adr_0009` `C-815` and `adr_0010` `C-906`, and this ADR adds no new source for it. The semaphore and backstop **wrap** that command without rewriting it. **Nothing this ADR writes enters a repository at all** (C-1201, C-1215, C-1223), so there is no gitignore line and no beat that can reach a PR — and the heartbeat file itself holds no credentials, no project content and no user text, only eight short fields and a step name. **Two named risks, both fixed in the 2026-09-05 fix round rather than accepted.** *Teardown:* a run's teardown composes `rm -rf` targets and a container prune from run ids and slugs, so ids and slugs are **orchestrator-minted** and slugified to `[a-z0-9][a-z0-9-]{0,63}`, **teardown refuses any delete target that does not resolve under its own run-root prefix**, container pruning is `docker container prune -f --filter label=<the run's own label>` and runs **only** where the run itself set that label, and process-group kills reach **only group ids the run recorded at spawn** (C-1216). *Untrusted output:* the OOM/resource triage no longer reads raw repository-controlled build output — the **worker** classifies and returns a bounded, quoted `oom-evidence` token, and a `heavy` reduction additionally needs corroboration from a **host** source (C-1217, `protocol.md` § Untrusted-text echoes). **`HOME` is deliberately not redirected (C-1215), and the trade-off runs in both directions.** *Availability-positive:* redirecting it silently detaches every credential-reading tool — git identity, `gh` auth, cargo tokens, ssh — from the credentials the user expects, and a run that cannot push is a worse and more confusing failure than a suite writing a few files under the real home. *Security-negative, and this half was missing:* hex runs **a possibly hostile repository's own documented verification command**, N-way concurrent and unattended, with read access to `~/.ssh`, `~/.config/gh` and `~/.aws`. Not redirecting `HOME` leaves that reach intact. **The default is probably right** — the alternative breaks the common case for every project to contain the uncommon one — but it is a **traded** exposure, not an absent one, and the `/hex-init` `HOME`-redirect audit item names **credential exposure to an untrusted verification command** as a first-class reason to take the opt-in, alongside suites known to write to `$HOME`. No network call is made anywhere in this ADR, and `hex-init`'s "nothing here reaches the network" stays true verbatim. |
| **Cost** | **Token cost rises, and the earlier claim that it falls was false.** **Part 3's pipeline coordinator is a real extra agent, one spawn per ready work package** — not a relabelling of an agent that already ran. Each carries its own context copy, its own turns and its own structured return, at the RCA's own 11.8–14.7 min median round trip, and § Quantified impact charges that as **+12 to +15 min per WP** rather than averaging it away. What *does* hold is that no new spawn **class**, no new role and no new research phase appear, and that breadth is unchanged (amendment 7): the added cost is one coordinator per WP, bounded and countable, not a multiplier per level. **Part 1 adds a handful of small foreground writes per worker.** **Part 4 adds no writer at all** — the parent renders from brackets and returns it already has (C-1223). **The second real cost is contention**: `limits.heavy` can serialize builds that used to overlap, which lengthens a run on a small host. That is the price of not OOM-killing it. **Always-on surface added: not zero, and the earlier "zero" was also false.** `workers.md` § Universal worker protocol — which every worker loads — gains the beat rule (C-1204), the scratch-env rule (C-1215) and the output-classification rule (C-1217); **every spawn prompt gains fields** (the run's runtime root, the lock directory, the agent id, `expect_next_s`). What stays at zero is the *rule-file* line count, the skill-description surface, and `resources.md`, which is conditional-load and costs a parse-only project nothing. |
| **Operability** | **Four new operational objects, and none of them is inside a repository.** **Ephemeral, one:** the run's heartbeat directory `${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/hb/*.json`, teardown-deleted and **never read by resume** (C-1201). Its sibling, the per-run scratch root under the same `<run-id>` (C-1215), rides the same owner. **Durable, two:** the `limits.heavy` config leaf and the `## Schedule log`'s second line kind. **Host-global, one:** the heavy-slot tokens at `${XDG_CACHE_HOME:-$HOME/.cache}/hex/locks/`, zero-byte, permanent, and never deleted by teardown or by any sweep (C-1212, C-1216) — host-scoped because the resource they meter is the host's, permanent because unlinking a held token breaks mutual exclusion. **There is no fifth object and no in-tree one: the JSONL spool was deleted (C-1223), so telemetry adds no file and no writer**, and **this ADR contributes no `.gitignore` line**. **No nested state file, at any depth** — one flat directory per run, never one per coordinator (driver 5). The genuinely new things an operator must learn are the `phase` log line and the `Degraded:` lines for the two new capability classes, all of which follow shapes already in the bundle. Teardown becomes load-bearing, and its failure mode is a **sweep-and-warn** on the next run rather than a deletion (C-1216). |

## Technical Details

### Runtime layout

```
<run root>/                        # the orchestrator's own checkout
└── .agents/worktrees/<wp>/        # unchanged — and this ADR writes nothing else here

${XDG_CACHE_HOME:-$HOME/.cache}/hex/   # host-global, outside every checkout
├── locks/heavy-{1..N}             # zero-byte flock tokens; permanent, never deleted
└── <run-id>/                      # this run's root — teardown deletes only this subtree
    ├── hb/<agent-id>.json         # one per live agent, flat, parent-linked
    └── <wp>/                      # disk-backed scratch: TMPDIR, XDG_CACHE_HOME, XDG_STATE_HOME
```

**Nothing this ADR writes lives inside a repository**, which is why there is
no `.gitignore` line anywhere in it. The drafted in-tree `.hex/` directory is
gone in both halves: the heartbeats moved out to the run root above (C-1201,
a security decision — a fixed in-tree path read as a control surface is
attacker-plantable by the repository under work), and the JSONL spool was
deleted outright (C-1223). The lock directory is the design's one host-global
object and its one artifact that outlives a run — both deliberate (C-1212,
C-1216). The orchestrator resolves every absolute path under
`${XDG_CACHE_HOME:-$HOME/.cache}/hex/` **once, from its own unredirected
environment**, and passes each in every spawn prompt; a worker never expands
`XDG_CACHE_HOME` for itself, because its own copy points at the per-run
scratch (C-1201, sole statement).

### File grammars

A heartbeat, written temp-then-rename so a reader never sees a partial object:

```sh
printf '%s\n' "$json" > "$HB/$ID.json.tmp" && mv -f "$HB/$ID.json.tmp" "$HB/$ID.json"
```

```json
{ "seq": 7, "parent": "wp4-coord", "state": "working",
  "step": "implement", "checkpoint": "src/index/claim.rs",
  "ts": "2026-09-05T14:32:07Z", "expect_next_s": 300 }
```

The file is `wp4-builder.json`, and **there is deliberately no `id` field** —
it would be byte-identical to the filename stem, the same rule that rejects a
`children` field (C-1201). This is a **leaf**, so its `checkpoint` is a
**path** — the last artifact it durably wrote. A **coordinator**'s beat
carries a **commit SHA** in the same field, the SHA of its last sub-WP join
commit (C-1205). **`seq` is the torn-write guard and never grades liveness**:
only `ts` and file completeness do, so an agent whose context is compacted and
which restarts its counter at 1 is not gradeable as dead for it. `blocked_on`
appears only in state `blocked`, and **a `blocked` beat missing it is graded
as nothing** — not a violation, not a death; it is simply a less useful beat.

One phase's telemetry fields, as the coordinator returns them to the parent
and the parent renders them into the plan (C-1223, C-1225) — **not a line in
any file this ADR creates**:

```json
{"ts":"2026-09-05T14:32:07Z","run":"r7","wp":"WP4","phase":"implement","event":"end","model":"deep-reasoning","agent":"wp4-builder","work_ms":712000,"wait_ms":41000}
```

which the parent renders as one `## Schedule log` line (C-1224):

```
- 2026-09-05T14:32:07Z · phase WP4/implement · model deep-reasoning · work 11m52s · wait 0m41s
```

### The heavy-slot idiom

The slot is held **around the documented command**, in the same shell
invocation, never in a wrapper that backgrounds it:

```sh
# $N = limits.heavy; $LOCKS = the host-global lock dir, absolute, from the
# spawn prompt: ${XDG_CACHE_HOME:-$HOME/.cache}/hex/locks — never re-derived
# by the worker, whose own XDG_CACHE_HOME is redirected (C-1201, C-1212, C-1215)
# $WALL      default 1800  (4 x the measured gate wall time, floor 600)
# $QUEUE_WAIT default 60   (per bounded attempt; total queue budget = $WALL)
deadline=$(( $(date +%s) + WALL ))
while :; do
  for i in $(seq 1 "$N"); do                       # pass: non-blocking 1..N scan
    ( flock -n 9 || exit 111                       # 111 = this slot is busy
      timeout --kill-after=10s "$WALL" "$@" 9>&-   # descendants never inherit fd 9
    ) 9>"$LOCKS/heavy-$i"
    rc=$?; [ "$rc" -eq 111 ] || exit "$rc"         # ran under the lock: its rc
  done
  [ "$(date +%s)" -lt "$deadline" ] || exit 75     # 75 = queue budget exhausted
  ( flock -w "$QUEUE_WAIT" 9 || exit 111           # FAIL CLOSED — no fall-through
    timeout --kill-after=10s "$WALL" "$@" 9>&-
  ) 9>"$LOCKS/heavy-1"
  rc=$?; [ "$rc" -eq 111 ] || exit "$rc"           # timed out → rescan all 1..N
done
```

**This block *is* C-1212, not an illustration of it.** Four properties are
load-bearing and each is visible above.

1. **Fail closed.** *Every* acquisition is exit-checked — `flock -n 9 || exit
   111` on the scan and **`flock -w "$QUEUE_WAIT" 9 || exit 111`** on the
   bounded wait. The drafted idiom omitted the second check, so a timed-out
   wait ran the command **unlocked**: under exactly the saturation the
   semaphore exists for, every waiter fell through at once and the OOM class
   returned in full. The busy sentinel must be a code the documented command
   cannot return (`flock -E` fixes the choice where `flock(1)` is present).
2. **The descriptor is closed for descendants** — `9>&-` on the command, with
   the subshell still holding the lock. A build tool that daemonizes (Gradle,
   testcontainers) therefore cannot inherit fd 9 and hold the slot after this
   shell exits; with `heavy` clamped to 1 on a small host, one leaked slot
   wedges every later run sharing `$HOME`. **Recovery, when a slot is leaked
   anyway:** identify the holder with `fuser`/`lsof` on the token and stop it —
   **never unlink the token**, because the `9>` redirection creates it on first
   use and **nothing ever removes one** (C-1216); an unlink under a live holder
   gives the next `open()` a fresh inode and hands the same slot to two agents.
3. **No lock convoy.** Scanning with `-n` first means N racing processes take N
   distinct slots in one pass with no wake storm. The overflow waiter blocks
   only **briefly** (`$QUEUE_WAIT`, 60 s) and **on timeout re-enters the full
   1..N scan** rather than staying pinned to `heavy-1` — a waiter pinned to one
   slot collapses N-way capacity to 1-way throughput under precisely the
   contention the semaphore exists to relieve.
4. **The terminal outcome on expiry is surfaced, never silently proceeded
   past.** When the total queue budget `$WALL` is spent the wrapper exits `75`
   and runs nothing: the worker writes a `failed` beat naming the exhausted
   wait, returns that failure in its structured result, and the orchestrator
   surfaces it. **It never retries the command unlocked.**

### Detection probes

Each is cheap, side-effect-free, and **probes rather than infers from
`uname`** — a minimal Linux image can carry only the BSD-flavoured tools.

| Layer | Probe | On absence |
|---|---|---|
| `flock(1)` | `command -v flock` | `python3 -c` with `fcntl.flock`; else `mkdir` + PID staleness check, announced |
| memory cgroup | `command -v systemd-run && [ -d /run/systemd/system ] && systemctl --user show-environment` | delegated cgroup v2 write; else `nice`/`ionice`; else backstop only |
| peak RSS | `/usr/bin/time -v true` → `/usr/bin/time -l true` → `command -v gtime` | record no profile, `limits.heavy = 1`, announce — never fabricate a number |
| wall-clock backstop | `command -v timeout` → `command -v gtimeout` | `perl -e 'alarm shift; exec @ARGV'` — **no acceptable absent outcome** |
| memory pressure | `[ -r /proc/pressure/memory ]` | skip **and announce the reduced check set** |

## Constitution deviations / DESIGN.md amendments

`hex/DESIGN.md` is binding. This decision proposes **seven live amendments,
numbered 1–8** — **amendment 1 was withdrawn in the 2026-09-05 fix round with
C-1209 and its number is kept dead so the rest stay stable**, and amendments
**6, 7 and 8 were added in that same round** to retarget the behavioural
riders the word *coordinator* carries. Each has a stated boundary. **The owner
accepts them by accepting this ADR; this run does not edit `DESIGN.md`.** The
round's number is assigned at implementation time — the file currently ends at
round 13, and `adr_0012` is in flight and expected to take the next one.
Following `adr_0005`'s deferred finding D-5, each justification names *which
simpler route was rejected and why*.

**With amendment 1 withdrawn, this ADR proposes no client-specific enforcement
of any kind** — verified by grep over this file: **every surviving occurrence
of *hook* is a prohibition (driver 3, C-1204), a withdrawal record (amendment
1, C-1209, D-4), or the argument for why option L4 lost. Not one is a
proposal.** `DESIGN.md` § Spec-kit comparison round (2026-07-19, round 5)'s non-adopt
of the extension-hook stack therefore needs no carve-out at all, which is the strongest form this section
could take.

| # | Amendment, and its boundary | Why needed | Simpler alternative rejected because |
|---|---|---|---|
| **1** | ~~**Client-specific enforcement, as a narrowed carve-out.**~~ **WITHDRAWN in the 2026-09-05 fix round, with `C-1209`. Proposes nothing; the number is kept dead so no other amendment moves.** The drafted amendment would have carved into `DESIGN.md` § Spec-kit comparison round (2026-07-19, round 5)'s non-adopt of spec-kit's "extension-hook stack (hex ships markdown, the client is the runtime — portability is the moat)" so that `/hex-init` could *propose* a project-local, opt-in client hook as an enforcement *ceiling* over the portable prompt floor. | **Withdrawn because the carve-out cost more than the mechanism was worth**: it would have been the first time hex writes *executable configuration* rather than documentation, for a mechanism nothing requires and nothing measures, paid for out of the one non-adopt the constitution names as the moat. | **Nothing replaces it.** Part 1's floor — a beat written as a foreground tool call by the agent itself (C-1204) — never depended on the hook, so the withdrawal costs no contract. The reasoning is preserved as deferred finding **D-4** and the option returns only if the beat contract is *measured* to be unreliable. |
| **2** | **Ephemeral runtime state — heartbeats only.** Amends `adr_0010` **driver 5** ("No nested state files, at any depth") and **`C-914`**'s "no per-coordinator state" clause. **Boundary: the four conditions — ephemeral (teardown-deleted, outside every checkout, never committed), never authoritative, never read by resume, and one flat directory per run.** **The telemetry half of this amendment was deleted in the 2026-09-05 fix round**: with the JSONL spool gone (C-1223), per-phase timings are written by the parent into the plan's `## Schedule log`, which is exactly where `C-912` already puts them, so telemetry needs no amendment at all. What remains needing one is the heartbeat directory, and nothing else. | A liveness signal cannot be expressed in an artifact that records one line per merge, and a beat is a *view of what is in flight*, not a second record of what happened. `C-912`'s four objections are all objections to a second **durable** record and are each answered in § Decision Outcome; none of them reaches a transient view. | **Putting the beats in the plan** was rejected on correctness: N concurrent writers editing one markdown section is a lost-update race with no available locking discipline and no way to detect the loss (axis 4, option T2). **Dropping liveness** was rejected because the 30-minute silent death is one of the RCA's own root causes. **One directory per coordinator** was rejected because it is the nested shape driver 5 forbids, and the flat directory with a `parent` field gives the same subtree reconstruction with one glob. |
| **3** | **The concurrency cap counts live model-compute.** Amends `protocol.md` § Worker coordination's recursive counting so that **an agent in state `blocked` does not occupy a slot**. **Boundary: `blocked` is a declared state with a `blocked_on` value, not an inference; every other property of the cap — recursive counting, `min(8, max-workers)`, the clamp, the federated single-lead read — is unchanged.** | **Deadlock avoidance, not an optimization.** Charging a coordinator that waits on its own children against the pool those children draw from is the Airflow `SubDagOperator` deadlock, documented verbatim in Python's `ThreadPoolExecutor` and Java's `ForkJoinPool` as well. Without it Part 3 deadlocks by construction. | **Raising the cap instead** was rejected: it treats a structural deadlock as a sizing problem and oversubscribes the API budget the cap exists to protect. **A separate pool for coordinators** — Airflow's and `ForkJoinPool`'s other documented fix — was rejected as a second budget to size, announce and reason about, where the field's other fix (do not count the blocked party) costs one clause and one state value. |
| **4** | **The coordinator gate splits in two.** `hex-execute/SKILL.md` § Coordinator spawn's single gate becomes two
questions: **(Q1) does this work package get a coordinator** — yes when the ready set holds ≥ 2 WPs and the harness can nest — and **(Q2) does that coordinator further decompose into sub-WPs** — the existing ≥ 3-independent-sub-task judgment, unchanged. **Boundary: no new role, no new level, no change to the coordinator's internals, its join rules, or its file-set intersection check.** | One gate has been answering two different questions. "Is this work package internally decomposable?" and "should this work package's pipeline run concurrently with its siblings'?" are unrelated, and conflating them is why the conservative default (a single builder) also serialized every pipeline onto the parent. | **A new per-WP orchestrator role** (axis 3, option P2) was rejected: it violates `C-914` on all three council grounds and **buys no additional parallelism**, since the effective cap is unchanged. **Leaving the gate alone and widening only the ≥ 3 threshold** was rejected because it would spawn coordinators for work packages that have nothing to decompose, which is the opposite defect — Q2's judgment is correct and is kept intact. |
| **5** | **One artifact enters the bundle's set — and it is now one, not two.** A new `hex-core` reference file, **`resources.md`** (conditional-load). **This amendment was rewritten rather than withdrawn in the 2026-09-05 fix round: it kept a real subject and lost a false one.** Its drafted second half added "a gitignored runtime directory `.hex/`", and **that subject no longer exists** — the heartbeat directory moved out of every checkout to `${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/hb/` (C-1201) and the JSONL spool was deleted outright (C-1223), so **this ADR adds no `.gitignore` line anywhere and writes nothing into a repository**. **Boundary: `resources.md` is a knob sheet, never a policy — hex still never defines how to verify a project; and no new bundle *member* is added, so `hex.toml` / `grimoire.toml` are untouched.** | The knob sheet is per-ecosystem project knowledge an orchestrator needs *before* it issues a heavy command, and it is too large to inline into `protocol.md`, which already loads into every orchestrator. Conditional-load is the shape `config.md` already uses for exactly this reason. | **Inlining it into `protocol.md`** was rejected on cold-load cost: that file is already the bundle's largest orchestrator load and a diet item in Wave 2. **Making it a new bundle member** was rejected because it is a reference consumed only by `hex-core`'s own consumers, and a member would add an install decision for no user-visible benefit. **Withdrawing the amendment outright** was rejected because a new shipped reference file is a real change to the bundle's artifact set and needs its stated boundary even with the gitignore subject gone. |
| **6** | **The `join` riders key on the *decomposing* coordinator, not on any coordinator.** Amends `protocol.md` § Worktree work-package mechanics — "the merge of a **coordinator-owned WP** … pays a full post-merge verification rather than a scoped check — the `join` trigger" — and `protocol.md` § Checkpoints — "a coordinator join resets the counter" — so both read "**decomposing**-coordinator-owned". **Boundary: only the firing *condition* moves. The scoped/full distinction itself, the `M = 3` value, `C-901`'s other triggers and `C-904`'s bisection walk are unchanged, and a decomposing coordinator's merge behaves exactly as it does today.** | C-1219 Q1 gives a **pipeline** coordinator to every ready work package. Left unamended, every merge in every run would pay the **full** post-merge gate — ~25 minutes on the ocx host against the 1m32s scoped check the RCA logged — which alone makes the traced run *slower*, and the `M = 3` counter would be reset on every work package and could never fire. **This amendment changes `adr_0010` `C-901`'s firing condition and is stated as such**, not claimed as a no-op. | **Leaving the riders on all coordinators** was rejected: it re-creates RCA root cause 6 by construction and reverses the whole point of Part 3. **Spawning pipeline coordinators under a different role name** was rejected as `C-914`'s new-role prohibition, and it would fork the coordinator's join rules, worktree rules and intersection check into two files to avoid amending two lines. |
| **7** | **Review breadth is decoupled from coordinator existence.** Amends `hex-execute/SKILL.md` § Coordinator spawn, deleting the
parenthetical "a coordinator WP is **by definition `panel`** — `self`/`light` WPs never qualify for a coordinator". **Breadth stays the work package's own budgeted `Review` value** (`adr_0010` `C-905`, and `adr_0012`'s per-WP effective tier), whatever kind of coordinator owns it. **Boundary: the `Review` cell's own semantics, its lower-only budget and `adr_0012` `C-1112`'s `Review: panel` escape hatch are all unchanged — only the coordinator-implies-`panel` inference is removed.** | Under C-1219 Q1 every ready work package gets a coordinator, so this rider would make **every** work package `panel` — RCA root cause 2 re-created, and a direct reversal of `DESIGN.md` § Worktrees (hex-execute parallel work
packages)'s lower-only Review budget. Breadth is a property of the work, not of who spawns the phases. | **Keeping the rider and exempting `self`/`light` work packages from coordinators** was rejected: it re-serializes exactly the small, cheap work packages Part 3 exists to overlap. **Reading breadth from the coordinator kind instead** was rejected as a second, competing source for a value `adr_0010` `C-905` and `adr_0012` already resolve. |
| **8** | **A pipeline coordinator's capability class follows the work package.** Amends `models.md`'s `coordinator` row and its **rule-5 tier gate**: a **pipeline** coordinator resolves to **the work package's own effective tier** (`adr_0012` `C-1109`, `C-1110`); a **decomposing** coordinator keeps the **deep-reasoning** class and the medium/high tier gate exactly as today. **Boundary: capability classes only — no literal model name enters `models.md` or this ADR; the decomposing row is unchanged; and `adr_0012` `C-1109`'s `min(T, medium)` floor stays scoped to the decomposing kind.** | Under Q1 every work package would otherwise gain a deep-reasoning agent it did not have — RCA root cause 3 — and Q1 has no tier clause at all, so a `low` work package would spawn a coordinator the tier gate says may not exist. Following the work package's effective tier makes the pipeline coordinator cost what the work costs. | **Giving pipeline coordinators a fixed cheap class** was rejected: it hard-codes a value `adr_0012` already derives per work package, and would diverge the moment that derivation changes. **Dropping the tier gate entirely** was rejected because the decomposing coordinator's gate is load-bearing — `models.md` rule 5 gives `coordinator` no `low` cell, which is precisely why `adr_0012` `C-1109` floors a decomposing-coordinator-owned work package at `min(T, medium)`. |

**The portability moat is intact, and it is checked rather than asserted.**
`DESIGN.md` § Spec-kit comparison round (2026-07-19, round 5) non-adopts
the extension-hook stack. **After the
2026-09-05 fix round this ADR proposes no client-specific enforcement at
all**: amendment 1 and C-1209 — the `/hex-init`-generated post-tool-call hook
— are both withdrawn, and a grep of this file for `hook` finds only
prohibitions, withdrawal records (including deferred finding **D-4**) and the
axis-1 argument for why L4 lost — **never a proposal**. Every mechanism that
remains is prompt text an agent executes with one foreground tool call
(driver 3).

**`adr_0010`'s verification budget is *not* untouched, and this ADR says so
rather than claiming otherwise.** Amendment 6 retargets `C-901`'s `join`
trigger and the `M = 3` checkpoint-counter reset from "coordinator-owned" to
"**decomposing**-coordinator-owned", which changes when `C-901` fires. That is
a deliberate, bounded change to `adr_0010`'s gate triggers and it is carried
as a numbered amendment, not smuggled in as a no-op. Every other property of
the budget — the scoped/full distinction itself, `C-905`'s breadth budget,
`C-904`'s bisection walk, `C-913`'s cascade, `C-915`'s presence checks — is
unchanged.

**Considered and not deviated:** the **single approval gate** (this ADR adds
no gate and asks nothing). The **depth-1 invariant** — not merely untouched
but reaffirmed: no recursion ≥ 2, no new orchestrator role, and state stays
one flat surface, with the run's out-of-tree runtime directory held to it
explicitly as **one directory per run, never one per coordinator**.
**Capability classes** — upheld actively:
every new mechanism is gated on a class (*agent messaging*, *agent
termination*, *condition-waiting*, *scheduled-wake*), announced as a
`Degraded:` line, detected per run and never stored, and **no shipped file
this ADR touches names a literal model or a harness primitive**. **The
two-layer knowledge model** — upheld: the resource profile and the scratch
convention are Layer-1 project facts reached through `hex.md › Pointers`; hex
records where they live, never what they say. **`hex never pushes` /
`hex never commits` outside execution** — untouched. **`adr_0005`'s fold
path** and **`adr_0004`'s federation contracts** (per-repo verification
`C-321` and global merge serialization `C-306` both apply unchanged; the cap
still reads only the lead's `max-workers`) — untouched. **Thin dispatchers +
per-tier phase files** — no tier file gains a rule.

## Migration / rollout plan

**Every change is additive and no migration step exists.** There is no plan
rewriter, no `--upgrade` flag, and **no version comparison anywhere in the
design** (`adr_0010` `C-915`).

**What an existing plan does on the new bundle.** It executes. Absent
`limits.heavy` ⇒ C-1213's derived value, or 1 where no measurement is
reachable. Absent resource-profile pointer ⇒ `/hex-init` is suggested and the
run proceeds. Absent `phase` lines in `## Schedule log` ⇒ a pre-`adr_0013`
run, never an error; the lines appear from the first merge onward. **The plan
is never rewritten to add anything.**

**What a new plan does on an old bundle.** It runs. `limits.heavy` hits merge
rule 8 — warn once, ignore, continue — which degrades to today's unbounded
heavy commands rather than to a failure. `phase` lines in a `## Schedule log`
are read by nothing, because the one consumer that reads that section filters
on `merged` (C-1224).

**What an in-flight run does.** Nothing changes mid-run: the contracts are
read at spawn time from shipped files, and a run that started under the old
bundle finishes under it. A run **resumed** after the upgrade re-reads the
plan exactly as today (`hex-execute/SKILL.md` § 2. Resolve the target)
and starts writing
beats for the workers it spawns from that point. **There is nothing to
rehydrate**, which is condition 3 of the ephemeral/durable split doing its
job.

**Wave order, in dependency order. The classes are file-disjoint except where
noted, which is what makes them decomposable.**

1. **`protocol.md` § Worker coordination** — the liveness subsection
   (C-1201–C-1208), the amended cap bullet (C-1211), the allocation invariant
   (C-1221), and the links out to `resources.md`. **Critical path: everything
   else links here.**
2. **`resources.md`** (new file) — semaphore, preflight, scratch, teardown
   checklist, output signals, containment ladder, knob sheet (C-1212–C-1218).
   **File-disjoint from class 1 and shippable in parallel with it.**
3. **`protocol.md` § Parallel-by-default decomposition + § Worktree work-package
   mechanics + § Handoff contract** — the log grammar and its consumer filter
   (C-1223–C-1226) and the teardown amendment (C-1216). Same file as class 1,
   different sections: **serialize class 3 behind class 1** rather than
   merging two edits to one file concurrently.
4. **`hex-execute/SKILL.md` § Coordinator spawn + `workers/coordinator.md`
   + `models.md`** — the gate split, the mission rewrite, and the three rider
   retargetings: `hex-execute/SKILL.md` § Coordinator spawn's `panel`
   parenthetical deleted (amendment 7), `workers/coordinator.md`'s Mission,
   Preconditions, Join loop and leaf-compile-check sentences, and Tools/Model
   paragraph scoped to the decomposing kind, and `models.md`'s `coordinator`
   row
   and rule-5 tier gate split by kind (amendment 8) — C-1219, C-1220.
5. **`config.md` + `memory.md` + `hex-init`** — the `limits.heavy` row, the
   `## Pointers` enumeration, and **two** audit items (resource profile, and
   the `HOME` opt-in naming credential exposure as a reason to take it). **No
   gitignore item, and no enforcement-hook item.** This ADR writes nothing into
   a checkout — the heartbeat directory is out of tree (C-1201) and the spool
   was deleted (C-1223) — and the client hook was withdrawn with C-1209 and
   amendment 1.
6. **`workers.md`** — the beat rule (C-1204), the per-run scratch-env rule
   (C-1215) and the **classify-and-return-a-bounded-token** rule (C-1217) in
   the Universal worker protocol; the heavy-role qualifier in the role index.
7. **`DESIGN.md`** — one dated round with the **seven live amendments**
   (2–8; amendment 1 is withdrawn), appended.
8. **Release** — `publish.toml` minor bump, `CHANGELOG.md`, `README.md`.

**What can ship independently.** **Part 1 (classes 1, 6) ships alone** and is
a win on its own — it needs neither `limits.heavy` nor a coordinator. **Part 2
(classes 2, 5) ships alone.** **Part 4 (class 3) ships alone**, degrading to
one writer where there is only one. **Part 3 (class 4) is the one with a hard
prerequisite**: it must not land before C-1211's cap amendment in class 1, or
it deadlocks by construction. That ordering constraint is the single most
important line in this section.

**One class-4 note for the implementing plan:** this repo dogfoods its own
bundle, so the installed copies under `.claude/skills/hex-*` go stale the
moment these edits land. Refreshing them is a **separate chore commit** after
the merge, not part of any work package.

**Rollback, at two grains.** *The bundle:* **every change is a markdown edit
on a feature branch, reverted by discarding it — there is no non-markdown
artifact and no gitignore line at all**, because nothing this ADR writes
enters a checkout. **The only thing written that outlives a run is a directory
of zero-byte lock tokens** at `${XDG_CACHE_HOME:-$HOME/.cache}/hex/locks/`,
which carry no data, are never deleted by design (C-1212, C-1216), and are
inert on a host that never runs hex again. Everything with content — the run's
heartbeat directory and its scratch root, both under
`${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/` — is deleted by teardown, and
a killed run's leftovers are swept and **reported, never deleted, by the next
run** (a run deletes only its own `<run-id>` subtree). *One project:* set `limits.heavy` high to
neutralize the semaphore, and the liveness contract degrades to a `Warn`
finding rather than a kill wherever the agent-termination capability is
absent. There is nothing to un-migrate at either grain.

## Validation

**Static, before execution.**

- `grim build <skill-dir>` for every changed skill; `task publish -- --dry-run`
  for the full sweep.
- **Contract coverage:** every `C-12xx` maps to at least one work package and
  one test in the implementing plan; every `S-12xx` maps to at least one work
  package. **C-1222 is exempt from both halves** — it is a stated boundary
  whose whole content is that no file changes; its check is the negative one
  below. **`C-1203` and `C-1209` are exempt because they are withdrawn** and
  ship nothing; the check on them is the opposite one — **no work package may
  implement either**, and no shipped file may mention a progress-delta test or
  a generated client hook.
- **No literal model name and no harness primitive name** in any changed
  shipped file. The existing no-literal-model check is re-run, and a second
  grep is run over the changed set for the harness's current primitive
  vocabulary — the token list is resolved **at check time from the harness in
  use**, never written into a shipped file or into this ADR, because that
  surface churns (`protocol.md` § Worker coordination). Every mechanism
  this ADR adds is
  named by its **capability class** instead, which is what the check
  confirms: each of the four classes below appears, and no primitive does.
- **Capability-class coverage:** each of the four new classes appears with a
  `Degraded:` line — `grep -rn 'Degraded:' hex/hex-core/references/protocol.md`
  shows the two new rungs alongside the existing ones.
- **Nothing lands in a checkout:** `grep -rn '\.hex' hex/` returns **no hits at
  all**, and `git diff` touches **no `.gitignore`**. The run's runtime root is
  out of tree by contract (C-1201), and the spool that would have needed a
  gitignore line was deleted (C-1223).
- **Condition 3 is greppable:** no shipped file reads the run's runtime root on
  a resume path. `grep -rn 'XDG_CACHE_HOME' hex/` hits only the liveness,
  semaphore, scratch and teardown definitions, and **never**
  `hex-execute/SKILL.md`'s resume block.
- **No client-specific enforcement:** `grep -rn 'hook' hex/` over the changed
  set returns nothing this ADR added — amendment 1 and C-1209 are withdrawn, so
  `DESIGN.md` § Spec-kit comparison round (2026-07-19, round 5)'s non-adopt
  needs no carve-out.
- **Sole-definition check:** `grep -rn 'limits.heavy' hex/` shows exactly one
  defining occurrence (`config.md`'s key row) plus links; the semaphore is
  defined once in `resources.md` and linked, not restated, from
  `protocol.md`.
- **`config.md` diff is one row.** The six Tier A key names are unchanged, and
  `limits.max-workers` is not renamed — the check is that
  `git diff hex/hex-core/references/config.md` touches only the key table and
  the v2 paragraph.
- **Range check:** `C-1201`–`C-1226` and `S-1201`–`S-1213` are contiguous and
  collide with nothing, and **no `C-11xx` or `S-11xx` is claimed** —
  `adr_0012_per_wp_effective_tier.md` owns `C-1101`–`C-1124` and
  `S-1101`–`S-1111`. `C-1203`, `C-1209` and amendment 1 are withdrawn rows and
  are counted as occupied, never reused.

**Part 1 — liveness, forced.** Spawn a worker and kill it hard mid-phase. The
run must: fire L1 within `2 × expect_next_s`, ping, wait 3 minutes, reach L3,
and **re-spawn from the checkpoint the last beat recorded** — not restart the
phase from zero where a checkpoint existed. Kill the same worker again in the
same phase: the run must mark the work package `failed` and surface it,
**never spawn a third time**. Separately — **the test that replaces the withdrawn delta test's forced
check, because C-1206 grades freshness and nothing else** — run a worker that
beats on time for twenty minutes without ever changing `step` (a long healthy
implement phase) and assert **nothing fires**: no L1, no ping, no kill. Then
run a worker whose harness exposes output, stop its beats but keep its tool
calls flowing, and assert the L2 discriminator logs a **`Warn` protocol
violation and does not kill it**. A `blocked` beat with no `blocked_on` must
also be graded as nothing, and a worker that restarts `seq` at 1 must not be
gradeable as dead for it.

**Part 2 — resources, forced.** With `limits.heavy = 1` and two work packages
whose implement gates both run the documented verification, assert the second
**waits** and does not run concurrently. `SIGKILL` the holder mid-command and
assert the slot is **immediately reusable** — the crash-safety property the
whole rung-1 choice rests on. Point the run at a `light` gate and assert **no
lock file is created at all**. **Run two separate checkouts of the same
project concurrently and assert they contend on the same slots** — the
host-global path is the whole of C-1212's correction and the assertion that
proves it. **Assert teardown leaves the token files in place** and that a
second run reuses the same inodes. Force each preflight check to trip and
assert the hold-60s-×3-then-surface behaviour rather than an indefinite wait.

**Part 3 — sub-orchestration, forced.** A plan with a three-WP ready set on a
nesting-capable harness must show three coordinators live at once, each
running its own pipeline, with merges still serialized in topological order.
On a harness with nesting disabled, the same plan must announce
`Degraded: flat execution` and behave exactly as today. **The deadlock test is
the one that matters:** with `effective max-workers = 2`, a coordinator
blocked on its children must not prevent its own child from being spawned.

**Part 4 — telemetry, forced.** After a multi-WP run, `## Schedule log` must
carry both line kinds, **written by the parent and by nobody else**; `adr_0010`
`C-904`'s bisection must still resolve correctly, proving the filter on the
first word after the first `·`; the handoff must print **six** figures
including the work/wait split; and **no file this ADR defines may exist inside
the checkout at any point in the run** — `git status` after teardown must be
clean apart from the committed plan, and the run's out-of-tree
`${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/` must be gone while a
*different* run id's directory placed there beforehand must **survive and be
reported**.

**Dogfood benchmark — the RCA's own work package.** Re-run a **WP-1-class
change** (size S, no risk flag, ~80 lines, 2 files) on `ocx-sion` under this
ADR, measured **externally** (the run's own start and end), and compare
against the RCA's traced 3 h 06. Report **three numbers, not one**: total
wall clock, the **`wait_ms` sum** across phases (which should collapse from
the RCA's **53-minute** queue tail toward the serialized merge lane while the
ready set has spare cap), and the **detection interval** for a deliberately
killed worker. Report them alongside the plan's ready-set width, because a
plan hex could not parallelize is a plan Part 3 cannot speed up — the same
sensitivity `adr_0010` recorded for its own arithmetic. **The target for this
ADR alone is 135–150 minutes against the traced 186, not the RCA's ≤ 30** —
the § Quantified impact range, charged with the pipeline coordinator's
+12–15 min per work package and floored by root cause 1's ~90 minutes.
Reaching 30 needs `adr_0012` and is not this ADR's claim. **A measured result
above 150 falsifies this ADR's arithmetic and must be reported as such**, not
re-baselined.

## Open Questions

Hard cap 3. **Two are open**, each with a recommendation; a plain approval at
the meta-plan gate accepts both. **A third — whether the opt-in client hook
belongs in the bundle — was closed by the 2026-09-05 fix round rather than
carried**: C-1209 and amendment 1 are withdrawn, this ADR now proposes no
client-specific enforcement at all, and the reasoning is preserved as deferred
finding **D-4**. Spending a capped slot on a resolved question is worse than
leaving the slot empty.

- **[NEEDS CLARIFICATION: should `limits.heavy` ship as a new v2 config leaf,
  against `adr_0010`'s zero-new-key posture?] This is the owner's call and
  both sides are stated, not one side plus a rebuttal.** *For adding it —
  the recommendation:* unlike `M = 3`, this value **is a property of the host,
  not of the work**. It cannot have one correct shipped default (a 31 GB
  desktop and an 8 GB laptop need different numbers for the same project), and
  it cannot ride in a plan cell, because a plan travels between machines and
  would then carry one machine's number to another. That is exactly the
  carrier test `adr_0010` driver 4 states, and this value fails the plan-cell
  half of it. It is a **leaf under the already-frozen `limits` key**, following
  `workflows`' v2 precedent, so the six-key vocabulary is not reopened and an
  old reader degrades to today's behaviour rather than to an error.
  ***Against adding it in v1 — the design panel's counter-argument, which is
  not weak:*** **C-1213 derives the value, and a derived value that is right
  needs no key.** The whole point of measuring peak RSS once at `/hex-init` and
  clamping is that the number is computed from the actual host — so shipping a
  key alongside it adds config vocabulary for an **override nobody has yet
  asked for**, against `adr_0003` `C-223`'s freeze and `adr_0010` driver 4's
  posture, and every key is permanent in a way a derivation is not. The panel's
  position is **defer the key until someone needs an override**, keeping only
  the derivation; adding it later is additive and costs nothing, while removing
  a shipped key costs a deprecation. *The counter to that counter, stated so
  the owner is not deciding blind:* a derivation with no override leaves a user
  whose measurement is wrong (an unrepresentative gate, a shared CI box) with
  no way to correct it short of editing a shipped file. **Recommendation stands
  at *add it*, but a decision to defer breaks nothing in this ADR** — every
  other contract reads `limits.heavy` through C-1213's derived default.

- **[NEEDS CLARIFICATION: what belongs in the default scratch-environment
  set, given that redirecting `HOME` breaks credential-reading tools?]**
  *Recommended:* **three variables by default — `TMPDIR`, `XDG_CACHE_HOME`
  and `XDG_STATE_HOME` — with `HOME` opt-in per project via a `/hex-init`
  audit item.** **`XDG_CONFIG_HOME` was dropped from the set in the 2026-09-05
  fix round** (C-1215): redirecting it silently detaches git and the package
  managers from the developer's own configuration — `credential.helper`,
  `commit.gpgsign`, and the two that matter, **`url.*.insteadOf` rewrites and
  registry/index pinning**. Losing `insteadOf` and index pinning means a run
  silently resolving dependencies from somewhere the developer deliberately
  redirected *away* from, which is a **supply-chain downgrade**, not merely a
  broken push. The remaining three carry the whole disk-and-tmpfs argument on
  their own. **`HOME` stays out for a different reason, and it is a trade:** a
  run that cannot push because hex moved `HOME` away from the user's git
  identity, `gh` token, cargo credentials and ssh keys is a worse and more
  confusing failure than a suite writing a few files under the real one — but
  leaving it in place also leaves an untrusted repository's own verification
  command with read access to `~/.ssh`, `~/.config/gh` and `~/.aws` (§ NFR
  Security). The audit item exists to reverse the default for either reason:
  a suite that genuinely writes to `$HOME`, or a repository whose verification
  command is not trusted with the developer's credentials. This is a
  **deliberate departure from `parallel-resource-pitfalls.md`'s own
  five-variable recommendation**, now two variables narrower than the draft.

## Links

- Sibling ADR: [**`adr_0012_per_wp_effective_tier.md`**](adr_0012_per_wp_effective_tier.md)
  — per-work-package effective tier. **The seam, stated by contract id in both
  directions:** `adr_0012` decides **which phases a work package runs and at
  what model class and review breadth** (`C-1104`, `C-1108`, `C-1109`,
  `C-1110`); `adr_0013` decides **how the workers running them are supervised,
  resourced and sub-orchestrated** (`C-1219`, `C-1220`, `C-1221`, `C-1222`).
  `adr_0012` scopes its coordinator `medium` floor to the **decomposing (Q2)**
  coordinator only, so **a pipeline (Q1) coordinator does not raise a work
  package's effective tier** and `adr_0012` `C-1108`'s collapse still fires on
  a `low` WP; `adr_0012` cites `C-1206`/`C-1207` for the dead-worker trip and
  `C-1221` for the serialization tail. No overlap, no gap — this ADR's C-1219
  and C-1220 say the same thing from this side.
- Amended: [`adr_0010_execution_performance.md`](adr_0010_execution_performance.md)
  — driver 5 and `C-914`'s per-coordinator-state clause (amendment 2), **and
  `C-901`'s `join` full-verification trigger plus the `M = 3` checkpoint-counter
  reset, both rescoped to the *decomposing* coordinator (amendment 6)**.
  `C-912`'s four objections answered by name; `C-915`'s presence-check rule
  followed verbatim; `C-904`'s bisection walk preserved by C-1224's filter;
  `C-905`'s review budget preserved by amendment 7's deletion of the
  coordinator-implies-`panel` rider.
- Depended on and not disturbed: `adr_0001` (`C-002`, capability classes),
  `adr_0002` (`C-101` ready-set dispatch, `C-105` statuses and rollups),
  `adr_0003` (`C-223` key freeze and the v2 vocabulary precedent), `adr_0004`
  (`C-306` merge serialization, `C-318` lead-only `max-workers`, `C-321`
  per-repo verification), `adr_0006` (`C-502` severity, the floor C-1206's
  `Warn` uses), `adr_0009` (`C-815` trust classes).
- Research: [`rca-review-fix-loop-wall-clock.md`](../research/rca-review-fix-loop-wall-clock.md) ·
  [`parallel-resource-pitfalls.md`](../research/parallel-resource-pitfalls.md) ·
  [`liveness-heartbeat-precedent.md`](../research/liveness-heartbeat-precedent.md) ·
  [`semaphore-containment-portability.md`](../research/semaphore-containment-portability.md) ·
  [`suborchestration-telemetry-precedent.md`](../research/suborchestration-telemetry-precedent.md)
- Constitution: [`hex/DESIGN.md`](../../hex/DESIGN.md) — the extension-hook
  non-adopt (§ Spec-kit comparison round (2026-07-19, round 5)), **upheld
  with no carve-out at all** after amendment 1's withdrawal; § Worktrees
  (hex-execute parallel work packages)'s lower-only Review budget, upheld by
  amendment 7;
  round 10's sole-definition-site pattern, round 11's supersede-by-pointer
  convention, round 12's `C-914` reaffirmation.
- Shipped contract text this ADR amends: `protocol.md` § Worker coordination (the cap and the
  fan-out ladder), `protocol.md` § Worker coordination (capability classes,
  copied not extended), `protocol.md` § Parallel-by-default decomposition
  (the schedule log), `protocol.md` § Untrusted-text echoes (linked by
  C-1206 and C-1217, never restated), **`protocol.md` § Worktree
  work-package mechanics and `protocol.md` § Checkpoints (the `join`
  trigger and the checkpoint-counter reset, amendment 6)**,
  `hex-execute/SKILL.md` § Coordinator spawn (the coordinator gate),
  **`hex-execute/SKILL.md` § Coordinator spawn (the `panel` parenthetical,
  deleted by amendment 7)**, `hex-execute/SKILL.md` § 2. Resolve the target
  (resume, unchanged and greppably so), `workers/coordinator.md` §
  coordinator (mission and preconditions), **`workers/coordinator.md` §
  coordinator (the join loop, the leaf compile check and the model class —
  all scoped to the decomposing kind)**, **`models.md` § The matrix and §
  Rules (the `coordinator` row and its rule-5 tier gate, amendment 8)**.

---

## Changelog

| Date | Change |
|---|---|
| 2026-09-06 | **Errata from execution (`plan_adr_0013_runtime_contracts.md`, WP 1 – WP 8) — every correction the implementation had to make against this file, recorded here rather than by rewriting the decision above. The **Status:** line is untouched: acceptance is the owner's decision, not execution's.** *Edit sites this file's per-file table missed.* The plan added **four**: **`hex-core/SKILL.md` § References**, for which the per-file table records **no** registration site although every reference file must be listed there; **`hex-init/SKILL.md` § 1's bullets**, which enumerate the audit items the ADR adds; **`hex-init/assets/templates/plan.md` § Schedule log**, which carries the grammar comment consumers read; and **`workers/builder.md`'s copy of the leaf-under-a-coordinator carve-out**, a site amendment 6 must retarget. Review found **three further** sites of the same class: `protocol.md` § Adversary contract routed the reader to *this ADR, cited as Proposed*, for a liveness contract that now lives three sections above it in the same file, and is retargeted to the in-file anchor; `workers.md`'s role index described the coordinator as owning one **decomposable** work package, which is false for the pipeline kind; and **no leaf spawn template showed the heartbeat, agent-id and scratch fields** the coordinator's template gains, so the block an orchestrator copies for a `builder`, `tester` or `reviewer` showed none of them while `S-1201`'s dying agent is a **leaf** — closed by one sentence in `workers.md` rather than a copy in each role file, per link-never-copy. *Renumber.* The liveness rule lands as `workers.md` § Universal worker protocol **rule 8**, so the existing rules **8, 9 and 10 renumber to 9, 10 and 11**; this file named the insertion and not the renumbering. *Vocabulary version.* `limits.heavy` is marked **v1, not v2**: the key is additive under the frozen `limits` key and `config.md`'s `# hex config, vocabulary vN` comment is unchanged, so the v2 written here would have announced a vocabulary break that does not exist. *Rider sites undercounted.* Amendment 6's retargeting covers **two `coordinator-owned` sites beyond those listed** — § Verification › Scoped check's gate site 3 and its merge-site scope bullet — and the leaf carve-out is **four copies, not two**, the two extra being `workers/builder.md` and `workers/coordinator.md`. *A ninth amendment.* The plan adds **amendment 9** and it is adjudicated in `hex/DESIGN.md` round 18 alongside the other eight: the frozen six-key config vocabulary admits a **second** additive key, `limits.heavy`, on the same footing as round 14 item 3's `limits.adversary-timeout`, and the ledger now reads **numbered 1 through 9, eight live (2–9), amendment 1 withdrawn with `C-1209`**. *The heavy-slot idiom signals acquisition out of band, and `C-1212`'s "verbatim" requirement is amended for exactly that.* This file discriminates "this slot is busy" from "the command ran" on the subshell's exit status being `111`. The documented verification command is **repository-authored** and therefore chooses its own exit status: a gate that returns `111` is read as a busy slot, re-run against the next slot and re-run again on every pass until the queue budget expires, which then reports `75` for what was a failing gate — amplification through the very semaphore that exists to bound load. **The `flock -E` mitigation named here does not close it**: that flag sets the code *`flock` itself* returns on non-acquisition, which `|| exit 111` already supplies, and it cannot stop the child returning the same value. The shipped idiom therefore writes an **acquisition marker** under the worker's own redirected scratch and reads that, instead of inferring acquisition from an exit status; `111` survives as `flock`'s own non-acquisition code, so `C-1312`'s check is unaffected, and the idiom is verbatim in every other respect. *§ Migration's reversibility lever is unreachable as written.* "Set `limits.heavy` high to neutralize the semaphore" cannot fire: the key's default **is** its ceiling, so under merge rule 9 a higher project value clamps and announces rather than raising the cap. The lever at that grain is the one the same paragraph already names — discard the branch — and the liveness half of the sentence (a `Warn` rather than a kill where the agent-termination capability is absent) stands. *Three touches into `plan_adr_0012`'s sections, both plans sharing one branch.* The **seam crossing** is into `protocol.md` § Parallel-by-default decomposition › `### The effective tier`, whose coordinator-owned-parents paragraph makes the rider retargeting **six sites rather than four**. The **second** drops `hex-execute/SKILL.md` § Coordinator spawn's trailer *"rather than being `panel` by definition"*, whose only purpose was to contrast with the inference amendment 7 removes. The **third** retargets `hex-execute/SKILL.md` § 6's `Recursion:` example lines, which still read *"others → single builder (below gate)"* — false under Q1, and in the very block the new Schedule step feeds. *Telemetry grammar.* The `phase` line's `wait` field is **bracketed** — simply absent whenever its start is unknown — where this file's grammar wrote it unbracketed and therefore mandatory. *A class of defect in the plan's own checks, not in this ADR.* **Five of the plan's Phase 3 check rows were unsatisfiable** against their own contracts or against pre-existing text — `C-1315`, `C-1321`, `C-1341`, `S-1311` and `S-1314` — and were corrected during execution by the negative-clause or section-scoping idiom the same table already used elsewhere; recorded here because the class, not any single row, is the finding. *Two clause spans this plan froze were narrowed at the convergence pass, because a frozen clause that states something false is the worse error.* **`C-1335`'s Preconditions freeze** covers the ≥ 3 test only, not the clause's outcome sentences: "else the orchestrator runs the WP with a single builder" is what Q1 falsified — under Q1 a work package answering no to Q2 still gets a **pipeline** coordinator, and it is that coordinator, not the orchestrator, that runs the single builder. § Fan-out's cycle fallback carried the same error and is reworded with it; the ≥ 3 test itself still diffs byte-identical. **`C-1347`'s round heading takes 2026-09-06**, the day the round was written, not the ADR's own 2026-09-05: the earlier date made `DESIGN.md`'s dates regress against round 17 in an append-only record. A **fourth seam touch** into `plan_adr_0012`'s sections was needed at `hex-execute/SKILL.md`'s worker-assignment phase table, whose coordinator row still read "0–1 per qualifying WP … granularity gate", which Q1 falsifies. And `CHANGELOG.md`'s `[Unreleased]` heading is cut as `[0.3.0] - 2026-09-06` in the same commit as the version bump, following `e9c00d6`'s precedent, so the release does not ship notes headed "Unreleased". |
| 2026-09-05 | **Design-panel fix round (F1–F12) — six Blocks and every High absorbed, applied against this file as canonical.** *F1, the coordinator riders.* The word *coordinator* carries **six** behavioural riders across four shipped files, not one identity: C-1219 now enumerates every one and assigns each to Q1 or Q2 — the `join` full-verification trigger and the `M = 3` checkpoint-counter reset (`protocol.md:828-831`, `:1222`), `coordinator.md:39`'s 1-round join loop and `:48`'s scoped leaf compile check, and the deep-reasoning class with its medium/high tier gate (`coordinator.md:53-56`, `models.md:41`/`:100-101`) are all **Q2-only**; `hex-execute/SKILL.md:561-564`'s *"a coordinator WP is by definition `panel`"* is **deleted for both kinds**. Three new numbered amendments carry the retargeting — **6** (`join` + counter, which **changes `adr_0010` `C-901`'s firing condition**), **7** (breadth stays the WP's budgeted `Review`, `C-905` + `adr_0012`'s per-WP tier), **8** (a pipeline coordinator resolves to the WP's effective tier, `adr_0012` `C-1109`/`C-1110`; a decomposing one keeps deep-reasoning). `models.md` added to the edit-site list. **The false claims that "adr_0010's verification budget — untouched" and S-1211's "C-901's gate triggers are untouched" are deleted at every site.** *F2 already landed:* the top orchestrator is the sole ladder runner. *F3, the delta test.* C-1203 stays withdrawn and its last three consumers go with it — S-1204 keeps `blocked`'s real job (the C-1211 cap exemption), S-1205 loses it, and § Validation's forced test is replaced by one that tests what C-1206 actually grades: freshness, the L2 `Warn` discriminator, a missing `blocked_on` graded as nothing, and a restarted `seq` that must not kill. *F4, the spool.* **`.hex/run.jsonl` deleted outright** — with it the `PIPE_BUF`/`O_APPEND` reasoning, the line-size rule, its failure modes, C-1226's teardown-ordering dependency, its `.gitignore` line and the telemetry half of amendment 2. **C-1223 is rewritten as one writer, one place**: the parent renders the plan's `## Schedule log` from its own `date -u +%FT%TZ` brackets (`protocol.md:638-642`) and from each coordinator's existing structured return (`coordinator.md:71-75`). C-1224's grammar and C-1225's field set survive in substance as what the parent writes; **`wait_ms` has one definition** (phase runnable → worker begins work) and the competing ones are gone; **C-1226 now lists six figures, adding the work/wait split**; a dying coordinator loses only unreturned timings (D-5). *F5, out of the repository.* Heartbeats live at `${XDG_CACHE_HOME:-$HOME/.cache}/hex/<run-id>/hb/`, so **`.hex/` disappears from the checkout completely** — all fifteen in-tree sites deleted, **no `.gitignore` line anywhere in this ADR**, the audit item that proposed one dropped, amendment 5 **rewritten** (one artifact, not two) rather than withdrawn, and § Validation restated against the out-of-tree path. Sweep rule made decidable by `<run-id>`: **report, never delete, another run's directory; delete only the run's own.** Path resolution stated once in C-1201 and referenced from C-1212. *F6, teardown safety.* `docker system prune -f --volumes` **replaced** by `docker container prune -f --filter label=<the run's own label>`, and only where the run set that label — otherwise report and delete nothing; every heavy command starts under its own `setsid` process group whose id is recorded at spawn, and **teardown signals only recorded group ids**; ids and slugs are orchestrator-minted to `[a-z0-9][a-z0-9-]{0,63}` and **teardown refuses any delete target that does not resolve under its own run-root prefix**. *F7, the semaphore fails closed.* The § Technical Details idiom **is** C-1212 now: `flock -w "$QUEUE_WAIT" 9 || exit`, the command run `9>&-` so descendants never inherit the slot, an overflow waiter that re-enters the full non-blocking 1..N scan on timeout, a stated terminal outcome on budget expiry (exit 75, `failed` beat, surfaced — never proceed unlocked) and the leaked-slot recovery path (`fuser`/`lsof`, never unlink). *F8, untrusted output.* C-1217's *report verbatim* is deleted: the **worker** classifies and returns a bounded `oom-evidence: "<≤120 chars, quoted>"`; `#untrusted-text-echoes` linked from C-1217 as well as C-1206; and **`heavy` moves only on corroboration from a host source** (`/proc/pressure`, `dmesg`, or a measured-profile overshoot), so planted repository text alone cannot walk a run's concurrency down to 1. New **S-1213** exercises the three-way triage. *F10 residue.* Open question 2 restated at **three** scratch variables (matching C-1215); NFR Security states the `HOME` trade-off **in both directions** and the audit item names credential exposure; open question 1 restated with the panel's defer-the-key counter-argument, recommendation unchanged. Open question 3 **closed rather than carried** — the client hook was withdrawn, so the slot is left empty rather than spent on a resolved question; **two open questions remain**. *F11, arithmetic.* The corrected figures propagate to every site: **53-minute tail**, **+12–15 min per WP**, **135–150 min** published — C-1222, C-1225, S-1211, NFR Latency and the dogfood benchmark all carried pre-correction numbers and no longer do. *F12 residue.* `id` deleted from the heartbeat worked example; `seq` never grades liveness and a missing `blocked_on` is graded as nothing, both stated at the grammar; `protocol.md:475-483` → **`:474-483`** (the other five citations were already correct); the `## Schedule log` discriminator is **the first word after the first `·`**, never "the second token"; `${XDG_CACHE_HOME:-$HOME/.cache}` used everywhere including the scratch root; the contract-ID evidence restated against `adr_0012_per_wp_effective_tier.md` as it now stands on disk (`C-1101`–`C-1124`, `S-1101`–`S-1111`, cited-not-claimed); **D-7** added for **sleep and suspend**, which suspends the whole fleet and would make a staleness discriminator announce the wrong diagnosis. *The seam with `adr_0012`* is now stated by contract id from this side too — `C-1104`/`C-1108`/`C-1109`/`C-1110` cited at C-1219, C-1220 and § Links, **a pipeline (Q1) coordinator does not raise a work package's effective tier** so `C-1108`'s collapse still fires, and the ownership split matches `adr_0012`'s own § Seam paragraph with no overlap and no gap. **Amendment ledger reconciled at all three sites** — Metadata, the section header and the table now state the same set: **numbered 1–8, seven live (2–8), amendment 1 withdrawn with C-1209** — and with it **this ADR proposes no client-specific enforcement at all**, verified by grep, so `hex/DESIGN.md:339-341` needs no carve-out. Cross-model review skipped: budget. Status stays **Proposed**. |
| 2026-09-05 | Initial draft. `C-1201`–`C-1226`, `S-1201`–`S-1212`; four scored option axes; five proposed `DESIGN.md` amendments; the ephemeral/durable split answering `adr_0010` `C-912`'s four objections by name. Corrections to the commissioning sketch, each stated in place: `limits.max-workers` is **not** renamed to `limits.workers` (a frozen-key rename is a silent no-op); the heartbeat directory is run-root, not worktree-local; the scratch set is four variables with `HOME` opt-in, not five. Deferred findings D-1 (slot sharing is per-checkout, not per-host), D-2 (the delta test cannot see wrong progress), D-3 (`expect_next_s` is worker-trusted). |
| 2026-09-05 | **Correction round against the commissioning brief — five defects found in the brief itself, applied here and in the companion system design so the two agree.** (1) **C-1212**: the heavy-slot directory moves from `<run root>/.agents/locks/` to the host-global `${XDG_CACHE_HOME:-$HOME/.cache}/hex/locks/heavy-{1..N}` — the semaphore meters a host resource, so its slots must be host-scoped; two projects deriving different `N` bound the host at `max(N)`, never the sum. The path is resolved once by the orchestrator and passed in the spawn prompt, because a worker's own `XDG_CACHE_HOME` is redirected by C-1215. **The drvfs relocation rule and its announcement are deleted, not deprecated** — `$HOME/.cache` is never on `/mnt/c`. **D-1** is re-scoped to the residual that survives: sessions that do not share a `$HOME`. (2) **C-1205**: a **leaf's** checkpoint is a path and never a commit SHA (it would contradict `workers.md:39-40`, "Never auto-commit"); the SHA form is **coordinator-only**, where `coordinator.md:49-51` already commits one. (3) **C-1217**: the lock-wait signal splits three ways — waiting on hex's own slot is the mechanism working and is **not** a signal, a build tool's own lock wait is a **configuration** fault that warns without lowering `heavy`, and only resource-exhaustion evidence lowers the cap. Without the discriminator `heavy` collapsed to 1 on the first busy wave of every run. (4) **C-1216**: the lock token files are zero-byte, permanent and **never deleted** by teardown or any sweep — unlinking a held token gives the next `open()` a fresh inode and hands one slot to two holders. (5) **C-1202 / C-1206**: every heartbeat file has exactly one writer, its own agent, always; `failed` in the enum means "the agent reported its own failure", never "the parent declared it dead", and a dead agent's terminal state is recorded in the plan's Status column. |
