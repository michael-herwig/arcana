"""The result vocabulary: status, failure reasons, findings, containment, review.

Tri-state by construction (C-1011): an unclassifiable run resolves to
`indeterminate` and never collapses to `ok`, and the exit code is never the
success gate. `NoxError` is the base of every exception nox raises; `review()`
is total (C-1029) and maps each one onto a `Review` with `status != "ok"`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final, Literal, get_args

from nox.capability import Enforcement, ModelClass
from nox.liveness import Heartbeat


class NoxError(Exception):
    """Base of every exception nox raises.

    Subclasses live with the component that raises them (`ConfigError`,
    `IsolationError`, `HarnessUnavailable`, `UnsupportedCapability`);
    `nox.api.review()` catches this type and never lets one escape (C-1029).
    """


Status = Literal["ok", "error", "indeterminate"]
"""Tri-state run outcome (C-1011)."""

Severity = Literal["block", "high", "warn", "suggest"]
"""Finding severity — lowercase on the wire and in Python (C-1018, E1).

Both precedents (Codex's `review-output.schema.json`, SARIF) are lowercase;
the consumer title-cases for display and ingest lowercases before validating.
"""

Verdict = Literal["approve", "needs-attention"]
"""Overall judgement, present only when `status == "ok"` (C-1018)."""

Mechanism = Literal["tool-removal", "os-sandbox", "config-deny"]
"""How a harness is held, per its own primitive (C-1007).

Named rather than spelled inline so `Containment.mechanism` and WP6's
`ContainmentPlan.mechanism` cannot drift apart.
"""


class FailureReason(StrEnum):
    """Why a run did not resolve `ok` (C-1012).

    Every adapter ships an evidence-backed classification table; `classify()`
    returns `None` — yielding `indeterminate` plus the raw error name —
    wherever no recorded fixture proves the cell. Never a substring guess.
    """

    ABSENT = "absent"
    """The harness binary could not be found or run."""

    UNAUTHENTICATED = "unauthenticated"
    """The harness ran and refused for want of credentials."""

    RATE_LIMITED = "rate_limited"
    """The provider refused for quota or rate reasons."""

    MALFORMED_OUTPUT = "malformed_output"
    """Output could not be parsed, or exceeded the byte cap."""

    TIMED_OUT = "timed_out"
    """A wall-clock or silence bound elapsed (C-1010)."""

    KILLED = "killed"
    """Exit 143 — *we* killed it. Never used for a generic non-zero exit."""

    ISOLATION_FAILED = "isolation_failed"
    """The ephemeral worktree could not be built or torn down (C-1006)."""

    UNSUPPORTED = "unsupported"
    """A required capability, or the platform itself, was absent (C-1013, D-j)."""

    INVALID_CONFIG = "invalid_config"
    """A refused passthrough element, a malformed permission value in a trusted
    config, or an unusable `ReviewTarget.path` (C-1023, C-1016, C-1027).

    Exists because `reason` is non-`None` iff `status != "ok"` and `ConfigError`
    had no member to carry.
    """


@dataclass(frozen=True, slots=True)
class Finding:
    """One reported issue.

    Attributes:
        severity: Lowercase severity literal (E1).
        title: One-line summary.
        body: The finding's argument.
        file: Where the harness said the finding is — unvalidated untrusted
            output (C-1019). Nothing here enforces repo-relativity or that
            the path is in-tree; WP6's `parse` owes the traversal check
            before any consumer resolves it.
        line_start: First line of the span, when located.
        line_end: Last line of the span, when located.
        confidence: How strongly the origin stands behind it.
        recommendation: The suggested fix, when one was offered.
        origin: `"nox"` marks the C-1026 completeness finding — the one element
            of `findings` that is NOT untrusted harness output (C-1019).
    """

    severity: Severity
    title: str
    body: str
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    recommendation: str | None = None
    origin: Literal["harness", "nox"] = "harness"


@dataclass(frozen=True, slots=True)
class Containment:
    """How contained the run that produced a `Review` actually was.

    Stamped into every `Review`, on EVERY return path including `error` and
    `indeterminate`. Derived from the resolved argv, never hand-written
    (C-1025) — the consumer weights findings by it (C-1019).

    Attributes:
        isolation: v1 has one value; the field is the seam.
        neutralized: Index entries dropped by name (C-1005), verified absent
            from the checkout. Does NOT force `needs-attention` — the reviewer
            loses no evidence about the change itself.
        neutralized_total: How many there were before `Workspace` capped the
            list at `ENUMERATION_BUDGET`. Every list here is branch-controlled
            and unbounded at the source, so a consumer that read `len(...)` off
            the stamp was reading the cap and calling it the count — and a
            repository holding more than the budget looked complete. A total
            above its list's length means the rest was never enumerated INTO
            THE STAMP, never that it was not there.
        omitted: Untracked paths NOT reviewed (C-1026); non-empty means the
            verdict may not be `approve`.
        omitted_total: The same for `omitted`.
        filtered: Entries dropped by mode (C-1043), as `<path> -> <target>`.
            EVIDENCE, not a verdict input: C-1043(2) requires every dropped
            entry listed so a symlink the branch *added* stays visible to the
            reviewer, so this is the union over both ends and a repository
            merely carrying a committed symlink or submodule populates it
            forever. Reading it as "the reviewer could not see part of the
            change" would make such a repository permanently un-approvable.
            The verdict gate is the differing subset — `Workspace.
            filtered_changed` under C-1043(4), the entries that are not the
            same at both ends — which is what forces `needs-attention`
            alongside a non-empty `omitted`. `filtered_changed` itself is
            deliberately NOT stamped: on every path that produced findings to
            attach one to, it reaches the consumer as the C-1026 completeness
            finding, which states its own `N of M`. A refusal carries no
            findings at all, which is the split this class already documents —
            what the reviewer could not see is read off `omitted` here.
        filtered_total: The same for `filtered`.
        mechanism: How this harness is held, per its own primitive. `None` on a
            pre-spawn refusal, where no harness was ever selected.
        write_enforcement: How strongly writes are prevented, not whether.
            `None` means not established — never a weaker value standing in
            (C-1007); the consumer must not read absence as a level.
        network_enforcement: The same for network reach.
        enforced_read_only: Whether `ENFORCED_READ_ONLY` was present (C-1013).
        env_scrubbed: Whether the child ran under the minimal env (C-1008).
        secrets_suspected: A credential shape was seen in the retained `raw`
            (C-1018). Never silently redacted. `False` means no credential
            shape was detected in `raw` — meaningless unless a harness
            produced output at all, so the consumer reads it together with
            `truncated` and never as "no secret leaked".
    """

    isolation: Literal["worktree"]
    neutralized: tuple[str, ...]
    neutralized_total: int
    omitted: tuple[str, ...]
    omitted_total: int
    filtered: tuple[str, ...]
    filtered_total: int
    mechanism: Mechanism | None
    write_enforcement: Enforcement | None
    network_enforcement: Enforcement | None
    enforced_read_only: bool
    env_scrubbed: bool
    secrets_suspected: bool


NOT_RUN: Final[Containment] = Containment(
    isolation="worktree",
    neutralized=(),
    neutralized_total=0,
    omitted=(),
    omitted_total=0,
    filtered=(),
    filtered_total=0,
    mechanism=None,
    write_enforcement=None,
    network_enforcement=None,
    enforced_read_only=False,
    env_scrubbed=False,
    secrets_suspected=False,
)
"""The one `Containment` for every path that refuses before a harness runs.

`isolation` names the model, not evidence a run reached it. Exists so no
call site invents an enforcement level for a run that never happened —
`Containment` is what the consumer weights findings by (C-1019), so a stood-in
`os` there is a security claim nothing established. The empty `omitted`,
`filtered` and `neutralized` tuples carry the same care the `None`
enforcement fields do: they mean the paths were NEVER ENUMERATED, not that
nothing was hidden from a reviewer that never ran. Their three `0` totals say
the same thing rather than "there were none", and the three `False` booleans
read the same way — nothing was established, so nothing is claimed.
"""


_STATUSES: Final[tuple[Status, ...]] = get_args(Status)
"""The three recognized outcomes, read off the `Literal` rather than restated."""


@dataclass(frozen=True, slots=True)
class Review:
    """The single result type. `nox.api.review()` returns one and never raises.

    Attributes:
        status: Tri-state outcome (C-1011).
        verdict: `None` whenever `status != "ok"` (C-1018).
        findings: Reported issues, harness-origin unless stamped otherwise.
        summary: The harness's own prose summary — untrusted output (C-1019),
            empty when no harness produced one.
        detail: nox's OWN account of a non-`ok` outcome (a dropped auth
            variable's name, a collector exception, a refused passthrough
            element). Never harness output, so the provenance split
            `Finding.origin` keeps holds here too; carries the C-1035
            redaction rule. Flattened by `api._safe` at the two sites that
            assemble it, because the strings handed to them are built from
            branch-controlled bytes.
        raw: Untruncated harness output, retained unconditionally.
        truncated: Whether the byte cap cut the stream.
        reason: Non-`None` iff `status != "ok"`.
        harness: The `ADAPTERS` key that ran.
        harness_version: The version that ran, when the probe resolved one.
        verified_against: The version this adapter was tested against (C-1020).
        model: The RESOLVED literal; `None` when the harness default was taken.
        model_class: What was asked for. Both sides recorded — asymmetry evidence.
        heartbeat: Progress evidence at the moment the run ended. `__post_init__`
            snapshots it with `dataclasses.replace`, so a caller may hand over
            the live instance the drain loop is still touching and the `Review`
            still holds a still frame. `Heartbeat` is mutable, so a `Review` is
            frozen but not hashable.
        containment: How contained the run was (C-1025).
        duration_s: Wall-clock seconds.
        cost_usd: Reported cost, where the harness reports one.
        warnings: The single home for every non-fatal advisory (C-1035),
            present — possibly empty — on every return path. Never carries an
            environment value, a `$HOME` path outside the repo, or any
            substring of `raw`.
    """

    status: Status
    verdict: Verdict | None
    findings: tuple[Finding, ...]
    summary: str
    detail: str | None
    raw: str
    truncated: bool
    reason: FailureReason | None
    harness: str
    harness_version: str | None
    verified_against: str
    model: str | None
    model_class: ModelClass | None
    heartbeat: Heartbeat
    containment: Containment
    duration_s: float
    cost_usd: float | None
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        """Enforce the three invariants and snapshot the heartbeat.

        `status` is one of the three (C-1011), `verdict` is non-`None` iff
        `status == "ok"` (C-1018), and `reason` is non-`None` iff it is not.
        Stated in prose the three would be re-asserted at every construction site
        in `nox.api`; here they cannot drift.

        **The domain check comes first, and refuses rather than coerces.** The
        other two derive from `status == "ok"`, so a word an adapter invented
        satisfied both — `verdict=None` with a `reason` set is exactly what a
        non-`ok` outcome looks like — and travelled on to a consumer that
        branches on it. Coercing an unknown word onto `indeterminate` would hide
        an adapter bug behind an outcome that reads as one nox classified.

        An invariant, not a sanitizer: what a `status` may BE is the type's own
        business, while making `detail` safe to print is a boundary duty and
        stays at the two `nox.api` sites that assemble it (`api._safe`). The
        split is deliberate — a check here would also run on every adapter test
        that builds a `Review` by hand, for a concern two call sites close.

        `heartbeat` is replaced with a copy because "pass a snapshot" was a
        convention every caller had to remember, and the drain loop keeps
        mutating the instance it was handed.

        Raises:
            ValueError: `status` is outside the tri-state, or either invariant
                is violated.
        """
        if self.status not in _STATUSES:
            raise ValueError(f"status is one of {_STATUSES}; got status={self.status!r}")
        ok = self.status == "ok"
        if (self.verdict is not None) != ok:
            raise ValueError(f"verdict is set iff status is 'ok'; got status={self.status!r} verdict={self.verdict!r}")
        if (self.reason is not None) == ok:
            raise ValueError(f"reason is set iff status is not 'ok'; got status={self.status!r} reason={self.reason!r}")
        object.__setattr__(self, "heartbeat", replace(self.heartbeat))

    def require_ok(self) -> Review:
        """Return self when `status == "ok"`, else raise.

        The single explicit decision point (C-1011). It performs no type
        narrowing — it is `if r.status != "ok": raise` with a name. `review()`
        itself never raises (C-1029); this is the opt-in.

        Returns:
            This review, unchanged.

        Raises:
            NoxError: On `error` and on `indeterminate`.
        """
        if self.status != "ok":
            raise NoxError(f"review did not resolve ok: status={self.status!r} reason={self.reason!r}")
        return self
