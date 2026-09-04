"""The result vocabulary: tri-state status, failure reasons, containment, review."""

from dataclasses import MISSING, FrozenInstanceError, fields, replace
from typing import get_args

import pytest

from nox.capability import Enforcement
from nox.liveness import Heartbeat, Liveness
from nox.outcome import (
    NOT_RUN,
    Containment,
    FailureReason,
    Finding,
    Mechanism,
    NoxError,
    Review,
    Severity,
    Status,
    Verdict,
)


def _heartbeat() -> Heartbeat:
    return Heartbeat(kind=Liveness.SEMANTIC, last_activity_at=0.0, last_byte_at=0.0)


def _review(
    status: Status = "ok",
    verdict: Verdict | None = "approve",
    reason: FailureReason | None = None,
    *,
    containment: Containment = NOT_RUN,
    warnings: tuple[str, ...] = (),
    heartbeat: Heartbeat | None = None,
    detail: str | None = None,
) -> Review:
    """Build a valid Review, overriding only the fields under test.

    `Review` is frozen and `__post_init__` is the guard being exercised, so
    every case builds fresh kwargs rather than replacing on an existing one.
    """
    return Review(
        status=status,
        verdict=verdict,
        findings=(),
        summary="",
        detail=detail,
        raw="",
        truncated=False,
        reason=reason,
        harness="claude",
        harness_version="2.1.252",
        verified_against="2.1.252",
        model=None,
        model_class=None,
        heartbeat=_heartbeat() if heartbeat is None else heartbeat,
        containment=containment,
        duration_s=0.0,
        cost_usd=None,
        warnings=warnings,
    )


def test_status_is_the_tri_state():
    # C-1011: indeterminate is a first-class outcome and never collapses to ok.
    assert set(get_args(Status)) == {"ok", "error", "indeterminate"}


def test_severity_is_lowercase_on_the_wire_and_in_python():
    # E1 amends C-1018's title-case vocabulary; the consumer title-cases for display.
    assert set(get_args(Severity)) == {"block", "high", "warn", "suggest"}


def test_verdict_members():
    assert set(get_args(Verdict)) == {"approve", "needs-attention"}


def test_mechanism_members():
    assert set(get_args(Mechanism)) == {"tool-removal", "os-sandbox", "config-deny"}


def test_failure_reason_carries_the_full_closed_member_set():
    # C-1012: the four contract-required states plus the additional members;
    # TIMED_OUT and KILLED are distinct — 143 means *we* killed it.
    assert {m.name for m in FailureReason} == {
        "ABSENT",
        "UNAUTHENTICATED",
        "RATE_LIMITED",
        "MALFORMED_OUTPUT",
        "TIMED_OUT",
        "KILLED",
        "ISOLATION_FAILED",
        "UNSUPPORTED",
        "INVALID_CONFIG",
    }


def test_failure_reason_values_are_lowercase_snake_case():
    assert {m.value for m in FailureReason} == {m.name.lower() for m in FailureReason}


def test_nox_error_is_an_exception():
    assert issubclass(NoxError, Exception)


@pytest.mark.parametrize(
    ("status", "verdict", "reason"),
    [
        ("ok", "approve", None),
        ("ok", "needs-attention", None),
        ("error", None, FailureReason.ABSENT),
        ("indeterminate", None, FailureReason.MALFORMED_OUTPUT),
    ],
)
def test_post_init_accepts_the_consistent_combinations(status, verdict, reason):
    review = _review(status, verdict, reason)
    assert (review.status, review.verdict, review.reason) == (status, verdict, reason)


@pytest.mark.parametrize(
    ("status", "verdict", "reason", "guard"),
    [
        ("ok", None, None, "verdict is set iff"),
        ("ok", "approve", FailureReason.TIMED_OUT, "reason is set iff"),
        # Both invariants are violated; the verdict guard is the one that must
        # answer, or a bare `raises(ValueError)` would let either do the job.
        ("ok", None, FailureReason.TIMED_OUT, "verdict is set iff"),
        ("error", "approve", FailureReason.ABSENT, "verdict is set iff"),
        ("error", "approve", None, "verdict is set iff"),
        ("error", None, None, "reason is set iff"),
        ("indeterminate", "needs-attention", FailureReason.MALFORMED_OUTPUT, "verdict is set iff"),
        ("indeterminate", "needs-attention", None, "verdict is set iff"),
        ("indeterminate", None, None, "reason is set iff"),
    ],
)
def test_post_init_rejects_the_inconsistent_combinations(status, verdict, reason, guard):
    # C-1018: verdict is non-None iff status == "ok".
    # C-1011: reason is non-None iff status != "ok".
    with pytest.raises(ValueError, match=guard):
        _review(status, verdict, reason)


