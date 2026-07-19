# Research: spec/plan/ADR federation across multiple related git repos

## Metadata

**Date:** 2026-07-20
**Domain:** packaging / workflow-tooling (multi-repo agent orchestration)
**Triggered by:** user request — align hex with openspec.dev; YAML config,
deep customization, multi-repo
**Expires:** 2027-01-31
**Decision it informs:** whether hex adds a cross-repo federation mechanism,
and of what shape.
**Sources of truth:** OpenSpec clone @ v1.6.0 (paths below are relative to
it), hex bundle @ `/home/mherwig/dev/arcana/hex`, plus live end-to-end runs
of the published CLI under a pty (`npx @fission-ai/openspec@1.6.0` — note
the scope: bare `openspec` on npm is a defunct `0.0.0` placeholder, so any
doc saying `npx openspec` is broken today).

## Direct Answer

Nobody has solved it, and the two most credible attempts both concluded the
same thing: **declare relationships, never synchronize them.** OpenSpec's
shipped answer (Stores, beta since v1.5.0) is explicitly "declarations, not
machinery — OpenSpec never clones, syncs, or pushes anything on its own"
(`docs/stores-beta/user-guide.md:327-329`); spec-kit's answer is "treat
divergent repos as separate projects with their own constitutions"
(github/spec-kit discussion #1743); log4brains, built specifically to
publish ADRs, still requires all ADRs in one central repo and lists
cross-repo aggregation as roadmap-only. Every mechanism that *did* try to
keep N repos in lockstep (submodules, subtree, Sourcegraph indexing,
Backstage catalog) pays for it with either drift or a daemon.

For hex the recommendation is **(d) lead-repo-owns-the-change, executed via
(e) multi-root worktrees** — the plan artifact stays a single file in one
repo, gains one optional `Repo` column in the existing Parallelization
table, and satellite work packages run `git -C <satellite> worktree add` in
a session launched with `--add-dir`. No new file format, no manifest at a
common ancestor, no cross-repo sync, no registry round-trip for in-flight
work. grim/OCI stays what it already is — distribution for *stable
published* contracts, not a transport for a change in progress.

## The problem, precisely

Eight concrete failure modes, each of which hex today either mishandles or
silently does the wrong thing on. They are what any design option below has
to answer.

1. **A change proposal touching 3 repos.** Where does the single artifact
   live, and does it have one Status block or three? Three Status blocks
   means three sources of truth for one decision — the exact drift
   `hex/DESIGN.md`'s link-never-copy rule exists to prevent. One Status
   block means two repos hold code with no local record of why.
2. **A spec owned by repo A, consumed by repo B.** B's code is built
   against a revision of A's spec. When A edits the spec, nothing in B
   knows. OpenSpec's `references:` (read-only, live-indexed from whatever
   is on disk) has exactly this hole and documents it: "a stale checkout
   shows stale specs until *you* pull"
   (`docs/stores-beta/user-guide.md:329-331`).
3. **Cross-repo traceability IDs.** hex's `C-001`/`S-001` IDs are
   plan-scoped and are the join key for the convergence check
   (`hex-core/references/protocol.md:320-341`). A satellite repo's commits
   carry no plan reference at all, so the join key stops at the repo
   boundary and coverage can only be checked in the lead repo.
4. **Review that must see both diffs.** `git diff` is per-repo. A reviewer
   worker with cwd in one repo sees half the change — and the half it
   cannot see is precisely the seam (caller/callee, producer/consumer)
   where a cross-repo change actually breaks. Single-repo review of a
   multi-repo change is structurally blind in the one place that matters.
