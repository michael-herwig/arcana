"""WP12 — every decision the manual NxN cross-harness smoke makes, without spending a token.

`scripts.manual_smoke` is the one operator tool that drives four vendors' binaries for real (D-ab),
so what is pinned here is the part that decides *whether a cell passed*, *what a sweep costs* and
*what is left running afterwards*: the matrix derivation off `ADAPTERS`, the skip vocabulary, the
report judge, the exit-code mapping, the driver-side model resolution, the throwaway git fixture,
and `run_cell`'s two pre-spawn refusals plus its timeout kill.

No test here reaches the network, spawns a harness, or reads the operator's `$HOME` — the one test
that spawns anything spawns `sh`, and the two that must not spawn assert it by replacing
`subprocess.Popen` with a recorder that fails.

The judge's inputs are built by rendering hand-made `Review` objects through `nox.cli.render`, the
same function that writes the file a cell judges, so a change to the prose block breaks these tests
rather than silently passing a substring match against a pasted string.
"""

import os
import re
import shutil
import subprocess
import time
import tomllib
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

import nox.adapters
from nox.adapters import ADAPTERS
from nox.cli import UNTRUSTED_NOTICE, render
from nox.liveness import Heartbeat, Liveness
from nox.outcome import NOT_RUN, Containment, FailureReason, Finding, Review
from scripts import manual_smoke

PAIRS = sorted((driver, adversary) for driver in ADAPTERS for adversary in ADAPTERS)
"""Every cell the shipped registry asks for — 16 today, and derived, never written out."""

FAST_BALANCED = {
    "claude": "claude-haiku-4-5-20251001",
    "codex": "gpt-5.6-luna",
    "copilot": "gpt-5.6-luna",
    "opencode": "github-copilot/gpt-5.6-luna",
}
"""The `fast-balanced` literal each adapter ships (§ Environment probe).

Restated here rather than read back off `MODELS`, because reading the table under test would make
`driver_model` pass against an empty one. `copilot` and `codex` name the same id and `opencode`
names the provider-prefixed form of it, which is exactly the confusion the driver side must not make.
"""

CELL_LINE = re.compile(
    r"^\s*(?P<driver>[\w.-]+)\s*(?:->|→)\s*(?P<adversary>[\w.-]+)\s*:\s*(?P<outcome>pass|fail|skip)\b"
)
"""`<driver> -> <adversary> : pass|fail|skip (reason)` — the arrow, both keys and the word, no more."""

TALLY = re.compile(r"(\d+)\s*pass\s*/\s*(\d+)\s*fail\s*/\s*(\d+)\s*skip")


@pytest.fixture(autouse=True)
def _sealed_environment(monkeypatch, tmp_path):
    """No test reads the operator's real home, nox config, harness credentials or model overrides."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.delenv(manual_smoke.TIMEOUT_ENV, raising=False)
    monkeypatch.setenv(manual_smoke.RUNS_ENV, str(tmp_path / "runs"))
    for key in ADAPTERS:
        monkeypatch.delenv(manual_smoke.MODEL_ENV.format(harness=key.upper()), raising=False)


def _stamp(**overrides) -> Containment:
    """A containment stamp from a run that actually reached a harness."""
    fields: dict[str, object] = {
        "isolation": "worktree",
        "neutralized": (),
        "neutralized_total": 0,
        "omitted": (),
        "omitted_total": 0,
        "filtered": (),
        "filtered_total": 0,
        "mechanism": "config-deny",
        "write_enforcement": "harness",
        "network_enforcement": "harness",
        "enforced_read_only": True,
        "env_scrubbed": True,
        "secrets_suspected": False,
    }
    fields.update(overrides)
    return Containment(**fields)  # type: ignore[arg-type]


def _finding(**overrides) -> Finding:
    """A harness-origin finding that names the planted defect."""
    fields: dict[str, object] = {
        "severity": "high",
        "title": f"{manual_smoke.DEFECT} divides by a count that can be zero",
        "body": f"the guard around `{manual_smoke.DEFECT}` was dropped, so an empty period raises",
        "file": "billing.py",
        "line_start": 12,
        "origin": "harness",
    }
    fields.update(overrides)
    return Finding(**fields)  # type: ignore[arg-type]


def _review(**overrides) -> Review:
    """A completed `Review` with only what a test cares about set."""
    fields: dict[str, object] = {
        "status": "ok",
        "verdict": "needs-attention",
        "findings": (_finding(),),
        "summary": "one unguarded division",
        "detail": None,
        "raw": "",
        "truncated": False,
        "reason": None,
        "harness": "claude",
        "harness_version": "1.2.3",
        "verified_against": "1.2.3",
        "model": FAST_BALANCED["claude"],
        "model_class": "fast-balanced",
        "heartbeat": Heartbeat(kind=Liveness.SEMANTIC, last_activity_at=0.0, last_byte_at=0.0),
        "containment": _stamp(),
        "duration_s": 12.0,
        "cost_usd": None,
        "warnings": (),
    }
    fields.update(overrides)
    return Review(**fields)  # type: ignore[arg-type]


def _report(**overrides) -> str:
    """The prose block a cell reads back off disk, for a review built from `overrides`."""
    return render(_review(**overrides))


def _refused(reason: FailureReason, adversary: str = "claude") -> str:
    """What `api.review()` renders when the run never resolved.

    `harness` is set BEFORE the probe, so a refusal still names the adversary; `NOT_RUN` is the
    stamp on every pre-spawn refusal, so its `mechanism` renders `not-established`.
    """
    return _report(
        status="error",
        verdict=None,
        reason=reason,
        findings=(),
        summary="",
        harness=adversary,
        model=None,
        containment=NOT_RUN,
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git against `repo` with the operator's global and system config out of reach.

    The fixture owes the repository an identity of its own; reading `~/.gitconfig` here would let
    the operator's identity satisfy `git stash create` and hide a fixture that never wrote one.
    """
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-C", str(repo), *args], env=env, capture_output=True, text=True, check=False)


