"""The Codex adapter: argv shape, the JSONL dialect, and C-1040's sandbox probe.

C-1007(codex), C-1011, C-1012(codex), C-1023, C-1025, C-1028, C-1030(codex),
C-1032, C-1040, D-ac, D-v, E3, E8, S-1002.

Codex is the one v1 harness allowed to claim `Enforcement` `"os"`, so every
assertion here is written so a *weaker* implementation fails it. Three of them
carry the whole weight and are worth naming up front:

1. **The preamble trap.** `review-findings-0.144.1.jsonl` item_0 is a
   schema-shaped `{"verdict":"approve","findings":[]}` emitted before the model
   has looked at anything. A `parse` that took the FIRST `agent_message` returns
   a clean approve for a review that had not begun, and both recorded fixtures
   would still pass it. The tests assert the LAST one wins, and re-assert that
   the trap is still in the fixture so the check cannot rot into a tautology.
2. **`attempt_proven`'s nonce substitution.** C-1040 asks for a
   `command_execution` item whose `status == "failed"`; 0.144.1 emits no item at
   all for a command the sandbox blocked (`sandbox-probe-declined-0.144.1.jsonl`,
   two blocked attempts, zero items). The `<attempt> || cat <nonce file>`
   spelling restores the item and puts a 128-bit nonce — one PER ATTEMPT — in
   its `aggregated_output`. Both halves are asserted separately: an item without
   the nonce fails, and a nonce without an item fails. So is the reason the
   nonce is per attempt: one batched item carrying both attempts and one shared
   nonce proved both, including an attempt that succeeded.
3. **Both spellings of one setting.** `derive_containment` cannot know that
   `--sandbox` and `sandbox_mode=` are the same switch, so `SANDBOX_EVIDENCE`
   names both. Every spelling of an override is asserted to refuse the `os`
   claim — including the two (`--config=k=v`, `-ck=v`) a rule reading only the
   separated form would miss.

Every fixture read here was recorded live from `codex-cli 0.144.1` (E3). The
recorded attempt strings and the recorded nonce cannot be reproduced by a live
run, which is why the decision they feed is *also* tested through a pure
module-level helper the fixtures can be pointed at directly.

The probe itself is tested from a **passing baseline**: `ProbeRunner` answers
every spawn the way a working sandbox would, `sandbox_probe` returns `True`, and
each further test breaks exactly one observation off that baseline. Without a
`True` anywhere, `all(...)` never evaluates true, no observation is load-bearing,
and coverage still reports 100% — nine separate weakenings of this probe were
verified to survive the suite that had no baseline in it.
"""

from __future__ import annotations

import ast
import json
import re
import socket
from pathlib import Path
from types import MappingProxyType

import pytest

import nox.harness as harness_module
from nox.adapters import codex, load
from nox.adapters.codex import (
    BINARY,
    CAPABILITIES,
    CONFIG_FLAGS,
    CONFIG_READS,
    EFFORT_KEY,
    HEARTBEAT_KIND,
    LOGGED_IN_PREFIX,
    LOGGED_OUT,
    LOGIN_SUBCOMMAND,
    MODEL_FLAG,
    NONCE_BYTES,
    PROBE_MARKER,
    SANDBOX_EVIDENCE,
    SANDBOX_MODE,
    SANDBOX_SUBCOMMAND,
    SCHEMA_FILENAME,
    SCHEMA_FLAG,
    STREAM_FLAG,
    SUBCOMMAND,
    VERIFIED_AGAINST,
    VERSION_PREFIX,
    CodexAdapter,
)
from nox.capability import Capability, Launcher, ModelSpecT
from nox.config import AUTH_HINT_TRAILER, ConfigError
from nox.harness import (
    DENIED_FLAGS,
    NEVER_EMITTED,
    PASSTHROUGH_ALLOW,
    PROMPT_ARGV_LIMIT,
    PROMPT_FILENAME,
    SIGTERM_EXIT,
    ContainmentPlan,
    HarnessInfo,
    HarnessUnavailable,
    ProbeCache,
    UnsupportedCapability,
    authorize,
    check_capabilities,
    config_read_paths,
    derive_containment,
    probe_digest,
    resolve_executable,
    resolve_model,
)
from nox.liveness import Heartbeat, Liveness
from nox.outcome import FailureReason
from nox.prompt import WIRE_SCHEMA
from nox.runner import Invocation
from nox.workspace import IsolationError, Workspace
from tests.unit.stubs import FakeProcess, FakeRunner, config

# Resolved from this file, never from the cwd: the fixtures and the static scans
# are about the nox subtree whether pytest ran from the repo root or from `nox/`.
NOX = Path(__file__).resolve().parents[2]
FIXTURES = NOX / "tests" / "contract" / "fixtures" / "codex"
ADAPTER_SOURCE = NOX / "src" / "nox" / "adapters" / "codex.py"

VERSION_FIXTURE = "version-0.144.1.txt"
AUTHENTICATED = "login-status-authenticated-0.144.1.txt"
UNAUTHENTICATED = "login-status-unauthenticated-0.144.1.txt"
FINDINGS = "review-findings-0.144.1.jsonl"
APPROVE = "review-approve-0.144.1.jsonl"
ERRORS = "error-events-0.144.1.jsonl"
PROBE_PASS = "sandbox-probe-0.144.1.jsonl"
PROBE_DECLINED = "sandbox-probe-declined-0.144.1.jsonl"
HELP = "help-0.144.1.txt"
REVIEW_HELP = "help-review-0.144.1.txt"
ARG_CONFLICTS = "review-arg-conflicts-0.144.1.txt"
SANDBOX_SUBCOMMAND_FIXTURE = "sandbox-subcommand-0.144.1.txt"
EFFORT_ENUM = "effort-enum-0.144.1.jsonl"
MODEL_RESOLVES = "model-resolves-0.144.1.jsonl"

DIGEST = "digest-under-test"
"""The one digest the pure derivation tests pass. `authorize` computes its own."""

RECORDED_NONCE = "f4fa2bf28bd62abb20d93483c5cc3803"
"""The per-run nonce `sandbox-probe-0.144.1.jsonl` was recorded with."""

RECORDED_ATTEMPTS = (
    "touch ./nox-probe-write || cat ./.nox-probe4/nonce",
    "bash -c 'exec 3<>/dev/tcp/127.0.0.1/47397' || cat ./.nox-probe4/nonce",
)
"""The two `<attempt> || cat <nonce file>` strings that fixture's items carry."""

RECORDED_NONCE_PATH = ".nox-probe4/nonce"
"""The nonce path both recorded items name — what `attempt_proven` is handed.

ONE path for both attempts, because the fixture predates the per-attempt nonce
(E22): it was recorded against the old shared spelling. So this fixture cannot
show per-attempt separation at all, and the tests that guard it are the
probe-level ones — `ProbeRunner(review_items=1)` and `ProbeRunner(review_batched=True)`,
which mint real per-attempt nonces and drive `sandbox_probe` itself.
"""

DECLINED_ATTEMPTS = (
    "touch ./nox-probe-write",
    "bash -c 'exec 3<>/dev/tcp/127.0.0.1/36645'",
)
"""C-1040's own bare spelling, and what 0.144.1 does with it: no item at all."""

LIFETIME_WORDS = (
    "reap",
    "outliv",
    "lifetime",
    "descendant",
    "process group",
    "kill",
    "sigterm",
    "sigkill",
    "orphan",
)
"""Vocabulary that could read as a claim about how long a process lives (D-ac)."""

NEGATIONS = ("not ", "never", "neither", "nothing", "no ", "cannot", "n't", "without")
"""What turns such a sentence into the disclaimer D-ac requires instead."""


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


def _lines(name: str) -> tuple[str, ...]:
    return tuple(FIXTURES.joinpath(name).read_text(encoding="utf-8").splitlines())


def _text(name: str) -> str:
    return FIXTURES.joinpath(name).read_text(encoding="utf-8")


def _hb() -> Heartbeat:
    return Heartbeat(kind=HEARTBEAT_KIND, last_activity_at=0.0, last_byte_at=0.0)


