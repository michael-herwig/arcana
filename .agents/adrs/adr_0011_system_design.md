# System Design: nox — multi-harness adversarial review

**Companion to** [`adr_0011_nox_multi_harness_adversary.md`](adr_0011_nox_multi_harness_adversary.md).
That ADR holds the decision, the four weighted options and the contracts;
**this doc is the buildable spec** — C4 at four altitudes, the threat model,
the failure-mode table, the degrade ladder, the per-harness invocation tables,
and the rollout sequence. Date 2026-08-31, revised 2026-09-02. Status tracks
the ADR (Proposed).

Contracts are numbered `C-10xx` in the ADR. **Where this doc and the ADR could
disagree, the ADR's contract text is canonical and everything here is derived
from it.** This doc introduces no contract of its own.

Terms: **harness** = an AI coding CLI nox drives (v1: Claude Code, Codex,
OpenCode); **adapter** = nox's per-harness translation layer; **workspace** =
the ephemeral git worktree one review runs in; **neutralization set** = the
literal path list deleted from the workspace before spawn (C-1005);
**containment plan** = how one adapter establishes no-repository-write and
no-network (C-1007); **consumer** = whatever calls `nox.api.review()`.

The single invariant everything below serves: **nox spawns a harness only
inside a tree it created, with the harness's own configuration filtered out of
the objects that tree is built from, no write path back to the repository, no
network, and an environment it built by allowlist.** Every diagram and failure
row is a restatement of that sentence at a different altitude — and § 5 states
plainly what kind of boundary it is, and what it is not.

Two qualifiers travel with that sentence wherever it is repeated, because
dropping them would be the dishonest version: **"no network" is enforced by the
operating system on one of the three harnesses and asserted by configuration on
the other two** (C-1007, and the `AF_UNIX` residual in § 5.8), and **untracked
files are not reviewed, with their omission stamped and verdict-blocking**
(C-1026).

---

## 1. C4 — Context

```
   ┌──────────────────────────────────────────────────────────────────┐
   │  consumer                                                        │
   │  · hex /hex-review, via `adversary: <skill>` (C-1001, no change) │
   │  · a human running the skill or the .pyz directly                │
   │  · CI — see the caveat below; NOT usable under subscription auth │
   │  requires: python3 on PATH. NOT required: hex, node, docker.     │
   └───────────────────────────┬──────────────────────────────────────┘
                               │ nox.api.review(ReviewRequest)
                               ▼
  grim registry ──ships──►  nox skill  ( SKILL.md + scripts/nox.pyz )
                               │
        ┌──────────────────────┼───────────────────────┬──────────────┐
        │ reads                │ reads + WRITES        │ spawns       │ reads
        ▼                      ▼                       ▼              ▼
  user config dir        local git repository   harness CLI ×3    the diff
  · nox.toml             · worktree add/remove   · claude         (untrusted
  · trust store          · stash create          · codex           content, by
  · call log             · object store (SHARED) · opencode        construction)
    (C-1017, C-1021)     · refs/    (SHARED)     (each authenticates
                                                  as ITSELF — C-1002)
                                       │
                                       ▼
                            vendor API (Anthropic / OpenAI / whatever
                            provider the user configured behind OpenCode).
                            nox holds NO key and speaks NO wire protocol.
```

Three Context edges deserve naming, because they are what makes nox different
from every cross-vendor second opinion in the survey:

1. **nox writes to the local git repository.** Every other tool in the
   landscape either holds API keys and multiplexes at the API layer (Amp's
   Oracle and Aider's architect/editor at
   [`discuss-nox-vendor.md:24-30`](../research/discuss-nox-vendor.md), Zen/PAL
   MCP at [`:49`](../research/discuss-nox-vendor.md)) or drives a harness in
   place. nox does neither: it creates a tree — and, under C-1005, two
   unreferenced commit objects per review as well. That write edge is the
   decision.
2. **nox never touches a credential.** Each harness authenticates as itself.
   This is the whole of nox's ToS position: the prohibited line is identity
   misrepresentation, not automation
   ([`nox-security.md:446-455`](../research/nox-security.md)). The three
   stores nox must never read are `~/.claude/.credentials.json`,
   `~/.codex/auth.json` and `~/.local/share/opencode/auth.json`.
3. **The object store and `refs/` are shared with the real repository even
   inside a worktree** — `git-worktree(1)`: "sharing everything except
   per-worktree files such as HEAD, index"
   ([`nox-security.md:806-816`](../research/nox-security.md)). The workspace is
   not a git boundary. § 5.4 develops what follows from that.
4. **CI is drawn as a consumer and the auth model excludes it.** C-1002 settles
   on the user's own interactively logged-in harness CLI, C-1021 forbids
   retrying an auth refresh, and `--bare` — Claude Code's API-key mode — is
   excluded by C-1023 for exactly that reason. Wire nox into a CI job and every
   run raises `UNAUTHENTICATED`, the consumer degrades to a graceful skip, and
   the pipeline stays green while reporting "Cross-model review skipped"
   forever. **A permanently skipped security gate that looks healthy is worse
   than an absent one.** Resolving this — drop CI from the diagram, or state
   that CI requires API-key mode and reconcile that with C-1023 — is deferred
   to `/hex-plan` and listed in the ADR's *Deferred* table. Until it is
   resolved, treat the CI edge as aspirational.

---

## 2. C4 — Container

```
┌──────────────────── nox.api.review()  (one process, no daemon) ─────────────┐
│                                                                             │
│  config ─► registry ─► probe ─► WORKSPACE ─► plan ─► prepare ─► supervise ─►│
│                                     ┃                                       │
│                          the seam: left of it nothing is spawned;           │
│                          right of it nothing runs in the user's tree        │
│                                                                             │
│  · serialized by default (C-1022, quota — no longer containment)            │
│  · zero runtime dependencies; stdlib only                                   │
└──┬──────────────┬─────────────────┬──────────────────┬──────────────────────┘
   │              │                 │                  │
   ▼              ▼                 ▼                  ▼
┌ config ──┐ ┌ registry ─┐ ┌ workspace ─────────┐ ┌ runner ──────────────┐
│ upward   │ │ str → dot │ │ filter NEUTRALIZE  │ │ Runner.spawn         │
│ search   │ │ ted path, │ │  out of BOTH trees │ │  └─ the ONE pragma   │
│ ≤20 deep │ │ lazy imp- │ │ worktree add synth │ │ supervise()          │
│ st_dev   │ │ ort       │ │ write .nox-<rand>/ │ │  deadline · silence  │
│ drop→val │ │ (fsspec   │ │      review.diff   │ │  byte cap · TERM→    │
│ trust    │ │  shape)   │ │ FINALLY: remove    │ │  grace → KILL(group) │
│ gate     │ │           │ │  --force + prune   │ │                      │
└──────────┘ └───────────┘ └────────────────────┘ └──────────────────────┘
                                   │                        │
                                   └──── cwd ───────────────┘
                                          ▼
              ┌ adapters/ ─────────────────────────────────────────┐
              │ claude.py        codex.py         opencode.py      │
              │ tool-removal     os-sandbox       config-deny      │
              │ probe · containment_plan · prepare · parse         │
              │ verified_against = "<version>"                     │
              └────────────────────────────────────────────────────┘
```

Container-level invariants:

- **No daemon, no broker, no long-lived protocol session.** `codex-plugin-cc`
  runs a detached Unix-socket broker to avoid app-server cold start; Codex
  offers `app-server`; OpenCode offers `run --attach <url>`. All three are
  documented upgrade paths, none is built (C-1024): a second long-lived
  process is a second lifecycle, a second leak class and a second thing to
  secure, for a saving nobody has measured — and in Codex's case the transport
  is `[experimental]` with undocumented trust behaviour.
- **The workspace is a context manager and its teardown is in a `finally`.**
  No code path spawns a harness without one, and none leaves one behind on a
  normal or exceptional exit.
- **Adapters translate; they do not decide.** Isolation, environment,
  timeouts, byte caps and the tri-state resolution are core concerns. An
  adapter contributes argv, a containment plan, a capability record and a
  parser.
- **One `subprocess` import, in `runner.py`.** Everything above it is a pure
  function over `Process`.

---

## 3. C4 — Component

```
review(req, repo)
 │
 ├─(0) minimal_env() ──────────────────────────────────── C-1008
 │      built ONCE, before anything is spawned — the probe is a real harness
 │      startup and must not run with the ambient environment either
 │      allowlist + credential denylist + inbound-value rejection (T4b)
 │      plus the C-1031 GIT_CONFIG_* overrides, CONSTRUCTED not forwarded —
 │      they bind every git in the child's process tree, which the old
 │      per-call `-c core.hooksPath=/dev/null` never did
 │
 ├─(1) config.load(cwd) ─────────────────────────────── C-1016, C-1017
 │      upward search, first nox.toml wins, depth ≤ 20, no st_dev crossing,
 │      tolerate the name being a directory (uv#7351)
 │      ├─ unknown key → warn, ignore                     (forward-compat)
 │      ├─ FIRST: permission key from an UNTRUSTED repo-local file → drop+warn
 │      │    trust = (path, sha256); any edit invalidates it (mise paranoid
 │      │    model, GHSA-436v-8fw5-4mj8). Content-scoped, NOT path-scoped —
 │      │    deliberately the opposite of Codex's project-trust gate (§5.2)
 │      ├─ THEN: malformed PERMISSION_KEYS value in what SURVIVED the drop
 │      │    → ConfigError (CWE-1188).  ORDER MATTERS: validate-then-drop
 │      │    re-opens T6 — `read_only = "yes"` in a hostile repo `nox.toml`
 │      │    would raise before the drop rule ever ran (§5.7)
 │      └─ resolve model CLASS → adapter literal            (C-1030, adr_0001)
 │           `model` is a class (fast-balanced | deep-reasoning), never a
 │           literal ID; literals live in [harness.<name>] only. Invalid ⇒
 │           warn + shipped default, NEVER ConfigError: every default here is
 │           a real model, not a guess about a control, so failing hard would
 │           hand `model = "garbage"` the same DoS the drop rule closes
 │
 ├─(2) ADAPTERS[req.harness] ──────────────────────────── lazy dotted import
 │
 ├─(3) adapter.probe(runner, cfg) ─────────────────────── C-1014
 │      a real short invocation through Launcher(prefix, binary), NOT
 │      shutil.which alone — `ocx package exec ocx.sh/anomalyco/opencode:
 │      1.18.22 -- opencode` is a live example of a harness with no binary
 │      on PATH
 │      cwd = a FRESH EMPTY TEMP DIR nox owns; env = step (0). Never an
 │        inherited cwd, never the repo: a `--version` is a startup, and
 │        OpenCode executes `.opencode/plugins/` on any startup (§5.2)
 │      raises HarnessUnavailable(reason=ABSENT | UNAUTHENTICATED, detail)
 │      returns HarnessInfo{version, verified_against, capabilities,
 │                          heartbeat_kind, launcher}
 │
 ├─(4) workspace(repo, target) ─── enter ──── C-1003 … C-1006, C-1026, C-1027
 │      a. resolve the PAIR:  ref → (merge-base(base,ref) | ref^, ref)
 │                            working-tree → (HEAD, `git stash create`);
 │                              no ref, no index, no working-tree mutation;
 │                              empty ⇒ (HEAD^, HEAD)
 │                            plan-artifact → (empty tree, empty tree + the
 │                              artifact as a ONE-FILE ADDITION) so the
 │                              artifact IS the diff and every adapter takes
 │                              the ordinary code-diff route      (C-1027)
 │      b. NEUTRALIZE BOTH ends at the OBJECT level: read-tree into a temp
 │           index, drop every entry matching the C-1005 set by ANY path
 │           component INCLUDING the basename (else a set member committed as
 │           a symlink survives) PLUS every mode-160000 gitlink,
 │           write-tree, commit-tree                       ← THE mitigation
 │           the set includes `.gitattributes` (a smudge filter runs during
 │           `worktree add`, before any harness) and `.gitmodules`
 │           the TARGET gets `-p <synthetic base>` — without ancestry
 │           merge-base fails and the Codex `--base` leg dies at runtime
 │      c. `git ls-files --others --exclude-standard` MINUS whatever step (a)
 │           materialized → ws.omitted; non-empty ⇒ verdict may not be
 │           approve (C-1026). The subtraction is what stops a plan-artifact
 │           review accusing the document it is reviewing
 │      d. git -c core.hooksPath=/dev/null worktree add --detach <tmp> <synth
 │           target>.  Nothing is ever deleted from disk
 │      e. mkdtemp .nox-<token>-<rand>/ BESIDE <tmp>, never inside it —
 │           random, never `.nox` (C-1009; plan E20 — inside the worktree it
 │           put nox's own prompt into the surface under review)
 │      f. write <scratch>/review.diff = synth base..synth target, O_NOFOLLOW
 │           (two-dot; with real ancestry three-dot is identical)
 │      any failure → IsolationError → FailureReason.ISOLATION_FAILED
 │
 ├─(5) adapter.containment_plan(cfg, info) ───────────── C-1007
 │      mechanism ∈ {tool-removal, os-sandbox, config-deny}
 │      write_enforcement and network_enforcement ∈ {os, harness, attested}
 │      either None ⇒ no launch. `os` requires a cached passing probe keyed
 │      on info.version — an adapter cannot simply claim it       (C-1025)
 │
 ├─(6) adapter.prepare(req, ws, info) ────────── C-1007, C-1013, C-1023
 │      ├─ capability ∉ REQUIRED absent     → UnsupportedCapability, no launch
 │      ├─ either enforcement axis is None  → UnsupportedCapability, no launch
 │      ├─ passthrough element not in PASSTHROUGH_ALLOW[adapter], or a
 │      │    value-carrying config flag, or a duplicate of a nox-owned flag
 │      │                                   → ConfigError, no launch
 │      └─ build Invocation{argv, cwd=ws.path, env=step (0)}       C-1008
 │            passthrough FIRST, nox's containment flags LAST (C-1023)
 │            argv is a list; the diff is NEVER in it and never on stdin
 │
 ├─(7) supervise(runner.spawn(inv), TimeoutPolicy.for_kind(...), hb, on_line)
 │      C-1009, C-1010, C-1015
 │      one merged pipe, drained in a thread (selectors has no Windows pipes)
 │      deadline = wall clock; silence = per Liveness kind, or None
 │      SIGTERM(group) → grace → SIGKILL(group); start_new_session=True
 │      byte cap 8 MiB → truncated=True
 │
 ├─(8) adapter.parse(lines, exit_code, hb) ────────────── C-1011, C-1012
 │      exit code is a coarse hint, NEVER the success gate
 │      classify from the event stream → ok | error | indeterminate
 │      unclassifiable → indeterminate + raw, never "approve"
 │
 ├─(9) workspace ── exit ──► git worktree remove --force; git worktree prune
 │
 ├─(10) Containment DERIVED from the resolved argv + env + cached probe
 │      C-1025 — never from a literal the adapter wrote. Stamped on EVERY
 │      return path, including error and indeterminate
 │
 └─(11) log(harness, model, ts, duration, outcome, cost) ── C-1021
        NEVER `raw`: it can carry credentials the child read (C-1018)
        return Review{..., containment=Containment(...)}  ── C-1019
        review() itself never raises — every exception above becomes a
        Review with status != "ok"                        ── C-1029
```

