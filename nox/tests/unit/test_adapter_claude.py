"""The Claude Code adapter: argv shape, containment claim, probe, output dialect.

C-1007(claude), C-1010, C-1011, C-1012(claude), C-1014, C-1016, C-1018, C-1019,
C-1020, C-1023, C-1025, C-1028, C-1030(claude), C-1032, C-1035, D-ac, E3,
S-1001, S-1007, S-1008, S-1009, and WP5's schema-drift carry-forward row.

Every parse assertion is written against a stream RECORDED from 2.1.260
(`tests/contract/fixtures/claude/`) — bar the 429, whose live rate limit cannot
be summoned to order and which therefore keeps its 2.1.259 capture (E30, and
`VERIFIED_AGAINST` says why) — never against a shape invented here: the
401 fixture's terminal event reads `"subtype": "success"` while `"is_error"` is
true, and an adapter keyed on `subtype` reports an authentication failure as a
clean review. Only the untrusted-field normalization cases are synthetic, and
they say so: no recorded run happened to invent a severity word.

The containment assertions are written so a *membership* implementation of the
argv fails them: the evidence run must be contiguous, terminated, and identical
to the words `prepare` emits.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path

import pytest

from nox import harness as harness_mod
from nox.adapters.claude import (
    CONFIG_READS,
    MODELS,
    READ_ONLY_TOOLS,
    VERIFIED_AGAINST,
    WIRE_JSON_SCHEMA,
    ClaudeAdapter,
    containment_argv,
    logged_out,
    parse_version,
)
from nox.capability import Capability, Launcher, ModelClass, ModelSpec, ModelSpecT
from nox.config import ConfigError
from nox.harness import (
    NEVER_EMITTED,
    PASSTHROUGH_ALLOW,
    HarnessUnavailable,
    ParsedOutput,
    ProbeCache,
    authorize,
    derive_containment,
    probe_harness,
    resolve_model,
    version_warning,
)
from nox.liveness import Heartbeat, Liveness
from nox.outcome import FailureReason
from nox.prompt import WIRE_SCHEMA, Scope
from nox.runner import Invocation
from nox.workspace import Workspace
from tests.unit.stubs import FakeProcess, FakeRunner, config, info_for

# Resolved from this file, never from the cwd: the recorded fixtures belong to
# the nox subtree whether pytest was invoked from the repo root or from nox/.
NOX = Path(__file__).resolve().parents[2]
FIXTURES = NOX / "tests" / "contract" / "fixtures" / "claude"
ADAPTER_SOURCE = NOX / "src" / "nox" / "adapters" / "claude.py"

EVIDENCE = (
    "--safe-mode",
    "--restricted",
    "--strict-mcp-config",
    "--permission-prompts",
    "none",
    "--tools",
    "Read,Grep,Glob",
)
"""The containment run, spelled out here rather than imported from the adapter.

A test that derives its expectation from the code under test proves only
self-consistency, and this is the one run C-1025 derives both enforcement axes
from.
"""

FORBIDDEN_LIFETIME_CLAIMS = (
    "cannot outlive",
    "outlive the review",
    "no surviving",
    "no descendant survives",
    "no process survives",
    "terminates every descendant",
    "kills every descendant",
    "bounds process lifetime",
)
"""Phrasings D-ac forbids this adapter's prose from carrying.

Neither enforcement axis says anything about how long a descendant lives, and
`runner.py` names two open holes. A sentence here that read otherwise would be
the claim D-ac declined to add as a third axis, smuggled back in as prose.
"""

ALIAS_LINE = re.compile(r"^ {2}(-[^\s,]+(?:,\s*-[^\s,]+)+)", re.MULTILINE)
"""One `--help` option line listing a flag under two or more spellings.

Anchored at exactly two spaces so a wrapped description line naming other flags
(`                    --settings, --agents, --plugin-dir.`) is not read as an
alias group.
"""


# ---------------------------------------------------------------------------
# Builders. Nothing here derives an expectation from the code under test.
# ---------------------------------------------------------------------------


WS_DIFF: str = (
    "diff --git a/billing.py b/billing.py\n"
    "@@ -1,3 +1,2 @@\n"
    "-    if not items:\n"
    "-        return 0\n"
    "     return sum(item.amount for item in items) / len(items)\n"
)
"""The change the stub workspace carries — what `review_prompt` must put in the prompt.

Not a placeholder: three of the four adapters deliver the diff by NO other route,
so "the argv carries this text" is the assertion that the reviewer is reviewing a
change rather than a snapshot of the after state.
"""


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _stream(name: str) -> list[str]:
    return _fixture(name).splitlines()


def _terminal(name: str) -> dict:
    """The last decodable JSON object of a recorded stream."""
    for line in reversed(_stream(name)):
        try:
            decoded = json.loads(line)
        except ValueError:
            continue
        if isinstance(decoded, dict):
            return decoded
    raise AssertionError(f"{name} carries no JSON object")


def _hb() -> Heartbeat:
    return Heartbeat(kind=Liveness.SEMANTIC, last_activity_at=0.0, last_byte_at=0.0)


def _bin(tmp_path: Path, *names: str) -> Path:
    """A directory holding an executable per name, for the minimal `PATH`."""
    directory = tmp_path / "bin"
    directory.mkdir(exist_ok=True)
    for name in names:
        path = directory / name
        path.write_bytes(b"#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    return directory


def _info(**overrides):
    defaults = {
        "capabilities": frozenset(
            {Capability.ENUMERABLE_DENY, Capability.ENFORCED_READ_ONLY, Capability.STRUCTURED_OUTPUT}
        ),
        "version": VERIFIED_AGAINST,
        "verified_against": VERIFIED_AGAINST,
        "launcher": Launcher(binary="claude"),
    }
    return info_for("claude", **{**defaults, **overrides})


def _workspace(tmp_path: Path, *, env=None, scope: Scope = "code-diff") -> Workspace:
    root = tmp_path / "ws"
    scratch = root / ".nox-tok"
    scratch.mkdir(parents=True, exist_ok=True)
    return Workspace(
        path=root,
        token="tok",
        base="base-sha",
        target="target-sha",
        scratch=scratch,
        diff_path=scratch / "review.diff",
        diff=WS_DIFF,
        env={"PATH": "/nonexistent-bin"} if env is None else env,
        neutralized=(),
        filtered=(),
        filtered_changed=(),
        omitted=(),
        omitted_ignored=0,
        scope=scope,
        neutralized_total=0,
        filtered_total=0,
        filtered_changed_total=0,
        omitted_total=0,
    )


def _launch(tmp_path: Path, cfg=None, *, instructions=None, scope: Scope = "code-diff"):
    """`prepare`'s output for a live workspace, with the workspace beside it."""
    ws = _workspace(tmp_path, scope=scope)
    launch = ClaudeAdapter().prepare(ws, _info(), cfg if cfg is not None else config(), instructions)
    return launch, ws


