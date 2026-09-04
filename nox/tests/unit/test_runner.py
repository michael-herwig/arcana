"""Process creation and supervision: kill ladder, drain thread and seam.

C-1009, C-1010, C-1015, C-1024, E6, E7.

Everything about `supervise` runs against a scripted `FakeProcess` with an
injected clock and an injected kill, so the ladder is pinned as an exact call
sequence instead of hoped for against a real child on a loaded machine — which
is the whole point of C-1015's seam. Simulated time only moves when the
supervisor polls, so a supervision that stops polling cannot hang the suite.

Some tests do spawn a real child, because a fake would prove nothing there:
that `_kill_group` actually reaps a process group, that the drain thread
survives a real pipe, that `SubprocessRunner.spawn` really puts the child
in its own session with stdin at EOF and stderr merged in order (C-1009), and
that D-ac's accepted residual is what the code actually does — a real forked
grandchild holding the merged pipe open bounds `Process.wait` by `JOIN_S` and
survives, on both of the paths the process group does not close.
"""

import ast
import io
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import tokenize
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import IO, cast

import pytest

from nox import runner
from nox.liveness import Heartbeat, Liveness, TimeoutPolicy
from nox.outcome import FailureReason
from nox.runner import (
    BYTE_CAP,
    JOIN_S,
    MAX_LINES,
    READ_BOUND,
    Invocation,
    SubprocessProcess,
    SubprocessRunner,
    Supervision,
    _drain,
    _kill_group,
    supervise,
)
from nox.workspace import IsolationError

START = 1000.0
"""Simulated clock origin. Non-zero so a reset-to-start assertion cannot pass by accident."""

STEP = 1.0
"""Simulated seconds one `lines()` poll consumes. The tests reason in these, never in real seconds."""

# Resolved from this file, never from the cwd — the static scans are about the
# nox subtree whether pytest was invoked from the repo root or from nox/.
NOX = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------
# Fakes: the C-1015 seam made concrete
# --------------------------------------------------------------------------


class _Clock:
    """A monotonic clock the test moves explicitly (C-1015: the clock is injected)."""

    def __init__(self, start: float = START) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _KillLog:
    """The injected kill primitive, recording `(pid, signal)` in order (D-j)."""

    def __init__(self, clock: _Clock, on_kill: Callable[[int, int], None] | None = None) -> None:
        self._clock = clock
        self._on_kill = on_kill
        self.calls: list[tuple[int, int]] = []
        self.times: list[float] = []

    def __call__(self, pid: int, sig: int) -> None:
        self.calls.append((pid, sig))
        self.times.append(self._clock.now)
        if self._on_kill is not None:
            self._on_kill(pid, sig)


class FakeProcess:
    """A scripted `Process` whose polls are the only thing that moves the clock.

    `lines()` consumes `step` simulated seconds and `wait(timeout)` consumes at
    most `timeout`, so nothing here depends on real time. A supervision that
    stops polling stops advancing, and the poll guard trips with a message
    rather than hanging the suite.

    `batches` is a FIFO of what each successive `lines()` call returns; once it
    is exhausted `producer(now)` is asked, and `()` is the answer if there is
    no producer. `exit_at`, `failure_at` and `overflow_at` are simulated clock
    times from which the child is gone, the drain thread is dead, and the byte
    cap has been hit, respectively.
    """

    _MAX_POLLS = 100_000

    def __init__(
        self,
        clock: _Clock,
        *,
        pid: int = 4321,
        step: float = STEP,
        batches: Sequence[Sequence[str]] | None = None,
        producer: Callable[[float], Sequence[str]] | None = None,
        exit_at: float | None = None,
        exit_code: int = 0,
        failure_at: float | None = None,
        failure: BaseException | None = None,
        overflow_at: float | None = None,
    ) -> None:
        self._clock = clock
        self.pid = pid
        self._step = step
        self._batches: list[Sequence[str]] = list(batches) if batches is not None else []
        self._producer = producer
        self.exit_at = exit_at
        self._exit_code = exit_code
        self._failure_at = failure_at
        self._failure = failure
        self._overflow_at = overflow_at
        self.polls = 0
        self.waits: list[float | None] = []

    @property
    def collector_failure(self) -> BaseException | None:
        if self._failure_at is None or self._clock.now < self._failure_at:
            return None
        return self._failure

    @property
    def overflowed(self) -> bool:
        return self._overflow_at is not None and self._clock.now >= self._overflow_at

    def lines(self, timeout: float) -> tuple[str, ...]:
        self.polls += 1
        if self.polls > self._MAX_POLLS:
            raise AssertionError(f"supervise polled {self.polls} times without resolving (timeout={timeout})")
        if self._batches:
            batch = tuple(self._batches.pop(0))
        elif self._producer is not None:
            batch = tuple(self._producer(self._clock.now))
        else:
            batch = ()
        self._clock.advance(self._step)
        return batch

    def wait(self, timeout: float | None) -> int | None:
        self.waits.append(timeout)
        if self.exit_at is not None and self.exit_at <= self._clock.now:
            return self._exit_code
        if timeout is None:
            if self.exit_at is None:
                raise AssertionError("supervise waited indefinitely on a child that never exits")
            self._clock.now = self.exit_at
            return self._exit_code
        if self.exit_at is not None and self.exit_at <= self._clock.now + timeout:
            self._clock.now = self.exit_at
            return self._exit_code
        self._clock.advance(timeout)
        return None


class _AdapterBlewUp(Exception):
    """Distinct from every exception the module itself raises, so a stub cannot satisfy the test."""


class _OnLine:
    """Records every line handed over and answers `semantic` for all of them."""

    def __init__(self, *, semantic: bool = False) -> None:
        self.seen: list[str] = []
        self._semantic = semantic

    def __call__(self, line: str) -> bool:
        self.seen.append(line)
        return self._semantic


def _hb(kind: Liveness, at: float = 0.0) -> Heartbeat:
    return Heartbeat(kind=kind, last_activity_at=at, last_byte_at=at)


def _noise(_now: float) -> tuple[str, ...]:
    """One raw line per poll that no adapter calls a semantic event."""
    return ("progress: still working\n",)


# --------------------------------------------------------------------------
# supervise — silence and wall-clock deadlines (items 1-5)
# --------------------------------------------------------------------------


def test_semantic_silence_fires_at_120s_even_while_bytes_keep_arriving():
    """C-1010: the SEMANTIC window is over events, not bytes.

    A harness emitting a progress bar for two minutes is a hang. `on_line`
    answers `False` for every raw line, so `last_byte_at` advances and
    `last_activity_at` does not, and the kill is `TIMED_OUT`.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock, producer=_noise)
    hb = _hb(Liveness.SEMANTIC)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=120)
    on_line = _OnLine(semantic=False)

    sup = supervise(proc, policy, hb, on_line, clock=clock, kill=kill)

    assert sup.reason is FailureReason.TIMED_OUT
    assert on_line.seen, "the run had byte activity throughout — the lines must have been consumed"
    assert hb.events == 0
    assert hb.last_byte_at > hb.last_activity_at
    assert kill.calls, "a silence timeout kills the child"
    assert 120 <= kill.times[0] - START <= 120 + 2 * STEP


def test_the_timeout_detail_labels_each_heartbeat_timestamp_with_its_own_value():
    """C-1010: "noisy but eventless" must be distinguishable from "dead" without guessing.

    Both numbers travel and each sits behind its own label, so swapping the two
    labels is a detectable regression rather than the same pair in some order.
    The stream goes quiet well before the window expires, which is what makes
    the two values differ.
    """
    clock = _Clock()
    quiet_at = START + 50.0

    def producer(now: float) -> tuple[str, ...]:
        return _noise(now) if now < quiet_at else ()

    proc = FakeProcess(clock, producer=producer)
    hb = _hb(Liveness.SEMANTIC)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=120)

    sup = supervise(proc, policy, hb, _OnLine(), clock=clock, kill=_KillLog(clock))

    assert sup.detail is not None
    assert hb.last_activity_at == pytest.approx(START), "no raw line was a semantic event"
    assert hb.last_byte_at == pytest.approx(quiet_at), "raw lines arrived until the stream went quiet"
    assert hb.last_activity_at != hb.last_byte_at, "the two must differ, or a swapped label still passes"
    labelled = dict(re.findall(r"(last_\w+_at)=(-?\d+(?:\.\d+)?)", sup.detail))
    assert float(labelled["last_activity_at"]) == pytest.approx(hb.last_activity_at), sup.detail
    assert float(labelled["last_byte_at"]) == pytest.approx(hb.last_byte_at), sup.detail


def test_semantic_events_hold_a_long_run_open_past_the_silence_window():
    """C-1010, the positive half of the same clause: real events do reset the window.

    Without it a `semantic=` regressed to a hardcoded `False` would kill every
    SEMANTIC harness at 120 s however many events it emitted, and every other
    assertion in the suite — all of which pin `hb.events == 0` — would stay green.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock, producer=_noise, exit_at=START + 600.0, exit_code=0)
    hb = _hb(Liveness.SEMANTIC)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=120)
    on_line = _OnLine(semantic=True)

    sup = supervise(proc, policy, hb, on_line, clock=clock, kill=kill)

    assert sup.reason is None, "a stream of real events must outlive the 120 s silence window"
    assert sup.exit_code == 0
    assert kill.calls == []
    assert hb.events == len(on_line.seen) >= 600, "every line was an event, and every one was counted"
    assert hb.last_activity_at == hb.last_byte_at, "a semantic line resets both clocks together"


