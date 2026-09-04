"""The adapter protocol, the launch gate, and containment derivation.

C-1007, C-1011 (the parse framework), C-1012, C-1013, C-1014, C-1020, C-1023,
C-1024, C-1025, C-1030 rule 6, C-1036, E3, E9a.

This module is the join: wave 2 built the workspace, the runner, the config and
the prompt independently, and everything an adapter is allowed to do passes
through here. Four properties are structural rather than conventional, and each
exists because the convention version of it failed a review:

1. **An adapter never spawns the review.** `prepare` returns a `Launch` — argv
   words and the environment additions its own containment needs — and
   `authorize` turns that into the `Invocation` core spawns. So `cwd` is the
   ephemeral worktree by construction, the environment is the C-1008 one plus
   only what the plan declared, and no adapter can be written that forgets
   either. The probe is an adapter's one spawn, and it runs in a nox-minted
   empty directory under the same environment (C-1014).
2. **An adapter never states its own containment.** `containment_plan()` is a
   *claim*; `derive_containment()` re-checks every axis against the final
   resolved argv and env, and downgrades to `None` anything the invocation does
   not corroborate (C-1025). `authorize` is the only producer of a review
   `Invocation` and it refuses on a `None` axis, so the gate is unskippable
   rather than a step WP8 has to remember.
3. **An adapter never builds instruction text.** `review_prompt()` is the one
   route from a workspace to a prompt, and it fills `neutralized_paths` and
   `structured_output` itself — the two arguments an adapter would otherwise
   have to remember for C-1028 and C-1043 to hold.
4. **An adapter never normalizes untrusted output by hand.**
   `ParsedOutput.__post_init__` runs every `Finding.file` through
   `safe_finding_file`, so a `../../etc/passwd` from a hostile review cannot
   reach a consumer that opens it, whichever adapter parsed it.

What this module deliberately does NOT model is descendant *lifetime*. Both
enforcement axes are about writes and network reach; neither says anything
about whether a process outlives the review, and D-ac ruled out a constant
third axis precisely because a value identical on every run would read as
derived evidence under C-1025 and carry none. `runner.py` names the two open
holes (a descendant backgrounded across a clean exit, and a `setsid()` escape);
nothing here may imply they are closed.

**Call order**, fixed by SD § 3 and enforced by the shape:
`probe` → `workspace` → `containment_plan` → `prepare` → `authorize` → spawn.
`authorize` is where (5) and (6) are checked against each other, and nothing
else in nox constructs a review `Invocation`.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import string
import sysconfig
import tempfile
import time
from collections.abc import Generator, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import ClassVar, Final, Protocol, cast, get_args

from nox.capability import REQUIRED, Capability, Enforcement, Launcher, ModelClass, ModelSpec, ModelSpecT
from nox.config import DENY_PATTERNS, ConfigError, HarnessConfig, matches_any
from nox.liveness import Heartbeat, Liveness, TimeoutPolicy
from nox.outcome import FailureReason, Finding, Mechanism, NoxError, Severity, Status, Verdict
from nox.prompt import render
from nox.runner import POLL_S, Invocation, Process, Runner, Supervision, supervise
from nox.workspace import Workspace, write_nofollow

# ── Errors ───────────────────────────────────────────────────────────────────


class HarnessUnavailable(NoxError):
    """The harness could not be reached, or refused before a review began (C-1014).

    Raised by `probe()` — never a sentinel return, so a caller cannot forget to
    check one. `reason` is the `FailureReason` the boundary stamps; `detail` is
    nox's own account of it, and under C-1034(4) an `UNAUTHENTICATED` detail
    names the dropped credential variables from `config.auth_hint`.

    Attributes:
        reason: `ABSENT`, `UNAUTHENTICATED` or `UNSUPPORTED`.
        detail: nox's own prose. Never harness output, and never an environment
            *value* (C-1035).
    """

    def __init__(self, reason: FailureReason, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


class UnsupportedCapability(NoxError):
    """The launch gate refused: a required capability or an enforcement axis is missing.

    C-1013 (a member of `REQUIRED` absent from `HarnessInfo.capabilities`) and
    C-1007 (either enforcement axis `None` after derivation). Both resolve to
    `FailureReason.UNSUPPORTED` with no harness spawned.
    """


# ── Shipped literals ─────────────────────────────────────────────────────────

PASSTHROUGH_ALLOW: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "claude": frozenset(),
        "codex": frozenset(),
        "copilot": frozenset(),
        "opencode": frozenset(),
    }
)
"""Per-adapter allowlist of `nox.toml` `passthrough` flags (C-1023) — THE gate.

Permission, not exclusion: anything absent is refused by name. Four empty sets
are the honest state of an allowlist over harnesses that expose almost nothing
containment-inert.

**Absent KEYS are refused by name too**, and that is what keeps the extension
point honest: `police_passthrough` reads this with an empty-set default, so a
fifth adapter needs no entry here to review — it simply passes nothing through,
which is the safe end of the gate rather than the permissive one. The four keys
below are therefore an audited statement about four harnesses, not the domain
of the function; `adapters.ADAPTERS` is the domain, and this module may not
import it (see `STDIN_PROMPT_HARNESSES` for why the dependency runs one way).

