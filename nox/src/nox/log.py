"""The append-only local call log (C-1021).

No vendor exposes a pre-call quota check, and the documented lockout tail has no
warning: [anthropics/claude-code#47754](https://github.com/anthropics/claude-code/issues/47754)
records a headless OAuth refresh blocked by a WAF and 26+ days locked out with no
recovery short of browser re-auth. This file is the only spend visibility that
exists for the harnesses that report no cost at all.

**It never carries `raw`, and that is the whole design constraint.** Under
Codex the containment mechanism is an OS sandbox, and a read-only sandbox denies
writes and network reach but not *reads* — so `raw` can carry a credential the
reviewing model read (C-1018), and a log line is a durable artifact under
`$XDG_STATE_HOME`. Six fields plus `len(warnings)`, and nothing else: no
`detail`, no `summary`, no `findings`, no `raw`. Every one of those four can
quote harness output.

The log lives beside the trust store, under the user state directory and never in
the repository — reached through `config.trust_store_path`, which is the one
function that already resolves that directory with the T4b guard (a
`$XDG_STATE_HOME` the branch under review controls falls back to the passwd
database).
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from nox.config import ConfigError, trust_store_path

if TYPE_CHECKING:
    from pathlib import Path

    from nox.outcome import Review

__all__ = ["CALL_LOG_NAME", "call_log_path", "record"]

CALL_LOG_NAME: Final[str] = "calls.jsonl"
"""The log's filename, beside `trust.json` in the user state directory.

JSON Lines rather than a single JSON document: append-only is the contract, and
appending to a JSON array means rewriting it — which turns every review into a
read-modify-write of a file two concurrent nox processes could both be holding.
"""

_LOG_MODE: Final[int] = 0o600
"""The log's creation mode. It records which harnesses a machine's owner drives and when."""

_LOG_FLAGS: Final[int] = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW
"""`record`'s open flags.

`O_APPEND` because append-only is the contract, `O_CREAT` because the first
review of a machine's life finds no file, and `O_NOFOLLOW` because a symlink
planted at the log path would otherwise make every review an arbitrary append as
the user. No `O_EXCL` — unlike `workspace._NOFOLLOW_FLAGS` this file is meant to
already exist. `O_WRONLY` is the access mode the other three modify; `os.open`
takes no implicit one, and `O_RDONLY` is zero.
"""


def call_log_path(state_dir: Path | None = None, *, repo: Path | None = None) -> Path:
    """Where the call log lives: `<state dir>/calls.jsonl` (C-1021).

    Derived as `trust_store_path(...).parent / CALL_LOG_NAME` rather than
    resolving the state directory again. `config._xdg` is private and `NoxConfig`
    carries no state directory, so `trust_store_path` is the only route to that
    directory's T4b belt — a `$XDG_STATE_HOME` resolving inside the repository
    under review is refused and falls back to the passwd database — and a second
    resolver would be a second place for that guard to be forgotten.

    `.parent /` rather than `.with_name(...)`: the latter would silently break if
    the trust store ever moved into a subdirectory, and it reads as if the log
    were a variant of `trust.json` rather than its sibling.

    Args:
        state_dir: Override for the user state directory.
        repo: The repository under review, whose own subtree may not supply the
            state directory. **Pass it whenever it is known**: omitting it
            silently drops the T4b belt.

    Returns:
        The log path, which need not exist.

    Raises:
        ConfigError: The environment named a repository-controlled directory and
            this uid has no passwd entry to fall back to.
    """
    return trust_store_path(state_dir, repo=repo).parent / CALL_LOG_NAME


def record(
    review: Review,
    *,
    state_dir: Path | None = None,
    repo: Path | None = None,
    timestamp: str | None = None,
) -> None:
    """Append one line for a completed review (C-1021).

    Exactly seven keys — the six C-1021 names plus the warning count:

    | Key | Value |
    |---|---|
    | `timestamp` | ISO-8601, UTC, second resolution |
    | `harness` | the registry key, `""` when none was resolved |
    | `model` | the resolved literal, `null` when the harness default was taken |
    | `duration_s` | wall clock, rounded to milliseconds |
    | `outcome` | `"ok"`, else `"<status>:<reason>"` — one greppable field |
    | `cost_usd` | what the harness reported, `null` otherwise |
    | `warnings` | `len(review.warnings)`, never the strings themselves |

    `outcome` folds status and reason into one word because a `.jsonl` is read
    with `grep` as often as with a parser, and `error:rate_limited` is the line a
    user greps for after a lockout.

    **Never raises, and that covers both ways it could.** `review()` is total
    (C-1029) and this runs after the `Review` is built, so nothing here may turn
    a completed review into a failure. `OSError` is the obvious one — an
    unwritable or missing state directory. `ConfigError` is the one that is easy
    to miss: `call_log_path` reaches `config.trust_store_path`, which raises when
    `$XDG_STATE_HOME` is repository-controlled *and* this uid has no passwd entry
    to fall back to. Both are swallowed; the review is the product, the log is
    bookkeeping.

    Opened with `O_APPEND | O_CREAT | O_NOFOLLOW`: append because the contract is
    append-only, and `O_NOFOLLOW` because a symlink planted at the log path would
    otherwise make every review an arbitrary append as the user. No `O_EXCL` —
    unlike `workspace.write_nofollow` this file is meant to already exist.

    The state **directory** is created here too, mode `0o700`, inside the same
    `suppress`. Nothing else in nox creates it, so the alternative is a C-1021
    that ships inert: `O_CREAT` creates a file, not its parent.

    Args:
        review: The completed review.
        state_dir: Override for the user state directory.
        repo: The repository under review — see `call_log_path`.
        timestamp: Override for the recorded time, for tests. `None` reads the
            clock.

    Note:
        The seven keys are inserted in the documented order and handed to
        `json.dumps` as a plain dict, whose iteration order is its insertion
        order — so the line reads the same on every run without an
        `OrderedDict` or a sort key. `outcome` branches on `reason is None`
        rather than on `status == "ok"`: `Review.__post_init__` makes the two
        equivalent, and this one narrows the optional for the type checker at
        the same time.
    """
    entry: dict[str, object] = {
        "timestamp": timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "harness": review.harness,
        "model": review.model,
        "duration_s": round(review.duration_s, 3),
        "outcome": "ok" if review.reason is None else f"{review.status}:{review.reason.value}",
        "cost_usd": review.cost_usd,
        "warnings": len(review.warnings),
    }
    with suppress(ConfigError, OSError):
        path = call_log_path(state_dir, repo=repo)
        # Nothing else under `src/nox/` ever creates the user state directory —
        # `trust_store_path` only resolves it, and D-w means nothing writes
        # `trust.json` either — so without this the very first review of a
        # machine's life fails `ENOENT` on the missing parent and the `suppress`
        # above eats it, forever. `0o700` for the same reason `_LOG_MODE` is
        # `0o600`: this directory records which harnesses the owner drives.
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(path, _LOG_FLAGS, _LOG_MODE), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
