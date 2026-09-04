"""SD § 9.4 — the adversarial fixture, the regression test for the entire ADR.

One branch carries every hostile feature at once: the seven hostile files, two
of them below the root (one under a directory whose name holds a newline), a set
member committed as a symlink, the three C-1043 escaping symlinks, a
`.gitattributes` smudge filter with a live driver in the repository's own config,
a `core.hooksPath` pointing at a hook that writes a marker, a `160000` submodule
entry with its `.gitmodules`, and both `.nox` shapes.

There is no harness binary here. The "stub harness" is `look_around` — it does
from `ws.path` exactly what a real adversary process would do first (read the
diff, list the tree it was given) — so every assertion is about the `Workspace`
and the checkout, which is where the isolation decision actually lives.

One test per § 9.4 bullet. If this file ever passes with something executing, or
with a clean diff nox never saw, the decision has been undone by a refactor.

A second section follows the fixture tests: the **security-literal oracles**. They
are here rather than beside their modules because this file already holds the only
correct pattern for the job — `ADR_DIRS` below — and the discipline is what the two
halves share, not the subject. See that section's own banner.
"""

import fnmatch
import os
import subprocess

import pytest

from nox.adapters.claude import CONFIG_READS as CLAUDE_CONFIG_READS
from nox.adapters.opencode import OpenCodeAdapter
from nox.api import CREDENTIAL_SHAPES, _scan_for_credentials
from nox.config import ALLOWLIST, NEVER_FORWARD, ConfigError
from nox.harness import NEVER_ALLOWLISTABLE, NEVER_EMITTED, NEVER_SET
from nox.workspace import GITLINK_MODE, SYMLINK_MODE, ReviewTarget, workspace
from tests.fixtures.repo import (
    DOT_NOX_BRANCH,
    E18_ANY_DEPTH,
    E18_ROOT_ONLY,
    NESTED_PREFIX,
    NEWLINE_DIR,
    REAL_CHANGE,
    GitRepo,
    make_repo,
    nox_env,
)

# The C-1005 set, hardcoded from the ADR and E18 — never imported from the code
# under test. A fixture that derives its hostile set from the code proves only
# that the code agrees with itself.
ADR_DIRS = frozenset({".claude", ".opencode", ".codex", ".cursor"})
ADR_FILES = frozenset(
    {
        ".mcp.json",
        "opencode.json",
        "opencode.jsonc",
        "CLAUDE.md",
        "AGENTS.md",
        ".env",
        ".envrc",
        "mise.toml",
        ".mise.toml",
        ".gitattributes",
        ".gitmodules",
        # E18 — basenames, matched at any depth like every other name here.
        "copilot-instructions.md",
        "GEMINI.md",
        "CLAUDE.local.md",
        "AGENTS.override.md",
    }
)
ADR_GLOBS = (".env.*", "*.instructions.md", "*.agent.md")
"""Basename globs. E18 added the last two: `.github/instructions/` and `.github/agents/`."""

ADR_PREFIXES = (
    ".github/skills/",
    ".agents/skills/",
    ".github/hooks/",
    ".github/copilot/",
    ".github/mcp.json",
)
"""E18's root-anchored prefixes — the one clause that is NOT depth-independent.

Anchored because the basename form over-drops: a bare `SKILL.md` would neutralize
every skill in nox's own repository. Sound under C-1003, where the harness's cwd
is the repository root. `.github/` wholesale is deliberately absent — it would
drop `.github/workflows/**`, the supply-chain surface the reviewer must see.
"""

# The seven, as the paths the fixture commits them at. `.codex/` is the symlink
# leg: its payloads live under `docs/build/` and `$HOME/.codex/`, which is what
# the SD § 9.4 "set member committed as a symlink" row is about.
THE_SEVEN = (
    ".claude/settings.json",
    ".claude/skills/lure/SKILL.md",
    ".mcp.json",
    ".opencode/plugins/evil.ts",
    "opencode.json",
    ".codex",
    f"{NESTED_PREFIX}.opencode/plugins/evil.ts",
)


def adr_matches(path: str) -> bool:
    """The ADR's matcher, hand-written here as the oracle for "no neutralization noise".

    Four clauses, the same shape `matches` has: every component against the
    directory set, the basename against the file set and the globs, and the whole
    path against E18's root-anchored prefixes. Case-SENSITIVE on purpose — the
    shipped matcher casefolds because macOS is a supported platform, and the two
    disagreeing there is the deliberate over-drop, not a bug in either.
    """
    parts = path.split("/")
    return (
        any(p in ADR_DIRS for p in parts)
        or parts[-1] in ADR_FILES
        or any(fnmatch.fnmatchcase(parts[-1], glob) for glob in ADR_GLOBS)
        or path.startswith(ADR_PREFIXES)
    )