Codex's `--title` was here and is **gone**. It is documented on `codex exec
review` and nowhere else, and nox spawns bare `codex exec` (E21), so
`police_passthrough` would have appended it to an argv that answers
`error: unexpected argument '--title' found` and exits 2 — the binary's clap
error where a nox refusal by name belongs, and it was the ONLY word this
allowlist let a repository pass through. Same class as `--resume`/`-r` and
E19's `OPENCODE_AUTH_JSON`: a name shipped in a security-relevant literal
without being checked against the binary's own `--help`.
`test_harness.py::test_every_allowlisted_passthrough_flag_is_a_real_flag_on_the_command_nox_spawns`
audits every future entry against the committed page for the command nox spawns.

The model flag is deliberately NOT here — under C-1030 every
adapter emits it from `MODELS[class]`, and the no-duplicate rule refuses any
passthrough copy of a nox-owned flag, so listing it would make the two rules
contradict each other on the design's highest-risk field.

Behind a `MappingProxyType`, not merely `Final`: `Final` blocks rebinding and
not mutation, and this is the mapping that decides which repository-supplied
words reach a harness.

Keyed by registry name, and a key here that `nox.adapters.ADAPTERS` does not
carry is a permission granted to nothing — a typo or a half-done deletion, which
a test catches. The reverse direction is deliberately legal and is the
extension point above.
"""

NEVER_ALLOWLISTABLE: Final[frozenset[str]] = frozenset(
    {
        "-c",
        "--config",
        "--settings",
        "--setting-sources",
        "--mcp-config",
        "--agents",
        "--plugin-dir",
        "--tools",
        "--permission-mode",
        "--system-prompt",
        "--append-system-prompt",
        "--permission-prompt-tool",
        "--enable",
        "--disable",
    }
)
"""Value-carrying config flags that may never join `PASSTHROUGH_ALLOW` (C-1023).

Not a runtime check — `police_passthrough` already refuses everything outside
the allowlist, so this set would be dead weight there. It exists so the ADR's
"no value-carrying config flag is ever addable here" is a test over the shipped
literal rather than a sentence a future adapter author has to have read.
`--settings` is the one that matters most: `--restricted`'s own help text says
managed settings and `--settings` still apply, so a single allowlisted
`--settings '{"hooks":…}'` is arbitrary command execution surviving the whole
flag stack.
"""

DENIED_FLAGS: Final[frozenset[str]] = frozenset(
    {
        # Codex
        "--dangerously-bypass-hook-trust",
        "--dangerously-bypass-approvals-and-sandbox",
        "-c",
        "--config",
        # Claude Code. `--permission-mode` is the value-carrying spelling of the
        # lift above: at 2.1.260 no value is narrower than the default a `-p`
        # run already gets, so `acceptEdits`, `auto`, `bypassPermissions` and
        # `dontAsk` widen and `plan` changes the output shape. It was in
        # `NEVER_ALLOWLISTABLE` alone, which is documented as NOT a runtime
        # check — so it was refused only for as long as the allowlist stays
        # empty, and nothing refused nox EMITTING it (E52).
        "--dangerously-skip-permissions",
        "--permission-mode",
        "--bare",
        "--add-dir",
        # OpenCode — `--no-pure` is yargs' negation of `--pure`, the one word in
        # this adapter's `argv_evidence`; allowing it through passthrough would
        # invalidate the evidence without changing the argv nox derives from.
        "--no-pure",
        # OpenCode — unpinned until WP7c verifies each name against its
        # committed `--help` fixture (E3). Over-denying passthrough is
        # fail-safe; a misspelling here is a refusal that never fires, not a
        # permission, and WP7c reports a correction rather than editing this.
        "--auto",
        "--share",
        "--attach",
        "--port",
        "--command",
        "--continue",
        "-s",
        "--session",
        "--fork",
        "-f",
        "--file",
        "--dir",
        "-i",
        "--interactive",
        # GitHub Copilot CLI (D-ab) — pinned against the committed
        # `tests/contract/fixtures/copilot/help-1.0.82.txt` (E3). `--allow-all`
        # and `--yolo` are that file's own documented aliases for
        # `--allow-all-tools --allow-all-paths --allow-all-urls`, so denying the
        # three long forms without them denied nothing. `-r` and `-C` are short
        # forms: `-r, --resume[=value]` reaches a denied capability under a
        # second spelling, and `-C <directory>` has no long form at all.
        "--allow-all-tools",
        "--allow-all-paths",
        "--allow-all-urls",
        "--allow-all",
        "--yolo",
        "--allow-all-mcp-server-instructions",
        "--allow-tool",
        "--allow-url",
        "--experimental",
        "--resume",
        "-r",
        "-C",
        # Code and configuration the harness loads and then runs, each of which
        # re-widens the tool set `--available-tools` was supposed to be the whole
        # of. `--plugin-dir` was in `NEVER_ALLOWLISTABLE` only, and that set is
        # documented as NOT a runtime check.
        "--additional-mcp-config",
        "--plugin-dir",
        "--extension-sdk-path",
        "--bash-env",
        "--agent",
        "--enable-mcp-server",
        "--enable-all-github-mcp-tools",
        "--add-github-mcp-tool",
        "--add-github-mcp-toolset",
        # Session egress and inbound control. The session IS the diff under
        # review, so `--share-gist` publishes it, and `--remote`/`--connect`
        # let something outside the ephemeral worktree drive the reviewer.
        "--share-gist",
        "--remote",
        "--remote-export",
        "--connect",
        # Claude Code 2.1.260, pinned against `fixtures/claude/help-2.1.260.txt`.
        # `-w/--worktree` is `-C`'s class — a DIFFERENT git worktree, so the
        # review would not be the C-1003 one; `--bg/--background`, `--cloud`,
        # `--environment` and `--teleport` move or detach the run so nothing nox
        # supervises is what answers; `--from-pr` replaces the reviewed content;
        # `--remote-control` is inbound and `_names_option` does not reach it
        # from `--remote`; `--allow-dangerously-skip-permissions` is the long
        # spelling of the lift already denied; `--plugin-url` loads code.
        "-w",
        "--worktree",
        "--bg",
        "--background",
        "--cloud",
        "--environment",
        "--teleport",
        "--from-pr",
        "--remote-control",
        "--allow-dangerously-skip-permissions",
        "--plugin-url",
        # Copilot 1.0.82, same page. `--acp` is `--connect`'s inbound class;
        # `--session-id` is the third spelling of resume, after `--resume`/`-r`
        # and `--continue`; `--autopilot`, `--plan` and `--no-ask-user` each
        # remove the approval step the review is supposed to stop at.
        "--acp",
        "--session-id",
        "--autopilot",
        "--plan",
        "--no-ask-user",
        # OpenCode 1.18.22 — the listener family beside the already-denied
        # `--port`. `--mdns` defaults the hostname to 0.0.0.0.
        "--hostname",
        "--mdns",
        "--cors",
    }
)
"""Flags refused from `passthrough` unconditionally (C-1023).

Refusal only. This set does NOT constrain nox's own argv: `-c` is Codex's sole
containment route (`-c sandbox_mode=read-only`, SD § 6.2 / E8) and `-f/--file`
is a plausible prompt channel, so a set that both refused repository input and
forbade nox's own emission would make two adapters unimplementable. That second
duty lives in `NEVER_EMITTED`.

The whole set ships up front, including the members only wave 4's adapters will
exercise: this file is WP6's, so an adapter that had to add its own entry would
have to edit a file it does not own (D-ab).
"""

NEVER_EMITTED: Final[frozenset[str]] = frozenset(
    {
        "--dangerously-bypass-hook-trust",
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-skip-permissions",
        # SD § 6.1 prescribes `--permission-mode dontAsk`; `adapters/claude.py`
        # deviated and emits `--permission-prompts none` instead, because no
        # value of this flag is narrower than the default. The design still says
        # otherwise, so the deviation needs an enforcer and not only a paragraph.
        "--permission-mode",
        "--bare",
        "--add-dir",
        "--auto",
        "--allow-all-tools",
        "--allow-all-paths",
        "--allow-all-urls",
        "--allow-all",
        "--yolo",
        "--allow-all-mcp-server-instructions",
        "--allow-tool",
        "--allow-url",
        "--experimental",
        "--additional-mcp-config",
        "--plugin-dir",
        "--extension-sdk-path",
        "--bash-env",
        "--agent",
        "--enable-mcp-server",
        "--enable-all-github-mcp-tools",
        "--add-github-mcp-tool",
        "--add-github-mcp-toolset",
        "--share",
        "--share-gist",
        "--remote",
        "--remote-export",
        "--connect",
        "--no-pure",
        "-C",
        # Claude Code 2.1.260, pinned against `fixtures/claude/help-2.1.260.txt`.
        # `-w/--worktree` is `-C`'s class — a DIFFERENT git worktree, so the
        # review would not be the C-1003 one; `--bg/--background`, `--cloud`,
        # `--environment` and `--teleport` move or detach the run so nothing nox
        # supervises is what answers; `--from-pr` replaces the reviewed content;
        # `--remote-control` is inbound and `_names_option` does not reach it
        # from `--remote`; `--allow-dangerously-skip-permissions` is the long
        # spelling of the lift already denied; `--plugin-url` loads code.
        "-w",
        "--worktree",
        "--bg",
        "--background",
        "--cloud",
        "--environment",
        "--teleport",
        "--from-pr",
        "--remote-control",
        "--allow-dangerously-skip-permissions",
        "--plugin-url",
        # Copilot 1.0.82, same page. `--acp` is `--connect`'s inbound class;
        # `--session-id` is the third spelling of resume, after `--resume`/`-r`
        # and `--continue`; `--autopilot`, `--plan` and `--no-ask-user` each
        # remove the approval step the review is supposed to stop at.
        "--acp",
        "--session-id",
        "--autopilot",
        "--plan",
        "--no-ask-user",
        # OpenCode 1.18.22 — the listener family beside the already-denied
        # `--port`. `--mdns` defaults the hostname to 0.0.0.0.
        "--hostname",
        "--mdns",
        "--cors",
    }
)
"""Flags that must never appear in nox's OWN emitted argv, for any adapter.

A subset of `DENIED_FLAGS`, and the distinction matters: every member *lifts* a
containment control, *escapes the boundary it is measured in*, or *sends the
review somewhere*, so nox emitting one would defeat the mechanism its own
`ContainmentPlan` claims. The three classes are not the same hazard. `-C` is
the second one: it changes
the working directory before anything else runs, so the harness would review
somewhere other than the C-1003 ephemeral worktree while `Invocation.cwd` still
reads `ws.path` and the stamp still says the axis holds. No derivation catches
that — `derive_containment` checks argv words against evidence, not the cwd the
harness actually ends up in — which is why the refusal has to be by name here.
The third class is `--share-gist` and the `--remote*` family: the session IS the
diff under review, so one of those publishes it or hands an outside party the
reviewer's controls, and neither enforcement axis is about egress at all.

`--no-pure` is the second class again, in yargs' spelling: it negates `--pure`,
which is the whole of OpenCode's `argv_evidence`, and derivation cannot see it
— rule 4 refuses a word that RE-SPECIFIES an evidence flag, and a negation
shares no spelling with the flag it cancels. So the argv would still carry
`--pure` contiguously, the axis would still stamp, and last-wins would have
turned it off.

`authorize` refuses the final argv on a member, matched through
`_names_option`: bare, on the token before `=`, and — since `-C` is a short
flag and every v1 harness parses `-Cvalue` as `-C value` — on an attached
value too. So a computed or table-driven flag is caught as well as a literal
one. A static scan over the adapter sources asserts the literal case, which is
what makes the offending word visible in review rather than only at launch.
"""

NEVER_SET: Final[frozenset[str]] = frozenset(
    {
        "LD_PRELOAD",
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "DYLD_LIBRARY_PATH",
        "NODE_OPTIONS",
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
    }
)
"""Environment names an adapter's `Launch` may never set, whatever its plan declares (C-1044).

Loader and interpreter hijack channels only, and the membership rule is that
class in full: every member makes the child — or a `git` the child spawns —
load and run code of the SETTER's choosing without the harness ever deciding
to. An adapter that declared one as `env_evidence` would widen the C-1008
environment through the launch path with the containment stamp intact.

`LD_AUDIT`, `LD_LIBRARY_PATH` and `PYTHONPATH` were on `config.NEVER_FORWARD`
and missing here, and the docstring claimed the class was complete while three
of its members were absent (H5). `LD_AUDIT` is `LD_PRELOAD`'s twin — glibc's
rtld-audit interface loads the named object before the first line of `main` —
and `PYTHONPATH` is `PYTHONSTARTUP`'s: `site` imports `sitecustomize` off the
search path at interpreter startup. That none of the three was *branch*
reachable (`ALLOWLIST ∩ NEVER_SET = ∅`, so no member can arrive from the user's
environment) is not the bar: C-1044 fixes membership by class, so an incomplete
set is a false claim in the one place a future adapter author reads.

**Twelve more were added under E70 for that same reason — the third time this
set's completeness claim has been found false (H5 first, C-1044 second).** Each
completes a family already represented here rather than opening a new one, which
is the test applied: five `DYLD_*` beside the two that were here
(`FRAMEWORK_PATH`, the two `FALLBACK_*`, the two `VERSIONED_*` — dyld consults
all of them); `GIT_SSH` and `GIT_PROXY_COMMAND` beside `GIT_SSH_COMMAND` and
`GIT_EXTERNAL_DIFF`, both naming a program git executes; `BASH_ENV` and `ENV`,
which are `PYTHONSTARTUP`'s shell twins — a non-interactive `sh`/`bash` sources
the named file before the command it was spawned to run, and all four harnesses
spawn shells; `PYTHONHOME` beside `PYTHONPATH`; and `PERL5OPT`/`RUBYOPT` beside
`NODE_OPTIONS`, all three being interpreter option injection.

Reachability is again not the bar and again not present: `minimal_env` is
allowlist-based, so none of these can arrive from the ambient environment, and
only a buggy adapter's `launch.env` could set one. The claim is what is being
repaired, not an exploit.

**The relation to `config.NEVER_FORWARD` is strict containment**:
`NEVER_SET ⊊ NEVER_FORWARD`. Two tests carry it and neither alone is the claim
— `NEVER_SET <= NEVER_FORWARD` (C-1044(3)'s subset test, so this set can never
drift into a name the inherit rule does not already cover) plus the four
held-out names asserted absent from this one, which is what makes the
containment strict rather than merely possible. The two sets answer different
questions — `NEVER_FORWARD` is "never *inherit* this from the user", this is
"never let an adapter *set* it" — and the residual is those four literal names
plus the `NEVER_FORWARD_GLOBS` pattern, each held out for a stated reason
rather than by omission:

- `OPENCODE_CONFIG_CONTENT` — the named exception, and the reason the two
  cannot be one set. Setting it IS OpenCode's containment mechanism
  (`ContainmentPlan.env_evidence`'s whole case, C-1025's derivation table), so
  a `NEVER_SET` that swallowed it would make that adapter unimplementable while
  every membership assertion still passed.
- `OPENCODE_CONFIG` — its path-valued twin, out for the same reason and one
  more: a config file is read by the harness *after* it starts, on the
  harness's own terms, which is not the pre-exec class. It is on the inherit
  list because a *user's* value would collide with the value the plan declares
  (`adapters/opencode.py::CONFIG_ENV`).
- `SSH_AUTH_SOCK` — a credential channel, not a code channel. It hands the
  child the ability to authenticate as the user over an agent socket; nothing
  is loaded and nothing runs. It is on the inherit list as C-1007's `AF_UNIX`
  residual (ADR :853) — an argument about what nox must not *pass down*, which
  says nothing about the launch path.
- `OPENCODE_AUTH_CONTENT` — a credential VALUE, inline (E19/D-ad, C-1002). Same
  judgement: no load semantics. `authorize` never puts its value in a message
  (C-1035), which is the property that one actually needs.
- `NEVER_FORWARD_GLOBS`' `BUN_*` — a PATTERN, and this set is matched by
  identity (`name in NEVER_SET`) because C-1044 contracts it as literal names.
  It is also not admissible as written: the glob's members are mostly inert
  paths and registry knobs (`BUN_INSTALL`, `BUN_CONFIG_REGISTRY`), so folding
  it in would make the universal claim above false rather than stronger. Should
  a specific Bun preload name ever be pinned against the binary, it joins here
  as a literal AND must be added to `NEVER_FORWARD` as a literal, or the subset
  assertion breaks — which is the point of that assertion.
"""

ASYMMETRY_NEGATIVE: Final[tuple[tuple[str, str], ...]] = (("claude-opus", "gpt-5"),)
"""(writer, reviewer) model-id prefixes that carry the C-1036 caveat (D-b).

**Model FAMILIES, and the generalization is untested** — say so wherever this
is read. `ASYMMETRY_MEASURED` names the one pair the citation measured, and no
shipped `MODELS` table resolves either half of it: the tables resolve
`claude-haiku-4-5-20251001`, `claude-opus-5`, `gpt-5.6-luna`,
`github-copilot/gpt-5.6-luna` and `github-copilot/gpt-5.6-sol`, so an entry
pinned to the measured ids matched nothing on any of the four harnesses and the
warning could never fire. A
warning that cannot fire is worse than one that does not exist, because its
absence reads as evidence — the same principle the `provider/` prefix bug was
fixed under, one release earlier.

The families are therefore what is keyed, and `asymmetry_warning`'s text pays
for that by saying plainly which pair was measured and that extending it to the
family is not. An over-fire costs a human one sentence of context on a review
they were reading anyway; an under-fire silently drops the caveat.

Prefixes, not exact ids, so a point release does not silently stop matching.
Direction matters: the pair is asymmetric, and the reversed pair fires nothing,
because the paper's measured effect is in one direction only.
"""

ASYMMETRY_MEASURED: Final[tuple[str, str]] = ("claude-opus-4-7", "gpt-5.5")
"""The (writer, reviewer) ids the citation actually measured, verbatim (C-1036).

Kept beside the family table rather than folded into it, because the warning
has to name both: the family match is what fired, and this is the only pair any
measurement covers. Neither is resolvable from a shipped `MODELS` table, which
is exactly why the table above is keyed on families and this one is not.
"""

ASYMMETRY_CITATION: Final[str] = "arXiv:2607.21656"
"""The single citation the C-1036 warning carries, so the string has one home."""

SIGTERM_EXIT: Final[int] = 143
"""`128 + SIGTERM`, as a harness that traps SIGTERM and exits 143 itself reports it (C-1012).

The shell's convention, not the kernel's, and the distinction is the whole
scope of this constant. `Popen.wait()` reports a signal death as the NEGATIVE
signal number — `-15`, never 143 — so a child killed by nox and not trapping
the signal never reaches this mapping at all, and `reason_for_exit(-15)` is
`None`. That is correct rather than a gap: the supervisor already knows it
killed the child and carries `TIMED_OUT`, and mapping `-15` here would clobber
that with the mechanism. What 143 catches is the other half — a harness that
handled the signal, cleaned up and chose the conventional status.

Owned here rather than in `supervise` for the same reason.
"""

PROMPT_FILENAME: Final[str] = "prompt.md"
"""The prompt's name inside `Workspace.scratch`.

That directory is `mkdtemp`ed BESIDE the ephemeral worktree (C-1009, C-1019), so
it is nox-owned, outside the tree the harness is given, and a fixed name inside
it is not a collision the branch can arrange.
"""

PROMPT_ARGV_LIMIT: Final[int] = 128 << 10
"""Bytes above which a prompt may not be passed as an argv word.

**A property of the argv CHANNEL, not of nox** (E29). It is Linux's own
`MAX_ARG_STRLEN` — `PAGE_SIZE * 32`, the ceiling on a SINGLE argv word — so it
is not a policy anyone can raise, and it binds only where the prompt actually
rides argv. 128 KiB also sits an order of magnitude under a typical 2 MiB
`ARG_MAX` shared with the environment, so the refusal fires before the kernel's
does rather than as a `E2BIG` out of `Popen`.

The cap is what keeps the argv channel honest: C-1028 forbids the prompt
truncating, and a silent `E2BIG` or a shell-free `execve` truncation would drop
the anti-injection framing that lives at the end of the prompt.

**Which harnesses it binds, established live (2026-09-03) rather than assumed:**

| harness | prompt channel | evidence |
|---|---|---|
| `claude` | **stdin** | `echo … \\| claude --print --tools Read Grep Glob --` → exit 0 |
| `codex` | **stdin** | `--help` documents `-` as "read from stdin"; verified live |
| `copilot` | argv (`-p <text>`) | 1.0.82 `--help` offers no prompt file and no stdin form |
| `opencode` | argv (`run [message..]`) | positional message, no prompt-file flag |

So **this limit binds two of the four**, and `Launch.stdin_path` is what the
other two use instead. That matters because `review_prompt` renders
`Workspace.diff` into the prompt — the prompt IS the diff-delivery route — and
a whole-branch review is the first case that clears 128 KiB. Under a global cap
nox refused its own primary use case on every harness; under a per-channel one
it refuses only where the kernel would.

**The stdin channel carries no nox-imposed byte cap, deliberately, and the
reason is not that nothing is buffered.** It is: `workspace()` captures the
whole `git diff` into `Workspace.diff`, `prompt.render` builds the entire prompt
as one `str`, and `write_nofollow` encodes it again — three full copies of
branch-controlled bytes in nox's address space, all of them upstream of this
constant and all of them there before and after E29. A cap here would not bound
any of that; the place to bound it is the capture in `workspace()`, and no
version of nox has. What this channel would be capped AGAINST is the model's
context window, which is per-harness and per-model and not knowable from here.
An over-context prompt surfaces as the harness's own error and resolves through
the existing tri-state parse, which is a truthful answer; a guessed byte number
would instead refuse reviews that would have succeeded, which is the failure
this constant is being corrected for. C-1028 asks for a loud refusal, not an
early one.

ponytail: a fixed cap, not a probe of `sysconf(_SC_ARG_MAX)` minus the
environment. The upgrade path is that computation, the day a real prompt lands
between the two numbers.
"""

STDIN_PROMPT_HARNESSES: Final[str] = "claude, codex"
"""The harnesses whose prompt rides stdin, named in the argv refusal (E29).

A literal rather than a scan over `ADAPTERS`: `argv_prompt` is called from
inside `prepare`, and importing the adapter registry from here to answer a
message would invert the dependency the whole module is built on. The static
test in `tests/unit/test_prompt_channel.py` is what keeps it true — it asserts
the adapters it walks are exactly `ADAPTERS` (so a fifth cannot slip past the
guard), then that every name here sets `Launch.stdin_path` and no name outside
it does.
"""

PROBE_BUDGET_S: Final[float] = 60.0
"""Wall clock a whole `probe` is held to, in seconds (C-1014).

An adapter states its own, shorter bound — copilot's is 30 s — and this is what
holds when it does not. `Process.wait(None)` waits **indefinitely**, and the
probe runs before the workspace exists, so no `TimeoutPolicy` and no supervisor
is watching: an adapter that passed `None` would hang nox outright, with no
deadline anywhere else in the flow to catch it.

A **deadline** rather than a per-call cap, because a per-call cap is not a
bound: `while proc.wait(30.0) is None:` blocks forever under one and is the
loop any patient probe would be written as. Every wait is clamped to what is
left of the budget, so the whole probe is bounded however it spells its waiting.
"""

PROBE_GRACE_S: Final[float] = 5.0
"""Seconds between SIGTERM and SIGKILL when a probe child outlives its probe."""


# ── Types an adapter declares ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ContainmentPlan:
    """How THIS harness is stopped from writing to the repo or reaching the network.

    A *claim*, checked against reality by `derive_containment` (C-1025) before
    anything reads it as evidence. `None` on either axis means not established
    and refuses the launch (C-1007) — never a weaker level standing in.

    Both axes are about **writes and network reach**. Neither says anything
    about how long a descendant lives, and no adapter may imply otherwise: the
    process group is nox's lifetime primitive, it does not close the two holes
    `runner.py` names, and D-ac accepted that residual in text rather than
    adding a constant-valued third axis here.

    The two axes share one evidence set, so they **fall together**: a missing
    flag downgrades both, which is the conservative direction for a v1
    mechanism that is one thing (removing Bash removes writes and network; an
    OS sandbox constrains both). No adapter may read a single absent flag as
    affecting only one axis. ponytail: per-axis evidence is the upgrade path
    the day a harness holds the two by different primitives — copilot's
    `--experimental` MXC leg would be the first, and it is out of v1 scope.

    Attributes:
        mechanism: The harness's own primitive. Shares `outcome.Mechanism` with
            `Containment.mechanism` so the plan and the stamp cannot drift, and
            it is itself corroborated: `derive_containment` requires the kind of
            evidence the named mechanism implies.
        write_enforcement: How strongly repository writes are prevented — not
            whether they are claimed to be.
        network_enforcement: The same for network reach.
        argv_evidence: The argv words that corroborate this plan, **verbatim
            and in order**, as they must appear contiguously in the final argv.
            An ordered run rather than a set because the words that matter
            carry values: `("--tools", "Read", "Grep", "Glob")` is a claim
            about the whole tool list, and a set-membership test would pass an
            argv that also carried `Bash`.
        env_evidence: Environment NAME → exact VALUE for a plan whose primitive
            is a config the harness reads from the environment. Values, not
            names: `OPENCODE_CONFIG_CONTENT="{}"` is present under a
            names-only check while denying nothing. This mapping is also the
            *only* environment an adapter may add — `authorize` refuses any
            other key, so the C-1008 minimal environment cannot be widened
            through the launch path.
    """

    mechanism: Mechanism
    write_enforcement: Enforcement | None
    network_enforcement: Enforcement | None
    argv_evidence: tuple[str, ...] = ()
    env_evidence: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        """Freeze `env_evidence` behind a read-only view.

        Same reason `Invocation` freezes its `env`: this mapping is read as
        evidence and used as the whitelist of environment keys a launch may
        add, and a frozen dataclass holding a caller's live `dict` promises an
        immutability it does not have.
        """
        object.__setattr__(self, "env_evidence", MappingProxyType(dict(self.env_evidence)))


@dataclass(frozen=True, slots=True)
class HarnessInfo:
    """What a probe established about one harness (C-1014, C-1020).

    Attributes:
        name: The `ADAPTERS` registry key.
        version: The probed version, or `None` when the harness ran but named
            no version.
        verified_against: The version this adapter's fixtures were recorded
            from — set from a re-probe with the `--help` committed as a
            fixture, never copied from a document (E3). A mismatch warns and
            continues; it never refuses (C-1020).
        capabilities: What the harness was established to support. Absence is
            the default and there is no permissive fallback to omit into.
        heartbeat_kind: Which C-1010 silence window applies.
        launcher: How the binary is reached — a prefix for a harness with no
            binary on `PATH`.
    """

    name: str
    version: str | None
    verified_against: str
    capabilities: frozenset[Capability]
    heartbeat_kind: Liveness
    launcher: Launcher

    def __post_init__(self) -> None:
        """Refuse a `capabilities` set holding anything but parsed `Capability` members, and copy it.

        The copy is the same reason `ContainmentPlan.env_evidence` and
        `Launch.env` wrap one: a frozen dataclass holding a caller's live `set`
        promises an immutability it does not have, and this is the collection
        the C-1013 gate reads.

        The single choke point for WP1's finding, and the reason
        `check_capabilities` can be a one-line subtraction. `Capability` is a
        `StrEnum`, so its members hash and compare equal to their own values:
        `REQUIRED <= {"enumerable_deny"}` is **True**, and a harness that
        declared nothing but happened to carry the right string would sail
        through the C-1013 gate. Refusing the string at construction is
        cheaper than teaching every comparison site to distrust its input.

        Raises:
            ValueError: Any member is not a `Capability`.
        """
        # Cast to `object` rather than annotate: the hazard IS a caller whose
        # set does not hold what the annotation promises, so this is the one
        # guard that must distrust its own declared type — and pyright narrows
        # an annotated assignment straight back to it.
        declared = cast("Iterable[object]", self.capabilities)
        unparsed = sorted(repr(member) for member in declared if not isinstance(member, Capability))
        if unparsed:
            raise ValueError(f"capabilities must be parsed Capability members: {', '.join(unparsed)}")
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))


@dataclass(frozen=True, slots=True)
class Launch:
    """What `prepare` returns: argv words and the environment its plan declared.

    Not an `Invocation`, and that is the point. An `Invocation` is spawnable
    and carries `cwd` and the whole environment, so an adapter returning one
    could point `cwd` at the live repository or re-add a credential variable
    C-1008 dropped — neither of which any gate downstream inspects. A `Launch`
    can express neither: `authorize` sets `cwd` to the workspace and merges
    `env` over the C-1008 environment after refusing every key the plan did not
    declare as evidence.

    Attributes:
        argv: The harness-level argv — its subcommand, the policed passthrough
            and nox's own flags, in that order. `authorize` prepends the
            resolved launcher and the absolute `argv[0]`, so an adapter never
            spells either.
        env: Environment additions this harness's containment needs. Every key
            must appear in the plan's `env_evidence` with the same value.
        stdin_path: The prompt file to hand this harness on **stdin**, or
            `None` for the argv channel and `DEVNULL`. An adapter whose harness
            reads its prompt from stdin sets it to the path `review_prompt`
            returned and emits no prompt word; `authorize` refuses any path that
            is not directly inside `Workspace.scratch`, so this is a choice of
            channel and never a choice of file (C-1028).
    """

    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    stdin_path: Path | None = None

    def __post_init__(self) -> None:
        """Freeze `env` behind a read-only view."""
        object.__setattr__(self, "env", MappingProxyType(dict(self.env)))


_STATUSES: Final[tuple[Status, ...]] = get_args(Status)
"""The three recognized outcomes, read off the `Literal` rather than restated.

Derived here as well as in `outcome`, from the same `Literal`, because the check
belongs at both types and a derivation cannot drift the way a restated tuple can.
"""


@dataclass(frozen=True, slots=True)
class ParsedOutput:
    """What an adapter's `parse` establishes from the harness's own output.

    Deviation from the ADR's `parse(...) -> Review`, and the reason for it is
    C-1025: a `Review` carries a `Containment`, `Containment` is DERIVED by
    core from the resolved argv, and an adapter returning a whole `Review`
    would have to name a containment value it is structurally forbidden to
    know. `NOT_RUN` is not available as a placeholder either — it means "no
    harness ran", which is the opposite of what a parse result reports. So
    `parse` returns what it actually establishes and `api.review()` assembles
    the `Review` around it.

    The tri-state invariants are enforced here rather than restated at every
    adapter's return sites (C-1011): `verdict` is set iff `status == "ok"`, and
    `reason` is set iff it is not. An adapter that reaches a success return by
    elimination therefore cannot express it. Every `Finding.file` is normalized
    through `safe_finding_file` here too, so the C-1019 traversal check happens
    once rather than in four adapters (WP1's row).

    Attributes:
        status: Tri-state outcome. The exit code never gates it.
        verdict: Present only when `status == "ok"`.
        findings: Reported issues — untrusted harness output (C-1019).
        summary: The harness's own prose summary; empty when it produced none.
        detail: nox's OWN account of a non-`ok` outcome, including the raw
            error name stamped when `classify` returned `None`.
        raw: The harness's output as the supervisor delivered it, retained
            unconditionally (C-1018). The 8 MiB byte cap may already have cut
            it; that fact travels separately as `Supervision.truncated`, never
            by shortening this. Core scans it for credential shapes; nothing
            here redacts it.
        reason: Non-`None` iff `status != "ok"`.
        cost_usd: Cost, where the harness reports one.
    """

    status: Status
    verdict: Verdict | None
    findings: tuple[Finding, ...]
    summary: str
    detail: str | None
    raw: str
    reason: FailureReason | None
    cost_usd: float | None = None

    def __post_init__(self) -> None:
        """Enforce the tri-state invariants and normalize every `Finding.file` and `Finding.severity`.

        Both normalizations are untrusted-output duties WP1's row made this
        class's, and both fail toward the safe answer: `safe_finding_file`
        drops a path that points outside the worktree, `to_severity` resolves
        an invented word to `block`. Doing them here rather than at four
        adapters' return sites is what makes them properties of the type.

        **The domain check comes first, and refuses rather than coerces** — the
        same check `outcome.Review` makes, at the earlier type, because this is
        where an invented word enters. The other two invariants derive from
        `status == "ok"`, so a word an adapter made up satisfies both: `verdict`
        unset with a `reason` set is exactly what a non-`ok` outcome looks like.
        Without this it left `parse` unchallenged and was caught one type later,
        if at all. It belongs on the type for the reason `Review` gives — what a
        `status` may BE is the type's own business, unlike flattening `detail`,
        which is a boundary duty and stays at `api`'s two assembly sites.

        `reason` is type-checked for the same reason and not merely for
        presence: the two tri-state tests below ask `is not None` and never what
        arrived, so an adapter returning the WIRE STRING rather than the member
        satisfied both, and `cli.to_json`'s `reason.value` then ended the shell
        in an `AttributeError` — the traceback-instead-of-an-answer shape
        `cli.main`'s `.get` default exists to prevent, on the other output path
        from the same untrusted source. `FailureReason` is a `StrEnum`, so its
        members pass this and a bare `str` does not.

        Raises:
            ValueError: `status` is outside the tri-state, `reason` is neither a
                `FailureReason` nor `None`, `verdict` is not set exactly when
                `status == "ok"`, or `reason` is not set exactly when it is not.
        """
        if self.status not in _STATUSES:
            raise ValueError(f"status is one of {_STATUSES}; got status={self.status!r}")
        # Cast to `object` rather than trust the annotation, the same way
        # `HarnessInfo.__post_init__` does: the hazard IS an adapter whose value
        # is not what it declared, so this guard has to distrust its own type.
        if not isinstance(cast("object", self.reason), FailureReason | None):
            raise ValueError(f"reason is a FailureReason or None; got reason={self.reason!r}")
        ok = self.status == "ok"
        if (self.verdict is not None) != ok:
            raise ValueError(f"verdict is set iff status is 'ok'; got status={self.status!r} verdict={self.verdict!r}")
        if (self.reason is not None) == ok:
            raise ValueError(f"reason is set iff status is not 'ok'; got status={self.status!r} reason={self.reason!r}")
        located = tuple(
            replace(item, file=safe_finding_file(item.file), severity=to_severity(item.severity))
            for item in self.findings
        )
        object.__setattr__(self, "findings", located)


class Adapter(Protocol):
    """One harness, behind seven methods and four class-level tables (SD § 9.3).

    An adapter is not trusted; it is *constrained*. It never spawns the review,
    never states its own containment as fact, and never builds instruction
    text. What it owns is the shape of one harness's argv, its output dialect
    and its evidence-backed error table — the three things nothing else can
    know.

    Adding one is four steps with no core change: implement this protocol,
    declare a `HarnessInfo` whose `capabilities` omit everything unverified,
    pin `verified_against` from a probe, and add one `ADAPTERS` entry. A
    `PASSTHROUGH_ALLOW` entry and a `CLASSIFY` table both default to empty,
    which means "refuse everything" and "resolve `indeterminate`" — an
    incomplete adapter is safe rather than permissive.

    That last sentence was false for `PASSTHROUGH_ALLOW` and is stated here
    because it is the kind of claim nothing runs: `police_passthrough` looked
    the key up without a default and raised on a miss, and every `prepare`
    calls it, so a correctly registered fifth adapter refused every review with
    a `ConfigError` naming an "unknown harness" it was not. Nothing caught it
    because every stub borrowed a shipped key. `tests/unit/stubs.py::FifthStub`
    is registered and named by no core literal, and a test walks it from
    `load` through `authorize` — the claim is now executed rather than written.
    """

    name: ClassVar[str]
    """The `ADAPTERS` registry key. Also the `PASSTHROUGH_ALLOW` key."""

    BINARY: ClassVar[str]
    """The executable this harness is spawned as, before any launcher prefix.

    Declared rather than read off `HarnessInfo.launcher`, because the contract
    tier has to name the binary in its C-1037(2) failure message for a harness
    whose probe never returned a `HarnessInfo` at all.
    """

    MODELS: ClassVar[Mapping[ModelClass, ModelSpec]]
    """Capability class → this harness's literal (C-1030).

    A class with no entry is not an error: `resolve_model` takes the harness
    default and records `Review.model = None` with `model_class` intact
    (rule 6, kept without a capability bit — D-f).
    """

    CONFIG_READS: ClassVar[tuple[str, ...]]
    """User-level config files this harness reads, as `${VAR}`-expandable paths.

    Hashed into the C-1025 probe digest, so a user editing
    `~/.codex/config.toml` is a cache miss rather than a stale pass on a
    sandbox probe that ran under different configuration.

    Expanded against the C-1008 minimal environment, in declaration order, so
    an adapter can state the precedence it knows: `("${CODEX_HOME}/config.toml",
    "${HOME}/.codex/config.toml")`. `CODEX_HOME`, `CLAUDE_CONFIG_DIR` and
    `XDG_CONFIG_HOME` are all on the C-1008 allowlist and all forwarded, so a
    plain `$HOME`-relative path would hash a file the harness is not reading
    and cache a pass across the edit that invalidated it.

    An empty tuple is a positive claim that this harness reads no user-level
    config — unlike the `PASSTHROUGH_ALLOW` and `CLASSIFY` empties, it is the
    *unsafe* default, so assert it rather than leaving it unwritten.
    """

    def probe(self, runner: Runner, cfg: HarnessConfig, env: Mapping[str, str], cwd: Path) -> HarnessInfo:
        """Establish that this harness is present and usable (C-1014).

        A real short invocation through the launcher — never `shutil.which`
        alone, which cannot tell a binary that exists from one that runs.

        Never called directly on the review path: `probe_harness` is the one
        sanctioned route, and it is what mints `cwd`.

        `cwd` is minted and removed by core (`probe_cwd`), not by the adapter:
        it is a fresh empty directory, because a `--version` is a harness
        startup and OpenCode executes `.opencode/plugins/` on any startup. An
        inherited cwd would run attacker JavaScript with Bun shell access in
        the user's live tree, before the workspace existed — the sharpest edge
        in the design (SD § 6.3), and far too sharp to leave to four adapters
        each remembering to mint a directory.

        Args:
            runner: The process seam. The adapter never touches `subprocess`.
            cfg: This harness's config, for its launcher prefix.
            env: The C-1008 minimal environment, built once before this call.
            cwd: A fresh empty directory nox owns.

        Returns:
            What the probe established.

        Raises:
            HarnessUnavailable: Absent, unauthenticated, or reachable only
                through a launcher that escapes the process group (C-1009).
        """
        ...

    def sandbox_probe(self, runner: Runner, ws: Workspace, info: HarnessInfo, env: Mapping[str, str]) -> bool:
        """Prove this harness's OS-level enforcement actually holds (C-1025, C-1040).

        The only writer of `ProbeCache`, and the reason an `os` claim is not
        self-certifying. Codex's is C-1040's four-step sequence: a listener on
        an ephemeral port, a review whose prompt instructs exactly two shell
        attempts, the write attempt observed not to have created its file, and
        the connect attempt observed not to have reached the listener — with a
        `command_execution` item required as evidence for BOTH attempts, since
        a model that merely *declined* to run a command is indistinguishable
        from a blocked one except by that item's absence.

        Every adapter that does not claim an `os` axis returns `False` in one
        line. That is what makes "a harness with no sandbox probe cannot reach
        `os`" a property of the protocol rather than a rule to remember: the
        default answer is refusal, and `derive_containment` downgrades the axis.

        Args:
            runner: The process seam.
            ws: The live workspace the probe runs inside.
            info: What `probe` established.
            env: The C-1008 minimal environment.

        Returns:
            `True` only when every observation the adapter's probe requires
            passed. An inconclusive probe is `False` — never a silent
            unsandboxed run.
        """
        ...

    def containment_plan(self, cfg: HarnessConfig, info: HarnessInfo) -> ContainmentPlan:
        """Claim how this harness is held, and name the evidence for it (C-1007).

        Queried BEFORE argv is assembled, so the refusal path is reachable
        without constructing an invocation at all — an adapter cannot smuggle
        containment into its argv builder and assert it afterwards.

        Args:
            cfg: This harness's config.
            info: What the probe established.

        Returns:
            The claim, with the argv run and environment values that
            corroborate it. `derive_containment` checks both against the launch
            `prepare` actually built.
        """
        ...

    def prepare(
        self,
        ws: Workspace,
        info: HarnessInfo,
        cfg: HarnessConfig,
        instructions: str | None,
    ) -> Launch:
        """Build the harness-level launch for one review (E9a, C-1023).

        Called after the workspace exists, because `cwd` IS the workspace.
        Three obligations, each of which `authorize` also checks:

        - deliver the prompt through `review_prompt`, which writes it into
          `ws.scratch` and returns its path together with its text. **Which of
          the two an adapter uses is decided by its harness, not by taste**
          (E29). A harness that reads the prompt from stdin (`claude`, `codex`)
          takes the PATH and returns it as `Launch.stdin_path`; one that has
          only an argv word (`copilot`, `opencode`) takes the TEXT through
          **`argv_prompt`**, which is what enforces `PROMPT_ARGV_LIMIT` —
          passing `text` straight into the argv is that route without its bound.
          Declaring a `stdin_path` on a harness that does not read stdin hands
          it an empty ask; putting the prompt on argv where stdin exists caps a
          whole-branch review at the kernel's `MAX_ARG_STRLEN` for nothing. The
          path is NOT a channel for a harness that merely reads files: C-1019
          puts `ws.scratch` beside the worktree, so an adapter naming it in argv
          would owe a check that the harness can read outside its own `cwd`.
        - compose argv as
          `(*subcommand, *police_passthrough(name, cfg.passthrough, nox_flags))`.
          Passthrough goes after the subcommand and before nox's own flags, so
          a last-wins harness resolves nox's containment flags and not the
          repository's. The launcher and the absolute `argv[0]` are
          `authorize`'s, not the adapter's.
        - emit every word of `plan.argv_evidence` contiguously, and every
          `plan.env_evidence` entry in `Launch.env`. Nothing else may go in
          `env`: `authorize` refuses a key the plan did not declare, which is
          what stops a launch widening the C-1008 environment.

        The scope is `ws.scope` and is not a parameter: the WP2 follow-up put
        it on `Workspace`, and a second source for one fact is the drift this
        module exists to prevent. An adapter that needs it reads it there.

        Args:
            ws: The live ephemeral worktree and its evidence.
            info: What the probe established.
            cfg: This harness's config.
            instructions: Extra instruction text from nox's OWN caller, or
                `None`. Never populated from repository content — C-1005
                deletes `CLAUDE.md` and `AGENTS.md` precisely so repo-authored
                instructions cannot reach the reviewer.

        Returns:
            The harness-level launch. `authorize` turns it into the
            `Invocation` core spawns.

        Raises:
            ConfigError: A refused `passthrough` element (C-1023), or a prompt
                that must ride argv and exceeds `PROMPT_ARGV_LIMIT`.
        """
        ...

    def on_line(self, line: str) -> bool:
        """Answer whether one output line was a *semantic* progress event (C-1010).

        `supervise`'s `on_line` seam, and a protocol member rather than
        something WP8 supplies, because the adapter is the only thing that
        knows the dialect: a stack trace, a progress bar or a Node deprecation
        warning is bytes without progress. The consequence of the seam having
        no owner is not cosmetic — `Heartbeat.touch` advances
        `last_activity_at` only on a `True`, and `supervise` measures the
        C-1010 silence window against that timestamp for every kind but
        `BYTE_ACTIVITY`, so a `SEMANTIC` harness whose lines nobody classifies
        is killed at `silence_s` while it is still working.

        Answered **honestly**, never to keep a clock alive: a `BYTE_ACTIVITY`
        adapter returns `False` for its raw lines and its 300 s window still
        measures, because that window runs against `last_byte_at`. An adapter
        that answered `True` to stay alive would corrupt `Heartbeat.events`,
        which is the evidence a timeout detail is written from. Never touch
        `Heartbeat` from an adapter; this return value is the whole channel.

        Args:
            line: One line of the merged output stream.

        Returns:
            Whether the line was a structured event this harness emits to
            report progress.
        """
        ...

    def classify(self, err: Mapping[str, object]) -> FailureReason | None:
        """Map one observed error shape to a reason, or decline (C-1012).

        `None` means this harness does not distinguish the state — the run
        resolves `indeterminate` with the raw error name stamped. Never a
        substring guess: OpenCode's only observed error is a generic
        `UnknownError`, and substring-matching its message is not a contract
        the harness has to keep across a patch release.

        Args:
            err: One decoded error object from the harness's stream.

        Returns:
            The reason, or `None` where no recorded fixture proves the cell.
        """
        ...

    def parse(self, lines: Iterable[str], exit_code: int, hb: Heartbeat) -> ParsedOutput:
        """Resolve the harness's output to a tri-state result (C-1011).

        The one thing this may never do is reach a success return by
        elimination. The exit code is recorded and gates nothing —
        `reason_for_exit` maps 143 to `KILLED`, and every harness in v1 puts
        the failure kind in the stream rather than in the status. An untrusted
        severity word goes through `to_severity`, which fails toward `block`.

        Args:
            lines: The merged output stream, in order.
            exit_code: What the child exited with. A coarse hint only.
            hb: Progress evidence at the moment the run ended.

        Returns:
            What the output establishes.
        """
        ...


# ── The launch gate ──────────────────────────────────────────────────────────


def check_capabilities(info: HarnessInfo, plan: ContainmentPlan) -> None:
    """Refuse the launch unless every required capability and both axes hold.

    The C-1013 and C-1007 gates in one place, so "raises on a missing required
    capability" is one behaviour rather than a discipline each adapter keeps.
    `plan` must be the DERIVED plan; `authorize` is the only caller on the
    review path and it passes `derive_containment`'s output, so a claim can
    never be checked against itself.

    Comparison is over parsed `Capability` members. `HarnessInfo.__post_init__`
    guarantees the set holds nothing else, which matters because `Capability`
    is a `StrEnum` whose members hash equal to their values — a raw-string set
    would satisfy `REQUIRED <= …` while declaring nothing.

    Args:
        info: What the probe established.
        plan: The plan AFTER `derive_containment`.

    Raises:
        UnsupportedCapability: A member of `REQUIRED` is absent, or either
            enforcement axis is `None`. The message names what is missing —
            an operator reading it needs the axis, not the fact of a refusal.
    """
    _require_capabilities(info)
    axes = [
        axis
        for axis, level in (("write", plan.write_enforcement), ("network", plan.network_enforcement))
        if level is None
    ]
    if axes:
        raise UnsupportedCapability(
            f"{info.name}: containment not established on {' and '.join(axes)} enforcement (C-1007)"
        )


def _require_capabilities(info: HarnessInfo) -> None:
    """Refuse unless every member of `REQUIRED` was established (C-1013).

    Split out of `check_capabilities` so `authorize` can run this half FIRST,
    before `adapter.sandbox_probe`: C-1040's probe is a full review-shaped
    spawn, and SD § 7.1 puts both `UNSUPPORTED` rows at "no harness spawned".
    The axis half stays where it is, because the axes are only knowable after
    derivation.

    Args:
        info: What the probe established.

    Raises:
        UnsupportedCapability: A member of `REQUIRED` is absent, named.
    """
    missing = sorted(capability.value for capability in REQUIRED - info.capabilities)
    if missing:
        raise UnsupportedCapability(f"{info.name}: required capability not established (C-1013): {', '.join(missing)}")


def enforced_read_only(info: HarnessInfo) -> bool:
    """Whether `ENFORCED_READ_ONLY` was established, for the C-1013 stamp.

    The capability→stamp mapping lives here, beside the `structured_output`
    one `review_prompt` makes, so both are read off `info.capabilities` rather
    than hand-set at a call site. OpenCode omits the capability and still
    launches: `REQUIRED` does not contain it, and the run is stamped `False`
    rather than refused.

    Args:
        info: What the probe established.

    Returns:
        Whether the capability is present.
    """
    return Capability.ENFORCED_READ_ONLY in info.capabilities


def police_passthrough(harness: str, passthrough: Sequence[str], nox_flags: Sequence[str]) -> tuple[str, ...]:
    """Vet `passthrough` against the C-1023 allowlist and compose the argv tail.

    Composition and policing are one call because the ordering rule and the
    duplicate rule need the same two inputs: passthrough goes FIRST and nox's
    own flags LAST (so a last-wins harness resolves nox's containment flags,
    not the repository's), and a passthrough copy of a flag nox emits is
    refused rather than silently duplicated. Splitting them left the ordering
    to whoever wrote the adapter.

    Five refusals, each naming the offending element:

    1. a `DENIED_FLAGS` member, in ANY of its spellings — bare, on the token
       before `=`, and (for a short flag) with its value attached. A denied
       capability reachable under a second spelling is the same hole with a
       different name, which is why the match is `_names_option` and not
       set membership;
    2. a flag outside `PASSTHROUGH_ALLOW[harness]`;
    3. a bare word that does not follow an allowed flag — a positional is not
       an inert flag, and `opencode run [message..]` takes its prompt as one;
    4. a duplicate of a flag `nox_flags` already carries, compared on the token
       before `=` on BOTH sides — `--color=ours` and `--color ours` are the
       same flag to the harness, and a check symmetric on only one side lets
       the repository re-specify a flag nox owns;
    5. a trailing value-taking flag with no value. Without it the harness binds
       nox's OWN first flag as the passthrough flag's value: `["--color"]`
       ahead of `["-c", "sandbox_mode=read-only"]` makes `-c` the colour setting
       and leaves the sandbox word a stray positional, while derivation still
       finds the word contiguous and stamps the axis.

    Refusals 2-5 are unreachable while every `PASSTHROUGH_ALLOW` set is empty,
    which is today's shipped state — refusal 2 answers everything first. They
    are the gate for the next entry, and the examples above use `--color`
    because it is a real, containment-inert `codex exec` flag rather than an
    invented one.

    Args:
        harness: The registry key, for the allowlist entry.
        passthrough: The configured words, in order.
        nox_flags: The FLAG TAIL nox itself emits for this launch — not the
            whole argv. A subcommand or an executable path passed here would
            join the duplicate check as if it were a flag, and would land after
            the passthrough in the result.

    Returns:
        `(*passthrough, *nox_flags)`.

    **A key with no entry gets the empty allowlist**, which refuses every word
    by name and passes nothing through. This raised instead, and that one
    `.get` returning `None` was the whole of what made `Adapter`'s "adding one
    is four steps with no core change" false: every `prepare` calls this
    unconditionally, so a fifth adapter hard-failed every review it could run
    until someone edited a literal in this module. The empty default is not a
    weakening — it *is* the "refuse everything" the same docstring already
    promised — and it is the only reading under which the extension point can
    be true, because this module may not import `nox.adapters` to consult the
    registry: the dependency runs the other way (see `STDIN_PROMPT_HARNESSES`).
    An unknown key is the REGISTRY's refusal, and `adapters.load` raises it from
    `ADAPTERS` before any adapter is constructed — which is also where the
    repository-supplied `[review] harness` is kept out of `detail` (C-1035(1)).
    The `harness` this function is given is an adapter's own `name` ClassVar,
    already past that gate.

    Raises:
        ConfigError: Any of the five refusals. The message names the offending
            element and the harness it was refused for; both are nox-side
            strings by the time this runs.
    """
    allowed = PASSTHROUGH_ALLOW.get(harness, frozenset())
    nox_owned = frozenset(word.split("=", 1)[0] for word in nox_flags if word.startswith("-"))
    pending: str | None = None
    for word in passthrough:
        flag = word.split("=", 1)[0]
        denied = _named_flag(word, DENIED_FLAGS)
        if denied is not None:
            raise ConfigError(f"passthrough: {denied} is refused unconditionally (C-1023)")
        if not word.startswith("-"):
            # A positional is not an inert flag: `opencode run [message..]`
            # takes the whole review prompt as one.
            if pending is None:
                raise ConfigError(f"passthrough: {word} is a positional, not an allowed flag's value (C-1023)")
            pending = None
            continue
        if flag not in allowed:
            raise ConfigError(f"passthrough: {flag} is not allowed for {harness} (C-1023)")
        if flag in nox_owned:
            raise ConfigError(f"passthrough: {flag} duplicates a flag nox emits for this launch (C-1023)")
        # `--flag=value` carries its own value, so the next word is a fresh one.
        pending = flag if "=" not in word else None
    if pending is not None:
        # Otherwise the harness binds nox's own first flag as this one's value.
        raise ConfigError(f"passthrough: {pending} expects a value and none follows it (C-1023)")
    return (*passthrough, *nox_flags)


def resolve_executable(name: str, env: Mapping[str, str]) -> str:
    """Resolve `name` to an absolute realpath on the minimal environment's `PATH`.

    Nothing else validated `argv[0]` (raised by WP3 at merge). It matters
    because `cwd` is the ephemeral worktree, which is attacker-controlled
    content: a relative or empty `PATH` entry would resolve a harness name
    against it. `config.minimal_env` already drops empty, relative and in-repo
    entries, so this function reads that rebuilt `PATH` and never `os.environ`.

    Args:
        name: The executable to find.
        env: The C-1008 minimal environment.

    Returns:
        The absolute, symlink-resolved path.

    Raises:
        HarnessUnavailable: Not found on `PATH`, or found and not executable —
            `ABSENT` either way, which is the reason a consumer degrades to a
            graceful skip on (SD § 7.1).
    """
    found = shutil.which(name, path=env.get("PATH", ""))
    # `which` resolves a name carrying a separator against the CURRENT DIRECTORY
    # and ignores `path` entirely, and the current directory is the ephemeral
    # worktree — so a `./harness` would be attacker-supplied. Only an absolute
    # answer came off the rebuilt `PATH`.
    if found is None or not os.path.isabs(found):
        raise HarnessUnavailable(FailureReason.ABSENT, f"{name}: not found as an executable on the minimal PATH")
    return str(Path(found).resolve())


def launch_argv(launcher: Launcher, env: Mapping[str, str], *args: str) -> tuple[str, ...]:
    """Build a launch argv whose first word is a resolved absolute path.

    With a launcher prefix the resolved word is the PREFIX's head, not the
    harness binary: that is what `execve` actually runs, and the binary
    following the wrapper's `--` is resolved by the wrapper under its own
    rules.

    Args:
        launcher: The binary and its prefix.
        env: The C-1008 minimal environment.
        *args: The harness-level arguments.

    Returns:
        The full argv, `argv[0]` replaced with its realpath.

    Raises:
        HarnessUnavailable: The executable could not be resolved.
    """
    argv = launcher.argv(*args)
    return (resolve_executable(argv[0], env), *argv[1:])


@contextlib.contextmanager
def probe_cwd() -> Generator[Path]:
    """Mint a fresh empty directory for one probe, and remove it after (C-1014).

    Core's, not each adapter's. The property it buys — a harness startup never
    sees repository content — is invisible in review when it fails (a probe
    that inherited a cwd still returns a version), and its consequence is
    OpenCode executing `.opencode/plugins/` in the user's live tree.

    Yields:
        An empty directory nox owns.
    """
    with tempfile.TemporaryDirectory(prefix="nox-probe-") as path:
        yield Path(path)


def _no_event(line: str) -> bool:
    """Answer `False` for every line: the reaper reads no dialect.

    `supervise`'s `on_line` seam, for the one call that is not supervising a
    review. A probe's own output has already been consumed by the adapter, and
    a teardown that guessed at semantics would put an event count nothing reads
    into a `Heartbeat` nothing keeps.

    Args:
        line: One output line, discarded.

    Returns:
        `False`.
    """
    del line
    return False


REAP_POLICY: Final[TimeoutPolicy] = TimeoutPolicy(wall_clock_s=0, silence_s=None, grace_s=PROBE_GRACE_S)
"""The policy the teardown ladder runs under: no waiting, then SIGTERM → grace → SIGKILL.

`wall_clock_s=0` because the run being supervised is already over — this is the
ladder, not a supervision — and `silence_s=None` because a stream nobody is
reading a dialect out of testifies to nothing (`Liveness.PROCESS_ONLY`).
"""


class _BoundedProcess:
    """One probe child, with every wait clamped to what is left of the probe budget.

    The clamp is the whole class. `Process` is what an adapter's probe is handed
    and `wait(None)` is a member of it, so "a probe cannot block forever" has to
    be a property of the object rather than a rule in `probe`'s docstring — the
    same argument that makes `prepare` return a `Launch` instead of an
    `Invocation`. Against a shared deadline rather than per call, because a
    per-call cap bounds no probe that waits in a loop. The remaining members
    delegate untouched.
    """

    def __init__(self, inner: Process, deadline: float) -> None:
        self._inner = inner
        self._deadline = deadline

    def _left(self) -> float:
        """Seconds remaining of the probe's budget, never negative."""
        return max(0.0, self._deadline - time.monotonic())

    @property
    def pid(self) -> int:
        """The child's pid, which is also its process-group id."""
        return self._inner.pid

    @property
    def collector_failure(self) -> BaseException | None:
        """The exception that ended the drain thread, or `None`."""
        return self._inner.collector_failure

    @property
    def overflowed(self) -> bool:
        """Whether the drain thread stopped on an output ceiling."""
        return self._inner.overflowed

    def lines(self, timeout: float) -> tuple[str, ...]:
        """Drain queued lines, waiting at most the shorter of `timeout` and the budget.

        Args:
            timeout: The caller's requested wait.

        Returns:
            The lines drained this batch.
        """
        # Floored at one poll interval once the budget is spent. `lines` is the
        # pacing call in `supervise`'s loop, and a clamp to 0.0 turns that loop
        # into a 100%-CPU spin until the supervisor's own wall clock fires.
        #
        # ponytail: so a probe that spends its whole budget can still run on to
        # its own stated wall clock, polling. The bound that always holds is the
        # reap; the upgrade path is `probe_run` reading the remaining budget off
        # the runner, which costs an `isinstance` against this module's private
        # wrapper for a case only a hung harness reaches.
        return self._inner.lines(max(min(timeout, self._left()), min(timeout, POLL_S)))

    def wait(self, timeout: float | None) -> int | None:
        """Reap the child, waiting at most what is left of the budget.

        Args:
            timeout: The caller's requested wait; `None` means "indefinitely",
                which is exactly the call this seam exists to refuse.

        Returns:
            The exit status, or `None` if the child is still running.
        """
        left = self._left()
        return self._inner.wait(left if timeout is None else min(timeout, left))


class _ProbeRunner:
    """The `Runner` adapter code that core spawns is handed: bounded, and reaped after.

    Two duties, both of which have to sit here because nothing downstream can
    do them. The caller removes the directory the spawn ran in — `probe_cwd`'s
    scratch directory, or the workspace a sandbox probe used — so a child that
    outlived the call would have that directory `rmtree`'d out from under it,
    and the adapter cannot prevent it: `Process` carries no kill, and the ladder
    that owns one is `supervise`. This wrapper is the only thing that both sees
    every child and outlives the call.

    The reap IS `supervise`: a child that has already exited is reaped by
    `wait(0.0)` and never signalled, and one still running takes the same
    SIGTERM → grace → SIGKILL ladder every review takes. Reusing it rather than
    restating it is what keeps the two kill paths from drifting.

    `budget` is `None` for a spawn with no meaningful ceiling — C-1040's sandbox
    probe is a full review-shaped model turn, and a 60 s clamp there would fail
    it rather than bound it. Reaping still applies; only the clamp is dropped.
    """

    def __init__(self, inner: Runner, *, budget: float | None) -> None:
        self._inner = inner
        self._deadline = None if budget is None else time.monotonic() + budget
        self._spawned: list[Process] = []

    def spawn(self, inv: Invocation) -> Process:
        """Start `inv`, remember the child, and hand back a bounded view of it.

        The child remembered is the INNER one, so the teardown ladder runs
        against the real process: clamping the reap's own grace wait to a budget
        the probe has already spent would collapse SIGTERM → grace → SIGKILL
        into two signals with no grace between them.

        Args:
            inv: The fully-resolved launch.

        Returns:
            The running child, clamped to the remaining budget where there is one.
        """
        child = self._inner.spawn(inv)
        self._spawned.append(child)
        return child if self._deadline is None else _BoundedProcess(child, self._deadline)

    def reap(self) -> None:
        """Reap every child this spawn produced, killing any that is still running.

        Every child is attempted even after one fails, because the failure this
        method exists to prevent is a live process whose directory is about to
        go, and abandoning the rest of the list on the first `OSError` is that
        failure with one extra step.

        Raises:
            BaseException: The FIRST failure the ladder raised, after every
                child has been attempted — typically the `OSError` `_kill_group`
                deliberately propagates for anything but a child already gone.
                It replaces an exception the caller was already raising, and
                that is the intended direction: a `HarnessUnavailable` is a
                harness that is not there, while this is one that is, that nox
                could not stop, and whose directory is about to be removed.
        """
        failures: list[BaseException] = []
        for child in self._spawned:
            try:
                # `wait(0.0)` IS the reap for a child that has already exited —
                # `SubprocessProcess.wait` joins the drain thread behind it — and
                # skipping `supervise` there saves a `POLL_S` block per probe on
                # the path every healthy probe takes.
                if child.wait(0.0) is None:
                    supervise(child, REAP_POLICY, Heartbeat(Liveness.PROCESS_ONLY, 0.0, 0.0), _no_event)
            except Exception as exc:  # a failed reap must not hide the next child's
                failures.append(exc)
        if failures:
            raise failures[0]


def probe_run(
    runner: Runner, launcher: Launcher, env: Mapping[str, str], cwd: Path, *args: str, timeout_s: int
) -> tuple[Supervision, tuple[str, ...]]:
    """Run one short probe invocation under `supervise` and collect its output (C-1014).

    Core's, not each adapter's, because `spawn` then `lines()` then `wait()` is
    wrong in the same three ways every time and three of four adapters wrote it:

    - **it truncates.** `Process.lines` returns as soon as the queue is
      momentarily non-empty, while `Process.wait` is the call carrying the tail
      guarantee. Draining first therefore loses any probe whose output arrives
      in more than one chunk — `claude auth status` prints its object across
      eleven lines, and reading only the first made `logged_out` fail OPEN on a
      harness that positively reported no credential.
    - **it abandons a hung child.** Neither call signals anything, and
      `probe_harness`'s reap is a backstop, not a bound.
    - **it spends its timeout twice**, once per call, so the probe's stated
      bound is not the one it keeps.

    `Liveness.PROCESS_ONLY` regardless of what the harness declares: a
    `--version` that prints one line and exits is silent by construction, and
    `SILENCE_S[PROCESS_ONLY]` is `None`, so no silence window is measured
    against it. `on_line` is not consulted for the same reason — it answers for
    the review dialect, and this is not one.

    Args:
        runner: The process seam.
        launcher: How the binary is reached.
        env: The C-1008 minimal environment.
        cwd: The empty directory `probe_harness` minted.
        *args: The harness-level arguments.
        timeout_s: This harness's own wall clock for one probe invocation,
            itself capped at `PROBE_BUDGET_S` — an adapter may ask for less than
            core's ceiling and never for more.

    Returns:
        `(supervision, lines)`. `Supervision.exit_code` is `None` whenever
        `supervise` forced the outcome — the wall clock elapsing, the output cap,
        a dead drain thread — which a caller reads exactly as it reads a non-zero
        status. So `exit_code == 0` means the harness exited cleanly and nothing
        else, which is the only reading a probe may build a `HarnessInfo` on.

    Raises:
        HarnessUnavailable: `argv[0]` is not on the minimal `PATH` (`ABSENT`) —
            which is what makes this more than `shutil.which`.
    """
    collected: list[str] = []

    def collect(line: str) -> bool:
        collected.append(line)
        return False

    supervision = supervise(
        runner.spawn(Invocation(argv=launch_argv(launcher, env, *args), cwd=cwd, env=env)),
        TimeoutPolicy.for_kind(Liveness.PROCESS_ONLY, min(timeout_s, int(PROBE_BUDGET_S))),
        Heartbeat(kind=Liveness.PROCESS_ONLY, last_activity_at=0.0, last_byte_at=0.0),
        collect,
    )
    if supervision.reason is not None:
        # A supervised failure is not a clean exit, whatever status the ladder
        # collected. `supervise`'s own `finally` reassigns `exit_code` from the
        # post-SIGTERM reap, so a harness that traps the signal and exits 0
        # arrives here as `exit_code=0, reason=TIMED_OUT` — and every caller
        # reads only the status. That reads a timed-out probe as a clean one on
        # a partial banner, and `logged_out` on a truncated `auth status` fails
        # OPEN. The overflow and collector-failure breaks are the same shape.
        supervision = replace(supervision, exit_code=None)
    return supervision, tuple(collected)


def probe_harness(adapter: Adapter, runner: Runner, cfg: HarnessConfig, env: Mapping[str, str]) -> HarnessInfo:
    """Run one adapter's probe in a nox-minted empty directory, bounded and reaped (C-1014).

    **The only sanctioned route to `Adapter.probe`.** `probe_cwd` is a free
    context manager and `probe` takes any path, so without this wrapper nothing
    stops a caller passing the repository root — which is OpenCode executing
    `.opencode/plugins/` in the user's live tree with Bun shell access, before
    the workspace exists (SD § 6.3). Same shape as `authorize`: the property is
    structural because there is one producer, not because a call site
    remembered.

    The runner the adapter sees is wrapped, for the two halves of one gap: every
    wait is clamped to what is left of `PROBE_BUDGET_S`, and every child the
    probe spawned is reaped **before** `probe_cwd` removes the scratch
    directory. Without the second, a probe that gave up on a hung harness —
    copilot's `wait(PROBE_TIMEOUT_S)` returning `None` is the shipped case —
    leaves a live process whose cwd is `rmtree`'d out from under it. The reap
    runs from a `finally`, so it covers the `HarnessUnavailable` path too, which
    is the path that has a live child.

    What this does NOT establish is that nothing survives the probe. The reap
    signals the child's process group, so D-ac's two holes are open here exactly
    as they are on the review path: a descendant backgrounded across a clean
    exit is never signalled at all, and one that called `setsid()` is outside
    the group. `.opencode/plugins/` running on a `--version` is why the cwd is
    minted empty; the reap does not make it survivable.

    Args:
        adapter: The selected adapter.
        runner: The process seam.
        cfg: This harness's config, for its launcher prefix.
        env: The C-1008 minimal environment, built once before this call.

    Returns:
        What the probe established.

    Raises:
        HarnessUnavailable: Absent, unauthenticated, or reachable only through
            a launcher that escapes the process group (C-1009).
    """
    bounded = _ProbeRunner(runner, budget=PROBE_BUDGET_S)
    with probe_cwd() as cwd:
        try:
            return adapter.probe(bounded, cfg, env, cwd)
        finally:
            bounded.reap()


# ── C-1025: containment is derived, never asserted ───────────────────────────


def config_read_paths(config_reads: Sequence[str], env: Mapping[str, str]) -> tuple[Path, ...]:
    """Expand an adapter's `CONFIG_READS` against the minimal environment.

    Args:
        config_reads: `${VAR}`-bearing paths, in declaration order.
        env: The C-1008 minimal environment.

    Returns:
        The expanded paths, in the same order. An entry naming a variable the
        environment does not carry is dropped — it names a file that cannot
        exist on this run — and the drop is itself a digest factor, so gaining
        the variable is a cache miss.

    Raises:
        ValueError: An entry is not a well-formed `${VAR}` template, or expands
            to a relative path or one carrying a `..` component. A config path
            is a shipped literal, so all three are adapter bugs rather than
            input, and a digest over a path that walks out of the config root
            proves nothing about what was read. `string.Template` raises its own
            `ValueError` on a malformed placeholder (`"$"`, `"${}"`), which is
            re-raised in this function's own shape so the one documented
            exception type is the only one a caller sees.
    """
    expanded: list[Path] = []
    for entry in config_reads:
        try:
            path = Path(string.Template(entry).substitute(env))
        except KeyError:
            continue
        except ValueError as exc:
            raise ValueError(f"CONFIG_READS entry is not a well-formed template: {entry!r}") from exc
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError(f"CONFIG_READS entry is not an absolute path free of '..': {entry!r}")
        expanded.append(path)
    return tuple(expanded)


def _content_digest(path: Path) -> str:
    """Hash one file's bytes, or answer with a stable marker when there is no file.

    Args:
        path: The file to hash.

    Returns:
        A hexadecimal digest, or `"absent"` — six characters, so it can never
        be confused with a digest, and stable, so a declared-but-missing file
        does not move the probe digest on every run.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "absent"


def _pairs(mapping: Mapping[str, str]) -> tuple[str, ...]:
    """Flatten a mapping to key/value words in sorted key order, for the digest.

    Args:
        mapping: What to flatten.

    Returns:
        `(key, value, key, value, …)`, key-sorted so iteration order cannot
        move the digest.
    """
    return tuple(word for key in sorted(mapping) for word in (key, mapping[key]))


def probe_digest(
    *,
    plan: ContainmentPlan,
    executable: str,
    launcher: Launcher,
    env: Mapping[str, str],
    config_reads: Sequence[Path],
) -> str:
    """Key a cached probe result on everything that could invalidate it (C-1025).

    Keyed on the PLAN, not on a caller-chosen argv slice. `plan.argv_evidence`
    is the containment-bearing run and nothing else, so the digest is stable
    across reviews — keying on a whole argv, which carries per-run words like a
    fresh scratch path, would miss the cache on every single run and make the
    `os` level unreachable in practice. It also means the digest computed
    before a sandbox probe and the digest computed at derivation are identical
    by construction rather than by two call sites agreeing.

    Every factor is one a passing sandbox probe depends on, and a change in any
    of them is a cache MISS rather than a stale pass:

    - the executable's realpath **and the hash of its bytes** — a harness
      upgrade in place keeps the path. Under a launcher this factor is the
      PREFIX's head (`ocx`), because that is what `execve` runs and what
      `launch_argv` resolved; the harness binary behind the wrapper's `--` is
      hashed by nothing here, so an in-place upgrade of a *wrapped* harness is
      NOT a cache miss. The launcher prefix and the `CONFIG_READS` contents are
      what move for that shape; the binary's own bytes are not, and this
      function does not claim otherwise. **That blind spot is not a stale pass,
      because `authorize` does not let this digest be reused across launches
      when the launcher has a prefix** (CG1): the artifact an opaque wrapper
      resolves is not addressable from here, so the answer is a per-launch
      cache rather than a key pretending to cover something it cannot see;
    - the platform, because an OS sandbox is an OS behaviour;
    - the launcher prefix, because the C-1009 session check is a property of
      the wrapper as much as the binary;
    - the plan's argv and env evidence, because the probe proved *that*
      containment;
    - the minimal environment, because the probe ran under it;
    - the content of every expanded `CONFIG_READS` file. This is the factor the
      obvious version of this function omits: a user-level `~/.codex/config.toml`
      can change the very posture the probe observed, and a digest that ignored
      it would cache a pass across the edit that invalidated it. A declared file
      that does not exist hashes as a distinct absent-marker, so creating it is
      also a miss.

    Args:
        plan: The adapter's claim, whose evidence is the containment key.
        executable: The resolved absolute path of what will be spawned.
        launcher: The launcher, for its prefix.
        env: The C-1008 minimal environment.
        config_reads: Already expanded by `config_read_paths`.

    Returns:
        A hexadecimal digest.
    """
    evidence_pairs = _pairs(plan.env_evidence)
    env_pairs = _pairs(env)
    words = [
        "platform",
        sysconfig.get_platform(),
        "executable",
        executable,
        _content_digest(Path(executable)),
        "launcher",
        launcher.binary,
        str(len(launcher.prefix)),
        *launcher.prefix,
        "argv-evidence",
        str(len(plan.argv_evidence)),
        *plan.argv_evidence,
        "env-evidence",
        str(len(evidence_pairs)),
        *evidence_pairs,
        "env",
        str(len(env_pairs)),
        *env_pairs,
    ]
    for path in config_reads:
        words += ("config-read", str(path), _content_digest(path))
    # Length-prefixed rather than joined on a separator: with a separator alone,
    # an evidence word spelled `env` would shift the words after it into the
    # environment's section and hash identically to a different launch. The
    # length prefix alone is not enough — the section MARKERS are unescaped
    # words in the same alphabet, so `argv_evidence=()` with an environment
    # carrying `env-evidence=env` digests exactly as `argv_evidence=
    # ("env-evidence", "env")` with an empty one. Each variable-length section
    # therefore carries its arity beside its marker, which fixes where the next
    # marker must fall and makes the encoding injective over the whole word list.
    blob = "".join(f"{len(word)}:{word}" for word in words)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ProbeCache:
    """Passing sandbox-probe digests for this process (C-1025).

    Deliberately not persisted. A cache that outlives the process is a trust
    store — it would have to be written somewhere a repository cannot reach,
    validated on read, and invalidated on a schema change, and it would let a
    pass recorded under one machine state authorize a launch under another.
    Every factor that could change is already in the digest, so a process-local
    cache is exactly as sound and costs one probe per `review()`.

    One exception, and it is the shape the digest cannot key: behind a
    **launcher**, `authorize` hands derivation a fresh cache per launch (CG1).
    An opaque wrapper resolves the harness itself, so no factor here moves when
    the wrapped target does, and a record made under one target would speak for
    another. Reuse is therefore for direct launches only.

    ponytail: in-memory, one probe per process. If the C-1040 probe's cost ever
    dominates a batch of reviews, the upgrade is a file under the user state
    dir with the digest as the key — not a wider key.
    """

    def __init__(self) -> None:
        """Start empty."""
        self._passing: set[str] = set()

    def record(self, digest: str) -> None:
        """Remember that the sandbox probe under `digest` passed.

        Args:
            digest: From `probe_digest`.
        """
        self._passing.add(digest)

    def passing(self, digest: str) -> bool:
        """Whether a sandbox probe under exactly this digest passed.

        Args:
            digest: From `probe_digest`.

        Returns:
            `True` only on an exact match. Anything else — a different digest,
            an empty cache — is `False`, so the failure direction is a refused
            `os` claim rather than an unproven one.
        """
        return digest in self._passing


