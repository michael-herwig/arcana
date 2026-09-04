"""C-1038 — the deterministic `nox.pyz` build, plus the hardening around it.

`scripts.build_pyz` imports because pytest's rootdir is `nox/` and
`pythonpath = ["."]` (pyproject) puts that directory on `sys.path`. `scripts/`
ships no `__init__.py` and must not: it is a build tool that never enters the
archive it produces, so it is a namespace package and nothing more.

Every build here writes into `tmp_path`. The repo's own
`nox/nox-review/scripts/nox.pyz` is never read: `task nox:verify` runs ahead of
`task nox:build` in the release gate, so a suite that depended on that file
existing would be green-by-skip on exactly the run that matters.
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import nox
from scripts import build_pyz

NOX = Path(__file__).resolve().parents[2]
SRC = NOX / "src" / "nox"
CLI = SRC / "cli.py"


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> tuple[Path, str]:
    """The real package, built once: eight assertions read the same archive."""
    target = tmp_path_factory.mktemp("pyz") / "nox.pyz"
    return target, build_pyz.build(SRC, target)


def _members(pyz: Path) -> list[str]:
    # zipfile tolerates the shebang prefix: it locates the end-of-central-directory
    # record from the tail and offsets every header by the concatenation delta.
    with zipfile.ZipFile(pyz) as archive:
        return archive.namelist()


def _main_source(pyz: Path) -> str:
    with zipfile.ZipFile(pyz) as archive:
        return archive.read("__main__.py").decode("utf-8")


def test_the_package_source_this_suite_builds_from_exists():
    assert CLI.is_file()
    assert (SRC / "__init__.py").is_file()


def test_perturbing_every_staged_mtime_changes_no_byte_of_the_archive(tmp_path):
    """C-1038(1): the mtime a file happens to carry is not archive input."""
    source = tmp_path / "src" / "nox"
    shutil.copytree(SRC, source)
    first, second = tmp_path / "first.pyz", tmp_path / "second.pyz"

    first_digest = build_pyz.build(source, first)
    for path in sorted(source.rglob("*")):
        os.utime(path, (1_700_000_000, 1_700_000_000))
    second_digest = build_pyz.build(source, second)

    assert first_digest == second_digest
    assert first.read_bytes() == second.read_bytes()


def test_a_different_source_date_epoch_changes_the_archive(tmp_path):
    """C-1038(2): the knob is wired, so a reproducer can pin the timestamp."""
    first = build_pyz.build(SRC, tmp_path / "first.pyz", source_date_epoch="1000000000")
    second = build_pyz.build(SRC, tmp_path / "second.pyz", source_date_epoch="1600000000")
    assert first != second


def test_source_date_epoch_is_read_off_the_environment_too(tmp_path, monkeypatch):
    """C-1038(2): the keyword is one half of the knob; `SOURCE_DATE_EPOCH` is the other.

    Delete the environment half and every keyword-driven assertion still passes,
    so the exported variable — which is how a reproducer actually pins the
    timestamp — needs its own case.
    """
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    unset = build_pyz.build(SRC, tmp_path / "unset.pyz")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1600000000")
    assert build_pyz.build(SRC, tmp_path / "exported.pyz") != unset


def test_no_member_is_bytecode(built):
    """C-1038(3): a stale `.pyc` is host state, and host state is what breaks E12."""
    for name in _members(built[0]):
        assert "__pycache__" not in name
        assert not name.endswith(".pyc")


def test_the_archive_runs_version_on_a_floor_satisfying_interpreter(built, tmp_path):
    """C-1038(4). Run from elsewhere: `sys.path[0]` is the archive, not the cwd."""
    pyz, _ = built
    result = subprocess.run(
        [sys.executable, str(pyz), "--version"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert nox.__version__ in result.stdout


def test_every_member_is_main_or_lives_under_the_package_directory(built):
    """A zipapp is `sys.path[0]` for the whole process.

    A root-level `queue.py` inside the archive would shadow the stdlib module
    for every import the interpreter makes afterwards, so exactly one root
    member is allowed and it is the entry point.
    """
    names = _members(built[0])
    assert "__main__.py" in names
    for name in names:
        assert name == "__main__.py" or name.startswith("nox/"), name


def test_the_emitted_entry_point_parses_as_python_3_8(built):
    """C-1039: the guard fires on interpreters that cannot parse the package.

    `feature_version` proves 3.8 validity with no 3.8 interpreter on the box —
    a `match`, a walrus in the wrong place or a `X | Y` runtime annotation in
    `__main__.py` would make the floor message itself a `SyntaxError`.
    """
    ast.parse(_main_source(built[0]), feature_version=(3, 8))


def test_the_entry_point_lifts_the_floor_guard_verbatim_from_cli(built):
    """The anti-drift mechanism: `cli.py` is WP8's and is never edited to suit this.

    The emitted `__main__.py` must carry `_require_python`'s source exactly as
    `cli.py` spells it. A copy that drifts is a floor message that no longer
    matches the one the library ships.
    """
    cli_source = CLI.read_text(encoding="utf-8")
    guard = next(
        node
        for node in ast.parse(cli_source).body
        if isinstance(node, ast.FunctionDef) and node.name == "_require_python"
    )
    segment = ast.get_source_segment(cli_source, guard)
    assert segment, "cli.py's _require_python has no recoverable source segment"
    assert segment in _main_source(built[0])


def test_the_entry_point_calls_the_guard_before_importing_the_package(built):
    """C-1039: `import nox` re-exports eagerly, so it must not run first.

    Below the floor that import raises a bare `ImportError` from `tomllib`,
    which is precisely the failure the guard exists to replace.
    """
    source = _main_source(built[0])
    tree = ast.parse(source)
    calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_require_python"
    ]
    assert calls, "the emitted __main__.py never calls _require_python()"
    guard_line = min(calls)

    package_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            package_imports += [node.lineno for alias in node.names if alias.name.split(".")[0] == "nox"]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "nox":
            package_imports.append(node.lineno)
    assert package_imports, "the emitted __main__.py never imports nox at all"
    assert min(package_imports) > guard_line


@pytest.mark.parametrize("plant", ["py-symlink", "other-symlink", "fifo"])
def test_build_refuses_a_source_tree_carrying_a_link_or_a_special_file(tmp_path, plant):
    """`shutil.copytree` defaults to `symlinks=False` — it embeds the target's bytes.

    So a symlink under `src/nox` is a file-exfiltration primitive into a
    published artifact, and a non-regular file is undefined input. Both refuse.
    The exception type is the implementer's choice; the refusal, the named
    path, and the absent output file are the contract.
    """
    source = tmp_path / "src" / "nox"
    shutil.copytree(SRC, source)
    outside = tmp_path / "outside.txt"
    outside.write_text("bytes that must never ship\n", encoding="utf-8")
    if plant == "py-symlink":
        (source / "planted.py").symlink_to(outside)
    elif plant == "other-symlink":
        (source / "planted.txt").symlink_to(outside)
    else:
        os.mkfifo(source / "planted.py")

    target = tmp_path / "nox.pyz"
    try:
        build_pyz.build(source, target)
    except Exception as exc:
        message = str(exc)
    else:
        pytest.fail(f"build accepted a source tree carrying a {plant}")

    assert "planted" in message
    assert not target.exists()


def test_build_refuses_a_source_directory_that_is_itself_a_symlink(tmp_path):
    """`os.walk` follows its root argument whatever `followlinks` says.

    So the per-entry refusal never sees the one link that matters: a symlinked
    `nox/src/nox` walks a foreign tree, every entry inside it is a regular file,
    and the archive ships someone else's bytes under the `nox/` prefix.
    """
    real = tmp_path / "elsewhere" / "nox"
    shutil.copytree(SRC, real)
    source = tmp_path / "planted-src"
    source.symlink_to(real, target_is_directory=True)

    target = tmp_path / "nox.pyz"
    with pytest.raises(ValueError, match="planted-src"):
        build_pyz.build(source, target)
    assert not target.exists()


def test_build_replaces_a_symlink_planted_at_the_target(tmp_path):
    """`task nox:build` is gate step 7; the file-set check that would spot the link is step 9.

    Writing through the link would put the archive's bytes — and mode 0755 —
    onto whatever it names, three steps before anything looks.
    """
    victim = tmp_path / "victim.txt"
    victim.write_text("untouched\n", encoding="utf-8")
    target = tmp_path / "nox.pyz"
    target.symlink_to(victim)

    build_pyz.build(SRC, target)

    assert victim.read_text(encoding="utf-8") == "untouched\n"
    assert not target.is_symlink()
    assert target.is_file()


def test_the_archive_is_executable_and_starts_with_the_shebang(built):
    pyz, _ = built
    assert build_pyz.SHEBANG == b"#!/usr/bin/env python3\n"
    assert pyz.read_bytes().startswith(build_pyz.SHEBANG)
    assert stat.S_IMODE(pyz.stat().st_mode) == 0o755


def test_build_returns_the_digest_of_the_bytes_it_wrote(built):
    pyz, digest = built
    assert digest == hashlib.sha256(pyz.read_bytes()).hexdigest()


def test_main_prints_the_digest_and_nothing_else(tmp_path, capsys):
    """`task nox:build` builds twice and compares stdout, so stdout is the digest.

    Positional argv mirrors `build(source, target)`.
    """
    target = tmp_path / "nox.pyz"
    assert build_pyz.main([str(SRC), str(target)]) == 0

    printed = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(printed) == 1
    assert re.fullmatch(r"[0-9a-f]{64}", printed[0])
    assert printed[0] == hashlib.sha256(target.read_bytes()).hexdigest()