def _wire_stream(obj: object) -> tuple[str, ...]:
    """A minimal well-formed Codex stream whose final message is `obj`."""
    message = {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": json.dumps(obj)}}
    return (
        '{"type":"thread.started","thread_id":"t"}',
        '{"type":"turn.started"}',
        json.dumps(message),
        '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}',
    )


def _finding(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "severity": "high",
        "title": "a title",
        "body": "an argument",
        "file": "src/app.py",
        "line_start": 1,
        "line_end": 2,
        "confidence": "high",
        "recommendation": None,
    }
    return {**body, **overrides}


def _first_agent_message(lines: tuple[str, ...]) -> str:
    for line in lines:
        event = json.loads(line)
        item = event.get("item") if isinstance(event.get("item"), dict) else None
        if event.get("type") == "item.completed" and item is not None and item.get("type") == "agent_message":
            return str(item["text"])
    raise AssertionError("the fixture carries no agent_message at all")


@pytest.fixture
def adapter() -> CodexAdapter:
    return CodexAdapter()


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    """A C-1008-shaped environment with a real `codex` on its rebuilt `PATH`.

    `resolve_executable` refuses anything that is not an absolute, executable
    realpath off this `PATH`, so `launch_argv` and every `authorize` test needs
    a file rather than a name. `touch` and `bash` are here for the same reason:
    the probe's two positive controls spawn them directly, and an unresolvable
    control is a `HarnessUnavailable` the probe swallows into `False` — which
    is correct, and would make every probe test below pass for that reason
    instead of the one it names.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in (BINARY, "touch", "bash"):
        binary = bindir / name
        binary.write_bytes(b"#!/bin/sh\nexit 0\n")
        binary.chmod(0o755)
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    return {"PATH": str(bindir), "HOME": str(home), "CODEX_HOME": str(home / ".codex")}


@pytest.fixture
def ws(tmp_path: Path, env: dict[str, str]) -> Workspace:
    root = tmp_path / "ws"
    scratch = root / ".nox-tok"
    scratch.mkdir(parents=True)
    return Workspace(
        path=root,
        token="tok",
        base="base-sha",
        target="target-sha",
        scope="code-diff",
        scratch=scratch,
        diff_path=scratch / "review.diff",
        diff=WS_DIFF,
        env=env,
        neutralized=(),
        neutralized_total=0,
        filtered=(),
        filtered_total=0,
        filtered_changed=(),
        filtered_changed_total=0,
        omitted=(),
        omitted_total=0,
        omitted_ignored=0,
    )


@pytest.fixture
def info() -> HarnessInfo:
    return HarnessInfo(
        name="codex",
        version=VERIFIED_AGAINST,
        verified_against=VERIFIED_AGAINST,
        capabilities=CAPABILITIES,
        heartbeat_kind=HEARTBEAT_KIND,
        launcher=Launcher(binary=BINARY),
    )


def _probe(
    adapter: CodexAdapter,
    tmp_path: Path,
    env: dict[str, str],
    version: tuple[str, ...],
    login: tuple[str, ...],
):
    cwd = tmp_path / "probe-cwd"
    cwd.mkdir(exist_ok=True)
    runner = FakeRunner(FakeProcess(version), FakeProcess(login))
    return runner, adapter.probe(runner, config(), env, cwd)


# ---------------------------------------------------------------------------
# The sandbox probe's fake host: one passing baseline, one knob per observation
# ---------------------------------------------------------------------------

UNREACHABLE_PGID = 2**31 - 1
"""A process-group id no POSIX kernel can have assigned.

Linux caps `pid_max` at 2^22 and macOS at 99998, so the real signal a timed-out
spawn triggers resolves `ESRCH` and reaches nothing. Belt for the tests that do
not also replace the primitive.
"""

SPELL_SEPARATOR = " || cat ./"
"""How the probe joins an attempt to its own nonce file — the fake reads it back out."""


class ProbeProcess:
    """A `Process` with an exit status, output, and both out-of-band signals settable.

    `stubs.FakeProcess` cannot express the three answers this file has to script:
    a spawn that never returns a status, a dead drain thread, and a truncated
    stream. Each is an observation the probe must read as "no evidence".
    """

    def __init__(self, lines=(), exit_code: int | None = 0, *, collector_failure=None, overflowed=False) -> None:
        self._lines = tuple(lines)
        self._exit_code = exit_code
        self._collector_failure = collector_failure
        self._overflowed = overflowed
        self.waits = 0

    @property
    def pid(self) -> int:
        return UNREACHABLE_PGID

    @property
    def collector_failure(self):
        return self._collector_failure

    @property
    def overflowed(self) -> bool:
        return self._overflowed

    def lines(self, timeout: float) -> tuple[str, ...]:
        del timeout
        drained, self._lines = self._lines, ()
        return drained

    def wait(self, timeout):
        del timeout
        self.waits += 1
        return self._exit_code


def _spawn_kind(argv: tuple[str, ...]) -> str:
    """Name one probe spawn by its argv — which leg it belongs to and what it runs."""
    if argv[1:2] == SUBCOMMAND[:1]:
        return "review"
    if argv[1:2] == SANDBOX_SUBCOMMAND[:1]:
        return f"sandboxed_{Path(argv[argv.index('--') + 1]).name}"
    return f"control_{Path(argv[0]).name}"


class ProbeRunner:
    """A `Runner` answering every `sandbox_probe` spawn the way a working sandbox would.

    Reactive rather than pre-scripted, and it has to be: the review leg's stream
    must carry the nonce PATHS the probe minted microseconds earlier and the
    nonce VALUES it wrote into scratch, neither of which exists when the test
    starts. Every process is therefore built from the argv it is handed, and the
    review leg reads the nonces back off disk exactly as the real harness would.

    With no knob set it returns a probe that passes. Each knob breaks exactly
    one observation, so a `False` below is attributable to that observation and
    to nothing else — which is what the previous shape of these tests could not
    say, because `FakeRunner` handed out default exit-0 processes for every
    spawn a test had not scripted.
    """

    def __init__(
        self,
        ws: Workspace,
        *,
        control_write_status: int | None = 0,
        control_write_creates: bool = True,
        control_network_status: int | None = 0,
        control_network_connects: bool = True,
        read_status: int | None = 0,
        write_status: int | None = 1,
        write_leaves_marker: bool = False,
        network_status: int | None = 1,
        network_connects: bool = False,
        review_status: int | None = 0,
        review_lines: tuple[str, ...] | None = None,
        review_items: int = 2,
        review_item_type: str = "command_execution",
        review_batched: bool = False,
        review_bare_cat: bool = False,
        review_leaves_marker: bool = False,
        review_removes_marker: bool = False,
        review_connects: bool = False,
        review_overflowed: bool = False,
        review_collector_failure: BaseException | None = None,
        never_answers: str | None = None,
    ) -> None:
        self.ws = ws
        self.spawned: list[Invocation] = []
        self.control_write_status = control_write_status
        self.control_write_creates = control_write_creates
        self.control_network_status = control_network_status
        self.control_network_connects = control_network_connects
        self.read_status = read_status
        self.write_status = write_status
        self.write_leaves_marker = write_leaves_marker
        self.network_status = network_status
        self.network_connects = network_connects
        self.review_status = review_status
        self.review_lines = review_lines
        self.review_items = review_items
        self.review_item_type = review_item_type
        self.review_batched = review_batched
        self.review_bare_cat = review_bare_cat
        self.review_leaves_marker = review_leaves_marker
        self.review_removes_marker = review_removes_marker
        self.review_connects = review_connects
        self.review_overflowed = review_overflowed
        self.review_collector_failure = review_collector_failure
        self.never_answers = never_answers

    # -- what each spawn does ------------------------------------------------

    def _touch(self, argv: tuple[str, ...]) -> None:
        (self.ws.path / argv[-1]).write_text("", encoding="utf-8")

    def _connect(self, port: int) -> None:
        socket.create_connection((codex.PROBE_HOST, port)).close()

    def marker_name(self) -> str:
        """The marker this run minted, read off the write attempt's own argv."""
        for inv in self.spawned:
            if _spawn_kind(inv.argv).endswith("_touch"):
                return inv.argv[-1].removeprefix("./")
        raise AssertionError("no touch spawn was recorded")

    def nonce_names(self) -> tuple[str, ...]:
        """The nonce files this run minted, read off the review leg's own ask.

        The same trick as `marker_name`: the names exist only inside the probe,
        so the fake recovers them from the argv rather than being told. Since
        E20 they live in the worktree ROOT — `ws.scratch` is a sibling of it now
        — and `_review_leg` removes them before it returns, so a test cannot
        find them by listing a directory afterwards.
        """
        for inv in self.spawned:
            if _spawn_kind(inv.argv) == "review":
                spelled = [line for line in inv.argv[-1].splitlines() if SPELL_SEPARATOR in line]
                return tuple(line.partition(SPELL_SEPARATOR)[2] for line in spelled)
        raise AssertionError("no review spawn was recorded")

    def _review_stream(self, argv: tuple[str, ...]) -> tuple[str, ...]:
        spelled = [line for line in argv[-1].splitlines() if SPELL_SEPARATOR in line]
        assert spelled, f"the probe's ask carried no attempt at all: {argv[-1]!r}"
        pairs = [
            (line, (self.ws.path / line.partition(SPELL_SEPARATOR)[2]).read_text(encoding="utf-8")) for line in spelled
        ]
        if self.review_bare_cat:
            # The model attempted nothing and simply READ each nonce file it was
            # told about. Every item is a real `command_execution`, carries the
            # attempt's own nonce path and its own nonce value, and proves
            # nothing about the sandbox.
            items = [(spell.partition(SPELL_SEPARATOR)[2], nonce) for spell, nonce in pairs]
            items = [(f"cat ./{path}", f"{nonce}\n") for path, nonce in items]
        elif self.review_batched:
            # One `bash -lc "a; b"` item carrying BOTH attempts, and the output
            # of the one that FAILED. With a single shared nonce this proved
            # both attempts, including the write that succeeded and printed
            # nothing of its own.
            items = [("; ".join(spell for spell, _ in pairs), f"denied\n{pairs[-1][1]}\n")]
        else:
            items = [(spell, f"denied\n{nonce}\n") for spell, nonce in pairs[: self.review_items]]
        events = ['{"type":"thread.started","thread_id":"t"}', '{"type":"turn.started"}']
        events += [
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": f"item_{index}",
                        "type": self.review_item_type,
                        "command": f"/bin/zsh -c {command!r}",
                        "aggregated_output": output,
                        "exit_code": 0,
                        "status": "completed",
                    },
                }
            )
            for index, (command, output) in enumerate(items)
        ]
        events.append('{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}')
        return tuple(events)

    def spawn(self, inv: Invocation):
        self.spawned.append(inv)
        kind = _spawn_kind(inv.argv)
        if kind == self.never_answers:
            return ProbeProcess(exit_code=None)
        if kind == "control_touch":
            if self.control_write_creates:
                self._touch(inv.argv)
            return ProbeProcess(exit_code=self.control_write_status)
        if kind == "control_bash":
            if self.control_network_connects:
                self._connect(_port_of([inv]))
            return ProbeProcess(exit_code=self.control_network_status)
        if kind == "sandboxed_ls":
            return ProbeProcess(exit_code=self.read_status)
        if kind == "sandboxed_touch":
            if self.write_leaves_marker:
                self._touch(inv.argv)
            return ProbeProcess(exit_code=self.write_status)
        if kind == "sandboxed_bash":
            if self.network_connects:
                self._connect(_port_of([inv]))
            return ProbeProcess(exit_code=self.network_status)
        assert kind == "review", f"the probe spawned something this fake does not model: {inv.argv}"
        if self.review_connects:
            self._connect(_port_of(self.spawned))
        if self.review_leaves_marker:
            (self.ws.path / self.marker_name()).write_text("", encoding="utf-8")
        if self.review_removes_marker:
            (self.ws.path / self.marker_name()).unlink(missing_ok=True)
        lines = self.review_lines if self.review_lines is not None else self._review_stream(inv.argv)
        return ProbeProcess(
            lines,
            exit_code=self.review_status,
            overflowed=self.review_overflowed,
            collector_failure=self.review_collector_failure,
        )


def _port_of(spawned: list[Invocation]) -> int:
    """The listener port this run bound, read off the network command's own argv."""
    for inv in spawned:
        if _spawn_kind(inv.argv).endswith("_bash"):
            return int(inv.argv[-1].rpartition("/")[2])
    raise AssertionError("no network spawn was recorded")


# ---------------------------------------------------------------------------
# The shipped tables: registry parity and the literals every probe pinned
# ---------------------------------------------------------------------------


def test_the_codex_adapter_is_what_the_registry_key_resolves_to():
    """E3/C-1024: the registry key, the `PASSTHROUGH_ALLOW` key and `name` are one string."""
    assert CodexAdapter.name == "codex"
    assert isinstance(load("codex"), CodexAdapter)
    assert CodexAdapter.BINARY == BINARY == "codex"


def test_the_probe_establishes_exactly_three_capabilities_and_a_semantic_heartbeat():
    """C-1013: absence is the default, so the shipped set is asserted rather than sampled."""
    assert CAPABILITIES == frozenset(
        {Capability.ENUMERABLE_DENY, Capability.ENFORCED_READ_ONLY, Capability.STRUCTURED_OUTPUT}
    )
    assert HEARTBEAT_KIND is Liveness.SEMANTIC


def test_the_passthrough_allowlist_for_codex_permits_nothing():
    """C-1023: permission, not exclusion — and this harness exposes nothing containment-inert.

    It held `--title` until that flag was checked against the binary: it is
    documented on `codex exec review`, and `SUBCOMMAND` is bare `codex exec`
    (E21), so the one word this gate let through answered
    `error: unexpected argument '--title' found` and exit 2 — a clap error where
    a nox refusal by name belongs. `test_harness.py` now audits every entry
    against the committed `--help` of the command nox spawns.
    """
    assert PASSTHROUGH_ALLOW["codex"] == frozenset()


def test_the_sandbox_evidence_names_both_of_codex_spellings_of_one_setting():
    """WP6 carry-forward: core cannot know `--sandbox` and `sandbox_mode=` are one switch."""
    assert SANDBOX_MODE == "read-only"
    assert SANDBOX_EVIDENCE == ("-c", f"sandbox_mode={SANDBOX_MODE}", "--sandbox", SANDBOX_MODE)


def test_the_config_flags_are_hardening_and_never_part_of_the_evidence():
    """C-1025: promoting them would let a plan corroborate `os` with no sandbox word present."""
    assert set(CONFIG_FLAGS).isdisjoint(SANDBOX_EVIDENCE)
    assert set(CONFIG_FLAGS) == {"--ephemeral", "--strict-config", "--ignore-rules", "--ignore-user-config"}