def derive_containment(inv: Invocation, plan: ContainmentPlan, digest: str, cache: ProbeCache) -> ContainmentPlan:
    """Re-derive both enforcement axes from the resolved invocation (C-1025).

    Returns the plan with every axis the invocation does not corroborate set to
    `None`, which `check_capabilities` then refuses on. The adapter's claim is
    an input, never the answer.

    **Evidence** is corroborated when all four hold:

    1. `plan.argv_evidence` appears in `inv.argv` as a **contiguous run**, in
       order — not as a set of members. `("--tools", "Read", "Grep", "Glob")`
       is a claim about the whole tool list.
    2. the word after the run is absent or starts with `-`. Without this,
       `--tools Read Grep Glob Bash` corroborates a claim that Bash was
       removed, restoring both writes and network reach.
    3. **last-wins by key.** For every evidence word carrying `=`, no *option
       assignment* carried by an argv word outside the run may start with that
       word's `key=`. An assignment is what a word could deliver as an option's
       value: the word itself when it is not `-`-prefixed, whatever follows the
       first `=` of a `-`-prefixed word, and whatever follows the two-character
       prefix of an attached short option (`-csandbox_mode=X`). This is what
       closes Codex's last-wins hole in all three of its spellings —
       `-c sandbox_mode=…`, `--config=sandbox_mode=…` and `-csandbox_mode=…`
       each leave every evidence word present and turn the sandbox off — while
       leaving a second `-c model_reasoning_effort=high` legal, because it
       carries a different key.
    4. **no re-specification.** For every `-`-prefixed evidence word whose
       successor inside the run does NOT carry `=`, no argv word outside the
       run may name it: neither the word itself, nor a `word=value` spelling of
       it, nor an attached short-option spelling. So a second `--tools Bash` or
       a `--tools=Read,Bash` cannot follow the first and win. A `-`-prefixed
       evidence word whose in-run successor DOES carry `=` is exempt, because
       rule 3 already owns its collision surface by key — that exemption is
       what lets Codex emit `-c` twice for two unrelated settings.

    **Residual, stated rather than papered over:** an override that shares no
    key with the evidence still corroborates.
    `codex exec -c sandbox_mode=read-only --sandbox danger-full-access` passes
    all four rules, because core cannot know that `--sandbox` and
    `sandbox_mode=` are the same setting under two spellings. That knowledge is
    the adapter's, and the fix is for the adapter to name both spellings in its
    own evidence set — not a rule here that would have to model every harness's
    option table.

    plus every `plan.env_evidence` entry matching `inv.env` **by value** —
    `OPENCODE_CONFIG_CONTENT="{}"` is present under a names-only check while
    denying nothing.

    **The mechanism** must be corroborated by the kind of evidence it names, so
    a `config-deny` plan cannot pass on argv alone: `tool-removal` requires a
    non-empty `argv_evidence`, `config-deny` a non-empty `env_evidence`, and
    `os-sandbox` both a non-empty `argv_evidence` and a passing cached probe.

    **`os` additionally requires the cached probe, per axis.** Only an axis
    whose claimed level is `os` needs it; an adapter holding one axis at `os`
    and the other at `harness` has the second corroborated by evidence alone.
    An OS sandbox is the one level whose presence cannot be read off an argv:
    `-c sandbox_mode=read-only` is a request, and whether the key name is even
    correct is what C-1040's probe settles.

    Neither axis says anything about descendant lifetime, and this function
    adds no axis that would (D-ac): the clean-exit and `setsid()` residuals are
    identical for every run, so a constant value here would read as derived
    evidence and carry none.

    Args:
        inv: The FINAL resolved launch, as `authorize` built it.
        plan: The adapter's claim.
        digest: This launch's `probe_digest`. `authorize` computes it from the
            plan; nothing on the review path passes one of its own choosing.
        cache: Passing sandbox-probe digests.

    Returns:
        The plan with each uncorroborated axis replaced by `None`.
    """
    proven = cache.passing(digest)
    corroborated = (
        _mechanism_corroborated(plan, proven=proven)
        and _argv_corroborates(inv.argv, plan.argv_evidence)
        and all(inv.env.get(name) == value for name, value in plan.env_evidence.items())
    )
    return replace(
        plan,
        write_enforcement=_derived_axis(plan.write_enforcement, corroborated=corroborated, proven=proven),
        network_enforcement=_derived_axis(plan.network_enforcement, corroborated=corroborated, proven=proven),
    )


