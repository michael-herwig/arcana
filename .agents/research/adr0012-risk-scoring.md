# Research: Change-Risk Scoring and Size Heuristics for Review-Effort Scaling

<!--
Technology-landscape research. Filename and location: this project's
documented research convention (.agents/research/adr0012-risk-scoring.md).
Owner: a researcher worker. Handoff to: hex-architect (adr_0012).

Purpose: persist landscape findings that inform ADRs, plans, and design
decisions. Findings decay - check the Expires date before trusting them.
-->

## Metadata

**Date:** 2026-09-05
**Domain:** testing
**Triggered by:** hex-architect adr_0012 — deriving a work-package "effective
tier" from a declared size class (S/M/L) + risk flags, to cut a 9-round-trip
review pipeline to ~3 for changes scored small-and-safe.
**Expires:** 2027-03-05

## Direct Answer

Every mature system that scales effort by change size does it on **two
independent axes that must both clear**, never one: a *size/diff-shape*
signal (cheap, mechanical, always computed) and a *domain-risk* signal (path
sensitivity, ownership, churn history — expensive to get right, and the one
that actually predicts defects). Size alone is a weak, well-studied predictor
with hard thresholds (~200-400 LOC for review; ~100-200 LOC for Google's own
CL-size guidance); it correctly flags "this will be hard to review carefully"
but says nothing about *domain* risk — a 12-line change to an auth check or a
crypto path is exactly the false negative the task worries about. No system
in this research trusts size alone to lower effort; they gate a low-effort
path on size AND an explicit absence of risk flags (sensitive path, low
ownership, high fan-in/churn history), AND they all keep a **backstop** for
when the classifier is wrong — nobody claims their risk score is sufficient
without one. No source found publishes a target ratio of "how many changes
should get the fast path" — that number is not an industry constant, treat
any figure hex picks as a policy choice needing local calibration and
monitoring, not a citation.

## Technology Landscape

### Trending (gaining momentum)

| Tool/Pattern | Adoption Signal | Key Benefit | Relevance |
|---|---|---|---|
| ML-driven predictive test/review selection (Meta PTS, Google TAP) | Deployed >1yr in production at Meta; Google TAP in continuous use since ~2011 | Cuts test/review cost 2-3x while publishing an explicit recall floor | Model: publish a numeric safety guarantee for the "skip" decision, not just a heuristic |
| Continuous-benchmarking-as-declaration (CodSpeed, Bencher, criterion.rs) | New GitHub Marketplace apps, active 2024-2026 development | Makes "this is a hot path" a fact about CI (a benchmark exists) rather than a comment | Directly answers §5: benchmark-suite existence *is* the declaration |
| GitHub required-reviewer rulesets (separate from CODEOWNERS) | Shipped as ruleset GA Feb 2026, team-scoped variant Nov 2025 | Splits *ownership* declaration from *enforcement policy* | Same split hex should make: size/risk *classification* vs. *tier policy* |

### Established (proven, widely accepted)

| Tool/Pattern | Status | Notes |
|---|---|---|
| LOC-threshold review-effort caps (SmartBear/Cisco, Google CL-size guide) | Standard since mid-2000s, still cited | 200-400 LOC ceiling for careful review; Google's own internal guidance is tighter (~100-200 LOC) |
| CODEOWNERS + branch protection | GitHub/GitLab/Bitbucket native since ~2017 | Path-declared review requirement; silently absent = silently unprotected |
| Code churn / change entropy as defect predictors | Nagappan & Ball 2005, Hassan 2009; still the base features in JIT defect prediction papers through 2024-2025 | Most-replicated features in the literature |
| CI/PR size-warning bots (Danger.js) | Mature, stable since ~2016 | Same LOC-threshold idea as SmartBear, automated at PR-diff level |

### Emerging (early but promising)

