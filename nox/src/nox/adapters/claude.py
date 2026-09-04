"""The Claude Code adapter: argv shape, output dialect, error table (C-1007, C-1012, C-1030).

Containment is `tool-removal` and both axes stamp `harness` — never `os`. Claude
Code has no operating-system sandbox nox drives, so `sandbox_probe` returns
`False` in one line and `derive_containment` would refuse an `os` claim this
adapter never makes.

**Every flag below was proven against the installed 2.1.260, not read off a
document** (E3). Two of the findings are the reason the set is what it is:

- `--restricted --tools Read,Grep,Glob` alone reported a session tool list of
  `Glob, Grep, Read` **plus every tool of the user's connected MCP servers**,
  among them file-creating and page-writing tools reaching the network.
  `--tools` constrains the *built-in* set only. Adding `--strict-mcp-config`
  (with no `--mcp-config`) reduced `mcp_servers` to `[]`. It is containment,
  not hygiene, and it is in the evidence run for that reason.
- SD § 6.1's `--permission-mode dontAsk` rests on "default for `-p` is Manual,
  which blocks forever on a prompt that never arrives". At 2.1.260 that premise
  is false — `permissionMode` was `default` in every observed run — and no
  `--permission-mode` value is *narrower* than that default: `acceptEdits`,
  `auto` and `bypassPermissions` widen, `plan` changes the output shape, and
  `dontAsk` names auto-approval. 2.1.260 ships the precise instrument instead,
  `--permission-prompts none` ("anything that would prompt is denied
  automatically"), which this adapter emits in its place. Deviation recorded
  rather than silently taken.

SD § 6.1 writes the tool list space-separated (`--tools Read Grep Glob`). This
adapter joins it with commas, which the flag's own help documents, because
`--tools <tools...>` is **variadic**: a space-separated list swallows the next
argv word, and the run is the tail of the argv.

Neither axis says anything about how long a descendant lives (D-ac). Removing
Bash removes the writes and the network reach of the *review*; it is not a claim
that the harness cannot leave a process behind.

**The prompt rides stdin** (E29). Claude Code exposes no user-prompt FILE
flag — `--file` is a remote file-API download, and the `--system-prompt-file`
slot named inside `--bare`'s help is a different message with different
semantics — but `--print` reads the user prompt from stdin when one is piped,
which `Launch.stdin_path` supplies from `review_prompt`'s own file. So
`argv_prompt` and its `PROMPT_ARGV_LIMIT` are NOT this adapter's route: that
limit is the kernel's `MAX_ARG_STRLEN` and binds only `copilot -p` and
`opencode run [message..]`, the two shapes with no second channel.

`--bare` looks like the strongest hardening flag here and is in
`harness.NEVER_EMITTED` for a reason worth stating once: it forces
authentication to `ANTHROPIC_API_KEY`, which C-1002 and `config.DENY_PATTERNS`
drop from the child environment, so emitting it would make the harness
permanently unauthenticated.

Authentication is preflighted (`claude auth status`) rather than left to the
review. It buys latency, not correctness — `classify` resolves a 401 from the
stream either way — but the latency is the point: a 401 sends Claude Code round
its own retry ladder **ten times** with escalating backoff (~185 s observed),
and a 429 ten times at 60 s each. nox reads one field of that output,
`loggedIn`, and never the identity fields beside it.
"""

from __future__ import annotations

import json
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Final, cast

from nox.capability import Capability, Launcher, ModelClass, ModelSpec, ModelSpecT
from nox.config import narrow_tools

# Nothing from `nox.prompt` is imported here, ever: an adapter that can reach
# `render` is an adapter that can guess `structured_output` and drop
# `neutralized_paths` (C-1028). `review_prompt` below is the sanctioned route,
# and `test_harness.py` scans for the shortcut.
from nox.harness import (
    ContainmentPlan,
    HarnessInfo,
    HarnessUnavailable,
    Launch,
    ParsedOutput,
    indeterminate,
    police_passthrough,
    probe_run,
    reason_for_exit,
    resolve_model,
    review_prompt,
    to_severity,
)
from nox.liveness import Heartbeat, Liveness
from nox.outcome import FailureReason, Finding

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from nox.config import HarnessConfig
    from nox.runner import Runner
    from nox.workspace import Workspace

# ── Shipped literals, pinned from the real binary ────────────────────────────

VERIFIED_AGAINST: Final[str] = "2.1.260"
"""The version the fixtures in `tests/contract/fixtures/claude/` were recorded from (E3).

Set from a re-probe of the installed binary, never copied from a document
(C-1020). A mismatch warns and continues.

**One fixture carries an older version in its name and that is deliberate.**
`error-429-2.1.259.jsonl` records a real rate limit, a state no re-recording can
manufacture on demand, so E30 kept the 2.1.259 recording rather than fabricate a
2.1.260 one — a fixture's filename names the release it was actually captured
from, and inventing the stream would be exactly the document-sourced claim E3
forbids. The `system`/`api_retry` event it turns on is byte-identical in shape
at 2.1.260, re-derived from the live 401 ladder when the pin moved, so the
recording remains a faithful sample of the dialect this adapter parses.
"""

