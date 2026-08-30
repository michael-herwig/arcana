# Research: Backward-compatible evolution of plan/workflow artifact schemas

## Metadata

- Date: 2026-08-30
- Expires: 2027-02-28
- Sources: see ### Sources below (8 systems/ecosystems surveyed)

## Direct answer

Don't invent a schema-version field for this change. Adding a `Verify` column
to a plan's Parallelization table and a last-reviewed-SHA field to its Status
block is a **pure additive-optional change** — every mature schema-evolution
discipline surveyed (protobuf, Kubernetes CRDs, OpenAPI, Terraform provider
state) converges on the same rule for exactly this shape of change: add an
optional field with a defined default, never make it required, and let old
producers/consumers ignore it. That maps directly to the ADR's own instinct
("missing column ⇒ old behavior") — the fix is to keep that rule as
**capability-detection by the parser** (does this table have a `Verify`
column? does this Status block have a last-reviewed-SHA line?), not a
`Plan-Schema: N` version counter compared against the tool's current version.
Reserve an explicit version marker + migration path for the day the change
stops being additive (rename/remove a column, restructure the table) —
that's the trigger that justifies the heavier machinery (Terraform
`SchemaVersion`+`StateUpgraders`, k8s `apiVersion`+conversion webhooks), not
this one.

## Trends