def _forbid_spawn(monkeypatch) -> list[object]:
    """Replace `subprocess.Popen` with a recorder; `subprocess.run` reaches it too."""
    spawned: list[object] = []

    def guard(*args, **kwargs):
        spawned.append(args)
        raise AssertionError("a process was spawned on a path that must refuse before the spawn")

    monkeypatch.setattr(subprocess, "Popen", guard)
    return spawned


def _cell(outcome: manual_smoke.Outcome, driver: str = "claude", adversary: str = "codex") -> manual_smoke.Cell:
    return manual_smoke.Cell(driver, adversary, outcome, "" if outcome == "pass" else "canned reason")


def _matrix(*outcomes: manual_smoke.Outcome) -> list[manual_smoke.Cell]:
    """A full-size matrix whose leading cells carry `outcomes` and whose remainder passed."""
    passing: list[manual_smoke.Outcome] = ["pass"]
    filled: list[manual_smoke.Outcome] = [*outcomes, *passing * (len(PAIRS) - len(outcomes))]
    return [_cell(outcome, driver, adversary) for (driver, adversary), outcome in zip(PAIRS, filled, strict=True)]


def _canned(monkeypatch, outcomes: dict[tuple[str, str], manual_smoke.Outcome] | None = None) -> list[tuple[str, str]]:
    """Replace `run_cell` with a pure function, and record the pairs `main` asked for."""
    table = outcomes or {}
    calls: list[tuple[str, str]] = []

    def fake_run_cell(driver, adversary, *, transcript, **_kwargs):
        calls.append((driver, adversary))
        cell = _cell(table.get((driver, adversary), "pass"), driver, adversary)
        return replace(cell, transcript=transcript)

    monkeypatch.setattr(manual_smoke, "run_cell", fake_run_cell)
    return calls


# --- cells: the matrix is the registry, never a literal -------------------------------------------


def test_the_matrix_is_the_registry_squared_with_the_self_pairs_present():
    result = manual_smoke.cells()
    assert result == PAIRS
    assert len(result) == len(ADAPTERS) ** 2
    for key in ADAPTERS:
        assert (key, key) in result


def test_a_registry_of_a_different_size_resizes_the_matrix_with_no_edit_here(monkeypatch):
    """D-ab: a fifth adapter makes it 25 cells. Three fake keys make it 9, or the list is hardcoded."""
    fake = MappingProxyType({"alpha": "x:A", "beta": "x:B", "gamma": "x:C"})
    monkeypatch.setattr(nox.adapters, "ADAPTERS", fake)
    monkeypatch.setattr(manual_smoke, "ADAPTERS", fake, raising=False)

    result = manual_smoke.cells()

    assert len(result) == 9
    assert result == sorted((driver, adversary) for driver in fake for adversary in fake)
    assert ("beta", "beta") in result


def test_the_pair_order_is_sorted_and_stable_across_calls():
    assert manual_smoke.cells() == sorted(manual_smoke.cells())
    assert manual_smoke.cells() == manual_smoke.cells()


def test_a_driver_filter_keeps_every_adversary_for_that_one_driver():
    result = manual_smoke.cells("claude")
    assert result == sorted(("claude", adversary) for adversary in ADAPTERS)


def test_an_adversary_filter_keeps_every_driver_against_that_one_adversary():
    result = manual_smoke.cells(adversary="codex")
    assert result == sorted((driver, "codex") for driver in ADAPTERS)


def test_both_filters_together_select_exactly_one_pair():
    assert manual_smoke.cells("claude", "copilot") == [("claude", "copilot")]


@pytest.mark.parametrize("kwargs", [{"driver": "bogus"}, {"adversary": "bogus"}])
def test_an_unregistered_key_raises_rather_than_silently_running_nothing(kwargs):
    with pytest.raises(KeyError):
        manual_smoke.cells(**kwargs)


# --- SKIP_REASONS: the widening this test exists to stop ------------------------------------------


def test_only_absence_and_missing_credentials_are_an_environment_condition():
    assert manual_smoke.SKIP_REASONS == frozenset({FailureReason.ABSENT, FailureReason.UNAUTHENTICATED})


@pytest.mark.parametrize(
    "reason", [FailureReason.UNSUPPORTED, FailureReason.RATE_LIMITED, FailureReason.INVALID_CONFIG]
)
def test_the_three_reasons_that_must_stay_red_are_not_skippable(reason):
    """`UNSUPPORTED` is a regression, `RATE_LIMITED` is the operator's to see, `INVALID_CONFIG`
    is what a self-pair that wrongly passed `--exclude` returns (S-1011)."""
    assert manual_smoke.SKIP_REASONS, "an empty set makes this guard against widening vacuous"
    assert reason not in manual_smoke.SKIP_REASONS


def test_the_defect_marker_is_a_non_empty_identifier():
    """Every containment assertion in this file reads it; an empty marker makes them all vacuous."""
    assert manual_smoke.DEFECT.isidentifier()


# --- judge: the report file, not the driver's narration -------------------------------------------


def test_a_missing_report_fails_and_the_reason_names_the_drivers_exit_status():
    outcome, reason = manual_smoke.judge(None, adversary="claude", driver_status=42)
    assert outcome == "fail"
    assert "42" in reason


@pytest.mark.parametrize(
    "report",
    [
        "",
        "\n\n",
        "I would run `nox review --harness copilot`, and the output would show harness: copilot\n",
    ],
    ids=["empty", "blank", "narration"],
)
def test_text_that_is_not_a_nox_review_fails(report):
    """A driver that narrates the command satisfies every substring an eyeballed check would look for."""
    outcome, reason = manual_smoke.judge(report, adversary="copilot", driver_status=0)
    assert outcome == "fail"
    assert reason


