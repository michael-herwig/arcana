# Research: nox — env hygiene, Codex sandbox gate, git-plumbing tests, severity vocab, cross-model asymmetry

<!--
Domain/security research feeding the items ADR 0011 explicitly deferred to
/hex-plan (§ "Deferred to /hex-plan"): the config.py env allowlist (C-1008),
the adapters/codex.py trust+sandbox gate (C-1017), workspace.py's git-fixture
test strategy, the severity-vocabulary wire format (C-1018), and the C-1020
selection-time asymmetry warning.
-->

## Metadata

**Date:** 2026-09-02
**Domain:** security
**Triggered by:** ADR 0011 `nox_multi_harness_adversary` § "Deferred to
/hex-plan" (adr_0011_nox_multi_harness_adversary.md ≈ line 2222) and
adr_0011_system_design.md § 5.5/5.5b (T4/T4b) and § 6 per-harness invocation
**Expires:** 2026-11-30 — confirmed during this pass (see Finding 2) that
Codex shipped 8 stable tags (0.144.0→0.152.1) plus dozens of alphas in the
~55 days before this research and the CLI installed locally (0.144.1) is
already 7 stable releases behind upstream; re-verify all Codex flag/behavior
claims against the currently-installed `codex --version` before the plan
executes, not against this document's version-pinned tables.

## Direct Answer

