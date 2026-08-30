# Research: OSS multi-agent coding orchestrator scheduling & verify-loop structure

## Metadata
Date: 2026-08-30
Expires: 2027-02-28
Lane: competitive/vendor, neutral (evidence only, no recommendation)

## Scope
Claude Code subagent/swarm skill collections (am-will/swarms, affaan-m/claude-swarm,
dsifry/metaswarm, ZaxbyHub/opencode-swarm, ruvnet claude-flow/ruflo), plus
LangGraph/CrewAI/AutoGen as the general-purpose multi-agent frameworks when
applied to code tasks. Questions: (1) scheduling model, (2) verification
structure + effort budgets, (3) sub-orchestrator nesting + depth experience.

## Findings

### 1. Scheduling: dependency-driven parallel waves converge across independent projects

- **am-will/swarms**: tasks declare `depends_on`; orchestrator computes waves
  (topological levels) — independent tasks in a wave run in parallel via
  spawned subagents, waves run sequentially. Documented example: Wave1 {T1,T2}
  parallel → Wave2 {T3,T4} after T1 → Wave3 {T5} after T3+T4 → Wave4 {T6}.
  https://github.com/am-will/swarms
- **affaan-m/claude-swarm**: Opus analyzes the codebase, builds a dependency
  graph, topologically sorts into waves; independent subtasks run
  simultaneously via the Claude Agent SDK, dependents wait. Adds pessimistic
  file locking (`{auth.ts -> Agent 1}`) to prevent concurrent-write conflicts.
  https://github.com/affaan-m/claude-swarm
- **ZaxbyHub/opencode-swarm**: hub-and-spoke by default (architect assigns
  work serially: coder → reviewer → test_engineer). v8 adds parallel
  execution in isolated git worktrees, but *only* for "provably file-disjoint
  task groups" — each agent declares write-target scope; on overlapping or
  unknown scope the system **automatically falls back to serial**. This is
  the most concrete "ready-set" safety valve found in the sweep.
  https://github.com/ZaxbyHub/opencode-swarm
- **ruvnet/claude-flow (now ruflo)**: markets mesh/hierarchical/adaptive
  topologies with "automatic task distribution, load balancing, fault
  tolerance" across a 3-tier stack (ruv-swarm local → Claude Flow
  coordination → Flow Nexus cloud). Documentation is marketing-heavy;
  concrete scheduling internals (how waves/DAG are actually computed) are
  much less specified than the three repos above.
  https://github.com/ruvnet/ruflo/wiki/Workflow-Orchestration ,
  https://github.com/ruvnet/ruflo/issues/945 (V3 "complete rebuild" — signals
  the architecture is still churning)
- **LangGraph**: the general primitive underlying all of the above —
  StateGraph is an explicit, hand-built DAG (fan-out/fan-in nodes + edges),
  not an auto-inferred dependency graph from task metadata the way the
  Claude-Code-native swarm skills do it.
  https://www.langchain.com/langgraph
- **CrewAI**: coarser — only two built-in processes, `sequential` (strict
  order) or `hierarchical` (one manager LLM dynamically delegates/reviews at
  runtime). No static dependency-graph decomposition into parallel waves.
  https://docs.crewai.com/en/learn/hierarchical-process
- **AutoGen**: GroupChat is conversational turn-taking (a manager picks the
  next speaker), not a scheduler in the DAG sense at all.
  https://microsoft.github.io/autogen/0.2/docs/Use-Cases/agent_chat/

**Convergent pattern**: independently-built Claude-Code-native swarm skills
all reinvented "declare deps → compute waves/topo-sort → parallelize within
a wave, serialize across waves," plus a file-conflict guard (locking or
scope-disjointness + auto-serial-fallback). The general-purpose frameworks
(LangGraph/CrewAI/AutoGen) don't ship this out of the box — you'd build it
yourself on LangGraph's graph primitives, or you don't get it at all in
CrewAI/AutoGen's built-in process types.

### 2. Verification: two camps — per-task/per-wave loop vs. single global gate

**Per-task or per-wave loop:**
- am-will/swarms verifies at each **wave boundary** before advancing (not
  fully per-task, not fully global — a middle tier).
