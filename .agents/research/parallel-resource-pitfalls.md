# Research: Resource pitfalls of parallel agent worktrees

<!--
Technology-landscape research, hex research template. Owner: hex
orchestrator (synthesis of five sonnet research lanes, 2026-09-05).
Handoff to: /hex-architect (runtime-contracts ADR: liveness, limits.heavy,
resource profile), /hex-plan.
Findings decay — check Expires before trusting them.
-->

## Metadata

**Date:** 2026-09-05
**Domain:** devops | testing | ci-cd
**Triggered by:** hex execution-performance RCA follow-up — a RAM warning in
the prompt cut *spawns* instead of *heavy commands*; two OOM kills on the
ocx host; a disk filled by per-worktree test artifacts; the question "what
must the AI know before it provokes an outage?"
**Expires:** 2027-03-05
**Lanes:** A local evidence (~/dev, read-only) · B Rust · C Python/Node/JVM/Go/containers · D OS/WSL2 containment · E prior art

## Direct Answer

An agent process costs ~0 local RAM. Outages come from what the agent
*runs* in its worktree, multiplied by the worktree count. Seven classes,
in the order they bite on a single developer machine:

1. **Per-worktree build/test parallelism defaults to `nproc`.** N worktrees
   × `nproc` compile/test jobs; cargo has no load or memory limiter
   ([cargo#12912](https://github.com/rust-lang/cargo/issues/12912)). The
   desktop freezes for minutes *before* the OOM killer fires. **This, not
   language servers, was the measured cause of both ocx OOM kills**
   (`ocx/.claude/rules/workflow-swarm.md:236-247`, 32 cores, 31 GB + 32 GB swap).
2. **Build outputs per worktree.** Rust `target/` is 10–18 GB *each* on ocx
   right now (four live wave-2 worktrees = 61 GB; ocx-sion wp-5 = 11 GB).
   Sharing one `CARGO_TARGET_DIR` does not help: cargo's build lock
   serializes and absolute-path fingerprints thrash.
3. **`/tmp` is tmpfs, i.e. RAM.** On this host `/tmp` is a 64 GB tmpfs on a
   31 GB box. Test artifacts "filling the disk" there are an OOM, not
   ENOSPC. ocx already redirects `TEST_TMPDIR` to disk
   (`ocx/test/taskfile.yml:22-29`).
4. **Language servers per activated worktree.** rust-analyzer ≈ 4 GB per
   instance here; 40–44 GB with `cachePriming` + `cargo.autoreload` in the
   serena topology ([serena#1556](https://github.com/oraios/serena/issues/1556)).
   Serena runs one MCP server per Claude *session*, not per worktree; a
   worktree becomes a second instance only if activated as a project. ocx
   excludes `.agents/worktrees` in `.serena/project.yml`; **arcana does not**
   (`ignored_paths: []`).
5. **Watcher and fd limits are per user, shared by every agent.** inotify
   `max_user_watches` (kernel default 8192) and `max_user_instances` (128,
   one per watcher *process*) surface as a misleading "No space left on
   device". Host is already raised to 524288 / 128.
6. **Orphans survive SIGKILL.** Shell `trap` cleanup, testcontainers' Ryuk
   reaper, and Gradle daemons all outlive a killed worker
   ([claude-code#18405](https://github.com/anthropics/claude-code/issues/18405),
   [testcontainers#739](https://github.com/testcontainers/testcontainers-java/issues/739)).
   Cleanup must be owned by the orchestrator's teardown, never by the worker.
7. **WSL2 ceilings.** Default guest RAM = min(50 % host, 8 GB); the ext4
   VHDX grows and never shrinks (cap 256 GB → 1 TB by release); `wsl
   --shutdown` is the only reliable RAM return. Host `.wslconfig` is already
   set to 32 GB / 32 GB swap / `autoMemoryReclaim=gradual`.

**Design consequence for hex:** cap *heavy commands* (build, test, verify,
merge gate) with a counting semaphore sized from a measured resource
profile; leave spawn count bound by API limits; give every run a
disk-backed scratch env the orchestrator deletes; exclude agent worktrees
from every watcher; preflight before each spawn wave.

## Local evidence (Lane A, verified 2026-09-05)

| Item | State | Note |
|---|---|---|
| ocx OOM kills ×2 | root-caused, mitigated | unbounded cargo/nextest parallelism across worktrees; `.cargo/config.toml` `[build] jobs = 4`, `.config/nextest.toml` `test-threads = 8` |
| ocx serena | mitigated | `.serena/project.yml` `ignored_paths` excludes `.agents/worktrees` ("starts ANOTHER rust-analyzer rooted there, ~4 GB each") |
| ocx pytest tmp | mitigated | `tmp_path_retention_count=1`, `policy="failed"`; `TEST_TMPDIR=~/.cache/ocx-test-tmp` (disk) injected as `TMPDIR` |
| arcana serena | **gap** | `.serena/project.yml:75` `ignored_paths: []`; `.vscode/settings.json` no worktree exclusion |
| ocx worktrees | 61 GB | wp-3..wp-6, live wave 2 of `plan_toolchain_activation`; ~10–15 GB `target/` each — cleanup must follow merge |
| host memory now | pressured | 31 GB RAM, swap 16/32 GB in use; rust-analyzer ×3 = 2.2 GB, VS Code server ×71 procs = 3.1 GB |
| `/tmp` | tmpfs 64 GB | RAM+swap backed |
| `/` | 763 GB free | disk not the constraint today |
| "thousands of pytest records" | not reproducible now | `/var/tmp/pytest-of-mherwig` 16 MB; `~/.cache/ocx-test-tmp` 123 entries, 460 KB — the retention fix closed it |

## Pitfall catalog

Deduplicated across lanes. *Detect* commands run in < 2 s.

| # | Class | Pitfall | Symptom | Detect | Mitigate | Source |
|---|---|---|---|---|---|---|
| 1 | Memory | `-j nproc` per worktree × N worktrees | freeze, then OOM kill mid-link | `cat /proc/pressure/memory`; `uptime` vs `nproc` | cap jobs ≈ `nproc / N_heavy`; orchestrator semaphore; `-l` load gate where the tool has one | [cargo#12912](https://github.com/rust-lang/cargo/issues/12912), [ninja -l](https://github.com/ninja-build/ninja/pull/274) |
| 2 | Memory | linker/LTO RSS spike (7–30 GB) while loadavg looks idle | OOM despite healthy load | `/usr/bin/time -v <build>` peak RSS | `mold`/`lld`; no LTO locally; serialize link steps | [rust#83911](https://github.com/rust-lang/rust/issues/83911) |
| 3 | Memory | freeze precedes OOM killer | 30–90 s unresponsive | `vmstat 1` si/so rising | `earlyoom` / `systemd-oomd` (PSI-based) | [earlyoom](https://github.com/rfjakob/earlyoom) |
| 4 | Memory | `ulimit -v` / `prlimit --as` on rustc, JVM, Go | spurious "Resource temporarily unavailable" | reproduce under `ulimit -v` | cgroup `memory.max`, never RLIMIT_AS for compiled-lang workers | [rust#115021](https://github.com/rust-lang/rust/issues/115021) |
| 5 | Memory | `/tmp` tmpfs = RAM | "disk full" is an OOM | `mount \| grep ' /tmp '`; `df -h /tmp` | `TMPDIR` to disk for heavy suites; cap tmpfs `size=` | [tmpfs docs](https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html) |
| 6 | Memory | rust-analyzer per activated worktree; `cachePriming`+`autoreload` | 4 GB each, 40 GB pathological | `ps -C rust-analyzer -o rss=` | exclude `.agents/worktrees` in `.serena/project.yml`; RA only for the human's checkout; `cachePriming.enable=false` for background | [serena#1556](https://github.com/oraios/serena/issues/1556) |
| 7 | Memory | Gradle/Kotlin daemon per JVM-args/JDK combo, 3 h idle | GBs held hours after tests | `./gradlew --status`; `jps -l` | identical `org.gradle.jvmargs`; `--no-daemon` for workers; `./gradlew --stop` in teardown | [Gradle env](https://docs.gradle.org/current/userguide/build_environment.html) |
| 8 | Memory | test runners default to all cores per invocation (xdist `-n auto`, Jest `cores-1`, Go `-p`, `RUST_TEST_THREADS`) | RAM = workers × app import × worktrees | `ps aux --sort=-rss \| head` | explicit `-n`/`--maxWorkers`/`GOFLAGS=-p`/`--test-threads` = `nproc / N_heavy`; Jest `--workerIdleMemoryLimit` | [xdist](https://pytest-xdist.readthedocs.io/en/stable/distribution.html), [Jest](https://jestjs.io/docs/cli), [nextest](https://nexte.st/docs/configuration/threads-required/) |
| 9 | Disk | `target/` 2–20 GB per worktree, never shrinks | disk fill across N worktrees | `du -sh .agents/worktrees/*/target` | delete with the worktree; `cargo sweep --time N`; `-Zno-embed-metadata` | [cargo#16665](https://github.com/rust-lang/cargo/issues/16665), [Kobzol](https://kobzol.github.io/rust/rustc/2025/06/02/reduce-cargo-target-dir-size-with-z-no-embed-metadata.html) |
| 10 | Disk | shared `CARGO_TARGET_DIR` across worktrees | "Blocking waiting for file lock"; full rebuilds anyway | grep worker logs for the lock message | per-worktree target + `sccache` with `SCCACHE_BASEDIRS`, or content-addressed hardlink store | [cargo#2627](https://github.com/rust-lang/cargo/issues/2627), [howardjohn](https://blog.howardjohn.info/posts/shared-rust-build/) |
| 11 | Disk | `node_modules` per worktree (~2 GB) | 5 worktrees ≈ 10 GB duplicate | `du -sh */node_modules` | pnpm store + `node-linker=hardlink` (~50 MB/worktree) | [pnpm worktrees](https://pnpm.io/git-worktrees) |
| 12 | Disk | pytest basetemp keeps 3 runs; `.hypothesis`; `.coverage.*` shards; report logs | slow fill per worktree | `du -sh /tmp/pytest-of-$USER .hypothesis`; `find . -name '.coverage.*' \| wc -l` | `tmp_path_retention_policy=failed`, `count=1`; `--basetemp=<scratch>`; `coverage combine && erase`; reports to scratch | [pytest tmp_path](https://docs.pytest.org/en/stable/how-to/tmp_path.html), [Hypothesis DB](https://hypothesis.readthedocs.io/en/latest/database.html) |
| 13 | Disk | tests writing `$HOME` / XDG dirs | cross-worktree state bleed, growth | mtime diff under `~/.cache` | per-run `HOME`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `XDG_CONFIG_HOME`, `TMPDIR` | [pytest#1120](https://github.com/pytest-dev/pytest/issues/1120) |
| 14 | Disk | `uv` hardlink → copy fallback across filesystems | silent 2× venv disk | uv logs "Failed to hardlink" | same fs for worktrees + `UV_CACHE_DIR`; `UV_LINK_MODE=hardlink`; `uv cache prune` | [uv#9500](https://github.com/astral-sh/uv/issues/9500) |
| 15 | Disk | Nx/Turbo/Jest caches, no eviction | 4.5–100 GB reports | `du -sh .turbo .nx/cache node_modules/.cache` | redirect to one dir outside worktrees; clear in teardown | [turborepo#7029](https://github.com/vercel/turborepo/issues/7029) |
| 16 | Disk | disk-full mid-write | git "unable to write new index"; sqlite "disk is full"; fingerprint corruption | `df --output=avail -BG <path>` | preflight threshold, abort before start | [cargo#12744](https://github.com/rust-lang/cargo/pull/12744) |
| 17 | Disk | `systemd-tmpfiles` reaps `/tmp` after 10 d by atime, may not run on WSL | live basetemp vanishes mid-run, or never cleaned | `systemctl list-timers systemd-tmpfiles-clean.timer` | dedicated per-run scratch, orchestrator-deleted | [systemd temp dirs](https://systemd.io/TEMPORARY_DIRECTORIES/) |
| 18 | Watchers | inotify `max_user_watches` 8192 default, per-UID pool | ENOSPC from `inotify_add_watch` | `cat /proc/sys/fs/inotify/max_user_watches`; `find /proc/*/fd -lname anon_inode:inotify 2>/dev/null \| wc -l` | `sysctl fs.inotify.max_user_watches=524288`; fewer watcher instances | [watchexec](https://watchexec.github.io/docs/inotify-limits.html) |
| 19 | Watchers | `max_user_instances` 128, one per watcher process | new watcher silently fails | `cat /proc/sys/fs/inotify/max_user_instances` | `sysctl fs.inotify.max_user_instances=1024`; no `--watch` in one-shot runs | [lkml](https://lkml.iu.edu/hypermail/linux/kernel/2010.3/01777.html) |
| 20 | Watchers | `ulimit -n` 1024 soft per process | EMFILE in one runner | `ulimit -Sn`; `cat /proc/sys/fs/file-nr` | `LimitNOFILE=` on the scope, `limits.d` | [fd limits](https://devopsbeast.com/blog/file-descriptor-limits-explained) |
| 21 | Orphans | SIGKILL skips `trap`; Ryuk skips; nested subagent trees | GBs held by dead sessions (14–56 GB reports) | `ps -eo pid,ppid,rss,comm --sort=-rss \| head`; `docker volume ls -f dangling=true` | orchestrator-owned teardown: kill process group, `docker system prune -f --volumes`, `./gradlew --stop` | [claude-code#18405](https://github.com/anthropics/claude-code/issues/18405), [testcontainers#739](https://github.com/testcontainers/testcontainers-java/issues/739) |
| 22 | Orphans | worktrees never pruned (Cursor: 140 GB/week) | disk creep unnoticed | `git worktree list`; `du -sh .agents/worktrees/*` | sweep on start, remove on merge (worktree hygiene rule already in global CLAUDE.md) | [Cursor forum](https://forum.cursor.com/t/windows-request-to-disable-automatic-worktree-creation-critical-disk-space-issue/146189) |
| 23 | WSL2 | guest RAM default min(50 %, 8 GB) | OOM inside guest, host idle | `free -m` vs Task Manager | `.wslconfig` `memory=`, `wsl --shutdown` | [WSL#9636](https://github.com/microsoft/WSL/issues/9636) |
| 24 | WSL2 | VHDX grows, never shrinks; cap 256 GB–1 TB | "disk full" with free space in `df` | compare `df` vs `.vhdx` size | `wsl --shutdown` + `diskpart compact vdisk`; `sparseVhd` had corruption reports | [MS Learn](https://learn.microsoft.com/en-us/windows/wsl/disk-space) |
| 25 | WSL2 | worktrees on `/mnt/c` cross 9P | 10–20× slower git/build, false timeouts | `time git status` | worktrees under `~` only | [WSL#8588](https://github.com/microsoft/WSL/issues/8588) |
| 26 | WSL2 | page cache never returned (`vmmem`) | host starved | Task Manager `vmmem` | `autoMemoryReclaim=gradual`; `wsl --shutdown` | [Hovhannisyan](https://www.aleksandrhovhannisyan.com/blog/limiting-memory-usage-in-wsl-2/) |

## Per-ecosystem knob sheet

What the orchestrator sets per heavy command. `N_heavy` = concurrent heavy slots.

| Ecosystem | Parallelism default | Cap knob | Per-worktree artifact | Share / redirect | Retention |
|---|---|---|---|---|---|
| cargo | `-j nproc` | `CARGO_BUILD_JOBS`, `[build] jobs` | `target/` 2–20 GB | do **not** share target; `sccache` + `SCCACHE_BASEDIRS` | `cargo sweep --time N`; delete with worktree |
| nextest / `cargo test` | ncpu | `--test-threads`, `--jobs`, `RUST_TEST_THREADS`, `threads-required` | tempfile under `TMPDIR` | per-run `TMPDIR` | — |
| pytest | xdist `-n auto` | `-n K` | `/tmp/pytest-of-*`, `.hypothesis`, `.coverage.*`, reports | `--basetemp`, `TMPDIR`, `HYPOTHESIS_DATABASE_FILE` | `tmp_path_retention_policy=failed`, `count=1`; `coverage combine && erase` |
| Jest | `cores-1` | `--maxWorkers`, `--workerIdleMemoryLimit` | `cacheDirectory` (OS tmp) | per-worktree cacheDirectory | `--clearCache` |
| Node deps | — | — | `node_modules` ~2 GB | pnpm store, `node-linker=hardlink` | `pnpm store prune` |
| tsc | one V8 heap/process | `NODE_OPTIONS=--max-old-space-size` = RAM/N_heavy | — | — | — |
| Gradle | workers = ncpu; daemon per args combo | `--max-workers`, `maxParallelForks`, `--no-daemon` | `.gradle/` | identical `jvmargs`; `~/.gradle/caches` shared | `./gradlew --stop` |
| Go | `-p NumCPU` | `GOFLAGS=-p=K` | — | `GOCACHE`/`GOMODCACHE` shared by default | `go clean -cache` |
| Docker/testcontainers | — | — | containers, anonymous volumes, build cache | — | `docker system prune -f --volumes` in teardown |
| Playwright | — | — | 1.2 GB browsers *if* `PLAYWRIGHT_BROWSERS_PATH=0` | leave default `~/.cache/ms-playwright` | — |

## Containment ladder (per heavy command)

1. `systemd-run --user --scope -p MemoryMax=<G> -p MemoryHigh=<G> -p CPUQuota=<N>00% <cmd>` — cgroup v2, RSS+cache aware; WSL2 needs `/etc/wsl.conf` `[boot] systemd=true`.
2. No user systemd: raw cgroupfs v2 (`mkdir /sys/fs/cgroup/hex-<id>`, write `memory.max`, `cgroup.procs`, `exec`). Not `cgcreate` (libcgroup is v1-only).
3. No cgroup access: `nice -n 19 ionice -c3 <cmd>`. Shrinks blast radius, no cap.
4. Last resort, scripting-language workers only: `ulimit -v`. Never for rustc, JVM, Go.
5. Always: `timeout --kill-after=10s <wall> <cmd>` as the wall-clock backstop.

## Preflight before every spawn wave (< 2 s)

| Check | Command | Hold when |
|---|---|---|
| disk on worktree + scratch volume | `df --output=avail -BG <path> \| tail -1` | < 5 GB (per-repo tunable) |
| memory pressure | `cat /proc/pressure/memory` → `full avg10` | > 10 % |
| load vs cores | `cat /proc/loadavg` vs `nproc` | > 1.5 × nproc |
| inotify headroom | limits vs `find /proc/*/fd -lname anon_inode:inotify 2>/dev/null \| wc -l` | > 80 % |
| fd headroom | `ulimit -Sn` vs `/proc/sys/fs/file-nr` | nearing soft limit |
| stale worktrees | `git worktree list`; `du -sh .agents/worktrees/*` | any not in the plan's active set |

## Design Patterns Worth Considering

- **Two caps, not one.** `limits.workers` (API-bound, agents are free) and
  `limits.heavy` (hardware-bound: builder:implement, tester, merge and
  checkpoint gates). Prior art: GitLab Runner `concurrent` vs `limit`;
  make/ninja keep `-j` and `-l` independent.
- **Measured resource profile, with floor and ceiling.** `/hex-init` runs
  the documented gate once under `/usr/bin/time -v`, stores peak RSS + wall
  in `hex.md › Pointers`, derives `heavy = floor((RAM − headroom) /
  peakRSS)`. Bazel's `HOST_RAM*.67` is the precedent and its tracker shows
  a bare fraction misfires at 8 GB and 256 GB alike, so clamp to
  `[1, nproc/jobs]`. Parse-only gates (arcana `grim build`) → unbounded.
- **Load-average and PSI gate at spawn time**, separate from the count cap
  (make `-l`, ninja `-l`). A semaphore sized on cores misses a machine
  already loaded by the human's own work.
- **Per-run scratch env, orchestrator-deleted.** `TMPDIR`, `HOME`,
  `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `XDG_CONFIG_HOME` → disk-backed
  `~/.cache/hex/<run>/<wp>`; deleted by the orchestrator's teardown, never
  by a worker `trap` (SIGKILL skips it). ocx's `TEST_TMPDIR` is the
  in-house precedent.
- **Teardown owns everything the worktree produced**: worktree, redirected
  build dirs, caches, daemons, containers, process group. Sweep + warn on
  start. Ephemeral-VM platforms (Copilot agent, Jules, Devin) get this for
  free by destroying the VM; shared-host worktree platforms (Claude Code,
  Cursor) are exactly where the field reports concentrate.
- **Recycle on threshold, not only cap on start** (Jest
  `--workerIdleMemoryLimit`). A heavy command exceeding profile × 1.5 is
  pulled, its finding logged as a concurrency-reduction signal.
- **Worker output is a resource signal.** "Blocking waiting for file lock",
  inotify ENOSPC, V8 "heap out of memory", `dmesg` OOM lines → lower
  `heavy` for the run, never retry as a flake.
- **Watcher hygiene as a checked-in convention.** Exclude
  `.agents/worktrees` from `.serena/project.yml` `ignored_paths`,
  `.vscode/settings.json` `files.watcherExclude`, and any `--watch` tooling;
  agent worktrees never activate a language server.

## Key Findings

1. The local OOM incidents were build parallelism, not language servers; serena is one MCP server per Claude session and rust-analyzer was ~3.6 GB shared across three worktrees when measured. Source: `ocx/.claude/rules/workflow-swarm.md:236-247`.
2. rust-analyzer *can* reach 40–44 GB in the serena topology when `cachePriming` and `cargo.autoreload` are on. [serena#1556](https://github.com/oraios/serena/issues/1556)
3. cargo has no load-average or memory-aware limiter; `-j` defaults to `nproc` per invocation. [cargo#12912](https://github.com/rust-lang/cargo/issues/12912)
4. Sharing `CARGO_TARGET_DIR` across worktrees serializes on the build lock and thrashes absolute-path fingerprints; hardlink-based sharing costs < 1 s / 0 GB vs 2m19s / 127 GB for copies. [howardjohn](https://blog.howardjohn.info/posts/shared-rust-build/), [cargo#2627](https://github.com/rust-lang/cargo/issues/2627)
5. `/tmp` on this host is a 64 GB tmpfs on 31 GB RAM; kernel default tmpfs size is 50 % of RAM. [tmpfs docs](https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html)
6. RLIMIT_AS breaks rustc's parallel front-end and JVM/Go address reservations; cgroup `memory.max` is the correct bound. [rust#115021](https://github.com/rust-lang/rust/issues/115021)
7. inotify limits are per UID and shared by all agents' watchers; `max_user_instances` counts watcher processes, not watches. [watchexec](https://watchexec.github.io/docs/inotify-limits.html)
8. Orphaned subagent/MCP/browser processes after crashes hold tens of GB; no first-party fix in Claude Code as of the report. [claude-code#18405](https://github.com/anthropics/claude-code/issues/18405)
9. Bazel derives local RAM budget as 67 % of host RAM and its own tracker documents the failure of a fixed fraction at both ends. [bazel#3886](https://github.com/bazelbuild/bazel/issues/3886)
10. No surveyed AI coding-agent platform publishes a liveness/heartbeat protocol for its parallel fleet; Temporal, MCP progress notifications, and A2A `TaskStatusUpdateEvent` do. [Temporal](https://docs.temporal.io/design-patterns/long-running-activity), [MCP progress](https://modelcontextprotocol.io/specification/2025-03-26/basic/utilities/progress), [A2A](https://a2a-protocol.org/latest/specification/)
11. pytest ≥ 7.3 has `tmp_path_retention_policy` / `tmp_path_retention_count`; ocx sets `failed` / 1. [pytest tmp_path](https://docs.pytest.org/en/stable/how-to/tmp_path.html)
12. Codex's trace-level SQLite logging wrote ~640 TB/yr and wore out SSDs; logging is a resource pitfall too. [codex#28224](https://github.com/openai/codex/issues/28224)

## Where it lands in hex

- `hex-core/references/resources.md` (new) — this catalog, trimmed to the
  knob sheet + preflight + ladder, linked from `protocol.md` § Worker
  coordination so every orchestrator reads it before a spawn wave.
- `config.md` — `limits.heavy`; `hex.md › Pointers` rows `Resource
  profile:` (peak RSS, wall, gate class) and `Scratch:` (disk-backed root).
- `protocol.md` § Worker coordination — preflight table, heavy semaphore
  (`flock` slots under `.agents/locks/`), teardown ownership, output-as-signal
  rule; § Worktree work-package mechanics — teardown deletes redirected
  build dirs.
- `workers.md` — heavy roles take a slot; universal rule: run under the
  per-run scratch env; report lock-wait/ENOSPC/OOM lines verbatim.
- `/hex-init` audit items — "Resource profile measured?", "Agent worktrees
  excluded from watchers?", "Scratch/temp convention documented?".
- Immediate local gaps outside hex: arcana `.serena/project.yml`
  `ignored_paths` add `.agents/worktrees`; ocx wave-2 worktrees (61 GB)
  removed on merge per the worktree-hygiene rule.

## Sources

Lane reports are in the session scratchpad; every row above carries its
link inline. Primary anchors: [cargo#12912](https://github.com/rust-lang/cargo/issues/12912) ·
[cargo#2627](https://github.com/rust-lang/cargo/issues/2627) ·
[serena#1556](https://github.com/oraios/serena/issues/1556) ·
[rust#115021](https://github.com/rust-lang/rust/issues/115021) ·
[watchexec inotify](https://watchexec.github.io/docs/inotify-limits.html) ·
[systemd temp dirs](https://systemd.io/TEMPORARY_DIRECTORIES/) ·
[tmpfs](https://www.kernel.org/doc/html/latest/filesystems/tmpfs.html) ·
[MS Learn WSL disk](https://learn.microsoft.com/en-us/windows/wsl/disk-space) ·
[WSL#9636](https://github.com/microsoft/WSL/issues/9636) ·
[claude-code#18405](https://github.com/anthropics/claude-code/issues/18405) ·
[testcontainers#739](https://github.com/testcontainers/testcontainers-java/issues/739) ·
[bazel#3886](https://github.com/bazelbuild/bazel/issues/3886) ·
[pytest tmp_path](https://docs.pytest.org/en/stable/how-to/tmp_path.html) ·
[pnpm worktrees](https://pnpm.io/git-worktrees) ·
[Jest CLI](https://jestjs.io/docs/cli) ·
[Gradle env](https://docs.gradle.org/current/userguide/build_environment.html) ·
[Temporal heartbeats](https://docs.temporal.io/design-patterns/long-running-activity) ·
[A2A spec](https://a2a-protocol.org/latest/specification/) ·
[MCP progress](https://modelcontextprotocol.io/specification/2025-03-26/basic/utilities/progress) ·
[Cursor worktree disk](https://forum.cursor.com/t/windows-request-to-disable-automatic-worktree-creation-critical-disk-space-issue/146189) ·
[codex#28224](https://github.com/openai/codex/issues/28224)
