# Retro dogfood — C-1452 evidence

Run: `/hex-retro --import .agents/handover_dogfood_findings.md`, executed by
following `hex/hex-retro/SKILL.md` literally from the source tree (no
installed copy yet), unattended. Command lines, exit codes and counts only —
no transcript content, no tool output dumps. Scratch files live under
`.tmp/retro-dogfood/` (gitignored).

## Preflight

- `python3 --version` → 3.14.5 (≥ 3.11).
- `python3 hex/hex-retro/scripts/retro.py where` → exit 0; home
  `.agents/retro/` (no `Retro:` Pointers row, default), `ignored: true`
  (the self-ignoring `inbox/.gitignore` it wrote) → no `Warning:` line.
- Owner resolution: `grim` not run in this part (deferred to part 2), so the
  SKILL.md "without grim" rule applied — every row's artifact source dir
  (`hex/hex-core`, `hex/hex-review`, `hex/hex-retro`) is in the repo → local.

## Seed import

- Model extraction of the 12 `## F-NNN — <title>` blocks into
  `.tmp/retro-dogfood/import.json` (`what` = title, `tell` = `**Observed:**`
  paragraph else first paragraph, `proposed_change` = the `**Change this
  argues for.**` section, `evidence`/key = `<path>#F-NNN`, `ts` = first date
  in the block else the file's last commit date 2026-09-23).
- `python3 hex/hex-retro/scripts/retro.py import .tmp/retro-dogfood/import.json`
  → exit 0, `written: 12, skipped: 0`.

## Mine

- `python3 hex/hex-retro/scripts/retro.py mine` (real transcripts,
  `~/.claude/projects/-home-mherwig-dev-arcana`, 1,047 transcript files)
  → exit 0 in 8.9 s; `written: 283` trajectory entries, `span_min: 38809.3`.
- `degraded`: 1 item — `transcript shape: 7 file(s) with unrecognised records
  or no tool pairs (record versions: 2.1.263)`.
- Diagnosis (per-file replay through `retro.scan`, counts only): all 7 files
  have `counted = 0` (zero unrecognised records) and `pairs = 0` — they are
  tool-free sessions of 1–44 records. A sweep of every top-level record type
  in all 1,047 files found 0 types outside `META_TYPES ∪ {user, assistant}`.
  So: no degraded item for known record types; the one `degraded` line is the
  "no tool pairs" arm firing on tool-free sessions (reported as a WP 1 defect).
- `python3 hex/hex-retro/scripts/retro.py read` → exit 0; 295 valid entries
  (0 self, 283 trajectory, 12 seed), 0 skipped.

## Folds

- Clustering (by `artifact|key|kind` for trajectory entries): 13 rows created
  (12 seed findings F-001..F-012, one per finding, plus
  `project-grep-failures`); 62 assigned (12 seed + 50 trajectory: 47 repeated
  `grep` failures → `project-grep-failures`, 3 `until`-poll / `sleep` wait
  entries → `hex-core-monitor-not-wake-signal`); 233 trajectory entries
  ignored with reasons (subagent / human-answer waits, test-build-verify cost,
  single long idle pairings, unattributed subagent errors, tool-contract
  errors, ordinary shell failures).
- Fold 1: `python3 hex/hex-retro/scripts/retro.py fold .tmp/retro-dogfood/fold1.json --wall-min 38809.3`
  → exit 0, `at 2026-09-23T17:25:04Z`, 295 consumed, 0 rejected, 13 rows
  `open`, 0 big.
- Gate (interactive, one structured question over the 12 local proposals
  P-2..P-13; cap 10 → P-2..P-11 asked, P-12/P-13 routed `deferred` by cap):
  answered **none** (unattended) → no edit applied, all 12 `deferred`.
- Fold 2 (status ops):
  `python3 hex/hex-retro/scripts/retro.py fold .tmp/retro-dogfood/fold2.json --wall-min 38809.3`
  → exit 0, `at 2026-09-23T17:25:20Z`; `hex-core-flock-fd-inheritance` →
  `fixed` (`by` = `hex/hex-core/references/resources.md`, verified: § 3
  property 2 closes `8>&-`/`9>&-` for descendants, `flock -w` bounds the
  wait, `fuser`/`lsof` recovery named); 12 rows → `deferred`.

## Report

- `.agents/retro/reports/2026-09-23.md` — `as of 2026-09-23T17:25:20Z`;
  13 proposals (P-1..P-12 under `## Harness` for F-001..F-012, P-13 under
  `## Project`); routes: 1 `applied` (P-1, pre-existing fix, no edit),
  12 `deferred`; 2 prunes considered (both kept); 0 upstream drafts;
  12 `## Deferred` items; 13 ledger rows.
- Candidate lines: none — interactive mode routes no proposal `candidate`
  (no `hex.md › Preferences` target), so `hex.md` is untouched.
- Handoff: report `.agents/retro/reports/2026-09-23.md`; 13 rows touched;
  0 big rows; the `Degraded:` line above;
  `retire .agents/handover_dogfood_findings.md: 12/12 entries imported`;
  `Next: /hex-loop .agents/retro/reports/2026-09-23.md`.

## Re-import

- `python3 hex/hex-retro/scripts/retro.py import .tmp/retro-dogfood/import.json`
  (same file, after the folds) → exit 0, `written: 0, skipped: 12` —
  re-import adds 0 entries (all 12 `-<sha8(key)>.json` suffixes already in
  `inbox/consumed/` and ledger rows).

## Part 2 — F-001 re-mark (E6)

- `.tmp/retro-dogfood/fold3.json` = one status op
  `hex-core-flock-fd-inheritance` → `fixed`, `by`
  `hex/hex-core/references/resources.md`, `"shipped": true`.
- `python3 hex/hex-retro/scripts/retro.py fold .tmp/retro-dogfood/fold3.json`
  → exit 0, `at 2026-09-23T17:30:20Z`, 0 consumed; row `fixed.stale_versions`
  = `[]` (was the fixed build's hash). Only that ledger file changed.
- Side effect: the row's `folded_at` (17:30:20Z) is now later than the
  committed report's `as of` (17:25:20Z), so the next run's step 7 treats it
  as due and re-proposes it (as a pre-existing fix).

## Part 2 — Lock-free writers

- Writer: `.tmp/retro-dogfood/write-entry.sh` — the `hex/hex-state.md`
  `Inbox:` recipe verbatim: main = first `worktree` line of
  `git worktree list --porcelain`; home `.agents/retro/` (no `Retro:`
  Pointers row); write `.<name>.tmp` in `<main>/.agents/retro/inbox/`, then
  `mv` to `<YYYYMMDDTHHMMSSZ>-<8 random hex>.json`; valid v1 entry.
- 16 writers started at once (`&` × 16, then `wait`) → exit 0; 16 distinct
  names, 0 leftover `.tmp` files.
- `python3 hex/hex-retro/scripts/retro.py read` → exit 0; 16 parseable
  entries, 0 skipped; the 16 names match the writers' names. Then the 16
  deleted; inbox back to `consumed/`, `rejected/`, `.gitignore`,
  `.mine-state.json`.

## Part 2 — Live worktree survival

- `git worktree add .agents/worktrees/retro-probe -b retro-probe` → exit 0;
  one entry written by the recipe with the worktree as cwd → exit 0;
  `git worktree remove --force .agents/worktrees/retro-probe` → exit 0;
  the entry was present in the main inbox after removal. Entry deleted,
  `git branch -D retro-probe` → exit 0.

## Part 2 — `--loop` routing probe

- `git worktree add .agents/worktrees/retro-loop-probe -b retro-loop-probe`
  (HEAD `48385e8`) → exit 0. Snapshot: main inbox (4 names) and
  `inbox/consumed/` (295 names), plus `.mine-state.json`.
- Two synthetic entries by the recipe (from the worktree, landing in the
  main inbox): one `artifact: hex-loop`, `scope: harness` proposing a
  temp-dir clause in `hex/hex-loop/SKILL.md` § The prompt; one
  `artifact: project`, `scope: project` proposing a `CLAUDE.md`
  § Verification line.
- `/hex-retro --loop .agents/goals/retro.md`, SKILL.md followed from the
  worktree's source tree:
  - Preflight: python3 3.14.5; goal file carries `Written: 2026-09-23 by
    /hex-loop`; `retro.py where` → exit 0, inbox = main checkout's, ledger
    and reports = the worktree's, `ignored: true`.
  - `retro.py mine` → exit 0, 0 written, 0 degraded. `retro.py read` →
    exit 0, 2 entries (2 self), 0 skipped.
  - Owner: `grim status --format json` → exit 0; `hex-loop` source
    `path: ./hex/hex-loop` (local), `hex-retro` `path: ./hex/hex-retro`.
  - Fold 1 (2 creates, 2 assigns), `--wall-min 94.2` (minutes since the
    goal file's first commit) → exit 0, `at 2026-09-23T17:31:44Z`,
    2 consumed, 0 rejected, 0 big.
  - Step 7: 2 due rows (`folded_at` after the report's `as of`
    17:25:20Z); 0 reopened, 0 big; no `Retro-Ledger:` trailers since the
    last reports commit.
  - Routes: **P-1 `applied`** — target `hex/hex-loop/SKILL.md#the-prompt`,
    local, inside a path-sourced skill dir, small (2 insertions,
    1 deletion, one file), applied unasked in the worktree only.
    **P-2 `candidate`** — target `CLAUDE.md#verification`, outside the
    allow-list → `candidate` + § Deferred.
  - Fold 2 (status ops: P-1 row `fixed` by `report
    .agents/retro/reports/2026-09-23-2.md P-1`; P-2 row `deferred`) →
    exit 0, `at 2026-09-23T17:32:06Z`.
  - Report `.agents/retro/reports/2026-09-23-2.md` (worktree) — heading
    `loop retro`, `as of 2026-09-23T17:32:06Z`, 1 Deferred item, 1 prune
    considered (kept). One `Retro candidate (project-context)` line written
    to the worktree's `hex.md › Memory` only. Handoff: 2 rows touched,
    0 big, no `Degraded:`/`Warning:`, `Next: /hex-loop
    .agents/retro/reports/2026-09-23-2.md`.
- Teardown: `git worktree remove --force` → exit 0;
  `git branch -D retro-loop-probe` → exit 0. The probe consumed only the
  two synthetic entries (consumed/ diff vs snapshot) → both deleted, none
  moved back; `.mine-state.json` restored from the snapshot. consumed/ is
  back to the 295 snapshot names; main `.agents/memory/hex.md` unmodified.

## Part 2 — Rendered retro goal paste

- Temp copy `.tmp/retro-dogfood/goals/retro.md` of `.agents/goals/retro.md`
  plus `- Retro checkpoints: after each outer cycle` in § Loop shape; paste
  rendered from `hex/hex-loop/assets/goal-prompt.md` (re-print: wrapper
  `/goal `, rounds 2, branch `"hex/retro"`, grants `none`, 13 criterion
  titles). Counted by the documented command
  (`mktemp` copy, `python3 -c 'import sys; print(len(open(sys.argv[1], encoding="utf-8").read()))'`)
  → **3,354** ≤ 4,000 (the temp path adds 22 chars over
  `.agents/goals/retro.md`).

## Part 2 — Install

- `grim lock` → exit 0 (`hex-loop`, `hex-retro`, `hex-state` locked; rest
  unchanged). `grim install` → exit 0: `hex-retro` installed; `hex-init`,
  `hex-loop`, `hex-state` updated. Files changed: `.claude/rules/hex-state.md`,
  `.claude/skills/hex-core/references/{memory,protocol}.md`,
  `.claude/skills/hex-init/{assets/templates/goal.md,references/audit.md}`,
  `.claude/skills/hex-loop/{SKILL.md,assets/goal-prompt.md}`,
  `.claude/skills/hex-retro/` (new), `grimoire.lock`. Nothing outside those.
- Installed rule carries the `Entry:` and `Inbox:` lines;
  `.claude/skills/hex-retro/scripts/retro.py` exists.

## Part 2 — Seed retirement

- `git rm -q .agents/handover_dogfood_findings.md` → exit 0 (handoff:
  `retire … 12/12 entries imported`).

## Part 2 — WP 6 sweep

- `bash .tmp/retro-sweeps/wp6.sh <repo>` → exit 1: 31 ok, 1 FAIL —
  `C1452-i1` (installed `SKILL.md` byte-equal to source). The body below
  the frontmatter is identical; grim's Claude transform hoists the
  `claude.*` metadata keys to top-level `user-invocable` /
  `disable-model-invocation`, so any skill carrying them (`hex-loop` too)
  never byte-matches. Sweep check defect, not an install defect.

## WP 7 — criterion j evidence (2026-09-23)

- `git worktree add .agents/worktrees/retro-cand-probe -b retro-cand-probe`
  (HEAD `f37c701`) → exit 0. Snapshot: main inbox (0 names), `consumed/`
  (295 names), `.mine-state.json`.
- One synthetic entry by the capture-rule recipe (from the worktree,
  landing in the main inbox): `artifact: project`, `scope: project`
  proposing a `CLAUDE.md` § Verification line. `retro.py where` (worktree
  cwd) confirmed inbox = main checkout, ledger/reports = worktree.
  `mine` skipped per task; `retro.py read` → exit 0, 1 entry, 0 skipped.
- Fold 1 (create + assign `project-claude-md-verification`) → exit 0,
  `at 2026-09-23T18:04:44Z`, 1 consumed. Route: **candidate** — target
  `CLAUDE.md#verification`, outside the loop allow-list (SKILL.md §
  Routing and gate names `CLAUDE.md` explicitly). Fold 2 (status
  `deferred`) → exit 0, `at 2026-09-23T18:04:49Z`. Report
  `.agents/retro/reports/2026-09-23-2.md` written in the worktree (a
  `2026-09-23.md` already existed there).
- Candidate line written to the worktree's `hex.md › Memory`:
  ```
  - Retro candidate (project-context): "CLAUDE.md Verification lacks worktree probe reminder" — ledger project-claude-md-verification, .agents/retro/reports/2026-09-23-2.md.
  ```
- Format check: `/usr/bin/grep -nE '^- Retro candidate \((perspective|review-value|checklist-item|project-context)\): "[^"]{1,120}" — ledger [a-z0-9][a-z0-9-]{2,79}, \.agents/retro/reports/[0-9]{4}-[0-9]{2}-[0-9]{2}(-[0-9]+)?\.md\.$' <worktree>/.agents/memory/hex.md`
  (id class from `retro.py` `ID_RE = [a-z0-9][a-z0-9-]{2,79}`) → exit 0,
  matched line 941, the line above verbatim.
- Teardown: `git worktree remove --force` → exit 0; `git branch -D
  retro-cand-probe` → exit 0. Consumed diff vs snapshot: exactly one new
  name (the synthetic entry, moved there by fold) → deleted. Inbox diff:
  empty. `cmp .mine-state.json` → exit 0 (untouched, `mine` never ran).
  `git status --short .agents/memory/hex.md` → empty (main copy
  unmodified).