def _run_index(argv: tuple[str, ...], run: tuple[str, ...]) -> int:
    """Where `run` appears contiguously and in order inside `argv`, or -1."""
    width = len(run)
    for start in range(len(argv) - width + 1):
        if argv[start : start + width] == run:
            return start
    return -1


def _probe_runner(
    *,
    version_lines=("2.1.260 (Claude Code)",),
    version_exit: int = 0,
    auth_text: str | None = None,
    auth_exit: int = 0,
) -> FakeRunner:
    auth = _fixture("auth-status-2.1.260.json") if auth_text is None else auth_text
    return FakeRunner(FakeProcess(version_lines, version_exit), FakeProcess(auth.splitlines(), auth_exit))


class TrickleProcess:
    """A `Process` that hands over ONE line per poll and exits only after the last one.

    `FakeProcess` queues every line before the first poll, so it cannot tell a
    supervised probe from a probe that drained once and reaped after: both read
    the whole object. A real child does not oblige — `Process.lines` returns as
    soon as the queue is momentarily non-empty, and `Process.wait` is the call
    carrying the tail guarantee.
    """

    def __init__(self, lines, exit_code: int = 0) -> None:
        self._lines = list(lines)
        self._exit_code = exit_code

    @property
    def pid(self) -> int:
        return 4243

    @property
    def collector_failure(self):
        return None

    @property
    def overflowed(self) -> bool:
        return False

    def lines(self, timeout):
        del timeout
        return (self._lines.pop(0),) if self._lines else ()

    def wait(self, timeout):
        del timeout
        return self._exit_code if not self._lines else None


def _terminal_event(**overrides) -> list[str]:
    """The synthetic terminal event with EVENT-level fields overridden.

    `_structured` overrides the wire object; this overrides the envelope around
    it — `is_error`, `total_cost_usd`, the classification fields.
    """
    event = json.loads(_structured()[0])
    return [json.dumps({**event, **overrides})]


def _structured(**overrides) -> list[str]:
    """One synthetic terminal event carrying a `structured_output` object.

    Synthetic on purpose, and the only synthetic stream in this file: no
    recorded 2.1.260 run happened to invent a severity word or hand back a
    traversing path, and those are exactly the untrusted-field branches
    `parse` owes an answer for.
    """
    finding = {
        "severity": "high",
        "title": "a title",
        "body": "a body",
        "file": "src/app.py",
        "line_start": 3,
        "line_end": 4,
        "confidence": "high",
        "recommendation": "do the thing",
        **overrides.pop("finding", {}),
    }
    payload = {
        "verdict": "approve",
        "summary": "a summary",
        "findings": [finding],
        "next_steps": ["MARKER-NEXT-STEP-9137"],
        **overrides,
    }
    event = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "api_error_status": None,
        "total_cost_usd": 0.25,
        "structured_output": payload,
    }
    return [json.dumps(event)]


def _parse(lines, exit_code: int = 0) -> ParsedOutput:
    return ClaudeAdapter().parse(lines, exit_code, _hb())


# ---------------------------------------------------------------------------
# argv and containment: C-1007, C-1023, C-1025
# ---------------------------------------------------------------------------


def test_the_containment_run_is_the_flags_proven_against_the_installed_binary():
    """C-1025: the evidence run is a shipped literal, verbatim and in the order argv carries it."""
    assert containment_argv(config()) == EVIDENCE


def test_the_containment_plan_claims_tool_removal_on_both_axes_from_the_argv_run():
    """C-1007: both axes are `harness`, the evidence is the argv, and nothing rides the environment."""
    plan = ClaudeAdapter().containment_plan(config(), _info())
    assert plan.mechanism == "tool-removal"
    assert plan.write_enforcement == "harness"
    assert plan.network_enforcement == "harness"
    assert plan.argv_evidence == containment_argv(config())
    assert dict(plan.env_evidence) == {}


def test_prepare_emits_the_evidence_run_contiguously_and_terminated_by_a_dash_dash(tmp_path):
    """C-1025 rules 1 and 2: a scattered run corroborates nothing, and the successor must be `-`-prefixed."""
    launch, _ = _launch(tmp_path)
    start = _run_index(launch.argv, EVIDENCE)
    assert start >= 0, launch.argv
    assert launch.argv[start + len(EVIDENCE)] == "--"


def test_the_prompt_rides_stdin_and_appears_in_no_argv_word(tmp_path):
    """C-1028, E29: Claude Code reads its prompt from stdin, so the diff never becomes an argv word.

    Verified live before it was relied on:
    `echo … | claude --print --tools Read Grep Glob --` → exit 0.

    Both halves are asserted, because either alone passes a launch that also
    puts the prompt on the command line: the diff would then still be in
    `/proc/<pid>/cmdline` and still bounded by `MAX_ARG_STRLEN`.
    """
    launch, ws = _launch(tmp_path)
    prompt_path = ws.scratch / harness_mod.PROMPT_FILENAME
    assert launch.stdin_path == prompt_path
    assert prompt_path.read_text(encoding="utf-8") not in launch.argv
    assert launch.argv[-1] == "--", "option parsing still ends, and C-1025 rule 2 still has its successor"


