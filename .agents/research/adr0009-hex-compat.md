# Research: hex-internal compatibility for adr_0009 (`/hex-finalize`)

## Metadata

**Date:** 2026-08-29
**Domain:** devops
**Triggered by:** `/hex-architect .agents/discussions/finalize-phase.md`
**Expires:** 2027-02-28

## Direct Answer

adr_0009 collides with five existing contracts, in descending order of
severity: (1) the **plan lifecycle's terminal state** — `done`/`landing`
already trigger archive and pointer-clear (`archive.md` C-410), so finalize
by design runs *after* the plan is already archived, which argues against a
new Status `State:` value; (2) the **"hex never pushes" statement**, which is
restated verbatim across at least nine shipped files and would need a single
sole-amender site plus a one-clause qualifier at every restatement, not nine
independent rewrites; (3) **fold-back's uncommitted write** (`archive.md`
C-409) sitting in the working tree when finalize's rebase runs — finalize
would be the *first* hex mechanism to commit a fold; (4) the **`tiers`/
`workflows` `<skill>` enumeration** in `config.md`, which is closed to the
four orchestrators and does not include `hex-discuss` today — finalize likely
doesn't need it at all, since nothing in the discussion artifact describes
finalize as tiered; (5) **federation's `landing` state**, which already
reserves the exact slot (converged, approved, not yet merged) finalize wants
to act in, but for N repos, not one — single-repo v1 scope is coherent and
matches the existing "Option F is the documented default, D+E is opt-in"
posture.

## 1. Config vocabulary freeze (adr_0003 / C-223)

[`config.md` § Key vocabulary](../../hex/hex-core/references/config.md#key-vocabulary)
states the freeze precisely: **"v1 — the six Tier A keys… freezes at the
first `grim release`: renaming a frozen key is a silent no-op in every
consumer `hex.md`."** The freeze reaches the six top-level **key names**
(`models`, `adversary`, `limits`, `perspectives`, `research-axes`, `tiers`) —
renaming or repurposing one of those six is what breaks every existing
consumer file silently. It does **not** reach: adding a wholly new top-level
key (v2's `workflows` is the shipped precedent — "v2 — v1 plus `workflows`");
adding rows to a table under an existing key (a `models.overrides` entry, a
`perspectives.always` rule); or prose bullets under `## Preferences` outside
the fenced block (`config.md:24-26` — "Prose bullets continue below the block
and still carry nuance the keys cannot"), which were never versioned at all.

The sharper collision point is **not** the six-key freeze but the `<skill>`
**enumeration** that both `tiers.<skill>.<tier>` and `workflows.<skill>.<tier>`
key off: `config.md § Dotted keys` states flatly — *"The `<skill>` segment is
`hex-plan` / `hex-execute` / `hex-review` / `hex-architect`"* — a closed list
of the four orchestrators. `hex-discuss` (adr_0008's precedent for a new,
non-orchestrator skill) was deliberately **not** added to this enumeration:
`hex/README.md:52` states outright, *"`hex-init` and `hex-discuss` are not
orchestrators and have no tiers."* Nothing in
`.agents/discussions/finalize-phase.md` describes `/hex-finalize` as tiered
(low/medium/high) — it is a single deterministic pipeline (rebase → recompose
→ verify → force-push → flip draft→ready) gated by one explicit invocation,
structurally closer to `hex-discuss` than to the four orchestrators.
**Practical conclusion: adr_0009 should not need to touch the `<skill>`
enumeration, `tiers`, or `workflows` at all** — and doing so anyway would
require its own amendment to that enumeration line, a genuine new C-ID, not a
freebie under the existing freeze.

Whether finalize needs *any* new config surface is a separate, open question.
The discussion's team-preference-discovery decisions (commit conventions,
DCO/signing, expensive-test tiers) are explicitly **discovered from project
context**, not authored as hex config — matching `DESIGN.md`'s Two-layer
knowledge model (`DESIGN.md:41-47`, layer 1 = project context, hex never
duplicates it). If a knob is still needed later (e.g. an explicit override of
the discovered squash-vs-series preference), the closed-list precedent says
that is a **v2-style new top-level key** (its own row in `config.md`'s table,
its own freeze note), not a repurposing of `tiers`/`workflows`.

## 2. Federation (adr_0004) — is single-repo-only a coherent v1 scope?

[`adr_0004_cross_repo_federation.md` § Normative specification](../adrs/adr_0004_cross_repo_federation.md)
already reserves almost exactly the slot finalize wants: a federated plan's
review Approve advances it to **`landing`**, not `done`
(`adr_0004.md:923`, `archive.md` § Plan archive), specifically because "the
window is *held open in the plan*: a federated plan stops at State `landing`,
not `done`, so the satellite locks (C-313) do not expire while the
integration is broken" (`adr_0004.md:443`). That is: hex already models
"converged and approved, not yet actually landed on trunk, N repos involved"
as a first-class state. What it does **not** do — by design, per FM7 (`adr_0004.md`
§ Failure modes → mechanism, row FM7) — is prescribe *how* each repo's branch
gets from `landing` to merged: "the handoff **enumerates the per-repo feature
branches and the required landing order**, and that is all." There is no
atomic cross-repo merge and adr_0004 explicitly says there never will be.

A federated `/hex-finalize` would have to run once **per participating
repo** (lead + each satellite), each rewriting and force-pushing its own
feature branch, in the order the `landing` handoff already enumerates — reusing
C-303's pre-flight access pattern (identity probe, write probe, trunk
discovery) rather than inventing a second one. Nothing here is prohibited by
adr_0004, but two things collide directly with the discussion's own working
positions: (a) the **workspace invariant** — "the checkout where the session
was opened always reflects the long-living feature branch… finalize operates
on/against the primary workspace's branch" — is stated in the *singular*,
which is exactly true for the lead but requires a session with `--add-dir`
access to every satellite (already a federation precondition, C-303) to
finalize the satellites too; (b) the **satellite halt** (`memory.md` §
Location and resolution, `adr_0004.md` § "The refusal (C-308)") fires
unconditionally for the four orchestrators on any repo carrying a
`Federation lead:` bullet — if `/hex-finalize` is not itself one of the
orchestrators the halt currently scopes to, a satellite invocation of
`/hex-finalize` would run *unguarded* against a repo whose memory says it is
mid-federated-change, which is precisely the FM6 class of hazard adr_0004
built the halt to close. **This needs an explicit adr_0009 clause** — either
`/hex-finalize` joins the halt's scoped skill list (like `/hex-init`'s
explicit exemption, `adr_0004.md` § "Scope of the halt"), or it is
deliberately exempted with the same reasoning `/hex-init` got.

