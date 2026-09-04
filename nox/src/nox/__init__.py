"""nox — multi-harness adversarial review.

nox runs a review of a diff, or of a plan artifact, under an AI harness other
than the one that produced it: Claude Code, Codex, GitHub Copilot CLI or
OpenCode, headlessly, from an ephemeral git worktree built out of neutralized
synthetic commits so the reviewing harness never sees the repository's own
instructions, hooks or credentials.

This module re-exports the leaf vocabulary — every type in `__all__` is stable
surface. The entry point itself is `nox.api.review()`.
Pre-1.0: breaking changes ship without shims.
"""

# `nox.api` reaches every other module in the package, and it is safe first in
# this block only because nothing under `src/nox/` imports a name DEFINED IN THIS
# FILE — so a half-initialized `nox` is never read. `api.py`'s `from nox import
# adapters` is not a counter-example: a fromlist entry naming a submodule
# resolves to the submodule, never to a `__init__` binding, which is why it
# holds while this block is still running. `nox.cli` is the one module that does
# import a name from here, and it is deliberately not re-exported: it is the
# argv shell, not the library.
#
# `derive_containment` is NOT re-exported and may not be added: its `digest`
# argument is trusted, and `harness.authorize` is the only thing that should
# compute one (C-1025).
from nox.api import ReviewRequest, ReviewTarget, review
from nox.capability import (
    REQUIRED,
    Capability,
    Enforcement,
    Launcher,
    ModelClass,
    ModelSpec,
    ModelSpecT,
)
from nox.config import (
    MIN_TIMEOUT_S,
    WORLD_WRITABLE_EXEMPT,
    ConfigError,
    HarnessConfig,
    NoxConfig,
)

# The other three of the four `NoxError` subclasses `outcome.NoxError` names as
# nox's exception vocabulary. Re-exported beside `ConfigError` because a caller
# that wants to tell an isolation failure apart from a missing harness would
# otherwise have to import from `nox.harness` and `nox.workspace`, which are not
# stable surface. `_SupervisorFailure` and `_AdapterFailure` stay private: they
# never escape `review()`.
from nox.harness import HarnessUnavailable, UnsupportedCapability
from nox.liveness import Heartbeat, Liveness, TimeoutPolicy
from nox.outcome import (
    NOT_RUN,
    Containment,
    FailureReason,
    Finding,
    Mechanism,
    NoxError,
    Review,
    Severity,
    Status,
    Verdict,
)
from nox.prompt import Scope
from nox.runner import Invocation, Process, Runner, SubprocessRunner
from nox.workspace import IsolationError

# A literal, not `importlib.metadata.version("nox")`: the zipapp stages `src/nox`
# with no dist-info, and an unrelated PyPI `nox` on the host would answer instead.
# `tests/test_version.py` asserts it equals `[project] version` in pyproject.toml.
__version__ = "0.3.0"

__all__ = [
    "MIN_TIMEOUT_S",
    "NOT_RUN",
    "REQUIRED",
    "WORLD_WRITABLE_EXEMPT",
    "Capability",
    "ConfigError",
    "Containment",
    "Enforcement",
    "FailureReason",
    "Finding",
    "HarnessConfig",
    "HarnessUnavailable",
    "Heartbeat",
    "Invocation",
    "IsolationError",
    "Launcher",
    "Liveness",
    "Mechanism",
    "ModelClass",
    "ModelSpec",
    "ModelSpecT",
    "NoxConfig",
    "NoxError",
    "Process",
    "Review",
    "ReviewRequest",
    "ReviewTarget",
    "Runner",
    "Scope",
    "Severity",
    "Status",
    "SubprocessRunner",
    "TimeoutPolicy",
    "UnsupportedCapability",
    "Verdict",
    "__version__",
    "review",
]
