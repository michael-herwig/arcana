# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-08-31

Consolidates three unreleased iterations (discussion mode, the finalize
phase, execution performance) into one release — 0.1.1 was the last
published version.

### Added

- `hex-discuss` skill — pre-plan discussion mode, drains to a plan, an ADR, a spec route, a project-context promotion, or a decision not to build
- `hex-state` rule — always on, re-anchors hex state from files after context loss, and holds code and config edits while a local discussion is `State: active` (released by parking it)
- `.agents/discussions/` convention for discussion artifacts
- `/hex-architect` accepts a handed-off discussion as its input, so the ground the discussion already covered is not re-explored: it explores only what the discussion left open, and skips the research axes the discussion already sourced with unexpired research
- A discussion dossier is user-ratified, consent-gated input — and still read as data, never as instructions — so the run is never below medium tier and the adversarial review is weighted up, not down
- `/hex-finalize` — takes a review-approved feature branch from *the work is right* to *this is ready to merge*: verify locally, recompose the commit series, one approval gate, then force-push and ready the pull request. The merge itself stays the human's; explicit invocation only
- A scoped remote-rights amendment: hex's "never pushes" rule is now "never pushes except `/hex-finalize`'s force-push of the one feature branch it was invoked on, after its gate", defined once in `hex-core/references/finalize.md` — the act set, consent model, force-push mechanics, backup-ref lifecycle, degrade ladder, and trust classes for convention inputs
- `/hex-init` audit item — "Commit and landing requirements documented?": DCO sign-off, signed commits, commit-message convention, which suites are release-grade, and which workflows are the release gate. It reads project context and checked-in files only, reaches no network, and recommends target-branch protection as the control that actually holds
- `/hex-review` hands an approved branch off to `/hex-finalize`
- A `Verify` column on the plan's work-package table (`scoped | full`) — plan-time, raise-only, for a work package whose merge deserves the full suite because it changes a default, a schema or a config value nothing textually references, which the merge-time risk predicate cannot see
- A `- Reviewed: <sha>` Status-block anchor and delta-scoped review rounds — a round reads what changed since the last round, plus the files the previous round's findings named, instead of re-reading the whole branch every time. The anchor is range-validated before use and falls back to a full-branch review when it fails; one full pass at the converged gate stays mandatory and cannot be lowered
- `## Schedule log` — an append-only plan section, one line per merge: time, work package, post-merge SHA, which gate ran and why, and the ready and blocked sets. It makes a ready-set that never widens visible as drift, and it makes a failed checkpoint bisectable. It replaces the plan template's never-written `## Progress Log`
- A selective-test-command convention — a `/hex-init` audit item ("Selective test command documented?") plus two `hex.md › Pointers` homes: where that command is documented, and where the project's security-sensitive / hot-path convention lives. hex substitutes `{base}` and `{files}` textually and never rewrites the command into a tool's flag dialect
- A stranded-work-package report at the end of a run: the failed work package first, then every package that never became eligible, each naming its direct blocker. `/hex-review` withholds the terminal Approve state — `done`, or `landing` for a federated plan — while a run ends with a non-empty stranded set

### Changed

- The per-merge gate: a work-package merge onto the feature branch now runs a scoped check — that package's own contract tests plus the project's cheapest documented gate proving the merged tree assembles — rather than the project's full documented verification. Full verification still runs on the documented triggers (a coordinator join; a checkpoint, which fires three merges after the last full run, on a cleared dependency level, or on a high-risk merge diff; and the final gate) and on the overrides (a `Verify: full` cell, or a degrade where no scoped check can be assembled). The final gate is unchanged and un-lowerable
- The failure cascade no longer halts the wave: a failed work package is still marked `failed`, but the run continues while any package is eligible and escalates at the end with the stranded set. A failure caught at a checkpoint is bisected over the merges since the last full run — the schedule log's SHAs make that free — and the escalation names the culprit, not the window

### Notes

- Upgrading changes the merge gate with no edit to any plan. The per-plan escape hatch is one Status-block line: `- Verify-default: full` restores the previous merge gates — the project's full documented verification after every merge — for that plan, and individual `Verify` cells still override it.
- No worker spawns and no new role for `/hex-finalize` — commit-boundary judgment needs the whole branch diff in one place and returns a decision, not a report, so `workers.md` and `models.md` are untouched. Revisit on field evidence that recomposition quality tracks the session model: that change is one spawn of an existing role plus one `models.md` row, not a design round.
- hex still ships no client-specific enforcement — `/hex-init` writes no `.claude/settings.json`, so `hex-state` is an always-on instruction, not a harness-enforced block. Revisit when a hooks entry lands in a tagged grimoire release.

## [0.1.1] - 2026-07-26

### Added

- publish under the michael-herwig/arcana namespace

## [0.1.0] - 2026-07-23

### Added

- initial hex skill