Given the discussion's own text never mentions federation and treats
finalize as single-branch/single-PR throughout, **scoping v1 to single-repo
and explicitly deferring federated finalize is coherent** — it mirrors
adr_0004's own "Option F is the documented default, D+E is the opt-in" shape,
and every prior hex ADR (0003, 0004, 0005) shipped one clean vacuous-when-unused
feature rather than the cross product of all open axes. The deferral should
be **stated**, not silent: a plan reaching `landing` with no finalize
mechanism at all continues to work exactly as adr_0004 shipped it (human
sequences the per-repo merges by hand); a plan at plain `done` (or the
not-yet-invented pre-terminal state below) is the v1 finalize target.

## 3. Fold-back (adr_0005 / archive.md) — ordering vs. finalize's rewrite

[`archive.md` § Revert](../../hex/hex-core/references/archive.md#revert) is
unambiguous about the current invariant: **"hex-review never commits and hex
never pushes… Every spec write lands unstaged in the working tree… There is
no hex command that undoes a fold. Reverting is a git operation the human
performs."** A converged, review-approved branch that also folded a spec
delta therefore sits with an **uncommitted** diff (the spec file plus the
plan's own `Folded:` receipt line) in the working tree the moment
`/hex-finalize` would be invoked.

Two concrete hazards follow directly from that fact:

- **A dirty working tree blocks an interactive rebase outright** (git refuses,
  or auto-stashes and can conflict on pop). Finalize's own requirement list
  says "rebases it onto the target branch, then recomposes the whole branch
  diff" — it cannot do that with the fold's write sitting unstaged unless it
  either commits that write first or requires the human to commit/discard it
  before invocation.
- **If finalize commits the fold's write as part of its own recomposition**
  (e.g. folding it into a `docs:` commit), **finalize becomes the first hex
  mechanism that commits a fold** — a new capability, not a reuse of an
  existing one. `archive.md`'s Revert section's claim that reverting a fold
  "is a git operation the human performs" would need an explicit amendment
  noting the one exception (finalize can commit it as part of the rewrite,
  under the same force-push consent), or finalize should refuse to run over
  an uncommitted fold and print the two-command fix (`git add` + `git commit`,
  or `git checkout --` to discard).

Nothing here breaks if finalize runs **after** the fold receipt has already
been committed by a human — that is git history like any other scaffolding
commit, and recomposing it is exactly the job description ("no commits exist
that fix issues… for the things the branch just introduced" — a folded spec
commit is not a fix, it is a deliverable, so it survives recomposition as its
own logical commit or gets merged into the feature commit it documents).
**Recommend**: finalize's pre-flight checks working-tree cleanliness before
touching history, same as archive.md's own step-4 destination-cleanliness
check (`archive.md` § Safety envelope, step 4) — a halt with a named fix, not
a silent stash.

## 4. Plan lifecycle — where does finalize slot in?

This is the load-bearing question and the answer is not obviously "add a
`finalize` state." Two facts pull in opposite directions:

1. **The plan template already anticipates a finalize actor.** The Status
   block's own comment reads: *"Read and mutated by `/hex-plan`,
   `/hex-execute`, `/hex-review`, and **whoever commits and finalizes the
   work**"* (`hex-init/assets/templates/plan.md:20-21`). This phrase predates
   adr_0009 and already treats "finalizing" as a fourth category of writer to
   the *same* Status block, alongside the three orchestrator skills — not as
   a new state, just a fourth writer.
2. **`done`/`landing` are already the archive trigger.** `archive.md` §
   Plan archive (C-410) and `protocol.md` § Upkeep step both key the
   active-plan-pointer clear and the artifact-index write on reaching "the
   plan's **terminal review state** (`State: done`, or `landing` for a plan
   carrying a `Repo` column)." hex-review's Verdict & Output phase is what
   writes that terminal state on Approve (`config.md`'s phase-duty table,
   `hex-review` row). Since the discussion's own requirement is "finalize
   takes a **converged, review-approved** feature branch" — finalize
   necessarily runs *after* Approve, i.e. after the plan is already at
   `done`/`landing`, **after the pointer has already been cleared and the
   plan already archived**.

Those two facts together argue for **not** inventing a new `State:` value.
Inserting one (e.g. `review` → `ready-to-finalize` → `done`) would require
amending hex-review's Verdict & Output contract (`config.md`'s phase-duty
table), `archive.md`'s terminal-state definition (C-410), and `protocol.md`'s
Upkeep step — three sole-amender-owned files, for a state transition whose
only consumer is a skill that (per the discussion) is invoked by explicit,
one-off human action, not resumed or polled by anything else. The lighter,
already-precedented move is: **finalize acts on an already-terminal plan**,
writes its quality-status ledger as a **supplementary line appended to the
existing (done/landing) Status block** — the same act the template comment
already names as legitimate — and does **not** touch `State:`, the pointer,
or the archive index. This also sidesteps the fold-ordering question in §3
for the archive machinery specifically: archive already happened; finalize
is strictly additive to a file nothing else is actively resolving.

