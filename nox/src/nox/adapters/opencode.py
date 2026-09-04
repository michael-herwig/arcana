"""The OpenCode adapter — reached only behind a launcher, contained only by config.

C-1007(opencode), C-1012(opencode), C-1014(a3), C-1023, C-1030(opencode),
C-1032, D-s, S-1003.

Three things make this the weakest of the four adapters, and each is stamped
rather than argued away:

1. **No binary on `PATH`.** OpenCode is reached through a package runtime —
   `ocx package exec <pinned coordinate> -- opencode …` — configured as
   `[harness.opencode] launcher` and paired with `BINARY` by
   `HarnessConfig.launcher_for`. `launch_argv` resolves the PREFIX's head, so
   what `execve` runs is the wrapper and the harness binary behind the `--` is
   the wrapper's to find.
2. **Containment is a config convention, not an enforced boundary.**
   `OPENCODE_CONFIG_CONTENT` carries an inline deny map the binary was observed
   to read; what was NOT observed is the resolution order that makes the deny
   win. Both axes are therefore `attested` and `ENFORCED_READ_ONLY` is absent
   from `capabilities` — the launch gate lets it through, since that capability
   is not in `REQUIRED`, and the run is stamped `enforced_read_only=False`.
3. **The prompt has no file channel.** `opencode run [message..]` takes its
   message as a positional and stdin is `DEVNULL` by C-1009, so the rendered
   prompt rides argv through `argv_prompt`, which is what enforces
   `PROMPT_ARGV_LIMIT`.

**What the live 1.18.22 binary refuted, recorded here because Step 11.2 records
it and E3 makes the committed fixture authoritative over the design record:**

- SD § 6.3 names `--agent explore` as half the containment mechanism. `explore`
  is a SUBAGENT: `opencode run --agent explore` answers
  `agent "explore" is a subagent, not a primary agent. Falling back to default
  agent` and reviews under the default agent anyway. It is not emitted — a
  no-op that adds a line to the stream `parse` reads is worse than nothing.
- SD § 6.3 records that no effort knob exists. `run --help` carries `--variant`
  (`provider-specific reasoning effort`), and it is emitted when a trusted
  config supplied one.
- `capability.Capability`'s evidence table records that OpenCode reports no
  cost. A real run's `step_finish` event carries `part.cost`, and `parse` reads
  it. That table is WP1's file and is not edited here; the correction is
  reported.
- The launcher does not escape nox's session or process group: `ocx package
  exec` `execve`s, so the harness IS the direct child. That is a property of
  the pinned coordinate the contract tier asserts, **not** of an arbitrary
  `launcher` prefix — a hand-written `setsid` wrapper would escape and nothing
  in this module could see it, since a descendant's session id is not readable
  without a process table. The contract tier owns that check (C-1009).
- **`--pure` does NOT stop a repository-authored `.opencode/plugins/` module
  from executing.** Probed on 1.18.22 in a directory holding one, in both flag
  positions (`opencode --pure run …` and `opencode run --pure …`): an ordinary
  startup ran the plugin and so did the flag'd one. The plan's 7c bullet made
  emission conditional on the opposite result, so this is reported rather than
  quietly kept — see `PURE_FLAG` for what the flag is worth and what actually
  closes the hole.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from itertools import islice
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final, Literal, cast

from nox.capability import Capability, Launcher
from nox.config import AUTH_ENV_HINTS, AUTH_HINT_TRAILER, ConfigError, narrow_tools
from nox.harness import (
    ContainmentPlan,
    HarnessInfo,
    HarnessUnavailable,
    Launch,
    ParsedOutput,
    argv_prompt,
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
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

    from nox.capability import ModelClass, ModelSpec
    from nox.config import HarnessConfig
    from nox.outcome import Verdict
    from nox.runner import Runner
    from nox.workspace import Workspace

# ── Shipped literals ─────────────────────────────────────────────────────────

VERIFIED_AGAINST: Final[str] = "1.18.22"
"""The release `tests/contract/fixtures/opencode/` was recorded from (E3, C-1020).

Set from a live re-probe at implementation time, never copied from a document.
A mismatch warns through `version_warning` and never refuses.
"""

CONFIG_ENV: Final[str] = "OPENCODE_CONFIG_CONTENT"
"""The environment name carrying the inline deny config — the whole mechanism.

**Never `OPENCODE_CONFIG`.** That names a config FILE, and a project
`opencode.json` is reported to outrank it; only the inline form is reported to
outrank the project file, and neither claim was verified — which is exactly why
both axes stay `attested` (SD § 6.3, R9). Under C-1005 the checkout carries no
`.opencode/` or `opencode.json` at all, so the precedence question is moot at
review time and this variable is the belt for a neutralization that
under-matched.

Deliberately absent from `harness.NEVER_SET`, and that absence is load-bearing:
setting it IS this adapter's containment. It is in `config.NEVER_FORWARD`, so it
can never arrive from the user's environment and collide with the value the plan
declares.