| Tool/Pattern | Signal | Worth Watching Because |
|---|---|---|
| Network-centrality-based defect prediction (dependency-graph hub-ness) | Zimmermann & Nagappan ICSE 2008, still referenced in 2024-2025 defect-prediction surveys | Closest validated ancestor to "a file many concurrent changes also touch" — see §3 below, but it's a *static* dependency graph, not a live concurrent-PR-collision signal |
| Co-change-graph entropy (combining logical coupling + change entropy) | arXiv:2504.18511 (2025) | Recent, "statistically significant" combined-feature gain reported; not yet widely productionized |
| Gerrit "Trust" label proposal (separating authorization risk from review quality) | golang/go#40699 (2020), still under discussion | Shows even Google's own Go project treats "who is trusted to approve" as a distinct risk axis from "was this reviewed well" |

### Declining (losing mindshare)

| Tool/Pattern | Signal | Avoid Because |
|---|---|---|
| Running the full test/review suite on every change regardless of size | Google TAP explicitly moved away from this by ~2012 (ran out of capacity) | Doesn't scale; the entire risk-scoring literature exists because this became infeasible at scale |
| Pure-LOC-only effort estimation (no path/ownership/churn signal) | No production system found relying on this alone | Provably insufficient — every mature system layers a domain-risk signal on top |

## Design Patterns Worth Considering

- **Dual-gate, not single-score** — a change needs *both* a small size class
  and a clean risk-flag set to get the fast path; either one failing routes
  to full effort. Used by: implicitly every system surveyed (none uses size
  alone). This directly answers the "is 50 lines defensible" question: yes,
  as one of two gates, never as the sole gate.