def test_a_child_that_never_writes_a_line_is_killed_at_the_silence_bound():
    """C-1010: silence is measured by the clock, not by output arriving.

    `lines()` answers `()` on every poll — nothing advances the iterator — and
    the kill is still observed on schedule through the injected primitive.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=120)
    on_line = _OnLine()

    sup = supervise(proc, policy, _hb(Liveness.SEMANTIC), on_line, clock=clock, kill=kill)

    assert on_line.seen == []
    assert sup.reason is FailureReason.TIMED_OUT
    assert kill.calls, "silence must be observed through the injected kill"
    assert 120 <= kill.times[0] - START <= 120 + 2 * STEP


def test_process_only_never_fires_on_silence_however_long_it_stays_quiet():
    """C-1010: absence of activity carries no information when the only signal is a live pid."""
    clock = _Clock()
    kill = _KillLog(clock)
    policy = TimeoutPolicy.for_kind(Liveness.PROCESS_ONLY, 900)
    assert policy.silence_s is None
    proc = FakeProcess(clock, exit_at=START + 600.0, exit_code=0)

    sup = supervise(proc, policy, _hb(Liveness.PROCESS_ONLY), _OnLine(), clock=clock, kill=kill)

    assert sup.reason is None
    assert sup.exit_code == 0
    assert kill.calls == []


@pytest.mark.parametrize("kind", list(Liveness))
def test_the_wall_clock_fires_at_every_liveness_kind(kind):
    """C-1010: a wall-clock ceiling always applies, whatever silence means for the harness."""
    clock = _Clock()
    kill = _KillLog(clock)
    policy = TimeoutPolicy.for_kind(kind, 10)
    proc = FakeProcess(clock)

    sup = supervise(proc, policy, _hb(kind), _OnLine(), clock=clock, kill=kill)

    assert sup.reason is FailureReason.TIMED_OUT
    assert kill.calls, "the wall clock kills the child"
    assert 10 <= kill.times[0] - START <= 10 + 2 * STEP


def test_byte_activity_silence_is_not_reached_while_raw_lines_keep_arriving():
    """C-1010: a BYTE_ACTIVITY adapter honestly answers `False`, and its window still measures.

    The window runs against `last_byte_at` because bytes are the only progress
    signal that harness has — an adapter answering `True` to keep its own clock
    alive would corrupt `Heartbeat.events`.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    policy = TimeoutPolicy.for_kind(Liveness.BYTE_ACTIVITY, 3600)
    assert policy.silence_s == 300
    proc = FakeProcess(clock, producer=_noise, exit_at=START + 600.0, exit_code=0)
    hb = _hb(Liveness.BYTE_ACTIVITY)
    on_line = _OnLine(semantic=False)

    sup = supervise(proc, policy, hb, on_line, clock=clock, kill=kill)

    assert sup.reason is None
    assert sup.exit_code == 0
    assert kill.calls == []
    assert hb.events == 0, "an honest BYTE_ACTIVITY adapter reports no semantic events"


def test_byte_activity_silence_fires_300s_after_the_lines_stop():
    """C-1010: the same window, measured against `last_byte_at`, does kill a stream that dies."""
    clock = _Clock()
    kill = _KillLog(clock)
    quiet_at = START + 100.0

    def producer(now: float) -> tuple[str, ...]:
        return _noise(now) if now < quiet_at else ()

    proc = FakeProcess(clock, producer=producer)
    policy = TimeoutPolicy.for_kind(Liveness.BYTE_ACTIVITY, 3600)

    sup = supervise(proc, policy, _hb(Liveness.BYTE_ACTIVITY), _OnLine(), clock=clock, kill=kill)

    assert sup.reason is FailureReason.TIMED_OUT
    assert kill.calls
    elapsed_since_quiet = kill.times[0] - quiet_at
    assert 300 <= elapsed_since_quiet <= 300 + 2 * STEP


def test_the_wall_clock_fires_on_the_poll_where_elapsed_equals_the_bound():
    """The comparison is `>=`, not `>`: the ceiling is reached at exactly `wall_clock_s`.

    Relaxing it to `>` costs one whole poll interval on every run and the
    range-based assertions elsewhere cannot see the difference.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock)
    policy = TimeoutPolicy(wall_clock_s=10, silence_s=None, grace_s=5.0)

    supervise(proc, policy, _hb(Liveness.PROCESS_ONLY), _OnLine(), clock=clock, kill=kill)

    assert kill.times[0] == pytest.approx(START + 10.0), "the wall clock fires at exactly wall_clock_s"


def test_the_silence_window_fires_on_the_poll_where_it_equals_the_bound():
    """The same `>=` boundary on the other deadline (C-1010)."""
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=120)

    supervise(proc, policy, _hb(Liveness.SEMANTIC), _OnLine(), clock=clock, kill=kill)

    assert kill.times[0] == pytest.approx(START + 120.0), "silence fires at exactly silence_s"


# --------------------------------------------------------------------------
# supervise — the kill ladder (items 6-8)
# --------------------------------------------------------------------------


def test_the_kill_ladder_is_sigterm_then_sigkill_to_the_childs_own_group():
    """C-1009: SIGTERM first (Claude Code gets a defined exit 143 and runs SessionEnd), then SIGKILL.

    Both go to the pid, which is the process-group id because the child leads
    its own session. Nothing else is sent.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock, pid=90210)
    policy = TimeoutPolicy(wall_clock_s=10, silence_s=None, grace_s=5.0)

    supervise(proc, policy, _hb(Liveness.PROCESS_ONLY), _OnLine(), clock=clock, kill=kill)

    assert kill.calls == [(90210, signal.SIGTERM), (90210, signal.SIGKILL)]
    assert kill.times[1] - kill.times[0] == pytest.approx(policy.grace_s)


def test_a_child_that_dies_on_sigterm_is_never_sent_sigkill():
    """C-1009: the grace period exists so a harness can exit on its own terms."""
    clock = _Clock()
    proc = FakeProcess(clock, pid=90210, exit_code=143)

    def die_on_term(_pid: int, sig: int) -> None:
        if sig == signal.SIGTERM:
            proc.exit_at = clock.now + 1.0

    kill = _KillLog(clock, on_kill=die_on_term)
    policy = TimeoutPolicy(wall_clock_s=10, silence_s=None, grace_s=5.0)

    sup = supervise(proc, policy, _hb(Liveness.PROCESS_ONLY), _OnLine(), clock=clock, kill=kill)

    assert kill.calls == [(90210, signal.SIGTERM)]
    assert sup.exit_code == 143