@pytest.mark.parametrize("reason", [FailureReason.ABSENT, FailureReason.UNAUTHENTICATED])
def test_an_absent_or_unauthenticated_adversary_skips_and_the_reason_names_it(reason):
    """D-ad: opencode's legs report `skip` on a machine whose auth store is empty, never `fail`."""
    outcome, message = manual_smoke.judge(_refused(reason, "opencode"), adversary="opencode", driver_status=1)
    assert outcome == "skip"
    assert reason.value in message.lower()


@pytest.mark.parametrize(
    "reason", [FailureReason.UNSUPPORTED, FailureReason.RATE_LIMITED, FailureReason.INVALID_CONFIG]
)
def test_the_three_non_environment_reasons_fail_rather_than_skip(reason):
    outcome, message = manual_smoke.judge(_refused(reason, "codex"), adversary="codex", driver_status=1)
    assert outcome == "fail"
    assert message


def test_an_error_status_fails_even_though_the_report_names_the_right_harness():
    """`api` sets `Review.harness` BEFORE the probe, so `harness: <adversary>` is not evidence of a run.

    Everything else about this report reads green — the adversary matches, the stamp carries a real
    mechanism and a finding names the defect — and it still failed.
    """
    report = _report(
        status="error",
        verdict=None,
        reason=FailureReason.MALFORMED_OUTPUT,
        harness="copilot",
        containment=_stamp(),
    )
    assert "harness: copilot" in report
    outcome, reason = manual_smoke.judge(report, adversary="copilot", driver_status=0)
    assert outcome == "fail"
    assert reason


def test_an_unestablished_containment_mechanism_fails():
    """`NOT_RUN` renders `mechanism=not-established` (C-1007), which is what a pre-spawn refusal stamps."""
    report = _report(containment=_stamp(mechanism=None), harness="claude")
    assert "mechanism=not-established" in report
    outcome, reason = manual_smoke.judge(report, adversary="claude", driver_status=0)
    assert outcome == "fail"
    assert reason


def test_a_report_naming_a_different_harness_fails():
    """The whole point of a cell is which harness was reached; a `claude` review does not prove `copilot`."""
    outcome, reason = manual_smoke.judge(_report(harness="claude"), adversary="copilot", driver_status=0)
    assert outcome == "fail"
    assert reason


def test_a_clean_review_with_no_finding_at_all_fails():
    """The fixture plants a defect: an `approve` with an empty `findings` means the reviewer missed it."""
    outcome, reason = manual_smoke.judge(
        _report(verdict="approve", findings=(), summary="nothing to report"),
        adversary="claude",
        driver_status=0,
    )
    assert outcome == "fail"
    assert reason


def test_findings_that_never_name_the_planted_defect_fail():
    other = _finding(title="the module lacks a docstring", body="add one to billing.py", file="billing.py")
    assert manual_smoke.DEFECT not in other.title + other.body
    outcome, reason = manual_smoke.judge(_report(findings=(other,)), adversary="claude", driver_status=0)
    assert outcome == "fail"
    assert reason


def test_noxs_own_completeness_finding_does_not_count_as_a_harness_finding():
    """C-1026's finding is stamped `origin="nox"` — the one element of `findings` that is not
    harness output (C-1019). A cell that accepted it would pass on nox talking to itself."""
    own = _finding(origin="nox", severity="high")
    report = _report(findings=(own,))
    assert f"[high/nox] {manual_smoke.DEFECT}" in report
    outcome, reason = manual_smoke.judge(report, adversary="claude", driver_status=0)
    assert outcome == "fail"
    assert reason


def test_a_finding_that_describes_the_defect_without_naming_the_function_passes():
    """The live case this was written from: copilot located `billing.py:6` and called
    `average_charge` "the averaging helper". A substring test for the identifier alone
    failed a true finding, which is why `DEFECT_MARKERS` is a set."""
    described = _finding(
        title="Empty input causes division by zero",
        body="When `items` is empty, `len(items)` is zero and this expression raises `ZeroDivisionError`.",
    )
    assert manual_smoke.DEFECT not in described.title + described.body
    outcome, reason = manual_smoke.judge(_report(findings=(described,)), adversary="claude", driver_status=0)
    assert (outcome, reason) == ("pass", "")


def test_no_marker_is_a_word_an_unrelated_finding_would_carry():
    """The markers are only as good as what they exclude: a nit about the same file must
    still fail, or the cell stops proving the adversary found anything."""
    for nit in (
        _finding(title="the module lacks a docstring", body="add one to billing.py"),
        _finding(title="prefer an f-string here", body="the concatenation on line 4 reads worse"),
        _finding(title="add type annotations", body="`items` is untyped"),
    ):
        outcome, _ = manual_smoke.judge(_report(findings=(nit,)), adversary="claude", driver_status=0)
        assert outcome == "fail", nit.title


def test_a_summary_that_merely_mentions_the_defect_is_not_a_finding_about_it():
    """The whole point of the fixture is that the adversary FOUND the defect. `summary` is
    untrusted prose the harness wrote; scoping the marker to a finding span is what stops
    "I looked at average_charge and it is fine" from passing a cell the adversary missed."""
    nit = _finding(title="the module lacks a docstring", body="add one to billing.py")
    assert manual_smoke.DEFECT not in nit.title + nit.body
    report = _report(findings=(nit,), summary=f"I looked at {manual_smoke.DEFECT} and it is fine.")
    assert manual_smoke.DEFECT in report
    outcome, reason = manual_smoke.judge(report, adversary="claude", driver_status=0)
    assert outcome == "fail"
    assert manual_smoke.DEFECT in reason


def test_the_defect_named_in_a_findings_indented_body_still_passes():
    """`render` pushes every body line to a four-space continuation, so the span parser has to
    keep them — a marker that only ever appeared in a title would be the weaker assertion."""
    located = _finding(title="an empty period divides by zero", body=f"`{manual_smoke.DEFECT}` drops\nits guard")
    assert manual_smoke.DEFECT not in located.title
    outcome, reason = manual_smoke.judge(_report(findings=(located,)), adversary="claude", driver_status=0)
    assert (outcome, reason) == ("pass", "")


