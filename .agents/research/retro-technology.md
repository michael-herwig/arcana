# Research: hex-retro — objective-signal channel, grim hook artifact, portable entry writer

<!--
Technology-landscape research. Owner: researcher worker (ecosystem lane).
Handoff to: hex-plan/hex-architect for the `retro` skill and its capture rule.

Builds on `.agents/research/discuss-retro-vendor.md` and
`.agents/research/discuss-retro-priorart.md` (read first, not repeated here)
— this file fills the four gaps the discussion's open questions named:
Claude Code hook/transcript contract, grim's hook artifact status, the
portable entry-writer mechanism, and the filename scheme.
-->

## Metadata

**Date:** 2026-09-23
**Domain:** cli / agent-config / observability
**Triggered by:** `.agents/discussions/retro.md` open questions Q2 (transcript
vs `/insights`), Q3 (grim hook artifact date), and the writer/filename design
**Expires:** 2027-03-23 — grim's hook branch and Claude Code's hook set are
both moving targets; re-verify before `/hex-plan` executes.

## Direct Answer

1. **No stable transcript schema exists.** `~/.claude/projects/<proj>/<session>.jsonl`
   is explicitly undocumented/internal — Anthropic's own docs say the entry
   format "changes between versions" and point integrators at hooks/SDK
   messages instead ([code.claude.com/docs/en/sessions](https://code.claude.com/docs/en/sessions)).
   A stable schema is an **open, unresolved feature request**
   ([anthropics/claude-code#53516](https://github.com/anthropics/claude-code/issues/53516)).
   `/insights` has no documented schema either (confirmed by prior vendor
   research). Current hooks (`PostToolUse`, `PostToolUseFailure`) carry
   `tool_output`/`tool_error` but **no duration or timing field in any
   event** — confirmed against `code.claude.com/docs/en/hooks` — and there
   is no generic tool-exit-code field (exit codes are hook-decision codes
   only, not tool exit status).
2. **grim's hook `ArtifactKind` is fully implemented but unreleased and
   unmerged** — no PR, no date. It lives on branch `hex/hooks-artifact-kind`
   in `/home/mherwig/dev/grimoire` (251 files, +70k/-750, last commit
   2026-08-29, `git merge-base --is-ancestor` against `HEAD`/`v0.14.2` is
   false — not reachable from main). Open issues #94/#95/#96/#91 on that
   branch's feature are real UX bugs, so the feature is functionally done,
   just parked. Installed `grim` is `0.14.0`; the running `--kind` enum
   (`skill|rule|agent|bundle|mcp`) has no `hook` value yet, and
   `grim-authoring`'s vendor-metadata reference states object-valued native
   fields (Claude `hooks`/`mcpServers`) are "not authorable at all" today.
3. **POSIX sh temp-then-rename, same directory, is the portable minimum** —
   `mktemp` (or `$$`-suffixed name) in the *target* directory + `mv` is
   atomic on any POSIX filesystem because rename(2) is guaranteed atomic
   only within one filesystem; cross-device `mv` silently falls back to
   copy+unlink and loses atomicity. `git rev-parse --path-format=absolute
   --git-common-dir` needs Git ≥2.31 (2021-03), which is universal in 2026
   fleets (this repo runs 2.54.0). No install beyond a POSIX shell and Git
   is needed, and any agent's plain file-write tool can do this directly:
   write `<inbox>/.tmp.<id>`, then `mv .tmp.<id> <id>.json` — the file-write
   tool's own write is not atomic (partial reads possible mid-write from a
   concurrent reader), but the **rename** step is, so as long as nothing
   reads `.tmp.*` names it's safe.
4. **Timestamp+pid, sortable, not a full ULID** — Maildir's own scheme
   (`<epoch-or-hi-res-time>.<pid>_<counter>.<hostname>`) is the closest
   precedent already named in the discussion and needs zero new dependency;
   a lower-res but simpler variant that's sortable and collision-safe with
   no coordination: `<ISO8601-with-microseconds>-<pid>-<4hex-random>.json`.

## Key findings

1. Claude Code hooks reference (fetched 2026-09-23,
   [code.claude.com/docs/en/hooks](https://code.claude.com/docs/en/hooks)):
   full current event list includes `PreToolUse`, `PostToolUse`,
   `PostToolUseFailure`, `PostToolBatch`, `PermissionRequest`/`PermissionDenied`,
   `Stop`/`StopFailure`, `SubagentStart`/`SubagentStop`, `PreCompact`/`PostCompact`,
   `SessionStart`/`SessionEnd`, plus config/context/model-switch events.
   `PostToolUseFailure` (`tool_name`, `tool_input`, `tool_use_id`, `tool_error`/
   `error_message`) is the closest analog to the discussion's
   "PostToolUseFailure?" question — it exists, named exactly that. No event
   in the current set carries wall-clock duration; a retro capture hook
   would have to compute it itself from `PreToolUse`→`PostToolUse` wall-clock
   deltas keyed by `tool_use_id`, which the payload does support (both
   events carry `tool_use_id`).
2. Transcript schema instability is Anthropic's stated position, not
   speculation: "the entry format is internal to Claude Code and changes
   between versions, so scripts that parse these files directly can break
   on any release" — and the community has filed exactly the gap retro
   would need, still open
   ([#53516](https://github.com/anthropics/claude-code/issues/53516)).
3. grim hook branch evidence (`/home/mherwig/dev/grimoire`, local clone,
   checked 2026-09-23): `git log --all --oneline -i --grep=hook` surfaces
   `12e7ed2c feat(hook): add ArtifactKind::Hook, installed via a grim hook
   run dispatcher`, `a8818203 docs(hook): document the hook kind, its gates
   and workspace consent`, `71160d95 chore(bench): measure hook dispatch
   latency`, `82757f0c docs(hook): add a Writing Hooks guide to the site`
   — all on `hex/hooks-artifact-kind`, none on `main`/`v0.14.2`.
   `gh issue list --repo michael-herwig/grimoire --state all` (actual repo:
   `grimoire-rs/grimoire`) turns up open issues #91/#94/#95/#96 filed
   *against* that hook feature (tiers `observer`/`gatekeeper`, events like
   `PreToolUse`, an `arming` per-client refusal list) — evidence of a
   working prototype, not a stub. No PR exists to track merge status.
4. `grim build --kind` today accepts `skill|rule|agent|bundle|mcp` only
   (`grim build --help`, local binary v0.14.0); CHANGELOG.md has no
   "hook" entries through v0.14.2 (2026-09-13).
5. POSIX/atomicity: `mktemp`+`mv` in the same directory is the standard
   crash-safe write pattern (rename(2) atomicity is a POSIX/Linux
   filesystem guarantee, not a shell feature — no source needed beyond
   POSIX rename(2) semantics already cited in prior-art research's
   maildir/O_APPEND discussion). `git rev-parse --path-format=absolute`
   confirmed working locally: `git rev-parse --path-format=absolute
   --git-common-dir` → `/home/mherwig/dev/arcana/.git` on Git 2.54.0;
   the flag was added for explicit absolute/relative path control
   ([git-scm.com/docs/git-rev-parse](https://git-scm.com/docs/git-rev-parse),
   patch series ~2021, i.e. Git 2.31) — predates every client's minimum
   supported Git by years, safe to depend on in 2026.
6. Python stdlib alternative: `tempfile.mkstemp(dir=inbox)` +
   `os.replace(tmp, dest)` gives the same atomic-rename guarantee
   cross-platform (`os.replace` is documented as atomic on POSIX and best
   available on Windows) with less shell-quoting risk, but requires a
   Python interpreter on the runner — not "any client, no install" the
   way `mktemp`+`mv` is.

## Recommendation

- **Q2 (transcript vs `/insights`):** confirmed, mine transcripts directly
  only as a *degraded-mode, version-pinned parser* if the objective channel
  ships before hooks land — treat every field as unstable and wrap parsing
  in a schema-version guard that fails soft. Prefer waiting for `Post­ToolUse`/`PostToolUseFailure` hooks (already available today, unlike the
  transcript schema) computing duration client-side from `tool_use_id`
  pairing, over parsing JSONL at all. `/insights` is not viable as a data
  source (no schema, no attribution field, confirmed again this pass).
- **Q3 (grim hook artifact date):** no date — the feature is implemented on
  an unmerged, un-PR'd branch, stale ~3.5 weeks as of 2026-09-23. Do not
  block hex-retro v1 on it (matches the discussion's existing decision);
  flag to Michael that a rebase+PR of `hex/hooks-artifact-kind` would
  unblock the later hook-based objective channel with materially less new
  work than a from-scratch design, once wanted.
- **Writer:** POSIX `mktemp -p <inbox> tmp.XXXXXX` (or, if the calling
  agent only has a file-write tool, write literally to
  `<inbox>/.tmp.<pid>-<rand>`) then `mv` to the final sortable name, inside
  the inbox directory (never `/tmp`, avoiding cross-device rename). Resolve
  the inbox root once via `git rev-parse --path-format=absolute
  --git-common-dir` (Git ≥2.31, universal). No Python dependency needed;
  this is the shortest path any client (Claude Code, Codex, Cursor,
  OpenCode) can execute with a shell tool or even a bare file-write tool.
- **Filename:** `<UTC-ISO8601-µs>-<pid-or-4hex-random>.json`, e.g.
  `20260923T142530123456Z-a1c9.json` — lexically sortable, collision-safe
  without coordination, and matches the maildir precedent the discussion
  already committed to; skip a true ULID library (rung 3 stdlib win over
  rung 5 dependency — nothing here needs base32 Crockford encoding or
  monotonic-within-millisecond guarantees a timestamp+random suffix
  doesn't already give at one-entry-per-friction-event rates).

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| [code.claude.com/docs/en/hooks](https://code.claude.com/docs/en/hooks) | Docs | fetched 2026-09-23 | Full current hook event list + payload fields |
| [code.claude.com/docs/en/sessions](https://code.claude.com/docs/en/sessions) | Docs | fetched 2026-09-23 | Transcript storage location, internal/unstable format statement |
| [anthropics/claude-code#53516](https://github.com/anthropics/claude-code/issues/53516) | GitHub issue | open, filed ~Apr 2026 | Confirms no stable/documented transcript schema exists |
| `/home/mherwig/dev/grimoire` local clone, branch `hex/hooks-artifact-kind` | Local repo (git log/diff) | commits through 2026-08-29 | grim `ArtifactKind::Hook` implementation, unmerged |
| `gh issue list --repo michael-herwig/grimoire --state all` → grimoire-rs/grimoire#91,#94,#95,#96 | GitHub issues | open, 2026 | Hook feature UX bugs — evidence of working prototype |
| `grim build --help`, `~/.claude/skills/grim-authoring/references/vendor-metadata.md`, `agent-spec.md` | Local CLI + skill docs | checked 2026-09-23 | No `hook` kind in current release; object-valued native fields unauthorable today |
| `/home/mherwig/dev/grimoire/CHANGELOG.md` | Local repo file | through v0.14.2, 2026-09-13 | No hook-kind release entry |
| [git-scm.com/docs/git-rev-parse](https://git-scm.com/docs/git-rev-parse) | Docs | current | `--path-format=absolute` flag semantics (~Git 2.31, 2021) |
| Local `git rev-parse --path-format=absolute --git-common-dir` | Command output | 2026-09-23 | Confirms flag works on Git 2.54.0 in this repo |