**Observed on 1.18.22**, which is what makes it a mechanism rather than a claim:
`opencode --pure agent list` prints each agent's resolved permission rules, and
the value `deny_config` renders appends `{"permission":"*","action":"deny"}`
followed by one allow rule per member of `ALLOWED_TOOLS`. What is still
unobserved is which end of that list wins, and that is the whole of `attested`.
"""

ALLOWED_TOOLS: Final[tuple[str, ...]] = ("read", "grep", "glob", "list")
"""The capabilities a reviewer keeps — this adapter's own containment set (C-1016).

`narrow_tools` validates `[harness.opencode] tools_allowed` against exactly
this, so config can only ever remove a name. It is the set the
`ENUMERABLE_DENY` capability claims, so an adapter that ignored the config key
while declaring the capability would be claiming an enumerable deny set nobody
can narrow.

Drawn from the permission vocabulary observed on 1.18.22 — `*, bash, doom_loop,
edit, external_directory, glob, grep, list, plan_enter, plan_exit, question,
read, task, todowrite, webfetch, websearch`.
"""

PURE_FLAG: Final[str] = "--pure"
"""`run without external plugins` — the one argv-visible knob this adapter emits.

**Probed on 1.18.22 and REFUTED as a plugin guard.** In a directory holding
`.opencode/plugins/evil.ts`, an ordinary `run` executed the plugin and so did
the same `run` with this flag, in either flag position. SD § 6.3's reading of it
is not what the binary does, and E3 makes the probe authoritative: the flag is
emitted as defence in depth over the *config-declared* plugin list its own help
text names, and it is **not** what closes the repository-authored plugin route.

What closes that route is core, on both paths a harness can start on:
`workspace.NEUTRALIZE_DIRS` carries `.opencode`, so C-1005 drops the directory
out of both synthetic trees before a review ever runs, and `probe_cwd` mints a
fresh empty directory for the probe. Neither depends on a flag.

It stays in `argv_evidence` as a derivation tripwire rather than as proof: the
mechanism is `config-deny`, which `_mechanism_corroborated` backs on
`env_evidence` alone, so this word promotes no axis — it only makes a launch
that lost it fail derivation. That is the shape the plan asked for minus the
proof, and the missing proof is reported rather than assumed.

**Residual, stated:** yargs enables boolean negation, so `--no-pure` lifts the
flag while leaving `--pure` contiguous in argv — `_names_option` does not match
it and it is not in `DENIED_FLAGS`. Unreachable only because
`PASSTHROUGH_ALLOW["opencode"]` is empty, and a future allowlist entry reopens
it. Reported to WP6 as a `DENIED_FLAGS` addition; it cannot go in
`argv_evidence`, where an absent word fails rule 1.
"""

PROBE_TIMEOUT_S: Final[int] = 120
"""Wall-clock bound for one probe spawn — not `HarnessConfig.timeout`, which bounds a review.

Wide because the launcher's first run may unpack a pinned package; a
`--version` that has not answered in two minutes is a broken launcher rather
than a slow model.

Paired with `Liveness.PROCESS_ONLY`, so this constant really is the bound. A
probe emits no structured events at all, so supervising it as `SEMANTIC` would
put a 120-second silence window over a stream that can never reset one — the
wall clock would be decorative and raising this number would change nothing.
"""

_VERSION_RE: Final[re.Pattern[str]] = re.compile(r"^\s*v?(\d+\.\d+\.\d+\S*)\s*$")
"""One whole output line that is nothing but a version.

Anchored on the whole line rather than searched, because the launcher may print
its own cache or download lines around the harness's answer, and a substring
search over those would report the wrapper's version as the harness's. No match
is `version=None` — C-1020 warns on a mismatch and never invents one — never
`ABSENT`, which is reserved for a binary that did not run.
"""

_ANSI_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
"""CSI escape sequences, stripped before any line of harness output is matched.

The live binary colours `providers list`; the committed fixtures are the same
bytes with the colour removed. Without this the two disagree, and a check
written against the fixture would be looser or tighter than the one that runs.
"""

_PROVIDER_BULLET: Final[str] = "●"
"""The glyph `providers list` prefixes each configured provider row with.

The C-1034(4) preflight tests for the PRESENCE of a provider, never for the
absence of one. `0 credentials` cannot be the test: the recorded authenticated
fixture carries that exact string too — that machine's provider rode
`GITHUB_TOKEN` — and a substring check would also match `10 credentials`. So
this asks the positive question, and no bullet is `UNAUTHENTICATED`.

Matched at the head of a colour-stripped line rather than anywhere in one: the
merged stream carries the launcher's own progress output too, and a spinner
frame or a package name carrying this glyph would otherwise read as a
configured provider and pass an unauthenticated harness through to a review.

Failure direction: a glyph change refuses a harness that would have worked,
which costs a skipped review. The inverse — treating an unauthenticated harness
as ready — spends a review that resolves `indeterminate` and tells the user
nothing about why. Both fixtures pin the glyph and the contract tier re-pins it
against the real binary.
"""

_MAX_ERROR_NAME: Final[int] = 64
"""Bytes of a harness-reported error name that may reach `Review.detail` (C-1035).

The one piece of harness output that travels into nox's own prose, so it is
bounded and stripped of anything unprintable before it gets there: an
unbounded name is a channel for a whole injected paragraph, and an escape
sequence in one repaints the reader's terminal.
"""

_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"```(?:json)?[^\S\n]*\n(.*?)\n?```", re.DOTALL)
"""A fenced block, for the reply shape the ask does not require but a model volunteers.