def test_the_launch_declares_no_environment_at_all(tmp_path):
    """C-1008: this harness's containment is argv only, so there is nothing for `authorize` to refuse."""
    launch, _ = _launch(tmp_path)
    assert dict(launch.env) == {}


def test_a_diff_far_over_the_argv_limit_still_prepares(tmp_path):
    """E29: the argv limit is a property of the argv channel, and this harness does not use it.

    The whole finding in one adapter. A whole-branch review is the first case
    that clears `MAX_ARG_STRLEN` — the feature branch this was found on diffs at
    2.8 MB — and it is also nox's primary use case, so a refusal here would make
    the tool unusable for what it is for.
    """
    ws = _workspace(tmp_path)
    object.__setattr__(ws, "diff", "+" + "a" * (harness_mod.PROMPT_ARGV_LIMIT * 2))

    launch = ClaudeAdapter().prepare(ws, _info(), config(), None)

    assert launch.stdin_path is not None
    assert max(len(word.encode("utf-8")) for word in launch.argv) < harness_mod.PROMPT_ARGV_LIMIT
    assert ws.diff in launch.stdin_path.read_text(encoding="utf-8"), "verbatim, never trimmed (C-1028)"


def test_authorize_derives_both_axes_harness_without_consulting_the_sandbox_probe(tmp_path):
    """C-1025: an adapter that claims no `os` axis is never probed, and evidence alone stamps `harness`."""

    class Recording(ClaudeAdapter):
        def __init__(self) -> None:
            self.sandbox_calls = 0

        def sandbox_probe(self, runner, ws, info, env):
            self.sandbox_calls += 1
            return super().sandbox_probe(runner, ws, info, env)

    adapter = Recording()
    ws = _workspace(tmp_path, env={"PATH": str(_bin(tmp_path, "claude"))})
    info = _info()
    cfg = config()
    plan = adapter.containment_plan(cfg, info)
    launch = adapter.prepare(ws, info, cfg, None)
    inv, derived = authorize(adapter, launch, ws, info, plan, ProbeCache(), FakeRunner())
    assert derived.write_enforcement == "harness"
    assert derived.network_enforcement == "harness"
    assert derived.mechanism == "tool-removal"
    assert adapter.sandbox_calls == 0
    assert _run_index(inv.argv, EVIDENCE) >= 0


def test_an_argv_that_appends_bash_after_the_tool_word_corroborates_neither_axis(tmp_path):
    """C-1025 rule 2, the whole point of derivation: every evidence word is present and shell is back."""
    plan = ClaudeAdapter().containment_plan(config(), _info())
    argv = ("/abs/claude", "--print", *EVIDENCE, "Bash", "--", "prompt")
    inv = Invocation(argv=argv, cwd=tmp_path, env={})
    derived = derive_containment(inv, plan, "digest-under-test", ProbeCache())
    assert derived.write_enforcement is None
    assert derived.network_enforcement is None


@pytest.mark.parametrize(
    "passthrough",
    [("--title", "x"), ("--settings", "{}")],
    ids=["benign-looking", "arbitrary-execution"],
)
def test_every_passthrough_element_is_refused_because_the_claude_allowlist_is_empty(tmp_path, passthrough):
    """C-1023: no repository-supplied word reaches this harness's argv at all."""
    assert PASSTHROUGH_ALLOW["claude"] == frozenset()
    with pytest.raises(ConfigError) as exc:
        _launch(tmp_path, config(passthrough=passthrough))
    assert passthrough[0] in str(exc.value)


def test_no_word_of_the_resolved_argv_lifts_a_containment_control(tmp_path):
    """C-1023: every `NEVER_EMITTED` member lifts a control the plan claims — `--bare` above all."""
    launch, _ = _launch(tmp_path)
    emitted = {word.split("=", 1)[0] for word in launch.argv}
    assert emitted & NEVER_EMITTED == set()


def test_a_configured_narrow_shrinks_the_tool_word():
    """C-1016: config may take tools away, and the evidence run says so."""
    assert containment_argv(config(tools_allowed=("Read",)))[-2:] == ("--tools", "Read")


def test_a_configured_narrow_may_not_restore_a_removed_tool():
    """C-1016: `tools_allowed` narrows the adapter's own set and can never widen it back to Bash."""
    with pytest.raises(ConfigError) as exc:
        containment_argv(config(tools_allowed=("Read", "Bash")))
    assert "Bash" in str(exc.value)


def test_an_explicit_empty_narrow_disables_every_tool_rather_than_reading_as_unset():
    """C-1016: `--tools ""` is a legal request; silently restoring the three defaults would widen it."""
    argv = containment_argv(config(tools_allowed=()))
    assert argv[-2:] == ("--tools", "")
    assert not any(tool in argv for tool in READ_ONLY_TOOLS)


def test_no_evidence_flag_has_a_second_spelling_the_evidence_run_omits():
    """C-1025's residual, discharged against the recorded `--help` rather than a docstring.

    Derivation matches argv words verbatim, so a flag the binary also accepts
    under a second name is an override that shares no word with the evidence
    and still passes all four rules. This reads the alias groups out of the
    2.1.260 `--help` and fails the day a new fixture introduces one for a flag
    nox emits as containment.
    """
    evidence = set(containment_argv(config()))
    groups = [
        tuple(word.strip() for word in match.group(1).split(","))
        for match in ALIAS_LINE.finditer(_fixture("help-2.1.260.txt"))
    ]
    assert groups, "the --help fixture parsed to no alias groups at all"
    for group in groups:
        if evidence & set(group):
            assert set(group) <= evidence, f"{group} is aliased and the evidence run names only part of it"


# ---------------------------------------------------------------------------
# Models: C-1030
# ---------------------------------------------------------------------------


