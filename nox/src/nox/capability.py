"""What a harness can be made to do, and how strongly (C-1007, C-1013).

Capabilities are absence-checked, never boolean-flagged: an adapter that
cannot establish one omits it and the launch gate refuses, rather than a
`False` reading as "supported, currently off". `Launcher`, `Enforcement`,
`ModelClass` and `ModelSpec` live here too (E9b) so the leaf cluster is closed
under its own imports; re-exporting each from its ADR home module is an
obligation those modules carry as they land — `Launcher` from `runner.py`
(WP3), `ModelClass` and `ModelSpec` from `config.py` (WP4) — not a property of
this module today.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal


class Capability(StrEnum):
    """A harness property nox depends on, established by probe, never assumed.

    Exactly three members: the enum is closed to what nox reads (E4/D-f). An
    unread member of a security enum invites a gate nothing checks, so the
    four capabilities the v1 flow never branches on are recorded here as
    evidence instead of shipped as values:

    | Capability (evidence only) | Claude Code 2.1.252 | Codex 0.144.1 | OpenCode 1.18.22 | Copilot 1.0.82 |
    |---|---|---|---|---|
    | streaming | `--output-format stream-json` | `--json` | `--format json` | `--output-format json` (JSONL) |
    | model | `--model`, `--effort` | `-m`, `-c model_reasoning_effort` | `-m provider/model` | `--model`, `--effort` |
    | cost | `total_cost_usd` | no | `step_finish` `part.cost` | AI credits, never USD |
    | tool allowlist | `--tools` | no — OS sandbox | no — config only | `--available-tools` |

    OpenCode's model selection carries no effort knob at all (BYOK, so the
    level is provider-specific), but it DOES report cost: WP7c pinned a real
    `step_finish` carrying `part.cost` of `0.000946` off the 1.18.22 binary,
    correcting the `no` this row used to claim. Copilot's four cells are pinned by WP7d off
    the binary, and two of them corrected what a reading of `--help` suggested:
    it reports **AI credits** and no dollar figure anywhere in the stream, so
    `ParsedOutput.cost_usd` stays `None` for that harness; and `--deny-tool`
    turned out to be a *permission* control that still offers the model every
    tool (14 denied, 17 offered), while `--available-tools` is the one that
    removes them (3 offered). Its deny set is enumerable — `--deny-tool`
    outranks `--allow-all-tools`, which is what satisfies `ENUMERABLE_DENY` —
    but there is no OS sandbox in v1, since `--experimental` MXC sandboxing is
    out of scope (D-ab), so containment is harness-level flags
    (`--available-tools`, `--deny-tool`, `--disable-builtin-mcps`,
    `--no-custom-instructions`) over the C-1003 worktree, and both enforcement
    axes stamp `harness`, never `os`.

    Model selection keeps its behaviour without a member: an adapter whose
    `MODELS` has no entry for the requested class resolves the harness default
    and records `Review.model = None` (C-1030 rule 6) — a property of `MODELS`,
    not of a capability bit.
    """

    ENUMERABLE_DENY = "enumerable_deny"
    """The deny set can be enumerated. Required to launch at all (C-1007)."""

    ENFORCED_READ_ONLY = "enforced_read_only"
    """Read-only is enforced below the model, not asked of it."""

    STRUCTURED_OUTPUT = "structured_output"
    """Output is schema-validated rather than prompt-requested."""


REQUIRED: Final[frozenset[Capability]] = frozenset({Capability.ENUMERABLE_DENY})
"""The capabilities `prepare()` refuses to launch without (C-1013).

A literal set, because "raises on a missing required capability" is otherwise
untestable. `ENFORCED_READ_ONLY` is deliberately absent: OpenCode launches
without it and is stamped `enforced_read_only=False`.
"""

Enforcement = Literal["os", "harness", "attested"]
"""How strongly a containment axis holds (C-1007).

