# Research: hierarchical execution performance

**Axis:** performance & scale (gate-selected, user pick)
**Date:** 2026-07-19
**Decision it informs:** adr_0002 — execution scheduling + recursive orchestration
(wave-barrier → DAG pipeline, sub-orchestrator role, join-scoped review hierarchy).
**Produced by:** hex-architect high run, researcher worker (fast-balanced).

## Direct answer

Barrier waves and single-writer serial merges are the *safe default*, not a
naive one: coordination cost grows superlinearly with fan-out (USL crosstalk
term quadratic in N; a Dec-2025 Google preprint measures coordination turns
scaling N^1.7 and error amplification up to 17.2x for uncoordinated parallel
agents). DAG-driven launch is close to a free win — coordination cost
unchanged, only the wait discipline changes. Sub-orchestrator recursion and
larger review panels pay off only above concrete granularity thresholds and go
*negative* on tightly sequential work or once a single agent is already capable.

## Key findings

1. **Barrier vs dataflow.** GitLab `needs` DAG pipelines start a job when its
   actual deps finish, not its stage (https://docs.gitlab.com/ci/yaml/needs/;
   https://oneuptime.com/blog/post/2025-12-21-dag-gitlab-ci/view). Bazel:
   build time bounded below by the critical path regardless of parallelism;
   profiler quantifies per-node "drag"
   (https://blog.bazel.build/2022/11/15/build-performance-metrics.html;
   https://blog.bazel.build/2019/02/01/dynamic-spawn-scheduler.html). BSP
   theory names the straggler problem; standard fixes (SSP, Elastic BSP) all
   relax the barrier, not the parallelism (https://arxiv.org/pdf/2308.15482;
   https://link.springer.com/article/10.1007/s10994-021-06064-w).
2. **Coordination laws.** USL C(N) = N / (1 + α(N−1) + β·N(N−1)): α linear
   contention, β quadratic coherence/crosstalk
   (http://thinkmicroservices.com/blog/2019/laws-of-scalability.html). Single
   serializing coordinator: average wait ~N/2 flows (Little's Law)
   (https://blog.acolyer.org/2015/04/29/applying-the-universal-scalability-law-to-organisations/).
   Direct model for hex's serialized merge+verify gate: bounding fan-out per
   join is the correct structural mitigation.
3. **Fork-join granularity.** ForkJoinPool: task worth forking at ~100–10,000
   basic steps; surplus-queued-task heuristic ~3
   (https://kar.kent.ac.uk/63829/1/pppj14-dewael-et-al-forkjoin-parallelism-in-the-wild.pdf;
   https://docs.oracle.com/javase/8/docs/api/java/util/concurrent/ForkJoinTask.html).
4. **Multi-agent empirical (2025-2026).**
   - Anthropic multi-agent research system: ~15x tokens of a chat turn, ~4x a
     single agent; Opus-lead+Sonnet-subagents beat single Opus by 90.2% on
     breadth-first research; wall-clock cut up to 90%; but coding named a poor
     fit — fewer truly parallelizable tasks
     (https://www.anthropic.com/engineering/multi-agent-research-system).
   - Google preprint "Towards a Science of Scaling Agent Systems"
     (https://arxiv.org/html/2512.08296v1): coordination turns
     T = 2.72×(n+0.5)^1.724; error amplification 1.0x single → 4.4x
     centralized → 5.1x hybrid → 7.8x decentralized → 17.2x independent;
     single-agent baseline >~45% accuracy → negative returns from adding
     agents (β=−0.408, p<0.001); 16-tool benchmark: 6.3x efficiency collapse
     in multi-agent mode (0.466 → 0.074 success/token); message density
     plateaus ~0.39 msg/turn. Non-peer-reviewed — exponents directional.
   - Stanford (https://arxiv.org/abs/2604.02460): under equal thinking-token
     budgets, single-context beats multi-agent on sequential/dependent
     reasoning; multi-agent earns keep only when one context can't hold the
     task or strictly more compute is spent.
   - Self-consistency scaling (https://arxiv.org/html/2511.00751v2): bulk of
     gain by N=5–10 same-kind samples, flat by 20–40, at 40–64x compute;
     noise can hurt past plateau. IID sampling — understates heterogeneous
     (role-differentiated) review value, right shape for same-role scaling.
5. **Merge serialization.** Bors sequential: 15-min CI caps 4 merges/hour;
   Google TAP fixes via batching + parallel validation
   (https://graphite.com/blog/bors-google-tap-merge-queue — also: 30→40
   merges/day = 70% cost increase for 33% traffic, nonlinear). Async queue
   submission ≈ 2x less human attention
   (https://matklad.github.io/2023/06/18/GitHub-merge-queue.html).

## Decision thresholds (citable in the ADR)

- **DAG launch:** adopt when >~30% of a wave's WPs have zero dependency on the
  wave's slowest WP (reasoned estimate); below that, scheduling complexity not
  worth it. Otherwise near-free upgrade — dependency data already in the plan.
- **Sub-orchestration gate:** only when a WP contains ≥3 independent,
  WP-grain-sized sub-tasks AND the work is decomposable (not tightly
  sequential/state-dependent — the regime where single-agent wins under equal
  budget). Spawn overhead (4–15x tokens) dominates below that grain.
- **Reviewers:** diminishing returns after ~5 same-kind; grow role/model
  diversity, not count. hex's 5-role panel is near the sweet spot.
- **Skip fan-out entirely:** single agent already ~45%+ success on the task
  class, or WP touches >8–12 distinct tools/files → split WPs smaller instead
  of adding agents.
- **Merge batching:** serialize-and-revalidate fine at current scale; batch
  file-disjoint WPs into one merge+revalidate pass only if ready-WPs queue
  faster than the gate drains (bors-ceiling regime).
- **Structural rule for any recursion:** every sub-orchestrator funnels
  through the same centralized verify gate as top-level waves — empirically
  the difference between 4.4x and 17.2x error amplification.

## Recommendation

Adopt DAG-driven launch (strict improvement, no new coordination risk). Be
conservative on recursion: gate sub-orchestration behind the ≥3-independent-
WP-sized-sub-tasks rule, centralized verify mandatory. Keep the review
panel's role-diversity model rather than growing same-role count.
