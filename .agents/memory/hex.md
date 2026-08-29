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

- **adr_0008 ACCEPTED (Michael, 2026-08-28; plain approval — all three
  open-question recommendations stand: sweep cap 12, discussions home =
  documented convention else `.agents/discussions/`, rule `hex-state` ships
  v0.2.0 with the skill). Rule generalized at review to bundle-generic
  `hex-state` (one always-on artifact, one line per shipped mode).**
  - **Landed plan (no active plan):** `plans/plan_adr_0008_discussion_mode.md`
    (State: **done**; ff-landed on main 2026-08-29 as `2aa16fa` feat +
    2 chores, owner skipped review round 4 — 3 rounds converged). All 5 WPs merged on
    branch **`hex/adr-0008-discussion-mode`** (9 commits `8f131bd`→
    `a1acfc9` off `ef566de`; merge order WP2→WP3→WP5→WP1→WP4 held).
    Full TDD cycle per WP (stub → post-stub spec+architect → checklist
    tester → implement → review); panels found 2 re-stubs (WP3, WP5) +
    fix passes on every panel WP; codex one-shot on the branch diff
    found 3 High + 1 Warn (all fixed: `<home>` interpolation in
    hex-init's recorded row; canonical-path read; shape-based
    `Ratified:` corroboration; re-point named at the restate).
    `task publish -- --dry-run` green at 0.2.0 (skill + rule + bundle).
    Learned: rule catalog check pre-publish = `grim build <rule>
    --format json` → `annotation_count` 8 (top-level) vs 5 (nested);
    skill `description` YAML rejects unquoted colon-space.
    Reviewed 2026-08-29 (`/hex-review`, tier high, 8-worker panel +
    codex one-shot): Request Changes — convergence 46/47 (C-723(a)
    partial → WP6 row). Fix pass executed same day (WP7–WP11, all
    findings incl. deferred Warn/Suggest per Michael's gate adjust):
    branch now 18 commits `8f131bd`→`6eb48e5`; ADR amended in place
    (changelog rows, § Validation +7, § Migration rollback sites);
    reviewers caught + fixed a template-seed freeze (template ships
    `State: parked`) and a restate-compression consent regression.
    Dry-run green at 0.2.0; `grimoire.toml` now lists both members.
    Learned: hex-discuss body pinned at exactly 400 (C-701 ceiling —
    next line forces the references/ split); RTK mangles `git diff
    --name-only` too (use `rtk proxy`).
    **Michael's 4 High decisions RESOLVED 2026-08-29** (all four
    recommendations accepted, applied as WP12 commit `87f7e04`,
    absorbing WP6): C-718 gains the in-rule stale-`active` release
    clause; `handed-off → context` is the fifth terminal state
    (C-711/C-714 + 4 shipped sites); C-723(a) marker route ratified
    (both stale Validation bullets corrected); C-722 dropped-Fix
    reworded to truth. Zero open deferred findings.
    **Re-reviewed 2026-08-29 (round 2, tier high, 8-worker panel + codex):
    Request Changes.** Convergence 42/47 — 5 partial (C-701 zero-headroom
    body, C-707 truncation clause, C-708/C-714 `Confidence:` drift, C-722
    Error literal) → WP13/WP14 rows appended, plan back to `executing`.
    Codex confirmed 1 High the panels missed: resuming a `parked`
    discussion never re-arms `State: active`, so the hex-state freeze
    silently lapses mid-discussion. RCA: 4 of 5 roots are RECURRENCES of
    round-1 roots (no ADR write-back channel; trust rules scoped to the
    motivating site; freeze over-firing unanalysed — now incl. the
    committed-artifact multi-clone case, owner call; no new-member
    structural checklist) + 1 new (ADR § Validation never re-derived
    after the fix passes — 16 stale/missing items).
    **Round-2 fix pass executed 2026-08-29 (WP15–WP18, all severities;
    owner gate decisions: session-bound freeze predicate accepted, full
    ADR batch authorized, hook backstop deferred, all findings).** Branch
    tip **`c6dfa02`** (WP15 `120b1ef` hex-discuss body 392/400 +
    references/reach.md split; WP16 `5276fcf` architect trust-boundary
    generalizations incl. header-anchored State extraction; WP17
    `f0eea25` session-bound rule predicate + release surface). ADR:
    +11 owner-attributed changelog rows, § Validation 21→29 items,
    C-721 retargeted to references/reach.md (7 sites), S-710/C-719
    recovery text corrected. Reviewers: WP16 FAILed once (unmatchable
    C-724 Domain-predicate → Triggered-by/topic match; echo list widened
    to <anchor>/<date>; extraction anchored) — all fixed in-round; WP15/
    17/18 PASS. Convergence WP13/WP14 closed. Dry-run exit 0 at 0.2.0.
    Owner note 2026-08-29: hooks will be enabled in the future — the
    hex-state hardening backstop should then become a REAL
    init-provisioned hook (deferred from this release; research already
    scoped it in discuss-mode-mechanics.md).
    **Round-3 focused review 2026-08-29 (owner-adjusted breadth): Needs
    Work.** Convergence **all 47** (five round-2 partials closed with
    evidence); merges intact, DESIGN round 9 byte-locked, dry-run green.
    Owner instructed committing all open changes onto the branch:
    `54756a3` (ADR/plan/dossier/13 research) + `3a247e8` (.serena,
    hex.png). 4 actionable remain: C-724 header-coupling (research
    template names `Triggered by:`/`Domain:` but 0/13 real artifacts
    carry them — producer side never points at the template; skip
    rarely fires, fails safe); echo-list misses `<canonical>`+`<topic>`;
    hex-discuss:44 "which is why" antecedent backwards; CHANGELOG:13
    "trusted input" inverts the hardening story. Deferred: unrequested
    riders in the docs commits (parity-oracle-gate.md, .serena/,
    unreferenced hex.png — logo is assets/hex.svg); grim describe check
    is post-publish-only; 29 § Validation items await the dogfood run.
    **Round-3 fix pass executed 2026-08-29 (WP19, single Opus builder +
    light review, PASS + 2 nits folded in-round):** C-724 title-line-
    primary predicate + producer header-contract pointer (single home =
    research.md title line + § Metadata; real counts recorded: 21
    artifacts, 3 with `Triggered by:`); echo list now 7 placeholders
    (+`<canonical>`, `<topic>`, sweep-verified complete); hex-discuss:44
    antecedent restored; CHANGELOG:13 trust wording truthful. Merged as
    WP19 `172d052` → merge tip; body 397/400; builds + dry-run exit 0.
    All 19 WPs merged. ADR restatement-relation (not byte-quote) for
    C-724 is the established norm — reviewer confirmed round-2 pair
    diverged identically.
    **History rewritten 2026-08-29 (owner instruction):** the branch's
    32 scaffolding commits (fix passes, review bookkeeping, merges)
    recomposed as 3 conventional commits — feat(hex) pre-plan discussion
    mode / docs(adr_0008) / chore(riders) — tree byte-identical to the
    old tip; backup ref `backup/adr-0008-round-history`. Owner idea for
    later (/hex-discuss candidate): a hex **finalize** phase that does
    this at landing — only changelog-worthy commits leave the branch;
    fixes to a feature being introduced on the same branch never land
    as separate commits.
    Next: Michael reviews commits + lands (no further review round —
    3 rounds converged, yield collapsed);
    **W3 RESOLVED 2026-08-29: Michael ran the grim install dev-sync**
    (.claude/skills + .claude/rules synced — hex-discuss + hex-state
    live; grim 0.13.0 regenerated grimoire.lock). Dogfood run unblocked.
  `adrs/adr_0008_pre_plan_discussion_mode.md` — pre-plan discussion mode
  (hex-discuss skill + `.agents/discussions/` artifact class + the bundle's
  first rule artifact + a trust-scoped hex-architect fast path). Tier-high
  run, dogfooding its own design: input dossier
  `discussions/hex-discuss-skill.md` (State handed-off → architect,
  Ratified). Claims C-701–731 / S-701–716 — **next ADR takes C-8xx**.
  Pipeline: explorer + 4 researchers → Opus architect → 3-reviewer panel
  (2 Block + 16 High, all fixed) → re-validation → codex adversary
  (7 findings, all actionable, fixed + validated). Research persisted
  (Expires 2027-02-28): discuss-{anthropic,openai,github,practitioners,
  vendors,skills-field,mode-mechanics,grill-mechanics,competitive-delta}.md,
  rule-{artifacts-grim,context-budgets}.md, dossier-fastpath-precedent.md.
  **Michael's:** accept/reject adr_0008; 3 open questions carry
  recommendations in the ADR; deferred — non-Claude skill-body durability
  untested (ship-on-assumption vs dogfood one non-Claude client first), and
  whether `grim update` removes a rule file when a bundle drops the member
  (affects rollback). Preference to propose at next `/hex-init`: research
  axis "AI-config packaging & distribution (grim, rules, hooks)".
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