def test_a_child_unreaped_after_sigkill_yields_no_exit_code():
    """C-1009: uninterruptible sleep or a ptrace stop must not make the wall-clock ceiling advisory.

    `None` is the honest answer — synthesising `-9` would report a status the
    OS never gave.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock, exit_at=None)
    policy = TimeoutPolicy(wall_clock_s=10, silence_s=None, grace_s=5.0)

    sup = supervise(proc, policy, _hb(Liveness.PROCESS_ONLY), _OnLine(), clock=clock, kill=kill)

    assert sup.exit_code is None
    assert sup.reason is FailureReason.TIMED_OUT
    assert [sig for _pid, sig in kill.calls] == [signal.SIGTERM, signal.SIGKILL]


def test_a_child_that_survives_sigterm_is_reaped_after_sigkill():
    """C-1009: the second rung is worth nothing without the reap that follows it.

    Dropping the final `wait` throws away a status the OS did give and reports
    `exit_code is None`, which `Supervision` reserves for a child nothing could
    reap at all.
    """
    clock = _Clock()
    proc = FakeProcess(clock, pid=4242, exit_code=-9)

    def die_on_sigkill(_pid: int, sig: int) -> None:
        if sig == signal.SIGKILL:
            proc.exit_at = clock.now + 1.0

    kill = _KillLog(clock, on_kill=die_on_sigkill)
    policy = TimeoutPolicy(wall_clock_s=10, silence_s=None, grace_s=5.0)

    sup = supervise(proc, policy, _hb(Liveness.PROCESS_ONLY), _OnLine(), clock=clock, kill=kill)

    assert kill.calls == [(4242, signal.SIGTERM), (4242, signal.SIGKILL)]
    assert sup.exit_code == -9, "the status the child died with is reported, not dropped"
    assert sup.reason is FailureReason.TIMED_OUT


def test_a_refused_sigterm_still_escalates_to_sigkill_and_still_reaps():
    """C-1009: `_kill_group` propagates every non-`ESRCH` `OSError`, so the ladder must survive one.

    An `EPERM` on the first rung used to abort the ladder before the grace wait
    and before SIGKILL, leaving a live harness writing into a worktree the
    caller is about to remove. The refusal still reaches the caller — it just no
    longer costs the escalation and the reap.
    """
    clock = _Clock()
    proc = FakeProcess(clock, pid=606, exit_code=137)
    denied = PermissionError(1, "Operation not permitted")

    def refuse_sigterm(_pid: int, sig: int) -> None:
        if sig == signal.SIGTERM:
            raise denied
        proc.exit_at = clock.now

    kill = _KillLog(clock, on_kill=refuse_sigterm)
    policy = TimeoutPolicy(wall_clock_s=10, silence_s=None, grace_s=5.0)

    with pytest.raises(PermissionError) as caught:
        supervise(proc, policy, _hb(Liveness.PROCESS_ONLY), _OnLine(), clock=clock, kill=kill)

    assert caught.value is denied, "the refusal reaches the caller unmasked by the escalation"
    assert [sig for _pid, sig in kill.calls] == [signal.SIGTERM, signal.SIGKILL]
    assert proc.waits[-1] == policy.grace_s, "the reap after SIGKILL still runs"


def test_a_line_queued_during_the_grace_window_still_reaches_on_line():
    """C-1009 + SD § 7.1: SIGTERM is chosen so the harness can print its result and exit 143.

    That line lands in the queue during the grace window, after the deadline has
    already broken the poll loop — so the ladder drains once more before
    returning. It is the most valuable part of a partial `raw`.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    final = '{"result": "written from the SIGTERM handler"}\n'

    def producer(now: float) -> tuple[str, ...]:
        return (final,) if now > START + 10.0 else ()

    proc = FakeProcess(clock, producer=producer)
    hb = _hb(Liveness.SEMANTIC)
    policy = TimeoutPolicy(wall_clock_s=10, silence_s=None, grace_s=5.0)
    on_line = _OnLine(semantic=True)

    sup = supervise(proc, policy, hb, on_line, clock=clock, kill=kill)

    assert sup.reason is FailureReason.TIMED_OUT
    assert on_line.seen == [final], "the final result line must not be left sitting in the queue"
    assert hb.events == 1


def test_supervision_refuses_a_missing_exit_code_without_a_forced_reason():
    """C-1015: `exit_code is None` is reachable only through the ladder, which always has a reason.

    Stating it in `__post_init__` is what lets the adapter contract keep
    `parse(lines, exit_code: int, hb)`.
    """
    with pytest.raises(ValueError, match=r"exit_code|reason"):
        Supervision(exit_code=None, truncated=False, reason=None, detail=None)


def test_supervision_accepts_a_missing_exit_code_alongside_a_reason():
    sup = Supervision(exit_code=None, truncated=False, reason=FailureReason.TIMED_OUT, detail="killed")
    assert sup.exit_code is None
    assert sup.reason is FailureReason.TIMED_OUT


# --------------------------------------------------------------------------
# supervise — the drain thread's two out-of-band signals (items 9-11)
# --------------------------------------------------------------------------


def test_overflow_kills_the_child_and_resolves_malformed_output():
    """E7: the cap stops the drain, the pipe fills, and the next poll takes the child down.

    The producer outruns the consumer, so the outcome is nox's own — never a
    wait behind a full pipe until the wall clock.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock, overflow_at=START + 3.0)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=None)

    sup = supervise(proc, policy, _hb(Liveness.BYTE_ACTIVITY), _OnLine(), clock=clock, kill=kill)

    assert sup.reason is FailureReason.MALFORMED_OUTPUT
    assert sup.detail == "output cap exceeded"
    assert sup.truncated is True
    assert kill.calls, "a child flooding a pipe nobody reads any more must be killed"
    assert clock.now - START < policy.wall_clock_s, "overflow resolves on the next poll, not at the wall clock"


def test_a_dead_drain_thread_is_detected_on_the_next_poll_and_kills_the_child():
    """E7: a dead collector behind a full pipe is otherwise indistinguishable from a slow review.

    The outcome is `KILLED` with the collector's exception in `detail`, and
    `supervise` returns well before the wall-clock deadline — asserted against
    the injected clock, not against wall time.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    boom = OSError("drain thread exploded on a torn pipe")
    proc = FakeProcess(clock, failure_at=START + 3.0, failure=boom)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=None)

    sup = supervise(proc, policy, _hb(Liveness.BYTE_ACTIVITY), _OnLine(), clock=clock, kill=kill)

    assert sup.reason is FailureReason.KILLED
    assert sup.detail is not None
    assert "drain thread exploded on a torn pipe" in sup.detail
    assert kill.calls, "the child is killed immediately, not at the wall clock"
    assert kill.times[0] - START <= 3.0 + 2 * STEP
    assert clock.now - START < 60.0, "returns well before the 3600 s wall clock"


def test_overflow_wins_over_an_exit_that_lands_on_the_same_poll():
    """E7: the poll order is a contract, not an accident of how the branches were typed.

    A child that floods past the cap and then exits is `MALFORMED_OUTPUT`.
    Checking exit first would report `reason=None` and hand a truncated stream
    to `parse` as if the review had run to completion.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    both_at = START + 3.0
    proc = FakeProcess(clock, overflow_at=both_at, exit_at=both_at, exit_code=0)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=None)

    sup = supervise(proc, policy, _hb(Liveness.BYTE_ACTIVITY), _OnLine(), clock=clock, kill=kill)

    assert sup.reason is FailureReason.MALFORMED_OUTPUT
    assert sup.truncated is True


def test_a_collector_failure_wins_over_an_exit_that_lands_on_the_same_poll():
    """E7: the same order at the first rung — a dead drain thread is `KILLED` whatever the child did."""
    clock = _Clock()
    kill = _KillLog(clock)
    both_at = START + 3.0
    proc = FakeProcess(clock, failure_at=both_at, failure=OSError("collector down"), exit_at=both_at, exit_code=0)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=None)

    sup = supervise(proc, policy, _hb(Liveness.BYTE_ACTIVITY), _OnLine(), clock=clock, kill=kill)

    assert sup.reason is FailureReason.KILLED


def test_truncated_mirrors_the_overflow_flag_even_on_a_timeout():
    """`truncated` reports the overflow flag on every path, never the outcome.

    The drain thread reaches the cap while the ladder is taking a timed-out
    child down: the run is `TIMED_OUT` and the stream really was truncated, and
    both facts have to travel.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    policy = TimeoutPolicy(wall_clock_s=10, silence_s=None, grace_s=5.0)
    proc = FakeProcess(clock, overflow_at=START + 12.0)

    sup = supervise(proc, policy, _hb(Liveness.BYTE_ACTIVITY), _OnLine(), clock=clock, kill=kill)

    assert sup.reason is FailureReason.TIMED_OUT, "the wall clock broke the loop before the cap was reached"
    assert sup.truncated is True


def test_killed_timed_out_and_malformed_output_are_three_distinct_labels():
    """E7 + SD § 7.1: `KILLED` means "we killed it", never a generic failure, and never a timeout."""
    policy = TimeoutPolicy(wall_clock_s=200, silence_s=None, grace_s=5.0)
    reasons: list[FailureReason | None] = []

    for factory in (
        lambda clock: FakeProcess(clock),
        lambda clock: FakeProcess(clock, failure_at=START + 3.0, failure=OSError("collector down")),
        lambda clock: FakeProcess(clock, overflow_at=START + 3.0),
    ):
        clock = _Clock()
        sup = supervise(
            factory(clock),
            policy,
            _hb(Liveness.BYTE_ACTIVITY),
            _OnLine(),
            clock=clock,
            kill=_KillLog(clock),
        )
        reasons.append(sup.reason)

    assert reasons == [FailureReason.TIMED_OUT, FailureReason.KILLED, FailureReason.MALFORMED_OUTPUT]
    assert len(set(reasons)) == 3


# --------------------------------------------------------------------------
# supervise — exit paths (items 12-15)
# --------------------------------------------------------------------------


