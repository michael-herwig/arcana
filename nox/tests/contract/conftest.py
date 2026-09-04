"""The contract tier's gate: skip locally, fail for a release (C-1037 1-3).

`tests/contract/` runs the real harness binaries. Three behaviours, and the
difference between the first two is the whole point:

1. `NOX_CONTRACT=1` with a binary absent — that adapter's tests **skip**, exit
   0. A developer without every harness installed can still run the tier.
2. `NOX_RELEASE=1` and the same binary absent — the same absence **fails**,
   naming binary and adapter. An absent binary must block a release rather
   than quietly reduce what was verified (C-1032).
3. `NOX_RELEASE=1` with everything present — a per-adapter count is asserted
   twice. Once at collection, **before any test runs**, so a missing file fails
   before a single test body executes; and once at session end over the tests
   that actually PASSED, because a `test_claude.py` carrying
   `pytestmark = pytest.mark.skip` collects a node, satisfies the first check
   and still runs no harness. A suite that proves nothing exits green, which is
   the one failure a release gate made of green suites cannot see, and a
   collection count alone does not catch it.

Neither variable set means the whole DIRECTORY skips — not merely the files
named `test_<adapter>.py`, because `testpaths = tests` collects this directory
on every ordinary `task nox:test` and C-1037(1) gates the tier, not a naming
convention. `adapter_of` keeps its narrower job: attributing a node to an
adapter for the C-1037(3) counts.

That also fixes the shape of this file: a directory conftest is loaded whenever
pytest walks the directory, so anything here that raises takes down the entire
session — the unit tier included. The hooks below therefore never raise except
where C-1037 requires it, and the decisions they make are pure module-level
functions that `tests/unit/test_contract_gate.py` exercises without spawning a
harness.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import pytest

from nox.adapters import ADAPTERS, load
from nox.config import ConfigError, auth_hint, minimal_env
from nox.config import load as load_config
from nox.harness import HarnessUnavailable, probe_harness
from nox.outcome import FailureReason
from nox.runner import SubprocessRunner

if TYPE_CHECKING:
    from collections.abc import Callable

    from nox.harness import HarnessInfo

GATE_ENV: Final[str] = "NOX_CONTRACT"
"""Set to `1` by `task nox:test:contract`. Without it the tier does not run."""

RELEASE_ENV: Final[str] = "NOX_RELEASE"
"""Set to `1` by `nox:release-gate`. Turns every skip in this tier into a failure."""

CONTRACT_DIR: Final[str] = "tests/contract"
"""The directory a node must live under to count toward an adapter (C-1037(3))."""

Mode = Literal["off", "contract", "release"]
"""What the two environment variables select."""


def gate_mode(environ: Mapping[str, str]) -> Mode:
    """Resolve the tier's mode from the environment.

    `RELEASE_ENV` implies `GATE_ENV`. C-1037(2) describes them as both set, but
    a release gate that silently did nothing because one of two variables was
    missing is the failure this whole file exists to prevent — so the stronger
    variable alone selects the stronger mode.

    The two variables read their values in OPPOSITE directions, because their
    fail-safe directions are opposite. `GATE_ENV` is strict — any value but
    `"1"` is off, so an accidental `NOX_CONTRACT=0` cannot run real binaries.
    `RELEASE_ENV` is permissive — anything but `""`, `"0"` or `"false"` selects
    `release`, so a `NOX_RELEASE=true` cannot silently disable the entire tier
    by failing an equality test and falling through to an unset `NOX_CONTRACT`.

    Args:
        environ: The process environment.

    Returns:
        `release`, `contract`, or `off`.
    """
    if environ.get(RELEASE_ENV, "") not in {"", "0", "false"}:
        return "release"
    if environ.get(GATE_ENV) == "1":
        return "contract"
    return "off"


def in_contract_dir(nodeid: str) -> bool:
    """Whether a collected node lives in this tier's directory.

    What C-1037(1) actually gates: the DIRECTORY runs real binaries, every file
    in it, whether or not its name matches an adapter. A helper suite named
    `test_shared_shapes.py` is exactly as live as `test_codex.py`.

    Anchored on a path boundary rather than a bare `endswith`, so a sibling
    `othertests/contract/` is a different directory and not this one.

    Args:
        nodeid: A pytest node id.

    Returns:
        Whether the node's file sits directly in `tests/contract/`.
    """
    directory = nodeid.partition("::")[0].rpartition("/")[0]
    return directory == CONTRACT_DIR or directory.endswith(f"/{CONTRACT_DIR}")


def adapter_of(nodeid: str) -> str | None:
    """Return the adapter a contract test node belongs to, from its path.

    The tier's one naming convention: `tests/contract/test_<adapter>.py`. Its
    only job is the C-1037(3) counts — what the tier SKIPS is decided by
    `in_contract_dir`, because a node this returns `None` for is still a node
    that spawns a real harness.

    Anchored on the directory as well as the file name, so neither a future
    `tests/unit/test_claude.py` nor an `othertests/contract/test_claude.py` can
    satisfy the count for an adapter whose contract suite does not exist. A
    convention rather than a marker because the count has to be computed for an
    adapter whose file is *missing entirely*, and a file that does not exist
    carries no marker.

    Args:
        nodeid: A pytest node id.

    Returns:
        The adapter name, or `None` for a node that is not an adapter suite.
    """
    filename = nodeid.partition("::")[0].rpartition("/")[2]
    if not in_contract_dir(nodeid) or not filename.startswith("test_") or not filename.endswith(".py"):
        return None
    name = filename[len("test_") : -len(".py")]
    return name if name in ADAPTERS else None


def zero_collection(nodeids: Iterable[str], registry: Iterable[str]) -> tuple[str, ...]:
    """Return the registered adapters with no collected contract test (C-1037(3)).

    Args:
        nodeids: Every collected node id.
        registry: The `ADAPTERS` keys.

    Returns:
        The adapter names with a zero count, sorted. Empty when every adapter
        collected at least one test.
    """
    collected = {adapter_of(nodeid) for nodeid in nodeids}
    return tuple(sorted(set(registry) - collected))


def zero_passes(passed: Mapping[str, int], registry: Iterable[str]) -> tuple[str, ...]:
    """Return the registered adapters whose contract suite never PASSED a test (C-1037(3)).

    The half `zero_collection` cannot see. A `test_claude.py` carrying
    `pytestmark = pytest.mark.skip` collects a node, so the collection-time
    check is satisfied, and then runs no harness at all — the conftest's own
    docstring names that as the failure a release gate made of green suites
    cannot catch, and a count of collected node ids is a green suite.

    Args:
        passed: Adapter name → number of passed test calls.
        registry: The `ADAPTERS` keys.

    Returns:
        The adapter names with no passing test, sorted.
    """
    return tuple(sorted(set(registry) - {name for name, count in passed.items() if count}))


def zero_passes_message(missing: Iterable[str]) -> str:
    """Render the C-1037(3) session-end failure.

    Args:
        missing: From `zero_passes`.

    Returns:
        One line, naming the adapters and why a green run is not enough.
    """
    return f"{RELEASE_ENV}=1: no contract test PASSED for {', '.join(missing)} — a suite that only skips proves nothing"


def absence_is_fatal(mode: Mode) -> bool:
    """Whether an absent harness fails the run rather than skipping it.

    Args:
        mode: From `gate_mode`.

    Returns:
        `True` only in `release`.
    """
    return mode == "release"


def absence_message(harness: str, binary: str, detail: str) -> str:
    """Render the message for an absent or unusable harness.

    Names the adapter AND the binary, per C-1037(2): "a harness was missing"
    without saying which one, or which executable to install, turns a release
    gate into a hunt. `binary` comes from the adapter's `BINARY` class
    attribute, which is readable without a successful probe — the case this
    message exists for.

    Args:
        harness: The registry key.
        binary: The adapter's `BINARY`.
        detail: `HarnessUnavailable.detail`.

    Returns:
        One line.
    """
    return f"{harness}: the {binary} binary is not usable — {detail}"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply the tier gate to the collected contract tests.

    Implemented rather than stubbed, and it must stay that way: a directory
    conftest is loaded on every walk of this directory, so a hook that raised
    `NotImplementedError` would abort the whole session — every unit test
    included — until the tier landed.

    Args:
        config: The pytest config. Unused; part of the hook signature.
        items: The collected items, skip-marked in place when the tier is off.

    Raises:
        pytest.UsageError: `release` mode and some registered adapter collected
            no test. Raised at collection so it precedes every test, which is
            what "before any test runs" in C-1037(3) buys. The passing-count
            half cannot be known until the session ends and lives in
            `pytest_sessionfinish`; this one stays because it is what makes a
            missing file fail before any test body runs.
    """
    del config
    mode = gate_mode(os.environ)
    if mode == "off":
        skip = pytest.mark.skip(reason=f"contract tier: set {GATE_ENV}=1 to run it")
        for item in items:
            # The whole directory, not just `test_<adapter>.py`: a helper suite
            # here spawns real binaries exactly as an adapter suite does.
            if in_contract_dir(item.nodeid):
                item.add_marker(skip)
        return
    if mode == "release":
        missing = zero_collection((item.nodeid for item in items), ADAPTERS)
        if missing:
            raise pytest.UsageError(
                f"{RELEASE_ENV}=1: no contract test collected for {', '.join(missing)} — "
                "a suite that collects nothing proves nothing"
            )