def test_the_fast_balanced_class_resolves_the_haiku_literal_with_no_effort():
    """C-1030: a capability class, never a literal ID, and this is the one the live matrix drives."""
    spec, model_class = resolve_model(ClaudeAdapter.MODELS, config(model="fast-balanced"))
    assert spec == ModelSpecT(model="claude-haiku-4-5-20251001", effort=None)
    assert model_class == "fast-balanced"


def test_the_deep_reasoning_class_pairs_a_frontier_literal_with_an_effort_level():
    """C-1030: `--effort` is Claude Code's own reasoning knob, carried by the spec rather than the argv builder."""
    spec, model_class = resolve_model(ClaudeAdapter.MODELS, config(model="deep-reasoning"))
    assert spec == ModelSpecT(model="claude-opus-5", effort="high")
    assert model_class == "deep-reasoning"


def test_prepare_emits_the_model_literal_and_its_effort_level(tmp_path):
    """C-1030: the flags come from the shipped table, so no configured literal is needed to reach them."""
    launch, _ = _launch(tmp_path, config(model="deep-reasoning"))
    assert _run_index(launch.argv, ("--model", "claude-opus-5")) >= 0
    assert _run_index(launch.argv, ("--effort", "high")) >= 0


def test_prepare_emits_the_model_literal_without_an_effort_flag_when_the_spec_carries_none(tmp_path):
    """C-1030: `--effort` appears only when the spec has one — never as an invented default."""
    launch, _ = _launch(tmp_path, config(model="fast-balanced"))
    assert _run_index(launch.argv, ("--model", "claude-haiku-4-5-20251001")) >= 0
    assert "--effort" not in launch.argv


def test_prepare_emits_neither_flag_when_no_capability_class_is_configured(tmp_path):
    """C-1030 rule 2: the harness default is taken, and both flags are omitted entirely."""
    launch, _ = _launch(tmp_path)
    assert "--model" not in launch.argv
    assert "--effort" not in launch.argv


def test_a_class_absent_from_the_table_takes_the_harness_default_and_records_no_model():
    """C-1030 rule 6: not an error and not a substitution from the other class — the harness chose.

    The shipped table is not weakened to reach this; a copy of it missing one
    class is, because the property is `resolve_model`'s answer to a gap, not a
    claim about what Claude Code supports.
    """
    partial: Mapping[ModelClass, ModelSpec] = {
        name: spec for name, spec in ClaudeAdapter.MODELS.items() if name != "fast-balanced"
    }
    spec, model_class = resolve_model(partial, config(model="fast-balanced"))
    assert spec is None
    assert model_class == "fast-balanced"


@pytest.mark.parametrize("model_class", sorted(MODELS))
def test_every_shipped_literal_is_a_usable_argv_word(model_class):
    """C-1030: a literal starting with `-` or carrying whitespace reaches `Popen` as an option."""
    spec = ModelSpecT.of(MODELS[model_class])
    assert spec.model
    assert not spec.model.startswith("-")
    assert spec.model == spec.model.strip()
    assert not any(char.isspace() for char in spec.model)


# ---------------------------------------------------------------------------
# The probe: C-1014, C-1020, C-1035
# ---------------------------------------------------------------------------


def test_the_probe_establishes_the_version_capabilities_and_liveness_kind(tmp_path):
    """C-1014: two short local invocations, and every capability absent unless the probe established it."""
    runner = _probe_runner()
    info = probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(_bin(tmp_path, "claude"))})
    assert info.name == "claude"
    assert info.version == "2.1.260"
    assert info.verified_against == VERIFIED_AGAINST
    assert info.heartbeat_kind is Liveness.SEMANTIC
    assert info.capabilities == frozenset(
        {Capability.ENUMERABLE_DENY, Capability.ENFORCED_READ_ONLY, Capability.STRUCTURED_OUTPUT}
    )
    assert info.launcher == Launcher(binary="claude")


def test_the_probe_runs_version_first_in_the_empty_directory_nox_minted(tmp_path):
    """C-1014: a harness startup never sees repository content, and `probe_cwd` owns and removes the directory."""
    directory = _bin(tmp_path, "claude")
    runner = _probe_runner()
    probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(directory)})
    first = runner.spawned[0]
    assert first.argv[0] == str((directory / "claude").resolve())
    assert first.argv[1:] == ("--version",)
    assert first.cwd.is_absolute()
    assert first.cwd != Path.cwd()
    assert not first.cwd.exists(), "the minted probe directory outlived the probe"
    assert runner.spawned[1].cwd == first.cwd


def test_the_probe_reaches_the_binary_through_a_configured_launcher(tmp_path):
    """C-1014: the launcher prefix is the config's and the binary is the adapter's — `launcher_for` joins them."""
    directory = _bin(tmp_path, "claude", "ocx")
    runner = _probe_runner()
    cfg = config(launcher=("ocx", "exec", "--"))
    info = probe_harness(ClaudeAdapter(), runner, cfg, {"PATH": str(directory)})
    assert info.launcher == Launcher(binary="claude", prefix=("ocx", "exec", "--"))
    assert runner.spawned[0].argv[0] == str((directory / "ocx").resolve())
    assert runner.spawned[0].argv[1:] == ("exec", "--", "claude", "--version")


def test_a_version_line_naming_nothing_records_no_version_and_warns_about_nothing(tmp_path):
    """C-1020, C-1035: an unknown version is `None`, never a mismatch nox invented."""
    runner = _probe_runner(version_lines=("Claude Code",))
    info = probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(_bin(tmp_path, "claude"))})
    assert info.version is None
    assert version_warning(info) is None


def test_a_drifted_version_warns_and_names_both_releases(tmp_path):
    """C-1020: a warning, never a refusal — but a silent drift must not read as a verified run."""
    runner = _probe_runner(version_lines=("9.9.9 (Claude Code)",))
    info = probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(_bin(tmp_path, "claude"))})
    assert info.version == "9.9.9"
    warning = version_warning(info)
    assert warning is not None
    assert "9.9.9" in warning
    assert VERIFIED_AGAINST in warning