def test_the_declared_config_reads_expand_to_absolute_paths_in_precedence_order(env):
    """C-1025: `CODEX_HOME` is forwarded, so a `$HOME`-relative path alone hashes the wrong file."""
    assert CONFIG_READS == ("${CODEX_HOME}/config.toml", "${HOME}/.codex/config.toml")
    expanded = config_read_paths(CONFIG_READS, env)
    assert len(expanded) == 2
    assert all(path.is_absolute() for path in expanded)


def test_the_shipped_model_table_carries_one_probed_literal_and_two_effort_levels():
    """C-1030/E3: a second model id joins the table when a probe proves one, not before."""
    assert set(CodexAdapter.MODELS) == {"fast-balanced", "deep-reasoning"}
    assert ModelSpecT.of(CodexAdapter.MODELS["fast-balanced"]) == ModelSpecT(model="gpt-5.6-luna", effort="low")
    assert ModelSpecT.of(CodexAdapter.MODELS["deep-reasoning"]) == ModelSpecT(model="gpt-5.6-luna", effort="high")


def test_the_nonce_is_wide_enough_that_a_declining_model_cannot_guess_it():
    """C-1040: 128 bits is the whole of the nonce's evidentiary value."""
    assert NONCE_BYTES == 16
    assert len(RECORDED_NONCE) == NONCE_BYTES * 2


def test_the_short_sandbox_spelling_is_refused_from_passthrough_by_the_shared_deny_set():
    """`SANDBOX_EVIDENCE` names two spellings and Codex has a third: `-s, --sandbox`.

    `harness._names_option("-s", "--sandbox")` is `False`, so C-1025 rule 4 does
    not see the short form and an outside `-s danger-full-access` would
    corroborate this adapter's `os` claim with the sandbox off. What closes it is
    `DENIED_FLAGS`, which refuses `-s` from `passthrough` before any argv exists
    — a guarantee this adapter depends on and does not own, so it is pinned from
    here as well as from WP6's own suite.
    """
    assert "-s" in DENIED_FLAGS
    assert "-s, --sandbox <SANDBOX_MODE>" in _text(HELP)


# ---------------------------------------------------------------------------
# E3: the fixtures the shipped docstrings cite, read rather than merely named
# ---------------------------------------------------------------------------


def test_the_recorded_help_still_carries_the_flags_this_adapter_emits():
    """A fixture nothing reads is a fixture that can rot — which is how a corrupted one shipped."""
    recorded = _text(HELP)
    assert [flag for flag in (*CONFIG_FLAGS, STREAM_FLAG, SCHEMA_FLAG, MODEL_FLAG) if flag not in recorded] == []
    assert f"possible values: {SANDBOX_MODE}," in recorded


def test_the_recorded_review_help_shows_why_that_subcommand_cannot_carry_the_sandbox_word():
    """Finding 2 in the module docstring: no `--sandbox` there, so the second spelling is unemittable.

    It DOES list `--output-schema`, which is why no finding about that flag
    being ignored is claimed: the fixture does not support one.
    """
    recorded = _text(REVIEW_HELP)
    assert "--sandbox" not in recorded
    assert SCHEMA_FLAG in recorded
    assert "--base <BRANCH>" in recorded


def test_the_recorded_argument_conflict_is_still_what_finding_one_says_it_is():
    """`--base` and a prompt are mutually exclusive, which is what forces bare `codex exec`."""
    recorded = _text(ARG_CONFLICTS)
    assert "'--base <BRANCH>' cannot be used with '[PROMPT]'" in recorded
    assert "Specify --uncommitted, --base, --commit, or provide custom review instructions" in recorded


def test_the_recorded_sandbox_subcommand_run_still_shows_both_attempts_blocked_and_the_control_passing():
    """The deterministic leg's own evidence: a read that exits 0 and two attempts that do not."""
    recorded = _text(SANDBOX_SUBCOMMAND_FIXTURE)
    assert recorded.count("exit=1") == 2
    assert "exit=0" in recorded
    assert "Read-only file system" in recorded
    assert "Operation not permitted" in recorded
    assert f"{SANDBOX_SUBCOMMAND[0]} -c sandbox_mode={SANDBOX_MODE}" in recorded


def test_the_recorded_effort_enum_names_every_level_the_shipped_table_asks_for():
    """C-1030/E3: both levels are read off the vendor's own enum, not guessed.

    The API enumerated its domain when handed an invalid value, so a level this
    adapter ships that the enum does not name would be a level no probe proved.
    """
    recorded = _text(EFFORT_ENUM)
    levels = {ModelSpecT.of(spec).effort for spec in CodexAdapter.MODELS.values()}
    assert levels == {"low", "high"}
    assert [level for level in levels if f"'{level}'" not in recorded] == []
    assert "Supported values are:" in recorded


def test_the_recorded_model_run_shows_the_shipped_literal_resolving():
    """E3: the evidence the one shipped model id rests on — a turn that started and completed.

    Recorded from `codex exec -m gpt-5.6-luna -c model_reasoning_effort=high`,
    so it is both knobs accepted together and not merely a model id that parses.
    """
    kinds = [json.loads(line)["type"] for line in _lines(MODEL_RESOLVES)]
    assert kinds[0] == "thread.started"
    assert "turn.completed" in kinds
    assert [kind for kind in kinds if kind in {"error", "turn.failed"}] == []


# ---------------------------------------------------------------------------
# C-1025: the `os` claim is derived, and both spellings are refused
# ---------------------------------------------------------------------------


def _os_plan() -> ContainmentPlan:
    return ContainmentPlan(
        mechanism="os-sandbox",
        write_enforcement="os",
        network_enforcement="os",
        argv_evidence=SANDBOX_EVIDENCE,
    )


def _derived(*argv: str, cached: bool = True) -> ContainmentPlan:
    cache = ProbeCache()
    if cached:
        cache.record(DIGEST)
    inv = Invocation(argv=argv, cwd=Path("/nonexistent-cwd"), env={})
    return derive_containment(inv, _os_plan(), DIGEST, cache)


def test_the_shipped_evidence_run_corroborates_the_os_claim_when_the_probe_passed():
    """C-1025: the positive control, without which every refusal below proves nothing."""
    derived = _derived("/bin/codex", "exec", *SANDBOX_EVIDENCE, STREAM_FLAG)
    assert derived.write_enforcement == "os"
    assert derived.network_enforcement == "os"


@pytest.mark.parametrize(
    "override",
    [
        ("--sandbox", "danger-full-access"),
        ("--sandbox=danger-full-access",),
        ("-c", "sandbox_mode=danger-full-access"),
        ("--config=sandbox_mode=danger-full-access",),
        ("-csandbox_mode=danger-full-access",),
    ],
    ids=["separated-sandbox", "joined-sandbox", "separated-config", "joined-config", "attached-short"],
)
def test_an_override_in_any_of_codex_spellings_refuses_the_os_claim(override):
    """WP6 carry-forward: naming both spellings is what closes the last-wins hole."""
    derived = _derived("/bin/codex", "exec", *SANDBOX_EVIDENCE, STREAM_FLAG, *override)
    assert derived.write_enforcement is None
    assert derived.network_enforcement is None


def test_a_second_config_flag_for_an_unrelated_key_leaves_both_axes_standing():
    """C-1025 rule 4's exemption: the effort knob rides a second `-c` and must stay legal."""
    derived = _derived("/bin/codex", "exec", *SANDBOX_EVIDENCE, "-c", f"{EFFORT_KEY}=high")
    assert derived.write_enforcement == "os"
    assert derived.network_enforcement == "os"


def test_the_os_claim_is_refused_until_a_sandbox_probe_passed_under_this_digest():
    """C-1007/C-1040: an unproven probe is a refusal, never a silent unsandboxed run."""
    derived = _derived("/bin/codex", "exec", *SANDBOX_EVIDENCE, STREAM_FLAG, cached=False)
    assert derived.write_enforcement is None
    assert derived.network_enforcement is None
    with pytest.raises(UnsupportedCapability) as exc:
        check_capabilities(
            HarnessInfo(
                name="codex",
                version=VERIFIED_AGAINST,
                verified_against=VERIFIED_AGAINST,
                capabilities=CAPABILITIES,
                heartbeat_kind=HEARTBEAT_KIND,
                launcher=Launcher(binary=BINARY),
            ),
            derived,
        )
    assert "write" in str(exc.value)
    assert "network" in str(exc.value)


# ---------------------------------------------------------------------------
# containment_plan: C-1007
# ---------------------------------------------------------------------------


def test_the_plan_claims_the_os_sandbox_on_both_axes(adapter, info):
    """C-1007: one sandbox constrains writes and network reach alike, so the axes fall together."""
    plan = adapter.containment_plan(config(), info)
    assert plan.mechanism == "os-sandbox"
    assert plan.write_enforcement == "os"
    assert plan.network_enforcement == "os"


def test_the_plan_names_the_sandbox_run_as_its_argv_evidence_and_adds_no_environment(adapter, info):
    """C-1025: Codex's containment is entirely in its argv, so `env_evidence` is empty."""
    plan = adapter.containment_plan(config(), info)
    assert plan.argv_evidence == SANDBOX_EVIDENCE
    assert dict(plan.env_evidence) == {}


# ---------------------------------------------------------------------------
# prepare: argv shape (E9a, C-1023, C-1028, C-1030)
# ---------------------------------------------------------------------------


def test_the_argv_opens_with_the_subcommand_and_then_the_policed_passthrough(adapter, ws, info, monkeypatch):
    """E9a: passthrough first, nox's own flags last, so a last-wins parser resolves nox's.

    Driven through a synthetic permission: this harness's shipped allowlist is
    empty, so nothing reaches `prepare` to be ordered. `--color` is codex's own
    and documented on the command nox spawns, so the ordering is exercised
    against a real flag without shipping a permission for it.
    """
    monkeypatch.setattr(
        harness_module,
        "PASSTHROUGH_ALLOW",
        MappingProxyType({**PASSTHROUGH_ALLOW, "codex": frozenset({"--color"})}),
    )
    argv = adapter.prepare(ws, info, config(passthrough=("--color", "never")), None).argv
    assert argv[: len(SUBCOMMAND)] == SUBCOMMAND
    assert argv[len(SUBCOMMAND) : len(SUBCOMMAND) + 2] == ("--color", "never")


def test_the_sandbox_evidence_is_emitted_once_as_one_contiguous_terminated_run(adapter, ws, info):
    """C-1025 rules 1-2: `_argv_corroborates` wants a run, and a run the next word terminates."""
    argv = adapter.prepare(ws, info, config(), None).argv
    width = len(SANDBOX_EVIDENCE)
    runs = [start for start in range(len(argv) - width + 1) if argv[start : start + width] == SANDBOX_EVIDENCE]
    assert len(runs) == 1
    start = runs[0]
    assert start + width == len(argv) or argv[start + width].startswith("-")


def test_the_argv_carries_the_stream_flag_and_every_hardening_flag(adapter, ws, info):
    """SD § 6.2: defence in depth, emitted on every launch and never the boundary."""
    argv = adapter.prepare(ws, info, config(), None).argv
    assert STREAM_FLAG in argv
    assert [flag for flag in CONFIG_FLAGS if flag not in argv] == []


def test_the_schema_flag_names_the_file_prepare_wrote_into_the_scratch_directory(adapter, ws, info):
    """C-1009: `ws.scratch` is nox-owned, so a fixed name inside it is not a collision."""
    argv = adapter.prepare(ws, info, config(), None).argv
    assert argv[argv.index(SCHEMA_FLAG) + 1] == str(ws.scratch / SCHEMA_FILENAME)