@pytest.fixture
def hostile(tmp_path) -> GitRepo:
    """The whole of SD § 9.4 on one branch."""
    return make_repo(
        tmp_path,
        untracked=True,
        hostile_root=True,
        hostile_nested=True,
        symlink_members=True,
        escaping_symlinks=True,
        gitlink=True,
        gitattributes_filter=True,
        hooks_path=True,
        dot_nox=True,
    )


def look_around(ws) -> list[str]:
    """The stub harness: read the diff and list the tree, from `ws.path`.

    No binary — the point is that a process starting here sees the neutralized
    checkout and nothing else, and that starting it executes none of the seven.

    It runs under `ws.env` rather than an environment of its own: that is the
    single source C-1031 gives a consumer that shells out, and rebuilding one
    here would exercise a path no adapter is allowed to take.
    """
    ws.diff_path.read_bytes()
    listed = subprocess.run(
        ["git", "-C", str(ws.path), "ls-files", "-z"],
        env=dict(ws.env),
        capture_output=True,
        check=True,
    )
    return [p for p in listed.stdout.decode(errors="replace").split("\0") if p]


def diff_paths(repo: GitRepo, spec: str) -> list[str]:
    out = repo.git("diff", "--no-ext-diff", "--name-only", "-z", spec)
    return [p for p in out.split("\0") if p]


def tree_entries(repo: GitRepo, commitish: str) -> list[tuple[str, str]]:
    raw = repo.git("ls-tree", "-r", "-z", commitish)
    entries: list[tuple[str, str]] = []
    for record in raw.split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        entries.append((meta.split(" ", 1)[0], path))
    return entries


def branch() -> ReviewTarget:
    return ReviewTarget(kind="ref", ref="refs/heads/main")


# ---------------------------------------------------------------------------


def test_none_of_the_seven_executes(hostile):
    """S-1006 / § 9.4: the review completes and none of the seven hostile files runs."""
    assert list(hostile.markers.iterdir()) == []
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        assert list(hostile.markers.iterdir()) == [], "a payload ran while the workspace was built"
        look_around(ws)
        assert list(hostile.markers.iterdir()) == [], "a payload ran when the harness started"
        for rel in THE_SEVEN:
            assert not os.path.lexists(ws.path / rel), rel
    assert list(hostile.markers.iterdir()) == [], "a payload ran during teardown"


def test_at_least_one_hostile_file_below_the_root_is_dropped(hostile):
    """§ 9.4: a root-only reading of C-1005 left `packages/api/.opencode/plugins/evil.ts` in place."""
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        for rel in (f"{NESTED_PREFIX}AGENTS.md", f"{NESTED_PREFIX}.opencode/plugins/evil.ts"):
            assert not os.path.lexists(ws.path / rel), rel
            assert rel in ws.neutralized, rel
        # And the `ls-tree -z` quoting case: a directory name holding a newline.
        # It is REPORTED escaped — C-1028 states `neutralized` verbatim in the
        # prompt, so the raw newline would inject a line there — and DROPPED raw,
        # which is what `-z` exists for.
        assert "pack\\x0aage/.claude/settings.json" in ws.neutralized
        assert not any("\n" in entry for entry in ws.neutralized)
        assert not os.path.lexists(ws.path / NEWLINE_DIR / ".claude" / "settings.json")


def test_the_copilot_instruction_surface_is_gone(hostile):
    """E18: the repo-resident instruction surfaces the S-1015 flag stack does NOT close.

    `--no-custom-instructions` is a flag, and for two of these paths it is not the
    boundary: a live canary planted a project skill under `.github/skills/`, ran
    with the flag set, and found the skill's `description:` verbatim in copilot's
    system prompt — and the model called the skill. So for this surface C-1005 is
    the boundary and neutralization is what closes it.

    Shaped like `test_at_least_one_hostile_file_below_the_root_is_dropped`: absent
    from the checkout AND named in `neutralized`, because a path that is merely
    gone is indistinguishable from one that was never committed, and C-1028 states
    the list verbatim in the prompt so the reviewer knows what it was not shown.
    """
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        planted = [
            *E18_ROOT_ONLY,
            *E18_ANY_DEPTH,
            *(f"{NESTED_PREFIX}{rel}" for rel in E18_ANY_DEPTH),
        ]
        assert planted, "an empty listing would pass silently"
        for rel in planted:
            assert not os.path.lexists(ws.path / rel), rel
            assert rel in ws.neutralized, rel
        # The prefix clause is root-anchored, and that is the whole reason it is a
        # prefix: the same names one directory down are NOT dropped, so nox's own
        # skills and `.agents/plans/` survive a review of this repository.
        assert not any(entry.startswith(f"{NESTED_PREFIX}.github/skills/") for entry in ws.neutralized)
        assert list(hostile.markers.iterdir()) == []


