"""The launch gate, derived containment, the parse framework, the prompt route and the registry.

C-1003, C-1007, C-1008, C-1011, C-1012, C-1013, C-1014, C-1018, C-1019, C-1020,
C-1023, C-1024, C-1025, C-1028, C-1030, C-1035, C-1036, C-1042, C-1043, S-1010,
D-ac, D-f, E3, E9a.

Every containment assertion here is written so a *membership* implementation of
`derive_containment` fails it: the scattered run, the terminator, the last-wins
`key=` word and the repeated flag are four separate rules, and each has a case
whose argv carries every evidence word and is still not corroborated.
"""

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from types import MappingProxyType
from typing import Final, cast

import pytest

import nox.adapters as adapters_module
import nox.harness as harness_module
from nox.adapters import ADAPTERS, load
from nox.capability import REQUIRED, Capability, Enforcement, Launcher, ModelSpecT
from nox.config import NEVER_FORWARD, ConfigError, HarnessConfig
from nox.harness import (
    ASYMMETRY_CITATION,
    ASYMMETRY_MEASURED,
    ASYMMETRY_NEGATIVE,
    DENIED_FLAGS,
    NEVER_ALLOWLISTABLE,
    NEVER_EMITTED,
    NEVER_SET,
    PASSTHROUGH_ALLOW,
    PROBE_BUDGET_S,
    PROMPT_ARGV_LIMIT,
    PROMPT_FILENAME,
    SIGTERM_EXIT,
    Adapter,
    ContainmentPlan,
    HarnessUnavailable,
    Launch,
    ParsedOutput,
    ProbeCache,
    UnsupportedCapability,
    argv_prompt,
    asymmetry_warning,
    authorize,
    check_capabilities,
    config_read_paths,
    derive_containment,
    enforced_read_only,
    indeterminate,
    launch_argv,
    police_passthrough,
    probe_cwd,
    probe_digest,
    probe_harness,
    probe_run,
    reason_for_exit,
    resolve_executable,
    resolve_model,
    review_prompt,
    safe_finding_file,
    to_severity,
    version_warning,
)
from nox.liveness import Heartbeat, Liveness
from nox.outcome import FailureReason, Finding, Mechanism, Severity, Status, Verdict
from nox.prompt import WIRE_SCHEMA, Scope
from nox.runner import Invocation, SubprocessRunner
from nox.workspace import Workspace
from tests.unit.stubs import (
    ENV_EVIDENCE,
    MODELS,
    OS_EVIDENCE,
    STUBS,
    TOOL_EVIDENCE,
    AttestedStub,
    DisagreeingStub,
    FakeRunner,
    FifthStub,
    HarnessStub,
    HostileEnvStub,
    OmittingStub,
    OsStub,
    config,
    info_for,
)

# Resolved from this file, never from the cwd: the static scans are about the
# nox subtree whether pytest was invoked from the repo root or from nox/.
NOX = Path(__file__).resolve().parents[2]
SRC = NOX / "src" / "nox"
ADAPTERS_DIR = SRC / "adapters"

DIGEST = "digest-under-test"
"""The one digest every derivation test passes. `authorize` computes its own."""

ARG_MAX_TYPICAL = 2 << 20
"""A typical Linux `ARG_MAX`, for the one `PROMPT_ARGV_LIMIT` sanity assertion."""


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


def _repo_files():
    """Every file git accounts for under `nox/` — tracked, plus untracked and not ignored.

    The same listing `tests/unit/test_hygiene.py` scans, and for the same
    reason: a hand-rolled walk needs a prune list, and a virtualenv the list
    does not name drops the scan into site-packages.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=NOX,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [NOX / name for name in listed.split("\0") if name]


def _plan(
    *,
    mechanism: Mechanism = "tool-removal",
    write: Enforcement | None = "harness",
    network: Enforcement | None = "harness",
    argv_evidence: tuple[str, ...] = (),
    env_evidence: Mapping[str, str] | None = None,
) -> ContainmentPlan:
    return ContainmentPlan(
        mechanism=mechanism,
        write_enforcement=write,
        network_enforcement=network,
        argv_evidence=argv_evidence,
        env_evidence={} if env_evidence is None else env_evidence,
    )


def _inv(*argv, env=None):
    return Invocation(argv=tuple(argv), cwd=Path("/nonexistent-cwd"), env={} if env is None else env)


def _derived(inv, plan, *, cached=False):
    cache = ProbeCache()
    if cached:
        cache.record(DIGEST)
    return derive_containment(inv, plan, DIGEST, cache)


def _executable(directory: Path, name: str, content: bytes = b"#!/bin/sh\nexit 0\n") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    path.chmod(0o755)
    return path


def _workspace(
    tmp_path: Path,
    *,
    env=None,
    scope: Scope = "code-diff",
    neutralized=(),
    filtered=(),
    filtered_changed=(),
    omitted=(),
    omitted_ignored=0,
) -> Workspace:
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
        neutralized=neutralized,
        filtered=filtered,
        filtered_changed=filtered_changed,
        omitted=omitted,
        omitted_ignored=omitted_ignored,
        scope=scope,
        neutralized_total=len(neutralized),
        filtered_total=len(filtered),
        filtered_changed_total=len(filtered_changed),
        omitted_total=len(omitted),
    )


def _parsed(
    *,
    status: Status = "ok",
    verdict: Verdict | None = "approve",
    findings: tuple[Finding, ...] = (),
    summary: str = "",
    detail: str | None = None,
    raw: str = "",
    reason: FailureReason | None = None,
) -> ParsedOutput:
    return ParsedOutput(
        status=status,
        verdict=verdict,
        findings=findings,
        summary=summary,
        detail=detail,
        raw=raw,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# The launch gate: C-1007, C-1013
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("write", "network", "named"),
    [(None, "harness", "write"), ("harness", None, "network")],
    ids=["write-axis", "network-axis"],
)
def test_a_none_enforcement_axis_refuses_the_launch_naming_the_axis(write, network, named):
    """C-1007: `None` is not a weaker level standing in, and the operator needs the axis, not the refusal."""
    plan = _plan(write=write, network=network, argv_evidence=TOOL_EVIDENCE)
    with pytest.raises(UnsupportedCapability) as exc:
        check_capabilities(info_for("stub"), plan)
    assert named in str(exc.value).lower()


@pytest.mark.parametrize("missing", sorted(REQUIRED))
def test_a_missing_required_capability_refuses_the_launch(missing):
    """C-1013: absence is the default and there is no permissive fallback to omit into."""
    info = info_for("stub", capabilities=frozenset(Capability) - {missing})
    with pytest.raises(UnsupportedCapability) as exc:
        check_capabilities(info, _plan(argv_evidence=TOOL_EVIDENCE))
    assert missing.value in str(exc.value)


def test_an_opencode_shaped_harness_launches_without_enforced_read_only():
    """C-1013: `REQUIRED` does not carry `ENFORCED_READ_ONLY`; the run is stamped, not refused."""
    adapter = AttestedStub()
    info = adapter.probe(FakeRunner(), config(), {}, Path("/nonexistent-cwd"))
    check_capabilities(info, _plan(mechanism="config-deny", write="attested", network="attested"))
    assert enforced_read_only(info) is False


def test_a_harness_with_the_capability_is_stamped_read_only():
    """C-1013: the capability→stamp mapping is read off `info.capabilities`, never hand-set."""
    info = info_for("stub", capabilities=frozenset({Capability.ENUMERABLE_DENY, Capability.ENFORCED_READ_ONLY}))
    assert enforced_read_only(info) is True


def test_the_strenum_hazard_is_real_and_a_raw_string_capability_is_refused():
    """C-1013: `Capability` is a `StrEnum`, so the subset check alone cannot be the gate.

    The first assertion is the hazard, verified in this Python rather than
    described: a set of bare strings satisfies `REQUIRED <= …` while declaring
    nothing. `HarnessInfo.__post_init__` is the single choke point that stops it.
    """
    assert REQUIRED <= {"enumerable_deny"}
    with pytest.raises(ValueError):
        info_for("stub", capabilities=cast("frozenset[Capability]", frozenset({"enumerable_deny"})))


def test_a_parsed_capability_set_is_accepted():
    """C-1013: the guard refuses raw strings only — real members pass through untouched."""
    info = info_for("stub", capabilities=frozenset({Capability.ENUMERABLE_DENY}))
    assert info.capabilities == frozenset({Capability.ENUMERABLE_DENY})


# ---------------------------------------------------------------------------
# Passthrough policing: C-1023, S-1010
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flag", sorted(DENIED_FLAGS))
def test_every_denied_flag_is_refused_bare(flag):
    """C-1023 refusal 1: the whole shipped set, not a hand-picked sample."""
    with pytest.raises(ConfigError) as exc:
        police_passthrough("codex", [flag], [])
    assert flag in str(exc.value)


@pytest.mark.parametrize("flag", sorted(DENIED_FLAGS))
def test_every_denied_flag_is_refused_equals_joined(flag):
    """C-1023 refusal 1: matched on the token before `=`, so `--flag=value` cannot slip past."""
    with pytest.raises(ConfigError) as exc:
        police_passthrough("codex", [f"{flag}=value"], [])
    assert flag in str(exc.value)


def test_an_element_outside_the_allowlist_is_refused_by_name():
    """C-1023 refusal 2: permission, not exclusion — anything absent is refused."""
    with pytest.raises(ConfigError) as exc:
        police_passthrough("claude", ["--verbose"], [])
    assert "--verbose" in str(exc.value)


PERMITTED = "--color"
"""The flag the fixture below grants, for the accept paths no shipped set reaches.

Codex's own, documented on `codex exec` — the command nox actually spawns — and
containment-inert, so these tests drive the policing with a real flag rather
than an invented one. It is deliberately not *shipped* as permitted: what is
under test is `police_passthrough`, not which flags a harness happens to allow.
"""


@pytest.fixture
def permits(monkeypatch):
    """Grant one harness a synthetic `PASSTHROUGH_ALLOW` entry for the duration of a test.

    Every shipped set is empty. Codex's `--title` was the last entry and it was
    *dead* — documented on `codex exec review` and not on the `codex exec` nox
    spawns, so the one word a repository could pass through answered
    `error: unexpected argument` out of the binary. Emptying it left
    `police_passthrough`'s two accept paths — an allowlisted flag, and the value
    that rides with it — with no live example, and a gate is not something to
    keep a dead entry alive to exercise.
    """

    def _permit(harness: str, *flags: str) -> None:
        monkeypatch.setattr(
            harness_module,
            "PASSTHROUGH_ALLOW",
            MappingProxyType({**PASSTHROUGH_ALLOW, harness: frozenset(flags)}),
        )

    return _permit


def test_a_bare_positional_not_following_an_allowed_flag_is_refused(permits):
    """C-1023 refusal 3: `opencode run [message..]` takes its prompt as a positional."""
    permits("codex", PERMITTED)
    with pytest.raises(ConfigError) as exc:
        police_passthrough("codex", [PERMITTED, "never", "review-this"], [])
    assert "review-this" in str(exc.value)


def test_an_allowed_flag_and_its_value_are_accepted(permits):
    """C-1023: an allowlisted flag survives the gate, and its value rides with it."""
    permits("codex", PERMITTED)
    assert police_passthrough("codex", [PERMITTED, "never"], []) == (PERMITTED, "never")


def test_the_same_flag_is_refused_for_a_harness_that_does_not_allow_it(permits):
    """C-1023: the allowlist is per-adapter, so a permission is never a global one."""
    permits("codex", PERMITTED)
    with pytest.raises(ConfigError) as exc:
        police_passthrough("claude", [PERMITTED, "never"], [])
    assert str(exc.value) == f"passthrough: {PERMITTED} is not allowed for claude (C-1023)"


def test_a_duplicate_of_a_nox_owned_flag_is_refused(permits):
    """C-1023 refusal 4: a passthrough copy of a flag nox emits is refused, never duplicated.

    Behind `permits` because refusal 2 answers first for anything the allowlist
    does not carry, so without a permission this asserts the wrong branch.
    """
    permits("codex", PERMITTED)
    with pytest.raises(ConfigError) as exc:
        police_passthrough("codex", [PERMITTED, "theirs"], [PERMITTED, "ours"])
    # The refusal's OWN words: refusal 2's message also carries the flag, so a
    # `permits` that stopped taking would pass this on the wrong branch.
    assert str(exc.value) == f"passthrough: {PERMITTED} duplicates a flag nox emits for this launch (C-1023)"


def test_passthrough_comes_first_and_nox_flags_last(permits):
    """C-1023: a last-wins harness must resolve nox's containment flags, not the repository's."""
    permits("codex", PERMITTED)
    result = police_passthrough("codex", [PERMITTED, "never"], ["-c", "sandbox_mode=read-only"])
    assert result == (PERMITTED, "never", "-c", "sandbox_mode=read-only")


def test_a_key_with_no_allowlist_entry_refuses_every_word_and_composes_nox_own_flags():
    """C-1023, H12: an absent entry is an EMPTY allowlist — "refuse everything", never "refuse the review".

    This asserted a `ConfigError` for an unlisted key, which is what made
    `Adapter`'s "a fifth adapter needs no core edit" false: every `prepare`
    calls this unconditionally, so an adapter without a `PASSTHROUGH_ALLOW` key
    hard-failed every review rather than passing nothing through. The unknown-key
    refusal belongs to `adapters.load`, which owns the registry — and which
    `test_an_unregistered_key_is_unsupported_without_echoing_it` pins for the
    C-1035(1) half, because `[review] harness` is repository-supplied there and
    an adapter's own `name` is not.
    """
    unlisted = "harness-with-no-entry"
    assert police_passthrough(unlisted, [], ["-c", "sandbox_mode=read-only"]) == ("-c", "sandbox_mode=read-only")
    with pytest.raises(ConfigError) as exc:
        police_passthrough(unlisted, ["--verbose=yes"], [])
    # The refusal's OWN words, on the `--flag=value` spelling. `"--verbose" in`
    # matched refusal 5's "expects a value" too, so a default of
    # `frozenset({"--verbose"})` — a permissive allowlist for every unregistered
    # harness — passed this by taking the other branch with the flag still named.
    assert str(exc.value) == f"passthrough: --verbose is not allowed for {unlisted} (C-1023)"


def test_the_codex_sandbox_escape_hatch_is_refused_from_passthrough():
    """S-1010: `-c sandbox_mode=danger-full-access` is the exact element the allowlist exists for."""
    with pytest.raises(ConfigError) as exc:
        police_passthrough("codex", ["-c", "sandbox_mode=danger-full-access"], [])
    assert "-c" in str(exc.value)


@pytest.mark.parametrize("harness", sorted(PASSTHROUGH_ALLOW))
def test_the_allowlist_never_carries_a_value_carrying_config_flag(harness):
    """C-1023: one allowlisted `--settings '{"hooks":…}'` is command execution surviving the flag stack."""
    assert PASSTHROUGH_ALLOW[harness].isdisjoint(NEVER_ALLOWLISTABLE)


@pytest.mark.parametrize("harness", sorted(PASSTHROUGH_ALLOW))
def test_the_allowlist_never_carries_a_denied_flag(harness):
    """C-1023: an allowlist entry that is also refused would make the two rules contradict."""
    assert PASSTHROUGH_ALLOW[harness].isdisjoint(DENIED_FLAGS)


@pytest.mark.parametrize("harness", sorted(PASSTHROUGH_ALLOW))
def test_every_shipped_allowlist_is_empty_and_the_absent_key_default_is_too(harness):
    """C-1023: "four empty sets" is a claim three docstrings rest on, and nothing ran it.

    `PASSTHROUGH_ALLOW`'s own docstring calls four empty sets the honest state;
    `police_passthrough`'s says refusals 2-5 are unreachable while that holds;
    the `permits` fixture and the `--help` audit both say every shipped set is
    empty and build their own reasoning on it — the audit passes *vacuously*
    because of it. Granting `codex` one containment-inert real flag
    (`frozenset({"--color"})`) left this whole file green: the disjointness
    tests do not fire on an inert flag, and the `--help` audit confirms it is a
    real option rather than refusing it. So a repository's `nox.toml`
    `passthrough` word reached the harness argv with nothing asserting the gate
    was still shut.

    The second assertion is the same gap on the OTHER literal — the empty
    default `police_passthrough` reads an absent key with. `test_a_key_with_no_
    allowlist_entry_refuses_every_word_and_composes_nox_own_flags` pins that a
    fifth adapter passes nothing through, but only for `--verbose`: a default of
    `frozenset({"--color"})` also survived the file. `PERMITTED` is the one flag
    anyone widening this would reach for, so refusing it for a key with no entry
    is what makes "an incomplete adapter is safe rather than permissive"
    executed rather than written. Neither assertion is a ceiling on what may
    ever be allowlisted — it is a requirement that granting anything comes with
    an edit here.
    """
    assert PASSTHROUGH_ALLOW[harness] == frozenset()
    with pytest.raises(ConfigError) as exc:
        police_passthrough("harness-with-no-entry", [PERMITTED, "never"], [])
    assert str(exc.value) == f"passthrough: {PERMITTED} is not allowed for harness-with-no-entry (C-1023)"


def test_every_never_emitted_flag_is_also_denied_from_passthrough():
    """C-1023: `NEVER_EMITTED` is the emission half of `DENIED_FLAGS`, never a wider set."""
    assert NEVER_EMITTED <= DENIED_FLAGS


def test_the_allowlist_never_carries_a_key_the_registry_does_not():
    """C-1023, C-1024, H12: a subset, deliberately — the missing direction is the extension point.

    Equality was the assertion here, and it made `Adapter`'s "adding one is four
    steps with no core change" false in a test: a fifth adapter had to be given a
    `PASSTHROUGH_ALLOW` entry to keep the suite green, and the entry it would be
    given is the empty set an absent key now means. The other direction still
    matters — an allowlist key naming no registered harness is a permission
    granted to nothing, which is either a typo or a deletion half-done.
    """
    assert set(PASSTHROUGH_ALLOW) <= set(ADAPTERS)


# The refusal sets, audited against the committed `--help` fixtures — E3, C-1023

HELP_FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures"
"""Where each adapter commits the `--help` its refusal set is pinned against (E3)."""

ALIAS = re.compile(r"^\s+(-[A-Za-z0-9]), (--[A-Za-z0-9][A-Za-z0-9-]*)", re.MULTILINE)
"""`-r, --resume` — the shape every one of these CLIs documents a short alias in."""


def _help_pages():
    """Every committed `--help` fixture, as `(harness, text)`."""
    return sorted((path.parent.name, path.read_text(encoding="utf-8")) for path in HELP_FIXTURES.glob("*/help-*.txt"))


def test_at_least_one_help_fixture_is_committed():
    """E3: the two audits below are parametrized off this glob, and an empty one passes silently."""
    assert _help_pages(), f"no `--help` fixture under {HELP_FIXTURES}"


SPAWNED_HELP: Final[Mapping[str, str]] = MappingProxyType(
    {"claude": "help-", "codex": "help-", "copilot": "help-", "opencode": "run-help-"}
)
"""Per harness, the fixture prefix of the `--help` for the command nox actually spawns.

