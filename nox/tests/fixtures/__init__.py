"""Hermetic git fixtures for the isolation tests.

See `repo.py` for what each builder flag plants and why the hostile set is
hardcoded here rather than imported from the code under test.
"""

from tests.fixtures.repo import (
    C1005_MEMBERS,
    HOSTILE_FILES,
    NESTED_PREFIX,
    NEWLINE_DIR,
    REAL_CHANGE,
    GitRepo,
    blob,
    commit_entries,
    make_repo,
    plant_refs,
    version_shim,
)

__all__ = [
    "C1005_MEMBERS",
    "HOSTILE_FILES",
    "NESTED_PREFIX",
    "NEWLINE_DIR",
    "REAL_CHANGE",
    "GitRepo",
    "blob",
    "commit_entries",
    "make_repo",
    "plant_refs",
    "version_shim",
]
