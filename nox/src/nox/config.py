"""Configuration, the minimal environment, and the trust gate (C-1016, C-1017, C-1008).

Two ideas live here and they are deliberately in one module, because both are
about *what a hostile repository is allowed to influence*.

**Config** is a normalized core plus an opaque passthrough (C-1016). Unknown
keys warn and are ignored; a malformed value on a key in `PERMISSION_KEYS`
raises — every possible default there would be a guess about a security
control (CWE-1188). The evaluation order is part of the contract (C-1017):
**drop untrusted permission keys first, then validate what survives**. The
reverse order reopens T6 — a hostile `read_only = "yes"` would raise before the
drop rule ever ran, and a review that never runs is a review that never
objects.

**The environment** is built once, before the probe (C-1008): an allowlist,
a credential-pattern denylist on top, a written-down never-forward literal
(C-1034) and an inbound-value rejection for the variables that point a harness
at its own config (T4b). nox never reads or forwards a credential (C-1002);
each harness authenticates from its own store.

Two deviations from the ADR's component block, both recorded rather than
silent:

- `GIT_CONFIG_OVERRIDES` and `GIT_PLAIN_ENV` live here, not in `workspace.py`
  where the ADR homes them. `minimal_env()` must emit them (SD step 0, C-1034(3))
  and the probe at step 3 runs before any worktree exists, so nothing in
  `workspace` could cover it — and a probe env that differs from the review env
  would split the C-1025 digest. `workspace.py` builds its default environment
  by calling `minimal_env()`, so there is one definition site.
- `ModelClass`, `ModelSpec` and `ModelSpecT` are re-exported here from
  `nox.capability`, which owns them under E9b: the ADR's component block
  declares them at this module's surface, and adapters read them from either
  home.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import pwd
import stat
import tomllib
from collections.abc import Container, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Final, TypeVar, cast, get_args

from nox.capability import Launcher, ModelClass, ModelSpec, ModelSpecT
from nox.outcome import NoxError

_T = TypeVar("_T")

__all__ = [
    "ALLOWLIST",
    "AUTH_ENV_HINTS",
    "AUTH_HINT_TRAILER",
    "CONFIG_NAME",
    "DEFAULT_MAX_PROMPT_BYTES",
    "DEFAULT_TIMEOUT_S",
    "DENY_PATTERNS",
    "GIT_CONFIG_OVERRIDES",
    "GIT_PLAIN_ENV",
    "INBOUND_PATH_VARS",
    "MAX_SEARCH_DEPTH",
    "MIN_TIMEOUT_S",
    "NEVER_FORWARD",
    "NEVER_FORWARD_GLOBS",
    "PERMISSION_KEYS",
    "REQUIRED_ENV",
    "TRUST_GATED_KEYS",
    "WORLD_WRITABLE_EXEMPT",
    "ConfigError",
    "HarnessConfig",
    "ModelClass",
    "ModelSpec",
    "ModelSpecT",
    "NoxConfig",
    "auth_hint",
    "is_trusted",
    "load",
    "matches_any",
    "minimal_env",
    "narrow_tools",
    "sanitize_path",
    "trust_store_path",
    "world_writable_forwards",
]


class ConfigError(NoxError):
    """A refused permission value, or an environment nox will not spawn under.

    Maps to `FailureReason.INVALID_CONFIG` in `nox.api.review()`, which is total
    (C-1029) — so every `ValueError` raised by the leaf vocabulary
    (`ModelSpecT.of`, `Launcher`) must be caught here and re-raised as this
    type rather than escaping the library.
    """


def _require(condition: bool, message: str) -> None:
    """Refuse with a `ConfigError` unless `condition` holds.

    Every hard refusal in this module funnels through one raise site, so
    `review()`'s totality (C-1029) is a property of a single line rather than of
    a dozen scattered `raise` statements staying in step with each other.

    Args:
        condition: What must hold.
        message: The refusal, naming the key or variable at fault.

    Raises:
        ConfigError: `condition` is false.
    """
    if not condition:
        raise ConfigError(message)


# ── Configuration ────────────────────────────────────────────────────────────

PERMISSION_KEYS: Final[frozenset[str]] = frozenset(
    {"read_only", "tools_allowed", "passthrough", "isolation", "launcher"}
)
"""The C-1016 permission surface: keys whose malformed value fails HARD.

A literal set, never a heuristic — the fail-soft/fail-hard asymmetry would
otherwise degrade into a judgment call at every new key. `model` is
deliberately absent: every possible default for it is a real model rather than
a guess about a control (C-1030 rule 5), so failing hard there would hand
`model = "garbage"` the same denial of service C-1017 closes.

