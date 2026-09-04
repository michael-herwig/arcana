"""The append-only call log: seven keys, no `raw`, and a `record` that never raises.

C-1018 (what may never reach a durable artifact), C-1021, C-1035.

Every assertion here reads the written file back as text, not as the object that
was handed in: the whole point of C-1021's field list is what lands on disk under
`$XDG_STATE_HOME`, and a credential that reaches the line is a credential a later
`grep` publishes.
"""

import json
import stat
from pathlib import Path

import pytest

from nox import config, log
from nox.config import ConfigError, trust_store_path
from nox.liveness import Heartbeat, Liveness
from nox.log import CALL_LOG_NAME, call_log_path, record
from nox.outcome import NOT_RUN, FailureReason, Finding, Review
from tests.fixtures.repo import make_repo

CREDENTIAL = "AKIAIOSFODNN7EXAMPLE"
"""One distinctive string, seeded into every field the log may not carry."""

WARNING_TEXT = "distinctive-warning-string-that-must-not-be-logged"
"""Seeded into `Review.warnings`, which the log records only the LENGTH of."""

FIELDS = ("timestamp", "harness", "model", "duration_s", "outcome", "cost_usd", "warnings")
"""The six C-1021 names plus the warning count — the whole record, and nothing else."""


def _review(**overrides) -> Review:
    """A completed `Review` with only what a test cares about set."""
    fields: dict[str, object] = {
        "status": "ok",
        "verdict": "approve",
        "findings": (),
        "summary": "",
        "detail": None,
        "raw": "",
        "truncated": False,
        "reason": None,
        "harness": "claude",
        "harness_version": "1.0.0",
        "verified_against": "1.0.0",
        "model": "stub-model-1",
        "model_class": "deep-reasoning",
        "heartbeat": Heartbeat(kind=Liveness.SEMANTIC, last_activity_at=0.0, last_byte_at=0.0),
        "containment": NOT_RUN,
        "duration_s": 1.25,
        "cost_usd": 0.5,
        "warnings": (),
    }
    fields.update(overrides)
    return Review(**fields)  # type: ignore[arg-type]


def _state_dir(tmp_path: Path) -> Path:
    """A user state directory that already exists, so a test about the LINE is not about the mkdir.

    `record` creates the directory itself — `test_record_creates_the_user_state_directory_it_writes_into`
    is the one that asserts it — and every other test here is about what lands
    in the file once there is one.
    """
    directory = tmp_path / "state"
    directory.mkdir()
    return directory


def _lines(state_dir: Path) -> list[str]:
    """Every line the log holds, newline-stripped, in write order."""
    return (state_dir / CALL_LOG_NAME).read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# The record's shape: C-1021
# ---------------------------------------------------------------------------


def test_one_record_carries_exactly_the_seven_documented_keys(tmp_path):
    """C-1021: six named fields plus the warning count — an eighth key is a field nobody bounded."""
    state = _state_dir(tmp_path)
    record(_review(), state_dir=state, timestamp="2026-01-01T00:00:00Z")
    assert tuple(json.loads(_lines(state)[0])) == FIELDS


def test_the_recorded_values_are_the_reviews_own(tmp_path):
    """C-1021: `harness`, `model`, `duration_s` and `cost_usd` are transcribed, not derived."""
    state = _state_dir(tmp_path)
    record(_review(), state_dir=state, timestamp="2026-01-01T00:00:00Z")
    entry = json.loads(_lines(state)[0])
    assert entry["timestamp"] == "2026-01-01T00:00:00Z"
    assert entry["harness"] == "claude"
    assert entry["model"] == "stub-model-1"
    assert entry["duration_s"] == pytest.approx(1.25)
    assert entry["cost_usd"] == pytest.approx(0.5)


def test_an_unresolved_harness_and_an_unresolved_model_are_recorded_as_their_no_evidence_values(tmp_path):
    """C-1021: `""` and `null` are the documented no-evidence values, never a guess."""
    state = _state_dir(tmp_path)
    review = _review(status="error", verdict=None, reason=FailureReason.ABSENT, harness="", model=None, cost_usd=None)
    record(review, state_dir=state, timestamp="2026-01-01T00:00:00Z")
    entry = json.loads(_lines(state)[0])
    assert entry["harness"] == ""
    assert entry["model"] is None
    assert entry["cost_usd"] is None


def test_warnings_is_the_count_and_never_the_warning_strings(tmp_path):
    """C-1021: `len(review.warnings)`, so a warning quoting a path cannot become a durable artifact."""
    state = _state_dir(tmp_path)
    record(_review(warnings=(WARNING_TEXT, "second")), state_dir=state, timestamp="2026-01-01T00:00:00Z")
    written = (state / CALL_LOG_NAME).read_text(encoding="utf-8")
    assert json.loads(_lines(state)[0])["warnings"] == 2
    assert WARNING_TEXT not in written


def test_no_field_that_can_quote_harness_output_reaches_the_log(tmp_path):
    """C-1018/C-1021: `raw`, `summary`, `detail` and a finding body can each carry a credential."""
    state = _state_dir(tmp_path)
    review = _review(
        status="indeterminate",
        verdict=None,
        reason=FailureReason.MALFORMED_OUTPUT,
        raw=f"line one\n{CREDENTIAL}\n",
        summary=f"the diff exposes {CREDENTIAL}",
        detail=f"unparsed: {CREDENTIAL}",
        findings=(Finding(severity="high", title="leak", body=f"see {CREDENTIAL}"),),
    )
    record(review, state_dir=state, timestamp="2026-01-01T00:00:00Z")
    assert CREDENTIAL not in (state / CALL_LOG_NAME).read_text(encoding="utf-8")