A map and not a glob, because the answer is per adapter and getting it wrong
reproduces the very bug the audit below exists to catch. opencode spawns
`opencode run`, whose page is `run-help-<version>.txt`; the top-level
`help-<version>.txt` documents `--mini`, `--prompt`, `--no-replay`, `--cors`
and `--hostname`, none of which `opencode run` accepts — and omits `--title`,
which it does. A glob that picked the top-level page would wave those five
through and reject the one real flag. Codex spawns bare `codex exec`, whose
page is `help-<version>.txt`; `help-review-<version>.txt` is the sibling
subcommand's and is deliberately not consulted (E21).
"""

OPTION_LINE = "(?m)^[ \\t]+(?:[-\\w]+,[ \\t]*)*{flag}(?![\\w-])"
"""A flag as its own entry in an Options block, not as a substring anywhere on the page.

Every one of these CLIs indents an option entry and lists any alias ahead of it
(`-c, --config`, `--allowedTools, --allowed-tools`). Matching the bare string
instead would pass `--out` off `--output-schema`, and `--last` off the sentence
"pick the most recent with --last" in codex's `resume` description.
"""


def _spawned_help_pages():
    """The `--help` of the command nox spawns, per harness, as `(harness, text)`."""
    pages = []
    for harness, prefix in SPAWNED_HELP.items():
        found = sorted(HELP_FIXTURES.glob(f"{harness}/{prefix}[0-9]*.txt"))
        assert len(found) == 1, f"{harness}: expected one {prefix}<version>.txt, found {found}"
        pages.append((harness, found[0].read_text(encoding="utf-8")))
    return sorted(pages)


def test_every_registered_harness_commits_the_help_of_the_command_nox_spawns():
    """The guard on the audit below: a harness with no page is not audited, and would pass silently."""
    assert set(SPAWNED_HELP) == set(ADAPTERS)
    assert {harness for harness, _ in _spawned_help_pages()} == set(ADAPTERS)


@pytest.mark.parametrize(("harness", "help_text"), _spawned_help_pages(), ids=lambda v: v if len(v) < 20 else "")
def test_every_allowlisted_passthrough_flag_is_a_real_flag_on_the_command_nox_spawns(harness, help_text):
    """C-1023: an allowlist entry naming a flag the binary has not is a clap error where a nox refusal belongs.

    `police_passthrough` appends the repository's word to an argv whose
    subcommand the adapter fixed, so a flag that exists only on a *different*
    subcommand is unreachable: `codex exec --title x` answers
    `error: unexpected argument '--title' found`, exit 2, out of the binary —
    past nox's gate, with none of nox's diagnosis. `--title` was codex's only
    allowlisted passthrough, so the single word a user could pass through was
    the one that could not work.

    The third instance of one class: a flag or variable name shipped in a
    security-relevant literal without being checked against the binary's own
    `--help` (`--resume`/`-r` on copilot, `OPENCODE_AUTH_JSON` in E19). This is
    the audit for the allowlist half — the sets above audit the refusal half.
    """
    absent = sorted(
        flag
        for flag in PASSTHROUGH_ALLOW.get(harness, frozenset())
        if not re.search(OPTION_LINE.format(flag=re.escape(flag)), help_text)
    )
    assert absent == []


@pytest.mark.parametrize(
    ("harness", "flag", "documented"),
    [
        ("codex", "--color", True),
        ("codex", "--title", False),
        ("codex", "--out", False),
        ("codex", "--last", False),
        ("opencode", "--title", True),
        ("opencode", "--mini", False),
    ],
    ids=["codex-real", "codex-review-only", "codex-substring", "codex-mentioned", "opencode-run", "opencode-top"],
)
def test_the_audit_above_can_tell_a_real_option_from_a_substring_or_a_mention(harness, flag, documented):
    """The guard on the audit: every shipped set is empty, so it passes vacuously and could be broken silently.

    Each case is one way the audit was, or could be, wrong. `--title` is the
    finding itself — real on `opencode run`, real on `codex exec review`, absent
    from `codex exec`. `--out` is a prefix of codex's `--output-schema`;
    `--last` appears on that page only inside the `resume` subcommand's prose;
    `--mini` is on `opencode --help` and not on `opencode run`, which is what a
    filename glob over the fixtures got wrong.
    """
    pages = dict(_spawned_help_pages())
    assert bool(re.search(OPTION_LINE.format(flag=re.escape(flag)), pages[harness])) is documented


@pytest.mark.parametrize("refused", [DENIED_FLAGS, NEVER_EMITTED], ids=["denied", "never-emitted"])
@pytest.mark.parametrize(("harness", "help_text"), _help_pages(), ids=lambda value: value if len(value) < 20 else "")
def test_a_short_alias_of_a_refused_long_flag_is_itself_refused(harness, help_text, refused):
    """C-1023: a denied capability reachable under a second spelling is the same hole, renamed.

    The general shape of the bug this suite was extended for: `--resume` was
    refused and `-r`, which `copilot --help` documents as the same option, was
    not. Read off the fixture rather than restated here, so a fifth adapter
    committing its own `--help` is audited by the same test with no edit.
    """
    del harness
    gaps = [(short, long) for short, long in ALIAS.findall(help_text) if long in refused and short not in refused]
    assert gaps == []


def test_the_copilot_permission_lifts_and_the_cwd_bypass_are_never_emitted():
    """C-1023, C-1003: `--help` for 1.0.82 documents each of these, and the set once carried none.

    `--allow-all` and `--yolo` are that page's own aliases for the three
    `--allow-all-*` flags, so refusing those three without these refused
    nothing. `-C` is the different and worse one: it is not a permission lift
    but a working-directory bypass, so the harness would review outside the
    C-1003 ephemeral worktree while `Invocation.cwd` still reads `ws.path`.
    """
    assert {
        # Permission and network lifts.
        "--allow-all",
        "--yolo",
        "--allow-all-urls",
        "--allow-all-mcp-server-instructions",
        "--allow-url",
        # Code and configuration the harness loads and then runs.
        "--additional-mcp-config",
        "--plugin-dir",
        "--extension-sdk-path",
        "--bash-env",
        "--agent",
        "--enable-mcp-server",
        "--enable-all-github-mcp-tools",
        "--add-github-mcp-tool",
        "--add-github-mcp-toolset",
        # Session egress and inbound control — the session IS the diff.
        "--share",
        "--share-gist",
        "--remote",
        "--remote-export",
        "--connect",
        # The working-directory bypass.
        "-C",
        # yargs' negation of OpenCode's whole `argv_evidence`, which derivation
        # cannot see: a negation re-specifies nothing, so rule 4 never fires.
        "--no-pure",
    } <= NEVER_EMITTED


@pytest.mark.parametrize("word", ["-C/tmp/elsewhere", "-Csandbox"])
def test_a_short_never_emitted_flag_is_refused_with_its_value_attached(word, tmp_path):
    """C-1023: every v1 harness parses `-Cvalue` as `-C value`, so the split-on-`=` check misses it."""
    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, HarnessStub(), launch=Launch(argv=("-p", *TOOL_EVIDENCE, word)))
    assert word in str(exc.value)


def test_a_short_denied_flag_is_refused_from_passthrough_with_its_value_attached():
    """C-1023 refusal 1: `-c sandbox_mode=X` and `-csandbox_mode=X` are one option to clap."""
    with pytest.raises(ConfigError) as exc:
        police_passthrough("codex", ["-csandbox_mode=danger-full-access"], [])
    # The refusal KIND, not just the flag: refusal 2 ("not allowed for codex")
    # already caught this word by name, so a test that only looked for `-c`
    # passed against the set-membership implementation this replaced.
    assert "-c is refused unconditionally" in str(exc.value)


# ---------------------------------------------------------------------------
# Containment derivation: C-1025
# ---------------------------------------------------------------------------


def test_a_contiguous_terminated_unique_run_corroborates_both_axes():
    """C-1025: the positive control every refusal below is measured against."""
    inv = _inv("claude", "-p", *TOOL_EVIDENCE)
    derived = _derived(inv, _plan(argv_evidence=TOOL_EVIDENCE))
    assert (derived.write_enforcement, derived.network_enforcement) == ("harness", "harness")


def test_scattered_evidence_words_do_not_corroborate():
    """C-1025 rule 1: the run is a claim about the whole tool list, not a set of members."""
    inv = _inv("claude", "--tools", "Read", "--verbose", "Grep", "Glob")
    derived = _derived(inv, _plan(argv_evidence=TOOL_EVIDENCE))
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_a_reordered_run_does_not_corroborate():
    """C-1025 rule 1: in order, not merely contiguous."""
    inv = _inv("claude", "--tools", "Glob", "Grep", "Read")
    derived = _derived(inv, _plan(argv_evidence=TOOL_EVIDENCE))
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_a_word_appended_after_the_run_does_not_corroborate():
    """C-1025 rule 2: `--tools Read Grep Glob Bash` restores writes and network reach."""
    inv = _inv("claude", "-p", *TOOL_EVIDENCE, "Bash")
    derived = _derived(inv, _plan(argv_evidence=TOOL_EVIDENCE))
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_a_flag_after_the_run_is_a_valid_terminator():
    """C-1025 rule 2: the terminator is "absent or starts with `-`", not "absent"."""
    inv = _inv("claude", "-p", *TOOL_EVIDENCE, "--model", "some-model")
    derived = _derived(inv, _plan(argv_evidence=TOOL_EVIDENCE))
    assert (derived.write_enforcement, derived.network_enforcement) == ("harness", "harness")


def test_a_later_word_sharing_a_key_prefix_does_not_corroborate():
    """C-1025 rule 3: Codex resolves the LAST `-c sandbox_mode=…`, with every evidence word present."""
    inv = _inv("codex", "-c", *OS_EVIDENCE, "-c", "sandbox_mode=danger-full-access")
    plan = _plan(mechanism="os-sandbox", write="os", network="os", argv_evidence=OS_EVIDENCE)
    derived = _derived(inv, plan, cached=True)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_a_second_occurrence_of_a_run_flag_does_not_corroborate():
    """C-1025 rule 4: a second `--tools Bash` follows the first and wins."""
    inv = _inv("claude", "--tools", "Read", "Grep", "Glob", "--model", "m", "--tools", "Bash")
    derived = _derived(inv, _plan(argv_evidence=TOOL_EVIDENCE))
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_environment_evidence_is_matched_by_value():
    """C-1025: `STUB_CONFIG_CONTENT="{}"` is present under a names-only check while denying nothing."""
    inv = _inv("opencode", "run", env={"STUB_CONFIG_CONTENT": "{}"})
    plan = _plan(mechanism="config-deny", write="attested", network="attested", env_evidence=ENV_EVIDENCE)
    derived = _derived(inv, plan)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_the_exact_environment_value_corroborates():
    """C-1025: the same key with the declared value is the positive control for the value check."""
    inv = _inv("opencode", "run", env=dict(ENV_EVIDENCE))
    plan = _plan(mechanism="config-deny", write="attested", network="attested", env_evidence=ENV_EVIDENCE)
    derived = _derived(inv, plan)
    assert (derived.write_enforcement, derived.network_enforcement) == ("attested", "attested")


def test_a_config_deny_plan_is_not_corroborated_by_argv_alone():
    """C-1025: the mechanism must be corroborated by the kind of evidence it names."""
    inv = _inv("opencode", "run", "--deny-writes")
    plan = _plan(mechanism="config-deny", write="attested", network="attested", argv_evidence=("--deny-writes",))
    derived = _derived(inv, plan)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_a_tool_removal_plan_is_not_corroborated_by_environment_alone():
    """C-1025: `tool-removal` requires a non-empty `argv_evidence`."""
    inv = _inv("claude", "-p", env=dict(ENV_EVIDENCE))
    plan = _plan(mechanism="tool-removal", env_evidence=ENV_EVIDENCE)
    derived = _derived(inv, plan)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_an_os_sandbox_plan_without_argv_evidence_is_not_corroborated():
    """C-1025: `os-sandbox` requires a non-empty `argv_evidence` AND the cached probe."""
    inv = _inv("codex", "exec", env=dict(ENV_EVIDENCE))
    plan = _plan(mechanism="os-sandbox", write="os", network="os", env_evidence=ENV_EVIDENCE)
    derived = _derived(inv, plan, cached=True)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_an_os_axis_without_a_cached_probe_is_not_corroborated():
    """C-1025: `-c sandbox_mode=read-only` is a request; C-1040's probe is what settles it."""
    inv = _inv("codex", "exec", "-c", *OS_EVIDENCE)
    plan = _plan(mechanism="os-sandbox", write="os", network="os", argv_evidence=OS_EVIDENCE)
    derived = _derived(inv, plan, cached=False)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_an_os_axis_with_a_cached_probe_survives():
    """C-1025: the cached pass under exactly this digest is what promotes the axis."""
    inv = _inv("codex", "exec", "-c", *OS_EVIDENCE)
    plan = _plan(mechanism="os-sandbox", write="os", network="os", argv_evidence=OS_EVIDENCE)
    derived = _derived(inv, plan, cached=True)
    assert (derived.write_enforcement, derived.network_enforcement) == ("os", "os")


def test_the_cached_probe_requirement_is_per_axis():
    """C-1025: only an axis whose claimed level is `os` needs the probe."""
    inv = _inv("claude", "-p", *TOOL_EVIDENCE)
    plan = _plan(mechanism="tool-removal", write="os", network="harness", argv_evidence=TOOL_EVIDENCE)
    derived = _derived(inv, plan, cached=False)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, "harness")


