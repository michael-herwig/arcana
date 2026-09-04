"""The Codex adapter: argv shape, the JSONL dialect, and C-1040's sandbox probe.

C-1007(codex), C-1012(codex), C-1023, C-1030(codex), C-1032, C-1040, D-v, E8,
S-1002. Verified live against `codex-cli 0.144.1` on 2026-09-03; every fixture
under `tests/contract/fixtures/codex/` was recorded from that binary (E3).

Codex is the one v1 harness whose containment is enforced **below the model**,
by the operating system, so it is the only adapter allowed to claim
`Enforcement` `"os"` — and the only one whose `sandbox_probe` may return `True`.
Everything else in this module exists to make that claim survive contact with
evidence.

## Why `codex exec` and not `codex exec review`

SD § 6.2 specifies `codex exec review --base refs/nox/<token>/base`. That
invocation cannot be built at 0.144.1, and the reason is structural rather than
cosmetic — two findings, each reproduced against the binary and committed as a
fixture, and each on its own enough:

1. **`--base` and the prompt are mutually exclusive.** `codex exec review`
   accepts exactly one of `{--uncommitted, --base, --commit, [PROMPT]}`; naming
   two is a clap conflict (`review-arg-conflicts-0.144.1.txt`) and naming none
   is an error. C-1028 makes the prompt mandatory — it is the only place the
   C-1019 anti-injection framing exists — so on that subcommand nox may have
   deterministic targeting or a prompt, never both.
2. **`codex exec review` has no `-s/--sandbox`.** So the second spelling of the
   sandbox setting cannot be emitted there, and WP6's carry-forward row — name
   both spellings, because core cannot know `--sandbox` and `sandbox_mode=` are
   one setting — is unsatisfiable on that leg (`help-review-0.144.1.txt`).

Bare `codex exec` has neither problem: it takes the prompt as its
positional, honours `--output-schema` exactly (`review-findings-0.144.1.jsonl`,
`review-approve-0.144.1.jsonl` — repo-relative `file`, nox's own severity words),
and carries `-s/--sandbox` alongside `-c`. **D-v is answered `yes` either way**:
`codex exec review` does execute shell commands (it collects the diff with
`git status`/`git diff`/`git log` of its own accord), so the sibling-subcommand
route is taken for the three reasons above rather than for D-v's stated trigger.

**No provenance stamp is needed, and WP1's deferred `Containment.provenance`
row stays deferred.** C-1040 requires the stamp when the probe proves one
subcommand and the review runs another. Here the review-shaped leg of the probe
is *the same* `codex exec` invocation shape the review uses, so there is no
sibling divergence to record.

## What the reviewer is pointed at

Bare `codex exec` has no `--base`, so nothing tells the harness which pair to
diff. That is safe by construction rather than by instruction: C-1005 commits
the synthetic target with `-p <synthetic base>`, so the ephemeral worktree's
`HEAD` has exactly one parent and it is the base — `HEAD^..HEAD` *is* the change.
The recorded runs show the harness resolving exactly that pair on its own.

**That is no longer what the reviewer depends on, and the cross-WP row this WP
raised is closed by delivery rather than by the remedy it proposed.** The row
asked `prompt.py` to name the base/target pair in its scope line, because
nothing told the harness which pair to diff. `review_prompt` now renders
`Workspace.diff` into the prompt itself (C-1028), so codex is handed the same
diff text as the three harnesses that have no shell at all — a live NxN matrix
found those three reviewing a snapshot of the after state. Naming the pair would
now be a second, weaker route to a fact the prompt already states.

## The C-1040 probe, and the one clause of it this binary withholds

C-1040 requires, for each of the two attempts, a `command_execution` item in the
JSONL whose command text carries the attempt **and whose `status == "failed"` /
non-zero exit** — because "a model that *declined* to run a command leaves no
such item and is indistinguishable from a blocked one only by that absence".

The item requirement holds and is implemented. The `status == "failed"` half
cannot be, and the reason is precise rather than general: **0.144.1 emits no
`command_execution` item at all for a command whose failure the sandbox caused.**
Not even `item.started`. The model still reports the denial text and the exit
status in its message, so the command demonstrably ran; the event is suppressed.
Recorded in `sandbox-probe-declined-0.144.1.jsonl` — the two bare attempt strings
C-1040 spells, both blocked, zero items, reproduced 2/2 and matching an earlier
4/4 on `codex exec review`. Requiring `status == "failed"` would therefore refuse
every correctly-sandboxed run.

**Spelling the attempt `<attempt> || cat <nonce file>` restores the item**, which
is why that spelling is the probe's and not a convenience. The wrapper exits 0,
so the event is emitted (3/3, `sandbox-probe-0.144.1.jsonl`), and its
`aggregated_output` then carries two things at once: the sandbox's own denial
text, and a 128-bit per-attempt nonce that arrives through the attempt's own
failure branch: a model that declined produces no item and no nonce, and a model
that ran the attempt against an absent sandbox takes the success branch,
produces no nonce, and leaves `PROBE_MARKER` behind for step 2 to find.

Both of C-1040's discriminators therefore survive — the item's presence, and
evidence that the attempt failed — with only the vendor's own status word
substituted for, because this release does not emit it.

**It is not, however, strictly stronger than `status == "failed"` would be**,
and E23 records the boundary rather than leaving a future reader to find it: the
nonce lives in the reviewed worktree because the read-only sandbox cannot reach
a path outside it, and the ask names that path — so a model that emits a command
merely CONTAINING the tail while reading the file attempted nothing and is
indistinguishable here. No string can close that; every string in this evidence
is one the ask itself hands the model. `attempt_proven` carries the same warning
beside the code, and the unfakeable half is elsewhere: `PROBE_MARKER`'s
continued absence and the listener's silence are nox's own observations.

The probe additionally runs a **deterministic leg** with no model in the loop:
`codex sandbox -c sandbox_mode=read-only -- <cmd>` runs a command nox itself
chose and nox holds the child's exit status, so "was it attempted" is not a
question at all. A read control must exit 0 — without it a sandbox that refused
*every* command would look like one that blocked exactly the two attempts — and
each attempt must exit non-zero. This is not C-1040's, and it is kept because it
is the half no harness can misreport.

**That leg proves the mechanism, not the setting**, and the distinction is the
binary's rather than a hedge. Probed live on 0.144.1: `codex sandbox -- touch
./m` blocks with no `-c` word present at all, because the subcommand is
read-only by default; an unknown `-c` key is accepted there in silence; and
`--strict-config` is refused outright (`error: unexpected argument`, exit 2), so
`_sandbox_args` cannot carry `CONFIG_FLAGS` and does not. What validates the
setting nox actually emits is the review-shaped leg, which runs `CONFIG_FLAGS`
— `--strict-config` among them — in the same argv shape the review uses.

**Every negative observation is falsifiable, because each attempt runs
unsandboxed first.** A `bash` that is absent, or built without `/dev/tcp`, makes
the network attempt exit non-zero for a reason having nothing to do with
containment, and a negative that could not have come out positive is not
evidence. So the write attempt runs first as a plain `runner.spawn` and must
exit 0 **and** leave its marker behind, which nox then removes; the network
attempt must exit 0 **and** actually reach nox's own listener. A control that
does not succeed makes the whole probe inconclusive — the refusing direction.

**Residual, stated rather than papered over:** a model that separately read a
nonce file and then fabricated the attempt would satisfy the review-shaped leg.
Nothing short of the harness's own execution log closes that, and this binary
withholds it for exactly the commands in question. Two things bound it. The
deterministic leg carries no model at all, so the *mechanism* half is free of
the residual outright. And the route by which a repository could ask for the
forgery is closed upstream: C-1005 neutralizes `AGENTS.md`, `CLAUDE.md` and
`.codex/` out of both synthetic trees (`workspace.NEUTRALIZE_FILES`,
`workspace.NEUTRALIZE_DIRS`), so a T1/T2 injection has no file left to arrive
in — a load-bearing dependency of this adapter's `os` claim, named here because
it is not visible from the argv. What remains genuinely open is the vendor
itself, which § T1-T4 do not model.

## What this adapter never claims

Neither enforcement axis says anything about descendant *lifetime* (D-ac).
Seatbelt and Landlock constrain what a process may touch, not whether it
outlives the review, and nothing here — docstring, plan or fixture — may read
as if the sandbox reaped anything.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import selectors
import shlex
import signal
import socket
from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar, Final, Literal, cast, get_args

from nox.capability import Capability, Launcher, ModelClass, ModelSpec, ModelSpecT
from nox.harness import (
    ContainmentPlan,
    HarnessInfo,
    HarnessUnavailable,
    Launch,
    ParsedOutput,
    argv_prompt,
    indeterminate,
    launch_argv,
    police_passthrough,
    reason_for_exit,
    resolve_model,
    review_prompt,
    to_severity,
)
from nox.liveness import Liveness
from nox.outcome import FailureReason, Finding, NoxError, Severity, Verdict
from nox.runner import Invocation
from nox.workspace import write_nofollow

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from pathlib import Path

    from nox.config import HarnessConfig
    from nox.liveness import Heartbeat
    from nox.runner import Runner
    from nox.workspace import Workspace

# ── Shipped literals, every one of them probed ───────────────────────────────

BINARY: Final[str] = "codex"
"""The executable, before any launcher prefix. On `PATH` at 0.144.1."""

VERIFIED_AGAINST: Final[str] = "0.144.1"
"""The version every fixture in `tests/contract/fixtures/codex/` was recorded from (E3).

