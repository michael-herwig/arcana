# nox

Multi-harness adversarial review. nox reviews a diff — or a plan artifact —
under an AI harness *other* than the one that wrote it: Claude Code, Codex,
GitHub Copilot CLI or OpenCode, headlessly.

The review never runs in your checkout. nox builds a pair of synthetic commits
with every instruction, hook, credential and agent-config file neutralized in
the tree, checks the target one out into an ephemeral git worktree it owns, and
spawns the harness there under a minimal environment. What the reviewing harness
sees of your repository is the change — not its instructions, not its hooks.

That environment is an allowlist, and it deliberately forwards `HOME` and each
harness's own config-directory variables. nox forwards no credential value of
its own, but the reviewing harness reaches its own credential store exactly as
it does when you run it by hand — that is how it authenticates at all. Writes
and network reach are held per harness and not equally strongly: `os` once nox
has probed that the sandbox holds, `harness` by the harness's own primitive in
the resolved argv, `attested` where the harness merely declares it. Every run
stamps the level it established, on a `containment:` line to weigh the findings
against.

Zero runtime dependencies, POSIX, Python ≥ 3.11.

## Status

Released with arcana. nox rides the repository's single release train, so its
version is the arcana tag rather than a cadence of its own — see
[`CHANGELOG.md`](CHANGELOG.md).

Design record:
[`.agents/adrs/adr_0011_nox_multi_harness_adversary.md`](../.agents/adrs/adr_0011_nox_multi_harness_adversary.md)
and [`.agents/plans/plan_adr_0011_nox_adversary.md`](../.agents/plans/plan_adr_0011_nox_adversary.md).

## Development

From the repo root:

```bash
task nox:verify                       # format check + lint + types + tests + coverage
task nox:test -- tests/unit           # selective; paths are relative to nox/
```

Published as `ghcr.io/michael-herwig/arcana/nox`.

## Install

```bash
grim add ghcr.io/michael-herwig/arcana/nox
```

Then the caller runs:

```
python3 <skill-dir>/scripts/nox.pyz review \
  --scope <code-diff|plan-artifact> \
  [--base <ref> | --path <file>] \
  [--harness <name>] \
  [--exclude <the harness you are running as>] \
  [--authored-by <model>] \
  [--repo <path>]
```

`<skill-dir>` is the directory holding the installed `nox-review/SKILL.md`, as
the AI client presents it — substitute that directory's absolute path. Skills
install under client-specific roots, so there is no cross-client path to
hardcode and never a relative `scripts/…`. When the client does not present the
directory, resolve it: `grim status --format json`, top-level `items[]`, the
entry whose `name` is `nox-review`, the `path` of its `outputs[]` entries.

`--harness` wins over the repository's `[review] harness`; with neither, the run
refuses and names every registered harness. There is no shipped default.

`[review] max_prompt_bytes` caps the diff nox will carry to a reviewer — 96 MiB
by default, from a measured ~8.4x peak-memory multiplier over diff size. A
larger change is refused whole and never trimmed. The key is trust-gated, so
only the user-level `nox.toml` may move it.

Every harness authenticates from its own store, so sign each one in through its
own flow first. One is not simply on `PATH`: OpenCode usually ships behind a
package runner, and nox reports it `absent` until the *user-level* `nox.toml`
(`~/.config/nox/nox.toml`) names a launcher for it — the key is trust-gated, so
a repository's own file cannot supply one.

```toml
[harness.opencode]
launcher = ["ocx", "package", "exec", "ocx.sh/anomalyco/opencode:1.18.22", "--"]
```