1. **Env allowlist (C-1008):** keep the existing infra-survivor list
   (`nox-security.md`'s table) and existing credential-pattern denylist, and
   add four items that table doesn't cover because they are code-execution or
   config-injection primitives, not credential-shaped: `NODE_OPTIONS`
   (Claude Code is an npm/Node binary — `--require` via `NODE_OPTIONS` is
   documented arbitrary-module-load), `LD_PRELOAD`/`DYLD_INSERT_LIBRARIES`
   (applies to any dynamically-linked binary, so it covers Codex's Rust
   binary and OpenCode's Bun/Go binary too), `OPENCODE_CONFIG_CONTENT`
   (OpenCode's documented *inline* config-override env var — content, not a
   path, so forwarding it bypasses every file-based trust boundary in one
   variable), and `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_<n>`/`GIT_CONFIG_VALUE_<n>`
   (overrides git config for every git subprocess the *harness itself*
   shells out to, undermining nox's own `-c core.hooksPath=/dev/null`
   discipline one level down). `PATH` sanitization: drop empty/relative
   entries and any entry that resolves inside the repository worktree under
   review.
2. **Codex sandbox gate (C-1017):** `sandbox_mode` (`read-only |
   workspace-write | danger-full-access`) is confirmed as the sole gate —
   `-s/--sandbox` exists on bare `codex exec` but is **absent from
   `codex exec review --help`**, so the review path must use
   `-c sandbox_mode="read-only"`. There is no dedicated
   sandbox-denial event in `--json`'s JSONL stream — enforcement proof has to
   come from a nox-authored probe (attempt a write, assert the
   `command_execution` item's `status` is `"failed"`/`exit_code` nonzero),
   not from a schema field the harness hands you. Two upstream changes since
   the ADR's 0.144.1 probe are directly relevant: 0.148.0 made sandbox
   denial fail-closed for unreadable paths on Linux/Windows, and **0.150.0
   stopped honoring `AGENTS.md` for untrusted projects** — closing the one
   gap nox-security.md's Addendum 2 flagged as open ("I found no flag to
   suppress it").
3. **Git-plumbing tests:** build fixtures with `git init -q` +
   `commit-tree`/`mktree`/`update-index --add --cacheinfo <mode> <sha> <path>`
   (120000/160000 entries need no real symlink or submodule on disk) +
   `worktree add --detach`; isolate from the operator's config with
   `GIT_CONFIG_GLOBAL=/dev/null` + `GIT_CONFIG_NOSYSTEM=1` on the test
   subprocess env (not a `HOME` override — it also relocates credential
   lookups you don't want touched); plant a hostile `core.hooksPath`/
   `filter.*.smudge` in the *fixture* via `GIT_CONFIG_COUNT`/`KEY_0`/`VALUE_0`
   and assert nox's own `-c core.hooksPath=/dev/null` invocation left the
   hook's marker file absent. Minimum Git version: **2.32.0** (first version
   whose docs carry `GIT_CONFIG_GLOBAL`; `GIT_CONFIG_COUNT` landed one minor
   earlier at 2.31.0) — comfortably below any real dev/CI floor.
4. **Severity case (C-1018):** ship lowercase. OpenAI's own
   `codex-plugin-cc` schema — the precedent nox is explicitly modeling
   itself on — uses `severity: enum["critical","high","medium","low"]` and
   `verdict: enum["approve","needs-attention"]`, both lowercase; SARIF's own
   `level` is lowercase `error|warning|note|none`. Two independent, primary,
   directly-fetched precedents for the same convention.
5. **C-1020 warning key:** arXiv:2607.21656's measured-negative cell is
   pinned to exact identifiers — writer **`claude-opus-4-7` through Claude
   Code 2.1.50**, reviewer **`gpt-5.5` through Codex CLI** — not to harness
   names. The warning must key on `Review.model` (the underlying model
   identifier nox already plans to record), not on "harness is Codex", or it
   both under- and over-fires once model versions move past this pinned pair.

## Key Findings

### 1. Environment allowlist/denylist — new inbound-channel entries for C-1008

`nox-security.md`'s existing table (infra survivors: `PATH`, `HOME`, `USER`/
`LOGNAME`, `TERM`, `LANG`/`LC_ALL`, `TMPDIR`, `HTTP_PROXY`/`HTTPS_PROXY`/
`NO_PROXY`, `SSL_CERT_FILE`/`NODE_EXTRA_CA_CERTS`/`REQUESTS_CA_BUNDLE`,
Windows `SystemRoot` etc., `XDG_CONFIG_HOME`/`XDG_DATA_HOME`,
`CLAUDE_CONFIG_DIR`; credential-pattern denylist: `*_TOKEN`, `*_KEY`,
`*_SECRET`, `*_PASSWORD`, `AWS_*`, `GITHUB_*`, `GH_*`, `NPM_*`, `PYPI_*`,
`OPENAI_*`, `DATABASE_*`) is confirmed still correct against current primary
docs and is the right foundation. This pass adds what that table doesn't
cover — vars that are dangerous not because they *look* like a credential but
because they are a **code-execution or config-injection primitive**:

| Variable | Why it's an inbound channel | Harness affected |
|---|---|---|
| `NODE_OPTIONS` | Node reads this at process startup for *any* invocation and honors `--require <module>` from it — a documented arbitrary-module-load primitive, confirmed on Node's own docs [nodejs.org/api/cli.html](https://nodejs.org/api/cli.html#node_optionsoptions). Claude Code ships as an npm package running on Node. Anthropic's own env-vars reference does **not** mention `NODE_OPTIONS` (confirmed by direct fetch — see Sources), so `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` (which targets "Anthropic and cloud provider credentials," verbatim) does not cover it either. | Claude Code |
| `LD_PRELOAD` / `DYLD_INSERT_LIBRARIES` | Injects a shared library into any dynamically-linked ELF (Linux)/Mach-O (macOS) process regardless of language runtime [systemshardening.com, "Linux Shared Library Security"](https://www.systemshardening.com/articles/linux/linux-shared-library-security/). Covers Codex's Rust binary and OpenCode's Bun/Go binary, not just Claude Code. | All three |
| `OPENCODE_CONFIG_CONTENT` | OpenCode's documented **inline** config override — the value itself is the config, not a path to one — sitting in the precedence chain between global config and project config: "remote config → global config → custom config (`OPENCODE_CONFIG`) → project config → `.opencode/` dirs → **inline config (`OPENCODE_CONFIG_CONTENT` env var)** → managed config," verbatim from [opencode.ai/docs/config/](https://opencode.ai/docs/config/) (fetched directly). Forwarding whatever a CI system or shell profile happens to have set here silently overrides OpenCode's behavior — including MCP server declarations — with no file on disk to audit. Not credential-shaped, so the existing pattern denylist misses it entirely. | OpenCode |
| `OPENCODE_CONFIG` | Same precedence chain, one layer earlier — a path override rather than inline content, so lower severity than `_CONTENT` but same treatment (deny unless nox itself sets it). | OpenCode |
| `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_<n>` / `GIT_CONFIG_VALUE_<n>` | "These environment variables will override values in configuration files, but will be overridden by any explicit options passed via `git -c`," verbatim, [git-scm.com/docs/git-config](https://git-scm.com/docs/git-config) (§ ENVIRONMENT, fetched directly). If forwarded from the parent shell, they win over every config *file* the harness's own `git` subprocess invocations read — including nox's own `-c core.hooksPath=/dev/null` guard is safe (`-c` beats env), but any git call the *harness* itself makes without that flag is not. | All three (any harness that shells to `git`) |

**`PATH` sanitization** (both team-lead's ask and confirmed as the right
rule by the precedent above): drop empty entries, drop entries that don't
start with `/` (POSIX) or aren't drive-rooted (Windows), and drop any entry
that resolves (post-`os.path.realpath`) inside the repository worktree under
review — a hostile branch that ships a `./bin/git` or `./node_modules/.bin/`
shim must not be able to shadow the real harness/git binary nox intends to
run.

**Negative:** none of the three v1 harness binaries is Python, so
`PYTHONPATH` is not a direct inbound channel for any of them this pass —
noted for the denylist as a low-priority "watch" item only, relevant if nox
ever spawns a Python-based MCP server as part of a harness's own tool use.

### 2. Codex sandbox — confirmed config surface, proof mechanism, and version churn

Confirmed directly against the **locally installed `codex-cli 0.144.1`**
(`--help`, primary/P-tier) and against
[developers.openai.com/codex/config-reference](https://developers.openai.com/codex/config-reference)
(fetched raw, primary):

- `sandbox_mode` values are exactly `read-only | workspace-write |
  danger-full-access` — verbatim: "sandbox_mode read-only | workspace-write
  | danger-full-access — Sandbox policy for filesystem and network access
  during command execution." `approval_policy` is a **separate** key
  (`untrusted | on-request | never | { granular = {...} }`) — a WebFetch
  summarization pass initially conflated the two keys' value sets; the
  direct grep against the raw doc corrected this. Treat AI-summarized
  fetches of this doc with suspicion; grep the raw text.
- `-s, --sandbox <SANDBOX_MODE>` **is** a flag on bare `codex exec`
  (confirmed, local `--help`) but is **not** a flag on `codex exec review`
  (confirmed, local `--help` — its option list runs `-c/-m/--uncommitted/
  --base/--enable/--commit/--disable/--strict-config/--title/-m/
  --dangerously-*/--skip-git-repo-check/--ephemeral/--ignore-user-config/
  --ignore-rules/--output-schema/--json/-o/-h`, no `-s`). Confirms
  `nox-security.md` Addendum 2's finding without a caveat: the review
  subcommand needs `-c sandbox_mode="read-only"`.
- **`codex exec review` has `--output-schema <FILE>`** — "Path to a JSON
  Schema file describing the model's final response shape" (local `--help`,
  primary) — directly relevant to the C-1018 severity-vocabulary question
  (§4): nox can hand Codex the same schema it expects Claude Code's
  `--json-schema` to emit against.
- **Proof of enforcement**: `codex exec --json` emits a JSONL event stream
  (`thread.started`, `turn.started`/`turn.completed`/`turn.failed`, `error`,
  and `item.*` events for `command_execution`/`file_change`/`mcp_tool_call`/
  etc. — [takopi.dev exec-json-cheatsheet](https://takopi.dev/reference/runners/codex/exec-json-cheatsheet/),
  secondary but directly corroborated by local `--help`'s `--json` flag
  description "Print events to stdout as JSONL"). **There is no distinct
  "sandbox-denied" event type** — a denied write surfaces only as a
  `command_execution` item whose `status` is `"failed"` with a nonzero
  `exit_code`, indistinguishable in the schema from an ordinary command
  failure. nox's own probe (not the review run) has to be the thing that
  interprets a failed-write attempt as "sandbox is enforced," because the
  harness's event schema doesn't hand you that distinction for free.

**Version churn — confirmed via `gh api repos/openai/codex/releases`
(primary, direct fetch, not a WebFetch summary):**

| Tag | Published | Relevant to nox |
|---|---|---|
| `rust-v0.144.1` | 2026-07-09 | Version the ADR's Addendum 2 was probed against |
| `rust-v0.147.0` | 2026-08-07 | Removed deprecated `codex exec --full-auto` (use `--sandbox workspace-write`); "Require explicit trust for unfamiliar local projects" |
| `rust-v0.148.0` | 2026-08-18 | **"Sandbox restrictions now fail closed for denied or unreadable paths across Linux and Windows"** — strictly strengthens the containment story |
| `rust-v0.149.0` | 2026-08-20 | "Documented DNS exfiltration risks and trust limitations for secure devcontainers" |
| `rust-v0.150.0` | 2026-08-26 | **"Untrusted projects no longer supply project-level `AGENTS.md` instructions"** — closes the exact gap nox-security.md Addendum 2 flagged: "`AGENTS.md`… is a prompt-injection surface… I found no flag to suppress it" |
| `rust-v0.152.1` | 2026-09-01 | Latest stable at research time |
| `rust-v0.153.0-alpha.6` | 2026-09-02 | Latest alpha at research time |

Eight stable releases and dozens of alphas landed in the ~55 days between
0.144.0 (2026-07-09) and this research (2026-09-02) — roughly one stable tag
every 5-7 days with alpha builds multiple times per day. This is a primary,
directly-observed cadence (not inferred), and it is the concrete evidence
behind this document's `Expires: 2026-11-30`: any Codex flag table, event
schema, or trust-gate description — including this one — needs re-probing
against the version actually installed at plan/execute time before nox's
`adapters/codex.py` ships against it.

### 3. Git-plumbing fixture test strategy

- **Building fixtures without a working tree of real files:**
  `git init -q` → `git commit-tree <tree> [-p <parent>] -m <msg>` for
  arbitrary history without checkout, or `git mktree`/`git update-index
  --add --cacheinfo <mode> <sha> <path>` to hand-place an index entry with
  a specific mode — `120000` (symlink) and `160000` (gitlink/submodule
  reference) both work via `--cacheinfo` **without a real symlink or
  submodule existing on disk**, which is exactly what a fixture testing
  "does nox's git wrapper correctly reject/handle a symlink or submodule
  entry in a hostile branch" needs (`git-update-index(1)`,
  [git-scm.com/docs/git-update-index](https://git-scm.com/docs/git-update-index)).
  `git worktree add --detach <path> <commit>` gives an isolated, non-branch
  checkout for tests that need actual files on disk.
- **Isolating from the operator's config** — the documented,
  purpose-built mechanism, verbatim (git-scm.com/docs/git-config §
  ENVIRONMENT, fetched directly):
  - `GIT_CONFIG_GLOBAL` / `GIT_CONFIG_SYSTEM` — "Take the configuration from
    the given files instead from global or system-level configuration."
    Point `GIT_CONFIG_GLOBAL` at `/dev/null` (or an empty tmp file) in the
    test subprocess env.
  - `GIT_CONFIG_NOSYSTEM=1` — "Whether to skip reading settings from the
    system-wide `$(prefix)/etc/gitconfig` file."
  - Prefer these over overriding `HOME`: `HOME` also relocates credential
    and identity lookups the test doesn't want to touch, where
    `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_NOSYSTEM` isolate exactly the config
    layer and nothing else.
  - `safe.directory` only matters if the fixture's UID differs from the
    checkout owner (CI containers, WSL `/mnt/c` mounts — this session's own
    environment is WSL2, so this is not hypothetical for this repo's CI).
    Set `safe.directory=*` **inside the fixture's own isolated
    `GIT_CONFIG_GLOBAL` file**, never in the developer's real global config.
- **Planting and then proving neutralization of a hostile hook/filter:**
  Use `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath
  GIT_CONFIG_VALUE_0=<tmp>/evil-hooks` (or the filter-driver equivalent,
  `filter.<name>.smudge`) as the *fixture setup's* own env to plant a hook
  that writes a marker file if it fires — GIT_CONFIG_COUNT/KEY/VALUE are
  documented, zero-indexed, and "missing key or value is treated as an
  error" (same source). Then invoke nox's actual git wrapper (which always
  passes `-c core.hooksPath=/dev/null` per the ADR's T3 mitigation) and
  assert the marker file is absent. Real-world motivation for testing this
  specific vector, not a hypothetical: CVE-2021-21300 is a documented
  remote-code-execution bug via a clean/smudge filter triggered on
  `git clone`/checkout on case-insensitive filesystems
  ([InfoQ summary](https://www.infoq.com/news/2021/03/git-clone-vulnerability/);
  fixed in git 2.30.2+).
- **Minimum Git version:** confirmed directly by diffing versioned docs
  pages (`curl` against `git-scm.com/docs/git-config/<version>`, not
  search-summarized): `GIT_CONFIG_NOSYSTEM` present since at least 2.30.0;
  `GIT_CONFIG_COUNT`/`KEY_<n>`/`VALUE_<n>` first present in the **2.31.0**
  docs (absent in 2.30.0); `GIT_CONFIG_GLOBAL` first present in the
  **2.32.0** docs (absent in 2.31.0). Recommend nox require and probe for
  **Git ≥ 2.32.0** (released June 2021) — the single version floor after
  which all three mechanisms this test strategy depends on are available,
  and well below any plausible real dev machine or CI image's actual git
  version.
- **No subprocess-equivalent of VCR exists** (already established in
  `nox-pattern-precedent.md` § 5 — not re-derived here): the closest
  packaged precedents are `pytest-subprocess` (patches at the `Popen`
  layer) and `testfixtures.popen`'s `MockPopen` (closer to nox's own
  `Runner`-seam DI shape); a hand-rolled fixture-repo approach as above
  remains the right fit for git-plumbing-level tests specifically, since
  those need a *real* git binary behaving correctly against a real (if
  minimal) repository, not a faked subprocess call.

### 4. Severity vocabulary — direct precedent, ground-truth fetched

Two independently-sourced, directly-fetched (not WebFetch-summarized)
precedents, both lowercase:

- **`codex-plugin-cc`'s own schema** — OpenAI's Claude-Code-side plugin for
  invoking Codex review, the exact tool nox's `hex-adversary` marker
  convention is modeling itself on. Fetched verbatim via
  `gh api repos/openai/codex-plugin-cc/contents/plugins/codex/schemas/review-output.schema.json`:
  ```json
  "severity": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
  "verdict":  { "type": "string", "enum": ["approve", "needs-attention"] }
  ```
  ([github.com/openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc),
  path `plugins/codex/schemas/review-output.schema.json`).
- **SARIF's `level`** — `error | warning | note | none`, lowercase, the
  format GitHub code scanning consumes; practitioner mapping convention is
  critical/high → `error`, medium → `warning`, low/info → `note`
  ([docs.github.com, SARIF support for code scanning](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning)).
- **Codex's own structured-output surface exists for this exact purpose**:
  `codex exec review --output-schema <FILE>` (confirmed local `--help`,
  §2 above) and Claude Code's `claude -p --output-format json --json-schema
  <FILE>` (confirmed local `--help`: `--json-schema <schema> JSON Schema
  for structured output validation`) are both real, both already installed
  and already probed in this session — nox can hand both harnesses the
  *same* schema file with a lowercase `severity` enum and get schema-
  validated compliance from each, rather than parsing free text from either.
- **OpenCode has no equivalent** — confirmed as a negative finding in
  `nox-tech-tooling.md` (already probed live against `opencode 1.18.22`):
  `--format json` is a raw event stream, not a schema-constrained final
  blob, and no `--output-schema`/`--json-schema`-equivalent flag exists.
  OpenCode's findings will need to be parsed from prose or the event stream
  rather than schema-validated at the source.

**Recommendation for C-1018:** the wire value is lowercase; the consumer
(hex) title-cases for display. Cite both `codex-plugin-cc`'s schema and
SARIF's `level` in C-1018's rationale — this is not an arbitrary pick, it is
the convention both the vendor whose plugin nox extends and the industry
interchange format already settled on.

### 5. arXiv:2607.21656 — exact identifiers for the C-1020 warning

Fetched the paper's HTML directly (`arxiv.org/html/2607.21656v1`, primary,
not summarized) and grepped its raw text rather than trusting a WebFetch
paraphrase, given `discuss-nox-priorart.md` already documents one retracted
figure from this same failure mode (a WebSearch auto-summary inventing a
citation that doesn't exist in its source). This figure is **not** a repeat
of that failure — the identifiers below are quoted directly from the
paper's own text:

> "The runs used **claude-opus-4-7** through **Claude Code 2.1.50** and
> **gpt-5.5** through **Codex CLI**. Both runs set `reasoning.effort = high`."
> (§3.3, Execution and Cost Accounting)

> "Claude Opus 4.7 review raises Codex GPT-5.5 drafts from 71.6% to 89.7%
> ($p_{BH}=.001$)… Codex GPT-5.5 reviewing Claude Opus 4.7 drafts drops the
> pass rate from 91.4% to 82.8% ($p_{BH}=.046$)." (Abstract)

> "…because coding agents change quickly we pin model identifiers, CLI
> versions, and execution dates, though future releases may shift the
> numbers in either direction." (§5.5, Scope, Limitations, and
> Reproducibility — explicit acknowledgment that this is a point-in-time
> result, not a durable ranking)

**Implication for C-1020's warning condition:** the negative pairing is
*model* `gpt-5.5`(-family) reviewing *model* `claude-opus-4-7`(-family), not
*harness* Codex reviewing *harness* Claude Code. The paper's own title
("Claude to review Codex or vice versa") conflates model and harness, but
its methodology doesn't — and the ADR's own reasoning for treating this as
informational rather than gating already makes the identical point about
OpenCode's BYOK leg. Keying the warning on `Review.model` (already planned)
rather than on harness identity is therefore not just more precise, it's
required for the warning to still mean anything once either vendor ships a
model past this pinned pair — which, per Finding 2's version-churn evidence,
should be expected on a timescale of weeks, not months. Publication status
unchanged from prior research: accepted at Agentic SE @ KDD'26, unreplicated,
116 tasks — treat as the strongest available signal, not a settled ranking.

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| [arxiv.org/abs/2607.21656](https://arxiv.org/abs/2607.21656) | Paper (abstract) | 2026-07-22 | Headline asymmetric result |
| [arxiv.org/html/2607.21656v1](https://arxiv.org/html/2607.21656v1) | Paper (fetched raw, grepped directly) | 2026-07-22 | Exact model identifiers, limitations §5.5 |
| [code.claude.com/docs/en/env-vars](https://code.claude.com/docs/en/env-vars) | Docs (fetched raw, grepped) | current | Full Claude Code env var reference; confirmed absence of `XDG_*`/`NODE_OPTIONS`/`SSL_CERT_FILE` |
| [code.claude.com/docs/en/settings](https://code.claude.com/docs/en/settings) | Docs | current | Settings precedence; `CLAUDE_CONFIG_DIR` pointer; XDG git-excludes fallback |
| [developers.openai.com/codex/config-reference](https://developers.openai.com/codex/config-reference) | Docs (fetched raw, grepped) | current | `sandbox_mode`/`approval_policy` exact enum values |
| Local `codex --help` / `codex exec --help` / `codex exec review --help` | CLI (P, primary) | 2026-09-02, v0.144.1 | `-s/--sandbox` present on `exec`, absent on `exec review`; `--output-schema`, `--json` |
| `gh api repos/openai/codex/releases` | Repo API (P, primary) | 2026-09-02 | Version churn 0.144.0→0.153.0-alpha.6; sandbox fail-closed (0.148.0); `AGENTS.md` untrusted-project fix (0.150.0) |
| [takopi.dev exec-json-cheatsheet](https://takopi.dev/reference/runners/codex/exec-json-cheatsheet/) | Third-party reference | current | `--json` event-type taxonomy |
| `gh api repos/openai/codex-plugin-cc/contents/plugins/codex/schemas/review-output.schema.json` | Repo (P, primary, fetched raw) | current | `severity`/`verdict` enum ground truth |
| [git-scm.com/docs/git-config](https://git-scm.com/docs/git-config) (+ `/2.30.0`, `/2.31.0`, `/2.32.0`) | Docs (P, primary, version-diffed) | current + version-pinned | `GIT_CONFIG_GLOBAL`/`NOSYSTEM`/`COUNT`/`KEY`/`VALUE` definitions and introduction versions |
| [git-scm.com/docs/git-update-index](https://git-scm.com/docs/git-update-index) | Docs | current | `--cacheinfo` for mode 120000/160000 without real files |
| [InfoQ, Git clone vulnerability](https://www.infoq.com/news/2021/03/git-clone-vulnerability/) | News/analysis | 2021-03 | CVE-2021-21300, real-world smudge-filter RCE motivating the neutralization test |
| [opencode.ai/docs/config/](https://opencode.ai/docs/config/) | Docs (fetched raw, grepped) | current | `OPENCODE_CONFIG`/`OPENCODE_CONFIG_CONTENT` verbatim precedence chain |
| [mintlify.wiki/opencode-ai/opencode/reference/environment-variables](https://mintlify.wiki/opencode-ai/opencode/reference/environment-variables) | Docs mirror | current | OpenCode BYOK provider env var list |
| [.agents/research/nox-tech-tooling.md](nox-tech-tooling.md) (internal) | Internal research | 2026-08-31 | OpenCode live-probed surface; `OPENCODE_AUTH_JSON`/`OPENCODE_<PROVIDER>_APIKEY`; no schema flag |
| [.agents/research/nox-security.md](nox-security.md) (internal, incl. Addendum 2) | Internal research | 2026-08-31 | Baseline env allowlist table; Codex 0.144.1 trust/hook/sandbox analysis |
| [.agents/research/nox-pattern-precedent.md](nox-pattern-precedent.md) § 5 (internal) | Internal research | 2026-08-31 | Subprocess-test precedent (no VCR-equivalent) — not re-derived here |
| [nodejs.org/api/cli.html#node_optionsoptions](https://nodejs.org/api/cli.html#node_optionsoptions) | Docs (primary) | current | `NODE_OPTIONS`/`--require` code-injection primitive |
| [docs.github.com, SARIF support for code scanning](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning) | Docs (primary) | current | `level: error\|warning\|note\|none` precedent |
| [systemshardening.com, Linux Shared Library Security](https://www.systemshardening.com/articles/linux/linux-shared-library-security/) | Article | current | `LD_PRELOAD` hijacking mechanism |

## Recommendation

Ship all five as stated in Direct Answer. None of this reopens a settled ADR
decision — it fills in the four items the ADR explicitly deferred, plus
corrects one internal-research gap (Codex's `AGENTS.md` prompt-injection
surface, flagged open in `nox-security.md` Addendum 2, is closed as of
Codex 0.150.0) and sharpens one (C-1020 must key on `Review.model`, not
harness identity, given the paper's own identifiers are model-pinned).
