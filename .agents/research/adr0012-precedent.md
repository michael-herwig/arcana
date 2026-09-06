# Research: Ceiling-plus-derived-effective-setting precedent (adr_0012)

<!--
Technology-landscape research. Filename and location: this project's
documented research convention.
Owner: researcher worker (design-pattern precedent axis). Handoff to: hex-architect (adr_0012).

Purpose: persist landscape findings that inform ADRs, plans, and design
decisions. Findings decay - check the Expires date before trusting them.
-->

## Metadata

**Date:** 2026-09-05
**Domain:** devops
**Triggered by:** adr_0012 — proposal that hex plan tier becomes a ceiling, and each work package (WP) derives an *effective tier* from declared size/risk flags, which (not the plan tier) drives phases, model class, review breadth and loop rounds.
**Expires:** 2027-03-05 (re-verify sooner if citing the Anthropic adaptive-thinking behavior — it is a beta-flagged, actively-changing surface as of this writing)

## Direct Answer

Yes — well-established precedent exists, and it splits into two distinct sub-patterns that matter for adr_0012:

**(A) Ceiling + free-direction *authored* override, with a *derived default* only when the unit is silent.** Bazel test `size`→timeout, GitHub Actions `timeout-minutes` (workflow→job→step), GitLab CI `default:`, and Kubernetes `LimitRange` all work this way: there is a computed default, but the unit can restate its own value in either direction, and nothing structurally stops it from exceeding the "ceiling."

**(B) Fully *derived* classification with no direct authoring.** Kubernetes Pod QoS class (Guaranteed/Burstable/BestEffort), Anthropic's adaptive-thinking `effort` parameter (an authored *ceiling* under which Claude itself decides how much to actually think, per request), and RouteLLM/FrugalGPT-style cascades all compute the effective setting from the unit's own declared shape — the operator cannot directly assign "Guaranteed," only shape the spec that produces it.

**adr_0012's proposal is pattern (B), not (A)**: plan tier is meant to be a hard ceiling the WP cannot exceed, and the effective tier is computed from declared features (size, risk flags), not restated freely. The closest primary-source analogues are Kubernetes QoS-class derivation and Anthropic's adaptive-thinking `effort`-as-ceiling design — not Bazel/GitHub/GitLab's freely-overridable defaults, which is a materially weaker guarantee (a WP could just declare itself high-tier every time, same as a GitLab job can freely restate any `default:` key).

Every mature system that collapses a pipeline for a small/cheap unit pairs that collapse with a **mandatory, non-collapsible backstop** further downstream (Zuul gate, Gerrit `Verified` submit-requirement, CI smoke-then-full). This directly validates hex's plan to make branch-level review the mandatory backstop for collapsed WPs — none of the researched systems let a fast path substitute for the final gate; it only pre-filters into it.

The sharpest documented anti-pattern is Kubernetes' BestEffort QoS: a workload that silently ends up in the worst class (by omission, not intent) is evicted first and can be OOMKilled/restarted repeatedly with no forcing function to notice — the object exposes its derived class (`kubectl describe pod` → `QoS Class:`) but nothing proactively flags that the derivation produced a dangerous result. This is the direct risk for adr_0012: a WP that under-declares risk flags derives a too-low effective tier, and unless the derivation is inspectable and audited, that under-provisioning is invisible until it recurs.

## Technology Landscape

### Established (proven, widely accepted)

