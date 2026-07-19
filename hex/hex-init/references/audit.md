# hex-init Audit Checklist

The checklist `/hex-init` runs in Step 1, and the copy-ready blocks it
proposes in Steps 2 and 6. Every item names what to look for, where to
look, and what "documented" (or "resolved") actually looks like — a
project passes an item only when the concrete bar below is met, not on a
vague impression that "it's probably in there somewhere."

## Audit items

### Verification documented?

- **Look for:** a section describing how to build, test, and lint the
  project.
- **Where:** the project-context file(s) directly, or a doc they point to
  (README, CONTRIBUTING.md, a docs/ page).
- **Documented looks like:** a runnable command (or a short named set of
  them) stated explicitly — "run `make check`" — not just "there's a test
  suite" or a bare mention that tests exist. A command buried three links
  deep with no pointer from project context does not count as documented.
- **De facto discovery:** before proposing a best-practice block, scan
  where verification actually lives undocumented — CI workflow files
  (`.github/workflows/*`, `.gitlab-ci.yml`), `Makefile` / `Taskfile.yml` /
  `justfile` targets, package-manifest scripts (`package.json` scripts,
  `pyproject`/`tox`, Cargo aliases). A found command is proposed for
  **adoption via pointer** — document what exists, don't invent a new one.

### Spec / plan / ADR conventions documented?

- **Look for:** where specs, plans, and ADRs live, and what format or
  template they follow.
- **Where:** same as above.
- **Documented looks like:** a named location plus a named format — even
  "plain markdown, no fixed template" counts — not silence, and not "look
  at the last one we wrote."
- **De facto discovery:** glob for practiced-but-undocumented homes —
  `docs/adr*`, `docs/decisions*`, `docs/plans*`, `specs/`, an existing
  `.agents/` artifact tree. A found scheme is proposed for
  **adoption via pointer**; the shipped hex templates are the last
  resort, never the first proposal.

#### Spec home documented (conditional)

A **conditional** sub-check, not a standalone item — asked only when a
plan carries an unresolved `## Spec Deltas` block (`Target: unresolved`),
**or** the conventions entry found above names plans and ADRs but no
specs. A project that has never planned anything is asked nothing.

- **Proposal order:** an existing practiced location first — the de facto
  glob above, `docs/specs/`, `specs/` — else `.agents/specs/` as
  the **last resort**, with consent.
- **ID-marker question:** does the resolved home's contracts use the
  default heading shape, or a project-specific marker? A non-default
  answer is recorded as `Spec ID marker:` prose in `hex.md › Preferences`
  (user-owned, written only by `/hex-init`, never edited by a run).
- **Seed offer:** when the resolved home is empty, offer to copy
  [`../assets/templates/spec.md`](../assets/templates/spec.md) to
  `<home>/spec_<slug>.md`, **copy-only-if-absent**, with consent.
