# hex — swarm memory

Maintained by the hex skills. Small by contract: pointers and
preferences, not copies. Team-shared — commit it.

## Pointers

- Verification: `CLAUDE.md` › "Verification" — `grim build <skill-dir>`
  per changed skill; full sweep `task publish -- --dry-run`.
- Plan / ADR conventions: `CLAUDE.md` › "Spec / plan / ADR conventions" —
  plans `.agents/plans/`, ADRs `.agents/adrs/` (MADR),
  research `.agents/research/`; hex shipped templates are the
  format.
- Spec home: `.agents/specs/` — ID marker: default (shipped
  `^#{1,6}\s+(C|S)-[0-9]+\b`; no override in Preferences).
- Product knowledge: `.agents/product.md` (indexed from `CLAUDE.md`).
- Key rules: `CLAUDE.md` › "Architecture rules" → `hex/DESIGN.md`
  (binding for the hex bundle).
- Worktrees: default `.agents/worktrees/` (gitignored).
- Constitution: `hex/DESIGN.md` (plans gated against its resolved
  decisions).

## Preferences

- Models (instantiated for this harness): fast-balanced → Sonnet,
  deep-reasoning → Opus. The hex matrix takes precedence over global
  CLAUDE.md model routing for hex spawns.
- Cross-model adversary: `codex:rescue` skill (one-shot; fires on
  one-way-door/security signals or `--adversary`).
- Limits: max-workers 8, loop rounds 1 (per-run `--loop-rounds`
  overrides).

## Memory