| Tool/Pattern | Status | Notes |
|--------------|--------|-------|
| Bazel test `size` → implied `timeout` | Mature/Standard | small=60s, medium=300s, large=900s, enormous=3600s; explicit `timeout` tag overrides in **either direction** ("all combinations of `size` and `timeout` are legal") [bazel.build/reference/test-encyclopedia] |
| Bazel `exec_properties` | Mature/Standard | Per-target value **overwrites** (does not merge with) `--remote_default_exec_properties`; free-form authored key/value, not derived from size or tags [bazelbuild/bazel#10252] |
| Kubernetes Pod QoS class | Mature/Standard | Fully derived from request/limit equality across containers; **not directly settable**; documented as of Kubernetes v1.37 [kubernetes.io/docs/concepts/workloads/pods/pod-qos/] |
| Kubernetes LimitRange + ResourceQuota | Mature/Standard | ResourceQuota = namespace ceiling (rejects pods without requests once enabled); LimitRange = per-container default + max, converts an omitted spec from BestEffort into Burstable [kubernetes.io/docs/concepts/policy/resource-quotas/, .../limit-range/] |
| GitHub Actions `timeout-minutes` (workflow→job→step) | Mature/Standard | Workflow-level `default` is copied down; job/step can freely override in either direction; steps are additionally capped by remaining job budget, not by workflow default itself |
| GitLab CI `default:` + per-job keys | Mature/Standard | Each `default:` key is copied to jobs that don't define it; a job-defined key fully replaces (most keys don't merge); `inherit:default:false` opts a job out entirely [docs.gitlab.com/ci/jobs/] |
| Zuul check vs gate pipelines | Mature/Standard | check = independent, advisory, fast; gate = dependent pipeline manager with **speculative execution** against the exact future merge state, and is the actual mandatory merge gate [zuul-ci.org/docs/zuul/latest/gating.html] |
| Gerrit `Verified` label / submit requirements | Mature/Standard | Check pipeline sets an early advisory vote; submit is blocked without the mandatory label regardless [gerrit-review.googlesource.com/Documentation/config-submit-requirements.html] |
| CI smoke test as fast path | Mature/Standard | Universally documented as a **pre-filter**, never a substitute — smoke failure blocks before the full suite runs, but passing smoke is necessary, not sufficient, for merge |
| Aider architect/editor model split | Mature/Standard | Two **authored** roles (strong reasoning model for planning, cheap/fast model for diff emission), not computed per-task; configured via `--model`/`--editor-model` [aider.chat/2024/09/26/architect.html] |
| FrugalGPT LLM cascade | Mature (2023 paper, since cited widely) | Cascade escalates per-query; up to 98% cost reduction matching best-LLM performance, or +4% accuracy at same cost [arXiv:2305.05176, May 2023] |
| RouteLLM learned router | Mature (2024 paper + maintained repo) | >85% cost reduction with 95% GPT-4 quality retained on MT Bench, routing only 14% of queries to the strong model; trained on GPT-4-1106-preview/Mixtral-8x7B, reported to generalize to other model pairs without retraining [arXiv:2406.18665, lm-sys/RouteLLM] |
| Claude Code subagent `model:` frontmatter | Mature/Standard | **Authored per subagent definition** (sonnet/opus/haiku/fable/full model ID/`inherit`), not derived from task features; omitted falls back to a resolution order ending at the main session's model [code.claude.com/docs/en/sub-agents] |

### Emerging (early but promising)

| Tool/Pattern | Signal | Worth Watching Because |
|--------------|--------|-------------------------|
| Anthropic adaptive thinking (`thinking.type: "adaptive"` + `output_config.effort`) | Now default-on for Claude Sonnet 5 / Opus 5; per-turn effort is beta as of 2026-07/08 beta headers | This is the **closest primary-source analogue to adr_0012's design**: `effort` (none…max) is an authored ceiling/soft-guidance, and "Claude evaluates the complexity of each request and decides whether and how much to think" **below** that ceiling — i.e., a human sets the ceiling, the unit of work (the request) derives its own effective allocation. [docs.aws.amazon.com/bedrock/.../claude-messages-adaptive-thinking.html] |
| Kubernetes Pod-level resources (beta since v1.34) and cgroup-v2 Memory QoS (beta since v1.37) | Recent betas per current K8s docs | Extends the derived-QoS mechanism to pod-level (not just container-level) requests/limits — may change how "ceiling vs derived" composes for multi-container pods |
| Practitioner "classify-then-set-`reasoning_effort`" pattern | Blog/community guidance only, not vendor-published | OpenAI's own docs describe `reasoning_effort` as **solely an authored, per-request parameter** with no vendor-side automatic derivation from task features; the "use a small classifier model to set effort" pattern is a third-party practice, unverified as an officially endorsed design |

### Declining / gap (worth flagging, not "declining" in the usual sense)

| Tool/Pattern | Signal | Avoid Because |
|--------------|--------|-----------------|
| Fixed `thinking.type: "enabled"` + `budget_tokens` on newest Claude models | Deprecated on Claude Opus 4.6 / Sonnet 4.6, unsupported (400 error) on Fable 5.1/Mythos 5.1/Opus 5 | Anthropic's own trajectory is explicitly *away* from a flat, fully-authored budget and *toward* ceiling+derived — evidence the industry is moving in adr_0012's direction, not away from it |
| Multi-agent frameworks (LangGraph/CrewAI/AutoGen/AG2) shipping a built-in feature→model router | Not found in current docs; frameworks are "model-agnostic" and let you assign a model per node/agent/role, but ship no standard derivation policy | Confirms a real gap: per-task model routing derived from task features is left entirely to the implementer in every mainstream framework surveyed — hex would be building this derivation logic itself, with no off-the-shelf pattern to copy wholesale |

