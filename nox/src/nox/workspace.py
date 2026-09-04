"""The ephemeral worktree: the one place isolation is decided (C-1003 to C-1006).

Every review runs against a *synthetic* commit pair built out of the repository's
git objects, never against the user's checkout. Neutralization (C-1005, C-1043)
happens at the object level — nothing is ever deleted from disk — so there is no
deletion primitive and no symlink semantics to get wrong, and no adapter has an
opportunity to forget it: the workspace is entered before any adapter code runs.

`ReviewTarget` lives here rather than in `api.py` (E9a) because it is the
workspace's input; `api.py` re-exports it.

**Every `env` parameter below is already a `config.minimal_env` product.**
`workspace()` builds one at entry when the caller passes none, and threads the
result down; C-1031 requires the override set on *every* git process, nox's own
included, so a call site that passed a raw environment would be a silent hole
rather than a visible bug. The C-1031 literals live in `config.py` and nowhere
else: the C-1014 probe runs before any worktree exists and must carry the same
overrides, or the C-1025 environment digest splits between probe and review.
"""

from __future__ import annotations

import fnmatch
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from collections.abc import Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal

from nox.config import DEFAULT_MAX_PROMPT_BYTES, ConfigError, minimal_env
from nox.outcome import NoxError
from nox.prompt import Scope


class IsolationError(NoxError):
    """The ephemeral worktree could not be built, verified or torn down.

    `nox.api.review()` maps this onto `FailureReason.ISOLATION_FAILED` with no
    harness ever spawned (C-1006, C-1029). Raised for a stale git (C-1041), an
    unresolvable commit-ish, a neutralized entry that reached the checkout, and
    any failing git call in the lifecycle.
    """


GIT_FLOOR: Final[tuple[int, int, int]] = (2, 32, 0)
"""The minimum git version nox will run against (C-1041, D-p).

Below 2.31 `GIT_CONFIG_COUNT` is ignored *silently*, which would turn the whole
C-1031 override set into a no-op with no error — a stale git must refuse, never
degrade.
"""

GITLINK_MODE: Final[str] = "160000"
"""Submodule entry mode — dropped by mode, never by name (C-1005)."""

SYMLINK_MODE: Final[str] = "120000"
"""Symlink entry mode — dropped by mode, never by name (C-1043)."""

NEUTRALIZE_DIRS: Final[frozenset[str]] = frozenset(
    {".claude", ".opencode", ".codex", ".cursor"},
)
"""C-1005 directory names, matched against EVERY path component.

The basename is included in the test (SD § 4.1): a set member committed as a
symlink is a blob whose whole path is one component, so excluding the basename
from the directory test let `.codex` → an attacker-controlled directory reach
the checkout still resolving to hostile content.
"""

NEUTRALIZE_FILES: Final[frozenset[str]] = frozenset(
    {
        ".mcp.json",
        "opencode.json",
        "opencode.jsonc",
        "CLAUDE.md",
        "AGENTS.md",
        ".env",
        ".envrc",
        "mise.toml",
        ".mise.toml",
        ".gitattributes",
        ".gitmodules",
        # E18. Each entry is pinned to an observation of a shipped binary, never
        # to a reading of the ADR's intent: `copilot-instructions.md`, `GEMINI.md`
        # were seen in Copilot 1.0.82's own system prompt in a live canary run;
        # `CLAUDE.local.md` and `AGENTS.override.md` are Claude Code's and Codex's
        # documented project-instruction names.
        "copilot-instructions.md",
        "GEMINI.md",
        "CLAUDE.local.md",
        "AGENTS.override.md",
    },
)
"""C-1005 file basenames, matched at any depth.

`.gitattributes` and `.gitmodules` are git's own execution surfaces: the first
runs a configured smudge filter during `worktree add`, before neutralization is
observable; the second is how a shell-capable reviewer is induced to fetch a
nested repository carrying config this walk never saw.
"""

NEUTRALIZE_GLOBS: Final[tuple[str, ...]] = (".env.*", "*.instructions.md", "*.agent.md")
"""C-1005 basename globs, matched case-insensitively — see `matches`.

E18 added the last two. `*.instructions.md` is Copilot's `.github/instructions/`
shape, observed loading into the system prompt; `*.agent.md` is
`.github/agents/`, which needs `--agent` or an interactive pick to load and is
neutralized anyway, because `--add-dir`'s own help calls that directory trusted
configuration.
"""

NEUTRALIZE_PREFIXES: Final[tuple[str, ...]] = (
    ".github/skills/",
    ".agents/skills/",
    ".github/hooks/",
    ".github/copilot/",
    ".github/mcp.json",
)
"""C-1005 path prefixes, anchored at the repository root and matched case-insensitively (E18).

The only matcher here that is not by component or by basename, and it is a
prefix rather than either because the basename that would cover these entries
over-drops catastrophically: a bare `SKILL.md` would neutralize every skill in
nox's own home repository, and `.agents/` as a directory entry would drop the
plan artifact C-1027 exists to review.

**Root-anchoring is sound because of C-1003.** cwd is the ephemeral worktree
root, so a harness's cwd-relative and git-root-relative discovery collapse to
the same anchor. The surfaces that *are* found at any depth — `AGENTS.md`,
`CLAUDE.md`, `.claude/`, `copilot-instructions.md` — stay on the component and
basename matchers above, which already match anywhere.

The first two are the entries the flag stack does not close. Copilot injects
each project skill's `description:` **verbatim into its system prompt**, and a
live canary proved that survives `--no-custom-instructions`: with the flag set,
the planted description was in the system prompt and the model *called the
skill*. So for this surface C-1005 is the boundary and the flag is not.

`.github/hooks/` and `.github/copilot/` are command execution plus
`additionalContext` injection; `.github/mcp.json` is a server declaration read
out of the 1.0.82 bundle's own literals. All three are folder-trust gated and
default-deny, and none fired in a probe. They are neutralized anyway because
the gate that stops them is **the harness's configuration, not nox's**: it is
lifted by `COPILOT_ALLOW_ALL=true`, by a managed policy, and by whatever the
user's own `~/.copilot/config.json` already trusts. nox drops that variable by
construction (`config.ALLOWLIST` carries no `COPILOT_*`), which is exactly why
the entries do not rest on it — C-1005 is about repo-resident content, and a
defence that held only while a consumer's own configuration cooperated would
not be one.

**`.github/` wholesale is deliberately NOT here**: it would drop
`.github/workflows/**`, which is exactly the supply-chain surface an
adversarial reviewer must see.

`.github/mcp.json` is the one entry that is a file rather than a directory, so
it is a prefix over a filename and also drops `.github/mcp.jsonc` and
`.github/mcp.json.example`. That over-drop is deliberate and in the fail-safe
direction: a neutralized entry is listed as evidence, never silently gone.
"""

WORKTREE_PREFIX: Final[str] = "nox-ws-"
"""Prefix of the ephemeral worktree directory (C-1006).

The call's token follows it, so the directory name is
`nox-ws-<token>-<mkdtemp entropy>` and `sweep` can recover the token from a
`git worktree list` path. Without that join `sweep` has no way to tell a live
concurrent call's refs from a leaked one's.
"""

REF_NAMESPACE: Final[str] = "refs/nox"
"""Where synthetic commits are pinned (C-1004). Swept at startup (C-1006).

A common-dir ref namespace, so a linked worktree and its primary checkout reach
the same refs and one process's sweep sees the other's pins (C-1003).
"""

SWEEP_GRACE_S: Final[int] = 60
"""How old a token's refs must be before `sweep` may reap them (C-1006).

A call pins its refs *before* `worktree add` (C-1004, to close the gc window),
so between those two steps its token has refs and no registered worktree —
which is otherwise exactly `sweep`'s delete predicate, and a concurrent call's
sweep would collect the synthetic commits out from under it. `worktree add` is
budgeted at ~1.2 s (SD § 8.1); 60 s is generous against that.

**The grace period bounds the concurrency window, NOT a SIGKILL leak.** A killed
nox leaves the worktree DIRECTORY on disk, so `git worktree prune` keeps the
registration, the token stays "live", and `sweep` skips its refs however old
they are. What C-1006 actually recovers on the next run is the *pruned* case —
a worktree directory a user or a `TMPDIR` reaper removed — and the ordinary
in-process teardown. See `sweep`.

ponytail: the leak needs liveness, not a longer grace period. The upgrade path
is an `fcntl.flock` held on the scratch directory for the life of the call: a
lock a dead process cannot hold makes "live" an observation rather than an
inference from a directory that outlived its owner. Not implemented here — it
is a lifecycle change, not a workspace one.
"""

SYMLINK_TARGET_BUDGET: Final[int] = 256
"""Bytes of a symlink's target carried into `filtered` (C-1043).

A mode-`120000` blob is only `PATH_MAX`-limited at checkout; in the object store
it is arbitrary attacker-chosen bytes of arbitrary length. `filtered` is stated
verbatim in the prompt (C-1028) and rendered by the consumer, so an unbounded
target is a prompt-injection channel, a terminal-escape channel and — through
argv size and UTF-8 decoding — a one-file denial of service.

It bounds the READ as well as the rendering: `_link_targets` runs a
`cat-file --batch-check` size pass first and asks `--batch` only for the shas it
cleared, because `capture_output` holds the whole answer in memory. One
committed `120000` entry with a 200 MB blob moved peak RSS 419 → 620 MB before
that check existed, and a 4 GB one OOMs every review of the branch — the argv
and decode halves alone did not close it.
"""

ENUMERATION_BUDGET: Final[int] = 1000
"""Entries carried into each of the four evidence lists (C-1028).

Every list here is built from tree entries a branch chose, and every one of
them is stated verbatim in the prompt. A tree holding 120000 `120000` entries
renders megabytes of path lines, and C-1028 forbids the prompt truncating
itself — so the front-truncation a context limit performs would cut the
anti-injection framing out of the model's window while leaving the branch's
own lines in it. The cap belongs at the point the evidence is produced, not at
the point it is rendered.

Capping is safe here in a way truncating the prompt is not: the entries are
evidence, and each list ships its untruncated `*_total` beside it, so a
consumer states "1000 of 120000" rather than a short list that looks whole. A
reviewer that must be told about a thousand withheld paths has already been
told the change is not reviewable. This count bounds the number of entries and
nothing else: git enforces no path limit of its own (a 59 960-character tree
entry is accepted — WP15's H6 reproduction, and see `sanitize_path`), so the
product is not an arithmetic ceiling. Ordinary entries run orders of magnitude
below any of it; a byte cap over the assembled evidence is E53's.
"""

