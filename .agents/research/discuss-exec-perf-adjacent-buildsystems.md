# Research: Build-system dependency-graph scheduling and test selection

## Metadata
Date: 2026-08-30
Expires: 2027-02-28

## 1. Bazel/Buck2 action-graph scheduling

**Bazel.** The action graph is produced during analysis (rules → actions); a built-in
scheduler parallelizes actions up to estimated local resources
(`--local_cpu_resources`/`--local_ram_resources`), queuing the rest. Remote Build
Execution (RBE) offloads queued/eligible actions to a remote farm via RPC.
*Dynamic execution* races the same action locally and remotely simultaneously, takes
whichever finishes first, cancels the other — this is how Bazel avoids a static
local-vs-remote stage barrier, at the cost of requiring local/remote environment
parity for correctness. `--high_priority_workers` lets a mnemonic be scheduled
preferentially for mnemonics known to sit on the critical path; Bazel reports the
critical path ("longest pole") post-build. No public writeup of the underlying
ready-queue/priority-heap dispatch algorithm was found beyond this flag-level control
(see negatives).
Sources: [Dynamic scheduling for faster builds](https://blog.bazel.build/2019/02/01/dynamic-spawn-scheduler.html), [Dynamic Execution docs](https://bazel.build/remote/dynamic), [BuildBuddy: Bazel remote caching/execution](https://www.buildbuddy.io/blog/bazels-remote-caching-and-remote-execution-explained/).

**Buck2.** Structurally different: a *single* incremental dependency graph (via DICE,
a Salsa/Adapton-inspired incremental computation engine on Tokio executors) replaces
Bazel/Buck1's staged configuration → analysis → action-execution phases. "None of the
build phases in Buck2 are blocking, and thus multiple targets could transition through
different states in great parallelization" — i.e., parallelism comes from the absence
of phase barriers by construction, not primarily from local/remote racing (which Buck2
also supports, same mechanism as Bazel: race local vs. RE, configurable RE queue-time
threshold before falling back). `dynamic_output`/dynamic dependencies let a rule
inspect a built file's contents before declaring downstream deps/actions.
Sources: [Buck2 architecture](https://buck2.build/docs/developers/architecture/buck2/), [DICE docs](https://github.com/facebook/buck2/blob/main/dice/dice/docs/index.md), [Meta eng blog: Buck2 launch](https://engineering.fb.com/2023/04/06/open-source/buck2-open-source-large-scale-build-system/), [Buck2 Remote Execution docs](https://buck2.build/docs/users/remote_execution/).

## 2. Test selection: Google TAP, Meta, Chromium CQ

**Google TAP — Speculative Cycles / Transition Prediction (TRANSPRED).** Two-tier
system: *comprehensive cycles* run all affected targets periodically as capacity
allows (the full-coverage backstop); *speculative cycles* run a small, ML-ranked
subset every ~20 minutes to front-run breakage detection. Model: GBDT (Yggdrasil
Decision Forests) trained on 120B test×cycle pairs / 7.7M breaking targets / ~20k
unique culprits, with target-static (language, rule type), target-dynamic (historical
pre/postsubmit failure counts), and commit-level (lines changed, reviewer count,
linked bugs, build-graph distance to changed files, ran-at-presubmit) features.
Selection is *top-k by rank*, not a probability threshold, to hold cost/latency
constant. Results: 85% recall at a 25% test-budget vs. 56% for the prior baseline;
p50 breakage-detection latency cut 65% (107min → 37min); auto-rollback requires ≥10
distinct broken targets as corroborating evidence. A companion paper (ICSE-SEIP 2019,
"Assessing Transition-based Test Selection Algorithms at Google") found recency/history
heuristics underperform expectations, the best simple signals are trigger-count and
distinct-author-count, and **84% of test transitions are flakiness, not real
regressions** — flakiness is the dominant noise source any selection system must
filter before ranking is even meaningful.
Sources: [Speculative Testing at Google with Transition Prediction (summary)](https://hackthology.com/speculative-testing-at-google-with-transition-prediction.html), [Assessing Transition-based Test Selection Algorithms at Google](https://research.google/pubs/assessing-transition-based-test-selection-algorithms-at-google/).

**Meta — Predictive Test Selection (Machalica et al.).** GBDT model estimating
P(test fails | change), built on top of an already-computed *transitive
build-dependency candidate set* (via build metadata/graph reachability from changed
files to tests) — the model then ranks/downsamples within that graph-derived pool
using file-level history (change frequency, distinct authors) and past test-outcome
data, rather than inventing candidates independent of the graph. Deployed >1 year as
of the 2018 announcement; catches >99.9% of regressions while running ~1/3 of the
tests that transitively depend on the change; doubled testing-infra efficiency.
Flakiness is handled by aggressively retrying failing tests *during label
construction* so training data isn't corrupted by nondeterminism. No published
periodic full-suite backstop, unlike Google TAP's explicit two-tier design — plausibly
because the underlying build-graph reachability set (soundness guaranteed by the same
declared-deps discipline Buck2 depends on) already functions as Meta's safety net; the
ML layer only prunes inside it rather than replacing it.
Sources: [Meta eng blog: Predictive Test Selection](https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/), [Meta Research: Predictive Test Selection](https://research.facebook.com/publications/predictive-test-selection/).

**Chromium CQ.** Not ML-based — an explicit, curated, maintained configuration.
Default per-CL builder set is tuned for <40 min median cycle time and explicitly
"catches most but not all regressions." Extra coverage is opt-in: `Cq-Include-Trybots`
footer (manual), `location_regexp` (path-triggered builders), `ci_only` flag (defers
slow/flaky tests to post-submit only). Two backstops: (1) **Mega-CQ**, an opt-in
mirror of every gardened CI builder for high-risk changes, aiming to catch "nearly
all" regressions at much higher latency; (2) a structural rule that every CQ builder
must have a matching, actively-gardened post-submit/waterfall CI builder — post-submit
is the continuous full-coverage layer, and human gardeners triage what the CQ's
lossy, fast pre-submit filter let through. This is the opposite end of the spectrum
from Google/Meta: static config + human gardening rather than a learned model.
Sources: [Chromium CQ docs](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/infra/cq.md), [Chromium Chronicle #14: Adding Tests to the Waterfall](https://developer.chrome.com/blog/chromium-chronicle-14/).

## 3. What the change-to-test mapping requires, and where each breaks

- **Explicit dependency graph** (Bazel/Buck2 `rdeps` queries, Chromium's
  directory-triggers, Meta's build-graph-distance feature): needs a fully and
  accurately declared build graph. Breaks on anything the build system can't see —
  dynamically loaded code, reflection, runtime-only wiring — which is exactly why
  Bazel/Buck2 are strict about declared deps (an undeclared dep silently violates the
  graph's soundness guarantee). Sound but coarse: transitive closure in a large
  monorepo can still mean "run a third of everything" (Meta's own number).
- **Coverage-based / test-impact analysis** (line/file coverage maps from instrumented
  runs): requires runtime instrumentation with measurable overhead (binary size,
  execution time); the map can silently go stale or wrong, under-selecting tests with
  no warning; has no answer for a change with no coverage history (new file, new
  test).
- **ML/predictive** (Google TAP, Meta): needs a large labeled historical dataset —
  Google's sweet spot was a 3-week training window (shorter loses signal, longer
  dilutes it) — and must solve flakiness-as-noise before "test failed" is a trustworthy
  label at all (84% flaky transitions at Google; Meta retries aggressively at
  label-construction time). Cold start on new tests/services with no history is the
  structural gap ML cannot cover on its own, which is why Google TAP keeps an explicit
  periodic comprehensive-cycle backstop, and why Meta's ML sits on top of graph
  reachability rather than replacing it as the sole gate.
- **Explicit static config + human gardening** (Chromium): sidesteps both instrumentation
  overhead and cold-start/training-data problems, at the cost of being maintained by
  hand and deliberately admitting it misses some regressions, relying on a
  continuously-run post-submit layer and human triage to catch the rest.

## negative (dead ends / contradicting evidence)
- Buck2's internal scheduler/dispatch algorithm (ready-set ordering, priority-heap
  mechanics) is not publicly documented at the requested level — only the
  single-graph architectural rationale is public. "Buck2 avoids stage barriers via
  racing" is a category error: racing (local vs. remote) is a mechanism Buck2 shares
  with Bazel; the single-graph-no-phases design is Buck2's actual distinguishing
  mechanism for parallelism.
- Bazel's critical-path prioritization is thin outside the `--high_priority_workers`
  flag; no public spec of the ready-queue/heap algorithm surfaced in this pass.
- The primary Google TAP source (ICST 2025 "Speculative Testing" paper PDF) failed to
  parse via fetch (image/binary-heavy PDF); all TAP numbers above come from a
  secondary HTML summary of the same paper (hackthology.com) — treat as
  secondary-source-verified, not primary-PDF-verified.
- Chromium's older design doc (`chromium.org/.../commit-queue/design/`) is stale and
  thin on test-selection internals; the current `docs/infra/cq.md` was the better
  source and superseded it for this research.

## leads (adjacent lanes)
- Direct comparison of Google TAP's top-k budget selection vs. Meta's
  ranking/downsampling-within-graph-reachability approach — both GBDT-based but
  optimizing for different constraints (fixed latency/cost vs. fixed test-volume
  fraction).
- Chromium's `ci_only` + human-gardening rotation as a manual/organizational backstop,
  contrasted with Google/Meta's fully automated backstops — relevant if the angle is
  human-in-the-loop vs. automated safety nets.
- Flakiness-as-dominant-noise (84% of transitions at Google) suggests flaky-test
  detection/quarantine is a prerequisite system underlying any test-selection
  approach, worth its own lane.
- Datadog's and Martin Fowler's "Test Impact Analysis" writeups surfaced in search but
  weren't deeply fetched; could deepen the coverage-based-approach section if needed.