## Design Patterns Worth Considering

- **Derived-class-from-spec** — the class (QoS tier, effective hex tier) is a pure function of the unit's own declared attributes, never a separate authored field. Used by: Kubernetes Pod QoS. [kubernetes.io/docs/concepts/workloads/pods/pod-qos/]
- **Ceiling-as-soft-guidance, model/unit decides depth below it** — the human sets a level (effort/tier); the unit of work computes how much of that ceiling it actually needs. Used by: Anthropic adaptive thinking. [docs.aws.amazon.com/bedrock/.../claude-messages-adaptive-thinking.html]
- **Derived default, freely-authored override in either direction** — weaker guarantee than a true ceiling; fine for scheduling hints, wrong for a governance cap. Used by: Bazel test timeout, GitHub Actions `timeout-minutes`, GitLab CI `default:`.
- **Collapsed fast path with a mandatory non-collapsible backstop** — the fast/derived-cheap path is always a pre-filter; the real gate cannot itself be collapsed. Used by: Zuul check/gate, Gerrit `Verified` submit requirement, CI smoke-then-full.
- **Learned/derived per-query routing with a published cost-quality curve** — a router or cascade decides the effective model/effort per unit, with measured numbers rather than a hand-authored policy. Used by: RouteLLM, FrugalGPT.

## Key Findings