- **AUTONOMOUS PROGRAM (started 2026-07-22, no-prompt).** Goal: all three ADRs
  (0003/0005/0004) implemented + a tier-high hex review/fix loop **converged**
  (≤5 iterations); default layout made **arcana-unspecific** — move
  `.agents/*` → `.agents/*` and change shipped hex defaults
  `.agents/` → `.agents/` (a late mechanical sweep, so ADR builders keep
  stable anchors); resulting skills must be **superior to** github/spec-kit,
  openspec.dev, and the ocx swarm skills, and **able to replace the swarm
  skills** + express swarm structure as user config. Constraints: **do not
  prompt**; **edit only this repo** (`/home/mherwig/dev/arcana`); **this
  instance = orchestrator**, forward maximally to subagents. Integration
  branch: `hex/spec-superiority-program` (off `3b7cfca`, stacks 0003→0005→0004→
  de-arcana→swarm). Land locally at the end, **never push**.
  - **Progress (2026-07-22):** adr_0005 landed (5 commits `939e1bb`→`c9d5fd6`,
    residual-fix subagent applied 11 Warn fixes); adr_0004 landed (7 commits
    `968b8fe`→`42e440f`, 4 actionable fixed in-loop). Both grim-green, all
    reviewers approve. Remaining: Stage 3 swarm docs + adr_0007 (Proposed) →
    Stage 4 de-arcana sweep → Stage 5 tier-high convergence (≤5 iters) → local
    land. Deferred 0004 Warn residuals for Stage 5 in
    `scratchpad/convergence-todo.md` (tier-low Discover gap; single-source
    drift across hex-execute tier files; DESIGN stale cite; template
    restatement).
  - **De-arcana done (2026-07-22, `8d0a3c9`):** `.agents/arcana/*` → `.agents/*`
    (this file now lives at `.agents/memory/hex.md`); shipped defaults rewritten
    `.agents/arcana/` → `.agents/` (91 refs across 27 files); all 6 grim builds
    green; CLEAN (zero residual). Stage 3 shipped `b8cc17c` (README positioning +
    config.md swarm recipes); adr_0007 milestone-driver authored **Proposed**
    (C-6xx, untracked). Remaining: **Stage 5** tier-high convergence loop (≤5) +
    codex adversary → local land (merge to main, never push). Program = 20
    commits off main `bb137ba`.
  - **LANDED (2026-07-22, merge `f1c47a2`, NOT pushed).** Stage 5 converged in
    4 rounds (the loop caught a de-arcana over-match, a dead ADR link, an
    unreachable landing→done, a Fold-Back phase-id gap). Codex cross-model
    adversary then caught **2 real gaps the loop missed**, both fixed
    fail-closed + re-verified: (1) **C-405 stale-base guard had no command
    evidence** (heading census can't see inline sub-IDs) → added a pasted
    sub-ID span scan mirroring C-416; (2) **a workflows fork could keep the
    Fold-Back phase but gut its guards** → config check 6 now fail-closed (a
    fork that folds must discharge archive.md § Safety envelope or is
    malformed → shipped-tier fallback). 23 commits merged to main; grim green.
  - **DEFERRED to Michael:** (a) `grim install` — `.claude/skills/` install
    copy ~23 commits stale (+ an uncommitted 16-line hand-patch in its
    protocol.md). (b) ratify 3 shipped fail-closed ADR amendments (adr_0003
    fork-security; C-405 command-evidence in adr_0005; fork fold-safety in
    adr_0003×0005). (c) **adr_0007** milestone driver is Proposed — accept/
    reject. (d) ADR `file:line` cites drifted 16/25 (shipped bundle uses
    heading anchors, all resolve) — mechanical re-resolve clears them. (e)
    design docs under `.agents/` still untracked per convention. (f) not
    pushed.
- Active decisions, **all Accepted** (Michael, by 2026-07-21; each first went
  panel → fix → re-validate → cross-model adversary → fix → re-validate, then
  a tier-high `/hex-review` of the working tree + a `/hex-execute` fix pass —
  **cross-consistent as a set**, re-verified):
  - `adrs/adr_0003_configuration_customization_surface.md` — config carrier
    + customization surface. Option D (frozen key block in
    `hex.md › Preferences` + forkable tier files). C-2xx.
  - `adrs/adr_0004_cross_repo_federation.md` — lead repo owns the change,
    `Repo` column, `git -C` satellite worktrees, `Hex-Plan:` trailer.
    C-3xx (301–324). Driving cluster: the ocx family.
  - `adrs/adr_0005_archive_fold_back.md` — terminal fold-back into the
    project's *documented* spec home; hex never ships the destination.
    C-4xx (401–419).
- **Implementation program, planned 2026-07-21** (`/hex-plan high "accept all
  and implement"`). An Opus architect reconcile pass settled the cross-ADR
  order and interactions; three plan artifacts authored + spec-reviewed
  (100% contract coverage each: 23/23, 19/19, 24/24), all fixes applied and
  re-validated. **Execute in strict order 0003 → 0005 → 0004** — one at a
  time; each runs against the prior's landed tree, so plans 2/3 anchor on
  headings + contract IDs, never line numbers.
  - `plans/plan_adr_0003_config_surface.md` — 6 WPs / 4 waves. New
    `hex-core/references/config.md` is the SoT for 13 contracts. Release-gate:
    P1-W2* (v1 vocabulary freeze) before first `grim release`; P1-W3
    (`workflows` v2 + wizard) floated to the very end, non-blocking.
  - `plans/plan_adr_0005_archive_fold_back.md` — 5 WPs / 3 waves. New
    `hex-core/references/archive.md` SoT. 0005 is the **sole amender** of
    hex-review's never-writes contract (0003 + 0004 both defer to it) — this
    is why 0005 lands before 0004.
  - `plans/plan_adr_0004_cross_repo_federation.md` — 8 WPs. P3-W1 (FM6
    memory-guard) independently shippable; P3-W3a (protocol.md change model,
    16 contracts) is the spine, P3-W3c/d/e federation edits parallel after it.
  - **Reconcile key finding:** C-223 freezes only the six v1 yaml *keys*; the
    0005 ID-marker regex and 0004 Federation bullets are Preferences/Pointers
    **prose**, not keys — the freeze does not reach them, so the order needs
    no escape hatch. No file collision forces a rework pass (all additive
    under strict order). Every ADR that amends `DESIGN.md` carries its dated
    round as a hard checkbox deliverable.
  - **Two open questions are Michael's** (folded into the plans as
    `[NEEDS CLARIFICATION]` with defaults): (1) first `grim release` before
    or between the plans — default "whole program first, `workflows` freezes
    v1, split moot"; (2) ship P3-W1 FM6 guard standalone-early or bundled —
    default bundled.
  - Reconcile brief saved this session at
    `scratchpad/reconcile-brief.md` (§1 C-223, §2 waves, §3 collisions,
    §4 constitution risk, §5 sequencing, §6 open questions).