PROBE_TIMEOUT_S: Final[int] = 60
"""The `supervise` wall clock for each of the probe's two short invocations.

Both are local: `--version` prints a string, `auth status` reads the credential
store. Generous rather than tight, because the failure this bound exists for is
a hung binary, not a slow one.

It bounds one invocation once. The probe runs under `supervise` with
`Liveness.PROCESS_ONLY`, whose `SILENCE_S` entry is `None`, so this and the kill
ladder's `grace_s` are the only clocks a probe is held to.
"""

READ_ONLY_TOOLS: Final[tuple[str, ...]] = ("Read", "Grep", "Glob")
"""The built-in tools the review keeps — nox's containment set for this harness.

An allowlist over Claude Code's built-in set, which is what makes the deny set
enumerable (`Capability.ENUMERABLE_DENY`): everything absent — Bash, Write,
Edit, WebFetch, WebSearch, Task and the rest — does not exist for the session.
`config.narrow_tools` may only shrink it, and an explicit empty narrow is a
legal request (`--tools ""` disables every tool) rather than "unset".
"""

MODELS: Final[Mapping[ModelClass, ModelSpec]] = MappingProxyType(
    {
        "fast-balanced": "claude-haiku-4-5-20251001",
        "deep-reasoning": ModelSpecT(model="claude-opus-5", effort="high"),
    }
)
"""Capability class → Claude Code literal (C-1030).

`fast-balanced` is the literal the plan's environment probe drove live.
`deep-reasoning` pairs a frontier literal with `--effort`, Claude Code's own
reasoning-effort knob (`low|medium|high|xhigh|max` at 2.1.260).

Both literals are checked against the binary rather than assumed, and
`tests/contract/test_claude.py` re-runs that check for every entry here so the
claim is an artifact and not this sentence. An unrecognised name makes 2.1.260
emit `[claude-code:unrecognized_model]` and resolve `api_error_status: 404` in
under a second at a cost of $0 — the resolution is the API's, not a local
registry's, so the negative is free and the positive costs the one bounded turn
that contract test spends per literal.
"""

CONFIG_READS: Final[tuple[str, ...]] = (
    "${CLAUDE_CONFIG_DIR}/settings.json",
    "${HOME}/.claude/settings.json",
)
"""User-level settings whose content is hashed into the C-1025 probe digest.

`${CLAUDE_CONFIG_DIR}` first because it wins when set, and it is on the C-1008
allowlist; the `${HOME}` form is the default location. An entry naming a
variable the minimal environment does not carry is dropped by
`config_read_paths`, and the drop is itself a digest factor.

Deliberately over-declared: `--restricted` makes the *review* leg ignore user,
project and local settings files, so on that leg these files change nothing.
The probe leg reads them, and this adapter claims no `os` axis, so the digest
gates nothing here in any case — the honest reading is "files this harness
reads that could move its posture", and under-declaring is the direction that
would matter.
"""

CLASSIFY_STATUS: Final[Mapping[int, FailureReason]] = MappingProxyType(
    {
        401: FailureReason.UNAUTHENTICATED,
        429: FailureReason.RATE_LIMITED,
    }
)
"""HTTP status → reason, each cell proven by a recorded fixture (C-1012).

Claude Code reports the status of a failed API call in two places with the same
integer: `error_status` on a `system/api_retry` event and `api_error_status` on
the terminal `result` event. Only statuses a fixture in
`tests/contract/fixtures/claude/` actually shows appear here.

`403` is absent although C-1021 names it beside 429: no fixture records it, and
a cell inferred from a sibling status is the substring guess C-1012 forbids
wearing a different hat. An unrecorded status resolves `indeterminate`, which
stops the run just as `RATE_LIMITED` does.
"""

CLASSIFY_ERROR: Final[Mapping[str, FailureReason]] = MappingProxyType(
    {
        "authentication_failed": FailureReason.UNAUTHENTICATED,
        "rate_limit": FailureReason.RATE_LIMITED,
    }
)
"""Claude Code's own error name → reason, each cell proven by the same fixtures.

The second half of `classify`, for a shape that names the error without a
status. An exact-key lookup, never a substring test on a message.
"""