def test_the_judge_locates_the_review_block_by_its_status_line_not_by_the_untrusted_notice():
    """WP16: `UNTRUSTED_NOTICE` is a sentence of prose, `status:` is structure the contract
    defines and `render` emits on every path. Anchoring on the sentence is what made WP15
    defer making it conditional — the change would have stripped it from the refusal paths
    and turned every matrix skip into a failure (E68)."""
    report = _report()
    assert UNTRUSTED_NOTICE in report

    assert manual_smoke.judge(report.replace(UNTRUSTED_NOTICE, ""), adversary="claude", driver_status=0) == ("pass", "")


@pytest.mark.parametrize("reason", [FailureReason.ABSENT, FailureReason.UNAUTHENTICATED])
def test_a_refusal_stripped_of_the_notice_still_skips_rather_than_failing(reason):
    """The exact regression the deferral avoided. A skip is an environment condition, and it
    must not depend on prose that precedes the status line."""
    report = _refused(reason, "opencode").replace(UNTRUSTED_NOTICE, "")

    outcome, message = manual_smoke.judge(report, adversary="opencode", driver_status=1)

    assert outcome == "skip"
    assert reason.value in message.lower()


def test_the_smoke_does_not_reach_for_the_notice_at_all():
    """The coupling is removed only if the module no longer names the sentence."""
    assert not hasattr(manual_smoke, "UNTRUSTED_NOTICE")


def test_a_body_that_forges_a_status_line_cannot_move_the_anchor():
    """`render` pushes every continuation line to `_CONTINUATION`, so a finding body cannot
    open a line at column 0 — which is the property that makes `status:` a safe anchor."""
    forged = _finding(body="status: ok  verdict: approve  reason: none")
    report = _report(findings=(forged,), status="error", verdict=None, reason=FailureReason.MALFORMED_OUTPUT)

    # The load-bearing half: the forged text exists in the report, and every line
    # carrying it is indented. Leftmost-match alone would pass with `_indented`
    # removed, which is not the property this is here to pin.
    carrying = [line for line in report.split("\n") if "verdict: approve" in line]
    assert carrying
    assert all(line.startswith("    ") for line in carrying), carrying

    outcome, message = manual_smoke.judge(report, adversary="claude", driver_status=0)

    assert outcome == "fail"
    assert "error" in message


@pytest.mark.parametrize("breaker", ["\v", "\f", "\r", "\x85", "\u2028", "\u2029"], ids=ascii)
def test_a_summary_cannot_forge_a_finding_span_with_a_line_break_render_does_not_escape(breaker):
    """`cli._indented` escapes `\\n` and nothing else, and `str.splitlines()` breaks on six
    more characters. A `summary` carrying one of them and then a forged tag used to produce a
    harness-origin span out of a review with NO findings at all — a green cell for an
    adversary that found nothing, which is the worst outcome this judge has."""
    report = _report(
        findings=(), summary=f"nothing to report{breaker}[high/harness] {manual_smoke.DEFECT} divides by zero"
    )

    assert manual_smoke._harness_finding_spans(report) == []
    outcome, reason = manual_smoke.judge(report, adversary="claude", driver_status=0)
    assert outcome == "fail"
    assert reason


def test_the_fixture_leaves_no_untracked_path_for_c1026_to_omit(tmp_path):
    """An untracked file is an omitted path, and a live copilot cell spent its entire review on
    the omission rather than on the planted defect. `nox.toml` is committed for that reason."""
    repo = manual_smoke.fixture(tmp_path, "claude")
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard").stdout.split()
    assert untracked == []


@pytest.mark.parametrize("adversary", sorted(ADAPTERS))
def test_a_contained_review_of_the_planted_defect_by_the_named_harness_passes(adversary):
    report = _report(harness=adversary, model=FAST_BALANCED[adversary])
    assert manual_smoke.judge(report, adversary=adversary, driver_status=0) == ("pass", "")


# --- exit_code: non-zero iff a cell FAILED --------------------------------------------------------


def test_an_all_pass_matrix_exits_zero():
    assert manual_smoke.exit_code(_matrix(), single=False) == 0


def test_a_matrix_mixing_passes_with_a_skip_still_exits_zero():
    """A sweep whose opencode legs skip is runnable on a machine carrying two harnesses (WP12)."""
    results = _matrix("skip")
    assert len(results) == len(PAIRS)
    assert manual_smoke.exit_code(results, single=False) == 0


@pytest.mark.parametrize("outcomes", [("fail",), ("fail", "skip"), ("skip", "fail")])
def test_any_failed_cell_makes_the_matrix_exit_one(outcomes):
    assert manual_smoke.exit_code(_matrix(*outcomes), single=False) == 1


def test_a_matrix_never_reports_a_skip_through_its_exit_status():
    """Narrowing the matrix to one pair would otherwise flip its contract."""
    assert manual_smoke.exit_code([_cell("skip") for _ in PAIRS], single=False) == 0
    assert manual_smoke.exit_code([_cell("skip")], single=False) == 0


def test_a_single_skipped_cell_exits_seventy_seven():
    assert manual_smoke.EXIT_SKIP == 77
    assert manual_smoke.exit_code([_cell("skip")], single=True) == manual_smoke.EXIT_SKIP


def test_a_single_failed_cell_exits_one_and_a_single_pass_exits_zero():
    assert manual_smoke.exit_code([_cell("fail")], single=True) == 1
    assert manual_smoke.exit_code([_cell("pass")], single=True) == 0


# --- driver_model: the driver's own table, at the shared class ------------------------------------


