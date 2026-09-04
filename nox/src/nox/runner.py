"""Process creation and supervision (C-1009, C-1015, C-1024, E6, E7).

The seam wraps process *creation only*. `Runner.spawn` returns a `Process`;
everything that decides an outcome — deadline, silence window, byte cap,
SIGTERM→grace→SIGKILL — is `supervise()`, a pure function over the `Process`
protocol with its clock and its kill primitive injected. That split is why the
single `subprocess.Popen(...)` call is the only no-cover pragma in the codebase
(C-1015): the escalation logic the seam exists to cover is on the covered side
of it.

Reading the merged pipe happens in a dedicated drain thread (`_drain`), never
in `supervise` — `selectors` does not support pipes on Windows and a
synchronous `readline` in the supervisor would make the silence timeout
unenforceable, because the supervisor would be blocked inside the very read it
is supposed to be timing (E7, D-k). `Process.lines` therefore returns a
materialized batch rather than a lazy iterator: "never blocks on a read" is
then a property of the type, not a promise in a docstring.

E7's "bounded queue" is bounded by the **two ceilings the drain thread enforces
before every enqueue**, not by a `maxsize`. `BYTE_CAP` bounds the bytes: the
chunk that would cross it is dropped rather than enqueued, so total enqueued
bytes never exceed `BYTE_CAP`. `MAX_LINES` bounds the Python objects those bytes
become, which the byte cap alone does not — 8 MiB of two-byte lines is 4.19 M
`str` objects and hundreds of MiB of RSS, which under a CI memory cgroup is an
OOM-kill of nox and a review that never runs.

A real `maxsize` would block the drain
thread on `put` the moment `supervise` stops polling — which is every kill path
— wedging a thread behind a full pipe, and the obvious release valve (closing
the pipe from `supervise`) is worse still: the racing `readline` raises inside
the thread, surfaces as `collector_failure`, and E7 then forces `KILLED` over
the `TIMED_OUT` that actually happened.

This module is POSIX-only (E6/D-j). `nox.api.review()` refuses `win32` before
any spawn, so nothing here branches on the platform; `signal.SIGKILL` and
`os.killpg` are therefore referenced from function bodies only, so importing
this module on Windows still succeeds and fails at the documented gate rather
than at import.
"""

from __future__ import annotations

import io
import os
import queue
import signal
import stat
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import IO, Final, Protocol

from nox.capability import Launcher
from nox.liveness import Heartbeat, Liveness, TimeoutPolicy
from nox.outcome import FailureReason
from nox.workspace import IsolationError

BYTE_CAP: Final[int] = 8 << 20
"""Captured output ceiling, in bytes (C-1009). An unmeasured default (C-1010)."""

MAX_LINES: Final[int] = BYTE_CAP // 64
"""Captured output ceiling, in lines — a second, independent ceiling.

`BYTE_CAP` bounds the *stream*; this bounds the per-object allocation the stream
turns into, which the byte count does not see. 8 MiB of two-byte lines is
4.19 M `str` objects and a measured ~320 MiB of RSS, so a harness emitting
two-byte lines could OOM-kill nox under a CI memory cgroup while staying well
inside the byte cap. 64 is a conservative per-`str` overhead charge, and the
derivation is from `BYTE_CAP` rather than from `_drain`'s `cap` argument so a
test's small injected cap cannot move it.
"""

READ_BOUND: Final[int] = 1 << 20
"""Per-`readline` byte bound (E7).

A line longer than this arrives split, and the split resolves
`MALFORMED_OUTPUT` downstream — the correct answer for a harness emitting a
1 MiB JSON line, and cheaper than a framer that would reassemble unbounded
attacker-sized lines in memory.
"""

POLL_S: Final[float] = 0.05
"""How long each `supervise` poll waits for its first line.

The reason `supervise` never blocks on a read: the wait is against the queue,
not against the child. It is *not* a bound on how late a deadline fires — a
poll drains its whole batch and calls `on_line` on every line before re-reading
the clock, so lateness is (batch size x `on_line` cost) and a measured 2.49 s
against a 1 s wall clock is normal. `BYTE_CAP` and `MAX_LINES` bound the total
number of lines, so the overrun is finite; a per-line clock check would buy
tightness at the cost of a clock call per line.
"""

