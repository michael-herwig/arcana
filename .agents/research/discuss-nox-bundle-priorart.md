# Research: config-layer splits and doctor/init idempotency — prior art

## Metadata

**Date:** 2026-09-06
**Domain:** cli
**Triggered by:** discussion `.agents/discussions/nox-hex-init-state-split.md` — entry recon (web)
**Expires:** 2027-09-06

## Direct Answer

How developer tools split team-committed / per-user-per-repo / per-user-global
/ per-machine-detected state, and how `doctor`/`init` verbs stay re-runnable.
No source frames "gitignored in-tree vs external XDG keyed by repo" as a named
trade-off; the evidence is behavioural.

## Key Findings

**Config layers**

1. Git: system → global → local (`.git/config`, highest); per-worktree config
   splits further; `includeIf gitdir:` pulls a file in by repo path.
2. VS Code: user < workspace (`.vscode/settings.json`, committed). Workspace
   Trust persisted outside the repo, keyed by folder URI.
3. Claude Code: `.claude/settings.json` (team) vs `.claude/settings.local.json`
   (auto-gitignored on first write, personal); managed › CLI › local › project › user.
4. Codex CLI: trust per absolute path as a table key in user-global
   `~/.codex/config.toml`; untrusted dirs skip all project `.codex/` layers.
   Path-keyed, no content-drift detection.
5. mise: safe subset needs no trust; anything executable prompts `mise trust`,
   which records a **content hash** under `$XDG_DATA_HOME/mise`.
6. direnv: `direnv allow` records a **content hash** under
   `$XDG_DATA_HOME/direnv/allow`; any edit re-arms the prompt.
7. pre-commit: committed config + idempotent `pre-commit install` writing the
   hook into gitignored `.git/hooks/` + `~/.cache/pre-commit` env cache —
   a 3-tier example.
8. `gh`: single global config, no per-repo layer.
9. Cargo: upward walk merging every `.cargo/config.toml`, deepest wins for
   scalars, arrays append; `$CARGO_HOME/config.toml` lowest.
10. uv: project › user › system; npm: cli › env › project › user › global,
    files ignored unless mode 0600; EditorConfig: nearest wins, `root=true` stops.

**doctor / init**

11. `brew doctor`: named checks, exit 0 only if clean; no JSON.
12. `flutter doctor`: tiered verbosity, per-component pass/partial/fail.
13. `npm doctor`: exits 0 even on failed check (npm/cli#1226); no `--json`.
14. `gh auth status`: read-only probe, `--json`, masks tokens.
15. `terraform init`: documented idempotent; caches in gitignored `.terraform/`;
    backend change needs an explicit flag, never silent. `.terraform.lock.hcl`
    committed beside gitignored `.terraform/` — "commit the decision,
    gitignore the derived state".
16. `rustup show`: pure probe, writes nothing.

**In-tree gitignored vs external keyed store**

17. direnv and mise — the two tools that must decide — both chose external
    storage keyed by content hash so an edit invalidates trust and the tracked
    repo cannot tamper with its own record. Secret-hygiene guidance: gitignore
    only stops untracked files; `git add -f`, pattern typos, and history apply.

## Negative

- No direct comparison source for the in-tree vs external question.
- No official `npm doctor` structured output; exit code unreliable.
- VS Code `trustedFolders` on-disk shape undocumented.

## Leads

- Codex's path-only trust key vs direnv/mise's content hash — is path-only a
  known weaker variant?
- Cargo's upward walk-and-merge as a third precedence shape (monorepos).

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| https://git-scm.com/docs/git-config | Docs | 2026 | levels, includeIf |
| https://code.visualstudio.com/docs/configure/settings | Docs | 2026 | user vs workspace |
| https://code.visualstudio.com/docs/editing/workspaces/workspace-trust | Docs | 2026 | trust outside repo |
| https://claudefa.st/blog/guide/settings-reference | Blog | 2026 | settings.local.json |
| https://developers.openai.com/codex/config-advanced | Docs | 2026 | project trust |
| https://mise.jdx.dev/cli/trust.html | Docs | 2026 | hash-keyed trust |
| https://github.com/jdx/mise/security/advisories/GHSA-436v-8fw5-4mj8 | Advisory | 2026 | paranoid mode |
| https://direnv.net/man/direnv.1.html | Docs | 2026 | allow hash |
| https://pre-commit.com/ | Docs | 2026 | 3-tier split |
| https://github.com/cli/go-gh/blob/trunk/pkg/config/config.go | Repo | 2026 | gh precedence |
| https://doc.rust-lang.org/cargo/reference/config.html | Docs | 2026 | upward merge |
| https://docs.astral.sh/uv/concepts/configuration-files/ | Docs | 2026 | uv layers |
| https://docs.npmjs.com/cli/v11/configuring-npm/npmrc/ | Docs | 2026 | npmrc, 0600 |
| https://spec.editorconfig.org/index.html | Spec | 2026 | nearest wins |
| https://docs.brew.sh/Troubleshooting | Docs | 2026 | brew doctor |
| https://docs.flutter.dev/install/troubleshoot | Docs | 2026 | flutter doctor |
| https://github.com/npm/cli/issues/1226 | Issue | open | npm doctor exit code |
| https://cli.github.com/manual/gh_auth_status | Docs | 2026 | gh auth status --json |
| https://developer.hashicorp.com/terraform/cli/init | Docs | 2026 | idempotent init |
| https://rust-lang.github.io/rustup/overrides.html | Docs | 2026 | rustup show |
