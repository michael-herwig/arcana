# Changelog

All notable changes to this project will be documented in this file.

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