@pytest.mark.parametrize("mechanism", ["tool-removal", "os-sandbox", "config-deny"])
def test_an_empty_evidence_set_corroborates_nothing(mechanism):
    """C-1025: an adapter that names no evidence has stated a claim and nothing else."""
    inv = _inv("claude", "-p", "--tools", "Read")
    derived = _derived(inv, _plan(mechanism=mechanism), cached=True)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_a_disagreeing_adapter_is_downgraded_on_both_axes(tmp_path):
    """C-1025: the stub whose plan says one thing and whose argv says another."""
    adapter = DisagreeingStub()
    info = info_for(adapter.name)
    plan = adapter.containment_plan(config(), info)
    launch = adapter.prepare(_workspace(tmp_path), info, config(), None)
    derived = _derived(_inv(adapter.BINARY, *launch.argv), plan)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_the_containment_plan_models_no_process_lifetime_axis():
    """D-ac: a constant third axis would read as derived evidence under C-1025 and carry none."""
    assert {f.name for f in fields(ContainmentPlan)} == {
        "mechanism",
        "write_enforcement",
        "network_enforcement",
        "argv_evidence",
        "env_evidence",
    }


# ---------------------------------------------------------------------------
# The probe digest and its cache: C-1025
# ---------------------------------------------------------------------------


def _digest_kwargs(tmp_path: Path):
    exe = _executable(tmp_path / "bin", "h-bin")
    cfg_file = tmp_path / "cfg" / "config.toml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_bytes(b"model = 'a'\n")
    return {
        "plan": _plan(argv_evidence=TOOL_EVIDENCE),
        "executable": str(exe),
        "launcher": Launcher(binary="h-bin"),
        "env": {"PATH": str(tmp_path / "bin"), "HOME": str(tmp_path)},
        "config_reads": (cfg_file,),
    }


def _other_executable_path(kwargs, tmp_path):
    return {**kwargs, "executable": str(_executable(tmp_path / "bin2", "h-bin"))}


def _other_executable_bytes(kwargs, tmp_path):
    del tmp_path
    Path(kwargs["executable"]).write_bytes(b"#!/bin/sh\nexit 1\n")
    return kwargs


def _other_launcher_prefix(kwargs, tmp_path):
    del tmp_path
    return {**kwargs, "launcher": Launcher(binary="h-bin", prefix=("wrapper", "--"))}


def _other_argv_evidence(kwargs, tmp_path):
    del tmp_path
    return {**kwargs, "plan": _plan(argv_evidence=("--tools", "Read"))}


def _other_env_evidence(kwargs, tmp_path):
    del tmp_path
    return {**kwargs, "plan": _plan(argv_evidence=TOOL_EVIDENCE, env_evidence={"STUB_CONFIG_CONTENT": "{}"})}


def _other_env(kwargs, tmp_path):
    del tmp_path
    return {**kwargs, "env": {**kwargs["env"], "CODEX_HOME": "/somewhere"}}


def _other_config_read_bytes(kwargs, tmp_path):
    del tmp_path
    kwargs["config_reads"][0].write_bytes(b"model = 'b'\n")
    return kwargs


@pytest.mark.parametrize(
    "mutate",
    [
        _other_executable_path,
        _other_executable_bytes,
        _other_launcher_prefix,
        _other_argv_evidence,
        _other_env_evidence,
        _other_env,
        _other_config_read_bytes,
    ],
    ids=[
        "executable-path",
        "executable-bytes",
        "launcher-prefix",
        "argv-evidence",
        "env-evidence",
        "environment",
        "config-read-bytes",
    ],
)
def test_the_probe_digest_changes_when_any_factor_changes(tmp_path, mutate):
    """C-1025: every factor a passing sandbox probe depends on is a cache MISS, not a stale pass."""
    kwargs = _digest_kwargs(tmp_path)
    before = probe_digest(**kwargs)
    after = probe_digest(**mutate(kwargs, tmp_path))
    assert before != after


def test_the_probe_digest_is_stable_when_nothing_changes(tmp_path):
    """C-1025: the digest before a probe and the digest at derivation are identical by construction."""
    kwargs = _digest_kwargs(tmp_path)
    assert probe_digest(**kwargs) == probe_digest(**kwargs)


def test_an_absent_config_read_hashes_stably_and_creating_it_is_a_miss(tmp_path):
    """C-1025: a declared file that does not exist hashes as a distinct absent-marker."""
    kwargs = _digest_kwargs(tmp_path)
    absent = tmp_path / "cfg" / "not-there.toml"
    kwargs["config_reads"] = (absent,)
    first = probe_digest(**kwargs)
    assert probe_digest(**kwargs) == first
    absent.write_bytes(b"")
    assert probe_digest(**kwargs) != first


def test_config_read_paths_expands_against_the_passed_environment_in_order():
    """C-1025: the precedence an adapter states is the order the digest hashes."""
    env = {"CODEX_HOME": "/opt/codex", "HOME": "/home/u"}
    result = config_read_paths(("${CODEX_HOME}/config.toml", "${HOME}/.codex/config.toml"), env)
    assert result == (Path("/opt/codex/config.toml"), Path("/home/u/.codex/config.toml"))


def test_config_read_paths_drops_an_entry_naming_an_absent_variable():
    """C-1025: it names a file that cannot exist on this run, and the drop is itself a digest factor."""
    env = {"HOME": "/home/u"}
    assert config_read_paths(("${CODEX_HOME}/config.toml", "${HOME}/.codex/config.toml"), env) == (
        Path("/home/u/.codex/config.toml"),
    )


@pytest.mark.parametrize("entry", ["relative/config.toml", "${HOME}/../elsewhere/config.toml"])
def test_config_read_paths_refuses_a_relative_or_dotdot_expansion(entry):
    """C-1025: a digest over a path that walks out of the config root proves nothing about what was read."""
    with pytest.raises(ValueError):
        config_read_paths((entry,), {"HOME": "/home/u"})


def test_an_empty_probe_cache_is_not_passing():
    """C-1025: the failure direction is a refused `os` claim rather than an unproven one."""
    assert ProbeCache().passing(DIGEST) is False


def test_a_probe_cache_passes_only_on_an_exact_digest():
    """C-1025: anything but an exact match is `False`."""
    cache = ProbeCache()
    cache.record(DIGEST)
    assert cache.passing(DIGEST) is True
    assert cache.passing(DIGEST + "x") is False


# ---------------------------------------------------------------------------
# `authorize`: the gate that cannot be skipped — C-1003, C-1007, C-1008, C-1025
# ---------------------------------------------------------------------------


def _authorized(tmp_path, adapter, *, launcher=None, launch=None, cache=None, ws=None, runner=None):
    bindir = tmp_path / "bin"
    _executable(bindir, adapter.BINARY)
    info = adapter.probe(FakeRunner(), config(), {}, tmp_path)
    if launcher is not None:
        info = info_for(adapter.name, capabilities=info.capabilities, launcher=launcher)
    workspace = _workspace(tmp_path, env={"PATH": str(bindir), "HOME": str(tmp_path)}) if ws is None else ws
    plan = adapter.containment_plan(config(), info)
    prepared = adapter.prepare(workspace, info, config(), None) if launch is None else launch
    spawner = FakeRunner() if runner is None else runner
    return authorize(adapter, prepared, workspace, info, plan, ProbeCache() if cache is None else cache, spawner)


def test_the_invocation_cwd_is_the_workspace(tmp_path):
    """C-1003: `cwd` is the ephemeral worktree by construction, not by an adapter remembering."""
    adapter = HarnessStub()
    ws = _workspace(tmp_path, env={"PATH": str(tmp_path / "bin")})
    inv, _ = _authorized(tmp_path, adapter, ws=ws)
    assert inv.cwd == ws.path


def test_a_launch_cannot_name_a_cwd():
    """C-1003: an adapter returns a `Launch`, which can express neither `cwd` nor a whole environment.

    `stdin_path` is the one path a `Launch` may name, and it is not an exception
    to that: `authorize` refuses any value outside `Workspace.scratch`, so it
    chooses a CHANNEL rather than a location (E29).
    """
    assert {f.name for f in fields(Launch)} == {"argv", "env", "stdin_path"}


def test_the_invocation_environment_is_the_workspace_env_plus_the_declared_additions(tmp_path):
    """C-1008: `ws.env` carries the C-1031 git overrides a rebuild from `os.environ` would drop."""
    adapter = AttestedStub()
    bindir = tmp_path / "bin"
    _executable(bindir, adapter.BINARY)
    ws = _workspace(tmp_path, env={"PATH": str(bindir), "GIT_CONFIG_GLOBAL": "/dev/null"})
    inv, _ = _authorized(tmp_path, adapter, ws=ws)
    assert dict(inv.env) == {**dict(ws.env), **dict(ENV_EVIDENCE)}


def test_an_undeclared_environment_key_is_refused(tmp_path):
    """C-1008: `env_evidence` is the whole of what an adapter may add to the minimal environment."""
    adapter = AttestedStub()
    launch = Launch(argv=("run",), env={**dict(ENV_EVIDENCE), "STUB_EXTRA": "1"})
    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, adapter, launch=launch)
    assert "STUB_EXTRA" in str(exc.value)


def test_a_declared_key_with_a_different_value_is_refused(tmp_path):
    """C-1008, C-1025: the value is the evidence, so a matching name is not enough."""
    adapter = AttestedStub()
    launch = Launch(argv=("run",), env={"STUB_CONFIG_CONTENT": "{}"})
    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, adapter, launch=launch)
    assert "STUB_CONFIG_CONTENT" in str(exc.value)


def test_a_re_added_credential_variable_is_refused_without_echoing_its_value(tmp_path):
    """C-1008, C-1035: a credential C-1008 dropped is unrepresentable, and its value never reaches a message."""
    adapter = AttestedStub()
    secret = "sk-ant-do-not-log-this"
    launch = Launch(argv=("run",), env={**dict(ENV_EVIDENCE), "ANTHROPIC_API_KEY": secret})
    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, adapter, launch=launch)
    message = str(exc.value)
    assert "ANTHROPIC_API_KEY" in message
    assert secret not in message


def test_a_launch_re_adding_path_is_refused(tmp_path):
    """C-1008: a `PATH` into the worktree is the sharpest widening of the minimal environment."""
    adapter = AttestedStub()
    launch = Launch(argv=("run",), env={**dict(ENV_EVIDENCE), "PATH": str(tmp_path)})
    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, adapter, launch=launch)
    assert "PATH" in str(exc.value)


def test_argv_zero_is_an_absolute_realpath(tmp_path):
    """E9a: nothing else validated `argv[0]`, and `cwd` is attacker-controlled content."""
    adapter = HarnessStub()
    expected = _executable(tmp_path / "bin", adapter.BINARY)
    inv, _ = _authorized(tmp_path, adapter)
    assert inv.argv[0] == str(expected.resolve())


def test_an_unresolvable_binary_is_absent(tmp_path):
    """E9a: `ABSENT` is the reason a consumer degrades to a graceful skip on."""
    adapter = HarnessStub()
    launcher = Launcher(binary="no-such-harness-binary")
    with pytest.raises(HarnessUnavailable) as exc:
        _authorized(tmp_path, adapter, launcher=launcher)
    assert exc.value.reason is FailureReason.ABSENT


def test_a_launcher_prefix_resolves_the_prefix_head_not_the_binary(tmp_path):
    """C-1014: the prefix head is what `execve` actually runs; the wrapper resolves the rest."""
    adapter = HarnessStub()
    wrapper = _executable(tmp_path / "bin", "ocx")
    launcher = Launcher(binary="not-on-path-binary", prefix=("ocx", "package", "exec", "pkg", "--"))
    inv, _ = _authorized(tmp_path, adapter, launcher=launcher)
    assert inv.argv[0] == str(wrapper.resolve())
    assert "not-on-path-binary" in inv.argv[1:]


def test_a_failing_sandbox_probe_refuses_the_launch(tmp_path):
    """C-1025, C-1040: an inconclusive probe is `False` — never a silent unsandboxed run."""
    adapter = OsStub(sandbox_passes=False)
    with pytest.raises(UnsupportedCapability):
        _authorized(tmp_path, adapter)
    assert adapter.sandbox_calls == 1


def test_a_passing_sandbox_probe_authorizes_the_launch(tmp_path):
    """C-1025: the probe is what promotes an `os` claim to a derived `os` axis."""
    adapter = OsStub(sandbox_passes=True)
    _, derived = _authorized(tmp_path, adapter)
    assert (derived.write_enforcement, derived.network_enforcement) == ("os", "os")


def test_a_second_authorize_reuses_the_cached_probe(tmp_path):
    """C-1025: the digest is keyed on the plan, so `os` is reachable across reviews in practice."""
    adapter = OsStub(sandbox_passes=True)
    cache = ProbeCache()
    _authorized(tmp_path, adapter, cache=cache)
    _authorized(tmp_path, adapter, cache=cache)
    assert adapter.sandbox_calls == 1


def test_an_adapter_with_no_os_axis_is_never_sandbox_probed(tmp_path):
    """C-1025: the probe is the `os` level's price, and no other level pays it."""
    adapter = HarnessStub()
    _authorized(tmp_path, adapter)
    assert adapter.sandbox_calls == 0


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_only_an_os_claiming_shipped_adapter_answers_its_sandbox_probe(name):
    """E70/J: the "every adapter that claims no `os` axis returns `False`" universal, pinned over the real four.

    `test_an_adapter_with_no_os_axis_is_never_sandbox_probed` proves the
    PROTOCOL half against a stub — that `authorize` does not call the probe. It
    cannot prove the ADAPTER half, because a stub is not one of the four things
    shipped, and the prose universal is about those four.

    That gap is the defect J names: a universal over N implementations asserted
    in prose with no parametrized pin drifts, and this branch found the same
    shape wrong three times (the exit-143 order, `NEVER_SET`'s "in full", the
    ADR's "written down here"). So the claim is now an executable one — add a
    fifth adapter that claims `os` without a real probe, or drop `codex`'s, and
    this fails.

    **Every leg asserts; none skips.** A skipped leg and a silently degraded
    gate are indistinguishable in pytest's output, which is the shape that let
    the contract tier once report 81 passed / 8 skipped while testing three
    harnesses — so the `os` claimer is asserted positively rather than stepped
    over. The claim is a biconditional and both directions are checked here:
    an adapter claims the `os` axis **iff** its probe does real work.

    `runner=None` is safe on the negative legs precisely because a non-`os`
    adapter's override is the one-line `return False` the docstring claims: an
    implementation that actually probed would raise on it, which is the point.
    The positive leg does not pass `None` — it asserts the claim, and that
    codex's probe genuinely proves the sandbox is asserted where the fixtures
    for it already live (`test_adapter_codex.py`, `... is True` under a
    `ProbeRunner` with no knob set, plus sixteen negatives, one per
    observation). Duplicating that machinery here would be a second copy of
    C-1040's oracle, which is the drift this convention exists to prevent.
    """
    adapter = load(name)
    plan = adapter.containment_plan(HarnessConfig(), None)  # type: ignore[arg-type]
    if "os" in {plan.write_enforcement, plan.network_enforcement}:
        assert name == "codex", f"{name} claims an `os` axis; only codex ships a real sandbox probe"
        return
    assert adapter.sandbox_probe(None, None, None, {}) is False  # type: ignore[arg-type]


def test_a_disagreeing_adapter_never_receives_an_invocation(tmp_path):
    """C-1025: `authorize` is the only producer of a review `Invocation`, so the gate is unskippable."""
    adapter = DisagreeingStub()
    with pytest.raises(UnsupportedCapability):
        _authorized(tmp_path, adapter)


# ---------------------------------------------------------------------------
# `resolve_executable` and `launch_argv` — WP3's carry-forward
# ---------------------------------------------------------------------------


def test_resolve_executable_reads_the_passed_path_and_never_os_environ(tmp_path, monkeypatch):
    """E9a: `config.minimal_env` already rebuilt `PATH`; reading `os.environ` would undo it."""
    real = tmp_path / "real"
    _executable(real, "h-bin")
    monkeypatch.setenv("PATH", str(real))
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(HarnessUnavailable) as exc:
        resolve_executable("h-bin", {"PATH": str(empty)})
    assert exc.value.reason is FailureReason.ABSENT


