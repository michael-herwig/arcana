"""C-1039(3) — the zipapp refuses a sub-floor interpreter with a message, not a traceback.

Ubuntu 22.04 ships 3.10 and the shebang is `/usr/bin/env python3`, so the wrong
interpreter is the ordinary case. Without the guard the user sees an
`ImportError` from `tomllib` raised inside `nox/__init__.py`'s eager re-exports.

The archive is built here rather than read from
`nox/nox-review/scripts/nox.pyz`: the release gate runs `task nox:verify` ahead
of `task nox:build`, so a skip-when-missing would make this test green by skip
on every run that matters.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import build_pyz

NOX = Path(__file__).resolve().parents[2]
SRC = NOX / "src" / "nox"
FLOOR_INTERPRETER = shutil.which("python3.10")


@pytest.mark.skipif(FLOOR_INTERPRETER is None, reason="python3.10 is not on PATH")
def test_a_sub_floor_interpreter_gets_the_remedy_and_no_traceback(tmp_path):
    pyz = tmp_path / "nox.pyz"
    build_pyz.build(SRC, pyz)

    result = subprocess.run(
        [str(FLOOR_INTERPRETER), str(pyz), "--version"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0, result.stdout
    combined = result.stdout + result.stderr
    assert "ImportError" not in combined
    assert "Traceback" not in combined

    # The found version, the floor, and something the user can act on.
    assert re.search(r"\b3\.10(\.\d+)?\b", result.stderr), result.stderr
    assert "3.11" in result.stderr, result.stderr
    assert re.search(r"python3\.11|re-run|rerun|upgrade|newer", result.stderr, re.I), result.stderr
