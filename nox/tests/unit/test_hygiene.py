"""Grep-level invariants: no hex reference under src (C-1001), no never-assert helper (D-l)."""

import ast
import dataclasses
import importlib
import pkgutil
import re
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path

import nox

# Resolved from this file, never from the cwd: pytest may be invoked from the
# repo root or from nox/, and the invariants are about the nox subtree either way.
NOX = Path(__file__).resolve().parents[2]


def _repo_files() -> list[Path]:
    """Every file git accounts for under `nox/`: tracked, plus untracked and not ignored.

    Exactly "the files in the repo, minus the gitignored ones", which is the
    property both scans are about — and it needs no prune list. A hand-rolled
    walk does, and a virtualenv the list does not name (`UV_PROJECT_ENVIRONMENT`
    puts one anywhere) drops the scan into site-packages, where the D-l needle
    is everywhere; a prune list wide enough to avoid that can hide a real hit.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=NOX,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [NOX / name for name in listed.split("\0") if name]


def _readable(paths: Iterable[Path]) -> Iterator[tuple[Path, bytes]]:
    """Yield `(path, bytes)` for each path whose content can be read.

    Bytes rather than text: neither scan may depend on a file being decodable,
    and a path git lists can be staged-but-deleted, a submodule, or unreadable.
    """
    for path in paths:
        if not path.is_file():
            continue
        try:
            yield path, path.read_bytes()
        except OSError:
            continue


def test_the_nox_root_resolved_from_file_is_the_package_root():
    assert (NOX / "pyproject.toml").is_file()
    assert (NOX / "src" / "nox" / "__init__.py").is_file()


def test_no_hex_reference_under_src():
    """C-1001(a1): nox is standalone; hex is merely its first consumer.

    `\\bhex\\b` is word-bounded so `hexdigest`, `hexadecimal` and `%x` cannot
    false-positive, and case-insensitive so `Hex`/`HEX` cannot slip through.
    Every file under `src/` is scanned, not just `*.py`: `py.typed`, a data
    file or a template ships with the package exactly as a module does.
    """
    word = re.compile(rb"\bhex\b", re.IGNORECASE)
    src = NOX / "src"
    sources = [p for p in _repo_files() if p.is_relative_to(src)]
    assert len(sources) >= 4, f"an empty listing would pass silently: {sources}"
    offenders = [str(p.relative_to(NOX)) for p, data in _readable(sources) if word.search(data)]
    assert offenders == []


def test_the_never_assert_helper_appears_nowhere_under_nox():
    """D-l: the name itself is kept out of the subtree so one grep proves it.

    Exhaustiveness over internal enums rides pyright strict's match check
    instead, and a match over an external JSON value takes `case _:`.
    """
    # Split with an explicit `+` (implicit concatenation is folded by ruff format)
    # so this file is not its own counterexample.
    needle = b"assert_" + b"never"
    paths = _repo_files()
    assert len(paths) >= 10, f"git listed only {len(paths)} files — an empty listing must not pass"
    offenders = [str(p.relative_to(NOX)) for p, data in _readable(paths) if needle in data]
    assert offenders == []


CONTRACT = NOX / "tests" / "contract"
"""The live tier. Everything under it spawns a real, credentialed harness binary."""


def _workspace_calls(source: bytes):
    """Every `workspace(...)` call in one file, as `ast.Call` nodes.

    Parsed rather than grepped, because the mistake this guards has more than
    one spelling: `env=nox_env(repo)` names the fixture builder, `env=repo.env`
    names nothing at all, and both hand the same throwaway `HOME` to a real
    harness. The property is about the CALL, so the check is too.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - a contract file that will not parse fails its own tier
        return []
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "workspace"
    ]


def test_no_contract_test_hands_workspace_an_environment_of_its_own():
    """A live leg under a test-built environment runs unauthenticated — and passes by SKIPPING.

    `workspace(..., env=None)` builds `config.minimal_env` from `os.environ`,
    which is exactly what `api.review()` does, so the real `HOME` reaches the
    child and the harness finds its own credential store. Anything else in this
    tier is a test-built environment: the git fixtures' `nox_env` and
    `GitRepo.env` both point `HOME` at a throwaway directory under `tmp_path`
    that holds no credential store.

    Not a style rule. Under the fixture environment all eight of copilot's live
    legs read `No authentication information found.` off the real binary and
    skipped: a green tier that pinned nothing, blaming a login the operator had
    already done. A structural check is what makes that unrepeatable, because
    the failure mode is a SKIP and no assertion inside a skipped test can see it.
    """
    files = [p for p in _repo_files() if p.is_relative_to(CONTRACT)]
    assert len(files) >= 4, f"git listed only {len(files)} contract files — an empty listing must not pass"
    scanned = 0
    offenders: list[str] = []
    for path, data in _readable(files):
        for call in _workspace_calls(data):
            scanned += 1
            if any(keyword.arg == "env" for keyword in call.keywords):
                offenders.append(f"{path.relative_to(NOX)}:{call.lineno}")
    assert scanned >= 4, f"only {scanned} workspace() calls found — a parse that yielded none must not pass"
    assert offenders == []


def _package_dataclass_fields():
    """Every `(qualname, Field)` the `nox` package defines, reached by importing it.

    Imported rather than parsed: the rule below is about the object a default
    evaluates to, and `MappingProxyType({})` and `dict()` are indistinguishable
    to a source scan.
    """
    # `nox` itself first: `walk_packages` yields sub-modules only, so a dataclass
    # added to `nox/__init__.py` would be exempt from the rule below.
    names = ["nox", *(info.name for info in pkgutil.walk_packages(nox.__path__, prefix="nox."))]
    for name in names:
        module = importlib.import_module(name)
        for value in vars(module).values():
            if isinstance(value, type) and dataclasses.is_dataclass(value) and value.__module__ == name:
                for member in dataclasses.fields(value):
                    yield f"{name}.{value.__qualname__}.{member.name}", member


def test_no_dataclass_default_is_rejected_by_the_python_floor():
    """D-n/C-1039: 3.11's `dataclasses` refuses any default whose class is unhashable.

    3.11 asks `default.__class__.__hash__ is None`, using unhashability as its
    proxy for mutability, and raises a `ValueError` while the CLASS BODY
    executes — so the refusal is not a failing test: the package does not
    import, and every unit module errors at collection.

    **The check is `hash()`, not 3.11's own predicate**, because `mappingproxy`
    answers that predicate differently per interpreter: `__hash__` is `None` on
    3.11 and a delegating slot from 3.12 on. Reading `__hash__` here would make
    this test agree with whatever venv it runs in and catch nothing on a newer
    one — which is precisely the machine that writes the next such default.
    `hash()` raises `TypeError` on both, so the answer is the floor's.

    Strictly stricter than the floor in one direction — a tuple holding a list
    is accepted by 3.11 and flagged here — which is the safe direction and has
    no instance among the defaults this walks.

    Exactly the shape a version matrix catches and a dev venv cannot: two
    shipped `harness.py` fields were in that state while a 3.12+ venv stayed
    green.
    """
    checked = 0
    offenders: list[str] = []
    for name, member in _package_dataclass_fields():
        if member.default is dataclasses.MISSING:
            continue
        checked += 1
        try:
            hash(member.default)
        except TypeError:
            offenders.append(f"{name}: {type(member.default).__name__}")
    assert checked >= 10, f"only {checked} defaults inspected — an empty walk must not pass"
    assert offenders == [], f"use `field(default_factory=...)` for: {offenders}"
