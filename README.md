<p align="center">
  <img src="assets/arcana.svg" width="128" alt="arcana logo — a purple flame with a spark">
</p>

<h1 align="center">arcana</h1>

<p align="center">
  Personal grimoire — AI skills, rules &amp; agents, published with
  <a href="https://grimoire.rs"><code>grim</code></a>.
</p>

---

Every artifact here ships as a versioned OCI package under
`ghcr.io/michael-herwig/arcana/<name>`: add it with
[`grim`](https://grimoire.rs), pin it in a lockfile, update it like any
other dependency. Skills are plain markdown — client-neutral by design,
developed against Claude Code.

## hex — swarm orchestration

The flagship bundle: seven slash commands that take a feature from idea to
merged, reviewed code with a tiered multi-agent swarm — not a single agent
following a script.

```sh
grim add ghcr.io/michael-herwig/arcana/hex
```

| Command | Phase |
|---|---|
| `/hex-init` | Audit &amp; bootstrap a project for the swarm |
| `/hex-discuss` | Talk it through first — elaborate, grill, research; drains to a plan, an ADR, or a no |
| `/hex-plan` | Decompose a feature into a reviewed, contract-first TDD plan |
| `/hex-execute` | Implement it — parallel git worktrees, review-fix loop, commit |
| `/hex-review` | Adversarial pre-merge panel — findings and a verdict, never auto-fixes |
| `/hex-finalize` | Recompose the approved branch into a clean series, push, ready the PR — merge stays yours |
| `/hex-architect` | ADRs and trade-off analysis for hard-to-reverse decisions |

Every orchestrator scales worker count, model choice, and review breadth
through one shared `low|medium|high` tier grammar (`auto` by default), and
asks for exactly **one approval** before any work starts — no mid-flow
questions.

The full story — tier grammar, two-layer swarm memory, and how hex
compares to [spec-kit](https://github.com/github/spec-kit) and
[OpenSpec](https://openspec.dev) — lives in [`hex/README.md`](hex/README.md).

## nox — cross-model adversarial review

A change reviewed by the model that wrote it is not reviewed. `nox` runs
the review under a *different* AI harness — Claude Code, Codex, Copilot CLI
or OpenCode — headlessly, from an ephemeral git worktree built out of
synthetic commits with every instruction file, hook and agent-config file
neutralized. The reviewer sees the change, not your repository's
instructions.

```sh
grim add ghcr.io/michael-herwig/arcana/nox
```

One skill, `nox-review`, plus the zero-dependency Python zipapp it shells
to; scopes are `code-diff` and `plan-artifact`, so it satisfies hex's
[adversary contract](hex/hex-core/references/protocol.md#adversary-contract)
as `/hex-review`'s cross-model gate. Findings come back as prose, stamped
untrusted, under a `containment:` line saying what the run actually
established rather than what it assumed. Details in
[`nox/README.md`](nox/README.md).

nox rides arcana's single release train: one `v*` tag publishes hex and nox
together, so nox's version is the arcana tag rather than a cadence of its
own.

## Layout

```
assets/   arcana logo (SVG source, rendered PNGs, favicon)
hex/      the hex bundle — eight skills, one rule + bundle manifest
nox/      the nox bundle — the nox-review skill + the Python it ships
.agents/  hex dogfooding hex: the ADRs, plans, and research behind it
```

## License

Apache-2.0.