- `adrs/adr_0006_finding_severity_contract.md` — **Accepted** (Michael,
  2026-07-20): a `[Block|High|Warn|Suggest]` severity tag on the
  `reviewer.md` worker line + a single-source `protocol.md § Finding
  severity`; no table, no synthetic ID. C-5xx (501–511).
- **Active plan:** `plans/plan_adr_0003_config_surface.md` (State: **review**,
  tier high, 2026-07-22) — **executed**, all 6 WPs across 4 waves landed on
  branch `hex/adr-0003-config-surface` (7 commits `bfc1f74`→`3b7cfca`, atop
  the adr_0006 merge on main). Next: `/hex-review
  .agents/plans/plan_adr_0003_config_surface.md`, then Michael lands
  the branch, then `/hex-execute plans/plan_adr_0005_archive_fold_back.md`.
  - **Shipped:** new `hex-core/references/config.md` (the config vocabulary
    SoT — 6 v1 keys, ten merge rules, glob/perspectives/tiers/phase-ids,
    §Workflows v2); protocol.md/memory.md/workers.md/models.md wiring; the
    four orchestrators' announce blocks + tier prose + dispatch interception;
    `/hex-init` Step 4½ + interactive wizard + fork lifecycle; DESIGN.md
    round 6 (4 constitution amendments).
  - **Cross-model gate (codex) caught a CRITICAL the panel missed:** workflow
    forks were a second path to drop `reviewer:security` outside C-218's
    attestation. Closed fail-closed in config.md check 6 (fork dropping the
    shipped security role without the `security-sensitive-paths: none`
    attestation is malformed → falls back to shipped tier file).
  - **Deferred to Michael:** (1) the fork security invariant closes a gap
    C-218 didn't cover — ships fail-closed, but ratify as an ADR amendment;
    (2) the **dogfood config yaml block was NOT written** into
    `.agents/memory/hex.md › Preferences` — C-202 says only /hex-init
    writes it with consent, and it freezes the keys, so it's Michael's
    /hex-init run; (3) two adr_0003 ADR-text nits (line 1026 apply-consent
    wording; C-210 "step 7" stale for hex-architect); (4) `grim install` sync
    of `.claude/skills/` (drift now spans ~13 shipped files across this plan
    + adr_0006).
  - Then plan_adr_0005, then plan_adr_0004, in that order.
- **Landed 2026-07-21:** `plans/plan_finding_severity.md` (adr_0006) — State
  `done`, merged to `main` as `24937c7` (3 commits: `a1c5e9e` WP1 hex-core,
  `c8db253` WP2 hex-review, `bb137ba` branch-review fix). Branch deleted.
  - **Behavior change shipped:** `High` now gates the verdict at all three
    hex-review sites ("High- or Warn-tier"). Reviews that previously Approved
    with an unresolved High finding now return Needs Work.
  - **Branch review caught + fixed one High** before landing: the Suggest
    verdict-floor cell read "none — routed to the deferred summary",
    re-introducing the phantom `suggest` *disposition* (routing by severity,
    not class) inside the canonical source; fixed to "none — reported, but
    never gates the verdict" in both `protocol.md` and adr_0006's normative
    block (byte-identical). All other panel findings adversarially refuted.
  - **Deferred (human call):** `protocol.md`'s "Nothing to report → no
    findings lines" can be read as *omit the whole `### Findings` section*,
    while the ADR Validation checklist says an empty bucket prints `(none)`.
    Ambiguity in the ADR's own prose, not a defect — one clarifying line
    resolves it.
  - **Learned:** `grim build` does **not** validate markdown links or
    anchors (proven repeatedly). A `#anchor` sweep is manual — resolve each
    `](path#anchor)` to a real file + heading yourself, with `/usr/bin/grep`.
