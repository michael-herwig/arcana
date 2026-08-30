# Research: How commercial autonomous coding agents bound verification/review effort per step

## Metadata
Date: 2026-08-30
Expires: 2027-02-28

## Scope
Neutral evidence survey (no recommendation) across six commercial autonomous
coding agent products: Devin (Cognition), GitHub Copilot coding agent,
Cursor background agents / Bugbot, OpenAI Codex (cloud agent), Claude Code
cloud sessions, Amazon Q Developer agents. Three questions: (1) test suite
scoping per iteration, (2) decomposition/parallelism for large changes, (3)
review-pass granularity (incremental vs full-diff) and published cost/latency
trade-offs.

## Findings by product

### Devin (Cognition)
- Architecture: cloud "brain" (stateless reasoning) + containerized "Devbox"
  execution workspace; orchestrates specialized sub-agents for planning,
  execution, verification, debugging. [Fastio architecture writeup](https://fast.io/resources/cognition-devin-ai-architecture/)
- Verification-at-scale post: Devin writes an explicit **test plan** ("clear
  target about what to test," "grounded in source, not assumptions") before
  running tests — implies scoped, plan-driven testing rather than a fixed
  full-suite-every-time policy, but the post does not state a mechanical rule
  for full vs. subset. **Devin Review** is described as closing the loop by
  "fixing each finding until the diff comes back clean" — phrasing implies
  diff-scoped review, not stated as incremental-vs-full explicitly.
  [Verifying Agentic Development at Scale](https://cognition.com/blog/testing-development)
- Cost signal: "billing at 1/5th the normal usage cost while in test mode" —
  the only explicit cost/latency number found for Devin.
- Parallelism: engineers report running "10 to 20 Devins in parallel, each
  with its own dev server" — this is user-level parallel *sessions*, not a
  documented in-agent sub-task decomposition/hierarchy for a single large
  change. [Fastio](https://fast.io/resources/cognition-devin-ai-architecture/)
- Dogfooding post ("How Cognition Uses Devin to Build Devin") recommends
  **human-directed** decomposition — "large-scale challenges should be broken
  into smaller, isolated tasks across separate sessions" — i.e., published
  guidance pushes decomposition onto the operator, not documented as automatic
  agent-side task splitting. [cognition.com/blog/how-cognition-uses-devin-to-build-devin](https://cognition.com/blog/how-cognition-uses-devin-to-build-devin)
- Testing artifact format: labeled screenshots + chaptered test video with
  pass/fail assertions, used for app-level (UI) verification specifically.

### GitHub Copilot coding agent
- Runs inside a GitHub Actions-backed sandbox; closed-loop: "run your existing
  test suites, wait for long-running integration tests, read build logs, and
  iterate on failures before creating a PR" — vendor language claims **existing
  test suites** run (suggests full suite as configured in CI), no published
  subset-selection mechanic found. [GitHub Blog: coding agent 101](https://github.blog/ai-and-ml/github-copilot/github-copilot-coding-agent-101-getting-started-with-agentic-workflows-on-github/)
- Hard **time bound, not a step/test bound**: each run has a documented ceiling
  of **59 minutes** wall-clock; that ceiling — not a turn or test count — is
  what forces the agent to wrap up. [GitHub Community discussion #177410](https://github.com/orgs/community/discussions/177410)
- Cost: nominally "one premium request per session" in docs, but practitioner
  reports put actual consumption at **20–50 (some report 30–50) premium
  requests per invocation** — the agentic loop's real cost is much higher than
  the advertised unit. GitHub Actions minutes are billed separately from the
  shared org allowance. [itnext.io teardown](https://itnext.io/github-copilot-coding-agent-the-complete-architecture-behind-agentic-devops-at-enterprise-scale-1f42c1c132aa), [GitHub Docs: requests in Copilot](https://docs.github.com/copilot/concepts/copilot-billing/understanding-and-managing-requests-in-copilot)
- Review: opens a draft `[WIP]` PR, updates it with title/description when
  done, accepts `@copilot`-tagged PR comments to iterate — no published
  statement on whether Copilot re-reviews the whole diff or only the deltas
  addressed by a comment.
- No published system card / technical report with explicit turn-limit or
  test-selection numbers was found (checked GitHub's "Application card:
  GitHub Copilot Agents" — describes responsible-use framing, not internal
  budgets).

### Cursor background agents / Bugbot
- **Background agents**: cloud-sandboxed, git-worktree-isolated; native
  parallel-agent support since v2.0 (**up to 8 agents on one problem**,
  auto-picks the best result); nested subagents since v2.5, one level deep
  (a subagent's own subagent cannot spawn further). [Cursor Subagents docs](https://cursor.com/docs/subagents), [dev.to Cursor 3 writeup](https://dev.to/thegdsks/cursor-3-ships-parallel-ai-agents-here-is-the-multi-agent-workflow-that-actually-works-2bk8)
- **Bugbot review scope is an explicit, documented toggle**: by default,
  Bugbot reviews **only the changes since the previous Bugbot review**
  (incremental); "Incremental Review" can be turned off to force full-PR-diff
  review on every push. This is the clearest published incremental-vs-full
  mechanism found across all six products. [Cursor Bugbot docs](https://cursor.com/docs/bugbot)
- Bugbot also does **differential review syncing**: if a remote diff matches
  an already-processed local diff, it skips redundant cloud execution and
  posts a reference to the prior run instead of re-billing.
- **Effort levels** (Default / High / Custom) are an explicit, published
  reasoning-budget knob, independent of the incremental/full toggle: Default
  finds ~0.7 bugs/run (79% resolved at merge), High finds ~0.95 bugs/run
  (~35% more, similar ~80% resolution) at higher latency and cost; Custom
  routes by natural-language rule (e.g., file path) between the two.
  [aicatchup.com effort-levels writeup](https://aicatchup.com/news/cursor-bugbot-effort-levels-usage-based-billing)
- Published latency/cost trajectory: reviews now average **~90 seconds**
  (down from ~5 minutes), 90% finish under 3 minutes, at **~22% lower cost
  per run** with **~10% more bugs found** than the prior version; typical run
  costs **$1.00–$1.50**. [getaibook.com](https://getaibook.com/news/cursors-composer-25-cuts-bugbot-review-times-to-90-seconds/), [digitalapplied.com](https://www.digitalapplied.com/blog/cursor-bugbot-90-second-reviews-june-2026-release)

### OpenAI Codex (cloud agent)
- Sandbox model: **two-phase runtime** — a network-enabled setup phase
  (install deps), then an **offline-by-default agent phase**; each task gets
  its own sandbox, preloaded with the repo. [OpenAI: Running Codex safely](https://openai.com/index/running-codex-safely/)
- Verification: "explicitly trained to iterate until tests pass without
  modifying them" — runs tests inside the sandbox and reads error output to
  self-correct; no published mechanic for scoping *which* tests run per
  iteration (full suite vs. targeted subset) was found for the cloud agent
  itself.
- Long-horizon task decomposition is **user/prompt-authored, not automatic**:
  OpenAI's own guide recommends a durable markdown "project memory" pattern —
  `Prompt.md` (frozen spec), `Plan.md` (breaks work into milestones "small
  enough to complete in one loop"), `Implement.md` (validate-after-each-step
  instructions), `Documentation.md` (status/decision log) — with an explicit
  **stop-and-fix rule**: run lint/typecheck/test/build at every milestone
  and repair failures before continuing. A cited 25-hour run consumed ~13M
  tokens and produced ~30k LOC, with no published cost/latency guidance for
  sizing tasks. [OpenAI Developers: long-horizon tasks with Codex](https://developers.openai.com/blog/run-long-horizon-tasks-with-codex)
- Parallelism: users can fire multiple independent Codex cloud tasks
  concurrently, each in its own sandbox — parallel *tasks*, not a documented
  in-task sub-agent hierarchy.
- Separately, **OpenAI's code-review verifier research** (not the Codex cloud
  agent specifically, but OpenAI's applied alignment team, describing a
  review/verification model used at scale) is the most explicit published
  statement in this whole survey on *why* verification effort is bounded:
  it deliberately trades recall for precision ("modestly reduced recall in
  exchange for high signal quality... low safety tax"), uses repo-wide
  context rather than diff-only analysis, and reports that **the verifier
  remains effective "at a small fraction of the generator's token spend"** —
  an explicit inference-budget-vs-catch-rate tradeoff statement. It is
  steerable per-repo via AGENTS.md/custom instructions. No tiered
  fast-check/slow-check hierarchy is spelled out despite that being implied
  by "low safety tax" framing. [OpenAI: A Practical Approach to Verifying Code at Scale](https://alignment.openai.com/scaling-code-verification/)

### Claude Code cloud sessions (Anthropic)
- Each cloud session runs in its own isolated, ephemeral sandbox (created at
  session start, destroyed at end, no cross-session state sharing).
  [Claude Cowork architecture overview](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview)
- Review UI is diff-based per session (added/removed line counts, inline
  comments feeding the next turn) — this is a **product review surface**, not
  a published statement about whether the *agent itself* re-verifies the
  whole diff or only the delta after a comment.
  [Claude Code on the web docs](https://code.claude.com/docs/en/claude-code-on-the-web)
- The most concrete published verification/test-scoping mechanics for Claude
  Code are **local-CLI feature docs, not cloud-session-specific**: subagents
  with separate context windows, "dynamic workflows" letting Claude write its
  own orchestration script and spin up "hundreds" of parallel subagents in a
  session, and a documented pattern of a **separate verification subagent
  grading a fresh model's output** so "the agent doing the work isn't the one
  grading it." One published example: 92 LLM calls in 13 minutes using up to
  7 parallel subagents for codebase exploration before a fix. No published
  numeric test-selection or review-budget policy (full suite vs. subset;
  incremental vs. full diff) was found specific to *cloud* sessions.
  [Anthropic: Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)
- The compiler-building case study (16 parallel Claude instances, ~2,000
  sessions, ~$20,000 API cost, 100k LOC) is Anthropic's most detailed
  published account of decomposition + verification at scale for a large,
  long-running change: task ownership via lock files
  (`current_tasks/` directory) prevents duplicate work; verification used
  **differential testing against GCC as an oracle** to isolate discrepancies,
  explicitly decomposing "the monolithic task into smaller, verifiable
  units." This is architecture research/demo framing, not a statement of
  product-wide policy for Claude Code cloud sessions.

### Amazon Q Developer agents
- `/test` unit-test generation workflow: generates tests, **self-debugs test
  errors**, and requires explicit user consent before adding tests — a
  human-in-the-loop gate not present as described for the other five
  products' default flow.
- General dev agent: "run the selected build and test commands to ensure the
  code is working as expected... iterate on the code prior to requesting the
  developer's review" — "**selected**" build/test commands implies a scoped
  (configured) set rather than an automatically-discovered full suite, but no
  published rule for what "selected" means or how scope is chosen was found.
  [AWS: Amazon Q Developer agent now runs builds and tests](https://aws.amazon.com/about-aws/whats-new/2025/01/amazon-q-developer-agent-builds-tests-validate-generated-code-real-time)
- **Code Transformation agent** (Java/.NET/mainframe migration) is Amazon's
  most detailed published decomposition case: a **debugger agent** with tools
  to browse/explore, edit files, trigger builds, add dependencies; workflow
  is "apply changes → build → test changed code" per iteration, but the
  published post does not state full-suite-vs-subset explicitly, and
  describes iteration as **sequential error-fixing**, not parallel sub-task
  fan-out, despite the surrounding product supporting bulk/parallel job
  submission across many repos. Reported gain: **85% higher success rate**
  vs. the prior (single-shot) approach on a 62-app, 100k+-LOC benchmark.
  [AWS: Dissecting the Performance Gains](https://aws.amazon.com/blogs/devops/dissecting-the-performance-gains-in-amazon-q-developer-agent-for-code-transformation/)
- Business-level decomposition numbers exist (avg. transformation time ~15
  minutes/app; Amazon-internal Java 17 migration saved "4,500 years" of dev
  work and $260M/year) but these are outcome metrics, not published
  mechanics of how verification effort is bounded per step.
  [Amazon press center](https://press.aboutamazon.com/2024/12/new-amazon-q-developer-capabilities-accelerate-large-scale-transformations-of-legacy-workloads)

## Cross-product pattern (evidence-only, no recommendation)
- **Explicit, mechanical incremental-vs-full toggle**: only Cursor Bugbot
  publishes one plainly (diff-since-last-review default, full-diff opt-out).
  Everyone else's public docs describe review qualitatively ("closes the loop
  until diff comes clean," "iterate on failures") without stating the
  comparison window.
- **Hard time bound vs. step/test bound**: GitHub Copilot coding agent is the
  only product with a published, unconditional wall-clock cutoff (59 min)
  that is explicitly *not* a step-count or test-count limit.
- **Reasoning-effort as a first-class, priced knob**: Cursor Bugbot (Default/
  High/Custom) is the clearest published example of verification effort being
  sold and measured as a spend/catch-rate tradeoff, with paired bugs-per-run
  and cost numbers. OpenAI's verifier research states the same idea
  (fraction-of-generator-spend catches most high-severity issues) but as
  research framing, not a per-product user-facing toggle.
- **Decomposition of long-running large changes is mostly human/prompt-
  authored, not automatic**, in the published guidance: Devin's own
  dogfooding post tells operators to split work into separate sessions;
  OpenAI's long-horizon guide has the user pre-write a milestone plan file.
  The exception is Anthropic's C-compiler case study and the "dynamic
  workflows" feature, where the agent itself writes the orchestration/lock
  files — but that is demoed as a capability, not documented as the default,
  bounded behavior of a cloud session.
- **Verification-budget-vs-generation-budget as an explicit ratio** appears
  only in OpenAI's alignment-team verifier research ("small fraction of the
  generator's token spend").

## negative
- No vendor among the six publishes an explicit "runs N% of the suite" or
  "selects tests via impact analysis" mechanic — despite this being a common
  request pattern, none of Devin, Copilot, Cursor, Codex, Claude Code, or
  Amazon Q Developer state a concrete test-selection algorithm in public
  docs/blogs. Multiple sources use scoping language ("existing test suites,"
  "selected build and test commands," "test plan") without defining the
  selection mechanic.
- Found no system-card-style technical report for GitHub Copilot coding agent
  with explicit turn/step limits (only the 59-minute wall-clock bound is
  documented; community discussions confirm this is the binding constraint,
  not a step count).
- Cognition's two blog posts (testing-development, how-cognition-uses-devin)
  do not state whether Devin Review is incremental or full-diff — inferred
  language only ("closes the loop... until diff comes back clean").
- Amazon Q Developer's Code Transformation post describes the debugger agent
  as fixing errors **sequentially**, which is evidence *against* an
  automatic parallel sub-task fan-out for a single large transformation job,
  even though the product supports submitting many transformation jobs in
  parallel across repos/apps.
- Did not find a credible independent teardown (third-party, non-vendor) with
  hard benchmarked numbers on verification-cost-per-iteration for Devin,
  Copilot coding agent, or Amazon Q Developer specifically — the strongest
  independent numbers found were for Cursor Bugbot (getaibook.com,
  digitalapplied.com) since those track a public product update cadence.

## leads
- Devstral research paper (arXiv 2509.25193) explicitly studies **max
  iteration/turn limits of 30/50/100** as a controlled variable for SWE-bench-
  style agent performance — an academic (non-vendor) angle on the same
  question, worth a dedicated lane if academic/benchmark evidence on turn-limit
  effects is in scope elsewhere.
- OpenAI's Promptfoo "Evaluate Coding Agents" guide and the "eval-skills"
  developer blog look like a vein for how third parties benchmark agent
  verification behavior — not pursued here (out of scope: neutral vendor-only
  research, this is an eval methodology tangent).
- Cursor's nested-subagent depth limit (one level: a subagent's subagent
  cannot itself spawn further subagents) is a concrete architectural
  constraint that could be directly relevant to any lane comparing sub-agent
  hierarchy depth limits across products.
- The Anthropic "dynamic workflows" feature (Opus 4.8, referenced as a
  research preview) — a agent-authored-orchestration capability distinct from
  the C-compiler case study — was mentioned only in passing by secondary
  sources; a lane specifically on this feature's published mechanics (as
  opposed to the compiler demo) would need Anthropic's own docs, not yet
  fetched here.