def test_resolve_executable_refuses_a_found_but_unexecutable_file(tmp_path):
    """E9a: found and not executable is `ABSENT` too — `shutil.which` alone cannot tell them apart."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "h-bin").write_bytes(b"not executable\n")
    with pytest.raises(HarnessUnavailable) as exc:
        resolve_executable("h-bin", {"PATH": str(bindir)})
    assert exc.value.reason is FailureReason.ABSENT


def test_resolve_executable_refuses_a_relative_name_not_on_path(tmp_path, monkeypatch):
    """E9a: `cwd` is the ephemeral worktree, so a cwd-relative resolution is attacker-controlled."""
    _executable(tmp_path, "h-bin")
    monkeypatch.chdir(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(HarnessUnavailable) as exc:
        resolve_executable("./h-bin", {"PATH": str(empty)})
    assert exc.value.reason is FailureReason.ABSENT


def test_resolve_executable_returns_an_absolute_symlink_resolved_path(tmp_path):
    """E9a: the realpath, so a symlinked shim cannot hide which binary ran."""
    real = _executable(tmp_path / "real", "h-bin")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "h-bin").symlink_to(real)
    resolved = resolve_executable("h-bin", {"PATH": str(bindir)})
    assert Path(resolved).is_absolute()
    assert resolved == str(real.resolve())


def test_launch_argv_resolves_the_prefix_head_and_keeps_the_rest_verbatim(tmp_path):
    """C-1014: the binary behind the wrapper's `--` is the wrapper's to resolve, not nox's."""
    wrapper = _executable(tmp_path / "bin", "ocx")
    launcher = Launcher(binary="opencode", prefix=("ocx", "package", "exec", "pkg", "--"))
    argv = launch_argv(launcher, {"PATH": str(tmp_path / "bin")}, "run", "hello")
    assert argv == (str(wrapper.resolve()), "package", "exec", "pkg", "--", "opencode", "run", "hello")


def test_probe_cwd_yields_a_fresh_empty_directory_and_removes_it():
    """C-1014: OpenCode executes `.opencode/plugins/` on any startup, so a probe never inherits a cwd."""
    with probe_cwd() as cwd:
        assert cwd.is_dir()
        assert list(cwd.iterdir()) == []
        seen = cwd
    assert not seen.exists()


# ---------------------------------------------------------------------------
# Model selection: C-1030 rule 6, D-f
# ---------------------------------------------------------------------------


def test_a_class_present_in_the_table_resolves_to_its_literal():
    """C-1030: the adapter's shipped table is what maps a capability class to a harness literal."""
    spec, model_class = resolve_model(MODELS, config(model="deep-reasoning"))
    assert (spec, model_class) == (ModelSpecT(model="stub-model-1"), "deep-reasoning")


def test_a_class_absent_from_the_table_takes_the_harness_default():
    """C-1030 rule 6, D-f: not an error and not a substitution — the honest record is that the harness chose."""
    assert resolve_model(MODELS, config(model="fast-balanced")) == (None, "fast-balanced")


def test_no_configured_class_takes_the_harness_default_with_no_class_recorded():
    """C-1030 rule 2: nothing was asked for, so nothing is recorded."""
    assert resolve_model(MODELS, config()) == (None, None)


def test_a_configured_literal_overrides_the_shipped_table():
    """C-1030 rule 1: a trusted `model_literal` overrides the table outright."""
    spec, model_class = resolve_model(MODELS, config(model="deep-reasoning", model_literal="operator-choice"))
    assert (spec, model_class) == (ModelSpecT(model="operator-choice"), "deep-reasoning")


@pytest.mark.parametrize("literal", ["--dangerously-skip-permissions", "with space", "", "nul\x00byte"])
def test_a_literal_that_is_not_a_usable_argv_word_is_refused(literal):
    """C-1030: accepting argv here would reopen the C-1023 hole through the back door."""
    with pytest.raises(ConfigError):
        resolve_model(MODELS, config(model_literal=literal))


# ---------------------------------------------------------------------------
# Warnings: C-1020, C-1036
# ---------------------------------------------------------------------------


def test_a_version_mismatch_warns_naming_both_versions():
    """C-1020: a silent drift must not be mistaken for a verified run."""
    warning = version_warning(info_for("stub", version="2.1.0", verified_against="2.0.9"))
    assert warning is not None
    assert "2.1.0" in warning
    assert "2.0.9" in warning


def test_a_matching_version_warns_nothing():
    """C-1020: the warning exists for drift, not for every run."""
    assert version_warning(info_for("stub", version="2.0.9", verified_against="2.0.9")) is None


def test_an_unknown_version_is_not_a_mismatch():
    """C-1020, C-1035: an unknown version is not evidence of a mismatch, so none is invented."""
    assert version_warning(info_for("stub", version=None, verified_against="2.0.9")) is None


def test_the_measured_negative_pair_warns_naming_both_models_and_the_citation():
    """C-1036, D-b: keyed on the MODEL pair, and the warning carries its one citation."""
    writer, reviewer = ASYMMETRY_NEGATIVE[0]
    warning = asymmetry_warning(writer, reviewer)
    assert warning is not None
    assert writer in warning
    assert reviewer in warning
    assert ASYMMETRY_CITATION in warning


def test_a_point_release_of_the_pair_still_warns():
    """C-1036: prefixes, not exact ids, so a point release does not silently stop matching."""
    writer, reviewer = ASYMMETRY_NEGATIVE[0]
    assert asymmetry_warning(f"{writer}-20260901", f"{reviewer}-preview") is not None


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_the_asymmetry_warning_fires_in_every_harness_own_model_spelling(name):
    """C-1036: a warning that is silent for one reviewer is worse than one that never fires.

    OpenCode names a model `github-copilot/gpt-5.6-luna` and nothing else in v1
    carries a `provider/` prefix, so a head-anchored match against the shipped
    literal matched three harnesses and structurally never the fourth. The
    prefix is read off each adapter's OWN shipped `MODELS`, so a harness that
    changes how it spells an id is audited by this test rather than by a reader.
    """
    if importlib.util.find_spec(ADAPTERS[name].partition(":")[0]) is None:
        # `find_spec`, not `except HarnessUnavailable`: `load` raises the same
        # `UNSUPPORTED` for a module that is absent and for one that is present
        # and broken, and the second must fail here rather than skip.
        pytest.skip(f"{name}: no adapter module in this tree yet — this test starts covering it when one lands")
    adapter = load(name)
    writer, reviewer = ASYMMETRY_NEGATIVE[0]
    ids = [spec if isinstance(spec, str) else spec.model for spec in adapter.MODELS.values()]
    prefixes = {model.rpartition("/")[0] for model in ids}
    assert prefixes, f"{name} ships no model literal to read a spelling off"
    for prefix in prefixes:
        head = f"{prefix}/" if prefix else ""
        assert asymmetry_warning(f"{head}{writer}-1", f"{head}{reviewer}-1") is not None, head


def test_the_reversed_pair_warns_nothing():
    """C-1036: the paper's measured effect is in one direction only."""
    writer, reviewer = ASYMMETRY_NEGATIVE[0]
    assert asymmetry_warning(reviewer, writer) is None


def test_an_unknown_writer_warns_nothing():
    """C-1036: `authored_by` is what the caller said, and silence is the honest answer to `None`."""
    _, reviewer = ASYMMETRY_NEGATIVE[0]
    assert asymmetry_warning(None, reviewer) is None


def test_a_harness_default_reviewer_warns_nothing():
    """C-1036: `model is None` means the harness chose, which is silent rather than guessed."""
    writer, _ = ASYMMETRY_NEGATIVE[0]
    assert asymmetry_warning(writer, None) is None


# ---------------------------------------------------------------------------
# The parse framework: C-1011, C-1012, C-1018, C-1019
# ---------------------------------------------------------------------------


def test_an_ok_status_without_a_verdict_is_refused():
    """C-1011: `verdict` is set iff `status == "ok"`, enforced once rather than at four return sites."""
    with pytest.raises(ValueError):
        _parsed(status="ok", verdict=None, reason=None)


def test_a_non_ok_status_with_a_verdict_is_refused():
    """C-1011: an adapter reaching a success return by elimination cannot express it."""
    with pytest.raises(ValueError):
        _parsed(status="error", verdict="approve", reason=FailureReason.MALFORMED_OUTPUT)


def test_an_ok_status_with_a_reason_is_refused():
    """C-1011: `reason` is set iff the status is not `ok` — the forward direction."""
    with pytest.raises(ValueError):
        _parsed(status="ok", verdict="approve", reason=FailureReason.KILLED)


def test_a_non_ok_status_without_a_reason_is_refused():
    """C-1011: `reason` is set iff the status is not `ok` — the reverse direction."""
    with pytest.raises(ValueError):
        _parsed(status="indeterminate", verdict=None, reason=None)


def test_a_status_outside_the_tri_state_is_refused_at_the_parse_type():
    """C-1011: the domain check belongs at the EARLIER type, not only one type later on `Review`.

    A word an adapter invented satisfies both tri-state invariants — `verdict`
    unset with a `reason` set is exactly what a non-`ok` outcome looks like — so
    it left `parse` unchallenged and travelled through `api.review()` before
    anything looked at it. An invariant is what the type may HOLD, which is why
    this one belongs here and the `detail` flattening does not: refused rather
    than coerced, for the reason `outcome.Review` gives — resolving an unknown
    word onto `indeterminate` hides an adapter bug behind an outcome that reads
    as one nox classified.
    """
    with pytest.raises(ValueError, match="status is one of"):
        _parsed(status="approved", verdict=None, reason=FailureReason.MALFORMED_OUTPUT)  # type: ignore[arg-type]


def test_a_reason_that_is_not_a_failure_reason_is_refused_at_the_parse_type():
    """C-1011/C-1029: `reason` is annotation-only, and `--json` calls `.value` on whatever arrives.

    An adapter returning the wire string rather than the member satisfies every
    invariant here and on `Review` — the tri-state checks test `is not None`,
    never the type — and then `cli.to_json` ends in `AttributeError: 'str' object
    has no attribute 'value'`. That is the traceback-instead-of-an-answer shape
    `main`'s `.get` default exists to prevent, reached on the other output path
    from the same untrusted source.
    """
    with pytest.raises(ValueError, match="reason is a FailureReason"):
        _parsed(status="error", verdict=None, reason="malformed_output")  # type: ignore[arg-type]


def test_every_finding_file_is_normalized_at_construction():
    """C-1019: a `../../etc/passwd` cannot reach a consumer that opens it, whichever adapter parsed it."""
    hostile = Finding(severity="block", title="t", body="see ../../etc/passwd", file="../../etc/passwd")
    parsed = _parsed(findings=(hostile,))
    assert parsed.findings[0].file is None
    assert parsed.findings[0].body == "see ../../etc/passwd"


@pytest.mark.parametrize(
    "raw",
    ["/etc/passwd", "../etc/passwd", "a/../../b", "a\x00b", "", "C:\\Windows\\system32", "..\\windows"],
    ids=["absolute", "leading-dotdot", "embedded-dotdot", "nul", "empty", "drive-letter", "backslash-dotdot"],
)
def test_an_unsafe_finding_file_resolves_to_none(raw):
    """C-1019: not a location in the review — an attempt to point a reader outside the worktree."""
    assert safe_finding_file(raw) is None


def test_a_repo_relative_finding_file_survives():
    """C-1019: the check refuses traversal, not location — a real path is still evidence."""
    assert safe_finding_file("src/nox/harness.py") == "src/nox/harness.py"


def test_a_dot_slash_prefix_is_normalized_away():
    """C-1019: normalized, so a consumer resolves one spelling of a path and not three."""
    assert safe_finding_file("./a/b.py") == "a/b.py"


def test_a_missing_finding_file_stays_missing():
    """C-1019: `None` in, `None` out — the harness located nothing and nothing is invented."""
    assert safe_finding_file(None) is None


@pytest.mark.parametrize("severity", ["block", "high", "warn", "suggest"])
@pytest.mark.parametrize("shape", ["{}", "{}  ", "  {}", "  {}  "])
def test_a_known_severity_word_round_trips(severity, shape):
    """C-1018: compared case-folded and stripped, so a harness's spacing is not a new severity."""
    assert to_severity(shape.format(severity)) == severity
    assert to_severity(shape.format(severity.upper())) == severity


@pytest.mark.parametrize("raw", ["", "critical", "info", "nit", "  ", "blocker"])
def test_an_unknown_severity_word_fails_to_the_highest(raw):
    """C-1018: a `suggest` default silently downgrades a real finding; a `block` default costs one look."""
    assert to_severity(raw) == "block"
    assert to_severity(raw) != "suggest"


def test_the_sigterm_exit_status_is_our_own_kill():
    """C-1012: `143` is `128 + SIGTERM`, labelled as such rather than as a generic failure."""
    assert reason_for_exit(SIGTERM_EXIT) is FailureReason.KILLED


@pytest.mark.parametrize("code", [0, 1, 137, -1, -15])
def test_every_other_exit_status_carries_no_reason(code):
    """C-1011: the exit code is never the success gate, so mapping more of it would rebuild a forbidden branch."""
    assert reason_for_exit(code) is None


# ---------------------------------------------------------------------------
# The prompt route: C-1028, C-1043(4)
# ---------------------------------------------------------------------------


def test_the_prompt_is_written_into_the_workspace_scratch(tmp_path):
    """C-1028: the path is the delivery route, and the text is returned beside it."""
    ws = _workspace(tmp_path)
    path, text = review_prompt(ws, info_for("stub"), None)
    assert path == ws.scratch / PROMPT_FILENAME
    assert path.read_bytes() == text.encode("utf-8")


def test_the_prompt_states_every_filtered_entry_not_only_the_changed_ones(tmp_path):
    """C-1043(2): each dropped entry is reviewer evidence, so the prompt gets the union.

    Coordinator ruling of 2026-09-03: `filtered` is evidence and feeds
    `render`'s `filtered_paths`; `filtered_changed` is the C-1043(4) verdict
    gate and belongs to `api.review()`. Narrowing the prompt to the differing
    subset would blind the reviewer to a symlink the branch just added, which
    is the one entry C-1043(2) exists to show them.
    """
    ws = _workspace(
        tmp_path,
        filtered=("static-entry -> /elsewhere", "changed-entry -> /elsewhere"),
        filtered_changed=("changed-entry -> /elsewhere",),
    )
    _, text = review_prompt(ws, info_for("stub"), None)
    assert "changed-entry" in text
    assert "static-entry" in text


DO_NOT_APPROVE = re.compile(
    r"\b(do not|don't|must not|cannot|can't|may not|never)\b[^.\n]{0,140}\bapprove\b",
    re.IGNORECASE,
)
"""C-1043(4)'s consequence, matched as prose rather than as a literal sentence.

The wording belongs to `prompt._INCOMPLETE` and `tests/unit/test_prompt.py`
pins it there; what these two tests own is the WIRING — which of `Workspace`'s
two filtered fields `review_prompt` hands `render` as the gate.
"""


@pytest.mark.parametrize(
    ("filtered_changed", "expected"),
    [((), False), (("changed-entry -> /elsewhere",), True)],
    ids=["committed-symlink-only", "branch-changed-a-symlink"],
)
def test_the_do_not_approve_consequence_is_wired_to_filtered_changed_not_to_filtered(
    tmp_path, filtered_changed, expected
):
    """C-1043(4), E36: `review_prompt` gates the consequence on the DIFFERING subset.

    Coordinator ruling of 2026-09-03 and its WP13 follow-up: `filtered` is the
    union C-1043(2) requires as reviewer evidence, and `filtered_changed` is the
    verdict gate. Both cases below carry the SAME non-empty `filtered`, so the
    only thing that can move the consequence is which field `review_prompt`
    reads.

    Untested, this wiring was a mutation that restored E36 verbatim: hard-coding
    `filtered_changed=True` at the call site left the whole suite green, and it
    tells every reviewer of every repository holding one committed symlink or
    submodule that the change was withheld and must not be approved — a
    `needs-attention` verdict manufactured out of a file nobody touched. Hard-
    coding `False` is the other half and loses the gate entirely, so both
    directions are asserted.

    `STRUCTURED_OUTPUT` is on so `WIRE_SCHEMA` stays out of the text: the schema
    carries prose of its own and the negative case must not match on it.
    """
    ws = _workspace(
        tmp_path,
        filtered=("static-entry -> /elsewhere", "changed-entry -> /elsewhere"),
        filtered_changed=filtered_changed,
    )
    info = info_for("stub", capabilities=frozenset({Capability.ENUMERABLE_DENY, Capability.STRUCTURED_OUTPUT}))
    _, text = review_prompt(ws, info, None)
    assert bool(DO_NOT_APPROVE.search(text)) is expected
    # The evidence is unconditional either way — the gate moves the consequence
    # and never the list (C-1043(2)).
    assert "static-entry" in text
    assert "changed-entry" in text