_VERSION_RE: Final[re.Pattern[str]] = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
"""First dotted pair-or-triple in `git --version`. Unparseable ⇒ refuse (C-1041)."""


@dataclass(frozen=True, slots=True)
class ReviewTarget:
    """What is under review, before any git object is resolved (E9a).

    Resolution is specified, not left to the caller — see `resolve_pair`.

    Attributes:
        kind: `"ref"` reviews a named commit-ish; `"working-tree"` reviews
            uncommitted work through `git stash create`; `"plan-artifact"`
            reviews one file as a one-file addition against the empty tree.
        ref: The commit-ish, for `kind="ref"`.
        base: The base commit-ish. `kind="ref"` resolves it through
            `merge-base(base, ref)`, falling back to `<ref>^`.
        path: The artifact, for `kind="plan-artifact"`. Must exist and resolve
            inside the repository, else `nox.config.ConfigError` before any
            repository state is touched (C-1027).
    """

    kind: Literal["working-tree", "ref", "plan-artifact"]
    ref: str | None = None
    base: str | None = None
    path: Path | None = None


@dataclass(frozen=True, slots=True)
class Workspace:
    """One live ephemeral worktree and the evidence about what it contains.

    Yielded by the `workspace` context manager; invalid outside it, because
    teardown removes `path` and deletes the pinning refs.

    Attributes:
        path: The ephemeral worktree — every `Invocation.cwd` is this (C-1003).
        token: This call's unique token. Public because the concurrency and gc
            tests address `refs/nox/<token>/*` by name, and because an adapter
            that needs a per-run unguessable name derives it from here — codex's
            sandbox probe does, for its marker and nonce filenames. **Not** a
            `--base` argument any more: SD § 6.2's `codex exec review --base
            refs/nox/<token>/base` cannot be built (E21) and the shipped leg is
            bare `codex exec`, so the refs are pinned for C-1004's gc window and
            handed to no harness.
        base: The synthetic base commit (C-1004, C-1005).
        target: The synthetic target commit — what is checked out.
        scope: Which of C-1042's two words describes this run —
            `"plan-artifact"` for a `plan-artifact` target, `"code-diff"` for
            every other kind. Derived here because `prompt.render` takes it and
            E9a's `prepare(ws, info, cfg, instructions)` gives its caller no
            other route back to `ReviewTarget.kind`.
        scratch: `<path>/../.nox-<token>-<random>/`, minted by `mkdtemp`
            (C-1009). A SIBLING of the worktree, never a child: the harness runs
            with `path` as its cwd, so nox's own prompt and diff would otherwise
            be part of the surface under review — and a reviewer doing its job
            reports the prompt as repository content addressing it, on every
            single run. C-1005 neutralizes the branch's instruction surfaces;
            nox may not then add one of its own.

            **Out of the review, not out of reach.** Only `claude` confines its
            file tools to the working directory; `copilot` and `opencode` take
            unconstrained paths and could still read this. That costs nothing
            today — every harness is already holding that text, whether through
            `harness.argv_prompt` (`copilot`, `opencode`) or on stdin from this
            very file (`claude`, `codex`; E29) — and what the move buys is that
            the file is no longer *enumerated as repository content*.
            The name still leads with `.nox-` and is never `.nox`, because it is
            also what a committed `.nox/` directory or `.nox` symlink would have
            collided with; `mkdtemp` adds the suffix that makes it this call's
            alone even where two calls share a token and a parent.

            **A SIGKILLed nox leaks this directory permanently, and nothing
            reclaims it.** Its removal is `workspace`'s `finally` block and
            nothing else: `sweep` reaps refs and prunes worktree
            *registrations*, and the scratch is neither — no ref names it, `git
            worktree prune` has never heard of it, and the worktree directory
            beside it is not reclaimed either (see `sweep`). So a killed run
            leaves everything written here — `review.diff`, `harness`'s
            `prompt.md`, whatever an adapter added beside them, which is the
            whole change under review and the whole prompt — under the temp root
            until the operator or a `TMPDIR` reaper removes it. Stated rather
            than fixed: `mkdtemp`'s `0700` directory and `write_nofollow`'s
            `0600` files are what bound the exposure, and a reaper is a
            lifecycle decision carrying the same liveness problem
            `SWEEP_GRACE_S` describes, not a workspace one.
        diff_path: `<scratch>/review.diff`, written with `O_NOFOLLOW`.
        diff: The same bytes, decoded — **the change itself**, and what
            `harness.review_prompt` renders into the prompt (C-1028). Carried
            here rather than re-read from `diff_path` at `prepare` time, so the
            read happens before any harness has run in this workspace at all.
            `write_nofollow`'s own contract states the scratch directory is
            unprotected once one has, and the only harness spawn into this
            workspace is `adapter.sandbox_probe`, which `authorize` runs AFTER
            `prepare` — so re-reading at `prepare` time would in fact still be
            safe today. It is carried anyway because the safety would then rest
            on that call order rather than on the bytes being read once, at the
            point they are produced. The window the order does open is the one
            between `review_prompt`'s write and `runner._open_prompt`'s read,
            which `spawn` guards directly.

            Decoded `errors="replace"`, which is the one place a nox evidence
            string is not byte-exact. The prompt is delivered as an argv word
            and written as UTF-8, so an undecodable byte has no verbatim route
            to the model at all; git already renders binary content as
            `Binary files ... differ`, so what `replace` can touch is a tracked
            text file that is not UTF-8, and a visible replacement character is
            a better answer there than a `UnicodeDecodeError` out of the review.
            Uncapped, unlike the four evidence lists: this is not an enumeration
            of branch-chosen entries but the change under review. A diff too
            large to DELIVER is refused rather than silently shortened, and
            where that bites depends on the harness's prompt channel:
            `harness.PROMPT_ARGV_LIMIT` binds `copilot` and `opencode`, whose
            prompt is an argv word, and never `claude` or `codex`, which read it
            from stdin (E29).
        env: The `config.minimal_env` environment every git process in this call
            ran under. Carried rather than recomputed so a consumer that shells
            out — the harness's own `git`, an adapter's probe — has one source
            for it, and so C-1025 can digest exactly what the children saw.
            Deriving one from `os.environ` instead would re-inherit everything
            C-1008 and C-1031 exist to drop. A read-only view: it is evidence,
            not a scratch dict.
        neutralized: Entries dropped by name (C-1005) across BOTH ends, sorted
            and de-duplicated; the target end's half is re-verified absent from
            the checkout. Carries no evidence loss about the change itself, so
            it does not constrain the verdict.
        filtered: EVERY entry dropped by mode (C-1043, C-1005) across both ends
            — every `120000` and `160000` entry, including one whose path is
            also a C-1005 member — as `<path> -> <sanitized target>`. C-1043(2)
            asks for the target of each, and a set member committed as a symlink
            (`.codex -> $HOME/.codex`, SD § 9.4) is precisely the entry whose
            target the reviewer must be told. Such an entry appears in
            `neutralized` too; the lists are evidence, not a partition.
        filtered_changed: The subset of `filtered` that differs between the two
            ends AND whose path is not a C-1005 member. C-1043(4): a change
            consisting only of symlink entries yields an empty diff, so a
            non-empty value forces `needs-attention` and a `high`,
            `origin="nox"` finding that NAMES these entries — exactly as a
            non-empty `omitted` does under C-1026. The `matches` exclusion is
            what keeps a branch editing its own `.codex` symlink approvable: a
            C-1005 member carries no review value by definition, so its change
            is not evidence the reviewer lost. Membership is decided on
            `(path, blob sha)`, never on the rendering — two targets sharing a
            `SYMLINK_TARGET_BUDGET`-byte prefix render identically, and
            differencing the renderings let such a pair cancel out.
        omitted: Untracked paths not carried into the review (C-1026). Non-empty
            only for `working-tree`; a commit has no untracked files.
        omitted_ignored: How many untracked paths git's ignore rules hid from
            `omitted`. The checked-out `.gitignore` governs `--exclude-standard`,
            so a `*` in it would otherwise empty `omitted` and make the
            completeness stamp read clean. A count, not a list: build output is
            the overwhelming majority and listing it would bury the signal.

    Every path in `neutralized`, `filtered`, `filtered_changed` and `omitted` is
    a `sanitize_path` rendering, because C-1028 states them verbatim in the
    prompt. They are evidence for a human and a model, never values to resolve:
    the raw paths are what `verify`, `update-index` and every internal
    comparison use.

    **All four are capped at `ENUMERATION_BUDGET` entries and each ships its
    untruncated `*_total` beside it.** The lists are branch-controlled and
    unbounded at the source, so a consumer must state "N of M" rather than
    `len(...)`; a `*_total` above its list's length means the rest was never
    enumerated to the prompt, never that it was not there. `verify` still runs
    against the whole drop list, which is why the cap costs no containment.
    """

    path: Path
    token: str
    base: str
    target: str
    scope: Scope
    scratch: Path
    diff_path: Path
    diff: str
    env: Mapping[str, str]
    neutralized: tuple[str, ...]
    neutralized_total: int
    filtered: tuple[str, ...]
    filtered_total: int
    filtered_changed: tuple[str, ...]
    filtered_changed_total: int
    omitted: tuple[str, ...]
    omitted_total: int
    omitted_ignored: int


_DROP_MODES: Final[frozenset[str]] = frozenset({SYMLINK_MODE, GITLINK_MODE})
"""The two entry modes dropped whatever the path says (C-1005, C-1043)."""

_NOFOLLOW_FLAGS: Final[int] = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW

_DEADLINE: Final[ContextVar[float | None]] = ContextVar("nox_git_deadline", default=None)
"""The absolute `time.monotonic()` every `_git` call in this module is held to (E54).

A `ContextVar` rather than a parameter because `_git` is reached through nine
public helpers — `sweep`, `resolve_pair`, `neutralize`, `pin_refs`, `verify`,
`untracked` and the rest — and threading a deadline down all of them would put
the same argument on every signature in the module to say one thing about the
phase as a whole. `workspace()` is the only writer; it sets the var on entry
and resets it on exit, so nothing outside one live workspace ever sees a value.

An ABSOLUTE deadline, never a per-call budget: the git phase as a whole is what
the wall clock bounds, and a budget handed to each call in turn would let a
repository with enough paths spend it many times over.
"""
"""`write_nofollow`'s open flags — `O_EXCL` refuses a file, `O_NOFOLLOW` a symlink (C-1009)."""

_UNSAFE_CHARS: Final[frozenset[str]] = frozenset(
    "\u2028\u2029"  # line separator, paragraph separator
    "\u202a\u202b\u202c\u202d\u202e"  # bidi embeddings and overrides
    "\u2066\u2067\u2068\u2069"  # bidi isolates
)
"""What `_escape` refuses beyond the control range: the line separators and the bidi controls."""

_FOLDED_DIRS: Final[frozenset[str]] = frozenset(name.casefold() for name in NEUTRALIZE_DIRS)
"""`NEUTRALIZE_DIRS`, casefolded once — see `matches` for why the test is case-insensitive."""

_FOLDED_FILES: Final[frozenset[str]] = frozenset(name.casefold() for name in NEUTRALIZE_FILES)
"""`NEUTRALIZE_FILES`, casefolded once — see `matches`."""

_FOLDED_PREFIXES: Final[tuple[str, ...]] = tuple(prefix.casefold() for prefix in NEUTRALIZE_PREFIXES)
"""`NEUTRALIZE_PREFIXES`, casefolded once — a tuple, because `str.startswith` takes one."""


@contextmanager
def _isolating(what: str) -> Generator[None]:
    """Map any `OSError` raised inside onto `IsolationError` (C-1029).

    `review()` maps `NoxError` and nothing else, so an `OSError` escaping this
    module lands in its plugin-boundary backstop instead and is resolved
    `indeterminate`/`MALFORMED_OUTPUT` — nox saying it does not know what
    happened about the one failure it does know. **What this buys is
    classification, not totality**: C-1029 is not breached without it, but
    `FailureReason.ISOLATION_FAILED` is the answer, and it needs no repository
    to reach: an absent or non-executable `git`, a `tempfile.tempdir` that does
    not exist, an unwritable checkout parent, a cwd that was removed underneath
    a `Path.resolve()`.

    Args:
        what: What was being attempted, for the refusal message.

    Yields:
        Nothing — the guarded statements run inside the block.

    Raises:
        IsolationError: The block raised an `OSError`.
    """
    try:
        yield
    except OSError as exc:
        raise IsolationError(f"{what}: {exc}") from exc


def _git(
    repo: Path,
    *args: str,
    env: Mapping[str, str],
    stdin: bytes | None = None,
    check: bool = True,
    stdout: Path | None = None,
) -> bytes:
    """Run one git command in `repo` and return its stdout.

    The single choke point for every git call in this module: an argv list with
    `shell=False`, the caller's already-`minimal_env`-built environment, and a
    non-zero exit mapped onto `IsolationError` naming the subcommand — a
    `CalledProcessError` never escapes. Bytes rather than text, because a tracked
    path and a diff body both carry whatever the repository holds, and decoding
    one that is not valid UTF-8 would be an attacker-chosen denial of service.

    `git` is spelled bare so the child is resolved through `env`'s own `PATH`,
    which is what lets the C-1041 tests put a version shim in front of it.

    Args:
        repo: What `-C` is given. Any directory git can run in.
        *args: The git arguments, without the leading `git`.
        env: The environment for the child.
        stdin: Bytes to feed the child, for the `--stdin` forms.
        check: Whether a non-zero exit refuses. `False` for the teardown steps
            alone: each of them must run whatever the one before it did, and a
            teardown failure must never replace an exception raised by the body.
            It does NOT cover a spawn failure — those raise whatever `check`
            says, and the teardown suppresses `IsolationError` around each step.
            **It also excludes the call from `_DEADLINE`** (E54), and for the
            same reason: a cleanup that gives up because the run's wall clock
            elapsed strands an ephemeral worktree and two pinned refs forever.
        stdout: A file to write the child's stdout into, opened
            `O_CREAT|O_EXCL|O_NOFOLLOW` exactly as `write_nofollow` does, or
            `None` to capture it in memory. The redirect is what lets a diff be
            MEASURED before it is allocated (E53): git writes it once, the
            caller `stat`s the result, and nothing is read into the process
            until the size is known to be inside the bound.

    Returns:
        stdout, unmodified — empty when `stdout` redirected it to a file.

    Raises:
        IsolationError: The command exited non-zero and `check` is set; the
            child could not be spawned at all — an absent `git` raises
            `FileNotFoundError` and a non-executable one `PermissionError`, and
            an `OSError` escaping here would surface as a traceback instead of
            `FailureReason.ISOLATION_FAILED` (C-1029); or the run's wall clock
            elapsed while the child was running.
    """
    # Read once, before the child is spawned, so a slow spawn cannot make the
    # bound generous. `max(0.0, ...)`: an already-elapsed deadline is a timeout
    # of zero, which `subprocess.run` raises on immediately — one code path for
    # "no time left" and "ran out of time", rather than a branch that says the
    # same thing twice.
    deadline = _DEADLINE.get() if check else None
    with _isolating(f"cannot run git {args[0]}"):
        sink = os.open(stdout, _NOFOLLOW_FLAGS, 0o600) if stdout is not None else None
        try:
            proc = subprocess.run(
                ["git", "-C", str(repo), *args],
                env=dict(env),
                input=stdin,
                stdout=subprocess.PIPE if sink is None else sink,
                stderr=subprocess.PIPE,
                shell=False,
                timeout=None if deadline is None else max(0.0, deadline - time.monotonic()),
            )
        except subprocess.TimeoutExpired as exc:
            # Not routed through `_isolating`: `TimeoutExpired` is a
            # `SubprocessError` and not an `OSError`, so it would escape as a
            # traceback (C-1029). The message names the phase rather than the
            # subcommand alone — an operator reading it needs to know the
            # budget was the REVIEW's, not a bound git invented.
            raise IsolationError(
                f"git {args[0]}: the review's wall clock elapsed while the ephemeral worktree "
                "was being built — the whole remaining budget of the run's timeout went to git"
            ) from exc
        finally:
            if sink is not None:
                os.close(sink)
    if check and proc.returncode != 0:
        # Sanitized, not just decoded: git echoes what it was given and what it
        # found — a ref name, a path, a hook's own output — so this string is
        # branch-controlled, and it becomes `Review.detail` (C-1028, C-1035).
        detail = _sanitize(proc.stderr.decode(errors="replace").strip())
        raise IsolationError(f"git {args[0]} failed ({proc.returncode}): {detail}")
    return proc.stdout or b""


def _text(repo: Path, *args: str, env: Mapping[str, str], stdin: bytes | None = None) -> str:
    """`_git`, decoded and stripped, for the calls whose output is a sha or a version.

    `os.fsdecode`, not `bytes.decode`: the same round-trippable surrogateescape
    the path-carrying calls need, so one decoder covers both.

    Args:
        repo: What `-C` is given.
        *args: The git arguments.
        env: The environment for the child.
        stdin: Bytes to feed the child.

    Returns:
        stdout, decoded and stripped.
    """
    return os.fsdecode(_git(repo, *args, env=env, stdin=stdin)).strip()


def _split_z(raw: bytes) -> tuple[str, ...]:
    """Split a `-z` record stream, dropping the empty field the trailing NUL leaves.

    Args:
        raw: The stream.

    Returns:
        The records, decoded with `os.fsdecode` so an undecodable path round-trips.
    """
    return tuple(os.fsdecode(field) for field in raw.split(b"\0") if field)


