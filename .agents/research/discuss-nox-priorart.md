# Research: Cross-Harness Adversarial Review — Prior Art

## Metadata

- Date: 2026-08-31
- Lane: prior-art web scan (hex `researcher` worker)
- Question: What is the current state of the art for making one AI coding harness invoke a *different* AI coding harness as an adversarial reviewer, and what are the concrete mechanics and known failure modes?
- Sources: see inline citations below (GitHub repos fetched via `gh api`, arXiv papers, vendor docs, GitHub issues)

## 1. `openai/codex-plugin-cc` — precise architecture

Repo: https://github.com/openai/codex-plugin-cc (Apache-2.0, 32.6k stars, 2266 forks, last push 2026-07-08, checked 2026-08-31). Description: "Use Codex from Claude Code to review code or delegate tasks." It ships as a **Claude Code plugin** (`.claude-plugin/plugin.json`, commands, hooks, an agent, skills) — not an MCP server and not a generic bridge. Everything is Node.js (`.mjs`, requires Node 18.18+).

**Mechanics** (from `plugins/codex/scripts/lib/app-server.mjs`, `codex.mjs`, `git.mjs`):
- It does **not** shell out to `codex exec`. It speaks Codex's **app-server JSON-RPC protocol** over stdio (`spawn("codex", ["app-server"])`, newline-delimited JSON messages) or, for repeated calls, over a persistent **broker**: a detached background process (`broker-lifecycle.mjs`) reachable over a Unix socket, avoiding cold-start on every review. `CodexAppServerClient.connect()` picks broker-if-available, else spawns direct.
- Review invocation is a dedicated RPC method, `review/start`, with a `target` object — this is a first-class "review" primitive in the Codex app-server protocol, distinct from a plain chat turn.
- **Diff/context passing** (`git.mjs`): `resolveReviewTarget()` computes scope (`auto`/`working-tree`/`branch`, or explicit `--base <ref>`) via `git diff --shortstat`/`--name-only`. `collectReviewContext()` then decides `inputMode`: **`inline-diff`** (the diff text, `--binary --no-ext-diff --submodule=diff`, is embedded directly) when file count and byte size are under thresholds (`maxInlineFiles`, `maxInlineDiffBytes`), else **`self-collect`** — Codex is handed only a lightweight summary and told: *"Inspect the target diff yourself with read-only git commands before finalizing findings."* So large diffs are not force-fed; Codex re-derives them via its own sandboxed shell access.
- **Findings return** as structured JSON conforming to `schemas/review-output.schema.json`: `{verdict: approve|needs-attention, summary, findings[{severity, title, body, file, line_start, line_end, confidence, recommendation}], next_steps[]}`. The review text is captured off Codex's `exitedReviewMode` lifecycle notification (`item.review`) inside the app-server event stream.
- Commands: `/codex:review` (read-only, non-steerable), `/codex:adversarial-review` (steerable — "questions the chosen implementation and design... pressure-test assumptions, tradeoffs, failure modes"), `/codex:rescue` (delegates a fix/investigation to Codex, not read-only), `/codex:transfer` (hands a live Claude Code session to Codex via its **external-agent session importer** — genuine cross-harness context transfer, not just a prompt), `/codex:status`/`/result`/`/cancel` for background job control.
- **Optional Stop-hook review gate**: `hooks.json` wires a `Stop` hook (900s timeout) to `stop-review-gate-hook.mjs`, which runs a targeted Codex review of Claude's just-produced response and **blocks the stop** (forces Claude to keep working) if Codex's verdict is `needs-attention`. The README explicitly warns: *"The review gate can create a long-running Claude/Codex loop and may drain usage limits quickly."*
- **Explicitly does not**: run its own model — it reuses the caller's local `codex` binary, local auth state (`codex login`), and local `.codex/config.toml`/`~/.codex/config.toml` (project-level config only loads if the project is Codex-trusted). No separate account or runtime.
- Auth/readiness check is a dedicated command, `/codex:setup`, which checks install + login state and can offer `npm install -g @openai/codex` — i.e., cross-harness readiness detection is its own explicit step, not inferred from a failed run.

