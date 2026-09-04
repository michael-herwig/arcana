"""C-1037(4) and C-1037(5), E12, D-x — the release path: gate, task file, workflow.

Scraped as text on purpose. nox ships zero runtime dependencies and its dev
extra carries no YAML parser, and the properties under test are ordering and
guard properties that survive a text scan intact: which marker precedes which,
and whether a line carries its guard.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import nox

NOX = Path(__file__).resolve().parents[2]
REPO = NOX.parent
GATE = NOX / "scripts" / "release_gate.sh"
RELEASE_TASKFILE = REPO / "taskfiles" / "release.taskfile.yml"
PUBLISH = REPO / ".github" / "workflows" / "publish.yml"
NOX_CI = REPO / ".github" / "workflows" / "nox-ci.yml"
SKILL = NOX / "nox-review" / "SKILL.md"
PYPROJECT = NOX / "pyproject.toml"
INIT = NOX / "src" / "nox" / "__init__.py"

# The C-1037(4) chain, in the order it must run and halt on. Each marker matches
# both the shell that executes the step and the line `DRY_RUN=1` prints for it,
# so one table serves the static scan and the live run.
STEPS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("clean tree on trunk", re.compile(r"clean[ -]tree|porcelain|git status", re.I)),
    ("version agreement", re.compile(r"NOX_RELEASE_VERSION|version agreement", re.I)),
    ("uv sync --locked", re.compile(r"uv sync --locked")),
    ("task nox:verify", re.compile(r"nox:verify")),
    ("grim build nox/nox-review", re.compile(r"grim build nox/nox-review")),
    ("contract tier under NOX_RELEASE", re.compile(r"nox:test:contract")),
    ("task nox:build", re.compile(r"nox:build\b")),
    ("artifact is non-empty", re.compile(r"test -s")),
    ("published file set", re.compile(r"SKILL\.md")),
)

GUARD_EVENT = "github.event_name == 'push'"
GUARD_REF = "startsWith(github.ref, 'refs/tags/')"

# Steps that must never run on a manual dispatch: they verify, build, or ship.
RELEASE_MARKERS = (
    "task nox:build",
    "test -s",
    "github.ref_name",
    # The publish steps spell the ref as "$GITHUB_REF_NAME" rather than as an
    # Actions expression, so this is what keeps them inside the guard scan.
    "grim publish",
)


def _uncommented(text: str) -> str:
    return "\n".join(line for line in text.split("\n") if not line.lstrip().startswith("#"))


def _order(text: str) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for name, pattern in STEPS:
        match = pattern.search(text)
        assert match, f"the {name} step is missing"
        found.append((name, match.start()))
    return found


def _assert_in_order(found: list[tuple[str, int]]) -> None:
    positions = [position for _, position in found]
    assert positions == sorted(positions), [name for name, _ in found]


def _workflow_steps(text: str) -> list[str]:
    return re.split(r"\n {6}- ", text)[1:]


def _tagged_versions(repo: Path = REPO) -> list[tuple[int, ...]]:
    """Every `vX.Y.Z` the RELEASE TRAIN has already tagged, as comparable tuples.

    D-aa: one release train, one tag — nox's version IS the arcana tag, so a
    version at or below a tag that already exists is a version no release can
    ever carry. Read from git rather than from a literal, and empty on a clone
    fetched without tags, where the check is simply vacuous rather than wrong.

    **`--merged origin/main`, not every local `v*`.** A bare tag listing reads
    the developer's own refs, so ambient state decided the verdict below: a
    local-only `v0.9.9` on a feature commit failed this module, and with it
    release-gate step [4/9], on a tag `origin` never carried. The train is what
    the rule is about. `ls-remote` would answer the same question and needs the
    network, which the unit tier may not; a tag `origin/main` cannot reach is
    not a release this repository has cut. When `origin/main` is absent — a
    tag-ref checkout, a clone with no remote — `git` fails and prints nothing,
    which lands back on the vacuous reading the paragraph above accepts.
    """
    listed = subprocess.run(
        ["git", "tag", "--list", "--merged", "origin/main", "v*"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    found = []
    for line in listed.split("\n"):
        match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", line.strip())
        if match:
            found.append(tuple(int(part) for part in match.groups()))
    return found


def _gate_repo(tmp_path):
    """A throwaway repo, clean and on `main`, carrying the real files step 2 reads.

    The gate `cd`s to the repo root and reads `nox/pyproject.toml`,
    `nox/src/nox/__init__.py` and `nox/nox-review/*.md` from there, so the
    *real* files are copied in: a fixture written by hand would prove the shell
    works and nothing about the versions this repository would actually release.
    """
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    (repo / "nox" / "scripts").mkdir(parents=True)
    (repo / "nox" / "nox-review").mkdir(parents=True)
    (repo / "nox" / "src" / "nox").mkdir(parents=True)
    shutil.copy(GATE, repo / "nox" / "scripts" / "release_gate.sh")
    shutil.copy(PYPROJECT, repo / "nox" / "pyproject.toml")
    shutil.copy(INIT, repo / "nox" / "src" / "nox" / "__init__.py")
    shutil.copy(SKILL, repo / "nox" / "nox-review" / "SKILL.md")
    env = {
        **{key: value for key, value in os.environ.items() if key not in ("DRY_RUN", "NOX_RELEASE_VERSION")},
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
        "GIT_AUTHOR_NAME": "nox",
        "GIT_AUTHOR_EMAIL": "noreply@nox",
        "GIT_COMMITTER_NAME": "nox",
        "GIT_COMMITTER_EMAIL": "noreply@nox",
    }
    done = subprocess.run(
        ["git", "init", "-q", "-b", "main"], cwd=str(repo), env=env, capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    _commit_all(repo, env)
    return repo, env


def _commit_all(repo, env) -> None:
    """Stage and commit everything, so the gate's step 1 sees a clean tree."""
    for arguments in (("add", "-A"), ("commit", "-qm", "c")):
        done = subprocess.run(["git", *arguments], cwd=str(repo), env=env, capture_output=True, text=True, check=False)
        assert done.returncode == 0, done.stderr


