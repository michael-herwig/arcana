# The live cross-harness matrix

Every harness in `nox.adapters.ADAPTERS` driving `nox review` against every
harness in it — 4 × 4 = 16 cells today, self-pairs included. A cell passes when
the *report file nox wrote* shows the named adversary reached, containment
established, and a harness-origin finding reporting the defect the fixture planted.
That is the proof that nox drives a **foreign** harness end to end, and that
nothing special-cases the same-harness path.

**Never in CI.** Every cell needs real provider credentials and reaches the
network twice — once as the driver, once as the adversary. Nothing here is
hermetic, and nothing here is a `pytest` test. The hermetic half of WP12 lives
in `tests/unit/test_manual_smoke.py`, which spends nothing.

## Preconditions

nox forwards **no credential to any harness** (C-1002, D-ad). Every harness
authenticates from its own store; the smoke only needs those stores populated.

| Harness | What must be true |
|---|---|
| `claude` | on `PATH` and logged in |
| `copilot` | on `PATH` and logged in |
| `codex` | logged in — `~/.codex/auth.json` present |
| `opencode` | reached through the `ocx package exec` launcher (below), and authenticated **from its own file store** |

opencode is not on `PATH` and is not reachable by the sibling `ocx exec`, which
resolves its pin from the *project's* `ocx.toml` and fails outside an ocx
project. Put the launcher in `~/.config/nox/nox.toml`:

```toml
[harness.opencode]
launcher = ["ocx", "package", "exec", "ocx.sh/anomalyco/opencode:1.18.22", "--"]
```

Its credential is a file: `$XDG_DATA_HOME/opencode/auth.json`, default
`~/.local/share/opencode/auth.json`, mode `0600`, installed by the operator out
of band. **Do not set `GITHUB_TOKEN`** — nox's `DENY_PATTERNS` drops it by
design, and an opencode leg that appears to work only because a token was in the
ambient environment is not evidence of anything.

## Running it

```sh
task nox:manual:matrix                        # every registered pair, serially
task nox:manual:cell -- claude copilot        # exactly one pair
```

Without `--cell`, the two positionals are optional *filters*:
`task nox:manual:matrix -- claude` runs one driver against every adversary.

## What it looks like

```
About to run 16 live cell(s): real tokens on every vendor these pairs name.
claude -> claude : pass
claude -> codex : pass
claude -> copilot : pass
claude -> opencode : skip (unauthenticated)
codex -> claude : pass
...
opencode -> opencode : skip (unauthenticated)

12 pass / 0 fail / 4 skip
```

Every leg whose **adversary** is opencode skips on a machine whose auth store is
empty — that is `FailureReason.UNAUTHENTICATED` coming back from the review, not
a nox defect, so the sweep still exits `0`. A failing cell additionally prints
the last 40 lines of the report nox wrote — or, when the driver never
produced one, of the driver's own captured output.

## Transcripts — what is still there afterwards

A sixteen-cell sweep runs for about half an hour, and the line that went red has
scrolled long before it ends. So **every cell writes its own transcript**:

```
nox/.manual-runs/20260904T142233-k3ba9x/claude__opencode.txt
```

Each file carries the pair, the outcome and its reason, **the argv that actually
ran** (model substituted, prompt included — so it names the exact `nox review`
command the driver was given), the driver's exit status, the report nox wrote
**in full**, and the driver's own captured output **in full**. The console only
ever shows a 40-line tail of one of them.

The run prints its directory before the first cell, and the tally at the end
names the transcript of every cell that failed — the two places an operator is
still looking. A re-run gets a directory of its own and never overwrites the
evidence of the run it is re-running. Set `NOX_MANUAL_RUNS_DIR` to move them.

**There is no retry, no tolerance and no allowed-flake budget, on purpose.** A
tolerance converts a real intermittent failure into noise, which is strictly
worse than a red cell somebody has to look at. This matrix has twice reported a
failure nobody could name; the defect was that the evidence evaporated, not that
the cell went red.

## Exit codes

| Command | Codes |
|---|---|
| `task nox:manual:matrix` | `0` / `1` — non-zero **iff a cell failed**. Skips never fail a sweep, so the matrix is runnable on a machine carrying two harnesses. |
| `task nox:manual:cell` | `0` pass / `1` fail / `77` skip. Only the single-cell target reports a skip through its status. |

**`task` does not pass a child's status through** — it collapses every non-zero
code to its own `201`, so a skipped cell and a failed one are indistinguishable
by exit code through the plain form. Read the printed line, which always says
which it was; automation that must branch on `77` takes `task -x`:

```sh
task -x nox:manual:cell -- claude opencode    # 0 / 1 / 77, verbatim
```

`ABSENT` and `UNAUTHENTICATED` are the only reasons that skip. `UNSUPPORTED`,
`RATE_LIMITED` and `INVALID_CONFIG` stay red on purpose.

## Overrides

| Variable | Effect |
|---|---|
| `NOX_MANUAL_MODEL_<HARNESS>` | Pins the **driver-side** model literal for that harness, e.g. `NOX_MANUAL_MODEL_CLAUDE`. Otherwise each side resolves its own adapter's `fast-balanced` entry. |
| `NOX_MANUAL_TIMEOUT_S` | Per-cell wall clock. Default is nox's review budget plus 600 s for the driver's own turns. |
| `NOX_MANUAL_RUNS_DIR` | Where the per-run transcript directory is created. Default `nox/.manual-runs/`, which is gitignored. |

## Cost

A full sweep is **real tokens on every vendor in the registry**, on both sides of
every cell: sixteen driver sessions and sixteen adversary reviews. Budget roughly
one to three minutes per cell, so a clean sweep is on the order of half an hour.
Re-run a single red cell with `task nox:manual:cell` rather than the whole sweep.

## What this does not prove

The **driver** side runs the operator's own harness binary, unsandboxed, with the
operator's own user settings loaded — hooks, user instruction files, MCP servers,
whatever is configured. That is inherent to driving the real binary: there is no
way to prove a harness can drive nox except by letting it be itself. Each
`DRIVERS` entry therefore carries exactly the one permission grant that harness
needs to run a shell command, and nothing more.

nox's containment claim is about the **adversary** side only. No flag from the
driver side reaches it: `review()` rebuilds the adversary's argv through
`adapter.prepare` and its environment through `minimal_env`, over an ephemeral
worktree. The containment stamp in the report describes that side, and a cell
that cannot show an established mechanism there fails.
