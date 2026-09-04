# Research: Stdlib Subprocess-Supervision Patterns for `nox`

<!--
Technology-landscape research. Owner: a researcher worker. Handoff to:
/hex-architect, /hex-plan.
-->

## Metadata

**Date:** 2026-09-02
**Domain:** cli | testing | observability
**Triggered by:** decomposing `nox/runner.py`, `nox/liveness.py`,
`nox/harness.py` work packages and the test strategy (fake `Runner`,
exactly one `# pragma: no cover`) from
[`adr_0011_nox_multi_harness_adversary.md`](../adrs/adr_0011_nox_multi_harness_adversary.md)
(C-1009, C-1010, C-1011, C-1014, C-1015, C-1029) and
[`adr_0011_system_design.md`](../adrs/adr_0011_system_design.md) § 4.2, § 4.3.
**Expires:** 2027-02-28

## Direct Answer

The ADR's design is already correct on the two points where the literature
disagrees with itself: **threads over a queue, not `selectors` or
`asyncio`**, and **the `Runner` seam wraps process creation only, not the
supervision loop**. Nothing found here argues to reopen either decision.
Three refinements do change the plan, all additive:

1. **Frame chunks, not lines, before parsing JSON.** Anthropic's own
   `claude-agent-sdk-python` — the closest real precedent to `nox` (it
   drives the same `claude --output-format stream-json` this ADR targets)
   — reads the pipe in raw chunks up to 64 KiB and explicitly reassembles
   lines in a dedicated `_LineFramer`, because a single JSON line can span
   several `read()` calls. `nox/runner.py`'s drain thread needs the same
   reassembly step before `json.loads`, not `for line in proc.stdout`
   (which itself is safe, but a naive `readline()`-in-a-loop-with-manual-
   buffering reimplementation is not, if that's the shape chosen).
2. **The Windows kill path needs its own primitive, not `os.killpg` with a
   platform `if`.** `SIGTERM`/`os.killpg` do not exist on Windows;
   `CREATE_NEW_PROCESS_GROUP` at spawn plus `CTRL_BREAK_EVENT` at kill-time
   is the closest analogue, and it is not equivalent — the ADR already
   resolves the `.cmd`-shim half of the Windows question (C-1009) but the
   kill half is still open in the excerpted `Runner`/`supervise` contract.
3. **`assert_never` in strict-mode pyright wants `reportMatchNotExhausted`,
   not a defensive final branch.** The tri-state `Status` and
   `FailureReason` `match` blocks in `nox/outcome.py` should rely on
   pyright's strict-mode exhaustiveness check rather than hand-adding an
   `assert_never(x)` catch-all branch, which triggers
   `reportUnnecessaryComparison` under strict mode on some pyright/
   basedpyright versions.

## Technology Landscape

### Established (proven, widely accepted)

| Tool/Pattern | Status | Notes |
|---|---|---|
| Thread-per-stream + queue draining a subprocess pipe | Standard, decades old | What the ADR already picked (C-1009); still the correct choice given the Windows `selectors`-on-pipes gap. |
| `Popen` as a context manager (`with Popen(...) as p:`) | Standard since 3.2 | Guarantees `wait()`/fd-close on exit, closing the classic zombie-process leak. `subprocess.run()`/`communicate()` do this internally already. |
| `os.killpg` + `start_new_session=True` for POSIX tree-kill | Standard | Exactly the shape in C-1009; corroborated by multiple 2026 sources below. |
| `Result`/tri-state via `Literal` + frozen dataclass, no pydantic | Established in strict-typed Python (2025-2026) | No stdlib type does this; `nox/outcome.py`'s custom `Status = Literal[...]` is the mainstream shape, matching prior research's finding that no Python library ships a first-class tri-state result. |

### Trending (gaining momentum)

| Tool/Pattern | Adoption Signal | Key Benefit | Relevance |
|---|---|---|---|
| `anyio`-style chunk framer over a raw pipe (`_LineFramer`) | Shipped in `claude-agent-sdk-python`, actively maintained by Anthropic | Correctly handles a JSON line spanning multiple `read()` chunks without blocking | `nox` is zero-dependency so it can't take `anyio`, but must reimplement the *framing logic*, not just call `for line in proc.stdout` and assume it's equivalent — see Key Finding 1. |
| `reportMatchNotExhausted` (pyright strict, on by default) as the exhaustiveness enforcement mechanism, replacing hand-written `assert_never` catch-alls | Active pyright/typing-sig discussion through 2026 | One less runtime branch; the type checker, not a runtime `NoReturn` call, is the enforcement point | Directly shapes how `nox/outcome.py`'s `match Status` blocks should be written. |

### Declining (losing mindshare)

| Tool/Pattern | Signal | Avoid Because |
|---|---|---|
| `selectors`-based multiplexed pipe reading for cross-platform subprocess draining | Documented stdlib limitation, not a fad that faded — but worth stating as "avoid," since it's the option nox's own ADR text explicitly rejected | `selectors` does not support pipes on Windows at all (already cited in the ADR from `nox-tech-tooling.md:76`); confirmed as a standing platform gap, not something fixed in recent Python 3.12-3.14 changelogs checked here. |
| Reading `stdout=PIPE`/`stderr=PIPE` via `proc.wait()` before draining either stream | Recurring bug-tracker pattern (`agentscope-ai/agentscope#1255` filed 2026) | Classic 64 KiB pipe-buffer deadlock: child blocks writing once the OS pipe buffer (~64 KiB on Linux) fills, parent blocks in `wait()` without reading — neither side progresses. `nox`'s merged-stdout/stderr-into-one-pipe design (C-1009) sidesteps the *two-pipe* variant of this bug by construction, but the same failure shape reappears if `supervise()` ever calls `proc.wait()` before the drain thread starts, or drains only after checking `poll()`. |

## Design Patterns Worth Considering

- **Chunk-reassembly line framer** — a small stateful class that buffers
  partial reads and yields only on `\n`, with a max-buffer flush guard
  against a pathological non-terminated stream (`_LineFramer.pending_len`
  cap in Anthropic's code). Used by: `claude-agent-sdk-python`
  ([source, `subprocess_cli.py`](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/transport/subprocess_cli.py)).
  Directly reusable shape for `nox/runner.py`'s drain thread even though
  the transport underneath (thread+pipe vs. `anyio.open_process`) differs.
- **Fresh subprocess + broker-multiplexer, JSONL-over-stdio, shell-wrapper
  ban** — `openai/codex-plugin-cc`'s own maintainers are mid-incident on
  exactly the failure the ADR already guards against: their Windows spawn
  path uses `shell: process.env.SHELL || true`, and a filed bug
  ([openai/codex-plugin-cc#236](https://github.com/openai/codex-plugin-cc/issues/236))
  traces a hang directly to that shell wrapper corrupting JSON-RPC framing
  over stdio ("quoting/path resolution problems, extra shell output on
  stdout/stderr, encoding differences, loss of direct stdio semantics").
  This is independent, live confirmation of C-1009's `shell=False`
  requirement — a sibling AI-harness-bridge project got bitten by the
  exact class of bug the contract exists to prevent.
- **Escalating two-step kill with an unconditional first step** — send
  `SIGTERM` to the process group, `wait(timeout=grace)`, unconditionally
  escalate to `SIGKILL` on timeout. No branch asks whether the child
  "looks cooperative"; the only conditional is the deadline itself. Matches
  C-1009's SIGTERM→grace→SIGKILL exactly; independently corroborated
  pattern, not merely nox's own prior design.
- **Working-directory / CLI-not-found / stream-corruption as three
  distinct exception types**, not one generic subprocess error —
  `claude-agent-sdk-python` raises `CLIConnectionError` (bad cwd or spawn
  failure), `CLINotFoundError` (binary missing), and `SDKJSONDecodeError`
  (malformed line) as separate classes rather than inspecting exit codes.
  Maps cleanly onto `nox/outcome.py`'s `FailureReason` enum, which already
  keeps `ABSENT`, `MALFORMED_OUTPUT`, and `ISOLATION_FAILED` distinct for
  the same reason — external validation that this granularity, not a
  single `SubprocessError`, is the right cut.

## Key Findings

1. **`nox`'s closest real precedent streams by chunk, not by line, and
   nox's drain thread needs the same discipline.**
   `claude-agent-sdk-python` — Anthropic's own SDK, driving the identical
   `claude --output-format stream-json` CLI this ADR targets — explicitly
   documents that its transport layer "yields CHUNKS (one per receive()
   call, up to 64KiB on the asyncio backend), not lines, so a large line
   spans several chunks," and ships a dedicated `_LineFramer` to
   reassemble them before `json.loads`.
   [`subprocess_cli.py`](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/transport/subprocess_cli.py).
   Python's `for line in file_obj` iterator protocol already does correct
   buffering internally (it is not naive chunk-splitting), so if `nox`'s
   drain thread iterates the pipe object directly this is handled for
   free; the finding matters only if the plan's drain-thread
   implementation reads in fixed-size `os.read()` chunks itself (e.g. to
   interleave a byte-cap check per read) rather than delegating to the
   file object's own line iteration — in that shape, the reassembly logic
   must be written explicitly, mirroring `_LineFramer`.
2. **A live sibling project confirms the `shell=False` contract is not
   theoretical.** `openai/codex-plugin-cc` — architecturally the nearest
   *other* AI-harness bridge in the ecosystem (Codex app-server + broker,
   fresh Claude subprocess per invocation) — has an open bug where a
   Windows shell-wrapped spawn (`shell: process.env.SHELL || true`)
   corrupts the JSON-RPC stdio stream and hangs the child indefinitely.
   [openai/codex-plugin-cc#236](https://github.com/openai/codex-plugin-cc/issues/236),
   filed 2026, unresolved as of this research. This is the failure mode
   C-1009's `shell=False`/argv-list requirement exists to prevent,
   observed in production in a directly comparable codebase, not a
   textbook warning.
3. **The 64 KiB pipe-buffer deadlock is an active, current bug class, not
   folklore.** A 2026 issue against `agentscope-ai/agentscope`
   ([#1255](https://github.com/agentscope-ai/agentscope/issues/1255))
   reports exactly the classic failure: `wait()` called (or blocking
   `read()` awaited) before both streams are actively drained, subprocess
   output exceeds the OS pipe buffer, child blocks on write, parent blocks
   on wait/read, deadlock. Confirms the ADR's merged-stdout-stderr +
   dedicated-drain-thread design (C-1009) is addressing a live risk, and
   argues the contract suite should include a large-output fixture
   (>64 KiB single write) as a regression test for `supervise()`, not only
   a timeout/kill fixture.
4. **Windows process-tree kill is a materially different primitive, not a
   platform branch on the same call.** POSIX gets `os.killpg` after
   `start_new_session=True`; Windows has no equivalent signal-to-a-
   process-group concept. The documented approach is
   `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` at spawn time, then
   `proc.send_signal(signal.CTRL_BREAK_EVENT)` for a "graceful" attempt,
   falling back to `TerminateProcess` (what `Popen.kill()`/`terminate()`
   both map to on Windows — they are the same forceful call on that
   platform, unlike POSIX where they differ) —
   [Python docs, `subprocess`](https://docs.python.org/3/library/subprocess.html);
   [bpo-5115, killing process groups](https://bugs.python.org/issue5115).
   The excerpted `Runner`/`supervise()` contract (C-1009, C-1015) does not
   yet show this branch; since C-1009 already resolves the Windows
   `.cmd`-shim question, `Launcher`/`SubprocessRunner` is the natural
   place for the paired kill-side Windows branch, gated behind
   `sys.platform`.
5. **Strict-mode pyright's exhaustiveness checker and `assert_never` can
   conflict, not compose.** `reportMatchNotExhausted` is on by default
   under `typeCheckingMode: strict` and is pyright's own recommended
   mechanism for catching an unhandled `Literal`/union arm at type-check
   time. Pairing it with a hand-written `case _: assert_never(x)` fallback
   is redundant at best; on `basedpyright`, it actively triggers
   `reportUnnecessaryComparison`
   ([basedpyright#469](https://github.com/DetachHead/basedpyright/issues/469);
   [pyright discussion #5186](https://github.com/microsoft/pyright/discussions/5186)).
   For `nox/outcome.py`'s `Status`/`FailureReason` matches: prefer relying
   on `reportMatchNotExhausted` alone under strict mode, and reserve an
   explicit `assert_never` only for a match that must also be correct at
   *runtime* against an untyped/external value (e.g. a value arriving from
   `json.loads` on harness output) — which is a real case here, since
   `_classify()` in § 4.3 processes untrusted stream content, not a
   closed internal type.
6. **`pip pre-commit tox git-python pexpect` do not converge on one named
   pattern; they split into "hook the base primitive" vs. "inject a
   replaceable object."** Confirms and narrows the prior research's
   finding (`nox-pattern-precedent.md` §5): `pyinvoke/invoke`'s own
   maintainers describe the split directly — "the highest level
   sanity/integration tests really need to actually spawn subprocesses,
   while the rest should be able to work with a dependency-injected mock
   object" ([pyinvoke/invoke#25](https://github.com/pyinvoke/invoke/issues/25)).
   `pexpect` took the injection route explicitly:
   `pexpect.popen_spawn.PopenSpawn` wraps `subprocess.Popen` behind
   `pexpect`'s own `spawn`-like interface specifically so test code can
   swap the transport
   ([pexpect#411](https://github.com/pexpect/pexpect/issues/411)). No
   evidence found that `pip`, `git-python`, or `tox` themselves ship a
   named injectable subprocess seam in their own test suites (contrary to
   the research request's premise) — treat "pip/tox test their process
   layer via an injected seam" as unconfirmed; `nox`'s own `Runner`
   `Protocol` is closer in spirit to `pexpect`'s explicit-wrapper choice
   than to anything found in `pip` or `tox`.

**Negative / unconfirmed:** no source found describing how `pip` or `tox`
specifically structure subprocess-layer unit tests (both almost certainly
rely on integration-style tests against real subprocesses rather than an
injected seam, based on their nature as thin CLI wrappers, but this was not
directly confirmed and should not be cited as precedent without a follow-up
read of their test suites). Aider's `base_coder.py`/`models.py` and
OpenHands' `action_execution_server.py` were both confirmed to use
`subprocess.Popen` directly but neither codebase's *adapter seam or error
classification* could be pinned down to specific functions/classes in this
pass — both are large enough that a targeted file read (not a web search)
would be needed to extract a comparable-precedent paragraph; flagged here
rather than fabricated.

## Recommendation

Keep the ADR's threads-over-a-queue, `Runner`-wraps-creation-only design
exactly as specified — it is already the position the wider ecosystem
converges on, including the one sibling project (`claude-agent-sdk-python`)
solving the identical `claude --output-format stream-json` problem. Make
three small, additive amendments before `/hex-plan` decomposes the work
packages:

1. Add an explicit large-output (>64 KiB single write) fixture to the
   `supervise()` contract suite, alongside the existing timeout/kill
   fixtures — Finding 3.
2. Give `Launcher`/`SubprocessRunner`'s kill path a real Windows branch
   (`CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT` → `TerminateProcess`,
   distinct from the POSIX `os.killpg` path) rather than treating C-1009's
   POSIX kill sequence as portable — Finding 4. If nox v1 is POSIX-only by
   explicit decision, say so in the ADR directly (the current text
   resolves Windows for the `.cmd`-shim and `selectors` questions but is
   silent on the kill path specifically), since half-resolving
   cross-platform behavior is worse than declaring the scope cut.
3. In `nox/outcome.py`, write the `Status`/`FailureReason` `match` blocks
   to rely on strict-mode `reportMatchNotExhausted` rather than a
   catch-all `assert_never` branch for internal, already-typed values;
   keep `assert_never`-style runtime guards only where a match consumes
   untrusted harness stream content — Finding 5.

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| [claude-agent-sdk-python, `subprocess_cli.py`](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/transport/subprocess_cli.py) | Repo (Anthropic, official) | fetched 2026-09-02 | Closest real precedent: same target CLI, chunk-framing, kill escalation, typed error classes |
| [openai/codex-plugin-cc#236](https://github.com/openai/codex-plugin-cc/issues/236) | GitHub issue | filed 2026 | Live confirmation of the shell-wrapper JSONL-corruption failure mode C-1009 prevents |
| [agentscope-ai/agentscope#1255](https://github.com/agentscope-ai/agentscope/issues/1255) | GitHub issue | 2026 | Current, real-world 64 KiB pipe-buffer deadlock instance |
| [pyinvoke/invoke#25](https://github.com/pyinvoke/invoke/issues/25) | GitHub issue | — | States the injected-seam-vs-integration-test split explicitly |
| [pexpect/pexpect#411](https://github.com/pexpect/pexpect/issues/411) | GitHub issue | — | `PopenSpawn` as a named precedent for wrapping `Popen` behind an injectable interface |
| [Python docs, `subprocess`](https://docs.python.org/3/library/subprocess.html) | Official docs | current | `CREATE_NEW_PROCESS_GROUP`, `CTRL_BREAK_EVENT`, `Popen` context-manager semantics |
| [bpo-5115](https://bugs.python.org/issue5115) | Bug tracker | — | Confirms no built-in cross-platform "kill process group" primitive |
| [Discuss.python.org, "Details of process.wait() deadlock"](https://discuss.python.org/t/details-of-process-wait-deadlock/69481) | Forum (python.org, official) | 2026 | Canonical explanation of the wait-before-drain deadlock |
| [pyright discussion #5186](https://github.com/microsoft/pyright/discussions/5186) | GitHub discussion (Microsoft, official) | — | `assert_never` + `match` interaction under strict mode |
| [basedpyright#469](https://github.com/DetachHead/basedpyright/issues/469) | GitHub issue | — | Concrete `reportUnnecessaryComparison` conflict with `assert_never` |
| [Coverage.py docs, "Excluding code"](https://coverage.readthedocs.io/en/latest/excluding.html) | Official docs | current | `exclude_also`, branch-coverage-and-excluded-clause interaction, confirms `# pragma: no cover` clause-wide exclusion semantics for C-1015's single-line carve-out |
| [`nox-pattern-precedent.md`](nox-pattern-precedent.md) | Local prior research | 2026-08-31 | Not repeated here; extended on §5 (testing seam) and left §1-4, §6 untouched |