@pytest.mark.parametrize("status", ["approved", "OK", "ok ", "success", ""])
def test_post_init_refuses_a_status_outside_the_tri_state(status):
    """C-1011: `ok = status == "ok"` alone lets an adapter invent a fourth outcome.

    `api._resolve` hands `ParsedOutput.status` straight into `Review` and neither
    type checked domain membership, so `"approved"` satisfied both invariants
    with `verdict=None` and a `reason` set and travelled on to a consumer that
    branches on the word. A refusal rather than a coercion onto `indeterminate`:
    a coerced value reads like an outcome nox classified, and this one is a bug.
    """
    with pytest.raises(ValueError, match="status is one of"):
        _review(status, None, FailureReason.MALFORMED_OUTPUT)  # type: ignore[arg-type]


def test_post_init_refuses_an_invented_status_before_the_two_tri_state_guards():
    # Otherwise a combination that is inconsistent *as well* would be reported as
    # a verdict fault, and the reader would go looking for the wrong bug.
    with pytest.raises(ValueError, match="status is one of"):
        _review("approved", "approve", None)  # type: ignore[arg-type]


def test_post_init_snapshots_the_heartbeat_the_drain_loop_keeps_touching():
    # C-1035's "a snapshot, never the live instance" was docstring convention
    # every caller had to remember; __post_init__ takes the copy itself, so a
    # Review's progress evidence cannot advance after the run ended.
    live = _heartbeat()
    review = _review(heartbeat=live)
    live.touch(99.0, semantic=True)
    assert review.heartbeat is not live
    assert (review.heartbeat.last_activity_at, review.heartbeat.last_byte_at, review.heartbeat.events) == (0.0, 0.0, 0)
    assert review.heartbeat.kind is Liveness.SEMANTIC


def test_require_ok_returns_self_on_ok():
    review = _review()
    assert review.require_ok() is review


def test_require_ok_raises_on_error():
    with pytest.raises(NoxError):
        _review("error", None, FailureReason.ABSENT).require_ok()


def test_require_ok_raises_on_indeterminate():
    # C-1011: indeterminate is not a soft ok — the explicit decision point
    # refuses it exactly as it refuses error.
    with pytest.raises(NoxError):
        _review("indeterminate", None, FailureReason.MALFORMED_OUTPUT).require_ok()


def test_review_carries_warnings_and_model_class_fields():
    # C-1035: warnings is the single home for every non-fatal advisory and is
    # present — possibly empty — on every return path; model_class records what
    # was asked for alongside the resolved model.
    names = {f.name for f in fields(Review)}
    assert {"warnings", "model_class", "model"} <= names
    review = _review()
    assert review.warnings == ()
    assert isinstance(review.warnings, tuple)
    assert _review(warnings=("verified_against mismatch",)).warnings == ("verified_against mismatch",)


@pytest.mark.parametrize("name", ["warnings", "detail"])
def test_review_requires_its_own_account_of_a_run(name):
    # C-1035: "present on every return path" is only true while the field has
    # no default — a `= ()` would let a construction site forget the advisories
    # rather than state there were none, and `detail` is nox's own account of a
    # non-ok outcome, not the harness's.
    field = {f.name: f for f in fields(Review)}[name]
    assert field.default is MISSING
    assert field.default_factory is MISSING


def test_finding_defaults_are_absent_location_and_a_harness_stamp():
    # C-1019: `origin` defaults to "harness" because that is what all but one
    # element of `findings` is — the "nox" stamp marks the C-1026 completeness
    # finding, the single element that is NOT untrusted harness output.
    finding = Finding(severity="warn", title="t", body="b")
    defaults = (
        finding.file,
        finding.line_start,
        finding.line_end,
        finding.confidence,
        finding.recommendation,
        finding.origin,
    )
    assert defaults == (None, None, None, "medium", None, "harness")
    assert Finding(severity="warn", title="t", body="b", origin="nox").origin == "nox"