**Why (4) precedes (5)–(6) and not the reverse.** The adapter cannot build its
argv until `cwd` exists, because `cwd` *is* the workspace. More importantly,
ordering neutralization before any adapter code runs means no adapter can be
written that forgets it: an adapter has no opportunity to spawn anything,
because it does not spawn — it returns an `Invocation` to core, which spawns.
The security-critical ordering is structural, not a convention an adapter
author must remember.

**Why (5) is a separate step from (6).** `containment_plan` is queried and
checked *before* argv is assembled, so the refusal path is reachable without
constructing an invocation at all. An adapter cannot smuggle containment into
its argv builder and assert it afterwards.

---

## 4. Code-level (only where warranted)

### 4.1 The workspace lifecycle — the one place isolation is decided

```python
@contextmanager
def workspace(repo: Path, target: ReviewTarget) -> Iterator[Workspace]:
    _git(repo, "worktree", "prune")                     # C-1006, reclaim leaks
    base, head = _resolve(repo, target)                 # C-1004 — a PAIR
    s_base = _neutralize(repo, base)                              # C-1005
    s_head = _neutralize(repo, head, parent=s_base)   # -p ⇒ REAL ANCESTRY
    omitted = _untracked(repo, target, materialized=s_head)       # C-1026
    path = Path(mkdtemp(prefix="nox-ws-"))              # nox-owned prefix
    try:
        _git(repo, "worktree", "add", "--detach", str(path), s_head)
        scratch = Path(mkdtemp(prefix=f".nox-{secrets.token_hex(8)}-",
                               dir=path.parent))  # C-1009, plan E20 — a
                                         # SIBLING of `path`, never a child:
                                         # inside the worktree it is content
                                         # under review. Still never a bare
                                         # `.nox`, and a mkdtemp name cannot be
                                         # pre-created by the branch
        diff = _write_nofollow(scratch / "review.diff",
                               _git(repo, "diff", f"{s_base}..{s_head}"))
        yield Workspace(path, s_base, s_head, scratch, diff, _verify(path), omitted)
    finally:
        _git(repo, "worktree", "remove", "--force", str(path))  # submodules
        _git(repo, "worktree", "prune")
        rmtree(scratch, ignore_errors=True)  # E20: the scratch is a SIBLING,
                                             # so `worktree remove` no longer
                                             # takes it with the worktree

def _resolve(repo: Path, target: ReviewTarget) -> tuple[str, str]:
    if target.kind == "plan-artifact":                            # C-1027
        empty = _git(repo, "hash-object", "-t", "tree", "/dev/null").strip()
        base  = _git(repo, "commit-tree", empty, "-m", "nox: empty").strip()
        # The artifact IS the diff: one file added against an empty tree, so
        # every adapter takes the ordinary code-diff route with no branch.
        blob = _git(repo, "hash-object", "-w", str(_inside(repo, target.path)))
        with _temp_index() as idx:
            _git(repo, "read-tree", empty, index=idx)
            _git(repo, "update-index", "--add", "--cacheinfo",
                 f"100644,{blob.strip()},{target.path.relative_to(repo)}", index=idx)
            tree = _git(repo, "write-tree", index=idx).strip()
        return base, _git(repo, "commit-tree", tree, "-p", base,
                          "-m", "nox: artifact").strip()
    if target.kind == "ref":
        base = (_git(repo, "merge-base", target.base, target.ref).strip()
                if target.base else f"{target.ref}^")
        return base, target.ref
    sha = _git(repo, "stash", "create").strip()   # a real commit object; no ref
    return ("HEAD", sha) if sha else ("HEAD^", "HEAD")   # clean tree ⇒ HEAD

def _neutralize(repo: Path, commitish: str, parent: str | None = None) -> str:
    """C-1005 — THE mitigation, at the git-object level. Nothing on disk."""
    with _temp_index() as idx:                       # GIT_INDEX_FILE=<tmp>
        _git(repo, "read-tree", commitish, index=idx)
        drop = [path for mode, path in _ls_tree(repo, commitish)      # mode too
                if mode == GITLINK_MODE or _matches(path)]   # submodules by MODE
        for chunk in _batched(drop, 500):            # argv length ceiling
            _git(repo, "update-index", "--force-remove", *chunk, index=idx)
        tree = _git(repo, "write-tree", index=idx).strip()
    args = ["commit-tree", tree] + (["-p", parent] if parent else [])
    return _git(repo, *args, "-m", f"nox: neutralized {commitish}").strip()
    # The TARGET is always given `-p <synthetic base>`. Without it both ends are
    # parentless roots: `merge-base` exits 1 and `git diff <sb>...<st>` fails
    # with "no merge base", so the Codex `--base` leg dies at runtime.

def _matches(path: str) -> bool:
    parts = path.split("/")
    return (any(p in NEUTRALIZE_DIRS for p in parts)   # ALL parts, basename too
            or parts[-1] in NEUTRALIZE_FILES
            or any(fnmatch(parts[-1], g) for g in NEUTRALIZE_GLOBS))
    # `parts`, not `parts[:-1]`: a set member committed as a SYMLINK is a blob
    # whose whole path is one component (`.codex`), and `.codex` is a directory
    # name, not a file name — so excluding the basename from the directory test
    # let it through to the checkout still resolving to attacker content.
    # Gitlinks are NOT handled here: mode 160000 is matched in _neutralize,
    # because a submodule can sit at any path and carries no telltale name.
```

**Two of the neutralized names are git's own execution surfaces, and they are
the reason `_ls_tree` reports modes.** `.gitattributes` makes `worktree add`
run a configured smudge filter while materializing the tree — verified: with
`filter.evil.smudge` in the repository's config and `*.py filter=evil`
committed, the driver executed, before neutralization is observable and before
any harness starts. Dropping the file at the object level stops it, also
verified, because with no attributes in the tree no filter applies whatever
drivers exist. `.gitmodules` and every mode-`160000` entry go for the second
surface: a checkout leaves submodules unpopulated, but a shell-capable reviewer
can be induced to run `git submodule update --init`, and the nested repository
arrives carrying its own `.claude/`, `.codex/` and `AGENTS.md` — none of which
this walk ever saw, because it only covers the superproject. Verified:
`git submodule status` in the resulting worktree lists nothing.

`_matches` is the whole of the root-versus-recursive question, answered:
**by path component, at any depth, and independent of entry mode.** A root-only
rule left `src/AGENTS.md` and `packages/api/.opencode/plugins/evil.ts` in place,
and rested on an unstated invariant — cwd is always the worktree root — that any
future subdirectory-scoped review would break.

**The basename must be in the directory test, and this was got wrong once.** An
earlier revision wrote `parts[:-1]`, testing only directory components. Run
against a real fixture, that matcher dropped every nested case and **kept**
`.codex` committed as a symlink to an in-repo `docs/build/` holding a
`settings.json` with a hook — because `ls-tree` emits that entry as the single
component `.codex`, so `parts[:-1]` was empty and the basename was tested only
against the *file* set. The symlink reached the checkout and still resolved to
attacker-controlled content: Security H5's breach, arriving through the matcher
after the deletion primitive that originally carried it had been removed.
`_verify` cannot catch this class — it re-checks that *dropped* entries are
absent, and an entry never matched is never dropped.

`_verify(path)` re-checks with `os.path.lexists` that every dropped entry is
absent from the checkout and raises `IsolationError` otherwise, because a false
entry in `Containment.neutralized` corrupts the stamp the consumer weights
findings by.

Every git process — nox's **and the child's** — runs under the C-1031
`GIT_OVERRIDES` set, delivered through `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_n`
/ `GIT_CONFIG_VALUE_n` rather than as a per-call `-c`. Git hooks are not
tracked files, so an attacker's *branch* cannot plant them — but the repository
config **is shared across worktrees**, `core.hooksPath` with it, and `/dev/null`
is git's own documented kill switch
([`nox-security.md:818-822`](../research/nox-security.md)). The per-call form
covered only nox's own command lines; a `git checkout` the model is induced to
run inside the workspace inherited the shared config untouched. The environment
form binds every git in the child's process tree — verified against a separate
child process — which is the difference between hardening nox and hardening the
boundary. `core.fsmonitor=false` and `core.attributesFile=/dev/null` ride the
same set; `GIT_ATTR_NOSYSTEM=1` covers the system attributes file.