The one place this needs an explicit rule, not silence: `archive.md`'s "not
moved and not renamed" clause (C-410) says nothing about whether a `done`
plan may still be *appended to*. adr_0009 should state, in one sentence, that
a post-archive append by finalize is permitted and is not a second archive
event (no second pointer-clear, no second index row).

## 5. Never-push sites

Every shipped-file site asserting hex does not push, force-push, or commit
(excluding one false-positive hit for an unrelated "default push" doc-scaffold
sense in `hex-init/SKILL.md:216`):

| File | Line | Statement |
|---|---|---|
| `hex/DESIGN.md` | 174, 482, 560, 577, 661 | Constitutional statement, restated across the Federation (round 8) and other rounds — "hex never pushes", "hex never commits outside execution" |
| `hex/hex-core/references/protocol.md` | 540, 544 | Worktree mechanics: "never force-push, never rebase a published ephemeral branch"; "landing the feature branch on the trunk is the human's step… hex never pushes" |
| `hex/hex-core/references/archive.md` | 356, 474 | "hex-review never commits and hex never pushes" (Revert section, twice) |
| `hex/hex-core/references/workers.md` | 40 | Universal worker protocol, rule 5: "Never auto-commit… the human decides when to commit and push" |
| `hex/hex-core/references/memory.md` | 161 | Federation pointer grammar: "hex never clones, fetches, pulls or pushes" |
| `hex/hex-core/references/workers/builder.md` | 29 | "never commit" |
| `hex/hex-plan/SKILL.md` | 303 | "Never commit and never push — this skill plans only." |
| `hex/hex-architect/SKILL.md` | 458 | "Never commit and never push — this skill designs only." |
| `hex/hex-review/SKILL.md` | frontmatter, 421, 433 | "Never edits… and never commits" |
| `hex/hex-execute/SKILL.md` | 495, 570, 615 | Constraints: "Never push to remote"; Upkeep: "hex never pushes and records no landing it did not observe locally" |
| `hex/hex-execute/tier-low.md` | 93 | "Never push." |
| `hex/hex-execute/tier-medium.md` | 122 | "Never push — landing the feature branch on the trunk is the…" |
| `hex/hex-execute/tier-high.md` | 148 | "Never push — landing the feature branch on…" |