def test_a_set_member_committed_as_a_symlink_is_absent(hostile):
    """§ 9.4: under an on-disk `rm` these survived while being reported as neutralized."""
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        assert not os.path.lexists(ws.path / ".codex")
        assert not os.path.lexists(ws.path / "packages" / "web" / ".claude")
        # Caught twice over, and REPORTED twice over: by name in `neutralized`,
        # and by mode in `filtered` WITH ITS TARGET. C-1043(2) asks for
        # `<path> -> <link target>` for every by-mode drop, and `.codex ->
        # $HOME/.codex` is the Security-H5 shape whose target the reviewer most
        # needs — listing it as the bare string `.codex` threw the target away.
        assert ".codex" in ws.neutralized
        assert "packages/web/.claude" in ws.neutralized
        targets = {entry.split(" -> ", 1)[0]: entry.split(" -> ", 1)[1] for entry in ws.filtered}
        assert targets[".codex"].endswith("/.codex"), targets.get(".codex")
        assert targets["packages/web/.claude"] == "../../docs/build"
        # But neither may force `needs-attention`: a C-1005 member carries no
        # review value, so a branch editing its own `.codex` stays approvable.
        assert not any(entry.startswith((".codex -> ", "packages/web/.claude -> ")) for entry in ws.filtered_changed)
        # The symlink's in-repo payload directory is not itself a set member, so
        # it stays — and is harmless, because nothing named `.claude` points at it.
        assert (ws.path / "docs" / "build" / "settings.json").is_file()


def test_a_committed_dot_nox_directory_and_symlink_capture_nothing(hostile, tmp_path):
    """§ 9.4 / C-1009: the first was a permanent DoS, the second an arbitrary file write."""
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        assert ws.scratch.is_dir() and not ws.scratch.is_symlink()
        assert ws.scratch.name.startswith(".nox-") and ws.scratch.name != ".nox"
        assert ws.diff_path.parent == ws.scratch and ws.diff_path.is_file()
        assert (ws.path / ".nox" / "keep.txt").read_text() == "committed scratch decoy\n"

    with workspace(hostile.path, ReviewTarget(kind="ref", ref=DOT_NOX_BRANCH), env=nox_env(hostile)) as ws:
        assert not os.path.lexists(ws.path / ".nox")
        assert ws.scratch.is_dir() and ws.diff_path.is_file()
    assert not (tmp_path / "hijack").exists()


def test_non_execution_holds_at_every_startup_in_the_workspace(hostile):
    """§ 9.4: asserted at harness startup, not only mid-review — OpenCode loads plugins on any start."""
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        for _ in range(3):
            look_around(ws)
            assert list(hostile.markers.iterdir()) == []
        assert not any(path.is_symlink() for path in ws.path.rglob("*"))


def test_the_diff_carries_the_real_change_and_no_neutralization_noise(hostile):
    """§ 9.4: the on-disk `rm` reviewed seven deletions and approved a change it never saw."""
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        hostile.git("merge-base", "--is-ancestor", ws.base, ws.target)
        for spec in (f"{ws.base}..{ws.target}", f"{ws.base}...{ws.target}"):
            changed = diff_paths(hostile, spec)
            assert set(changed) == set(REAL_CHANGE), spec
            assert not any(adr_matches(path) for path in changed), spec
        body = ws.diff_path.read_bytes()
        assert b"src/feature.py" in body
        assert b".claude" not in body
        assert b"deleted file" not in body


def test_untracked_completeness_names_both_new_files(hostile):
    """§ 9.4 / S-1004: two untracked files present ⇒ `omitted` names both, `approve` is off."""
    with workspace(hostile.path, ReviewTarget(kind="working-tree"), env=nox_env(hostile)) as ws:
        assert set(ws.omitted) == {"notes.txt", "scratch.txt"}
        assert ws.omitted != ()


