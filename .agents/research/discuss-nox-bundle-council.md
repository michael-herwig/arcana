# Research: setup surface for nox/hex — council (3 blind seats)

## Metadata

**Date:** 2026-09-06
**Domain:** cli
**Triggered by:** discussion `.agents/discussions/nox-hex-init-state-split.md` — council lane
**Expires:** 2027-03-06

## Direct Answer

Question put to three blind seats: which shape owns harness/model/adversary
setup — (A) separate `nox-init` skill + hex-init detection; (B) hex-init the
only wizard, nox adds a `doctor` verb; (C) no wizard, doctor prints paste-able
config; (D) other. Also: where per-user-per-repo state lives; what is team vs
user vs detected.

**Unanimous:** no separate `nox-init` *skill*; ship `nox doctor` over the
existing probe machinery; C-1033 marker detection stays as is; nox stays
hex-blind; trusted keys never in a gitignored in-tree file.
**Split:** who writes the user file — premortem: nobody (paste); simplicity:
"some guided path earns its keep"; user-advocate: hex-init consumes doctor
read-only. Two seats: per-clone layer is YAGNI on current evidence.

## Key Findings

**Premortem seat** — verdict: sharpened C. `nox doctor` emits paste-ready
TOML; hex-init stays exactly at C-1033 scope. If per-repo pinning is ever
added, key it by `git rev-parse --git-common-dir` outside the tree, never
gitignored in-tree.
- nox structurally forbidden from knowing hex (C-1001; `nox-review/SKILL.md`
  marker the sole exception, adr_0011:602) — a nox-init skill cannot reuse
  hex-init's wizard conventions, so two wizard styles would coexist.
- hex-init charter (`hex/hex-init/SKILL.md:20-38`): write only what belongs to
  project or swarm. `~/.config/nox/nox.toml` is neither — a hex-init write
  there is out of charter twice.
- Trust split exists so a repo can never grant itself `launcher` /
  `model_literal` / `read_only`; a third layer is safe only if it inherits the
  user-level trust class (outside tree, outside branch reach).
- 48 refusals are a per-machine, cross-repo signal — "configure once per
  machine".
- Negative: paste step still manual; the refusal message already lists the
  fix and 48 runs refused anyway; no evidence refusals span repos wanting
  different harnesses.

**Simplicity seat** — verdict: B narrowed; no nox-init wizard, no new
per-user-per-repo layer.
- Probe machinery exists unexposed (`harness.py:1669,720,1880,2344`); CLI has
  one verb. Exposing = rung-2 reuse.
- Two config layers already clean; `launcher` (genuinely per-machine) is
  already user-level only.
- hex-init already has the seam (marker → propose pin) — stops at the skill
  name; the gap is data (harness registry), not a missing wizard.
- Existing wart not to repeat: committed `hex.md` stores literals and a
  per-host resource profile (`config.md:64`, `hex.md:30-33`, `resources.md`).
- Negative: pure C too spartan for onboarding. Team-committed repo `nox.toml`
  pinning `[review] harness` cannot coexist with a personal gitignored
  override at the same path (`CONFIG_NAME`) — lazy fix is documenting
  `--harness` wins, not a new layer; no evidence anyone hit it.

**User-advocate seat** — verdict: B; doctor consumed by hex-init's audit.
- hex-init already does the discoverable-pin half; missing is "installed +
  pinned but will not run". nox refusing = graceful skip, surfaced
  prominently only at `xhigh`/`max` (`adversary.md:158-167`) — a pinned,
  unconfigured nox yields zero reviews silently at `high`. Matches the 48
  refusals.
- Trust-gated keys force launcher/model_literal into the user-level file;
  team files may say *which harness/class*, never how to launch.
- Second-machine / new-teammate: `hex.md` travels with the pin, `~/.config`
  does not; nothing in hex-init's re-audit checks nox resolvability
  (`hex-init/SKILL.md:149-154`).
- nox-only Codex/Copilot user gets prose + hand-transcribed TOML.
  `openspec doctor` cited favourably in-repo
  (`.agents/research/openspec-framework-analysis.md:654-668`).
- Negative: repo-committed `nox.toml [review] harness` is real shareable
  state — do not overstate the gap.

## Recommendation (orchestrator synthesis)

`nox doctor` unanimous. "nox-init" resolves to an `init` **CLI verb** in the
pyz (prior art: doctor/status never write; init writes idempotently with
diff + consent, `--yes` for scripts) — no second wizard engine, hex-blind,
serves nox-only users. hex-init re-audit shells `nox doctor --json` read-only
and reports pin resolvability. Per-clone layer: keep in the ADR as a designed
layer, sequence after doctor/init. Separate hex defect to carry: adversary
skip visibility at tier `high`.

## Leads

- Surface the adversary skip at `high`, not only `xhigh`/`max` (`adversary.md`).
- doctor output renders straight from `HarnessConfig` field shape into a
  paste-ready `[harness.<name>]` block.
- Decision is ADR-shaped — C-1033 got a numbered contract for the adjacent seam.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| repo files cited inline | Repo | 2026-09-06 | all seats |
