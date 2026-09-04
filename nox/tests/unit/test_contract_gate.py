"""The contract tier's gate, exercised without spawning a harness (C-1037 1-3).

The conftest is loaded **by file path**: the contract tier runs under a
different invocation than the unit tier, so a test that reached it through an
import statement would be asserting about `sys.path` shape as much as about the
gate. Two of the tests below run a real nested pytest through the `pytester`
fixture, because "before any test runs" (C-1037(3)) is a claim about collection
ordering that only a real run can settle.
"""

import importlib.util
import shutil
from pathlib import Path

import pytest

from nox.adapters import ADAPTERS
from nox.config import AUTH_HINT_TRAILER, NoxConfig
from nox.harness import HarnessUnavailable
from nox.outcome import FailureReason

pytest_plugins = ["pytester"]

CONFTEST = Path(__file__).resolve().parents[1] / "contract" / "conftest.py"
"""The file under test. Never imported as `tests.contract.conftest`."""


def _gate():
    """Load the contract conftest as a plain module, by path."""
    spec = importlib.util.spec_from_file_location("nox_contract_gate_under_test", CONFTEST)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _gate()


def _seed(pytester, adapters):
    """Write a contract tier holding one throwaway test per named adapter.

    Each test body touches a marker file, so "no test body ran" is checkable
    rather than inferred from the summary line.
    """
    contract = pytester.path / "tests" / "contract"
    contract.mkdir(parents=True)
    shutil.copy(CONFTEST, contract / "conftest.py")
    marker = pytester.path / "a-test-body-ran"
    for name in adapters:
        (contract / f"test_{name}.py").write_text(
            f"def test_{name}_smoke():\n    open({str(marker)!r}, 'a').close()\n",
            encoding="utf-8",
        )
    return marker


# ---------------------------------------------------------------------------
# `gate_mode`: C-1037(1), C-1037(2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({}, "off"),
        ({"NOX_CONTRACT": "1"}, "contract"),
        ({"NOX_CONTRACT": "1", "NOX_RELEASE": "1"}, "release"),
        ({"NOX_CONTRACT": "0"}, "off"),
        ({"NOX_CONTRACT": "true"}, "off"),
        ({"NOX_CONTRACT": ""}, "off"),
        ({"NOX_RELEASE": "0"}, "off"),
    ],
    ids=["neither", "contract", "both", "zero", "true", "empty", "release-zero"],
)
def test_gate_mode_resolves_the_tier_from_the_environment(environ, expected):
    """C-1037(1): any value but `"1"` is off — an accidental `NOX_CONTRACT=0` must not run real binaries."""
    assert gate.gate_mode(environ) == expected


def test_the_release_variable_alone_selects_release():
    """C-1037(2), deliberate deviation: the literal wording asks for both variables.

    A release gate that silently did nothing because one of two variables was
    missing is the exact failure the tier exists to prevent, so the stronger
    variable alone selects the stronger mode. Fail-safe, and documented on
    `gate_mode` itself.
    """
    assert gate.gate_mode({"NOX_RELEASE": "1"}) == "release"


# ---------------------------------------------------------------------------
# `adapter_of` and `zero_collection`: C-1037(3)
# ---------------------------------------------------------------------------


def test_a_contract_node_is_attributed_to_its_adapter():
    """C-1037(3): the tier's one naming convention, `tests/contract/test_<adapter>.py`."""
    assert gate.adapter_of("tests/contract/test_claude.py::test_x") == "claude"


def test_a_unit_test_of_the_same_name_is_not_attributed():
    """C-1037(3): anchored on the directory, so a unit test cannot satisfy the release count."""
    assert gate.adapter_of("tests/unit/test_claude.py::test_x") is None


def test_a_non_adapter_contract_file_is_not_attributed():
    """C-1037(3): a contract-tier helper suite belongs to no adapter and counts for none."""
    assert gate.adapter_of("tests/contract/test_shared_shapes.py::test_x") is None


def test_an_adapter_with_no_collected_node_is_reported():
    """C-1037(3): a suite that collected zero tests exits green while proving nothing."""
    covered = sorted(ADAPTERS)[1:]
    nodeids = [f"tests/contract/test_{name}.py::test_x" for name in covered]
    assert gate.zero_collection(nodeids, ADAPTERS) == (sorted(ADAPTERS)[0],)


def test_full_coverage_reports_nothing():
    """C-1037(3): every registered adapter collected at least one test."""
    nodeids = [f"tests/contract/test_{name}.py::test_x" for name in ADAPTERS]
    assert gate.zero_collection(nodeids, ADAPTERS) == ()


