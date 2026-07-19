# Research: plan-schema evolution for hierarchical execution

**Axis:** data model / compatibility (gate-selected, user pick)
**Date:** 2026-07-19
**Decision it informs:** adr_0002 — execution scheduling + recursive orchestration.
**Produced by:** hex-architect high run, researcher worker (fast-balanced).

## Direct answer

Extend the Parallelization table by ID string alone: dotted sub-WP IDs
(`WP3.1`) in the same table, same columns, same 4-value status vocabulary. No
new columns, no new status values, no schema-version marker. A plan with zero
sub-WP rows is byte-identical to today's — old plans execute unchanged.

## Key findings

1. GitLab `needs` vs `stages`: needs = real DAG edge; stages (hex's wave) =
   derived, cached view for readability/fast scheduling. hex's "waves are
   computed, not asserted" already is this. https://docs.gitlab.com/ci/yaml/needs/
2. Airflow TaskGroups: hierarchy purely via ID prefixing (dot separator), no
   separate scheduling entity for the group; `prefix_group_id=False` exists so
   retrofits don't rename existing IDs.
   https://airflow.apache.org/docs/apache-airflow/stable/concepts/dags.html?highlight=taskgroup
3. Dagster: groups are labels only — dependencies exist at leaf level. The
   precedent for parent-WP-with-children never being schedulable itself.
   https://docs.dagster.io/guides/build/assets/defining-assets-with-asset-dependencies
4. WBS numbering is the cautionary tale (manual renumber on insert/delete);
   hex's append-only never-renumber C-00x discipline extends to sub-WP
   suffixes: next sibling = next integer, never reindexed.
   https://support.microsoft.com/en-us/office/create-wbs-codes-in-project-desktop-bb6a61aa-debd-4e38-8c04-8e2c1ae3cbda
5. Bazel labels: stable string composition beats sequence numbers.
   https://bazel.build/concepts/labels
6. Temporal: append-only history authoritative, mutable-state projection on
   the hot path — maps to hex's "branches are evidence, table is state of
   record." Parent WP Status must be a computed rollup, never independently
   mutable — GitLab hit real parent/child pipeline status drift storing them
   separately. https://docs.temporal.io/workflows ·
   https://gitlab.com/gitlab-org/gitlab/-/work_items/456868
7. GH Actions re-run --failed: per-unit status cells give partial resume for
   free once sub-WPs are ordinary rows.
   https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs
8. K8s additive-only field evolution + tolerant-consumer convention; Docker
   Compose's `version:` field became obsolete dead weight — skip any
   schema-version marker; presence of dotted IDs IS the signal.
   https://kubernetes.io/docs/concepts/overview/kubernetes-api/ ·
   https://adamj.eu/tech/2025/05/05/docker-remove-obsolete-compose-version/

## Recommended table shape

Same columns: `WP | Scope | Expected files | Size | Wave | Depends-on | Status`.
Sub-WPs = new rows, dotted IDs, same table (no sub-tables, no indentation).

| WP | Scope | Expected files | Size | Wave | Depends-on | Status |
|----|-------|-----------------|------|------|------------|--------|
| WP3 | C-004, S-001 | `src/api/*.rs` | L | 2 | WP1, WP2 | active *(rollup — computed)* |
| WP3.1 | C-004 | `src/api/handlers.rs` | M | 2 | *(inherits WP3's)* | merged |
| WP3.2 | S-001 | `src/api/routes.rs` | S | 2 | WP3.1 | active |

Rules:
- **Wave:** sub-WPs join the same global topological numbering — no
  wave-within-a-WP; existing wave contract unchanged, just more nodes.
- **Depends-on inheritance:** absent → inherit parent's; override for tighter
  edges.
- **Scheduling:** only leaf rows get branch+worktree; a parent with children
  is never branched (Dagster rule).
- **Parent Status = computed rollup:** merged iff all children merged (+ join
  check); failed if any child failed; active once any child started; pending
  iff all pending. Recomputed on every child write, never set directly. A
  real integration-work join is an ordinary sibling row (`WP3.3`,
  depends-on children) with the same 4 statuses — no 5th status, no `.join`
  suffix.
- **IDs never renumbered** (existing C-00x discipline extended).

## Backward-compat analysis

- Old plans: no sub-rows → every rule vacuous (rollup of zero children =
  literal status) → 100% unchanged, no fallback, no version detection.
- Resume: unchanged shape; sub-WP branches are just longer slugs; existing
  branch-scan fallback finds them.
- No schema-version marker; status vocabulary explicitly NOT extended.

## Recommendation

Ship the ID-suffix extension only. Frame in the ADR as generalizing three
rules hex already has (wave computed-not-asserted; IDs append-only;
graceful missing-column fallback) to a richer ID space. The one genuinely
new behavior to specify: the parent-rollup computation rule (the
precedent-informed drift failure mode to avoid).