def test_lines_still_queued_when_the_child_exits_all_reach_on_line():
    """C-1024 tail guarantee: the harness's final result object is never dropped.

    Without the final `lines(0.0)` after observing exit, a complete review
    resolves a spurious `MALFORMED_OUTPUT` whenever the child exits between one
    poll's drain and the same poll's exit check.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock, batches=[(), ('{"result": "final"}\n',)], exit_at=START, exit_code=0)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=None)
    on_line = _OnLine()

    sup = supervise(proc, policy, _hb(Liveness.SEMANTIC), on_line, clock=clock, kill=kill)

    assert on_line.seen == ['{"result": "final"}\n']
    assert sup.reason is None
    assert kill.calls == []


def test_a_clean_exit_forces_no_reason_and_issues_no_kill():
    """C-1011: the exit code is never the success gate — `reason is None` hands classification to `parse`."""
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock, batches=[("one\n", "two\n")], exit_at=START + 5.0, exit_code=2)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=None)
    on_line = _OnLine(semantic=True)

    sup = supervise(proc, policy, _hb(Liveness.SEMANTIC), on_line, clock=clock, kill=kill)

    assert sup.reason is None
    assert sup.detail is None
    assert sup.truncated is False
    assert sup.exit_code == 2
    assert kill.calls == []
    assert on_line.seen == ["one\n", "two\n"]


def test_no_kill_is_issued_when_exit_and_deadline_land_on_the_same_poll():
    """C-1009 / CWE-367: once `Process.wait` has returned a status, no further kill is issued.

    This is the invariant that stands in for the pid-recycling guard
    `_kill_group` cannot hold — it takes a bare pid by design (D-j), so there
    is no `returncode` for it to consult.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    policy = TimeoutPolicy(wall_clock_s=10, silence_s=None, grace_s=5.0)
    # Both become true on the same poll: the wall clock has elapsed and the
    # child has already exited. The documented poll order checks exit first.
    proc = FakeProcess(clock, exit_at=START + 10.0, exit_code=7)

    sup = supervise(proc, policy, _hb(Liveness.PROCESS_ONLY), _OnLine(), clock=clock, kill=kill)

    assert kill.calls == []
    assert sup.exit_code == 7
    assert sup.reason is None


def test_an_on_line_that_raises_still_reaps_the_child_and_propagates():
    """C-1009: the ladder runs from a `finally`, so no live harness is left writing into a worktree.

    The caller is about to remove that worktree; a surviving child would write
    into a path that no longer exists — or, worse, into whatever replaces it.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    proc = FakeProcess(clock, pid=555, batches=[("boom\n",)])
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=None, grace_s=5.0)

    def explode(_line: str) -> bool:
        raise _AdapterBlewUp("adapter blew up mid-stream")

    with pytest.raises(_AdapterBlewUp):
        supervise(proc, policy, _hb(Liveness.SEMANTIC), explode, clock=clock, kill=kill)

    assert kill.calls, "an exception must not leave a live child behind"
    assert kill.calls[0] == (555, signal.SIGTERM)


def test_both_heartbeat_timestamps_are_reset_to_the_start_of_supervision():
    """C-1010: the silence window is measured from the start of the run, not from `Heartbeat` construction.

    A caller that built the `Heartbeat` minutes earlier would otherwise hand
    `supervise` a silence window that had already expired.
    """
    clock = _Clock()
    kill = _KillLog(clock)
    hb = _hb(Liveness.SEMANTIC, at=-1_000_000.0)
    proc = FakeProcess(clock, exit_at=START + 3.0, exit_code=0)
    policy = TimeoutPolicy(wall_clock_s=3600, silence_s=120)

    sup = supervise(proc, policy, hb, _OnLine(), clock=clock, kill=kill)

    assert sup.reason is None, "a stale heartbeat must not expire the silence window on the first poll"
    assert hb.last_activity_at == START
    assert hb.last_byte_at == START


# --------------------------------------------------------------------------
# _drain — the byte cap, the read bound and decoding (items 17-23)
# --------------------------------------------------------------------------


def _sink() -> "queue.SimpleQueue[str]":
    return queue.SimpleQueue()


def _drained(sink: "queue.SimpleQueue[str]") -> list[str]:
    out: list[str] = []
    while True:
        try:
            out.append(sink.get_nowait())
        except queue.Empty:
            return out


class _RaisingStream:
    """A pipe whose `readline` fails — a real one cannot be made to fail on demand (E7)."""

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.closed = False

    def readline(self, _size: int = -1) -> bytes:
        raise self._error

    def close(self) -> None:
        self.closed = True


def test_drain_returns_false_on_a_clean_eof_and_decodes_every_line():
    """E7: the drain thread hands decoded lines to `supervise` through the queue."""
    sink = _sink()
    overflowed = _drain(io.BytesIO(b"one\ntwo\nthree\n"), sink, BYTE_CAP)
    entries = _drained(sink)

    assert overflowed is False
    assert all(isinstance(e, str) for e in entries)
    assert [e.rstrip("\n") for e in entries] == ["one", "two", "three"]


def _write_and_close(fd: int, payload: bytes) -> None:
    """Write `payload` into `fd` from a second thread and close it.

    The write is larger than the 64 KiB pipe buffer, so it blocks until the
    drain has consumed the first chunk — which is the whole point: the claim is
    about a pipe, and only a pipe can make the write arrive in pieces.
    """
    with open(fd, "wb", closefd=True) as handle:
        handle.write(payload)


def test_a_write_larger_than_a_pipe_buffer_passes_through_whole():
    """E7: 64 KiB is a pipe buffer, not a line boundary — a line under `READ_BOUND` is never split.

    Over a real `os.pipe()`, because against `io.BytesIO` there is no pipe, no
    64 KiB buffer, and nothing the property could fail on.
    """
    payload = "W" * ((64 << 10) + 1)
    read_fd, write_fd = os.pipe()
    writer = threading.Thread(target=_write_and_close, args=(write_fd, (payload + "\n").encode()), daemon=True)
    writer.start()
    sink = _sink()

    with open(read_fd, "rb", closefd=True) as reader:
        overflowed = _drain(reader, sink, BYTE_CAP)
    writer.join(30.0)
    entries = _drained(sink)

    assert writer.is_alive() is False, "the writer must have finished, or the read was short"
    assert overflowed is False
    assert len(entries) == 1
    assert entries[0].rstrip("\n") == payload


def test_a_line_longer_than_the_read_bound_arrives_split():
    """E7/D-k: an over-long line arrives split and resolves `MALFORMED_OUTPUT` downstream.

    That is the correct answer for a harness emitting a 1 MiB JSON line, and
    cheaper than a framer reassembling unbounded attacker-sized lines in memory.
    """
    payload = "L" * (READ_BOUND + 7)
    sink = _sink()

    overflowed = _drain(io.BytesIO((payload + "\n").encode()), sink, 4 * READ_BOUND)
    entries = _drained(sink)

    assert overflowed is False
    assert len(entries) == 2
    assert len(entries[0]) == READ_BOUND
    assert "".join(entries).rstrip("\n") == payload


def test_the_byte_cap_is_enforced_before_the_enqueue():
    """E7: the over-cap line is never handed on, so the queue is bounded by the cap.

    A small injected cap stands in for the shipped 8 MiB one — the boundary is
    the same and the fixture is not 8 MiB of memory.
    """
    sink = _sink()
    source = b"aaaaaaaaaa\nbbbbbbbbbb\ncccccccccc\n"  # three 11-byte lines

    overflowed = _drain(io.BytesIO(source), sink, 22)
    entries = _drained(sink)

    assert overflowed is True
    assert entries == ["aaaaaaaaaa\n", "bbbbbbbbbb\n"]
    assert not any("cccccccccc" in e for e in entries), "the over-cap line must never be enqueued"
    assert sum(len(e.encode()) for e in entries) <= 22


def test_the_line_ceiling_stops_the_drain_independently_of_the_byte_cap():
    """A4: the byte cap bounds the stream; `MAX_LINES` bounds the objects the stream becomes.

    `MAX_LINES + 1` two-byte lines is a quarter of a megabyte of stream — nowhere
    near `BYTE_CAP` — but at the shipped cap the same shape is 4.19 M `str`
    objects and a measured ~320 MiB of RSS, which under a CI memory cgroup is an
    OOM-kill of nox and a review that never runs.
    """
    sink = _sink()

    overflowed = _drain(io.BytesIO(b"x\n" * (MAX_LINES + 1)), sink, BYTE_CAP)
    entries = _drained(sink)

    assert overflowed is True
    assert len(entries) == MAX_LINES
    assert sum(len(e.encode()) for e in entries) < BYTE_CAP, "the byte cap was never in play"


def test_the_shipped_output_ceilings_are_the_contract_literals():
    """C-1009/E7: 8 MiB captured output and a 1 MiB read bound, both named in the record.

    `MAX_LINES` derives from `BYTE_CAP` and never from `_drain`'s `cap`
    argument, so a test's small injected cap cannot move the object ceiling.
    """
    assert BYTE_CAP == 8 << 20
    assert READ_BOUND == 1 << 20
    assert MAX_LINES == BYTE_CAP // 64


def test_invalid_utf8_decodes_with_replacement_rather_than_raising():
    """E7: harness output is untrusted bytes — a text-mode pipe would raise inside the thread."""
    sink = _sink()

    overflowed = _drain(io.BytesIO(b"good\n\xff\xfe\nafter\n"), sink, BYTE_CAP)
    entries = _drained(sink)

    assert overflowed is False
    assert len(entries) == 3
    assert "�" in entries[1]
    assert entries[2].rstrip("\n") == "after"


def test_interleaved_partial_writes_keep_their_order_and_their_raw_text():
    """C-1009/E7: one merged pipe carries the whole stream in order, and the raw text is retained.

    Classifying the spliced result as `MALFORMED_OUTPUT`/`indeterminate` is
    WP6's job; what the drain owes is ordering and retention.
    """
    source = b'{"a":1}\nwarn: half{"b":2}\n'
    sink = _sink()

    overflowed = _drain(io.BytesIO(source), sink, BYTE_CAP)
    entries = _drained(sink)

    assert overflowed is False
    assert "".join(entries) == source.decode()


@pytest.mark.parametrize(("source", "cap", "expected"), [(b"a\nb\n", BYTE_CAP, False), (b"aaaa\nbbbb\n", 4, True)])
def test_the_stream_is_closed_on_the_way_out(source, cap, expected):
    """E7: closed on both the EOF path and the cap path — the drain owns the pipe it was handed."""
    stream = io.BytesIO(source)

    assert _drain(stream, _sink(), cap) is expected
    assert stream.closed is True


def test_a_read_error_propagates_out_of_drain_so_the_thread_can_record_it():
    """E7: a dead drain thread becomes `collector_failure`, which `supervise` reads on every poll."""
    boom = OSError("torn pipe")
    stream = _RaisingStream(boom)

    with pytest.raises(OSError, match="torn pipe"):
        _drain(cast("IO[bytes]", stream), _sink(), BYTE_CAP)


# --------------------------------------------------------------------------
# _kill_group (items 24-25)
# --------------------------------------------------------------------------


@pytest.fixture
def spawn_child():
    """Start real children and guarantee every one is signalled and reaped.

    The cleanup runs even when the code under test raises — a stub phase must
    not leave a `sleep 30` behind for every test that touches a real process.
    """
    started: list[subprocess.Popen[bytes]] = []

    def start(code: str) -> subprocess.Popen[bytes]:
        # A fixed argv of this interpreter, never a shell.
        proc = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        started.append(proc)
        return proc

    yield start

    for proc in started:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
        if proc.stdout is not None and not proc.stdout.closed:
            proc.stdout.close()


def test_kill_group_takes_down_a_real_process_group(spawn_child):
    """C-1009: `start_new_session=True` makes the child its own group, so the kill reaps grandchildren."""
    proc = spawn_child("import time; time.sleep(30)")
    assert os.getpgid(proc.pid) == proc.pid, "the child leads its own session"

    _kill_group(proc.pid, signal.SIGKILL)

    assert proc.wait(timeout=10) == -signal.SIGKILL


def test_kill_group_swallows_esrch_because_a_race_with_the_reap_is_normal(monkeypatch):
    """C-1009: a race between the liveness poll and the signal is normal, not an error."""
    monkeypatch.setattr(os, "killpg", lambda *_a: (_ for _ in ()).throw(ProcessLookupError(3, "No such process")))

    assert _kill_group(4321, signal.SIGTERM) is None


def test_kill_group_does_not_swallow_a_failure_that_is_not_esrch(monkeypatch):
    """C-1009: only `ESRCH` is a race — a refused signal is a real failure and must not be hidden."""
    monkeypatch.setattr(os, "killpg", lambda *_a: (_ for _ in ()).throw(PermissionError(1, "Operation not permitted")))

    with pytest.raises(PermissionError):
        _kill_group(4321, signal.SIGTERM)


# --------------------------------------------------------------------------
# SubprocessProcess / SubprocessRunner over real children (items 26-30)
# --------------------------------------------------------------------------


class _FakeChild:
    """A `_Child` whose pipe fails on demand (E7): a real pipe's `readline` cannot be made to."""

    def __init__(self, error: Exception, *, pid: int = 777, exit_code: int = 0) -> None:
        self.pid = pid
        self.stdout = cast("IO[bytes]", _RaisingStream(error))
        self._exit_code = exit_code

    def wait(self, timeout: float | None = None) -> int:
        _ = timeout
        return self._exit_code

    def kill(self) -> None:
        return None


