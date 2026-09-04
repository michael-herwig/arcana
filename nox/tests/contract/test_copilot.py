"""The copilot adapter against the real GitHub Copilot CLI (C-1037).

Runs only under `NOX_CONTRACT=1`, and fails rather than skips under
`NOX_RELEASE=1` — `conftest.py` owns both rules. What is here is the half the
unit tier structurally cannot prove: the unit suite asserts this adapter against
*recorded* fixtures, and a fixture is a claim about a binary that may have moved
since it was recorded (E3).

**One live review, reused.** The § 9.4 run is module-scoped: it costs AI credits
and about a minute, and every assertion that needs a real review reads the same
one. Everything provable without spawning the model — the argv, the derivation,
the passthrough refusals, the flag names against a live `--help` — spawns
nothing or spawns only `--help`. The timeout leg is the one deliberate second
billed run: it cannot share the first, because it needs a turn that is still
running when the deadline fires.

**Three of step 7x.4's assertions are proven elsewhere and deliberately not
restated here**, because each holds before any harness is spawned and a copy
would drift: the `.gitattributes` smudge-driver negative and the submodule
negative are `tests/acceptance/test_adversarial_fixture.py`'s
(`test_the_gitattributes_smudge_driver_never_runs_during_worktree_add`,
`test_the_submodule_surface_is_gone`), and the auth/quota classification
negative is the unit tier's `test_the_classify_table_is_empty_and_declines_every_shape`
— 1.0.82 emits no error-typed event, so `CLASSIFY` is empty and every
unrecorded shape resolves `indeterminate`. The one auth shape that WAS recorded
by this suite is `fixtures/copilot/error-unauthenticated-1.0.82.txt`, and
mapping it needs an owner decision that `PROVENANCE.md` states.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest

from nox.adapters.copilot import (
    BINARY,
    CONTAINMENT_ARGV,
    DENIED_TOOLS,
    MAX_AI_CREDITS,
    PINNED_TOOLS,
    REVIEW_TOOLS,
    VERIFIED_AGAINST,
    CopilotAdapter,
)
from nox.capability import Capability
from nox.config import ConfigError, HarnessConfig
from nox.harness import (
    NEVER_EMITTED,
    ContainmentPlan,
    ProbeCache,
    UnsupportedCapability,
    authorize,
    police_passthrough,
)
from nox.liveness import Heartbeat, Liveness, TimeoutPolicy
from nox.outcome import FailureReason
from nox.runner import SubprocessRunner, Supervision, supervise
from nox.workspace import ReviewTarget, workspace
from tests.fixtures.repo import HOSTILE_FILES, make_repo

if TYPE_CHECKING:
    from collections.abc import Callable

    from nox.harness import HarnessInfo, ParsedOutput

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "copilot"

REVIEW_TIMEOUT_S = 300
"""Wall clock for the one live review. Generous: this is a real model turn, not a unit test."""

AUTH_SKIP = (
    "copilot found no credential under $HOME/.copilot/, and C-1008 drops the environment token "
    "by construction (ALLOWLIST miss AND DENY_PATTERNS *_TOKEN/GH_*/GITHUB_*). Run `copilot` "
    "and `/login` to write the OAuth store, which minimal_env forwards HOME for."
)
"""Every live leg's skip reason, so the remedy is stated once.

Reached only on a machine that has genuinely never run `/login`. Until the
`nox_env` fix it fired on every live leg of this file on a machine whose store
was present, because the fixture environment pointed `HOME` at a throwaway
directory — eight skips reading as a missing login, and eight legs proving
nothing about the binary they claimed to pin. `tests/unit/test_hygiene.py`
greps for the shape so it cannot come back silently.
"""

UNAUTHENTICATED_SHAPE = "No authentication information found."
"""The first line of `error-unauthenticated-1.0.82.txt`, recorded off this very suite.

