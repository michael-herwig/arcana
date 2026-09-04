"""The live NxN cross-harness smoke: every harness driving nox against every harness (D-ab).

Not part of the `nox` package and never shipped inside `nox.pyz`: this is an
operator tool that spends real tokens on four vendors' meters, and it sits
outside the test tiers because nothing here is hermetic — every cell reaches the
network twice, once as the *driver* harness and once as the *adversary* nox
spawns underneath it.

**The two sides are different argv and must not be confused.** The adversary
side is the adapter's review argv, which `nox` owns; the driver side is the
harness's own headless-prompt argv, which is what `DRIVERS` holds. A cell is
`driver`, in its own headless mode, asked to run one `nox review` whose
`--harness` is `adversary`. A pass is therefore evidence that a foreign harness
drives nox end to end, and the self-pairs are a smoke that nothing special-cases
the same-harness path. Self-review is not a product claim (SD § 9.1, E14).

**A self-pair omits `--exclude`.** `api._resolve_harness` refuses an `--exclude`
equal to the resolved harness (S-1011), so `claude → claude` runs with no
exclusion and takes the `MISSING_EXCLUDE_WARNING` path instead. That is the
honest shape: the gate is caller-supplied, and here the caller genuinely is the
harness under review.

**The judged evidence is the report file, not the driver's stdout.** Step 12.1
words the assertions as "on the driver's stdout"; this ships them against the
file nox itself writes, because a driver that *narrates* ("I would run this; the
output would show `harness: copilot` …") satisfies every stdout substring
assertion without executing anything — the file exists only if the command ran.
The driver's captured output is still kept, as the tail printed on a failure.
It also keeps the adversary's untrusted findings out of the driver's context.

**Every cell writes a transcript, because a red cell has to stay attributable.**
This matrix has failed twice and neither failure could be named, because the
cell's output had scrolled by the time anyone looked; "transient and
unattributed" is what a test harness reports when it cannot tell you what broke.
So each cell's argv, exit status, report and full output go to a file under
`RUNS_ROOT`, a re-run gets its own directory rather than overwriting the one it
is re-running, and the tally names the transcript of every cell that failed.
There is deliberately **no retry, no tolerance and no flake budget**: a tolerance
turns a real intermittent failure into noise, which is worse than a red cell
somebody has to look at. The problem was that the evidence evaporated.

The cell list is derived from `nox.adapters.ADAPTERS`, never written out here: a
fifth adapter makes the matrix 25 cells with no edit to this file. `DRIVERS` is
keyed by the same registry strings, and a *missing* entry is a `skip` rather
than a crash — that is the path for a future adapter registered before its
driver form is pinned. All four v1 forms ship pinned (§ Environment probe).
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal, get_args

from nox.adapters import ADAPTERS, load
from nox.capability import ModelClass, ModelSpecT
from nox.config import DEFAULT_TIMEOUT_S
from nox.outcome import FailureReason, Mechanism

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "CELL_TIMEOUT_S",
    "DEFECT",
    "DEFECT_MARKERS",
    "DRIVERS",
    "EXIT_SKIP",
    "MODEL",
    "MODEL_CLASS",
    "MODEL_ENV",
    "RUNS_ENV",
    "RUNS_ROOT",
    "SKIP_REASONS",
    "TIMEOUT_ENV",
    "Cell",
    "cells",
    "driver_model",
    "exit_code",
    "fixture",
    "judge",
    "main",
    "run_cell",
    "runs_dir",
]

Outcome = Literal["pass", "fail", "skip"]
"""What one cell reports. `skip` is an environment condition, never a defect."""

EXIT_SKIP: Final[int] = 77
"""What a single skipped cell returns. Distinct from `0` (pass) and `1` (fail).

Only `task nox:manual:cell` can return it: the matrix's contract is "non-zero
iff a cell *failed*", so a sweep whose opencode legs skip still exits `0`.
"""

MODEL_CLASS: Final[ModelClass] = "fast-balanced"
"""The capability class BOTH sides of every cell resolve (C-1030).