- `os` — enforced below the model by the operating system, so the harness
  cannot lift it (Codex's sandbox).
- `harness` — enforced by the harness's own primitive, visible in the resolved
  argv (a deny list the harness itself applies).
- `attested` — self-declared by the harness and never probed. A claim, not
  evidence: the weakest of the three, and the reason `None` is not spelled as
  one of them.
"""

ModelClass = Literal["fast-balanced", "deep-reasoning"]
"""A capability class, never a literal model ID (adr_0001 C-001, C-1030)."""


def _reject_unusable_argv_word(field: str, value: str) -> None:
    """Raise unless `value` is one safely spawnable, safely loggable argv word (C-1030).

    Args:
        field: The field name, for the message.
        value: The candidate, normalized with `str()` first so a `str` subclass
            overriding `startswith` cannot lie its way past the guard.

    Raises:
        ValueError: Empty, starting with `-`, or carrying a whitespace or
            non-printable character — NUL, ESC and zero-width included, each of
            which otherwise reaches `Popen` or a log verbatim.
    """
    word = str(value)
    if not word or word.startswith("-") or any(ch.isspace() or not ch.isprintable() for ch in word):
        raise ValueError(f"{field} is not a usable argv word: {value!r}")


@dataclass(frozen=True, slots=True)
class ModelSpecT:
    """A typed model selection the adapter maps to flags — never a raw argv fragment.

    Codex's effort knob rides `-c`, which C-1023 refuses from passthrough;
    accepting argv here would reopen that hole through the back door. The
    C-1030 guard therefore lives in `__post_init__` rather than in `of()`:
    every construction path routes through it, including a direct
    `ModelSpecT(...)` out of an adapter's `MODELS` table.

    Attributes:
        model: The harness-local literal (OpenCode's carries a `provider/`
            prefix; Copilot's is bare).
        effort: The harness's reasoning-effort level, when it has one.
    """

    model: str
    effort: str | None = None

    def __post_init__(self) -> None:
        """Validate `model`, and `effort` when set, as argv words (C-1030).

        Raises:
            ValueError: Either field would smuggle an argv fragment, a NUL or an
                escape sequence past C-1023.
        """
        _reject_unusable_argv_word("model", self.model)
        if self.effort is not None:
            _reject_unusable_argv_word("effort", self.effort)

    @classmethod
    def of(cls, spec: str | ModelSpecT) -> ModelSpecT:
        """Normalize a `ModelSpec` to a `ModelSpecT`.

        The single place the `str` arm of `ModelSpec` is unwrapped. It performs
        no validation of its own — `__post_init__` owns that, so an already-typed
        `spec` was checked when it was built and is returned verbatim. Callers
        map the `ValueError` onto their own error type (`ConfigError` in
        `nox.config`); the leaf cluster raises no `NoxError` so it stays closed
        under its own imports.

        Args:
            spec: A bare literal, or an already-typed selection.

        Returns:
            The typed selection.

        Raises:
            ValueError: `spec` is a `str` that is not a usable argv word.
        """
        return spec if isinstance(spec, ModelSpecT) else cls(model=spec)


ModelSpec = str | ModelSpecT
"""A bare `str` means `ModelSpecT(model=s, effort=None)`. Read it via `ModelSpecT.of`."""


@dataclass(frozen=True, slots=True)
class Launcher:
    """A harness may be reachable only behind a prefix (C-1014).

    Attributes:
        binary: The executable name or path.
        prefix: Argv words that must precede it, e.g. a package-exec wrapper.
    """

    binary: str
    prefix: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Refuse an argv word that is empty.

        Unlike `ModelSpecT`, a leading `-` is legitimate here (`--` ends a
        wrapper's own options), so only emptiness is refused.

        Raises:
            ValueError: `binary`, or any element of `prefix`, is empty — each
                reaches `execve` as an empty argument.
        """
        if not self.binary or not all(self.prefix):
            raise ValueError(f"launcher argv words must be non-empty: binary={self.binary!r} prefix={self.prefix!r}")

    def argv(self, *args: str) -> tuple[str, ...]:
        """Return the full argv for `args` behind this launcher's prefix.

        Args:
            *args: The harness-level arguments.

        Returns:
            `prefix + (binary,) + args`.
        """
        return (*self.prefix, self.binary, *args)
