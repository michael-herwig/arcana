"""OpenCode 1.18.22 through the real launcher — the claims only the binary can settle.

C-1009, C-1014(a3), C-1020, C-1023, C-1032, C-1037, D-s, R9, R10, S-1003.

Runs only under `NOX_CONTRACT=1`, and every test opens with `require_harness`,
which runs the adapter's own `probe()` through a real `SubprocessRunner` under
the C-1008 minimal environment. On a machine with no provider in OpenCode's
store that probe raises `UNAUTHENTICATED` and the whole file skips — the honest
outcome, and the one C-1037(2) turns into a release failure. Nothing below
weakens an assertion to survive that state: each one spends the real binary.

The three claims SD § 6.3 makes and never proved (R9) are the reason this file
exists: `--pure` actually skipping `.opencode/plugins/`, `OPENCODE_CONFIG_CONTENT`
actually being read, and the launcher not escaping the process group nox created
for the child. Anything not observed here stays `attested` in the adapter.

**One of the three came back negative and the tests below say so.** On 1.18.22
`--pure` does NOT stop a repository-authored `.opencode/plugins/` module from
executing — the flag'd review ran it exactly as the plain one did, in either
flag position. What closes that route is core, on both paths a harness can
start on: `workspace.NEUTRALIZE_DIRS` carries `.opencode`, so C-1005 drops the
directory out of both synthetic trees, and `probe_cwd` mints a fresh empty
directory for the probe. E3 makes the probe authoritative over SD § 6.3, so
these tests pin the refutation rather than the design's expectation.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from nox.adapters.opencode import CONFIG_ENV, VERIFIED_AGAINST, OpenCodeAdapter, deny_config
from nox.config import ConfigError, HarnessConfig, minimal_env
from nox.harness import DENIED_FLAGS, launch_argv, police_passthrough, version_warning
from nox.liveness import Heartbeat, Liveness, TimeoutPolicy
from nox.prompt import WIRE_SCHEMA
from nox.runner import Invocation, SubprocessRunner, supervise
from nox.workspace import NEUTRALIZE_DIRS

HARNESS = "opencode"

SD_DENIED_FLAGS = (
    "--auto",
    "--share",
    "--attach",
    "--port",
    "--command",
    "--continue",
    "-s",
    "--session",
    "--fork",
    "-f",
    "--file",
    "--dir",
    "-i",
    "--interactive",
)
"""The flags the plan's 7c bullet names for `DENIED_FLAGS`, spelled out here.

Membership in the shipped set and existence in the real flag vocabulary are
both pinned in the UNIT tier, against the committed help fixtures, so they hold
on CI and on a machine with no credential. This tier asserts the refusal itself
— what a repository actually meets — and re-pins the vocabulary against the
live binary rather than the recording.
"""

EVIL_PLUGIN = """\
import { writeFileSync } from "fs";
writeFileSync("evil-marker.txt", "the plugin executed");
export const Evil = async () => ({});
"""
"""SD § 6.3's sharpest edge: a branch-authored plugin with Bun shell access.

