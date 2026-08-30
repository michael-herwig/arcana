# Research: Operability of DAG task execution and checkpointed verification

## Metadata
- Date: 2026-08-30
- Expires: 2027-02-28
- Sources: see below (each claim cited inline)

## Direct answer

DAG runners (GitHub Actions, GitLab CI, Airflow, Argo, Bazel/Buck2) converge on the
same operability lesson: **compute the failure blast radius explicitly and eagerly,
never let it emerge from per-node trigger-rule propagation** — every mature runner
has years of bug history from the latter approach. On checkpoint cadence, the
Young/Daly formula does **not** transfer cleanly to heterogeneous DAGs of tasks —
its own literature says so — so hex should not try to compute an optimal M from a
failure-rate formula. Instead it should copy the pattern every checkpointed system
converges on independently (Postgres WAL, CI tiered testing, HPC workflow
checkpointing): a small fixed cadence plus a risk-based override trigger, whichever
fires first.

## Trends

- **Explicit closure over lazy propagation.** Every DAG runner that tried to derive
  "which downstream nodes are affected by this failure" node-by-node via local
  trigger rules (Airflow's `trigger_rule`, GitLab's `needs`) has accumulated years
  of confusing-UX bug reports. The fix in each case is the same: compute the
  transitive closure once, from the static graph, at failure time.
- **Y/D's own community says it doesn't generalize to workflow DAGs.** The 2024
  survey explicitly extends Young/Daly to "workflow applications represented as a
  graph of tasks" and reports the optimal period comes out "of a different order"
  than the formula predicts for that case — the formula was derived for a single
  preemptible process with i.i.d. exponential failures, not a DAG of
  heterogeneous, non-exponential-failure tasks.
- **Every production checkpoint policy is a dual trigger, not a pure formula.**
  Postgres (time OR WAL volume), CI (fast-path every commit, full suite on a
  schedule/gate), and LLM pretraining checkpointing (cost/overhead vs
  lost-progress-on-failure) all converge on "whichever threshold fires first" plus
  a risk override, not a single computed optimum.

## Key findings