def _mechanism_corroborated(plan: ContainmentPlan, *, proven: bool) -> bool:
    """Whether the plan's evidence is of the KIND its mechanism names (C-1025).

    A `config-deny` plan cannot pass on argv alone, and an empty evidence set
    corroborates nothing whatever the mechanism: an adapter that names no
    evidence has stated a claim and nothing else.

    Args:
        plan: The adapter's claim.
        proven: Whether a sandbox probe passed under this launch's digest.

    Returns:
        Whether the named primitive is backed by the evidence it implies.
    """
    if plan.mechanism == "tool-removal":
        return bool(plan.argv_evidence)
    if plan.mechanism == "config-deny":
        return bool(plan.env_evidence)
    # `os-sandbox`, and deliberately the arm any mechanism added later falls
    # into: the strictest of the three, so a new member is refused rather than
    # admitted by a default nobody chose.
    return bool(plan.argv_evidence) and proven


def _argv_corroborates(argv: tuple[str, ...], evidence: tuple[str, ...]) -> bool:
    """Whether the resolved argv corroborates the plan's argv evidence (C-1025 rules 1-4).

    Every occurrence of the run must be terminated, not merely the first: a
    second, unterminated copy later in the argv is the one a harness resolving
    last-wins actually obeys. Rules 3 and 4 are then read over the argv words
    *outside* every occurrence of the run — the evidence's own words are the
    claim, not a collision with it, so a plan whose run legitimately repeats a
    flag (`--deny-tool shell --deny-tool write`) corroborates.

    `derive_containment`'s docstring states the residual these rules do not
    reach: an override sharing no key with the evidence.

    Args:
        argv: The final resolved argv.
        evidence: The words that corroborate the plan, verbatim and in order.

    Returns:
        Whether all four rules hold. An empty evidence set is vacuously true —
        `_mechanism_corroborated` is what refuses it.
    """
    if not evidence:
        return True
    width = len(evidence)
    runs = [start for start in range(len(argv) - width + 1) if argv[start : start + width] == evidence]
    if not runs:  # rule 1: a contiguous run in order, never a set of members
        return False
    # Rule 2: `--tools Read Grep Glob Bash` carries every evidence word and
    # restores both writes and network reach.
    if not all(start + width == len(argv) or argv[start + width].startswith("-") for start in runs):
        return False
    covered = {index for start in runs for index in range(start, start + width)}
    outside = tuple(word for index, word in enumerate(argv) if index not in covered)
    # Rule 3: Codex resolves the LAST `sandbox_mode=…`, whichever of its three
    # spellings delivered it, so a second assignment of the same key turns the
    # sandbox off with every evidence word still present.
    keys = {f"{word.split('=', 1)[0]}=" for word in evidence if "=" in word}
    assignments = [value for word in outside for value in _assignments(word)]
    if any(value.startswith(key) for key in keys for value in assignments):
        return False
    # Rule 4: a second `--tools Bash`, or a `--tools=Read,Bash`, cannot follow
    # the first and win.
    return not any(_names_option(word, flag) for flag in _respecifiable(evidence) for word in outside)