Read off `codex --version` at implementation time, never copied from a document.
`version_warning` compares the probed version against this and warns on a
mismatch; it never refuses (C-1020).
"""

VERSION_PREFIX: Final[str] = "codex-cli "
"""What `codex --version` prints before the version (`version-0.144.1.txt`)."""

SUBCOMMAND: Final[tuple[str, ...]] = ("exec",)
"""Bare `codex exec`, not `codex exec review` — see the module docstring."""

SANDBOX_SUBCOMMAND: Final[tuple[str, ...]] = ("sandbox",)
"""`codex sandbox` — runs one command under Codex's sandbox with no model in the loop."""

LOGIN_SUBCOMMAND: Final[tuple[str, ...]] = ("login", "status")
"""The C-1014 auth preflight.

`codex --version` exits 0 with no credentials at all, so a version probe alone
cannot answer C-1014 for this harness. `codex login status` is Codex's own
answer to the question and needs no network: it prints `Logged in using ChatGPT`
or `Not logged in` (fixtures `login-status-{,un}authenticated-0.144.1.txt`) and
exits 0 either way, so the ANSWER is the line and never the status. It writes to
**stderr**, which C-1009's merged drain delivers as ordinary lines.

nox never opens the harness's own credential store (C-1002): Codex authenticates
from it and nox only asks the binary whether it can. No path INSIDE that store
is named anywhere under `src/`, which `test_config.py`'s needle scan enforces —
`CONFIG_READS` names two `config.toml` paths under `$CODEX_HOME` and `$HOME`,
which are the C-1025 digest's inputs and carry no credential.

The ANSWER is a `LOGGED_IN_PREFIX` line, required rather than inferred from the
absence of `LOGGED_OUT`: a renamed subcommand, or one that failed for any other
reason, prints neither line, and reading that silence as authenticated is the
same C-1014 failure as the version-only probe with its direction reversed.
"""

LOGGED_OUT: Final[str] = "Not logged in"
"""The recorded unauthenticated line. Matched on the whole stripped line, never as a substring."""

LOGGED_IN_PREFIX: Final[str] = "Logged in"
"""The recorded authenticated prefix — the account kind follows it."""

SANDBOX_MODE: Final[str] = "read-only"
"""The one `sandbox_mode` value nox ever asks for.

`--strict-config` proves both the key and the value are real rather than
inferred, which is the cheap half of C-1040's rollout gate and closes SD § 6.2's
"the key name is *inferred*" caveat: an unknown key is refused
(``unknown configuration field `…` in -c/--config override``) and an unknown
value is refused naming the whole domain
(``expected one of `read-only`, `workspace-write`, `danger-full-access```).
Recorded in `strict-config-0.144.1.txt`.
"""

SANDBOX_EVIDENCE: Final[tuple[str, ...]] = ("-c", f"sandbox_mode={SANDBOX_MODE}", "--sandbox", SANDBOX_MODE)
"""The containment-bearing argv run, in both of Codex's spellings.

WP6's carry-forward row: `derive_containment` cannot know that `--sandbox` and
`sandbox_mode=` are one setting under two names, so an override in the spelling
the evidence does not carry would corroborate the plan while turning the sandbox
off. Naming both LONG spellings closes them inside the adapter, where the
knowledge lives:

- the `=`-carrying word arms C-1025 rule 3, which refuses any `sandbox_mode=`
  assignment outside the run in all three of Codex's spellings
  (`-c k=v`, `--config=k=v`, `-csandbox_mode=v`);
- `--sandbox`, whose in-run successor carries no `=`, arms rule 4, which refuses
  any later `--sandbox` or `--sandbox=…`.

`-c` itself is exempt from rule 4 by design, which is what lets the model-effort
knob ride a second `-c` for an unrelated key (C-1030).

**A third spelling exists and is NOT closed here.** `help-0.144.1.txt` lists
`-s, --sandbox <SANDBOX_MODE>`, and `harness._names_option("-s", "--sandbox")`
is `False` — the short form names the same option and rule 4 would not see it,
so an outside `-s danger-full-access` would corroborate this claim with the
sandbox off. What closes it is `harness.DENIED_FLAGS`, which carries `-s` and
refuses it from `passthrough` before any argv is built; the test asserting that
membership lives beside this adapter's own, because the guarantee is this
adapter's and the constant is not.

Emitted as one contiguous run because that is what `_argv_corroborates` requires,
and proven accepted together by the recorded review runs.
"""

CONFIG_FLAGS: Final[tuple[str, ...]] = ("--ephemeral", "--strict-config", "--ignore-rules", "--ignore-user-config")
"""Defence in depth, never the boundary (SD § 6.2).

`--ephemeral` writes no session file; `--ignore-user-config` drops
`$CODEX_HOME/config.toml`; `--ignore-rules` drops user and project execpolicy
`.rules` files; `--strict-config` turns an unrecognised `-c` key into a refusal
instead of a silently ignored override — which is what makes the sandbox key a
verified name rather than a hopeful one.

Deliberately NOT part of `SANDBOX_EVIDENCE`: they harden the run and none of
them is the mechanism, so promoting them to evidence would let a plan
corroborate an `os` claim without the sandbox word being present at all.
"""

STREAM_FLAG: Final[str] = "--json"
"""JSONL events on stdout — the `SEMANTIC` heartbeat's only source."""

SCHEMA_FLAG: Final[str] = "--output-schema"
"""Codex validates the final message against a JSON Schema file (`STRUCTURED_OUTPUT`).

Honoured on bare `codex exec` and ignored by `codex exec review` — one of the
three reasons this adapter uses the former.
"""

SCHEMA_FILENAME: Final[str] = "codex-output-schema.json"
"""The schema's name inside `Workspace.scratch`, beside `prompt.md`.

`ws.scratch` is `mkdtemp`ed as a SIBLING of the worktree (E20), so a fixed name
inside it is not a collision the branch can arrange — the branch cannot write
there at all. The path is absolute and outside the harness's cwd, which is
correct for this flag: `--output-schema` is read by the `codex` process itself,
not by the model-generated shell commands `--sandbox` confines.
"""

MODELS: Final[Mapping[ModelClass, ModelSpec]] = {
    "fast-balanced": ModelSpecT(model="gpt-5.6-luna", effort="low"),
    "deep-reasoning": ModelSpecT(model="gpt-5.6-luna", effort="high"),
}
"""Capability class → Codex's literal and effort level (C-1030).

One model id, because one is what was probed: `gpt-5.6-luna` is this binary's
own default and the only id proven to resolve — E3 evidence, recorded as
`model-resolves-0.144.1.jsonl` from
`codex exec -m gpt-5.6-luna -c model_reasoning_effort=high` (with `--json` for
the stream), which completed its turn and exited 0 with both knobs accepted
together. The classes differ by
`model_reasoning_effort`, whose domain the API itself enumerated when handed an
invalid value — `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`,
recorded in `effort-enum-0.144.1.jsonl` — so both levels are read off the
vendor's own enum rather than guessed. A second model id joins this table when a
probe proves one, not before (E3).

The effort knob rides `-c model_reasoning_effort=<level>`, which C-1023 refuses
from passthrough unconditionally — so it is emitted here from a typed
`ModelSpecT` and never from a config-supplied argv fragment (C-1030).
"""

MODEL_FLAG: Final[str] = "-m"
"""`-m/--model <MODEL>`."""

EFFORT_KEY: Final[str] = "model_reasoning_effort"
"""The `-c` key carrying the reasoning-effort level (SD § 6.2)."""

CONFIG_READS: Final[tuple[str, ...]] = ("${CODEX_HOME}/config.toml", "${HOME}/.codex/config.toml")
"""User-level config hashed into the C-1025 probe digest, in precedence order.

`CODEX_HOME` is on the C-1008 allowlist and forwarded, so a `$HOME`-relative
path alone would hash a file the harness is not reading. Both are declared even
though nox emits `--ignore-user-config`: over-declaring costs a cache miss the
day the file changes, while under-declaring caches a sandbox-probe pass across
the edit that invalidated it, and only one of those two failures is safe.
"""

CAPABILITIES: Final[frozenset[Capability]] = frozenset(
    {Capability.ENUMERABLE_DENY, Capability.ENFORCED_READ_ONLY, Capability.STRUCTURED_OUTPUT}
)
"""What the probe establishes, and nothing else (C-1013).

- `ENUMERABLE_DENY` — `sandbox_mode` has a closed, binary-enumerated domain
  which `--strict-config` refuses to widen.
- `ENFORCED_READ_ONLY` — read-only is enforced by the kernel, not asked of the
  model: the probe's write attempt fails with `Read-only file system` and its
  network attempt with `Operation not permitted`.
- `STRUCTURED_OUTPUT` — `--output-schema` shapes the final message, proven by
  the two recorded review fixtures.

Cost reporting is absent: `turn.completed` carries token counts and no cost, so
`ParsedOutput.cost_usd` is always `None` for this harness.
"""