**Why not delete the files from the checkout.** That was the previous design and
it had two defects, both closed by construction here. *One:* deletions in a
checkout are that checkout's uncommitted state, so `codex exec review
--uncommitted` would have reviewed seven deleted config files while the real
change, committed at `HEAD`, stayed invisible — returning `approve` on a review
that never happened, with an accurate containment stamp. *Two:* deleting
attacker-controlled paths is not a safe primitive. `Path.is_dir()` follows
symlinks and `shutil.rmtree` refuses them, so the natural
`if p.is_dir(): shutil.rmtree(p, ignore_errors=True)` leaves a `.claude`
symlink in place while reporting it deleted. An index filter has no symlink
semantics to get wrong: a symlink is an entry with mode 120000, and a dropped
entry is never materialized. Cost: two extra commit objects per review,
unreferenced, reclaimed by `gc` — the same class of object `git stash create`
already writes.

**Unverified, and marked as such (C-1004).** The `git stash create` →
`worktree add --detach` flow is derived from documentation; the fixture that
would have proven it was blocked at a permission prompt during research. Work
package 2 builds that fixture *before* anything depends on it, and now also
proves the synthetic-pair diff. If `stash create` does not behave as specified,
the fallback is a scope cut — v1 reviews committed refs only — not a redesign;
see the ADR's risk list for why that cut is not cost-free.

### 4.2 Timeout policy derivation (C-1010)

```python
@classmethod
def for_kind(cls, kind: Liveness, wall_clock_s: int) -> TimeoutPolicy:
    silence = {
        Liveness.SEMANTIC:      120,   # structured events; 2 min silent is a hang
        Liveness.BYTE_ACTIVITY: 300,   # only bytes; be generous
        Liveness.PROCESS_ONLY:  None,  # silence carries NO information — no guess
    }[kind]
    return cls(wall_clock_s=wall_clock_s, silence_s=silence)
```

`PROCESS_ONLY` deliberately has no silence timeout. A supervisor that only
knows a PID exists cannot distinguish "thinking" from "hung", and inventing a
threshold there is how you kill a working review. All three v1 harnesses are
`SEMANTIC` — Claude Code `--output-format stream-json`, Codex `--json` JSONL,
OpenCode `--format json` — so `BYTE_ACTIVITY` and `PROCESS_ONLY` serve **zero**
v1 harnesses. The honest framing is **"three lines of code, so kept as the
extension seam"**, not "required by precedent": watchdog's lesson is about
degraded tiers in environments that *exist*
([`nox-pattern-precedent.md:21`](../research/nox-pattern-precedent.md)), and the
harness that originally generated this one — Copilot, with no documented stream
format and no exit-code table — is Out of v1. Collapsing to one silence
threshold is a legitimate plan-time simplification and is listed in the ADR's
*Deferred* table.

**What a non-semantic touch does, which was previously undefined** (C-1010):
`Heartbeat.touch(now, semantic=False)` updates `last_byte_at` and **never**
resets `last_activity_at`. The silence clock is over events, not bytes. A
harness emitting only a stack trace or a progress bar for longer than the window
is treated as silent and killed, because a review producing no events for two
minutes is a hang; the `TIMED_OUT` detail carries both timestamps so "noisy but
eventless" is distinguishable from "dead". The alternative — bytes resetting the
clock — makes the 120 s `SEMANTIC` window do nothing the 300 s `BYTE_ACTIVITY`
window would not do better, deleting the distinction the type exists to carry.

**These numbers are unmeasured engineering defaults**, and are stated as such
rather than dressed as findings: 120 s, 300 s, `grace_s = 5.0`, the 8 MiB byte
cap, the depth-20 config search bound, the ≤ 1.2 s `worktree add` figure and the
≤ 2 s total in § 8.1 all rest on judgement. The riskiest is 120 s — a large diff
under extended thinking can plausibly exceed it between stream events, and the
consequence is a working review killed and reported as `TIMED_OUT`. The contract
suites record observed inter-event gaps per harness, and the defaults are
revised from that data before release.

### 4.3 Tri-state classification (C-1011)

```python
def parse(self, lines, exit_code, hb) -> Review:
    events = [json.loads(l) for l in lines if _is_json(l)]
    if err := _first_error_event(events):
        return _error(_classify(err))       # UNAUTHENTICATED | RATE_LIMITED | ...
    if (payload := _extract_result(events)) is None:
        return _indeterminate(MALFORMED_OUTPUT)    # ← never "approve"
    try:
        return _ok(_validate(payload))
    except SchemaError:
        return _indeterminate(MALFORMED_OUTPUT)
    # exit_code is recorded, and gates NOTHING. 143 ⇒ reason=KILLED.