**1. Failure blast-radius UX**
- GitHub Actions computes blast radius via `needs`: by default a job runs only if
  every needed job succeeded, and "a failure or skip applies to all jobs in the
  dependency chain from the point of failure or skip onwards" — it exposes the
  reason via `needs.<job>.result`, so downstream jobs can distinguish "skipped
  because upstream failed" from other skip reasons. [GitHub Docs: Using jobs in a
  workflow](https://docs.github.com/actions/using-jobs/using-jobs-in-a-workflow)
- GitLab's DAG mode (`needs`) has had **multiple open issues since 2019** over
  skip-propagation being inconsistent or silent: a job needing a skipped job runs
  when it shouldn't ([#31526](https://gitlab.com/gitlab-org/gitlab/-/issues/31526)),
  manual/delayed jobs weren't skipped when their dependency failed
  ([#281878](https://gitlab.com/gitlab-org/gitlab/-/issues/281878)), and status
  handling around skipped `needs` targets is still flagged as inconsistent
  ([#213080](https://gitlab.com/gitlab-org/gitlab/-/issues/213080)). Root cause in
  every case: propagation computed incrementally per-job rather than as one
  graph-wide pass.
- Airflow marks every downstream task `upstream_failed` (a distinct state from
  `failed`) when an ancestor fails or is itself `upstream_failed`, and the graph
  view is the documented tool for "visual debugging of task failure paths or
  identifying downstream blockers"
  ([Astronomer: trigger rules](https://www.astronomer.io/docs/learn/airflow-trigger-rules);
  [MoldStud: Airflow UI](https://moldstud.com/articles/p-master-apache-airflow-ui-visualize-dag-execution-troubleshoot-issues)).
  But dynamic/mapped tasks have shipped bugs where they're marked
  `upstream_failed` with **no actual failed or upstream_failed ancestor**
  ([apache/airflow#27449](https://github.com/apache/airflow/issues/27449),
  filed 2022, still cited in 2025 discussion) — evidence that per-task-instance
  propagation logic is fragile even in a mature, widely-deployed runner.
- Bazel has the analogous silent-blast-radius failure mode for its
  `target_compatible_with` skip mechanism: "Indirect incompatible target skipping
  can have highly non-local silent effects"
  ([bazelbuild/bazel#18707](https://github.com/bazelbuild/bazel/issues/18707)) —
  the explicit complaint is that skips propagate transitively through the
  dependency graph without a visible report of what got skipped and why.
- Argo Workflows' DAG UI has had bugs where a step depending on an *omitted*
  (not merely failed) step disappears from the rendered graph entirely
  ([argoproj/argo-workflows#9852](https://github.com/argoproj/argo-workflows/issues/9852))
  — i.e., the blast radius becomes literally invisible rather than just
  mis-colored.
- Temporal's Web UI takes the opposite, more robust approach: a full parent/child
  execution tree with a fixed color/line vocabulary — solid red = failed, dashed
  red = retrying, dashed purple = pending, green = complete — computed and
  rendered from the durable event history rather than inferred live from
  per-node trigger state
  ([Temporal blog: Redesigning Workflow experience](https://temporal.io/blog/the-dark-magic-of-workflow-exploration);
  [Temporal docs: Web UI](https://docs.temporal.io/web-ui)). A Child Workflow
  Failure is delivered to the parent as a typed event carrying the failed child's
  identity, not inferred from absence.
- Bazel's end-of-build summary and Buck2's `superconsole`/`buck2 log whatup` both
  print a point-in-time flat status snapshot (what's running, what completed) that
  is itself the incident report when something is killed mid-build
  ([Buck2 docs: Consoles](https://buck2.build/docs/users/build_observability/interactive_console/);
  [Tweag: A Tour Around Buck2](https://www.tweag.io/blog/2023-07-06-buck2/)).

**2. Checkpoint-interval theory and its limits**
- Classical formulas (foundational, pre-dates the 18-month window by design —
  cited as the standing baseline every later paper argues against): Young's
  first-order optimum `T_c ≈ √(2·T_s·T_f)` (checkpoint cost × mean-time-to-failure)
  and Daly's refinement `T_c ≈ √(2δ(M+R)) − δ` (checkpoint cost δ, restart
  overhead R, mean time between failures M)
  ([Checkpointing à la Young/Daly: An Overview](https://icl.utk.edu/files/publications/2020/icl-utk-1385-2020.pdf)).
  Both assume a single process (or tightly-coupled parallel job) with i.i.d.
  exponential failures — a hardware/platform failure model, not a
  human-or-LLM-introduced-regression model.
- The 2024 survey **"A survey on checkpointing strategies: Should we always
  checkpoint à la Young/Daly?"** (Bautista-Gomez, Benoit, Di, Hérault, Robert,
  Sun; *Future Generation Computer Systems*, DOI
  [10.1016/j.future.2024.07.022](https://www.sciencedirect.com/science/article/abs/pii/S0167739X24003777))
  explicitly extends the question to "workflow applications represented as a
  graph of tasks" and reports cases where "the optimal period is of a different
  order than that dictated by the Young/Daly formula." This is the single most
  load-bearing finding for adr_0010: **the formula's own research community does
  not endorse applying it unmodified to DAG-of-tasks workloads.** (Published
  ~22 months ago — past the 18-month freshness bar, flagged accordingly, but it
  is the most current treatment of this exact question and nothing more recent
  supersedes it.)
- A May-2026 operational report on LLM pretraining recovery at 504-GPU scale
  confirms the practical framing hex should borrow — checkpoint interval trades
  off checkpoint-save overhead against lost-progress-on-failure, surfaced via a
  monitoring dashboard rather than solved analytically in production — but did
  not yield a reusable closed-form number
  ([arXiv:2605.09370](https://arxiv.org/pdf/2605.09370)).
- Production systems that already ship a checkpoint cadence use a **dual
  trigger**, not a pure formula: Postgres fires a WAL checkpoint on
  `checkpoint_timeout` **or** `max_wal_size`, whichever comes first, explicitly
  trading checkpoint I/O cost against crash-recovery replay time, with common
  production values around 30–60 minutes / roughly one hour of WAL headroom
  ([PostgreSQL docs: WAL Configuration](https://www.postgresql.org/docs/current/wal-configuration.html);
  [EDB: Basics of Tuning Checkpoints](https://www.enterprisedb.com/blog/basics-tuning-checkpoints)).
- CI practice independently converges on the same tiered shape: fast/scoped
  checks on every commit, full/expensive suites on a schedule (nightly) or at a
  merge gate, explicitly to bound cost while accepting that drift is "caught even
  if no PR touched the affected paths" only at the periodic full run
  ([Mergify: Cut your GitHub Actions CI bill](https://mergify.com/blog/cut-your-github-actions-ci-bill);
  general 2025–2026 CI-cost sources synthesized in search).

**3. Progress/state reporting shape**
- The state-table pattern that recurs everywhere a batch/DAG system reports
  progress is a small closed enum (queued → running → succeeded/failed/skipped)
  plus a per-node reason field, rendered as either a flat list (Buck2
  superconsole, Bazel summary) or a rollup tree (Temporal, Airflow Grid+Graph)
  ([AWS Batch job states](https://docs.aws.amazon.com/batch/latest/userguide/job_states.html);
  [Airflow 3.1.0 blog](https://airflow.apache.org/blog/airflow-3.1.0/)).
  Flat lists win for "what's the current status of everything" at a glance;
  trees/graphs win for "why is this one thing blocked." A DAG executor that only
  has one of the two is missing half its own operability story.

## Sources
- https://docs.github.com/actions/using-jobs/using-jobs-in-a-workflow
- https://gitlab.com/gitlab-org/gitlab/-/issues/31526
- https://gitlab.com/gitlab-org/gitlab/-/issues/281878
- https://gitlab.com/gitlab-org/gitlab/-/issues/213080
- https://www.astronomer.io/docs/learn/airflow-trigger-rules
- https://moldstud.com/articles/p-master-apache-airflow-ui-visualize-dag-execution-troubleshoot-issues
- https://github.com/apache/airflow/issues/27449
- https://github.com/bazelbuild/bazel/issues/18707
- https://github.com/argoproj/argo-workflows/issues/9852
- https://temporal.io/blog/the-dark-magic-of-workflow-exploration
- https://docs.temporal.io/web-ui
- https://buck2.build/docs/users/build_observability/interactive_console/
- https://www.tweag.io/blog/2023-07-06-buck2/
- https://icl.utk.edu/files/publications/2020/icl-utk-1385-2020.pdf
- https://www.sciencedirect.com/science/article/abs/pii/S0167739X24003777 (DOI 10.1016/j.future.2024.07.022; ~22 months old — past 18-month bar, flagged, still current SOTA on this exact question)
- https://arxiv.org/pdf/2605.09370
- https://www.postgresql.org/docs/current/wal-configuration.html
- https://www.enterprisedb.com/blog/basics-tuning-checkpoints
- https://mergify.com/blog/cut-your-github-actions-ci-bill
- https://docs.aws.amazon.com/batch/latest/userguide/job_states.html
- https://airflow.apache.org/blog/airflow-3.1.0/

## Recommendation

Ship three concrete, opinionated defaults in adr_0010:

1. **Logging shape**: an append-only structured event log, one line per merge
   (jsonl), fields `{ts, event: "wp_merged", wp_id, ready_set: [...], blocked_set:
   [{wp_id, blocked_by: [failed_wp_id, ...]}]}`. Flat-per-event, not a mutable
   dashboard row — this is what Temporal's durable event history and Buck2's
   `log whatup` snapshot both get right and per-node trigger-rule systems (Airflow,
   GitLab) get wrong when they try to reconstruct state live instead of recording
   it at the moment it's known.
2. **Stranded-work report shape**: on any WP failure, compute the full transitive
   closure of dependents from the static DAG in one pass (not per-node trigger
   propagation) and emit a single report: `{failed_wp, stranded: [{wp_id,
   direct_blocker}]}`. This sidesteps the entire class of bug GitLab/Airflow/Bazel
   have each shipped (silent, partial, or inconsistent propagation) by never
   relying on incremental per-node state at all.
3. **Checkpoint cadence**: do not attempt a Young/Daly-style computed optimum —
   the formula's own 2024 survey says it breaks down for DAG-of-tasks workloads,
   and hex doesn't have the volume of runs needed to fit a failure-rate parameter
   anyway. Ship a dual trigger instead, mirroring Postgres's `checkpoint_timeout
   OR max_wal_size`: **run full verification every M=3 merges, or immediately
   after any merge that clears every WP at the current topological depth
   (a "layer" completes), whichever comes first** — plus an unconditional
   override checkpoint after any WP flagged high-risk (touches shared/core
   files) regardless of the counter. M=3 keeps worst-case undetected rework
   bounded to two WPs' worth of work between checkpoints while still amortizing
   full-suite cost across multiple cheap scoped merges, matching the
   every-commit-fast/periodic-full-slow shape every CI org above converges on.