Never a literal, and never the same table on both sides: the driver's model
comes from the *driver's* adapter `MODELS` and the adversary's from the
*adversary's*. They are not interchangeable — `github-copilot/gpt-5.6-luna`,
`gpt-5.6-luna` and `claude-haiku-4-5-20251001` all name a class member and none
of them resolves under another harness.
"""

MODEL_ENV: Final[str] = "NOX_MANUAL_MODEL_{harness}"
"""Per-harness override for the driver-side literal; `{harness}` uppercased."""

TIMEOUT_ENV: Final[str] = "NOX_MANUAL_TIMEOUT_S"
"""Override for the per-cell wall clock."""

RUNS_ENV: Final[str] = "NOX_MANUAL_RUNS_DIR"
"""Override for where a run's transcript directory is created."""

RUNS_ROOT: Final[Path] = Path(__file__).resolve().parent.parent / ".manual-runs"
"""Where transcripts land by default: `nox/.manual-runs`, gitignored.

Derived from this file rather than from the cwd, so a direct
`python scripts/manual_smoke.py` and a `task nox:manual:matrix` write to the
same place. Repo-local rather than under `$TMPDIR` for one reason: the
evidence has to still be there when someone comes back to a red cell, and a
tmp sweep is exactly the thing that makes a failure unattributable.
"""

CELL_TIMEOUT_S: Final[int] = DEFAULT_TIMEOUT_S + 600
"""The per-cell bound: nox's own review budget plus the driver's own turns.

Derived from `config.DEFAULT_TIMEOUT_S` rather than written as a literal, so a
change to nox's review budget cannot leave this one silently below it.
"""

MODEL: Final[str] = "{model}"
"""The placeholder a `DRIVERS` template carries where its model literal goes."""

DRIVERS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        # `--allowedTools` is variadic and is terminated by the `--model` that
        # follows it: reordering these two swallows the model literal as a tool
        # name and the run takes the harness default.
        "claude": ("claude", "-p", "--allowedTools", "Bash", "--model", MODEL),
        # `--ephemeral` keeps the driver's own session out of the operator's
        # history; `--skip-git-repo-check` because the driver's cwd is a bare
        # scratch directory, not the fixture.
        "codex": (
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "--sandbox",
            "danger-full-access",
            "--model",
            MODEL,
        ),
        # `-p` must stay LAST: the prompt is appended as the final argv word and
        # is this flag's value.
        "copilot": ("copilot", "--no-color", "--log-level", "none", "--silent", "--allow-all", "--model", MODEL, "-p"),
        # The `ocx package exec` form is mandatory. The sibling `ocx exec`
        # resolves its pin from the *project's* `ocx.toml` and fails outside an
        # ocx project, which a scratch directory under $TMPDIR is.
        "opencode": (
            "ocx",
            "package",
            "exec",
            "ocx.sh/anomalyco/opencode:1.18.22",
            "--",
            "opencode",
            "run",
            "--auto",
            "--model",
            MODEL,
        ),
    }
)
"""Registry key → that harness's headless-prompt argv; the prompt is appended last.

Each entry is pinned off the real binary (§ Environment probe) and carries the
one permission grant the driver needs to run a shell command at all — the driver
side is deliberately the operator's own harness, unsandboxed and with its own
user settings loaded. nox's containment claim is about the *adversary* side, and
no flag here reaches it: `review()` rebuilds argv through `adapter.prepare` and
the environment through `minimal_env`.
"""

SKIP_REASONS: Final[frozenset[FailureReason]] = frozenset({FailureReason.ABSENT, FailureReason.UNAUTHENTICATED})
"""`FailureReason` values that are an environment condition, not a nox defect.

Exactly the plan's causes that a `Review` can express: `ABSENT` (the adversary
binary is not there) and `UNAUTHENTICATED` (D-ad — opencode's legs report `skip`
on a machine whose auth store is empty, never `fail`).

Everything else fails, deliberately. `UNSUPPORTED` is a capability or platform
absence, which on a POSIX box carrying all four shipped adapters is a nox
regression. `RATE_LIMITED` is a red cell on purpose: a provider's quota is
something the operator has to see and re-run, not something a green tally should
absorb. `INVALID_CONFIG` must never be here — it is what a self-pair that wrongly
passed `--exclude` returns, and hiding that would make the bug read as weather.

The plan's other two skip causes are not `FailureReason`-shaped at all: a missing
*driver* binary and an unpinned driver form are decided before the spawn, in
`run_cell`.
"""

