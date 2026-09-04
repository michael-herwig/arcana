"""The prompt channel is a property of the HARNESS, not of nox (C-1028, E29).

`PROMPT_ARGV_LIMIT` is Linux's `MAX_ARG_STRLEN` — the kernel's ceiling on a
single argv word. It was applied to all four adapters, which made a whole-branch
review refuse at 128 KiB everywhere: the prompt carries the diff, real
work-package commits here measure 38-77 KB, and the branch this was found on
diffs at 2.8 MB. That is nox's primary use case refused on three harnesses that
had no kernel reason to refuse it.

Two of the four read their prompt from stdin. Established live on 2026-09-03
rather than inferred from a document:

| harness | channel | evidence |
|---|---|---|
| `claude` | stdin | `echo … \\| claude --print --tools Read Grep Glob --` → exit 0 |
| `codex` | stdin | `--help` for `[PROMPT]` documents `-` as "read from stdin"; run live behind the real flag set |
| `copilot` | argv | 1.0.82 `--help`: `-p <text>`, no prompt file, no stdin form |
| `opencode` | argv | `run [message..]`, no prompt-file flag |

This module owns the two assertions that belong to no single adapter: that the
split is what the code actually does, and that `STDIN_PROMPT_HARNESSES` — the
literal the refusal message advises an operator from — stays true.
"""

from __future__ import annotations

import pytest

from nox.adapters import ADAPTERS
from nox.adapters.claude import ClaudeAdapter
from nox.adapters.codex import CodexAdapter
from nox.adapters.copilot import CopilotAdapter
from nox.adapters.opencode import OpenCodeAdapter
from nox.config import ConfigError
from nox.harness import PROMPT_ARGV_LIMIT, STDIN_PROMPT_HARNESSES
from nox.workspace import Workspace
from tests.unit.stubs import config, info_for

STDIN_ADAPTERS = (ClaudeAdapter, CodexAdapter)
"""The harnesses whose prompt rides stdin — spelled out, not read off the code."""

ARGV_ADAPTERS = (CopilotAdapter, OpenCodeAdapter)
"""The harnesses whose prompt rides argv, and which `MAX_ARG_STRLEN` therefore binds."""


def _workspace(tmp_path, diff: str) -> Workspace:
    """A workspace carrying `diff` — the only field this module varies."""
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
        diff=diff,
        env={"PATH": "/nonexistent-bin"},
        neutralized=(),
        neutralized_total=0,
        filtered=(),
        filtered_total=0,
        filtered_changed=(),
        filtered_changed_total=0,
        omitted=(),
        omitted_total=0,
        omitted_ignored=0,
        scope="code-diff",
    )


def _prepare(adapter_type, tmp_path, diff: str):
    """One `prepare`, in a workspace of its own — `prompt.md` is written `O_EXCL`."""
    adapter = adapter_type()
    ws = _workspace(tmp_path / adapter.name, diff)
    return ws, adapter.prepare(ws, info_for(adapter.name), config(), None)