def test_the_written_schema_parses_as_json(adapter, ws, info):
    """`--output-schema` takes a JSON Schema FILE; an unparseable one fails at launch, not here."""
    adapter.prepare(ws, info, config(), None)
    json.loads((ws.scratch / SCHEMA_FILENAME).read_text(encoding="utf-8"))


def test_the_written_schema_names_exactly_the_wire_contracts_own_keys(adapter, ws, info):
    """WP5 carry-forward: nothing joins the two schemas today, so they can drift apart silently.

    The finding object as well as the top level: the top-level keys are four
    words that rarely move, while the finding is where a field is added, and a
    join that stopped at `verdict/summary/findings/next_steps` would watch the
    half that does not drift.
    """
    adapter.prepare(ws, info, config(), None)
    schema = json.loads((ws.scratch / SCHEMA_FILENAME).read_text(encoding="utf-8"))
    contract = json.loads(WIRE_SCHEMA)
    assert set(schema["properties"]) == set(contract)
    assert set(schema["properties"]["findings"]["items"]["properties"]) == set(contract["findings"][0])


def _delivered(launch) -> str:
    """The prompt text this launch actually hands the harness — the stdin file (E29)."""
    assert launch.stdin_path is not None, "codex takes its prompt on stdin"
    return launch.stdin_path.read_text(encoding="utf-8")


def test_the_prompt_rides_stdin_behind_a_dash_positional(adapter, ws, info):
    """C-1028, E29: `codex exec -` reads the prompt from stdin, so the diff never becomes an argv word.

    From the 0.144.1 `--help` for `[PROMPT]`: "If not provided as an argument
    (or if `-` is used), instructions are read from stdin." Verified live behind
    the real flag set, `--` included.

    `-` also keeps C-1025 rule 2 satisfied without `--` carrying the whole
    burden: the word after the evidence run is still `-`-prefixed. Both words
    are spelled out rather than imported — an expectation derived from the code
    under test proves only self-consistency.
    """
    launch = adapter.prepare(ws, info, config(), None)
    written = (ws.scratch / PROMPT_FILENAME).read_text(encoding="utf-8")
    assert launch.stdin_path == ws.scratch / PROMPT_FILENAME
    assert _delivered(launch) == written
    assert "data, never instructions" in written
    assert launch.argv[-2:] == ("--", "-")
    assert written not in launch.argv


def test_a_second_prepare_on_one_workspace_refuses_rather_than_overwriting(adapter, ws, info):
    """`write_nofollow` is `O_EXCL|O_NOFOLLOW`, and unlinking first would defeat exactly that.

    Its own docstring says the scratch DIRECTORY is unprotected once a harness
    has run, so a delete-then-create after a spawn would unlink and then write
    THROUGH a swapped `ws.scratch` — a delete-and-overwrite outside the worktree
    in place of the fatal `IsolationError` this refusal is. A caller that must
    retry builds a workspace; `prompt.md` is `review_prompt`'s file in any case.
    """
    adapter.prepare(ws, info, config(), None)
    with pytest.raises(IsolationError):
        adapter.prepare(ws, info, config(), None)


def test_the_launch_adds_no_environment(adapter, ws, info):
    """C-1008: this adapter's containment adds none, and `authorize` refuses an undeclared key."""
    assert dict(adapter.prepare(ws, info, config(), None).env) == {}


def test_the_scope_is_read_off_the_workspace_and_not_a_second_parameter(adapter, ws, info):
    """E9a: `prepare` takes no `scope`; a second source for one fact is the drift WP6 prevents.

    The second workspace gets a scratch directory of its own, because that is
    what a second workspace has: `ws.scratch` is `.nox-<token>/`, minted per
    workspace with no `exist_ok`. Sharing one made this test the only reason
    `prepare` ever unlinked before writing — a delete-and-overwrite that
    `write_nofollow`'s `O_EXCL|O_NOFOLLOW` exists to refuse.
    """
    code = _delivered(adapter.prepare(ws, info, config(), None))
    plan_scratch = ws.path / ".nox-plan"
    plan_scratch.mkdir()
    plan_ws = Workspace(
        path=ws.path,
        token=ws.token,
        base=ws.base,
        target=ws.target,
        scope="plan-artifact",
        scratch=plan_scratch,
        diff_path=plan_scratch / "review.diff",
        diff=WS_DIFF,
        env=ws.env,
        neutralized=(),
        neutralized_total=0,
        filtered=(),
        filtered_total=0,
        filtered_changed=(),
        filtered_changed_total=0,
        omitted=(),
        omitted_total=0,
        omitted_ignored=0,
    )
    assert "plan or design artifact" not in code
    assert "plan or design artifact" in _delivered(adapter.prepare(plan_ws, info, config(), None))


# ---------------------------------------------------------------------------
# prepare: model selection (C-1030)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("model_class", "effort"), [("fast-balanced", "low"), ("deep-reasoning", "high")])
def test_each_capability_class_resolves_to_the_one_probed_literal(model_class, effort):
    """C-1030: the classes differ by effort, not by model id — one id is what was probed."""
    spec, resolved = resolve_model(CodexAdapter.MODELS, config(model=model_class))
    assert spec == ModelSpecT(model="gpt-5.6-luna", effort=effort)
    assert resolved == model_class


@pytest.mark.parametrize(("model_class", "effort"), [("fast-balanced", "low"), ("deep-reasoning", "high")])
def test_the_model_rides_the_model_flag_and_the_effort_rides_a_second_config_flag(
    adapter, ws, info, model_class, effort
):
    """C-1030: the effort knob is emitted from a typed `ModelSpecT`, never from config argv."""
    argv = adapter.prepare(ws, info, config(model=model_class), None).argv
    assert argv[argv.index(MODEL_FLAG) + 1] == "gpt-5.6-luna"
    assert f"{EFFORT_KEY}={effort}" in argv
    assert argv.count("-c") == 2


def test_no_configured_class_takes_the_harness_default_and_emits_no_model_flag(adapter, ws, info):
    """C-1030 rule 2: an absent class is the harness default with `Review.model = None`."""
    argv = adapter.prepare(ws, info, config(), None).argv
    assert MODEL_FLAG not in argv
    assert not any(word.startswith(f"{EFFORT_KEY}=") for word in argv)


def test_a_class_the_shipped_table_does_not_name_emits_no_model_flag(adapter, ws, info, monkeypatch):
    """C-1030 rule 6: not an error and not a substitution — the honest record is that the harness chose."""
    monkeypatch.setattr(CodexAdapter, "MODELS", {})
    argv = adapter.prepare(ws, info, config(model="deep-reasoning"), None).argv
    assert MODEL_FLAG not in argv
    assert not any(word.startswith(f"{EFFORT_KEY}=") for word in argv)


def test_a_trusted_model_literal_overrides_the_shipped_table(adapter, ws, info):
    """C-1030 rule 1: the literal is trust-gated config, and it wins outright."""
    cfg = config(model="fast-balanced", model_literal="gpt-9-probe", effort="xhigh")
    argv = adapter.prepare(ws, info, cfg, None).argv
    assert argv[argv.index(MODEL_FLAG) + 1] == "gpt-9-probe"
    assert f"{EFFORT_KEY}=xhigh" in argv
    assert "gpt-5.6-luna" not in argv


# ---------------------------------------------------------------------------
# prepare: passthrough policing (C-1023) and the argv prompt bound (C-1028)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "denied",
    ["-c", "--config", "--dangerously-bypass-approvals-and-sandbox", "--dangerously-bypass-hook-trust"],
)
def test_a_denied_flag_in_passthrough_is_refused_by_name(adapter, ws, info, denied):
    """C-1023 refusal 1: `-c` is Codex's own containment route and is never repository-supplied."""
    with pytest.raises(ConfigError) as exc:
        adapter.prepare(ws, info, config(passthrough=(denied, "value")), None)
    assert denied in str(exc.value)


def test_a_bare_positional_in_passthrough_is_refused(adapter, ws, info):
    """C-1023 refusal 3: Codex's prompt IS a positional, so a stray word is not an inert flag."""
    with pytest.raises(ConfigError) as exc:
        adapter.prepare(ws, info, config(passthrough=("just-a-word",)), None)
    assert "just-a-word" in str(exc.value)


@pytest.mark.parametrize("flag", [STREAM_FLAG, SCHEMA_FLAG, "--sandbox", "--ephemeral"])
def test_a_passthrough_copy_of_a_flag_nox_emits_is_refused(adapter, ws, info, flag):
    """C-1023 refusals 2/4: the repository may not re-specify a flag nox owns for this launch."""
    with pytest.raises(ConfigError) as exc:
        adapter.prepare(ws, info, config(passthrough=(flag, "value")), None)
    assert flag in str(exc.value)


def test_a_trailing_value_taking_passthrough_flag_with_no_value_is_refused(adapter, ws, info):
    """C-1023 refusal 5: otherwise the harness binds nox's own first flag as the title."""
    with pytest.raises(ConfigError) as exc:
        adapter.prepare(ws, info, config(passthrough=("--title",)), None)
    assert "--title" in str(exc.value)


def test_a_diff_far_over_the_argv_limit_still_prepares(adapter, ws, info):
    """E29: `MAX_ARG_STRLEN` binds the argv channel, and this harness does not use it.

    A whole-branch review is the first case that clears 128 KiB, and it is also
    nox's primary use case — a refusal here would make the tool unusable for
    what it is for.
    """
    object.__setattr__(ws, "diff", "+" + "a" * (PROMPT_ARGV_LIMIT * 2))

    launch = adapter.prepare(ws, info, config(), None)

    assert max(len(word.encode("utf-8")) for word in launch.argv) < PROMPT_ARGV_LIMIT
    assert ws.diff in _delivered(launch), "verbatim, never trimmed (C-1028)"


# ---------------------------------------------------------------------------
# authorize: the whole launch survives derivation with two `-c` occurrences
# ---------------------------------------------------------------------------


def test_the_launch_carrying_two_config_flags_survives_derivation_on_both_axes(adapter, ws, info, env):
    """C-1025 rules 3/4 interacting: the sandbox key and the effort key share `-c` and must both stand."""
    cfg = config(model="deep-reasoning")
    plan = adapter.containment_plan(cfg, info)
    launch = adapter.prepare(ws, info, cfg, None)
    resolved = {**env, **dict(launch.env)}
    digest = probe_digest(
        plan=plan,
        executable=resolve_executable(BINARY, env),
        launcher=info.launcher,
        env=resolved,
        config_reads=config_read_paths(CONFIG_READS, resolved),
    )
    cache = ProbeCache()
    cache.record(digest)
    inv, derived = authorize(adapter, launch, ws, info, plan, cache, FakeRunner())
    assert inv.argv.count("-c") == 2
    assert derived.write_enforcement == "os"
    assert derived.network_enforcement == "os"


def test_an_unproven_sandbox_probe_refuses_the_launch_rather_than_weakening_it(adapter, ws, info):
    """C-1007/C-1040: `authorize` runs the probe, and a `False` leaves both axes `None`."""
    cfg = config()
    plan = adapter.containment_plan(cfg, info)
    launch = adapter.prepare(ws, info, cfg, None)
    with pytest.raises(UnsupportedCapability):
        authorize(adapter, launch, ws, info, plan, ProbeCache(), FakeRunner())


# ---------------------------------------------------------------------------
# probe: C-1014, C-1020, C-1034(4)
# ---------------------------------------------------------------------------


