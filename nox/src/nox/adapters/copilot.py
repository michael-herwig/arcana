"""GitHub Copilot CLI, the fourth v1 harness (D-ab).

Verified against **1.0.82**, probed live on 2026-09-03; every literal below is
set from a file in `tests/contract/fixtures/copilot/`, never from a document
(E3). `PROVENANCE.md` there records the exact command behind each.

Five things about this harness decided the shape of this module, and four of
them contradict what a reading of its `--help` would suggest:

1. **There is no OS sandbox in v1.** `copilot help sandbox` says sandboxing is
   experimental, MXC-backed, off by default and reachable only behind
   `--experimental` or a managed policy — and that with it disabled "shell
   commands run directly on your machine with the same access your user account
   has". So both enforcement axes stamp `harness`, never `os` (D-ab, R15),
   `sandbox_probe` returns `False` in one line, and `--experimental` is a
   `NEVER_EMITTED` word. The boundary for this harness is C-1003's ephemeral
   worktree; the flag stack below is defence in depth over it.
2. **`--deny-tool` does not remove a tool.** A live run denying fourteen of the
   seventeen tools was still offered all seventeen (`toolCount: 17`); a run
   passing `--available-tools view,rg,glob` was offered exactly three. The deny
   flag is a *permission* control — which is what satisfies
   `Capability.ENUMERABLE_DENY` natively, since it outranks `--allow-all-tools`
   — and `--available-tools` is the *tool-removal* one. The adapter emits both,
   and `mechanism="tool-removal"` is true because of the second. An allowlist
   is also the only form that is closed by construction against a future
   release adding an eighteenth tool.
3. **`--disable-builtin-mcps` disables the BUILT-INS only, and 1.0.82 has no
   `--strict-mcp-config` analogue.** Its own help says as much —"Disable all
   built-in MCP servers (currently: github-mcp-server)" — so a user's
   `~/.copilot/mcp-config.json` server loads under the shipped flag stack and
   offers the model its tools, named `<server>-<tool>`. `PINNED_TOOLS` was
   recorded with no MCP server configured, so it carries no such row and
   `DENIED_TOOLS`, derived from it, can never name one: `--deny-tool` cannot
   reach an MCP tool even in principle. What closes it is `--available-tools`,
   which is an allowlist and therefore closed by construction — re-probed
   against a planted stdio server offering one tool, the model was offered it
   with no restriction (18) and with the full deny list (18), and was offered
   `view,rg,glob` and nothing else under the shipped run (3). **That run, not
   `--disable-builtin-mcps`, is what `network_enforcement="harness"` rests on**,
   and it is why the allowlist is not redundant beside the deny list. Recorded
   in `tool-visibility-1.0.82.txt`; the sibling `claude.py` records the same
   failure for its own leg, where `--strict-mcp-config` exists to close it.
4. **A project skill's `description:` reaches the system prompt verbatim and
   survives `--no-custom-instructions`.** Proven by canary: with the flag set,
   the planted description was in the system prompt and the model *called the
   skill*. That is why E18 extends C-1005's shipped literal with
   `NEUTRALIZE_PREFIXES` — for this one surface the flag is not the boundary
   and neutralization is.
5. **The stats footer is on stderr.** `SubprocessRunner.spawn` merges stderr
   into stdout, so `parse` sees `Changes` / `AI Credits` / `Tokens` / `Resume`
   lines interleaved with the JSONL and skips every line that is not a JSON
   object, rather than assuming a pure stream.

The adapter never spawns the review, never states its own containment as fact
and never builds instruction text — `nox.harness` owns all three (see its module
docstring). What lives here is one harness's argv shape, its output dialect and
its evidence-backed error table.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar, Final, Literal, cast

from nox.capability import Capability, Launcher, ModelClass, ModelSpec, ModelSpecT
from nox.config import HarnessConfig
from nox.harness import (
    ContainmentPlan,
    HarnessInfo,
    HarnessUnavailable,
    Launch,
    ParsedOutput,
    argv_prompt,
    police_passthrough,
    probe_run,
    reason_for_exit,
    resolve_model,
    review_prompt,
    to_severity,
)
from nox.liveness import Heartbeat, Liveness
from nox.outcome import FailureReason, Finding, Verdict
from nox.runner import Runner
from nox.workspace import Workspace

# ── Shipped literals, each pinned to a fixture ───────────────────────────────

BINARY: Final[str] = "copilot"
"""The executable. `~/.npm-global/bin/copilot` on the owner's machine, resolved off the minimal `PATH`."""

VERIFIED_AGAINST: Final[str] = "1.0.82"
"""The version every fixture here was recorded from — read off `version-1.0.82.txt` (E3, C-1020)."""

