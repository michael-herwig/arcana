#!/usr/bin/env python3
"""Insert one freshly generated changelog section into an existing CHANGELOG.md.

`release:changelog` calls this instead of git-cliff's own `--prepend`, which
re-emits the `[changelog]` header on every render and glues the new section
above the file's own title — two headers after one run, three after two.

Released sections here are hand-authored prose: the `0.3.0` notes in
`hex/CHANGELOG.md` describe what shipping nox means, and nothing generated from
commit subjects would say it. So the rule is the opposite of regeneration:
everything already in the file is frozen, and exactly one section is added above
the newest one.

Three cases the insert has to get right, all reachable from a plain
`task release:changelog`:

- an **empty** section — no commits under this bundle's paths since the last tag
  — is dropped rather than inserted as a bare heading with nothing under it;
- a rolling `## [Unreleased]` is **replaced**, never stacked, so repeated runs
  converge instead of growing;
- a heading the file **already carries** is left alone — nothing added and
  nothing removed — which is what freezes a released section and makes
  re-cutting the same tag a no-op. `Unreleased` is the exception, because it is
  the one heading that is *meant* to be rewritten.

Self-check: `python3 taskfiles/changelog.py --self-check`.
"""

from __future__ import annotations

import pathlib
import re
import sys

UNRELEASED = re.compile(r"\n## \[Unreleased\].*?(?=\n## \[|\Z)", re.S)
"""One rolling section, from its heading to the next one or to end of file."""


def insert(old: str, section: str) -> str:
    """Return `old` with `section` above its newest version heading.

    Args:
        old: The current changelog, header and all.
        section: What git-cliff rendered, with the header stripped.

    Returns:
        The new changelog, or `old` unchanged where the section is empty or its
        heading is already present.
    """
    section = section.strip()
    if "### " not in section:
        return old
    # `## [0.3.0]` and not the whole heading line: git-cliff dates a section the
    # day it renders it, and a hand-authored `## [0.3.0] - 2026-09-02` re-cut a
    # day later would otherwise look like a different version and be inserted
    # beside itself. The VERSION is the identity; the date is decoration.
    version = section.split("]", 1)[0] + "]"
    if version != "## [Unreleased]" and version in old:
        # Frozen: the file already carries this version. Checked BEFORE the
        # rolling section is stripped, so re-cutting a tag that is already
        # written up by hand cannot silently delete the pending work above it.
        return old
    old = UNRELEASED.sub("", old)
    at = old.find("\n## [")
    if at < 0:
        return f"{old.rstrip()}\n\n{section}\n"
    return f"{old[:at].rstrip()}\n\n{section}\n{old[at:]}"


def _self_check() -> None:
    base = "# Changelog\n\nPreamble.\n\n## [0.3.0] - 2026-09-02\n\nHand-authored.\n"
    new = "## [0.4.0] - 2026-09-10\n\n### Added\n\n- a thing\n"

    out = insert(base, new)
    assert out.startswith("# Changelog\n\nPreamble.\n\n## [0.4.0]"), out
    assert "Hand-authored." in out, "a released section is frozen, never regenerated"
    assert out.index("## [0.4.0]") < out.index("## [0.3.0]"), "newest first"
    assert insert(out, new) == out, "re-cutting a section the file already carries is a no-op"
    assert insert(base, "## [0.4.0] - 2026-09-10\n") == base, "an empty section is dropped"

    pending = insert(base, "## [Unreleased]\n\n### Added\n\n- wip\n")
    frozen = insert(pending, "## [0.3.0] - 2026-09-02\n\n### Added\n\n- from commits\n")
    assert frozen == pending, "freezing a released section removes nothing either"
    later = insert(pending, "## [0.3.0] - 2027-01-01\n\n### Added\n\n- from commits\n")
    assert later == pending, "a section is identified by its VERSION, never by the date beside it"

    again = insert(pending, "## [Unreleased]\n\n### Fixed\n\n- other\n")
    assert again.count("[Unreleased]") == 1, "a rolling section is replaced, not stacked"
    assert "- other" in again and "- wip" not in again, "and replaced by the newer render"
    assert "Hand-authored." in again

    fresh = insert("# Changelog\n\nPreamble.\n", new)
    assert fresh == "# Changelog\n\nPreamble.\n\n## [0.4.0] - 2026-09-10\n\n### Added\n\n- a thing\n", fresh
    print("self-check ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        _self_check()
    else:
        target, rendered = (pathlib.Path(arg) for arg in sys.argv[1:3])
        target.write_text(insert(target.read_text(), rendered.read_text()))