1. **Bazel test size→timeout is derived-with-free-override, not a true ceiling**: size implies a timeout (60/300/900/3600s) but an explicit `timeout` tag legally overrides it in either direction; a separate, still-open issue (bazelbuild/bazel#25793, filed ~April 2025) shows Bazel *still* lacks a good way to derive local/remote **resource** sizing from a target's declared class — proof that getting derivation right for one axis (test timeout) doesn't automatically generalize to another (exec resources) in the same tool. [https://bazel.build/reference/test-encyclopedia, https://github.com/bazelbuild/bazel/issues/25793, https://github.com/bazelbuild/bazel/issues/10252]
2. **Kubernetes QoS class is the sharpest true-derivation analogue**: Guaranteed/Burstable/BestEffort is computed solely from request==limit equality, cannot be set directly, and its visible failure mode (BestEffort evicted first, can be silently OOMKilled and auto-restarted, masking a recurring problem) is exactly the risk shape adr_0012 must guard against for an under-declared WP. LimitRange supplies namespace-wide defaults so omission doesn't silently produce the worst class — but LimitRange **does not validate its own defaults for consistency**, so a bad default/request combination can produce a silently unschedulable pod. [https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/, https://kubernetes.io/docs/concepts/policy/limit-range/, https://cast.ai/blog/oomkilled-exit-code-137/]
3. **Per-unit model routing in agent frameworks is universally authored-per-role, not derived-per-task, at the framework level.** Aider's architect/editor split, Claude Code's subagent `model:` frontmatter, and OpenAI Agents SDK's per-agent model are all hand-assigned to a *role*, not computed from the *task's* features at runtime. The only genuinely feature-derived per-query routing found is in dedicated router/cascade research (RouteLLM, FrugalGPT), not in the agent-orchestration frameworks themselves. [https://aider.chat/2024/09/26/architect.html, https://code.claude.com/docs/en/sub-agents, https://openai.github.io/openai-agents-python/models/]
4. **Anthropic's adaptive thinking is a live, primary-source instance of exactly adr_0012's shape**: `output_config.effort` (none…max) is authored as a ceiling/"soft guidance," and the model itself "evaluates the complexity of each request and decides whether and how much to think" below that ceiling. Anthropic's own migration direction (deprecating fixed `budget_tokens` on newer models, making adaptive the default) is *evidence the industry is moving toward* ceiling+derived, away from flat authored settings. This is dated to beta flags as recent as 2026-08-01, so re-verify before citing in a final ADR after the Expires date. [https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-adaptive-thinking.html]
5. **Router papers give real, cited numbers for derived per-unit routing paying off**: RouteLLM reports >85% cost reduction while retaining 95% of GPT-4-level quality on MT Bench, sending only 14% of queries to the strong model, and reports the router generalizing to other model pairs without retraining (arXiv:2406.18665, July 2024). FrugalGPT reports up to 98% cost reduction matching the best individual LLM's performance, or a 4% accuracy improvement at equal cost, via an LLM cascade (arXiv:2305.05176, May 2023). Both are evidence that a well-built derivation function beats a flat global setting on the cost/quality frontier, supporting adr_0012's core bet. [https://arxiv.org/abs/2406.18665, https://arxiv.org/abs/2305.05176]
6. **Every collapsed-pipeline precedent keeps a mandatory backstop that cannot itself be collapsed**: Zuul's gate pipeline re-tests speculatively against the true future merge state regardless of what the (optional, fast) check pipeline reported; Gerrit's `Verified` label is a submit-requirement independent of the check vote; CI smoke tests are documented purely as a pre-filter that blocks *before* the full suite, never a replacement for it. This directly supports making branch-level review the mandatory backstop for every collapsed hex WP, independent of its derived tier. [https://zuul-ci.org/docs/zuul/latest/gating.html, https://gerrit-review.googlesource.com/Documentation/config-submit-requirements.html]

## Anti-patterns (documented failures of derived-per-unit policy)

- **Silent under-provisioning, masked by auto-recovery**: BestEffort pods are evicted first and can be repeatedly OOMKilled and auto-restarted by Kubernetes' self-healing, which hides a recurring resource problem until it causes a real outage at a traffic peak. No proactive internal alert fires on the classification itself — only `kubectl describe pod`'s `QoS Class:` field and external monitoring/audit tooling expose it after the fact. [https://cast.ai/blog/oomkilled-exit-code-137/, https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/]
- **Unchecked derived defaults producing an inconsistent, unschedulable result**: LimitRange's injected defaults are not validated against the pod's own requests, so a default limit can end up below a requested value, silently making the pod unschedulable — caught only by a scheduling failure event, not by any dedicated "why was this rejected" explainer. [https://kubernetes.io/docs/concepts/policy/limit-range/]
- **Escape hatches exist but must be explicit and enumerated, not implicit**: Kubernetes Pod Security Admission requires exemptions from enforcement to be statically and explicitly enumerated in the admission controller's own configuration, and policy violations that are allowed under audit/warn modes are recorded via audit annotations rather than silently passing. This is the ecosystem's answer to "how do we know a derived/enforced classification got overridden": explicit enumeration + an audit trail, not a silent bypass. [https://kubernetes.io/docs/concepts/security/pod-security-admission/, https://kubernetes.io/docs/reference/labels-annotations-taints/audit-annotations/]
- **A derivation mechanism that works for one axis doesn't automatically generalize**: Bazel solved size→timeout derivation years ago but, per a still-open 2025 issue, has not solved the analogous problem for exec resource sizing — a caution against assuming adr_0012's derivation logic, once correct for "phases/review breadth," will trivially extend to future axes (e.g. cost budget) without separate validation. [https://github.com/bazelbuild/bazel/issues/25793]

## Recommendation for adr_0012

1. **Make the plan tier a true ceiling with no upward escape past it** — mirror Kubernetes ResourceQuota (namespace hard-caps total consumption) rather than GitLab CI's `default:`/GitHub Actions' `timeout-minutes`, where a job or step can freely restate *any* value including one that exceeds the workflow default. adr_0012 should treat "effective tier > plan tier" as structurally impossible, not merely discouraged. *Source: kubernetes.io/docs/concepts/policy/resource-quotas/ vs docs.gitlab.com/ci/jobs/.*
2. **Derive the effective tier from structural, declared WP features (size/risk flags), not from a free-text or freely-restated field** — mirror Kubernetes QoS-class derivation and Anthropic's adaptive-thinking design (ceiling authored, actual depth derived by evaluating the request). Do not use a Bazel-`tags`-style free-form authored label for this governance axis — that pattern is fine for scheduling hints, not for something phases/model-class/review-breadth depend on. *Source: kubernetes.io/docs/concepts/workloads/pods/pod-qos/; docs.aws.amazon.com/bedrock/.../claude-messages-adaptive-thinking.html.*
3. **Every WP whose derived tier collapses/skips phases must still pass a mandatory, non-collapsible backstop** — this is universal across Zuul (gate re-tests speculatively regardless of check outcome), Gerrit (`Verified` submit requirement independent of check), and CI (smoke never replaces full regression). This directly justifies branch-level review as the mandatory backstop for every collapsed WP, with no tier low enough to skip it. *Source: zuul-ci.org/docs/zuul/latest/gating.html; gerrit-review.googlesource.com/Documentation/config-submit-requirements.html.*
4. **Persist the derivation's inputs and result as an inspectable record on the WP, not just the final effective tier** — mirror `kubectl describe pod`'s exposed `QoS Class:` field plus Kubernetes' audit-annotation-on-policy-decision pattern. Without this, a WP that under-declares risk and derives too low a tier fails the same way a BestEffort pod does: invisibly, until the same failure recurs. *Source: kubernetes.io/docs/reference/labels-annotations-taints/audit-annotations/; cast.ai/blog/oomkilled-exit-code-137/.*
5. **Keep one explicit, enumerated escape hatch to force a higher-than-derived tier (never lower than derived, never above the plan ceiling)** — mirror Bazel's explicit `timeout` tag overriding the size-implied default, and Kubernetes Pod Security Admission's requirement that exemptions be statically and explicitly enumerated rather than silently applied. A human or a later-discovered signal must be able to escalate a WP that the derivation under-classified. *Source: bazel.build/reference/test-encyclopedia; kubernetes.io/docs/concepts/security/pod-security-admission/.*

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| https://bazel.build/reference/test-encyclopedia | Docs (primary) | undated page, current | Test size→timeout derivation, override direction |
| https://github.com/bazelbuild/bazel/issues/10252 | Issue (primary repo) | 2019 | exec_properties overwrite (not merge) semantics |
| https://github.com/bazelbuild/bazel/issues/25793 | Issue (primary repo) | ~2025-04, open | Gap: no derived resource sizing for local/remote exec |
| https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/ | Docs (primary) | current, v1.37 stable | QoS class derivation, non-authorable, eviction order |
| https://kubernetes.io/docs/concepts/policy/limit-range/ | Docs (primary) | current | LimitRange defaults, consistency-check gap |
| https://kubernetes.io/docs/concepts/policy/resource-quotas/ | Docs (primary) | current | Namespace ceiling, reject-without-request behavior |
| https://kubernetes.io/docs/concepts/security/pod-security-admission/ | Docs (primary) | current | Explicit enumerated exemptions as escape hatch |
| https://kubernetes.io/docs/reference/labels-annotations-taints/audit-annotations/ | Docs (primary) | current | Audit trail on policy decisions, even when allowed |
| https://cast.ai/blog/oomkilled-exit-code-137/ | Blog (vendor) | 2026 | BestEffort silent-restart masking anti-pattern |
| https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-adaptive-thinking.html | Docs (primary, AWS/Anthropic) | current, beta flags dated 2026-07/08 | Ceiling (`effort`) + model-derived depth — closest analogue to adr_0012 |
| https://developers.openai.com/api/docs/guides/reasoning | Docs (primary) | current | `reasoning_effort` is authored-only, no vendor-published derivation |
| https://arxiv.org/abs/2406.18665 (RouteLLM) | Paper | 2024-06 | Measured cost/quality numbers for derived per-query routing |
| https://github.com/lm-sys/routellm | Repo (primary) | 2024-07 blog ref | Router generalization claim, benchmark list |
| https://arxiv.org/abs/2305.05176 (FrugalGPT) | Paper | 2023-05 | LLM cascade cost/accuracy numbers |
| https://aider.chat/2024/09/26/architect.html | Blog (primary/maintainer) | 2024-09 | Architect/editor authored role split |
| https://code.claude.com/docs/en/sub-agents | Docs (primary) | current | Subagent `model:` frontmatter, authored not derived |
| https://openai.github.io/openai-agents-python/models/ | Docs (primary) | current | Per-agent model assignment in handoff graphs |
| https://zuul-ci.org/docs/zuul/latest/gating.html | Docs (primary) | current | Check vs gate, speculative execution, mandatory gate |
| https://gerrit-review.googlesource.com/Documentation/config-submit-requirements.html | Docs (primary) | current | Mandatory submit requirement independent of check vote |
| https://docs.gitlab.com/ci/jobs/ | Docs (primary) | current | `default:` + per-job override, `inherit:default` |
| GitHub Actions timeout-minutes (community docs, actions/runner#1449, github/community#10690) | Issue/discussion (primary repo) | various | Workflow→job→step timeout hierarchy, free override |