Writes into the cwd rather than a fixed path, because the cwd is the only thing
this test controls — the C-1008 environment carries no variable a plugin could
be told to read.
"""

PLUGIN_MARKER = "evil-marker.txt"

SAMPLE_PROMPT = (
    "Reply with a single JSON object and nothing else: "
    '{"verdict":"approve","summary":"contract probe","findings":[],"next_steps":[]}'
)
"""One short review-shaped request. Short on purpose: this tier spends real tokens."""


def _env(tmp_path: Path) -> dict[str, str]:
    env, _ = minimal_env(tmp_path, tmp_path / "worktree")
    return env


def _hostile_cwd(tmp_path: Path) -> Path:
    """A directory holding the § 9.4 plugin, so `--pure` is asserted against a live one."""
    cwd = tmp_path / "hostile"
    plugins = cwd / ".opencode" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "evil.ts").write_text(EVIL_PLUGIN, encoding="utf-8")
    return cwd


def _run(info, env: dict[str, str], cwd: Path, *args: str, timeout: float = 600.0):
    """Spawn one real harness invocation through the probed launcher and collect it.

    Returns:
        `(exit_code, lines)` — the merged stream in arrival order.

    **600 s, not 240 s (E71).** The old ceiling sat inside the spread of a
    non-`--pure` run: measured over eleven runs of one invocation on one
    machine, 7.7-213 s passing and a 242 s run killed by the deadline itself.
    A ceiling under a heavy-tailed distribution fires on a slow run rather than
    a stuck one, which is the opposite of its job; and moving it to just past
    the worst observation reproduces the defect one sample later. 600 s is
    ~2.5x the slowest passing run and still bounds a genuine hang.
    """
    proc = SubprocessRunner().spawn(Invocation(argv=launch_argv(info.launcher, env, *args), cwd=cwd, env=env))
    collected: list[str] = []
    deadline = time.monotonic() + timeout
    while True:
        collected.extend(proc.lines(0.2))
        status = proc.wait(0.0)
        if status is not None:
            collected.extend(proc.lines(0.0))
            return status, tuple(collected)
        if time.monotonic() > deadline:  # pragma: no cover - contract tier only
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(5.0)
            pure = "--pure" in args
            pytest.fail(
                f"{' '.join(args)} did not finish within {timeout}s "
                f"({len(collected)} lines seen, --pure={pure}).\n"
                + (
                    ""
                    if pure
                    else "A non-`--pure` run loads the operator's own ~/.config/opencode "
                    "(global plugins, agents, skills) — C-1008 forwards the real HOME and "
                    "sets no XDG_CONFIG_HOME — and runs 10-60x slower than the `--pure` "
                    "sibling. Check that config and the machine's load BEFORE the fixture."
                )
            )


def _denials(lines: tuple[str, ...]) -> int:
    """Count the `deny` actions in an `agent list` listing, colour codes and all."""
    return sum(line.count('"action": "deny"') for line in lines)


def _group_members(pgid: int) -> tuple[str, ...]:
    """Every live pid in one process group — the whole descendant set, not just the child.

    `SubprocessRunner` spawns with `start_new_session`, so the group is exactly
    what nox created for this run and nothing else can be in it.
    """
    result = subprocess.run(["ps", "-o", "pid=", "-g", str(pgid)], capture_output=True, text=True, check=False)
    return tuple(result.stdout.split())


def _ps_ids(pid: int, deadline: float) -> tuple[int, int] | None:
    """Read one live process's session and process-group ids, or `None` if it is gone."""
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["ps", "-o", "sid=,pgid=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        words = result.stdout.split()
        if len(words) == 2:
            return int(words[0]), int(words[1])
        time.sleep(0.05)
    return None


# ---------------------------------------------------------------------------
# C-1014(a3), C-1020: presence, version and the recorded release
# ---------------------------------------------------------------------------


def test_the_probed_version_is_the_release_the_fixtures_were_recorded_from(require_harness):
    """C-1020, E3: a drift here means the committed fixtures need re-recording, not a code change."""
    info = require_harness(HARNESS)
    assert info.verified_against == VERIFIED_AGAINST
    assert info.version == VERIFIED_AGAINST, version_warning(info)


def test_the_probe_establishes_exactly_the_capabilities_the_adapter_can_prove(require_harness):
    """C-1013, R9: the deny is a config convention, so `ENFORCED_READ_ONLY` is never claimed."""
    info = require_harness(HARNESS)
    assert {capability.value for capability in info.capabilities} == {"enumerable_deny"}
    assert info.heartbeat_kind is Liveness.SEMANTIC


# ---------------------------------------------------------------------------
# C-1009: the launcher does not escape the group nox created
# ---------------------------------------------------------------------------


def test_the_harness_stays_in_the_session_and_group_nox_spawned_it_into(require_harness, tmp_path):
    """C-1009, D-s: `ocx package exec` `execve`s, so the harness IS the direct child.

    `SubprocessRunner` spawns with `start_new_session`, so the child is its own
    session and group leader and both ids equal its pid. A launcher that forked
    and called `setsid()` would leave a harness in a session nox cannot signal —
    the residual `harness.py` names and this test is the only thing that sees.
    """
    info = require_harness(HARNESS)
    env = _env(tmp_path)
    cwd = tmp_path / "run"
    cwd.mkdir()
    argv = launch_argv(info.launcher, env, "--pure", "run", "--format", "json", SAMPLE_PROMPT)
    proc = SubprocessRunner().spawn(Invocation(argv=argv, cwd=cwd, env=env))
    try:
        ids = _ps_ids(proc.pid, time.monotonic() + 30.0)
        assert ids is not None, "the harness exited before ps could sample it"
        assert ids == (proc.pid, proc.pid)
    finally:
        with contextlib.suppress(OSError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(10.0)


def test_a_review_that_times_out_is_proven_killed_through_the_launcher(require_harness, tmp_path):
    """C-1009, C-1010, Step 7x.4: the kill ladder reaches a harness behind a package runtime.

    The whole point of the launcher question: `ocx package exec` `execve`s, so
    nox's SIGTERM to the process group reaches the harness itself. A wrapper
    that forked would leave the model running after `supervise` returned, and
    the only observable is that no process in the group survives the ladder.
    """
    info = require_harness(HARNESS)
    env = _env(tmp_path)
    cwd = tmp_path / "timeout"
    cwd.mkdir()
    argv = launch_argv(info.launcher, env, "--pure", "run", "--format", "json", SAMPLE_PROMPT)
    proc = SubprocessRunner().spawn(Invocation(argv=argv, cwd=cwd, env=env))
    pid = proc.pid
    result = supervise(
        proc,
        TimeoutPolicy(wall_clock_s=1, silence_s=None, grace_s=5.0),
        Heartbeat(Liveness.PROCESS_ONLY, 0.0, 0.0),
        OpenCodeAdapter().on_line,
    )
    assert result.reason is not None, result
    assert _group_members(pid) == (), "a descendant outlived the kill ladder"


# ---------------------------------------------------------------------------
# R9: what `--pure` is actually worth, and what really closes the plugin route
# ---------------------------------------------------------------------------


def test_a_probe_startup_does_not_execute_a_branch_authored_plugin(require_harness, tmp_path):
    """C-1014: neither probe spawn loads `.opencode/plugins/` on 1.18.22.

    `probe` is called with a chosen cwd rather than through `probe_harness`
    precisely because the property under test is what happens in a directory
    that HOLDS a plugin — core's minted directory never can. The observed reason
    is the SUBCOMMAND, not the flag: a `--version` and a `providers list` do not
    start a session, and the two tests below show a `run` does whether or not
    `--pure` is present. `probe_cwd` is what makes this moot on the real path.

    The config is rebuilt from the launcher the tier's own probe resolved, not
    left bare: this harness has no binary on `PATH` (D-s), so a bare
    `HarnessConfig()` would refuse `ABSENT` before reaching the directory.
    """
    info = require_harness(HARNESS)
    cwd = _hostile_cwd(tmp_path)
    OpenCodeAdapter().probe(SubprocessRunner(), HarnessConfig(launcher=info.launcher.prefix), _env(tmp_path), cwd)
    assert not (cwd / PLUGIN_MARKER).exists()


def test_the_pure_flag_does_not_stop_a_branch_authored_plugin(require_harness, tmp_path):
    """R9 refuted, E3: SD § 6.3's reading of `--pure` is not what 1.18.22 does.

    The plan's 7c bullet made emission conditional on the opposite result. This
    asserts the negative rather than dropping the flag, because the refutation
    is the finding: an adapter that kept `--pure` in `argv_evidence` as a
    *proven* plugin guard would be stamping containment it does not have. It
    stays in the evidence set as a derivation tripwire only — the mechanism is
    `config-deny`, which `_mechanism_corroborated` backs on `env_evidence`
    alone, so this word promotes no axis.
    """
    info = require_harness(HARNESS)
    cwd = _hostile_cwd(tmp_path)
    _run(info, _env(tmp_path), cwd, "--pure", "run", "--format", "json", SAMPLE_PROMPT)
    assert (cwd / PLUGIN_MARKER).exists()


def test_an_ordinary_review_executes_it_too_which_is_what_c1005_is_for(require_harness, tmp_path):
    """R9: the control, and the reason the residual is closed in core rather than in argv.

    A failure here does NOT mean the adapter is unsafe. Nor does it
    necessarily mean the plugin fixture stopped being live — that was this
    docstring's claim, it was wrong, and it sent the first reader to check a
    fixture that was working (E71).

    **This is the slowest test in the file by an order of magnitude, and the
    only full run that omits `--pure`.** One machine, one invocation: 3.3-4.4 s
    for the `--pure` sibling above, 7.7-213 s here across eleven runs, plus one
    killed at the old 240 s ceiling. The gap is not the model call — both make
    one — but everything a non-`--pure` startup loads.

    So a failure has two shapes, told apart by the message rather than by
    inspection: a `_run` deadline (the run never finished) or a missing marker
    carrying the exit status and output (it finished and the plugin did not
    run). Only the second means the fixture died and the `--pure` test above
    proves nothing. The marker is written LATE — measured at 53.18 s of a
    55.22 s run, ~2 s before exit — so a killed run leaves no marker for
    reasons that say nothing about plugin loading.

    What keeps a real review out of this state is `NEUTRALIZE_DIRS`, asserted
    alongside so the two facts are read together.
    """
    info = require_harness(HARNESS)
    cwd = _hostile_cwd(tmp_path)
    status, lines = _run(info, _env(tmp_path), cwd, "run", "--format", "json", SAMPLE_PROMPT)
    if not (cwd / PLUGIN_MARKER).exists():
        strays = sorted(str(found) for found in tmp_path.rglob(PLUGIN_MARKER))
        pytest.fail(
            f"the SD 9.4 plugin left no marker in {cwd}.\n"
            f"opencode exited {status}; markers elsewhere under tmp: {strays or 'none'}.\n"
            f"last of {len(lines)} lines:\n" + "\n".join(lines[-40:])
        )
    assert ".opencode" in NEUTRALIZE_DIRS


# ---------------------------------------------------------------------------
# C-1023: the passthrough allowlist against the real flag vocabulary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flag", SD_DENIED_FLAGS)
def test_every_flag_the_design_names_is_refused_from_passthrough(require_harness, flag):
    """C-1023: refused by `DENIED_FLAGS` AND by the empty allowlist, so both are asserted.

    The allowlist alone refuses everything and also names the flag, so a bare
    `pytest.raises` here would pass against an empty `DENIED_FLAGS`.
    """
    require_harness(HARNESS)
    assert flag in DENIED_FLAGS
    with pytest.raises(ConfigError) as exc:
        police_passthrough(HARNESS, [flag], [])
    assert flag in str(exc.value)


def test_every_refused_flag_is_a_real_flag_on_the_live_binary(require_harness, tmp_path):
    """E3: a misspelled entry is a refusal that never fires — asked of the binary, not the recording."""
    info = require_harness(HARNESS)
    cwd = tmp_path / "help"
    cwd.mkdir()
    _, top = _run(info, _env(tmp_path), cwd, "--pure", "--help")
    _, run_help = _run(info, _env(tmp_path), cwd, "--pure", "run", "--help")
    vocabulary = "".join((*top, *run_help))
    unknown = [flag for flag in SD_DENIED_FLAGS if flag not in vocabulary]
    assert unknown == [], f"report these to WP6 rather than editing harness.py: {unknown}"


def test_the_committed_help_fixtures_still_match_the_live_flag_vocabulary(require_harness, tmp_path):
    """E3: the unit tier reads these fixtures, so a stale recording would silently weaken it."""
    info = require_harness(HARNESS)
    cwd = tmp_path / "help-drift"
    cwd.mkdir()
    _, run_help = _run(info, _env(tmp_path), cwd, "--pure", "run", "--help")
    recorded = (Path(__file__).resolve().parent / "fixtures" / HARNESS / "run-help-1.18.22.txt").read_text("utf-8")
    live = "".join(run_help)
    missing = [flag for flag in SD_DENIED_FLAGS if (flag in recorded) != (flag in live)]
    assert missing == [], f"re-record the fixture: {missing}"


# ---------------------------------------------------------------------------
# R9: the containment variable is actually read by the binary
# ---------------------------------------------------------------------------


def test_the_inline_config_variable_changes_the_resolved_agent_permissions(require_harness, tmp_path):
    """C-1007, R9: the mechanism is only a mechanism if the binary reads it.

    `agent list` prints each agent's resolved permissions, so the deny map is
    observable without spending a review. What is still NOT observed is the
    resolution ORDER against a project `opencode.json` — which is exactly why
    both axes stay `attested`.

    Counted rather than merely compared: the listing's `external_directory`
    rows arrive in a different order on every run, so an inequality alone would
    pass on ordering noise while the deny map was being ignored.
    """
    info = require_harness(HARNESS)
    cwd = tmp_path / "agents"
    cwd.mkdir()
    env = _env(tmp_path)
    _, plain = _run(info, env, cwd, "--pure", "agent", "list")
    _, denied = _run(info, {**env, CONFIG_ENV: deny_config(("read",))}, cwd, "--pure", "agent", "list")
    assert _denials(denied) > _denials(plain), (plain, denied)


def test_the_inline_config_is_read_even_beside_a_project_config_file(require_harness, tmp_path):
    """C-1032, R9: what IS observable about precedence, stated as exactly that and no more.

    A project `opencode.json` granting the tools this adapter denies does not
    suppress the inline value — the deny rules still appear in the resolved
    list. What is still NOT observable from `agent list` is which end of that
    list the resolver obeys, and that unobserved half is the whole reason both
    axes stay `attested` rather than `harness`.

    Under C-1005 the reviewed checkout carries no `opencode.json` at all
    (`NEUTRALIZE_FILES`), so this is the belt for a neutralization that
    under-matched, not the boundary.
    """
    info = require_harness(HARNESS)
    cwd = tmp_path / "project-config"
    cwd.mkdir()
    (cwd / "opencode.json").write_text('{"permission":{"bash":"allow","edit":"allow"}}', encoding="utf-8")
    env = _env(tmp_path)
    _, project_only = _run(info, env, cwd, "--pure", "agent", "list")
    _, both = _run(info, {**env, CONFIG_ENV: deny_config(("read",))}, cwd, "--pure", "agent", "list")
    assert _denials(both) > _denials(project_only), (project_only, both)


# ---------------------------------------------------------------------------
# C-1011: extraction over the real stream
# ---------------------------------------------------------------------------


def test_a_real_review_resolves_ok_through_the_bare_object_extraction(require_harness, tmp_path):
    """C-1011, E3: the recorded 1.18.22 answer was BARE, and this re-pins that on the live binary."""
    info = require_harness(HARNESS)
    cwd = tmp_path / "ok"
    cwd.mkdir()
    exit_code, lines = _run(info, _env(tmp_path), cwd, "--pure", "run", "--format", "json", SAMPLE_PROMPT)
    parsed = OpenCodeAdapter().parse(lines, exit_code, Heartbeat(Liveness.SEMANTIC, 0.0, 0.0))
    assert parsed.status == "ok"
    assert parsed.verdict == "approve"


def test_a_review_that_reads_a_file_first_still_resolves_ok(require_harness, tmp_path):
    """The gap the whole `* -> opencode` column of the live NxN matrix fell into.

    `SAMPLE_PROMPT` is answerable without touching a tool, so every recorded
    fixture and every green cell of this tier saw exactly ONE `text` part. A real
    review reads the tree first, and OpenCode emits one `text` part per step — a
    narration part, then the answer — which concatenated to prose-plus-object and
    failed both extractions. 29 passed / 0 skipped never saw it because nothing
    here made the model use a tool. This does.
    """
    info = require_harness(HARNESS)
    cwd = tmp_path / "review"
    cwd.mkdir()
    (cwd / "billing.py").write_text(
        "def average_charge(items):\n    return sum(item.amount for item in items) / len(items)\n",
        encoding="utf-8",
    )
    exit_code, lines = _run(
        info,
        _env(tmp_path),
        cwd,
        "--pure",
        "run",
        "--format",
        "json",
        "Read billing.py in this directory, then reply with a single JSON object and nothing else, in "
        'exactly this shape: {"verdict":"approve | needs-attention","summary":"string","findings":[],'
        '"next_steps":[]}',
    )
    parsed = OpenCodeAdapter().parse(lines, exit_code, Heartbeat(Liveness.SEMANTIC, 0.0, 0.0))
    assert [line for line in lines if '"type":"text"' in line], lines
    assert parsed.status == "ok", parsed.detail
    assert parsed.verdict is not None


def test_a_reply_that_is_not_the_wire_object_resolves_indeterminate(require_harness, tmp_path):
    """C-1011: neither extraction decodes, so the run resolves `indeterminate` and never `ok`."""
    info = require_harness(HARNESS)
    cwd = tmp_path / "prose"
    cwd.mkdir()
    exit_code, lines = _run(
        info,
        _env(tmp_path),
        cwd,
        "--pure",
        "run",
        "--format",
        "json",
        "Reply with exactly the word hello. Emit no JSON and no code fence.",
    )
    parsed = OpenCodeAdapter().parse(lines, exit_code, Heartbeat(Liveness.SEMANTIC, 0.0, 0.0))
    assert parsed.status == "indeterminate"
    assert parsed.verdict is None
    assert parsed.raw != ""


def test_a_live_review_stream_carries_at_least_one_semantic_event(require_harness, tmp_path):
    """C-1010: the silence window runs over events, so a stream of `False` lines is killed at 120s.

    `any`, not `all`, and named for it: the merged stream carries the launcher's
    own lines and the harness's stderr warnings, which are honestly `False`.
    What the window needs is that events arrive at all.
    """
    info = require_harness(HARNESS)
    cwd = tmp_path / "events"
    cwd.mkdir()
    _, lines = _run(info, _env(tmp_path), cwd, "--pure", "run", "--format", "json", SAMPLE_PROMPT)
    subject = OpenCodeAdapter()
    assert any(subject.on_line(line) for line in lines), lines


# ---------------------------------------------------------------------------
# WP5 carry-forward: what `WIRE_SCHEMA` actually is
# ---------------------------------------------------------------------------


def test_the_wire_schema_is_a_json_shaped_prose_template_not_a_schema(require_harness):
    """WP5 carry-forward, corrected: `json.loads(WIRE_SCHEMA)` DOES parse.

    The plan's carry-forward row expects it not to. It does — every value in the
    template is a syntactically valid JSON string, number or array. What it is
    not is a *schema*: the values are placeholders (`"approve | needs-attention"`),
    so nothing may validate a harness reply against it. This test asserts what is
    true, and the placeholder assertion is what stops a future reader mistaking a
    parsable template for a validator.
    """
    require_harness(HARNESS)
    template = json.loads(WIRE_SCHEMA)
    assert sorted(template) == ["findings", "next_steps", "summary", "verdict"]
    assert template["verdict"] not in {"approve", "needs-attention"}