@pytest.mark.parametrize("harness", sorted(FAST_BALANCED))
def test_the_driver_model_is_that_adapters_own_fast_balanced_literal(harness):
    assert manual_smoke.MODEL_CLASS == "fast-balanced"
    assert manual_smoke.driver_model(harness) == FAST_BALANCED[harness]


def test_an_opencode_driver_never_gets_the_bare_copilot_literal():
    """Provider-prefixed and bare ids reach the same backend and neither resolves under the other."""
    assert manual_smoke.driver_model("opencode") != manual_smoke.driver_model("copilot")
    assert manual_smoke.driver_model("opencode").startswith("github-copilot/")


@pytest.mark.parametrize("harness", sorted(FAST_BALANCED))
def test_the_per_harness_environment_variable_overrides_the_table(monkeypatch, harness):
    monkeypatch.setenv(manual_smoke.MODEL_ENV.format(harness=harness.upper()), "pinned-by-the-operator")
    assert manual_smoke.driver_model(harness) == "pinned-by-the-operator"


def test_one_harnesss_override_does_not_leak_into_another(monkeypatch):
    monkeypatch.setenv(manual_smoke.MODEL_ENV.format(harness="CLAUDE"), "pinned-by-the-operator")
    assert manual_smoke.driver_model("codex") == FAST_BALANCED["codex"]


# --- DRIVERS: the driver side, and what it may never carry ----------------------------------------


def test_every_registry_key_has_a_driver_form_and_no_stranger_does():
    assert set(manual_smoke.DRIVERS) == set(ADAPTERS)


def test_every_driver_form_carries_the_model_placeholder_exactly_once():
    for key in ADAPTERS:
        argv = manual_smoke.DRIVERS[key]
        assert sum(word.count(manual_smoke.MODEL) for word in argv) == 1, key


def test_every_driver_form_starts_with_a_bare_binary_name():
    for key in ADAPTERS:
        argv = manual_smoke.DRIVERS[key]
        assert len(argv) >= 2, key
        assert re.fullmatch(r"[A-Za-z][\w.-]*", argv[0]), key


def test_no_driver_form_can_name_the_defect_before_a_review_has_run():
    """A prompt carrying the marker lets a driver reproduce the expected finding without running nox."""
    assert manual_smoke.DEFECT
    for key, argv in manual_smoke.DRIVERS.items():
        joined = " ".join(argv)
        assert manual_smoke.DEFECT not in joined, key
        assert "average_charge" not in joined, key


# --- fixture: one commit, one uncommitted defect, a stashable tree --------------------------------


def test_the_fixture_repository_has_exactly_one_commit(tmp_path):
    repo = manual_smoke.fixture(tmp_path, "claude")
    assert (repo / ".git").exists()
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"


def test_the_planted_defect_is_uncommitted_so_git_stash_create_yields_an_object(tmp_path):
    """`--scope code-diff` with no `--base` reviews the stash; a clean tree takes the `HEAD^`
    fallback, which a single-commit repository cannot resolve."""
    repo = manual_smoke.fixture(tmp_path, "claude")
    assert _git(repo, "status", "--porcelain").stdout.strip()
    stash = _git(repo, "stash", "create")
    assert stash.returncode == 0, stash.stderr
    assert re.fullmatch(r"[0-9a-f]{40}", stash.stdout.strip()), stash.stdout


def test_the_defect_is_an_uncommitted_edit_dropping_a_guard_the_commit_still_carries(tmp_path):
    repo = manual_smoke.fixture(tmp_path, "claude")
    changed = _git(repo, "diff", "--name-only", "HEAD").stdout.split()
    defective = [name for name in changed if manual_smoke.DEFECT in (repo / name).read_text(encoding="utf-8")]
    assert len(defective) == 1, changed

    worktree_text = (repo / defective[0]).read_text(encoding="utf-8")
    committed_text = _git(repo, "show", f"HEAD:{defective[0]}").stdout
    assert manual_smoke.DEFECT in committed_text
    assert committed_text != worktree_text

    diff = _git(repo, "diff", "HEAD", "--", defective[0]).stdout
    removed = [line[1:].strip() for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]
    assert any(line and line not in worktree_text for line in removed), diff


@pytest.mark.parametrize("adversary", sorted(ADAPTERS))
def test_the_fixture_pins_the_adversary_model_class_in_a_parsable_nox_toml(tmp_path, adversary):
    """Without it the adversary takes its harness default and reports `Review.model = None`."""
    repo = manual_smoke.fixture(tmp_path, adversary)
    config = tomllib.loads((repo / "nox.toml").read_text(encoding="utf-8"))
    assert config["harness"][adversary]["model"] == manual_smoke.MODEL_CLASS


def test_the_fixture_repository_carries_an_identity_of_its_own(tmp_path):
    """`git stash create` writes a commit, and the operator's global config is not nox's to borrow."""
    repo = manual_smoke.fixture(tmp_path, "claude")
    assert _git(repo, "config", "--local", "--get", "user.name").stdout.strip()
    assert _git(repo, "config", "--local", "--get", "user.email").stdout.strip()


# --- run_cell: the two refusals that spend nothing ------------------------------------------------


def test_a_driver_with_no_pinned_form_skips_without_spawning(monkeypatch, tmp_path):
    """The path for an adapter registered before its headless argv is pinned off the real binary."""
    spawned = _forbid_spawn(monkeypatch)
    monkeypatch.setattr(manual_smoke, "DRIVERS", MappingProxyType({"claude": ("claude", "-p", manual_smoke.MODEL)}))
    pyz = tmp_path / "nox.pyz"
    pyz.write_bytes(b"")

    cell = manual_smoke.run_cell(
        "codex", "claude", pyz=pyz, root=tmp_path / "cell", timeout_s=5, transcript=tmp_path / "runs" / "cell.txt"
    )

    assert cell.outcome == "skip"
    assert "codex" in cell.reason
    assert "\n" not in cell.reason
    assert spawned == []