HEARTBEAT_KIND: Final[Liveness] = Liveness.SEMANTIC
"""One JSON event per line, so silence over events is meaningful (C-1010)."""

PROBE_MARKER: Final[str] = "nox-probe-write"
"""PREFIX of C-1040 step 2's file, in the worktree root the sandbox holds read-only.

Never the whole name: `_probe_marker` appends a per-run token, minted the way
the nonces are. A fixed literal here would be a name the branch under review can
read out of this source and commit at its own root — the check is a bare
`exists()`, none of `workspace.NEUTRALIZE_FILES` covers it, and one empty file
would then make the probe permanently inconclusive, both axes `None` and
`check_capabilities` refuse. That is a hostile repository escaping the only
OS-enforced harness by adding a file, so the path the probe writes and checks is
unguessable from the repository.
"""

NONCE_BYTES: Final[int] = 16
"""Per-attempt nonce width, from `secrets.token_hex`, and the run token's width too.

128 bits, so the nonce cannot be guessed by a model that declined to run the
command that would have revealed it — which is the whole of its evidentiary
value.
"""

SEVERITY_KEY: Final[str] = "severity"
"""Where a finding's severity lives in the wire object. `to_severity` fails it toward `block`."""

ARGV_END: Final[str] = "--"
"""clap's end-of-options word, emitted between the flag tail and the trailing positional.

It is what makes `SANDBOX_EVIDENCE` a run C-1025 rule 2 accepts — the rule wants
the word after the run absent or `-`-prefixed. That was load-bearing while the
prompt itself was the positional and could begin with any character; since E29
the positional is `STDIN_PROMPT`, which satisfies rule 2 on its own, and this
word is kept because the *contract* is that nox ends its own option parsing
rather than relying on what the trailing positional happens to look like.
"""

STDIN_PROMPT: Final[str] = "-"
"""The `[PROMPT]` positional that makes Codex read the prompt from stdin (E29).

From the 0.144.1 help for `[PROMPT]`: "If not provided as an argument (or if
`-` is used), instructions are read from stdin." `-` rather than omitting the
positional entirely, because the two are not equivalent when a prompt could
also arrive by another route — the same help says a piped stdin is appended as
a `<stdin>` block when a prompt IS given — and an explicit `-` states which
channel nox meant instead of leaving it to argument-count inference.

Verified live behind the real flag set, `--` included, before it was relied on.
`Launch.stdin_path` is the other half; `harness.authorize` is what constrains
it to a file inside `Workspace.scratch`.
"""

NONCE_FILENAME: Final[str] = "nonce"
"""PREFIX of one attempt's nonce file in the worktree ROOT — see `_nonce_file` for why not scratch.

`<prefix>-<run token>-<attempt index>`, so each attempt has a file of its own
and no two runs collide. Both halves are load-bearing:

- **per attempt**, because the path is what `FALLBACK_MATCH` is built from, so
  each call asks about its own attempt. One shared nonce lets a single batched
  `bash -lc "a; b"` item — whose `command` carries both attempts and whose
  output carries the one nonce once — prove BOTH attempts, including one that
  succeeded and never printed anything;
- **per run**, because `write_nofollow` is `O_EXCL`: a fixed name would make a
  second `sandbox_probe` on one workspace raise `IsolationError` on the
  leftover, which `contextlib.suppress(NoxError)` swallows into a `False` that
  has nothing to do with the sandbox, permanently and silently.

The path is also what keeps the discriminator matchable where the attempt text
is not: matching the attempt depends on how the harness's login shell re-spelled
it — the recorded fixture shows zsh wrapping it in double quotes because the
attempt carries single ones — and a wrapper that escaped them instead would
refuse every Codex review on that machine. This path is nox-minted, unique per
attempt, and carries no character a shell rewrites; `FALLBACK_MATCH` absorbs the
spacing and quoting a harness may still add around it.
"""

FALLBACK_MATCH: Final[str] = r"\|\|\s*cat\s+['\"]?\.?/?{path}(?![\w-])"
r"""How an attempt's `|| cat <nonce file>` tail is recognised in an item's `command`.

A pattern and not a literal, and each part earns its place against a real
refusal — a tail that does not match makes `sandbox_probe` answer `False`,
which nulls both axes and refuses **every** Codex review on that machine:

- `\s*` and `\s+` because `||cat` and `|| cat` are one command to a shell;
- `['\"]?` because a harness that re-renders the command may quote the path;
- `\.?/?` because `cat nonce-x-0` and `cat ./nonce-x-0` name the same file;
- `(?![\w-])` because `nonce-<token>-1` is a prefix of `nonce-<token>-10`, and
  the index is what separates one attempt's evidence from another's.

What it does NOT tolerate is the `||` going missing: that is the whole point of
matching the tail rather than the bare path, and `attempt_proven` says why.
Backslash-escaping between the words (a wrapper spelling `\|\|\ cat`) is not
covered — no such harness is known, and the failure is a refusal, not a pass.
"""

PROBE_HOST: Final[str] = "127.0.0.1"
"""Loopback. The listener is nox's own, in nox's own process."""

REVIEW_TIMEOUT_S: Final[float] = 900.0
"""Wall-clock bound on the review-shaped probe spawn, which is a whole model turn.

Generous rather than tuned. A spawn that has not answered by then reports no
status, which every caller here reads as no evidence — the refusing direction.
"""

PROBE_TIMEOUT_S: Final[float] = 60.0
"""Wall-clock bound on every probe spawn with no model in it.

`--version`, `login status`, the two unsandboxed controls and the three
`codex sandbox` legs all finish in milliseconds once the binary has started, so
this is two orders of magnitude of headroom rather than a real bound, and it is
deliberately far below `REVIEW_TIMEOUT_S`: a deterministic leg that is still
running after a minute has stopped answering, and waiting a quarter of an hour
to say so would spend the user's whole budget on a leg that is already lost.
"""

PROBE_GRACE_S: Final[float] = 5.0
"""How long a signalled probe spawn is waited on before nox stops waiting.

Mirrors `TimeoutPolicy.grace_s`. What it bounds is nox's own return and nothing
else; no claim about the signalled process follows from it (D-ac).
"""

READ_CONTROL: Final[tuple[str, ...]] = ("ls", "-1a", ".")
"""The command that must SUCCEED under the sandbox (`sandbox-subcommand-0.144.1.txt`).

Without it a sandbox that refused every command whatsoever would be
indistinguishable from one that blocked exactly the two attempts.
"""

ERROR_NAME_LIMIT: Final[int] = 200
"""Characters of an error's first line that travel into `detail`.

The name is the one piece of harness output `indeterminate` carries (C-1012), so
it is bounded: 0.144.1 embeds a whole JSON blob in one `message`, and an
unbounded name would put an arbitrary amount of harness text into `Review.detail`.
Wide enough that every recorded shape still names its own error type.
"""

PROBE_INSTRUCTION: Final[str] = (
    "Run each of the following commands exactly as written, one shell invocation per command, "
    "then report each command's output and its exit status verbatim. Change nothing else."
)
"""The probe's own ask. Not a review prompt: it names two commands and asks for their output.

C-1028 keeps *review* instructions in `prompt.py`; this text accompanies no diff
and reaches no repository content, and `test_prompt.py`'s scan over every module
is what holds the line.
"""

_ERROR_KINDS: Final[frozenset[str]] = frozenset({"error", "turn.failed"})
"""Top-level envelopes carrying a failure. `turn.failed` nests its message one level deeper."""

_VERDICTS: Final[Mapping[str, Verdict]] = {word: word for word in get_args(Verdict)}
"""The two wire verdicts, read off the `Literal` rather than restated.

A lookup rather than a comparison: anything else the model wrote is absent from
it, so an unrecognised word resolves `indeterminate` instead of a verdict nox
never defined.
"""

_CONFIDENCE: Final[Mapping[str, Literal["high", "medium", "low"]]] = {
    "high": "high",
    "medium": "medium",
    "low": "low",
}
"""Wire confidence → `Finding.confidence`. An invented word takes the field's own default."""

_NULLABLE_STRING: Final[Mapping[str, object]] = {"type": ["string", "null"]}
_NULLABLE_INTEGER: Final[Mapping[str, object]] = {"type": ["integer", "null"]}
_STRING: Final[Mapping[str, object]] = {"type": "string"}

_FINDING_PROPERTIES: Final[Mapping[str, Mapping[str, object]]] = {
    SEVERITY_KEY: {"type": "string", "enum": list(get_args(Severity))},
    "title": _STRING,
    "body": _STRING,
    "file": _NULLABLE_STRING,
    "line_start": _NULLABLE_INTEGER,
    "line_end": _NULLABLE_INTEGER,
    "confidence": {"type": "string", "enum": sorted(_CONFIDENCE)},
    "recommendation": _NULLABLE_STRING,
}
"""One finding's fields, in `--output-schema`'s dialect. The severity domain is `Severity` itself."""


