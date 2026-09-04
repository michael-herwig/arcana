# Research: Multi-model / second-opinion code review — competitive & vendor landscape

## Metadata
- Date: 2026-08-31
- Lane: competitive/vendor (hex-discuss researcher worker)
- Question: How do comparable AI coding products handle multi-model or second-opinion code review, and what do they deliberately refuse to do?
- Sources: inline per finding (WebSearch/WebFetch, dated)

## Findings by product

### Cursor
- **BugBot** (separate paid product, $40/user/mo) auto-reviews PRs; 8 parallel passes with randomized diff ordering; June 2026 update cut review time ~5min→~90s, +10% bugs found, -22% cost/run. Autofix (Feb 2026) spawns cloud VM agents to fix flagged issues (~35% of Autofix changes get merged). — [Digital Applied, Jun 2026](https://www.digitalapplied.com/blog/cursor-bugbot-90-second-reviews-june-2026-release)
- **Cross-vendor routing**: not evidenced as user-facing "pick a different vendor's model for review" — BugBot/Agent Review are Cursor-operated services; model choice is Cursor's, not exposed as a second-opinion toggle across vendors in what we found.
- **Isolation**: Cloud/Background Agents run in per-task VMs (own filesystem/terminal/package manager); env defined via Dockerfile/`​.cursor/environment.json` or saved snapshots; snapshots capture full disk state + harness/model/API-key config; layer-cached Docker builds ~70% faster on cache hit. — [Cursor Docs, 2026](https://cursor.com/docs/cloud-agent); [Digital Applied](https://www.digitalapplied.com/blog/cursor-cloud-agents-isolated-vms-guide)
- **ToS-relevant**: subscriptions sold only via cursor.com, no resellers; enterprise seat reassignment allowed under True-Up terms. Anthropic's Jan 9 2026 OAuth-spoofing crackdown named "Cursor IDE (in certain configurations)" as disrupted — i.e., Cursor's use of Claude subscription auth was affected by Anthropic-side enforcement, not a Cursor-authored restriction. — [VentureBeat, Jan 9 2026](https://venturebeat.com/technology/anthropic-cracks-down-on-unauthorized-claude-usage-by-third-party-harnesses)

### GitHub Copilot
- Model picker spans Claude (Opus/Sonnet/Haiku), GPT-5.x, Gemini 3.x, and Microsoft's own MAI-Code-1-Flash — genuine cross-vendor choice, but picked by the user/org per task, not auto-triggered as a "second opinion" pass. — [DevLeader, Mar 2026](https://www.devleader.ca/2026/03/29/multimodel-support-in-github-copilot-sdk-gpt5-vs-claude-in-c)
- **Code review**: static-analysis only (no execution/tests); posts inline PR comments as a standard GitHub review; devs can reply/dismiss/apply. Business seat gets it with no extra install. — search synthesis, 2026
- **Isolation**: Coding agent runs each session in an isolated, ephemeral GitHub Actions container, destroyed after completion; can only push to `copilot/*` branches; default firewall blocks egress unless allow-listed; self-hosted ARC runners supported for private infra (public preview). — [GitHub Changelog, Jun 2 2026](https://github.blog/changelog/2026-06-02-cloud-and-local-sandboxes-for-github-copilot-now-in-public-preview/); [GitHub Docs](https://docs.github.com/copilot/concepts/agents/coding-agent/about-coding-agent)
- **ToS**: GitHub prohibits "excessive or automated usage" / bulk-scripted Copilot calls under its Acceptable Use Policy — abuse detection can suspend access; exact automation ceiling not published in numeric terms (negative below).

### Amp (Sourcegraph → Amp Frontier Corp, spun out Dec 2025)
- **Cross-vendor by design**: "Smart" mode = Claude Opus 4.8; "Deep"/"Rush" = GPT-5.5 variants; **Oracle** sub-agent explicitly routes to a GPT reasoning model (reported as GPT-5/o3-class) for planning/review even when the main thread is on Claude — this is the clearest same-product, cross-vendor second-opinion mechanism found in this lane. — [DeepWiki, 2026](https://deepwiki.com/x1xhlol/system-prompts-and-models-of-ai-tools/5.3-amp-by-sourcegraph); [Siddharth Bharath guide, 2026](https://www.siddharthbharath.com/amp-code-guide/)
- **Mechanism**: subagent launch within Amp's own orchestrator (not MCP, not shelling out to a rival CLI) — Amp holds API keys / provider access itself and multiplexes at the API layer.
- **Review subagents**: Amp can launch one subagent per check, combining independently-useful outputs — parallel review pattern, single vendor-controlled harness.

### Aider
- **Architect/Editor two-model workflow** (Sep 2024 feature, still current): reasoning model ("architect") proposes a solution, a second "editor" model turns it into concrete edits — can freely mix vendors (e.g., o1 architect + Sonnet editor) since Aider is BYOK/LiteLLM-backed. SOTA benchmark combo cited: o1-preview architect + DeepSeek/o1-mini editor → 85% on Aider's edit benchmark. — [Aider docs](https://aider.chat/docs/usage/modes.html); [Aider blog, Sep 2024](https://aider.chat/2024/09/26/architect.html)
- This is design-time role-splitting, not a dedicated "review my diff with model B" reviewer, but functionally is the most explicit deliberate cross-vendor pairing in the survey.

### Cline / Roo Code
- Both are BYOK/model-agnostic (Anthropic, OpenAI, Gemini, local/Ollama) — no restriction to one vendor. Roo's "Boomerang Tasks" enable multi-mode (Code/Architect/Ask/Debug) sub-agent orchestration; docs describe general "model orchestration" patterns. — [Cline docs, Model Orchestration](https://docs.cline.bot/cline-cli/samples/model-orchestration); comparison roundups, 2026
- No evidence found of an automatic "second model reviews this diff" built-in flow distinct from manually invoking a different mode/model — user has to wire it.

### Devin (Cognition)
- Bug/security flags carry **confidence/severity ratings** rather than a binary gate (Devin Review). Multi-agent parallel sessions (Devin 2.0, Apr 2025); Feb 2026 update added parallel-session + long-context retention improvements. Core plan: up to 10 concurrent sessions; unlimited users.
- **Isolation**: every session gets a full sandboxed VM (own IDE/browser/terminal), Cognition-hosted — no shared working tree across concurrent Devins.
- **Pricing**: ACU (Agent Compute Unit) ≈ 15 min of active autonomous work; Core $20 base + $2.25/ACU; Team $500/mo incl. 250 ACU @ $2.00/ACU + unlimited concurrency; Max $200/seat/mo (Jul 2026). This is metered compute, not flat seat-for-unlimited-headless-use. — [Dynalord/Usecarly pricing pages, 2026]
- No evidence Devin routes review to a different **vendor's** model as a deliberate second opinion; single-vendor (OpenAI/Anthropic backend not disclosed in sources found) confidence scoring instead.

### Codex CLI / ChatGPT (OpenAI)
- Codex CLI supports subagents and a documented pattern of running "a separate Codex agent as a pre-commit reviewer" — but that's a second *Codex* instance, not a second vendor by default.
- Model override exists (`codex -m <flag>`), and community tooling (a "Codex router") lets people point the harness at non-OpenAI models — this is user/community-built, not an OpenAI-shipped cross-vendor review feature. — [Opper.ai, Codex router guide, 2026]
- No first-party "ask Claude to review this Codex diff" feature found.

### Claude Code (Anthropic)
- Subagents run in isolated context + optionally isolated **git worktrees**; each subagent's `model` field can be set independently (Opus/Sonnet/Haiku) — but this is intra-Anthropic model selection, not cross-vendor, in the shipped product.
- Cross-vendor second opinions are achieved via **community MCP servers** layered on top — e.g. **Zen MCP** / its successor **PAL MCP** (formerly Zen), which let Claude orchestrate conversations with Gemini, OpenAI, X.AI models for "second opinion," consensus-building, and cross-model validation (`thinkdeep`, debate-style tools). This is MCP-mediated API multiplexing: the MCP server holds separate API keys per provider and Claude calls it as a tool. — [PulseMCP](https://www.pulsemcp.com/servers/zen-multi-model-ai-collaboration); [GitHub: BeehiveInnovations/pal-mcp-server](https://github.com/BeehiveInnovations/pal-mcp-server)
- **This repo's own hex system is itself in this category** (worth noting for the discussion, not as external evidence): hex's cross-model gate spawns other CLIs, which is exactly the pattern Anthropic's Jan 2026 enforcement action targets when it rides on *subscription* OAuth rather than metered API keys (see ToS section below).

### Windsurf (Cognition, post-acquisition of Codeium)
- **Arena Mode** (launched Jan 30 2026): side-by-side multi-model comparison on the same task — closest thing to a built-in, user-facing cross-model bake-off in this survey, though framed as "compare," not "review my code with model B."
- **Devin Review** (available since May 2026, post Cognition/Windsurf merger) does automated PR review without a manual Cascade session — Cognition's Devin-review tech folded into Windsurf.
- Cascade's own driver model is SWE-1.6 (Windsurf/Cognition in-house), +10% SWE-Bench Pro over SWE-1.5.

## Cross-cutting: what vendors explicitly decline to support (ToS evidence)

- **Anthropic Consumer ToS §3** (quoted verbatim, [anthropic.com/legal/terms](https://anthropic.com/legal/terms), fetched 2026-08-31):
  - Bans automated/non-human access "Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it, to access the Services through automated or non-human means, whether through a bot, script, or otherwise."
  - Bans building competing products: "To develop any products or services that compete with our Services, including to develop or train any artificial intelligence or machine learning algorithms or models or resell the Services."
  - Bans scraping/harvesting beyond what's permitted.
  - **Commercial Terms** separately prohibit reselling/intermediating Claude usage on end users' behalf, and forbid removing/disabling Claude Code's built-in auth.
- **Anthropic enforcement, Jan 9 2026**: technical crackdown on third-party harnesses spoofing the Claude Code client identity to ride flat-rate Pro/Max OAuth instead of metered API billing. Named casualties: **OpenCode** (directly broken), **Cursor** ("in certain configurations"), **Windsurf** (Anthropic had already cut it off in June 2025). Anthropic's Thariq Shihipar: "tightened our safeguards against spoofing the Claude Code harness," citing technical instability. OpenCode's maintainer responded within the same window by launching a $200/mo "OpenCode Black" tier that routes through enterprise gateways instead of consumer OAuth. — [VentureBeat, Jan 9 2026](https://venturebeat.com/technology/anthropic-cracks-down-on-unauthorized-claude-usage-by-third-party-harnesses)
  - **Direct relevance to this project**: any cross-model review design that has Claude Code (on a Pro/Max seat) drive a second CLI, or has a second CLI impersonate Claude Code to piggyback its OAuth, sits exactly in the enforcement zone above. Using a distinct, metered API key per tool (not shared subscription OAuth) is the documented-safe path.
- **OpenAI Terms of Use** ([openai.com/policies/row-terms-of-use](https://openai.com/policies/row-terms-of-use/)): prohibits using Output to build/train competing models; prohibits reverse engineering; prohibits "automatically or programmatically extract[ing]" data/Output at scale; API/Enterprise/Team data is excluded from model training by policy (separate from the competing-use ban).
- **GitHub**: Acceptable Use Policy bars "excessive or automated usage" / bulk automated Copilot requests — abuse-detection triggers temporary suspension. Could not find a published numeric threshold (negative below).
- **Cursor**: no automation-specific clause surfaced beyond standard no-resale/non-transferable-seat language; nothing found forbidding driving Cursor programmatically from another tool (contrast with Anthropic's explicit stance).

## Isolation & concurrency mechanisms (concrete implementations)

| Product | Mechanism |
|---|---|
| Cursor Cloud/Background Agents | Per-task VM, own filesystem/terminal; Docker-based env (`.cursor/environment.json` or Dockerfile) or saved snapshot; layer-cached builds |
| GitHub Copilot coding agent | Isolated, ephemeral GitHub Actions container per session, destroyed after; branch-scoped push (`copilot/*`); firewalled egress; optional self-hosted ARC runners |
| Devin | Cognition-hosted sandboxed VM per session (IDE+browser+terminal); up to 10 concurrent sessions (Core), unlimited (Team) |
| Amp | Subagent-per-check pattern within one orchestrator process (no separate VM evidence found — negative below) |
| Claude Code | Git-worktree isolation for parallel subagents (community-documented pattern: 4–8 concurrent worktrees/dev as of mid-2026); no vendor-shipped VM sandbox for local subagents (cloud/Actions integration is separate) |
| Windsurf | Cascade sessions; Arena Mode compares models but isolation-implementation detail not found in sources |

## Pricing/metering reality for headless/programmatic use

- **Claude Code**: headless (`claude -p`), Agent SDK, and GitHub Actions usage currently draw from the **same** subscription usage limits as interactive use (5-hour rolling window + weekly ceiling), shared with claude.ai chat. Anthropic announced (then paused, June 15 2026) a plan to move this to a separately metered credit pool at standard API rates — signals headless/automated draw was seen internally as disproportionate to flat-fee pricing, consistent with the Jan 2026 anti-spoofing crackdown. — [CloudZero/Verdent pricing guides, 2026]
- **Devin**: explicitly metered (ACU-based), not seat-flat — automation cost is transparent and scales with compute used, sidestepping the "is headless free" question entirely.
- **GitHub Copilot**: Business/Enterprise seat includes code-review "instantly" per search summaries, but automated/bulk use is capped by abuse-detection rather than a published quota (negative below).
- **Amp / Cursor BugBot / Windsurf**: pricing pages not fetched directly in this pass; BugBot is a separate $40/user/mo SKU from Cursor's editor seat, i.e., review is metered/sold separately rather than bundled into headless coding quota.

## negative
- Could not find a GitHub-published numeric automation/rate-limit threshold for Copilot — only "excessive/automated usage may trigger abuse detection," no number.
- Could not verify Amp's isolation mechanism for concurrent subagents (VM vs. process-level) — no primary-source doc fetched, only secondary write-ups.
- Could not find a Cursor ToS clause specifically addressing "driving Cursor programmatically from a third-party automation tool" (unlike Anthropic's explicit stance) — absence may mean permissive, or may mean uncovered by search; not confirmed either way.
- Could not confirm whether OpenAI's Codex CLI ToS specifically forbids pointing the harness at a non-OpenAI backend via community routers — found evidence the practice exists (Codex router tooling) but no OpenAI statement for or against it.
- Devin's backend model vendor(s) were not disclosed in any source fetched — cannot say whether its "confidence-scored" review ever crosses vendors internally.
- Have not independently re-verified the Register article (404'd); relied on VentureBeat's Jan 9 2026 coverage of the same Anthropic OAuth-spoofing crackdown as the primary source for that finding.
- Anthropic's Commercial (non-consumer) Terms of Service full text was not fetched directly — commercial-terms quotes above are secondary-sourced (autonomee.ai, groundy.com summaries), not a direct fetch of the commercial ToS PDF.

## leads
- **Anthropic OAuth-spoofing enforcement (Jan 9 2026)** is the single most load-bearing fact for this project's own design: if hex's cross-model gate ever has one CLI ride another's subscription auth (vs. each tool using its own metered API key), it risks the same enforcement Cursor/Windsurf/OpenCode hit — worth a dedicated architecture-lane follow-up on "which auth mode does hex's cross-model gate assume."
- **Zen MCP / PAL MCP** is a working, shipping precedent for exactly the "Claude Code asks a different vendor's model for a second opinion via MCP" pattern this project may want — worth a technical-lane deep dive on its actual protocol/tool-call shape rather than the secondary write-ups used here.
- **Amp's Oracle sub-agent** (Claude main thread routing to a GPT reasoning model for review) is the cleanest same-product cross-vendor precedent found — worth checking Sourcegraph/Amp's own engineering blog (not reached in this pass) for how they justify/license the cross-vendor API calls.