PASSED: dict[str, int] = {}
"""Passing test calls per adapter, filled by `pytest_runtest_logreport`."""


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Count each adapter's passing test calls, for the C-1037(3) session-end check.

    `call` only: a passing `setup` phase is reported for a test that then skips,
    and counting it would reintroduce the hole this counter exists to close.

    Args:
        report: One phase report.
    """
    if report.when == "call" and report.passed:
        name = adapter_of(report.nodeid)
        if name is not None:
            PASSED[name] = PASSED.get(name, 0) + 1


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail a release run in which some adapter never passed a contract test (C-1037(3)).

    Args:
        session: The finished session, whose `exitstatus` this sets.
        exitstatus: What the run resolved to. Unused; part of the signature.
    """
    del exitstatus
    if gate_mode(os.environ) != "release":
        return
    missing = zero_passes(PASSED, ADAPTERS)
    if missing:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(zero_passes_message(missing), red=True)


REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
"""The repository this checkout lives in — `nox/`'s parent, not the tier's cwd.

The argument `minimal_env` and `load` both call "the repository under review",
and getting it wrong scopes every T4b refusal to a subtree of the real one.
"""


def probe_or_skip(harness: str, mode: Mode) -> HarnessInfo:
    """Probe one adapter's binary, skipping (`contract`) or failing (`release`) on absence.

    A plain function rather than the fixture's inner closure, for the same
    reason every other decision in this file is one: `tests/` is outside the
    coverage source, so a `pytest.skip` where C-1037(2) requires `pytest.fail`
    leaves the whole suite green. `tests/unit/test_contract_gate.py` calls this
    directly with a stub adapter, which is what makes the two branches verified
    rather than merely written.

    Args:
        harness: A registry key.
        mode: From `gate_mode`.

    Returns:
        What the probe established.
    """
    # `load` is outside the guard on purpose: a registered adapter whose module
    # is missing is an incomplete build, not an absent harness, and skipping it
    # would be the silence C-1037(3) exists to refuse.
    adapter = load(harness)
    warnings: tuple[str, ...] = ()
    dropped: tuple[str, ...] = ()
    try:
        env, dropped = minimal_env(REPO_ROOT, REPO_ROOT / ".nox-contract-probe")
        # The USER's config, not `HarnessConfig()`. D-s puts OpenCode behind an
        # `ocx package exec` launcher and it has no binary on `PATH` at all, so
        # an empty config probes a name that cannot resolve and the whole tier
        # skips as "absent" on a machine where the harness demonstrably works —
        # which under `NOX_RELEASE=1` is C-1037(2) failing for a reason that is
        # nox's own. This is also the config a real review resolves, so the tier
        # exercises the launcher route rather than a shape only tests take.
        #
        # `REPO_ROOT`, never `Path.cwd()`: both calls take "the repository under
        # review" and use it to scope T4b, and cwd here is the `nox/` subtree. An
        # `XDG_CONFIG_HOME` pointing at `<repo>/.config` is outside `nox/` and so
        # would pass the refusal, making a branch-authored `nox.toml` the
        # *trusted* file — whose `launcher` names the binary this then execs.
        cfg, warnings = load_config(REPO_ROOT)
        return probe_harness(adapter, SubprocessRunner(), cfg.for_harness(harness), env)
    except ConfigError as exc:
        # A config nox cannot resolve is not a harness that is absent, but it
        # reaches the operator through the same two doors, and a traceback out of
        # a fixture would reach them through neither.
        pytest.fail(f"{harness}: configuration could not be resolved: {exc}")
    except HarnessUnavailable as exc:
        # The resolver's warnings travel with the absence: a `launcher` dropped
        # as untrust-gated is exactly why a present harness reads as missing, and
        # under `NOX_RELEASE=1` that is C-1037(2) failing for a reason of nox's own.
        # `api._auth_detail`'s job, done here because this path does not go
        # through `review()`. No adapter composes the C-1034(4) hint — it needs
        # `minimal_env`'s real dropped list, which `Adapter.probe` is never
        # handed — so without this an `UNAUTHENTICATED` release failure names
        # the condition and not the cause, and the operator's obvious next move
        # (export the API key) is the one C-1002 guarantees cannot work.
        reasoned = (exc.detail, *warnings)
        if exc.reason is FailureReason.UNAUTHENTICATED:
            reasoned = (*reasoned, auth_hint(harness, dropped))
        detail = "; ".join(reasoned)
        message = absence_message(harness, adapter.BINARY, detail)
        if absence_is_fatal(mode):
            pytest.fail(message)
        pytest.skip(message)


@pytest.fixture
def require_harness() -> Callable[[str], HarnessInfo]:
    """Probe one adapter's binary, skipping or failing per the tier mode.

    The wrapper every contract test opens with. It runs the adapter's real
    `probe()` through a real `SubprocessRunner` under the C-1008 minimal
    environment and a nox-minted empty cwd — the same startup the review will
    do, so a harness that is installed but unauthenticated is caught here
    rather than mid-review.

    Returns:
        A callable taking a registry key and returning what the probe
        established. It skips (`contract`) or fails (`release`) when the probe
        raises `HarnessUnavailable`.
    """
    mode = gate_mode(os.environ)
    return lambda harness: probe_or_skip(harness, mode)