WIRE_JSON_SCHEMA: Final[str] = json.dumps(
    {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdict", "summary", "findings", "next_steps"],
        "properties": {
            "verdict": {"type": "string", "enum": ["approve", "needs-attention"]},
            "summary": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "severity",
                        "title",
                        "body",
                        "file",
                        "line_start",
                        "line_end",
                        "confidence",
                        "recommendation",
                    ],
                    "properties": {
                        "severity": {"type": "string", "enum": ["block", "high", "warn", "suggest"]},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "file": {"type": ["string", "null"]},
                        "line_start": {"type": ["integer", "null"]},
                        "line_end": {"type": ["integer", "null"]},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        "recommendation": {"type": ["string", "null"]},
                    },
                },
            },
            "next_steps": {"type": "array", "items": {"type": "string"}},
        },
    },
    separators=(",", ":"),
)
"""The `--json-schema` argument: the ADR wire object expressed as a JSON Schema.

`prompt.WIRE_SCHEMA` is prose a model reads; this is the schema Claude Code
validates against natively, which is why `review_prompt` renders no fenced-JSON
ask for this harness (`structured_output=True`). Nothing joins the two, so the
unit tier asserts this schema's property names against
`json.loads(prompt.WIRE_SCHEMA)` — otherwise they drift apart silently (WP5's
carry-forward row).

Hand-written rather than derived from `WIRE_SCHEMA`: that object is an *example*
whose values are prose (`"approve | needs-attention"`), so deriving a schema
from it means writing a converter that infers enums and nullability out of
English. One extra file and a guard test is smaller than that, and the guard is
what the carry-forward row asked for.
"""

_VERSION_RE: Final[re.Pattern[str]] = re.compile(r"\b(\d+\.\d+\.\d+)\b")
"""Reads the dotted version out of `2.1.260 (Claude Code)`."""

_RESULT_TYPE: Final[str] = "result"
"""`type` of the terminal event `parse` resolves on."""

_RETRY_SUBTYPE: Final[str] = "api_retry"
"""`subtype` of the `system` event Claude Code emits per internal retry attempt."""

_SHAPE_LIMIT: Final[int] = 40
"""Longest error NAME `_error_shape` repeats into an `indeterminate` detail.

Claude Code's own names — `authentication_failed`, `rate_limit`,
`model_not_found` — are well inside it. Anything longer is a message body
wearing the `error` key, and C-1035 keeps message bodies out of a `Review`.
"""


def containment_argv(cfg: HarnessConfig) -> tuple[str, ...]:
    """Return the containment flags, verbatim and in the order the argv carries them.

    The single source for both `containment_plan`'s `argv_evidence` and the
    words `prepare` emits, so the claim and the launch cannot disagree by
    construction — the disagreement C-1025 exists to catch is a bug this
    function makes unwritable.

    The run is `--safe-mode --restricted --strict-mcp-config
    --permission-prompts none --tools <comma-joined set>`, and it goes LAST
    among the flags so C-1025 rule 2 has a `-`-prefixed successor (`--`).

    Args:
        cfg: This harness's config, for `tools_allowed`.

    Returns:
        The evidence run.

    Raises:
        ConfigError: `cfg.tools_allowed` widens `READ_ONLY_TOOLS` (C-1016).
    """
    # `is None` and not a truth test: `narrow_tools` answers `None` for "unset"
    # and the requested tuple otherwise, and the EMPTY tuple is a legal explicit
    # narrow (`--tools ""` disables every tool). A truthiness check would read
    # that request as unset and hand the session the three defaults back.
    narrowed = narrow_tools(cfg.tools_allowed, READ_ONLY_TOOLS)
    tools = READ_ONLY_TOOLS if narrowed is None else narrowed
    return (
        "--safe-mode",
        "--restricted",
        "--strict-mcp-config",
        "--permission-prompts",
        "none",
        # Comma-joined: `--tools <tools...>` is variadic, and a space-separated
        # list swallows the next argv word — which is the review prompt.
        "--tools",
        ",".join(tools),
    )


def parse_version(text: str) -> str | None:
    """Read the version out of `claude --version` output.

    Args:
        text: The probe's merged output (`2.1.260 (Claude Code)`).

    Returns:
        The dotted version, or `None` when the output names none — an unknown
        version is recorded as `None`, which silences the C-1020 mismatch
        warning rather than inventing one (C-1035 forbids the invention).
    """
    found = _VERSION_RE.search(text)
    return found.group(1) if found is not None else None


def logged_out(text: str) -> bool:
    """Whether `claude auth status` positively reports no credential.

    Reads exactly one field, `loggedIn`. The surrounding object carries the
    account email, organisation id and organisation name; none of them may reach
    a `Review`, and none is retained past this call (C-1035).

    Unparseable output, or output with no `loggedIn` field, answers `False`.
    This is an availability preflight, not a containment gate: a shape nox
    cannot read is not evidence of a missing credential, and the review's own
    `classify` still catches one.

    The object is decoded from the FIRST `{` to the end of the text rather than
    from the first byte: C-1009 merges stderr into stdout and Claude Code writes
    advisories there (this adapter's own `error-401` fixture records one), so a
    single advisory line ahead of the object would otherwise defeat the whole
    preflight — and with it the ~185 s the preflight exists to save. Not a
    per-line scan, because the object is pretty-printed across eleven lines.

    Args:
        text: The probe's merged output.

    Returns:
        Whether the harness said it is logged out.
    """
    # `partition` rather than a slice: text carrying no `{` at all leaves both
    # halves empty, which decodes to `None` and fails open like every other
    # shape nox cannot read — no branch of its own.
    _, brace, body = text.partition("{")
    # `is False` rather than `not …`: only a positive `false` is a refusal, so a
    # missing field, a string, or an object nox cannot decode all fail open.
    status = _decode(brace + body)
    return status is not None and status.get("loggedIn") is False