def _assignments(word: str) -> tuple[str, ...]:
    """Every option value one argv word could be delivering (C-1025 rule 3).

    Three spellings, because a harness's own parser accepts all three and a
    rule that read only the separated one would miss two working overrides.

    Args:
        word: One argv word from outside the evidence run.

    Returns:
        The candidate assignments — empty for a bare short flag like `-c`,
        which carries its value in the NEXT word and is therefore covered by
        that word's own entry.
    """
    if not word.startswith("-"):
        return (word,)
    carried: list[str] = []
    if "=" in word:  # `--config=sandbox_mode=X`, `-c=X`
        carried.append(word.split("=", 1)[1])
    if not word.startswith("--") and len(word) > 2:  # clap's attached short form, `-csandbox_mode=X`
        carried.append(word[2:])
    return tuple(carried)


def _respecifiable(evidence: tuple[str, ...]) -> tuple[str, ...]:
    """The evidence flags rule 4 owns: those whose in-run successor carries no `=`.

    A flag whose value is the next word (`--tools Read`) is re-specified by
    naming the flag again, so rule 4 must refuse that name outside the run. A
    flag whose value is a `key=value` word (`-c sandbox_mode=read-only`) is
    re-specified only by that KEY, which rule 3 already owns — refusing the
    flag itself would make Codex unlaunchable, since its reasoning-effort knob
    rides a second `-c` for an unrelated setting.

    Args:
        evidence: The plan's argv evidence, verbatim and in order.

    Returns:
        The `-`-prefixed evidence words rule 4 applies to.
    """
    flags: list[str] = []
    for index, word in enumerate(evidence):
        if not word.startswith("-"):
            continue
        # A trailing flag has no in-run successor, which reads as "carries no
        # `=`" — the conservative arm, and the right one for a boolean flag.
        successor = "".join(evidence[index + 1 : index + 2])
        if "=" not in successor:
            flags.append(word)
    return tuple(flags)