def test_the_plan_artifact_leg_works_and_refuses_a_bad_path(hostile, tmp_path):
    """§ 9.4 / S-1005: an untracked artifact is present in the workspace; bad paths refuse first."""
    artifact = hostile.toplevel / "notes.txt"
    with workspace(hostile.path, ReviewTarget(kind="plan-artifact", path=artifact), env=nox_env(hostile)) as ws:
        assert ws.omitted == ()
        assert [path for _, path in tree_entries(hostile, ws.target)] == ["notes.txt"]
        assert (ws.path / "notes.txt").read_text() == "untracked note\n"
        assert b"+untracked note" in ws.diff_path.read_bytes()

    outside = tmp_path / "elsewhere.md"
    outside.write_text("# out of tree\n")
    for bad in (hostile.toplevel / "no-such-plan.md", outside):
        with (
            pytest.raises(ConfigError),
            workspace(hostile.path, ReviewTarget(kind="plan-artifact", path=bad), env=nox_env(hostile)),
        ):
            pass  # the context manager never yields
    assert list(hostile.markers.iterdir()) == []


def test_the_gitattributes_smudge_driver_never_runs_during_worktree_add(hostile):
    """§ 9.4: verified as a live defect — the driver executed before neutralization was observable."""
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        assert not (hostile.markers / "smudge").exists()
        assert not os.path.lexists(ws.path / ".gitattributes")
        assert (ws.path / "src" / "app.py").read_text() == "print(2)\n"


def test_the_submodule_surface_is_gone(hostile):
    """§ 9.4: `.gitmodules` absent, no `160000` entry surviving, `git submodule status` empty."""
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        assert not any(mode == GITLINK_MODE for mode, _ in tree_entries(hostile, ws.target))
        assert not any(mode == SYMLINK_MODE for mode, _ in tree_entries(hostile, ws.target))
        assert not os.path.lexists(ws.path / ".gitmodules")
        assert hostile.git("-C", str(ws.path), "submodule", "status") == ""


def test_a_child_process_checkout_fires_no_hook_from_the_shared_config(hostile):
    """§ 9.4: the per-call `-c` form did not prevent this; the environment form does."""
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        subprocess.run(
            ["git", "checkout", "--detach", "HEAD"],
            cwd=ws.path,
            env=dict(ws.env),
            capture_output=True,
            check=True,
        )
        assert list(hostile.markers.iterdir()) == []


def test_the_three_escaping_symlinks_are_absent_and_named_with_their_targets(hostile):
    """§ 9.4 / C-1043: no symlink at all reaches the checkout, and all three stay review evidence."""
    with workspace(hostile.path, branch(), env=nox_env(hostile)) as ws:
        for rel in ("docs/host", "docs/up", "docs/tree"):
            assert not os.path.lexists(ws.path / rel), rel
        rendered = "\n".join(ws.filtered)
        assert "docs/host -> " in rendered
        assert "docs/up -> ../../../" in rendered
        assert "docs/tree -> build" in rendered
        assert "\x1b" not in rendered and "\x00" not in rendered


# ---------------------------------------------------------------------------
# The security-literal oracles.
#
# `ADR_DIRS`/`ADR_FILES` above are the pattern, and this section is that pattern
# applied to the rest of nox's security literals: the expected membership is
# WRITTEN OUT HERE from the ADR, the plan and the errata, and never derived from
# `nox.*`. Each test's docstring names the contract and the record line, so a
# future reader re-derives the set from the design record rather than from the
# code the set is guarding.
#
# The suite these replace imported each constant and then asserted properties OF
# the imported value — `assert NEVER_EMITTED <= DENIED_FLAGS`, `assert NEVER_SET`,
# `@parametrize(sorted(NEVER_EMITTED))`. Every one of those changes with the
# literal, so deleting a member deleted its own guard: a review found six of the
# seven droppable with the suite green.
#
# Two shapes, and each docstring says which it uses and why:
#
#   `==` — the record enumerates the whole set, so nothing may join it silently.
#   `⊇`  — the record states a MINIMUM ("contains at least", "and any future
#          member of that class"). The minimum is still hand-written, so every
#          name the record does specify still kills its own mutant; names beyond
#          it are guarded by whatever pinned them (a committed `--help` fixture,
#          a live probe), not by this file.
#
# `⊇` on a DENY set is fail-safe — a wider refusal refuses more. On the one ALLOW
# set here it is not, so that test bounds the set from above as well.
# ---------------------------------------------------------------------------