- **Every ecosystem treats "add an optional field with a safe default" as a
  non-event, and treats "require a field" or "restructure/remove a field" as
  the actual breaking change requiring versioning machinery.** Protobuf
  (proto3 optional-by-default), Kubernetes CRDs, and OpenAPI additive-change
  guidance all state this almost verbatim. This is the single strongest,
  most-repeated pattern across the whole survey — not a single system
  disagreed. [Robert Yokota, 2021](https://yokota.blog/2021/08/26/understanding-protobuf-compatibility/); [Kubernetes CRD versioning](https://faun.dev/c/stories/dineshparvathaneni/kubernetes-crd-versioning-for-operator-developers/); [Red Hat, 2024](https://developers.redhat.com/articles/2024/03/25/how-navigate-api-evolution-versioning)
- **"Pin the in-flight instance to the version it started with" beats "migrate
  the in-flight instance."** Airflow 3's DAG versioning (2025, AIP-63/65/66)
  runs an in-progress DAG run to completion under the DAG version it started
  with, even if a newer version is uploaded mid-run; only *new* runs pick up
  the change. Temporal's `GetVersion`/Patched API does the same thing at
  finer grain: a marker recorded once in a workflow's event history decides
  which code branch every future replay of *that* execution takes, while new
  executions take the new branch. Neither system forces a live migration of
  in-flight state — both branch on a marker/version already attached to the
  running instance. [Airflow 3 GA, 2025](https://airflow.apache.org/blog/airflow-three-point-oh-is-here/); [AIP-63](https://cwiki.apache.org/confluence/display/AIRFLOW/AIP-63:+DAG+Versioning); [Temporal versioning docs](https://docs.temporal.io/develop/go/workflows/versioning)
- **Heavyweight version+migration machinery is reserved for structural
  breaks, and is expensive enough that mature tools avoid it until forced.**
  Kubernetes conversion webhooks and Terraform `StateUpgraders` both exist
  because *some* changes in those ecosystems are non-additive (field
  renames, type changes, restructures) — but both ecosystems explicitly
  document "if you're only adding optional fields, you don't need this."
  [oneuptime CRD conversion, 2026](https://oneuptime.com/blog/post/2026-02-09-crd-conversion-webhooks-multi-version/view); [Terraform state upgraders](https://developer.hashicorp.com/terraform/plugin/framework/migrating/resources/state-upgrade)
- **Spec-driven-dev tooling (hex's direct competitive category) has not
  solved this at all yet — this is a real gap, not a solved problem to copy
  from.** GitHub's spec-kit has an "upgrade workflow" for refreshing its own
  *tool* templates/scripts, and separately documents three patterns for
  evolving a project's *spec* content (flow-forward, living-spec,
  flow-back) — but nowhere addresses what happens to a `spec.md` authored
  under an older field/section layout when the tool's template schema
  changes. flagging as current/unresolved, not stale. [spec-kit evolving-specs.md, 2026](https://github.com/github/spec-kit/blob/main/docs/guides/evolving-specs.md)
- **CI/pipeline-definition engines (GitHub Actions, GitLab CI) don't really
  face this problem the way hex does**, because the *interpreter* (the
  runner) is centrally upgraded and reads the YAML fresh on every run —
  there's no long-lived "in-flight document" whose interpreter version is
  frozen at authoring time. GitLab does apply the additive-optional-field
  rule to its own CI schema keywords (new keywords are added as optional,
  e.g. the `default:` keyword rollout was explicitly designed to be fully
  backward compatible with configs that predated it), which is the same
  convergent pattern, just applied to a shorter-lived artifact. [GitLab default: backward compat](https://gitlab.com/gitlab-org/gitlab-foss/-/issues/62732); [GitLab CI schema](https://docs.gitlab.com/development/cicd/templates/)
- **Nothing resembling a published "prompt-contract versioning" standard
  exists.** The nearest analogue is treating LLM tool/output JSON Schemas
  like API contracts (version them, keep additions backward compatible,
  make consumers tolerant of unknown fields) — i.e., the same protobuf/
  OpenAPI convergence, just re-stated for structured-output schemas. One
  caveat worth flagging forward: OpenAI Structured Outputs' *strict* mode
  requires `additionalProperties: false` at every object level, which means
  a schema in strict mode has **zero tolerance for undeclared fields** —
  if hex's plan format is ever parsed via a strict JSON-schema-validated
  path (rather than markdown/regex), "missing column ⇒ old behavior" stops
  being free and needs an explicit schema-version bump at that point. Not
  relevant today (hex plans are markdown tables), but worth a forward
  pointer in the ADR. [PromptLayer, 2026](https://blog.promptlayer.com/how-json-schema-works-for-structured-outputs-and-tool-integration/); [DeepDocs additionalProperties](https://deepdocs.dev/json-schema-additionalproperties/)

## Key findings

1. **Additive-optional-with-default is the industry-converged rule for this
   exact change shape.** protobuf: "adding a field with a default value is a
   fully compatible change... never reuse field numbers, always add, never
   remove." Kubernetes CRDs: "Kubernetes doesn't add a required field;
   instead it adds an optional field with a sane default value... you must
   be able to round-trip between versions without losing data." OpenAPI:
   "additive changes are safe... introduce new fields rather than removing
   or altering existing ones." All three independently phrase the identical
   constraint. Apply directly: `Verify` column absent from a table row ⇒
   treat as its default (e.g., "not required" or whatever adr_0010 defines);
   last-reviewed-SHA absent from Status block ⇒ treat as "unknown/never
   reviewed," not as an error.

2. **The parser should branch on field *presence*, not on a compared version
   number, for a change this small.** Temporal's Patching API is the
   clearest worked example of *why*: `GetVersion` records a marker the first
   time new code runs, and every future interpretation of that specific
   execution's history checks the marker, not a global "workflow schema
   version." Applied to hex: `hex-execute`/`hex-review` check "does this
   plan's Parallelization table have a `Verify` header cell" the same way,
   rather than reading a `Plan-Schema: 1` line and dispatching on `== 1` vs
   `== 2`. A presence-check is strictly less machinery than a version
   comparator and gives identical behavior for one additive field.

3. **In-flight/already-authored artifacts should be pinned to old behavior
   forever, not migrated forward.** Airflow 3's decision to run a started
   DAG run to completion under its starting version — even mid-run — is the
   direct precedent for adr_0010's requirement that "existing approved plans
   without them must still execute unchanged." No migration step, no
   forced upgrade: the old artifact's absence of the new field *is* its
   version marker, permanently.

4. **A real version field + migration command is worth introducing only at
   the point a change is no longer additive** (a column is renamed, removed,
   or a table's shape changes incompatibly). Terraform's model —
   `SchemaVersion` integer + a chain of `StateUpgraders`, each upgrading
   exactly one version step — is the right template to reach for *then*,
   not now. Introducing it preemptively for a single additive column is the
   over-engineered version of this problem: it adds a versioning axis, a
   comparison, and a place for the comparison to be wrong, to solve a
   problem ("is this field present") that a presence-check already solves
   for free.

5. **Expand-contract (Fowler's Parallel Change) reframes why "never force a
   contract phase" is fine here.** Database expand-contract has a mandatory
   contract phase because old columns cost storage/index overhead forever if
   kept. A markdown plan artifact has no such cost — keeping "no `Verify`
   column present" as a permanently valid, permanently-supported shape is
   nearly free. So unlike a DB migration, hex has no forcing function to
   ever deprecate the pre-adr_0010 plan shape; the ADR should say so
   explicitly rather than implying a future cleanup pass is expected.

6. **spec-kit — hex's closest sibling in the spec-driven-dev category — has
   not solved artifact-schema migration at all**, only tool-file refresh.
   This is worth noting in the ADR not as prior art to copy but as
   confirmation that hex is ahead of the category here; there's no
   established convention being deviated from.

## Sources

- [Understanding Protobuf Compatibility – Robert Yokota, 2021](https://yokota.blog/2021/08/26/understanding-protobuf-compatibility/)
- [Kubernetes CRD Versioning for Operator Developers – faun.dev](https://faun.dev/c/stories/dineshparvathaneni/kubernetes-crd-versioning-for-operator-developers/)
- [How to Implement CRD Conversion Webhooks for Multi-Version Support – oneuptime, 2026](https://oneuptime.com/blog/post/2026-02-09-crd-conversion-webhooks-multi-version/view)
- [Terraform State Upgraders – HashiCorp Developer](https://developer.hashicorp.com/terraform/plugin/framework/migrating/resources/state-upgrade)
- [Terraform Resources - State Migration – HashiCorp Developer](https://developer.hashicorp.com/terraform/plugin/sdkv2/resources/state-migration)
- [AIP-63: DAG Versioning – Apache Airflow wiki](https://cwiki.apache.org/confluence/display/AIRFLOW/AIP-63:+DAG+Versioning)
- [Apache Airflow 3 is Generally Available!, 2025](https://airflow.apache.org/blog/airflow-three-point-oh-is-here/)
- [Temporal Versioning – Go SDK docs](https://docs.temporal.io/develop/go/workflows/versioning)
- [Versioning Workflows with the Patching API – Temporal Community Forum](https://community.temporal.io/t/versioning-training-versioning-workflows-with-the-patching-api/12017)
- [How to navigate API evolution with versioning – Red Hat Developer, 2024](https://developers.redhat.com/articles/2024/03/25/how-navigate-api-evolution-versioning)
- [Expand and Contract Method for Database Changes – Jasmin Fluri](https://medium.com/@jasminfluri/expand-and-contract-method-for-database-changes-414d236f236f)
- [spec-kit evolving-specs.md – github/spec-kit, 2026](https://github.com/github/spec-kit/blob/main/docs/guides/evolving-specs.md)
- [GitLab `default:` keyword backward compatibility issue #62732](https://gitlab.com/gitlab-org/gitlab-foss/-/issues/62732)
- [GitLab CI/CD schema development docs](https://docs.gitlab.com/development/cicd/templates/)
- [How JSON Schema Works for LLM Tools & Structured Outputs – PromptLayer, 2026](https://blog.promptlayer.com/how-json-schema-works-for-structured-outputs-and-tool-integration/)
- [Mastering JSON Schema additionalProperties for Flexible Validation – DeepDocs](https://deepdocs.dev/json-schema-additionalproperties/)

## Recommendation

Write adr_0010's compat rule as: *"A `Verify` column absent from the
Parallelization table, or a last-reviewed-SHA line absent from the Status
block, is a permanently valid legacy shape — not a version to detect and
migrate away from. Every reader of a plan artifact must check for the
field's presence and fall back to the pre-adr_0010 default when absent;
readers must not compare a plan-level version number."* Do not add a
`Plan-Schema:` or similar version field for this change — that's
over-engineering for a purely additive change, evidenced by every mature
schema-evolution discipline surveyed treating optional-field-with-default as
a non-versioned non-event. Explicitly bank the pattern for later: the day a
plan-format change is *not* additive (rename/remove/restructure a column),
that's the trigger to introduce a real version marker plus a migration step
in `hex-execute` — modeled on Terraform's `SchemaVersion`+`StateUpgraders`
chain — not before.
