# Research: nested execution tooling mechanics

**Axis:** technology/tooling (gate-selected, user pick)
**Date:** 2026-07-19
**Decision it informs:** adr_0002 — execution scheduling + recursive orchestration.
**Produced by:** hex-architect high run, researcher worker (fast-balanced).

## Direct answer

The ref-namespace collision is real and hard: branch `hex/plan/wp` blocks
`hex/plan/wp/sub` (refs are paths; a leaf can't also be a directory). Claude
Code's public Workflow docs expose no workflow-calls-workflow primitive
(`agent()`/`parallel()`/`pipeline()` only) — what nests is subagents (depth-5
hard cap). Recommendation: build within-WP fan-out on workflow primitives
inside the WP's single worktree/branch — no sub-branches ever needed.

## Constraints (hard, with evidence)

1. `refs/heads/hex/plan/wp` prevents `refs/heads/hex/plan/wp/sub`
   simultaneously ("cannot lock ref").
   https://dev.to/manojspace/how-to-fix-the-cannot-lock-ref-git-error-cg2 ·
   https://www.baeldung.com/ops/git-repo-structure-cannot-lock-ref
2. A branch can be checked out in only one worktree at a time.
   https://git-scm.com/docs/git-worktree
3. Subagent nesting depth 5, hard-coded, not configurable (v2.1.172+);
   depth-5 subagent has no Agent tool.
   https://code.claude.com/docs/en/sub-agents
4. Workflow run: ≤16 concurrent agents ("fewer on limited CPU" — no exact
   formula documented), 1,000 total per run.
   https://code.claude.com/docs/en/workflows
5. No mid-run user input to a workflow (only permission prompts pause).
6. Pause/resume caches only completed agents; in-flight restarts.
7. Workflow resume same-CLI-session only.
8. Subagent depth fixed at spawn time.
9. A fork can't spawn another fork.
10. Session subagent budget 200 default (`CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION`,
    v2.1.212+); workflow `agent()` calls exempt, but their own nested
    Agent-tool spawns count.

Caveat (orchestrator note): the harness running this session exposes a
one-level `workflow()` nesting primitive not found in the public docs the
researcher read — capability surface is version-volatile; design against the
capability class, not the primitive (consistent with adr_0001's churn rating).

## Choices (design freedom, with trade-offs)

1. Worktree-from-worktree works (resolves via $GIT_COMMON_DIR); keep worktrees
   as siblings under .agents/worktrees/ (tooling hygiene, not a git rule).
   https://www.jetbrains.com/help/idea/use-git-worktrees.html
2. Sub-branch naming under constraint 1: (a) hyphenated leaf
   `hex/<plan>/<wp>--<sub>`, never deeper slash path; or (b) no sub-branches —
   same worktree, disjoint files. (b) simpler, matches how workflows nest.
3. Within-WP fan-out implementation fork: (A) workflow primitives in the WP's
   one worktree/branch — no new refs, workflow budget, sidesteps collision;
   (B) Agent-tool spawns with isolation:'worktree' — triggers constraints
   1/2/3/10, burns session budget. (A) default; (B) only for true filesystem
   isolation needs.
4. Concurrent worktrees: no documented ceiling; cost ≈ checkout-size × count;
   sparse-checkout case study: 9.6GB → 3.7GB across 3 worktrees.
   https://gitcheatsheet.dev/docs/advanced/worktrees/disk-space-management/
5. Merge discipline: bors/homu (single stateful integration branch, test just
   before fast-forward, rollup batching) over GitHub merge queue — no hosted-CI
   dependency, plain git + hex's own verification.
   https://github.com/rust-lang/homu/blob/master/README.md ·
   https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue ·
   https://docs.mergify.com/merge-queue/batches/

## Cross-harness nesting (mid-2026)

Claude Code: depth 5, governed. Codex CLI: hard-coded depth 1 (subagents
can't spawn; open feature request openai/codex#9912).
https://codex.danielvaughan.com/2026/03/26/codex-cli-subagents-toml-parallelism/
OpenCode: NO depth limit — open runaway-nesting bug (anomalyco/opencode#18100).
A hex depth cap must be hex-enforced, not harness-inherited.

## Recommendation

Within-WP fan-out on workflow primitives inside the WP's single
worktree/branch (no sub-refs; documented budget; matches shipped reality).
Worktree-per-branch stays top-level-WP-only. True isolation need → sibling
worktree with hyphenated leaf branch, never deeper slash. Serialized merge:
bors/homu model — frozen-base integration branch, verify just before
fast-forward, re-parent next WP after land.