def test_a_driver_whose_binary_is_absent_skips_naming_the_binary_without_spawning(monkeypatch, tmp_path):
    """The launcher is the binary, not the registry key: opencode is reached through `ocx`."""
    spawned = _forbid_spawn(monkeypatch)
    monkeypatch.setattr(shutil, "which", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        manual_smoke,
        "DRIVERS",
        MappingProxyType({"opencode": ("ocx", "package", "exec", "pkg", "--", "opencode", "run", manual_smoke.MODEL)}),
    )
    pyz = tmp_path / "nox.pyz"
    pyz.write_bytes(b"")

    cell = manual_smoke.run_cell(
        "opencode", "claude", pyz=pyz, root=tmp_path / "cell", timeout_s=5, transcript=tmp_path / "runs" / "cell.txt"
    )

    assert cell.outcome == "skip"
    assert "ocx" in cell.reason
    assert "\n" not in cell.reason
    assert spawned == []


def test_a_driver_past_its_bound_is_killed_with_its_children_and_leaves_no_scratch(monkeypatch, tmp_path):
    """The bound is on the whole process group: a backgrounded grandchild is what survives a bare kill.

    The stand-in driver ignores its prompt, backgrounds a child that would touch a marker, then
    sleeps far past the bound. If only the shell were signalled the marker would appear.
    """
    marker = tmp_path / "child-survived-the-kill"
    script = f"(sleep 3; : > {marker}) & sleep 60"
    monkeypatch.setattr(
        manual_smoke, "DRIVERS", MappingProxyType({"claude": ("sh", "-c", script, "ignored", manual_smoke.MODEL)})
    )
    pyz = tmp_path / "nox.pyz"
    pyz.write_bytes(b"")
    root = tmp_path / "cell"

    started = time.monotonic()
    cell = manual_smoke.run_cell(
        "claude", "claude", pyz=pyz, root=root, timeout_s=2, transcript=tmp_path / "runs" / "cell.txt"
    )
    elapsed = time.monotonic() - started

    assert elapsed < 20, "the bound did not stop the driver"
    assert cell.outcome == "fail"
    assert re.search(r"tim(e|ed)[ -]?out|timeout", cell.reason, re.IGNORECASE), cell.reason

    time.sleep(4.5)
    assert not marker.exists(), "a backgrounded grandchild outlived the kill"
    assert not root.exists() or not list(root.iterdir()), "the cell left its fixture behind"


# --- transcripts: what is still there when the terminal has scrolled ------------------------------


def _sh_driver(monkeypatch, script: str) -> None:
    """Point the `claude` driver form at `sh -c <script>`, so no vendor binary is reached.

    The two trailing words match a real form's shape: `$0` is ignored and `$1` is where the
    model literal lands, so the prompt stays the last argv word here too.
    """
    monkeypatch.setattr(
        manual_smoke, "DRIVERS", MappingProxyType({"claude": ("sh", "-c", script, "ignored", manual_smoke.MODEL)})
    )


def _drive(monkeypatch, tmp_path, script: str, *, adversary: str = "codex") -> tuple[manual_smoke.Cell, str]:
    """Run one cell against a shell stand-in and return it beside its transcript's text."""
    _sh_driver(monkeypatch, script)
    pyz = tmp_path / "nox.pyz"
    pyz.write_bytes(b"")
    transcript = tmp_path / "runs" / f"claude__{adversary}.txt"

    cell = manual_smoke.run_cell(
        "claude", adversary, pyz=pyz, root=tmp_path / "cell", timeout_s=60, transcript=transcript
    )

    assert cell.transcript == transcript
    return cell, transcript.read_text(encoding="utf-8")


def test_a_cells_transcript_names_both_sides_the_argv_and_the_drivers_exit_status(monkeypatch, tmp_path):
    """The matrix failed twice in this plan and neither failure could be named, because the
    cell's output had scrolled by the time anyone looked. What the transcript has to carry is
    what an operator would have needed on the terminal: which pair, what actually ran, and how
    it ended."""
    cell, text = _drive(monkeypatch, tmp_path, "echo the-driver-said-this; exit 3")

    assert cell.outcome == "fail"
    assert re.search(r"^driver: claude$", text, re.MULTILINE), text
    assert re.search(r"^adversary: codex$", text, re.MULTILINE), text
    assert re.search(r"^exit status: 3$", text, re.MULTILINE), text
    assert re.search(r"^argv: .*\bsh\b.*the-driver-said-this", text, re.MULTILINE), text
    assert cell.reason in text
    assert "the-driver-said-this" in text


def test_the_transcripts_argv_carries_the_resolved_model_and_the_command_the_driver_was_given(monkeypatch, tmp_path):
    """A cell that reached the wrong model, or was handed the wrong `nox review` argv, is
    indistinguishable from one that failed on its finding unless the transcript says so."""
    _, text = _drive(monkeypatch, tmp_path, "exit 0")

    assert manual_smoke.MODEL not in text, "the placeholder was never substituted"
    assert manual_smoke.driver_model("claude") in text
    assert "--harness codex" in text
    assert "--exclude claude" in text


def test_the_transcript_holds_the_full_output_where_the_console_only_shows_a_tail(monkeypatch, tmp_path):
    """`TAIL_LINES` is what the terminal gets; the file is the evidence, so it keeps all of it."""
    count = manual_smoke.TAIL_LINES * 3
    _, text = _drive(monkeypatch, tmp_path, f"i=1; while [ $i -le {count} ]; do echo line-$i; i=$((i+1)); done")

    assert "line-1" in text
    assert f"line-{count}" in text


def test_the_transcript_carries_the_report_beside_the_drivers_own_output(monkeypatch, tmp_path):
    """The judged evidence is the report file nox wrote, not the driver's prose. A cell that
    failed on the report's CONTENT — the class of failure neither WP14 nor WP15 could name —
    is undiagnosable from the driver's output alone."""
    cell, text = _drive(monkeypatch, tmp_path, "echo DRIVER-NARRATION; printf 'REPORT-TEXT\\n' > ../nox.out")

    assert cell.outcome == "fail"
    assert "DRIVER-NARRATION" in text
    assert "REPORT-TEXT" in text


