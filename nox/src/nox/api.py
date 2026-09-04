"""The public boundary: `review()` is total, and it is the only composition point.

C-1018 (the `raw` credential scan), C-1019, C-1021, C-1022, C-1026 (enforce),
C-1029, C-1035, C-1036 (wiring), C-1042(5-6), C-1043(4), D-i, D-j, E16, S-1004,
S-1011.

Everything below `nox.api` raises; this module is where each exception becomes a
`Review` with `status != "ok"` (C-1029). Nothing else in nox catches, and nothing
else assembles a `Review`.

**The call order is fixed** (SD § 3, WP6's row against this file, and E44's
pre-flight): `_check_target` → `probe_harness` → `workspace` →
`containment_plan` → `prepare` → `authorize` → spawn. `authorize` is the only
producer of a review `Invocation`, and the three
enforcement fields of `Containment` are stamped from the **derived** plan it
returns — never from the adapter's `containment_plan` claim, which is an input to
derivation rather than its answer. `derive_containment` itself is deliberately
absent from `nox.__all__`: its `digest` argument is trusted, and only `authorize`
computes one.

Six properties are structural here rather than conventional:

1. **One environment, built once.** `minimal_env` runs before the C-1014 probe
   and its result is threaded into the probe, the workspace and the launch, so
   C-1025's environment digest is identical between probe and review. It is built
   in two passes — a provisional one against the caller's `repo`, purely so
   `discover_repo` has an environment, then the real one against the discovered
   **top level**. The second pass is what closes T4b for a caller standing in a
   subdirectory: `minimal_env`'s inbound-path check is against the path it is
   given, so a one-pass build would let a `CODEX_HOME` at the repository *root*
   through. `workspace()` is then handed the top level and the same environment,
   and skips the rebuild it would otherwise do. The environment crosses the
   plugin boundary behind a `MappingProxyType`: `adapter.probe` is handed the
   same object that becomes `ws.env` and then `Invocation.env`, and `authorize`'s
   `launch.env` gate never re-inspects it, so a mutation there would be a
   forwarded variable nothing derived.
2. **The worktree path is reserved before the environment is built**, because it
   is what `minimal_env` tests the inbound path variables against, and
   `workspace()` must receive the same value or the digest splits.
3. **Totality is layered.** `NoxError` and its subclasses map to their
   `FailureReason`; the two `OSError` leaks WP3 named (`spawn`'s
   `FileNotFoundError`/`PermissionError`, `supervise`'s deliberate EPERM
   propagation from `_kill_group`) are mapped at their own call sites; and a
   final `except Exception` is the backstop for the plugin boundary — four
   adapters are written independently of this file, and an adapter bug must
   degrade the consumer to `indeterminate` rather than break C-1029. The degrade
   ladder's lowest rung is a consumer-side skip (SD § 7.2); an escaping traceback
   is below even that.
4. **Serialized by default** (C-1022) — one module-level lock, held for the whole
   call, so two threads cannot spend the same vendor quota concurrently.
5. **`Containment` is stamped exactly where a run becomes evidence: in the
   `finally` that owns `raw`.** A refusal *after* a harness has run — the kill
   ladder failing, an adapter's `parse` raising — must not report `NOT_RUN`,
   whose empty tuples and `False` booleans mean "nothing was established"; and a
   run that never started must not report anything else. `_spawn` therefore sits
   *outside* the `try`, so its `ABSENT` refusal keeps `NOT_RUN`, and the stamp
   sits beside `run.raw` inside the `finally`, so every path out of a started run
   carries both the enforcement fields and a `secrets_suspected` the C-1018 scan
   actually read.
6. **The configuration is loaded against the discovered top level, never against
   the caller's path.** `config.load`'s argument is its *whole* T4b reference: it
   is what `_xdg` tests `$XDG_CONFIG_HOME` / `$XDG_STATE_HOME` against and what
   `is_trusted` tests a config file's own location against. Loading against a
   caller standing in `<repo>/sub` would leave an `XDG_CONFIG_HOME` at
   `<repo>/.cfg` outside that reference, making a branch-authored file *the
   user-level config* and handing every `TRUST_GATED_KEYS` member — `launcher`,
   and through it `execve`, included — to whoever wrote the branch.
   `discover_repo` therefore runs before the load, and nothing above the probe
   needs `cfg` except `_resolve_harness` and `resolve_model`.

**What returning proves is that nox is done** (D-ac). No string this module
produces may state or imply that the harness and everything it started are gone.

**D-i is discharged structurally**: `Review` has no `next_steps` field and
`ParsedOutput` has none either, so a wire object carrying one parses and the
field simply has nowhere to land. Nothing here drops it — there is nothing to
drop.
"""

from __future__ import annotations

import json
import secrets
import sys
import tempfile
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast

# The MODULE, not the mapping: `ADAPTERS` is the vocabulary C-1042(5) generates
# its refusal from and the set `--exclude` is checked against, and both have to
# read whatever is registered at call time. Binding the mapping at import would
# freeze a fifth adapter — or a test's own registration — out of both.
from nox import adapters
from nox.capability import ModelClass
from nox.config import ConfigError, auth_hint, minimal_env, world_writable_forwards
from nox.config import load as load_config
from nox.harness import (
    HarnessUnavailable,
    ProbeCache,
    UnsupportedCapability,
    asymmetry_warning,
    authorize,
    enforced_read_only,
    probe_harness,
    resolve_model,
    version_warning,
)
from nox.liveness import Heartbeat, Liveness, TimeoutPolicy
from nox.log import record
from nox.outcome import NOT_RUN, Containment, FailureReason, Finding, NoxError, Review, Status, Verdict
from nox.prompt import Scope
from nox.runner import SubprocessRunner, supervise
from nox.workspace import (
    WORKTREE_PREFIX,
    IsolationError,
    ReviewTarget,
    artifact_rel,
    check_git_version,
    discover_repo,
    resolve_pair,
    workspace,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from nox.config import NoxConfig
    from nox.harness import ContainmentPlan, HarnessInfo, ParsedOutput
    from nox.runner import Invocation, Process, Runner, Supervision
    from nox.workspace import Workspace

__all__ = [
    "CREDENTIAL_SHAPES",
    "MISSING_EXCLUDE_WARNING",
    "ReviewRequest",
    "ReviewTarget",
    "review",
]


class _SupervisorFailure(NoxError):
    """The supervisor's own kill ladder failed, and the harness may still be running.

    `supervise` propagates every non-`ESRCH` `OSError` from `_kill_group`
    deliberately — a refused SIGTERM must not abandon the child one rung short —
    and `review()` is total (C-1029), so the leak is mapped here rather than
    escaping as a traceback.

    Private, like `_AdapterFailure`: `review()` never lets either escape, so a
    public name would widen the surface for a consumer that can never catch one.
    The public exception vocabulary stays the four `NoxError` subclasses
    `outcome.NoxError` names.

    Resolves `error` / `KILLED` — nox forced the end of the run, and `KILLED` is
    the member `supervise` itself already uses for a run it ended (C-1012).
    """


class _AdapterFailure(NoxError):
    """An adapter method raised something that is not a `NoxError` (C-1029 backstop).

    The plugin boundary: four adapters are written independently of this file and
    an adapter bug must degrade the consumer to `indeterminate` rather than break
    the one contract every consumer relies on.

    Carries the exception's **type name only**. An adapter's exception message can
    quote repository content, a `$HOME` path or a slice of harness output, and
    `Review.detail` carries C-1035's redaction rule.
    """


CREDENTIAL_SHAPES: Final[tuple[str, ...]] = (
    "AKIA",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "github_pat_",
    "eyJ",
    "sk-ant-",
    "-----BEGIN",
)
"""Literal prefixes whose presence in `raw` sets `Containment.secrets_suspected` (C-1018).

Prefixes matched as plain substrings, never a regex over an 8 MiB attacker-chosen
string: `raw` is bounded by `runner.BYTE_CAP` and a backtracking pattern over it
is a denial of service against nox's own boundary.

`-----BEGIN` rather than the full PEM header, because the key type varies
(`RSA PRIVATE KEY`, `OPENSSH PRIVATE KEY`, `EC PRIVATE KEY`) and the armour line
is the invariant.

**The GitHub family and `eyJ` are here because the credential stores of nox's
own harnesses use exactly those shapes**, which the first four literals could
not see — and the threat model `_scan_for_credentials` documents is a sandboxed
model reading precisely such a store. Established by inspecting what is on this
machine rather than by reasoning about formats (E70): the GitHub CLI token that
copilot and opencode both authenticate with is a `gho_`, and codex's is an OAuth
JWT. `ghu_`, `ghs_` and `github_pat_` join `ghp_`/`gho_` as the rest of one
prefix family rather than as three separate guesses.

`eyJ` is three characters — base64 for `{"` — so it flags any base64-encoded
JSON, not only a JWT. Accepted deliberately: C-1018 raises a flag and never
redacts, so a false positive costs a sentence in the review, while the miss it
replaces cost the whole signal on a live token. The one false positive that
occurs routinely in the wild is an inline JavaScript source map
(`//# sourceMappingURL=data:application/json;base64,eyJ…`); it is named here so
a reader meeting `secrets_suspected` on a bundled front end knows the shape
before going looking. It costs nothing beyond that sentence — the flag is
report-only and gates neither `status:` nor `verdict:`.

**`sk-proj-` was considered and rejected.** `OPENAI_API_KEY` is unset where that
literal would have had to match, and the JWT is the shape actually present; a
literal matching nothing is noise in a security oracle rather than depth.

Claude Code needs no entry of its own — its store holds no token on this
machine, the credential living in OS secure storage — and copilot keeps none
outside the GitHub CLI's. So this set covers what the four shipped harnesses
actually persist.

**Nothing here redacts.** C-1018 flags the review and says so; silently removing
the match would hide from the user that the reviewing model read a credential —
which is the fact that matters, not the bytes.

ponytail: four literal shapes, no entropy heuristic. C-1018 also names
"high-entropy tokens"; a length-and-alphabet score over untrusted output is a
false-positive generator on base64 diffs and minified JavaScript, and the flag it
sets is one a human reads. The upgrade path is a scorer the day a real leak gets
past these four.
"""

MISSING_EXCLUDE_WARNING: Final[str] = (
    "self-review not excluded: no --exclude supplied — nox cannot detect the client it runs as"
)
"""The C-1042(6) advisory for a run whose caller named no harness to exclude."""

_CALL_LOCK: Final[threading.Lock] = threading.Lock()
"""C-1022: adversary calls are serialized by default.

A quota requirement rather than a containment one under C-1003 (each call owns
its own tree), so this is a default and not a structural ceiling.

ponytail: a `threading.Lock` serializes one *process*. The primary consumer is
`nox.cli`, so two shells started in parallel spend the same vendor quota
concurrently and this lock sees neither. Stated rather than papered over: the
upgrade path is an `fcntl.flock` on the already-open call-log descriptor, which
makes the bound cross-process for the cost of one `flock` per review.
"""

_PROBE_CACHE: Final[ProbeCache] = ProbeCache()
"""Passing sandbox-probe digests, for the life of this process (C-1025).

Module-level rather than per-call, which is what makes `ProbeCache`'s own
"one probe per `review()`" true: a fresh cache would re-run
`adapter.sandbox_probe` — a full review-shaped Codex spawn under C-1040 — on
every single review, and the `os` enforcement level would cost a second live
review to reach every time.

Mutated only under `_CALL_LOCK`, which `review()` holds for the whole call.
"""


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    """One review, as nox's own caller states it.

    Attributes:
        scope: Which of C-1042's two words the caller asked for. Redundant with
            `target.kind` by construction and checked against it, rather than
            derived from it: the CLI takes `--scope` and the target shape from
            two different flags, and a `plan-artifact` reviewed under
            `code-diff` framing is a silently wrong prompt.
        target: What is under review (E9a; it lives in `workspace.py` because it
            is the workspace's input).
        harness: The `ADAPTERS` key to run, or `None` to take `[review] harness`.
            Absent on both routes is `INVALID_CONFIG` naming every registered key
            — there is no shipped default, because the explicit cross-model
            choice *is* the product claim (C-1042(5)).
        exclude: The harness the caller is running as, which nox may not use as
            the adversary. `None` proceeds and warns (C-1042(6)): nox cannot
            detect its own client, so the gate is caller-supplied and its
            unreliability is stamped rather than assumed away.
        authored_by: The model that wrote the change, for the C-1036 asymmetry
            warning. `None` is silent — never guessed.
        instructions: Extra adversarial steering, rendered to the reviewer **as
            instructions** and unfenced.

            **Python-API only, and it must stay that way.** There is no CLI flag
            for it and none may be added: C-1005 removes `CLAUDE.md` and
            `AGENTS.md` from both synthetic trees precisely so repo-authored
            instructions cannot reach the reviewer, and an `--instructions-file`
            taking a repo-relative path reopens that in one line. The obligation
            that this is never populated from repository content is the caller's;
            nox cannot check it.
    """

    scope: Scope
    target: ReviewTarget
    harness: str | None = None
    exclude: str | None = None
    authored_by: str | None = None
    instructions: str | None = None


def _idle_heartbeat() -> Heartbeat:
    """A heartbeat for a run that never started.

    `PROCESS_ONLY` is the honest kind before a probe has said otherwise — it
    means "nothing is known about progress", which is exactly the state of a
    `Review` that refused before spawning. Zeroed timestamps because a monotonic
    origin is arbitrary and only a `TIMED_OUT` detail ever reads them.

    Returns:
        The idle heartbeat.
    """
    return Heartbeat(kind=Liveness.PROCESS_ONLY, last_activity_at=0.0, last_byte_at=0.0)


@dataclass(slots=True)
class _Run:
    """What `review()` has established so far, for the `Review` every path returns.

    Mutable and accumulated, because C-1019 requires a populated envelope on
    **every** return path and the evidence arrives in stages: the harness name is
    known before the probe, the version and capabilities after it, the model
    beside them, the containment only after `authorize` has derived it, and `raw`
    only after the run. A formulation that built the `Review` from locals would
    have each `except` clause restate whichever subset had been reached.

    Every field starts at its **no-evidence** value, and those values are the
    same ones `NOT_RUN` documents: absence means nothing was established, never
    that nothing was there.

    Attributes:
        started: `time.monotonic()` at entry — the base of `duration_s`.
        harness: The resolved registry key, or `""`. Assigned only after
            `adapters.load` has accepted it, so it is always a real registry key:
            `[review] harness` is deliberately not trust-gated, and an
            unresolved value is repository-authored text that C-1035(1) keeps out
            of the envelope exactly as it keeps it out of `detail`.
        harness_version: What the probe read off the binary.
        verified_against: What this adapter's fixtures were recorded from.
        model: The resolved literal, `None` when the harness default was taken.
        model_class: What was asked for. Both sides travel — C-1036 evidence.
        heartbeat: Progress evidence. Idle until `supervise` touches it.
        containment: `NOT_RUN` until the child is running, then the real stamp,
            written in the same `finally` as `raw` so `secrets_suspected` always
            has the run's output to read. Every **pre-spawn** refusal keeps
            `NOT_RUN`, workspace or no workspace and derived plan or no derived
            plan (WP1's row): a per-call-site value would be an enforcement claim
            about a harness that never executed.
        raw: The harness's output as the supervisor delivered it, retained
            unconditionally (C-1018) and assembled in a `finally`, so a refusal
            after the run still carries what the run produced.
        truncated: Whether one of the drain thread's two ceilings was hit.
        cost_usd: What the harness reported, where it reports one.
        warnings: The five C-1035 sources, in the order they are established.
    """

    started: float
    harness: str = ""
    harness_version: str | None = None
    verified_against: str = ""
    model: str | None = None
    model_class: ModelClass | None = None
    heartbeat: Heartbeat = field(default_factory=_idle_heartbeat)
    containment: Containment = NOT_RUN
    raw: str = ""
    truncated: bool = False
    cost_usd: float | None = None
    warnings: list[str] = field(default_factory=list[str])


def review(
    req: ReviewRequest,
    *,
    repo: Path | None = None,
    runner: Runner | None = None,
    config: NoxConfig | None = None,
) -> Review:
    """Run one adversarial review. Returns a `Review` and never raises (C-1029).

    The one public entry point. Internal functions raise; this is the boundary
    that maps each exception onto a `Review` with `status != "ok"` and a
    populated `Containment` (C-1019).

    In order, and the order is SD § 3's:

    0. Refuse a non-POSIX platform (D-j) — `UNSUPPORTED`, before anything is
       built. v1's kill primitive is a POSIX process group and its path handling
       is POSIX; half-resolving Windows is worse than declaring the cut, and
       `runner.py` is written against the guard living here.
    1. Refuse a `repo` that names no directory — the one operator error step 6a
       cannot reach, because `discover_repo` runs before it and reports a
       mistyped `--repo` as `ISOLATION_FAILED`. Then reserve the worktree path
       and build the provisional minimal environment against the caller's path —
       purely so `discover_repo` has one.
    2. `discover_repo`, which is what turns the caller's `--repo`/cwd into the
       repository **top level** every T4b reference below is taken against.
    3. `config.load(toplevel)`, unless the caller supplied a resolved
       `NoxConfig`. This is the only route that produces the C-1035 config
       warnings, and property 6 above is why its argument is the top level and
       not the caller's path.
    4. Check `req.scope` against the scope `req.target.kind` implies.
    5. Resolve the harness and the `--exclude` gate (C-1042(5-6)), then
       `adapters.load` — after which `run.harness` is a real registry key — then
       `resolve_model`, so an unusable configured literal refuses before any
       harness is started and so `model`/`model_class` travel on every later
       failure path.
    6. Build the real minimal environment against the top level, and freeze it.
    6a. `_check_target` — the target the operator named, refused here rather than
        at step 8. `workspace()` validates it too and remains the authority, but
        it runs after the probe, so an absent harness answered for a mistyped
        `--base` and for both `--path` mistakes alike: three different operator
        errors, one message telling them to install something (H13). The check
        touches no repository state, so the property step 8 has — a target
        refusal reaches `sweep` never having run — survives moving it earlier.
    7. `probe_harness`, then `_warnings_for` — which is where sources 2-4 all
       land, the C-1008 world-writable one included: it reads the environment
       built at step 6, but the other two need `info`, and one call keeps the
       fixed order C-1035 asks for in one place.
    8. Enter `workspace`, and stay inside it for everything below: the four
       evidence tuples outlive teardown, but `prepare` needs the live tree and
       every post-spawn refusal needs `ws` to stamp from.
    9. `containment_plan` → `prepare` → `authorize` → spawn → supervise → stamp
       → `parse` → resolve. The stamp is in the `finally` that owns `raw`, which
       is what keeps a spawn failure at `NOT_RUN` and every later refusal at the
       real one.
    10. `log.record`, outside the `Review`'s construction and unable to affect
        it — but still inside `_CALL_LOCK`, which C-1022 holds for the whole
        call. It never raises, so keeping it there costs a caller nothing and
        serializes the append as a side effect. `repo=` is the top level where
        one was discovered and the caller's own path otherwise, because
        `call_log_path`'s T4b belt is dropped silently by a `None`.

    **Deviation from the plan's Step 8.1 signature, stated rather than assumed:**
    `repo` is a fourth keyword parameter. Step 8.1 abbreviates the signature to
    `review(req, *, runner=None, config=None)`, but C-1042(4) gives the skill a
    `--repo <path>` flag and the ADR's own sketch spells `review(req, *, repo:
    Path, …)`. It defaults to the current working directory, which is the other
    half of C-1042(4)'s rule.

    Args:
        req: What to review, under which harness.
        repo: Any path inside the repository under review; the top level is
            discovered from it. Defaults to the current working directory.
        runner: The process seam. Defaults to `SubprocessRunner`.
        config: Already-resolved configuration, for a caller that loaded its own.
            `None` loads it from `repo`.

    Returns:
        The review. `status` is tri-state, `verdict` is non-`None` iff `status ==
        "ok"`, `reason` is non-`None` iff it is not, and `containment` is
        populated on every path — `NOT_RUN` wherever no harness was spawned.
    """
    run = _Run(started=time.monotonic())
    # Seeded, never resolved, above the lock: `Path.cwd()` raises
    # `FileNotFoundError` on a removed working directory, and out here that
    # escapes `review()` and `cli.main` — the one operator-error shape of eight
    # that raised instead of returning `error/INVALID_CONFIG`, while the
    # backstop below names it as covered. `record(result, repo=toplevel or
    # start)` already tolerates `None`, so the seed costs nothing (C-1029).
    start: Path | None = repo
    toplevel: Path | None = None
    dropped: tuple[str, ...] = ()
    # Established beside `dropped` and for the same reason: an `ABSENT` refusal
    # is raised by a layer that was handed one argv word and cannot say whose it
    # is, and the answer — this harness's configured launcher prefix — is known
    # only here.
    launcher: tuple[str, ...] = ()
    with _CALL_LOCK:
        try:
            _require_posix()
            # Resolved here rather than at the seed, so a removed cwd is refused
            # by the `except` ladder like every other operator error instead of
            # raising out of `review()`. Restated as `ConfigError` rather than
            # left to the generic clause below, because that clause answers
            # `indeterminate` and the other seven operator-error shapes answer
            # `error`/`INVALID_CONFIG` — the asymmetry was the finding, and a
            # deleted cwd is an operator error like a mistyped `--repo`.
            if start is None:
                try:
                    start = Path.cwd()
                except OSError as exc:
                    raise ConfigError("the working directory does not exist; pass --repo") from exc
            # The one operator error `_check_target` cannot answer: a mistyped
            # `--repo` never reaches step 6a, because `discover_repo` runs first
            # and `git -C <nothing>` is an `IsolationError` — reporting a typo
            # under the word a consumer reads as "the ephemeral worktree could
            # not be kept out of the repository" is exactly what E44 removed
            # everywhere else. `is_dir` and not `exists`: `git -C` needs a
            # directory, and a `--repo` naming a file is the same typo.
            if not start.is_dir():
                raise ConfigError(f"--repo {str(start)!r} does not name a directory")
            proc_runner = SubprocessRunner() if runner is None else runner
            # Reserved before the environment, because it is what `minimal_env`
            # tests the inbound path variables against, and `workspace()` must be
            # handed the same value or the C-1025 digest splits.
            reserved = Path(tempfile.gettempdir()) / f"{WORKTREE_PREFIX}{secrets.token_hex(8)}"
            bootstrap, _provisional = minimal_env(start, reserved)
            toplevel, _common = discover_repo(start, bootstrap)
            if config is None:
                # The TOP LEVEL, never `start`: this argument is `config.load`'s
                # whole T4b reference (property 6 above), and a caller standing
                # in a subdirectory would otherwise leave an `XDG_CONFIG_HOME`
                # at the repository root outside it.
                cfg, config_warnings = load_config(toplevel)
                run.warnings.extend(config_warnings)
            else:
                cfg = config
            _check_scope(req)
            name = _resolve_harness(req, cfg, run.warnings)
            adapter = adapters.load(name)
            run.harness = name
            harness_cfg = cfg.for_harness(name)
            launcher = harness_cfg.launcher or ()
            spec, run.model_class = resolve_model(adapter.MODELS, harness_cfg)
            run.model = spec.model if spec is not None else None
            built, dropped = minimal_env(toplevel, reserved)
            # Frozen before it crosses the plugin boundary: `adapter.probe` is
            # handed this very object, and it goes on to become `ws.env` and then
            # `Invocation.env`, which `authorize`'s `launch.env` gate never
            # re-inspects (property 1 above).
            env: Mapping[str, str] = MappingProxyType(built)
            # Before the probe, never after it (H13): an absent harness must not
            # be the answer to a target the operator got wrong.
            _check_target(toplevel, req.target, env)
            info = probe_harness(adapter, proc_runner, harness_cfg, env)
            run.harness_version = info.version
            run.verified_against = info.verified_against
            run.heartbeat = Heartbeat(kind=info.heartbeat_kind, last_activity_at=0.0, last_byte_at=0.0)
            run.warnings.extend(_warnings_for(info, env, run.model, req.authored_by))
            policy = TimeoutPolicy.for_kind(info.heartbeat_kind, harness_cfg.timeout)
            # The git phase gets what is LEFT of the very policy the harness run
            # is held to — no second constant and no second key (E54). It is
            # the same run and the same clock; a probe that took 30 s has spent
            # 30 s of it, and `run.started` is where that clock began.
            with workspace(
                toplevel,
                req.target,
                path=reserved,
                env=env,
                max_prompt_bytes=cfg.max_prompt_bytes,
                deadline=run.started + policy.wall_clock_s,
            ) as ws:
                plan = adapter.containment_plan(harness_cfg, info)
                launch = adapter.prepare(ws, info, harness_cfg, req.instructions)
                inv, derived = authorize(adapter, launch, ws, info, plan, _PROBE_CACHE, proc_runner)
                # Outside the `try` on purpose: an `ABSENT` refusal here is a
                # harness that never executed, and the `finally` below would
                # otherwise stamp enforcement fields for it (WP1's row).
                proc = _spawn(proc_runner, inv, name)
                sink: list[str] = []
                try:
                    sup = _supervise(proc, policy, run.heartbeat, info, sink)
                finally:
                    # `raw`, the stamp that describes it and the truncation flag
                    # are established together, because a consumer reads
                    # `secrets_suspected` and `truncated` as a pair (C-1018) and
                    # `_supervise` can raise after the sink is already full — a
                    # kill ladder that hit EPERM leaves output whose credential
                    # scan would otherwise never run. `proc.overflowed` rather
                    # than `sup.truncated`: `sup` is unbound on that path, and
                    # the drain thread's ceiling is the same fact either way.
                    run.raw = "".join(sink)
                    run.truncated = proc.overflowed
                    run.containment = _stamp(ws, info, derived, run.raw)
                if sup.reason is None:
                    # `Supervision.__post_init__` guarantees the status is an int
                    # wherever `reason` is `None`, which is the whole reason the
                    # adapter contract can keep `parse(lines, exit_code: int, hb)`.
                    parsed = adapter.parse(sink, cast("int", sup.exit_code), run.heartbeat)
                    # A non-finite cost is dropped rather than carried: an
                    # adapter reading a harness's cost field gets `NaN` or
                    # `Infinity` back from `json.loads` without an error, and
                    # `json.dumps` writes both out unquoted — one such value
                    # makes a C-1021 log line invalid JSON, and that log is read
                    # with `grep` and `jq` as often as with a parser.
                    cost = parsed.cost_usd
                    run.cost_usd = cost if cost is None or isfinite(cost) else None
                else:
                    parsed = None
                result = _resolve(run, parsed, sup, ws)
        except NoxError as exc:
            status, reason = _reason_for(exc)
            detail = exc.detail if isinstance(exc, HarnessUnavailable) else str(exc)
            if reason is FailureReason.UNAUTHENTICATED:
                detail = _auth_detail(run.harness, detail, dropped)
            elif reason is FailureReason.ABSENT:
                detail = _absent_detail(run.harness, launcher, detail)
            result = _refused(run, status, reason, detail)
        except (SystemExit, Exception) as exc:
            # The plugin boundary (C-1029): four adapters are written
            # independently of this file, and an adapter bug degrades the
            # consumer to `indeterminate` rather than escaping as a traceback.
            # `SystemExit` is named because it is not an `Exception`: an adapter
            # calling `sys.exit()` in `prepare` or `parse` is an ordinary plugin
            # bug, and letting it terminate nox's consumer is the one outcome
            # this boundary exists to prevent. `KeyboardInterrupt` is
            # deliberately not caught — a user's Ctrl-C is not an adapter bug.
            #
            # The wording names the type and NOT the source: this clause also
            # covers nox's own faults, and `Review.detail` is documented as
            # nox's own account rather than a provenance claim it cannot
            # support. It no longer illustrates that with the removed cwd — the
            # example was the one operator error that actually escaped, because
            # `Path.cwd()` ran ABOVE the lock where nothing caught it; it is now
            # resolved inside the `try` and restated as `ConfigError`.
            failure = _AdapterFailure(f"an unexpected {type(exc).__name__} escaped nox or its adapter")
            status, reason = _reason_for(failure)
            result = _refused(run, status, reason, str(failure))
        # Inside the lock, after the `Review` exists and unable to affect it, and
        # serializing the append costs nothing a call already paid.
        # `toplevel or start` rather than `toplevel`, because every refusal above
        # `discover_repo` would otherwise pass `None` and drop the T4b belt
        # `call_log_path` documents as caller-supplied.
        #
        # The one place in nox a bare `suppress(Exception)` is right. `record`
        # swallows the two failures it OWNS (`OSError`, `ConfigError`) and its
        # narrowness there is correct — a `TypeError` from a bad field is a bug
        # and must not be hidden from that module's tests. But the record is
        # built from `Review` fields an adapter supplied, and `ParsedOutput`
        # annotates `reason` and `cost_usd` without validating either at runtime,
        # so a `str` reason or a `Decimal` cost reaches `json.dumps` and raises.
        # C-1029 outranks the log: bookkeeping may not turn a completed review
        # into a traceback.
        with suppress(Exception):
            record(result, repo=toplevel or start)
    return result


def _require_posix() -> None:
    """Refuse a platform whose process model v1 does not implement (D-j).

    The kill ladder signals a POSIX process group, `start_new_session=True` has
    no Windows equivalent that reaches descendants, and `.cmd` resolution on
    `PATH` was never verified. `runner.py` states that this guard lives here, so
    nothing in the process layer branches on the platform and D-j costs no second
    `# pragma: no cover` (C-1015's budget is one).

    Raises:
        UnsupportedCapability: `sys.platform` is `win32`. `UNSUPPORTED` with no
            harness spawned, which is where SD § 7.1 puts both `UNSUPPORTED`
            rows.
    """
    if sys.platform == "win32":
        raise UnsupportedCapability(
            "nox v1 is POSIX-only (D-j): its kill primitive is a process group, `start_new_session` has no Windows "
            "equivalent that reaches descendants, and `.cmd` resolution on PATH was never verified"
        )


def _scope_of(target: ReviewTarget) -> Scope:
    """Which C-1042 scope word a target shape implies.

    The same derivation `workspace()` performs for `Workspace.scope`, read here
    so `review()` can check the caller's declared `scope` against it rather than
    silently preferring one of the two. `Workspace.scope` stays the value
    `prepare` and `render` are given; this is only the agreement check.

    Args:
        target: What is under review.

    Returns:
        `"plan-artifact"` for a `plan-artifact` target, `"code-diff"` otherwise.
    """
    return "plan-artifact" if target.kind == "plan-artifact" else "code-diff"


def _check_scope(req: ReviewRequest) -> None:
    """Refuse a request whose declared scope contradicts its target (C-1042(2)).

    The CLI builds both from `--scope`, so they agree there by construction; a
    Python caller can disagree, and the consequence is silent — a plan artifact
    reviewed under the `code-diff` sentence, or a branch diff introduced to the
    reviewer as a document with no running code.

    Raises:
        ConfigError: The two disagree. `INVALID_CONFIG`, before any repository
            state is touched and before any spawn.
    """
    implied = _scope_of(req.target)
    if req.scope != implied:
        raise ConfigError(
            f"the declared scope {req.scope!r} contradicts a {req.target.kind!r} target, whose scope is "
            f"{implied!r} (C-1042(2))"
        )


def _check_target(repo: Path, target: ReviewTarget, env: Mapping[str, str]) -> None:
    """Refuse a target the operator got wrong, BEFORE the C-1014 probe runs (H13).

    `workspace()` already refuses all three of these — a `--path` that names no
    regular file, a `--path` outside the repository, a commit-ish that does not
    resolve — and it stays the authority. What it cannot do is answer FIRST: the
    call order is `probe_harness` → `workspace`, so a harness that is not
    installed refused before any of them was looked at, and a mistyped `--base`,
    a `--path` pointing outside the tree and a `--path` naming nothing all came
    back as `<launcher>: not found as an executable on the minimal PATH`. Three
    distinct operator errors, one message, and the one thing it told the
    operator to do was the one thing that would not have helped.

    This is a *pre-flight*, not a second authority. It may only be more
    permissive than `workspace()`'s own step 4 and step 6, never stricter: if
    the two ever drift, the consequence is that the probe answers first again —
    the bug this closes — and never that an unusable target gets through.

    It touches no repository state, which is what lets it move ahead of the
    probe at all. `resolve_pair` on a `"ref"` shape is two `rev-parse`s and a
    `merge-base`, `check_git_version` is a `git --version`, and the artifact
    half is `artifact_rel`'s `stat`. None writes an object, a ref, the index or
    the working tree, and none runs `sweep`.

    **The refusal is `ConfigError` and not `IsolationError`.** A commit-ish that
    does not resolve is the operator's input, which is what `INVALID_CONFIG`
    means; `ISOLATION_FAILED` is the word a consumer reads as "the ephemeral
    worktree could not be kept out of the repository", and reporting a typo
    under it spends the one reason that should make a reader stop. The message
    names the flag and the value, the way the `plan-artifact` refusals already
    do, and carries none of git's own stderr — `rev-parse`'s text is
    branch-controlled (C-1035(1)) and says nothing the flag and the value do not.

    **And the conversion runs one way only.** `resolve_pair` reports a git that
    is absent, unrunnable or below the C-1041 floor as an `IsolationError` too,
    so a blanket `except IsolationError` here made the reason word depend on
    which sentence happened to be true — a stale git came back as a mistyped
    `--base` under `INVALID_CONFIG`, which is the mirror image of the bug this
    function exists to close. `check_git_version` runs first and outside the
    catch, so what is left inside it is the operator's own spec. The residue is
    a damaged object store, which git reports through the same exit status as an
    unknown revision and which no caller can separate from a typo.

    Neither half restates `workspace()`'s checks: `artifact_rel` and
    `check_git_version` are the same functions `workspace()` calls, imported
    rather than copied, because the copy that used to live here is what drifted.

    ponytail: `ReviewTarget(kind="ref", ref=spec, base=spec)` is a one-commit
    probe built out of the only public resolver there is — with `base == ref`,
    `resolve_pair` resolves that single commit-ish and takes its merge-base with
    itself, which is the same commit. `base=None` would take the `<ref>^`
    branch instead and refuse a root commit for having no parent, which is a
    legitimate `--base`. The ceiling is that this is three git processes to
    answer one question; the upgrade path is a public single-commit resolver in
    `workspace.py` (its `_commit` is exactly that function, and importing a
    private across modules is what pyright strict refuses).

    Args:
        repo: The repository top level, as `discover_repo` resolved it.
        target: What is under review.
        env: The C-1008 minimal environment, for the git calls.

    Raises:
        ConfigError: The artifact is missing, is not a regular file or resolves
            outside `repo` (C-1027), or a commit-ish the caller supplied names
            no commit. `INVALID_CONFIG` on every one of them.
        IsolationError: The artifact path could not be resolved at all — a
            relative `path` is resolved against nox's cwd and `os.getcwd()`
            raises once that directory is gone — or git is absent, unrunnable or
            below the C-1041 floor. Each is a real isolation failure and keeps
            its own word.
    """
    if target.kind == "plan-artifact":
        # `workspace()`'s own step 4, CALLED rather than restated: the sentence
        # the operator reads is the same whichever of the two fires, and the
        # copy that used to live here proved the point by drifting — it dropped
        # `artifact_rel`'s `_isolating` guard, so a removed cwd escaped as a
        # bare `FileNotFoundError` and degraded to `indeterminate` instead of
        # refusing `ISOLATION_FAILED`. Only the flag is added here, which is the
        # one thing `workspace()` cannot know.
        try:
            artifact_rel(repo, target.path)
        except ConfigError as exc:
            raise ConfigError(f"--path: {exc}") from exc
        return
    specs = tuple(
        (flag, spec)
        for flag, spec in (("--base", target.base), ("the review target ref", target.ref))
        if spec is not None
    )
    if not specs:
        return
    # OUTSIDE the catch below, and first: `resolve_pair` reports a git that is
    # absent, unrunnable or below the C-1041 floor as an `IsolationError` too,
    # and a blanket catch called all three a mistyped commit — telling an
    # operator whose git cannot run `GIT_CONFIG_COUNT` that their `--base` is
    # wrong. Establishing that git itself is usable is what leaves the operator's
    # own input as the only thing the conversion below can be about.
    check_git_version(repo, env)
    for flag, spec in specs:
        try:
            resolve_pair(repo, ReviewTarget(kind="ref", ref=spec, base=spec), env)
        except IsolationError as exc:
            raise ConfigError(f"{flag} {spec!r} does not name a commit in this repository") from exc


def _absent_detail(harness: str, launcher: Sequence[str], detail: str) -> str:
    """Say whose executable was missing when a launcher prefix hides the answer.

    `launch_argv` resolves the launcher PREFIX's head, because that is what
    `execve` actually runs — so a harness reachable only through
    `ocx package exec … -- opencode` reports `ocx` when the wrapper is what is
    absent. `resolve_executable` is handed one word and cannot say more, and the
    word it names is one the operator never typed and that no user-facing
    surface of nox mentions: the flag is `--harness opencode`, the config key is
    `[harness.opencode]`, and `ocx` appears in neither. The sentence is completed
    here, which is the one place the registry key and the configured prefix are
    both in scope — the same reason `_auth_detail` sits here.

    An `ABSENT` detail that already names the harness is the adapter's own
    account (`codex: ran but named no version`) and travels untouched: rewriting
    it would replace a true statement about the binary with a false one about
    the wrapper.

    Args:
        harness: The resolved registry key — what the operator asked for.
        launcher: This harness's configured launcher prefix; empty when it runs
            as a bare binary, in which case the raiser's word IS the harness's.
        detail: The raiser's own account.

    Returns:
        `detail`, or a sentence naming the harness and its launcher.
    """
    if not launcher or harness in detail:
        return detail
    return (
        f"{harness} could not be started: it is configured to run behind the launcher {launcher[0]}, and that "
        f"launcher was not found as an executable on the minimal PATH nox builds"
    )


def _resolve_harness(req: ReviewRequest, cfg: NoxConfig, warnings: list[str]) -> str:
    """Pick the adversary and refuse a self-review (C-1042(5-6), S-1011).

    Precedence is `--harness` > `[review] harness` > refusal, with **no shipped
    default**: the explicit cross-model choice is the product claim, and a
    default would quietly turn a mis-typed pin into a same-model review.

    The `--exclude` comparison is against the **resolved** harness and never
    against `req.harness`. `[review] harness` is deliberately not trust-gated
    (C-1042(5)), so a hostile repository can name the adversary — and a check
    that read the CLI flag would pass `--exclude claude` while the repository
    steered the run straight back to `claude`.

    Membership in `ADAPTERS` is `adapters.load`'s to check for the harness
    itself; `--exclude` is checked here, because an unknown exclusion is a
    typo that silently disables the gate and nothing downstream would look at it.

    Args:
        req: The caller's request.
        cfg: The resolved configuration.
        warnings: Accumulator; the C-1042(6) missing-`--exclude` notice lands here.

    Returns:
        The name to hand `adapters.load`. Not yet known to be a registry key.

    Raises:
        ConfigError: No harness on either route — the message names every key in
            `ADAPTERS`, generated from the registry so a fifth adapter needs no
            edit here. Also an `--exclude` outside the registry, and an
            `--exclude` equal to the resolved harness, both naming the values:
            they are nox's own caller's words, not the repository's.
    """
    name = req.harness or cfg.review_harness
    registered = ", ".join(sorted(adapters.ADAPTERS))
    if name is None:
        raise ConfigError(
            f"no harness was named on either route and nox ships no default (C-1042(5)); registered: {registered}"
        )
    if req.exclude is None:
        warnings.append(MISSING_EXCLUDE_WARNING)
    elif req.exclude not in adapters.ADAPTERS:
        raise ConfigError(f"the excluded harness {req.exclude!r} is not registered; registered: {registered}")
    elif req.exclude == name:
        raise ConfigError(
            f"the resolved harness {name!r} is the one the caller excluded — nox may not run the adversary as the "
            "client that produced the change (S-1011)"
        )
    return name


def _warnings_for(info: HarnessInfo, env: Mapping[str, str], model: str | None, authored_by: str | None) -> list[str]:
    """The four C-1035 sources that are not the config load, in a fixed order.

    C-1035 fixes the source set at five and this is where four of them are
    actually called — each lives in another module and none had a caller in
    `src/` before this file:

    1. `config.load`'s own warnings, threaded in by `review()` (not here);
    2. `harness.version_warning(info)` — the C-1020 `verified_against` mismatch;
    3. `config.world_writable_forwards(env)` — the C-1008 forward under a
       directory any local user can plant configuration in;
    4. `harness.asymmetry_warning(authored_by, model)` — the C-1036 measured
       negative pair, keyed on the **model** pair so a harness swap alone neither
       fires nor silences it;
    5. `MISSING_EXCLUDE_WARNING` — C-1042(6), raised earlier by
       `_resolve_harness` because it is decided before the probe.

    **No warning may carry an environment value, a `$HOME` path outside the
    repository, or any substring of `raw`** (C-1035(1)). Each of the four
    functions above already holds that property; this composes them and adds no
    text of its own.

    Args:
        info: What the probe established.
        env: The C-1008 minimal environment.
        model: The resolved reviewer literal, or `None`.
        authored_by: The model that wrote the change, or `None`.

    Returns:
        The warnings from sources 2-4, in that order.
    """
    sources = (version_warning(info), *world_writable_forwards(env), asymmetry_warning(authored_by, model))
    return [item for item in sources if item is not None]


def _scan_for_credentials(raw: str) -> bool:
    """Whether `raw` carries a known credential shape (C-1018).

    Under Codex the containment mechanism is an OS sandbox, and a read-only
    sandbox denies writes and network reach — **not reads**. A model-generated
    command can therefore `cat ~/.aws/credentials`, and the review body is an
    egress channel by definition because a human reads it. The answer is a flag,
    never a redaction: what the user needs to know is that something was read.

    Args:
        raw: The harness's retained output.

    Returns:
        Whether any `CREDENTIAL_SHAPES` member appears in it. `False` is
        meaningless unless a harness produced output at all, which is why
        `Containment.secrets_suspected` is documented as read together with
        `truncated`.
    """
    return any(shape in raw for shape in CREDENTIAL_SHAPES)


def _completeness_finding(ws: Workspace) -> Finding | None:
    """The `origin="nox"` finding for a review that was shown less than the change.

    The one element of `findings` that is not untrusted harness output (C-1019),
    which is what `Finding.origin` exists to make machine-readable rather than a
    distinction a consumer draws by eye.

    Three inputs, and they do not carry the same weight:

    - `omitted` — untracked paths the review never carried (C-1026). **`high`**,
      and the verdict may not be `approve`.
    - `filtered_changed` — entries dropped by mode that **differ** between the
      two ends (C-1043(4)). **`high`**, same consequence. Deliberately not
      `Workspace.filtered`, which is the union over both ends and is C-1043(2)
      *evidence*: a repository merely carrying a committed symlink populates it
      forever, and reading it as a verdict input would make such a repository
      permanently un-approvable.
    - `omitted_ignored` — how many untracked paths git's ignore rules hid from
      `omitted`. **`suggest`, and never a verdict override.** WP2 added the count
      because the governing `.gitignore` is the one currently checked out, so a
      `*` in it empties `omitted` and makes the completeness stamp read clean.
      It cannot force `needs-attention`: build output is the overwhelming
      majority and every repository with a `.gitignore` would become
      permanently un-approvable — which is the "disabled within a week" failure
      C-1026 names about itself. Making it visible is the whole remedy.

    Counts are stated as **"N of M"** wherever the list was capped: all four
    `Workspace` lists stop at `ENUMERATION_BUDGET` and each ships its untruncated
    `*_total` beside it, so `len(...)` on a capped list is a false count in the
    one finding C-1019 tells the consumer *is* nox's own. Stated that way
    unconditionally rather than only past the cap: "2 of 2" is true and costs a
    reader nothing, while a branch on `len(...) < total` is a second place the
    rule can be forgotten and the uncapped rendering is the one every ordinary
    review would exercise.

    Args:
        ws: The live workspace, which owns all three lists and their totals.

    Returns:
        One `Finding`, or `None` when nothing was withheld and nothing was
        ignored.
    """
    parts: list[str] = []
    if ws.omitted:
        parts.append(
            f"untracked paths not carried into the review ({len(ws.omitted)} of {ws.omitted_total}): "
            f"{', '.join(ws.omitted)}"
        )
    if ws.filtered_changed:
        parts.append(
            f"entries dropped by mode that differ between the two ends "
            f"({len(ws.filtered_changed)} of {ws.filtered_changed_total}): {', '.join(ws.filtered_changed)}"
        )
    if ws.omitted_ignored:
        parts.append(f"untracked paths the checked-out ignore rules hid: {ws.omitted_ignored}")
    if not parts:
        return None
    withheld = bool(ws.omitted or ws.filtered_changed)
    return Finding(
        severity="high" if withheld else "suggest",
        title=(
            "the reviewer was shown less than the change"
            if withheld
            else "untracked paths were hidden by the checked-out ignore rules"
        ),
        body="\n".join(parts),
        confidence="high",
        origin="nox",
    )


def _semantic(line: str, info: HarnessInfo) -> bool:
    """Whether one output line is a semantic progress event (C-1010).

    `Adapter` has no per-line hook — its six methods are probe, sandbox probe,
    containment plan, prepare, classify and parse — so this judgement is core's,
    and `runner.OnLine` is the seam it is delivered through. The discriminator is
    the one thing every `SEMANTIC` harness in v1 shares: its events are one JSON
    object per line (`--output-format stream-json`, `--json`, `--format json`),
    and its noise — a Node deprecation warning, a stack trace, a progress bar —
    is not.

    A `BYTE_ACTIVITY` harness answers `False` for every line and its 300 s window
    still measures, because `supervise` runs that window against `last_byte_at`.
    `PROCESS_ONLY` skips the silence check entirely.

    Answering `True` for noise would corrupt `Heartbeat.events`, which is the
    evidence a `TIMED_OUT` detail is written from — so the failure direction here
    is a run killed at the silence bound, never one kept alive by its own stack
    trace. A hostile diff cannot manufacture events either: the harness has to
    emit the line.

    ponytail: the `{` … `}` shape test is a **prefilter**, and the parse runs
    behind it rather than instead of it. Shape alone accepts a strict superset of
    JSON objects, so every disagreement between the two would be noise counted as
    progress — a run kept alive by a `console.log({ foo: 1 })` a stalled harness
    repeats inside the silence window, which inverts the failure direction fixed
    two paragraphs above. Parsing every line unconditionally is the other error:
    work proportional to `runner.BYTE_CAP`'s 8 MiB of attacker-chosen text to
    answer a boolean. With the prefilter first the cost is proportional to
    brace-shaped bytes only. The remaining ceiling is a JSON object that is not an
    event — a harness whose *noise* is well-formed JSON objects; the upgrade path
    is a per-adapter discriminator, which needs a seventh `Adapter` method.

    Args:
        line: One line of the merged output stream, newline included.
        info: What the probe established, for `heartbeat_kind`.

    Returns:
        Whether the line counts as progress.
    """
    stripped = line.strip()
    if info.heartbeat_kind is not Liveness.SEMANTIC or not (stripped.startswith("{") and stripped.endswith("}")):
        return False
    try:
        return isinstance(json.loads(stripped), dict)
    except (ValueError, RecursionError):
        # `RecursionError` is a `RuntimeError`, so `ValueError` alone never
        # caught it, and `json` reaches it at a nesting depth of roughly 1200 on
        # the DECLARED 3.11 floor against above 20000 from 3.12 — a difference a
        # dev venv resolved to the newest interpreter cannot see. The line that
        # gets there is 7 KB the harness chose, well inside `runner.BYTE_CAP`,
        # and one escaping here escapes `supervise` too and lands on `review()`'s
        # plugin-boundary backstop, which discards a COMPLETED review as
        # `indeterminate`. `config.py` names the same three-way clause for the
        # same reason at each of its own `json`/`tomllib` reads.
        return False


def _spawn(runner: Runner, inv: Invocation, harness: str) -> Process:
    """Start the review, mapping `spawn`'s `OSError` leak onto a `NoxError` (C-1029).

    `resolve_executable` already checked that `argv[0]` is on the minimal `PATH`
    and executable, so this fires on a race — the binary replaced or unlinked
    between resolution and `execve` — and on the refusals `which` cannot see
    (`noexec`, a full descriptor table). `ABSENT` either way: nox could not run
    the harness, which is the row a consumer degrades to a graceful skip on
    (SD § 7.1).

    Args:
        runner: The process seam.
        inv: The `Invocation` `authorize` produced.
        harness: The registry key, for the message.

    Returns:
        The running child.

    Raises:
        HarnessUnavailable: `ABSENT`, naming the harness and the exception TYPE
            — an `OSError`'s message carries the resolved path, which is a
            `$HOME` path outside the repository (C-1035(1)).
    """
    try:
        return runner.spawn(inv)
    except OSError as exc:
        raise HarnessUnavailable(
            FailureReason.ABSENT, f"{harness} could not be started ({type(exc).__name__})"
        ) from exc


def _supervise(
    proc: Process,
    policy: TimeoutPolicy,
    hb: Heartbeat,
    info: HarnessInfo,
    sink: list[str],
) -> Supervision:
    """Supervise the run, mapping `supervise`'s `OSError` leak onto a `NoxError` (C-1029).

    `_kill_group` swallows `ESRCH` and propagates everything else — an `EPERM`
    from the first rung must not abandon the child one rung short — so a refused
    signal reaches this boundary as an `OSError` rather than as an outcome.

    Args:
        proc: The running child.
        policy: The bounds this run is held to.
        hb: Progress evidence, mutated in place.
        info: What the probe established, for the `_semantic` judgement.
        sink: Where every line is retained, in order, for `raw`. Appended to as
            the run proceeds, so a failure part-way through still leaves the
            caller what the harness had produced.

    Returns:
        What the run resolved to before any adapter parsed a byte of it.

    Raises:
        _SupervisorFailure: The kill ladder itself failed. The harness may still
            be running; the message says so and never the opposite (D-ac).
    """

    def on_line(line: str) -> bool:
        sink.append(line)
        return _semantic(line, info)

    try:
        return supervise(proc, policy, hb, on_line)
    except OSError as exc:
        raise _SupervisorFailure(
            f"the kill ladder failed ({type(exc).__name__}); nox has stopped supervising this run and the harness "
            "may still be running"
        ) from exc


def _stamp(ws: Workspace, info: HarnessInfo, derived: ContainmentPlan, raw: str) -> Containment:
    """Build the `Containment` for a run that reached a harness (C-1025).

    The three enforcement fields come from the **derived** plan `authorize`
    returned, never from the adapter's `containment_plan` claim: derivation is
    what re-checks each axis against the resolved argv and env, and stamping the
    claim would restore exactly the assertion C-1025 exists to remove.

    `enforced_read_only` is `harness.enforced_read_only(info)` — read off the
    probed capability set rather than hand-set here, so the C-1013 stamp and the
    C-1013 gate cannot disagree. `env_scrubbed` is `True`: `authorize` builds
    `Invocation.env` from `ws.env`, which is a `minimal_env` product by
    construction, and this function is only ever called on the spawn path.

    `filtered` is `Workspace.filtered`, the union over both ends: it is C-1043(2)
    evidence about what the reviewer could not see, and the *differing* subset
    that gates the verdict is `filtered_changed`, which reaches the consumer
    through `_completeness_finding` instead. The two are deliberately not
    conflated, which is also why only three of the four lists are stamped and
    `filtered_changed_total` is not among the totals copied here.

    Each list carries its `Workspace` total, never `len(...)`: all four are
    capped at `ENUMERATION_BUDGET`, and a consumer reading the stamp rather than
    the completeness finding would otherwise read the cap as the count.

    Called from exactly one place — the `finally` that assembles `run.raw`,
    which `review()` enters only once `_spawn` has returned a running child.
    That single site is what makes both halves of WP1's row hold at once: a
    harness that never started keeps `NOT_RUN`, and a refusal after one did run
    (the kill ladder failing, `parse` raising) carries the enforcement fields
    *and* a `secrets_suspected` the C-1018 scan read off real output.

    Args:
        ws: The live workspace, which owns all four evidence lists.
        info: What the probe established.
        derived: `authorize`'s second return value.
        raw: The harness's retained output, for the C-1018 scan.

    Returns:
        The stamp.
    """
    return Containment(
        isolation="worktree",
        neutralized=ws.neutralized,
        neutralized_total=ws.neutralized_total,
        omitted=ws.omitted,
        omitted_total=ws.omitted_total,
        filtered=ws.filtered,
        filtered_total=ws.filtered_total,
        mechanism=derived.mechanism,
        write_enforcement=derived.write_enforcement,
        network_enforcement=derived.network_enforcement,
        enforced_read_only=enforced_read_only(info),
        env_scrubbed=True,
        secrets_suspected=_scan_for_credentials(raw),
    )


def _resolve(run: _Run, parsed: ParsedOutput | None, sup: Supervision, ws: Workspace) -> Review:
    """Turn a completed run into the `Review`, applying nox's own overrides.

    Three steps, in this order:

    1. **The supervisor's forced outcome wins.** `Supervision.reason` is
       non-`None` only where `supervise` itself ended the run, and `parse` is not
       called on that path at all — `Supervision.__post_init__` guarantees the
       exit status is an `int` wherever `reason` is `None`, which is what lets
       the adapter contract keep `parse(lines, exit_code: int, hb)`. WP3's row
       makes the status resolution WP8's: `TIMED_OUT` and `KILLED` resolve
       **`error`** (SD § 7.1), and `MALFORMED_OUTPUT` resolves
       **`indeterminate`**. That last one is E16: E7's prose said `error`, SD
       § 7.1 lists the 8 MiB cap as a *modifier* (`truncated=True`) rather than a
       status of its own, and the later text wins.
    2. **Otherwise the adapter's `ParsedOutput` is the answer**, tri-state
       invariants already enforced by its own `__post_init__`.
    3. **Then C-1026 and C-1043(4).** `_completeness_finding` is appended
       whenever it fires, and a **`high`** one — non-empty `omitted` or
       `filtered_changed` — overrides a `verdict` of `approve` to
       `needs-attention`. `Verdict` has exactly two members, so "may not be
       `approve`" is an override rather than a refusal, and the review still
       returns its findings. A `suggest` one (ignored untracked paths only) never
       touches the verdict.

    The finding is appended on every status **this function resolves** — the
    supervisor's forced outcomes included, not only `ok` — and the verdict
    override is vacuous off the `ok` path, where `verdict` is already `None`
    (C-1018). It does **not** reach a refusal: `_refused` returns `findings=()`,
    so a post-spawn refusal carries the withheld paths in `Containment` alone.
    That is the deliberate split — `Containment` is populated on every path and
    is where a consumer reads what the reviewer could not see; the finding is
    its human-readable form for a run that produced a review to attach it to.

    **`summary` is left as the harness wrote it.** C-1026 asks for the summary to
    "lead with" the completeness statement, which predates `Finding.origin` —
    the provenance mechanism the same pass added. `Review.summary` is documented
    as the harness's own prose and untrusted under C-1019, so nox prose written
    into it would be exactly the by-eye distinction `origin` removes. The
    statement goes in the finding instead.

    Args:
        run: What has been established so far, including `raw` and the stamp.
        parsed: The adapter's result, or `None` when the supervisor forced the
            outcome.
        sup: What the supervisor resolved.
        ws: The live workspace, for the completeness lists.

    Returns:
        The review.
    """
    if parsed is None:
        status: Status = "indeterminate" if sup.reason is FailureReason.MALFORMED_OUTPUT else "error"
        verdict: Verdict | None = None
        findings: tuple[Finding, ...] = ()
        summary, detail, reason = "", _safe(sup.detail), sup.reason
    else:
        status, verdict, findings = parsed.status, parsed.verdict, parsed.findings
        # `parsed.detail` is the adapter's, and on this path the adapter has just
        # read harness output — so it is the one `detail` that can carry a byte
        # the harness chose. `cli.render` prints `detail` to the consumer's
        # terminal (C-1042(7) makes prose the only channel), which is what makes
        # an ESC here a repaint rather than a cosmetic issue.
        summary, detail, reason = parsed.summary, _safe(parsed.detail), parsed.reason
    finding = _completeness_finding(ws)
    if finding is not None:
        findings = (*findings, finding)
        if finding.severity == "high" and verdict == "approve":
            verdict = "needs-attention"
    return Review(
        status=status,
        verdict=verdict,
        findings=findings,
        summary=summary,
        detail=detail,
        raw=run.raw,
        truncated=run.truncated,
        reason=reason,
        harness=run.harness,
        harness_version=run.harness_version,
        verified_against=run.verified_against,
        model=run.model,
        model_class=run.model_class,
        heartbeat=run.heartbeat,
        containment=run.containment,
        duration_s=time.monotonic() - run.started,
        cost_usd=run.cost_usd,
        warnings=tuple(run.warnings),
    )


_MAX_DETAIL_CHARS: Final[int] = 1024
"""Cap on the flattened detail (C-1035(1)), well above every message nox writes itself.

`config._MAX_NAME_CHARS` bounds one interpolated name; this bounds the whole
account, because two of its sources are unbounded at the source — git's own
stderr and the offender list a re-check names.
"""


def _safe_detail(text: str) -> str:
    """Flatten a detail to one bounded line of printable text (C-1035).

    `Review.detail` is documented as nox's own account, but neither site that
    assembles one is handed nox's own prose: `_refused` gets `str(exc)` for every
    `NoxError` that is not a `HarnessUnavailable` — and `workspace.py` raises
    `IsolationError` around git's stderr and around repository paths — while
    `_resolve` gets an adapter's `ParsedOutput.detail`, a plugin's output. A
    committed filename carrying an ESC byte repaints the reader's terminal, and
    one carrying a newline can open a line that reads like nox's own prose in
    the block the CLI prints.

    `str.isprintable()` rather than a control-range pattern, and it is the same
    test `config._safe_name` applies: the control range is only the loudest
    quarter of the problem. A bidi override reorders what a human reads while
    the bytes stay put, a line separator is a line break to every renderer
    downstream, and a lone surrogate — what `os.fsdecode` yields for an
    undecodable byte in a path — raises `UnicodeEncodeError` in whatever writes
    the prose out, which is a denial of service from one committed filename.
    One category test covers all four.

    Bounded for a reason `raw` is not: `raw` is retained whole and deliberately
    kept OUT of the prose form, while this is printed into it, so an unbounded
    account pushes the containment stamp and the warnings out of a reader's view.
    `Finding.title` and `Finding.body` deliberately get none of this — C-1019
    asks the consumer to weigh the reviewer's argument, and mangling it destroys
    the evidence. This is nox speaking; that is the reviewer speaking, quoted.

    A sanitizer, not a quoter: nox's own messages are single-line printable
    prose well under the cap and come through byte-identical, so the readable
    path pays nothing — and the whole-string `str.isprintable()` is what makes
    that literally true rather than nearly true. Without it the per-character
    comprehension ran on EVERY account, and because the cap is applied to the
    result it bounded none of that cost: a 400 KB printable account measured
    2.11 ms against 0.30 ms with the pre-scan. `isprintable` and not `isascii`,
    for the reason `workspace._escape` gives: the C0 controls are ASCII, so
    "ASCII" is not "nothing to do here".

    An account that really does carry a non-printable still walks itself
    (1.9 ms per 400 KB, 7.7 ms if every character is one), and that residue is
    accepted rather than chased. Splitting the walk into `isprintable`-tested
    chunks was measured — 10x on ONE sparse ESC and nothing at all when the
    controls are dense — which buys a shape rather than a bound, and this
    function's semantics admit no bound: the collapse below can consume any
    amount of input to produce one character of output.

    **The cap stays after the flattening**, unlike `config._safe_name`'s, and is
    deliberately not moved in front of it: `.split()` collapses a whitespace run
    to one separator, so a cut applied to the input drops everything past a long
    run that the documented behaviour keeps. The two orders return different
    accounts and `test_a_detail_is_cut_after_its_whitespace_collapses_and_never_before`
    is the pin. What stays linear is an account made *entirely* of
    non-printables (7.7 ms per 400 KB); no bound is reachable there without
    changing what this returns.

    Args:
        text: The detail as assembled.

    Returns:
        `text` with every non-printable character replaced by a space, every
        whitespace run collapsed to one, and an ellipsis where the cap cut it.
    """
    printable = text if text.isprintable() else "".join(char if char.isprintable() else " " for char in text)
    flattened = " ".join(printable.split())
    if len(flattened) <= _MAX_DETAIL_CHARS:
        return flattened
    return f"{flattened[:_MAX_DETAIL_CHARS]}…"


def _safe(text: str | None) -> str | None:
    """`_safe_detail` for the optional `detail`, so both `Review` sites flatten alike.

    `_resolve` and `_refused` are the only two places in nox that build a
    `Review`, which is what makes flattening at both of them complete — the
    obligation does not have to reach `outcome.Review.__post_init__`, where it
    would also run on every adapter test that builds one by hand.
    """
    return None if text is None else _safe_detail(text)


def _refused(run: _Run, status: Status, reason: FailureReason, detail: str) -> Review:
    """Build the `Review` for a path that produced no parseable result (C-1019, C-1029).

    Every field that was never established keeps its no-evidence value, and
    `containment` is whatever `run` carries — `NOT_RUN` for a **pre-spawn**
    refusal (WP1's row: a per-call-site enforcement value would be a claim
    nothing derived), and the real `_stamp` for anything after `authorize`,
    because a harness that ran and then hit the kill ladder is not a harness that
    never ran.

    `raw` is `run.raw`, so a post-spawn refusal still surfaces what the harness
    produced — which is also what makes `secrets_suspected` meaningful on that
    path.

    Args:
        run: What had been established when the refusal fired.
        status: `error` or `indeterminate` — never `ok`.
        reason: The mapped `FailureReason`.
        detail: nox's OWN account. Never harness output, never an environment
            value, never a `$HOME` path outside the repository (C-1035).
            Flattened here rather than trusted, because two `IsolationError`
            sites build it from branch-controlled bytes; `_resolve` owes its own
            route the same call, and the two of them are every site that exists.

    Returns:
        The review.
    """
    return Review(
        status=status,
        verdict=None,
        findings=(),
        summary="",
        detail=_safe_detail(detail),
        raw=run.raw,
        truncated=run.truncated,
        reason=reason,
        harness=run.harness,
        harness_version=run.harness_version,
        verified_against=run.verified_against,
        model=run.model,
        model_class=run.model_class,
        heartbeat=run.heartbeat,
        containment=run.containment,
        duration_s=time.monotonic() - run.started,
        cost_usd=run.cost_usd,
        warnings=tuple(run.warnings),
    )


def _reason_for(exc: NoxError) -> tuple[Status, FailureReason]:
    """Map one internal exception onto its row in SD § 7.1 (C-1029).

    | Exception | `status` | `reason` |
    |---|---|---|
    | `HarnessUnavailable` | `error` | its own `reason` (`ABSENT`, `UNAUTHENTICATED`, `UNSUPPORTED`) |
    | `UnsupportedCapability` | `error` | `UNSUPPORTED` |
    | `ConfigError` | `error` | `INVALID_CONFIG` |
    | `IsolationError` | `error` | `ISOLATION_FAILED` |
    | `_SupervisorFailure` | `error` | `KILLED` |
    | `_AdapterFailure` | `indeterminate` | `MALFORMED_OUTPUT` |
    | any other `NoxError` | `indeterminate` | `MALFORMED_OUTPUT` |

    Args:
        exc: What escaped.

    Returns:
        `(status, reason)`. An unmapped `NoxError` subclass resolves
        `indeterminate` rather than `error`: nox does not know what happened, and
        the tri-state exists so that answer does not have to be forced into one
        of the other two.
    """
    if isinstance(exc, HarnessUnavailable):
        return "error", exc.reason
    if isinstance(exc, UnsupportedCapability):
        return "error", FailureReason.UNSUPPORTED
    if isinstance(exc, ConfigError):
        return "error", FailureReason.INVALID_CONFIG
    if isinstance(exc, IsolationError):
        return "error", FailureReason.ISOLATION_FAILED
    if isinstance(exc, _SupervisorFailure):
        return "error", FailureReason.KILLED
    return "indeterminate", FailureReason.MALFORMED_OUTPUT


def _auth_detail(harness: str, detail: str, dropped: Sequence[str]) -> str:
    """Extend an `UNAUTHENTICATED` refusal with the credential names nox dropped (C-1034(4)).

    `Adapter.probe` raises `HarnessUnavailable` but never sees `minimal_env`'s
    dropped names, so the join happens here — a harness that ran and refused for
    want of credentials is usually a harness whose API key nox declined to
    forward, and saying so is the difference between a bug report and a one-line
    fix. Names only, never values.

    `dropped` is the **second** `minimal_env` pass's list, the one built against
    the discovered top level: it is the superset, since the second pass drops
    every inbound path variable resolving inside the repository as well as
    everything the first pass dropped.

    Args:
        harness: The registry key, for the `AUTH_ENV_HINTS` entry.
        detail: The adapter's own account.
        dropped: `minimal_env`'s dropped names.

    Returns:
        `detail` followed by `config.auth_hint`'s sentence pair.
    """
    return f"{detail} {auth_hint(harness, dropped)}"