class _NoPipeChild:
    """A `_Child` whose `stdout` is `None` — the protocol permits it, so the wrapper must."""

    def __init__(self, *, pid: int = 888, exit_code: int = 3) -> None:
        self.pid = pid
        self.stdout: IO[bytes] | None = None
        self._exit_code = exit_code

    def wait(self, timeout: float | None = None) -> int:
        _ = timeout
        return self._exit_code

    def kill(self) -> None:
        return None


class _ScriptedChild:
    """A `_Child` over an in-memory stream, recording whether it was killed and reaped.

    The route to the wrapper's `cap=` knob without an 8 MiB fixture, and to the
    constructor's own failure path, where a child that has no `Process` object
    yet has nothing else in existence that could reap it.
    """

    def __init__(self, payload: bytes = b"", *, pid: int = 666, exit_code: int = 0) -> None:
        self.pid = pid
        self.stdout = cast("IO[bytes]", io.BytesIO(payload))
        self._exit_code = exit_code
        self.waits = 0
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        _ = timeout
        self.waits += 1
        return self._exit_code

    def kill(self) -> None:
        self.killed = True


class _LateLineChild:
    """A `_Child` whose last line becomes readable only once `wait` has been called.

    A real child loses the `wait`/drain race only occasionally, so a real-child
    test passes whether or not `wait` joins the thread. Here it cannot: the line
    is produced after the reap, and behind a delay wide enough that an unjoined
    `wait` provably returns first.
    """

    def __init__(self, line: bytes, *, pid: int = 999, exit_code: int = 0) -> None:
        self.pid = pid
        self._exit_code = exit_code
        self._line = line
        self._reaped = threading.Event()
        self._sent = False
        self.stdout = cast("IO[bytes]", self)

    def readline(self, _size: int = -1) -> bytes:
        if self._sent:
            return b""
        self._reaped.wait(30.0)
        self._sent = True
        time.sleep(0.05)
        return self._line

    def close(self) -> None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        _ = timeout
        self._reaped.set()
        return self._exit_code

    def kill(self) -> None:
        return None


class _ExplodingThread:
    """A `threading.Thread` whose `start` fails — `RLIMIT_NPROC`, or interpreter shutdown."""

    def __init__(self, **_kwargs: object) -> None:
        return None

    def start(self) -> None:
        raise RuntimeError("can't start new thread")


def test_a_real_child_is_drained_reaped_and_reported(spawn_child):
    """E7: the concrete wrapper is covered against a real, harness-free child, not a pragma."""
    popen = spawn_child("import sys\nfor i in range(3):\n    print(i, flush=True)\n")
    proc = SubprocessProcess(popen)

    assert proc.pid == popen.pid
    assert proc.wait(10.0) == 0
    assert [line.rstrip("\n") for line in proc.lines(0.0)] == ["0", "1", "2"]
    assert proc.collector_failure is None
    assert proc.overflowed is False


def test_lines_returns_empty_without_blocking_past_its_timeout(spawn_child):
    """C-1015: the wait is against the queue, never against the child — every deadline depends on it."""
    popen = spawn_child("import time\ntime.sleep(30)\n")
    proc = SubprocessProcess(popen)

    started = time.monotonic()
    batch = proc.lines(0.05)
    elapsed = time.monotonic() - started

    assert batch == ()
    assert elapsed < 5.0, "a poll that blocks on the child makes the silence timeout unenforceable"


def test_wait_joins_the_drain_thread_so_no_line_is_lost():
    """C-1024: a non-`None` `wait` implies every enqueued line is retrievable by a later `lines(0.0)`.

    Driven through a child whose final line only becomes readable after the
    reap, so the guarantee is what makes this pass — not a race a real child
    happens to win. Dropping the `JOIN_S` join leaves the thread alive and the
    line unqueued.
    """
    final = b'{"result": "final"}\n'
    proc = SubprocessProcess(_LateLineChild(final))

    assert proc.wait(10.0) == 0
    assert proc.lines(0.0) == (final.decode(),), "the last line is the harness's result object"
    assert proc._thread.is_alive() is False, "`wait` returned a status, so the drain thread is done"


def test_a_failing_pipe_becomes_collector_failure_rather_than_a_crash():
    """E7: a drain thread that dies is an out-of-band signal `supervise` reads, never an exception."""
    boom = OSError("pipe torn from under the drain thread")
    proc = SubprocessProcess(_FakeChild(boom))

    assert proc.wait(5.0) == 0
    assert proc.collector_failure is boom
    assert proc.pid == 777


def test_a_child_without_a_pipe_reaches_eof_at_once_and_still_reports_its_status():
    """`_Child.stdout` is `IO[bytes] | None`: `None` is an immediately-closed stream, not a crash.

    The drain thread still starts and still ends cleanly, so every other member
    behaves as it does for a child that simply wrote nothing.
    """
    proc = SubprocessProcess(_NoPipeChild())

    assert proc.wait(5.0) == 3
    assert proc.lines(0.0) == ()
    assert proc.collector_failure is None
    assert proc.overflowed is False


