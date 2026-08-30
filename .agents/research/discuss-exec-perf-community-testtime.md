# Research: Test-suite time inside automated/agentic dev loops (community evidence)

## Metadata
Date: 2026-08-30
Expires: 2027-02-28
Lane: community-threads (strictly neutral — evidence only, no recommendation)

## Scope
Practitioner experience with test-suite time inside automated/agentic dev
loops: slow suites (5+ min) hit on every TDD/verify iteration. How teams
bound it (selective test execution, tiered pyramids), and reported
successes/failures — especially selective-testing "escapes" (regressions the
subset missed).

## Findings

### The feedback-loop-speed argument (baseline motivation)
- ploeh blog, "TDD test suites should run in 10 seconds or less"
  (https://blog.ploeh.dk/2012/05/24/TDDtestsuitesshouldrunin10secondsorless/):
  canonical statement that TDD cadence (1-2 runs/minute) requires sub-5-second
  feedback; a 5-minute suite breaks the red-green-refactor cycle entirely
  because feedback arrives after the developer has moved on.
- Quality Coding, "Are Slow Tests Killing Your Feedback Loop?"
  (https://qualitycoding.org/slow-tests/): slow suites make developers
  reluctant to add tests and defer running them, lengthening the cycle
  further — a compounding effect, not just a one-time cost.
- dev-tester.com, "How Slow Is Too Slow to Run Your Tests?"
  (https://dev-tester.com/how-slow-is-too-slow-to-run-your-tests/) and
  MinimumCD's "Test Suite Is Too Slow to Run"
  (https://beyond.minimumcd.org/docs/symptoms/testing/slow-test-suites/):
  root-cause is usually pyramid inversion (too many E2E/integration tests
  launching browsers/services vs. fast unit tests).

### Selective test execution — tools and reported experience
- **pytest-testmon** (https://github.com/tarpas/pytest-testmon,
  https://www.testmon.org/): coverage.py-based dependency tracking, selects
  only tests touching changed code. HN thread on it
  (https://news.ycombinator.com/item?id=46540391) exists but the fetched
  content only returned story metadata, no comment text was retrievable.
  Documented behavior issue: tarpas/pytest-testmon#90 — `--testmon -x` still
  re-runs an already-known-failing test, i.e. state can get stale/out of
  sync after interrupted runs (testmon is explicitly stateful).
- **Jest `--onlyChanged`/`--changedSince`/`--findRelatedTests`**: walk the
  *static* import graph. jestjs/jest#10222
  (https://github.com/jestjs/jest/issues/10222, open/unresolved since 2020):
  these flags ignore `moduleNameMapper`-aliased imports, so a source file
  reached only via an alias doesn't trigger its dependents — false
  confidence that changes are safe when the relevant tests simply never ran.
  jestjs/jest#11271 (missing merge base) and Lightrun/dev.to writeups note
  shallow-clone CI checkouts (`actions/checkout` default depth) break
  `--changedSince` outright.
- **vitest `--changed`** shares the same static-graph blind spot: dev.to
  writeup "Why vitest --changed misses some tests"
  (https://dev.to/kazutaka-dev/why-vitest-changed-misses-some-tests-and-how-runtime-coverage-fixes-it-jjm)
  gives a concrete repro — a registry/dynamic-`import()` loader pattern
  (`import(REGISTRY[name])`) has no static edge from test to source, so the
  selector reports "No test files found" for a file the test actually
  exercises. Proposes recording *runtime* coverage per test instead of
  static parsing, with the stated safety principle "when in doubt, run
  more, never less."
- **Nx affected**: nrwl/nx#22835 "the affected projects might have not been
  identified properly"
  (https://github.com/nrwl/nx/issues/22835) and nrwl/nx#1222 ("affected:test
  --all does not watch changes in files/specs") document detection gaps.
  nrwl/nx#3419 flags a related process gap: `nx affected` doesn't consider
  previously-failed jobs, so a commit that doesn't touch the failing test's
  dependencies lets a still-broken test quietly not re-run. nrwl/nx#34211
  (v22 regression) shows the inverse failure mode — an over-broad affected
  calculation made *every* commit relevant to *every* project, erasing the
  speed benefit for independent packages.
- **Bazel**: no direct "affected targets missed dependency" GitHub issue
  surfaced; Bazel's model instead leans on explicit `size` attributes
  (small/medium/large/enormous, each with a RAM+timeout budget — small: 20MB/1min,
  medium: 100MB/5min, large: 300MB/15min) per Google Testing Blog "Test
  Sizes" (https://testing.googleblog.com/2010/12/test-sizes.html) and Bazel's
  test encyclopedia (https://bazel.build/reference/test-encyclopedia), plus
  javac's direct-dependency checking to fail fast on undeclared deps.

### Explicit false-negative/escape discussion (the core risk)
- **Martin Fowler, "The Rise of Test Impact Analysis"**
  (https://martinfowler.com/articles/rise-test-impact-analysis.html) is the
  most direct primary source on this exact question. Key points:
  - States the core assumption plainly: "other tests, that passed before,
    will pass again since the code that they exercise hasn't changed" — and
    flags that this breaks under external state (resource files, config,
    timing/environment).
  - Quotes Misha Dmitriev (creator of Microsoft's Testar/TIA-style tool):
    selective execution "may not be the best option if a company runs a
    wide variety of tests, and has enough hardware resources" — i.e. full
    parallel runs can beat selection when compute is cheap.
  - Cites a real deployment (HedgeServ's "Test Reducer") cutting a
    12,000-test Excel-based suite from hours to ~10 minutes.
- **Microsoft Azure DevOps Test Impact Analysis** docs
  (https://devblogs.microsoft.com/devops/accelerated-continuous-testing-with-test-impact-analysis-part-1/,
  https://learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis)
  explicitly name the false-negative risk ("TIA thinks a test isn't
  affected when it's actually broken") and mitigate with a documented safe
  fallback: run full suite on protected branches, and fall back to running
  everything whenever a change (e.g. HTML/CSS, non-managed code) is outside
  what TIA can reason about.
- **Meta/Facebook "Predictive Test Selection"**
  (https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/,
  paper: https://arxiv.org/pdf/1810.05286) — the strongest production-scale
  data point. ML-ranked test selection deployed >1 year at the time of
  writing: catches >99.9% of regressions before they reach trunk while
  running only ~1/3 of tests, explicitly modeling and discounting test
  flakiness in its training signal. This is a "selective testing done well"
  counterpoint to the Jest/Nx/vitest escape reports above — the difference
  being ML-based historical-outcome ranking (with an accepted small
  residual miss rate) vs. static-analysis dependency graphs (which can miss
  entire classes of edges deterministically, e.g. aliasing/dynamic imports).

### HN community sentiment (direct quotes, via Algolia API — the raw HN
pages 429'd on direct fetch)
- Thread "Faster CI with Selective Testing" (https://news.ycombinator.com/item?id=42517163):
  - **gorset**: Bazel-based selective testing cut a pipeline from ~30 min to
    "seconds-to-minutes" despite the project growing.
  - **deathanatos** (central skeptical voice): path-based test selection "is
    wrong" — gives a concrete counterexample where a commit touching only
    `b/*` paths passes its selected subset and is marked green while it
    actually broke something outside the naive path mapping; calls these
    "successive miss" bugs "almost always" present in real implementations.
  - **ay**: real-world case of unrelated plugins breaking together via
    shared memory contention / function-table offsets — a failure mode
    invisible to any dependency- or path-based selector.
  - **lbriner**: "if we could accurately know the dependencies... we are not
    likely to have a problem in the first place" — and notes flakiness
    alone causes ~50% of CI failures the selection problem doesn't touch.
  - **atq2119**: recommends merge trains/batching full validation over
    several commits rather than trusting per-commit selection alone.
- Thread "Slow CI: real problem or easy excuse for developers?"
  (https://news.ycombinator.com/item?id=19047096):
  - **craftyguy**: non-test overhead (artifact fetch, compile, syncing
    across ~200 test devices) can exceed actual test execution time — a
    reminder that "test time" in these threads is often conflated with
    total pipeline time.
  - **malkia**: cites Google/Bazel's small/medium/large test-size tiering
    as the standard tiered-pyramid answer.
  - **Orphis**: "a proper build environment will know what tests could be
    impacted and only run those in CI" (pro-selective-testing).
  - Contrarian tangent: **segmondy** ("100% feature tests, 0 unit tests")
    vs. **monksy** (feature-only leaves paths unvalidated) vs. **avinium**
    ("the correct amount of testing is the amount that lets you refactor
    quickly" — rejects fixed pyramid ratios as dogma).

### Agentic-loop-specific evidence
- Dan Luu, "Agentic test processes..." (https://danluu.com/ai-coding/):
  describes an early personal workflow of "a very simple loop that would
  just keep compiling the code and running the tests and re-prompting until
  everything passes" — i.e. the naive brute-force verify loop this research
  topic is about bounding. Also describes a hardware-company pattern of a
  fast pre-commit tier on overclocked dedicated machines plus a 3-month
  wall-clock full regression suite run continuously on a compute farm (20%
  regression / 80% new-test-generation split) — an extreme version of the
  tiered-pyramid pattern.
- dspn.substack, "Model Feel, Fast Tests, and Staying in Flow with AI Coding
  Agents" (https://dspn.substack.com/p/model-feel-fast-tests-and-staying):
  "the real breakthrough for me wasn't just picking the right model, but
  adding simple, fast tests (like Cypress reloads) to the harness... Fast,
  agent-runnable tests have saved my sanity more than any leaderboard-topping
  model ever could." Frames harness/feedback-loop speed as higher-leverage
  than model choice.
- Claude Code hooks docs/community writeups (e.g.
  https://thepromptshelf.dev/blog/claude-code-hooks-complete-reference-2026-v2/):
  the emerging agentic-loop pattern is a `Stop` hook that runs the test
  suite and blocks the agent from declaring the turn done on failure —
  moving "did tests pass" out of model judgment and into deterministic
  harness enforcement. This is orthogonal to selective-testing speed but is
  the concrete mechanism by which "every iteration" actually invokes the
  suite in current agentic tooling.

## Negative (dead ends / contradicting evidence)
- Could not retrieve actual comment text for the HN "Testmon" thread
  (https://news.ycombinator.com/item?id=46540391) or the "Making PyPI's test
  suite faster" thread (https://news.ycombinator.com/item?id=43931237) —
  direct HN fetch returned HTTP 429, and the Algolia API mirror for the
  Testmon thread returned only story metadata with an empty children array
  (comments not indexed/returned). Flagging so another pass can retry later
  or via a different HN mirror.
- No r/ExperiencedDevs or general Reddit thread specifically about
  slow-suite-in-agentic-loop frustration was found via search; general
  queries surfaced only generic testing-best-practice blog posts, not
  practitioner threads. Absence noted, not confirmed absent.
- No GitHub issue was found documenting a concrete Bazel "affected target
  selection missed a dependency" regression — Bazel's ecosystem discussion
  skews toward flaky-test handling (`--flaky_test_attempts`) rather than
  selection-correctness bugs, suggesting either Bazel's target-graph model
  is more trusted for correctness than Jest/vitest's import-graph model, or
  simply that such issues aren't tagged/searchable the way Jest's are.
- pytest-testmon's own docs/FAQ page did not yield explicit text on
  documented unsafe scenarios via fetch (page structure didn't expose it to
  the fetch tool) — the tool's own caveats are asserted by secondary sources
  (blog.nshephard.dev, ipwnponies.github.io) but not confirmed first-party
  in this pass.

## Leads (adjacent lanes, one line each)
- Google's 80/15/5 unit/integration/E2E pyramid ratio (Google Testing Blog,
  Software Engineering at Google) as a normative baseline worth comparing
  against other lanes' recon on real-world test pyramid shapes.
- Flakiness-as-confound: multiple sources (lbriner on HN, Meta's predictive
  selection paper) treat flaky tests as a *separate* ~50%-of-failures
  problem that selective testing doesn't solve and can even obscure —
  possibly its own research lane.
- Merge trains / batched validation (atq2119's suggestion) as a distinct
  bounding strategy from both selective testing and tiered pyramids — worth
  a dedicated look if the exec-perf discussion wants a third bucket.
- CoverUp / HITS (arxiv 2503.14713, agentic test-suite generation using
  runtime coverage) — adjacent to selective testing via runtime coverage,
  but for generation rather than selection; the "testpick" tool in the
  vitest article above uses the same runtime-coverage idea for selection.
