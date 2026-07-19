# Research: harness capability landscape (mid-2026)

**Axis:** technology/tooling (gate-selected, user pick)
**Date:** 2026-07-19
**Decision it informs:** adr_0001_model_matrix_capability_classes — hex model-matrix
capability-class vocabulary, orchestrator-class model handling, harness-capability
representation, split between hex runtime instantiation and grimoire #26
install-time templating.
**Produced by:** hex-architect medium run, researcher worker (fast-balanced).

## Direct answer

Both concerns are real and current. Anthropic created a model tier
("Mythos-class": Fable 5 / Mythos 5, announced 2026-06-09) that sits above Opus
and is positioned as an orchestrator seat, not a fungible "strongest" leaf
worker — Claude Code's subagent `model` field lists `fable` as a distinct alias
alongside `opus`/`sonnet`/`haiku`, so the harness itself treats it as a routing
target. Separately, Claude Code shipped programmatic orchestration (`Workflow`
tool / "ultracode", research preview since ~2026-05) with no analogue in the
other three harnesses' core docs — Copilot and OpenCode expose only
conversational subagent delegation; Codex's equivalent ("Ultra mode" + Agents
SDK) is SDK/community-level, not a first-class scripted runtime with
checkpointing. Both axes are weeks-to-months old and still being renamed release
to release — good candidates for capability booleans, bad candidates for
hardcoding into a two-class `fast-balanced`/`strongest` grid.

## Trends

- **Established (12+ months, stable API shape):** per-spawn model override on
  subagents (Claude, Codex, OpenCode); subagent tool/permission scoping;
  background/async task execution as a first-class harness feature.
- **Trending (converging, last ~6 months):** cloud-hosted long-running
  background agents (Claude Code background subagents, Codex cloud tasks up to
  25h, Copilot cloud coding agent via Actions runner).
- **Emerging (≤1 vendor, or informal only):** vendor-declared orchestrator-class
  model tier (Anthropic only, formal); scripted multi-agent orchestration with
  checkpointing (Claude Workflow tool only — Codex community has an informal
  Sol/Luna orchestrator-executor prompting pattern, not a vendor primitive);
  nested subagents spawning subagents (Claude Code explicit, 5-level cap since
  v2.1.172; unconfirmed elsewhere).
- **Declining:** Gemini as first-class Copilot model option (dropped from
  Copilot Chat web 2026-05-20) — vendor×model rosters churn faster than
  capability booleans.

## Capability table

| Vendor | Nested subagent spawn | Per-spawn model override | Programmatic orchestration (ultracode-like) | Background/async execution | Orchestrator-class model tier |
|---|---|---|---|---|---|
| **Claude Code** | Yes — 5 levels (v2.1.172+) | Yes — `model`: `haiku`/`sonnet`/`opus`/`fable`/`inherit`/full ID | Yes — `Workflow` tool, JS script, 1,000 agents/run, resumable | Yes — background-by-default since v2.1.198 | Yes — Mythos-class, explicitly above Opus |
| **OpenAI Codex** | Unclear beyond one level | Yes — agent files set `model` + `model_reasoning_effort` | Partial — "Ultra mode" fan-out + Agents SDK; no scripted/checkpointed runtime | Yes — cloud tasks up to 25h; local worktree parallelism | No formal tier — community Sol/Luna convention only |
| **GitHub Copilot** | Partial — Fleet mode, depth undocumented | **No** — docs explicit: all agents share session model | Partial — Fleet mode SDK binding, marked experimental | Yes — cloud coding agent + local background tasks | No — per-task-kickoff model pick only |
| **OpenCode** | Unclear — Task tool role subagents; recursive nesting unconfirmed | Yes — `model: provider/model-id` per agent frontmatter; inherits if unset | Partial — conversational Task delegation in core; scripted orchestrators are community add-ons | Unconfirmed in docs reviewed | No — vendor-neutral, inherits provider tiers |

**Churn:** per-spawn model override, background execution — stable. Nested
spawn — stable as boolean, volatile in depth detail. Programmatic orchestration,
orchestrator-class tier — volatile (single-vendor, renamed within own lifetime:
`workflow` keyword → `ultracode` in v2.1.160; Mythos-class ~6 weeks old).

## Key findings

- Claude Workflow tool moves orchestration out of conversation into a JS script
  with agent-count guidance, 16-concurrent/1,000-total caps, resumability — a
  materially different primitive from turn-by-turn delegation.
  https://code.claude.com/docs/en/workflows
- `AgentDefinition.model` alias list (`fable`, …) is concrete evidence Anthropic
  treats orchestrator-class as a distinct routing target — the exact ambiguity
  in the `strongest` naming, already resolved in the harness schema.
  https://code.claude.com/docs/en/agent-sdk/subagents
- Fable 5 is "a Mythos-class model made safe for general use", with safety
  classifiers that fall back to Opus 4.8 on certain requests — the
  orchestrator-tier model can silently downgrade mid-session; a naive boolean
  hides this. https://www.anthropic.com/news/claude-fable-5-mythos-5
- Copilot docs explicitly state no per-agent model override in a session — a
  verified capability gap, not just undocumented.
  https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/custom-agents
- MCP initialize handshake (each side declares features; effective set =
  intersection) is working precedent for boolean-capability-matrix +
  conditional behavior — the pattern grimoire #26 wants, at protocol level.
  https://modelcontextprotocol.info/specification/draft/basic/versioning/
- AGENTS.md (60k+ projects, Linux Foundation Agentic AI Foundation) is
  context-sharing, not capability-declaration — no "caniuse for harnesses"
  exists; grimoire's capability matrix fills a real gap.
  https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation

## Sources

- https://code.claude.com/docs/en/workflows — Workflow tool mechanics, limits, resumability
- https://code.claude.com/docs/en/agent-sdk/subagents — AgentDefinition schema, model aliases, nesting, background default
- https://www.anthropic.com/news/claude-fable-5-mythos-5 — Mythos-class tier, Fable/Mythos distinction, Opus fallback
- https://learn.chatgpt.com/docs/agent-configuration/subagents — Codex subagent model/effort override, async execution
- https://openai.com/index/introducing-gpt-5-3-codex/ — Codex model framing, no formal orchestrator tier
- https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/custom-agents — Copilot custom agents, no per-agent model override
- https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/fleet-mode — Fleet mode, experimental SDK binding
- https://opencode.ai/docs/agents/ — OpenCode agent frontmatter, model inheritance
- https://modelcontextprotocol.info/specification/draft/basic/versioning/ — capability negotiation precedent
- https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation — AGENTS.md governance
- https://github.blog/changelog/2026-04-14-model-selection-for-claude-and-codex-agents-on-github-com/ — Copilot per-task model picker
- https://www.digitalapplied.com/blog/github-copilot-drops-gemini-model-shakeup-may-2026 — model-roster churn example

## Recommendation

Five capability axes. Bake three install-time (stable): `subagent_spawn`,
`per_spawn_model_override` (false for Copilot — verified absent),
`background_execution`. Keep two runtime-detected or policy-flagged (volatile):
`programmatic_orchestration` (gate behind runtime check / version floor, not a
shipped boolean), `orchestrator_tier_model` (durable as a boolean, but which
model fills it churns; comes with the silent-fallback wrinkle). Do not make
`strongest` do double duty: keep it meaning best single-model worker quality;
handle "don't spawn this as a leaf" via a separate orchestrator concept
(present only where `orchestrator_tier_model` is true, else falls back) —
matches grim's Vendor-trait-keyed boolean design in #26.