Matched HERE and not in the adapter: mapping it to `UNAUTHENTICATED` there needs
a substring match on a harness's message, which `Adapter.classify` forbids on its
own authority. A test may recognize a shape it refuses to skip blindly past; an
adapter may not turn one into a `FailureReason` without a decision.
"""


class LiveReview(NamedTuple):
    """One real review, and the argv that produced it."""

    parsed: ParsedOutput
    argv: tuple[str, ...]
    lines: tuple[str, ...]
    derived: ContainmentPlan
    markers: Path
    supervision: Supervision


def _help_text(info: HarnessInfo) -> str:
    """Run the real `--help` and return its output. Costs no AI credits."""
    argv = [*info.launcher.prefix, info.launcher.binary, "--help"]
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=60).stdout


@pytest.fixture
def info(require_harness: Callable[[str], HarnessInfo]) -> HarnessInfo:
    """The real probe: `copilot --version` under the C-1008 environment in a nox-minted cwd.

    Through `conftest.py`'s own fixture, which is what applies C-1037's
    skip-or-fail rule — an absent binary skips under `NOX_CONTRACT=1` and fails
    under `NOX_RELEASE=1`.
    """
    return require_harness("copilot")


_LIVE: dict[str, LiveReview] = {}
"""The one live review, cached across this module's tests.

