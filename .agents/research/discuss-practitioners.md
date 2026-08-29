# Pre-Implementation Discussion Phase — Practitioner Evidence

Researched: 2026-08-28. Expires: 2027-02-28.

## Sources

- https://boristane.com/blog/how-i-use-claude-code/ — HN 976 pts/591 comments; eng lead's research→plan→implement workflow with inline-annotation plan review.
- https://harper.blog/2025/02/16/my-llm-codegen-workflow-atm/ — HN 522 pts/160 comments; "idea honing" one-question-at-a-time conversation → spec.md → prompt_plan.md/todo.md.
- https://steipete.me/posts/just-talk-to-it — prominent independent practitioner (steipete); argues against upfront exhaustive specs, favors live dialogue; explicit Claude-vs-Codex pushback comparison.
- https://news.ycombinator.com/item?id=47623101 — 50 pts/25 comments; "Superpowers" skill framework (brainstorm→spec w/ adversarial review→plan w/ review→implement), mixed verdict on the plan stage.
- https://neonwatty.com/posts/interview-skills-claude-code/ — individual practitioner blog + OSS skill (github.com/neonwatty/claude-skills); AskUserQuestion-based 5–10 round interview gate.
- https://news.ycombinator.com/item?id=44362244 — Ask HN, 19 pts/16 comments; varied concrete tactics, individual comments +69/+20/+19/+11 pts.
- https://simonwillison.net/guides/agentic-engineering-patterns/how-coding-agents-work/ — Simon Willison's agentic-patterns guide; mechanics-only, no discussion-phase content (see Findings note).
- https://news.ycombinator.com/item?id=44232225 (via HN Algolia API, direct fetch 429'd) — plan-mode thread; sparse, contested commentary on plan mode's existence/behavior.

## Findings

### 1. What's praised / demonstrably works

- **Written plan reviewed before code**: Tane's research.md → plan.md → (annotated) → todo.md → implement pipeline is the single most-engaged writeup in this set (976 HN pts). The plan stage is explicitly gated: he tells Claude "don't implement yet" through 1–6 review cycles before ever authorizing code.
- **One-question-at-a-time idea honing**: Harper Reed's prompt ("Ask me one question at a time so we can develop a thorough, step-by-step spec... Each question should build on my previous answers") is the most-cited concrete elicitation pattern in the space (522 HN pts) — it converges on a spec.md judged "developer-ready."
- **Adversarial subagent review of the spec** (Superpowers): "has caught several things I would've missed" (tao_oat, on a 50-pt thread) — praised more consistently than the plan-review step in the same pipeline.
- **Interview-style question gating** (neonwatty's feature-interview skill): forces 5–10 rounds of assumption-surfacing questions ("reveal hidden assumptions / expose edge cases / uncover tradeoffs") behind a mandatory approval checkpoint before any file is written. Concrete outcome: 10 rounds on a party-video-app concept surfaced enough unresolved product questions that the author shelved the idea — evidence the questioning phase can kill work, not just refine it.
- **External model as reviewer mid-discussion** (steipete): drafts a spec, sends it to GPT-5-Pro via chatgpt.com for a second opinion, pastes back what's useful — "surprisingly often, this greatly improves my plan."
- **Explicit non-obvious tactics that HN upvoted** (44362244): sample input/output before requesting code (+69), tests-before-code (+20), a CLAUDE.md of common workflows (+19), capping each request to ~30 min of human-equivalent work (+11).

### 2. What fails / annoys / gets abandoned

- **Plan-stage output judged low-value even inside pipelines that praise the spec stage**: "the implementation plan not being that useful for me to read" (emschwartz); "The plan often ends up being code blocks in a Markdown doc," prompting the open question of whether models are "good enough to get straight to coding once the spec is written" (tao_oat) — both on the Superpowers thread (47623101).
- **Claude Code's native plan mode is inflexible in revision loops**: "would write up a giant plan document and ask for feedback... if you give it feedback, it would respond with a whole new version" (deaux) rather than incrementally editing.
- **Plan mode itself is inconsistently recognized**: on the plan-mode thread (44232225), one commenter says it "enforces this behavior" but is "poorly documented"; another reports "Claude Code denies that it has a plan mode" — contested, thin discussion overall (no deep mechanics thread survived).
- **Skills/process overhead can hurt, not help**: "I think Claude makes more mistakes when using superpowers than when not... It's still the same Claude" (d--b) — a caution against assuming more process structure improves output.
- **Upfront exhaustive spec-writing has a real cost**: steipete says forcing a model to work from a big spec makes it "slowly fetch all files needed to build the feature again," adding roughly "10 minutes to everything" versus starting from a live-discussion context the agent already built.
- **The whole genre is acknowledged as fragile/dated fast**: Harper Reed, in the piece itself: "This is working well NOW, it will probably not work in 2 weeks" — plus a caveat that over-specification forces manual trimming when token budgets tighten.
- **Baseline complaint motivating all of this**: on the Ask-HN tactics thread, the starting problem cited is that roughly half of raw agent output needs substantial cleanup — the discussion/plan phase is positioned as the fix.

### 3. Concrete mechanics

- **Question cadence**: "one question at a time," each building on the prior answer (Harper Reed) vs. a fixed 5–10 round batch gated by mandatory approval before proceeding (neonwatty).
- **Pushback / anti-sycophancy**: steipete's explicit model comparison — Codex "reads much more files in your repo before deciding what to do. It pushes back harder when you make a silly request," vs. "Claude/other agents are much more eager and just try *something*."
- **Background research signaling**: Tane finds passive requests get skimmed; explicit phrasing like "read this folder in depth" / "study...in great details" is required to force deep reads — "Without these words, Claude will skim."
- **Artifact structures**: research.md (codebase understanding) → plan.md (code snippets, file paths, trade-offs) → annotated plan.md → todo.md (Tane); spec.md → prompt_plan.md (chunked codegen prompts) → todo.md (Reed); brainstorm doc → spec (adversarially reviewed) → plan (reviewed) (Superpowers).
- **Handoff phrasing**: Tane's explicit gate-lift command is "implement it all... do not stop until all tasks... are completed," issued only after "add a detailed todo list to the plan." Reed hands the finished spec.md to a separate reasoning model (o1/o3/r1) with instructions to decompose it into codegen-ready prompts — a distinct model swap at the discussion→plan boundary.
- **External-review injection point**: steipete pastes the in-progress spec out to a different vendor's model (GPT-5-Pro) mid-discussion, then folds selected feedback back into the same file before continuing.

### 4. Hard numbers

- Tane (boristane.com): 976 HN points / 591 comments (item 47106686).
- Reed (harper.blog): 522 HN points / 160 comments (item 43094006).
- Superpowers thread (47623101): 50 points / 25 comments.
- Ask-HN tactics thread (44362244): 19 points / 16 comments overall; individual tactic comments at +69, +20, +19, +11.
- Plan-mode thread (44232225): point/comment totals not recoverable (source blocked direct fetch both attempts; only comment text recovered via alternate route).
- simonwillison.net guide: no discussion-phase content found — the fetched page covers system-prompt/tool-loop mechanics only, no plan-mode or pre-implementation-discussion material to extract.
