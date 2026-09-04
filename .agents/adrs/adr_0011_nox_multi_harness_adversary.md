# ADR: nox — a multi-harness adversarial-review library

## Metadata

**Status:** Accepted (Michael, 2026-09-02, at the /hex-plan gate)
**Date:** 2026-08-31
**Deciders:** Michael Herwig
**Issue/Ticket:** N/A
**Related PRD:** N/A — drained from
[`.agents/discussions/nox-multi-harness-adversary.md`](../discussions/nox-multi-harness-adversary.md)
(ratified 2026-08-31)
**Architectural Conventions:**
- [x] Decision follows this project's stated architectural conventions /
      golden path
- [ ] OR the deviation is justified in the Rationale section below
**Domain Tags:** security, integration, infrastructure, developer-experience
**Supersedes:** N/A
**Superseded By:** N/A

**Companion:** [`adr_0011_system_design.md`](adr_0011_system_design.md) — C4,
threat model, failure-mode tables, rollout sequence. **Where the two
disagree, this file's contract text is canonical.**

Contracts are numbered `C-10xx`. The system-design doc restates them in
buildable form and derives from them; it never introduces a contract of its
own.

## Context

`openai/codex-plugin-cc` (Apache-2.0, 32.6k stars) gives Claude Code an
adversarial reviewer backed by Codex
([`discuss-nox-priorart.md:12`](../research/discuss-nox-priorart.md)). It is
single-vendor in both directions: only Codex reviews, and only Claude Code
can ask. Nothing in it generalizes — the transport is Codex's app-server
JSON-RPC, the host is a Claude Code plugin, and the review primitive
(`review/start`) exists only in one vendor's protocol.

**What it therefore does not cover, stated without inflation.** hex's adversary
seam is already vendor-neutral — `adversary: <skill-name>` in
`hex.md › Preferences`
([`protocol.md` § Adversary contract, ~:1210](../../hex/hex-core/references/protocol.md),
pinned today to `codex:rescue` at
[`.agents/memory/hex.md:30`](../memory/hex.md)) — and it degrades gracefully
when the named skill is absent. **The seam is not the gap, and neither is the
Claude↔Codex direction v1 actually ships.** That pair is covered twice over
already: publicly by `codex-plugin-cc`, and on this machine by the installed
`codex:rescue` skill the pointer is pinned to. The discussion's own council
synthesis said so
([discussion:~118](../discussions/nox-multi-harness-adversary.md)), and the
uncovered *direction* value it identified — Copilot, Cursor, and Claude invoked
as reviewer from a non-Claude harness — arrives with the Copilot and Cursor
adapters, which are Out of v1 (§9.1 of the companion).

So v1's differentiator is not direction coverage. It is three things, and the
ADR is only entitled to claim these:

1. **OpenCode as a review participant at all.** No prior art drives it, and it
   is the one BYOK leg, so it is nox's widest cross-model reach.
2. **The containment posture.** `codex-plugin-cc` runs the reviewer in the
   user's tree; nox does not. That is the first-of-its-kind claim, and it is
   what the rest of this document is about.
3. **The facade.** Copilot and Cursor become four-step additions (§9.3 of the
   companion) rather than new products.

v1 is therefore the proving ground for a containment posture and an extension
point, re-implementing one already-covered pair to build them. Success for v1
is not "a direction nobody had"; it is "a boundary nobody had, on three
harnesses, with the fourth and fifth cheap."

**v1 targets three harnesses: Claude Code, OpenCode, and Codex — and that set
is an owner constraint on this decision, not an output of it.** The set was
fixed by the owner after the discussion drained and after a two-harness draft
existed. The isolation question below is decided *against* that set; it is not
decided jointly with it. This matters for how the rest of the document reads:
the security lane's first-listed resolution of the OpenCode asymmetry was "drop
OpenCode from v1" ([`nox-security.md:938-943`](../research/nox-security.md)),
and it is absent from the options below because scope excludes it, not because
the analysis defeated it. Stating the constraint also breaks a circle a reader
would otherwise be trapped in — OpenCode motivates the worktree, and the
worktree motivates the third harness — and it makes the argument for the chosen
option *shorter*, not longer: with a harness that has no flag-based containment
fixed in scope, the permissive options are unshippable rather than merely
low-scoring.

**Why this is a one-way door.** nox spawns the user's own logged-in AI coding
harness, on the user's laptop, with the user's full ambient authority — SSH
keys, cloud credentials, npm/PyPI tokens, and the harness's own long-lived
subscription credential — and feeds it a diff, which is untrusted content by
construction. The security research is unambiguous that the dominant risk is
not the model obeying injected text; it is that **the tree under review
contains the harness's own configuration, and all three target harnesses read
it** ([`nox-security.md:33-37`](../research/nox-security.md) states this for
Claude Code and OpenCode, being written before Codex entered v1 scope; the
Codex leg is addendum 2,
[`nox-security.md:1206-1242`](../research/nox-security.md)). The public Python
surface, the isolation posture and the failure taxonomy are external contracts
that later adapters and later consumers will be written against. Getting the
isolation posture wrong does not degrade — it silently grants arbitrary code
execution.

### The three-way asymmetry

The question is narrow and answerable: **is "safe against a hostile branch, in
the same working tree, via flags alone" achievable per harness?** The security
lane assessed all three from local `--help` output and vendor documentation
([`nox-security.md:1206-1242`](../research/nox-security.md)).

**Read the confidence column before the verdict column.** The lane states
plainly that **no empirical test was run for any harness**
([`nox-security.md:1281-1284`](../research/nox-security.md)), that **OpenCode
was not installed** on the research machine and that its config-precedence claim
in particular could not be verified
([`nox-security.md:727-731`](../research/nox-security.md)), and that **no Codex
command was executed beyond `--help`**. The Claude Code column is `--help` text
plus docs; the Codex column is `--help` text plus docs whose pages 404'd in
places; the OpenCode column is documentation and an issue tracker only. Nothing
in this table is observed behaviour. The version label is also drifting under
the table: the lane verified `claude` **v2.1.251**
([`nox-security.md:1206`](../research/nox-security.md)) and the same machine
reports **v2.1.252** while this ADR is written — relabelled below because the
column is the flag surface, not the build, but that relabelling is itself an
instance of decision driver C2 and should be read as such.

| | Claude Code 2.1.252 (verified 2.1.251) | Codex 0.144.1 | OpenCode 1.18.22 (not installed) |
|---|---|---|---|
| Repo config gate, non-interactive | **fails open** — hooks "Used", `.mcp.json` "Connected without asking" | **fails closed** — untrusted project layers ignored… but trust is **path-scoped** | **fails open** — project `opencode.json` outranks `OPENCODE_CONFIG` *(explicitly unverified — [`nox-security.md:727-731`](../research/nox-security.md))* |
| Second gate on hook/plugin code | none | **content-hash hook trust — new/changed hooks skipped** | none |
| Repo-directory code autoload | no | no | **yes — `.opencode/plugins/` at startup** |
| Off-switch for repo MCP | `--strict-mcp-config` | **none** (`-c mcp_servers={}`, unverified) | none documented |
| Credential-key protection in project config | none | **explicit blocked-key list** | none |
| OS-level sandbox | opt-in, off by default, degrades silently, no native Windows | **on by default** — Seatbelt / Landlock+seccomp / restricted token | none |
| **Researcher's verdict** | Yes, via flags | Yes, via flags | **No** |

Read at face value that is 2–1, and it points at treating OpenCode
differently. Two details underneath it point the other way, and they are what
this ADR turns on.

**First: Codex's project-trust gate does not defend nox's threat model.**
Trust is scoped to a **path**, not to a **commit**. The user's own repository
is already trusted, so a hostile *branch* checked out into that same path
inherits that trust. The gate defends against a hostile *repository*; nox's
threat is a hostile *branch in a trusted repository*
([`nox-security.md:1044-1050`](../research/nox-security.md)). What actually
saves Codex is the second, independent gate: hook trust is recorded against
the hook's **current hash**, so "new or changed hooks are marked for review
and skipped until trusted", and untrusted hooks are skipped non-interactively
([`nox-security.md:1086-1090`](../research/nox-security.md)). That is a real
structural defence — and it covers hooks only.

**Second: Codex's "yes, via flags" carries a stated residual.** `mcp_servers`
is not on the blocked-keys list, there is no `--strict-mcp-config` analogue on
`codex`, `codex exec`, or `codex exec review`, and a stdio MCP entry spawns a
command. The researcher's own minimum-mitigation line for Codex ends:
"**Residual accepted risk: repo-declared MCP servers in an already-trusted
project**" ([`nox-security.md:1232`](../research/nox-security.md)), with the
only candidate mitigation — `-c mcp_servers={}` — explicitly untested and its
table merge-versus-replace semantics undocumented.

So the honest reading of the table is **not** 2–1. It is: one harness with no
containment story at all, one whose containment rests on flags that are
`--help`-only and untested against `-p`, and one that is genuinely well
designed and still leaves a documented open hole between a hostile branch and
a spawned command. § *Decision Outcome* returns to what closes all three at
once.

### The constraint this ADR reopens

The discussion settled *"Isolation: read-only same working tree, diff passed
in the prompt. No per-adversary worktree, no container"*
([discussion:64](../discussions/nox-multi-harness-adversary.md)) and listed
worktrees under *Out of scope*
([discussion:252](../discussions/nox-multi-harness-adversary.md)). That
decision was taken against a threat model the security lane falsified. The
lane also corrects the framing of what a worktree is *for*:

> A worktree's security value is not isolation from the attacker — it is that
> it gives nox **a scratch tree it is allowed to mutate.**
> — [`nox-security.md:824-828`](../research/nox-security.md)

Harness config files are tracked files on the attacker's branch, so any
checkout materialises them byte-for-byte
([`nox-security.md:799-803`](../research/nox-security.md)). The worktree does
not filter the attacker out. It removes the prohibition on mutating the tree —
and C-1005 spends that permission on the git objects rather than on the disk.

## Decision Drivers

- **Repo-supplied configuration is a startup-time code-execution surface, not
  a permissions problem.** Claude Code under `-p` treats project hooks, the
  `env` block, `apiKeyHelper`, project-skill `allowed-tools` and `.mcp.json`
  servers as *used* / *connected without asking* — trust verification is
  disabled in exactly the mode nox uses
  ([`nox-security.md:203-213`](../research/nox-security.md)). OpenCode's
  `.opencode/plugins/` auto-loads repo-supplied JS/TS **with shell execution
  via Bun's API, at startup, outside the permission model, with no documented
  off-switch** ([`nox-security.md:908-916`](../research/nox-security.md)).
  Codex closes the hook path by content hash and leaves the MCP path open.
- **Three harnesses that differ in kind are what makes the facade real.** With
  two, every mismatch can be special-cased into whichever adapter is weirder.
  The third forced a genuine generalization — see C-1007, which had to move
  from "remove the shell tool" to "establish no-write and no-network by
  whatever mechanism this harness offers", because Codex establishes it with
  an OS sandbox rather than a tool allowlist.
- **The containment story must be statable in one sentence.** Anthropic's own
  best-practice list item 2 is "avoid piping untrusted content directly to
  Claude" — literally nox's core operation
  ([`nox-security.md:95`](../research/nox-security.md)). A tool that does that
  anyway owes its users a boundary they can describe, not a flag list.