- ZaxbyHub/opencode-swarm runs a full loop per task: "coder writes code →
  automated checks run → reviewer checks correctness → test engineer writes
  and runs tests → architect runs regression sweep → failures loop back with
  structured feedback," THEN a separate coarser `phase_complete` gate
  ("bounded read-only gate report, revalidates the exact plan/config/evidence
  snapshot under lock") once all tasks in a phase finish. So it's two-tier:
  tight per-task loop + a phase-level re-check.
- dsifry/metaswarm: per-work-unit cycle IMPLEMENT → VALIDATE → ADVERSARIAL
  REVIEW → COMMIT; the orchestrator explicitly does not trust subagent
  self-reports — it re-runs tests itself and checks "DoD compliance with
  file:line evidence." Has a stated "3-iteration cap before human
  escalation." https://github.com/dsifry/metaswarm

**Single global gate:**
- affaan-m/claude-swarm explicitly skips per-subtask verification — junior
  agents run free in their waves, then one senior-model pass (Opus, "Phase
  2.5") reviews the *combined* diff for "correctness, consistency, and
  completeness" and catches cross-agent integration issues. Philosophy
  quoted verbatim: "a senior architect designs the plan, junior engineers
  execute in parallel, and the senior reviews the combined result."

**Effort/cost budgets:**
- affaan-m/claude-swarm: explicit dollar budget with a dashboard
  ("Budget: $0.23 / $5.00") and a hard cutoff that cancels remaining tasks
  when exceeded.
- opencode-swarm: a per-task tool-call ceiling ("200 tool calls") as a
  guardrail, but no token/effort budget tied to task complexity.
- No surveyed OSS coding orchestrator was found wiring a *complexity-scaled*
  per-task effort budget into its verify loop (e.g., spend less on
  verifying a trivial task). The nearest first-party analog is Claude's own
  platform **Task budgets** feature — the model sees a live token countdown
  for a full agentic loop and paces/finishes against it — but this is an
  API-level primitive, not something any surveyed swarm-skill repo visibly
  consumes yet. https://platform.claude.com/docs/en/build-with-claude/task-budgets

### 3. Nesting: only one project claims it by name; no depth case studies found

- **dsifry/metaswarm** is the only project explicitly describing recursive
  orchestration: "Orchestrators spawn sub-orchestrators for complex epics
  (swarm of swarms)," each running its own Issue Orchestrator instance
  (implying its own review loop). No quantified max-depth or postmortem is
  given — only a claim of being field-proven across "hundreds of PRs."
- am-will/swarms, affaan-m/claude-swarm, and opencode-swarm are all
  documented as single-level orchestration only — no sub-orchestrator
  spawning in their docs.
- claude-flow/ruv-swarm's 3-tier stack (local/coordination/cloud) is nesting
  in spirit but is a fixed infrastructure hierarchy, not a dynamic
  orchestrator-of-orchestrators pattern chosen per-task.
- **negative**: no primary source in this sweep gives a quantified,
  coding-orchestrator-specific experience report on nesting depth (e.g. "we
  went 3 levels deep and X broke"). The failure-mode writeups that do exist
  are generic multi-agent-system commentary, not tied to any of the repos
  above:
  - Context: "at 4+ workers, the orchestrator frequently exceeds context
    limits" holding full history per worker; summarization is lossy and
    compounds per hop. (Beam.ai / Augment Code / Glukhov blog roundups)
  - Cost: decomposition + aggregation LLM calls stack on top of every worker
    call at each nesting hop; cited example of a $0.50 test workflow
    reaching "$50,000/month at 100K executions." (HackerNoon, "Why Modern
    Agent Orchestrators Fail at Cost Control")
  - Dynamic routing failure: "infinite handoff" loops (A→B→C→A) when no
    agent owns the task, cited as the "number one failure mode" in
    production guides.
  These should be read as general-pattern risk, not evidence about
  metaswarm or any specific project's actual nesting behavior.

## negative
- Could not find a primary-source, quantified account of nesting-depth
  experience (successes or breakage) from any of the coding-specific swarm
  projects themselves — only generic multi-agent-system commentary.
- claude-flow/ruv-swarm's actual scheduling internals (vs. marketing copy)
  were not pinned down to primary-source specificity in this pass; the V3
  "complete rebuild" issue suggests current docs may not reflect the
  shipping architecture.
- No project was found tying a complexity-scaled effort/token budget
  directly into its verify/review loop (only flat dollar or tool-call
  ceilings).

## leads
- opencode-swarm's scope-declaration + auto-serial-fallback-on-overlap is
  the most concrete "ready-set" file-conflict mechanism found — worth a
  closer look if a file-disjoint work-package detector needs a reference
  design.
- Claude Platform's native Task budgets primitive is unclaimed territory —
  no surveyed OSS orchestrator visibly consumes it yet.
- ruvnet/ruflo issue #945 (V3 rebuild) — architecture is churning; treat
  current claude-flow docs as provisional, revisit post-rebuild.
- awesome-agent-orchestrators (andyrewlee) and awesome-claude-code-toolkit
  (rohitg00) are curated indexes for a broader future sweep, not
  individually fetched in this pass.