def _names_option(candidate: str, flag: str) -> bool:
    """Whether one argv word re-specifies `flag`, in any of its spellings (C-1025 rule 4).

    Args:
        candidate: An argv word from outside the evidence run.
        flag: A `-`-prefixed evidence word.

    Returns:
        Whether `candidate` names the same option.
    """
    return (
        candidate == flag
        or candidate.split("=", 1)[0] == flag
        or (len(flag) == 2 and len(candidate) > 2 and candidate.startswith(flag) and not candidate.startswith("--"))
    )


def _named_flag(word: str, flags: frozenset[str]) -> str | None:
    """The member of `flags` that `word` names, in any spelling, or `None`.

    Both refusal sets are matched through here, so `-r` reaching `--resume`'s
    capability, `--add-dir=/etc` reaching `--add-dir`, and `-C/tmp` reaching
    `-C` are one behaviour rather than three set-membership tests that each had
    to remember a spelling. Set membership was the shape both sites had, and it
    is what let a short-form alias of a denied long flag through.

    Args:
        word: One argv or passthrough word.
        flags: A refusal set.

    Returns:
        The member named, or `None`. Sorted, so a word naming two members
        reports the same one every run.
    """
    return next((flag for flag in sorted(flags) if _names_option(word, flag)), None)


def _derived_axis(level: Enforcement | None, *, corroborated: bool, proven: bool) -> Enforcement | None:
    """Keep one axis's claimed level, or downgrade it to `None` (C-1025).

    The cached probe is required PER AXIS: an adapter holding one axis at `os`
    and the other at `harness` has the second corroborated by evidence alone.

    Args:
        level: The claimed level for this axis.
        corroborated: Whether the invocation corroborates the shared evidence.
        proven: Whether a sandbox probe passed under this launch's digest.

    Returns:
        The level, or `None` when it is not established.
    """
    if not corroborated:
        return None
    if level == "os" and not proven:
        return None
    return level