def test_the_minimal_environment_forwards_c1008s_infrastructure_and_no_more():
    """C-1008 (ADR :973), through the research table it cites (`nox-security.md:348-376`).

    Bounded from BOTH sides, because this is the section's only allowlist and an
    allowlist's security value is what it excludes: `⊇` alone would pass a set
    that forwarded everything.

    **Below:** C-1008's enumerated infrastructure, minus two removals the record
    makes explicitly — `OPENCODE_AUTH_JSON` (E19: the name is absent from the
    opencode 1.18.22 binary, so C-1008 enumerated a variable no harness reads)
    and the Windows mandatory set `SystemRoot`/`SystemDrive`/`USERPROFILE`/
    `APPDATA`/`LOCALAPPDATA`/`ComSpec`/`PATHEXT` (E6: v1 is POSIX-only, so those
    names are inert rather than shipped).

    **Above:** the widenings past C-1008 that the record actually carries —
    `XDG_CACHE_HOME` for D-s's launcher route (plan :252) and
    `CLAUDE_SECURESTORAGE_CONFIG_DIR` (plan :868, a review finding: without it
    every claude review refused `UNAUTHENTICATED` while the harness was logged
    in) — plus the six that are justified only in `config.ALLOWLIST`'s own
    docstring and in no design record. Listing those six here is not an
    endorsement; it is what makes a SEVENTH silent widening fail, and sends
    whoever wants one back to the record first.

    **The two bounds are joined into an EQUALITY, and that is the enforcement
    C-1008's prose does not carry.** C-1008's own text names neither
    `XDG_CACHE_HOME` nor `CLAUDE_SECURESTORAGE_CONFIG_DIR` — not in its closed
    enumeration and not in the sentence that lists the E48 widenings past it —
    so a reader of the contract alone counts a shipped allowlist seven names
    shorter than the one that ships. E48 recorded that structural half as
    closed; it was not. The upper bound here (`ALLOWLIST - c1008 <=
    recorded_widenings`) also permitted the reverse drift: deleting a recorded
    widening passed silently, which is how `CURL_CA_BUNDLE` went missing once
    already. Equality is the smaller fix than a prose list nothing reads —
    every future edit to `ALLOWLIST`, in EITHER direction, now fails here until
    the name is written down beside its record citation.

    **Exclusions**, hand-written from C-1008's own text: no name it lists as
    never-forwarded (rule 3, ADR :1018), no name matching a `DENY_PATTERNS`
    shape it enumerates, and not `SHELL` — which names an executable a hostile
    `.envrc` can point into the branch (T4b) and which no containment plan reads.
    """
    c1008 = frozenset(
        {
            # Infrastructure (`nox-security.md` "What breaks if you clear too much").
            "PATH",
            "HOME",
            "USER",
            "LOGNAME",
            "TERM",
            "LANG",
            "LC_ALL",
            "TMPDIR",
            # The proxy set, "+ lowercase" per the same table.
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "no_proxy",
            # The CA-bundle set.
            "SSL_CERT_FILE",
            "NODE_EXTRA_CA_CERTS",
            "REQUESTS_CA_BUNDLE",
            # Config roots.
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "CLAUDE_CONFIG_DIR",
            "CODEX_HOME",
        }
    )
    assert c1008 <= ALLOWLIST, sorted(c1008 - ALLOWLIST)

    recorded_widenings = frozenset(
        {
            "XDG_CACHE_HOME",  # plan :252 (D-s launcher route)
            "CLAUDE_SECURESTORAGE_CONFIG_DIR",  # plan :868
            # E48, kept on MEASURED cause — a shipped harness's own code reads
            # each one: `LC_CTYPE` (codex, opencode), the `ALL_PROXY` pair
            # (Claude Code's `HTTPS_PROXY || https_proxy || ALL_PROXY` chain).
            # `TZ` was measured the same way, read by none of the four, and
            # deleted rather than recorded.
            "LC_CTYPE",
            "ALL_PROXY",
            "all_proxy",
            # E48, kept on NAMED cause and deliberately not on measurement: the
            # condition these exist for is a TLS-inspecting proxy with a private
            # CA, which no stock developer machine can produce, so the read
            # measurement returns a false negative rather than an absence of
            # cause. `test_the_ca_bundle_names_are_forwarded_on_named_cause`
            # is what kills a deletion of them.
            "SSL_CERT_DIR",
            "CURL_CA_BUNDLE",
        }
    )
    expected = c1008 | recorded_widenings
    assert ALLOWLIST == expected, {
        "unrecorded widening": sorted(ALLOWLIST - expected),
        "recorded and no longer shipped": sorted(expected - ALLOWLIST),
    }

    for name in (
        "NODE_OPTIONS",
        "LD_PRELOAD",
        "PYTHONSTARTUP",
        "GIT_SSH_COMMAND",
        "GIT_EXTERNAL_DIFF",
        "SSH_AUTH_SOCK",
        "OPENCODE_CONFIG",
        "OPENCODE_CONFIG_CONTENT",
        "OPENCODE_AUTH_CONTENT",
        "OPENCODE_AUTH_JSON",
        "SHELL",
    ):
        assert name not in ALLOWLIST, name

    for shape in (
        "*_TOKEN",
        "*_KEY",
        "*_SECRET",
        "*_PASSWORD",
        "AWS_*",
        "GITHUB_*",
        "GH_*",
        "NPM_*",
        "PYPI_*",
        "OPENAI_*",
        "DATABASE_*",
    ):
        assert [name for name in sorted(ALLOWLIST) if fnmatch.fnmatchcase(name, shape)] == [], shape