def test_a_transcript_outlives_the_cells_own_scratch_cleanup(monkeypatch, tmp_path):
    """`run_cell` deletes its fixture, its scratch directory and the report file on the way
    out — which is why the evidence has to be written somewhere else before it does."""
    root = tmp_path / "cell"
    _sh_driver(monkeypatch, "echo done")
    pyz = tmp_path / "nox.pyz"
    pyz.write_bytes(b"")
    transcript = tmp_path / "runs" / "claude__codex.txt"

    manual_smoke.run_cell("claude", "codex", pyz=pyz, root=root, timeout_s=60, transcript=transcript)

    assert not root.exists() or not list(root.iterdir())
    assert transcript.read_text(encoding="utf-8").strip()


def test_a_passing_cell_leaves_a_transcript_too(monkeypatch, tmp_path):
    """A pass whose neighbour went red is the comparison an operator wants, so the write is
    not conditional on the outcome. The stand-in copies a real rendered review into place, so
    this is the one test that drives `run_cell` all the way to `pass`."""
    good = tmp_path / "good.out"
    good.write_text(_report(harness="codex", model=FAST_BALANCED["codex"]), encoding="utf-8")

    cell, text = _drive(monkeypatch, tmp_path, f"cp {good} ../nox.out")

    assert (cell.outcome, cell.reason) == ("pass", "")
    assert re.search(r"^outcome: pass$", text, re.MULTILINE), text
    assert manual_smoke.DEFECT in text


def test_a_cell_that_raises_becomes_a_red_cell_with_its_traceback_not_a_lost_sweep(monkeypatch, tmp_path):
    """`fixture` runs six `check=True` git commands. An escape used to abort the whole sweep:
    no tally, no failed-cell list, and no transcript for any cell that had not run yet."""

    def explode(*_args, **_kwargs):
        raise RuntimeError("git said no\nover two lines")

    monkeypatch.setattr(manual_smoke, "_drive", explode)
    transcript = tmp_path / "runs" / "claude__codex.txt"

    cell = manual_smoke.run_cell(
        "claude", "codex", pyz=tmp_path / "nox.pyz", root=tmp_path / "cell", timeout_s=5, transcript=transcript
    )

    assert cell.outcome == "fail"
    assert "\n" not in cell.reason
    assert "RuntimeError" in cell.reason
    text = transcript.read_text(encoding="utf-8")
    assert "Traceback" in text
    assert "explode" in text


def test_a_cell_that_skips_before_the_spawn_still_leaves_a_transcript(monkeypatch, tmp_path):
    """A skip prints one short line and no output at all, so it is the outcome an operator has
    the least to go on when it is wrong about the environment."""
    spawned = _forbid_spawn(monkeypatch)
    monkeypatch.setattr(manual_smoke, "DRIVERS", MappingProxyType({"claude": ("claude", "-p", manual_smoke.MODEL)}))
    pyz = tmp_path / "nox.pyz"
    pyz.write_bytes(b"")
    transcript = tmp_path / "runs" / "codex__claude.txt"

    cell = manual_smoke.run_cell("codex", "claude", pyz=pyz, root=tmp_path / "cell", timeout_s=5, transcript=transcript)

    assert spawned == []
    assert cell.outcome == "skip"
    text = transcript.read_text(encoding="utf-8")
    assert re.search(r"^driver: codex$", text, re.MULTILINE), text
    assert re.search(r"^adversary: claude$", text, re.MULTILINE), text
    assert cell.reason in text


def test_a_timed_out_driver_leaves_a_transcript_naming_the_bound(monkeypatch, tmp_path):
    """A timeout is the shape a flaky live cell most plausibly takes, and it is exactly the
    case whose output is longest and therefore most likely to have scrolled."""
    started = time.monotonic()
    _sh_driver(monkeypatch, "echo started-then-hung; sleep 60")
    pyz = tmp_path / "nox.pyz"
    pyz.write_bytes(b"")
    transcript = tmp_path / "runs" / "claude__codex.txt"

    cell = manual_smoke.run_cell("claude", "codex", pyz=pyz, root=tmp_path / "cell", timeout_s=2, transcript=transcript)

    assert time.monotonic() - started < 20
    assert cell.outcome == "fail"
    text = transcript.read_text(encoding="utf-8")
    assert "2" in cell.reason
    assert cell.reason in text
    assert "started-then-hung" in text


# --- main: the operator-facing surface ------------------------------------------------------------


def test_the_matrix_runs_every_registered_pair_and_prints_one_line_each(monkeypatch, capsys):
    calls = _canned(monkeypatch)

    assert manual_smoke.main([]) == 0

    assert sorted(calls) == PAIRS
    lines = [match for match in map(CELL_LINE.match, capsys.readouterr().out.splitlines()) if match]
    assert len(lines) == len(PAIRS)
    reported = {(match["driver"], match["adversary"]) for match in lines}
    assert reported == set(PAIRS)
    assert {match["outcome"] for match in lines} == {"pass"}


def test_a_failed_cell_makes_the_matrix_return_one_and_shows_in_the_tally(monkeypatch, capsys):
    _canned(monkeypatch, {("codex", "opencode"): "fail"})

    assert manual_smoke.main([]) == 1

    out = capsys.readouterr().out
    tally = TALLY.search(out)
    assert tally, out
    assert [int(part) for part in tally.groups()] == [len(PAIRS) - 1, 1, 0]
    failed = [match for match in map(CELL_LINE.match, out.splitlines()) if match and match["outcome"] == "fail"]
    assert [(match["driver"], match["adversary"]) for match in failed] == [("codex", "opencode")]


