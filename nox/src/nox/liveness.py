"""Liveness signals and the timeout policy derived from them (C-1010).

A harness that streams structured events tells nox something a harness that
streams raw bytes does not: silence over *events* means stalled, while silence
over *bytes* only means quiet. The timeout policy is therefore a function of
what the harness can actually report, never a single number applied to all
three.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Liveness(StrEnum):
    """What a harness's output stream can testify to about progress."""

    SEMANTIC = "semantic"
    """Structured per-event stream — silence over events is meaningful."""

    BYTE_ACTIVITY = "byte_activity"
    """Raw stdout bytes only — silence is weak evidence, so the bound is wider."""

    PROCESS_ONLY = "process_only"
    """The PID exists and nothing else is known — silence carries no information."""


SILENCE_S: Final[Mapping[Liveness, int | None]] = {
    Liveness.SEMANTIC: 120,
    Liveness.BYTE_ACTIVITY: 300,
    Liveness.PROCESS_ONLY: None,
}
"""The C-1010 policy table, at module level so tests assert it directly.

`None` means silence carries no information and only the wall clock bounds the
run.
"""


@dataclass(slots=True)
class Heartbeat:
    """Progress evidence for one run, updated as output arrives.

    Mutable by design: `supervise()` touches it from the drain loop. Both
    timestamps travel into the `TIMED_OUT` detail, so "noisy but eventless" is
    distinguishable from "dead".

    Attributes:
        kind: What the harness's stream can testify to.
        last_activity_at: `time.monotonic()` of the last SEMANTIC event.
        last_byte_at: `time.monotonic()` of the last output of any kind.
        events: Count of semantic events seen.
    """

    kind: Liveness
    last_activity_at: float
    last_byte_at: float
    events: int = 0

    def touch(self, now: float, *, semantic: bool) -> None:
        """Record output at `now`.

        `semantic=False` updates `last_byte_at` ONLY. It never resets the
        silence clock, which runs over events, not bytes (C-1010).

        Args:
            now: `time.monotonic()` at the moment the output was read.
            semantic: Whether the output was a structured event.
        """
        self.last_byte_at = now
        if semantic:
            self.last_activity_at = now
            self.events += 1


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    """The bounds one run is supervised against.

    Attributes:
        wall_clock_s: Always enforced, whatever the liveness kind.
        silence_s: `None` when silence carries no information (PROCESS_ONLY).
        grace_s: Seconds between SIGTERM and SIGKILL.
    """

    wall_clock_s: int
    silence_s: int | None
    grace_s: float = 5.0

    @classmethod
    def for_kind(cls, kind: Liveness, wall_clock_s: int) -> TimeoutPolicy:
        """Return the policy for `kind`, reading `SILENCE_S` (C-1010).

        Args:
            kind: The harness's liveness signal.
            wall_clock_s: The overall bound, always enforced.

        Returns:
            The policy for that kind.
        """
        return cls(wall_clock_s=wall_clock_s, silence_s=SILENCE_S[kind])