VERSION_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(\d+\.\d+\.\d+)\b")
"""Extracts the version from `GitHub Copilot CLI 1.0.82.`

`--version` prints two lines — the banner and an unconditional
`Run 'copilot update' to check for updates.` — so the parse is a search over the
first matching line rather than a whole-output match.
"""

PROBE_TIMEOUT_S: Final[int] = 30
"""Wall clock for `--version`. A startup, not a review; `DEFAULT_TIMEOUT_S` bounds the review."""

REVIEW_TOOLS: Final[tuple[str, ...]] = ("view", "rg", "glob")
"""The only tools the reviewer is offered: read a file, search, list.

Read-only by construction. `bash` is absent, and with it every write and all
network reach; `skill` is absent, which is the second half of E18's mitigation
(neutralization removes the skill files, this removes the tool that would load
one from anywhere else).

All three are usable in `-p` mode **without** any allow flag: the recorded
`review-shaped-1.0.82.txt` run calls `view` and returns the file's contents
under exactly this argv. That matters because stdin is `DEVNULL` (C-1009), so a
review that stalled on a permission prompt would hang to the wall clock rather
than ask.
"""

PINNED_TOOLS: Final[tuple[str, ...]] = (
    "bash",
    "read_bash",
    "stop_bash",
    "list_bash",
    "apply_patch",
    "view",
    "web_fetch",
    "fetch_copilot_cli_documentation",
    "skill",
    "sql",
    "session_store_sql",
    "read_agent",
    "list_agents",
    "write_agent",
    "rg",
    "glob",
    "task",
)
"""Every tool 1.0.82 offers the model, in the order it offers them.

Read off a live run's `requestCapture.tools` and committed as
`tools-1.0.82.txt`, because a tool list is not in `--help` and a guessed one
would leave a real tool undenied. A unit test asserts this tuple equals that
fixture, so a re-probe against a newer release is a failing test rather than a
silent gap.
"""

DENIED_TOOLS: Final[tuple[str, ...]] = tuple(name for name in PINNED_TOOLS if name not in REVIEW_TOOLS)
"""Everything but `REVIEW_TOOLS`, derived rather than listed.

Derived so the two sets cannot drift: a tool added to `PINNED_TOOLS` at the next
re-probe is denied by construction unless it is deliberately named a review
tool. `--deny-tool` is what makes this an *enumerable* deny (C-1013) and it
outranks `--allow-all-tools`; `--available-tools` is what actually removes them.
"""

MAX_AI_CREDITS: Final[str] = "30"
"""The `--max-ai-credits` bound on one review.

Copilot bills in AI credits, not dollars: a trivial 14 k-token turn cost 0.39.
**30 is the tightest bound the binary accepts** — `--max-ai-credits 25` is
refused with `Use at least 30 AI credits.` — so this is the floor rather than a
chosen ceiling, and it still sits about two orders of magnitude above one turn.

ponytail: a shipped constant, not a `nox.toml` key. The upgrade path is a config
field the day a real review legitimately exceeds it — and the failure mode of
the constant is a truncated review, which `parse` resolves `indeterminate`,
never `approve`.
"""

CONTAINMENT_ARGV: Final[tuple[str, ...]] = (
    "--available-tools",
    ",".join(REVIEW_TOOLS),
    "--deny-tool",
    ",".join(DENIED_TOOLS),
    "--disable-builtin-mcps",
    "--no-custom-instructions",
)
"""The contiguous argv run `containment_plan` names as its evidence (C-1025).

Emitted **last** in nox's own flag tail, so the run ends the resolved argv and
C-1025's rule 2 ("the word after the run is absent or starts with `-`") holds
structurally rather than by the accident of what follows.

**Space-separated, not `=`-attached, and that is a derivation property rather
than a style choice.** `derive_containment`'s rule 4 protects an evidence flag
only when its in-run successor carries no `=`; an evidence word spelled
`--available-tools=view,rg,glob` is exempt from rule 4 and is not reached by
rule 3 either, because rule 3 compares an outside word's *value* against the
evidence *key*. A later `--available-tools=bash` would then leave every evidence
word present and restore the whole tool set with the containment stamp intact.
In the separated spelling both flags are `_respecifiable`, so any later
spelling of either is refused. Verified against the binary in the separated
form (`review-shaped-1.0.82.txt`: `toolCount: 3`), and the variadic parse is
safe because every value word here is followed by a `-`-prefixed one.

S-1015 names `--deny-tool`, `--disable-builtin-mcps` and
`--no-custom-instructions`; `--available-tools` is added because it is the word
that makes `tool-removal` a fact rather than a claim (see the module docstring).

**The other three do not carry the claim between them**, which is the whole
point of adding the fourth: `--deny-tool` removes nothing (a 14-name deny list
was still offered all 17 tools) and cannot name an MCP tool at all,
`--disable-builtin-mcps` leaves a user-configured MCP server loaded, and
`--no-custom-instructions` does not survive a planted skill description (E18).
Only `--available-tools` was measured removing a tool that reaches the network,
including the MCP-server one. `--deny-tool` stays because it is what makes the
deny ENUMERABLE under C-1013 and because it outranks `--allow-all-tools`; it is
defence in depth over the allowlist, never the load-bearing word.
"""

