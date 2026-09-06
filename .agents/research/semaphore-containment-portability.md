# Research: Portability and correctness of flock-based semaphores and per-command resource containment

<!--
Technology-landscape research, hex research template. Owner: researcher
worker (ecosystem lane), 2026-09-05.
Handoff to: /hex-architect (portable runtime-contracts ADR: heavy-command
semaphore primitive, containment ladder detection), /hex-plan.
Findings decay — check Expires before trusting them.
-->

## Metadata

**Date:** 2026-09-05
**Domain:** devops | cli | testing
**Triggered by:** hex is writing a portable, shell-executed contract that
caps concurrent heavy commands (build/test/verify) at N slots across
parallel agent worktrees on one developer machine, and optionally contains
each heavy command's memory. Must work on Linux, WSL2, macOS, and inside
whatever sandbox the agent harness imposes, and must degrade loudly rather
than silently no-op. Builds on
[`.agents/research/parallel-resource-pitfalls.md`](parallel-resource-pitfalls.md)
(Containment ladder, Preflight) — this document is the depth pass behind
those two sections.
**Expires:** 2027-03-05

## Direct Answer

**Part A (semaphore).** `flock`'s crash-safety property is real and
citable: locks attach to the *open file description*, not the process, and
the kernel releases them when every fd referencing that description closes
— including on SIGKILL, because the kernel closes all of a killed
process's fds as part of exit ([flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html)).
That is the one property `mkdir`-lock schemes cannot get for free. The
correctness hazard that survives is fd inheritance: a **child process**
that inherits the locked fd (backgrounded, daemonized, or `exec`'d without
`close-on-exec`) keeps the lock held after the parent that acquired it
exits — a documented, real footgun, not a hypothetical
([utoronto FlockUsageNotes](https://utcc.utoronto.ca/~cks/space/blog/linux/FlockUsageNotes) —
blocks AI fetches but is independently corroborated by
[flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html)'s own fd-duplication
language and by the Stack/community threads on the topic). `flock(1)` is
Linux-only (util-linux); **it does not exist on stock macOS**, whose closest
native primitive is `shlock(1)` (weaker) or `mkdir` (POSIX-atomic, but not
crash-safe) — the portable contract must name a fallback ladder, not assume
`flock` everywhere.

**Part B (containment).** Every optional containment layer — `systemd-run
--user --scope`, cgroup v2 delegation, GNU `time -v`, GNU `timeout` — is
Linux-only or Linux-first and absent or degraded on macOS and inside many
sandboxes/containers. The contract must (a) detect each layer with one
cheap, scriptable command, (b) fall back down a named ladder when absent,
and (c) never treat absence as "skip the whole containment idea" — the
wall-clock backstop (`timeout`/`perl alarm`) is the one layer with no
excuse to be missing anywhere, because Perl (with `alarm`) ships on every
Linux, WSL2, and macOS base install.

## Part A — flock counting semaphore

### A1. The canonical N-slot idiom

```sh
# Try slots 1..N, take the first free one, fail fast if all are busy.
N=4
slot=""
for i in $(seq 1 "$N"); do
  exec {fd}>"/path/to/locks/heavy.$i.lock"
  if flock -n "$fd"; then
    slot=$i
    break
  fi
  eval "exec $fd>&-"          # close this fd before trying the next
done
if [ -z "$slot" ]; then
  echo "no free heavy slot, waiting on slot 1 with a timeout" >&2
  exec {fd}>"/path/to/locks/heavy.1.lock"
  flock -w 60 "$fd" || { echo "timed out waiting for a heavy slot" >&2; exit 1; }
  slot=1
fi
# ... run the heavy command here, still holding $fd ...
eval "exec $fd>&-"             # release explicitly (also released on exit/kill)
```

Or the more common **subshell form**, one lock file, one command:

```sh
( flock -n 9 || exit 1
  cargo test
) 9>/path/to/locks/heavy.3.lock
```

- `9>` opens fd 9 on the lock file for writing (creating it if absent — the
  file's *content* is irrelevant, it is a pure mutex token); `flock -n 9`
  tries a non-blocking exclusive lock on that fd and fails immediately
  (exit 1) if another process holds it instead of waiting.
  [flock(1)](https://man7.org/linux/man-pages/man1/flock.1.html).
- `flock -n` = **fail fast**, for a slot-scan loop where blocking on slot 1
  while slot 2 is free would waste time. `flock -w SECONDS` = **block up to
  a timeout**, for the "no free slot, queue for a bounded wait" fallback —
  use it once you've already scanned all N slots and want to wait rather
  than error, so a caller gets a bounded queue instead of an infinite hang.
  A bare `flock` (no `-n`/`-w`) blocks forever — never use that in an
  orchestrator that must stay responsive.
  [flock(1)](https://man7.org/linux/man-pages/man1/flock.1.html).
- **No thundering herd**: scanning slots 1..N with `-n` is non-blocking at
  every step, so N racing processes each grab a distinct free slot in one
  pass with no wake-storm; only the "all slots busy" fallback blocks, and
  only one waiter queues on one designated slot (slot 1) rather than all
  waiters piling onto all N locks.

### A2. Correctness hazards

- **SIGKILL**: released. Locks are associated with the *open file
  description*; the lock is released "either by an explicit LOCK_UN … or
  when all … file descriptors [referring to that open file description]
  have been closed" — and a SIGKILLed process has all its fds closed by
  the kernel as part of process teardown, unconditionally, before the
  parent can react. [flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html).
  This is the citable robustness property that makes `flock` the right
  primitive for an agent-orchestration contract where a heavy command
  (or the orchestrator itself) may be killed mid-run.
- **Stale lock *file***: harmless by design. The file is a bare mutex
  token; a `flock` lock is never "stuck" by the file persisting on disk
  after a crash — a new `flock -n` call on that same file immediately
  succeeds once no live fd references it, because the *file* is not what's
  locked, the *open file description* is.
  [flock(1)](https://man7.org/linux/man-pages/man1/flock.1.html) — this is
  precisely what makes `flock` superior to a stale-PID-file scheme.
- **fd inheritance — the real hazard**: if the process holding the lock
  backgrounds, forks, or execs a child that inherits the fd (no
  `close-on-exec`, or an explicit `9>&-` never issued), that child keeps
  the *open file description* alive, and therefore keeps the lock held,
  even after the original locking process exits. `flock(2)` states this
  directly: duplicate fds from `fork(2)`/`dup(2)` "refer to the same lock,"
  released only when *all* of them close.
  [flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html). Practical
  corroboration: community write-ups of `flock(1)` usage bugs describe
  exactly this — a daemon that doesn't close inherited fds holds the lock
  forever even though the shell script that spawned it has exited. For a
  contract that spawns build/test tooling (which may itself fork background
  workers — Gradle daemons, `cargo`'s jobserver children, browser
  processes under Playwright), the mitigation is: acquire the lock in the
  same shell invocation that runs the heavy command directly (the `(
  flock -n 9; cmd ) 9>lockfile` form), never in a wrapper that then
  backgrounds the real command, and prefer commands that don't
  self-daemonize.
- **Worktree vs shared repo-root lock directory**: `flock` locks by *file
  description*, keyed to whatever inode the fd was opened against — there
  is nothing about a git worktree that changes this. But git worktrees
  each have **their own working tree while sharing one `.git`
  object store** (they are not independent filesystems), so a lock file
  placed inside a per-worktree path (`.agents/worktrees/<wp>/.lock`) is
  *not visible* to a sibling worktree and therefore cannot coordinate a
  cross-worktree semaphore at all. **The lock files must live at a path
  shared by every worktree** — e.g. the main repo root or a fixed
  `~/.cache/hex/<repo>/locks/` — never under a worktree's own directory,
  or the semaphore silently becomes N independent no-op locks, one per
  worktree, which is worse than not having a semaphore because it looks
  correct.

### A3. Filesystem support

| Filesystem | `flock()` support | Note |
|---|---|---|
| ext4 (native Linux, incl. WSL2's ext4 VHDX) | Full, kernel-native | Standard case; no caveats. |
| WSL2 `/mnt/c` (drvfs over 9P) | **Unreliable** — file-locking support on the drvfs/9P path is a documented gap; SVN and other lock-dependent tools report "filesystem does not support file locking" against `\\wsl$`/`/mnt/c` paths. [microsoft/WSL#4689](https://github.com/microsoft/WSL/issues/4689) | **Do not place lock files under `/mnt/c/...` from WSL2.** Keep locks inside the Linux filesystem (`~` or repo checked out under `/home/...`), not the Windows-mounted drive. |
| macOS APFS | Full — `flock(2)` is a native BSD syscall on Darwin; the gap is the **`flock(1)` command-line tool**, not the syscall (see A4). | |
| NFS (Linux client) | Supported since Linux 2.6.12 (emulated as whole-file `fcntl` byte-range locks); a `local_lock` compatibility mode to force local-only semantics landed in 2.6.37. Before 2.6.12, `flock()` did not lock across NFS at all — it was local-only. [flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html), `nfs(5)`. | Modern kernels are fine; only relevant if the repo lives on an NFS mount, which is not the primary target here (single developer machine). |

Net: the only real-world hazard for hex's target platforms is **WSL2's
drvfs mount** — a contract that says "put the lock file next to the repo"
must also say "and the repo must be on the Linux side, not `/mnt/c`,"
which is already the standard WSL2 performance advice for unrelated
reasons (drvfs is also ~10-20x slower for file I/O).

### A4. macOS: flock(1) is not native — the crux trade-off

`flock(1)` is a util-linux program; **macOS's BSD userland does not ship
it**. The closest native tool is `shlock(1)`, which MacPorts' own tracker
calls less secure and less robust than `flock`
([MacPorts #23733](https://trac.macports.org/ticket/23733)). Options, in
order of portability for a *shipped* contract that cannot assume `brew
install`:

1. **`mkdir` as the lock primitive.** `mkdir` is POSIX-atomic on every
   filesystem in scope (ext4, APFS, drvfs) with zero dependencies — no
   external binary, works in any POSIX shell. This is the standard
   portable substitute for `flock` in shell scripts that must run on both
   Linux and macOS.
   [tobru: Easy bash script locking with mkdir](https://www.tobru.ch/easy-bash-script-locking-with-mkdir/),
   [BashFAQ/045](https://mywiki.wooledge.org/BashFAQ/045).
2. **`python3 -c '...fcntl.flock...'`** — Python 3 with `fcntl.flock` ships
   on stock macOS and virtually every Linux distro used for development;
   this gets real kernel `flock(2)` semantics (crash-safe, no stale-file
   problem) with no extra install, at the cost of a slower process spawn
   and a slightly uglier one-liner than the shell idiom.
3. **Homebrew `flock`** (`brew install util-linux` or the standalone
   [discoteq/flock](https://github.com/discoteq/flock) which explicitly
   supports Darwin) — real `flock(1)`, but an extra install step a shipped
   *prose* contract cannot force on the user's machine; usable only as an
   optional fast path when detected present.
4. **`shlock(1)`** — native on macOS, but weaker guarantees than `flock`
   per MacPorts' own assessment; not recommended as the primary mechanism.

**The crux trade-off, stated explicitly**: `flock` (syscall or via
`python3 -c fcntl.flock`) is released automatically on process death
(SIGKILL included) with **zero stale-lock possibility**, because the lock
lives in kernel state tied to the fd, not in anything visible on disk. A
`mkdir`-based lock is **not** released on process death — `mkdir` creates
a directory that persists until something explicitly `rmdir`s it, so a
SIGKILLed holder (or a killed agent session, or an OOM-killed heavy
command) leaves the "lock" directory standing forever, wedging that slot
for every future run until a human or a stale-detection pass clears it.
Community write-ups of the mkdir pattern converge on the same conclusion:
you must pair `mkdir` with a PID file inside the lock directory and a
`kill -0 $PID` staleness check (dead PID → safe to `rmdir` and retry), and
even that has a PID-reuse race that `flock` structurally cannot have.
[adrian.idv.hk: Mutex lock in bash](https://www.adrian.idv.hk/2022-12-09-bashlock/),
[BashFAQ/045](https://mywiki.wooledge.org/BashFAQ/045).

**Recommendation for the contract**: name `flock` (native, or via
`python3 -c` when the binary is absent) as the primary mechanism *because*
crash-safety is the one property this exact use case cannot compromise on
— a heavy command that gets OOM-killed or a worktree that gets torn down
mid-build must never wedge a semaphore slot for the rest of the session.
`mkdir` is the fallback **only** when neither `flock(1)` nor a `python3`/
`perl` interpreter is reachable at all (a bare-bones container), and even
then the contract must mandate the PID-file-plus-`kill -0` staleness check
as a non-optional companion, plus a documented manual unwedge command
(`rm -rf` the slot dir), because an agent contract that can silently wedge
itself with no recovery path is worse than one with no semaphore.

### A5. Alternatives

- **GNU `parallel --semaphore` / `sem`**: a purpose-built counting
  semaphore (`sem --jobs N --id my_id 'cmd'`) — "like having multiple
  toilets," `-j N` sets concurrent slots, an `--id` names the semaphore
  ([GNU sem docs](https://www.gnu.org/software/parallel/sem.html)). It is
  strictly higher-level than raw `flock` (handles the slot-scan loop
  internally) but adds a dependency (`moreutils`/`parallel` package) that
  is not guaranteed present the way `flock`+coreutils are on Linux, and is
  not installed on macOS by default either — same portability tier as
  Homebrew `flock`, not better.
- **`xargs -P`**: solves "run N things in parallel from a list," not "cap
  concurrency across independent, separately-invoked processes" — wrong
  shape for hex's problem (heavy commands are triggered by independent
  agent sessions at unpredictable times, not enumerated up front).
- **systemd slice-based limits (`--property=`)**: caps *resource usage*
  (CPU/memory) of a slice, not *concurrency count* — orthogonal to the
  semaphore question, relevant instead to Part B.
- **Orchestrator self-gates, no lock at all**: correct and sufficient
  *if and only if* there is exactly one orchestrator process per host
  holding the count in memory. **What breaks**: the moment a second,
  independent agent session (a second Claude Code window, a second
  terminal running `/hex-execute` on a different repo, or the same repo
  from two clones) starts on the same machine, its in-memory counter knows
  nothing about the first session's outstanding heavy commands — both
  think they have the full N slots free and jointly oversubscribe to 2N.
  This is the exact failure mode a cross-process, filesystem-backed
  semaphore (`flock`) exists to prevent, and it is not a theoretical edge
  case for hex's target user (one developer routinely runs several parallel
  Claude Code sessions across different repos/worktrees on one machine —
  the scenario this contract is written for).

## Part B — containment portability

### B1. `systemd-run --user --scope -p MemoryMax=` availability

| Environment | Availability | Notes |
|---|---|---|
| Stock Linux desktop (systemd distro: Ubuntu, Fedora, Arch, …) | Available | `systemd-run --user --scope -p MemoryMax=8G -p MemoryHigh=7G <cmd>` is the documented pattern for ad hoc memory-capped runs. [utcc: Using systemd-run to limit something's memory usage](https://utcc.utoronto.ca/~cks/space/blog/linux/SystemdForMemoryLimitingII), [blog.fraggod.net](https://blog.fraggod.net/2019/10/02/cgroup-v2-resource-limits-for-apps-with-systemd-scopes-and-slices.html). |
| WSL2 | Available **only** with `/etc/wsl.conf` `[boot]\nsystemd=true` set, requiring a WSL/Windows build that supports it (Microsoft Store WSL ≥ 0.67.6; announced generally available in WSL as of the 2022 systemd rollout) and a `wsl --shutdown` + relaunch to take effect. [Microsoft devblog: Systemd support is now available in WSL](https://devblogs.microsoft.com/commandline/systemd-support-is-now-available-in-wsl/), [gist: WSL2 enabling systemd](https://gist.github.com/djfdyuruiry/6720faa3f9fc59bfdf6284ee1f41f950). Without that flag (the WSL2 default), there is no PID 1 systemd and no user bus. |
| Docker containers | Generally **absent** — containers run a single process as PID 1, not systemd, so there is no user session bus for `systemd-run --user` to talk to; the classic error is "System has not been booted with systemd as init system (PID 1). Can't operate." [Docker forums thread](https://forums.docker.com/t/docker-installation-system-has-not-been-booted-with-systemd-as-init-system-pid-1-cant-operate/120332). Making systemd PID 1 work inside a container is possible but requires a purpose-built base image and privileged/cgroup-mount flags most agent-harness containers do not grant. |
| macOS | **None** — systemd does not exist on Darwin. Not applicable at any layer. |

**Detection command for the contract**: two cheap, composable checks —

```sh
command -v systemd-run >/dev/null 2>&1 && [ -d /run/systemd/system ] && \
  systemctl --user show-environment >/dev/null 2>&1
```

- `[ -d /run/systemd/system ]` is the portable shell equivalent of
  `sd_booted(3)`: "checks whether the system was booted up using the
  systemd init system … A simple check like this can also be implemented
  trivially in shell" by testing for that directory.
  [sd_booted(3)](https://man7.org/linux/man-pages/man3/sd_booted.3.html).
  This one test is what tells the contract "no PID 1 systemd here" —
  covering the Docker/devcontainer and non-systemd-Linux cases in one
  line, no error output to parse.
- `command -v systemd-run` is the binary-presence check (cheap, no
  process spawn beyond the shell builtin).
- `systemctl --user show-environment` (or `systemctl --user is-active
  default.target`) is the final probe that a **user session bus** is
  actually reachable — this is what fails on WSL2 without `systemd=true`
  even when `/run/systemd/system` exists at the *system* level but no user
  manager was started, and what surfaces the "Failed to connect to bus"
  class of error a bare `command -v` check would miss.

When any leg fails, the contract's instruction is: **skip to the next
containment ladder rung, do not retry, do not error the whole command** —
absence of `systemd-run` is expected and common (macOS, most containers),
not a bug to work around.

### B2. cgroup v2 delegation for a non-root user

- `systemd-run --user --scope` gives you a cgroup **for free**, no root
  action needed beyond what modern systemd already delegates: since
  systemd ~245+, the `user@.service` template unit delegates the
  `memory` and `pids` controllers to each logged-in user's slice by
  default, which is exactly what `-p MemoryMax=`/`-p MemoryHigh=` need.
  Delegating *additional* controllers (cpu, cpuset, io) needs an admin
  drop-in (`/etc/systemd/system/user@.service.d/delegate.conf` with
  `Delegate=cpu cpuset io memory pids`) — root-only, one-time, host
  config, not something a per-run agent contract can or should do.
- `Delegate=yes` on a scope/service means "hand a real, writable subtree
  of the cgroup hierarchy to this unit and its children," letting
  applications (including nested container runtimes) manage their own
  sub-cgroups under it — the mechanism that makes rootless Docker/Podman
  and rootless systemd-nspawn work at all.
- **Raw `/sys/fs/cgroup` writes without `systemd-run`**: possible only if
  the calling user already owns a writable cgroup subtree (e.g. the
  session already sits inside a delegated user slice) — `mkdir
  /sys/fs/cgroup/user.slice/user-$UID.slice/.../hex-<id>`, write
  `memory.max`, then move the target PID into `cgroup.procs`. This is
  strictly more fragile than `systemd-run` (manual cleanup, no automatic
  scope teardown, easy to get hierarchy paths wrong across distros) and
  should be the fallback only when `systemd-run` itself is unavailable but
  a writable cgroup subtree still is (uncommon in practice — most hosts
  without `systemd-run` also lack a delegated subtree).
- **`cgcreate`/libcgroup: do not use.** libcgroup predates the cgroup v2
  unified hierarchy and its multi-hierarchy model doesn't map cleanly onto
  v2's single tree; RHEL's own migration guidance marks libcgroup
  deprecated for removal in the v2 era.
  [Red Hat: Migrating from CGroups V1 to V2](https://access.redhat.com/articles/3735611).
  This corroborates the existing pitfalls doc's ladder, which already
  excludes `cgcreate` — no change to that guidance, cited here for the
  ADR record.
- **Does `memory.max` on a delegated user cgroup work without root?**
  Yes — that's the entire point of delegation: once a subtree is
  delegated (`Delegate=yes`, or the default memory/pids delegation on
  `user@.service`), the owning user can write `memory.max` inside it and
  the kernel enforces the limit like any other cgroup, no root or
  `CAP_SYS_ADMIN` needed for writes confined to that subtree.

### B3. Sandbox interference

Concrete, current reports on the exact harness this contract targets:

- **Claude Code's own sandboxed Bash tool** uses **Seatbelt**
  (`sandbox-exec`) on macOS and **bubblewrap + seccomp** on Linux/WSL2; per
  its own docs the sandbox provides filesystem and network isolation only
  — it is explicitly a namespace/syscall boundary, not a resource-cap
  layer. [Claude Code docs: Configure the sandboxed Bash tool](https://code.claude.com/docs/en/sandboxing).
  Independent write-ups of the same mechanism are explicit that this is by
  design: "the sandbox layer has no rlimit/cgroup/timeout by design as
  these are expected at a higher level" — i.e. `systemd-run`/`ulimit`/
  `timeout` layered *around* a sandboxed command are expected to keep
  working, because the sandbox does not itself impose or block them.
  [Medium: How Claude Code and Codex Sandbox Untrusted Code](https://medium.com/@Koukyosyumei/how-claude-code-and-codex-sandbox-untrusted-code-ba39b493046a).
- **bubblewrap itself sets no CPU/memory/PID limits** — it is a namespace
  tool, not a cgroup tool; its own project guidance is to pair it with
  systemd-run/cgroups for resource limits, which is exactly the layering
  hex's ladder already proposes.
  [containers/bubblewrap issues discussion](https://github.com/containers/bubblewrap/issues/505).
  A concrete platform bug worth flagging: bubblewrap installed via
  Homebrew on Apple Silicon can get picked up on `$PATH` and cause Claude
  Code to mistakenly select the Linux sandbox code path on macOS, which
  then fails because `bwrap` doesn't run on Darwin at all.
  [anthropics/claude-code#32275](https://github.com/anthropics/claude-code/issues/32275).
  Not a containment-ladder issue directly, but a reason the contract
  should not assume "bubblewrap present" implies "on Linux."
- **Nested sandboxes (bwrap-in-Docker)**: bubblewrap can fail inside an
  already-namespaced/unprivileged Docker container ("No permissions to
  create new namespace") when the outer container doesn't allow nested
  user namespaces — relevant only if hex's own contract is ever run one
  layer further nested than "agent harness sandbox on bare host," worth a
  one-line caveat, not a blocking concern for the primary target.
- **Devcontainers**: inherit the Docker case in B1 — no systemd PID 1
  unless purpose-built, so `systemd-run` is absent there by the same
  detection check; `ulimit` and `timeout` remain unaffected since they are
  shell/process primitives, not sandbox-mediated.

Net for B3: no evidence that Claude Code's sandbox (or bubblewrap
generally) *blocks* `systemd-run`, cgroup writes, `ulimit`, or `timeout`
when they are otherwise available on the host — it simply doesn't provide
them itself, which is exactly why the containment ladder in the existing
pitfalls doc layers them on top rather than relying on the sandbox.

### B4. `/usr/bin/time -v` portability

- **GNU time** (`/usr/bin/time` on most Linux distros, when the actual GNU
  coreutils binary is installed rather than the shell builtin) supports
  `-v`/`--verbose`, which includes "Maximum resident set size (kbytes)" —
  the peak-RSS figure hex's resource-profile measurement wants.
- **macOS's `/usr/bin/time` is the BSD variant** and has **no `-v` flag at
  all**; its extended-stats flag is `-l`, which prints (among other
  fields) `maximum resident set size` — same *data*, different flag and
  different units convention (BSD reports bytes on Darwin; GNU reports
  kilobytes, and has its own well-known quirk of over-reporting by 4x on
  some architectures if a build miscompiles the page-to-kB conversion —
  worth a footnote if the contract ever compares absolute numbers across
  platforms, though for hex's use — deriving a per-host concurrency budget
  from a same-host baseline — that's a non-issue since the ratio is only
  ever compared within one platform).
- **`gtime`**: Homebrew's `coreutils` package installs GNU time as
  `gtime` (prefixed to avoid clobbering the BSD `time`), giving true `-v`
  output on macOS at the cost of a Homebrew dependency the shipped prose
  contract cannot force.
- **Shell builtin `time`** (bash/zsh `time cmd`) reports wall/user/sys CPU
  only, on every platform — **no RSS field at all** — useless for this
  measurement regardless of OS.

**Recommendation — one-liner with a documented fallback:**

```sh
if command -v /usr/bin/time >/dev/null && /usr/bin/time -v true >/dev/null 2>&1; then
  /usr/bin/time -v <heavy-cmd> 2>&1 | grep -i 'maximum resident'   # GNU: kbytes
elif /usr/bin/time -l true >/dev/null 2>&1; then
  /usr/bin/time -l <heavy-cmd> 2>&1 | grep -i 'maximum resident'   # BSD/macOS: bytes
else
  command -v gtime >/dev/null && gtime -v <heavy-cmd> 2>&1 | grep -i 'maximum resident'
fi
```

Probe with `-v true` / `-l true` first (cheap, no side effects) rather than
assuming by `uname` — the same detect-don't-assume principle as the
`systemd-run` check, and it also covers the case of a Linux box where only
the BSD-flavored `time` happens to be on `$PATH` inside a minimal
container image.

### B5. `timeout(1)` portability

- **GNU coreutils `timeout`** (Linux, WSL2): `timeout --kill-after=10s
  <wall> <cmd>` sends the default `TERM` at `<wall>`, then escalates to
  `KILL` if the process hasn't exited `10s` later — exactly the two-stage
  backstop hex's ladder already specifies. Exit-status conventions: `124`
  when the command timed out (unless `--preserve-status`), `137` when the
  final signal was `KILL` (128+9), `125` if `timeout` itself fails, `126`
  if the command couldn't be invoked. Duration takes `s`/`m`/`h`/`d`
  suffixes, seconds by default, `0` disables the timeout.
  [timeout(1)](https://man7.org/linux/man-pages/man1/timeout.1.html).
- **macOS**: `timeout` is **absent by default** — BSD userland has no
  equivalent; it's available only as `gtimeout` from Homebrew's
  `coreutils` (same naming convention as `gtime`), which the contract
  cannot assume is installed.
- **Portable wall-clock backstop with no dependency**: `perl -e 'alarm
  shift; exec @ARGV' <seconds> <cmd> [args...]` — Perl with `alarm` ships
  on the base install of every target platform (Linux, WSL2, and macOS
  all bundle a system Perl), needs no package manager, and the `exec`
  replaces the Perl process with the target command so signal delivery and
  exit-status semantics stay close to the native case (the `alarm` fires
  SIGALRM into the still-Perl-labeled process if `exec` hasn't happened
  yet, or into the exec'd command's process after — because `exec`
  preserves the PID and pending signal timers). This is the same pattern
  independently recommended in tooling write-ups facing the identical
  macOS gap.

**Recommendation — one-liner with fallback:**

```sh
if command -v timeout >/dev/null 2>&1; then
  timeout --kill-after=10s "$WALL" <heavy-cmd>
elif command -v gtimeout >/dev/null 2>&1; then
  gtimeout --kill-after=10s "$WALL" <heavy-cmd>
else
  perl -e 'alarm shift; exec @ARGV' "$WALL" <heavy-cmd>
fi
```

Note the Perl fallback loses `--kill-after`'s two-stage TERM-then-KILL
escalation (it delivers one SIGALRM, default action terminates the
process); acceptable for hex's purpose since the wall-clock backstop's job
is "guarantee the slot is eventually freed," not "guarantee graceful
shutdown" — a contract note should say so rather than silently claim
parity.

## Key findings

1. `flock` locks are tied to the open file description and released when
   every fd referencing it closes, including on SIGKILL — the citable
   crash-safety property. [flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html).
2. A child process that inherits the locked fd (fork/exec without
   close-on-exec, or a self-daemonizing tool) keeps the lock alive after
   the acquiring parent exits — a real, documented hazard, not a corner
   case, and the reason to acquire-and-run in one subshell rather than a
   detach-then-run wrapper. [flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html).
3. `flock(1)` is util-linux, absent from stock macOS; `shlock`, `mkdir`,
   `python3 -c fcntl.flock`, and Homebrew `flock` are the alternatives, and
   `mkdir` trades away crash-safety for zero-dependency portability.
   [MacPorts #23733](https://trac.macports.org/ticket/23733),
   [BashFAQ/045](https://mywiki.wooledge.org/BashFAQ/045).
4. WSL2's drvfs/`9P` mount (`/mnt/c`) is an unreliable place for lock
   files — file locking on that path is a documented gap; lock files must
   live on the Linux-native side of the WSL2 filesystem.
   [microsoft/WSL#4689](https://github.com/microsoft/WSL/issues/4689).
5. `systemd-run --user` needs a live user-session bus, which needs PID 1
   systemd; that's absent by default on WSL2 (needs `wsl.conf`
   `systemd=true`) and absent in almost all Docker/devcontainer images.
   [Microsoft devblog](https://devblogs.microsoft.com/commandline/systemd-support-is-now-available-in-wsl/),
   [Docker forums](https://forums.docker.com/t/docker-installation-system-has-not-been-booted-with-systemd-as-init-system-pid-1-cant-operate/120332).
6. `[ -d /run/systemd/system ]` is the documented, man-page-blessed shell
   equivalent of `sd_booted(3)` — the cheapest correct "is systemd even
   the init system here" probe. [sd_booted(3)](https://man7.org/linux/man-pages/man3/sd_booted.3.html).
7. Modern systemd delegates the `memory` and `pids` cgroup v2 controllers
   to each user's slice by default, which is exactly what
   `systemd-run --user --scope -p MemoryMax=` needs with no root action;
   `cgcreate`/libcgroup is the deprecated v1-era tool and should not be
   used. [Red Hat cgroups v1→v2 migration](https://access.redhat.com/articles/3735611).
8. Claude Code's sandbox (Seatbelt on macOS, bubblewrap+seccomp on
   Linux/WSL2) is documented and independently reported to impose no
   rlimit/cgroup/timeout containment itself — those are expected to layer
   on top, which is exactly hex's existing ladder shape.
   [Claude Code docs](https://code.claude.com/docs/en/sandboxing),
   [Medium writeup](https://medium.com/@Koukyosyumei/how-claude-code-and-codex-sandbox-untrusted-code-ba39b493046a).
9. macOS `/usr/bin/time` has no `-v`; its peak-RSS flag is `-l`. GNU `time
   -v`'s "Maximum resident set size" is available on macOS only via
   Homebrew's `gtime`. Neither bash's nor zsh's builtin `time` reports RSS
   at all.
10. GNU `timeout --kill-after` gives a two-stage TERM-then-KILL wall-clock
    backstop with documented exit codes (124/125/126/137); macOS has no
    `timeout` by default, and the zero-dependency portable substitute is
    `perl -e 'alarm shift; exec @ARGV'`, which ships on every target
    platform's base install. [timeout(1)](https://man7.org/linux/man-pages/man1/timeout.1.html).

## Sources

| Source | Type | Covers |
|---|---|---|
| [flock(2) — man7](https://man7.org/linux/man-pages/man2/flock.2.html) | Man page | Open-file-description locking, fork/dup fd duplication, NFS support history (2.6.12, 2.6.37 `local_lock`) |
| [flock(1) — man7](https://man7.org/linux/man-pages/man1/flock.1.html) | Man page | `-n`, `-w`, subshell/fd idiom, exit-status via `-E` |
| [timeout(1) — man7](https://man7.org/linux/man-pages/man1/timeout.1.html) | Man page | `--kill-after`, default TERM signal, exit codes 124/125/126/137, duration suffixes |
| [sd_booted(3) — man7](https://man7.org/linux/man-pages/man3/sd_booted.3.html) | Man page | `/run/systemd/system` as the portable shell check for "is systemd PID 1" |
| [GNU coreutils timeout manual](https://www.gnu.org/software/coreutils/manual/html_node/timeout-invocation.html) | Docs | (attempted fetch rate-limited; corroborated via man7 instead) |
| [GNU Parallel `sem` docs](https://www.gnu.org/software/parallel/sem.html) | Docs | Counting-semaphore semantics, `-j N`, `--id` |
| [MacPorts ticket #23733](https://trac.macports.org/ticket/23733) | Issue tracker | `flock(1)` absence on macOS, `shlock` weakness, MacPorts/source alternatives |
| [discoteq/flock](https://github.com/discoteq/flock) | Repo | Portable C reimplementation of `flock(1)` for Darwin and others |
| [tobru: Easy bash script locking with mkdir](https://www.tobru.ch/easy-bash-script-locking-with-mkdir/) | Blog | `mkdir` atomicity, stale-lock handling |
| [BashFAQ/045 — Greg's Wiki](https://mywiki.wooledge.org/BashFAQ/045) | Wiki | `mkdir`/`flock` locking patterns, crash-safety comparison |
| [adrian.idv.hk: Mutex lock in bash shell](https://www.adrian.idv.hk/2022-12-09-bashlock/) | Blog | PID-file + `kill -0` staleness check for `mkdir` locks |
| [microsoft/WSL#4689](https://github.com/microsoft/WSL/issues/4689) | Issue tracker | drvfs/9P (`/mnt/c`, `\\wsl$`) file-locking gap |
| [Microsoft devblog: Systemd support in WSL](https://devblogs.microsoft.com/commandline/systemd-support-is-now-available-in-wsl/) | Docs/blog | WSL2 `systemd=true` requirement and version gating |
| [gist: WSL2 enabling systemd](https://gist.github.com/djfdyuruiry/6720faa3f9fc59bfdf6284ee1f41f950) | Gist | `wsl.conf` `[boot] systemd=true` steps |
| [Docker forums: "System has not been booted with systemd"](https://forums.docker.com/t/docker-installation-system-has-not-been-booted-with-systemd-as-init-system-pid-1-cant-operate/120332) | Forum | Docker containers lacking PID 1 systemd, `systemd-run` failure mode |
| [utcc: Using systemd-run to limit something's memory usage](https://utcc.utoronto.ca/~cks/space/blog/linux/SystemdForMemoryLimitingII) | Blog | `systemd-run --user --scope -p MemoryMax=/MemoryHigh=` worked example |
| [blog.fraggod.net: cgroup-v2 resource limits with systemd scopes](https://blog.fraggod.net/2019/10/02/cgroup-v2-resource-limits-for-apps-with-systemd-scopes-and-slices.html) | Blog | Delegate= drop-in for additional controllers |
| [Red Hat: Migrating from CGroups V1 to V2](https://access.redhat.com/articles/3735611) | Vendor docs | libcgroup/`cgcreate` deprecation under cgroup v2 |
| [Claude Code docs: Configure the sandboxed Bash tool](https://code.claude.com/docs/en/sandboxing) | Official docs | Seatbelt (macOS) / bubblewrap+seccomp (Linux/WSL2), scope of isolation (fs/network, not resource caps) |
| [Medium: How Claude Code and Codex Sandbox Untrusted Code](https://medium.com/@Koukyosyumei/how-claude-code-and-codex-sandbox-untrusted-code-ba39b493046a) | Third-party analysis | "no rlimit/cgroup/timeout by design" characterization of the sandbox layer |
| [anthropics/claude-code#32275](https://github.com/anthropics/claude-code/issues/32275) | Issue tracker | Homebrew bubblewrap on macOS mis-selecting the Linux sandbox path |
| [containers/bubblewrap#505](https://github.com/containers/bubblewrap/issues/505) | Issue tracker | bwrap sets no CPU/memory/PID limits; nested-namespace failure inside unprivileged Docker |
| [allenap.me: flock(2) behaviour on macOS and Linux](https://allenap.me/posts/flock-behaviour) | Blog | Lock-conversion non-atomicity parity between Darwin and Linux `flock(2)` |

## Recommendation

**Locking primitive — name `flock` as the primary mechanism, `python3 -c
'...fcntl.flock...'` as the same-guarantee fallback when the `flock(1)`
binary is absent (stock macOS), and `mkdir` + mandatory PID-file staleness
check as the last-resort fallback only when no `flock`-capable runtime
(binary or Python) is reachable at all.** Rationale: crash-safety —
"a heavy command that gets OOM-killed never wedges a slot" — is the one
property this exact use case cannot trade away, and only kernel-level
`flock()` semantics give it for free; `mkdir` demotes crash-safety to a
manual/PID-check recovery path, so it should never be the first choice on
a platform where a real `flock` is reachable.

**Slot files live at a path shared by every worktree** (repo root or
`~/.cache/hex/<repo>/locks/`, never inside `.agents/worktrees/<wp>/`), and
**never under a WSL2 `/mnt/c` (drvfs) path** — both are correctness bugs
that look like a working semaphore until two worktrees race.

**Containment ladder detection commands, exactly as the contract should
name them:**

| Layer | Detect with | If absent |
|---|---|---|
| `systemd-run --user` | `command -v systemd-run >/dev/null 2>&1 && [ -d /run/systemd/system ] && systemctl --user show-environment >/dev/null 2>&1` | Drop to raw cgroup v2 writes if a delegated subtree is already writable, else `nice`/`ionice`, else `ulimit -v` (scripting-language workers only) |
| Delegated cgroup v2 subtree | `test -w "/sys/fs/cgroup/$(cat /proc/self/cgroup | sed 's|^0::||')"` (writable check on the process's own cgroup path) | Drop to `nice -n 19 ionice -c3` |
| GNU `time -v` peak RSS | `/usr/bin/time -v true >/dev/null 2>&1` | Try `/usr/bin/time -l true` (macOS/BSD); else `gtime -v`; else skip RSS measurement, do not fabricate a number |
| GNU `timeout --kill-after` | `command -v timeout >/dev/null 2>&1` | Try `gtimeout`; else `perl -e 'alarm shift; exec @ARGV'` — never skip the wall-clock backstop, it is the one rung with zero excuse to be absent |

**What the contract must say on absence, at every rung**: degrade to the
next rung down and **announce it once** (matching hex's existing
`Degraded:` convention for subagent/model capability gaps) — never
silently no-op a containment layer, and never treat an optional layer's
absence as a reason to skip the mandatory wall-clock backstop, which is
the only rung with no acceptable "not available" outcome anywhere in
scope (Linux, WSL2, macOS, or inside any sandbox surveyed).