def test_the_probe_runs_the_version_then_the_login_status_in_the_directory_core_minted(adapter, tmp_path, env):
    """C-1014: `codex --version` exits 0 with no credentials, so one spawn cannot answer the question."""
    runner, _ = _probe(adapter, tmp_path, env, _lines(VERSION_FIXTURE), _lines(AUTHENTICATED))
    assert len(runner.spawned) == 2
    assert "--version" in runner.spawned[0].argv
    assert runner.spawned[1].argv[-len(LOGIN_SUBCOMMAND) :] == LOGIN_SUBCOMMAND
    assert {inv.cwd for inv in runner.spawned} == {tmp_path / "probe-cwd"}


def test_the_probe_resolves_the_binary_to_an_absolute_path_off_the_minimal_path(adapter, tmp_path, env):
    """C-1009: `cwd` is attacker-controlled content, so `argv[0]` is never a bare name."""
    runner, _ = _probe(adapter, tmp_path, env, _lines(VERSION_FIXTURE), _lines(AUTHENTICATED))
    assert runner.spawned[0].argv[0] == str(Path(env["PATH"]) / BINARY)


def test_an_authenticated_probe_reports_the_version_and_the_shipped_tables(adapter, tmp_path, env):
    """C-1020/E3: `verified_against` is read off a re-probe, never copied from a document."""
    _, probed = _probe(adapter, tmp_path, env, _lines(VERSION_FIXTURE), _lines(AUTHENTICATED))
    assert _lines(VERSION_FIXTURE)[0].startswith(VERSION_PREFIX)
    assert probed.version == "0.144.1" == VERIFIED_AGAINST
    assert probed.verified_against == VERIFIED_AGAINST
    assert probed.capabilities == CAPABILITIES
    assert probed.heartbeat_kind == HEARTBEAT_KIND
    assert probed.name == "codex"


def test_an_unauthenticated_probe_refuses_and_leaves_the_credential_hint_to_its_caller(
    adapter, tmp_path, env, monkeypatch
):
    """C-1034(4): the hint is `api._auth_detail`'s, composed from `minimal_env`'s REAL dropped names.

    `Adapter.probe` is never handed that list — claude's own docstring says so —
    and an adapter that composes the hint anyway has to reconstruct one. Codex's
    reconstruction was `AUTH_ENV_HINTS[self.name]` minus what `env` carries, and
    it was wrong twice over: `review()` appends the same sentence pair a second
    time, so the operator reads the whole C-1034(4) hint TWICE; and the table's
    entries are `fnmatchcase` PATTERNS, so an entry like opencode's
    `OPENCODE_*_APIKEY` would be printed to the operator as a variable name that
    exists nowhere.

    So the adapter's half is: nox's own prose naming the harness and the
    condition, no trailer, no variable name, and never a byte of the value.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-be-echoed")
    with pytest.raises(HarnessUnavailable) as exc:
        _probe(adapter, tmp_path, env, _lines(VERSION_FIXTURE), _lines(UNAUTHENTICATED))
    assert exc.value.reason is FailureReason.UNAUTHENTICATED
    assert exc.value.detail == "codex reports it holds no credentials"
    assert AUTH_HINT_TRAILER not in exc.value.detail
    assert "OPENAI_API_KEY" not in exc.value.detail
    assert "sk-must-not-be-echoed" not in exc.value.detail


def test_a_stderr_warning_ahead_of_the_login_answer_is_tolerated(adapter, tmp_path, env):
    """C-1009: `codex login status` writes to stderr and the merged drain delivers noise with it."""
    recorded = _lines(UNAUTHENTICATED)
    assert recorded[0].startswith("WARNING:")
    assert recorded[-1] == LOGGED_OUT
    with pytest.raises(HarnessUnavailable) as exc:
        _probe(adapter, tmp_path, env, _lines(VERSION_FIXTURE), recorded)
    assert exc.value.reason is FailureReason.UNAUTHENTICATED


def test_a_line_merely_containing_the_logged_out_words_does_not_trip_the_refusal(adapter, tmp_path, env):
    """The answer is the whole stripped LINE, never a substring — a note quoting it is not a refusal."""
    login = (f"note: {LOGGED_OUT!r} is the phrase this harness prints when it is not", "Logged in using ChatGPT")
    _, probed = _probe(adapter, tmp_path, env, _lines(VERSION_FIXTURE), login)
    assert probed.version == VERIFIED_AGAINST


def test_the_recorded_authenticated_answer_is_the_line_the_probe_requires(adapter, tmp_path, env):
    """The guard on the test below: the fixture must still carry the POSITIVE line."""
    recorded = _lines(AUTHENTICATED)
    assert recorded[0].startswith(LOGGED_IN_PREFIX)
    _, probed = _probe(adapter, tmp_path, env, _lines(VERSION_FIXTURE), recorded)
    assert probed.version == VERIFIED_AGAINST


@pytest.mark.parametrize(
    "login",
    [(), ("error: unrecognized subcommand 'status'",), ("codex: command failed",)],
    ids=["said-nothing", "subcommand-gone", "failed-some-other-way"],
)
def test_a_login_status_that_answered_neither_line_refuses_rather_than_reading_as_authenticated(
    adapter, tmp_path, env, login
):
    """C-1014: the two-spawn design exists against exactly this, in the other direction.

    `codex login status` exits 0 either way, so the exit status answers nothing
    and the ANSWER is the line. A subcommand that was renamed, or that failed,
    prints no `Not logged in` — and inferring authentication from that absence
    is the 401-retry-loop mid-review the second spawn was added to prevent.
    """
    with pytest.raises(HarnessUnavailable) as exc:
        _probe(adapter, tmp_path, env, _lines(VERSION_FIXTURE), login)
    assert exc.value.reason is FailureReason.UNAUTHENTICATED
    assert exc.value.detail == "codex did not answer whether it holds credentials"
    assert AUTH_HINT_TRAILER not in exc.value.detail


def test_a_binary_that_names_no_version_is_absent(adapter, tmp_path, env):
    """C-1014: `ABSENT` is what a consumer degrades to a graceful skip on (SD § 7.1)."""
    with pytest.raises(HarnessUnavailable) as exc:
        _probe(adapter, tmp_path, env, ("some-other-tool 9.9.9",), _lines(AUTHENTICATED))
    assert exc.value.reason is FailureReason.ABSENT


# ---------------------------------------------------------------------------
# classify: C-1012 — every cell declines, and that is the honest state
# ---------------------------------------------------------------------------


def test_the_classification_table_is_empty():
    """SD § 7.1a admits a cell only where a recorded fixture proves it, and none does."""
    assert CodexAdapter.CLASSIFY == {}


@pytest.mark.parametrize(
    "index",
    range(3),
    ids=["item-level-error", "top-level-http-blob", "top-level-reconnect"],
)
def test_classify_declines_every_recorded_error_shape(adapter, index):
    """C-1012: mapping HTTP 401/429 out of the embedded blob would be a reading no fixture pins.

    `classify` keys on `type`, and all three recorded shapes carry the same one
    — a benign model-metadata warning, an HTTP 400 blob, and a live
    `401 Unauthorized` are all `"error"`. That is why the table is empty and why
    a recorded 401 still adds no cell: an `UNAUTHENTICATED` row keyed on
    `"error"` would claim the warning too.
    """
    recorded = _lines(ERRORS)
    assert len(recorded) == 3
    event = json.loads(recorded[index])
    err = event["item"] if event.get("type") == "item.completed" else event
    assert err["type"] == "error"
    assert "401 Unauthorized" in recorded[2]
    assert adapter.classify(err) is None


# ---------------------------------------------------------------------------
# parse: C-1011, C-1018, C-1019
# ---------------------------------------------------------------------------


def test_the_recorded_findings_stream_resolves_to_the_single_reported_finding(adapter):
    """C-1011: `--output-schema` on bare `codex exec` yields nox's own words and a repo-relative file."""
    out = adapter.parse(_lines(FINDINGS), 0, _hb())
    assert out.status == "ok"
    assert out.verdict == "needs-attention"
    assert len(out.findings) == 1
    assert out.findings[0].file == "bug.py"
    assert out.findings[0].severity == "high"
    assert out.reason is None


def test_the_recorded_approve_stream_resolves_to_approve_with_no_findings(adapter):
    """C-1011: the other recorded shape, so "one finding" is not an artefact of one fixture."""
    out = adapter.parse(_lines(APPROVE), 0, _hb())
    assert out.status == "ok"
    assert out.verdict == "approve"
    assert out.findings == ()


@pytest.mark.parametrize("fixture", [FINDINGS, APPROVE])
def test_no_recorded_stream_reports_a_cost(adapter, fixture):
    """E4: `turn.completed` carries token counts and no cost, so `cost_usd` is always `None` here."""
    assert adapter.parse(_lines(fixture), 0, _hb()).cost_usd is None


def test_the_schema_shaped_preamble_message_never_wins_over_the_final_one(adapter):
    """C-1011: item_0 is an approve emitted before the model started work — taking the first is the bug."""
    recorded = _lines(FINDINGS)
    preamble = json.loads(_first_agent_message(recorded))
    assert preamble["verdict"] == "approve"
    assert preamble["findings"] == []
    out = adapter.parse(recorded, 0, _hb())
    assert out.verdict == "needs-attention"
    assert len(out.findings) == 1


@pytest.mark.parametrize("fixture", [FINDINGS, APPROVE])
def test_a_stream_that_ends_before_turn_completed_is_indeterminate(adapter, fixture):
    """C-1011: without it the last `agent_message` may be the preamble, so no verdict may be read."""
    recorded = _lines(fixture)
    assert json.loads(recorded[-1])["type"] == "turn.completed"
    out = adapter.parse(recorded[:-1], 0, _hb())
    assert out.status == "indeterminate"
    assert out.verdict is None
    assert out.reason is FailureReason.MALFORMED_OUTPUT


@pytest.mark.parametrize(
    ("index", "token"),
    [(0, "definitely-not-a-model"), (1, "invalid_request_error"), (2, "401 Unauthorized")],
    ids=["item-level-error", "top-level-http-blob", "top-level-reconnect"],
)
def test_an_unrecorded_error_event_resolves_indeterminate_with_its_own_name_stamped(adapter, index, token):
    """C-1012/S-1008: without the name, "indeterminate" names no shape a human could add to the table."""
    out = adapter.parse((_lines(ERRORS)[index],), 1, _hb())
    assert out.status == "indeterminate"
    assert out.reason is FailureReason.MALFORMED_OUTPUT
    assert out.detail is not None
    assert token in out.detail


def test_non_json_lines_are_skipped_rather_than_fatal(adapter):
    """C-1009: stderr merges into this stream, so a bare line is noise and not a parse failure."""
    recorded = _lines(APPROVE)
    noisy = ("codex: a bare stderr line", *recorded[:3], "and another one", *recorded[3:])
    out = adapter.parse(noisy, 0, _hb())
    assert out.status == "ok"
    assert out.verdict == "approve"


def test_raw_retains_every_line_including_the_noise(adapter):
    """C-1018: `raw` is what the supervisor delivered, retained unconditionally."""
    recorded = _lines(APPROVE)
    noisy = ("codex: a bare stderr line", *recorded, "and another one")
    out = adapter.parse(noisy, 0, _hb())
    assert [line for line in noisy if line not in out.raw] == []