def test_the_prompt_takes_its_scope_from_the_workspace(tmp_path):
    """C-1028: one source for the scope — `Workspace.scope`, never a second parameter."""
    code, _ = review_prompt(_workspace(tmp_path, scope="code-diff"), info_for("stub"), None)
    plan_ws = _workspace(tmp_path / "plan", scope="plan-artifact")
    _, plan_text = review_prompt(plan_ws, info_for("stub"), None)
    assert "plan or design artifact" in plan_text
    assert "plan or design artifact" not in code.read_text()


def test_the_prompt_states_the_neutralized_and_omitted_entries_verbatim(tmp_path):
    """C-1028: `neutralized_paths` is the argument an adapter would otherwise silently forget."""
    ws = _workspace(tmp_path, neutralized=("CLAUDE.md",), omitted=("build/artifact.bin",))
    _, text = review_prompt(ws, info_for("stub"), None)
    assert "CLAUDE.md" in text
    assert "build/artifact.bin" in text


def test_a_structured_output_harness_is_asked_for_no_wire_schema(tmp_path):
    """C-1028: the harness-native schema is the single authority; a prose restatement would drift."""
    info = info_for("stub", capabilities=frozenset({Capability.ENUMERABLE_DENY, Capability.STRUCTURED_OUTPUT}))
    _, text = review_prompt(_workspace(tmp_path), info, None)
    assert WIRE_SCHEMA not in text


def test_a_harness_without_structured_output_is_asked_for_the_wire_schema(tmp_path):
    """C-1028: `structured_output` is read off `info.capabilities`, never hand-set at a call site."""
    info = info_for("stub", capabilities=frozenset({Capability.ENUMERABLE_DENY}))
    _, text = review_prompt(_workspace(tmp_path), info, None)
    assert WIRE_SCHEMA in text


def test_the_argv_prompt_limit_sits_well_under_a_typical_arg_max():
    """C-1028: the refusal must fire before the kernel's `E2BIG` truncates the anti-injection framing."""
    assert isinstance(PROMPT_ARGV_LIMIT, int)
    assert 0 < PROMPT_ARGV_LIMIT <= ARG_MAX_TYPICAL // 10


# ---------------------------------------------------------------------------
# The registry: C-1024, C-1042(5)
# ---------------------------------------------------------------------------


def test_the_registry_carries_every_v1_key():
    """D-ab: the registry ships every v1 key up front, so no adapter branch edits it."""
    assert set(ADAPTERS) == {"claude", "codex", "copilot", "opencode"}


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_every_registry_value_is_a_dotted_module_attribute(name):
    """C-1024: shipped literals in the `fsspec` shape — a repository cannot steer the import target."""
    assert re.fullmatch(r"nox\.adapters\.[a-z_][a-z_0-9]*:[A-Za-z_]\w*", ADAPTERS[name])


def test_an_unregistered_key_is_unsupported_without_echoing_it():
    """C-1042(5), C-1035(1): `[review] harness` is repository-supplied and never lands in `detail`."""
    unknown = "harness-from-the-branch"
    with pytest.raises(HarnessUnavailable) as exc:
        load(unknown)
    message = str(exc.value)
    assert exc.value.reason is FailureReason.UNSUPPORTED
    assert unknown not in message
    assert all(key in message for key in ADAPTERS)


@pytest.mark.parametrize(
    "target",
    ["nox.adapters.not_a_module:Adapter", "nox.adapters.codex:NotAnAttribute"],
    ids=["module-missing", "attribute-missing"],
)
def test_a_registered_key_whose_module_or_attribute_is_gone_is_unsupported(monkeypatch, target):
    """C-1024, C-1035(1): an incomplete build refuses by reason, and the dotted path never reaches `detail`.

    This leg was covered only while no shipped adapter module existed. All four
    now do, so every registered key resolves and the `except` body went
    unreachable — a 99% gate on a `fail_under = 100` project, and the reason
    this is driven by a synthetic registry entry rather than by a real key.
    """
    monkeypatch.setattr(adapters_module, "ADAPTERS", MappingProxyType({**ADAPTERS, "incomplete": target}))
    with pytest.raises(HarnessUnavailable) as exc:
        load("incomplete")
    message = str(exc.value)
    assert exc.value.reason is FailureReason.UNSUPPORTED
    assert "no adapter is installed" in message
    # C-1035(1): the exception TYPE, never its text — an import error's message
    # carries the dotted path and reads as an invitation to supply one.
    assert "nox.adapters" not in message


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_a_registered_key_never_raises_a_bare_import_error(name):
    """C-1024: a missing module or attribute is `HarnessUnavailable`, never `ModuleNotFoundError`."""
    try:
        adapter = load(name)
    except HarnessUnavailable as exc:
        assert exc.reason is FailureReason.UNSUPPORTED
    else:
        assert adapter.name == name


@pytest.mark.parametrize(
    ("target", "expected"),
    [("nox.adapters.definitely_not_here:Nope", "ModuleNotFoundError"), ("nox.adapters.codex:Nope", "AttributeError")],
)
def test_a_registered_key_whose_module_or_attribute_is_missing_refuses(monkeypatch, target, expected):
    """C-1024: registered-but-unloadable is `HarnessUnavailable`, and the message names the type only.

    Until every adapter shipped, this branch was covered by accident — a
    registered key whose module did not exist yet. With all four present it is
    unreachable without a planted target, so it is planted rather than lost.
    """
    monkeypatch.setattr("nox.adapters.ADAPTERS", MappingProxyType({**ADAPTERS, "planted": target}))
    with pytest.raises(HarnessUnavailable) as excinfo:
        load("planted")
    assert excinfo.value.reason is FailureReason.UNSUPPORTED
    assert expected in str(excinfo.value)
    # The dotted path would read as an invitation to supply one (C-1035(1)).
    assert "nox.adapters." not in str(excinfo.value)


def test_no_core_module_names_an_adapter_module():
    """C-1024: the core flow reaches an adapter through `load()` and nothing else."""
    needle = re.compile(r"nox\.adapters\.(" + "|".join(re.escape(n) for n in ADAPTERS) + r")\b")
    core = [
        p
        for p in _repo_files()
        if p.is_relative_to(SRC) and p.suffix == ".py" and not p.is_relative_to(ADAPTERS_DIR) and p.is_file()
    ]
    assert len(core) >= 8, f"an empty listing would pass silently: {core}"
    text_hits = [p.name for p in core if needle.search(p.read_text(encoding="utf-8"))]
    import_hits = []
    for path in core:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            import_hits += [(path.name, m) for m in modules if needle.search(m)]
    assert text_hits == []
    assert import_hits == []


def test_no_shipped_adapter_emits_a_never_emitted_flag():
    """C-1023: every member LIFTS a containment control, so nox emitting one defeats its own plan."""
    files = sorted(p for p in _repo_files() if p.is_relative_to(ADAPTERS_DIR) and p.suffix == ".py" and p.is_file())
    assert ADAPTERS_DIR / "__init__.py" in files, f"the adapters package was not enumerated: {files}"
    offenders = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in NEVER_EMITTED:
                offenders.append((path.name, node.value))
    assert offenders == []


def test_a_registered_key_resolves_to_the_instance_its_dotted_path_names(monkeypatch):
    """C-1024: the success leg of the lazy import.

    Appended by the implementation phase: no shipped adapter module exists
    until wave 4, so every registered key takes the `ImportError` leg above and
    the one line that returns an adapter is otherwise unreachable. The imports
    are function-local so this test is a pure append.
    """
    import sys
    import types

    name = sorted(ADAPTERS)[0]
    module_name, _, attribute = ADAPTERS[name].partition(":")
    module = types.ModuleType(module_name)
    setattr(module, attribute, HarnessStub)
    monkeypatch.setitem(sys.modules, module_name, module)
    assert isinstance(load(name), HarnessStub)


# ---------------------------------------------------------------------------
# Review-fix round: the panel's findings, each with the case that was live
# before the fix. Appended as a block so the sections above stay as they were.
# ---------------------------------------------------------------------------

# `_argv_corroborates` rules 3 and 4 — C-1025

CODEX_EVIDENCE = ("-c", "sandbox_mode=read-only")
"""Codex's real containment run: the flag AND its `key=value`, as `prepare` emits them."""

DENY_TOOL_EVIDENCE = ("--deny-tool", "shell", "--deny-tool", "write")
"""Copilot's shape — a run that legitimately repeats one flag."""


def _os_plan(evidence):
    return _plan(mechanism="os-sandbox", write="os", network="os", argv_evidence=evidence)


def test_a_second_unrelated_use_of_a_run_flag_still_corroborates():
    """C-1025 rule 4: `capability.py` puts Codex's reasoning-effort knob on a SECOND `-c`.

    Refusing every repeat of an evidence flag makes Codex unlaunchable the
    moment a reasoning effort is configured — WP7b emits `-c
    model_reasoning_effort=high` for a reason unrelated to containment, and it
    collides with `sandbox_mode=` on nothing but the flag spelling. Rule 3 owns
    that flag's collision surface by KEY, so rule 4 exempts it.
    """
    inv = _inv("codex", "exec", *CODEX_EVIDENCE, "-c", "model_reasoning_effort=high")
    derived = _derived(inv, _os_plan(CODEX_EVIDENCE), cached=True)
    assert (derived.write_enforcement, derived.network_enforcement) == ("os", "os")


def test_a_run_that_legitimately_repeats_a_flag_corroborates():
    """C-1025 rule 4: `--deny-tool shell --deny-tool write` is one claim, not a claim and a collision."""
    inv = _inv("copilot", *DENY_TOOL_EVIDENCE, "--model", "m")
    derived = _derived(inv, _plan(argv_evidence=DENY_TOOL_EVIDENCE))
    assert (derived.write_enforcement, derived.network_enforcement) == ("harness", "harness")


def test_a_long_spelling_of_the_evidence_key_does_not_corroborate():
    """C-1025 rule 3: `--config=sandbox_mode=danger-full-access` is the same setting, last-wins."""
    inv = _inv("codex", "exec", *CODEX_EVIDENCE, "--config=sandbox_mode=danger-full-access")
    derived = _derived(inv, _os_plan(CODEX_EVIDENCE), cached=True)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_an_attached_short_spelling_of_the_evidence_key_does_not_corroborate():
    """C-1025 rule 3: clap accepts `-csandbox_mode=…` attached, and it wins over the earlier one."""
    inv = _inv("codex", "exec", *CODEX_EVIDENCE, "-csandbox_mode=danger-full-access")
    derived = _derived(inv, _os_plan(CODEX_EVIDENCE), cached=True)
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_an_equals_joined_respecification_of_a_run_flag_does_not_corroborate():
    """C-1025 rule 4: `--tools=Read,Bash` names the same flag as `--tools Read`, and follows it."""
    inv = _inv("claude", "-p", *TOOL_EVIDENCE, "--tools=Read,Bash")
    derived = _derived(inv, _plan(argv_evidence=TOOL_EVIDENCE))
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_the_unshared_key_override_is_a_stated_residual_not_a_closed_hole():
    """C-1025: `--sandbox danger-full-access` shares no key with `sandbox_mode=`, and still corroborates.

    Asserted rather than wished away. Core cannot know two spellings are the
    same setting without modelling every harness's option table; the fix is for
    the adapter to name both in its own evidence, and `derive_containment`'s
    docstring says so. The day an adapter does, this test is the one that
    changes.
    """
    inv = _inv("codex", "exec", *CODEX_EVIDENCE, "--sandbox", "danger-full-access")
    derived = _derived(inv, _os_plan(CODEX_EVIDENCE), cached=True)
    assert (derived.write_enforcement, derived.network_enforcement) == ("os", "os")


# `authorize`: the environment an adapter may add — C-1008


@pytest.mark.parametrize(
    "key",
    ["PATH", "GIT_CONFIG_COUNT", "LD_PRELOAD", "NODE_OPTIONS", "ANTHROPIC_API_KEY"],
)
def test_a_hostile_environment_key_is_refused_even_when_the_plan_declares_it(tmp_path, key):
    """C-1008: declaring a key is not a permission to set it.

    `env = {**ws.env, **launch.env}` puts the adapter's value on top of the
    minimal environment, so a plan naming any of these as evidence would put it
    in the child with the containment stamp intact. Three rules cover the set:
    already in `ws.env`, a `DENY_PATTERNS` credential shape, or `NEVER_SET`.
    """
    adapter = HostileEnvStub(key)
    bindir = tmp_path / "bin"
    ws = _workspace(tmp_path, env={"PATH": str(bindir), "HOME": str(tmp_path), "GIT_CONFIG_COUNT": "3"})
    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, adapter, ws=ws)
    assert key in str(exc.value)


SWEPT_INTO_NEVER_SET: Final[frozenset[str]] = frozenset({"LD_AUDIT", "LD_LIBRARY_PATH", "PYTHONPATH"})
"""The three loader/interpreter channels the H5 sweep found on `NEVER_FORWARD` and not on `NEVER_SET`.

Written here as literals rather than read back out of `harness.NEVER_SET`, so
the parametrization below was RED before they were added: a table over the
shipped set alone passes vacuously for a name the shipped set does not carry,
which is precisely the shape of the gap. `LD_AUDIT` is `LD_PRELOAD`'s twin —
glibc's rtld-audit interface loads the named object before the harness's first
line — and an adapter declaring it as `env_evidence` passed `authorize`.
"""


@pytest.mark.parametrize("name", sorted(NEVER_SET | SWEPT_INTO_NEVER_SET))
def test_no_launch_may_set_a_loader_hijack_channel_however_its_plan_declares_it(tmp_path, name):
    """C-1044(1): the refusal is over the whole shipped set, so a future member is covered for free.

    Table-driven over `NEVER_SET` itself and not over a hand-picked sample:
    C-1044 fixes the set's membership by CLASS ("⊇, so a future channel of the
    same class joins without an erratum"), and a sample would leave the next
    addition asserted by nothing. The union with `SWEPT_INTO_NEVER_SET` is the
    double entry that made this fail before the sweep landed.

    The message is asserted whole rather than by substring: the four env rules in
    `authorize` all name the offending key, so `name in str(exc.value)` passes on
    any of them and would not notice a member that is refused for being a
    credential shape or for colliding with `ws.env` instead of for being a
    hijack channel.
    """
    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, HostileEnvStub(name))
    assert str(exc.value) == f"launch env: {name} is a code-injection channel and is never set by a launch (C-1044)"


def test_never_set_can_never_drift_past_the_inherit_rule():
    """C-1008: every name a launch may not SET is already a name nox will not INHERIT."""
    assert NEVER_SET <= NEVER_FORWARD


def test_never_set_omits_the_one_name_a_containment_plan_must_set():
    """C-1008: why the two literals are separate rather than one reused set.

    `OPENCODE_CONFIG_CONTENT` is on the never-inherit list because it carries a
    whole config inline — and setting it is precisely OpenCode's containment
    mechanism, so the never-set list must not carry it.
    """
    assert "OPENCODE_CONFIG_CONTENT" in NEVER_FORWARD
    assert "OPENCODE_CONFIG_CONTENT" not in NEVER_SET


