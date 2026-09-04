# copilot fixtures — how each was recorded (E3)

Every file here came off the installed binary on 2026-09-03. None was copied
from a document. `verified_against` in `nox/src/nox/adapters/copilot.py` is set
from `version-1.0.82.txt` and nothing else.

Binary: `~/.npm-global/bin/copilot`, **GitHub Copilot CLI 1.0.82**, authenticated.

| File | Command |
|---|---|
| `version-1.0.82.txt` | `copilot --version` |
| `help-1.0.82.txt` | `copilot --help` |
| `output-format-json-1.0.82.txt` | `copilot --no-color --log-level none --output-format json --disable-builtin-mcps --no-custom-instructions --deny-tool shell --deny-tool write --model gpt-5.6-luna -p 'Reply with exactly: NOX-JSON-OK'`, stdout |
| `text-footer-1.0.82.txt` | the same run with `--output-format text` — **stderr**, verbatim |
| `tools-1.0.82.txt` | the tool names Copilot offered the model, read off `model.model_call_success.data.requestCapture.tools` in a live `--output-format json` run |
| `error-invalid-model-1.0.82.txt` | the same shape with `--model definitely-not-a-model`: stdout then stderr, concatenated in that order because they were captured on separate pipes. Exit 1, and **no `result` line** |
| `tool-visibility-1.0.82.txt` | **seven** live runs' `toolCount` and offered tool list, one row each, with the permission argv that produced it — the evidence behind emitting `--available-tools`. The last three add a user-configured MCP server (below) |
| `error-unauthenticated-1.0.82.txt` | the shipped review argv run **through nox's own C-1008 minimal environment** (`task nox:test:contract`): stderr, exit 1, **no JSONL at all**. Not reproducible from an ordinary shell — see below |
| `review-shaped-1.0.82.txt` | **the shipped argv**: `copilot --no-color --log-level none --output-format json --model gpt-5.6-luna --effort high --max-ai-credits 30 -p '<prompt>' --available-tools view,rg,glob --deny-tool <14 names> --disable-builtin-mcps --no-custom-instructions`. `toolCount: 3`, `reasoningEffort: high`, the model called `view` with no allow flag, exit 0 |

## What was elided from the JSONL fixture, and why

`output-format-json-1.0.82.txt` holds every `session.*`, `user.*`,
`assistant.*`, `tool.*` and `result` line of that run **verbatim**. The
`model.*` events are dropped: `model.messages_snapshot` carries Copilot's own
35 KB system prompt, which is the vendor's text and does not belong in this
repository, and the rest is request telemetry. `parse()` reads none of them —
it reads the last `assistant.message` and the `result` line — so the fixture is
complete with respect to what the adapter consumes.

The same rule is applied **inside** the retained lines, which the first pass
missed: every `encryptedContent`, `apiCallId` and `reasoningOpaque` value is
replaced by an `<elided: N bytes of vendor telemetry>` marker, the
`<system_reminder>` fragment of copilot's prompt by a one-line marker, and the
recording machine's own scratch path — which carried a session uuid — by
`/tmp/nox-probe/`. Every line still parses as JSON and the adapter reads none
of the elided fields. A scan of the whole directory for `gh[pousr]_`,
`github_pat_` and bearer shapes returns nothing; the two session ids that
remain (`--resume=…`, `result.sessionId`) are local-store handles.

## Four shapes the recordings pin that a document would have got wrong

1. **The stats footer is on stderr, not stdout.** The plan's Environment probe
   records it as trailing stdout. `SubprocessRunner.spawn` merges stderr into
   stdout, so it still reaches `parse()` interleaved with the JSONL — which is
   why `parse()` skips unparseable lines rather than assuming a pure stream.
2. **`--deny-tool` does not remove a tool from the model's list.** A run
   denying fourteen tools was still offered all seventeen
   (`toolCount: 17`); `--available-tools view,rg,glob` was offered exactly
   three. `--deny-tool` is a permission control, `--available-tools` is the
   tool-removal one, and the adapter emits both.
   `tool-visibility-1.0.82.txt` is that comparison as a committed table.
3. **`--max-ai-credits` has a floor of 30.** `--max-ai-credits 25` is
   refused outright: `Use at least 30 AI credits.` So `MAX_AI_CREDITS` is
   the tightest bound the binary accepts, not a chosen ceiling.
4. **`--disable-builtin-mcps` does not disable a user's MCP server**, and
   `--available-tools` does. The first four `tool-visibility` rows were recorded
   with no MCP server configured, so they could not tell the two apart: the
   containment claim rested on a flag whose name reads like it covers the case
   and whose `--help` text says otherwise ("Disable all built-in MCP servers
   (currently: github-mcp-server)"). 1.0.82 has no `--strict-mcp-config`
   analogue, so `~/.copilot/mcp-config.json` loads regardless.

   Re-probed on 2026-09-03 against a throwaway stdio MCP server offering one
   tool, `nox_canary`, injected with `--additional-mcp-config @<file>`. All
   three runs carried `--disable-builtin-mcps --no-custom-instructions`, the
   `-p 'Reply with exactly: NOX-JSON-OK'` prompt and `--model gpt-5.6-luna`;
   the tool list is `model.model_call_success.data.requestCapture.tools` as
   before:

   | permission argv | toolCount | `noxcanary-nox_canary` offered? |
   |---|---|---|
   | (none) | 18 | **yes** |
   | `--deny-tool <14 names>` | 18 | **yes** |
   | `--available-tools view,rg,glob --deny-tool <14 names>` | 3 | no |

   The MCP tool is named `<server>-<tool>` in the model's list, so
   `DENIED_TOOLS` — derived from a zero-MCP `PINNED_TOOLS` — can never name it,
   and `--deny-tool` cannot reach it. `--available-tools` is closed by
   construction and does. That is what `network_enforcement="harness"` rests
   on, and the reason the allowlist is not redundant beside the deny list.

## The one shape nox's own environment produces and an ordinary shell does not

`copilot` on this machine is authenticated by an **environment token**, not by
an on-disk OAuth store: `~/.copilot/` holds `config.json`, settings and a
session store, and no credential. C-1008 drops `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`
and `GITHUB_TOKEN` **twice over** — none is in `config.ALLOWLIST`, and all three
match `DENY_PATTERNS` (`*_TOKEN`, `GH_*`, `GITHUB_*`) — so a review launched
through `minimal_env` reaches the binary with no credential and exits 1 having
emitted `error-unauthenticated-1.0.82.txt` and nothing else.

That is C-1008 working, not failing: forwarding it would put a credential VALUE
across the boundary, which C-1002 forbids. The route that works is the harness's
own store — `copilot`, then `/login`, which writes under `$HOME/.copilot/`, and
`HOME` **is** forwarded. Same resolution as opencode's D-ad.

Consequences recorded rather than patched around:

- `AUTH_ENV_HINTS["copilot"]` is empty and `CLASSIFY` is empty, so this shape
  resolves `indeterminate`/`MALFORMED_OUTPUT` rather than `UNAUTHENTICATED`.
  Mapping it needs a substring match on a message, which the `Adapter.classify`
  contract forbids on its own authority — a finding for the owner, not a silent
  edit. The fixture is here so whoever decides it has the evidence.
- `--version` still exits 0 logged out, so `probe()` cannot see this. It is a
  review-time shape, which is why C-1034(4)'s hint belongs on the parse leg.