def _reach_step_nine(tmp_path, repo, env) -> dict[str, str]:
    """Shim the tools steps 3-7 shell out to, and lay down the artifact step 8 wants.

    Step 9 is the only step this fixture exists to reach, and running steps 3-7
    for real would mean `uv sync` and a whole `task nox:verify` inside a
    throwaway repo that carries no sources at all. So `uv`, `task` and `grim`
    become no-op shims on PATH — the cheapest route that still runs, for real,
    everything the gate script itself owns: git in step 1, the `test -s` of
    step 8, and the `find` scan of step 9.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("uv", "task", "grim"):
        shim = bin_dir / name
        shim.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        shim.chmod(0o755)
    scripts = repo / "nox" / "nox-review" / "scripts"
    scripts.mkdir()
    (scripts / "nox.pyz").write_text("not empty\n", encoding="utf-8")
    _commit_all(repo, env)
    return {**env, "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"}


def _run_gate(repo, env, version: str | None = None) -> tuple[int, str]:
    """The gate's exit code *and* its output — a refusal is both, or it is nothing.

    `taskfiles/release.taskfile.yml` chains the changelog, `task publish --
    --dry-run` and the sign instructions after `task nox:release-gate` on exit
    status alone. A step that prints its refusal and still exits 0 therefore
    flows straight through to a signed release, which is why every refusal test
    below asserts the code as well as the text.
    """
    extra = {"NOX_RELEASE_VERSION": version} if version is not None else {}
    result = subprocess.run(
        ["bash", "nox/scripts/release_gate.sh"],
        cwd=str(repo),
        env={**env, **extra},
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


def _full_guard(block: str) -> bool:
    for line in block.split("\n"):
        if "if:" in line and GUARD_REF in line:
            return GUARD_EVENT in line
    return False


def test_the_release_path_files_all_exist():
    for path in (GATE, RELEASE_TASKFILE, PUBLISH, NOX_CI):
        assert path.is_file(), path


def test_the_gate_script_is_strict_moves_to_the_repo_root_and_runs_nine_steps_in_order():
    """C-1037(4). `task nox:release-gate` runs with cwd `nox/`, so the `cd` is load-bearing."""
    text = GATE.read_text(encoding="utf-8")
    body = _uncommented(text)
    assert re.search(r"^set -euo pipefail$", body, re.M)
    assert 'cd "$(git rev-parse --show-toplevel)"' in body
    assert body.index("set -euo pipefail") < body.index("git rev-parse --show-toplevel")
    _assert_in_order(_order(body))


def test_a_dry_run_of_the_gate_prints_every_step_in_order_and_exits_zero():
    """The order is a runtime property, not just a source-layout one."""
    result = subprocess.run(
        ["bash", str(GATE)],
        cwd=str(REPO),
        env={**os.environ, "DRY_RUN": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_in_order(_order(result.stdout))


def test_the_gate_halts_on_the_first_failing_step(tmp_path):
    """C-1037(4): "the first non-zero exit halts the chain", run rather than grepped.

    A `set -euo pipefail` grep proves the source says so and the `DRY_RUN=1` run
    executes nothing, so neither observes the halt. Here step 1's dirty-tree arm
    fails by construction — a throwaway repo with an uncommitted file — and
    every later step label must be absent from the output. Step 2 would *pass*
    in this repo, so a broken halt is visible as `[2/9]` rather than only as a
    later failure. The exit code is the other half: the release task chains on
    it, so a halt that exits 0 is not a halt.
    """
    repo, env = _gate_repo(tmp_path)
    (repo / "dirt.txt").write_text("uncommitted\n", encoding="utf-8")

    code, output = _run_gate(repo, env)
    assert "[1/9]" in output, output
    assert "the working tree is not clean" in output, output
    for number in range(2, 10):
        assert f"[{number}/9]" not in output, output
    assert code != 0, output


def test_the_gate_refuses_a_clean_tree_that_is_not_on_main(tmp_path):
    """C-1037(4): step 1's second arm — releases are cut from `main`, and only main.

    Renaming the branch in place leaves the tree clean, so the dirty-tree arm
    passes and this arm is the only thing left that can refuse. Without it a
    release could be signed off a feature branch, and the tag would name a
    commit trunk never carried.
    """
    repo, env = _gate_repo(tmp_path)
    renamed = subprocess.run(
        ["git", "branch", "-m", "sidequest"], cwd=str(repo), env=env, capture_output=True, text=True, check=False
    )
    assert renamed.returncode == 0, renamed.stderr

    code, output = _run_gate(repo, env)
    assert "[1/9]" in output, output
    assert "releases are cut from main" in output, output
    assert "sidequest" in output, output
    assert "[2/9]" not in output, output
    assert code != 0, output


def test_the_version_is_one_the_release_train_can_still_tag():
    """B1/D-aa: nox's version IS the arcana tag, so it may not be one already cut.

    The bug this pins shipped: every site said `0.1.0` while `v0.1.0` and
    `v0.2.0` were tagged, so `task release:prepare` could name no version the
    gate's step 2 would accept — and step 2 halts the chain before hex publishes.
    """
    current = tuple(int(part) for part in nox.__version__.split("."))
    tagged = _tagged_versions()
    assert current not in tagged, f"v{nox.__version__} is already tagged"
    assert not tagged or current >= max(tagged), f"{nox.__version__} is behind v{'.'.join(map(str, max(tagged)))}"


def test_the_tag_scan_ignores_a_local_tag_the_release_train_never_carried(tmp_path):
    """The verdict above may not depend on the developer's own refs.

    `git tag --list 'v*'` reads whatever is in `refs/tags/`, so a scratch tag
    nobody pushed decides whether this module passes — a local-only `v0.9.9`
    did, and took release-gate step [4/9] with it. Modelled the way it happens:
    `origin/main` is where the fetched train stops, and the local branch has
    moved past it carrying a tag of its own.

    The tag that IS on the train is asserted present in the same call, because a
    filter that returned nothing would pass the negative and prove nothing.
    """
    repo, env = _gate_repo(tmp_path)

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=str(repo), env=env, capture_output=True, text=True, check=False)

    released = git("rev-parse", "HEAD").stdout.strip()
    assert git("tag", "v0.1.0", released).returncode == 0
    assert git("update-ref", "refs/remotes/origin/main", released).returncode == 0
    (repo / "scratch.txt").write_text("work that was never released\n", encoding="utf-8")
    _commit_all(repo, env)
    assert git("tag", "v0.9.9").returncode == 0

    assert _tagged_versions(repo) == [(0, 1, 0)]


def test_the_version_agreement_accepts_the_version_the_subtree_carries(tmp_path):
    """B1: run the gate's step 2 for real, against the shipped files.

    Step 3 (`uv sync --locked`) fails in the throwaway repo, which is fine and
    deliberate: the observable is that the chain REACHED it, which it can only do
    by passing the version agreement — which is what a disagreement between
    `pyproject.toml` and `SKILL.md` would stop.
    """
    repo, env = _gate_repo(tmp_path)
    _, output = _run_gate(repo, env, f"v{nox.__version__}")
    assert "[2/9]" in output, output
    assert "version disagreement" not in output, output
    assert "[3/9]" in output, output


def test_the_version_agreement_reads_the_file_its_own_remedy_names(tmp_path):
    """Step [2/9] told the operator to edit `nox/src/nox/__init__.py` and never opened it.

    The drift was caught — but at step [4/9], after `uv sync --locked` and a
    whole `task nox:verify`, and as a failing unit test rather than as a release
    refusal. A gate whose remedy names a file it does not read teaches the wrong
    thing about where the check lives, and pays minutes for a comparison that
    costs one `awk`.

    `__init__.py` alone is moved, so `pyproject.toml` and `SKILL.md` still agree
    with `NOX_RELEASE_VERSION` and this third literal is the only thing that can
    refuse.
    """
    repo, env = _gate_repo(tmp_path)
    init = repo / "nox" / "src" / "nox" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    moved = text.replace(f'__version__ = "{nox.__version__}"', '__version__ = "99.99.99"')
    assert moved != text, "the fixture no longer carries the literal the gate reads"
    init.write_text(moved, encoding="utf-8")
    _commit_all(repo, env)

    code, output = _run_gate(repo, env, f"v{nox.__version__}")
    assert "[2/9]" in output, output
    assert "version disagreement" in output, output
    assert "99.99.99" in output, output
    assert "[3/9]" not in output, output
    assert code != 0, output


def test_the_version_agreement_refuses_a_version_the_files_do_not_carry(tmp_path):
    """The negative control: without it, a step 2 that always passed would look right.

    A disagreement that printed its message and exited 0 would be worse than no
    check at all — `task release:prepare` would go on to sign a tag naming a
    version the subtree does not carry.
    """
    repo, env = _gate_repo(tmp_path)
    code, output = _run_gate(repo, env, "v99.99.99")
    assert "[2/9]" in output, output
    assert "version disagreement" in output, output
    assert "[3/9]" not in output, output
    assert code != 0, output


def test_the_gate_passes_all_nine_steps_and_exits_zero_on_the_published_file_set(tmp_path):
    """C-1037(4): the positive control for step 9, and for the chain reaching it.

    Every other run in this module stops early, so this is the one observation
    that a gate refusing *everything* — or exiting non-zero unconditionally —
    cannot produce.
    """
    repo, env = _gate_repo(tmp_path)
    env = _reach_step_nine(tmp_path, repo, env)

    code, output = _run_gate(repo, env)
    assert "[9/9]" in output, output
    assert "all nine steps passed" in output, output
    assert code == 0, output


def test_the_published_file_set_refuses_an_extra_file_in_the_skill_directory(tmp_path):
    """C-1037(4), step 9: `grim` packs the directory whole and is gitignore-blind.

    Anything stale sitting in `nox/nox-review/` is therefore a *published* file,
    so the set must be exactly `SKILL.md` and `scripts/nox.pyz`. The extra is
    committed, not left loose, so step 1 stays green and step 9 is the only
    thing that can refuse.
    """
    repo, env = _gate_repo(tmp_path)
    env = _reach_step_nine(tmp_path, repo, env)
    (repo / "nox" / "nox-review" / "stale.md").write_text("left over from a previous release\n", encoding="utf-8")
    _commit_all(repo, env)

    code, output = _run_gate(repo, env)
    assert "[9/9]" in output, output
    assert "does not hold exactly the two files" in output, output
    assert "stale.md" in output, output
    assert "all nine steps passed" not in output, output
    assert code != 0, output


def test_the_gate_runs_before_the_publish_dry_run_and_the_print_block():
    """C-1037(4): the gate wants a clean tree, so it runs before the changelog dirties it."""
    text = _uncommented(RELEASE_TASKFILE.read_text(encoding="utf-8"))
    gate = text.index("nox:release-gate")
    dry_run = text.index("task publish -- --dry-run")
    tag_line = text.index("git tag ")
    assert gate < dry_run < tag_line


def test_release_prepare_prints_the_git_commands_and_never_runs_them():
    """C-1037(4): the human commits, tags and pushes; the task only spells them out."""
    offenders: list[str] = []
    for line in RELEASE_TASKFILE.read_text(encoding="utf-8").split("\n"):
        if line.lstrip().startswith("#"):
            continue
        for command in ("git commit", "git tag", "git push"):
            index = line.find(command)
            if index == -1:
                continue
            echo = line.find("echo")
            if echo == -1 or echo > index:
                offenders.append(line.strip())
    assert offenders == []


def test_every_tag_guard_also_pins_the_event_name():
    """`workflow_dispatch` accepts a tag ref, so `startsWith` alone is not a tag push."""
    text = PUBLISH.read_text(encoding="utf-8")
    guarded = [line.strip() for line in text.split("\n") if GUARD_REF in line]
    assert guarded, "no release step is guarded by the tag ref at all"
    assert [line for line in guarded if GUARD_EVENT not in line] == []


def test_every_release_step_of_the_workflow_is_guarded():
    unguarded = [
        block.split("\n")[0].strip()
        for block in _workflow_steps(PUBLISH.read_text(encoding="utf-8"))
        if "workflow_dispatch" not in block and any(m in block for m in RELEASE_MARKERS) and not _full_guard(block)
    ]
    assert unguarded == []


def test_every_action_is_pinned_to_a_commit_sha():
    """A moving tag on a release workflow is a supply-chain hole with `packages: write`."""
    floating = [
        match.group(1)
        for match in re.finditer(r"uses:\s*(\S+)", PUBLISH.read_text(encoding="utf-8"))
        if not re.fullmatch(r"[0-9a-f]{40}", match.group(1).rpartition("@")[2])
    ]
    assert floating == []


def test_the_coverage_report_step_is_linux_only():
    """D-x: platform-conditional branches make `fail_under = 100` unattainable off Linux."""
    blocks = [block for block in _workflow_steps(NOX_CI.read_text(encoding="utf-8")) if "nox:cov:report" in block]
    assert blocks, "nox-ci.yml never runs the coverage report"
    for block in blocks:
        assert "runner.os == 'Linux'" in block
