# Discussion: nox — multi-harness adversarial review

State: handed-off → architect
Updated: 2026-08-31
Ratified: 2026-08-31 → architect
Confidence: ratified by Michael Herwig. Backed by six researcher lanes run
2026-08-31 — codebase recon, prior-art web scan, competitive/vendor, and a
three-seat council (premortem, simplicity, operability). Weakest evidence:
the cross-model asymmetry result is one unreplicated 116-task paper; Cursor
and Copilot flag surfaces are search-summarized, not primary-verified; ToS
quotes are secondary-sourced.

## Problem

`openai/codex-plugin-cc` gives Claude Code an adversarial reviewer backed by
Codex. It is single-vendor in both directions: only Codex reviews, and only
Claude Code can ask. Generalise it — any supported harness can be asked to
adversarially review work done in any other. Target harnesses: Claude Code,
Codex, Copilot, Cursor.

## Settled

- **Drain target: ADR** (`/hex-architect`, tier ≥ medium — the fast path
  refuses low).
- **Boundary: standalone product**, not a hex-internal phase. hex becomes its
  first consumer by re-pointing `hex.md › Preferences: Cross-model adversary`
  (today pinned to the `codex:rescue` skill) at nox.
- **Delivery form: a shared Python library shipped as a script asset**, with
  facades/interfaces the per-harness adapters satisfy. Not an MCP server, not
  a pure-markdown argv table. **Single skill carrying its own script** — the
  original `nox-core` + siblings shape is withdrawn: grim installs `scripts/`
  verbatim per client, but explicitly does not guarantee a stable on-disk path
  across clients (`grim-usage/references/consume.md:239`), so a relative path
  from a sibling skill to `nox-core/scripts/` is unsafe.
- **Auth: the user's own installed, logged-in harness CLI.** Not metered API
  keys — an API key buys a model, not a harness, and the agentic loop plus
  repo tooling is what makes harness review worth more than a chat completion.
- **Review directions: full N×N, user picks.** Owner's decision, made with the
  asymmetry evidence on the table (see Open questions).
- **Transport is an implementation detail behind the facade.** Codex's
  app-server JSON-RPC approach may be reused internally; the contract is the
  interface, not the wire format.
- **nox is its own repository**, not a directory in arcana. arcana is a
  pure-markdown grimoire; a project carrying uv, ruff, pyright, pytest,
  mkdocs and a taskfile does not belong in it.
- **The grim skill lives inside the Python repo** — `skill/SKILL.md` plus a
  CI-built `skill/scripts/nox.pyz`. One repo, one tag, one version. This is
  what dissolves the version-bump coupling the owner raised at the outset:
  the skill carries its own copy of the library, so there is no
  publish-then-bump-the-pin dance.
- **Ship as a `zipapp` `.pyz`, built in CI at release, never committed.**
  `python -m zipapp src/nox -o skill/scripts/nox.pyz -p "/usr/bin/env python3"
  -m "nox.cli:main"`. Zero dependencies means nothing to vendor, so the
  archive is trivially pure Python. The argument is not packaging — grim
  installs `scripts/` verbatim either way — it is that **a skill directory is
  context a consuming agent reads**: a fifteen-file package tree sits in that
  context surface, one opaque `.pyz` does not.
- **PyPI is optional and load-bearing on nothing.** hatchling produces a wheel
  for free; publish it as an unpinned convenience for `uvx` reach. Nothing in
  the skill path depends on it.
- **Zero runtime dependencies.** `subprocess`, `json`, `shutil.which`,
  `threading`, `signal`, `dataclasses` cover the whole surface. Dataclasses
  over pydantic for the finding schema.
- **Isolation: read-only same working tree**, diff passed in the prompt. No
  per-adversary worktree, no container.
- **No vendored copies.** One script, one home; the "every skill carries a
  copy of the library" shape is rejected.
- **hex needs no changes.** Its adversary seam is already vendor-neutral —
  `hex/hex-core/references/protocol.md:1210` § Adversary contract, selected by
  `adversary: <skill-name>` in `hex.md › Preferences`, documented in 7 files as
  "only an example value", and it already degrades gracefully when the named
  skill is absent. nox becomes a valid value; no integration work.

## Interface requirements

The facade must carry, at minimum:

- **Heartbeat, with its fidelity in the type.** Liveness is not uniform across
  targets: Codex (app-server JSON-RPC notifications) and Claude Code
  (`--output-format stream-json`) give semantic per-event liveness; Cursor
  claims the same but is unverified; Copilot CLI has `-p` with no documented
  stream format and no exit-code table, leaving only process-liveness plus
  stdout byte activity. Proposed shape:
  `Heartbeat { last_activity_at, kind: Semantic | ByteActivity | ProcessOnly }`,
  with timeout policy set per `kind`. A flattened `is_alive()` forces one
  timeout that is either too aggressive for Copilot's silent stretches or too
  slow to catch a hung Codex.
