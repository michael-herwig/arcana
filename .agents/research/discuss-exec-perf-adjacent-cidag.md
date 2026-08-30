# Research: DAG vs STAGE semantics in CI/workflow engines

## Metadata
Date: 2026-08-30
Expires: 2027-02-28

## Scope

Neutral evidence survey (no recommendation) on staged/wave-barrier execution
vs DAG/dependency-graph execution across CI and workflow engines: why DAG
support was added, measured effects, adoption friction, and failure-handling
differences.

## 1. GitLab CI: stages vs `needs:` (DAG)

**Mechanism.** Stages are a wave barrier: every job in stage N must finish
before any job in stage N+1 starts. `needs:` lets a job declare its actual
job-level dependencies and start as soon as those specific jobs finish,
ignoring stage order entirely. `needs: []` makes a job start immediately at
pipeline creation, bypassing stages altogether.
[GitLab Docs — Make jobs start earlier with needs](https://docs.gitlab.com/ci/yaml/needs/)

**Why it was added.** Tracked from a 2019-era GitLab issue: staged execution
means fast jobs in a stage wait on the slowest job in that same stage, and a
downstream stage waits on the whole upstream stage even if it only truly
needs one job from it.
[Out-of-sequence job execution using DAG MVC (#47063)](https://gitlab.com/gitlab-org/gitlab-foss/-/work_items/47063)

**Measured wall-clock effects (case studies, not controlled benchmarks).**
- 8 min → 5 min restructuring a full-stack pipeline from sequential stages
  into a DAG via `needs`.
- 25 min → under 6 min combining caching, DAG, parallel test splitting, and
  stage optimization together (DAG is one of several levers, not isolated).
- 14 min → under 3 min over 7 iterations.
  [How We Reduced Our GitLab CI Pipeline Duration by 70% at PION](https://cpcwood.com/blog/6-how-we-reduced-our-gitlab-ci-pipeline-duration-by-70-at-student-beans)
- `needs` on a `package-and-qa` job saved up to 26 minutes for QA branches;
  frontend tests starting as soon as the frontend build finished (rather than
  waiting for the whole build stage) saved ~3 minutes.
  [Let's make faster GitLab CI/CD pipelines](https://www.theodo.com/en-ma/blog/lets-make-faster-gitlab-ci-cd-pipelines)

General framing found repeatedly: with a DAG, wall-clock time collapses
toward the length of the slowest dependency chain rather than the sum of all
stage durations; total *compute* time is often unchanged — only wall-clock
drops. All figures above are self-reported blog case studies, not vendor
benchmarks or academic measurements — treat as directional, not a specific
multiplier to expect.

**Adoption friction / gotchas.**
- **Artifacts**: with `needs`, GitLab only downloads artifacts from the jobs
  explicitly listed in `needs` — not all prior-stage artifacts as under plain
  stages. A job whose needed output isn't listed silently fails from missing
  files. Recommended fix: `artifacts: false` on `needs` entries that are
  order-only (no artifact required).
  [Gitdash — Why is your pipeline still waiting on unrelated jobs?](https://gitdash.dev/blog/gitlab-pipeline-performance-needs-keyword)
- **Missing-job errors**: a `needs` entry naming a job that doesn't exist in
  the pipeline (e.g., pruned by `rules:`) fails pipeline *creation* unless
  marked `optional: true`.
- **Job-count limit**: a job's `needs` array is capped at 50 dependencies by
  default (self-managed instances can raise it); this was raised from an
  original limit of 5 in GitLab 12.3. Current docs state the default (50)
  without restating the history.
  [GitLab CI/CD limits](https://docs.gitlab.com/administration/cicd/limits/)
- **Cross-pipeline needs** (`needs: project` / `needs: pipeline`) are a
  different mechanism — they fetch artifacts or mirror pipeline status, not
  job-level ordering — and are easy to conflate with same-pipeline `needs`.
- **Visualization**: GitLab ships a dedicated "Needs" graph view distinct
  from the normal stage view; jobs with no `needs` relationships are omitted
  from it, which several sources flag as a source of confusion when a
  pipeline mixes staged and DAG jobs.
- **Internal complexity acknowledged by GitLab itself**: GitLab's own
  architecture design doc says the additive changes to pipeline YAML (stages,
  needs, rules, parallel, etc.) "caused some surprising behaviors in the
  pipeline processing logic," with keywords accumulating overlapping
  responsibilities over time.
  [Future of CI Pipeline Processing (GitLab handbook)](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/ci_pipeline_processing)

**Explicit case for staying with stages** (found as a general framing across
multiple secondary sources, not one canonical GitLab statement): linear
stages are simpler to teach and reason about; DAGs are worth the complexity
specifically when stage boundaries are hiding real parallel opportunity — a
small, already-obvious pipeline gets *harder* to read by adding `needs`
everywhere. Framed as "use DAGs to express true dependencies, not to show off
YAML knowledge."

## 2. GitHub Actions `needs`, Argo Workflows, Airflow/Dagster/Temporal

**GitHub Actions.** Jobs run in parallel by default; `jobs.<id>.needs` adds
an edge, and the whole set of jobs + needs edges forms a DAG that the runner
schedules. A job `needs`-ing a failed (or skipped) job is itself skipped by
default — skip/failure propagates forward through the whole downstream chain
from the failure point, not just the immediate consumer. This default is
overridable per job with `if: always()` (run regardless of upstream
outcome) or `if: failure()` (run only on upstream failure), and
`needs.<job>.result` exposes the specific upstream outcome for conditional
logic.
[GitHub Docs — Using jobs in a workflow](https://docs.github.com/actions/using-jobs/using-jobs-in-a-workflow)

**Argo Workflows: DAG template vs Steps template.**
- *Steps*: outer list = sequential stages, inner list = parallel-within-stage
  — functionally the same wave-barrier model as GitLab stages.
- *DAG*: each task declares its own `dependencies:`; tasks with no
  dependency in common run in maximum parallel, independent of any notion of
  stage.
- **Failure semantics differ by default and are configurable in both**: a
  DAG's default `failFast: true` means once one task fails, no *new* tasks
  are scheduled, though already-running tasks are allowed to finish before
  the DAG is marked failed. Setting `failFast: false` lets all branches run
  to completion regardless of failures elsewhere in the graph — closer to
  Airflow's `trigger_rule=all_done`. Steps templates can express controlled
  failure handling too (via `continueOn`/exit-status conditionals), so the
  DAG/Steps choice is not itself a failure-handling tradeoff — it's
  orthogonal, both need explicit configuration to deviate from "stop on first
  failure."
  [Argo Workflows — DAG walkthrough](https://argo-workflows.readthedocs.io/en/latest/walk-through/dag/),
  [Argo Workflows — Retries](https://argo-workflows.readthedocs.io/en/latest/retries/)

**Airflow.** Pure task-DAG scheduler: a task's `trigger_rule` decides whether
it runs given its upstream tasks' outcomes (default `all_success`). Skipped
tasks *cascade* through `all_success`/`all_failed` trigger rules — a
skipped upstream produces a skipped downstream by default — but a rule of
`all_done` breaks that cascade and runs regardless of upstream success,
failure, or skip. This is the mechanism Airflow users reach for to emulate
"run cleanup/notify regardless," and is explicitly documented as easy to
misuse after a branching operation (`all_success`/`all_failed` downstream of
a branch is called out as almost always wrong).
[Astronomer — Manage task and task group dependencies](https://www.astronomer.io/docs/learn/managing-dependencies)

**Dagster vs Airflow.** Not a stage-vs-DAG distinction so much as
task-DAG vs asset-DAG: Airflow's graph nodes are *tasks* ("do this, then
that"); Dagster's nodes are *assets* (the data artifacts, with tasks implicit
in how assets are produced). This matters for the failure/retry granularity
angle: Dagster retries and partial-materializes at the asset/partition level,
and rematerializing one asset naturally recomputes just its downstream
assets — closer to a fine-grained, resumable DAG than Airflow's
whole-task-rerun model. (Sourced from vendor/comparison blogs, not neutral —
Dagster's own blog is among the sources, so treat the framing as
Dagster-favorable marketing language even though the underlying
asset-vs-task distinction is accurate.)
[Dagster — Building with Dagster vs Airflow](https://dagster.io/blog/building-with-dagster-vs-airflow)

**Temporal.** Not a DAG-of-tasks model at all — workflows are ordinary code
(sequential/branching/looping), and "dependencies" are just program order
plus explicit `Promise`/`await` composition, not a declared graph. Failure
handling is per-Activity via a `RetryPolicy` (backoff, max attempts), with a
sharp distinction between a *Workflow Task Failure* (retried transparently)
and a *Workflow Execution Failure* (only certain typed failures propagate to
fail the whole workflow). This is a materially different execution model
from GitLab/GitHub/Argo/Airflow's declared-graph approach — worth flagging
if the parent discussion's DAG/STAGE framing gets generalized to "all
workflow engines," since Temporal doesn't fit either bucket cleanly.
[Temporal — Retry Policies](https://docs.temporal.io/encyclopedia/retry-policies),
[Temporal — Failures reference](https://docs.temporal.io/references/failures)

## Cross-cutting pattern on failure handling

Across every DAG-capable system surveyed (GitLab needs, GitHub Actions needs,
Argo DAG, Airflow), the *default* is fail-fast/stop-propagation: a failure
stops new downstream scheduling and cascades as failure or skip to
dependents. Every one of them also ships an explicit opt-out
(`optional:`/`if: always()`/`failFast: false`/`trigger_rule=all_done`) for
"run regardless." None of the surveyed systems make "run downstream
regardless of upstream failure" the default — this is the strongest and most
consistent finding across the whole search. Staged/wave-barrier execution's
usual defense is exactly this same default behavior (stop the wave on
failure) achieved with zero configuration, since there's no per-edge
override to reach for in the first place.

## negative

- Could not find a rigorous, apples-to-apples benchmark (academic or vendor)
  quantifying DAG vs staged wall-clock savings — every number found is a
  single team's self-reported blog case study, often bundling DAG adoption
  with caching and test-splitting changes in the same before/after, so the
  DAG-specific contribution is not isolated in any source.
  [GitLab CI Parallel Jobs Guide (Markaicode)](https://markaicode.com/benchmarks/gitlab-ci-production-benchmark-latency/)
  is titled as a benchmark but reads as another blog-style writeup, not a
  controlled study.
- Could not confirm the *current* self-managed-configurable ceiling for
  GitLab's `needs` limit beyond "default 50" — the official `needs` docs
  page itself doesn't restate the limit (it lives on the separate CI/CD
  limits page), and no source gave a definitive "as of GitLab X.Y this
  changed again" beyond the 5→50 change in 12.3.
- Did not find a canonical, single-source GitLab (or Argo/GitHub) statement
  explicitly "defending" staged execution — the readability/simplicity case
  for stages is consistently a third-party blog framing (oneuptime.com
  and similar SEO-content sites appear disproportionately across every
  query), not a first-party engineering rationale. Treat the "stages are
  simpler to teach" argument as widely-repeated received wisdom rather than
  a documented design decision from any vendor.
- Argo Workflows official docs did not directly contrast DAG vs Steps
  failure semantics in one place — that comparison had to be assembled from
  the DAG walkthrough page plus the separate Retries page; no first-party
  page states the "orthogonal, not a tradeoff" conclusion drawn above in
  those words (that synthesis is mine, flagging it as such).

## leads

- GitLab's own "Future of CI Pipeline Processing" design doc (handbook link
  above) is a first-party admission of YAML/keyword complexity accumulation
  — worth a deeper read if the discussion wants GitLab's internal reasoning
  about why the current stage+needs model is being reconsidered.
- Kubernetes-native workflow engines beyond Argo (Tekton pipelines, which
  also has an explicit `runAfter`/DAG model) were not covered — same
  fail-fast-by-default pattern is likely but unverified here.
- AWS Step Functions / GCP Workflows retry/catch semantics came up only
  tangentially (via a Temporal comparison article) — not independently
  verified against their own docs.
- The asset-DAG framing (Dagster) vs task-DAG framing (Airflow/GitLab/GitHub)
  might be the more interesting axis for a CI-specific discussion than
  DAG-vs-stage: none of the CI systems (GitLab/GitHub/Argo) have an
  asset-level model, only a job/task-level one.