DEFECT: Final[str] = "average_charge"
"""The identifier the planted defect lives in."""

DEFECT_MARKERS: Final[tuple[str, ...]] = (DEFECT, "len(items)", "zero", "empty")
"""Any one of which, inside a harness finding, reports the planted defect.

A set rather than the identifier alone, because a live cell proved the
identifier alone is the wrong assertion: copilot located the defect exactly
(`billing.py:6`, "`len(items)` is zero and this expression raises
`ZeroDivisionError`") and called the function "the averaging helper" — a true
finding, failed by a substring test for its name.

Each member names something only THIS defect produces: the function, the
divisor, the exception it raises, or the precondition whose guard the diff
dropped. The file under review is four lines long and carries nothing else, so
a finding about anything else in it — a missing docstring, a type annotation —
matches none of them. Matched case-insensitively, and only within a
harness-origin finding span, never against the adversary's own `summary`.
"""

PROMPT: Final[str] = (
    "Run this exact shell command, once, exactly as written:\n\n"
    "{command}\n\n"
    "Do not create, edit or delete any other file, and run no other command. Do not read, "
    "summarise or quote the command's output. When the command has finished, reply with just DONE."
)
"""What the driver is told. It never names the planted defect, and never asks for the output.

Keeping the output out of the reply is deliberate: it keeps the adversary's
untrusted findings out of the driver's context, and the report file — not the
driver's prose — is what `judge` reads.
"""

KILL_GRACE_S: Final[float] = 1.0
"""How long the driver's process group gets between SIGTERM and SIGKILL."""

TAIL_LINES: Final[int] = 40
"""How much of a failed cell's captured output is printed."""

_CONTINUATION: Final[str] = "    "
"""The column `render` pushes every continuation line of an untrusted span to."""

_STATUS_LINE: Final[re.Pattern[str]] = re.compile(
    r"^status: (?P<status>\S+)\s+verdict: (?P<verdict>\S+)\s+reason: (?P<reason>\S+)\s*$", re.MULTILINE
)
"""`render`'s first fact line. Continuation lines are indented, so a finding body cannot forge it."""

_MECHANISM = re.compile(r"^containment: mechanism=(?P<mechanism>\S+)", re.MULTILINE)
"""The containment stamp's first field."""

_HARNESS_FINDING = re.compile(r"^\[[^\]/\s]+/harness\]", re.MULTILINE)
"""A finding tag whose `Finding.origin` is the harness — never nox's own C-1026 finding."""

_MECHANISMS: Final[frozenset[str]] = frozenset(get_args(Mechanism))
"""What `render` may print for an ESTABLISHED mechanism.

Read off the type rather than compared against a hand-copy of `cli._UNESTABLISHED`:
if that word ever changed, an equality test against a copy would go false and
every run with no containment at all would silently pass.
"""


def _harness_finding_spans(block: str) -> list[str]:
    r"""Return each harness-origin finding as its tag line plus its indented body.

    `render` writes a finding as `[severity/origin] title` followed by body lines
    pushed to `cli._CONTINUATION` (four spaces), so a span ends at the first line
    that is neither indented nor empty. Scoping the defect check to these spans is
    what stops an untrusted `summary:` that merely mentions the identifier from
    passing a cell the adversary actually missed.

    **Split on `"\n"`, never `str.splitlines()`.** `cli._indented` escapes exactly
    one character, and `splitlines()` breaks on six more — `\v`, `\f`, `\r`,
    `\x85`, `U+2028` and `U+2029`. A harness `summary` carrying any of them
    followed by `[high/harness] average_charge` forged a finding span, and a
    review with NO findings at all judged `pass`: a green cell for an adversary
    that found nothing. `render`'s own anchors are `re.MULTILINE`, which is
    `"\n"`-only, so this is the one place the two ever disagreed.

    Args:
        block: The rendered review.

    Returns:
        One string per harness-origin finding, tag line included.
    """
    spans: list[str] = []
    current: list[str] | None = None
    for line in block.split("\n"):
        if _HARNESS_FINDING.match(line):
            current = [line]
            spans.append("")
        elif current is not None and line.startswith(_CONTINUATION):
            current.append(line)
        elif current is not None:
            spans[-1] = "\n".join(current)
            current = None
    if current is not None:
        spans[-1] = "\n".join(current)
    return spans


