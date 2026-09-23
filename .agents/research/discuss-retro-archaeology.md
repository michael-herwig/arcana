# Research: this repo's history of "run experience → skill/config change" mechanisms

## Metadata

**Date:** 2026-09-23
**Domain:** cli (hex skill bundle, git archaeology)
**Triggered by:** proposed friction-capture + `retro` skill — deciding whether
to extend the Upkeep step or build a separate capture channel
**Expires:** 2026-12 (re-verify after any further ADR touches Upkeep, Memory,
or hex-init audit)

## Direct Answer

The Upkeep step and the Memory/Preferences split are **original design**, not
an evolved mechanism — both are present at the very first hex commits
(`a4aaa34`/`3745eac`/`0b5019e`, "initial hex skill"/baseline), so there is no
"why it was introduced" commit message to cite beyond the baseline itself.
The mechanism has been used exactly **once**, real, end to end: `5ff3441`
"docs(hex): record plan_hex_loop with its dogfood evidence" added the only
"Review perspective that mattered" entry that exists in `.agents/memory/hex.md`
today (line 53, hex-loop dogfood). It was written **2026-09-23 (today)** and
has not yet had a `/hex-init` re-audit run to pick it up — so the promotion
half of the loop (candidate → `review.<level>.*` key or checklist line) has
**zero realized instances** in this repo's history, only the machinery for it
(`adr_0016`, `fd243e9`). None of `.agents/handover_dogfood_findings.md`'s 12
findings (F-001..F-012, all dated 2026-09-19, still git-untracked) have
produced a matching commit anywhere in `hex/` — grepped for their specific
fixes (fd eviction on `flock`, Monitor+poll rule, print-matches-not-count,
`.tmp/<wp>/` evidence home, exit-127/E2BIG handling, ack channel, mutation
per-edit hashing) and got zero hits. Nothing about Upkeep or Memory has ever
been reverted or narrowed; `adr_0014`'s instruction-diet split (in flight)
keeps the Upkeep step in the always-loaded spine rather than moving it to a
prunable per-topic sibling.

## Key findings

1. **Origin.** `git log --all --oneline -S "Upkeep" -- protocol.md` bottoms
   out at `a4aaa34`/`3745eac`/`0b5019e` — all three are "initial hex
   skill"/baseline commits, i.e. the Upkeep step shipped with hex's first
   version, no separate introduction. Same for `hex.md › Preferences`
   (`git log -S "› Preferences" -- memory.md` → same three baseline commits).
   `hex/hex-core/references/protocol.md:840-862` is the current text.

2. **The "three candidate classes" refinement (closest thing to a real
   introduction event) is `adr_0016`, commit `fd243e9` "feat(hex): parallel
   adversary, review checklist, reviewer config (adr_0016)"** —
   `.agents/adrs/adr_0016_parallel_adversary_review_checklist.md`, cited
   inline as `adr_0016` C-990 in `protocol.md:855`. This is what gives Upkeep
   its structured shape (hint / `review.<level>.*` / checklist-item), not the
   baseline commit.

3. **Realized-use count in `.agents/memory/hex.md` (925 lines, 30 commits
   touched it across history).** Of the file's ~27 bold top-level Memory
   entries, exactly **1** is a "Review perspective that mattered" (class-1
   candidate) entry: line 53, added by `5ff3441`. Zero entries match the
   documented shape of a class-2 (`review.<level>.*` budget/residue/round
   candidate) or class-3 (recurring finding → checklist item) candidate —
   `grep` for "budget expiry", "residue line", "round count", "finding class
   that recurred" inside `hex.md` returns only the *definitional* prose in
   `hex/hex-init/references/audit.md:281-283`, not a lived instance.

4. **hex-init's consumption side (`### Review settings tuned?`,
   `hex/hex-init/references/audit.md:269-287`) has never fired on real
   material** — its "de facto discovery" clause reads a Memory candidate that,
   per finding 3, has existed in this repo for less than a day and has not yet
   had a `/hex-init` re-audit pass. The audit item itself was added in
   `8c322b0` "feat(hex-init): three audit items, three wizard bullets, the
   phase list" (pre-`fd243e9`, so the item predates the class vocabulary it
   now cites — it was generalized in place, not created fresh, when
   `adr_0016` landed).

