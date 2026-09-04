"""The version literal and the curated public surface."""

import re
import tomllib
from pathlib import Path

import pytest

import nox

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
CONFIG = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _export_order_key(name: str) -> tuple[int, str]:
    # ruff's RUF022 order for __all__: SCREAMING_CASE, then CamelCase, then the rest.
    return (0 if name.isupper() else 1 if name[0].isupper() else 2, name)


def test_version_literal_equals_pyproject():
    # The whole reason __version__ is a literal rather than importlib.metadata:
    # the zipapp stages src/nox with no dist-info, and an unrelated PyPI `nox`
    # on the host would answer instead.
    assert nox.__version__ == CONFIG["project"]["version"]


def test_version_is_a_non_empty_pep440_release():
    assert nox.__version__
    assert re.fullmatch(r"\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?", nox.__version__)


def test_all_is_ordered_and_duplicate_free():
    assert list(nox.__all__) == sorted(nox.__all__, key=_export_order_key)
    assert len(set(nox.__all__)) == len(nox.__all__)


@pytest.mark.parametrize("name", sorted(nox.__all__))
def test_every_exported_name_resolves(name):
    assert hasattr(nox, name)


def test_the_python_floor_is_3_11():
    # D-n / C-1039: 3.11 is the floor and the guard fires before the first
    # 3.11-only import. Nothing else in the suite notices a ">=3.10" here.
    assert CONFIG["project"]["requires-python"] == ">=3.11"


def test_the_coverage_gate_is_a_full_hundred():
    # D-x: the refusal lives here, in `task nox:cov:report`. Codecov's status
    # checks track the trend and would pass a drop to 99%.
    assert CONFIG["tool"]["coverage"]["report"]["fail_under"] == 100


def test_not_implemented_error_is_not_excluded_from_coverage():
    # The deliberate delta: every WP ships stubs first, so excluding the row
    # would let a forgotten stub body pass fail_under = 100. A stub phase is
    # red here, which is the point.
    excluded = CONFIG["tool"]["coverage"]["report"]["exclude_also"]
    assert not [row for row in excluded if "NotImplementedError" in row]
