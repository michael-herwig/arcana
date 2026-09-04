"""The adapter registry: string key → dotted path, imported lazily on selection.

The registry carries every v1 key up front (D-ab), and the modules behind them
need not exist yet: the import happens when an adapter is *selected*, not when
this module loads. That is what lets four adapter work packages run in parallel
against a registry none of them edits — a shared file four concurrent branches
each append a line to is a merge conflict by construction, and the line is the
one that decides which code runs.

The values are shipped literals and `load()` is a dictionary lookup, never
`import_module(f"nox.adapters.{name}")`. A repository under review can choose
among the four shipped adapters through `[review] harness` (C-1042(5), and that
key is deliberately not trust-gated), but it cannot steer the import target —
so the worst it buys is a different reviewer, never different code.

Nothing under `nox/` outside this package may import `nox.adapters.<name>`: the
core flow reaches an adapter through `load()` and nothing else, which is what
keeps `nox.harness` free of any adapter's dialect. A static test asserts it.
"""

from __future__ import annotations

import importlib
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from nox.harness import HarnessUnavailable
from nox.outcome import FailureReason

if TYPE_CHECKING:
    from collections.abc import Mapping

    from nox.harness import Adapter

ADAPTERS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "claude": "nox.adapters.claude:ClaudeAdapter",
        "codex": "nox.adapters.codex:CodexAdapter",
        "copilot": "nox.adapters.copilot:CopilotAdapter",
        "opencode": "nox.adapters.opencode:OpenCodeAdapter",
    }
)
"""Registry key → `module:attribute`, in the `fsspec` registry shape.

The keys are the whole of nox's harness vocabulary: C-1042(5) generates its
"unknown harness" message from this mapping rather than a hand-written list, and
`load` below refuses an unregistered key against it — so this mapping is the one
place a harness name is checked, and a fifth adapter needs no edit anywhere
else. Behind a `MappingProxyType` because `Final` blocks rebinding and not
mutation, and this mapping decides which code runs.

`harness.PASSTHROUGH_ALLOW` is keyed by the same strings but is **not** a second
copy of this domain: it reads with an empty-set default, so a key it does not
carry passes nothing through rather than failing the review. It said as much and
did the opposite — `police_passthrough` raised on a key it had no entry for, and
since every `prepare` calls it, a fifth adapter registered here hard-failed
every review while this docstring said no other edit was needed. `harness.py`
cannot import this module to settle it — the dependency runs the other way — so
the default is what makes the claim true, and `stubs.FifthStub` is what runs it.
"""


def load(name: str) -> Adapter:
    """Import and instantiate the adapter registered under `name`.

    Args:
        name: A registry key.

    Returns:
        The adapter instance.

    Raises:
        HarnessUnavailable: `name` is not registered, or its module or
            attribute is missing — `UNSUPPORTED`, naming the REGISTERED keys
            and never the unknown one. `[review] harness` is repository-supplied
            and not trust-gated, so echoing it into `Review.detail` would put
            branch-authored text there (C-1035(1)); the registered set is also
            the more useful answer.
    """
    registered = ", ".join(sorted(ADAPTERS))
    target = ADAPTERS.get(name)
    if target is None:
        raise HarnessUnavailable(FailureReason.UNSUPPORTED, f"unknown harness; registered: {registered}")
    module_name, _, attribute = target.partition(":")
    try:
        adapter: Adapter = getattr(importlib.import_module(module_name), attribute)()
    except (ImportError, AttributeError) as exc:
        # The exception TYPE, never its message: an import error's text carries
        # the dotted path and would read as an invitation to supply one.
        raise HarnessUnavailable(
            FailureReason.UNSUPPORTED, f"no adapter is installed for this harness ({type(exc).__name__})"
        ) from exc
    return adapter