5. **F-series (`.agents/handover_dogfood_findings.md`, git-untracked, 12
   entries, all from a 2026-09-19 run on a different repo, "ocx crate
   split") → zero matching commits in `hex/`.** Checked each finding's
   specific proposed fix against the shipped skill text:
   - F-001 (`flock`+`sccache` fd inheritance, non-participant-holder
     eviction): no `fuser`/eviction text anywhere in `hex/`.
   - F-002 (Monitor armed ≠ wake signal, poll-after-arm rule): no hits.
   - F-003 (self-matching process scan, "print matches not count" rule): no
     hits.
   - F-005 (evidence home, `.tmp/<wp>/` convention): no hits — the phrase
     doesn't appear in `hex/` at all (only in the untracked finding itself).
   - F-006 (exit 127 can mean E2BIG, read the log marker not the wrapper
     code): no hits.
   - F-010/F-011 (liveness discriminator, ack channel): the **heartbeat/
     liveness mechanism predates these findings** (`28a24d6` "worker
     liveness, the cap amendment, allocation invariant and preflight," well
     before 2026-09-19) but does not implement the ack-on-report convention
     F-010/F-011 argue for — confirms the finding is still open, not stale.
   - F-012 (mutation harness per-edit backup + hash verification): no hits.
   **Time from finding to fix: not applicable — none have shipped.** The
   findings file itself is still untracked in the working tree (`git status`
   shows `??`), so by definition nothing derived from it has been committed;
   F-004 (the retro-skill proposal) is the one under active discussion right
   now (`.agents/discussions/retro.md`, `State: active`).

6. **Nothing reverted or narrowed.** No commit message containing "revert"
   touches `protocol.md` or `memory.md`'s Upkeep/Memory text (checked both
   files across full history). `adr_0014_instruction_diet.md:201` — the live
   instruction-diet split — explicitly keeps "Upkeep step" listed in the
   always-loaded spine's bullet list (27,171 B, "every orchestrator"), i.e.
   the diet ADR had the opportunity to move Upkeep to a conditional sibling
   the way it moved `loop`/`decompose`/`worktree`/`verify`/`adversary`/
   `severity`, and chose not to — treated as core, not as prunable weight.

## negative:

- No commit exists that "introduces" the Upkeep step or the Memory/
  Preferences split with its own rationale — both are baseline. Citing a
  specific commit as "why Upkeep was added" would be fabricating a decision
  that was never separately made; the only real design-rationale commit in
  this lineage is `adr_0016`/`fd243e9`, and that only refines an existing
  mechanism.
- The single realized Memory candidate (`5ff3441`, line 53) is too recent
  (today) to have any promotion outcome yet — reporting it as "promoted" or
  "not promoted" both overstate what's known; the honest state is
  "un-consumed, pending next `/hex-init`."
- None of F-001..F-012 should be read as "rejected" or "considered and
  passed over" — the more precise read is "not yet acted on," since the
  source file is still an untracked draft one commit away from being staged
  at all.

## leads:

- **ecosystem lane, cross-repo**: the F-series findings originated on a
  *different* repo ("ocx crate split," WP-36/WP-34) but their proposed fixes
  are scoped as hex-skill changes belonging in *this* repo — worth checking
  whether that other repo's own history has independently worked around any
  of F-001/F-005/F-006 in its own tooling, which would be a second data point
  on how long "harness defect found while dogfooding" actually takes to
  reach a fix when nothing like a retro skill exists yet.
- **adr_0016's full text** (`.agents/adrs/adr_0016_parallel_adversary_review_checklist.md`)
  was not read in full this pass — only the C-990 citation — worth a look if
  the design phase wants the original rationale for the three-class split,
  since that ADR is the nearest precedent for "how hex previously designed a
  structured-candidate taxonomy" and a retro skill's finding taxonomy (F-004's
  project-vs-harness split) would want to justify itself the same way.