- Traceability ID ranges in use, so the next ADR does not collide: adr_0001
  `C-00x`, adr_0002 `C-1xx`, adr_0003 `C-2xx`, adr_0004 `C-3xx`, adr_0005
  `C-4xx`, adr_0006 `C-5xx`. 0004 and 0005 were drafted in parallel and both
  grabbed `C-3xx`; 0005 was renumbered while still Proposed. Assign the range
  at the gate, not in the architect prompt — the next ADR takes `C-6xx`.
- **Implementation status, audited 2026-07-21** (3 auditors + adversarial
  verify, evidence read from `hex/` only — installed `.claude/skills/` copies
  never count): adr_0003 **1 of 23** contracts implemented (C-201) plus C-216
  partial (batching half yes, the 4-step displacement procedure no) ≈ 7%;
  adr_0004 **0 of 24**; adr_0005 **0 of 19**. Not partial — structurally
  absent: `hex-core/references/config.md` (home of 13 adr_0003 contracts)
  does not exist, no `yaml` block anywhere in `hex/`, all four dispatch steps
  still the verbatim pre-ADR line, `hex-init/SKILL.md` byte-identical to the
  ADR's quoted "before" state, `DESIGN.md` has no new dated round. Nothing
  was ever planned for them — they are still Proposed, and the adr_0003
  sliver leaked in as *review fixes* to shipped text, not as implementation.
  Its C-201 text physically entered the repo inside commit `a1c5e9e` (the
  adr_0006 WP1 commit) via file-granularity bundling.
- **Shipped** (independent of acceptance): adr_0003 Wave 1 + the review
  fix pass — `protocol.md` defines `min(8, max-workers)` as the effective
  cap (batch size, not panel size; batches run in declaration order, gate
  holds, announced) and `loop rounds` as a ceiling (effective = lower of
  stored value and the run's resolved request; `limits.*` sit outside
  later-wins — a flag may lower a limit, never raise past the stored
  ceiling); announce block gained a `Limits:` line; `hex-review` tier
  files no longer hardcode 8. **Two follow-ups are Michael's, not hex's:**
  (1) `hex.md:28` still reads `loop rounds 1 (per-run --loop-rounds
  overrides)` — that parenthetical now contradicts the shipped ceiling
  rule, but `## Preferences` is user-owned (`protocol.md:527`), so hex
  never edits it (finding B1). (2) The installed `.claude/skills/` copies
  of the 4 edited shipped files are drifted from source until a `grim
  install` sync — this repo's own hex runs load the stale copies otherwise
  (finding W3: the sync step is undocumented). As of 2026-07-21 that drift
  covers **6** shipped files — the 4 above plus `hex-review/SKILL.md` and
  `hex-core/references/workers/reviewer.md` from the adr_0006 waves.
- The findings-severity contract (above, adr_0006) came from a design
  workflow (3 candidates → 3-lens judge → adversary, ship-with-fixes) and a
  two-reviewer verify pass; it is now written as adr_0006, Proposed. It
  defines the severity vocabulary hex already branches verdicts on but never
  defined, and — a latent-bug find in passing — `High` had **no verdict
  home** today (RCA processes Block/High but the Needs Work rule keyed only
  on Warn), plus the tier files carry a phantom `suggest` *disposition*
  (Suggest is a severity, not a class). adr_0006 fixes both.
- OpenSpec alignment research, 2026-07-20 (OpenSpec v1.6.0 clone read in
  full, plus get-shit-done and Spec Kitty):
  `research/openspec-framework-analysis.md`,
  `research/swarm-customization-and-config.md`,
  `research/spec-federation-multi-repo.md`. Expires 2027-01-31.
- Learned: hex's largest structural gap vs the SDD field is the absence of
  an **archive / fold-back** step — plans reach `done` and nothing folds
  their deltas into a durable spec. Not covered by adr_0003.
- Preference to propose at the next `/hex-init`: research axes of interest
  already cover registry ecosystems; add "agent-orchestration competitive
  landscape" — it carried the adr_0003 evidence.
