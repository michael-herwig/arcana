#!/usr/bin/env bash
# The C-1037(4) local release gate chain.
#
# `task nox:release-gate` runs with cwd `nox/` (the root Taskfile includes this
# subtree with `dir: ./nox`), so the first thing this does is move to the repo
# root: every path in the chain below is repo-root-relative.
#
# Contract: every step runs in the order written, and the first non-zero exit
# halts the chain. `DRY_RUN=1` prints the same steps in the same order without
# running any of them, and exits 0.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Echo the step, then run it — or, under DRY_RUN, only echo it.
step() {
  echo "$1"
  shift
  if [ "${DRY_RUN:-}" = "1" ]; then
    return 0
  fi
  "$@"
}

clean_tree_on_trunk() {
  local dirty branch
  dirty="$(git status --porcelain)"
  if [ -n "$dirty" ]; then
    echo "release gate: the working tree is not clean; commit or stash first:" >&2
    echo "$dirty" >&2
    return 1
  fi
  branch="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$branch" != "main" ]; then
    echo "release gate: releases are cut from main; HEAD is on '$branch'." >&2
    return 1
  fi
}
step "[1/9] clean tree on trunk (git status --porcelain, branch main)" clean_tree_on_trunk

# Fail-closed by design: nothing here bumps a version inside a release that is
# about to be signed. The skill file is matched by glob — its literal name is
# spelled once, by the published-file-set step that owns it.
# The remedy names three files, so all three are read. `__init__.py` was named
# and not read: its drift surfaced at step [4/9] instead — after `uv sync` and a
# whole `task nox:verify`, as a failing unit test rather than as a refusal.
version_agreement() {
  local want project init skill
  local -a skill_files
  if [ -z "${NOX_RELEASE_VERSION:-}" ]; then
    echo "  NOX_RELEASE_VERSION is unset — skipping the version agreement check."
    return 0
  fi
  want="${NOX_RELEASE_VERSION#v}"
  project="$(awk -F'"' '/^version = /{print $2; exit}' nox/pyproject.toml)"
  init="$(awk -F'"' '/^__version__ = /{print $2; exit}' nox/src/nox/__init__.py)"
  skill_files=(nox/nox-review/*.md)
  skill="$(awk -F': *' '/^[[:space:]]*hex-adversary-version:/{gsub(/["[:space:]]/, "", $2); print $2; exit}' \
    "${skill_files[0]}")"
  if [ "$want" != "$project" ] || [ "$want" != "$init" ] || [ "$want" != "$skill" ]; then
    cat >&2 <<EOF
release gate: version disagreement — refusing to sign a release that says four things.
  NOX_RELEASE_VERSION       : $want
  nox/pyproject.toml        : $project
  nox/src/nox/__init__.py   : $init
  ${skill_files[0]} : $skill
Remedy: set all three to $want and re-run "task release:prepare". Edit
  nox/pyproject.toml        ([project] version)
  nox/src/nox/__init__.py   (__version__)
  ${skill_files[0]} (metadata.hex-adversary-version)
EOF
    return 1
  fi
}
step "[2/9] version agreement (NOX_RELEASE_VERSION, when set)" version_agreement

uv_sync() { (cd nox && uv sync --locked); }
step "[3/9] uv sync --locked (in nox/)" uv_sync

step "[4/9] task nox:verify" task nox:verify

step "[5/9] grim build nox/nox-review" grim build nox/nox-review

contract_tier() { NOX_RELEASE=1 task nox:test:contract; }
step "[6/9] NOX_RELEASE=1 task nox:test:contract" contract_tier

step "[7/9] task nox:build" task nox:build

# `grim build` exits 0 with the asset absent, so presence is asserted here.
step "[8/9] test -s nox/nox-review/scripts/nox.pyz" test -s nox/nox-review/scripts/nox.pyz

# grim packs the whole directory and is gitignore-blind, so anything stale in it
# ships. The published set is exactly two files.
published_file_set() {
  local expected found
  expected=$'SKILL.md\nscripts/nox.pyz'
  # `! -type d` rather than `-type f`: `-type f` sees neither a symlink nor
  # anything behind a symlinked directory, so extras hide from the check.
  found="$(cd nox/nox-review && find . -mindepth 1 ! -type d -print | sed 's|^\./||' | LC_ALL=C sort)"
  if [ "$found" != "$expected" ]; then
    echo "release gate: nox/nox-review does not hold exactly the two files grim may publish." >&2
    echo "  expected:" >&2
    sed 's/^/    /' >&2 <<<"$expected"
    echo "  found (delete the extras before releasing):" >&2
    sed 's/^/    /' >&2 <<<"$found"
    return 1
  fi
}
step "[9/9] published file set: exactly SKILL.md and scripts/nox.pyz" published_file_set

echo "release gate: all nine steps passed."