def test_never_forward_carries_every_execution_channel_c1034_enumerates():
    """C-1034(1) (plan :385) and E19 — the written-down exclusions.

    `⊇`: the contract's words are "contains at least", and the shipped set is
    wider by `LD_AUDIT`, `LD_LIBRARY_PATH` and `PYTHONPATH` — three more loader
    and interpreter channels of exactly the enumerated class. Wider is fail-safe
    on a deny set, and each of C-1034(1)'s own names still kills its mutant here.

    `OPENCODE_AUTH_CONTENT` is E19's addition and is the one member that is a
    credential rather than an execution channel: on opencode 1.18.22 it carries
    the whole auth store INLINE, and opencode SETS it when it spawns a
    subprocess — so a nox invoked from inside an opencode session would inherit
    the user's store in the ambient environment and hand it to the adversary
    (C-1002). No `DENY_PATTERNS` shape claims that name, so this entry is the
    only thing keeping it out by more than the allowlist's braces.

    `BUN_*` is deliberately NOT expected here: C-1034(1) puts patterned members
    in the separate `NEVER_FORWARD_GLOBS`, and a glob in a set matched by
    equality would be a member that never fires.
    """
    c1034 = frozenset(
        {
            "NODE_OPTIONS",
            "LD_PRELOAD",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
            "PYTHONSTARTUP",
            "GIT_SSH_COMMAND",
            "GIT_EXTERNAL_DIFF",
            "SSH_AUTH_SOCK",
            "OPENCODE_CONFIG",
            "OPENCODE_CONFIG_CONTENT",
            "OPENCODE_AUTH_CONTENT",  # E19
        }
    )
    assert c1034 <= NEVER_FORWARD, sorted(c1034 - NEVER_FORWARD)
    assert "BUN_*" not in NEVER_FORWARD


def test_no_value_carrying_config_flag_is_allowlistable():
    """C-1023 rule 2 (ADR :863) — the class that may never join `PASSTHROUGH_ALLOW`.

    `⊇`: the rule ends "and any future member of that class", so a fifteenth name
    is permitted; the fourteen it enumerates are not droppable, which is what is
    asserted. The shipped set is exactly these fourteen today.

    `--settings` is the one that carries the contract: `--restricted`'s own help
    text states that managed settings and `--settings` **still apply**, so a
    single allowlisted `--settings '{"hooks":…}'` is arbitrary command execution
    surviving the entire `--safe-mode --restricted --strict-mcp-config` stack.
    `-c` is the same shape on Codex, whose help examples are themselves a sandbox
    widening and `shell_environment_policy.inherit=all` — the C-1008 scrub undone
    from inside the child.
    """
    c1023_rule_2 = frozenset(
        {
            "-c",
            "--config",
            "--settings",
            "--setting-sources",
            "--mcp-config",
            "--agents",
            "--plugin-dir",
            "--tools",
            "--permission-mode",
            "--system-prompt",
            "--append-system-prompt",
            "--permission-prompt-tool",
            "--enable",
            "--disable",
        }
    )
    assert c1023_rule_2 <= NEVER_ALLOWLISTABLE, sorted(c1023_rule_2 - NEVER_ALLOWLISTABLE)