Two observations beyond the raw count. First, the three `hex-execute` tier
files (`tier-low.md:93`, `tier-medium.md:122`, `tier-high.md:148`) each
**independently restate** the same sentence rather than linking to
`protocol.md:544`, which already owns it — an existing minor violation of
`DESIGN.md`'s "single-source contracts (link, never copy)" rule that
predates this ADR. Second, `hex-execute/SKILL.md`'s Constraints list
(`SKILL.md:570`) is phrased as an unconditional "Never push to remote,"
structurally identical to the other orchestrators' phrasing — **this is the
one line adr_0009 must not touch**, since hex-execute itself gains no
push capability; only `/hex-finalize` does.

**adr_0005's fold-back precedent is the template to follow.** `archive.md`
became the *sole definition site* for fold mechanics, linked from
`hex-execute`, `hex-review`, and `protocol.md`, none of which restate its
rules (`archive.md:6-10`). adr_0009 should do the same: introduce **one** new
reference file (e.g. `hex-core/references/finalize.md`) that is the sole
definition site for the force-push consent model, and amend every site above
with a **one-clause qualifier**, not a rewrite — e.g. `protocol.md:544`
becomes "…hex never pushes, except `/hex-finalize`'s explicitly consented
force-push of the feature branch — see [`finalize.md`](finalize.md)." Nine-plus
independent rewrites of the same sentence is exactly the copy-drift
`DESIGN.md:36` (referenced throughout adr_0004 and adr_0008) forbids; a
one-clause qualifier at each site, pointing at one owned definition, is the
only version of this amendment that stays consistent with the project's own
binding rule (`arcana/CLAUDE.md` § Architecture rules: "single-source
contracts… `protocol.md` owns the Review-Fix Loop").

## 6. New-member structural checklist (adr_0008 precedent)

adr_0008's Provisioning-and-wiring table (`adr_0008_pre_plan_discussion_mode.md`
§ E, C-727 through C-731) is the exact template to repeat. What it did to add
`hex-discuss` + `hex-state`, and the corresponding item for `hex-finalize`:

| adr_0008 did | adr_0009 equivalent |
|---|---|
| `hex.toml` gains `"hex-discuss" = "./hex-discuss:latest"` | `hex.toml` gains `"hex-finalize" = "./hex-finalize:latest"` |
| `publish.toml` gains `[skills."hex-discuss"] path = "hex-discuss"` | `publish.toml` gains `[skills."hex-finalize"] path = "hex-finalize"` |
| Both files' `version` bumps **minor** (`0.2.0`) — new member, no breaking change | Same pattern — minor bump, no `deprecated`/`replaced-by` |
| `hex/CHANGELOG.md` entry | Same, one line naming the new command |
| `hex/README.md` gains a table row (`README.md:38`) + a line in the invocation-order sketch (`README.md:18`) | Same — README's flow diagram needs the seventh command placed after review's Approve handoff |
| `grimoire.toml` root gains `hex-discuss = "./hex/hex-discuss"` | `grimoire.toml` gains `hex-finalize = "./hex/hex-finalize"` |
| `hex/DESIGN.md` gains a dated round (round 9, "Discussion-mode round") with a scoped constitution-deviations table | `hex/DESIGN.md` gains round 10 (rounds 2, 5, 6, 7, 8, 9 are taken) — this is exactly the "amends the never-push contract" round the discussion artifact itself already names as the trigger for routing to `/hex-architect` |
| A rule artifact (`hex-state.md`) + its own `[rules]` entries in both TOMLs | Open — see below |
| `memory.md` gained one sibling rule + one placement sentence (C-729) rather than a new section | Likely equivalent: one clause on how a `finalize`-owned Status-block append relates to `## Memory`'s destination-of-knowledge rules (§4 above), not a new section |

