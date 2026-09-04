# nox — Python conventions

Guide for Claude Code inside `nox/`. Repo-wide rules load from the repo root;
this file adds only what is specific to the Python subtree. There is no
`nox/.claude/` directory and there must not be one.

## What this is

A zero-runtime-dependency Python library plus a `.pyz` CLI that runs an
adversarial review of a diff or a plan artifact under a *different* AI harness
(Claude Code, Codex, GitHub Copilot CLI, OpenCode), from an ephemeral git
worktree built out of neutralized synthetic commits. The design record is
[`adr_0011`](../.agents/adrs/adr_0011_nox_multi_harness_adversary.md); its
§ Component contracts is the spec for the public surface, and the plan's
errata are the only deltas.

## Commands

Run from the repo root (the include sets `dir: ./nox`, so every path argument
is relative to `nox/`, never to the root):

| Task | Purpose |
|---|---|
| `task nox:verify` | Full gate — format check, lint, types, tests, coverage |
| `task nox:check` | The gate minus the coverage threshold — what EVERY matrix leg runs (Linux and macOS, 3.11–3.14); the Linux legs then add `task nox:cov:report` |
| `task nox:test -- <paths>` | Selective pytest under coverage |
| `task nox:test:contract` | Real-binary tier; owner's machine only |
| `task nox:format` | Apply the ruff formatter |

## Invariants

- **Zero runtime dependencies.** `[project] dependencies` stays empty — nox
  ships as a zipapp built from this tree alone. Dev-only tooling lives in the
  `dev` extra.
- **Python floor 3.11** (D-n), enforced before the first 3.11-only import
  (C-1039). ruff and pyright target `py311`; CI runs 3.11–3.14.
- **No reference to `hex` under `src/`** (C-1001). nox is a standalone library
  and hex is merely its first consumer. The `nox-review/` skill's marker keys
  are the single authorised exception.
- **Typing's never-assert helper is used nowhere** (D-l) — the name itself is
  kept out of the subtree so one grep proves it. Exhaustiveness over internal
  enums rides pyright strict's `reportMatchNotExhausted`; a match over an
  external JSON value takes `case _:` and resolves `indeterminate`, which is a
  real runtime answer and must stay covered.
- **`fail_under = 100` with branch coverage**, enforced on the Linux CI leg
  (D-x). The pragma budget is fixed by the ADR: `SubprocessRunner.spawn`'s
  `subprocess.Popen(...)` line is the only `# pragma: no cover` (C-1015).
- **Dataclasses are `frozen=True, slots=True`** unless mutation is the point
  (`Heartbeat` is, and says so). No pydantic.
- **Capabilities are absence-checked, never boolean-flagged.** An adapter that
  cannot establish one omits it and the gate refuses.
- Public surface is the curated re-export list in `src/nox/__init__.py`.

## The dev venv is not the floor

`uv sync` resolves to the newest interpreter on the machine; `requires-python`
is `>=3.11` and CI's matrix starts there. The two disagree in ways a 3.14-only
run cannot see — a `MappingProxyType({})` dataclass default is accepted from
3.12 on and raises `ValueError: mutable default ... use default_factory` on
3.11, which took the whole suite out at collection time while `task verify`
stayed green locally.

Before pushing anything that touches a dataclass default or a stdlib edge:

    uv run --python 3.11 --extra dev python -m pytest tests/unit tests/acceptance -q