JOIN_S: Final[float] = 5.0
"""How long `Process.wait` waits for the drain thread once the child is gone.

A grandchild that inherited the pipe holds it open, so the read never sees EOF
however dead the child is. The thread is a daemon: abandoning one costs a
thread, blocking here would cost the caller the deadline it asked for.

This is therefore the whole of what v1 guarantees against a descendant that
survives the review (D-ac): nox returns on time. The survivor is not killed —
on the clean-exit path nothing signals it, and a `setsid()` escape is outside
the group on every path.
"""

Clock = Callable[[], float]
"""Monotonic clock seam; tests inject a deterministic one."""

Kill = Callable[[int, int], None]
"""`(pid, signal)` seam. Injected so the ladder is testable without a child, and
so a non-POSIX kill primitive would cost no second pragma (D-j)."""

OnLine = Callable[[str], bool]
"""Consumes one output line; returns whether it was a *semantic* progress event.

The adapter, not the supervisor, knows whether a line is an event or noise
(C-1010): a stack trace, a progress bar or a Node deprecation warning is bytes
without progress. The answer means the same thing for every harness — a
`BYTE_ACTIVITY` adapter answers `False` for its raw lines and its 300 s window
still measures, because `supervise` runs that window against `last_byte_at`.
An adapter that answered `True` to keep its own clock alive would corrupt
`Heartbeat.events`, which is the evidence a timeout detail is written from.
"""


@dataclass(frozen=True, slots=True)
class Invocation:
    """One fully-resolved child launch. Nothing here is composed further.

    Attributes:
        argv: The complete argv as a list of words — never an f-string, never
            shell-parsed (C-1009, CWE-78). C-1009 also said the diff is never
            an element of it; that half is corrected by E29 — on the two
            argv-only harnesses the diff rides here inside the prompt, bounded
            by `harness.PROMPT_ARGV_LIMIT`.
        cwd: Always the ephemeral worktree (C-1003).
        env: The already-minimal child environment (C-1008). Copied behind a
            `MappingProxyType` at construction: this is the C-1008 trust
            boundary, and a frozen dataclass holding a caller's live `dict`
            would be promising an immutability it does not have.
        stdin_path: A nox-owned file to hand the child as its standard input,
            or `None` for `DEVNULL`. This is the **second prompt channel**
            (C-1028): `claude` and `codex` read their prompt from stdin, so on
            those two the prompt — and with it the diff — never becomes an argv
            word and `PROMPT_ARGV_LIMIT` does not bind. Only `harness.authorize`
            sets it, and only to a path directly inside `Workspace.scratch`;
            `spawn` opens it `O_NOFOLLOW`. Both halves matter: without the first
            an adapter could name any readable file, and without the second a
            symlink planted at `prompt.md` by a harness that already ran in this
            workspace would redirect the open.
    """

    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]
    stdin_path: Path | None = None

    def __post_init__(self) -> None:
        """Replace `env` with a read-only snapshot of what the caller passed."""
        object.__setattr__(self, "env", MappingProxyType(dict(self.env)))


class _Child(Protocol):
    """The slice of `subprocess.Popen` that `SubprocessProcess` is written against.

    Private, and deliberately four members wide. It exists so the drain
    thread's failure path can be exercised against a fake whose `stdout` raises
    — a real pipe's `readline` cannot be made to fail on demand, and covering
    that path any other way would cost a second no-cover pragma the budget does
    not have (C-1015, E7).

    `kill` is here only for the constructor's own failure path: a child whose
    drain thread never started has no `Process` wrapper, so nothing else could
    ever reap it. Escalation belongs to `supervise`'s ladder, which signals the
    group through the injected `kill` and never touches this member.
    """

    @property
    def pid(self) -> int:
        """The child's pid."""
        ...

    @property
    def stdout(self) -> IO[bytes] | None:
        """The merged stdout+stderr pipe, in binary mode."""
        ...

    def wait(self, timeout: float | None = None) -> int:
        """Reap the child, raising `subprocess.TimeoutExpired` on timeout."""
        ...

    def kill(self) -> None:
        """Send SIGKILL to this child alone — not to its group."""
        ...


