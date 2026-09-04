"""Codex against the real `codex` binary (C-1032, C-1037, C-1040, S-1002).

Runs only under `NOX_CONTRACT=1` and fails rather than skips under
`NOX_RELEASE=1` — the gate is `tests/contract/conftest.py` and every test here
opens with its `require_harness` fixture, which runs the adapter's own `probe()`
through a real `SubprocessRunner` under the C-1008 minimal environment.

What this tier proves that the unit tier structurally cannot:

- the `--output-schema` object is a shape *this* binary accepts, and its
  property set still matches `prompt.WIRE_SCHEMA`'s own keys — nothing in the
  product joins those two schemas, so they can drift apart silently (WP5's
  carry-forward row);
- `--strict-config` refutes an unknown key AND an unknown `sandbox_mode` value,
  which is what turns the sandbox key from an *inferred* name into a verified
  one (SD § 6.2's own caveat, closed here);
- C-1040's probe passes against the live sandbox — the one observation that
  cannot be replayed, because the nonce is minted per run;
- C-1032's auth negative: a probe under an empty `CODEX_HOME` refuses
  `UNAUTHENTICATED` rather than reporting a harness that fails mid-review;
- the SD § 9.4 hostile branch survives a real review with none of the seven
  hostile files executing (S-1006);
- the SIGTERM path through a real spawn leaves no surviving descendant *in the
  process group*. That is the whole of the claim: D-ac's clean-exit and
  `setsid()` residuals are accepted and open, and nothing here may be read as
  closing them.

Every real turn costs tokens and wall clock, so this file spends them only where
a fixture cannot stand in.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from nox.adapters.codex import (
    BINARY,
    CAPABILITIES,
    CONFIG_FLAGS,
    SANDBOX_MODE,
    SCHEMA_FILENAME,
    SUBCOMMAND,
    VERIFIED_AGAINST,
    CodexAdapter,
)
from nox.config import ConfigError, HarnessConfig
from nox.harness import (
    PASSTHROUGH_ALLOW,
    HarnessUnavailable,
    ProbeCache,
    authorize,
    resolve_executable,
    version_warning,
)
from nox.liveness import Heartbeat, TimeoutPolicy
from nox.outcome import FailureReason
from nox.prompt import WIRE_SCHEMA
from nox.runner import Invocation, SubprocessRunner, supervise
from nox.workspace import ReviewTarget, workspace
from tests.fixtures.repo import make_repo

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codex"
STRICT_CONFIG_FIXTURE = FIXTURES / "strict-config-0.144.1.txt"

UNKNOWN_KEY = "definitely_not_a_real_key_xyz=1"
"""The `-c` override `strict-config-0.144.1.txt` recorded a refusal for."""

UNKNOWN_KEY_MESSAGE = "unknown configuration field"
UNKNOWN_VALUE_MESSAGE = "expected one of `read-only`, `workspace-write`, `danger-full-access`"

TRIVIAL_PROMPT = "Reply with exactly: X"
"""The cheapest turn this binary will run — used only where the config load must fail first."""

SCHEMA_REJECTION = "invalid_json_schema"
"""The provider's code for a refused `--output-schema` (`output-schema-rejected-0.144.1.jsonl`).