def test_a_missing_required_capability_refuses_before_the_sandbox_probe_spawns(tmp_path):
    """C-1013, C-1040: SD § 7.1 puts both `UNSUPPORTED` rows at "no harness spawned".

    The C-1040 probe is a full review-shaped spawn, so checking the capability
    after it would run a harness for a launch the gate was always going to
    refuse.
    """
    adapter = OsStub(sandbox_passes=True)
    bindir = tmp_path / "bin"
    _executable(bindir, adapter.BINARY)
    info = info_for(adapter.name, capabilities=frozenset())
    ws = _workspace(tmp_path, env={"PATH": str(bindir), "HOME": str(tmp_path)})
    plan = adapter.containment_plan(config(), info)
    launch = adapter.prepare(ws, info, config(), None)
    with pytest.raises(UnsupportedCapability) as exc:
        authorize(adapter, launch, ws, info, plan, ProbeCache(), FakeRunner())
    assert Capability.ENUMERABLE_DENY.value in str(exc.value)
    assert adapter.sandbox_calls == 0


def test_a_never_emitted_flag_in_the_final_argv_is_refused(tmp_path):
    """C-1023: the AST scan sees string literals only — a computed flag reaches argv unseen."""
    launch = Launch(argv=("-p", *TOOL_EVIDENCE, "--dangerously-skip-permissions"))
    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, HarnessStub(), launch=launch)
    assert "--dangerously-skip-permissions" in str(exc.value)


def test_a_never_emitted_flag_is_refused_in_its_equals_joined_spelling(tmp_path):
    """C-1023: matched on the token before `=`, like every other flag check in this module."""
    launch = Launch(argv=("-p", *TOOL_EVIDENCE, "--add-dir=/etc"))
    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, HarnessStub(), launch=launch)
    assert "--add-dir" in str(exc.value)


# `police_passthrough`: the two holes — C-1023


def test_a_trailing_value_taking_passthrough_flag_is_refused(permits):
    """C-1023 refusal 5: otherwise the harness binds nox's own first flag as this one's value.

    `codex --color -c sandbox_mode=read-only` makes `-c` the colour setting and
    leaves the sandbox word a stray positional, while derivation still finds the
    run contiguous and stamps the axis.
    """
    permits("codex", PERMITTED)
    with pytest.raises(ConfigError) as exc:
        police_passthrough("codex", [PERMITTED], ["-c", "sandbox_mode=read-only", "--model", "m"])
    assert str(exc.value) == f"passthrough: {PERMITTED} expects a value and none follows it (C-1023)"


def test_an_equals_joined_passthrough_duplicate_of_a_nox_flag_is_refused(permits):
    """C-1023 refusal 4: `--color=ours` and `--color ours` are the same flag to the harness."""
    permits("codex", PERMITTED)
    with pytest.raises(ConfigError) as exc:
        police_passthrough("codex", [PERMITTED, "x"], [f"{PERMITTED}=ours"])
    assert str(exc.value) == f"passthrough: {PERMITTED} duplicates a flag nox emits for this launch (C-1023)"


# `safe_finding_file`: what a consumer renders and may pass to a command — C-1019


@pytest.mark.parametrize(
    "raw",
    ["a\nb", "a\rb", "a\x1b[31mb", "﻿a", "‮", "-rf", " /etc/passwd"],
    ids=["newline", "carriage-return", "ansi-escape", "bom", "bidi-override", "leading-dash", "leading-space"],
)
def test_a_rendered_or_argument_shaped_finding_file_resolves_to_none(raw):
    """C-1019: `Finding.file` is model output a consumer renders and may hand to a command.

    A newline forges a second finding, `\x1b[` repaints the terminal, a BiDi
    override makes the rendered path name a different file than the one that
    opens, `-rf` is an option rather than a path, and a leading space renders
    as absolute while resolving as relative.
    """
    assert safe_finding_file(raw) is None


def test_a_finding_file_carrying_an_inner_space_still_survives():
    """C-1019: the refusal is about the edges and the non-printables, not about spaces."""
    assert safe_finding_file("src/my file.py") == "src/my file.py"


# `to_severity`: total, and the route every `Finding` takes — C-1018


def test_every_finding_severity_is_normalized_at_construction():
    """C-1018: `to_severity` was correct and called from nowhere in `src/`.

    WP1's row made both untrusted-output duties this class's, and an adapter
    passing a harness's raw word straight into a `Finding` got it unnormalized.
    """
    invented = Finding(severity=cast("Severity", "CRITICAL"), title="t", body="b", file=None)
    assert _parsed(findings=(invented,)).findings[0].severity == "block"


@pytest.mark.parametrize("raw", [None, 3, 3.5, [], {"severity": "block"}], ids=["none", "int", "float", "list", "dict"])
def test_a_non_string_severity_fails_to_the_highest_rather_than_raising(raw):
    """C-1018, C-1029: `"severity": null` gave an adapter an `AttributeError`, which is not a `NoxError`.

    An exception that is not a `NoxError` escapes `review()`'s totality as a
    traceback rather than resolving to a run outcome.
    """
    assert to_severity(raw) == "block"


# `probe_harness`: the empty probe cwd, bound structurally — C-1014


