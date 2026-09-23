# Research: retro friction-capture + consolidation prior art

<!--
Technology-landscape research. Owner: researcher worker (competitive-research
lane). Handoff to: hex-discuss (nox-hex-init/retro discussion), later
hex-plan/hex-architect for the `retro` skill design.

Purpose: persist landscape findings that inform the design of (a) a
concurrent friction-capture mechanism for subagents and (b) a `retro` skill
that consolidates captured entries into proposed config edits.
-->

## Metadata

**Date:** 2026-09-23
**Domain:** cli / agent-config / observability
**Triggered by:** discussion `.agents/discussions/retro.md` — entry recon (web)
**Expires:** 2027-03-23 (fast-moving field; several sources <6mo old already)

## Direct Answer

Two loosely-connected literatures exist. (1) Academic agent-memory/self-evolving-agent
research (Reflexion, ExpeL, Voyager, AWM, GEPA, 2025-2026 self-evolving-agent
surveys) treats "capture friction → consolidate → reuse" as a first-class
learning loop, generally at cluster/threshold-then-summarize granularity, and
has hard evidence that raw self-reported difficulty/confidence is a weak
signal — behavioral/trajectory signals (retries, disagreement, tool errors)
predict failure better. (2) Coding-agent product landscape (Claude Code, Cursor,
Windsurf, Cline, Devin, Copilot, Codex, OpenHands) has convergently built
"observe → suggest → human approves" loops for exactly one thing — durable
config (memories/rules/knowledge) — and *none* of them auto-apply the
suggestion without a human gate. Concurrent-capture mechanics has settled
prior art from mail/logging systems (maildir-style atomic-rename
one-file-per-entry beats shared JSONL append under concurrency; JSONL append
only stays atomic under PIPE_BUF and specific filesystem guarantees).
Consolidation prior art clusters by similarity + promotes on a
salience/recurrence threshold, mirroring "seen N times" folk practice.

## Trends

### Established (proven, widely accepted)