def test_a_final_message_that_is_not_the_wire_object_is_indeterminate(adapter):
    """C-1011: never `ok` by elimination — a prose answer establishes no verdict."""
    lines = (
        '{"type":"thread.started","thread_id":"t"}',
        '{"type":"turn.started"}',
        '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I could not review this."}}',
        '{"type":"turn.completed","usage":{"input_tokens":1}}',
    )
    out = adapter.parse(lines, 0, _hb())
    assert out.status == "indeterminate"
    assert out.verdict is None
    assert out.reason is not None


def test_a_synthesized_wire_object_resolves_exactly_as_a_recorded_one_does(adapter):
    """The positive control for the synthesized streams below, so a negative cannot pass for the wrong reason."""
    wire = {"verdict": "approve", "summary": "clean", "findings": [], "next_steps": []}
    out = adapter.parse(_wire_stream(wire), 0, _hb())
    assert out.status == "ok"
    assert out.verdict == "approve"
    assert out.summary == "clean"


def test_a_run_nox_killed_reports_killed_rather_than_a_parse_failure(adapter):
    """C-1012: 143 is `128 + SIGTERM` as a harness that trapped the signal reports it."""
    out = adapter.parse(_lines(APPROVE)[:-1], SIGTERM_EXIT, _hb())
    assert out.status != "ok"
    assert out.verdict is None
    assert out.reason is FailureReason.KILLED


def test_a_completed_turn_outranks_our_own_kill(adapter):
    """C-1011/SD § 4.3: "exit_code is recorded, and gates NOTHING" — 143 labels, it does not overrule.

    The corner the four adapters disagreed on. A turn that completed and carried
    a well-formed verdict is the harness's own account of the review; a 143 that
    arrives after it is the process status of a run that had already answered —
    a harness trapping the signal during its own teardown reports exactly that.
    Reading it as a failure would discard a finished review, and reading the exit
    code before the stream is the branch SD § 4.3 forbids.
    """
    out = adapter.parse(_lines(APPROVE), SIGTERM_EXIT, _hb())
    assert out.status == "ok"
    assert out.reason is None


def test_a_reported_error_outranks_our_own_kill_the_way_opencode_and_copilot_resolve_it(adapter):
    """C-1012/SD § 4.3 and § 7.1: the stream's own outcome decides, then — and only then — the exit status.

    The whole order in three rows, because the tiebreak alone does not state it:

    1. **error AND 143** — the ambiguous shape. Codex read the exit status
       before its error table and reported `error`/`KILLED`, where `opencode`
       resolves its error flag first and `claude` its terminal `result` event
       first, so identical evidence resolved two ways across the four adapters
       and plan E38's "unified" claim was false. Fixed for codex, opencode and
       copilot; **`claude` still diverges and this name no longer claims
       otherwise** — it reads `reason_for_exit` above its `api_retry` ladder, a
       row unreachable through nox because `supervise` stamps `TIMED_OUT` before
       a 143 reaches `parse` (E70 names it rather than reordering it). SD § 4.3's `parse` pseudocode
       consults `_first_error_event` before an exit code that "is recorded, and
       gates NOTHING", and SD § 7.1's `exit 143` row labels a run whose stream
       established neither a verdict nor a terminal outcome of its own. A
       reported error IS such an outcome, so it wins.
    2. **error, no 143** — the same resolution, asserted by equality: the exit
       status changes not one field of the answer.
    3. **143, no error** — the row's actual territory, where nothing else
       established anything and `KILLED` is the honest label.
    """
    reported = _lines(ERRORS)[2]
    assert "401 Unauthorized" in reported
    both = adapter.parse((reported,), SIGTERM_EXIT, _hb())
    assert both.status == "indeterminate"
    assert both.reason is FailureReason.MALFORMED_OUTPUT
    assert both.detail is not None
    assert "401 Unauthorized" in both.detail
    assert adapter.parse((reported,), 1, _hb()) == both
    killed = adapter.parse(_lines(APPROVE)[:-1], SIGTERM_EXIT, _hb())
    assert killed.status == "error"
    assert killed.reason is FailureReason.KILLED


def test_an_invented_severity_word_resolves_to_block(adapter):
    """C-1018 through `ParsedOutput.__post_init__`: the two failure directions are not symmetric."""
    wire = {
        "verdict": "needs-attention",
        "summary": "s",
        "findings": [_finding(severity="catastrophic")],
        "next_steps": [],
    }
    out = adapter.parse(_wire_stream(wire), 0, _hb())
    assert out.findings[0].severity == "block"


def test_raw_reconstructs_the_stream_the_supervisor_delivered_verbatim(adapter):
    """C-1018: `runner._drain` keeps the newline `readline` produced, so `"".join` IS the stream.

    Every other test here feeds `splitlines()` output, which is why a join on
    `"\\n"` — doubling every line break against real runner output — passed the
    whole suite.
    """
    delivered = tuple(f"{line}\n" for line in _lines(APPROVE))
    out = adapter.parse(delivered, 0, _hb())
    assert out.raw == "".join(delivered)
    assert "\n\n" not in out.raw
    assert out.verdict == "approve"


DEEP_JSON = "[" * 100_000 + "]" * 100_000
"""One 200 KB line, far under `runner.BYTE_CAP` and under no per-line cap at all.

`json.loads` refuses it with `RecursionError`, which is a `RuntimeError` and not
a `ValueError` — so a decoder guarding only the latter lets it escape `parse`
and `sandbox_probe` alike, and C-1029 totality means a run outcome rather than a
traceback.
"""


def test_a_line_nested_past_the_decoders_recursion_limit_is_skipped_rather_than_fatal(adapter):
    """C-1029: every line of harness output is untrusted input, including its shape."""
    out = adapter.parse((DEEP_JSON, '{"type":"turn.completed"}'), 0, _hb())
    assert out.status == "indeterminate"
    assert out.reason is FailureReason.MALFORMED_OUTPUT


def test_a_line_nested_past_the_decoders_recursion_limit_proves_no_attempt():
    """The same line on the probe's path, where `suppress(OSError, NoxError)` would not have caught it."""
    assert codex.attempt_proven((DEEP_JSON,), RECORDED_NONCE_PATH, RECORDED_NONCE) is False


def test_a_probe_whose_review_leg_emitted_that_line_is_inconclusive_rather_than_fatal(adapter, ws, info, env):
    """C-1029 through the probe: `sandbox_probe` answers `False`, and never a traceback."""
    assert adapter.sandbox_probe(ProbeRunner(ws, review_lines=(DEEP_JSON,)), ws, info, env) is False


def test_a_started_agent_message_arriving_last_does_not_become_the_verdict(adapter):
    """C-1011: the LAST `item.completed` message wins, and `item.started` is not one.

    Without the envelope check a trailing `item.started` agent_message IS
    `messages[-1]`, its text is not the wire object, and a real
    `needs-attention` carrying a `block` finding resolves `indeterminate`
    behind it.
    """
    wire = {"verdict": "needs-attention", "summary": "s", "findings": [_finding(severity="block")], "next_steps": []}
    complete = _wire_stream(wire)
    started = json.dumps(
        {"type": "item.started", "item": {"id": "item_9", "type": "agent_message", "text": "still working"}}
    )
    out = adapter.parse((*complete[:-1], started, complete[-1]), 0, _hb())
    assert out.status == "ok"
    assert out.verdict == "needs-attention"
    assert out.findings[0].severity == "block"


def test_a_failed_turn_refuses_the_run_whatever_else_the_stream_carried(adapter):
    """C-1011: `turn.failed` is checked, not inferred from the absence of `turn.completed`.

    The defence for reading a verdict here was that a failed turn is not a
    completed one — an assumption about the vendor's bookkeeping rather than an
    observation. This stream carries both, which is the case that assumption
    gets wrong.
    """
    wire = {"verdict": "approve", "summary": "clean", "findings": [], "next_steps": []}
    failed = '{"type":"turn.failed","error":{"message":"the request was rejected"}}'
    out = adapter.parse((*_wire_stream(wire), failed), 0, _hb())
    assert out.status == "indeterminate"
    assert out.verdict is None
    assert out.reason is FailureReason.MALFORMED_OUTPUT
    assert out.detail is not None
    assert "the request was rejected" in out.detail


def test_an_ordinary_error_event_does_not_throw_away_a_completed_review(adapter):
    """The deliberate other half: `type:"error"` is advisory, because 0.144.1 uses it for a warning.

    `error-events-0.144.1.jsonl` line 1 is a model-metadata note — refusing a
    review that completed anyway over that is the more likely wrong answer.
    """
    warning = _lines(ERRORS)[0]
    assert "Defaulting to fallback metadata" in warning
    wire = {"verdict": "approve", "summary": "clean", "findings": [], "next_steps": []}
    out = adapter.parse((warning, *_wire_stream(wire)), 0, _hb())
    assert out.status == "ok"
    assert out.verdict == "approve"


def test_the_recorded_rejected_request_resolves_indeterminate_with_its_nested_message(adapter):
    """`turn.failed` nests its message one level deeper, and that arm is what this fixture exercises."""
    recorded = _lines(EFFORT_ENUM)
    nested = json.loads(recorded[-1])["error"]["message"]
    out = adapter.parse(recorded, 0, _hb())
    assert out.status == "indeterminate"
    assert out.verdict is None
    assert out.reason is FailureReason.MALFORMED_OUTPUT
    assert out.detail is not None
    assert nested.strip().partition("\n")[0] in out.detail


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, 1), (4096, 4096), (True, None), (False, None), (0, None), (-3, None), ("7", None), (None, None)],
    ids=["one", "large", "true", "false", "zero", "negative", "string", "null"],
)
def test_a_wire_line_number_is_kept_only_when_it_names_a_line(adapter, value, expected):
    """`isinstance(True, int)` is `True`, so a `bool` reaches `Finding.line_start` and renders as line 1."""
    wire = {
        "verdict": "needs-attention",
        "summary": "s",
        "findings": [_finding(line_start=value, line_end=value)],
        "next_steps": [],
    }
    out = adapter.parse(_wire_stream(wire), 0, _hb())
    assert out.findings[0].line_start == expected
    assert out.findings[0].line_end == expected
    assert not isinstance(out.findings[0].line_start, bool)


@pytest.mark.parametrize("hostile", ["/etc/passwd", "../../etc/passwd", "..", "src/\x1b[2Kapp.py"])
def test_a_finding_pointing_outside_the_worktree_loses_its_location_and_keeps_its_body(adapter, hostile):
    """C-1019 through `ParsedOutput.__post_init__`: the field a machine acts on is the one normalized."""
    wire = {
        "verdict": "needs-attention",
        "summary": "s",
        "findings": [_finding(file=hostile)],
        "next_steps": [],
    }
    out = adapter.parse(_wire_stream(wire), 0, _hb())
    assert out.findings[0].file is None
    assert out.findings[0].title == "a title"


# ---------------------------------------------------------------------------
# on_line: C-1010
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        '{"type":"turn.started"}',
        '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"x"}}',
        '{"type":"error","message":"Reconnecting... 2/5"}',
        '{"type":"turn.completed","usage":{"input_tokens":1}}',
    ],
)
def test_every_json_event_line_is_a_semantic_event(adapter, line):
    """C-1010: `HEARTBEAT_KIND` is `SEMANTIC`, so this is what advances the 120 s window.

    An `error` envelope counts: a retry is a real event and the harness is
    demonstrably alive. Answering `False` to buy a faster timeout would be a lie
    about a live harness.
    """
    assert adapter.on_line(line) is True, line