- **Declaration-by-artifact over declaration-by-comment** — CODEOWNERS (a
  file), a benchmark suite (a file), a Scorecard check (re-derived from
  workflow YAML) are all machine-checkable facts, not free-text judgment
  calls. [CODEOWNERS](https://www.aviator.co/blog/a-modern-guide-to-codeowners/),
  [git-crypt .gitattributes](https://github.com/AGWA/git-crypt).
- **Itemized, re-derived score over cached label** — OpenSSF Scorecard
  recomputes every check from repo state on each run and reports a per-check
  point breakdown; nothing is "set once and trusted." This is the
  auditability model hex should copy (see §7).
  [scorecard/docs/checks.md](https://github.com/ossf/scorecard/blob/main/docs/checks.md).
- **Explicit asymmetric-cost framing for false negatives** — Google's Test
  Selection Safety and Evaluation Framework names false-negative ("unsafe")
  and false-positive ("conservative") disagreement as *not symmetric*: a
  missed regression ships silently, a spurious skip only costs compute.
  [research.google/pubs/test-selection-safety-and-evaluation-framework](https://research.google/pubs/test-selection-safety-and-evaluation-framework/).
- **Backstop via periodic full re-validation, not per-change trust** — TAP's
  postsubmit doesn't trust presubmit's selection; it batches and re-runs.
  Design translation for hex: a low-effort-tier work package should still be
  swept by a periodic/aggregate full-tier pass, not exempted forever.

## Key Findings

1. **SmartBear/Cisco (Cohen et al., "Best Kept Secrets of Peer Code Review,"
   analysis of ~2,500 reviews / 3.2M LOC over 10 months at Cisco):** optimal
   review chunk is 200-400 LOC; effectiveness at ≤400 LOC and 60-90 minutes
   yields 70-90% defect discovery; inspection rate above ~450 LOC/hour drops
   into below-average defect density in 87% of observed reviews; defect
   detection is roughly a **constant ~15 defects found per hour regardless of
   review size** — meaning bigger reviews don't find proportionally more
   defects, they just find a smaller fraction of what's there. Average defect
   density 32/kLOC; 61% of reviews found zero defects (most changes genuinely
   are safe — the base rate is on hex's side, but the literature's whole
   point is that size alone can't tell you which 39% aren't).
   [mikeconley.ca summary](https://mikeconley.ca/blog/2009/09/14/smart-bear-cisco-and-the-largest-study-on-code-review-ever/),
   [original Cisco case-study PDF](https://static1.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf).
2. **Google's own internal guidance is tighter than Cisco's**: "100 lines is
   usually a reasonable size for a CL, and 1000 lines is usually too large";
   a 200-line single-file change may be fine but the same 200 lines spread
   across 50 files usually isn't — **file count multiplies size risk**, it
   isn't a separate independent axis.
   [google.github.io/eng-practices/review/developer/small-cls.html](https://google.github.io/eng-practices/review/developer/small-cls.html).
3. **Google's measured review behavior (Sadowski et al., "Modern Code Review:
   A Case Study at Google," ICSE-SEIP 2018):** 90% of reviews touch fewer than
   10 files, >35% touch exactly one file; median time-to-first-feedback is
   under 1 hour for small changes vs. ~5 hours for very large ones, overall
   median latency under 4 hours. [ICSE-SEIP'18 paper](https://sback.it/publications/icse2018seip.pdf),
   [secondary summary](https://www.michaelagreiler.com/code-reviews-at-google/).
4. **Meta's Predictive Test Selection (Zhang et al., arXiv:1810.05286 /
   ICSE-SEIP 2019), deployed in production >1 year:** the model must clear a
   published production SLO of **>95% recall on individual test failures**
   and **>99.9% recall on "faulty changes"** (at least one failing test
   surfaced), while running roughly a third of dependency-eligible tests
   (~2x-4x cost reduction depending on source). No explicit periodic
   full-run backstop was found described in the paper/blog — **flagged as
   unverified/gap**; the recall floor is treated as the entire safety
   argument. [engineering.fb.com/2018/11/21](https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/),
   [research.facebook.com/publications/predictive-test-selection](https://research.facebook.com/publications/predictive-test-selection/).
5. **Google TAP** does not run all tests at every commit even in postsubmit —
   it batches and waits for capacity; Google explicitly built a **Test
   Selection Safety and Evaluation Framework** that defines false-negative
   ("unsafe": a missed regression full revalidation would have caught) vs.
   false-positive ("conservative": a spurious flag) as asymmetric outcomes,
   because false negatives silently ship broken compositions. This is the
   most direct precedent for "the failure mode that matters is a false
   negative." [Test Selection Safety and Evaluation Framework](https://research.google/pubs/test-selection-safety-and-evaluation-framework/),
   [Taming Google-Scale Continuous Testing](https://research.google.com/pubs/archive/45861.pdf).
6. **Code churn** (Nagappan & Ball, ICSE 2005, "Use of Relative Code Churn
   Measures to Predict System Defect Density") — *relative* churn (change
   size normalized to file/module size) is highly predictive of defect
   density; this is one of the most-replicated defect-prediction features
   through the current literature.
   [researchgate summary](https://www.researchgate.net/publication/4200542_Use_of_relative_code_churn_measures_to_predict_system_defect_density).
7. **Change entropy** (Hassan, ICSE 2009) — Shannon entropy applied to how a
   change is scattered across files predicts future defects; changes
   scattered across many files in a short window are more defect-prone than
   the same LOC concentrated in one file. Recent work (2025) combines
   co-change/logical-coupling graph structure with entropy and reports a
   statistically significant improvement over either alone.
   [PMC: Entropy Churn Metrics](https://pmc.ncbi.nlm.nih.gov/articles/PMC7512562/),
   [Co-Change Graph Entropy, arXiv:2504.18511](https://arxiv.org/pdf/2504.18511).
8. **Ownership fragmentation** (Bird, Nagappan, Murphy et al., FSE 2011,
   "Don't Touch My Code!," Windows Vista & Windows 7): the number of
   low-expertise ("minor") contributors to a component and the proportion of
   ownership held by the top owner correlate with both pre-release faults and
   post-release failures; removing low-expertise-contributor data from a
   prediction model **substantially degrades** the model's accuracy,
   confirming ownership fragmentation is a load-bearing signal, not noise.
   [ACM DL](https://dl.acm.org/doi/10.1145/2025113.2025119),
   [researchgate](https://www.researchgate.net/publication/221560133_Don't_Touch_My_Code_Examining_the_Effects_of_Ownership_on_Software_Quality).
9. **"Hub-ness" IS validated, under the name network centrality on a
   dependency graph** (Zimmermann & Nagappan, ICSE 2008, "Predicting Defects
   Using Network Analysis on Dependency Graphs," Windows Server 2003):
   network-centrality metrics (degree / ego-network measures on the binary
   dependency graph) beat traditional complexity metrics by **+10 percentage
   points of recall**, and identified **60% of the binaries developers
   independently flagged as "critical"** vs. only **30%** for complexity
   metrics. **Important caveat**: this is a *static* structural dependency
   graph (who depends on whom), not the specific "file that other
   concurrently-open changes also touch" collision signal hex is asking
   about — the closer literature family for *that* framing is logical/
   evolutionary coupling (co-change: files historically changed together),
   which is validated as a *complementary* signal (works best combined with
   churn/entropy) but is weaker in isolation than raw churn or ownership.
   Treat "concurrent-PR collision on the same file" specifically as
   **unverified as its own named, published metric** — it's a reasonable
   extrapolation from hub-ness/co-change, not a metric with its own citation.
   [Microsoft Research page](https://www.microsoft.com/en-us/research/publication/predicting-defects-using-network-analysis-on-dependency-graphs/).
10. **CODEOWNERS / GitHub branch protection**: path-scoped required reviewers;
    GitHub added a policy-layer "required reviewer rule" (GA Feb 2026,
    team-scoped Nov 2025) explicitly to separate *ownership* declaration from
    *enforcement policy* — CODEOWNERS still governs "who," the ruleset
    governs "is review mandatory here." **Absence handling**: a path with no
    CODEOWNERS match gets no automatic reviewer and no enforcement — silence
    means unprotected, not "reviewed as safe."
    [Aviator CODEOWNERS guide](https://www.aviator.co/blog/a-modern-guide-to-codeowners/),
    [GitHub changelog: required reviewer rule GA](https://github.blog/changelog/2026-02-17-required-reviewer-rule-is-now-generally-available/).
11. **OpenSSF Scorecard**: `Dangerous-Workflow` check flags
    `pull_request_target`/`workflow_run` combined with an explicit
    checkout of PR code (untrusted-code-execution pattern) and script
    injection via untrusted context variables in `run:` steps — it
    **re-derives risk from workflow structure on every scan**, so there is
    no "stale declaration" failure mode the way CODEOWNERS has; absence of
    the dangerous pattern scores well by default, it isn't a manual
    allow-list. `Code-Review` check penalizes unreviewed commits in the last
    ~30 (bot changes -3, a single unreviewed human change -7, more for
    repeated occurrences). `Branch-Protection` is tiered (force-push/deletion
    protection → reviewer requirement → status checks), each tier gated on
    the one below. [scorecard/docs/checks.md](https://github.com/ossf/scorecard/blob/main/docs/checks.md).
12. **Gerrit**: default `Code-Review` label plus arbitrary custom labels;
    Go's own tooling proposed a separate `Trust` label (2020) specifically
    because a single compromised or careless approver on the existing
    `Code-Review` label was judged too strong a single point of failure —
    an explicit precedent for **splitting "was this reviewed" from "is this
    approver trusted for this kind of change."**
    [golang/go#40699](https://github.com/golang/go/issues/40699).
13. **Danger.js / PR-size bots**: community convention warns at ~600
    combined added+deleted lines ("Big PR"); configurable rule sets like
    `@vtex/danger`'s `pr_size` default to an `additionLimit` around 800 —
    the same LOC-threshold idea as SmartBear, just automated and enforced
    pre-merge rather than advisory. [danger.systems](https://danger.systems/js/),
    [vtex/danger](https://github.com/vtex/danger).
14. **Secret/sensitive-path declaration precedent**: `git-crypt` declares
    sensitive paths via a checked-in `.gitattributes` (`path filter=git-crypt
    diff=git-crypt`), including `dir/**` for whole subtrees — a
    version-controlled, diffable, blame-able declaration file, the same
    pattern family as CODEOWNERS. Rules must exist **before** a sensitive
    file is added, or that file silently isn't protected — same
    "silence = unprotected, not safe" failure mode as CODEOWNERS.
    [github.com/AGWA/git-crypt](https://github.com/AGWA/git-crypt).
15. **Hot-path declaration has no standardized annotation convention** beyond
    the benchmark suite's own existence. `criterion.rs` (Rust), CodSpeed, and
    Bencher all work the same way: if a path has a maintained
    `#[bench]`/criterion/CodSpeed benchmark, CI gates merges on a regression
    threshold; CodSpeed's own marketing materials cite a 1.5% regression
    threshold achieving a sub-1% false-positive rate (**vendor-reported,
    unverified independently**). There is no equivalent to CODEOWNERS for
    performance sensitivity — "a benchmark exists for this path" is the only
    machine-checkable declaration found. [CodSpeed performance checks](https://codspeed.io/docs/features/performance-checks/index),
    [Bencher prior art](https://bencher.dev/docs/reference/prior-art/).
16. **No published fast-path admission ratio found anywhere in this
    research.** DORA's 2025 State of DevOps data gives a *destination*
    metric — elite performers run ~5% change failure rate, "ideal" is
    commonly cited as 0-2%, and only 8.5% of teams hit that ideal band — but
    none of Google/Meta/Gerrit/GitHub/OpenSSF sources publish "what
    percentage of changes should be eligible for reduced review." Treat this
    as a genuine gap: hex's fast-path admission rate is a policy choice to
    set conservatively and tune against measured outcomes (e.g., escaped
    defects on fast-tracked work packages), not a number backed by prior art.
    [DORA CFR summary](https://axify.io/blog/change-failure-rate-explained).
17. **Auditability**: no dev-tooling source in this research publishes a
    dedicated "why was this change classified low-risk" UX distinct from the
    declaration itself. The closest existing patterns are: (a) Scorecard's
    itemized per-check point breakdown, recomputed and shown on every run;
    (b) CODEOWNERS' match line being visible directly in GitHub's own
    reviewer-assignment UI; (c) Gerrit's Prolog submit rules being literal,
    readable source that can be inspected for which rule fired. None of
    these keep a **historical log of score changes over time** as a
    first-class feature in what was found — that would be new work for hex,
    not something to point at prior art for.

## Recommendation for adr_0012

**Feature set** (dual-gate: size class AND risk flags, both must be clean for
the reduced tier):

- **Size class** — LOC changed *and* file count, not LOC alone (Google's own
  guidance: 200 lines in one file is fine, the same 200 spread across many
  files isn't — [small-cls.html](https://google.github.io/eng-practices/review/developer/small-cls.html)).
  A ~50-line threshold for "S" is defensible as the aggressive end of a
  well-studied range (Cisco: 200-400 LOC before defect-finding degrades;
  Google's own internal norm is already tighter at ~100-200 LOC), so 50 lines
  sits comfortably inside the zone every source treats as reviewable in one
  pass — but it is a size gate only, never sufficient alone.
- **Risk flags that must all be clear**, each with its own literature/tooling
  precedent:
  1. **Path sensitivity** — a CODEOWNERS-style declared-paths list (security,
     auth, crypto, CI workflow files, release/publish paths). Model on
     CODEOWNERS + git-crypt's `.gitattributes` pattern: version-controlled,
     diffable, and — critically — **treat an unmatched path as "unknown,"
     never as "verified safe."** ([Aviator CODEOWNERS guide](https://www.aviator.co/blog/a-modern-guide-to-codeowners/), [git-crypt](https://github.com/AGWA/git-crypt))
  2. **Churn/entropy history of touched files** — files with high historical
     churn or that this change touches alongside many other files (entropy)
     escalate tier, per Nagappan & Ball 2005 and Hassan 2009 — both
     replicated, cheap to compute from git history alone.
  3. **Ownership concentration** — a file with no dominant owner / many
     recent low-context contributors escalates tier, per Bird et al. 2011 —
     validated and, per that paper, load-bearing (not safely droppable).
  4. **Fan-in / hub-ness** — a file many other modules depend on, or that
     recent commits/PRs frequently co-change with (logical coupling)
     escalates tier, per Zimmermann & Nagappan 2008 (+10pt recall, 2x hit
     rate on "critical" files vs. complexity alone) and the 2025 co-change
     entropy work. Be explicit in the ADR that "another *concurrently open*
     change touches this file" is an extrapolation of this literature, not
     itself a cited metric — flag it as such rather than over-claiming.
  5. **Hot-path/perf sensitivity** — presence of a maintained benchmark
     (criterion/CodSpeed/Bencher-style) for a touched path is the *only*
     machine-checkable "this is a hot path" signal found; its *absence* is
     not evidence of safety, only evidence nobody instrumented it.
  6. **Workflow/CI-file changes** — treat like Scorecard's Dangerous-Workflow
     check: re-derive risk from what the workflow diff actually does
     (`pull_request_target`+checkout, secret exposure) rather than a static
     path allow-list, since CI files are exactly where a stale declaration
     is most dangerous.

- **Thresholds, each with its source**: 50-line "S" ceiling (defensible per
  Cisco 200-400 LOC / Google ~100-200 LOC bands, biased conservative); file
  count as a size multiplier, not an independent bucket (Google small-cls.html);
  no numeric threshold available for churn/entropy/ownership/fan-in cutoffs
  in the surveyed literature — these papers validate the *features*, not a
  specific score cutoff, so hex should implement them as boolean escalation
  flags (touched-file exceeds Nth-percentile churn/fan-in in this repo's own
  history) rather than importing a borrowed absolute number that wasn't
  validated for this codebase.

- **Backstop discipline** (the load-bearing recommendation, since size+flags
  will still be wrong sometimes): mirror Google TAP's postsubmit
  re-validation, not Meta PTS's recall-floor-only approach — the research
  found TAP's periodic full-run backstop explicitly designed for the
  false-negative case, while Meta's published safety story rests entirely on
  its recall number with no disclosed backstop (a gap, not a model to copy).
  Concretely: (a) run the reduced-tier pipeline's *cut* review stages in
  full on a periodic aggregate sweep (e.g., every N merged low-tier work
  packages, or nightly) rather than never; (b) treat every reduced-tier
  merge as provisionally risk-scored, escalating retroactively (a
  "review the reviewer" pass) if the sweep or a later incident implicates a
  file that was scored low — same asymmetric-cost framing as Google's Test
  Selection Safety Framework (false negative ships silently, false positive
  only costs a few extra review rounds, so tune thresholds to
  over-escalate, not under-escalate, when uncertain).
  [Test Selection Safety and Evaluation Framework](https://research.google/pubs/test-selection-safety-and-evaluation-framework/).

- **Auditability**: since no source publishes a ready-made "why low risk" UX,
  build the simplest version of the two patterns that did show up in
  research — Scorecard's itemized, recomputed-every-time point breakdown,
  and CODEOWNERS' inline visible declaration. Concretely: persist, per work
  package, the matched size numbers and the boolean state of every risk flag
  (which one, if any, escalated it) as part of the plan/execution artifact
  hex already writes — not a separate score, a transparent list of the
  inputs that produced the tier, so overriding it means editing a visible
  flag rather than fighting an opaque number.
  [scorecard/docs/checks.md](https://github.com/ossf/scorecard/blob/main/docs/checks.md).

- **On the fast-path admission ratio**: no citable number exists (finding
  #16). Do not put a specific target percentage in the ADR as if it were
  evidence-backed; if a ratio is wanted for planning purposes, frame it
  explicitly as an internal policy default to be tuned against hex's own
  measured escaped-defect rate on reduced-tier work packages, not a value
  drawn from this research.

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| [Smart Bear, Cisco, and the Largest Study on Code Review Ever](https://mikeconley.ca/blog/2009/09/14/smart-bear-cisco-and-the-largest-study-on-code-review-ever/) | Blog (summary) | 2009 | LOC thresholds, defect density, inspection rate numbers |
| [Cisco Code Review Case Study (PDF)](https://static1.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf) | Vendor case study | ~2006 | Original source for the 200-400 LOC guidance |
| [Google eng-practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html) | Official docs | n.d. (evergreen) | Google's own ~100-200 line CL-size guidance, file-count multiplier |
| [Modern Code Review: A Case Study at Google (ICSE-SEIP'18)](https://sback.it/publications/icse2018seip.pdf) | Peer-reviewed paper | 2018 | Change-size distribution, review latency by size |
| [Predictive Test Selection (arXiv:1810.05286)](https://arxiv.org/abs/1810.05286) | Peer-reviewed paper | 2018 | Meta PTS recall guarantee, cost reduction |
| [Predictive test selection — Meta Engineering blog](https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/) | Company blog | 2018 | Production SLO framing, retraining cadence |
| [Test Selection Safety and Evaluation Framework](https://research.google/pubs/test-selection-safety-and-evaluation-framework/) | Research publication page | n.d. | False-negative vs false-positive asymmetry, TAP backstop framing |
| [Taming Google-Scale Continuous Testing](https://research.google.com/pubs/archive/45861.pdf) | Peer-reviewed paper | 2017 | TAP presubmit/postsubmit batching, capacity constraints |
| [Use of Relative Code Churn Measures to Predict System Defect Density](https://www.researchgate.net/publication/4200542_Use_of_relative_code_churn_measures_to_predict_system_defect_density) | Peer-reviewed paper (Nagappan & Ball, ICSE 2005) | 2005 | Churn as a replicated defect-prediction feature |
| [Entropy Churn Metrics for Fault Prediction](https://pmc.ncbi.nlm.nih.gov/articles/PMC7512562/) | Peer-reviewed paper | n.d. | Change entropy as a defect signal (Hassan 2009 lineage) |
| [Co-Change Graph Entropy (arXiv:2504.18511)](https://arxiv.org/pdf/2504.18511) | Preprint | 2025 | Combined coupling+entropy feature, recent |
| [Don't Touch My Code! (ACM DL)](https://dl.acm.org/doi/10.1145/2025113.2025119) | Peer-reviewed paper (Bird et al., FSE 2011) | 2011 | Ownership fragmentation validated as load-bearing |
| [Predicting Defects Using Network Analysis on Dependency Graphs (MSR page)](https://www.microsoft.com/en-us/research/publication/predicting-defects-using-network-analysis-on-dependency-graphs/) | Peer-reviewed paper (Zimmermann & Nagappan, ICSE 2008) | 2008 | Hub-ness/network-centrality validated, +10pt recall |
| [A Modern Guide to CODEOWNERS](https://www.aviator.co/blog/a-modern-guide-to-codeowners/) | Vendor blog | n.d. | CODEOWNERS mechanics, absence-handling |
| [GitHub Changelog: Required reviewer rule GA](https://github.blog/changelog/2026-02-17-required-reviewer-rule-is-now-generally-available/) | Official changelog | 2026-02-17 | Ownership-vs-policy split, recent |
| [scorecard/docs/checks.md](https://github.com/ossf/scorecard/blob/main/docs/checks.md) | Official docs | current (main) | Code-Review, Branch-Protection, Dangerous-Workflow scoring mechanics |
| [Gerrit issue: golang/go#40699 (Trust label)](https://github.com/golang/go/issues/40699) | Issue tracker discussion | 2020 | Precedent for splitting trust/authorization from review-quality label |
| [Danger JS](https://danger.systems/js/) | Official docs | n.d. | PR-size warning convention |
| [vtex/danger](https://github.com/vtex/danger) | OSS repo | n.d. | Configurable `pr_size` thresholds |
| [git-crypt (AGWA)](https://github.com/AGWA/git-crypt) | OSS repo/docs | n.d. | Sensitive-path declaration via `.gitattributes` |
| [CodSpeed: Performance Checks](https://codspeed.io/docs/features/performance-checks/index) | Vendor docs | current | Regression-gate mechanics; 1.5% threshold cited elsewhere (vendor-reported) |
| [Bencher: Prior Art](https://bencher.dev/docs/reference/prior-art/) | Vendor docs | current | Continuous-benchmarking landscape survey |
| [Complete Guide to Change Failure Rate (DORA)](https://axify.io/blog/change-failure-rate-explained) | Blog (secondary summary of DORA 2025 report) | 2026 | Change-failure-rate benchmarks (destination metric, not admission ratio) |
