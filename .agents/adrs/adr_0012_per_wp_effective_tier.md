# ADR: the per-WP effective tier — plan tier becomes a ceiling, each work package derives its own

## Metadata

**Status:** Proposed
**Date:** 2026-09-05
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A (originated in the 2026-09-05 root-cause analysis, persisted as [`.agents/research/rca-review-fix-loop-wall-clock.md`](../research/rca-review-fix-loop-wall-clock.md))
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below
      (one `DESIGN.md` round with **four** amendments — one superseding the
      2026-07-20 Review-budget addendum by pointer, one amending
      `protocol.md`'s canonical four-phase contract-first TDD list, one
      amending `protocol.md`'s *"no schema-version marker — the presence of
      the field is the signal"* rule, which this ADR's marker breaks by
      carrying a value space and a hard refusal, and one amending the
      **thin-dispatcher / sole-definition rule** (`DESIGN.md` rounds 10 and
      13, and `adr_0010` C-916's *"No tier file gains a rule"*), because
      `hex-execute`'s three tier files do gain one — **plus one new binding
      rule that amends no existing `DESIGN.md` position** (C-1117's mandatory
      ceiling-tier branch review), an explicit record that the
      *Plan visualization* lock is **not** amended, and a round-number
      collision with `plan_wave0_quick_wins` — see
      [Constitution deviations](#constitution-deviations))
**Domain Tags:** performance, devops
**Supersedes:** N/A as a whole ADR. It **partially supersedes `adr_0010`'s
`Review` column semantics** — the column survives with its direction
flipped and its baseline moved — and it takes two `plan_wave0_quick_wins`
contracts out of service in plans that carry this ADR's generation marker:
C-928's guard is **suppressed** (its downward half is not vacuous but
*contradicted* — it declares a plan defect exactly where this ADR sanctions
an escape hatch), and C-930's histogram has its bucket key replaced. Both
are recorded as errata rather than as a supersession header, because in
every legacy plan the superseded text stays true forever.
**Superseded By:** N/A

*Template slots deliberately omitted: **Quantified Impact** as a standalone
section (the numbers are § Decision Outcome › The arithmetic, and a second
copy would drift — the same call `adr_0010` made), **Technical Details ›
Data Model** and **› API Contract** (there are no entities and no
interfaces; the durable objects are one optional Status-block line and a
pure function over cells that already exist), and **Implementation Plan**
as a numbered checklist (§ Migration / rollout plan carries it in edit-site
order, which is the form the implementing plan actually consumes).*

## Context

A size-**S** work package — 2 files, **+78/−3** — took **3 h 06** and
**9 serial worker round trips**
([`rca-review-fix-loop-wall-clock.md`](../research/rca-review-fix-loop-wall-clock.md);
`ocx-sion`, plan `plan_index_claim_command.md`, tier **high**, 19 WPs, 16 of
them `panel`; WP-1 → commit
[19251402](https://github.com/ocx-sh/ocx/commit/19251402)). The RCA's verdict
is one sentence and it is the premise of this ADR: **wall clock scales with
serial worker round-trips, not LOC.** `adr_0010`'s delta scoping cut *bytes
read per round*; on an 80-line diff that was already ≈ 0, while the round-trip
count went **up**.

Three of the RCA's six ranked root causes are this ADR's:

1. **Pipeline depth is constant.** "Stub→Specify→Implement→R1→fix→R2→converged
   pass→merge ≥ 7 serial round trips **at every tier**" — `tier-low.md` says so
   in its own words: *"Keep the contract-first TDD skeleton (Stub → Specify →
   Implement → Review-Fix) unchanged; only scale the worker count, review
   breadth, and loop rounds down."* At ~12 min per deep-reasoning trip that is a
   ~90 min floor **before the first finding exists**.
2. **Tier is plan-global, and the only per-WP dial is `Review`, set wrong.**
   Tier `high` forced deep-reasoning `tester` and `builder:implement` plus
   adversarial breadth on all 19 WPs. `protocol.md` § Parallel-by-default
   decomposition's own heuristic — *"docs-only or tiny low-risk work (~≤50
   expected lines, no security-sensitive or hot-path files) → `self`"* — says
   WP-1 should have been `self`; it was authored `panel`. **The plan-side guard
   exists only upward** (a `self` on a security WP is a defect); nothing caught
   a budget set too high, and no dial anywhere lowers **phases** or **model
   class**.
3. **All-deep-reasoning, plus stages no hex file defines.** `ocx`'s
   `hex.md › Preferences` pins every reviewer role to deep-reasoning at every
   tier, and the traced run's first 17 minutes went to an "edge-case hunt"
   reviewer that appears in **no hex file at all**. Opus share 69% → 76%.

**Root causes 4, 5 and 6 are explicitly not this ADR's.** Worker liveness (a
silently dead worker cost 30 min), the missing adversary deadline (a 95-minute
hole in a second traced run), single-threaded sub-orchestration (one
orchestrator serialized five WPs; WP-1 sat idle for the last 53 minutes of its
own run), and the unscoped Implement / loop-exit gates belong to **`adr_0013`**
(liveness, resources, per-WP sub-orchestration) and to
[`plan_wave0_quick_wins`](../plans/plan_wave0_quick_wins.md). This ADR does
not design them, and § The arithmetic attributes their minutes to them rather
than claiming them.

### The central tension

The rule being replaced is not arbitrary. **`Review` only ever lowers, and its
baseline is the tier's full panel**, because a budget column whose unsafe
direction is reachable is a budget column that will eventually be set unsafely
— `adr_0010` C-905 states that as an invariant and it is correct. Deriving the
budget instead means a *function* now decides how much review a change gets,
and a function can be wrong in the one direction that matters.

What makes the trade defensible is that the invariant was protecting the wrong
end. `Review`'s baseline sits at the maximum, so the column can only be
mis-authored *downward* — and the traced defect is the opposite one: a budget
authored **too high**, which no rule anywhere catches because no rule looks.
Meanwhile the safe direction is not free: 16 `panel` budgets on a 19-WP plan is
16 adversarial panels, and the ADR's whole premise is that those panels cost
round trips, not bytes.

The industry's answer to exactly this shape is uniform and is quoted in
§ Industry Context: **derive the class from the unit's own declared spec,
never let the unit author the class, and pair every collapsed fast path with a
mandatory backstop that cannot itself be collapsed.** Kubernetes does not let
you write `QoS: Guaranteed`; it computes it from requests and limits you *did*
write. That is this ADR's shape exactly, and the backstops are where its
correctness lives.

## Decision Drivers

1. **Wall-clock, honestly measured — and honestly attributed.** The RCA
   decomposes 186 minutes across six owners. This ADR claims only its own
   segments, states what it cannot reach, and says plainly that the
   program's ≤ 30 min target is **not** met by this ADR alone.
2. **The false negative is the only failure that matters.** Google's Test
   Selection Safety and Evaluation Framework names the asymmetry: a missed
   regression ships silently, a spurious escalation costs compute. Every
   default in this ADR is set on that asymmetry, and where one is not
   (`door`), the exception is argued rather than smuggled.
3. **Zero new config vocabulary and zero new plan-table columns.**
   `config.md`'s top-level key set froze at six (`adr_0003` C-223) and
   `DESIGN.md`'s *Plan visualization* lock has now been amended **four
   times**. A fifth amendment for a value derivable from cells that already
   exist would be a cost paid for nothing.
4. **Additive compatibility, to the byte.** An approved plan must execute
   unchanged, forever, with no prompt and no error. The failure this driver
   exists to prevent is a bundle upgrade silently reinterpreting a plan
   somebody already approved.
5. **Sole definition sites, budgeted explicitly.** `DESIGN.md` round 13
   records the cost of getting this wrong in its own words: nine
   restatements of one clause meant *"a one-line contract change became a
   ten-file diff"*, and it names the repair — *"for `protocol.md` to own the
   sentence and the tier files to link it."* The vocabulary this ADR touches
   (`tier`, `Review`, `panel`, the phase list) is restated across roughly
   twenty files. Canonical text lands **once** in `protocol.md`; every other
   site links or takes a one-clause qualifier; a site whose sentence stays
   true is not touched at all.
6. **The derived value must be explainable from the announce block alone.**
   Kubernetes' BestEffort class is the documented anti-pattern: a workload
   silently lands in the worst class by omission, and nothing proactively
   says so. "Why was this WP classified `low`?" must be answerable without
   re-running anything — **against the block that carries the value the WP
   actually ran under.** The function is recomputed at each WP's own spawn
   time (C-1101), so the Discover-time histogram is a **snapshot, labelled as
   one**, and the per-WP value that governed the run is announced by
   `/hex-execute` at that WP's spawn (C-1119, C-1120) and again in the
   execution handoff (C-1118).
7. **No new state, at any depth.** `adr_0010` driver 5 is unchanged and this
   ADR is the first that could have broken it, because a derivation
   *invites* a cached result. Nothing is persisted; the derivation is a pure
   function of the plan artifact plus one pointer.

## Industry Context & Research

Three artifacts were commissioned for this ADR —
[`adr0012-precedent.md`](../research/adr0012-precedent.md) (ceiling+derived
design precedent),
[`adr0012-risk-scoring.md`](../research/adr0012-risk-scoring.md) (change-risk
scoring and size heuristics),
[`adr0012-risk-flags.md`](../research/adr0012-risk-flags.md) (flag taxonomy,
degrade rules, migration markers) — on top of the RCA. All are dated
2026-09-05 and expire 2027-03-05.

**Derived-class-from-authored-spec is a real, primary-source pattern, and it
splits cleanly from the weaker thing it is often confused with.**
`adr0012-precedent.md` separates **(A)** ceiling plus freely-authored override
— Bazel test `size`→`timeout` (small=60 s … enormous=3600 s, where *"all
combinations of `size` and `timeout` are legal"*), GitHub Actions
`timeout-minutes` down the workflow→job→step chain, GitLab CI `default:` — from
**(B)** genuinely derived classification with no direct authoring: **Kubernetes
Pod QoS class**, computed solely from request/limit equality, *not directly
settable*, exposed but never assigned. This ADR is pattern **(B)**, and the
research says so explicitly: Bazel's flavour is *"a materially weaker guarantee
— a WP could just declare itself high-tier every time."* Anthropic's own
adaptive thinking is the live second instance — an authored `effort` ceiling
under which the model *"evaluates the complexity of each request and decides
whether and how much to think"* — and Anthropic's deprecation of flat
`budget_tokens` on newer models is evidence the direction of travel is toward
ceiling+derived, not away from it.

**QoS also answers the sharpest objection to this design before it is raised.**
QoS is derived — but from `requests` and `limits` the operator *authored*.
Derived-from-authored-primitives is the pattern; derived-from-nothing is not
available to anybody. That is the precedent for `size` remaining an authored
cell while the *class* it feeds is not (§ Judgment calls, call 4).

**Every collapsed fast path in the survey pairs with a mandatory,
non-collapsible backstop.** Zuul's gate pipeline re-tests speculatively against
the true future merge state regardless of what the fast, advisory *check*
pipeline reported; Gerrit's `Verified` label is a submit requirement
independent of the check vote; a CI smoke test is documented universally as a
**pre-filter, never a substitute**. `adr0012-precedent.md` finding 6 states it
as a universal: *"none of the researched systems let a fast path substitute for
the final gate; it only pre-filters into it."* This is the direct authority for
§ E's two backstops.

**No mature system scales effort down on size alone.**
`adr0012-risk-scoring.md`'s direct answer is unambiguous: every system that
scales effort by change size uses **two independent axes that must both clear**
— a cheap mechanical size signal, and a domain-risk signal (path sensitivity,
ownership, churn) — and *"no system in this research trusts size alone to lower
effort."* Pure-LOC-only effort estimation is listed under *Declining* with the
note *"no production system found relying on this alone."* This is why the
function dual-gates and why a set flag defeats any size.

**The ~50-line `S` threshold is defensible, as one of two gates.** Cisco /
SmartBear's ~2,500-review, 3.2 M-LOC study puts the optimal review chunk at
**200–400 LOC**, with defect discovery of 70–90 % at ≤ 400 LOC and inspection
rates above ~450 LOC/hour dropping into below-average defect density in 87 % of
observed reviews; Google's own internal CL-size guidance is tighter still
(*"100 lines is usually a reasonable size for a CL"*), and **file count
multiplies size risk rather than forming an independent axis** — 200 lines in
one file is fine, the same 200 across 50 files is not. Hex's shipped ~≤50-line
figure sits conservatively inside every one of those bands. The same research
supplies the base rate that makes the fast path worth having at all: **61 % of
reviews in the Cisco corpus found zero defects** — most changes genuinely are
safe, and the literature's whole point is that size alone cannot tell you which
39 % are not.

**Hub-ness is validated — under a different name, on a different graph, and the
difference must be stated.** Zimmermann & Nagappan (ICSE 2008, Windows Server
2003) show network-centrality metrics on a **static binary dependency graph**
beating traditional complexity metrics by **+10 percentage points of recall**
and identifying **60 % of the binaries developers independently flagged as
"critical" against 30 % for complexity metrics**. `adr0012-risk-scoring.md`
finding 9 then draws the line this ADR must not cross: *"this is a static
structural dependency graph … not the specific 'file that other
concurrently-open changes also touch' collision signal hex is asking about …
Treat 'concurrent-PR collision on the same file' specifically as **unverified
as its own named, published metric** — it's a reasonable extrapolation from
hub-ness/co-change, not a metric with its own citation."*
`adr0012-risk-flags.md` § 5 agrees from the tooling side: CodeScene's 20 %
co-change threshold and its hotspot/defect correlation are **vendor
self-reported**, `dependency-cruiser` ships **no** built-in fan-in detector, and
no mainstream tool treats a fan-in cutoff as a universal constant. **This is
exactly why `hub` floors at `medium` and not at the ceiling** (§ Judgment
calls, call 1).

**Ownership fragmentation is load-bearing and is nonetheless dropped here.**
Bird, Nagappan & Murphy (FSE 2011, *"Don't Touch My Code!"*, Windows Vista and
7) find the number of low-expertise contributors and the top owner's ownership
share correlate with both pre-release faults and post-release failures, and
that removing low-expertise-contributor data **substantially degrades** the
model — it is not safely droppable *as a predictor*. It is dropped as a *flag*
here for a mechanism reason, named as a departure in § Departures.

**Fail-closed on a missing policy input is the rule; the one clean
counter-example is the one to avoid.** `adr0012-risk-flags.md` § 2 splits the
field: controls gating **identity/authorization** default fail-closed
unconditionally — **AWS IAM's implicit deny** (no matching Allow ⇒ Deny),
SELinux enforcing-by-default — while controls gating **availability-affecting
admission** sometimes ship fail-open (OPA/Gatekeeper's `failurePolicy: Ignore`,
which would otherwise deadlock a cluster), but *always as a named, switchable,
documented* trade-off. The single **silent, undocumented** fail-open found in
the whole survey is **GitHub branch protection with CODEOWNERS**: a missing,
empty, or all-invalid file makes *"require review from code owners"* simply not
enforce, with no operator-facing signal beyond a UI banner — and the API that
would list the errors has its own documented bug returning an empty list. That
is precisely the failure shape this ADR must not reproduce: **a missed flag
collapsing a pipeline, silently.**

**Closed, versioned enumerations with an explicit catch-all.** OpenSSF
Scorecard ships ~18 named checks extensible only by contribution to the tool;
OWASP ASVS ships 14 chapters in 3 nested levels; NIST SSDF ships 4 practice
groups, 19 practices, 42 tasks. The one surveyed taxonomy that got outgrown —
PCI DSS's in-scope/out-of-scope binary — responded in v4.0.1 with **a new named
category plus a catch-all principle in a version bump**, never with free text.
Recommendation 1 of that artifact turns this into the rule this ADR adopts
verbatim: *"an unrecognized or malformed input escalates, it does not default to
a known flag."*

**Absent marker = old behaviour, frozen exactly.** Node's `package.json`
`"type"` (absent ⇒ CommonJS), Rust's `edition` (absent ⇒ 2015), Go's `go`
directive — all three freeze the legacy behaviour for pre-existing artifacts
and make the new behaviour opt-in per artifact, and **all three ecosystems now
tell authors to write the field explicitly, precisely because the
absent-default's meaning can never safely change later**. Go supplies the
second, distinct trap: Go 1.21 changed the directive's *meaning* and Go 1.26
walked back `go mod init`'s chosen *default value* — getting the default right
is an ongoing correction, not a one-time decision. The same artifact draws the
boundary this ADR needs: *"A missing whole-plan marker is a legitimate legacy
signal; a missing single flag inside a current plan is the missing-input case,
and rule 2 applies."*

**Escape hatches: narrow scope and durable visibility, never mandatory
ceremony.** `nosemgrep` keeps the suppressed finding *visible* in an Ignored
state rather than deleting it; Kubernetes PSA exemptions are statically
enumerated per username/namespace with the docs warning that a
too-broad exemption can be laundered through a more-privileged path; Terraform's
`ignore_changes` is a permanent, diff-visible declaration. None of them
enforces a justification string, an expiry, or a second approver — that
discipline is delegated to review. **Two properties are structurally common:
narrow scoping and durable visibility.** Both are met here by the **raise**
hatch — `Review: panel`, one cell on one WP, visible in the plan's diff and in
the announce block.

**The research's "never a global skip switch" warning applies to the *reduce*
hatch, not the raise hatch, and that is where this design is weakest.** The
survey's warning is about breadth of effect, and the raise hatch has none: it
can only ever *add* review. The reduce path is the opposite shape. **One
project-wide attestation — a `hex.md › Pointers` row locating a convention file
that declares an empty security-sensitive set, or
`perspectives.security-sensitive-paths: none` — clears `sec` on every WP of
every plan in the repository, permanently, including files that do not exist
yet.** Measured against the survey's two
structural properties it passes one and fails the other: it is **durably
visible** (a version-controlled, diffable, blame-able line, exactly the
CODEOWNERS/`ignore_changes` shape) and it is **not narrowly scoped** — it is
precisely the *"too-broad exemption laundered through a more-privileged path"*
that Kubernetes PSA's own docs warn about, and it is closer to Terraform's
`ignore_changes` than to `nosemgrep`'s per-finding suppression. **This ADR does
not fix that** — a per-plan or per-path attestation would need a config key
driver 3 forbids and a vocabulary `adr_0003` C-223 froze. What it does instead
is refuse to let one attestation clear *both* conventions (C-1105 resolves
`sec` and `hot` independently), keep hex's own shipped triggers outside the
project's reach (C-1103), and state the residual here rather than in a
footnote. **It is the single broadest lever in the design and the owner should
read it as one.**

**A staged, simple pipeline outperforming an open-ended agentic one is a
published result, and it is the direct precedent for "collapse is
defensible".** *Agentless* (Xia, Deng, Dunn & Zhang, arXiv
[2407.01489](https://arxiv.org/abs/2407.01489), Jul 2024, rev. Oct 2024)
replaced multi-round agent scaffolds with a fixed three-phase
localize→repair→validate pipeline and beat every open-source agent on
SWE-bench Lite at a fraction of the cost per issue, concluding that the
complexity of agentic control flow was not where the value sat. **The caveat is
load-bearing and is stated rather than buried:** Agentless collapses
*open-ended tool use into fixed stages*; C-1108 collapses *three fixed stages
into one turn*, and one of the three is the write-tests-before-implementation
boundary. Those are not the same operation, and Agentless offers **no evidence
about merging a TDD write-test step into the implementation step**. It supports
the claim that a shallower pipeline can be as good; it does **not** settle open
question 2, and this ADR does not cite it as if it did.

**Self-reported evidence from the agent being evaluated is a known failure
mode.** Bondarenko et al. (*Demonstrating specification gaming in reasoning
models*, arXiv [2502.13295](https://arxiv.org/abs/2502.13295), Feb 2025) find
frontier reasoning models manipulating the evaluation itself rather than
solving the task when the grader is reachable. It is **adjacent precedent, not
a direct match** — their setting is an adversarial game environment, not a
worker returning a test transcript — but the mechanism is the one C-1108 was
originally exposed to: a claim checked only by the artifact its own author
produced. It is the named reason the red→green evidence moved from a
self-reported transcript to a **committed, orchestrator-re-run** check
(C-1108).

**A preview is actionable only when it is aggregate-first, drillable, and
source-attributed.** `terraform plan`'s *"Plan: X to add, Y to change, Z to
destroy"* over a per-resource diff; OPA's `eval --explain` graduated verbosity
for *why* a decision was reached; Bazel's `--announce_rc`, which prints every
flag in effect **and which `.bazelrc` it came from**. `adr0012-risk-flags.md`
§ 7's closing line is the specification for § F: *"A preview that shows only the
final aggregate tier without provenance is the noise failure mode."*

**Derived per-unit routing pays, with published numbers.** RouteLLM reports
**> 85 % cost reduction retaining 95 % of GPT-4 quality on MT Bench, routing
only 14 % of queries to the strong model**; FrugalGPT reports up to **98 % cost
reduction** matching the best individual model, or +4 % accuracy at equal cost.
Against that, `adr0012-precedent.md` finding 3 records the gap: per-unit model
routing in every mainstream agent framework — Aider's architect/editor split,
Claude Code's subagent `model:` frontmatter, the OpenAI Agents SDK — is
**authored per role, never derived per task**. Hex would be building this
derivation itself, with no off-the-shelf pattern to copy.

**One number nobody publishes.** `adr0012-risk-scoring.md` finding 16:
*"No published fast-path admission ratio found anywhere in this research."*
This ADR therefore states no target percentage of WPs that should reduce, and
§ Validation makes the measured reduction rate a dogfood output rather than an
acceptance threshold.

## Considered Options

Five options carry real design freedom. All five were scored; the two closest
are argued in prose afterwards, because the arithmetic does not carry either
call.

| | Option |
|---|---|
| **O1** | **Derived effective tier, plan tier as ceiling.** Each WP resolves `effective = f(size, sec, hot, hub, door)`, never above the plan tier, never authored. The effective tier drives phases, model class, review breadth and loop rounds. *(chosen)* |
| **O2** | **Keep the authored budget cell, add the downward guard, and bind the four axes to it.** [`plan_wave0_quick_wins`](../plans/plan_wave0_quick_wins.md) C-928 promoted from a quick win to the whole fix (`panel` on a small, single-area, flag-free WP becomes a plan defect, exactly as `self` on a security WP already is) — **and the phase collapse, the model-class drop and the round cap bound to the existing `Review: self` cell** rather than to a derived tier. Edit surface ≈ 3 sites: one `protocol.md` budget bullet, one `tier-low.md` clause, one `models.md` clause. |
| **O3** | **A per-WP authored `Tier` column.** A tenth plan-table column holding `low \| medium \| high`, capped at the plan tier, authored by the planner. |
| **O4** | **New tiers — `xhigh` / `max` above `high`, or a fourth tier below `low`.** Re-cut the tier vocabulary so the *plan* tier lands closer to the work. |
| **O5** | **A continuous risk score with a threshold.** Compute a numeric score per WP from size, churn, ownership, fan-in and path sensitivity; reduce below a cutoff. |

Criteria and weights. *Wall-clock* is the point of the exercise. *Correctness
residual* and *authoring-error surface* are the two ways this change can be
wrong — the second one matters because mis-authoring **is** the traced root
cause. *Bundle surface* and *additive compatibility* are what the house
constitution prices most heavily (drivers 3–5). *Explainability* is driver 6.

| Criterion | Weight | O1 | O2 | O3 | O4 | O5 |
|---|---|---|---|---|---|---|
| Wall-clock reduction | 5 | 5 | 5 | 4 | 1 | 4 |
| Correctness residual (lower risk = higher score) | 5 | 4 | 3 | 2 | 4 | 3 |
| Authoring-error surface (smaller = higher score) | 4 | 5 | 1 | 1 | 3 | 4 |
| Bundle surface / sole-definition cost (less = higher) | 4 | 3 | 5 | 2 | 2 | 1 |
| Additive compatibility | 4 | 4 | 3 | 3 | 2 | 3 |
| Explainability of the derived value | 3 | 4 | 5 | 5 | 4 | 1 |
| **Weighted total** (max 125) | | **105** | **91** | **69** | **65** | **70** |

**Correction against this ADR's own first draft, recorded rather than
smoothed.** The draft scored O2 at **98** on a misreading of `protocol.md`
§ The Review-Fix Loop: it credited `Review: self` with a "1-round loop" and
charged O2 with leaving R1 and R2 in place. The shipped clause says the
opposite — `self` means *"**no reviewer spawns in this loop**, and the WP skips
the Verify-Architecture reviewer"*. A correctly-authored `self` on WP-1
therefore removes **the whole Review-Fix Loop**: R1 (11 min), the round-2 fix
segment that only exists because R1 produced findings (39), and R2 (16) —
**66 minutes, 35 % of the traced 186**, against O1's 43 (23 %). **The draft's
central claim that O1 saves more than O2 was false and is withdrawn.**
Re-scored below on the corrected semantics, and the correction moves three
cells, not one — two of them **against** O2.

**Stated sensitivity: O1 beats O2 by fourteen points on a 125-point scale.**
That is wider than the draft's seven, but it is not carried by wall clock — the
two now tie there — and it is not robust: the whole margin sits in two criteria
(**correctness residual** and **authoring-error surface**) that moved for the
*same* reason, so a reader who rejects the argument below restores the near-tie.
**The arithmetic still does not carry this choice and is not claimed to.** O1's
genuine margins remain over O5 (35 points), O3 (36) and O4 (40); against O2 the
recommendation rests on the prose. It is named as a judgment call in
§ Judgment calls 8.

**Why O1 is chosen over O2 — and it is not because it saves more.** On wall
clock the two are a tie, and the reason is that **both need the same lever**:
the phase collapse (45 min → 18, three serial trips → one) is the dominant
segment and neither option reaches the ≤ 30 min band without it. O2's *extra*
minutes over O1 — 66 against 43 — are bought by reviewing **less**, not by
running a shallower pipeline: `self` is zero WP-level review, where O1's
effective `low` keeps `review=minimal`'s `quality` + `spec` batch. That is a
correctness difference, not a speed win, and it is why O2's **correctness
residual drops from 5 to 3** on the corrected reading.

Three grounds decide it, and the first is the whole argument:

1. **O1 gates the reduction on signals the author does not choose; O2 gates it
   entirely on one authored cell.** `sec`, `hot` and `hub` are read from the
   project's documented conventions and from the plan's own file-set
   intersection — a WP touching a flagged path resolves at the ceiling **no
   matter what its author wrote**. Under O2 the author writes `self` and the
   pipeline collapses, full stop. **This is the traced root cause's own shape**:
   WP-1's defect was an authored *class*, and O2 keeps classes authored while
   making a wrong one four times more expensive. That is the asymmetry driver 2
   names — O2's failure mode is silent and O1's is a spurious escalation.
2. **O2, extended this far, *is* O3 wearing the `Review` column's name.** Once
   the phase collapse, the model class and the round cap all read a
   freely-authored three-value cell, that cell is a per-WP `Tier` column with a
   misleading header. `adr0012-precedent.md` recommendation 2 disqualifies
   exactly this — a freely-restated field is *"fine for scheduling hints, not
   for something phases/model-class/review-breadth depend on"* — and it is why
   O2's **authoring-error surface drops from 2 to 1**, level with O3's.
   C-928's new guard does not repair it: it catches only `panel`-set-too-high.
   The `self`-set-too-low direction is caught by the *upward* guard, which is
   prose judgment (*"is this WP security-sensitive?"*) asked of the same author
   who just got it wrong.
3. **O2 is not free on compatibility either, and the draft scored it as if it
   were.** Binding new semantics to a cell that already exists in every
   approved plan means either a legacy `Review: self` WP silently starts
   collapsing phases and dropping model class on a bundle upgrade — driver 4's
   exact prohibited failure — or O2 needs the same generation marker O1 needs,
   which is where its 3-site edit surface becomes ~6. **Additive compatibility
   drops from 5 to 3.**

**What O2 keeps, and it is the real cost of choosing O1.** Its bundle surface
is genuinely ~6 sites against O1's ~22, and its explainability is perfect
because a human wrote the value. Those two criteria are why the margin is
fourteen and not forty. **O2's downward guard ships regardless** — it is
`plan_wave0_quick_wins` C-928 and it lands before this ADR does; what changes
under O1 is that it is suppressed in derived-generation plans (C-1112), not
that it was wrong.

**Why O3 loses.** It is the shortest path to the same four axes and it
reintroduces the defect it is meant to cure: **author error is the traced root
cause**, and a `Tier` cell is exactly as mis-authorable as the `Review` cell
that was set to `panel` on a 78-line WP. `adr0012-precedent.md` recommendation 2
is explicit that a freely-restated field is *"fine for scheduling hints, not for
something phases/model-class/review-breadth depend on."* It also costs a
**fifth** amendment to the `DESIGN.md` *Plan visualization* lock, whose column
enumeration has now been amended by explicit act four times (`status`, the
review budget, `Repo`, `Verify`) — a cost O1 pays zero of, because it adds no
column.

**Why O4 loses.** `protocol.md` § Tier grammar already reserves `xhigh` and
`max` for future overlay stacks, with the classifier forbidden from emitting
them and an explicit "`<tier>` reserved, running high" degrade for a user who
passes one. Spending a reserved tier here would buy nothing this ADR needs: the
problem is not that `high` is too coarse at the top, it is that **one tier
governs nineteen work packages of wildly different shapes**, which a fourth or
fifth *plan-global* tier does not change. Recorded as considered; the reserved
tiers are deliberately left unspent.

**Why O5 loses, and what it was right about.** A continuous score is the most
expressive option and the research disqualifies it on its own terms.
`adr0012-risk-scoring.md`: *"no numeric threshold available for
churn/entropy/ownership/fan-in cutoffs in the surveyed literature — these papers
validate the **features**, not a specific score cutoff, so hex should implement
them as boolean escalation flags (touched-file exceeds Nth-percentile churn /
fan-in **in this repo's own history**)."* A percentile against repo history is a
computation hex has nowhere to run at plan time and nowhere to store — driver 7
forbids the cache and `config.md` forbids the key. A three-value classification
is also *auditable in a sentence* — "S, no flags" — and a score is not; OPA's
`--explain` exists because a computed decision without a trace is unusable, and
a score would need one. What O5 was right about survives as § F's per-WP flag
provenance: the *inputs* are shown, itemized, every time — Scorecard's
recomputed per-check breakdown, without the arithmetic.

## Decision Outcome

**Chosen: O1**, implemented as twenty-four contracts, `C-1101`–`C-1124`, with
scenarios `S-1101`–`S-1111`. **The recommendation is unchanged from the first
draft; the argument for it is not** — see § Considered Options, where O2 is
re-scored on its real semantics and the claim that O1 saves more is withdrawn.

The shape in one paragraph: **the plan's `Tier` becomes a ceiling. Each work
package derives an *effective tier* from cells that already exist — `Size`,
`Expected Files`, `Verify` — plus one `hex.md › Pointers` row, by a pure
function that is never authored and never resolves above the ceiling. The
effective tier, not the plan tier, drives four things: which phases run, which
`models.md` cell each WP-scoped spawn reads, the `review=` breadth, and the
`loop-rounds` cap. At effective tier `low`, Stub + Specify + Implement collapse
into one builder spawn that commits stubs and tests before the implementation,
with the orchestrator re-running the project's test command at that commit and
requiring failure. A risk flag whose source is absent, unreadable, or malformed
reads `true`, so a project that has attested nothing runs at the ceiling on
every WP — byte-identically to today for plans whose `Review` cells are absent
or `panel`, and with more review where they are `self` or `light`. `Review`
survives with its direction flipped: it may now only raise, and `panel` raises
the WP to the ceiling — the one escape hatch. One optional Status line,
`- Effective-tier: derived`, is the generation marker; its absence is
pre-`adr_0012` semantics forever. Two backstops carry the correctness: the
merge-time re-derivation `adr_0010` already ships, and a branch-level
`/hex-review` that runs at no less than the plan's ceiling tier before the plan
can reach its terminal review state.**

### The function

Inputs, all from cells and pointers that **already exist** — no new plan-table
column, no new config key:

| Input | Source | Missing / unreadable ⇒ |
|---|---|---|
| `size` ∈ {S,M,L} | the table's existing `Size` cell, resolved against the size-class table (C-1102) | **`L`** |
| `sec` | any path in `Expected Files` matches **hex's own shipped security triggers** (auth/crypto/signing paths, dependency manifests and lockfiles, CI-workflow files, new package manifests — `classify.md`'s structural-marker table) **OR** the project's documented **security-sensitive** convention, located via the `hex.md › Pointers` row `memory.md`'s Pointers row already defines as *"the named source the high-risk merge trigger reads"*. The project half only ever **widens** (C-1103) | **`true`** |
| `hot` | the same source's **hot-path** convention | **`true`** |
| `hub` | any `(Repo, path)` pair in this WP's `Expected Files` also appears in **another** WP's `Expected Files`, any wave | **`true`** |
| `door` | the WP's `Verify` cell resolves to `full` | `false` |

Resolution, with ceiling `T` = the plan's `Tier`:

```
if sec or hot or door   → effective = T                  (no reduction)
elif hub                → effective = min(T, medium)
elif size == S          → effective = min(T, low)
elif size == M          → effective = min(T, medium)
else  (size == L)       → effective = T
```

`min` over the ordered vocabulary `low < medium < high`. **The effective tier
is never above the ceiling and is never authored.**

Two floors apply after the branches above, in this order: **a WP owned by a
*decomposing* coordinator floors at `min(T, medium)`** — `adr_0013`'s `C-1219`
Q2 kind, the coordinator that fans the WP out into sub-work-packages, because
`models.md` Rule 5 gives `coordinator` no `low` cell and a `low` derivation
there would leave that fan-out with no defined spawn (C-1109). **A *pipeline*
coordinator — `adr_0013`'s `C-1219` Q1 kind, which owns a WP's phase pipeline
and adds no sub-WPs — does not raise the floor**, or C-1108's collapse could
never fire under `adr_0013` at all (`C-1219` gives a coordinator to every ready
WP when the ready set is ≥ 2 and the harness can nest; `C-1220`(a) is the
exception). Then **`Review: panel` raises the WP to `T`**, the one escape
hatch (C-1112). The run's own `review=` and `loop-rounds` axes then apply as a
`min` **cap over the result**, never as an input to it (C-1110).

**One axis the effective tier deliberately does not move: the adversary gate.**
`hex-execute/overlays.md`'s per-tier adversary default (`low` → `off`, `high` →
`on`) is read from the **plan tier `T`**, never from a reduced WP's effective
tier, so a WP that derived `low` inside a `high` plan **still runs the
cross-model gate** (C-1110). The cross-model pass is a run-level assurance
decision, and letting a per-WP reduction switch it off is precisely the global
skip switch the escape-hatch research warns against.

**`T` is the plan's Status-block `Tier:` value**, not `/hex-execute`'s optional
run-tier argument (C-1101). **The whole function is recomputed at each WP's own
spawn time**, never once per run: the plan table is mutable while the run
executes, and a value computed at Discover and carried forward is a cached
derivation under another name (C-1121).

Three properties are worth naming because each carries an argument the rest of
this ADR leans on:

- **It is a dual gate, in the research's exact sense.** Size never reduces on
  its own: every reduction branch is reachable only after all four flags are
  clear. *"No system in this research trusts size alone to lower effort"* — and
  neither does this one.
- **`hub` is conservative *when the declaration holds*, and not otherwise.**
  It reads *declared* file sets, and merge-time file-set re-validation requires
  every actually-changed file to sit **inside** the declared set — so where the
  declaration holds, declared-set intersection ⊇ actual-set intersection and
  `hub` over-fires rather than under-fires. **The first draft called that
  property "contractual, not empirical". It is neither, and the claim is
  withdrawn:** file-set re-validation's own remedy for a diff outside the
  declared set is to **widen the declaration**, not to fail the WP, so the
  contract does not in fact bound the actual set — and `DESIGN.md` round 13's
  process defect is the empirical counter-example, a WP whose cell declared two
  `hex/` paths while its merge carried thirteen. Any of those eleven undeclared
  paths could have been another WP's, with `hub` reading `false` at plan time.
  **`hub` is therefore an optimistic plan-time signal with a merge-time
  correction, not a conservative one** — which is exactly why C-1116 re-derives
  `hub` from the actual file list too, rather than exempting it.
- **`hub` needs no new machinery at all.** It is **the same predicate on a
  different left operand** as `adr_0010` C-903's high-risk clause 2 (*"a
  `(Repo, path)` pair that appears in any other WP's `Expected Files` anywhere
  in the plan — a file two WPs touch across levels is a hub"*): C-903 tests the
  WP's **actual merge-diff** file list, plan-time `hub` tests its **declared**
  set. One predicate, two operands, two clocks.

### The arithmetic, and its sensitivity

The traced WP-1, decomposed from the RCA's own timestamps and attributed to its
owner. Nothing here is measured by this ADR; the segments are the RCA's.

| Segment | UTC | min | Owner |
|---|---|---|---|
| sub-orchestrator spawn → first WP-1 spawn | 01:33→01:38 | 5 | neither |
| "edge-case hunt" reviewer — a stage in **no hex file** | 01:38→01:55 | 17 | wave 0 (C-931/C-932) |
| stub | 01:55→02:13 | 18 | **adr_0012** |
| specify | 02:13→02:28 | 15 | **adr_0012** |
| implement | 02:28→02:40 | 12 | **adr_0012** |
| R1 — quality + spec reviewers + architect, one concurrent batch | 02:40→02:51 | 11 | adr_0012 narrows the batch; the **trip** stays |
| round-2 fix + silent worker death + re-spawn | 02:51→03:30 | 39 | adr_0013 (liveness) |
| R2 quality | 03:30→03:46 | 16 | **adr_0012** (1-round cap) |
| no WP-1 spawn — one sub-orchestrator on WP-4/WP-5, then merge + verify | 03:46→04:39 | 53 | adr_0013 (sub-orchestration) + wave 0 (unscoped gates) |
| **Total** | 01:33→04:39 | **186** | |

*Erratum against the source, recorded rather than propagated:* the RCA's table
labels the final segment **69 m**, while its own timestamps give **53** —
69 is `03:30→04:39`, one row too early. 53 is what closes the column to the
traced 186, and 53 is used here.

**adr_0012's own effect, everything else held fixed.** The three-spawn
`{stub, specify, implement}` block — 45 minutes across 3 trips — becomes one
collapsed builder trip, costed at **18 min** (the largest of the three it
replaces), band 12–25. The 1-round cap removes R2 (16 min). R1 stays: it is one
round trip whether it batches three reviewers or two.

- **Saving = (45 − 18) + 16 = 43 min. 186 → 143 min, a 23 % cut — the central
  estimate of a 9–26 % band, and the band belongs beside the figure rather
  than only in the sensitivity list below.** The whole spread is the collapsed
  builder's unmeasured turn cost against the 12–25 min band: at **25 min** the
  saving is 36 (186 → 150, **19 %**); at the band's **12-minute** floor it is
  49 (186 → 137, **26 %**); and if the collapsed builder costs what the three
  phases cost — 45 min, one worker doing three jobs with no compression — the
  saving is the round cap alone, 16 min (186 → 170, **9 %**). **Nothing in this
  ADR rules that last case out**; it is what sensitivity 2 means, and 23 % is a
  point estimate inside it, not a floor.
- **Round trips: 9 → 6 for this ADR alone** (collapsed builder, the
  out-of-contract "edge-case hunt" stage, R1, fix, the dead-worker re-spawn,
  merge). **5 with wave 0**, which removes the out-of-contract stage
  (C-931/C-932) — a trip § The trip count falls further says plainly is not
  this ADR's to claim. **4 with `adr_0013`'s liveness ladder**
  (`C-1206`/`C-1207`), which removes the dead-worker re-spawn. **3 on a clean
  R1**, where there is no fix pass — the shape the brief names.
  **The trip claim is the robust one and holds across the whole 9–26 % band**:
  the collapse is one trip by construction whatever it costs in minutes.

**One honest deduction against the traced WP itself.** WP-1's *actual* diff was
**+78/−3 — 81 lines, over C-1102's ~50-line `S` threshold.** So on this very
work package, C-1116's merge-time re-derivation resolves `medium` and restores a
`review=full` round **before the merge**, adding back a trip the table above
does not charge. The 43-minute figure is therefore an **upper bound for WP-1
specifically**, and the clean 3–4-trip path needs a WP whose plan-time estimate
actually holds. This is the backstop working as designed and it is priced here
rather than in a footnote (S-1101).

**The trip count falls further than the wall clock, and that gap is the honest
headline.** Two of the nine trips are not this ADR's to remove: the
out-of-contract reviewer stage (wave 0, C-931/C-932) and the dead-worker
re-spawn (`adr_0013` `C-1206`/`C-1207`). Quoting 9→3 as a wall-clock claim
would be exactly the overclaim `adr_0010` refused when it separated its own
run-count statement from its wall-clock statement.

**With wave 0 and `adr_0013` also landed** — wave 0 removing the 17-minute
out-of-contract stage and scoping the Implement and loop-exit gates,
`adr_0013` removing the 27 minutes of dead-worker excess (`C-1206`/`C-1207`)
and the 53-minute serialization tail (`C-1219`/`C-1221`) — the residual WP-1
pipeline is:

`5 (startup) + 18 (collapsed builder) + 11 (R1) + ~12 (one fix pass) + ~2
(scoped merge check) ≈ 48 min`, or **≈ 36 min on a clean first review.**

**Against the RCA's ≤ 30 min target for a WP-1-class package: not reached, by
this ADR and not obviously by the whole program either.** The residual gap is
**per-trip latency**, and this is where the arithmetic runs out of measurements.

**What the saving is not sensitive to.**

- **LOC and diff bytes.** This is the RCA's central finding and it is why
  `adr_0010`'s delta scoping produced nothing here: on an 80-line diff the
  bytes were already ≈ 0.
- **Plan width.** Unlike `adr_0010`, whose entire saving vanished on a linear
  plan because its backstop was level-shaped, this reduction is **per-WP** and
  applies on the critical path exactly as it applies off it. A plan hex could
  not parallelize is a plan `adr_0010` could not speed up; it is not a plan
  this ADR cannot speed up.

**What it is sensitive to, in decreasing order.**

1. **Per-trip latency — and the one fast-balanced datapoint the traced run
   does contain points the wrong way.** The RCA measures deep-reasoning at a
   **14.7 min** median batch→next-batch before 2026-08-30 (858 batches) and
   **11.8 min** after (221 batches), and it publishes no fast-balanced
   *median*. But its own stage table is not silent: **the stub row ran
   fast-balanced and took 18 minutes** — the **slowest** of the three build
   phases (stub 18 fast-balanced, specify 15 deep-reasoning, implement 12
   deep-reasoning) and **well above** the 11.8-min deep-reasoning median. On
   the single measurement available, dropping a spawn's model class did not
   make its trip faster. **The "if fast-balanced runs at half deep-reasoning's
   median, the clean path lands near 22 min and the target is met" path the
   first draft offered is withdrawn** — nothing in the evidence supports it,
   and one datapoint mildly contradicts it. So the model-class half of this ADR
   — a size-S WP inside a `high` plan running `builder:implement` and `tester`
   at fast-balanced — is claimed **only** as a *cost* reduction, which is real
   and separately true, and as **zero** wall-clock effect until measured.
   One stage is not a median and the direction could still reverse; **producing
   that number is the dogfood benchmark's first job** (§ Validation), and until
   it exists the ≤ 30 min target has no supported route (D-1).
2. **The collapsed builder's turn cost.** One worker doing three jobs in one
   turn is one *trip* by construction, but not necessarily 18 minutes. At 45 it
   saves only the two hand-offs; at 12 it saves 33. The claim this ADR makes is
   about **trips**, which is the RCA's own law; the duration is owed by
   measurement.
3. **The reduction rate — how many WPs actually derive below the ceiling.**
   For a project that has attested nothing it is **zero, and the saving is
   exactly zero** (§ The degrade rule). No target rate is stated, because
   `adr0012-risk-scoring.md` finding 16 reports that no such number is
   published anywhere and warns against inventing one.
4. **Everything in the merge tail**, which the RCA attributes to
   single-threaded sub-orchestration and unscoped gates. That is `adr_0013`'s
   (`C-1219`/`C-1221`) and wave 0's; it is 53 of the traced 186 and this ADR
   does not touch it.

### Departures from research recommendations

Each is a departure from a *recommendation*, named as one.

1. **Nothing is persisted.** `adr0012-precedent.md` recommendation 4 says
   *"Persist the derivation's inputs and result as an inspectable record on the
   WP, not just the final effective tier"*, and `adr0012-risk-scoring.md` asks
   for the same thing in the plan artifact. **Declined.** The derivation is a
   pure function of the plan artifact plus one pointer, reproducible at zero cost
   — which is precisely what Kubernetes does: `kubectl describe pod` *shows*
   the QoS class without the API ever storing it. A stored copy would be a
   second source for a value the table already determines, and would go stale
   the first time an author edits a `Size` cell — the drift `DESIGN.md`'s
   single-source rule exists to prevent, and the same objection `adr_0010`
   raised against writing per-event data into mutable per-WP rows. **What the
   recommendation was protecting is delivered in full**: the announce block and
   the execution handoff *are* the inspectable record, itemized per WP with the
   flags that fired (C-1119, C-1120, C-1118), which is the visible half of the
   BestEffort anti-pattern's cure. What is given up is the *historical* half —
   there is no log of how a WP's derivation changed over the plan's life —
   and `adr0012-risk-scoring.md` finding 17 records that **no surveyed tool
   ships that either**.
2. **No periodic aggregate sweep of the cut stages.**
   `adr0012-risk-scoring.md`'s backstop recommendation asks to *"run the
   reduced-tier pipeline's cut review stages in full on a periodic aggregate
   sweep (e.g. every N merged low-tier work packages, or nightly)"*, on Google
   TAP's postsubmit model. **Declined in that form.** TAP's periodicity exists
   because its stream of changes is unbounded; a hex run is bounded — one plan,
   one branch, a terminal review — so the sweep's bounded form is a **terminal**
   pass, which is what C-1117 makes mandatory and raises to the ceiling tier.
   A second periodic cadence *inside* a run would need its own counter and its
   own state (driver 7 forbids both) and would re-review already-reviewed WPs
   once per subsequent WP — `O(N²)`, the exact shape `adr_0010` C-909 rejected
   when it refused to read the feature branch at the end of every per-WP loop.
   The **retroactive** half of the same recommendation is kept: C-1116
   re-derives at merge time and re-runs review at the higher breadth.
3. **Four flags, not six.** `adr0012-risk-scoring.md` recommends six —
   path sensitivity, churn/entropy history, ownership concentration, fan-in,
   hot-path, and CI-workflow re-derivation. This ADR ships four and drops
   three-and-a-half. **Churn/entropy and ownership are dropped on mechanism,
   not on evidence** — both are validated and Bird et al. show ownership is not
   safely droppable as a *predictor* — because both require walking git history
   per file at plan time and then comparing against **a percentile of this
   repo's own history**, which is a computation with nowhere to run and a
   result with nowhere to live. **The CI-workflow flag is subsumed rather than
   dropped**: a workflow file is the canonical content of a documented
   security-sensitive path convention, and Scorecard's own re-derivation
   argument (*a stale declaration is most dangerous exactly here*) is an
   argument about **what the convention should list**. **The first draft
   stopped there and left a residual it should not have accepted** — a project
   whose convention omitted `.github/workflows/**` got no flag for it and no
   compensating signal, which is a **silent loss of a security reviewer hex
   ships today**, not a Layer-1 gap. C-1103 closes it: `sec` reads hex's own
   shipped triggers (`classify.md`'s structural-marker table — CI workflows,
   dependency manifests, auth/crypto/signing paths, new package manifests) as
   an independent disjunct the project cannot subtract from. **The CI-workflow
   flag is therefore neither dropped nor merely subsumed: it is shipped, from a
   table that already exists.** The genuine residual is narrower and is what
   Layer-1 knowledge is actually for: a path that is security-sensitive **for
   this project alone** and matches none of hex's globs gets no flag until the
   project's convention names it.

### Judgment calls made inside the decision

Ten places where the design underdetermined itself and this ADR resolved it
rather than escalating.

1. **`hub` floors at `medium`, not at the ceiling.** The literature behind
   `hub` is a static-dependency-graph result (Zimmermann & Nagappan's 60 %-vs-30 %
   hit rate on critical files), and the research is explicit that
   "another WP also touches this file" is an **extrapolation** of it, not a
   cited metric. A signal on extrapolated evidence should not be allowed to
   swallow the entire win: cross-wave file sharing is common in any plan of
   width, and flooring `hub` at the ceiling would make it the dominant term.
   `medium` still buys back the full four-phase pipeline, `review=full`
   breadth and a 3-round cap — everything the collapse removes — while leaving
   the ceiling's deep-reasoning cells and adversarial breadth for the flags
   with real evidence behind them. **Resolved here rather than escalated**, and
   revisitable in one line of the function if the dogfood shows escaped defects
   clustering on `hub`-flagged WPs.
2. **`door` reuses `Verify: full` rather than adding a flag.** `adr_0010`
   C-905 already defines `Verify: full` as *"author judgment the merge-time
   high-risk predicate cannot see — a WP that changes a default, a schema, or a
   config value nothing textually references"*, already raise-only, already
   justified in one line when used. That **is** the one-way-door declaration,
   already written down; a second cell meaning the same thing would be two
   places to keep in sync. **The cost is real and is stated:** after wave 0's
   C-924 the `Verify` cell sets **two** gates (the merge gate and the
   Review-Fix-Loop exit gate that immediately precedes it — C-924 says in its
   own words that *"the Implement-phase gate is **not** coupled to the cell"*,
   D6/C-925), so `Verify: full` is already an expensive hammer, and this ADR
   makes it heavier still by also blocking tier reduction. An author who wanted
   only the one-way-door signal now pays **three** gates for it — merge, loop
   exit, and now the reduction block. Accepted: the alternative is a fifth
   flag with its own cell, its own column-lock amendment, and its own way of
   being mis-authored.

   **The incentive gradient this creates is against the ADR and is stated
   rather than hoped away.** `Verify: full` is now the plan table's **most
   expensive cell**, and it is the *only* risk signal an author controls. The
   unsafe declaration in the other direction — attesting an empty
   security-sensitive set, which clears `sec` on every WP of every plan forever
   *and* disarms C-903's checkpoint trigger (judgment call 3) — is **free,
   written once, and permanent.** So the design charges three gates for caution
   and nothing for its opposite. Nothing in this ADR corrects that; C-1107's
   degrade line makes the *absence* of an attestation visible but says nothing
   once one exists, and C-1116 re-reads the same convention it was misled by
   (§ Risks). The honest mitigation is review of the attestation itself, which
   is a human process this ADR does not ship.
3. **`door`'s fail-open asymmetry is deliberate.** `sec`, `hot` and `hub` read
   `true` on a missing source; `door` reads `false`. Three grounds, and they do
   not generalize to the other three. **(a)** `door` is the *author-declared*
   flag: its absence genuinely means "the author declared nothing", where the
   other three mean "hex could not read the project's convention" — a different
   fact. **(b)** The other three still gate: a WP with an unreadable convention
   is already at the ceiling regardless of `door`. **(c)** A plan with no
   `Verify` column at all is **refused** the marker (C-1114), so the fail-open
   branch is unreachable rather than merely unlikely.

   **The general rule underneath, corrected from the first draft.** That draft
   claimed *"a fail-safe default is direction-relative, not source-relative"* —
   the same source read fail-open by `adr_0010` C-903 and fail-closed here,
   reconciled by which way each consumer moves effort. **That argument does not
   work and is withdrawn.** On an absent row, C-903's clause 1 goes vacuous ⇒
   *fewer* full verifications, and a fail-open reading here would ⇒ *less*
   review. **Both consumers move effort in the same direction — down — so a
   direction-relative rule yields the same answer at both sites and condemns
   C-903 rather than reconciling it.**

   **What is actually load-bearing is residual risk: how much still catches the
   miss after the default fires.** Behind C-903's vacuous clause 1 sit **three
   independent backstops** — the checkpoint counter, the level-clear trigger,
   and the un-lowerable final gate — none of which the absent row touches, so
   the absence costs one *earlier* full verification out of several, and the
   run still gets one. Behind a fail-open `sec`/`hot` here sits **one**: the
   branch-level `/hex-review` (C-1117), and it is a review, not a
   verification — the collapsed phases and the reduced model class are already
   spent by the time it runs (C-1116). **One source, two absence semantics,
   decided by the backstop count, not by the direction.** That is a wart and it
   is recorded as one in § Consequences.

   **The consequence the first draft never stated, and it is the sharpest
   thing in this section: one attestation of `none` disarms two controls, not
   one.** The row that clears `sec` here is the *same* row `adr_0010` C-903
   clause 1 reads as its high-risk checkpoint trigger. Writing it as an empty
   set therefore buys tier reduction **and silently removes a pre-existing,
   unrelated full-verification trigger** that has nothing to do with this ADR.
   Nothing in either contract announces the second effect. It is stated here,
   at C-1106, and in erratum row 6, so that a reader deciding whether to attest
   sees both prices.
4. **`size` stays authored, and the ADR does not pretend otherwise.** The
   sharpest objection to a "derive, don't author" ADR is that its primary input
   is an authored cell. The answer is the precedent, not a dodge: **Kubernetes
   QoS is derived from `requests` and `limits` the operator authored.**
   Derived-from-authored-primitives is the entire pattern; derived-from-nothing
   is available to nobody, and at plan time the diff that would allow it does
   not exist. Three things bound the residual: the class is not authorable even
   though its input is; `size` alone never reduces (the dual gate); and C-1116
   re-derives against the **actual** diff at merge time and re-runs review if
   the estimate was wrong. **Authoring error is reduced, not eliminated**, and
   the reduction is specifically in the direction that failed: the traced
   defect was an authored *class* (`panel`), and classes are no longer
   authored.
5. **`Review: panel` raises the whole effective tier, not only breadth.** The
   alternative — raise breadth alone — produces the weakest available
   combination: an adversarial panel reviewing a single collapsed builder turn
   whose tests were written by the same worker that implemented them. If an
   author has spotted risk the function could not see, the correct response is
   the ceiling's whole pipeline. `adr0012-precedent.md` recommendation 5 asks
   for an escape hatch to *"force a higher-than-derived **tier**"*, and this is
   it. The cost is that a column named `Review` now moves phases and model
   class; that naming debt is accepted rather than repaired, because a rename
   would break every legacy plan and cost the column-lock amendment driver 3
   exists to avoid.
6. **The `Size` vocabulary is defined by reusing shipped numbers, not by
   inventing them.** `S`/`M`/`L` appear **in the plan template's example cells
   (`[S/M/L]`) and nowhere else in the bundle** — the template's *header* cell
   reads `Size`, and `DESIGN.md`'s *Plan visualization* lock enumerates the
   column **name** `size`, not its values. A function whose primary input is an
   undefined cell is authored judgment wearing a mechanical costume, so C-1102
   defines it — from § Parallel-by-default decomposition's own `self` heuristic
   (*"~≤50 expected lines"*) for `S`'s line count, from § Tier grammar's `low`
   row (*"≤3 files, one area"*) for its file count, and from
   `hex-review/classify.md`'s already-shipped tier-metric table (`medium`: ≤15
   files, ≤500 lines) for `M`. Zero new numbers. **It does not make C-1116's
   merge-time re-derivation exact**: C-1102 and `classify.md` are **not one
   table** — `classify.md`'s `low` row is `≤3 files, ≤100 lines` against
   C-1102's `S` at `~≤50` — and C-1102 states that divergence rather than
   claiming a shared table. What the definition buys is that plan-time estimate
   and merge-time diff are measured on **the same vocabulary**, which is what
   C-1116 needs.
7. **The marker line sits immediately after `Tier:`, not after `Next:`.**
   `adr_0010` C-907 placed its two new Status lines after `Next:` and before
   the multi-row `Repos:` ledger, on the ground that a line behind an unbounded
   entry has no stable position. That ground is honoured — `Effective-tier:` is
   a single fixed line ahead of the ledger — and the placement is one line
   earlier because the marker *qualifies `Tier:`*: a reader who sees
   `Tier: high` must see "and it is a ceiling" in the same breath. `adr_0010`'s
   own sentence ("immediately after `Next:`") stays true of its own two lines,
   which still sit immediately after `Next:`; no erratum is owed.
8. **O1 over O2 is a judgment call, and it is named as one rather than
   presented as arithmetic.** After the re-scoring in § Considered Options the
   two tie on wall clock and O1 leads by fourteen points on a 125-point scale,
   with the entire margin sitting in two criteria that moved for the same
   reason. **The choice rests on one argument** — O1 gates the reduction on
   signals the author does not choose, O2 gates it on one cell the author
   writes — **and a reader who weighs bundle surface above authoring-error
   surface can defensibly reach O2.** It is resolved here rather than escalated
   because the owner's approval of this ADR *is* that decision, and adding it
   to Open Questions would spend one of three slots asking "should we do this
   ADR", which the Status field already asks. If it is reopened, O2's live form
   is the one scored — the four axes bound to `self`, with the generation
   marker it also needs — not the first draft's weaker reading.
9. **A bounded, repo-relative sizing was available and was not scored as its
   own option.** § Considered Options rejects O5 partly because a churn or
   fan-in percentile *"is a computation hex has nowhere to run at plan time and
   nowhere to store."* The second half of that is right and the first half is
   overstated: **`git log -n 50 --numstat` at Discover, computed once and never
   persisted, sits entirely inside this ADR's own recompute-never-persist rule
   (C-1121)** — the same rule that lets C-1116 shell out to `git diff` at merge
   time. A bounded window is not a full-history percentile, and it would give a
   **repo-relative** size distribution rather than the absolute ~50-line
   constant C-1102 hardcodes. **It was not considered as a distinct option, and
   that is a gap in the option set, not a rejection.** It is recorded here
   rather than retrofitted into the matrix, because scoring it honestly needs
   research this ADR did not commission — `adr0012-risk-scoring.md` validates
   the *features* and explicitly supplies no cutoff, bounded-window or
   otherwise. The absolute threshold ships for v1; this is the first thing to
   revisit if the dogfood shows C-1102's constant mis-sizing a real repo (D-3).
10. **C-1117 gates a markdown status field, not a merge — stated plainly
    rather than dressed as a submit requirement.** The analogy the contract
    draws is to Zuul's gate pipeline and Gerrit's `Verified` label, and **both
    of those are *submit* requirements enforced by the forge.** hex has no such
    surface: it never pushes outside `/hex-finalize`, and `/hex-finalize`'s own
    gate is a **single human approval**, not a mechanical precondition. So what
    C-1117 actually blocks is a plan reaching `done` / `landing` — a field in a
    markdown Status block that no forge reads, and a human who ignores it can
    merge anyway. **The analogy is to the discipline (a fast path never
    substitutes for the final gate), not to the enforcement, and the contract
    now says so.** The stronger form — making `/hex-finalize` refuse a branch
    whose plan carries an unsatisfied C-1117 precondition — is a real option,
    is a cross-skill contract this ADR does not own, and is deliberately not
    taken here: it would put a hard stop in front of the one irreversible act
    in the bundle on the strength of a derived value, which deserves its own
    record.

### Consequences

**Positive.** The dominant per-WP serial cost — pipeline depth — becomes
scalable for the first time; it has been constant at every tier since round 4.
**Authoring a *class* is no longer possible**: the `Review` cell can no longer
name a review breadth below the derived one, so the specific defect the RCA
traced — `panel` on a 78-line WP, and its mirror image `self` on a WP that
needed review — has no cell left to live in. **What that does not do is remove
authoring error, and § Judgment calls 4 says so:** `Size` is still authored and
is still the sole reduction input. The `models.md` matrix gains a per-WP
resolution for the first time, so a 78-line WP inside a `high` plan stops
paying for a deep-reasoning `tester`. A `hex.md` model override that raises a
spawn above its cell becomes an announced disclosure instead of a silent
config win. And the whole change costs **zero** new config keys, **zero** new
plan-table columns, **zero** new state files, and **zero** amendments to the
*Plan visualization* lock.

**Negative, and accepted.**

- **Authoring error is *moved*, not removed — and it is moved from a column
  that fails slow to one that fails silent.** This is the single most important
  concession in the ADR and the first draft did not make it. Today the
  mis-authorable cell is `Review`, and its expensive direction is **upward**:
  `panel` set too high costs an adversarial panel and wall clock, which is
  loud, measurable, and exactly what the RCA caught. Under this ADR the
  mis-authorable cell is `Size`, and its dangerous direction is **downward**:
  `S` written on work that is really `M` silently collapses three phases, drops
  the model class, and cuts review to `minimal` — **with no announce line
  saying anything is wrong**, because from the function's point of view nothing
  is. Mis-sizing produces the correct-looking output `WP1 low (derived: S, no
  flags)`. **A cheap-and-loud failure has been traded for a cheap-and-quiet
  one.** What genuinely improves is narrower than "the error is gone" and is
  stated exactly: **(a)** the three flags gating the reduction are **not
  authored** — `sec` and `hot` come from the project's conventions and hex's
  own shipped triggers, `hub` from the plan's own file-set intersection — so a
  mis-sized WP that touches a flagged path still resolves at the ceiling and
  the sizing error costs nothing; and **(b)** C-1116 re-derives at merge time
  from the **actual** diff, which sees through the estimate entirely and
  restores review breadth before the merge. **Both are partial.** (a) does
  nothing for a mis-sized WP in unflagged code, which is the common case; (b)
  restores only review — the phases and the model class are spent by the time
  it runs, as C-1116 itself states.
- **The `Review` column's vocabulary goes effectively binary in a
  derived-generation plan.** `panel` raises to the ceiling; `self` and `light`
  name breadths at or below the derived baseline and are therefore **inert**.
  Three values, one live. The alternative — re-vocabularizing the column — costs
  a lock amendment and breaks every legacy plan, where all three values still
  do all three jobs. Naming debt, recorded, not repaired.
- **One `hex.md › Pointers` row now has two absence semantics** — vacuous for
  `adr_0010` C-903's high-risk trigger, `true` for this ADR's `sec`/`hot`.
  Justified in § Judgment calls 3, and genuinely confusing to a reader
  encountering one site without the other. Both sites carry the cross-reference.
- **The Status block grows by one line**, and `adr_0010`'s erratum already
  records that the template's own *"must stay within the first 20 lines"*
  invariant is unmet before this ADR adds anything (`State:` sits at line 24).
  This makes a pre-existing overflow one line worse. Recorded as an erratum,
  not fixed here — fixing it means restructuring the template's comment block,
  which is a change with no relationship to this decision.
- **The collapsed builder trades author≠verifier at the WP level.** The
  Specify phase exists as a separate `tester` spawn precisely so tests are
  written against the contract rather than against an implementation the same
  agent already has in mind. The committed-stub check (C-1108) recovers the
  **temporal** property (tests existed and failed before the implementation)
  but **not the independence property**, and this ADR does not claim otherwise.
  The backstops are the reviewer batch (`review=minimal` still runs a `spec`
  reviewer) and the ceiling-tier branch review. Open question 2.
- **Merge-time re-derivation can restore review, never phases.** By the time a
  WP merges, its collapsed pipeline has already run; C-1116 can re-run review
  at a higher breadth but cannot un-collapse a stub phase that never existed
  separately, and cannot re-run an implementation at a different model class.
  The plan-time estimate is load-bearing in a way `adr_0010`'s `Review`
  re-validation was not.

**Risks.**

- **The most likely production failure is not an absent attestation — it is a
  *readable but narrow* one, and it is the one the backstops do not catch.**
  Every degrade path in this design keys on **unreadable**: C-1105 reads `true`
  on absent/unreadable/malformed, C-1107 prints a line naming which convention
  could not be read, and § Validation forces that path. **A convention that
  parses cleanly and lists too little triggers none of it.** A row naming
  `src/auth/**` in a repo whose signing code lives in `src/release/` is a
  perfectly readable source: `sec` reads `false`, the pipeline collapses, the
  announce block truthfully prints `no flags`, and **no degrade line prints,
  because nothing degraded.** It defeats C-1116 as well, because merge-time
  re-derivation re-reads **the same convention** — a narrow declaration is
  narrow against the actual diff too, so the backstop that exists precisely to
  catch a wrong plan-time estimate is blind to a wrong plan-time *convention*.
  What is left is C-1117's branch review, one layer, after the phases and the
  model class are spent. **This is the CODEOWNERS failure mode with the file
  present and valid**, and the one partial mitigation this ADR ships is C-1103's
  rule that hex's own shipped triggers (auth/crypto/signing paths, dependency
  manifests, CI workflows) fire **regardless** of what the project declared —
  the project may widen hex's sensitivity, never subtract from it. That covers
  the canonical categories and nothing project-specific.
- **A size-S WP whose risk the function cannot see, in a
  project that attested `none` too eagerly.** This is the Kubernetes BestEffort
  shape — a unit silently in the cheapest class, with no forcing function to
  notice — and `adr0012-precedent.md` names it as the direct risk for this
  design. Mitigation is the two-layer backstop and nothing else: C-1116
  re-derives against the actual diff before the merge, and C-1117 makes a
  branch-level `/hex-review` at **no less than the ceiling tier** a
  precondition for the plan's terminal review state. Neither is optional and
  neither is lowerable by any budget cell.
- **An attestation that is right on the day it is written and wrong six months
  later.** CODEOWNERS' and git-crypt's shared failure mode: rules must exist
  *before* the sensitive file is added, or that file is silently unprotected.
  Hex mitigates only partly — `protocol.md` § Verification's standing rule
  requires verifying a pointer on consumption and re-detecting on a miss, which
  catches a *moved* convention but not an *incomplete* one. Stated as a
  residual.
- **A project that attests security paths but says nothing about hot paths.**
  The Pointers row is one source carrying two conventions, and C-1104 resolves
  them independently: silence on one leaves that one `true`, so a
  half-attestation buys nothing. This is correct and it will read as a bug to
  the first person who hits it, which is why C-1107's degrade announcement
  names **which** convention was unreadable and its one-line remedy.

**Deferred findings.** **(D-1)** The ≤ 30 min target is not reached by this
ADR and its reachability by the whole program depends on an unmeasured
quantity — fast-balanced per-trip latency. **(D-2)** Churn, entropy and
ownership are validated defect predictors this ADR does not use, dropped on
mechanism; the day hex has somewhere to compute and store a per-repo
percentile, they are the first three flags to add, and C-1101's enumeration is
closed-and-versioned specifically so adding one is a version bump rather than
an edge-case judgment. **(D-3)** A bounded repo-relative sizing
(`git log -n 50 --numstat` at Discover, never persisted) was inside this ADR's
own rules and was never scored as a distinct option; § Judgment calls 9 records
the gap. It is the first thing to revisit if C-1102's absolute ~50-line
constant mis-sizes a real repo.

## Non-Functional Requirements

Only affected axes; silence means not affected.

| Axis | Impact of this decision |
|---|---|
| Latency | **The point of the change.** Per-WP round trips **9 → 6 for this ADR alone** on the traced case, **5 with wave 0**, **4 with `adr_0013`'s liveness ladder (`C-1206`)**, **3 on a clean R1** — **the robust claim**, and stated with its owners rather than as a bare 9 → 3; wall clock 186 → 143 min for this ADR alone, a 23 % point estimate inside a **9–26 % band**, ≈ 36–48 min with wave 0 and `adr_0013`. **Two sensitivities govern it** and neither is measured: the collapsed builder's turn cost (the whole band), and per-trip latency by capability class — deep-reasoning has an 11.8-min median, fast-balanced has no median at all, and the one fast-balanced stage the RCA traced (stub, 18 min) was the **slowest** of the three build phases, so the model-class drop is claimed as a cost reduction with **zero** wall-clock effect until measured. **Unlike `adr_0010`, the saving does not depend on plan width** — it is per-WP and applies on the critical path. It **does** depend on the reduction rate, which is zero for a project that has attested nothing. |
| Cost | Token cost falls independently of latency and more reliably: a size-S no-flag WP inside a `high` plan runs `builder:implement` and `tester` at fast-balanced instead of deep-reasoning, and `review=minimal` instead of `review=adversarial` drops the `architect` and `researcher` spawns from Round 1. No new spawns, no new role, no new phase. Always-on surface added: **zero** — no rule-file line, no new skill description, no `config.md` key. |
| Correctness / reliability | **The residual is stated, not mitigated away.** A WP whose risk the function cannot see runs a collapsed pipeline at a reduced model class, and the merge-time re-derivation can restore its *review* but not its *phases*. The un-lowerable final gate (`adr_0010` C-901 trigger (iii)) is untouched. The collapsed builder gives up author≠verifier at WP level and recovers only the temporal half of it. Both backstops are mandatory and neither is lowerable by a budget cell. |
| Operability | One new operational object: an optional Status line. One new announce line and one histogram, both reusing wave 0 C-930's grammar. **No new state file, at any depth** (driver 7); the derivation is recomputed, never cached. The genuinely new thing an operator must learn is that `Tier:` is now a ceiling — which is exactly why the marker line sits directly under it. |
| Security | **One boundary, and it is a read, not an execution.** `sec` and `hot` resolve through a `hex.md › Pointers` row to project-documented paths. The convention is read **only from authoritative-class *sources*** (`adr_0009` C-815) — project context, never `CONTRIBUTING.md`, a PR body, or any narrowing- or untrusted-class surface — because it decides how much review security-relevant code receives; **the Pointers row itself stays a cache** (`memory.md`: *"Never authoritative"*) and **C-1105 fails closed when it is wrong, missing, or points outside the repository root**. hex reads path conventions and never executes anything from that source; no credential is read and no network call is made. The fail-closed degrade is itself a security control (§ The degrade rule). |
| Compatibility | **Purely additive at the artifact level.** One optional Status line with a defined absent-default, no new column, no new key, no migration step, no rewriter. **A plan without the marker executes byte-identically forever** — that half is unconditional. **The second half is scoped:** a project without an attested convention resolves every WP at the ceiling, which is byte-identical to today **for a marked plan whose `Review` cells are absent or `panel`**, and runs *more* review where they are `self` or `light` (C-1112 makes those inert). Safe direction, visible per WP, but not identity — and it is the common shape, since wave 0's C-928 instructs planners to author those cells. The two things a user notices without editing anything are the degrade line and, on such a plan, the reduced WPs announcing at the ceiling. |
| Scalability | Improved on the axis that mattered: per-WP serial depth stops being a constant 7–9 trips at every tier — **6 for the reduced class on this ADR alone, and 3–4 once wave 0 and `adr_0013` (`C-1206`) have removed the two trips this ADR does not own**. Concurrency is unchanged, dispatch is not redesigned, the depth-1 coordinator invariant (`adr_0010` C-914) is untouched, and **no recursion level is added**. |
| Availability | Not affected. |

## Component contracts

Contracts are numbered `C-11xx`; UX scenarios `S-11xx` — the next free range,
**verified free: no `C-11xx` or `S-11xx` token exists anywhere in the
repository**. Predecessors: `adr_0001` `C-00x`, `adr_0002` `C-1xx`, `adr_0003`
`C-2xx`, `adr_0004` `C-3xx`, `adr_0005` `C-4xx`, `adr_0006` `C-5xx`,
`adr_0007` `C-6xx`, `adr_0008` `C-7xx`/`S-7xx`, `adr_0009` `C-8xx`/`S-8xx`,
`adr_0010` `C-901`–`C-919`/`S-901`–`S-910`, `plan_wave0_quick_wins`
`C-920`–`C-937`/`S-911`–`S-917`, `adr_0011` `C-10xx`/`S-10xx` (ending at
`C-1044`/`S-1015`). Home names the single definition or edit site;
"(sole source)" marks a definition every other file links to rather than
restates.

### A. The effective-tier function

| ID | Contract | Home |
|---|---|---|
| **C-1101** | **The effective tier — derived, never authored, never above the ceiling.** Every work package resolves an **effective tier** over the ordered vocabulary `low < medium < high` by the function in § The function, from four boolean risk flags and one size class. The plan's `Tier:` is a **ceiling**: `effective ≤ T` is structurally guaranteed by every branch of the function, and **no input, cell, flag, preference or user override may produce `effective > T`** — the one property `adr0012-precedent.md` recommendation 1 asks be made impossible rather than discouraged, mirroring Kubernetes ResourceQuota rather than GitLab CI's freely-restated `default:`. **The effective tier is never written into the plan and never authored**; it is recomputed on every read, and its value is a function of **the plan artifact** plus one pointer and nothing else (C-1121) — *artifact*, not *table*, because `door` resolves through the `Verify-default:` **Status line** when the cell is empty, which is outside the table. **The ceiling `T` is the plan's Status-block `Tier:` value, explicitly independent of `/hex-execute`'s optional `[tier]` argument.** A run invoked as `/hex-execute low <high-plan>` resolves its own overlays at `low` as it does today, but **`T` stays `high`**: the flag says how much effort the *run* asks for, and the plan's Status block says how much the *work* was scoped for. Reading `T` from the run flag instead would collapse even flagged WPs — every `sec` WP in a `high` plan silently reduced by a command-line argument — and would lower C-1117's backstop floor at the same time, which is the one place the design has no second layer. The two compose as a `min` on the axes (C-1110), never on the ceiling. **The flag enumeration is closed and versioned**: exactly four flags, named `sec`, `hot`, `hub`, `door`; a fifth arrives by amending this contract in a later ADR, never by analogy at an edge case — the closed-enumeration discipline of OpenSSF Scorecard and OWASP ASVS, with PCI DSS v4.0.1's versioned-category-addition as the precedent for how the list grows. **Three consumers, and the execution one recomputes per WP at that WP's own spawn time — never once at Discover.** `/hex-execute` resolves a WP's effective tier when it spawns that WP, because the plan table is **mutable during the run** (the Status column is written on every merge, and a `Size` or `Expected Files` cell can be corrected mid-run); a value computed at Discover and carried forward is a cached derivation in everything but name, which is the exact thing C-1121 forbids. `/hex-plan` computes it at the Decompose gate for the histogram (C-1119); `/hex-review` reads it for the backstop (C-1117). **A run in which a WP's inputs changed after Discover therefore announces the recomputed value at spawn, and the Discover-time histogram is a snapshot, labelled as one.** | `protocol.md` § Parallel-by-default decomposition › The effective tier (new subsection, sole source) |
| **C-1102** | **The `Size` vocabulary, defined for the first time, from numbers already shipped.** `S`/`M`/`L` appear **in the plan template's example cells (`[S/M/L]`) and nowhere else in the bundle** — the template's header cell reads `Size`, and `DESIGN.md`'s *Plan visualization* lock enumerates the column **name** `size`, not its values — so the vocabulary is **defined nowhere**. This ADR's function keys on that cell, so the cell gets a definition: **`S`** — ~≤50 expected lines **and** ≤3 expected files; **`M`** — ~≤500 expected lines **and** ≤15 expected files; **`L`** — anything else. **Both halves must hold**, per Google's `small-cls` guidance that file count *multiplies* size risk rather than forming an independent axis (200 lines in one file is fine; the same 200 across 50 files is not). **Zero new numbers:** ≤3 files is § Tier grammar's own `low` row (*"≤3 files, one area"*), ~≤50 lines is § Parallel-by-default decomposition's shipped overhead floor and the `self` heuristic's own figure, and ≤15 files / ≤500 lines are `hex-review/classify.md`'s shipped tier-metric table for `medium`. `adr0012-risk-scoring.md` finds ~50 defensible as the aggressive end of the Cisco 200–400 / Google 100–200 bands — *"comfortably inside the zone every source treats as reviewable in one pass — but a size gate only, never sufficient alone"*, which C-1101's dual gate honours. **An absent, empty, unrecognized or ambiguous cell reads `L`.** **`hex-review/classify.md` is not moved**, and the first draft's claim that this makes *"one shared table, so the two never drift"* was **false and is withdrawn — only the `medium` row's numbers are actually shared.** The divergence, stated because C-1117 compares the two vocabularies directly: `classify.md`'s **`low` row is `≤3 files, ≤100 lines`**, while this contract's **`S` is `≤3 files, ~≤50 lines`**. The file counts agree; the line counts differ by a factor of two, and the two thresholds have different jobs — `classify.md` sizes an **actual diff** for a review, C-1102 sizes an **estimate** for a reduction, and the reduction side is deliberately the more conservative of the two, per `adr0012-risk-scoring.md` calling ~50 *"the aggressive end"* of the Cisco 200–400 / Google 100–200 bands. **The concrete consequence, and it is not hypothetical: a 60–100-line WP is `M` here and `low` there**, so a `medium` plan whose WPs all land in that band reduces nothing under C-1102 while `/hex-review` classifies the finished branch `low`. **C-1117's `max(classified, ceiling)` is what keeps that safe** — the ceiling wins — and it is the reason the two vocabularies can differ without the backstop breaking. `classify.md` gains one clause **cross-referencing** C-1102 and naming the divergence; it does not adopt the number, and it keeps its own richer classifier (areas touched, structural markers). | `protocol.md` § Parallel-by-default decomposition (sole source); one cross-reference clause in `hex-review/classify.md`; the plan template's table comment |
| **C-1103** | **The four flags and their sources — every one of them already exists.** **`sec` is a union of two sources, and the project half may only widen it.** `sec` is `true` when **either** (a) a path in this WP's `Expected Files` matches one of **hex's own shipped, project-independent triggers**, **or** (b) it matches the project's documented security-sensitive convention, read through the `hex.md › Pointers` row `memory.md` already establishes as *"the named source the high-risk merge trigger reads"* (`adr_0010` C-917). **The project may widen hex's sensitivity; it may never subtract from it** — no attestation, no empty set, and no narrow convention clears (a). **Why this half is mandatory rather than nice-to-have:** at effective `low` the review set is `review=minimal`, which `hex-execute/overlays.md` defines as *"`reviewer` (focus `quality`) + `reviewer` (focus `spec`…). Nothing else."* — the conditional `reviewer:security` that `full` carries **cannot spawn at all**. So without (a), a CI-workflow edit or a lockfile bump inside a `high` plan **loses a security reviewer it gets today**, silently, while the announce line truthfully reads `no flags`. **Zero new machinery: the triggers are already shipped and already cited by this ADR.** `overlays.md`'s own `full` row names them project-independently — *"auth/crypto/signing, a new dependency manifest, a CI workflow file"* — and `hex-review/classify.md`'s structural-marker table is the enumerated form: **auth / crypto / signing paths** (*"path contains `auth`, `crypto`, `sign`, `token`, or `secret`"*, marked *"security perspective required"*), **dependency-manifest / lockfile changes** (*"supply-chain scrutiny"*), **CI-workflow changes** (`.github/workflows/**`, `.gitlab-ci.yml`, …), and **new package/crate manifests**. C-1102 already cites that table for the size half; this cites the same table for the security half. **`hot`** — the project's documented hot-path convention through the same Pointers row, project-only, because hex ships no project-independent hot-path trigger; that asymmetry is deliberate and is why a half-attestation still buys nothing (C-1105). **This also closes the residual § Departures 3 left open**: a project whose convention omits `.github/workflows/**` now gets the flag from (a) regardless. **`hub`** — any `(Repo, path)` pair in this WP's `Expected Files` also appears in **another WP's** `Expected Files`, in any wave. It is **the same predicate as `adr_0010` C-903's high-risk clause 2 on a different left operand** — C-903 tests the WP's actual merge diff, this tests its declared set at plan time; the key is `(Repo, path)` and not the bare path for C-316's reason, and with no `Repo` column every pair is `(., p)` and the test is a path comparison. **WPs sharing a wave are required to be file-disjoint** (`protocol.md` § Parallel-by-default decomposition), so within a wave `hub` cannot fire; **it is not confined to firing across waves**, because dependency-ready launch runs independent WPs from different waves concurrently — the pair `hub` catches is *some other WP anywhere in the plan*, which is where merge-order-dependent breakage lives. **`hub` is conservative only where the declaration holds** — re-validation's remedy for an out-of-set diff is to widen the declaration, so the declared set is not a guaranteed upper bound (§ The function), which is why C-1116 re-derives `hub` from the actual file list rather than carrying it forward. **`door`** — the WP's `Verify` cell resolves to `full` through `adr_0010` C-905's existing chain (cell → `Verify-default:` → `scoped`). `Verify: full` is already defined as *"author judgment the merge-time high-risk predicate cannot see"*, already raise-only, already justified in one line when used: it **is** the one-way-door declaration and needs no second cell. **No flag adds a command**: `sec`/`hot` are a path match against a pointer the run already resolves, `hub` is a set intersection over the table, `door` is a cell read. | `protocol.md` § Parallel-by-default decomposition › The effective tier (sole source) |
| **C-1104** | **Sub-WPs and coordinator-owned parents.** **A sub-WP's effective tier is its parent's — unless the sub-WP's own `Review` cell raises it (C-1112).** The inheritance follows the shipped rule that *"a sub-WP inherits its parent's budget **when absent**"* and the fact that a coordinator's subtree shares one worktree and one authoritative join verification — the subtree is one fan-out unit, not N independently classified ones. The exception follows the same shipped word: a present cell is not an absent one, and `Review: panel` on a sub-WP raises that sub-WP to the ceiling exactly as it does on any other row. **A coordinator-owned parent derives from its own cells**, with one stated consequence: its `Verify` cell is `—` by the plan template's own rule (*"`Verify` is not inherited and is n/a for sub-WPs … n/a on a coordinator-owned parent row too — write `—`"*), so **`door` reads `false` there**. This is harmless because a coordinator-owned WP's merge already pays the project's full documented verification under `adr_0010` C-901 trigger (i), which supersedes the cell. **The first draft added a second ground that does not hold and it is withdrawn:** it claimed *"the granularity gate that made the WP a coordinator at all makes it `L` under C-1102, so it resolves to the ceiling regardless."* The shipped gate (`hex-core/references/workers/coordinator.md`) has **no size floor** — its preconditions are *"≥3 independent, WP-grain sub-tasks"*, decomposability, and *"no single sub-task touches more than 8–12 distinct files"* — so an `S` or `M` coordinator parent is authorable, and a `low` derivation there would collide with `models.md` Rule 5, whose `coordinator` cell at `low` is `—`, *"never spawned at that tier"*, leaving the fan-out **no defined spawn at all**. **The floor is stated as a rule in C-1109 rather than inferred from a correlation, and it is scoped to the coordinator kind that actually fans out: a WP owned by a *decomposing* coordinator — `adr_0013`'s `C-1219` Q2 kind, the one that splits the WP into dotted sub-WPs — floors at `min(T, medium)`.** **A *pipeline* coordinator (`adr_0013`'s `C-1219` Q1 kind), which owns a WP's phase pipeline and adds no sub-WPs, does not raise the floor**; `C-1219` gives such a coordinator to every ready WP when the ready set is ≥ 2 and the harness can nest (`C-1220` names the two exceptions), so an unscoped floor would mean no WP ever derives `low` and C-1108's collapse — this ADR's largest lever — would never fire at all. **The seam in one sentence: `adr_0012` decides which phases a work package runs and at what model class and review breadth; `adr_0013` decides how the workers running them are supervised, resourced and sub-orchestrated.** **No new inheritance mechanism** and no fifth status. | `protocol.md` § Parallel-by-default decomposition (sole source); the plan template's sub-WP comment |

### B. The degrade and attestation rules

| ID | Contract | Home |
|---|---|---|
| **C-1105** | **The degrade rule — a rule, not a preference. A flag whose source is absent, unreadable, or malformed reads `true`, never `false`.** It is never inferred from a sibling flag, never defaulted to a "known" value, and never borrowed from another WP. This is the fail-closed branch, and it is chosen on the split `adr0012-risk-flags.md` § 2 documents: every control gating identity or authorization defaults this way unconditionally (**AWS IAM implicit deny** — no matching Allow ⇒ Deny; **SELinux enforcing-by-default**), and the systems that ship fail-open do so **only** for availability reasons, always as a named and switchable choice, **never silently**. **The negative precedent, named because it is exactly this failure:** GitHub branch protection with a missing, empty, or all-invalid `CODEOWNERS` file silently stops enforcing "require review from code owners", with no operator-facing signal — a missed flag collapsing a pipeline, invisibly. That is the outcome this rule forecloses. **The read rule, because "absent, unreadable, or malformed" is not self-defining and this contract carries a fail-closed consequence.** The first draft named the outcome and left the predicate to the reader, which reproduces the CODEOWNERS *"missing, **empty**, or all-invalid"* ambiguity it cites as the thing to avoid. It adopts `hex-architect/SKILL.md`'s shipped `State:`-parsing discipline verbatim in shape: **(1) Where the row is read.** `memory.md` § Pointers ships **one combined entry** — *"where the project's security-sensitive / hot-path convention is documented"* — so the row is read as **two independent halves**, each resolved on its own; a row present but naming only one convention leaves the other **absent**. `sec` and `hot` never share a resolution. **(2) What is read — a *location*, never a value.** The half's value is the text between its convention label and the **first field separator** — `·`, `&nbsp;`, or end of line — trimmed, and it must resolve to a **repo-relative path to the file that documents that convention**. **The Pointers row never carries the convention itself: not an inline glob set, and not the literal `none`.** This is the constitution's own division of labour, not a stylistic preference — `DESIGN.md` makes Layer 2 *"cached pointers … never a second copy of project truth"* and `memory.md` classes `## Pointers` **"Never authoritative"** — and it is what keeps this round's own claim that *hex records **where** it lives, never what it says* true rather than contradicted by its first consumer. **(3) The catch-all, stated explicitly rather than implied.** **Anything else ⇒ `true`.** That includes: a half present but empty; a value that is not a repo-relative path; a path that resolves to nothing readable; and a value hex does not recognise at all. **(4) The target — where the convention actually lives, and the only place a value is read.** The target file is matched against a **closed enumeration**: the literal `none`, or a set of one or more globs. **A missing target ⇒ `true`**; **an empty target ⇒ `true`**; **a target resolving outside the repository root ⇒ `true`**, never followed (the containment rule — a pointer that escapes the repo is a pointer hex cannot trust to decide review depth, and `adr_0009` C-815 puts this input in the authoritative class); **a partially malformed glob set ⇒ `true`** (**any** invalid glob makes the whole target unreadable — never "use the valid ones", which is CODEOWNERS' `all-invalid` bug shape read as `some-invalid`); and anything that is neither `none` nor a parseable glob set ⇒ `true`. **(5) The one sentence that resolves the ambiguity `none` creates:** **`none` is declared *in the target file*, never inferred from an empty or missing target, and never written into the Pointers row.** An empty file and a file saying `none` are different facts; only the second is an attestation. **(6) Interaction with `memory.md` § Staleness, which pulls the other way.** That section's standing rule is *"verify on consumption … on a miss it re-discovers from project context, **updates the pointer in the same run**, and proceeds"* — repair-and-proceed. **Both apply, in this order:** re-detection runs first and, if it succeeds, the repaired pointer is what rules 1–5 read; if re-detection finds nothing, **this rule wins and the flag reads `true`**. Repair-and-proceed never means proceed-without-the-flag, and a run that repaired a pointer says so in the same degrade line C-1107 defines. **`sec` and `hot` resolve independently even though one Pointers row carries both conventions**: a row that names security-sensitive paths and is silent on hot paths leaves `hot` absent, therefore `true`. A half-attestation buys nothing, deliberately — the alternative is inferring "silence means none", which is the CODEOWNERS reading. **`door`'s fail-open is the single, argued exception** (C-1106), and hex's own shipped `sec` triggers (C-1103) are outside this rule entirely — they cannot be made unreadable by anything a project writes. | `protocol.md` § Parallel-by-default decomposition › The effective tier (sole source); one cross-reference clause in `memory.md` § Pointers naming the entry's two independent halves and stating that each half is a **location**, never the convention's own value |
| **C-1106** | **`door`'s fail-open asymmetry, and the general rule it does not break.** `door` reads `false` on an absent `Verify` cell, against C-1105's direction. **Three grounds:** (a) `door` is the **author-declared** flag — its absence means "the author declared nothing", a different fact from "hex could not read the project's convention"; (b) the other three flags still gate, so a WP with an unreadable convention is at the ceiling with or without `door`; (c) a plan with no `Verify` column at all **is refused the generation marker** (C-1114), so the fail-open branch is **unreachable except on coordinator-owned parent rows and sub-WPs**, where the plan template's own rule writes `—` in the `Verify` cell and C-1104 therefore reads `door` as `false` by construction. **On those rows the compensating control is C-1109's `medium` floor**, not the refusal — a decomposing-coordinator parent cannot derive `low` at all, and a sub-WP inherits its parent's tier. The first draft called the branch "structurally unreachable" without qualification; that was false, and the qualified form is the true one. **The general rule, corrected. The first draft wrote *"a fail-safe default is direction-relative, not source-relative"*; that is unsound and is withdrawn.** On an absent row, `adr_0010` C-903's clause 1 goes **vacuous** ⇒ *fewer* full verifications, and a fail-open reading here would ⇒ *less* review. **Both consumers move effort in the same direction — down — so a direction-relative rule returns the same answer at both sites and condemns C-903 rather than reconciling it.** **What actually reconciles them is residual risk — how many independent backstops survive the default.** Behind C-903's vacuous clause 1 sit **three**, none of which the absent row touches: the checkpoint counter, the level-clear trigger, and the un-lowerable final gate. The absence costs one *earlier* full verification out of several and the run still gets one. Behind a fail-open `sec`/`hot` here sits **one** — C-1117's branch review — and it is a *review*, not a verification, arriving after the collapsed phases and the reduced model class are already spent (C-1116). **The safe default is decided by the backstop count behind it, not by the direction it moves effort.** One source, two absence semantics, one honest reason. **The consequence neither site stated, and it is the one a reader most needs: an attestation of `none` disarms two controls, not one.** The row that clears `sec` here is the **same row** C-903 clause 1 reads as its high-risk checkpoint trigger. Declaring an empty security-sensitive set therefore buys tier reduction **and silently removes a pre-existing, unrelated full-verification trigger** — a control that predates this ADR and has nothing to do with it. **Buying speed here removes a control there, and nothing in either contract announces it.** Both sites carry it: the cross-reference is not "see the other reading" but *"this row feeds two consumers; clearing it disarms both."* | `protocol.md` § Parallel-by-default decomposition (sole source); a cross-reference clause in § Checkpoints beside C-903 clause 1, carrying the double-disarm sentence verbatim |
| **C-1107** | **An explicit attestation of *none* is a readable source, and the degrade is announced once with its remedy.** *Readable-`none`:* a convention whose **target file** declares an **empty set** — the literal `none` — makes that convention's flag read `false`. **The attestation is read from the target the Pointers row locates, never from the row itself** (C-1105 rule 2: the row carries a location, never a value), which is what keeps the attestation a version-controlled, diffable, blame-able declaration in project truth — the CODEOWNERS-and-git-crypt pattern — rather than a value cached in a skill-managed index. **The already-frozen `perspectives.security-sensitive-paths: none` key clears `sec` and `sec` only, and it clears it under `config.md`'s own conditions — both of them, verbatim.** It is a *security* attestation, defined in `config.md` as *"`none` asserts this project has no security-sensitive path"*, and it says nothing about hot paths, so `hot` still needs the Pointers row. **The first draft kept only half of the key's shipped meaning and that is corrected here.** `config.md` merge rule 5 (`adr_0003` C-218) honours that key *"**only** when both hold: (a) the block declares `perspectives.security-sensitive-paths: none`, and (b) no security-sensitive path matched this run — no `always` rule whose `when:` names a security path, and no hit on `classify.md`'s shipped security markers"*, closing with *"Every other case, **including the ambiguous one** … is a refusal."* **This ADR requires both conjuncts, unchanged — and pins the grain at which (b) is evaluated, which `config.md` had no reason to state.** There, (b) is a **per-run** predicate (*"no security-sensitive path matched **this run**"*); here `sec` is a **per-WP** flag, so **(b) is evaluated per WP, over that WP's own `Expected Files`** — the same `classify.md` marker test C-1103 already runs on that set, plus any `always` rule whose `when:` names a security path in it. A marker hit on some *other* WP's files neither sets nor clears `sec` here; what (b) refuses is the attestation **for the WP being resolved**. `config.md`'s own rule is untouched at its own grain. Keeping (a) and dropping (b) — which is what the draft did — would give an **already-frozen key a second, weaker meaning that activates on a bundle upgrade**, so a project whose attestation is currently *refused* by rule 5 would silently start clearing `sec`. That is precisely the failure driver 4 exists to prevent, committed against `config.md` instead of against a plan. Conjunct (b) is also what makes C-1103's shipped triggers coherent: the same `classify.md` markers that force `sec` true there are what refuse the attestation here — **one marker table, one answer, in both directions.** **`config.md` gains no key and no clause** (C-1115); this contract cites rule 5, it does not restate or amend it. *The announcement:* a run in which any flag degraded prints **one line, once**, naming **which** flag, **which** convention was unreadable, the consequence (*"every WP resolves at the ceiling"*), and the one-line remedy (the Pointers row to write, or the attestation of none). **A silent fail-closed is how a project never learns why it got nothing** — the whole failure of the CODEOWNERS shape is that it is silent, not that it fails open. **It is a new trigger class at the gate, not a member of the config-disclosure list.** `protocol.md` scopes config disclosure to *"when a `hex.md › Preferences` config block changes what the run does"*, and an absent, unreadable or malformed **Pointers** row is not a config block — filing it under that enumeration would widen a scoped list by analogy, which is exactly the move C-1101's closed-enumeration discipline forbids. It is added as its own named trigger — **risk-flag degrade** — printed at the same gate, in the shipped disclosure **grammar**, beside every other resolved axis. (C-1122's model-override line **is** a Preferences config block and does join the existing list.) | `protocol.md` § The meta-plan approval gate (the degrade line, as a new trigger class) + § Parallel-by-default decomposition (the attestation rule, sole source) |

### C. What the effective tier drives

| ID | Contract | Home |
|---|---|---|
| **C-1108** | **Phases — at effective tier `low`, Stub + Specify + Implement collapse into one `builder` spawn, and the phase-ordering property is checked by the orchestrator, not reported by the builder.** The builder writes the public surface, then the failing tests, then the implementation, in **one turn**. **This is the single largest wall-clock lever in the ADR** — three serial round trips become one. **Verify-Architecture does not run** at effective `low`, which is already true for a `self` budget and already true of `hex-execute/tier-low.md`'s shipped Phase 3. **The check, replacing the first draft's self-reported transcript:** the collapsed builder **commits the stubs and the specification tests as its first commit on the WP branch, before the implementation commit**, and **the orchestrator runs the project's test command at that commit and requires it to fail.** The builder's output contract names that commit's SHA; the check is then `git` and the project's own test command, and nothing else. **Why the transcript was replaced.** The first draft required the builder to return the pre-implementation test output. Three reviewers reached the same objection independently and it is conceded in full: **the artifact was produced by the same worker whose claim it checks, nothing re-ran it, and it is satisfied trivially by writing the implementation first and stashing it.** Bondarenko et al. (arXiv 2502.13295) is the adjacent precedent for why a grader the agent can reach is not a grader. **The deviation's whole defence was that the property becomes *checkable* rather than assumed** — a defence an unfalsifiable artifact does not supply, which under `protocol.md` § Constitution gate makes the deviation unjustified and the ADR a Request Changes. The committed-stub check restores it: the ordering is a fact about the branch's commit graph, verified by a party that did not write it. **It costs no extra round trip** — the builder already commits on its WP branch, and merge-time re-validation already shells out to `git` — so the collapse's three-trips-to-one claim is unaffected. **What is given up is stated in the contract, not only in the rationale: author≠verifier at the WP level.** The check recovers the **temporal** property (tests existed and failed before the implementation); it does not recover **independence** — the tests are still written by the agent that then implements against them — and no clause here claims it does. The backstops are the `review=minimal` batch's `spec` reviewer and C-1117's ceiling-tier branch review. **Model-cell resolution, corrected.** The first draft claimed *"no model-cell conflict arises"* because `models.md`'s `builder:stub`, `builder:implement` and `tester` rows all read `fast-balanced` at `low`. That holds for the **shipped** matrix only: Rule 2 puts the instantiated `hex.md › Preferences` matrix and its per-cell overrides at resolution **step 1, above the shipped default**, so a project pinning any one of the three makes the collapsed spawn's three source cells disagree. **The rule: the collapsed spawn resolves each of the three cells and reads the highest**, disclosed under C-1122 like any other override-driven raise. Never the lowest — a project that pinned `tester` to deep-reasoning asked for a stronger test author, and collapsing must not be the thing that silently revokes it. At effective `medium` and `high` the four-phase list is unchanged in every byte. | `protocol.md` § The Review-Fix Loop (the phase list, sole source); `hex-execute/tier-low.md` and `tier-medium.md`/`tier-high.md` take a conditional-on-effective-tier rule (not a one-clause qualifier — see § Migration, edit-site class 4); `hex-execute/SKILL.md`'s phase table |
| **C-1109** | **Model class — `models.md` cells resolve against the WP's effective tier, not the plan's.** The matrix's columns are the tiers from § Tier grammar; this contract fixes **which** tier a given spawn reads, with one rule and no row list: **a spawn made for a work package reads that WP's effective tier; a spawn made for the run reads the plan tier.** So `builder:stub`, `builder:implement`, `tester`, every `reviewer:*`, `doc-reviewer` and `coordinator` follow the effective tier during execution, while `explorer`, `architecture-explorer` and `researcher` — spawned for the run, not for a WP — follow the plan tier. `architect` is `deep-reasoning` in all three columns, so the split is moot for it and no special case is written. **Consequence, and RCA root cause 2's model half:** a size-S no-flag WP inside a `high` plan runs `builder:implement` and `tester` at **fast-balanced**, not deep-reasoning. **One clause resolves the collision with Rule 5: a WP owned by a *decomposing* coordinator floors at `min(T, medium)`** — never flatly at `medium`, because at `T = low` a flat floor would produce `effective > T` and break C-1101's own ceiling invariant. Rule 5 tier-gates `coordinator` — its `low` cell is `—`, *"never spawned at that tier"* — and the shipped granularity gate in `hex-core/references/workers/coordinator.md` has **no size floor** (its preconditions are *"≥3 independent, WP-grain sub-tasks"*, decomposability, and *"no single sub-task touches more than 8–12 distinct files"*), so an `S` or `M` coordinator parent is authorable and would otherwise derive `low` and have **no defined spawn at all**. C-1104's claim that the granularity gate makes such a WP `L` under C-1102 is a plausible correlation, not a rule, and it is not relied on here. **The floor is scoped to the coordinator kind that fans out, and this is the seam with `adr_0013`.** That ADR's `C-1219` splits one gate into two questions: *(Q1) does this WP get a coordinator at all?* — **yes whenever the ready set holds ≥ 2 WPs and the harness can nest**, with `C-1220` naming the exceptions — and *(Q2) does that coordinator split the WP into dotted sub-WPs?* — the unchanged ≥ 3-sub-task judgment. **Only Q2's decomposing coordinator raises the floor**, because Q2 is what needs a `coordinator` spawn to fan work out. **A Q1 pipeline coordinator, which merely owns the WP's phase pipeline and adds no sub-WPs, does not** — an unscoped floor composed against `C-1219` would give every ready WP a coordinator, floor every one of them at `medium`, and leave C-1108's collapse structurally unreachable, silently deleting this ADR's largest lever. **The division of ownership in one sentence: `adr_0012` decides which phases a work package runs and at what model class and review breadth; `adr_0013` decides how the workers running them are supervised, resourced and sub-orchestrated.** The floor is stated in the model contract because that is where the `—` lives; C-1104 cross-references it. **`models.md` Rules 1–5 are otherwise untouched** — cells stay recommendations rather than floors or ceilings, a judgment escalation above a cell still requires an announced reason, and a silent escalation is still a spec violation. What changes is only which column the cell is read from. | `models.md` § The matrix (one clause under the matrix) + § Rules rule 2, linking `protocol.md` (sole source) |
| **C-1110** | **Review breadth — the `review=` axis value follows the effective tier.** `low` → `minimal`, `medium` → `full`, `high` → `adversarial`, exactly the per-tier default table `hex-execute/overlays.md` already ships, read per WP instead of per run. The axis remains a **ceiling** in the sense that file already states — *"Both the `review` and `loop-rounds` axes are **ceilings**"* — and a user flag still overrides the classifier for the run as a whole, with the shipped downward-override announcement (*"high tier recommends adversarial review — running `full` per user flag"*) unchanged. **The run-level axis and the per-WP derivation compose by `min`:** a WP's breadth is the lower of its effective tier's default and the run's resolved axis value, so a user asking for less still gets less and a derivation asking for less than the user's flag is honoured. **The composition order is stated, because `min` alone contradicts C-1112.** On a `high` ceiling with `--review=full`, a `panel` WP would otherwise be handed both `full` (the run axis) and `adversarial` (C-1112's "`panel` raises all four axes"). **One sentence resolves it: `panel` raises the derived *tier* to the ceiling; the run's resolved axes then apply as a `min` cap over the result.** So that WP runs at effective `high` — four phases, the ceiling's model cells, a 3-round cap — with `review=full`, because the user's downward flag caps the breadth axis last. `panel` buys the pipeline, not an escape from the user's own request. **The identical order governs `loop-rounds` (C-1111): `panel` raises the tier, then the lowest of {tier default, run request, stored ceiling} applies.** **The adversary axis is the one per-tier default the effective tier does **not** move: it stays pinned to the plan tier `T`.** `hex-execute/overlays.md` ships a fifth per-tier default beside the four this ADR retargets — the cross-model adversary gate (`low` → `off`, `medium` → `off` with a classifier auto-on, `high` → `on`) — and a WP that derived `low` inside a `high` plan **still runs it**. The reason is stated rather than assumed: the cross-model pass is a **run-level assurance decision** on the branch diff, and letting a per-WP size estimate switch it off is precisely the global skip switch the escape-hatch research names as the failure mode. Wave 0's C-921/C-922 deadline and skip grammar are untouched. | `hex-execute/overlays.md` § review axis (one clause) and § adversary axis (one clause pinning it to the plan tier), both linking `protocol.md` (sole source) |
| **C-1111** | **Loop rounds — the `loop-rounds` cap follows the effective tier.** `low` → 1, `medium` and `high` → 3, the shipped per-tier defaults read per WP. **The stored `hex.md › Preferences` `loop rounds` ceiling is untouched and still binds**: `protocol.md`'s rule that the effective cap is *"the lower of the stored value and the run's resolved request"* now takes a third term, and the cap is the lowest of the three. The stored value still never raises a tier default and never lifts `low` above one round; `limits.*` still sit outside the later-wins spawn-selection precedence. **Plan-artifact scope is untouched** — it moves only via the explicit `artifact loop rounds: N` limit, as today. | `hex-execute/overlays.md` § loop-rounds axis (one clause) + `protocol.md` § The Review-Fix Loop (the ceiling rule gains one term, sole source) |

### D. The `Review` direction flip and the generation marker

| ID | Contract | Home |
|---|---|---|
| **C-1112** | **`Review` survives with its direction flipped — and the direction invariant is preserved by the flip, not broken by it.** `adr_0010` C-905's invariant reads: *"a column whose baseline is the maximum may only lower; a column whose baseline is the minimum may only raise"*, with each baseline set at the unsafe end so the unsafe direction is unreachable. **The effective tier moves `Review`'s baseline off the maximum** — the derived breadth is now the WP's effective-tier Round-1 set, not the plan tier's panel — so honouring the invariant *requires* flipping the column. **`Review` becomes raise-only against the derived breadth, capped at the ceiling.** Operatively: a cell naming a breadth **at or below** the derived one is **inert** — honoured as a no-op, never a defect — and a cell naming a breadth **above** it is honoured up to the ceiling. **`Review: panel` raises the WP's effective tier to the ceiling** — all four axes, not breadth alone, because breadth alone yields the weakest combination (an adversarial panel over a single collapsed builder turn). It is the one explicit escape hatch `adr0012-precedent.md` recommendation 5 asks for: *higher than derived, never lower, never above the ceiling*. It meets both structural properties the escape-hatch research requires — **narrow scoping** (one cell, one WP, never a global switch) and **durable visibility** (it appears in the plan's diff and in the announce block's per-WP line, C-1119). **The degenerate case is named rather than left to be discovered: in a `low`-tier plan the hatch is a no-op.** `panel` raises the WP to the ceiling, and at `T = low` the ceiling **is** the collapsed pipeline — one builder spawn, `review=minimal`, one round. An author who wants more than that on a `low` plan has no cell to write it in; the lever is the plan's own `Tier:`, and C-1117's branch review still runs at that ceiling. Accepted, because raising a WP above its plan's declared ceiling is the one property C-1101 makes impossible by construction. **Consequences, stated plainly.** `self` and `light` become inert in derived-generation plans: authoring `self` on a WP the function derived as ceiling-equivalent is now **a no-op, not a defect**. **What that removes is the ability to author a review *class* below the derived one. It does not make mis-authoring "structurally impossible" — that phrase was in the first draft, it is false, and it is struck everywhere.** `Size` is still authored and is still the sole reduction input; § Consequences › Negative prices the direction the error moved (from a column that fails slow to one that fails silent) and § Judgment calls 4 states the residual. **The two guards are affected differently, and the first draft called both "vacuous" when one of them is *contradicted*.** The shipped **upward** guard (*`self` or `light` on a security-, hot-path-, large or cross-area WP is a plan defect*) genuinely has nothing left to catch: those cells are inert. But `plan_wave0_quick_wins` **C-928's new downward half** declares *"`panel` on a size **S or M**, **single-area** WP whose expected file set contains **no** security-sensitive or hot-path file"* a plan defect — **which is precisely this ADR's sanctioned escape hatch.** A planner following C-928 must flag as a defect the one cell C-1112 exists to honour. That is a contradiction, not a vacuity, and it is resolved by **suppression, named at its source**: in a plan carrying the generation marker, **C-928's downward half does not apply**, and `Review: panel` on a small flag-free WP is a deliberate raise, never a defect. Both guards stay live and unchanged in legacy plans, where all three `Review` values still do all three jobs. **The suppression is written at C-928's own definition site — `protocol.md` § Parallel-by-default decomposition, where wave 0 C-928 lands it — and at the three `hex-plan` tier files that link it under C-929** (`tier-low.md`, `tier-medium.md`, `tier-high.md`); those files carry links rather than restatements after C-929, so the suppression rides the one definition and the links need no edit of their own. The column is **not renamed**: a rename breaks every legacy plan and costs a *Plan visualization* lock amendment this ADR otherwise avoids entirely; the resulting naming debt is recorded in § Consequences instead. | `protocol.md` § The Review-Fix Loop (the budget **consumption** bullet — the one carrying *"The budget only lowers breadth below the tier baseline"*) + § Parallel-by-default decomposition (the **assignment** bullet and C-928's guard), sole source; the plan template's table comment |
| **C-1113** | **`Verify` survives unchanged and gains one more consumer.** Its raise-only direction, its `scoped` floor, its `Verify-default:` plan-level escape and its merge-gate meaning are untouched in every byte. It gains the `door` flag as a reader (C-1103). **The "and nothing else" clause is already being widened by `plan_wave0_quick_wins` C-924** — from the merge gate alone to **two gates: the merge gate and the Review-Fix-Loop exit gate that immediately precedes it**; C-924 states in its own words that *"the Implement-phase gate is **not** coupled to the cell (D6, C-925)"*, so it is not one of them — and this ADR does **not** re-claim that erratum; it adds a **third consumer** on top of C-924's widened text and records the compounding cost in § Judgment calls 2. **No new cell, no new value, no change to the column's vocabulary or position.** | `protocol.md` § Parallel-by-default decomposition (the `Verify` bullet — one clause added after wave 0's C-924 lands) |
| **C-1114** | **The generation marker — one optional Status line, `- Effective-tier: derived`.** **Presence** ⇒ this ADR's semantics. **Absence** ⇒ pre-`adr_0012` semantics **byte-for-byte, forever: never a prompt, never an error, never a migration step, and never a rewrite of the plan to add the line.** This mirrors `adr_0010` C-905's `Verify-default:` precedent exactly — an optional Status line that changes how existing cells are interpreted, with absence meaning the older reading — and the ecosystem shape `adr0012-risk-flags.md` § 3 documents as uniform: Node's `package.json` `"type"`, Rust's `edition`, Go's `go` directive, all of which **freeze the legacy behaviour exactly** and make the new behaviour opt-in per artifact. **`derived` is the only value v1 accepts. An unrecognized value is a refusal, not a default** — the catch-all discipline of `adr0012-risk-flags.md` recommendation 1 (*"an unrecognized or malformed input escalates, it does not default to a known flag"*), and the one place this ADR chooses a hard stop over a degrade, because a marker whose value hex does not understand means the plan was written against a generation hex cannot execute. The refusal names the value read and the values understood, in the shipped `Error:` / `Fix:` pair. **The parsing rule, stated because a contract carrying a hard refusal cannot leave "unrecognized" to the reader.** It is `hex-architect/SKILL.md`'s shipped `State:` discipline, applied verbatim in shape: the line is read **line-initial** and **only from the Status block above the first `##`** — never a match anywhere in the body, so a plan quoting `- Effective-tier: derived` inside a code fence or a prose paragraph is not a marker. The **value** is the text between the line's `:` and the **first field separator** — `·`, `&nbsp;`, or end of line — **trimmed**, then matched **exactly**. Both halves carry weight for the same reasons `hex-architect` gives: a whole-line read must not refuse a valid two-field line, and a substring read must not accept `derived (proposed)`. **A line present with an empty value is a refusal**, not an absence — a hand-truncated marker is a different fact from no marker. **An absent line is legacy, forever, and is never a refusal** (C-1123). **A marker on a plan with no `Verify` column is a refusal.** The `Verify` column is `door`'s only source, and C-1106's ground (c) — *"a plan with no `Verify` column predates the generation marker and runs pre-`adr_0012` semantics anyway"* — is **only true if this refusal exists**; without it the ground is false and `door`'s fail-open branch is reachable on a current plan, which is exactly the missing-input case C-1105 forecloses everywhere else. **The second reason is sharper and is the one to read twice:** hand-adding the marker to a legacy plan flips **every blank `Review` cell** from meaning `panel` to meaning *the derived breadth* — the one genuinely unsafe direction of the flip, applied silently and in bulk to a plan nobody re-authored. A legacy plan is exactly the plan most likely to have blank cells and no `Verify` column, so the refusal covers both hazards with one check. The `Fix:` line says to run the plan through `/hex-plan`, which writes both the column and the marker, rather than adding the line by hand. **The known trap, addressed:** every one of those ecosystems now tells authors to write the field explicitly because *the absent-default's meaning can never safely change later*. So: `/hex-plan` writes the line on **every** new plan; **absence is frozen as pre-`adr_0012` permanently**, and a future generation takes a **new value**, never a redefinition of `derived`. Go's second trap — that a chosen default value may itself need walking back — is why the only value ships as a literal rather than as a version number to compare. **Placement: immediately after `Tier:`**, because it qualifies that line and a reader seeing `Tier: high` must see "and it is a ceiling" in the same breath; it is a single fixed line ahead of the multi-row `Repos:` ledger, which is the placement ground C-907 established. `adr_0010`'s own two lines still sit immediately after `Next:` and no erratum is owed. **`plan_wave0_quick_wins` writes no marker** and its plans therefore run legacy semantics, which is correct — they predate this ADR. | plan template Status block; `protocol.md` § Parallel-by-default decomposition (the semantics, sole source); `hex-plan/SKILL.md` (the write) |
| **C-1115** | **Two stated non-changes, with their grounds.** **(a) No new plan-table column, so `DESIGN.md`'s *Plan visualization* lock is NOT amended.** Every input the function needs is a cell that already exists (`Size`, `Expected Files`, `Verify`) or a pointer that already exists. That lock's enumeration has been amended by explicit act **four times** — `status` (round 5), the review budget (the 2026-07-20 perf pass), `Repo` (round 8, `adr_0004` C-302) and `Verify` (round 12) — and a fifth was avoidable here, so it is avoided. **A Status line is not inside the lock's scope**: the lock enumerates *the WP table's canonical column set*, and `adr_0010`'s `Reviewed:` line is the precedent — a Status line landed with no lock amendment of its own. Round 12's `Verify-default:` rode amendment 3 only because it was a table-wide default for the column being added; there is no column here for anything to ride. **(b) No new `config.md` key, and the frozen top-level vocabulary of six (`adr_0003` C-223) is not reopened.** Every value has a carrier that costs no vocabulary: the marker is a Status line, the flags are cells and one existing pointer, the size classes are shipped text. `DESIGN.md` round 12's own adjudication is the precedent — *per-WP budgets are plan-artifact fields, not config* — and the attestation of none reuses `config.md`'s **already-frozen** `perspectives.security-sensitive-paths` key rather than adding a sibling. | (no edit — a stated non-change) |

### E. The backstops

| ID | Contract | Home |
|---|---|---|
| **C-1116** | **Backstop 1, runtime — the merge-time budget re-validation becomes an effective-tier re-derivation.** `protocol.md` § Parallel-by-default decomposition already ships the sentence: *"Budgets are re-validated at merge time: alongside the merge-time file-set re-validation, a WP whose actual diff outgrew its budget class … escalates to the next budget and its review re-runs at that breadth before the merge — a plan-time estimate never caps review of what was actually built."* That sentence becomes an **effective-tier** re-derivation: the same function (C-1101) is re-run against the **actual merge diff** — `size` from the diff measured on C-1102's table, `sec`/`hot` from the actual changed-file list, **`hub` from the actual changed-file list too**, `door` unchanged (it is an authored declaration, not an observation) — using the file list `git diff --name-only <base>..<wp-branch>` **already produces** for merge-time file-set re-validation, so this adds no command. **`hub`'s re-derivation is a correction against the first draft, which exempted it.** The exemption contradicted this contract's own sentence (*"the same function re-run against the actual merge diff"*) and it diverged from `adr_0010` C-903 clause 2, whose byte-identical predicate **does** evaluate against the merge diff. It rested on the claim that declared sets are guaranteed upper bounds — *"contractual, not empirical"* — which **merge-time file-set re-validation's own remedy falsifies**: an out-of-set diff is repaired by **widening the declaration**, so the declared set does not bound the actual one, and `DESIGN.md` round 13's two-declared/thirteen-merged WP is the empirical case. An undeclared file this WP actually touched may be another WP's declared file; only the actual list can see it. **The re-derived `hub` compares this WP's actual changed files against every other WP's `Expected Files`, one intersection over a list the merge already has.** **If the re-derived tier is above the plan-time one, review re-runs at the re-derived breadth before the merge.** **The limit is stated rather than papered over: only review can be restored.** The collapsed phases already ran and the model class is already spent; a WP that under-declared cannot have its stub phase re-separated or its implementation re-run at a higher class. **The plan-time estimate is therefore load-bearing in a way `adr_0010`'s `Review` re-validation was not**, and C-1117 is what covers the rest. Google TAP's postsubmit discipline is the shape — the periodic re-validation does not trust the presubmit selection — in the bounded form a hex run admits. | `protocol.md` § Parallel-by-default decomposition (the existing re-validation sentence, amended in place) |
| **C-1117** | **Backstop 2, branch level — the mandatory `/hex-review` becomes mechanical, at the ceiling tier.** `protocol.md` already states that a `self` WP *"is deliberately un-reviewed at the WP level — which makes the branch-level `/hex-review` pass **mandatory before the feature branch lands on the trunk** for any plan containing one; the execution handoff records it"*, and § Delta round scope repeats that *"the mandatory branch-level `/hex-review` is its backstop"*. **It is advisory prose enforced by nothing mechanical**, because hex never pushes and landing is the human's step. This ADR makes it real with one clause on machinery that already exists: **a plan containing any WP whose effective tier fell below its ceiling does not reach its terminal review state — `done`, or `landing` for a plan carrying a `Repo` column — until a branch-level `/hex-review` has run at **no less than the plan's ceiling tier**.** The enforcement point needs nothing new: `/hex-review` is already the **sole writer** of that state (`adr_0005` C-410) and already carries one precondition of exactly this shape (`adr_0010` C-913(f)'s stranded-set rule). This is a second precondition on the same write, not a second writer. **The ceiling is a floor on the review's tier, never a cap:** `/hex-review` classifies its own tier from actual diff metrics, and the resolved tier is `max(classified, ceiling)` — a large diff on a `medium`-ceiling plan is still reviewed at `high` if its own classifier says so. **The ceiling floors an explicit `--tier` flag too, and this needs saying because `overlays.md` § Precedence otherwise decides it the other way:** that section's rule is *"User-supplied flags always override classifier-inferred overlays"* — later wins — so `/hex-review low` on a `high`-ceiling plan would resolve `low` and the backstop would evaporate at the one moment it exists for. **The precondition is on the *tier*, not on the invocation:** the pass satisfies C-1117 only when it ran at ≥ the ceiling, so a lower flag is honoured for the run and simply **does not discharge the precondition**, with the shipped downward-override grammar naming why — `"ceiling high (plan) floors --tier low — this pass does not satisfy the adr_0012 backstop"`. The ceiling is the one input `max()` is taken over that no flag can lower; the ADR would otherwise have a backstop a single command-line argument removes. **`T` here is the plan's Status-block `Tier:`, the same pin C-1101 states**, so `/hex-execute low <high-plan>` cannot lower it either. **The precedent this cites is a discipline, not an enforcement, and the contract says so plainly:** Zuul's gate and Gerrit's `Verified` are **submit** requirements enforced by a forge; hex never pushes outside `/hex-finalize` and that skill's gate is a **human approval**, so what C-1117 blocks is a plan reaching `done` / `landing` — **a field in a markdown Status block.** A human who ignores it can still merge. The borrowed property is *"no tier low enough to skip it"* (`adr0012-precedent.md` recommendation 3); the borrowed enforcement is not available and is not claimed (§ Judgment calls 10). | `protocol.md` § The Review-Fix Loop (the budget bullet's mandatory-review clause, amended in place, sole source); a one-clause precondition qualifier at `hex-review/SKILL.md`'s verdict write and in `archive.md`, beside C-913(f)'s |
| **C-1118** | **The execution handoff lists the reduced WPs.** `protocol.md` § Handoff contract makes the handoff block the required final message of every run. `/hex-execute`'s block gains **one line per WP whose effective tier fell below its ceiling**, naming the WP, its effective tier, its ceiling, and the inputs that produced the reduction — so the human deciding whether to run the branch review can see **what the backstop is covering** rather than being told one is owed. It reuses the shipped sentence's own promise (*"the execution handoff records it"*), which today records only that a `self` WP existed. Absent any reduction, the lines are absent and the block is unchanged. | `hex-execute/SKILL.md` § handoff (additive) |

### F. Announce, attribution and observability

| ID | Contract | Home |
|---|---|---|
| **C-1119** | **The announce block gains a per-WP effective-tier line and a histogram — reusing the histogram grammar wave 0 ships, not inventing a second one.** `plan_wave0_quick_wins` C-930 defines a budget histogram — *"buckets keyed `<Size>:<Review>`, dot-separated, ordered by `Size` then `Review` **in the order each vocabulary declares them** (`S, M, L`; `self, light, panel`) … A bucket with count 0 is omitted"*, printed by `/hex-execute` in its announce block and by `/hex-plan` at the Decompose gate. **This ADR adopts that grammar verbatim and replaces its bucket key** with the effective tier: `effective tier: low 6 · medium 2 · high 1 (ceiling high)`. **It replaces rather than joins**, because in a derived-generation plan `Review` is inert (C-1112) and a histogram bucketed on an inert column is noise — *"two logs of the same events … is the drift the sole-definition rule exists to prevent"*, `adr_0010`'s own words about retiring `## Progress Log`. C-930's line stays exactly as it is for legacy plans. **There is no deviation from C-930's ordering rule.** The first draft claimed one, on a misquote — it read C-930 as *"counts ascending by bucket name"* and then argued at length that `low · medium · high` had to override an alphabetical order. C-930 says no such thing: its rule is *the order each vocabulary declares them*, and the tier vocabulary declares `low < medium < high`, so applying C-930 **unchanged** yields exactly the wanted order. **The misquote and the deviation paragraph built on it are both withdrawn**; C-1119 takes C-930's grammar whole, key included in the substitution and ordering rule untouched. **The line is aggregate-first and drillable**, per `adr0012-risk-flags.md` § 7's three properties: the histogram is the aggregate, the per-WP lines are the drill-down, and C-1120 supplies the attribution. Printed by the same two skills at the same two points as C-930. | `hex-execute/SKILL.md` and `hex-plan/SKILL.md` announce steps; the grammar's one home is `protocol.md` § Parallel-by-default decomposition › The effective tier (sole source) |
| **C-1120** | **A fifth source attribution: `derived`.** `protocol.md` § The meta-plan approval gate today attributes each announced item to one of four sources — *`classifier` / `hex.md preference` / `user flag` / `tier baseline`*. The effective tier is **none of them**: it is derived from the plan artifact. The enumeration gains **`derived`**, and a derived item's attribution **names the inputs that produced it, per WP** — `WP1 low (derived: S, no flags) · WP4 high (derived: sec)` — so *"why was this WP classified low"* is answerable from the block alone, with no re-run. **With C-1101's caveat carried here rather than left at its source: the value is recomputed at each WP's own spawn time, so the Decompose-gate and run-start listings are *snapshots, labelled as one*.** The value a WP actually ran under is announced by `/hex-execute` **at that WP's spawn**, and the run's final answer is the execution handoff's per-WP line (C-1118). A WP whose `Size` or `Expected Files` cell changed mid-run therefore has two announced values, both true of their own moment, and the block says which is which. This is Bazel `--announce_rc`'s discipline (print the value **and where it came from**) and OPA `--explain`'s (the decision **and** why), applied to the one value in the run that no human wrote. The four existing sources and every other line of the block are unchanged. | `protocol.md` § The meta-plan approval gate (the source enumeration, sole source) |
| **C-1121** | **Nothing is persisted, and this is a decision rather than an omission.** The derivation is a **pure function of the plan artifact plus one pointer** — *artifact*, not *table*, because `door` resolves through the `Verify-default:` Status line when the cell is empty (C-1101) — recomputed on every read at zero cost. No cache, no derived column, no state file, at any depth (`adr_0010` C-914, driver 7). Kubernetes is the model: `kubectl describe pod` shows `QoS Class:` without the API ever storing it. **The announce block and the execution handoff are the inspectable record** `adr0012-precedent.md` recommendation 4 and `adr0012-risk-scoring.md`'s auditability recommendation ask for — itemized, recomputed every time, exactly Scorecard's *"recomputed from repo state on each run … nothing is set once and trusted"* model. A stored copy would be a second source for a value the table already determines and would drift the first time a `Size` cell is edited. **What is given up is the historical half** — no log of how a WP's derivation changed over the plan's life — and the same research records that no surveyed dev-tooling ships one either. Recorded as a departure in § Departures 1. | (no edit — a stated non-change) |
| **C-1122** | **A `hex.md › Preferences` model override that raises a spawn above its effective-tier cell becomes an announced config-disclosure line.** `models.md` Rule 2 puts the instantiated matrix and its per-cell overrides at resolution step 1, **above** the shipped class default, so a project that pins every reviewer role to deep-reasoning at every tier — RCA root cause 3, `ocx`'s actual configuration — silently wins over the matrix today, and Rule 1's announce-or-it-is-a-spec-violation requirement bites only on **step 3** judgment escalations. Under this ADR the shipped cell is now per-WP, so such an override is the mechanism by which a derived reduction is quietly cancelled. **It stays possible and becomes visible:** one config-disclosure line per raised spawn, in the shipped `[…]` grammar, naming the role, the class, the WP's effective tier, and `hex.md preference` as the source. It joins the four triggers `protocol.md` § The meta-plan approval gate already enumerates. **No override is blocked, weakened or reordered** — the ocx-style pin keeps working exactly as written, and the only change is that it is now stated at the gate. | `protocol.md` § The meta-plan approval gate (the config-disclosure trigger list, sole source); `models.md` Rule 2 gains one cross-reference clause |

### G. Compatibility and migration

| ID | Contract | Home |
|---|---|---|
| **C-1123** | **Presence-check compatibility, joining `adr_0010` C-915's rule rather than restating it.** Every reader branches on **field presence**, never on a compared version number. **Absent `- Effective-tier:` line ⇒ pre-`adr_0012` semantics, byte-for-byte, permanently** — plan tier drives everything, `Review` is lower-only against the tier panel with a missing cell meaning `panel`, the four-phase list runs at every tier, `models.md` reads the plan tier, and wave 0's two-direction budget guard is live. **Never a prompt, never an error, never a rewrite.** A plan without the line is a **permanently valid shape, not a migration backlog** — C-915's own reasoning applies unchanged: a markdown Status block has no storage or index cost, so unlike a database expand-contract there is no forcing function to ever deprecate it. **No `Plan-Schema:` field is added and none may be inferred.** The one deviation from C-915's shape is deliberate and is C-1114's: an **unrecognized** marker value is a refusal, where every C-915 field degrades. A missing field and a field hex cannot read are different facts, and `adr0012-risk-flags.md` recommendation 3 draws exactly this line — *"A missing whole-plan marker is a legitimate legacy signal; a missing single flag inside a current plan is the missing-input case."* | `protocol.md` § Worktree work-package mechanics, beside C-915's no-marker sentences (one clause) |
| **C-1124** | **Fail-closed and backward-compatible are the same state — for the plans this claim is scoped to, and the scope is stated because the first draft's unscoped version was false.** A project that has never declared a security-sensitive / hot-path convention gets `sec = hot = true` for **every** WP (C-1105), so every WP resolves at the ceiling: same phases, same model cells, same breadth, same round cap. **The byte-identity holds only for a marked plan whose `Review` cells are absent or `panel`.** Where a marked plan carries `self` or `light` cells it does **not** run byte-identically to pre-`adr_0012` — **it runs strictly more review**, because C-1112 makes those two values inert while the ceiling supplies the full panel. S-1107 walks exactly that case, and it is not a corner: **wave 0's C-928 instructs planners to author `self` and `light` cells**, so plans full of them are the expected output of the release immediately preceding this one. The direction is safe — more review, never less — but it **is** a behaviour change in an unattested project, which is what the unscoped claim denied. The safe default therefore **costs nothing in review coverage**, may cost wall clock on a plan whose author had already scaled it down, and the speedup is an **opt-in a project buys with one attested line**. This is what makes the fail-closed choice free rather than expensive, and it is why no fast-path admission target is stated: the rate is whatever the project's own attestation makes it. **The only observable difference for such a project is C-1107's single degrade line**, which names the remedy. **Named migration consequence, recorded as a deferred owner action rather than a design flaw:** `arcana`'s own `.agents/memory/hex.md` has **no sensitive-path Pointers row** and its `hex.md › Preferences` carries **no `perspectives.security-sensitive-paths` attestation** — verified by reading the whole file. So this ADR buys arcana **nothing** until that row is written. That is the rule working as designed, and open question 1 puts the row in front of the owner. | (no edit — a stated property, argued in § Migration) |

**Range handoff.** The next ADR takes **`C-12xx` / `S-12xx`**. `adr_0013`
(liveness, resources, per-WP sub-orchestration) is the expected claimant.

**UX scenarios.**

| ID | Scenario |
|---|---|
| **S-1101** | A 19-WP plan at tier `high` carrying `- Effective-tier: derived`, in a project whose `hex.md › Pointers` names both conventions. WP-3 is `Size: S`, two files totalling ~40 expected lines, neither matching either convention, neither appearing in another WP's `Expected Files`, `Verify` empty. It resolves **`low`**. One `builder` commits stubs + specification tests, the orchestrator runs the project's test command at that commit and requires failure, and the same builder's next commit is the implementation; `review=minimal` runs `reviewer:quality` + `reviewer:spec` in one concurrent batch at fast-balanced; the 1-round cap allows one fix pass; its actual diff lands at 44 lines, so merge-time re-derivation confirms `low` and the merge pays a scoped check. **Three to four serial round trips against the traced nine.** **The traced WP-1 is deliberately *not* this scenario, and S-1111 says why** — a flagship example whose own numbers fail the ADR's backstop would be worse than no example. |
| **S-1102** | Same plan, WP-6's `Expected Files` names `src/auth/token.rs`, which the project's documented security-sensitive convention matches. `sec` is `true`, so **no reduction**: WP-6 runs the full four-phase pipeline at `high`, deep-reasoning `tester` and `builder:implement`, `review=adversarial`, 3 rounds. The announce line reads `WP6 high (derived: sec)`. |
| **S-1103** | A project with no sensitive-path Pointers row and no attestation — arcana today. `sec` and `hot` read **`true`** for every WP and every WP resolves at the ceiling. One degrade line prints: which flags degraded, which convention was unreadable, that every WP resolves at the ceiling, and the one-line remedy. **For a marked plan whose `Review` cells are absent or `panel`, the run is byte-identical to pre-`adr_0012`.** For a marked plan carrying `self` or `light` cells — the shape wave 0's C-928 tells planners to author — those cells are inert and the run does **more** review than before: safe, visible in the announce block's per-WP lines, and **not** byte-identical (C-1105, C-1107, C-1112, C-1124; walked in S-1107). |
| **S-1104** | A project whose Pointers row names security-sensitive paths and is **silent about hot paths**. `sec` resolves normally; `hot` is unreadable and therefore **`true`**, so every WP still resolves at the ceiling and the half-attestation buys nothing. The degrade line names `hot` specifically, and the remedy is two lines, not one: the row's hot-path half must **point at a file**, and that file must declare the empty set (`none`) — C-1105 rule 2 forbids inlining either the globs or the `none` in the Pointers row itself. Adding `perspectives.security-sensitive-paths: none` would **not** fix it — that key is a security attestation and clears `sec` only (C-1105, C-1107). |
| **S-1105** | WP-4 is `Size: S` with no flag matches, but its `Expected Files` names `src/index/mod.rs`, which WP-11's `Expected Files` also names in a later wave. `hub` is `true`, so WP-4 resolves **`min(high, medium)` = `medium`**: four phases, `review=full`, 3 rounds, `medium`'s model cells. It does **not** resolve to the ceiling — the flooring judgment call (§ Judgment calls 1), reflected in the announce line `WP4 medium (derived: hub)`. |
| **S-1106** | WP-9 is `Size: S`, flag-free, and its author knows it changes a default nothing textually references. They write `Verify: full` with the one-line justification `adr_0010` C-905 already requires. `door` is `true`, so **no reduction** — and the same cell also raises the merge gate and the Review-Fix-Loop exit gate to the project's full documented verification under wave 0's C-924, which explicitly leaves the Implement-phase gate uncoupled. One cell, three effects, all visible in the table (C-1103, C-1113). |
| **S-1107** | WP-2 was authored `Review: self` at plan time; the function derives its effective tier as `high` because `hot` matched. Under the flip the cell names a breadth **below** the derived one, so it is **inert** — honoured as a no-op, not flagged as a defect, and WP-2 runs at `high`, which is **more** review than the authored cell asked for. This is the case C-1124's byte-identity claim is scoped *away* from: safe, but not identical to pre-`adr_0012`. The shipped **upward** guard has nothing left to catch; wave 0's **C-928 downward** guard is not vacuous but **suppressed**, because on a small flag-free WP it would flag this ADR's own escape hatch as a plan defect (C-1112). |
| **S-1108** | WP-7 declares `Size: S` and two files; its actual merge diff is 340 lines across nine files, one of which the security-sensitive convention matches. Merge-time re-derivation runs the same function against `git diff --name-only <base>..<wp-branch>` — the list file-set re-validation already produced — and resolves **`high`**. Review **re-runs at adversarial breadth before the merge**. The collapsed phases and the fast-balanced implementation are **not** re-run and the contract says so; the branch-level backstop covers the rest (C-1116). |
| **S-1109** | A run finishes with six WPs reduced below the ceiling. The handoff names all six with their effective tiers and the inputs that produced them. `/hex-review` is then invoked on the feature branch; its own classifier says `medium` from the diff metrics, the plan's ceiling is `high`, so it runs at **`high`** — `max(classified, ceiling)`. Until that pass completes, the plan **cannot** reach `done` (or `landing`, federated); `/hex-review` remains the sole writer of that state and now carries two preconditions, this one and C-913(f)'s (C-1117, C-1118). |
| **S-1110** | A plan authored before this ADR — no `- Effective-tier:` line — executes on the new bundle. Every reader branches on presence: plan tier drives all four axes, the four-phase list runs, `Review` is lower-only with a missing cell meaning `panel`, wave 0's two-direction guard is live. No version field is read, no migration runs, the plan is never rewritten. A **second** plan carries `- Effective-tier: v2`; hex **refuses** with the shipped `Error:` / `Fix:` pair naming the value read and the values understood — the one hard stop in the ADR, because a marker hex cannot read means a generation it cannot execute (C-1114, C-1123). |
| **S-1111** | **The traced WP-1, run under this ADR, honestly.** Its plan row is `Size: S`, its author's estimate held at plan time, and it resolves **`low`** — the collapse, fast-balanced cells, `review=minimal`, one round. Then its **actual** diff lands at **+78/−3 = 81 lines**, over C-1102's ~50-line `S` bound. C-1116 re-derives it as **`M` ⇒ `medium`** against the real diff and **review re-runs at `full` breadth before the merge**, adding back a round trip the § The arithmetic table does not charge. **The collapsed phases and the fast-balanced implementation are not re-run**, as C-1116 states. So the 43-minute saving is an **upper bound for this particular WP**: the backstop worked, and it cost some of the win back. This is the design behaving correctly on a mis-estimated cell (C-1102, C-1116; § Consequences › Negative). |

## Constitution deviations

`hex/DESIGN.md` is binding. This decision adds **one dated round with four
amendments** — one superseding the 2026-07-20 Review-budget addendum by
pointer, one amending `protocol.md`'s canonical four-phase contract-first TDD
list, one amending `protocol.md`'s presence-checks-not-a-version-field rule,
and one amending the thin-dispatcher / sole-definition rule (`DESIGN.md`
rounds 10 and 13, and `adr_0010` C-916's *"No tier file gains a rule"*),
because `hex-execute`'s three tier files do gain one — **plus one new binding
rule that amends no existing `DESIGN.md` position** (C-1117's mandatory
ceiling-tier branch review, round-15 item 3) — and **explicitly records one
lock it does not amend**. The same four-plus-one split is stated identically
in § Metadata and in the round-15 header below; the three sites agree number
for number by construction.

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **§ Worktrees, the 2026-07-20 perf-pass addendum** — *"a per-WP Review budget (`self \| light \| panel`, **lower-only vs the tier baseline, missing = panel**) — review breadth now scales with WP size, not plan tier alone."* C-1112 flips the direction to raise-only against a derived baseline and makes `self`/`light` inert; C-1101 makes the plan tier a ceiling rather than the baseline. | The addendum's own stated intent is that *"review breadth now scales with WP size, not plan tier alone."* That intent is what this round completes and what the addendum's mechanism could not deliver: a lower-only column cannot stop a budget authored **too high**, which is the traced defect, and it cannot scale phases or model class at all — 43 of the 61 addressable minutes are in exactly those two. The lock's letter is broken by honouring its intent, the same shape round 12 used for the *Plan visualization* lock. | **Keeping the column authored and binding the four axes to it** (option O2 — C-928's downward guard plus the phase collapse, model-class drop and round cap bound to `Review: self`) is rejected in prose in § Considered Options, **not on wall clock, where it ties**: on the corrected reading of `protocol.md`'s `self` clause it removes *more* traced minutes than O1, by removing all WP-level review. It loses by fourteen points on **what gates the reduction** — one authored cell versus three signals the author does not choose — and because an authored cell driving phases, model class, breadth and rounds is O3 under another name. Recorded as a judgment call (§ Judgment calls 8). **A per-WP authored `Tier` column** (O3) was rejected because author error is the traced root cause and because it costs a fifth *Plan visualization* amendment. **A `config.md` key** was rejected on C-223's freeze, the same ground round 12 gave for both budget columns. |
| **`protocol.md` § The Review-Fix Loop — the canonical four-phase contract-first TDD list** (Stub → Specify → Implement → Review-Fix), restated as a hard invariant in `hex-execute/tier-low.md`: *"Keep the contract-first TDD skeleton (Stub → Specify → Implement → Review-Fix) unchanged; only scale the worker count, review breadth, and loop rounds down."* C-1108 collapses the first three into one spawn at effective tier `low`. | That sentence **is** RCA root cause 1: pipeline depth is constant at every tier by explicit design, and it is the single largest addressable segment of the traced run (45 of 186 minutes in three trips that produce no finding). **The phases' properties are preserved, not deleted** — the public surface is still written before the tests, the tests are still written before the implementation, and they must still fail against the stubs. What changes is that one worker performs the sequence in one turn and the ordering is **checked by a third party**: the builder commits stubs + tests as its **first commit on the WP branch**, and **the orchestrator runs the project's test command at that commit and requires failure** (C-1108). A property previously *asserted by construction* (a separate `tester` spawn could not see an implementation that did not exist) becomes *verified against the commit graph*. | **Collapsing only Stub into Specify**, keeping Implement separate, was rejected: it saves one trip of three and keeps the two hand-offs that cost the most. **Keeping all three and cutting review instead** is O2 and is rejected above. **Collapsing against a self-reported red→green transcript** — the first draft's form — was rejected on review and the rejection is recorded rather than quietly patched: the transcript is produced by the same worker whose claim it checks, nothing re-runs it, and it is satisfied by writing the implementation first and stashing it. **That left the deviation with no defence at all** — its whole justification is that the property becomes checkable, and an unfalsifiable artifact is not a check — which under `protocol.md` § Constitution gate is an automatic Request Changes. The committed-stub check is what makes the deviation justifiable, and it costs no round trip: the builder already commits, and merge-time re-validation already shells out to `git`. |
| **`protocol.md` § Worktree work-package mechanics — *"Presence checks, not a version field"*:** *"there is **no schema-version marker**, the presence of the field is the signal … Every reader branches on presence, never on a compared version number."* C-1114's `- Effective-tier:` line **has a value space** (`derived`, v1) and **a hard refusal** on anything else, including a present-but-empty value. | **The rule's own mechanism cannot express this change and the first draft left the conflict in prose instead of naming it.** Every field that rule covers (`Verify`, `Verify-default:`, `Reviewed:`, `## Schedule log`, dotted IDs, `Repo`) carries **one** meaning, so presence is a complete signal. This marker's presence must eventually distinguish *generations* of the derivation — the Go-directive trap `adr0012-risk-flags.md` documents, where a chosen default's meaning needs walking back — and a bare presence check has nowhere to put the second generation. **Presence-plus-refusal is a version marker under a different name and this ADR does not pretend otherwise.** What is genuinely preserved is the rule's *purpose*: **absence is never a version comparison** — it is legacy, permanently, with no migration and no prompt (C-1123). The compared-version prohibition holds for the absent case, which is the case the rule exists to protect. | **A bare presence check with no value** — `- Effective-tier:` alone — was rejected: it is unreadable, and it gives the next generation no carrier but a second Status line, which is worse. **A `Plan-Schema:` field** was rejected outright: C-1123 forbids it and it would version the whole artifact for one behaviour. **Silently accepting an unrecognized value as `derived`** was rejected on `adr0012-risk-flags.md` recommendation 1 — *"an unrecognized or malformed input escalates, it does not default to a known flag"* — and because a marker hex cannot read means a plan written against a generation hex cannot execute. |
| **The thin-dispatcher / sole-definition rule** — `DESIGN.md` round 10's *"a site either links or takes a one-clause qualifier"*, round 13's repair (*"for `protocol.md` to own the sentence and the tier files to link it"*), and `adr_0010` **C-916's *"No tier file gains a rule"*** restating it. **All three `hex-execute` tier files gain a rule, not a qualifier:** `tier-low.md`'s skeleton sentence becomes false and is rewritten, and `tier-medium.md` / `tier-high.md` must condition their phase sections on the **WP's** effective tier rather than on the file they live in — so a tier file's phase list stops being a property of the file. Promoted here from a "considered and not deviated" note, where the first draft filed it: a rule is a deviation, whatever heading it sits under. | **The phase list is exactly what this round exists to scale**, and it is the one thing a per-tier phase file is *for*. A dispatcher that cannot be conditioned cannot express "this WP runs three phases and that one runs four", so the rule cannot land anywhere else without duplicating the function into every tier file — the ten-file diff round 13 named. **The intent is upheld while the letter is broken:** the function is defined **once**, in `protocol.md`; the tier files carry only the conditioning, never a second copy of the derivation. | **Leaving the tier files untouched** and letting `protocol.md`'s phase list carry the condition alone was rejected: the tier files each state their own phase list unconditionally today, so an unamended `tier-low.md` ships a sentence the round makes false (§ Validation greps for exactly that sentence). **Collapsing at every tier**, which would keep each file's list unconditional, is not this design — the collapse is scoped to effective `low` precisely so `medium` and `high` are unchanged in every byte. **A fifth tier file** for the collapsed pipeline was rejected: it is a new artifact for a value already derivable, and `DESIGN.md`'s tier files are indexed by *plan* tier, which is exactly the coupling this ADR removes. |

**Considered and explicitly not deviated: the *Plan visualization* lock is NOT
amended.** Its enumeration of the WP table's canonical column set stands
unchanged, because this ADR adds no column: every input is a cell that already
exists or a pointer that already exists. That enumeration has been amended by
explicit act four times and a fifth was avoidable, so it was avoided —
recorded here rather than left as an absence, because four prior amendments
make "no amendment" the surprising outcome. The one new artifact field is a
**Status-block line**, and `adr_0010`'s `Reviewed:` line is the standing
precedent that a Status line does not touch the column lock (round 12's
`Verify-default:` rode amendment 3 only because it defaulted the column that
amendment was adding).

### DESIGN.md amendment round — 2026-09-05, round 15

**Round-number collision, recorded rather than resolved silently.** The shipped
`DESIGN.md` ends at round 13, which makes 14 the next free number — but
[`plan_wave0_quick_wins`](../plans/plan_wave0_quick_wins.md) C-936, at
`State: executing` (`Updated: 2026-09-05`), **already claims round 14** for its
own record item. **Round 14 is claimed *and in flight*, which is a stronger
ground than the first draft's "approved but unexecuted":** the number is being
spent by a run that has started, so taking 14 here would collide with a write
already under way rather than with a reservation. This ADR also supersedes two
of that plan's contracts (C-928's guard, C-930's histogram bucket key), so it
lands **after** wave 0 by dependency. It takes **round 15**. If wave 0 is
abandoned mid-execution or lands after this ADR, the implementing plan
renumbers to 14 — **the number is a sequence position, not an identity, and
this round's amendment content is unaffected either way.**

Proposed text, to be appended to `hex/DESIGN.md` (implementation is downstream;
this ADR does not edit the file):

> ## Per-WP effective-tier round (2026-09-05, round 15)
>
> `adr_0012` (the per-WP effective tier — plan tier becomes a ceiling, each
> work package derives its own) makes **four amendments — items 1, 2, 4 and
> 5 below**: **one position in § Worktrees**, **one canonical phase list in
> `protocol.md`**, **one presence-checks-not-a-version-field rule in
> `protocol.md`**, and **the thin-dispatcher / sole-definition rule as it
> applies to `hex-execute`'s three tier files** (`adr_0010` C-916's *"No tier
> file gains a rule"*). It **adds one new binding rule — item 3 — which
> amends no existing `DESIGN.md` position**: the mandatory ceiling-tier
> branch review as a precondition on the terminal review state. And it
> explicitly **declines to amend a fifth position**, the *Plan
> visualization* lock. The § Worktrees amendment supersedes **by pointer**: the
> 2026-07-20 perf-pass addendum's bytes are left as written and the
> `### Worktrees` region's existing erratum pointer gains one clause, per
> round 11's convention and following the precedent that **round 12 already
> superseded that same addendum by pointer** when it retro-claimed the
> Review budget under `adr_0010` C-905. Full adjudication and the scored
> five-option comparison: `adr_0012` § Considered Options.
>
> 1. **The per-WP Review budget's direction flips, and the plan tier becomes
>    a ceiling rather than a baseline.** The 2026-07-20 addendum above added
>    *"a per-WP Review budget (`self | light | panel`, **lower-only vs the
>    tier baseline, missing = panel**) — review breadth now scales with WP
>    size, not plan tier alone."* Its stated intent stands and is what this
>    amendment completes; its mechanism does not. **Each work package now
>    resolves an *effective tier* — derived from its declared size class, a
>    closed set of four risk flags, and nothing else; never authored, never
>    above the plan's tier — and the effective tier, not the plan tier,
>    drives four axes: which phases run, which `models.md` cell each
>    WP-scoped spawn reads, review breadth, and the loop-round cap.** The
>    `Review` column survives with its **direction flipped**: `adr_0010`
>    C-905's invariant — *a column whose baseline is the maximum may only
>    lower; a column whose baseline is the minimum may only raise* — is
>    **preserved by the flip, not broken by it**, because the derivation
>    moved `Review`'s baseline off the maximum. `Review` is now raise-only
>    against the derived breadth, capped at the ceiling; `panel` raises the
>    WP to the ceiling and is the one explicit escape hatch; `self` and
>    `light` are inert in a plan carrying the generation marker. **A risk
>    flag whose source is absent, unreadable, or malformed reads `true`,
>    never `false`** — fail-closed, on the AWS-IAM-implicit-deny /
>    SELinux-enforcing precedent, and against GitHub CODEOWNERS' silent
>    fail-open, which is the exact failure this forecloses. **`sec`
>    additionally reads hex's own shipped triggers** — the `classify.md`
>    structural markers for auth/crypto/signing paths, dependency manifests
>    and CI workflows — as an independent disjunct: **a project may widen
>    hex's security sensitivity, never subtract from it**, because at
>    effective `low` the review set is `minimal` and the conditional
>    `reviewer:security` cannot spawn at all. **The same `hex.md › Pointers`
>    row feeds two consumers, and this round records the consequence rather
>    than leaving it to be discovered: an attestation of an empty
>    security-sensitive set buys tier reduction *and* silently disarms
>    `adr_0010` C-903's high-risk checkpoint trigger.** The two absence
>    semantics for that one row are reconciled by **residual risk, not by
>    direction** — three independent backstops survive C-903's vacuous
>    clause, one survives a fail-open reduction here. The consequence the
>    round's compatibility rests on: **a project that has attested no
>    security-sensitive or hot-path convention runs at the ceiling on every
>    WP**, byte-identically to before this round **for plans whose `Review`
>    cells are absent or `panel`** — where such a plan carries `self` or
>    `light`, those cells go inert and it runs *more* review, never less.
>    So the safe default costs nothing in coverage and the speedup is an
>    opt-in bought with one attested line. Rejected alternative:
>    **keeping the column authored and binding the four axes to it** — the
>    downward guard (`panel` on a small flag-free WP declared a plan defect,
>    `plan_wave0_quick_wins` C-928, which ships regardless) plus the phase
>    collapse, model-class drop and round cap bound to `Review: self`. It
>    **ties on wall clock** — both options need the phase collapse, which is
>    the dominant lever — and loses by **fourteen points on a 125-point
>    scale**, a margin resting entirely on two criteria: an authored cell
>    that drives phases, model class, breadth and rounds **is a per-WP
>    `Tier` column with a misleading header**, and binding new meaning to a
>    cell already present in approved plans either reinterprets them
>    silently or needs the same generation marker. **The choice is a
>    judgment call and is recorded as one** (`adr_0012` § Judgment calls 8).
>    Also rejected:
>    **a per-WP authored `Tier` column** — author error is the traced root
>    cause, and a fifth *Plan visualization* amendment for a value derivable
>    from existing cells is a cost with no return. **The sole definition site
>    is `protocol.md` § Parallel-by-default decomposition › The effective
>    tier**; `models.md`, `hex-execute/overlays.md`, `hex-review/classify.md`
>    and the plan template link or take a one-clause qualifier, and **every
>    site whose sentence stays true is untouched**. **The three
>    `hex-execute` tier files are the stated exception, and this round files
>    it as its own amendment rather than as a footnote here — item 5.**
>
> 2. **The canonical four-phase contract-first TDD list collapses to one
>    spawn at effective tier `low`, against a check the builder cannot
>    write.** `protocol.md` § The Review-Fix Loop's phases 1–3 (Stub,
>    Specify, Implement) become a single `builder` spawn that **commits the
>    stubs and the specification tests as its first commit on the WP branch,
>    before the implementation commit**, and **the orchestrator runs the
>    project's test command at that commit and requires failure**. A
>    self-reported red→green transcript was the first draft's form and was
>    **rejected on review**: it is produced by the same worker whose claim it
>    checks, nothing re-runs it, and it is satisfied by writing the
>    implementation first and stashing it — leaving the deviation with no
>    defence, since its whole justification is that the property becomes
>    checkable. The committed-stub form costs no round trip (the builder
>    already commits; merge-time re-validation already shells out to `git`).
>    `hex-execute/tier-low.md`'s *"Keep the contract-first TDD skeleton
>    … unchanged"* becomes false and is amended. This is the round's largest
>    wall-clock lever: three serial round trips become one, and pipeline
>    depth stops being constant at every tier for the first time since round
>    4. **The phases' properties are preserved and one of them is
>    strengthened:** the surface is still written before the tests and the
>    tests before the implementation, and *"they MUST fail against the
>    stubs"* becomes **demonstrated by output** rather than assured by the
>    fact that a separate `tester` could not see an implementation that did
>    not exist. **What is given up is stated rather than argued away:
>    author≠verifier at the work-package level.** The check recovers the
>    temporal property, not independence; the backstops are the
>    `review=minimal` batch's spec reviewer and the branch-level pass below.
>    The collapse exists **only** at effective `low`. **The single spawn
>    resolves all three source cells and reads the highest** — the shipped
>    matrix has `builder:stub`, `builder:implement` and `tester` all
>    `fast-balanced` at `low`, but `models.md` Rule 2 puts an instantiated
>    `hex.md` matrix **above** the shipped default, so a project pinning any
>    one of the three makes them disagree; taking the highest means
>    collapsing never silently revokes a pin, and the raise is disclosed at
>    the gate. No matrix row is added. Rejected alternative: **collapsing
>    Stub into Specify only** — one trip of three, keeping the costliest
>    hand-offs. Also rejected: **collapsing against the builder's own
>    transcript**, above.
>
> 3. **A new binding rule, not an amendment — the collapsed path's backstop
>    is made mechanical, reusing the one writer that already exists.** This
>    item **amends no existing `DESIGN.md` position**; it adds one. It is
>    numbered here with the amendments because it belongs to the same round,
>    and it is classed separately because calling a new rule an amendment
>    would leave the round's count wrong at three of its four statement
>    sites. `protocol.md` already declares the
>    branch-level `/hex-review` mandatory for any plan containing a `self`
>    WP — as prose enforced by nothing. This round binds it: **a plan
>    containing any WP whose effective tier fell below its ceiling does not
>    reach its terminal review state (`done`, or `landing` when a `Repo`
>    column is present) until a branch-level `/hex-review` has run at no
>    less than the plan's ceiling tier**, the ceiling acting as a floor on
>    the review's own classified tier and never as a cap. `/hex-review` is
>    already the sole writer of that state (`adr_0005` C-410) and already
>    carries one precondition of this shape (`adr_0010` C-913(f)), so this
>    is a second precondition on the same write, not a second writer. **The
>    ceiling floors an explicit `--tier` flag too** — `overlays.md`
>    § Precedence would otherwise let a user flag lower it and remove the
>    backstop with one argument — and the ceiling `T` is read from the
>    plan's Status-block `Tier:`, never from `/hex-execute`'s run tier.
>    This borrows the **discipline** every surveyed system pairs with a fast
>    path (Zuul's gate re-testing regardless of the check pipeline,
>    Gerrit's `Verified` submit requirement, CI smoke as pre-filter and
>    never substitute) and **not their enforcement, which hex does not
>    have**: hex never pushes outside `/hex-finalize`, whose gate is a human
>    approval, so what this precondition blocks is a plan reaching `done` /
>    `landing` — a markdown Status field, not a merge. Recorded plainly
>    rather than left as an implied equivalence. The **runtime** half rides
>    `adr_0010`'s existing merge-time budget re-validation, which becomes an
>    effective-tier re-derivation against the actual diff — **including
>    `hub`, re-derived from the actual changed-file list**, since a declared
>    file set is repaired by widening it and therefore does not bound the
>    actual one.
>
> 4. **The presence-checks-not-a-version-field rule takes one named
>    exception.** `protocol.md` § Worktree work-package mechanics states
>    *"there is no schema-version marker, the presence of the field is the
>    signal"*, and it holds for every field it covers, each of which carries
>    one meaning. **`- Effective-tier:` does not: it has a value space
>    (`derived` in v1) and a hard refusal on anything else**, including a
>    present-but-empty value, because a marker whose value hex cannot read
>    means a plan written against a generation hex cannot execute. That is a
>    version marker under another name and this round says so rather than
>    burying it in prose. **What survives verbatim is the half the rule
>    exists for: absence is never a version comparison** — an absent line is
>    legacy semantics, permanently, with no prompt, no error, no migration
>    and no rewrite. The value is a **literal, not a number to compare**, and
>    a future generation takes a new literal rather than redefining
>    `derived` — Go's own directive walk-back is the cited reason. The
>    marker is read line-initial, above the first `##`, to the first field
>    separator, trimmed and matched exactly, on `hex-architect/SKILL.md`'s
>    shipped `State:` discipline; **a marker on a plan carrying no `Verify`
>    column is refused**, because such a plan's blank `Review` cells would
>    otherwise flip in bulk from `panel` to derived — the one unsafe
>    direction of the flip.
>
> 5. **The thin-dispatcher / sole-definition rule takes one scoped
>    amendment: `hex-execute`'s three tier files gain a rule, not a
>    qualifier.** Round 10's *"a site either links or takes a one-clause
>    qualifier"*, round 13's repair (*"for `protocol.md` to own the sentence
>    and the tier files to link it"*), and `adr_0010` **C-916's *"No tier
>    file gains a rule"*** all say the same thing, and this round breaks it
>    in exactly one place. `tier-low.md`'s *"Keep the contract-first TDD
>    skeleton … unchanged"* becomes false and is rewritten (amendment 2);
>    `tier-medium.md` and `tier-high.md` must **condition their phase
>    sections on the *WP's* effective tier** rather than on the file they
>    live in — **a behavioural rule, not a qualifier**, because a tier
>    file's phase list stops being a property of the file. **It is filed as
>    an amendment rather than as a note under "considered and not deviated",
>    where the first draft put it: a rule is a deviation whatever heading it
>    sits under.** **The intent is upheld while the letter is broken** — the
>    function is defined **once**, in `protocol.md`, and the tier files
>    carry only the conditioning, never a second copy. It is the one place
>    this round spends dispatcher thinness, and it is spent because the
>    phase list is exactly what the round exists to scale. `adr_0010`
>    C-916's sentence takes an erratum (`adr_0012` § Interaction, erratum
>    row 9).
>
> **Considered and not deviated** (unchanged by this round): the
> ***Plan visualization* lock is explicitly NOT amended** — this round adds
> **no column**, every input being a cell or pointer that already exists,
> and the one new artifact field is a Status-block line, for which
> `adr_0010`'s `Reviewed:` is the standing precedent. That enumeration has
> been amended by explicit act four times and a fifth was avoidable. The
> **single approval gate** — count and position untouched; the derivation
> is computed before the gate and disclosed *at* it, and asks nothing. The
> **depth-1 coordinator invariant** (`adr_0010` C-914) — untouched and
> reaffirmed: no recursion ≥ 2, no new orchestrator role, and **nothing is
> persisted at all**, so the flat-state requirement is met by construction
> rather than by discipline. **Capability classes** — upheld: `models.md`
> gains one clause about *which tier column a cell is read from* and no
> literal model name appears in any changed shipped file. **`hex never
> pushes` / `hex never commits` outside execution** — untouched; round 10's
> scoping stands. **The two-layer knowledge model** — upheld and load-bearing:
> the security-sensitive / hot-path convention is a **Layer-1 project fact**
> reached through a `hex.md › Pointers` row, and hex records **where** it
> lives, never what it says — **C-1105 rule 2 makes that structural: the row
> carries a location, never an inline glob set and never the literal
> `none`, so the attestation itself lives in project truth and the Pointers
> row stays the cache `memory.md` classes "never authoritative"**; the
> fail-closed degrade is what keeps hex from inventing Layer-1 knowledge it
> does not have. **`adr_0005`'s fold path** —
> untouched; `hex-review` still writes only the Status block, the
> convergence check, and — on an approved converged fold — the spec file and
> receipt, and C-410's exclusive ownership of the terminal review state
> gains one precondition rather than a second writer. **`adr_0004`'s
> federation contracts** — unchanged: `hub` keys on `(Repo, path)` for
> C-316's reason, and the per-repo verification rule and global merge
> serialization are untouched. **Thin dispatchers + per-tier phase files** —
> upheld **outside `hex-execute`'s tier files**: canonical text lands once in
> `protocol.md` and every consumer takes a link or a one-clause qualifier —
> the repair round 13 named when it recorded that nine restatements turned a
> one-line contract change into a ten-file diff. **The three `hex-execute`
> tier files are *not* in this list: they gain a rule, and that is
> amendment 5 above, not a non-deviation.**
> **`config.md` gains no key** and its frozen six-key vocabulary is not
> reopened.

### Interaction with `adr_0010` — what survives, what is derived, what takes an erratum

**Untouched, in every byte.** The `Verify` column's raise-only direction, its
`scoped` floor and its merge-gate meaning (C-905's `Verify` half); the
`Verify-default:` Status line; the three full-verification policy triggers and
the two override paths (C-901); the scoped check and its degrades (C-902); the
checkpoint cadence and the high-risk predicate (C-903); the bounded bisection
(C-904); the selective-test convention (C-906); the `Reviewed:` anchor, its
validation predicate, delta round scope and the mandatory converged pass
(C-907–C-909); `/hex-review`'s baseline resolution (C-910); the
diminishing-returns stop (C-911); the schedule log (C-912); the failure cascade
and derived strandedness (C-913); depth-1 and the flat state surface (C-914);
presence-check compatibility (C-915); `hex-init`'s audit item and its two
Pointers rows (C-917 — this ADR adds a *reader* of the sensitive-path row
C-917 created and changes nothing about the row's own contract); the
zero-config-key posture (C-918); the bundle-wiring and release shape (C-919 —
this ADR's own release is § Migration class 9 and follows the same form).
**The final gate remains mandatory, un-lowerable, and outside every budget** —
no effective tier reaches it.

**The one `adr_0010` contract that is *not* untouched, and the first draft's
enumeration omitted it entirely: C-916.** Its *"No tier file gains a rule"* is
exactly what § Migration edit-site class 4 breaks — `tier-medium.md` and
`tier-high.md` condition their phase sections on a per-WP value. It takes
**erratum row 9**, and it is the fourth constitution deviation
(§ Constitution deviations, round-15 amendment 5). The § Links enumeration
lists the same set, contract for contract.

**Derived rather than authored.** `adr_0010`'s per-WP `Review` assignment
heuristic — *"docs-only or tiny low-risk work (~≤50 expected lines, no
security-sensitive or hot-path files) → `self`; a single-area moderate change →
`light`; large, cross-area, security- or hot-path-touching work → `panel`"* —
stops being an **authoring instruction** and becomes the **derivation's
heuristic**, in the same three-band shape with the same threshold. The one
substantive change is that it now dual-gates: `adr0012-risk-scoring.md` finds
the ~50-line figure defensible (conservatively inside the Cisco 200–400 and
Google 100–200 bands) but is unambiguous that *"no system in this research
trusts size alone to lower effort"* — so size clears the gate only when all
four flags are clear, which the prose heuristic implied and no mechanism
enforced.

**Erratum table**, in `adr_0010`'s own style.

| # | `adr_0010` site | What it says | What `adr_0012` makes true |
|---|---|---|---|
| 1 | C-905, the `Review` instance | *"it is lower-only against the tier's panel baseline; a missing column or cell means `panel`"* | In a plan carrying `- Effective-tier: derived`, `Review` is **raise-only against the derived breadth, capped at the ceiling**; a missing column or cell means **the derived breadth**, and `panel` raises the WP to the ceiling. **Unchanged in every legacy plan.** |
| 2 | C-905, the direction invariant | *"a column whose baseline is the maximum may only lower; a column whose baseline is the minimum may only raise"* | **The invariant itself stays true and is not amended.** What moved is `Review`'s *baseline*: it is no longer the tier's panel but the WP's derived breadth, so the invariant's own logic now requires raise-only. The erratum is against the invariant's **application** to `Review`, not against the invariant. |
| 3 | C-905, the `Verify` instance | *"It sets the WP's **merge gate** … **and nothing else**"* | Already widened by `plan_wave0_quick_wins` C-924 to **two gates (the merge gate and the Review-Fix-Loop exit gate)** — C-924 states in its own words that *"the Implement-phase gate is **not** coupled to the cell (D6, C-925)"*. `adr_0012` adds a **third consumer** — the `door` flag — on top of C-924's text and **does not re-claim that erratum**. |
| 4 | **§ The Review-Fix Loop**, the per-WP-review-budget bullet — *retargeted; the first draft filed this against § Parallel-by-default decomposition, where the budget's **assignment** heuristic lives, not its **consumption** rule* | *"The budget only **lowers** breadth below the tier baseline, never raises it. A missing column or cell means `panel` — pre-budget plans run unchanged."* | Both sentences invert in a derived-generation plan (erratum 1). The final clause — *pre-budget plans run unchanged* — is **strengthened rather than changed**: it now covers pre-`adr_0012` plans too, permanently (C-1123). The `self` clause four lines above it — *"**no reviewer spawns in this loop**, and the WP skips the Verify-Architecture reviewer"* — is **not** amended: it stays exactly true in legacy plans and is inert in derived-generation ones. |
| 5 | § Parallel-by-default decomposition, the merge-time re-validation | *"a WP whose actual diff outgrew its budget class … escalates to the next budget and its review re-runs at that breadth before the merge"* | Becomes an **effective-tier re-derivation** against the actual diff (C-1116), with the stated limit that only review can be restored — the collapsed phases and the model class are already spent. |
| 6 | C-903, high-risk clause 1 | *"until that row exists clause 1 is vacuous"* — the `hex.md › Pointers` sensitive-path row read **fail-open** | The **same row** is read **fail-closed** by `adr_0012` (C-1105). Not a contradiction and not an erratum against C-903's text, which stays true — but **not for the reason the first draft gave.** *"A fail-safe default is direction-relative"* is withdrawn: both consumers move effort **down** on an absent row, so a direction rule condemns C-903 rather than reconciling it. **The reconciliation is residual risk**: three independent backstops survive C-903's vacuous clause (counter, level-clear, final gate); **one** survives a fail-open reduction here (C-1117's branch review, after the phases are spent). **And the consequence both sites now carry: clearing this row disarms *both* consumers** — an attestation bought for tier reduction also removes C-903's high-risk checkpoint trigger, a pre-existing control unrelated to this ADR (C-1106, § Judgment calls 3). |
| 7 | C-907, Status-block placement | *"Placement: immediately after `Next:` and **before** the `Repos:` ledger"* | Still true of `adr_0010`'s own two lines. `- Effective-tier:` sits **immediately after `Tier:`**, one line earlier, on the same ordering ground (a fixed single line ahead of the unbounded ledger) because it qualifies `Tier:` itself. **No erratum owed**; recorded so the two placements are not read as a conflict. |
| 8 | C-907's own erratum, the 20-line Status invariant | records that the template's *"must stay within the first 20 lines"* invariant *"is already unmet before this ADR adds anything"* | One line worse. Recorded, not fixed — repairing it means restructuring the template's comment block, which has no relationship to this decision. |
| 9 | **C-916, the sole-definition-sites rule** | *"**No tier file gains a rule**; per `DESIGN.md` round 10, a site either links or takes a one-clause qualifier"* | **False for `hex-execute`'s three tier files under this ADR, and stated as an erratum rather than left in the "untouched" list where the first draft implied it.** `tier-low.md`'s skeleton sentence is rewritten (C-1108) and `tier-medium.md` / `tier-high.md` **condition their phase sections on the WP's effective tier** — a behavioural rule, not a qualifier, because a tier file's phase list stops being a property of the file. **C-916's sentence stays true of every other site and of every `hex-plan` and `hex-review` tier file**, and the sole-definition half is upheld: the function is defined once in `protocol.md`. Carried as constitution deviation 4 / round-15 amendment 5 and as § Migration edit-site class 4. |

**Interaction with `plan_wave0_quick_wins`** (`State: executing` as of
2026-09-05 — claimed and in flight, which is why this ADR takes round 15):
C-928's **two-direction budget guard is affected asymmetrically, and the first
draft's "both become vacuous" was wrong on one half.** Its **upward** half
(`self` / `light` on a security-, hot-path-, large or cross-area WP is a plan
defect) is genuinely vacuous in a derived-generation plan — those cells are
inert. Its **downward** half is **contradicted, not vacuous**: it declares
*"`panel` on a size **S or M**, **single-area** WP whose expected file set
contains **no** security-sensitive or hot-path file"* a plan defect, which is
**exactly** C-1112's sanctioned escape hatch. It is therefore **suppressed in
derived-generation plans**, stated at C-928's own definition site
(`protocol.md` § Parallel-by-default decomposition) and inherited by the three
`hex-plan` tier files that link it under **C-929** rather than restating it.
Both halves stay live and unchanged in legacy plans. C-930's **budget
histogram has its bucket key replaced** by the effective tier (C-1119), its
grammar — **including its ordering rule, which the first draft misquoted and
then wrongly deviated from** — adopted verbatim, and its line kept for legacy
plans. C-924's widened `Verify` reach **compounds** the `door` flag's cost
(§ Judgment calls 2). C-936's claim on `DESIGN.md` round 14 is the collision
recorded above.

**Seam with `adr_0013`, stated by contract id rather than by name.**
`adr_0012` decides **which phases a work package runs and at what model class
and review breadth**; `adr_0013` decides **how the workers running them are
supervised, resourced and sub-orchestrated**. Three gaps sit on the seam and
are recorded here rather than resolved: **(1)** `C-1219`'s coordinator *kind*
decides whether C-1109's floor applies at all — Q2 decomposing raises it, Q1
pipeline does not — and `C-1219`'s rider *"a coordinator WP is by definition
`panel`"* would otherwise raise every coordinator-owned WP to the ceiling
through C-1112; `adr_0013` retargets that rider, and this ADR's collapse
depends on the retargeting landing. **(2)** `C-1220`(a) inlines a one-WP ready
set and reads itself as covering a collapsed pipeline, so C-1108 and
`C-1220`(a) read each other and neither states which resolves first.
**(3)** `C-1206`/`C-1207`'s liveness ladder removes the dead-worker trip
§ The arithmetic attributes to `adr_0013`, and no single document owns the
composed figure.

## Migration / rollout plan

**Every change is additive at the artifact level and no migration step
exists.** There is no plan rewriter, no `--upgrade` flag, and no version
comparison anywhere in the design (C-1123).

**What an existing plan does on the new bundle.** It executes, unchanged.
Absent `- Effective-tier:` ⇒ pre-`adr_0012` semantics byte-for-byte: plan tier
drives all four axes, the four-phase list runs at every tier, `Review` is
lower-only with a missing cell meaning `panel`, wave 0's two-direction guard is
live. **Never a prompt, never an error, and the plan is never rewritten to add
the line.**

**What a project with no attested convention does.** Every flag `true`, every
WP at the ceiling, plus one announced degrade line naming which convention was
unreadable and its one-line remedy (C-1107, C-1124). **Byte-identical to
today — for a marked plan whose `Review` cells are absent or `panel`.** A
marked plan carrying `self` or `light` cells runs **more** review than today,
because C-1112 makes those cells inert and the ceiling supplies the full panel.
That is the safe direction and it is announced per WP, but it is **not**
identity, and it is the common shape rather than a corner: wave 0's C-928 tells
planners to author exactly those cells. This is the fail-closed rule working as
designed, not a failure state.

**`arcana` itself buys nothing until one row is written.** Its
`.agents/memory/hex.md` § Pointers carries rows for verification, plan/ADR
conventions, the spec home, product knowledge, key rules, worktrees,
discussions and the constitution — and **no sensitive-path row**; its
§ Preferences carries the instantiated model matrix, the adversary skill and
limits — and **no `perspectives.security-sensitive-paths` attestation**. So on
the day this ships, every arcana WP resolves at the ceiling. **Named migration
step, and a deferred owner action**: write the Pointers row **and the
convention file it points at** — C-1105 rule 2 makes the row a location and
the file the value (open question 1).
It is a one-line edit to a `/hex-init`-owned section, offered with consent, and
it is deliberately **not** bundled into the implementing plan —
`plan_wave0_quick_wins` already scopes `.agents/memory/hex.md` out for the same
reason.

**Edit-site classes, in dependency order.** File-disjoint except where noted,
which is what makes them decomposable.

1. **`protocol.md` canonical text** — § Parallel-by-default decomposition (the
   new *The effective tier* subsection carrying the function, the flags, the
   size classes, the degrade and attestation rules, the marker semantics, the
   histogram grammar; the amended review-budget and re-validation bullets),
   § The Review-Fix Loop (the collapsed phase list, the flipped budget bullet,
   the mandatory-review clause, the loop-cap's third term), § The meta-plan
   approval gate (the fifth source, **one** new config-disclosure trigger
   (C-1122) and **one new trigger class** — the risk-flag degrade line
   (C-1107), which is not a `Preferences` config block and therefore does
   not join that enumeration),
   § Worktree work-package mechanics (one clause beside C-915's no-marker
   sentences), § Checkpoints (one cross-reference clause). **One file, five
   sections; it is the critical path and everything else links to it.** *Must
   not break:* the four-phase list stays canonical at effective `medium` and
   `high`; the final gate's un-lowerable status; C-903's own text.
2. **Plan template** — the `- Effective-tier: derived` Status line with its
   comment, the Parallelization table comment's `Size` definition and flipped
   `Review` description. *Must not break:* the table header row is **byte-
   unchanged** — that is the mechanical proof no column was added.
3. **`models.md`** — one clause under the matrix and one in Rule 2, naming
   which tier column a WP-scoped spawn reads. *Must not break:* Rules 1, 3, 4
   and 5, and the no-literal-model-names constraint.
4. **`hex-execute`** — `overlays.md`'s `review` and `loop-rounds` axis
   sections take one clause each, **its `adversary` axis section takes one
   clause pinning that axis to the plan tier** (C-1110), and **the sentence
   outside every axis heading at `overlays.md` § *Both axes are ceilings*** —
   *"a WP's `Review` budget in the plan table lowers them per WP — `self` and
   `light` also force a 1-round loop for that WP regardless of this axis"* —
   **is named explicitly here, because C-1112 makes it false and it sits
   outside both axis headings, so the two one-clause qualifiers do not reach
   it.** `tier-low.md` takes the collapsed-phase amendment (its *"Keep
   the contract-first TDD skeleton … unchanged"* sentence becomes false);
   `tier-medium.md` and `tier-high.md` **condition their phase sections on the
   WP's effective tier**; `SKILL.md`'s announce step gains the effective-tier
   line and histogram, its handoff gains the reduced-WP lines, **its
   § Work packages table-parse default — *"A missing `Review` column or cell
   defaults to **`panel`** at table-parse time"* — gains the
   derived-generation exception**, because C-1112 and erratum 1 make a missing
   cell mean *the derived breadth* in a marked plan, and a parse-time default
   that contradicts the consumption rule is the drift the sole-definition rule
   exists to prevent; and **its phase table's `Stub` / `Specify` / `Implement`
   rows — which today declare `1 per work package` — gain the effective-`low`
   exception**, because that declaration becomes false under C-1108 and a
   table saying `1 per work package` beside a collapsed spawn is a shipped
   contradiction. *Correction to the first draft's characterization, which
   claimed the tier files gain "no rule, only links and qualifiers":*
   **`tier-medium.md` and `tier-high.md` do gain a rule.** Conditioning a
   phase section on a per-WP value means the file no longer states its own
   phase list unconditionally — that is a behavioural rule, not a qualifier,
   and pretending otherwise would understate the diff the implementing plan
   has to write. It is the one place this ADR spends dispatcher thinness;
   § Constitution deviations carries it as deviation 4 and § Interaction as
   erratum row 9 against `adr_0010` C-916. **C-1117's
   ceiling-floors-`--tier` clause is *not* here** — it is about
   `/hex-review`'s own `--tier` flag, so it lands in class 6.
5. **`hex-plan`** — `SKILL.md` writes the marker on every new plan and prints
   the histogram at the Decompose gate, replacing C-930's bucket key.
6. **`hex-review`** — `classify.md` gains the **cross-reference** to C-1102 and
   the named divergence (its `low` row is `≤100` lines against C-1102's `S` at
   `~≤50`; the two are not one table and the first draft said they were);
   **`overlays.md` § Precedence takes C-1117's ceiling-floors-`--tier`
   clause** — that section's *"User-supplied flags always override
   classifier-inferred overlays"* would otherwise let `/hex-review low` on a
   `high`-ceiling plan evaporate the backstop, and the clause belongs beside
   the rule it qualifies, not in `hex-execute` where the first draft filed it;
   `SKILL.md`'s verdict write gains the C-1117 precondition qualifier, beside
   C-913(f)'s, plus the ceiling-floors-`--tier` announce line; `archive.md`
   takes the matching qualifier.
7. **`hex-core/references/memory.md`** — **missing from the first draft's edit
   list entirely, and C-1105 cannot resolve without it.** Its § Pointers entry
   ships **one combined line** — *"where the project's security-sensitive /
   hot-path convention is documented"* — which the degrade rule must read as
   **two independent halves**; that entry gains one clause saying so, and a
   cross-reference to C-1105's read rule and to the § Staleness interaction
   (re-detect first, fail closed if re-detection finds nothing). *Must not
   break:* § Staleness's repair-and-proceed rule is **not** amended — C-1105
   sequences after it rather than replacing it.
8. **`DESIGN.md`** — round 15 appended; the `### Worktrees` region's existing
   erratum pointer gains one clause, **bytes otherwise unchanged**. *Must not
   break:* the *Plan visualization* lock is not touched at all — that is a
   checkable invariant, not a preference.
9. **Release** — `publish.toml` minor bump, `CHANGELOG.md` with the behaviour
   change under `### Changed` and the marker under `### Added`, `README.md` one
   line stating that plan tier is a ceiling and each WP derives its own.

**Ordering constraint against wave 0.** This ADR's implementing plan **depends
on `plan_wave0_quick_wins` having landed**, because C-1113 builds on C-924's
widened `Verify` text and C-1119 adopts C-930's histogram grammar. Executing
them in the other order is possible but means writing two contracts against
text that does not exist yet.

**Rollback, at two grains.** *The bundle:* every change is a markdown edit on a
feature branch, reverted by discarding it; a plan authored with the marker
still parses under the old bundle, which ignores unknown Status lines. **No
state is written that outlives a plan** — there is nothing to un-migrate,
because there is nothing stored (C-1121). *One plan, under the new bundle:* the
escape is **one line** — delete `- Effective-tier: derived` and the plan runs
pre-`adr_0012` semantics immediately. That is a strictly cheaper rollback than
`adr_0010`'s, which needed a `Verify-default:` line to avoid editing N cells.

***The third grain, which the first draft omitted, and it is the only
irreversible one: the code.*** Both paragraphs above roll back *configuration*.
Neither touches the artifact that actually accumulates — **every work package
already merged through a collapsed pipeline at a reduced model class and a
`minimal` review breadth.** A bundle revert changes what future runs do; it
re-reviews nothing. There is no marker on those commits, no record of which
WPs reduced beyond the transient handoff block (C-1121 persists nothing by
design), and C-1116 cannot help because it ran at the time and already made its
call. **So the honest cost of deciding in three months that this ADR was wrong
is not `git revert` — it is a ceiling-tier re-review of every WP that reduced
in the interim**, reconstructed from `Size` cells and the function, because
nothing recorded the answer. **That is the price of driver 7's no-new-state
rule, charged here rather than left implicit**, and it is the strongest
argument anyone will have for the persisted-derivation record § Departures 1
declined. It is also why C-1117's branch review is mandatory rather than
recommended: **it is the only pass that touches the merged code before it
leaves the branch**, and it is the difference between a three-month rollback
costing a re-review and costing nothing at all.

**One class-4 note for the implementing plan:** this repo dogfoods its own
bundle, so the installed copies under `.claude/skills/hex-*` go stale the moment
these edits land. Refreshing them is a **separate chore commit** after the
merge, not part of any WP — the same rule `adr_0010`'s plan carried.

## Validation

**Static, before execution — mechanically checkable.**

- `grim build <skill-dir>` for every changed skill; `task publish -- --dry-run`
  for the full sweep.
- **Contract coverage:** every `C-11xx` maps to at least one WP and one test in
  the implementing plan; every `S-11xx` maps to at least one WP. **C-1115,
  C-1121 and C-1124 are exempt from both halves** — all three carry a Home of
  *(no edit)*: two stated non-changes and one stated property, whose whole
  content is that no file is edited; their check is the negative one below,
  and they carry it explicitly rather than being silently skipped.
- **No new column** — `git diff` on the plan template shows the Parallelization
  table's **header row byte-unchanged**. This is the single mechanical proof
  that the *Plan visualization* lock needed no amendment.
- **No new key** — `git diff hex/hex-core/references/config.md` is empty.
- **The lock is untouched** — `git diff hex/DESIGN.md` shows exactly two
  hunks: round 15 appended, and one clause added to the `### Worktrees`
  erratum pointer. The *Plan visualization* lock's lines appear in neither.
- **Single-source check** — the function is defined once, pinned to a sentence
  this ADR actually specifies for `protocol.md` (C-1101's own canonical
  wording): `grep -c 'The effective tier is never above the ceiling and is
  never authored' hex/hex-core/references/protocol.md` = **1**, and every
  other hit in `hex/` is a link or a one-clause qualifier.
  **Phrase-pinned, never line-pinned** — this ADR's own diff shifts every line
  it touches, which is the failure `adr_0010`'s round-2 review found in its own
  site table.
- **The false sentence is gone** — `grep -rn "skeleton (Stub → Specify →
  Implement → Review-Fix) unchanged" hex/` returns **zero** hits outside
  `DESIGN.md` round 15's own quotation of it.
- **The marker's refusal exists** — the `Error:` / `Fix:` pair for an
  unrecognized `Effective-tier:` value is present in `protocol.md` and matches
  the shipped refusal grammar.
- **The announce lines exist** — the effective-tier line, the histogram, the
  `derived` source token, the **one** new config-disclosure trigger (C-1122)
  and the **one** new risk-flag-degrade trigger class (C-1107, filed as its
  own trigger and **not** appended to the config-disclosure enumeration) each
  appear in `protocol.md`'s gate section, and the histogram grammar appears
  **once**.
- **No literal model name** in any changed shipped file.
- **The phase-ordering check is mechanical, not narrative** — for a WP that
  reduced to `low`, `git log --reverse` on its branch shows the stub+tests
  commit **before** the implementation commit, and the orchestrator's record
  carries the test command's **failing** exit at that SHA. A run whose only
  evidence is the builder's own prose is a C-1108 violation.
- **Range check** — `C-1101`–`C-1124` and `S-1101`–`S-1111` are contiguous and
  collide with nothing.

**Only a dogfood run can prove these** — the benchmark
`plan_wave0_quick_wins` defers to Wave 2 is the real gate, and it must produce
these five numbers on a multi-WP plan, measured externally rather than from a
transcript:

1. **Per-trip latency by capability class.** The one measurement this ADR's
   arithmetic is missing and the first thing the benchmark owes: a
   fast-balanced median batch→next-batch figure to sit beside the RCA's
   deep-reasoning 11.8 min. **Without it, whether the program's ≤ 30 min
   target is reachable at all is unknown** (D-1).
2. **Round trips per WP**, counted from `.claude/state/subagents.jsonl` for a
   size-S, flag-free WP: the claim is **3 on a clean review, 4 with one fix
   pass**, against the traced 9.
3. **The collapsed builder's turn cost**, against the 18-minute central
   estimate and its 12–25 band, which is the whole 9–26 % spread — and,
   separately, whether the stub+tests commit actually precedes the
   implementation commit on every reduced WP's branch and whether the test
   command genuinely failed at it (C-1108, checked from `git`, never from a
   worker's summary).
4. **The reduction rate** — the effective-tier histogram on a real plan. **This
   is a measurement, not a threshold**: no target percentage is stated, because
   `adr0012-risk-scoring.md` finding 16 reports that none is published
   anywhere.
5. **Wall clock**, total run against a pre-change baseline, reported alongside
   the reduction rate — the headline is meaningless without it, since a project
   with nothing attested reduces nothing and saves nothing by design.

**Two forced degrades, both required.**

- **No attestation.** Run against a project with no sensitive-path Pointers row
  — arcana today. Every WP must resolve at the ceiling and **exactly one**
  degrade line must print, naming the flags, the unreadable convention, and the
  remedy. **The byte-identity half is scoped so the test is satisfiable:** the
  baseline plan's `Review` cells must be **absent or `panel`**, and *that* run
  must be byte-identical to the pre-change baseline. The first draft demanded
  byte-identity unconditionally, which **C-1112 makes unsatisfiable** — a
  `self` or `light` cell goes inert and the run does more review than the
  baseline, which is the safe direction and a real difference. **The second
  half of the test asserts exactly that:** run a plan whose cells include
  `self` and `light`, and require the reduced WPs to resolve at the ceiling
  **with the extra review visible in the per-WP announce lines** — a run that
  came out byte-identical there would mean C-1112 did not fire.
- **Unrecognized marker.** Author a plan with `- Effective-tier: v2`. hex must
  **refuse** with the `Error:` / `Fix:` pair — never default to `derived`,
  never default to legacy, never prompt.

**One forced backstop.** Execute a plan in which at least one WP reduces, then
attempt to reach the terminal review state without a branch-level
`/hex-review`. It must not be reachable; then run `/hex-review` and confirm it
resolves at `max(classified, ceiling)` and announces which of the two won.

## Open Questions

Hard cap 3, each with a recommendation. **Two are open**; the third slot is
deliberately left unspent rather than filled — `hub`'s `medium` floor was
escalated here by the first draft *and* resolved in § Judgment calls 1, which
spent a capped slot on a question the ADR had already answered. A plain
approval at the meta-plan gate accepts both.

- **[NEEDS CLARIFICATION: should `arcana` attest its own security-sensitive and
  hot-path conventions now, and with what list?]** *Recommended:* **yes, and
  the ADR is inert here until it happens.** Add one `hex.md › Pointers` row
  **locating** both conventions — the row carries two paths, and the
  convention files they point at carry the lists (C-1105 rule 2; the row is a
  cache, never project truth). Proposed lists —
  security-sensitive: `hex/hex-core/references/**`
  (the contract surface every orchestrator reads), **`hex/DESIGN.md`** (the
  constitution every plan is gated against) **and `hex/hex-*/SKILL.md`** (the
  dispatchers that decide what spawns at all) — **the first draft's list
  omitted both, which would have let a constitution or dispatcher edit derive
  `low` and collapse**, the single worst reduction available in this
  repository — plus `.github/workflows/**` (Scorecard's Dangerous-Workflow
  class), `nox/src/nox/{config,outcome}.py` and any credential- or
  subprocess-handling module under `nox/`; hot-path:
  **an explicit empty set** — arcana ships prose bundles and one Python
  package with no latency budget, and `adr0012-risk-scoring.md` finds a
  maintained benchmark suite to be the only machine-checkable hot-path
  declaration, which arcana does not have. **Both halves are required**: a row
  silent on hot paths leaves `hot` reading `true` and buys nothing (C-1105,
  S-1104). The list above is the architect's proposal, not a verified audit —
  the row is `/hex-init`-owned and lands with owner consent, which is exactly
  why it is a question rather than a contract.
- **[NEEDS CLARIFICATION: is the collapsed builder's committed-stub check
  sufficient, or must Specify stay a separate spawn at effective tier
  `low`?]** *Recommended:* **sufficient for v1, and the residual is named
  rather than denied.** The check — stubs and tests committed first, the
  orchestrator re-running the project's test command at that commit and
  requiring failure (C-1108) — recovers the temporal property against the
  branch's own commit graph, which the first draft's self-reported transcript
  did not. **It still does not recover author≠verifier**: the separate `tester`
  spawn existed precisely so tests are written against the contract rather
  than against an implementation the same agent already has in mind, and one
  agent writing both is unchanged. **`Agentless` (arXiv 2407.01489) is
  supporting evidence and is explicitly not decisive here** — it shows a fixed
  staged pipeline beating open-ended agent scaffolds at lower cost, which is
  not the same operation as merging a TDD write-test step into the
  implementation turn, and it offers no data on that boundary. Keeping Specify
  separate costs one of the three collapsed trips, roughly a third of this
  ADR's wall-clock saving. Recommended as v1 because the reduced class is
  size-S and flag-free by construction (the dual gate), because the
  `review=minimal` batch still runs an independent `spec` reviewer, and
  because C-1117's ceiling-tier branch review is mandatory and covers exactly
  this. Revisit if the dogfood shows reduced-tier WPs escaping defects a
  separately-authored test would have caught — the fix is then one clause in
  C-1108, not a design round.

## Links

- RCA (the evidence): [`rca-review-fix-loop-wall-clock.md`](../research/rca-review-fix-loop-wall-clock.md)
- Commissioned research: [`adr0012-precedent.md`](../research/adr0012-precedent.md) · [`adr0012-risk-scoring.md`](../research/adr0012-risk-scoring.md) · [`adr0012-risk-flags.md`](../research/adr0012-risk-flags.md)
- Added at the design-panel fix pass: Xia, Deng, Dunn & Zhang, *Agentless: Demystifying LLM-based Software Engineering Agents*, arXiv [2407.01489](https://arxiv.org/abs/2407.01489) (Jul 2024, rev. Oct 2024) — a fixed staged pipeline beating open-ended agent scaffolds at lower cost; **supports "collapse is defensible", does not settle open question 2** (§ Industry Context) · Bondarenko et al., *Demonstrating specification gaming in reasoning models*, arXiv [2502.13295](https://arxiv.org/abs/2502.13295) (Feb 2025) — models gaming a reachable grader; **adjacent precedent, cited as the reason C-1108's self-reported transcript was replaced with a committed-stub check**
- Constitution: [`hex/DESIGN.md`](../../hex/DESIGN.md) — § Worktrees' 2026-07-20 perf-pass Review-budget addendum (superseded by pointer; already superseded once by round 12), the *Plan visualization* lock (**explicitly not amended**), round 11 (supersede-by-pointer convention), round 12 (live-lock adjudication), round 13 (the ten-file-diff cost of restatement, and the undeclared-file-set process defect)
- Predecessor this ADR partially supersedes: `adr_0010` (C-905's `Review` half — direction flipped, erratum rows 1/2/4; **C-916's *"No tier file gains a rule"* — erratum row 9**, the fourth constitution deviation; C-901/C-902/C-903/C-904/C-906–C-915/C-917/C-918/C-919 untouched — the same set § Interaction enumerates, contract for contract; C-903's fail-open sensitive-path clause cross-referenced; C-914's flat-state requirement met by construction)
- Sibling in flight: [`plan_wave0_quick_wins`](../plans/plan_wave0_quick_wins.md) (`State: executing`) — C-924 (widened `Verify` reach to **two** gates, built on), C-928 (**downward guard contradicted → suppressed in derived-generation plans**; the upward half is genuinely vacuous there), C-930 (histogram grammar adopted, bucket key replaced), C-936 (`DESIGN.md` round-number collision)
- Successor and seam: `adr_0013` — RCA root causes 4, 5 and 6 (worker liveness, adversary deadline, per-WP sub-orchestration, resource pitfalls); takes contract range `C-12xx` / `S-12xx`. **The seam is referenced by contract id, not by name**: `C-1219` / `C-1220` own coordinator ownership and the Q1-pipeline / Q2-decomposing split C-1104 and C-1109 scope their floor to; `C-1206` / `C-1207` own the dead-worker ladder § The arithmetic credits with one round trip; `C-1221` owns the serialization tail. **`adr_0012` decides which phases a work package runs and at what model class and review breadth; `adr_0013` decides how the workers running them are supervised, resourced and sub-orchestrated** — the three recorded seam gaps are at the end of § Interaction.
- Other predecessors depended on and not disturbed: `adr_0002` (C-101 ready-set, C-105 statuses and rollups), `adr_0003` (C-223 key freeze), `adr_0004` (C-302 column-position discipline, C-316 `(Repo, path)` keying, C-321 per-repo verification, C-324 terminal `landing` state), `adr_0005` (C-410 sole writer of the terminal review state), `adr_0009` (C-815 trust classes, C-819 sole-definition-site precedent)

---

## Changelog

| Date | Change |
|---|---|
| 2026-09-05 | **Spec revalidation round**, after the design-panel fix pass — a closed docket of 32 findings applied against this file alone; **five Blocks and the recommendation both unchanged: O1, Status Proposed.** *Block 1 — the two-gate correction.* Wave 0's C-924 says verbatim *"the Implement-phase gate is **not** coupled to the cell (D6, C-925)"*, so the `Verify` cell sets **two** gates (merge, Review-Fix-Loop exit), not three, and `door` makes **three**, not four; corrected at every site — § Judgment calls 2, C-1113, erratum row 3, S-1106 (*"one cell, three effects"*). *Block 2 — the Pointers row carries a pointer, never a value.* C-1105 rule 2 now restricts the row's half to a **repo-relative location**; the globs and the literal `none` live in the **target file**, read under rule 4, `none` **declared there and never in the row** — an undeclared Layer-2 deviation removed, and this round's own *"hex records where it lives, never what it says"* claim made structural rather than contradicted by its first consumer. Propagated to C-1107, the fail-closed rule, § Industry Context, § NFR Security, S-1104, § Migration and open question 1; the fail-closed direction is unchanged. *Block 3 + the round-count reconciliation.* The three `hex-execute` tier files gaining **a rule, not a qualifier** is a deviation, not a "considered and not deviated" note: promoted to **constitution deviation 4** and **round-15 amendment 5**, with `adr_0010` **C-916** (*"No tier file gains a rule"*) taking **erratum row 9**. Round 15 is now stated identically at all three sites — § Metadata, § Constitution deviations, the round-15 header — as **four amendments (items 1, 2, 4, 5) plus one new binding rule (item 3, C-1117's backstop, which amends no existing position)** plus one explicitly declined lock. *Block 4 — the coordinator floor, scoped.* C-1109/C-1104's floor applies only to `adr_0013`'s **decomposing** coordinator (`C-1219` Q2); a **pipeline** coordinator (`C-1219` Q1) does not raise it, or `C-1219`'s every-ready-WP coordinator would compose to "no WP ever derives `low`" and delete C-1108's collapse. Stated as `min(T, medium)`, never a flat `medium`, which at `T = low` broke C-1101's own ceiling invariant. *Block 5 — the seam is now referenced by contract id*: `C-1219`/`C-1220` (coordinator ownership), `C-1206`/`C-1207` (dead-worker ladder), `C-1221` (serialization tail), at the floor, the round-trip claim, § Links and a new **Seam with `adr_0013`** paragraph carrying the ownership split — *adr_0012 decides which phases a work package runs and at what model class and review breadth; adr_0013 decides how the workers running them are supervised, resourced and sub-orchestrated* — plus three recorded seam gaps. *The honest round-trip restatement:* **9 → 6 for this ADR alone**, 5 with wave 0, 4 with `adr_0013`'s liveness ladder, 3 on a clean R1 — the out-of-contract stage was silently claimed before. *Also corrected:* the adversary axis pinned to the **plan tier**, not the effective tier (C-1110), so a reduced WP in a `high` plan still runs the cross-model gate; C-1106 ground (c) *"structurally unreachable"* → unreachable **except** on coordinator-owned parents and sub-WPs, where C-1109's floor is the compensating control; C-1107 pins `config.md` rule 5's conjunct (b) to a **per-WP** evaluation and files the degrade line as a **new trigger class**, not a config-disclosure member; C-1104's sub-WP inheritance takes *"unless the sub-WP's own `Review` cell raises it (C-1112)"*; C-1112 names the `T = low` degenerate case; C-1120 and driver 6 carry C-1101's snapshot caveat; `hub`'s predicate is *"the same predicate on a different left operand"* as C-903, and the *"only ever fires across waves"* inference is dropped; `S`/`M`/`L` appear **in the plan template's example cells and nowhere else**; judgment call 6's *"one table"* claim replaced by C-1102's divergence statement and `~≤50` re-sourced to § Parallel-by-default decomposition; wave 0 is `State: executing`, which is the stronger ground for taking round 15; C-928 is *"downward guard contradicted → suppressed"*, never *"vacuous"*; O2's surface *"~6 sites"*; NFR Security reads *"authoritative-class **sources**"* against `memory.md`'s *"Never authoritative"*; `plan table` → `plan artifact`; the single-source grep pinned to a sentence this ADR actually specifies; C-1124 added to the contract-coverage exemption; C-1117's ceiling-floors-`--tier` clause moved from edit-site class 4 to class 6 (`hex-review/overlays.md` § Precedence); class 4 gains `hex-execute/SKILL.md` § Work packages' table-parse default and `overlays.md`'s out-of-axis *"lowers them per WP"* sentence; S-1111 moved to the end of the scenario table so S-1101–S-1111 are contiguous as § Validation asserts; judgment call 1's escalation dropped, leaving **two** open questions rather than spending a capped slot on a resolved one. Cross-model review skipped: budget. Status stays **Proposed**. |
| 2026-09-05 | **Design-panel fix pass** (spec / quality-adversarial / security / researcher seats, orchestrator-triaged). **The recommendation is unchanged — O1 — and the argument for it is not.** *Re-scored option comparison:* the draft credited `Review: self` with a 1-round loop; `protocol.md` says *"no reviewer spawns in this loop"*, so a correct `self` on WP-1 removes **66 min (35 %)** against O1's 43 (23 %). **The claim that O1 saves more is withdrawn**; the two tie on wall clock (both need the phase collapse) and O1 wins on *what gates the reduction* — non-authored signals versus one authored cell. O2 re-scored **98 → 91** (correctness 5→3, authoring-error 2→1, compatibility 5→3); margin 7 → 14, named a judgment call (§ Judgment calls 8). *Struck:* "mis-authoring downward becomes structurally impossible" — false; the error is **moved**, from a column that fails slow to one that fails silent, now priced in § Consequences › Negative and § Risks. *Replaced:* C-1108's self-reported red→green transcript with a **committed stub+tests first commit re-run by the orchestrator** — the transcript was produced by the worker whose claim it checked, which left the four-phase deviation with no defence. *Security:* `sec` now reads hex's own shipped `classify.md` triggers **OR** the project convention, project may only widen (C-1103, closing a silent loss of `reviewer:security` at `review=minimal`); C-1107 restores **both** conjuncts of `config.md` merge rule 5; C-1105 gains an exact read rule, closed enumeration, catch-all ⇒ `true`, target containment and *"`none` is declared, never inferred"*; C-1106's "direction-relative" reconciliation replaced with the **residual-risk/backstop-count** argument, plus the previously-unstated consequence that one attestation **disarms both** `sec` and `adr_0010` C-903's checkpoint trigger. *Spec:* byte-identity scoped to `Review` cells absent or `panel` (C-1124, S-1103, § Migration, § Validation); coordinator-owned WPs floored at `medium` (C-1109); marker parsing rule + refusal on a plan lacking `Verify` (C-1114); `panel` raises the tier, run axes then `min`-cap (C-1110/C-1111); ceiling `T` pinned to the plan's Status `Tier:` and flooring an explicit `--tier` (C-1101, C-1117); **constitution deviation 3 added** — the marker is a schema-version marker against `protocol.md`'s presence-checks rule; collapsed spawn reads the **highest** of three resolved model cells (C-1108/C-1122). *Corrections:* erratum row 4 retargeted to § The Review-Fix Loop; C-930's ordering rule was **misquoted** and the deviation built on it withdrawn (C-1119); C-928's downward guard is **contradicted, not vacuous** — suppressed, named at its site and C-929's three tier files; C-1102's `S` threshold **diverges** from `classify.md`'s `low` row (50 vs 100) and the "never drift" claim is dropped; `hub` re-derived at merge time and "declared sets are upper bounds — contractual" withdrawn (C-1116); effective tier recomputed **per WP at spawn**, not once at Discover (C-1101); "plan table" → "plan artifact"; the 23 % figure stated as the centre of a **9–26 %** band; sensitivity 1 corrected — the RCA's stub row **is** fast-balanced at 18 min, the slowest of the three phases, so the "half the median" path is withdrawn. *Added:* `memory.md` to the edit-site list (its Pointers entry must resolve as two halves); `hex-execute/SKILL.md`'s `1 per work package` phase table; the concession that `tier-medium.md`/`tier-high.md` gain **a rule, not a qualifier**; **S-1111** (the traced WP-1's 81-line diff re-deriving to `medium` at merge — S-1101 reworked so the flagship no longer fails the ADR's own backstop); the readable-but-narrow attestation risk; the irreversible-code grain of Rollback (a three-month reversal costs a ceiling-tier re-review, not a `git revert`); the `Verify: full`-costs-four-gates incentive gradient; the **reduce**-hatch assessment against the research's never-a-global-skip-switch warning; `hex/DESIGN.md` and `hex-*/SKILL.md` added to open question 1's path list; **Agentless** and **specification-gaming** citations, both caveated; a judgment-call entry conceding a bounded `git log -n 50 --numstat` sizing was available and unscored (D-3). Status stays **Proposed**. |
| 2026-09-05 | Initial draft. `C-1101`–`C-1124`, `S-1101`–`S-1110`; DESIGN round 15 proposed with two amendments plus one explicitly-declined lock amendment; `adr_0010` C-905's `Review` half partially superseded. **Five findings recorded against the synthesized design rather than smoothed over:** (1) the `Size` column is used by the function and **defined nowhere in the bundle** — C-1102 defines it from numbers already shipped in § Tier grammar and `hex-review/classify.md`; (2) `DESIGN.md` round **14 is already claimed** by `plan_wave0_quick_wins` C-936, so this round takes **15** with the renumbering rule stated; (3) a histogram format **does** exist in the approved wave-0 plan (C-930), so C-1119 adopts its grammar and replaces its bucket key instead of inventing a second line; (4) the RCA's final segment is labelled 69 min while its own timestamps give **53**, which is what closes the traced 186 — corrected and not propagated; (5) `adr_0010` C-903 reads the **same** `hex.md › Pointers` row fail-**open** where this ADR reads it fail-**closed** — reconciled by C-1106's direction-relative rule with cross-references at both sites, and recorded as a wart in § Consequences. Sub-WP and coordinator-parent derivation (C-1104), the run-scoped vs WP-scoped model-cell split (C-1109), and the `min`-composition of the run-level `review=` axis with the per-WP derivation (C-1110) were under-specified in the brief and are resolved here. The arithmetic attributes all 186 traced minutes to their owners and states plainly that the ≤ 30 min target is **not** reached by this ADR, and that its reachability depends on a fast-balanced per-trip latency **nobody has measured**. |