A module-scoped fixture cannot take `require_harness`, which is function-scoped
and owns the C-1037 gate; a dict is cheaper than restating that gate at a wider
scope, and the run costs AI credits and about a minute.
"""


@pytest.fixture
def live(info: HarnessInfo, tmp_path_factory: pytest.TempPathFactory) -> LiveReview:
    """One real review of the SD § 9.4 hostile repository, through the whole gate.

    The path a review actually takes, minus `api.review()` (WP8): workspace,
    `prepare`, `containment_plan`, `authorize`, a real spawn under `supervise`,
    and `parse`. Every assertion below that needs a live harness reads this.
    """
    if "review" in _LIVE:
        return _LIVE["review"]
    repo = tmp_path_factory.mktemp("hostile")
    fixture = make_repo(repo, hostile_root=True, hostile_nested=True)
    adapter = CopilotAdapter()
    cfg = HarnessConfig(model="deep-reasoning")
    with workspace(fixture.path, ReviewTarget(kind="ref", ref="HEAD")) as ws:
        launch = adapter.prepare(ws, info, cfg, None)
        plan = adapter.containment_plan(cfg, info)
        runner = SubprocessRunner()
        inv, derived = authorize(adapter, launch, ws, info, plan, ProbeCache(), runner)
        heartbeat = Heartbeat(kind=info.heartbeat_kind, last_activity_at=0.0, last_byte_at=0.0)
        collected: list[str] = []

        def on_line(line: str) -> bool:
            """`supervise` hands every line here; the caller is what accumulates them.

            The honest answer to "was this a SEMANTIC event": a decodable JSONL
            object is progress, the merged stderr footer is not. Written here
            because the `Adapter` protocol has no member for it — reported as a
            cross-WP finding rather than invented as a seventh adapter method.
            """
            collected.append(line)
            try:
                return isinstance(json.loads(line), dict)
            except ValueError:
                return False

        supervision = supervise(
            runner.spawn(inv),
            TimeoutPolicy.for_kind(info.heartbeat_kind, REVIEW_TIMEOUT_S),
            heartbeat,
            on_line,
        )
        parsed = adapter.parse(collected, supervision.exit_code or 0, heartbeat)
    if UNAUTHENTICATED_SHAPE in parsed.raw:
        # C-1008 working, not failing: an environment token is dropped by
        # `ALLOWLIST` and `DENY_PATTERNS` twice over, and forwarding one would
        # put a credential VALUE across the boundary (C-1002). The route that
        # works is the harness's own store under `$HOME/.copilot/`, and `HOME`
        # is forwarded — so reaching this line means the store is genuinely
        # absent, not that nox hid it. Skipped rather than failed because the
        # adapter is not what is unproven here; the machine is.
        pytest.skip(AUTH_SKIP)
    _LIVE["review"] = LiveReview(
        parsed=parsed,
        argv=inv.argv,
        lines=tuple(collected),
        derived=derived,
        markers=fixture.markers,
        supervision=supervision,
    )
    return _LIVE["review"]


# ---------------------------------------------------------------------------
# The probe and the recorded literals, against the binary that is installed now
# ---------------------------------------------------------------------------


def test_the_installed_binary_is_the_version_every_fixture_was_recorded_from(info: HarnessInfo) -> None:
    """C-1020/E3: a fixture is a claim about a binary, and this is where the claim is re-checked.

    A mismatch is a warning in production (C-1020 never refuses on version) and
    a FAILURE here: the contract tier's whole job is to notice that the recorded
    evidence has gone stale.
    """
    assert info.version == VERIFIED_AGAINST
    assert info.name == "copilot"
    assert info.heartbeat_kind is Liveness.SEMANTIC


def test_the_probe_declares_exactly_the_two_capabilities_this_harness_holds(info: HarnessInfo) -> None:
    """C-1013/D-ab: `ENUMERABLE_DENY` natively, `ENFORCED_READ_ONLY` by allowlist, no `STRUCTURED_OUTPUT`."""
    assert info.capabilities == frozenset({Capability.ENUMERABLE_DENY, Capability.ENFORCED_READ_ONLY})
    assert Capability.STRUCTURED_OUTPUT not in info.capabilities


@pytest.mark.parametrize(
    "flag",
    [
        "--available-tools",
        "--deny-tool",
        "--disable-builtin-mcps",
        "--no-custom-instructions",
        "--max-ai-credits",
        "--output-format",
        "--log-level",
        "--no-color",
        "--model",
        "--effort",
        "-p",
    ],
)
def test_every_flag_this_adapter_emits_is_still_in_the_live_help(info: HarnessInfo, flag: str) -> None:
    """E3: the unit tier checks the RECORDED help; this checks the installed one.

    A flag renamed in a patch release is a launch that refuses at runtime, and
    R15 names exactly that as this harness's residual — its containment is
    flags, so a flag rename removes half of it.
    """
    assert f"\n  {flag}" in _help_text(info), flag


def test_the_recorded_help_is_byte_for_byte_the_installed_one(info: HarnessInfo) -> None:
    """E3: `verified_against` is only meaningful while the fixture it was read from is current.

    The whole text, not a flag sample: the fixture is what every unit-tier
    assertion about a flag name is measured against, and a release that changed
    a flag's ARGUMENT or removed an option this adapter does not yet emit is
    exactly the drift a spot check misses.
    """
    recorded = (FIXTURES / f"help-{VERIFIED_AGAINST}.txt").read_text(encoding="utf-8")
    assert recorded.strip(), "an empty fixture would pass silently"
    assert _help_text(info).strip() == recorded.strip()


# ---------------------------------------------------------------------------
# Passthrough — C-1023, against the real allowlist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "element",
    ["--allow-all-tools", "--allow-all-paths", "--add-dir", "--experimental", "--allow-tool", "--resume"],
)
def test_the_sd_named_flags_are_refused_from_passthrough(element: str) -> None:
    """C-1023: the words that lift this harness's containment, refused by name before any argv is built."""
    with pytest.raises(ConfigError) as exc:
        police_passthrough("copilot", [element], list(CONTAINMENT_ARGV))
    assert element in str(exc.value)


# ---------------------------------------------------------------------------
# The live review — C-1003, C-1005, C-1011, C-1025, S-1015, § 9.4
# ---------------------------------------------------------------------------


def test_none_of_the_hostile_fixtures_seven_executed_during_the_review(live: LiveReview) -> None:
    """SD § 9.4: the fixture's payloads each drop a marker file when they run. None may."""
    assert sorted(path.name for path in live.markers.iterdir()) == []