class Process(Protocol):
    """The slice of a running child `supervise` is written against.

    Deliberately without a `send`: v1 adapters are argv plus a line-oriented
    stream and no adapter runs a long-lived protocol session (C-1024). Adopting
    Codex's `app-server` later adds exactly one method here and moves nothing
    else in the seam.

    `collector_failure` and `overflowed` are the drain thread's two out-of-band
    signals. `supervise` reads both on every poll rather than waiting for a
    stream that will never end: a dead collector behind a full pipe would
    otherwise be indistinguishable from a slow review until the wall clock (E7).

    The sketch's `poll()` and `signal_group()` are absent: `wait(0.0)` subsumes
    the first, and the kill primitive is injected into `supervise` instead of
    living here, which is what makes a non-POSIX kill cost no second pragma
    (D-j).
    """

    @property
    def pid(self) -> int:
        """The child's pid, which is also its process-group id (`start_new_session`)."""
        ...

    @property
    def collector_failure(self) -> BaseException | None:
        """The exception that ended the drain thread, or `None` while it is healthy."""
        ...

    @property
    def overflowed(self) -> bool:
        """Whether the drain thread stopped because output passed one of its ceilings."""
        ...

    def lines(self, timeout: float) -> tuple[str, ...]:
        """Return every line that has arrived, waiting at most `timeout` for the first.

        Bounded by `timeout` and never by the child: this is the read
        `supervise` polls, and a read that could block on the child would make
        every deadline in this module advisory. A materialized tuple rather
        than an `Iterator` for the same reason — a lazy iterator's `__next__`
        would put the blocking read back, one call deeper.

        Args:
            timeout: Seconds to wait for the first line before giving up.

        Returns:
            The lines drained this batch, possibly empty.
        """
        ...

    def wait(self, timeout: float | None) -> int | None:
        """Reap the child, waiting at most `timeout` seconds.

        A non-`None` return implies the drain thread has finished or been
        abandoned, and that every line it enqueued is retrievable by a
        subsequent `lines(0.0)`. Without that guarantee the last line — which
        is typically the harness's final result object — is dropped whenever
        the child exits between one poll's drain and the same poll's exit
        check, and a complete review resolves a spurious `MALFORMED_OUTPUT`.

        Args:
            timeout: Seconds to wait; `None` waits indefinitely.

        Returns:
            The exit status, or `None` if the child is still running.
        """
        ...


class Runner(Protocol):
    """Process *creation* only (C-1015). Supervision is `supervise`, not a method here."""

    def spawn(self, inv: Invocation) -> Process:
        """Start `inv` and return the live child.

        Args:
            inv: The fully-resolved launch.

        Returns:
            The running child, already being drained.
        """
        ...


@dataclass(frozen=True, slots=True)
class Supervision:
    """What one supervised run resolved to, before any adapter parses a byte of it.

    Attributes:
        exit_code: The child's exit status. `None` only when the child was
            still unreaped `grace_s` after SIGKILL — uninterruptible sleep, a
            ptrace stop. A supervisor that waited indefinitely for that status
            would make the wall-clock ceiling it exists to enforce advisory, and
            synthesising `-9` instead would report a status the OS never gave.
        truncated: Mirrors the drain thread's overflow flag: one of its two
            ceilings (`BYTE_CAP`, `MAX_LINES`) was hit (C-1009). Not "was the
            stream cut" — on the collector-failure and kill paths the stream
            ends early and this is still `False`.
        reason: The outcome `supervise` itself forced — `TIMED_OUT`, `KILLED`
            or `MALFORMED_OUTPUT`. `None` means the child ended on its own and
            the adapter's `parse` owns the classification; the exit code is
            never the success gate (C-1011).
        detail: nox's own account of a forced outcome — both heartbeat
            timestamps on a timeout, the collector's exception on a dead drain
            thread. Never harness output.
    """

    exit_code: int | None
    truncated: bool
    reason: FailureReason | None
    detail: str | None

    def __post_init__(self) -> None:
        """Enforce that a missing exit status always arrives with a forced reason.

        `exit_code is None` is reachable only through the kill ladder, which
        only ever runs with a `reason` already decided. Stating it here rather
        than in prose is what lets the adapter contract keep `parse(lines,
        exit_code: int, hb)` exactly as the ADR spells it: a consumer calls
        `parse` on the `reason is None` path, where the status is always an int.

        Raises:
            ValueError: `exit_code` is `None` while `reason` is not set.
        """
        if self.exit_code is None and self.reason is None:
            raise ValueError("exit_code is None only on the kill ladder, which always carries a reason")


