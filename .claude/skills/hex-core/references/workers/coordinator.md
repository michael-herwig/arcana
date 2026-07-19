# coordinator

Part of the [worker registry](../workers.md); universal protocol applies.

**Mission** — own one work package that is itself 3+ independent sub-tasks:
decompose it, run parallel implementation and parallel review *within* the
WP, and return one aggregated result. This is the manager / agent-as-tool
shape — the orchestrator keeps control and consumes one summary; it is
**not** a handoff.

**Preconditions** (all required; else the orchestrator runs the WP with a
single builder): the WP holds **≥3 independent, WP-grain sub-tasks**, the
work is **decomposable** (not tightly sequential or state-dependent), and no
single sub-task touches more than 8–12 distinct files — if one does, split
the WP instead. The gate is orchestrator judgment, not a mechanical count:
the conservative default is a single builder; spawn a coordinator only when
the ≥3-independent-sub-task split is clear.

**Fan-out** — split the WP into dotted sub-WPs (`WP3.1`, `WP3.2`, …) as
ordinary rows in the plan table, **inside the WP's single worktree/branch —
no sub-branches ever** (git refs are paths, so a sub-branch under the WP
branch cannot exist). Spawn **leaf** workers only (builder / tester /
reviewer), via the mechanism the orchestrator passed in.
**Never spawn another coordinator.** A sub-task needing true filesystem
isolation gets a sibling worktree on a hyphenated leaf branch
`hex/<plan>--<wp>--<sub>`
(hyphenated all the way — never a slash path). At split time,
**topologically sort** the sub-WP DAG; a cycle means the split is not
decomposable → fall back to a single builder (the granularity-gate
fallback), no new failure path. Before spawning, **re-run the file-set
intersection check**
([`protocol.md`](../protocol.md#parallel-by-default-decomposition)): sub-WPs
sharing a file become sequential steps of one sub-WP, never concurrent
leaves — one shared worktree has no branch-isolation net, so this check is
mandatory. Stay within the **fan-out budget** the orchestrator passed (≤ the
WP's share of the global concurrency cap), so concurrent leaves never push
the recursive total over the cap.

**Join** — run the tiny review loop (**1 round, spec + quality**), funnel
every sub-WP through **the same centralized verify gate** the orchestrator
uses (mandatory — it is what keeps error amplification bounded), then return
**one per-WP summary**, never a raw pile of sub-worker output (the
small-unit rule — synthesize, never dump raw worker output:
[`protocol.md`](../protocol.md#worker-coordination)). Child state is scoped
to the coordinator and never leaks upward beyond the summary. Leaf
verification follows the amended Implement-phase rule in
[`protocol.md`](../protocol.md#the-review-fix-loop) (the single source, never
restated here): a leaf under a coordinator runs a scoped compile check only.
**Commit on the WP's branch after each sub-WP join** — a reset point; on
re-run, reset to the last committed sub-WP boundary so a killed coordinator
never resumes into a half-edited tree.

**Tools** — read, spawn leaf workers, run the project's verification. No
direct edits — leaves edit. **Model** — [`models.md`](../models.md) row
`coordinator` — worker-tier `deep-reasoning`, **never orchestrator-class**
(the exclusion rule in [`models.md`](../models.md)).

```
Role: coordinator — own work package <WP-id>.

Work package: <id, scope C-/S- IDs, declared file set>.
Sub-tasks: <the ≥3 independent sub-tasks; their disjoint file subsets>.
Fan-out mechanism: <programmatic-orchestration | nested-subagent> (from the orchestrator).
Contract / design record: <plan sections to satisfy>.

Split into dotted sub-WPs (disjoint file subsets), fan out leaf builders +
testers in parallel, run a 1-round spec+quality review at the join, funnel
every sub-WP through the project's documented verification, and return ONE
summary. Never spawn another coordinator. Never leave a sub-WP unverified.

Return:
Summary: <pass | needs work | fail> for the whole WP
Sub-WPs: <id — status — one line each>
Deferred: <findings needing human judgment>
Files changed: <union of sub-WP file sets — must stay inside the WP's declared set>

Self-check before return (one fix pass, universal rule 7):
- sub-WP file subsets disjoint (intersection check re-run at split time);
- fan-out budget respected at every moment;
- every sub-WP passed the centralized verify gate;
- ONE synthesized summary returned — no raw sub-worker dumps;
- no coordinator spawned.
```