The run before the newline is `[^\\S\\n]*` and deliberately not `\\s*`: `\\s`
contains `\\n`, so `\\s*\\n` is an ambiguous quantifier pair and a reply of one
fence marker followed by a long run of newlines backtracks quadratically. That
input is attacker-reachable — the diff under review can ask the reviewer to
echo it — and `parse` runs after `supervise` has released its deadline, so the
hang would be unbounded.

`prompt._SCHEMA_ASK` asks for `a single JSON object and nothing else`, and the
recorded 1.18.22 answer was a BARE object — so bare is the primary shape and the
fence is the fallback, not the reverse. SD § 6.3's "nox extracts a fenced block"
is refuted by the shipped prompt and this adapter's own committed fixture; E3
makes the fixture authoritative.
"""

_VERDICTS: Final[frozenset[str]] = frozenset({"approve", "needs-attention"})
"""The two words `ParsedOutput.verdict` accepts, as a membership test over untrusted input."""

Confidence = Literal["high", "medium", "low"]
"""How strongly the harness stands behind one finding — `Finding.confidence`'s domain."""

_CONFIDENCES: Final[tuple[Confidence, ...]] = ("high", "medium", "low")
"""The three words a `Finding.confidence` may carry, in `Finding`'s own order."""


def deny_config(allowed: Iterable[str]) -> str:
    """Render the inline `OPENCODE_CONFIG_CONTENT` value for one launch.

    Deny-first (`"*": "deny"`) with `allowed` added back, rather than an
    enumeration of the writing tools: an enumeration has to be re-derived every
    release, while a wildcard deny fails toward refusal when the permission
    vocabulary grows. `ask` is never used — a headless run has nobody to ask,
    and an `ask` rule is a hang.

    The single producer, called by both `containment_plan` and `prepare`, which
    is what keeps the plan's `env_evidence` and the launch's `env` byte-equal:
    `derive_containment` matches that value EXACTLY, so two independent
    renderings would be a containment downgrade nobody could see in review.

    Args:
        allowed: The capabilities to permit, in order.

    Returns:
        A compact JSON object. Separators are pinned so the string does not move
        with a formatting default.
    """
    permission = {"*": "deny"} | {tool: "allow" for tool in allowed}
    return json.dumps({"permission": permission}, separators=(",", ":"), sort_keys=False)


def _decode(text: str) -> object:
    """Decode one JSON document, or answer `None` for anything that is not one.

    Args:
        text: One output line, or a whole model reply.

    Returns:
        The decoded value, or `None`. `json.JSONDecodeError` is a `ValueError`,
        and both a truncated line and a plain warning line arrive here.
    """
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        # `RecursionError` is not a `ValueError`: CPython's decoder raises it on
        # deeply nested input, and one line of `[[[[…` well under `READ_BOUND`
        # would otherwise escape `parse` and break `review()`'s C-1029 totality.
        return None


def _mapping(value: object) -> Mapping[str, object] | None:
    """Read one decoded value as a JSON object, or decline (C-1019).

    The single narrowing point for untrusted output: every field this module
    reads comes through it, so `"part": 3` is a declined object rather than an
    `AttributeError` escaping `parse` past `review()`'s C-1029 totality.

    Args:
        value: A decoded JSON value.

    Returns:
        The object, or `None`. The cast is sound because `json.loads` only ever
        produces `dict[str, Any]`.
    """
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else None


def _version_of(lines: Sequence[str]) -> str | None:
    """Read the harness's own version out of a probe's output (C-1020).

    Args:
        lines: The merged output of the version spawn, in order.

    Returns:
        The LAST whole line that is nothing but a version, or `None` when the
        launcher answered and no line was one. Last rather than first, because
        the launcher's own cache or download lines come before the harness's
        answer and one of them printing a bare `x.y.z` would otherwise report
        the wrapper's version as the harness's — the substitution the
        whole-line anchoring exists to prevent.
    """
    found = [match.group(1) for line in lines if (match := _VERSION_RE.match(line)) is not None]
    return found[-1] if found else None


def _wire_object(answer: str) -> Mapping[str, object] | None:
    """Extract the reply object from a model's answer — bare first, then the last fence.

    Never a first-`{`-to-last-`}` scan: the diff under review is
    attacker-controlled text that the model may quote back, and such a scan
    would let it supply the verdict.

    Exactly two candidates, and the LAST fence is the only fence considered.
    Walking every fence backwards would mean that a model whose real answer is
    malformed falls back to an earlier block — which on a hostile branch is the
    fenced object the reviewer quoted out of the diff. A malformed final answer
    is `indeterminate`, never someone else's object.

    Args:
        answer: The LAST `text` part of the stream — the reply. Earlier parts
            are per-step narration, not the answer.

    Returns:
        The object, or `None` when neither extraction produced one.
    """
    for candidate in (answer, *_FENCE_RE.findall(answer)[-1:]):
        decoded = _mapping(_decode(candidate))
        if decoded is not None:
            return decoded
    return None