def _drain(stream: IO[bytes], sink: queue.SimpleQueue[str], cap: int) -> bool:
    """Read `stream` line by line into `sink` until EOF, `cap` bytes or `MAX_LINES` lines (E7).

    Binary, then decoded per line with `errors="replace"`: harness output is
    untrusted bytes, a text-mode pipe would raise `UnicodeDecodeError` inside
    the thread on the first invalid sequence, and `len()` over bytes is the byte
    count the cap is specified in rather than a character count that resembles
    one.

    Both ceilings are enforced **before** the enqueue, so the offending line is
    never handed on and the queue is bounded by both. `MAX_LINES` is checked
    against the module constant, never against `cap`: the two bound different
    things — bytes on the wire and `str` objects in the heap — and folding the
    object charge into `cap` would make output *smaller* than `BYTE_CAP`
    truncate. Stopping the read is what then kills the run: the pipe fills, the
    child blocks on write, and the next `supervise` poll sees `overflowed` and
    takes it down.

    A line keeps the trailing newline `readline` produced, so `"".join(lines)`
    reconstructs the stream verbatim — `raw` is retained unconditionally
    (C-1018) and a consumer wanting a bare line strips it.

    Args:
        stream: The child's merged stdout+stderr pipe. Closed on the way out.
        sink: Where decoded lines are handed to `supervise`.
        cap: Byte ceiling for the whole stream.

    Returns:
        `True` if either ceiling was reached, `False` on a clean EOF.
    """
    total = 0
    count = 0
    try:
        while True:
            chunk = stream.readline(READ_BOUND)
            if not chunk:
                return False
            if total + len(chunk) > cap:
                return True
            if count >= MAX_LINES:
                return True
            total += len(chunk)
            count += 1
            sink.put(chunk.decode("utf-8", errors="replace"))
    finally:
        stream.close()


def _kill_group(pid: int, sig: int) -> None:
    """Send `sig` to the process group led by `pid`, swallowing `ESRCH`.

    The child leads its own session (`start_new_session=True`), so its pid is
    its process-group id and this can never reach the group nox itself runs in.
    A race between the liveness poll and the signal is normal, not an error: the
    child is reaped by `Process.wait` either way.

    The pid-recycling guard (CWE-367, bpo-38630) cannot live here — the seam
    takes a bare pid by design (D-j), so there is no `returncode` to consult.
    It is an invariant of `supervise` instead: once `Process.wait` has returned
    a status, `supervise` issues no further kill, and an unreaped child holds
    its own pid as a zombie until then.

    Only `ESRCH` is swallowed. Every other `OSError` propagates — a swallowed
    `EPERM` would hide a kill that never landed.

    Args:
        pid: The child's pid, which is its process-group id.
        sig: The signal number.
    """
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass  # Reaped between the poll and the signal; `Process.wait` has it either way.