def test_the_wrapper_flags_overflow_through_the_cap_it_was_constructed_with():
    """E7 through the concrete wrapper, not through `_drain` alone.

    `overflowed` is the out-of-band signal `supervise` polls; proving the cap on
    `_drain` and on a `FakeProcess` leaves the assignment between them untested,
    and the documented `cap=` knob is the only route to it without 8 MiB of
    fixture.
    """
    child = _ScriptedChild(b"aaaaaaaaaa\nbbbbbbbbbb\ncccccccccc\n")
    proc = SubprocessProcess(child, cap=22)

    assert proc.wait(5.0) == 0
    assert proc.overflowed is True
    assert [line.rstrip("\n") for line in proc.lines(0.0)] == ["aaaaaaaaaa", "bbbbbbbbbb"]
    assert proc.collector_failure is None


def test_a_drain_thread_that_cannot_start_kills_and_reaps_the_child(monkeypatch):
    """`spawn` has already created the `Popen` by the time the thread starts.

    Under thread exhaustion the exception escapes the constructor, no `Process`
    object comes into existence, and nothing is left that could `wait` or `kill`
    the child — it would outlive the review inside a worktree the caller is
    about to remove.
    """
    monkeypatch.setattr(runner.threading, "Thread", _ExplodingThread)
    child = _ScriptedChild(b"never read\n")

    with pytest.raises(RuntimeError, match="can't start new thread"):
        SubprocessProcess(child)

    assert child.killed is True, "a child with no wrapper has nothing else that could reap it"
    assert child.waits == 1, "killed and then reaped, not left as a zombie"


def test_wait_reports_none_while_the_child_is_still_running(spawn_child):
    """C-1015: `wait` is bounded by its timeout — a live child yields `None`, never a block.

    `supervise` polls exit with `wait(0.0)` on every pass, so a `wait` that
    blocked past its timeout would make every deadline in the module advisory.
    """
    popen = spawn_child("import time\ntime.sleep(30)\n")
    proc = SubprocessProcess(popen)

    started = time.monotonic()
    status = proc.wait(0.2)
    elapsed = time.monotonic() - started

    assert status is None
    assert elapsed < 5.0, "a bounded wait must not sit on the child past its timeout"


# --------------------------------------------------------------------------
# D-ac: the two lifetime holes the process group does not close, pinned as the
# accepted residual they are. Both run against a real fork, because the whole
# claim is about what the kernel does with an inherited descriptor and with a
# process group — a fake would pin the fake.
# --------------------------------------------------------------------------

_ORPHAN = """\
import os, sys, time
pidfile, mode, parent = sys.argv[1], sys.argv[2], sys.argv[3]
if os.fork() == 0:
    if mode == "setsid":
        os.setsid()
    tmp = pidfile + ".part"
    with open(tmp, "w") as fh:
        fh.write(str(os.getpid()))
    os.replace(tmp, pidfile)
    time.sleep(120)
    os._exit(0)
print("finding", flush=True)
if parent == "sleep":
    time.sleep(120)
os._exit(0)
"""
"""Fork a grandchild that keeps the inherited merged pipe open after its parent is gone.

The grandchild never writes to the pipe, so the only thing the drain thread can
still be waiting on is the EOF it is withholding; the parent writes exactly one
line first, so the `lines(0.0)` tail guarantee has something to be about.

`mode` picks which D-ac hole the grandchild escapes through (`backgrounded`
stays in the group, `setsid` leaves it); `parent` picks whether the child exits
cleanly — the path on which no signal is issued at all — or waits to be killed.
"""


def _await_pid(pidfile: Path, deadline_s: float = 10.0) -> int:
    """Block until the forked grandchild has published its pid, then return it."""
    limit = time.monotonic() + deadline_s
    while time.monotonic() < limit:
        try:
            return int(pidfile.read_text())
        except (FileNotFoundError, ValueError):
            time.sleep(0.01)
    raise AssertionError(f"the grandchild never published a pid to {pidfile}")


def _alive(pid: int) -> bool:
    """Whether `pid` still exists. The grandchild is reparented, so it is never a zombie here."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _gone_within(pid: int, deadline_s: float) -> bool:
    """Whether `pid` disappears inside `deadline_s`. Signal delivery is asynchronous, so poll."""
    limit = time.monotonic() + deadline_s
    while time.monotonic() < limit:
        if not _alive(pid):
            return True
        time.sleep(0.01)
    return False


def _sweep(pids: Sequence[int]) -> None:
    """Kill whatever the test may have left running. A test for a process leak must not be one."""
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_join_s_is_the_stamped_five_seconds():
    """D-ac: the bound below is `JOIN_S`-relative, so the literal itself needs its own pin.

    `runner.py`'s own docstring states this number to an operator — and it is the
    only text that does; the skill body and `nox/README.md` document the wall and
    silence bounds, not the join. Re-tuning it silently would keep every relative
    assertion green while changing the guarantee that docstring makes.
    """
    assert JOIN_S == 5.0


def test_a_pipe_holding_grandchild_bounds_wait_by_join_s_and_still_survives(tmp_path):
    """D-ac: `JOIN_S` is the whole of v1's guarantee — nox returns on time, the survivor is not killed.

    The child exits cleanly, so no rung of the kill ladder ever fires, and the
    grandchild it left behind holds the write end of the merged pipe: the drain
    thread's `readline` cannot reach EOF however dead the child is. What must
    hold is the bound, not the reaping — `wait` returns after `JOIN_S` and
    abandons the daemon thread instead of sitting on a 120 s sleep — and the
    tail guarantee must survive it: a line queued before the exit is still
    retrievable after the join was abandoned, or a harness could suppress its
    own findings by backgrounding a pipe-holder on the way out.

    The lower bound is the anti-vacuity check: it fails if the grandchild did
    not really wedge the thread, which would leave the upper bound proving
    nothing.
    """
    pidfile = tmp_path / "orphan.pid"
    inv = Invocation(
        argv=(sys.executable, "-c", _ORPHAN, str(pidfile), "backgrounded", "exit"),
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", "")},
    )
    proc = SubprocessRunner().spawn(inv)
    orphan = None
    try:
        orphan = _await_pid(pidfile)
        started = time.monotonic()
        status = proc.wait(JOIN_S + 60.0)
        elapsed = time.monotonic() - started

        assert status == 0, "the child exited cleanly; only its descendant is still around"
        assert elapsed >= JOIN_S - 0.1, "the grandchild did not hold the pipe, so the bound proves nothing"
        assert elapsed < JOIN_S + 10.0, f"`wait` outran `JOIN_S` by {elapsed - JOIN_S:.1f}s behind a held pipe"
        assert any(thread.name == f"nox-drain-{proc.pid}" and thread.is_alive() for thread in threading.enumerate()), (
            "the wedged drain thread is abandoned as a daemon, not joined to completion"
        )
        assert proc.lines(0.0) == ("finding\n",), "an abandoned join must not cost the caller a queued line"
        assert _alive(orphan), "D-ac accepts the survivor: v1 bounds nox's own return, never the survivor's lifetime"
    finally:
        _sweep([pid for pid in (orphan,) if pid is not None] + [proc.pid])


@pytest.mark.parametrize(
    ("mode", "survives"),
    [("backgrounded", False), ("setsid", True)],
    ids=["in-group grandchild dies", "setsid grandchild escapes"],
)
def test_the_group_kill_reaches_the_group_and_nothing_outside_it(tmp_path, spawn_child, mode, survives):
    """E17: the group signal reaches every descendant *still in that group* — and no others.

    Both halves of the corrected sentence, on the one path where a signal is
    issued at all. The positive is what makes the process group the right
    primitive; the negative is D-ac's second hole, which no rung of the ladder
    can close, which is why D-ac stamps it rather than deferring a mechanism.
    """
    pidfile = tmp_path / "orphan.pid"
    popen = spawn_child(f"import sys\nsys.argv[1:] = [{str(pidfile)!r}, {mode!r}, 'sleep']\n{_ORPHAN}")
    orphan = None
    try:
        orphan = _await_pid(pidfile)
        assert (os.getpgid(orphan) != os.getpgid(popen.pid)) is survives, "group membership is what decides reach"

        _kill_group(popen.pid, signal.SIGKILL)

        assert popen.wait(timeout=10) == -signal.SIGKILL
        if survives:
            # The leader is already reaped, so the signal has been delivered to
            # everything it was going to reach — there is nothing to wait for.
            assert _alive(orphan), "the group kill cannot reach a descendant that left the group"
        else:
            assert _gone_within(orphan, 10.0), "a descendant still in the group is reached by the signal"
    finally:
        _sweep([pid for pid in (orphan,) if pid is not None])


_SPAWN_PROBE = """\
import os, sys
print("stdin:" + repr(sys.stdin.read()), flush=True)
print("ids:%d:%d" % (os.getpid(), os.getpgid(0)), flush=True)
print("cwd:" + os.path.realpath(os.getcwd()), flush=True)
print("marker:" + str(os.environ.get("NOX_TEST_MARKER")), flush=True)
print("out", flush=True)
print("err", file=sys.stderr, flush=True)
print("done", flush=True)
"""


def test_spawn_applies_the_c1009_hardening_observably(tmp_path):
    """C-1009: own process group, stdin at EOF, stderr merged into stdout in order.

    The hardening is fixed rather than configurable, so the child's own view of
    it is the assertion — not the kwargs `spawn` happened to pass.
    """
    inv = Invocation(
        argv=(sys.executable, "-c", _SPAWN_PROBE),
        cwd=tmp_path,
        env={"NOX_TEST_MARKER": "present", "PATH": os.environ.get("PATH", "")},
    )

    proc = SubprocessRunner().spawn(inv)
    try:
        assert proc.wait(20.0) == 0
        out = [line.rstrip("\n") for line in proc.lines(0.0)]
    finally:
        proc.wait(20.0)

    fields = dict(line.split(":", 1) for line in out if ":" in line)
    child_pid, child_pgid = (int(part) for part in fields["ids"].split(":"))
    assert child_pid == child_pgid, "start_new_session must make the child its own process-group leader"
    assert fields["stdin"] == "''", "stdin is DEVNULL, so a harness prompting for input gets EOF"
    assert fields["cwd"] == os.path.realpath(tmp_path)
    assert fields["marker"] == "present"
    assert out[-3:] == ["out", "err", "done"], "one pipe carries the whole stream in order"


_FD_PROBE = """\
import os, sys
fd, ino = int(sys.argv[1]), int(sys.argv[2])
try:
    leaked = os.fstat(fd).st_ino == ino