- **Config: normalized core plus per-harness escape hatch.** Core:
  `model`, `read_only`, `timeout`, `tools_allowed`. Escape hatch: opaque
  per-harness passthrough, because `--permission-mode`, `--allow-tool` and
  `--sandbox` do not map onto one another.
- **Read-only does not normalize.** `codex --sandbox read-only` is a
  harness-enforced sandbox; Copilot's `--deny-tool` is a denylist. Different
  guarantees. With no per-adversary worktree, these flags are the only
  containment.
- **Four distinguishable failure states**, none requiring an interactive
  prompt: harness absent · present but unauthenticated · authenticated but
  rate-limited · ran but returned garbage.

## Council

Three blind seats (premortem, simplicity, operability) on whether nox should
exist given hex's seam is already vendor-neutral and `codex-plugin-cc` already
fills the Claude→Codex direction.

**Convergence.** All three independently identify full N×N as the weakest
decision — 12 directed edges, one measured-good, one measured-harmful, ten
unmeasured.

**Divergence.** Premortem and simplicity both rank "unnecessary/duplicative"
as the leading failure mode; operability assumes it ships and prescribes
day-one requirements. Simplicity recommends building nothing, on the argument
that `codex:rescue` is unreachable outside a hex orchestrator run — that
argument is **rejected**: it was inferred from `hex.md`'s memory log rather
than from the skill, and `codex-plugin-cc` already ships `/codex:review` and
`/codex:adversarial-review` as standalone commands.

**Synthesis.** The Claude→Codex direction is covered twice over. nox's
uncovered value is therefore *entirely* in the remaining directions — Copilot,
Cursor, and Claude-as-reviewer invoked from Codex/Copilot/Cursor — which is
the owner's original complaint, and also precisely where the evidence is
thinnest. Premortem's preventive framing is adopted: nox is an **adapter into
hex's existing adversary seam**, never a parallel one.

**Day-one operability requirements, adopted:**

1. **Never gate success on exit code.** Claude Code surfaces auth failures in
   the stdout JSON result, not a distinct exit code — a script trusting exit 0
   reports "review passed" on an auth failure. Copilot documents no exit-code
   table. Require structured output from every harness; each adapter maps its
   harness's signal to ok / error / **indeterminate**, and anything it cannot
   positively classify surfaces raw, never coerced to "passed".
2. **Hard wall-clock timeout, SIGTERM→SIGKILL, enforced by the script.**
   Claude Code's headless default permission mode is Manual — an adapter that
   omits the override blocks forever on a prompt that never arrives. Exit 143
   is labelled "we killed it", not folded into generic failure.
3. **Serialize adversary calls against one working tree by default.** With no
   worktree, containment is per-harness flag trust. Each adapter must
   positively enumerate a deny-write list and refuse to launch any harness it
   cannot enumerate for. No concurrent fan-out until real isolation exists.
4. **Record the harness version each adapter was verified against** and warn
   on mismatch at invocation, so churn surfaces as "untested against vX"
   rather than a silent misparse.
5. **Log every call locally** (harness, timestamp, outcome) — no vendor
   exposes a pre-call quota check, and the documented lockout tail risk has no
   warning.

## Python project shape

Modelled on the sibling `ocx-sdk-python` (`/home/mherwig/dev/ocx-sdk-python`),
which is already this shape and already ships `dependencies = []`.

- **Layout**: `src/` layout, hatchling build backend, uv for the environment.
- **Lint/type**: ruff with `E,W,F,I,B,UP,ANN,RUF,D` and the google docstring
  convention; pyright `strict` on `src`, standard on tests.
- **Tests**: `tests/{unit,contract,acceptance}/` — the split
  `ocx-sdk-python` already uses.
- **Coverage**: branch coverage, `fail_under = 100`, with the single
  un-testable `subprocess.Popen(...)` call behind a `Runner` seam that tests
  inject a fake for, and a `# pragma: no cover` on that one production line.
  Owner accepted either this or a slightly-below-100 threshold; the pragma is
  preferred, because a drifting threshold hides regressions the exclusion
  does not.
- **Why the seam matters more than the number**: 100% on subprocess adapters
  otherwise means mocking `Popen`, which verifies the code against *our model*
  of each CLI rather than against the CLI. The operability seat's top-ranked
  failure — Claude Code returning exit 0 with an auth failure inside the
  stdout JSON — is precisely the class a mock renders invisible, because the
  mock encodes the belief being tested. Adapter fidelity therefore lives in
  `tests/contract/`, running the real binary and skipping via `shutil.which()`
  when it is absent. The coverage number measures pure logic; it is not
  evidence that the adapters are correct.