class SubprocessProcess:
    """A live child plus the daemon thread draining its merged pipe.

    Constructed by `SubprocessRunner.spawn` and unit-tested against both a real,
    harness-free child and a scripted fake, so every line of it is covered under
    `fail_under = 100` without the seam's one pragma widening (E7).
    """

    def __init__(self, popen: _Child, *, cap: int = BYTE_CAP) -> None:
        """Start a daemon thread draining `popen`'s merged output pipe.

        The thread is a daemon so an unreapable child cannot hang interpreter
        shutdown behind a pipe that never reaches EOF — the same failure
        `Supervision.exit_code is None` exists to bound.

        A `popen.stdout` of `None` — which the `_Child` protocol permits — is an
        immediately-closed stream: the thread still starts and reaches EOF at
        once, so every other member behaves as it does for a silent child rather
        than growing a `None` case of its own.

        A `start` that fails — `RLIMIT_NPROC` exhaustion, interpreter shutdown —
        kills and reaps the child before re-raising. `SubprocessRunner.spawn`
        has already created the `Popen` by this point, so letting the exception
        escape would leave a live harness with no `Process` object in existence
        to `wait` or `kill` it, writing into a worktree the caller is about to
        remove.

        Args:
            popen: A child started with `stdout=PIPE, stderr=STDOUT` and
                `start_new_session=True`.
            cap: Byte ceiling handed to the drain thread. A test knob, not a
                C-1009 knob: `Runner.spawn` exposes no route to it and no
                config value reaches it.
        """
        self._popen = popen
        self._queue: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._failure: BaseException | None = None
        self._overflowed = False
        stream = io.BytesIO() if popen.stdout is None else popen.stdout
        self._thread = threading.Thread(
            target=self._collect, args=(stream, cap), name=f"nox-drain-{popen.pid}", daemon=True
        )
        try:
            self._thread.start()
        except BaseException:
            popen.kill()
            popen.wait()
            raise

    def _collect(self, stream: IO[bytes], cap: int) -> None:
        """Run `_drain`, recording whatever ended the thread as an out-of-band signal.

        A drain thread that dies must become `collector_failure` rather than a
        traceback on stderr: `supervise` reads it on the next poll and takes the
        child down, instead of waiting out the wall clock behind a full pipe (E7).

        Both flags are written here and read from `supervise`'s thread with no
        lock, and that is sound on the supported matrix: CPython 3.11-3.14 under
        the GIL, where an attribute store is atomic and the drain's last
        `sink.put` — a C-level locked operation — happens-before the assignment,
        so a reader that observes either flag has already observed every line
        behind it. CI runs no free-threaded build, which is the only
        configuration that would need an explicit fence; the whole
        out-of-band-signal design rests on this.
        """
        try:
            self._overflowed = _drain(stream, self._queue, cap)
        except BaseException as exc:  # Recorded, never handled here: `supervise` decides what it means.
            self._failure = exc

    @property
    def pid(self) -> int:
        """The child's pid, which is also its process-group id."""
        return self._popen.pid

    @property
    def collector_failure(self) -> BaseException | None:
        """The exception that ended the drain thread, or `None`."""
        return self._failure

    @property
    def overflowed(self) -> bool:
        """Whether the drain thread stopped at `BYTE_CAP` or at `MAX_LINES`."""
        return self._overflowed

    def lines(self, timeout: float) -> tuple[str, ...]:
        """Drain every queued line, waiting at most `timeout` for the first.

        Args:
            timeout: Seconds to wait for the first line.

        Returns:
            The lines drained this batch, possibly empty.
        """
        try:
            batch = [self._queue.get(timeout=timeout)]
        except queue.Empty:
            return ()
        while True:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                return tuple(batch)

    def wait(self, timeout: float | None) -> int | None:
        """Reap the child, waiting at most `timeout` seconds.

        Before returning a status it joins the drain thread for at most
        `JOIN_S`, so the `Process.wait` tail guarantee holds: everything the
        child wrote is queued by the time a caller sees it exit. A thread still
        alive after that is abandoned — it is a daemon, and a grandchild
        holding the pipe open must not outlast the deadline.

        Args:
            timeout: Seconds to wait; `None` waits indefinitely.

        Returns:
            The exit status, or `None` if the child is still running.
        """
        try:
            status = self._popen.wait(timeout)
        except subprocess.TimeoutExpired:
            return None
        self._thread.join(JOIN_S)
        return status