except OSError:
    leaked = False
print("leaked:%s" % leaked, flush=True)
"""


def test_spawn_closes_every_descriptor_the_parent_holds(tmp_path):
    """C-1009: `close_fds=True` — no descriptor nox holds leaks into an untrusted child.

    The parent marks a pipe inheritable and names it in argv; the child compares
    the inode behind that number with the parent's, so an unrelated descriptor
    the interpreter happened to open at the same number cannot pass for a leak.
    """
    read_fd, write_fd = os.pipe()
    os.set_inheritable(read_fd, True)
    try:
        inv = Invocation(
            argv=(sys.executable, "-c", _FD_PROBE, str(read_fd), str(os.fstat(read_fd).st_ino)),
            cwd=tmp_path,
            env={"PATH": os.environ.get("PATH", "")},
        )

        proc = SubprocessRunner().spawn(inv)
        assert proc.wait(20.0) == 0
        out = [line.rstrip("\n") for line in proc.lines(0.0)]
    finally:
        os.close(read_fd)
        os.close(write_fd)

    assert out == ["leaked:False"], "an inheritable parent descriptor must not survive the exec"


_ENV_PROBE = """\
import os
print("names:" + ",".join(sorted(os.environ)), flush=True)
"""


def test_spawn_hands_the_child_the_invocation_env_and_nothing_else(monkeypatch, tmp_path):
    """C-1008: the minimal child environment is the T4 credential-exfiltration control.

    `env=dict(inv.env)`, never a merge over `os.environ`: a harness that
    inherited nox's environment would inherit every token in it.
    """
    monkeypatch.setenv("NOX_PARENT_ONLY_SECRET", "must-not-travel")
    inv = Invocation(argv=(sys.executable, "-c", _ENV_PROBE), cwd=tmp_path, env={"PATH": os.environ.get("PATH", "")})

    proc = SubprocessRunner().spawn(inv)
    assert proc.wait(20.0) == 0
    out = [line.rstrip("\n") for line in proc.lines(0.0)]

    names = out[-1].removeprefix("names:").split(",")
    assert "PATH" in names, "the invocation's own env does reach the child"
    assert "NOX_PARENT_ONLY_SECRET" not in names, "nothing the parent holds is merged in"


_STDIN_PROBE = """\
import sys
print("stdin:" + repr(sys.stdin.read()), flush=True)
"""


def test_spawn_gives_the_child_eof_even_when_the_parents_stdin_has_bytes(tmp_path):
    """C-1009: `stdin=DEVNULL` — a harness prompting for input gets EOF, never nox's own input.

    fd 0 carries real bytes for the duration of the spawn, so an inherited stdin
    is observable: under pytest's own fd capture the inherited descriptor is
    already at EOF and the assertion would hold either way.
    """
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"parent stdin bytes\n")
    os.close(write_fd)
    saved = os.dup(0)
    try:
        os.dup2(read_fd, 0)
        inv = Invocation(
            argv=(sys.executable, "-c", _STDIN_PROBE), cwd=tmp_path, env={"PATH": os.environ.get("PATH", "")}
        )

        proc = SubprocessRunner().spawn(inv)
        assert proc.wait(20.0) == 0
        out = [line.rstrip("\n") for line in proc.lines(0.0)]
    finally:
        os.dup2(saved, 0)
        os.close(saved)
        os.close(read_fd)

    assert out == ["stdin:''"], "an inherited stdin would have handed the child the parent's bytes"


def test_invocation_snapshots_the_env_it_was_handed(tmp_path):
    """C-1008: the constructor is the trust boundary — a frozen dataclass holding a live dict promises nothing."""
    source = {"A": "1"}
    inv = Invocation(argv=("echo",), cwd=tmp_path, env=source)

    source["A"] = "tampered"
    source["B"] = "added"

    assert dict(inv.env) == {"A": "1"}
    with pytest.raises(TypeError):
        cast("dict[str, str]", inv.env)["C"] = "4"


# --------------------------------------------------------------------------
# Static invariants over src/ (items 31-33)
# --------------------------------------------------------------------------


def _src_files() -> list[Path]:
    """Every file git accounts for under `src/`: tracked, plus untracked and not ignored.

    The `git ls-files` route rather than a walk, for the reason
    `test_hygiene.py` gives: `UV_PROJECT_ENVIRONMENT` can put a virtualenv
    anywhere, and a prune list wide enough to dodge it can hide a real hit.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "src"],
        cwd=NOX,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    paths = [NOX / name for name in listed.split("\0") if name]
    assert len(paths) >= 4, f"an empty listing would pass silently: {paths}"
    return paths