_GUARDED = '''"""Billing helpers."""


def average_charge(items):
    """Return the mean amount charged across `items`."""
    if not items:
        return 0.0
    return sum(item["amount"] for item in items) / len(items)
'''
"""The committed form: the guard is present, so the diff is the only defect."""

_DEFECTIVE = '''"""Billing helpers."""


def average_charge(items):
    """Return the mean amount charged across `items`."""
    return sum(item["amount"] for item in items) / len(items)
'''
"""The uncommitted form: the empty-period guard is gone."""


@dataclass(frozen=True, slots=True)
class Cell:
    """One (driver, adversary) result, and everything its transcript is written from.

    The last four fields exist because a live matrix cell that goes red has to be
    *attributable* after the fact: this sweep has failed twice with the cell's
    output already scrolled off the terminal, and "transient and unattributed" is
    what a harness that cannot tell you what broke reports.

    Attributes:
        driver: Registry key of the harness that ran nox.
        adversary: Registry key of the harness nox reviewed under.
        outcome: The tri-state this cell reports.
        reason: Why, for `fail` and `skip`. Empty on `pass`.
        output: The driver's captured stdout+stderr — its own, never the report's.
        argv: What was actually spawned, model substituted and prompt included.
            Empty on the two skips that refuse before the spawn.
        status: The driver's exit status, or `None` when it was never spawned.
        report: The prose nox wrote, or `None` when the driver produced no file.
        transcript: Where all of the above was written. `run_cell` sets it.
    """

    driver: str
    adversary: str
    outcome: Outcome
    reason: str = ""
    output: str = field(default="", repr=False)
    argv: tuple[str, ...] = field(default=(), repr=False)
    status: int | None = None
    report: str | None = field(default=None, repr=False)
    transcript: Path | None = None


def cells(driver: str | None = None, adversary: str | None = None) -> list[tuple[str, str]]:
    """Return the (driver, adversary) pairs to run, in a stable order.

    Args:
        driver: Restrict to this driver. `None` means every registry key.
        adversary: Restrict to this adversary. `None` means every registry key.

    Returns:
        The pairs, sorted — `ADAPTERS` squared when both arguments are `None`.

    Raises:
        KeyError: A named key is not in `ADAPTERS`. `main` renders it as a usage
            error rather than a traceback.
    """
    for key in (driver, adversary):
        if key is not None and key not in ADAPTERS:
            raise KeyError(key)
    drivers = [driver] if driver is not None else list(ADAPTERS)
    adversaries = [adversary] if adversary is not None else list(ADAPTERS)
    return sorted((one, other) for one in drivers for other in adversaries)


def driver_model(harness: str) -> str:
    """Resolve the driver-side model literal for `harness` at `MODEL_CLASS`.

    Args:
        harness: A registry key.

    Returns:
        `$NOX_MANUAL_MODEL_<HARNESS>` when set, else that adapter's own
        `MODELS[MODEL_CLASS]` literal.
    """
    override = os.environ.get(MODEL_ENV.format(harness=harness.upper()))
    return override if override else ModelSpecT.of(load(harness).MODELS[MODEL_CLASS]).model


def _git(repo: Path, *args: str) -> None:
    """Run one git command in `repo`, with the operator's system config out of reach.

    Args:
        repo: The repository to run in.
        *args: The git subcommand and its arguments.
    """
    subprocess.run(
        ["git", "-C", str(repo), *args],
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"},
        capture_output=True,
        text=True,
        check=True,
    )