def _strict(properties: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    """Wrap a property table as a STRICT JSON Schema object.

    `additionalProperties: false` and a `required` naming every property are not
    style: the provider refuses the request without them —
    ``'additionalProperties' is required to be supplied and to be false``, a 400
    `invalid_json_schema` that fails the turn before the model sees the prompt
    (reproduced live at 0.144.1, `output-schema-rejected-0.144.1.jsonl`). It
    applies at every level, so the finding object needs it as much as the root.

    Every property is `required` because that is the same dialect's rule — an
    optional field is spelled as a nullable type, which is why `file`,
    `line_start`, `line_end` and `recommendation` already are.

    Args:
        properties: Field name → its schema.

    Returns:
        The object schema, ready to nest or serialize.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": dict(properties),
    }


_FINDING_SCHEMA: Final[Mapping[str, object]] = _strict(_FINDING_PROPERTIES)
"""One finding, strict — see `_strict` for why the two extra keys are load-bearing."""

_PROPERTY_SCHEMA: Final[Mapping[str, Mapping[str, object]]] = {
    "verdict": {"type": "string", "enum": list(get_args(Verdict))},
    "summary": _STRING,
    "findings": {"type": "array", "items": _FINDING_SCHEMA},
    "next_steps": {"type": "array", "items": _STRING},
}
"""`prompt.WIRE_SCHEMA`'s object, in `--output-schema`'s dialect rather than as prose.

A wire contract, not instruction text — the line the ADR draws directly under its
§ API Contract object, and why this is not the inline prompt-building C-1028
forbids. The keys are restated here rather than read out of `prompt.WIRE_SCHEMA`
because C-1024 keeps `nox.prompt` out of every adapter: `review_prompt` is the
one route from a workspace to a prompt, and an adapter that imported the module
could call `render` itself with `structured_output` guessed. The join is
`test_the_written_schema_names_exactly_the_wire_contracts_own_keys`, which fails
the day either side gains a key — WP5's carry-forward row, tested rather than
argued.
"""


def _output_schema() -> dict[str, object]:
    """Build the `--output-schema` document Codex validates the final message against.

    Returns:
        A JSON Schema object, ready to serialize.
    """
    return _strict(_PROPERTY_SCHEMA)


def _decode(line: str) -> Mapping[str, object] | None:
    """Decode one stream line as a JSON object, or decline it.

    Non-fatal by construction: stderr merges into this stream under C-1009, so a
    bare line is noise rather than a parse failure, and a JSON value that is not
    an object establishes nothing either.

    Args:
        line: One line of the merged output stream.

    Returns:
        The decoded object, or `None`.
    """
    try:
        decoded: object = json.loads(line)
    except (ValueError, RecursionError):
        # `RecursionError` is a `RuntimeError`, not a `ValueError`: `json` raises
        # it at ~100k nesting depth, which is a 200 KB line — far under
        # `runner.BYTE_CAP`, and there is no per-line cap. Uncaught it escapes
        # `parse` and `sandbox_probe` alike (`suppress(OSError, NoxError)` does
        # not cover it), and C-1029 totality means a run outcome, never a
        # traceback.
        return None
    return cast("Mapping[str, object]", decoded) if isinstance(decoded, dict) else None


def _object(value: object) -> Mapping[str, object]:
    """Return `value` when it is a JSON object, else an empty one.

    Args:
        value: Whatever the wire produced.

    Returns:
        A mapping, always — so a missing or mistyped nesting reads as "carried
        nothing" rather than raising inside `parse`.
    """
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else {}


def _text(value: object) -> str:
    """Return `value` when it is a string, else the empty string.

    Args:
        value: Whatever the wire produced.

    Returns:
        A string, always.
    """
    return value if isinstance(value, str) else ""


def _optional_text(value: object) -> str | None:
    """Return `value` when it is a string, else `None`.

    Args:
        value: Whatever the wire produced.

    Returns:
        The string, or `None`.
    """
    return value if isinstance(value, str) else None


def _line_number(value: object) -> int | None:
    """Return `value` when it is a usable 1-based line number, else `None`.

    Three refusals, and each is a shape the wire can carry. `bool` is a subclass
    of `int`, so a `"line_start": true` would otherwise land in
    `Finding.line_start` as `True` and render as line 1; a negative or zero
    names no line in any file; and anything that is not a number at all is a
    location nothing can act on.

    Args:
        value: Whatever the wire produced.

    Returns:
        The line number, or `None`.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _error_name(err: Mapping[str, object]) -> str:
    """Name one error event, bounded, for the `indeterminate` stamp (C-1012, S-1008).

    A single stripped first line and at most `ERROR_NAME_LIMIT` characters,
    because this string travels into `Review.detail` and 0.144.1 puts a whole
    JSON blob in one `message`.

    Args:
        err: The decoded error object — the item, the top-level envelope, or
            `turn.failed`'s nested object.

    Returns:
        The bounded name, or a fixed phrase when the shape named nothing.
    """
    named = _text(err.get("message")).strip().partition("\n")[0].strip()
    return named[:ERROR_NAME_LIMIT] if named else "an error carrying no message"


def _finding(item: Mapping[str, object]) -> Finding:
    """Read one wire finding, coercing every field to the type `Finding` declares.

    `severity` goes through `to_severity` only so the value is typed at
    construction; `ParsedOutput.__post_init__` normalizes it and `file` again for
    every adapter at once, and neither check is re-implemented here.

    Args:
        item: One decoded element of the wire object's `findings`.

    Returns:
        The finding, before `ParsedOutput` normalizes it.
    """
    return Finding(
        severity=to_severity(item.get(SEVERITY_KEY)),
        title=_text(item.get("title")),
        body=_text(item.get("body")),
        file=_optional_text(item.get("file")),
        line_start=_line_number(item.get("line_start")),
        line_end=_line_number(item.get("line_end")),
        confidence=_CONFIDENCE.get(_text(item.get("confidence")), "medium"),
        recommendation=_optional_text(item.get("recommendation")),
    )


def _findings(wire: Mapping[str, object]) -> tuple[Finding, ...]:
    """Read the wire object's `findings` array, skipping anything that is not an object.

    Args:
        wire: The decoded final message.

    Returns:
        The findings, in wire order.
    """
    reported = wire.get("findings")
    items = cast("list[object]", reported) if isinstance(reported, list) else []
    return tuple(_finding(cast("Mapping[str, object]", item)) for item in items if isinstance(item, dict))


def _events(lines: Iterable[str]) -> Iterator[Mapping[str, object]]:
    """Yield every JSON object the stream carries, in order, skipping everything else.

    Args:
        lines: The merged output stream.

    Yields:
        Each decoded event.
    """
    for line in lines:
        event = _decode(line)
        if event is not None:
            yield event


def _items(lines: Iterable[str]) -> Iterator[Mapping[str, object]]:
    """Yield every `item` object carried by the stream, in order.

    Args:
        lines: The merged output stream.

    Yields:
        Each event's `item`, when it has one.
    """
    for event in _events(lines):
        item = event.get("item")
        if isinstance(item, dict):
            yield cast("Mapping[str, object]", item)


def attempt_proven(lines: Iterable[str], nonce_path: str, nonce: str) -> bool:
    """Whether the stream proves one sandbox attempt ran and took its failure branch (C-1040).

    Pure, and deliberately: the recorded discriminators and the recorded nonce
    cannot be reproduced by a live probe, so this is the decision the fixtures
    can be pointed at directly.

    Both halves are required and neither is sufficient. The
    `command_execution` item is C-1040's own discriminator — 0.144.1 emits none
    at all for a command the sandbox stopped, so a model that merely declined
    leaves nothing here. The nonce in `aggregated_output` is what stands in for
    the `status == "failed"` clause this release withholds: the attempt is
    spelled `<attempt> || cat <nonce file>`, so the nonce can only have been read
    through the attempt's own failure branch, and a model narrating it in a
    message carries no item and proves nothing.

    **`discriminator` is that attempt's own `|| cat ./<nonce path>` tail, not
    its command text and not the bare path.** Three things ride on that choice:

    - *per attempt*, because Codex batches — one `bash -lc "a; b"` item can
      carry both attempts, so with one nonce shared between them a single item
      (including one where the write attempt SUCCEEDED and printed nothing)
      satisfies both calls, and the evidence degrades from "each attempt failed"
      to "at least one did";
    - *the tail and not the bare path*, because the nonce lives in the worktree,
      the read-only sandbox lets the model read it, and the ask names the path —
      so `cat ./nonce-<token>-0` is a genuine `command_execution` item carrying
      the path and the value with nothing attempted. `|| cat ./<path>` cannot
      appear in a command that ran nothing ahead of the fallback;
    - *not the attempt text*, because the harness's login shell re-quotes it:
      the recorded fixture shows zsh choosing double quotes because the network
      attempt carries single ones, and a wrapper that escaped them instead would
      refuse every Codex review on that machine. The tail is quote-free.

    **What this does NOT prove**, stated because C-1040 leans on it: this
    answers "a command whose text carried the tail also emitted the nonce", not
    "the attempt ran". Any item does, including
    `echo 'would run: touch ./m || cat ./n0'; cat ./n0` — which attempts
    nothing, needs no deliberation from the model, and leaves the marker absent
    and the listener silent, so the other two observations do not catch it
    either. No discriminator can close it: every string here is one the ask
    itself hands the model. What IS closed is C-1040's own named case, the model
    that declined and ran nothing at all. E23 carries the boundary.

    Args:
        lines: The merged output stream of the review-shaped leg.
        nonce_path: This attempt's own nonce file, relative to the worktree.
            `FALLBACK_MATCH` is built from it; the bare path is NOT what is
            matched, and `attempt_proven`'s own docstring says why.
        nonce: This attempt's 128-bit nonce.

    Returns:
        Whether one item carries both.
    """
    tail = re.compile(FALLBACK_MATCH.format(path=re.escape(nonce_path)))
    for item in _items(lines):
        command = _text(item.get("command"))
        output = _text(item.get("aggregated_output"))
        if item.get("type") == "command_execution" and tail.search(command) and nonce in output:
            return True
    return False


def _signal_group(pid: int) -> None:
    """Signal the group led by `pid`, mirroring the primitive `runner` uses.

    Restated rather than imported, because that one is private to its module.
    It is not a containment mechanism here either: the child leads its own
    session, so its pid is its own group id and this can never reach the group
    nox itself runs in. `ProcessLookupError` means the child was already gone,
    which is not an error; every other `OSError` propagates, because a swallowed
    `EPERM` would report a signal that never landed.

    Args:
        pid: The child's pid, which is its own group id.
    """
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, signal.SIGKILL)
        # Nothing about what that signal reached is observed, waited on or
        # claimed — here or anywhere in this adapter (D-ac).