- **Human-in-the-loop suggestion, never silent auto-apply.** Every product
  surveyed that lets an agent propose its own config change (Devin Knowledge,
  Cursor Memories, Windsurf Cascade Memories) requires an explicit accept/
  dismiss/edit step from the user. [Devin Knowledge](https://docs.devin.ai/product-guides/knowledge), [Cursor Memories](https://localskills.sh/blog/cursor-memories-guide), [Windsurf Memories](https://docs.windsurf.com/plugins/cascade/memories)
- **Static, human-authored file for durable convention capture** (CLAUDE.md,
  AGENTS.md, `.cursor/rules`, `copilot-instructions.md`, Aider
  `CONVENTIONS.md`) is the universal substrate every "suggestion" loop writes
  into. [AGENTS.md](https://developers.openai.com/codex/guides/agents-md), [Copilot repo instructions](https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot), [Aider conventions](https://aider.chat/docs/usage/conventions.html)
- **Maildir-style atomic rename (one file per entry) is the settled answer for
  safe concurrent delivery from many uncoordinated writers** — write to a temp
  name, `rename()` into place; rename within a directory is atomic on every
  mainstream filesystem, no locking needed, single-writer-per-file discipline.
  [Maildir man page / pattern](https://en.wikipedia.org/wiki/Maildir), [Atomic file mailboxes for agents](https://munderdiffl.in/blog/atomic-file-mailboxes-for-agents/)
- **Cluster-then-summarize + salience/recurrence threshold** is the standard
  consolidation mechanic in memory-architecture work (Stanford Generative
  Agents reflections fire when importance-sum crosses a threshold, e.g. 150).
  [Generative Agents](https://arxiv.org/pdf/2304.03442), [Memory consolidation, explained](https://cognitivx.io/blog/memory-consolidation-ai-agents)

### Emerging (2025-2026, worth watching)

- **Self-evolving agents as a named research area.** A dedicated survey
  ("A Survey of Self-Evolving Agents", Jul 2025) frames capture→consolidate→
  reuse as the central loop toward "artificial super intelligence"; a second
  survey (Feb 2026) reframes agent memory itself as the substrate for
  self-evolution. [Self-Evolving Agents survey](https://arxiv.org/pdf/2507.21046), [Agent Memory in the Second Half](https://arxiv.org/pdf/2602.06052)
- **GEPA / reflective prompt evolution** — natural-language critique of a
  rollout, not just a scalar reward, used to mutate the prompt/config text
  itself; outperforms RL (GRPO) with 35x fewer rollouts. Directly analogous to
  "friction entry → proposed instruction edit." [GEPA paper](https://arxiv.org/abs/2507.19457), [GEPA/DSPy docs](https://dspy.ai/current/api/optimizers/GEPA/overview/)
- **Globalized/cluster-based skill evolution (GSE, Aug 2026)** explicitly
  argues *local* per-episode skill updates overfit and don't generalize;
  proposes a skill-relation graph + cluster-based consolidation + replay
  verification before a skill update is trusted — i.e. dedup/promotion
  needs a compatibility check, not just a count. [Learning Globally Reusable Skills](https://arxiv.org/pdf/2608.06153)
- **`agent-retro` (giannimassi, community skill)** — a Claude-Code-specific
  skill that parses session transcripts for correction/redirect/abandoned-
  approach patterns and tool-result waste, tags each friction item with one
  label from a small fixed vocabulary split by owner (ambiguous-instruction /
  missing-context → instructions; missing-documentation / environment-friction
  → project; agent-error → the agent itself), and proposes concrete skill/rule
  edits. Directly the closest existing artifact to the "retro" skill under
  design; currently single-session, Claude-Code-only, no stated N-occurrence
  promotion threshold or concurrent-capture story. [agent-retro repo](https://github.com/giannimassi/agent-retro)
- **PROJECTMEM (Jun 2026)** — local-first, event-sourced, append-only plain-
  text log of typed events (issue/attempt/fix/decision/note) for coding
  agents, with a "memory-as-governance" pre-action gate that warns before
  repeating a known-failed fix. Independent validation that append-only event
  logs (not vector DBs) are a viable substrate for this exact problem class.
  [PROJECTMEM paper](https://arxiv.org/abs/2606.12329)

### Declining / contested

- **Verbalized self-confidence as a difficulty/failure signal** — repeatedly
  shown weak: GPT-4 self-reported-confidence AUROC for failure prediction is
  ~62.7% (barely above random); confidence is structurally inflated because
  an agent that already committed to an action is incentivized to justify,
  not critique, it; behavioral-consistency and post-hoc verbal-confidence
  (near trajectory end) beat early self-reports. [Confidence calibration overview](https://www.emergentmind.com/topics/confidence-calibration-in-llms), [Behavioral consistency > self-confidence](https://arxiv.org/html/2602.11619v2), [Last Step Matters](https://arxiv.org/html/2608.29685v1)
- **Central-store/last-write-wins shared memory for concurrent agent writers**
  — demonstrated to silently overwrite under concurrency (20/20 trials lost
  writes with N=4 concurrent agents, last-write-wins); community consensus is
  moving toward per-agent branch + explicit merge or append-only-by-default.
  [Shared-state collision analysis](https://deeplake.ai/answers/swarm-communication-shared-state-without-collisions)

## Key Findings

1. **Reflexion (NeurIPS 2023)** converts scalar/binary env feedback into a
   textual self-reflection stored in an episodic buffer and re-injected next
   trial — the original "verbal RL" capture-and-reuse loop, no gradient
   update. [arXiv:2303.11366](https://arxiv.org/abs/2303.11366)
2. **ExpeL (AAAI 2024)** autonomously extracts natural-language "insights"
   from a batch of training trajectories (no fine-tuning), separating capture
   (per-episode) from consolidation (cross-episode insight extraction) —
   structurally the same two-phase split as capture-vs-retro. [arXiv:2308.10144](https://arxiv.org/abs/2308.10144)
3. **Voyager**'s ever-growing skill library stores *executable, verified* code
   skills, only adding a skill after self-verification against env feedback —
   i.e. it gates promotion on execution success, not just LLM-judged
   usefulness. [arXiv:2305.16291](https://arxiv.org/abs/2305.16291)
4. **Agent Workflow Memory (AWM, EMNLP 2024 / ICML 2025 poster)** induces
   reusable multi-step "workflows" from an agent's own past trajectories and
   selectively re-injects them; +24.6%/+51.1% relative success on Mind2Web/
   WebArena, fewer steps to success — concrete evidence the consolidation step
   (not just capture) is where the performance win lives. [arXiv:2409.07429](https://arxiv.org/abs/2409.07429)
5. **Claude Code auto-memory + Stop/SubagentStop hooks** already exist as
   harness primitives: Stop/SubagentStop fire when the (sub)agent finishes;
   a Stop hook's `block`/reason text cannot override system-level auto-memory
   instructions, meaning today's harness treats built-in auto-memory as
   privileged over hook-authored text — a concrete gate this project's own
   capture hook will have to work around or through. [Claude Code memory docs](https://code.claude.com/docs/en/memory), [Hooks + Memory writeup](https://medium.com/@n913239/hooks-memory-automate-claude-codes-reactions-and-build-long-term-memory-22697bd34af1)
6. **Cursor Memories (2025 beta)** uses a separate "sidecar model" that
   observes the chat and *proposes* memories for the user to approve/reject —
   an explicit capture/propose split with a cheaper model doing the noticing.
   [Cursor Memories guide](https://localskills.sh/blog/cursor-memories-guide)
7. **Devin Knowledge** is user-feedback-triggered (Devin suggests a Knowledge
   entry when chat feedback implies something worth remembering), editable
   before saving, and — as of the docs snapshot found — being deprecated in
   favor of "Skills in Plugins," i.e. the product is folding ad hoc
   knowledge-suggestion back into a more structured skill format. [Devin Knowledge docs](https://docs.devin.ai/product-guides/knowledge)
8. **GitHub Copilot repo instructions** are read from the PR's head branch,
   not base — letting an instruction-file edit be tested in the same PR that
   needed it, a lightweight built-in feedback loop without any separate
   "propose" mechanism. [Copilot custom instructions](https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot)
9. **OpenHands microagents** split "always-loaded repo knowledge" (`repo.md`)
   from "keyword-triggered knowledge agents" — an explicit precedent for
   routing consolidated lessons by trigger/scope rather than dumping
   everything into one always-on file. [OpenHands microagents PR](https://github.com/OpenHands/OpenHands/pull/7542)
10. **O_APPEND/JSONL concurrency limits are filesystem- and size-bounded**:
    POSIX atomicity for a single write is only guaranteed for pipes under
    PIPE_BUF, not regular files; practitioners cap records ≤4KiB to stay
    within PIPE_BUF as "atomicity as a property of the format," or move to
    per-process files merged at read time; NFSv3 gives no cross-client
    append guarantee at all. Real torn-append incidents are reported from
    concurrent hook firings. [O_APPEND atomicity discussion](https://linux-fsdevel.vger.kernel.narkive.com/RRQpP2Oj/question-are-concurrent-write-calls-with-o-append-on-local-files-atomic), [torn JSONL appends example](https://github.com/pleaseai/honmoon/issues/140)
11. **Maildir's concurrency answer is "atomic rename, single-writer-per-file,"
    not locking** — each writer creates a uniquely-named temp file then
    renames it into a shared directory; rename is atomic per POSIX/most
    filesystems, so no two writers ever touch the same inode. This is the
    literature's clearest "avoid the lock entirely" precedent, directly
    applicable to "many concurrent subagents record structured friction
    entries." [Maildir (Wikipedia)](https://en.wikipedia.org/wiki/Maildir), [Atomic file mailboxes for agents](https://munderdiffl.in/blog/atomic-file-mailboxes-for-agents/)
12. **Stanford Generative Agents' reflection trigger** is a numeric
    importance-sum threshold over recent memories (150 in the original
    implementation) that, once crossed, triggers an LLM-generated high-level
    "reflection" synthesized from clustered/cited source memories — the
    closest documented analogue to "promote after seen N times." [Generative Agents paper](https://arxiv.org/pdf/2304.03442)
13. **GSE (Aug 2026)** argues per-episode/local skill promotion overfits and
    proposes cluster-based consolidation plus **replay-driven verification**
    before a skill update is accepted — evidence that a promotion mechanism
    needs a correctness check, not just a repetition count, to avoid
    entrenching bad lessons. [arXiv:2608.06153](https://arxiv.org/pdf/2608.06153)
14. **Self-reported LLM confidence is measurably miscalibrated and
    structurally biased upward**: GPT-4 "0.9 confidence" outputs were
    empirically correct only ~72% of the time; confidence AUROC for failure
    prediction is barely above random (62.7%); context growth further
    inflates verbalized confidence over a session. Directly bears on whether
    a subagent's own "this was hard" self-report is trustworthy signal vs.
    noise that should be corroborated with objective trajectory data (retry
    counts, tool error counts, elapsed time). [Confidence calibration in LLMs](https://www.emergentmind.com/topics/confidence-calibration-in-llms)
15. **Behavioral-consistency signals beat verbalized confidence as failure
    detectors** across all three tested models in "When Agents Disagree With
    Themselves" — reinforcing that objective/behavioral trajectory signals
    (disagreement across resampled attempts, by extension retries/errors) are
    the more reliable half of a capture mechanism, with self-reports better
    used as a secondary, human-readable annotation layered on top rather than
    the sole signal. [arXiv:2602.11619](https://arxiv.org/html/2602.11619v2)
16. **PROJECTMEM's append-only typed-event log + pre-action gate** is a
    working (if small-scale: 207 logged events over a 2-month self-study)
    independent implementation of exactly the target architecture: capture
    structured events locally, project them into agent-readable summaries,
    and — beyond passive reuse — actively warn before a repeated failure.
    [arXiv:2606.12329](https://arxiv.org/abs/2606.12329)

## negative: (dead ends, contradicting evidence)

- No source frames "concurrent friction capture" as a solved, named pattern
  specific to *AI agents* — all the hard concurrency evidence (PIPE_BUF,
  O_APPEND, maildir) comes from general systems/mail literature, not agent
  research; agent-memory papers are silent on write-concurrency mechanics
  entirely (they assume single-agent or already-serialized trajectories).
- No product surveyed (Cursor, Windsurf, Devin, Cline, Copilot, Codex,
  OpenHands) auto-applies a self-proposed config edit without a human
  accept/reject step — contradicts any design assuming agents should
  directly write their own instruction files. All require a gate.
- "Seen N times" as a literal, explicit, documented promotion rule was **not**
  found anywhere as a stated design choice — Generative Agents uses an
  *importance-weighted sum* threshold (not a raw count), and GSE explicitly
  argues a raw-count/local-update rule causes overfitting; treat "promote
  after N occurrences" as folk practice, not evidenced best practice, unless
  paired with a compatibility/verification check.
- Central-store shared memory for concurrent multi-agent writers is
  empirically shown to lose writes under last-write-wins (20/20 trials, N=4
  agents) — this is evidence *against* a single shared mutable file/DB for
  concurrent capture, reinforcing the maildir-style alternative rather than
  contradicting it.
- `agent-retro`, the closest existing community skill, explicitly has **no**
  stated deduplication/promotion-threshold logic and **no** concurrent/
  multi-session story per its own docs — it is a starting point, not a
  solved reference implementation, despite looking topically identical.

## leads: (adjacent lanes worth a follow-up, one line each)

- **hooks/PostToolUse mechanics** — a deeper look at exactly which Claude
  Code hook events fire per-subagent (PostToolUse, SubagentStop) and whether
  hook stdout/JSON output can carry structured friction payloads without an
  LLM round-trip, since this determines whether capture can be near-zero-cost.
- **mem0 / mem0.ai multi-agent memory design** — a production vendor's
  concrete conflict-resolution mechanics (branch + explicit merge) for
  concurrent agent writers; worth reading past the blog teaser found here.
- **CODESKILL / EvoClawBench (2605.25430, 2607.09711)** — sibling papers to
  GSE on self-evolving coding-agent skills; not read in depth, may have more
  concrete promotion-threshold numbers than GSE's abstract.
- **flock()-based JSONL append implementations in the wild** — the search
  surfaced the *problem* (torn appends) more than a vetted *solution*;
  worth a targeted look at how existing logging libraries (e.g. structured
  loggers with multi-process support) actually implement the lock-and-append
  path versus the maildir alternative, to compare real overhead.
- **"Documentation rot" / drift-detection tooling** — several product blogs
  (context-rot, doc-drift-check) describe self-verifying instruction files
  that assert against ground truth; adjacent to config bloat risk the retro
  skill's consolidation step must guard against, not covered in depth here.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| [Reflexion (arXiv:2303.11366)](https://arxiv.org/abs/2303.11366) | Paper | 2023 (NeurIPS) | Verbal RL / self-reflection capture loop — **>18mo old** |
| [ExpeL (arXiv:2308.10144)](https://arxiv.org/abs/2308.10144) | Paper | 2023/2024 (AAAI) | Capture vs. consolidation split — **>18mo old** |
| [Voyager (arXiv:2305.16291)](https://arxiv.org/abs/2305.16291) | Paper | 2023 | Skill library, verified-promotion gate — **>18mo old** |
| [Agent Workflow Memory (arXiv:2409.07429)](https://arxiv.org/abs/2409.07429) | Paper | 2024 (EMNLP)/2025 (ICML poster) | Workflow induction from own trajectories — **>18mo old** |
| [GEPA (arXiv:2507.19457)](https://arxiv.org/abs/2507.19457) | Paper | Jul 2025 | Reflective prompt evolution |
| [A Survey of Self-Evolving Agents (arXiv:2507.21046)](https://arxiv.org/pdf/2507.21046) | Survey | Jul 2025 | Field framing |
| [Agent Memory in the Second Half (arXiv:2602.06052)](https://arxiv.org/pdf/2602.06052) | Survey | Feb 2026 | Self-evolving/long-horizon memory survey |
| [Learning Globally Reusable Skills / GSE (arXiv:2608.06153)](https://arxiv.org/pdf/2608.06153) | Paper | Aug 2026 | Cluster-based promotion + replay verification |
| [PROJECTMEM (arXiv:2606.12329)](https://arxiv.org/abs/2606.12329) | Paper | Jun 2026 | Event-sourced local-first agent memory, working system |
| [Confidence calibration in LLMs](https://www.emergentmind.com/topics/confidence-calibration-in-llms) | Aggregator | 2026 | Self-report vs. accuracy evidence |
| [Behavioral consistency as uncertainty signal (arXiv:2602.11619)](https://arxiv.org/html/2602.11619v2) | Paper | Feb 2026 | Objective signal beats verbal confidence |
| [Last Step Matters (arXiv:2608.29685)](https://arxiv.org/html/2608.29685v1) | Paper | Aug 2026 | Early-trajectory uncertainty weak predictor |
| [Claude Code memory docs](https://code.claude.com/docs/en/memory) | Docs | current | Auto-memory mechanics |
| [Hooks + Memory (Medium)](https://medium.com/@n913239/hooks-memory-automate-claude-codes-reactions-and-build-long-term-memory-22697bd34af1) | Blog | May 2026 | Stop/SubagentStop vs. auto-memory precedence |
| [Cursor Memories guide](https://localskills.sh/blog/cursor-memories-guide) | Blog | 2026 | Sidecar-model propose/approve loop |
| [Cursor Rules docs](https://cursor.com/docs/rules) | Docs | current | Rule types (Always/Auto/Agent-Requested/Manual) |
| [Cline Memory Bank docs](https://docs.cline.bot/best-practices/memory-bank) | Docs | current | Structured markdown, git-committed, manual "update memory bank" |
| [Windsurf Cascade Memories docs](https://docs.windsurf.com/plugins/cascade/memories) | Docs | current | Auto-generated + manual memories, 6000-char rule file cap |
| [OpenHands microagents PR #7542](https://github.com/OpenHands/OpenHands/pull/7542) | Docs/repo | 2026 | repo.md vs. keyword-triggered knowledge agents |
| [Devin Knowledge docs](https://docs.devin.ai/product-guides/knowledge) | Docs | current | Feedback-triggered suggestion, editable, being folded into Skills |
| [Aider conventions](https://aider.chat/docs/usage/conventions.html) | Docs | current | Static convention file, read-only cached context |
| [Copilot repo instructions](https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot) | Docs | current | Head-branch read, PR-testable instruction edits |
| [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md) | Docs | 2026 | Cross-tool standard, precedence chain |
| [agent-retro repo](https://github.com/giannimassi/agent-retro) | Repo | 2026 | Closest existing "retro" skill — friction labels, no stated promotion/concurrency logic |
| [O_APPEND atomicity discussion (lkml/narkive)](https://linux-fsdevel.vger.kernel.narkive.com/RRQpP2Oj/question-are-concurrent-write-calls-with-o-append-on-local-files-atomic) | Mailing list | undated (kernel semantics, stable) | PIPE_BUF/O_APPEND atomicity limits |
| [Torn JSONL appends issue example](https://github.com/pleaseai/honmoon/issues/140) | Issue (illustrative) | 2026 | Real-world torn-append failure mode |
| [Maildir (Wikipedia)](https://en.wikipedia.org/wiki/Maildir) | Reference | stable | Atomic-rename, single-writer-per-file pattern |
| [Atomic file mailboxes for agents](https://munderdiffl.in/blog/atomic-file-mailboxes-for-agents/) | Blog | 2026 | Maildir pattern applied to agent messaging |
| [Generative Agents (arXiv:2304.03442)](https://arxiv.org/pdf/2304.03442) | Paper | 2023 | Importance-threshold reflection trigger — **>18mo old** |
| [Memory consolidation, explained](https://cognitivx.io/blog/memory-consolidation-ai-agents) | Blog | 2026 | Cluster-then-summarize, recurrence threshold |
| [Swarm shared-state collision analysis](https://deeplake.ai/answers/swarm-communication-shared-state-without-collisions) | Blog/Q&A | 2026 | Last-write-wins loss evidence, branch+merge alternative |
