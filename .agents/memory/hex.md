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
  `.claude/skills` hex-* refresh chore, 0.4.0 publish.
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
