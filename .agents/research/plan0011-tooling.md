# Research: Reproducible zipapp release, uv CI, and local-release-gate patterns for a zero-dependency Python tool (nox)

## Metadata

**Date:** 2026-09-02
**Domain:** packaging | ci-cd
**Triggered by:** adr_0011 nox plan — `cli.py` + zipapp build + release workflow + `skill/` packaging work
packages (Implementation Plan step 7, `adr_0011_nox_multi_harness_adversary.md:2341`), and the owner's
2026-09-02 `/hex-plan high` gate decision: local release gate — `task release` runs real-binary contract
tests, then tags; GitHub Actions builds and publishes the `.pyz` on tag only; CI dropped as a v1 consumer.
**Expires:** 2027-02-28 (CI/tooling churn — re-verify `astral-sh/setup-uv`/`setup-grimoire` pin versions,
CPython zipapp issue status, and vendor CI-auth guidance before relying on exact versions/URLs past this
date).

This extends [`nox-tech-tooling.md`](nox-tech-tooling.md) (OpenCode surface, zipapp packaging edges,
stdlib process control — not repeated here) rather than duplicating it.

## Direct Answer

Everything nox needs is stdlib-only and already decided in shape by the ADR; this research confirms the
choice, closes two open hedges, and adds one real gap the plan should absorb. Byte-identical `.pyz`:
`python -m zipapp` wrapping `zipfile.ZipInfo` construction to a **hardcoded fixed `date_time`** (derived
from `SOURCE_DATE_EPOCH` if set, else `1980-01-01`) plus `sorted()` file iteration — the stdlib does
**not** read `SOURCE_DATE_EPOCH` on its own; that CPython issue is still open
([python/cpython#89507](https://github.com/python/cpython/issues/89507)). shiv/pex solve dependency
bundling, which nox doesn't have. `requires-python = ">=3.11"` (tomllib) is right, but ~27% of Python
users are still below 3.11 ([JetBrains State of Python 2025](https://blog.jetbrains.com/pycharm/2025/08/the-state-of-python-2025/))
and Ubuntu 22.04 LTS (supported to 2027) defaults to 3.10 — `cli.py` needs a version guard with a clear
message, not a bare `tomllib` `ImportError`. grim publishing from nox's own repo is a straight copy of
arcana's already-working `publish.yml`/`publish.toml` recipe (one skill entry instead of seven,
`repository_prefix = "michael-herwig/arcana"`), with one carried-over gotcha: **GHCR packages publish
private and must be flipped public by hand, no API**. A tag-message receipt or git-notes attestation for
"the local gate ran" is theater for a single-owner repo — Red Hat's own guidance on securing a Claude Code
plugin repo calls a full signed/policy-gated pipeline "overkill for a single-maintainer plug-in"; a signed
tag is the whole trust boundary a solo maintainer needs. All three vendors (Anthropic, OpenAI, and by
extension OpenCode's Anthropic-model path) structurally push subscription/OAuth sessions **away** from
headless CI toward API keys or workspace access tokens — this isn't just ToS risk, it's the sanctioned
shape of the product, which independently confirms the ADR's "release runner = the owner's machine" call.

## Technology Landscape

### Established (proven, widely accepted)

| Tool/Pattern | Status | Notes |
|--------------|--------|-------|
| `python -m zipapp` (PEP 441) | Standard, stdlib since 3.5 | Zips a source tree + shebang; does not resolve or bundle third-party dependencies |
| `astral-sh/setup-uv` + `uv sync`/`uv build` | Standard for uv-based CI as of 2026 | Official Astral-maintained action, actively released (v9.x/v10.x observed this session) |
| Signed annotated git tags as a release trust anchor | Standard, decades old | `git tag -s`/`git tag -v`; native GitHub tag-protection rules can require this |
| `tomllib` (stdlib, read-only) | Standard since Python 3.11 | Cannot write TOML — read-only is fine for nox's config use |

### Declining / not-fit (ruled out, not because they're bad, but because nox's problem doesn't need them)

| Tool/Pattern | Signal | Why nox skips it |
|--------------|--------|-------------------|
| `shiv` / `pex` | Both mature but purpose-built for LinkedIn-scale multi-dependency CLI fleets ([shiv docs, "Motivation & Comparisons"](https://shiv.readthedocs.io/en/latest/history.html)) | nox is `dependencies = []`; there is no dependency graph to bundle or isolate — plain zipapp is strictly sufficient |
| `repro-zipfile` (PyPI) | Small, maintained, exists specifically to patch zipfile's non-reproducibility | Zero-dependency constraint + the fix is ~10 lines (wrap `ZipInfo` construction); prior art, not a dependency to take |
| `hatch-pyz` plugin | Real Hatch build-target plugin for zipapps | Adds a build-time (not runtime) dependency for something one `python -m zipapp` CLI call already does — no gain over the plan's existing recipe |
| Self-hosted GitHub Actions runner on WSL2 | Technically works, no adoption argument either way | Re-creates the exact trust boundary `task release` already has, plus runner-uptime/registration overhead — no net gain (Q5 detail below) |
| Tag-embedded/git-notes "gate ran" attestation | SLSA/in-toto-style provenance is a real, growing pattern for orgs, but explicitly called out as excessive for a solo maintainer's plugin repo ([Red Hat Developer, 2026-08-18](https://developers.redhat.com/articles/2026/08/18/securing-claude-code-plug-ins-best-practices-repository-security)) | The same person holds the tag-signing key and the "ran the tests" claim — nothing stops them from tagging without running `task release` either way; a receipt documents intent, it doesn't gate anything |

## Key Findings

### 1. Byte-identical `.pyz` recipe

`python -m zipapp` does **not** honor `SOURCE_DATE_EPOCH` — [python/cpython#89507](https://github.com/python/cpython/issues/89507)
(originally bpo-45344, filed 2021) is the tracking issue and is **still open**, no linked/merged PR, target
version listed as "3.11" but unimplemented. This closes the hedge `nox-tech-tooling.md:69` left open
("did not verify which exact CPython version added partial support") — there isn't one, for zipapp
specifically. `zipfile.ZipFile.writestr`/`ZipInfo` also do not read it (confirmed by the existence of
[`drivendataorg/repro-zipfile`](https://github.com/drivendataorg/repro-zipfile), whose entire reason to
exist is patching this exact gap; the CPython zipfile test suite honoring `SOURCE_DATE_EPOCH` internally
for its own reproducible-build CI, per [python/cpython#134261](https://github.com/python/cpython/issues/134261),
is a different, unrelated mechanism and should not be read as runtime support).

Concrete recipe for nox's build step (still zero-dependency — this is ~10 lines, not a package):
1. Stage the source into a clean temp directory first (never zip `src/nox` in place) — a stray
   `__pycache__/` from a prior local `uv run` ships inside the archive otherwise, and it isn't
   deterministic across machines (`nox-tech-tooling.md:50` already flags the general risk; this closes it
   with the concrete fix: stage-then-zip).
2. Walk the staged tree with `sorted()`, not `os.walk`/`Path.rglob` default order (filesystem order isn't
   deterministic).
3. Monkeypatch/wrap `zipfile.ZipInfo` construction (or hand `zipapp.create_archive` an already-built
   `ZipFile`-like object) to force a **fixed `date_time`** — read `SOURCE_DATE_EPOCH` from the environment
   and convert it if set, else fall back to `1980-01-01T00:00:00Z` (the ecosystem default, per
   [reproducible-builds.org](https://reproducible-builds.org/docs/source-date-epoch/)). This is the one
   place `SOURCE_DATE_EPOCH` should actually be *read by nox's own build code*, not just exported in CI —
   exporting it without reading it (which is what the current ADR §8.4 text describes as "for consistency
   with the ecosystem convention") is decorative; reading it in the wrapper is what makes it load-bearing.
4. Pick one compression mode (stored or deflate) and don't branch on it — deflate output is deterministic
   for identical input given the same zlib linked into the same CPython build, which is the actual
   guarantee needed ("byte-identical across two CI runs" on the same runner image), not cross-platform
   byte-identity.
5. Shebang `-p "/usr/bin/env python3"`, entry point `-m "nox.cli:main"` — both already in the plan.
6. Acceptance check (already in the ADR, §8.4): `sha256sum` the `.pyz` from two separate CI runs of the
   same commit and diff — that's the real test, not "the env var is set."

### 2. Minimum Python and the version-guard gap

`tomllib` needs 3.11 — already correctly assumed throughout the ADR and `nox-tech-tooling.md:80`. What's
new: **a meaningful fraction of machines nox will run on don't have it.** JetBrains' State of Python 2025
survey ([blog.jetbrains.com](https://blog.jetbrains.com/pycharm/2025/08/the-state-of-python-2025/)) found
48% of respondents on 3.11 and 27% on 3.10-or-older — i.e. roughly a quarter of the Python-using
population is below the floor nox needs. Ubuntu 24.04 LTS defaults to 3.12
([documentation.ubuntu.com](https://documentation.ubuntu.com/ubuntu-for-developers/reference/availability/python/)),
but Ubuntu 22.04 LTS — still in support until 2027, and a common WSL2 base — defaults to 3.10. nox's
actual user population (developers who already run Claude Code/Codex/OpenCode, not "Python developers" in
general) likely skews newer, but "likely" isn't a guard. **Recommendation: add an explicit version check
as the very first thing `cli.py` does**, before the `tomllib` import can throw a bare `ImportError`:
```python
import sys
if sys.version_info < (3, 11):
    sys.exit(f"nox requires Python 3.11+, found {sys.version.split()[0]}. "
              f"Install a newer python3, or `uv python install 3.12`.")
```
Small, cheap, and turns a confusing traceback into an actionable message — worth folding into work package
7 rather than treating it as separate scope. Note the *build* toolchain's Python version (whatever `uv`
provisions in CI, e.g. 3.12) is independent of the *shipped* `.pyz`'s minimum — zipapp ships source, not
build-pinned bytecode, so the artifact runs on any interpreter ≥3.11 regardless of what built it
(consistent with `nox-tech-tooling.md`'s zipapp findings).

### 3. grim packaging from a separate repo

arcana's own `.github/workflows/publish.yml` and `hex/publish.toml` (read directly this session) are the
working, proven recipe — reuse the shape rather than re-deriving it:
- `repository_prefix = "michael-herwig/arcana"` in nox's own `publish.toml` → publishes to
  `ghcr.io/michael-herwig/arcana/nox`, matching the CLAUDE.md namespace rule already stated in
  `adr_0011_system_design.md` §9.1.
- One `[skills."nox"]` entry (arcana's file has seven; nox needs one) — same `version`/tag-override
  mechanics: `grim publish --manifest publish.toml --version "${{ github.ref_name }}"` cascades
  `X.Y.Z`/`X.Y`/`X`/`latest`.
- Pin `grimoire-rs/setup-grimoire` to an exact version tag (`v0.11.1` or newer), never the floating `@v1`
  — arcana's workflow comment explicitly documents this was previously "stale/broken"; carrying a fresh
  floating pin forward would reintroduce a fixed bug.
- `GITHUB_TOKEN` with job-level `packages: write` is sufficient for the bytes-to-GHCR publish step alone
  — confirmed by arcana's own working workflow, which uses exactly that for login. The broader
  `GRIM_ANNOUNCE_TOKEN` (classic PAT, `repo`+`workflow` scope) is only needed for `--announce` (the
  fork-and-PR-to-the-public-index path), which is genuinely optional for nox v1 — the ADR doesn't commit
  to index discoverability, so **recommend nox's release workflow skip `--announce` entirely for v1**
  (simpler token surface, one less cross-owner failure mode) unless the owner wants nox indexed.
- **Real, previously-hit gotcha to carry forward: GHCR packages publish PRIVATE by default and there is no
  API to flip them public** — confirmed first-hand from arcana's own publish history. After nox's first
  tagged release, the package needs a manual visibility change in GitHub's package settings before
  `grim add ghcr.io/michael-herwig/arcana/nox` works from any other machine.

### 4. Local-release-gate patterns

The owner's decision (`task release` runs the three real-binary contract suites locally → tag → GitHub
Actions builds+publishes on tag only, CI dropped as a v1 consumer) matches an established, unremarkable
pattern: local validation before a signed, pushed tag is literally what signed tags are *for* — "anchor
trust in a git workflow... when publishing binaries," and gated-commit-style local validation before
integration is a named, long-standing pattern (Wikipedia, "Gated commit"). The one design question worth
resolving explicitly is whether to embed a machine-checkable "the gate ran" receipt (git notes, a tag
trailer, a committed JSON file) that CI could refuse to build without. **Verdict: skip it — it's theater,
not a gate.** The same person holds the tag-signing key and controls whether `task release` actually ran;
a receipt only proves the owner *typed* the receipt, not that tests passed, and Red Hat's own
Claude-Code-plugin-security guidance independently calls a full signed/policy-gated pipeline "overkill for
a single-maintainer plug-in." If the owner wants a lightweight, purely documentary trail later (not
required for v1): `git tag -s -m "<one-line test summary>"` puts it in `git show <tag>` for free, zero
infra, explicitly non-cryptographic.

### 5. Feasibility check: hosted runner with a logged-in harness session — rejected, and rightly so

All three vendors structurally steer subscription/OAuth sessions away from headless CI, independent of any
GitHub-specific ToS question:
- **Claude Code**: non-interactive automation (`claude -p`, the Agent SDK) is officially supported by
  Anthropic for CI — but explicitly requires **API-key** auth; OAuth tokens from Free/Pro/Max subscriptions
  are documented as not usable with the Agent SDK / non-interactive automation. Storing an OAuth token
  file in a GitHub Actions secret to impersonate an interactive login would work against the vendor's
  stated boundary for this exact use case, not just a gray-area ToS risk.
- **Codex**: OpenAI shipped "Codex access tokens" in May 2026 specifically because ChatGPT-plan OAuth
  sign-in isn't the sanctioned path for unattended `codex exec` in CI — the supported non-interactive
  credential is either an API key (metered billing) or a Business/Enterprise workspace access token, not a
  smuggled personal OAuth session.
- **OpenCode**: BYOK by design, and nox's own prior security research already found OpenCode-with-an-
  Anthropic-model specifically **cannot** use a Claude subscription since the 2026-04-04 enforcement
  (`nox-security.md:399-420`, cited in `adr_0011_system_design.md` §8.2) — same shape, third confirmation.

This isn't three unrelated policies; it's one converging signal that subscription/OAuth sessions are the
wrong credential type for CI across the whole vendor landscape in 2026, which independently validates the
ADR's decision to keep the harness sessions on the owner's machine rather than trying to host them.

**Self-hosted runner on WSL2**: technically straightforward (self-hosted runners are just a labeled
process polling GitHub's Actions API with a registration token; any machine, WSL2 included, can be one).
But it solves nothing here — a runner that's "logged in" as the owner's real Claude Code/Codex session
*is* the owner's machine, wrapped in runner-registration bookkeeping and an always-on-or-manually-started
availability requirement that plain `task release` doesn't have. No trust or automation gain over running
the command directly; net additional operational surface for zero benefit. Confirms the ADR's choice not
to pursue it.

### 6. uv in CI (2026)

From `docs.astral.sh/uv/guides/integration/github/` (fetched this session):
- **Pin `astral-sh/setup-uv` to an exact version** (commit SHA + version comment, e.g.
  `astral-sh/setup-uv@<sha> # v9.0.0`) — Astral's own docs call this "best practice." Worth doing from
  nox's first commit: arcana already paid for the lesson once with `setup-grimoire@v1` floating and
  breaking (`hex-publish-ci` memory) — no reason to repeat it on a different action.
- **`uv sync --locked --all-extras --dev` is Astral's own recommended CI command, not `--frozen`.**
  `--locked` fails the run if `uv.lock` is out of date relative to `pyproject.toml` — the correct default
  for a release gate, since silent lock drift is exactly the kind of thing a "does this actually build
  reproducibly" gate should catch. `--frozen` skips that check entirely for speed and would mask drift.
  Recommend `--locked` for nox's `task verify`/CI step; there's no case in a release pipeline where
  skipping the staleness check is the right trade.
- **`uv build`** produces sdist/wheel — not part of the release path (nox ships a `.pyz`, not a wheel;
  wheel publication is explicitly out of v1 scope per `adr_0011_system_design.md` §9.1's "PyPI publication
  as anything load-bearing" exclusion), so it's not needed in the release workflow, only potentially for
  local dev (`uv build` / `pip install -e .`).
- **Python provisioning**: `uv python install` (respects `requires-python` from `pyproject.toml`) or an
  explicit `python-version` input to `setup-uv` decouples the CI interpreter from whatever the runner image
  happens to default to — same reasoning as finding 2's version-drift risk, just on the build side instead
  of the shipped-artifact side.
- **Caching**: `enable-cache: true` on `setup-uv`, keyed off `uv.lock`'s hash — built-in, no manual
  `actions/cache` wiring needed unless finer control is wanted.
- **hatchling + `src/` layout**: Astral's docs have no special-casing for this combination because none is
  needed — hatchling auto-detects a `src/<pkg>` layout as the package root, and `uv sync`/`uv build` just
  defer to whatever `[build-system]` in `pyproject.toml` says. This is already implicit in the ADR's
  "`ocx-sdk-python` shape" (`src/` layout, hatchling, uv) — no new config surface to add.

## Recommendation

Ship the ADR's existing plan unchanged in shape, with four concrete additions folded into the existing
work packages rather than treated as new scope:

1. **Work package 7 (`cli.py` + zipapp build)**: add the `sys.version_info < (3, 11)` guard as the first
   lines of `cli.py`, and implement the fixed-`date_time`-from-`SOURCE_DATE_EPOCH` wrapper (stage-then-zip,
   sorted iteration) rather than exporting the env var without reading it.
2. **Work package 8 (`skill/SKILL.md` + release workflow)**: copy arcana's `publish.yml`/`publish.toml`
   shape verbatim (pinned `setup-grimoire`, `packages: write`-only `GITHUB_TOKEN` for the publish step),
   skip `--announce` for v1, and add "make the GHCR package public" as an explicit first-release manual
   step in the plan's own notes so it isn't rediscovered the hard way.
3. **CI job for nox itself** (build/lint/typecheck, separate from the release-only `.pyz` build): pin
   `astral-sh/setup-uv` by SHA, use `uv sync --locked`, let `uv python install` provision the interpreter.
4. **No new work package for release-gate attestation** — the owner's `task release` → signed tag → tag-
   triggered build is sufficient as designed; do not add a receipt/git-notes mechanism.

## Sources

| Source | Type | Date | Relevance |
|--------|------|------|-----------|
| [python/cpython#89507](https://github.com/python/cpython/issues/89507) | Issue tracker | filed 2021, checked 2026-09-02 (still open) | Authoritative: zipapp does not honor `SOURCE_DATE_EPOCH` |
| [python/cpython#134261](https://github.com/python/cpython/issues/134261) | Issue tracker | fetched 2026-09-02 | Clarifies the zipfile test-suite's own `SOURCE_DATE_EPOCH` use is internal, not runtime support |
| [drivendataorg/repro-zipfile](https://github.com/drivendataorg/repro-zipfile) | Repo | fetched 2026-09-02 | Prior art for the fixed-`ZipInfo.date_time` wrapper pattern; not taken as a dependency |
| [reproducible-builds.org/docs/source-date-epoch](https://reproducible-builds.org/docs/source-date-epoch/) | Docs | fetched 2026-09-02 | `SOURCE_DATE_EPOCH` convention and the 1980-01-01 fallback default |
| [shiv docs — Motivation & Comparisons](https://shiv.readthedocs.io/en/latest/history.html) | Docs | fetched 2026-09-02 | Why shiv/pex exist (dependency bundling at scale) and why nox doesn't need them |
| [JetBrains — State of Python 2025](https://blog.jetbrains.com/pycharm/2025/08/the-state-of-python-2025/) | Survey | 2025-08 | 48% on 3.11, 27% on ≤3.10 — motivates the version-guard finding |
| [Ubuntu for Developers — Python availability](https://documentation.ubuntu.com/ubuntu-for-developers/reference/availability/python/) | Docs | fetched 2026-09-02 | 24.04 LTS defaults to 3.12; corroborates 22.04's 3.10 default as still in-support |
| `/home/mherwig/dev/arcana/.github/workflows/publish.yml`, `hex/publish.toml` | Local, working code | read 2026-09-02 | Proven grim publish recipe to copy for nox's own repo |
| [`hex-publish-ci` memory](file:///home/mherwig/.claude/projects/-home-mherwig-dev-arcana/memory/hex-publish-ci.md) | Local memory | modified 2026-07-23 | GHCR private-by-default gotcha, PAT scope lessons, floating-tag breakage precedent |
| [Astral — Using uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/) | Docs | fetched 2026-09-02 | `setup-uv` pinning, `--locked` vs `--frozen`, caching, python provisioning |
| [Wikipedia — Gated commit](https://en.wikipedia.org/wiki/Gated_commit) | Reference | fetched 2026-09-02 | Names the local-validate-before-integrate pattern the owner's gate already follows |
| [Red Hat Developer — Securing Claude Code plug-ins](https://developers.redhat.com/articles/2026/08/18/securing-claude-code-plug-ins-best-practices-repository-security) | Blog | 2026-08-18 | Calls full signed/policy-gated provenance "overkill for a single-maintainer plug-in" — directly supports the anti-attestation recommendation |
| Anthropic Agent SDK / Claude Code CI guidance (via search aggregation) | Docs/blog aggregation | fetched 2026-09-02 | OAuth (Free/Pro/Max) not usable with Agent SDK/non-interactive automation; API keys are the sanctioned CI path |
| Codex CLI access tokens coverage (via search aggregation, "Codex Access Tokens: Enterprise CI/CD Authentication," 2026-05-14) | Blog | 2026-05-14 | OpenAI's May 2026 access-token feature exists because OAuth sign-in isn't meant for headless CI |
| `.agents/research/nox-tech-tooling.md` | Local research | 2026-08-31 | Base research this file extends — zipapp packaging edges, stdlib process control, not repeated here |
| `.agents/research/nox-security.md` | Local research | cited via `adr_0011_system_design.md` §8.2 | OpenCode-with-Anthropic-model subscription restriction, third confirmation for finding 5 |
