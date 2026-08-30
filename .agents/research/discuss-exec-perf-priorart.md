# Research: Execution-performance prior art for staged vs DAG scheduling, verification scoping, review scoping, and hierarchical orchestration

## Metadata

- Date: 2026-08-30
- Expires: 2027-02-28
- Sources: see per-axis citations below

## Scope

Neutral evidence gathering (no recommendation) across four axes relevant to designing hex's execution/review pipeline: (1) staged/phased vs DAG task scheduling, (2) run-everything vs selective verification, (3) whole-change vs delta-only incremental review, (4) hierarchical sub-orchestration with nested local verify loops.

---

## Axis 1 — Task scheduling: staged/phase (barrier) vs ready-set DAG dispatch

### For DAG dispatch (each task starts when its deps finish)

- **Bazel**: builds a DAG of actions; if 500 compile actions have no interdependency, all run concurrently — no artificial phase barrier. Granularity matters: Maven's coarser (module-level) compilation units reduce achievable parallelism vs Bazel's finer (package-level) units, but too-fine granularity adds synchronization overhead. ([gocodeo.com](https://www.gocodeo.com/post/how-bazel-works-dependency-graphs-caching-and-remote-execution), [arxiv.org/2405.00796](https://arxiv.org/html/2405.00796v1))
- **Buck2**: single incremental dependency graph "avoiding any phases," explicitly designed so eliminating phase boundaries "increases parallelism." DAG-acyclicity is required specifically to build independent subgraphs concurrently. ([tweag.io](https://www.tweag.io/blog/2023-07-06-buck2/), [buck2.build/why](https://buck2.build/docs/about/why/))
- **GitLab CI `needs:`**: lets jobs bypass stage boundaries; GitLab's own docs/blog state DAG pipelines are "often faster" because "a job in a particular stage waits for the previous stage to complete only for semantic reasons – it could already run in parallel from a purely technical perspective." ([about.gitlab.com/directed-acyclic-graph](https://about.gitlab.com/blog/directed-acyclic-graph/), [oneuptime DAG guide](https://oneuptime.com/blog/post/2025-12-21-dag-gitlab-ci/view))
- **GitHub Actions**: jobs run in parallel by default; `needs:` is the *only* ordering primitive, making the full dependency graph explicit and enabling fan-out/fan-in and diamond patterns that a linear stage list cannot express. ([datadef.io](https://datadef.io/guides/en/living-diagram-from-github-actions), [oneuptime job-deps guide](https://oneuptime.com/blog/post/2025-12-20-job-dependencies-github-actions/view))
- **Nx / Turborepo**: both compute a task graph from project/package dependencies and execute with "maximum parallelism" rather than fixed stages; Nx's graph is more fine-grained (file-level import edges, not just package edges), which both increases achievable parallelism and correctness of the affected-set. ([nx.dev/nx-vs-turborepo](https://nx.dev/docs/kb/nx-vs-turborepo))

### Against DAG dispatch / for staged (barrier) execution

- **Debuggability**: "A linear chain's execution log is a list while a DAG's execution log is a graph" — DAGs are harder to trace visually and require dedicated observability tooling (execution-path rendering) to be tractable at scale; this investment "is not optional at production scale." ([tianpan.co](https://tianpan.co/blog/2026-04-10-dag-first-agent-orchestration-linear-chains-scale))
- **Teachability / simplicity**: GitLab's own stageless-pipelines post concedes "linear stages are easier to teach" and recommends choosing "the simplest dependency model that matches the system you operate" — i.e., don't reach for DAG semantics by default. ([about.gitlab.com/stageless-pipelines](https://about.gitlab.com/blog/stageless-pipelines/))
- **Implementation/config complexity**: GitLab's `needs:` DAG model carries real gotchas — a default cap of 5 (configurable to 50) needs per job, a requirement that all `needs:`-using jobs still declare stages, no same-stage dependencies (to avoid cycles), artifact access restricted to only the needed jobs, and silent no-ops when a needed job doesn't exist due to `only/except` rules. Each is a sharp edge staged execution doesn't have. ([oneuptime needs-keyword guide](https://oneuptime.com/blog/post/2025-12-21-gitlab-ci-needs-keyword/view), [gitlab-foss #66680](https://gitlab.com/gitlab-org/gitlab-foss/issues/66680))
- **Failure isolation is genuinely two-sided**: staged execution gives *simple* debugging (whole stage stops, blast radius is legible) but *worse* failure isolation (one failure blocks everything behind the barrier, even independent work); DAGs give better failure isolation (independent branches keep progressing) but *harder* debugging (need graph-aware tooling to see what's blocked vs progressing vs failed). Neither dominates on this dimension — it's a real trade, not a strict win. ([tianpan.co](https://tianpan.co/blog/2026-04-10-dag-first-agent-orchestration-linear-chains-scale))

### Agent-orchestration frameworks (LangGraph / CrewAI / AutoGen)

- **LangGraph**: explicit graph-based workflow, conditional edges, parallel branches — closest analogue to DAG dispatch; built-in checkpointing/time-travel state management. Positioned for "production-grade state management," mission-critical systems.
- **CrewAI**: role-based, "sequential or parallel" process types — supports both models depending on configured process, not DAG-native by default.
- **AutoGen**: conversation-driven (GroupChat), not graph-scheduled — ordering emerges from conversation flow rather than declared dependencies, the least DAG-like of the three.
- No source found offering head-to-head throughput/wall-clock benchmarks between these frameworks' scheduling models specifically (as opposed to general framework comparisons). This is a gap. ([datacamp.com](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen), [dev.to comparison](https://dev.to/pockit_tools/langgraph-vs-crewai-vs-autogen-the-complete-multi-agent-ai-orchestration-guide-for-2026-2d63))

**negative**: Did not find any source arguing staged execution is *faster* in wall-clock terms than DAG dispatch when real parallelism exists in the dependency structure — every build-system source treats phase barriers as a pure efficiency cost paid for simplicity, never as a performance advantage in its own right. The only performance-flavored counterargument found is indirect: fine-grained DAG scheduling can *lose* to coarser staging if the granularity is too fine and synchronization/dispatch overhead dominates (the Bazel-vs-Maven granularity point) — i.e., DAG dispatch's advantage is conditional on the graph being coarse enough that per-node overhead doesn't eat the parallelism gain.

---

## Axis 2 — Verification scoping: run-everything vs selective/test-impact analysis

### Evidence for selective testing (with mitigations)

- **Meta's Predictive Test Selection** (arXiv:1810.05286 / engineering.fb.com 2018): ML-learned selection from historical test-outcome data. In production it **cut testing infrastructure cost by ~2x while still surfacing >95% of individual test failures and >99.9% of faulty changes** — i.e., selective testing accepted a small, quantified, and deliberately bounded miss rate in exchange for large cost savings. ([research.facebook.com](https://research.facebook.com/publications/predictive-test-selection/), [engineering.fb.com](https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/))
- **Google TAP / "Taming Google-Scale Continuous Testing"** (Memon & Gao, ICSE-SEIP 2017, analyzing 500K+ CLs / 5.5M test targets / 4B+ test outcomes): found "very few tests ever fail," failures cluster near the changed code, and certain hot files/users/tools predict breakage — supporting running low-signal tests less often as a resource-saving strategy, with the finding itself functioning as the safety argument (rare-failing tests are rare-failing empirically, not just assumed). ([research.google](https://research.google/pubs/pub45861/))
- **Chromium's Regression Test Selection (RTS) / CQ**: runs a subset at CQ+1 (dry run) chosen by change-file/test-file co-change frequency and file-graph distance; explicitly runs the *skipped* tests at CQ+2 to guarantee 100% eventual coverage. Also has an automatic backstop: if no reusable RTS-enabled build exists within a 24-hour window, it falls back to compiling and running **all** tests as if RTS didn't exist. This is a clean two-tier "fast selective gate + full-coverage backstop" pattern. ([chromium docs](https://chromium.googlesource.com/chromium/src/+/112.0.5615.165/docs/testing/regression-test-selection.md))
- **Nx affected**: computes a project graph (including file-level import edges) to select impacted projects/tasks; documented as capable of keeping PR feedback loops under 10 minutes "while still covering the actual risk surface" *when the impact analysis is accurate*. ([itnext.io deep dive](https://itnext.io/deep-dive-into-nx-affected-b3c29c715d41))
- **pytest-testmon**: file/fixture-level dependency tracking for Python; the tool's own docs/blog are explicit that non-literal `request.getfixturevalue(expr)` calls are handled conservatively (treated as depends-on-everything-in-scope, so never silently missed there) — but plain function calls with no fixture/conftest involvement, data files, env vars, external services, and other non-Python inputs **are** invisible to the analysis and can cause a real miss. The project's own recommended mitigation is "run the full suite on main branches" — i.e., selective locally/on-PR, full on the branch that matters most. ([testmon.org/hidden-test-dependencies](https://www.testmon.org/blog/hidden-test-dependencies/), [github.com/tarpas/pytest-testmon](https://github.com/tarpas/pytest-testmon))
- **Bazel-diff / target-determinator**: reverse-dependency (`rdeps`) queries between two git revisions to compute affected targets; documented edge cases requiring extra handling — BUILD/Starlark files aren't tracked by `bazel query` itself, so added/deleted BUILD files and modified `.bzl` files need special-cased "run everything downstream" handling to avoid false negatives. ([groups.google.com/bazel-discuss](https://groups.google.com/g/bazel-discuss/c/I9udqWIcEdI), [github.com/Tinder/bazel-diff](https://github.com/Tinder/bazel-diff))

### Standard mitigation pattern across all of the above

Every real-world selective-testing system pairs selection with a **backstop**: Meta bounds the miss rate statistically and monitors it; Chromium runs skipped tests at the next tier and falls back to full-run when the incremental base is stale; Nx/Bazel tooling special-cases the file types their static analysis can't see and routes those to "run everything." None of the surveyed systems trust selection alone with no full-run safety net.

**negative**: The clearest counter-evidence is pytest-testmon's own admission that plain-function-call dependencies (no fixture involved) are simply not tracked — this is a real, not just theoretical, escape class, and the tool's own remediation is "don't rely on selection alone on your main branch." This is the strongest single piece of evidence *against* selective-only verification in the set gathered. Also notable: none of the sources found gave a general-purpose quantified "escape rate" for test-impact analysis as a category (only Meta's specific number, which is for their specific ML model, not a general bound) — treating any specific escape-rate figure as generalizable beyond its source system would be an overreach.

---

## Axis 3 — Incremental review scoping: delta-since-last-review vs whole-change-each-round

### How real systems handle it

- **Gerrit**: patch sets are versioned per change; the review UI's "Diff Against" dropdown lets a reviewer pick *any* earlier patch set as the diff base (not just "last reviewed"), and "Show Diffs" surfaces the delta for the currently selected pair. This makes delta-review a deliberate reviewer choice, not the only mode — full-change view is always one click away. ([gerrit-review.googlesource.com/patch-sets](https://gerrit-review.googlesource.com/Documentation/concept-patch-sets.html), [user-review-ui](https://gerrit-review.googlesource.com/Documentation/user-review-ui.html))
- **GitHub PRs**: "view changes since last review" is an explicit, named feature for skipping already-reviewed content. Documented rough edges: (a) it doesn't appear on your own review of your own PR after adding changes (an access/ownership gap, not a correctness one); (b) separately, GitHub's default PR diff is a **three-dot diff** (comparing tip-of-branch against the merge-base at last sync with target, not a true two-dot diff against target's current head) — community discussion flags this as capable of hiding target-branch drift from reviewers, independent of the since-last-review feature. ([github community discussion #7645](https://github.com/orgs/community/discussions/7645))
- **Graphite stacked diffs**: each diff in a stack is reviewed independently/in parallel; tooling shows "which diffs need re-review due to changes in their parent diffs" and auto-rebases children when a parent changes. This is the closest analogue to a formal backstop for delta-review's blind spot: dependency-aware re-review triggering rather than a stale, disconnected delta.

### Documented miss classes / backstops

- **Cross-delta interaction**: no source directly documented a named "cross-stack bug class" from independently-reviewed stacked diffs; the strongest indirect evidence is the *prescribed mitigation* pattern itself — "keep diffs small, single-coherent-change, test each layer independently" — which is advice that exists precisely because interactions between diffs are a known risk, even though no source quantified it. This is a genuine evidence gap, not a confirmed non-issue.
- **GitHub's 3-dot-diff base-drift issue** is the most concrete, named miss class found across all three tools: a delta-scoped review can look clean while silently omitting changes that landed on the target branch since the PR's merge-base, because the diff being reviewed is against a stale base, not current target HEAD.

**negative**: Found no source with an empirical count/rate of bugs that escaped specifically because reviewers only saw the delta rather than the whole change (as opposed to bugs that escaped due to reviewer inattention generally). All evidence here is structural/anecdotal (documented UI quirks, prescribed best practices) rather than measured miss rates — noticeably weaker evidentiary base than axis 2's testing literature.

---

## Axis 4 — Hierarchical orchestration: nested sub-orchestrators with local verify loops

### Cost side (evidence overhead can dominate)

- **Anthropic's multi-agent research system** (single documented case study with real numbers): multi-agent systems use **~15× more tokens than simple chat interactions**, and agents generally ~4×; the team's own framing is that this burn rate is only justified "where the value of the task is high enough to pay for the increased performance." Early failure modes included agents "spawning 50 subagents for simple queries" and subagents "distracting each other with excessive updates" — coordination overhead manifesting as literal wasted work, not just latency. Notably, **this architecture is single-level** (lead + subagents, no further nesting) — no data point here on multi-level hierarchies specifically. ([anthropic.com/engineering/multi-agent-research-system](https://www.anthropic.com/engineering/multi-agent-research-system))
- **Hierarchical manager-worker breakdown estimate**: decomposition + result-synthesis by the manager "accounts for 15-20% of total time" in surveyed hierarchical systems — a concrete (if source-unverified-primary) figure for pure coordination tax. ([kore.ai](https://www.kore.ai/blog/choosing-the-right-orchestration-pattern-for-multi-agent-systems) via search synthesis)
- **Latency compounding with depth**: a 3-level hierarchy with ~2s LLM calls per level adds a minimum ~6s of pure coordination latency before any worker starts — and summarization between levels is lossy (a mid-level supervisor's summary to the top can drop details later needed for the final decision). ([emergentmind.com](https://www.emergentmind.com/topics/hierarchical-multi-agent-orchestration))
- **Practical depth-limit consensus** (opencode/Claude-Code-ecosystem discussion, not peer-reviewed but converging across multiple independent sources): default max spawn depth is commonly capped at 3, with explicit guidance that "depth 2 is practical for most use cases... going deeper typically indicates architectural problems" — each extra level multiplies token spend (a 3×3×3 fan-out reaches 27 concurrent leaf agents), and one source frames it plainly: "once it goes any further than that, it's usually an indication of a problem." A separate general-multi-agent finding: beyond some group-size/topology threshold, "communication overhead outweighs any collective intelligence gains" — a tipping point rather than smooth diminishing returns. ([github.com/anomalyco/opencode #2906](https://github.com/anomalyco/opencode/issues/2906), [#18100](https://github.com/anomalyco/opencode/issues/18100))

### Benefit side / conditions where nesting pays off

- Anthropic's case study: parallel tool calling (a shallow, single-level form of the pattern) **cut research time up to 90%** for complex queries and produced a 90.2% quality improvement over single-agent — but this is the *shallow* (one level) case, and the source is explicit that the technique is reserved for high-value tasks precisely because of the token cost, not applied by default.
- Hierarchical scaling claim: systems can scale roughly logarithmically because each manager handles a bounded span of subordinates, so *total* coordination overhead grows sub-linearly with worker count — this is presented as a structural argument for hierarchy at scale, distinct from (and not contradicting) the per-additional-level tax above. The two effects compound differently: adding workers under a fixed hierarchy depth is cheap; adding a depth level is what multiplies cost.
- **AdaptOrch** (arXiv:2602.16873) argues that as underlying models converge in raw capability, "orchestration topology... now dominates system-level performance over individual model capability" — a claim that nesting/topology choices matter more than they used to, without itself resolving how deep is too deep.

**negative**: No source found gives a rigorously measured "effective depth limit" for multi-agent *coding* systems specifically (as distinct from general orchestration or Claude-Code-tool-ecosystem folk consensus) — the depth-2-to-3 guidance is practitioner consensus from GitHub issue discussions and blog commentary, not a controlled study. The 15-20% synthesis-overhead figure and the "6 seconds minimum latency" figure both trace to secondary/blog-level sources (emergentmind.com, kore.ai) rather than a primary paper — treat as illustrative, not load-bearing.

---

## Leads (adjacent research lanes worth a follow-up)

- **AdaptOrch (arXiv:2602.16873) full paper** — orchestration-topology-dominates-model-capability claim deserves a direct read; could bear on whether hex's own tiering (low/medium/high) should key off topology choice rather than model capability.
- **Chromium's "Quick Run" (QR)** — described as "more granular than the conventional build dependency graph technique" for regression test selection; a follow-up read of `docs/cq_quick_run.md` could surface a finer-grained selection model than plain rdeps/affected-graph approaches already covered here.
- **Cross-stack-diff bug empirical study** — axis 3's weakest evidence gap (no quantified miss class for stacked/delta review); worth a targeted search for engineering blog postmortems (Meta/Google monorepo review-tooling teams) rather than general Graphite/GitLab marketing content.
- **Google's internal multi-level agent/build orchestration** (if anything is public) — all depth-limit evidence gathered is from smaller open-source agent frameworks (opencode) or a single-level Anthropic case study; a large-scale production multi-level system (if documented anywhere) would be a stronger data point than the current practitioner-consensus evidence.
- **Bazel/Buck2 remote-execution scheduler internals** — this pass covered the DAG-vs-stage conceptual model but not the actual scheduler algorithm (queueing, priority, resource-aware dispatch) that decides *which* ready node runs first when many become ready simultaneously — relevant if hex's DAG dispatch needs a concrete dispatch-order policy.
