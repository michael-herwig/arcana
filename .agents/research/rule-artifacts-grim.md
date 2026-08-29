# Research: rule artifacts in grim

Researched: 2026-08-28. Expires: 2027-02-28.

## Research: rule artifacts in grim

### Direct answer

Yes to both, with one caveat on timing. A rule with **no `paths:` frontmatter**
is grim's native "always-on" primitive — it installs to `.claude/rules/<name>.md`
for Claude Code and gets the equivalent always-loaded treatment on most other
clients for free. hex should ship its discussion-mode stance as a small
unscoped rule, added to `hex.toml`'s `[rules]` table alongside the existing
`[skills]` table — no publish-order or "first rule" constraint exists. Hook
provisioning is a different story: grim now has an ADR-accepted, fully
implemented `hook` artifact kind, but it lives on an **unmerged, unreleased
branch** as of today. hex-init cannot reach for it yet — an "optional
hardening" hook has to be the skill's own runtime write to
`.claude/settings.json`, exactly the fallback the research question named.

### Trends

- **Rules are the minority surface, by design.** Only a handful of clients
  host an ownable, path-scoped rule file at all; the rest (Codex, Gemini, Zed,
  Amp, …) only offer always-on `AGENTS.md`-style hierarchies or a UI-managed
  surface with no on-disk path grim can own. A skill reaches every client; a
  rule reaches a minority — [rule-spec.md § Per-Client
  Transforms](/home/mherwig/.claude/skills/grim-authoring/references/rule-spec.md#71).
- **The ecosystem overwhelmingly shares rules via git-copy, not a package
  manager.** Cursor's own docs describe `.cursor/rules/*.mdc` as something you
  commit to your repo by hand; the community answer to distribution is
  "awesome-cursor-rules"-style curated repos people copy from, not an
  installable package — [Cursor Rules docs](https://cursor.com/docs/rules),
  [awesome-cursor-rules-mdc](https://github.com/sanjeed5/awesome-cursor-rules-mdc/blob/main/cursor-rules-reference.md).
  grim's OCI-distributed, per-client-transforming rule format has no real
  peer in the neighborhood — it's closer to a novel category than a
  fast-follow of an existing one.
- **Hooks-as-a-package is landing industry-wide, right now.** Claude Code
  itself ships a native plugin mechanism (`hooks/hooks.json` in a plugin,
  merged in when the plugin is enabled, plus hooks declared directly in
  skill/subagent frontmatter) — [Claude Code hooks
  docs](https://code.claude.com/docs/en/hooks). grim's own survey (dated this
  branch, 2026-08) found **15 of 17 grim clients now have some hook
  mechanism**, up from a 2026-06 draft that treated hooks as bespoke —
  [`research_hooks_vendor_survey.md`](/home/mherwig/dev/grimoire/.agents/research/research_hooks_vendor_survey.md)
  (referenced from
  [`adr_hooks_support.md`](/home/mherwig/dev/grimoire/.agents/adr/adr_hooks_support.md)).

### Key findings

1. **A rule is one `.md` file; `paths:` absent = always active.** Frontmatter
   is entirely optional — a bare Markdown file with no fence is a valid rule.
   `summary`/`keywords`/`repository`/`deprecated`/`replaced-by` sit at the
   **top level** of a rule's frontmatter (the opposite convention from
   skills, which nest the same keys under `metadata`) —
   [rule-spec.md § Frontmatter, § The
   Asymmetry](/home/mherwig/.claude/skills/grim-authoring/references/rule-spec.md#23).

2. **For Claude Code specifically, an unscoped rule lands at
   `.claude/rules/<name>.md`, natively discovered.** Grim's install code
   documents this directly: `.claude/rules/` is a Claude Code-native
   discovery path, `PROJECT_PREFIX` writes `**/.claude/rules/<name>/**` glob
   entries for scoped rules, and an unscoped rule installs "~verbatim" —
   [`src/install/claude_config.rs:9,61,104`](/home/mherwig/dev/grimoire/src/install/claude_config.rs).
   This is the mechanism that survives what a skill's loaded-into-context body
   cannot guarantee: the rule is a first-class discovered file, not text
   fetched on trigger.

3. **The same rule reaches Cursor (`alwaysApply: true` when unscoped),
   Copilot (project `.github/instructions/`, global
   `~/.copilot/instructions/`), and Kiro (`inclusion: always`) automatically**
   — one canonical file, per-client projection at install time. OpenCode
   strips all frontmatter but still registers the body as a managed always-on
   glob in `opencode.json`; Junie is degraded (no per-file activation key,
   project-scope only) — full table in [rule-spec.md § Per-Client
   Transforms](/home/mherwig/.claude/skills/grim-authoring/references/rule-spec.md#71).

4. **A bundle mixes skills, rules, and agents freely — three independent
   optional tables, no ordering or "first-of-kind" constraint.** `hex.toml`
   today only populates `[skills]`; adding `[rules]` is exactly as
   unconstrained as adding another skill —
   [bundle-spec.md § Member
   Tables](/home/mherwig/.claude/skills/grim-authoring/references/bundle-spec.md#38),
   confirmed against the live
   [`hex/hex.toml`](/home/mherwig/dev/arcana/hex/hex.toml). Publish order is
   members-before-bundle, enforced by `grim publish`'s fixed kind order, not
   by which kinds are present.

5. **Grim has a real `hook` artifact kind — ADR Accepted 2026-08-16 — but it
   is not released.** `hook.toml` (schema, `[[hooks]]` array, event/tier/
   matcher/argv/timeout) is fully specified and implemented on branch
   `hex/hooks-artifact-kind`
   ([`catalog/skills/grim-authoring/references/hook-spec.md`](/home/mherwig/dev/grimoire/catalog/skills/grim-authoring/references/hook-spec.md),
   [`adr_hooks_support.md`](/home/mherwig/dev/grimoire/.agents/adr/adr_hooks_support.md)),
   but as of 2026-08-28 that branch is **not an ancestor of `origin/main`**
   (verified: `git merge-base --is-ancestor HEAD origin/main` fails) and
   today's tagged release, `v0.14.0` (2026-08-28), does not mention hooks in
   its changelog. The installed CLI here is 0.12.1, and even
   `grim add --help` on the branch's own working tree lists only
   `skill|rule|agent|bundle|mcp` as released kinds today.

6. **Even once released, a hook ships hard-disarmed by design — two
   independent, off-by-default gates.** `options.experimental.hooks`
   (config-only, no env override) plus a **per-registry** `trust_hooks` that
   a project file can only ever *restrict*, never grant — global config or an
   explicit `--trust-hooks` flag is the only way to arm. `grim add` alone
   never arms anything; only `grim install` with both gates open does —
   walked through end-to-end in
   [`catalog/hooks/README.md`](/home/mherwig/dev/grimoire/catalog/hooks/README.md)
   and [`hook-spec.md § Ships
   Disarmed`](/home/mherwig/dev/grimoire/catalog/skills/grim-authoring/references/hook-spec.md#16).
   This is a deliberate consent model, not a stopgap — it's exactly the
   "optional, explicit hardening" shape hex-init would want, just not
   available through grim yet.

7. **Claude Code has its own native, independent hook-distribution path** —
   a plugin's `hooks/hooks.json`, merged in when the plugin is enabled, or
   hooks declared directly in skill/subagent frontmatter — separate from
   grim/OCI entirely — [Claude Code hooks
   docs](https://code.claude.com/docs/en/hooks). Not a fit for arcana today
   since hex ships as grim-distributed skills, not a Claude Code plugin
   bundle, but worth naming as the other lever if hex ever targets
   Claude-only distribution.

### Sources

- [rule-spec.md](/home/mherwig/.claude/skills/grim-authoring/references/rule-spec.md) — local, grim-authoring skill (current, ships with installed grim 0.12.1)
- [bundle-spec.md](/home/mherwig/.claude/skills/grim-authoring/references/bundle-spec.md) — local, grim-authoring skill
- [vendor-metadata.md](/home/mherwig/.claude/skills/grim-authoring/references/vendor-metadata.md) — local, grim-authoring skill
- [consume.md](/home/mherwig/.claude/skills/grim-usage/references/consume.md) — local, grim-usage skill
- `/home/mherwig/dev/arcana/hex/hex.toml`, `/home/mherwig/dev/arcana/hex/publish.toml` — local, live precedent
- [`catalog/skills/grim-authoring/references/hook-spec.md`](/home/mherwig/dev/grimoire/catalog/skills/grim-authoring/references/hook-spec.md) — local, unreleased branch `hex/hooks-artifact-kind`
- [`.agents/adr/adr_hooks_support.md`](/home/mherwig/dev/grimoire/.agents/adr/adr_hooks_support.md) — local, Accepted 2026-08-16 (2 weeks old, fresh)
- [`catalog/hooks/README.md`](/home/mherwig/dev/grimoire/catalog/hooks/README.md) — local, worked walkthrough
- `/home/mherwig/dev/grimoire/src/install/claude_config.rs` — local source, `.claude/rules/` discovery path
- [Claude Code hooks docs](https://code.claude.com/docs/en/hooks) — anthropic, live
- [Cursor Rules docs](https://cursor.com/docs/rules) — live
- [awesome-cursor-rules-mdc reference](https://github.com/sanjeed5/awesome-cursor-rules-mdc/blob/main/cursor-rules-reference.md) — community, live

### Recommendation

Ship the discussion-mode stance as a **new unscoped rule** (`hex-discussion-mode.md`,
no `paths:` frontmatter) added to `hex.toml`'s `[rules]` table now — it's the
mechanism the rest of the ecosystem doesn't have (one file, native always-on
projection to Claude/Cursor/Copilot/Kiro, degraded-but-present on OpenCode/Junie),
and hex.toml has zero friction for adding it. Do **not** build hook provisioning
through grim yet: the `hook` kind is real and well-designed but sitting
unreleased on `hex/hooks-artifact-kind` as of 2026-08-28. For "optional
hardening" today, have hex-init write the hook entry itself at runtime,
directly into `.claude/settings.json`, gated behind an explicit user
confirmation — mirror grim's own consent shape (off by default, explicit
opt-in, easy to reverse) since that's the model its own authors converged on
after two ADR drafts. Revisit swapping to `grim add --kind hook` once that
branch merges and ships in a tagged release — watch for a hooks entry in a
future grimoire `CHANGELOG.md`.