Fixed at exactly five members by C-1016, which is why the *trust* drop is keyed
on the wider `TRUST_GATED_KEYS` rather than on this set.
"""

TRUST_GATED_KEYS: Final[frozenset[str]] = PERMISSION_KEYS | {"model_literal", "effort"}
"""The keys dropped from an untrusted file (C-1017 + C-1030 rule 5's second half).

C-1030 rule 5 makes a `[harness.<name>]` model literal droppable "exactly like
a permission key" without adding it to the C-1016 set, so the two sets are
genuinely different and each is named. `effort` joins the literal because it is
the same channel: it becomes an argv word (`--effort <level>`, OpenCode's
`--variant`), and splitting the ADR's single `ModelSpec` into two flat TOML
keys would otherwise leave half of it ungated.

Two keys are deliberately **out**, and the omissions are recorded here so
neither reads as an oversight:

- `model` — the capability *class* — stays freely settable from any file,
  because a closed two-member `Literal` cannot express anything worse than a
  warning (C-1030 rule 5). The class is mapped to a literal by the adapter's
  own `MODELS` table, so a repository can at worst ask for the other shipped
  class.
- `[review] harness` picks *which* adversary runs, and every candidate is a
  registry key of a harness nox already ships an adapter for. A repository
  steering its own review to a different shipped harness changes who reviews,
  never what that reviewer is allowed to do — and gating it would break the
  ordinary case of a repository declaring the harness it is reviewed under.
"""

MAX_SEARCH_DEPTH: Final[int] = 20
"""Upward-search bound for `nox.toml` (C-1017). Arbitrary, not measured."""

CONFIG_NAME: Final[str] = "nox.toml"
"""The file name searched for, both user-level and repo-local."""

DEFAULT_TIMEOUT_S: Final[int] = 900
"""Wall-clock default, and the fallback for an out-of-domain `timeout`."""

DEFAULT_MAX_PROMPT_BYTES: Final[int] = 96 << 20
"""Default ceiling on the diff nox will deliver to a reviewer, in bytes (E53).

**Derived from a measurement, not chosen.** The diff rides the prompt on every
shipped harness (E29) and the prompt is built in memory, so peak resident set
is a multiple of the diff rather than a constant. Measured on this tree, worst
case — 32 MiB of non-ASCII diff through `prompt.render` and the prompt write,
where `_fence`'s `str.isascii()` fast path does not fire and its `str.translate`
copy is real — peak RSS was **281.8 MB against 33.55 MB of diff: 8.40x**. The
ASCII legs run 7.2-7.7x raw at 8-128 MiB and are not the bound.

The arithmetic, so a later edit is traceable rather than a matter of taste:

    a 1 GiB peak-RSS budget / 8.40x measured  =  127.9 MiB
    rounded down to a round figure            =   96 MiB   (peak ~806 MB)

The margin between 96 and 128 MiB is what the measurement being from one
machine, one interpreter and one diff shape is worth; it is not a second
safety factor applied to a first one.

Two things this is NOT. It is not a truncation point — C-1028 forbids
shortening the evidence, so a diff past this is refused whole (`ConfigError`,
`INVALID_CONFIG`) and the operator is told the knob. And it is not the argv
ceiling: `harness.PROMPT_ARGV_LIMIT` is the kernel's `MAX_ARG_STRLEN`, three
orders of magnitude smaller, binds only the two argv-channel harnesses, and
answers to no configuration at all.
"""

MIN_TIMEOUT_S: Final[int] = 60
"""Floor a configured `timeout` is **clamped** to, never refused for (T6).

`timeout = 1` is inside the key's domain, so fail-soft never fires, and it
denies every review of the branch that ships it — the T6 shape arriving through
the one key the C-1017 drop rule deliberately does not cover. Clamping rather
than raising keeps a legitimate repo-local *raise* working and keeps a hostile
lowering harmless; a refusal here would hand the same one-character denial of
service back.

One minute, because it is the smallest wall clock under which a real harness
startup plus a first model turn has ever been observed to finish — arbitrary at
the second, deliberate at the order of magnitude.
"""

_MAX_CONFIG_BYTES: Final[int] = 1 << 20
"""Read cap for a config file. Generous by four orders of magnitude for TOML,
and the bound between `nox.toml` being a symlink to `/dev/zero` and an OOM."""

_MAX_NAME_CHARS: Final[int] = 64
"""Cap on any attacker-authored name interpolated into a message (C-1035(1))."""

_MODEL_CLASSES: Final[tuple[str, ...]] = get_args(ModelClass)
"""The recognized capability classes, read off the `Literal` rather than restated."""

_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset({"harness", "review"})
"""The tables `nox.toml` defines at its top level."""

_REVIEW_KEYS: Final[frozenset[str]] = frozenset({"harness", "max_prompt_bytes"})
"""The keys `[review]` defines."""

_GATED_REVIEW_KEYS: Final[frozenset[str]] = frozenset({"max_prompt_bytes"})
"""The `[review]` keys an untrusted file may not supply — the C-1017 drop, second table.

`TRUST_GATED_KEYS` is a `[harness.<name>]` set and stays one; this is the
sibling for the other table, so neither has to describe keys it does not own.

`max_prompt_bytes` is here and `harness` is not, and the difference is what the
key can express. `harness` picks which shipped adversary runs — a repository
steering its own review to another harness nox already ships an adapter for.
`max_prompt_bytes` is a memory bound, and a branch-authored one is hostile in
BOTH directions: lowered, it denies the review of the branch that ships it (T6);
raised, it re-opens exactly the allocation the bound was measured to close.
Dropping it closes both with the mechanism already here, and leaves the key
fully settable from the user-level file, which is the one that is trusted.
"""

_HARNESS_KEYS: Final[frozenset[str]] = TRUST_GATED_KEYS | {"model", "timeout"}
"""The keys `[harness.<name>]` defines — derived, so a new gated key is known here too."""


def _safe_name(name: str) -> str:
    """A TOML-authored name, made safe to put in a message (C-1035(1)).

    A section or key name is as attacker-controlled as a value: `[harness.<name>]`
    is whatever the branch author typed, and both `Review.warnings` and
    `Review.detail` reach a terminal. A raw name therefore forges lines with a
    newline, repaints the screen with an escape sequence, and pads a 200 KB
    warning out of a 200 KB key. Every `{key}`/`{name}` interpolation in this
    module goes through here.

    Bounded by construction rather than after the fact. `islice` stops the
    filter at `_MAX_NAME_CHARS + 1` surviving characters — one more than the cap
    is all it takes to know the name was longer — so the 200 KB key this exists
    for costs 65 characters of work instead of 200 000, and never materializes
    the 200 KB string the old form built and then cut to 64 (a **100 000-character**
    name measured 1.82 ms and 878 KiB of transient allocation, against 0.002 ms
    and 1 KiB — a 980x wall and 815x memory ratio; CPython 3.14 on Linux). A cap applied only to the RESULT bounds the
    output and not the work, which is the shape `prompt._fence` and
    `workspace._sanitize` were each fixed for.

    The cap cannot move in front of the filter, only inside it: it counts the
    characters that SURVIVE, and one control character per printable one would
    halve an input-side cut. `test_a_name_is_cut_after_its_non_printables_are_dropped_and_never_before`
    pins both that and the `+ 1` boundary the ellipsis hangs on.

    Args:
        name: The authored name.

    Returns:
        Its printable characters, truncated to `_MAX_NAME_CHARS` with an
        ellipsis when it was longer.
    """
    printable = "".join(islice((character for character in name if character.isprintable()), _MAX_NAME_CHARS + 1))
    if len(printable) <= _MAX_NAME_CHARS:
        return printable
    return f"{printable[:_MAX_NAME_CHARS]}…"


def _soft(key: str, value: _T, ok: bool, fallback: _T, warnings: list[str]) -> _T:
    """Keep `value` when `ok`, else warn and take `fallback` (C-1016 fail-soft).

    The counterpart of `_require`, for every key outside `PERMISSION_KEYS`: an
    out-of-domain value there says nothing about the enforced boundary, and
    failing hard would hand a one-character edit the same denial of service
    C-1017 closes.

    Args:
        key: The key at fault, for the warning.
        value: The configured value.
        ok: Whether it is inside the key's domain.
        fallback: What stands in when it is not.
        warnings: Accumulator, appended to in place. Names only, never a value.

    Returns:
        `value`, or `fallback`.
    """
    if ok:
        return value
    warnings.append(f"{_safe_name(key)}: value outside its domain — ignored, using the default")
    return fallback


def _table(raw: object) -> dict[str, Any]:
    """A parsed TOML value read as a table; anything else, absent included, reads as empty.

    The one place a malformed *shape* is absorbed rather than diagnosed: a
    `harness = 3` cannot supply keys, so it supplies none. Returns the very
    object it was handed when that object is a table, which is what lets
    `_drop_gated` delete through it.

    Args:
        raw: The parsed value.

    Returns:
        The table, or `{}`.
    """
    return cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}


def _positive_int(value: object) -> bool:
    """Whether `value` is a positive `int` that is not a `bool`.

    `isinstance(True, int)` holds in Python, so a TOML `timeout = true` would
    otherwise read as a one-second wall clock.

    Args:
        value: The parsed value.

    Returns:
        Whether it is inside `timeout`'s domain.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _words(key: str, raw: Any) -> tuple[str, ...] | None:
    """A permission key's argv-word list: a TOML array of strings, or `None` when absent.

    Args:
        key: The key, for the refusal message.
        raw: The parsed value.

    Returns:
        The words, or `None` when the key was not supplied.

    Raises:
        ConfigError: The value is neither absent nor an array of strings. This
            is a `PERMISSION_KEYS` member, where every possible default would be
            a guess about a security control (CWE-1188).
    """
    _require(raw is None or _is_word_list(raw), f"{_safe_name(key)}: expected an array of strings")
    return None if raw is None else tuple(raw)


def _is_word_list(raw: Any) -> bool:
    """Whether `raw` is a TOML array whose every element is a string.

    Args:
        raw: The parsed value.

    Returns:
        Whether it is a list of strings.
    """
    return isinstance(raw, list) and all(isinstance(word, str) for word in cast("list[object]", raw))


def _warn_unknown(scope: str, table: Mapping[str, Any], known: Container[str], warnings: list[str]) -> None:
    """Warn once per key `scope` does not define (C-1016 fail-soft).

    An unknown key is a forward-compatibility signal that changes nothing about
    the enforced boundary, so it never raises — not even in the trusted
    user-level file, because fail-soft is a property of the key rather than of
    the file's trust.

    Args:
        scope: The section name, for the warning.
        table: The parsed section.
        known: The keys `scope` defines.
        warnings: Accumulator, appended to in place.
    """
    for key in sorted(table):
        if key not in known:
            warnings.append(f"{_safe_name(key)}: unknown key in {scope} — ignored")


def _warn(warnings: list[str] | None, message: str) -> None:
    """Append `message` when the caller offered an accumulator.

    `trust_store_path` is public and has no warnings channel, so the two
    environment guards below are shared by a caller that can report and one that
    cannot; the guard itself must not depend on which.

    Args:
        warnings: Accumulator, or `None`.
        message: The warning. Names only, never a value or a path.
    """
    if warnings is not None:
        warnings.append(message)


def _inside_repo(value: str, repo: Path | None) -> bool:
    """Whether `value` resolves at, or inside, the repository under review.

    Args:
        value: A filesystem path as a string.
        repo: The repository under review, or `None` when the caller does not
            know it — in which case nothing is inside it.

    Returns:
        Whether the value is repository-controlled.
    """
    return repo is not None and _inside(value, (repo.resolve(),))


def _passwd_home() -> Path:
    """The home directory from the passwd database — the one `$HOME` cannot steer.

    `Path.home()` and `expanduser` read `$HOME` first, so both are steerable by
    exactly the attacker this fallback exists to escape (T4b: `mise.toml [env]`
    is declarative and needs no code execution).

    Returns:
        The uid's home directory.

    Raises:
        ConfigError: This uid has no passwd entry (`docker run -u 1234`), so
            there is no home to fall back to. A `NoxError`, because
            `Path.home()`'s own `RuntimeError` is not one and `review()` is
            total (C-1029).
    """
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError as exc:
        raise ConfigError(
            "no usable home directory: $HOME is unset or repository-controlled and this uid has no passwd entry"
        ) from exc


def _home(repo: Path | None, warnings: list[str] | None) -> Path:
    """The user's home directory, refusing a repository-controlled `$HOME` (T4b).

    Args:
        repo: The repository under review.
        warnings: Accumulator, or `None`.

    Returns:
        `$HOME`, or the passwd-database home when `$HOME` is unset, empty or
        resolves inside the repository.

    Raises:
        ConfigError: The fallback has no passwd entry to read.
    """
    home = os.environ.get("HOME")
    if home and not _inside_repo(home, repo):
        return Path(home)
    if home:
        _warn(warnings, "HOME: resolves inside the repository under review — ignored (T4b)")
    return _passwd_home()


def _xdg(explicit: Path | None, variable: str, repo: Path | None, warnings: list[str] | None, *fallback: str) -> Path:
    """A nox directory: the caller's override, else `$<variable>/nox`, else `~/<fallback>`.

    One helper for both XDG roots, so the config directory and the state
    directory cannot drift into different resolution rules.

    **The environment is not trusted to name it.** T4b's premise is that the
    branch author sets these variables — declaratively, through `mise.toml
    [env]` or `.envrc`, in the user's own shell, before nox is ever invoked. An
    `XDG_CONFIG_HOME` inside the repository would make a branch-authored file
    *the trusted user file* and hand every `TRUST_GATED_KEYS` member, `launcher`
    included, to whoever wrote the branch; an `XDG_STATE_HOME` inside it does
    the same one hop further out, through a branch-authored `trust.json`. Both
    fall back to the passwd-database home instead.

    **And containment is a property of the answer, not of the channel it
    arrived on.** The override is checked by the same rule for the same reason:
    a `state_dir` inside the tree under review buys precisely the `trust.json`
    the paragraph above refuses to derive from the environment, and the branch
    wrote both files, so the C-1017 digest matches by construction. Checking it
    here rather than at each call site is what keeps every consumer on one rule
    — `is_trusted`'s belt covers `user_config` alone, so a per-caller guard
    would have left the store, which is the half that pays, and `log.py`'s
    `call_log_path` derives from this helper too.

    Args:
        explicit: The caller's override, which wins unless it too resolves
            inside `repo`.
        variable: The XDG environment variable to consult.
        repo: The repository under review, whose own subtree may not name a nox
            directory. `None` when the caller does not know it.
        warnings: Accumulator, or `None`.
        *fallback: Path components under `~` when the variable is unset, empty
            or repository-controlled.

    Returns:
        The directory, which need not exist.

    Raises:
        ConfigError: The fallback is needed and this uid has no passwd entry.
    """
    if explicit is not None:
        if not _inside_repo(str(explicit), repo):
            return explicit
        _warn(warnings, f"the {variable} override resolves inside the repository under review — ignored (T4b)")
    root = os.environ.get(variable)
    if root and not _inside_repo(root, repo):
        return Path(root) / "nox"
    if root:
        _warn(warnings, f"{variable}: resolves inside the repository under review — ignored (T4b)")
    return _home(repo, warnings).joinpath(*fallback)


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    """Per-harness settings — the C-1016 normalized core plus the opaque passthrough.

    Every field is per-harness (`[harness.<name>]` in `nox.toml`); there is no
    top-level default section, so a wrong-harness value is unrepresentable
    rather than caught by a check.

    `isolation` is a `nox.toml` key (it is in `PERMISSION_KEYS`, so a repository
    cannot supply it and a trusted file supplying anything but `"worktree"`
    raises) but deliberately **not** a field: v1 has one value and nothing reads
    it, and a stored value no branch consults is a control nothing enforces.
    Option D reopens the key, and re-adding the field then is a smaller change
    than a year of it lying around unread.

    Attributes:
        model: A capability *class*, never a literal ID (C-1030, adr_0001
            C-001). `None` takes the harness default. An unrecognized class
            warns and falls back here — never a `ConfigError`.
        model_literal: A harness-local literal overriding the adapter's shipped
            `MODELS` entry. Accepted only in that harness's own section, and in
            `TRUST_GATED_KEYS` so an untrusted repo-local file cannot steer the
            review to a model of the branch author's choosing. Rejected outright
            when it starts with `-` or carries whitespace: that can only be an
            attempt to smuggle argv through a value slot.
        effort: The reasoning-effort level to pair with `model_literal`, for
            harnesses that have one. Same argv-word rules, same trust gate.
        read_only: v1's domain is `{True}`. `False` raises, naming C-1003 and
            C-1007 — there is no in-tree mode to fall back to, so accepting it
            would mean either refusing every launch or silently ignoring it.
        timeout: Wall-clock bound in seconds; the domain is the positive ints.
            Not a permission key, so a value outside it warns and falls back to
            `DEFAULT_TIMEOUT_S` (C-1016 fail-soft). That fallback is the bound
            `TimeoutPolicy.for_kind` does not carry: a TOML `-1` is a
            well-typed int, and this is the only gate between it and a
            supervisor whose wall clock has already elapsed.
        tools_allowed: May only *narrow* the adapter's own containment set
            (C-1016) — see `narrow_tools`, which the adapter calls with its set.
        launcher: Argv words that must *precede* the harness binary — the
            prefix only, since the binary is the adapter's to name (D-s:
            `["ocx", "package", "exec", "<pkg>", "--"]`, with `opencode`
            following the `--`). Use `launcher_for` to pair it with a binary.
        passthrough: Verbatim per-harness argv. The highest-risk field in the
            design; policed by WP6's per-adapter allowlist (C-1023), never here.
    """

    model: ModelClass | None = None
    model_literal: str | None = None
    effort: str | None = None
    read_only: bool = True
    timeout: int = DEFAULT_TIMEOUT_S
    tools_allowed: tuple[str, ...] | None = None
    launcher: tuple[str, ...] | None = None
    passthrough: tuple[str, ...] = ()

    def launcher_for(self, binary: str) -> Launcher | None:
        """Pair this config's launcher prefix with the adapter's own binary name.

        The ADR types the field as `Launcher`, but a `Launcher` carries the
        binary and `nox.toml` cannot: the configured value is the prefix, and
        which executable follows the `--` is the adapter's fact, not the
        repository's. This is the one line that reconciles the two.

        Args:
            binary: The executable the adapter spawns.

        Returns:
            A `Launcher` over this config's prefix, or `None` when no launcher
            is configured.

        Raises:
            ConfigError: The prefix or `binary` carries an empty argv word —
                `Launcher.__post_init__`'s `ValueError`, mapped, because
                `review()` is total (C-1029).
        """
        if self.launcher is None:
            return None
        try:
            return Launcher(binary=binary, prefix=self.launcher)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

    def model_spec(self) -> ModelSpecT | None:
        """Return the configured literal override as a typed spec, if any.

        Returns:
            `ModelSpecT(model_literal, effort)`, or `None` when no literal is
            configured — in which case the adapter's shipped `MODELS` answers.

        Raises:
            ConfigError: The literal or effort is not a usable argv word. The
                guard lives in `ModelSpecT.__post_init__` and raises a bare
                `ValueError`; mapping it here is what keeps `review()` total.
        """
        if self.model_literal is None:
            return None
        try:
            return ModelSpecT(model=self.model_literal, effort=self.effort)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class NoxConfig:
    """The whole of `nox.toml`, after the trust drop and validation (D-u/E10).

    Attributes:
        review_harness: `[review] harness` — the adversary to run when the
            caller passes no `--harness`. There is no shipped default: an
            absent value on both routes is `INVALID_CONFIG` (C-1042 item 5),
            because the explicit cross-model choice *is* the product claim.
        harnesses: `[harness.<name>]` sections, keyed by `ADAPTERS` registry
            key. A key with no section resolves to the field defaults. Wrapped
            in a `MappingProxyType` so `frozen=True` is not undone by a live
            handle to the underlying dict.
        max_prompt_bytes: `[review] max_prompt_bytes` — the ceiling on the diff
            nox will deliver, in bytes. Defaults to
            `DEFAULT_MAX_PROMPT_BYTES`, whose docstring carries the arithmetic.
            Trust-gated (`_GATED_REVIEW_KEYS`), unlike its neighbour.
    """

    review_harness: str | None = None
    max_prompt_bytes: int = DEFAULT_MAX_PROMPT_BYTES
    harnesses: Mapping[str, HarnessConfig] = field(default_factory=lambda: MappingProxyType({}))

    def for_harness(self, name: str) -> HarnessConfig:
        """Return the section for `name`, or the shipped defaults when absent.

        Args:
            name: An `ADAPTERS` registry key.

        Returns:
            The configured section, else a default `HarnessConfig`.
        """
        return self.harnesses.get(name, HarnessConfig())


def trust_store_path(state_dir: Path | None = None, *, repo: Path | None = None) -> Path:
    """Where the trust store lives: `<state dir>/trust.json` (C-1017).

    A JSON object mapping a resolved config path to the sha256 of the content
    that was trusted, so any edit invalidates the entry — mise's paranoid model,
    whose necessity is evidenced by a real bypass advisory (GHSA-436v-8fw5-4mj8),
    and deliberately the opposite of Codex's path-scoped project trust.

    **Nothing in v1 writes it** (D-w): there is no trust-granting command, so
    the file is normally absent and `is_trusted` answers from the user-level
    file alone. It is read rather than ignored because that is what makes
    `nox trust <path>` a later *addition* rather than a later mechanism.

    Args:
        state_dir: Override for the user state directory. Defaults to
            `$XDG_STATE_HOME/nox`, else `~/.local/state/nox`. Refused, like the
            variable, when it resolves inside `repo`.
        repo: The repository under review, whose own subtree may not supply the
            store — a branch-authored one grants a branch-authored `nox.toml`
            every trust-gated key (T4b), and neither the environment nor the
            override argument is a way in. `None` when the caller does not know it.

    Returns:
        The store path, which need not exist.

    Raises:
        ConfigError: The environment or the override named a repository-controlled
            directory and this uid has no passwd entry to fall back to.
    """
    return _xdg(state_dir, "XDG_STATE_HOME", repo, None, ".local", "state", "nox") / "trust.json"


def is_trusted(
    path: Path,
    digest: str,
    *,
    user_config: Path,
    state_dir: Path | None = None,
    repo: Path | None = None,
) -> bool:
    """Whether `path`, whose content hashes to `digest`, may supply `TRUST_GATED_KEYS`.

    Two ways to be trusted, and no third in v1:

    1. `path` **is** the user-level `nox.toml`. The user authored it in their
       own config directory; requiring them to bless it separately would make
       D-s's launcher unusable out of the box.
    2. The trust store carries `path` with exactly this `digest`. No v1 code
       path writes such an entry (D-w), so in practice this is how a repo-local
       file *fails*: the drop is unconditional and the tests assert it.

    `digest` is not decorative. C-1017 keys trust on path **and** content, so
    the caller hashes the bytes it parsed — the same bytes, from one read — and
    hands them here. That is the whole of the no-TOCTOU rule: there is no
    stat-then-reopen anywhere on the path from file to decision.

    Route 1 carries one refusal of its own: a `user_config` that resolves inside
    the repository is not the user's file at all, however it was derived. `_xdg`
    already refuses to derive one there, and this is the belt over that brace —
    the argument arrives from a caller, and a trusted file inside the tree under
    review is the whole of T4b.

    Args:
        path: The resolved config file path.
        digest: Lowercase sha256, in hexadecimal, of the bytes that were parsed.
        user_config: The resolved user-level `nox.toml` path.
        state_dir: Override for the trust store's directory.
        repo: The repository under review. `None` when the caller does not know
            it, in which case no path is repository-controlled.

    Returns:
        Whether the file may supply trust-gated keys.

    Raises:
        ConfigError: `$XDG_STATE_HOME` is repository-controlled and this uid has
            no passwd entry to fall back to. Nothing else here raises: an absent
            store is the normal case (D-w), and a corrupt, unreadable or
            nesting-bomb store must not deny every review — the fail-closed
            answer to all three is the same word, "no". `RecursionError` is
            named because `json.loads` raises it, and it is a `RuntimeError`
            that neither of the other two clauses would catch.
    """
    if path == user_config:
        return not _inside_repo(str(user_config), repo)
    try:
        store = json.loads(trust_store_path(state_dir, repo=repo).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return False
    return _table(store).get(str(path)) == digest


def _device_of(path: Path) -> int:
    """The filesystem device `path` lives on — the upward search's boundary (C-1017).

    A module-private seam rather than an inline `stat().st_dev`: a unit test
    cannot mount a second filesystem, and the alternative to the seam is a
    contract clause with no test at all.

    Args:
        path: An existing directory.

    Returns:
        Its `st_dev`.
    """
    return path.stat().st_dev


def _read_bytes(path: Path) -> bytes | None:
    """Read a config file's bytes once, refusing anything that is not a plain file.

    git stores symlinks, so `ln -s /dev/zero nox.toml` is committable: a
    `read_bytes` follows it and reads until the machine is out of memory, and
    `/dev/random` or a FIFO simply never returns. Hence three guards on one
    descriptor — `O_NOFOLLOW` (nothing may be substituted between the caller's
    `resolve()` and this open), `O_NONBLOCK` (opening a FIFO with no writer must
    not block), and `S_ISREG` on the *descriptor* rather than a second stat of
    the name.

    A module-private seam like `_device_of`: it is the one read of the file, so
    it is where a test proves the digest and the parse cannot come from two.

    Args:
        path: The candidate config file, already resolved.

    Returns:
        The bytes, or `None` when the name is absent or is not a plain file — a
        directory called `nox.toml`
        ([uv#7351](https://github.com/astral-sh/uv/issues/7351)), a device or a
        FIFO. None of those is an error; none of them is configuration either.

    Raises:
        OSError: The file is there and could not be read.
        ValueError: It is larger than `_MAX_CONFIG_BYTES`. Refused rather than
            truncated: a truncated parse is a config the user did not write.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        # `closefd=False`: the `finally` below owns the descriptor, and a
        # `FileIO` that refuses a directory does *not* close the one it was
        # handed. One owner, one close, no leak on the refusal path.
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            data = handle.read(_MAX_CONFIG_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(data) > _MAX_CONFIG_BYTES:
        raise ValueError(f"a {CONFIG_NAME} larger than {_MAX_CONFIG_BYTES} bytes is not configuration")
    return data


def _read_config(path: Path) -> tuple[str, dict[str, Any]] | None:
    """Read `path` once, and hash and parse *those* bytes (C-1017).

    One `_read_bytes`, and both the digest `is_trusted` keys on and the parsed
    table come out of it. A stat for the hash followed by a reopen for the parse
    is the whole of the race this closes.

    Args:
        path: The candidate config file, already resolved.

    Returns:
        `(lowercase sha256 of the bytes, parsed table)`, or `None` when the name
        is absent or is not a plain file.

    Raises:
        OSError: The file is there and could not be read.
        ValueError: The bytes are over the cap, are not UTF-8, or are not valid
            TOML — `tomllib.TOMLDecodeError` is a `ValueError`, so one clause
            catches them all and `review()` stays total.
        RecursionError: The TOML nests deeply enough to exhaust the parser's
            stack — a `RuntimeError`, caught by neither clause above, and
            reachable from a two-kilobyte file.
    """
    data = _read_bytes(path)
    if data is None:
        return None
    # `utf-8-sig`: a BOM is what every Windows editor writes, and a hard refusal
    # of the user's own file over three invisible bytes is not a security control.
    return hashlib.sha256(data).hexdigest(), tomllib.loads(data.decode("utf-8-sig"))


def _repo_layer(cwd: Path) -> tuple[Path, str, dict[str, Any]] | None:
    """The first `nox.toml` at or above `cwd`, already read (C-1017).

    Bounded by `MAX_SEARCH_DEPTH` and by an `st_dev` change. The filesystem root
    needs no bound of its own: `/`'s parent is `/`, so the depth count is what
    ends the walk there, and a separate root guard would be a branch no test on
    a machine with `/tmp` on its own device can ever reach.

    The candidate is **resolved before it is read**, not after: the path the
    trust decision is keyed on and the path the bytes came from must be one
    path. Reading `repo/nox.toml` and resolving it afterwards is two syscalls on
    the decision path, and a repo `nox.toml` symlinked into the user config
    directory resolves, after the fact, onto the one path `is_trusted` grants
    outright.

    Args:
        cwd: Where the search starts. An existing directory; the caller checks.

    Returns:
        `(resolved path, digest, parsed table)`, or `None` when no file is found
        inside the bounds.

    Raises:
        OSError: A found file could not be read.
        ValueError: A found file is over the size cap, is not decodable, or is
            not valid TOML.
        RecursionError: A found file nests deeply enough to exhaust the parser.
    """
    device = _device_of(cwd)
    current = cwd
    for _ in range(MAX_SEARCH_DEPTH):
        if _device_of(current) != device:
            return None
        candidate = (current / CONFIG_NAME).resolve()
        found = _read_config(candidate)
        if found is not None:
            return (candidate, *found)
        current = current.parent
    return None


def _drop_gated(table: Mapping[str, Any], warnings: list[str]) -> None:
    """Strip every `TRUST_GATED_KEYS` member an untrusted file may not supply (C-1017 step 2).

    Runs before any validation, which is the whole of the ordering contract: a
    hostile `read_only = "yes"` is removed here, so the fail-hard leg it would
    otherwise trip never sees it.

    Args:
        table: The parsed file, mutated in place.
        warnings: Accumulator, appended to in place. Key names, never values.
    """
    review = _table(table.get("review"))
    for key in sorted(_GATED_REVIEW_KEYS & set(review)):
        del review[key]
        warnings.append(f"{key}: dropped from [review] — an untrusted {CONFIG_NAME} may not supply it")
    for name, raw_section in _table(table.get("harness")).items():
        section = _table(raw_section)
        for key in sorted(TRUST_GATED_KEYS & set(section)):
            del section[key]
            # `read_only` is the one gated key with no trusted home: v1's domain is
            # `{True}` on BOTH tiers, so the shared wording read as "put it in the
            # user-level file" and sent the operator to a `_harness_config` refusal.
            reason = (
                f"v1 has no in-tree mode, and the user-level {CONFIG_NAME} cannot supply one either"
                if key == "read_only"
                else f"an untrusted {CONFIG_NAME} may not supply it"
            )
            warnings.append(f"{key}: dropped from [harness.{_safe_name(name)}] — {reason}")


def _harness_config(name: str, section: Mapping[str, Any], warnings: list[str]) -> HarnessConfig:
    """Validate one merged `[harness.<name>]` section — C-1017 step 3, after the drop.

    Everything still here either came from a trusted file or is not trust-gated,
    which is what makes the fail-hard legs below safe to reach: a repository's
    `read_only = "yes"` was deleted a step ago and cannot get to them. It is
    also why every refusal here is a `ConfigError` and none of them is a drop —
    including the two C-1030 adds, `launcher`'s empty argv word and an
    unusable `model_literal`/`effort`. The untrusted arm of "rejected wherever
    it is supplied" already ran, one step earlier.

    Args:
        name: The `ADAPTERS` registry key, for messages.
        section: The merged raw keys.
        warnings: Accumulator, appended to in place.

    Returns:
        The validated section.

    Raises:
        ConfigError: A malformed value on a `PERMISSION_KEYS` key, a `read_only`
            that is not `true`, an empty `launcher` word, or a `model_literal`
            or `effort` that is not a usable argv word.
    """
    scope = f"[harness.{_safe_name(name)}]"
    _warn_unknown(scope, section, _HARNESS_KEYS, warnings)
    _require(
        section.get("read_only", True) is True,
        f"{scope} read_only: v1's domain is true — C-1003 mandates the ephemeral worktree and C-1007 "
        f"holds the harness read-only inside it, so there is no in-tree mode to fall back to",
    )
    _require(
        section.get("isolation", "worktree") == "worktree",
        f'{scope} isolation: v1 knows only "worktree"',
    )
    model = section.get("model")
    literal = section.get("model_literal")
    effort = section.get("effort")
    launcher = _words("launcher", section.get("launcher"))
    _require(
        launcher is None or all(launcher),
        f"{scope} launcher: every argv word must be non-empty — an empty one reaches execve verbatim (C-1016)",
    )
    return HarnessConfig(
        model=_soft("model", model, model is None or model in _MODEL_CLASSES, None, warnings),
        model_literal=_argv_word(scope, "model_literal", literal, warnings),
        effort=_argv_word(scope, "effort", effort, warnings),
        timeout=_timeout(section.get("timeout", DEFAULT_TIMEOUT_S), warnings),
        tools_allowed=_words("tools_allowed", section.get("tools_allowed")),
        launcher=launcher,
        passthrough=_words("passthrough", section.get("passthrough")) or (),
    )


def _argv_word(scope: str, key: str, value: Any, warnings: list[str]) -> str | None:
    """Validate a `model_literal` or `effort` at **load**, not at first use (C-1030).

    `model_spec()` maps the same `ValueError`, but it is a method a caller has to
    remember: `.model_literal` is a public field, an adapter reads it straight
    into argv, and `HarnessConfig(model_literal="-c", effort="a b")` coming out
    of `load()` with no warning at all is the hole C-1030's "rejected wherever
    it is supplied" names. Only a trusted file reaches here, so the answer is a
    refusal rather than a drop.

    Args:
        scope: The sanitized section name, for the message.
        key: `"model_literal"` or `"effort"`.
        value: The parsed value.
        warnings: Accumulator, appended to in place.

    Returns:
        The value, or `None` when it is absent or not a string.

    Raises:
        ConfigError: It is a string that is not one safely spawnable, safely
            loggable argv word.
    """
    word = _soft(key, value, value is None or isinstance(value, str), None, warnings)
    if word is None:
        return None
    try:
        # `model` carries the word being checked; a lone `effort` still needs a
        # spec to sit in, and the placeholder never leaves this function.
        ModelSpecT(model=word if key == "model_literal" else "nox", effort=word if key == "effort" else None)
    except ValueError as exc:
        raise ConfigError(f"{scope} {exc}") from exc
    return word


def _timeout(value: Any, warnings: list[str]) -> int:
    """The wall clock: out-of-domain falls back, below the floor clamps (C-1016, T6).

    Clamping is the one place a value is silently corrected rather than dropped
    or refused, and it is deliberate: `timeout = 1` is a well-typed positive int
    that fail-soft never sees, and it denies every review of the branch shipping
    it. Refusing it would hand the same denial of service straight back, so the
    value is raised to the floor and the correction is stamped.

    Args:
        value: The parsed value.
        warnings: Accumulator, appended to in place.

    Returns:
        A wall clock of at least `MIN_TIMEOUT_S` seconds.
    """
    seconds = _soft("timeout", value, _positive_int(value), DEFAULT_TIMEOUT_S, warnings)
    if seconds >= MIN_TIMEOUT_S:
        return seconds
    warnings.append(f"timeout: below the {MIN_TIMEOUT_S}s floor — clamped, so a repository cannot deny its own review")
    return MIN_TIMEOUT_S


def load(
    cwd: Path,
    user_dir: Path | None = None,
    state_dir: Path | None = None,
) -> tuple[NoxConfig, tuple[str, ...]]:
    """Resolve configuration for a review starting at `cwd` (C-1016, C-1017).

    Two files, both optional: the user-level `nox.toml` (trusted; D-s puts the
    OpenCode launcher there) and the first `nox.toml` found searching upward
    from `cwd` — depth ≤ `MAX_SEARCH_DEPTH`, never crossing an `st_dev`
    boundary, tolerating the name being a directory
    ([uv#7351](https://github.com/astral-sh/uv/issues/7351)). The repo-local
    file's non-gated keys override the user-level ones; its trust-gated keys are
    dropped. The device check routes through a module-private `_device_of` so a
    test can force a boundary without mounting a second filesystem.

    **The order is the contract (C-1017):** resolve trust → drop every key in
    `TRUST_GATED_KEYS` the file is not trusted to supply, with a warning →
    validate only what survives. Validating first reopens T6 in full: a hostile
    `read_only = "yes"` would raise before the drop rule ever ran.

    **No hash/read TOCTOU:** each file is opened once, its bytes read once, and
    those same bytes are both hashed (for `is_trusted`) and parsed. Never a
    stat-then-reopen, and never a resolve after the read.

    **The environment does not get to say where the trusted file lives, and
    neither does the caller.** `$XDG_CONFIG_HOME`, `$XDG_STATE_HOME` and `$HOME`
    are all declaratively settable by the branch under review (T4b), and any of
    the three pointing inside `cwd` would make a branch-authored file the
    *trusted* one. Each is refused there and falls back to the passwd database,
    which `$HOME` cannot steer — and `_xdg` applies the same refusal to the two
    override arguments below, since which channel named the directory says
    nothing about where it lands.

    Args:
        cwd: Where the upward search starts — the repository under review.
            Resolved first, so a relative path cannot truncate the upward search
            at the process's own working directory.
        user_dir: Override for the user config directory. Defaults to
            `$XDG_CONFIG_HOME/nox`, else `~/.config/nox`. Refused, and warned
            about, when it resolves inside `cwd`.
        state_dir: Override for the user state directory holding the trust
            store. Defaults to `$XDG_STATE_HOME/nox`, else `~/.local/state/nox`.
            Refused inside `cwd` on the same rule.

    Returns:
        `(config, warnings)`. Warnings are the C-1035 config source: dropped
        trust-gated keys, unknown keys, unrecognized model classes,
        out-of-domain values. Never an environment value and never a path under
        `$HOME` outside the repository.

    Raises:
        ConfigError: A malformed value on a `PERMISSION_KEYS` key **in a trusted
            file** — there the user expressed an intent about the boundary that
            nox cannot read. Also `read_only = false` wherever it survives the
            drop, and unreadable or syntactically malformed TOML in the
            user-level file. A repo-local file that is unreadable or malformed
            TOML **warns and is ignored entirely**, never raises: T6 is a
            one-character denial of service against a repository's own review,
            and it is closed by the same fail-closed direction as the key drop.
            Also a `$HOME` that is unusable with no passwd entry to fall back to.
    """
    warnings: list[str] = []
    cwd = cwd.resolve()
    user_config = (_xdg(user_dir, "XDG_CONFIG_HOME", cwd, warnings, ".config", "nox") / CONFIG_NAME).resolve()
    try:
        user = _read_config(user_config)
    except (OSError, ValueError, RecursionError) as exc:
        # The exception's own text is not carried: it would put a path under
        # `$HOME` into `Review.detail`. `from exc` keeps the whole chain for a
        # traceback without publishing it.
        message = f"the user-level {CONFIG_NAME} is unreadable or not valid TOML ({type(exc).__name__})"
        raise ConfigError(message) from exc
    repo = None
    if not cwd.is_dir():
        # Distinct from the clause below on purpose: nothing was unreadable, the
        # search never started, and saying "unreadable TOML" would send the user
        # looking for a file that does not exist.
        warnings.append(f"the path under review is not an existing directory — no repository {CONFIG_NAME} was read")
    else:
        try:
            repo = _repo_layer(cwd)
        except (OSError, ValueError, RecursionError):
            # T6: a one-character edit in a branch must not deny the review of
            # that branch, so the repository's own file is ignored rather than
            # fatal — and that has to hold for *every* way a read can fail,
            # `RecursionError` out of a nested-array bomb included.
            warnings.append(f"the repository's {CONFIG_NAME} is unreadable or not valid TOML — ignored entirely")

    layers: list[tuple[Path, str, dict[str, Any]]] = []
    if user is not None:
        layers.append((user_config, *user))
    if repo is not None:
        layers.append(repo)

    review_raw: dict[str, Any] = {}
    harness_raw: dict[str, dict[str, Any]] = {}
    for path, digest, table in layers:
        _warn_unknown(CONFIG_NAME, table, _TOP_LEVEL_KEYS, warnings)
        if not is_trusted(path, digest, user_config=user_config, state_dir=state_dir, repo=cwd):
            _drop_gated(table, warnings)
        # Merged key by key rather than section by section, so a repo-local
        # `timeout` overrides the user's without emptying the launcher beside it.
        review_raw.update(_table(table.get("review")))
        for name, section in _table(table.get("harness")).items():
            if not isinstance(section, dict):
                # `[harness]\nread_only = false` names a scalar member, which
                # `_table` would read as an empty section: a phantom harness
                # with no keys and, until this line, no warning either.
                warnings.append(f"{_safe_name(name)}: not a table in [harness] — ignored")
                continue
            harness_raw.setdefault(name, {}).update(cast("dict[str, Any]", section))

    _warn_unknown("[review]", review_raw, _REVIEW_KEYS, warnings)
    harness = review_raw.get("harness")
    cap = review_raw.get("max_prompt_bytes", DEFAULT_MAX_PROMPT_BYTES)
    config = NoxConfig(
        review_harness=_soft("harness", harness, harness is None or isinstance(harness, str), None, warnings),
        # `not isinstance(cap, bool)`: TOML's `true` is a Python `int` by
        # inheritance, so `max_prompt_bytes = true` would otherwise read as a
        # one-byte ceiling and refuse every review.
        max_prompt_bytes=_soft(
            "max_prompt_bytes",
            cap,
            isinstance(cap, int) and not isinstance(cap, bool) and cap > 0,
            DEFAULT_MAX_PROMPT_BYTES,
            warnings,
        ),
        harnesses=MappingProxyType(
            {name: _harness_config(name, section, warnings) for name, section in harness_raw.items()}
        ),
    )
    return config, tuple(warnings)


def narrow_tools(requested: tuple[str, ...] | None, adapter_allowed: Iterable[str]) -> tuple[str, ...] | None:
    """Validate that a configured `tools_allowed` only narrows the adapter's set (C-1016).

    Any element outside the adapter's own containment set is a `ConfigError`, so
    config can never restore Bash on the tool-removal leg. Lives here rather
    than in the adapter because the rule is config's and the set is the
    adapter's.

    Args:
        requested: The configured value, or `None` for "the adapter's set".
        adapter_allowed: The adapter's own containment set.

    Returns:
        `requested` unchanged, or `None` when nothing was configured.

    Raises:
        ConfigError: An element is not already in `adapter_allowed`, naming it.
    """
    if requested is None:
        return None
    widened = sorted(set(requested) - set(adapter_allowed))
    _require(
        not widened,
        f"tools_allowed may only narrow the adapter's own set; not in it: "
        f"{', '.join(_safe_name(tool) for tool in widened)}",
    )
    return requested


# ── The minimal environment (C-1008, C-1034) ─────────────────────────────────

ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        # Infrastructure. A missing member of `REQUIRED_ENV` raises rather than
        # degrading: dropping a credential fails safely, dropping infrastructure
        # fails confusingly, and users answer confusing failures by turning
        # scrubbing off entirely.
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "TERM",
        "LANG",
        "LC_ALL",
        # `LC_CTYPE` outranks `LANG` in the POSIX precedence, so a user who sets
        # only it would otherwise get a non-UTF-8 child and a mojibake diff.
        # Named by codex's and opencode's own shipped code (E48).
        "LC_CTYPE",
        "TMPDIR",
        # Proxy set, both cases — curl and Node disagree about which they read.
        # `ALL_PROXY`/`all_proxy` are the last arm of Claude Code's own
        # resolution chain, `HTTPS_PROXY || https_proxy || ALL_PROXY` (E48).
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
        "all_proxy",
        # CA-bundle set. Forwarded because a corporate TLS-inspecting proxy is
        # the ordinary case, and guarded by `INBOUND_PATH_VARS` like every other
        # trust input: the axis is *trust*, not execution — a branch-authored
        # PEM plus a proxy is a TLS session the harness terminates against the
        # attacker while authenticating as itself.
        #
        # This set is kept on NAMED CAUSE, deliberately not on measurement (E48).
        # Every other widening here was settled by checking whether a shipped
        # harness reads the name; that check cannot settle these, because the
        # condition they exist for — a TLS-inspecting corporate proxy — is one no
        # developer machine with the stock trust store can produce. A measurement
        # taken where the breaking condition is unreachable returns "no cause"
        # for a cause that is real, and deleting on it would leave nox unusable
        # exactly where these names are load-bearing.
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "NODE_EXTRA_CA_CERTS",
        # XDG and the per-harness config roots. Forwarded because auth needs
        # them, and exactly why `INBOUND_PATH_VARS` exists: each one points a
        # harness at a directory whose contents it will read, trust or execute.
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_SECURESTORAGE_CONFIG_DIR",
        "CODEX_HOME",
    }
)
"""Everything forwarded to a child. Everything else is dropped (C-1008).

An allowlist, so its security value is what it excludes *by construction*, and
every widening past C-1008's enumerated set is recorded here rather than left
to be re-derived:

- `LC_CTYPE` joins the locale set. It outranks `LANG` in the POSIX precedence,
  so a user who sets only it would otherwise hand the reviewer a non-UTF-8
  child and a mojibake diff — and codex's and opencode's own shipped code name
  it, which is what earns it (E48). `TZ` was recorded here beside it and is
  **gone**: no shipped harness reads it, and its absence changes how a
  timestamp renders, never whether a review runs.
- The `ALL_PROXY`/`all_proxy` pair is past C-1008's proxy enumeration because
  it is the last arm of Claude Code's own chain,
  `HTTPS_PROXY || https_proxy || ALL_PROXY` — read out of the shipped 2.1.260
  bundle, not inferred from the name (E48).
- `SSL_CERT_DIR` and `CURL_CA_BUNDLE` are the two members of the CA-bundle set
  that no shipped harness was observed to read, and they are kept anyway, on
  **named cause rather than measurement** (E48). The measurement every other
  widening here passed cannot be run for these: it asks whether a harness reads
  the name, and the only environment in which one does — behind a TLS-inspecting
  proxy with a private CA — is one no ordinary developer machine can produce. A
  false negative from an unreachable condition is not evidence of no cause, and
  the failure it would ship is a harness that cannot complete a single request.
- `XDG_CACHE_HOME` is required by D-s's launcher route (`ocx package exec`
  resolves a pinned coordinate out of the cache); it is guarded by
  `INBOUND_PATH_VARS` like every other directory-valued member.
- `CLAUDE_SECURESTORAGE_CONFIG_DIR` points at Claude Code's credential store,
  and dropping it makes `auth status` report `loggedIn: false` — so every claude
  review refused `UNAUTHENTICATED` under the minimal environment while the
  harness was in fact logged in. Same class as the `OPENCODE_AUTH_JSON` row
  below and the reason both are recorded: an auth-adjacent variable's allowlist
  status is probed against the binary, never assumed from its name. The other
  two are probed and covered — codex reads its store under `$CODEX_HOME` and
  copilot under `$HOME/.copilot/`, and both roots are already here. It is
  deliberately NOT in `AUTH_ENV_HINTS`: that table names credential-shaped
  variables nox **dropped**, and every member must match a `DENY_PATTERNS`
  shape; this one is a directory nox now forwards, so there is nothing for an
  `UNAUTHENTICATED` detail to tell an operator about it.
- `OPENCODE_AUTH_JSON` was here and is **gone** (E19/D-ad): WP7c pinned the name
  against the real 1.18.22 binary and it does not exist. What that release reads
  is `OPENCODE_AUTH_CONTENT`, which carries the store INLINE rather than as a
  path — so it is a credential value, not a trust input, and it is in
  `NEVER_FORWARD` rather than here. OpenCode's own store is reached through
  `HOME`/`XDG_DATA_HOME`, both already forwarded, so nothing was lost.
- `SHELL` is deliberately **absent**: it names an executable, no v1 containment
  plan reads it, and a `.envrc` sourced in the user's own shell is exactly the
  T4b route that would set it to a path inside the branch.
- The Windows mandatory set CPython documents — `SystemRoot`, `SystemDrive`,
  `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `ComSpec`, `PATHEXT` — is inert
  under v1's POSIX-only scope (D-j/E6) and is recorded in this sentence rather
  than shipped as a constant no branch reads.
"""

REQUIRED_ENV: Final[frozenset[str]] = frozenset({"PATH", "HOME"})
"""Infrastructure whose absence from the built env raises, naming it (C-1008).

`HOME` is here as well as in `INBOUND_PATH_VARS`: a `HOME` that resolves inside
the repository under review is dropped by the inbound rule and then missing, so
the run refuses instead of proceeding with a repository-controlled home.
"""

DENY_PATTERNS: Final[tuple[str, ...]] = (
    "*_TOKEN",
    "*_KEY",
    "*_SECRET",
    "*_PASSWORD",
    "AWS_*",
    "GITHUB_*",
    "GH_*",
    "NPM_*",
    "PYPI_*",
    "OPENAI_*",
    "DATABASE_*",
    "ANTHROPIC_*",
    "*APIKEY",
    "*_CREDENTIALS",
    "*_PAT",
)
"""Credential shapes dropped even if they would otherwise pass (C-1008).

`fnmatch.fnmatchcase` semantics — see `matches_any`. Belt over the allowlist's
braces: the allowlist already excludes every one of these today, and this is
what keeps that true after the next "just add one more" edit. That is the whole
job, so the set is written wider than today's allowlist needs — `*APIKEY` is
the shape `AUTH_ENV_HINTS` already ships as a known OpenCode credential name,
and `ANTHROPIC_*` covers the two names `AUTH_ENV_HINTS` lists for `claude`
without relying on `*_KEY` and `*_TOKEN` to keep matching them.
"""

NEVER_FORWARD: Final[frozenset[str]] = frozenset(
    {
        "NODE_OPTIONS",
        "LD_PRELOAD",
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "DYLD_LIBRARY_PATH",
        "PYTHONSTARTUP",
        "PYTHONPATH",
        "GIT_SSH_COMMAND",
        "GIT_EXTERNAL_DIFF",
        "DYLD_FRAMEWORK_PATH",
        "DYLD_FALLBACK_LIBRARY_PATH",
        "DYLD_FALLBACK_FRAMEWORK_PATH",
        "DYLD_VERSIONED_LIBRARY_PATH",
        "DYLD_VERSIONED_FRAMEWORK_PATH",
        "GIT_SSH",
        "GIT_PROXY_COMMAND",
        "BASH_ENV",
        "ENV",
        "PYTHONHOME",
        "PERL5OPT",
        "RUBYOPT",
        "SSH_AUTH_SOCK",
        "OPENCODE_CONFIG",
        "OPENCODE_CONFIG_CONTENT",
        "OPENCODE_AUTH_CONTENT",
    }
)
"""The written-down exclusions, so they survive a future "add one more" (C-1034(1)).

Every member is already dropped by construction — none is on `ALLOWLIST` — and
a test asserts that disjointness. The set exists as the regression guard the
next edit is tested against, and because each member is an *execution* channel
rather than a credential: `NODE_OPTIONS --require` injects into any Node
harness (Claude Code and OpenCode both), `SSH_AUTH_SOCK` is load-bearing
against C-1007's `AF_UNIX` residual and must not come back as an ergonomics
fix, and `OPENCODE_CONFIG_CONTENT` carries a whole config inline.

`OPENCODE_AUTH_CONTENT` is the one member that is a credential rather than an
execution channel, and it is here for the sharper reason (E19/D-ad, C-1002): on
1.18.22 it carries OpenCode's whole credential store INLINE, so its *value* is
the secret. `DENY_PATTERNS` does not claim that name — it carries no `_TOKEN`,
`_KEY` or `_SECRET` shape — so without this entry the allowlist's braces would
be the only thing keeping it out, which is exactly the arrangement C-1034(1)
refuses. Its path-valued predecessor `OPENCODE_AUTH_JSON` does not exist in the
binary at all and is on neither list.
"""

NEVER_FORWARD_GLOBS: Final[tuple[str, ...]] = ("BUN_*",)
"""Patterned members of the same exclusion list (C-1034(1)). `fnmatchcase`."""

INBOUND_PATH_VARS: Final[frozenset[str]] = frozenset(
    {
        "HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_SECURESTORAGE_CONFIG_DIR",
        "CODEX_HOME",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "NODE_EXTRA_CA_CERTS",
    }
)
"""Variables refused when they resolve inside the repository or worktree (T4b).

The environment is an *inbound* channel, not only an outbound one. A hostile
branch's `.envrc` or `mise.toml` is sourced **in the user's own shell** when
they check the branch out to look at it — that is what direnv and mise are for
— so `CODEX_HOME=/tmp/x` can be set before nox is ever invoked, and Codex then
reads `/tmp/x/hooks.json` and `/tmp/x`'s trust store. Filtering these files out
of the worktree does nothing, because the export happened against the user's
real tree.

The membership rule is **trust, not execution**: every `ALLOWLIST` member whose
value names a path the harness reads, trusts, writes into or executes out of
belongs here. That is wider than "config root", and each widening past the
config roots is a reproduced attack rather than a precaution:

- The CA-bundle set (`SSL_CERT_FILE`, `SSL_CERT_DIR`, `REQUESTS_CA_BUNDLE`,
  `CURL_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`) is the strongest of them. A PEM
  committed to the branch plus a proxy is a TLS session the attacker terminates
  — and the harness crosses it authenticating as *itself*, so the user's own
  API key is what travels. A certificate is not an executable input; it is a
  trust input, which is the axis this set is actually about.
- `TMPDIR` is where a harness stages files it then reads back. A scratch
  directory inside the tree under review is a scratch directory the branch can
  rewrite between the write and the read.

The proxy set stays out, and stays on `ALLOWLIST`: C-1008 enumerates it, an
attacker-chosen proxy is an ADR-level residual rather than a path this rule can
judge, and refusing it would break every corporate network.

A test asserts this set is a subset of `ALLOWLIST`, rather than trusting the two
lists to be edited together.
"""

AUTH_ENV_HINTS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "claude": frozenset({"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}),
        "codex": frozenset({"OPENAI_API_KEY"}),
        "copilot": frozenset(),
        "opencode": frozenset({"OPENCODE_*_APIKEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN"}),
    }
)
"""Per-adapter credential-shaped variables worth naming on `UNAUTHENTICATED` (C-1034(4)).

An audited statement about the **four shipped harnesses**, not a table a fifth
adapter has to join: `auth_hint` reads it with `.get(harness, frozenset())`, so a
registered harness this map does not name simply contributes no names to the
detail. It stays a literal rather than a derivation over `ADAPTERS` because the
dependency runs the other way — `nox.config` ← `nox.harness` ← `nox.adapters` —
and importing the registry here would cycle. `copilot` is deliberately empty: C-1034(4)
names `GITHUB_TOKEN`/`GH_TOKEN` as candidates *and* says the entry stays empty
until a recorded fixture proves the shape, and the second clause is the
operative one — a guess in a security-adjacent message is worse than silence.
WP7d pins it from the real binary. Patterned entries use `fnmatchcase` like
every other pattern here.
"""

AUTH_HINT_TRAILER: Final[str] = (
    "nox never forwards credentials (C-1002); each harness authenticates from its own store."
)
"""The sentence every `UNAUTHENTICATED` detail ends with (C-1034(4))."""

GIT_CONFIG_OVERRIDES: Final[tuple[tuple[str, str], ...]] = (
    ("core.hooksPath", "/dev/null"),
    ("core.fsmonitor", "false"),
    ("core.attributesFile", "/dev/null"),
)
"""git config forced on every git in the child's process tree (C-1031).

Delivered as `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_<n>` / `GIT_CONFIG_VALUE_<n>`,
which binds a child-issued `git checkout` too — something a per-call
`-c core.hooksPath=…` never did. `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM`
are deliberately **not** nulled. Requires git ≥ 2.32 (C-1041): below 2.31 the
count variable is ignored *silently*, which is why `workspace()` probes the
version before it relies on this.

Homed here rather than in `workspace.py` (see the module docstring): the probe
runs before any worktree exists and must carry the same overrides, or the
C-1025 digest differs between probe and review.
"""

GIT_PLAIN_ENV: Final[Mapping[str, str]] = MappingProxyType(
    {
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "nox",
        "GIT_AUTHOR_EMAIL": "noreply@nox",
        "GIT_COMMITTER_NAME": "nox",
        "GIT_COMMITTER_EMAIL": "noreply@nox",
    }
)
"""git variables set outright rather than through the config count (C-1031, D-p).

The identity pair is what makes `commit-tree` independent of ambient config: an
unset identity fails every synthetic commit in a hermetic fixture.

`GIT_CONFIG_NOSYSTEM` is SET here rather than allowlisted, because the value
must be nox's and never the caller's. `ALLOWLIST` carries no `GIT_*` name, so a
system `/etc/gitconfig` would otherwise reach every git nox runs. The three
`GIT_CONFIG_OVERRIDES` keys outranking it is not sufficient: a system
`filter.<x>.smudge` bound through `$GIT_DIR/info/attributes` is a different key,
and it executes during `worktree add`. `GIT_ATTR_NOSYSTEM` beside it is the same
argument for the system attributes file.
"""


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    """Whether `name` matches any pattern, `fnmatch.fnmatchcase` semantics.

    Stated once and used by every patterned set here (`DENY_PATTERNS`,
    `NEVER_FORWARD_GLOBS`, `AUTH_ENV_HINTS`), so "how do these match" has one
    answer instead of three. Case-sensitive on purpose: environment names are,
    and a case-insensitive match would drop `path` alongside `PATH`.

    Args:
        name: The candidate name.
        patterns: Glob patterns.

    Returns:
        Whether any pattern matches.
    """
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


_INHERITED_GIT_GLOBS: Final[tuple[str, ...]] = (
    "GIT_ATTR_NOSYSTEM",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_KEY_*",
    "GIT_CONFIG_VALUE_*",
)
"""The inherited git names `minimal_env` drops at step 1 (C-1034(3)).

Named separately from step 2 even though none of them is on `ALLOWLIST` today:
these are the keys that decide whether a child-issued git runs a hook, and the
step exists so a future widening of the allowlist cannot quietly readmit them.
"""


def _inside(value: str, roots: tuple[Path, ...]) -> bool:
    """Whether `value` resolves at, or inside, any of `roots`.

    Resolved first: a symlink outside the tree pointing back into it is the same
    attack with one more hop.

    A value nox cannot resolve answers **yes**, which is the fail-closed
    direction: every caller reads this as "refuse it". `Path.resolve()` raises a
    bare `ValueError` on an embedded NUL — reachable through
    `minimal_env(environ=…)`, where the value is inherited — and that would
    otherwise escape `review()`'s `NoxError` catch entirely (C-1029).

    Args:
        value: A filesystem path as a string.
        roots: The trees under review, already resolved.

    Returns:
        Whether the resolved value is one of `roots` or below one, or could not
        be resolved at all.
    """
    try:
        resolved = Path(value).resolve()
    except (OSError, ValueError):
        return True
    return any(resolved == root or root in resolved.parents for root in roots)


def _forwardable_path_entry(entry: str, roots: tuple[Path, ...]) -> bool:
    """Whether one `PATH` entry may be forwarded (C-1034(2)).

    Args:
        entry: One `os.pathsep`-separated entry.
        roots: The trees under review.

    Returns:
        Whether it is non-empty, absolute, and resolves outside every root.
    """
    return bool(entry) and os.path.isabs(entry) and not _inside(entry, roots)


def sanitize_path(value: str, repo: Path, worktree: Path) -> str:
    """Rebuild a `PATH` value so no entry resolves inside the tree under review (C-1034(2)).

    Drops empty entries (which mean "the current directory" to most shells),
    non-absolute entries, and any entry whose `realpath` lies inside `repo` or
    `worktree` — each of which would let a branch supply the binary a harness
    resolves.

    Args:
        value: The inherited `PATH`.
        repo: The repository under review.
        worktree: The ephemeral worktree the harness runs in. It need not exist
            yet; only its resolved path is read.

    Returns:
        The surviving entries, `os.pathsep`-joined, order preserved.

    Raises:
        ConfigError: Every entry was dropped — naming `PATH`, per C-1008's
            missing-infrastructure rule.
    """
    roots = (repo.resolve(), worktree.resolve())
    kept = [entry for entry in value.split(os.pathsep) if _forwardable_path_entry(entry, roots)]
    _require(bool(kept), "PATH: every entry resolved inside the tree under review or was not usable (C-1008)")
    return os.pathsep.join(kept)


def _survives(name: str, value: str, roots: tuple[Path, ...]) -> bool:
    """Whether one inherited variable survives steps 1 to 4 of `minimal_env`.

    Args:
        name: The variable's name.
        value: Its inherited value, read only by the step-4 inbound check.
        roots: The repository and the reserved worktree path.

    Returns:
        Whether it is forwarded.
    """
    if matches_any(name, _INHERITED_GIT_GLOBS):  # step 1
        return False
    # Steps 2 and 3 share one leg deliberately. No `ALLOWLIST` member matches the
    # denylist today and a test asserts it, so a step-3 branch of its own would be
    # a branch nothing can reach; `_denied` is still evaluated for every name that
    # survives step 2, which is what makes it a belt rather than decoration.
    if name not in ALLOWLIST or _denied(name):
        return False
    if name not in INBOUND_PATH_VARS:
        return True
    # Step 4. Absoluteness is half the test, not a tidiness check: `_inside`
    # resolves against *nox's* working directory and the child's is the
    # worktree, so a relative `CODEX_HOME=planted` resolves outside the roots
    # here and is read from inside the worktree there.
    #
    # `/proc` is the absolute spelling of the same trick, and `_inside` cannot
    # see it: `/proc/self/cwd` resolves HERE to nox's own directory, which is
    # outside the roots, and THERE to the child's — the C-1003 worktree, which
    # is branch content. `/proc/<pid>/root` and `/proc/self/fd/<n>` are the same
    # indirection through a different name, so the whole tree is refused rather
    # than three paths under it.
    return os.path.isabs(value) and not _under_proc(value) and not _inside(value, roots)


def _under_proc(value: str) -> bool:
    """Whether a path reaches through `/proc`, whose links resolve per process.

    Args:
        value: An absolute inherited value.

    Returns:
        Whether `/proc` is its first component.
    """
    return PurePosixPath(value).parts[:2] == ("/", "proc")


def _denied(name: str) -> bool:
    """Step 3: a credential shape or an execution channel, dropped even if allowlisted.

    Args:
        name: The variable's name.

    Returns:
        Whether any of the three exclusion sets claims it.
    """
    return matches_any(name, DENY_PATTERNS) or name in NEVER_FORWARD or matches_any(name, NEVER_FORWARD_GLOBS)


def minimal_env(
    repo: Path,
    worktree: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Build the environment every child runs under, once, before the probe (C-1008).

    The probe is a real harness startup (C-1014) and must not see the ambient
    environment any more than the review does, so this is called **once** per
    `review()` and its result is reused — which is also what keeps C-1025's
    "hash of the C-1008 environment" digest factor identical between probe and
    review.

    That ordering is why `worktree` is a *reserved path*, not an existing
    directory: `review()` mints the worktree path before step 0 and hands the
    same value here and to `workspace()`. `sanitize_path` reads only the
    resolved string, so nothing has to exist yet.

    Order, and each step closes something the previous formulation did not:

    1. Inherited `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_<n>` /
       `GIT_CONFIG_VALUE_<n>` / `GIT_ATTR_NOSYSTEM` are dropped **first**
       (C-1034(3)) — they are the keys that decide whether a child-issued git
       runs a hook, so a parent-supplied value is an inbound channel of exactly
       the T4b shape.
    2. Only `ALLOWLIST` names survive.
    3. `DENY_PATTERNS`, `NEVER_FORWARD` and `NEVER_FORWARD_GLOBS` drop what
       remains, even if it was allowlisted.
    4. `INBOUND_PATH_VARS` that are not absolute, or that resolve inside `repo`
       or `worktree`, are dropped.
    5. `PATH` is rebuilt by `sanitize_path`.
    6. Every `REQUIRED_ENV` name still missing raises, naming it.
    7. nox's own C-1031 set — `GIT_CONFIG_OVERRIDES` as the count/key/value
       triple, plus `GIT_PLAIN_ENV` — is written **after** the drop, never
       forwarded.

    Args:
        repo: The repository under review.
        worktree: The reserved path of the ephemeral worktree.
        environ: The parent environment. Defaults to `os.environ`.

    Returns:
        `(env, dropped)`. `dropped` is the sorted **names** of every variable in
        `environ` whose inherited value did not survive — which includes the
        step-1 git names even though step 7 re-sets them under nox's own values,
        because the question `dropped` answers is "what did nox refuse to carry
        through", not "what is absent from the result". Names only, never
        values: it travels into an error detail (C-1034(4)) and must not be able
        to carry a secret.

    Raises:
        ConfigError: A `REQUIRED_ENV` variable is absent, empty or was dropped,
            or `PATH` sanitized down to nothing.
    """
    parent = os.environ if environ is None else environ
    roots = (repo.resolve(), worktree.resolve())
    env = {name: value for name, value in parent.items() if _survives(name, value, roots)}
    # Answered before step 7 writes nox's own git set, because the question is
    # "what did nox refuse to carry through", not "what is absent from the result".
    dropped = tuple(sorted(set(parent) - set(env)))
    if "PATH" in env:
        env["PATH"] = sanitize_path(env["PATH"], repo, worktree)
    # Presence is not usability: an empty `HOME` is forwarded by every step
    # above and expands `~` to `/` in the child.
    missing = sorted(name for name in REQUIRED_ENV if not env.get(name))
    _require(not missing, f"the minimal environment is missing required infrastructure (C-1008): {', '.join(missing)}")
    env.update(GIT_PLAIN_ENV)
    env["GIT_CONFIG_COUNT"] = str(len(GIT_CONFIG_OVERRIDES))
    for index, (key, value) in enumerate(GIT_CONFIG_OVERRIDES):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = value
    return env, dropped


WORLD_WRITABLE_EXEMPT: Final[frozenset[str]] = frozenset({"TMPDIR"})
"""`INBOUND_PATH_VARS` members the world-writable scan skips (C-1008 rule 2).

A shared scratch directory is world-writable *by design* — `/tmp` is 0o1777 on
every POSIX machine — so scanning `TMPDIR` warns on essentially every run, and a
warning that always fires is a channel that carries nothing. It keeps its
`INBOUND_PATH_VARS` membership, which is the half that pays: a `TMPDIR` inside
the tree under review is still refused outright.

The exemption is about the *shape* of the variable, not its mode: nothing is
read from `TMPDIR` by a name an attacker could pre-create, because the names in
it are minted by whoever writes them. That is not true of a config root, which
is why this set has exactly one member.
"""


def world_writable_forwards(env: Mapping[str, str]) -> tuple[str, ...]:
    """Warn about forwarded `INBOUND_PATH_VARS` under a world-writable directory (C-1008 rule 2).

    The inbound rule refuses a value resolving inside the repository outright; a
    value under a world-writable directory is *forwarded* — refusing it would
    break legitimate setups — but it is a directory any local user can plant a
    `hooks.json` in, so it is stamped loudly.

    "Under" is the whole rule, so the **ancestor chain** is walked and not just
    the leaf: `CODEX_HOME=/shared/cfg` with `/shared` world-writable and `cfg`
    itself 0755 is a directory another user can rename out from under, and
    inspecting one level warns about nothing.

    The sticky bit (`S_ISVTX`, which is what `/tmp` is) exempts an **ancestor**
    and never the directory the harness reads its configuration from. Sticky
    stops another user replacing or removing an entry that is not theirs; it
    does not stop them *creating* one, and a config file the harness would read
    is usually a file that does not exist yet.

    Scoped to `INBOUND_PATH_VARS` minus `WORLD_WRITABLE_EXEMPT`, and the warning names the
    variable and nothing else: the resolved directory is that variable's own
    forwarded value, and C-1035(1) puts no value in a warning (C-1035(1) is
    about `HOME` and `CODEX_HOME` exactly as much as about a token).

    Split from `minimal_env` rather than folded into it because C-1034 fixes
    that function's return as `(env, dropped)`, and `Review.warnings` is
    assembled in `nox.api` from five named sources (C-1035); this is one of
    them, and it reads the env `minimal_env` already built.

    Args:
        env: The built minimal environment.

    Returns:
        One warning per offending variable, naming the variable only.
    """
    return tuple(
        f"{name} resolves under a world-writable directory — "
        f"any local user on this machine can plant configuration there"
        for name in sorted((INBOUND_PATH_VARS - WORLD_WRITABLE_EXEMPT) & set(env))
        if _world_writable(env[name])
    )


def _mode_of(path: Path) -> int:
    """`path`'s mode bits, or `0` when it cannot be stat-ed.

    This feeds an advisory, and an advisory is the worst place to raise on a
    path the user simply has not created yet.

    Args:
        path: The candidate.

    Returns:
        `st_mode`, or `0`.
    """
    try:
        return path.stat().st_mode
    except OSError:
        return 0


def _world_writable(value: str) -> bool:
    """Whether `value` sits under a directory any local user can plant entries in.

    A value that names a file is judged by the directory holding it: a file in a
    world-writable directory is a file any local user can replace.

    Args:
        value: A forwarded `INBOUND_PATH_VARS` value.

    Returns:
        Whether the directory it is read from — or, sticky bit aside, any
        existing ancestor of that directory — is world-writable. A component
        that does not exist has no mode and contributes nothing, so the walk
        continues past it to the ones that do.
    """
    path = Path(value)
    directory = path if stat.S_ISDIR(_mode_of(path)) else path.parent
    # The directory itself gets no sticky exemption: sticky stops another user
    # replacing an entry that is not theirs, not creating one that is not there.
    if _mode_of(directory) & stat.S_IWOTH:
        return True
    for ancestor in directory.parents:
        mode = _mode_of(ancestor)
        if mode & stat.S_IWOTH and not mode & stat.S_ISVTX:
            return True
    return False


def auth_hint(harness: str, dropped: Sequence[str]) -> str:
    """Compose the `UNAUTHENTICATED` detail naming the credential vars nox dropped (C-1034(4)).

    A harness that ran and refused for want of credentials is usually a harness
    whose API key nox declined to forward — and saying so is the difference
    between a bug report and a one-line fix. Names only, never values.

    Args:
        harness: An `ADAPTERS` registry key. An unknown key contributes no
            names rather than raising: this composes an error message, and an
            error path is the worst place to raise a second error.
        dropped: `minimal_env`'s dropped names.

    Returns:
        A single sentence pair: the intersection of `dropped` with this
        harness's `AUTH_ENV_HINTS` entry (patterns matched with
        `fnmatchcase`), sorted, followed by `AUTH_HINT_TRAILER`. With an empty
        intersection, the trailer alone.
    """
    patterns = AUTH_ENV_HINTS.get(harness, frozenset())
    names = sorted({name for name in dropped if matches_any(name, patterns)})
    if not names:
        return AUTH_HINT_TRAILER
    return f"credential-shaped variables nox did not forward: {', '.join(names)}. {AUTH_HINT_TRAILER}"
