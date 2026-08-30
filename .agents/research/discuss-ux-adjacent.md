# Research: Mixed-Initiative Interaction and Requirements Elicitation for Concurrent-Computation Dialogues

<!--
Technology-landscape research. Filename and location: this project's
documented research convention (.agents/research/).
Owner: a researcher worker. Handoff to: hex-discuss UX discussion.

Purpose: persist landscape findings that inform the discussion design.
Findings decay - check the Expires date before trusting them.
-->

## Metadata

**Date:** 2026-08-30
**Domain:** HCI / requirements engineering (mixed-initiative UX, elicitation methodology)
**Triggered by:** hex-discuss UX discussion
**Expires:** 2027-02-28

## Direct Answer

Both fields converge on the same shape of answer: **structure the default, but
let evidence override it.** Mixed-initiative HCI says the system should stay
quiet unless the *expected utility of interrupting* exceeds the *expected cost
of the interruption* — a bounded-deferral policy, not a hard rule of "always
wait" or "always interrupt." Concretely: don't push a background result into
the dialogue mid-turn; surface it at the next natural breakpoint (turn
boundary), flagged as new rather than blended into the flow, and let the user
decide whether to engage now or later. Requirements-elicitation literature
says the same for closing a session: end on evidence of completeness (a
closing question goes unanswered, new information stops surfacing) rather
than on a checklist being exhausted or a clock running out — and treat rigid
checklists and topic-tunneling as named failure modes, not neutral defaults.

## Key Findings