def test_the_resolved_argv_carries_no_word_that_lifts_containment(live: LiveReview) -> None:
    """S-1015/D-ab: matched bare and on the token before `=`, since `--add-dir=/etc` is `--add-dir` to the parser."""
    # Read off the shipped set, never restated: a hand-written copy here drifts
    # silently every time `NEVER_EMITTED` grows, which is exactly what it did.
    forbidden = NEVER_EMITTED | {"--resume", "-r"}
    for word in live.argv:
        assert word not in forbidden, word
        assert word.split("=", 1)[0] not in forbidden, word


def test_the_argv_the_gate_authorized_ends_in_the_containment_run(live: LiveReview) -> None:
    """C-1025 rule 2: the evidence run is the argv's tail after `authorize` resolved `argv[0]`."""
    assert live.argv[-len(CONTAINMENT_ARGV) :] == CONTAINMENT_ARGV
    assert "--max-ai-credits" in live.argv
    assert MAX_AI_CREDITS in live.argv


def test_the_derived_containment_stamps_harness_on_both_axes_and_never_os(live: LiveReview) -> None:
    """D-ab/R15: copilot's MXC sandbox is experimental and off by default, so `os` is unreachable in v1."""
    assert live.derived.mechanism == "tool-removal"
    assert (live.derived.write_enforcement, live.derived.network_enforcement) == ("harness", "harness")


def test_the_review_resolved_a_verdict_or_an_honest_indeterminate_and_never_a_guess(live: LiveReview) -> None:
    """C-1011: the tri-state, over a real model turn. `raw` is retained either way (C-1018)."""
    assert live.parsed.status in {"ok", "indeterminate"}
    assert live.parsed.raw, "C-1018 retains the output unconditionally"
    assert '"type":"result"' in live.parsed.raw.replace(" ", ""), (
        "a run that never reached the model would make every assertion below vacuous"
    )
    assert live.supervision.reason is None, live.supervision.detail
    if live.parsed.status == "ok":
        assert live.parsed.verdict in {"approve", "needs-attention"}
    else:
        assert live.parsed.verdict is None


def test_the_adapters_own_liveness_answer_is_true_somewhere_in_the_real_stream(live: LiveReview) -> None:
    """C-1010, off the real stream: the fixture's own `on_line` calls a decodable line progress.

    That closure is the caller's accumulator, not the adapter's answer, so
    without this the shipped `CopilotAdapter.on_line` is proven only against
    recorded lines. `HEARTBEAT_KIND` is `SEMANTIC`, so an adapter that never
    says `True` has every review killed at the silence window while it works.
    `any`, not `all`: the merged stream carries the harness's stderr footer,
    which is honestly `False`.
    """
    assert any(CopilotAdapter().on_line(line) for line in live.lines), live.lines


def test_the_live_review_reports_no_cost_because_this_harness_bills_credits(live: LiveReview) -> None:
    """C-1035: `result.usage` carries `premiumRequests` and durations and no money figure at all."""
    assert live.parsed.cost_usd is None


def test_the_prompt_told_the_reviewer_which_paths_were_neutralized(live: LiveReview) -> None:
    """C-1028: the prompt rides argv for this harness, so the C-1005 notice is visible in the argv itself."""
    prompt = live.argv[live.argv.index("-p") + 1]
    assert "CLAUDE.md" in prompt, "a hostile fixture whose neutralized list is empty proves nothing"
    for rel in HOSTILE_FILES:
        assert rel not in prompt.split("\n\n")[0], rel


def test_a_plan_claiming_an_os_axis_refuses_the_launch_for_this_adapter(info: HarnessInfo, tmp_path: Path) -> None:
    """D-ab/C-1007: `sandbox_probe` returns `False` unconditionally, so an `os` claim cannot be corroborated.

    And an uncorroborated axis is not a weaker level standing in — `authorize`
    nulls both and `check_capabilities` then refuses the launch outright. The
    refusal, not a downgraded stamp, is what makes `os` unreachable here.
    """
    adapter = CopilotAdapter()
    cfg = HarnessConfig()
    fixture = make_repo(tmp_path / "plain")
    with workspace(fixture.path, ReviewTarget(kind="ref", ref="HEAD")) as ws:
        launch = adapter.prepare(ws, info, cfg, None)
        claiming_os = ContainmentPlan(
            mechanism="tool-removal",
            write_enforcement="os",
            network_enforcement="os",
            argv_evidence=CONTAINMENT_ARGV,
        )
        with pytest.raises(UnsupportedCapability) as exc:
            authorize(adapter, launch, ws, info, claiming_os, ProbeCache(), SubprocessRunner())
    assert "write and network" in str(exc.value)