def test_nox_never_emits_a_flag_that_lifts_its_own_containment():
    """C-1023's `DENIED_FLAGS` re-scope (ADR :863) plus the plan's two audit rows.

    `⊇`, and by a wide margin: the record names fourteen, the shipped set carries
    fifty. The other thirty-six were pinned by WP7a-d against the committed
    `--help` fixtures (E3) — `fixtures/claude/help-2.1.260.txt`,
    `fixtures/copilot/help-1.0.82.txt` and the opencode 1.18.22 sheet — and it is
    those fixtures, not this file, that guard them. Do not fold them in here from
    the source: copying the literal into the test is the vacuous oracle this
    section exists to remove.

    Sources for the fourteen:

    - **ADR :863**, the re-scoping sentence: `--dangerously-bypass-hook-trust`,
      `--dangerously-bypass-approvals-and-sandbox`,
      `--dangerously-skip-permissions`, `--bare`, `--add-dir`, `--auto`. Hook
      trust matters most — a content hash is the *only* thing between a hostile
      branch and Codex's `SessionStart` hooks.
    - **plan :879** (WP7d's carry-forward row, "`NEVER_EMITTED` misses five words
      Copilot CLI 1.0.82 ships"): `--allow-all`, `--yolo`, `--allow-all-urls`,
      `--allow-all-mcp-server-instructions`, and `-C`. `-C` is the different
      hazard the row calls out: a working-directory bypass escapes C-1003's
      worktree rather than lifting a permission, and derivation cannot see it —
      `Invocation.cwd` still reads `ws.path` and the stamp still says the axis
      holds.
    - **plan :1186-1187**, copilot's permission surface, for the two long forms
      the row above names `--allow-all` an alias of: `--allow-all-tools`,
      `--allow-all-paths`.
    - **plan :875** (WP7c's row): `--no-pure`. It is yargs' negation of `--pure`,
      the whole of opencode's `argv_evidence`; the argv would still carry
      `--pure` contiguously, the axis would still stamp, and last-wins would have
      turned it off.

    `--agent` is shipped in this set and is deliberately NOT expected here:
    C-1025's derivation table has nox EMIT `--agent explore` as half of
    opencode's `attested` mechanism, so the record forbids expecting it. The two
    do not collide in practice only because opencode 1.18.22 rejects `explore` as
    a primary agent and `adapters/opencode.py` documents not emitting it.
    """
    specified = frozenset(
        {
            # ADR :863
            "--dangerously-bypass-hook-trust",
            "--dangerously-bypass-approvals-and-sandbox",
            "--dangerously-skip-permissions",
            "--bare",
            "--add-dir",
            "--auto",
            # plan :879
            "--allow-all",
            "--yolo",
            "--allow-all-urls",
            "--allow-all-mcp-server-instructions",
            "-C",
            # plan :1186-1187
            "--allow-all-tools",
            "--allow-all-paths",
            # plan :875
            "--no-pure",
        }
    )
    assert specified <= NEVER_EMITTED, sorted(specified - NEVER_EMITTED)


def test_no_adapter_may_set_a_loader_hijack_variable():
    """C-1044 (plan :417) — the set rule, over the loader and interpreter channels of C-1034(1).

    `NEVER_SET` is contracted by **C-1044**: an adapter's `Launch` may never set
    one of these, whatever its `ContainmentPlan` declares. C-1044 fixes the
    membership as C-1034(1)'s enumeration narrowed to its loader/interpreter
    class — every name that makes the child run code of the setter's choosing
    before the harness's own first line — so the expected set is written down
    here from the record rather than read back out of `harness.NEVER_SET`.
    That double entry is the whole value of this oracle and is deliberately not
    collapsed into an import: `assert NEVER_SET <= NEVER_SET` checks nothing.
    (E47: until C-1044 was authored, no contract named this set at all and the
    membership was derived from C-1034(1) alone.)

    `⊇`, so a future channel of the same class may join. **Three did (H5):**
    C-1044's own enumeration lists seven names, and E50 records `LD_AUDIT`,
    `LD_LIBRARY_PATH` and `PYTHONPATH` as shipped members of `NEVER_FORWARD`
    past C-1034(1)'s enumeration, "loader and interpreter channels
    indistinguishable in kind from `LD_PRELOAD` and `PYTHONSTARTUP`". They were
    on the inherit list and absent from this one, so an adapter returning
    `Launch(env={"LD_AUDIT": …})` passed `authorize` while C-1044's docstring
    claimed the class was covered in full. Expected here under C-1044's `⊇`
    together with the seven the contract enumerates.

    The negatives are contracted too (C-1044(3)), and they are why these cannot
    be one set with `NEVER_FORWARD`: C-1025's derivation table (ADR :923)
    requires `OPENCODE_CONFIG_CONTENT` **present in `Invocation.env`** for
    opencode's `attested` level on both axes. It is in `NEVER_FORWARD` and must
    never be in `NEVER_SET`, because setting it is precisely opencode's
    containment mechanism — a `NEVER_SET` that swallowed it would make that
    adapter unimplementable while every membership assertion still passed. The
    other three ride with it as the record of the H5 sweep's judgement, so
    "fold `NEVER_FORWARD` in wholesale" is refused by a test rather than by a
    comment: `OPENCODE_CONFIG` is the same mechanism by path, and
    `SSH_AUTH_SOCK` and `OPENCODE_AUTH_CONTENT` are credential channels with no
    load semantics — on the inherit list for C-1007's `AF_UNIX` residual and
    for E19/D-ad respectively, neither of which is an argument about the launch
    path.
    """
    hijack_channels = frozenset(
        {
            "LD_PRELOAD",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
            "NODE_OPTIONS",
            "PYTHONSTARTUP",
            "GIT_SSH_COMMAND",
            "GIT_EXTERNAL_DIFF",
            # E50's three, in the same class and on `NEVER_FORWARD` already.
            "LD_AUDIT",
            "LD_LIBRARY_PATH",
            "PYTHONPATH",
        }
    )
    assert hijack_channels <= NEVER_SET, sorted(hijack_channels - NEVER_SET)
    for held_out in ("OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG", "SSH_AUTH_SOCK", "OPENCODE_AUTH_CONTENT"):
        assert held_out not in NEVER_SET, held_out


