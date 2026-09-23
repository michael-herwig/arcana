# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] - 2026-09-23

### Added

- add finalize C-805a and the /hex-loop gate exemption
- add the goal-file template and goals-home audit items
- add the goal-file writer and goal-prompt printer
- add the → loop drain target
- name the branch in I9 and resolve deferred answers
- add retro skill and friction capture rule
- add retro checkpoints to hex-loop and hex-init

### Chores

- open 0.5.0 as the next train version
- run retro over the dogfood seed
- install hex-loop and hex-retro, update skills
- re-pin claude, codex, copilot harness versions
- bump publish manifests to 0.5.0, date hex changelog

### Documentation

- record the autonomous-goal-loop discussion and research
- propose adr_0018 goal-loop prompt
- document hex-loop in DESIGN, READMEs and changelog
- record plan_hex_loop with its dogfood evidence
- accept adr_0018 goal-loop prompt
- add discussion, research and goal file
- add ADR 0019, plan and design research
- register hex-retro, DESIGN round 24
- record finalize in plan status

### Fixed

- bind the named branch tighter

### Other

- announce nox to the public index alongside hex
- update skills

## [0.4.1] - 2026-09-06

### Added

- multi-harness adversarial review
- an adversary that ran and produced nothing is a skip, not a pass
- crescent badge logo
- per-WP effective tier, runtime contracts, instruction diet
- allow model invocation of /hex-finalize
- review by join level (adr_0015)
- parallel adversary, review checklist, reviewer config (adr_0016)
- five-tier grammar — inline low, xhigh, max (adr_0017)

### Changed

- shift tier files one step up (adr_0017 C-992, renames only)

### Chores

- sync the installed hex-discuss skill
- relock against grim 0.14.0
- repo-wide Task and gitleaks defaults
- pin the opencode CLI toolchain
- exclude agent worktrees from serena and VS Code indexing
- prepare 0.4.1

### Documentation

- design record, plan, research and swarm memory
- name the one routine eyJ false positive, and credential files under neutralized
- the Reviewed anchor reaches the tip
- review-fix wall-clock RCA, resource pitfalls, dogfood benchmark
- adr_0012, adr_0013, adr_0014 proposed, with plans and swarm memory
- adr_0016 and adr_0017 proposed; DESIGN rounds 21 and 22; changelog

### Fixed

- raise the opencode contract deadline to 600s, name its failures (E71)
- re-pin the claude adapter to 2.1.263
- re-pin the copilot adapter to 1.0.83
- the copilot contract tier reads tool-visibility at its 1.0.82 recording

### Other

- verify the signed release tag, then publish nox
- prepend changelog sections instead of regenerating
- SHA-pin actions/checkout to match publish.yml
- the opencode contract deadline was the bug, not the fixture (E71)
- drop the signed-tag release gate (E72)

## [0.1.1] - 2026-07-26

### Added

- publish under the michael-herwig/arcana namespace

## [0.1.0] - 2026-07-23

### Added

- initial hex skill

### Chores

- bootstrap arcana with logo assets and placeholder README