class _RecordingProbe:
    """Records what `probe_harness` hands its `probe`, and can raise instead of returning."""

    name = "recordingstub"
    BINARY = "recordingstub-bin"

    def __init__(self, *, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.seen: Path | None = None
        self.was_empty_dir = False

    def probe(self, runner, cfg, env, cwd: Path):
        del runner, cfg, env
        self.seen = cwd
        self.was_empty_dir = cwd.is_dir() and not any(cwd.iterdir())
        if self.unavailable:
            raise HarnessUnavailable(FailureReason.ABSENT, "no binary")
        return info_for(self.name)


def test_probe_harness_hands_the_adapter_an_empty_directory_and_removes_it():
    """C-1014, SD § 6.3: `probe` takes any path, so nothing but this wrapper stops the repo root.

    OpenCode executes `.opencode/plugins/` on any startup, so a probe that
    inherited a cwd would run branch-authored JavaScript with Bun shell access
    in the user's live tree, before the workspace existed.
    """
    adapter = _RecordingProbe()
    info = probe_harness(cast("Adapter", adapter), FakeRunner(), config(), {})
    assert info.name == adapter.name
    assert adapter.was_empty_dir
    assert adapter.seen is not None
    assert not adapter.seen.exists()


def test_probe_harness_removes_the_directory_on_the_exception_path():
    """C-1014: an unavailable harness is the common case, and it must not leave a directory behind."""
    adapter = _RecordingProbe(unavailable=True)
    with pytest.raises(HarnessUnavailable):
        probe_harness(cast("Adapter", adapter), FakeRunner(), config(), {})
    assert adapter.seen is not None
    assert not adapter.seen.exists()


class _TimeoutRecorder:
    """A `Process` recording every timeout it is handed, and every read of its pid.

    The pid read is the signal that matters: `supervise` touches it only on the
    kill ladder, so "an already-exited probe child is never signalled" is
    checkable rather than inferred from the absence of a traceback.
    """

    def __init__(
        self, exit_code: int = 0, running_for: int = 0, lines: tuple[str, ...] = (), watch: Path | None = None
    ) -> None:
        self.waits: list[float | None] = []
        self.line_waits: list[float] = []
        self.pid_reads = 0
        self.dir_alive: list[bool] = []
        self.watch = watch
        self._lines = list(lines)
        self._exit_code = exit_code
        # A fake must never reach `supervise`'s kill ladder: `pid` is a made-up
        # number and `_kill_group` would signal whatever real group holds it.
        # So it reports "still running" for exactly the probe's own waits and
        # has exited by the time the reap looks.
        self._running_for = running_for

    @property
    def pid(self) -> int:
        self.pid_reads += 1
        return 4242

    @property
    def collector_failure(self) -> BaseException | None:
        return None

    @property
    def overflowed(self) -> bool:
        return False

    def lines(self, timeout: float) -> tuple[str, ...]:
        self.line_waits.append(timeout)
        drained, self._lines = tuple(self._lines), []
        return drained

    def wait(self, timeout: float | None) -> int | None:
        self.waits.append(timeout)
        if self.watch is not None:
            self.dir_alive.append(self.watch.exists())
        return None if len(self.waits) <= self._running_for else self._exit_code


class _SpawningProbe:
    """A probe that spawns a child through the runner it was handed, like every real one."""

    name = "spawningstub"
    BINARY = "spawningstub-bin"

    def __init__(
        self,
        inv: Invocation,
        *,
        wait_for: float | None = 0.0,
        waits: int = 1,
        drain: bool = False,
        children: int = 1,
        inspect: bool = False,
        recorder: _TimeoutRecorder | None = None,
    ):
        self._inv = inv
        self._wait_for = wait_for
        self._waits = waits
        self._drain = drain
        self._children = children
        self._inspect = inspect
        self.recorder = recorder
        self.child = None
        self.inspected = None

    def probe(self, runner, cfg, env, cwd: Path):
        del cfg, env
        if self.recorder is not None:
            self.recorder.watch = cwd
        for _ in range(self._children):
            self.child = runner.spawn(self._inv)
            if self._drain:
                # An hour, which the seam has to refuse: `lines` is bounded by
                # its own argument and by nothing else.
                self.child.lines(3600.0)
            if self._inspect:
                self.inspected = (self.child.pid, self.child.collector_failure, self.child.overflowed)
            for _ in range(self._waits):
                self.child.wait(self._wait_for)
        return info_for(self.name)


def _spawned(adapter, runner):
    """Run `adapter` through `probe_harness` with a throwaway config and environment."""
    return probe_harness(cast("Adapter", adapter), runner, config(), {})


def test_a_probe_wait_of_none_is_clamped_to_the_probe_budget():
    """C-1014: `Process.wait(None)` waits indefinitely, and no supervisor is watching a probe.

    The clamp is at the seam rather than in `probe`'s docstring for the same
    reason `prepare` returns a `Launch`: an adapter cannot express the
    unbounded call at all.
    """
    recorder = _TimeoutRecorder()
    adapter = _SpawningProbe(Invocation(argv=("x",), cwd=Path(), env={}), wait_for=None, drain=True, recorder=recorder)
    _spawned(adapter, FakeRunner(recorder))
    # A hair under the budget, never `None` and never the hour the probe asked
    # for: the deadline was set when the wrapper was built, a moment earlier.
    waited = recorder.waits[0]
    assert waited is not None, "the unbounded wait reached the child"
    assert PROBE_BUDGET_S - 1.0 < waited <= PROBE_BUDGET_S
    assert PROBE_BUDGET_S - 1.0 < recorder.line_waits[0] <= PROBE_BUDGET_S


def test_a_probe_wait_shorter_than_the_budget_is_passed_through_unchanged():
    """C-1014: the clamp is a ceiling, never a floor — copilot's own 30 s must still be 30 s."""
    recorder = _TimeoutRecorder()
    adapter = _SpawningProbe(Invocation(argv=("x",), cwd=Path(), env={}), wait_for=30.0, recorder=recorder)
    _spawned(adapter, FakeRunner(recorder))
    assert recorder.waits[0] == 30.0


def test_a_probe_child_that_already_exited_is_never_signalled():
    """C-1014: the reap is `supervise`, whose first `wait(0.0)` reaps a dead child and stops."""
    recorder = _TimeoutRecorder(lines=("a footer line",))
    adapter = _SpawningProbe(Invocation(argv=("x",), cwd=Path(), env={}), recorder=recorder)
    _spawned(adapter, FakeRunner(recorder))
    # Both halves: the reap ran (its own `wait(0.0)` is the last one recorded),
    # and it signalled nothing. Without the first, deleting the reap outright
    # still satisfies `pid_reads == 0`.
    assert recorder.waits[-1] == 0.0
    assert recorder.pid_reads == 0


def test_the_reap_runs_while_the_probe_directory_still_exists():
    """C-1014: the ordering IS the fix — `rmtree` over a live child is the reported failure."""
    recorder = _TimeoutRecorder()
    adapter = _SpawningProbe(Invocation(argv=("x",), cwd=Path(), env={}), recorder=recorder)
    _spawned(adapter, FakeRunner(recorder))
    assert len(recorder.dir_alive) >= 2  # the probe's own wait, then the reap's
    assert all(recorder.dir_alive)


def test_a_probe_child_still_running_when_the_probe_returns_is_killed_and_reaped(tmp_path):
    """C-1014: a real child, because the hazard is a real `rmtree` over a live process.

    Copilot's shipped probe is exactly this shape — `wait(PROBE_TIMEOUT_S)`
    returning `None` on a hung harness — and it cannot signal from there:
    `Process` carries no kill and the ladder that owns one is `supervise`.
    """
    script = "print('working', flush=True); import time; time.sleep(60)"
    inv = Invocation(argv=(sys.executable, "-c", script), cwd=tmp_path, env={})
    adapter = _SpawningProbe(inv, wait_for=0.0)
    _spawned(adapter, SubprocessRunner())
    assert adapter.child is not None
    status = adapter.child.wait(0.0)
    assert status is not None, "the child outlived probe_harness"
    assert status < 0, f"reaped, but not by a signal: {status}"


class _FailingReap(_TimeoutRecorder):
    """A child the reap cannot reap: its `wait` is fine during the probe and raises after."""

    def wait(self, timeout: float | None) -> int | None:
        status = super().wait(timeout)
        if len(self.waits) > 1:
            raise PermissionError("kill refused")
        return status


class _SpawningSandbox(OsStub):
    """An `os`-claiming adapter whose `sandbox_probe` really spawns, as C-1040's does."""

    def __init__(self, inv: Invocation, *, wait_for: float | None = 0.0) -> None:
        super().__init__()
        self._inv = inv
        self._wait_for = wait_for

    def sandbox_probe(self, runner, ws, info, env):
        runner.spawn(self._inv).wait(self._wait_for)
        return super().sandbox_probe(runner, ws, info, env)


def test_the_bounded_view_delegates_every_member_but_the_two_it_clamps():
    """`_BoundedProcess` stands in for a `Process` wherever the adapter reads one — E7's two signals included."""
    recorder = _TimeoutRecorder()
    adapter = _SpawningProbe(Invocation(argv=("x",), cwd=Path(), env={}), inspect=True, recorder=recorder)
    _spawned(adapter, FakeRunner(recorder))
    assert adapter.inspected == (recorder.pid, None, False)


def test_a_probe_wait_is_clamped_to_what_is_left_of_the_budget_not_to_the_whole_of_it():
    """C-1014: a per-call cap bounds nothing — `while proc.wait(30.0) is None:` blocks forever under one.

    Under a per-call cap every clamped wait is exactly `PROBE_BUDGET_S`; under a
    deadline each is strictly smaller than the last, because the clock moved.
    """
    recorder = _TimeoutRecorder(running_for=3)
    adapter = _SpawningProbe(Invocation(argv=("x",), cwd=Path(), env={}), wait_for=None, waits=3, recorder=recorder)
    _spawned(adapter, FakeRunner(recorder))
    clamped = [seen for seen in recorder.waits[:3] if seen is not None]
    assert len(clamped) == 3, recorder.waits
    assert all(seen < PROBE_BUDGET_S for seen in clamped), clamped
    assert clamped == sorted(clamped, reverse=True), clamped


def test_every_probe_child_is_attempted_even_after_one_reap_fails():
    """C-1014: abandoning the rest of the list on the first `OSError` IS the failure being prevented."""
    first, second = _FailingReap(running_for=1), _TimeoutRecorder(running_for=1)
    adapter = _SpawningProbe(Invocation(argv=("x",), cwd=Path(), env={}), children=2)
    with pytest.raises(PermissionError):
        _spawned(adapter, FakeRunner(first, second))
    assert len(second.waits) == 2, "the second child was never reaped"


def test_a_sandbox_probe_child_is_reaped_too(tmp_path):
    """C-1040, C-1014: `sandbox_probe` is adapter code that spawns, and `workspace()` removes `ws.path`."""
    recorder = _TimeoutRecorder(running_for=1)
    adapter = _SpawningSandbox(Invocation(argv=("x",), cwd=tmp_path, env={}))
    _authorized(tmp_path, adapter, runner=FakeRunner(recorder))
    assert len(recorder.waits) == 2, "the sandbox probe's child was not reaped"


def test_a_sandbox_probe_child_is_not_clamped_to_the_probe_budget(tmp_path):
    """C-1040: the sandbox probe is a full review-shaped model turn — a 60 s clamp fails it, not bounds it."""
    recorder = _TimeoutRecorder(running_for=1)
    adapter = _SpawningSandbox(Invocation(argv=("x",), cwd=tmp_path, env={}), wait_for=3600.0)
    _authorized(tmp_path, adapter, runner=FakeRunner(recorder))
    assert recorder.waits[0] == 3600.0


def test_a_probe_the_supervisor_had_to_end_never_reports_a_clean_exit(tmp_path):
    """C-1014: `supervise` reassigns `exit_code` from the post-SIGTERM reap, so a trapped
    signal arrives as `exit_code=0, reason=TIMED_OUT` — and every adapter reads only the
    status. A real child, because the reassignment only happens on a real kill ladder.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    sleeper = bindir / "sleeper"
    sleeper.write_text("#!/bin/sh\nprintf 'partial banner\\n'\nsleep 60\n", encoding="utf-8")
    sleeper.chmod(0o755)
    probed, lines = probe_run(
        SubprocessRunner(),
        Launcher(binary="sleeper"),
        # The system PATH too: the script itself calls `sleep`, and the child
        # inherits exactly this environment.
        {"PATH": os.pathsep.join((str(bindir), os.defpath))},
        tmp_path,
        timeout_s=1,
    )
    assert probed.reason is FailureReason.TIMED_OUT
    assert probed.exit_code is None, "a timed-out probe read as a clean exit on a partial banner"
    assert lines == ("partial banner\n",)


# `argv_prompt`: the cap that keeps the positional-message deviation honest — C-1028


def test_a_prompt_one_byte_under_the_argv_limit_is_returned_unchanged():
    """C-1028: the cap refuses AT the limit and nothing below it — the boundary is not off by one."""
    text = "a" * (PROMPT_ARGV_LIMIT - 1)
    assert argv_prompt(text) == text


def test_a_prompt_of_exactly_the_argv_limit_is_refused():
    """The kernel counts the terminating NUL, so exactly `MAX_ARG_STRLEN` bytes is `E2BIG`.

    `PROMPT_ARGV_LIMIT` IS Linux's `MAX_ARG_STRLEN` (32 pages), and `copy_strings`
    refuses when `strnlen_user` — which includes the NUL — exceeds it. A prompt of
    exactly that many bytes therefore dies in `execve` rather than in this
    refusal, and a silent `E2BIG` is what C-1028 exists to keep out of the flow.
    """
    with pytest.raises(ConfigError):
        argv_prompt("a" * PROMPT_ARGV_LIMIT)


def test_a_prompt_over_the_argv_limit_is_refused_naming_both_sizes():
    """C-1028: a silent `E2BIG` would drop the anti-injection framing at the end of the prompt."""
    with pytest.raises(ConfigError) as exc:
        argv_prompt("a" * (PROMPT_ARGV_LIMIT + 1))
    message = str(exc.value)
    assert str(PROMPT_ARGV_LIMIT) in message
    assert str(PROMPT_ARGV_LIMIT + 1) in message


def test_the_argv_limit_is_measured_in_bytes_and_not_characters():
    """C-1028: the cap is in BYTES and `review_prompt` returns a `str`.

    A prompt of `PROMPT_ARGV_LIMIT` characters whose last one is multi-byte
    straddles the boundary: a character-count check passes it and the kernel
    does not.
    """
    straddling = "a" * (PROMPT_ARGV_LIMIT - 1) + "é"
    assert len(straddling) == PROMPT_ARGV_LIMIT
    with pytest.raises(ConfigError):
        argv_prompt(straddling)


# `indeterminate`: the C-1012 route an adapter takes when `classify` declines


def test_indeterminate_stamps_the_unrecorded_shape_and_can_never_approve():
    """C-1012: step 6.3's other half — nothing in core turned a `None` classify into a result."""
    parsed = indeterminate("raw harness output", "UnknownError")
    assert parsed.status == "indeterminate"
    assert parsed.reason is FailureReason.MALFORMED_OUTPUT
    assert parsed.verdict is None
    assert parsed.findings == ()
    assert parsed.summary == ""
    assert parsed.raw == "raw harness output"
    assert "UnknownError" in (parsed.detail or "")


@pytest.mark.parametrize("adapter", STUBS, ids=[stub.name for stub in STUBS])
def test_every_stub_classify_declines_on_an_unrecorded_shape(adapter):
    """C-1012: `None` where no recorded fixture proves the cell — never a substring guess."""
    assert adapter.classify({"type": "UnknownError", "message": "something went wrong"}) is None


# `HarnessInfo.capabilities`: the one collection that was not copied — C-1013


def test_a_mutable_capability_set_is_copied_at_construction():
    """C-1013: a frozen dataclass holding a caller's live `set` promises an immutability it lacks."""
    live = {Capability.ENUMERABLE_DENY}
    info = info_for("stub", capabilities=cast("frozenset[Capability]", live))
    live.add(Capability.STRUCTURED_OUTPUT)
    assert info.capabilities == frozenset({Capability.ENUMERABLE_DENY})


# `probe_digest`: the section markers are arity-separated — C-1025


def test_the_probe_digest_separates_a_section_marker_from_a_word_that_spells_one(tmp_path):
    """C-1025: length-prefixing is injective within a word, not across sections.

    The markers are unescaped words in the same alphabet, so an environment
    carrying `env-evidence=env` with no argv evidence digested identically to
    argv evidence spelling those two words with no environment. The arity beside
    each marker fixes where the next marker falls.
    """
    kwargs = _digest_kwargs(tmp_path)
    as_environment = probe_digest(**{**kwargs, "plan": _plan(), "env": {"env-evidence": "env"}})
    as_evidence = probe_digest(**{**kwargs, "plan": _plan(argv_evidence=("env-evidence", "env")), "env": {}})
    assert as_environment != as_evidence


# `config_read_paths`: the documented exception is the only one — E3


@pytest.mark.parametrize("entry", ["$", "${}", "${HOME"], ids=["bare-dollar", "empty-braces", "unclosed-brace"])
def test_config_read_paths_maps_a_malformed_template_to_the_documented_error(entry):
    """E3: `string.Template` raises its own `ValueError`, and the docstring promised only this one."""
    with pytest.raises(ValueError, match="CONFIG_READS"):
        config_read_paths((entry,), {"HOME": "/home/u"})


# The shipped security literals: emptying one must not leave the suite green


def test_the_denied_flag_set_carries_the_flags_it_exists_for():
    """C-1023: the parametrized tests degrade to a SKIP on an empty set, proving nothing."""
    assert {
        "-c",
        "--config",
        "--dangerously-skip-permissions",
        "--dangerously-bypass-approvals-and-sandbox",
    } <= DENIED_FLAGS


def test_the_never_allowlistable_set_carries_the_config_flags_it_exists_for():
    """C-1023: `isdisjoint` against an empty set is vacuously true for every adapter."""
    assert {"--settings", "--mcp-config", "--tools"} <= NEVER_ALLOWLISTABLE


def test_the_never_emitted_set_is_not_empty_and_carries_a_containment_lifting_flag():
    """C-1023: a subset assertion against an empty set is vacuously true."""
    assert NEVER_EMITTED
    assert "--dangerously-skip-permissions" in NEVER_EMITTED


def test_the_second_spelling_of_the_permission_lift_is_refused_and_never_emitted():
    """C-1023, E52: `--permission-mode bypassPermissions` is `--dangerously-skip-permissions`, renamed.

    Four records said this flag was in `NEVER_EMITTED`; it was in neither
    refusal set. Its only home was `NEVER_ALLOWLISTABLE`, which this module
    documents as "Not a runtime check" — so the whole of its refusal was
    refusal 2 answering an empty allowlist, and nothing at all stopped nox
    EMITTING it.

    Reachable rather than theoretical: SD § 6.1 prescribes
    `--permission-mode dontAsk`, and `adapters/claude.py` deviated from that on
    evidence — at 2.1.260 no value of the flag is narrower than the default it
    already gets, so `acceptEdits`, `auto`, `bypassPermissions` and `dontAsk`
    each widen what the `ContainmentPlan` claims while `plan` changes the output
    shape. An author who reads the design and not the deviation re-adds it, and
    this is what refuses it then. The ban costs no adapter anything, which is
    what separates it from `-c`: nox emits `--permission-prompts none` in its
    place and needs this word for nothing.
    """
    assert "--permission-mode" in DENIED_FLAGS
    assert "--permission-mode" in NEVER_EMITTED
    with pytest.raises(ConfigError) as exc:
        police_passthrough("claude", ["--permission-mode", "dontAsk"], ["-p"])
    # Refusal 1, not refusal 2: unconditional, and no longer contingent on
    # `PASSTHROUGH_ALLOW["claude"]` staying empty.
    assert str(exc.value) == "passthrough: --permission-mode is refused unconditionally (C-1023)"


def test_the_never_set_environment_names_are_not_empty_and_carry_a_loader_hijack():
    """C-1008: the same vacuity, for the newest of the four literals."""
    assert NEVER_SET
    assert "LD_PRELOAD" in NEVER_SET


def test_no_shipped_adapter_imports_a_module_it_must_reach_through_core():
    """C-1024, C-1028: `render` hand-called is `structured_output` guessed and `neutralized_paths` dropped.

    `review_prompt` is the enforced route, and enforcement is this scan: an
    adapter importing `nox.prompt` could set the two arguments itself, which is
    exactly what the wrapper exists to stop it forgetting.
    """
    forbidden = {"nox.prompt"}
    files = sorted(p for p in _repo_files() if p.is_relative_to(ADAPTERS_DIR) and p.suffix == ".py" and p.is_file())
    assert ADAPTERS_DIR / "__init__.py" in files, f"the adapters package was not enumerated: {files}"
    hits = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            hits += [(path.name, module) for module in modules if module in forbidden]
    assert hits == []


def test_review_prompt_delivers_the_workspace_diff(tmp_path):
    """C-1028: the prompt is how the change reaches three of the four shipped harnesses.

    `<scratch>/review.diff` was written and never read by any adapter, so a
    reviewer with no shell — claude's allowlist is `Read`, `Grep`, `Glob` — had no
    route to the change at all. `review_prompt` is the one place that can fix it
    for every adapter at once, which is why the assertion is here and not in four
    adapter suites.
    """
    ws = _workspace(tmp_path)
    _, text = review_prompt(ws, info_for("stub"), None)
    assert WS_DIFF.rstrip("\n") in text


def test_review_prompt_reads_the_diff_off_the_workspace_not_off_the_scratch_file(tmp_path):
    """`sandbox_probe` spawns a harness into the workspace BEFORE `prepare` runs.

    `write_nofollow` states the scratch directory is unprotected once a harness
    has run, so a `prepare` that re-read `<scratch>/review.diff` would render
    whatever survived that spawn. The workspace decoded the bytes when it produced
    them, which is before any harness existed; a scratch file that disagrees must
    not reach the prompt.
    """
    ws = _workspace(tmp_path)
    ws.diff_path.write_text("diff --git a/swapped b/swapped\n+planted\n", encoding="utf-8")
    _, text = review_prompt(ws, info_for("stub"), None)
    assert "planted" not in text
    assert WS_DIFF.rstrip("\n") in text


# ── The stdin prompt channel: authorize is what polices it — C-1028, E29 ─────


def test_authorize_carries_a_scratch_stdin_path_onto_the_invocation(tmp_path):
    """C-1028: the file `review_prompt` already wrote is the second channel — nothing new is written."""
    adapter = HarnessStub()
    bindir = tmp_path / "bin"
    _executable(bindir, adapter.BINARY)
    ws = _workspace(tmp_path, env={"PATH": str(bindir)})
    prompt = ws.scratch / PROMPT_FILENAME
    prompt.write_text("rendered", encoding="utf-8")
    launch = Launch(argv=("-p", *TOOL_EVIDENCE), stdin_path=prompt)

    inv, _ = _authorized(tmp_path, adapter, launch=launch, ws=ws)

    assert inv.stdin_path == prompt


def test_a_launch_declaring_no_stdin_path_leaves_the_invocation_at_devnull(tmp_path):
    """C-1009: the argv harnesses declare nothing, so DEVNULL stays the default rather than an opt-out."""
    inv, _ = _authorized(tmp_path, HarnessStub())
    assert inv.stdin_path is None


@pytest.mark.parametrize(
    "escape",
    [
        "..",
        "../..",
        "nested",
    ],
)
def test_authorize_refuses_a_stdin_path_that_is_not_directly_in_the_scratch_directory(tmp_path, escape):
    """C-1028: an adapter may not choose which file nox opens and hands the harness as its prompt.

    Unpoliced, `stdin_path` is an arbitrary-file-read primitive pointed at the
    model: the adapter names `~/.codex/auth.json`, nox opens it, and the harness
    is asked to review its contents. The parent directory is the whole test —
    `spawn`'s `O_NOFOLLOW` covers the one shape this cannot, a symlink planted
    at the final component by a harness that already ran in this workspace.
    """
    adapter = HarnessStub()
    bindir = tmp_path / "bin"
    _executable(bindir, adapter.BINARY)
    ws = _workspace(tmp_path, env={"PATH": str(bindir)})
    launch = Launch(argv=("-p", *TOOL_EVIDENCE), stdin_path=ws.scratch / escape / PROMPT_FILENAME)

    with pytest.raises(ConfigError) as exc:
        _authorized(tmp_path, adapter, launch=launch, ws=ws)

    assert "stdin" in str(exc.value)


def test_the_argv_limit_refusal_names_the_channel_and_the_harnesses_that_do_not_have_it(tmp_path):
    """C-1028, E29: the limit is a property of the argv CHANNEL, not of nox — the message must say so.

    An operator reading "nox refused" looks for a nox setting to raise. There is
    none: `PROMPT_ARGV_LIMIT` is Linux's `MAX_ARG_STRLEN`, so the honest advice
    is to review a narrower base *or* run a harness whose prompt rides stdin.
    """
    with pytest.raises(ConfigError) as exc:
        argv_prompt("a" * PROMPT_ARGV_LIMIT)

    message = str(exc.value)
    assert "argv" in message
    assert "claude" in message and "codex" in message
    assert "stdin" in message


# ---------------------------------------------------------------------------
# WP13: the argv channel's other unrepresentable byte, the C-1036 family widen,
# C-1025 rule 1's killing case, the launcher-opaque probe cache, and the
# extension point being true — H2, H5, H8, CG1, H12
# ---------------------------------------------------------------------------


def test_the_embedded_nul_hazard_is_real_and_popen_raises_a_valueerror(tmp_path):
    """H2: the hazard, verified in this Python rather than described.

    `api._spawn` catches `OSError` and maps it to `ABSENT`. A NUL inside an
    argv word does not raise one: `Popen` refuses before it ever reaches
    `execve`, with a `ValueError` that is not an `OSError` at all — so it goes
    past `_spawn`'s handler, past every `NoxError` mapping, and lands on
    `review()`'s catch-all as `indeterminate`/`MALFORMED_OUTPUT`. That row is
    the one a consumer degrades to a graceful skip, which means a repository
    that commits one NUL byte silently denies its own review and blames the
    reviewer for it.
    """
    with pytest.raises(ValueError) as exc:
        subprocess.Popen([str(tmp_path / "no-such-binary"), "a\x00b"])

    assert not isinstance(exc.value, OSError), "`api._spawn` catches `OSError`, and this is not one"


def test_a_prompt_carrying_a_nul_byte_is_refused_by_the_argv_channel():
    """H2, C-1028: `git` diffs a blob with a NUL as text and `Workspace.diff` keeps the byte.

    `errors="replace"` repairs invalid UTF-8; U+0000 is perfectly valid UTF-8
    and survives untouched into the prompt. Refusing it here is the honest
    answer — the alternative is a `ValueError` out of `Popen` that reads as the
    reviewer malfunctioning.
    """
    with pytest.raises(ConfigError) as exc:
        argv_prompt("diff --git a/blob.bin b/blob.bin\n+\x00\n")

    message = str(exc.value)
    assert "NUL" in message
    assert "byte 34" in message, "the offset turns 'somewhere in your branch' into a place to look"


def test_the_nul_offset_is_a_byte_offset_on_a_prompt_that_is_not_ascii():
    """E40, C-1028: the message says "byte", so the number has to be one.

    `str.find` answers in CODE POINTS. On ASCII the two agree, which is the
    whole of why the coverage above passed while the number was wrong on every
    real diff — a prompt carrying one accented word, one em dash or one box
    character is already off, and the message sends the operator to that offset
    in a file on the branch. Ten two-byte characters is the smallest case where
    the two readings differ by more than rounding: character 10, byte 20.
    """
    with pytest.raises(ConfigError) as exc:
        argv_prompt("é" * 10 + "\x00")

    assert "byte 20" in str(exc.value)


def test_the_nul_refusal_fires_below_the_size_limit():
    """H2: the two argv refusals are independent — a one-byte NUL prompt is refused on its own.

    Ordering matters because a NUL-carrying prompt is usually also a large one,
    and a size check that answered first would name the wrong cause and send the
    operator to narrow their base for a byte no base narrows away.
    """
    with pytest.raises(ConfigError) as exc:
        argv_prompt("\x00")

    assert str(PROMPT_ARGV_LIMIT) not in str(exc.value)


def test_a_prompt_of_printable_text_is_returned_unchanged():
    """H2: the positive control — the NUL guard refuses one byte value and nothing else."""
    text = "diff --git a/b b/b\n+\ttab, newline and é all ride argv fine\n"
    assert argv_prompt(text) == text


# C-1036: the shipped tables resolve no member of the measured pair — H5


SHIPPED_WRITER = "claude-opus-5"
"""`claude.MODELS["deep-reasoning"]`, spelled out rather than imported.

The point of these four tests is that the shipped literals and the C-1036 table
agree, and reading both off the same import would assert only that a mapping
lookup works. `claude-opus-4-7` — the id the paper measured — is resolved by no
shipped table, which is why `ASYMMETRY_NEGATIVE` was inert on all four harnesses
before the family widen.
"""

SHIPPED_REVIEWER = "gpt-5.6-luna"
"""`codex.MODELS` and `copilot.MODELS`, both classes. The measured id was `gpt-5.5`."""

OPENCODE_REVIEWER = "github-copilot/gpt-5.6-luna"
"""`opencode.MODELS["fast-balanced"]` — the one v1 spelling carrying a `provider/` prefix."""


def test_the_warning_fires_for_the_models_the_shipped_tables_actually_resolve():
    """C-1036, H5: an entry matching no resolvable literal is a warning that can never fire.

    `ASYMMETRY_NEGATIVE` shipped `("claude-opus-4-7", "gpt-5.5")` and every
    shipped `MODELS` table resolves neither, so the C-1036 warning was inert on
    all four harnesses — the exact failure `asymmetry_warning`'s own docstring
    calls worse than one that never fires.
    """
    assert asymmetry_warning(SHIPPED_WRITER, SHIPPED_REVIEWER) is not None


def test_the_warning_fires_through_opencodes_provider_prefixed_spelling():
    """C-1036: `_bare_model` strips `provider/`, so the family prefix must match after the strip."""
    assert asymmetry_warning(SHIPPED_WRITER, OPENCODE_REVIEWER) is not None


def test_the_reversed_shipped_pair_still_warns_nothing():
    """C-1036: the measured effect is one-directional, and widening to families must not lose that."""
    assert asymmetry_warning(OPENCODE_REVIEWER, SHIPPED_WRITER) is None


def test_the_asymmetry_docstring_names_exactly_the_literals_the_four_tables_resolve():
    """C-1036: the sentence the family argument rests on, derived rather than transcribed.

    `ASYMMETRY_NEGATIVE`'s docstring lists what the shipped tables resolve, and
    the argument that follows turns on whether a family prefix survives a
    `provider/` prefix — so the bare/prefixed distinction is the one detail in
    that list that has to be right. It was not: `gpt-5.6-sol` was listed bare,
    a spelling no table carries (opencode's is `github-copilot/gpt-5.6-sol`),
    which reads as evidence that a bare id IS resolvable and quietly undercuts
    the paragraph it is the premise of.

    Read off the four tables and off the source text, so the next model bump
    fails here rather than leaving the prose behind. A `str` entry and a
    `ModelSpecT` one are the same claim to `asymmetry_warning`, which is why
    `ModelSpecT.of` normalizes before the comparison.
    """
    resolved = {ModelSpecT.of(spec).model for name in ADAPTERS for spec in load(name).MODELS.values()}
    assert len(resolved) >= 4, f"an under-collected table would pass vacuously: {resolved}"

    source = (SRC / "harness.py").read_text(encoding="utf-8")
    listed = re.search(r"the tables resolve\s+(.*?), so ", source, re.S)
    assert listed, "the docstring no longer names what the tables resolve"

    assert set(re.findall(r"`([^`]+)`", listed.group(1))) == resolved


def test_the_warning_names_the_measured_pair_and_calls_the_generalization_untested():
    """C-1036, C-1035, H5: the table now matches a FAMILY, and the text may not overstate that.

    The paper measured `claude-opus-4-7` written / `gpt-5.5` reviewing. Matching
    `claude-opus-5` → `gpt-5.6-luna` and reporting "a measured negative
    interaction" would put a claim in `Review.warnings` that no measurement
    supports. The honest form names the citation, names the pair that WAS
    measured, and says the family generalization is untested — so an operator
    can weigh the caveat rather than take it as data.
    """
    warning = asymmetry_warning(SHIPPED_WRITER, SHIPPED_REVIEWER)

    assert warning is not None
    assert ASYMMETRY_CITATION in warning
    assert all(model in warning for model in ASYMMETRY_MEASURED), "the pair that was measured is not named"
    assert "untested" in warning.lower()


# C-1025 rule 1: the argv that never names the evidence flag at all — H8


def test_an_argv_omitting_the_evidence_flag_entirely_does_not_corroborate():
    """C-1025 rule 1's killing case: rules 2, 3 and 4 are all vacuous here.

    With the run absent there is nothing to terminate (rule 2 quantifies over an
    empty set), the evidence carries no `=` so there is no key to re-assign
    (rule 3), and no argv word names `--tools` so nothing re-specifies it
    (rule 4). Deleting `if not runs: return False` therefore corroborates this
    plan, and the harness — handed three bare positionals and no `--tools` —
    runs with its DEFAULT tool set: full write and shell access under a plan
    claiming both were removed.

    `DisagreeingStub` cannot catch that. Its run is present and rule 2 refuses
    it, so rule 1 was the one rule in this function with no test that fails
    when it is deleted.
    """
    inv = _inv("claude", "-p", *TOOL_EVIDENCE[1:])
    derived = _derived(inv, _plan(argv_evidence=TOOL_EVIDENCE))
    assert (derived.write_enforcement, derived.network_enforcement) == (None, None)


def test_an_adapter_that_omits_its_evidence_flag_never_receives_an_invocation(tmp_path):
    """C-1025, H8: rule 1 at the gate, not only at the derivation — the launch is refused."""
    adapter = OmittingStub()
    with pytest.raises(UnsupportedCapability):
        _authorized(tmp_path, adapter)


# CG1: a launcher hides the harness the digest is meant to key on


def test_a_probe_pass_behind_a_launcher_is_never_reused_by_a_later_launch(tmp_path):
    """CG1, C-1025: `probe_digest` hashes the LAUNCHER's bytes, never the harness it resolves.

    Under `ocx package exec pkg -- codex`, `launch_argv` resolves the prefix
    head, so `executable` and its content hash are `ocx` — stable across every
    in-place change to the wrapped harness. `CONFIG_READS` and the prefix words
    move for that shape; the harness binary's own bytes do not. So a passing
    C-1040 sandbox probe recorded under one wrapped target authorizes a launch
    of a different one at the `os` level, which is the one level whose whole
    price is that probe.

    `api._PROBE_CACHE` is module-level *by design* — its docstring makes reuse
    across reviews the point — so this is reachable rather than theoretical for
    the one shipped adapter that claims `os`, `codex`, whose `launcher` is an
    ordinary `[harness.codex]` config key.
    """
    adapter = OsStub(sandbox_passes=True)
    _executable(tmp_path / "bin", "ocx")
    launcher = Launcher(binary="wrapped-harness", prefix=("ocx", "package", "exec", "pkg", "--"))
    cache = ProbeCache()

    _authorized(tmp_path, adapter, launcher=launcher, cache=cache)
    _authorized(tmp_path, adapter, launcher=launcher, cache=cache)

    assert adapter.sandbox_calls == 2, "the second launch reused a probe that cannot speak for its harness"


def test_a_probe_pass_behind_a_launcher_still_authorizes_its_own_launch(tmp_path):
    """CG1: refusing the CACHE is not refusing the probe — a wrapped harness still reaches `os`."""
    adapter = OsStub(sandbox_passes=True)
    _executable(tmp_path / "bin", "ocx")
    launcher = Launcher(binary="wrapped-harness", prefix=("ocx", "package", "exec", "pkg", "--"))

    _, derived = _authorized(tmp_path, adapter, launcher=launcher)

    assert (derived.write_enforcement, derived.network_enforcement) == ("os", "os")


def test_a_failing_probe_behind_a_launcher_is_refused_even_after_an_earlier_pass(tmp_path):
    """CG1: the sharp end — a stale PASS must not survive the probe that now fails.

    Evicting nothing and merely re-probing would leave the earlier digest in the
    cache, and `derive_containment` reads `proven` off the cache rather than off
    the probe just run. The wrapped target that stopped sandboxing would then be
    stamped `os` on the strength of the launch before it.
    """
    passing = OsStub(sandbox_passes=True)
    failing = OsStub(sandbox_passes=False)
    _executable(tmp_path / "bin", "ocx")
    launcher = Launcher(binary="wrapped-harness", prefix=("ocx", "package", "exec", "pkg", "--"))
    cache = ProbeCache()

    _authorized(tmp_path, passing, launcher=launcher, cache=cache)

    with pytest.raises(UnsupportedCapability):
        _authorized(tmp_path, failing, launcher=launcher, cache=cache)


# H12: the extension point the docstrings promise, exercised by a fifth adapter


def test_a_harness_with_no_allowlist_entry_gets_an_empty_allowlist_not_a_refused_review():
    """C-1023, H12: an absent entry means "refuse everything", which is the documented safe default.

    `.get(harness)` answering `None` and raising made the opposite true: every
    `prepare` calls this unconditionally, so a fifth adapter with no
    `PASSTHROUGH_ALLOW` entry hard-failed every review it could ever run — while
    `Adapter`'s own docstring said the entry defaults to empty and needs no core
    edit. The unknown-key refusal belongs to `adapters.load`, which owns the
    registry and is where the repository-supplied `[review] harness` is checked
    against it (C-1035(1)).
    """
    assert FifthStub.name not in PASSTHROUGH_ALLOW

    assert police_passthrough(FifthStub.name, [], list(TOOL_EVIDENCE)) == TOOL_EVIDENCE
    with pytest.raises(ConfigError) as exc:
        police_passthrough(FifthStub.name, ["--verbose=yes"], [])
    # Refusal 2 by name, in the `--flag=value` spelling refusal 5 cannot reach.
    # A substring match on the flag also passed refusal 5's "expects a value",
    # so a permissive default kept this green while every unregistered harness
    # passed `--verbose` straight through.
    assert str(exc.value) == f"passthrough: --verbose is not allowed for {FifthStub.name} (C-1023)"


def test_a_fifth_registered_adapter_runs_the_whole_launch_flow_with_no_core_edit(tmp_path, monkeypatch):
    """C-1024, H12: the claim in `ADAPTERS`' and `Adapter`'s docstrings, executed rather than asserted.

    One registry entry and nothing else — no `PASSTHROUGH_ALLOW` key, no core
    literal naming `fifthstub`. The walk is the shipped call order (SD § 3):
    `load` → `probe` → `containment_plan` → `prepare` → `authorize`, which is
    every core function a review crosses before `Runner.spawn`. A hard-fail
    anywhere in it is a fifth adapter that cannot review, whatever the docstrings
    say.
    """
    monkeypatch.setattr(
        adapters_module,
        "ADAPTERS",
        MappingProxyType({**ADAPTERS, FifthStub.name: "tests.unit.stubs:FifthStub"}),
    )
    adapter = load(FifthStub.name)
    bindir = tmp_path / "bin"
    _executable(bindir, adapter.BINARY)
    env = {"PATH": str(bindir), "HOME": str(tmp_path)}
    runner = FakeRunner()

    info = probe_harness(adapter, runner, config(), env)
    ws = _workspace(tmp_path, env=env)
    plan = adapter.containment_plan(config(), info)
    launch = adapter.prepare(ws, info, config(), None)
    inv, derived = authorize(adapter, launch, ws, info, plan, ProbeCache(), runner)

    assert (derived.write_enforcement, derived.network_enforcement) == ("harness", "harness")
    assert inv.stdin_path == ws.scratch / PROMPT_FILENAME
    assert inv.stdin_path is not None  # narrows `Invocation.stdin_path` from `Path | None`
    assert WS_DIFF in inv.stdin_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# WP15: the outcome-order row all four adapters share — C-1012, SD § 4.3, § 7.1
# ---------------------------------------------------------------------------


ESTABLISHED: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "claude": (json.dumps({"type": "result", "subtype": "success", "is_error": True, "api_error_status": 401}),),
        "codex": (json.dumps({"type": "error", "message": "the model refused this request"}),),
        "opencode": (json.dumps({"type": "error", "error": {"name": "UnknownError"}}),),
        "copilot": (
            json.dumps(
                {
                    "type": "assistant.message",
                    "data": {
                        "messageId": "m",
                        "content": '```json\n{"verdict":"approve","summary":"s","findings":[],"next_steps":[]}\n```',
                        "phase": "final_answer",
                    },
                }
            ),
            json.dumps({"type": "result", "sessionId": "s", "exitCode": 0, "usage": {}}),
        ),
    }
)
"""One stream per adapter that establishes an outcome in the harness's OWN voice.

Three of them use the adapter's error channel, because that is the read the row
is about. **Copilot uses a final answer instead, and the asymmetry is honest
rather than a shortcut**: `CopilotAdapter.CLASSIFY` is empty and 1.0.82 emits no
error event at all, so an error stream here would be a shape its fixtures do not
record — an invented row proves nothing. Its established outcome is therefore the
one it really has, a `final_answer` carrying a fenced `WIRE_SCHEMA` object with
the terminal `result` line behind it.

Hand-written from each adapter's recorded shape, never derived from the code
under test, so an adapter that changed which events it reads fails here.
"""


