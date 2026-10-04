# Research: council — which mechanism should hex's per-gate verification choice rest on

## Metadata

- Date: 2026-09-24
- Lane: council (3 seats: premortem, operability, simplicity; blind to each other and to the owner's leaning)
- Discussion: .agents/discussions/verification-levels.md
- Fixed context given to seats: verified-tree memo, fresh full final gate, reviewers run targeted tests only

## Question

(A) keep `scoped`/`full` with structural triggers, projects tier inside their own
scoped command · (B) hex-defined named levels with default gate×change-class
guidance, project-bound commands · (C) gate-time change-class routing on the
existing grades (non-behavioural paths lower, infra/security raise).

## Seat verdicts

- **Premortem → A, refined.** A's observed failure is the hub-file trigger
  firing on every merge (`verify.md` degenerate case) — a predicate fix, not a
  mechanism defect. B fails by vocabulary collision (`tier`, `L0–L3`,
  `scoped|full`) and unbound levels silently falling back to full cost. C fails
  rarely but badly: a "non-behavioural" merge that was cross-cutting, with no
  dependents-of-merged-WP net (adr_0010 D-2); adr_0010 killed the similar A3 on
  the same reasoning.
- **Operability → A.** Structural triggers leave the agent nothing to misjudge,
  and the schedule log already explains why a gate ran full. B adds a fourth
  ordered axis an agent can confuse mid-run; C adds a per-gate subjective diff
  classification and imports the skipped-required-check failure class.
- **Simplicity → A.** B is the largest new surface and duplicates adr_0012's
  risk flags; C's raise half already exists (checkpoint condition 3) and its
  lower half saves little because `scoped` is already cheap. Both reopen doors
  adr_0010/adr_0012 closed.

## Synthesis

- **Agreement (3/3):** no hex-owned level axis (B), and no content-based
  lowering at the **merge** site (C's merge half).
- **Divergence:** premortem wants the hub predicate fixed; operability and
  simplicity want no change beyond the memo.
- **Blind spot all three share:** each assumes the memo removes most of the
  waste. It does not cover a **fix pass that changes only docs/comments** — the
  tree hash changes, so the memo misses, and the pass re-runs the WP's resolved
  verification (`loop.md` L1 "one builder fix pass, re-verified by the WP's
  resolved verification"). In ocx a "small fix batch — messages, doc lines"
  agent ran 6 full verifies. Lowering at an **in-worktree** site is backstopped
  twice (merge scoped check, fresh full final gate); lowering at the merge site
  is not — so the council's merge-site objection does not transfer.
- **Orchestrator recommendation:** A, refined — memo + targeted-only
  reviewers (settled), a narrowed hub predicate, proportional re-verify for
  fix passes at in-worktree sites only, and the owner's "levels as guideline"
  delivered as `/hex-init` advice on how a project tiers its own scoped command
  (ocx T0–T3 as the worked example), not as a runtime hex axis.
