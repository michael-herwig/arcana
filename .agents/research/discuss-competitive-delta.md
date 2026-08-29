# Discuss-mode competitive delta

Researched: 2026-08-28. Expires: 2027-02-28.

## Sources

- https://api.github.com/repos/github/spec-kit — live stargazer/fork counts
- https://api.github.com/repos/Fission-AI/OpenSpec — live stargazer/fork counts
- https://api.github.com/repos/obra/superpowers — live stargazer/fork counts
- https://api.github.com/repos/ruvnet/ruflo — live stargazer/fork counts (claude-flow renamed)
- https://api.github.com/repos/MadeByTokens/claude-brainstorm — live stargazer counts
- https://github.com/Fission-AI/OpenSpec/blob/main/CHANGELOG.md — v1.8.0–v1.11.0 explore-mode consent hardening
- https://github.com/MadeByTokens/claude-brainstorm — dedicated brainstorm-mode plugin mechanics
- https://deepwiki.com/ruvnet/claude-flow/9.1-sparc-methodology + gist.github.com/ruvnet/e8bb444c6149e6e060a785d1a693a194 — SPARC specification-phase interactivity (secondary, thin)
- https://claudemarketplaces.com — marketplace plugin counts + discuss-related listing search
- https://github.com/anthropics/claude-plugins-official — official marketplace plugin count
- https://dev.to/stevengonsalvez/claude-flow-the-multi-agent-swarm-orchestrator-before-it-got-a-new-name-4kd4 — secondary, claude-flow→ruflo rebrand context (>1yr-adjacent framing, verify against primary repo)

## Direct answer

The competitive-landscape axis is not saturated by the 8 prior artifacts on one dimension: none of them covers claude-flow/ruflo (swarm orchestrators) or gives adoption numbers for spec-kit/OpenSpec/superpowers themselves. That gap is now closed. The single most important shipped-recently finding: **OpenSpec independently hardened its explore-mode consent boundary in v1.9.0–v1.11.0** — "answering its own clarifying questions no longer reads as consent," now requiring a separate explicit yes/no before any file write. This is the same anti-sycophancy principle `discuss-github.md` documented in agent-skills' `interview-me` (restate-then-confirm) and Sorbh's `--verify`, now independently converged on by a second, actively-growing maintainer team — treat it as validated field consensus, not a one-off design choice.

## Trends

- **Convergence, not divergence, on "consent ≠ answered-a-question."** Two unrelated projects (agent-skills, OpenSpec) landed on the same fix within the same research window. hex-discuss should treat this as a baseline requirement, not a differentiator.
- **The whole SDD-tooling category is still in a growth phase, not consolidating.** spec-kit went 111k→132k stars in under 8 weeks; superpowers is at 279k (up from a widely-cited 150k in April); OpenSpec sits at 66.6k. None of this reads as a closing window — there's room to enter.
- **Swarm orchestrators are generalizing on *execution* (multi-agent, multi-vendor), not on *discussion quality*.** ruflo's own tagline now advertises "Claude Code / Codex / Hermes and many more" — cross-agent portability is the axis they're racing on, leaving interview/pushback mechanics undeveloped and CLI-flag-shallow (a binary `non_interactive` toggle, not a designed interview).
- **A dedicated "discussion-mode plugin" niche exists but is unclaimed.** MadeByTokens/claude-brainstorm proves demand (hook-enforced state, code-writing blocked, technique menu) but is tiny and stale (13★, last push Jan 2026) — no one has won this specific product shape yet.
- **Rebrand/name-squat churn is real noise in this space** — claude-flow renamed to ruflo, with at least two lookalike forks (samart/claude-flow, kodflow/claude-flow) carrying identical marketing copy. Minor, but a discoverability hazard worth remembering for hex's own naming.

## Key findings (links)

1. **[github/spec-kit](https://github.com/github/spec-kit)** — 132,029★ / 11,861 forks, pushed today. `/speckit.clarify` is a bolt-on refinement command between `specify` and `plan` (already mechanics-documented in `discuss-skills-field.md`) — it has no state for the pre-spec fuzzy-idea stage. **Gap hex-discuss fills**: the "I don't know what I want yet" moment before `spec.md` exists at all.
2. **[Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)** — 66,563★ / 4,581 forks, pushed today. Closest philosophical match to hex-discuss (explore = zero artifacts, pure discussion) and just proved the field is actively hardening this exact boundary (v1.9–v1.11, see [CHANGELOG](https://github.com/Fission-AI/OpenSpec/blob/main/CHANGELOG.md)). **Gap**: TS/CLI-only, not a portable cross-agent skill — hex's packaging model is the differentiator, not the discussion mechanic itself.
3. **[obra/superpowers](https://github.com/obra/superpowers)** — 278,979★ / 24,981 forks. Brainstorming is one skill inside a fully chained lifecycle, and it's been in Anthropic's **official** Claude Code marketplace since Jan 15, 2026. **Competitive risk, not just gap**: users who already installed superpowers for the marketplace-official trust signal get a brainstorming step bundled in — hex-discuss should consider explicit interop rather than head-on replacement, given the scale gap.
4. **[ruvnet/ruflo](https://github.com/ruvnet/ruflo)** (claude-flow, renamed) — 69,628★ / 8,323 forks. SPARC's "Specification" phase is a `non_interactive: true/false` config flag on an autonomous agent, inside a 5-phase pipeline built for swarm parallelism (12 worker-daemon types, RAG, shared memory) — no one-question-at-a-time cadence, no pushback/anti-sycophancy instruction found anywhere in its docs. **Gap**: hex-discuss's conversational discipline has zero analog here; if a team already runs ruflo for execution, hex-discuss is the missing front door, not a competitor.
5. **Claude Code plugin marketplaces** — official ([anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)): 284 plugins as of 2026-08-10; community marketplace: 2,291 plugins, same date. A search for discuss-shaped listings on [claudemarketplaces.com](https://claudemarketplaces.com) surfaces exactly two direct hits — **grill-me** (now marketplace-distributed, not just a blog post as `discuss-skills-field.md` found it) and **MadeByTokens/claude-brainstorm** ([repo](https://github.com/MadeByTokens/claude-brainstorm), 13★, hook-enforced `.brainstorm-state`, blocks `.py`/`.js` file creation during the session, exits via `/brainstorm:done` into a full-log + ~20-line summary artifact pair). **Reading**: real demand, unclaimed product — nobody has made "discussion mode" a marketplace headliner on its own merits yet.

## Recommendation (rationale)

Ship hex-discuss positioned as **OpenSpec's zero-artifact discussion rigor, packaged as a portable cross-agent skill** — that's the specific white space: OpenSpec has the mechanic and the momentum but not the distribution model hex already has via grim; superpowers has the distribution and scale but discussion is a minor step in a much bigger bundle, not the product; claude-flow/ruflo has neither. Concretely: (1) adopt OpenSpec's hardened consent rule verbatim — a proposed artifact list plus a separate explicit yes, never inferred from answering a clarifying question — since two independent maintainers now agree on it; (2) do not compete with superpowers on lifecycle breadth, consider explicit compatibility/handoff notes instead, given its 279k★ and official-marketplace placement; (3) treat claude-flow/ruflo users as a downstream integration target (hex-discuss feeding a SPARC/swarm pipeline) rather than a competing surface, since it has no discussion-quality story to lose to.
