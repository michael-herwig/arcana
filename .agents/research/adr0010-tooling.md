# Research: Invocation shapes of selective/scoped test execution tooling

## Metadata
- Date: 2026-08-30
- Expires: 2027-02-28
- Sources: see per-tool citations below; all fetched/searched 2026-08-30.

## Decision this informs
adr_0010 lets `/hex-init` record a project's selective-test command as a
convention; hex substitutes a changed-files/base-ref scope per work package.
This survey establishes what parameters such a convention must carry to work
across real tools, without hex having to know each tool's flag dialect.

## Per-tool invocation shapes

### Nx — `nx affected`
- `nx affected -t test --base=<ref> --head=<ref>` (head defaults to `HEAD`,
  base defaults to `nx.json`'s `defaultBase`, usually `main`). `--files=<list>`
  is an alternative to `--base`/`--head` for manually supplied changed files.
- Prerequisite: full git history sufficient to diff base..head, plus Nx's own
  project graph (computed from the workspace, not git).
- Fallback when the diff can't be computed (shallow clone, missing base ref):
  **not documented**. This is a real gap — Nx's own docs don't specify
  graceful degradation the way Turborepo's do.
- Sources: [nx affected](https://nx.dev/nx-api/nx/documents/affected), [Run Only Tasks Affected by a PR](https://nx.dev/docs/features/ci-features/affected), [nx.json Reference](https://nx.dev/docs/reference/nx-json)

### Turborepo — `turbo run <task> --filter`
- `--filter=...[<ref>]` (changed packages + dependents), `--filter=[<ref>]`
  (only changed), `--filter=[<ref>]...` (changed + their dependencies).
  Ref can be a branch, SHA, or `HEAD^1`.
- Prerequisite: git history covering base..head must exist in the checkout
  (docs recommend `--filter=blob:none --depth=0` for CI clones).
- Fallback is **explicit and documented**: "the comparison requires
  everything between base and head to exist in the checkout. If the checkout
  is too shallow, then all packages will be considered changed." This is a
  clean, safe-by-default degrade.
- Sources: [Filtering and Git-Based Filtering — Vercel Academy](https://vercel.com/academy/production-monorepos/filtering-git-based), [run reference](https://turborepo.dev/docs/reference/run)

### pytest-testmon
- Invocation: `pytest --testmon` — **no base-ref or file-list parameter at
  all**. It is stateful, not diff-based: a local SQLite DB (`.testmondata`)
  records which tests exercised which lines (via coverage.py), updated on
  every run, independent of version control.
- Prerequisite: a warm DB from a prior full run. First run with `--testmon`
  executes the full suite to seed the DB — that's the natural fallback.
  Persisting the DB across CI runs requires caching `.testmondata` as a build
  artifact; a stale/absent DB just means the next run pays the full-suite
  cost again to rebuild it.
- This tool **breaks the base-ref model entirely** — it can't be parameterized
  by `{base}` or `{files}`, only invoked as-is.
- Sources: [About testmon](https://www.testmon.org/), [Data Flow — DeepWiki](https://deepwiki.com/tarpas/pytest-testmon/3.2-data-flow), [Pytest testmon blog](https://blog.nshephard.dev/posts/pytest-testmon/)

### Jest
- `--changedSince=<branch-or-commit>` — ref-based, requires git/hg. If the
  current branch has diverged from the given ref, only *locally* made changes
  are tested (documented quirk, not a hard failure).
- `--findRelatedTests <file> <file> ...` — **file-list based**, no repo
  requirement at all; walks the static import graph forward from the given
  files to their tests. This is the one flag in the survey that takes
  `{files}` with zero git coupling.
- `--onlyChanged` (`-o`) — auto-detects changed/uncommitted files; requires
  git/hg and a static (non-dynamic) require graph.
- Sources: [Jest CLI Options](https://jestjs.io/docs/cli), [Under the hood: how Jest find related tests works](https://thesametech.com/under-the-hood-jest-related-tests/), [Jest and --changedSince in GH Actions](https://dev.to/bnb/jest-and-the-changedsince-flag-in-github-actions-ci-468i)

### Vitest
- `--changed <ref>` — mirrors Jest's `--changedSince`; accepts `HEAD~1`, a
  commit hash, or a branch name. Git-based, same shape as Jest's ref flag.
- Known rough edge (flag as immature): `--changed` only considers changed
  *source* files and historically ignored changed test files themselves
  ([vitest-dev/vitest#1113](https://github.com/vitest-dev/vitest/issues/1113)); a `--changed`-in-`list` interaction bug was still open as of the
  Vitest 4.1 era ([#8270](https://github.com/vitest-dev/vitest/issues/8270)).
- Sources: [Command Line Interface — Vitest](https://vitest.dev/guide/cli), [How does --changed work — discussion](https://github.com/vitest-dev/vitest/discussions/6734)

### Bazel — `bazel-diff` (Tinder)
- Two-step, **heavier prerequisite** than a single-command diff: run
  `bazel-diff generate-hashes` at the starting revision, check out the final
  revision, run it again, then `bazel-diff get-impacted-targets -sh <start.json> -fh <final.json>` (or feed the impacted-target list into a
  `bazel query 'rdeps(...)'`/`bazel test` invocation). Needs two full
  checkouts or two hash snapshots, not a single working tree.
- Fallback: **none needed by design** rather than none-documented — BUILD/
  WORKSPACE/`.bzl` file changes are hashed like any other input and propagate
  correctly through the target graph, so there's no separate "give up and
  build everything" branch to fall into.
- Sources: [Tinder/bazel-diff README](https://github.com/Tinder/bazel-diff), [Bazel Query Reference](https://bazel.build/query/language)

### Go
- No dedicated first-party tool needed for the common case: Go's build/test
  cache is content-addressed, so `go test ./...` already skips packages whose
  transitive inputs (including imported packages) didn't change — reverse-
  dependency invalidation is free and automatic, not something a wrapper has
  to compute. This only helps with a **warm, persistent cache**; on an
  ephemeral CI container the cache is cold and everything reruns anyway —
  which is itself the correct/degenerate fallback, requiring no special-casing.
- Lighter, coarser local-dev pattern (direct-changes only, no reverse deps):
  `go test $(git diff --name-only $base | xargs -I{} dirname {} | sort -u | sed 's#^#./#')`.
- Dedicated tool for explicit reverse-dependency selection from a file list:
  `go-selectivetesting`.
- Sources: [Testing only changed Go packages — Carlos Becker](https://carlosbecker.com/posts/go-test-changed/), [A single command to test all my changed Go packages](https://alexwlchan.net/notes/2026/go-changed-tests/), [go-selectivetesting](https://github.com/pwnedgod/go-selectivetesting)

### Cargo / cargo-nextest
- **No native git integration at all.** Selection is purely name/graph based:
  `-p <package>` / `--workspace`, and nextest filterset predicates like
  `package(name)`, `deps(crate)`, `rdeps(crate)` (reverse deps by name/glob) —
  none of these accept a git ref or a file list.
- A selective-test convention for Rust must supply its own glue: diff files,
  map paths to crate names via `cargo metadata`, then pass `-p` per crate
  (optionally widened with `rdeps()` to catch dependents). Third-party
  `cargo-rail` packages exactly this glue as "graph-aware change detection."
- Sources: [About filtersets — cargo-nextest](https://nexte.st/docs/filtersets/), [Running tests — cargo-nextest](https://nexte.st/docs/running/), [cargo-rail](https://github.com/loadingalias/cargo-rail)

### Gradle — AffectedModuleDetector
- `./gradlew runAffectedUnitTests -Paffected_module_detector.enable` (also
  `runAffectedAndroidTests`, `assembleAffectedAndroidTests`).
- Base-ref selection is a first-class, multi-mode config: `PreviousCommit`
  (default), `ForkCommit` (branch divergence point), `SpecifiedBranchCommit`,
  `SpecifiedBranchCommitMergeBase`, `SpecifiedRawCommitSha`.
- **Best-documented fallback model in the survey**: `buildAllWhenNoProjectsChanged` (default `true`) runs everything when impact analysis finds nothing
  affected; `pathsAffectingAllModules` (default includes `buildSrc/`) forces a
  full build when root-level/build-logic paths change. This is an explicit,
  two-rule escape hatch — recommend hex borrow this shape.
- Provenance note: Dropbox archived this repo; as of Aug 2025 it's
  community-maintained at `flo-health/AffectedModuleDetector` — cite the fork,
  not the archived original, in anything durable.
- Separately, Gradle Enterprise/Develocity ships "Predictive Test Selection,"
  an ML-based probabilistic selector — a different paradigm (likely-to-fail
  prediction, not deterministic changed-file mapping) and out of scope for a
  deterministic base-ref convention.
- Sources: [dropbox/AffectedModuleDetector](https://github.com/dropbox/AffectedModuleDetector), [flo-health/AffectedModuleDetector](https://github.com/flo-health/AffectedModuleDetector), [Gradle modules: Running unit tests only in affected modules](https://itnext.io/gradle-modules-running-unit-tests-only-in-affected-modules-fff89562339e), [Develocity Predictive Test Selection](https://docs.gradle.com/enterprise/predictive-test-selection/)

### Maven
- **Weakest ecosystem fit.** Reactor supports manual targeting
  (`-pl <modules> -amd`, also-make-dependents) but computing the changed-
  module list is not first-party — it must come from a script or a
  third-party extension: `lesfurets/partial-build-plugin` (git-diff-based;
  flag as possibly stale, no confirmed recent activity found) or the
  `maven-build-cache-extension` (sidesteps module selection altogether by
  restoring unaffected modules from a content-hash-keyed cache, closer to the
  Bazel model than to Nx/Turbo).
- Sources: [Incremental Builds — Apache Maven wiki](https://cwiki.apache.org/confluence/display/MAVEN/Incremental+Builds), [lesfurets/partial-build-plugin](https://github.com/lesfurets/partial-build-plugin), [Exploring maven incremental builds with maven-build-cache-extension](https://www.mortega.dev/posts/exploring-maven-build-cache-extension/)

## What the generic convention needs

Two orthogonal axes emerged, and the convention has to be honest about both:

1. **Input shape varies per tool and can't be normalized.** Some tools want a
   single git ref and compute their own diff (Nx `--base`, Turborepo
   `--filter=[ref]`, Vitest `--changed`, Jest `--changedSince`). Some want a
   pre-computed file list (Jest `--findRelatedTests`, a Cargo/Go glue script).
   Bazel wants two full hash snapshots, not a ref or a list. pytest-testmon
   and a warm-cache `go test ./...` want **neither** — they're stateful and
   self-scoping.
2. **Fallback-to-full is not uniform.** Turborepo and AffectedModuleDetector
   build it in and document it. Nx, Jest, Vitest, and Bazel-diff don't
   document an automatic degrade at all — an unresolvable ref is either
   undefined behavior or the caller's problem.

## Recommendation

Don't try to model each tool's flags. Have `/hex-init` record one opaque
shell-command template per project, with at most two optional named
placeholders that hex substitutes textually and never interprets:

- `{base}` — a single git ref, resolved by hex to the work package's
  merge-base/scope ref.
- `{files}` — a shell-quoted, space-separated list of changed file paths
  scoped to the work package.

Rules:
- A template may use zero, one, or both placeholders. Zero-placeholder
  templates (`pytest --testmon`, `go test ./...`) are valid — they mean "this
  command manages its own scope/state; just run it."
- `/hex-init` also records a `full_test_command` fallback (probably already
  captured elsewhere in the ADR's conventions). hex runs the full command
  instead of the selective one when either check fails, run *before* the
  selective command: (a) the template references `{base}` and
  `git rev-parse --is-shallow-repository` is true or the merge-base can't be
  resolved, or (b) the project has flagged the tool as one whose own fallback
  isn't trustworthy (i.e., anything other than Turborepo/AffectedModuleDetector-shaped tools, per the survey above) — since most surveyed tools don't
  self-degrade, treat "no documented fallback" as the default assumption and
  let a project override it only if its tool is confirmed self-degrading.
- Never have hex translate `{base}`/`{files}` into tool-specific flags itself
  — the project author already encodes the right flag syntax in the template
  they hand `/hex-init`. This keeps hex's surface area at "textual
  substitution + one shallow-clone guard," not "understand nine test
  runners' CLIs."

## Self-check (universal rule 7)
- Every per-tool claim above is cited to a URL fetched or searched today
  (2026-08-30).
- Flagged currency concerns explicitly: `lesfurets/partial-build-plugin`
  (no confirmed recent activity — treat as possibly stale) and the Dropbox→
  Flo Health AffectedModuleDetector migration (Dropbox archived it; the Aug
  2025 migration is the load-bearing recent fact, and I cited the live fork,
  not just the archived original).
- No claim is older than ~18 months by construction: all sources are current
  docs pages, active repos, or 2025/2026-dated posts/issues; none rely on
  pre-2025 blog posts as their sole support.
- Opinionated recommendation given, not just a survey: the `{base}`/`{files}`
  textual-substitution model with a pre-flight shallow-clone guard, scoped to
  hex doing substitution only and never flag translation.