5. **Worktrees across repos.** `git worktree` has no cross-repo concept at
   all; it gives one repo several working directories against its own
   history. A cross-repo WP set needs N worktrees in N repos, created with
   `git -C`. Upside: hex's file-disjointness invariant
   (`protocol.md:367-368`) is *free* across repos — two WPs in different
   repos can never touch the same file. Downside: merge order still has to
   be one global topological serialization, because the dependency edge
   that matters (B calls A's new endpoint) crosses the boundary.
6. **Where the plan artifact lives.** hex resolves memory by upward search
   from cwd, nearest wins (`hex-core/references/memory.md:11-13`). Run
   `/hex-execute` from the satellite's cwd and it finds the *satellite's*
   `.agents/memory/hex.md` — a different active-plan pointer, a
   different verification command, a different worktree location. Split
   brain, silently, with no error.
7. **Who archives, and when.** A plan reaches `done` when the last repo
   merges. Repos have independent PR cadences, so the plan sits in
   `review` for days while some repos have landed and others have not.
   There is no cross-repo atomic merge and never will be — partial landing
   means a real broken-integration window that the plan's Status column
   cannot express today (`pending | active | merged | failed` is per-WP,
   which is the right granularity; the gap is that nothing tracks "landed
   on trunk" per repo).
8. **Verification has no home repo.** Each repo documents its own verify
   command (`protocol.md:423-429`). The integration check that a cross-repo
   change actually needs — does B still work against A's new contract —
   belongs to neither repo, so no pointer resolves it.

Rollback inherits all of the above: reverting a cross-repo plan is N
reverts with the same ordering constraint, inverted.

## What OpenSpec does today

Verified against the clone, not the marketing.

- **Root resolution is a plain nearest-ancestor walk for a literal
  `openspec/` directory** — `findRepoPlanningRootSync`
  (`src/core/planning-home.ts:59-62`) walks parents testing
  `pathExistsAsDirectory(path.join(dirPath, 'openspec'))`.
  `findQualifyingRootSync` (`src/core/root-selection.ts:284-298`) layers one
  qualifier on top: an `openspec/` dir only counts if it carries a planning
  shape or a config pointer, so the recommended `~/openspec/<id>` store
  layout doesn't turn `$HOME` into a phantom root capturing every command
  under the home tree. There is no monorepo root, no workspace file, no
  configurable directory name (open: #581, #697). **Failure is a two-line
  `Error:`/`Fix:` pair, and it is store-aware** — live-run verbatim in an
  uninitialized repo: `Error: No OpenSpec root found from the current
  directory.` / `Fix: Run openspec init to create a root here.` (exit 1,
  identical for `doctor` and `context`). With stores registered the same
  miss instead names them: `… Registered stores: <ids>. Pass --store <id> to
  use one, or run openspec init to create a local root.`
  (`root-selection.ts:436-452`). That is the "error-with-hint" terminal step
  of the precedence chain below, and the hint enumerates the valid values
  rather than pointing at `--help`.
- **Free per-package scoping falls out of that walk** — each package in a
  monorepo can hold its own `openspec/` and commands run inside it pick it
  up. That is the whole monorepo story; there is no aggregate view (`view`
  "acts on the current directory only — no `--store`").
- **A double-root guard exists** — `openspec init` refuses to scaffold a
  nested root under a repo whose planning is externalized via a `store:`
  pointer: "a subdirectory of such a repo must not silently grow a nested
  root" (`src/core/init.ts:132-160`, throws when `pointer.value !==
  undefined`). Good defensive pattern, directly relevant to failure mode 6.
- **Stores (beta, v1.5.0 2026-06-28, extended v1.6.0)** — a store is an
  ordinary standalone git repo holding a normal `openspec/` tree plus an
  identity file `.openspec-store/store.yaml`, registered per machine by
  name (`openspec store register <path>`), addressable from any repo. Five-
  step resolution precedence: `--store <id>` > nearest local `openspec/`
  root > `store:` pointer in `openspec/config.yaml` > global `defaultStore`
  > error-with-hint (or classic cwd behavior if no stores are registered)
  (`docs/stores-beta/user-guide.md:300-316`).
- **Cross-repo spec sharing is read-only reference, not merge** —
  `references: [platform-reqs]` (or `- { id: platform-reqs, remote:
  "git@github.com:acme/platform-reqs.git" }`) makes that repo's `openspec
  instructions` include an index of the referenced store's specs, each with
  a one-line summary and the exact fetch command. The referencing repo
  keeps writing its own specs and changes locally; there is no merged or
  writable shared spec set (`user-guide.md:168-224`).
- **Documented non-goals**: "No sync, ever — by design. OpenSpec never
  clones, pulls, or pushes." One checkout per store id per machine.
  Everything on the page may change between releases
  (`user-guide.md:323-332`).
- **The user-facing doc says the same thing, and says it first** —
  `docs/existing-projects.md` (§ "Monorepos and work that spans repos") is
  the shipped guidance and it is deliberately modest: "For a monorepo, the
  simplest model is one `openspec/` directory at the repo root, with domains
  that map to your packages or services. That covers most teams." Only work
  that "genuinely spans **multiple repositories**" is pointed at Stores,
  with the beta warning attached ("treat its commands and state as
  evolving"). The adjacent § "Organizing specs in a big codebase" is the
  whole taxonomy story: `openspec/specs/` grouped by domain — by feature
  area, by component, or by bounded context — created lazily, "when your
  first change in that area needs one", explicitly refinable later. Note
  what this concedes: the recommended monorepo answer is **one root, folder
  conventions, no tooling**, which is exactly the "run it at the top level"
  punt the precedent survey below attributes to spec-kit. OpenSpec's
  multi-root machinery is reserved for the genuinely-multi-repo case.
- **Diagnostics for a federated setup exist and are read-only** —
  `openspec doctor` (`src/commands/doctor.ts`) answers "are the roots this
  work relates to available on this machine?" and is documented in-source as
  never cloning, syncing, or repairing. For store-backed roots it reports
  metadata presence/validity, the store's canonical remote vs the actual
  `git origin`, and tracking drift — and it deliberately runs
  `isGitRepositoryAtRoot` first, because "`git -C` walks UP the tree:
  probing a non-repo store nested inside another repo would record the
  ENCLOSING repo's origin (and drift)". `openspec context`
  (`src/commands/context.ts`) presents the same relationship data as a
  working set (agent brief `--json`, human listing, or `--code-workspace`).
  Live-run on an ordinary single-repo project with no store and no
  references, the whole output is four lines — `Doctor` / `Root` (Location,
  `OpenSpec root: ok`) / `References` / `(none declared)`
  (`doctor.ts:151-169`), and `--json` is
  `{"root":{…,"healthy":true,"status":[]},"store":null,"references":[],"status":[]}`.
  Three lessons for hex: (1) federation needs a *health* command distinct
  from the *presentation* command, (2) every finding ships a `fix` string
  beside its `message`, and (3) **the name oversells it** — `doctor` reads
  as a project-health linter but checks only cross-root reachability, so a
  hex equivalent should either do broader checks or be named for what it
  does. A pointer-based hex federation (option c) gets the same failure
  modes and should get the same answer.
- **Worksets are a launcher, not coordination — and they are machine state,
  not project state.** `openspec workset create platform --member
  ~/openspec/platform-reqs --member ~/src/api-server` generates a
  `.code-workspace`; personal, never committed, no traceability content
  (`user-guide.md:262-298`). Verified live: the entire feature lives under
  `<XDG_DATA_HOME or ~/.local/share>/openspec/worksets/` — a `worksets.yaml`
  index (`version: 1`, then name → `{tool, members:[{name, path}]}`) plus
  one generated `.code-workspace` per set — "so deleting that one directory
  removes every trace. Nothing here is committed, shared, or derived from
  declarations, and nothing is ever written into a member folder"
  (`worksets.ts:26-33, 63-72`); `git status` in the member repos shows
  nothing. Member order is meaningful: the first is primary and is the
  session cwd (`worksets.ts:53`), surfaced in the interactive wizard as the
  step label `[2/3] Add member folders (the first one is the primary -
  sessions start there)` (`src/commands/workset-prompts.ts:41-100`). This
  is the *personal* half of a two-tier split that also covers config:
  machine-wide defaults in `~/.config/openspec/config.json`
  (profile/delivery/workflows/telemetry, `global-config.ts:43-62`) vs
  per-repo `openspec/config.yaml` (schema/context/rules). For hex the
  transferable rule is the split itself: a developer's checkout layout is
  personal and belongs in a global data dir, never in a file other people
  clone — the same reason option (a) below is rejected.
- **What remains open**: a change that spans repos, tracked as one thing —
  issue #725 "[Feature Request] Multi-repository / microservice spec
  management" (open; filed by the `alfred-openspec` bot account quoting a
  Discord user at rio.cloud, not by that user directly): "Where should the
  spec be maintained when it can't be mapped to a specific repo?" …  "If
  the specs live in an independent, 'pure' spec repository, how do we teach
  the agent which repositories are relevant". Hierarchical/nested specs:
  #662, #594 (specs are flat, `specs/<capability>/spec.md`, one level).
  Configurable directory: #581, #697. OpenSpec's own dogfooded planning docs
  still list "How should monorepos map capabilities, folders, and repo-local
  changes?" as unresolved
  (`openspec/initiatives/context-store-and-initiatives/questions.md:11`,
  last touched four days before Stores shipped).
- **Community state of the art**: hand-authored flat naming conventions
  (`{scope}-{module}[-{feature}]`, `{verb}-{scope}-{module}`) plus an
  `AGENTS.md` inside `openspec/` to make the agent obey them (discussion
  #768); and a contributor in discussion #176: "monorepo's and cross repos
  are a bit of a challenge… the intuition would be to initialize openspec
  multiple times per app. But this makes cross app changes a bit harder."

## Precedent survey

| Mechanism | Identity | Versioning / pinning | Staleness handling | Server/daemon? | Fit for LLM-read markdown |
|---|---|---|---|---|---|
| git submodule | path + gitlink | exact commit SHA, never a branch name | none automatic; forgotten `--recursive` breaks CI | no | poor — pinned copy, manual bump, high ceremony |
| git subtree | none (copy) | none after import | `git subtree pull`, tangled merges once diverged | no | poor — copy-not-reference, violates link-never-copy |
| Nx / Turborepo | workspace package name | workspace protocol | content-hash caching (intra-repo) | optional cache server | n/a — assumes one repo |
| Bazel (bzlmod) | module name + version | MODULE.bazel version resolution | lockfile | remote cache optional | n/a — build graph, not docs |
| Terraform registry | `ns/name/provider` | SemVer constraint (`~> 1.2.0`); git escape hatch `?ref=<tag\|SHA>` | re-resolve on `init -upgrade` | registry HTTP only, client resolves | good shape — closest analog to grim |
| Backstage catalog | `[namespace/]kind/name`, `spec.dependsOn` | none (live entity graph) | periodic re-scan of each Location | **yes** — Backstage backend | discovery convention borrowable, backend is not |
| OCI / ORAS | `registry/repo:tag` + `@sha256:` digest | tag, semver, or immutable digest; OCI 1.1 `subject`/referrers chains artifacts | pull-on-demand; digest is frozen | no — any conformant registry | **best fit** — grim already is this |
| Flux OCIRepository | same OCI coords | precedence digest > semver > tag; revision recorded as `<tag>@sha256:<digest>` | continuous reconcile on `spec.interval` | **yes** — source-controller | pinning semantics adopt; daemon reject |
| Renovate presets | `github>owner/repo[:preset][//path][#ref]` | `#ref` pins a tag/SHA; omitting it floats the default branch | re-fetched every run | bot to *act*, plain fetch to *resolve* | good — cheapest "extends one canonical file" shape |
| ESLint shareable config | npm package `eslint-config-*` | npm semver | npm install | no | caution — nested config vs plugin resolution rules differ, a known confusion source |
| OpenAPI `$ref` | URI | none built in; `/v2/` path segments are pure convention | bundle (frozen snapshot) vs live ref | no | direct analog of the hex choice: embed a frozen clause vs link to it |
| repo / vcstool / west / meta | manifest entry name | per-project revision pin (`.meta` pins nothing) | explicit `repo sync` / `vcs import` / `west update` | no | wrong problem — gets N repos onto disk, doesn't share one artifact |
| west `import: true` | project entry | transitive, each at its recorded revision | re-run update | no | the one composable-pinned-extends in that family |
| Sourcegraph | repo+symbol | SCIP index generation | scheduled re-index | **yes** — server + executors | read-time navigation, not distribution |
| moon `extends:` | HTTPS URL or relative path | versioned filename or git ref in the URL | live GET at load, no lockfile | no | cheapest possible indirection; no integrity check |
| Kiro multi-root | root folder name tags each steering file | none | editor session scope | no (editor) | **conceptually the closest**: always-included vs conditional-per-root inclusion |
| Claude Code `--add-dir` | filesystem path | none | session scope | no | the actual runtime hex has; see gotchas below |
| OpenSpec Stores | store id (`.openspec-store/store.yaml`) | none — whatever the checkout is at | manual `git pull`; "no sync, ever" | no | honest, minimal; no versioning is the weak point |
| OpenSpec worksets | workset name in a machine-global `worksets.yaml`; members are absolute paths, first = primary/cwd | none | none — plain paths, resolved at open time | no | not federation at all: a per-developer editor launcher, deliberately outside every repo's git |
| grim (this project) | `registry/repo:tag` or `@digest` | tag or content digest, lockfile | `grim update` | no | already shipping; digest pinning confirmed (`grim add --help`) |

Two negative baselines worth citing when someone argues for less machinery:
**EditorConfig** ships zero indirection (walk up until `root = true`, no
extends primitive) and every consuming repo's copy drifts independently;
**Dependabot** has no `extends` at all, which is a documented reason teams
migrate to Renovate once they operate many repos.

## Runtime constraints (Claude Code, verified)

These bound every option below — hex ships markdown, the client is the
runtime.

1. `CLAUDE.md` resolution is **concatenation**, filesystem root → cwd, not
   nearest-wins override. A `CLAUDE.md` at a common ancestor directory is
   *already* loaded in any session started below it — a free federation
   channel that costs nothing to use and cannot be turned off
   (code.claude.com/docs/en/memory).
2. `--add-dir` / `/add-dir` grants file access **and always loads skills**,
   but loads the added directory's `CLAUDE.md`/rules **only** when
   `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` is set; the
   `additionalDirectories` permission setting never loads them at all
   (code.claude.com/docs/en/large-codebases). A hex worker reading a
   satellite's conventions must therefore `Read` the file explicitly rather
   than assume it is in context.
3. `.claude/settings.json` is **not** inherited from parent directories the
   way `CLAUDE.md` is — it loads only from the starting directory.
4. `@path` imports in `CLAUDE.md` resolve relative to the importing file,
   recurse at most 4 hops, and load in full at launch.
5. hex's own memory search is nearest-wins upward from cwd
   (`memory.md:11-13`) — it does **not** merge ancestors. This is the
   mechanic that makes failure mode 6 real, and the one that constrains
   option (c).

## Design Patterns Worth Considering

- **Declarations, not machinery** — a repo may declare how it relates to
  another; the declaration changes what the tool can *tell* you, never
  where commands *act* (OpenSpec Stores, `user-guide.md`). The single most
  transferable idea in this whole survey.
- **Nearest marker directory wins, qualified** — walk up for a marker, but
  require the marker to carry real content before accepting it, or a bare
  directory at `$HOME` captures everything (`root-selection.ts:284-298`).
- **Double-root guard** — refuse to scaffold a second root under a repo
  that already declared an external one (`init.ts:132-160`).
- **Tag + digest as one revision string** — record `<tag>@sha256:<digest>`
  so the human-readable label and the immutable identity travel together
  (Flux OCIRepository `.status.artifact.revision`).
- **Bundle vs live `$ref`** — freeze a copy at build time or dereference at
  read time. For an LLM reader the live ref is strictly better: the agent
  can dereference a path or URL itself, and the frozen copy is exactly the
  drift `hex/DESIGN.md` forbids.
- **Always-included vs conditional-per-root inclusion** (Kiro multi-root) —
  the only shipped model that scopes shared context *by which root the
  agent is currently touching*.

## Key Findings

1. OpenSpec's cross-repo answer is read-only reference plus a shared
   planning repo, with sync explicitly a non-goal: "No sync, ever — by
   design." (`docs/stores-beta/user-guide.md:327-329`)
2. A change that spans repos, tracked as one unit, is **open and
   unimplemented** in OpenSpec — issue #725, filed by the
   `alfred-openspec` bot quoting a Discord user, not closed by Stores; the
   related cluster is #662, #594, #435, #581, #697.
3. spec-kit's maintainer position is the null answer: run it at the top
   level, and repos with sufficiently different requirements are separate
   projects with their own constitutions (github/spec-kit discussion
   #1743). Open issues #581, #1095, #1026 track monorepo/subfolder support.
4. log4brains — a tool whose entire purpose is publishing ADRs — still
   requires one central repo for all ADRs; per-package fetching is
   README-roadmap, unshipped. Central ADR home is state of the art, which
   is what `.agents/adrs/` already is.
5. Claude Code's own guidance for "conventions across many repos" is not
   more nested context files: move them into **skills, plugins (versioned,
   centrally owned bundles), or an MCP index**
   (code.claude.com/docs/en/large-codebases). That is structurally what
   grim already does for arcana — the architecture is already the
   recommended one.
6. `--add-dir` is a real multi-root primitive but a leaky one: skills load,
   `CLAUDE.md`/rules do not without an env var, and `settings.json` never
   inherits. Any hex multi-repo mode must read satellite conventions
   explicitly instead of relying on ambient context.
7. `git worktree` is not a multi-repo mechanism (one repo, many working
   dirs). Third-party wrappers fan `git worktree add` out per sibling repo
   and add no pinning between repos — which is exactly the shape option (e)
   needs, and confirms there is nothing to adopt beyond `git -C`.
8. The manifest-plus-CLI family (Google `repo`, ROS `vcstool`, Zephyr
   `west`, `meta`) solves "get N repos onto disk at pinned revisions",
   which is not this problem. `west`'s `import: true` (transitive,
   per-revision) is the only composable idea in the family.
9. Registry distribution is the converged industry answer for *stable*
   shared context — Terraform modules, Helm OCI (tag must equal the chart
   SemVer, no floating `latest`), Tessl's Spec Registry (>10k published
   specs), Claude Code plugins, grim. None of them carry an in-flight
   change; they carry released artifacts.
10. grim already supports both mutable tags and immutable `@digest`
    pinning with a lockfile (`grim add --help`: "`registry/repo:tag` or
    `@digest`… a path declares the artifact verbatim and pins it by content
    hash"), so the pinning question raised in prior research is answered —
    no new mechanism needed for option (b).
11. Monorepo-vs-polyrepo commentary in 2025-2026 argues context bandwidth,
    not human coordination, is now the binding constraint — but the
    actionable part is scoping discipline, which hex already has (per-WP
    file sets, path-scoped rules), not repo topology.
12. Cross-repo file-disjointness is free: two WPs in different repos cannot
    collide on a file, so hex's core parallelism invariant
    (`protocol.md:367-368`) survives federation untouched. What does *not*
    survive is post-merge verification — the interaction that breaks is
    across the seam, so a cross-repo plan needs an explicit integration WP.

## Design options for hex

### (a) Federation manifest at a common ancestor

**Sketch.** A file at the nearest common ancestor of the member repos,
e.g. `~/dev/.agents/federation.md`, listing members:

```markdown
## Members
| Key | Path | Remote | Role |
|---|---|---|---|
| arcana | ./arcana | git@github.com:acme/arcana.git | lead |
| api    | ./api-server | git@github.com:acme/api-server.git | satellite |
```

**Worked example.** `/hex-plan` run in `~/dev/arcana` walks up past the repo
root, finds `~/dev/.agents/federation.md`, and offers cross-repo WPs.

**Trade-offs.** The upward walk hits `~/dev/arcana/.agents/...`
first and stops — nearest-wins (`memory.md:11-13`) means the ancestor file
is *never seen* unless hex adds a second, different search rule ("keep
walking past the first hit"), which is precisely the phantom-root problem
OpenSpec had to add a qualifier for (`root-selection.ts:284-298`). The
ancestor directory is usually outside every repo, so the manifest is
uncommittable and unshared — each developer's checkout layout differs, which
is exactly why OpenSpec put worksets in a machine-global data dir and never
writes into a member folder (`worksets.ts:26-33`). New file
format, new resolution rule, unversioned content, and it duplicates
information git remotes already hold. **Reject.**

### (b) OCI-distributed shared spec packages via grim

**Sketch.** Repo A publishes its stable contract as a grim artifact;
consumers declare it and pin it.

```bash
# in repo A
grim release   # publishes ghcr.io/acme/spec-payments:1.4.0
# in repo B
grim add ghcr.io/acme/spec-payments@sha256:… -k rule
```

The spec lands in B as an installed artifact, digest-pinned in B's lockfile;
`grim update` is the deliberate bump. Following Helm's rule, the tag must
equal the declared spec version — no floating `latest` as an artifact's only
identity.

**Worked example.** The payments contract that three services build against
becomes `spec-payments`. Each service's lockfile records which revision it
was built against; the drift in failure mode 2 becomes a visible lockfile
diff instead of an invisible staleness.

**Trade-offs.** Correct and already-built for **stable, published,
slow-moving** contracts — it is the industry-converged shape (finding 9)
and needs zero new hex code. Useless for an in-flight change: a proposal
touching 3 repos would need a publish round-trip per iteration, and the
proposal isn't a released artifact in the first place. Also imposes an OCI
dependency on every consumer repo. **Adopt, but only for the published-spec
case — it does not address failure modes 1, 3, 4, 5, 7, 8.**

### (c) Pointer-only federation in `hex.md`

**Sketch.** No new file: add rows to the existing `## Pointers` section.

```markdown
- Federation: sibling repo `api-server` at `../api-server`
  (git@github.com:acme/api-server.git); its verification: `make check`.
```

**Worked example.** A researcher worker in arcana needs the API contract;
the pointer tells it where, and it `Read`s the file directly — which works
regardless of the `--add-dir` `CLAUDE.md` gotcha (constraint 2), since
`Read` needs only path access.

**Trade-offs.** Zero new machinery, zero new format, fits the existing
verify-on-consumption staleness rule (`memory.md:117-127`) exactly. But it
scales as N×(N−1) hand-maintained pointers, has no notion of a shared
change, and each repo's pointer set drifts independently. It answers "where
is the other repo" and nothing else. Note the reach question directly: the
upward search does **not** stretch to a common ancestor in any useful way,
because it stops at the first hit inside the current repo. **Adopt as the
substrate — it is how any option records what it found — but it is not by
itself a federation model.**

### (d) Lead repo owns the change; satellites get generated work packages

**Sketch.** One plan artifact, in one repo (the lead), unchanged in every
respect except that the Parallelization table gains one optional column:

```markdown
| WP | Repo | Scope (IDs) | Files | Depends-on | Status |
|----|------|-------------|-------|------------|--------|
| WP1 | .    | C-001, C-002 | src/pay/*.rs | — | merged |
| WP2 | api  | C-003        | src/routes/pay.ts | WP1 | active |
| WP3 | web  | C-004        | app/checkout.tsx | WP2 | pending |
| WP4 | .    | C-005 (integration) | tests/e2e/* | WP2, WP3 | pending |
```

`Repo` values are keys resolved from a new `## Federation` block in the
lead repo's **existing** `hex.md` (no new file):

```markdown
## Federation
| Key | Path | Verification |
|-----|------|--------------|
| .   | .    | `task check` |
| api | ../api-server | `npm test` |
| web | ../web-app    | `pnpm test` |
```

**Runtime resolution.** The orchestrator reads `hex.md` (nearest — and by
construction that is the lead repo's, because the plan pointer lives there),
resolves each `Path` relative to the lead repo root, and verifies it with
`git -C <path> rev-parse --show-toplevel`. Absent `Repo` column ⇒ every WP
is local ⇒ every existing plan behaves exactly as today.

**Cross-repo mechanics, concretely:**
- **Feature branch:** `hex/<plan-slug>` in *each* participating repo, same
  slug. The shared slug is the git-level join key.
- **Worktrees:** `git -C <repo> worktree add .agents/worktrees/<wp-slug>` —
  the worktree belongs to the repo whose history it checks out. Each repo
  gitignores its own `.agents/worktrees/` as already specified
  (`protocol.md:419-421`).
- **Merge:** still one global topological serialization across all repos —
  each merge runs the **owning repo's** documented verification, read from
  that repo's context explicitly (constraint 2), cached in the Federation
  table's Verification column.
- **Traceability:** `C-`/`S-` IDs stay plan-scoped and therefore global to
  the change; satellite commits carry a trailer
  `Hex-Plan: acme/arcana:.agents/plans/plan_x.md` so the join key
  survives the repo boundary (failure mode 3) with no new file in the
  satellite.
- **Review:** the reviewer panel receives
  `git -C <repo> diff <base>..<wp-branch>` for every participating repo as
  one union diff, so the seam is inside the review scope (failure mode 4).
- **Integration:** the cross-repo check is an **ordinary WP row** depending
  on the WPs it joins (WP4 above) — hex already has this construct for
  coordinator joins (`protocol.md:409-417`); no new concept.
- **Archive:** the lead repo. Landing on trunk stays the human's step per
  repo, as today.

**Trade-offs.** Reuses every existing hex contract — Status block, WP
statuses, traceability IDs, worktree mechanics, convergence check — and adds
exactly one optional column and one optional memory section. Honest about
what it cannot do: there is no atomic cross-repo merge, so a partially
landed plan is a real state (failure mode 7); the plan's Status column
tracks WP merges onto each feature branch, not trunk landings, and that
limit must be stated rather than papered over. Requires the session to have
access to the satellite paths (see (e)). **Adopt.**

### (e) hex-execute multi-root worktrees via additional working directories

**Sketch.** The runtime for (d). The session must be launched with the
satellite paths available:

```bash
claude --add-dir ../api-server --add-dir ../web-app
```

**Worked example.** This very research session runs with
`Additional working directories: /home/mherwig/dev` — one ancestor grant
covers every sibling repo under it, which is the cheapest ergonomic form.

**Pre-flight, concretely.** Before creating any satellite worktree,
`/hex-execute` checks each Federation path is writable from the session
(a trivial write probe or a `git -C <path> status`). On failure it **halts
with a pasteable relaunch command** rather than degrading — a skill cannot
grant itself directories mid-session, and silently skipping a repo would
produce a half-executed plan. Workers must `Read` satellite conventions
explicitly (constraint 2) and must not assume the satellite's `CLAUDE.md`
is in context.

**Trade-offs.** No new mechanism at all — `git -C` plus a flag that already
exists. Costs: a documented launch requirement (the one genuinely new thing
a user must learn), and the `--add-dir` context gotchas, which are
mitigated by explicit reads rather than by asking users to set
`CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`. **Adopt, as (d)'s
runtime.**

### (f) Baseline: independent plans per repo, linked by ID (do nothing)

**Sketch.** Each repo runs its own `/hex-plan`; the lead plan's Overview
links the satellite plans by path/URL; humans sequence the merges.

**Trade-offs.** This is the spec-kit stance (finding 3) and today's hex
behavior. Zero work, zero risk, and for genuinely loosely coupled repos it
is correct. It fails exactly where coupling is tight: three Status blocks
for one decision, no shared coverage check, review blind to the seam. Keep
it as the documented default; (d) is the opt-in.

## Recommendation

**Adopt (d) + (e); keep (c) as the substrate; keep (b) for published
contracts only; reject (a); document (f) as the default.**

Concretely, the migration-free adoption path — three additive changes, none
of which alters a single existing artifact:

1. **`hex-core/references/memory.md`** — add an optional `## Federation`
   section to the documented `hex.md` shape (Key | Path | Verification),
   skill-managed like Pointers, verify-on-consumption. Absent ⇒ single-repo,
   which is every repo today.
2. **`hex-core/references/protocol.md`** — in Worktree work-package
   mechanics, state that the Parallelization table's `Repo` column is
   optional and defaults to `.`; that satellite worktrees are
   `git -C <repo> worktree add .agents/worktrees/<wp-slug>`; that the
   feature branch slug is shared across repos; that merge serialization and
   post-merge verification are per-owning-repo but globally ordered; and
   that satellite commits carry the `Hex-Plan:` trailer. Every existing plan
   without the column resolves identically — the rule is vacuous, exactly
   like the sub-WP rollup rule for childless parents (`protocol.md:417`).
3. **`hex-execute`** — one pre-flight step: resolve Federation paths, probe
   access, halt with a pasteable `--add-dir` relaunch line on a miss. One
   review-scope line in `hex-review`: the diff under review is the union
   across participating repos.

Rationale: this is the only option that answers all eight failure modes with
constructs hex already has (one Status block, one ID space, one WP table,
one convergence check), that requires no daemon, no scanner, no new binary,
and no new file format, and that is invisible to every existing single-repo
user. It also matches the one design principle both credible precedents
converged on independently — declare the relationship, never synchronize it.

**Explicitly do NOT build (YAGNI):**

- **No ancestor workspace manifest** (option (a)) — needs a second
  resolution rule, lives outside every repo, cannot be committed.
- **No cross-repo sync, clone, pull, or push.** OpenSpec's hardest-won
  lesson, and hex never pushes today anyway.
- **No cross-repo ADR aggregation.** ADRs stay central in
  `.agents/adrs/` — still state of the art per log4brains.
- **No spec registry, no `references:`-style read-only index, no
  `store:`-equivalent pointer repo.** grim already distributes published
  artifacts; a second distribution channel for the same content is the
  drift `DESIGN.md` forbids.
- **No cross-repo atomic merge, no distributed transaction, no rollback
  orchestration.** Partial landing is a real state; name it in the plan,
  don't try to prevent it in markdown.
- **No daemon, scanner, or catalog** (Backstage/Sourcegraph shape) — an
  MCP index is the sanctioned escape hatch if live cross-repo search is ever
  actually needed, and it isn't yet.
- **No per-repo copy of the plan.** One artifact, one Status block, a commit
  trailer as the only satellite-side trace.

Weakest evidence in this artifact: OpenSpec Stores is explicitly beta
("names, flags, file formats, JSON keys" may change), and the live CLI runs
exercised only the *no-store* paths — `doctor` reported `"store": null`,
`References (none declared)`, and `workset create` was driven with a single
local member. So the store-registered branches (five-step resolution
precedence, canonical-remote vs `git origin` drift reporting, cross-store
`references:` indexing) remain read-from-source only, and the beta caveat
still applies to them; the *unregistered* branches — root walk, root-miss
error text, worksets storage and shape, `doctor`'s output contract — are now
observed, not inferred. The Kiro multi-root details still come from a docs
summary rather than a direct read.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| `src/core/planning-home.ts:59-62` (OpenSpec v1.6.0) | Code | 2026-07 | nearest-ancestor root walk |
| `src/core/root-selection.ts:284-298` | Code | 2026-07 | qualified walk; phantom-root guard |
| `src/core/init.ts:132-160` | Code | 2026-07 | double-root refusal under a `store:` pointer |
| `src/core/root-selection.ts:436-452` | Code | 2026-07 | root-miss errors: `Error:`/`Fix:` pair, store-aware variant listing registered ids |
| `src/core/worksets.ts:26-33, 53, 63-72` | Code | 2026-07 | worksets are machine-global state: `<dataDir>/worksets/worksets.yaml` + generated `.code-workspace`; first member is primary/cwd; never written into a member folder |
| `src/commands/workset-prompts.ts:41-100` | Code | 2026-07 | `[1/3]`–`[3/3]` compose wizard; primary-member wording |
| `src/core/global-config.ts:38-70` | Code | 2026-07 | two-tier config: `$XDG_CONFIG_HOME`/`~/.config/openspec` global vs per-repo `openspec/config.yaml`; data dir `$XDG_DATA_HOME`/`~/.local/share/openspec` |
| Live pty runs of `npx @fission-ai/openspec@1.6.0` (`init`, `doctor`, `doctor --json`, `context`, `workset create`) | CLI transcript | 2026-07-20 | observed no-store `doctor` output and JSON shape, root-miss error text, workset file location and contents; npm scope correction (bare `openspec` is a defunct placeholder) |
| `docs/stores-beta/user-guide.md:95-332` | Docs | 2026-07 | store identity, references, resolution order, known limitations, worksets |
| `docs/existing-projects.md` (§§ "Organizing specs in a big codebase", "Monorepos and work that spans repos") | Docs | 2026-07 | shipped guidance: one root at repo top level + domain folders for monorepos; Stores only for genuinely-multi-repo, with beta warning |
| `src/commands/doctor.ts`, `src/commands/context.ts` (OpenSpec v1.6.0) | Code | 2026-07 | read-only cross-root health vs presentation split; `{message, fix}` findings; store remote/drift facts; `git -C` walks-up hazard |
| `openspec/initiatives/context-store-and-initiatives/questions.md:11` | Repo doc | 2026-06-24 | monorepo mapping still unresolved |
| https://github.com/Fission-AI/OpenSpec/issues/725 | Issue (open) | 2026 | multi-repo/microservice spec management; bot-filed, quotes a Discord user |
| https://github.com/Fission-AI/OpenSpec/issues/662, /594, /581, /697 | Issues (open) | 2026 | hierarchical specs; configurable directory |
| https://github.com/Fission-AI/OpenSpec/discussions/176, /768 | Discussion | 2026 | monorepo scaling doubts; flat naming workaround |
| https://github.com/github/spec-kit/discussions/1743 | Discussion | 2026 | maintainer stance: separate projects, separate constitutions |
| https://github.com/thomvaill/log4brains | Repo README | 2026 | cross-repo ADR aggregation unshipped; central repo required |
| https://code.claude.com/docs/en/memory | Docs | 2026 | CLAUDE.md concatenation, @path imports, 4-hop cap |
| https://code.claude.com/docs/en/large-codebases | Docs | 2026 | `--add-dir` loading matrix; settings.json non-inheritance; centralize via plugins/skills/MCP |
| https://kiro.dev/docs/editor/multi-root-workspaces/ | Docs | 2026 | always-included vs conditional per-root steering |
| https://oras.land/docs/ , https://helm.sh/docs/topics/registries/ | Docs | 2026 | OCI client-only distribution; tag-equals-version rule |
| https://fluxcd.io/flux/components/source/ocirepositories/ | Docs | 2026 | digest > semver > tag precedence; `<tag>@sha256:<digest>` revision |
| https://developer.hashicorp.com/terraform/language/modules/sources | Docs | 2026 | registry-version vs git-ref source split |
| https://docs.renovatebot.com/config-presets/ | Docs | 2026 | `extends` with optional `#ref` pinning |
| https://moonrepo.dev/docs/guides/sharing-config | Docs | 2026 | `extends:` a raw remote file, pin via URL ref |
| https://docs.zephyrproject.org/latest/develop/west/manifest.html | Docs | 2026 | transitive pinned manifest `import: true` |
| https://backstage.io/docs/integrations/github/discovery/ | Docs | 2026 | conventional per-repo file + scanning backend |
| https://tessl.io/blog/tessl-launches-spec-driven-framework-and-registry/ | Blog | 2026 | spec registry as converged distribution shape |
| `grim add --help` (grim 0.10.0) | CLI | 2026-07-20 | tag and `@digest` pinning confirmed |
| `hex/hex-core/references/{protocol,memory}.md`, `hex/DESIGN.md` | Repo | 2026-07 | worktree mechanics, traceability IDs, memory resolution, link-never-copy |