def test_outcome_is_ok_for_a_review_that_resolved(tmp_path):
    """C-1021: one greppable field, and `ok` is the word it carries on the success path."""
    state = _state_dir(tmp_path)
    record(_review(), state_dir=state, timestamp="2026-01-01T00:00:00Z")
    assert json.loads(_lines(state)[0])["outcome"] == "ok"


@pytest.mark.parametrize("status", ["error", "indeterminate"])
@pytest.mark.parametrize("reason", [FailureReason.RATE_LIMITED, FailureReason.MALFORMED_OUTPUT])
def test_outcome_joins_status_and_reason_for_every_other_review(tmp_path, status, reason):
    """C-1021: `error:rate_limited` is the line a user greps for after a lockout."""
    state = _state_dir(tmp_path)
    record(
        _review(status=status, verdict=None, reason=reason),
        state_dir=state,
        timestamp="2026-01-01T00:00:00Z",
    )
    assert json.loads(_lines(state)[0])["outcome"] == f"{status}:{reason.value}"


def test_the_log_is_append_only_and_an_earlier_line_is_never_rewritten(tmp_path):
    """C-1021: append-only is the contract, which is why the file is JSON Lines and not a JSON array."""
    state = _state_dir(tmp_path)
    record(_review(harness="claude"), state_dir=state, timestamp="2026-01-01T00:00:00Z")
    first = _lines(state)[0]
    record(_review(harness="codex"), state_dir=state, timestamp="2026-01-02T00:00:00Z")
    written = _lines(state)
    assert len(written) == 2
    assert written[0] == first
    assert json.loads(written[1])["harness"] == "codex"


# ---------------------------------------------------------------------------
# Where it lives: C-1021, T4b
# ---------------------------------------------------------------------------


def test_record_creates_the_user_state_directory_it_writes_into(tmp_path):
    """C-1021: `O_CREAT` creates a file, not its parent, and nothing else in nox creates that parent.

    `trust_store_path` only resolves the directory and D-w means nothing writes
    `trust.json` either, so without the `mkdir` here the very first review of a
    machine's life fails `ENOENT`, `record`'s own `suppress` eats it, and C-1021
    ships inert on every real machine while every test that pre-creates the
    directory passes.
    """
    state = tmp_path / "never-created" / "state"
    record(_review(), state_dir=state, timestamp="2026-01-01T00:00:00Z")
    assert json.loads(_lines(state)[0])["harness"] == "claude"


def test_the_created_state_directory_is_reachable_only_by_its_owner(tmp_path):
    """C-1021: it holds the trust store and a record of which harnesses this machine drives."""
    state = tmp_path / "fresh-state"
    record(_review(), state_dir=state)
    assert stat.S_IMODE(state.stat().st_mode) == 0o700


def test_the_log_file_is_created_readable_only_by_its_owner(tmp_path):
    """C-1021: the line records which harnesses a machine's owner drives and when."""
    state = _state_dir(tmp_path)
    record(_review(), state_dir=state)
    assert stat.S_IMODE((state / CALL_LOG_NAME).stat().st_mode) == 0o600


def test_the_log_sits_beside_the_trust_store(tmp_path):
    """C-1021: derived from `trust_store_path` so the T4b belt cannot be forgotten in a second resolver."""
    state = _state_dir(tmp_path)
    resolved = call_log_path(state, repo=tmp_path / "repo")
    assert resolved.parent == trust_store_path(state, repo=tmp_path / "repo").parent
    assert resolved.name == CALL_LOG_NAME


def test_call_log_path_honours_an_explicit_state_dir(tmp_path):
    """C-1021: the caller's override wins outright, exactly as it does for the trust store."""
    state = _state_dir(tmp_path)
    assert call_log_path(state) == state / CALL_LOG_NAME


def test_call_log_path_refuses_a_state_directory_the_repository_under_review_controls(tmp_path, monkeypatch):
    """T4b: `repo=` is what makes an `$XDG_STATE_HOME` inside the branch fall back to the passwd home."""
    repo = make_repo(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(repo.toplevel / "state"))
    assert not call_log_path(repo=repo.toplevel).is_relative_to(repo.toplevel)


# ---------------------------------------------------------------------------
# It never raises: C-1021
# ---------------------------------------------------------------------------


def test_record_swallows_an_unusable_state_directory(tmp_path):
    """C-1021: the review is the product and the log is bookkeeping — an `OSError` may not surface."""
    blocked = tmp_path / "state-is-a-file"
    blocked.write_text("not a directory\n")
    assert record(_review(), state_dir=blocked) is None
    assert blocked.read_text() == "not a directory\n"


def test_record_swallows_a_config_error_from_the_state_directory(tmp_path, monkeypatch):
    """C-1021: the easy-to-miss one — `call_log_path` reaches `trust_store_path`, which raises."""
    repo = make_repo(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(repo.toplevel / "state"))

    def _no_passwd_entry() -> Path:
        raise ConfigError("no usable home directory")

    monkeypatch.setattr(config, "_passwd_home", _no_passwd_entry)
    assert record(_review(), repo=repo.toplevel) is None


def test_the_log_is_opened_nofollow_so_a_planted_symlink_is_not_written_through(tmp_path):
    """C-1021: without `O_NOFOLLOW` a symlink at the log path makes every review an append as the user."""
    state = _state_dir(tmp_path)
    target = tmp_path / "victim"
    target.write_text("")
    (state / CALL_LOG_NAME).symlink_to(target)
    assert record(_review(), state_dir=state) is None
    assert target.read_text() == ""


def test_the_log_module_exports_only_its_documented_surface():
    """C-1021: `CALL_LOG_NAME`, `call_log_path` and `record` — the mode constant stays private."""
    assert sorted(log.__all__) == ["CALL_LOG_NAME", "call_log_path", "record"]
