# Research: Practitioner experience with iterative AI/agent code review loops

## Metadata
Date: 2026-08-30
Expires: 2027-02-28

## Question
For review→fix→re-review cycles, do tools/teams re-review the whole diff each
round or only what changed since the last round? What review-fatigue/cost
complaints show up around full-diff re-review, what do practitioners report
about AI reviewers (CodeRabbit, Copilot code review, Codex review, custom
agent panels) across repeated rounds — duplicate findings, drift, cost per
round — and what scoping strategies are actually reported in use.

Stance: neutral evidence gathering, no recommendation.

## Findings

**Full-diff re-review is the reported default failure mode, not an edge case.**
GitHub Copilot Code Review, when its "run on each push" auto-review rule is
on, does a full re-scan of the entire diff on every push rather than just the
delta ([GitHub community discussion #189767](https://github.com/orgs/community/discussions/189767)).
Practitioners in that thread documented a single PR going through 5 review
rounds with comment counts of 10 → 6 new → 4 new → 2 new → 2 more, and
complained: "Our developers spend unnecessary time because of copilot's
review over again on the same lines of code" and "If Copilot can find an
issue on round 3, it should find it on round 1." Copilot is also reported to
sometimes repeat comments that were already resolved or downvoted
([GitHub Docs](https://docs.github.com/en/copilot/using-github-copilot/code-review/using-copilot-code-review)).

**CodeRabbit is the one tool in this set that ships an explicit incremental-vs-full
distinction as a first-class command**, rather than leaving it implicit:
`@coderabbitai review` triggers an incremental review of only new changes
since the last review; `@coderabbitai full review` explicitly re-reviews
everything from scratch ([CodeRabbit docs](https://docs.coderabbit.ai/reference/review-commands)).
This is the clearest evidence found of a tool-level scoping mechanism a team
can invoke deliberately, as opposed to a default behavior they have to work
around.

**Cost scales directly with re-review frequency, and teams report treating
trigger configuration as their main cost lever.** A tool set to review on
every push "re-reviews the same pull request each time a developer pushes a
fix, a rebase, or a response to earlier comments, so a PR that goes through
six commits before merge can generate six billable reviews instead of one"
([Codacy blog, 2026](https://blog.codacy.com/ai-code-review-cost-per-pull-request-what-engineering-teams-actually-pay-in-2026)).
The same piece notes cost scales with diff size, so the changes that most
need careful re-review (large refactors) are also the most expensive to
re-run — creating pressure to "ration review to smaller and lower-risk
changes precisely because the expensive option is the one they can least
afford to skip." Reported reviewer pricing in the wild ranges widely: from
under $0.02/review for lightweight implementations up to ~$15–25/PR for
Anthropic's Claude Code Review on typical PRs, and $0.45/file capped at
$50/dev/month for one commercial tool (HN commenter called this "expensive
... for a glorified linter") ([HN #42451968](https://news.ycombinator.com/item?id=42451968)).

**Signal-to-noise complaints are the dominant practitioner theme, and compound
across rounds.** Multiple independent write-ups converge on the same rough
figure: most AI code review tools generate 10–20 comments per PR, and roughly
70–80% are noise (style nits, naming suggestions, wording) rather than
real bugs ([HN: "Are you drowning in AI code review noise? 70% of AI PR
comments are useless"](https://news.ycombinator.com/item?id=45772215);
[dev.to signal/noise framework](https://dev.to/jet_xu/drowning-in-ai-code-review-noise-a-framework-to-measure-signal-vs-noise-304e)).
In the Copilot discussion thread specifically, of ~24 comments across review
cycles on one PR, only ~3 were judged genuinely useful (crash-causing bugs);
the rest — things like "error message wording" — got the same Medium
severity label as real runtime errors, which practitioners flagged as
actively harmful to triage. Research cited on 22,000+ real review comments
found concise, code-snippet-bearing, manually-triggered comments (especially
hunk-level ones) were far more likely to lead to an actual code change —
i.e., scope and framing affect whether a re-review round is worth anything,
independent of raw finding count.

**Practitioner-requested workarounds (not built into tools at time of
writing) point at what scoping strategies people actually want:** limiting
re-review scope to "verify the previous fix only" rather than re-scanning
everything; severity filtering/thresholds so nits don't compete with
crash-level findings; an explicit "stop reviewing" state once a PR is judged
done. No built-in mechanism for these was found in the Copilot thread as of
the writing surveyed.

**Multi-agent / custom review-fix loop patterns (not a specific commercial
product) report explicit convergence tracking rather than a fixed round
count**, which functions as a scoping strategy of its own: one write-up
describes findings dropping monotonically round over round (7 → 4 → 2 → 2 →
1 → 0/CLEAN by round 8), with a stated best practice of capping self-review
cycles at 2–3 rounds to avoid diminishing returns
([AgentPatterns.ai / Zylos research summary](https://zylos.ai/research/2026-03-01-multi-model-ai-code-review-convergence/)).
The same family of write-ups names an **oscillation** failure mode specific
to iterative fix loops: fixing issue A in round 2 can introduce issue B; fixing
B in round 3 can reintroduce A. Reported mitigations: an explicit approval
signal plus an iteration budget plus diminishing-returns detection as the
stop condition; context isolation / an explicit `complete_review` action to
prevent circular reasoning; capping automated fix attempts at one pass and
escalating to a human rather than continuing to loop when a fix doesn't
resolve cleanly.

**Non-determinism across rounds is called out as a distinct problem from
noise volume**: re-running review on the same diff can surface a different
set of issues each time ("it's non-deterministic, so you end up with half a
dozen commits, with each run noting different issues" —
[HN #46766961](https://news.ycombinator.com/item?id=46766961)), which
undermines any "only re-review the delta" strategy that assumes a stable
baseline of prior findings to diff against.

**Uber's internal uReview tool** was found and fetched as a candidate primary
source on scoping strategy but did not yield direct evidence either way: the
public write-up describes deduplication *within* one review pass (a semantic
similarity filter merging overlapping suggestions) and a *post-hoc*
verification step (5 re-runs against the final commit to check whether a
comment was addressed), but does not document whether normal push-triggered
review re-scans the whole diff or only the delta
([Uber Engineering blog](https://www.uber.com/ug/en/blog/ureview)).

## negative
- Could not find a Reddit thread directly matching the query (CodeRabbit/Copilot
  duplicate-comment complaints specifically on r/programming, r/ExperiencedDevs,
  etc.) — search tooling returned only doc pages and DEV.to articles for
  reddit-scoped queries; HN and GitHub Discussions substituted as the
  community-thread evidence instead.
- Uber's uReview post was a promising primary source (real engineering team,
  named tool) but does not actually answer the round-over-round scoping
  question — don't cite it as evidence for "full diff vs incremental" either
  way.
- No practitioner report found of a team explicitly measuring or stating
  "cost per re-review round" as a tracked metric (e.g., $X on round 1, $Y on
  round 2) — cost complaints are about aggregate/monthly spend or per-PR
  averages, not a round-by-round breakdown.

## leads
- CodeRabbit CLI (local, pre-PR review) as a distinct lane — same tool, but
  local/interactive review may have different re-review scoping norms than
  its PR-bot mode; not explored here.
- The "oscillation" / fix-reintroduces-earlier-issue failure mode (AgentPatterns.ai,
  Zylos) is itself a rich adjacent lane — convergence-detection and
  stop-condition design for iterative agent loops generally, beyond code
  review specifically.
- HN "There is an AI code review bubble" (https://news.ycombinator.com/item?id=46766961)
  has broader market/skepticism commentary beyond the loop-specific excerpt
  pulled here — worth a dedicated pass if market-perception is in scope.
- Anthropic's Claude Code Review pricing ($15–25/PR) vs. DIY alternatives
  (under $0.02/review) is a cost-comparison lane of its own, referenced here
  only in passing.