_FOOTER_LABELS: Final[tuple[str, ...]] = ("Changes", "AI Credits", "Tokens", "Resume")
"""First word of each stats-footer line 1.0.82 writes to stderr when the run ends.

`SubprocessRunner.spawn` merges stderr into stdout, so these arrive interleaved
with the JSONL rather than after it, and they are the one thing dropped from
`raw`: they are the harness's own progress accounting, not output about the
change under review, and a `raw` whose content depended on *where* the footer
landed in the merge would make two identical reviews compare unequal. Everything
else the stream carried — including a bare `Error:` line, which is where an
unavailable `--model` reports itself — is retained verbatim (C-1018).
"""

_FENCE: Final[re.Pattern[str]] = re.compile(r"```+(?:json)?[^\S\n]*\n(.*?)```+", re.DOTALL)
"""A fenced block in the final answer, non-greedy so one fence is one match.

**The prompt does not ask for a fence.** `prompt._SCHEMA_ASK` is "Reply with a
single JSON object and nothing else"; the backticks around `WIRE_SCHEMA` are
nox's own delimiter for untrusted content, not an output-format instruction. So
a model that complies literally answers with a bare object and one that renders
markdown wraps it — `_candidates` therefore offers `parse` both spellings, and
neither is the one true shape.
"""

_VERDICTS: Final[tuple[Verdict, ...]] = ("approve", "needs-attention")
"""The two words `WIRE_SCHEMA` names, as `Verdict`'s own members.

A tuple and not a `frozenset` deliberately —
`x in frozenset(...)` raises `TypeError` on an unhashable `x`, and `x` here is
whatever a model put in a JSON field."""

_CONFIDENCES: Final[tuple[Literal["high", "medium", "low"], ...]] = ("high", "medium", "low")
"""`Finding.confidence`'s domain, for the same reason and with the same tuple.

Typed as the literals rather than as `str` so membership NARROWS: `x in
_CONFIDENCES` is what turns an untrusted `object` off the wire into the field's
own type, with no cast standing in for the check.
"""


def _event(line: str) -> Mapping[str, object]:
    """Decode one stream line, or return an empty mapping.

    Total over any line, because the stream is not pure JSONL: the merged
    stderr contributes the footer and a bare `Error:` line, and a JSON line
    that decodes to something other than an object would hand `.get` an `int`
    — an `AttributeError` is not a `NoxError` and would escape `review()`'s
    C-1029 totality as a traceback.

    Args:
        line: One line of the merged stream.

    Returns:
        The decoded object, or `{}` for anything else.
    """
    try:
        event: object = json.loads(line)
    except ValueError:
        return {}
    return cast("Mapping[str, object]", event) if isinstance(event, dict) else {}


def _final_answer(event: Mapping[str, object]) -> str | None:
    """Return this event's final-answer text, or `None` if it is not one.

    Three near-misses this rejects, all present in the recorded fixtures: an
    `assistant.message` announcing a tool call carries `content: ""` and a
    phase that is not `final_answer`; `assistant.message_start` carries the
    `final_answer` phase with no content at all; and `assistant.message_delta`
    carries the same text in fragments under `deltaContent`.

    Args:
        event: One decoded stream event.

    Returns:
        The answer text, or `None`.
    """
    payload = event.get("data")
    if event.get("type") != "assistant.message" or not isinstance(payload, dict):
        return None
    data = cast("Mapping[str, object]", payload)
    content = data.get("content")
    return content if data.get("phase") == "final_answer" and isinstance(content, str) else None