def _oversized() -> str:
    """A diff comfortably past `MAX_ARG_STRLEN`, so no framing text decides the outcome."""
    return "".join(f"+{'a' * 78}\n" for _ in range(PROMPT_ARGV_LIMIT * 2 // 80))


@pytest.mark.parametrize("adapter_type", ARGV_ADAPTERS, ids=lambda t: t().name)
def test_a_diff_over_the_argv_limit_refuses_on_an_argv_channel_harness(adapter_type, tmp_path):
    """C-1028: no second channel exists on these two, so a refusal is the only honest answer.

    Loud, never a trim: a reviewer handed a silently shortened diff reports on a
    change nobody made, and the anti-injection framing lives at the END of the
    prompt, which is exactly what an `execve` truncation would cut.
    """
    with pytest.raises(ConfigError) as exc:
        _prepare(adapter_type, tmp_path, _oversized())

    message = str(exc.value)
    assert str(PROMPT_ARGV_LIMIT) in message
    assert "argv" in message, "the message must name the CHANNEL that refused, not just nox"
    assert STDIN_PROMPT_HARNESSES in message, "and it must name the harnesses that would not have"


@pytest.mark.parametrize("adapter_type", STDIN_ADAPTERS, ids=lambda t: t().name)
def test_the_same_diff_prepares_on_a_stdin_channel_harness(adapter_type, tmp_path):
    """E29, the whole finding in one assertion: the same diff that refuses above reviews here.

    Three properties together, because any one alone passes a launch that is
    still broken: the prompt is delivered, it is delivered VERBATIM (C-1028
    forbids trimming, and a truncating implementation would satisfy a mere
    "prepare did not raise"), and no argv word is anywhere near the kernel's
    ceiling — a launch that put the prompt on both channels would still `E2BIG`.
    """
    diff = _oversized()

    ws, launch = _prepare(adapter_type, tmp_path, diff)

    assert launch.stdin_path == ws.scratch / "prompt.md"
    assert diff in launch.stdin_path.read_text(encoding="utf-8")
    assert max(len(word.encode("utf-8")) for word in launch.argv) < PROMPT_ARGV_LIMIT


def test_the_harnesses_named_in_the_refusal_are_exactly_the_ones_with_a_stdin_channel(tmp_path):
    """E29: the refusal advises an operator to switch harness, so the advice must stay true.

    `STDIN_PROMPT_HARNESSES` is a literal — `argv_prompt` is called from inside
    `prepare`, and importing the adapter registry to build a message would
    invert the dependency the module is built on. This is what keeps the literal
    honest: an adapter that gains or loses the channel and does not update it
    ships a refusal telling the operator to run a harness that would refuse too.
    """
    every = (*STDIN_ADAPTERS, *ARGV_ADAPTERS)
    # Without this the guard is vacuous for the case that matters: a FIFTH
    # adapter is added, `ADAPTERS` needs no edit anywhere else by its own
    # docstring, and the hand-written lists above simply do not mention it — so
    # the walk below never asks it, and a stdin harness missing from
    # `STDIN_PROMPT_HARNESSES` ships a refusal telling the operator to switch to
    # a list that omits the one harness that would have worked.
    assert {adapter_type().name for adapter_type in every} == set(ADAPTERS)

    named = {name.strip() for name in STDIN_PROMPT_HARNESSES.split(",")}
    observed = {
        adapter_type().name
        for adapter_type in every
        if _prepare(adapter_type, tmp_path, "+a\n")[1].stdin_path is not None
    }

    assert named == observed


NUL_DIFF = "diff --git a/blob.bin b/blob.bin\n" + "+" + "a" * 40 + "\x00" + "b" * 40 + "\n"
"""A diff carrying one NUL, as `git` produces for a committed file it diffs as text.

`Workspace.diff` decodes with `errors="replace"`, which repairs invalid UTF-8;
U+0000 is valid UTF-8 and is not touched. The byte therefore reaches the prompt
whatever the harness, and only the CHANNEL decides whether it can be delivered.
"""


@pytest.mark.parametrize("adapter_type", ARGV_ADAPTERS, ids=lambda t: t().name)
def test_a_diff_carrying_a_nul_byte_refuses_on_an_argv_channel_harness(adapter_type, tmp_path):
    """H2, C-1028: `execve` argument strings are NUL-terminated, so a NUL is unrepresentable there.

    `Popen` refuses first, with a `ValueError` — not an `OSError`, so
    `api._spawn`'s handler does not see it and the run resolves
    `indeterminate`/`MALFORMED_OUTPUT`: the row a consumer degrades to a
    graceful skip. A repository could therefore deny its own review with one
    committed byte and leave the reviewer holding the blame. A refusal naming
    the cause is the honest answer, exactly as for `MAX_ARG_STRLEN`.
    """
    with pytest.raises(ConfigError) as exc:
        _prepare(adapter_type, tmp_path, NUL_DIFF)

    message = str(exc.value)
    assert "NUL" in message
    assert STDIN_PROMPT_HARNESSES in message, "the same advice the size refusal gives, for the same reason"


@pytest.mark.parametrize("adapter_type", STDIN_ADAPTERS, ids=lambda t: t().name)
def test_the_same_nul_carrying_diff_prepares_on_a_stdin_channel_harness(adapter_type, tmp_path):
    """H2, E29: the stdin channel is a file descriptor, and a file descriptor carries every byte.

    The decision this pins is that the NUL guard is a property of the argv
    CHANNEL, like `PROMPT_ARGV_LIMIT` beside it, and not a nox-wide content
    policy. A global refusal would fail a whole-branch review on two harnesses
    the kernel has no objection to — the identical over-reach E29 corrected for
    the size cap, one release earlier. The byte survives VERBATIM: nothing
    strips or replaces it, so the reviewer sees the file as committed.
    """
    ws, launch = _prepare(adapter_type, tmp_path, NUL_DIFF)

    assert launch.stdin_path == ws.scratch / "prompt.md"
    assert NUL_DIFF in launch.stdin_path.read_text(encoding="utf-8")
