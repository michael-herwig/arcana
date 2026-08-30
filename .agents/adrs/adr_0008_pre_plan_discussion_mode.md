# ADR: Pre-plan discussion mode — the hex-discuss skill, the discussion artifact class, and the bundle's first rule

## Metadata

**Status:** Accepted (Michael, 2026-08-28 — plain approval: the three
Open-Questions recommendations stand)
**Date:** 2026-08-28
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A (originated in the 2026-08-27/28 dogfood discussion, persisted as `.agents/discussions/hex-discuss-skill.md`)
**Related PRD:** N/A
**Architectural Conventions:**
- [ ] Decision follows this project's stated architectural conventions /
      golden path
- [x] OR the deviation is justified in the Rationale section below
      (two `DESIGN.md` amendments + two `protocol.md` deviations + one
      `models.md` scoping clause — see
      [Constitution deviations](#constitution-deviations))
**Domain Tags:** api, devops (a bundle member + a shared artifact convention)
**Supersedes:** N/A
**Superseded By:** N/A

## Context

Every non-trivial hex session starts the same way and hex has no skill for
it: *"let's just discuss, do not edit anything."* The user wants an
interactive elaboration phase **before** `/hex-plan` or `/hex-architect` —
one that pushes back on design ideas, checks them against the state of the
art, researches disputed facts in the background while the conversation
continues, and leaves something durable behind. The full intent, the
requirements, the working decisions taken with the user, and the research
index are in `.agents/discussions/hex-discuss-skill.md`; this ADR does not
restate them and treats its **Decisions** as ratified working positions
subject to adversarial validation.

Five surfaces are in scope, and they are one decision because each is
load-bearing for the others: (a) the skill, (b) a new artifact class
under `.agents/`, (c) the bundle's **first rule artifact**, (d) an input
fast-path into `/hex-architect`, (e) `hex-init` provisioning.

### The central constraint

hex's differentiator is that **the client is the runtime** — it ships
markdown and reaches every harness. A discussion mode strains that in a way
no prior hex skill has:

1. **Stance must outlive compaction.** The requirement is that the stance
   **survives at least one compaction event**, exiting only on explicit
   handoff. Compaction is the expected path on any discussion long enough to
   need a mode at all — the dossier's "50+ turns" is the illustrative shape
   of such a discussion, not the normative bar. A skill body is conversation
   content and is exactly what compaction condenses first
   (`rule-context-budgets.md`); the system prefix is architecturally exempt.
   The only grim-shippable artifact that lands in the prefix is a **rule** —
   which reaches a *minority* of clients (`rule-artifacts-grim.md`). So the
   mechanism that makes the mode durable is the one that is least portable.
2. **The shared shape does not fit.** Every hex orchestrator runs *parse args
   → classify tier → resolve overlays → single meta-plan gate → announce →
   dispatch to a tier file* (`DESIGN.md` § Shared shape). A discussion has no
   resolved config at turn zero — the spawn set is discovered *through* the
   conversation — and its whole premise is that nothing is committed, so an
   entry gate guards nothing. `protocol.md:54-58` names `hex-init` as the one
   exemption and says it "does not extend to any skill that spawns workers."
   hex-discuss spawns researchers. It does not fit the exemption as written.
3. **The drain must not fork the fold path.** `adr_0005` made
   `/hex-review`'s Fold-Back the single mechanism that writes a spec, under a
   7-step safety envelope (`archive.md § Safety envelope`). A "drain to spec"
   target is the obvious second path, and it must not be built.
4. **The frozen config vocabulary has no room.** `config.md`'s six Tier A
   keys froze at the **first `grim release`** — `v0.1.0`, 2026-07-23 — and
   `tiers.<skill>` is closed to the four orchestrators (`config.md:92-94`). Any hex-discuss knob must ride an
   existing key or be a DESIGN.md-gated new mechanism.

## Decision Drivers

- **Stance durability** — the stance must survive **at least one compaction
  event**; that requirement is the reason the feature exists, and a mode that
  silently lapses is worse than no mode.
- **Portability** — the moat. A capability that only works on one harness
  splits the bundle's behavior in two.
- **Constitution fit** — deviations are permitted, unstated ones are not.
- **Least surface** — one skill, one 10-line rule, one directory, one
  template. No config key, no tiers, no hook, no new worker role.
- **Handoff fidelity** — all four drain targets must route through
  mechanisms that already exist, never through new ones.

## Industry Context & Research

**Research artifacts** (all in `.agents/research/`, all
`Expires: 2027-02-28`): `discuss-skills-field.md`,
`discuss-mode-mechanics.md`, `discuss-grill-mechanics.md`, the two-wave
vendor sweep (`discuss-{anthropic,openai,github,practitioners,vendors}.md`),
`rule-context-budgets.md`, `rule-artifacts-grim.md`,
`dossier-fastpath-precedent.md`, `discuss-competitive-delta.md`.

**Key insight — the mechanism is greenfield, the consent rule is not.**
`discuss-skills-field.md` finds **no shipped prior art anywhere** for
background research running while a discussion continues. But
`discuss-competitive-delta.md` finds OpenSpec independently hardened the
*consent* boundary in v1.9.0–v1.11.0 — "answering its own clarifying
questions no longer reads as consent," now requiring a separate explicit
yes before any write — landing on the same rule agent-skills' `interview-me`
reached (restate-then-confirm). Two unrelated maintainer teams converging
inside one research window is **field consensus on the rule**, not a design
choice to litigate. What is adopted is the *rule* — a soft confirmation is
not consent; a separate explicit yes is required. The wording stays hex's
own and is deliberately varied between discussions rather than recited
(C-710).

**Trending approaches.** The SDD category is growing, not consolidating —
spec-kit 132k★, superpowers 279k★ (in Anthropic's official marketplace since
2026-01-15), OpenSpec 66.6k★, ruflo 69.6k★. Swarm orchestrators are racing on
*cross-agent execution portability*, leaving interview and pushback mechanics
undeveloped (ruflo's specification phase is a binary `non_interactive` flag).
A dedicated discussion-mode plugin niche exists and is **unclaimed** —
claude-brainstorm proves demand at 13★ and stale since Jan 2026.
Positioning follows `discuss-competitive-delta.md`'s recommendation:
**OpenSpec's zero-artifact discussion rigor, packaged as a portable
cross-agent skill** — interop with superpowers rather than compete on
lifecycle breadth.

**Second key insight — trust the dossier, weight the review up.**
`dossier-fastpath-precedent.md` finds no tool pairs "skip re-derivation" with
"keep review mandatory": spec-kit re-derives everything and ignores
provenance; OpenSpec refuses to persist anything; BMAD trusts the PRD
wholesale but its validation is optional. The transferable finding is
ASDLC.io's: **two-party consensus is a bias signal, not a safety one** — the
same assumptions that produced the defect produce the blind spot in the
review. This inverts the naive fast-path: Discover *shrinks*, Research skips
*per-axis*, and adversarial Review is weighted **up** (C-723…C-726).

**Third — the budget is instruction count, not tokens.** Perfect-compliance
collapses to zero by ~80 simultaneous system-prompt instructions
([arXiv 2607.19257](https://arxiv.org/abs/2607.19257)); compliance falls
96%→~20% from 1 to 20 stacked instructions, with **format and length
constraints collapsing hardest and lexical ones surviving best**
([arXiv 2608.02639](https://arxiv.org/html/2608.02639)). Separately, and
independently of length, **conditional/gated instructions are a known weak
point** — "take this stance only when X" fails as a *triggering* error
distinct from an execution error (`rule-context-budgets.md:50-57`).
Caching makes repeat turns near-free, so the rule's cost is not dollars —
it is permanent competition for a fixed attention budget on every unrelated
task. This is why the rule is ≤10 lines and why its one predicate is a
**file check, not a remembered mode flag** (C-718).

## Considered Options

Five options for how the mode acquires durable stance, a durable artifact,
and a handoff, all within grim's shippable surface.

### Option A — Skill + unscoped rule + discussion artifact, gate at the exit (recommended)

**Description:** a `hex-discuss` skill carries the full protocol; a ~10-line
unscoped grim rule (`hex-state`, bundle-generic) carries the
file-anchored-state frame, the mode's no-edit line, and the re-anchor duty
after compaction; `.agents/discussions/<slug>.md` carries
the durable state; the single approval gate is the **restate-gate at the
drain**, not an entry meta-plan gate.

| Pros | Cons |
|------|------|
| The one mechanism (a prefix-resident rule) that survives compaction on the clients that host one | Two `DESIGN.md` amendments + two `protocol.md` deviations |
| Rule is explicitly non-load-bearing — the skill is complete without it, so no behavior split | Stance durability degrades on Codex/Gemini/Zed/Amp to skill-body-plus-artifact |
| Zero config keys, zero tiers, zero new worker roles; all four drain targets route through existing mechanisms | A new install surface (`[rules]` table) the bundle has never shipped |

### Option B — Skill only, no rule

**Description:** the whole protocol in one skill; stance held by the skill
body; artifact and drain as in A.

| Pros | Cons |
|------|------|
| One client-uniform behavior; no new artifact kind, no `[rules]` table, one fewer amendment | **Fails the requirement the feature exists for**: the body is conversation content, condensed first at compaction, so the stance lapses on exactly the long discussions that need it |
| Laziest option that ships anything | "Re-read the skill" is itself an instruction living in the region that just got summarized — and re-invoking an already-loaded skill returns "already loaded", not a fresh copy (`discuss-mode-mechanics.md`), so recovery means re-reading the artifact or opening a fresh session |

### Option C — Option A plus a hex-init-provisioned `UserPromptSubmit` hook

**Description:** A, plus `hex-init` runtime-writes `.claude/settings.json`
with a two-gate off-by-default consent shape mirroring grim's own.

| Pros | Cons |
|------|------|
| Strongest enforcement — the stance is checked by the harness, not recalled by a model | Claude-only. The bundle's moat is that it ships markdown and reaches every client; this is the first client-specific enforcement path |
| The consent shape is already designed upstream and proven | Builds a `settings.json` writer whose replacement is **already implemented** — grim's `hook` kind is ADR-Accepted 2026-08-16, awaiting a merge (`rule-artifacts-grim.md` finding 5) |
| | Hard-blocking a *conversational* stance repeats native plan mode's failure: it also blocks the scoped writes the mode needs |

### Option D — Fold discussion into `/hex-architect` as an interactive front-phase

**Description:** no new skill, no rule, no artifact. `--discuss` adds an
interactive Phase 0 to hex-architect.

| Pros | Cons |
|------|------|
| Zero new install surface; reuses the architect's research and review machinery outright | Breaks the single-gate rule head-on — a mid-flow interactive phase inside a spawning orchestrator is precisely what `protocol.md:50-58` forbids, and it would strand the swarm it launches |
| | An architect run must produce a design: the `dropped` and `→ plan` terminal states become unreachable, and `dropped` is a **valid success** (field evidence: discussions legitimately talk users out of building) |

### Option E — Ephemeral discussion, no artifact (OpenSpec `explore` parity)

**Description:** pure conversation, zero writes, handoff by pasting context
into the next command.

| Pros | Cons |
|------|------|
| Zero write surface, zero deviations beyond the shape, cheapest to ship and to reason about | No cross-session re-entry and no fresh-session handoff — Anthropic's own guidance recommends the latter, and there is nothing for a fast-path to consume |
| Matches the closest philosophical peer | OpenSpec is the **anti**-precedent here: it declined persistence *because* it never crosses a session boundary (`dossier-fastpath-precedent.md` finding 2). hex-discuss must |

## Decision Outcome

**Chosen Option:** Option A — skill + unscoped rule + discussion artifact,
with the single approval gate relocated to the drain.

**Rationale:** Option B is the honest lazy runner-up and it loses on exactly
one axis — the one the feature exists for. Compaction is not an edge case for
a discussion long enough to need a mode, it is the expected path, and "the
skill body will remind itself" is a promise made by text that has already
been summarized — and one the harness cannot keep, since re-invoking a loaded
skill yields "already loaded" rather than a fresh copy. A
prefix-resident rule is the only grim-shippable answer, so the question
becomes how to buy durability without splitting behavior across clients. The
answer is to make the rule **strictly a hardening** (C-719): the skill is
complete without it, so a client that hosts no rule file loses persistence
convenience, never correctness. That single constraint converts the
portability objection from a fork into a graceful degradation and is what
lets A keep B's portability score while paying B's failing axis.

C and D are rejected on structure, not on cost. C buys enforcement by
building a Claude-only runtime writer for a capability grim has already
designed, implemented, and Accepted — the revisit trigger is a merge, not a
design round (C-730). D collapses because hex-architect's own contract makes
it impossible: five phases, one entry gate, and an obligation to produce a
design. E is rejected because the dossier's own resolved research conflict —
Anthropic's fresh-session handoff versus grill-me's Q&A-*is*-the-context — is
reconciled only by an artifact good enough to make a fresh session lossless.
That conflict is the argument for the artifact's existence.

**The dossier's Decisions, adversarially validated.** Six of seven hold and
are adopted without re-derivation. One is wrong and is overturned:

> **Overturned — "the architect fast-path skips its own Design phase."**
> hex-architect's Design phase *is* ADR authoring (`tier-medium.md` Phase 4:
> "Reason & Design — architect worker, ADR mandatory"). There is no separate
> authoring step for it to skip *into*. Skipping Design would skip the
> trade-off matrix, the NFR coverage, and the component contracts — the ADR's
> entire required content (`hex-architect/SKILL.md` § Required content) —
> which a discussion artifact by its own contract does **not** carry
> (requirements stay provisional prose, no `C-`/`S-` IDs). The fast-path is
> **trust-scoped, not phase-scoped**: Discover shrinks, Research skips
> per-axis, **Design never skips**, and Review is weighted *up*
> (C-723…C-726).

### The dossier's docket, answered

The eight open questions handed to the architect, each resolved and where.

| # | Docket item | Answer |
|---|---|---|
| 1 | Rule-vs-skill text boundary | Rule = the bundle-generic **`hex-state`**: file-anchored-state frame + one concrete line per shipped mode + re-anchor duty, ≤10 lines, one **file-checkable** predicate; entry stays the skill's description match, and everything else lives in the skill body, which costs zero until matched. **C-718**, **C-719** |
| 2 | First rule artifact — packaging and install surface | One unscoped `.md`, catalog keys at **top level** (the Asymmetry), new `[rules]` table + `publish.toml` entry, no first-of-kind constraint; reach documented once, in `hex-discuss/references/reach.md`. **C-720**, **C-721**, **C-731** |
| 3 | Tone rule vs the announce-block convention | **Both**: DESIGN.md amendment 1 scopes the announce block with the gate, and the conforming quiet form is **one line per mandated disclosure** — no block, but nothing mandatory dropped. **C-712** |
| 4 | Architect fast-path shape | Trust-scoped, no new flag: input is a `handed-off → architect` artifact (any other `State` refused) and it **floors the tier to medium**; Discover shrinks to a claim diff with a stale-base halt; Research skips per-axis; **Design never skips** (working decision overturned); Review weighted up. **C-722…C-726** |
| 5 | On-demand research expansion via capability classes | **No new mechanism.** `researcher` × ≤12, user-selected lanes, orchestrator-side dedup, batched under the existing cap with the existing batch-split disclosure. No coordinator, no nested spawn, no new class. **C-707** |
| 6 | No-tiers deviation | Ratified as a **DESIGN.md amendment**, not an exemption: the shared shape scopes to the four orchestrators and hex-discuss keeps exactly one **approval** gate, relocated to the drain. `protocol.md`'s exemption sentence gains a second named member with its own ground. **C-701**, **C-710** |
| 7 | Optional hook provisioning by hex-init | **Declined** for this release with a named revisit trigger — grim's `hook` kind is Accepted and implemented but unreleased; hex ships no client-specific enforcement. **C-730** |
| 8 | Contract range | **C-701…C-731**, scenarios **S-701…S-716**; `adr_0007` holds `C-6xx`, verified free. |

### Weighted scoring

Criteria and weights follow the Decision Drivers; scores 0–100, higher is
better.

| Option | Stance durability ×30 | Portability ×25 | Constitution fit ×20 | Least surface ×15 | Handoff fidelity ×10 | **Total** |
|---|---|---|---|---|---|---|
| **A — skill + rule + artifact, exit gate** (durability scored on a rule-hosting client) | 90 | 85 | 70 | 70 | 95 | **82.3** |
| A — same design, durability blended across all clients (90 on the 4 rule-hosting of C-721's ten, 35 elsewhere — degraded counted as absent) | 57 | 85 | 70 | 70 | 95 | 72.4 |
| B — skill only | 35 | 100 | 80 | 90 | 95 | 74.5 |
| E — ephemeral, no artifact | 20 | 100 | 90 | 95 | 25 | 65.8 |
| C — A + provisioned hook | 95 | 40 | 45 | 30 | 95 | 61.5 |
| D — folded into hex-architect | 30 | 100 | 25 | 85 | 40 | 55.8 |

**Two readings, and A does not win both.** The first A row scores durability
where the mechanism actually exists — on a client that hosts a rule file. The
second blends it across the ten clients in the C-721 reach table, and on *that*
reading A (72.4) **loses to B** (74.5): the rule buys nothing on the four
clients with no ownable rule path and little on the two where it lands
degraded, while A pays its amendments and its second install surface
everywhere. The break-even is a **rule-hosting share above
53%**; below that, B is the better design.

The choice therefore rests on the deployment population, not on the client
list. `.agents/product.md` names the users as Michael on Claude Code; the
dossier adds the coworkers now adopting the hex skills, but **does not name
their client** — that they also run Claude Code is a stated assumption, not
a sourced fact. On product.md's named population plus that assumption the
rule-hosting share of hex's actual consumers today is **100%**, so the
native-client row is the one that describes them, and A is chosen on it with
the client-weighted row left in the table as the standing cost of being wrong
about that.

Two re-open triggers follow, and both are stated rather than discovered
later. If the durability requirement were dropped — if the stance no longer
had to survive a compaction — B wins outright on either reading. And **if the
consumer population diversifies materially beyond rule-hosting clients, this
ADR should be re-opened**: the client-weighted row becomes the operative one
and the A/B ordering inverts. Both are why C-719 keeps the rule optional:
**B is A's own degraded mode**, reached automatically on any client without a
rule surface, not a separate design.

### Consequences

**Positive:**
- A discussion becomes a re-enterable, handoff-quality artifact instead of
  scrollback, and the Anthropic-vs-grill-me handoff conflict is reconciled.
- The bundle gains a rule surface it can reuse later at zero marginal design
  cost — the `[rules]` table has no first-of-kind constraint.
- The single-gate *count* is preserved while the gate moves to where the
  irreversible act actually happens; OpenSpec's hardened consent *rule* is
  adopted as settled rather than reinvented, while its phrasing stays hex's
  own.
- No config key is added, so the frozen v1 vocabulary stays frozen.

**Negative:**
- Stance persistence is a two-class capability: native on
  Claude/Cursor/Copilot/Kiro, degraded on OpenCode/Junie, absent on
  Codex/Gemini/Zed/Amp. C-719 bounds the blast radius to convenience.
- A new skill and a new artifact class enlarge what `hex-init` audits
  and what a new adopter must understand.

**Risks:**
- **The rule is ignored anyway.** Conditional dormancy in always-loaded text
  is a named failure mode. Mitigation: the rule's predicate is a file check —
  an `active` discussion artifact in the discussions home that is
  **git-untracked or locally modified**, a committed unmodified copy being
  inert (the session-bound form, C-718) — not a remembered flag — the
  point being that a file predicate is **externally observable and
  correctable**: a user or a later run can look at the file and see whether
  the mode should be on, which a remembered flag never permits (C-718). The
  failure still degrades to Option B.
- **A stale dossier drains into an unearned ADR.** ~1/3 of long-horizon agent
  failures are context drift that "fails quietly." Mitigation: the stale-base
  halt at Discover (C-723) — loud, not silent.
- **Rubber-stamp review of a pre-agreed design.** Mitigation: C-726 weights
  the panel up rather than down when a dossier is present.

## Component contracts

Contracts are numbered `C-7xx`; UX scenarios `S-7xx` (`adr_0001` `C-00x`,
`adr_0002` `C-1xx`, `adr_0003` `C-2xx`, `adr_0004` `C-3xx`, `adr_0005`
`C-4xx`, `adr_0006` `C-5xx`, `adr_0007` `C-6xx`). Home names the single
definition or edit site.

### A. The skill

| ID | Contract | Home |
|---|---|---|
| **C-701** | **Identity, entry, exit.** `hex-discuss` is **a hex skill, not a fifth orchestrator**: no `classify.md`, no `overlays.md`, no `tier-*.md`, no tier vocabulary. It is entered only by explicit user invocation or the skill's own description match on a discuss request, **never self-triggered from another skill's flow** (the `hex-init` precedent), and exits only on an explicit drain (C-711) or an explicit user abort — **the user is the one who ends the interview** (C-709), never this skill. **Entry is answer-first:** the opening turn composes and emits substance — its engagement with intake slot 1 — **before anything dispatches**; the shared-contract reads that inform the reply gate the entry wave's dispatch (C-706), never the reply itself, and the mandated one-liners follow the substance as independent lines (C-712). The dispatcher/tier-file split (`DESIGN.md` § Shared shape) is **vacuous, not deviated**: it exists to dispatch to tier files, and there are none. Body budget ≤400 lines, **measured on the body — the H1 onward, frontmatter excluded**; the `references/` split budget is **two files, both authorized and both spent** — `hex-discuss/references/reach.md` (§ Reach, C-721) and `hex-discuss/references/research-lanes.md` (the researcher spawn contract, the lane catalog, and the return schema), the second authorized by the 2026-08-30 amendment, which states this new budget. **A third split needs its own amendment.** **Packaging:** frontmatter sets `claude.user-invocable: "true"` and, unlike `hex-init`, does **not** set `claude.disable-model-invocation` — `hex-init` disables it because it must never self-trigger from a description match, whereas a discuss request reaches `hex-discuss` *through* the skill's description match — model invocation — so disabling it would disable entry itself (the rule carries no triggers, C-718). | new `hex/hex-discuss/SKILL.md` |
| **C-702** | **Intake is one composite ask with three slots.** **Argument syntax:** `/hex-discuss <topic \| path \| slug>` — free text becomes intake slot 1 and is **never re-asked**; a path into the resolved discussions home, or the slug of an existing artifact, resumes that artifact (C-713). The opening turn asks exactly once, for: (1) the problem in the user's words, (2) a source-material inventory ("dump anything" — tickets, example apps, references, code), (3) the outcome shape (plan / ADR / spec / just clarity). Any subset is answerable. Slot 3 pre-sets the drain target (C-711); slot 2 seeds `## Related` and grounds every researcher prompt. A second composite intake ask is a contract violation — later gaps are design questions under C-703. | `hex-discuss/SKILL.md` |
| **C-703** | **Dual question cadence.** *Inventory* questions (facts the user simply has) batch into one composite ask. *Design* questions — anything whose answer is a choice — ship in **dependency-batched sets of ≤3**, each option still carrying its own attached recommendation, and **never a numbered list outside that batch shape**. More than three pending → the three highest-priority ship, the rest carry to the next batch. Never spend a question on what the artifact or the repo already answers. This **supersedes the original strictly-one-per-turn law** (2026-08-30): `discuss-skills-field.md`'s finding was against *undifferentiated* numbered lists, and the rework's own research (`discuss-ux-sota.md`, `discuss-ux-community.md`) finds a small dependency-ordered batch beats strict one-at-a-time on both turn count and answer quality. | `hex-discuss/SKILL.md` |
| **C-704** | **Chips by default, prose by exception.** A design question ships as selectable options plus a free-text escape, rendered through the client's **native structured-choice prompt where one exists** and a numbered list otherwise — stated as a capability, never as a harness tool name (`DESIGN.md` house rule). An open prose question is permitted but is the exception and is self-justifying: it is used when the option set would prejudge the answer. | `hex-discuss/SKILL.md` |
| **C-705** | **Grill ruleset — four rules, all four normative.** (a) **Rebuttal gate**: categorize user pushback as *new evidence* (update the position and state what changed) or *repeated opinion* (hold, and restate the evidence) — never concede on repetition alone. (b) **Anti-theater**: never manufacture an objection; on agreement about a decision-relevant point, name the strongest remaining counter-argument **once** and move on. (c) **Scoped elicitation**: pick **≤2** fitting techniques per thread (premortem, inversion, first-principles, force-rank) — never present a catalog. (d) **Researcher blindness**: a research prompt states the question neutrally — the evidence for and against each option on the named axis — and **never reveals which side the user or the orchestrator favors**, including where the user has already stated a preference. It **binds every research prompt this skill sends, the automatic entry wave's two lanes included** (C-706), and its single carve-out is **lexically scoped to opt-in lanes** — a property of the user-opted path, never a precondition restated per lane. | `hex-discuss/SKILL.md` |
| **C-706** | **Default research gear.** At most **3 concurrent** `researcher` spawns, model class `fast-balanced` by default — the researcher's cell at every tier (`models.md`), so hex-discuss never escalates *on its own judgment*. It is **not** exempt from `models.md` rule 1: `models.overrides` is a frozen v1 config key that applies at every tier, so a project can pin `researcher` above its cell and hex-discuss will run it there. That escalation is disclosed exactly as everywhere else — via the resolved-literal-model line, printed once on the first spawn of the role (C-712). **The automatic entry wave** rides this same gear: entry dispatches two fixed lanes — codebase recon and a prior-art web scan, seeded from intake slot 1 — inside the 3-concurrent default, leaving one slot free. Dispatch is **two-path, not unconditional**: **slot 1 present** → the wave dispatches this same turn, right after the turn's substance is emitted (C-701); **slot 1 absent** → the wave defers, firing once when slot 1 lands, seeded from it. **Only an already-dispatched wave is non-repeatable**: a resume never re-fires a wave that already ran, but a discussion parked before slot 1 ever landed still gets its wave when slot 1 does. **Automatic spend never exceeds the default gear and is always announced; anything above it is user-initiated** (C-707). Spawns are **three classes**, and the trigger differs per class: **(a) the entry recon spawn** — automatic, the fixed two-lane wave; **(b) the opt-in lane spawn** — user-selected at C-707's multi-select; **(c) the disputed-fact spawn** — skill-initiated on a decision-relevant disputed fact. **Never on an opinion** binds **(a) and (c)**, as does never on a question the repo answers (read it instead). **(b) alone may target a judgment question** — the council lane: the user's own selection is the position-taking, not the researcher's, so the exception is **lexically scoped to the opt-in path** and is never restated as a per-lane precondition. Researchers are **never on the critical path**: the conversation continues while they run, and a landed result surfaces **at the next turn boundary** as a one-line aside flagged as new (C-712), never spliced mid-turn; a result that changes a live thread **feeds the next question**, and a return's `leads:` entries **join the offerable lane set** for C-707's next offer, deduplicated **first-seen-wins**. A researcher that **returns nothing useful** is folded in with no aside — there is nothing to report. A researcher that **fails to return at all** is a different event and is surfaced **once**, as a one-line transport note; a dead worker is never normalized into "no result found." | `hex-discuss/SKILL.md`; roles from `workers.md` |
| **C-707** | **Lane expansion — no new mechanism, and the multi-select replaces the two-gear offer entirely.** On-demand research is a **multi-select over research lanes**, offered **once**, immediately after the entry wave dispatches (C-706), seeded with the default lane set — `hex-discuss/references/research-lanes.md` is the catalog's normative home — with the **running spend total in the chip text**. **Skip → no re-offer** until the user asks again or a returning researcher's `leads:` entries add a new lane; the retired two-gear offer survives nowhere in shipped text. Spawns are ordinary `researcher` spawns with a **hard total cap of 12 per expansion** (`max-workers` caps concurrency, not the total), each expansion bounded by the existing effective concurrency cap `min(8, limits.max-workers)`. **A demand above 12 truncates to 12, announced once.** An expansion exceeding the concurrency cap runs in sequential batches per `protocol.md` § Worker coordination and **announces the batch split with the cap's source**. No `coordinator`, no nested spawning, no new role, no new capability class: dedup of `leads:`-fed lanes is **incremental and first-seen-wins**, and the synthesis — of lane returns, and of the council lane's N perspective seats into a single aside — is the orchestrator's **own synthesis duty**, which `protocol.md` already assigns it. Findings longer than a paragraph persist per lane as research artifacts. **The offer never blocks a conversational turn** and neither does an expansion: results land asynchronously and fold in at turn boundaries (C-706), so the hard Latency NFR holds unchanged. That moment is a **bounded, user-initiated spend confirmation, not an approval gate**: nothing strands if the user declines, no state advances if they accept, and it exists only because a 12-worker spend mid-conversation must never be silent — the counterpart rule being that automatic spend never exceeds the default gear and is always announced (C-706). **Not YAGNI:** the demand is proven, not speculative — this design's own dogfood discussion ran a user-requested 12-agent expansion mid-conversation on 2026-08-28, and the per-lane research artifacts it produced are the ones this ADR cites. | `hex-discuss/SKILL.md`; lane catalog in `hex-discuss/references/research-lanes.md` |
| **C-708** | **Write surface — scoped, split by the gate, and exhaustively enumerated.** hex-discuss writes exactly five things, and *when* is as binding as *what*. **Pre-gate** — only (i) its own discussion artifact, (ii) research artifacts in the convention-resolved research home, and (v) the `hex.md › Pointers` **staleness re-point**, made when resolving the discussions home finds that pointer stale. (ii) is pre-gate because the user mandated persistence for research, not because the design needs it there; (v) is pre-gate because verify-on-consumption repairs a stale pointer **in the same run it is found** — deferring that repair past a gate the run may never reach is exactly what `memory.md` § Staleness forbids. The re-point's single home is `memory.md` § Staleness (*Verify on consumption*); both hex-discuss (as writer) and `hex-architect` (C-722's verify-on-consumption before any refusal) reference that one home rather than restating the duty. **Post-gate**, written at the drain alongside the handoff — the drain's own header update to (i) (`State:` to its terminal value, plus the `Ratified:` line and, **where the provenance exists**, the optional `Confidence:` line, C-710), (iii) `hex.md › Memory` (discussion hand-off record, artifact index, C-711 promotion candidates) and (iv) `hex.md › Pointers` (the discussions-home row, C-727); these are the ordinary upkeep writes, deferred past the gate so nothing outside the discussion's own footprint exists before consent. It writes **no** code, **no** config, **no** plan, **no** ADR, **no** spec, and **never** `hex.md › Preferences` (user-owned). **Revert is not "delete one directory."** Undoing an abandoned pre-gate discussion means deleting the discussion file **and** the research artifacts it lists under `## Research` — the research home is shared with every other hex skill and is never removed wholesale. The two `hex.md` rows exist only after the gate and revert by deleting two lines; a pre-gate re-point repairs a row that already exists and so carries nothing to revert. **Federation:** hex-discuss sits outside the satellite halt's scope — the halt names the four orchestrators; the C-729 amendment states the non-orchestrator case explicitly (it resolves no plan and writes no plan or federation state). | `hex-discuss/SKILL.md` § Constraints |
| **C-709** | **Coverage-based stop rule — and the user is the one who ends the interview.** This skill **never offers to end the discussion**: no “shall we wrap up”, no “ready to drain”, not once, at any point in the run. Its whole affordance is **one drain-affordance sentence at entry**, said once and never repeated (C-701), naming that the user calls the drain when they are ready. The **restate-gate (C-710) is the completeness check, not a stopping heuristic**: the interview is drain-ready when the restate can be filled without a gap — **never** at a question count and never at a turn budget — and a gap the restate exposes returns to the conversation rather than pre-empting a drain the user asked for. Conversely, **no artifact obligation for a small discussion**: a question answered in a few turns drains inline with no discussion file (net of C-715's entry stub, which the inline drain deletes), per the cheap-to-skip NFR and OpenSpec's zero-artifact precedent. **It nets zero *discussion* files, not zero files:** the entry wave (C-706) may already have landed research artifacts before that drain fires, and those persist in the shared research home and are named in the terminal report. (`discuss-openai.md` is adjacent support, not the ground: it is about question *cadence* — a 1–3 question cap — and about gating the planning **tool** off "roughly the easiest 25%" of tasks, which is an argument by analogy for skipping the artifact, not a finding that extended clarification is itself an anti-pattern.) | `hex-discuss/SKILL.md` |
| **C-710** | **The restate-gate is hex-discuss's single *approval* gate, and it sits at the exit.** Before any drain the orchestrator emits a **six-part structured restate** — Outcome / User / Why now / Success / Constraint / Out of scope — and requires a **separate, explicit yes**. The restate additionally names **what has already been written** (the discussion artifact and every research artifact by path) and **what the drain will touch** (the proposed-artifact list, including C-708's two `hex.md` rows). Without that list a "separate yes" is still a yes to an unstated write set — the exact gap the consent rule exists to close. A **resumed** artifact whose `Updated:` predates this session also gets a one-line staleness note at the restate: recorded decisions may have drifted since, and the receiving claim diff (C-723) is the real check. **Answering a clarifying question is never consent, and a soft confirmation ("sounds good", "yeah ok") is not consent** — the *rule* is field consensus (OpenSpec v1.9.0–v1.11.0 + agent-skills `interview-me`; `discuss-competitive-delta.md`); the wording is hex's own and **varies naturally between discussions**, because a recited script is the fastest route to a reflex yes. Against the same fatigue: a pattern of instant unqualified yeses across discussions may be **gently flagged once**, never repeated and never made a block. The yes is **recorded in the artifact** whenever one survives the drain: the drain appends a `Ratified:` line — date and drain target — to the header, a durable, human-auditable record of the consent event; its absence on a `handed-off` artifact is a C-722 gate question, because the state header alone is mutable prose, not proof. (An inline drain leaves no artifact and no `Ratified:` line — and its outcome can never be C-722 input.) A "no" returns to the conversation with the disputed part named. Exactly **one approval gate per run**, as everywhere else in hex — C-707's **lane-expansion offer** is a bounded spend confirmation, not a second approval gate. Only the position differs: the gate sits where the irreversible act is (handing a downstream orchestrator a mandate), because at entry nothing is yet committed. | `hex-discuss/SKILL.md`; scoping in `protocol.md` § meta-plan gate |
| **C-711** | **Four drain targets, zero new write paths.** After the C-710 yes: **→ plan** emits `Next: /hex-plan "<title>, per <artifact path>"`; **→ ADR** emits `Next: /hex-architect <artifact path>` (the fast-path input, C-722). **Neither command carries a tier**: hex-discuss has no tier vocabulary, so the receiving orchestrator's own classifier resolves it (`auto`) — a tier appears only when the user named one at the restate — except `low` on the **→ ADR** target, which C-722 would refuse on arrival; the restate states the medium floor instead of emitting a dead-end command; **→ spec** emits the plan command and states that the spec is reached by `/hex-review`'s Fold-Back on the converged plan — **hex-discuss never writes a spec and never invokes a fold**, so `archive.md`'s envelope stays the only fold path; **→ project context** records the candidate convention in `hex.md › Memory` **post-gate** (C-708), where the next `/hex-init` **re-audit** picks it up and proposes it against the matching audit item, with consent (`hex-init/references/audit.md`). This is deliberately *not* `protocol.md` § Upkeep step's mechanism reused verbatim: that one routes a surfaced **preference** to `hex.md › Preferences`, whereas a durable project convention belongs in project context, which only `/hex-init` writes. hex-discuss never writes CLAUDE.md/AGENTS.md. Terminal states: `parked`, or `handed-off → plan \| architect \| context \| dropped` — a `State:` vocabulary whose **single home is the C-728 template**, which defines it while `hex-discuss/SKILL.md` and `hex-architect/SKILL.md`'s refusal table only consume it. **`dropped` is a valid success** and is reported as one, not as an abort, and carries **no `Next:` line** — nothing runs next. Every drain closes on a literal `## Discussion Complete: <topic>` block carrying three bullets: the terminal `State:`, `Written:` (every path this run touched, including the two `hex.md` rows), and `Next:` where one exists. | `hex-discuss/SKILL.md` § Handoff |
| **C-712** | **The quiet announce form.** hex-discuss prints **no announce block**. The contract is a *shape*, not a whitelist: **every disclosure the shared contracts mandate renders as one line, never as a block**, and none is repeated. Nothing mandatory is dropped — only the block is. The currently known set: (1) a research aside when a result lands (`— checked that: <one-line finding> [<source>]`); (1a) the **combined entry line**, `— discussion notes: <path> · recon: N dispatched`, printed once at entry — the stub write and the entry wave's dispatch count on **one line, never two**: a mode pitched as "don't edit anything yet" writes no file *and spawns no worker* silently; (2) a **lane expansion's** batch split with the cap's source (`protocol.md` § Worker coordination, C-707); (3) `Degraded: inline workers — no subagent spawning`, printed **once** on a client that cannot spawn, because background-research-while-discussing is the mode's differentiator and silently serializing it changes the conversation's rhythm; (4) the **resolved literal model** on the first spawn of a role — the disclosure `models.md` rule 1 mandates, carried per the one-line scoping clause Wave 1 adds to rule 1 (a skill with no announce block discloses under its declared quiet form), and where a `models.overrides` escalation becomes visible (C-706); (5) a `Limits:` line, printed once, when a `hex.md › Preferences` limit is in force; (6) the **second degraded axis when it composes** — a harness that also lacks per-spawn model override prints `Degraded: single session model — no per-spawn override; matrix advisory` as its own line, per `protocol.md`'s one-line-per-degraded-axis rule; and (7) the **one-line transport note for a researcher that failed to return**, surfaced once — C-706's mandated disclosure, and the reason a dead worker is never normalized into "no result found." A later contract that mandates a disclosure adds a line under the same rule; it never earns a block. No phase announcements, no thread-board recital, no resolved-config table — unless the user asks, which is always honored. | `hex-discuss/SKILL.md`; scoping in `DESIGN.md` § Shared shape |

### B. The discussion artifact

| ID | Contract | Home |
|---|---|---|
| **C-713** | **Home and resolution order.** Discussion artifacts resolve like every other hex artifact class: the project's **documented convention** if it names one, else `.agents/discussions/<slug>.md`. The resolved home is cached in `hex.md › Pointers` (C-727). One file per discussion; the slug is derived from the topic, stable for the discussion's life. **Every write this skill makes — the artifact and each per-lane research artifact alike — holds to `archive.md` § Containment's path conditions (C-418):** inside the resolved home, no `..` segment, never absolute. The fold-specific conditions (already-exists, git-tracked) belong to the fold and do not apply. **No silent clobber:** entry with a slug that already exists at `State: active` or `parked` **resumes** that artifact — never overwrites it; a slug colliding with a drained (`handed-off`) artifact takes a date suffix instead. | `memory.md` § Location and resolution; `hex-discuss/SKILL.md` |
| **C-714** | **Header contract and state vocabulary.** The artifact opens with exactly two required fields on one line — `State:` and `Updated:` — followed by an optional participants line. `State` ∈ `active \| parked \| handed-off → plan \| handed-off → architect \| handed-off → context \| handed-off → dropped` — a vocabulary whose **single home is this template's header contract**; every consumer that enumerates it (C-711's terminal states, C-722's out-of-vocabulary `Fix:` line) carries a copy for its message's sake and tracks the template whenever it changes. `Updated` is the fallback staleness anchor for an untracked artifact (C-723). Two further lines are defined. A `Ratified:` line — date and drain target — is **written by the drain itself** (C-710) and is what C-722 corroborates the `handed-off` state against. And an **optional** `Confidence:` provenance line naming who ratified the decisions and which research vintages back them — filled by the drain **where that provenance exists**, never manufactured — the one thing a receiving orchestrator cannot reconstruct from the body, and the gap `dossier-fastpath-precedent.md` identifies as worth being early on. No other header field is required, and **no schema-version marker** — house rule. | `hex-init/assets/templates/discussion.md` |
| **C-715** | **Lazy materialization, with one declared exception.** **The exception:** mode entry **on a new slug** writes a **header-only stub** — `State: active` plus `Updated:`, nothing else; entry that resumes an existing `active` or `parked` artifact (C-713) opens it and **never re-stubs**, but does refresh the header — a fresh `Updated:` **always**, plus `State:` back to `active` when resuming from `parked`. That refresh is a header update, not a re-stub, and it **re-arms C-718's stance** for the resumed conversation; a later abort returns the artifact to `parked`, which releases it again. It has to: C-718's rule predicate is a file check, and a predicate needs a referent, so a mode with no file on disk is a mode the rule can never see. The automatic entry wave (C-706) **reaffirms the exception rather than weakening it**: the wave dispatches on the entry turn, so content is imminent — the first landed result materializes `## Research` — and the stub is what **arms C-718's stance from the first turn**, before any result exists to materialize a section with. **Everything below the header stays lazy.** A section appears on its first content — the first of a research result landing, a captured requirement, or the user saying "capture" — and **an empty section is never scaffolded**. A small discussion that drains inline **deletes its own stub** at the drain, so C-709's no-obligation clause still nets **zero *discussion* files** — research artifacts the entry wave landed persist in the shared research home and are listed in the terminal report. The full menu — Intent · Requirements · Decisions · Threads · Research · Related · Open questions · Verification — is documented in exactly one place, the template; section order is fixed, presence is not. `hex-discuss/SKILL.md` **references the template by repo path and never restates the menu** (the same sibling-file read `hex-execute` already does for `../hex-init/assets/templates/plan.md`), and carries a **one-line fallback naming only the C-714 header contract** for a project where `/hex-init` never ran and no template exists. | `hex-discuss/SKILL.md`; `hex-init/assets/templates/discussion.md` |
| **C-716** | **No `C-`/`S-` IDs in a discussion artifact — a hard prohibition, not a style note.** Requirements stay provisional prose. `protocol.md` § Traceability IDs makes IDs originate in the spec when one exists and be carried into the plan unchanged; a second origin would collide with the fold-back join key `archive.md` depends on. An orchestrator consuming a discussion **assigns** IDs; it never inherits them. | `protocol.md` § Traceability IDs (one added sentence); `hex-discuss/SKILL.md` |
| **C-717** | **Drain-readiness quality bar.** At the C-710 gate the artifact must be: self-contained (a fresh session needs no access to the source conversation), name the files and interfaces it touches, state what is out of scope, carry unresolved points under `## Open questions`, and end with a `## Verification` section naming how the eventual work is checked. **Every path the artifact names is repo-root-relative** (`.agents/adrs/…`, `hex/hex-core/…`) — C-723's claim diff resolves paths mechanically, and a path relative to wherever its author happened to be standing is not resolvable by a later reader. `## Open questions` are **carried, not blocking** — they become the receiving orchestrator's docket, and a receiving orchestrator that leaves one unanswered is a review finding, not a discuss defect. Those entries **may** carry the house clarification marker — `NEEDS CLARIFICATION` in square brackets with the question, paired with a `Recommended: <answer> — <reason>` line, exactly the shape `hex-init`'s plan and spec templates already define — so a receiving orchestrator's gate presents them natively instead of re-deriving them from prose. This does not contradict C-703/C-704's mid-conversation cadence: a question asked *live* is answered by the person in the room, while a marker is a question **handed forward** to a gate its asker will not attend — a different interaction class, and so a different shape. | `hex-init/assets/templates/discussion.md`; checked at C-710 |

### C. The rule

| ID | Contract | Home |
|---|---|---|
| **C-718** | **Rule content contract — ≤10 lines, lexical, file-predicated, bundle-generic.** The rule is **`hex-state`** — the bundle's single always-on artifact, and its concern is not discussion but **re-anchoring from file state after context loss**. It carries exactly three things: the generic frame (*hex state lives in files, never in conversation memory* — locations via `hex.md › Pointers`); **one concrete line per shipped mode** — today exactly one, and its predicate is **session-bound, not repo-wide**: **any** discussion artifact at `State: active` in the discussions home (resolved C-713-faithfully — *documented convention via `hex.md › Pointers`, else `.agents/discussions/`*) **that is git-untracked or locally modified** → no code or config edits; re-read that artifact and the `hex-discuss` skill file before acting. **A committed, unmodified copy is another session's in-flight discussion — inert**, so a colleague's landed discussion never freezes this working tree. `Any` is a **scan of the home, not a first match** — one armed artifact anywhere in it fires the stance. The negative is cheap: **no discussions home on disk means nothing to check**, and that negative holds until a hex skill runs. Third, the re-anchor duty (*after compaction, re-anchor from these files*). **Entry is not its job**: a discuss request reaches `hex-discuss` through the skill's own description match, so the rule carries no trigger phrases — and a future hex mode (a milestone loop, a resumable execution) adds exactly **one concrete line via its own ADR**, never prose or protocol, with the ≤10-line cap re-examined at that ADR rather than silently exceeded. Its predicate stays **externally checkable** — the mode's state file (C-715's entry stub is the discussion referent) together with that file's git status, never a remembered flag: conditional dormancy in already-loaded text is the failure mode the instruction-stacking research names, and a file check is **observable and correctable** — a human or a later run can open the file and see whether the mode should be on. **Evaluation point:** checked **before any turn that would otherwise edit code or config** — not on every turn, not once at load. No examples, no protocol, no edge cases — with **exactly one carve-out**: a single correction clause naming how a stale or abandoned `active` artifact is released (park it — `State: parked`), because a predicate whose whole justification is that it is *correctable* must say how it is corrected — **and no reach table** (that is C-721's, and it lives with the skill, in `hex-discuss/references/reach.md`). Rules carry **no `description` field** — grim derives the catalog line from the first heading or first non-empty line, so the opening line must carry meaning. | new `hex/hex-state.md` |
| **C-719** | **The rule is a hardening, never a precondition — the contract that keeps behavior unsplit.** `hex-discuss` must be complete and correct with the rule absent. A client that hosts no ownable rule file loses *persistence convenience* — the stance may lapse after compaction, and recovery is **re-reading the discussion artifact — whose header carries the *state*, not the stance — plus `hex-discuss/SKILL.md` itself and, where the rule landed, its `hex-state` line**, or **opening a fresh session**, never re-invoking the skill, which returns "already loaded" rather than a fresh copy (`discuss-mode-mechanics.md`) — never *capability*: intake, cadence, chips, grill, research, artifact, gate, and drain are all skill-body behavior. No hex file may make a rule's presence a condition of any other behavior. Option B is therefore not a rejected alternative but **hex-discuss's own degraded mode**, reached automatically. | `hex-discuss/SKILL.md` § Constraints; `hex-state.md` |
| **C-720** | **Packaging.** One `.md` file at `hex/hex-state.md`, **no `paths:` frontmatter** (absent = always active). Catalog keys `summary` / `keywords` / `license` / `repository` sit at the **top level** of frontmatter — *not* nested under `metadata:`, the inverse of the skill convention ("the Asymmetry"); `metadata:` carries vendor-namespaced keys only. Wiring: a new `[rules]` table in `hex/hex.toml` binding `"hex-state" = "./hex-state:latest"` (deployment-relative, no file extension — the reference names an OCI repo), and a `[rules."hex-state"]` entry in `hex/publish.toml` with `path = "hex-state.md"`. Both use **quoted keys**, matching the convention `hex.toml` and `publish.toml` already follow for every existing member. No first-of-kind constraint exists; publish order is members-before-bundle, enforced by grim's fixed kind order. | `hex/hex-state.md`; `hex/hex.toml`; `hex/publish.toml` |
| **C-721** | **Declared per-client reach — documented with the skill, not in the rule.** The reach table's single documentation site is **`hex-discuss/references/reach.md`**, reached from `SKILL.md` § Constraints by one link (retargeted from a `## Reach` subsection of `SKILL.md` itself; see the 2026-08-29 changelog). It cannot live in the rule body: C-718 caps that at three things, and a reach table is neither trigger, stance, nor pointer — every line of it would be permanent instruction budget spent on all clients to describe the clients. The table is **derived from grim's per-client transform table, never authored independently**, and is **exemplary for the ten clients it lists**: **native** on Claude Code (`.claude/rules/hex-state.md`, natively discovered and reloaded), Cursor (`alwaysApply: true`), Copilot (`.github/instructions/`, global `~/.copilot/instructions/`) and Kiro (`inclusion: always`); **degraded** on OpenCode (frontmatter stripped, body registered as a managed always-on glob) and Junie (project-scope only, no per-file activation key); **absent** on clients with no ownable on-disk rule path (Codex, Gemini, Zed, Amp). **Any grim client not listed defaults to absent-or-degraded per grim's transform table**, which stays the authority — so the table informs a reader without claiming to be exhaustive, and a grim client added later does not silently make it false. The table is verified against grim's behavior at authoring and **re-verified at each grim minor**. | `hex/hex-discuss/references/reach.md` |

### D. The `/hex-architect` fast path

| ID | Contract | Home |
|---|---|---|
| **C-722** | **Input contract — no new flag, plus a tier floor.** The fast path engages iff `/hex-architect`'s `<decision>` argument names a **readable file inside the resolved discussions home** that carries the C-714 header. The path must **canonicalize — symlinks resolved — to a location inside the repository root and inside that home**; a path resolving outside either is refused. The discussions-home pointer itself is **verified on consumption** per `memory.md` and re-pointed on drift *before* any refusal is issued (C-713, C-727) — a stale pointer must not make a valid artifact unreachable. And the trust the state header carries is bounded by construction: the header is prose, so C-722 corroborates it against C-710's `Ratified:` line (missing → gate question), C-723 verifies every repo claim, C-726 weights review up, and the architect's **own meta-plan gate still blocks before any worker launches** — a manufactured `handed-off` state reaches a human gate before anything runs. Anything else is ordinary free text and every phase runs unchanged. **Reading the value is header-anchored:** the `State:` value is taken from a **line-initial `State:` above the first `##`** — never a match anywhere in the body — as the text between it and the **first field separator** (`·`, `&nbsp;`, or end of line), trimmed, then matched **exactly**. Both halves carry weight: a whole-line read would fail closed on the shipped template's valid two-field header (`State: <value> · Updated: <date>`), and a substring read would accept `parked (was handed-off → architect)`. **Only `State: handed-off → architect` is accepted** — every other state is refused, never fast-pathed, under one shared `Error:` and **exactly one** `Fix:` — the line the state selects. `Error: <path> is State: <s> — a discussion is fast-path input only at 'handed-off → architect'.` Then, for `handed-off → plan`: `Fix: this discussion's target is /hex-plan — run that, or paste the decision as free text.` For `handed-off → dropped`: `Fix: this discussion ratified not building — a new /hex-discuss "<topic>" revisits it — the dropped artifact stays dropped — or paste the decision as free text.` For `handed-off → context`: `Fix: this discussion's outcome was promoted to project context — run /hex-init to adopt it, or paste the decision as free text.` For `active` or `parked`: `Fix: resume it with /hex-discuss "<topic>" and drain it to → architect, or paste the decision as free text.` And for a `State:` line whose value is not in the C-714 vocabulary at all — an unedited seeded template header, a hand-typed value — a fifth branch refuses like the others rather than falling through to free text: `Fix: set State: to one of active, parked, handed-off → plan, handed-off → architect, handed-off → context, handed-off → dropped — or paste the decision as free text.` The C-710 yes is what makes the state `handed-off`, so the consent gate and the trust gate are the same event. **Tier floor:** a dossier input **floors the tier to `medium`**, because C-723…C-726's compensating controls are homed in `tier-medium.md` and `tier-high.md` only — a `low` run has nowhere to put the claim diff, the per-axis skip, or the weighted-up review, and would take the fast path's discount without paying its price. A classifier result of `low` is **promoted to medium and announced**; an explicit user `low` flag is **refused**: `Error: tier low cannot take a discussion dossier — the safeguards that make the fast path safe only exist at medium and high (claim diff, per-axis research skip, weighted-up review).` / `Fix: re-run as /hex-architect medium "<decision>" (or high), or pass the decision as free text for an ordinary low run.` **A path-shaped `<decision>` that does not engage is never refused** — it runs as ordinary free text, disclosed once before the run proceeds with a `Note:` naming the condition that failed (not readable / not under the discussions home / no `State:`/`Updated:` header) and a `Fix:` line offering a re-run with the corrected path. | `hex-architect/SKILL.md` § Argument syntax |
| **C-723** | **Discover shrinks to a claim diff, with a loud stale-base halt.** With a dossier, Phase 1 does **not** launch the `architecture-explorer` for ground the dossier already covers. It instead runs a bounded **claim diff** over every repo-root-relative path the artifact names (C-717), delegated to the same `architecture-explorer` worker rather than read into the orchestrator's own context — the fast path *relocates* Discover's reads, it does not promote them into the conversation. **Containment first, and it reaches every path the dossier names, not just the dossier's own.** Each named path is **canonicalized — symlinks resolved — immediately before it is read**, and must land **inside the repository root**; the check and the read use that one canonical path, so nothing swaps between them. It is the same canonicalize-then-read discipline C-722 applies to the dossier's own path, against the repository root alone — the discussions home bounds the dossier, never what the dossier points at, which is repo-root-relative by contract. **Two failure modes, deliberately not the same event.** (a) A path that is unresolvable *and* absent from the repo's history is an **author error**, not stale ground: it is carried into the drafted ADR's `## Open questions` as a **`[NEEDS CLARIFICATION]` marker** — `[NEEDS CLARIFICATION: "<path>" names nothing this repo has ever had — typo, planned file, or another repo's path?]` — under that section's hard cap of **3** (markers past the cap surface in the handoff instead), and is **never asked live and never halts**: Phase 1 runs *after* the meta-plan gate, so there is no live gate left to ask at, and C-717 prescribes the marker for exactly this class — a question handed forward to a gate its asker will not attend. Halting on a typo would teach users to route around the guard. **A path whose canonical target escapes the repository root takes that same author-error branch — never read — under its own marker text:** `[NEEDS CLARIFICATION: "<path>" resolves outside this repository — typo, symlink, or another repo's path?]`. (b) A path that resolved when the artifact was written and is gone or changed since the staleness anchor (below) is a genuine **stale base**: deleted **halts at the gate** with an `Error:`/`Fix:` pair naming the path; changed is **announced as changed and re-read**, never silently trusted. Git history is what makes the two decidable — absence from history versus deletion after the staleness anchor. And the anchor is **derived, not asserted**: for a git-tracked artifact the anchor is its **last-commit date**, read from history; the self-authored `Updated:` line is the fallback for an untracked file, and a disagreement between the two is announced. Ground the dossier does *not* cover is explored normally. This reuses the stale-base-guard shape rated **Adopt** in `openspec-framework-analysis.md` — an older artifact (2026-07-20, `Expires: 2027-01-31`), cited for the guard's *shape*, which is structural, and not for any version-specific claim about OpenSpec. The failure mode it exists for is confident reasoning from outdated ground truth, which fails quietly by default. Discover **shrinks; it never disappears** — the skipped-discovery failure ("a missing migration, an undocumented dependency, a function called from three places") is the most commonly skipped and most underrated checkpoint. **Governing echo rule, stated once in `hex-architect/SKILL.md` and never restated at the sites that use it:** every echo of dossier-controlled text — in a message or in an authored file alike — is **interpolated quoted, truncated with `…` past 120 characters, and never allowed to break its own line**. It governs **every placeholder in `SKILL.md` and the tier files that interpolates dossier-trust-class text** — today `<path>`, `<canonical>`, `<s>`, `<artifact>`, `<anchor>`, `<topic>`, and `<date>` — so both marker texts above, the stale-base `Error:`/`Fix:` pair, and C-724's skip announcement are bounded by construction. | `hex-architect/tier-medium.md` Phase 1; `hex-architect/tier-high.md` Phase 1; echo rule in `hex-architect/SKILL.md` |
| **C-724** | **Research skips per axis, never wholesale.** An axis is skipped **only** when the dossier cites at least one source for it **and** that source's research artifact is unexpired; `Expires:` is read from the cited artifact **on disk**, never from the dossier's prose about it, and a cited artifact that is missing, unreadable, or whose canonical target escapes the repository root (C-723's containment) is **no evidence at all** — that axis runs normally. **Which axis a citation covers is read from that same artifact, never inferred from the dossier's prose**: the dossier's `## Research` section is a pathlist with no axis label, so attribution comes from the header the `Expires:` read already opened — the artifact's **topic (title) line**, the one field every artifact carries, as the **primary match**, with **`Triggered by:` and `Domain:` as corroborating evidence where present**. **Neither absence is a disqualifier**: most live artifacts carry a compact header rather than the template's full `## Metadata` block, and `Domain:` is in any case a subject-area taxonomy, orthogonal to `classify.md`'s axis catalog. An artifact whose header matches **nothing** about the selected axis is **no evidence** for it — that axis runs normally; prose inference is never the discount's basis. Those header fields have **one home**: the header contract in `hex-init/assets/templates/research.md` — its **title line** and its **`## Metadata` block** (the title line sits above `## Metadata`, which carries only `Date:`/`Domain:`/`Triggered by:`/`Expires:`) — and **the producer is bound to that same home** — `hex-discuss` writes each per-lane research artifact against that header contract, so artifacts authored there carry the corroborating fields this predicate reads. The skip is announced with its source (`Research: <axis> skipped — dossier cites <artifact> (Expires <date>)`). An axis with no cited source, or one whose cited artifact has expired, runs normally. A dossier covering every selected axis may legitimately resolve to zero researchers — announced, never silent. | `hex-architect/tier-medium.md` Phase 2; `tier-high.md` Phase 2; producer clause in `hex-discuss/SKILL.md` § Conversation |
| **C-725** | **Design never skips — the overturned working decision.** Phase 4 "Reason & Design" runs in full for every input form. It **is** the ADR-authoring phase; a discussion artifact carries provisional prose and no `C-`/`S-` IDs (C-716) and therefore supplies none of the ADR's required content — component contracts, NFR coverage, the weighted trade-off matrix. The dossier is an *input* to the architect worker (alongside the claim diff and the surviving research), never a substitute for it. | `hex-architect/SKILL.md` § Required content (one added sentence) |
| **C-726** | **Review is weighted up when a dossier is present.** Two changes, both minimal: the `reviewer` (focus `quality`, adversarial) prompt gains one mandatory duty — **steelman against the dossier's own `## Decisions`, treating two-party agreement as unexamined rather than as evidence** — and the adversary gate defaults **on** for a dossier input (today it is auto-on only for one-way-door signals). Rationale, from every source surveyed: pre-existing agreement is a bias signal the independent gate exists to catch, not grounds to relax it; same-session self-review is structurally blind. Fast-pathing is a **rebalancing**, not a discount: what Discover and Research stop paying, Review pays. | `hex-architect/tier-medium.md` Phase 5; `tier-high.md` Review phase |

### E. Provisioning and wiring

| ID | Contract | Home |
|---|---|---|
| **C-727** | **`hex-init` audit item and Pointers row.** A **conditional** audit item, in the shape of the existing spec-home sub-check: asked only when a discussion artifact already exists or the user opts in — never asked of a project that has never discussed anything. On a hit, record one `hex.md › Pointers` row following the Spec-home / Worktrees pattern: ``- Discussions: `<home>` — pre-plan discussion artifacts (/hex-discuss).`` — `<home>` being the location the user consented to, `.agents/discussions/` only where the last resort was taken. **Seed offer, conditional and separately consented:** when the resolved home is **empty**, offer to copy the C-728 template to `<home>/_template.md`, **copy-only-if-absent**, saying in the offer that the underscore prefix marks the file as **never a discussion**, so nothing scanning the home for a live one picks it up. A non-empty home is never seeded. Verify-on-consumption and the re-audit both apply unchanged; no new staleness mechanism. | `hex-init/references/audit.md`; `hex-init/SKILL.md` Step 1/2 |
| **C-728** | **A fifth shipped template.** `hex-init/assets/templates/discussion.md` documents the C-715 section menu and the C-714 header — including the drain-written `Ratified:` line and the optional `Confidence:` provenance line, the latter shown *as* optional so an author sees it exists without being obliged to fill it — joins the Step-3 copy set, and is **copy-only-if-absent** like the other four (`plan`, `adr`, `research`, `spec`). **Its shipped `State:` value is `parked`, not `active`** — the template is seeded *into the live discussions home* (C-727), and C-718's always-on rule fires on `State: active` there, so an `active` template would arm a repo-wide no-edit freeze on a file that is not a discussion at all. Entry writes its own `State: active` stub (C-715); the template's value is never copied into a real artifact. The `State` vocabulary itself is a header comment rather than a literal option list on the `State:` line, because an option list reads as a malformed state to every consumer that scans the home. It is the **single documentation site** for the artifact's shape: no `SKILL.md` restates the menu, and `hex-discuss/SKILL.md` reaches it by repo path — the same cross-skill read `hex-execute` already makes into `../hex-init/assets/templates/`. A project where `/hex-init` never ran falls back to C-715's one-line header-contract minimum. | `hex-init/assets/templates/discussion.md`; `hex-init/SKILL.md` Step 3 |
| **C-729** | **`memory.md` gains one sibling rule and one placement sentence.** § Destination of knowledge gains a **fifth** bullet — it carries four today: **in-flight discussion state → the discussion artifact, never `hex.md`.** `hex.md` holds pointers, not prose (§ Editing rules, "keep it small"), and a discussion is prose by nature; `hex.md › Memory` records only the discussion hand-off record, the artifact-index row, and C-711's promotion candidate. That candidate is proposed into **project context** by the next `/hex-init` **re-audit**, with consent (`hex-init/references/audit.md`) — the route for *project* knowledge, distinct from § Upkeep step's route for *preferences*, and the amendment says so in one clause so the two are not conflated. The same amendment places hex-discuss against the **satellite halt** (§ Location and resolution › Federation satellites): **out of scope, and stated so** — the halt fires unconditionally for the four orchestrators and never named a non-orchestrator, so "exempt" would overstate; the amendment instead extends the scope lead-in with one sentence saying a non-orchestrator skill sits outside the halt on `/hex-init`'s own ground — it resolves no plan and writes no plan or federation state, and hex-discuss's only memory writes are the discussion hand-off record and index rows, post-gate (C-708). One bullet, one scope sentence, and the re-grounded `/hex-init` exemption clause; no new section, no new mechanism. | `hex-core/references/memory.md` § Destination of knowledge, § Location and resolution |
| **C-730** | **Hook provisioning is declined for this release, with a named revisit trigger.** `hex-init` does **not** write `.claude/settings.json` and hex ships no client-specific enforcement. Three reasons: grim's `hook` artifact kind is fully specified, implemented and ADR-Accepted (2026-08-16) but sits on an unmerged branch absent from `v0.14.0`, so building a runtime writer now builds a thing whose replacement already exists; it would be the bundle's only Claude-only surface in a bundle whose moat is portability; and hard-blocking a conversational stance repeats native plan mode's failure by also blocking the scoped writes the mode needs. **Revisit trigger:** a hooks entry in a tagged grimoire release, at which point the change is a `[hooks]` table entry, not a design round. This **overrides `rule-artifacts-grim.md`'s own interim recommendation**, which proposed that `hex-init` write the `.claude/settings.json` entry itself until grim's `hook` kind ships: that recommendation optimizes for the capability landing early, and this decision optimizes for portability — a Claude-only enforcement surface inside a bundle whose moat is reaching every client is the wrong thing to ship for a few months' head start. | this ADR (a stated non-goal); revisit tracked in `hex/CHANGELOG.md` |
| **C-731** | **Bundle wiring and release.** `hex.toml` gains `[skills] "hex-discuss" = "./hex-discuss:latest"` and the `[rules]` table of C-720; `publish.toml` gains `[skills."hex-discuss"] path = "hex-discuss"` and `[rules."hex-state"] path = "hex-state.md"` — **quoted keys**, as every existing entry in both files already uses — and its `version` bumps to `0.2.0` — a **minor** bump: two new members and a new capability, no breaking change to any existing skill. No artifact is deprecated and no `replaced-by` is set. | `hex/hex.toml`; `hex/publish.toml`; `hex/CHANGELOG.md` |

**UX scenarios.**

| ID | Scenario |
|---|---|
| **S-701** | A three-turn question ("should this be a flag or a subcommand?") is answered and drains inline. Entry wrote the header-only stub (C-715) and fired the entry wave (C-706); the inline drain **deletes the stub**, so the run leaves **no discussion artifact** — C-709's no-obligation clause holds and the net **discussion-file** count is zero. A **research artifact** the wave landed before the drain **persists** in the shared research home and is named in the terminal report: the clause nets zero discussion files, never zero files. |
| **S-702** | A long discussion. Entry writes the header-only stub. Turn 4 lands a research result → `## Intent` and `## Research` appear; `## Threads` appears at turn 11 when the second thread opens; `## Decisions` never appears because none was taken. No empty section is ever written (C-715). |
| **S-703** | The user pushes back twice on the same point with the same argument. The orchestrator **holds and restates the evidence** (C-705a); when the user's third message adds a benchmark, it updates and states what changed. |
| **S-704** | The user says "sounds good" after the restate. The orchestrator **does not drain** — it asks for an explicit yes, naming that it is asking (C-710). |
| **S-705** | The drain target is `spec`. The handoff prints `/hex-plan` plus a line stating the spec is reached by `/hex-review`'s Fold-Back on the converged plan. **No spec file is written and no fold runs** (C-711, C-708). |
| **S-706** | A remark ("we always gate merges on the acceptance suite") is recognized as a durable convention. **After** the C-710 yes it lands in `hex.md › Memory` as a promotion candidate (C-708); `CLAUDE.md` is untouched; the next `/hex-init` **re-audit** surfaces it against the matching audit item and proposes it into project context with consent (C-711, C-729). |
| **S-707** | `/hex-architect .agents/discussions/foo.md` where `State: active`. The run **refuses** with the C-722 pair rather than fast-pathing an unratified discussion. The same refusal fires at `handed-off → dropped`, with the branched `Fix:` naming that this discussion ratified *not* building — a ratified "no" must not be laundered into an ADR by re-pointing the file at the architect. |
| **S-708** | A fast-path run where the dossier names `src/auth/token.rs`, since deleted. Discover **halts at the gate** naming the path (C-723) — no ADR is produced from a stale premise. |
| **S-709** | A fast-path run on a fresh dossier. Discover shrinks to the claim diff, Research announces two of three axes skipped with their cited artifacts, **Phase 4 runs in full**, and the adversary gate runs by default (C-723…C-726). |
| **S-710** | The same skill on a client with no ownable rule path (Codex). The rule is simply absent; `/hex-discuss` runs with identical intake, cadence, grill, artifact, gate, and drain. The only difference is that after a compaction the stance may lapse; recovery is **re-reading the discussion artifact — whose header carries the state, not the stance — together with `hex-discuss/SKILL.md`**, which is where the stance actually lives, or a fresh session — never re-invoking the skill, which returns "already loaded" (C-719). |
| **S-711** | A **lane multi-select expansion** resolves to 11 researchers **in total** — under the hard cap of 12. Batching is a *concurrency* split: a demand of 11 runs as batches of **8 then 3** under the effective cap `min(8, limits.max-workers)`, and the split prints once with the cap's source. A demand above 12 **truncates to 12, announced once**. No coordinator is spawned and no nested spawn occurs. **After the expansion a research artifact exists per lane** for every finding longer than a paragraph (C-707). |
| **S-712** | The discussion concludes that the feature should not be built. `State: handed-off → dropped`, and the handoff reports it as a **successful outcome** with the reasoning preserved (C-711). |
| **S-713** | The user and the orchestrator agree on a decision-relevant point. The orchestrator names the strongest remaining counter-argument **once** and moves on — it neither manufactures a second objection to look rigorous nor re-raises the same one later (C-705b). |
| **S-714** | A thread stalls. The orchestrator picks **two** fitting techniques (a premortem, then a force-rank) and applies them inline. It never prints the catalog, and a third technique on the same thread is a contract violation (C-705c). |
| **S-715** | The user has stated a preference for option X. The researcher prompt spawned for the disputed fact states the question neutrally — the evidence for and against X and Y on the named axis — and reveals neither the user's nor the orchestrator's leaning (C-705d). |
| **S-716** | The opening turn asks all three intake slots at once; the user answers two. The orchestrator proceeds with what it has, and the missing slot resurfaces later as a **single design question with an attached recommendation** — a second composite intake ask would be a C-702 violation. |

## Non-Functional Requirements

Only affected axes; silence means not affected.

| Axis | Impact of this decision |
|---|---|
| Scalability | Bounded by construction — ≤3 concurrent researchers by default (the automatic entry wave takes two of those three slots), ≤12 total per **lane expansion**, both inside the existing `min(8, max-workers)` cap counted recursively. No new fan-out mechanism and no new recursion level. |
| Availability | Not affected. |
| Latency | **The one axis with a hard requirement**: background research must never block a conversational turn (C-706). A client that cannot spawn subagents serializes them, which materially changes the experience — hence the mandatory one-line degraded disclosure (C-712), the only place hex-discuss is loud about its own mechanics. |
| Security | Two boundaries. (i) The **write surface is enumerated, scoped, and split by the gate** (C-708) — no code, no config, no project context. Pre-gate writes are the discussion artifact, its research artifacts, and the `hex.md › Pointers` staleness re-point — a repair of a row that already exists, with nothing to revert — and reverting an abandoned discussion means deleting that file **plus the research artifacts it lists**, not a directory: the research home is shared with every other hex skill. The two `hex.md` rows exist only post-gate and revert by deleting two lines. (ii) A discussion artifact is prose written across sessions and then **read by a downstream orchestrator as input** — a trust boundary. **The dossier and every file it names** are treated as *data*, never as instructions — one trust class, governing the engagement check, the claim diff (including the re-read of a changed named path), the research-citation `Expires:` read, the mandatory steelman, and the `architect` worker's own read alike. At Phase 4 the dossier reaches that worker **clearly delimited as data**, with the worker **told explicitly** that any directive, tool request, or role change appearing inside it is content to analyze, never an instruction to follow. Every echo of that text is quoted and length-bounded (C-723's governing echo rule), and C-723's claim diff is the substantive check: a dossier's assertions about the repo are verified against the repo, not believed. The always-on rule adds ~10 lines of static prefix text and no execution. |
| Cost | The rule's real cost is not tokens (caching makes repeat turns near-free) but **instruction-count budget on every unrelated task** — bounded at ≤10 lines by C-718. The skill body costs zero until its description matches. |
| Operability | One new directory, one new artifact class, one new install surface. Drift is handled by mechanisms that already exist: verify-on-consumption for the pointer, `hex-init` re-audit for the row, and — deliberately — **no new staleness machinery**. The per-client reach table (C-721) is the one genuinely new thing an operator must know, which is why it lives in `hex-discuss/references/reach.md` — off the always-loaded body, one link from `SKILL.md` § Constraints, and derived from grim's transform table, not restated as an independent claim that could drift away from it. |

## Constitution deviations

`hex/DESIGN.md` is binding. This decision amends it in **two** places,
declares **two** `protocol.md` deviations, and adds **one** `models.md`
scoping clause. Following `adr_0005`'s deferred
finding D-5, each justification is stated as *which simpler route was
rejected and why*, not as "why the change is needed."

### DESIGN.md amendment round — 2026-08-28, round 9

Proposed text, to be appended to `hex/DESIGN.md` (implementation is
downstream; this ADR does not edit the file):

```markdown
## Discussion-mode round (2026-08-28, round 9)

`adr_0008` (pre-plan discussion mode — the `hex-discuss` skill, the
`.agents/discussions/` artifact class, and the bundle's first rule
artifact) amends **two resolved positions**. Full adjudication and the
scored A/B/C/D/E comparison: `adr_0008` § Constitution deviations and
§ Considered Options.

1. **"Shared shape (all orchestrators)" scopes to the four orchestrators;
   `hex-discuss` is a fifth *skill* with its single gate at the exit.**
   The shape above — parse args → classify tier → resolve overlays →
   single meta-plan approval gate → announce the resolved config →
   dispatch to a tier file, laid out as `SKILL.md` + `classify.md` +
   `overlays.md` + `tier-{low,medium,high}.md` — was written for skills
   that resolve a whole swarm before launching it. `hex-discuss` resolves
   nothing at turn zero: its spawn set is discovered *through* the
   conversation, and its two knobs (research on/off, the deep-sweep gear)
   are conversational moments, not config. Rejected alternative:
   **giving `hex-discuss` tiers and an entry gate** (Option D's shape,
   and the conforming route) forces an approval block that announces a
   config nobody has yet chosen, in front of a mode whose premise is that
   nothing is committed — an entry gate that guards nothing while
   destroying the mode's opening turn. What the rule protects is
   preserved exactly: there is still **exactly one approval gate per
   run**, and the reader is still never misled about what will happen —
   the gate simply sits where the irreversible act is, at the drain
   (`adr_0008` C-710), and the announce block is replaced by **one line
   per mandated disclosure** (C-712) rather than dropped. One further
   user-facing confirmation is declared here rather than left implicit,
   and it is **not a gate**: the deep-sweep offer (C-707) asks before
   spending up to twelve workers. It is a bounded, user-initiated
   **spend** confirmation — a conversation is not a swarm, so nothing
   strands when the user declines and no state advances when they
   accept; it exists only because a twelve-worker spend mid-conversation
   must never be silent. The approval-gate count is still one. Tier
   *vocabulary* is untouched; `hex-discuss` has no tiers to name, so
   `config.md`'s `tiers.<skill>` segment stays closed to the four and the
   frozen v1 vocabulary gains no key.

2. **The bundle ships a rule artifact — a second install surface, with
   declared degradation.** Every resolved decision above assumes hex ships
   skills; the closest neighbour, "Worker definitions: markdown prompt
   blocks inside tier files, not shipped agent artifacts," chose *against*
   a second artifact kind on portability grounds. A rule reaches Claude,
   Cursor, Copilot and Kiro natively, is degraded on OpenCode and Junie,
   and is absent elsewhere. Rejected alternative: **keeping the stance in
   the skill body alone** (Option B) is the portable route and loses on
   the single requirement the mode exists for — a skill body is
   conversation content, condensed first at compaction, so the stance
   lapses on exactly the long discussions that need it. The
   portability the old decision protects is preserved by a contract, not
   by abstinence: the rule is **strictly a hardening** and no hex file may
   make its presence a condition of any behavior (`adr_0008` C-719), so a
   client without a rule surface loses persistence convenience and never
   capability — Option B is not a rejected design but `hex-discuss`'s own
   degraded mode. The surface is also **singular by design**: the one
   bundle-generic `hex-state` rule carries a single concrete line per
   shipped mode, and a future mode amends that same file through its own
   ADR rather than adding a rule per feature — the always-on cost stays
   one artifact and grows by single lines, never by artifacts.

**Considered and not deviated** (unchanged by this round): the **two-layer
knowledge model** is upheld — `hex-discuss` writes no project context; a
durable convention it surfaces is recorded in `hex.md › Memory` post-gate and
proposed into project context at the next `/hex-init` **re-audit**, with
consent (`hex-init/references/audit.md`) — the route for *project* knowledge,
distinct from § Upkeep step's route for surfaced *preferences*, and named
separately here so the two do not merge into one claim.
**`adr_0005`'s fold path is untouched** — the spec drain target
emits a `/hex-plan` command and a pointer to `/hex-review`'s Fold-Back;
`hex-discuss` writes no spec and invokes no fold, so `archive.md`'s safety
envelope remains the only fold mechanism. **Capability classes** — no
literal model name appears in any shipped file (`DESIGN.md`'s own rule) and
no harness tool name either (`protocol.md` § Worker coordination's
capability-class-not-primitive-name rule, which is where that half of the
house rule actually lives). The researcher's shipped default is
`fast-balanced`, its matrix cell at every tier, so `hex-discuss` escalates
nothing on its own judgment; a `models.overrides` escalation is possible and
is disclosed by the resolved-literal-model line like any other. **A new
directory under `.agents/` is not a
deviation** — `.agents/` is the stated default artifact overflow home and
`specs/`, `workers/`, `workflows/` were each added without an amendment.
**`hex never pushes`, `hex never commits` outside execution** — unchanged.
```

*(Amendment 2's always-on cost sentence above is amended by the 2026-08-29
erratum; see Changelog. The fenced text is left as round 9 proposed it.)*

### `protocol.md` deviation 1 — the single-gate scoping sentence

`protocol.md:54-58` currently reads: "This single-gate rule scopes to the
four orchestrators …; `/hex-init` is a configuration wizard, not an
orchestrator, and is exempt — **an exemption that does not extend to any
skill that spawns workers.**" `hex-discuss` spawns workers, so it is
excluded by the sentence's own terms.

**This is not resolved by widening the exemption.** The exemption's stated
ground — `hex-init` "spawns nothing" — is written down in `DESIGN.md`'s
round 6, item 4, not in `protocol.md`'s own sentence; and the rule's purpose
is to prevent a **stranded swarm** — a long autonomous run where a mid-flow
question leaves parallel workers hanging. Rejected alternative:
**re-writing the exemption as a criterion** ("skills whose workers are off
the critical path") makes a narrow, auditable carve-out into a judgement
call, and the hex-init exemption had to be written down twice precisely
because implicit conformance did not hold. The sentence instead gains a
**second named member with its own stated ground**: `hex-discuss` keeps
exactly one gate, positioned at the drain, and its workers are read-only,
capped at three by default, and never on the critical path — the
conversation proceeds whether or not they return, so there is no swarm to
strand. Two named skills, two stated grounds, no criterion to interpret.

### `protocol.md` deviation 2 — the Upkeep step is scoped to orchestrators

`protocol.md` § Upkeep step opens "Every orchestrator's **final phase** …"
and assigns to it the `hex.md › Pointers` re-point and the `hex.md › Memory`
update. `hex-discuss` is not an orchestrator and has no final phase, yet
C-708 has it making exactly those two writes at the drain. Rejected
alternative: **saying nothing and letting those writes ride on "every
orchestrator" by analogy** — an unstated exception is precisely how a second,
divergent upkeep convention gets written a year from now, and it is the drift
single-source exists to prevent. Wave 1 instead adds one scoping sentence:
the Upkeep duties belong to the four orchestrators; a **non-orchestrator hex
skill makes an upkeep write only where its own contract names one**, and
`hex-discuss`'s post-gate discussion-pointer and index rows (C-708) are the
single such case today.

### `models.md` amendment — the disclosure carrier

`models.md` rule 1's second clause names the **announce block** as the
carrier of the resolved-literal-model disclosure, and the meta-plan gate as
its timing; `hex-discuss` has neither. Rejected alternative: **letting the
literal-model line ride rule 1 by analogy** — the same unstated-exception
drift deviation 2 exists to prevent. Wave 1 adds one scoping clause to
rule 1: a skill with no announce block prints the same disclosure as **one
line under its declared quiet form** (C-712's item 4), at the first spawn of
the role.

**Which `protocol.md` sections bind a spawning non-orchestrator skill.**
Stated once here, so the next such skill inherits an answer instead of a
precedent. **Bound:** § Worker coordination — the concurrency cap, sequential
batching, and the per-axis degraded lines govern *spawning itself*, and
`hex-discuss` spawns; and § Upkeep step as amended above. **Exempt, with
ground:** § Shared shape — it describes the args → tier → overlays → dispatch
loop of a skill that resolves a whole config before launching, and
`hex-discuss` resolves none (DESIGN.md amendment 1); § The meta-plan
approval gate — deviation 1 above, which *relocates* the gate rather than
removing it; and § Spawn-selection precedence — its carriers (an announce
block showing the resolved set, a user picking perspectives at an entry
gate) do not exist here, because there is no resolved spawn set at turn
zero and the user's lever is the conversation itself plus the relocated
gate; its layered precedence is moot for a skill with no tier baseline and
no overlays. § Handoff contract is **bound in substance via C-711**: every
drain ends with the required final block — the `Next:` command and the
terminal-state report — while the orchestrator-specific fields
(classification, tier, overlays) do not apply.

## Migration / rollout plan

*(Fills the template's Implementation-Plan slot; the corpus uses this
heading — `adr_0003`, `adr_0005`, `adr_0006`.)*

Three waves. `hex` is released at v0.1.1, so backward compatibility is a real
constraint for the first time. Every wave is **additive**, and the honest
claim is narrower than "vacuous when unused": a session that never invokes
`/hex-discuss` sees **no behavior change** — but it does carry ~10 always-on
rule lines on a rule-hosting client, and it loads two **amended** sentences in
the shared references (`protocol.md`'s single-gate scoping sentence and its
§ Upkeep step) alongside the sentences this ADR adds. Nothing is
byte-identical; nothing behaves differently either.

- **Wave 1 — the skill and the artifact class.** `hex/hex-discuss/SKILL.md`
  (C-701…C-717, plus `hex-discuss/references/reach.md` per C-721), the
  `memory.md` sibling bullet
  and satellite-scope sentence (C-729), the `protocol.md` gate-scoping
  sentence (deviation 1), the § Upkeep step scoping sentence and its
  binding-sections sentence (deviation 2), the `models.md` rule-1 scoping
  clause (the disclosure carrier), the C-716 ID sentence, and
  `hex-init/assets/templates/discussion.md` (C-728). After Wave 1 the mode
  works everywhere, with Option-B durability. *Verify:*
  `grim build ./hex/hex-discuss`, `./hex/hex-core`, `./hex/hex-init`.
- **Wave 2 — the rule.** `hex/hex-state.md` (C-718…C-720; C-721's
  reach table shipped with the skill in Wave 1) plus the
  `hex.toml` / `publish.toml` wiring (C-720, C-731). *Verify:*
  `grim build ./hex/hex-state.md` and `grim build ./hex/hex.toml`;
  confirm `summary`/`keywords` appear in `grim describe` — a rule whose
  catalog keys were nested under `metadata:` builds clean and silently shows
  no summary, which is the Asymmetry's one trap.
- **Wave 3 — the fast path and provisioning.** `hex-architect` (C-722…C-726)
  and the `hex-init` audit item (C-727). *Verify:*
  `grim build ./hex/hex-architect`, `./hex/hex-init`.

**Existing installs.** `grim update` pulls the two new members; the
`[rules]` table is new, so a consumer on a client with no rule surface
installs the skill and skips the rule with no error. A missing
`.agents/discussions/` directory is normal — created lazily on first
materialization (C-715), never provisioned eagerly.

**Coworkers mid-adoption.** Nothing they already run changes. A discussion
artifact authored before the template exists still satisfies C-714 if it
carries `State:` and `Updated:` — the dogfood instance
(`.agents/discussions/hex-discuss-skill.md`) already does, and is the
acceptance fixture for C-722/C-723.

**Version and changelog.** `publish.toml` `version = "0.2.0"`;
`hex/CHANGELOG.md` gains an `## [0.2.0]` section with `### Added` — the
`hex-discuss` skill, the `hex-state` rule, and the
`.agents/discussions/` convention — and one line under a `### Notes` heading
recording C-730's declined hook provisioning and its revisit trigger, so the
deferral is tracked where a reader will find it rather than in this ADR
alone.

**Rollback.** Unwiring the two members is the smallest part of it, so the
full edit set is enumerated rather than discovered piecemeal:

- `hex/hex.toml` — the `[rules]` table and the `"hex-discuss"` skill entry.
- `hex/publish.toml` — the `[skills."hex-discuss"]` and
  `[rules."hex-state"]` entries, and the version bump.
- `protocol.md` — the single-gate scoping sentence (deviation 1), the
  § Upkeep step scoping and binding-sections sentences (deviation 2), and the
  C-716 Traceability-IDs sentence.
- `models.md` — the rule-1 scoping clause (the disclosure carrier).
- `memory.md` — the § Destination of knowledge bullet and the § Location and
  resolution satellite-scope sentence (C-729), **and** the re-grounded
  `/hex-init` exemption sentence in that same paragraph ("exempt rather than
  outside, because it *does* write federation state"): rollback **restores the
  prior sentence**, it does not merely delete the new clause.
- `hex/DESIGN.md` — round 9 in full, **and** round 6 item 4's strikethrough
  annotation: rollback restores the un-struck text (`hex-init` only, because
  it spawns nothing; no skill that spawns workers gets the exemption).
  Deleting round 9 while leaving the annotation would leave round 6 pointing
  at a round that no longer exists.
- `hex-init` — the conditional audit item (C-727) and
  `assets/templates/discussion.md` (C-728).
- `hex-architect` — the C-722…C-726 fast-path clauses.

No other skill takes a dependency on `hex-discuss`, and `hex-architect` needs
no behavioral revert beyond deleting text: C-722's fast path is a conditional
branch on an input shape and is inert without a discussion artifact.
**A published artifact is never un-shipped by deletion.** Retiring
`hex-state` or `hex-discuss` follows this repo's convention —
`deprecated` plus `replaced-by` authored in the artifact source and
re-released — so an existing consumer's `grim update` learns the artifact is
retired instead of failing to resolve it.

## Validation

- [ ] `grim build` exits 0 for `./hex/hex-discuss`, `./hex/hex-core`,
      `./hex/hex-init`, `./hex/hex-architect`,
      `./hex/hex-state.md`, and `./hex/hex.toml` after their wave.
- [ ] `task publish -- --dry-run` is green across the bundle.
- [ ] `grim describe` on the published rule shows the `summary` and
      `keywords` (proves the top-level placement, C-720).
- [ ] The rule body is ≤10 lines and states no protocol beyond its single
      C-718 correction clause — and that clause is **present**: a stale or
      abandoned `active` artifact is released by parking it, and parking it
      **demonstrably releases the stance** (a subsequent turn edits code
      without re-arming).
- [ ] The C-718 predicate is **session-bound**, on both branches: an `active`
      artifact that is git-untracked or locally modified **arms** the stance,
      and a **committed, unmodified** `active` artifact is **inert** — a
      colleague's landed discussion never freezes this working tree. With no
      discussions home on disk, nothing is checked at all.
- [ ] **Resume re-arms** (C-715): re-entering a `parked` artifact writes a
      fresh `Updated:` and sets `State:` back to `active`, and the stance is
      armed again on the next code-editing turn; a later abort returns it to
      `parked` and releases it. Re-entering an `active` artifact also writes a
      fresh `Updated:` and never re-stubs.
- [ ] No shipped file added by this ADR names a literal model or a
      harness-specific tool — a grep sweep over **prose**, scoped to exclude
      `hex-discuss/references/reach.md`, whose per-client table names clients
      by contract (C-721) and is the one sanctioned exception
      (`DESIGN.md` house rule). The sweep **covers**
      `hex-discuss/references/research-lanes.md` — C-701's second split — which
      is held to the rule rather than excluded from it: every lane there, the
      council seats included, names a **capability class**, never a model.
- [ ] `hex-discuss` runs end-to-end with the rule file deleted, exercising
      **C-701…C-717 and C-721** (proves C-719 — C-718…C-720 are the rule's
      own contracts, and C-722…C-731 belong to other skills; C-721's reach
      reference ships with the skill and is exercised regardless). The run
      covers the **automatic entry wave** and the **lane multi-select**
      (C-706, C-707) end to end: both are skill-body behavior, neither
      degrades when the rule is absent, and that is the C-719 claim under
      test. After a
      compaction in that run, recovery is asserted to be **the artifact plus
      `hex-discuss/SKILL.md`** — the artifact header carries the *state*, the
      skill file carries the *stance* — never a re-invocation of the skill.
- [ ] The C-717 drain-readiness check **refuses** a bar-failing artifact
      rather than draining it with a warning: one missing its
      `## Verification` section, and one naming a path that is not
      repo-root-relative.
- [ ] Provisioning covers **three** cases (C-727/C-728). (i) A project that
      already holds a discussion artifact: `/hex-init` provisions the
      `hex.md › Pointers` discussions row **and**, only when the resolved home
      is **empty**, offers the seed — `assets/templates/discussion.md` copied
      to `<home>/_template.md`, copy-only-if-absent, under its own consent; a
      non-empty home is never seeded. (ii) A project with **no** artifact where
      the user opts in at invocation or at a Step-2 question: the same item
      fires, having never been raised by hex first. (iii) A project that has
      never discussed anything and does not opt in: **asked nothing**. The
      Step-3 fallback copy is a separate half — `discussion.md` joins the
      five-template copy set only when the user opts into shipped defaults.
- [ ] `memory.md` carries the fifth § Destination of knowledge bullet and the
      satellite-placement sentence, and a `/hex-discuss` run inside a
      federation satellite does **not** halt (C-729).
- [ ] The **`handed-off → context` drain closes properly** (S-706, C-711):
      the promoted convention lands in `hex.md › Memory` post-gate, the
      artifact reaches the **terminal** `State: handed-off → context` — not
      left unresolved — the drain writes `Ratified: <date> → context`, and the
      handoff's next step is `Next: /hex-init`, whose re-audit surfaces the
      candidate with consent. `CLAUDE.md` is untouched.
- [ ] A dogfood discussion exercises **answer-first** mode entry with the
      fixed **two-lane entry wave**, the **lane multi-select** chips moment
      offered once after that dispatch, one background result folded in at a
      turn boundary, a **user-called** drain, the restate-gate refusing a soft
      confirmation, and a drain to plan — with **zero unprompted drain
      offers** across the whole run (C-709).
- [ ] `/hex-architect .agents/discussions/hex-discuss-skill.md` fast-paths:
      Discover reports a claim diff, Research announces per-axis skips,
      **Phase 4 runs**, and the adversary gate is on (C-723…C-726). The
      fixture's `.agents/specs/` path — a documented convention with no
      file in git history yet — surfaces as a C-723(a)
      `[NEEDS CLARIFICATION]` marker in the drafted ADR — not a halt, not a
      live question.
- [ ] **Every branch of C-722's refusal table fires, and each prints exactly
      the one `Fix:` line the state selects** — five cases, under the one
      shared `Error:`: `active` **or** `parked` → `Fix: resume it with
      /hex-discuss "<topic>" and drain it to → architect, …`;
      `handed-off → plan` → `Fix: this discussion's target is /hex-plan …`;
      `handed-off → context` → `Fix: … run /hex-init to adopt it …`;
      `handed-off → dropped` → `Fix: … a new /hex-discuss "<topic>" revisits
      it — the dropped artifact stays dropped …`; and an out-of-vocabulary
      `State:` value (hand-typed, typo'd arrow, older vocabulary) →
      `Fix: set State: to one of active, parked, …` — a refusal like the
      others, **never a fallthrough to free text** (S-707).
- [ ] An explicit `low` tier with a dossier is **refused at step 1**, before
      the classifier runs, with the shipped `Error:`/`Fix:` pair; a
      *classifier* `low` is instead **promoted to medium and announced**,
      carrying the classifier's own rationale forward.
- [ ] A **path-shaped `<decision>` that does not engage** is never refused: it
      runs as ordinary free text and the run **discloses once** beforehand
      with the `Note:` line naming the failed condition — not readable / not
      under the discussions home / no `State:`/`Updated:` header — plus its
      `Fix:` line offering a re-run with the corrected path.
- [ ] Claim-diff outcomes, **all three** (C-723): a dossier naming a
      **deleted** path **halts at the gate**; a path **absent from history**
      surfaces as a `[NEEDS CLARIFICATION]` marker in the drafted ADR — never
      a live question, never a halt; and a path that **changed** since the
      staleness anchor is **announced as changed and re-read**, never silently
      trusted and never folded into the deleted branch (S-708).
- [ ] Claim-diff **named-path containment** (C-723): a named path whose
      canonical target **escapes the repository root** is **never read** and
      takes the author-error branch under its own marker text
      (`… resolves outside this repository — typo, symlink, or another repo's
      path?`) — no halt; and an **over-long or newline-bearing** named path is
      echoed **quoted, truncated with `…` past 120 characters, and never
      breaking its own line** (the governing echo rule).
- [ ] The consent record round-trips across **four** failure sub-cases, each
      raised as a step-4 gate question rather than a refusal (C-722): a
      `handed-off` artifact **missing** its `Ratified:` line; one whose line
      is **malformed**; one **dated unparseably**; and one drained to a target
      **other than `architect`**. A drain that keeps an artifact appends the
      `Ratified:` line, and a **git-tracked** artifact exercises C-723's
      last-commit staleness anchor, including the announced disagreement when
      `Updated:` and the commit date diverge.
- [ ] The **quiet announce form** holds (C-712): a dogfood turn asserts a
      research aside renders as **one line, never a block**, and the entry
      turn prints the **combined** `— discussion notes: <path> · recon: N
      dispatched` line — one line, never two, the stub write and the entry
      wave's dispatch count together, and both **after** the turn's substance
      (C-701). S-710 is
      extended — a client that cannot spawn prints `Degraded: inline workers`
      exactly **once** while intake, cadence, grill, artifact, gate, and drain
      run identically, the only losses being that the stance may lapse after a
      compaction and that the entry wave runs inline.
- [ ] The three announce forms that no other item exercises each render as
      **one line, once** (C-712): the entry disclosure in its **combined**
      form, `— discussion notes: <path> · recon: N dispatched`, on the run
      that writes the stub; the
      `Limits:` line when a `hex.md › Preferences` limit is in force; and the
      **composed second degraded axis**, `Degraded: single session model — no
      per-spawn override; matrix advisory`, on its own line beside the
      inline-workers line.
- [ ] The **researcher failure branch**: one researcher is failed
      deliberately; the one-line transport note prints, and the event is
      never folded into "no result found" (C-706).
- [ ] C-713's **no-silent-clobber holds on both branches**: entry on a slug
      already at `State: active` or `parked` **resumes** that artifact with no
      overwrite, and a slug colliding with a `handed-off` artifact takes a
      **date suffix**.
- [ ] The restate names the **whole write set** (C-710) — the full shipped
      disclosure list, nothing elided: every already-written path (the
      discussion artifact and each research artifact), **any
      `hex.md › Pointers` re-point made this run**, the proposed-artifact
      list, **the artifact's own header update**, the two `hex.md` rows the
      drain will touch, and — for an inline drain — **the stub deletion**.
- [ ] **Lane-expansion cap boundary** (C-707): a demand above 12
      **truncates to 12, announced once**, and that 12 bounds **one lane
      expansion** — concurrency inside it still batches under
      `min(8, limits.max-workers)`, the split announced with the cap's
      source. Under `Degraded: inline workers` the expansion runs inline, one
      spawn at a time, announced once by the degraded line — **no separate
      degraded re-cap exists**.
- [ ] A **grep of the dogfood-produced discussion artifact finds no `C-`/`S-`
      IDs** (C-716), and a grep of the **shipped template** confirms its
      `State:` value is **`parked`, never `active`** (C-728) while the seeded
      copy lands as `<home>/_template.md` (C-727).
- [ ] A **reviewed sweep for `/hex-discuss` outside `hex/hex-discuss/`**
      confirms no shipped file emits it **as a model instruction** (C-701's
      never-self-triggered clause). The sweep is reviewed, not a bare zero-hit
      grep: the allowed hit classes are command listings (`CLAUDE.md`,
      `README`), user-facing `Fix:` and README prose telling a *person* what
      to run, TOML wiring, and ownership comments in templates and audit
      references.
- [ ] S-701…S-716 pass as acceptance cases.

## Open Questions

- [NEEDS CLARIFICATION: should the deep sweep's total be a hard cap of 12,
  or ride `limits.max-workers` alone with no separate ceiling?]
  **Recommended: a hard cap of 12**, batched under `min(8, max-workers)` —
  `max-workers` is a *concurrency* ceiling, not a total, so without a
  separate cap a sweep offered mid-conversation has unbounded cost, and a
  cost surprise is exactly what breaks the "feels like a discussion" NFR.

  *(**Resolved 2026-08-30**, ratified by the owner at the `hex-discuss`
  interactive-rework plan round: the **hard cap of 12 stands**, and it now
  bounds a single user-selected **lane expansion** rather than a two-wave
  sweep — the two-gear offer this question presumed is **retired** in favour
  of the lane multi-select (C-707; `hex/DESIGN.md`'s 2026-08-30 round). The
  question text above is preserved as it was asked.)*

- [NEEDS CLARIFICATION: does the discussions home follow a project's
  documented artifact convention, or is it always `.agents/discussions/`?]
  **Recommended: follow the documented convention when one names a
  discussion home, else `.agents/discussions/`** — the same resolution order
  every other artifact class uses (`memory.md` § Location and resolution).
  `hex-init` asks about it only when a discussion already exists (C-727), so
  a project that never discusses anything gains no wizard question.

- [NEEDS CLARIFICATION: does the rule ship in v0.2.0 with the skill, or one
  release later, after the skill is dogfooded alone?]
  **Recommended: the same release.** The rule is ten non-load-bearing lines
  (C-719) and splitting it doubles the release ceremony for no risk
  reduction — and shipping the skill alone first would field-test precisely
  the degraded mode (Option B) rather than the chosen design.

## Links

- Source discussion: [hex-discuss-skill.md](../discussions/hex-discuss-skill.md)
  — the dossier this ADR consumes, and the acceptance fixture for C-722/C-723.
- Related ADR: [adr_0003_configuration_customization_surface.md](adr_0003_configuration_customization_surface.md)
  — the frozen v1 config vocabulary this decision deliberately does not extend.
- Related ADR: [adr_0005_archive_fold_back.md](adr_0005_archive_fold_back.md)
  — the single fold path C-711's spec drain routes to rather than duplicates.
- Related ADR: [adr_0006_finding_severity_contract.md](adr_0006_finding_severity_contract.md)
  — the un-forkable-carrier pattern C-719 mirrors for the rule.
- Research: [discuss-skills-field.md](../research/discuss-skills-field.md),
  [discuss-mode-mechanics.md](../research/discuss-mode-mechanics.md),
  [discuss-grill-mechanics.md](../research/discuss-grill-mechanics.md),
  [discuss-anthropic.md](../research/discuss-anthropic.md),
  [discuss-openai.md](../research/discuss-openai.md),
  [discuss-github.md](../research/discuss-github.md),
  [discuss-practitioners.md](../research/discuss-practitioners.md),
  [discuss-vendors.md](../research/discuss-vendors.md),
  [rule-context-budgets.md](../research/rule-context-budgets.md),
  [rule-artifacts-grim.md](../research/rule-artifacts-grim.md),
  [dossier-fastpath-precedent.md](../research/dossier-fastpath-precedent.md),
  [discuss-competitive-delta.md](../research/discuss-competitive-delta.md),
  [openspec-framework-analysis.md](../research/openspec-framework-analysis.md).
- Prior art: OpenSpec v1.9.0–v1.11.0 explore-mode consent hardening
  ([CHANGELOG](https://github.com/Fission-AI/OpenSpec/blob/main/CHANGELOG.md));
  ASDLC.io adversarial code review
  ([pattern](https://asdlc.io/patterns/adversarial-code-review/)).

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-08-28 | hex-architect | Initial draft. Chosen Option A (skill + unscoped rule + discussion artifact, single gate relocated to the drain) from a 5-option weighted comparison. Overturns the dossier's "architect fast-path skips Design" working decision — Design *is* ADR authoring — and replaces it with a trust-scoped fast path (Discover shrinks, Research skips per-axis, Design never skips, Review weighted up). Declines hook provisioning with a named revisit trigger. Contracts C-701…C-731, scenarios S-701…S-712. Two DESIGN.md amendments (round 9) plus one protocol.md deviation. Status Proposed. |
| 2026-08-28 | hex-architect | Panel round 1 fixes: reach table relocated out of the rule into `hex-discuss/SKILL.md` § Reach (C-718/C-721 conflict) [retargeted 2026-08-29 to `hex-discuss/references/reach.md` — see the C-701/C-721 row below]; durability rescored honestly — client-weighted row added, A loses to B below a 53% rule-hosting share, with a stated re-open trigger; pre-gate write surface narrowed to the artifact plus research artifacts, the `hex.md` rows moved post-gate, and the real revert enumerated. A second `protocol.md` deviation declared (§ Upkeep scoped to orchestrators, plus which sections bind a spawning non-orchestrator); mode entry's header-only stub declared as C-715's exception; fast path gains a medium tier floor and refuses every state but `handed-off → architect`. Citations repaired throughout; scenarios extended to S-701…S-716. Contracts amended in place — no renumbering. Status Proposed. |
| 2026-08-28 | hex-architect | Re-validation residuals applied (each as the re-validator specified): C-719 acceptance range corrected to C-701…C-717 + C-721; blended durability restated with its blend (57 → total 72.4, decision unchanged); the coworker-client claim marked a stated assumption; the `models.md` rule-1 disclosure carrier declared as a Wave-1 scoping clause; § Spawn-selection precedence and § Handoff contract classified in the binding list; satellite halt reworded out-of-scope (not "exempt"); constitution copy of the 50-turn sentence demoted; C-709 stub pointer, fixture C-723(a) validation clause, Wave-1 contract range C-701…C-717. Status Proposed. |
| 2026-08-28 | hex-architect | Cross-model adversary (codex, plan-artifact, one-shot) fixes — all seven findings triaged actionable: C-710 drain now appends a `Ratified:` header line (durable consent record; C-714/C-722 corroborate it); C-722 gains canonical-path/symlink containment inside repo root + discussions home, pointer verify-on-consumption before refusal, and an explicit bounded-trust statement (the architect's own meta-plan gate still blocks); C-723's staleness anchor is the artifact's last-commit date when tracked (`Updated:` fallback, disagreement announced); C-707 dedup declared incremental-not-global (bounded duplicate margin); C-711 drain commands carry no tier (receiving classifier resolves `auto`); C-713 no-silent-clobber slug rule. Post-fix validation residuals folded in: inline drains keep no consent record and are never fast-path input; the drain's header update named on C-708's post-gate side; user-named `low` excluded on the ADR drain; resume never re-stubs; template documents `Ratified:`; consent-record + tracked-anchor Validation bullet; fixture carries `Ratified:`. Status Proposed. |
| 2026-08-28 | hex-architect | Decider-ratified refinement (Michael, at review): the rule generalizes from a discussion-specific sidecar to the **bundle-generic `hex-state` rule** — file-anchored-state frame + one concrete line per shipped mode + re-anchor duty; entry sheds to the skill's description match (no triggers in the rule); future modes amend the same file via their own ADRs, keeping the always-on surface singular. C-718 rewritten; C-719/C-720/C-721/C-731, Option A description, docket row 1, C-701 entry wording, DESIGN amendment 2, waves/rollback/validation renamed `hex-discussion-mode` → `hex-state`. Status Proposed. |
| 2026-08-28 | Michael Herwig | **Accepted.** Plain approval — the three Open-Questions recommendations stand: sweep hard cap 12; discussions home = documented convention else `.agents/discussions/`; rule ships in v0.2.0 with the skill. |
| 2026-08-29 | /hex-review (tier high) | **C-708 — the `hex.md › Pointers` staleness re-point is ratified as the third pre-gate write**, alongside the discussion artifact and the research artifacts. Ground: resolving the discussions home can find that pointer stale, and `memory.md` § Staleness repairs a pointer **in the same run it is found**, so the repair cannot wait for a gate the run may never reach. C-708's pre-gate enumeration and the **Security NFR's statement of the pre-gate set are amended accordingly**; the re-point's single home is `memory.md` § Staleness (*Verify on consumption*), which both `hex-discuss` (writer) and `hex-architect` (verify-on-consumption before a C-722 refusal) reference rather than restate. A re-point repairs an existing row and carries nothing to revert. Same review: seven acceptance items appended to § Validation, and two missing rollback sites added to § Migration › Rollback. Status Accepted (unchanged). |
| 2026-08-29 | /hex-review (tier high) | **DESIGN round-9 erratum — the always-on cost sentence undercounts.** Recorded verbatim: "the round-9 always-on cost sentence undercounts — a shipped skill's frontmatter description is a second permanent always-on surface alongside the rule body. Corrected: the always-on cost is the rule body plus each shipped member's description line; a description carries entry triggers only and never duplicates body prose; a future member's ADR budgets both." Erratum only — C-718's ≤10-line cap and the Cost NFR are unchanged. Status Accepted (unchanged). |
| 2026-08-29 | /hex-review (tier high) | **Deviation 1 — the gate exemption is scoped to *named* skills, never by class analogy.** `protocol.md`'s single-gate exemption for spawning non-orchestrator skills reaches only the skills **named in the gate section's closed exemption list** (`hex-init`, `hex-discuss`); a later skill that merely resembles them — read-only workers, off the critical path — does **not** inherit the exemption by class and needs its own named entry with its own stated ground. This is the binding reading of the deviation's own "two named skills, two stated grounds, no criterion to interpret." Status Accepted (unchanged). |
| 2026-08-29 | /hex-review (tier high) | **C-729 — the shipped `memory.md` edit also re-grounds the pre-existing `/hex-init` exemption sentence; sanctioned.** Beyond the fifth § Destination-of-knowledge bullet and the satellite-scope sentence, the edit re-states `/hex-init` as "exempt rather than outside, because it *does* write federation state" — a re-grounding of prose that predates this ADR, recorded here as sanctioned rather than as unscoped drift. Its rollback site is added to § Migration › Rollback (restore the prior sentence, do not merely delete the clause). Status Accepted (unchanged). |
| 2026-08-29 | /hex-review (tier high) | **S-711 — wave-math wording corrected.** The scenario read as though wave 1 alone ran 11. Corrected: a demand of **11 within one wave** runs as batches of **8 then 3** under the effective concurrency cap `min(8, limits.max-workers)`; the **waves remain the breadth→depth split**, and the sweep's **total stays ≤12**. Wording only — C-707's mechanism, cap, and incremental dedup are unchanged. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision via /hex-review deferred list) | **C-718 — the "no examples, no protocol, no edge cases" clause is narrowed to permit exactly one correction clause.** The rule may name how a stale or abandoned `active` discussion artifact is released — park it, `State: parked` — because a predicate justified by being externally *correctable* must say how it is corrected. C-718's row carries the carve-out inline; `hex/hex-state.md`'s mode line gains the clause lexically, adding no physical line (the body stays at its cap). Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision via /hex-review deferred list) | **`handed-off → context` added as a fifth terminal state.** Ground: C-711's → project-context drain is a real drain with a real consent event, yet a convention-promotion-only discussion previously had **no expressible terminal state** — it drained and left the artifact's `State:` unresolved. C-711's terminal-states sentence and C-714's `State` vocabulary both gain it; the drain now sets `State: handed-off → context` and writes `Ratified: <date> → context`, keeping its `Next: /hex-init` re-audit guidance. Shipped in `hex-discuss/SKILL.md` § Handoff, the `discussion.md` template's header-comment vocabulary and `Ratified:` target list, and a new `handed-off → context` row (plus the vocabulary enumeration in the fallback row) in `hex-architect/SKILL.md`'s State-keyed refusal table. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision via /hex-review deferred list) | **C-723(a) — the marker route is ratified over the gate-question wording.** Branch (a) — a path unresolvable *and* absent from history — is carried into the drafted ADR's `## Open questions` as a `[NEEDS CLARIFICATION]` marker under that section's hard cap of 3, and is **never asked live**: Phase 1 runs after the meta-plan gate, so no live gate remains to ask at, and C-717 prescribes the marker for precisely this class. `tier-medium.md` already shipped this behavior; the ADR is corrected to match it at three sites — C-723's row (whose marker text is aligned verbatim to the shipped `tier-medium.md` Phase 1 string) and **both** § Validation bullets that carried the old wording: the fast-path fixture bullet (`.agents/specs/`) and the "Negative fast-path cases" bullet, which still read "asks at the gate instead of halting". Wording follows behavior, not the reverse. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision via /hex-review deferred list) | **C-722 — the `handed-off → dropped` reopen Fix is reworded.** "Reopen it with /hex-discuss" implied the dropped artifact is mutated back into an open discussion, which C-713's no-silent-clobber rule forbids. Replaced with: `a new /hex-discuss "<topic>" revisits it — the dropped artifact stays dropped — or paste the decision as free text.` Applied to the C-722 row and to the shipped `hex-architect/SKILL.md` refusal-table row. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-718 — the rule predicate is narrowed to a session-bound file check.** The freeze fires on an `active` discussion artifact in the resolved discussions home **that is git-untracked or locally modified**; a **committed, unmodified** copy is another session's in-flight discussion and is **inert**, so a colleague's landed discussion never freezes this working tree. `Any` is a **scan of the home, not a first match** — one armed artifact anywhere in it fires the stance. The negative is cheap: **no discussions home on disk means nothing to check**, and that holds until a hex skill runs. The home resolves C-713-faithfully — documented convention via `hex.md › Pointers`, else `.agents/discussions/`. C-718's contract body, which still stated the unqualified predicate, is rewritten to match `hex/hex-state.md`'s shipped lines; § Validation gains the release-clause, inert-committed-copy, and cheap-negative items. Wording follows behavior. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-715 — resuming a discussion re-arms the stance.** Resume still **never re-stubs**, but it does refresh the header: a fresh `Updated:` **always**, plus `State:` back to `active` when resuming from `parked`. That refresh is a header update, not a re-stub, and it **re-arms C-718's no-code-or-config-edits stance** for the resumed conversation; a later abort returns the artifact to `parked`, releasing it again. C-715's contract text and a new § Validation item both state it. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-722 — quoted literals aligned to the shipped strings (closes convergence WP14).** Three alignments. The explicit-`low` refusal now carries the shipped pair: `Error: tier low cannot take a discussion dossier — the safeguards that make the fast path safe only exist at medium and high (claim diff, per-axis research skip, weighted-up review).` with `Fix: re-run as /hex-architect medium "<decision>" (or high), or pass the decision as free text for an ordinary low run.` The `active`/`parked` branch's `Fix:` is replaced by the reworded shipped line, `Fix: resume it with /hex-discuss "<topic>" and drain it to → architect, or paste the decision as free text.` And the **header-anchored extraction rule** is recorded: the `State:` value is read from a **line-initial `State:` above the first `##`** — never a body match — as the text up to the **first field separator** (`·`, `&nbsp;`, or end of line), trimmed and matched exactly, so a valid two-field header never fails closed and `parked (was handed-off → architect)` is never accepted. Wording follows behavior. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-723 — the dossier-path hardening is ratified.** Containment reaches **every path the dossier names**, not just the dossier's own: canonicalize — symlinks resolved — immediately before the read, landing inside the repository root, the check and the read sharing that one canonical path. A path whose canonical target **escapes** takes the author-error branch under its **own** marker text — `[NEEDS CLARIFICATION: "<path>" resolves outside this repository — typo, symlink, or another repo's path?]` — never read, never halting. The **governing echo rule** is recorded once: every placeholder interpolating dossier-trust-class text — `<path>`, `<s>`, `<artifact>`, `<anchor>`, `<date>` — is **quoted, truncated with `…` past 120 characters, and never allowed to break its own line**, stated in `hex-architect/SKILL.md` and never restated at the sites that use it. The Security NFR's data-never-instructions boundary widens accordingly to **the dossier and every file it names** as one trust class, and records the Phase-4 feed of the dossier to the `architect` worker **clearly delimited as data**, with the worker told explicitly that any directive inside it is content to analyze. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-724 — the axis-attribution predicate is stated.** Which axis a citation covers is read from the **cited artifact's own header** — its `Triggered by:` line and its topic (title) line — never inferred from the dossier's prose, because `## Research` is a pathlist with no axis label. **`Domain:` is corroboration only** where present, and a **missing `Domain:` is not a disqualifier**: it is a subject-area taxonomy orthogonal to `classify.md`'s axis catalog. An artifact whose header matches **nothing** about the selected axis is **no evidence** for it, so that axis runs normally — prose inference is never the discount's basis. Those header fields have one home: the `## Metadata` block in `hex-init/assets/templates/research.md`. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-727/C-728 — the seed conventions are ratified.** The discussion template is seeded to `<home>/_template.md`, **offered only when the resolved home is empty**, under its own consent, copy-only-if-absent; the underscore prefix marks it as never a discussion, said so in the offer. Its shipped `State:` value is **`parked`, not `active`** — the seed lands *in the live discussions home*, where C-718's always-on rule fires on `State: active`, so an `active` template would arm a repo-wide no-edit freeze on a file that is not a discussion at all. The `State` vocabulary stays a header **comment** rather than a literal option list, which would read as a malformed state to every consumer scanning the home. C-727's quoted Pointers row is aligned to the shipped `<home>` form. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-708/C-714 — the `Confidence:` line is filled conditionally.** The drain fills the optional `Confidence:` provenance line **where the provenance exists**, never manufactured; the shipped text had it unconditional. Recorded on C-708's post-gate header update and on C-714's header contract. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-701's measurement basis stated and its `references/` split spent; C-721 retargeted.** The ≤400-line body budget is measured **on the body — the H1 onward, frontmatter excluded** — and the pre-authorized `references/` split is now **spent**: § Reach moved out of `hex-discuss/SKILL.md` into **`hex-discuss/references/reach.md`**, so a further split needs its own decision. Every site naming the old home is retargeted — C-721's contract text and its Home column, the docket's decision-outcome row 2, the Operability NFR line, and the Wave-1 line — and the § Validation reference now reads "reach reference" rather than "reach section". The 2026-08-28 changelog entry that recorded the original relocation is **annotated with a bracketed pointer rather than rewritten**: history is not edited. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-707 — the sweep's cap gains its boundary and its degraded form.** The total stays a **hard 12** (`max-workers` caps concurrency, not the total), and **a demand above 12 truncates to 12, announced once**. Under `Degraded: inline workers` there is no background wave to buy, so the sweep **re-caps to the quick check's 3** and the chip text drops "background". C-707's row and the sweep-cap § Validation item both state it. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **C-712 gains the entry-write disclosure, and `hex-discuss`'s structural clauses are recorded.** The quiet form's known set gains `— discussion notes: <path>`, printed once when entry writes the stub — a mode pitched as "don't edit anything yet" writes no file silently. Recorded with it, each in the contract it belongs to: the `## Argument syntax` rule (C-702 — free text becomes intake slot 1 and is never re-asked; a path or slug resumes); the literal `## Discussion Complete` closing block and `dropped`'s absent `Next:` line (C-711); the resumed-artifact staleness note at the restate (C-710); the `State`-vocabulary single-home clauses (C-711/C-714 — the C-728 template defines it, every other site carries a tracking copy); and `archive.md` § Containment's path conditions (C-418) binding this skill's own writes (C-713). The same decision **corrects C-719 and S-710's recovery text to shipped truth**: the artifact header carries the **state**, not the stance, so recovery is the artifact **plus `hex-discuss/SKILL.md`** and, where the rule landed, its `hex-state` line — never a re-invocation, which returns "already loaded". § Validation's two items that run S-710 are corrected with them. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-2 fix-pass gate) | **The repo-root `grimoire.toml` entries are ratified, retroactively.** WP10's `[skills] hex-discuss` and `[rules] hex-state` entries were already on this branch; the plan's former "stated deferral" was false and is corrected. Verification is that `grimoire.toml`'s member set matches `hex/hex.toml`'s. No ADR contract changes — the wiring C-731 describes is the bundle's `hex.toml`/`publish.toml`; this row records the repo's own consuming config as sanctioned rather than unscoped drift. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-3 fix-pass gate) | **C-724 — the axis-attribution predicate is re-based on the field that actually exists, and its producer is bound.** The round-2 predicate led with `Triggered by:`, but live research artifacts do not carry it: of the 21 in this repo's research home, 3 carry `Triggered by:` and 3 carry `Domain:`, while **every one carries a topic (title) line**. The predicate is corrected accordingly: the **topic (title) line is the primary match**, with **`Triggered by:` and `Domain:` as corroborating evidence where present**, and **neither absence is a disqualifier** — most live artifacts carry a compact header rather than the template's full `## Metadata` block. Unchanged: an artifact whose header matches **nothing** about the selected axis is **no evidence**, so that axis runs normally, and prose inference is never the discount's basis. The **producer half** closes the coupling gap: `hex-discuss`'s per-lane research writes are now bound to the same single home — the header contract in `hex-init/assets/templates/research.md`, **its title line and its `## Metadata` block**, the title line sitting above `## Metadata` rather than inside it — so artifacts authored there carry the corroborating fields the fast path's skip reads. Status Accepted (unchanged). |
| 2026-08-29 | Michael Herwig (owner decision at the round-3 fix-pass gate) | **C-723 — the echo-bounding enumeration is completed.** The governing echo rule's "today" list omitted two placeholders that interpolate dossier-trust-class text: `<canonical>`, the symlink-resolved target echoed in the containment refusal, and `<topic>`, the discussion topic echoed in two `Fix:` lines. The list is now `<path>`, `<canonical>`, `<s>`, `<artifact>`, `<anchor>`, `<topic>`, and `<date>` — quoted, truncated with `…` past 120 characters, never allowed to break its own line — stated once in `hex-architect/SKILL.md` and never restated at the sites that use it. The rule itself is unchanged; only its enumeration is corrected, so the two placeholders were already governed in intent and are now governed by construction. Status Accepted (unchanged). |
| 2026-08-30 | Michael Herwig (owner decision at the `hex-discuss` interactive-rework plan round) | **Answer-first entry and the automatic entry recon wave.** The opening turn emits substance first and dispatches only afterwards; entry then fires a **fixed two-lane wave** — codebase recon and a prior-art web scan, seeded from intake slot 1 — inside the 3-concurrent default gear, leaving one slot free, with **no approval gate and no opt-out knob** (a flag or Preferences key would reintroduce the turn-zero configuration DESIGN round 9 exists to avoid — considered and declined). The **spend threshold** is stated with it: automatic spend never exceeds the default gear and is always announced; anything above it is user-initiated. C-701 gains the answer-first entry clause, C-705(d)'s blindness is stated to bind **every** research prompt including the wave's two lanes, C-706 carries the wave and the threshold, and C-715 reaffirms the entry stub — the wave makes content imminent, and the stub is what arms C-718's stance from the first turn. **The round-9 premise this falsifies — that the spawn set is wholly conversation-discovered — is re-argued in `hex/DESIGN.md`'s own 2026-08-30 round**, not here: a fixed two-lane wave inside the default gear is grounding, not turn-zero config. Status Accepted (unchanged). |
| 2026-08-30 | Michael Herwig (owner decision at the `hex-discuss` interactive-rework plan round) | **The lane multi-select replaces the two-gear offer entirely (C-707).** On-demand research is now a multi-select over research lanes, offered **once** immediately after the entry wave dispatches, seeded with the default lane set, carrying the **running spend total** in the chip text and **re-offered only** on user demand or on a new lane surfaced by a returning researcher's `leads:`. The **hard cap of 12 is kept** — now per lane expansion — with the same truncate-and-announce boundary and the same batch-split disclosure under `min(8, limits.max-workers)`; the degraded re-cap is dropped, since there is no second gear to re-cap to. The orchestrator's synthesis duty now also covers **council synthesis** (the N perspective seats into one aside). Retired vocabulary is removed from every normative site: docket row 5, C-707, S-711, the Scalability NFR, and the § Validation cap-boundary and quiet-announce items; the § Open Questions cap item is **annotated with its ratified resolution, never rewritten**, and the round-9 fenced block and all changelog history stay verbatim. Status Accepted (unchanged). |
| 2026-08-30 | Michael Herwig (owner decision at the `hex-discuss` interactive-rework plan round) | **The user ends the interview, and design questions batch (C-709, C-703).** C-709 gains the explicit user-only drain: the skill **never offers to end the discussion**, its whole affordance is one drain-affordance sentence at entry, and the restate-gate is the **completeness check** rather than a stopping heuristic. The inline-drain clause is corrected to net **zero *discussion* files** — research artifacts the entry wave landed persist in the shared research home and are listed in the terminal report (C-715, S-701 amended with it). C-703's strictly-one-design-question-per-turn law is **superseded** by dependency-batched sets of ≤3, each option keeping its attached recommendation, with the three highest-priority shipping when more are pending: the original finding was against undifferentiated numbered lists, and the rework's research (`discuss-ux-sota.md`, `discuss-ux-community.md`) finds a small dependency-ordered batch beats one-at-a-time on turn count and answer quality. Status Accepted (unchanged). |
| 2026-08-30 | Michael Herwig (owner decision at the `hex-discuss` interactive-rework plan round) | **The spawn-contract reference is authorized, and the spawn classes are named (C-701, C-706).** C-701's `references/` split budget is amended from *spent* to **two files, both authorized and both spent** — `reach.md` (C-721, untouched) and the new `references/research-lanes.md` carrying the researcher spawn contract, the open-ended lane catalog and the `negative:`/`leads:` return schema; **a third split needs its own amendment**. C-706 now names **three spawn classes** — (a) automatic entry recon, (b) user-selected opt-in lanes, (c) skill-initiated disputed-fact — with *never on an opinion* binding (a) and (c), and the judgment-question exception **lexically scoped to the opt-in path** so the **perspective council** lane (N same-class seats, distinct assigned perspectives, no mutual ranking, orchestrator-side synthesis) is permitted without a new role or capability class. Cross-model council seats stay out of scope, deferred to a future ADR. Turn-boundary fold-in is recorded with it: a landed result surfaces as a one-line aside flagged as new, a result changing a live thread feeds the next question, and `leads:` entries join the offerable lane set first-seen-wins. The § Validation grep-sweep exclusion list is scoped to `reach.md` alone — `research-lanes.md` is **covered** by the sweep. Status Accepted (unchanged). |
| 2026-08-30 | /hex-review round 2 (doc-drift + cross-model findings; fix pass WP5) | **C-706 — the entry wave's dispatch is stated as two-path, not unconditional.** The prior text read as though the wave always fires after the turn's substance; corrected to name both paths explicitly: **slot 1 present** → the wave dispatches that same turn, right after the substance is emitted (C-701); **slot 1 absent** → the wave defers, firing once when slot 1 lands, seeded from it — slot 1 is never re-asked. **Only an already-dispatched wave is non-repeatable**: a resume never re-fires a wave that already ran, but a discussion parked *before* slot 1 ever landed still gets its wave when slot 1 does. C-701 and C-707's own dispatch phrasing ("after that answer is emitted", "immediately after the entry wave dispatches") were checked against this and left unchanged — both are already conditional on dispatch, not claims that dispatch is unconditional. `hex/DESIGN.md`'s round 11 gains the same clause where it restates the wave. Status Accepted (unchanged). |
