# Research: Defining, Sourcing, and Degrading Risk Flags for Derived Tier Policy

<!--
Technology-landscape research. Filename and location: this project's
documented research convention (`.agents/research/adr0012-risk-flags.md`).
Owner: a researcher worker. Handoff to: /hex-architect (adr_0012).

Purpose: persist landscape findings that inform ADRs, plans, and design
decisions. Findings decay - check the Expires date before trusting them.
-->

## Metadata

**Date:** 2026-09-05
**Domain:** security
**Triggered by:** adr_0012 — hex-architect design of a per-work-package
effective tier `f(size, risk flags)`, where flags come from plan-table
cells and an optionally-absent project-memory file, and a low tier
collapses the review/verification pipeline.
**Expires:** 2027-03-05

## Direct Answer

Every mature system studied here draws the same line: **the enumeration of
risk categories is closed and versioned** (OpenSSF Scorecard's ~18 named
checks, OWASP ASVS's 14 nested chapters, NIST SSDF's 4 practice groups),
never open-ended per-instance judgment — and the one system that got
outgrown by reality (PCI DSS's two-bucket in-scope/out-of-scope model)
responded by shipping a new named category in a major version
("connected-to / security-impacting", PCI DSS v4.0.1) plus a catch-all
principle, not by falling back to free text. On the crux question — what a
system does when the input that would raise a control is **absent** —
identity/authorization primitives default fail-closed (AWS IAM implicit
deny, SELinux enforcing-by-default) while availability-sensitive admission
layers (Kubernetes admission webhooks, OPA/Gatekeeper) often ship
fail-open **by explicit, documented choice**, always with a fail-closed
switch and a documented cost for flipping it. The one clean
**silent, undocumented** fail-open in this research is GitHub branch
protection: a missing or malformed `CODEOWNERS` file makes "require review
from code owners" simply not enforce, with no operator-facing signal
beyond an easy-to-miss UI banner — this is the negative precedent, not one
to follow. Migration of a new derived policy over pre-existing artifacts
has one standard shape across ecosystems (Node's `package.json` `"type"`,
Rust's `edition` field, Go's `go` directive): **absent marker = old
behavior, frozen exactly**, new behavior is opt-in per-artifact, and every
one of these ecosystems now tells authors to write the field explicitly
specifically because the absent-default's meaning can never safely change
later. No tool researched here claims to *detect* irreversibility or hub
risk as a semantic judgment — migration linters (strong_migrations,
squawk), API-diff tools (buf breaking, cargo-semver-checks), and
change-coupling analysis (CodeScene/Code Maat) all substitute a narrow,
named, mechanically-checkable proxy, are explicit about what they miss,
and pair the proxy with a cheap, code-reviewed, narrowly-scoped escape
hatch rather than a global override — none bakes mandatory
justification/expiry/second-approval into the mechanism itself; the
safety property that *is* structurally common is that overrides stay
narrowly scoped and remain visible after the fact rather than vanishing.

## 1. Risk / Sensitivity Taxonomies: Closed Enumeration or Open Judgment?

| System | Shape | How it handles an unanticipated category | Source |
|---|---|---|---|
| OpenSSF Scorecard | Closed, fixed list of 18 named checks (Binary-Artifacts, Branch-Protection, CI-Tests, CII-Best-Practices, Code-Review, Contributors, Dangerous-Workflow, Dependency-Update-Tool, Fuzzing, License, Maintained, Packaging, Pinned-Dependencies, SAST, SBOM, Security-Policy, Signed-Releases, Token-Permissions, Vulnerabilities, Webhooks) | New checks land only via project contribution/PR to the tool itself; no per-user runtime extension | [ossf/scorecard checks.md](https://github.com/ossf/scorecard/blob/main/docs/checks.md) (fetched 2026-09-05) |
| SLSA | Leveled (0–3), track-based (Build track is primary) | Not independently confirmed this pass (levels page 404'd); general framing is that new tracks/levels are added by spec revision, not per-user extension — **unverified in this pass, treat as directionally correct only** | [slsa.dev](https://slsa.dev/spec/v1.2/) |
| NIST SSDF (SP 800-218) | Closed: 4 practice groups (PO/PS/PW/RV), 19 practices, 42 tasks | Deliberately notional/outcome-based — organizations map their own existing practices onto the fixed task list rather than the list growing per-org | [NIST SSDF overview](https://www.nist.gov/document/eo-14028-presentation-nist-secure-software-development-framework-ssdf) |
| OWASP ASVS | Closed: 14 chapters, 3 nested levels (L2 ⊇ L1, L3 ⊇ L2), 286 requirements mapped to CWE | New requirements land only in a versioned ASVS release | [SoftwareMill: Implementing OWASP ASVS](https://softwaremill.com/implementing-owasp-asvs/); [Codific ASVS overview](https://codific.com/owasp-asvs-a-comprehensive-overview/) |
| CIS Benchmarks | Closed, per-platform control list, versioned | New controls ship in a new benchmark version | general knowledge, not independently re-verified this pass |
| PCI DSS scoping | **Not** a fixed enumeration of systems — a judgment-driven categorization (in-scope / connected-to / out-of-scope) applied per environment | v4.0.1 formalized a **third bucket**, "connected-to or security-impacting systems," specifically because the old in-scope/out-of-scope binary missed systems that can affect the CDE's confidentiality/integrity/availability without touching card data directly (jump servers, log aggregators, vulnerability scanners, auth servers) | [SecurityMetrics: PCI Scope Categories](https://www.securitymetrics.com/blog/pci-scope-categories-keeping-your-card-data-separate); [Secureframe: PCI Scope](https://secureframe.com/blog/pci-scope) |

**Takeaway:** all six close the enumeration rather than leaving it open —
but PCI DSS is the direct precedent for *what happens when the closed list
turns out to be incomplete*: a versioned taxonomy revision that adds a
named category plus a catch-all principle ("if it can affect the CDE, it's
in scope"), not silent expansion by individual judgment calls at the edge.

## 2. Fail-Open vs Fail-Closed for a Missing Policy Source

| System | Default | Documented rationale | Documented incident/gotcha |
|---|---|---|---|
| Kubernetes admission webhooks | `failurePolicy: Fail` is the **API default** (fail-closed); `Ignore` (fail-open) is opt-in, and good-practices docs say to use it only for non-security-critical/mutating webhooks | Availability vs safety trade-off, made explicit per-webhook | [k8s/k8s#128162](https://github.com/kubernetes/kubernetes/issues/128162) (2024): pod admission can still fail even when *every* webhook is set to `Ignore`, because a shared 30s cross-webhook timeout budget can be exceeded — i.e. the fail-open guarantee itself has an edge case under compounding latency |
| OPA/Gatekeeper | Ships **fail-open** (`failurePolicy: Ignore`) by default for its own admission webhook | Explicitly documented trade-off: flipping to `Fail` (fail-closed) is supported, but can deadlock a cluster — if every node is lost, the webhook can't run, so no node can be re-admitted until the circular dependency is manually broken | [Gatekeeper: Failing Closed](https://open-policy-agent.github.io/gatekeeper/website/docs/failing-closed/) |
| GitHub branch protection + `CODEOWNERS` | **Silent fail-open**: a missing, empty, or all-invalid-entries `CODEOWNERS` file means "require review from code owners" is simply not enforced — any write-access approver satisfies it | Undocumented as a security default; only surfaced as a UI warning banner | [GitHub: About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners); the "List CODEOWNERS errors" API has its own documented bug returning an empty error list even when errors exist — [community discussion #55942](https://github.com/orgs/community/discussions/55942) |
| AWS IAM | **Fail-closed by design**: implicit deny — no matching Allow ⇒ Deny | Foundational to the whole model, not a special case | [AWS IAM policy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_AccessPolicyLanguage_Interplay.html) |
| SELinux | **Fail-closed by default**: enforcing is the default and recommended mode; permissive is an explicit, logged opt-out for policy development | Never a silent default | [Red Hat: SELinux states and modes](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/html/selinux_users_and_administrators_guide/sect-security-enhanced_linux-introduction-selinux_modes) |
| CSP report-only vs enforce | Report-Only is **deliberately** fail-open (logs only, blocks nothing) — used as a staged rollout step, never a silent fallback; a genuinely **missing** CSP header is unambiguously fail-open and is treated by OWASP as a vulnerability outright | Explicit two-step rollout discipline | [content-security-policy.com: Report-Only](https://content-security-policy.com/report-only/); [OWASP CSP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html) |
| Terraform Sentinel/OPA on missing data | Historically **silent fail-open on `null`**: Terraform Enterprise pre-v202403-1 converted config nulls to "undefined," letting policies that mishandled null "erroneously execute" instead of erroring | HashiCorp corrected this in v202403-1 to error loudly on null misuse instead of silently passing — an explicit fix *away from* silent fail-open | [HashiCorp: Changes to Handling of Null values](https://support.hashicorp.com/hc/en-us/articles/26762947739923-Changes-to-Handling-of-Null-values-in-Sentinel-Worker-In-Terraform-Enterprise-v202403-1) |

**Takeaway:** the split is not arbitrary — controls that gate *identity/
authorization* default fail-closed unconditionally; controls that gate
*availability-affecting admission* sometimes ship fail-open, but always as
a **named, switchable, documented** trade-off with a stated cost to
reversing it. The only *silent, undocumented* fail-open found is GitHub
CODEOWNERS — this is the shape adr_0012 must avoid, not emulate.

## 3. The Migration Problem: Absent Field ⇒ Legacy Behavior

| Pattern | Absent-value meaning | Opt-in mechanism | Known trap |
|---|---|---|---|
| Node.js `package.json` `"type"` | Absent ⇒ CommonJS (pre-ESM legacy), frozen exactly | Explicit `"type": "module"`; `.cjs`/`.mjs` extensions always override regardless of the field | Node's own docs now tell authors to set the field explicitly even for CommonJS packages "to future-proof... in case the default type of Node.js ever changes" — an implicit admission that the absent-default's meaning is effectively frozen forever once tooling depends on it | [Node.js Modules: Packages](https://nodejs.org/api/packages.html) |
| Rust `edition` in `Cargo.toml` | Absent ⇒ edition 2015 (oldest), frozen exactly | Explicit `edition = "2021"` etc.; `cargo new` auto-writes the current edition, so the absent-default path only ever applies to pre-existing manifests, never new work | Mixed-edition linking is explicitly supported (a 2015 crate can depend on a 2018 one) — the standard shape avoids a big-bang migration | [Rust Edition Guide](https://doc.rust-lang.org/edition-guide/editions/) |
| Go `go` directive in `go.mod` | Historically inferred from the active toolchain at `go mod init` time | Go 1.21 changed the directive's meaning from "version used to compile" to "minimum required version"; Go 1.26 walked back `go mod init`'s default from "current toolchain version" to a deliberately **older** version | Even the *chosen default value* needed a later correction once the ecosystem showed the eager "always newest" default caused unwanted forced upgrades — the trap isn't only "absent vs present," it's that a present-but-wrong default also needs revisiting | [Go Modules Reference](https://go.dev/ref/mod); [golang/go#74748](https://github.com/golang/go/issues/74748) |
| Kubernetes feature gates | Alpha-gated fields are dropped/ignored ("field dropping") until the gate is enabled cluster-wide | Explicit, cluster-level opt-in flag, never per-object | Field-dropping means an object *can* silently lose a value it was written with if the gate isn't on where it's read — a variant of the same "absence reads as legacy" hazard, one layer down | [Kubernetes feature gates docs](https://kubernetes.io/docs/reference/command-line-tools-reference/feature-gates/) |
| DB schema migration nullable-column pattern | A new nullable column with no default is `NULL` for every pre-existing row — `NULL` doubles as "not yet migrated" | A backfill job or lazy-write populates it; only once backfill is complete does application code treat `NULL` as meaningful | If the backfill is silently incomplete, code that treats "`NULL` = legacy row" can't distinguish that from a genuinely-new row that legitimately has no value yet — the sentinel is overloaded | general pattern, well-established (not independently re-cited this pass) |

**Takeaway:** the standard shape is uniform: **absent marker freezes old
behavior exactly; new behavior is opt-in per-artifact; tooling nudges
authors toward writing the field explicitly going forward, precisely
because the absent-default's meaning can't be changed later without
breaking everything that already depends on it.** Go's toolchain-default
history is a second, distinct trap: getting the *default value itself*
right is an ongoing correction, not a one-time decision.

## 4. One-Way-Door / Irreversibility as a Machine-Detectable Signal

| Tool | What it actually detects (the proxy) | Escape hatch | Stated coverage limits |
|---|---|---|---|
| `strong_migrations` (Ruby) | Named, rule-based lock/rewrite-cost signatures: column type change, non-concurrent index, dropping a column, adding `NOT NULL` without a safe path, etc. — **not** semantic irreversibility | `safety_assured { }` block — no justification or expiry enforced by the tool; relies on code review | Own docs: "you probably don't need this gem for smaller projects" — deliberately conservative/context-blind by design | [ankane/strong_migrations](https://github.com/ankane/strong_migrations) |
| `squawk` (Postgres linter) | Same shape: AST rules keyed to lock acquisition and backward-compat breakage (`require-concurrent-index-creation`, `adding-not-nullable-field`, `ban-drop-column`, …) | Per-rule config-based ignore | Rule-scoped by design, not a general classifier | [squawkhq.com/docs/rules](https://squawkhq.com/docs/rules) |
| `buf breaking` | Mechanically-provable wire/source incompatibility only (deletion, rename, retype, renumber), categorized by blast radius (FILE < PACKAGE < WIRE_JSON < WIRE) | Category selection (choose a looser level); no per-change suppression documented | Explicitly out of scope: "custom options... a generic compatibility rule can't reason about them" | [buf.build/docs/breaking/rules](https://buf.build/docs/breaking/rules) |
| `cargo-semver-checks` | Rustdoc-JSON diff against dozens of named lints for public-API breakage | N/A (linter, not enforced at compile time) | Candid: "No, it will not — not yet!" catch every semver violation; known gaps include type changes inside signatures/fields and generics/lifetimes; treats any false positive as a bug | [obi1kenobi/cargo-semver-checks](https://github.com/obi1kenobi/cargo-semver-checks) |

**Takeaway:** no tool here claims to detect irreversibility as a semantic
judgment. Each substitutes a **narrow, named, mechanically-checkable
proxy** and is explicit about what it misses. None publishes a measured
false-positive rate; instead, each keeps the rule set narrow enough that
any false positive is individually arguable in code review, paired with a
cheap, local override. This is direct precedent for adr_0012's "one-way-door"
flag: prefer a short list of named mechanical proxies (deletes a public
symbol, removes a config key, drops a column, changes a wire format) over
a general irreversibility classifier.

## 5. "Hub" / High-Fan-In File Detection

| Approach | Method | Threshold | Validation |
|---|---|---|---|
| CodeScene / Code Maat (Adam Tornhill, "Your Code as a Crime Scene") | Hotspot = change frequency × complexity/code-health; change coupling = files that co-change above a threshold | CodeScene's own hotspot maps use a **20% co-change threshold** by default | CodeScene's own docs claim "a strong correlation between Hotspots and software defects," citing an example where hotspots comprising 1.2% of a codebase held 45% of detected bugs — **this is vendor-self-reported, not independently peer-reviewed; treat as directionally suggestive, flagged unverified for a stronger claim** |
| dependency-cruiser | Generic rules engine for dependency graphs (circular deps, orphans, forbidden layers) | **No built-in fan-in/"god file" detector or threshold** — a team must write a custom rule | N/A — negative evidence that no mainstream JS dependency tool ships an out-of-the-box, validated fan-in cutoff |
| Google build-graph fan-in as a risk signal | Not found with a citable primary source in this pass (search budget exhausted before this could be run down) | — | **Unverified — not found**, do not cite as precedent |

**Takeaway:** "many concurrent touches ⇒ higher risk" is a named,
practiced methodology (change coupling / hotspots) with a specific
vendor-published threshold (20%) and a specific vendor-published
correlation claim — but the strongest supporting number is self-reported
by the tool's own vendor, not independently replicated, and no mainstream
tool treats the cutoff as a universal constant; every implementation
studied here makes it a per-repo tunable. adr_0012 should treat "file
touched by another concurrent work package" as a directionally-reasonable
heuristic worth flagging, not as validated science, and should not
hard-code a magic fan-in number.

## 6. Escape Hatches and Their Discipline

| Mechanism | Justification required? | Expiry? | Audit trail / visibility | What actually makes it safe |
|---|---|---|---|---|
| Kubernetes PSA exemptions | No — statically configured by an admin, not per-request | No | Static config list, not a runtime audit log | **Narrow scoping is the safety property**: docs explicitly warn "controller service accounts should generally not be exempted, as doing so would implicitly exempt any user who can create the corresponding workload resource" — safety comes from scoping tight enough that the exemption can't be laundered through a more-privileged path | [Kubernetes: Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/) |
| `nosemgrep` | No | No | **Yes — persistent**: "Ignoring code through this method still generates a finding. The finding is automatically set to the Ignored triage state" — suppressed findings remain visible/queryable, not deleted | Persistence-of-record: the override doesn't erase the underlying finding | [Semgrep: Ignoring findings](https://docs.semgrep.dev/ignoring-files-folders-code) |
| `strong_migrations` `safety_assured` | No (tool-enforced) | No | No tool-level trail; relies entirely on code review | Cheapness + code review, not tooling |
| Terraform `lifecycle { ignore_changes }` | No | No — explicitly a **permanent** statement, not framed as temporary | Visible in the resource config/diff itself | Scoped per-attribute (or `all`); docs warn that stacking with `prevent_destroy` "makes certain configuration changes impossible to apply" — a compounding escape hatch can remove your own reversal path | [Terraform: lifecycle meta-argument](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle) |

**Takeaway:** none of these bake mandatory justification strings, expiry,
or a second-approver into the *mechanism* — that discipline is uniformly
delegated to code review / org process. What the well-designed ones *do*
enforce structurally is: (a) **narrow scoping** — per-rule, per-attribute,
per-username, never a single global kill switch, and (b) **durable
visibility** — the override remains discoverable after the fact (a
persisted Ignored-state finding, a diff-visible config block, a named
exemption list) rather than vanishing silently.

## 7. Announce/Preview Surfaces

| Tool | What it previews | What makes it actionable |
|---|---|---|
| `terraform plan` | Aggregate `+`/`~`/`-`/`-/+` counts plus a per-resource diff, summarized as "Plan: X to add, Y to change, Z to destroy" | Deliberately separated from `apply`; a saved plan becomes a reviewable PR artifact | [Terraform plan docs](https://developer.hashicorp.com/terraform/cli/commands/plan) |
| `helm template` / `kubectl diff` | Client-side rendering of the effective manifest before it reaches the cluster | Actionable for content review, but `helm template`'s own docs flag that it explicitly skips server-side validation (e.g. CRD schema checks) — a preview can be actionable on one axis while silent on another | [Helm: helm template](https://helm.sh/docs/helm/helm_template/) |
| OPA `eval --explain {notes,fails,full,debug}` | Graduated verbosity for **why** a decision was reached, not just what the decision is | Drill-down on demand from a summary to a full evaluation trace — the closest precedent for showing *which flag fired and why*, not just the resulting tier | [OPA CLI docs](https://www.openpolicyagent.org/docs/latest/cli/) |
| Bazel `--announce_rc` | Prints every flag actually in effect, and which `.bazelrc` file it came from, before the build runs | Source-attributed: names *where* each effective value came from, not just its final value | general knowledge (Bazel docs), not independently re-fetched this pass |

**Takeaway:** an actionable preview across all of these has the same three
properties: **(1) aggregate first** (counts/histogram, so a large batch is
sanity-checkable at a glance), **(2) drill-down on demand** to the
individual decision and its cause, and **(3) source-attributed** — naming
*where* each effective value came from, not only its final value. A
preview that shows only the final aggregate tier without provenance is the
noise failure mode.

## Recommendation for adr_0012

**1. Flag taxonomy shape.** A closed, versioned enumeration of named flags
(not open-ended free text), each independently sourced and independently
degradable, with an explicit catch-all clause ("an unrecognized or
malformed input escalates, it does not default to a known flag"). Mirrors
OpenSSF Scorecard's closed check list and OWASP ASVS's closed, nested
chapter/level structure; the catch-all mirrors PCI DSS v4.0.1's response to
its own taxonomy being outgrown (a new named "connected-to" category plus
a general impact-based backstop, added in a version bump, not ad hoc).
Source: [ossf/scorecard checks.md](https://github.com/ossf/scorecard/blob/main/docs/checks.md); [SecurityMetrics: PCI Scope Categories](https://www.securitymetrics.com/blog/pci-scope-categories-keeping-your-card-data-separate).

**2. Degrade rule when a flag source is missing — stated as a rule, not a
preference:** *A flag whose source is absent, unreadable, or malformed is
treated as present (true) for tier computation; it is never treated as
absent (false).* This is the fail-closed branch, chosen because every
precedent that gates identity/authorization defaults this way
unconditionally (AWS IAM implicit deny, SELinux enforcing-by-default), and
even the systems that ship fail-open do so only for availability reasons,
never for a genuinely-unknown security-relevant input, and always as a
named, documented, switchable choice — never silently. The negative
precedent to actively avoid is GitHub's `CODEOWNERS`: a missing or
malformed file silently disables "require review from code owners" with no
operator-facing error, which is exactly the "missed flag → collapsed
pipeline" failure adr_0012 must not reproduce. Source: [AWS IAM policy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_AccessPolicyLanguage_Interplay.html); [GitHub: About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) (negative precedent); [Gatekeeper: Failing Closed](https://open-policy-agent.github.io/gatekeeper/website/docs/failing-closed/) (documents the fail-open/fail-closed trade-off explicitly, for contrast).

**3. Migration shape for pre-existing plans.** Give every hex plan a
real, explicit generation-version marker going forward; a plan's *absence*
of that marker (i.e., it predates the policy) is the only thing that
legitimately means "compute tier under legacy rules, unchanged" — matching
Node's `package.json` `"type"` and Rust's `edition` field, both of which
freeze old behavior exactly for pre-existing artifacts and require new
artifacts to opt in explicitly (and both ecosystems now tell authors to
write the field explicitly rather than rely on the default, because the
absent-default's meaning can never safely change later). Do **not** let a
missing *individual* flag-source row inside an otherwise policy-aware plan
borrow this same "it's legacy" excuse — that collapses into the
CODEOWNERS trap from recommendation 2. A missing whole-plan marker is a
legitimate legacy signal; a missing single flag inside a current plan is
the missing-input case, and rule 2 applies. Source: [Node.js Modules: Packages](https://nodejs.org/api/packages.html); [Rust Edition Guide](https://doc.rust-lang.org/edition-guide/editions/); [Go Modules Reference](https://go.dev/ref/mod) (as a caution that even a chosen default value needs revisiting — Go 1.21 and 1.26 both changed the `go` directive's default semantics after real-world friction).

**4. Escape-hatch discipline.** Do not build mandatory justification
strings, expiry, or a second-approver into the override mechanism itself —
no precedent studied here requires that structurally (`strong_migrations`,
`nosemgrep`, Kubernetes PSA exemptions, and Terraform `ignore_changes` all
delegate that discipline to code review/org process, not the tool). Do
require the two properties that are structurally common to every
well-designed escape hatch found: **(a) narrow scoping** — an override
names one flag on one work package, never a global "skip tier
computation" switch, matching PSA's per-username/namespace scoping and
`nosemgrep`'s per-rule-id targeting; and **(b) durable visibility** — the
override must appear in the plan's diff/preview (per §7's preview-surface
findings) rather than vanish, matching `nosemgrep`'s persisted
Ignored-state findings and Terraform's `ignore_changes` being a permanent,
diff-visible declaration rather than a silent runtime suppression. Source:
[Semgrep: Ignoring findings](https://docs.semgrep.dev/ignoring-files-folders-code); [Kubernetes: Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/); [Terraform: lifecycle meta-argument](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle).

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| [ossf/scorecard checks.md](https://github.com/ossf/scorecard/blob/main/docs/checks.md) | Docs (fetched) | fetched 2026-09-05 | Closed-enumeration precedent, §1, Rec. 1 |
| [slsa.dev spec v1.2](https://slsa.dev/spec/v1.2/) | Docs (search only) | current as of search | SLSA level/track structure, §1 — flagged partially unverified |
| [NIST SSDF (SP 800-218) overview](https://www.nist.gov/document/eo-14028-presentation-nist-secure-software-development-framework-ssdf) | Gov docs (search) | — | Practice-group enumeration, §1 |
| [SoftwareMill: Implementing OWASP ASVS](https://softwaremill.com/implementing-owasp-asvs/) | Blog (search) | — | ASVS level/chapter structure, §1 |
| [Codific: OWASP ASVS overview](https://codific.com/owasp-asvs-a-comprehensive-overview/) | Blog (search) | — | ASVS CWE/CRE mapping, §1 |
| [SecurityMetrics: PCI Scope Categories](https://www.securitymetrics.com/blog/pci-scope-categories-keeping-your-card-data-separate) | Blog (search) | — | PCI DSS scoping categories, §1, Rec. 1 |
| [Secureframe: PCI Scope](https://secureframe.com/blog/pci-scope) | Blog (search) | — | PCI DSS v4.0.1 "connected-to" category, §1 |
| [Kubernetes: Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/) | Official docs (search) | — | failurePolicy Fail/Ignore semantics, §2 |
| [k8s/kubernetes#128162](https://github.com/kubernetes/kubernetes/issues/128162) | GitHub issue | 2024 | Documented fail-open edge-case incident, §2 |
| [Gatekeeper: Failing Closed](https://open-policy-agent.github.io/gatekeeper/website/docs/failing-closed/) | Official docs (fetched via search) | — | Fail-open default + fail-closed deadlock trade-off, §2, Rec. 2 |
| [GitHub: About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) | Official docs (search) | — | Silent fail-open on missing/malformed CODEOWNERS, §2, Rec. 2 |
| [community discussion #55942](https://github.com/orgs/community/discussions/55942) | GitHub discussion | — | CODEOWNERS-errors API bug, §2 |
| [AWS IAM policy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_AccessPolicyLanguage_Interplay.html) | Official docs (search) | — | Implicit-deny fail-closed default, §2, Rec. 2 |
| [Red Hat: SELinux states and modes](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/html/selinux_users_and_administrators_guide/sect-security-enhanced_linux-introduction-selinux_modes) | Official docs (search) | — | Enforcing-by-default fail-closed, §2 |
| [content-security-policy.com: Report-Only](https://content-security-policy.com/report-only/) | Reference site (search) | — | CSP staged fail-open rollout, §2 |
| [OWASP CSP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html) | Official docs (search) | — | Missing-CSP-header as vulnerability, §2 |
| [HashiCorp: Null value handling change](https://support.hashicorp.com/hc/en-us/articles/26762947739923-Changes-to-Handling-of-Null-values-in-Sentinel-Worker-In-Terraform-Enterprise-v202403-1) | Vendor support article (search) | v202403-1 | Sentinel silent-null-fail-open fix, §2 |
| [Node.js Modules: Packages](https://nodejs.org/api/packages.html) | Official docs (search) | v26.8.1 docs | `"type"` field default/migration pattern, §3, Rec. 3 |
| [Rust Edition Guide](https://doc.rust-lang.org/edition-guide/editions/) | Official docs (search) | — | `edition` field default/migration pattern, §3, Rec. 3 |
| [Go Modules Reference](https://go.dev/ref/mod) | Official docs (search) | — | `go` directive semantics, §3, Rec. 3 |
| [golang/go#74748](https://github.com/golang/go/issues/74748) | GitHub issue | 2026 | `go mod init` default-version walk-back, §3 |
| [Kubernetes feature gates docs](https://people.wikimedia.org/~jayme/k8s-docs/v1.16/docs/reference/command-line-tools-reference/feature-gates/) | Official docs (search) | — | Field-dropping/alpha-gate pattern, §3 |
| [ankane/strong_migrations](https://github.com/ankane/strong_migrations) | Docs (fetched) | fetched 2026-09-05 | Migration-safety proxy rules + `safety_assured` escape hatch, §4, §6 |
| [squawkhq.com/docs/rules](https://squawkhq.com/docs/rules) | Docs (fetched) | fetched 2026-09-05 | Postgres migration lint rules, §4 |
| [buf.build/docs/breaking/rules](https://buf.build/docs/breaking/rules) | Docs (fetched) | fetched 2026-09-05 | Breaking-change blast-radius categories, §4 |
| [obi1kenobi/cargo-semver-checks](https://github.com/obi1kenobi/cargo-semver-checks) | Docs (fetched) | fetched 2026-09-05 | Semver-lint coverage and stated gaps, §4, Rec. 1 |
| CodeScene hotspot/change-coupling docs (via search summary; direct fetch 404'd) | Vendor docs (search) | — | Hotspot correlation claim (flagged vendor-self-reported/unverified), §5 |
| [sverweij/dependency-cruiser](https://github.com/sverweij/dependency-cruiser) | Docs (fetched) | fetched 2026-09-05 | No built-in fan-in/god-file detector, §5 |
| [docs.semgrep.dev: Ignoring findings](https://docs.semgrep.dev/ignoring-files-folders-code) | Official docs (fetched) | fetched 2026-09-05 | `nosemgrep` scoping + persisted Ignored state, §6, Rec. 4 |
| [Kubernetes: Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/) | Official docs (fetched) | fetched 2026-09-05 | PSA exemption scoping discipline, §6, Rec. 4 |
| [Terraform: lifecycle meta-argument](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle) | Official docs (fetched) | fetched 2026-09-05 | `ignore_changes` permanence + stacking risk, §6, Rec. 4 |
| [Terraform: plan command](https://developer.hashicorp.com/terraform/cli/commands/plan) | Official docs (fetched) | fetched 2026-09-05 | Aggregate + per-resource preview shape, §7 |
| [Helm: helm template](https://helm.sh/docs/helm/helm_template/) | Official docs (fetched) | fetched 2026-09-05 | Client-side preview + its server-side-validation gap, §7 |
| [OPA CLI docs](https://www.openpolicyagent.org/docs/latest/cli/) | Official docs (search) | — | `--explain` graduated verbosity, §7 |
