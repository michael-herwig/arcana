# Pushback / anti-sycophancy mechanics in discussion skills

Researched: 2026-08-28. Expires: 2027-02-28.
Question: concrete instruction wording that makes an agent genuinely
challenge the user, plus adaptive-artifact-structure precedents.

## Sources

- https://vibehackers.io/claude-code/skills/anti-sycophancy-sickn33
- https://github.com/brandonsimpson/devils-advocate
- https://github.com/bmad-code-org/BMAD-METHOD — src/core-skills/bmad-advanced-elicitation/SKILL.md
- https://www.mindstudio.ai/blog/prevent-ai-sycophancy-adversarial-council-prompts
- https://adr.github.io/madr/decisions/adr-template.html
- https://github.com/anthropics/claude-code/issues/46427 (failure mode)

## Findings — pushback patterns (wording is the deliverable)

- **Rebuttal categorization**: "Categorise the pushback: is it new evidence
  or repeated opinion? If new evidence → update your position, state what
  changed. If repeated opinion → restate your position with the evidence."
  Also: extract the user's core claim stripped of premises; assess it
  independently of user agreement/authority. Cleanest gate against
  "reversed under pushback with no new argument" (claude-code#46427).
- **devils-advocate**: binary pass/fail per criterion ("no percentage
  scores, no wiggle room"); anti-theater rule — "forbidden from
  manufacturing problems to appear thorough. 'Do nothing' is a valid
  outcome."; independence gate — reviewer "never sees the author's
  reasoning, only the artifact and codebase."
- **BMAD advanced elicitation**: category-scoped menu — "pick the 2–4
  categories that fit the target (risk before a launch, technical for code,
  collaboration when stakeholders compete...)". Methods incl. premortem,
  inversion, first-principles, red-vs-blue. The menu pattern is the steal;
  the 50+ method catalog is overkill.
- **Forced-critique templates**: devil's advocate — "Do not: Acknowledge
  strengths unless they directly set up a counterargument." Premortem —
  "Assume this plan was implemented and failed badly... what went wrong?"
  Force-rank top-5 problems. Scored-but-forced — "If the score is above 7,
  list at least three things that prevent it from being a 9 or 10."

## Findings — adaptive structure

- MADR "More Information" section: "Links to other decisions and resources"
  — the phrasing precedent for a Related section (arcana ADRs already MADR).
- No collection ships explicit "omit empty sections" / progressive-
  elaboration wording except obra/superpowers brainstorming ("sections
  scaled to complexity"). Single-precedent; treat as a design choice, not a
  field convention.