def authorize(
    adapter: Adapter,
    launch: Launch,
    ws: Workspace,
    info: HarnessInfo,
    plan: ContainmentPlan,
    cache: ProbeCache,
    runner: Runner,
) -> tuple[Invocation, ContainmentPlan]:
    """Turn a `Launch` into a spawnable `Invocation`, or refuse (C-1007, C-1025).

    **The only producer of a review `Invocation` in nox.** That is what makes
    the gate unskippable: WP8 has no other route to something `Runner.spawn`
    accepts, so a harness cannot be spawned before derivation has refused, and
    a `Containment` cannot be stamped from a claim rather than from evidence.
    Under the previous shape both were correct orderings that a caller had to
    perform, which is the discipline-instead-of-mechanism failure C-1025 exists
    to remove.

    In order:

    1. refuse a missing REQUIRED capability, before anything spawns. C-1040's
       sandbox probe is a full review-shaped spawn, and SD § 7.1 puts both
       `UNSUPPORTED` rows at "no harness spawned". `check_capabilities` checks
       this half again at step 6 for its other callers; checking it twice is
       cheaper than a probe that ran for a harness the gate was going to refuse.
    2. refuse any `launch.env` key the plan did not declare in `env_evidence`,
       or whose value differs — AND, whatever the plan declares, any key that
       is already in `ws.env`, carries a `config.DENY_PATTERNS` credential
       shape, or is in `NEVER_SET`. Declaring a key is not a permission to set
       it: `env = {**ws.env, **launch.env}` puts the launch's value on top, so
       without those three the plan alone could re-add `ANTHROPIC_API_KEY`,
       point `PATH` into the worktree, put `GIT_CONFIG_COUNT` ahead of nox's
       C-1031 set, or `LD_PRELOAD` a library into the child — each with the
       containment stamp intact.
    3. build the `Invocation` with `cwd = ws.path` (C-1003) and
       `env = {**ws.env, **launch.env}` — `ws.env` because the harness's own
       `git` must inherit the C-1031 overrides, which a rebuild from
       `os.environ` would drop.
    4. resolve `argv[0]` to an absolute realpath through `launch_argv`, and
       refuse a final argv naming a `NEVER_EMITTED` word in any spelling. The
       static scan over the adapter sources sees only string literals; this
       sees a computed or table-driven flag, and every member either lifts a
       containment control or leaves the boundary it is measured in. Then
       refuse a `stdin_path` outside `ws.scratch` — the adapter chooses the
       channel, never the file.
    5. compute the digest and, when the plan claims an `os` axis and the digest
       is not already cached, run `adapter.sandbox_probe` and record a pass.
       Behind a launcher the cache is per-launch, because `probe_digest` keys
       on the wrapper and not on the harness the wrapper resolves (CG1).
    6. `derive_containment`, then `check_capabilities` on the DERIVED plan.

    Args:
        adapter: The selected adapter — for `CONFIG_READS` and `sandbox_probe`.
        launch: What `prepare` returned.
        ws: The live workspace.
        info: What the probe established.
        plan: The adapter's claim, from `containment_plan`.
        cache: Passing sandbox-probe digests.
        runner: The process seam, for the sandbox probe.

    Returns:
        `(invocation, derived_plan)`. The derived plan is what WP8 stamps
        `Containment`'s three enforcement fields from — never `plan`.

    Raises:
        UnsupportedCapability: A required capability is absent, or an axis did
            not survive derivation (C-1007, C-1013).
        ConfigError: `launch.env` carries a key or value the plan did not
            declare, a key no launch may set whatever the plan declares, the
            final argv carries a `NEVER_EMITTED` word, or `stdin_path` names a
            file outside `ws.scratch`.
        HarnessUnavailable: `argv[0]` could not be resolved.
    """
    _require_capabilities(info)
    for name, value in launch.env.items():
        # The NAME only, in every message below: a re-added credential's value
        # would otherwise reach `Review.detail` through it (C-1035).
        if plan.env_evidence.get(name) != value:
            raise ConfigError(f"launch env: {name} is not declared in the plan's env_evidence (C-1008)")
        if name in ws.env:
            raise ConfigError(f"launch env: {name} may not override the minimal environment (C-1008)")
        if matches_any(name, DENY_PATTERNS):
            raise ConfigError(f"launch env: {name} has a credential shape and is never set by a launch (C-1008)")
        if name in NEVER_SET:
            raise ConfigError(f"launch env: {name} is a code-injection channel and is never set by a launch (C-1044)")
    argv = launch_argv(info.launcher, ws.env, *launch.argv)
    for word in argv:
        if _named_flag(word, NEVER_EMITTED) is not None:
            raise ConfigError(f"launch argv: {word} lifts a containment control and is never emitted (C-1023)")
    # Step 4b: the stdin channel names a FILE, and an unpoliced one is an
    # arbitrary-file read pointed at the model — an adapter naming any readable
    # path under `$HOME` would have nox open it and ask the harness to review
    # its contents. `ws.scratch` is nox-minted and nox-written, so requiring the
    # path to sit directly in it leaves three residuals at the final component —
    # a symlink, a non-regular file, and a hardlink — of which `_open_prompt`
    # closes the first two. A hardlink is invisible to `O_NOFOLLOW`, and like a
    # swapped directory component it needs the same-uid write access that would
    # already let the attacker read the target directly, so neither is an
    # escalation over the shape it starts from.
    if launch.stdin_path is not None and launch.stdin_path.parent != ws.scratch:
        raise ConfigError(f"launch stdin: {launch.stdin_path.name} is not a file in the workspace scratch (C-1028)")
    inv = Invocation(argv=argv, cwd=ws.path, env={**ws.env, **launch.env}, stdin_path=launch.stdin_path)
    digest = probe_digest(
        plan=plan,
        executable=inv.argv[0],
        launcher=info.launcher,
        env=inv.env,
        config_reads=config_read_paths(adapter.CONFIG_READS, inv.env),
    )
    if info.launcher.prefix:
        # CG1: under a launcher the digest cannot see the harness it keys.
        # `launch_argv` resolves the PREFIX's head, so `executable` and its
        # content hash are the wrapper's (`ocx`) and stay identical across every
        # in-place change to the wrapped target — the launcher's whole job is to
        # resolve that itself, out of a store nox cannot name, let alone hash.
        # A pass recorded under one wrapped harness would therefore authorize a
        # launch of a different one at `os`, the one level whose entire price is
        # that probe. A per-launch cache is the answer rather than a wider key:
        # the artifact behind an opaque wrapper is not addressable from here, and
        # keying on something that cannot see it is what produced this.
        #
        # It must be a fresh CACHE and not merely a forced re-probe:
        # `derive_containment` reads `proven` off the cache, so a shared cache
        # keeping the earlier record would stamp `os` from the previous launch
        # even when the probe just run failed.
        #
        # ponytail: one probe per review for wrapped harnesses, none for the
        # rest. The upgrade path is a launcher that can report the artifact it
        # resolved — a digest is only worth keying on once something can.
        cache = ProbeCache()
    if "os" in (plan.write_enforcement, plan.network_enforcement) and not cache.passing(digest):
        # Same wrapper as `probe_harness`, for the same reason: C-1040's probe is
        # adapter code that spawns, and `workspace()` removes `ws.path` at
        # teardown. No clamp — this one is a full review-shaped model turn.
        prober = _ProbeRunner(runner, budget=None)
        try:
            proven = adapter.sandbox_probe(prober, ws, info, inv.env)
        finally:
            prober.reap()
        if proven:
            cache.record(digest)
    derived = derive_containment(inv, plan, digest, cache)
    check_capabilities(info, derived)
    return inv, derived


# ── Model selection, warnings and the parse framework ────────────────────────


def resolve_model(
    models: Mapping[ModelClass, ModelSpec], cfg: HarnessConfig
) -> tuple[ModelSpecT | None, ModelClass | None]:
    """Resolve the requested capability class to this harness's literal (C-1030).

    Four cases, and rule 6 is the one that is easy to get wrong:

    1. a trusted `model_literal` overrides the shipped table outright;
    2. no class configured — the harness default, `model = None`;
    3. the class has a `MODELS` entry — that literal;
    4. **the class has no entry** — the harness default with `model = None`,
       and `model_class` still recorded. Not an error and not a substitution
       from the other class: nox asked for a capability the harness does not
       name, and the honest record is that the harness chose.

    Args:
        models: The adapter's shipped table.
        cfg: This harness's config.

    Returns:
        `(spec, model_class)`. A `None` spec means the harness default is
        taken and `Review.model` is `None`; `model_class` travels either way,
        because both sides of the asymmetry evidence matter (C-1036).

    Raises:
        ConfigError: A configured literal is not a usable argv word.
    """
    override = cfg.model_spec()
    if override is not None:  # rule 1
        return override, cfg.model
    if cfg.model is None:  # rule 2
        return None, None
    shipped = models.get(cfg.model)
    # Rule 6: no entry is the harness default with `model = None`, never a
    # substitution from the other class — the honest record is that the
    # harness chose.
    return (ModelSpecT.of(shipped) if shipped is not None else None), cfg.model


def version_warning(info: HarnessInfo) -> str | None:
    """Warn when the probed version is not the one this adapter was verified on (C-1020).

    A warning and never a refusal: a harness that moved one patch release is
    overwhelmingly likely to still work, and refusing would make every upgrade
    an outage. What the warning buys is that a *silent* drift cannot be
    mistaken for a verified run when the review it produced is weighed.

    Args:
        info: What the probe established.

    Returns:
        One warning naming both versions, or `None` when they match or the
        probe named no version — an unknown version is not evidence of a
        mismatch (C-1035 forbids inventing one).
    """
    if info.version is None or info.version == info.verified_against:
        return None
    return (
        f"{info.name}: running {info.version}, verified against {info.verified_against} — "
        "the adapter's fixtures were recorded from a different release (C-1020)"
    )


def _bare_model(spec: str) -> str:
    """The model id without a harness's `provider/` prefix.

    Args:
        spec: A model id as some harness spells it.

    Returns:
        The segment after the last `/`, or the whole string when there is none.
        `/` only: a Bedrock-style `us.anthropic.claude-opus-4-7-v1:0` is a
        different spelling again, and no v1 harness emits one.
    """
    return spec.rpartition("/")[2]


def asymmetry_warning(authored_by: str | None, model: str | None) -> str | None:
    """Warn when writer and reviewer are in the C-1036 negative FAMILY pair (D-b).

    Keyed on the MODEL pair, not the harness pair: `copilot` and `opencode` can
    both resolve to the same backend under different strings, so a harness swap
    alone changes nothing and must not silence or trigger this.

    **The text may not claim more than the citation measured.**
    `ASYMMETRY_NEGATIVE` matches families because the measured ids
    (`ASYMMETRY_MEASURED`) are resolved by no shipped `MODELS` table, so a
    match here is nearly always a *different* pair from the one the paper ran.
    The warning therefore names the citation, names the measured pair, and says
    the extension to the family is untested — an operator can then weigh the
    caveat instead of reading it as a measurement of the two models in front of
    them. A warning that overstates its own evidence is the same failure as one
    that never fires, one step further along: it is believed.

    The prefix match is anchored at the head only, so `claude-opus` also
    matches a future `claude-opus-9`. Deliberate: an over-fire costs a human
    one sentence of context on a review they were reading anyway, while an
    under-fire silently drops the caveat on a point release — and the same
    unanchored tail is what makes `gpt-5.6-luna` keep matching, which is the
    case the prefix form exists for.

    Anchored at the head of the BARE id, not of the harness's spelling of it.
    OpenCode names a model `github-copilot/gpt-5.6-luna` and nothing else in v1
    carries a `provider/` prefix, so a head-anchored match against the shipped
    literal was structurally silent for exactly one harness — and a warning that
    is absent for one reviewer is worse than one that never fires, because the
    operator reads its absence as evidence.

    Args:
        authored_by: The model that wrote the change, when the caller said.
        model: The RESOLVED reviewer literal — `None` when the harness default
            was taken, which is silent rather than guessed.

    Returns:
        One warning naming both models, the measured pair and
        `ASYMMETRY_CITATION`, and stating that the family generalization is
        untested — or `None`. Never changes status, verdict or findings.
    """
    if authored_by is None or model is None:
        return None
    measured_writer, measured_reviewer = ASYMMETRY_MEASURED
    for writer, reviewer in ASYMMETRY_NEGATIVE:
        if _bare_model(authored_by).startswith(writer) and _bare_model(model).startswith(reviewer):
            return (
                f"reviewer {model} and author {authored_by} are the {writer}/{reviewer} model families, for "
                f"which a negative reviewing interaction was measured ({ASYMMETRY_CITATION}). The measurement "
                f"is of {measured_writer} written and {measured_reviewer} reviewing; generalizing it to these "
                "families is UNTESTED. Weigh its findings accordingly."
            )
    return None