def fixture(root: Path, adversary: str) -> Path:
    """Build the throwaway repository under review, and its `nox.toml`.

    One commit carrying a guarded `average_charge`, then the planted defect as
    an *uncommitted* working-tree edit that drops the guard — so `--scope
    code-diff` with no `--base` reviews exactly the defect through
    `git stash create`. A local `user.name`/`user.email` is written so that
    stash commit has an identity of its own.

    The repository also gets a `nox.toml` carrying
    `[harness.<adversary>] model = "fast-balanced"`: `model` is not in
    `TRUST_GATED_KEYS`, so a repo-local file may set it, and without it the
    adversary silently takes its *harness default* and reports
    `Review.model = None` — which is not what the plan asks a cell to prove.

    Args:
        root: The scratch directory the repository is created inside.
        adversary: The harness whose model class the `nox.toml` pins.

    Returns:
        The repository path.
    """
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "--local", "user.name", "nox manual smoke")
    _git(repo, "config", "--local", "user.email", "nox-manual-smoke@invalid")
    source = repo / "billing.py"
    source.write_text(_GUARDED, encoding="utf-8")
    # `nox.toml` is COMMITTED, not left untracked: an untracked file is a C-1026
    # omitted path, and a live cell watched the adversary spend its entire review
    # on the omission rather than on the defect the fixture exists to plant.
    (repo / "nox.toml").write_text(f'[harness.{adversary}]\nmodel = "{MODEL_CLASS}"\n', encoding="utf-8")
    _git(repo, "add", "billing.py", "nox.toml")
    # `--no-gpg-sign`: the operator's global config is still in reach here, and a
    # `commit.gpgsign = true` there would make the fixture unbuildable.
    _git(repo, "commit", "-q", "--no-gpg-sign", "-m", "billing: guard the empty period")
    source.write_text(_DEFECTIVE, encoding="utf-8")
    return repo


def judge(report: str | None, *, adversary: str, driver_status: int) -> tuple[Outcome, str]:
    """Decide one cell from the report file nox wrote.

    Args:
        report: The file's contents, or `None` when the driver never created it.
        adversary: The harness the run was supposed to reach.
        driver_status: The driver process's exit status, for the message on a
            missing report.

    Returns:
        The outcome and its one-line reason. Empty reason on `pass`.
    """
    if report is None:
        return "fail", f"the driver wrote no report file; its exit status was {driver_status}"
    # The anchor is `render`'s own `status:` line, never `UNTRUSTED_NOTICE`. The
    # notice is a sentence of prose; this is structural output the contract
    # defines and `render` emits on EVERY path, refusals included. It is just as
    # unforgeable — `render` pushes every continuation line to `_CONTINUATION`,
    # so a finding body cannot open one at column 0 — and it does not couple the
    # judge to the wording of a security notice that may be reworded (E68).
    line = _STATUS_LINE.search(report)
    if line is None:
        return "fail", "the report carries no nox review block"
    block = report[line.start() :]
    status, reason = line["status"], line["reason"]
    if reason in {item.value for item in SKIP_REASONS}:
        return "skip", reason
    if f"harness: {adversary}" not in block:
        return "fail", f"the review names another harness, not {adversary}"
    if status != "ok":
        return "fail", f"the review ended {status} (reason {reason})"
    # `api.review` sets `Review.harness` BEFORE the probe, so a refused run still
    # renders the right harness name; the unestablished stamp is what tells the
    # two apart.
    mechanism = _MECHANISM.search(block)
    if mechanism is None or mechanism["mechanism"] not in _MECHANISMS:
        return "fail", "containment was never established"
    spans = _harness_finding_spans(block)
    if not spans:
        return "fail", "the review carries no harness-origin finding"
    if not any(marker in span.lower() for span in spans for marker in DEFECT_MARKERS):
        return "fail", f"no harness finding reports the planted defect in {DEFECT}"
    return "pass", ""


