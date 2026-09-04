# hex — swarm memory

Maintained by the hex skills. Small by contract: pointers and
preferences, not copies. Team-shared — commit it.

## Pointers

- Verification: `CLAUDE.md` › "Verification" — `grim build <skill-dir>`
  per changed skill; Python under `nox/` is `task nox:verify` (selective:
  `task nox:test -- <nox-relative paths>`); full sweep
  `task publish -- --dry-run` **and** `task nox:verify`.
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
- Discussions home: `.agents/discussions/` (default convention,
  adr_0008 artifact class; owner `/hex-discuss`).
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

- **Plan done (no active plan):** `plans/plan_adr_0010_execution_performance.md`
  (State: **done**, tier high, executed 2026-08-30, **Approved round 3
  2026-08-31**, archived in place; fold target: none — no `## Spec
  Deltas` block) — implements
  adr_0010 (Accepted). Branch `hex/adr-0010-execution-performance`, tip
  `4415839`, base `6d8bba0`; all 6 WPs merged in order (285711b WP1
  protocol.md +460/−6 · 783e61d WP2 plan template/hex-plan · 04f8268 WP3
  execute+review qualifiers · 6b99067 WP4 audit item · d6da0f7 WP5
  DESIGN round 12 + ADR errata · 99297e0 WP6 0.4.0 release; ripple
  b13a2a8; adversary fix pass bd736d2). Full TDD cycle per WP
  (stub → verify-arch → worktree-local checklist → implement → budget
  review); WP1 panel Block traced to the ADR itself ("the run halts"
  contradicted C-913(b), 2 sites → erratum rows); 11 ADR erratum rows
  total; pinned Worktrees erratum-pointer re-pinned twice (v3 final).
  Codex adversary post-merge: 6 findings, 5 fixed in bd736d2 (landing
  guard both sites, trigger-list findability ¶ in § Verification
  preamble, tier-low anchored case + erratum, two-step anchor-validation
  order, ADR C-905 cell), 1 deferred (converged-pass paid-vs-owed not
  persisted). Deferred docket for review/owner: C-910 continuing-loop
  discriminator unevaluable; level-clear trigger dies after
  failure-with-dependents; checklist-style plans pay `full(degrade)`
  every merge (this plan's own class); memory.md Example lacks the two
  new pointer kinds; T5 checklist wording; glossary hybrid-row split;
  column-order reconstructability. Run executed under pre-adr_0010
  policy throughout (full grim build per merge — the plan's stated
  caveat). Dogfood docket + `.claude/skills` hex-* refresh chore still
  Michael's.
  **/hex-review round 1 (2026-08-30, tier medium artifact target,
  breadth=full + codex plan-artifact): Needs Work.** Convergence 27/29 —
  C-907 partial (protocol.md:286-289 ships the line-budget rationale
  erratum :1114 retracted, false vs template's file-scoped 20-line
  invariant) + C-916 partial (two hex-review write-set enumerations
  missing `Reviewed:` parity) → WP7 row appended, plan back to
  `executing`. 2 High (the C-907 rationale; codex: dogfood "Full-run
  count" equation double-counts coincident triggers — RHS structural
  counts not disjoint under the one-entry-first-token rule; shares root
  with the unbacked C-912 disambiguations), 6 Warn (CHANGELOG:22 outside
  ADR allowed-set; hex-execute/SKILL.md:508 fourth column-enumeration
  site w/o Verify; ADR/plan line-pins self-drifted → phrase anchors;
  tier-high/-medium "runs after every merge" base clause contradicts its
  own qualifier; template coordinator-parent Verify cell inert under
  trigger (i) — codex-confirmed; changelog silent on stranded-set
  approve-block), 5 Suggest actionable. All mechanical gates green
  (5 builds, dry-run, 13/13 anchors, round-12 byte-fidelity ×3 checks,
  DESIGN 5-hit prediction exact). Deferred: 12/19 contracts have no
  static check — dogfood run is the real release gate (owner call);
  C-902 example latitude; C-912 disambiguation erratum.
  **WP7 fix pass executed 2026-08-30 (`5e94bc8`, single Opus builder +
  light review PASS, one fix round):** all 14 docket items + item-5
  amendment (C-916 site-table pins) + 4 light-review follow-ups applied —
  both Highs closed (protocol.md placement rationale ordering-only;
  dogfood check 2 re-derived tag-partitioned, `≤` bounds + coverage
  half), `layer-clear`→`level-clear`, trigger-links retargeted to
  `#worktree-work-package-mechanics`, line-pins → phrase anchors both
  sides, 6 new ADR erratum rows. Convergence partials C-907/C-916
  closed; builds + dry-run green; round-12 fidelity intact.
  **/hex-review round 2 (2026-08-30, delta scope 1d529ec..c44ee8d,
  breadth=minimal fix-verification + codex delta): Needs Work.** All 18
  round-1 closures verified item-by-item, **Converged** (C-907/C-916
  delivered), gates green, sweep reconciles 9+2 hits exactly. 5
  actionable one-liners remain (1 Warn fix-pass-introduced: erratum
  `degrade =`→`≤`; 2 Warn in pre-existing WP5 erratum rows: "links
  C-912 rather than re-listing" imprecise — the merge-gate text defers,
  the C-912 home lists; stale `plan.md:203` pin now a mermaid node; 2
  plan-side: site-table pre-amendment-pins sentence, allowed-set parity
  WP5-checklist vs final-sweep). Deferred: check-2 opportunity-ceiling
  counting rule (write it FROM the dogfood run's evidence, not cold);
  hex.md layer-clear historical descriptor. Codex round-2 value: caught
  both pre-existing erratum-row inaccuracies; its 5th finding
  self-corrected (wrap-split example is DESIGN 849-850). Process note
  (2nd occurrence, adr_0009 precedent): one-line Warns force full
  review invocations — severity floor for fix-verification rounds
  still a design candidate. Plan back to `executing`.
  **Round-2 fix pass applied 2026-08-30 (inline, FX4 precedent):** all 5
  one-liners landed (ADR erratum-row `=`→`≤`, merge-gate narrowing,
  Merge-order phrase pin, site-table pre-`adr_0010` intro, WP5-checklist
  parity); no shipped file touched.
  **Round 3 (2026-08-31): Approve** — verify-only inline (5/5 closures
  grep-verified, delta docs-only, convergence stands from round 2, no
  shipped byte since last green gates). State: done, Next cleared,
  archived in place, Fold-Back not performed (no Spec Deltas block).
  Next (Michael's): land `hex/adr-0010-execution-performance` (tip
  `f31cbd1` + this terminal-state commit), dogfood docket (5 ADR
  checks incl. writing check-2's opportunity-ceiling rule from run
  evidence + forced anchor-fail-safe + slow-run attribution),
  `.claude/skills` hex-* refresh chore.
  **Landed + released 2026-08-31:** PR #1 merged (`40aa7a3`); release
  renumbered **0.2.0** (owner decision — 0.2.0/0.3.0 never published,
  0.1.1 last on GHCR; CHANGELOG sections consolidated into one
  `## [0.2.0]`, publish.toml 0.2.0, ADR erratum row records it); root
  README command table gained `/hex-discuss` + `/hex-finalize` (was
  5-command, pre-0.2.0-era); tagged `v0.2.0` → tag-driven publish CI.
- **adr_0010 ACCEPTED (Michael, 2026-08-30, at the /hex-plan gate — tier
  high, fast path from the ratified exec-performance dossier)**
  (`adrs/adr_0010_execution_performance.md`, 1076 lines, ADR only — owner
  dropped system-design at the gate; research=3 kept at tier baseline).
  Claims **C-901–C-919 / S-901–S-910 — next ADR takes C-10xx.** Scoped
  per-WP verification (WP contract tests via path-append convention +
  build gate; selective command augments, never replaces), full verify =
  three policy triggers (coordinator-owned-WP merge · dual-trigger
  checkpoint M=3/level-clear/high-risk-(Repo,path) · final gate) + two
  override paths (`Verify: full` cell, degrades); checkpoint failure
  auto-bisects over schedule-log SHAs (⌈log₂ M⌉ bound, non-empty
  attributed windows only); delta review rounds anchored `Reviewed:`
  (valid iff reachable-from-HEAD AND not-reachable-from-base — fail-open
  closed), full pass per C-907 scope at converged gate; C-911 oscillation
  stop (Block/High-floored, declared departure 4); failure cascade =
  derived strandedness, no fifth status; `Verify` column + presence-check
  compat (no schema version); DESIGN round-12 text drafted in-ADR incl.
  the live Plan-visualization column-lock amendment. Pipeline: explorer +
  3 axis researchers (`research/adr0010-{compat,operability,tooling}.md`,
  expire 2027-02-28) → Opus architect → panel (spec+adversarial-quality
  Opus + gap-check): 3 Block/13 High/14 Warn all fixed in 2 passes →
  codex adversary: 1 Block/4 High/2 Warn all real, all fixed (join-log
  equation, bisect bound 2-not-1, anchor fail-open, federated Status
  placement) → final spec validation PASS. Key learned: layer-clear
  trigger makes linear plans save 0% (plan shape is the second governing
  sensitivity); R=2 review loops are a net loss (win is cross-invocation
  only, D-1); C-306 merge-parallelism lever is federation-scoped and
  left unspent. 3 markers carried (slow-run phase attribution → dogfood;
  M cadence tuning; C-903 clause-1 vacuous until the C-917 Pointers row
  exists). Deferred: D-2 dependents' tests not run at merge (residual up
  to M−1 merges), flaky-failure single-rerun → future correctness-policy
  ADR, Review-column C-ID debt noted. Next (Michael's): accept adr_0010,
  then `/hex-plan "adr_0010 execution performance, per
  adrs/adr_0010_execution_performance.md"`.
- **Discussion drained 2026-08-30: "hex execution performance" → architect**
  (`discussions/hex-execution-performance.md`, `Ratified: 2026-08-30 →
  architect`). Mandate: adr_0010 (claims C-9xx) — scoped per-WP
  verification (WP contract tests + build per merge; full suite only at
  coordinator joins + periodic checkpoints + final gate;
  project-documented selective-test command as /hex-init convention),
  delta-scoped review-fix rounds (last-reviewed-SHA anchor in the plan
  Status block, full branch once at the converged gate), ready-set
  compliance hardening (recompute + log ready-set per merge — contract
  already ready-set, observed behavior waves), failure cascade =
  dependents block / siblings flow / stranded list, nesting capped at
  the existing depth-1 coordinators (flat table + computed rollups is a
  hard requirement; recursion ≥2 rejected by unanimous 3-seat blind
  council). Key evidence: no surveyed SDD tool runs the full suite per
  task; selective testing always pairs with a full-run backstop
  (TAP/Meta/Chromium); Cursor Bugbot reviews incremental-by-default and
  caps nesting at one level. 10 research artifacts
  `research/discuss-exec-perf-*.md` (expire 2027-02-28). 4 open markers
  carried (slow-run phase attribution — check installed-copy drift in
  the bigger repos first; checkpoint cadence M; ready-set logging
  shape; oscillation stop). ADR fast path: medium tier floor.
  Next: `/hex-architect .agents/discussions/hex-execution-performance.md`.
- **Plan done (no active plan):** `plans/plan_hex_discuss_ux_rework.md`
  (State: **done**, tier medium, archived in place 2026-08-30; fold
  target: none — no `## Spec Deltas` block) — **executed + reviewed to
  Approve** on `hex/discuss-ux-rework` (tip `5eab897`, base `f680fee`,
  unpushed, 9 commits; merge order WP2→WP1→WP3 held, then fix commits
  WP4 `961862e`, WP5 `a3b31ac`, `83309e4`, `5eab897`). Three /hex-review
  rounds: R1 Needs Work (1 High entry-path + 3 Warn), R2 Needs Work
  (ADR/DESIGN drift + dispatch-keyed once-rule + 4 Warn), R3 **Approve**
  (Converged 23/23; gates wp1 51/51 · wp2 48/48 · wp3 31/31 · grim 0 ·
  dry-run 0; body 399/400). Codex caught real gaps every round
  (entry-path ambiguity, park-before-slot-1 resume, lane-menu timing
  residue). Learned: a fix pass that changes shipped entry behavior must
  re-touch the same round's ADR/DESIGN amendments (WP3 predated WP4 →
  R2's two High). Next (Michael's): land the branch, dogfood run per the
  plan's Step 5.3 docket, 0.3.0 publish. — hex-discuss interactive
  rework per the drained hex-discuss-ux dossier. 3 WPs / 2 waves: WP1
  SKILL.md rewrite ∥ WP2 new `references/research-lanes.md`, then WP3
  adr_0008 amendments (10 stale sites, C-701 split budget) + DESIGN.md
  full new round (re-argues round-9 deviation-1 premise; spend threshold:
  automatic ≤ default gear, announced). Panel (spec+architect Opus+
  researcher): 3 Block/7 High all fixed; codex adversary 5/5 actionable
  fixed; final validation PASS. **Council lane in-plan (Michael,
  2026-08-30), reframed as perspective council**: N same-class researcher
  seats with assigned perspectives, blind to each other, orchestrator-side
  synthesis, no ranking (moots self-preference bias); C-706 opinion
  exception lexically scoped to opt-in lanes; cross-model seats → future
  ADR. Zero open markers.
  Next: `/hex-execute plans/plan_hex_discuss_ux_rework.md`.
- **Discussion drained 2026-08-30: "hex-discuss UX" → plan**
  (`discussions/hex-discuss-ux.md`, `Ratified: 2026-08-30 → plan`).
  Mandate: rework `hex/hex-discuss` interactive/answer-first — automatic
  fixed-2 entry recon wave; user-only drain (no unprompted offers;
  restate + terminal summary stay); leads-fed multi-select research
  lanes replace the quick/deep two-gear (gone entirely, cap 12 holds);
  design questions batched ≤3 w/ recommendations; new `references/`
  spawn contract (`negative:`/`leads:` return schema, blindness incl.
  entry wave); results feed questions at turn boundaries; opt-in council
  lane (karpathy/llm-council pattern; degraded single-provider). Ships
  as skill edits + adr_0008 in-place amendments (C-7xx; § Validation
  re-derivation is a hard deliverable). 3 research artifacts
  `research/discuss-ux-{sota,community,adjacent}.md` (expire
  2027-02-28). Zero open questions carried.
- **Plan done (no active plan):** `plans/plan_adr_0009_finalize_phase.md`
  (State: **done**, tier high, archived in place 2026-08-30 per C-410;
  fold target: none — plan carries no `## Spec Deltas` block) —
  implement `/hex-finalize` per adr_0009. **Execution complete**: all 7 WPs merged on
  `hex/adr-0009-finalize` (tip `5e3ea3d`, base local `main` = `71aa5c2`,
  unpushed; 19 files, +1566/−28); merge order WP2→WP1→WP5→WP6→WP3→WP4→WP7
  held; every WP reviewed per its budget (WP1/WP2 panel, WP3 light+security,
  WP4/5/6 light-or-self, WP7 light PASS), all severities applied; builds ×7
  + `task publish -- --dry-run` green post-close. Implementation errata
  folded into the ADR: WP2 panel (E1 lease/ancestry, E2 re-entry gate, E3
  never-list), WP3 (exemption clause), WP7 sweep (V12 stale grep), adversary
  round (C-809 rename-refusal exit, C-802 PR-base-mismatch hard stop, C-812
  quoted interpolation). 40-item validation mapping: 7 mechanical, 33 on the
  plan's Dogfood docket (§ Deferred). **/hex-review 2026-08-29 (tier
  medium, artifact target, breadth=full + codex plan-artifact): Request
  Changes** — Converged 41/41, but 1 Block (README quickstart order),
  6 High (quoting-rule scope, forged sign-off trailer provenance,
  arming-refusal silent circle, gate-flag key, hex-init restatement,
  C-807/808 definition sites), 10 Warn. **Fix pass FX1–FX3 merged
  2026-08-30** (tip `80111ec`): all 18 actionable findings applied —
  FX1 finalize.md (quoting rule → § Scope, arming-refusal loud exit,
  gate-flag keyed (branch, pushed SHA), dispatch-guard scoped to own
  workflow_dispatch runs), FX2 hex-finalize (trailer-provenance rule:
  no trailer copied from branch messages; **C-807.**/**C-808.**
  definition tags; full resume Never: line; "pre-gate" carve-out
  dropped), FX3 (quickstart order, keywords, series-shape link);
  5 ADR contract errata + plan docket V32/V37/V40 tightened; sweep
  green; body 399 ≤400. Deferred (owner): gate-render weight,
  ident-field classification, local-only × RESUME_PUBLISHED shape,
  archive.md revert sentence.
  **Round 2 (2026-08-30): Needs Work** — 17/18 fixed verified, 2 Warn
  (stale index label; nine-item enumerations missing the tenth) →
  **FX4 `92742dd`** closed both (direct commit, f1dc369 precedent);
  zero "never-push qualifier" bundle-wide, sweep green. Tip `92742dd`.
  **Round 3 (2026-08-30): Approve** — fix-verification scope (inline,
  owner-approved minimal pass): stale label 0/0, tenth rule 1/1 in both
  enumerations (wrap-tolerant), `grim build hex/hex-core` green,
  Converged (all 11 table rows merged), Fold-Back not performed (no
  Spec Deltas block). State: done, Next cleared, archived in place.
  **Dogfooded 2026-08-30: `/hex-finalize` ran on this very branch**
  (local-only by owner directive — no push, no dispatch, no PR):
  26 commits → 3 signed (`38dec67` feat, `6fffd85` docs, `b660620`
  chore dev-sync), tree byte-identical, author-set equal, verification
  exit 0 pre-rewrite (base unmoved, no re-run), gate approved; backup
  `backup/hex/adr-0009-finalize-cbd2aa2` (inert — pruning is
  Michael's, post-merge). Run observations: fetched `origin/main`
  `ef566de5` is 4 behind local `main` `71aa5c2` (unpushed adr_0008
  land) — contract-literal fetched-target base would conflate landed
  trunk work into the series (docket-relevant); virgin branch = no
  lease pin, eventual publish is a plain first push.
  Next (Michael's): push `main`, push the branch, 0.3.0 publish,
  V40's docket mapping from this run. Process note for next design
  round: no verify-only re-entry — two one-line Warns forced a full
  review invocation to flip Approve; severity floor for
  fix-verification rounds is a candidate.
- **adr_0009 ACCEPTED (Michael, 2026-08-29, at the /hex-plan gate)** (`adrs/adr_0009_finalize_phase.md`,
  1059 lines + `adrs/adr_0009_system_design.md`, 764 lines) — `/hex-finalize`
  branch-finalization mode, from the ratified finalize-phase dossier
  (fast path, tier high). Claims **C-801–828 / S-801–813 — next ADR takes
  C-9xx.** Recommended: one command, five phases, hex's single gate
  relocated to the local/remote seam (commit list + sign-offs disclosed
  pre-push); remote acts scoped to feature branch + PR; ambient forge CLI
  disclosed at gate; four-rung degrade ladder ends local-only. Key
  contracts: authoritative-only resolver for target/merge-strategy/
  workflow-list (checked-in text narrows, never widens); armed/inert
  backup-ref lifecycle = the lock + its release; recompose =
  `rebase --onto` → `reset --soft` → staged re-commit with message-diff +
  author-set halts; forge-conditional dispatch (GitHub per workflow,
  GitLab per SHA); auto-merge armed → no flip (S-813). Amends in the open:
  C-718 cap ≤14 physical lines; 4 bundle-wide never-push sites via 17-row
  site table; third meta-plan-gate exemption; echo rule promoted to
  protocol.md; C-826 audit item has zero forge reads. Pipeline: explorer +
  3 axis researchers (adr0009-{remote-rights,failure-modes,hex-compat}.md,
  expire 2027-02-28) → Opus architect → 4-seat panel (5 Block/23 High —
  all fixed, 3 rounds) → codex (6 findings, High-1 a real defect:
  re-signing makes recompose SHA-unstable, false no-op resume deleted) →
  final spec validation PASS. **Both markers resolved by Michael
  2026-08-29 (zero remain):** series-shape default = minimal bisectable
  series behind a 3-step resolution order (project docs → `hex.md ›
  Preferences` prose hint via /hex-init, never a key → shipped default;
  gate names which step resolved); rerun ceiling = exactly one, failed
  jobs only, per SHA. C-825 narrowed "zero config surface" → "zero config
  *key*". Acknowledged limits (deferred, human judgment): act set is
  prompt text — real backstops are target-branch protection + harness
  allowlist; virgin-satellite hole narrowed not closed; backup-ref
  accumulation cleanup is the human's. Research-axis note for next
  /hex-init: "agent-held remote rights / CI supply-chain security"
  carried the decisive evidence.
- **Discussion drained 2026-08-29: "finalize phase" → architect**
  (`discussions/finalize-phase.md`, `Ratified: 2026-08-29 → architect`).
  Mandate: adr_0009 (claims C-8xx) for a new `/hex-finalize` command —
  rebase onto target + recompose the feature branch into changelog-worthy
  commits (3 OSS universals baked in, 2 shape axes team-discovered),
  DCO/sign-off satisfied during rewrite, strictest documented verification
  triggered post-rewrite on final SHAs via forge CLI (gh/glab),
  force-push consented by invocation (feature branch + PR only, merge
  stays human), draft→ready flip. Workspace invariant: primary checkout =
  the PR branch. 9 research artifacts
  `research/discuss-finalize-*.md` (expire 2027-02-28). 4 open-question
  markers carried in the artifact (backup ref/range-diff, quality-ledger
  home, changelog generation out, PR-mutation rights).
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
- **Discussion handed off 2026-08-31 → architect:**
  `discussions/nox-multi-harness-adversary.md` (State: `handed-off →
  architect`, Ratified 2026-08-31). **nox** — a multi-harness adversarial
  review tool generalising `openai/codex-plugin-cc` beyond its single
  Claude-Code→Codex direction. Settled: own repository (not arcana — a
  uv/ruff/pyright/pytest project does not belong in a pure-markdown
  grimoire), modelled on `ocx-sdk-python`; zero runtime dependencies;
  shipped as a CI-built `zipapp` `.pyz` script asset inside a grim skill
  that lives in the same repo (one tag, one version — this dissolves the
  publish-then-bump-the-pin coupling); auth via the user's own installed,
  logged-in harness CLIs; read-only against the shared working tree, no
  worktree or container; full N×N review directions, owner's call.
  **hex needs no changes** — its `adversary: <skill-name>` seam
  (`hex-core/references/protocol.md:1210`) is already vendor-neutral and nox
  is simply a valid value. Carried to the ADR: v1 harness scope
  (recommended Codex + Claude Code shipping, Copilot + Cursor as documented
  adapter contracts — `cursor-agent` is not installed here and its flags are
  unverified); the arXiv:2607.21656 asymmetry result (Codex reviewing Claude
  *lowered* pass rate 91.4%→82.8%) as a documented risk, not a gate; ToS
  exposure from Anthropic's Jan 2026 enforcement; Python becoming arcana's
  first executable-asset precedent.
- **Research 2026-08-31 (nox discussion):**
  `research/discuss-nox-priorart.md` — headless flag/output surfaces for
  Claude Code, Codex, Copilot and Cursor, plus cross-model-review evidence
  and failure modes. `research/discuss-nox-vendor.md` — multi-model review
  across Amp/Aider/Copilot/Cursor/Devin, vendor ToS on programmatic driving,
  isolation and metering. Both expire 2027-02-28 — headless CLI surfaces
  churn release-to-release and none are versioned public APIs.
- Learned: `grim` installs `scripts/` and `assets/` verbatim per client and
  re-renders only `SKILL.md`, **but explicitly does not guarantee a stable
  on-disk path across clients** (`grim-usage/references/consume.md:239`).
  A skill shelling to a *sibling* skill's script by relative path is
  therefore unsafe — the `hex-core` markdown-link precedent does not extend
  to executable assets. Any shared script must live in the skill that runs
  it.
- **Plan done (no active plan):** `plans/plan_adr_0011_nox_adversary.md`
  (State: **done**, tier high, executed 2026-09-02…09-04, archived in place;
  fold target: none — no `## Spec Deltas` block. **17 WPs merged**, 3
  `/hex-review` turns at tier high (rounds 1/2/3 each Needs Work → WP13, WP15,
  WP17 convergence-gap packages; the round-3 cross-model gate came back clean),
  plus WP14/WP16 owner-ruling and diagnosability packages. Errata **E1–E70**,
  contracts C-1001–C-1044, decisions D-a–D-ad. Gates at the tip: `task
  nox:verify` exit 0 with **100%** branch coverage (2652 stmts / 558 branches,
  pragma budget 1), 3.11 floor and 3.14 leg green, `task nox:test:contract`
  91/0 live against claude 2.1.260 · codex 0.144.1 · copilot 1.0.82 ·
  opencode 1.18.22, `task nox:manual:matrix` **16/16** live 4×4, `task publish
  -- --dry-run` exit 0 at 0.3.0. Finalized 2026-09-04 — 167 commits recomposed
  to 9, branch `hex/adr-0011-nox-adversary` force-pushed, backup ref
  `backup/hex/adr-0011-nox-adversary-440100a`,
  [PR #2](https://github.com/michael-herwig/arcana/pull/2) ready. **Next
  (Michael's): merge PR #2, then cut `v0.3.0`** — the tag publishes hex and nox
  together (D-aa), and the release needs a one-time hand-flip of the nox GHCR
  package to public. (The signed-tag gate that also wanted
  `NOX_RELEASE_ALLOWED_SIGNERS` was removed on the owner's ruling — plan E72.)
  Superseded pre-execution detail follows.) Originally recorded as: State
  **plan-approved**, 2026-09-02; **single repo — nox lives at
  `nox/` beside `hex/`** by owner decision after the first handoff,
  superseding the ADR's separate repository (plan D-aa/E13; the federated
  shape was fully planned, reviewed, then withdrawn — adr_0004's first
  dogfood is deferred); slug `hex/adr-0011-nox-adversary`). Implements
  adr_0011 (**Accepted by Michael 2026-09-02 at the `/hex-plan` gate**;
  gate decisions: local release gate — arcana's `task release:prepare`
  gains `nox:release-gate` (real-binary suites on the owner's machine),
  `publish.yml` verifies the signed tag and the `.pyz` digest before
  publishing both bundles on one `v*` tag; C-1033's audit item ships as
  WP9). Verification for nox: `task nox:verify` (root `Taskfile.yml`
  include — WP1 documents it in `CLAUDE.md` › Verification; re-point the
  Verification pointer above when it lands).
  43 contracts (C-1001–C-1033 carried; C-1034–C-1037 per the ADR's
  Deferred delegation; C-1038–C-1043 plan-authored), 14 scenarios, 12
  errata/spelled points, 12 WPs / 6 waves (WP9 arcana audit item ∥ WP1
  scaffold+leaf types → WP2 workspace spike ∥ WP3 runner ∥ WP4 config ∥ WP5
  prompt → WP6 harness → WP7a/b/c adapters ∥ WP8 api/cli → WP10 skill+
  release → WP11 assembly proof); critical path WP1→WP2→WP6→WP7b→WP10→
  WP11; shippable after wave 5; merge order WP9 first. Pipeline: 4
  discover + 3 researchers (`research/plan0011-{tooling,patterns,domain}.md`;
  domain expires 2026-11-30) → Opus architect brief (found two import
  cycles in the ADR's module assignment → E9a) → 3-seat panel (spec 2
  Block/7 High; architect 1 Block/7 High; gap 1 High refuted by a live
  opencode probe) → one fix pass → revalidation **Approve** (46 fixed) →
  `codex:rescue` plan-artifact pass **2 Block / 12 High / 3 Warn, all
  actionable, all applied** (unpinned synthetic commits in the gc window →
  `refs/nox/<token>/*`; escaping symlinks → C-1043 by-mode drop; probe
  attempt evidence; checkout→key→verify-tag order; digest in the signed tag
  message; skill path portability) → final spec validation **Approve**
  (join 57/57 both sides; its 7 Warn one-liners applied inline afterwards,
  no further round — loop cap). Owner ratification requested: D-j
  POSIX-only v1, D-i `next_steps` kept with no `Review` home. Zero markers. Live probes this run: `codex exec review`
  flag set identical at 0.144.1 and 0.152.1; opencode 1.18.22 via the ocx
  launcher has `providers list` (alias `auth`), `--variant`, `--pure`,
  and an **empty credential store** (R10 — owner runs `opencode providers
  login`). Reshape review (Opus, narrow): 1 Block / 6 High / 5 Warn on the
  release path, all applied inline (manifest `version`, tag-only guard on
  the `publish.yml` chain, `setup-task`, `gpg.ssh.allowedSignersFile`,
  documented selective command `task nox:test -- <nox-relative paths>`,
  skill name in the `<skill-dir>` fallback, commit-the-working-set
  precondition). Its pre-execution "Next" — commit the untracked set, ratify
  D-aa/D-j/D-i, user-level `nox.toml` + `opencode providers login`, then
  `/hex-execute` — is **discharged**; the live one is the merge-and-tag line
  at the top of this entry.
- **ADR 0011 designed 2026-09-02, Accepted 2026-09-02 (at the `/hex-plan` gate):**
  `adrs/adr_0011_nox_multi_harness_adversary.md` (contracts C-1001–C-1033;
  **0 open markers** — all three resolved by the owner 2026-09-02: Python
  runtime accepted, `nox` kept with the PyPI channel removed entirely,
  instruction files deleted with the neutralization set) + `adrs/adr_0011_system_design.md`
  (1400 lines, C4 ×4, threat model T1–T6, per-adapter failure matrix
  §7.1a). Input: dossier `discussions/nox-multi-harness-adversary.md`
  (fast path; tier **high** — one-way-door, external contract, novel,
  security touch; dossier floor inert). **Decision:** Option C — every
  harness reviews from an ephemeral git worktree checked out from
  **synthetic commits** in which repo-supplied harness config
  (`.claude/`, `.mcp.json`, `.opencode/`, `opencode.json`, `.codex/`,
  `AGENTS.md`, `CLAUDE.md`, `.gitattributes`, `.gitmodules`, every mode-
  `160000` gitlink; matched by path component at any depth, any entry
  mode) is filtered at the git-object level on both base and target —
  never `rm`'d on disk, absent from every diff any harness computes.
  Reverses the dossier's ratified "no worktree" on security-lane evidence
  (a hostile *branch* poisons the harness's own config in-tree; `-p`
  disables Claude Code trust verification; OpenCode auto-loads
  `.opencode/plugins/` with no off-switch). v1 = Claude Code + OpenCode +
  Codex (owner mandate, non-negotiable). Passthrough is a per-adapter
  **allowlist** (`PASSTHROUGH_ALLOW`); containment stamp derived from
  final argv + digest-keyed probe (C-1025); model by capability class per
  adr_0001, mapped per adapter, typed `{model, effort}` never argv
  (C-1030); child-git config boundary via `GIT_CONFIG_*` env (C-1031);
  real-binary contract tests release-blocking, absent binary blocks not
  skips (C-1032). Codex transport is `codex exec review` with a
  `refs/nox/base/<token>` temp ref as primary — app-server deferred
  (C-1024). Matrix C 96 / B 77 / D 73 / A 66; B overtakes C only when
  `w(C3)+2·w(C7) > 26` (today 7).
  **Review:** 3-reviewer panel (spec/quality/security, Opus) + SOTA gap
  check → 10 Blocks, all closed; revalidation ×2 (owner authorized one
  narrow pass past the artifact-loop cap); `codex:rescue` cross-model
  pass → 2 Block / 4 High / 2 Warn, all 8 closed, final spec revalidation
  clean. Cross-model pass found what the same-family panel missed:
  `.gitattributes` filter execution at checkout and submodule escape.
  **Deferred to /hex-plan** (ADR "Deferred" table): env-key handling
  (`ANTHROPIC_API_KEY`, `PATH`), selection-time warning on the measured-
  negative direction, severity mapping table, CI as a consumer under
  subscription auth, explicit decision scenarios for the matrix. Trivia
  open: C-1032 credits "C-1031's CI job" (cross-ref typo).
  **Unverified, labelled as such in the ADR:** no harness review was ever
  executed; Codex sandbox scope and auth/quota event shapes unobserved;
  OpenCode security claims from docs only (binary not installed; runnable
  via `ocx package exec ocx.sh/anomalyco/opencode:1.18.22 -- <cmd>`).
- **Research 2026-08-31/09-02 (adr_0011):** `research/nox-security.md`
  (two addenda; Expires 2026-11-30 — Codex pre-1.0),
  `research/nox-tech-tooling.md`, `research/nox-pattern-precedent.md`
  (Expires 2027-02-28). `research/discuss-nox-priorart.md:87` — the
  arXiv:2606.19544 18%/39% figure is **retracted** (paper fetched; figure
  absent). arXiv:2607.21656 now accepted at Agentic SE @ KDD'26, still
  unreplicated.
- Preference to propose at the next `/hex-init`: research axis of
  interest **security & compliance** — on adr_0011 it was the decisive
  axis (surfaced the repo-config-poisoning class that overturned a
  ratified decision) and the one whose escalation to deep-reasoning paid
  for itself.
- Learned: at plan-artifact scope the cross-model adversary should be
  aimed explicitly at **mechanisms the native design does not name**
  (here: git internals outside the path matcher). Three same-family Opus
  reviewers plus two revalidations converged on the same blind spot.
  Confirmed again on the plan (2026-09-02): aimed at git internals,
  signals, and release mechanics, Codex found the gc window between
  `commit-tree` and `worktree add` and the out-of-tree symlink escape —
  both invisible to a panel reading the plan's own vocabulary.
- Learned: CLI-surface claims for Codex/OpenCode must be verified against
  `--help` of the pinned binary, never against docs or AI summaries — the
  gap seat's one High (`opencode providers list` "does not exist") came
  from docs and was refuted by running the binary through the launcher.
  The launcher form is `ocx package exec <coord> -- opencode …` (the
  executable name follows the `--`).
- Promotion candidate for the next `/hex-init` re-audit (adr_0011 C-1033):
  add audit item **"Cross-model adversary skill installed?"** to
  `hex/hex-init/references/audit.md` — scan installed `SKILL.md`s for the
  plain metadata key `hex-adversary-scopes`; when found and `Preferences`
  has no live `adversary:` pin, propose `adversary: <skill-name>` with
  consent; silent otherwise. nox and hex stay independent — either runs
  alone; the item only proposes, never pins.