def _pragma_comments(path: Path) -> list[tuple[int, str]]:
    """Every `pragma: no cover` that is an actual comment token, as `(lineno, line)`.

    Tokenized rather than grepped: `runner.py`'s module docstring discusses the
    pragma in prose, and a prose mention is not a pragma.
    """
    found: list[tuple[int, str]] = []
    with path.open(encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    with path.open(encoding="utf-8") as handle:
        for token in tokenize.generate_tokens(handle.readline):
            if token.type == tokenize.COMMENT and re.search(r"pragma:\s*no cover", token.string):
                found.append((token.start[0], lines[token.start[0] - 1]))
    return found


def test_exactly_one_no_cover_pragma_and_it_is_on_the_popen_call():
    """C-1015: the pragma budget is one line, and that line is the `subprocess.Popen(` call.

    The seam exists so the escalation logic is on the covered side of it; a
    second pragma anywhere would mean it is not.
    """
    pragmas = [
        (path, line, text) for path in _src_files() if path.suffix == ".py" for line, text in _pragma_comments(path)
    ]

    assert len(pragmas) == 1, f"the pragma budget is exactly one line (C-1015): {[(str(p), n) for p, n, _ in pragmas]}"
    path, lineno, text = pragmas[0]
    assert path.name == "runner.py"
    assert "subprocess.Popen(" in text, f"line {lineno} is not the Popen call: {text!r}"

    tree = ast.parse(path.read_text(encoding="utf-8"))
    spawns = [
        fn
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "SubprocessRunner"
        for fn in node.body
        if isinstance(fn, ast.FunctionDef) and fn.name == "spawn"
    ]
    assert len(spawns) == 1
    assert spawns[0].lineno <= lineno <= (spawns[0].end_lineno or spawns[0].lineno)


def test_subprocess_popen_appears_under_src_only_in_runner():
    """C-1015: `SubprocessRunner.spawn` is the only place a child is created."""
    hits = sorted(p.name for p in _src_files() if p.is_file() and b"subprocess.Popen" in p.read_bytes())
    assert hits == ["runner.py"]


def _posix_portability_offenders(path: Path) -> list[str]:
    """Every E6/D-j violation in `path`, as `<name>@<line>`.

    Two rules, and the second is why this is an AST walk and not a scan of
    module-level lines: `signal.SIGKILL` and `os.killpg` are legal inside a
    function body and illegal at module level, while `sys.platform` is illegal
    *anywhere* — a platform branch in a function body is exactly the half the
    module docstring claims does not exist.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    spans = [
        (node.lineno, node.end_lineno or node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]

    def inside_a_function(lineno: int) -> bool:
        return any(start <= lineno <= end for start, end in spans)

    forbidden = {"killpg", "SIGKILL", "SIGTERM"}
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in forbidden and not inside_a_function(node.lineno):
            offenders.append(f"{node.attr}@{node.lineno}")
        if isinstance(node, ast.ImportFrom) and node.module in {"os", "signal"} and not inside_a_function(node.lineno):
            offenders += [f"{a.name}@{node.lineno}" for a in node.names if a.name in forbidden]
        if isinstance(node, ast.Attribute) and node.attr == "platform" and isinstance(node.value, ast.Name):
            offenders += [f"sys.platform@{node.lineno}"] if node.value.id == "sys" else []
        if isinstance(node, ast.ImportFrom) and node.module == "sys":
            offenders += [f"sys.{a.name}@{node.lineno}" for a in node.names if a.name == "platform"]
    return offenders


def test_runner_holds_no_module_level_posix_primitive_and_no_platform_branch(tmp_path):
    """E6/D-j: the module must import on a non-POSIX host and fail at the documented gate instead.

    `nox.api.review()` refuses `win32` before any spawn, so nothing here
    branches on the platform — an import-time `signal.SIGKILL` would move the
    failure from that gate to the import, and a `sys.platform` test anywhere,
    function bodies included, would move the decision out of the gate entirely.
    """
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import signal\nimport sys\n\nSIG = signal.SIGKILL\n\n\ndef f():\n    return sys.platform == 'win32'\n",
        encoding="utf-8",
    )
    assert sorted(_posix_portability_offenders(planted)) == ["SIGKILL@4", "sys.platform@8"], "the scan is not vacuous"

    assert _posix_portability_offenders(NOX / "src" / "nox" / "runner.py") == []


# ── The stdin prompt channel (C-1009, C-1028) ────────────────────────────────


def test_spawn_hands_the_child_the_stdin_path_as_its_standard_input(tmp_path):
    """C-1028: the second prompt channel — a nox-owned file, not the parent's terminal.

    The parent's own fd 0 carries real bytes for the duration of the spawn, so
    "the child read the FILE" and "the child read whatever nox inherited" are
    distinguishable rather than both spelled `''`.
    """
    prompt = tmp_path / "prompt.md"
    prompt.write_text("the rendered review prompt", encoding="utf-8")
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"parent stdin bytes\n")
    os.close(write_fd)
    saved = os.dup(0)
    try:
        os.dup2(read_fd, 0)
        inv = Invocation(
            argv=(sys.executable, "-c", _STDIN_PROBE),
            cwd=tmp_path,
            env={"PATH": os.environ.get("PATH", "")},
            stdin_path=prompt,
        )

        proc = SubprocessRunner().spawn(inv)
        assert proc.wait(20.0) == 0
        out = [line.rstrip("\n") for line in proc.lines(0.0)]
    finally:
        os.dup2(saved, 0)
        os.close(saved)
        os.close(read_fd)

    assert out == ["stdin:'the rendered review prompt'"]


def _stdin_inv(tmp_path, path, argv=None):
    """An `Invocation` whose prompt is at `path`."""
    return Invocation(
        argv=(sys.executable, "-c", _STDIN_PROBE) if argv is None else argv,
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", "")},
        stdin_path=path,
    )


def _open_fds() -> set[str]:
    """The parent's open descriptors. `/dev/fd`, not `/proc/self/fd` — macOS is supported (D-j)."""
    return set(os.listdir("/dev/fd"))


def test_spawn_refuses_a_symlinked_stdin_path_rather_than_following_it(tmp_path):
    """C-1009: the prompt file is written at `prepare` and opened at `spawn`, and a harness runs between.

    `adapter.sandbox_probe` is spawned from inside `authorize` — after
    `review_prompt` wrote `prompt.md`, before this open — so a harness has run
    in this workspace by the time the descriptor is taken, and
    `write_nofollow`'s contract says the scratch DIRECTORY is unprotected once
    one has. `authorize` refuses a path whose parent is not the scratch
    directory, so what remains is the final component: a symlink swapped in at
    `prompt.md`, which followed would feed an arbitrary readable file to the
    next harness as its prompt.

    `IsolationError`, not a bare `OSError`: this is a detected tamper, and
    `api._spawn` maps every `OSError` to `ABSENT`, which SD § 7.1 tells a
    consumer to degrade to a graceful skip. The write half of the same defence
    (`write_nofollow`) already raises `IsolationError`.
    """
    secret = tmp_path / "secret"
    secret.write_text("a credential the next harness may not read", encoding="utf-8")
    link = tmp_path / "prompt.md"
    link.symlink_to(secret)

    with pytest.raises(IsolationError) as exc:
        SubprocessRunner().spawn(_stdin_inv(tmp_path, link))

    assert "prompt" in str(exc.value)


def test_spawn_refuses_a_fifo_at_the_stdin_path_instead_of_blocking_forever(tmp_path):
    """`O_NOFOLLOW` refuses a symlink and says nothing about a FIFO, which is the worse shape.

    Opening a FIFO for reading blocks until a writer appears, and this open runs
    in `review()`'s own thread before any `TimeoutPolicy` exists — no deadline
    anywhere would end it. Same attacker precondition as the symlink above, so
    the guard is `S_ISREG` and `O_NONBLOCK` is what lets the open return far
    enough to test it (a no-op on a regular file, so the child's fd is
    unaffected).

    A directory at the same path is the same class with a milder symptom, and is
    refused by the same check.
    """
    fifo = tmp_path / "prompt.md"
    os.mkfifo(fifo)

    with pytest.raises(IsolationError) as exc:
        SubprocessRunner().spawn(_stdin_inv(tmp_path, fifo))

    assert "regular file" in str(exc.value)


def test_spawn_refuses_a_directory_at_the_stdin_path(tmp_path):
    """The other non-regular shape the same `S_ISREG` guard closes."""
    (tmp_path / "prompt.md").mkdir()

    with pytest.raises(IsolationError):
        SubprocessRunner().spawn(_stdin_inv(tmp_path, tmp_path / "prompt.md"))


def test_spawn_reports_a_missing_prompt_file_as_an_isolation_failure(tmp_path):
    """Not `ABSENT`: the harness is installed, and its prompt is what went missing."""
    with pytest.raises(IsolationError):
        SubprocessRunner().spawn(_stdin_inv(tmp_path, tmp_path / "prompt.md"))


def test_spawn_leaks_no_stdin_descriptor_into_the_parent(tmp_path):
    """The parent's fd table is unchanged by a spawn that opened a prompt file."""
    prompt = tmp_path / "prompt.md"
    prompt.write_text("x", encoding="utf-8")

    before = _open_fds()
    proc = SubprocessRunner().spawn(_stdin_inv(tmp_path, prompt, argv=("true",)))
    assert proc.wait(20.0) == 0
    list(proc.lines(0.0))

    assert _open_fds() - before == set()


def test_a_spawn_that_fails_to_start_still_closes_the_stdin_descriptor(tmp_path):
    """The `finally` is the whole point, and branch coverage alone does not prove it.

    Moving the close inside the `try` leaks one descriptor per failed spawn and
    keeps every other test green, because the success path already covers the
    branch. This is the test that fails.
    """
    prompt = tmp_path / "prompt.md"
    prompt.write_text("x", encoding="utf-8")
    inv = _stdin_inv(tmp_path, prompt, argv=(str(tmp_path / "no-such-binary"),))

    before = _open_fds()
    with pytest.raises(OSError):
        SubprocessRunner().spawn(inv)

    assert _open_fds() - before == set()


def test_an_invocation_defaults_to_no_stdin_path(tmp_path):
    """C-1009: DEVNULL stays the default — the argv harnesses declare nothing and get EOF."""
    assert Invocation(argv=("echo",), cwd=tmp_path, env={}).stdin_path is None


def test_a_prompt_refused_for_its_shape_still_closes_the_descriptor_it_opened(tmp_path):
    """The `except BaseException: os.close(fd)` guard, which branch coverage alone does not reach.

    `O_NONBLOCK` is what lets the FIFO open RETURN rather than block, so by the
    time `S_ISREG` refuses, a descriptor is already held. Deleting the guard
    leaks one per refusal and keeps every other test green: the two shape tests
    beside this one assert the refusal and never the fd table, and the success
    path returns the descriptor to `Popen`, which closes it.

    A leak here is not cosmetic. The refusal is the *tamper-detected* path — the
    one an attacker can drive on demand by planting a FIFO or a directory at
    `prompt.md` — so the descriptor it strands is one an attacker chooses how
    many of, against nox's own process, until the table is full and every later
    `os.open` fails as an `OSError` the layer above reads as `ABSENT`.
    """
    fifo = tmp_path / "prompt.md"
    os.mkfifo(fifo)

    before = _open_fds()
    with pytest.raises(IsolationError):
        SubprocessRunner().spawn(_stdin_inv(tmp_path, fifo))

    assert _open_fds() - before == set()
