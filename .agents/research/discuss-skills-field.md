# Pre-plan discussion phases in SDD tools — field survey

Researched: 2026-08-27. Expires: 2027-02-28.
Lane: named tools (deep pass; complements `discuss-github.md` breadth pass).

## Sources

- https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md
- https://github.com/github/spec-kit — templates/commands/clarify.md
- https://openspec.dev/docs/quickstart — explore phase
- https://lucumr.pocoo.org/2025/12/17/what-is-plan-mode/
- https://azukiazusa.dev/en/blog/before-implementation-interview-design-requirements-grill-me/
- https://github.com/roy-reshef/socratic-ai-prompt-skill
- https://github.com/anthropics/claude-code/issues/23599 (closed dup)

## Findings

- **superpowers brainstorming**: one question per message, always; hard gate —
  no implementation skill until partner approves intent. Three paths by
  complexity: spike (throwaway investigation), bounded (in-chat design, no
  doc), architectural (dated spec doc, committed). Sections scaled to
  complexity, approve-per-section. Synchronous only — no background research.
- **spec-kit /speckit.clarify**: one-shot command, ≤5 questions, sequential,
  multiple-choice or ≤5-word answers. Appends into the spec under
  `## Clarifications > ### Session YYYY-MM-DD`, propagates immediately,
  saves after each Q (crash-safe). Recommends /speckit.plan next.
- **OpenSpec explore**: pure discussion phase before propose — "writes no
  code and no files. The output is a sharper idea." No forced exit; explicit
  handoff to /openspec-propose. Strongest zero-artifact precedent.
- **Claude Code plan mode**: read-only tool enforcement, but fused with
  plan-authoring — no "just talk, don't plan yet" sub-state. The discuss gap
  is unfilled natively.
- **grill-me** (Pocock): "Ask me questions about every aspect of this plan
  until we have reached a shared understanding. Follow every branch of the
  design tree." One at a time, each with a recommended answer; warns against
  rubber-stamping and against resetting context at implementation — the Q&A
  *is* the design context, doc handoff is lossy.
- **Background research mid-discussion: no shipped prior art anywhere.**
  Only an unimplemented feature request (claude-code#23599). Greenfield.

## Cross-cutting

Every real precedent: one design question at a time, with pushback on the
answer. Open axes the field splits on: artifact-or-not (OpenSpec vs
superpowers), and Q&A-as-context vs compressed-spec handoff (grill-me vs
spec-kit).