def _bounded_name(error: Mapping[str, object]) -> str:
    """Bound and clean the one piece of harness output that reaches `detail` (C-1035).

    `islice` bounds the filter itself rather than its result: `name` is
    model-controlled and arrives over the wire, so a cap applied only to the
    joined string bounds the output and not the work — the shape `prompt._fence`
    and `workspace._sanitize` were each fixed for. Stopping at `_MAX_ERROR_NAME`
    survivors is bit-identical to filtering the whole name and slicing it, and a
    **100 000-character** name measured 1.83 ms and 878 KiB of transient
    allocation before, 0.002 ms and 1 KiB after — a 1010x wall and 892x memory
    ratio (CPython 3.14 on Linux). The cap
    counts the characters that SURVIVE, so it cannot move in front of the filter
    — one control character per printable one would halve an input-side cut, which
    `test_an_error_name_is_cut_after_its_non_printables_are_dropped_and_never_before`
    pins.

    Args:
        error: One decoded error object.

    Returns:
        Its `name`, stripped of every non-printable character — a newline forges
        a second line of nox's own prose and an escape sequence repaints the
        reader's terminal — and cut to `_MAX_ERROR_NAME`.
    """
    return "".join(islice((char for char in str(error.get("name")) if char.isprintable()), _MAX_ERROR_NAME))


def _text_or_none(value: object) -> str | None:
    """Read an untrusted field as a string, or drop it (C-1019).

    Args:
        value: Whatever the wire carried.

    Returns:
        The string, or `None`.
    """
    return value if isinstance(value, str) else None


def _int_or_none(value: object) -> int | None:
    """Read an untrusted field as a line number, or drop it (C-1019).

    Args:
        value: Whatever the wire carried.

    Returns:
        The integer, or `None`. `bool` is excluded because it is an `int`
        subclass and `"line_start": true` is not a line number.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _confidence(value: object) -> Confidence:
    """Map an untrusted confidence word onto `Finding`'s three, failing to the middle.

    Unlike `to_severity`, neither direction of a wrong answer is dangerous here:
    confidence is advisory and carries no gate, so the honest default is the
    one that claims nothing.

    Args:
        value: Whatever the wire carried.

    Returns:
        One of `high`, `medium`, `low`.
    """
    for known in _CONFIDENCES:
        if known == value:
            return known
    return "medium"


def _finding(entry: Mapping[str, object]) -> Finding:
    """Build one `Finding` out of untrusted wire fields (C-1019).

    Every slot is coerced before it reaches a typed field: a harness emitting
    `"file": 123` would otherwise raise a `TypeError` out of `parse` and escape
    `review()`'s C-1029 totality as a traceback. The traversal check on `file`
    and the final severity normalization are `ParsedOutput.__post_init__`'s,
    which is what makes them properties of the type rather than of this adapter.

    Args:
        entry: One decoded element of the reply's `findings` list.

    Returns:
        The finding.
    """
    return Finding(
        severity=to_severity(entry.get("severity")),
        title=_text_or_none(entry.get("title")) or "",
        body=_text_or_none(entry.get("body")) or "",
        file=_text_or_none(entry.get("file")),
        line_start=_int_or_none(entry.get("line_start")),
        line_end=_int_or_none(entry.get("line_end")),
        confidence=_confidence(entry.get("confidence")),
        recommendation=_text_or_none(entry.get("recommendation")),
    )


def _unusable(raw: str, cost: float | None, detail: str, exit_code: int) -> ParsedOutput:
    """Resolve a run whose output carried no usable answer (C-1011).

    Never `ok`, and never by elimination: this is the one constructor `parse`
    reaches for when an extraction failed, so a success return cannot be
    written by leaving a branch out.

    **The one place this adapter reads the exit status**, and the reason it is
    read here rather than at the top of `parse`: SD § 7.1 gives exit 143 a
    single row — `error` / `KILLED`, "labelled 'we killed it', never generic
    failure" — while SD § 4.3 requires that the exit code gate nothing. Both
    hold at once only where the stream established nothing of its own, which is
    exactly this constructor. A run that emitted an `error` event, or a usable
    verdict, resolves on that and never on the status of the process that
    carried it; a run that emitted neither would otherwise be reported as
    `MALFORMED_OUTPUT` — "the harness produced garbage" — when the truth is that
    nox terminated it. Three of the four adapters resolve the row this way;
    `claude` is the exception, and deliberately so — it reads `reason_for_exit`
    ahead of its `api_retry` ladder, so harness-reported retry evidence on a run
    that exited 143 resolves there as `KILLED` where it resolves here through
    the reported error. Unreachable through nox (`supervise` stamps
    `TIMED_OUT` before `parse` sees a 143), so it is named rather than fixed.

    Args:
        raw: The output as the supervisor delivered it (C-1018).
        cost: What the stream reported, which a failed answer still spent.
        detail: nox's OWN account of what was unusable. Never harness output.
        exit_code: What the child exited with. A label only, and only for the
            one status `reason_for_exit` maps.

    Returns:
        `error`/`KILLED` for nox's own stop, else `indeterminate`/
        `MALFORMED_OUTPUT`.
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
        cost_usd=cost,
    )