1. **Mixed-initiative interaction is a cost/benefit trade, not a mode
   toggle.** Horvitz's foundational CHI'99 paper frames the core design
   problem as choosing when automation should act autonomously vs. defer to
   the user, driven by uncertainty about the user's goals; his listed
   principles include developing significant dialogue only to resolve
   high-value uncertainties, minimizing the cost of a bad guess, and — most
   relevant here — attending to the user's current focus of attention and the
   cost of interrupting it. [Horvitz, CHI'99]
2. **Bounded deferral: cap the wait, don't eliminate it.** Horvitz, Jacobs &
   Hovel's "Attention-Sensitive Alerting" formalizes this as an expected-
   utility computation that weighs the cost of interrupting now against the
   cost of the delay in delivering the alert, then defers up to a bounded time
   window rather than either firing immediately or holding indefinitely. This
   is the direct analogue for background research results in a live
   discussion: surface at the next turn boundary (bounded), not the instant
   the subagent returns (interrupt) or only when the user explicitly asks
   (unbounded staleness). [Horvitz, Jacobs & Hovel, UAI'99]
3. **Empirical support for deferring to interruptible moments.** A
   large-scale study (680k+ users) found delaying notification delivery until
   a detected interruptible moment cut user response time by roughly half
   (49.7%) versus immediate delivery — evidence that timing, not just content
   relevance, drives whether an interruption reads as helpful or disruptive.
   [ScienceDirect, adaptive notification scheduling]
4. **Relevance moderates perceived disruption.** Iqbal & Bailey's CHI'08 work
   on intelligent notification management found users perceive less
   disruption when an interruption is highly relevant to the task at hand,
   and that perceived disruption scales with the user's mental load at
   arrival — i.e., a background result about the exact question just
   discussed lands very differently from a tangential one, even at the same
   timing. [Iqbal & Bailey, CHI'08]
5. **Current agentic-UX practitioner writing converges on "surface, don't
   inject."** Recent design-pattern write-ups (UX Magazine, Mania/Sandhya
   Hegde, Hatchworks) describe async agent work as arriving as discrete
   "suggested observations" added to a visible surface rather than spliced
   into the transactional turn-taking flow, with explicit start/stop/pause
   controls and a preference for showing decision highlights over raw output
   — the goal being that the user can inspect and act on results without the
   agent forcing engagement. One documented failure mode: background-task
   notifications injected as if they were user messages pollute conversation
   history and get mis-attributed. [UX Magazine; Mania; Hatchworks;
   NousResearch/hermes-agent#35298]
6. **Elicitation interviews follow a four-stage arc, and structure is a
   scaffold, not a script.** The standard model is prepare (identify
   stakeholders, define goals) → interview → record → integrate/synthesize.
   Structured formats (JAD, paper prototyping) trade spontaneity for
   consistency; unstructured interviews trade consistency for depth. No
   source treats either extreme as correct in general — the choice is
   context-dependent. [GeeksforGeeks; Apriorit; ScienceDirect family-of-
   experiments study]
7. **Question sequencing: broad-to-narrow (funnel) is the default shape.**
   The funnel technique — open questions first, narrowing to specific/closed
   questions — is recommended because unprompted information is more likely
   to reflect the stakeholder's actual priorities than answers to a
   pre-narrowed question, and because open questions build rapport before the
   interviewer imposes structure. The inverse (narrow-to-broad) and tunnel
   (single-topic, no breadth) sequences are named as situational, not
   default. [NN/g; UXtweak; w3computing]
8. **Interviewer-induced bias is a documented, specific failure mode.**
   Academic work on elicitation-question typology names "content
   maneuvering" — phrasing that steers toward a preferred answer, e.g.
   forced-choice questions that presuppose the answer set — as a bias
   mechanism, and "tunneling" — over-focusing on one topic at the expense of
   necessary breadth — as a structural failure that a rigid line of
   questioning falls into even without intent to bias. [York U, RE2021
   typology paper]
9. **Premature closure and checklist rigidity are named, opposing failure
   modes.** Overly rigid checklists are repeatedly flagged as suppressing the
   natural, adaptive follow-up that surfaces real requirements — "a set of
   problems to solve, not a checklist" — while too little structure risks
   incomplete or inconsistent coverage. Practitioner guidance places the
   decision to close a session on evidence (a closing question — "is there
   anything important we haven't discussed?" — goes unanswered, or time
   budget is reached) rather than on exhausting a predefined list, and treats
   follow-up sessions as the standard safety valve for time-constrained or
   incomplete interviews rather than a failure to plan properly.
   [datavidhya; BATimes; CS ODU elicitation notes]

## Sources

| Source | URL |
|---|---|
| Horvitz, "Principles of Mixed-Initiative User Interfaces," CHI'99 | https://dl.acm.org/doi/10.1145/302979.303030 |
| Horvitz, Jacobs & Hovel, "Attention-Sensitive Alerting," UAI'99 | https://arxiv.org/abs/1301.6707 |
| Adaptive notification scheduling, large-scale study | https://www.sciencedirect.com/science/article/abs/pii/S1574119217304388 |
| Iqbal & Bailey, "Effects of Intelligent Notification Management," CHI'08 | https://interruptions.net/literature/Iqbal-CHI08.pdf |
| UX Magazine, "Secrets of Agentic UX" | https://uxmag.com/articles/secrets-of-agentic-ux-emerging-design-patterns-for-human-interaction-with-ai-agents |
| Mania (Sandhya Hegde), "Agentic UX & Design Patterns" | https://manialabs.substack.com/p/agentic-ux-and-design-patterns |
| Hatchworks, "Agent UX Patterns" | https://hatchworks.com/blog/ai-agents/agent-ux-patterns/ |
| Background-notification-as-user-message bug report | https://github.com/NousResearch/hermes-agent/issues/35298 |
| ScienceDirect, "Requirements elicitation methods based on interviews... family of experiments" | https://www.sciencedirect.com/science/article/abs/pii/S0950584920301282 |
| Apriorit, "Requirements Elicitation in Software Engineering" | https://www.apriorit.com/white-papers/699-requirement-elicitation |
| NN/g, "The Funnel Technique in Qualitative User Research" | https://www.nngroup.com/articles/the-funnel-technique-in-qualitative-user-research/ |
| York U, "Towards a typology of questions for requirements elicitation interviews," RE2021 | https://www.yorku.ca/liaskos/Papers/RE2021/RE2021.pdf |
| datavidhya, requirements-gathering checklist critique | https://datavidhya.com/learn/de-system-design/the-framework/requirements-gathering/ |
| BATimes, "8 Tips for a successful Requirement Elicitation" | https://www.batimes.com/articles/8-tips-for-a-successful-requirement-elicitation/ |
| CS ODU, "Eliciting Requirements" course notes | https://www.cs.odu.edu/~zeil/cs350/latest/Public/eliciting/index.html |