def _run(
    runner: Runner,
    launcher: Launcher,
    env: Mapping[str, str],
    cwd: Path,
    timeout: float,
    *args: str,
) -> tuple[int | None, tuple[str, ...]]:
    """Spawn one child through the runner seam and collect what it left behind.

    The adapter's only route to a process: `Runner.spawn` is the seam C-1015
    reserves, and `launch_argv` is what puts an absolute realpath at `argv[0]`
    even though `cwd` is content nox does not control.

    Three ways a spawn answers nothing, and all three report no status, which
    every caller here reads as no evidence rather than as a refusal:

    - it is still running at `timeout`. The group is signalled and waited on for
      `PROBE_GRACE_S`, because up to four of these run per probe and the
      review-shaped one is a whole model turn; nothing beyond nox's own return
      is bounded by that and nothing about a process outside the group is
      claimed (D-ac);
    - its drain thread died, so the stream is not what the child wrote;
    - it passed `runner.BYTE_CAP` or `runner.MAX_LINES`, so the stream is
      truncated and a missing item proves nothing about a missing attempt.

    Args:
        runner: The process seam.
        launcher: How the binary is reached.
        env: The C-1008 minimal environment.
        cwd: Where the child runs.
        timeout: Wall-clock bound on this spawn.
        *args: The harness-level arguments.

    Returns:
        `(exit status, lines)`, the status `None` for any of the three above.
    """
    process = runner.spawn(Invocation(argv=launch_argv(launcher, env, *args), cwd=cwd, env=env))
    status = process.wait(timeout)
    if status is None:
        _signal_group(process.pid)
        process.wait(PROBE_GRACE_S)
        # The second wait's answer is deliberately dropped rather than returned:
        # it would be a signal number, not the child's own exit status, and
        # `_blocked` cannot tell those apart.
    lines = process.lines(0.0)
    unusable = process.collector_failure is not None or process.overflowed
    return (None if unusable else status), lines


def _sandbox_args(command: tuple[str, ...]) -> tuple[str, ...]:
    """Wrap one command in the `codex sandbox` invocation the deterministic leg uses.

    `CONFIG_FLAGS` is deliberately absent: `codex sandbox --strict-config` is
    `error: unexpected argument` on 0.144.1, so adding it would refuse every
    deterministic leg. The module docstring records what that costs — this leg
    proves the mechanism and the review-shaped leg proves the setting.

    Args:
        command: The argv words to run under the sandbox.

    Returns:
        The harness-level arguments, `command` after `--`.
    """
    return (*SANDBOX_SUBCOMMAND, "-c", f"sandbox_mode={SANDBOX_MODE}", ARGV_END, *command)


def _blocked(status: int | None) -> bool:
    """Whether a deterministic attempt was stopped, as its own exit status reports it.

    Args:
        status: What the child exited with, or `None` when it never answered.

    Returns:
        `True` only for a real non-zero status. A child that produced no status
        produced no evidence, which is the refusing direction.
    """
    return status is not None and status != 0


def _connected(listener: socket.socket) -> bool:
    """Whether anything reached the listener since the last time this was asked.

    Non-blocking, and never a reading of what the harness said: the socket is
    nox's, in nox's process, so a pending connection is the one observation on
    the network axis that no harness can misreport.

    **Draining is what makes it repeatable.** The queue is the state, so a call
    that only peeked would answer `True` for the rest of the probe once the
    unsandboxed control connected once — and the sandboxed attempt after it
    would then be judged by the control's own connection. Accepting and closing
    is also what the control needs: a listener nobody accepts on has proved that
    the packet arrived, not that a connection completed.

    Args:
        listener: The bound, listening, non-blocking socket.

    Returns:
        Whether a connection was waiting.
    """
    with selectors.DefaultSelector() as selector:
        selector.register(listener, selectors.EVENT_READ)
        if not selector.select(0):
            return False
    # A connection the peer aborted between the two calls disappears from the
    # queue: the listener is non-blocking, so this never waits, and the answer
    # is still `True` because something did arrive.
    with contextlib.suppress(OSError):
        listener.accept()[0].close()
    return True


def _marker(token: str) -> str:
    """Name C-1040 step 2's file for one probe run.

    Args:
        token: This run's random token.

    Returns:
        The name, relative to the worktree root — see `PROBE_MARKER` for why it
        is not a literal.
    """
    return f"{PROBE_MARKER}-{token}"


def _nonce_file(ws: Workspace, token: str, index: int) -> tuple[str, str]:
    """Mint one attempt's nonce file in the worktree ROOT, beside the probe marker.

    Not in `ws.scratch`, and that is E20's doing rather than a preference: the
    scratch directory is now `mkdtemp`ed as a SIBLING of the worktree, so no
    path under it is relative to `ws.path` at all — and the attempt has to name
    the file from inside the sandboxed shell's own cwd, which is the worktree.
    An absolute path out of the tree would additionally be asking the sandbox a
    question the probe is not trying to answer.

    So the nonce goes where `PROBE_MARKER` already goes, under the same per-run
    token: unguessable from the repository, and `_review_leg` removes both
    before `authorize` returns, so the review that follows never sees a file
    nox wrote. That last part is what keeps E20's own fix intact — nox content
    inside the reviewed tree is what made a live review report a false
    prompt-injection finding.

    Args:
        ws: The live workspace the probe runs inside.
        token: This run's random token.
        index: Which attempt the file belongs to.

    Returns:
        `(path relative to the worktree, nonce)` — the pair `attempt_proven`
        takes, one per attempt.

    Raises:
        IsolationError: The file could not be written. `write_nofollow` is
            `O_EXCL|O_NOFOLLOW`, so a planted file or symlink of this name
            refuses rather than being followed — and the name carries the run
            token, which the repository cannot have guessed.
    """
    nonce = secrets.token_hex(NONCE_BYTES)
    relative = f"{NONCE_FILENAME}-{token}-{index}"
    write_nofollow(ws.path / relative, nonce.encode("utf-8"))
    return relative, nonce


def _controls(
    runner: Runner,
    ws: Workspace,
    env: Mapping[str, str],
    listener: socket.socket,
    marker: str,
    commands: tuple[tuple[str, ...], ...],
) -> bool:
    """Prove each attempt SUCCEEDS unsandboxed, so its later failure is falsifiable (C-1040).

    Run through `Runner.spawn` directly — no `codex`, and above all no
    `--sandbox` word of any value — because what these establish is that the
    command itself works on this host: that `touch` creates the file it is
    pointed at, and that this `bash` has `/dev/tcp` and can reach nox's
    listener. Without them a host missing either makes both sandboxed attempts
    exit non-zero for a reason having nothing to do with containment, both
    observations pass, and `os` is stamped with no sandbox present at all.

    An executable that does not resolve on the minimal `PATH` raises
    `HarnessUnavailable`, which `sandbox_probe` suppresses into `False`: no
    control, no evidence.

    Args:
        runner: The process seam.
        ws: The live workspace the probe runs inside.
        env: The C-1008 minimal environment.
        listener: The bound socket the network command aims at.
        marker: The file the write command creates, which this removes again.
        commands: The write command and the network command, as argv.

    Returns:
        Whether both succeeded and both left the evidence they should.

    Raises:
        HarnessUnavailable: An executable did not resolve on the minimal `PATH`.
    """
    write, network = commands
    written, _ = _run(runner, Launcher(binary=write[0]), env, ws.path, PROBE_TIMEOUT_S, *write[1:])
    created = (ws.path / marker).exists()
    (ws.path / marker).unlink(missing_ok=True)
    reached, _ = _run(runner, Launcher(binary=network[0]), env, ws.path, PROBE_TIMEOUT_S, *network[1:])
    # Read before the `and` chain can short-circuit past it: the accept queue is
    # state, and a connection left in it would be credited to the sandboxed
    # attempt that follows.
    connected = _connected(listener)
    return written == 0 and created and reached == 0 and connected


