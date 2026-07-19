# ADR: Cross-repo federation — work that spans multiple git repos

## Metadata

**Status:** Accepted
**Date:** 2026-07-20
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below
      (see [Constitution deviations](#constitution-deviations) — this
      decision amends **four** resolved decisions in
      [`hex/DESIGN.md`](../../../hex/DESIGN.md) — two worktree/branch
      rules, the locked plan-visualization column set and the locked
      plan-time file-set intersection check — and adds one new class of
      write)
**Domain Tags:** infrastructure, integration, developer-experience
**Supersedes:** N/A (amends `DESIGN.md` § Worktrees, § Plan visualization
and § Parallel-by-default decomposition — see the deviations
table; relates to [`adr_0002`](adr_0002_execution_scheduling_recursion.md)
whose `Depends-on` DAG and Status column this reuses unchanged)
**Superseded By:** N/A

## Context

hex today is single-repo by construction, and nothing in the bundle says
so. Every orchestrator resolves memory by upward search from cwd, nearest
wins (`memory.md:11-13`); the plan's Parallelization table has no repo
axis (`hex-init/assets/templates/plan.md:139` — `| WP | Scope | Expected
Files | Size | Wave | Depends on | Review | Status |`); worktrees and
merges are `git` invocations with an implicit cwd
(`protocol.md:358-437`); and verification is "the project's documented
verification" (`protocol.md:441-446`), singular.

**This is not a speculative gap.** The driving cluster is the `ocx`
family under `/home/mherwig/dev`: one core Rust CLI plus satellites, all
owned and writable by the decider. Its coupling is evidenced, not
inferred:

- `ocx-mirror/.gitmodules` and `ocx-mcp/.gitmodules` both vendor
  `external/ocx` → `https://github.com/ocx-sh/ocx.git`.
- `ocx-mirror/Cargo.toml:21` and `ocx-mcp/Cargo.toml:30` both consume
  `ocx_lib = { path = "external/ocx/crates/ocx_lib" }`, and both
  re-declare `[patch.crates-io]` re-pointing `oci-client` into the
  submodule's nested fork (`ocx-mirror/Cargo.toml:96-97`), because Cargo
  patch tables apply only at the consuming workspace root.
- The drift the patch table invites is **already visible**:
  `ocx-mirror/Cargo.toml:91` records the fork requirement as `oci-client
  "0.17"`, `ocx-mcp/Cargo.toml:47` still says `"0.16"`. Two satellites,
  one upstream, two different beliefs about it. The only guard is a
  hand-written `cargo tree -i oci-client` assertion per satellite
  (`ocx-mirror/Cargo.toml:95`), which each repo runs alone.
- A coordinated cross-repo change already happened and is fully
  reconstructable: `ocx@1476192c` ("refactor!: move ocx-mirror to its own
  repository", 2026-06-12) and `ocx-mirror@903eea5` ("chore: scaffold
  standalone repository", same day), with `ocx-mcp@8f08740` ("chore:
  scaffold ocx-mcp from ocx-mirror") reusing the template two days later.

**The worked example used throughout this ADR** is the next instance of
exactly that coupling: **`ocx` v0.5.0 changes `ocx_lib`'s public API, and
that one change must land as a submodule bump + patch-table edit + source
adaptation in both `ocx-mirror` and `ocx-mcp`.** It already happened once
at v0.4.2 (`ocx-mirror@a8f504f`, 2026-07-08) and cost a commit's worth of
manual adaptation to two API breaks. Three repos, one decision, no shared
artifact.

Two facts about this cluster that a naive design gets wrong, both
verified rather than assumed:

1. **`ocx-evelynn`, `ocx-sion` and `ocx-soraka` are not repos.** They are
   worktrees of `ocx` — `git -C ocx-evelynn rev-parse --show-toplevel`
   returns `/home/mherwig/dev/ocx-evelynn`, but
   `rev-parse --git-common-dir` returns `/home/mherwig/dev/ocx/.git`,
   identical to `ocx`'s. The research's proposed identity probe
   (`spec-federation-multi-repo.md:476`, "verifies it with `git -C <path>
   rev-parse --show-toplevel`") accepts all four as distinct repos. It is
   the wrong probe.
2. **Trunk state diverges across the cluster.** `ocx` is on `main`,
   `ocx-mcp` on `main`, `ocx-mirror` on `feat/pypi-mirror`. hex's feature
   branch rule — "the non-trunk branch already checked out, else create
   `hex/<plan-slug>` from the trunk" (`protocol.md:363-367`) — applied
   per repo would put this change on `hex/<slug>` in two repos and on
   `feat/pypi-mirror` in the third, destroying the shared slug that is
   supposed to be the git-level join key.

Verification also diverges: most of the cluster shares `task verify`, but
`setup-ocx` uses `bun test` and `vscode-ocx` uses `vscode-test`. No
single command spans the family, which is consistent with hex's existing
"hex never defines how to verify a project" (`protocol.md:441`) and rules
out any uniform cross-repo gate.

### The eight failure modes

From [`spec-federation-multi-repo.md:45-96`](../research/spec-federation-multi-repo.md).
These are the acceptance criteria for this decision, restated compactly:

| # | Failure mode |
|---|---|
| **FM1** | **One proposal, three repos.** Where does the artifact live, and does it have one Status block or three? Three = three sources of truth for one decision. |
| **FM2** | **Spec owned by A, consumed by B.** A edits; nothing in B knows. (The `oci-client 0.17`/`0.16` split, live.) |
| **FM3** | **Traceability across the boundary.** `C-`/`S-` IDs are plan-scoped and are the convergence join key (`protocol.md:346-356`); satellite commits carry no plan reference, so coverage stops at the repo edge. |
| **FM4** | **Review must see both diffs.** `git diff` is per-repo; a reviewer in one repo is blind at precisely the seam where a cross-repo change breaks. |
| **FM5** | **Worktrees across repos.** `git worktree` has no cross-repo concept. Upside: file-disjointness (`protocol.md:383-384`) is free across repos. Downside: merge order must still respect edges that cross the boundary, and the orchestrator executing them is one sequential actor. |
| **FM6** | **Where the plan lives / memory resolution.** Upward search is nearest-wins and does **not** merge ancestors (`memory.md:11-13`). Run an orchestrator from a satellite's cwd and it finds the *satellite's* memory — different active plan, different verification. Split brain, silently, no error. |
| **FM7** | **Who archives, and when.** Repos have independent PR cadences. There is no cross-repo atomic merge; partial landing is a real broken-integration window that nothing in the plan expresses. |
| **FM8** | **Verification has no home repo.** Each repo documents its own; the integration check ("does B still work against A's new contract") belongs to neither, so no pointer resolves it. |

Rollback inherits all of them, inverted.

## Decision Drivers

- **hex ships markdown; the client is the runtime.** No daemon, no
  server, no new binary, no scanner, no catalog
  (`DESIGN.md:320-322` — "hex ships markdown, the client is the runtime
  — portability is the moat"). Every mechanism here must be something an
  LLM does by reading a small file and running `git`.
- **No new file format if an existing hex construct can carry it.** The
  plan table, `hex.md › Pointers`, git branches, git trailers and the WP
  Status column already exist and already carry state.
- **Silent wrong behaviour is the worst outcome, and FM6 is exactly
  that.** A satellite-cwd run today produces a plausible, wrong,
  *silent* result. Any adopted design must convert it into a halt.
- **Declare relationships, never synchronize them.** Both credible
  precedents converged on this independently (OpenSpec Stores: "No sync,
  ever — by design", `docs/stores-beta/user-guide.md:327-329`; spec-kit
  discussion #1743). hex never pushes today (`protocol.md:408`) and
  must not start.
- **Invisible to single-repo users.** Every rule adopted must be vacuous
  when the federation pointers are absent — the same no-version-marker
  discipline as `adr_0002` C-105 ("no schema-version marker: the presence
  of dotted IDs is the signal").
- **Blast radius is new.** Every mechanism prior to this ADR acts inside
  one repo. Federation makes an orchestrator write in a repo the session
  did not start in. That is a security-relevant change, not just an
  ergonomic one.

## Industry Context & Research

Primary artifact:
[`spec-federation-multi-repo.md`](../research/spec-federation-multi-repo.md)
(~20 mechanisms surveyed, fit table at `:231-252`). Prior art that
actually constrains the answer:

- **OpenSpec Stores** (beta, v1.5.0) — a store is an ordinary git repo
  with an identity file, registered per machine, addressable from any
  repo. Cross-repo spec sharing is **read-only reference, never merge**
  (`user-guide.md:168-224`), and the documented non-goal is absolute:
  "No sync, ever — by design. OpenSpec never clones, pulls, or pushes"
  (`user-guide.md:323-332`). A change that spans repos, tracked as one
  thing, remains **open and unimplemented** — issue #725, not closed by
  Stores. This is the state of the art and it does not solve FM1.
- **OpenSpec's double-root refusal** (`src/core/init.ts:132-160`) —
  `init` throws rather than scaffold a nested root under a repo whose
  planning is externalized. This is the shipped precedent for the FM6
  guard, and it is a *refusal*, not a warning.
- **OpenSpec's `git -C` walks-up hazard** (`src/commands/doctor.ts`) —
  `doctor` runs `isGitRepositoryAtRoot` *first*, because probing a
  non-repo path nested inside another repo silently records the
  **enclosing** repo's origin. Directly reused in C-303.
- **OpenSpec worksets** (`src/core/worksets.ts:26-33,63-72`) — a
  developer's checkout layout is machine-global personal state, "nothing
  is ever written into a member folder". The reason option A is rejected.
- **Gerrit Topics**
  (`gerrit-review.googlesource.com/Documentation/cross-repository-changes.html`)
  — the most mature production system for exactly FM1/FM4/FM7. A shared
  **topic string** groups changes across repositories; the UI shows them
  as one related set and offers "Submitted Together". That is
  independent validation of two choices here: a **shared string as the
  cross-repo join key** (C-304's `<plan-slug>`) and a **union review
  view** (C-309). Decisive for FM7: Gerrit's own documentation states
  submission across repositories is **not atomic** — a topic spanning
  repos "simply triggers submission of all changes. No other guarantees
  are given. Submission of all changes could fail, so you could get a
  partial topic submission." The field's best tool has the same window
  this ADR names, and offers no landing order at all.
- **Dedicated coordination repo** — the "repo-of-repos"
  (`raffertyuy.com/raztype/repo-of-repos-pattern/`, a `repos/repos.yaml`
  manifest in its own git repo with workspace-level agent rules
  centralized there) and "meta-repo"
  (`seylox.github.io/2026/03/05/blog-agents-meta-repo-pattern.html`, a
  context-only repo with an `AGENTS.md` entry point, `repos.yaml` and
  workflow playbooks) write-ups. Structurally distinct from option A —
  the manifest is itself a committed, clonable repo — so option A's
  objections do not transfer. Evaluated as option A′ below.
- **spec-kit** (discussion #1743) — the null answer: run it at the top
  level; repos with different requirements are separate projects with
  separate constitutions. That is option F, and it is a real answer for
  loosely coupled repos.
- **log4brains** — a tool whose entire purpose is publishing ADRs still
  requires one central repo; cross-repo aggregation is README-roadmap.
  Central ADR home is state of the art, which `.agents/adrs/`
  already is.
- **Claude Code's own guidance** for conventions across many repos is not
  more nested context files — it is skills, plugins and MCP
  (code.claude.com/docs/en/large-codebases). Structurally that is what
  grim already is for arcana: the architecture is already the recommended
  one, which is why no new distribution channel appears below.
- **The manifest family** (Google `repo`, ROS `vcstool`, Zephyr `west`,
  `meta`) solves "get N repos onto disk at pinned revisions". That is a
  different problem — the ocx cluster is already on disk. Only `west`'s
  `import: true` (transitive, per-revision) is conceptually interesting,
  and it is not needed here.

**Runtime constraints, verified** (`spec-federation-multi-repo.md:260-284`):
`CLAUDE.md` is *concatenated* root→cwd; `--add-dir` grants file access
and always loads skills but loads the added directory's `CLAUDE.md`
**only** under `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`;
`.claude/settings.json` never inherits; and hex's own memory search is
nearest-wins and does not merge ancestors. Consequence for every option:
**a worker reading a satellite's conventions must `Read` the file
explicitly and must never assume ambient context.**

## Considered Options

Each option is shown coordinating the **same** worked example: `ocx`
v0.5.0 breaks `ocx_lib`'s public API; `ocx-mirror` and `ocx-mcp` must
each bump `external/ocx`, reconcile `[patch.crates-io]`, and adapt
source.

### Option A — Federation manifest at a common ancestor

A new file at the nearest common ancestor, `~/dev/.agents/
federation.md`, listing members and roles.

**Worked example.** `/hex-plan` in `~/dev/ocx` walks up past the repo
root, finds `~/dev/.agents/federation.md` listing `ocx`,
`ocx-mirror`, `ocx-mcp`, and offers cross-repo WPs.

**Trade-offs.** The upward walk hits `~/dev/ocx/.agents/…` first and
stops — nearest-wins (`memory.md:11-13`) means the ancestor file is
*never seen* unless hex adds a second, different search rule, which is
precisely the phantom-root problem OpenSpec needed a qualifier for
(`root-selection.ts:284-298`). `~/dev` is outside every repo, so the
manifest is uncommittable and unshared; every developer's layout differs
— the exact reason OpenSpec put worksets in a machine-global data dir and
never writes into a member folder. New file format, new resolution rule,
unversioned, duplicating what git remotes already hold. **Reject.**

### Option A′ — Dedicated coordination repo (hub-and-spoke manifest)

A new git repo, e.g. `ocx-meta`, holding `repos.yaml` (or an
`AGENTS.md` + playbooks), cloned alongside the cluster and named
explicitly by each member. The 2026 "repo-of-repos" / "meta-repo"
patterns.

**Worked example.** `ocx-meta/repos.yaml` lists `ocx`, `ocx-mirror`,
`ocx-mcp` with roles; `/hex-plan` in `ocx` reads the pointer to
`../ocx-meta`, then reads the manifest, then offers cross-repo WPs.

**Trade-offs.** Genuinely fixes option A's two fatal flaws: the manifest
is committed, versioned and shared, and it is found by an explicit
reference rather than a second upward-search rule. It also collapses
C-301's N×(N−1) bilateral pointer set into one hub — a real advantage at
larger N, and the reason this option is recorded rather than dismissed.
Rejected here for three reasons, all cost-shaped rather than
correctness-shaped: (1) it is a **new repo and a new distribution
channel**, which `DESIGN.md:320-322` and the "no second distribution
channel" rule of this ADR both push against — and grim is already the
sanctioned channel if one is ever needed; (2) it does not remove the
bilateral pointer anyway — every member still needs one pointer to the
hub, and the satellite side still needs C-308's back-pointer for the
FM6 refusal, so the hub replaces N×(N−1) lead-side bullets with N
hub-side pointers plus a manifest to keep in sync — at N=3 satellites
that is more moving parts, not fewer; (3) the manifest becomes a second
source of truth for membership that must be reconciled with git remotes
and with each member's own memory, which is exactly the copy-drift
`DESIGN.md:36` forbids. **Reject at this scale; revisit if the
federation ever exceeds roughly five members or if a second cluster
appears** — the migration is mechanical, since C-301's bullets already
carry every field a manifest row would need.

### Option B — OCI-distributed shared contracts via grim

`ocx` publishes `ocx_lib`'s contract as a grim artifact; satellites
declare and digest-pin it; `grim update` is the deliberate bump.

**Worked example.** `ocx` runs `grim release` →
`ghcr.io/ocx-sh/spec-ocx-lib:0.5.0`; `ocx-mirror` and `ocx-mcp` each
`grim add …@sha256:…`. The `0.17`/`0.16` divergence becomes a visible
lockfile diff instead of a comment nobody reads.

**Trade-offs.** Correct, already built, zero new hex code, and the
industry-converged shape for **stable published** contracts (research
finding 9; grim already supports tag and `@digest` pinning with a
lockfile). Useless for an in-flight change: a proposal touching three
repos would need a publish round-trip per iteration, and the proposal is
not a released artifact. It answers FM2 and nothing else. **Adopt for
the published-contract case only; it is not a federation model.**

### Option C — Pointer-only federation in `hex.md › Pointers`

No new file, no new section: bullets under the existing `## Pointers`
recording where each sibling repo is and where it documents its
verification.

**Worked example.** A researcher in `ocx` needs `ocx-mirror`'s patch-table
convention; the pointer names the path and it `Read`s
`ocx-mirror/Cargo.toml` directly — which works regardless of the
`--add-dir` `CLAUDE.md` gotcha, since `Read` needs only path access.

**Trade-offs.** Zero new machinery, zero deviation, and it fits the
existing verify-on-consumption staleness rule (`memory.md:117-127`)
exactly. But it answers "where is the other repo" and nothing else: no
notion of a shared change, no ordering, no coverage. It scales as
hand-maintained N×(N−1) pointers that drift independently. **Adopt as
the substrate — every other option records what it found here — but it is
not by itself a federation model.**

### Option D+E — Lead repo owns the change; satellites get WPs, run in multi-root worktrees

One plan artifact in the lead repo, unchanged in every respect except one
optional `Repo` column in the existing Parallelization table, resolved
against Option C's pointers, executed with `git -C <satellite> worktree
add` in a session launched with `--add-dir`.

**Worked example.** `/hex-plan high` in `ocx` produces one plan at
`ocx/.agents/plans/plan_ocx_lib_v050.md` with one Status block and
one ID space:

| WP | Repo | Scope | Expected Files | Wave | Depends on | Status |
|----|------|-------|----------------|------|------------|--------|
| WP1 | `.` | C-001, C-002 | `crates/ocx_lib/src/**` | 1 | — | pending |
| WP2 | `mirror` | C-003 | `external/ocx`, `Cargo.toml`, `src/**` | 2 | WP1 | pending |
| WP3 | `mcp` | C-004 | `external/ocx`, `Cargo.toml`, `src/**` | 2 | WP1 | pending |
| WP4 | `.` | C-005 (lockstep integration) | `.github/workflows/*` | 3 | WP2, WP3 | pending |

WP2 and WP3 declare textually identical `Expected Files` and are
nonetheless disjoint, because the disjointness key is `(Repo, path)`
(C-316) — different repos, FM5's upside. They run in parallel; merges
are one global serialization; the review
panel sees the union of three diffs; every satellite commit carries a
`Hex-Plan:` trailer so convergence can find it.

**Trade-offs.** Reuses every existing hex contract — one Status block,
one ID space, one WP table, one `Depends-on` DAG, one convergence check —
and adds one optional column plus one bullet grammar. Costs: a documented
launch requirement (`--add-dir`), a new class of write (into a repo the
session did not start in), and it does **not** solve FM7. **Adopt.**

### Option F — Independent plans per repo, linked by ID (do nothing)

Each repo runs its own `/hex-plan`; the lead plan's Overview links the
others; humans sequence the merges.

**Worked example.** Three plans, three Status blocks, three review runs.
`ocx-mirror`'s reviewer never sees `ocx`'s diff; the lockstep assertion
that both satellites are green against the *same* `ocx` SHA is nobody's
job — which is today's state, and is how `0.17` and `0.16` came to
disagree.

**Trade-offs.** Zero work, zero risk, and for genuinely loosely coupled
repos it is correct — it is spec-kit's maintainer position. It fails
exactly where coupling is tight. **Keep as the documented default; D+E is
the opt-in.**

## Decision Outcome

**Chosen: Option D+E — the lead repo owns the change, executed in
multi-root worktrees — with Option C as its substrate and Option B
retained for published contracts only. Options A and A′ rejected (A′
with a named revisit trigger); Option F stays the documented default.**

This adopts the research's recommendation, with **three corrections it
got wrong on the evidence of the real cluster**:

1. **The repo-identity probe is `--git-common-dir`, not
   `--show-toplevel`** (research `:476`). Verified above: all four `ocx`
   worktrees pass the proposed probe. Two "repos" sharing one history and
   one branch namespace would break file-disjointness and the merge
   serialization simultaneously. C-303 fixes this.
2. **Satellite feature branches are created from the satellite's own
   trunk, never from a checked-out non-trunk branch** — the research
   inherits `protocol.md:363-367` unexamined, and `ocx-mirror` sitting on
   `feat/pypi-mirror` breaks the shared slug the research makes the join
   key. C-304 fixes this.
3. **The Federation block is bullets under the existing `## Pointers`, not
   a new `## Federation` section** (research `:461-471,:561-563`).
   `memory.md:26` documents exactly three sections; a satellite path is
   "a cached location discovered from project context", which is the
   Pointers row's own definition (`memory.md:35`), with the right
   ownership (skill-managed, re-pointable, never authoritative). And the
   research's `Verification` **column caches the command literal** —
   a copy, not a pointer, of knowledge that lives in the satellite's
   project context. `bun test` vs `task verify` vs `vscode-test` across
   this cluster is precisely the kind of value that drifts. C-301 stores
   a *pointer to where the satellite documents verification*, matching
   the Pointers row's "cached locations discovered from project context"
   definition (`memory.md:35`). Note that the shipped example bullet
   (`memory.md:49`) caches the command literal *alongside* its pointer
   for the **own** repo, where verify-on-consumption re-reads it every
   run; a satellite's command is not re-read on the same cadence, so
   C-301 carries the pointer only.

### Weighted scoring

**Feasibility gate.** Option B cannot carry an in-flight change at all —
it distributes released artifacts — so it is infeasible against FM1, FM3,
FM4, FM5, FM7 and FM8 and its total is informational. Scores 1–5, higher
is better.

| Criterion | W | A | B† | C | **D+E** | F |
|---|--:|--:|--:|--:|--:|--:|
| Coverage of the eight failure modes | 30 | 3 | 1 | 2 | **5** | 1 |
| New machinery / `DESIGN.md` conformance | 20 | 1 | 4 | 5 | **4** | 5 |
| Silent-failure resistance (esp. FM6) | 15 | 1 | 4 | 2 | **4** | 3 |
| Authoring + ergonomic cost | 10 | 2 | 2 | 4 | **3** | 5 |
| Works on today's runtime, unmodified | 10 | 2 | 5 | 5 | **4** | 5 |
| Portability across four harnesses | 10 | 3 | 3 | 5 | **4** | 5 |
| Reversibility after first release | 5 | 2 | 3 | 5 | **4** | 5 |
| **Weighted total (max 500)** | | 205 | *285* | 355 | **420** | 350 |

† Infeasible against the settled requirement set; total is comparative
only.

Read the near-tie between C (355) and F (350) as the finding it is:
**pointers alone barely beat doing nothing.** They tell a worker where
the other repo is and change nothing about how work is coordinated. D+E's
65-point lead is entirely in the coverage row, and it buys that with one
table column, one bullet grammar, one commit trailer and one refusal —
all constructs hex already owns.

D+E loses points against C and F on conformance, cost, runtime and
reversibility for one reason each: it amends the one-feature-branch rule,
it requires a `--add-dir` launch, it introduces a write into a foreign
repo, and the `Repo` column values become a soft compatibility surface
once plans exist that use them. Each is priced in the sections below.

### Failure modes → mechanism

The acceptance criteria, answered explicitly. Two are *not* solved.

| FM | Answered by | How |
|---|---|---|
| **FM1** one proposal, N repos | **C-302, C-307** | One artifact in the lead, **one** Status block, one ID space. Satellite repos hold no plan copy; their only local trace is the `Hex-Plan:` commit trailer, which is a pointer, not a second record. |
| **FM2** spec drift A→B | **Option B (published)** + **C-302 (in-flight)** | For a released contract, grim digest-pinning makes drift a lockfile diff. For an in-flight change, both consumers are WP rows on one plan, so the bump is one decision, not two independent ones. Not solved for a consumer *outside* the plan — see Consequences. |
| **FM3** traceability across the boundary | **C-307, C-310** | `C-`/`S-` IDs stay plan-scoped and are therefore global to the change. Satellite commits carry `Hex-Plan:`, so `git -C <repo> log --grep` recovers the join key. |
| **FM4** review blind at the seam | **C-309, C-320** | C-320's pre-flight halts a review that cannot reach every participating repo, so the union is never silently narrower than the plan. The resolved review scope is the **union** of `git -C <repo> diff <base>...hex/<plan-slug>` over the lead and every repo appearing in the `Repo` column. `hex-review/SKILL.md:298`'s stay-in-scope rule is unchanged; only the scope's definition generalizes. |
| **FM5** worktrees across repos | **C-305, C-306, C-316, C-317** | N worktrees in N repos via `git -C`; each belongs to the repo whose history it checks out. File-disjointness is free across repos **only because the disjointness key is `(Repo, path)`** (C-316) — compared as bare paths, satellites declaring `Cargo.toml` would collide. N frozen bases, all resolved at execution start (C-317). Merges are serialized per repo (correctness) and ordered by `Depends on` across repos (correctness); the orchestrator additionally executes them one at a time globally because it is one sequential actor — an operability choice, stated as such in C-306. |
| **FM6** memory split brain | **C-323 (structural), C-303, C-308, C-313** | The load-bearing guard is **C-323**: federated execution is lead-originated by construction — a run whose own resolved `hex.md` carries no `Federation:` bullets cannot resolve a satellite path, so it is not federated, and it **halts** rather than executing a plan that carries a `Repo` column. That holds on a virgin satellite, a fresh clone and a second machine, with nothing written anywhere in advance. C-308's back-pointer is the **early, better-worded** refusal on top of it (it names the lead), not the thing the guarantee rests on. The bullet is a **filesystem** fact written into the satellite's main checkout, so it is live the moment it is written — it does not wait on any branch landing (C-308 point 2). C-313 gives it a lifecycle so it expires with the plans that created it. This is the highest-severity item here and it is answered with a refusal, not a warning. |
| **FM7** who archives / partial landing | **NOT SOLVED — C-312; bounded by C-324** | There is no atomic cross-repo merge and there never will be. A partially landed change is a real broken-integration window. hex does not track trunk landings today and does not start; the handoff **enumerates the per-repo feature branches and the required landing order**, and that is all. What C-324 adds is that the window is *held open in the plan*: a federated plan stops at State `landing`, not `done`, so the satellite locks (C-313) do not expire while the integration is broken. Cost stated in Consequences. |
| **FM8** verification has no home | **PARTIALLY — C-306, C-311** | Per-repo post-merge verification is the *owning* repo's, read explicitly from that repo's project context. The genuinely homeless check — "both satellites green against the same `ocx` SHA" — is an ordinary integration WP row whose command is written **inline in the plan**, because the plan is the only artifact that spans repos. No new construct, but also no pointer: the command lives as prose in the one place that owns the change. What C-311 does make mechanical is its *shape*: the check must name every participating repo and the exact state each must be at, and report per-repo pass/fail — an aggregate "all green" is not evidence. |

### Normative specification

Nothing below introduces a file format, a parser, or a marker version.
C-324's `Repos:` ledger is lines inside the Status block hex already
owns and reads every run, and `landing` is one more value in a State
sequence that already has five.

**1. Federation pointers (C-301).** Zero or more bullets under the
existing `## Pointers` heading in the **lead** repo's
`.agents/memory/hex.md`. Fixed grammar, one satellite per bullet:

```markdown
- Federation: `mirror` → `../ocx-mirror`
  (`https://github.com/ocx-sh/ocx-mirror.git`); verification documented in
  its `CLAUDE.md` › "Verify".
- Federation: `mcp` → `../ocx-mcp`
  (`https://github.com/ocx-sh/ocx-mcp.git`); verification documented in
  its `CLAUDE.md` › "Verify".
```

- The **key** is the value used in the plan table's `Repo` column. Lead
  is always `.` and is **never** listed.
- The **path** is relative to the lead repo root. Absolute paths are
  permitted and are what a `--add-dir` relaunch line prints.
- The **remote** is recorded for identity, not for fetching. hex never
  clones, fetches, pulls or pushes.
- The **verification clause is a pointer, never a command literal** —
  the Pointers row's own definition (`memory.md:35`); unlike the shipped
  own-repo example (`memory.md:49`) it does **not** cache the command.
  Verify-on-consumption applies: a
  worker acting on it re-reads the target and re-points on a miss
  (`memory.md:123-126`).
- **Vacuous when absent.** No `Federation:` bullet ⇒ single-repo ⇒ every
  rule below is inert and every existing project behaves byte-identically.

**2. Satellite back-pointer (C-308).** In each satellite's own
`.agents/memory/hex.md`, one bullet under `## Pointers`:

```markdown
- Federation lead: `../ocx` — this repo participates as satellite key
  `mirror` for plan(s): `ocx-lib-v050`. Run hex orchestrators from the
  lead, not here.
```

The trailing **plan-slug list is part of the grammar, not decoration**:
it is what makes C-313's removal decidable and what tells a human reading
the satellite why it is locked. A slug is appended on first worktree
creation for that plan; the list never holds duplicates.

The file is created holding only this bullet if the satellite has none
(true for `ocx-mirror` and `ocx-mcp` today — neither has
`.agents/memory/`). Written lazily by `/hex-execute` at first
satellite worktree creation, disclosed at the existing meta-plan gate —
**never a second gate** (`protocol.md:45-49`).

**Where the write lands (durability).** The bullet is written into the
satellite's **main checkout working tree** — `<path>/.agents/
memory/hex.md` — and **never** inside the ephemeral WP worktree or on
the `hex/<plan-slug>` branch. This is load-bearing: memory resolution
reads the **filesystem**, not git, so the FM6 guard is live the instant
the file is written and does **not** depend on C-312's untracked landing
step. A stalled or abandoned satellite PR therefore cannot reopen FM6 on
this machine.

hex leaves the write **uncommitted** (untracked, in the general case)
and reports it in the handoff as a working-tree change for the human to
commit. hex does not commit it because both alternatives are worse: the
satellite's checked-out branch may be unrelated in-flight work
(`ocx-mirror` on `feat/pypi-mirror` — committing bookkeeping there is a
foreign write into someone else's change), and committing it on the
plan's branch would make the guard hostage to a landing hex explicitly
does not track. The cost is stated in Consequences: **until a human
commits it, the guard is machine-local** — a fresh clone of the
satellite starts with FM6 open, and the next federated run from the lead
re-writes it. C-303 (iii)'s `status --porcelain` check accepts this
file's presence in the dirty set; it never treats hex's own back-pointer
as a blocking dirty tree.

**3. The refusal (C-308).** Every orchestrator, in its
resolve-memory step (`hex-execute/SKILL.md:60-71` and the three
equivalents): if the resolved `hex.md` carries a `Federation lead:`
bullet, **halt** and print

```
Error: this repo is a federation satellite (key `mirror`) for active
       plan(s) `ocx-lib-v050`; its swarm memory is not the plan's memory.
Fix:   cd ../ocx && claude --add-dir <this repo> …   # then re-run
       (or, if that plan is finished, delete the `Federation lead:`
        bullet from this repo's hex.md — see C-313)
```

**`memory.md` is the single definition site for this text.** The four
`SKILL.md` resolve-memory steps each add **one line referencing it** —
"if the resolved `hex.md` carries a `Federation lead:` bullet, halt per
[`memory.md`](…) § Location and resolution" — and never restate the
`Error:`/`Fix:` block. Four copies of a halt message is exactly the
copy-drift `DESIGN.md:36` forbids, and the precedent is `protocol.md`
owning the Review-Fix Loop while every tier file links to it.

**Scope of the halt, and its one exemption.** The halt fires on the
bullet's presence, unconditionally, for `/hex-plan`, `/hex-execute`,
`/hex-review` and `/hex-architect` — a satellite that is mid-federated-
change must not accumulate a second, competing active plan, and
distinguishing "related" from "unrelated" local work is exactly the
judgement call that produced FM6 in the first place. **`/hex-init` is
exempt**: it writes no plan, resolves no active-plan pointer, and must
stay runnable so a satellite can be audited (and so C-313's removal can
be offered). Escape hatches are two, both cheap and both printed in the
`Fix:` line: relaunch from the lead, or delete the bullet (C-313).

Halt, never degrade. A satellite with *no* memory file is the benign
case: upward search finds nothing, the orchestrator falls back to shipped
defaults and has no active-plan pointer, so it stops and asks for a
target (`hex-execute/SKILL.md:80-82`) — visible, not silent.

**4. Plan-table column (C-302).**

- **Name:** `Repo`. **Position:** second, immediately after `WP`.
- **Values:** a Federation key, or `.` for the lead.
- **Default:** `.` — an empty cell means the lead.
- **Vacuous when absent:** a plan with no `Repo` column is entirely
  lead-local. **There is no schema-version marker; the presence of the
  column is the signal** — the same discipline as `adr_0002` C-105's
  dotted sub-WP IDs and its "old plans byte-identical" rule.
- Sub-WP rows inherit the parent's `Repo` when the cell is empty, exactly
  as `Depends-on` already inherits (`protocol.md:421-422`) and `Review`
  does in the template comment (`plan.md:133`). A sub-WP **never** names
  a different repo than its parent: only leaf rows are branch- and
  worktree-eligible (`protocol.md:414-417`), so a cross-repo split
  belongs at WP grain, not sub-WP grain.
- `Expected Files` for a satellite WP are **repo-relative to that
  satellite**, because merge-time file-set re-validation runs
  `git -C <repo> diff --name-only` (`protocol.md:390-397`).

**5. Pre-flight access check (C-303).** In `/hex-execute` step 1, after
reading `hex.md` and before any worktree is created, for every Federation
key **that the resolved plan actually uses**:

```bash
git -C <path> rev-parse --show-toplevel                          # (i)
git -C <path> rev-parse --path-format=absolute --git-common-dir  # (ii)
git -C <path> status --porcelain                                 # (iii)
mkdir -p <path>/.agents && : > <path>/.agents/.hex-write-probe \
  && rm <path>/.agents/.hex-write-probe                          # (iv-a)
git -C <path> update-ref refs/hex/write-probe HEAD \
  && git -C <path> update-ref -d refs/hex/write-probe            # (iv-b)
git -C <path> symbolic-ref --short refs/remotes/origin/HEAD      # (v)
git -C <path> check-ignore -q .agents/worktrees/                 # (vi)
```

Six refusals, all halting:

- **(i) must resolve to `<path>` itself.** `git -C` walks *up*: a
  non-repo path nested inside another repo silently reports the enclosing
  repo. This is OpenSpec's `isGitRepositoryAtRoot`-first rule
  (`src/commands/doctor.ts`), adopted verbatim in intent.
- **(ii) must differ from the lead's `--git-common-dir`.** Equality means
  the path is another **worktree of the lead**, not a separate repo —
  `ocx-evelynn` reports `/home/mherwig/dev/ocx/.git`, identical to `ocx`.
  Two such rows would share one history and one branch namespace.
- **(iii) must succeed.** Failure means the session cannot even read the
  repo.
- **(iv) must succeed — the write probe.** (i)–(iii) prove *readability*
  only, and every federated write comes later: a branch, a worktree, a
  back-pointer, commits, a merge. A read-only grant passes (i)–(iii) and
  then fails partway through execution, which is the half-executed plan
  C-303 exists to prevent. So the pre-flight writes, twice, and undoes
  both immediately: **(iv-a)** a zero-byte file under the satellite's
  `.agents/` (the directory C-305's worktree will live in) proves
  working-tree writability; **(iv-b)** a ref under `refs/hex/`, created
  from `HEAD` and deleted in the same breath, proves git-directory
  writability — it points at an existing commit, fast-forwards nothing,
  moves no branch and is namespaced away from `refs/heads/` and
  `refs/tags/`. Both are non-destructive: they leave the repo
  byte-identical whether they pass or fail. If (iv-a) fails, `.agents/`
  may have been created and is left in place — it is the same directory
  C-305 needs and is inert if the run halts. Failure of either **halts**
  with the same `Error:`/`Fix:` pair.
- **(v) must resolve a trunk, or halt** — see C-304's discovery order.
  Trunk is resolved in the pre-flight, not at branch-creation time,
  because C-317 freezes every base in this same step.
- **(vi) `.agents/worktrees/` must be ignored, or halt.** C-305 creates
  the satellite worktree under `.agents/worktrees/`, and gitignoring that
  path is a `/hex-init` audit (`DESIGN.md:142-145`) — but `/hex-init` is
  **exempt in satellites** (C-308) and a satellite may never have run it,
  so nothing guarantees the path is ignored. An un-ignored checkout would
  dirty that repo's `status --porcelain` and risk being committed onto the
  feature branch. `git -C <path> check-ignore -q .agents/worktrees/` must
  succeed; on a miss, **halt** and offer to add the ignore line —
  `.agents/worktrees/` specifically, **never** `.agents/` wholesale, since
  `.agents/memory/hex.md` is version-controlled (`DESIGN.md:142-145`).

**No cross-repo mutation happens before all six pass for every key the
plan uses.** The pre-flight is a barrier, not a per-repo gate: the first
`git -C <satellite> branch` of the run is issued only after the last key
has cleared. A cluster that is partially writable therefore produces zero
writes, exactly as a partially readable one does.

**The probe is the one write that precedes consent**, and it is stated
rather than hidden: it runs before the meta-plan gate because its whole
purpose is to fail before the gate promises something the session cannot
deliver. It is self-undoing, leaves no git object and no branch, and its
outcome is disclosed as the `writable` token in the echo line the gate
displays. The alternative — probing after approval — moves the failure
past the point where the human has already agreed to the run.

On any failure, **halt with a pasteable relaunch line** rather than
degrade — a skill cannot grant itself directories mid-session, and
skipping a repo produces a half-executed plan:

```
Error: Federation path `../ocx-mirror` is not accessible from this session.
Fix:   claude --add-dir /home/mherwig/dev/ocx-mirror \
              --add-dir /home/mherwig/dev/ocx-mcp
```

One ancestor grant covers a whole sibling cluster (`--add-dir
/home/mherwig/dev`) and is the cheapest ergonomic form; print the
narrowest form that works.

**The pre-flight leaves evidence.** Clauses (ii) and (iii) fail loudly
on their own — a bad path produces an ordinary `git` error even if the
check is skipped. Clause (i) is the one rule here where **skipping it is
silent**: `git -C` walking up into an enclosing repo *succeeds*, and
every later worktree, branch and commit then operates on the wrong repo
with no git-level signal. So the pre-flight's outputs are not merely
consumed, they are **echoed** — one line per key in the run's announce
block, before approval:

```
Pre-flight: mirror  ../ocx-mirror  toplevel=/home/mherwig/dev/ocx-mirror
                    common-dir=/home/mherwig/dev/ocx-mirror/.git
                    clean  writable  trunk=main (origin/HEAD)
            mcp     ../ocx-mcp     toplevel=/home/mherwig/dev/ocx-mcp
                    common-dir=/home/mherwig/dev/ocx-mcp/.git
                    clean  writable  trunk=main (CLAUDE.md › Branches)
```

A reader can verify by inspection that `toplevel` equals the declared
path, that no two `common-dir` values coincide — including the lead's —
that every repo is `writable`, and that each `trunk` is the branch they
expect with the source it came from. Absent this line the check is
unauditable, which for clause (i) means indistinguishable from not
having run.

**6. Branches (C-304).** The `<plan-slug>` is the git-level join key and
is **identical in every participating repo**.

- **Lead:** unchanged — the non-trunk branch already checked out, else
  `hex/<plan-slug>` from trunk (`protocol.md:363-367`).
- **Satellite:** always `hex/<plan-slug>` created from **that repo's own
  trunk**, never from whatever branch is checked out there. The
  checked-out-branch clause is suspended for satellites. When a satellite
  had a non-trunk branch checked out (`ocx-mirror` on
  `feat/pypi-mirror`), announce it at the gate — it is a signal of
  unrelated in-flight work in that repo, which is a scheduling fact the
  human needs.
- Ephemeral per-WP branches are unchanged: `hex/<plan-slug>--<wp-slug>`
  in the owning repo (`protocol.md:368-372`).

**Trunk discovery, in order — `main` is never assumed.** "That repo's own
trunk" is not a constant: hex has no cross-repo default, and C-318
forbids reading a satellite's swarm memory, so trunk must be *discovered*
per satellite, in C-303's pre-flight, in exactly this order:

1. `git -C <path> symbolic-ref --short refs/remotes/origin/HEAD` →
   `origin/<trunk>`; strip the remote prefix. This is the repo's own
   recorded answer and is authoritative when present.
2. If (1) fails — common in clones that never ran
   `git remote set-head`, and in repos with no `origin` — read that
   repo's **project context** explicitly (C-306's never-assume `Read`)
   and take the trunk it documents.
3. If neither resolves, **halt and ask**, naming the repo:

```
Error: cannot determine the trunk branch of Federation key `mcp`
       (../ocx-mcp): no refs/remotes/origin/HEAD, and its project
       context documents no trunk.
Fix:   git -C ../ocx-mcp remote set-head origin --auto   # then re-run
       (or name the trunk in that repo's project context)
```

Whatever (1) or (2) yields must exist locally —
`git -C <path> rev-parse --verify refs/heads/<trunk>` — or the same halt
fires. hex never fetches (C-305), so trunk is always the local ref as it
stands; a stale local trunk is a stale base, which is why C-324 records
the resolved SHA where a human can see it. The resolved trunk and its
source are echoed in the pre-flight line.

**7. Worktrees (C-305).** Verbatim, for satellite key `mirror`, WP slug
`bump-ocx-lib`:

```bash
git -C ../ocx-mirror fetch --no-tags origin        # optional, human's call; hex never fetches on its own
git -C ../ocx-mirror branch hex/ocx-lib-v050 <base>   # the frozen SHA from
                                                     # the plan's Repos:
                                                     # ledger (C-324),
                                                     # never a branch name
git -C ../ocx-mirror worktree add \
    .agents/worktrees/bump-ocx-lib hex/ocx-lib-v050--bump-ocx-lib
```

The worktree lives under the **satellite's** `.agents/worktrees/`, not
the lead's: `git worktree` records the checkout in the owning repo's
admin directory, and each repo already gitignores its own
`.agents/worktrees/` (`protocol.md:433-437`) — `ocx/.agents/worktrees`
already exists on disk. A lead-side path would require every satellite to
ignore a foreign directory. Removal after merge is
`git -C ../ocx-mirror worktree remove …` plus the branch delete, as today.

**8. Merge serialization (C-306).** **One global topological order over
all WP rows regardless of repo.** One merge in flight at a time, never a
batch.

Two distinct claims, kept apart because they have different strengths:

- **Correctness requires exactly two things.** (a) Within one repo,
  merges are serialized — the existing rule (`protocol.md:385-389`),
  unchanged, because each merge moves the base under the next. (b)
  Across repos, merges are ordered wherever a `Depends on` edge crosses
  the boundary, which the DAG already enforces. Nothing more is
  *required*: WP2 (`mirror`) and WP3 (`mcp`) touch different
  repositories with no shared object store and no edge between them, so
  no correctness argument orders them relative to each other. The
  earlier framing — "the edge that matters crosses the boundary" —
  justifies ordering WP4 after WP2 and WP3 and nothing else.
- **Global one-at-a-time is adopted for operability, and that is the
  honest reason.** The orchestrator is a single sequential actor: each
  merge is followed by the owning repo's verification, whose failure
  triggers a one-pass fix playbook and possibly a halt
  (`protocol.md:398-405`). Running two merge-plus-verify cycles
  concurrently means two possible halts racing for one session's
  attention and a `Status` column written from two places, so resume
  after an interrupt could not be reconstructed from the table alone.
  The cost is wall-clock, it is priced in the NFR table, and the rule is
  the first thing to relax if merge time ever dominates — cross-repo
  merges genuinely can run concurrently.

- Each merge is `git -C <repo> merge` onto **that repo's**
  `hex/<plan-slug>`.
- After each merge, run the **owning repo's** documented verification,
  discovered by an **explicit `Read`** of that repo's project context —
  `--add-dir` does not load a satellite's `CLAUDE.md` without
  `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`, so ambient context
  must never be assumed.
- Cross-repo dependency edges are ordinary `Depends on` entries; the
  `adr_0002` C-101 ready-set launcher needs no change — a satellite WP
  becomes eligible when its deps are `merged`, whichever repo they are
  in.
- Merge-conflict / post-merge-failure playbook is unchanged
  (`protocol.md:398-405`), including its halt-after-one-fix-pass rule.
- The concurrency cap counts across repos, not per repo
  (`protocol.md:208-220`).

**9. Commit trailer (C-307).** Every commit hex makes in a satellite
carries, in the commit message's trailer block:

```
Hex-Plan: ocx-sh/ocx:.agents/plans/plan_ocx_lib_v050.md
```

`<remote-slug>:<repo-relative plan path>`. Ordinary git trailer syntax —
no new format, `git interpret-trailers`-compatible, and recoverable with
`git -C ../ocx-mirror log --grep='Hex-Plan: ocx-sh/ocx:…'`. The WP is not
in the trailer; it is derivable from the ephemeral branch name. Lead
commits do not need it (the plan is in the same repo) but may carry it
harmlessly.

**10. Review scope (C-309).** For a target that traces to a plan
carrying a `Repo` column, the resolved diff scope is the union over the
lead plus every distinct `Repo` value:

```bash
git -C <repo> diff <base>...hex/<plan-slug>
```

`<base>` is **read from the plan's `Repos:` ledger** (C-324), never
re-resolved from a trunk ref that may have moved since execution started.
Presented to the panel as one diff set, per-hunk labelled with its repo.
`hex-review`'s never-edits contract (`hex-review/SKILL.md:278,:286`) and
its stay-in-scope rule (`:298`) are unchanged in text; only the scope's
construction generalizes.

**11. Convergence (C-310).** Unchanged in mechanism
(`protocol.md:487-504`): the 4-way gap taxonomy keyed by `C-`/`S-` IDs,
gaps appended as new WP rows with derived waves, existing rows never
rewritten. Federated additions: coverage is evaluated against the **union
diff**, satellite delivery is located via the `Hex-Plan:` trailer, and an
appended gap row carries a `Repo` value like any other row. A convergence
delta originating from a work package whose `Repo` is **not** `.` (a
satellite) is **not** folded into the lead's spec — it is reported
"delivered in `<repo>`, fold by hand" and left in the plan, deferring to
sibling [`adr_0005`](adr_0005_archive_fold_back.md)'s lead-scoped
Fold-Back rule (the fold owner): a fold has no correct destination across
a repo boundary, so the boundary-crossing delta is surfaced, not folded.

**12. Integration WP (C-311).** A cross-repo change **must** carry at
least one integration WP row depending on every satellite WP it joins
(WP4 in the worked example). hex already has this construct — it is an
ordinary row, the same shape as a coordinator join
(`protocol.md:430-431`). Because its check belongs to no repo, its
command is written **inline in the plan's Implementation Steps**, not
resolved from any repo's project context.

**The inline check is a per-repo table, not a sentence.** This is the one
gate between "we changed three repos" and "we know they still work
together", and C-321 deliberately supplies no implicit federated verify
gate — so if this check is free prose, the whole cross-repo guarantee
rests on an LLM's reading of a sentence. It therefore has a fixed
minimum shape: one row per participating repo (the lead and **every**
distinct `Repo` value, no exceptions), each naming the exact state that
repo must be at and the command that proves it, each reported
independently:

```markdown
### WP4 — integration check (run from the lead, after WP2 and WP3 merge)

| Repo | Required state | Command | Result |
|---|---|---|---|
| `.` | `hex/ocx-lib-v050` @ `<merge SHA>` | `cargo test -p ocx_lib` | |
| `mirror` | `hex/ocx-lib-v050` @ `<merge SHA>`, `external/ocx` = `<ocx SHA>` | `git -C ../ocx-mirror … && cargo tree -i oci-client` | |
| `mcp` | `hex/ocx-lib-v050` @ `<merge SHA>`, `external/ocx` = `<ocx SHA>` | `git -C ../ocx-mcp … && cargo tree -i oci-client` | |
```

- **Required state is verified, not assumed.** Before running its
  command, each row's `git -C <repo> rev-parse hex/<plan-slug>` (and, for
  a submodule pin, the recorded SHA) must equal what the row names. A
  mismatch fails that row — it means the repo is not at the state the
  check was written for, which is precisely the drift the check exists to
  catch.
- **Per-repo results, never an aggregate.** The WP reports one pass/fail
  per row. A single "integration green" line is not evidence and does not
  satisfy C-311; nor does running the command only in the lead.
- **Any missing, unresolved or failed row fails the WP**, with the merge
  playbook's ordinary consequences (`protocol.md:398-405`).
- **Plan-time enforcement.** A plan carrying a `Repo` column whose
  integration WP does not enumerate the lead plus every distinct `Repo`
  value is incomplete: `/hex-plan` does not emit it (C-314) and the
  meta-plan gate rejects it. The check is mechanical — compare two sets
  of strings — which is the point of making it a table.

For the worked example the substance is unchanged ("`cargo tree -i
oci-client` green in both satellites against the same `external/ocx`
SHA"); what changes is that each satellite is named, its required SHA is
written down, and each reports for itself. (`cargo-semver-checks` is the
off-the-shelf form of the lead's row here — see D-10.)

**13. Landing (C-312, the non-answer).** hex still never pushes. Trunk
landing per repo remains the human's step and hex records **no landed
status it did not observe locally**. What C-324 adds is that a federated
plan does not reach `done` while the window is open: the lead's review
advances it to `landing`, and the satellite locks stay on until every
repo's row in the plan's `Repos:` ledger is confirmed landed. The handoff
must enumerate:

```
Feature branches to land, in this order:
  1. ocx-sh/ocx          hex/ocx-lib-v050
  2. ocx-sh/ocx-mirror   hex/ocx-lib-v050
  3. ocx-sh/ocx-mcp      hex/ocx-lib-v050
Between 1 and 2 the satellites do not build against ocx trunk.
```

That window is real and named, not prevented. Note that this is not a
weak position relative to the field: Gerrit Topics, the most mature
production cross-repo review system, explicitly documents that
submission across repositories is not atomic and may partially succeed —
and it prints no landing order at all. C-312 names the window and orders
the landings, which is strictly more than the state of the art offers.

**14. Back-pointer lifecycle (C-313).** The C-308 bullet is a **lock on
running hex locally in a satellite**, so it must expire with the thing
that justified it.

- **Write:** `/hex-execute` appends the plan slug at first satellite
  worktree creation for that plan, creating the bullet if absent (C-308).
- **Remove:** `/hex-execute`'s upkeep step, when a plan whose table uses
  the `Repo` column reaches **State `done`** — which, per C-324, means
  every repo's row is confirmed landed, so the lock outlives the
  broken-integration window rather than expiring inside it — removes that
  slug from
  every participating satellite's bullet. When the slug list becomes
  **empty, the whole bullet is deleted** — and the `hex.md` file too, if
  the bullet was its only content (the common case: a satellite that had
  no memory file before). The satellite is then exactly as it was, and
  local hex use is unlocked.
- **Also removed** when the plan is abandoned: `/hex-init` in a
  satellite offers removal for any slug whose plan no longer exists in
  the lead, or exists with State `done`, resolving the lead by the
  bullet's own path. This is the re-audit shape already used for stale
  pointers (`memory.md:123-126`), and it is why `/hex-init` is exempt
  from the C-308 halt.
- **Manual removal is always legitimate.** Deleting the bullet by hand
  is a supported action, printed in the halt's `Fix:` line. The bullet
  is skill-managed, never authoritative (`memory.md:35`); the worst case
  of removing it early is the pre-C-308 status quo for that repo, which
  the next federated run repairs.
- **Never** removed silently as a side effect of anything else, and
  never rewritten to point at a different lead — a satellite that would
  need two leads is a design smell the human should see, so a second
  `Federation lead:` bullet with a different path **halts** at the
  pre-flight.

**15. Planning-side discovery (C-314).** The `Repo` column does not
populate itself. `/hex-plan`'s Discover phase, at the same point it
reads `hex.md › Pointers` for every other cached location, collects the
`Federation:` bullets; its Decompose phase then offers **per-repo
decomposition**: any WP whose scope lies in a satellite gets that
satellite's key in `Repo`, and C-311's integration row is added.

- Absent `Federation:` bullets, nothing is offered, no `Repo` column is
  emitted, and the plan is byte-identical to today (S-301). The bullets'
  presence is the only signal — no flag, no marker.
- The keys offered are exactly the declared ones. `/hex-plan` never
  discovers a sibling repo by scanning, never proposes a repo that has
  no bullet, and never writes anything into a satellite (only
  `/hex-execute` writes there, per C-308).
- `/hex-plan` does **not** run the C-303 pre-flight. Planning needs no
  access to the satellites; a plan naming an unreachable repo is caught
  at execution, with the relaunch line, before any write.

**16. The gate's federation line (C-315).** When a plan carries a `Repo`
column, the meta-plan approval gate's announce block
(`protocol.md:45-49`) gains **one line**, in the same
`<label>: <resolved value> (<source>)` shape as the existing `Degraded:`
line, placed immediately after it:

```
Federation: lead `.` + mirror, mcp — 3 repos, 4 WPs (2 satellite)
            ../ocx-mirror on `feat/pypi-mirror` — unrelated in-flight work
            back-pointer to be written in: mirror, mcp   (hex.md Pointers)
```

- **Line 1** is mandatory: the lead, every distinct `Repo` value in
  table order, then repo count, WP count and the satellite-WP count in
  parentheses.
- **Line 2** appears once per satellite found on a non-trunk branch
  (C-304) — the scheduling fact, named, not silently discarded.
- **Line 3** appears only when a back-pointer will be written that does
  not already exist, and is the disclosure C-308 requires. It is a
  disclosure at the **existing** gate, never a second gate.
- The C-303 pre-flight echo lines (point 5) sit under this block at
  execution.
- Absent a `Repo` column the whole block is absent. The `Degraded:`
  line and every other line are unchanged.

**17. File-set disjointness is keyed by `(Repo, path)` (C-316).** The
plan-time set-intersection check (`protocol.md:280-284`) and the
concurrency invariant (`protocol.md:383-384`) both compare **file sets**.
`Expected Files` are repo-relative (C-302), so two WPs in different repos
routinely declare **textually identical** paths — WP2 and WP3 of the
worked example both declare `external/ocx`, `Cargo.toml`, `src/**`. Read
as bare paths, those sets intersect and the two WPs may not share a wave;
read as `(Repo, path)` pairs they are disjoint, which is FM5's stated
upside.

- The invariant is therefore: **concurrently-running WPs must own
  disjoint sets of `(Repo, path)` pairs.** The lead's rows carry `.` and
  compare as they always did.
- Merge-time re-validation is unchanged in shape and already repo-scoped:
  `git -C <repo> diff --name-only` is compared against that WP's
  satellite-relative declared set (`protocol.md:390-397`).
- **Vacuous single-repo:** with no `Repo` column every pair is `(., p)`,
  so the check is the existing path comparison, byte-for-byte.
- This generalizes a locked `DESIGN.md` decision and is recorded as a
  deviation row.

**18. One frozen base per participating repo (C-317).** The frozen base
rule (`protocol.md:365-367`) is per feature branch, and C-304 gives a
federated plan one feature branch per repo. So there are **N frozen
bases**, one per participating repo, **all resolved at execution start in
the same pre-gate step** (C-303's, where trunk is discovered) — never
re-resolved mid-run when a satellite is first touched, which would make a
wave-1 satellite WP branch from a moving baseline.

**Frozen means written down.** "Resolved together" is worthless if the
value does not outlive the session that resolved it: a resumed run, a
later `/hex-review`, and convergence all need the *same* `<base>` that
C-309's `git -C <repo> diff <base>...hex/<plan-slug>` and merge-time
re-validation used, and a trunk ref that has moved since is a different
answer to the same question. So each repo's base is persisted as a **full
40-character SHA** in the plan's `Repos:` ledger (C-324), and every later
consumer **reads it there rather than re-resolving it**. A WP's base is
its own repo's row; `<base>` in C-309 and in the merge-time diff is
always that SHA, never a branch name.

**19. Preferences and Pointers are the lead's, exclusively (C-318).** A
federated run resolves **exactly one** `hex.md` — the lead's — and the
C-308 halt guarantees no run resolves a satellite's. Made explicit
because `hex.md` has three owned sections with three different owners
(`memory.md:26-37`) and a second repo's copy would silently compete:

- **`Preferences`** (user-owned): the model matrix, adversary skill,
  always-on perspectives and `max-workers` all come from the **lead**. A
  satellite's `Preferences` are never read, never merged, never
  reconciled. Consequence: the effective cap is
  `min(8, lead's max-workers)` (`protocol.md:208-220`), counted
  recursively **and across repos** — a satellite cannot raise or lower it.
- **`Pointers`** (skill-owned): the lead's, plus — for a satellite —
  exactly the one clause C-301's own bullet carries. A satellite's
  `Pointers` file is not consulted; satellite verification and project
  rules are read from that repo's **project context** by explicit `Read`
  (C-306), which is where they authoritatively live (`memory.md:89-113`).
- **`Memory`** (skill-owned): the active-plan pointer lives in the lead
  only. Satellites never get one — that is precisely FM6.
- No cross-repo merge, precedence or "nearest wins among several" rule is
  introduced: `memory.md:9-13`'s single upward search is unchanged, and
  `memory.md:14-16`'s no-section-sharing posture is untouched.

**20. The depth chain is unchanged (C-319).** Federation adds **no
recursion level**. The orchestrator that owns the federated plan is *the*
orchestrator; it drives satellites with `git -C` and ordinary leaf
workers, and it **never spawns a per-repo `/hex-execute`** — that would
put an orchestrator under an orchestrator and break the hex-enforced
`orchestrator → coordinator → leaf` chain (`protocol.md:196-206`;
`adr_0002` C-104).

- A `coordinator` may own a satellite WP; its gate is unchanged
  (`adr_0002` C-103 — ≥3 independent WP-grain sub-tasks, decomposable,
  centralized verify, one aggregated result), and its sub-WPs stay in the
  parent's repo (C-302).
- The join hierarchy stays **three** levels (`adr_0002` C-106): sub-WP
  join → WP merge → swarm `/hex-review`. C-309 **widens the third
  level's scope** to the union diff; it does not add a fourth, cross-repo
  join level.
- `adr_0002` C-107's capability gates are detected per run for the one
  session, as today; a federated run spans repos, not harnesses, so no
  per-repo capability reconciliation exists (`protocol.md:264-270`'s
  per-run, never-stored rule is unchanged). C-108's `coordinator` model
  row is untouched.

**21. `/hex-review` runs the pre-flight too (C-320).** C-309's union
scope is only sound if every participating repo is actually readable. A
`/hex-review` launched without `--add-dir` would otherwise resolve a
**silently narrower** union — a review that reports full coverage over a
partial diff, which is exactly the class of failure C-303 exists to stop,
and it would break the stay-in-scope contract (`hex-review/SKILL.md:298`)
by under-scoping rather than over-scoping.

- Before resolving the union, `/hex-review` runs C-303 clauses (i) and
  (ii) plus a **read** check for every `Repo` value the plan uses, and
  **halts** with the same `Error:`/`Fix:` relaunch line on failure.
- Clause (iii)'s writability requirement does **not** apply:
  `/hex-review` never writes in a satellite (`hex-review/SKILL.md:278-282`
  unchanged — its only writes remain the **lead's** plan artifact, whose
  Status block and appended convergence rows stay singular, C-310).
- `/hex-plan` still does not run it (C-314): planning reads nothing in a
  satellite.

**22. Verification scope words are repo-scoped (C-321).** `protocol.md`
says "run the project's documented verification" (`:441-446`) and
`hex-execute/tier-high.md` raises two gates to "**across the whole
workspace**" (`:49-50`, `:88-89`). In a federated run "the project" and
"the workspace" are ambiguous, and the ambiguity is silent — a
workspace-wide `cargo check` in the lead says nothing about `ocx-mcp`.

- **"The project's documented verification" = the owning repo's**, read
  by explicit `Read` of that repo's project context (C-306).
- **"Across the whole workspace" = across the whole workspace of the
  repo the gate is running in** — never a cross-repo aggregate, because
  no command spans this cluster (`task verify` / `bun test` /
  `vscode-test`) and hex never defines one (`protocol.md:441`).
- The genuinely cross-repo check remains C-311's integration WP, inline
  in the plan. There is no implicit federated verify gate.

**23. The constitution gate stays per-repo, lead-governed (C-322).** The
gate is opt-in and project-owned (`protocol.md:448-464`). A federated
plan is the **lead's** artifact, so the **lead's** constitution pointer
governs it and its `Constitution deviations` table, exactly as today. A
satellite's own constitution is **not** merged into that gate — merging
two governance documents is a governance act hex has no standing to
perform. Instead, when a satellite's project context names a
constitution, the gate announce line names it as **unapplied**, so the
human sees the gap rather than inheriting it silently. No new gate, no
new table.

**24. Federated execution is lead-originated (C-323).** C-308's
back-pointer cannot be the guarantee, because the guard is created by the
very thing it guards: the bullet is written at first satellite worktree
creation, so a **virgin** satellite — a fresh clone, a second machine, or
the first run ever launched from that repo — carries none. Ordering bug,
not a gap in coverage. The fix is structural and needs no marker:

- **A run is federated only if its own resolved `hex.md` carries at least
  one `Federation:` bullet.** Satellite paths resolve from exactly one
  place — the lead's `## Pointers` (C-301) — and C-318 forbids merging
  any other repo's memory, so a run that resolved a memory file without
  those bullets has **no way to name a satellite at all**. It cannot
  construct the federation; it is an ordinary single-repo run.
- **Therefore: a plan carrying a `Repo` column, executed or reviewed by a
  run whose resolved `hex.md` carries no `Federation:` bullets, halts.**
  That is the only path by which a satellite could reach the federated
  plan — the plan lives in the lead, so reaching it needs an explicit
  path target (`hex-execute/SKILL.md:73-102`); the active-plan pointer
  never crosses a repo boundary (C-318). The halt closes it:

```
Error: this plan is federated (`Repo` column: `.`, mirror, mcp) but this
       run resolved no `Federation:` pointers — it cannot address those
       repos and must not execute a partial plan.
Fix:   cd <lead> && claude --add-dir <satellite> …   # run from the lead
```

- **Every `Repo` value must resolve to a declared key** in that same
  `hex.md`. An unknown key halts with the same pair — no key, no path, no
  write. This also catches a renamed key (Consequences' soft
  compatibility surface) at the gate instead of mid-run.
- **Fail-closed by construction, and that is the point.** There is no
  state to provision, nothing that can be missing, and nothing a stale
  file can get wrong: the guarantee holds on a machine that has never
  seen this plan. C-308's bullet is retained as the **earlier and
  better-worded** refusal — it fires at memory resolution, before a
  target is even resolved, and it names the lead so the human gets a `cd`
  line instead of a puzzle — and as the human-readable "this repo is
  locked" marker C-313 garbage-collects. It is a convenience and a
  diagnostic, **not the guard**. Where the two disagree, C-323 is the
  invariant.
- Vacuous single-repo: a plan with no `Repo` column trips none of this.

**25. Frozen bases and landing live in the plan's Status block
(C-324).** The plan is the state of record; two things previously
asserted but never written down now live in it, in one block, because
they are read at the same moments (resume, review, upkeep). The Status
block gains a `Repos:` sub-block, present **only** for a plan carrying a
`Repo` column:

```markdown
## Status
- State:   landing        <!-- planning → plan-approved → executing → review → landing → done -->
- Tier:    high
- Updated: 2026-07-20
- Next:    land the branches below, then /hex-execute <this plan path>
- Repos:   <!-- frozen at execution start; bases are never re-resolved -->
  - `.`      /home/mherwig/dev/ocx         trunk `main` base `a1b2c3d4…`  landed: yes (2026-07-21)
  - `mirror` /home/mherwig/dev/ocx-mirror  trunk `main` base `e5f6a7b8…`  landed: no
  - `mcp`    /home/mherwig/dev/ocx-mcp     trunk `main` base `9c0d1e2f…`  landed: no
```

- **Written once**, by `/hex-execute` in the C-303/C-317 pre-gate step,
  before any branch is created: key, absolute path, resolved trunk
  (C-304), full base SHA, `landed: no`.
- **Resume rule.** A resumed `/hex-execute`, a `/hex-review` and
  convergence **read** this block and re-resolve nothing. If the block is
  absent while the table carries a `Repo` column and any WP row is not
  `pending`, the run's bases are unrecoverable and it **halts** — the
  alternative is diffing against a baseline that has moved, silently.
  With every WP still `pending`, the block is simply written fresh.
- **`landing` is a plan State, not a WP Status.** The WP vocabulary stays
  exactly `pending|active|merged|failed` and `merged` keeps its meaning
  (merged onto that repo's feature branch, not landed on trunk). The
  plan's State sequence gains one step, for federated plans only:
  `review → landing → done`. `/hex-review`'s Approve verdict sets
  `landing` instead of `done` when the plan carries a `Repo` column, with
  `Next` naming C-312's landing enumeration; single-repo plans keep
  `review → done` byte-identically.
- **Who flips `landed`, and on what evidence.** A human does, or
  `/hex-execute`'s upkeep offers to on evidence it can actually see:
  `git -C <repo> merge-base --is-ancestor hex/<plan-slug> <trunk>` — the
  feature branch is contained in that repo's **local** trunk. hex never
  fetches, so a branch landed through a remote PR shows up only after the
  human updates the local trunk; upkeep never infers landing from
  anything weaker and never marks a row it did not verify.
- **`done` requires every row landed.** Only then does the plan advance,
  and only then does C-313 remove the satellite locks. This is the fix
  for the contradiction C-312 otherwise carries: naming a
  broken-integration window and then unlocking local satellite
  orchestration in the middle of it.
- **The 20-line Status-block rule holds** (`plan.md:19-21`): the block
  costs one line per participating repo, so a federation past roughly ten
  members stops fitting — which is well beyond Option A′'s stated revisit
  trigger, and is a signal rather than a constraint to engineer around.

### Explicitly not built (YAGNI)

- **No ancestor manifest** (Option A) — needs a second resolution rule,
  lives outside every repo, cannot be committed.
- **No sync, clone, fetch, pull or push.** OpenSpec's hardest-won lesson,
  and hex never pushes today.
- **No cross-repo ADR aggregation.** ADRs stay central in the lead's
  `.agents/adrs/` — state of the art per log4brains.
- **No second distribution channel.** grim already distributes published
  artifacts; a spec registry or `references:`-style index would be the
  copy-drift `DESIGN.md:36` forbids.
- **No cross-repo atomic merge, distributed transaction, or rollback
  orchestration.** Partial landing is named, not prevented.
- **No daemon, scanner, catalog, or health command.** An MCP index is the
  sanctioned escape hatch if live cross-repo search is ever needed, and
  it is not needed yet. (OpenSpec's `doctor` is the tempting shape; the
  research's own note that "the name oversells it" is the reason to skip
  it — the pre-flight check in C-303 already runs at the only moment the
  answer matters.)
- **No per-repo plan copy.** One artifact, one Status block, a commit
  trailer as the only satellite-side code trace.
- **No cross-repo ID namespacing.** `C-`/`S-` IDs stay plan-scoped
  (`protocol.md:336-357`); one plan means one ID space means no repo
  prefix, no join-key scheme, no renumbering.
- **No cross-repo memory merge or precedence rule.** One upward search,
  one `hex.md` — the lead's (C-318). Satellite knowledge is reached
  through that repo's project context, never through its swarm memory.
- **No fourth join level and no per-repo orchestrator.** Depth stays
  orchestrator → coordinator → leaf (C-319).
- **No fan-out over homogeneous fleets.** The ~35 `ocx-contrib/mirror-*`
  repos are a scripted rollout, not a coordinated design change.

## Consequences

**Good.** FM1, FM3, FM4, FM5 are answered with constructs hex already
owns; the additive surface is one table column, one bullet grammar, one
trailer and one refusal. FM6 — today a *silent* wrong answer — becomes a
halt with a fix line. Single-repo projects are untouched: absent the
bullets and the column, every rule is inert and no run changes by a byte.
The `ocx` cluster gets a shared artifact for a change that has already
cost real manual adaptation twice.

**Bad, and priced.**

- **FM7 is unsolved.** Between the lead landing and the last satellite
  landing, the satellites do not build against trunk. hex names the
  window, orders the landings and now **holds the plan open across it**
  (C-324's `landing` State); it cannot close it. A team that needs
  atomicity needs a monorepo, and this ADR is not an argument against
  that. Calibration, so this is not read as an unusual weakness: Gerrit
  Topics — the field's most mature cross-repo review system — documents
  the identical window ("you could get a partial topic submission") and
  supplies no ordering at all. Naming the window and printing the order
  is ahead of the state of the art, not behind it.
- **FM2 is only half-answered.** A consumer outside the plan — a
  fourth repo, or `ocx-contrib`'s mirror fleet — still learns nothing
  when `ocx_lib` changes. Option B is the answer there and it requires a
  publish cadence nobody in this cluster has today.
- **FM8 is half-answered.** The integration command lives as plan prose,
  which means it is not discoverable outside the plan and does not
  survive the plan's archival. That is deliberate — inventing a home for
  it would be inventing a construct — but it is a real limit.
- **A new class of write.** hex now writes in a repo the session did not
  start in (a worktree, commits, and one memory bullet). The blast radius
  is bounded by explicit paths — never a glob, never a scan, never a
  discovered sibling — by the halting pre-flight, and by hex never
  pushing. It is still strictly larger than before.
- **A launch requirement is the one genuinely new thing a user must
  learn.** `--add-dir` (or an ancestor grant) is not discoverable; the
  halt-with-relaunch line is the only teaching mechanism, and it fires
  after the user has already started a run.
- **The `Repo` values become a soft compatibility surface.** Once plans
  exist that use keys, renaming a key breaks resume for those plans. The
  column is optional, so the surface is opt-in, but it is not free.
- **The FM6 back-pointer is machine-local until a human commits it — but
  it is no longer what FM6 rests on.** The bullet is a working-tree write
  (C-308 point 2), deliberately not committed onto an unrelated
  checked-out branch nor made hostage to C-312's untracked landing, so it
  protects the checkout where the federated run happened and only that
  one. C-323 is what closes the gap: federation is lead-originated by
  construction, so a virgin clone refuses the federated plan with nothing
  provisioned in advance. What the missing bullet costs on that clone is
  a worse error message and no visible lock marker — an ergonomic
  residual, not an open failure mode.
- **A federated plan now needs a human return visit to finish.** C-324
  stops it at `landing`, and nothing advances it to `done` until the
  landings are confirmed — which is the point (the satellite locks must
  outlive the broken-integration window) but it also means a plan whose
  PRs are landed and forgotten sits in `landing` indefinitely, with its
  locks on. The escapes are unchanged and cheap: upkeep offers to confirm
  each row from local git, and hand-deleting a lock bullet is supported
  and printed in the halt. Abandonment is the same story one state later
  than before.
- **The back-pointer locks local hex use in the satellite while it
  exists.** That is the point — but it means the lock has to be
  garbage-collected, which is C-313, which is another skill-managed
  write in a foreign repo and another thing that can be left behind if a
  plan is abandoned rather than finished. The mitigations are that
  `/hex-init` stays runnable in a satellite and offers removal, and that
  hand-deleting the bullet is explicitly supported and printed in the
  halt itself. A stale lock is therefore an annoyance with a one-line
  fix, not a trap.
- **Four shipped contracts needed explicit generalization, not just
  addition.** The disjointness key (C-316), the frozen base (C-317), the
  `hex.md` owner set (C-318) and the verification-scope words (C-321)
  all read correctly single-repo and *silently* wrong federated. Each is
  now stated; each is vacuous without a `Repo` column. That they had to
  be hunted for is the cost of layering a cross-repo dimension onto
  contracts written with one repo in mind, and it is a cost the first
  implementation wave's review must pay again.
- **The coordination-repo option (A′) is deferred, not disproven.** At
  four members the bilateral pointer set is smaller than a hub plus its
  manifest; past roughly five, it is not. The revisit trigger is stated
  in Option A′ and the migration is mechanical.

## Component contracts

Numbered **`C-3xx`** — the next free range, after `adr_0001`'s `C-00x`,
`adr_0002`'s `C-1xx` and `adr_0003`'s `C-2xx`. UX scenarios `S-3xx` per
`protocol.md` § Traceability IDs.

| ID | Contract | Home / changed file |
|---|---|---|
| **C-301** | **Federation pointer grammar** — zero or more `- Federation: \`<key>\` → \`<path>\` (\`<remote>\`); verification documented in …` bullets under the lead's existing `## Pointers`. Key `.` is the lead and is never listed. The verification clause is a **pointer, never a command literal**. Skill-managed, verify-on-consumption, re-pointable. Absent ⇒ single-repo ⇒ every federation rule is inert. **No new `hex.md` section.** | `memory.md` § The three sections + § Example file (sole definition site) |
| **C-302** | **Plan-table `Repo` column** — second column, values = a Federation key or `.`, empty cell = `.`, sub-WPs inherit the parent's. `Expected Files` are repo-relative to the named repo. **No schema-version marker; the column's presence is the signal** (`adr_0002` C-105 discipline); a plan without it is byte-identical to today. | `hex-init/assets/templates/plan.md:139-145`; `protocol.md` § Worktree mechanics |
| **C-303** | **Pre-flight repo identity, access, writability and trunk** — for each Federation key the plan uses: (i) `rev-parse --show-toplevel` must equal the declared path (`git -C` walks up — OpenSpec `doctor.ts`); (ii) `rev-parse --path-format=absolute --git-common-dir` must **differ** from the lead's (equality ⇒ a sibling worktree of the lead, not a repo — verified against `ocx-evelynn`); (iii) `status --porcelain` must succeed (hex's own uncommitted back-pointer never counts as blocking); (iv) a **non-destructive write probe** must succeed — a zero-byte file created and removed under `<path>/.agents/`, plus `update-ref refs/hex/write-probe HEAD` created and deleted — because (i)–(iii) prove readability only and every federated write comes later; (v) the repo's trunk must resolve per C-304; (vi) `.agents/worktrees/` must be git-ignored (`check-ignore -q`) — `/hex-init`'s worktree-ignore audit (`DESIGN.md:142-145`) is exempt in satellites, so a satellite may not ignore it; halt offering to add the ignore line. Any failure **halts** with an `Error:`/`Fix:` pair carrying a pasteable `--add-dir` relaunch line. **No cross-repo mutation occurs until all six clauses pass for every key** — the pre-flight is a barrier, not a per-repo gate. Never degrades, never skips a repo. **The outputs are echoed per key into the announce block** so clause (i) — the one whose omission is silent — is auditable. | `hex-execute/SKILL.md` § Dispatch step 1 (the procedure); `protocol.md` § Worktree mechanics (the invariant, cross-referenced by C-305/C-306) |
| **C-304** | **Shared-slug branch rule** — `<plan-slug>` is identical in every participating repo. Lead resolution unchanged (`protocol.md:363-367`). **Satellites always create `hex/<plan-slug>` from their own trunk, never from a checked-out non-trunk branch**; a satellite found on a non-trunk branch is announced at the gate. **Trunk is discovered, never assumed to be `main`**: `symbolic-ref --short refs/remotes/origin/HEAD`, else the trunk documented in that repo's project context read explicitly (C-318 forbids reading its swarm memory), else **halt and ask**; the result must exist as a local ref. Discovery runs in the C-303 pre-flight, alongside C-317's base freeze, and both the trunk and its source are echoed. | `protocol.md` § Worktree mechanics (amends the one-feature-branch rule) |
| **C-305** | **Satellite worktree mechanics** — `git -C <path> branch hex/<plan-slug> <base SHA from the C-324 ledger>` then `git -C <path> worktree add .agents/worktrees/<wp-slug> hex/<plan-slug>--<wp-slug>`. The worktree lives under the **satellite's** `.agents/worktrees/` (the owning repo records the checkout and already gitignores that path). Removal and branch delete after merge, as today. hex never fetches. | `protocol.md` § Worktree mechanics |
| **C-306** | **Global merge serialization** — one topological order over all WP rows across all repos, one merge in flight. **Correctness requires only per-repo serialization plus `Depends on` ordering across repos; global one-at-a-time is an operability choice** (one sequential orchestrator, one halt-capable verification at a time, resume reconstructible from the Status column) and is the first rule to relax if merge wall-clock ever dominates. Each merge is `git -C <repo> merge` onto that repo's `hex/<plan-slug>`, then the **owning repo's** documented verification read by an **explicit `Read`** (never ambient — `--add-dir` does not load a satellite's `CLAUDE.md`). Cross-repo `Depends on` edges are ordinary; the `adr_0002` C-101 ready-set is unchanged; the concurrency cap counts across repos. Merge playbook unchanged. | `protocol.md` § Worktree mechanics; `hex-execute/tier-*.md` § Merge and commit |
| **C-307** | **`Hex-Plan:` commit trailer** — every hex commit in a satellite carries `Hex-Plan: <remote-slug>:<repo-relative plan path>` in the trailer block. Ordinary git trailer syntax, no new format, recoverable via `git -C <repo> log --grep`. The only satellite-side record of the plan; there is never a plan copy. | `protocol.md` § Worktree mechanics; `hex-execute/tier-*.md` § Merge and commit |
| **C-308** | **Satellite back-pointer + orchestrator refusal** — each satellite's own `hex.md › Pointers` carries `- Federation lead: \`<path>\` — this repo participates as satellite key \`<key>\` for plan(s): \`<slug>[, …]\`.`, written lazily by `/hex-execute` at first satellite worktree creation into the satellite's **main checkout working tree, uncommitted** (the guard is a filesystem fact, never contingent on C-312's untracked landing), and disclosed at the existing meta-plan gate (never a second gate). `/hex-plan`, `/hex-execute`, `/hex-review`, `/hex-architect` resolving a memory file carrying that bullet **halt** with an `Error:`/`Fix:` pair naming the lead and the delete-the-bullet escape; **`/hex-init` is exempt** so a satellite stays auditable. Transplants OpenSpec's double-root refusal (`init.ts:132-160`). | `memory.md` § Location and resolution (**sole definition site** of the `Error:`/`Fix:` text); the four `SKILL.md` resolve-memory steps each add **one line linking to it — never a copy** (`DESIGN.md:36`) |
| **C-309** | **Union-diff review scope** — for a target tracing to a plan with a `Repo` column, the resolved scope is the union of `git -C <repo> diff <base>...hex/<plan-slug>` over the lead and every distinct `Repo` value, presented as one repo-labelled diff set. `<base>` is **read from the plan's `Repos:` ledger** (C-324), never re-resolved. `hex-review`'s never-edits and stay-in-scope rules are unchanged in text. | `hex-review/SKILL.md` § target resolution + § Constraints |
| **C-310** | **Convergence across the boundary** — mechanism unchanged (`protocol.md:487-504`); coverage evaluated against the union diff, satellite delivery located via the `Hex-Plan:` trailer, appended gap rows carry a `Repo` value. `C-`/`S-` IDs stay plan-scoped and therefore global to the change. | `protocol.md` § Convergence contract |
| **C-311** | **Mandatory integration WP** — a plan using the `Repo` column carries at least one integration WP row depending on every satellite WP it joins; its verification command is written **inline in the plan's Implementation Steps**, because the check belongs to no repo and no pointer resolves it. The inline check is a **per-repo table, not a sentence**: one row per participating repo (the lead plus every distinct `Repo` value), each naming the **exact state** that repo must be at (branch + SHA, plus any submodule pin) and the command proving it, each **reported pass/fail independently** — an aggregate "integration green", a missing row, or running the command only in the lead does not satisfy C-311. Required state is verified (`rev-parse`) before the command runs; any missing, unresolved or failed row fails the WP. Enumeration completeness is checked at plan time and at the gate. Ordinary row, no new construct. | `hex-init/assets/templates/plan.md` § Parallelization comment; `protocol.md` § Verification |
| **C-312** | **Landing is not automated (the honest non-answer)** — hex never pushes and never infers a landing it did not observe locally. The handoff **must** enumerate the per-repo feature branches, the required landing order, and the named window in which satellites do not build against lead trunk. What is no longer true is that landing is entirely untracked: per C-324 the lead's review advances a federated plan to **`landing`**, and the per-repo `landed` flags in the plan's `Repos:` ledger gate `done`. | `hex-execute/SKILL.md` § Handoff |
| **C-313** | **Back-pointer lifecycle** — the C-308 bullet carries the plan slug(s) that justify it. `/hex-execute`'s upkeep removes a slug when its plan reaches State `done` — which per C-324 requires every repo confirmed landed, so the lock spans the broken-integration window instead of expiring inside it; an empty list deletes the bullet, and deletes the `hex.md` file if the bullet was its only content. `/hex-init` in a satellite offers removal for slugs whose lead-side plan is `done` or absent. Manual deletion is supported and printed in the halt. A second `Federation lead:` bullet naming a different lead **halts** at the pre-flight. | `memory.md` § Location and resolution; `hex-execute/SKILL.md` § Upkeep; `hex-init/references/audit.md` |
| **C-314** | **Planning-side federation discovery** — `/hex-plan`'s Discover phase reads the `Federation:` bullets from `hex.md › Pointers` alongside every other pointer; its Decompose phase offers per-repo WP decomposition (satellite scope ⇒ that key in `Repo`) and adds C-311's integration row. Never scans for siblings, never proposes an undeclared repo, never writes into a satellite, and does **not** run the C-303 pre-flight (planning needs no satellite access). Absent bullets ⇒ no offer, no column, byte-identical plan. | `hex-plan/SKILL.md` § Discover; `hex-plan/tier-{low,medium,high}.md` § Decompose |
| **C-315** | **Gate federation announce line** — when a plan carries a `Repo` column, the meta-plan gate's announce block gains one block immediately after `Degraded:`, in the same `<label>: <value> (<source>)` shape: mandatory line 1 `Federation: lead \`.\` + <keys> — N repos, M WPs (K satellite)`; a line per satellite on a non-trunk branch (C-304); a line naming satellites where a back-pointer will be written (C-308's disclosure). Absent the column, the block is absent. No new gate. | `protocol.md` § The meta-plan approval gate |
| **C-316** | **`(Repo, path)` disjointness key** — the plan-time set-intersection check (`protocol.md:280-284`) and the concurrent-WP invariant (`protocol.md:383-384`) compare `(Repo, path)` pairs, not bare paths, because `Expected Files` are repo-relative and satellites routinely share path text (`Cargo.toml`, `src/**`). Merge-time re-validation is unchanged and already repo-scoped. Vacuous single-repo: every pair is `(., p)`. Amends a locked `DESIGN.md` decision — see the deviations table. | `protocol.md` § Parallel-by-default decomposition + § Worktree mechanics; `hex-init/assets/templates/plan.md` § Parallelization comment |
| **C-317** | **N frozen bases, resolved together** — the frozen-base rule (`protocol.md:365-367`) is per feature branch, so a federated plan has one per participating repo. **All are resolved in the same pre-gate step at execution start**, never lazily at first touch, so no wave-1 satellite WP branches from a moving baseline, and each is **persisted as a full SHA in the plan's `Repos:` ledger** (C-324) so resume, review, merge-time re-validation and convergence all read the same `<base>` rather than re-resolving a trunk ref that may have moved. Each WP's base is its own repo's row. | `protocol.md` § Worktree mechanics; `hex-init/assets/templates/plan.md` § Status |
| **C-318** | **One `hex.md`, the lead's** — a federated run resolves exactly one memory file (the C-308 halt guarantees it is never a satellite's). `Preferences` are the lead's exclusively: model matrix, adversary, perspectives and `max-workers`, so the effective cap is `min(8, lead's max-workers)` counted recursively **and across repos** (`protocol.md:208-220`). `Pointers` are the lead's plus C-301's own clause; satellite verification and rules come from that repo's **project context** by explicit `Read` (`memory.md:89-113`). The active-plan pointer exists only in the lead. **No cross-repo merge, precedence or nearest-wins rule is added** — `memory.md:9-13` and `:14-16` are untouched. | `memory.md` § The three sections + § Destination of knowledge; `protocol.md` § Worker coordination |
| **C-319** | **Depth chain unchanged** — federation adds no recursion level. The federated orchestrator is *the* orchestrator; it drives satellites with `git -C` and leaf workers and **never spawns a per-repo `/hex-execute`** (`protocol.md:196-206`; `adr_0002` C-104). A `coordinator` may own a satellite WP under its unchanged gate (`adr_0002` C-103), with sub-WPs in the parent's repo. The join hierarchy stays **three** levels (`adr_0002` C-106); C-309 widens the third level's scope, it does not add a fourth. `adr_0002` C-107/C-108 untouched; degraded detection stays per-run (`protocol.md:264-270`). | `protocol.md` § Worker coordination; `hex-execute/SKILL.md` § Coordinator spawn (both **cross-referenced, not changed**) |
| **C-320** | **`/hex-review` pre-flight** — before resolving C-309's union, `/hex-review` runs C-303 clauses (i) and (ii) plus a **read** check per `Repo` value the plan uses, and **halts** with the same relaunch line. Clause (iii)'s writability check does not apply: `/hex-review` writes only the **lead's** plan artifact (`hex-review/SKILL.md:278-282` unchanged). Without this the union resolves silently narrower — full-coverage claims over a partial diff, an under-scoping break of `hex-review/SKILL.md:298`. `/hex-plan` still runs no pre-flight (C-314). | `hex-review/SKILL.md` § target/baseline resolution |
| **C-321** | **Verification scope words are repo-scoped** — "the project's documented verification" (`protocol.md:441-446`) means the **owning repo's**, read explicitly; `tier-high.md`'s "across the whole workspace" gates (`:49-50`, `:88-89`) mean the workspace of the repo the gate runs in, never a cross-repo aggregate. No command spans this cluster and hex never defines one (`protocol.md:441`). The cross-repo check stays C-311's inline integration WP; there is no implicit federated verify gate. | `protocol.md` § Verification; `hex-execute/tier-{medium,high}.md` § gates |
| **C-322** | **Constitution gate stays lead-governed** — the plan is the lead's artifact, so the lead's constitution pointer governs it and its deviations table, unchanged (`protocol.md:448-464`). A satellite's own constitution is **never merged in** — merging governance documents is not hex's act. When a satellite names one, the gate announce block names it as **unapplied**, so the gap is visible rather than silently inherited. No new gate, no new table. | `protocol.md` § Constitution gate; `protocol.md` § The meta-plan approval gate (C-315's block) |
| **C-323** | **Federated execution is lead-originated (fail-closed)** — a run is federated **only if its own resolved `hex.md` carries `Federation:` bullets**; satellite paths resolve from nowhere else (C-301, C-318), so a run without them cannot name a satellite at all. A plan carrying a `Repo` column, executed or reviewed by such a run, **halts** with an `Error:`/`Fix:` pair naming the lead — which closes the virgin-satellite hole (fresh clone, second machine, first-ever run) that C-308's lazily-written back-pointer structurally cannot, since that bullet is created by the very execution it guards. Every `Repo` value must additionally resolve to a declared key, or halt. **C-308's bullet is the earlier, better-worded refusal and C-313's garbage-collectable lock marker — a convenience and a diagnostic, not the guard.** Requires no provisioning and no marker; vacuous without a `Repo` column. | `hex-execute/SKILL.md` § Dispatch (target resolution); `hex-review/SKILL.md` § target resolution; `memory.md` § Location and resolution (stated alongside C-308's text) |
| **C-324** | **`Repos:` ledger in the plan Status block + the `landing` State** — a plan carrying a `Repo` column carries one Status-block line per participating repo: key, absolute path, resolved trunk (C-304), **full base SHA** (C-317) and a `landed:` flag. Written once by `/hex-execute` in the pre-gate step, before any branch; **read, never re-resolved**, by resume, `/hex-review`, merge-time re-validation and convergence; a run that finds it absent with any WP not `pending` **halts**. The plan State sequence gains one federated-only step, `review → landing → done`: `/hex-review`'s Approve sets `landing`, and `done` requires every row `landed`, so C-313's satellite locks span the broken-integration window C-312 names instead of expiring inside it. `landed` is flipped by a human, or by upkeep on locally verifiable evidence only (`merge-base --is-ancestor hex/<slug> <trunk>`) — hex never fetches and never infers. **The WP Status vocabulary is untouched** (`pending\|active\|merged\|failed`; `merged` still means merged onto the feature branch). Absent a `Repo` column: no block, no `landing` state, byte-identical. | `hex-init/assets/templates/plan.md` § Status; `hex-execute/SKILL.md` § The plan artifact + § Upkeep; `hex-review/SKILL.md` § The review report |

**UX scenarios.**

| ID | Scenario |
|---|---|
| **S-301** | A repo with no `Federation:` bullet runs `/hex-plan`. No column offered, no pre-flight, no announce line, shipped behaviour byte-identical. |
| **S-302** | `/hex-plan high` in `ocx` with two Federation bullets: Discover reads them (C-314), Decompose offers per-repo WPs and the mandatory integration row, producing the worked-example table; the gate announces `Federation: lead \`.\` + mirror, mcp — 3 repos, 4 WPs (2 satellite)` per C-315. |
| **S-303** | `/hex-execute` on that plan in a session launched without `--add-dir`. C-303 (iii) fails on `../ocx-mirror`; the run **halts** before any worktree, printing the two-line `Error:`/`Fix:` with the pasteable relaunch. Nothing was created; re-running after relaunch starts clean. |
| **S-304** | A Federation bullet points at `../ocx-evelynn`. C-303 (ii) finds its `--git-common-dir` equals `ocx`'s and **refuses**: "`../ocx-evelynn` is a worktree of the lead, not a separate repo." |
| **S-305** | A Federation bullet points at `../ocx-contrib` (not a git repo; contains 35 nested ones). C-303 (i) finds `--show-toplevel` resolves to an enclosing repo ≠ the declared path and **refuses**, instead of silently operating on the enclosing repo. |
| **S-306** | `/hex-execute` run with cwd in `ocx-mirror` after a prior federated run wrote the back-pointer. The orchestrator halts with `Error: this repo is a federation satellite (key \`mirror\`)` and the `cd ../ocx` fix line. Before C-308, this run silently used the wrong memory. |
| **S-307** | `/hex-execute` run with cwd in `ocx-mcp`, which has **no** memory file at all. Upward search finds none, shipped defaults apply, no active-plan pointer exists, so the run stops and asks for a target (`hex-execute/SKILL.md:80-82`). Benign and visible — the degenerate case of S-306. |
| **S-308** | WP2 (`mirror`) and WP3 (`mcp`) are both ready after WP1 merges. They launch in parallel — file-disjoint for free, different repos — and merge one at a time in topological order, each followed by its **own** repo's verification, read explicitly from that repo's `CLAUDE.md`. |
| **S-309** | `ocx-mirror` is on `feat/pypi-mirror` at execution start. C-304 creates `hex/ocx-lib-v050` from `main` anyway and the gate announces the checked-out branch as unrelated in-flight work. Without C-304 the slug join key would not exist in that repo. |
| **S-310** | `/hex-review` on the plan resolves the union of three diffs. A reviewer flags that `ocx-mcp`'s `[patch.crates-io]` comment still says `oci-client "0.16"` while `ocx`'s fork moved — a finding structurally invisible to any single-repo review, and the exact drift live in the cluster today. |
| **S-311** | WP2's merge-time file-set re-validation runs `git -C ../ocx-mirror diff --name-only` and finds `external/ocx` plus `Cargo.toml` plus `src/**`, all inside the WP's declared satellite-relative set. WP3 touching a file in `ocx` would be outside its declared set and blocks the merge, as today. |
| **S-312** | Execution completes. The handoff lists three feature branches in landing order and states the window in which the satellites do not build against `ocx` trunk. No landed status is recorded anywhere; the human lands them. |
| **S-313** | Convergence finds C-004 unmet in `ocx-mcp`. A gap row is appended with `Repo: mcp` and a derived wave; existing rows and IDs are untouched. `git -C ../ocx-mcp log --grep='Hex-Plan: ocx-sh/ocx:…'` is how the delivered commits were located. |
| **S-314** | The `ocx_lib` v0.5.0 plan reaches State `done`. Upkeep removes slug `ocx-lib-v050` from `ocx-mirror`'s and `ocx-mcp`'s `Federation lead:` bullets; both lists are now empty, so both bullets — and both `hex.md` files, which held nothing else — are deleted (C-313). `/hex-plan` run locally in `ocx-mirror` the next day proceeds normally: the lock expired with the change that justified it. |
| **S-315** | `ocx-mcp`'s federated PR is abandoned; the plan never reaches `done`, so the back-pointer persists and `/hex-review` in `ocx-mcp` halts. `/hex-init` — exempt from the halt — is run there, finds the referenced plan is `done`/absent in the lead, and offers to remove the slug with consent. Hand-deleting the bullet, as the halt's own `Fix:` line says, is equally valid. |
| **S-316** | The C-308 bullet is written into `ocx-mirror`'s main checkout and left uncommitted; the human never commits it and later clones `ocx-mirror` fresh on a second machine. That clone has no bullet, so C-308 cannot fire there — but C-323 does, structurally, on the plan's own `Repo` column (S-322). What the missing bullet costs is the *quality* of the refusal: a generic "this run resolved no `Federation:` pointers" instead of "this repo is satellite `mirror` of `../ocx`", and no visible marker that the repo is locked. Ergonomics, not correctness. |
| **S-317** | WP2 (`mirror`) and WP3 (`mcp`) both declare `external/ocx`, `Cargo.toml`, `src/**`. The plan-time intersection check compares `(Repo, path)` pairs (C-316), finds them disjoint, and both share wave 2. Read as bare paths they would collide and the plan reviewer would demand they be folded into one sequential WP — losing exactly the parallelism FM5 says is free. |
| **S-318** | `/hex-review` is run on the federated plan from `ocx` in a session that can read `ocx-mirror` but not `ocx-mcp`. The C-320 pre-flight **halts** with the relaunch line. Without it the union resolves over two repos, convergence reports every `C-` covered, and a verdict of Approve is issued over a diff that never included `ocx-mcp`. |
| **S-319** | The lead's `hex.md › Preferences` sets `max-workers: 4`; `ocx-mirror` has a memory file of its own setting `8`. The effective cap is `min(8, 4) = 4`, counted across all three repos (C-318). The satellite's value is never read — the run resolves exactly one `hex.md`. |
| **S-320** | `ocx-mirror`'s project context names a constitution. The plan is gated against the **lead's** constitution only; the gate's federation block adds `constitution in mirror not applied` (C-322). The human sees the gap; hex does not merge two governance documents, and does not silently ignore one either. |
| **S-321** | WP2 (`mirror`) holds ≥3 independent sub-tasks and gets a `coordinator`. Its sub-WPs are dotted rows inheriting `Repo: mirror`; the coordinator fans out one level of leaves, verifies centrally, returns one result. Depth stays orchestrator → coordinator → leaf and the join hierarchy stays three levels (C-319). At no point is a second `/hex-execute` spawned in `ocx-mirror`. |
| **S-322** | `ocx-mirror` is cloned fresh on a second machine — no `Federation lead:` bullet, so C-308 cannot fire. A `/hex-execute` there is pointed at `../ocx/.agents/plans/plan_ocx_lib_v050.md` by explicit path. The plan carries a `Repo` column; the run's resolved `hex.md` (the satellite's, or none) carries no `Federation:` bullets, so C-323 **halts** before anything is created. The guard needed nothing to be provisioned in advance — which is exactly what the back-pointer could not offer on a virgin checkout. |
| **S-323** | Execution is interrupted after WP1 merges; `ocx`'s `main` advances by three commits before the run resumes. Resume reads `base a1b2c3d4…` from the plan's `Repos:` ledger (C-324) and branches, diffs and re-validates against it — identical to the first half of the run. Re-resolving trunk would have produced a different base for WP4 than for WP1, and neither the plan nor the diff would have said so. |
| **S-324** | The lead's review approves. The plan goes to `landing`, not `done`; `ocx` lands the same day, `ocx-mirror` and `ocx-mcp` sit in review for a week. `/hex-plan` run locally in `ocx-mirror` during that week still **halts** — the lock is still on, because the integration window C-312 names is still open. Once all three rows read `landed: yes` the plan reaches `done`, C-313 removes both bullets, and local hex use unlocks. Under the pre-C-324 rule the lock expired at review, in the middle of the window. |
| **S-325** | The session was launched with a read-only grant on `../ocx-mcp`. Clauses (i)–(iii) all pass — the repo reads fine. Clause (iv) fails on the `.agents/` file probe, and the run **halts** with the relaunch line before any repo is branched, including the two that *are* writable. Without (iv) the run would have created `ocx`'s and `ocx-mirror`'s branches and worktrees and failed on `ocx-mcp`'s. |
| **S-326** | A satellite's default branch is `master`, and a second was cloned in a way that left no `refs/remotes/origin/HEAD`. C-304's discovery reads `master` from `origin/HEAD` for the first; for the second it falls back to that repo's project context, and — finding no trunk documented — **halts and asks** with the `remote set-head` fix. Neither repo is branched from a guessed `main`. |
| **S-327** | WP4's integration check runs. `ocx-mcp`'s row asserts `external/ocx` = the same SHA as `ocx-mirror`'s; `rev-parse` shows it one commit behind because WP3's merge picked up an older pin. That row reports **fail** while the other two report pass, and the WP fails. An aggregate "integration green" — or running `cargo tree -i oci-client` only in the lead — would have reported success over the exact `0.17`/`0.16` shape of drift this ADR exists to catch. |

## Non-Functional Requirements

| Axis | Impact |
|---|---|
| Cost (tokens) | **Slightly up, opt-in and bounded.** A federated project adds N pointer bullets to a file already read every run, one column to a table already read whole, and one pre-flight per used key. The real increase is the union diff at review: an N-repo change costs roughly N times a single-repo review, which is inherent to the change, not to this design — and a per-WP review budget (`plan.md:130-133`) still scales it down. An unfederated project pays exactly zero: no new file is loaded, because the mechanism lives entirely in files hex already reads. |
| Operability | **Affected, mixed — the main cost.** Gains: the FM6 split brain becomes a halt; the pre-flight surfaces access, identity and worktree-confusion problems at one moment with one fix line; per-repo landing order is printed rather than remembered. Costs: a launch requirement that is not discoverable until it fires; a new class of write into a foreign repo; three `rev-parse` invariants a reader must hold; and no automated test that any of it is honoured. The mechanical checks are the announce block, the halts, C-311's per-repo integration table (an enumeration comparable against the `Repo` column) and C-324's `Repos:` ledger (a written value a later run can be caught re-resolving) — but all are still self-reported by the same instruction-following pass whose reliability is the risk. What C-323 changes is that the highest-severity guard no longer depends on any state having been written correctly earlier. |
| Security | **Affected — this is the largest single change in blast radius since hex existed.** An orchestrator now creates branches, worktrees and commits in repos the session did not start in. Four structural bounds: (1) targets are **explicit paths from the lead's memory file** — never a glob, never a scan, never a discovered sibling, so a repo not written down is never touched; (2) the C-303 pre-flight **halts** rather than degrading and is a barrier over all keys, so a partially-accessible **or partially-writable** cluster produces no writes at all — except the self-undoing write probe itself, whose only possible residue is an empty `.agents/` directory; (3) hex still **never pushes** (`protocol.md:408`), so every effect is local and revertible with ordinary git; (4) the satellite-side persistent footprint is exactly two things — a `Federation lead:` bullet and commit trailers. **What this is not:** a permission boundary. The harness's `--add-dir` grant is the only real control, and it is coarse (an ancestor grant covers every sibling under it, which is also the recommended ergonomic form). A project that needs a repo to be unwritable by an agent must not grant the directory. No model names appear anywhere in this design (`adr_0001` C-001/C-002 preserved). |
| Portability | **Not degraded.** `git -C`, git trailers and markdown bullets work identically on all four harnesses. `--add-dir` is Claude-Code-specific *as a flag*, but the requirement it expresses — "the session can read and write these paths" — is a property of every harness, and the pre-flight probes the property, not the flag. Only the printed fix line is client-shaped, and it is output, not contract. |
| Scalability | N repos ⇒ N feature branches and up to N×WP worktrees. The concurrency cap (`protocol.md:208-220`) is unchanged in value and now counts **across** repos, so a wide federated plan batches rather than fanning out further. Merge stays strictly serial globally, which makes wall-clock merge time linear in total WP count regardless of repo count. Per C-306 that global serialization is an **operability** choice (one sequential orchestrator, one halt-capable verification at a time), not a correctness requirement — correctness needs only per-repo serialization plus `Depends on` ordering — so it is the identified relaxation if merge time ever dominates. Homogeneous fleets (the 35 `ocx-contrib` mirrors) are explicitly out of scope. |
| Availability | Not affected — no runtime, no service, nothing to be down. |

## Constitution deviations

`hex/DESIGN.md` is the constitution. **Four** resolved decisions are
amended — two worktree/branch rules, the locked plan-visualization column
set and the locked plan-time file-set intersection check — and one new
class of write is introduced; each of these needs a new dated round
appended to `DESIGN.md` in the same change. One further deviation is
declared below — C-303's write probe precedes the single approval gate
(`protocol.md:47`) — which preserves the single-gate letter
(`DESIGN.md:13-21`: no second gate, no mid-flow prompt) and so needs only
the gate disclosure it already carries, not a `DESIGN.md` round.

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **`DESIGN.md:157-165`** — "**one feature branch per plan**". A federated plan has one branch *per participating repo*, sharing a slug. | Branches are per-repo objects; a single branch cannot span repos, and the plan is one decision. The shared slug is the only join key git can express across repo boundaries, and it is what makes C-306's global ordering and C-309's union diff addressable by one name. | Keeping literally one branch means the satellites' work lives on their default branches or on ad-hoc names — no join key, no addressable union diff, no resume. The rule's *intent* (one integration target per plan) is preserved: there is still exactly one integration target per repo per plan, and the slug makes the set of them one named thing. |
| **`DESIGN.md:159` / `protocol.md:363-367`** — "existing non-trunk branch, else `hex/<plan-slug>` from trunk". Suspended for satellites, which always branch from their own trunk. | Verified on the real cluster: `ocx-mirror` sits on `feat/pypi-mirror` while `ocx` and `ocx-mcp` sit on `main`. Applying the rule per repo yields three different branch names for one change, and the slug join key that C-306/C-307/C-309 all depend on ceases to exist. | Honouring the rule in satellites and recording the resulting per-repo branch names in the plan was considered: it turns one join key into an N-row lookup table that must be kept in sync with git — a second source of truth for something git already names, which is the drift `DESIGN.md:36` exists to prevent. The checked-out branch is not discarded silently: it is announced at the gate. |
| **`DESIGN.md:183-188`** — "**Plan visualization (locked 2026-07-19)**", which enumerates the WP table's canonical column set (id, scope, expected files, size, wave, depends-on, plus status and the review budget). C-302 adds a **`Repo`** column in second position. | The table is the canonical artifact and the lock's stated intent is that the plan "stays fully actionable from the table alone". A federated plan is *not* actionable from the locked column set: nothing in it says which repo a WP's `Expected Files` are relative to, so merge-time file-set re-validation (`protocol.md:390-396`) and worktree creation have no addressable target. Adding the column preserves the lock's intent — one table, still sufficient on its own — where honouring its letter would break it. | Encoding the repo inside `Scope` or as a path prefix on `Expected Files` was considered: it keeps the column set literally intact but makes the repo a substring to be parsed out of free prose, which is a format-in-a-format and cannot be inherited by sub-WP rows the way a column is (`protocol.md:421-422`). A separate repo→WP lookup table below the plan table was also rejected: a second place to keep in sync with the first, the drift `DESIGN.md:36` exists to prevent. The mermaid index is unaffected, and a plan without the column renders and reads exactly as today. |
| **`DESIGN.md:166-182`** — "**Parallel-by-default decomposition (locked 2026-07-19)**", whose plan-time set-intersection check compares declared **file sets**. C-316 compares `(Repo, path)` pairs instead. | `Expected Files` are repo-relative (C-302, forced by `git -C <repo> diff --name-only` at merge time), so satellites in a Rust cluster declare textually identical paths as a matter of course — WP2 and WP3 of the worked example both declare `external/ocx`, `Cargo.toml`, `src/**`. Read as bare paths those sets intersect, the two WPs may not share a wave, and FM5's stated upside (cross-repo work is disjoint for free) is destroyed by a string comparison. The lock's intent — parallel eligibility decided at plan time by set intersection, never by merge-time discovery — is preserved exactly; only the element type is qualified. | Making `Expected Files` lead-relative (`../ocx-mirror/Cargo.toml`) was considered: it keeps bare-path comparison working, but breaks merge-time re-validation, which runs inside the satellite and reports satellite-relative paths, so every check would need a prefix strip — a second encoding of the repo that the `Repo` column already carries. Declaring the paths unique by convention (renaming, disambiguating prefixes) was rejected as an unenforceable authoring rule protecting a mechanical check. A plan without a `Repo` column compares `(., p)` pairs, i.e. exactly as today. |
| **New class of write** — hex writes in a repo the session did not start in (worktree, commits, one `Federation lead:` bullet, the self-undoing C-303 pre-flight write probe, and — on a C-303 (vi) miss — an offered `.agents/worktrees/` ignore line). No `DESIGN.md` rule forbids it, but every mechanism before this ADR assumed a single repo, and stating it as a deviation is more honest than claiming conformance. | Coordinating a change across repos requires acting in those repos; the alternative is generating instructions for a human to run, which is option F with extra steps. | Read-only satellites (plan the change, let the human execute it there) was considered and rejected: it re-splits execution across three sessions, none of which can run the post-merge verification the plan orders, so FM5 and FM8 both reopen. The write is instead bounded by explicit paths, a halting pre-flight, never pushing, and a two-item persistent footprint. |
| **`protocol.md:47`** — "**one approval point, before any work starts**". C-303's write probe (clause (iv)) creates and deletes a zero-byte file and a `refs/hex/` ref in each satellite **before** the meta-plan gate, so a write precedes approval. | The rule protects the user's *decision*, not the filesystem: its purpose is that nothing the user must consent to happens before they consent. A self-undoing probe consents to nothing — it leaves each repo byte-identical — and its whole job is to make the gate honest: its `writable` outcome is disclosed *in* the gate's own echo block (point 5), so the user approves knowing the cluster can actually be written. Probing after approval moves the failure past the point where the user has already agreed to a run the session cannot deliver — the half-executed plan C-303 exists to prevent — which serves the same decision worse. This preserves the single-gate letter (`DESIGN.md:13-21`): no second gate, no mid-flow prompt; only the "before any work starts" clause is deviated. | Probing after the gate satisfies the rule's letter and defeats its intent — it promises a run that then fails partway through in a foreign repo. The residual is priced rather than denied: on a *declined* run the probe may have already created an empty `.agents/` directory in a satellite (clause (iv-a)'s `mkdir -p`), which the ADR concedes and leaves in place as inert — the same directory C-305 needs anyway. |

**Considered and *not* deviated**, explicitly: **no new file format** —
the mechanism rides `hex.md › Pointers` bullets, one plan-table column,
git branches and a git trailer, and `memory.md:26`'s "three sections"
survives intact (this is why the research's `## Federation` section was
rejected). **One Status block, one ID space** — `DESIGN.md:36`'s
link-never-copy holds: no plan copy in any satellite. **Capability
classes** (`DESIGN.md:216-217`, `adr_0001` C-001/C-002) — untouched; no
literal model name appears in this design. **Single meta-plan gate**
(`DESIGN.md:13-21`; `protocol.md:45-49`) — no new gate and no mid-flow
prompt: federation is announced and consented at the existing gate. The
one thing that precedes it, C-303's write probe, is declared as its own
deviation above (`protocol.md:47`) rather than claimed as conformance —
the gate's *approval* semantics are untouched, only the "before any work
starts" clause is.
**The self-contained Status block** (`DESIGN.md:242`) — preserved as the
sole plan-status protocol: C-324's `Repos:` ledger and `landing` state
live *inside* it, so there is still no external state file and no second
place to look. `DESIGN.md` locks the WP table's column set (`:183-188`,
already deviated for `Repo`) but locks no Status-block field list and no
plan-State vocabulary, so neither addition is a fifth deviation — the
count stays four. **The WP Status vocabulary** (`pending|active|merged|
failed`) — untouched, and deliberately not extended with a landed value:
`merged` keeps meaning merged onto the feature branch, and landing is a
plan-level fact recorded per repo (C-324).
**Concurrency cap** (`protocol.md:208-220`) — unchanged in value,
clarified to count across repos; the **lead's** `max-workers` is the only
one read (C-318). **hex never pushes**
(`protocol.md:408`) — preserved without exception, in every repo.
**hex-plan never commits or pushes** (`hex-plan/SKILL.md:272`) —
preserved; C-314 writes nothing in a satellite. **Parallel-by-
default and the `adr_0002` C-101 ready-set** — unchanged; cross-repo
edges are ordinary `Depends on` entries. **Verification is never defined
by hex** (`protocol.md:441-446`) — preserved; C-306/C-321 read each
repo's own, and C-311's integration command is authored by the plan's
author, not by hex. **Serialized topological merge**
(`protocol.md:385-389`) and **merge-time file-set re-validation**
(`protocol.md:390-397`) — preserved per repo, unchanged in mechanism.
**Frozen base** (`protocol.md:365-367`) — preserved, one per repo,
all resolved together (C-317). **Memory resolution**
(`memory.md:9-13`) and **no section sharing** (`memory.md:14-16`) —
untouched: one upward search, one file, no cross-repo merge or
precedence rule (C-318). **Depth chain and join hierarchy**
(`protocol.md:196-206`; `adr_0002` C-103/C-104/C-106) — unchanged;
federation adds no level (C-319). **Traceability IDs**
(`protocol.md:336-357`) — unchanged: one plan, one artifact, one ID
space, so no namespacing scheme is needed and none is added.
**Convergence append-only and byte-identical-when-clean**
(`protocol.md:498-505`) — preserved; the lead's plan is the sole
recipient of appended rows (C-310). **hex-review never edits code and
never commits** (`hex-review/SKILL.md:278-282`) — the **never-commits**
half is preserved across every participating repo, and C-320's pre-flight
is read-only. The **only-writes-the-plan-artifact** half is *not* certified
untouched here: sibling
[`adr_0005`](adr_0005_archive_fold_back.md) (Proposed) amends it — its
Fold-Back gives hex-review a write into the spec beyond the plan artifact
— so that half is owned and qualified by adr_0005, not asserted preserved
by this ADR. **Single meta-plan
gate**, **adversary contract** (`protocol.md:466-485`) and **handoff
contract** (`protocol.md:509-518`) — one of each per run, regardless of
repo count. **Constitution gate** (`protocol.md:448-464`) — preserved
per-project; the lead's governs, a satellite's is announced as unapplied
rather than merged or ignored (C-322). **Degraded-mode announcement**
(`protocol.md:264-270`) — per run, never stored, unchanged: a federated
run spans repos, not harnesses.

## Migration / rollout plan

The repo is unreleased (`hex/` v0.1.0, no `grim release`). **Nothing
breaks and nothing is detected**: absence of `Federation:` bullets is the
signal, absence of the `Repo` column is the signal, and a project with
neither runs byte-identically to today. There is no version marker and no
migration step — the same discipline as `adr_0002` C-105.

**Wave 1 — the guard alone (independently shippable, ships even if
everything below is rejected).**

| File | Change |
|---|---|
| `hex-core/references/memory.md` | § Location and resolution gains the `Federation lead:` back-pointer grammar (including its plan-slug list), the **canonical** `Error:`/`Fix:` halt text, the `/hex-init` exemption (C-308) and the removal lifecycle (C-313). This is the sole definition site. |
| `hex-plan/SKILL.md`, `hex-execute/SKILL.md:60-71`, `hex-review/SKILL.md`, `hex-architect/SKILL.md` | The resolve-memory step gains **one line** each: halt if the resolved `hex.md` carries a `Federation lead:` bullet, per `memory.md` § Location and resolution. A link, never a copy of the `Error:`/`Fix:` block (`DESIGN.md:36`). |
| `hex-init/references/audit.md` | Audit item: in a repo carrying a `Federation lead:` bullet, check each listed plan slug against the lead and offer removal for slugs whose plan is `done` or absent (C-313). `/hex-init` is exempt from the halt. |
| `hex-execute/SKILL.md` § Dispatch (target resolution); `hex-review/SKILL.md` § target resolution | Two sentences each (C-323): a run is federated only if its **own** resolved `hex.md` carries `Federation:` bullets; a target plan carrying a `Repo` column resolved by a run without them **halts**, as does a `Repo` value naming an undeclared key. Ships in Wave 1 because it is the structural half of the FM6 guard and costs nothing; it is inert until Wave 3 makes a `Repo` column possible. |

Wave 1 is worth shipping alone: it converts today's silent FM6 split
brain into a halt — structurally in C-323, and with a better message
wherever C-308's bullet exists — for a handful of sentences and no new
capability.

**Wave 2 — the substrate.**

| File | Change |
|---|---|
| `hex-core/references/memory.md:33-38,:47-57` | Pointers row and example file gain the `Federation:` bullet grammar (C-301). |
| `hex-core/references/memory.md:26-37` § The three sections; `:89-113` § Destination of knowledge | One sentence: a federated run resolves exactly **one** `hex.md` — the lead's — so `Preferences`, `Pointers` and `Memory` all have their existing single owner and no cross-repo merge, precedence or nearest-wins rule exists; a satellite's project knowledge is read from its **project context**, never from its swarm memory (C-318). |
| `hex-init/references/audit.md` | New audit item: when a `Federation:` bullet exists, verify each path still resolves and each verification pointer still resolves; report drift, fix with consent. Re-uses the existing pointer re-audit shape. |

**Wave 3 — the change model.**

| File | Change |
|---|---|
| `hex-core/references/protocol.md` § Worktree mechanics | The `Repo` column (C-302); **the pre-flight repo-identity, access, writability and trunk invariant (C-303) stated as a contract here** — the six clauses, what each rules out, and that no cross-repo mutation precedes all of them — so C-305 and C-306 cross-reference it instead of restating it, while the step-by-step procedure stays in `hex-execute/SKILL.md`; shared-slug branch rule, the satellite-branches-from-trunk amendment and the trunk **discovery order** (C-304); the frozen-base ledger and its read-never-re-resolve rule (C-317, C-324); satellite worktree commands (C-305); merge serialization, its correctness-vs-operability split and per-owning-repo explicit-read verification (C-306); the `Hex-Plan:` trailer (C-307); and the concurrent-WP file-disjointness invariant (`:383-384`) keyed on `(Repo, path)` pairs (C-316) — the second of C-316's two invariant sites, the plan-time set-intersection check (`:280-284`) being patched in the § Parallel-by-default row below. |
| `hex-core/references/protocol.md` § The meta-plan approval gate | The `Federation:` announce block (C-315), placed after the `Degraded:` line, plus the pre-flight echo lines (C-303). Absent a `Repo` column, no change to the block. |
| `hex-core/references/protocol.md` § Convergence contract | Union-diff coverage, trailer-based delivery lookup, `Repo` on appended gap rows (C-310). The lead's plan is the sole recipient; append-only and byte-identical-when-clean unchanged. |
| `hex-core/references/protocol.md` § Verification | One sentence: a federated plan's integration check is authored inline in the plan (C-311), and "the project's documented verification" means the **owning repo's** (C-321). |
| `hex-core/references/protocol.md` § Parallel-by-default decomposition (`:280-284`) | The plan-time set-intersection check compares `(Repo, path)` pairs (C-316). One clause; vacuous without a `Repo` column. |
| `hex-core/references/protocol.md` § Worker coordination (`:196-206`, `:208-220`) | Two clauses: the cap counts **across repos** and the **lead's** `max-workers` is the only one read (C-318); federation adds no recursion level — never a per-repo `/hex-execute` (C-319). Values, depth chain and coordinator gate unchanged. |
| `hex-core/references/protocol.md` § Constitution gate (`:448-464`) | One sentence: the **lead's** constitution governs a federated plan; a satellite's is announced as unapplied, never merged (C-322). |
| `hex-core/references/protocol.md` § Upkeep step (`:520-532`) | Upkeep additionally removes a finished plan's slug from every participating satellite's `Federation lead:` bullet, deleting the bullet (and the file, if it held nothing else) when the list empties (C-313); and, for a plan in `landing`, offers to confirm each `Repos:` row from `merge-base --is-ancestor`, advancing the plan to `done` only when all are confirmed (C-324). Explicit because the shipped step re-points **one** project's `hex.md`; this is the only upkeep write that leaves the lead. `hex.md › Preferences` stays never-edited, in every repo. |
| `hex-init/assets/templates/plan.md:117-145` | `Repo` column in the table and one line in the Parallelization comment covering C-302's default/inheritance and C-311's mandatory integration row, including its **per-repo table shape** (one row per participating repo, required state, independent pass/fail). |
| `hex-init/assets/templates/plan.md:19-27` § Status | The optional `Repos:` sub-block (key, path, trunk, frozen base SHA, `landed:`) and the federated-only `review → landing → done` step in the `State` comment (C-324). Absent a `Repo` column, the block is absent and the sequence is unchanged. |
| `hex-review/SKILL.md` § The review report (`:229-231`) | One clause: an Approve verdict on a plan carrying a `Repo` column sets `State: landing`, not `done`, with `Next` naming C-312's landing enumeration (C-324). |
| `hex-plan/SKILL.md` § Discover; `hex-plan/tier-{low,medium,high}.md` § Decompose | Discover reads `hex.md › Pointers` `Federation:` bullets; Decompose offers per-repo WP decomposition and the mandatory integration row (C-314), and applies the `(Repo, path)` disjointness key when cutting waves (C-316). Absent bullets, no offer and no column. |
| `hex-plan/tier-{medium,high}.md` § Discover (Phase 1) | One clause: explorers scoped to a satellite's area read **that repo's** rules by explicit `Read` — ambient context covers the lead only (C-306's never-assume rule, C-318). Absent `Federation:` bullets, unchanged. |
| `hex-plan/SKILL.md` § The plan artifact (`:200-223`) | One sentence: a federated plan lives in the **lead** repo and its active-plan pointer is recorded in the lead's `hex.md › Memory` only — satellites never hold a plan or a pointer (FM1/FM6). Lead = the repo whose change the others adapt to; for symmetric changes, the repo owning the shared contract (D-9). The `Never commit and never push` constraint (`:272`) is unchanged. |
| `hex-execute/SKILL.md` § Dispatch step 1, § The plan artifact, § Work packages, § Upkeep, § Handoff | The C-303 pre-flight — six clauses, write probe, trunk discovery, worktree-ignore check, barrier semantics — with its halt/relaunch and its per-key echo lines; the `Repos:` ledger written in that same pre-gate step and read on resume (C-317, C-324); satellite worktree creation from the frozen SHA and the lazy back-pointer write into the satellite's main checkout (C-308); the `landing` state and per-row landing confirmation, slug removal only on `done` (C-313, C-324); the C-312 landing enumeration plus the uncommitted back-pointer files the human should commit. |
| `hex-execute/tier-{low,medium,high}.md` § Merge and commit | `git -C <repo>`, per-owning-repo verification, the `Hex-Plan:` trailer. |
| `hex-execute/tier-{medium,high}.md` § Discover (Phase 1) | One clause: "project rules for every area the plan's work packages touch" resolves **per owning repo**, read by explicit `Read` of that repo's project context — `--add-dir` does not load a satellite's `CLAUDE.md` (C-306, C-318). Absent a `Repo` column, unchanged. |
| `hex-execute/tier-high.md` gates (`:49-50`, `:88-89`) | "Across the whole workspace" is scoped to the workspace of the repo the gate runs in — never a cross-repo aggregate, because no command spans the cluster and hex never defines one (C-321). |
| `hex-review/SKILL.md` § target + baseline resolution | The union-diff scope (C-309); `git rev-parse --verify <base>` runs per participating repo; the C-320 pre-flight (clauses (i)/(ii) + read access) halts before a silently narrower union is resolved. |
| `hex-review/SKILL.md` § The review report, § Constraints | One sentence: "the plan artifact" is the **lead's**, and it is the only one whose Status block and appended convergence rows are written — the never-edits/never-commits contract (`:278-282`, `:286-288`) is unchanged and now spans every participating repo. The stay-in-scope bullet gains "…across every participating repo". |
| `hex/DESIGN.md` § Worktrees; § Two-layer knowledge model | New dated round recording **all four** amendments — the one-feature-branch-per-plan generalization, the satellite branch-origin suspension, the plan-visualization column-set amendment adding `Repo` (`:183-188`) and the `(Repo, path)` disjointness key (`:166-182`) — plus the new class of write. The two-layer model (`:30-113`) gains one clause: Layer 2 stays one file per repo; a federated run reads the **lead's** and reaches satellites through Layer 1 (their project context), so no third layer is introduced. |
| `.agents/memory/hex.md` | Unchanged — arcana is single-repo. The dogfood instance is `ocx`'s, written when the first federated plan runs there. |

**Files the map lists as touchable and this ADR deliberately does not
change.** Recorded so the omission is a decision, not an oversight.

| File / section | Why not touched |
|---|---|
| `protocol.md` § Traceability IDs (`:336-357`) | One plan, one artifact, one ID space (C-307/C-310), so `C-`/`S-` IDs are already global to the change. No repo-prefixed namespacing scheme is added, and none is needed; the join key across the repo boundary is the `Hex-Plan:` trailer, not a new ID form. |
| `protocol.md` § The meta-plan approval gate — the **single-gate rule itself** (`:45-49`) | One gate per run regardless of repo count. C-315 adds lines *inside* the existing announce block; no repo-scoped sub-gate exists, because a sub-gate is a mid-flow question. |
| `protocol.md` § Adversary contract, § Handoff contract | One of each per run. C-312 adds content to the handoff block via `hex-execute/SKILL.md` § Handoff; the contract's shape is unchanged. |
| `hex-execute/SKILL.md` § Schedule (`:311-349`) | The ready-set, its critical-path ordering and the fan-out mechanism are repo-agnostic already: a satellite WP is eligible when its deps are `merged`, whichever repo they sit in (`adr_0002` C-101/C-102 unchanged). Only the cap's counting scope is clarified, and that lives in `protocol.md` § Worker coordination. |
| `hex-execute/SKILL.md` § Coordinator spawn (`:350-374`) | C-319: the gate, the depth chain and the three join scopes are unchanged. A coordinator may own a satellite WP; C-309 widens the *scope* of the third join level without adding a fourth. Cross-referenced from `protocol.md`, not restated here. |
| `hex-execute/SKILL.md` § Constraints (`:376-399`) | `Never push to remote.` (`:384`) needs no qualifier — it is already absolute and now binds in N repos. Commit-per-phase is per-worktree and each worktree belongs to exactly one repo. |
| `hex-execute/SKILL.md` § Dispatch step 2, target resolution (`:73-102`) | The resolution *mechanism* is unchanged — explicit path, active-plan pointer, free text. What Wave 1 adds is one refusal on top of it (C-323): a resolved plan carrying a `Repo` column halts unless this run's own `hex.md` declares the keys. Listed here because the resolution order, the pointer semantics and the free-text path are all untouched. |
| `hex-review/SKILL.md` target forms (branch / PR / working tree) | Only the *plan-artifact* form fans out to a union (C-309). A bare branch or PR target stays single-repo — generalizing every target form would invent a cross-repo diff syntax with no caller. |
| `hex-init/assets/templates/plan.md` mermaid index | A visual index, explicitly droppable (`plan.md:136-137`); the table remains the source of truth. Repo grouping in the diagram is not built. |

**Rollback.** Wave 1 is unconditional and independently valuable. Wave 2
rolls back by deleting the bullets. Wave 3 rolls back by deleting the
column and the protocol sections; any plan carrying a `Repo` column
degrades to a lead-local plan whose satellite rows must be executed by
hand — which is option F, the documented default, i.e. the failure path
is the baseline.

## Open Questions

1. **[NEEDS CLARIFICATION: should the pre-flight compare the recorded
   remote against `git -C <path> remote get-url origin`?]**
   *Recommended:* **yes, as a warning, never a halt.** A mismatch is
   informative but legitimately occurs for forks and mirrors. And remote
   equality is emphatically not freshness: `ocx-save` shares `ocx`'s
   origin while sitting four months and hundreds of commits behind, which
   is exactly the checkout a federation pointer must not silently accept
   as "the same repo". The remote is identity; C-303 (ii) is the only
   invariant strong enough to halt on.

2. **[NEEDS CLARIFICATION: does `/hex-init` offer to write satellite
   back-pointers, or does `/hex-execute` write them lazily?]**
   *Recommended:* **`/hex-execute`, lazily, at first satellite worktree
   creation.** `/hex-init` has no plan and therefore no evidence of which
   siblings actually participate; offering to write into N sibling repos
   at init time is a scan in disguise. A lazily written pointer exists
   only where a run genuinely acted, which keeps the satellite-side
   footprint proportional to what happened. C-323 lowers the stakes of
   this question: the bullet is no longer the FM6 guard, so writing it
   late costs a worse error message, not a hole.

3. **[NEEDS CLARIFICATION: how do homogeneous fleets — the ~35
   `ocx-contrib/mirror-*` repos consuming one pipeline — map onto this?]**
   *Recommended:* **they do not; keep option F.** A fan-out over 35
   structurally identical repos is a scripted rollout, not a coordinated
   design change: there is one decision and 35 mechanical applications of
   it, so a per-repo WP row buys nothing and a 35-repo union diff is not
   reviewable. Revisit only if a single change ever needs a distinct
   review verdict per fleet member.

## Deferred review findings

Raised in adversarial review, judged real but not blocking this
decision. Each carries enough context to act on without re-deriving it.
None changes a contract above; all are candidates for the first
implementation wave's own review or a follow-up round.

| # | Perspective | Finding | Action when picked up |
|---|---|---|---|
| **D-1** | spec | **C-303 (ii) is lead-pairwise, not all-pairs.** The comparison set is `{lead}`, so two satellites that are worktrees *of each other* (rather than of the lead) both pass. Real shape: `ocx-evelynn` and a second worktree cut from it. *(Re-raised by cross-model review (codex).)* | Extend (ii) to compare each resolved Federation path's `--git-common-dir` against `{lead} ∪ every path already validated in this run` — cheap, since the pre-flight already collects all of them and now echoes them (point 5), which makes the collision visible to a human even before the rule changes. Or record the narrower scope as accepted residual risk. |
| **D-2** | spec | **C-312's landing order is asserted as a strict sequence with no tie-break rule.** The worked example prints "ocx, then ocx-mirror, then ocx-mcp", but WP2 and WP3 share no `Depends-on` edge — only lead-before-dependents is actually required. *(Re-raised by cross-model review (codex): a strict printed order over independent satellites reads as a constraint the DAG does not impose.)* | State that only edges in the DAG constrain landing order, that independent satellites may land in any order or concurrently, and that the printed enumeration uses plan-table row order as a deterministic **presentation** tie-break — distinguishing the two explicitly, since C-324's per-row `landed` flags now make the distinction observable. |
| **D-3** | spec | **A satellite that never ran `/hex-init` may not gitignore `.agents/worktrees/`.** `DESIGN.md:141-144` ties that audit to `/hex-init`; nothing in C-303 or C-305 checks or provisions it before `git -C <satellite> worktree add` writes there. *(Re-raised by cross-model review (codex).)* | *Resolved (fix pass 2026-07-20):* taken as the sixth-clause route — C-303 now runs `git -C <path> check-ignore -q .agents/worktrees/` in the pre-flight, halting with an offer to add the ignore line on a miss (the `DESIGN.md:142-145` audit shape). The barrier fails before any worktree is created; the lazy-write alternative was not taken because it would leave the first worktree's checkout un-ignored. |
| **D-4** | quality | **Global merge serialization is now correctly justified but still adopted.** C-306 as amended states the operability reason and names the relaxation; no further change is needed today. | Revisit only if wall-clock merge time becomes a real cost at higher WP/repo counts: cross-repo merges share no git state and can run concurrently while same-repo merges stay serial. |
| **D-5** | consistency | **Citation drift.** Two line citations were corrected in this round (`DESIGN.md:163-165` → `:159` for branch origin; `protocol.md:432-437` → `:408` for "hex never pushes"). Others may remain, and the ADR's "verified rather than assumed" framing depends on them. | *Done in round 2:* every `file:line` reference to a hex file was re-read against the shipped text. Corrected: `protocol.md:200-204` → `:208-220` (the concurrency cap; `:200-204` is the depth-chain paragraph, cited 3×), `:412-417` → `:421-422` (sub-WP `Depends-on` inheritance; `Review` inheritance lives in `plan.md:133`, not `protocol.md`), `:409-417` → `:430-431` (the join-work sibling row), `:397-404` → `:398-405` (merge playbook), `:390-396` → `:390-397`. The `memory.md:49` "pointer, never a literal" claim was corrected — that line caches the command literal alongside its pointer; the definition C-301 follows is the Pointers row at `memory.md:35`. Re-verify after any `hex/` edit. |
| **D-6** | quality | **The NFR Cost row prices tokens only, not doc surface.** Roughly a dozen shipped files gain permanent content for a need currently evidenced by one cluster, and every future edit to those sections must reason about federation even for single-repo maintainers. | Add a doc-surface line to the NFR table: files touched and approximate lines added, per wave. |
| **D-7** | quality | **C-311's integration check never graduates to project context.** The same `cargo tree -i oci-client` check recurred at v0.4.2 and v0.5.0; `memory.md`'s destination-of-knowledge rule says knowledge useful to any agent belongs in project context once it stops being a one-off, but C-311 keeps it as disposable plan prose. *(Re-raised by cross-model review (codex) as the true residual behind FM8: C-311's amended per-repo table makes the check mechanically checkable **within** a plan, but it still dies with the plan.)* | Have upkeep (or `/hex-init`) offer to persist a recurring integration check into the relevant repo's project context after its second use, mirroring the Verification pointer mechanism. The amended C-311 table is the shape to persist — repo, required state, command — so the migration is a copy, not a redesign. |
| **D-8** | quality | **The Decision Outcome commits to all three waves at once** on the evidence of two manual-adaptation incidents, though only Wave 1 is described as independently shippable. *(Re-raised by cross-model review (codex): no Wave 3 trigger is named anywhere.)* | Either state an explicit Wave 3 adoption trigger, or reframe as "adopt Waves 1+2 now; Wave 3 approved separately when the v0.5.0 migration is scheduled." |
| **D-9** | architecture | **Lead selection is never stated as a rule.** For symmetric coupling it defaults to "whichever repo runs `/hex-plan` first", which C-313 now bounds (the back-pointer expires) but does not decide. | *Resolved in round 2:* the rule — **lead = the repo whose change the other participants must adapt to**; for genuinely symmetric changes, the repo owning the shared contract — is now recorded in the migration plan's `hex-plan/SKILL.md` § The plan artifact row. Carry it into that file when Wave 3 ships. |
| **D-10** | research | **`cargo-semver-checks` is the off-the-shelf form of the worked example's integration check.** Widely adopted in the Rust ecosystem (tokio, PyO3, Cargo) specifically to catch the public-API breaks that drive this ADR's example. Running it as a lead-repo pre-flight on `ocx_lib` would surface the break *before* satellite WPs are decomposed. | Name it in the worked example or a footnote, so C-311's "the plan's author writes the command" does not read as an instruction to reinvent it. No contract change. |
| **D-11** | architecture | **Option A′ (dedicated coordination repo) is deferred with a trigger, not disproven.** See Option A′ and the closing Consequences bullet. | Revisit past roughly five federation members or a second cluster; C-301's bullets already carry every field a manifest row needs. |

## Links

- Research:
  [`spec-federation-multi-repo.md`](../research/spec-federation-multi-repo.md)
  — 8 failure modes, ~20-mechanism fit table, verified Claude Code
  runtime constraints, options (a)–(f).
- Research:
  [`openspec-framework-analysis.md`](../research/openspec-framework-analysis.md)
  § "Multi-repo: Stores".
- Constitution: [`hex/DESIGN.md`](../../../hex/DESIGN.md).
- Related: [`adr_0001`](adr_0001_model_matrix_capability_classes.md)
  (capability classes — preserved untouched),
  [`adr_0002`](adr_0002_execution_scheduling_recursion.md) (C-101
  ready-set reused unchanged; C-105's no-version-marker discipline
  reused),
  [`adr_0003`](adr_0003_configuration_customization_surface.md)
  (`Error:`/`Fix:` pair discipline reused).

## Changelog

- 2026-07-20 — Proposed. Grounded in the `ocx` cluster; corrects three
  points of the research recommendation (identity probe, satellite branch
  origin, Pointers-not-a-new-section).
- 2026-07-20 — Adversarial review round 1 applied, Status unchanged.
  Added **C-313** (back-pointer lifecycle: slug list, removal on plan
  `done`, `/hex-init` exemption and manual delete), **C-314**
  (`/hex-plan` federation discovery and per-repo decomposition) and
  **C-315** (the gate's `Federation:` announce block), with `S-314`–
  `S-316`. Specified **where the C-308 back-pointer write lands** —
  satellite main checkout, uncommitted, so the FM6 guard never depends
  on C-312's untracked landing — and priced the machine-local residual.
  Made the four `SKILL.md` halts one-line **links** to `memory.md`'s
  canonical text rather than copies. C-303 now **echoes** its three
  probe outputs into the announce block so clause (i)'s silent-skip is
  auditable, and its home in `protocol.md` is in the migration plan.
  **C-306** re-justified: correctness needs only per-repo serialization
  plus `Depends on` edges; global one-at-a-time is an operability
  choice, named as such. Added the **fourth constitution deviation**
  (`DESIGN.md:183-188`, the locked plan-visualization column set that
  C-302's `Repo` column amends) and corrected the metadata tally and the
  `DESIGN.md` rollout row. Added **Gerrit Topics** to Industry Context
  and to FM7's honest framing, and **Option A′** (dedicated coordination
  repo) with an explicit revisit trigger. Corrected two line citations.
  New **Deferred review findings** section (D-1 – D-11).
- 2026-07-20 — **Reconciled against the recovered Discover input**, Status
  unchanged. The Discover worker that should have produced an
  architecture map of the touched hex files crashed; rounds 1 and 2 were
  designed from the `ocx` cluster survey and the architect's own reading
  only. The recovered map (27 touched file/section rows, 30 binding
  constraints, 20 findings) was checked line by line against this ADR.
  It changed four things.
  **(a) One silently broken binding constraint**: `protocol.md:280-284`
  and `:383-384` compare declared **file sets**, and the ADR's own worked
  example gives WP2 and WP3 textually identical repo-relative
  `Expected Files` — so as written the two satellite WPs could not share
  a wave and FM5's "disjoint for free" claim was false. Fixed by
  **C-316**, the `(Repo, path)` disjointness key, with a **fifth
  Constitution deviation** row (`DESIGN.md:166-182`, the locked
  plan-time set-intersection check) and the metadata tally corrected to
  four amended decisions.
  **(b) Three constraints honoured only implicitly**, now stated:
  **C-317** (one frozen base per repo, all resolved at execution start —
  `protocol.md:365-367`), **C-318** (exactly one `hex.md`, the lead's;
  which repo's `Preferences`/`max-workers`/`Pointers` govern —
  `memory.md:26-37`, `protocol.md:208-220`) and **C-319** (federation
  adds no recursion level and no fourth join scope — `protocol.md:196-206`,
  `adr_0002` C-103/C-104/C-106/C-107/C-108, none of which round 1 had
  checked).
  **(c) Two silent under-scoping gaps**: **C-320** (`/hex-review` runs
  the pre-flight, so a union diff is never silently narrower than the
  plan — an Approve over a partial diff) and **C-321** (`tier-high.md`'s
  "across the whole workspace" gates, `:49-50` and `:88-89`, and
  "the project's documented verification" resolve per owning repo).
  **C-322** records that the lead's constitution governs and a
  satellite's is announced as unapplied, never merged or ignored.
  Scenarios **S-317**–**S-321** added.
  **(d) Migration plan completed**: every row of the map's Touched-files
  table now appears with a change or an explicit reason — new Wave 3
  rows for `protocol.md` §§ Parallel-by-default, Worker coordination,
  Constitution gate and **Upkeep step**, `memory.md` §§ three
  sections/Destination of knowledge, `hex-{plan,execute}/tier-*.md`
  § Discover, `tier-high.md`'s gates, `hex-plan/SKILL.md` § The plan
  artifact (which also resolves **D-9**, lead selection),
  `hex-review/SKILL.md` § The review report, and `DESIGN.md`'s two-layer
  model — plus a new **deliberately not changed** table covering
  Traceability IDs, the single-gate rule, the adversary and handoff
  contracts, `hex-execute` §§ Schedule / Coordinator spawn / Constraints
  / target resolution, `hex-review`'s non-plan target forms and the
  mermaid index. **D-5**'s citation pass was run: five `protocol.md`
  ranges and one `memory.md` claim corrected.
- 2026-07-20 — **Cross-model adversarial pass (codex) applied**, Status
  unchanged. Triage: **6 actionable, 5 deferred, 4 stated-convention,
  1 trivia.** The six:
  **(1) Virgin satellites bypassed the FM6 guard** — C-308's back-pointer
  is written by the first federated execution, so a fresh clone, a second
  machine or a first-ever satellite run carried none and could still
  resolve the wrong memory. Ordering bug, fixed structurally by new
  **C-323**: federation is **lead-originated** — satellite paths resolve
  only from the lead's `Federation:` bullets (C-301, C-318), so a run
  without them cannot construct the federation and **halts** on any plan
  carrying a `Repo` column. Fail-closed with nothing provisioned in
  advance; C-308's bullet is demoted to the earlier, better-worded
  refusal and C-313's lock marker (`S-322`).
  **(2) `State: done` unlocked satellites mid-window** — C-312 names a
  broken-integration window while C-313 expired the locks at `done`,
  which the lead's review set. New **C-324** adds the plan State
  **`landing`** between `review` and `done` (federated plans only; the WP
  vocabulary `pending|active|merged|failed` is untouched) and per-repo
  `landed` flags that gate `done`, flipped by a human or by upkeep on
  `merge-base --is-ancestor` evidence hex can actually see (`S-324`).
  **(3) Frozen bases were asserted but unaddressable** — C-317 froze N
  bases and named no place to keep them, leaving `<base>` ambiguous on
  resume, review and convergence. C-324's **`Repos:` ledger** in the plan
  Status block persists key, path, trunk and full base SHA; every later
  consumer reads it and re-resolves nothing, and a missing ledger with
  work in flight halts (`S-323`).
  **(4) The pre-flight proved readability, not writability** — C-303
  gains clause **(iv)**, a non-destructive write probe (a file created
  and removed under `<path>/.agents/`, plus a `refs/hex/` ref created and
  deleted), and barrier semantics: no cross-repo mutation until every key
  clears every clause (`S-325`).
  **(5) Satellite trunk was undefined** — C-304 gains an explicit
  discovery order (`refs/remotes/origin/HEAD` → the repo's project
  context → **halt and ask**), echoed with its source; `main` is never
  guessed (`S-326`). Resolved in the pre-flight, as clause (v).
  **(6) The integration WP's check was free prose** — C-311 now requires
  a **per-repo table**: every participating repo named, the exact state
  each must be at, and independent pass/fail; aggregates, missing rows
  and lead-only runs do not satisfy it (`S-327`).
  Deferred findings **D-1, D-2, D-3, D-7, D-8** re-raised by this pass
  and merged into the existing entries with attribution — not duplicated.
  Stated conventions confirmed as triaged, unchanged: partial landing is
  not solved (C-312, now bounded by C-324 rather than contradicted by
  it), no cross-repo constitution merge (C-322), no per-repo orchestrator
  and no fourth recursion level (C-319, verified against `adr_0002`
  C-104/C-106), and mirror-fleet fan-out remains out of scope. The remote
  URL question stays open question 1, warning-only.
- 2026-07-20 — **Adversarial review fix pass applied** — actor
  hex-execute (fix pass), Status unchanged. Six agreed findings.
  **H6** — C-303 gains a **sixth** pre-flight clause: `.agents/worktrees/`
  must be git-ignored (`check-ignore -q`), because `/hex-init`'s
  worktree-ignore audit (`DESIGN.md:142-145`) is exempt in satellites and
  a satellite may never have run it; a miss halts offering to add the
  ignore line, and the precondition is named in deviation row 5. Clause
  counters updated five → six throughout (D-3 resolved).
  **H7** — the pre-gate write probe is declared as its **own** Constitution
  deviation (`protocol.md:47`, "before any work starts") and added to row
  5's write enumeration; the single-gate "not deviated" claim is split so
  only the "before any work starts" clause is conceded — the no-second-gate
  / no-mid-flow letter (`DESIGN.md:13-21`) still holds, so the "four
  amended DESIGN.md decisions" tally is unchanged.
  **H2** — the hex-review never-writes certification is **split**:
  never-commits preserved across every repo; the
  only-writes-the-plan-artifact half is deferred to sibling `adr_0005`'s
  Fold-Back, not certified untouched here.
  **H3** — C-310 states that a convergence delta from a satellite WP
  (`Repo` other than `.`) is reported "delivered in `<repo>`, fold by
  hand", not folded into the lead's spec, deferring to `adr_0005`'s
  lead-scoped Fold-Back rule.
  **H10** — deviation-row citation corrected against live `DESIGN.md`: the
  Parallel-by-default lock is `:166-182`, not `:186-202` (which overlapped
  the `:183-188` plan-visualization lock and bled into Staleness).
  **U10** — C-316 added to the Wave-3 § Worktree-mechanics migration row so
  its `:383-384` concurrency-invariant site is patched alongside the
  `:280-284` plan-time site already scheduled in the § Parallel-by-default
  row.