def test_the_missing_adapters_are_reported_sorted():
    """C-1037(3): the message is read by a human under a failing release gate."""
    covered = sorted(ADAPTERS)[:1]
    nodeids = [f"tests/contract/test_{name}.py::test_x" for name in covered]
    assert gate.zero_collection(nodeids, ADAPTERS) == tuple(sorted(set(ADAPTERS) - set(covered)))


# ---------------------------------------------------------------------------
# `absence_is_fatal` and `absence_message`: C-1037(2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("mode", "fatal"), [("off", False), ("contract", False), ("release", True)])
def test_an_absent_harness_is_fatal_only_for_a_release(mode, fatal):
    """C-1037(2), C-1032: a developer without every harness can still run the tier."""
    assert gate.absence_is_fatal(mode) is fatal


def test_the_absence_message_names_the_harness_and_the_binary():
    """C-1037(2): "a harness was missing" without which executable to install is a hunt."""
    message = gate.absence_message("opencode", "opencode-bin", "not found on PATH")
    assert "opencode-bin" in message
    assert "opencode" in message


# ---------------------------------------------------------------------------
# End to end through a real pytest — the only proof of "before any test runs"
# ---------------------------------------------------------------------------


def test_the_whole_tier_skips_when_neither_variable_is_set(pytester, monkeypatch):
    """C-1037(1): `testpaths = tests` collects this directory on every ordinary run."""
    monkeypatch.delenv("NOX_CONTRACT", raising=False)
    monkeypatch.delenv("NOX_RELEASE", raising=False)
    marker = _seed(pytester, sorted(ADAPTERS))
    result = pytester.runpytest_subprocess("tests/contract", "-p", "no:cacheprovider")
    result.assert_outcomes(skipped=len(ADAPTERS))
    assert result.ret == 0
    assert not marker.exists()


def test_a_release_run_fails_at_collection_when_an_adapter_collected_nothing(pytester, monkeypatch):
    """C-1037(3): raised at collection, so it precedes every test rather than joining them."""
    monkeypatch.setenv("NOX_RELEASE", "1")
    monkeypatch.setenv("NOX_CONTRACT", "1")
    absent = sorted(ADAPTERS)[0]
    marker = _seed(pytester, [name for name in sorted(ADAPTERS) if name != absent])
    result = pytester.runpytest_subprocess("tests/contract", "-p", "no:cacheprovider")
    assert result.ret != 0
    assert absent in result.stdout.str() + result.stderr.str()
    assert not marker.exists()


# ---------------------------------------------------------------------------
# Review-fix round: four gate holes and the untested skip-vs-fail branch
# ---------------------------------------------------------------------------


class _AbsentAdapter:
    """An adapter whose real `probe` refuses, for the C-1037(1)/(2) branch."""

    name = "claude"
    BINARY = "some-harness-bin"
    CONFIG_READS: tuple[str, ...] = ()

    def probe(self, runner, cfg, env, cwd):
        del runner, cfg, env, cwd
        raise HarnessUnavailable(FailureReason.ABSENT, "not found on the minimal PATH")


class _UnauthenticatedAdapter(_AbsentAdapter):
    """An adapter whose real `probe` refuses for want of credentials (C-1034(4))."""

    def probe(self, runner, cfg, env, cwd):
        del runner, cfg, env, cwd
        raise HarnessUnavailable(FailureReason.UNAUTHENTICATED, "the harness reports no stored credential")


class _Report:
    """The three fields `pytest_runtest_logreport` reads off a phase report."""

    def __init__(self, nodeid, when, passed):
        self.nodeid = nodeid
        self.when = when
        self.passed = passed


def _seed_shared(pytester, adapters):
    """Seed the tier with one suite per adapter PLUS a non-adapter helper suite.

    `test_shared_shapes.py` is the file `adapter_of` returns `None` for by
    design, and it spawns real binaries exactly as an adapter suite does.
    """
    marker = _seed(pytester, adapters)
    contract = pytester.path / "tests" / "contract"
    (contract / "test_shared_shapes.py").write_text(
        f"def test_shared_smoke():\n    open({str(marker)!r}, 'a').close()\n",
        encoding="utf-8",
    )
    return marker