- The mechanics this question feeds — resolution order, the ID-marker
  convention, containment, the no-spec-home defer — are defined once in
  [`archive.md`](../../hex-core/references/archive.md#destination-resolution);
  this item only asks and records the answer, never restates them.

### Rules carry architectural context?

- **Look for:** rules or conventions that state module boundaries,
  invariants, a golden path, or which paths are security-sensitive — not
  just formatting or lint rules.
- **Where:** project-context file(s), or a rules/ or docs/ directory they
  point to.
- **Documented looks like:** a rule that would change how a reviewer or
  architect reasons about a diff (e.g. "code under `src/auth/**` is
  security-sensitive," "never call X directly, use Y"). Style-only rules
  (naming, formatting) don't count toward this item, however plentiful.
- **De facto discovery:** check `CONTRIBUTING*`, `docs/`, and any
  design/architecture docs for rules that carry weight but aren't linked
  from project context — propose a pointer to them, not a rewrite.

### Product context documented?

- **Look for:** what the product *is*, who uses it and where it runs,
  related repositories, spec/doc homes beyond the code, useful
  web-research keywords, and comparable tools.
- **Where:** the project-context file(s) directly (a short product
  section), or a product doc — README, `docs/`, or a provisioned
  `.agents/product.md` — reached from a one-line index entry in the
  context file.
- **Documented looks like:** a reader who has never seen the repo could
  say in two sentences what the product does and for whom, and name at
  least one comparable tool. Missing pieces are gathered from the user in
  Step 2's wizard questions — this is the one audit item whose answers
  usually cannot be discovered from the repo alone.

### Constitution / governing principles pointer?

- **Look for:** a governing-principles or constitution doc — a named
  file of binding decisions that plans are checked against.
- **Where:** the project-context file(s), or its cached location in the
  Pointers section of `.agents/memory/hex.md`.
- **Documented looks like:** a named file of binding principles
  (boundaries, non-negotiables) — not a style or lint guide. **Optional**
  — absent is fine and the gate stays off silently; see
  [`protocol.md#constitution-gate`](../../hex-core/references/protocol.md#constitution-gate).

### Worktree path gitignored?

- **Look for:** whether the path `/hex-execute` uses for parallel work
  packages (`.agents/worktrees/` by default, or a project-declared
  alternative) is excluded from version control.
- **Where:** the ignore file (`.gitignore` or equivalent), and
  `hex.md › Pointers` for a declared alternative path.
- **Resolved looks like:** the exact path (with trailing slash) present in
  the ignore file. Flag it if `.agents/` is ignored wholesale — that drops
  the team-shared `.agents/memory/hex.md` from version control and
  must be narrowed to `.agents/worktrees/` specifically.

### Existing `hex.md › Pointers` and index lines still resolve?

- **Look for:** every pointer in the `hex.md › Pointers` section
  (verification location, conventions location, doc/product homes, key
  rules, worktree deviation) and every one-line index entry hex seeded
  in the context file still points at something that exists and still
  says what it claims.
- **Where:** `.agents/memory/hex.md` and the project-context
  file(s), cross-checked against the current tree.
- **Resolved looks like:** the file or section a pointer or index line
  names still exists and still covers what it describes. A pointer to a
  moved or rewritten section is drift — report it, don't silently trust
  it.

### Federation pointers still resolve? (lead repos)

- **Look for:** in a repo whose `hex.md › Pointers` carries one or more
  `Federation:` bullets, whether each declared satellite `<path>` still
  exists and each bullet's verification clause still points at where that
  satellite documents verification.
- **Where:** the lead's `.agents/memory/hex.md` `Federation:`
  bullets, cross-checked against the current tree and each satellite's
  project context. The `<remote>` is recorded for identity only and is
  never fetched — nothing here reaches the network.
- **Resolved looks like:** the `<path>` resolves to the satellite and the
  verification clause still covers what it claims. A moved path, or a
  verification target that no longer exists, is drift — re-detect from the
  satellite's project context and re-point in the same run, the same
  verify-on-consumption re-audit shape used for the Existing
  `hex.md › Pointers` item above; never silently trust it.

### Federation back-pointer slugs still live?

- **Look for:** in a repo whose `hex.md › Pointers` carries a
  `Federation lead:` bullet, whether each plan slug the bullet lists still
  names a live, unfinished plan in the lead. `/hex-init` is **exempt** from
  the satellite halt ([`memory.md` § Location and
  resolution](../../hex-core/references/memory.md#location-and-resolution))
  precisely so it can run this audit and offer removal.
- **Where:** the satellite's `.agents/memory/hex.md`
  `Federation lead:` bullet, and the lead repo it names (resolved by the
  bullet's own path) — check each slug against the lead's plans and their
  Status `State`.
- **Resolved looks like:** every listed slug names a plan that still exists
  in the lead and has not reached State `done`. Offer removal for any slug
  whose lead-side plan is absent or `done`; when the slug list empties,
  delete the bullet — and the `hex.md` file too, if it held nothing else
  (C-313). A second `Federation lead:` bullet naming a different lead is a
  design smell — report it, never auto-merge.

### Workflow fork stamps current?

- **Look for:** every file a `workflows.<skill>.<tier>` pointer names, and
  its `Forked from … @ hex <version>` stamp.
- **Where:** `.agents/workflows/` (the fork files) and the
  `workflows` key in `hex.md › Preferences`.
- **Resolved looks like:** the fork file exists, carries a stamp, and the
  stamped hex version matches the installed one. A stamped version older
  than installed is **drift** — report it with the [fork-drift
  block](#workflow-fork-drift-report) below and show what changed in the
  shipped tier file; never auto-merge or rewrite the fork. A pointer naming
  a missing file, or a fork with no stamp, is reported the same way (the
  run itself falls back to the shipped tier file per
  [`config.md` § Workflows](../../hex-core/references/config.md#workflows)).

## Best-practice blocks

Copy-ready templates `/hex-init` proposes for the gaps above. Fill the
placeholders from what the audit actually found; never paste these
unfilled.

### Verification section

```markdown
## Verification
Run `<command>` before considering any change complete. Covers: <build |
test | lint - whatever it actually runs>. <Anything it doesn't cover, if
relevant.>
```

### Spec / plan / ADR conventions block

```markdown
## Spec / plan / ADR conventions
- Specs and plans live in `<path>`, format: `<format>`.
- ADRs live in `<path>`, format: `<format, e.g. MADR>`.
- Shipped hex templates (`hex-init/assets/templates/`) are the fallback
  only, used when nothing above is documented.
```

### Constitution pointer block

```markdown
- Constitution: `<path>` (optional; plans gated against it when present).
```

### Product doc (provisioned)

A standalone product doc, written to a de-facto home when one exists
(`README`, `docs/`) or to a provisioned `.agents/product.md` — no hex
markers; it is ordinary project documentation.

```markdown
# Product
- What: <one or two sentences: what the product is>.
- Users: <who, and where it runs — local, CI, server, embedded>.
- Related repos: <repositories this product depends on or serves>.
- Docs / spec: <where the spec and user docs are maintained>.
- Research keywords: <terms researchers should search for>.
- Comparable tools: <tools solving the same problem>.
```

### Product index line (context file)

One line in the project-context file so every agent discovers the doc
ambiently; `hex.md › Pointers` records the same location.

```markdown
Product overview: `<path/to/product-doc>` — what it is, who uses it,
comparable tools.
```

Short facts may instead live directly as a `## Product` section in the
context file when there is too little to warrant a separate doc
([`memory.md`](../../hex-core/references/memory.md#destination-of-knowledge)).

### Worktree gitignore line

```gitignore
.agents/worktrees/
```

Never `.agents/` wholesale — `.agents/memory/hex.md` is team-shared
memory and belongs in version control; only the transient worktree
checkouts are ignored.

### Discovery note block

```markdown
<!-- hex:start -->
Swarm memory: `.agents/memory/hex.md` (search upward; pointers + preferences).
Commands: `/hex-init`, `/hex-plan`, `/hex-execute`, `/hex-review`, `/hex-architect`.
<!-- hex:end -->
```

### Workflow fork drift report

Emitted by the re-audit for a fork whose stamped version differs from the
installed hex version (or whose file is missing / unstamped). It points at
what changed upstream and never applies a patch — hex never auto-merges a
fork.

```
Workflow drift: .agents/workflows/<skill>-<tier>.md
  forked from hex-<skill>/tier-<tier>.md @ hex <stamped-version>
  installed hex <current-version>
  shipped changes: <phases added / removed / re-pointed, gates changed>
  Fix: re-fork to adopt the new baseline, or hand-edit the fork; runs use
  the fork as-is until you do.
```