It fails the turn before the model reads the prompt, so a review that hit it
looks — to every assertion about what did NOT happen — exactly like a review
that behaved.
"""


def _target() -> ReviewTarget:
    return ReviewTarget(kind="ref", ref="refs/heads/main")


def _heartbeat(info) -> Heartbeat:
    return Heartbeat(kind=info.heartbeat_kind, last_activity_at=0.0, last_byte_at=0.0)


def _collector(sink: list[str], adapter: CodexAdapter | None = None):
    """An `OnLine` that keeps every line for `parse` and answers with the ADAPTER's own verdict.

    Delegating rather than returning `True`, because a collector that calls
    every line semantic is what let this tier assert nothing about `on_line`
    while `HEARTBEAT_KIND` is `SEMANTIC`: `supervise` measures the 120 s silence
    window against `Heartbeat.touch`, which advances only on `True`, so an
    adapter that never says `True` has every real review killed while it works.
    Delegating means the window here is driven by the shipped answer, as a
    review's is (`test_claude.py` does the same).

    `adapter=None` keeps the plain accumulator for the legs that are not
    reviews — a `--help` spawn emits no JSON at all and would time out on an
    honest `False`.
    """

    def on_line(line: str) -> bool:
        sink.append(line)
        return True if adapter is None else adapter.on_line(line)

    return on_line


@pytest.fixture
def adapter() -> CodexAdapter:
    return CodexAdapter()


@pytest.fixture
def live(require_harness, tmp_path):
    """A probed `HarnessInfo` and one live ephemeral worktree over a clean repository.

    **No `env=`, here or anywhere else in this tier.** `workspace()` then builds
    its own `config.minimal_env` from `os.environ`, which is exactly what
    `review()` does — so the real `HOME` and `CODEX_HOME` reach the child and
    Codex finds its own credential store. Hand it the git fixtures' `nox_env`
    instead and `HOME` is a throwaway directory under `tmp_path`: every live leg
    runs unauthenticated, and `sandbox_probe`'s review leg gets a 401 retry loop
    rather than a `command_execution` item — `False` for a reason that has
    nothing to do with the sandbox. `tests/unit/test_hygiene.py` greps for it.

    nox still never reads the store (C-1002): `ALLOWLIST` forwards the two
    variables that let the harness reach it, and that is all.
    """
    info = require_harness("codex")
    repo = make_repo(tmp_path)
    with workspace(repo.path, _target()) as ws:
        yield info, ws


# ---------------------------------------------------------------------------
# C-1020 / E3: the version every fixture in this directory was recorded from
# ---------------------------------------------------------------------------


def test_the_probed_version_is_the_one_every_fixture_was_recorded_from(require_harness):
    """C-1020/E3: a mismatch warns and never refuses, so the release gate is what pins it."""
    info = require_harness("codex")
    assert info.version == VERIFIED_AGAINST
    assert version_warning(info) is None


def test_the_probe_establishes_exactly_the_shipped_capability_set(require_harness):
    """C-1013: what the real probe established, against what the adapter ships as its claim."""
    assert require_harness("codex").capabilities == CAPABILITIES


# ---------------------------------------------------------------------------
# WP5 carry-forward: the two schemas, joined by nothing but this test
# ---------------------------------------------------------------------------


def test_the_output_schema_object_names_exactly_the_wire_contracts_own_keys(adapter, live):
    """WP5 carry-forward: nothing joins `--output-schema` and `WIRE_SCHEMA`, so they can drift silently.

    Both levels. The top-level keys are four words that rarely move; the finding
    object is where a field is actually added, so a join that compared only the
    top level would be watching the half that does not drift.
    """
    info, ws = live
    adapter.prepare(ws, info, HarnessConfig(), None)
    schema = json.loads((ws.scratch / SCHEMA_FILENAME).read_text(encoding="utf-8"))
    contract = json.loads(WIRE_SCHEMA)
    assert set(schema["properties"]) == set(contract)
    assert set(schema["properties"]["findings"]["items"]["properties"]) == set(contract["findings"][0])


# ---------------------------------------------------------------------------
# C-1032: auth, the required negative — the one this tier can actually produce
# ---------------------------------------------------------------------------


def test_a_probe_with_no_credentials_refuses_unauthenticated(adapter, live, tmp_path):
    """C-1032: a required negative, and `login-status-unauthenticated-0.144.1.txt` proves it reproducible.

    `codex --version` exits 0 with no credentials at all, so this is the half of
    C-1014 a version probe cannot answer — and the failure it prevents (a 401
    retry loop mid-review) costs a whole model turn to discover any other way.
    `CODEX_HOME` is the C-1008-forwarded variable Codex authenticates out of, so
    pointing it at an empty directory is the reproducible shape of "installed
    and logged out".
    """
    info, ws = live
    del info
    empty = tmp_path / "codex-home-with-no-credentials"
    empty.mkdir()
    cwd = tmp_path / "probe-cwd"
    cwd.mkdir()
    env = {**dict(ws.env), "CODEX_HOME": str(empty)}
    with pytest.raises(HarnessUnavailable) as exc:
        adapter.probe(SubprocessRunner(), HarnessConfig(), env, cwd)
    assert exc.value.reason is FailureReason.UNAUTHENTICATED
    assert BINARY in exc.value.detail


# ---------------------------------------------------------------------------
# C-1023: passthrough rejections, including the SD's named flags
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "passthrough",
    [
        ("-c", "sandbox_mode=danger-full-access"),
        ("--config=sandbox_mode=danger-full-access",),
        ("--dangerously-bypass-approvals-and-sandbox",),
        ("--dangerously-bypass-hook-trust",),
        ("--ephemeral",),
        ("a-bare-positional",),
        ("--title",),
    ],
    ids=[
        "config-sep",
        "config-joined",
        "bypass-sandbox",
        "bypass-hooks",
        "nox-owned",
        "positional",
        "review-subcommand-flag",
    ],
)
def test_a_refused_passthrough_element_never_reaches_the_real_binary(adapter, live, passthrough):
    """C-1023: the allowlist permits nothing, and every shape here is refused before any spawn.

    `--title` is in the list for what it is now rather than for what it was: an
    allowlist miss like any other word, refused by name. It used to be the one
    permitted flag and reached this refusal only as a trailing value-taking flag
    with no value — the id said `no-value` and now says what the case is.
    """
    info, ws = live
    with pytest.raises(ConfigError):
        adapter.prepare(ws, info, HarnessConfig(passthrough=passthrough), None)


def test_the_allowlist_permits_nothing_and_the_flag_it_once_permitted_is_not_a_flag_here(live):
    """C-1023: `--title` was codex's ONLY allowlisted passthrough, and `codex exec` has no such flag.

    Refuted against the live binary rather than the committed page, which is
    what this tier is for. `codex exec review` documents `--title`; bare
    `codex exec` — what `SUBCOMMAND` spawns (E21) — answers
    `error: unexpected argument`. So the single word this gate let a repository
    pass through produced a clap error from the binary, past nox's refusal path
    and with none of nox's diagnosis, which is why the cell is now empty.

    `-h` after the flag costs no AI credits: clap refuses the argv before any
    model is reached, and the exit status is 2 either way.
    """
    info, ws = live
    argv = (resolve_executable(BINARY, ws.env), *SUBCOMMAND, "--title", "nox-contract", "-h")
    proc = SubprocessRunner().spawn(Invocation(argv=argv, cwd=ws.path, env=ws.env))
    collected: list[str] = []
    result = supervise(proc, TimeoutPolicy.for_kind(info.heartbeat_kind, 60), _heartbeat(info), _collector(collected))
    assert PASSTHROUGH_ALLOW["codex"] == frozenset()
    assert result.exit_code not in (0, None)
    assert any("unexpected argument '--title'" in line for line in collected), collected


# ---------------------------------------------------------------------------
# SD § 6.2: `--strict-config` turns an inferred key name into a verified one
# ---------------------------------------------------------------------------


def test_the_recorded_strict_config_fixture_still_carries_both_refutations():
    """The guard on the two live assertions below, so a re-recorded fixture cannot weaken them."""
    recorded = STRICT_CONFIG_FIXTURE.read_text(encoding="utf-8")
    assert UNKNOWN_KEY_MESSAGE in recorded
    assert UNKNOWN_VALUE_MESSAGE in recorded


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        (UNKNOWN_KEY, UNKNOWN_KEY_MESSAGE),
        ("sandbox_mode=totally-bogus-value", UNKNOWN_VALUE_MESSAGE),
    ],
    ids=["unknown-key", "unknown-sandbox-mode"],
)
def test_strict_config_refutes_an_unknown_key_and_an_unknown_sandbox_mode(live, override, expected):
    """SD § 6.2: without this the sandbox key is a hopeful name rather than a verified one.

    Run on the shape nox actually emits — bare `codex exec` with the same
    hardening flags — because a refutation on a sibling subcommand would prove
    nothing about the launch this adapter builds.
    """
    info, ws = live
    argv = (resolve_executable(BINARY, ws.env), "exec", *CONFIG_FLAGS, "-c", override, TRIVIAL_PROMPT)
    proc = SubprocessRunner().spawn(Invocation(argv=argv, cwd=ws.path, env=ws.env))
    collected: list[str] = []
    result = supervise(
        proc,
        TimeoutPolicy.for_kind(info.heartbeat_kind, 120),
        _heartbeat(info),
        _collector(collected),
    )
    assert result.exit_code not in (0, None)
    assert any(expected in line for line in collected), collected


# ---------------------------------------------------------------------------
# C-1040: the probe against the live sandbox
# ---------------------------------------------------------------------------


def test_the_sandbox_probe_passes_against_the_live_binary(adapter, live):
    """C-1040/S-1002: the one observation no fixture can stand in for — the nonce is minted per run."""
    info, ws = live
    assert adapter.sandbox_probe(SubprocessRunner(), ws, info, dict(ws.env)) is True


def test_a_launch_authorized_after_the_probe_stamps_both_axes_os(adapter, live):
    """C-1007/C-1025: the `os` claim survives derivation only with a passing cached probe behind it."""
    info, ws = live
    cfg = HarnessConfig()
    plan = adapter.containment_plan(cfg, info)
    launch = adapter.prepare(ws, info, cfg, None)
    _, derived = authorize(adapter, launch, ws, info, plan, ProbeCache(), SubprocessRunner())
    assert derived.mechanism == "os-sandbox"
    assert derived.write_enforcement == "os"
    assert derived.network_enforcement == "os"
    assert f"sandbox_mode={SANDBOX_MODE}" in launch.argv


# ---------------------------------------------------------------------------
# S-1006 / SD § 9.4: the hostile branch through the real binary
# ---------------------------------------------------------------------------


def test_none_of_the_seven_hostile_files_executes_under_a_real_review(adapter, require_harness, tmp_path):
    """S-1006: the whole of § 9.4 on one branch, reviewed by the real adversary.

    `repo.markers` is the oracle — every hostile payload writes into it when it
    runs — and it is checked before the workspace exists, after the probe, after
    the review, and after teardown.
    """
    info = require_harness("codex")
    repo = make_repo(
        tmp_path,
        untracked=True,
        hostile_root=True,
        hostile_nested=True,
        symlink_members=True,
        escaping_symlinks=True,
        gitlink=True,
        gitattributes_filter=True,
        hooks_path=True,
        dot_nox=True,
    )
    assert list(repo.markers.iterdir()) == []
    cfg = HarnessConfig()
    with workspace(repo.path, _target()) as ws:
        plan = adapter.containment_plan(cfg, info)
        launch = adapter.prepare(ws, info, cfg, None)
        inv, _ = authorize(adapter, launch, ws, info, plan, ProbeCache(), SubprocessRunner())
        assert list(repo.markers.iterdir()) == [], "a payload ran during the sandbox probe"
        collected: list[str] = []
        hb = _heartbeat(info)
        result = supervise(
            SubprocessRunner().spawn(inv),
            TimeoutPolicy.for_kind(info.heartbeat_kind, cfg.timeout),
            hb,
            _collector(collected, adapter),
        )
        assert result.exit_code is not None, "the review never ran, so non-execution proves nothing"
        assert list(repo.markers.iterdir()) == [], "a payload ran during the review"
        # C-1010, off the real stream and not a fixture. `_collector` above was
        # handed the adapter, so the silence window this run was supervised
        # against is the shipped answer's — and this asserts the answer was not
        # a flat `False`, which would have killed the run at 120 s. `any`, not
        # `all`: C-1009 merges stderr in and those lines are honestly `False`.
        assert any(adapter.on_line(line) for line in collected), collected
        out = adapter.parse(collected, result.exit_code, hb)
        assert out.status in {"ok", "indeterminate"}
        # The turn this test already spends is the only place the emitted
        # `--output-schema` is put to the provider. Without this line a schema
        # the API refuses still satisfies every assertion above — no payload
        # runs during a review that 400s before the model reads the prompt —
        # and every real review would fail while this tier stayed green.
        assert SCHEMA_REJECTION not in out.raw, "the emitted --output-schema was refused; see _strict"
    assert list(repo.markers.iterdir()) == [], "a payload ran during teardown"


def test_the_emitted_output_schema_is_strict_at_every_level(adapter, live):
    """E3: the recorded refusal, and the two keys that answer it.

    `output-schema-rejected-0.144.1.jsonl` is what this adapter emitted before
    `_strict` existed: a 400 `invalid_json_schema` naming `additionalProperties`,
    raised before the model saw the prompt. The unit tier compared property key
    sets and passed it, because the defect is in what the document OMITS.
    """
    recorded = (FIXTURES / "output-schema-rejected-0.144.1.jsonl").read_text(encoding="utf-8")
    assert SCHEMA_REJECTION in recorded
    assert "'additionalProperties' is required to be supplied and to be false" in recorded

    info, ws = live
    adapter.prepare(ws, info, HarnessConfig(), None)
    schema = json.loads((ws.scratch / SCHEMA_FILENAME).read_text(encoding="utf-8"))
    for level in (schema, schema["properties"]["findings"]["items"]):
        assert level["additionalProperties"] is False
        assert set(level["required"]) == set(level["properties"])


# ---------------------------------------------------------------------------
# C-1009 / C-1010: the SIGTERM path through a real spawn
# ---------------------------------------------------------------------------


def test_a_review_that_times_out_leaves_no_process_in_the_group(adapter, live):
    """C-1009/C-1010: the group is signalled on every forced path, and this is that path.

    The assertion is about the process GROUP and nothing wider: D-ac's two
    residuals — a descendant backgrounded across a clean exit, and one that
    called `setsid()` — are accepted and open, and neither is claimed closed
    here or anywhere in this adapter.
    """
    info, ws = live
    cfg = HarnessConfig()
    plan = adapter.containment_plan(cfg, info)
    launch = adapter.prepare(ws, info, cfg, None)
    inv, _ = authorize(adapter, launch, ws, info, plan, ProbeCache(), SubprocessRunner())
    proc = SubprocessRunner().spawn(inv)
    result = supervise(
        proc,
        TimeoutPolicy(wall_clock_s=5, silence_s=None, grace_s=2.0),
        _heartbeat(info),
        lambda line: True,
    )
    assert result.reason is FailureReason.TIMED_OUT
    with pytest.raises(ProcessLookupError):
        os.killpg(proc.pid, 0)