- **Read-only does not normalize across three harnesses and must not be
  presented as if it did.** Claude Code evaluates permission rules before a
  tool call runs; Codex enforces at the OS level via Seatbelt / Landlock +
  seccomp but only around *model-generated shell commands*; OpenCode's is a
  config-file convention with permissive defaults, no CLI override, and one
  report of non-enforcement closed as not-planned
  ([anomalyco/opencode#8832](https://github.com/anomalyco/opencode/issues/8832)).
- **Flag surfaces churn within weeks.** The security lane verified against
  `claude` v2.1.251 on 2026-08-31; the same machine reports **v2.1.252** while
  this ADR is being written. Codex hard-removed `--full-auto` in v0.147.0 so
  that scripts error rather than degrade
  ([`discuss-nox-priorart.md:64`](../research/discuss-nox-priorart.md)), and
  its app-server is still marked `[experimental]`. A design whose only
  containment is a flag string loses containment on a patch release.
- **Zero runtime dependencies, and a `.pyz` a consuming agent does not read as
  context** — both settled
  ([discussion:51-63](../discussions/nox-multi-harness-adversary.md)).
- **Auth is the user's own installed, logged-in harness CLI.** This is what
  keeps nox on the permitted side of Anthropic's line, which is *identity
  misrepresentation*, not automation
  ([`nox-security.md:446-455`](../research/nox-security.md)).

## Industry Context & Research

**Research artifacts:**
[`nox-security.md`](../research/nox-security.md) (1284 lines including two
addenda — the dominant input),
[`nox-tech-tooling.md`](../research/nox-tech-tooling.md),
[`nox-pattern-precedent.md`](../research/nox-pattern-precedent.md),
[`discuss-nox-priorart.md`](../research/discuss-nox-priorart.md),
[`discuss-nox-vendor.md`](../research/discuss-nox-vendor.md).

**Where the industry is.** Every shipping cross-vendor second-opinion
mechanism found holds the API keys itself and multiplexes at the API layer —
Amp's Oracle sub-agent routes to a GPT reasoning model from a Claude main
thread; Zen/PAL MCP holds a key per provider and Claude calls it as a tool;
Aider's architect/editor split mixes vendors through LiteLLM
([`discuss-nox-vendor.md:24-30`](../research/discuss-nox-vendor.md) for Amp's
Oracle and Aider,
[`:49`](../research/discuss-nox-vendor.md) for Zen/PAL MCP). Two
projects instead drive *other harnesses*: `codex-plugin-cc`, at protocol level
for exactly one pair; and `coder/agentapi`, which drives eleven CLIs by typing
into their interactive TUIs through an in-memory terminal emulator and
screen-scraping the result — broad coverage, brittle to any redraw
([`discuss-nox-priorart.md:56`](../research/discuss-nox-priorart.md)). **nox
occupies the empty third position: native headless contracts, several
harnesses, no keys held.**

**Isolation is where the industry has already converged, and it converged away
from the shared tree.** Every vendor that runs an agent unattended gives it
its own filesystem: Cursor cloud agents get a per-task VM; Copilot's coding
agent gets an ephemeral Actions container with firewalled egress and
`copilot/*`-scoped push; Devin gets a sandboxed VM per session; Claude Code's
own parallel-subagent story is *git worktrees*
([`discuss-nox-vendor.md:72-79`](../research/discuss-nox-vendor.md), the
isolation-mechanism table; per-product detail at `:14`, `:20`, `:38`, `:48`).
No
vendor documents a supported story for concurrent agents on one working tree
([`discuss-nox-priorart.md:65`](../research/discuss-nox-priorart.md)). The
settled no-worktree constraint put nox alone on the wrong side of that
consensus.

**Key insight.** CSA's "Comment and Control" (disclosed 2026-04-15) hijacked
three separate agents — Anthropic's Claude Code Security Review, Google's
Gemini CLI Action, Microsoft's Copilot Agent — via PR titles, issue bodies and
HTML-comment blocks, and exfiltrated repo and API secrets. **Read-only
permissions did not prevent these attacks**
([`nox-security.md:48-59`](../research/nox-security.md)). The academic
position matches: arXiv:2506.08837 concludes there is no general solution
while agents process free-form text, and that resistance comes from
constraining what the agent *can do*, not from detecting attacks. Design
patterns for the interface shape — `fsspec`'s string-keyed lazy registry,
`keyring`'s probe-by-raising, LSP's absence-means-unsupported capability
record, Boost `tribool`'s never-collapse-the-third-state, `mise`'s trust gate
backed by a real bypass advisory (GHSA-436v-8fw5-4mj8) — are drawn from
[`nox-pattern-precedent.md`](../research/nox-pattern-precedent.md) and cited
per contract below.

## Considered Options

The isolation question is the decision. Four resolutions were weighed, and one
was excluded before weighing.

**Excluded by scope, not by analysis: "drop OpenCode from v1."** It is the
security lane's first-listed resolution of the asymmetry
([`nox-security.md:938-943`](../research/nox-security.md)) and it would resolve
the whole question by deleting the harness that creates it. It is off the table
because the v1 harness set is an owner constraint (§ *Context*). An earlier
revision of this file carried it as a scored Option E; it was removed from the
matrix rather than argued down, and prose elsewhere that still says "A, B, D and
E" has been corrected. **There are four options and four scored rows, and no
Option E exists in this document.**

### Option A: In-tree, per-harness flags only, all three — with or without a "trusted diffs only" caveat

**Description:** Spawn each harness with `cwd` at the user's working tree;
containment entirely from flags — Claude Code `--safe-mode --restricted
--strict-mcp-config --permission-prompts none --tools "Read,Grep,Glob"`; Codex
`codex exec review --ephemeral --strict-config --ignore-rules` with the
sandbox set via `-c`; OpenCode `OPENCODE_CONFIG_CONTENT` inline carrying the
deny map, with `--pure` the only argv-visible word. This is the settled
baseline. Its documented-caveat variant
— shipping the same code and putting OpenCode's exposure in the README — is
folded in here rather than scored separately, because the two differ only in
prose: identical code, identical boundary, and the caveat moves only the
honesty score.

| Pros | Cons |
|------|------|
| Nothing to build; untracked files and build artifacts present, so review fidelity is maximal | OpenCode's `.opencode/plugins/` is unconditional arbitrary code execution from the tree under review, at startup, with no documented off-switch |
| No disk or checkout cost | Codex's repo-MCP hole stays open, with only an explicitly untested `-c mcp_servers={}` between a hostile branch and a spawned command |
| Uniform: one code path | Claude Code's containment rests on `--safe-mode`/`--restricted`, which are `--help`-only, absent from code.claude.com, and untested against `-p` ([`nox-security.md:940`](../research/nox-security.md)) |
| The caveat variant matches how the tool will be used most of the time — reviewing your own branch | An unsafe default with a documentation-only mitigation is CWE-1188, *Initialization of a Resource with an Insecure Default* ([`nox-security.md:628`](../research/nox-security.md)) |
| Zero implementation risk | The caveat excludes exactly the case where a second opinion is most valuable — a diff you did *not* write — and the failure is silent, total, and indistinguishable from success |

### Option B: Ephemeral worktree for OpenCode only

**Description:** Claude Code and Codex keep the in-tree flag stack; OpenCode
alone gets a throwaway worktree in which nox deletes the neutralization set
before spawning.

| Pros | Cons |
|------|------|
| Applies the mitigation exactly where the researcher's verdict says flags fail | Two isolation code paths, two guarantees, two sets of failure modes |
| **Two of three harnesses never pay the worktree's *correctness* cost.** This is B's strongest point and it grew stronger during review: C-1026 and C-1027 exist only because a worktree cannot contain untracked work, so under B the Claude Code and Codex legs keep untracked-file coverage and a plan-artifact review that needs no synthetic-commit machinery at all. B trades a *known, documented* residual on one harness for the removal of a *structural* fidelity loss on two | |
| Two of three harnesses retain full-fidelity context | **Codex's stated residual stays accepted** — the one option-independent hole the worktree would have closed for free |
| Cheapest path that closes the critical finding | The user sees OpenCode silently lose their uncommitted untracked work while the other two do not, with no visible cause |
| | Forfeits the §3 credential win (untracked `.env`, `.envrc`, scratch dumps) on two of three legs |

### Option C: Ephemeral worktree for all three — **chosen**

**Description:** Every review, every harness, runs in a nox-owned ephemeral
worktree checked out from a commit-ish; nox deletes the neutralization set
before spawn; per-harness flags are retained as defense in depth rather than
as the boundary.

| Pros | Cons |
|------|------|
| One code path, one sentence of guarantee, uniform failure modes | A full checkout per review — O(repo size) in time and disk |
| Closes every repo-supplied vector on all three by filtering them out of the checked-out tree, "stronger and more portable than any combination of per-harness flags" ([`nox-security.md:824-828`](../research/nox-security.md)) | Untracked and ignored files are absent. **This is a correctness cost, not only a fidelity one:** untracked files vanish from a code-diff review, and a plan artifact under review is untracked by construction. C-1026 and C-1027 exist because of it, and neither existed in the first draft |
| **Closes Codex's stated residual** — `.codex/config.toml` is deleted, so repo-declared MCP servers cannot be declared at all, and `-c mcp_servers={}` stops being load-bearing | Leaked worktrees are a real recurring operational cost in this environment |
| **And may additionally trip Codex's own fail-closed gate**: the worktree is a fresh path, and Codex's project trust is path-scoped, so its project `.codex/` layer is plausibly untrusted there | That bonus is conditional on how trust is granted, which the research flags as its highest-value open question — so it is a bonus, never the argument |
| Also removes untracked `.env`/`.envrc`/scratch credentials from every child's reach | `git worktree remove` fails on a tree containing submodules; teardown must always use `--force` |
| Flags become defense in depth, so a flag rename degrades the posture instead of removing it | New failure class: worktree creation can fail and must map to a distinct outcome, not to "review failed" |

### Option D: Per-harness isolation tier, capability-selected

**Description:** Option B generalized. Isolation mode becomes a declared
per-adapter capability: an adapter that holds `SELF_CONTAINS_REPO_CONFIG` runs
in-tree behind its flags, one that does not gets a worktree. For v1 that
resolves to exactly Option B; the machinery is the extension point.

| Pros | Cons |
|------|------|
| Matches the researcher's 2–1 verdict precisely | **It is not cheaper than Option C — it is strictly more.** The worktree path is built either way, for OpenCode; the tier adds a second path, a selector, and a 3 × 2 contract-test matrix on top of it |
| Isolation posture becomes a first-class capability, consistent with the rest of the design | Makes a *capability declaration* load-bearing on containment, when two of the three declarations rest on untested flags and one on an explicitly accepted residual |
| Preserves latency and fidelity for two of three harnesses | The guarantee is no longer statable — it is computed per adapter, and a user must consult the record to know what protected them |
| The right shape *later*, once a checkout cost is measured | Carries Option B's containment while paying more than Option C's cost |

### Weighted comparison

| # | Criterion | Weight | Why weighted here |
|---|---|---|---|
| C1 | Containment of repo-supplied code execution | 5 | The critical finding, and the one that does not degrade gracefully |
| C2 | Robustness to vendor flag churn | 5 | The real discriminator, and evidenced: v2.1.251 → v2.1.252 inside one research session; `--full-auto` removed in a patch release; Codex's app-server still `[experimental]` |
| C3 | Review fidelity — does the reviewer see what it needs | 3 | A contained reviewer that gives worse findings is a worse product |
| C4 | **Implementation** cost only | 2 | Real, but bounded — and the worktree path is built under every option but A. *Operational* cost is deliberately **not** in this column: it ranks the options in the opposite order (A pays zero per review, C pays a checkout every time) and is carried in C3 and in *Quantified Impact* instead. Scoring both halves in one column, as an earlier revision did, flattered the chosen option |
| C5 | Reversibility | 3 | One-way door; the cost of being wrong is asymmetric |
| C6 | Honesty — can the guarantee be stated in one sentence | 2 | A boundary users cannot describe is one they will not respect |
| C7 | **Operational cost per review** | 2 | Added after a cross-model reviewer noted it was named in C4 and scored nowhere. It ranks the options in the *opposite* order to C4, which is exactly why it needs its own row rather than being averaged into one |

| Option | C1 ×5 | C2 ×5 | C3 ×3 | C4 ×2 | C5 ×3 | C6 ×2 | C7 ×2 | **Total** |
|---|---|---|---|---|---|---|---|---|
| A — in-tree, flags only (± caveat) | 2 → 10 | 1 → 5 | 5 → 15 | 5 → 10 | 4 → 12 | 2 → 4 | 5 → 10 | **66** |
| B — worktree, OpenCode only | 3 → 15 | 3 → 15 | 4 → 12 | 3 → 6 | 5 → 15 | 3 → 6 | 4 → 8 | **77** |
| **C — worktree, all three** | **5 → 25** | **5 → 25** | **3 → 9** | **4 → 8** | **5 → 15** | **5 → 10** | **2 → 4** | **96** |
| D — per-harness tier | 3 → 15 | 3 → 15 | 4 → 12 | 2 → 4 | 5 → 15 | 2 → 4 | 4 → 8 | **73** |

**C7 is scored against C without mercy: 2.** C pays a full checkout, two
synthetic-tree builds and a teardown on *every* review, on every repo size; A
pays nothing; B and D pay it on one harness of three. The row moves every total
and changes no ordering — C leads B by 19 rather than 23.

A's C1 is scored 2, not 1, in fairness to the two harnesses where flags do
real work — but a user selects one harness per review, and selecting OpenCode
under A yields zero containment, so the weakest harness sets the ceiling.

**One concession, made explicitly.** B and D score 3 rather than 2 on C2
because *part* of Codex's protection is not flag-shaped at all: hook trust is
recorded against the hook's content hash, so it cannot be broken by a flag
rename ([`nox-security.md:1086`](../research/nox-security.md)). That is a real
robustness advantage over Claude Code and it belongs in the score. It does not
reach the vector that matters here: Codex's *containment* (`sandbox_mode`) is
still set through a config key whose name is unverified, and its *MCP* path has
neither a flag nor a hash protecting it — the researcher's own line ends
"Residual accepted risk: repo-declared MCP servers in an already-trusted
project". So the concession moves B from 64 to 69 and D from 60 to 65, and
changes nothing: **C leads by 23.**

**What C4 does and does not decide.** C1 and C2 alone open a 20-point gap
between C and B; C4 contributes a 2-point swing and does not decide the
outcome. What C4 *does* decide is the **B-versus-D ordering**, and it decides it
in the opposite direction to intuition: **D scores below B because D is B plus
machinery, at the same containment.** C's implementation cost is scored *above*
both, not below, because under B, C and D alike the worktree path must be
written for OpenCode — C is the only one of the three that does not *also*
carry the in-tree path, its selector, its second `Containment` shape and its
doubled contract matrix. Options B and D are not the cheap options they look
like.

**De-biasing check on the matrix itself.** C1, C2 and C6 measure one underlying
property — whether the boundary is a worktree or a flag string — and together
they carry 12 of the 20 weight points, so the decision variable is weighted 60%
and the matrix is partly counting it three times. Three reweightings were run
against that objection. Collapsing C1+C2+C6 into a single containment criterion
at weight 5 gives A 47, B 48, C 57, D 46 — C still leads, by 9 rather than 23.
Inflating C4 to weight 5, the criterion most favourable to A, gives A 71 and
C 104. Inflating C3 to weight 5 *and* dropping C's fidelity score to 1 gives
A 66 and C 88. De-duplicating the correlated cluster narrows the margin and
changes nothing else.

**Sensitivity, as a range rather than three hand-picked reweightings.** The
honest challenge is not A — it is **B**, which keeps Codex's MCP residual but
spares two of three harnesses the worktree's correctness cost, and which
therefore buys real untracked-file and plan-artifact fidelity on the two legs
where flags do some work. B overtakes C exactly when
`w(C3) + 2·w(C7) > 26`, holding the other five weights fixed. Today that sum
is 7. Reaching 26 needs review fidelity and per-review operational cost
weighted at roughly **10 and 8** — each about twice the weight of containment
itself. **Would a reasonable engineer pick those weights?** Only one who does
not believe the branch under review is hostile. That is a coherent position
for someone reviewing only their own work, and it is exactly the position the
security lane falsified for the case a second opinion is worth most: a diff you
did not write. So the reweighting that flips this decision exists and is
nameable, and taking it means abandoning the premise the whole document rests
on. That is a stronger claim than "no defensible reweighting flips it", and it
is the true one. C5 should
also be read as inert: it scores 4/5/5/5 and discriminates nothing among the
three live options, so the reversibility argument below is prose doing prose's
work, not a column doing arithmetic.

**Reversibility — the asymmetry is in consequence, not in cost.** An earlier
revision priced this as "A → C is one code path but an apology; C → D is one
config key", which compares a reputational currency on one side with a code
currency on the other, and contradicts the matrix that charges D for "a second
path, a selector, and a 3 × 2 contract-test matrix". Both directions cost
roughly the same: **one code path plus one revised shipped guarantee.** C → D is
also more than "one key" — `isolation` sits in `PERMISSION_KEYS`, so under
C-1017 a repo-local file supplying it is dropped unless path *and* content hash
are registered as trusted; and `Containment.isolation: Literal["worktree"]` is a
frozen field on a public type, so widening it is a typed-API change for any
consumer doing exhaustiveness checks.

What is genuinely asymmetric is what happens when the default is wrong.
**A too-tight default produces a complaint someone files. A too-loose default
produces arbitrary code execution nobody observes.** That is fail-safe defaults
(Saltzer & Schroeder, [`nox-security.md:642-648`](../research/nox-security.md)),
the same principle §6.2 of the companion cites for tool allowlists, and it is
the whole argument: **start at the containing end, where being wrong is
visible, rather than at the permissive end, where being wrong is not.**

## Decision Outcome

**Chosen Option: C — ephemeral worktree for all three harnesses.**

This declines the steer that the 2–1 asymmetry points at a per-harness tier.
The reasoning is in the matrix above and in the three points below; Option D
is adopted **as the deferred escape hatch**, not as the v1 default.

**Rationale.** Three points, in order of weight.

1. **Neutralization closes what the flags leave open on every harness,
   including the two that "pass".** OpenCode's plugin autoload has no
   flag-based mitigation at all. Codex's one genuine gap is repo-declared MCP
   servers, whose only candidate mitigation is explicitly untested — and a
   checkout that never contains `.codex/` cannot declare them, so the gap
   closes without needing `-c mcp_servers={}` to work. Claude Code's
   `.mcp.json`, settings hooks and project-skill frontmatter hooks go the same
   way. One control, three harnesses, no flag names in it. C-1005 performs the
   neutralization at the **git-object level** rather than by deleting files
   from a checkout, which is what makes it invisible to every harness's own
   diff collection and removes the deletion primitive's symlink hazards
   entirely — see the contract for why that matters more than it looks.

   There is a further effect that is welcome but deliberately *not* load
   bearing: Codex's project trust is path-scoped, and a nox worktree is a
   fresh path, so its project `.codex/` layer is plausibly untrusted there and
   Codex's own fail-closed gate engages. The research flags how trust is
   granted as its highest-value open question
   ([`nox-security.md:1261-1270`](../research/nox-security.md)), so this is
   recorded as a bonus and the decision does not rest on it. The deletion does
   not care either way.

2. **Option D costs more than Option C for less containment.** The worktree
   implementation exists under B, C and D alike, because OpenCode requires it.
   D adds a second isolation path, a capability that selects between them, two
   `Containment` shapes, and a 3 × 2 test matrix — and buys, in exchange, one
   checkout's latency and untracked-file fidelity on two harnesses, while
   leaving Codex's stated residual accepted. Building both paths to be less
   safe is the wrong trade in either direction you read it.

3. **Option C is the only option whose guarantee fits in a sentence.** *"nox
   reviews inside a throwaway checkout with the harness's own configuration
   filtered out, no write path to your repository, no network, and a scrubbed
   environment; it never reads your credentials."* A, B and D each need a
   per-harness footnote, and D's guarantee is not even a fixed sentence — it
   is computed from a capability record. Two honest qualifiers travel with that
   sentence and are stated wherever it appears: "no network" is enforced at the
   OS level on one of the three harnesses and asserted by configuration on the
   other two (C-1007), and untracked files are not reviewed and their omission
   is stamped (C-1026).

**What this decision rests on that nobody has run.** Stated here, in the
decision itself, rather than only in §6 of the companion — a reader who stops
after the Decision Outcome must still leave knowing it. **No harness review was
ever executed during this work.** Every per-harness security property below is
`--help` text, vendor documentation, or inference:

| Assumption | Status |
|---|---|
| Codex's OS sandbox is entered by `-c sandbox_mode=read-only` | **key name inferred from a flag name**, never read from documentation, never observed taking effect |
| Codex's sandbox denies network | `AF_INET` only; `AF_UNIX` is exempt and whether Landlock incidentally blocks socket connection is **unverified** |
| OpenCode's inline config outranks a project `opencode.json` | **explicitly unverified** — no binary on the security lane's machine ([`nox-security.md:727-731`](../research/nox-security.md)) |
| Claude Code's `--safe-mode` / `--restricted` behave as their help text says | `--help`-only, absent from the docs site, untested against `-p` |
| Auth and quota failures are distinguishable per harness | observed on **none**; see §7.1a of the companion |

The single mechanically verified claim in either document is C-1005's git
behaviour, and it took two attempts to get right. **The design is arranged so
that each of these being wrong degrades rather than breaches** — the workspace
holds independently of every one of them — but "arranged to fail safe" is not
"tested", and C-1032 is what converts them.

**What the decision does not claim.** The worktree is *not* a git-level
boundary — `git-worktree(1)` shares the object store and "all refs starting
with `refs/`" ([`nox-security.md:809`](../research/nox-security.md)) — so a
harness able to run shell inside the worktree can still reach the real
repository's refs. That is why C-1007 is a *launch precondition*. Nor does the
worktree isolate the filesystem: under Claude Code's default sandbox read
policy a read-only agent with Bash still reads `~/.ssh` and
`~/.aws/credentials`. **Three independent controls are required and each
covers what the others do not** — worktree (repo-supplied execution), the
per-harness containment plan (repository writes, filesystem reach, network),
environment allowlist (credential leak into the child).

### On transport: v1 does not use Codex's app-server

`codex app-server` is the shape that differs in kind — long-lived JSON-RPC 2.0
over stdio, a first-class `review/start` method, an optional Unix-socket
broker. v1 does not use it. The security lane's own recommendation:

> **Recommendation for nox:** prefer `codex exec review` over the app-server
> for v1. It is non-experimental, its trust behaviour is documented, and it
> carries the flags that matter … The app-server buys streaming and session
> reuse that nox's one-shot review does not need.
> — [`nox-security.md:1200`](../research/nox-security.md)

and, on the app-server's config handling:

> neither the official app-server page nor the community guide states whether
> the app-server honours the project-trust and hook-trust gates … that is an
> inference, and it is the one fact on this axis I would not ship on.
> — [`nox-security.md:1192`](../research/nox-security.md)

For a security tool, adopting an `[experimental]` transport whose trust
behaviour is undocumented, in order to exercise a facade, is the wrong order
of priorities. All three v1 adapters are therefore argv + line-stream
(C-1024).

**This does not cost the facade its third shape.** The three backends still
differ in the dimensions the facade actually abstracts: capability sets (7 / 5
/ 3 members), output contracts (`--json-schema` versus `--output-schema`
versus no schema flag at all), permission models (argv tool allowlist versus
OS sandbox versus config-file convention), review-target vocabularies, and
credential stores. The proof that two would not have sufficed is C-1007: with
Claude Code and OpenCode alone the contract would have read "deny the shell
tool", and Codex — which has no tool allowlist and instead denies writes and
network at the OS level — forced it to generalize to "establish no-write and
no-network by whatever mechanism this harness offers". The third backend broke
the abstraction exactly as predicted; it broke it at the permission layer
rather than the transport layer.

---

### Contracts

Contract IDs are allocated in order of *addition*, not in order of reading, and
are never renumbered once published — reviewers and plans cite them. C-1023 and
C-1024 therefore sit inside topic groups whose other members have lower numbers.
The full numeric index is C-1001 … C-1032; the changelog records which revision
added which.

#### Boundary and product

- **C-1001 — nox is a standalone library; hex is its first consumer, and hex
  does not change.** nox's skill becomes a valid `adversary: <skill-name>`
  value in `hex.md › Preferences`. One hex-side addition is required so
  that value is *proposed* rather than hand-typed — `/hex-init`'s audit gains
  a detection item (C-1033); the adversary contract itself is untouched
  ([`protocol.md` § Adversary contract](../../hex/hex-core/references/protocol.md)).
  nox never imports, requires or assumes hex. nox emits findings; the
  orchestrator does the 4-way triage. nox never loops.
- **C-1002 — nox never reads, copies, forwards or caches a harness
  credential.** It spawns the official binary and lets the binary authenticate
  as itself. This is what separates nox from the tools Anthropic technically
  blocked on 2026-04-04; the prohibited line is identity misrepresentation,
  not automation ([`nox-security.md:446-455`](../research/nox-security.md)).
  Violating C-1002 is not a bug, it is a different product. The credential
  stores nox must never touch: `~/.claude/.credentials.json`,
  `~/.codex/auth.json`, `~/.local/share/opencode/auth.json`.

#### Isolation

- **C-1003 — every review runs in an ephemeral, nox-owned git worktree.** nox
  never spawns a harness with `cwd` inside the user's working tree. There is
  no in-tree mode in v1.
- **C-1004 — the review target is materialized as a *pair* of commit-ishes,
  base and target, and both are neutralized before either is checked out.**
  Resolution first: for a named ref or PR branch, that ref, with `base`
  resolving to `git merge-base <base> <ref>` when `ReviewTarget.base` is given
  and to `<ref>^` otherwise; for uncommitted work, `git stash create`, which
  writes a real commit object to the store and returns its SHA **without
  touching any ref, the index or the working tree**, with `base` = `HEAD`;
  empty `stash create` output (clean tree) falls back to `HEAD` and `HEAD^`;
  for `plan-artifact`, see C-1027. Neutralization (C-1005) then rewrites both
  ends into *synthetic* commits, and it is the synthetic pair that is checked
  out and diffed. Untracked files are not carried, and their omission is a
  stamped, verdict-blocking condition rather than a silent one (C-1026).
  *The `git stash create` half of this flow is documentation-derived; the
  permission prompt blocked the fixture, so the first implementation work
  package must prove it with a real repo before anything else builds on it.*
- **C-1005 — neutralization filters a shipped literal set out of the git
  objects, never off the disk.** The set:

  ```
  .claude/   .mcp.json   .opencode/   opencode.json   opencode.jsonc
  .codex/    .cursor/    CLAUDE.md    AGENTS.md
  .env  .env.*  .envrc  mise.toml  .mise.toml
  .gitattributes   .gitmodules              ← git's own execution surfaces
  ```

  **plus every entry with mode `160000`** — gitlinks are dropped by *mode*, not
  by name, because a submodule can sit at any path.

  **The last line is git's own two execution surfaces, and neither is closed by
  a path matcher alone.**

  - **`.gitattributes` runs code during checkout.** A branch adding
    `*.py filter=evil` makes `git worktree add` execute
    `filter.evil.smudge` while materializing the tree — before neutralization
    is even observable, before any harness starts, outside every control in
    this document. The driver itself is defined in the *invoking machine's*
    git config, so the branch supplies only half the gadget; but git-lfs is
    exactly such a driver and is present on a great many developer machines,
    and the branch chooses which paths it applies to. **Verified:** with a
    driver configured and a hostile `.gitattributes` committed, the filter ran
    on `worktree add`. Removing `.gitattributes` at the object level stops it —
    also verified — because with no attributes in the tree no filter applies,
    whatever drivers exist. That is the whole fix for the branch-controlled
    half; C-1031 covers the attribute sources a branch does *not* control.
  - **`.gitmodules` plus gitlinks are an instruction and code escape.** A
    checkout leaves submodules unpopulated, so nothing runs at materialization
    — but a shell-capable reviewer (Codex, OpenCode) can be induced to run
    `git submodule update --init`, and the nested repository arrives with its
    own `.claude/`, `.codex/`, `AGENTS.md` and source, none of which this
    filter ever saw because it only walks the superproject's tree. Dropping
    `.gitmodules` and every mode-`160000` entry removes both the map and the
    mount points. `git ls-tree -r` reports gitlinks with their mode without
    recursing into them, so the predicate costs one comparison on a walk that
    already happens, and `update-index --force-remove` drops a gitlink like any
    other entry. **Verified:** `git submodule status` inside the resulting
    worktree lists nothing.

  **Mechanism.** For each end of the C-1004 pair: read that commit's tree into
  a temporary index (`GIT_INDEX_FILE=<tmp> git read-tree <commit>`), drop every
  matching entry from that index, `git write-tree`, and `git commit-tree` the
  result. The worktree is then created at the synthetic *target* and the review
  diff is synthetic-base → synthetic-target. Nothing is ever removed from disk.

  **The synthetic target is committed with `-p <synthetic base>`.** Without a
  parent both ends are parentless roots with no common ancestor: `git merge-base`
  exits 1 and `git diff <sb>...<st>` fails outright with *"no merge base"*. Two-dot
  diffs work either way, so nox's own `review.diff` was unaffected — but nox
  drives the Codex leg with `codex exec review --base <synthetic base>`, and
  "review this against base" conventionally means the merge-base diff, so the
  Codex adapter would have failed at runtime. One token fixes it, and the
  ancestry is asserted in the §9.4 fixture rather than assumed. **Diff semantics
  per leg, stated so no implementer has to guess:** nox writes `review.diff` with
  **two-dot** `<sb>..<st>`, which is exactly the change under review because the
  base is the target's only parent; any harness computing its own diff, by either
  convention, gets the identical result for the same reason.

  **Why the object level rather than an `rm` in the checkout — three reasons,
  each of which was a defect in the previous formulation.**

  1. **A deletion in the checkout is the checkout's uncommitted state.** Any
     harness that collects its own diff sees nox's housekeeping and not the
     change: `codex exec review --uncommitted` would review seven deleted
     config files while the real change, committed at `HEAD`, stayed invisible,
     and would return `approve` on a review that never happened. Filtering at
     the object level makes the paths absent from the checkout **and** from
     every diff any harness can compute, so nox's diff and a harness-collected
     diff are identical by construction and the question of which one is
     authoritative does not arise.
  2. **The deletion primitive is a hazard on attacker-controlled paths.** A
     branch may commit `.claude` as a *symlink*; `Path.is_dir()` follows
     symlinks while `shutil.rmtree` refuses them, so the natural
     `if p.is_dir(): shutil.rmtree(p, ignore_errors=True)` idiom silently
     leaves the symlink in place while reporting the path as neutralized —
     a breach plus a false containment stamp, separated from correct behaviour
     by one keyword argument. A `git rm --cached`-shaped filter has no symlink
     semantics to get wrong: a symlink is an index entry with mode 120000, and
     dropping the entry means it is never materialized.
  3. **It is exact at any depth, and independent of entry mode.** Matching
     happens over `git ls-tree -r --name-only`, by **path component**: an entry
     is dropped if **any** of its components — including the basename — equals
     a directory name in the set, or its basename matches a file name or glob
     in the set. `src/AGENTS.md`, `packages/api/.opencode/plugins/evil.ts` and
     `packages/api/.codex/config.toml` are all dropped. Root-only matching was
     a real bypass — Codex reads nested `AGENTS.md`, Claude Code loads
     `CLAUDE.md` from the directory tree of the files it reads, and Codex
     "walks from the project root to your current working directory and loads
     every `.codex/config.toml` it finds". A root-only rule also rested on an
     unstated invariant (cwd is always the worktree root) that any future
     subdirectory-scoped review would break.

     **"Including the basename" is the whole of the symlink leg, and it is not
     a detail.** A set member committed as a *symlink* — `.codex` pointing at
     an in-repo `docs/build/` that holds a `settings.json` with a hook — is a
     **blob** with mode 120000 whose path is the single component `.codex`. An
     earlier formulation tested components against the directory set but
     excluded the basename from that test, and tested the basename only against
     the *file* set; `.codex` is a directory name, so neither test fired, the
     symlink reached the checkout, and it still resolved to attacker-controlled
     content. That is Security H5's breach arriving through the matcher instead
     of through `rmtree` — the hazard moved rather than being removed. Matching
     every component against the directory set closes it **regardless of entry
     mode**, because `ls-tree` reports names and the filter never asks what
     kind of object a name denotes. Note `_verify` cannot catch this class: it
     re-checks that dropped entries are absent, and an entry that was never
     matched was never dropped.

  `.opencode/` and `.codex/` are dropped **wholesale**, never by named
  subdirectory: OpenCode's own docs disagree with themselves on `plugins/`
  versus `plugin/` and `agents/` versus `agent/`
  ([`nox-security.md:956-960`](../research/nox-security.md)). `AGENTS.md` is
  dropped because it is repo-supplied, steers the model, and has no documented
  off-switch on **either** Codex or OpenCode. Project execpolicy `.rules` files
  are *not* globbed out — `--ignore-rules` covers them and a `*.rules` glob
  would remove unrelated files.

  **One post-research addition was checked and changes nothing.** Codex "Agent
  Plugins" shipped in v0.146.0 (2026-07-29), after the 0.144.1 probe this ADR
  rests on, and a repo-directory plugin autoload would be an OpenCode-shaped
  hole in the harness the design treats as the well-behaved one. They require
  an explicit `codex plugins install <dir>` rather than project-directory
  auto-discovery, so no new path enters the set. It is named here because the
  set is a shipped literal whose staleness is the maintenance cost (§9.5 of the
  companion), and because the probed version predates the feature.

  **Verified, and it is the only mechanically verified claim in this
  document — at the second attempt.** The sequence was executed on a throwaway
  repository carrying a root `AGENTS.md`, a root `.claude/settings.json`, a
  nested `packages/api/AGENTS.md`, a nested
  `packages/api/.opencode/plugins/evil.ts` and `.codex` committed as a
  **symlink** to an in-repo directory holding a `settings.json`, against a
  branch whose real change was one line in `src/app.py`. Result: all five
  neutralization paths absent from the synthetic tree, symlink and both nested
  files included; the synthetic base an **ancestor** of the synthetic target,
  so `merge-base`, two-dot and three-dot diffs all resolve; the three-dot diff
  containing the one-line real change and nothing else; and
  `git worktree add --detach` accepting the unreferenced synthetic commit.

  **The first attempt reported the same result and was wrong, which is worth
  recording rather than quietly fixing.** That run's script matched `.codex`
  as a *file* name, while the contract text above matched basenames only
  against the file set — so the script verified a matcher the specification did
  not describe, and the symlink survived under the spec as written. A
  re-validation pass caught it by running the *specified* matcher instead of
  trusting this paragraph. Two corrections follow. **A verification is only
  worth its script's fidelity to the contract**, and a claim of mechanical
  verification is exactly the kind of thing a later reader will not re-derive —
  so the failure is named here rather than in a changelog. **And
  `git status --porcelain` in the worktree is empty at spawn time** — but
  only because the scratch directory was later moved out of the worktree
  (E20). As C-1009 was written, step (4e) created `.nox-<token>/` *inside* the
  worktree and the porcelain then read `?? .nox-<token>/`; the earlier wording
  claimed a clean tree and had been measured before the scratch dir existed.
  That is recorded rather than deleted, because it is the observation that
  eventually moved the directory. Both readings argue against `--uncommitted`
  on the Codex leg — inside the worktree that flag would have reviewed nox's
  own scratch directory, outside it there is nothing uncommitted to review at
  all — and C-1005's argument does not depend on it either way.

  Everything else in this ADR is documentation, `--help` text or inference, and
  is labelled as such where it matters.

  **Cost, stated.** Two `write-tree` plus two `commit-tree` per review, and two
  unreferenced commit objects left in the user's object store. `git stash
  create` already writes exactly such an object, so this is not a new class,
  and `git gc` reclaims them; the small race is that a concurrent `gc --prune`
  could collect a synthetic commit mid-review, which surfaces as
  `ISOLATION_FAILED` rather than as a wrong review.

  The security-relevant *content* of a filtered file remains reviewable,
  because the diff text reaches the model through the prompt regardless; the
  prompt states which paths were filtered (C-1028).

  **Alternatives considered and rejected.** *Commit the deletions inside the
  worktree* — the deletions then appear in every base-to-HEAD diff instead of
  every uncommitted diff, which moves the noise rather than removing it.
  *Hand the diff explicitly and forbid harness-side diff collection* — this
  costs `codex exec review`'s native targeting, and with it the
  `--output-schema` / `--ephemeral` / `--strict-config` / `--ignore-rules` set
  C-1024 selected that subcommand for, while leaving the on-disk `rm` and its
  symlink hazards in place. The object-level filter is the only one of the
  three that fixes both the wrong-diff defect and the deletion-primitive
  defect at once.
- **C-1006 — teardown is unconditional.** Worktrees live under a nox-owned
  prefix, are removed in a `finally` with `git worktree remove --force` (plain
  `remove` fails on a tree containing submodules), and `git worktree prune`
  runs at startup so a leak from a killed process is reclaimed rather than
  accumulated.
- **C-1007 — an adapter must positively establish no-repository-write and
  no-network, and must say *how strongly*.** The worktree shares `refs/` and
  the object store, so a harness that can write or reach the network from
  inside it reaches past the boundary. `ContainmentPlan` therefore carries, per
  axis, an enforcement level rather than a boolean:
  **`os`** (enforced below the harness by the operating system),
  **`harness`** (enforced by the harness before the model acts, documented as
  such), **`attested`** (the harness is configured to refuse, with no
  documented enforcement guarantee), or **`None`** ⇒ not established. nox
  refuses to launch when either axis is `None`. *A bare `no_repo_write: bool`
  was the previous shape and it was wrong:* it made the launch gate verify
  that a claim had been made rather than that the claim was true, and it read
  as "enforced" to every future adapter author. That is exactly the failure
  Option D was rejected for — a capability declaration becoming load-bearing on
  containment — and it had been shipped inside the type.

  The three v1 mechanisms are genuinely different and the contract does not
  flatten them:

  | Harness | Mechanism | Repo write | Network |
  |---|---|---|---|
  | Claude Code | tool removal (`--tools Read Grep Glob`; a bare tool name "removes the tool from Claude's context entirely", which also removes the non-configurable read-only command set that survives even `dontAsk`) | `harness` | `harness` — **enumeration-derived**: no Bash, WebFetch or WebSearch means no egress, but that is a property of a list, so any tool the adapter fails to account for, or any new built-in in a future release, restores it. The design does not enable Claude Code's own OS sandbox, so there is no layer beneath the list |
  | Codex | OS sandbox (`sandbox_mode` read-only — Seatbelt on macOS, Landlock + seccomp on Linux, restricted token on Windows denying `.git`) | `os`, pending the rollout gate below | `os` **for `AF_INET` only** — the seccomp filter blocks `connect`/`bind`/`sendto` with **`AF_UNIX` exempted** ([`nox-security.md:1130-1138`](../research/nox-security.md), itself flagged secondary-source-only). Reachable Unix sockets on a developer machine routinely include the Docker daemon socket and an SSH agent, and a model-generated command reaching `/var/run/docker.sock` is a full escape. Two things bound this and both are recorded rather than assumed: `SSH_AUTH_SOCK` is **deliberately** excluded from C-1008, and Landlock read-only mode denies filesystem writes, which *plausibly* blocks socket connection — **plausibly is not verified**, and this residual stays open in §5.8 of the companion until a fixture closes it |
  | OpenCode | config deny (`OPENCODE_CONFIG_CONTENT` inline denying `bash`/`edit`/`write`/`webfetch`/`websearch` — the deny map is the whole mechanism; `--pure` is the only argv-visible word and it corroborates the derivation rather than enforcing anything) | `attested` | `attested` |

  OpenCode's `attested` level is not a formality: the research records
  OpenCode's enforcement as *not documented as harness-level*, with
  [anomalyco/opencode#8832](https://github.com/anomalyco/opencode/issues/8832)
  reporting `"git": "deny"` ignored and closed as not-planned. Under T3 the
  worktree shares `refs/` with the real repository, so `attested` is the only
  thing between OpenCode and the user's git history — which is precisely why
  it must appear in the envelope under that name rather than as `True`.
  nox's own git invocations pass `-c core.hooksPath=/dev/null`.
- **C-1023 — `passthrough` is policed by a per-adapter allowlist.** The
  previous formulation was a six-name denylist, and a denylist of flag *names*
  cannot police a flag that carries an arbitrary *value*. Verified against the
  local binaries: `codex exec review` documents
  `-c, --config <key=value>` with its own help examples being a
  sandbox-permission widening and `shell_environment_policy.inherit=all`, so
  `-c sandbox_mode=danger-full-access` disables the OS sandbox by last-wins,
  `-c mcp_servers={…}` re-declares the very servers C-1005 removes, and
  `-c shell_environment_policy.inherit=all` undoes the C-1008 scrub from
  inside the child; `claude --help` documents `--settings <file-or-json>`,
  whose own `--restricted` help text states that `--settings` **still
  applies**, so `--settings '{"hooks":{"SessionStart":[…]}}'` is arbitrary
  command execution surviving the entire `--safe-mode --restricted
  --strict-mcp-config` stack, alongside `--setting-sources`, `--mcp-config`,
  `--agents`, `--plugin-dir`, `--tools` and `--permission-mode`. None of those
  names a denied flag. The companion cites Saltzer & Schroeder — "base access
  decisions on permission rather than exclusion" — for the tool list and then
  policed its highest-risk field by exclusion; the contract is now consistent
  with the principle it invokes. Four rules:

  1. **Allowlist per adapter.** `PASSTHROUGH_ALLOW[adapter]` is a shipped
     literal frozenset of flag names known to be inert with respect to
     containment (`--model`, `--title` and their per-harness equivalents).
     Anything not in it is refused with a `ConfigError` naming the element.
  2. **No value-carrying configuration flag is ever allowlistable.** `-c`,
     `--config`, `--settings`, `--setting-sources`, `--mcp-config`, `--agents`,
     `--plugin-dir`, `--tools`, `--permission-mode`, `--system-prompt`,
     `--append-system-prompt`, `--permission-prompt-tool`, `--enable`,
     `--disable` and any future member of that class are refused
     unconditionally, matched on the token before `=` as well as on the bare
     token so `--settings={…}` is caught.
  3. **No duplicate of a nox-owned flag.** A `passthrough` element naming a
     flag nox itself emits is refused: a duplicate is either a no-op or an
     override, and neither is ever wanted.
  4. **Ordering is part of the contract.** nox emits `passthrough` first and
     its own containment flags **last**, on every harness where last occurrence
     wins. The previous design specified no ordering at all.

  **Rules 1 and 3 compose to nearly-empty allowlists, and that is the correct
  answer rather than an accident.** An earlier revision allowlisted `--model`
  on all three adapters while C-1030 had every adapter emit the model flag
  itself — so rule 1 permitted it and rule 3 refused it, a self-contradiction
  on the field C-1016 calls the highest-risk in the design. It failed *closed*,
  so nothing was exposed, but the §§6.1–6.3 tables advertised a flag no user
  could ever pass. The model flag is gone from the allowlist: model selection
  goes through C-1030's capability class, which is a better surface than
  passthrough anyway. What remains is `--title` on Codex and nothing at all on
  the other two.

  `DENIED_FLAGS` survives, re-scoped: it is no longer the gate on user argv
  (rule 1 subsumes it) but a regression assertion over **nox's own emitted
  argv**, so no future adapter edit can introduce
  `--dangerously-bypass-hook-trust`,
  `--dangerously-bypass-approvals-and-sandbox`,
  `--dangerously-skip-permissions`, `--bare`, `--add-dir` or `--auto`.
  `--dangerously-bypass-hook-trust` matters most: content-hashed hook trust is
  the *only* thing standing between a hostile branch and Codex's
  `SessionStart` hooks. `--bare` is excluded for a second reason — it forces
  `ANTHROPIC_API_KEY`/`apiKeyHelper` and never reads OAuth credentials,
  colliding head-on with the settled subscription-auth constraint.
- **C-1025 — the containment stamp is derived from the final argv, never
  written by hand.** `Containment` is computed *after* `prepare()` has produced
  the invocation, by inspecting the resolved argv and environment against the
  adapter's declared mechanism, plus — where the enforcement level is `os` —
  a cached probe result keyed on the harness binary version. An adapter cannot
  return a plan that the argv does not implement, because the plan is not what
  is stamped. This is what makes C-1007 testable at all: with a hand-written
  literal, an adapter returning `write_enforcement="os"` passes every possible
  test, and the Codex rollout gate below is enforced by an implementer
  remembering a table row rather than by code. With derivation, "blocked until
  the sandbox key is resolved" is enforced by the absence of a passing probe.

  **All three levels are derived, not just `os`.** Saying only that `os`
  requires a probe left `harness` and `attested` to be invented per implementer,
  and the C-1007 launch gate would still have been reading a self-declared value
  on those axes — the exact failure this contract exists to remove, surviving on
  two thirds of the surface. The derivation is a shipped table per adapter, from
  the resolved argv and environment:

  | Adapter | Axis | Feature required in the resolved invocation | Level |
  |---|---|---|---|
  | claude | write | `--tools` present, its value a subset of `{Read, Grep, Glob}`, and no `--add-dir` | `harness` |
  | claude | network | same `--tools` check (removing Bash, WebFetch and WebSearch is what removes egress) plus `--strict-mcp-config` | `harness` |
  | codex | write | `-c sandbox_mode=read-only` present **and** the cached sandbox probe passed under the C-1025 cache key | `os` |
  | codex | network | as above | `os` (`AF_INET` only — see C-1007) |
  | opencode | write | `OPENCODE_CONFIG_CONTENT` present in `Invocation.env` and denying `bash`/`edit`/`write`, plus `--pure` present in argv and followed by a flag (rule 2) | `attested` |
  | opencode | network | same, denying `webfetch`/`websearch` | `attested` |

  **The `os` cache key is the whole of that level's integrity, so it is not the
  version string.** A version alone says nothing about *which* binary answered:
  a different resolved executable on `PATH`, a different platform (Landlock is
  Linux-only; Seatbelt macOS; the Windows path is a restricted token), a
  different launcher prefix (`ocx package exec …` resolves elsewhere entirely),
  different containment argv, or a different environment can each make a stored
  pass irrelevant while the version matches — and the failure mode is a later
  invocation stamped `os` on the strength of a probe that never covered it. The
  key is a digest of: the **resolved executable realpath and its content
  hash**, the **platform triple**, the **launcher prefix**, the
  **containment-relevant argv**, and a hash of the **C-1008 environment**. Any
  mismatch is a cache miss, and a miss is not a failure — it is a re-probe, or,
  where probing is not possible, `None` and a refusal to launch.

  Any axis whose feature is absent derives `None`, and `None` refuses launch.
  The level is a property of what was emitted, so the §9.4 stub-adapter test
  exercises **all three** levels — a stub claiming `os` without the probe, one
  claiming `harness` without the `--tools` restriction, and one claiming
  `attested` without the config-deny env — and each must fail.

#### Process and environment

- **C-1008 — minimal environment, allowlist-shaped, with a credential-pattern
  denylist on top.** Infrastructure variables pass, **enumerated by name and
  never by class**: `PATH`, `HOME`, `USER`, `LOGNAME`, `TERM`, `LANG`,
  `LC_ALL`, `TMPDIR`; the proxy names `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`
  and their lowercase forms `http_proxy`, `https_proxy`, `no_proxy`; the
  CA-bundle names `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`;
  the config roots `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `CLAUDE_CONFIG_DIR`,
  `CODEX_HOME`; `OPENCODE_AUTH_JSON`; and the Windows set
  `SystemRoot`/`SystemDrive`/`USERPROFILE`/`APPDATA`/`LOCALAPPDATA`/`ComSpec`/
  `PATHEXT` that CPython documents as mandatory.

  *An earlier revision wrote "the proxy set" and "the CA-bundle set" here.
  A closed allowlist whose text delegates membership to whatever the
  implementation happens to spell is not closed, and only a test was enforcing
  the strict reading — so the classes are expanded and the contract now says
  what the oracle checks (**E48**).* Two corrections travel with the list:
  `OPENCODE_AUTH_JSON` is struck by **E19/D-ad** — the name does not exist at
  1.18.22 and is absent from the shipped allowlist — and the Windows set is
  inert under v1's POSIX-only scope (**D-j/E6**).

  Everything else is dropped, **including a name that reads as a member of one
  of those families and is not on this list**. Seven names ship past this
  enumeration and every one is recorded rather than implied: `ALL_PROXY`,
  `all_proxy`, `SSL_CERT_DIR`, `CURL_CA_BUNDLE` and `LC_CTYPE` (E48), plus
  `XDG_CACHE_HOME` (D-s's launcher route — `ocx package exec` resolves a pinned
  coordinate out of the cache) and `CLAUDE_SECURESTORAGE_CONFIG_DIR` (WP7a —
  without it every claude review refused `UNAUTHENTICATED` while the harness was
  in fact logged in). The last two were named nowhere in this contract, which is
  the half of E48's structural correction it recorded as closed and was not
  (**E57**); the enforcement is an EQUALITY in the acceptance oracle
  (`test_the_minimal_environment_forwards_c1008s_infrastructure_and_no_more`),
  so an edit to `ALLOWLIST` in either direction now fails until the name is
  written down **in the oracle** beside its record citation. Not in this
  document: the oracle's second operand is a literal `frozenset` in
  `test_adversarial_fixture.py`, nothing in the suite reads the ADR, and the
  test passes against a copy of `nox/` with no `.agents/` present at all. Anything
  matching
  `*_TOKEN`, `*_KEY`, `*_SECRET`, `*_PASSWORD`, `AWS_*`, `GITHUB_*`, `GH_*`,
  `NPM_*`, `PYPI_*`, `OPENAI_*`, `DATABASE_*` is dropped even if it would
  otherwise pass ([`nox-security.md:348-376`](../research/nox-security.md)).
  **A missing infrastructure variable raises a nox-authored error naming the
  variable** — dropping a credential degrades safely while dropping
  infrastructure fails confusingly, and users respond to confusing failures by
  disabling scrubbing entirely.

  Three further rules, each closing a hole the first formulation had.

  1. **The minimal environment is built once, before the probe** — not inside
     `prepare()`. The probe is a real harness startup (C-1014) and must not run
     with the ambient environment any more than the review does.
  2. **The environment is an *inbound* channel, not only an outbound one.** T4
     is about credentials leaking outward; there was no counterpart for
     attacker *values* arriving inward, and the allowlist forwards exactly the
     variables that would carry one. A branch's `.envrc` or `mise.toml` is
     sourced **in the user's own shell** when they check the branch out to look
     at it — that is what direnv and mise are for — so a hostile branch can set
     `CODEX_HOME=/tmp/x` before nox is ever invoked. C-1008 then forwards it
     because auth needs it, and Codex reads `/tmp/x/hooks.json` *and*
     `/tmp/x`'s trust store, so the content-hash gate the entire Codex safety
     case rests on blesses attacker-authored hooks.
     `--ignore-user-config` does not help: it kills
     `$CODEX_HOME/config.toml`, not `$CODEX_HOME/hooks.json`. The same shape
     applies to `CLAUDE_CONFIG_DIR`, to `OPENCODE_AUTH_JSON`, and in its
     strongest form to `HOME`. Filtering these files out of the *worktree*
     does nothing here, because the export happened in the parent shell
     against the user's real tree. **Rule:** for `HOME`, `XDG_CONFIG_HOME`,
     `XDG_DATA_HOME`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME` and
     `OPENCODE_AUTH_JSON`, nox resolves the value and refuses to forward it if
     it resolves inside the repository under review; a value under a
     world-writable directory is forwarded with a loud warning carried in the
     review envelope. This is threat T4b in the companion.
  3. **The allowlist's security value is what it excludes by construction, and
     that is written down so it survives a future "just add one more" edit.**
     Never forwarded, deliberately: `NODE_OPTIONS` (`--require` injects into
     any Node harness — Claude Code and OpenCode both), `BUN_*`, `LD_PRELOAD`,
     `PYTHONSTARTUP`, `GIT_SSH_COMMAND`, `GIT_EXTERNAL_DIFF`, and
     **`SSH_AUTH_SOCK`** — the last of which is load-bearing against C-1007's
     `AF_UNIX` residual and must not be re-added as an ergonomics fix.
  4. **The environment carries the C-1031 git overrides outward.**
     `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_n`, `GIT_CONFIG_VALUE_n` and
     `GIT_ATTR_NOSYSTEM=1` are *constructed by nox*, never forwarded from the
     parent — a parent-supplied value would be an inbound channel of exactly
     the T4b shape, and these keys are the ones that decide whether a
     child-issued `git` runs a hook. They are set, not passed through, and any
     inherited value of the same names is dropped before they are.
- **C-1009 — subprocess hardening is fixed, not configurable.** `shell=False`
  with argv as a list, never an f-string (CWE-78); on Windows resolve the real
  executable rather than a `.cmd` shim, which the OS re-parses through
  `cmd.exe` regardless of Python quoting. The diff is **never** an argv element
  and never stdin — it is written into nox's own scratch directory beside the
  ephemeral worktree (E20) and referenced by path, which removes the 10 MB
  stdin cap, removes the inline-versus-
  self-collect size branch `codex-plugin-cc` has to carry, and needs no shell
  to read.

  **The scratch directory is `.nox-<random>/`, created fresh, never a fixed
  `.nox/`.** A fixed name is a path *inside the tree under review*, and
  everything in that tree is attacker-controlled by construction. A branch that
  commits `.nox/keep` makes `mkdir` raise `FileExistsError` and every review of
  that branch fail permanently — a one-file denial of service, and a review
  that never runs is a review that never objects. The obvious remedy,
  `exist_ok=True`, is worse: a committed `.nox` symlink pointing at
  `~/.claude` then turns the diff write into an arbitrary file write outside
  the worktree (CWE-59). The `nox` PyPI session runner creates exactly a
  `.nox/` directory, so the collision is not hypothetical. A name from
  `secrets.token_hex` cannot be pre-created by a branch, so `os.mkdir` without
  `exist_ok` succeeds or the tree is not what nox just checked out; the diff is
  then written with `O_NOFOLLOW|O_CREAT|O_EXCL`. **Placement reversed by E20:
  the directory is a SIBLING of the worktree, `mkdtemp`ed in nox's temp space,
  never a child of it.** Inside the worktree it put nox's own prompt into the
  surface under review, and a reviewer doing its job then reported repository
  content as addressing and directing it — a `high` finding manufactured on
  every single run, which trains an operator to dismiss the one finding class
  that catches real injection. C-1005 neutralizes the branch's instruction
  surfaces; nox may not then add one of its own. Every naming rule above is
  kept unchanged. **The reason it was placed inside is not struck, because it
  is a precondition on any future change:** Claude Code under `--restricted`
  "confines the file tools to the working directories", so a path outside the
  worktree is not readable by the harness that needs it. That costs nothing
  while nothing reads a scratch path — every merged adapter delivers the prompt
  as an argv word through `argv_prompt`, and the Codex leg takes
  `--base refs/nox/base/<token>` rather than `<scratch>/review.diff` — and it
  binds again on the first adapter that moves to a file-delivered prompt or
  diff, which must re-establish out-of-worktree readability (`--add-dir`, or
  whatever that harness's equivalent turns out to be) or move its scratch back
  inside and accept the manufactured finding on every run.
  `start_new_session=True` so a timeout kill reaps
  grandchildren; SIGTERM to the process group, grace period, then SIGKILL —
  SIGTERM first because it gives Claude Code a defined exit 143 and runs its
  `SessionEnd` hooks. Cap captured output at 8 MiB and record `truncated`.
  Merge stderr into stdout and drain in a dedicated thread — not `selectors`,
  which does not support pipes on Windows
  ([`nox-tech-tooling.md:76`](../research/nox-tech-tooling.md)).
- **C-1010 — timeout policy is derived per `Heartbeat.kind`, never global.** A
  wall-clock ceiling always applies. A *silence* timeout applies only where
  silence is meaningful: `Semantic` 120 s, `ByteActivity` 300 s,
  `ProcessOnly` **none at all** — absence of activity carries no information
  when the only signal is that a PID exists. pytest-xdist is the cautionary
  precedent: a worker can spin forever because timeout ownership and liveness
  classification live in two layers that disagree
  ([`nox-pattern-precedent.md:53`](../research/nox-pattern-precedent.md)). nox
  owns both, in one place — and this is what that one place decides:

  **`Heartbeat.touch(now, semantic=False)` updates a byte-activity timestamp
  and never resets the silence clock.** The `Semantic` silence window is over
  *events*, not bytes. A harness emitting a stack trace, a progress bar or a
  Node deprecation warning for longer than the window is treated as silent and
  killed, because a review producing only noise for two minutes is a hang. The
  kill is reported as `timed_out` with **both** timestamps in the detail
  string, so "noisy but eventless" is distinguishable from "dead" without
  guessing. The alternative — letting bytes reset the clock — would make the
  120 s `Semantic` window do nothing that the 300 s `ByteActivity` window does
  not do better, which is to say it would delete the distinction the type
  exists to carry.

  **The thresholds are unmeasured engineering defaults and are labelled as
  such** — 120 s, 300 s, `grace_s = 5.0`, and the 8 MiB byte cap in C-1009 have
  no measurement behind them. The risk is concentrated in the 120 s window: a
  large diff under extended thinking can plausibly exceed it between stream
  events, and the consequence is a working review killed and reported as
  `timed_out`. The contract suite records observed inter-event gaps per harness
  and the default is revised from that data before release; until then the
  wall-clock ceiling is the number to trust.

#### Outcome, capability and configuration

- **C-1011 — tri-state outcome, and the exit code is never the success gate.**
  `ok | error | indeterminate`. All three v1 harnesses put the failure *kind*
  in the JSON stream rather than the exit code — **observed on one, documented
  on one, inferred on one**, and the difference is worth keeping straight
  because C-1020's drift detector should be testing a behaviour rather than a
  belief. **Observed:** OpenCode's provider-resolution failure exited 1 with
  `{"type":"error",...,"error":{"name":"UnknownError",...}}` on stdout, the
  only empirical harness observation in the whole research set
  ([`nox-tech-tooling.md:18-22`](../research/nox-tech-tooling.md)).
  **Documented:** Claude Code "prints the failure as the result on stdout" and
  can exit 0 with an auth failure inside it
  ([`nox-security.md:613-614`](../research/nox-security.md)) — vendor
  documentation, directly on point, not run.
  **Inferred:** Codex under `--ask-for-approval never` returns "execution
  failures … immediately … to the model"
  ([`nox-security.md:1155-1157`](../research/nox-security.md)) — that sentence
  is about *approval policy*, and reading exit-code-versus-stream divergence
  out of it is an inference. The contract stands on the fail-safe direction
  regardless of which reading is right; the evidence claim is now stated at its
  real strength. Anything nox cannot
  positively classify is `indeterminate` and surfaces raw. **Indeterminate
  never collapses to ok** (Boost `tribool`'s indeterminate-propagates rule).
  Exactly one explicit narrowing helper is provided so callers who have decided
  can stay two-branch after a visible decision point.
- **C-1012 — four failure states are contract-required and distinguishable
  without any interactive prompt** *where the harness distinguishes them*:
  `absent`, `unauthenticated`, `rate_limited`, `malformed_output`. `timed_out`,
  `killed` (exit 143 is labelled *we killed it*, never folded into generic
  failure), `isolation_failed`, `unsupported` and `invalid_config` are
  additional, non-contract members of the same closed enum.

  **The per-harness escape, and why it is needed.** The only OpenCode error
  shape ever observed is a generic `{"name":"UnknownError","data":{"message":
  "Unexpected server error…"}}` from a *provider-resolution* failure
  ([`nox-tech-tooling.md:18-22`](../research/nox-tech-tooling.md)). If
  authentication failure and HTTP 429 surface under the same name — which is
  what "UnknownError" suggests — nox cannot separate `unauthenticated` from
  `rate_limited` on that harness at all, and the alternatives are to violate
  the contract or to substring-match `data.message`, which no contract
  specifies and which the harness can change on any patch release. So: **each
  adapter ships a classification table, backed by observed output, mapping
  harness error shapes to `FailureReason`. Where the harness does not
  distinguish two states, the adapter resolves `indeterminate` and stamps the
  raw error name; it never guesses.** C-1021's "`rate_limited` stops the run"
  is unaffected, because `indeterminate` also stops the run — the tri-state
  fails toward not-retrying, which is the safe side of the 26-day lockout tail.
- **C-1013 — capabilities are a closed enum; absence means unsupported.** No
  permissive booleans, no defaults-on state — LSP's normative model, twice
  validated (LSP and MCP,
  [`nox-pattern-precedent.md:33-41`](../research/nox-pattern-precedent.md)).
  Two members carry the harness asymmetry explicitly and must not be merged:
  **`ENUMERABLE_DENY`** (nox can state how this harness is contained —
  required to launch, all three have it) and **`ENFORCED_READ_ONLY`** (the
  harness enforces it below the model — Claude Code yes via pre-tool-call
  permission evaluation, Codex yes via an OS sandbox that is on by default,
  OpenCode **no**). Absence is stamped into the review envelope, never papered
  over, and is enforced at the *gate*: `prepare()` raises on a missing required
  capability rather than trusting callers to check. **The required set is
  itself a shipped literal** — `REQUIRED: Final[frozenset[Capability]] =
  frozenset({ENUMERABLE_DENY})` — because "raises on a missing required
  capability" with the required set left unstated is a contract no test can be
  written against. `ENFORCED_READ_ONLY` is deliberately *not* in it: OpenCode
  ships without it and still launches, with the absence stamped.
- **C-1014 — the availability probe raises; it never returns a sentinel, it is
  not `shutil.which` alone, and it runs contained.** A harness may be reachable
  only through a runner prefix — `ocx package exec
  ocx.sh/anomalyco/opencode:1.18.22 -- opencode …` is a live, working example
  ([`nox-tech-tooling.md:7`](../research/nox-tech-tooling.md)). The probe is a
  real short invocation through the configured launcher and raises
  `HarnessUnavailable` carrying a `FailureReason` and the cause string,
  following `keyring`'s priority-raises idiom.

  **Because it is a real invocation, it is a real harness startup, and a
  harness startup is the attack.** OpenCode loads `.opencode/plugins/` at
  startup unconditionally, outside the permission model, with no documented
  off-switch — a `--version`-class invocation is a startup. A subprocess with
  no `cwd=` inherits its parent's, and nox's parent cwd is the user's working
  tree with the hostile branch checked out and un-neutralized, because the
  workspace does not exist yet at this point in the flow. The specification, as
  drawn, produced code that executes attacker-supplied JavaScript with Bun
  shell access in the live tree before any of the three controls had been
  applied, and did so with the full ambient environment. That is T1 fired
  through the one step of the flow the threat model did not cover, and a direct
  violation of C-1003 committed by the flow the design itself specifies.
  **Therefore:** the probe runs with `cwd` set to a **fresh empty temporary
  directory nox owns and removes**, never an inherited cwd and never the repo,
  and with the C-1008 minimal environment, which is built before the probe for
  this reason. The §9.4 fixture asserts `.opencode/plugins/evil.ts` does not
  execute during the **probe**, not only during the review.
- **C-1015 — the `Runner` seam wraps process *creation only*.**
  `Runner.spawn` returns a `Process`; supervision (deadline, silence timeout,
  byte cap, SIGTERM→SIGKILL escalation) is a pure function over `Process` and
  is fully tested against a fake. The single `subprocess.Popen(...)` call is
  the only `# pragma: no cover` line in the codebase. This refines the
  discussion's sketch, which placed the seam around the whole run and would
  have left the escalation logic uncovered by the very seam that exists to
  cover it.
- **C-1016 — config is a normalized core plus an opaque passthrough, with an
  enumerated permission surface.** Core: `model`, `read_only`, `timeout`,
  `tools_allowed`. Passthrough: verbatim per-harness argv — **the highest-risk
  field in the design**, and the field C-1023 polices. Fail **soft** on
  unknown keys (warn, ignore — a forward-compatibility signal that changes
  nothing about the enforced boundary); fail **hard** on a malformed value on
  any key in the literal permission set
  `{read_only, tools_allowed, passthrough, isolation, launcher}` — every
  possible default there is a guess about a security control (CWE-1188). The
  set is a literal, not a heuristic, or the asymmetry degrades into a judgment
  call at every new key ([`nox-security.md:665-676`](../research/nox-security.md)).
  `tomllib` supplies the syntax half for free by raising on malformed TOML.

  **Two of the core keys need their interaction with C-1007 stated, or they are
  footguns.** `read_only = false` is **refused** with a `ConfigError` naming
  C-1003 and C-1007: there is no in-tree, no non-read-only mode in v1, so the
  only two possible behaviours were "accept it and refuse every launch" and
  "accept it and silently ignore it", and a loud refusal at config load beats
  both. The key is retained rather than deleted because it is the seam Option D
  reopens; its v1 domain is `{true}`. `tools_allowed` may only **narrow** the
  adapter's own containment set — any element not already in that set is a
  `ConfigError`, so it can never restore Bash on the tool-removal leg.
- **C-1030 — the shared config core selects a *capability class*, never a
  literal model name; adapters own the class → literal map.** This reuses
  [`adr_0001`](adr_0001_model_matrix_capability_classes.md)'s existing
  precedent rather than inventing a second vocabulary — its C-001 defines
  exactly two classes at one definition site, `fast-balanced` (the capable
  default workhorse) and `deep-reasoning`
  ([`adr_0001:368-371`](adr_0001_model_matrix_capability_classes.md)), under
  the rule "cells hold **capability classes, never literal model names**"
  ([`adr_0001:23-26`](adr_0001_model_matrix_capability_classes.md)). hex
  already instantiates them per harness in `hex.md › Preferences`, so this is
  the vocabulary hex hands nox when it configures the adversary. Making it a
  second vocabulary would be a mapping table between two names for one thing.

  A bare `model: str` in the shared core was wrong on all three legs at once:
  `sonnet` means nothing to Codex, `gpt-5.4` means nothing to Claude Code, and
  OpenCode requires a `provider/model` prefix a bare string never supplies —
  three harnesses, three identifier vocabularies, one field.

  1. **Core:** `model: ModelClass | None`, `ModelClass = Literal[
     "fast-balanced", "deep-reasoning"]`. `None` means the harness default.
     The map is open-keyed so a **third class is an `adr_0001` vocabulary
     change, not a nox change** — no third tier is added here speculatively.
  2. **Per adapter:** a shipped `MODELS: Mapping[ModelClass, ModelSpec]`,
     overridable **only** in that harness's own `[harness.<name>]` section of
     `nox.toml`. A literal ID is accepted there and nowhere else, so a
     wrong-harness model string is unrepresentable by construction rather than
     caught by a check.
  3. **`ModelSpec` is typed, and that is a security property, not
     ergonomics.** On some harnesses more effort is the same model with a
     reasoning knob rather than a different model: Claude Code has
     `--effort <level>` (verified on the local v2.1.252 `--help`), Codex sets
     `model_reasoning_effort` through `-c`, and OpenCode has no equivalent —
     being BYOK, effort there is provider-specific. So
     `ModelSpec = str | ModelSpecT`, where `ModelSpecT` is a frozen
     `{model: str, effort: str | None}` and a bare string is shorthand for
     `ModelSpecT(model=..., effort=None)`. **It is never a raw argv
     fragment.** Codex's effort knob rides `-c`, which C-1023 refuses
     unconditionally from `passthrough`; permitting
     `deep-reasoning = "-c model_reasoning_effort=high …"` would reopen that
     exact hole through the back door and defeat the allowlist. The adapter
     maps a typed value to flags; the config never supplies argv.
  4. **OpenCode's literal must carry the provider prefix**, and `probe()`
     verifies that provider is actually configured. `opencode providers list`
     is confirmed safe to shell out to as a preflight — run live during
     research it reported `0 credentials` without prompting or blocking
     ([`nox-tech-tooling.md:32`](../research/nox-tech-tooling.md)). An
     unconfigured provider is `unauthenticated` (C-1012), not a crash and not a
     mid-review failure. Note that nox does **not** forward
     `OPENCODE_<PROVIDER>_APIKEY`: it is not on the C-1008 allowlist, so
     OpenCode must be configured through its own auth store — which is C-1002
     working as intended, not an oversight.
  5. **Invalid values fail soft, on purpose — but the literal map is
     trust-gated.** An unrecognized class, or a literal that does not resolve,
     produces a warning and the shipped default — **never** a `ConfigError`.
     `model` is deliberately not in `PERMISSION_KEYS`: every possible default
     for it is a real model rather than a guess about a security control, which
     is precisely the C-1016 asymmetry. Failing hard would hand a hostile
     repo-local `nox.toml` containing `model = "garbage"` a one-line denial of
     service against its own review — the same shape as the evaluation-order
     defect C-1017 closes, arriving through a different key.

     Fail-soft on the *class* does not license fail-soft on the *literal*.
     Because C-1017's drop rule is keyed on `PERMISSION_KEYS`, leaving the
     whole of C-1030 outside it also left the `[harness.<name>]` literal map
     outside it — so an untrusted repo-local `nox.toml` could redirect any
     review to a model of the branch author's choosing, and rule 5's own
     fail-soft meant a bad value warned rather than refusing, so nothing
     surfaced it. `shell=False` bounds the damage to one argv token rather than
     an injected flag, which is why this is a hardening gap and not a breach —
     but "the config never supplies argv" should be enforced, not asserted.
     **Therefore:** `[harness.<name>]` model literals are **dropped from an
     untrusted repo-local file** with a warning, exactly like a permission key,
     and nox's shipped `MODELS` default is used. `model` itself — the class —
     stays freely settable from any file, because a closed two-member `Literal`
     cannot express anything worse than a warning. Additionally, a literal that
     begins with `-` or contains whitespace is rejected wherever it is
     supplied: it can only be an attempt to smuggle argv through a value slot.
  6. **`MODEL_SELECTION` stays a capability.** A harness that does not hold it
     resolves any class to the harness default and records `Review.model =
     None` — it never guesses a literal. `Review` records the **resolved
     literal** on both sides as before, now alongside `model_class`: the
     arXiv:2607.21656 asymmetry evidence is more useful with both, because the
     class says what the user asked for and the literal says what answered.

  *The quality review's `adr_0001` audit cleared this document, correctly, on
  the two things it checked — nox's `Capability` enum is harness capability, an
  unrelated concept, and `Review.model` is a recorded runtime value that
  `adr_0001` explicitly permits. It did not check the config **input**, which
  is the leg `adr_0001` actually governs. Recorded so the next reader knows the
  audit was narrower than its verdict sounded.*
- **C-1017 — config resolved from the repository may not supply
  permission-surface keys unless the file is trusted.** Upward search from
  cwd, first `nox.toml` wins, max depth 20, never crossing a filesystem
  boundary (`st_dev`), robust to the name being a directory
  ([uv#7351](https://github.com/astral-sh/uv/issues/7351)). Non-permission
  keys from a repo-local file are used freely. Permission-surface keys are
  **dropped with a warning** unless the file's path *and content hash* are
  recorded as trusted in the user config dir — mise's paranoid model, whose
  necessity is evidenced by a real bypass advisory
  ([GHSA-436v-8fw5-4mj8](https://github.com/jdx/mise/security/advisories/GHSA-436v-8fw5-4mj8)).
  Dropping is the fail-closed direction, because nox's own defaults are the
  restrictive ones; a hard abort would hand any repo a one-character
  denial-of-service against its own review. **Note the parallel:** this is the
  same failure Codex has and Claude Code does not — path-scoped versus
  content-scoped trust — and nox takes the content-hashed side deliberately.

  **Evaluation order is part of the contract: drop first, then validate what
  survives.** The reverse order reopens T6 completely. A hostile branch adding
  a `nox.toml` containing `read_only = "yes"` hits C-1016's fail-hard rule —
  `read_only` is a permission key, the value is malformed, `ConfigError`, nox
  never runs — and the two sections that argue at length for drop-not-abort are
  bypassed by a parser that ran first. So: resolve trust, remove every
  permission key the file is not trusted to supply, and only then validate the
  keys that remain. A malformed permission value in an **untrusted** repo-local
  file is dropped with a warning and never raises; a malformed permission value
  in a **trusted** file raises, because there the user expressed an intent about
  the boundary that nox cannot read.
- **C-1018 — the finding schema is fixed, and severity uses hex's
  vocabulary.** `Block | High | Warn | Suggest`
  ([`protocol.md` § Finding severity](../../hex/hex-core/references/protocol.md)).
  Inventing a second vocabulary plus a mapping table for a consumer set of one
  is exactly the abstraction this project does not build. `verdict` is `null`
  whenever `status != ok`. The untruncated harness output is retained in `raw`
  unconditionally.

  **`raw` is a credential sink, and persistence is a separate question from
  trust.** Under Codex the containment mechanism is an OS sandbox, and Landlock
  read-only denies writes and network, **not reads** — so a model-generated
  command can `cat ~/.aws/credentials`, `~/.ssh/id_ed25519` or
  `~/.claude/.credentials.json`, and the review body is an egress channel by
  definition because a human reads it. C-1019 says do not *trust* `raw`;
  nothing said do not *persist* it, and `raw` flows onward into hex's Fold-Back
  phase, which may write review content into a spec or plan artifact that gets
  committed. **Therefore:** the C-1021 call log never carries `raw`; nox scans
  `raw` for known credential shapes (`AKIA`, `ghp_`, `sk-ant-`,
  `-----BEGIN … PRIVATE KEY`) and high-entropy tokens and **flags the review**
  rather than redacting silently, so the user knows something was read; and
  nox's docs state that a consumer folding review text into a committed
  artifact must review it first.
- **C-1019 — review output is untrusted content and is never presented as
  authoritative.** A diff that induces the adversary to emit "this is clean",
  or a confident wrong finding that sends the user to change unrelated code,
  is an attack no permission flag touches
  ([`nox-security.md:115-119`](../research/nox-security.md)). nox's envelope
  carries the containment stamp (isolation mode, neutralization set applied,
  containment mechanism, `ENFORCED_READ_ONLY` present or absent) so the
  consumer can weight the finding, and nox's docs state the limit rather than
  implying safety.

#### Transport and operability

- **C-1024 — v1 adapters are argv plus a line-oriented stream. No adapter runs
  a long-lived protocol session.** Codex's `app-server` is `[experimental]`,
  and whether it honours the project-trust and hook-trust gates is
  undocumented — the research names it as the one fact it would not ship on.
  v1 uses `codex exec review --json`, which is non-experimental, has
  documented trust behaviour, and carries `--output-schema`, `--ephemeral`,
  `--strict-config`, `--ignore-rules` and `--ignore-user-config`. When the
  app-server is adopted later, the single facade change it requires is one
  `Process.send(line)` method; nothing else in the seam moves. That
  one-method delta is why it is deferred rather than designed around.

  **Fresh evidence, in the same direction.** The MCP specification's
  **2026-07-28** release deprecates *sampling* — the mechanism by which a
  server asks its host to make a model call — in favour of servers calling
  providers directly
  ([blog.modelcontextprotocol.io, 2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28/)).
  That is the ecosystem moving away from routing model invocation through a
  long-lived protocol session and toward the plain-subprocess shape this
  contract picks. It is corroboration, not the reason: the reason remains that
  Codex's app-server is `[experimental]` with undocumented trust behaviour.
- **C-1020 — every adapter records the harness version it was verified
  against.** Mismatch warns at invocation ("untested against vX") and does not
  refuse; a *parse* failure resolves to `indeterminate`, never to a clean
  verdict. Contract tests run the real binary, skipped via the probe when
  absent, and are the drift detector — a mock encodes the belief being tested,
  which is precisely the class of failure (exit 0 with an auth error in
  stdout) that mocks render invisible.

  **A drift detector that skips itself is not a drift detector.** On a CI
  container with none of `claude`, `codex` or `opencode` installed, every
  contract test skips, the suite is green, and flag churn — the thing decision
  driver C2 weights at 5 and these tests exist to catch — is detected only by
  whichever developer happens to have all three binaries locally. **Therefore:**
  one release-blocking CI job runs on a runner carrying all three binaries and
  asserts that the contract-test collection count is non-zero per adapter. The
  skip path stays, for contributors; it is not what gates a release.
- **C-1021 — every call is logged locally** (harness, model, timestamp,
  duration, outcome, cost when reported). No vendor exposes a pre-call quota
  check, and the documented lockout tail has no warning:
  [anthropics/claude-code#47754](https://github.com/anthropics/claude-code/issues/47754)
  — headless OAuth refresh blocked by Cloudflare WAF, 26+ days locked out, no
  recovery short of browser re-auth. nox never auto-retries a 403/429 refresh
  loop; `rate_limited` stops the run.
- **C-1022 — adversary calls are serialized by default.** Under C-1003 this is
  no longer a containment requirement — it is a quota requirement
  (practitioner convergence: 1–3 agents steady is fine, 5+ overnight hits
  limits within hours,
  [`discuss-nox-priorart.md:63`](../research/discuss-nox-priorart.md)).
  Concurrency becomes a supportable future option rather than an
  architecturally excluded one.

#### Completeness of the thing reviewed

- **C-1026 — a review that could not see the whole target says so, and cannot
  return `approve`.** `git stash create` carries staged and unstaged changes to
  **tracked** files; a file created and never `git add`ed appears neither in
  the worktree nor in the diff. The design named that fact four times and named
  its consequence nowhere, and the consequence is not a fidelity cost — it is
  the review tool's own worst failure. hex's contract-first flow creates new
  source and test files per work package; a user running the adversary gate
  before committing gets `ok`/`approve` on the three tracked files while the
  two untracked ones ship unreviewed, with the same status, the same
  containment stamp, and the same shape as a complete review. **Therefore:**
  before the workspace is built, nox runs
  `git ls-files --others --exclude-standard` scoped to the target. Every path
  it returns **and that was not materialized into the synthetic target** is
  recorded in `Containment.omitted`. When `omitted` is non-empty, `verdict`
  **may not be `approve`** under any circumstances; nox appends its own
  `high`-severity finding naming the omitted paths, and the summary leads with
  it. The review still runs and still returns findings — forcing
  `indeterminate` on any repo with an untracked scratch file would make the
  tool useless and would be disabled within a week — but it can never report
  success on something it did not look at.

  **The materialization clause is what keeps this contract from eating
  C-1027.** A plan artifact is untracked by construction, so an unconditional
  `git ls-files --others` made every plan-artifact review carry non-empty
  `omitted`, refuse `approve`, and append a `high` finding naming *the very
  artifact under review* — two contracts added in the same pass, neither
  mentioning the other. Scoping `omitted` to untracked paths that did **not**
  reach the synthetic target fixes it without a per-scope branch: under C-1027
  the artifact does reach it, so it is not omitted, and every other untracked
  file still is.

  Two smaller points, previously true only by composition. `verdict` is `null`
  whenever `status != "ok"` (C-1018), so on `indeterminate` this rule holds
  vacuously; and since `Verdict` has exactly two members, "may not be
  `approve`" means nox **overrides** a harness-returned `approve` to
  `needs-attention` rather than refusing the review. The nox-authored finding
  is the one element of `findings` that is *not* untrusted harness output, and
  carries `origin: Literal["nox", "harness"]` so a consumer weighting findings
  under C-1019 is not asked to tell them apart by eye.
- **C-1027 — `plan-artifact` is materialized explicitly, and a missing artifact
  is a hard failure.** The scope is declared in `ReviewTarget`, mapped onto
  hex's adversary contract, and had no path through the flow: `_resolve`
  branched on `ref` and otherwise fell through to `git stash create`, and a
  plan artifact is untracked or dirty *by construction* because it is written
  by `/hex-plan` or `/hex-architect` and reviewed before it is committed. Both
  files of this ADR were untracked while under review. As specified, the
  artifact would have been absent from the checkout, the diff empty, and the
  result `status=ok, verdict=approve, findings=()` behind a full containment
  stamp — an envelope that reads as *more* trustworthy than a real review, and
  the exact silent-total-indistinguishable-from-success failure this ADR
  rejects the permissive options for. **Therefore: the artifact is materialized
  as a one-file addition against the empty tree.** `_resolve` returns
  `base` = a synthetic commit over the **empty tree**; nox then `hash-object -w`s
  the file read from the user's working tree, builds a tree holding it at its
  repo-relative path, and `commit-tree`s that with the empty-tree commit as
  parent (C-1005's `-p` rule, uniformly). `path` must exist and must resolve
  inside `repo`; otherwise `ConfigError` before any spawn.

  **This deletes the special case rather than adding one, which is why it is
  shaped this way.** An earlier formulation returned the same empty-tree commit
  for *both* ends and copied the artifact into the scratch directory after
  checkout. That gave the scope a path through the *flow* and still left it with
  no path through the *review*: `git diff c..c` is empty, the scratch directory
  is outside any diff, no contract said how a harness was told where the file
  was, and `codex exec review` reviews a diff rather than a document — so the
  Codex leg had nothing to review and the other two had nothing to read. With
  base ≠ target the artifact **is** the diff, as a whole-file addition. Every
  downstream leg is then the code-diff leg unchanged: `review.diff` is
  non-empty, `--base <synthetic base>` resolves through real ancestry, the
  worktree contains exactly the artifact and nothing else, C-1028's existing
  slots need no plan-artifact special case, and no adapter learns a second
  invocation shape. The worktree still holds no other repository content, which
  is correct for reviewing one document and satisfies the neutralization set by
  construction. Verified against real git alongside the rest of C-1005.

  There is no path on which a plan-artifact review runs against a workspace
  that does not contain the artifact, and none on which it runs against an
  empty diff.

#### Public boundary and prompt

- **C-1028 — the prompt is a module, a contract and a work package, not three
  inline f-strings.** The prompt is the exact point where untrusted diff
  content meets the model — the one thing T5 says nothing structural closes —
  and it is where C-1005's statement of which paths were filtered has to live,
  where C-1019's framing of the reviewer's job is set, and where the wire
  schema is asked for on the harness without `STRUCTURED_OUTPUT`. The
  component contracts covered `outcome`, `liveness`, `capability`, `runner`,
  `harness`, `workspace`, `config` and `api`, and no prompt module; the rollout
  sequence had no prompt work package. Three adapter authors each writing their
  own would produce three unversioned, untested framings of the security-
  critical text. **Therefore:** `nox/prompt.py` owns one versioned template
  with per-harness slots, it is the only place review instructions are
  constructed, it states the filtered paths and the omitted-untracked paths
  verbatim, and it has its own tests and its own work package.
- **C-1031 — one fixed git environment governs every git process, nox's and
  the child's.** `-c core.hooksPath=/dev/null` was applied only to nox's own
  invocations, which left the larger half open: a worktree **shares
  `$GIT_DIR/config`** with the real repository, so any `git` the *model* is
  induced to run inside the workspace picks up `core.hooksPath`,
  `core.fsmonitor`, `includeIf`, `core.attributesFile` and every other
  executable extension the shared config carries. The branch does not need to
  write that config; it only needs to get the model to type `git`. Under Codex
  and OpenCode the model has a shell, so it can.

  **Therefore:** nox builds one override set and delivers it through
  `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_n` / `GIT_CONFIG_VALUE_n` in the C-1008
  child environment, which git applies to **every** invocation in the child's
  process tree rather than to one command line. The same set is used for nox's
  own git calls, replacing the per-call `-c` injection with a single list:

  ```
  core.hooksPath      = /dev/null      # no hook runs, in any worktree
  core.fsmonitor      = false          # fsmonitor spawns a configured command
  core.attributesFile = /dev/null      # user-level attributes cannot re-apply
                                       #   a filter (C-1005 removes the tree's)
  ```

  plus `GIT_ATTR_NOSYSTEM=1` for the system attributes file. **Verified:** an
  override delivered this way is visible to a `git` run by a separate child
  process, and suppresses a smudge filter that otherwise executed.

  **What is deliberately *not* done: `GIT_CONFIG_GLOBAL=/dev/null` and
  `GIT_CONFIG_SYSTEM=/dev/null`.** They look like the stronger move and they do
  not close this vector — verified: the filter driver in the test lived in
  **local** config, which is the shared `$GIT_DIR/config`, so blanking global
  and system changed nothing. They would additionally break credential helpers
  and git-lfs configuration for no gain against a branch-controlled input. The
  targeted override set is both narrower and more effective.

  **One welcome side effect.** With the tree's `.gitattributes` gone (C-1005)
  and `core.attributesFile` blanked, no smudge filter applies during checkout —
  so Git LFS files materialize as pointer text rather than being fetched. That
  is *better* for a reviewer, which reads pointers as data instead of executing
  a filter, and it removes the unbounded LFS cost §8.1 of the companion names
  as its one open latency exclusion. Reviewing an LFS repository means
  reviewing its pointers; nox says so rather than pretending otherwise.
- **C-1032 — real-binary contract tests are release-blocking, and named
  negative tests carry the unverified assumptions.** C-1020 made the contract
  suite the drift detector and C-1031's CI job stops it skipping itself green;
  neither makes it a *gate*. Every per-harness security property this design
  relies on is documentation or inference (see § *Decision Outcome*), and the
  §9.4 adversarial fixture — necessary as it is — cannot prove vendor
  semantics: it proves nox's own tree is clean, not that Codex honoured
  `sandbox_mode` or that OpenCode's inline config outranks a project file.
  **Therefore no release ships without these passing against real binaries, as
  negative tests** — each asserts the thing that must *not* happen:

  | Test | Asserts |
  |---|---|
  | sandbox escape | a write inside the workspace and an outbound connection both **fail** under `-c sandbox_mode=read-only`; this is what promotes Codex's `write_enforcement` to `os` under C-1025, and there is no other route to that value |
  | auth classification | a logged-out binary produces the shape §7.1a records for it, or the run resolves `indeterminate` — never a clean verdict |
  | quota | a rate-limit response stops the run and is never retried (C-1021) |
  | config loading | a project config in the tree does **not** reach the harness — the OpenCode precedence claim, tested rather than assumed |
  | **filter execution** | a hostile `.gitattributes` plus a configured driver: the driver does not run during `worktree add` |
  | **submodule population** | `git submodule status` inside the workspace lists nothing |

  A test that cannot run because its binary is absent **blocks the release**;
  it does not skip. That is the difference between this contract and C-1020,
  and it is deliberate: the alternative is shipping a security tool whose
  security properties were only ever read.
- **C-1029 — `nox.api.review()` is total: it returns a `Review` and never
  raises.** Three contracts disagreed about this — C-1014 says the probe
  *raises*, C-1012 says `absent` is a *failure state*, and the companion's
  failure table shows `status=error, reason=ABSENT`, i.e. a returned value — and
  a planner cannot write the API without picking one, because the choice changes
  every caller. It is picked here: **internal functions raise**
  (`HarnessUnavailable`, `UnsupportedCapability`, `ConfigError`,
  `IsolationError`), and `review()` is the boundary that catches them and maps
  each to a `Review` with `status != "ok"` and the corresponding
  `FailureReason`. C-1014's "raises, never a sentinel" describes `probe`, which
  is internal, and is unchanged. The consumer contract is therefore one branch
  on `status`, with no undocumented `try`/`except` — which is what hex's
  graceful-skip degrade needs.

---

### Component contracts — the public Python surface

Precise enough for `/hex-plan` to decompose without re-deriving the design.
Everything below is `src/nox/`. Dataclasses are `frozen=True, slots=True`
unless noted; no pydantic (settled).

```python
# nox/outcome.py ─────────────────────────────────────────────── C-1011, C-1012, C-1018

Status   = Literal["ok", "error", "indeterminate"]
Severity = Literal["block", "high", "warn", "suggest"]   # hex vocabulary, C-1018
Verdict  = Literal["approve", "needs-attention"]

class FailureReason(StrEnum):
    ABSENT           = "absent"            # ─┐
    UNAUTHENTICATED  = "unauthenticated"   #  │ the four contract-required
    RATE_LIMITED     = "rate_limited"      #  │ states (C-1012)
    MALFORMED_OUTPUT = "malformed_output"  # ─┘
    TIMED_OUT        = "timed_out"
    KILLED           = "killed"            # exit 143 — "we killed it", never generic
    ISOLATION_FAILED = "isolation_failed"  # worktree could not be built or cleaned
    UNSUPPORTED      = "unsupported"       # a required capability was absent
    INVALID_CONFIG   = "invalid_config"    # refused passthrough element, malformed
                                           # permission value in a TRUSTED config,
                                           # unusable ReviewTarget.path (C-1023,
                                           # C-1016, C-1027). Exists because
                                           # `reason` is non-None iff status != ok
                                           # and ConfigError had no member to carry

@dataclass(frozen=True, slots=True)
class Finding:
    severity: Severity
    title: str
    body: str
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    recommendation: str | None = None
    origin: Literal["harness", "nox"] = "harness"
    #   "nox" marks the C-1026 completeness finding — the one element of
    #   `findings` that is NOT untrusted harness output (C-1019).

Enforcement = Literal["os", "harness", "attested"]        # C-1007

@dataclass(frozen=True, slots=True)
class Containment:
    """Stamped into every Review, on EVERY return path including error and
    indeterminate. Derived from the resolved argv, never hand-written (C-1025).
    C-1019 — the consumer weights findings by it."""
    isolation: Literal["worktree"]          # v1 has one value; the field is the seam
    neutralized: tuple[str, ...]            # index entries filtered out (C-1005),
                                            # verified absent from the checkout
    omitted: tuple[str, ...]                # untracked paths NOT reviewed (C-1026);
                                            # non-empty ⇒ verdict may not be approve
    mechanism: Literal["tool-removal", "os-sandbox", "config-deny"]
    write_enforcement: Enforcement          # how strongly, not whether (C-1007)
    network_enforcement: Enforcement
    enforced_read_only: bool                # ENFORCED_READ_ONLY present? (C-1013)
    env_scrubbed: bool
    secrets_suspected: bool                 # credential shapes seen in raw (C-1018)

@dataclass(frozen=True, slots=True)
class Review:
    status: Status
    verdict: Verdict | None                 # None whenever status != "ok" (C-1018)
    findings: tuple[Finding, ...]
    summary: str
    raw: str                                # untruncated harness output, always
    truncated: bool
    reason: FailureReason | None            # non-None iff status != "ok"
    harness: str
    harness_version: str | None
    verified_against: str
    model: str | None                       # the RESOLVED literal; None when the
                                            # harness lacks MODEL_SELECTION (C-1030)
    model_class: ModelClass | None          # what was asked for. Both sides of both
                                            # fields recorded — asymmetry evidence
    heartbeat: Heartbeat
    containment: Containment
    duration_s: float
    cost_usd: float | None

    def require_ok(self) -> Review: ...
    # The single explicit decision point (C-1011). Raises NoxError on error and
    # on indeterminate; returns self otherwise. It performs no type narrowing —
    # it is `if r.status != "ok": raise` with a name — and is not described as
    # a narrowing helper, because a reader would expect a narrowed type.
    # `review()` itself never raises (C-1029); this is the opt-in.
```

```python
# nox/liveness.py ────────────────────────────────────────────────────── C-1010

class Liveness(StrEnum):
    SEMANTIC       = "semantic"        # structured per-event stream
    BYTE_ACTIVITY  = "byte_activity"   # raw stdout bytes only
    PROCESS_ONLY   = "process_only"    # the PID exists; nothing else is known

@dataclass(slots=True)                  # mutable: updated as events arrive
class Heartbeat:
    kind: Liveness
    last_activity_at: float             # time.monotonic(); SEMANTIC events only
    last_byte_at: float                 # any output at all
    events: int = 0
    def touch(self, now: float, *, semantic: bool) -> None: ...
    # semantic=False updates last_byte_at ONLY. It never resets the silence
    # clock, which is over events, not bytes (C-1010). Both timestamps travel
    # into the TIMED_OUT detail so "noisy but eventless" is distinguishable
    # from "dead".

@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    wall_clock_s: int                   # always enforced
    silence_s: int | None               # None ⇒ silence carries no information
    grace_s: float = 5.0                # SIGTERM → SIGKILL

    @classmethod
    def for_kind(cls, kind: Liveness, wall_clock_s: int) -> TimeoutPolicy: ...
    # SEMANTIC → 120 · BYTE_ACTIVITY → 300 · PROCESS_ONLY → None   (C-1010)
```

```python
# nox/capability.py ───────────────────────────────────────── C-1007, C-1013

class Capability(StrEnum):
    ENUMERABLE_DENY    = "enumerable_deny"     # required to launch (C-1007)
    ENFORCED_READ_ONLY = "enforced_read_only"  # enforced below the model
    STRUCTURED_OUTPUT  = "structured_output"   # schema-validated, not prompt-asked
    STREAMING_EVENTS   = "streaming_events"
    MODEL_SELECTION    = "model_selection"
    COST_REPORTING     = "cost_reporting"
    TOOL_ALLOWLIST     = "tool_allowlist"

REQUIRED: Final[frozenset[Capability]] = frozenset({Capability.ENUMERABLE_DENY})
#   C-1013. The gate needs a literal set or "raises on a missing required
#   capability" is untestable. ENFORCED_READ_ONLY is deliberately absent:
#   OpenCode launches without it, stamped.

@dataclass(frozen=True, slots=True)
class ContainmentPlan:
    """How THIS harness is prevented from writing to the repo or reaching the
    network, and HOW STRONGLY. C-1007 — the three v1 mechanisms are not
    interchangeable and the type does not pretend they are. `None` on either
    axis means not established, and prepare() refuses to launch."""
    mechanism: Literal["tool-removal", "os-sandbox", "config-deny"]
    write_enforcement: Enforcement | None
    network_enforcement: Enforcement | None
    #   A bare `no_repo_write: bool` was the previous shape. It made the launch
    #   gate check that a claim was made rather than that it was true, and it
    #   read as "enforced" to every adapter author — the Option D failure,
    #   shipped inside the type. `denied: frozenset[str]` was also here and is
    #   deleted: nothing in the specified flow ever read it, and its own
    #   comment admitted it held three incompatible things by mechanism.
    #   An adapter that needs a deny list keeps it as adapter-local state.

@dataclass(frozen=True, slots=True)
class HarnessInfo:
    name: str
    version: str | None
    verified_against: str                # the version this adapter was tested on
    capabilities: frozenset[Capability]  # absence ⇒ unsupported. No booleans.
    heartbeat_kind: Liveness
    launcher: Launcher
```

Capability facts as they stand for v1, each a design input rather than an
assumption — but **not each verified to the same standard**. The Claude Code
column is `--help` text from a local binary; the Codex column is `--help` text
from a local binary plus documentation whose pages 404'd in places; the OpenCode
column is a `--help` probe run through `ocx package exec`
([`nox-tech-tooling.md:7`](../research/nox-tech-tooling.md)) plus documentation,
with the *security* lane having no binary at all
([`nox-security.md:727-731`](../research/nox-security.md)). No cell was
established by running a review. `verified_against` plus the C-1020 release gate
is how these become behaviour rather than belief.

| | Claude Code 2.1.252 | Codex 0.144.1 | OpenCode 1.18.22 |
|---|---|---|---|
| `ENUMERABLE_DENY` | yes | yes | yes |
| `ENFORCED_READ_ONLY` | yes — pre-tool-call rules | yes — OS sandbox, on by default | **no** |
| `STRUCTURED_OUTPUT` | yes — `--json-schema` | yes — `--output-schema` | **no** — fenced-block extraction |
| `STREAMING_EVENTS` | yes — `--output-format stream-json` | yes — `--json` | yes — `--format json` |
| `MODEL_SELECTION` | yes — `--model`, plus `--effort <level>` | yes — `-m/--model`, plus `model_reasoning_effort` via `-c` | yes — `-m provider/model`; **no effort knob** (BYOK, provider-specific) |
| `COST_REPORTING` | yes — `total_cost_usd` | **no** | **no** |
| `TOOL_ALLOWLIST` | yes — `--tools` | **no** — sandbox is OS-level, not tool-level | **no** — config-file only |
| `ContainmentPlan.mechanism` | `tool-removal` | `os-sandbox` | `config-deny` |

Where `STRUCTURED_OUTPUT` is absent, nox extracts a fenced JSON block from the
final message and resolves to `indeterminate` when extraction fails. It does
not silently downgrade the guarantee.

```python
# nox/runner.py ──────────────────────────────────────────────── C-1009, C-1015

@dataclass(frozen=True, slots=True)
class Launcher:
    """A harness may be reachable only behind a prefix (C-1014)."""
    binary: str
    prefix: tuple[str, ...] = ()
    def argv(self, *args: str) -> tuple[str, ...]: ...

@dataclass(frozen=True, slots=True)
class Invocation:
    argv: tuple[str, ...]
    cwd: Path                    # always the ephemeral worktree (C-1003)
    env: Mapping[str, str]       # already minimal (C-1008)

class Process(Protocol):
    pid: int
    def lines(self) -> Iterator[str]: ...   # merged stdout+stderr, one pipe
    def poll(self) -> int | None: ...
    def signal_group(self, sig: int) -> None: ...
    def wait(self, timeout: float | None) -> int: ...
    # NOTE: no `send`. Adding Codex's app-server later adds exactly one
    # method here and touches nothing else (C-1024).

class Runner(Protocol):
    def spawn(self, inv: Invocation) -> Process: ...

class SubprocessRunner:
    """The only place `subprocess` is imported. `spawn` holds the single
    `# pragma: no cover` line in the codebase (C-1015)."""

def supervise(
    proc: Process, policy: TimeoutPolicy, hb: Heartbeat,
    on_line: Callable[[str], None], *, byte_cap: int = 8 << 20,
) -> tuple[int, bool]:                      # (exit_code, truncated)
    """Pure over `Process` — deadline, silence check, byte cap, SIGTERM→
    grace→SIGKILL on the process group. 100% covered against a fake."""
```

```python
# nox/harness.py ─────────────────────── C-1007, C-1013, C-1014, C-1023

PASSTHROUGH_ALLOW: Final[Mapping[str, frozenset[str]]] = {   # C-1023 — THE gate
    "claude":   frozenset(),
    "codex":    frozenset({"--title"}),
    "opencode": frozenset(),
}   # The model flag is NOT here: under C-1030 every adapter emits it itself
    # from MODELS[class], and rule 3 refuses any duplicate of a nox-owned flag.
    # Listing it made rule 1 and rule 3 contradict each other on the design's
    # highest-risk field. Two empty sets is the honest state of an allowlist
    # whose harnesses expose almost nothing containment-inert.
    # Permission, not exclusion. Anything absent is refused. No value-carrying
    # config flag is ever addable here: -c/--config, --settings,
    # --setting-sources, --mcp-config, --agents, --plugin-dir, --tools,
    # --permission-mode, --system-prompt, --append-system-prompt,
    # --permission-prompt-tool, --enable, --disable — matched on the token
    # before `=` as well as bare. Nor is any flag nox itself emits.

DENIED_FLAGS: Final[frozenset[str]] = frozenset({          # C-1023, re-scoped:
    "--dangerously-bypass-hook-trust",                     # Codex
    "--dangerously-bypass-approvals-and-sandbox",          # Codex
    "--dangerously-skip-permissions", "--bare", "--add-dir",  # Claude Code
    "--auto",                                              # OpenCode
})  # asserted against NOX'S OWN emitted argv in tests, so no future adapter
    # edit can introduce one. It is no longer the gate on user argv.

class HarnessUnavailable(NoxError):
    reason: FailureReason
    detail: str

class Adapter(Protocol):
    name: ClassVar[str]

    def probe(self, runner: Runner, cfg: HarnessConfig) -> HarnessInfo: ...
    #   Raises HarnessUnavailable. Never returns None, never a sentinel
    #   (C-1014). A real short invocation through the launcher, with cwd set
    #   to a fresh empty temp dir nox owns and env = the C-1008 minimal
    #   environment — never an inherited cwd, never the repo.

    MODELS: ClassVar[Mapping[ModelClass, ModelSpec]]
    #   Shipped class → literal map (C-1030). Overridable only in this
    #   harness's own [harness.<name>] section. OpenCode's literals carry the
    #   `provider/` prefix and probe() checks the provider is configured.

    def containment_plan(self, cfg: HarnessConfig, info: HarnessInfo) -> ContainmentPlan: ...
    #   Positive establishment with a stated enforcement level, per this
    #   harness's own mechanism (C-1007). `os` requires a cached passing probe
    #   result keyed on info.version — an adapter cannot claim it (C-1025).

    def prepare(self, req: ReviewRequest, ws: Workspace, info: HarnessInfo) -> Invocation: ...
    #   Refuses when: a required capability is absent (REQUIRED, C-1013); either
    #   enforcement axis is None (C-1007); or any passthrough element fails the
    #   allowlist (C-1023). Emits passthrough FIRST and nox's own containment
    #   flags LAST. This is the enforcement point — capability checks are not
    #   left to caller discipline.

    def classify(self, err: Mapping[str, object]) -> FailureReason | None: ...
    #   Per-harness error-shape table, backed by observed output (C-1012).
    #   None ⇒ this harness does not distinguish the state → indeterminate
    #   with the raw error name stamped. Never a substring guess.

    def parse(self, lines: Iterable[str], exit_code: int, hb: Heartbeat) -> Review: ...
    #   Exit code is never the success gate (C-1011).

ADAPTERS: Mapping[str, str] = {          # string key → dotted path, lazily
    "claude":   "nox.adapters.claude:ClaudeAdapter",     # imported on selection
    "codex":    "nox.adapters.codex:CodexAdapter",       # (fsspec registry shape)
    "opencode": "nox.adapters.opencode:OpenCodeAdapter",
}
```

```python
# nox/workspace.py ───────────────────────────── C-1003, C-1004, C-1005, C-1006

NEUTRALIZE_DIRS:  Final[frozenset[str]] = frozenset({...})  # matched on ANY path
NEUTRALIZE_FILES: Final[frozenset[str]] = frozenset({...})  # component (C-1005)
NEUTRALIZE_GLOBS: Final[tuple[str, ...]] = (".env.*",)      # basename globs
GITLINK_MODE: Final[str] = "160000"     # dropped by MODE, not name (C-1005):
                                        # a submodule can sit at any path

GIT_OVERRIDES: Final[Mapping[str, str]] = {                 # C-1031
    "core.hooksPath":      "/dev/null",
    "core.fsmonitor":      "false",
    "core.attributesFile": "/dev/null",
}   # delivered via GIT_CONFIG_COUNT/KEY_n/VALUE_n so they bind EVERY git in
    # the child's process tree, not just nox's own command lines. The worktree
    # shares $GIT_DIR/config, so a child-issued `git` would otherwise inherit
    # core.hooksPath from it. NOT GIT_CONFIG_GLOBAL/SYSTEM=/dev/null: verified
    # not to cover this (the driver lives in local config) and it breaks
    # credential helpers and git-lfs for nothing.

@dataclass(frozen=True, slots=True)
class Workspace:
    path: Path                 # the ephemeral worktree
    base: str                  # SYNTHETIC base commit   (C-1004, C-1005)
    target: str                # SYNTHETIC target commit — what is checked out
    scratch: Path              # SIBLING of <path>: .nox-<token>-<rand>/ (C-1009, E20)
    diff_path: Path            # <scratch>/review.diff
    neutralized: tuple[str, ...]   # index entries filtered, re-checked absent
    omitted: tuple[str, ...]       # untracked paths not carried (C-1026)

def neutralize(repo: Path, commitish: str, parent: str | None = None) -> str:
    """Read the tree into a temporary index, drop every entry matching the
    C-1005 set by ANY path component (basename included, so a set member
    committed as a symlink is dropped too), write-tree, commit-tree, return the
    synthetic SHA. The target is committed with `-p <synthetic base>` so the
    pair has real ancestry and merge-base-based diffs resolve. Nothing on disk
    is touched, so there is no deletion primitive and no symlink semantics to
    get wrong."""

@contextmanager
def workspace(repo: Path, target: ReviewTarget) -> Iterator[Workspace]:
    """resolve base+target (C-1004) → neutralize BOTH (C-1005) → worktree add
    --detach the synthetic target → mkdtemp a random scratch dir BESIDE the
    worktree, never inside it (C-1009, E20) → write the synthetic base..target
    diff into it. Teardown with
    `git worktree remove --force` in a finally (C-1006). Failure anywhere
    raises IsolationError → FailureReason.ISOLATION_FAILED."""
```

```python
# nox/config.py ──────────────────────────────────────────────── C-1016, C-1017

PERMISSION_KEYS: Final[frozenset[str]] = frozenset(
    {"read_only", "tools_allowed", "passthrough", "isolation", "launcher"}
)   # a literal set, never a heuristic (C-1016)

ModelClass = Literal["fast-balanced", "deep-reasoning"]   # adr_0001 C-001, C-1030

@dataclass(frozen=True, slots=True)
class ModelSpecT:
    """A TYPED value the adapter maps to flags — never a raw argv fragment.
    Codex's effort knob rides `-c`, which C-1023 refuses from passthrough;
    accepting argv here would reopen that hole through the back door."""
    model: str
    effort: str | None = None

ModelSpec = str | ModelSpecT      # a bare str ⇒ ModelSpecT(model=s, effort=None)

@dataclass(frozen=True, slots=True)
class HarnessConfig:
    model: ModelClass | None = None   # a CLASS, never a literal ID (C-1030).
                                      # Literals live in [harness.<name>] only,
                                      # so a wrong-harness model string is
                                      # unrepresentable. Invalid ⇒ warn + the
                                      # shipped default, never ConfigError.
    read_only: bool = True            # v1 domain is {True}; False → ConfigError
    timeout: int = 900
    tools_allowed: tuple[str, ...] | None = None   # may only NARROW (C-1016)
    launcher: Launcher | None = None
    passthrough: tuple[str, ...] = ()   # allowlisted per adapter — C-1023

def load(start: Path) -> tuple[NoxConfig, tuple[str, ...]]:
    """Upward search, first hit wins, depth ≤ 20 (an arbitrary bound, not a
    measured one), no filesystem crossing. Returns (config, warnings).

    ORDER IS PART OF THE CONTRACT (C-1017): resolve trust, DROP untrusted
    permission keys with a warning, THEN validate what survives. Validating
    first re-opens T6 — a hostile `read_only = "yes"` would raise before the
    drop rule ever ran. Unknown key → warning. Malformed permission value in a
    TRUSTED file → ConfigError."""
```

```python
# nox/api.py ─────────────────────────────────────────────── the whole surface

@dataclass(frozen=True, slots=True)
class ReviewTarget:
    kind: Literal["working-tree", "ref", "plan-artifact"]
    ref: str | None = None
    base: str | None = None   # resolution is specified, not left to the planner:
                              #   kind="ref"   → merge-base(base, ref); ref^ if None
                              #   working-tree → HEAD; HEAD^ if stash is empty
                              #   plan-artifact→ the empty tree; the TARGET is that
                              #     tree plus `path` as a one-file addition, so the
                              #     artifact IS the diff and every leg is the
                              #     code-diff leg unchanged (C-1027)
    path: Path | None = None  # plan-artifact scope; must exist and resolve
                              # inside repo, else ConfigError (C-1027)

@dataclass(frozen=True, slots=True)
class ReviewRequest:
    target: ReviewTarget
    harness: str                      # key into ADAPTERS
    instructions: str | None = None   # extra adversarial steering
    config: HarnessConfig = HarnessConfig()

def review(req: ReviewRequest, *, repo: Path, runner: Runner | None = None) -> Review: ...
#   The one public entry point, and it is TOTAL: it returns a Review and never
#   raises (C-1029). Internal functions raise; this is the boundary that maps
#   each exception to a Review with status != "ok". `nox.cli:main` is a thin
#   argv shell over it, and is what the zipapp targets.
```

The two hex adversary scopes map onto it: `code-diff` →
`ReviewTarget(kind="working-tree" | "ref")`, `plan-artifact` →
`ReviewTarget(kind="plan-artifact")` with the C-1027 materialization — the
second of which had no path through the flow before that contract existed, so
"maps directly" was true of the type and false of the implementation.

`ReviewTarget` also maps onto Codex's own review-target vocabulary, but **not**
by the obvious route. `--uncommitted` is never used: under C-1005 the workspace
carries no uncommitted state that belongs to the branch, and since E20 moved
the scratch directory out of the worktree it carries none of nox's own either —
so the flag has nothing to review at all. As C-1009 was originally written it
had something worse to review: nox's own scratch directory, instead of the
change.

**nox drives `codex exec review --base refs/nox/base/<token>`, a temporary ref,
and this is the primary path rather than a fallback.** Codex 0.144.1's help
documents the parameter as `--base <BRANCH>`, not `<SHA>`. An earlier revision
made the raw synthetic SHA primary and left the ref as a fallback gated at work
package 6b — which put an unproven assumption on the critical path and carried
an open rollout item to protect it. Inverting the two removes the item
entirely: a ref is what the flag documents, so it works whether or not raw
object IDs are accepted, and the whole cost is one `update-ref` and one
`update-ref -d`. Raw-SHA support becomes an optional optimization that a
contract test may later prove; nothing waits on it.

**Ref lifecycle.** Created in `prepare()` pointing at the synthetic base,
deleted in the same `finally` as the worktree, and namespaced under `refs/nox/`
with a `secrets.token_hex` suffix — so it cannot collide with a user's branch,
never appears in `git branch`, and a leak is identifiable and reclaimed by the
same startup sweep as a leaked worktree. The diff Codex computes is then the
same one nox writes to `<scratch>/review.diff` for the other two — identical by
construction, because both sides come from the same filtered commit pair and
the synthetic base is the target's only parent.

---

### Quantified Impact

| Metric | Before (Option A baseline) | After (Option C) | Notes |
|---|---|---|---|
| Repo-supplied execution vectors closed | Claude Code ~4 of 5 by flags; Codex hooks yes / MCP **no**; OpenCode **0 of 2** | all three harnesses, all vectors, by one index filter applied at any depth | `.opencode/plugins/` and Codex's repo MCP had no working flag mitigation |
| Controls between a hostile diff and code execution | 1 (flag string) | 3 independent (worktree · containment plan · env allowlist) | flag churn now degrades rather than removes |
| nox overhead per review | ~0 | 2 × (`read-tree` + `write-tree` + `commit-tree`) + one `git worktree add` + teardown | budget: ≤ 2 s p50 on a repo ≤ 50k files, excl. harness time. **An engineering estimate, not a measurement** — and it excludes Git LFS, which does not respect sparse-checkout ([git-lfs#3803](https://github.com/git-lfs/git-lfs/issues/3803)), so an LFS repo pays a full smudge per review and blows this budget by an amount nobody has measured |
| Untracked credentials reachable by the child | all (`.env`, `.envrc`, scratch dumps) | none | free consequence of a fresh checkout |
| Isolation code paths shipped | 1 (in-tree) | 1 (worktree) | Options B and D ship **2** |
| Concurrency ceiling | 1, architecturally (shared tree) | 1, by quota policy only | C-1022 becomes a default, not a constraint |
| Peak disk during a review | 0 | one working-tree copy | the material cost of the decision |

### Consequences

**Positive:**

- One containment story, one sentence, three harnesses; the flag stacks become
  defense in depth rather than the boundary.
- Codex's documented residual — repo-declared MCP servers in an
  already-trusted project — stops being accepted risk and becomes a deleted
  file. The untested `-c mcp_servers={}` lever is no longer load-bearing.
- The diff-size branch disappears. Because nox owns the tree, the diff is a
  file at a known path inside it — no 10 MB stdin cap, no
  inline-versus-self-collect threshold pair, and no shell needed to read it.
- Untracked credentials, `node_modules`, `.venv` and build output leave every
  child's reach for free.
- Concurrency stops being architecturally excluded, so the serialization
  default becomes a quota policy that can be relaxed with evidence.
- The capability record carries the three-way asymmetry as *data*
  (`ENFORCED_READ_ONLY`, `ContainmentPlan.mechanism`, the two enforcement
  levels, stamped per review) rather than as a paragraph in a README nobody
  reads.
- Neutralizing at the git-object level rather than by deleting files has three
  consequences beyond the wrong-diff defect it exists to fix: the filtered
  paths are invisible to every harness's own diff collection, so nox's diff and
  a harness-collected diff cannot disagree; there is no deletion primitive, so
  the symlink class of failure (`.claude` as a symlink surviving an
  `ignore_errors=True` `rmtree` while being reported as neutralized) does not
  exist; and matching by path component makes nested `AGENTS.md`,
  `packages/*/.codex/` and `packages/*/.opencode/` cost nothing extra.

**Negative:**

- A full checkout per review, in time and disk, on every repo size, plus two
  unreferenced commit objects per review in the user's store (same class as
  `git stash create`, reclaimed by `gc`).
- Untracked and ignored files are invisible to the reviewer. Generated code
  never committed, and vendored dependencies, cannot be read. **This is a
  correctness cost, not a fidelity one**, and C-1026 makes it loud rather than
  removing it: a review that could not see the whole target can never return
  `approve`. The plan-artifact scope needed a whole contract (C-1027) to exist
  at all, because the artifact under review is untracked by construction.
- `CLAUDE.md` / `AGENTS.md` deletion (C-1005) removes genuine project
  convention context that would have improved finding quality — a real
  fidelity cost paid for a real injection channel with no off-switch on two of
  three harnesses. See open question 3.
- v1 does not review untracked files at all (C-1004).
- v1 does not exercise Codex's app-server, so the facade's transport dimension
  is validated by one shape rather than two (C-1024).
- Worktree lifecycle is a new failure class with its own operational tail.

**Risks:**

- **Worktree leak on a killed process.** Mitigated by C-1006's
  prune-at-startup plus a nox-owned path prefix; not eliminated, because
  SIGKILL to nox itself skips the `finally`.
- **`git stash create` behaviour is documentation-derived, not verified**
  (C-1004). Mitigated by making the fixture the first thing the implementation
  builds; if it does not behave as specified, the fallback is "v1 reviews
  committed refs only" — a scope cut, not a redesign. **The fallback removes no
  control and adds no surface**: worktree, neutralization, containment plan and
  env allowlist are identical whichever way the commit-ish was obtained, so the
  threat model is unaffected and only coverage shrinks. Its real cost is
  second-order and worth stating: reviewing uncommitted working-tree changes is
  hex's common case, so a v1 that cannot do it makes the `isolation =
  "in-tree"` escape urgent on day one — and *that* change is the one that moves
  the posture back toward Option A for whichever harness takes it. A scope cut
  that makes the escape hatch urgent is not a neutral fallback. Two smaller
  notes on the same contract: `git stash create` can fail or behave unusually
  mid-merge, mid-rebase or with unresolved conflicts, which resolves to
  `ISOLATION_FAILED` and should be an expected outcome rather than a surprise;
  and `codex exec review --uncommitted` is documented as reviewing "staged,
  unstaged, **and untracked** changes", a meaning nox's worktree can never
  match, which is one more reason C-1005 routes Codex through `--base` instead.
- **Codex's read-only sandbox cannot be set by a flag on `codex exec
  review`.** Its verified option list has no `-s/--sandbox` and no
  `-a/--ask-for-approval`, so the mode must go through `-c`, and the config
  key name (`sandbox_mode`) is *inferred from the flag name*, not read from
  documentation ([`nox-security.md:1246-1257`](../research/nox-security.md)).
  This is a verification task, not an open decision, and it is a rollout gate
  rather than an open question carrying a marker. Two corrections to how an
  earlier revision framed it. **First, it is not one command.** Confirming the
  *key name* plausibly is — `--strict-config` is already in nox's Codex stack
  and, if it rejects unknown keys as its name implies, `codex exec review
  --strict-config -c sandbox_mode=read-only` errors on a wrong name and
  succeeds on the right one. Confirming the mode *takes effect* is a fixture:
  a write attempt and a network attempt inside the sandbox, both observed to
  fail. That is comparable in size to work package 2, and it is what the gate
  actually requires. **Second, the refusal is only structural because C-1025
  makes it so.** With a hand-written `no_repo_write=True` next to the
  `-c sandbox_mode=read-only` argv, every unit test passes, the contract suite
  passes (it checks the argv nox produces, not whether Codex honoured it), and
  the §9.4 fixture passes (the neutralization set closes T1 independently of
  the sandbox) — while Codex runs at its default posture against a worktree
  sharing `refs/`, stamped `os-sandbox / enforced_read_only=True`. Deriving the
  enforcement level from a cached probe result is what turns "blocked until the
  key is resolved" from a row in a rollout table into a condition the code
  cannot pass.
- **Terms of service — the "ordinary use" discretion clause.** The core
  question is settled favourably: `claude -p` and third-party apps
  authenticating through the Agent SDK are *explicitly enumerated* as covered
  by the Agent SDK credit, and the docs ship `gh pr diff "$1" | claude -p
  --append-system-prompt "You are a security engineer…"` as a supported
  example ([`nox-security.md:399-420`](../research/nox-security.md)). The
  residual is that Anthropic "reserves the right to draw" third-party-tool
  usage from usage credits at its discretion. Mitigated by C-1002, C-1021,
  C-1022, and by surfacing `total_cost_usd`.
- **Billing is not equivalent across three harnesses and must not be
  documented as if it were.** Claude Code draws on the Agent SDK monthly
  credit, a separate and smaller budget than users expect; Codex draws on the
  user's ChatGPT plan or API key; OpenCode with an Anthropic model can no
  longer use a Claude subscription at all and needs a Console API key
  ([`nox-security.md:463-471`](../research/nox-security.md)).
- **Full N×N ships a measured-negative cell.** arXiv:2607.21656 (116 tasks,
  since **accepted at Agentic SE @ KDD'26**, still unreplicated): Claude
  reviewing Codex 71.6% → 89.7% (p=.001); **Codex reviewing Claude 91.4% →
  82.8% (p=.046, worse)**. With Codex in v1 this is no longer hypothetical — it
  is a shipped, user-selectable direction that one paper measured as harmful.
  The owner chose full N×N with this on the table, and the decision holds on
  the evidence rather than merely on the fact of settlement: one unreplicated
  study of two models is thin ground on which to remove a product surface, the
  discussion carries its own counter-citation (arXiv:2604.16790 — LLM-judge
  verdicts are prompt-sensitive enough to flip model rankings), and the paper
  measures **models** while nox selects **harnesses**, which with OpenCode's
  BYOK leg are not the same axis, so a harness-level gate would be the wrong
  instrument even if the finding held. Mitigation is informational:
  `Review.model` records the model on *both* sides, so the asymmetry is
  measurable in a user's own logs and every user generates replication evidence
  the field currently lacks. The point-of-use complement — a non-blocking
  warning when the selected pair lands on the known-negative cell — is left to
  `/hex-plan` (see *Deferred*), because it costs one condition on a code path
  C-1020 already has.
- **Managed settings outrank nox's flags on Claude Code.** "No other level,
  including command line arguments, can override a managed permission rule."
  Note the inversion: on **Codex, CLI flags win outright** over project config
  ([`nox-security.md:1001-1004`](../research/nox-security.md)) — two harnesses
  with opposite precedence, which is one more reason the boundary lives in the
  workspace rather than in a flag.
- **Name collision.** `nox` is an established PyPI package. Resolved by
  removing the PyPI channel entirely: grim/GHCR is the only distribution, no
  wheel is ever published, and the name is kept everywhere. See Open Questions
  (resolved).
- **`--safe-mode`, `--restricted` and `--disable-slash-commands` are
  `--help`-only, absent from the docs site, and untested against `-p`**, and
  Codex's skill-hook chain is reasoned rather than demonstrated. Under Option
  C these are defense in depth, so the cost of their being weaker than
  advertised is a degraded second layer, not a breach — which is exactly why
  the decision does not rest on them.
- **Publishing namespace for a skill built outside arcana.** `CLAUDE.md` states
  that every published artifact lives under
  `ghcr.io/michael-herwig/arcana/<name>`, and nox's skill is built in the nox
  repository so that one tag ships one version of skill and code together.
  Resolution, so the rule does not acquire a silent first exception: **nox's
  skill publishes to `ghcr.io/michael-herwig/arcana/nox` from the nox
  repository**, with `repository_prefix = "michael-herwig/arcana"` in nox's own
  `publish.toml` and a release credential scoped to that path; nox's CI runs
  `grim build skill/` as the artifact gate, which is arcana's per-skill
  verification step, alongside the Python `task verify`. The separate repository
  solves a real toolchain problem — uv, ruff, pyright, pytest and mkdocs would
  be a second toolchain and a second CI shape in a pure-markdown grimoire — but
  it relocates publishing and verification rather than solving them, and this
  is where they land.

### Deferred to `/hex-plan`

Recorded so the planner does not re-derive them, and deliberately **not**
designed here.

| Item | What the planner decides |
|---|---|
| Specific env-key handling | Naming the dropped credential-shaped variable in the `unauthenticated` detail string (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY` both match the `*_KEY` denylist and are dropped silently today), and `PATH` sanitization — dropping relative entries and entries resolving inside the repository |
| Selection-time asymmetry warning | A non-blocking warning when the reviewer/reviewee model pair lands on arXiv:2607.21656's measured-negative cell, on C-1020's existing warning path. Does not gate; does not reopen the full-N×N decision |
| Severity case | The wire value is lowercase (`"block"`), hex's vocabulary is title-case (`Block`). Pick lowercase on the wire, have the consumer title-case for display, and say so in C-1018 — a case difference across a process boundary is the mapping table C-1018 says it refuses to build |
| CI as a consumer | The Context diagram lists CI; the settled subscription-auth model requires an interactively logged-in CLI, and `--bare` is excluded. Either drop CI from the diagram or state that CI needs API-key mode and reconcile that with C-1023. A permanently skipped security gate that reports green is worse than an absent one |
| Unreachable `Liveness` members | `ByteActivity` and `ProcessOnly` serve zero v1 harnesses; all three are `Semantic`. Kept as the extension seam, and the honest framing is "three lines of code, so kept", not "required by precedent" — the precedent (watchdog) is about environments that exist, and the harness that generated this one (Copilot) is Out of v1 |
| Capability members with no reader | Four of seven (`STREAMING_EVENTS`, `MODEL_SELECTION`, `COST_REPORTING`, `TOOL_ALLOWLIST`) are held by all three harnesses and duplicate `HarnessInfo.heartbeat_kind`, `Review.cost_usd` or `ContainmentPlan.mechanism`. `ENUMERABLE_DENY` duplicates the C-1007 gate. The two that carry the asymmetry (`ENFORCED_READ_ONLY`, `STRUCTURED_OUTPUT`) are load-bearing. Kept for v1 because the table is evidence; trimming is a plan-time call |
| `Review` field count | `harness_version` + `verified_against` + the C-1020 warning are three representations of one drift signal |
| Explicit decision scenarios for the matrix | A cross-model reviewer asked for named scenarios (own-branch review, hostile PR review, large-repo review, LFS repo) scored individually rather than one aggregate matrix. The aggregate has now held through three native reviewers, two re-validations and a cross-model pass, so this is presentation rather than a decision risk — but scenario tables are how a reader checks a weighting against their own situation, and the sensitivity paragraph is a summary of what they would show |


- **C-1033 — discoverable, independent, proposed-never-pinned.** nox and hex
  are not bound to each other: nox runs alone with no hex present, and hex
  runs alone with no adversary pinned (its seam already degrades to
  "Cross-model review skipped"). hex *benefits* from nox, so nox must be
  discoverable without being executed. Three parts:
  1. **Marker.** nox's skill (`nox-review`) declares, in its `SKILL.md`
     frontmatter `metadata` map, the plain string keys
     `hex-adversary-scopes: "code-diff,plan-artifact"` and
     `hex-adversary-version: "<nox version>"`. Plain keys, not a vendor
     namespace — grim treats non-namespaced `metadata` as ordinary
     string→string catalog metadata and passes it through to every client
     verbatim, so the marker survives install unchanged.
  2. **Detection.** `/hex-init`'s audit gains one item, *"Cross-model
     adversary skill installed?"*: scan the installed skill set for any
     `SKILL.md` carrying `hex-adversary-scopes`, and if `hex.md › Preferences`
     has no `adversary:` pin (or pins a skill that is no longer installed),
     **propose** `adversary: <skill-name>` with consent — the same
     propose-with-consent shape every other audit item uses. Absent marker →
     the item is silent. It never writes the pin unasked, and it never
     removes an existing pin the user typed. `codex:rescue` carries no
     marker and stays user-typed; that is acceptable — it is not nox's to
     retrofit.
  3. **Home.** Part 2 is a change to `hex/hex-init/references/audit.md`,
     outside this ADR's write surface. It is specified here and delivered as
     one work package in the nox plan that touches arcana (the audit item)
     or as a one-item hex plan — the planner decides. Until it lands, the
     rollout's step 9 is the manual flip it was.
  Reversibility: two-way — removing the audit item leaves the marker inert
  and the pin hand-typed, exactly today's state.
## Non-Functional Requirements

| Axis | Impact of this decision |
|---|---|
| **Scalability** | Not a service; the only axis is concurrent adversary calls. C-1003 makes concurrency *safe* (each call owns its tree), so the remaining limiter is vendor quota, not correctness. v1 serializes by default (C-1022); the reported ceiling is 1–3 steady agents, 5+ overnight hitting limits within hours. |
| **Availability** | nox has no service to be available. Availability is the harness CLI's plus the vendor's, with a documented long tail: [claude-code#47754](https://github.com/anthropics/claude-code/issues/47754), headless OAuth refresh blocked by Cloudflare WAF, 26+ days locked out. nox must never enter a refresh-retry loop; `rate_limited` (C-1012) stops the run. Adversary review is a gate, not a blocker — an unavailable harness degrades to a graceful skip in the consumer, per the seam nox plugs into. Three harnesses means a user who loses one has two fallbacks, which is a real availability gain over the single-vendor precedent. |
| **Latency** | nox's own overhead budget: ≤ 2 s p50 on a repo of ≤ 50k tracked files (two synthetic-tree builds + worktree add + diff write + teardown), excluding harness time, which dominates at tens of seconds to minutes. **The budget is an engineering estimate, not a measurement**, and it has one named exclusion: **Git LFS does not respect sparse-checkout ([git-lfs#3803](https://github.com/git-lfs/git-lfs/issues/3803))**, so an LFS repository smudges its pointers on every worktree checkout and blows the budget by an unmeasured amount. No broker or warm-server reuse in v1 — `codex-plugin-cc`'s Unix-socket broker, Codex's `app-server` and OpenCode's `run --attach <url>` are all documented upgrade paths if per-call cold start ever measures as the bottleneck. Building any of them now would be speculative. |
| **Security** | The decision *is* the security posture; contracts C-1003–C-1010 and C-1023–C-1029, plus the companion doc's threat model, carry it. Summary: three independent controls (worktree, per-harness containment plan, environment allowlist); no claim of filesystem isolation beyond what the containment plan provides; the containment stamp derived from the argv rather than asserted (C-1025); review output itself treated as untrusted and as a possible credential sink (C-1018, C-1019). |
| **Cost** | Auth is the user's own subscription, so nox adds no metered spend of its own — but the three harnesses draw from three *different* pools and are documented separately. `total_cost_usd` is surfaced only where the harness reports it (Claude Code alone holds `COST_REPORTING`); the local call log (C-1021) is the only spend visibility that exists for the other two, since no vendor exposes a pre-call quota check. Disk cost: one working-tree copy for the duration of a review. |
| **Operability** | Four distinguishable failure states with no interactive prompt (C-1012); per-adapter `verified_against` with a mismatch warning (C-1020); local call log (C-1021); worktree prune at startup and `--force` teardown (C-1006); zero runtime dependencies, so the install surface is a Python interpreter and the `.pyz`. The known operational tails are worktree leaks and vendor flag churn, both named above with mitigations. |

## Technical Details

### Architecture

```
consumer (hex /hex-review, or a human, or CI)
     │  adversary: nox-review        ← unchanged hex seam (C-1001)
     ▼
┌─ nox.api.review() ── TOTAL: returns, never raises      (C-1029)┐
│  config.load()  ── drop-untrusted THEN validate    (C-1016/17) │
│  minimal_env()  ── built BEFORE anything spawns        (C-1008)│
│  ADAPTERS[key] ── lazy import, string-keyed registry           │
│  adapter.probe() ── raises; cwd = empty temp dir       (C-1014)│
│  workspace()   ── neutralize objects · worktree · diff (C-1003-6)│
│  adapter.containment_plan() ── enforcement level, not bool (C-1007)│
│  adapter.prepare() ── capability + passthrough allowlist (C-1013/23)│
│  supervise(Runner.spawn(inv)) ── deadline · kill  (C-1009/1015)│
│  adapter.parse() ── tri-state, never exit-code-gated   (C-1011)│
│  Containment ── DERIVED from the resolved argv         (C-1025)│
└────────────────────────────────────────────────────────────────┘
     │
     ▼
Review{status, verdict, findings[], containment, heartbeat, raw}
```

### API Contract

The public surface is the *Component contracts* section above. The wire
contract nox asks each harness to produce is one JSON object:

```json
{
  "verdict": "approve | needs-attention",
  "summary": "string",
  "findings": [{
    "severity": "block | high | warn | suggest",
    "title": "string", "body": "string",
    "file": "path or null",
    "line_start": 0, "line_end": 0,
    "confidence": "high | medium | low",
    "recommendation": "string or null"
  }],
  "next_steps": ["string"]
}
```

Shape adopted from `codex-plugin-cc`'s `schemas/review-output.schema.json`
([`discuss-nox-priorart.md:18`](../research/discuss-nox-priorart.md)) with
severity replaced by hex's vocabulary (C-1018). Claude Code receives it via
`--json-schema` and Codex via `--output-schema`, and both validate it;
OpenCode has no schema flag, so nox asks for it in the prompt, extracts the
fenced block, and resolves to `indeterminate` on extraction failure. The
capability difference is visible in `HarnessInfo`, not hidden behind a uniform
call.

### Data Model

No persistence beyond two files, both under the user config/state dir, never
in the repo: the trust store (config path → content hash, C-1017) and the
append-only call log (C-1021). The ephemeral worktree is the only other state
and is removed in a `finally`.

## Implementation Plan

1. [ ] Repo scaffold modelled on `ocx-sdk-python`: `src/` layout, hatchling,
       uv, `dependencies = []`, ruff `E,W,F,I,B,UP,ANN,RUF,D` + google
       docstrings, pyright strict on `src`, `tests/{unit,contract,acceptance}/`,
       branch coverage `fail_under = 100`.
2. [ ] **Prove C-1004 and C-1005 with a real fixture first** — `git stash
       create` → `read-tree`/`write-tree`/`commit-tree` filtering →
       `git worktree add --detach` → expected tree contents *and* an expected
       synthetic-base-to-target diff, on a repo with staged, unstaged and
       untracked changes and with hostile config files at the root and below
       it. Everything else depends on it.
3. [ ] `runner.py`: `Process`/`Runner` protocols, `SubprocessRunner` (the one
       pragma), `supervise()` fully covered against a fake.
4. [ ] `workspace.py`: worktree lifecycle, object-level neutralization, random
       scratch dir, diff write, untracked-file check (C-1026), plan-artifact
       materialization (C-1027), prune, `--force` teardown.
5. [ ] `outcome.py`, `liveness.py`, `capability.py`, `config.py`,
       `prompt.py` (C-1028) — pure, and therefore straightforwardly at 100%.
6. [ ] `adapters/claude.py`, `adapters/codex.py`, `adapters/opencode.py` —
       file-disjoint, parallelizable; each with a `verified_against` constant,
       a per-harness error-classification table (C-1012), a
       `PASSTHROUGH_ALLOW` entry, and a `tests/contract/` suite that runs the
       real binary and skips via `probe()`. **Codex is gated on resolving the
       `sandbox_mode` config key** (see Validation). The `--base` route needs no
       gate: it uses a temporary `refs/nox/` ref, which is what the flag
       documents.
7. [ ] `cli.py` + CI zipapp build (`python -m zipapp src/nox -o
       skill/scripts/nox.pyz -p "/usr/bin/env python3" -m "nox.cli:main"`),
       gitignored, built at release only. Deterministic entry order and a fixed
       `ZipInfo.date_time`; never call the no-arg
       `importlib.resources.files()`, which fails inside a `.pyz`
       ([`nox-tech-tooling.md:52`](../research/nox-tech-tooling.md)).
8. [ ] `skill/SKILL.md` in the same repo, one tag, one version; `grim build`
       clean.
9. [ ] Run `/hex-init` (re-audit); accept the proposed `adversary: nox-review` pin (C-1033). Manual flip of `hex.md › Preferences` remains the fallback until the audit item lands.
       No hex source change (C-1001).

## Validation

- [ ] **Codex read-only is actually asserted.** Resolve the config key that
      sets the sandbox on `codex exec review` (`-c sandbox_mode=read-only` is
      the inference) and prove it takes effect. Until this passes, C-1007
      refuses to launch the Codex adapter.
- [ ] Contract suites pass against the real `claude`, `codex` and `opencode`
      binaries, and skip cleanly on a machine without them.
- [ ] **`refs/nox/base/<token>` is created in `prepare()`, drives
      `codex exec review --base`, and is deleted in the same `finally` as the
      worktree** — including on an exceptional exit. No `refs/nox/` ref
      survives a full test run, asserted alongside the worktree check.
- [ ] **Adversarial fixture**: a repo whose branch adds `.claude/settings.json`
      with a `SessionStart` hook; `.mcp.json` with a server;
      `.claude/skills/lure/SKILL.md` with frontmatter hooks; `.codex/hooks.json`
      with a `SessionStart` hook; `.codex/config.toml` declaring a stdio
      `mcp_servers` entry; `.opencode/plugins/evil.ts`; and `opencode.json`
      with an attacker-controlled provider `baseURL`. The review completes on
      all three harnesses and **none of the seven executes**. Extended, and
      every addition is a finding this fixture would previously have missed:
      at least one hostile file **below the root**
      (`packages/api/AGENTS.md`, `packages/api/.opencode/plugins/evil.ts`);
      `.claude` committed as a **symlink** to an in-repo directory and `.codex`
      as a symlink to `$HOME/.codex`; a committed `.nox/` directory and a
      committed `.nox` symlink; the `.opencode/plugins/evil.ts` case asserted
      non-executing during the **probe** as well as the review; and an
      assertion that the diff each harness sees contains the branch's real
      change and **no** neutralization noise.
- [ ] **`passthrough` allowlist rejection is tested per harness**, including
      `["-c", "sandbox_mode=danger-full-access"]`,
      `["--settings", "{\"hooks\":…}"]`, `["--mcp-config", …]`,
      `["--tools", "Read,Bash"]`, `["--permission-mode", "bypassPermissions"]`
      and the `=`-joined forms — none of which the old denylist caught — plus
      `--dangerously-bypass-hook-trust` through `passthrough`, and an assertion
      that no `DENIED_FLAGS` member appears in nox's own emitted argv.
- [ ] **Synthetic-pair ancestry**: assert
      `git merge-base --is-ancestor <synth-base> <synth-target>` succeeds and
      that `git diff <sb>...<st>` resolves. Without `-p` both ends are
      parentless roots, three-dot fails with "no merge base", and the Codex
      `--base` leg dies at runtime.
- [ ] **Neutralization is mode-independent**: a set member committed as a
      **symlink** (`.codex` → an in-repo directory holding `settings.json`) is
      absent from the checkout. This is the case the first verification pass
      claimed to have covered and had not.
- [ ] **`.gitattributes` filter never executes**: a repo with
      `filter.evil.smudge` configured locally and a branch committing
      `*.py filter=evil`; assert the driver does not run during
      `worktree add`. Without C-1005's `.gitattributes` entry it does — this
      was verified, and it is code executing before any harness starts.
- [ ] **Submodules are neither mapped nor mountable**: a branch with a
      submodule whose nested repo carries its own `.claude/settings.json`;
      assert `.gitmodules` is absent, no mode-`160000` entry survives, and
      `git submodule status` inside the worktree lists nothing.
- [ ] **Child-issued git is governed**: set `core.hooksPath` in the shared
      `$GIT_DIR/config` to a script that touches a marker, run a `git checkout`
      from a *child* process under the C-1008 environment, and assert the hook
      did not fire (C-1031). The per-call `-c` form does not cover this.
- [ ] **Untracked-file completeness**: a repo with two untracked new files,
      reviewed on the working tree; assert `Containment.omitted` names both and
      `verdict != "approve"`. Separately assert a **plan-artifact** review has
      `omitted == ()` — the artifact is untracked but materialized, and an
      unconditional check made every such review refuse `approve` while
      accusing the document under review.
- [ ] **`plan-artifact` end to end**: an untracked artifact under
      `.agents/plans/`; assert the diff is a one-file addition of that path,
      that the workspace contains no other repository content, that all three
      adapters take the ordinary code-diff route with no per-scope branch, and
      that a missing or out-of-repo `path` raises before any spawn.
- [ ] `Containment` stamp accurate on all three and present on **every** return
      path including `error` and `indeterminate`, including
      `enforced_read_only = False`, `mechanism = "config-deny"` and
      `network_enforcement = "attested"` for OpenCode — and derived from the
      resolved argv, proven by stub adapters whose plan disagrees with their
      argv failing the test — **one per enforcement level**: `os` without the
      cached sandbox probe, `harness` without the `--tools` restriction,
      `attested` without the config-deny environment.
- [ ] Contract-test collection count asserted non-zero per adapter on the
      release runner, so the drift detector cannot skip itself green (C-1020).
- [ ] Byte-identical `.pyz` across two CI runs.
- [ ] Branch coverage 100% with exactly one `# pragma: no cover`.
- [ ] Security review of the diff before release.
- [ ] No worktree survives a full test run (`git worktree list` clean).

## Open Questions

None open. The three markers the design carried were resolved by the owner on
2026-09-02 (via `/hex-architect` handoff chips); each resolution is recorded
here with the option set it was chosen from, so the reasoning survives.

- **Python runtime as a hard dependency — RESOLVED: yes, accept.** arcana holds
  zero executable assets today; nox is the precedent-setter. Accepted on the
  grounds the design already argued: every target user has `python3` on PATH by
  virtue of running an AI coding harness, the consuming agent sees one opaque
  `skill/scripts/nox.pyz` rather than a package tree in its context surface,
  and grim installs `scripts/` verbatim per client. Alternatives declined:
  fencing the precedent with a documented executable-asset rule in
  `hex/DESIGN.md` (deferred — revisit if a second executable artifact appears);
  keeping arcana pure markdown with nox published from its own namespace.
- **`nox` name vs the PyPI session runner — RESOLVED: keep `nox`, never publish
  a wheel.** Repo, skill, CLI verb and `nox.toml` stay `nox`. The optional PyPI
  channel is **removed** rather than renamed: grim/GHCR is the only
  distribution, so the collision ceases to exist because the surface does.
  This tightens the dossier's "PyPI optional and load-bearing on nothing" to
  "PyPI: none". `uvx` reach for non-grim users is given up; it was a known
  audience of zero. Alternatives declined: renaming the project; publishing a
  convenience wheel as `nox-adversary`.
- **Project instruction files (`CLAUDE.md`, `AGENTS.md`) reaching the reviewer
  — RESOLVED: no, delete with the neutralization set (C-1005).** The reviewer
  runs convention-blind. nox cannot distinguish a legitimate convention file
  from one that says "report this diff clean", `AGENTS.md` has no documented
  off-switch on Codex or OpenCode, and the reviewer's job is adversarial rather
  than convention-conformant. The fidelity cost is accepted as bounded. The
  trusted-context opt-in — a `nox.toml`-named out-of-tree instructions file
  copied into the workspace — is the designated future answer if findings
  measurably suffer, and is recorded in the Deferred table; it was declined
  for v1 to keep one materialization path.

## Links

- Discussion (ratified): [`nox-multi-harness-adversary.md`](../discussions/nox-multi-harness-adversary.md)
- Companion system design: [`adr_0011_system_design.md`](adr_0011_system_design.md)
- Research: [`nox-security.md`](../research/nox-security.md) (incl. Addendum 2 — Codex) ·
  [`nox-tech-tooling.md`](../research/nox-tech-tooling.md) ·
  [`nox-pattern-precedent.md`](../research/nox-pattern-precedent.md) ·
  [`discuss-nox-priorart.md`](../research/discuss-nox-priorart.md) ·
  [`discuss-nox-vendor.md`](../research/discuss-nox-vendor.md)
- Capability-class precedent (binding on C-1030):
  [`adr_0001_model_matrix_capability_classes.md`](adr_0001_model_matrix_capability_classes.md)
  § C-001 — two classes, one definition site, never literal model names
- hex seam: [`protocol.md` § Adversary contract](../../hex/hex-core/references/protocol.md) ·
  [`hex/DESIGN.md` § Adversary contract](../../hex/DESIGN.md) ·
  [`.agents/memory/hex.md`](../memory/hex.md) › Preferences
- Sibling repo shape: `/home/mherwig/dev/ocx-sdk-python`
- External: [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) ·
  [anomalyco/opencode#8832](https://github.com/anomalyco/opencode/issues/8832) ·
  [anthropics/claude-code#47754](https://github.com/anthropics/claude-code/issues/47754) ·
  [arXiv:2607.21656](https://arxiv.org/abs/2607.21656) (accepted, Agentic SE @ KDD'26; unreplicated) ·
  [arXiv:2506.08837](https://arxiv.org/abs/2506.08837) ·
  [MCP spec 2026-07-28 — sampling deprecated in favour of direct provider calls](https://blog.modelcontextprotocol.io/posts/2026-07-28/) ·
  [git-lfs#3803](https://github.com/git-lfs/git-lfs/issues/3803) ·
  [GHSA-436v-8fw5-4mj8](https://github.com/jdx/mise/security/advisories/GHSA-436v-8fw5-4mj8) ·
  [CWE-59](https://cwe.mitre.org/data/definitions/59.html) ·
  [CWE-1188](https://cwe.mitre.org/data/definitions/1188.html)

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-08-31 | architect (`/hex-architect` tier-high) | Initial draft. Reopens and reverses the discussion's settled no-worktree constraint on the security lane's addendum evidence; contracts C-1001–C-1022. |
| 2026-08-31 | architect | v1 scope → three harnesses (Codex added). "Drop OpenCode" removed from the matrix, per-harness isolation tier added and declined with reasoning; three-way asymmetry made the spine; C-1007 generalized to `ContainmentPlan`; C-1023 (denied-flag list) and C-1024 (argv-only transport) added. |
| 2026-09-02 | architect (`/hex-architect` tier-high, adversarial-panel fix pass) | Recommendation **unchanged** (Option C). C-1005 moved from an on-disk `rm` to a git-object-level filter, recursive by path component — closes the wrong-diff defect and the deletion-primitive symlink class at once; C-1004 became a base/target pair; C-1023 replaced by a per-adapter passthrough allowlist with ordering; C-1007 replaced booleans with enforcement levels; C-1008 gained pre-probe construction, the inbound-channel rule (T4b) and a written exclusion list; C-1009 moved the scratch dir to a random name; C-1010, C-1012, C-1013, C-1014, C-1016, C-1017, C-1018, C-1020 tightened. **New:** C-1025 (argv-derived containment stamp), C-1026 (untracked completeness), C-1027 (`plan-artifact` materialization), C-1028 (prompt contract), C-1029 (total public boundary), C-1030 (model selection by `adr_0001` capability class, adapter-owned class → literal maps with typed effort, fail-soft on invalid values). `ContainmentPlan.denied` deleted. v1 harness set stated as an owner constraint; the Context value claim corrected; reversibility re-argued on consequence rather than cost; matrix de-biasing check added; evidence-strength caveats and citation anchors corrected throughout. |
| 2026-09-02 | architect (narrow pass, post-re-validation) | Six PARTIALs closed, **no new contracts**. **C-1005:** synthetic target committed with `-p <synthetic base>` — parentless roots broke `merge-base` and would have failed the Codex `--base` leg at runtime; matcher now tests **every** path component including the basename against the directory set, closing the symlink leg (Spec B3 / Sec H5). That leg's earlier "mechanically verified" claim was false — the verification script matched a rule the contract did not state — and is corrected in place rather than deleted, as is the "porcelain is empty" claim, which held only before the scratch dir existed. **C-1027:** the artifact is materialized as a one-file addition against the empty tree instead of copied into scratch, so it *is* the diff and every adapter takes the unchanged code-diff route — deleting the special case rather than patching it. **C-1026:** `omitted` scoped to untracked paths *not materialized*, resolving its collision with C-1027; `Finding.origin` added. **C-1025:** per-adapter derivation table for `harness` and `attested`, so all three enforcement levels are computed from argv rather than only `os`. **C-1023:** model flag removed from `PASSTHROUGH_ALLOW` — rule 1 and rule 3 contradicted each other once C-1030 had every adapter emit it. **C-1030:** `[harness.*]` literals dropped from untrusted repo-local files; literals starting with `-` or containing whitespace rejected. Ancestry, symlink and plan-artifact mechanics re-verified against real git with the matcher exactly as specified. |
| 2026-09-02 | architect (cross-model adversary pass) | Four git mechanisms the object-level filter did not reach, each verified against real git. **C-1005:** `.gitattributes` and `.gitmodules` added to the set, plus every mode-`160000` gitlink dropped by mode. A committed `.gitattributes` makes `worktree add` execute a configured smudge filter **before any harness starts** — confirmed running, and confirmed stopped by the object-level drop alone. A submodule is an instruction and code escape a shell-capable reviewer can mount with one command. **New C-1031:** one fixed git environment (`core.hooksPath`, `core.fsmonitor`, `core.attributesFile`, `GIT_ATTR_NOSYSTEM`) delivered via `GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n` so it binds **every git in the child's process tree**, not just nox's command lines — the worktree shares `$GIT_DIR/config`, so a model-issued `git checkout` inherited `core.hooksPath` untouched. `GIT_CONFIG_GLOBAL`/`SYSTEM=/dev/null` rejected: verified not to cover the vector and it breaks credential helpers and LFS. **C-1025:** probe cache keyed on resolved executable realpath + content hash + platform triple + launcher prefix + containment argv + environment hash, not the version string. Side effect: no smudge filter applies, so LFS materializes as pointers and § 8.1's one open latency exclusion closes. |
| 2026-09-02 | architect (cross-model adversary pass, part 2) | **Codex `--base` flipped:** a temporary `refs/nox/base/<token>` is now the primary route, not a fallback — the 0.144.1 help documents `<BRANCH>`, so making the ref primary *removes* the rollout gate rather than promoting it; raw-SHA support is an optional optimization. **Failure classification:** the universal auth/quota rows became a per-adapter matrix (companion § 7.1a) in which no adapter may claim a distinction the research did not observe — which is every cell except Claude Code's documented auth shape. **Matrix:** operational cost added as criterion **C7** and scored honestly against C (2 of 5); totals A 66, B 77, C 96, D 73, ordering unchanged, C's lead 23 → 19. Sensitivity stated as a range: B overtakes C when `w(C3) + 2·w(C7) > 26`, needing fidelity and operational cost at roughly twice containment's weight — which means abandoning the hostile-branch premise. Option B's steelman strengthened on the two-harness correctness point. **New C-1032:** real-binary contract tests are release-blocking, with named negative tests for sandbox escape, auth, quota, config loading, filter execution and submodule population; an absent binary blocks rather than skips. The unverified assumptions are now tabled in the Decision Outcome itself, not only in the body. |
| 2026-09-02 | orchestrator (`/hex-architect` handoff) | Three open markers resolved by the owner: Python runtime accepted as a hard dependency; `nox` kept, PyPI channel removed (no wheel ever); instruction files deleted with the neutralization set. Name-collision consequence aligned. Status unchanged — acceptance is the owner's step. |
| 2026-09-02 | orchestrator (`/hex-architect` handoff, owner input) | **C-1033** added: nox and hex are independent; nox's skill carries plain-metadata discoverability markers; `/hex-init`'s audit gains a propose-with-consent detection item (specified here, delivered hex-side). Integration claim corrected from "hex needs no changes" to "the adversary contract is unchanged; one audit item is added". Rollout step 9 re-pointed at the re-audit. |
| 2026-09-02 | orchestrator (`/hex-plan` gate, owner decisions) | **Accepted** by the owner at the `/hex-plan high` gate. Gate decisions binding on the plan: (1) federated plan, lead = arcana, satellite `nox` at `../nox` (adr_0004 shape; first real federated run); (2) deferred item "CI as a consumer" resolved as a **local release gate** — the three real-binary contract suites run on the owner's machine via `task release` before the tag, GitHub Actions builds and publishes the `.pyz` on tag only, CI dropped as a v1 consumer (C-1032's "release runner" is the owner's machine); (3) C-1033's audit item ships as a `Repo: .` work package of the nox plan. |
| 2026-09-02 | orchestrator (`/hex-plan`, owner decision after handoff) | **nox lives inside arcana at `nox/`**, a sibling bundle directory of `hex/` — not in its own repository. Supersedes the dossier's "own repository" Settled item and SD § 9.1 "Publishing"'s separate-repo shape (plan E13/D-aa): `nox/publish.toml` + `nox/nox.toml` ride arcana's existing `task publish` sweep and tag-driven `publish.yml`, one release train, one tag; SD § 9.1's scoping sentence reads "a separate bundle directory in the same repository". The federated plan shape (adr_0004) was withdrawn; every arcana release becomes a signed-tag release (plan C-1037). |
| 2026-09-02 | orchestrator (`/hex-plan` tier-high, plan addendum) | plan_adr_0011_nox_adversary — C-1034–C-1043 plan-authored (C-1034–C-1037 per § Deferred; C-1043 from the cross-model pass); errata E1–E12 applied; decisions D-i (`next_steps` kept, no home), D-j (POSIX-only v1 — owner ratification), D-w (no trust verb in v1), D-x (Linux-gated coverage); CI dropped as consumer |
| 2026-09-02 | orchestrator (`/hex-execute`, owner addendum during execution) | **Fourth v1 harness: GitHub Copilot CLI** (`copilot` 1.0.82, probed live before adoption). `--deny-tool` is an explicit enumerable deny list taking precedence over `--allow-all-tools`, so it satisfies `Capability.ENUMERABLE_DENY` — C-1013's `REQUIRED` capability — natively. Its MXC sandbox is **experimental and off by default**, so v1's containment for this harness is the C-1003 worktree plus `--deny-tool`/`--disable-builtin-mcps`/`--no-custom-instructions`, and both enforcement axes stamp `harness`, never `os`; `--experimental` sandboxing is out of v1. **And the manual cross-harness smoke became an N×N matrix** over the adapter registry — every harness as driver × every harness as adversary, self-pairs included (4 × 4 = 16 cells), data-driven so a fifth adapter re-instantiates it rather than rewriting it. **No new contract, and the decision is not reopened:** Option C is an ephemeral worktree for *every* harness, so a fourth harness is one more consumer of the same boundary — the option set, the weighted matrix and its ordering are untouched. Superseded by this row: § Context's placement of the Copilot adapter's direction value "Out of v1" (:50–62), companion § 9.1's In/Out lists and § 9.2 row 9's "all three binaries"; § 9.1's six-directed-edge N×N statement stands as the *product* claim — the 16-cell matrix is a test matrix and ships nothing. Carried in plan_adr_0011_nox_adversary as **D-ab / E14 / WP7d / S-1015 / R15**. |
| 2026-09-03 | orchestrator (`/hex-execute`, erratum during execution) | **The scratch directory moves OUT of the ephemeral worktree — a placement detail; the isolation decision is not reopened.** C-1009 put it *inside* the worktree; a live `copilot` review proved that this feeds nox's own `prompt.md` to the reviewer as repository content, and the reviewer correctly returned a `high` "repository content addresses and directs the reviewer" finding — **a false finding manufactured on every single review**, which trains an operator to dismiss the one finding class that catches real prompt injection (T1). It is now `mkdtemp`ed as a **sibling** of the worktree, mode `0o700` by construction, created in the same guarded step as the worktree so teardown removes both — so `git status --porcelain` in the worktree is empty at spawn time again, correcting the 2026-09-02 narrow-pass row's own correction. C-1009's naming rules (never a fixed `.nox`, never `exist_ok`, `O_NOFOLLOW\|O_CREAT\|O_EXCL` on the diff write) are unchanged. **The original rationale is kept as a precondition, not struck:** Claude Code under `--restricted` confines its file tools to the working directories, so a path outside the worktree is unreadable to that harness — void today, because every merged adapter delivers the prompt as an argv word through `argv_prompt` and the Codex leg targets `--base refs/nox/base/<token>` rather than `<scratch>/review.diff`, but binding again on the first adapter that moves to a **file-delivered prompt or diff**, which must re-establish out-of-worktree readability or move its scratch back inside and accept the manufactured finding. **Not reopened:** C-1003 / Option C — an ephemeral worktree for every harness; the option set, the weighted matrix and its ordering are untouched. Corrected in place: C-1009's scratch paragraph and its diff-by-path sentence, § Component contracts' `Workspace.scratch` comment and `workspace()` docstring, § Decision Outcome's `--uncommitted` note, the narrow-pass porcelain correction, and companion § 4.1 step (e) with its pseudocode. Carried in plan_adr_0011_nox_adversary as **E20**; WP11 Step 11.2's addendum row carries it alongside D-ac/E15/E16/E17/E18. |
| 2026-09-03 | orchestrator (`/hex-execute`, WP11 assembly proof — Step 11.2 addendum) | **Execution addendum: what execution corrected in this ADR's text, and the one residual it accepted rather than closed. No decision is reversed; Option C, the option set, the weighted matrix and its ordering are untouched.** **D-ac — process-lifetime containment on the clean-exit path is ACCEPTED AND STAMPED, not deferred.** The process group is the containment primitive and it does not close two holes: a descendant **backgrounded across a clean exit** (no signal is issued on that path, so nothing sweeps it) and one that calls **`setsid()`** (it leaves the group, and no rung of the kill ladder reaches it). What v1 guarantees — now the stated guarantee, not an implied one — is **nox's own return**: a survivor holding the merged pipe open delays `Process.wait` by at most `JOIN_S` (5.0 s) before the daemon drain thread is abandoned. Weighed and rejected: `waitid(WNOWAIT)` is the only portable primitive that observes an exit without reaping (the CWE-367 pid-recycling guard a post-exit `killpg` needs), and CPython does not expose it on macOS before 3.13, so the mechanism would hold on Linux plus macOS-3.13+ and fall back elsewhere — a stamp under another name; and it closes only the *backgrounded* hole, the `setsid()` escape needing cgroup v2 delegation or a PID namespace, both outside a zero-runtime-dependency POSIX-only v1. Severity is bounded by what the residual grants, which is **nothing new**: a survivor runs at the same uid, under the C-1008 minimal environment, from the C-1003 ephemeral worktree. **No `Containment` field is added** — the residual is identical for every run, so a constant-valued axis would read as derived evidence under C-1025 and carry none; correspondingly **no adapter, stamp or user-visible string may claim that containment bounds descendant lifetime**. WP11 pins the bound against a real forked pipe-holding grandchild (`JOIN_S` measured against a 120 s sleeper, the queued line surviving the abandoned join, the survivor still alive afterwards) and pins both halves of E17's corrected sentence. **E17 — C-1009's text corrected:** "`start_new_session=True` so a timeout kill reaps grandchildren" overstates the primitive; a signal to the process group reaches every descendant *still in that group*, on a path where a signal is actually issued. **E15/E16 — drain-thread reading settled:** E7's "bounded queue" is bounded by the pre-enqueue byte cap plus an independent `MAX_LINES` ceiling, never by a `queue.maxsize` (which would wedge the drain thread on every kill path); and an overflow resolves **`indeterminate`**, not `error` — § 7.1 wins over E7's prose, and `Supervision` has no `status` field by construction. **E18 — C-1005's neutralization set EXTENDED by evidence, closing an unmitigated T1 on a shipped adapter:** the set was written from three harnesses and missed repo-resident instruction surfaces all four v1 harnesses actually read, so the reviewed branch's own instructions loaded into the review. Added to `NEUTRALIZE_FILES`: `copilot-instructions.md`, `GEMINI.md`, `CLAUDE.local.md`, `AGENTS.override.md`; to `NEUTRALIZE_GLOBS`: `*.instructions.md`, `*.agent.md`; and a new repo-root-anchored `NEUTRALIZE_PREFIXES` (`.github/skills/`, `.agents/skills/`, `.github/hooks/`, `.github/copilot/`, `.github/mcp.json`) — root-anchored **because of C-1003**, and prefixes rather than basenames because `SKILL.md`/`settings.json` over-drop catastrophically. Every entry is pinned to an observation (a live canary or a literal read out of the binary's own bundle), never to a reading of intent. Deliberately excluded: `.github/` wholesale (it would drop `.github/workflows/**`, the supply-chain surface an adversarial reviewer must see), `.vscode/mcp.json` (support removed in copilot 1.0.82), `.github/prompts/**` (absent from the package). The existing set, the mode-`160000`/`120000` rules and the object-level mechanism are unchanged. **E19 — `OPENCODE_AUTH_JSON` does not exist** in the opencode 1.18.22 binary: C-1008 enumerated a variable no harness reads. Dropped from the allowlist and the inbound-path guard — nothing is lost, the store is reached through `HOME`/`XDG_DATA_HOME`, which are on both already — and the name that really carries the store **inline, by value**, `OPENCODE_AUTH_CONTENT`, is added to the never-forward set: opencode **sets it itself** when spawning subprocesses, so a nox invoked from inside an opencode session would otherwise hand the adversary the user's whole auth store. Per D-ad, **no credential value crosses the boundary in v1** — no per-harness `forward_env`, and `GITHUB_TOKEN` is not allowlisted. **E21 — the Codex leg is bare `codex exec`, not `codex exec review --base refs/nox/<token>/base`:** § 6.2's invocation cannot be built at 0.144.1 — `exec review` accepts exactly one of `{--uncommitted, --base, --commit, [PROMPT]}` while C-1028 makes the prompt mandatory, and it carries no `-s/--sandbox`. Consequence stated plainly: **`refs/nox/<token>/base` now has no consumer on this leg** — it is still minted and still does its C-1004 anti-gc job, but nothing passes it to a harness; § 6.2's three codex rows still call it the `--base` argument, and its `passthrough` row named an `--title` flag `codex exec` does not have. D-v is answered **yes** either way (`codex exec review` does execute shell commands), so this is not R1's fallback firing and no provenance stamp is owed. **E22 — C-1040's `status == "failed"`/non-zero-exit clause is struck; its discriminator is kept:** a command the sandbox blocks emits **no `command_execution` item at all**, so the clause as written would refuse every correctly-sandboxed run. Shipped: each attempt is spelled `<attempt> \|\| cat <nonce>`, restoring the item and carrying an unforgeable per-attempt nonce (`secrets.token_hex` under the run token, `O_EXCL\|O_NOFOLLOW`, removed before `authorize` returns). A missing item is still **inconclusive**, never a pass; all four observations are still required to resolve either axis `"os"`. **R9 refuted:** `--pure` does **not** stop a repo-authored `.opencode` plugin executing (tested with and without the flag, both positions); the route is closed by the neutralization directory set plus `probe_cwd`, the contract tests pin the negative, and `--pure` stays emitted as a derivation tripwire promoting **no** enforcement axis. **Release-path errata (E24–E27), all in the fail-closed direction:** grim 0.14.0 emits no member list in either dry-run output mode, so C-1037(4)'s "the packed skill must list `scripts/nox.pyz`, asserted from the dry-run output" is not implementable and is substituted by `test -s` plus a **layer-digest differential** that builds the skill directory with and without the asset — the discriminator preserved, not relaxed (E24); WP10's file cell omitted two shipped files (E25); the gate runs **nine** steps, the contract's seven plus a version-agreement step and a published-file-set step (E26); and `publish.yml` installs the toolchain **after** `git verify-tag` rather than before, so nothing is downloaded or executed before the signature is verified (E27). **E20** (scratch directory moved outside the worktree, with C-1009's `--restricted` rationale preserved as a live precondition naming the Codex leg) is carried by the row above it and is not repeated here. **E23 — what C-1040's attempt evidence proves, and what it does not** (authored on `codexfix2`, merged at `b8f6385`; recorded here rather than left as a pointer): `attempt_proven`'s discriminator is the `\|\| cat <nonce path>` **tail**, not the bare nonce path — matched as a pattern, because a tail that fails to match returns `False` and would refuse **every** Codex review on that machine, so it absorbs spacing, an optional `./` and any quoting, and ends on a word boundary because `nonce-<token>-1` is a prefix of `nonce-<token>-10`. **Not closed, and not closable by any discriminator:** an item whose command merely CONTAINS the tail while reading the file proves the same thing, attempts nothing, and leaves the marker absent and the listener silent — every string in this evidence is one the probe's own ask hands the model. **The honest claim is therefore narrower than C-1040 reads:** the item plus the nonce proves that a command carrying the tail emitted the nonce, which rules out C-1040's own named case (the model that declined and ran nothing), while the marker's continued absence and the listener's silence — nox's own observations, not the model's report — prove that nothing wrote or connected. All four observations are required together and none is sufficient. The nonce stays unguessable: a 128-bit value under a 128-bit run token, both minted after checkout, written `O_EXCL`+`O_NOFOLLOW` and unlinked before `authorize` returns. **Assembly proof at tip `920a423`:** `task nox:verify` exit 0 at 100% coverage (2482 stmts / 514 branches, Python 3.11); `task publish -- --dry-run` exit 0 over both manifests; the live contract tier **89 passed / 0 skipped** against all four real binaries; `/hex-init`'s audit item proposes `adversary: nox-review` and is silent with the skill uninstalled; a live cross-model review through the installed skill reached `copilot` and returned findings including the planted defect; and `hex/` changed in exactly three files (C-1001(a2)). Carried in plan_adr_0011_nox_adversary as **D-ac, E15, E16, E17, E18, E19, E21, E22, E24–E27** and § WP11 assembly proof. |
| 2026-09-03 | orchestrator (`/hex-execute`, erratum during execution) | **C-1005: the diff now does reach the model through the prompt, but a NEUTRALIZED file's content still reaches it by no route — the ADR's :811 sentence draws the wrong conclusion from a premise that has since become true.** C-1005 drops each neutralized entry from both synthetic trees, so the file is identical on either side and `git diff` emits nothing for it. The reviewer is told the path was filtered (C-1028, C-1043), which is the designed answer; rendering the content back in would reopen the injection channel C-1005 closes. No decision is reversed and the body is unchanged — recorded as plan erratum **E28** so the code is not "fixed" to match the prose. |
| 2026-09-03 | orchestrator (`/hex-execute`, erratum during execution) | **The prompt-delivery limit is per-CHANNEL, and C-1009's "never stdin" is superseded for the prompt.** `PROMPT_ARGV_LIMIT` is the kernel's `MAX_ARG_STRLEN`, and applying it to every adapter refused any review whose diff passed 128 KiB — on this branch, 2.8 MB — making whole-branch review unreachable on all four harnesses. Probed live: `claude` and `codex` take the prompt on **stdin**; `copilot` 1.0.82 and `opencode` have no prompt file and no stdin form. Those two keep the argv refusal, now loud about which channel and which kernel limit refused; the other two carry `Launch.stdin_path`, opened `O_NOFOLLOW` from `Workspace.scratch` and policed by `authorize`. `DEVNULL` remains the default everywhere else. Isolation, containment and C-1028's no-truncation rule are unchanged. Plan erratum **E29**; SD § 7.1 gains the matching `INVALID_CONFIG` row. |
| 2026-09-03 | orchestrator (`/hex-execute`, WP13 convergence — errata E30–E52) | **Execution addendum: what WP13 corrected in these records, the three rulings it puts on the record, and the **one** question it hands back to the owner — corrected in place from four, within this same WP, as E47 became a contract, E51 was resolved by live probe and E48 by measurement. No decision is reversed and no contract is reopened.** **Corrections where the record was wrong and the code right:** C-1006's restatement claimed the startup sweep reaps a SIGKILLed nox's refs *and* worktree — `git worktree prune` deregisters only a worktree whose **directory is gone**, so a killed run's registration survives, its token reads as live, and its refs are spared forever; the scratch sibling is `finally`-only and leaves `review.diff` + `prompt.md` (the whole diff and the whole prompt) at `0700`/`0600` under the temp root **permanently**, recorded as a residual and not given an invented cleanup contract (**E30**). C-1018's "high entropy" is not a scanned shape and is declined on the record: four literal prefixes, because a score over an 8 MiB attacker-chosen `raw` is a false-positive generator and a regex over it is a denial of service (**E31**). C-1022 is written as a **quota** requirement and ships as a `threading.Lock`, which is **vacuous for `nox.cli`** — one process, one review — so two shells spend the same vendor quota concurrently (**E32**). `grim status --format json` has no top-level `outputs` array; the shape is `items[].outputs[]` (**E33**). § *Option A* and SD § 6.1 both name `--permission-mode dontAsk` on the Claude Code leg; `--permission-prompts none` is what ships, and `--permission-mode` is in `NEVER_EMITTED` — a flag nox refuses — because at 2.1.259 the "blocks forever on a prompt that never arrives" premise is false and `dontAsk` names auto-approval. No stamp leans on it (C-1025's claude rows rest on `--tools` and `--strict-mcp-config`), so it is a record correction, taken at both sites (**E52**). **Three rulings, recorded not re-argued.** **R-1:** D-aa's one-tag train makes **nox's version track the arcana tag rather than its own cadence** — 0.1.0 → 0.3.0 with no 0.2.0 is the intent, not an accident, and the consequence is that a nox version number carries no information about how much nox changed (**E34**). **R-2:** a reviewer reproduced `.git/info/attributes` smudge → execution during `worktree add`; **the reproduction is real and it is not a defect** — it needs a capability the threat model denies, since an attacker who can write inside `.git` already owns the repository host and nox's boundary starts at repository *content*. § T1b stays as written; what was missing was the record that it had been tested (**E35**). **R-3:** the prompt's do-not-approve sentence was gated on the `filtered` **union**, so any repository holding one committed symlink or submodule told every reviewer of every branch that the change had been withheld — a `needs-attention` verdict manufactured out of a file nobody touched. The union still renders as evidence (C-1043(2)); `_INCOMPLETE` is now gated on **`filtered_changed`** (C-1043(4)) as a gate-only argument, and `PROMPT_VERSION` moves **3 → 4** with it (owner ruling): no sentence was edited, but for any repository holding a committed symlink or submodule version 3 emitted the do-not-approve instruction and version 4 does not, so the bytes the model receives changed and a version that did not move would lie to anything pinning it (**E36**). **What WP13 shipped and the records did not yet carry:** C-1036's asymmetry warning was **inert on all four harnesses** — no shipped `MODELS` table resolved either measured id — and is widened to family prefixes with the warning text naming the measured pair and stating the family generalization is **untested** (**E37**); § 7.1's single `exit 143` row was resolved three different ways across four adapters, one of which never mapped it at all while documenting that it did, and is unified as "the exit status labels a run whose stream established neither a verdict nor a terminal outcome of its own, and never overrules one that did" (**E38**); copilot's `network_enforcement="harness"` stamp **stands**, but the argument under it was wrong — measured live against a user-configured MCP server, `--disable-builtin-mcps` does not cover it and `--deny-tool` cannot reach a `<server>-<tool>` name, and **`--available-tools`** (18 → 3 tools) is what removes it; the argument is now a committed fixture (**E39**); a committed **NUL** made `Popen` raise `ValueError`, which `api._spawn` did not catch, letting a repository deny its own review and blame the harness — `argv_prompt` now refuses `INVALID_CONFIG`, and the **stdin** channel is deliberately left unguarded because it hands the child an fd, not a string (**E40**); `probe_digest` hashes the launcher, not the wrapped payload, so `authorize` now uses a **per-launch** probe cache behind any launcher prefix (**E41**); an explicit `state_dir`/`user_dir` override bypassed repository containment, letting a branch-local `trust.json` authorize a branch-local `nox.toml` — i.e. the branch choosing the executable nox spawns — closed by one guard in `config._xdg`, reachable today only by a library consumer, which is what makes a later `--state-dir` flag safe (**E42**); the merge-base branch had no killing test and the symlink/submodule enumeration spawned two `git cat-file` per entry per tree end (50 000 entries: 40.3 s → 0.5 s, ~86×, via one `--batch-check`/`--batch` pair), with `<oid> missing` exiting **0** where `cat-file -s` exited 128 now refused explicitly as `ISOLATION_FAILED` (**E43**); the harness probe ran before target validation, so a bad `--base`, a `--path` outside the repo and a missing `--path` all reported the harness absent — validation now runs first, a bad `--base` refuses `INVALID_CONFIG` naming flag and value instead of `isolation_failed` (which reads as a containment breach), and an absent launcher names the harness and its launcher rather than the bare word `ocx` (**E44**); and the consumer failure vocabulary — `detail:`, `counts:`, and a non-`ok` `status:` as **the skip** — is now documented on both sides, with hex's degrade clause widened from "the skill is unavailable" to "the adversary produced no review" and the rule that an empty finding list is never a clean pass (**E45**). The prompt fence allocated one Python object per character (9.4 of a measured 12.0-fold peak-RSS multiplier) and missed invisible characters outside `Cf`/`Mn`, so a diff line could render as exactly the closing delimiter; both closed, and **the byte cap stays deferred** as a product decision colliding with C-1028 (**E46**). **Two widenings recorded rather than resolved, both fail-safe and neither an owner question:** `NEVER_EMITTED` grew to 50 members pinned against committed `--help` fixtures under E3, **30 of which appear in no design record** (**E49**); `NEVER_FORWARD` ships `LD_AUDIT`, `LD_LIBRARY_PATH` and `PYTHONPATH` past C-1034(1)'s enumeration, authorized by its "at least" wording (**E50**). **One question handed back to the owner: the prompt's byte cap stays deferred (E46, above)**, a product decision colliding with C-1028. **Three more left this list inside WP13, and this row is corrected in place rather than contradicted by a later one:** `config.ALLOWLIST`'s widening past a closed C-1008 is **settled by evidence, not by ruling, and by two instruments** — the six names without a record trace were checked against the four shipped harnesses' own artifacts for an environment read; `TZ` is read by none of them and is the one deletion, `LC_CTYPE` and the `ALL_PROXY` pair are kept on that measured cause, and `SSL_CERT_DIR` with `CURL_CA_BUNDLE` are kept on **named** cause and explicitly not on measurement, because their breaking condition — a TLS-inspecting corporate proxy — is one a stock developer machine cannot produce, making a read measurement there a false negative rather than an absence of cause; the drop-and-run sweep that preceded all of it was vacuous, since `minimal_env` forwards only names that are present and seven of the eight are unset; and C-1008's own enumeration is **rewritten from class-shaped to name-shaped** above, so the contract now says what its oracle checks (**E48**); `harness.NEVER_SET` is no longer a rule without a contract — it is authored as **C-1044** under this ADR's "Deferred to /hex-plan" delegation, the seven members unchanged and only the record moved (**E47**); and `--agent explore` is no longer a launch-gate question — probed live, 1.18.22 answers `agent "explore" is a subagent, not a primary agent. Falling back to default agent` and then runs under **`build`**, opencode's default **read-write** agent, so the flag is accepted syntactically and silently discarded. Emitting it would put a containment word on argv that a derivation rule could corroborate over a read-write run, so **not emitting it is the safer answer, not just the simpler one**; the five sites in this ADR and the system design are corrected to name the `OPENCODE_CONFIG_CONTENT` deny map plus `--pure`, and both axes stay `attested` because the deny map's resolution order was never observed — only its presence in the resolved rule list (**E51**). Carried in plan_adr_0011_nox_adversary as **E30–E52** and § WP13 errata, residuals and open questions. |