def test_a_logged_out_auth_status_refuses_before_a_review_begins(tmp_path):
    """C-1014, S-1008: the credential preflight buys latency — a 401 costs ~185 s of Claude Code's retry ladder."""
    runner = _probe_runner(auth_text=json.dumps({"loggedIn": False}))
    with pytest.raises(HarnessUnavailable) as exc:
        probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(_bin(tmp_path, "claude"))})
    assert exc.value.reason is FailureReason.UNAUTHENTICATED


def test_the_unauthenticated_refusal_carries_none_of_the_account_identity(tmp_path):
    """C-1035: `auth status` holds the account email, org id and org name; nox reads `loggedIn` and nothing else."""
    secrets = {
        "email": "NOX-SECRET-EMAIL@example.invalid",
        "orgId": "NOX-SECRET-ORG-ID",
        "orgName": "NOX-SECRET-ORG-NAME",
        "projectsDirectory": "NOX-SECRET-PROJECTS-DIR",
    }
    runner = _probe_runner(auth_text=json.dumps({"loggedIn": False, **secrets}))
    with pytest.raises(HarnessUnavailable) as exc:
        probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(_bin(tmp_path, "claude"))})
    for value in secrets.values():
        assert value not in str(exc.value)
        assert value not in exc.value.detail


@pytest.mark.parametrize(
    "auth_text",
    ["not json at all", "{}", '{"loggedIn": "yes"}', ""],
    ids=["non-json", "no-field", "wrong-type", "empty"],
)
def test_an_auth_status_shape_nox_cannot_read_is_not_evidence_of_a_missing_credential(tmp_path, auth_text):
    """C-1014: an availability preflight fails open — the review's own `classify` still catches a 401."""
    runner = _probe_runner(auth_text=auth_text)
    info = probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(_bin(tmp_path, "claude"))})
    assert info.version == "2.1.260"


def test_a_non_zero_auth_status_does_not_resolve_absent(tmp_path):
    """C-1014: `--version` already established runnability, so a failed preflight is not an absent binary."""
    runner = _probe_runner(auth_exit=1)
    info = probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(_bin(tmp_path, "claude"))})
    assert info.version == "2.1.260"


def test_a_binary_that_exists_and_cannot_run_is_absent(tmp_path):
    """C-1014, S-1007: this is what makes the probe more than `shutil.which`."""
    runner = _probe_runner(version_exit=1)
    with pytest.raises(HarnessUnavailable) as exc:
        probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(_bin(tmp_path, "claude"))})
    assert exc.value.reason is FailureReason.ABSENT


def test_the_binary_is_absent_when_the_minimal_path_does_not_carry_it(tmp_path):
    """C-1008, S-1007: the probe reads the rebuilt `PATH`, never `os.environ`."""
    with pytest.raises(HarnessUnavailable) as exc:
        probe_harness(ClaudeAdapter(), _probe_runner(), config(), {"PATH": str(tmp_path / "empty")})
    assert exc.value.reason is FailureReason.ABSENT


def test_the_sandbox_probe_refuses_in_one_line_because_this_adapter_claims_no_os_axis(tmp_path):
    """C-1025: the default answer is refusal, which is what makes "no sandbox probe means no `os`" structural."""
    ws = _workspace(tmp_path)
    assert ClaudeAdapter().sandbox_probe(FakeRunner(), ws, _info(), {}) is False


def test_parse_version_reads_the_dotted_release_out_of_the_recorded_line():
    """E3: the version is read from the binary's own output, never copied from a document."""
    assert parse_version(_fixture("version-2.1.260.txt")) == VERIFIED_AGAINST


def test_logged_out_reads_exactly_one_field_of_the_recorded_auth_object():
    """C-1035: the recorded fixture redacts the identity fields on purpose — only `loggedIn` is read."""
    assert logged_out(_fixture("auth-status-2.1.260.json")) is False
    assert logged_out(json.dumps({"loggedIn": True})) is False
    assert logged_out(json.dumps({"loggedIn": False})) is True


def test_an_advisory_line_ahead_of_the_auth_object_does_not_defeat_the_preflight():
    """C-1009, C-1014: stderr is merged into stdout, so the object is not the first thing on the stream.

    The recorded `error-401` fixture carries such an advisory. One of them ahead
    of the object is enough to make a whole-blob decode fail open on a harness
    that positively said it has no credential — which is the ~185 s the
    preflight exists to save, silently not saved.
    """
    advisory = "⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY is set\n"
    assert logged_out(advisory + json.dumps({"loggedIn": False}, indent=2)) is True
    assert logged_out(advisory + _fixture("auth-status-2.1.260.json")) is False
    assert logged_out(advisory) is False


def test_a_probe_whose_output_arrives_in_chunks_is_read_whole_before_it_is_reaped(tmp_path):
    """C-1014: `Process.wait` carries the tail guarantee and `Process.lines` does not.

    `auth status` prints its object across eleven lines. A probe that drained
    once and reaped afterwards read the first of them, `logged_out` failed open,
    and the credential preflight never fired.
    """
    auth = json.dumps({"loggedIn": False, "email": "NOX-SECRET-EMAIL@example.invalid"}, indent=2)
    runner = FakeRunner(
        TrickleProcess(["2.1.260 (Claude Code)\n"]),
        TrickleProcess(auth.splitlines(keepends=True)),
    )
    with pytest.raises(HarnessUnavailable) as exc:
        probe_harness(ClaudeAdapter(), runner, config(), {"PATH": str(_bin(tmp_path, "claude"))})
    assert exc.value.reason is FailureReason.UNAUTHENTICATED
    assert "NOX-SECRET-EMAIL@example.invalid" not in exc.value.detail


# ---------------------------------------------------------------------------
# parse: C-1011, C-1012, C-1018, C-1019
# ---------------------------------------------------------------------------