class ClaudeAdapter:
    """Claude Code behind the `Adapter` protocol (SD § 6.1).

    Stateless: every method takes what it needs, and nothing is cached across
    reviews. The registry instantiates one per selection.
    """

    name: ClassVar[str] = "claude"
    """The `ADAPTERS` registry key, and the `PASSTHROUGH_ALLOW` key — whose entry
    for this harness is the EMPTY set, so no repository-supplied word reaches
    the argv at all (C-1023)."""

    BINARY: ClassVar[str] = "claude"
    """The executable, before any launcher prefix."""

    MODELS: ClassVar[Mapping[ModelClass, ModelSpec]] = MODELS
    """This harness's C-1030 table."""

    CONFIG_READS: ClassVar[tuple[str, ...]] = CONFIG_READS
    """The C-1025 digest's config files for this harness."""

    def probe(self, runner: Runner, cfg: HarnessConfig, env: Mapping[str, str], cwd: Path) -> HarnessInfo:
        """Establish that Claude Code is present, runnable and authenticated (C-1014).

        Two short local invocations through the configured launcher, both in the
        empty directory core minted:

        1. `--version`, which is what makes this more than `shutil.which` — a
           binary that exists and cannot run fails here;
        2. `auth status`, whose `loggedIn` field is the credential preflight.

        Neither invocation's output is retained: `parse_version` and
        `logged_out` consume it and nothing else sees it. `HarnessInfo` carries
        the parsed version and nothing from `auth status`, whose object holds
        the account's identity (C-1035). `Containment.raw` is the *review*
        stream, never a probe's.

        A non-zero `auth status` does NOT resolve `ABSENT`: `--version` has
        already established runnability, and `logged_out`'s fail-open answer is
        the documented one for a shape nox cannot read.

        This adapter does not implement C-1009's launcher session check. That
        check is a property of any configured launcher rather than of one
        harness, `probe_harness` is the single sanctioned route to every
        adapter's probe, and four `/proc` parsers would be the
        discipline-instead-of-mechanism failure C-1025 exists to remove — so it
        is reported as a cross-WP finding against `harness.py` rather than
        written here. The residual is bounded: `launcher` is in
        `config.PERMISSION_KEYS`, so a repository cannot set one and only the
        user's own trusted config can.

        Args:
            runner: The process seam. The adapter never touches `subprocess`.
            cfg: This harness's config, for its launcher prefix.
            env: The C-1008 minimal environment, built once before this call.
            cwd: A fresh empty directory nox owns.

        Returns:
            What the probe established: the version, `VERIFIED_AGAINST`,
            `ENUMERABLE_DENY | ENFORCED_READ_ONLY | STRUCTURED_OUTPUT`,
            `Liveness.SEMANTIC` and the resolved launcher.

        Raises:
            HarnessUnavailable: `ABSENT` when the binary is not on the minimal
                `PATH` or `--version` did not exit cleanly; `UNAUTHENTICATED`
                when `auth status` reported no credential. The detail is nox's
                own prose and never the probe's output — WP8 appends the
                C-1034(4) `config.auth_hint` from the names `minimal_env`
                dropped, which this adapter is not given.
        """
        launcher = cfg.launcher_for(self.BINARY) or Launcher(binary=self.BINARY)
        probed, lines = probe_run(runner, launcher, env, cwd, "--version", timeout_s=PROBE_TIMEOUT_S)
        version = "".join(lines)
        if probed.exit_code != 0:
            # `None` — the bound elapsed with the child still running — lands
            # here too: a `--version` that never returns is not a usable binary.
            raise HarnessUnavailable(FailureReason.ABSENT, f"{self.BINARY}: --version did not exit cleanly")
        # The exit status of the preflight is deliberately unread: `--version`
        # settled runnability, and `logged_out` is the only question left.
        _, auth_lines = probe_run(runner, launcher, env, cwd, "auth", "status", timeout_s=PROBE_TIMEOUT_S)
        auth = "".join(auth_lines)
        if logged_out(auth):
            raise HarnessUnavailable(
                FailureReason.UNAUTHENTICATED,
                f"{self.BINARY}: the harness reports no stored credential; sign in with its own login flow",
            )
        return HarnessInfo(
            name=self.name,
            version=parse_version(version),
            verified_against=VERIFIED_AGAINST,
            capabilities=frozenset(
                {Capability.ENUMERABLE_DENY, Capability.ENFORCED_READ_ONLY, Capability.STRUCTURED_OUTPUT}
            ),
            heartbeat_kind=Liveness.SEMANTIC,
            launcher=launcher,
        )

    def sandbox_probe(self, runner: Runner, ws: Workspace, info: HarnessInfo, env: Mapping[str, str]) -> bool:
        """Always `False`: this adapter claims no `os` axis (C-1025).

        Claude Code has no operating-system sandbox nox drives, so there is
        nothing to prove and `derive_containment` would refuse an `os` claim in
        any case. Returning `False` rather than raising is what makes "a harness
        with no sandbox probe cannot reach `os`" a property of the protocol.

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
        """Claim `tool-removal` on both axes, with the argv run that corroborates it (C-1007).

        Both axes are `harness` and neither is `os`: the mechanism is Claude
        Code's own tool set, visible in the resolved argv, not an operating
        system boundary. The evidence is `containment_argv`, so the claim is
        literally the words `prepare` emits. The two axes fall together by
        design — removing Bash removes writes and network reach in one move, and
        no single absent flag here affects only one of them.

        **The C-1025 residual, stated because the answer is not the obvious
        one.** None of the evidence flags has a second spelling in the 2.1.260
        `--help` (the only aliased pairs there are `--allowedTools /
        --allowed-tools` and `--disallowedTools / --disallowed-tools`, neither
        of which nox emits), so "name both spellings" has nothing to name. But
        the residual is *not* closed by the evidence set: `--mcp-config`,
        `--settings`, `--add-dir`, `--agents`, `--plugin-dir` and
        `--plugin-url` each defeat this containment while sharing no `key=`
        with any evidence word, so all four derivation rules still pass. Two
        other mechanisms close it, and they are the ones a reader must check
        rather than this docstring: `PASSTHROUGH_ALLOW["claude"]` is empty, so
        no repository word reaches the argv at all, and `harness.NEVER_EMITTED`
        refuses nox's own argv. Widening `argv_evidence` cannot help — evidence
        is a positive run nox must emit, not a denylist.

        Args:
            cfg: This harness's config.
            info: What the probe established. Unused: the containment does not
                vary by version within `VERIFIED_AGAINST`'s line.

        Returns:
            The claim.

        Raises:
            ConfigError: `cfg.tools_allowed` widens `READ_ONLY_TOOLS`.
        """
        del info
        return ContainmentPlan(
            mechanism="tool-removal",
            write_enforcement="harness",
            network_enforcement="harness",
            argv_evidence=containment_argv(cfg),
        )

    def prepare(
        self,
        ws: Workspace,
        info: HarnessInfo,
        cfg: HarnessConfig,
        instructions: str | None,
    ) -> Launch:
        """Build the review launch (E9a, C-1023, C-1028).

        Argv, composed as
        `police_passthrough(name, cfg.passthrough, nox_flags)` so passthrough
        goes first and nox's own flags last — vacuous for this harness, whose
        allowlist is empty, and kept because the rule is the contract's rather
        than this adapter's:

        `--print`, `--output-format stream-json`, `--verbose` — the per-event
        stream `Liveness.SEMANTIC` measures against. `--json-schema` with
        `WIRE_JSON_SCHEMA`, so the harness validates the wire object itself and
        `review_prompt` renders no fenced-JSON ask. `--no-session-persistence`,
        so a review of hostile repository content is not transcribed into
        `~/.claude/projects/` where the user's *other* sessions resume and read
        it — a write outside the repository, so it is hygiene rather than an
        enforcement axis and stays out of the evidence run. `--model` and
        `--effort` from `resolve_model`, both omitted entirely when the harness
        default is taken. Then `containment_argv`, then `--`, which ends it.

        **The prompt rides stdin** (E29). Claude Code exposes no user-prompt
        FILE flag, but `--print` reads the prompt from stdin when one is piped —
        verified live, `echo … | claude --print --tools Read Grep Glob --` → exit
        0 — so `Launch.stdin_path` names the file `review_prompt` already wrote
        and the prompt is never an argv word. It was one until E29, which put
        the whole rendered diff under the kernel's `MAX_ARG_STRLEN` and refused
        a whole-branch review, nox's primary use case, at 128 KiB. Two further
        properties come with the move: the diff is no longer world-readable in
        `/proc/<pid>/cmdline`, and `argv_prompt` — still the right answer for a
        harness that has only argv — is no longer called here.

        `--` still ends option parsing and still gives the evidence run the
        `-`-prefixed successor C-1025 rule 2 requires; it is now the last word.

        `Launch.env` is empty. This harness's containment is argv only, so there
        is nothing to declare and nothing `authorize` could refuse.

        Args:
            ws: The live workspace.
            info: What the probe established.
            cfg: This harness's config.
            instructions: Extra text from nox's own caller, never repository
                content. What is under review is `ws.scope`, not a parameter:
                the WP2 follow-up put it on `Workspace`, and a second source for
                one fact is the drift `harness.py` exists to prevent.

        Returns:
            The harness-level launch.

        Raises:
            ConfigError: A refused `passthrough` element (C-1023 — the claude
                allowlist is empty, so any element is refused), or a
                `tools_allowed` that widens. **No prompt-size refusal**: the
                prompt rides stdin, so `PROMPT_ARGV_LIMIT` does not apply (E29).
        """
        prompt_path, _ = review_prompt(ws, info, instructions)
        spec, _ = resolve_model(self.MODELS, cfg)
        # Both flags are omitted entirely when the harness default is taken, so
        # a run with no configured class carries no model word at all (C-1030).
        model = () if spec is None else ("--model", spec.model)
        effort = () if spec is None or spec.effort is None else ("--effort", spec.effort)
        nox_flags = (
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
            "--json-schema",
            WIRE_JSON_SCHEMA,
            "--no-session-persistence",
            *model,
            *effort,
            # The containment run goes last among the flags and `--` follows it,
            # which is what gives C-1025 rule 2 its `-`-prefixed successor: with
            # the prompt directly behind `--tools`, a variadic parse would read
            # the prompt as a fourth tool and derivation would still corroborate.
            *containment_argv(cfg),
            "--",
        )
        return Launch(argv=police_passthrough(self.name, cfg.passthrough, nox_flags), stdin_path=prompt_path)

    def classify(self, err: Mapping[str, object]) -> FailureReason | None:
        """Map one observed Claude Code error object to a reason, or decline (C-1012).

        Status first, then the harness's own error name, because the status is
        the field both carriers share: `system/api_retry` reports
        `error_status`, the terminal `result` event reports `api_error_status`,
        and both are the same integer.

        `None` wherever no recorded fixture proves the cell — the run then
        resolves `indeterminate` with the raw name stamped, which still stops it
        (C-1021). Never a substring match on a message.

        Args:
            err: One decoded object from the stream. Untrusted: a status that is
                not an integer, or an error name that is not a string, declines
                rather than raising.

        Returns:
            The reason, or `None`.
        """
        for status in (err.get("error_status"), err.get("api_error_status")):
            # `isinstance(True, int)` holds, so a JSON `true` in a status slot
            # would otherwise be read as the integer 1.
            if isinstance(status, int) and not isinstance(status, bool) and status in CLASSIFY_STATUS:
                return CLASSIFY_STATUS[status]
        name = err.get("error")
        return CLASSIFY_ERROR.get(name) if isinstance(name, str) else None

    def parse(self, lines: Iterable[str], exit_code: int, hb: Heartbeat) -> ParsedOutput:
        """Resolve the `stream-json` output to a tri-state result (C-1011).

        The terminal `result` event decides, and only in one direction: an event
        whose `is_error` is the boolean `False` — tested by identity, so an
        absent or `null` field is not success by elimination on the one field
        that decides it — carrying a well-formed `structured_output` object is
        the single route to `status="ok"`. Everything else resolves `error` or
        `indeterminate`.

        **`subtype` is not the gate, and the fixture is why.** A 401 run's
        terminal event reads `"subtype": "success"` while `"is_error": true` and
        `"api_error_status": 401` — an adapter keyed on `subtype` would report
        an authentication failure as a clean review.

        Order:

        1. non-JSON lines are ignored, not fatal — C-1009 merges stderr into
           stdout and Claude Code writes advisory lines there
           (`⚠ claude.ai connectors are disabled…`);
        2. a `result` event with `is_error` false and a well-formed
           `structured_output` → `ok`, with `total_cost_usd` as `cost_usd`;
        3. a `result` event with `is_error` false and `structured_output`
           absent or `null` → `indeterminate`/`MALFORMED_OUTPUT`. This is a real
           and recorded shape, not a defensive branch: a model that declines to
           call the `StructuredOutput` tool ends the run this way;
        4. a `result` event whose `is_error` is anything but the boolean
           `False` — an error, or a shape that never positively reported
           success — → `classify`, else `indeterminate` naming the status or
           error name the event carried (`_error_shape`);
        5. no `result` event → `KILLED` when `reason_for_exit` says so, else the
           last `api_retry` error through `classify`, else `indeterminate`.

        **Rule 5 is where this adapter diverges from the other three, and the
        divergence is deliberate.** codex, opencode and copilot read the harness's
        own reported error BEFORE the exit status; this one reads
        `reason_for_exit` first, so a retry-429 stream that exited 143 resolves
        `KILLED` here and `RATE_LIMITED` there on identical evidence. It is not
        reachable through nox — `supervise` stamps `TIMED_OUT` (`runner.py`)
        before a 143 reaches `parse`, so only an external SIGTERM produces the
        shape — and reordering the one adapter that HAS a live retry ladder is a
        behaviour change bought for an unreachable row. Named rather than fixed,
        and named here rather than left to a universal the other three assert.

        Step 5 is where SD § 7.1's `exit 143` row lands, and its position is the
        row's whole content: the exit status labels a run whose stream
        established nothing of its own, and never overrules a terminal event
        that did (C-1011, SD § 4.3). Three of the four adapters resolve it there;
        this one resolves it a step earlier, per the divergence noted above.

        Every field of `structured_output` is untrusted: an unrecognised
        severity fails to `block` (`to_severity`), an unrecognised verdict fails
        to `needs-attention` — the same direction, and never to `approve` — a
        non-integer line number becomes `None`, an unrecognised confidence
        becomes `medium`, and `Finding.file` is normalized by
        `ParsedOutput.__post_init__`. `next_steps` is accepted and discarded
        (D-i).

        Args:
            lines: The merged output stream, in order.
            exit_code: What the child exited with. A hint; never the gate.
            hb: Progress evidence. Unused — the stream carries the outcome.

        Returns:
            What the output establishes.
        """
        del hb
        # Materialized once: `lines` is an `Iterable`, and `raw` and the event
        # scan each read the whole stream — a generator would leave one empty.
        stream = tuple(lines)
        # `"".join`, never `"\n".join`: a drained line KEEPS the newline
        # `readline` produced (`runner.py`'s `_drain`) and `supervise` hands it
        # to `on_line` unchanged, so this is the verbatim reconstruction C-1018
        # calls "as the supervisor delivered it" — joining with a newline puts a
        # blank line between every record.
        raw = "".join(stream)
        events = [event for event in (_decode(line) for line in stream) if event is not None]
        terminal = [event for event in events if event.get("type") == _RESULT_TYPE]
        if terminal:
            # The LAST one: a stream carrying two would otherwise resolve on the
            # older, and the run's outcome is whatever it ended with.
            return self._resolved(terminal[-1], raw)
        reason = reason_for_exit(exit_code)
        if reason is not None:
            return _failed(raw, reason)
        # Nothing terminal and no kill: the retry ladder is the only evidence
        # the run left behind, and an empty stream classifies as `{}`, which
        # declines — so a silent clean exit can never resolve `ok` (C-1011).
        retries = [event for event in events if event.get("subtype") == _RETRY_SUBTYPE]
        retried = self.classify(retries[-1] if retries else {})
        return _failed(raw, retried) if retried is not None else indeterminate(raw, "no terminal result event")

    def _resolved(self, event: Mapping[str, Any], raw: str) -> ParsedOutput:
        """Resolve the terminal `result` event, the one place `ok` is reachable (C-1011).

        Args:
            event: The decoded terminal event.
            raw: The whole stream, retained unconditionally (C-1018).

        Returns:
            What the event establishes.
        """
        # `is not False`, not a truth test: `is_error` is the single field
        # standing between this event and `ok`, and an absent or `null` one is
        # not a positive report of success. Reaching `ok` by elimination on it
        # is exactly what C-1011 forbids.
        if event.get("is_error") is not False:
            failed = self.classify(event)
            return _failed(raw, failed) if failed is not None else indeterminate(raw, _error_shape(event))
        payload = event.get("structured_output")
        if not isinstance(payload, dict):
            # Recorded, not defensive: a model that declines to call the
            # `StructuredOutput` tool ends the run with the field absent.
            return indeterminate(raw, "no structured_output object")
        wire = cast("dict[str, Any]", payload)
        reported = wire.get("findings")
        items = cast("list[object]", reported) if isinstance(reported, list) else []
        cost = event.get("total_cost_usd")
        return ParsedOutput(
            status="ok",
            # An unrecognised word fails toward `needs-attention` — the same
            # direction `to_severity` fails, and never toward `approve`.
            verdict="approve" if wire.get("verdict") == "approve" else "needs-attention",
            findings=tuple(_finding(cast("Mapping[str, Any]", item)) for item in items if isinstance(item, dict)),
            summary=_text(wire.get("summary")),
            detail=None,
            raw=raw,
            reason=None,
            cost_usd=cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None,
        )

    def on_line(self, line: str) -> bool:
        """Whether one output line is a semantic event, answered honestly (C-1010).

        `True` for a line that decodes to a JSON object carrying `type` — every
        `stream-json` record, `system/api_retry` included, because a retry *is*
        a real event and the harness is demonstrably alive. `False` for the
        stderr advisories C-1009 merges into the same stream, which are bytes
        and not progress.

        The honest answer has a cost worth naming: a 429 retry storm emits an
        event a minute for ten minutes, so the C-1010 silence window never
        fires and the wall clock is the only bound during exactly the pathology
        a silence window would otherwise catch. Answering `False` to buy a
        faster timeout would be a lie about a live harness, and the fix belongs
        in `supervise` — whose `on_line -> bool` has no abort channel — not
        here.

        Not a member of the `Adapter` protocol as WP6 shipped it. The WP3
        carry-forward row addresses `on_line` to WP7a-d and `supervise` takes
        one, so the adapter that knows the dialect owns it; the protocol gap is
        reported as a cross-WP finding rather than fixed by editing
        `harness.py`.

        Args:
            line: One line of merged output.

        Returns:
            Whether it was a semantic event.
        """
        event = _decode(line)
        return event is not None and "type" in event


def _failed(raw: str, reason: FailureReason) -> ParsedOutput:
    """Build the `error` result for a reason this adapter established (C-1011).

    Args:
        raw: The whole stream, retained unconditionally (C-1018).
        reason: What the stream or the exit status established.

    Returns:
        An `error` result. `verdict` is `None`, so no route through here can
        reach a success answer.
    """
    return ParsedOutput(
        status="error",
        verdict=None,
        findings=(),
        summary="",
        detail=f"the review did not complete: {reason.value}",
        raw=raw,
        reason=reason,
    )


def _finding(item: Mapping[str, Any]) -> Finding:
    """Build one `Finding` out of one untrusted wire object (C-1018, C-1019).

    `ParsedOutput.__post_init__` re-runs `safe_finding_file` and `to_severity`
    over whatever this returns, so the traversal and severity checks are the
    type's rather than four adapters'. Both are still answered here, for the one
    reason that survives the redundancy: `Finding` DECLARES `severity` as one of
    four words and `file` as `str | None`, and a wire object carrying a number in
    either slot would reach `safe_finding_file` as a `TypeError` — a traceback
    past `review()`'s totality rather than a run outcome. The fields the type
    does not own at all — the line span and the confidence — are answered here
    and nowhere else.

    Args:
        item: One decoded element of the wire object's `findings` array.

    Returns:
        The finding, with every field a consumer acts on made safe.
    """
    location = item.get("file")
    recommendation = item.get("recommendation")
    confidence = item.get("confidence")
    return Finding(
        severity=to_severity(item.get("severity")),
        title=_text(item.get("title")),
        body=_text(item.get("body")),
        file=location if isinstance(location, str) else None,
        line_start=_line(item.get("line_start")),
        line_end=_line(item.get("line_end")),
        # `medium` rather than a fail-high or fail-low default: confidence
        # ranks a finding a human already has to read, so neither direction is
        # the honest reading of a word the harness invented.
        confidence=confidence if confidence in ("high", "medium", "low") else "medium",
        recommendation=recommendation if isinstance(recommendation, str) else None,
    )


def _text(value: object) -> str:
    """Keep a wire string only when it is one.

    Args:
        value: Whatever the wire carried in a text slot.

    Returns:
        The string, or `""`. `str(value)` would render a JSON `null` as the
        literal `"None"` and an object as its Python repr, and both reach a
        human as if the harness had written them.
    """
    return value if isinstance(value, str) else ""


def _error_shape(event: Mapping[str, Any]) -> str:
    """Name the shape of a terminal error `classify` declined, for `indeterminate` (C-1035).

    `indeterminate` documents the error name as "the one piece of harness output
    that travels into `detail`, and deliberately": without it the detail names
    no shape a human could add to `CLASSIFY_STATUS` or `CLASSIFY_ERROR`, which
    is the whole reason that argument was made. So the status integer or the
    harness's own error name is repeated — and nothing else. A `str` carrying
    whitespace, or one longer than `_SHAPE_LIMIT`, is a message body rather than
    a name, and a message body is what C-1035 keeps out of a `Review`; it falls
    back to the wording that names no shape at all.

    Args:
        event: The decoded terminal event.

    Returns:
        The phrase `indeterminate` renders into its detail.
    """
    for value in (event.get("api_error_status"), event.get("error_status"), event.get("error")):
        # `isinstance(True, int)` holds, so a JSON `true` would otherwise be
        # reported as the status integer 1.
        if isinstance(value, int) and not isinstance(value, bool):
            return f"a terminal error with status {value}"
        if isinstance(value, str) and len(value) <= _SHAPE_LIMIT and value.split() == [value]:
            return f"a terminal error named {value}"
    return "a terminal error"


def _line(value: object) -> int | None:
    """Keep a wire line number only when it is one.

    Args:
        value: Whatever the wire carried in a line-number slot.

    Returns:
        The integer, or `None`. `bool` is excluded although it is an `int`: a
        JSON `true` is not line 1.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _decode(line: str) -> dict[str, Any] | None:
    """Decode one stream line to a JSON object, or `None`.

    Args:
        line: One line of merged output.

    Returns:
        The object, or `None` for a blank line, a non-JSON advisory, or a JSON
        value that is not an object.
    """
    try:
        decoded: object = json.loads(line)
    except ValueError:
        return None
    return cast("dict[str, Any]", decoded) if isinstance(decoded, dict) else None
