# Research: hierarchical orchestration precedent

**Axis:** design-pattern precedent (gate-selected, user pick)
**Date:** 2026-07-19
**Decision it informs:** adr_0002 — execution scheduling + recursive orchestration.
**Produced by:** hex-architect high run, researcher worker (fast-balanced).

## Direct answer

Every mature precedent — supervision trees, fork-join runtimes, DAG
schedulers, human merge hierarchies, 2025-2026 agent frameworks — converges on
three levers: (1) launch-on-dependency-ready beats wave barriers with no
correctness cost; (2) recursive fan-out is safe only when depth is hard-capped
and gated by a granularity threshold; (3) review/escalation scopes small at
the leaf and widens only on failure to resolve locally. The one internal
disagreement: review-hierarchy depth without matching reviewer capacity per
level becomes a bottleneck (Linux kernel lesson), not quality.

## Trends

Build/CI: one-directional barrier/BSP → DAG-native migration (GitLab needs,
GitHub Actions needs, Buck2 single graph vs Bazel phases); none reverted.
Agent frameworks: 2025-2026 mainstreamed graph-of-graphs hierarchy (LangGraph
subgraphs, Google ADK sub-agent trees, Claude workflows) — every shipping
implementation hard-caps recursion depth.

## Key findings

1. OTP/Akka supervision: Restart/Resume/Stop/Escalate; escalate is the
   exception path — most failures resolve at the immediate parent.
   https://getakka.net/articles/concepts/supervision.html ·
   https://www.erlang.org/doc/system/design_principles.html
2. ForkJoinPool/Cilk recurse only above a measured granularity threshold;
   below it sequential wins. https://www.baeldung.com/java-fork-join ·
   https://grokipedia.com/page/Cilk
3. Buck2 collapsed Bazel's phases into one incremental dep graph; GitLab/GH
   Actions `needs` start jobs the instant actual deps finish (worth 3-5 min
   per GitLab's numbers). https://buck2.build/docs/about/why/ ·
   https://docs.gitlab.com/ci/yaml/needs/
4. Linux kernel maintainer tree = closest human join-scoped-review precedent;
   counter-finding (ffwll "Maintainers Don't Scale"): deep hierarchy without
   reviewer capacity = overloaded bottleneck; the kernel's fix was widening
   trust (group maintainership), not more levels.
   https://docs.kernel.org/maintainer/pull-requests.html ·
   https://blog.ffwll.ch/2017/01/maintainers-dont-scale.html
5. Stacked-PR data: >1,000-line PRs get real review ~10% of the time, ~20x
   less scrutiny/line than <200 — quantitative case for tiny-loop-at-WP /
   panel-at-branch / swarm-at-end.
   https://www.awesomecodereviews.com/best-practices/stacked-prs/ ·
   https://graphite.com/guides/stacked-diffs
6. LangGraph: a compiled graph is callable, so hierarchy = same node shape
   recursively, subgraph state/checkpointing scoped to the subteam.
   https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025
7. AutoGen hierarchical chat exists to cut O(n²) pairwise messaging to ~O(n)
   via a mediating manager.
   https://microsoft.github.io/autogen/stable//user-guide/core-user-guide/design-patterns/group-chat.html
8. CrewAI hierarchical process hard-caps delegation via manager iteration
   limit; open issues show hierarchical delegation misbehaving in practice —
   cautionary. https://docs.crewai.com/en/learn/hierarchical-process ·
   https://github.com/crewAIInc/crewAI/issues/4783
9. Claude Code runs DIFFERENT depth caps per construct: subagents depth 5
   (deepest level loses the Agent tool); workflow self-nesting capped at 1 —
   the cap tracks what state/contract each construct carries
   (resumable/checkpointed → shallow; stateless workers → deeper). Rationale
   for the workflow cap is inferred from docs framing, not stated — treat as
   inference. https://code.claude.com/docs/en/sub-agents ·
   https://code.claude.com/docs/en/workflows
10. OpenAI Agents SDK: handoff (control transferred) vs manager/agent-as-tool
    (orchestrator keeps control, aggregates) are non-interchangeable; a hex
    sub-orchestrator is the manager shape.
    https://openai.github.io/openai-agents-python/multi_agent/

## Recurring structural rules (cross-domain invariants)

- Depth caps universal but never uniform — small fixed integers, different per
  construct, tied to each construct's failure mode.
- Depth cap and fan-out/resource cap are orthogonal levers — set both.
- A granularity floor gates recursive splitting; below it, sequential wins.
- Escalation/review scopes small by default, widens only on local failure —
  and each level's reviewable unit must stay small (per-WP summaries, not raw
  piles) or the level rubber-stamps.
- Barrier→DAG is the strongest, least-caveated finding: strict win, adopt.
- A sub-orchestrator is not a new type — the same orchestrator recursively,
  child state scoped so it can't leak upward.
- Manager/agent-as-tool, not handoff: one aggregated result to one join point.

## Recommendation

Adopt all three directions, wired by the invariants: DAG launch without
hedging; sub-orchestrator gated by granularity threshold + own depth cap
(pick by what state it carries) + scoped state + manager shape; hierarchical
review scaled to join size with the ffwll guardrail (capacity per level,
small reviewable units). Weakest evidence: the inferred workflow-cap
rationale (flagged in finding 9).
