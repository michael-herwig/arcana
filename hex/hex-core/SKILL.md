---
name: hex-core
description: Shared reference library for the hex swarm-orchestration bundle - worker role registry, model capability matrix, swarm protocol vocabulary, and the .agents/memory/hex.md memory spec. Not invoked directly; the hex-plan, hex-execute, hex-review, hex-architect, and hex-init skills link into it.
license: Apache-2.0
metadata:
  summary: Shared reference library for the hex swarm bundle
  keywords: swarm,orchestration,workers,models,protocol,memory,library
  repository: https://github.com/michael-herwig/arcana
  claude.disable-model-invocation: "true"
---

# hex-core — Shared Reference Library

`hex-core` is the library skill of the **hex** swarm bundle. It holds the
vocabulary and contracts every other hex skill builds on, kept in one
place so they never drift apart. It is **never invoked directly** — there
is no orchestration flow here and no `$ARGUMENTS`. The orchestrator skills
(`/hex-plan`, `/hex-execute`, `/hex-review`, `/hex-architect`) and
`/hex-init` link into these references.

## References

| Reference | Holds |
|---|---|
| [`references/protocol.md`](references/protocol.md) | The shared swarm vocabulary: tier and overlay grammar, the meta-plan approval gate, spawn-selection precedence, the canonical Review-Fix Loop, worker coordination, degraded (no-subagent) mode, worktree work-package mechanics, the adversary contract, and the per-run upkeep step. |
| [`references/workers.md`](references/workers.md) | The worker role **index** plus the universal worker protocol; full personas (mission, spawn-prompt template, focus modes, output contract) live one file per role under `references/workers/` — explorer, architecture-explorer, researcher, builder, tester, reviewer, doc-reviewer, architect, coordinator. Orchestrators load only the personas in the resolved spawn set. Workers are prompt blocks the orchestrator copies into a subagent, not shipped agent files. |
| [`references/models.md`](references/models.md) | The one model matrix for the whole bundle: recommended capability class per role × tier, plus the escalation, resolution-order, and instantiation rules. No model guidance lives anywhere else in hex. |
| [`references/memory.md`](references/memory.md) | The `.agents/memory/hex.md` memory spec: the three sections and their per-section ownership, resolution order, a complete example file, plus the editing, destination-choice, and staleness rules. |
| [`references/config.md`](references/config.md) | The `hex.md › Preferences` config vocabulary — keys, defaults, merge rules. **Conditional-load** — read only when `hex.md › Preferences` contains a fenced `yaml` block. |
| [`references/archive.md`](references/archive.md) | The spec fold-back mechanics — delta grammar, destination resolution, the safety envelope and its four commands, halt semantics, idempotence and the fold receipt, revert, and the plan archive. Sole definition site; `hex-execute`, `hex-review`, and `protocol.md` link here. **Conditional-load** — read only when the plan under review carries a `## Spec Deltas` block. |

## How sibling skills reference this

Every hex skill installs as a sibling under the client's skills directory,
so references resolve by relative path:

```markdown
See [`../hex-core/references/protocol.md`](../hex-core/references/protocol.md).
```

If `hex-core` is not installed, add it:

```sh
grim add ghcr.io/michael-herwig/hex-core:latest
```

Cross-skill mentions elsewhere use the command form: `/hex-plan`,
`/hex-execute`, `/hex-review`, `/hex-architect`, `/hex-init`.
