# Parity Oracle — a gate hex does not have

Handover from `grimoire-lore`, 2026-08-16. Not a decision, not a plan —
a gap worth discussing before it gets designed.

## The gap

`/hex-execute` and `/hex-review` both treat the project's own test suite
as the thing that says whether a change is safe. On feature work that is
correct: the suite was written against the behaviour being added.

On a **restructure** it is not. The suite was written against the old
shape. It proves the pieces still fit, not that they still do the same
thing. A 100%-green run is the normal state of a refactor that shipped a
regression — the type system checked the wiring and nothing checked the
behaviour.

So there is a class of change where hex's implicit gate is structurally
unable to fail, and hex has no way to notice.

## What a parity oracle is

A behavioural snapshot captured from the **pre-change** binary and
committed before the first code-move commit: stdout, stderr, exit code,
and filesystem effects for a set of representative invocations.

Two properties make it a gate rather than a build check:

1. **It predates the change.** A suite written or edited during the
   restructure cannot gate it — it encodes the new shape by construction.
2. **It has a measured detection rate.** Inject faults; count how many the
   oracle catches. If you cannot state that fraction, you have a build
   check. This is the part that makes it falsifiable, and it is the part
   every "we have tests" argument skips.

The oracle then re-runs at **every merge point**, not only at the end.
Localising a regression one move later is far cheaper than after fifty.

## Why it lands in arcana and not in a Rust catalog

None of the above is Rust. The Rust-specific move hazards (borrow-duration
changes on method conversion, `debug_assert!` compiled out in release,
extracted crates dragging dependencies with them) now live in
`rules/rust-quality/restructuring.md` in `grimoire-lore`. What is left is
a refactoring discipline that applies to any language and belongs next to
the orchestrator that would enforce it.

## Open questions for the discussion

- **Which skill owns it.** A restructure has a plan phase and an execute
  phase; the oracle is built in the first and consumed in the second. That
  is either a new tier in `/hex-execute`, or a distinct orchestrator.
- **Is it a tier or a mode?** Restructuring is not "bigger execution" —
  the phase order differs (oracle before decomposition), so a `high` tier
  may be the wrong lever.
- **Where the detection rate is recorded** so a later phase can refuse to
  merge against an unmeasured oracle. `hex.md › Memory` is the obvious
  home; whether a *number* belongs in memory is not obvious.
- **Overlap with the convergence contract.** Both ask "did the delivered
  code do what was promised". Convergence checks against plan IDs; parity
  checks against prior behaviour. Related, not the same, possibly one
  mechanism.
- **Cheap fallback when no oracle can be built.** The lore rule says the
  first work package then *is* building the oracle, and the restructure
  waits. Whether hex should be able to refuse a run is a policy call.

## Source

`.agents/research/large-scale-ports.md` in `grimoire-lore` (26.6K, cited)
is the research behind this, and is the thing to read before designing
anything here.

The distilled version lived at
`skills/rust-restructure/references/parity-harness.md` in that repo —
characterization snapshots, the mutation baseline, which suite may gate,
absent-call guards. It was deleted along with the skill and **nothing in
that repo is committed to git**, so it is not recoverable: this file plus
the research source are what is left. Re-distilling from the research is a
short job; hunting for the deleted file is not.