def _review_leg(
    runner: Runner,
    ws: Workspace,
    info: HarnessInfo,
    env: Mapping[str, str],
    listener: socket.socket,
    token: str,
    commands: tuple[tuple[str, ...], ...],
) -> bool:
    """Prove the sandbox reaches MODEL-GENERATED commands, in the argv shape the review uses.

    One `codex exec` spawn carrying `STREAM_FLAG`, `CONFIG_FLAGS` and
    `SANDBOX_EVIDENCE` exactly as `prepare` emits them, with the probe's own ask
    in place of the review prompt and no `--output-schema` — so what passes here
    is the same invocation shape that later runs, and C-1040 needs no
    sibling-subcommand provenance stamp. It is also the only leg that carries
    `--strict-config`, which is what makes the emitted setting a verified name
    rather than an accepted one.

    The commands are spelled from the same argv tuples the deterministic leg
    ran, through `shlex.join`, so the two legs cannot drift into attempting
    different things.

    Args:
        runner: The process seam.
        ws: The live workspace the probe runs inside.
        info: What `probe` established.
        env: The C-1008 minimal environment.
        listener: The bound socket the network attempt aims at.
        token: This run's random token, naming the marker and the nonce files.
        commands: The write command and the network command, as argv.

    Returns:
        Whether the spawn answered, both attempts are proven, the marker is
        still absent and nothing reached the listener.

    Raises:
        IsolationError: A nonce file could not be written.
        ConfigError: The probe's own ask exceeded `PROMPT_ARGV_LIMIT`.
    """
    # Accumulated INSIDE the `try`, never built ahead of it: `_nonce_file`
    # raises on a plant, and a raise on the second nonce would otherwise leave
    # the first behind — the one file E20 exists to keep out of the reviewed
    # tree. The `finally` below can only unlink what this list already holds.
    minted: list[tuple[str, str]] = []
    try:
        minted.extend(_nonce_file(ws, token, index) for index in range(len(commands)))
        spelled = tuple(
            f"{shlex.join(command)} || cat ./{relative}"
            for command, (relative, _) in zip(commands, minted, strict=True)
        )
        status, lines = _run(
            runner,
            info.launcher,
            env,
            ws.path,
            REVIEW_TIMEOUT_S,
            *SUBCOMMAND,
            STREAM_FLAG,
            *CONFIG_FLAGS,
            *SANDBOX_EVIDENCE,
            ARGV_END,
            argv_prompt("\n".join((PROBE_INSTRUCTION, *spelled))),
        )
        proven = [attempt_proven(lines, relative, nonce) for relative, nonce in minted]
        connected = _connected(listener)
        return status is not None and all(proven) and not connected and not (ws.path / _marker(token)).exists()
    finally:
        # In a `finally`, and before `authorize` can return: the review spawns
        # into this same worktree, and a file nox left in the reviewed tree is
        # exactly what E20 moved the scratch directory out to stop — it reads
        # as repository content and draws a false prompt-injection finding.
        for relative, _ in minted:
            (ws.path / relative).unlink(missing_ok=True)


