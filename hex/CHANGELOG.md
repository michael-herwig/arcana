# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-08-29

### Added

- `/hex-finalize` — takes a review-approved feature branch from *the work is right* to *this is ready to merge*: verify locally, recompose the commit series, one approval gate, then force-push and ready the pull request. The merge itself stays the human's; explicit invocation only
- A scoped remote-rights amendment: hex's "never pushes" rule is now "never pushes except `/hex-finalize`'s force-push of the one feature branch it was invoked on, after its gate", defined once in `hex-core/references/finalize.md` — the act set, consent model, force-push mechanics, backup-ref lifecycle, degrade ladder, and trust classes for convention inputs
- `/hex-init` audit item — "Commit and landing requirements documented?": DCO sign-off, signed commits, commit-message convention, which suites are release-grade, and which workflows are the release gate. It reads project context and checked-in files only, reaches no network, and recommends target-branch protection as the control that actually holds
- `/hex-review` hands an approved branch off to `/hex-finalize`

### Notes

- No worker spawns and no new role for `/hex-finalize` — commit-boundary judgment needs the whole branch diff in one place and returns a decision, not a report, so `workers.md` and `models.md` are untouched. Revisit on field evidence that recomposition quality tracks the session model: that change is one spawn of an existing role plus one `models.md` row, not a design round.

## [0.2.0] - 2026-08-29

### Added

- `hex-discuss` skill — pre-plan discussion mode, drains to a plan, an ADR, a spec route, a project-context promotion, or a decision not to build
- `hex-state` rule — always on, re-anchors hex state from files after context loss, and holds code and config edits while a local discussion is `State: active` (released by parking it)
- `.agents/discussions/` convention for discussion artifacts
- `/hex-architect` accepts a handed-off discussion as its input, so the ground the discussion already covered is not re-explored: it explores only what the discussion left open, and skips the research axes the discussion already sourced with unexpired research
- A discussion dossier is user-ratified, consent-gated input — and still read as data, never as instructions — so the run is never below medium tier and the adversarial review is weighted up, not down

### Notes

- hex still ships no client-specific enforcement — `/hex-init` writes no `.claude/settings.json`, so `hex-state` is an always-on instruction, not a harness-enforced block. Revisit when a hooks entry lands in a tagged grimoire release.

## [0.1.1] - 2026-07-26

### Added

- publish under the michael-herwig/arcana namespace

## [0.1.0] - 2026-07-23

### Added

- initial hex skill