```

The one thing this function may never do is reach a success return by
elimination. All three harnesses put the failure kind in the stream rather than
the exit code — **observed on OpenCode** (a provider failure exited 1 with a
structured `{"type":"error"}` line,
[`nox-tech-tooling.md:18-22`](../research/nox-tech-tooling.md), the only
empirical harness observation in the research set); **documented on Claude
Code** ("prints the failure as the result on stdout", and can exit 0 with an
auth failure inside it,
[`nox-security.md:613-614`](../research/nox-security.md)); **inferred on
Codex**, from a sentence about *approval policy*
([`nox-security.md:1155-1157`](../research/nox-security.md)) that does not
itself speak to exit-code-versus-stream divergence. The contract holds on the
fail-safe direction regardless of which reading is right, and the drift
detector is what turns the inference into a behaviour.

`_classify` is **per adapter**, backed by a table of that harness's observed
error shapes (C-1012), and returns `None` where the harness does not
distinguish two states. OpenCode is the live case: its only observed error is a
generic `UnknownError`, so if authentication failure and HTTP 429 share that
name, nox stamps the raw name and resolves `indeterminate` rather than
substring-matching `data.message`, which no contract specifies and which the
harness can change on any patch release. `indeterminate` also stops the run, so
C-1021's no-retry rule is unaffected.

A parser that branches on exit code reports "review passed" on an auth failure —
the operability seat's top-ranked failure mode, and the exact class a `Popen`
mock renders invisible, because the mock encodes the belief being tested.

---

## 5. Threat model

The core of the design. Ordered by severity, each with what closes it and what
does not.

### 5.1 Assets, adversary, trust boundaries

**Assets.** The user's source tree and its git history; credentials on the
developer machine (`~/.ssh`, `~/.aws/credentials`,
`~/.claude/.credentials.json` mode 0600, `~/.codex/auth.json`,
`~/.local/share/opencode/auth.json` plain JSON); the ambient environment of the
invoking shell; the user's subscription quota; and the *review verdict itself*,
which is an asset because a user acts on it.

**Adversary.** Anyone who can get a diff in front of the user. CSA's framing
transfers directly: "an adversary who previously needed write access to a
trusted repository now needs only the ability to create an issue or pull
request" ([`nox-security.md:53`](../research/nox-security.md)). No account, no
network position, no local access required.

**Trust boundaries, in order of crossing:**

| # | Boundary | Trusted side | Untrusted side |
|---|---|---|---|
| B1 | The diff and every tracked file on the branch | nox, the user | the branch author |
| B2 | The workspace filesystem | nox's own writes | anything the checkout materialised |
| B3 | The spawned harness process | the binary's own auth | everything the model reads or emits |
| B4 | The review text returned | — | **all of it**; it is model output shaped by B1 |
| B5 | `nox.toml` reached by upward search | the user's config dir | anything inside the repo |

nox's architecture is: make B2 disposable, make B3 unable to reach past the
workspace, and never let B4 be mistaken for authority.

### 5.2 T1 — repo-supplied configuration executes at harness startup

**Severity: critical. This is the finding the ADR reverses a settled
constraint for, and it is the axis on which the three harnesses differ most.**

The evidence table is in the ADR (§ Context, *The three-way asymmetry*), taken
from [`nox-security.md:1206-1242`](../research/nox-security.md). Per harness:

**Claude Code — fails open.** Trust verification is *disabled* under `-p`
([`nox-security.md:203`](../research/nox-security.md)), and the documented
per-content table for "folder never trusted" reads:

| Repository-supplied content | Under `claude -p` |
|---|---|
| Hooks in settings files, the `env` block, `apiKeyHelper`, a project skill's hooks and `allowed-tools` | **Used.** "Workspace trust never gates a skill's `allowed-tools` in any session" |
| Servers in `.mcp.json` | **Connected without asking, approved or not.** |

`--restricted` closes settings-file hooks but explicitly *not* `.mcp.json`
(its own help text instructs adding `--strict-mcp-config`), and says nothing
about project skills, whose frontmatter hooks register on invocation
"including in a `-p` run in a folder you haven't trusted". `--safe-mode` is the
only flag naming skills, plugins, hooks, MCP servers and custom agents
together — and it is `--help`-only, absent from code.claude.com, untested
against `-p`. `--bare` is denied outright (C-1023): it forces API-key auth.

**Codex — fails closed, then leaks in two named places.** Verbatim: "Codex
loads project-scoped config files only when the project is trusted. If the
project is untrusted, Codex ignores project `.codex/` layers". It additionally
blocks credential-redirecting keys (`openai_base_url`, `model_providers`,
`notify`, `profile`, …) in project config *regardless of trust* — a designed
defence neither of the other two has. But:

1. **Project trust is scoped to a path, not a commit.** The user's own
   repository is already trusted, so a hostile branch checked out into that
   path inherits trust. The gate defends against a hostile *repository*; nox's
   threat is a hostile *branch in a trusted repository*
   ([`nox-security.md:1044-1050`](../research/nox-security.md)).
2. **`mcp_servers` is not on the blocked-keys list, and there is no
   `--strict-mcp-config` analogue** on `codex`, `codex exec`, or `codex exec
   review`. A stdio MCP entry spawns a command. The only candidate lever,
   `-c mcp_servers={}`, is explicitly untested and its table merge-versus-
   replace semantics undocumented.

What saves Codex on the hook path is the *second* gate: hook trust is recorded
against the hook's **current hash**, so "new or changed hooks are marked for
review and skipped until trusted", and untrusted hooks are skipped
non-interactively ([`nox-security.md:1086-1090`](../research/nox-security.md)).
An attacker's branch editing `.codex/hooks.json` changes the hash → skipped.
**This is the structural defence path-scoped trust cannot give, and
`--dangerously-bypass-hook-trust` turns it off — which is why C-1023 both
never emits it and hard-errors on it.**

**OpenCode — fails open, with no mitigation at all.** Files in
`.opencode/plugins/` "are automatically loaded at startup" without explicit
approval; a plugin is a JS/TS module whose context provides "an AI client,
**shell execution via Bun's API**, and directory information", and can
"intercept tool execution, modify behavior, add custom tools". **The
documentation names no flag, setting, or mechanism to disable plugin loading**
([`nox-security.md:908-916`](../research/nox-security.md)). Additionally
`.opencode/agents/*.md` are repo-supplied, carry permissions in frontmatter,
and "agent rules take precedence" — so the repository can supply the very agent
nox names on `--agent`.

**What closes it, on all three:** deleting the neutralization set from a tree
nox owns (C-1005). One control, three harnesses, no flag names in it. For
Codex specifically this converts a *stated accepted residual* into a deleted
file: `.codex/config.toml` is where repo MCP servers would be declared, and it
is gone before the process starts.

**A welcome side effect, deliberately not load-bearing.** The workspace is a
fresh path, and Codex's project trust is path-scoped, so its project `.codex/`
layer is plausibly untrusted there and Codex's own fail-closed gate engages on
top of the deletion. How trust is actually granted is the research's own
highest-value open question
([`nox-security.md:1261-1270`](../research/nox-security.md)), so this is
recorded as a bonus. **The deletion does not depend on it.**

**Residual:** managed (MDM) settings on Claude Code — "no other level,
including command line arguments, can override a managed permission rule". Note
the inversion: on Codex, CLI flags win outright over project config. Two
harnesses with opposite precedence rules is one more reason the boundary lives
in the workspace rather than in a flag.

### 5.3 T2 — the model reads credentials outside the workspace

**Severity: high.** The workspace is not a filesystem boundary. Claude Code's
OS sandbox — off by default, silently degrading when unavailable, absent on
native Windows — has a default read policy of "read access to the entire
computer… this default still allows reading credential files such as
`~/.aws/credentials` and `~/.ssh/`"
([`nox-security.md:191-195`](../research/nox-security.md)). Its read-only Bash
command set is not configurable and not empty: `cat`, `head`, `find`, `grep`,
read-only `git` run without a prompt **in every mode, including `dontAsk`**.

**What closes it** differs per harness, and C-1007's `ContainmentPlan` is the
type that keeps the difference visible:

- **Claude Code — tool removal.** A bare tool name in a deny rule "removes the
  tool from Claude's context entirely, so Claude never sees it", while a scoped
  rule leaves it available; Anthropic's own warning is that
  argument-constraining Bash patterns are defeated by options-before-URL,
  protocol change, `-L` redirect, a shell variable, or an extra space
  ([`nox-security.md:162-176`](../research/nox-security.md)). So
  `--tools "Read,Grep,Glob"`, not a denylist. Saltzer & Schroeder settle the
  general form: "base access decisions on permission rather than exclusion."
- **Codex — OS sandbox.** `read-only` mode via Seatbelt (macOS), Landlock +
  seccomp (Linux; blocks `connect`, `bind`, `sendto`, with **`AF_UNIX`
  exempted**), or a restricted token (Windows, denying `.git`). On by default
  and network-denying by default — strictly stronger than Claude Code's opt-in
  sandbox for the vector it covers, and the platform mechanisms are
  secondary-sourced ([`nox-security.md:1130-1138`](../research/nox-security.md)).
  **The `AF_UNIX` exemption is a real hole and is not closed here.** Reachable
  Unix sockets on a developer machine routinely include the Docker daemon
  socket, an SSH agent, gpg-agent and local HTTP proxies; a model-generated
  command reaching `/var/run/docker.sock` is root on the host and unrestricted
  egress in one step, and reaching the SSH agent is a signing oracle. Two things
  bound it, and both are now deliberate rather than incidental: `SSH_AUTH_SOCK`
  is **excluded from C-1008 on purpose**, so the child cannot find the agent,
  and Landlock read-only denies filesystem writes, which *plausibly* blocks
  connecting to a socket file. Plausibly is not verified, and the §5.8 residual
  says so.
- **Reads are not denied on the Codex leg, and that has a second consequence.**
  Landlock read-only denies writes and network, not reads, so a model-generated
  command can read `~/.aws/credentials`, `~/.ssh/id_ed25519` or
  `~/.claude/.credentials.json`. Egress is cut at the socket, subject to the
  paragraph above — but **the review text is an egress channel by definition,
  because a human reads it.** `Review.raw` therefore carries whatever the child
  read, and C-1018 makes persistence a separate question from trust: the call
  log never carries `raw`, credential shapes in `raw` set
  `Containment.secrets_suspected` rather than being silently redacted, and a
  consumer folding review text into a committed artifact must review it first.
- **OpenCode — config deny.** `OPENCODE_CONFIG_CONTENT` inline denying
  `bash`/`edit`/`write`/`webfetch`/`websearch`. That deny map is the whole
  mechanism; `--pure` is the only argv-visible word, carried as a derivation
  tripwire rather than a second enforcement layer. An earlier revision also
  named `--agent explore` here as a built-in agent that "Cannot modify files".
  **It is deliberately not emitted**: on 1.18.22 `explore` is a *subagent*, so
  the flag is accepted syntactically, silently discarded, and the run proceeds
  under `build` — opencode's default **read-write** agent. Emitting it would put
  a containment word on argv that a derivation rule could corroborate over a
  read-write run, which is strictly worse than leaving it off (plan **E51**).

**Residual, stated:** OpenCode's enforcement is a config-file convention, not a
documented harness-level gate, with one report of `"git": "deny"` being ignored
and closed as not planned
([anomalyco/opencode#8832](https://github.com/anomalyco/opencode/issues/8832)).
This is exactly why `ENFORCED_READ_ONLY` is a capability OpenCode does **not**
hold and why its absence is stamped into every `Containment` record.

### 5.4 T3 — the harness reaches the real repository through shared refs

**Severity: high, and specific to the worktree decision.** A worktree shares
the object store and "all refs starting with `refs/`". A harness that can run
shell *inside* the workspace can therefore `git commit`, `git branch`,
`git push` against the user's actual repository — the disposable checkout buys
nothing against it.

**What closes it:** the same containment plan as T2, which is why C-1007 is a
launch precondition rather than a preference: `write_enforcement` must be
established before an argv is built. Note the three mechanisms close it in
genuinely different ways — Claude Code by having no shell at all (`harness`),
Codex by Landlock write-denial (`os`; inside writable roots `.git` and `.codex`
are read-only subpaths, and Windows denies `.git` outright), OpenCode by a
denied `bash` permission whose enforcement is unproven (`attested`). **This
threat is why the OpenCode adapter's weaker guarantee has to be visible in the
envelope under its own name rather than averaged into a boolean** — the previous
`no_repo_write: bool` reported all three as `True`, which is exactly how a
capability declaration becomes load-bearing on containment. nox's own git
invocations also pass `-c core.hooksPath=/dev/null`.

### 5.5 T4 — credential leak through the inherited environment

**Severity: high.** `subprocess` inherits the parent environment by default;
CPython is explicit that `env=` replaces rather than augments it. A developer
shell routinely carries `AWS_*`, `GITHUB_TOKEN`, `NPM_TOKEN`, `PYPI_TOKEN`,
`DATABASE_URL`, `STRIPE_*` and whatever `.envrc` sourced. Anthropic ships
`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` for the same problem one level down —
evidence the vendor considers it real.

**What closes it:** the C-1008 allowlist plus credential-pattern denylist.
**The design constraint that matters is the failure mode, not the list:**
dropping a credential degrades safely, while dropping an infrastructure
variable fails loudly and confusingly — `HOME` missing means auth silently
fails and the harness looks logged out; `HTTPS_PROXY` missing means every API
call fails behind a corporate proxy; `SSL_CERT_FILE` missing means TLS
verification failures. Users respond to confusing failures by disabling
scrubbing entirely, so a missing infrastructure variable must raise a
nox-authored error *naming the variable*
([`nox-security.md:365-368`](../research/nox-security.md)). Three
harness-specific variables must survive: `CLAUDE_CONFIG_DIR`, `CODEX_HOME`,
`OPENCODE_AUTH_JSON`.

**Also closed for free by the workspace:** an untracked `.env` or `.envrc`
never reaches the checkout, and OpenCode reads a project-local `.env` for
provider keys. A *tracked* `.env` is in the neutralization set for the same
reason: `opencode.json` can define a provider with a custom `baseURL`, which
would redirect the entire diff to an attacker-chosen endpoint. (Codex blocks
the equivalent keys by design — `openai_base_url`, `model_providers` — which is
the one place a v1 harness protects this vector without nox's help.)

### 5.5b T4b — the environment as an *inbound* channel

**Severity: high, and it did not exist in the first draft of this model.** T4 is
entirely about credentials leaking outward. There was no counterpart for
attacker *values* arriving inward, and the C-1008 allowlist forwards exactly the
variables that would carry one: `HOME`, `PATH`, `XDG_CONFIG_HOME`,
`XDG_DATA_HOME`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `OPENCODE_AUTH_JSON`.

**The attack needs no privilege and no unusual behaviour from the user.** They
check out the PR branch to look at it — the ordinary first step before asking
for a review. direnv or mise sources the branch's `.envrc` or `mise.toml` **in
their own shell**, which is the entire point of those tools and the reason both
files are in the neutralization set. The branch sets `CODEX_HOME=/tmp/x`. The
user runs nox. C-1008 forwards `CODEX_HOME` because the harness legitimately
needs it for auth. Codex then reads `/tmp/x/hooks.json` — attacker-authored
hooks — *and* `/tmp/x`'s trust store, which the attacker also authored, so the
content-hash gate the entire Codex safety case rests on
([`nox-security.md:1086-1090`](../research/nox-security.md)) blesses them.
`--ignore-user-config` does not help: it kills `$CODEX_HOME/config.toml`, not
`$CODEX_HOME/hooks.json`. The same shape applies to `CLAUDE_CONFIG_DIR`, to
`OPENCODE_AUTH_JSON`, and in its strongest form to `HOME`.

**Deleting `.envrc` and `mise.toml` from the worktree does nothing against
this.** The export happened in the parent shell, in the user's real tree, before
nox was invoked. The neutralization set creates the appearance of covering this
vector while covering only the copy nobody reads — which is exactly why it needs
its own row rather than being folded into T1.

**What closes it (C-1008):** for `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`,
`CLAUDE_CONFIG_DIR`, `CODEX_HOME` and `OPENCODE_AUTH_JSON`, nox resolves the
value and **refuses to forward it if it resolves inside the repository under
review**; a value under a world-writable directory is forwarded with a warning
carried in the review envelope. The allowlist's exclusions are also written down
in the contract so they survive a future ergonomics patch — `NODE_OPTIONS`
(`--require` injects into any Node harness, which is two of the three),
`BUN_*`, `LD_PRELOAD`, `PYTHONSTARTUP`, `GIT_SSH_COMMAND`, `GIT_EXTERNAL_DIFF`
and `SSH_AUTH_SOCK`.

**Residual:** `PATH` is forwarded verbatim. Relative entries would resolve
against the child's cwd, which is the attacker's worktree. In practice direnv
and mise export absolute paths into the user's *real* tree, so this needs a
pre-existing relative `PATH` entry to bite; sanitizing it is cheap hardening
deferred to `/hex-plan`.

### 5.6 T5 — the review text attacks the user

**Severity: medium, and no permission flag touches it.** A diff that induces
the adversary to emit "this diff is clean", or a confident wrong finding that
sends the user to change unrelated code, is an attack on B4
([`nox-security.md:115-119`](../research/nox-security.md)). Under Willison's
lethal trifecta the tractable leg to cut is external communication — and nox
cuts it mechanically on all three harnesses (no WebFetch/WebSearch, no MCP, no
network) — but the review output *is* an egress channel, because a human reads
it. `AGENTS.md` is the purest instance: repo-supplied, steers the model,
executes nothing, and has **no documented off-switch on either Codex or
OpenCode** — which is why it is deleted rather than argued with.

**What closes it:** nothing, structurally. What is done instead: nox never
presents adversary output as authoritative (C-1019); the `Containment` stamp
travels with every review so the consumer can weight it; hex's adversary
contract already frames this correctly as one-shot, triaged, and a gate rather
than a blocker. nox's own docs state the limit rather than implying safety.

### 5.7 T6 — denial of service against nox itself

**Severity: low.** A malicious `nox.toml` in the tree under review with a
malformed `read_only` value would, under a naive fail-hard rule, prevent nox
from ever running — and a review that never runs is a review that never objects
([`nox-security.md:661-666`](../research/nox-security.md)).

**What closes it:** C-1017's architecture, not C-1016's parser. Permission keys
from an untrusted repo-local file are *dropped with a warning*, never aborted
on, because nox's own defaults are the restrictive ones — dropping *is* the
fail-closed direction. Fail-hard applies to permission values in a **trusted**
config, where the user expressed an intent about the boundary and nox cannot
read it; there, every possible default is a guess about a security control
(CWE-1188). Note that nox's trust is keyed on **path plus content hash**,
deliberately taking Codex's hook-trust model rather than Codex's project-trust
model — because § 5.2 is a live demonstration of what path-scoped trust costs.

**And the order of the two rules is the whole of it.** The first draft of the
component flow listed malformed-value validation *before* the trust drop, which
reopens T6 completely: `read_only = "yes"` in a hostile repo `nox.toml` is a
malformed value on a permission key, so `ConfigError` fires and nox never runs,
and the two sections arguing for drop-not-abort are bypassed by a parser that
ran first. **Drop first, validate what survives.** A malformed permission value
in an untrusted repo-local file is dropped with a warning and never raises. The
residual for T6 is therefore not "none known" — it is **"none known, and
conditional on this ordering"**, which is why the ordering is in the contract
text and in the flow diagram rather than left to the implementer.

### 5.8 Threat summary

| ID | Threat | Closed by | Residual |
|---|---|---|---|
| T1 | repo-supplied config executes at startup | object-level neutralization + workspace (C-1003/5), applied at any depth, and applied to the **probe** as well as the review (C-1014) | managed MDM settings (Claude Code only) |
| **T1b** | **git itself executes branch-controlled code, before any harness** | `.gitattributes` dropped at the object level, so no smudge filter applies during `worktree add` (C-1005, verified); `.gitmodules` and every mode-`160000` entry dropped, so a submodule cannot be mounted to import a nested harness config; `core.hooksPath`, `core.fsmonitor` and `core.attributesFile` forced for **every** git in the child's process tree via `GIT_CONFIG_*` (C-1031) | `$GIT_DIR/info/attributes` and the shared `$GIT_DIR/config` are not branch-controlled — a hostile value there means the machine was already compromised. Not closed, and not nox's boundary |
| T2 | model reads `~/.ssh`, `~/.aws` | per-harness containment plan (C-1007) | OpenCode's is `attested`, not enforced → stamped, not claimed. **Codex denies writes and network, not reads**, so what the child reads reaches the user through `raw` (C-1018) |
| T3 | harness reaches shared `refs/` and objects | both enforcement axes as a launch precondition, derived from argv (C-1007, C-1025) | same as T2. OpenCode's `attested` write level is the only thing between it and the user's git history |
| T4 | credential leak via inherited env (outbound) | env allowlist + credential denylist (C-1008) | each harness's own auth path, which must survive |
| **T4b** | **attacker values arrive via the env (inbound)** | reject harness-config-path variables resolving inside the repo; written-down exclusion list (C-1008, § 5.5b) | `PATH` forwarded verbatim; relative entries would resolve in the worktree. Needs a pre-existing relative entry to bite; sanitization deferred |
| T5 | review text attacks the user | nothing structural — C-1019 posture, plus C-1018's persistence rules | inherent; stated, not hidden |
| T6 | malformed repo config denies the review | drop-not-abort for untrusted keys (C-1017) | none known, **conditional on drop-before-validate ordering** (§ 5.7) |
| **T2/T3 network** | **egress from inside the workspace** | tool removal (Claude Code), OS sandbox (Codex), config deny (OpenCode) | **not uniform, and not closed.** Claude Code's is enumeration-derived — a tool the adapter fails to account for, or a new built-in, restores egress, and no OS sandbox sits beneath it. Codex's seccomp filter is **`AF_INET`-scoped, `AF_UNIX` exempted**, and whether Landlock incidentally blocks socket connection is **unverified**. OpenCode's is `attested` |

**Three independent controls, each covering what the others do not:** the
workspace covers repo-supplied execution (T1) and untracked credentials (T4a);
the containment plan covers filesystem reach (T2) and shared refs (T3); the
environment allowlist covers ambient credentials (T4) and inbound values (T4b).
No single one is sufficient, and the ADR's rejection of Options A, B and D is
exactly the observation that each ships one or two of the three.

**Two rows deliberately do not read as closed.** T2/T3-network and T2's read
leg are recorded as open because the earlier version of this table showed the
network threat closed for Codex on the strength of a mechanism whose own
description exempts `AF_UNIX`, and closed for Claude Code on the strength of an
enumeration. The § 9.5 churn table's claim that removing a containment flag
"degrades, does not vanish" is true for T1, where the workspace holds
independently — and false for network, where the workspace provides nothing.

---

## 6. Per-harness invocation

### 6.1 Claude Code (verified against local v2.1.252 `--help`)

| Concern | Flag | Note |
|---|---|---|
| headless | `-p` / `--print` | trust verification disabled in this mode — the reason T1 exists |
| stream | `--output-format stream-json` | `SEMANTIC` heartbeat |
| schema | `--json-schema <schema>` | `STRUCTURED_OUTPUT`; the harness validates |
| containment | `--tools Read,Grep,Glob` | `tool-removal`; removes Bash and with it the non-configurable read-only command set and all network reach. **Comma-joined, not space-separated** — `--tools <tools...>` is variadic, so a space-separated list swallows the next argv word and the evidence run is the tail of the argv |
| perms | `--permission-prompts none` | "anything that would prompt is denied automatically". **Never `--permission-mode dontAsk`**: that rested on "default for `-p` is Manual, which blocks forever on a prompt that never arrives", and at 2.1.259 the premise is false — `permissionMode` is `default` in every observed run and no `--permission-mode` value is narrower than it, `dontAsk` least of all, since it names auto-approval. `--permission-mode` is in `harness.NEVER_EMITTED` (plan **E52**) |
| config | `--safe-mode --restricted --strict-mcp-config` | defense in depth under Option C; **not** the boundary |
| model | `--model <literal>` (+ `--effort <level>`) | `MODEL_SELECTION`. Both emitted from the adapter's `MODELS[class]` entry, never from config argv (C-1030) |
| cost | `total_cost_usd` in the JSON result | `COST_REPORTING`; `--max-budget-usd` available |
| **passthrough** | allowlist = **empty** | C-1023. Everything else refused, including `--settings`, `--setting-sources`, `--mcp-config`, `--agents`, `--plugin-dir`, `--tools`, `--permission-mode`. **`--settings` is the one that matters**: `--restricted`'s own help text says managed settings and `--settings` *still apply*, so `--settings '{"hooks":{"SessionStart":[…]}}'` is arbitrary command execution surviving the whole flag stack. A denylist of six flag names caught none of these |
| **never emitted** | `--bare`, `--add-dir`, `--dangerously-skip-permissions` | C-1023's re-scoped `DENIED_FLAGS`, asserted against nox's own argv |

### 6.2 Codex (verified against local `codex-cli 0.144.1` `--help`)

| Concern | Mechanism | Note |
|---|---|---|
| headless | `codex exec review` | non-experimental; **not** `app-server`, which is `[experimental]` with undocumented trust behaviour (C-1024) |
| stream | `--json` | JSONL; `SEMANTIC` |
| schema | `--output-schema` | `STRUCTURED_OUTPUT` |
| target | **`--base refs/nox/base/<token>`** — never `--uncommitted`, never a raw SHA | C-1005's workspace has **no uncommitted state**, so `--uncommitted` would review nothing. It would previously have reviewed nox's own housekeeping: with an on-disk `rm`, the deletion of seven tracked config files *was* the worktree's uncommitted state, and the real change, committed at `HEAD`, was invisible — `approve` on a review that never happened. Object-level neutralization makes Codex's self-collected diff identical to `<scratch>/review.diff` by construction, so the two cannot disagree. **A temporary ref, not a raw SHA — the help documents `<BRANCH>`.** `refs/nox/base/<token>` is created in `prepare()` pointing at the synthetic base and deleted in the teardown `finally`; it cannot collide with a user branch and never appears in `git branch`. Making the ref primary rather than a fallback removes an open rollout item instead of promoting one: raw-SHA acceptance is now an optional optimization a contract test may prove. **Ancestry is still required:** the synthetic target is committed with `-p <synthetic base>` (C-1005), so `merge-base` resolves whichever diff convention this flag uses. Without the parent both ends are roots and `--base` fails with "no merge base" — a runtime failure on this leg only, invisible to nox's own two-dot `review.diff` |
| containment | `-c sandbox_mode=read-only` | `os-sandbox`. **`codex exec review` has no `-s/--sandbox` and no `-a/--ask-for-approval`** — the verified option list omits both, so the mode must go through `-c`, and the key name is *inferred*. Rollout gate; until a probe passes, C-1025 cannot derive `write_enforcement="os"` and C-1007 refuses to launch |
| config | `--ephemeral --strict-config --ignore-rules --ignore-user-config` | defense in depth. `--strict-config` is also the cheap half of the rollout gate: if it rejects unknown keys as its name implies, one invocation settles the *key name*. Proving the mode **takes effect** is a fixture — a write attempt and a network attempt observed to fail — not one command |
| model | `-m/--model <literal>`; effort via `-c model_reasoning_effort=<level>` | `MODEL_SELECTION`. **The effort knob rides `-c`, which passthrough refuses unconditionally** — so it is emitted by the adapter from a typed `MODELS[class]` entry, never from a config-supplied argv fragment. Permitting the latter would reopen the `-c` hole through the back door (C-1030) |
| **passthrough** | allowlist = `{--title}` | C-1023. **`-c/--config` is refused unconditionally and can never be allowlisted**, which is the single most important line in this table: `codex exec review --help` documents `-c <key=value>` with its own examples being a sandbox-permission widening and `shell_environment_policy.inherit=all`, so `-c sandbox_mode=danger-full-access` disables the OS sandbox by last-wins, `-c mcp_servers={…}` re-declares the servers C-1005 removes, and `-c shell_environment_policy.inherit=all` undoes the C-1008 scrub from inside the child. nox emits its own `-c` **last** |
| **never emitted** | `--dangerously-bypass-hook-trust`, `--dangerously-bypass-approvals-and-sandbox` | The first disables content-hashed hook trust — the *only* thing standing between a hostile branch and Codex's `SessionStart` hooks |

Two Codex properties have no analogue in the other two and are worth naming:
CLI flags outrank project config (the inverse of Claude Code's managed-settings
precedence), and project config cannot override credential-redirecting keys.
Both are in nox's favour; neither is depended on. Note that the first is also
what makes an allowlisted `passthrough` and a stated argv ordering load-bearing
here rather than cosmetic.

**Checked after the research closed:** Codex "Agent Plugins" (v0.146.0,
2026-07-29) postdate the 0.144.1 probe this table rests on. They require an
explicit `codex plugins install <dir>` rather than project-directory
auto-discovery, so no new path enters the C-1005 set. Recorded because the set
is a shipped literal whose staleness is the standing maintenance cost (§ 9.5).

### 6.3 OpenCode (`--help` probed live at 1.18.22; security findings docs-only)

**Two lanes, two confidence levels, and the difference matters.** The tech lane
ran a live `--help` behind `ocx package exec`
([`nox-tech-tooling.md:7`](../research/nox-tech-tooling.md)), which is where the
flag names below come from. The **security** lane had no binary at all —
"OpenCode is not installed on this machine … all OpenCode findings are
documentation and issue-tracker only. In particular I could not verify the
config-precedence claim that a project `opencode.json` overrides
`OPENCODE_CONFIG`, which is load-bearing"
([`nox-security.md:727-731`](../research/nox-security.md)). Both statements are
true of different lanes, and an earlier revision of this document read as
self-contradictory because it said neither.

| Concern | Mechanism | Note |
|---|---|---|
| headless | `opencode run [message..]` | **no `-p`** — that is the server password flag; the message is positional |
| stream | `--format json` | one JSON event per line; `SEMANTIC` |
| schema | — | no schema flag; nox extracts a fenced block, `indeterminate` on failure |
| containment | `OPENCODE_CONFIG_CONTENT` inline (the deny map) + `--pure` on argv | `config-deny`, and **both enforcement axes are `attested`**, not `harness` — the deny map's resolution order was never observed, only its presence in the resolved rule list, so neither axis can ever be `harness` or `os`. `--agent explore` is **not** emitted; `explore` is a subagent on 1.18.22 and the run falls back to the default read-write `build` agent (plan **E51**). **Never `OPENCODE_CONFIG`** — a project `opencode.json` is reported to outrank it, and only the inline form is reported to outrank the project file. *That precedence claim is explicitly unverified* ([`nox-security.md:727-731`](../research/nox-security.md)); under C-1005 it is not load-bearing, because `opencode.json` is filtered out of the objects before checkout |
| model | `-m provider/model` | `MODEL_SELECTION`; nox's widest cross-model leg. **The literal must carry the `provider/` prefix**, and `probe()` runs `opencode providers list` as a preflight — confirmed live-safe, reporting `0 credentials` without prompting or blocking ([`nox-tech-tooling.md:32`](../research/nox-tech-tooling.md)). An unconfigured provider is `UNAUTHENTICATED`, not a mid-review crash. **No effort knob exists**, being BYOK and provider-specific, so `MODELS[class]` is a bare literal here (C-1030). nox does not forward `OPENCODE_<PROVIDER>_APIKEY` — it is not on the C-1008 allowlist, so OpenCode authenticates from its own store, which is C-1002 working as intended |
| **passthrough** | allowlist = **empty** | C-1023. The model flag is emitted by the adapter from `MODELS[class]` (C-1030), and rule 3 refuses any duplicate of a nox-owned flag — so listing it here would contradict rule 1 |
| **never emitted** | `--auto` | "auto-approve permissions that are not explicitly denied (dangerous!)" |

Under C-1005 the checkout never contains `.opencode/` or `opencode.json`, so the
config-precedence problem is *moot* by the time OpenCode starts.
`OPENCODE_CONFIG_CONTENT` is retained because it costs nothing and covers the
case where neutralization under-matches: OpenCode's own docs disagree on
`.opencode/plugins/` versus `.opencode/plugin/` and `.opencode/agents/` versus
`.opencode/agent/`, unresolved because OpenCode was not installed on the
security lane's machine
([`nox-security.md:956-960`](../research/nox-security.md)). **Hence the
neutralization set drops `.opencode/` and `.codex/` wholesale rather than by
named subdirectory — and, since the fix pass, by path component at any depth,
so `packages/api/.opencode/` goes too.**

**The probe is the sharp edge on this harness.** OpenCode executes
`.opencode/plugins/` at startup, and a `--version`-class invocation is a
startup, so C-1014's probe would have executed attacker JavaScript with Bun
shell access in the user's live tree — before the workspace existed, with the
full ambient environment. That is why the probe now runs with `cwd` set to a
fresh empty temp directory and the C-1008 environment, and why the § 9.4 fixture
asserts non-execution during the probe as well as the review.

---

## 7. Failure modes and the degrade ladder

### 7.1 Failure-mode table

| Symptom | `status` | `reason` | Detection | Behaviour |
|---|---|---|---|---|
| binary not on PATH and no launcher | error | `ABSENT` | probe raises | consumer degrades to graceful skip |
| binary present, not logged in | error | `UNAUTHENTICATED` | **per adapter — see § 7.1a**, never the exit code | report; never retry a refresh loop |
| quota exhausted / 429 | error | `RATE_LIMITED` | **per adapter — see § 7.1a** | **stop**; the documented lockout tail is 26+ days |
| ran, output unparseable | **indeterminate** | `MALFORMED_OUTPUT` | schema/extraction failure | surface `raw`; never "approve" |
| wall clock exceeded | error | `TIMED_OUT` | `supervise` deadline | SIGTERM→SIGKILL group; partial `raw` kept |
| silence exceeded (kind-derived) | error | `TIMED_OUT` | `supervise` silence check | as above; never applied at `PROCESS_ONLY` |
| exit 143 | error | `KILLED` | exit code | labelled "we killed it", never generic failure |
| worktree add/remove failed, **or the prompt file was tampered with** | error | `ISOLATION_FAILED` | `IsolationError` | **no harness is spawned**; distinct from a failed review. The second shape is new with the stdin channel (E29): `runner._open_prompt` refuses a symlink or a non-regular file at `<scratch>/prompt.md`, which `adapter.sandbox_probe` — a real harness, spawned into this workspace between the write and the read — is in a position to plant. It is `IsolationError` and not the bare `OSError` the open raises, because `api._spawn` maps every `OSError` to `ABSENT`, and a detected tamper reported as "the harness is not installed" is a silent no-review |
| containment plan incomplete (either axis `None`) | error | `UNSUPPORTED` | `prepare()` raises | no launch; names the missing axis |
| capability in `REQUIRED` missing | error | `UNSUPPORTED` | `prepare()` raises | no launch; names the capability |
| refused `passthrough` element | error | `INVALID_CONFIG` | `ConfigError` | no launch; names the element and why (C-1023) |
| malformed permission value in a **trusted** config | error | `INVALID_CONFIG` | `ConfigError` | no launch. An **untrusted** repo-local file never reaches here: the key is dropped first (C-1017, § 5.7) |
| `plan-artifact` path missing or outside repo | error | `INVALID_CONFIG` | `ConfigError` | no launch; never a review of an absent artifact (C-1027) |
| diff too large for this harness's prompt CHANNEL | error | `INVALID_CONFIG` | `argv_prompt` raises `ConfigError` inside `prepare()` | no launch. **Reachable only on `copilot` and `opencode`** — the two shapes whose prompt is an argv word, where the kernel's `MAX_ARG_STRLEN` binds. `claude` and `codex` read the prompt from stdin and have no such limit, so the same review runs there (C-1028, E29). Loud, never a trim: the anti-injection framing is at the END of the prompt. The message names the channel, the kernel limit and the stdin harnesses, because the configuration is not what was refused |
| untracked files in the target, **not materialized** | ok | — | `git ls-files --others` minus what step (4a) materialized | review runs; `Containment.omitted` non-empty; **`verdict` may not be `approve`**; nox appends a `high` finding with `origin="nox"` naming the paths (C-1026). A `plan-artifact` review has `omitted == ()` — its artifact is untracked but materialized, and an unconditional check made every such review refuse `approve` while accusing the document under review |
| adapter version mismatch *(modifier, not an outcome)* | unchanged | unchanged | `verified_against` ≠ probed | warn "untested against vX", continue |
| output > 8 MiB *(modifier, not an outcome)* | unchanged | unchanged | byte cap | `truncated=True`; `indeterminate` if the JSON did not survive |

`reason` is non-`None` **iff** `status != "ok"`, and the table now honours it:
the four `ConfigError` rows carry `INVALID_CONFIG`, which exists because they
previously produced `status=error` with no enum member to carry, so a consumer
writing `match review.reason:` over every non-ok review fell through to
"unknown failure" and lost the one fact the user needed. The last two rows are
**modifiers** — they do not set a status of their own, and the `(any)` in the
earlier version read as `status != ok` with `reason = None`.

The rows that carry the design are `MALFORMED_OUTPUT` → **indeterminate**,
`ISOLATION_FAILED` → **no spawn**, the two `UNSUPPORTED` rows → **no spawn**,
and the untracked row → **never `approve`**. Everything else is bookkeeping. In
particular, an unresolved Codex `sandbox_mode` key yields a refusal, never a
silent unsandboxed run — **and that is now structural rather than procedural**,
because C-1025 derives the enforcement level from a cached probe result instead
of reading a literal an implementer wrote. Under the previous shape, a developer
writing `no_repo_write=True` next to the `-c sandbox_mode=read-only` argv passed
every unit test, every contract test and the § 9.4 fixture, while Codex ran at
its default posture and the envelope stamped `enforced_read_only=True`.

Every row above returns a `Review`. `review()` never raises (C-1029); the
raising happens inside, and the boundary converts it.

### 7.1a Per-adapter failure classification

The two rows above previously read as universal stream-event detection on all
three harnesses. They are not universal, and writing them that way let an
adapter claim a distinction the research never observed — while C-1012 in the
ADR already said the opposite for OpenCode. **No adapter may claim a
distinction the evidence does not support.** One row per adapter × state:

| Adapter | State | Observed shape | Resolution | Fixture required |
|---|---|---|---|---|
| claude | `UNAUTHENTICATED` | documented, not observed: the failure is printed "as the result on stdout" and the run can exit 0 ([`nox-security.md:613-614`](../research/nox-security.md)) | `UNAUTHENTICATED` when the result payload carries an auth error; otherwise `indeterminate` | yes — recorded stream from a logged-out binary |
| claude | `RATE_LIMITED` | **not observed** | `indeterminate`, raw error name stamped, until a recorded shape exists | yes, before the distinction may be claimed |
| codex | `UNAUTHENTICATED` | **not observed** — the ADR's only citation here is about *approval policy* | `indeterminate`, stamped | yes, before the distinction may be claimed |
| codex | `RATE_LIMITED` | **not observed** | `indeterminate`, stamped | yes, before the distinction may be claimed |
| opencode | `UNAUTHENTICATED` | only `{"name":"UnknownError","data":{"message":…}}` from a *provider-resolution* failure ([`nox-tech-tooling.md:18-22`](../research/nox-tech-tooling.md)) | `indeterminate` — the name does not separate auth from quota, and substring-matching `data.message` is not a contract | n/a until the harness distinguishes them |
| opencode | `RATE_LIMITED` | as above | `indeterminate` | n/a |

**Every cell resolving `indeterminate` still stops the run**, so C-1021's
never-retry-a-refresh-loop rule holds regardless: the tri-state fails toward
not-retrying, which is the safe side of the 26-day lockout tail. A cell is
promoted from `indeterminate` to a named `FailureReason` only when a recorded
fixture of that harness's actual output exists — which is what makes C-1020's
contract suite the thing that grows this table, rather than an implementer's
guess. A consumer implementing the old universal rows literally would have
misclassified a provider failure as `malformed_output`, or claimed an auth
classification on Codex that nothing supports.

### 7.2 Degrade ladder

```
full            worktree · neutralized · containment asserted · env scrubbed ·
  │             schema-validated                    ← Claude Code / Codex, healthy
  ▼
no schema       as above, fenced-block extraction instead   ← OpenCode, healthy
  │             STRUCTURED_OUTPUT absent, stamped
  ▼
no enforcement  as above, ENFORCED_READ_ONLY absent and both enforcement
  │             axes = "attested", stamped in Containment  ← OpenCode, always
  ▼
incomplete      as above, Containment.omitted non-empty → verdict may NOT be
  │             approve; nox's own `high` finding names the paths   (C-1026)
  ▼
indeterminate   ran, unclassifiable → raw surfaced, verdict null. Also where a
  │             harness cannot distinguish two failure states       (C-1012)
  ▼
skip            probe raised, or containment could not be asserted → consumer
                logs "Cross-model review skipped: <reason>" and continues;
                it is a gate, not a blocker (hex adversary contract)
```

**There is no rung below `skip`, and no rung above it that drops isolation.** A
degrade never trades containment for a result — the ladder only ever reduces
the *fidelity* of the answer, never the boundary it was produced behind. That
is the difference between this ladder and Option A, which is permanent
residence on a rung that does not exist here.

`incomplete` is the rung added by the fix pass, and it is about **coverage**
rather than fidelity: it exists because the previous design could return
`approve` on files it had never seen, with the same status, the same containment
stamp and the same shape as a complete review.

---

## 8. Non-functional detail

### 8.1 Latency budget

| Stage | Budget | Basis |
|---|---|---|
| `config.load` upward search | < 10 ms | ≤ 20 `stat` calls |
| `probe` | < 500 ms | one `--version`-class invocation; longer behind a launcher prefix |
| neutralize (both ends) | < 200 ms | 2 × (`read-tree` + `ls-tree` + batched `update-index` + `write-tree` + `commit-tree`); O(tracked file count) |
| `worktree add` | ≤ 1.2 s p50 at ≤ 50k tracked files | dominated by checkout I/O; O(repo size), not O(diff) |
| diff write | < 100 ms | one `git diff` and one write |
| **harness review** | 20 s – 10 min | dominates everything above by one to two orders of magnitude |
| teardown | < 300 ms | `remove --force` + `prune` |
| **nox overhead total** | **≤ 2 s p50** | excluding harness time |

**Every number in this table is an engineering estimate. None was measured.**
The budget is stated so that a future broker (§ 2) has a threshold to beat, and
it should be read as a target the first benchmark replaces, not as a finding —
including in § 8.1's own use of it to justify deferring Option D, which is one
intuition arguing against another.

**Git LFS was the named exclusion and C-1031 closes it, as a side effect of a
security fix.** `git-lfs` does not respect sparse-checkout
([git-lfs#3803](https://github.com/git-lfs/git-lfs/issues/3803)), so every
`worktree add` on an LFS repository would smudge its pointers — a full fetch
per review, unbounded by anything in this table. But git-lfs *is* a smudge
filter, and under C-1005 the tree carries no `.gitattributes` and under C-1031
`core.attributesFile` is `/dev/null`, so no filter applies and LFS files
materialize as **pointer text**. That is both faster and safer: a reviewer
reads pointers as data instead of the checkout executing a filter. The honest
statement of the consequence is that **nox reviews an LFS repository's
pointers, not its large objects** — which is what a diff review wants anyway.
On a repo where
`worktree add` exceeds the budget, LFS or otherwise, the honest fix is the
`isolation = "in-tree"` key the ADR defers as Option D — which is a config key
*plus* a trust registration (`isolation` is in `PERMISSION_KEYS`) *plus*
widening a frozen public `Literal`, and available only to an adapter that
declares the capability.

### 8.2 Cost and quota

Three pools, documented separately and never as equivalent. **Claude Code**
runs draw on the Agent SDK monthly credit, which explicitly covers "the
`claude -p` command in Claude Code (non-interactive mode)" and "third-party
apps that authenticate with your Claude subscription through the Agent SDK" —
a separate, smaller budget than the interactive allowance users expect
([`nox-security.md:399-420`](../research/nox-security.md)). **Codex** draws on
the user's ChatGPT plan or API key. **OpenCode** draws on whatever provider the
user configured, and OpenCode with an Anthropic model **cannot** use a Claude
subscription at all since the 2026-04-04 enforcement. Only Claude Code holds
`COST_REPORTING`, so for the other two the local call log (C-1021) is the only
spend visibility that exists — no vendor exposes a pre-call quota check.

### 8.3 Operability

- **Version churn is the standing maintenance cost.** Claude Code's headless
  contract was revised repeatedly through 2026; Codex hard-*removed*
  `--full-auto` in v0.147.0 and its docs migrated domains mid-2026
  (`developers.openai.com/codex/*` now 308-redirects to
  `learn.chatgpt.com/docs/*`); OpenCode's docs trail its binary, which is why
  the tech lane probed `--help` rather than reading docs. The response is
  `verified_against` + a warning + contract tests against real binaries — not
  refusal, which would make nox brittle in the opposite direction. Note the
  research's own `Expires:` tightened to **2026-11-30** on the Codex axis.
- **Worktree leaks.** `prune` at startup, a `nox-ws-` path prefix so a leak is
  identifiable, `--force` on removal (plain `remove` fails on a tree containing
  submodules), teardown in a `finally`. Not eliminated: SIGKILL to nox itself
  skips the `finally`, which is what `prune` at startup is for.
- **Install surface.** `python3` on PATH and one `.pyz`. Zero runtime
  dependencies means no lockfile, no resolver, no supply chain beyond CPython.

### 8.4 Build reproducibility

`zipapp` uses `zipfile`, which stamps entries with wall-clock mtime, so two
builds of identical source differ byte-for-byte. nox does not take the
`repro-zipfile` dependency; it sorts entry iteration and forces a fixed
`ZipInfo.date_time`, and CI sets `SOURCE_DATE_EPOCH` for consistency with the
ecosystem convention even where the stdlib does not read it
([`nox-tech-tooling.md:60-66`](../research/nox-tech-tooling.md)). The
acceptance check is byte-identical output across two CI runs, not the presence
of the env var. Two zipapp constraints are load-bearing: a stale `__pycache__`
in the staging directory ships inside the archive, and
`importlib.resources.files()` **called with no argument** fails inside a `.pyz`
while the explicit-package form works — so nox never calls the bare form.

---

## 9. Rollout

### 9.1 v1 scope

**In:** the `nox` repository (own repo, `ocx-sdk-python` shape); the public
surface of the ADR's *Component contracts*; adapters for **Claude Code, Codex
and OpenCode**; workspace isolation; the prompt module (C-1028); `nox.toml`
with the trust gate; the CLI; `skill/SKILL.md` + CI-built
`skill/scripts/nox.pyz`; the `hex.md` pointer flip.

**Out:** Copilot and Cursor adapters (the `Adapter` protocol is the documented
extension point); Codex's `app-server` transport and any broker or warm-server
reuse (C-1024); concurrency beyond the serialized default; the
`isolation = "in-tree"` escape (Option D, deferred); a trusted-context opt-in
for `CLAUDE.md`/`AGENTS.md`; PyPI publication as anything load-bearing.

**Publishing.** `CLAUDE.md` states that every published artifact lives under
`ghcr.io/michael-herwig/arcana/<name>`, and nox's skill is built outside arcana
so that one tag ships one version of skill and code together. It publishes to
**`ghcr.io/michael-herwig/arcana/nox`** from the nox repository, with
`repository_prefix = "michael-herwig/arcana"` in nox's own `publish.toml` and a
release credential scoped to that path. arcana's per-skill verification gate
travels with it: nox's CI runs `grim build skill/` alongside the Python
`task verify`. The separate repository genuinely solves a toolchain problem —
uv, ruff, pyright, pytest and mkdocs would be a second toolchain and a second
CI shape in a markdown-only grimoire, and a `fail_under = 100` coverage gate has
no meaning for arcana's other artifacts — but it *relocates* publishing and
verification rather than solving them, and this paragraph is where they land.
Relatedly, `hex/DESIGN.md`'s "no shipped file names a literal model or a harness
tool" binds the hex bundle; nox is a separate bundle in a separate repository
and its `SKILL.md` necessarily names `claude`, `codex` and `opencode`. The
`hex.md › Preferences` pointer flip is the seam where the two rule sets meet,
and the scoping is stated here so a future reader does not have to ask.

**Full N×N across three harnesses is six directed edges** (3 × 2),
user-selected. The discussion's convention excludes self-review — it counted
twelve edges for four harnesses — and an earlier revision said nine, which
silently included `claude→claude`, `codex→codex` and `opencode→opencode`.
Self-review is a different product claim with none of the cross-model asymmetry
evidence behind it, and it is not shipped. The asymmetry evidence is model-level
rather than harness-level, and OpenCode is BYOK, so `Review.model` records the
model on both sides — making arXiv:2607.21656's measured-negative Codex→Claude
direction visible in a user's own call log rather than an argument in a README.

### 9.2 Sequence

| # | Work | Gate |
|---|---|---|
| 1 | Repo scaffold, tooling, CI skeleton | `task verify` green on an empty package |
| 2 | **C-1004 + C-1005 fixture** — `stash create` → object-level filter → `worktree add`, staged + unstaged + untracked, hostile files at and below the root | the flow behaves as specified, the synthetic-pair diff contains the real change and no neutralization noise, or v1 scope cuts to committed refs |
| 3 | `runner.py` — `Process`/`Runner`, `SubprocessRunner`, `supervise()` | 100% branch coverage against a fake; exactly one pragma |
| 4 | `workspace.py` — lifecycle, object-level `neutralize`, random scratch dir, untracked check (C-1026), plan-artifact materialization (C-1027), prune, `--force` | adversarial fixture (§ 9.4) passes with a stub harness, **including the nested and symlink cases** |
| 5 | `outcome`/`liveness`/`capability`/`config`/`prompt` incl. `PASSTHROUGH_ALLOW` and `REQUIRED` | pure; 100%. Config tests encode **drop-then-validate** order (§ 5.7) |
| 5b | `prompt.py` (C-1028) — one versioned template, per-harness slots, filtered-path and omitted-path statements | not inline in any adapter; its own tests |
| 6a | `adapters/claude.py` + `tests/contract/` | real binary, skipped via `probe()` when absent; passthrough allowlist rejects `--settings`/`--mcp-config`/`--tools` |
| 6b | `adapters/codex.py` + `tests/contract/` | **blocked until the `sandbox_mode` key is resolved *and* a probe proves the mode takes effect**, because C-1025 derives `write_enforcement="os"` from that probe and cannot be hand-written. The `--base` route uses a temporary `refs/nox/` ref, so it is not gated on anything |
| 6c | `adapters/opencode.py` + `tests/contract/` | `ENFORCED_READ_ONLY` correctly **absent**; `mechanism = "config-deny"`; both enforcement axes `"attested"`; error-classification table backed by observed output; `MODELS` literals carry the `provider/` prefix and `probe()` preflights via `opencode providers list` |
| 7 | `cli.py`, zipapp CI build, `skill/SKILL.md` | `grim build skill/` clean; byte-identical `.pyz` twice; publishes to `ghcr.io/michael-herwig/arcana/nox` |
| 8 | `hex.md › Preferences` pointer flip | a `/hex-review` run reaches nox and degrades gracefully when it is removed |
| 9 | Release CI job on a runner carrying all three binaries | contract-test collection count asserted non-zero per adapter (C-1020) — the drift detector cannot skip itself green |

Work packages 3–5b are file-disjoint and parallelizable; 6a/6b/6c are disjoint
from each other and depend on 3–5b; 2 gates everything; 9 gates release.

### 9.3 Adding an adapter later

Four steps, no core change: implement the `Adapter` protocol
(`probe`/`containment_plan`/`prepare`/`parse`); declare a `HarnessInfo` whose
`capabilities` frozenset omits everything not verified — **absence is the
default, and there is no permissive fallback to omit it into**; pin
`verified_against` to the probed version; add one `ADAPTERS` entry mapping a
string key to a dotted path, imported lazily on selection (`fsspec` registry
shape). Contract tests against the real binary are part of the adapter, not
optional.

An adapter whose `ContainmentPlan` leaves either enforcement axis `None` does
not launch (C-1007). That is a *feature* of the extension point: a harness with
no containment story cannot be added quietly — and since C-1025 derives the
stamp from the resolved argv, an adapter cannot *claim* a story it does not
have either. A new adapter also ships a `PASSTHROUGH_ALLOW` entry (C-1023) and
a per-harness error-classification table (C-1012); both default to empty, which
means "refuse everything" and "resolve `indeterminate`" respectively, so an
incomplete adapter is safe rather than permissive. A protocol-shaped harness
(JSON-RPC, a broker) additionally needs `Process.send(line)` — one method, the
delta C-1024 measured before deferring the app-server.

### 9.4 The adversarial acceptance fixture

A repository whose branch adds, simultaneously: `.claude/settings.json` with a
`SessionStart` hook; `.mcp.json` with a server; `.claude/skills/lure/SKILL.md`
with frontmatter hooks and an enticing `description:`; `.codex/hooks.json` with
a `SessionStart` hook; `.codex/config.toml` declaring a stdio `mcp_servers`
entry; `.opencode/plugins/evil.ts` calling Bun's shell API; and `opencode.json`
defining a provider with an attacker-controlled `baseURL`. The review completes
on all three harnesses and **none of the seven executes**.

**Every addition below is a case the seven-file fixture passed while the design
was broken**, which is why the fixture is extended rather than trusted:

- **At least one hostile file below the root** — `packages/api/AGENTS.md` and
  `packages/api/.opencode/plugins/evil.ts`. The original fixture placed all
  seven at the worktree root, so it passed under a root-only *and* a recursive
  reading of C-1005, and could not tell them apart.
- **`.claude` committed as a symlink** to an in-repo directory containing a
  `settings.json` with a hook, and `.codex` as a symlink to `$HOME/.codex`.
  Under an on-disk `rm` these survived while being reported as neutralized.
- **A committed `.nox/` directory and a committed `.nox` symlink.** The first
  was a permanent denial of service against every review of that repository;
  the second turned the obvious fix for the first into an arbitrary file write.
- **Non-execution asserted during the `probe`**, not only during the review —
  the probe is a harness startup and OpenCode loads plugins on any startup.
- **Diff correctness:** the diff each harness sees contains the branch's real
  change and **no** neutralization noise. Under the on-disk `rm`,
  `codex exec review --uncommitted` reviewed seven deletions and returned
  `approve` on a change it never saw.
- **Untracked completeness:** two untracked new files present; assert
  `Containment.omitted` names both and `verdict != "approve"`.
- **`plan-artifact`:** an untracked artifact; assert it is present in the
  workspace and that a missing or out-of-repo `path` refuses before any spawn.

Plus a `nox.toml` in the same branch setting
`passthrough = ["--dangerously-bypass-hook-trust"]`, refused twice over — once
as an untrusted permission key (C-1017), once by the C-1023 allowlist — **and**
the cases the old six-name denylist did not catch:
`passthrough = ["-c", "sandbox_mode=danger-full-access"]`,
`["--settings", "{\"hooks\":…}"]`, `["--mcp-config", …]`,
`["--tools", "Read,Bash"]`, `["--permission-mode", "bypassPermissions"]`, and
the `=`-joined forms of each.

Plus, for the neutralization mechanism itself: **a set member committed as a
symlink** (`.codex` → an in-repo directory holding a `settings.json` with a
hook) absent from the checkout, and **`git merge-base --is-ancestor
<synth-base> <synth-target>`** succeeding so three-dot diffs resolve.

And for git's own surfaces, all three verified as live defects before the fix:
a branch committing `*.py filter=evil` against a machine with
`filter.evil.smudge` configured — **the driver must not run during
`worktree add`**; a branch carrying a **submodule** whose nested repo holds its
own `.claude/settings.json` — `.gitmodules` absent, no mode-`160000` entry
surviving, `git submodule status` empty; and `core.hooksPath` set in the shared
`$GIT_DIR/config` with a **child process** running `git checkout` inside the
workspace — the hook must not fire, which the per-call `-c` form did not
prevent. Both were
open defects that a re-validation pass found by running the *specified* matcher
rather than trusting this document's verification paragraph — which is the
reason both are fixture rows now.

Finally, **stub adapters whose `ContainmentPlan` disagrees with their argv**
must fail, one per enforcement level: `os` without the cached sandbox probe,
`harness` without the `--tools` restriction, `attested` without the config-deny
environment. This proves C-1025's derivation rather than the adapter's word on
all three levels, not just the one the probe already gated.

This fixture is the regression test for the entire ADR — if it ever passes with
something executing, or with a clean verdict on a diff it did not see, the
decision has been undone by a refactor.

### 9.5 What breaks when a harness's flags churn

| Change | Effect | Response |
|---|---|---|
| a flag is renamed | argv rejected → non-zero + error stream | `MALFORMED_OUTPUT`/`error`, never a clean verdict; contract test fails first in CI |
| a flag is removed (`--full-auto` precedent) | same | adapter pin bumped; `verified_against` updated |
| output schema changes | extraction fails | **indeterminate**, `raw` surfaced |
| a *containment* flag is removed | **for T1, posture degrades and does not vanish — for network, it vanishes** | the workspace holds independently against repo-supplied execution, so T1 degrades. It provides **nothing** against egress, so removing Claude Code's tool-list lever or Codex's sandbox key removes network denial outright. `ContainmentPlan` is updated, and if either enforcement axis can no longer be established the adapter refuses to launch (C-1007, C-1025) |
| a new repo-supplied execution surface appears | neutralization set is stale | one constant to extend (C-1005) — the reason it is a literal, shipped list. Codex Agent Plugins (v0.146.0) were checked and add nothing, being install-scoped rather than project-discovered |
| a new dangerous *bypass* flag appears | `DENIED_FLAGS` is stale | one constant to extend — but this is now the *lesser* half: since C-1023 became an allowlist, a new dangerous flag is refused by default rather than needing to be enumerated. The denylist's remaining job is asserting nox never emits one itself |
| a new value-carrying *config* flag appears | previously a silent bypass; now refused by default | the allowlist is why. `-c` and `--settings` were both live bypasses under the denylist and neither was a "dangerous" flag by name |

The last four rows are the payoff of Option C **plus** the allowlist. Under
Option A or B, row 4 is a breach rather than a degrade for whichever harnesses
run in-tree, and rows 5 to 7 have nowhere to be fixed. Row 4 is also the row
where this document previously overclaimed, and the correction is above.

---

## 10. Open questions

Carried from the ADR, hard cap 3, not restated in full here:

1. Python as arcana's first executable asset — recommended **yes**, the `.pyz`
   keeps it out of a consuming agent's context surface.
2. The `nox` / PyPI name collision — recommended **keep `nox`**, rename only
   the optional wheel.
3. Whether `CLAUDE.md`/`AGENTS.md` reach the reviewer — recommended **no**,
   with a trusted-context opt-in as the cheap future answer.

Six things this design does **not** treat as open, and states as carried
uncertainty or as a gate instead:

- The `git stash create` flow — unverified, gated by work package 2.
- Codex's `sandbox_mode` config key name — a verification task gating work
  package 6b. The *key name* is plausibly answerable by one `--strict-config`
  invocation; proving the mode **takes effect** needs a fixture with a write
  attempt and a network attempt observed to fail, which is work-package-2 sized.
  Its failure mode is a refusal to launch, never a silent unsandboxed run — and
  since C-1025, that refusal is enforced by the absence of a passing probe
  rather than by an implementer remembering a table row.
- Whether `codex exec review --base` accepts a raw commit SHA — no longer on
  the critical path. The help documents `<BRANCH>`, so nox uses a temporary
  `refs/nox/base/<token>` outright; raw-SHA support is an optional
  optimization, not a precondition. This closed an open rollout item rather
  than carrying one.
- Whether Codex's Landlock read-only mode incidentally blocks
  `connect(AF_UNIX)` — **unverified**, and the reason T2/T3-network is not shown
  as closed for Codex in § 5.8.
- Whether `--safe-mode`/`--restricted` behave as their help text claims, and
  how Codex project trust is granted — both untested, and both deliberately not
  load-bearing under Option C.
- Whether OpenCode's error stream distinguishes authentication failure from
  rate limiting — unknown, and handled by C-1012's per-harness escape rather
  than by a substring guess.

## 11. Links

- Decision: [`adr_0011_nox_multi_harness_adversary.md`](adr_0011_nox_multi_harness_adversary.md)
- Discussion: [`nox-multi-harness-adversary.md`](../discussions/nox-multi-harness-adversary.md)
- Research: [`nox-security.md`](../research/nox-security.md) (Addendum 1 — worktree
  and hook/MCP neutralisation; Addendum 2 — Codex CLI) ·
  [`nox-tech-tooling.md`](../research/nox-tech-tooling.md) ·
  [`nox-pattern-precedent.md`](../research/nox-pattern-precedent.md) ·
  [`discuss-nox-priorart.md`](../research/discuss-nox-priorart.md) ·
  [`discuss-nox-vendor.md`](../research/discuss-nox-vendor.md)
- Precedent for a paired system-design doc: [`adr_0009_system_design.md`](adr_0009_system_design.md)

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-08-31 | architect (`/hex-architect` tier-high) | Initial draft, derived from ADR 0011's contracts C-1001–C-1022. |
| 2026-08-31 | architect | Three-harness v1: Codex added throughout. Threat model T1–T3 restructured around the three-way asymmetry; per-harness invocation split into §§ 6.1–6.3; `ContainmentPlan` (C-1007) and `DENIED_FLAGS` (C-1023) wired into the component flow; rollout 6a/6b/6c with the Codex sandbox-key gate. |
| 2026-09-02 | architect (`/hex-architect` tier-high, adversarial-panel fix pass) | Component flow reordered: `minimal_env()` at step 0, probe contained, config drop-before-validate, `Containment` derived at step 10. § 4.1 rewritten for object-level neutralization; § 5.5b (T4b, inbound environment) added; § 5.8 gained a network row and lost two false "closed" cells; §§ 6.1–6.3 gained passthrough allowlists, Codex `--base` targeting and per-lane evidence caveats; § 7.1 gained `INVALID_CONFIG` and the untracked row and demoted two modifiers; the degrade ladder gained an `incomplete` rung; § 8.1 named Git LFS and its own estimate status; § 9.1 settled the publishing namespace and corrected nine directed edges to six; § 9.2 added work packages 5b and 9; § 9.4 extended with nested, symlink, `.nox`, probe-time, diff-correctness, completeness and plan-artifact cases; § 9.5 corrected the "degrades, does not vanish" claim for network. Option E references removed. Model selection (C-1030) wired through the config flow and §§ 6.1–6.3: a capability class in the core, adapter-owned class → literal maps, effort knobs emitted from typed values rather than config argv. |
| 2026-09-02 | architect (narrow pass, post-re-validation) | § 4.1 rewritten again: `_neutralize` takes a `parent` and the target is committed with `-p <synthetic base>` (parentless roots broke `merge-base`, three-dot diffs and the Codex `--base` leg); `_matches` tests **all** path components including the basename, closing the symlink leg a re-validation run demonstrated open; `_resolve` builds the plan-artifact target as a one-file addition against the empty tree, deleting `_copy_artifact` and the per-scope branch; `_untracked` subtracts what was materialized, resolving C-1026's collision with C-1027. Flow step (4) reordered and annotated to match. §§ 6.1–6.3 passthrough allowlists emptied of the model flag (rules 1 and 3 contradicted each other under C-1030); Codex row gained the ancestry requirement. § 7.1 untracked row scoped to non-materialized paths. § 9.4 gained symlink, ancestry and three-level stub-adapter rows. |
| 2026-09-02 | architect (cross-model adversary pass) | `_neutralize` walks modes and drops mode-`160000` gitlinks; `.gitattributes` and `.gitmodules` enter the C-1005 set (a smudge filter was confirmed executing during `worktree add`). § 4.1's git note replaced: the C-1031 `GIT_OVERRIDES` set is delivered through `GIT_CONFIG_*` in the child environment rather than as a per-call `-c`, binding every git in the child's process tree. New threat row **T1b** (git itself executes branch-controlled code). § 8.1's Git LFS exclusion closed as a side effect — no attributes means no smudge, so LFS materializes as pointer text. § 9.4 gained filter, submodule and child-issued-git rows. |
| 2026-09-02 | architect (cross-model adversary pass, part 2) | Codex targets `--base refs/nox/base/<token>` (a temporary ref, primary not fallback — the help documents `<BRANCH>`), removing the open rollout item; new § 7.1a per-adapter failure-classification matrix replacing the universal auth/quota rows, with `indeterminate` wherever the shape was never observed and a fixture required before any distinction may be claimed; WP 6b's `--base` gate dropped. |
| 2026-09-03 | orchestrator (`/hex-execute`, WP13 convergence — plan errata E30–E52) | **Five divergences between this design and what ships, recorded here; no decision is reversed.** Three are recorded without touching their sections; two (E51, E52) are corrected in §§ 5.3, 6.1 and 6.3, because in each the record named a flag nox does not emit. **§ 7.1's single `exit 143` row** was resolved three different ways across the four adapters — `opencode` never mapped it at all while its docstring claimed it did — and § 4.3 requires that the exit code gate nothing. The two hold together at exactly one point in a parse, and all four now say so identically: the exit status labels a run whose stream established **neither a verdict nor a terminal outcome of its own**, and never overrules one that did, so it is read only in the constructor each adapter reaches for when extraction failed (plan **E38**). **§ 5.3 / § 6.3's opencode derivation named `--agent explore`** as half the `attested` mechanism on both axes, and `harness.py` emits it nowhere. **Resolved inside this same WP by a live probe, and this row is corrected in place rather than contradicted by a later one:** 1.18.22 answers `agent "explore" is a subagent, not a primary agent. Falling back to default agent` and then runs under **`build`**, opencode's default **read-write** agent, so `--agent` — which takes a string — accepts the flag syntactically and silently discards it. Emitting it would put a containment word on argv that a derivation rule could corroborate over a read-write run, so it is deliberately **not** emitted; §§ 5.3 and 6.3 are corrected to name what carries the axis — the `OPENCODE_CONFIG_CONTENT` deny map, plus `--pure` as a derivation tripwire. Both axes stay `attested` and can never be `harness` or `os`, because the deny map's resolution order was never observed, only its presence in the resolved rule list. No launch-gate ruling is outstanding (plan **E51**). **§ 6.1's `perms` row named `--permission-mode dontAsk`**, which nox does not emit and `harness.NEVER_EMITTED` refuses: at 2.1.259 the row's premise is false — `permissionMode` reads `default` in every observed run — and no `--permission-mode` value is narrower than that default, `dontAsk` naming auto-approval. The row now carries `--permission-prompts none`, what ships, and the `containment` row above it is comma-joined because `--tools <tools...>` is variadic. No stamp leans on either, so nothing is re-derived (plan **E52**). **§ 8's T1b residual is re-affirmed by test, not merely asserted:** a reviewer reproduced `.git/info/attributes` smudge → execution during `worktree add`; the reproduction is real and is **not** a defect, because it needs a capability the row already denies — `$GIT_DIR` is not branch-controlled, and an attacker who can write there owns the repository host (plan **E35**). **§ 4.1(e)'s scratch directory has one residual the design never weighed:** its removal is `workspace`'s `finally` and nothing else, so a SIGKILLed run leaves `review.diff` and `prompt.md` — the whole diff and the whole prompt — under the temp root permanently at `0700`/`0600`; `git worktree prune` reclaims neither it nor the worktree beside it, because `prune` deregisters only a worktree whose directory is gone (plan **E30**). |