@pytest.mark.parametrize(
    "line",
    [
        "Reading additional input from stdin...",
        "WARNING: proceeding, even though we could not create PATH aliases: Refusing to create helper binaries",
        "",
        "[1, 2, 3]",
    ],
)
def test_what_the_merged_drain_delivers_from_stderr_is_not_progress(adapter, line):
    """C-1009 merges stderr into this stream; those lines are bytes, not events."""
    assert adapter.on_line(line) is False, line


# ---------------------------------------------------------------------------
# C-1040: `attempt_proven`, the pure decision the live probe cannot reproduce
# ---------------------------------------------------------------------------


def test_the_passing_fixture_still_carries_the_attempts_and_the_nonce_this_suite_names():
    """The guard on every assertion below: a re-recorded fixture must not silently pass them."""
    recorded = _text(PROBE_PASS)
    assert [attempt for attempt in RECORDED_ATTEMPTS if attempt not in recorded] == []
    assert recorded.count(RECORDED_NONCE) >= 2


def test_the_declined_fixture_records_two_blocked_attempts_and_not_one_command_item():
    """C-1040's withheld clause, verified in the fixture rather than asserted in prose.

    This is why `status == "failed"` cannot be the discriminator on 0.144.1: the
    sandbox blocked both commands, the model reported the denial text and the
    exit status, and the harness emitted no `command_execution` item at all —
    not even `item.started`.
    """
    recorded = _lines(PROBE_DECLINED)
    items = [json.loads(line).get("item", {}).get("type") for line in recorded if "item" in json.loads(line)]
    assert items and "command_execution" not in items
    text = "\n".join(recorded)
    assert [attempt for attempt in DECLINED_ATTEMPTS if attempt not in text] == []


def test_an_item_carrying_the_fallback_and_the_nonce_proves_the_attempt():
    """C-1040: the nonce reached the output through the attempt's own failure branch.

    Handed the nonce PATH, which is what `_review_leg` passes; `attempt_proven`
    builds the `|| cat <path>` pattern from it. Not parametrized: both recorded
    items name the same path (see `RECORDED_NONCE_PATH`).
    """
    assert codex.attempt_proven(_lines(PROBE_PASS), RECORDED_NONCE_PATH, RECORDED_NONCE) is True


def test_a_stream_with_no_command_item_proves_nothing():
    """C-1040: a model that DECLINED is indistinguishable from a blocked one except by that absence."""
    assert codex.attempt_proven(_lines(PROBE_DECLINED), RECORDED_NONCE_PATH, RECORDED_NONCE) is False


def test_an_item_whose_output_carries_a_different_nonce_proves_nothing():
    """The item alone is not the evidence — a run against an absent sandbox emits one too."""
    assert codex.attempt_proven(_lines(PROBE_PASS), RECORDED_NONCE_PATH, "0" * (NONCE_BYTES * 2)) is False


def test_a_nonce_that_only_a_model_message_carries_proves_nothing():
    """C-1040: the item's presence is required, so a model narrating the nonce is not evidence."""
    lines = (
        '{"type":"turn.started"}',
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "item_1",
                    "type": "agent_message",
                    "text": f"I ran `{RECORDED_ATTEMPTS[0]}` and it printed {RECORDED_NONCE}",
                },
            }
        ),
        '{"type":"turn.completed","usage":{}}',
    )
    assert codex.attempt_proven(lines, RECORDED_NONCE_PATH, RECORDED_NONCE) is False


def test_an_item_that_only_started_proves_nothing():
    """`item.started` carries an empty `aggregated_output`, so a started-only item has no nonce in it."""
    started = tuple(line for line in _lines(PROBE_PASS) if '"item.started"' in line and RECORDED_ATTEMPTS[0] in line)
    assert len(started) == 1
    assert codex.attempt_proven(started, RECORDED_NONCE_PATH, RECORDED_NONCE) is False


def test_non_json_lines_interleaved_with_the_stream_do_not_break_the_decision():
    """C-1009: stderr merges into this stream too, and a bare line must not lose the evidence."""
    noisy = ("codex: a bare stderr line", *_lines(PROBE_PASS), "and another one")
    assert codex.attempt_proven(noisy, RECORDED_NONCE_PATH, RECORDED_NONCE) is True


def test_one_attempts_evidence_is_never_credited_to_another():
    """Both attempts must be proven separately; a stream carrying one is not a stream carrying both."""
    assert codex.attempt_proven(_lines(PROBE_PASS), "nonce-some-other-run-0", RECORDED_NONCE) is False


def test_an_index_is_never_credited_to_the_attempt_whose_path_it_prefixes():
    """`nonce-<token>-1` is a prefix of `nonce-<token>-10`, and the index is what separates the attempts.

    Latent at two attempts and live the day a third command joins `_controls`,
    which is exactly when nobody re-reads this matcher — so the pattern ends on
    a `(?![\\w-])` boundary and this is the case that holds it there.
    """
    item = json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "/bin/zsh -c 'touch ./m || cat ./nonce-tok-10'",
                "aggregated_output": RECORDED_NONCE,
            },
        }
    )
    assert codex.attempt_proven((item,), "nonce-tok-10", RECORDED_NONCE) is True
    assert codex.attempt_proven((item,), "nonce-tok-1", RECORDED_NONCE) is False


@pytest.mark.parametrize(
    "command",
    [
        "touch ./m||cat ./nonce-tok-0",
        "touch ./m || cat nonce-tok-0",
        'touch ./m || cat "./nonce-tok-0"',
        "touch ./m ||  cat  './nonce-tok-0'",
    ],
    ids=["no-spaces", "no-dot-slash", "double-quoted", "extra-spaces"],
)
def test_a_shell_that_respells_the_fallback_still_proves_the_attempt(command):
    """A tail that does not match REFUSES every Codex review on that machine, so the pattern tolerates spelling.

    The one live observation is zsh re-quoting the wrapper and leaving the tail
    verbatim; that is not a guarantee about every harness, and the failure
    direction here is total — `sandbox_probe` answers `False`, both axes null,
    `check_capabilities` refuses. What is NOT tolerated is the `||` going
    missing, which `test_a_bare_read_of_the_nonce_file_is_not_an_attempt` holds.
    """
    item = json.dumps(
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": command, "aggregated_output": RECORDED_NONCE},
        }
    )
    assert codex.attempt_proven((item,), "nonce-tok-0", RECORDED_NONCE) is True


# ---------------------------------------------------------------------------
# C-1040: the deterministic leg, and what makes the probe inconclusive
# ---------------------------------------------------------------------------


def test_a_probe_whose_every_observation_passes_returns_true(adapter, ws, info, env):
    """The baseline the whole section is written against, and the one `True` in it.

    Without it `all(...)` is never true, `_review_leg` could `return False`
    outright, `_connected` could answer `False` always, and every assertion
    below would still pass — none of them can tell "refused for my reason" from
    "refused for every reason". It also pins the accept queue's draining: the
    unsandboxed control connects, and the sandboxed attempt after it is only
    seen as unconnected because `_connected` took that connection off the queue.
    """
    assert adapter.sandbox_probe(ProbeRunner(ws), ws, info, env) is True


def test_the_probe_runs_its_controls_unsandboxed_and_then_the_three_sandboxed_legs(adapter, ws, info, env):
    """C-1040: the order is the argument — a control after the attempt would prove nothing."""
    runner = ProbeRunner(ws)
    assert adapter.sandbox_probe(runner, ws, info, env) is True
    assert [_spawn_kind(inv.argv) for inv in runner.spawned] == [
        "control_touch",
        "control_bash",
        "sandboxed_ls",
        "sandboxed_touch",
        "sandboxed_bash",
        "review",
    ]
    for inv in runner.spawned[:2]:
        assert Path(inv.argv[0]).name != BINARY, "a control that ran through codex controls nothing"
        assert "--sandbox" not in inv.argv
        assert not any(word.startswith("sandbox_mode=") for word in inv.argv)


def test_the_deterministic_leg_spawns_codex_sandbox_with_the_read_only_setting(adapter, ws, info, env):
    """C-1040: no model is in the loop here, so "was it attempted" is not a question at all."""
    runner = ProbeRunner(ws)
    adapter.sandbox_probe(runner, ws, info, env)
    argv = next(inv.argv for inv in runner.spawned if _spawn_kind(inv.argv).startswith("sandboxed_"))
    assert SANDBOX_SUBCOMMAND[0] in argv
    assert argv[argv.index("-c") + 1] == f"sandbox_mode={SANDBOX_MODE}"
    assert "--" in argv


def test_the_deterministic_leg_never_carries_the_flag_that_subcommand_rejects(adapter, ws, info, env):
    """`codex sandbox --strict-config` is `error: unexpected argument` — adding it refuses every leg."""
    runner = ProbeRunner(ws)
    adapter.sandbox_probe(runner, ws, info, env)
    for inv in runner.spawned:
        if _spawn_kind(inv.argv).startswith("sandboxed_"):
            assert [flag for flag in CONFIG_FLAGS if flag in inv.argv] == []


def test_the_review_leg_runs_the_argv_shape_the_review_itself_will_run(adapter, ws, info, env):
    """C-1040: what passes here must be the invocation that later runs, or the pass transfers nothing.

    `CONFIG_FLAGS` is what makes this the leg that validates the *setting* —
    `--strict-config` refuses an unknown key, and the deterministic leg cannot
    carry it — and `SANDBOX_EVIDENCE` must be the contiguous run
    `_argv_corroborates` looks for.
    """
    runner = ProbeRunner(ws)
    assert adapter.sandbox_probe(runner, ws, info, env) is True
    argv = runner.spawned[-1].argv
    assert argv[1:2] == SUBCOMMAND[:1]
    assert STREAM_FLAG in argv
    assert [flag for flag in CONFIG_FLAGS if flag not in argv] == []
    width = len(SANDBOX_EVIDENCE)
    assert [start for start in range(len(argv) - width) if argv[start : start + width] == SANDBOX_EVIDENCE]


@pytest.mark.parametrize(
    "knob",
    [
        {"control_write_status": 1},
        {"control_write_creates": False},
        {"control_network_status": 1},
        {"control_network_connects": False},
    ],
    ids=["write-exited-nonzero", "write-created-nothing", "network-exited-nonzero", "network-reached-nothing"],
)
def test_a_positive_control_that_did_not_succeed_makes_the_probe_inconclusive(adapter, ws, info, env, knob):
    """C-1040: a negative observation that could not have come out positive is not evidence.

    Each attempt runs unsandboxed first. On a host where `bash` is absent or
    built without `/dev/tcp`, or where the write would not have landed anyway,
    the sandboxed attempt exits non-zero for a reason that has nothing to do
    with containment — and without these four, `network_enforcement="os"` is
    stamped with no network sandbox present at all.
    """
    assert adapter.sandbox_probe(ProbeRunner(ws, **knob), ws, info, env) is False


def test_the_write_control_removes_the_marker_it_created(adapter, ws, info, env):
    """Otherwise the control's own file is what step 2 finds, and every probe is inconclusive."""
    runner = ProbeRunner(ws)
    assert adapter.sandbox_probe(runner, ws, info, env) is True
    assert sorted(path.name for path in ws.path.iterdir()) == [ws.scratch.name]


def test_a_read_control_the_sandbox_refused_makes_the_probe_inconclusive(adapter, ws, info, env):
    """C-1040: without it a sandbox refusing EVERY command looks like one that blocked the two attempts."""
    assert adapter.sandbox_probe(ProbeRunner(ws, read_status=1), ws, info, env) is False


