# Pre-Implementation Discussion Phase — GitHub Evidence

Researched: 2026-08-28. Expires: 2027-02-28.

## Sources

- https://github.com/addyosmani/agent-skills — 90.5k★/9.7k forks, 24 lifecycle skills incl. `spec-driven-development` + `interview-me`, pushed daily
- https://github.com/github/awesome-copilot — 38.4k★, official GitHub org; `breakdown-feature-prd` skill, pushed 2026-08-28
- https://github.com/RobMitt/grill-me-skill — 348★/42 forks, 0 open issues; decision-tree interview skill, origin repo (many forks)
- https://github.com/genkovich/sdd — 117★/44 forks, 82 commits; 22 atomic Socratic skills + tool-adapter map
- https://github.com/paulp-o/ask-user-questions-mcp — 146★; MCP unified question inbox across agents
- https://github.com/Sorbh/interview-me — 43★; senior-architect interview skill, has `--verify` drift detection
- https://github.com/Q00/Symposium — 30★/8 forks; Socratic "Seed" artifact pack
- https://github.com/engineering4ai/awesome-spec-driven-development — 252★; curated index, 40+ entries across standards/tools/frameworks

## Findings

### 1. What practitioners praise / demonstrably works

- **One-question-at-a-time is the near-universal winning pattern.** Independently converged on by `interview-me` (agent-skills), `grill-me-skill`, `Sorbh/interview-me`, and `genkovich/sdd` — all four reject batched question lists as producing "surface answers."
- **Attaching a guessed answer to each question** (agent-skills `interview-me`): forces the agent to commit to a hypothesis rather than fish neutrally; framed as what separates a real interview from a form.
- **Explicit confirmation before persistence.** agent-skills `interview-me` requires an unambiguous "yes" to a 6-part restate (Outcome/User/Why now/Success/Constraint/Out of scope) before writing anything to disk — "sounds good" / "whatever" do not count.
- **Gated artifact chains** (`genkovich/sdd`): each of 13 backbone stages hard-refuses to run if its prerequisite artifact is missing; every handoff ends in a copy-ready "next command to run after `/clear`" block — cited as a concrete anti-drift mechanic.
- **Depth dial** (`sdd`: easy/medium/hard) lets question breadth scale to risk without ever dropping acceptance-criteria coverage — offered as the fix for "the interview is either too shallow or too exhausting."
- **Drift detection after the fact** (`Sorbh/interview-me --verify`): re-scans committed code against the original spec for contradictions/unplanned expansion — treats the discussion artifact as a living contract, not a one-time doc.
- **Cross-agent unified inbox** (`paulp-o/ask-user-questions-mcp`, 146★): lets several parallel agents (Claude Code, Cursor, OpenCode) queue clarifying questions to one human-facing inbox instead of each blocking its own thread — "one queue, one source of truth."

### 2. What fails / is explicitly guarded against

These are the anti-patterns the skills themselves were built to suppress — the clearest signal of what practitioners observed going wrong before these existed:
- **Agent self-answers instead of asking** — filling in who benefits / why now / what success means from its own assumptions (agent-skills `interview-me`, Symposium's whole premise: vague words like "simple" or "dashboard" get silently filled by the model).
- **Batching multiple questions into one message** — named as a "red flag" that degrades answer quality.
- **Accepting soft confirmation as terminal** — "sounds good," "whatever you think" treated explicitly as *not* consent; "whatever you think" is reframed as a delegation to push back on, not a decision.
- **Producing the spec/plan before explicit restatement confirmation** — flagged as a red flag in agent-skills; genkovich/sdd's gating exists for the same reason.
- **Stagnant confidence across rounds** — 3+ interview rounds with non-rising confidence signals the wrong line of questioning, not persistence.
- **Running interview skills non-interactively** (CI, autonomous loops) — agent-skills `interview-me` explicitly warns against this; underspecification should block, not be guessed through, when no human can answer.
- **Rationalizations table** (agent-skills) directly catalogs the excuses that precede the above failures: "the ask is clear enough," "asking wastes their time," "I'll figure it out while building" — each paired with the concrete cost it hides.

### 3. Concrete mechanics

| Mechanic | Example |
|---|---|
| Question cadence | One question/turn, wait for answer, no batching (near-universal) |
| Pushback rule | Hard-block on security gaps; push back on contradictions (Sorbh/interview-me) |
| Anti-sycophancy | Reject "sounds good"; require explicit yes to a structured restate (agent-skills) |
| Confidence gate | ~95% ("can I predict the next 3 answers?"); <70% needs a stated gap (agent-skills) |
| Depth control | easy/medium/hard dial, decisions-only vs. full trade-off walk (sdd) |
| Cross-tool mapping | `AskUserQuestion` → Codex stdin/TUI → Cursor chat panel (sdd `tool-adapters.md`) |
| Artifact produced | Confirmed intent statement → `spec.md` (sdd); PRD w/ 8 sections (awesome-copilot); Seed (goal/constraints/acceptance/ontology) (Symposium); markdown spec + decision log + implementation order (Sorbh) |
| Handoff | `spec.md` gates `clarify`→`design`→...→`implement` (sdd); PRD is engineering's "single source of truth" feeding a tech spec (awesome-copilot); confirmed restate is what specs/plans downstream consume (agent-skills) |
| Async/parallel | Unified cross-agent question inbox, non-blocking (paulp-o AUQ) |
| Graceful degradation | Missing MCP (e.g. Figma) → stages fall back to markdown wireframes rather than blocking (sdd) |

### 4. Hard numbers

- addyosmani/agent-skills: **90.5k★ / 9.7k forks**, 60 open issues, pushed daily
- github/awesome-copilot: **38.4k★**, pushed 2026-08-28
- RobMitt/grill-me-skill: **348★ / 42 forks**, 0 open issues
- genkovich/sdd: **117★ / 44 forks**, 82 commits
- paulp-o/ask-user-questions-mcp: **146★**
- Sorbh/interview-me: **43★**
- Q00/Symposium: **30★ / 8 forks**
- engineering4ai/awesome-spec-driven-development: **252★**, 40+ curated entries across 8 categories (specification tools, frameworks, IDE integrations, MCP servers, workflow mgmt)

Gap: no direct evidence of issue-thread/HN-style user complaints was retrievable via page fetch (GitHub Issues content wasn't rendered); §2 is inferred from what each skill's own guardrails target.
