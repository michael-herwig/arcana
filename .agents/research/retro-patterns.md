# Research: retro ledger — clustering, lifecycle, valuation, storage

<!--
Technology-landscape research. Owner: researcher worker (ecosystem lane,
design patterns axis). Handoff to: hex-plan/hex-architect for the
`hex-retro` ledger design.

Purpose: fill the ledger-specific gap left by discuss-retro-priorart.md and
discuss-retro-community.md — fingerprinting/grouping, lifecycle transitions,
recurrence×cost valuation and thresholds, and a git-mergeable storage format.
-->

## Metadata

**Date:** 2026-09-23
**Domain:** observability / error-tracking / ci-cd / agent-config
**Triggered by:** `.agents/discussions/retro.md` § Requirements ledger bullet, § Open Q4/Q5/Q6
**Expires:** 2027-03-23

## Direct Answer

**1. Fingerprinting.** Mature systems all do deterministic-key-first,
model/ML-judged-second. Sentry: `fingerprint` field → stack trace → exception
type/value → message, in that priority order, with per-project override rules
[Sentry grouping-and-fingerprints](https://docs.sentry.io/product/issues/grouping-and-fingerprints/). Buildkite/Trunk flaky detection: same test
identity (suite+test name) producing both pass and fail on the *same commit
SHA* across reruns — a pure identity key, no ML [Buildkite Test Analytics flaky detection](https://buildkite.com/resources/releases/2023-06/flaky-test-tracker/). For LLM-authored free text, the
deterministic analogue is **artifact + kind + a normalized tell** (strip
numbers/paths/timestamps, lowercase, first N tokens or a short hash of the
normalized string) — cheap, stable, no model call. Reserve an LLM clustering
pass for cross-entry merge of near-duplicate tells (paraphrases), and make it
idempotent across runs by match-existing-then-create: feed the model the
existing ledger ids + summaries, force it to either return an existing id or
emit `new`, never regenerate ids from scratch — this is the same fix GSE
(Aug 2026, already in priorart) demands for skill promotion, applied to
clustering.

**2. Lifecycle.** Sentry's model is the concrete, load-bearing precedent:
`resolved-in-release` marks a release+earlier as "expected"; a **regression**
fires only when a *new event* arrives from a release *newer* than the
resolving one — semver-compare if versions are semver, else by release
creation date [Sentry regression semantics](https://www.sentry.help/en/articles/13964279-why-didn-t-my-issue-regress-after-i-resolved-it-in-a-release) [Sentry commit-resolution](https://sentry.zendesk.com/hc/en-us/articles/23158703560859-Issue-resolved-via-commit-message-is-not-marked-as-regressed). Applied to retro: `fixed` records the
artifact **version** that fixed it; a later occurrence only flips it to
`reopened` if it comes from a version ≥ the fix version — an occurrence from
a version the fix predates is noise, not a regression, and this exact bug
class (issues wrongly re-opened as "regressed") is Sentry's own most-reported
complaint against a naive time-based rule [Sentry forum: incorrectly re-opened as regressed](https://forum.sentry.io/t/issues-incorrectly-re-opened-as-regressed/3795). `deferred` is a
third state distinct from `open`/`fixed`: acknowledged, no edit made, still
accruing cost — matches the discussion's existing design, no correction
needed. "Verified by absence" = an N-run or N-day silence window post-fix
before a status could even theoretically read as durably fixed; no surveyed
system fixes a numeric window for this (Sentry's window is "next differing
release", not time), so treat this as ungated — the version-compare rule
above already makes false-reopen unlikely without an extra silence timer.

**3. Valuation + thresholds.** The dominant real-world formula, converging
across flaky-test cost analysis and CI-quality tooling, is
**cost = occurrences × reruns/retries × duration**, i.e. rank by time wasted,
not raw count [CI/CD Watch: cost of flaky tests](https://cicd.watch/blog/flaky-test-cost) [flaky test ranking by time wasted](https://buildpulse.io/compare/best-flaky-test-tools). That is a direct match for the
discussion's "recurrence × cost" framing — use `occurrences × wall_time_lost`
(already the discussion's own metric), not a weighted multi-factor score;
WSJF's `(business value + time criticality + risk reduction) / job size`
[SAFe WSJF](https://framework.scaledagile.com/wsjf) is the wrong tool here — it needs three subjective
Fibonacci-scored inputs per item, meant for human backlog grooming across
heterogeneous work, not for an unattended ledger scoring homogeneous friction
entries against a single objective wall-time signal. Google's SRE toil-budget
convention (cap operational/toil work at 50% of an SRE's time) [Google SRE eliminating toil](https://sre.google/workbook/eliminating-toil/) [Google SRE error-budget policy](https://sre.google/workbook/error-budget-policy/)
is a useful **portfolio-level** sanity check (if retro-ledger'd toil exceeds
some fraction of loop wall time, that's itself a nudge-worthy finding) but
not a per-entry promotion formula. SRE postmortem trackers add one thing
worth stealing: **an owner and a due date make action items land** — postmortem
completion rate below 50% is explicitly called "theater" when items have no
owner [incident.io: SRE postmortem best practices](https://incident.io/blog/sre-incident-postmortem-best-practices) — so every promoted ledger row should carry a routing target
(the discussion's project/harness/upstream split already does this; make
sure the promoted-finding representation always fills it, never leaves it
blank).
Concrete thresholds, opinionated: **PROMOTION BAR = cumulative
`wall_time_lost ≥ 10% of the loop's elapsed wall time so far` OR
`occurrences ≥ 3`** — keep the discussion's own recommendation, it already
matches the flaky-test literature's "rank by time wasted" norm and needs no
import from WSJF/toil. **NUDGE THRESHOLD = 5 open/deferred entries in the
inbox, OR any single `severity: high` entry present** — also as recommended
in the discussion; no source contradicts a low, cheap nudge trigger since
every surveyed consolidation tool defaults to manual invocation, not cron
[netresearch/retro-skill manual invoke](https://github.com/netresearch/retro-skill) [martinalderson.com: cron is aspirational only](https://martinalderson.com/posts/self-improving-claude-md-files/) — the nudge is what stands in for cron here, so keep it
cheap and hard-coded, not model-scored.

**4. Ledger storage.** Confirms and sharpens the discussion's own
recommendation: **committed, one-file-per-finding**, not a single JSON/TOML/
markdown table. This is exactly the changelog-fragment pattern
(towncrier/changie/scriv/reno) adopted industry-wide specifically because a
single shared file with one growing table or list serializes concurrent
writers into merge conflicts on the same anchor line/section, while
per-entry files make two writers' diffs disjoint by construction
[Towncrier docs](https://towncrier.readthedocs.io/en/stable/) — Towncrier stores fragments in `changelog.d/`, one file
per change, named `<id>.<type>.md`, assembled at release time and deleted;
changie is the same model as a Go single-binary with YAML fragments
[Towncrier vs changie comparison](https://towncrier.readthedocs.io/en/stable/), both explicitly built to avoid this exact class of conflict, and a
`.gitattributes merge=union` driver on a single shared file was tried and
rejected industry-wide because GitHub doesn't run merge drivers server-side
for PR-mergeability checks, so PRs still show conflicting even when a local
merge would succeed silently and without list-order guarantees. Recommended
ledger shape: `.agents/retro/ledger/<finding-id>.json` (or `.toml`), one file
per clustered finding — a **derived, small, human-reviewable file per row**,
sorted-key JSON/TOML for stable diffs, `id` = the deterministic fingerprint
from decision 1 so two branches clustering the same raw entries independently
still land on the same filename and merge as an ordinary two-sided edit to
one file (rare) rather than a structural conflict across branches (common
with a single table). The gitignored raw inbox stays exactly as designed
(ephemeral, pre-clustering); only the clustered ledger is committed.

## Recommendation

1. Fingerprint key = `hash(artifact, kind, normalize(tell))`; reserve an LLM
   pass only for cross-fingerprint dedup, run match-existing-then-create
   against the current ledger ids for run-to-run stability.
2. Lifecycle = Sentry's model verbatim: `fixed` records fix version;
   `reopened` fires only on a later occurrence from a version ≥ the fix
   version (not on elapsed time); `deferred` is a first-class third state.
3. Valuation = `occurrences × wall_time_lost`, ranked, no WSJF/toil import.
   PROMOTION BAR: ≥10% of loop wall time OR ≥3 occurrences. NUDGE: ≥5 open/
   deferred entries OR any high-severity entry. Every promoted row must carry
   an owner/routing target — unrouted findings are the postmortem-theater
   failure mode.
4. Ledger = committed, one file per finding under `.agents/retro/ledger/`,
   filename = fingerprint id, sorted-key JSON or TOML — the
   changelog-fragment pattern, not a single table/JSON array.

Artifact: `/home/mherwig/dev/arcana/.agents/research/retro-patterns.md`

## Sources

| Source | Type | Date | Relevance |
|---|---|---|---|
| [Sentry grouping and fingerprints](https://docs.sentry.io/product/issues/grouping-and-fingerprints/) | Docs | current (2026) | Fingerprint→stacktrace→exception→message priority |
| [Sentry: why didn't my issue regress](https://www.sentry.help/en/articles/13964279-why-didn-t-my-issue-regress-after-i-resolved-it-in-a-release) | Docs | current | Regression only on newer-release event |
| [Sentry: commit-resolved regression](https://sentry.zendesk.com/hc/en-us/articles/23158703560859-Issue-resolved-via-commit-message-is-not-marked-as-regressed) | Docs | current | Version-compare, not time-based, regression rule |
| [Sentry forum: incorrectly re-opened as regressed](https://forum.sentry.io/t/issues-incorrectly-re-opened-as-regressed/3795) | Forum | 2026 | Real-world failure mode of naive reopen rules |
| [Buildkite Test Analytics flaky detection](https://buildkite.com/resources/releases/2023-06/flaky-test-tracker/) | Docs/blog | 2023 (**>18mo**, mechanism stable) | Same-SHA pass+fail identity key |
| [CI/CD Watch: cost of flaky tests](https://cicd.watch/blog/flaky-test-cost) | Blog | 2026 | occurrences×reruns×duration cost formula |
| [Buildpulse flaky tool buyer's guide](https://buildpulse.io/compare/best-flaky-test-tools) | Blog | 2026 | Rank by time wasted, not raw count |
| [Google SRE: eliminating toil](https://sre.google/workbook/eliminating-toil/) | Docs | stable | 50% toil budget convention |
| [Google SRE: error budget policy](https://sre.google/workbook/error-budget-policy/) | Docs | stable | Budget-as-gate pattern |
| [incident.io: SRE postmortem best practices](https://incident.io/blog/sre-incident-postmortem-best-practices) | Blog | 2026 | Owner+due-date correlates with action items landing |
| [SAFe WSJF](https://framework.scaledagile.com/wsjf) | Docs | current | Cost-of-delay/job-size formula, ruled out as per-entry mechanism |
| [Towncrier docs](https://towncrier.readthedocs.io/en/stable/) | Docs | current (25.8.0) | changelog.d/ per-fragment pattern, changie comparison |
| [netresearch/retro-skill](https://github.com/netresearch/retro-skill) | Repo | 2026 | Manual-invoke precedent (already in discuss-retro-community.md) |
| [martinalderson.com self-improving CLAUDE.md](https://martinalderson.com/posts/self-improving-claude-md-files/) | Blog | 2026 | Cron consolidation is aspirational, not built anywhere |