def _unresolved(raw: str, detail: str, exit_code: int) -> ParsedOutput:
    """Build the `indeterminate` result for a stream that established no verdict (C-1011).

    Not `harness.indeterminate`, which stamps "this adapter's classification
    table does not record it" — true of an error object `classify` declined,
    and false of every case here, none of which is an error object at all.

    `reason_for_exit` gets the first word, and only for the one status that
    carries meaning: a harness nox itself SIGTERMed prints nothing more and
    exits 143, and reporting that as `MALFORMED_OUTPUT` reads as "the harness
    produced garbage" when the truth is that nox killed it.

    **It takes the status with it**, which the first version of this function
    did not: SD § 7.1's `exit 143` row reads `error` / `KILLED`, and § 7.2
    defines `indeterminate` as "ran, unclassifiable" — a run nox terminated is
    classified exactly, so stamping it `indeterminate` contradicted the reason
    word sitting beside it. Three of the four adapters resolve the row the same
    way:
    the exit status labels a run whose stream established neither a verdict nor
    a terminal outcome of its own, and never overrules one that did (C-1011,
    SD § 4.3). Reaching here is precisely that condition for this harness.
    `claude` is the one exception and its docstring says so: its `reason_for_exit`
    read sits ABOVE its `api_retry` ladder, so that adapter alone can label a
    harness-reported rate limit with nox's own stop.

    Args:
        raw: The stream as delivered, retained unconditionally (C-1018).
        detail: nox's own account of why no verdict was established.
        exit_code: What the child exited with. A coarse hint only — it never
            gates success, and `reason_for_exit` maps exactly one value.

    Returns:
        `error`/`KILLED` for nox's own stop, else `indeterminate`/
        `MALFORMED_OUTPUT`. Neither can say `approve`: `ParsedOutput` refuses a
        verdict on a non-`ok` status.
    """
    stopped = reason_for_exit(exit_code)
    return ParsedOutput(
        status="error" if stopped is not None else "indeterminate",
        verdict=None,
        findings=(),
        summary="",
        detail=detail,
        raw=raw,
        reason=stopped or FailureReason.MALFORMED_OUTPUT,
    )


def _candidates(answer: str) -> tuple[tuple[Verdict, Mapping[str, object]], ...]:
    """Every object in `answer` that names a verdict this adapter recognizes.

    Both spellings, because the prompt asks for neither: each fenced block, and
    the whole answer as one bare object. An element that does not decode, or
    decodes to something that is not an object, or whose `verdict` is not one of
    `_VERDICTS`, is not a candidate — which is what keeps the fenced
    `WIRE_SCHEMA` template itself out (its `verdict` reads
    `"approve | needs-attention"`, a third word).

    Args:
        answer: The final answer's text.

    Returns:
        `(verdict, object)` per candidate, in the order they appear. The verdict
        travels beside its object because recognizing it is what MAKES it a
        candidate — reading it off the mapping a second time would be a second
        source for one fact.
    """
    found: list[tuple[Verdict, Mapping[str, object]]] = []
    for block in (*_FENCE.findall(answer), answer):
        try:
            decoded: object = json.loads(block)
        except ValueError:
            continue
        if not isinstance(decoded, dict):
            continue
        wire = cast("Mapping[str, object]", decoded)
        # Compared member by member, the shape `to_severity` uses: `x in
        # _VERDICTS` would raise on an unhashable `x` for a `frozenset` and
        # narrows to nothing for a tuple, and `x` here is whatever a model put
        # in a JSON field.
        for verdict in _VERDICTS:
            if wire.get("verdict") == verdict:
                found.append((verdict, wire))
                break
    return tuple(found)


def _finding(item: Mapping[str, object]) -> Finding:
    """Build one `Finding` from one wire object, coercing every field it may have invented.

    Nothing here trusts a type. `ParsedOutput.__post_init__` still normalizes
    `severity` and `file` afterwards — this is what stops a non-`str` `file` or
    a non-`int` line number reaching that normalization as the wrong type
    (C-1019).

    Args:
        item: One decoded `findings` element.

    Returns:
        The finding, with every unusable field dropped rather than carried.
    """
    file = item.get("file")
    confidence = item.get("confidence")
    recommendation = item.get("recommendation")
    return Finding(
        severity=to_severity(item.get("severity")),
        title=str(item.get("title", "")),
        body=str(item.get("body", "")),
        file=file if isinstance(file, str) else None,
        line_start=_line(item.get("line_start")),
        line_end=_line(item.get("line_end")),
        confidence=confidence if confidence in _CONFIDENCES else "medium",
        recommendation=recommendation if isinstance(recommendation, str) else None,
    )