This is the closest thing to a reference implementation for the coordinator's own use case, and — relevant to this session — `arcana`'s own environment already has this plugin's commands (`codex:rescue`, `codex:setup`, `codex:codex-cli-runtime`, `codex:codex-result-handling`, `codex:gpt-5-4-prompting`) installed as skills.

## 2. Headless invocation contracts (as of 2026-08-31)

**Claude Code CLI** (https://code.claude.com/docs/en/headless, fetched 2026-08-31):
- One-shot: `claude -p "<prompt>"` (aka `--print`). `--bare` skips hook/skill/MCP/CLAUDE.md auto-discovery for reproducible CI runs and requires `ANTHROPIC_API_KEY` (bare mode never reads OAuth/keychain).
- Machine-readable: `--output-format text|json|stream-json`. `json` returns `result`, `session_id`, `total_cost_usd` (+ per-model cost breakdown, client-side estimate); pair with `--json-schema '<JSON Schema>'` to get a `structured_output` field validated against a caller-supplied schema.
- Permissions: `--allowedTools`/`--disallowedTools` (permission-rule syntax, e.g. `Bash(git diff *)`), `--permission-mode auto|dontAsk|acceptEdits` (default starting mode for `-p` is **Manual** on every plan — must be overridden explicitly for unattended runs).
- Model: `/model <name>` works as a `-p`-mode slash command (requires v2.1.205+); no dedicated `--model` flag surfaced in this fetch.
- Not-authenticated detection: no pre-flight flag — "when a failure happens inside the run, such as missing authentication, Claude Code prints the failure as the result on stdout" and exits non-zero (0 = success, non-zero = failure; SIGTERM → exit 143).
- Session resumption: `--continue` (most recent), `--resume <session_id>` (specific; findable across directories on the same machine since v2.1.223).

**Codex CLI** (`codex exec`; per gist/blog cross-checks, not independently re-verified against primary OpenAI docs in this pass — flag as secondary-sourced):
- One-shot/non-interactive by construction: "codex exec runs non-interactively, so it takes no approval flag."
- Sandbox: `--sandbox read-only` (default), `workspace-write`, `danger-full-access`. `--full-auto` is **deprecated and, as of v0.147.0, removed** — scripts still passing it now error.
- Machine-readable: `--json` → JSONL event stream on stdout.
- Config isolation for CI: `--ignore-user-config`, `--ignore-rules`.
- (Confirmed independently via `codex-plugin-cc`): the **app-server** JSON-RPC protocol (`codex app-server`) is the structured alternative to `codex exec` for programmatic embedding, with a dedicated `review/start` method — this is the layer real cross-harness integrations use, not the plain-text `exec` CLI.

**GitHub Copilot CLI** (https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference, fetched 2026-08-31):
- One-shot: `-p PROMPT` / `--prompt`. Quiet output: `-s` ("outputting only the agent's response... for piping").
- Tool/path permissions: `--allow-all-tools`, `--allow-tool=TOOL` (supports scoped forms like `shell(dotnet test)`), `--deny-tool=TOOL` (deny wins over allow), `--allow-all-paths`, `--add-dir=DIRECTORY`.
- Model: `--model=MODEL` (e.g. `gpt-5.2`, `claude-sonnet-4.6`) or `COPILOT_MODEL` env var.
- Auth: env vars `COPILOT_GITHUB_TOKEN`/`GH_TOKEN`/`GITHUB_TOKEN`. **Not verified**: no documented exit-code table or explicit "not authenticated" pre-check surfaced in this doc page — flagged as unconfirmed rather than guessed.

**Cursor CLI** (`cursor-agent`; https://cursor.com/docs/cli/reference/output-format, https://cursor.com/docs/cli/headless — titles cross-checked via search, not independently WebFetched in this pass):
- Headless via `--print`/`-p`, inferred automatically also when stdout is non-TTY or stdin is piped.
- `--output-format text|json|stream-json` (default `text`); `stream-json` emits typed events (`system`, `assistant`, `tool_call` with started/completed subtype, final `result` with duration); `--stream-partial-output` adds char-level deltas.
- Model selection and exact permission-flag surface **not independently confirmed** in this pass — worth a follow-up fetch of the primary Cursor docs before relying on exact flag names.

## 3. Cross-vendor plumbing that already exists

- **`coder/agentapi`** (https://github.com/coder/agentapi, MIT, ~1.5k stars, active). Go HTTP server that drives Claude Code, Codex, Copilot, Cursor CLI, Gemini, Amp, Aider, Goose, OpenCode, AmazonQ, Auggie through an **in-memory terminal emulator** — it types into each CLI's interactive TUI and screen-scrapes/diffs terminal output into structured messages, rather than using each tool's native headless/JSON contract. This is architecturally the opposite approach from `codex-plugin-cc`'s protocol-level integration: broader coverage, but brittle to any TUI redraw change ("logic for removing extra bits may need to be updated" if an agent's UI changes). No documented guidance on running several of its wrapped agents concurrently against the same repo.
- **MCP-ecosystem multi-agent-review servers** (surfaced by search, not independently source-verified — treat as leads): `religa/multi_mcp` ("Multi-Model chat, code review and analysis MCP Server for Claude Code"), an `agent-link-mcp` described as enabling "spawning and communication with any AI coding agent CLI," and assorted "AI Council" style MCP servers that query several CLI agents in parallel and reconcile verdicts. None of these were fetched directly; maturity/license unverified.
- **`bradAGI/awesome-cli-coding-agents`** — a curated directory (not a tool) cataloguing the harness landscape (Pi, OpenCode, Aider, Goose, platform agents, parallel runners); useful as an index for further scans, not evidence itself.

## 4. Reported failure modes

- **Headless auth/token expiry**: [anthropics/claude-code#47754](https://github.com/anthropics/claude-code/issues/47754) (opened ~2026-04, still open at fetch time) — Claude Code's OAuth refresh (`POST https://platform.claude.com/v1/oauth/token`) gets HTTP 403 from Cloudflare's WAF (bot-traffic classification) or 429 (rate limit) when the refresh originates from a headless Linux server with no browser context; access tokens expire ~1 hour; no `--no-browser`/stdin auth-code flow exists; reporter was locked out of a headless Pro-subscription box for 26+ days with no working recovery short of a browser-capable re-auth. This is a concrete, citable instance of the "headless auth" failure class the task asked about.
- **Rate limits under concurrency**: practitioner guidance (developersdigest.tech, amux.io, cross-checked 2026-08) converges on "1–3 agents steady is fine, 5+ agents overnight hits rate limits within hours," and multiple headless agents sharing one subscription share its weekly cap — recommendation is to switch to metered API-key billing for sustained parallel/multi-agent use.
- **Sandbox/approval semantics churn**: Codex CLI's `--full-auto` flag was deprecated then hard-removed in v0.147.0 (scripts using it now error rather than degrade) — direct evidence of output/flag-surface breakage between versions that a cross-harness bridge must track.
- **Concurrent agents on one working tree**: no vendor documents a supported story for this; `agentapi`'s docs are silent on it; the `codex-plugin-cc` broker design (one persistent app-server process per repo, referenced by a state file under a resolved state dir) implies the authors anticipated repeat/concurrent calls from Claude Code but there's no explicit multi-writer-safety guarantee documented for concurrent git-state review vs. edit.
- **Non-deterministic/evolving exit codes and output formats**: Claude Code's own docs list several dated behavior changes within 2026 (background-task grace period added v2.1.163, stream-drain wait capped v2.1.214 vs previously ~2s, capabilities array requires v2.1.205+, nested-subagent stream forwarding requires v2.1.211/v2.1.219) — the headless contract has been actively revised release-to-release, which is a real integration-maintenance burden for anything hard-coding today's flags.
- **Cost/latency**: not independently quantified in this pass beyond the qualitative "5+ agents overnight" rate-limit note and the review-gate README's own warning that Claude/Codex Stop-hook loops "may drain usage limits quickly."

## 5. Evidence on whether cross-model review finds different defects

- **"Cross-Model LLM Code Review: Should you use Claude to review Codex or vice versa?"**, Xiang/Zhang/Zhang/Xu, submitted 2026-07-22, https://arxiv.org/abs/2607.21656. 116 coding tasks, six write/review conditions with Claude and Codex. Findings are **directional, not symmetric**: Claude reviewing Codex raised Codex's pass rate 71.6% → 89.7% (p=.001); Codex self-review raised it to 84.5% (p=.022); **Codex reviewing Claude lowered Claude's pass rate 91.4% → 82.8% (p=.046)** — i.e. cross-model review made results *worse* in that direction; Claude self-review left its 91.4% baseline unchanged. Their conclusion: "use Claude to review Codex, not the other way around." This directly contradicts a simplistic "cross-model review is strictly better" claim — the benefit is pairing-specific and can be net-negative.
- **"Bias in the Loop: Auditing LLM-as-a-Judge for Software Engineering"**, Zhao/Esmaeili/Fard, submitted 2026-04-18, https://arxiv.org/abs/2604.16790. Reports LLM-judge decisions in SE tasks (code generation, repair, test generation) are "highly sensitive to prompt biases even when the underlying code snippet is unchanged," with prompt-bias direction shifting accuracy and, when misaligned, "substantially" reducing it — enough to flip relative model rankings. Caution against reading any single cross-model review run as a stable, reproducible signal.
- **"Reliability without Validity"**, https://arxiv.org/html/2606.19544v1 (surfaced by search, not independently fetched — leads only): reports LLM-judge agreement/consistency/bias at scale; and a practitioner note surfaced alongside it claims strict agreement between Claude Opus and "GPT Codex 5.3-xhigh" averaged only ~18% (partial ~39%) across Java/Go/HCL — **this specific figure came from WebSearch's auto-summary, not a source I fetched directly; treat as unverified** until the primary paper is pulled.

## negative

- Could not independently WebFetch the primary Cursor CLI docs pages (`cursor.com/docs/cli/headless`, `.../reference/output-format`) in this pass — Cursor's exact permission-flag names and model-selection flag are sourced only from WebSearch's summarization, not primary text. Flag before relying on exact flag spelling.
- Codex CLI's `codex exec` flag details (sandbox flags, `--json`, `--ignore-user-config`) are sourced from a third-party gist/blog cross-check, not OpenAI's own `developers.openai.com/codex/cli` reference — the app-server protocol details (confirmed via `codex-plugin-cc` source) are solid, but the plain `exec` CLI surface should be re-verified against primary docs before being treated as authoritative.
- GitHub Copilot CLI: no documented exit-code table or explicit pre-flight "not authenticated" check found in the fetched programmatic-reference page — this may simply be undocumented rather than absent; not confirmed either way.
- The MCP-ecosystem "multi-agent review" servers (`multi_mcp`, `agent-link-mcp`, "AI Council") are search-surfaced names only — none fetched, so maturity/license/actual approach are unverified and could be low-quality or abandoned projects.
- The 2607.21656 result should not be over-generalized: it is two models (Claude/Codex), 116 tasks, one paper, submitted 2026-07-22 (five weeks old at time of writing) — not yet a body of replicated evidence. Its central finding (asymmetric, sometimes-negative cross-review) is nonetheless the most concrete quantified counter-evidence found against "cross-model review is strictly additive."

## leads

- Primary OpenAI Codex CLI docs (`developers.openai.com/codex/cli/reference`, `developers.openai.com/codex/app-server`) — re-verify `codex exec` flag surface and get the authoritative app-server protocol spec (method list beyond `review/start`) directly rather than via the plugin's usage of it.
- Primary Cursor CLI docs — confirm exact permission/model flags before any implementation depends on them.
- ~~`arxiv.org/html/2606.19544v1` ("Reliability without Validity") — fetch directly to confirm or retract the ~18%/~39% Claude-vs-Codex agreement figure currently only sourced from a search summary.~~ **RETRACTED 2026-09-02** (hex-architect adr_0011 Review, SOTA gap check, paper fetched directly): the paper evaluates 21 LLM-judges across MT-Bench/JudgeBench/RewardBench and contains no mention of Claude, Codex, code review, or any 18%/39% figure. The figure does not exist in the cited source. Do not cite.
- `religa/multi_mcp` and `coder/agentapi`'s issue tracker — worth a look for concrete concurrent-multi-agent-on-one-repo failure reports, since no vendor documents this and it's directly relevant if the coordinator's own design runs two harnesses against the same working tree simultaneously.