def _open_prompt(path: Path) -> int:
    """Open the prompt file to hand a child as stdin, or refuse it (C-1028, E29).

    The window this guards is real and narrow: `review_prompt` writes
    `prompt.md` during `prepare`, `authorize` then spawns `adapter.sandbox_probe`
    — a real harness, in this same workspace — and only afterwards does `spawn`
    take this descriptor. `write_nofollow`'s contract says the scratch DIRECTORY
    is unprotected once a harness has run there, so between the write and this
    open the file may have been replaced.

    Three flags and one check, each closing a different shape:

    - `O_NOFOLLOW` refuses a **symlink** swapped in at `prompt.md`, which would
      otherwise feed an arbitrary readable file to the next harness as its
      prompt.
    - `O_NONBLOCK` is what makes the **FIFO** shape testable rather than fatal.
      Opening a FIFO for reading blocks until a writer appears, and this runs in
      `review()`'s own thread before any `TimeoutPolicy` exists — no deadline
      anywhere would end it, so the symlink guard alone would leave the strictly
      worse hang open beside the read it refused. It is a no-op on a regular
      file, so the descriptor the child receives is unaffected.
    - `S_ISREG` is the actual refusal, and it covers the directory shape too.
    - `O_CLOEXEC` keeps this descriptor out of any other child; `Popen` dup2s it
      onto fd 0 before exec, which clears the flag exactly where it must.

    Two residuals, neither an escalation. `O_NOFOLLOW` guards only the FINAL
    component, so a swapped *directory* component is unreached — `dir_fd=` is
    the upgrade path, the same one `write_nofollow` names — and a **hardlink**
    at `prompt.md` is invisible to it. Both need the same-uid write access that
    would already let the attacker read the target directly, so neither buys
    anything the shape does not already have.

    `IsolationError` and not a bare `OSError`, because `api._spawn` maps every
    `OSError` to `HarnessUnavailable(ABSENT)` — which SD § 7.1 documents as the
    row a consumer degrades to a graceful skip. A detected tamper reported as
    "the harness is not installed" is a silent no-review. The write half of this
    same defence already raises `IsolationError`.

    Args:
        path: The prompt file, already constrained to `Workspace.scratch` by
            `harness.authorize` — this function checks WHAT it is, never where.

    Returns:
        A read-only descriptor on a regular file.

    Raises:
        IsolationError: The path is gone, is not a regular file, or is a
            symlink. The message names the failure, never the resolved path,
            which is a `$HOME` path outside the repository (C-1035(1)).
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as exc:
        raise IsolationError(f"prompt: {path.name} could not be opened to deliver it ({type(exc).__name__})") from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise IsolationError(f"prompt: {path.name} is not a regular file and is never delivered (C-1028)")
    except BaseException:
        os.close(fd)
        raise
    return fd


class SubprocessRunner:
    """The only place `subprocess` is imported, and the only place a child is created.

    `spawn` constructs the `Popen` with the C-1009 hardening fixed rather than
    configurable — there is no knob here, by contract.
    """

    def spawn(self, inv: Invocation) -> Process:
        """Start `inv` with the C-1009 hardening and begin draining it.

        `shell=False` with argv as a list (CWE-78); `start_new_session=True` so
        the child leads its own process group and one signal reaches every
        descendant still in it; `close_fds=True` so no descriptor nox holds
        leaks into an untrusted child; stderr merged into stdout so one pipe
        carries the whole stream in order; stdin at `DEVNULL` so a harness
        prompting for input gets EOF instead of nox's own terminal.

        **`inv.stdin_path` is the one exception, and it does not weaken that
        last property.** The child reads a nox-written file and then gets EOF —
        never nox's own fd 0, which is what `DEVNULL` was defending. The open is
        `O_RDONLY|O_NOFOLLOW|O_CLOEXEC`: `Workspace.scratch` is unprotected once
        a harness has run there (`write_nofollow`), so a symlink planted at
        `prompt.md` is the live shape, and following it would feed an arbitrary
        readable file to the next harness as its prompt. A regular file rather
        than a pipe nox writes, so there is no size to bound and no drain to
        deadlock against: the kernel does the reading while the drain thread
        owns stdout.

        A pgid is process-group control, not containment: a grandchild that
        calls `setsid()` itself leaves the group and no rung of the ladder
        reaches it, and on the clean-exit path no signal is issued at all, so
        anything the harness backgrounded outlives the review and can hold the
        merged pipe open until `JOIN_S` abandons the drain thread.

        Both holes are **accepted, not deferred** (D-ac). Sweeping the group
        after a clean exit needs `waitid(WNOWAIT)` — observing the exit without
        reaping is what the CWE-367 pid-recycling guard requires before a
        post-exit `killpg` — and CPython does not expose `os.waitid` on macOS
        before 3.13, against a 3.11 floor; and it would still not reach a
        `setsid()` escape, which needs cgroups or a PID namespace. So v1 bounds
        nox's own return, by `JOIN_S`, and never the survivor's lifetime.

        Args:
            inv: The fully-resolved launch.

        Returns:
            The running child, already being drained.
        """
        stdin: int = subprocess.DEVNULL
        if inv.stdin_path is not None:
            stdin = _open_prompt(inv.stdin_path)
        try:
            # The one pragma the codebase is allowed (C-1015). It is a budget
            # ceiling, not a coverage gap: the real-child test below does execute
            # this line. Do not delete the marker — the static test asserts it is
            # here, and its absence would let a second one appear elsewhere.
            popen = subprocess.Popen(  # pragma: no cover - C-1015: the codebase's only no-cover line
                list(inv.argv),
                cwd=inv.cwd,
                env=dict(inv.env),
                shell=False,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            # `Popen` dup2s it onto the child's fd 0 before exec, so the parent's
            # copy is dead weight either way — and on the raising path it is a
            # descriptor leak into every later spawn.
            if stdin != subprocess.DEVNULL:
                os.close(stdin)
        return SubprocessProcess(popen)


def _timeout_detail(bound: str, elapsed: float, hb: Heartbeat) -> str:
    """Render a `TIMED_OUT` detail carrying both heartbeat timestamps (C-1010).

    Both travel, so "noisy but eventless" is distinguishable from "dead"
    without guessing.

    Args:
        bound: Which deadline elapsed.
        elapsed: Seconds that bound had been running when it fired.
        hb: The heartbeat whose timestamps are the evidence.

    Returns:
        The detail string.
    """
    return (
        f"{bound} timeout after {elapsed:.1f}s "
        f"(last_activity_at={hb.last_activity_at:.3f}, last_byte_at={hb.last_byte_at:.3f})"
    )


def supervise(
    proc: Process,
    policy: TimeoutPolicy,
    hb: Heartbeat,
    on_line: OnLine,
    *,
    clock: Clock = time.monotonic,
    kill: Kill = _kill_group,
) -> Supervision:
    """Supervise `proc` to an outcome, blocking on nothing but the poll interval.

    Pure over `Process` (C-1015): the clock and the kill primitive are injected,
    so the whole ladder is exercised against a fake with no child in sight.

    Each poll drains whatever the drain thread has queued, hands each line to
    `on_line` and touches `hb` with its answer, then — in this order — checks
    the drain thread's two out-of-band signals, the child's own exit, and the
    two deadlines. Collector failure and overflow come first deliberately: a
    child flooding a pipe nobody is reading any more must be killed on the next
    poll, not at the wall clock (E7).

    Both heartbeat timestamps are reset to the moment supervision begins, so the
    silence window is measured from the start of the run rather than from
    whenever the caller happened to construct the `Heartbeat`.

    **Which clock silence runs against is derived from `hb.kind`, never from the
    adapter** (C-1010): `BYTE_ACTIVITY` measures `last_byte_at`, because bytes
    are the only progress signal that harness has; every other kind measures
    `last_activity_at`, so a `SEMANTIC` harness emitting noise for 120 s is
    killed exactly as C-1010 requires. `policy.silence_s is None`
    (`PROCESS_ONLY`) skips the check entirely — absence of activity carries no
    information when the only signal is that a pid exists.

    The kill ladder is SIGTERM to the group, `policy.grace_s`, then SIGKILL to
    the group, then a final reap bounded by `policy.grace_s` again. It runs from
    a `finally`, so an `on_line` that raises — or a `KeyboardInterrupt` — cannot
    leave a live harness writing into a worktree the caller is about to remove;
    the second rung and the reap run from a `finally` of their own for the same
    reason, since `_kill_group` propagates every non-`ESRCH` `OSError` and a
    refused SIGTERM must not abandon the child one rung short. No kill is ever
    issued after `proc.wait` has returned a status, which is what stands in for
    the pid-recycling guard `_kill_group` cannot hold.

    Whatever ended the loop, one last `lines(0.0)` runs after the ladder and
    before returning. That is where the SIGTERM rung pays off: a harness that
    handles SIGTERM prints its final result and exits 143, and that line is
    queued during the grace window, after the poll loop has already broken.

    `truncated` mirrors `proc.overflowed` on every return path, timeout and
    collector failure included — it reports the overflow flag, never "was the
    stream cut short", which is also true on paths that leave it `False`. And
    where exit and a deadline land on the same poll, `reason` is `None`: the
    documented poll order decides it, and the child ended on its own.

    Args:
        proc: The running child.
        policy: The bounds this run is held to (C-1010).
        hb: Progress evidence, mutated in place as output arrives.
        on_line: Consumes each line; returns whether it was a semantic event.
        clock: Monotonic clock; defaults to `time.monotonic`.
        kill: `(pid, signal)` primitive; defaults to signalling the process group.

    Returns:
        The outcome, with `reason` set only where `supervise` itself forced one.
    """
    started = clock()
    hb.last_activity_at = started
    hb.last_byte_at = started
    exit_code: int | None = None
    reason: FailureReason | None = None
    detail: str | None = None
    reaped = False
    try:
        while True:
            for line in proc.lines(POLL_S):
                hb.touch(clock(), semantic=on_line(line))
            now = clock()

            failure = proc.collector_failure
            if failure is not None:
                reason, detail = FailureReason.KILLED, f"drain thread failed: {failure!r}"
                break
            if proc.overflowed:
                reason, detail = FailureReason.MALFORMED_OUTPUT, "output cap exceeded"
                break

            exit_code = proc.wait(0.0)
            if exit_code is not None:
                reaped = True
                break

            elapsed = now - started
            if elapsed >= policy.wall_clock_s:
                reason, detail = FailureReason.TIMED_OUT, _timeout_detail("wall-clock", elapsed, hb)
                break
            if policy.silence_s is not None:
                last = hb.last_byte_at if hb.kind is Liveness.BYTE_ACTIVITY else hb.last_activity_at
                if now - last >= policy.silence_s:
                    reason, detail = FailureReason.TIMED_OUT, _timeout_detail("silence", now - last, hb)
                    break
    finally:
        # `reaped` is the CWE-367 stand-in: once `proc.wait` has returned a
        # status no signal is issued, and until then the child holds its own pid
        # as a zombie, so the group id cannot have been recycled under us.
        if not reaped:
            try:
                kill(proc.pid, signal.SIGTERM)
                exit_code = proc.wait(policy.grace_s)
            finally:
                # An `EPERM` from the first rung, or a `KeyboardInterrupt`
                # inside the grace wait, must not leave the child alive: the
                # child is outside nox's foreground group, so Ctrl-C reaches
                # nox and not the harness. Whatever raised still propagates.
                if exit_code is None:
                    kill(proc.pid, signal.SIGKILL)
                    exit_code = proc.wait(policy.grace_s)
    # After the ladder, not inside it: on the path where `on_line` itself raised
    # there is nothing to hand a line to, and re-entering it there would mask
    # the exception the caller has to see.
    for line in proc.lines(0.0):
        hb.touch(clock(), semantic=on_line(line))
    return Supervision(exit_code=exit_code, truncated=proc.overflowed, reason=reason, detail=detail)


__all__ = [
    "BYTE_CAP",
    "JOIN_S",
    "MAX_LINES",
    "POLL_S",
    "READ_BOUND",
    "Clock",
    "Invocation",
    "Kill",
    "Launcher",
    "OnLine",
    "Process",
    "Runner",
    "SubprocessProcess",
    "SubprocessRunner",
    "Supervision",
    "supervise",
]