def _cell_command(*, pyz: Path, driver: str, adversary: str, repo: Path, report: Path) -> str:
    """Build the one shell command the driver is told to run.

    `--exclude` is present only on a foreign pair: `api._resolve_harness` raises
    `ConfigError` (INVALID_CONFIG) when the exclusion equals the resolved
    harness, so a self-pair must omit it (S-1011).

    Args:
        pyz: The built zipapp.
        driver: The driving harness, which is what the review must exclude.
        adversary: The harness the review must reach.
        repo: The fixture repository.
        report: Where the review's prose is redirected.

    Returns:
        The command line.
    """
    words = ["python3", str(pyz), "review", "--scope", "code-diff", "--harness", adversary]
    if driver != adversary:
        words += ["--exclude", driver]
    words += ["--repo", str(repo)]
    return f"{shlex.join(words)} > {shlex.quote(str(report))} 2>&1"


def _signal_group(proc: subprocess.Popen[str], number: int) -> None:
    """Signal the driver's whole process group, tolerating a group that is already gone.

    With `start_new_session=True` the group id equals the child's pid, so this
    never calls `getpgid` — that read-then-signal pair is the TOCTOU nox itself
    names, and it can address a group the kernel has already recycled.

    Args:
        proc: The driver process.
        number: The signal to deliver.
    """
    try:
        os.killpg(proc.pid, number)
    except (ProcessLookupError, PermissionError):
        pass


def _terminate(proc: subprocess.Popen[str]) -> str:
    """Kill a driver past its bound and reap it, keeping whatever it had written.

    Args:
        proc: The driver process, whose `communicate` has already timed out.

    Returns:
        The captured output.
    """
    _signal_group(proc, signal.SIGTERM)
    try:
        return proc.communicate(timeout=KILL_GRACE_S)[0]
    except subprocess.TimeoutExpired:
        _signal_group(proc, signal.SIGKILL)
        try:
            return proc.communicate(timeout=KILL_GRACE_S)[0]
        except subprocess.TimeoutExpired:
            # A descendant that called `setsid()` outlives every rung of the ladder
            # and can still hold the merged pipe (D-ac). nox's own bound applies
            # here too: what returning proves is that the SMOKE is done.
            return ""