def _ls_tree(repo: Path, commitish: str, env: Mapping[str, str]) -> tuple[tuple[str, str, str], ...]:
    """Read `commitish`'s entries as `(mode, sha, path)`, `-z` so nothing is C-quoted.

    See `neutralize` for why the `-z` is a security requirement rather than a
    style choice.

    Args:
        repo: The repository top level.
        commitish: The tree-ish to list.
        env: The environment for the git call.

    Returns:
        One triple per entry, recursively, gitlinks included.
    """
    entries: list[tuple[str, str, str]] = []
    for record in _git(repo, "ls-tree", "-r", "-z", commitish, env=env).split(b"\0"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        mode, _, rest = meta.partition(b" ")
        _, _, sha = rest.partition(b" ")
        entries.append((mode.decode(), sha.decode(), os.fsdecode(path)))
    return tuple(entries)


def _hostile(entries: Sequence[tuple[str, str, str]]) -> tuple[str, ...]:
    """The paths in `entries` that must not survive — by name (C-1005) or by mode (C-1043).

    Shared by `neutralize`'s drop list and by its post-condition on the resulting
    tree, so the invariant is asserted with exactly the predicate that built the
    list rather than with a second copy of it.

    Args:
        entries: `(mode, sha, path)` triples, as `_ls_tree` returns them.

    Returns:
        The sorted, de-duplicated paths.
    """
    return tuple(sorted({path for mode, _, path in entries if matches(path) or mode in _DROP_MODES}))


def _batch(repo: Path, shas: Sequence[str], *args: str, env: Mapping[str, str]) -> bytes:
    """Feed `shas` to one `git cat-file` child and return its whole answer.

    `--buffer` because the request list is written and the answer read by one
    `communicate()`: git has no reason to flush per object, and at six figures
    of entries the syscalls are the difference the batching exists to buy.

    Args:
        repo: The repository top level.
        shas: The object names, one per request line.
        *args: The `cat-file` mode — `--batch-check` or `--batch`.
        env: The environment for the git call.

    Returns:
        The child's stdout, undecoded: `--batch` interleaves blob bytes with its
        own headers and a blob is whatever the branch committed.
    """
    return _git(repo, "cat-file", *args, "--buffer", env=env, stdin=b"".join(f"{sha}\n".encode() for sha in shas))


def _batch_header(line: bytes) -> tuple[str, int]:
    """Read one `<oid> SP <type> SP <size>` answer line, refusing anything else.

    The one guard both batches need. `cat-file -s` per object got this for free —
    an object the store does not hold exits 128 and `_git` maps it — while a
    batch answers `<oid> missing` IN BAND and still exits 0. An unguarded `int()`
    would raise `ValueError` out of this module, where `review()`'s
    plugin-boundary backstop catches it and resolves the call
    `indeterminate`/`MALFORMED_OUTPUT` — so **what this guard buys is
    classification, not totality** (C-1029): a pruned object store is an
    isolation failure nox can name, not a shrug. It is reachable twice: a pruned
    or partially fetched store answers the size pass that way, and a
    `gc --prune=now` landing between the two children answers the content pass
    that way for an object the size pass had already cleared.

    Args:
        line: One answer line, without its terminator.

    Returns:
        The object name and its size in bytes.

    Raises:
        IsolationError: The line is not an object-info answer.
    """
    name, _, rest = line.partition(b" ")
    size = rest.rpartition(b" ")[2]
    if not size.isdigit():
        raise IsolationError(f"git cat-file cannot read a symlink blob: {_sanitize(os.fsdecode(line))}")
    return name.decode(), int(size)


def _link_targets(repo: Path, entries: Sequence[tuple[str, str, str]], env: Mapping[str, str]) -> dict[str, str]:
    """Every `120000` blob's sanitized rendering, keyed by sha, in at most two git children.

    **The count of children is the point.** Asking `cat-file` per entry costs two
    processes per `120000` entry per tree end, and both ends are neutralized on
    every run: a tree of 50 000 symlinks measured **40.3 s inside `neutralize`
    alone**. Nothing upstream bounds that — `ENUMERATION_BUDGET` is a slice
    `workspace` applies to the finished lists, so it caps what is REPORTED and
    never what is spent, and `api.TimeoutPolicy` reaches the harness supervisor,
    not this module, where no git call carries a `timeout=`. Batched, the same
    tree is **0.5 s**.

    The size pass is separate and comes first, because `--batch` writes a whole
    object out whatever its size and `_git` holds a child's entire stdout in
    memory: only shas the size pass cleared are ever asked for. That is the same
    guarantee the per-entry `cat-file -s` gave, kept for the same reason — see
    `SYMLINK_TARGET_BUDGET`.

    Gitlinks are absent by construction: a `160000` entry's target is its
    recorded commit sha, which needs no read at all, and asking the object store
    for a commit this repository may not even have would fail the batch.

    Args:
        repo: The repository top level.
        entries: `(mode, sha, path)` triples, as `_ls_tree` returns them.
        env: The environment for the git calls.

    Returns:
        `{blob sha: rendering}` for every distinct `120000` blob in `entries` —
        the sanitized target, or a size-only stand-in for a blob no plausible
        symlink target could fill. Empty when there is no symlink entry, which
        is the ordinary tree and spawns nothing.
    """
    shas = sorted({sha for mode, sha, _ in entries if mode == SYMLINK_MODE})
    if not shas:
        return {}
    sizes = dict(_batch_header(line) for line in _batch(repo, shas, "--batch-check", env=env).splitlines())
    blobs = _read_batch(_batch(repo, [sha for sha in shas if sizes[sha] <= SYMLINK_TARGET_BUDGET], "--batch", env=env))
    return {
        sha: sanitize_target(blobs[sha])
        if sha in blobs
        else f"…(unread: {sizes[sha]} bytes, over the {SYMLINK_TARGET_BUDGET}-byte budget)"
        for sha in shas
    }


def _read_batch(raw: bytes) -> dict[str, bytes]:
    """Split a `git cat-file --batch` stream into `{sha: content}`.

    The stream is `<sha> SP <type> SP <size> LF <content> LF` per object, and the
    length prefix is what makes it parseable at all: a symlink blob is arbitrary
    committed bytes and may hold the header shape, a NUL or no trailing newline
    of its own. Indexed rather than split, so nothing in `content` is ever read
    as a delimiter.

    Args:
        raw: The child's whole stdout. Empty when nothing was requested.

    Returns:
        One entry per object in the stream.
    """
    out: dict[str, bytes] = {}
    at = 0
    while at < len(raw):
        end = raw.index(b"\n", at)
        name, size = _batch_header(raw[at:end])
        out[name] = raw[end + 1 : end + 1 + size]
        at = end + 2 + size
    return out


def _render(entries: Iterable[tuple[str, str, str]]) -> tuple[str, ...]:
    """Render `(path, sha, target)` triples as sorted, de-duplicated `<path> -> <target>` lines.

    Both halves are sanitized, and both for the same reason: C-1028 states these
    lines verbatim in the prompt, and a committed PATH is exactly as
    attacker-chosen as a symlink's target. `sanitize_target` ran at `neutralize`
    time on the target; `sanitize_path` runs here on the path.

    Args:
        entries: The by-mode entries, as `neutralize` returns them.

    Returns:
        The rendered lines.
    """
    return tuple(sorted({f"{sanitize_path(path)} -> {target}" for path, _, target in entries}))


def _refuse(offenders: Sequence[str], message: str) -> None:
    """Raise naming `offenders`, or return when there are none.

    One guard for both re-checks: `verify`'s against the checkout and
    `neutralize`'s against its own synthetic tree — which is also why the
    sanitizing happens here rather than at either call site. An offender is a
    committed path, as attacker-chosen as a symlink's target, and this message
    becomes `Review.detail` (C-1028, C-1035).

    Args:
        offenders: What was found, as raw paths. Empty means the check passed.
        message: What the offenders violate. nox's own prose, never repository
            content — the caller states it.

    Raises:
        IsolationError: `offenders` is non-empty.
    """
    if offenders:
        raise IsolationError(f"{message}: {', '.join(_sanitize(entry) for entry in offenders)}")


def _commit(repo: Path, spec: str, env: Mapping[str, str]) -> str:
    """Resolve `spec` to a commit sha, refusing anything that does not resolve.

    `--end-of-options` so a commit-ish that begins with `-` is a revision and
    never an option.

    Args:
        repo: The repository top level.
        spec: The commit-ish.
        env: The environment for the git call.

    Returns:
        The commit sha.

    Raises:
        IsolationError: `spec` does not resolve to a commit.
    """
    return _text(repo, "rev-parse", "--verify", "--end-of-options", f"{spec}^{{commit}}", env=env)


def _dotted(version: tuple[int, int, int]) -> str:
    """Render a parsed git version back as `major.minor.patch`.

    Args:
        version: The parsed triple.

    Returns:
        The dotted rendering, for the C-1041 refusal message.
    """
    return ".".join(str(part) for part in version)


def _escape(char: str) -> str:
    r"""Render one character, escaping anything that steers a renderer, a terminal or a model.

    Escaped: every C0/C1 control and DEL; the two Unicode line separators
    U+2028/U+2029, which are a line break to a JSON, HTML or markdown renderer
    and to a model reading the prompt while a `"\n" not in` check sees nothing;
    the bidi embeddings, overrides and isolates U+202A-U+202E and U+2066-U+2069,
    which reorder what a human reads while the bytes stay put (Trojan Source);
    and the lone surrogates `os.fsdecode` maps an undecodable byte onto, which
    raise `UnicodeEncodeError` in every consumer that encodes the string —
    `Path.write_text`, `json.dumps(...).encode()`, argv.

    Args:
        char: The character.

    Returns:
        The character, or its `\xNN` (below U+0100) or `\uNNNN` escape.
    """
    if char < " " or "\x7f" <= char <= "\x9f" or char in _UNSAFE_CHARS or "\ud800" <= char <= "\udfff":
        return f"\\x{ord(char):02x}" if ord(char) < 0x100 else f"\\u{ord(char):04x}"
    return char


@cache
def _escape_table() -> dict[int, str]:
    """The `str.translate` table `_sanitize` runs, built from `_escape` itself.

    Derived and never restated: `_escape` stays the one place the rule lives, so
    the table cannot drift from it the way a hand-written character class would.
    Every entry is a code point `_escape` does not return unchanged.

    Built once and cached rather than at import, and over `range(0xE000)` rather
    than all of Unicode: the full sweep is 176 ms, which is more than importing
    `nox` costs in total, while the bounded one is 8 ms. The bound is safe
    because the highest code point `_escape` escapes is U+DFFF, the last lone
    surrogate — and it is not an assumption a reader has to take on trust:
    `test_sanitize_escapes_exactly_the_reference_rule_at_every_unicode_code_point`
    sweeps every code point in `range(0x110000)` against a hand-written oracle,
    so a rule that grew past this bound fails there rather than silently letting
    a steering character through.

    Returns:
        `{code point: escape}` for every character `_escape` refuses.
    """
    return {point: escaped for point in range(0xE000) if (escaped := _escape(chr(point))) != chr(point)}


def _sanitize(text: str) -> str:
    r"""Escape every steering character in `text`, without truncating it.

    The primitive under `sanitize_path`, and the one every refusal message built
    from repository content goes through: git's own stderr, and the offenders
    `_refuse` names. All three reach `Review.detail`, which the CLI prints as
    prose, and all three are assembled from bytes a branch chose.

    Nothing is bounded here. A tree entry's path is bounded by git, a refusal
    lists what a re-check found, and git's diagnostic is the evidence a reader
    needs whole — the byte cap that exists for a `120000` blob is about a value
    that could be a whole file (`sanitize_target`), which none of these are.

    One `str.translate` and not a per-character comprehension, for the reason
    `_fence` is not one either. This runs per PATH out of `_render`, over every
    tree entry both ends carry, so its input is the whole of an attacker-sized
    path list: `"".join(_escape(char) for char in text)` pays a Python call and
    a generator resume per character and materializes an N-pointer list inside
    `str.join`, which measured **165x** the cost of the table on 409 KB of path
    text (26.9 ms against 0.163 ms) and **9.7x** its transient memory (3.9 MB
    against 0.4 MB) — the pointer list is what the memory multiplier is.

    No `isascii` fast path, unlike `_fence`: `_escape` escapes the C0 controls
    and DEL, which are ASCII, so "ASCII" is not "nothing to do here" — and a
    compiled-regex pre-scan for the unsafe classes measured *slower* than simply
    translating (0.68 ms against the table's 0.16 ms on the same text), because a
    character class holding the surrogate range compiles to a bigcharset whose
    per-character lookup costs more than the translate it was meant to skip.
    The table alone is the fast path.

    Args:
        text: The rendering, as `os.fsdecode` or a lossy decode produced it.

    Returns:
        `text` with every character `_escape` refuses replaced by its escape.
    """
    return text.translate(_escape_table())


def artifact_rel(repo: Path, path: Path | None) -> str:
    """The artifact's repository-relative path, or `ConfigError` (C-1027).

    Separate from `materialize_artifact` because `workspace` runs it before
    `sweep` — the refusal must have touched no repository state, and `sweep`
    already would have. **Public for the same reason a third caller needs it:**
    `api`'s step-6a pre-flight answers this question ahead of the C-1014 probe
    (H13), and a copy of these three checks there is a copy that drifts — the
    one it already had dropped the `_isolating` guard below, so a removed cwd
    escaped as a bare `FileNotFoundError` and degraded to `indeterminate`
    instead of refusing `ISOLATION_FAILED`. `ConfigError` and not an isolation
    failure because
    C-1027 fixes the outcome as `FailureReason.INVALID_CONFIG`; it is imported
    from `config.py` rather than restated here, which is also what keeps
    `review()`'s C-1029 catch a closed match over one hierarchy.

    Args:
        repo: The repository top level.
        path: The artifact, as the `ReviewTarget` carries it.

    Returns:
        The repository-relative path, POSIX-separated.

    Raises:
        ConfigError: `path` is absent, is not a regular file, or resolves outside
            `repo`.
        IsolationError: The resolution itself failed — a relative `path` is
            resolved against nox's cwd, and `os.getcwd()` raises once that
            directory is gone (C-1029).
    """
    with _isolating(f"cannot resolve the plan artifact path {path}"):
        resolved = Path(path or ".").resolve()
        root = repo.resolve()
    if not resolved.is_file():
        raise ConfigError(f"plan artifact is missing or not a regular file: {path}")
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ConfigError(f"plan artifact resolves outside the repository: {path}") from exc


def check_git_version(repo: Path, env: Mapping[str, str]) -> tuple[int, int, int]:
    """Probe `git --version` once per review and refuse a stale git (C-1041).

    Runs before `sweep` and before any other git call, so a refusal touches no
    repository state.

    Args:
        repo: Where to run git. Any existing directory works.
        env: The environment for the probe.

    Returns:
        The parsed `(major, minor, patch)`; a two-component version reads as
        patch `0`.

    Raises:
        IsolationError: Below `GIT_FLOOR`, or the output carries no parseable
            version. The message names found and floor and states the reason:
            below 2.31 `GIT_CONFIG_COUNT` is ignored silently, so C-1031 would
            become a no-op with no error.
    """
    reported = _text(repo, "--version", env=env)
    found = _VERSION_RE.search(reported)
    if found is None:
        raise IsolationError(f"cannot parse a git version from {reported!r}; nox requires >= {_dotted(GIT_FLOOR)}")
    version = (int(found[1]), int(found[2]), int(found[3] or 0))
    if version < GIT_FLOOR:
        raise IsolationError(
            f"git {_dotted(version)} is below the {_dotted(GIT_FLOOR)} floor: below 2.31 GIT_CONFIG_COUNT is "
            "ignored silently, so the C-1031 override set would become a no-op with no error"
        )
    return version


def discover_repo(start: Path, env: Mapping[str, str]) -> tuple[Path, Path]:
    """Resolve the repository through git, never by assuming a `.git` directory.

    A repository whose `.git` is a *file* — a linked worktree, or a submodule
    checkout — has its objects and refs in the common dir (C-1003). Both values
    are returned: `toplevel` is what every other call here runs against, and
    `common_dir` is what the temp-directory containment check in `workspace`
    tests against, so an ephemeral worktree can never be placed inside either
    half of the repository.

    Args:
        start: Any path inside the repository.
        env: The environment for the git calls.

    Returns:
        `(toplevel, common_dir)`, both absolute and resolved.

    Raises:
        IsolationError: `start` is not inside a git repository, or either
            reported path could not be resolved (C-1029).
    """
    listed = _text(start, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir", env=env)
    toplevel, _, common = listed.partition("\n")
    with _isolating(f"cannot resolve the repository discovered from {start}"):
        return Path(toplevel).resolve(), Path(common).resolve()


def matches(path: str) -> bool:
    """Whether `path` is a C-1005 set member, by path component at any depth.

    Every component is tested against `NEUTRALIZE_DIRS`, the basename against
    `NEUTRALIZE_FILES` and `NEUTRALIZE_GLOBS`, and the whole path against
    `NEUTRALIZE_PREFIXES` (E18). The basename is deliberately in the directory
    test too: a set member committed as a symlink is a single-component blob
    path, and testing only `parts[:-1]` let it through (SD § 4.1).

    The prefix test is the one that is NOT depth-independent, and deliberately:
    it is anchored at the repository root, which under C-1003 is the harness's
    cwd. See `NEUTRALIZE_PREFIXES` for why a basename would over-drop instead.

    **Case-insensitive, because macOS is a supported platform.** APFS and HFS+
    are case-insensitive by default, so `.Claude/settings.json`, `CLAUDE.MD`,
    `.ENV`, `.Codex/config.toml` and `Mise.toml` all materialize in the checkout
    at the path a harness then opens — `open(".claude/settings.json")` resolves
    to `.Claude/settings.json`, and C-1005 is defeated by one capital letter.
    Both sides are casefolded rather than lowercased (Kelvin sign, dotted I),
    and the globs go through `fnmatch.fnmatch` so a case-insensitive platform's
    own `normcase` applies as well. Over-dropping on Linux costs nothing: the
    entry lands in `neutralized`, which is evidence, not a verdict input.

    Args:
        path: A repository-relative path, already un-quoted — `ls-tree` is read
            `-z` precisely so this never sees a C-quoted string (see
            `neutralize`).

    Returns:
        Whether the entry must be dropped by name.
    """
    parts = [part.casefold() for part in path.split("/")]
    return (
        any(part in _FOLDED_DIRS for part in parts)
        or parts[-1] in _FOLDED_FILES
        or any(fnmatch.fnmatch(parts[-1], pattern.casefold()) for pattern in NEUTRALIZE_GLOBS)
        or "/".join(parts).startswith(_FOLDED_PREFIXES)
    )


def resolve_pair(repo: Path, target: ReviewTarget, env: Mapping[str, str]) -> tuple[str, str]:
    """Resolve `target` to a `(base, head)` pair of real commit-ishes (C-1004).

    Nothing here mutates a ref, the index or the working tree — `git stash
    create` writes a commit object and returns its SHA without touching any of
    the three (proven on git 2.54.0, WP2's spike).

    Args:
        repo: The repository top level.
        target: What is under review. `plan-artifact` is materialized by
            `materialize_artifact` instead and is not accepted here.
        env: The environment for the git calls.

    Returns:
        `(base, head)`: for `"ref"`, `merge-base(base, ref)` when `base` is
        given else `<ref>^`; for `"working-tree"`, `(HEAD, <stash sha>)`, or
        `(HEAD^, HEAD)` when `stash create` prints nothing on a clean tree.

    Raises:
        IsolationError: A commit-ish does not resolve, or `HEAD` has no parent
            where the fallback needs one.
    """
    if target.kind == "working-tree":
        stashed = _text(repo, "stash", "create", env=env)
        if stashed:
            return _commit(repo, "HEAD", env), stashed
        return _commit(repo, "HEAD^", env), _commit(repo, "HEAD", env)
    head = _commit(repo, f"{target.ref}", env)
    if target.base:
        return _text(repo, "merge-base", _commit(repo, f"{target.base}", env), head, env=env), head
    return _commit(repo, f"{target.ref}^", env), head


def materialize_artifact(repo: Path, path: Path, env: Mapping[str, str]) -> tuple[str, str, str]:
    """Build the `plan-artifact` pair: the empty tree, plus a one-file addition.

    The artifact *is* the diff, so every adapter takes the ordinary code-diff
    route with no branch (C-1027). Neutralization still runs over the pair — the
    artifact may itself be a set member by name, and dropping it is then the
    correct answer.

    Args:
        repo: The repository top level.
        path: The artifact. Must exist and resolve inside `repo`.
        env: The environment for the git calls.

    Returns:
        `(base, head, relpath)` — the empty-tree commit, its one-file child, and
        the artifact's repository-relative path. The path is returned rather
        than recomputed by the caller so the containment check that produced it
        is not duplicated against an unresolved input.

    Raises:
        ConfigError: `path` is missing, is not a regular file, or resolves
            outside `repo` — raised before any git object is written (C-1027).
            `api` maps it onto `FailureReason.INVALID_CONFIG`.
    """
    relpath = artifact_rel(repo, path)
    empty = _text(repo, "hash-object", "-w", "-t", "tree", "--stdin", env=env, stdin=b"")
    base = _text(repo, "commit-tree", empty, "-m", "nox: empty base", env=env)
    with _isolating(f"cannot read the plan artifact {relpath}"):
        content = (repo / relpath).read_bytes()
    blob = _text(repo, "hash-object", "-w", "--stdin", env=env, stdin=content)
    with _isolating("cannot create a temporary index"), tempfile.TemporaryDirectory(prefix="nox-index-") as index_dir:
        scoped = {**env, "GIT_INDEX_FILE": str(Path(index_dir) / "index")}
        _git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{relpath}", env=scoped)
        tree = _text(repo, "write-tree", env=scoped)
    head = _text(repo, "commit-tree", tree, "-p", base, "-m", "nox: plan artifact", env=env)
    return base, head, relpath


def neutralize(
    repo: Path,
    commitish: str,
    env: Mapping[str, str],
    parent: str | None = None,
) -> tuple[str, tuple[str, ...], tuple[tuple[str, str, str], ...]]:
    r"""Rewrite `commitish` into a synthetic commit with the hostile set removed.

    Reads the tree into a temporary index, drops every entry matching C-1005 by
    name and every entry whose mode is `160000` (C-1005) or `120000` (C-1043),
    writes the tree, commits it. Nothing on disk is touched.

    **The tree is read `git ls-tree -r -z` and the drop list is fed to
    `git update-index --force-remove -z --stdin`.** Without `-z`, git C-quotes
    any path containing a newline, a quote, a backslash or a non-ASCII byte —
    `"pack\nage/.claude/settings.json"`, quotes included. `matches` would still
    see `.claude` and list it, but `--force-remove` on the quoted string matches
    no index entry and exits 0: the hostile file survives into the checkout
    while `neutralized` reports it dropped. `-z` also removes the argv-length
    ceiling that would otherwise need chunking.

    The target is always given `-p <synthetic base>`: without it both ends are
    parentless roots, `merge-base` exits 1 and `git diff <sb>...<st>` fails with
    "no merge base", so the Codex `--base` leg dies at runtime.

    The synthetic tree is then re-listed and checked: no `120000` or `160000`
    entry may remain and no surviving path may `match`. That is an invariant on
    the *result*, so it holds even if the drop list itself was built wrong —
    which is the one class `verify` structurally cannot catch.

    Args:
        repo: The repository top level.
        commitish: The end to rewrite.
        env: The environment for the git calls.
        parent: The synthetic base, for the target end.

    **The two lists overlap; they are evidence, not a partition.** An entry that
    `matches` is listed in `neutralized`, and EVERY `120000`/`160000` entry is
    listed in `filtered` with its target — a matching one included. C-1043(2)
    asks for `<path> -> <link target>` for each by-mode drop, and `.codex ->
    $HOME/.codex` (SD § 9.4, Security-H5) is exactly the entry whose target the
    reviewer most needs; reporting it as the bare string `.codex` threw the
    target away without ever computing it.

    What the by-name match still governs is `filtered_changed`, which is built
    in `workspace`: a C-1005 member is excluded there, because
    `filtered_changed` forces `needs-attention` and a member carries no review
    value by definition — the reviewer must not see it — so a branch that edits
    its own `.codex` symlink would otherwise become permanently un-approvable.
    C-1043's evidence-loss argument is about symlinks that are ordinary content.

    Returns:
        `(sha, neutralized, filtered)`. `neutralized` is the sorted paths
        dropped by name. `filtered` is the sorted `(path, sha, target)` triples
        for every by-mode drop — a symlink's target is its sanitized blob
        content, a gitlink's is its recorded commit SHA. Kept structured rather
        than pre-rendered because both other halves are load-bearing: `verify`
        `lexists`es the path, and `filtered_changed` differences on the sha,
        which is the only half that cannot collide the way a
        `SYMLINK_TARGET_BUDGET`-truncated rendering can.

    Raises:
        IsolationError: Any git call fails, the temporary index cannot be
            created, or the synthetic tree still holds a by-mode or by-name
            entry.
    """
    entries = _ls_tree(repo, commitish, env)
    named = tuple(sorted({path for _, _, path in entries if matches(path)}))
    targets = _link_targets(repo, entries, env)
    filtered = tuple(
        sorted(
            (path, sha, sha if mode == GITLINK_MODE else targets[sha])
            for mode, sha, path in entries
            if mode in _DROP_MODES
        )
    )
    drop = _hostile(entries)
    with _isolating("cannot create a temporary index"), tempfile.TemporaryDirectory(prefix="nox-index-") as index_dir:
        scoped = {**env, "GIT_INDEX_FILE": str(Path(index_dir) / "index")}
        _git(repo, "read-tree", commitish, env=scoped)
        if drop:
            _git(
                repo,
                "update-index",
                "--force-remove",
                "-z",
                "--stdin",
                env=scoped,
                stdin=b"".join(os.fsencode(entry) + b"\0" for entry in drop),
            )
        tree = _text(repo, "write-tree", env=scoped)
    ancestry = [] if parent is None else ["-p", parent]
    sha = _text(repo, "commit-tree", tree, *ancestry, "-m", f"nox: neutralized {commitish}", env=env)
    _refuse(_hostile(_ls_tree(repo, sha, env)), f"the neutralized tree for {commitish} still holds")
    return sha, named, filtered


def sanitize_target(raw: bytes) -> str:
    r"""Render a symlink's blob content safe to state in a prompt and a log.

    A mode-`120000` blob is arbitrary attacker-chosen bytes: newlines would
    inject lines into a prompt section nox presents as its own fact, ANSI
    escapes would manipulate the consumer's terminal, a NUL would raise from
    `subprocess` when the prompt goes on argv, invalid UTF-8 would raise on
    decode, and megabytes would hit `E2BIG` — each a one-file denial of service
    on any branch (C-1043, C-1028).

    Decodes with `errors="replace"`, escapes every C0/C1 control character and
    DEL as `\xNN`, and truncates to `SYMLINK_TARGET_BUDGET` bytes with an
    explicit marker. The result is evidence for a human reader, never a value to
    resolve.

    Args:
        raw: The blob's bytes.

    Returns:
        The sanitized single-line rendering.
    """
    rendered = _sanitize(raw[:SYMLINK_TARGET_BUDGET].decode("utf-8", errors="replace"))
    encoded = rendered.encode()
    if len(raw) <= SYMLINK_TARGET_BUDGET and len(encoded) <= SYMLINK_TARGET_BUDGET:
        return rendered
    return encoded[:SYMLINK_TARGET_BUDGET].decode("utf-8", errors="ignore") + " …(truncated)"


def sanitize_path(path: str) -> str:
    r"""Render a repository path safe to state in a prompt and a log (C-1028, C-1043).

    A committed PATH is as attacker-chosen as a symlink's target, and every path
    nox reports goes into a section the prompt states verbatim as nox's own
    fact. `pack\nage/.claude/settings.json` injects a line there,
    `docs/\x1b[31mesc` drives the consumer's terminal, and the lone surrogate
    `os.fsdecode` produces for an undecodable byte raises `UnicodeEncodeError`
    in any consumer that writes the evidence out — a one-file denial of service
    from a single committed filename. `sanitize_target` escaped the target half
    of `<path> -> <target>` while the path half went in raw.

    Not truncated, unlike a `120000` blob — and **not because git bounds the
    path**: it does not. WP15's H6 reproduction committed a 59 960-character
    tree entry and git accepted it, so the old claim here was false and the
    ceiling it implied does not exist. The real reason is that the whole path IS
    the evidence and the entry's identity: a reader has to be able to find the
    file, `verify` `lexists`es it, and a truncated path collides with its
    siblings the way a `SYMLINK_TARGET_BUDGET`-truncated target can. Bounding it
    would be a byte cap over the assembled evidence — E53's territory, not a
    limit this function may invent on its own. **Only the reported copy is
    sanitized.**
    `verify`, `update-index --force-remove -z` and every internal comparison
    keep the raw path — sanitizing those would reopen the C-quoting hole the
    `-z` reads exist to close.

    Args:
        path: The repository-relative path, as `os.fsdecode` produced it.

    Returns:
        The sanitized single-line rendering.
    """
    return _sanitize(path)


def pin_refs(repo: Path, token: str, base: str, target: str, env: Mapping[str, str]) -> None:
    """Pin both synthetic commits under `refs/nox/<token>/` (C-1004).

    Called immediately after `commit-tree` and BEFORE `worktree add`: a
    concurrent `git gc --prune=now` in that window would otherwise collect two
    commits nothing references. `sweep`'s grace period is what keeps another
    process from reaping these before `worktree add` registers the worktree.

    Args:
        repo: The repository top level.
        token: This call's unique token.
        base: The synthetic base commit.
        target: The synthetic target commit.
        env: The environment for the git calls.

    Raises:
        IsolationError: Either `update-ref` fails.
    """
    for leg, sha in (("base", base), ("target", target)):
        _git(repo, "update-ref", f"{REF_NAMESPACE}/{token}/{leg}", sha, env=env)


def sweep(repo: Path, env: Mapping[str, str]) -> None:
    """Reap what a SIGKILLed nox left behind (C-1006).

    Runs `git worktree prune`, then deletes every `refs/nox/<token>/*` whose
    token has neither a registered worktree nor a ref younger than
    `SWEEP_GRACE_S`. `prune` never touches refs, so without this sweep a leaked
    ref pins its synthetic commits forever.

    The token is recovered from the worktree directory name, which carries it
    after `WORKTREE_PREFIX` — `git worktree list --porcelain` reports paths, and
    nothing else joins a path back to a ref namespace.

    Both conditions are load-bearing, and this is what makes concurrent nox
    processes safe with no repository lock. The registered-worktree test alone
    is not enough: a call pins its refs before `worktree add`, so in that window
    it looks exactly like a leak. The age test covers that window; the worktree
    test covers a long-running review that outlives the grace period.

    **What this does NOT reclaim is a SIGKILLed nox.** That leaves the worktree
    directory in place, so `prune` keeps the registration, the token stays in
    `live`, and its refs are spared forever however old they are. What is
    recovered is the *pruned* shape — a registration whose directory is gone —
    and the ordinary teardown. `SWEEP_GRACE_S` carries the `fcntl.flock`
    upgrade path that would make "live" an observation rather than an inference.

    A refname that does not reach a `refs/nox/<token>/…` shape is skipped rather
    than indexed into: a bare `refs/nox` ref cannot be attributed to a token, and
    an `IndexError` here would escape as a traceback (C-1029).

    Args:
        repo: The repository top level.
        env: The environment for the git calls.

    Raises:
        IsolationError: `worktree prune` fails. A ref that vanishes underneath
            the sweep — another process reaped it first — is not an error, so
            the delete carries no old-value guard.
    """
    _git(repo, "worktree", "prune", env=env)
    live: set[str] = set()
    for line in _text(repo, "worktree", "list", "--porcelain", env=env).split("\n"):
        name = Path(line[len("worktree ") :]).name if line.startswith("worktree ") else ""
        if name.startswith(WORKTREE_PREFIX):
            live.add(name[len(WORKTREE_PREFIX) :].rsplit("-", 1)[0])
    now = time.time()
    legs: dict[str, list[str]] = {}
    young: set[str] = set()
    listed = _text(repo, "for-each-ref", "--format=%(refname) %(committerdate:unix)", REF_NAMESPACE, env=env)
    for line in listed.split("\n"):
        refname, _, stamp = line.rpartition(" ")
        parts = refname.split("/")
        if len(parts) < 3:
            continue
        token = parts[2]
        legs.setdefault(token, []).append(refname)
        if now - int(stamp or 0) < SWEEP_GRACE_S:
            young.add(token)
    for token, refnames in legs.items():
        if token in live or token in young:
            continue
        for refname in refnames:
            _git(repo, "update-ref", "-d", refname, env=env)


def write_nofollow(path: Path, content: bytes) -> None:
    """Write `content` to `path`, refusing to follow a symlink (C-1009).

    Opened `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`: `O_EXCL` refuses an existing
    file and `O_NOFOLLOW` refuses an existing symlink, so neither a committed
    entry nor a race can redirect the write outside the scratch directory.

    Bytes, not text: `git diff` output carries whatever the tracked files hold,
    and a file with invalid UTF-8 in its content or its path would otherwise
    raise on decode and kill the review — an attacker-chosen denial of service.

    ponytail: `O_NOFOLLOW` guards the FINAL component only. That suffices here
    because the parent scratch directory was `mkdir`ed by nox microseconds
    earlier and no adversary process exists before `yield`. Any write into
    scratch AFTER the harness spawns is not protected — the harness may have
    replaced the directory with a symlink. Upgrade path if one is ever added:
    hold `os.open(scratch, O_RDONLY|O_DIRECTORY|O_NOFOLLOW)` and write with
    `dir_fd=`.

    Args:
        path: Where to write. Its parent must already exist.
        content: What to write.

    Raises:
        IsolationError: The path exists, is a symlink, or the write fails.
    """
    try:
        with os.fdopen(os.open(path, _NOFOLLOW_FLAGS, 0o600), "wb") as handle:
            handle.write(content)
    except OSError as exc:
        raise IsolationError(f"cannot write {path}: {exc}") from exc


def untracked(
    repo: Path,
    target: ReviewTarget,
    materialized: Sequence[str],
    env: Mapping[str, str],
) -> tuple[tuple[str, ...], int]:
    """Untracked paths NOT carried into the review, and how many were ignored.

    `git ls-files --others --exclude-standard` minus `materialized` (C-1026).

    **Only `working-tree` is ever non-empty.** C-1026 and SD § 4.1(c) scope the
    completeness check to the review TARGET, and a commit has no untracked files
    by construction: the untracked files sitting in the user's checkout are not
    part of a `ref` review's target, so counting them would make every `ref`
    review of a repository with two scratch files permanently un-approvable
    under WP8's enforcement. `plan-artifact` is the same case — subtracting only
    the artifact left every unrelated untracked file in the result.

    The second element counts what `--exclude-standard` hid. `ls-files --others`
    runs in the user's checkout, so the governing `.gitignore` is the one
    CURRENTLY checked out — not the reviewed ref's — and a `*` in it would empty
    `omitted` and make the "I could not see everything" stamp read clean. A
    count rather than a list because build output is the overwhelming majority.

    Args:
        repo: The repository top level.
        target: What is under review; every kind but `working-tree`
            short-circuits.
        materialized: Repository-relative paths the synthetic target carries.
        env: The environment for the git calls.

    Returns:
        `(omitted, ignored_count)`. A non-empty `omitted` means the verdict may
        not be `approve`.

    Raises:
        IsolationError: A git call fails.
    """
    if target.kind != "working-tree":
        return (), 0
    others = _split_z(_git(repo, "ls-files", "--others", "--exclude-standard", "-z", env=env))
    ignored = _split_z(_git(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "-z", env=env))
    return tuple(sorted(set(others) - set(materialized))), len(ignored)


def verify(path: Path, dropped: Sequence[str]) -> None:
    """Re-check with `lexists` that every dropped entry is absent (SD § 4.1).

    A false entry in `Containment.neutralized` or `.filtered` corrupts the stamp
    the consumer weights findings by, so the claim is verified rather than
    asserted. `lexists`, not `exists`: a dangling symlink is exactly the case
    that must fail.

    Both of the TARGET end's drop lists are checked — by-name and the path half
    of by-mode. C-1043(1) requires the checkout to contain no symlink at all,
    which nothing would test if only `neutralized` were passed.

    **The target end only, never the union of both ends.** The checkout
    materializes the synthetic target and nothing else, so a base-end drop says
    nothing about what is on disk. Checking the union rejects a legitimate
    branch: one that replaces a symlink with a real file drops `docs/x` by mode
    at the base end, and `docs/x` is then correctly present in the checkout as a
    regular blob. `Workspace.neutralized` and `.filtered` stay the union — they
    are evidence for the consumer about both ends — but only the target half is
    an assertion about the checkout.

    This catches a dropped entry that came back. It cannot catch an entry the
    matcher never matched — for that, `neutralize` re-lists its own synthetic
    tree and asserts the invariant on the result.

    Args:
        path: The ephemeral worktree.
        dropped: The TARGET end's bare repository-relative paths, by-name and
            by-mode together.

    Raises:
        IsolationError: Any dropped entry exists in the checkout, naming it.
    """
    _refuse([entry for entry in dropped if os.path.lexists(path / entry)], f"a dropped entry is back in {path}")


@contextmanager
def workspace(
    repo: Path,
    target: ReviewTarget,
    *,
    path: Path | None = None,
    env: Mapping[str, str] | None = None,
    max_prompt_bytes: int = DEFAULT_MAX_PROMPT_BYTES,
    deadline: float | None = None,
) -> Generator[Workspace]:
    """Build, yield and tear down one ephemeral worktree (C-1003 to C-1006).

    Lifecycle, in the order the ADR fixes it (SD § 4.1), with the constraints
    that are security properties rather than convenience:

    1. Settle the reserved worktree path — the caller's, checked for the
       `nox-ws-<token>` shape before anything else runs, or `<temp root>/`
       `nox-ws-<token>`, the name `mkdtemp` will extend with its own entropy —
       and, unless the caller supplied one, build the environment with
       `config.minimal_env`, the single builder (C-1008, C-1031). The reserved
       path is what `minimal_env` tests the inbound path variables against, so
       it has to be a path and not the temp root: `TMPDIR` resolves inside the
       latter and would be dropped as if a branch had chosen it. Neither step
       touches git.
    2. `check_git_version` — refuses a stale git before anything is touched.
    3. `discover_repo`, then refuse if the reserved path resolves inside the
       repository or its common dir. `tempfile.gettempdir()` reads nox's own
       process environment, which the C-1008 minimal env does not reach, so a
       branch's `.envrc` setting `TMPDIR=$PWD/tmp` would otherwise place the
       ephemeral worktree inside the user's tree and void C-1003; a
       caller-supplied `path` gets exactly the same test, because a reserved
       path minted somewhere else is no more trusted than `TMPDIR`.
    4. Validate `target.path` for `plan-artifact` — a `ConfigError` here has
       touched no repository state, which `sweep` would already have done.
    5. `sweep` — reclaim a previous run's leaks.
    6. `resolve_pair` or `materialize_artifact`.
    7. `neutralize` both ends, target with `-p <synthetic base>`.
    8. `pin_refs` — BEFORE the worktree is created, so no gc can collect the pair.
    9. The worktree directory: `mkdtemp` when none was reserved, otherwise
       `mkdir` on the reserved path with no `exist_ok`; then the scratch
       directory, `mkdtemp`ed as its SIBLING. One guarded step, so the teardown
       may delete both without asking whether this call made them.
    10. `worktree add --detach` into it. The scratch directory was `mkdtemp`ed
        BESIDE the worktree in step 9 — never inside it, because the harness runs
        with the worktree as its cwd and nox's own prompt would otherwise be part
        of the surface under review.
    11. Write the `<synthetic base>..<synthetic target>` diff — **straight to
        the scratch file, never through memory** — then `stat` it and refuse
        past `max_prompt_bytes` before a byte of it is read (E53). Run with
        `--no-ext-diff` so an inherited `diff.external` cannot execute and
        `--no-textconv` so a `diff.<driver>.textconv` cannot either:
        `$GIT_DIR/info/attributes` is read whatever `core.attributesFile` and
        `GIT_ATTR_NOSYSTEM` say, and the worktree shares that `$GIT_DIR`.
    12. `verify` both drop lists absent from the checkout.

    Teardown runs every step independently and none of them may raise, so a
    failing `worktree remove` cannot skip the ref deletions and leave the
    synthetic commits pinned forever. A teardown failure never replaces an
    exception from the body: a `verify` failure — a symlink reached the checkout
    — is the loudest signal in the design and must not be masked by a cleanup
    error. `check=False` covers a non-zero exit and the `suppress` around each
    step covers a spawn failure.

    Args:
        repo: Any path inside the repository under review — resolved through
            git, so a linked worktree or submodule checkout works (C-1003).
        target: What is under review.
        path: The reserved path of the ephemeral worktree, or `None` to mint one
            with `mkdtemp`. `review()` mints it before the C-1014 probe and
            hands the same value to `config.minimal_env` and to here, so the
            C-1025 environment digest is identical between probe and review;
            without that the two split and the containment stamp is wrong. It
            must NOT exist yet — it is created with no `exist_ok`, so a
            directory already there is an error rather than a shared one — and
            its basename must be `nox-ws-<token>`, which is the only thing that
            joins a leaked worktree back to its ref namespace for `sweep`. Its
            PARENT must be writable: the scratch directory is minted there
            (step 10), and being a sibling is what keeps it out of the review.
        env: The environment for every git call, already built by
            `config.minimal_env`. Used exactly as given, because it is the
            digest input `review()` committed to. Defaults to building one here,
            first against `repo` and then against the discovered top level.
        max_prompt_bytes: The ceiling on the diff this workspace will carry, in
            bytes — `NoxConfig.max_prompt_bytes`, whose default docstring holds
            the arithmetic. Measured against the diff FILE, before it is read,
            because a bound checked once the diff is in RAM is not a bound. Past
            it the workspace refuses whole rather than delivering a shortened
            change: C-1028 forbids trimming the evidence (E53).
        deadline: An absolute `time.monotonic()` every git call in the lifecycle
            is held to, or `None` for no bound. `review()` passes what is LEFT
            of `TimeoutPolicy.wall_clock_s` when the phase starts — no second
            number and no second key, because the git phase is part of the same
            run that policy already bounds (E54). The TEARDOWN is deliberately
            outside it: a cleanup that gives up strands a worktree and two
            pinned refs forever.

    Yields:
        The live workspace. Invalid once the block exits.

    Raises:
        IsolationError: Anything in the lifecycle fails, the reserved path
            resolves in-tree, its basename is not `nox-ws-<token>`, or
            `deadline` elapsed while a git call was running. `review()` maps it
            to `FailureReason.ISOLATION_FAILED` with no harness spawned
            (C-1029).
        ConfigError: A `plan-artifact` path that is missing or out of tree
            (C-1027), raised before any repository state is touched; the diff
            exceeds `max_prompt_bytes` (E53); or, on the `env is None` default,
            an environment `config.minimal_env` refuses to build (C-1008). All
            three are `FailureReason.INVALID_CONFIG`.
    """
    # Set here and released below, so the whole lifecycle — the pre-work included,
    # where `neutralize` hashes every path a hostile repository holds — is inside
    # the bound, and nothing outside one live workspace ever sees a value. A leak
    # would refuse the NEXT call's `discover_repo`, which runs before a policy to
    # derive a deadline from even exists (E54).
    token_deadline = _DEADLINE.set(deadline)
    try:
        # The token is minted here rather than beside `mkdtemp`, because the reserved
        # path has to exist as a VALUE before `minimal_env` is called: it is what
        # step 4 tests the inbound path variables against. The temp root itself will
        # not do — `TMPDIR` and, in a test tree, `HOME` resolve inside it, and every
        # one of them would then be dropped as if it were branch-controlled.
        token = secrets.token_hex(8)
        reserved_raw = Path(tempfile.gettempdir()) / f"{WORKTREE_PREFIX}{token}" if path is None else path
        if path is not None:
            # `sweep` recovers a call's token from the worktree directory name and
            # nothing else joins a path back to `refs/nox/<token>`, so a reserved
            # path has to carry the shape `mkdtemp` would have produced. Enforced
            # rather than worked around: a token that cannot be recovered makes the
            # refs of a SIGKILLed run unreclaimable forever (C-1006).
            stem = path.name.removeprefix(WORKTREE_PREFIX)
            token = stem.rsplit("-", 1)[0]
            if stem == path.name or not token:
                raise IsolationError(
                    f"the reserved worktree path {path} must be named `{WORKTREE_PREFIX}<token>`, "
                    "because `sweep` recovers a call's token from the directory name (C-1006)"
                )
        with _isolating(f"cannot resolve the reserved worktree path {reserved_raw}"):
            reserved = reserved_raw.resolve()
        resolved: Mapping[str, str] = env if env is not None else minimal_env(repo, reserved)[0]
        check_git_version(repo, resolved)
        toplevel, common = discover_repo(repo, resolved)
        # Rebuilt against the DISCOVERED top level: the first build could only test
        # `minimal_env`'s inbound path variables against the caller's `repo`, and a
        # caller inside a subdirectory would then let a `CODEX_HOME` at the
        # repository ROOT through. Never rebuilt when the caller supplied `env` —
        # that one is what C-1025 digested, and a second build here would split the
        # digest from the environment the children actually run under.
        if env is None:
            resolved = minimal_env(toplevel, reserved)[0]
        if reserved.is_relative_to(toplevel) or reserved.is_relative_to(common):
            raise IsolationError(
                f"the reserved worktree path {reserved} resolves inside the repository under review, "
                "so the ephemeral worktree would be built in-tree (C-1003)"
            )
        artifact = Path(target.path or ".") if target.kind == "plan-artifact" else None
        if artifact is not None:
            artifact_rel(toplevel, artifact)  # refuse before `sweep` touches anything
        sweep(toplevel, resolved)
        if artifact is not None:
            raw_base, raw_head, _ = materialize_artifact(toplevel, artifact, resolved)
        else:
            raw_base, raw_head = resolve_pair(toplevel, target, resolved)
        synthetic_base, base_named, base_filtered = neutralize(toplevel, raw_base, resolved)
        synthetic_target, head_named, head_filtered = neutralize(toplevel, raw_head, resolved, parent=synthetic_base)
        # The worktree and the scratch are made together, in one guarded step, so the
        # teardown below can remove both unconditionally: `mkdtemp` and an `os.mkdir`
        # with no `exist_ok` each prove this call created what it is about to delete.
        #
        # The scratch is a SIBLING of the worktree and never a child (C-1005): the
        # harness runs with the worktree as its cwd, so a scratch directory in there
        # puts nox's own prompt into the surface under review — and a reviewer doing
        # its job reports it as "repository content addresses the reviewer" on EVERY
        # run, which trains the operator to dismiss the one finding class that
        # catches real injection. `reserved` is proven out-of-tree just above, and a
        # sibling of it is out-of-tree for the same reason. `mkdtemp` rather than
        # `os.mkdir`: the suffix makes the name this call's alone even where two
        # calls share a token and a parent, and the mode is `0o700` by construction.
        with _isolating(f"cannot create an ephemeral worktree directory under {reserved}"):
            if path is None:
                worktree = Path(tempfile.mkdtemp(prefix=f"{WORKTREE_PREFIX}{token}-"))
            else:
                worktree = path
                os.mkdir(worktree, 0o700)
            try:
                scratch = Path(tempfile.mkdtemp(prefix=f".nox-{token}-", dir=worktree.parent))
            except OSError:
                # The worktree directory exists by now and the `try` below — which
                # owns the teardown — is never entered if this raises. `git worktree
                # prune` will not reap a directory that still exists, so without
                # this the failure strands one on the operator's disk for good.
                shutil.rmtree(worktree, ignore_errors=True)
                raise
        try:
            pin_refs(toplevel, token, synthetic_base, synthetic_target, resolved)
            _git(toplevel, "worktree", "add", "--detach", str(worktree), synthetic_target, env=resolved)
            diff_path = scratch / "review.diff"
            spec = f"{synthetic_base}..{synthetic_target}"
            # Redirected into the scratch file rather than captured and then
            # written, so the diff exists on disk and nowhere else until it has
            # been measured (E53). The open is `write_nofollow`'s own
            # `O_CREAT|O_EXCL|O_NOFOLLOW`, so C-1009 holds exactly as it did.
            _git(worktree, "diff", "--no-ext-diff", "--no-textconv", spec, env=resolved, stdout=diff_path)
            size = diff_path.stat().st_size
            if size > max_prompt_bytes:
                # Refused, never trimmed (C-1028): a reviewer handed a silently
                # shortened diff reports on a change nobody made, and the
                # anti-injection framing lives at the END of the prompt. The three
                # things an operator needs are all here — what was measured, what
                # it exceeded, and the key that moves the bound — and none of them
                # appears in `harness.argv_prompt`'s refusal, which is the kernel's
                # `MAX_ARG_STRLEN` and answers to no configuration (E29).
                raise ConfigError(
                    f"the diff is {size} bytes and the delivery bound is {max_prompt_bytes} "
                    "(`[review] max_prompt_bytes` in nox.toml). nox refuses rather than shortening it: "
                    "a reviewer shown part of a change reports on a change nobody made. Raise the key "
                    "from your user-level nox.toml, or review a narrower target."
                )
            verify(worktree, [*head_named, *(entry for entry, _, _ in head_filtered)])
            materialized = tuple(entry for _, _, entry in _ls_tree(toplevel, synthetic_target, resolved))
            omitted, ignored = untracked(toplevel, target, materialized, resolved)
            # `filtered_changed` differences on `(path, sha)`, never on the rendering:
            # two targets sharing a `SYMLINK_TARGET_BUDGET`-byte prefix render
            # identically, so a symmetric difference over renderings cancelled a
            # genuine change and made a C-1043(4) review approvable. The `matches`
            # exclusion is what keeps a branch editing its own `.codex` approvable.
            by_key = {(entry, sha): (entry, sha, rendered) for entry, sha, rendered in (*base_filtered, *head_filtered)}
            changed = {(entry, sha) for entry, sha, _ in head_filtered if not matches(entry)} ^ {
                (entry, sha) for entry, sha, _ in base_filtered if not matches(entry)
            }
            # Enumerated in full first, then capped: `*_total` is the honest count,
            # and `verify` above already ran against the whole drop list.
            all_neutralized = tuple(sorted({sanitize_path(entry) for entry in (*base_named, *head_named)}))
            all_filtered = _render((*base_filtered, *head_filtered))
            all_changed = _render(by_key[key] for key in changed)
            all_omitted = tuple(sorted(sanitize_path(entry) for entry in omitted))
            yield Workspace(
                path=worktree,
                token=token,
                base=synthetic_base,
                target=synthetic_target,
                scope="plan-artifact" if target.kind == "plan-artifact" else "code-diff",
                scratch=scratch,
                diff_path=diff_path,
                # Read back rather than kept from the capture: the bound above is
                # what makes this allocation safe to make at all.
                diff=diff_path.read_bytes().decode("utf-8", errors="replace"),
                env=MappingProxyType(dict(resolved)),
                neutralized=all_neutralized[:ENUMERATION_BUDGET],
                neutralized_total=len(all_neutralized),
                filtered=all_filtered[:ENUMERATION_BUDGET],
                filtered_total=len(all_filtered),
                filtered_changed=all_changed[:ENUMERATION_BUDGET],
                filtered_changed_total=len(all_changed),
                omitted=all_omitted[:ENUMERATION_BUDGET],
                omitted_total=len(all_omitted),
                omitted_ignored=ignored,
            )
        finally:
            # Every step runs independently and none of them may raise: a failing
            # `worktree remove` must not skip the ref deletions, and no teardown
            # failure may replace an exception raised by the body — a `verify`
            # failure is the loudest signal in the design. `check=False` covers a
            # non-zero exit, the `suppress` covers a git that cannot be spawned at
            # all. The `rmtree` is the backstop for the window where the directory
            # exists and the worktree is not registered yet.
            for step in (
                ("worktree", "remove", "--force", str(worktree)),
                ("update-ref", "-d", f"{REF_NAMESPACE}/{token}/base"),
                ("update-ref", "-d", f"{REF_NAMESPACE}/{token}/target"),
            ):
                with suppress(IsolationError):
                    _git(toplevel, *step, env=resolved, check=False)
            shutil.rmtree(worktree, ignore_errors=True)
            shutil.rmtree(scratch, ignore_errors=True)
    finally:
        _DEADLINE.reset(token_deadline)