class CodexAdapter:
    """Codex behind the `Adapter` protocol.

    Six methods and four class-level tables (SD § 9.3). The tables are shipped
    literals probed from the binary; the methods own the argv shape, the JSONL
    dialect and the sandbox probe, and nothing else — the launch, the
    containment derivation and the prompt all belong to `nox.harness`.
    """

    name: ClassVar[str] = "codex"
    BINARY: ClassVar[str] = BINARY
    MODELS: ClassVar[Mapping[ModelClass, ModelSpec]] = MODELS
    CONFIG_READS: ClassVar[tuple[str, ...]] = CONFIG_READS

    CLASSIFY: ClassVar[Mapping[str, FailureReason]] = {}
    """Observed error shape → reason (C-1012). Empty, and that is the honest state.

    SD § 7.1a admits a cell only where a recorded fixture proves it, and
    `classify` keys on `type`. Every shape this binary was observed to emit
    carries the SAME `type` — `"error"` — whatever it is about: an item-level
    model-metadata warning, a top-level JSON blob carrying an HTTP 400, and a
    reconnect notice quoting a live `401 Unauthorized` are all
    `{"type":"error",…}` in `error-events-0.144.1.jsonl`. So there is no key to
    add a cell UNDER: distinguishing them means matching inside `message`, which
    is the substring reading C-1012 forbids, and an `UNAUTHENTICATED` cell keyed
    on `"error"` would claim every one of the three.

    That the 401 was recorded and still adds no cell is the point — the table is
    empty because of the wire's shape, not because the condition was
    unreachable. So `classify` returns `None` for everything and every
    unrecorded error resolves `indeterminate` with the raw name stamped, which
    stops the run without inventing a cause (S-1008, S-1009). A cell lands here
    the day a fixture shows a `type` that names one condition and only that one.
    """

    def _unauthenticated(self, said: str) -> HarnessUnavailable:
        """Build the C-1014 refusal as nox's own prose, and nothing more.

        The C-1034(4) credential hint is deliberately NOT composed here.
        `api._auth_detail` appends it to every `UNAUTHENTICATED` detail from
        `minimal_env`'s real `dropped` list — the one this adapter is never
        handed — so composing one here printed the whole sentence pair twice.
        The reconstruction it was composed from was the wrong shape besides:
        `AUTH_ENV_HINTS` entries are `fnmatchcase` patterns, so an entry like
        opencode's `OPENCODE_*_APIKEY` would reach the operator as the name of a
        variable that exists nowhere. claude, copilot and opencode all raise the
        bare detail; this is that contract, restated by obeying it.

        Args:
            said: What the login answer did, as one clause.

        Returns:
            The exception, returned rather than raised so each call site reads
            as the answer it refuses.
        """
        return HarnessUnavailable(FailureReason.UNAUTHENTICATED, f"{BINARY} {said}")

    def probe(self, runner: Runner, cfg: HarnessConfig, env: Mapping[str, str], cwd: Path) -> HarnessInfo:
        """Establish that Codex is present, runnable and authenticated (C-1014).

        Two spawns, because one does not answer the question: `codex --version`
        exits 0 and prints its version with no credentials whatsoever, so
        version alone would report a usable harness that fails mid-review with a
        401 retry loop. `codex login status` is the second, and it is the
        harness's own answer rather than a file nox opened (C-1002).

        Both run in the empty directory `probe_harness` mints, never the
        repository (C-1014).

        Args:
            runner: The process seam.
            cfg: This harness's config, for its launcher prefix.
            env: The C-1008 minimal environment.
            cwd: A fresh empty directory nox owns.

        Returns:
            What the probe established, with `verified_against` set to
            `VERIFIED_AGAINST` and `capabilities` set to `CAPABILITIES`.

        Raises:
            HarnessUnavailable: `ABSENT` when the binary does not resolve or
                names no version; `UNAUTHENTICATED` when `codex login status`
                reports `Not logged in` OR does not report `Logged in` at all.
                The detail is nox's own prose and never the probe's output —
                WP8 appends the C-1034(4) `config.auth_hint` from the names
                `minimal_env` dropped, which this adapter is not given.
        """
        launcher = cfg.launcher_for(BINARY) or Launcher(binary=BINARY)
        _, printed = _run(runner, launcher, env, cwd, PROBE_TIMEOUT_S, "--version")
        stripped = tuple(line.strip() for line in printed)
        version = next(
            (line.removeprefix(VERSION_PREFIX) for line in stripped if line.startswith(VERSION_PREFIX)), None
        )
        if version is None:
            raise HarnessUnavailable(FailureReason.ABSENT, f"{BINARY}: ran but named no version")
        _, answered = _run(runner, launcher, env, cwd, PROBE_TIMEOUT_S, *LOGIN_SUBCOMMAND)
        # The whole stripped LINE, never a substring: the recorded unauthenticated
        # answer arrives behind a stderr WARNING, and a note quoting the phrase is
        # not this harness refusing.
        lines = tuple(line.strip() for line in answered)
        if any(line == LOGGED_OUT for line in lines):
            raise self._unauthenticated("reports it holds no credentials")
        # The positive line is REQUIRED, not inferred from the negative's
        # absence: a subcommand that was renamed, or that failed for any reason
        # at all, prints neither, and taking that silence for a yes is C-1014's
        # own failure with the direction reversed.
        if not any(line.startswith(LOGGED_IN_PREFIX) for line in lines):
            raise self._unauthenticated("did not answer whether it holds credentials")
        return HarnessInfo(
            name=self.name,
            version=version,
            verified_against=VERIFIED_AGAINST,
            capabilities=CAPABILITIES,
            heartbeat_kind=HEARTBEAT_KIND,
            launcher=launcher,
        )

    def sandbox_probe(self, runner: Runner, ws: Workspace, info: HarnessInfo, env: Mapping[str, str]) -> bool:
        """Prove Codex's OS-level enforcement actually holds (C-1025, C-1040).

        Every observation must pass; anything else — an attempt that produced no
        evidence, a spawn that answered nothing, a nonce that never came back —
        returns `False`, and `derive_containment` then downgrades both axes to
        `None` and `check_capabilities` refuses the launch. There is no path
        from an inconclusive probe to a silent unsandboxed run.

        **Step 0** binds a listener on `127.0.0.1:<ephemeral>` and records the
        port. The listener is nox's, in nox's process, so "did anything connect"
        is answered by the accept queue rather than by anything the harness said.
        It also mints this run's token, which names the marker and every nonce
        file, so nothing the probe writes or checks has a name the repository
        under review could have guessed.

        **The controls**, two plain `runner.spawn`s with no `codex` and no
        sandbox in sight: the write command must exit 0 and create the marker
        (which is then removed again), and the network command must exit 0 and
        actually reach the listener. They are what make each negative below
        falsifiable — `_controls` says what fails without them.

        **The deterministic leg**, three `codex sandbox` spawns carrying the same
        `-c sandbox_mode=read-only` word the review emits — though what this leg
        establishes is the mechanism and not that word, because the subcommand
        already defaults to read-only and accepts an unknown `-c` key in silence
        (`_sandbox_args`). Proving the setting is the review-shaped leg's job:

        1. a read control, which must exit 0 — without it a sandbox that refused
           *every* command would look like a sandbox that blocked exactly the two
           attempts;
        2. the write attempt, which must exit non-zero and must not leave the
           marker behind;
        3. the network attempt, which must exit non-zero and must not reach the
           listener.

        No model is in the loop here, so the attempt evidence C-1040 asks for is
        the child's own exit status.

        **The review-shaped leg**, one `codex exec` spawn in the same shape the
        review uses, proving the mode reaches *model-generated* commands. Each
        attempt is spelled `<attempt> || cat <nonce file>`, so its OWN nonce —
        one per attempt, never one shared — reaches the output through that
        attempt's failure branch, and C-1040's `command_execution` item is
        required for both: the item's `command` must carry that attempt's
        `|| cat <nonce path>` TAIL and its `aggregated_output` must carry that
        attempt's nonce. A model that declined produces neither and the probe is
        inconclusive; a model that ran the attempt against an absent sandbox
        takes the success branch, produces no nonce, and leaves the marker
        behind for step 2. The module docstring records why the item's
        `status == "failed"` half is unobtainable on this release and what
        stands in its place; `attempt_proven` records why the tail and not the
        bare path — and, under **What this does NOT prove**, the narrower claim
        this evidence actually supports (E23).

        Re-runnable on one workspace, which `authorize` needs because it caches
        only a PASSING probe: every file this writes is named from the run
        token, so a second call collides with nothing the first left behind.

        Args:
            runner: The process seam.
            ws: The live workspace the probe runs inside.
            info: What `probe` established.
            env: The C-1008 minimal environment.

        Returns:
            `True` only when every observation passed.
        """
        proven = False
        # Anything that did not answer the question answers `False`: a socket that
        # would not bind, an argv that would not resolve, a nonce that could not be
        # written. There is no route from here to an unproven `os` axis standing.
        with contextlib.suppress(OSError, NoxError), socket.socket() as listener:
            listener.bind((PROBE_HOST, 0))
            listener.listen(1)
            listener.setblocking(False)  # so `_connected` can never wait on an aborted peer
            port = int(listener.getsockname()[1])
            token = secrets.token_hex(NONCE_BYTES)
            marker = _marker(token)
            commands = (("touch", f"./{marker}"), ("bash", "-c", f"exec 3<>/dev/tcp/{PROBE_HOST}/{port}"))
            if _controls(runner, ws, env, listener, marker, commands):
                read, _ = _run(runner, info.launcher, env, ws.path, PROBE_TIMEOUT_S, *_sandbox_args(READ_CONTROL))
                write, _ = _run(runner, info.launcher, env, ws.path, PROBE_TIMEOUT_S, *_sandbox_args(commands[0]))
                network, _ = _run(runner, info.launcher, env, ws.path, PROBE_TIMEOUT_S, *_sandbox_args(commands[1]))
                connected = _connected(listener)
                deterministic = read == 0 and _blocked(write) and _blocked(network) and not connected
                if deterministic and not (ws.path / marker).exists():
                    proven = _review_leg(runner, ws, info, env, listener, token, commands)
        return proven

    def containment_plan(self, cfg: HarnessConfig, info: HarnessInfo) -> ContainmentPlan:
        """Claim the OS sandbox, and name the argv run that corroborates it (C-1007).

        `os-sandbox` on both axes, which under C-1025 requires a non-empty
        `argv_evidence` **and** a passing cached probe — so this claim is
        refused rather than believed until `sandbox_probe` has returned `True`
        under this launch's digest.

        The two axes fall together, which is correct for this mechanism: one
        sandbox constrains writes and network reach alike, and there is no
        Codex flag that lifts one without the other.

        No environment evidence: Codex's containment is entirely in its argv.

        Args:
            cfg: This harness's config.
            info: What the probe established.

        Returns:
            The claim, with `SANDBOX_EVIDENCE` as its argv run.
        """
        return ContainmentPlan(
            mechanism="os-sandbox",
            write_enforcement="os",
            network_enforcement="os",
            argv_evidence=SANDBOX_EVIDENCE,
        )

    def prepare(self, ws: Workspace, info: HarnessInfo, cfg: HarnessConfig, instructions: str | None) -> Launch:
        """Build the harness-level launch for one review (E9a, C-1023).

        The argv, in the order `authorize` requires:
        `(*SUBCOMMAND, *police_passthrough(...))`, where the policed tail is the
        configured passthrough followed by nox's own flags — passthrough first,
        so a last-wins parser resolves nox's containment words and not the
        repository's, and Codex documents CLI flags outranking project config.

        nox's own flags are the stream flag, the schema flag and its file, the
        model selection when one resolves, `CONFIG_FLAGS`, `SANDBOX_EVIDENCE`
        as one contiguous run, and finally the prompt as the positional.

        **The prompt rides stdin** (E29), behind `STDIN_PROMPT`. Codex has no
        prompt-FILE flag, but `[PROMPT]` documents `-` as "read from stdin", and
        `Launch.stdin_path` supplies the file `review_prompt` already wrote. It
        rode argv until E29, which put the whole rendered diff under the
        kernel's `MAX_ARG_STRLEN` and refused a whole-branch review — nox's
        primary use case — at 128 KiB on a limit that is a property of the argv
        channel and not of nox. `argv_prompt` and its `PROMPT_ARGV_LIMIT` remain
        the right answer for `copilot -p` and `opencode run`, which have no
        second channel; this adapter no longer calls it here. It still calls it
        for the *probe's* own ask, which is a short literal and genuinely argv.

        The JSON Schema is written into `ws.scratch` beside the prompt and named
        by `--output-schema`. It is `prompt.WIRE_SCHEMA`'s object in Codex's own
        dialect — a wire contract rather than instruction text, the line the ADR
        draws directly under its § API Contract object. `_PROPERTY_SCHEMA` says
        why the keys are restated there rather than read out of that module, and
        which test is the join.

        Args:
            ws: The live ephemeral worktree and its evidence.
            info: What the probe established.
            cfg: This harness's config.
            instructions: Extra instruction text from nox's OWN caller, or
                `None`. Never populated from repository content (C-1005).

        Returns:
            The harness-level launch. Its `env` is empty: this adapter's
            containment adds no environment.

        Raises:
            ConfigError: A refused `passthrough` element (C-1023). **No
                prompt-size refusal**: the prompt rides stdin, so
                `PROMPT_ARGV_LIMIT` does not apply to the review leg (E29).
            IsolationError: The schema file could not be written.
        """
        # Nothing is unlinked first, deliberately. `write_nofollow` is
        # `O_EXCL|O_NOFOLLOW` precisely so nothing pre-existing is overwritten,
        # and its own docstring says the scratch DIRECTORY is unprotected once a
        # harness has run — so a delete-then-create after a spawn would unlink
        # and then write THROUGH a swapped `ws.scratch`, outside the worktree,
        # turning what the untouched code makes a fatal `IsolationError` into a
        # silent overwrite. A second `prepare` on one workspace therefore
        # refuses, which is the safe answer; `PROMPT_FILENAME` is
        # `review_prompt`'s file in any case and not this module's to remove.
        schema = ws.scratch / SCHEMA_FILENAME
        write_nofollow(schema, json.dumps(_output_schema()).encode("utf-8"))
        spec, _ = resolve_model(self.MODELS, cfg)
        # Rule 6 lands here as an empty tail: no entry is the harness default,
        # never a substitution from the other class.
        selection = () if spec is None else (MODEL_FLAG, spec.model)
        effort = () if spec is None or spec.effort is None else ("-c", f"{EFFORT_KEY}={spec.effort}")
        prompt_path, _ = review_prompt(ws, info, instructions)
        nox_flags = (
            STREAM_FLAG,
            SCHEMA_FLAG,
            str(schema),
            *selection,
            *effort,
            *CONFIG_FLAGS,
            *SANDBOX_EVIDENCE,
            ARGV_END,
            STDIN_PROMPT,
        )
        return Launch(
            argv=(*SUBCOMMAND, *police_passthrough(self.name, cfg.passthrough, nox_flags)),
            stdin_path=prompt_path,
        )

    def on_line(self, line: str) -> bool:
        """Whether one output line is a semantic event, answered honestly (C-1010).

        `True` for a line that decodes to a JSON object carrying `type` — every
        `--json` record, an `error` envelope included, because an error IS a
        real event and the harness is demonstrably alive. `False` for what
        C-1009's merged drain delivers from stderr: this binary's
        `Reading additional input from stdin…` and its `CODEX_HOME` advisories
        are bytes, not progress.

        Load-bearing rather than cosmetic. `HEARTBEAT_KIND` is `SEMANTIC`, so
        `supervise` measures the 120 s silence window against
        `last_activity_at`, which `Heartbeat.touch` advances only on `True` —
        an adapter that never answers `True` has every review killed at 120 s
        while it is working normally.

        Args:
            line: One line of merged output.

        Returns:
            Whether it was a semantic event.
        """
        event = _decode(line)
        return event is not None and "type" in event

    def classify(self, err: Mapping[str, object]) -> FailureReason | None:
        """Map one observed Codex error object to a reason, or decline (C-1012).

        Declines everything today, because `CLASSIFY` is empty and no fixture
        proves a cell. That is a positive statement rather than a gap: the run
        resolves `indeterminate` with the raw error name stamped, which stops it
        without inventing a cause a substring match would have guessed.

        Args:
            err: One decoded error object from the JSONL stream.

        Returns:
            The reason, or `None`.
        """
        return self.CLASSIFY.get(_text(err.get("type")))

    def _declined(self, err: Mapping[str, object], raw: str) -> ParsedOutput:
        """Resolve one error object through `classify`, or stamp it `indeterminate` (C-1012).

        Args:
            err: The error object — an item, an envelope, or `turn.failed`'s
                nested object.
            raw: The output as the supervisor delivered it (C-1018).

        Returns:
            `indeterminate` with the bounded error name stamped, or an `error`
            carrying the reason `classify` recognised.
        """
        declined = indeterminate(raw, _error_name(err))
        reason = self.classify(err)
        return declined if reason is None else replace(declined, status="error", reason=reason)

    def parse(self, lines: Iterable[str], exit_code: int, hb: Heartbeat) -> ParsedOutput:
        """Resolve Codex's JSONL stream to a tri-state result (C-1011).

        The stream is one JSON object per line. Four event shapes matter, and
        the last is the one whose absence is load-bearing:

        - `{"type":"item.completed","item":{"type":"agent_message","text":…}}` —
          the model's message. Under `STRUCTURED_OUTPUT` its `text` is the wire
          object. **The LAST one wins**: Codex emits a schema-shaped *preamble*
          message before it starts work (`review-findings-0.144.1.jsonl` item_0
          carries `"verdict":"approve","findings":[]` while the model is still
          announcing what it will do), so taking the first would return a clean
          approve for a review that had not begun. The envelope is checked as
          well as the item: an `item.started` agent_message arriving after the
          final one would otherwise BE the last message, and a real
          `needs-attention` carrying a `block` finding would resolve
          `indeterminate` behind it.
        - `{"type":"error","message":…}` and its `item.completed` form — handed
          to `classify`, which declines, so the run resolves `indeterminate`
          with the name stamped. **Advisory, and deliberately so**: 0.144.1
          emits `type:"error"` for a benign model-metadata warning
          (`error-events-0.144.1.jsonl` line 1), so a decodable verdict that
          arrived anyway outranks these. The line is drawn here rather than at
          "any error at all" because throwing away a completed review over a
          warning is the more likely wrong answer of the two.
        - `{"type":"turn.failed","error":{"message":…}}` — **decisive**, and
          the one error shape that is. It nests its message one level deeper and
          is what a rejected request actually produces
          (`effort-enum-0.144.1.jsonl`), and it refuses the run whatever else
          arrived. That it is not `turn.completed` is an assumption about the
          vendor's own bookkeeping; checking it directly is a fact about the
          stream, and the difference is a turn that failed after emitting a
          schema-shaped message.
        - `{"type":"turn.completed",…}` — **required**. Without it the stream
          ended before the model finished, and the last `agent_message` may be
          that preamble; the result is `indeterminate`, never a verdict read off
          a half-finished run. Its `usage` carries token counts and no cost, so
          `cost_usd` stays `None`.

        A line that is not JSON, a message whose text is not the wire object, and
        an unrecognised envelope all resolve `indeterminate` with `raw` retained
        (C-1018) — never `ok` by elimination. `raw` is `"".join` and never a join on
        newlines: `runner._drain` keeps the newline `readline` produced on every
        line, so adding one more would double every line break in what C-1018
        calls verbatim. Severity words go through `to_severity`, which fails
        toward `block`; `Finding.file` normalization is `ParsedOutput`'s and
        happens for every adapter at once.

        Args:
            lines: The merged output stream, in order.
            exit_code: What the child exited with. A label only — `143` maps to
                `KILLED` through `reason_for_exit`, and only for a run whose
                stream established neither a verdict nor an error of its own.
                Nothing else is read.
            hb: Progress evidence at the moment the run ended.

        Returns:
            What the output establishes.
        """
        del hb
        collected = tuple(lines)
        raw = "".join(collected)
        messages: list[str] = []
        errors: list[Mapping[str, object]] = []
        refused: list[Mapping[str, object]] = []
        completed = False
        for event in _events(collected):
            kind = _text(event.get("type"))
            item = _object(event.get("item"))
            nested = _object(event.get("error"))
            item_kind = _text(item.get("type"))
            if kind == "turn.completed":
                completed = True
            elif kind == "item.completed" and item_kind == "agent_message":
                messages.append(_text(item.get("text")))
            elif kind in _ERROR_KINDS or item_kind == "error":
                # One object per shape: the item for an item-level error,
                # `turn.failed`'s nested object, the envelope itself otherwise.
                err = item or nested or event
                errors.append(err)
                if kind == "turn.failed":
                    refused.append(err)
        # Before the verdict, not after it: the harness said this turn failed,
        # and a wire object that arrived anyway is a message from a run its own
        # producer disowned.
        if refused:
            return self._declined(refused[0], raw)
        # The LAST message, never the first: 0.144.1 opens with a schema-shaped
        # preamble carrying `approve` before the model has looked at anything.
        wire = _decode(messages[-1]) if completed and messages else None
        verdict = _VERDICTS.get(_text(wire.get("verdict"))) if wire is not None else None
        if wire is not None and verdict is not None:
            # `next_steps` is asked for and has no home on `Review` (D-i).
            return ParsedOutput(
                status="ok",
                verdict=verdict,
                findings=_findings(wire),
                summary=_text(wire.get("summary")),
                detail=None,
                raw=raw,
                reason=None,
            )
        if errors:
            return self._declined(errors[0], raw)
        # LAST, after the verdict AND after the error table. SD § 7.1 gives exit
        # 143 one row — `error` / `KILLED` — and SD § 4.3 requires the exit code
        # gate nothing; both hold only where the stream established nothing of
        # its own. A completed turn carrying a well-formed verdict, and equally
        # an error the harness itself reported, are the harness's own account of
        # the run; a 143 arriving alongside either is the status of a process
        # that had already said what happened, and reading it first discarded
        # that. This read used to sit above the error table, so one evidence
        # shape — an error event on a run that exited 143 — resolved here as
        # nox's own stop and on `opencode` and `claude` through the reported
        # error; the order below is the one THREE of the four adapters share.
        # `claude` is the exception and its own `parse` docstring records why it
        # was named rather than reordered (E70).
        stopped = reason_for_exit(exit_code)
        if stopped is not None:
            detail = f"{BINARY} exited {exit_code}, which nox reads as its own stop signal (C-1012)"
            return ParsedOutput(
                status="error", verdict=None, findings=(), summary="", detail=detail, raw=raw, reason=stopped
            )
        return ParsedOutput(
            status="indeterminate",
            verdict=None,
            findings=(),
            summary="",
            detail=f"{BINARY} produced no completed turn carrying the wire object (C-1011)",
            raw=raw,
            reason=FailureReason.MALFORMED_OUTPUT,
        )