class OpenCodeAdapter:
    """OpenCode behind `ocx package exec`, contained by an inline deny config."""

    name: ClassVar[str] = "opencode"
    BINARY: ClassVar[str] = "opencode"

    MODELS: ClassVar[Mapping[ModelClass, ModelSpec]] = MappingProxyType(
        {
            "fast-balanced": "github-copilot/gpt-5.6-luna",
            "deep-reasoning": "github-copilot/gpt-5.6-sol",
        }
    )
    """Capability class → literal (C-1030). **`provider/`-prefixed** — a bare name does not resolve.

    Both entries name non-Anthropic backends on purpose: the product claim is a
    cross-model reviewer, and the driver is Claude. Bare `str` values, so no
    effort rides the shipped table; `--variant` is emitted only when a trusted
    config supplies BOTH `model_literal` and `effort`, since `resolve_model`
    surfaces an effort only through `HarnessConfig.model_spec()`.

    OpenCode is BYOK, so which provider a literal resolves against is the user's,
    and `probe` reports what the harness can authenticate as before a review
    spends a token on the answer.

    **Residual, reported to WP6/WP8:** `asymmetry_warning` prefix-matches
    `ASYMMETRY_NEGATIVE`'s bare reviewer ids against the resolved literal, and a
    `provider/`-prefixed literal can never match one — so C-1036 is structurally
    silent for this harness. Latent today (no listed pair names a model this
    table carries) and not fixable here: the comparison is core's.
    """

    CONFIG_READS: ClassVar[tuple[str, ...]] = (
        "${XDG_CONFIG_HOME}/opencode/opencode.json",
        "${XDG_CONFIG_HOME}/opencode/opencode.jsonc",
        "${HOME}/.config/opencode/opencode.json",
        "${HOME}/.config/opencode/opencode.jsonc",
    )
    """The user-level config files hashed into the C-1025 digest, in precedence order.

    Both roots, because `XDG_CONFIG_HOME` is unset on an ordinary machine and
    `config_read_paths` drops an entry whose variable the environment does not
    carry — a drop that is itself a digest factor, so gaining the variable is a
    cache miss rather than a stale pass.

    The credential store is deliberately absent: it changes whether the harness
    authenticates, not what it is permitted to do, and hashing a secret-bearing
    file on every launch buys nothing for an adapter that never claims `os`.
    """

    CLASSIFY: ClassVar[Mapping[str, FailureReason | None]] = MappingProxyType({"UnknownError": None})
    """Observed error name → reason, read by `classify`. **Every cell is `None`** (SD § 7.1a).

    The one error shape 1.18.22 emits is
    `{"name":"UnknownError","data":{"message":…,"ref":…}}`, and a
    provider-resolution failure, an auth failure and a quota failure all produce
    it. The name separates none of them and substring-matching `data.message` is
    not a contract the harness has to keep across a patch release, so every run
    resolves `indeterminate` with the name stamped — never `approve`, and never
    a guessed `UNAUTHENTICATED`.

    A recorded key holding `None` rather than an empty table, so the cell reads
    as *observed and undecidable* rather than as *not yet looked at*.

    **Obligation on whoever records a non-`None` cell here:** `parse` threads
    the reason through `indeterminate`, whose prose says the table did not
    record the name. That prose is true of every cell today and would become a
    contradiction the moment one is filled, so a recorded cell owes `parse` its
    own `detail` alongside the reason.
    """

    def probe(self, runner: Runner, cfg: HarnessConfig, env: Mapping[str, str], cwd: Path) -> HarnessInfo:
        """Establish presence, version and authentication through the launcher (C-1014).

        Two spawns, in this order, both `--pure` and both inside the empty
        directory core minted:

        1. `--pure --version` — presence, and the string `version_warning`
           compares against `VERIFIED_AGAINST`. A non-zero exit, an unresolvable
           launcher or no output at all is `ABSENT`; a zero exit whose output
           carries no version line is `version=None`, which warns rather than
           refuses.
        2. `--pure providers list` — the C-1034(4) preflight. A non-zero exit is
           `ABSENT` (the preflight did not run); a clean run listing no provider
           row is `UNAUTHENTICATED`, naming this harness's `AUTH_ENV_HINTS`
           entry as CANDIDATES rather than as drops that happened. That is the
           honest answer on a machine whose store is empty and whose provider
           rode a variable C-1008 dropped (C-1002 working as designed); without
           the preflight the same state surfaces mid-review as an `UnknownError`
           that classifies to `indeterminate` and names nothing.

        Both spawns are supervised, never `spawn`-then-`wait`: a launcher that
        hangs unpacking a package would otherwise leak a live process group into
        a caller that has already given up.

        The detail names `AUTH_ENV_HINTS`' patterns rather than what
        `minimal_env` actually dropped, because `Adapter.probe` is not given the
        dropped list — reported to WP8, which has it.

        Args:
            runner: The process seam. The adapter never touches `subprocess`.
            cfg: This harness's config, for the launcher prefix.
            env: The C-1008 minimal environment.
            cwd: A fresh empty directory nox owns.

        Returns:
            What the probe established. `capabilities` carries `ENUMERABLE_DENY`
            only — no `ENFORCED_READ_ONLY`, because the deny is a convention, and
            no `STRUCTURED_OUTPUT`, because there is no schema flag.

        Raises:
            HarnessUnavailable: `ABSENT` when the launcher or binary could not
                run, `UNAUTHENTICATED` when no provider is configured.
        """
        # `launcher_for` answering `None` is "no wrapper configured", not "an
        # unresolvable one": the bare binary is then what `launch_argv` resolves,
        # and its absence from the minimal PATH is what decides `ABSENT`.
        launcher = cfg.launcher_for(self.BINARY) or Launcher(binary=self.BINARY)
        result, lines = probe_run(runner, launcher, env, cwd, PURE_FLAG, "--version", timeout_s=PROBE_TIMEOUT_S)
        if result.exit_code != 0 or not lines:
            raise HarnessUnavailable(
                FailureReason.ABSENT,
                f"{self.name}: {self.BINARY} produced no usable version through its launcher",
            )
        preflight, rows = probe_run(
            runner, launcher, env, cwd, PURE_FLAG, "providers", "list", timeout_s=PROBE_TIMEOUT_S
        )
        # A preflight that did not RUN is `ABSENT`, not `UNAUTHENTICATED`: the
        # second reading would blame the user's credentials for a broken
        # launcher, and `UNAUTHENTICATED` is the one probe outcome whose remedy
        # is an operator action.
        if preflight.exit_code != 0:
            raise HarnessUnavailable(
                FailureReason.ABSENT,
                f"{self.name}: the provider preflight did not run through its launcher",
            )
        if not any(_ANSI_RE.sub("", row).lstrip().startswith(_PROVIDER_BULLET) for row in rows):
            # The NAMES only, and as candidates: this adapter is not given
            # `minimal_env`'s dropped list, so it may not claim any of them was
            # set (C-1035 keeps a value out either way).
            hints = ", ".join(sorted(AUTH_ENV_HINTS[self.name]))
            raise HarnessUnavailable(
                FailureReason.UNAUTHENTICATED,
                f"{self.name}: the preflight listed no configured provider. Credential-shaped names "
                f"nox never forwards for this harness: {hints}. {AUTH_HINT_TRAILER}",
            )
        return HarnessInfo(
            name=self.name,
            version=_version_of(lines),
            verified_against=VERIFIED_AGAINST,
            capabilities=frozenset({Capability.ENUMERABLE_DENY}),
            heartbeat_kind=Liveness.SEMANTIC,
            launcher=launcher,
        )

    def sandbox_probe(self, runner: Runner, ws: Workspace, info: HarnessInfo, env: Mapping[str, str]) -> bool:
        """Always `False`: this adapter claims no `os` axis (C-1025).

        Args:
            runner: The process seam.
            ws: The live workspace.
            info: What `probe` established.
            env: The C-1008 minimal environment.

        Returns:
            `False`, so `derive_containment` would refuse an `os` claim this
            adapter never makes.
        """
        del runner, ws, info, env
        return False

    def containment_plan(self, cfg: HarnessConfig, info: HarnessInfo) -> ContainmentPlan:
        """Claim `config-deny`, both axes `attested`, and name both kinds of evidence (C-1007).

        `env_evidence` carries `CONFIG_ENV` at the exact value `deny_config`
        renders for this config — the mechanism, and what
        `_mechanism_corroborated` requires of `config-deny`. `argv_evidence`
        carries `PURE_FLAG` alone: one word, because `derive_containment` rule 2
        requires the word AFTER the run to be a flag and the argv's last word is
        the prompt positional. `prepare` therefore emits `--pure` immediately
        before `--format json`, never last.

        Args:
            cfg: This harness's config, for `tools_allowed`.
            info: What the probe established. Unused — nothing this adapter can
                claim is contingent on what the probe saw, and reading a field
                it does not need would imply otherwise.

        Returns:
            The claim. Neither axis is ever `harness` or `os`: the deny map's
            resolution order was never observed, only its presence in the
            resolved rule list.

        Raises:
            ConfigError: `tools_allowed` names a capability outside
                `ALLOWED_TOOLS`, i.e. it widens rather than narrows (C-1016).
        """
        del info
        return ContainmentPlan(
            mechanism="config-deny",
            write_enforcement="attested",
            network_enforcement="attested",
            argv_evidence=(PURE_FLAG,),
            env_evidence={CONFIG_ENV: deny_config(self._tools(cfg))},
        )

    def _tools(self, cfg: HarnessConfig) -> tuple[str, ...]:
        """Resolve the permitted capability set for one launch (C-1016).

        Called by both `containment_plan` and `prepare`, so the refusal fires on
        either route and neither can widen alone.

        Args:
            cfg: This harness's config.

        Returns:
            The configured narrowing, or this adapter's own set.

        Raises:
            ConfigError: `tools_allowed` widens rather than narrows.
        """
        # `is None`, never falsiness: an explicit empty `tools_allowed` is the
        # MAXIMALLY restrictive configuration, and reading `()` as "unset" would
        # silently answer it with the full grant.
        requested = narrow_tools(cfg.tools_allowed, ALLOWED_TOOLS)
        return ALLOWED_TOOLS if requested is None else requested

    def prepare(
        self,
        ws: Workspace,
        info: HarnessInfo,
        cfg: HarnessConfig,
        instructions: str | None,
    ) -> Launch:
        """Build `opencode run` for one review (E9a, C-1023, C-1028).

        `("run", *police_passthrough(name, cfg.passthrough, nox_flags), prompt)`,
        with `nox_flags` fixed at
        `("--pure", "--format", "json", "-m", <model>[, "--variant", <effort>])`
        — `--pure` first so derivation's rule-2 terminator is a flag, and every
        value-taking flag emitted only as a complete pair, because a bare
        trailing flag would bind the prompt as its value and leave `run` with no
        message. `resolve_model` returning no spec (C-1030 rule 6) drops `-m`
        entirely rather than emitting it empty.

        The prompt is LAST and is a positional: `run [message..]` has no
        prompt-file flag and no stdin form, so `review_prompt`'s text goes
        through `argv_prompt`, which enforces `PROMPT_ARGV_LIMIT`. This is one of
        the two shapes that limit still binds (E29) — `claude` and `codex` read
        their prompt from stdin and declare `Launch.stdin_path` instead. The
        written file still exists inside `ws.scratch`; this shape cannot name it,
        and declaring it would hand the harness a channel it does not read.
        A prompt whose first character is `-` is refused rather than emitted: it
        would parse as an option, and `--` is not a verified separator on this
        yargs build.

        `-f/--file` would be a fourth channel and is not used: it is refused from
        passthrough by `DENIED_FLAGS`, and nox declines to emit it because it
        ATTACHES a file to the message rather than replacing it, which would put
        the prompt on argv anyway.

        The scope is `ws.scope`; `review_prompt` reads it there.

        Args:
            ws: The live workspace.
            info: What the probe established.
            cfg: This harness's config.
            instructions: Extra instruction text from nox's own caller.

        Returns:
            The launch, with `env` carrying exactly `CONFIG_ENV`.

        Raises:
            ConfigError: A refused `passthrough` element (C-1023), a
                `tools_allowed` that widens (C-1016), a model literal that is
                not a usable argv word (C-1030), a prompt over
                `PROMPT_ARGV_LIMIT` or one starting with `-` (C-1028).
            IsolationError: The prompt could not be written into `ws.scratch`.
        """
        tools = self._tools(cfg)
        flags = [PURE_FLAG, "--format", "json"]
        spec, _ = resolve_model(self.MODELS, cfg)
        if spec is not None:
            flags += ["-m", spec.model]
            if spec.effort is not None:
                flags += ["--variant", spec.effort]
        _, text = review_prompt(ws, info, instructions)
        prompt = argv_prompt(text)
        if prompt.startswith("-"):
            raise ConfigError("prompt: a message beginning with '-' parses as an option on this harness (C-1028)")
        return Launch(
            argv=("run", *police_passthrough(self.name, cfg.passthrough, flags), prompt),
            env={CONFIG_ENV: deny_config(tools)},
        )

    def on_line(self, line: str) -> bool:
        """Whether one output line is a SEMANTIC progress event (C-1010).

        `Liveness.SEMANTIC` runs a 120-second silence window against
        `Heartbeat.last_activity_at`, which only moves when this answers `True`,
        so a harness whose every line answered `False` would be killed at 120
        seconds of perfectly healthy output. A line is an event exactly when it
        decodes to a JSON object carrying a `type` — the merged stderr's warning
        lines are bytes without progress and answer `False`, which is the honest
        answer rather than the convenient one.

        Not a member of the `Adapter` Protocol: WP3's row makes `on_line` the
        adapter's, and nothing declares it. Reported to WP6/WP8 — until the
        Protocol carries it, `api.review()` has to reach for this by name.

        Args:
            line: One line of merged output.

        Returns:
            Whether it was a structured event.
        """
        event = _mapping(_decode(line))
        return event is not None and "type" in event

    def classify(self, err: Mapping[str, object]) -> FailureReason | None:
        """Map one decoded error object to a reason, or decline (C-1012).

        Reads `CLASSIFY` rather than restating it, so the table is the answer
        and a future recorded cell needs no code change. Every cell is `None` on
        1.18.22, and an unrecorded name declines too.

        Args:
            err: One decoded error object from the JSON stream.

        Returns:
            The recorded reason, or `None`.
        """
        name = err.get("name")
        return self.CLASSIFY.get(name) if isinstance(name, str) else None

    def parse(self, lines: Iterable[str], exit_code: int, hb: Heartbeat) -> ParsedOutput:
        """Resolve the `--format json` event stream to a tri-state result (C-1011).

        Each line is one JSON event; anything that does not decode to an object
        is ignored, which is what makes the merged stderr's warning lines
        harmless. Three event types carry meaning:

        - `type == "text"` — the LAST one's `part.text` is the answer. One is
          emitted per step, so a review that calls tools narrates in the first
          and replies in the last; concatenating them prefixed the wire object
          with prose and failed both extractions, which is the defect the live
          matrix's whole `* -> opencode` column was;
        - `type == "step_finish"` — `part.cost` is summed across every step, so
          a multi-step review does not report only its last leg;
        - `type == "error"` — `error.name` goes to `classify`, and a declined
          name resolves `indeterminate` with the name stamped, bounded to
          `_MAX_ERROR_NAME` printable characters (C-1035). An error anywhere in
          the stream wins over any text — an event of that type is enough, even
          with no readable payload: a run that failed after emitting a partial
          answer has not produced a verdict.

        The answer is then a JSON object — bare first, since that is what the
        recorded 1.18.22 reply produced and what `prompt._SCHEMA_ASK` asks for,
        and otherwise the LAST fenced block. Never a first-`{`-to-last-`}` scan:
        the diff under review is attacker-controlled text that the model may
        quote back, and such a scan would let it supply the verdict.

        Every field is untrusted (C-1019) and is coerced before it reaches a
        typed slot — `file` to `str | None`, the line numbers to `int | None`,
        `confidence` to its three words — because a harness that emits
        `"file": 123` would otherwise raise a `TypeError` out of `parse` and
        escape `review()`'s C-1029 totality as a traceback. `severity` and the
        traversal check on `file` are `ParsedOutput.__post_init__`'s.

        Resolves `indeterminate` with `MALFORMED_OUTPUT`, never `ok`, when there
        is no text at all, neither extraction decodes, the result is not an
        object, `verdict` is not one of the two words, or `findings` is not a
        list — **unless nox killed the run**, which `_unusable` labels
        `error`/`KILLED` off `reason_for_exit` (SD § 7.1). The exit code gates
        nothing beyond that label: it is read only where the stream established
        neither a verdict nor an error of its own, so it can never overrule what
        the harness said, and never reach `ok`.

        Args:
            lines: The merged output stream, in order.
            exit_code: What the child exited with. Reaches `_unusable` and
                nowhere else — a harness that failed says so in the stream, and
                branching on the status before reading it is what SD § 4.3
                forbids.
            hb: Progress evidence at the moment the run ended. Unused: activity
                is not a verdict.

        Returns:
            What the output establishes.
        """
        del hb
        collected = tuple(lines)
        # `""`, not `"\n"`: `_drain` keeps each line's trailing newline, so this
        # is the join that reconstructs the stream verbatim (C-1018).
        raw = "".join(collected)
        answer = ""
        costs: list[float] = []
        failed = False
        error: Mapping[str, object] = {}
        for line in collected:
            fields = _mapping(_decode(line))
            if fields is None:  # a merged stderr warning line, or a truncated one
                continue
            kind = fields.get("type")
            part = _mapping(fields.get("part"))
            if kind == "text" and part is not None:
                # Replaced, never appended. One `run` emits one `text` part per
                # STEP, and a review that calls a tool narrates first: the live
                # 1.18.22 stream for a real review carries "Reviewing repository
                # change…" as part 1 and the wire object as part 20. Concatenated,
                # neither extraction decodes and every such review resolved
                # `malformed_output` — which is what the whole `* -> opencode`
                # column of the live matrix was. Each part arrives once and whole
                # (probed at 7953 characters, one event, `time.start`/`time.end`
                # both set), so the last one IS the answer and this loses nothing.
                #
                # NOT "the last part that decodes". A run whose final part narrates
                # rather than answers then resolves `malformed_output`, which is the
                # honest answer and the one `_wire_object` already commits to: a
                # malformed final answer is `indeterminate`, never someone else's
                # object. Walking back to an earlier part is exactly the fallback
                # that lets a hostile branch get a JSON object quoted mid-review and
                # have it read as the verdict.
                answer = _text_or_none(part.get("text")) or ""
            elif kind == "step_finish" and part is not None:
                cost = part.get("cost")
                if isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost):
                    costs.append(float(cost))
            elif kind == "error":
                # The FLAG is what decides, not the payload: an error event
                # carrying no readable object still means the run failed, and
                # letting it overwrite a well-formed predecessor with `None`
                # would resolve a failed run `ok` off an earlier text part.
                failed = True
                error = _mapping(fields.get("error")) or error
        spent = sum(costs) if costs else None
        if failed:
            # `indeterminate` owns the prose; `classify`'s answer is threaded
            # through it so a future recorded cell travels as its own reason
            # instead of being flattened to `MALFORMED_OUTPUT`.
            return replace(
                indeterminate(raw, _bounded_name(error)),
                reason=self.classify(error) or FailureReason.MALFORMED_OUTPUT,
                cost_usd=spent,
            )
        wire = _wire_object(answer)
        if wire is None:
            return _unusable(raw, spent, "the harness produced no JSON object, bare or fenced", exit_code)
        verdict = wire.get("verdict")
        if verdict not in _VERDICTS:
            return _unusable(raw, spent, "the harness reported no verdict this adapter recognizes", exit_code)
        findings = wire.get("findings")
        if not isinstance(findings, list):
            return _unusable(raw, spent, "the harness reported findings that are not a list", exit_code)
        reported = cast("list[object]", findings)
        return ParsedOutput(
            status="ok",
            verdict=cast("Verdict", verdict),
            findings=tuple(_finding(entry) for item in reported if (entry := _mapping(item)) is not None),
            summary=_text_or_none(wire.get("summary")) or "",
            detail=None,
            raw=raw,
            reason=None,
            cost_usd=spent,
        )
