"""Liveness signals and the C-1010 timeout policy derived from them."""

from dataclasses import FrozenInstanceError, fields
from enum import StrEnum

import pytest

from nox.liveness import SILENCE_S, Heartbeat, Liveness, TimeoutPolicy


def test_liveness_is_a_str_enum_with_three_members():
    assert issubclass(Liveness, StrEnum)
    assert {m.name: m.value for m in Liveness} == {
        "SEMANTIC": "semantic",
        "BYTE_ACTIVITY": "byte_activity",
        "PROCESS_ONLY": "process_only",
    }


def test_silence_policy_table_is_the_c1010_literal():
    assert dict(SILENCE_S) == {
        Liveness.SEMANTIC: 120,
        Liveness.BYTE_ACTIVITY: 300,
        Liveness.PROCESS_ONLY: None,
    }


def test_every_liveness_member_has_a_silence_policy():
    # A new member cannot be added without deciding what its silence means.
    assert set(SILENCE_S) == set(Liveness)


@pytest.mark.parametrize(
    ("kind", "expected_silence"),
    [
        (Liveness.SEMANTIC, 120),
        (Liveness.BYTE_ACTIVITY, 300),
        (Liveness.PROCESS_ONLY, None),
    ],
)
@pytest.mark.parametrize("wall", [1, 900])
def test_for_kind_reads_the_table_and_keeps_the_wall_clock(kind, expected_silence, wall):
    policy = TimeoutPolicy.for_kind(kind, wall)
    assert policy.wall_clock_s == wall
    assert policy.silence_s == expected_silence
    assert policy.grace_s == 5.0


def test_touch_semantic_advances_both_clocks_and_counts_the_event():
    hb = Heartbeat(kind=Liveness.SEMANTIC, last_activity_at=10.0, last_byte_at=10.0)
    hb.touch(25.0, semantic=True)
    assert (hb.last_activity_at, hb.last_byte_at, hb.events) == (25.0, 25.0, 1)


def test_touch_non_semantic_advances_only_the_byte_clock():
    """C-1010's core rule: bytes never reset the silence clock, which runs over events.

    A harness emitting a progress bar or a deprecation warning for two minutes
    is silent, not alive — otherwise the 120 s SEMANTIC window would do nothing
    the 300 s BYTE_ACTIVITY window does not do better.
    """
    hb = Heartbeat(kind=Liveness.SEMANTIC, last_activity_at=10.0, last_byte_at=10.0, events=3)
    hb.touch(25.0, semantic=False)
    assert hb.last_activity_at == 10.0
    assert hb.events == 3
    assert hb.last_byte_at == 25.0


def test_touch_counts_every_semantic_event():
    hb = Heartbeat(kind=Liveness.BYTE_ACTIVITY, last_activity_at=10.0, last_byte_at=10.0)
    hb.touch(11.0, semantic=True)
    hb.touch(12.0, semantic=False)
    hb.touch(13.0, semantic=True)
    assert (hb.events, hb.last_activity_at, hb.last_byte_at) == (2, 13.0, 13.0)


def test_timeout_policy_is_frozen():
    policy = TimeoutPolicy(wall_clock_s=900, silence_s=120)
    with pytest.raises(FrozenInstanceError):
        setattr(policy, "grace_s", 1)  # noqa: B010 — a direct assignment is a type error, not a runtime one


def test_timeout_policy_fields():
    # FrozenInstanceError fires for any attribute name, so the field set is
    # pinned here or not at all.
    assert tuple(f.name for f in fields(TimeoutPolicy)) == ("wall_clock_s", "silence_s", "grace_s")