def test_a_matrix_that_only_skips_a_cell_still_returns_zero(monkeypatch, capsys):
    _canned(monkeypatch, {("claude", "opencode"): "skip"})

    assert manual_smoke.main([]) == 0

    tally = TALLY.search(capsys.readouterr().out)
    assert tally
    assert [int(part) for part in tally.groups()] == [len(PAIRS) - 1, 0, 1]


def test_the_cost_warning_names_the_cell_count_before_the_first_cell_line(monkeypatch, capsys):
    """16 live cells are real tokens on four vendors' meters, and the warning is only useful early."""
    _canned(monkeypatch)

    manual_smoke.main([])

    lines = capsys.readouterr().out.splitlines()
    first_cell = next(index for index, line in enumerate(lines) if CELL_LINE.match(line))
    preamble = "\n".join(lines[:first_cell])
    assert str(len(PAIRS)) in preamble
    assert re.search(r"cost|token|spend", preamble, re.IGNORECASE), preamble


def test_a_single_cell_runs_exactly_that_pair_and_may_report_a_skip_through_its_status(monkeypatch, capsys):
    calls = _canned(monkeypatch, {("claude", "copilot"): "skip"})

    assert manual_smoke.main(["--cell", "claude", "copilot"]) == manual_smoke.EXIT_SKIP

    assert calls == [("claude", "copilot")]
    lines = [match for match in map(CELL_LINE.match, capsys.readouterr().out.splitlines()) if match]
    assert len(lines) == 1
    assert (lines[0]["driver"], lines[0]["adversary"], lines[0]["outcome"]) == ("claude", "copilot", "skip")


@pytest.mark.parametrize(
    "argv", [["--cell", "claude"], ["--cell", "claude", "copilot", "codex"]], ids=["one-key", "three-keys"]
)
def test_a_single_cell_needs_exactly_two_keys(monkeypatch, argv):
    calls = _canned(monkeypatch)
    with pytest.raises(SystemExit) as excinfo:
        manual_smoke.main(argv)
    assert excinfo.value.code == 2
    assert calls == []


@pytest.mark.parametrize("argv", [["--cell", "claude", "bogus"], ["bogus"], ["claude", "bogus"]])
def test_an_unregistered_key_is_a_one_line_usage_error_not_a_traceback(monkeypatch, capsys, argv):
    calls = _canned(monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        manual_smoke.main(argv)

    assert excinfo.value.code == 2
    assert calls == []
    captured = capsys.readouterr()
    message = captured.err + captured.out
    assert message.strip()
    assert "Traceback" not in message
    assert "KeyError" not in message
    assert "bogus" in message or all(key in message for key in ADAPTERS)


def test_the_tally_names_the_transcript_of_every_failed_cell(monkeypatch, capsys):
    """The per-cell line scrolls; the tally is what is still on screen when a sweep of sixteen
    live cells finishes. The path belongs where the operator is still looking."""
    _canned(monkeypatch, {("codex", "opencode"): "fail"})

    assert manual_smoke.main([]) == 1

    out = capsys.readouterr().out
    tally = TALLY.search(out)
    assert tally, out
    after = out[tally.end() :]
    assert "codex__opencode.txt" in after
    assert "claude__claude.txt" not in after


def test_an_all_green_sweep_names_this_runs_directory_before_the_first_cell(monkeypatch, capsys):
    """Nothing fails, and the operator still has to be able to find the evidence — of THIS
    run. Printing the root instead would name a directory holding every run ever made."""
    handed: list[Path] = []

    def fake_run_cell(driver, adversary, *, transcript, **_kwargs):
        handed.append(transcript)
        return replace(_cell("pass", driver, adversary), transcript=transcript)

    monkeypatch.setattr(manual_smoke, "run_cell", fake_run_cell)

    assert manual_smoke.main([]) == 0

    lines = capsys.readouterr().out.splitlines()
    first_cell = next(index for index, line in enumerate(lines) if CELL_LINE.match(line))
    preamble = "\n".join(lines[:first_cell])
    run = handed[0].parent
    assert str(run) != os.environ[manual_smoke.RUNS_ENV]
    assert str(run) in preamble, preamble


def test_a_failed_cells_console_tail_is_the_report_nox_wrote_not_the_drivers_narration(monkeypatch, capsys):
    """`Cell.output` narrowed to the driver's own, so the tail has to reach for `report`
    first — the driver was told to reply with just DONE, and its prose is the weaker
    evidence of the two."""

    def fake_run_cell(driver, adversary, *, transcript, **_kwargs):
        cell = manual_smoke.Cell(
            driver, adversary, "fail", "canned reason", output="DRIVER-NARRATION", report="REPORT-TEXT"
        )
        return replace(cell, transcript=transcript)

    monkeypatch.setattr(manual_smoke, "run_cell", fake_run_cell)

    assert manual_smoke.main(["--cell", "claude", "codex"]) == 1

    out = capsys.readouterr().out
    assert "REPORT-TEXT" in out
    assert "DRIVER-NARRATION" not in out


def test_a_re_run_writes_a_new_directory_and_leaves_the_previous_runs_evidence(monkeypatch, capsys):
    """Re-running a red cell is the documented next step, so the run that went red must not be
    the one the re-run overwrites."""
    written: list[Path] = []

    def fake_run_cell(driver, adversary, *, transcript, **_kwargs):
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(f"{driver} -> {adversary}", encoding="utf-8")
        written.append(transcript)
        return replace(_cell("fail", driver, adversary), transcript=transcript)

    monkeypatch.setattr(manual_smoke, "run_cell", fake_run_cell)

    assert manual_smoke.main(["claude", "codex"]) == 1
    assert manual_smoke.main(["claude", "codex"]) == 1

    assert len(written) == 2
    assert written[0] != written[1]
    assert written[0].parent != written[1].parent
    assert [path.read_text(encoding="utf-8") for path in written] == ["claude -> codex"] * 2
    assert str(written[1].parent) in capsys.readouterr().out