**Does finalize need a rule artifact, per `workers.md`/`hex-state.md`'s
precedent?** `hex-state.md` exists because `hex-discuss` introduces
**cross-session, in-flight state** (a `State: active` discussion artifact)
that another mode could stumble into and edit unsafely without an always-on
tripwire (`.claude/rules/hex-state.md`: "Any discussion artifact at `State:
active`… → no code or config edits"). Finalize has a structurally similar
hazard: an **interrupted rewrite** — backup ref created, history rewritten,
but the force-push or the draft→ready flip never completed — leaves the
feature branch in a state where another hex mode (most obviously a resumed
`/hex-execute` on the same plan) could stack fresh scaffolding commits onto
already-rewritten history, or a second `/hex-finalize` invocation could
re-rebase over a half-finished rewrite. This is exactly the "silent wrong
behaviour is the worst outcome" class adr_0004 named as its top decision
driver. The discussion's own open thread already proposes a `backup/<branch>-
pre-finalize` ref; that ref (present without a matching completion marker)
is a natural, already-planned artifact to double as the in-flight signal —
avoiding a wholly new artifact class, the same "reuse what already carries
state" instinct that made `hex-state.md`'s design cheap. **Recommend a short
rule artifact analogous to `hex-state.md`**, keyed on "a `backup/<branch>-
pre-finalize` ref exists with no completion marker → halt, do not
merge/rewrite/commit onto `<branch>`" — cheap to add now, expensive to retrofit
once a real interrupted-rewrite incident happens.

**Does finalize need a new worker role, per `workers.md`?** No shipped role
does git rewrite or push today. But `hex-execute`'s "Merge and commit" duty
(`config.md`'s phase-duty table: *"**Merge and commit** merges the worktree
and commits"* — notably with **no role prefix**, unlike every other duty in
that row) is already performed by the **orchestrator itself**, not a
dispatched worker — `workers.md`'s "Never auto-commit" rule (universal
worker protocol, rule 5) binds *workers*, and orchestrators already commit.
`/hex-finalize` extending that same precedent from commit to push is a
direct, minimal-blast-radius reuse: **no new role, the orchestrator (or a
non-orchestrator skill following the same shape as `hex-discuss`) performs
the rewrite and push itself**, consistent with how `hex-execute` already
breaks the worker-level "never commit" rule at the orchestrator level.

## Recommendation

Scope adr_0009 to single-repo v1 (Option F federation posture, deferred
opt-in like adr_0004's own D+E), and design finalize as a **post-terminal**
actor rather than a new plan lifecycle state: it runs after hex-review's
Approve has already written `State: done`/`landing` and archive.md's Upkeep
has already cleared the active-plan pointer, and it appends a quality-status
line to that same (already-archived) Status block — reusing the writer role
the plan template already names ("whoever commits and finalizes the work")
rather than inventing a `ready-to-finalize` state that would require
amending hex-review's Verdict & Output contract, archive.md's terminal-state
definition, and protocol.md's Upkeep step all at once. Do not touch
`config.md`'s `tiers`/`workflows` `<skill>` enumeration — finalize isn't
tiered and doesn't need it, matching the `hex-discuss` precedent exactly. Do
require a pre-flight working-tree-cleanliness check before any rebase, to
close the fold-back collision (§3), and require finalize's pre-flight to
either join the federation satellite halt's scoped-skill list or be
explicitly exempted with stated reasoning, the same way `/hex-init` was
(§2). Treat the "hex never pushes" amendment the way adr_0005 treated
fold-back: one new sole-definition file (`hex-core/references/finalize.md`),
a one-clause qualifier at each of the ~13 existing restatement sites (§5),
and a dedicated DESIGN.md round 10. Add a short rule artifact paralleling
`hex-state.md`, keyed on an in-flight backup ref, to close the
interrupted-rewrite hazard (§6) — cheap now, and consistent with adr_0004's
top decision driver that silent wrong behavior is the failure mode hex
designs against everywhere else.