_SEVERITIES: Final[tuple[Severity, ...]] = get_args(Severity)
"""The four recognized severity words, read off the `Literal` rather than restated."""


def to_severity(raw: object) -> Severity:
    """Map a harness's severity word onto nox's four, failing HIGH (C-1018).

    An unrecognized word becomes `block`, the *highest* severity, not the
    lowest. The input is untrusted output from a model that may invent a word,
    and the two failure directions are not symmetric: a `suggest` default
    silently downgrades a real finding out of a consumer's attention, while a
    `block` default costs a human one look.

    Total over `object`, not over `str`, and that is the point: a harness
    emitting `"severity": null` or a number hands an adapter a `None` or an
    `int`, and an `AttributeError` from `.strip()` is not a `NoxError` — it
    would escape `review()`'s C-1029 totality as a traceback rather than
    resolving to a run outcome. Anything that is not one of the four words
    becomes `block`, whatever its type.

    Args:
        raw: The harness's word, whatever the wire produced. Rendered with
            `str()`, then compared case-folded and stripped.

    Returns:
        The matching severity, or `block`.
    """
    word = str(raw).strip().casefold()
    for known in _SEVERITIES:
        if known == word:
            return known
    return "block"


def safe_finding_file(raw: str | None) -> str | None:
    r"""Return `raw` only if it is a repo-relative path a consumer can resolve safely.

    `Finding.file` is untrusted harness output (C-1019) and a consumer will
    both RENDER it and may hand it to a command. Four shapes are refused, and
    the last two are about the rendering rather than the resolving:

    - an absolute path, a `..` component or an embedded NUL — not a location in
      the review, but an attempt to point a reader outside the worktree;
    - a backslash or a colon — `C:\Windows` and `..\windows` walk out of the
      tree on the reader's machine while carrying neither a leading `/` nor a
      POSIX `..` component;
    - any non-printable character. A newline forges a second finding in a
      line-oriented render, an `\x1b[` sequence repaints the terminal, and a
      BiDi override or a zero-width joiner makes the rendered path read as a
      different file than the one a consumer opens;
    - a leading `-`, or leading/trailing whitespace. `-rf` is an option to
      whatever command a consumer builds, and `" /etc/passwd"` renders as an
      absolute path while resolving as a relative one.

    The finding's own body still carries whatever the harness said; this
    normalizes the one field a machine acts on.

    Called from `ParsedOutput.__post_init__`, so it runs once for every adapter
    rather than four times by convention.

    Args:
        raw: What the harness reported, or `None`.

    Returns:
        The normalized repo-relative path, or `None` when there is no safe one.
    """
    if raw is None or any(char in raw for char in ("\x00", "\\", ":")) or not raw.isprintable():
        return None
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts:
        return None
    normalized = str(pure)
    if normalized == ".":  # `""` and `"./"` both land here
        return None
    if normalized.startswith("-") or normalized != normalized.strip():
        return None
    return normalized


def reason_for_exit(exit_code: int) -> FailureReason | None:
    """Map an exit status to a reason, for the one status that carries meaning.

    `143` is `128 + SIGTERM`: nox's own kill, labelled as such rather than as a
    generic failure (C-1012). Everything else returns `None` — the exit code is
    never the success gate (C-1011), and mapping more of it would rebuild the
    branch SD § 4.3 forbids.

    Args:
        exit_code: What the child exited with.

    Returns:
        `KILLED` for 143, else `None`.
    """
    return FailureReason.KILLED if exit_code == SIGTERM_EXIT else None


def indeterminate(raw: str, error_name: str) -> ParsedOutput:
    """Build the result an adapter returns when its `classify` declined (C-1012).

    Step 6.3 requires `classify()` to return `None` on any unrecorded shape,
    and this is the other half of that rule: the run resolves `indeterminate`
    with the raw error name stamped, rather than each of four adapters carrying
    the same six-field construction in prose. It **can never return `approve`**
    — `verdict` is `None` and `ParsedOutput` refuses a verdict on a non-`ok`
    status, so an adapter cannot reach a success answer through this route.

    The error name is the one piece of harness output that travels into
    `detail`, and deliberately: without it "indeterminate" names no shape a
    human could add to the adapter's table.

    Args:
        raw: The harness's output as the supervisor delivered it (C-1018).
        error_name: The unrecorded error name the harness reported.

    Returns:
        An `indeterminate` result carrying `MALFORMED_OUTPUT`.
    """
    return ParsedOutput(
        status="indeterminate",
        verdict=None,
        findings=(),
        summary="",
        detail=f"the harness reported {error_name}, which this adapter's classification table does not record",
        raw=raw,
        reason=FailureReason.MALFORMED_OUTPUT,
    )


def review_prompt(
    ws: Workspace,
    info: HarnessInfo,
    instructions: str | None,
) -> tuple[Path, str]:
    """Render the review prompt and write it into the workspace scratch (C-1028).

    The single sanctioned route from a workspace to a prompt, and the reason it
    exists rather than each adapter calling `render` itself: the arguments an
    adapter would have to remember are exactly the ones that are silent when
    forgotten. `neutralized_paths` is what tells the reviewer that a branch
    ADDING a C-1005 member was filtered out of both synthetic trees;
    `structured_output` decides whether the fenced-JSON ask appears at all — a
    hand-set bool there either duplicates a harness-native schema or drops the
    only one there was; and `filtered_paths` is `ws.filtered`, the UNION of
    every entry dropped by mode, because C-1043(2) requires each one listed as
    `<path> -> <link target>` — a symlink the branch just added is evidence the
    reviewer must see. `ws.filtered_changed` travels beside it as the BOOL
    `render` asks for: C-1043(4)'s verdict gate selects the incomplete-checkout
    framing and renders no paths of its own, and `api.review()` reads the same
    field for the verdict half. The three
    `*_total` counts travel beside their lists for the same reason: every list is
    capped at `ENUMERATION_BUDGET`, and the count the prompt states is what the
    reviewer is told to check the fenced region's line count against, so a
    truncated list stating its own length is a false claim inside C-1028's own
    tamper signal.

    **`ws.diff` travels the same way, and that is what makes the prompt the
    delivery route for the change itself.** `<scratch>/review.diff` was written
    and never read: three of the four shipped adapters hand the reviewer a
    worktree checked out at the *after* commit and no diff by any channel, and
    claude's allowlist (`Read`, `Grep`, `Glob`) has no shell to derive one with,
    so those reviewers were reading a snapshot under a prompt asserting they had
    the whole change. A live NxN matrix is what caught it. The text is read off
    `Workspace` rather than off `ws.diff_path` here, so the prompt carries what
    `git diff` emitted rather than whatever is on disk now. No harness has run in
    this workspace yet at this point — `adapter.sandbox_probe` is the only one
    that does, and `authorize` spawns it after `prepare` returns — so this is
    belt-and-braces rather than a live defence. The live one is downstream: that
    probe runs BETWEEN this function's write of `prompt.md` and
    `runner._open_prompt`'s read of it, and `write_nofollow` says the scratch
    directory is unprotected once a harness has run there.

    **Both return values are live, and the harness picks** (E29). `claude` and
    `codex` read their prompt from stdin, so they hand the PATH back as
    `Launch.stdin_path` and the diff never becomes an argv word. `copilot` and
    `opencode` have only an argv word, so they take the TEXT through
    `argv_prompt`, whose `PROMPT_ARGV_LIMIT` — the kernel's `MAX_ARG_STRLEN` —
    keeps that honest: a diff too large for an argv word is a refused review,
    never a trimmed prompt (C-1028). The file is written unconditionally, which
    is what makes the stdin channel free: nothing extra is created for it. It is
    NOT out of the harness's reach — `ws.scratch` is beside the ephemeral
    worktree (C-1019) rather than inside it, and a harness confined to `cwd` by
    its own file tools cannot name it, but it runs as the same uid and the
    directory is unprotected once one has run there. `runner._open_prompt` is
    what acts on that, not the mode bits.

    Args:
        ws: The live workspace, which owns the diff and all three path lists.
        info: What the probe established — `structured_output` is read from
            its capabilities, never passed in.
        instructions: Extra instruction text from nox's own caller, or `None`.

    Returns:
        `(path, text)` — the file inside `ws.scratch`, and its content.

    Raises:
        IsolationError: The prompt could not be written (`write_nofollow`).
    """
    text = render(
        ws.scope,
        ws.filtered,
        ws.omitted,
        instructions,
        diff=ws.diff,
        neutralized_paths=ws.neutralized,
        structured_output=Capability.STRUCTURED_OUTPUT in info.capabilities,
        filtered_total=ws.filtered_total,
        omitted_total=ws.omitted_total,
        neutralized_total=ws.neutralized_total,
        filtered_changed=bool(ws.filtered_changed),
    )
    path = ws.scratch / PROMPT_FILENAME
    write_nofollow(path, text.encode("utf-8"))
    return path, text


def argv_prompt(text: str) -> str:
    """Bound a prompt that must ride argv, per `PROMPT_ARGV_LIMIT` (C-1028).

    The required route for the two v1 shapes with no second channel:
    `opencode run [message..]` and `copilot -p <text>` both take the message as
    an argv word, and neither offers a prompt file or a stdin form. That
    deviation from "the file is the route" is honest only while the cap actually
    fires — C-1028 forbids the prompt truncating, and a silent `E2BIG` or a
    shell-free `execve` truncation would drop the anti-injection framing that
    lives at the end of the prompt.

    **The other two do not call this, and that is the point** (E29). `claude`
    and `codex` both read their prompt from stdin, so they set
    `Launch.stdin_path` and the kernel's `MAX_ARG_STRLEN` never binds. Calling
    this on all four made the argv limit look like a nox policy and refused a
    whole-branch review — nox's own primary use case — on every harness.

    The cap is in BYTES and `review_prompt` returns a `str`, so the measurement
    is over the UTF-8 encoding: a prompt of mostly non-ASCII characters is
    two to four times its character count on the wire, and a character-count
    check would pass a launch the kernel refuses. The comparison is `>=` and not
    `>`: `PROMPT_ARGV_LIMIT` is Linux's `MAX_ARG_STRLEN`, and the kernel's own
    bound counts the terminating NUL, so a prompt of exactly that many bytes is
    an `E2BIG` out of `Popen` rather than the refusal this function exists to
    give.

    **Residual this bound does not cover, and it is now the whole diff.** A
    prompt on argv is world-readable in `/proc/<pid>/cmdline` for the length of
    the review, so the content of every changed file is visible to any local
    user on the machine. `copilot.py` documented that for its own leg; the diff
    made it true of every harness that crosses this chokepoint. Moving `claude`
    and `codex` to stdin closed it for those two as a side effect: the prompt
    file is `0o600` in a `mkdtemp` scratch, so it is not world-readable the way
    `/proc/<pid>/cmdline` is. That is a claim about OTHER local users and not
    about the harness itself — the harness runs as the same uid, and file modes
    stop it from nothing; what keeps a harness out of `ws.scratch` is its own
    file-tool confinement, which is per-harness. The exposure stays open for
    `copilot` and `opencode`, which offer no second channel to close it with.

    **The other byte argv cannot carry, and the one that reads as nox's fault.**
    An `execve` argument string is NUL-terminated, so a NUL *inside* one is
    unrepresentable — and `Popen` refuses it with a `ValueError`, which is not
    an `OSError` and therefore not what `api._spawn` catches. It travels past
    every mapping to `review()`'s catch-all and resolves
    `indeterminate`/`MALFORMED_OUTPUT`: the row consumers degrade to a graceful
    skip. Meanwhile the byte's whole provenance is the branch — `git` diffs a
    blob it reads as text, `Workspace.diff` decodes with `errors="replace"`
    (which repairs invalid UTF-8 and leaves a perfectly valid U+0000 alone), and
    `review_prompt` renders the diff into the prompt. So one committed NUL let a
    repository deny its own review and made the denial look like the reviewer
    malfunctioning. Refused here for the same reason as the size: named, at the
    channel that cannot carry it, with the cause pointing at the branch.

    **The stdin channel is deliberately NOT guarded against it, and that is the
    consistent treatment rather than the lenient one** (E29). `_open_prompt`
    hands the child a file descriptor, not a string; a fd carries U+0000 like
    any other byte, so `claude` and `codex` deliver the diff intact and the
    reviewer sees the file as committed. A guard placed on the prompt instead
    of on the channel would refuse a review two harnesses can run — the exact
    over-reach E29 corrected for the byte cap one release earlier, where a
    kernel property of argv had been applied to all four. Both of this
    function's refusals are properties of `execve`, and `execve` is what the
    other two do not go through.

    Checked BEFORE the size, and the order carries meaning: a NUL-bearing diff
    is usually also a large one, and the size message advises narrowing the base
    — advice no narrowing can satisfy while the byte is inside the range. The
    offset is reported because "somewhere in your branch" is not actionable and
    a byte count is; it is an integer, so C-1035(1) has nothing to leak.

    Args:
        text: The rendered prompt, from `review_prompt`.

    Returns:
        `text` unchanged, so the call reads as the delivery route rather than
        as a check a caller could forget to act on.

    Raises:
        ConfigError: The prompt carries a NUL, or its encoding reaches
            `PROMPT_ARGV_LIMIT` — each naming what the argv channel cannot
            carry and saying that the diff is what the prompt carries, so the
            caller's configuration is not what was refused.
    """
    # Both refusals measure the ENCODING, never the character count: `execve`
    # sees bytes, and `str.find` answers in code points — so the offset handed
    # to the operator was wrong on every prompt carrying one non-ASCII
    # character, which is most real diffs.
    encoded = text.encode("utf-8")
    nul = encoded.find(b"\x00")
    if nul >= 0:
        raise ConfigError(
            f"prompt: a NUL byte at byte {nul} cannot ride argv (C-1028). An execve argument string ends at "
            "the first NUL, so this harness cannot be handed the prompt at all — and the prompt carries the "
            "diff, so the byte came from a file on the branch under review, not from the configuration. "
            f"Either drop that file from the diff, or run a harness whose prompt rides stdin, which carries "
            f"every byte ({STDIN_PROMPT_HARNESSES})."
        )
    size = len(encoded)
    if size >= PROMPT_ARGV_LIMIT:
        raise ConfigError(
            f"prompt: {size} bytes reaches the {PROMPT_ARGV_LIMIT}-byte argv limit (C-1028). This harness "
            "takes its prompt as an argv word and the prompt carries the diff, so the kernel's "
            "MAX_ARG_STRLEN is what refused it — not nox, and not the configuration. Either review a "
            f"narrower base, or run a harness whose prompt rides stdin and has no such limit "
            f"({STDIN_PROMPT_HARNESSES})."
        )
    return text