def test_not_run_establishes_no_enforcement_level():
    # C-1007: absence is not a level. A stood-in "os" here would be a security
    # claim nothing established, and a True below would be a hardening claim.
    assert NOT_RUN.mechanism is None
    assert NOT_RUN.write_enforcement is None
    assert NOT_RUN.network_enforcement is None
    assert NOT_RUN.write_enforcement not in get_args(Enforcement)
    assert NOT_RUN.network_enforcement not in get_args(Enforcement)
    assert NOT_RUN.enforced_read_only is False
    assert NOT_RUN.env_scrubbed is False
    assert NOT_RUN.secrets_suspected is False


def test_not_run_has_empty_path_tuples_and_zero_totals():
    # Empty means never enumerated, not "nothing was hidden": no run happened,
    # and a total is the count that enumeration would have produced.
    assert (NOT_RUN.neutralized, NOT_RUN.omitted, NOT_RUN.filtered) == ((), (), ())
    assert (NOT_RUN.neutralized_total, NOT_RUN.omitted_total, NOT_RUN.filtered_total) == (0, 0, 0)


def test_containment_states_an_untruncated_total_beside_every_capped_list():
    """`Workspace` caps each list at `ENUMERATION_BUDGET`, and the stamp copies the cap.

    A consumer reading the stamp rather than the C-1026 finding saw `len(...)`
    and nothing else, so a repository holding more entries than the budget looked
    complete. A total above its list's length means the rest was never enumerated
    into the stamp — never that it was not there.
    """
    stamp = replace(NOT_RUN, filtered=("docs/host -> /elsewhere",), filtered_total=9)
    assert (len(stamp.filtered), stamp.filtered_total) == (1, 9)


def test_not_run_is_usable_as_a_review_containment():
    assert _review(containment=NOT_RUN).containment is NOT_RUN


def test_containment_has_no_field_defaults_at_all():
    """Every axis is stated at the call site or the `Containment` does not build.

    A default anywhere here is a safety claim a call site never made — that is
    why `NOT_RUN` is a shipped literal rather than `Containment()`.
    """
    for field in fields(Containment):
        assert field.default is MISSING, field.name
        assert field.default_factory is MISSING, field.name


def test_filtered_is_distinct_from_neutralized():
    """C-1043: the same tuple type with opposite consequences.

    `neutralized` entries were dropped by name and cost the reviewer no
    evidence about the change itself; `filtered` entries were dropped by mode
    (a symlink, whose target the prompt carries instead), so part of the change
    was NOT visible.
    """
    containment = replace(NOT_RUN, filtered=("docs/host -> /home/u/.ssh",))
    assert containment.filtered == ("docs/host -> /home/u/.ssh",)
    assert containment.neutralized == ()


def test_finding_is_frozen():
    finding = Finding(severity="warn", title="t", body="b")
    with pytest.raises(FrozenInstanceError):
        setattr(finding, "severity", "other")  # noqa: B010 — a direct assignment is a type error, not a runtime one


def test_finding_fields():
    # FrozenInstanceError fires for any attribute name, so the field set is
    # pinned here or not at all.
    assert tuple(f.name for f in fields(Finding)) == (
        "severity",
        "title",
        "body",
        "file",
        "line_start",
        "line_end",
        "confidence",
        "recommendation",
        "origin",
    )


def test_containment_is_frozen():
    containment = replace(NOT_RUN)
    with pytest.raises(FrozenInstanceError):
        setattr(containment, "mechanism", "other")  # noqa: B010 — direct assignment is a type error, not a runtime one


def test_containment_fields():
    assert tuple(f.name for f in fields(Containment)) == (
        "isolation",
        "neutralized",
        "neutralized_total",
        "omitted",
        "omitted_total",
        "filtered",
        "filtered_total",
        "mechanism",
        "write_enforcement",
        "network_enforcement",
        "enforced_read_only",
        "env_scrubbed",
        "secrets_suspected",
    )


def test_review_is_frozen():
    review = _review()
    with pytest.raises(FrozenInstanceError):
        setattr(review, "status", "other")  # noqa: B010 — a direct assignment is a type error, not a runtime one


def test_review_fields():
    assert tuple(f.name for f in fields(Review)) == (
        "status",
        "verdict",
        "findings",
        "summary",
        "detail",
        "raw",
        "truncated",
        "reason",
        "harness",
        "harness_version",
        "verified_against",
        "model",
        "model_class",
        "heartbeat",
        "containment",
        "duration_s",
        "cost_usd",
        "warnings",
    )
