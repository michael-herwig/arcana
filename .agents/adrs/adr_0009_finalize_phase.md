# ADR: The finalize phase — the `/hex-finalize` command, the scoped remote-rights amendment, and the convention-discovery contract

## Metadata

**Status:** Accepted (Michael, 2026-08-29 — at the implementation plan's meta-plan gate)
**Date:** 2026-08-29
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A (originated in the 2026-08-29 dogfood discussion, persisted as `.agents/discussions/finalize-phase.md`)
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below
      (one `DESIGN.md` round with two amendments + one `protocol.md`
      deviation + one `memory.md` scope amendment + one `adr_0008` C-718
      cap amendment — see [Constitution deviations](#constitution-deviations))
**Domain Tags:** devops, security (a bundle member + the bundle's first remote-write capability)
**Supersedes:** N/A
**Superseded By:** N/A

*Template slots deliberately omitted: **Quantified Impact** (a markdown skill
bundle has no latency, throughput or SLO metric to quantify — the one real
number, CI spend, is in the Cost NFR), **Technical Details › Data Model** (no
entities; the only durable object is a git ref), and **Trending approaches**
as a standalone line (it is the substance of § Industry Context and would be
a second, drifting copy).*

## Context

A hex run ends at review. `/hex-review` writes `Approve`, the plan reaches
its terminal state, the pointer clears — and the feature branch is left
exactly as execution built it: a pile of scaffolding commits, unrebased,
with whatever signature and sign-off state the rewrites happened to leave.
Everything between "the work is right" and "this is a pull request someone
can merge" is hand work. The owner did it by hand for `adr_0008` on
2026-08-29 and flagged the missing method in the same breath.

The intent, the requirements, the ratified working decisions, and the
nine-artifact research index are in
[`.agents/discussions/finalize-phase.md`](../discussions/finalize-phase.md).
This ADR does not restate them. Its **Decisions** section is owner-ratified
and is treated as constraint, not as a position to re-litigate: the mode
surface is a **new command**; **force-push is in scope** with the invocation
carrying the consent; **merging stays human**; conventions are **discovered,
never invented**; the **workspace invariant** holds (the checkout the session
opened is the long-living feature branch). Where the dossier and a research
finding conflict, **the dossier's ratified decisions win on *what*, and
research wins on *how*** — and where this design departs from a dossier
*recommendation* (as distinct from a ratified decision), the departure is
named as a departure, not smoothed over. There are two, both in § F6.

### The central constraint

hex's most-restated invariant is that **hex never pushes**. It is load-bearing
three times over: it is what makes every hex effect local and revertible
(`adr_0004`), what makes every fold reviewable at `git diff` and undoable at
`git checkout --` (`adr_0005`), and what lets the bundle ship markdown to any
harness without ever asking what credentials that harness holds. Finalize is
the first hex mechanism that must break it.

It also breaks it in the most dangerous available direction. The act is a
**force-push** — the one git operation that destroys history rather than
adding to it — carrying commits that may bear a **`Signed-off-by:` line**,
which is not a formatting convention but a first-person legal certification
(*"By making a contribution to this project, **I** certify that…"*,
[developercertificate.org](https://developercertificate.org/)), and a
**cryptographic signature** made with the human's own key. It decides what to
write by reading files an attacker can edit through an ordinary pull request.
And it **dispatches CI workflows whose definitions are read from the branch
ref** — which is to say it executes code from the artifact under change.
Five sharp edges, one command.

Five surfaces are in scope and they are one decision because each is
load-bearing for the others: (a) the command, (b) the recomposition and
verification contract, (c) the remote act set, (d) the convention-discovery
contract, (e) the scoped amendment to the never-push invariant and its
sole-definition file.

## Decision Drivers

- **Irreversibility containment** — the run's one irreversible act destroys
  history and makes a legal attestation. Every other property is negotiable
  against this one.
- **Completing the loop** — the problem statement is a ready-to-merge PR. A
  design that stops halfway and hands the rest back as instructions has not
  solved it.
- **Protocol fit** — hex has exactly one approval gate, one handoff block,
  single-source contracts, and no literal model names. Deviations are
  permitted; unstated ones are not.
- **Least surface** — one member, one reference file, one rule line, zero
  config keys, zero new worker roles, zero new lifecycle states.
- **Portability and graceful degradation** — `gh` and `glab` both first
  class, and the whole remote half must be optional without the local half
  losing correctness. **First class does not mean identically shaped:** the
  two forges differ in their unit of CI dispatch (GitHub has one per workflow
  file, GitLab one pipeline per ref), so the contract states the *outcome* —
  the documented release checks ran against the final SHA — and lets each CLI
  reach it its own way (C-813).

## Industry Context & Research

**Research artifacts** (all in `.agents/research/`, all
`Expires: 2027-02-28`), cited below by their title lines:
*Automating feature-branch finalization before merge*;
*Commit-Message Conventions and Changelog-Generation Frameworks (2025–2026
Landscape)*; *Detection recipe for reading a team's git/landing preferences*;
*Who Rewrites Feature-Branch History, When, and With What Etiquette*;
*Rules Governing the Shape of a Final Commit Series Before Landing*;
*Preference-Adaptive Developer Tooling*; *How AI Coding Agents Handle
Branch-Landing/Finalization and Team Git Conventions*; *OSS Projects with
Strict Pre-Landing Git History Conventions*; *Where teams codify git/landing
preferences in and around a repo*; *Finalize-Phase Failure Modes & Recovery
Patterns*; *hex-internal compatibility for adr_0009 (`/hex-finalize`)*;
*Security surface of an agent holding remote-rights (finalize)*.

**Key insight — the field gap is judgment, and it is narrowing at the
edges.** *Automating feature-branch finalization before merge* finds **no
end-to-end mechanism**: six narrow layers exist and **deciding commit
boundaries and content is the part nothing automates end to end**.
*How AI Coding Agents Handle Branch-Landing/Finalization and Team Git
Conventions* confirms it from the other side — Copilot pushes WIP commits and
treats draft→ready as the human's finalize signal, Cursor batches one commit
at completion, and the spec-driven frameworks are silent on git finalization
entirely. **The honest qualifier:** `jj absorb` (and `git absorb` before it)
*does* mechanically fold fixup hunks into the commits that introduced them,
by blame. So "nothing automates any of this" is too strong; what nothing
automates is **choosing the boundaries in the first place** — absorb
redistributes into an existing series, it does not decide what the series
should be. C-807 records absorb as a declined mechanical pre-pass rather than
pretending it does not exist.

**Second — the shape of the answer is not a matter of taste.**
*Rules Governing the Shape of a Final Commit Series Before Landing* finds
**three universals** across kernel, Node.js, Kubernetes, Rust, Zephyr and
curl — the commit boundary is a logical, independently-correct change and
never a size; fixup/WIP/review-response commits never survive; message
structure is enforced, not advisory — and exactly **two genuine conflict
axes**: the default commit count per PR (squash-to-one versus a bisectable
series) and which test triggers the squash decision. That split is the whole
design of the convention-discovery contract: bake the universals, discover
the two axes.

**Third — the ordering is fixed by one sentence, and only one source says
it.** Every rewrite-etiquette source frames the cost of rewriting as lost
reviewer diff-visibility. Only the Linux kernel's maintainer documentation
names the *testing* cost: a reparented series "invalidates much of the
testing that was done… should be treated like new code and retested from the
beginning" (*Finalize-Phase Failure Modes & Recovery Patterns*, citing
[docs.kernel.org](https://docs.kernel.org/maintainer/rebasing-and-merging.html)).
That makes verify → rewrite → push → remote-CI the only defensible order.

**Fourth — containment is structural, and hex's own share of it is small.**
*Security surface of an agent holding remote-rights (finalize)* finds the
nearest field precedent in GitHub's Copilot coding agent, which contains a
repo-writing agent by **branch-name restriction** — no write access outside
its own prefix — rather than by trusting the model. It also finds the live
threat class is not hypothetical: a PR title alone was enough to make
Anthropic's, Google's and GitHub's own review actions post secrets; an
injected issue title stole an npm publish token and shipped an unauthorized
`cline` release; Wiz documented a 500+-PR campaign built to harvest CI
credentials. **The parity claim must be stated honestly, and this ADR
corrects an earlier over-reach:** Copilot's restriction is enforced
*server-side*, by the forge, against a credential that cannot reach other
branches. hex ships markdown; **its act-set enumeration is prompt text, and
prompt text is a design constraint on a cooperative agent, not a control that
survives a compromised one.** The controls that actually hold are outside
hex — **target-branch protection** ("restrict force pushes" plus a required
pull request) and the **harness's own command allowlist** — and C-826 makes
recommending the first of those an audit item rather than leaving it implied.
Copilot's *other* control, human approval of workflow runs triggered by the
agent, is the one this design must not silently drop; C-813 addresses it.

**Fifth — where conventions live, and the trap.** *Where teams codify
git/landing preferences in and around a repo* finds the forge's
branch-protection/ruleset API is the only truly authoritative surface and that
**configuration presence never implies enforcement**. *Detection recipe for
reading a team's git/landing preferences* names the specific trap: the
non-admin-readable rulesets endpoint returns rules from rulesets **only**, so
a repo protected by classic branch protection answers `200 OK` with an empty
array — which a naive reader takes for "nothing enforced." Unknown is
therefore never unenforced. *Preference-Adaptive Developer Tooling* supplies
the interaction norm — eleven tools, all detect silently with a config
override, none ask — and Renovate's flip-flopping on inconsistent repos is
why hex departs from that norm in one direction only: detect silently,
**disclose always**, ask only on ambiguous signal.

**Sixth — changelog generation stays out.** *Commit-Message Conventions and
Changelog-Generation Frameworks (2025–2026 Landscape)* splits the field into
enforcers (semantic-release, release-please — full automation bought with
standing CI push and tag rights), format-agnostic generators (git-cliff,
cocogitto — clean output over curated linear history, **no repo permissions
at all**), and convention-free change-file schemes. Finalize's job is to
produce the input the second family reads cleanly. Generating the changelog
would buy a release-time concern with a permanent increase in what finalize
is allowed to write.

## Considered Options

Four options for where the run's boundary and its one gate sit. All four
honor the ratified constraints (new command, force-push in scope, merge stays
human); they differ on **how the irreversible act is consented to and how much
of the loop closes**.

### Option A — One command, one gate at the local/remote boundary (recommended)

**Description:** `/hex-finalize` runs pre-flight → conventions → local verify
→ recompose → **gate** → remote. Everything before the gate is local and
reversed by one command against a backup ref; nothing leaves the machine
before the gate. The gate shows the exact recomposed commit list with its
sign-off, signing identity and signature state, the resolved conventions with
their sources and trust classes, the acting credential, and the enumerated
remote acts.

| Pros | Cons |
|------|------|
| The gate sits where the irreversible act is and shows what cannot be shown any earlier — the concrete commit plan does not exist until the rewrite is computed | The gate's *position* deviates from "before any work starts": it needs the third named entry in `protocol.md`'s closed exemption list |
| The DCO attestation and the signature set are in front of the human before they become an irreversible public record — the one real gap the security research found in the ratified design | Pre-gate work is destructive-in-the-small (the local branch is rewritten before consent), bounded by the backup ref rather than by abstinence |
| Closes the loop: one invocation, one approval, a ready-to-merge PR | One member, one reference file, four qualifier sites, one rule line, one cap amendment |
| Degrades along a stated ladder — no forge CLI leaves a correct local-only finalize, which is Option D reached automatically | |

### Option B — Invocation-only consent, no gate

**Description:** the literal reading of "force-push is consented by
invocation." Rewrite, push, dispatch, flip — no approval point at all.

| Pros | Cons |
|------|------|
| Fewest interactions; closes the loop in one uninterrupted run | hex has **exactly one approval gate per run** everywhere; zero gates is a deviation no prior ADR has taken, and it removes the only place the resolved conventions could be disclosed |
| Smallest surface — no gate contract, no gate rendering | The human's key signs, and their name attests to, a commit list they never saw. Mechanical `--signoff` over an unseen list is the one use of the DCO its own first-person text forbids |
| | A wrong convention read (the classic-branch-protection empty-array trap) becomes a wrong force-push with no interception point |

### Option C — Two commands: local finalize, then a separate promote

**Description:** `/hex-finalize` recomposes and verifies locally and stops; a
second command performs the remote acts. The human's invocation of the second
command is the consent.

| Pros | Cons |
|------|------|
| The consent boundary is a command boundary — the cleanest possible statement of "nothing remote happened without a second human act" | Two members, two handoff blocks, and cross-command state that must be re-derived — the second command has to reconstruct which rewrite it is promoting |
| Each command keeps a conforming single gate | Two gates across one logical operation. The dossier ratified **a** new command, singular, and the second invocation is the same approval Option A gets inside one run — bought with a whole extra install surface |
| | The re-entry contract doubles: an interrupted first command and an interrupted second command are different states with different recoveries |

### Option D — Local-only finalize; the remote half stays manual

**Description:** recompose, satisfy commit requirements, verify locally, print
the exact remote commands for the human to run. hex never pushes, unamended.

| Pros | Cons |
|------|------|
| Perfect *remote* containment — nothing leaves the machine, and no credential question exists | **Does not solve the stated problem.** "A ready-to-merge, ready-to-release pull request" is the requirement; this delivers a rewritten local branch and a list of chores |
| Smallest surface of all four; portable everywhere by construction | **It does not actually conform better on the gate.** D still rewrites history locally and still produces commits carrying a DCO attestation, so it needs the *same* relocated gate before printing the commands — it buys no protocol-fit premium, only a shorter tail |
| Captures most of the *value* — commit-boundary judgment is the un-automated part | Handing the push to a human by copy-paste re-opens both failures the ordering exists to close: the lease must be pinned to the SHA *this run* fetched, and the checks must be dispatched against the SHAs the rewrite just produced |

## Decision Outcome

**Chosen Option:** Option A — one command, one gate at the local/remote
boundary.

### Weighted scoring, and its sensitivity

Criteria and weights follow the Decision Drivers; scores 0–100, higher is
better.

| Option | Irreversibility containment ×30 | Protocol fit ×20 | Completes the loop ×20 | Least surface ×15 | Portability / degrade ×15 | **Total** |
|---|---|---|---|---|---|---|
| **A — one command, gate at the local/remote boundary** | 90 | 85 | 95 | 70 | 85 | **86.3** |
| D — local-only, remote stays manual | 100 | 85 | 40 | 90 | 100 | 83.5 |
| C — two commands | 90 | 60 | 80 | 45 | 85 | 74.5 |
| B — no gate | 30 | 40 | 100 | 85 | 85 | 62.5 |

**Two cells decide this table, and both are defended rather than asserted.**

- **D's protocol fit is 85, not 100.** D is not the definition of
  conformance: it rewrites history locally and mints commits carrying a
  first-person legal attestation, so it needs the *same* gate at the *same*
  position, before it prints the commands the human will paste. Its only
  protocol advantage is that it leaves the never-push sentence unamended,
  which is worth something but is not a different gate story. A and D
  therefore tie here.
- **A's irreversibility containment is 90 against D's 100.** That gap is
  real and is not argued away: D genuinely performs no irreversible remote
  act, and A does. A is not scored equal to D; it is scored close, because
  A's remote act is confined to one branch, anchored by a backup ref,
  disclosed in full at a gate, and hard-stopped on a lease rejection.

**The ranking is not robust, and the decision does not rest on the total.**
At A-irreversibility 80 (or below), D wins; the margin is 2.8 points on a
100-point scale. What carries the decision is a specific argument the totals
only approximate: **the two steps D hands back are exactly the two that
cannot be performed correctly outside the run.** A `--force-with-lease` value
must be pinned to the SHA *this run* fetched — bare `--force-with-lease`
degrades to plain `--force` the moment any background fetch updates the
tracking ref — and a `workflow_dispatch` must target the SHAs the rewrite just
minted, because checks against pre-rewrite SHAs are invalidated work.
Copy-pasting those into a terminal an hour later is precisely the failure the
ordering exists to prevent. **D is not a rejected alternative but A's own
degraded mode** (C-811 § degrade ladder), reached automatically when no forge
CLI is available — the same relationship `adr_0008` established between its
Options A and B, and the reason the local-only rung must stay a first-class
outcome with a full gate and a full handoff.

B is rejected on the DCO finding, not on process aesthetics. C is rejected on
surface: it buys the same approval A gets inside one run and pays a second
member, a second handoff, and a doubled re-entry contract for it.

### The reconciliation flags, resolved

**F1 — consent model.** The dossier ratified "force-push consented by
invocation"; the security research wants the exact rewritten commit list and
its sign-off lines disclosed immediately before the push. **This design
narrows the ratified grant, and says so.** The invocation grants the
**action class** — that this run will rewrite and force-push *this* branch,
and that no separate out-of-band authorization ceremony will be demanded — and
hex's one mandatory approval gate **narrows that grant to a disclosed
instance**: this commit list, these sign-offs, this signing identity, this
lease target, these three post-gate remote acts. Calling it "not a second
consent event" would overclaim: it *is* a consent point the dossier's literal
text did not require. The ground for narrowing is that the dossier's own
Requirements already say "hex protocol conventions apply: single approval
gate", so the gate exists regardless; the only open question was where it sits
and what it carries, and that is a *how*, which research wins (C-805).

**F2 — gate exemption versus adoption.** Finalize **adopts** the single-gate
contract in count (exactly one) and **deviates in position** (at the
local/remote boundary, not before any work starts). `protocol.md`'s exemption
list is closed and, per the 2026-08-29 review ruling on `adr_0008`'s
deviation 1, is scoped to *named* skills and never inherited by class analogy.
So finalize takes **the third named entry with its own stated ground** — the
concrete commit plan does not exist until the rewrite is computed, and
everything before the gate is local and reversed by one command against the
backup ref (`protocol.md` deviation, below; C-805).

**F3 — credential model.** **The ambient `gh`/`glab` login is the shipped
default and is disclosed, never silently assumed; a project-provisioned
scoped credential is supported without being required; no forge CLI degrades
to local-only.** hex ships markdown and provisions no credentials — which
credential a project uses is a Layer-1 project-context fact, exactly like
which command verifies it. Requiring a minted fine-grained PAT would make
finalize unusable on the common path. What *is* addressable is silence: the
gate names the acting identity, **which credential source is in force** (a
`GH_TOKEN`/`GITLAB_TOKEN` environment override versus the ambient login) and,
where the CLI reports them, the credential's scopes beside the rights this run
needs (C-817). The containment that does the real work is structural and
mostly **outside hex** — branch identity in the act set, and target-branch
protection plus the harness allowlist on the outside (C-826).

**F4 — the fold commit.** **Finalize never commits a fold.** `adr_0005` made
the fold land *uncommitted* precisely so that `git add` is where the human
approves it; a finalize that commits the fold to get a clean tree would delete
that consent point and then force-push the result. Instead, pre-flight
**halts on any dirty working tree** with a named fix, and the halt is
**fold-aware**: when the dirty paths are exactly a fold's write set, the
message says so and prints the `git add`/`git commit` pair. The human's
`git add` stays the fold's consent act; the resulting commit is then ordinary
history that recomposition treats like any other deliverable. No new
capability, `archive.md` § Revert untouched (C-804).

**F5 — `hex-state`.** **One line added to `hex/hex-state.md`**, not a second
rule artifact — `adr_0008`'s round-9 amendment 2 states the intent directly.
The predicate is a git ref, as externally checkable as C-718's file check.
**The cap needs an explicit amendment and gets one** (C-821): C-718 says
"≤10 lines" with no measure qualifier, the shipped body is **exactly 10
physical lines**, and a second mode line written like its sibling is ~3
physical lines. Silently redefining the measure as "non-blank" to make the
arithmetic work would be exactly the kind of quiet reinterpretation C-718
exists to prevent, so this ADR **amends the cap in the open** — to 14 physical
lines with the ground stated, plus the round-9 erratum's missing counterpart:
the **description-line budget** (C-801), which the erratum requires every new
member's ADR to budget and which `adr_0008` itself never carried forward.

**F6 — the dossier's four open-question markers, and two departures.** All
four markers are resolved by research and none survives; the ADR's own cap of
three is now down to **two**, because R13's fix folded the second into the
contracts. The **quality-status ledger** lives in a marker-fenced PR-body
block with a one-line mirror on the plan's terminal Status block (C-814,
C-822). **Changelog generation is out of scope.** **PR-mutation rights** are
the scoped set the security research enumerated. **The backup ref departs
from the dossier's Recommended in two ways, both named here rather than
absorbed:** the dossier recommended creating it "before the force-push" and
"delete after the PR merges"; this design creates it **before the first
history-modifying operation** (earlier — the force-push is not the first
destructive act, the rewrite is) and **never deletes it, renaming it instead**
(different — finalize never observes the merge, so a delete-after-merge rule
would have no trigger, and a rename gives the armed/inert distinction the
rule line's predicate needs). Both departures are on *how*, and both are
research-grounded (C-809).

### Consequences

**Positive:**
- The lifecycle closes. `/hex-plan` → `/hex-execute` → `/hex-review` →
  `/hex-finalize` produces a rebased, recomposed, verified, ready-to-merge
  pull request, and the human's remaining act is the merge.
- Scaffolding history stops reaching the trunk. The thing the owner did by
  hand for `adr_0008` has a method, and the method is the one every surveyed
  project already follows.
- The bundle gains a *stated* remote-rights boundary. Before this ADR, "hex
  never pushes" was true by abstinence; after it, the boundary is written
  down in one file, scoped to one branch, and every other site links to it.
- Zero new config keys, zero new lifecycle states, zero new worker roles,
  zero spawns.

**Negative:**
- hex is no longer local-only. A user who trusted the bundle *because* every
  effect was revertible with `git checkout --` now has one command that
  isn't, and that must be discoverable from the README rather than learned.
- The remote half is a multi-class capability (four rungs, C-811). The ladder
  is stated, but it is a second behavior to understand.
- A seventh command enlarges what `/hex-init` audits and what a new adopter
  must read before the first run, and it raises the always-on rule budget.

**Risks:**
- **A hostile `CONTRIBUTING.md` steers the rewrite.** Mitigation: checked-in
  text may only ever **narrow** finalize's behavior, and the set of
  conventions it may narrow at all is enumerated and **excludes the target
  branch, the merge strategy and the workflow list**, which are
  authoritative-class only (C-815, C-816).
- **A dispatched workflow is branch-defined code.** `gh workflow run --ref
  <branch>` executes the workflow *as defined on the branch*; only its
  presence on the default branch is required to be dispatchable. Mitigation:
  the workflow list is authoritative-class (documented ∩ forge-dispatchable),
  **branch-versus-target workflow drift is named at the gate**, inputs are
  never sourced from any untrusted string, and the forge's own
  human-approval-for-triggered-runs control is named as the backstop that
  actually holds (C-813).
- **The empty-array trap reads as permissive.** Mitigation: an empty or
  unreadable enforcement read is recorded as **unknown, never unenforced**
  (C-815), disclosed at the gate as `unknown`.
- **The signing oracle is available for the session's duration.** Mitigation
  is the act-set enumeration plus the harness allowlist named in C-826; hex's
  own share of this is prompt text and the Security NFR says so.
- **A stale lease passes.** Mitigation: the lease value is **pinned to the SHA
  fetched at pre-flight** rather than to the tracking ref, `--force-if-includes`
  is issued with it unconditionally, and a rejection is a **hard stop** with
  diagnostics that distinguish "someone pushed" from "cannot prove
  integration" (C-812).
- **An interrupted or declined run leaves a rewritten branch.** Mitigation:
  the armed backup ref plus the `hex-state` line halts other hex modes on
  that branch (C-821); **every terminal outcome — success, decline, or a halt
  after the rewrite — renames the ref inert, which releases the lock**
  (C-809); and every resume that has not yet pushed re-enters at the **gate**,
  never at the push (C-818).

## Component contracts

Contracts are numbered `C-8xx`; UX scenarios `S-8xx` (`adr_0001` `C-00x`,
`adr_0002` `C-1xx`, `adr_0003` `C-2xx`, `adr_0004` `C-3xx`, `adr_0005`
`C-4xx`, `adr_0006` `C-5xx`, `adr_0007` `C-6xx`, `adr_0008` `C-7xx`/`S-7xx`).
Home names the single definition or edit site. **Round-1 panel fixes amended
contract text in place; nothing was renumbered.** One scenario was added,
extending the scenario range contiguously to **S-813**.

### A. The command

| ID | Contract | Home |
|---|---|---|
| **C-801** | **Identity, entry, exit, packaging, and both always-on budgets.** `/hex-finalize` is **a hex skill, not a fifth orchestrator**: no `classify.md`, no `overlays.md`, no `tier-*.md`, no tier vocabulary — the flow is one fixed pipeline, and C-807's universals do not scale with blast radius. **Body budget ≤400 lines**, measured on the body (H1 onward, frontmatter excluded), with one pre-authorized `references/` split. **Description budget — the round-9 erratum's counterpart, carried forward here because `adr_0008` never did:** the frontmatter `description` is a second permanent always-on surface, it carries **entry triggers only and never duplicates body prose**, and it is budgeted at **≤2 rendered lines**; this member takes the bundle from six shipped descriptions to seven, which is stated as a cost rather than discovered later. **Packaging:** frontmatter sets `claude.user-invocable: "true"` **and** `claude.disable-model-invocation: "true"` — the `hex-init` precedent, applied for a sharper reason: the invocation *is* the grant for the action class (C-805), so it must originate with a human and must never be reached by a model matching a description. Entry is explicit invocation only; exit is the handoff block (C-806) or a pre-flight halt. | new `hex/hex-finalize/SKILL.md` |
| **C-802** | **Argument syntax and the workspace invariant.** `/hex-finalize [<target-branch>]`. The target is resolved from **authoritative sources only** (C-815) in precedence order: the explicit argument, else the open PR's base field, else the discovered trunk — and it is echoed at the gate with its source. **An explicit argument that contradicts an open PR's base field is a hard stop at discovery, not an override** [erratum, adversary round, 2026-08-29]: acting would rebase onto one target while readying a PR that lands another; the `Fix:` names the two exits — drop the argument (the base field wins by precedence) or retarget the PR by hand — and finalize never retargets the PR itself, which would widen C-811's fixed act set. The stop rides the discovery phase like C-812's push rejection, outside C-804's six pre-flight halts, so no count changes. **No tier argument** (there are no tiers) and **no `--local` flag**: the degrade ladder selects the local-only rung by itself (C-811), and the gate is a real approval on every rung, so a flag would be a second way to reach a state the ladder already reaches. **The workspace invariant is enforced, not assumed** — pre-flight refuses to run in an agent worktree (check 4, C-804), because finalizing from a worktree would rewrite a branch the session did not open and the invariant exists to prevent exactly that. | `hex-finalize/SKILL.md` § Argument syntax |
| **C-803** | **Six phases, one fixed order, no re-ordering knob.** **1. Pre-flight** (C-804) → **2. Resolve conventions** (C-815) → **3. Local verification** (C-810) → **4. Recompose** (C-807, C-808, C-809) → **5. Gate** (C-805) → **6. Remote** (C-811 … C-814). The order is not stylistic. Verification runs **before** the rewrite, on the tree that exists, because it is cheap and because the rewrite invalidates it as *testing evidence* per the kernel's own framing. The rewrite's own rebase onto the freshly-fetched target is the **structural second check** — a conflict halts. **Where that rebase moves the branch onto a base that advanced since verification ran, the local suite re-runs once, before the gate; where the base did not move, it does not** (this is the folded-in resolution of what was an open question in the draft — the contracts and the rendered gate now state one position, not two). The expensive remote suites run exactly once, after the push, against the SHAs that will ship. Phases 1–4 are local and reversible; phase 6 is not. The gate is the seam. | `hex-core/references/finalize.md` (C-819) |
| **C-804** | **Pre-flight — three resolution steps and six halting checks, in this order.** *Resolution (not halts):* **(a)** probe the forge CLI for presence, authenticated identity, credential source and reported scopes — absence selects the local-only rung (C-811), it never halts; **(b)** resolve branch and target (C-802); **(c)** fetch **both** the branch's upstream **and the target ref** from the remote, once, record the branch's fetched SHA as the lease pin (C-812), **and assert `git merge-base --is-ancestor <pinned-sha> <branch>`** — the integration proof, made here because ancestry still exists to test and because after the rewrite the answer is meaningless [erratum, WP2 panel, 2026-08-29: this replaces `--force-if-includes`, a documented no-op under the pinned-lease form]. The target is fetched, never read from the local ref: a stale local target would make the rebase publish local commits the remote has never seen. **A failed fetch here is halt (6) below, not a rung** — every rung rebases onto a fetched target, and the only fallback would be the local ref this clause forbids. *Halts, each with a named `Error:`/`Fix:` pair and no writes:* **(1)** invoked on the target branch; **(2)** **not the primary checkout** — an agent worktree is refused, detected by the repository's own worktree state, closing the workspace-invariant hole (C-802); **(3)** **working tree not clean** — the halt is **fold-aware**: when the dirty set is exactly `/hex-review`'s fold write (the resolved spec file plus the plan's `Folded:` receipt), the message names it as the fold and prints the `git add` / `git commit` pair, because that `git add` is `adr_0005`'s consent point and finalize must not take it (F4). **The halt has a recompose-aware variant, and it takes precedence on the simplest possible predicate: an *armed* backup ref plus any unclean tree.** The armed name exists only while a run is in flight (every terminal path renames it inert, C-809), so armed-and-dirty means one thing — a recomposition interrupted somewhere between `reset --soft` and its last re-commit. Matching on the staged diff instead would be wrong: it holds only in the instant before commit 1 of N and goes false for the rest of the build window, which is most of it. The printed `Fix:` is the recovery — `git reset --hard <armed ref>`, then re-run — never the fold pair, which would freeze a half-built series into history. The fold variant fires only when **no** ref is armed, which is every ordinary pre-flight; **(4)** branch has no commits the target lacks; **(5)** repo is a federation satellite — the C-308 halt with finalize's own `Fix:` (C-824); **(6)** **resolution (c) could not establish a trustworthy base** — either **the fetch failed** (no fetched target means nothing trustworthy to rebase onto, and the local target ref is not a fallback) **or (ii) the pinned SHA is not an ancestor of the local branch tip**, meaning this checkout has not integrated what the remote already carries and a force-push would discard it. **Two diagnostics, one halt, and the count stays six** [erratum, WP2 panel, 2026-08-29]: commits that are someone else's work → reconcile by hand; work this checkout merely lost track of (fresh clone, hard reset, dropped reflog) → establish integration locally, **never** force past it. This is the one remote failure the degrade ladder does not absorb: an absent or unauthenticated *forge CLI* selects the local-only rung (step a), but a broken *git transport* halts. | `hex-finalize/SKILL.md` § Pre-flight; halt texts in `finalize.md` |
| **C-805** | **The single approval gate, positioned at the local/remote boundary, on every rung.** Finalize asks for **exactly one** approval. Its position differs from the shared shape because the thing it must disclose — the concrete recomposed commit list with its attestations — **does not exist until the rewrite is computed**. **The gate is a publication gate, and the framing is stated in it:** the pre-gate commits already carry a `Signed-off-by` line and a signature, but they exist only in a local ref that a reset destroys; the gate is where that attestation becomes a public, permanent record. It therefore asks on **every rung, including local-only**, where the approval covers the recomposed series itself (the human publishes by hand afterwards) — a rung that skipped the gate would let an unreviewed attestation reach a `git push` the human types five minutes later. The gate follows `protocol.md`'s `<label>: <resolved value> (<source>)` shape and carries, mandatorily: branch and target with their sources; every **resolved convention with its source and its trust class**, `unknown` rendered as `unknown`; the **full recomposed commit list** with per-commit sign-off, re-sign and `Co-authored-by:` state; **the DCO signing identity as `user.name <user.email>`, never the forge login** — they routinely differ, and the forge login is not what the attestation carries; the local verification result, and whether it re-ran post-rebase; the rebase result and whether the base advanced; **branch-versus-target workflow drift** (C-813); **the PR's auto-merge / merge-queue state** (C-814); the **enumerated post-gate remote acts** with the pinned lease SHA; a `Never:` line; the acting identity **with its credential source**; and the backup ref with its SHA. A `no` performs no remote act, leaves the rewritten branch, **renames the backup ref inert** (C-809), and prints the restore command. | `hex-finalize/SKILL.md` § Gate; scoping in `protocol.md` § The meta-plan approval gate |
| **C-806** | **Handoff block.** The [handoff contract](../../hex/hex-core/references/protocol.md#handoff-contract) binds: a literal `## Finalize Complete: <branch>` block is the run's required final message on **every** outcome — halt, gate refusal, lease rejection, red check, local-only, success. It carries the terminal outcome; the commit list as it stands; the pushed SHA **or an explicit absent marker, never a blank field**; the remote-check result **on two independent lines, never one** — *what this run dispatched* (**green** / **red with the failing run named** / **no remote gate exists**, the last where the documented set was empty) and *what is running now* (**unwatched (running)** / **none**), because a run with no dispatchable gate can still have `on: pull_request` checks that the ready-flip itself triggered, and collapsing the two into one value forces an implementer to overwrite one truth with the other. An absent check is never rendered as a pass; the PR URL and draft/ready state; the backup ref under its terminal (inert) name; and `Next:` — the merge is the human's, so the line names it as such and emits no hex command. | `hex-finalize/SKILL.md` § Handoff |

### B. Recomposition and verification

| ID | Contract | Home |
|---|---|---|
| **C-807** | **Series shape, and the mechanism that produces it.** From *Rules Governing the Shape of a Final Commit Series Before Landing*, the **universals are shipped behavior and are not discoverable or overridable**: (a) a commit boundary is a **logical, independently-correct change**, never a size or file count; (b) **no fixup, WIP, or review-response commit survives**; (c) **message structure is enforced**, in whatever form the project's own convention names. The **two conflict axes resolve in three steps, in this order** (owner decision, 2026-08-29): **(1) the project's documented convention** — `CLAUDE.md` / `AGENTS.md` / `CONTRIBUTING.md`, the existing discovery of C-815, which **always wins**; **(2) a `hex.md › Preferences` prose hint**, written by `/hex-init` with consent (C-826) — **prose, not a config key**: `config.md`'s v1 vocabulary froze at six keys (C-223) and this decision does not reopen it, following the `adr_0004`/`adr_0005` precedent of carrying nuance as Preferences prose; **(3) the shipped default: a minimal bisectable series** — one commit per user-facing change, riders split out. The default's ground: squash-to-one is unrecoverable information loss performed on the human's behalf, while a series can still be squashed by the merge button — the reversible direction. **The resolving step is named at the gate**, so a reader always sees which of the three produced the shape. Riders **split into their own commits**; the `adr_0008` landing is the worked precedent, cited as a **mechanism, never a commit count**. **The mechanism is named, because it is the hardest step and because idempotence depends on it:** (1) `git rebase --onto <fetched-target-tip> <merge-base> <branch>` — conflicts halt here, and a clean result is C-803's structural check; (2) `git reset --soft <fetched-target-tip>` — the whole branch diff is now one staged tree; (3) build the series by staging each logical change's paths or hunks and committing it, with C-808 applied **per new commit**; (4) a **message-matches-diff sanity check** — a commit message may reference only paths and symbols present in that commit's own diff, and a mismatch is a halt, not a warning. **Step 2 is what makes re-running safe:** it discards the prior history and rebuilds from the diff, so a second run **never double-applies** a recomposition. It does not promise a byte-identical series — the partition into logical commits is judgment — and C-818 leans only on the weaker property, which is why no tip-shape guard is needed. **Declined: a mechanical absorb pre-pass.** `jj absorb` / `git absorb` fold fixup hunks into the commits that introduced them by blame, which would pre-shape the input — but step 2 discards the input history entirely, so the pre-pass would be work thrown away. Recorded as considered, not as unavailable. | `hex-finalize/SKILL.md` § Recompose |
| **C-808** | **Commit requirements are satisfied during the rewrite, never after it.** Discovered requirements (C-815) are applied **as each commit in C-807 step 3 is created**: `--signoff` where DCO is required, and **re-signing with the human's own configured signing method** (`user.signingkey`, `gpg.format`) where signed commits are required — a rebase invalidates every prior signature because a signature covers the parent hash. **finalize never provisions, chooses, or reads a signing key**; where signing is required and no key is configured, it says so at the gate rather than silently producing unsigned commits. **One consequence is load-bearing for re-entry and is stated here rather than discovered there: a signature stamps a fresh timestamp, so recomposition is *not* SHA-stable** — rebuilding an identical partition yields different commit ids. C-818 therefore resumes from an already-published rewrite instead of rebuilding it. **A second mechanical check, symmetric with C-807's message-matches-diff halt** (`archive.md` C-414: evidence is command output, not narration): **author-set equality** — the set of `%an <%ae>` over the backup ref's original series must equal the union of the recomposed commits' authors and their `Co-authored-by:` trailers. A mismatch means attribution was dropped or invented in the rewrite, and it **halts**; asserting preservation without the comparison is exactly the narration C-414 forbids. **Identity rules, both load-bearing:** the sign-off carries the invoking human's **git identity — `user.name <user.email>`, which the gate renders literally** and which is not the forge login; and **every distinct original author is preserved as a `Co-authored-by:` trailer** on the commit carrying their work, with the gate naming the other authors so the human sees whose work they are attesting to. **Trailer provenance** [erratum, review fix pass, 2026-08-30]: a recomposed commit message is *derived from the diff*, not carried over from the branch's original messages; the only trailers it carries are the ones finalize itself generates — `Signed-off-by:` from `--signoff` with the resolved signing identity, and `Co-authored-by:` reconstructed from the original series' author set. No trailer is ever copied from a branch commit message — an untrusted branch could otherwise smuggle a forged `Signed-off-by:` through recomposition into a signed, published series, since the message/diff check constrains only paths and symbols and the author-set equality halt covers only `Co-authored-by:`. Original messages may inform the summary line's wording, never the trailer block. | `hex-finalize/SKILL.md` § Recompose; disclosed at C-805 |
| **C-809** | **The backup ref — armed and inert, one rename, no deletes.** Before the first history-modifying operation, finalize creates **`backup/<branch>-pre-finalize`**, preserving the branch's `/` structure (`hex/foo` → `backup/hex/foo-pre-finalize`) so two branches can never collide on one ref. **Creation refuses to overwrite an existing armed ref** — that ref is an interrupted run's only anchor, and clobbering it would destroy the thing it exists for; the run re-enters instead (C-818). The armed name is the **sole predicate** C-821's rule line reads. **Every terminal outcome renames it inert** — success, gate decline, and any halt after the rewrite alike — to **`backup/<branch>-<pre-rewrite-short-sha>`**, a name no predicate reads and durable as the recovery anchor and the left-hand side of `git range-diff`. The SHA makes the name unique per pre-rewrite tip, which is what defeats the same-day collision a date suffix would have had — **but not the repeat case**: declining twice from the *same* tip would target a name that already exists. That is a no-op rather than a hazard (the existing ref already points at that exact commit), so the rename **succeeds silently when the target ref already resolves to the same SHA and otherwise refuses**, which is the same refuse-rather-than-clobber posture as arming. **The refusal is loud, never a silent non-release** [erratum, adversary round, 2026-08-29]: a foreign ref at the inert name (short-prefix collision or hand-created) gets an `Error:`/`Fix:` pair — inspect both refs, move the stray aside by hand, run the rename yourself — and the branch **stays locked until then**, correctly, since the armed ref still guards an unreconciled state; this is the one qualified exception to "every terminal outcome renames". **The arming refusal prints its own exit too** [erratum, review fix pass, 2026-08-30]: the draft said creation refuses to overwrite an armed ref and the run "re-enters instead" — but re-entry does not always clear it: an armed ref over a **clean** tree whose tip differs from the remote fails `published_rewrite` (C-818) and misses halt (3)'s armed-and-dirty predicate (C-804), so it routes to pre-flight, reaches Recompose, and refuses again with nothing printed. The refusal now carries an `Error:`/`Fix:` pair in the rename refusal's loud register — inspect the armed ref with `git range-diff`, then either `git reset --hard` the branch onto it and run the inert rename that releases the lock, or reconcile by hand. **Re-arming over an armed ref is forbidden**, not merely avoided — that overwrite destroys the only anchor an interrupted run left. **The rename is what releases the lock**, which is why a decline performs it: without that, a declined run would leave every hex mode halted on the branch with no documented exit but performing the push it just refused. finalize **never deletes** either name; pruning inert `backup/` refs after a merge is the human's, and the handoff says so once rather than growing a garbage-collection mechanism. | `hex-core/references/finalize.md` |
| **C-810** | **Verification is inherited, never invented.** "The strictest documented level" means the project's **own documented verification** ([`protocol.md` § Verification](../../hex/hex-core/references/protocol.md#verification)), at whatever level that documentation names as release-grade — hex neither defines test tiers nor decides which suite is expensive. **Ordering (the single canonical statement, which C-803, the gate and the state machine all render):** local verification runs **before** the rewrite; the rebase onto the freshly-fetched target must be **clean**; and **the local suite re-runs exactly once, after the rebase and before the gate, if and only if the fetched target tip differs from the base the pre-rewrite verification ran against**. A target that did not move leaves the earlier result valid; a target that moved makes it evidence about a tree that no longer exists, and a clean rebase proves textual compatibility, never semantic. Where no verification is documented, finalize detects one for this run and suggests `/hex-init` to persist it, exactly as every other hex phase does. | `protocol.md` § Verification (linked, not restated) |

### C. The remote surface

| ID | Contract | Home |
|---|---|---|
| **C-811** | **The remote act set — four kinds, three of them post-gate, all scoped by branch identity.** The four: **(1) fetch** the branch's upstream and the target ref, once, at pre-flight — a *read*, performed before the gate, which is why the gate renders three acts and not four; **(2) force-push** that branch (C-812); **(3) dispatch and read** the resolved workflows (C-813); **(4) create or mutate that one PR** — create when absent, edit title and body, flip draft→ready (C-814). **It never:** pushes the target branch or any other branch; merges anything; **writes or bypasses** branch protection or rulesets — it **reads** them, as authoritative-class discovery (C-815) [erratum, WP2 panel, 2026-08-29: the draft's "reads, writes or bypasses" forbade the very reads C-815 and the system design's § 8 command table mandate]; creates or edits tags, releases, or workflow files; touches another PR; provisions, mints or stores a credential; or writes a changelog file. **What the enumeration fixes is the mutations plus the one fetch** — the complete set of things finalize *changes* on a remote — and that set is **fixed in shipped text**; no discovered convention, config value, or file content adds to it (C-816). **Read-only forge queries are discovery, not acts**: identity and scopes, merge strategy, protection and rulesets, required checks, and the PR base field are bounded by their trust class rather than by this list, mutate nothing, and are disclosed at the gate with their source. **Degrade ladder — four rungs, and the rung is selected where the information exists, not all at pre-flight:** *full* (all six phases); *no remote gate* — **selected at the dispatch step, which is the first point that can know it** — where the resolved workflow set is empty, the run completes and the handoff says **no remote gate exists**; *partial rights* — an act refused by the forge degrades **that act alone**, reported, never silently skipped; *local-only* — selected at pre-flight (a) when no forge CLI is present or authenticated **while git's own transport still works**, running phases 1–5 including the gate, with each remote act named as manual. **The ladder degrades the forge half and never the base:** a failed *fetch* is not a fourth-rung condition but a pre-flight halt (C-804 c), because a rung with no fetched target could only rebase onto the local ref. | `hex-core/references/finalize.md` |
| **C-812** | **Force-push mechanics, in literal form.** The command is `git push --force-with-lease=<branch>:<pinned-sha> <remote> <local-sha>:refs/heads/<branch>` — an **explicit refspec naming one ref** and the lease **pinned to the SHA fetched at pre-flight**. **`--force-if-includes` is deliberately not issued** [erratum, WP2 panel, 2026-08-29]: git-push(1) states that the flag, "specified along with `--force-with-lease=<refname>:<expect>`, … is a `no-op`", so pairing it with the pinned lease this contract requires would buy nothing while reading as a second safety check. The integration property it was carrying moves **earlier**, to C-804(c)'s `git merge-base --is-ancestor <pinned-sha> <branch>` assertion — tested while ancestry still exists, and failing as halt (6) **before** the rewrite rather than after it. Never bare `--force`, never the unpinned lease form, and **never `--all`, `--mirror`, or `--tags`**, each of which would push refs outside the act set. **Every rejection is a hard stop** — there is no success case for a rejected push, and the draft's "a rejection because the remote already matches is success" carve-out is **removed**: re-entry routes on an `ls-remote` comparison (C-818), so a run that reaches the push has already established that the tips differ. **One cause remains at the push itself** [erratum, WP2 panel, 2026-08-29]: **the remote SHA no longer equals the pinned SHA** — someone pushed between pre-flight and this push. Both SHAs and the backup ref are reported and the human reconciles by hand before re-invoking; there is no re-fetch and no retry. The second diagnostic this contract used to carry — integration cannot be proven — is now **C-804 halt (6)(ii)**, where it is detected before anything is rewritten. **The placeholder-quoting rule is file-wide, stated once in `finalize.md` § Scope** [erratum, review fix pass, 2026-08-30]: stated inside force-push mechanics it read as a property of the push command alone, while the reference and `hex-finalize/SKILL.md` carry a dozen further literal forms substituting the same placeholders (the `backup/` rename and `range-diff`, C-809; the rebase and `reset --soft` forms, C-807; the `reset --hard` and `git add` inside halt Fix: lines, C-804; every `gh`/`glab` row, C-813). Promoted to § Scope as one rule governing every literal command form in both files; this row keeps a one-line pointer, the skill restates nothing (C-819). C-804's halt (1) drops its `git switch <feature-branch>` Fix: line in the same pass — the run cannot know which branch the user meant, so the placeholder was never fillable; the Fix: is now prose. | `hex-core/references/finalize.md` |
| **C-813** | **Remote verification — a discovery contract, a trust class, and a spend ceiling that survives re-invocation.** **Which workflows:** the set is **authoritative-class only** — the workflows the project's own context or `hex.md › Pointers` **documents** as release-grade (C-810), intersected with what the forge reports as dispatchable. **finalize never scans the branch for dispatchable workflows and runs what it finds**: that would let a branch introduce a workflow and have finalize execute it. An undocumented workflow is never dispatched, no matter how dispatchable it is. **What dispatch actually does, stated plainly:** a dispatch executes the workflow **as defined on the branch ref** — only its *presence* on the default branch is required for dispatchability — so dispatching runs code from the artifact under change. Two controls follow. **(i) Drift is disclosed:** where the branch modifies any file under the workflow directory, the gate names the changed files and states that the dispatch will execute the branch's version. **(ii) The forge's own control is named, not silently dropped:** the human-approval-for-triggered-workflow-runs setting is the backstop that holds server-side, and the shipped text says so rather than implying hex's enumeration substitutes for it. **Inputs:** finalize passes **no workflow inputs** unless the project's documented convention names them; no input value is ever sourced from checked-in text, a PR field, a commit message, or any other narrowing- or untrusted-class string. **Orchestration is forge-conditional, because the two forges do not have the same unit.** On **GitHub**, dispatch **once per documented workflow file**, against the pushed final SHA, taking the run ID from the dispatch response. On **GitLab** there is no per-workflow dispatch to have: a ref has **one** pipeline configuration, and triggering it runs that pipeline — so finalize issues **one pipeline trigger per SHA**, and the documented set maps to **jobs or stages inside that pipeline**, verified against the pipeline's own status rather than against N separate runs. A documented entry with no matching job in the resolved pipeline is reported as **not present**, never as passed. This is a **mapping, not a degrade** — GitLab satisfies the same contract with one trigger — but it is named as a forge condition so an implementer does not attempt N triggers and conclude the CLI is broken. Read results through the CLI's watch or status facility **wrapped in a bounded retry**: the bound comes from the **calling harness's tool-execution limit**, not from any documented CLI timeout, so a single long-running call can be cut off with the run still healthy and must not be read as a failure. **Ceilings that survive re-invocation:** the re-dispatch guard suppresses a dispatch when a run exists for that SHA in **any** state — queued, running, **or completed, including completed-red** — and the flake-rerun ceiling is **exactly one rerun, of the failed jobs only**, counted **per SHA from the run's own rerun count** rather than per invocation, so re-invoking cannot reset the budget. Past the ceiling the run stops, the PR stays in draft, and the failing run and URL are named. **"No `workflow_dispatch` workflow" is not "no CI":** the common `on: pull_request` pattern is suppressed while a PR is draft and first fires **because of** the ready-flip. C-814 states how that is handled. **The re-dispatch guard counts finalize's own `workflow_dispatch` runs, not any run on the SHA** [erratum, review fix pass, 2026-08-30]: the draft's ceiling clause said "a run exists for that SHA in **any** state" and named no owner, contradicting C-818's scoping of the same query — ordinary `on: push`/`on: pull_request` CI is never evidence finalize dispatched anything — and would let unrelated automation suppress the one remote-verification step this design owns. The guard is scoped here to match C-818, the any-state breadth (queued, running, completed-red) unchanged; C-806's ledger follows, so a foreign run never appears in the handoff as verification evidence. | `hex-core/references/finalize.md` |
| **C-814** | **PR surface, the quality ledger, and the flip.** finalize creates the PR when none exists (title and body derived from the recomposed series) and otherwise edits only its own content. The quality ledger — verification level and result, dispatched runs and outcomes, the `git range-diff` against the backup ref, and the resolved conventions with their sources — is written into a **marker-fenced block**, `<!-- hex:finalize:start --> … <!-- hex:finalize:end -->`, reusing `hex-init`'s marker convention. **Only the block is replaced; the rest of a human-authored body is never touched.** **The flip is the last act and carries two guards.** *First,* **auto-merge and merge-queue state is read and disclosed at the gate**: where the PR has auto-merge armed or sits in a merge queue, flipping it to ready can be the last domino of an actual merge, which would violate "merging stays human" in effect while honoring it in letter. That state **narrows** the run — with auto-merge armed, finalize **does not flip**; it reports the PR as ready-but-held and names the setting. *Second,* **flip-triggered checks are watched, not assumed**: after a flip, finalize watches whatever checks appear on the PR under the same bounded watch and ceiling, and the handoff reports them as green, red-with-run-named, or **unwatched (still running)**. finalize does **not** un-flip on a red post-flip check — un-flipping is not in the act set — it reports it prominently. | `hex-finalize/SKILL.md` § Remote |

### D. Convention discovery

| ID | Contract | Home |
|---|---|---|
| **C-815** | **Discovery surfaces, three trust classes, and an enumerated narrowing scope.** **Authoritative** (changing it requires a privileged mutation): forge merge-strategy fields, rulesets / rules-for-branch, required-check lists, **the PR's base field**, the project's own context and `hex.md › Pointers`, and — for the two series-shape axes only — the **`hex.md › Preferences` prose hint** of C-807, which is user-owned and written solely by `/hex-init` with consent, and which sits **below** the project's documented convention and **above** the shipped default. **Narrowing-only** (arrives as branch content, so any contributor writes it): `CONTRIBUTING.md`, commitlint-family configs, PR and issue templates. **Untrusted** (arbitrary text): PR title and body, commit messages, issue text, CI logs. **The narrowing class reaches an enumerated set of conventions and nothing else** — the two series-shape axes, the message format, and the sign-off and signing requirements. **The target branch, the merge strategy, the workflow list and the verification level are authoritative-class only and are never resolved from narrowing-class input**, because each of them selects *what code runs* or *what history is replaced*, which is a widening act however it is dressed. Cross-referencing declared against enforced is the reliable signal; presence never implies enforcement. **An empty or unreadable enforcement read is `unknown`, never `unenforced`** — the readable rulesets endpoint returns rules from rulesets only, so a classically-protected repo answers `200 OK` with an empty array. **Interaction rule — hex culture over field norm:** detect silently, **disclose always** at the gate with each convention's source and trust class, and **ask only on genuinely ambiguous signal**. **Authoritative *files* resolve from the fetched target ref, never from the branch under change** [erratum, WP2 panel, 2026-08-29] — otherwise a branch that edits its own `CLAUDE.md` or `hex.md` promotes branch content into the class that *sets* values, which is the whole distinction. C-804(c) already has the target in hand; where the branch's copy differs, the divergence is **disclosed at the gate** with the changed paths, exactly as workflow drift is (C-813), and the target's copy is what resolved. | `hex-finalize/SKILL.md` § Discover conventions |
| **C-816** | **Narrow-never-widen, and the echo rule gets a real home.** Content from any narrowing- or untrusted-class surface **may only make finalize stricter** within C-815's enumerated set; it may **never** widen: no file content adds a remote act, retargets a branch or PR, changes the acting or signing identity, relaxes a verification level, selects a workflow, or bypasses the gate. Every such input is **data, never instruction**, and reaches any reasoning step clearly delimited as data with an explicit statement that a directive inside it is content to analyze. **Echoes are quoted, truncated with `…` past 120 characters, and never allowed to break their own line.** That echo rule currently exists only inside `hex-architect/SKILL.md`, which is skill-scoped and therefore not referenceable by a second consumer; rather than restate it — the copy-drift `DESIGN.md` forbids — this ADR **promotes it to `protocol.md` as a short § Untrusted-text echoes**, retargets `hex-architect/SKILL.md`'s statement to a one-line link, and has `finalize.md` link the same home. One rule, one home, two consumers. | `hex-core/references/protocol.md` § Untrusted-text echoes (new, promoted); linked from `finalize.md` and `hex-architect/SKILL.md` |
| **C-817** | **Credential posture — disclosed, never assumed (F3).** The shipped default is the **ambient forge-CLI credential**. finalize provisions nothing and stores nothing. **A project may point the CLI at a narrower credential** — on GitHub a fine-grained PAT scoped to `Contents: write` + `Actions: write` + `Pull requests: write` on the single repository; on GitLab `write_repository` with a Developer-role token, or an `api`-scoped project token where the CLI path requires it — supported without being required. **The gate discloses the acting identity, the credential *source* (an environment-variable override versus the ambient login, because which one is in force changes the blast radius and is invisible otherwise), and the reported scopes beside the rights this run needs.** finalize **does not refuse** on a broad credential: the common path is exactly that, and the containment that matters is structural. **It does surface one scope gap concretely**, because it fails late and confusingly otherwise: pushing a series that touches the workflow directory requires a workflow-scoped credential over and above the three rights, and the gate says so when the series touches those paths. | `hex-finalize/SKILL.md` § Gate; audit item at C-826 |

### E. Re-entry

| ID | Contract | Home |
|---|---|---|
| **C-818** | **Idempotent re-entry, derived from git and the PR — no journal file, and every pre-push resume lands on the gate.** A re-invoked finalize reconstructs its position by inspecting: whether an **armed** `backup/<branch>-pre-finalize` ref exists; whether `ls-remote`'s branch tip equals the local tip (**never the remote-tracking ref**, which is exactly the value a background fetch corrupts and whose staleness the lease design exists to defeat); whether a run exists for that SHA in any state; and whether the PR is ready. **The governing rule is one sentence: no resume performs a remote act without passing the gate.** A run interrupted or declined before the push re-enters at pre-flight and runs forward **to the gate again** — it never resumes directly at the push, which in the draft would have turned a declined gate into an approved force-push on the next invocation. That is safe to do because **recomposition never double-applies**: C-807 step 2's `reset --soft` discards the prior history and rebuilds from the diff, so a second run cannot stack a recomposition on a recomposition. **The guarantee is that and no more** — the *partition* into logical commits is model judgment, so a re-run may draw boundaries slightly differently; what is invariant is the branch diff and the base, not the exact series. That is sufficient precisely because every re-run passes the gate again, which re-displays whatever series it produced before anything is published. The draft's promised **tip-shape guard stays dropped**: it was there to catch a double-apply `reset --soft` already makes impossible, and it could never have caught a differing partition — the re-gate is what covers that. **One piece of state is session-local, deliberately:** whether the gate already passed for the current pushed SHA. It is not a journal — losing it **fails toward the gate**, so a fresh session with a pushed-but-undispatched branch re-asks rather than dispatching on consent it cannot see. **Once a rewrite is published, re-entry resumes from it and never rebuilds it.** The chain's **first** test — evaluated before any decision to recompose — is `published_rewrite`: **an *armed* backup ref exists** for this branch **and** the remote tip equals the local tip. **Armed, never merely present:** the armed name survives only while a run is unfinished (every terminal path renames it inert, C-809), so it means precisely "this run pushed and has steps pending". An *inert* ref plus equal tips is a different situation entirely — a prior finalize that already terminated, on a branch that has since gained human commits **and had them pushed** — and that must be **rebuilt**, not resumed, or the new work would be dispatched and flipped without ever being recomposed. That path skips the rewrite and the push outright and resumes at whichever remote step is still pending, passing the gate first if this session has not, **with a reduced act set that names no rewrite and no force-push**. This is routing, not a comparison, and it has to be: **C-808's mandatory re-signing stamps a fresh timestamp, so recomposition is not SHA-stable** — a rebuild of an identical partition mints different SHAs, which means the tips would already have diverged before any "push is a no-op when they match" check could fire. That check is therefore **removed from this contract as unreachable**; without the routing fix, a fresh session resuming a pushed-but-undispatched branch would force-push a second time, dispatch a second time, and leave a second signed attestation for work already published. **Every state that is not `published_rewrite` routes to pre-flight** [erratum, WP2 panel, 2026-08-29] — armed or not, tips equal or not, a run present or not. The draft's chain fell through to `WATCH` / `FLIP` / `POST` on *not armed + tips equal + a run exists*, which reached a post-push step **with no gate at all**, on work that had never been recomposed; the run state is now consulted **only inside `RESUME_PUBLISHED`**. `FLIP` and `WATCH` are therefore reachable exactly two ways: forward from a gate this session passed, or through `RESUME_PUBLISHED`, whose own precondition is the armed ref this run created and which still gates first. **The run query is scoped to finalize's own dispatch** — a `workflow_dispatch` run this design created against that head SHA, never any run that happens to exist on the SHA — so a branch's ordinary `on: push` CI cannot stand in for the step this design owns, and no journal file is needed to tell them apart. After the push, the remaining steps are guarded individually: the **dispatch** is suppressed by the any-state run guard (C-813); the **flip** is a forge-side no-op when already ready. **No new state file is created**, on any path. **The gate-already-passed flag is keyed on the pair (branch, pushed SHA)** [erratum, review fix pass, 2026-08-30]: the draft called it "session-local" and said no more, leaving one session finalizing two branches — or one branch pushed twice — able to read a prior yes as consent for a series the human never saw. The key is stated at the definition site: a second branch never inherits the first one's approval, and a new push re-keys the flag. Losing the flag still **fails toward the gate**; keying it only removes the case where *keeping* it failed away from one. | `hex-core/references/finalize.md` |

### F. Contract amendments in the bundle

| ID | Contract | Home |
|---|---|---|
| **C-819** | **One new hex-core reference file — the sole definition site.** `hex/hex-core/references/finalize.md` is the single home for: the remote act set and its branch-identity scope (C-811); the consent model and the class/instance narrowing (C-805); force-push mechanics in literal form (C-812); the backup-ref armed/inert lifecycle (C-809); remote-verification discovery, trust class and ceilings (C-813); re-entry derivation (C-818); the degrade ladder; and **the scoping sentence every qualifier site links to**. It follows `archive.md`'s precedent: one owned definition, linked from everywhere, restated nowhere. `hex-finalize/SKILL.md` carries the *flow* and links here for every *rule*. | new `hex/hex-core/references/finalize.md` |
| **C-820** | **The never-push amendment is scoped, additive, and lands at four sites.** The corrected site table is below; it replaces the draft's prose counts, which conflated files with line-sites and wrongly included `archive.md:356` (a never-**commits** statement about `hex-review`, not a never-pushes claim). **Four sites make a bundle-wide claim and take a one-clause qualifier**; every other restatement is skill-, worker-, or federation-scoped, **remains true verbatim, and is deliberately not touched** — a qualifier on any of them would be false. The qualifier is one clause with one link, identical at every site: *"…except `/hex-finalize`'s force-push of the one feature branch it was invoked on, consented by that invocation and approved at its gate — see [`finalize.md`](finalize.md)."* `protocol.md:850`'s is the fetch variant: *"…except `/hex-finalize`'s single pre-flight fetch of the branch it finalizes and its target, which pins the force-push lease and never informs a landing claim."* | `hex-core/references/finalize.md` owns the definition; the four sites below |
| **C-821** | **`hex-state.md` gains one mode line, and C-718's cap is amended in the open.** The mode line's predicate is a git ref: *an **armed** `backup/<branch>-pre-finalize` ref for the checked-out branch means a finalize is in flight or was interrupted → do not commit onto, rewrite, or merge that branch; re-read `finalize.md` and re-enter `/hex-finalize`, or release it by renaming the ref (`finalize.md` gives the one command)*. The **release clause is mandatory**, matching `adr_0008`'s own precedent that a predicate justified by being correctable must say how it is corrected — and a normal decline performs the release itself (C-809). Absence of the armed ref means nothing to check. **No second rule artifact.** **The cap:** C-718 says "≤10 lines" with no measure qualifier and the shipped body is **exactly 10 physical lines**; a second mode line written like its sibling is about three. Redefining the measure as "non-blank" to fit would be a silent reinterpretation of the very contract that demands the cap be re-examined rather than exceeded. **This ADR therefore amends C-718's cap explicitly: ≤14 physical lines, measured H1 onward**, on the stated ground that the cap's purpose is bounding always-on instruction budget and that two modes at ~3 lines plus the 4-line generic frame is 14 with nothing to spare. **The next mode's ADR must compress or amend again** — and, per the round-9 erratum, must budget the description-line surface alongside (C-801). | `hex/hex-state.md`; the cap amendment recorded here and in DESIGN round 10 |
| **C-822** | **Finalize is a post-terminal actor — no new lifecycle state.** By construction finalize runs *after* Approve wrote the plan's terminal state and after Upkeep cleared the active-plan pointer and wrote the artifact-index row (`archive.md` C-410). It therefore **does not touch `State:`**, the pointer, or the index. Its quality-status mirror is **one line appended to the existing terminal Status block** — the writer role the shipped plan template already names ("whoever commits and finalizes the work"). **A post-archive append is permitted and is not a second archive event:** no second pointer clear, no second index row. `archive.md`'s "not moved and not renamed" clause is unchanged; this ADR adds the one sentence it never said. | `archive.md` § Plan archive (one added sentence) |
| **C-823** | **`/hex-review` emits `Next: /hex-finalize` on a clean Approve — a handoff line, not a contract change.** `hex-review`'s `### Next step` reads `(none — approved)` on a clean verdict; it becomes `/hex-finalize` when the verdict is `Approve` **and** the target is a branch or PR (never a plan-artifact-only or working-tree review). hex-review still never edits the code or diff under review, still never commits, and performs **no forge read** to produce this line — finalize's own pre-flight resolves PR state. Making review re-derive forge state it otherwise never reads would be a real contract change; emitting one line is not. | `hex-review/SKILL.md` § Handoff |

#### C-820's site table

| File · line | Statement | Class | Qualify? | Ground |
|---|---|---|---|---|
| `DESIGN.md:174` | "feature branch → trunk is the human's PR. hex never pushes." | bundle-wide | **yes** | The live Worktrees decision text |
| `protocol.md:544` | "landing it on the trunk is the human's step … hex never pushes." | bundle-wide | **yes** | § Worktree mechanics, the sentence the tier files restate |
| `protocol.md:850` | "hex never fetches and never infers landing from anything weaker" | bundle-wide (fetch) | **yes** (fetch variant) | finalize fetches once, at pre-flight, to pin the lease |
| `archive.md:474` | "hex-review never commits and hex never pushes" | bundle-wide | **yes** | § Revert's opening premise |
| `DESIGN.md:482, :560, :577, :661` | round-7/8/9 restatements | historical round text | **no** | Rounds are never rewritten; round 10 supersedes them (`adr_0008` precedent) |
| `archive.md:356` | "Since hex-review never commits, revert-by-discard is…" | never-**commits**, about hex-review | **no** | Not a never-push site at all — the draft's error, corrected |
| `protocol.md:540` | "never force-push, never rebase a published ephemeral branch" | hex-execute's WP branches | **no** | Still absolute; finalize touches no ephemeral WP branch |
| `protocol.md:637` | "hex never fetches" (satellite worktree creation) | federation-scoped | **no** | finalize is single-repo v1 and halts in satellites (C-824) — see the note below on why this and `:850` split |
| `workers.md:39` | "Never auto-commit… the human decides when to commit and push" | binds **workers** | **no** | finalize is orchestrator-level; `hex-execute` already commits there |
| `workers/builder.md:29` | "never commit" | worker-scoped | **no** | Unchanged |
| `hex-plan/SKILL.md:303` | "Never commit and never push — this skill plans only." | skill-scoped | **no** | True verbatim |
| `hex-architect/SKILL.md:458` | "Never commit and never push — this skill designs only." | skill-scoped | **no** | True verbatim |
| `hex-review/SKILL.md` frontmatter, `:421`, `:433` | "never edits… and never commits" | skill-scoped | **no** | True verbatim |
| `hex-execute/SKILL.md:495`, **`:570`** | "never push", "**Never push to remote.**" | skill-scoped | **no** | hex-execute gains no push capability — `:570` must not be touched |
| `hex-execute/SKILL.md:615` | "hex never pushes and records no landing it did not observe locally" | federation upkeep | **no** | finalize observes no landing and claims none |
| `hex-execute/tier-{low,medium,high}.md` | "Never push — …" | hex-execute's own, ×3 | **no** | A **pre-existing** restatement of `protocol.md:544`; recorded, not fixed here — their meaning did not change |
| `hex-init/references/audit.md:171` | "never fetched — nothing here reaches the network" | hex-init-scoped | **no** | Stays true by C-826: the audit item makes **no forge reads** |

**Why `:637` and `:850` land in different columns although both sit in
federation mechanics.** They are not the same claim. `:637` is a statement
about *satellite worktree creation* — it promises that hex will not reach the
network **in a repo the session did not start in**, which finalize cannot
violate because it halts in satellites before it fetches anything (C-824).
`:850` is a statement about *the repo the run is in* — "hex never fetches and
never infers landing from anything weaker" — and finalize does fetch there, so
the sentence would be false without the qualifier. The distinguishing test is
therefore **which repo the claim is about**, not which section it lives in:
finalize fetches in exactly one repo, its own, and `:850` is the only
federation sentence that speaks about that one.

### G. Scope boundaries

| ID | Contract | Home |
|---|---|---|
| **C-824** | **Federation — single-repo v1, `/hex-finalize` joins the satellite halt, and the residual hole is stated.** Federated finalize is **explicitly deferred**, mirroring `adr_0004`'s own posture: a plan at `landing` works exactly as shipped, with the human sequencing the per-repo merges. The deferral must not leave a hole, and here it would: `memory.md`'s satellite-halt scope says a non-orchestrator "resolves no plan and writes no plan or federation state" and therefore sits **outside** the halt — true of `hex-discuss`, **false of finalize**, which rewrites and force-pushes a branch that may be a row in a lead's `Repos:` ledger. So `/hex-finalize` is **brought inside the halt's scope** — the first non-orchestrator to be — with its own stated ground. **It also needs its own `Fix:` variant**, because the halt's single-definition text tells the reader to re-run from the lead, and re-running `/hex-finalize` from the lead finalizes *the lead's* branch, not the satellite's — a wrong-repo action the existing text would actively steer someone into. finalize's variant says instead: **a satellite's feature branch is finalized by hand until federated finalize exists**, and names the recomposition and push as the human's. **Two residual limits, stated rather than implied:** the halt keys on a `Federation lead:` bullet, which a **virgin satellite does not carry** and which the documented escape hatch permits deleting, so the halt is a heuristic, not a guarantee; and `adr_0004`'s C-323 structural invariant reads the *plan*, which is already terminal and pointer-cleared by the time finalize runs, so it is unavailable here. `adr_0004`'s FM6 hazard (distinct from this ADR's system-design failure-mode numbering) is therefore **narrowed, not closed**, for a satellite finalize — which is a further reason the deferral is the right scope. | `memory.md` § Location and resolution › Federation satellites (scope amendment + finalize's `Fix:` variant) |
| **C-825** | **Zero config *key*.** `config.md` is **not touched**: no new key, and the `tiers`/`workflows` `<skill>` enumeration stays closed to the four orchestrators — finalize is not tiered, exactly as `hex-discuss` is not, and README's exemption sentence gains it as a third name. Everything finalize would want to configure — commit conventions, DCO and signing requirements, which suites are release-grade, which workflows, which forge — is a **Layer-1 project-context fact** discovered by `/hex-init` (C-826). A future explicit override would be a v2-style **new top-level key** with its own row and freeze note, never a repurposing of `tiers`. **The one thing that does land in `hex.md` is C-807's series-shape hint, and it is deliberately not a key:** it is `## Preferences` **prose**, written by `/hex-init` with consent, the same carrier `adr_0004` and `adr_0005` used for nuance the frozen vocabulary cannot express. Prose costs no vocabulary and needs no freeze note; a key would have reopened C-223's closed v1 set for a single default. | (no edit — a stated non-change) |

### H. Provisioning, wiring, and stated non-goals

| ID | Contract | Home |
|---|---|---|
| **C-826** | **`hex-init` gains one audit item and two Pointers rows — and makes no forge reads.** A new top-level item, **"Commit and landing requirements documented?"**, in the standard four-part shape. *Look for:* whether the project requires DCO sign-off, signed commits, or a commit-message convention; which suites count as release-grade; and **which workflows are the release gate**. *Where:* **project context and checked-in files only.** *Documented looks like:* a named requirement with its enforcement point — "commits must carry `Signed-off-by`, enforced by the `dco` check" — not "we use conventional commits, probably". *De-facto discovery:* commitlint-family configs, `CONTRIBUTING.md`, and the last ~20 non-merge commits' own dialect; a found requirement is proposed for **adoption via pointer**, never invented. **Where discovery finds the two series-shape axes undocumented, the item offers to record the team's preference as `hex.md › Preferences` prose** (C-807 step 2), with consent and with the shipped default named as what happens otherwise — the first time hex asks about series shape rather than inferring it, and the only reason step 2 exists. **The item performs no network read** — `audit.md:171`'s "nothing here reaches the network" stays true verbatim, and every forge read in this design lives inside `/hex-finalize`, behind its gate, where it is disclosed. Two `hex.md › Pointers` rows follow the Spec-home pattern: the **forge and its CLI**, and the **target/trunk branch** where it is not the obvious default. **The item also recommends the control that actually holds:** target-branch protection with "restrict force pushes" and a required pull request — a server-side backstop that binds regardless of what any agent's prompt says, which hex's own enumeration cannot claim to be. | `hex-init/references/audit.md`; `hex-init/SKILL.md` Step 1/2 |
| **C-827** | **Bundle wiring and release — all seven touch points, none optional.** (a) `hex/hex.toml` `[skills]` gains `"hex-finalize" = "./hex-finalize:latest"`; (b) `hex/publish.toml` gains `[skills."hex-finalize"] path = "hex-finalize"` and bumps `version` to **`0.3.0`** — a minor bump: one new member, one new capability, no breaking change, no `deprecated`, no `replaced-by`; (c) `hex/CHANGELOG.md` gains an `## [0.3.0]` section with `### Added` bullets and a `### Notes` line recording C-828's declined spawn; (d) `hex/README.md` gains a Members row, a Quickstart line after `/hex-review`, a sentence in the intro flow, **`/hex-finalize` added to the tier-grammar exemption sentence**, and one line stating plainly that finalize is the one hex command that writes to a remote; (e) `hex/DESIGN.md` gains **round 10**; (f) the `hex-core` amendments of C-816/C-819/C-820/C-822/C-824; (g) the project's own `CLAUDE.md` "Commands:" line **and** `hex-init/references/audit.md`'s discovery-note block, both of which enumerate all commands. The repo-root `grimoire.toml` gains `hex-finalize = "./hex/hex-finalize"`, keeping its member set matching `hex.toml`'s. | `hex/hex.toml`; `hex/publish.toml`; `hex/CHANGELOG.md`; `hex/README.md`; `grimoire.toml` |
| **C-828** | **No worker spawns, no new role — a stated non-goal with a revisit trigger.** finalize spawns **nothing**. Commit-boundary judgment needs the whole branch diff in one place and returns a decision, not a report. Consequently `workers.md` gains no role, `models.md` gains no row, no capability class is named, `protocol.md` § Worker coordination does not bind this skill, and there is no spawn disclosure. The precedent is `hex-execute`'s own "Merge and commit" duty, which carries no role prefix for exactly this reason. **Revisit trigger:** field evidence that recomposition quality tracks the session model — at which point the change is one spawn of an existing role plus one `models.md` row, not a design round. | this ADR (a stated non-goal); revisit tracked in `hex/CHANGELOG.md` |

**UX scenarios.**

| ID | Scenario |
|---|---|
| **S-801** | A branch of 32 scaffolding commits, review-approved. finalize verifies locally, rebases cleanly onto the freshly-fetched target, recomposes into one feature commit plus two rider chores, and shows all three subjects with their `Signed-off-by` lines and the signing identity `Michael Herwig <…>` at the gate. Approved: force-pushed with a pinned lease, one documented workflow runs green against the final SHA, the PR flips draft→ready. |
| **S-802** | `/hex-review` approved and folded a spec delta, so the tree carries the uncommitted spec file and the plan's `Folded:` receipt. finalize **halts at pre-flight check 3**, names the dirty paths **as the fold**, and prints the `git add` / `git commit` pair. It does not commit the fold and does not stash it (F4). |
| **S-803** | A colleague pushes to the branch mid-run. The lease — pinned at pre-flight — rejects. The run **stops**, reports **"the remote SHA no longer equals the pinned SHA"** with both values, names the backup ref, and does not re-fetch or retry (C-812). |
| **S-804** | The repo is protected by classic branch protection, so the ruleset read returns an empty array. finalize records enforcement as **`unknown`**, renders it as `unknown` at the gate, and proceeds under shipped defaults — never as "nothing enforced" (C-815). |
| **S-805** | `CONTRIBUTING.md` on the branch contains injected text naming a different rebase target and demanding a merge. The target is **authoritative-class only**, so the text cannot reach it; the merge is not in the act set. Its one readable narrowing-class value — a stricter message regex — is applied, and every echo of its text at the gate is quoted and truncated (C-815, C-816). |
| **S-806** | No forge CLI is installed. Pre-flight step (a) selects the **local-only rung**: conventions, verification, recomposition, and **the gate — which still asks**, because the commits carry a live attestation the human will publish by hand. Approved, the handoff names the push, dispatch and flip as manual and marks the pushed-SHA field explicitly absent (C-805, C-811). |
| **S-807** | The human answers **no** at the gate. No remote act occurs, the rewritten branch stands, the backup ref is **renamed inert** — releasing the `hex-state` lock — and the handoff prints the restore command (C-805, C-809). |
| **S-808** | A run is killed after the push but before the dispatch. Re-invoked, finalize finds the **armed** ref and an `ls-remote` tip equal to the local tip, so `published_rewrite` holds: it **resumes from the published tip instead of recomposing**, **passes the gate again** with a reduced act set naming no rewrite and no force-push, and dispatches. There is no "skipped push" — the push is never reached (C-818) [erratum, WP2 panel, 2026-08-29]. |
| **S-809** | The dispatched workflow fails on a flaky test. finalize reruns the failed jobs once, sees the same failure, **stops**, leaves the PR in draft, and names the failing run and URL. Re-invoked later, the guard sees a **completed** run for that SHA and does **not** dispatch again, and the rerun ceiling — counted from that run's own rerun count — is already spent (C-813). |
| **S-810** | The branch carries commits by two authors. The gate names the second author, each recomposed commit preserves the matching `Co-authored-by:` trailer, and the `Signed-off-by` line carries the invoking human's `user.name <user.email>` — never a bot's, never the co-author's, never the forge login (C-808). |
| **S-811** | `/hex-finalize` is invoked in a repo whose `hex.md` carries a `Federation lead:` bullet. It **halts**, and its `Fix:` says the satellite's branch is finalized **by hand** — not "re-run from the lead", which would finalize the lead's own branch (C-824). |
| **S-812** | The PR body was written by a human. finalize replaces **only** the content between its `<!-- hex:finalize:… -->` markers, creating the block once if absent, leaving every other line byte-identical across two successive runs (C-814). |
| **S-813** | The PR has auto-merge armed. The gate **discloses it**, and finalize **does not flip** draft→ready — flipping would make the ready-state the last domino of a real merge. The handoff reports the PR as ready-but-held and names the setting, so "merging stays human" holds in effect and not only in letter (C-814). |

## Non-Functional Requirements

Only affected axes; silence means not affected.

| Axis | Impact of this decision |
|---|---|
| Scalability | Not affected. finalize spawns nothing (C-828) — no fan-out, no concurrency cap, no new recursion level. |
| Availability | The remote half depends on a third-party forge, a first for hex. Bounded by construction: the watch is wrapped in a bounded retry rather than trusted to return, ceilings are per-SHA and survive re-invocation, and every remote failure degrades to a reported manual step rather than a hang. The local half has no external dependency. |
| Latency | The run is long by nature — remote CI dominates and hex neither controls nor estimates it. The one latency commitment is **positional**: the gate sits before the wait, so the human's attention is spent once, up front. The post-rebase re-verification (C-810) is conditional precisely so the common case does not pay it twice. |
| Security | **Four boundaries.** (i) **The act set is enumerated, fixed in shipped text, and scoped by branch identity** (C-811). **Its honest status is stated: this is prompt text, and prompt text constrains a cooperative agent, not a compromised one.** The controls that hold server-side are outside hex — target-branch protection with "restrict force pushes" and a required PR, and the harness's own command allowlist — and C-826 makes recommending the first an audit item. Copilot's branch-prefix precedent is cited for its *shape*, not as a parity claim. (ii) **Convention inputs carry three trust classes** (C-815), and the narrowing class reaches an **enumerated** set that excludes the target branch, the merge strategy, the workflow list and the verification level — each of which selects what code runs or what history is replaced. (iii) **A dispatch executes branch-defined code.** The workflow set is authoritative-class, never scanned from the branch; branch-versus-target workflow drift is named at the gate; inputs are never sourced from narrowing- or untrusted-class strings; and the forge's own human-approval control for triggered runs is named as the real backstop (C-813). (iv) **The attestation boundary runs outward**: a `Signed-off-by` is a first-person certification and a signature is made with the human's own key, so the exact commit list with its sign-offs and the literal signing identity is disclosed at the gate immediately before publication (C-805, C-808). Residual risks named rather than mitigated away: the signing oracle's session-long availability, and C-824's narrowed-not-closed FM6 hole for a satellite. |
| Cost | **CI minutes are the real spend, bounded three ways**: the expensive suites are dispatched **once**, against the final SHA only; the re-dispatch guard suppresses on a run in **any** state including completed-red, so re-invoking cannot re-spend; **and a resume never rebuilds an already-published rewrite** (C-818) — without that routing, re-signing's fresh timestamps would mint new SHAs on every resume, and each one would look like new work to the guard, spending a fresh dispatch per re-invocation; and the flake-rerun ceiling is **exactly one rerun, of the failed jobs only**, counted **per SHA from the run's own rerun count** rather than per invocation, well under the forge's 50-per-run shared limit. **Token cost is near zero**: no spawns, no fan-out, no research phase. The always-on cost is one rule line and one member description (C-801, C-821). |
| Compatibility | **Vacuous when uninvoked.** No new config key, no new lifecycle state, no change to any orchestrator's flow. What a non-invoking session carries: the amended rule body, one more member description, four amended sentences, and one promoted `protocol.md` section (C-816). Nothing is byte-identical; nothing behaves differently. **Federation** is deferred, not broken (C-824). **`config.md` is untouched** (C-825). |
| Operability | One new command, one new reference file, one new audit item, one new rule line, one promoted protocol section. **No new state file**: re-entry derives from git and the PR (C-818). The genuinely new operational object is the **backup ref's armed/inert lifecycle** (C-809) — one name means in-flight and locks the branch, the other means finished-and-recoverable — and it is the one thing an operator must learn, which is why the rule line reads exactly one of those names and why every terminal path performs the rename. |

## Constitution deviations

`hex/DESIGN.md` is binding. This decision adds **one dated round with two
amendments**, declares **one `protocol.md` deviation**, makes **one `memory.md`
scope amendment**, and **amends one `adr_0008` contract (C-718's cap)**.
Following `adr_0005`'s deferred finding D-5, each justification is stated as
*which simpler route was rejected and why*.

### DESIGN.md amendment round — 2026-08-29, round 10

Proposed text, to be appended to `hex/DESIGN.md` (implementation is
downstream; this ADR does not edit the file):

```markdown
## Finalize round (2026-08-29, round 10)

`adr_0009` (the finalize phase — the `/hex-finalize` command, the scoped
remote-rights amendment, and the convention-discovery contract) amends
**two resolved positions**. Full adjudication and the scored A/B/C/D
comparison, including its stated sensitivity: `adr_0009` § Constitution
deviations and § Considered Options.

1. **`hex never pushes` scopes to everything except `/hex-finalize`'s
   force-push of the one feature branch it was invoked on.** The rule
   above — "feature branch → trunk is the human's PR. hex never pushes"
   (§ Worktrees) — made every hex effect local and revertible, and that
   remains true of every other skill: `hex-plan`, `hex-execute`,
   `hex-review` and `hex-architect` are unchanged, and `hex-execute`'s
   own "Never push to remote" is untouched. The amendment is **one
   branch wide**: `/hex-finalize` may force-push the branch it was
   invoked on, fetch that branch and its target once to pin the lease
   and rebase onto real remote state, dispatch the project's own
   **documented** release workflows against the pushed SHA, and create
   or mutate that branch's one pull request. It **never** pushes the
   target branch, never merges, never touches branch protection, and
   never mints or stores a credential. Rejected alternative: **keeping
   the rule absolute and printing the remote commands for the human to
   run** (`adr_0009` Option D) scores within three points and is the
   design's own bottom rung — but the two steps it hands back are
   precisely the two that cannot be performed correctly outside the
   run. A `--force-with-lease` value must be pinned to the SHA *this
   run* fetched, or a background fetch silently degrades it to a plain
   force; and the checks must be dispatched against the SHAs the
   rewrite just minted, because a rewrite invalidates testing done
   against the SHAs it replaced. What the old rule protected — that a
   hex run leaves nothing a human cannot undo — is preserved by a
   mechanic rather than by abstinence: every rewrite is anchored by an
   armed `backup/<branch>-pre-finalize` ref taken before the first
   history-modifying operation and renamed inert on **every** terminal
   outcome, and a lease rejection is a hard stop rather than a retry.
   The **sole definition site** is `hex-core/references/finalize.md`;
   the four bundle-wide restatement sites gain a one-clause qualifier
   pointing there, and every skill-, worker- and federation-scoped
   restatement is **unchanged, because it remains true**.

2. **The single approval gate's *position* clause admits a third named
   member.** The shared shape puts one gate "before any work starts."
   `/hex-finalize` keeps **exactly one** approval gate and moves it to
   the local/remote boundary, on every degrade rung. Rejected
   alternative: **a conforming entry gate** would have to announce a
   commit plan that does not yet exist — the recomposed series is
   derived by reading the branch diff, so an entry gate asks the human
   to consent to a rewrite whose shape is unknown, which is the consent
   theater `adr_0005` rejected for the fold. What the rule protects is
   preserved exactly: one approval per run, no mid-flow questions, and
   the reader never misled — the gate sits where the irreversible act
   is and carries what only that position can carry, the exact
   recomposed commit list with its `Signed-off-by` lines and its
   literal signing identity. Everything before the gate is local and is
   reversed by one command against the backup ref. The exemption list
   in `protocol.md` § The meta-plan approval gate stays a **closed list
   of named skills with stated grounds**, gaining a third name and
   never a criterion to interpret.

**One `adr_0008` contract is amended, in the open.** C-718's rule-body cap
reads "≤10 lines" with no measure qualifier, and `hex-state.md`'s body is
exactly ten physical lines today. A second mode line is about three more.
Rather than redefine the measure to "non-blank" and claim headroom that
does not exist, `adr_0009` **raises the cap to ≤14 physical lines**, on the
ground that the cap bounds always-on instruction budget and that two modes
plus the generic frame is fourteen with nothing spare. The next mode's ADR
compresses or amends again, and — per this round's own erratum — budgets
the **description-line** surface alongside the rule body.

**Considered and not deviated** (unchanged by this round): the **two-layer
knowledge model** is upheld — every git convention, commit requirement,
release workflow and release-grade suite is a Layer-1 project fact,
discovered by `/hex-init` and pointed at, never authored as hex config;
`config.md` gains no key and its `<skill>` enumeration stays closed to the
four orchestrators. **`adr_0005`'s fold path is untouched** — finalize
never commits a fold; it halts on the uncommitted fold write with a named
fix, so `git add` remains where a human approves a fold. **Capability
classes** — untouched, and vacuously so: `/hex-finalize` spawns no workers.
**Plan lifecycle** — no new `State:` value; finalize appends one line to an
already-archived plan's Status block. **Federation** — `adr_0004` is
unchanged and federated finalize is deferred; the one amendment is that
`/hex-finalize` joins the satellite halt's scope, with its own `Fix:`
variant, because its blast radius is a rewritten branch rather than a
report.
```

### `protocol.md` deviation — the single-gate position clause

`protocol.md` § The meta-plan approval gate reads: "Exactly **one** approval
point, **before any work starts**… two skills are exempt, each named here with
its own stated ground… The list is closed — a skill not named here is not
exempt, whether or not it spawns workers, and a third member is added by
amending this sentence, never by analogy."

`/hex-finalize` keeps exactly one approval gate, so the *count* conforms; its
*position* does not. Per the 2026-08-29 review ruling on `adr_0008`'s
deviation 1, the exemption reaches only skills **named** in that closed list
and is never inherited by class analogy — so finalize cannot ride
`hex-discuss`'s entry on the grounds of also having a relocated gate.
**Rejected alternative: re-writing the exemption as a criterion** ("skills
whose gate sits at their irreversible act") converts a narrow, auditable
carve-out into a judgement call, the exact failure the sentence's own closing
clause was written to prevent. The sentence instead gains a **third named
member with its own stated ground**: `/hex-finalize` keeps exactly one
approval gate, positioned at the local/remote boundary on every degrade rung,
because the concrete commit plan it must disclose does not exist until the
rewrite is computed, and everything before that gate is local apart from one
read-only fetch and a credential probe, mutates nothing on any remote, spawns
nothing, and is undone from the backup ref — so there is no swarm to strand
and nothing on any remote has changed. Three named skills, three stated
grounds, no criterion to interpret. [erratum, WP3 review, 2026-08-29: the
draft's "everything before that gate is local … reversed by one command …
nothing has left the machine" was false — pre-gate finalize runs C-804(a)'s
credentialed CLI probe and (c)'s two-ref fetch, which writes `FETCH_HEAD` and
tracking refs, and the one-command reversal holds only on a clean tree in
phase 4. The shipped `protocol.md` sentence carries the corrected wording
above.]

**Second `protocol.md` edit, and it is not a deviation:** C-816 **promotes**
the untrusted-text echo rule from `hex-architect/SKILL.md` into a short
`protocol.md` § Untrusted-text echoes and retargets hex-architect's statement
to a link. That is single-source *compliance*, not a departure — the rule
gained a second consumer and a skill-scoped home cannot serve two skills.

### `memory.md` scope amendment — the satellite halt

`memory.md` § Location and resolution › Federation satellites scopes the C-308
halt to the four orchestrators and states that a non-orchestrator "resolves no
plan and writes no plan or federation state" and therefore sits **outside** it.

That reasoning does not transfer. `/hex-finalize` resolves no plan, but it
**rewrites and force-pushes a branch** that may be a row in a lead's `Repos:`
ledger and a step in its landing order. **Rejected alternative: letting
finalize sit outside the halt by the paragraph's own terms** — the
non-orchestrator clause is written for skills whose satellite-local effect is
advisory prose, and applying it to a skill whose effect is destroyed history
would reopen FM6 exactly as `adr_0004` describes it. The paragraph gains one
clause placing `/hex-finalize` **inside** the scope, and **one `Fix:`
variant**, because the existing single-definition `Fix:` ("re-run from the
lead") would steer a finalize invocation into finalizing the wrong repo's
branch. `hex-discuss`'s outside-status and `/hex-init`'s exemption are
unchanged. The amendment states honestly what it does not fix: the halt keys
on a bullet a virgin satellite lacks and a human may delete, and C-323's
structural invariant reads a plan that is already terminal by the time
finalize runs — so for a satellite the FM6 hazard is narrowed, not closed, and
a satellite branch is finalized by hand until federated finalize exists.

## Migration / rollout plan

*(Fills the template's Implementation-Plan slot; the corpus uses this heading —
`adr_0003`, `adr_0005`, `adr_0006`, `adr_0008`.)*

Three waves. `hex` is released at v0.2.0, so backward compatibility is a real
constraint. Every wave is **additive**; the honest claim is narrower than
"vacuous when unused": a session that never invokes `/hex-finalize` sees no
behavior change, but carries an amended always-on rule body, one more member
description, four amended sentences and one promoted protocol section.

- **Wave 1 — the contract.** `hex/hex-core/references/finalize.md` (C-819,
  carrying the definitions of C-809, C-811, C-812, C-813, C-818); the **four**
  qualifier sites (C-820); the `protocol.md` gate-position sentence (the
  deviation); the **promoted § Untrusted-text echoes** plus hex-architect's
  retargeting link (C-816); `archive.md`'s post-archive-append sentence
  (C-822); `memory.md`'s satellite-halt clause and finalize `Fix:` variant
  (C-824). After Wave 1 the contract exists and nothing consumes it yet.
  *Verify:* `grim build ./hex/hex-core`, `./hex/hex-architect`.
- **Wave 2 — the command.** `hex/hex-finalize/SKILL.md` (C-801…C-808, C-810,
  C-814, C-815, C-817); the `hex-state.md` mode line and the amended cap
  (C-821); `hex-review`'s handoff line (C-823). *Verify:*
  `grim build ./hex/hex-finalize`, `./hex/hex-review`, `./hex/hex-state.md`.
- **Wave 3 — provisioning and wiring.** The `hex-init` audit item and Pointers
  rows (C-826); the seven bundle touch points plus `grimoire.toml` (C-827);
  DESIGN.md round 10. *Verify:* `grim build ./hex/hex-init`,
  `grim build ./hex/hex.toml`, `task publish -- --dry-run`.

**Existing installs.** `grim update` pulls the new member; a consumer that
never invokes it is unaffected. No directory is provisioned eagerly — finalize
creates no artifact of its own beyond a git ref.

**Version and changelog.** `publish.toml` `version = "0.3.0"`;
`hex/CHANGELOG.md` gains an `## [0.3.0]` section with `### Added` (the
`hex-finalize` command; the scoped remote-rights amendment and its
`finalize.md` home; the `hex-init` commit-and-landing-requirements audit item;
`/hex-review`'s finalize handoff) and a `### Notes` line recording C-828's
declined spawn with its revisit trigger.

**Rollback.** The full edit set, enumerated rather than discovered piecemeal:

- `hex/hex.toml` — the `"hex-finalize"` skill entry.
- `hex/publish.toml` — the `[skills."hex-finalize"]` entry and the version bump.
- `grimoire.toml` — the `hex-finalize` skill entry.
- `hex/hex-core/references/finalize.md` — deleted in full.
- The **four** qualifier sites — **restore the prior sentence**, do not merely
  delete the clause: `DESIGN.md:174`, `protocol.md:544`, `protocol.md:850`,
  `archive.md:474`. (`archive.md:356` is **not** on this list — it was never a
  never-push site.)
- `protocol.md` § The meta-plan approval gate — restore the two-name closed
  list, including the count in the sentence's own text.
- `protocol.md` § Untrusted-text echoes — delete the promoted section **and**
  restore `hex-architect/SKILL.md`'s inline statement; deleting the section
  while leaving the link would strand hex-architect's own rule.
- `memory.md` § Federation satellites — restore the paragraph without the
  finalize clause **and** without the finalize `Fix:` variant.
- `archive.md` § Plan archive — the post-archive-append sentence.
- `hex/hex-state.md` — the finalize mode line; **and restore C-718's ≤10-line
  cap**, which the rollback must undo alongside the line that needed it.
- `hex/hex-review/SKILL.md` — the handoff `Next:` line reverts to
  `(none — approved)`.
- `hex/README.md` — the Members row, the Quickstart line, the intro sentence,
  the tier-grammar exemption's third name, and the remote-write sentence.
- `hex/DESIGN.md` — round 10 in full.
- `hex-init` — the audit item, the two Pointers rows, and the discovery-note
  block's seventh command.
- Project `CLAUDE.md` — the "Commands:" line's seventh entry.

No other skill takes a dependency on `hex-finalize`; `hex-review`'s handoff
line is a conditional string and is inert without it. **A published artifact
is never un-shipped by deletion** — retiring `hex-finalize` follows this repo's
convention (`deprecated` plus `replaced-by` authored in the source and
re-released).

## Validation

- [ ] `grim build` exits 0 for `./hex/hex-core`, `./hex/hex-architect`,
      `./hex/hex-finalize`, `./hex/hex-review`, `./hex/hex-init`,
      `./hex/hex-state.md`, and `./hex/hex.toml` after their wave;
      `task publish -- --dry-run` is green.
- [ ] **The never-push sweep matches C-820's site table exactly**: the **four**
      qualified sites (`DESIGN.md:174`, `protocol.md:544`, `protocol.md:850`,
      `archive.md:474`) each carry the clause and a link to `finalize.md`; and
      **every other row in that table is byte-identical to before** — including
      `archive.md:356`, `protocol.md:540`, `protocol.md:637`,
      `hex-execute/SKILL.md:495` and **`:570`**, the three `hex-execute` tier
      files, `workers.md:39`, `workers/builder.md:29`,
      `hex-plan/SKILL.md:303`, `hex-architect/SKILL.md:458`,
      `hex-review/SKILL.md`'s three sites, and `hex-init/references/audit.md:171`.
- [ ] **The echo rule has exactly one home** (C-816): `protocol.md` carries
      § Untrusted-text echoes, `hex-architect/SKILL.md` links it instead of
      stating it, `finalize.md` links it, and a grep finds the 120-character
      rule stated **once**.
- [ ] **`hex-state.md` fits its amended cap**: body ≤14 physical lines
      measured H1 onward, the finalize line's predicate is the **armed** ref
      name alone, and the line carries the **release clause** (rename to
      inert). C-718's amended cap is recorded in DESIGN round 10, not
      only here.
- [ ] No shipped file added by this ADR names a literal model or a
      harness-specific tool — verified by grep, not assumed.
- [ ] **The gate is complete and precedes every remote act** (C-805): a
      dogfood run renders branch/target with sources; every convention with
      source **and trust class**, `unknown` as `unknown`; the full commit list
      with per-commit sign-off, re-sign and `Co-authored-by:` state; the
      **signing identity as `user.name <user.email>`, not the forge login**;
      the verification result **and whether it re-ran post-rebase**; the rebase
      result and base movement; **workflow drift**; **auto-merge / merge-queue
      state**; the three post-gate acts with the pinned lease SHA; the
      `Never:` line; the identity **with its credential source**; and the
      backup ref. **No remote act precedes it, on any rung.**
- [ ] **The gate asks on the local-only rung too** (C-805, S-806), and the
      state machine renders that rung's own terminal path.
- [ ] **A `no` at the gate performs zero remote acts, leaves the rewritten
      branch, renames the backup ref inert, and prints the restore command**
      (S-807) — and a subsequent `/hex-state`-governed turn on that branch is
      **no longer halted**, proving the decline released the lock.
- [ ] **Pre-flight is three resolution steps and six halts** (C-804), each
      halt with its own `Error:`/`Fix:` pair: on the target branch; **not the
      primary checkout** (an agent worktree is refused); dirty tree, with the
      **fold-aware** variant that names the fold and prints `git add` /
      `git commit` while committing nothing; no commits ahead; federation
      satellite; and **a failed fetch**, which never falls back to the local
      target ref. The CLI probe is **not** a halt — it selects a rung.
- [ ] **Halt 3's two variants select correctly across the whole build window**
      (C-804, system design FM12): with **no armed ref**, a tree dirty with the
      fold write prints the `git add`/`git commit` pair; with an **armed ref
      and any unclean tree** — tested at three points, before commit 1, after
      commit *k* of *N*, and after the last — it prints the
      **reset-and-re-run** recovery. The fold pair must never fire while a ref
      is armed.
- [ ] **The forge half degrades without the base degrading** (C-804, C-811):
      with the CLI removed but git transport working, the run takes the
      local-only rung **and still rebases onto a freshly fetched target**;
      with the fetch itself failing, the run **halts**.
- [ ] **The force-push command form is literal and exact** (C-812): a grep of
      shipped text finds `--force-with-lease=<branch>:<sha>` with an
      **explicit single-ref refspec**, finds `--force-if-includes` in **no
      command position** — its only permitted occurrence is C-812's
      "deliberately not issued" prose, so a naive presence grep passes for
      the wrong reason and the check must assert absence-from-command-form
      [erratum, WP7 sweep, 2026-08-29: E1 dropped the flag; the item still
      required finding it] — and finds no bare `--force`, no unpinned
      lease, and **no `--all`, `--mirror` or `--tags`**.
- [ ] **A lease rejection is a hard stop with two distinguishable
      diagnostics** (C-812, S-803): the pushed-during-run case reports both
      SHAs; the fresh-clone / reset case reports that integration cannot be
      proven and does **not** advise forcing. Neither retries.
- [ ] **The backup ref round-trips armed → inert on all three terminal paths**
      (C-809): success, gate decline, and a post-rewrite halt. Creation
      **refuses to overwrite** an armed ref. The name preserves the branch's
      `/` structure, and two branches differing only after a `/` produce
      distinct refs. **Declining twice from the same pre-rewrite tip** is a
      no-op rename (the inert ref already resolves to that SHA), not a
      failure and not a clobber.
- [ ] **Every pre-push resume lands on the gate** (C-818, S-808): killed after
      recomposition, killed after the gate but before the push, and **declined
      then re-invoked** all re-run forward to the gate — none resumes directly
      at the push. Recomposition run twice **never double-applies** (C-807) —
      the asserted property is that the branch diff and base are preserved,
      **not** that the series is byte-identical.
- [ ] **A published rewrite is resumed, never rebuilt** (C-808, C-818): a run
      that pushed but did not dispatch, re-invoked **in a fresh session**,
      takes the `published_rewrite` path — it performs **no second
      recomposition, no second force-push and no second dispatch**, and its
      gate (asked again, since the flag is session-local) shows a **reduced act
      set naming no rewrite and no push**. Asserted by SHA: the branch tip
      after the resume equals the tip before it.
- [ ] **The predicate keys on *armed*, not on any backup ref** (C-818): the
      complementary case — a **terminated** prior finalize (inert ref) on a
      branch that has since gained human commits — **rebuilds**, in **both**
      variants: commits left local (tips differ) **and commits already
      pushed** (tips equal). The pushed variant is the one an
      any-backup-ref predicate would misroute into a resume, dispatching and
      flipping work that was never recomposed.
- [ ] **Recomposition is asserted SHA-unstable, not assumed stable** (C-808):
      recomposing the same partition twice with signing enabled produces
      **different commit ids**, which is why no contract anywhere relies on a
      "push is a no-op when tips match" branch.
- [ ] **Author-set equality halts on a mismatch** (C-808, `archive.md` C-414):
      `%an <%ae>` over the backup ref's original series equals the union of the
      recomposed authors and their `Co-authored-by:` trailers; a fixture that
      drops one trailer **halts**, and the check is command output, not a
      claim in prose.
- [ ] **Post-push re-entry skips correctly** (C-818): tips equal → push
      skipped; a run exists for the SHA in **any** state, including
      **completed-red** → **no second dispatch**; PR ready → no second flip.
      **No state file is created on any path.**
- [ ] **The workflow set is authoritative-class** (C-813): a branch that adds
      a dispatchable workflow **not named by project context** does **not**
      get it dispatched; and a branch that **modifies** a documented
      workflow's file has that drift **named at the gate** with the changed
      paths.
- [ ] **No workflow input is ever sourced from narrowing- or untrusted-class
      text** (C-813) — verified by grep of the shipped text and by a fixture
      whose `CONTRIBUTING.md` and PR body both attempt to supply one.
- [ ] **The series shape resolves in three steps and the gate names which
      one won** (C-807, C-815, C-826): a repo documenting its convention gets
      it (step 1); a repo with only a `hex.md › Preferences` hint gets that
      (step 2); a repo with neither gets a **minimal bisectable series**
      (step 3). The gate line carries the step, so "bisectable series" is
      never ambiguous between *asked for* and *defaulted to*. `config.md`
      stays byte-identical — the hint is Preferences **prose**, not a key.
- [ ] **`/hex-init` offers the hint only when discovery finds nothing**
      (C-826): a project whose convention is already documented is **not**
      asked; a project with neither documentation nor hint is offered the
      record once, with consent, and the shipped default is named as the
      alternative.
- [ ] **The rerun ceiling is exactly one** (C-813): a second consecutive
      failure **stops the run** rather than rerunning again, the PR stays in
      draft, and the count is read from the run's own rerun count so
      re-invoking does not buy a second attempt.
- [ ] **Dispatch matches the forge's own unit** (C-813): on GitHub, one
      dispatch **per documented workflow file**; on GitLab, **one pipeline
      trigger per SHA** with the documented set verified against that
      pipeline's job statuses, and a documented entry with no matching job
      reported **not present**, never passed. No implementation attempts N
      triggers on GitLab.
- [ ] **The handoff renders both check facts** (C-806): a run with an **empty
      documented set** that flipped the PR and thereby triggered
      `on: pull_request` CI prints **two lines** — *no remote gate exists* and
      *checks running, unwatched* — and never collapses them into one value.
- [ ] **Spend ceilings survive re-invocation** (C-813, S-809): re-invoking
      after a completed-red run neither re-dispatches nor resets the rerun
      budget, because both key on the run's own state and rerun count.
- [ ] **The flip is guarded twice** (C-814, S-813): with auto-merge armed or a
      merge queue present, the gate discloses it and finalize **does not
      flip**, reporting ready-but-held; and after a flip, flip-triggered
      checks are **watched**, with the handoff distinguishing green, red, and
      **unwatched (still running)**.
- [ ] **"No dispatchable workflow" is not reported as a pass** (C-806, C-811):
      the rung is selected **at the dispatch step**, not at pre-flight, and
      the handoff says **no remote gate exists**.
- [ ] **Narrow-never-widen holds, and its scope is enumerated** (C-815,
      C-816, S-805): a hostile `CONTRIBUTING.md` cannot reach the target
      branch, the merge strategy, the workflow list or the verification level;
      its stricter message rule *is* applied; and every echo is quoted and
      truncated past 120 characters without breaking its line.
- [ ] **The DCO identity rules hold on a multi-author branch** (C-808, S-810).
- [ ] **The workflow-scope gap is surfaced before it bites** (C-817): a series
      touching the workflow directory produces a gate line naming the extra
      credential right required, and the rejection itself (system design
      FM15) is reported with that cause rather than as a generic push failure.
- [ ] **Finalize touches no lifecycle state** (C-822): the plan's `State:` is
      unchanged, the pointer stays cleared, the artifact index gains **no
      second row**, and the Status block carries exactly one appended line.
- [ ] **`/hex-review` emits the handoff line under exactly its condition**
      (C-823), with **no forge read** in hex-review.
- [ ] **The satellite halt fires with finalize's own `Fix:`** (C-824, S-811):
      the message names hand-finalization and does **not** say "re-run from
      the lead"; `/hex-discuss` in the same repo still does not halt.
- [ ] **`config.md` is byte-identical** (C-825), and README's tier-grammar
      exemption sentence names three skills.
- [ ] **`hex-init` makes no network call** (C-826): the new audit item is
      exercised offline and `audit.md:171` stays true verbatim; the item
      surfaces the target-branch-protection recommendation.
- [ ] **Dogfood — `/hex-finalize` runs on its own implementation branch**:
      recomposed changelog-worthy commits, sign-off and signature state
      intact, a clean linear rebase onto the freshly-fetched target, the
      documented workflow dispatched against the final SHA, and the
      draft→ready flip observed.
- [ ] S-801…S-813 pass as acceptance cases.

## Open Questions

**None. Zero markers remain**, and the section is kept as the record of how
the three the draft carried were closed.

- **Post-rebase re-verification** — resolved during the round-1 fix pass into
  **C-803 and C-810** rather than shipped as contracts that contradict their
  own open question: the local suite re-runs once, after the rebase and before
  the gate, **if and only if** the fetched target tip differs from the base
  the pre-rewrite verification ran against.

- **Series-shape default** — **resolved by the owner, 2026-08-29**:
  recommendation accepted **with a rider**. The shipped default is a minimal
  bisectable series, and it is now the last of **three** resolution steps
  rather than the only fallback — the project's documented convention first,
  then a **`hex.md › Preferences` prose hint** written by `/hex-init` with
  consent, then the shipped default (**C-807**, with the audit item at
  **C-826** and the trust class at **C-815**). The rider is the substance of
  the change: the default becomes part of hex's own init surface instead of
  being reachable only by documenting it in the project. It rides
  **Preferences prose, never a config key** — `config.md`'s v1 vocabulary is
  frozen at six keys (C-223) and one default does not justify reopening it
  (**C-825**).

- **Rerun ceiling** — **resolved by the owner, 2026-08-29**: recommendation
  accepted as-is. **Exactly one automatic rerun, of the failed jobs only,
  counted per SHA**, folded into **C-813**'s spend text. The forge's
  50-reruns-per-run ceiling is a shared, exhaustible budget, and a second
  automatic rerun starts laundering a real failure into a flake — which is the
  one thing a finalize that flips a PR to "ready" must never do.

## Links

- Source discussion: [finalize-phase.md](../discussions/finalize-phase.md)
  — the ratified dossier this ADR consumes.
- Companion: [adr_0009_system_design.md](adr_0009_system_design.md) — the
  buildable spec: C4, the state machine and its re-entry points, the trust
  boundaries, the failure-mode table, the degrade ladder, the per-act forge
  command table, and the per-file edit sequence.
- Related ADR: [adr_0004_cross_repo_federation.md](adr_0004_cross_repo_federation.md)
  — the satellite halt this decision joins, and the federation posture it
  defers to.
- Related ADR: [adr_0005_archive_fold_back.md](adr_0005_archive_fold_back.md)
  — the sole-amender pattern C-819/C-820 follow, and the uncommitted-fold
  consent point C-804 refuses to take.
- Related ADR: [adr_0008_pre_plan_discussion_mode.md](adr_0008_pre_plan_discussion_mode.md)
  — the precedent class, the closed gate-exemption list this decision extends,
  the rule-amendment pattern C-821 follows, and the C-718 cap it amends.
- Research: [adr0009-remote-rights.md](../research/adr0009-remote-rights.md),
  [adr0009-failure-modes.md](../research/adr0009-failure-modes.md),
  [adr0009-hex-compat.md](../research/adr0009-hex-compat.md),
  [discuss-finalize-series-shape-rules.md](../research/discuss-finalize-series-shape-rules.md),
  [discuss-finalize-rewrite-timing.md](../research/discuss-finalize-rewrite-timing.md),
  [discuss-finalize-detection-recipe.md](../research/discuss-finalize-detection-recipe.md),
  [discuss-finalize-teams-policy-surfaces.md](../research/discuss-finalize-teams-policy-surfaces.md),
  [discuss-finalize-teams-adaptive-tools.md](../research/discuss-finalize-teams-adaptive-tools.md),
  [discuss-finalize-teams-agent-field.md](../research/discuss-finalize-teams-agent-field.md),
  [discuss-finalize-teams-oss-landscape.md](../research/discuss-finalize-teams-oss-landscape.md),
  [discuss-finalize-branch-automation.md](../research/discuss-finalize-branch-automation.md),
  [discuss-finalize-changelog-frameworks.md](../research/discuss-finalize-changelog-frameworks.md).
- Prior art: the Developer Certificate of Origin
  ([developercertificate.org](https://developercertificate.org/)); GitHub
  Copilot's coding agent branch-prefix write restriction **and its
  human-approval control for agent-triggered workflow runs**
  ([risks and mitigations](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations));
  OpenAI's Codex least-privilege token guidance
  ([Codex admin setup](https://developers.openai.com/codex/enterprise/));
  the Linux kernel's rebasing-and-merging guidance
  ([docs.kernel.org](https://docs.kernel.org/maintainer/rebasing-and-merging.html)).

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-08-29 | hex-architect | Initial draft. Chosen Option A (one command, one gate at the local/remote boundary) from a 4-option weighted comparison. Contracts C-801…C-828, scenarios S-801…S-812. One DESIGN.md round (10), one `protocol.md` gate-position deviation, one `memory.md` satellite-halt scope amendment. Status Proposed. |
| 2026-08-29 | hex-architect | **Panel round 1 fixes — 5 Block / 23 High / 12 Warn / 8 Suggest, all actionable findings applied; contracts amended in place, nothing renumbered; scenario range extended contiguously to S-813.** Security Block: C-813 rewritten — the workflow set is **authoritative-class** (documented ∩ dispatchable, never scanned from the branch), a dispatch is stated to execute **branch-defined code**, branch-vs-target workflow drift is disclosed at the gate, no input is ever sourced from narrowing- or untrusted-class text, and Copilot's human-approval-of-triggered-runs control is named rather than silently dropped; spend ceilings now key on the run's own state and rerun count so they survive re-invocation. Quality Block + spec Block 2: **every pre-push resume re-enters at the gate** — a declined gate can no longer become an approved force-push — which is safe because C-807 now **names the recomposition mechanism** (`rebase --onto` → `reset --soft` → staged re-commit), making the series a function of the diff and therefore **idempotent by construction** [weakened at round 2 to *never double-applies* — see the row below; history is annotated, not rewritten]; the draft's "not blindly re-runnable" claim is overturned. Spec Block 3: `archive.md:356` is a never-**commits** site, so the amendment lands at **four** bundle-wide sites, not five; prose counts are replaced by a **site table** reconciled byte-for-byte with the migration, rollback and Validation lists, and `hex-init/references/audit.md:171` is kept true by scoping C-826 to zero forge reads. Spec Block 1: the leaked EOF scaffolding is stripped from both files. Further root fixes: backup ref gains an **armed/inert two-name lifecycle** whose rename **releases the lock on every terminal path including a decline** (closing the "declined run leaves every hex mode halted" hole), preserves `/` structure against cross-branch collision, and refuses to overwrite an armed ref; the rebase target is **fetched fresh** and target/merge-strategy/workflow-list/verification-level are **authoritative-class only**, removing them from the narrowing resolver; C-812 gains the literal command form with an explicit single-ref refspec, forbids `--all/--mirror/--tags`, drops the unreachable already-matches carve-out, and splits the rejection diagnostics; the gate gains the DCO **signing identity** (`user.name <user.email>`, not the forge login), auto-merge/merge-queue state (with a **do-not-flip** narrowing), credential source, workflow drift, and the publication-gate framing; C-814 watches **flip-triggered** CI so "no `workflow_dispatch`" is no longer conflated with "no CI"; pre-flight is corrected to **three resolution steps and five halts**, gaining a **workspace-invariant refusal** for agent worktrees and a corrected ordering (target resolved before it is checked); C-816 **promotes the echo rule to `protocol.md`** rather than restating it; C-821 **amends C-718's cap in the open** (≤14 physical lines) instead of silently redefining the measure, and C-801 adds the round-9 erratum's missing **description-line budget**; C-824 gains finalize's own `Fix:` variant and states the virgin-satellite and post-terminal-plan holes honestly; C-811's ladder fixes its rung-selection points. Decisions recorded rather than deferred: the matrix's **two decisive cells are defended and its ranking declared non-robust** (D's protocol fit corrected to 85 — D needs the same gate — and the decision rests on the two-manual-steps argument); **OQ2 folded into C-803/C-810**, leaving **two** markers; the **absorb pre-pass declined** with its ground; a **message-matches-diff** check adopted. F1 restated as **narrowing-with-ground** rather than "not a second consent event", F6 states its **two departures from the dossier's backup-ref recommendation** as departures, and the Security NFR corrects the "structural containment" parity claim — hex's act set is prompt text; target-branch protection and the harness allowlist are the controls that hold. Status Proposed. |
| 2026-08-29 | hex-architect | **Round-2 micro-fixes — 3 High, 3 Warn, 3 Suggest, all applied; no IDs added or renumbered.** *High:* the local-only rung is separated from a failed fetch — C-804(c) makes a **fetch failure a halt** (a rung with no fetched target could only rebase onto the local ref the same clause forbids) while an absent or unauthenticated **CLI** still takes the rung, because git's own transport is unaffected; C-811's ladder and the system design's FM6a/FM6b split and § 7.2 say the same thing. Pre-flight **halt 3 gains a recompose-aware variant that takes precedence** — an armed ref plus a staged diff equal to the branch-vs-target diff means an interrupted `reset --soft`, so the printed `Fix:` is reset-and-re-run, never the fold pair [predicate widened at round 3 to *armed ref + unclean tree* — see the row below; history is annotated, not rewritten], which would have frozen a half-built series into history (system design FM12's trigger list extended). *Warn:* the **idempotence claim is weakened to the true one** — recomposition **never double-applies**, but the partition into logical commits is judgment, so the series is not promised byte-identical; C-807, C-818 and the re-entry table now say so, and the dropped tip-shape guard is justified on its own terms (it could not have caught a differing partition; the re-gate does). `draft→ready only when green` is corrected for the empty-workflow path — the bar is the **resolved** gate, and the composing rule for "no remote gate exists" beside C-814's post-flip watch is stated. C-820's site table gains a comparative note on **why `:637` and `:850` split** (which repo the claim is about, not which section it sits in). *Suggest:* the inert rename is defined for a **repeat decline from the same tip** (no-op when the ref already resolves to that SHA, refuse otherwise); the re-entry chain defines its two forge helpers **on the local-only rung**; and the per-act forge command table is given **C-813 as its owner** and folded into `finalize.md` § 6. Four Validation items added, one amended. Status Proposed. |
| 2026-08-29 | hex-architect | **Cross-model (codex) round — 3 High, 2 Warn, 1 Suggest, all applied; no IDs added or renumbered.** *High-1, a real defect:* C-808's mandatory re-signing stamps a fresh timestamp, so **recomposition is not SHA-stable** — a rebuild of an identical partition mints new commit ids. C-818's "the push is a content no-op when the tips match" was therefore **unreachable**, and a fresh session resuming a pushed-but-undispatched branch would have force-pushed, dispatched and attested a **second** time. Fixed at the root by **routing, not comparison**: re-entry now evaluates `published_rewrite` (a backup ref exists **and** the remote tip equals the local tip) **before** any decision to recompose, and resumes from the published tip with a **reduced act set naming no rewrite and no force-push**; only genuine local divergence rebuilds. The no-op clause is deleted as false. Reconciled across C-808, C-818, the system design's § 4.1 chain and § 5 table, and the Cost NFR (which would otherwise have been unbounded across re-invocations). *High-2:* halt 3's recompose-aware predicate widened from a staged-diff-equality test — true only in the instant before commit 1 of N — to the whole-window invariant **armed ref + unclean tree**, which is sound because the armed name exists only while a run is in flight; FM12 and Validation aligned. *High-3:* dispatch semantics made **forge-conditional** — GitHub dispatches once per documented workflow file, GitLab has one pipeline per ref and so issues **one trigger per SHA** with the documented set mapped to jobs/stages inside it and a missing entry reported *not present*, never passed; stated in C-813, the portability driver, and the system design's § 8. *Warn-1:* C-806's remote-check result splits into **two independent lines** — what this run dispatched, and what is running now — so an empty documented set plus flip-triggered `on: pull_request` CI cannot overwrite one truth with the other. *Warn-2:* `Co-authored-by` preservation gains a mechanical **author-set equality halt** (`%an <%ae>` over the backup series against the union of recomposed authors and trailers), citing `archive.md` C-414's evidence-not-narration rule, making it symmetric with C-807's message-matches-diff halt. *Suggest-1:* the watch bound is re-attributed to the **calling harness's tool-execution limit** rather than a documented CLI timeout; the bounded retry stands. Six Validation items added, two amended. Status Proposed. |
| 2026-08-29 | hex-architect | **Final residual round — two Warns closed.** *Warn-A:* the fetch failure was declared a halt in C-804(c)'s prose but never counted, so every enumeration still said five. It is now **halt (6)** with its own `Fix:`, and the count reads **six** at all four sites — C-804's header, its numbered list, the system design's § 3 pre-flight box and § 5 mermaid halt edge, and § Validation. *Warn-B:* `published_rewrite` keyed on *any* backup ref, so a branch whose prior finalize had **terminated** (inert ref) and which then gained human commits **that were pushed** satisfied `anchor and local == remote` and was resumed — dispatching and flipping work that was never recomposed. The predicate now keys on the **armed** ref alone, which is exact rather than heuristic: the armed name survives only while a run is unfinished, so it means "pushed, steps pending", while an inert ref means the prior run terminated and any new work must be rebuilt. The `anchor` binding is deleted, the `run is None` branch re-routed to `PREFLIGHT`, and the § 5 "Second, later finalize" row now states that its tips may be equal. One Validation item added for the pushed variant. Status Proposed. |
| 2026-08-29 | Michael Herwig (owner decision) | **Both open questions resolved; zero markers remain.** **(1) Series-shape default — accepted with a rider.** The shipped default stands as a **minimal bisectable series** (one commit per user-facing change, riders split), on the recorded ground that squash-to-one is unrecoverable information loss performed on the human's behalf while a series can still be squashed by the merge button — the reversible direction. The rider makes the default part of hex's **own init surface** rather than something reachable only by documenting it in the project: C-807 now resolves the two axes in **three explicit steps** — (1) the project's documented convention, which always wins; (2) a **`hex.md › Preferences` prose hint** written by `/hex-init` with consent; (3) the shipped default. Step 2 rides **Preferences prose, never a config key**, following the `adr_0004`/`adr_0005` precedent — `config.md`'s v1 vocabulary froze at six keys (C-223) and one default does not justify reopening it, so **C-825's claim is narrowed from "zero config surface" to "zero config *key*"** and states the distinction. C-815 places the hint in the authoritative class between documentation and default; C-826's audit item now **offers to record the preference when discovery finds the axes undocumented**, naming the shipped default as the alternative; and the gate **names which of the three steps resolved**, because "bisectable series" means a different thing when a team asked for it than when nobody said anything. **(2) Rerun ceiling — accepted as-is:** **exactly one automatic rerun, of the failed jobs only, counted per SHA**, folded into C-813's spend text and the Cost NFR. § Open Questions is kept as the record of all three closures rather than deleted. **Status remains Proposed** — acceptance is the owner's separate act. |
| 2026-08-29 | WP2 panel | **Implementation-panel errata — two design defects found while building `finalize.md`; contracts amended in place, nothing renumbered, counts unchanged.** *E1, verified against git-push(1):* `--force-if-includes` is a documented **no-op** when combined with `--force-with-lease=<refname>:<expect>`, so C-812's literal command carried a flag that did nothing while reading as a second safety check. The flag is **dropped**; the pinned lease stands; and the integration property moves **earlier** to C-804(c), which now asserts `git merge-base --is-ancestor <pinned-sha> <branch>` while ancestry still exists to test. Halt (6) widens from "the fetch failed" to "the fetch failed **or** the pinned SHA is not an ancestor of the local tip", carrying **two diagnostics** (someone else's commits → reconcile by hand; work this checkout lost track of → establish integration locally, never force). **The halt count stays six**, and the failure now fires **before** the rewrite rather than at a rejected push. *E2:* C-818's chain fell through to `WATCH` / `FLIP` / `POST` on *not armed + tips equal + a run exists*, reaching a post-push step **with no gate**, on work never recomposed. Every state that is not `published_rewrite` now routes to **pre-flight**; the run state is consulted only inside `RESUME_PUBLISHED`; and the run query is **scoped to finalize's own `workflow_dispatch` run for that head SHA**, so a branch's ordinary `on: push` CI cannot stand in for it — still no journal file. *E3:* C-811's never-list forbade "**reads**, writes or bypasses branch protection or rulesets", contradicting the reads C-815 and the § 8 command table mandate; narrowed to **writes or bypasses**, with the fixed enumeration scoped to **mutations plus the one fetch** and read-only forge queries stated as discovery, not acts. *F4:* C-815 gains the resolution ref for authoritative **files** — the fetched target, never the branch under change, with divergence disclosed at the gate. *F10:* S-808 reworded to the resume-published path (the push is never reached, not "skipped as a no-op"). Status Accepted; these are errata to an accepted record, not a re-decision. |
| 2026-08-29 | WP3 review | **Implementation-panel erratum — one High, found while splicing the exemption sentence.** The `protocol.md` deviation's prescribed clause claimed that before finalize's gate "everything … is local", that the run "is reversed by one command against the backup ref", and that "nothing has left the machine". All three overstate: C-804(a) probes the forge CLI **with credentials** and (c) **fetches two refs**, writing `FETCH_HEAD` and remote-tracking refs, before the gate is reached; and the one-command reversal is exact only for a clean tree inside phase 4. The clause is reworded to the true claim — local **apart from one read-only fetch and a credential probe**, **mutates nothing on any remote**, spawns nothing, **undone from the backup ref**, so there is no swarm to strand and **nothing on any remote has changed** — keeping the position-deviation grammar and the closed named list. The consent boundary is unchanged: what the gate protects is the first *mutation*, which is still the force-push. `protocol.md` ships the corrected wording; the deviation text above carries the inline marker. Status Accepted; erratum to an accepted record. |
| 2026-08-29 | WP2 panel (addendum) | **Two additions from WP1's panel, same round.** *(1)* The system design's § 10 worked gate filed `branch protection` inside the **narrowing** block, contradicting C-815 — rulesets, rules-for-branch and required-check lists are **authoritative-class**, and resolver B has exactly four conventions. The row moves to the authoritative block in the render; **C-815's own text was already correct and is unchanged**. *(2)* S-802's "names the dirty paths as the fold" is now discharged explicitly in `finalize.md`'s halt (3) fold-aware variant, which **lists every dirty path** and is stated never to summarise them as "the fold". **S-802's ADR wording needed no change** — it already says what the halt renders. |
| 2026-08-29 | WP7 sweep | **Validation erratum — one stale item.** The C-812 command-form check (V12) still required the grep to find `--force-if-includes` beside the pinned lease — the exact flag E1 dropped — so a naive presence grep passed only because C-812's "deliberately not issued" prose mentions the flag. The item now asserts the inverse: `--force-if-includes` appears in **no command position**, its sole permitted occurrence being that prose sentence. No contract text changed; the check was corrected to match E1. Status Accepted; erratum to an accepted record. |
| 2026-08-29 | Adversary round (codex, code-diff, branch close) | **Two High, one Warn — all applied.** *High-1 (C-809):* "every terminal outcome performs the rename" contradicted the rename's own refuse-rather-than-clobber branch, leaving no documented exit when a foreign ref occupies the inert name — the branch would stay armed, locking every hex mode, silently. The refusal is now **loud**: an `Error:`/`Fix:` pair (inspect both refs, move the stray aside, run the rename by hand), the lock's persistence stated as correct, and the invariant qualified with its one exception. *High-2 (C-802):* the explicit target argument outranked an open PR's base field silently, so a run could rebase onto one branch and force-push, then flip **a PR landing a different branch** to ready. Now a **hard stop at discovery** — before the gate and the rewrite — with both values and both exits named; finalize never retargets the PR itself (that would widen C-811's fixed act set), and the stop rides the discovery phase like the push rejection, outside C-804's six pre-flight halts, so no enumeration changes. *Warn (C-812):* the literal command's `<…>` placeholders gain the rule that each substitutes as a **single quoted shell argument** — refnames may legally carry `$`, `;` and parentheses, so an unquoted substitution lets a hostile but valid branch name rewrite the command. Status Accepted; errata to an accepted record. |
| 2026-08-30 | Review fix pass (/hex-review 2026-08-29: Request Changes — 1 Block, 6 High, 10 Warn; all actionable findings applied in FX1–FX3) | **Five contract errata, in place.** *C-808:* **trailer provenance** — recomposed messages derive from the diff and carry only finalize-generated trailers (`Signed-off-by:` from `--signoff`, `Co-authored-by:` from the author set); no trailer is ever copied from a branch message, closing the forged-sign-off lift the message/diff and author-set checks both missed. C-807/C-808 also gain their bolded definition sites in `hex-finalize/SKILL.md` § Recompose — the two IDs DESIGN round 10 cites were otherwise undefined in the bundle. *C-809:* the **arming** refusal gets the rename refusal's loud `Error:`/`Fix:` treatment — armed + clean tree + tip ≠ remote routed pre-flight → Recompose → refuse in a circle with nothing printed; re-arming over an armed ref is stated forbidden. *C-812/C-804:* the **placeholder-quoting rule promotes to `finalize.md` § Scope** (file-wide, both files, stated once); halt (1)'s unfillable `git switch <feature-branch>` Fix: becomes prose. *C-818:* the gate-passed flag is **keyed on (branch, pushed SHA)** at its definition site. *C-813/C-806:* the re-dispatch guard is **scoped to finalize's own `workflow_dispatch` runs**, matching C-818's emphasis; a foreign run never suppresses the dispatch nor appears as verification evidence. Doc-level fixes with no contract delta: README quickstart order (Block), bundle keywords, hex-init series-shape single-sourcing, resume render's full Never: line, "never runs pre-gate" carve-out dropped, remote-rights site label, Preferences added to the authoritative enumeration (aligns C-815's prose with its own table), `<transport error>` marked as a C-816 echo site. Status Accepted; errata to an accepted record. |
