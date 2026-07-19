# hex Worker Registry

The index of roles an orchestrator dispatches during a swarm run.
**Workers are prompt blocks, not shipped agent files** — the orchestrator
copies a role's spawn-prompt template into a subagent it launches (or, in
degraded mode, runs the block inline; see
[`protocol.md`](protocol.md#worker-coordination)). Keeping the roles as
prose makes them portable across clients that shape subagents differently.

Full personas — mission, focus modes, spawn-prompt template, output
contract — live one file per role under [`workers/`](workers/). **Load
only what runs**: the orchestrator always reads this index; it reads a
persona file only for roles in the resolved spawn set
([`protocol.md`](protocol.md#spawn-selection-precedence)).

Model choice is not decided here — every role links to its row in
[`models.md`](models.md). Coordination, concurrency limits, and the
Review-Fix Loop that sequences these roles live in
[`protocol.md`](protocol.md).

## Universal worker protocol

Every worker, regardless of role, follows these:

1. **Read the project's relevant rules and conventions first**, before any
   write. They live in project context (the client's ambient instructions /
   project rules), their locations cached in the Pointers section of
   `.agents/memory/hex.md` (see [`memory.md`](memory.md)). A post-hoc
   self-review is no substitute for reading them up front.
2. **Grep for existing utilities, helpers, and patterns before writing new
   code.** Extend what exists; never work around it. Reinventing something
   that already lives a few files over is the most common waste.
3. **Anchor in the project, not in memory.** Grep project context for the
   stated invariants and conventions of the area you touch; verify claims
   by reading the code. Do not carry assumptions from other codebases.
4. **Report deferred findings instead of oscillating.** If a fix needs
   human judgment or regresses on re-attempt, stop and report it deferred
   with the specific question — do not thrash.
5. **Never auto-commit.** Report status only; the human decides when to
   commit and push.
6. **Return a structured result** in the role's output contract so the
   orchestrator can synthesize across workers without re-reading your work.
7. **Self-check before return.** Run your persona's self-check list; fix
   what it catches in **one** pass — never iterate (an item that regresses
   on the fix goes to deferred, rule 4). A passing self-check carries
   **zero evidentiary weight upstream** — it never substitutes for
   orchestrator-run review; it exists to catch obvious defects before they
   cost a review round. A persona without a self-check list (the read-only
   explorers) is exempt — its template's citation rules are the check.

## Role index

| Role | Mission | Persona | Model |
|---|---|---|---|
| `explorer` | Fast read-only search: locate files, symbols, call sites | [`workers/explorer.md`](workers/explorer.md) | [`models.md`](models.md) |
| `architecture-explorer` | Live-architecture discovery: module map, dependencies, reusable code | [`workers/architecture-explorer.md`](workers/architecture-explorer.md) | [`models.md`](models.md) |
| `researcher` | External research; focus `ecosystem` or `competitive-research` | [`workers/researcher.md`](workers/researcher.md) | [`models.md`](models.md) |
| `builder` | Implementation; focus `stub` or `implement` | [`workers/builder.md`](workers/builder.md) | [`models.md`](models.md) |
| `tester` | Tests; focus `specification` or `validation` | [`workers/tester.md`](workers/tester.md) | [`models.md`](models.md) |
| `reviewer` | Diff-scoped review; focus `quality`, `security`, `performance`, `spec`, or `user-feedback` | [`workers/reviewer.md`](workers/reviewer.md) | [`models.md`](models.md) |
| `doc-reviewer` | Documentation-drift detection | [`workers/doc-reviewer.md`](workers/doc-reviewer.md) | [`models.md`](models.md) |
| `architect` | Design decisions, trade-off analysis, ADRs | [`workers/architect.md`](workers/architect.md) | [`models.md`](models.md) |
| `coordinator` | Owns one decomposable WP; fans out one level of leaves | [`workers/coordinator.md`](workers/coordinator.md) | [`models.md`](models.md) |

## Project-local personas

A project may ship additional personas as `.agents/workers/*.md`
(same format as the files under [`workers/`](workers/)). They fold into
spawn selection as **project hints** — layer 2 of the
[spawn-selection precedence](protocol.md#spawn-selection-precedence) —
and never override a shipped role of the same name. A project-local
persona resolves to the `fast-balanced` class unless its file names a
class or `hex.md › Preferences` overrides it — never a silent escalation
([`models.md`](models.md)).

Naming a persona's role in `perspectives.always`
([`config.md`](config.md#perspectives)) is how it enters a launch list —
the documented persona→panel wiring.
