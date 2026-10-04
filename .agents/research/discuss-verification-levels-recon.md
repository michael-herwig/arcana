# Research: hex verification gate model and ocx tiers

## Metadata

Date: 2026-09-24
Lane: codebase recon
Discussion: .agents/discussions/verification-levels.md

## Direct answer

hex has exactly **two** verification grades — `scoped` (contract tests + cheapest
assembly gate) and `full` (project's whole documented verification) — chosen per
gate site by fixed structural triggers (merge count, dependency-level clear,
high-risk path/hub match, coordinator-join, or an author-set `Verify: full`
cell), never by diff *content* class. Content/path class (docs-only, security
paths, hot paths, new manifests) is read in exactly two places, both **review**
sizing (join-level escalation, `/hex-review` tier classification) — not
verification-command selection. Reviewers *are* allowed to run commands ("read-only
plus run commands for verification"), builders run the scoped/full check as
part of their gate. ocx layers a **five**-tier scheme (T0 lint, T1 inner, T2
full, T2 release, T3 deep) entirely inside "the project's documented
verification" that hex treats as one opaque unit — hex has no visibility into
ocx's T0–T3 split at all. Vocabulary collision risk: hex already owns `low
medium high xhigh max` (tier), `L0–L3` (review join level), `scoped|full`
(Verify budget) — a fourth "verification level" axis needs a name distinct
from all three.

## Key findings (each with file:line)

### 1. hex's current verification model — every gate site

- **Two verification classes only**, both defined once: `hex/hex-core/references/verify.md:41-155`
  (scoped check) and `:156-241` (checkpoint = a full run). "hex never defines
  how to verify a project" (`verify.md:8`) — it always shells out to the
  project's own documented command; hex only decides *when* to run the cheap
  vs. the full form of that one opaque command.
- **Scoped check, three gate sites** (`verify.md:43-57`):
  1. Review-Fix Loop **Implement gate** — unconditional at every tier
     (`loop.md:18-39`), except a leaf under a decomposing coordinator runs
     compile/parse only (`loop.md:33-39`).
  2. Loop **exit gate**, when the WP's `Verify` cell resolves `scoped`
     (`loop.md:128-134`, grammar in `decompose.md:76-110`).
  3. **WP merge onto the feature branch** (`worktree.md:36-38`), except a
     decomposing-coordinator-owned WP's merge, which pays full instead
     (trigger (i), `worktree.md:40-46`).
- **Full verification ("checkpoint"), fires on first of three triggers**
  (`verify.md:161-184`): `M=3` merges since last full run; a merge that
  clears a dependency level; a merge that is high-risk (path or hub match,
  `verify.md:210-227`). Plus the mandatory un-lowerable **final gate**
  (`worktree.md:50-51`) and two override paths: an author-set `Verify: full`
  cell / `Verify-default: full` line (`worktree.md:52`, grammar
  `decompose.md:76-110`), and a **degrade** when no assembly gate or no
  runner-addressable test set is discoverable (`worktree.md:53-58`,
  `verify.md:87-97`).
- **The `Verify` cell / `Verify-default:`** — the *only* author-declared
  budget lever, raise-only (`scoped`→`full`), set per-WP at plan time
  (`decompose.md:76-110`). It also feeds the `door` risk flag that can raise
  a WP's *effective tier* to the plan ceiling (`decompose.md:323-324,333`).
- **Resources**: every `heavy`-classed run of either check takes a semaphore
  slot (`resources.md:95-112`); a `light` gate is unbounded and never
  consults it (`resources.md:80-84`).
- **DESIGN.md's execution-performance round** (`hex/DESIGN.md:855-931`,
  `adr_0010`) is the origin of the scoped/checkpoint split — it replaced
  "verification after every merge" with a bounded dual-trigger cadence,
  explicitly modeled on Chromium CQ / Postgres-style dual-trigger checkpoint
  policies, not on a graded-level scheme.

### 2. Diff content / path class — review sizing only, never verification selection

- **`sec`/`hot` flags** (`decompose.md:293-322`) raise the WP's **effective
  tier** (phases + model class) and, via `door`, can force `Verify: full` —
  but the *predicate itself* (path matches auth/crypto/CI/lockfile markers,
  or a project hot-path convention) never appears in `verify.md` or
  `worktree.md`'s scoped/full decision; it only feeds tier derivation and,
  separately, the checkpoint's own independent high-risk clause
  (`verify.md:210-227`, keyed on the *actual merge diff*, same marker table).
- **Review join-level escalation is content-aware**: `loop.md:217-228`
  — `sec`/`hot`/`door` (or the plan's `risk`-flagged `Review` cell) raise a
  WP's *review* one join level (`L0→L1`, `L1→L2`), never a round count and
  never verification depth.
- **`L0`-only carve-out is content-aware for review, not verification**:
  `loop.md:172-179` — a WP is reviewed with zero reviewer spawns ("L0 only")
  when its entire diff is markdown/docs; this is purely a **review** shortcut
  (mechanical evidence-table grep) and has no verification-side twin — the
  Implement-gate scoped check still runs "unconditionally, at every tier"
  (`loop.md:20`) regardless of doc-only content.
- **`/hex-review`'s classifier is fully diff-content-driven** but this is
  *review* tiering, a distinct machine from execution's verification gates:
  `hex/hex-review/classify.md:44-92` — file_count/lines_changed/areas_touched
  plus a structural-marker table (new manifest → xhigh; CI workflow →
  breadth=full; auth/crypto/token/secret path → adversary=on; public API →
  xhigh) drives the **review** tier (`low..xhigh`) and overlay axes
  (`breadth`, `rca`, `adversary`), never a verification command choice.
- **Conclusion: no site in verify.md/loop.md/worktree.md/decompose.md reads
  diff content or path class to choose *between* scoped and full** — the
  scoped/full choice is driven purely by structural counters (merge count,
  dependency-level clear) and the same marker table's *hub/high-risk*
  reading (which *is* path-based, `verify.md:210-227`) — so path class does
  feed the checkpoint trigger, but only as one of three trigger conditions,
  never as a distinct verification-level axis of its own.

### 3. Review workers running the test suite themselves

- **`reviewer` (L1/L2 seat)**: "**Tools — read-only plus run commands for
  verification.** No edits — the orchestrator dispatches a builder to fix."
  (`hex/hex-core/references/workers/reviewer.md:28-29`). Explicitly
  permitted to run commands (to verify claims by execution), forbidden to
  edit.
- **`doc-reviewer`**: "**Tools — read-only plus run commands.**"
  (`workers/doc-reviewer.md:9`), same shape.
- **`coordinator`**: "**Tools — read, spawn leaf workers, run the project's
  verification.**" (`workers/coordinator.md:82`) — the decomposing
  coordinator is the one non-review role explicitly authorized to run the
  project's real verification command (the sub-WP join check).
- **Pure read-only, no run at all**: `explorer` (`workers/explorer.md:9-13`,
  "read-only exploration… No edits — do not edit any file"),
  `architecture-explorer` (`workers/architecture-explorer.md:10-14`, same).
- No file forbids a reviewer from running the *documented verification
  command itself*; the grant is generic ("run commands for verification"),
  not scoped to a narrower selftest-only command — but the mission text
  never instructs a reviewer to run the *full suite*, only to "verify claims
  by reading the code" and cite evidence, so in practice the grant is used
  for point-checks, not a substitute for the builder-run scoped/full gate.

### 4. Recording "this exact tree already passed verification"

- **The one explicit skip-on-unchanged-tree rule**: `hex/hex-core/references/finalize.md:71-75`
  — after `/hex-finalize`'s rebase onto a freshly-fetched target, the local
  suite re-runs "exactly once… where the base did not move, it does not [re-run]
  — the earlier result is still evidence about the same tree." This is the
  only place hex reasons explicitly about tree-identity to skip a re-run.
- **Adjacent but not a memo**: the collapsed-builder ordering check
  (`loop.md:57-62`) runs the scoped check "warm, reusing the tree already
  built" — a build-artifact reuse optimization, not a certification cache;
  it still re-executes the tests.
- **The selective-test convention's `pytest --testmon` example**
  (`verify.md:120-135`) is a project-owned tool that *itself* may skip
  unchanged tests — hex treats it as opaque and never inspects or relies on
  its skip decision; hex's own floor ((a) contract tests, (b) assembly gate)
  always re-runs regardless.
- **No hex-side hash/SHA-keyed "already verified" cache exists** for the
  scoped/full choice itself — checkpoints are purely counter- and
  trigger-driven (`verify.md:161-184`), never conditioned on whether the
  current tree state was already checked.

### 5. ocx's tier scheme (`/home/mherwig/dev/ocx`)

`.claude/artifacts/adr_test_speed_tiers.md` (Accepted 2026-09-23) defines
**C-TIER**, a five-row table (`adr_test_speed_tiers.md:208-217`):

| Tier | Runs | Trigger | Budget | Proves |
|---|---|---|---|---|
| **T0 lint** | `task test:lint:structure` + `scoped_gate.py --check-coverage` | verify phase 1; every `verify:scoped` | ≤30s, uncached | structural sweeps, coverage of the routing table |
| **T1 inner** | `task bazel:test:unit` (cached, reverse-dep floor) + per-crate clippy + T0 + smoke + scoped globs | `task verify:scoped --force`, per WP iteration | ≤120s (target) first-verify-after-edit | the changed crate + its reverse dependents |
| **T2 full** | `task verify` (both phases incl. `bazel:test:accept`) | WP merge commit (enforced by `commit_gate.py`), `/hex-finalize`, any escalation, commits on `main` | unbounded, measured | everything; mechanically enforced via tree-digest match |
| **T2 release** | `task verify` with `bazel:test:accept NOCACHE=1` | `release:` commits | unbounded | same as T2 but cold acceptance |
| **T3 deep** | `verify-deep.yml` | push to `main`, merge queue, dispatch | CI, cold | fresh-runner acceptance, no remote cache reuse |

- **Escalation table** lives in `test/scoped_rows.toml`, read by
  `scripts/scoped_gate.py` (`adr_test_speed_tiers.md:296-328`): `[security]`
  globs checked first (always escalate: `.github/**`, `ocx_oci`, `ocx_trust`,
  `ocx_config`, `ocx_store`, `ocx_sign`, sign/verify/attest/login/logout
  command files); `[verbs]` escalate-only markers (`*_common.rs`,
  `script_runner.rs`, `deprecated.rs`); `[crates]` maps a crate to test globs
  or `"escalate"` (`ocx_test_support` always escalates); any other
  `crates/ocx_cli/src/**` path escalates by permit-list default; a hub crate
  (≥ HUB_RDEPS reverse dependents) or ecosystem-member crate escalates.
- **Taskfile `verify` vs `verify:scoped`**: `taskfile.yml:150-161` (`verify`
  = mark-precheck → git:hooks → `.verify:lint` → `.verify:build-test` →
  full mark) vs. `taskfile.yml:163-235` (`verify:scoped` = `scripts/scoped_gate.py
  --plan` decides `escalate|routed|scoped`; `escalate`→ runs the full
  `verify` task; `routed`/`scoped` run only the touched lanes — lint tier
  always, then per-route checks, concurrently as `.verify:scoped:lanes`
  for a true `scoped` decision — cargo check, per-crate clippy/doc tests,
  one cached `bazel:test:unit`, doc ratchet, `test:smoke`, `test:scoped`
  over `acceptance_globs`).
- **`hex.md › Pointers` "Verification" row** (`ocx/.agents/memory/hex.md:8-11`):
  `` `task verify:scoped --force` per task and review-fix iteration (escalates
  to the full gate when a path demands it); `task verify` (full) at the
  work-package merge and at finalize; `task` = fast check. `` — this is the
  **entire surface hex sees**: from hex's point of view ocx has exactly the
  scoped/full vocabulary hex already expects, and T0/T1/T2/T3 are invisible,
  folded inside "the project's documented verification."
- **Measured durations** (`adr_test_speed_tiers.md:37,151-162,177`): cold
  full acceptance 1421s serial pre-fix / 283s cold concurrent post-AM-9;
  `task test:parallel` 160s; T1 target ≤120s wall for a reference one-crate
  edit; CI minutes per PR ≈18 (basic tier, unaffected); a docs-only or
  clean/dirty-flip commit previously re-ran all 181 acceptance targets
  (target: 0 after D1's provenance-placeholder fix).

### 6. Naming collisions a new "verification level" vocabulary would hit

- **`low | medium | high | xhigh | max`** — hex's **tier** grammar
  (`hex/hex-core/references/protocol.md` § Tier grammar, referenced
  `decompose.md:255-259`) — scales phases and model class per WP.
- **`L0 | L1 | L2 | L3`** — hex's **review join level** grammar
  (`loop.md:140-154`) — scales review depth/seats, keyed on where a diff
  joins, explicitly *not* on tier.
- **`scoped | full`** — hex's existing **`Verify` cell** budget vocabulary
  (`decompose.md:76-110`) — this is the closest existing thing to a
  "verification level" already, binary and raise-only.
- **`T0 | T1 | T2 | T2-release | T3`** — ocx's project-local **test speed
  tier** vocabulary (`adr_test_speed_tiers.md`), entirely inside Layer-1
  project knowledge hex never parses.
- A fourth "verification level" concept in hex would collide semantically
  (not textually, if letters/words differ) with three existing closed,
  versioned enumerations already named `tier`, `level` (join level), and
  `Verify` budget; **"level" as a word is already claimed by join level**,
  so a graded-verification axis reusing that word needs a different lexeme
  entirely (hex's own convention, per `decompose.md`'s explicit avoidance of
  "wave" for a levels concept, `decompose.md:186-188`, suggests hex authors
  are already sensitive to this collision class).

## negative: (contradicting evidence, dead ends)

- hex's `Size` cell (`S|M|L`) looks like a candidate third "level" name but
  is explicitly **not** a verification-budget input — it only seeds
  effective-tier derivation (`decompose.md:24-39,280-292`); confirmed no
  crossover into `verify.md`.
- The `sec`/`hot`/`hub`/`door` "flags" are not a graded scale — they are
  four independent booleans, closed and versioned at exactly four
  (`decompose.md:277-278`); do not mistake them for a leveled verification
  axis, they gate tier and the `Verify` cell only.
- ocx's `adr_test_speed_tiers.md` Status line shows amendments AM-1…AM-12
  layered onto an "Accepted" ADR — some Consequences/Negative-risk rows
  (e.g. `bazel:test:accept` serial at T2, 1421s) are stated as **superseded
  by AM-9** (concurrent, 283s) inline in the same document; the file itself
  is not fully current in every cell — cite with that caveat.
- No hex file defines a per-tree verification memo/hash cache; the only hit
  (`finalize.md:71-75`) is scoped to one narrow re-entrant-finalize scenario,
  not a general mechanism — do not generalize it as "hex has a verification
  cache."

## leads: (one line each)

- **priorart lane** — survey how other multi-agent/CI systems (Bazel remote
  cache, Chromium CQ, cargo-dist tiering) name graded verification levels,
  to avoid colliding with hex's `tier`/`L0-L3`/`scoped|full` triad.
- **statemap lane** — check whether hex's `Verify` cell (`scoped|full`)
  could simply gain a third value instead of inventing a parallel axis,
  given ocx already proves a 3-5-way split is valuable underneath one
  "scoped" hex call.
- **council lane** — resolve whether "graded verification chosen per gate
  and per kind of change" is better modeled as (a) hex delegating tier
  choice entirely to project-documented verification (status quo, ocx already
  does this), or (b) hex itself gaining a third+ `Verify` value — the
  ocx evidence in this file supports (a) already working without hex changes.
