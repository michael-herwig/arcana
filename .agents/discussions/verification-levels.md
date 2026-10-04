# Discussion: proportional gate cost — verification cadence and review classification

State: parked · Updated: 2026-10-04 · superseded by adr_0020 (fast path, branch hex/fast-path-overhaul)

## Intent

In the owner's words: "shouldn't we support test-levels and advise (or make
configurable) when which test level is appropriate? Each test level describing
more like a guideline? Maybe there is some research to it?" — and earlier: "the
fact that so much is tested even for comment changes is an issue of the hex
suite, at least partially."

Why now: the ocx test-speed-tiers `/goal` run (session `cbb3cce0`, 2026-09-22 →
2026-09-24, ~36 h wall) spent ~18 h of leaf time in `task verify` (~25 min each,
serialized one-at-a-time) plus ~11 h in acceptance/Bazel runs and ~4 h in
quiet-host/lock waits, against ~11 h of total model time. Doc/wording fix agents
ran full verifies (a "small fix batch — messages, doc lines" agent: 6 full +
2 scoped). Friction recorded as retro entry
`.agents/retro/inbox/20260924T061049Z-1e78816e.json`.

Added mid-discussion (owner): "we should also check whether we can relax the
review classification, such that lower levels are used more often — sometimes a
two file change already triggers high."

Outcome shape: ADR (`/hex-architect`, `high` floor).

## Requirements

- A gate whose check is skipped or lowered still records what it did and
  why (the schedule log or the WP's evidence) — a silent skip is a defect
  (community lane: skipped CI checks that never report are the dominant
  real-world failure).
- The final gate stays full, fresh and un-lowerable; every cheaper path is
  backstopped by it (every surveyed selection system keeps a full backstop).
- hex still never defines a project's commands; anything new is bound by the
  project in `hex.md › Pointers`, and an unbound project behaves as today.

## Decisions

- **Verified-tree memo — yes.** A pass is recorded per (git tree hash, check
  command) and reused on the identical tree; the reuse is logged. Generalizes
  the narrow `/hex-finalize` exception (`hex/hex-core/references/finalize.md:71-75`).
  The final gate always runs fresh (covers flakes and external inputs).
- **Reviewer seats — targeted runs only.** Reviewers consume the builder's
  verification evidence and may run one targeted test to prove a finding,
  never the suite (today `hex/hex-core/references/workers/reviewer.md:28-29`
  allows "run commands for verification").
- **Mechanism — refined A, levels as guidance.** Keep `scoped`/`full` and the
  structural triggers; no hex-owned level vocabulary (council 3/3; avoids a
  fourth axis beside tier `low..max`, join level `L0–L3`, budget `scoped|full`).
  The owner's "test levels as guidelines" lands as `/hex-init` advice
  (`hex/hex-init/references/audit.md`) on how a project tiers its own
  documented scoped command, with ocx's T0–T3 as the worked example.
- **Fix passes — proportional re-verify, in-worktree only.** A review-fix pass
  whose diff touches only project-declared non-behavioural paths re-verifies
  with the build/parse half of the scoped check, logged; the merge-site scoped
  check and the fresh full final gate remain the backstop. No lowering at the
  merge site.
- **Hub trigger — fire on actual interaction.** The high-risk "path in another
  WP's `Expected Files`" clause (`hex/hex-core/references/verify.md:211-228`)
  fires only when that other WP has already merged, and at most once per WP
  pair; same file list, no new command.
- **Review classification — in this same ADR.** Same theme (a gate's cost
  proportional to the change), same `/hex-architect` run.
- **Tier table — size bands plus escalating markers.** In
  `hex/hex-review/classify.md` § Tier metric table, size metrics pick the
  **lowest** row whose file, line and area limits all hold; markers and labels
  only raise. Area bands stop overlapping (today `high` says 1–2 and `xhigh`
  says ≥2, so two areas land `xhigh`). Root cause of the owner's report: the
  rows are ceilings and the rule "pick the highest tier with at least one clear
  signal" makes any diff of ≤15 files / ≤500 lines match `high` when read
  literally (`classify.md:41-50`). A 2-file, 20-line, 1-area diff becomes
  `medium`.
- **Security path marker — whole words in the path.** `auth`, `crypto`,
  `sign`, `token`, `secret` match only a whole path segment or a `_`/`-`/`.`
  delimited word inside one (`ocx_sign`, `auth/`, `secret.rs`), never a
  substring (`design`, `DESIGN.md`, `signal`, `tokenizer`) (`classify.md:69`).
  The effective tier's `sec` flag (`hex/hex-core/references/decompose.md`
  § The effective tier) reads the same table and inherits the fix; projects may
  still widen via `hex.md › Preferences`, never subtract.

## Research

- `.agents/research/discuss-verification-levels-recon.md` — hex has two grades
  (`scoped`/`full`) chosen by structural triggers only; diff path/content class
  drives review depth, never verification; no general verified-tree memo (one
  narrow `/hex-finalize` exception); ocx's T0–T3 sits invisibly under hex's
  single `verify:scoped` pointer; vocabulary collisions: tiers `low..max`,
  join levels `L0–L3`, budgets `scoped|full`.
- `.agents/research/discuss-verification-levels-priorart.md` — four layerable
  mechanisms: static size/scope taxonomies (classify tests, not runs),
  change/impact-based selection (2–6× savings, non-zero escape, always a full
  backstop), coarse path-filter skips (GitHub required-check pitfall), result
  caching (undeclared inputs and flakes → confidently-wrong hits).