def test_a_write_attempt_the_sandbox_allowed_makes_the_probe_inconclusive(adapter, ws, info, env):
    """C-1040 step 2: nox holds the child's exit status, so a zero here is the sandbox absent."""
    assert adapter.sandbox_probe(ProbeRunner(ws, write_status=0), ws, info, env) is False


def test_a_network_attempt_the_sandbox_allowed_makes_the_probe_inconclusive(adapter, ws, info, env):
    """The other axis of the same observation: a zero exit is the sandbox absent, not a blocked connect."""
    assert adapter.sandbox_probe(ProbeRunner(ws, network_status=0), ws, info, env) is False


def test_an_attempt_that_never_answered_is_not_read_as_a_blocked_one(adapter, ws, info, env, monkeypatch):
    """`_blocked(None)` must be `False`: no status is no evidence, and a signal is not a refusal.

    The spawn is also signalled rather than left running — up to four of these
    run per probe and one of them is a whole model turn.
    """
    signalled: list[int] = []
    monkeypatch.setattr(codex, "_signal_group", signalled.append)
    runner = ProbeRunner(ws, never_answers="sandboxed_touch")
    assert adapter.sandbox_probe(runner, ws, info, env) is False
    assert signalled == [UNREACHABLE_PGID]


def test_a_review_leg_that_never_answered_makes_the_probe_inconclusive(adapter, ws, info, env):
    """The evidence is the stream, and a spawn nox stopped waiting on has no complete stream.

    The real signalling primitive runs here rather than a replacement: the fake
    reports `UNREACHABLE_PGID`, so the call resolves `ESRCH` and reaches
    nothing, which is also the swallow that path depends on.
    """
    assert adapter.sandbox_probe(ProbeRunner(ws, never_answers="review"), ws, info, env) is False


@pytest.mark.parametrize(
    "knob",
    [{"review_overflowed": True}, {"review_collector_failure": OSError("the drain thread died")}],
    ids=["truncated", "collector-died"],
)
def test_a_review_leg_whose_output_nox_could_not_trust_makes_the_probe_inconclusive(adapter, ws, info, env, knob):
    """C-1009/E7: a truncated stream is missing items, and a missing item is exactly the evidence."""
    assert adapter.sandbox_probe(ProbeRunner(ws, **knob), ws, info, env) is False


def test_a_marker_the_sandboxed_write_left_behind_makes_the_probe_inconclusive(adapter, ws, info, env):
    """C-1040 step 2: the file must not exist afterwards, whatever the exit status said."""
    assert adapter.sandbox_probe(ProbeRunner(ws, write_leaves_marker=True), ws, info, env) is False


def test_a_marker_the_sandboxed_write_left_behind_is_refused_before_the_model_turn(adapter, ws, info, env):
    """The deterministic check gates the review leg, so a harness cannot tidy the evidence away.

    Here the write attempt exits non-zero AND leaves the marker, and the review
    leg would remove it. Only the deterministic check sees that — and it is also
    what keeps a probe that has already failed from spending a whole model turn.
    """
    runner = ProbeRunner(ws, write_leaves_marker=True, review_removes_marker=True)
    assert adapter.sandbox_probe(runner, ws, info, env) is False
    assert [inv for inv in runner.spawned if _spawn_kind(inv.argv) == "review"] == []


def test_a_marker_the_review_leg_left_behind_makes_the_probe_inconclusive(adapter, ws, info, env):
    """The same observation on the model-generated side, which the deterministic check cannot see."""
    assert adapter.sandbox_probe(ProbeRunner(ws, review_leaves_marker=True), ws, info, env) is False


def test_a_connection_that_reached_the_listener_makes_the_probe_inconclusive(adapter, ws, info, env):
    """The accept queue is nox's own, so this is the one network observation no harness can misreport."""
    assert adapter.sandbox_probe(ProbeRunner(ws, network_connects=True), ws, info, env) is False


def test_a_review_leg_that_reached_the_listener_makes_the_probe_inconclusive(adapter, ws, info, env):
    """Model-generated commands are the half the deterministic leg cannot speak for."""
    assert adapter.sandbox_probe(ProbeRunner(ws, review_connects=True), ws, info, env) is False


def test_a_review_leg_proving_only_one_attempt_makes_the_probe_inconclusive(adapter, ws, info, env):
    """Both attempts, separately: a stream carrying one is not a stream carrying both."""
    assert adapter.sandbox_probe(ProbeRunner(ws, review_items=1), ws, info, env) is False


def test_one_batched_item_cannot_prove_an_attempt_that_printed_no_nonce(adapter, ws, info, env):
    """Codex batches, so a per-attempt nonce is what keeps "each failed" from becoming "one did".

    The item here carries BOTH attempt spellings in its `command` and the output
    of the one that failed. With a single nonce shared between the attempts, that
    one item satisfies both calls — including for the write attempt, which
    succeeded and printed nothing of its own.
    """
    assert adapter.sandbox_probe(ProbeRunner(ws, review_batched=True), ws, info, env) is False


def test_a_bare_read_of_the_nonce_file_is_not_an_attempt(adapter, ws, info, env):
    """C-1040: the evidence must bind the nonce to an attempt, not merely to a file the model read.

    The nonce sits in the worktree, the read-only sandbox lets the model read
    it, and the probe's own ask tells it the path — so `cat ./nonce-<token>-0`
    is a real `command_execution` item carrying that path and that value while
    nothing was attempted. Matching the path alone accepted it. The
    discriminator is `|| cat ./<path>`: quote-free, so the login shell's
    re-quoting of the attempt cannot move it, and absent from any command that
    did not run something ahead of the fallback.
    """
    assert adapter.sandbox_probe(ProbeRunner(ws, review_bare_cat=True), ws, info, env) is False


def test_an_item_that_is_not_a_command_execution_proves_nothing(adapter, ws, info, env):
    """C-1040 names the item type, and a model can put any words it likes in a message."""
    assert adapter.sandbox_probe(ProbeRunner(ws, review_item_type="agent_message"), ws, info, env) is False


def test_a_review_leg_whose_attempts_emitted_no_item_makes_the_probe_inconclusive(adapter, ws, info, env):
    """C-1040: the deterministic leg passing is not enough — the mode must reach model-generated commands."""
    runner = ProbeRunner(ws, review_lines=_lines(PROBE_DECLINED))
    assert adapter.sandbox_probe(runner, ws, info, env) is False


def test_a_review_leg_replaying_another_runs_nonce_makes_the_probe_inconclusive(adapter, ws, info, env):
    """C-1040: the nonce is per-run, so a recorded stream can never satisfy a live probe."""
    runner = ProbeRunner(ws, review_lines=_lines(PROBE_PASS))
    assert adapter.sandbox_probe(runner, ws, info, env) is False


def test_nothing_the_probe_writes_or_checks_has_a_name_the_repository_could_guess(adapter, ws, info, env):
    """The marker is `PROBE_MARKER` plus a per-run token, never the bare literal.

    A fixed name is a name the branch under review can read out of the adapter
    source and commit at its own root: the check is a bare `exists()`, no
    `NEUTRALIZE_*` member covers it, and one empty file would make the probe
    permanently inconclusive, both axes `None`, and `check_capabilities` refuse
    — a hostile repository escaping the only OS-enforced harness by adding a
    file.
    """
    (ws.path / PROBE_MARKER).write_text("planted by the branch under review", encoding="utf-8")
    first = ProbeRunner(ws)
    assert adapter.sandbox_probe(first, ws, info, env) is True
    second = ProbeRunner(ws)
    assert adapter.sandbox_probe(second, ws, info, env) is True
    markers = {runner.marker_name() for runner in (first, second)}
    assert PROBE_MARKER not in markers
    assert len(markers) == 2
    assert all(name.startswith(f"{PROBE_MARKER}-") for name in markers)


def test_the_probe_is_re_runnable_on_one_workspace(adapter, ws, info, env):
    """`write_nofollow` is `O_EXCL`, so a fixed nonce name makes every retry `False` for a reason
    that has nothing to do with the sandbox — swallowed, permanent and silent.

    `authorize` caches only a PASSING probe, so every retry re-enters this.
    """
    first, second = ProbeRunner(ws), ProbeRunner(ws)
    assert adapter.sandbox_probe(first, ws, info, env) is True
    assert adapter.sandbox_probe(second, ws, info, env) is True
    nonces = (*first.nonce_names(), *second.nonce_names())
    assert len(nonces) == 4, nonces
    assert len(set(nonces)) == 4, "a name reused across runs or attempts is an O_EXCL collision waiting"
    # E20: the review spawns into this same worktree, so every file the probe
    # wrote is gone before `authorize` returns — otherwise nox's own nonce reads
    # as repository content and draws a false prompt-injection finding.
    assert [name for name in nonces if (ws.path / name).exists()] == []


# ---------------------------------------------------------------------------
# Static properties of the shipped adapter source (D-ac, C-1023)
# ---------------------------------------------------------------------------

ADAPTER_TEXT = ADAPTER_SOURCE.read_text(encoding="utf-8")
ADAPTER_STRINGS = tuple(
    node.value
    for node in ast.walk(ast.parse(ADAPTER_TEXT))
    if isinstance(node, ast.Constant) and isinstance(node.value, str)
)


@pytest.mark.parametrize("flag", sorted(NEVER_EMITTED))
def test_the_codex_adapter_never_spells_a_containment_lifting_flag(flag):
    """C-1023: every member LIFTS a control, so the offending word must be visible in review."""
    assert len(ADAPTER_STRINGS) >= 20, "an empty scan would pass silently"
    assert flag not in ADAPTER_STRINGS


def test_no_sentence_in_this_adapter_claims_its_containment_bounds_descendant_lifetime():
    """D-ac: Seatbelt and Landlock constrain what a process may touch, not whether it outlives the review.

    A word list alone cannot be the check — the adapter's own honest disclaimer
    uses every one of these words. So each sentence carrying one must also carry
    a negation, and at least one such sentence must exist, or the scan proves
    nothing.
    """
    sentences = re.split(r"(?<=[.!?])\s+", ADAPTER_TEXT)
    carrying = [s for s in sentences if any(word in s.lower() for word in LIFETIME_WORDS)]
    assert carrying, "the scan found no lifetime vocabulary at all and would pass vacuously"
    claiming = [s for s in carrying if not any(negation in s.lower() for negation in NEGATIONS)]
    assert claiming == []


def test_no_recorded_codex_fixture_reads_as_a_claim_about_descendant_lifetime():
    """D-ac: "nothing here — docstring, plan or fixture — may read as if the sandbox reaped anything"."""
    files = sorted(path for path in FIXTURES.iterdir() if path.is_file())
    assert len(files) >= 10, f"the fixture directory was not enumerated: {files}"
    offenders = [
        (path.name, word)
        for path in files
        for word in LIFETIME_WORDS
        if word in path.read_text(encoding="utf-8", errors="replace").lower()
    ]
    assert offenders == []


def test_the_prompt_carries_the_diff_so_the_reviewer_reviews_a_change(adapter, ws, info):
    """The live NxN matrix's first blocker: this adapter delivered NO diff at all.

    The harness is handed a worktree checked out at the AFTER commit and, before
    this, a prompt asserting the diff it was given was the whole change. Nothing
    in the argv carried one. The prompt is the delivery route, so the assertion is
    on what stdin delivers: `Workspace.diff` reaches the harness verbatim.
    """
    assert WS_DIFF.rstrip("\n") in _delivered(adapter.prepare(ws, info, config(), None))