def test_a_recorded_successful_review_resolves_ok_with_its_verdict_summary_and_cost():
    """C-1011, S-1001: a well-formed `structured_output` on a non-error terminal event is the ONE route to `ok`."""
    terminal = _terminal("review-ok-2.1.260.jsonl")
    result = _parse(_stream("review-ok-2.1.260.jsonl"))
    assert result.status == "ok"
    assert result.verdict == terminal["structured_output"]["verdict"]
    assert result.summary == terminal["structured_output"]["summary"]
    assert result.cost_usd == terminal["total_cost_usd"]
    assert result.reason is None


def test_a_successful_review_retains_the_whole_stream_as_raw():
    """C-1018: `raw` is retained unconditionally; the byte cap travels separately as `Supervision.truncated`."""
    lines = _stream("review-ok-2.1.260.jsonl")
    result = _parse(lines)
    for line in lines:
        assert line in result.raw


def test_raw_reconstructs_the_stream_exactly_as_the_supervisor_delivered_it():
    """C-1018: a drained line keeps `readline`'s newline, so `raw` is the concatenation, not a re-join.

    `"\\n".join` over lines that already end in one puts a blank line between
    every record — a `raw` that is not what the harness wrote.
    """
    delivered = [f"{line}\n" for line in _stream("review-ok-2.1.260.jsonl")]
    assert _parse(delivered).raw == "".join(delivered)


def test_a_model_that_declined_to_call_structured_output_resolves_indeterminate():
    """C-1011: a real recorded shape, not a defensive branch — `is_error` is false and there is no object."""
    result = _parse(_stream("review-structured-output-null-2.1.260.jsonl"))
    assert result.status == "indeterminate"
    assert result.reason is FailureReason.MALFORMED_OUTPUT
    assert result.verdict is None
    for line in _stream("review-structured-output-null-2.1.260.jsonl"):
        assert line in result.raw


def test_an_explicit_null_structured_output_resolves_indeterminate_too():
    """C-1011: the docstring's "absent or `null`" — the recorded fixture proves absent, this proves null."""
    event = json.dumps(
        {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.1, "structured_output": None}
    )
    result = _parse([event])
    assert result.status == "indeterminate"
    assert result.reason is FailureReason.MALFORMED_OUTPUT


def test_a_recorded_401_run_resolves_error_and_unauthenticated():
    """C-1012, S-1008: the status is the field both carriers share, and 401 is proven by this fixture."""
    result = _parse(_stream("error-401-2.1.260.jsonl"))
    assert result.status == "error"
    assert result.reason is FailureReason.UNAUTHENTICATED
    assert result.verdict is None


def test_a_terminal_event_reading_subtype_success_while_is_error_is_true_never_resolves_ok():
    """C-1011, the recorded trap: an adapter keyed on `subtype` reports an auth failure as a clean review.

    Asserted here against a shape carrying NO recorded status or error name, so
    it cannot pass by way of the classification table: the only thing standing
    between it and `ok` is that `subtype` is not the gate.
    """
    event = json.dumps({"type": "result", "subtype": "success", "is_error": True, "total_cost_usd": 0.0})
    result = _parse([event])
    assert result.status != "ok"
    assert result.verdict is None
    assert result.reason is FailureReason.MALFORMED_OUTPUT


def _without_is_error() -> list[str]:
    """The synthetic terminal event with the `is_error` field removed entirely."""
    event = json.loads(_structured()[0])
    del event["is_error"]
    return [json.dumps(event)]


@pytest.mark.parametrize("stream", [_terminal_event(is_error=None), _without_is_error()], ids=["null", "absent"])
def test_a_terminal_event_that_never_said_it_succeeded_cannot_resolve_ok(stream):
    """C-1011: `is_error` is the one field between the event and `ok`, so only the boolean `False` opens it.

    Both shapes carry a well-formed `structured_output` with `verdict:
    "approve"`, so the only thing standing between them and a success answer is
    that a falsy `is_error` is not a positive report of one.
    """
    result = _parse(stream)
    assert result.status == "indeterminate"
    assert result.verdict is None
    assert result.reason is FailureReason.MALFORMED_OUTPUT


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        ({"is_error": True, "api_error_status": 500}, "500"),
        ({"is_error": True, "error_status": 503}, "503"),
        ({"is_error": True, "error": "model_not_found"}, "model_not_found"),
    ],
    ids=["terminal-status", "retry-status", "error-name"],
)
def test_an_unclassified_terminal_error_names_the_shape_a_reader_would_have_to_record(event, expected):
    """C-1012, C-1021: the detail exists to name a shape someone could add to the classification table.

    `indeterminate` calls the error name "the one piece of harness output that
    travels into `detail`, and deliberately". A placeholder there spends that
    allowance on nothing.
    """
    result = _parse(_terminal_event(**event))
    assert result.reason is FailureReason.MALFORMED_OUTPUT
    assert expected in (result.detail or "")


@pytest.mark.parametrize(
    "event",
    [
        {"is_error": True},
        {"is_error": True, "error": True},
        {"is_error": True, "error": "the model refused this request, and here is everything it had to say"},
    ],
    ids=["no-shape", "a-bool", "a-message-body"],
)
def test_a_terminal_error_with_no_readable_shape_names_none_rather_than_quoting_the_harness(event):
    """C-1035: a status integer and a short error name only — a message body may never reach a `Review`."""
    result = _parse(_terminal_event(**event))
    assert result.reason is FailureReason.MALFORMED_OUTPUT
    assert "the harness reported a terminal error, which" in (result.detail or "")
    assert "everything it had to say" not in (result.detail or "")


def test_a_recorded_429_run_with_no_terminal_event_is_classified_from_the_last_retry():
    """C-1012, S-1009: the run was killed mid-ladder, and the retry events are the only evidence left."""
    result = _parse(_stream("error-429-2.1.259.jsonl"))
    assert result.status == "error"
    assert result.reason is FailureReason.RATE_LIMITED
    assert result.verdict is None


def test_a_retry_event_naming_the_error_without_a_status_is_still_classified():
    """C-1012: the second half of `classify` — an exact-key lookup on the harness's own error name."""
    event = json.dumps({"type": "system", "subtype": "api_retry", "error": "rate_limit"})
    result = _parse([event])
    assert result.reason is FailureReason.RATE_LIMITED