def _heartbeat() -> Heartbeat:
    """The progress evidence `parse` is handed. Every adapter ignores it; none may require it."""
    return Heartbeat(kind=Liveness.SEMANTIC, last_activity_at=0.0, last_byte_at=0.0)


@pytest.mark.parametrize("harness", sorted(ADAPTERS))
def test_no_adapter_lets_the_exit_status_overrule_a_stream_that_established_an_outcome(harness):
    """C-1012, SD § 4.3: `exit_code` "is recorded, and gates NOTHING".

    The table nothing pinned. `codex.parse` read `reason_for_exit` ABOVE its
    error table while `claude` and `opencode` read the harness's own signal
    first, so one evidence shape — an error event on a run that exited 143 —
    resolved as nox's own stop on codex and as the reported error everywhere
    else. Each adapter's own tests cover its own order; only a table across all
    four can catch the next one to drift.

    Asserted as an EQUALITY between the kill status and an ordinary failure
    status, because that is the property: a stream that spoke resolves the same
    way whatever the process it rode on exited with. The `KILLED` negative is
    the same claim named after the defect it closes.
    """
    stream = ESTABLISHED[harness]
    adapter = load(harness)

    killed = adapter.parse(stream, SIGTERM_EXIT, _heartbeat())

    assert killed == adapter.parse(stream, 1, _heartbeat())
    assert killed.reason is not FailureReason.KILLED


@pytest.mark.parametrize("harness", sorted(ADAPTERS))
def test_every_adapter_reads_sigterm_as_its_own_stop_when_the_stream_established_nothing(harness):
    """C-1012, SD § 7.1: exit 143 has exactly one row, and this is the territory it owns.

    The other half of the same table. Where the stream said nothing at all, the
    exit status is the only evidence the run left behind, and it is labelled
    "nox stopped this" rather than flattened into `MALFORMED_OUTPUT` — "the
    harness produced garbage" is a different and untrue account, and it is the
    one a consumer would degrade on.
    """
    parsed = load(harness).parse((), SIGTERM_EXIT, _heartbeat())

    assert parsed.status == "error"
    assert parsed.reason is FailureReason.KILLED
    assert parsed.verdict is None