def runs_dir() -> Path:
    """Create and return this run's own transcript directory.

    `mkdtemp` under a timestamped prefix, so a re-run can never overwrite the
    evidence of the run it is re-running — which is the whole point, since
    re-running a red cell is the documented next step.

    Returns:
        The directory, already created.
    """
    root = Path(os.environ.get(RUNS_ENV) or RUNS_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{time.strftime('%Y%m%dT%H%M%S')}-", dir=root))


def _transcript(cell: Cell) -> str:
    """Render one cell as the file that outlives the run.

    Everything an operator would have needed on the terminal and no longer has:
    which pair, what was actually spawned, how it ended, the report nox wrote and
    the driver's own output **in full** — the console only ever shows
    `TAIL_LINES` of one of them.

    Args:
        cell: The finished cell.

    Returns:
        The transcript's text.
    """
    return "\n".join(
        [
            f"driver: {cell.driver}",
            f"adversary: {cell.adversary}",
            f"outcome: {cell.outcome}",
            f"reason: {cell.reason or 'none'}",
            f"exit status: {'none' if cell.status is None else cell.status}",
            f"argv: {shlex.join(cell.argv) if cell.argv else 'none - the driver was never spawned'}",
            "",
            "--- the report nox wrote -------------------------------------------------",
            cell.report if cell.report is not None else "(the driver produced no report file)",
            "",
            "--- the driver's own captured output -------------------------------------",
            cell.output or "(nothing captured)",
            "",
        ]
    )


def run_cell(driver: str, adversary: str, *, pyz: Path, root: Path, timeout_s: int, transcript: Path) -> Cell:
    """Run one cell and write its transcript, whatever the cell decided.

    The transcript is written for a `skip`, a `pass` and a raise too: a skip is the
    outcome with the least on the terminal and the one most likely to be wrong
    about the environment, a pass whose neighbour went red is the comparison an
    operator wants, and an exception is the one case that used to leave nothing at
    all. `transcript` is deliberately outside `root`, which `_drive` deletes.

    Args:
        driver: Registry key of the driving harness.
        adversary: Registry key of the harness nox must reach.
        pyz: The built `nox.pyz` the driver is told to run.
        root: A per-cell scratch directory, deleted on the way out.
        timeout_s: Wall-clock bound for the whole cell.
        transcript: Where this cell's evidence is written.

    Returns:
        The cell, naming its transcript.
    """
    try:
        cell = _drive(driver, adversary, pyz=pyz, root=root, timeout_s=timeout_s)
    except Exception as error:  # a red cell with a traceback beats losing the sweep
        # `fixture` runs six `check=True` git commands and `Popen` can fail on
        # its own; an escape here would abort a half-hour live sweep with no
        # tally, no failed-cell list, and no transcript for any later cell. The
        # cell is red and its transcript carries the traceback, which is the
        # same bargain the rest of this file makes.
        cell = Cell(
            driver, adversary, "fail", " ".join(f"{type(error).__name__}: {error}".split()), traceback.format_exc()
        )
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text(_transcript(cell), encoding="utf-8")
    return replace(cell, transcript=transcript)


def _drive(driver: str, adversary: str, *, pyz: Path, root: Path, timeout_s: int) -> Cell:
    """Spawn one driver, have it run one `nox review`, and judge what came back.

    Skips before spending a token when `driver` has no `DRIVERS` entry or its
    binary is not on `PATH`. The driver runs in a scratch directory that is
    **not** the fixture, so its own session droppings never land in the tree
    under review; the repository is named to nox with `--repo`.

    Args:
        driver: Registry key of the driving harness.
        adversary: Registry key of the harness nox must reach.
        pyz: The built `nox.pyz` the driver is told to run.
        root: A per-cell scratch directory holding the fixture, the driver's
            working directory and the report file.
        timeout_s: Wall-clock bound for the whole cell. On expiry the driver's
            whole process group is signalled, then reaped.

    Returns:
        The cell, with no transcript path — `run_cell` writes the file.
    """
    template = DRIVERS.get(driver)
    if template is None:
        return Cell(driver, adversary, "skip", f"no driver form is pinned for {driver}")
    binary = template[0]
    if shutil.which(binary) is None:
        return Cell(driver, adversary, "skip", f"the {driver} driver binary {binary} is not on PATH")
    root.mkdir(parents=True, exist_ok=True)
    try:
        repo = fixture(root, adversary)
        report_path = root / "nox.out"
        scratch = root / "driver"
        scratch.mkdir()
        model = driver_model(driver)
        argv = [word.replace(MODEL, model) for word in template]
        argv.append(
            PROMPT.format(
                command=_cell_command(pyz=pyz, driver=driver, adversary=adversary, repo=repo, report=report_path)
            )
        )
        proc = subprocess.Popen(
            argv,
            cwd=scratch,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
            start_new_session=True,
        )
        timed_out = False
        try:
            output = proc.communicate(timeout=timeout_s)[0]
        except subprocess.TimeoutExpired:
            output, timed_out = _terminate(proc), True
        # Read back even on the timeout path: a partially written report is the
        # best evidence there is about where a hung cell got to.
        report = report_path.read_text(encoding="utf-8", errors="replace") if report_path.exists() else None
        outcome, reason = (
            ("fail", f"the driver timed out after {timeout_s}s")
            if timed_out
            else judge(report, adversary=adversary, driver_status=proc.returncode)
        )
        return Cell(driver, adversary, outcome, reason, output, tuple(argv), proc.returncode, report)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def exit_code(results: Sequence[Cell], *, single: bool) -> int:
    """Map results onto a process status.

    Args:
        results: Every cell that ran.
        single: True for `task nox:manual:cell`, which alone may report a skip
            through its exit status. The matrix must not: narrowing it to one
            pair would otherwise flip its contract.

    Returns:
        `1` if any cell failed; else `EXIT_SKIP` when `single` and that cell
        skipped; else `0`.
    """
    if any(cell.outcome == "fail" for cell in results):
        return 1
    if single and any(cell.outcome == "skip" for cell in results):
        return EXIT_SKIP
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the matrix, or one cell, and print a line per cell plus a tally.

    Prints a cost warning naming the cell count **before the first spawn**: a
    full sweep is real tokens on every vendor in the registry, and the run's own
    transcript directory beside it, so the evidence is findable even when every
    cell passes.

    Args:
        argv: Arguments after the program name. `None` reads `sys.argv[1:]`.
            `--cell <driver> <adversary>` selects the single-cell contract; with
            no `--cell`, both positionals are optional filters over the matrix.

    Returns:
        The process status from `exit_code`.
    """
    parser = argparse.ArgumentParser(
        prog="manual_smoke.py", description="The live NxN cross-harness smoke. Spends real tokens."
    )
    parser.add_argument("--cell", action="store_true", help="run exactly one pair, and report a skip as 77")
    parser.add_argument("keys", nargs="*", metavar="HARNESS", help="<driver> [<adversary>]; filters without --cell")
    arguments = parser.parse_args(argv)
    if arguments.cell and len(arguments.keys) != 2:
        parser.error("--cell takes exactly two harness keys: <driver> <adversary>")
    if len(arguments.keys) > 2:
        parser.error("at most two harness keys: <driver> [<adversary>]")
    driver, adversary = [*arguments.keys, None, None][:2]
    try:
        pairs = cells(driver, adversary)
    except KeyError:
        parser.error(f"unknown harness; registered: {', '.join(sorted(ADAPTERS))}")

    print(f"About to run {len(pairs)} live cell(s): real tokens on every vendor these pairs name.", flush=True)
    timeout_override = os.environ.get(TIMEOUT_ENV)
    try:
        timeout_s = int(timeout_override) if timeout_override else CELL_TIMEOUT_S
    except ValueError:
        parser.error(f"{TIMEOUT_ENV} must be a whole number of seconds, not {timeout_override!r}")
    runs = runs_dir()
    print(f"Transcripts: {runs}", flush=True)
    results: list[Cell] = []
    with tempfile.TemporaryDirectory(prefix="nox-manual-") as run_root:
        pyz = Path(run_root) / "nox.pyz"
        here = Path(__file__).resolve().parent
        subprocess.run(
            [sys.executable, str(here / "build_pyz.py"), str(here.parent / "src" / "nox"), str(pyz)],
            check=True,
            capture_output=True,
        )
        # Serially, never in parallel (C-1022).
        for one, other in pairs:
            cell = run_cell(
                one,
                other,
                pyz=pyz,
                # `__` and not `-`: a future hyphenated registry key would make
                # `a-b` + `c` and `a` + `b-c` the same path, and the losing
                # cell's evidence would be silently overwritten.
                root=Path(run_root) / f"{one}__{other}",
                timeout_s=timeout_s,
                transcript=runs / f"{one}__{other}.txt",
            )
            results.append(cell)
            suffix = "" if cell.outcome == "pass" else f" ({cell.reason})"
            print(f"{cell.driver} -> {cell.adversary} : {cell.outcome}{suffix}", flush=True)
            # The report is the judged evidence; the driver was told to reply with
            # just DONE, so its own output only helps when there is no report.
            evidence = cell.report or cell.output
            if cell.outcome == "fail" and evidence:
                print("\n".join(evidence.splitlines()[-TAIL_LINES:]), flush=True)

    tally = Counter(cell.outcome for cell in results)
    print()
    print(f"{tally['pass']} pass / {tally['fail']} fail / {tally['skip']} skip")
    # After the tally, not only beside the cell: on a sixteen-cell sweep the line
    # that went red scrolled off long ago, and this is what is still on screen.
    failed = [cell for cell in results if cell.outcome == "fail"]
    if failed:
        print()
        print("failed cells, and the transcript that says why:")
        for cell in failed:
            print(f"  {cell.driver} -> {cell.adversary} : {cell.transcript}")
    return exit_code(results, single=arguments.cell)


if __name__ == "__main__":
    raise SystemExit(main())