def test_non_json_advisory_lines_never_make_parse_raise():
    """C-1009 merges stderr into stdout, and Claude Code writes advisories there."""
    result = _parse(["⚠ claude.ai connectors are disabled", "", "not json {", "[1, 2]"])
    assert result.status == "indeterminate"
    assert result.verdict is None


def test_an_exit_of_143_with_no_terminal_event_is_reported_as_our_own_kill():
    """C-1012: 143 is `128 + SIGTERM` from a harness that trapped it — labelled, not a generic failure."""
    result = _parse([], exit_code=harness_mod.SIGTERM_EXIT)
    assert result.reason is FailureReason.KILLED
    assert result.status != "ok"


def test_a_terminal_result_event_outranks_our_own_kill():
    """C-1011/SD § 4.3: the exit code labels a run that established nothing; it never overrules one that did.

    The reference for the row the four adapters now share. `result` is emitted
    at the END of a Claude Code run, so a 143 arriving beside one is the status
    of a process that had already answered — a harness that trapped the signal
    during its own teardown reports exactly that. Reading the status first would
    discard a finished review, which is the branch SD § 4.3 forbids.
    """
    result = _parse(_structured(), exit_code=harness_mod.SIGTERM_EXIT)
    assert result.status == "ok"
    assert result.reason is None


def test_an_empty_stream_with_a_clean_exit_never_resolves_ok():
    """C-1011: the exit code is never the success gate, so a silent clean exit is not a review."""
    result = _parse([], exit_code=0)
    assert result.status == "indeterminate"
    assert result.verdict is None
    assert result.reason is FailureReason.MALFORMED_OUTPUT


def test_a_wellformed_synthetic_result_resolves_ok_so_the_normalization_cases_isolate_one_field_each():
    """The control for the six untrusted-field tests below: everything recognised, nothing normalized away."""
    result = _parse(_structured())
    assert result.status == "ok"
    assert result.verdict == "approve"
    assert result.findings[0].severity == "high"
    assert result.findings[0].file == "src/app.py"
    assert result.findings[0].line_start == 3
    assert result.findings[0].confidence == "high"


def test_an_invented_severity_fails_toward_block():
    """C-1018: a `suggest` default silently downgrades a real finding; a `block` default costs one look."""
    result = _parse(_structured(finding={"severity": "catastrophic"}))
    assert result.findings[0].severity == "block"


def test_an_invented_verdict_fails_toward_needs_attention_and_never_toward_approve():
    """C-1011: the same direction as severity — a success may never be reached by elimination."""
    result = _parse(_structured(verdict="looks-fine-to-me"))
    assert result.verdict == "needs-attention"


def test_a_traversing_finding_path_is_dropped_rather_than_handed_to_a_consumer():
    """C-1019: `Finding.file` is untrusted output a consumer both renders and may hand to a command."""
    result = _parse(_structured(finding={"file": "../../etc/passwd"}))
    assert result.findings[0].file is None


def test_a_non_integer_line_number_becomes_none():
    """C-1019: a harness that emits a word where a line number belongs must not reach a consumer as one."""
    result = _parse(_structured(finding={"line_start": "twelve"}))
    assert result.findings[0].line_start is None


def test_an_invented_confidence_becomes_medium():
    """C-1018: the neutral value, since neither failing high nor failing low is the honest reading here."""
    result = _parse(_structured(finding={"confidence": "absolute"}))
    assert result.findings[0].confidence == "medium"


def test_a_null_summary_does_not_reach_a_consumer_as_the_word_none():
    """C-1018: `str(None)` renders the literal `"None"` into a field a human reads as the harness's own words."""
    assert _parse(_structured(summary=None)).summary == ""


UNTRUSTED_GUARDS = (
    ("status-is-a-bool", lambda: ClaudeAdapter().classify({"error_status": True}), None),
    ("line-is-a-bool", lambda: _parse(_structured(finding={"line_start": True})).findings[0].line_start, None),
    ("cost-is-a-string", lambda: _parse(_terminal_event(total_cost_usd="0.25")).cost_usd, None),
    ("cost-is-a-bool", lambda: _parse(_terminal_event(total_cost_usd=True)).cost_usd, None),
    ("findings-is-not-a-list", lambda: _parse(_structured(findings={"one": "finding"})).findings, ()),
    ("a-findings-element-is-not-a-dict", lambda: _parse(_structured(findings=["not an object"])).findings, ()),
    ("file-is-not-a-string", lambda: _parse(_structured(finding={"file": 12})).findings[0].file, None),
    (
        "recommendation-is-not-a-string",
        lambda: _parse(_structured(finding={"recommendation": 12})).findings[0].recommendation,
        None,
    ),
    ("title-is-null", lambda: _parse(_structured(finding={"title": None})).findings[0].title, ""),
    ("body-is-null", lambda: _parse(_structured(finding={"body": None})).findings[0].body, ""),
)
"""Every guard on an untrusted wire field, as `(id, reader, expected)`.

Each is a `and`-operand or a conditional expression, and coverage.py splits
neither — so 100% branch coverage on the adapter is reached without any of them
being exercised even once.
"""


@pytest.mark.parametrize(
    ("read", "expected"),
    [(read, expected) for _, read, expected in UNTRUSTED_GUARDS],
    ids=[name for name, _, _ in UNTRUSTED_GUARDS],
)
def test_every_untrusted_field_guard_answers_for_a_shape_no_recorded_run_produced(read, expected):
    """C-1018, C-1019: the guards a coverage gate cannot see, pinned by hand.

    Every one of these is a shape the harness is free to emit and no fixture
    happens to record — a JSON `true` where an integer belongs, an object where
    an array belongs, a `null` where prose belongs.
    """
    assert read() == expected


def test_next_steps_is_accepted_and_discarded():
    """D-i: the wire object carries it and nox's result type does not — it must not leak into a text field."""
    result = _parse(_structured())
    assert result.status == "ok"
    assert "next_steps" not in {field.name for field in fields(ParsedOutput)}
    assert "MARKER-NEXT-STEP-9137" not in result.summary
    assert "MARKER-NEXT-STEP-9137" not in (result.detail or "")