def test_every_credential_shape_c1018_names_flags_the_review():
    """C-1018 (ADR :1362) — `raw` is scanned for known credential shapes and the review flagged.

    Asserted through the scanner rather than over the tuple, so it fails on a
    dropped member AND on a scanner that stopped consulting the tuple. Each
    sample is written here from the ADR's own spelling of the shape, embedded in
    surrounding text the way harness output would carry it.

    `⊇` in effect: the ADR writes the PEM shape as `-----BEGIN … PRIVATE KEY`
    and the shipped prefix stops at the armour line, which matches strictly more
    (the key type varies — `RSA`, `OPENSSH`, `EC`). Wider is the safe direction
    for a flag that redacts nothing.

    **Not shipped, and the ADR names it:** C-1018's "and high-entropy tokens".
    `api.CREDENTIAL_SHAPES` carries a `ponytail:` note declining an entropy
    scorer as a false-positive generator over base64 diffs and minified JS. That
    is a recorded decision in the code and an open delta against the ADR text,
    so the negative below asserts only that the four literal shapes do not fire
    on ordinary output — never that high-entropy strings are covered.
    """
    for sample in (
        "listing key AKIAIOSFODNN7EXAMPLE from the profile",
        "token ghp_16C7e42F292c6912E7710c838347Ae178B4a\n",
        'ANTHROPIC_API_KEY="sk-ant-api03-xxxxxxxx"',
        "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaA==\n",
        "-----BEGIN RSA PRIVATE KEY-----",
    ):
        assert _scan_for_credentials(sample), sample

    assert not _scan_for_credentials("verdict: approve — src/feature.py adds one function\n")
    assert CREDENTIAL_SHAPES, "an empty tuple would pass every assertion above vacuously"


def test_claude_declares_the_user_settings_file_c1025_hashes():
    """C-1025 (plan :345) — "claude: `~/.claude/settings.json`" in the probe digest.

    `⊇`: the record names one file per adapter as the minimum; the shipped tuple
    adds the `${CLAUDE_CONFIG_DIR}` form, which WINS when the variable is set and
    which is on the C-1008 allowlist — so declaring only the `$HOME` form would
    hash a file the harness is not reading. `config_read_paths` drops an entry
    whose variable the environment does not carry, and the drop is itself a
    digest factor, so gaining the variable is a cache miss rather than a stale
    pass.

    Written as the `${HOME}`-expandable spelling the plan's `~` abbreviates,
    because that is the shape `CONFIG_READS` is contracted to carry (plan :885,
    "`CONFIG_READS` (`${VAR}`-expandable)").
    """
    assert "${HOME}/.claude/settings.json" in CLAUDE_CONFIG_READS


def test_opencode_declares_the_user_config_files_c1025_hashes():
    """C-1025 (plan :345) — "opencode: `~/.config/opencode/opencode.json[c]`".

    `⊇`, and both members of the `[c]` alternation are required: a review that
    hashed only `opencode.json` would cache a sandbox-probe pass across an edit
    to `opencode.jsonc`, which is the one failure direction C-1025 calls unsafe.
    The shipped tuple adds the `${XDG_CONFIG_HOME}` forms for the same reason
    the claude adapter adds `${CLAUDE_CONFIG_DIR}`.

    The credential store is deliberately absent from the record's minimum and
    from the shipped tuple: it decides whether the harness authenticates, not
    what it is permitted to do, and hashing a secret-bearing file on every launch
    buys nothing for an adapter that never claims `os`. Asserted, so a future
    "hash everything under the config root" edit has to argue with this line.
    """
    for path in (
        "${HOME}/.config/opencode/opencode.json",
        "${HOME}/.config/opencode/opencode.jsonc",
    ):
        assert path in OpenCodeAdapter.CONFIG_READS, path
    assert not any("auth" in entry for entry in OpenCodeAdapter.CONFIG_READS)
