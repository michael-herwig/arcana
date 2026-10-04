# Research: hex/nox harness + model config and state map

## Metadata

**Date:** 2026-09-06
**Domain:** cli
**Triggered by:** discussion `.agents/discussions/nox-hex-init-state-split.md` — entry recon (codebase)
**Expires:** 2027-03-06

## Direct Answer

Facts only, no recommendation. Every place configuration or detected state
about harnesses and models is stored or discovered across hex and nox.

## Key Findings

1. `.agents/memory/hex.md › Preferences` — literal `models.fast-balanced` /
   `models.deep-reasoning` + `models.overrides`, `adversary` skill name,
   `limits.*`. Written by `/hex-init` with consent; **team-shared,
   committed**; read-only for orchestrators (`hex/hex-core/references/memory.md:189`,
   `.agents/memory/hex.md:28-33`).
2. `.agents/memory/hex.md › Pointers` — verification/conventions/spec/product/
   worktree locations plus **measured** `Resource profile:` (peak RSS, wall
   time, light/heavy) and `Scratch:` root (`memory.md:188`). Skill-managed
   cache; project context wins on conflict.
3. `hex/hex-core/references/models.md:99-105` — shipped matrix holds
   capability classes; instantiation to literals happens only in
   `hex.md › Preferences`. Cells never resolve to an orchestrator-class model.
4. `hex/hex-init/SKILL.md:293-311` (Step 4) — detects "the harness in use…
   from the client running this skill, or ask if ambiguous"; writes nothing
   until Step 4½ consent.
5. `hex/hex-init/references/audit.md:199-224` — cross-model adversary skill
   detection via `grim status --format json` `items[]`/`outputs[]` or raw
   `SKILL.md` frontmatter `hex-adversary-scopes`; no network, executes nothing.
6. nox `trust.json` — `<XDG_STATE_HOME>/nox/trust.json`, config path → sha256.
   **v1 writes nothing to it** (D-w); `is_trusted` answers from the user-level
   `nox.toml` alone (`nox/src/nox/config.py:661-672`, `693-749`). Per-user,
   per-host; `$XDG_*`/`$HOME` inside the repo are refused (T4b).
7. nox `calls.jsonl` — append-only under the state dir, 7 fields
   (timestamp/harness/model/duration/outcome/cost/warning-count), never raw
   output (`nox/src/nox/log.py`).
8. `HarnessConfig` (`[harness.<name>]`) — `model` (class), `model_literal` +
   `effort` (trust-gated), `read_only`, `timeout`, `tools_allowed`,
   `launcher`, `passthrough` (`config.py:525-624`). Two-file merge: user-level
   (trusted) + first repo-local `nox.toml` upward (non-gated keys override;
   gated keys dropped with warning) (`config.py:1030-1120`).
9. `ProbeCache` — **in-memory, one per process**, deliberately not persisted
   (`nox/src/nox/harness.py:1880-1899`).
10. `HarnessInfo` / `probe_harness` — name, version, `verified_against`,
    capabilities, heartbeat kind, launcher; probed fresh every run in a
    nox-minted empty dir (`harness.py:720-772`, `1669-1715`).
    `version_warning` warns, never refuses (`harness.py:2383-2404`).
    `resolve_model` — trusted `model_literal` › unset › shipped `MODELS` entry
    for the class › harness default (`harness.py:2344-2380`).
11. nox CLI has exactly one verb, `review` (`nox/src/nox/cli.py:224-236`).
    No probe/doctor/list verb.
12. nox never infers the caller's harness; `--exclude` is caller-supplied and
    compared against the resolved `--harness`; match refuses (S-1011,
    `nox/src/nox/api.py:837-901`); omission only warns (C-1042(6)).
13. No `.local` file, gitignore split, or merge rule exists for an uncommitted
    `hex.md › Preferences` overlay (`config.md`, `memory.md:267-268`).

## Negative

- No probe/inspect/doctor/list nox verb; no persisted cross-run harness cache;
  no local overlay for `hex.md`; no `nox trust` command (schema only); no
  env var lets a repo redirect `XDG_*`/`HOME` into itself.

## Leads

- `ADAPTERS` registry is the single source of registered harness names.
- `adversary.md:115-129` "detected per run and announced, never stored" is
  the same shape as `ProbeCache`.
- `resources.md` § 2 is the one place hex caches a host-measured value in a
  committed file — contrast with nox's refusal to persist host state outside
  `$XDG_STATE_HOME`.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| repo files cited inline | Repo | 2026-09-06 | all findings |