@pytest.mark.parametrize(
    "err",
    [
        {"error_status": 403},
        {"api_error_status": 500},
        {"error": "overloaded_error"},
        {"error_status": "401"},
        {"error_status": None, "error": 42},
        {},
    ],
    ids=["403", "500", "unknown-name", "status-not-an-int", "name-not-a-str", "empty"],
)
def test_classify_declines_wherever_no_recorded_fixture_proves_the_cell(err):
    """C-1012: a cell inferred from a sibling status is the substring guess this contract forbids."""
    assert ClaudeAdapter().classify(err) is None


@pytest.mark.parametrize(
    ("err", "reason"),
    [
        ({"error_status": 401}, FailureReason.UNAUTHENTICATED),
        ({"api_error_status": 401}, FailureReason.UNAUTHENTICATED),
        ({"error_status": 429}, FailureReason.RATE_LIMITED),
        ({"error": "authentication_failed"}, FailureReason.UNAUTHENTICATED),
        ({"error": "rate_limit"}, FailureReason.RATE_LIMITED),
    ],
    ids=["retry-401", "terminal-401", "retry-429", "name-auth", "name-quota"],
)
def test_classify_answers_only_the_cells_a_recorded_fixture_proves(err, reason):
    """C-1012: both carriers report the same integer, and the error name is an exact-key lookup."""
    assert ClaudeAdapter().classify(err) is reason


# ---------------------------------------------------------------------------
# on_line: C-1010
# ---------------------------------------------------------------------------


def test_every_stream_json_record_is_a_semantic_event():
    """C-1010: a `system/api_retry` is a real event — the harness is demonstrably alive, so the answer is honest."""
    adapter = ClaudeAdapter()
    for line in _stream("review-ok-2.1.260.jsonl") + _stream("error-429-2.1.259.jsonl"):
        assert adapter.on_line(line) is True, line


@pytest.mark.parametrize(
    "line",
    [
        "⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY is set",
        "",
        "   ",
        "[1, 2]",
        '"a string"',
        "42",
        "null",
        "{not json",
        '{"no": "type field"}',
    ],
    ids=["advisory", "blank", "whitespace", "array", "string", "number", "null", "broken", "no-type"],
)
def test_bytes_that_are_not_a_stream_json_record_are_not_progress(line):
    """C-1010: answering `True` to a stderr advisory would reset the silence window on noise."""
    assert ClaudeAdapter().on_line(line) is False


# ---------------------------------------------------------------------------
# Static properties: the WP5 carry-forward row and D-ac
# ---------------------------------------------------------------------------


def test_the_json_schema_and_the_prose_wire_object_name_the_same_top_level_fields():
    """WP5's carry-forward row: nothing joins the two, so they drift apart silently without this."""
    schema = json.loads(WIRE_JSON_SCHEMA)
    example = json.loads(WIRE_SCHEMA)
    assert set(schema["properties"]) == set(example)
    assert set(schema["required"]) == set(example)


def test_the_json_schema_and_the_prose_wire_object_name_the_same_finding_fields():
    """WP5's carry-forward row, for the object a consumer actually reads findings out of."""
    item = json.loads(WIRE_JSON_SCHEMA)["properties"]["findings"]["items"]
    example = json.loads(WIRE_SCHEMA)["findings"][0]
    assert set(item["properties"]) == set(example)
    assert set(item["required"]) == set(example)


def test_the_adapter_claims_nothing_about_how_long_a_descendant_lives():
    """D-ac: both axes are about writes and network reach, and `runner.py` names two open lifetime holes.

    A static scan over this adapter's own prose, because the claim D-ac
    declined to add as a third axis is exactly the one that would come back as
    a reassuring sentence in a docstring.
    """
    source = ADAPTER_SOURCE.read_text(encoding="utf-8").casefold()
    found = [phrase for phrase in FORBIDDEN_LIFETIME_CLAIMS if phrase in source]
    assert not found, f"the adapter claims containment bounds process lifetime: {found}"


def test_the_adapter_registry_key_and_its_config_reads_are_what_the_gates_are_keyed_on():
    """C-1023, C-1025: `name` keys both `ADAPTERS` and `PASSTHROUGH_ALLOW`; `CONFIG_READS` feeds the digest.

    The `CONFIG_READS` assertion is spelled out rather than compared to itself.
    `assert ClaudeAdapter.CONFIG_READS == CONFIG_READS` says only that the class
    attribute and the module constant are the same object, and the non-empty
    check passes on any one-entry tuple — so dropping
    `${CLAUDE_CONFIG_DIR}/settings.json`, the settings file that WINS when the
    variable is set and the one the C-1025 digest would then stop hashing, left
    the whole unit and acceptance tier green. The acceptance oracle pins the
    `${HOME}` entry and only that one.
    """
    assert ClaudeAdapter.name == "claude"
    assert ClaudeAdapter.name in PASSTHROUGH_ALLOW
    assert ClaudeAdapter.BINARY == "claude"
    assert ClaudeAdapter.CONFIG_READS == CONFIG_READS
    assert CONFIG_READS == ("${CLAUDE_CONFIG_DIR}/settings.json", "${HOME}/.claude/settings.json")


def test_the_prompt_carries_the_diff_so_the_reviewer_reviews_a_change(tmp_path):
    """The live NxN matrix's first blocker: this adapter delivered NO diff at all.

    The harness is handed a worktree checked out at the AFTER commit and, before
    this, a prompt asserting the diff it was given was the whole change. Nothing
    in the argv carried one. The prompt is the delivery route, so the assertion
    is on what stdin delivers: `Workspace.diff` reaches the harness verbatim.
    """
    launch, _ = _launch(tmp_path)
    assert launch.stdin_path is not None
    assert WS_DIFF.rstrip("\n") in launch.stdin_path.read_text(encoding="utf-8")
