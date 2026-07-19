# arcana

Personal grimoire — AI skills, rules & agents, published with `grim`.

Product knowledge: [.agents/product.md](.agents/product.md) — what this
is, users, related repos, research keywords, comparable tools.

## Verification

Run `grim build <skill-dir>` for every changed skill/rule before considering
a change complete (validates + packs, no push; exit 65 on validation
failure). Full sweep: `task publish -- --dry-run`.

## Spec / plan / ADR conventions

- Plans live in `.agents/plans/`, ADRs in `.agents/adrs/`
  (MADR-based), research in `.agents/research/`.
- Specs live in `.agents/specs/` — the fold-back target for
  `/hex-review`'s Fold-Back phase; ID marker is the shipped default (see
  `.agents/memory/hex.md` › Pointers).
- Formats follow the hex shipped templates
  (`hex/hex-init/assets/templates/`).

## Architecture rules

- `hex/DESIGN.md` is binding for the hex bundle: single-source contracts
  (link, never copy — `protocol.md` owns the Review-Fix Loop), thin
  `SKILL.md` dispatchers + per-tier phase files, capability classes never
  literal model names in shipped files.
- Constitution: `hex/DESIGN.md` (plans are gated against its resolved
  decisions).

<!-- hex:start -->
Swarm memory: `.agents/memory/hex.md` (search upward; skill-managed).
Commands: `/hex-init`, `/hex-plan`, `/hex-execute`, `/hex-review`, `/hex-architect`.
<!-- hex:end -->