def _seed_skipping(pytester, adapters, skipped):
    """Seed the tier where the named adapters' suites collect a node and always skip."""
    contract = pytester.path / "tests" / "contract"
    contract.mkdir(parents=True, exist_ok=True)
    shutil.copy(CONFTEST, contract / "conftest.py")
    for name in adapters:
        head = "import pytest\n\npytestmark = pytest.mark.skip(reason='no binary')\n\n" if name in skipped else ""
        (contract / f"test_{name}.py").write_text(
            f"{head}def test_{name}_smoke():\n    assert True\n",
            encoding="utf-8",
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", "release"), ("TRUE", "release"), ("yes", "release"), ("", "off"), ("0", "off"), ("false", "off")],
)
def test_any_release_value_but_the_three_off_spellings_selects_release(value, expected):
    """C-1037(2): `NOX_RELEASE=true` failed a `== "1"` test and fell through to an unset `NOX_CONTRACT`.

    The whole tier then silently did nothing under a release gate — the exact
    failure this file exists to prevent, so the permissive direction is the
    fail-safe one here. `NOX_CONTRACT` keeps its strict `"1"`, where strict is
    the fail-safe direction instead.
    """
    assert gate.gate_mode({"NOX_RELEASE": value}) == expected


def test_the_contract_directory_test_is_anchored_at_a_path_boundary():
    """C-1037(1): what the tier gates is the DIRECTORY, and `endswith` matched a sibling of it."""
    assert gate.in_contract_dir("tests/contract/test_shared_shapes.py::test_x")
    assert gate.in_contract_dir("test_claude.py::test_x") is False
    assert gate.in_contract_dir("othertests/contract/test_claude.py::test_x") is False
    assert gate.in_contract_dir("tests/unit/test_harness.py::test_x") is False


def test_a_similarly_named_directory_is_not_attributed_to_an_adapter():
    """C-1037(3): `othertests/contract/` is a different directory, and its nodes count for nothing."""
    assert gate.adapter_of("othertests/contract/test_claude.py::test_x") is None


def test_an_adapter_whose_suite_only_skipped_is_reported():
    """C-1037(3): a collected-but-skipped suite satisfies the collection count and runs no harness."""
    assert gate.zero_passes({name: 1 for name in sorted(ADAPTERS)[1:]}, ADAPTERS) == (sorted(ADAPTERS)[0],)


def test_a_present_but_zero_pass_count_is_still_a_zero():
    """C-1037(3): the key existing is not the question; a passing test body is."""
    assert gate.zero_passes({name: 0 for name in ADAPTERS}, ADAPTERS) == tuple(sorted(ADAPTERS))


def test_a_passing_test_for_every_adapter_reports_nothing():
    """C-1037(3): the positive control for the session-end half."""
    assert gate.zero_passes({name: 1 for name in ADAPTERS}, ADAPTERS) == ()


def test_the_zero_pass_message_names_the_adapters_and_the_reason():
    """C-1037(3): read by a human under a failing release gate."""
    message = gate.zero_passes_message(["claude", "codex"])
    assert "claude" in message
    assert "codex" in message
    assert "PASSED" in message


def test_only_a_passing_call_phase_counts_toward_an_adapter(monkeypatch):
    """C-1037(3): a passing `setup` phase is reported for a test that then skips."""
    monkeypatch.setattr(gate, "PASSED", {})
    gate.pytest_runtest_logreport(_Report("tests/contract/test_claude.py::t", "setup", True))
    gate.pytest_runtest_logreport(_Report("tests/contract/test_claude.py::t", "call", False))
    gate.pytest_runtest_logreport(_Report("tests/unit/test_claude.py::t", "call", True))
    gate.pytest_runtest_logreport(_Report("tests/contract/test_shared_shapes.py::t", "call", True))
    assert gate.PASSED == {}
    gate.pytest_runtest_logreport(_Report("tests/contract/test_claude.py::t", "call", True))
    assert gate.PASSED == {"claude": 1}


def _outcome(environ, monkeypatch):
    """Return the outcome exception `probe_or_skip` raised for an absent harness.

    Caught rather than asserted through `pytest.raises`, because a `Skipped`
    escaping a test that expected a `Failed` SKIPS that test instead of failing
    it — which is the same silence C-1037(2) exists to refuse, one level up.

    The config resolver is stubbed, not exercised: `probe_or_skip` reads the
    USER's `nox.toml` so the contract tier can reach D-s's launcher, and the
    unit tier must not fail or change answer on whatever the developer running
    it happens to have written there.
    """
    monkeypatch.setattr(gate, "load_config", lambda root: (NoxConfig(), ()))
    try:
        gate.probe_or_skip("claude", gate.gate_mode(environ))
    except (pytest.skip.Exception, pytest.fail.Exception) as exc:
        return exc
    return None