- `.agents/research/discuss-verification-levels-archaeology.md` — scoped
  merge check came from `adr_0010` (hex 0.2.0); diff-class skips, docs-only
  exemptions and verified-tree memo were declined or left opt-in (C-906), a
  tunable `M` declined; `adr_0012` rejected a continuous risk score for
  boolean flags; the hub-trigger degenerate case is acknowledged in
  `verify.md`; no prior retro named verification cost.
- `.agents/research/discuss-verification-levels-vendor.md` — no agent product
  does graded, diff-selected or cached verification; most delegate to project
  commands; OpenHands' fixed three-layer stack is the nearest "levels" shape.
- `.agents/research/discuss-verification-levels-community.md` — narrowed runs
  always paired with a full-run safety net and fallback-to-full on ambiguous
  diffs; path-based selection misses cross-module effects; Bazel cache-key
  bugs give stale greens; flake handling is a separate axis.
- `.agents/research/discuss-verification-levels-council.md` — 3/3 seats: no
  hex-owned level axis, no content-based lowering at the merge site; shared
  blind spot: the memo misses doc/comment-only fix passes (tree hash changes).

## Related

- `.agents/retro/inbox/20260924T061049Z-1e78816e.json` — verify-cadence retro entry.
- `hex/hex-core/references/verify.md`, `hex/hex-core/references/loop.md`,
  `hex/hex-core/references/decompose.md`, `hex/hex-core/references/worktree.md`,
  `hex/hex-core/references/resources.md`, `hex/DESIGN.md` (execution-performance round).
- `hex/hex-review/classify.md` (tier metric table, structural markers,
  plan/artifact default `high`), `hex/hex-plan/classify.md` (same "pick the
  highest" rule over descriptive rows), `hex/hex-core/references/decompose.md`
  § The effective tier (`sec` flag).
- `.agents/discussions/hex-execution-performance.md` — the earlier round that
  introduced the scoped merge check.
- Consumer prior art: `../ocx/.claude/artifacts/adr_test_speed_tiers.md` (T0–T3),
  `../ocx/scripts/scoped_gate.py`, `../ocx/test/scoped_rows.toml`.

## Out of scope

- A hex-owned verification-level axis (option B) and content-based lowering at
  the merge site (option C) — rejected, see council artifact.
- ocx's project-side cost drivers: its `hex.md › Pointers` row forcing full
  `task verify` at every WP merge, and `scripts/scoped_gate.py` escalating to
  full on any `scripts/**`/taskfile change. Owner decides in ocx; `/hex-init`
  guidance may flag the first pattern.
- ocx's 100 KB `hex.md` (memory "small by contract" not enforced) — separate
  retro item.
- Flaky-test quarantine and cache-key completeness — separate axes.

## Open questions

- [NEEDS CLARIFICATION: Where does the verified-tree memo live and what exactly is its key?]
  Recommended: key = `git write-tree` of the index after staging the worktree
  plus the resolved command string; stored in the run's schedule log /
  per-WP evidence, never a global cache — scoped to one run, so no stale
  cross-run hits.
- [NEEDS CLARIFICATION: Where are non-behavioural paths declared, and what is the default?]
  Recommended: a `hex.md › Pointers` row recorded by `/hex-init`; no default
  (unset = today's behaviour) — Markdown can be code input (doctests,
  `include_str!`, mkdocs), so hex must not assume `**/*.md` is inert.
- [NEEDS CLARIFICATION: Should a public-API change still jump straight to `xhigh` (`classify.md:71`)?]
  Recommended: raise to `high` plus `adversary=on` instead; `xhigh` only with a
  removal/rename of an exported item or a `breaking-change` label — in a Rust
  library nearly every `pub` edit counts as "public API surface".
- [NEEDS CLARIFICATION: Should plan/ADR review targets keep defaulting to `high`?]
  Recommended: classify a markdown target by its own size (lines changed in the
  artifact) with `medium` as the default for a delta re-review; `high` stays for
  a first review of a new plan or ADR.
- [NEEDS CLARIFICATION: How does the ADR answer adr_0010's earlier decline of docs-only exemptions and a memo?]
  Recommended: cite the ocx run (≈18 h of `task verify` vs ≈11 h model
  time) as the new evidence, and note both mechanisms are backstopped by the
  un-lowerable final gate.

## Verification

- `grim build` on every changed hex skill (`hex/hex-core`, `hex/hex-execute`,
  `hex/hex-init`, `hex/hex-review` as touched) exits 0.
- `task nox:verify` passes, including any contract-lint for cross-references.
- Contract checks: `verify.md` states the memo, the fix-pass carve-out and the
  narrowed hub clause once, linked (not copied) from `loop.md`, `worktree.md`
  and `workers/reviewer.md`; the final gate remains un-lowerable in text.
- Classifier fixtures: a table of sample diffs with expected auto tiers —
  2 files / 20 lines / 1 area → `medium`; 1 file / 10 lines → `low`;
  a `DESIGN.md` edit → no security marker; `crates/ocx_sign/src/lib.rs` →
  security marker; 2 areas → `high`; new crate manifest → `xhigh` — checked
  against the rewritten `classify.md` (a nox contract test if one fits).
- Field check: re-run a comparable multi-WP plan on ocx and compare full-verify
  count per WP and hours in verification against the 2026-09-22 run
  (session `cbb3cce0`), with zero regressions caught only by the final gate
  counted as the escape signal.