# ---------------------------------------------------------------------------
# The tool surface — C-1013, and the finding that forced `--available-tools`
# ---------------------------------------------------------------------------


def test_the_recorded_tool_visibility_table_still_says_deny_alone_does_not_remove(info: HarnessInfo) -> None:
    """C-1013: `--deny-tool` is a PERMISSION control (17 offered); `--available-tools` is the removal one (3).

    Pinned as a committed table rather than re-derived, because reading the
    model's offered tool list needs `--log-level debug` and a second billed run.
    If a release makes `--deny-tool` remove tools, this table is what a re-probe
    is measured against.
    """
    del info
    table = (FIXTURES / f"tool-visibility-{VERIFIED_AGAINST}.txt").read_text(encoding="utf-8")
    rows = [line.split("\t") for line in table.splitlines() if line and not line.startswith("#")]
    counts = {row[0]: row[1] for row in rows}
    assert counts["deny only"] == "17", "a release where deny alone removes tools is a re-probe, not a pass"
    assert counts["shipped shape"] == str(len(REVIEW_TOOLS))
    assert len(PINNED_TOOLS) == len(REVIEW_TOOLS) + len(DENIED_TOOLS)


def test_the_binary_is_reachable_under_the_name_this_adapter_spawns(info: HarnessInfo) -> None:
    """C-1037(2): `BINARY` is readable without a successful probe, and it is what the absence message names."""
    assert info.launcher.binary == BINARY


def test_a_review_that_outruns_its_wall_clock_is_killed_and_leaves_no_descendant(
    info: HarnessInfo, tmp_path: Path
) -> None:
    """7x.4: the SIGTERM-timeout path through the REAL spawn, and the harness proven gone after it.

    A five-second wall clock against a real model turn: `supervise` runs its
    SIGTERM → grace → SIGKILL ladder against the child's process GROUP, which is
    the whole point of `start_new_session` — a harness that spawned helpers must
    not leave one writing into a worktree the caller is about to remove.

    Skips, like every other live leg here, when nox's own C-1008 environment
    cannot carry this machine's copilot credential: an unauthenticated binary
    exits in about a second and would never reach the deadline, so the assertion
    would be vacuous rather than failing.
    """
    fixture = make_repo(tmp_path / "slow", hostile_root=True)
    adapter = CopilotAdapter()
    cfg = HarnessConfig(model="deep-reasoning")
    with workspace(fixture.path, ReviewTarget(kind="ref", ref="HEAD")) as ws:
        runner = SubprocessRunner()
        inv, _ = authorize(
            adapter,
            adapter.prepare(ws, info, cfg, None),
            ws,
            info,
            adapter.containment_plan(cfg, info),
            ProbeCache(),
            runner,
        )
        heartbeat = Heartbeat(kind=info.heartbeat_kind, last_activity_at=0.0, last_byte_at=0.0)
        seen: list[str] = []

        def collect(line: str) -> bool:
            seen.append(line)
            return True

        process = runner.spawn(inv)
        pid = process.pid
        supervision = supervise(process, TimeoutPolicy(wall_clock_s=5, silence_s=None), heartbeat, collect)
    if UNAUTHENTICATED_SHAPE in "".join(seen):
        pytest.skip(AUTH_SKIP)
    assert supervision.reason is FailureReason.TIMED_OUT, supervision.detail
    with pytest.raises(ProcessLookupError):
        # The group, not the pid: signal 0 on a reaped leader whose group still
        # holds a member would succeed, which is the leak this asserts against.
        os.killpg(pid, 0)