def test_an_absent_harness_skips_under_the_contract_variable(monkeypatch):
    """C-1037(1): a developer without every harness installed can still run the tier.

    `tests/` is outside `source = ["nox"]`, so swapping this `skip` for a
    `fail` — or the reverse below — leaves the whole suite green. These two are
    what make the branch verified rather than merely written.
    """
    monkeypatch.setattr(gate, "load", lambda name: _AbsentAdapter())
    outcome = _outcome({"NOX_CONTRACT": "1"}, monkeypatch)
    assert isinstance(outcome, pytest.skip.Exception)
    assert "some-harness-bin" in str(outcome)
    assert "claude" in str(outcome)


def test_an_absent_harness_fails_a_release_run(monkeypatch):
    """C-1037(2), C-1032: an absent binary must block a release, not quietly reduce what was verified."""
    monkeypatch.setattr(gate, "load", lambda name: _AbsentAdapter())
    outcome = _outcome({"NOX_RELEASE": "1"}, monkeypatch)
    assert isinstance(outcome, pytest.fail.Exception)
    assert "some-harness-bin" in str(outcome)
    assert "claude" in str(outcome)


def test_an_unauthenticated_refusal_names_the_credential_variables_nox_dropped(monkeypatch):
    """C-1034(4): this path does not go through `review()`, so it has to compose the hint itself.

    No adapter composes it — the hint needs `minimal_env`'s real dropped list
    and `Adapter.probe` is never handed one — so an `UNAUTHENTICATED` release
    failure would otherwise name the condition and not the cause, and the
    operator's obvious next move (export the API key) is the one C-1002
    guarantees cannot work. `ANTHROPIC_API_KEY` is `AUTH_ENV_HINTS["claude"]`'s
    own member, and `DENY_PATTERNS` drops it, so it lands in `dropped` for real
    rather than by a stub agreeing with itself.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-be-echoed")
    monkeypatch.setattr(gate, "load", lambda name: _UnauthenticatedAdapter())
    outcome = _outcome({"NOX_RELEASE": "1"}, monkeypatch)
    assert isinstance(outcome, pytest.fail.Exception)
    assert "ANTHROPIC_API_KEY" in str(outcome)
    assert AUTH_HINT_TRAILER in str(outcome)
    assert str(outcome).count(AUTH_HINT_TRAILER) == 1
    assert "sk-must-not-be-echoed" not in str(outcome)


def test_a_non_adapter_contract_file_skips_with_the_rest_of_the_tier(pytester, monkeypatch):
    """C-1037(1): `adapter_of` returns `None` for it by design, so a per-file gate ran it for real.

    On every ordinary `task nox:verify`, against whatever binaries the machine
    happens to have.
    """
    monkeypatch.delenv("NOX_CONTRACT", raising=False)
    monkeypatch.delenv("NOX_RELEASE", raising=False)
    marker = _seed_shared(pytester, sorted(ADAPTERS))
    result = pytester.runpytest_subprocess("tests/contract", "-p", "no:cacheprovider")
    result.assert_outcomes(skipped=len(ADAPTERS) + 1)
    assert result.ret == 0
    assert not marker.exists()


def test_a_release_run_fails_when_an_adapter_suite_collected_only_skips(pytester, monkeypatch):
    """C-1037(3): the collection count passes on a suite that never runs a harness.

    `pytestmark = pytest.mark.skip` collects a node for every adapter, so the
    before-any-test check is satisfied and the run exits green having proved
    nothing — which the conftest's own docstring names as the failure a release
    gate made of green suites cannot see.
    """
    monkeypatch.setenv("NOX_RELEASE", "1")
    monkeypatch.setenv("NOX_CONTRACT", "1")
    absent = sorted(ADAPTERS)[0]
    _seed_skipping(pytester, sorted(ADAPTERS), {absent})
    result = pytester.runpytest_subprocess("tests/contract", "-p", "no:cacheprovider")
    output = result.stdout.str() + result.stderr.str()
    assert result.ret != 0
    assert "no contract test PASSED" in output
    assert absent in output


def test_a_release_run_with_every_adapter_passing_is_green(pytester, monkeypatch):
    """C-1037(3): the positive control — the session-end check must not fail an honest run."""
    monkeypatch.setenv("NOX_RELEASE", "1")
    monkeypatch.setenv("NOX_CONTRACT", "1")
    _seed_skipping(pytester, sorted(ADAPTERS), set())
    result = pytester.runpytest_subprocess("tests/contract", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=len(ADAPTERS))
    assert result.ret == 0