Sketch:

```
nox/                          # own repo
├── pyproject.toml            # dependencies = []; ruff/pyright strict; fail_under = 100
├── src/nox/
│   ├── cli.py                # zipapp entry — nox.cli:main
│   ├── harness.py            # facade: Harness protocol, Heartbeat, tri-state Outcome
│   ├── runner.py             # the Popen seam — injectable, pragma'd
│   ├── config.py             # normalized core + opaque per-harness passthrough
│   └── adapters/{claude,codex,copilot,cursor}.py
├── tests/{unit,contract,acceptance}/
└── skill/
    ├── SKILL.md
    └── scripts/nox.pyz       # CI-built at release, gitignored
```

## Open questions

- [NEEDS CLARIFICATION: which harnesses ship in v1?]
  Recommended: Codex + Claude Code, with a documented adapter contract for
  Copilot and Cursor. `codex-plugin-cc` already proves the Codex path end to
  end; `cursor-agent` is not installed on the author's machine and its flag
  surface is search-summarized only, not primary-verified.
- **Cross-model review is asymmetric, and full N×N ships a measured-negative
  cell.** arXiv:2607.21656 (2026-07-22, 116 tasks, unreplicated): Claude
  reviewing Codex 71.6%→89.7% (p=.001); Codex reviewing Claude 91.4%→82.8%
  (p=.046, worse). Owner chose full N×N with this on the table. Carried as a
  documented risk for the ADR, not a gate. Caveat: one paper, two models, five
  weeks old, and arXiv:2604.16790 shows LLM-judge verdicts are prompt-sensitive
  enough to flip model rankings.
- **Terms-of-service exposure.** Anthropic's Jan 9 2026 enforcement broke
  third-party harnesses riding Claude subscription OAuth (OpenCode broken,
  Windsurf cut off since Jun 2025, some Cursor configs). Shelling to the user's
  own installed `claude` binary is materially different from spoofing the
  harness identity, but Consumer ToS §3 bans automated non-human access outside
  an API key, and unattended review runs are automated access. ToS quotes are
  secondary-sourced; the ADR should verify against primary terms.
- **Headless auth has a documented lockout mode.**
  anthropics/claude-code#47754 — Cloudflare WAF blocking headless OAuth token
  refresh (403/429), 26+ days locked out, no recovery short of browser
  re-auth.
- Read-only enforcement differs per vendor and is now the only containment.
  Proposed mitigation: the script asserts read-only via each harness's own
  flag and refuses to launch any harness whose read-only mode it cannot
  positively assert. Pending recon evidence on what each CLI exposes.
- Whether a Python runtime is an acceptable hard dependency for a repo whose
  artifacts are, today, entirely markdown — recon confirmed zero executable
  assets exist in arcana.

## Related

- `openai/codex-plugin-cc` — the single-vendor precedent being generalised.
  Apache-2.0, 32.6k stars. Speaks Codex's app-server JSON-RPC over stdio with
  an optional Unix-socket broker; not `codex exec`. Size-gated inline diff,
  else Codex self-collects. Findings against a checked-in JSON Schema.
- `.agents/research/discuss-nox-priorart.md` — headless flag surfaces for all
  four targets, cross-model review evidence, failure modes.
- `.agents/research/discuss-nox-vendor.md` — vendor landscape, ToS, isolation
  and metering.
- Amp's Oracle sub-agent and Zen/PAL MCP — the two closest working precedents
  for cross-vendor second opinions.
- Installed `codex:*` plugin skills (`rescue`, `setup`, `codex-cli-runtime`,
  `codex-result-handling`) — existing Codex bridge on this machine.
- `.agents/memory/hex.md` › Preferences — the `Cross-model adversary` pin nox
  would replace.
- `hex/DESIGN.md` — `hex-core` shared-contract precedent for the `nox-core`
  shape.

## Out of scope

- Building nox. This discussion drains to an ADR.
- Changing `hex-review`'s own phase structure — its adversary seam already
  takes nox as a value with no modification.
- MCP-server delivery. Considered and rejected in favour of the script asset.
- Metered-API-key auth. Considered and rejected: an API key buys a model, not
  a harness.
- Per-adversary git worktrees and containers. Considered and rejected in
  favour of read-only against the shared tree.

## Verification

The eventual ADR is checked against `hex/DESIGN.md` and gated by
`/hex-architect`'s adversarial review phase. Any resulting skill is verified
with `grim build <skill-dir>` per changed skill and `task publish -- --dry-run`
for the full sweep.