def _line(value: object) -> int | None:
    """Return `value` as a line number, or `None` — a wire field is not an `int` because it says so."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


# The words this adapter's argv must never carry live in
# `tests/unit/test_adapter_copilot.py`, not here. WP6's static scan refuses any
# string constant in `src/nox/adapters/*.py` that equals a `NEVER_EMITTED`
# member — correctly, since the scan cannot tell a literal used as a guard from
# one used as a flag. The test module is not scanned, and 1.0.82 carries five
# words `NEVER_EMITTED` does not, in two classes:
#
#   permission lifts — `--allow-all` and `--yolo`, which `--help` documents as
#   aliases for `--allow-all-tools --allow-all-paths --allow-all-urls`, and
#   `--allow-all-urls`, which restores network reach on its own;
#
#   a containment BYPASS — `-C <directory>` changes the working directory before
#   anything else runs, so the harness would review somewhere other than the
#   C-1003 worktree while `Invocation.cwd` still reads `ws.path` and the
#   `Containment` stamp still says `harness`. A different and worse class than a
#   permission lift, and reported to WP6 as its own row.
#
# Unreachable in v1 either way — `PASSTHROUGH_ALLOW["copilot"]` is empty and nox
# emits none of them — but `NEVER_EMITTED` is the gate that would catch a
# computed one, `harness.py` is WP6's, and it is not edited from here.


class CopilotAdapter:
    """The `copilot` adapter (C-1007, C-1011, C-1012, C-1030, S-1015)."""

    name: ClassVar[str] = "copilot"
    BINARY: ClassVar[str] = BINARY
    CONFIG_READS: ClassVar[tuple[str, ...]] = (
        "${HOME}/.copilot/config.json",
        "${HOME}/.copilot/settings.json",
        "${HOME}/.copilot/mcp-config.json",
    )
    """The user-level files copilot reads, hashed into the C-1025 probe digest.

    All three observed under `~/.copilot/` on the probed machine; the third is
    named by `--additional-mcp-config`'s own help text ("augments config from
    ~/.copilot/mcp-config.json"). `$HOME`-relative rather than
    `${XDG_CONFIG_HOME}`-relative because 1.0.82 was observed reading the first
    location and nothing proves the second.

    A file that does not exist hashes as a stable absent-marker, so declaring
    `mcp-config.json` before it exists costs nothing and makes creating it a
    cache miss.
    """

    MODELS: ClassVar[Mapping[ModelClass, ModelSpec]] = MappingProxyType(
        {
            "fast-balanced": ModelSpecT(model="gpt-5.6-luna"),
            "deep-reasoning": ModelSpecT(model="gpt-5.6-luna", effort="high"),
        }
    )
    """Capability class → this harness's literal (C-1030).

    **Bare model ids**, unlike opencode's `provider/`-prefixed form — both reach
    the same GitHub Copilot backend, which is why D-b's asymmetry warning keys
    on the model pair rather than the harness (C-1036).

    `gpt-5.6-luna` was resolved live; an invented second id is worse than one
    honest one, and 1.0.82 offers no way to enumerate models (`--model bogus`
    answers `Model "bogus" from --model flag is not available.` and lists
    nothing). So `deep-reasoning` is the same model at the harness's own
    reasoning-effort knob — `--effort high`, one of the seven levels
    `--help` documents — which is exactly the shape Codex's effort knob takes.
    """

    CLASSIFY: ClassVar[Mapping[str, FailureReason]] = MappingProxyType({})
    """Observed error shape → reason (C-1012). Empty, and that is the honest state.

    1.0.82 emits no `error`-typed JSONL event in any recorded run. Its one
    recorded failure — an unavailable `--model` — is a bare stderr line and exit
    1 with **no `result` line at all**, which `parse` resolves `indeterminate`
    with the raw retained; there is no object for `classify` to see. Under SD
    § 7.1a a cell stays `None` until a recorded fixture proves it, so an
    `UNAUTHENTICATED` or `RATE_LIMITED` mapping is not written here on a guess.

    `config.AUTH_ENV_HINTS["copilot"]` is empty for the same reason.
    """

    def probe(self, runner: Runner, cfg: HarnessConfig, env: Mapping[str, str], cwd: Path) -> HarnessInfo:
        """Run `copilot --version` under the C-1008 environment in nox's empty cwd (C-1014).

        Reached only through `harness.probe_harness`, which mints and removes
        `cwd`.

        Args:
            runner: The process seam.
            cfg: This harness's config, for its launcher prefix.
            env: The C-1008 minimal environment.
            cwd: A fresh empty directory nox owns.

        Returns:
            A `HarnessInfo` naming `Liveness.SEMANTIC` (the JSONL stream is
            typed events), `verified_against=VERIFIED_AGAINST`, and capabilities
            `{ENUMERABLE_DENY, ENFORCED_READ_ONLY}`.

            `ENFORCED_READ_ONLY` is declared, and the bar it is measured against
            is the ADR's own: *the harness enforces it below the model*, which
            the ADR stamps `yes` for Claude Code on pre-tool-call permission
            rules. `--available-tools view,rg,glob` clears that bar by a wider
            margin — a writing tool is never put in the model's list at all,
            rather than offered and refused at call time. The OS distinction
            lives on the other field: `Enforcement` stays `harness`, never `os`
            (R15). The stamp cannot outrun the argv either, because
            `--available-tools` is a member of `CONTAINMENT_ARGV`: if it does
            not survive to the resolved argv, `derive_containment` nulls both
            axes and `authorize` refuses, so no `Review` can carry
            `enforced_read_only=True` without that word present.

            `STRUCTURED_OUTPUT` is omitted, and load-bearingly so: declaring it
            sets `review_prompt`'s `structured_output=True`, which drops the
            fenced-JSON ask from the prompt while `parse` still looks for a
            fence — every review would resolve `indeterminate`. 1.0.82 has no
            schema flag.

        Raises:
            HarnessUnavailable: `ABSENT` when the binary cannot be resolved or
                run. An `UNAUTHENTICATED` shape is **not** recognized: no
                recorded fixture proves what a logged-out 1.0.82 prints, and
                under SD § 7.1a a shape without a fixture is not mapped on a
                guess. `config.AUTH_ENV_HINTS["copilot"]` is empty for the same
                reason, so this leg lands as `ABSENT` or reaches `parse` and
                resolves `indeterminate` — never a clean verdict either way.
        """
        launcher = cfg.launcher_for(BINARY) or Launcher(binary=BINARY)
        probed, lines = probe_run(runner, launcher, env, cwd, "--version", timeout_s=PROBE_TIMEOUT_S)
        banner = "".join(lines)
        if probed.exit_code != 0:
            # `None` — the wall clock elapsed with the child still running — is
            # the same answer: a probe that never returned is not a harness that
            # named a version. One message for both, as `claude` has, because the
            # distinction is `supervise`'s to report and not this adapter's to
            # re-derive from a status it did not choose.
            raise HarnessUnavailable(FailureReason.ABSENT, f"{BINARY}: --version did not exit cleanly")
        found = VERSION_PATTERN.search(banner)
        return HarnessInfo(
            name=self.name,
            version=found.group(1) if found else None,
            verified_against=VERIFIED_AGAINST,
            capabilities=frozenset({Capability.ENUMERABLE_DENY, Capability.ENFORCED_READ_ONLY}),
            heartbeat_kind=Liveness.SEMANTIC,
            launcher=launcher,
        )

    def sandbox_probe(self, runner: Runner, ws: Workspace, info: HarnessInfo, env: Mapping[str, str]) -> bool:
        """Always `False`: this adapter claims no `os` axis (D-ab, R15).

        Copilot's MXC sandbox is experimental and off by default, so there is
        nothing here to prove. What actually makes `os` unreachable for this
        harness is `containment_plan` never claiming it plus `_derived_axis`
        downgrading an unproven `os` to `None` — `authorize` only calls this
        method when the plan claims an `os` axis, so it is the second line of
        the argument rather than the first.

        Args:
            runner: The process seam. Unused.
            ws: The live workspace. Unused.
            info: What `probe` established. Unused.
            env: The C-1008 minimal environment. Unused.

        Returns:
            `False`.
        """
        del runner, ws, info, env
        return False

    def containment_plan(self, cfg: HarnessConfig, info: HarnessInfo) -> ContainmentPlan:
        """Claim `tool-removal` on both axes at `harness` level, evidenced by `CONTAINMENT_ARGV`.

        Never `os`: see the module docstring. `derive_containment` re-checks
        every word of the evidence against the argv `prepare` actually built.

        `network_enforcement="harness"` is carried by `--available-tools`, and
        by nothing else in the run: it is the only evidence word measured
        removing a network-reaching tool, and the only one that reaches a
        user-configured MCP server's tool — which `--deny-tool` cannot name and
        `--disable-builtin-mcps` does not disable (module docstring, point 3).
        Both axes rest on the same word, which is why the run is emitted as a
        contiguous tail whose every flag is `_respecifiable`.

        Args:
            cfg: This harness's config.
            info: What the probe established.

        Returns:
            The claim and the contiguous argv run that corroborates it.
        """
        del cfg, info
        return ContainmentPlan(
            mechanism="tool-removal",
            write_enforcement="harness",
            network_enforcement="harness",
            argv_evidence=CONTAINMENT_ARGV,
        )

    def prepare(
        self,
        ws: Workspace,
        info: HarnessInfo,
        cfg: HarnessConfig,
        instructions: str | None,
    ) -> Launch:
        """Build the harness-level launch for one review (E9a, C-1023).

        Copilot has no § 6.x table in the system design — it joined v1 during
        execution (D-ab) — so this is its home, in the sibling adapters' shape:

        | Concern | Flag | Note |
        |---|---|---|
        | headless | `-p <text>` | exits after completion; there is no prompt-FILE flag |
        | stream | `--output-format json` | JSONL, one object per line; `SEMANTIC` |
        | schema | — | none in 1.0.82: `STRUCTURED_OUTPUT` absent, fenced ask in the prompt |
        | containment | `CONTAINMENT_ARGV` | `tool-removal`; both axes `harness`, never `os` |
        | model | `--model L` (+ `--effort E`) | from `MODELS[class]`, never config argv (C-1030) |
        | cost | `--max-ai-credits 30` | AI credits, not USD; 30 is the binary's own floor |
        | noise | `--no-color`, `--log-level none` | keeps the merged stream to JSONL + footer |
        | passthrough | allowlist = **empty** | C-1023; every element is refused by name |

        Emission order is `--no-color --log-level none --output-format json
        [--model L [--effort E]] --max-ai-credits 30 -p <prompt>` and then
        `*CONTAINMENT_ARGV` **last**, so the evidence run ends the argv and
        C-1025's rule 2 holds structurally. `--effort` is emitted only beside a
        `--model`, and only when the resolved `ModelSpecT` carries one.

        The prompt comes from `harness.review_prompt(ws, info, instructions)`
        and then `harness.argv_prompt(text)` — that chain, not
        `prompt.render`, because `review_prompt` is what fills
        `neutralized_paths=` and `structured_output=` (C-1028, C-1043) and
        `argv_prompt` is what enforces `PROMPT_ARGV_LIMIT`. Copilot 1.0.82 has
        **no prompt-file flag and no stdin form** — `--help` offers `-p <text>`
        and nothing else — so argv is the only channel, the same deviation
        `opencode run [message..]` forces. These two are the only shapes that
        limit still binds (E29): `claude` and `codex` read their prompt from
        stdin and declare `Launch.stdin_path` instead, which is why a
        whole-branch diff refuses here and reviews there.

        **Residual that bound does not cover:** a prompt on argv is world-
        readable in `/proc/<pid>/cmdline` for the length of the review, so the
        rendered diff is visible to any local user on the machine.
        `PROMPT_ARGV_LIMIT` bounds truncation, not disclosure, and 1.0.82 offers
        no second channel to close it with. `claude` and `codex` closed it by
        moving to stdin (E29); this harness cannot follow them.

        There is no subcommand: `copilot [options]` is the whole shape. So the
        argv is exactly `police_passthrough("copilot", cfg.passthrough,
        nox_flags)` — passthrough first (and always empty in practice, since
        `PASSTHROUGH_ALLOW["copilot"]` is an empty allowlist), nox's flags last.

        Args:
            ws: The live ephemeral worktree.
            info: What the probe established.
            cfg: This harness's config.
            instructions: Extra instruction text from nox's own caller. The
                scope is `ws.scope`, not a parameter.

        Returns:
            The launch. `env` is empty: this harness's containment is entirely
            in argv, so declaring any environment key would be an unevidenced
            widening `authorize` would refuse anyway.

        Raises:
            ConfigError: A refused `passthrough` element (C-1023), or a prompt
                over `PROMPT_ARGV_LIMIT`.
        """
        spec, _ = resolve_model(self.MODELS, cfg)
        model_words: tuple[str, ...] = ()
        if spec is not None:
            model_words = ("--model", spec.model, *(("--effort", spec.effort) if spec.effort else ()))
        _, text = review_prompt(ws, info, instructions)
        nox_flags = (
            "--no-color",
            "--log-level",
            "none",
            "--output-format",
            "json",
            *model_words,
            "--max-ai-credits",
            MAX_AI_CREDITS,
            "-p",
            argv_prompt(text),
            *CONTAINMENT_ARGV,
        )
        return Launch(argv=police_passthrough(self.name, cfg.passthrough, nox_flags))

    def on_line(self, line: str) -> bool:
        """Answer whether one stream line was a typed copilot event (C-1010).

        This adapter declares `Liveness.SEMANTIC`, so `supervise` measures the
        120 s silence window against `Heartbeat.last_activity_at`, which only a
        `True` here advances — an adapter that never answered would have every
        review killed at 120 s while the model was still working.

        The test is the same one `parse` discriminates on: a line that decodes
        to a JSON object carrying a top-level `type` is one of the `session.*`,
        `user.message`, `assistant.*`, `tool.*` or `result` events. Everything
        else — the stats footer and the bare `Error:` line the merged stderr
        contributes, and blank lines — decodes to `{}` and is bytes without
        progress, which is exactly what `False` means.

        Args:
            line: One line of the merged output stream.

        Returns:
            Whether the line was a typed event.
        """
        return "type" in _event(line)

    def classify(self, err: Mapping[str, object]) -> FailureReason | None:
        """Map one observed error object to a reason, or decline (C-1012).

        Always declines today — `CLASSIFY` is empty, and its docstring says why.

        Args:
            err: One decoded error object from the stream.

        Returns:
            The reason, or `None`.
        """
        return self.CLASSIFY.get(str(err.get("message", "")))

    def parse(self, lines: Iterable[str], exit_code: int, hb: Heartbeat) -> ParsedOutput:
        """Resolve copilot's JSONL stream to a tri-state result (C-1011).

        The stream is `--output-format json`: one JSON object per line,
        discriminated on the **top-level `"type"`** key — `session.*`,
        `user.message`, `assistant.*`, `tool.*` and a terminal `result`. Four
        properties of the real stream shape this:

        - **it is not pure JSONL.** The stats footer arrives on stderr, which
          `SubprocessRunner.spawn` merges into stdout, so every unparseable line
          is skipped rather than treated as a failure.
        - **the answer is the last `assistant.message`'s `data.content`**, the
          one whose `data.phase` is `final_answer`. `assistant.message_delta`
          events carry the same text in fragments and are ignored, and an
          `assistant.message` announcing a tool call carries `content: ""`.
        - **`result` has no `data` key.** Its fields sit at the top level:
          `type`, `timestamp`, `sessionId`, `exitCode`, `usage`. A parser that
          reaches for `data` on every line finds nothing here.
        - **`result` may be absent entirely.** An unavailable `--model` exits 1
          having emitted only `session.*` lines. No `result` and no final answer
          resolves `indeterminate` carrying `MALFORMED_OUTPUT`, never `ok`.

        The verdict object is extracted from the final answer's fenced JSON
        (`prompt.WIRE_SCHEMA`), because copilot has no native schema flag and
        `STRUCTURED_OUTPUT` is therefore absent from its capabilities. A missing
        or unparseable fence resolves `indeterminate` with `raw` retained
        (C-1011), never `approve`.

        `cost_usd` stays `None` on every path: copilot reports **AI credits**
        and never dollars. `result.usage` carries `premiumRequests` and
        durations with no money figure at all; the only credit number in the
        stream is `session.usage_checkpoint`'s `data.totalNanoAiu`, and an AI
        credit is not a dollar. Reporting one as the other would put an invented
        number on a `Review`.

        Args:
            lines: The merged output stream, in order.
            exit_code: What the child exited with. Recorded, never the gate.
            hb: Progress evidence at the moment the run ended.

        Returns:
            What the output establishes.
        """
        del hb
        kept = [line for line in lines if line.strip() and not line.startswith(_FOOTER_LABELS)]
        # `rstrip`, because `SubprocessProcess` keeps the newline `readline`
        # produced while a `splitlines()`-derived fixture does not: joining the
        # first shape on "\n" would double every line break, and `raw` is the
        # record C-1018 retains and core scans for credential shapes.
        raw = "\n".join(line.rstrip("\r\n") for line in kept)
        answer: str | None = None
        finished = False
        for line in kept:
            event = _event(line)
            finished = finished or event.get("type") == "result"
            content = _final_answer(event)
            answer = answer if content is None else content
        if answer is None or not finished:
            return _unresolved(raw, "the stream carried no final answer, or no terminal result line", exit_code)
        wires = _candidates(answer)
        if len(wires) != 1:
            # Zero is a model that answered in prose. **More than one is the T1
            # case**: the diff is not neutralized — it is the thing under review
            # — so a hostile file can carry a complete verdict object, and a
            # reviewer quoting it back puts two in the answer. Picking either
            # end lets whoever controls that end decide the review, so neither
            # is picked. One object, or no verdict.
            return _unresolved(
                raw, f"the final answer carried {len(wires)} verdict objects where exactly one is a verdict", exit_code
            )
        verdict, wire = wires[0]
        reported = wire.get("findings")
        summary = wire.get("summary")
        return ParsedOutput(
            status="ok",
            verdict=verdict,
            findings=tuple(
                _finding(cast("Mapping[str, object]", item))
                for item in (cast("list[object]", reported) if isinstance(reported, list) else [])
                if isinstance(item, dict)
            ),
            summary=summary if isinstance(summary, str) else "",
            detail=None,
            raw=raw,
            reason=None,
        )


__all__ = [
    "BINARY",
    "CONTAINMENT_ARGV",
    "DENIED_TOOLS",
    "MAX_AI_CREDITS",
    "PINNED_TOOLS",
    "PROBE_TIMEOUT_S",
    "REVIEW_TOOLS",
    "VERIFIED_AGAINST",
    "VERSION_PATTERN",
    "CopilotAdapter",
]
