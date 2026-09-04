"""C-1042 — `nox-review`'s `SKILL.md` is the whole consumer contract.

Docs-checks, so every assertion is derivable from something else in the tree:
the scope words and the flag set come out of `cli.py` by `ast`, the harness
names out of `nox.adapters.ADAPTERS`, the version out of `nox.__version__`.
Nothing here hardcodes a value the code owns — a CLI change or a fifth adapter
must break this file rather than silently drift from the shipped skill.

`nox/publish.toml`'s `version` is deliberately not asserted: it is a
placeholder that `publish.yml`'s `--version <tag>` overrides at release.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import get_args, get_type_hints

import pytest

import nox
from nox.adapters import ADAPTERS
from nox.capability import Enforcement
from nox.cli import EXIT_CODES
from nox.config import ALLOWLIST, CONFIG_NAME, DEFAULT_TIMEOUT_S, MIN_TIMEOUT_S, PERMISSION_KEYS
from nox.liveness import SILENCE_S, Liveness
from nox.log import CALL_LOG_NAME
from nox.outcome import FailureReason, Finding, Status
from scripts import build_pyz

NOX = Path(__file__).resolve().parents[2]
SKILL_DIR = NOX / "nox-review"
SKILL = SKILL_DIR / "SKILL.md"
CLI_SOURCE = (NOX / "src" / "nox" / "cli.py").read_text(encoding="utf-8")
TEXT = SKILL.read_text(encoding="utf-8")


def _split() -> tuple[dict[str, str], dict[str, str], str]:
    """Hand-parse the flat frontmatter and return `(top, metadata, body)`.

    No YAML dependency: nox ships zero runtime dependencies and its dev extra
    carries no parser either. The frontmatter is flat `key: value` with one
    nested `metadata:` block, which is a five-line parse.
    """
    lines = TEXT.split("\n")
    assert lines[0] == "---", "SKILL.md does not open with frontmatter"
    end = lines.index("---", 1)
    top: dict[str, str] = {}
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        nested = line[:1].isspace()
        key, _, value = line.strip().partition(":")
        target = metadata if nested else top
        target[key.strip()] = value.strip().strip('"').strip("'")
    return top, metadata, "\n".join(lines[end + 1 :])


TOP, METADATA, BODY = _split()


def _add_argument_calls() -> list[ast.Call]:
    return [
        node
        for node in ast.walk(ast.parse(CLI_SOURCE))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
    ]


def _flags(call: ast.Call) -> list[str]:
    return [arg.value for arg in call.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]


def _scope_choices() -> tuple[str, ...]:
    for call in _add_argument_calls():
        if "--scope" not in _flags(call):
            continue
        for keyword in call.keywords:
            if keyword.arg == "choices":
                elements = getattr(keyword.value, "elts", [])
                return tuple(e.value for e in elements if isinstance(e, ast.Constant) and isinstance(e.value, str))
    raise AssertionError("cli.py has no --scope add_argument carrying choices")


def _parser_flags() -> set[str]:
    return {flag for call in _add_argument_calls() for flag in _flags(call) if flag.startswith("--")}


def _render_labels() -> set[str]:
    """Every labelled line `cli.render` can print, read off its own source (H9).

    The prose block is the consumer's only surface (C-1042(7)), so a label the
    renderer gains has to reach the shipped table — and a hand-written list of
    labels here is blind to exactly that: `confidence:` and `recommendation:`
    were printed to every consumer while this file iterated eight literals that
    did not include them. Every label is literal text in one of `render`'s
    f-strings, so its string constants are the whole domain, and the docstring
    is skipped because it is prose about the labels rather than one of them.

    The stamp's own `mechanism=`/`write=` fields and the `N of M` counts are not
    labels and carry no colon, which is what keeps them out with no exclusion
    list to maintain.
    """
    for node in ast.walk(ast.parse(CLI_SOURCE)):
        if not (isinstance(node, ast.FunctionDef) and node.name == "render"):
            continue
        labels: set[str] = set()
        for statement in node.body[1:] if ast.get_docstring(node) else node.body:
            for constant in ast.walk(statement):
                if isinstance(constant, ast.Constant) and isinstance(constant.value, str):
                    for match in re.finditer(r"(?:^|\s)([a-z][a-z-]*):(?:\s|$)", constant.value):
                        labels.add(match.group(1))
        return labels
    raise AssertionError("cli.py has no render function")


def _count_names() -> set[str]:
    """The words `cli.render`'s `counts:` line prints, read off its own source.

    `_render_labels`' lesson applied to the other enumeration: a hand-written list
    is blind to exactly the drift it exists to catch. The whole line is one
    implicitly concatenated f-string, so its constant parts are `counts: <word>=`,
    ` of `, `  <word>=` — the trailing `=` is what separates a counted word from
    the prose around it, and the `containment:` line is excluded by its own first
    constant rather than by a name list.
    """
    for node in ast.walk(ast.parse(CLI_SOURCE)):
        if not isinstance(node, ast.JoinedStr):
            continue
        constants = [
            part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str)
        ]
        if not constants or not constants[0].startswith("counts: "):
            continue
        return {match.group(1) for text in constants for match in re.finditer(r"([a-z_]+)=", text)}
    raise AssertionError("cli.render prints no `counts:` line")


def _sections() -> dict[str, str]:
    sections: dict[str, str] = {}
    name, buffer = "", []
    for line in BODY.split("\n"):
        if line.startswith("## "):
            sections[name] = "\n".join(buffer)
            name, buffer = line[3:].strip(), []
        else:
            buffer.append(line)
    sections[name] = "\n".join(buffer)
    return sections


def _where(needle: str) -> str:
    """Every section mentioning `needle`, joined — a heading rename must not fail this."""
    hits = [body for body in _sections().values() if needle in body]
    assert hits, f"no section of SKILL.md mentions {needle!r}"
    return "\n".join(hits)


def test_the_skill_file_exists_and_carries_a_body():
    assert SKILL.is_file()
    assert BODY.strip(), "SKILL.md has frontmatter and nothing else"


def test_the_marker_keys_carry_the_scopes_and_the_current_version():
    """C-1033 / C-1042(1): `/hex-init`'s audit scans for exactly these two keys."""
    assert METADATA["hex-adversary-scopes"] == "code-diff,plan-artifact"
    assert METADATA["hex-adversary-version"] == nox.__version__
    assert METADATA["hex-adversary-scopes"].split(",") == list(_scope_choices())


def test_the_body_uses_exactly_the_two_scope_words_the_cli_accepts():
    """C-1042(2): the vocabulary comes from `cli.py`, so a third choice breaks this."""
    choices = _scope_choices()
    assert len(choices) == 2

    used: set[str] = set()
    for match in re.finditer(r"--scope\s+<?([a-z0-9|-]+)>?", BODY):
        used.update(word for word in match.group(1).split("|") if word)
    assert used == set(choices)


def test_the_body_names_no_client_primitive_and_no_model_literal():
    """C-1042(3), and the semantics are a judgment call, so they are stated here.

    - `Bash`, `Read`, `Grep`: case-sensitive **whole word**. Lowercase prose
      ("read the findings") is fine; the capitalized tool name is not.
    - `Skill(`: case-sensitive substring — the call syntax, not the English word.
    - `claude-`, `gpt-`, `opus`, `sonnet`: case-insensitive substring. The bare
      harness keys (`claude`, `codex`, `copilot`, `opencode`) are argument
      *values* and stay legal; `claude-` with the dash is a model literal.

    Scanned over the whole file, frontmatter included: a `description` naming a
    model reaches every catalog listing.
    """
    for word in ("Bash", "Read", "Grep"):
        assert not re.search(rf"\b{word}\b", TEXT), word
    assert "Skill(" not in TEXT
    for literal in ("claude-", "gpt-", "opus", "sonnet"):
        assert literal not in TEXT.lower(), literal


def test_the_body_spells_one_command_shape():
    """C-1042(4): an absolute `<skill-dir>` path, never a relative `scripts/…`."""
    assert re.search(r"python3\s+<skill-dir>/scripts/nox\.pyz\s+review", BODY)
    for flag in ("--scope", "--harness", "--exclude", "--authored-by", "--repo"):
        assert flag in BODY, flag
    assert not re.search(r"python3\s+nox\.pyz", BODY)
    assert not re.search(r"python3\s+scripts/nox\.pyz", BODY)


def test_every_flag_the_body_names_exists_in_the_parser():
    """C-1042(4): a documented flag that argparse rejects is the failure here.

    Lines mentioning `grim` are skipped — the `<skill-dir>` fallback quotes
    `grim status --format json`, whose flags belong to a different CLI.
    """
    named: set[str] = set()
    for line in BODY.split("\n"):
        if "grim" in line:
            continue
        named.update(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", line))
    assert named
    assert named <= _parser_flags(), sorted(named - _parser_flags())


def test_the_skill_directory_rule_and_its_grim_fallback_are_both_stated():
    """C-1042(4): grim installs under client-specific roots with no stable path.

    The fallback is a real traversal of `grim status --format json` (probed on
    grim 0.14.0): top-level `items[]`, the entry whose `name` is `nox-review`,
    that entry's `outputs[]` entries' `path`.
    """
    assert "<skill-dir>" in BODY
    fallback = _where("grim status --format json")
    for token in ("items", "name", "nox-review", "outputs", "path"):
        assert token in fallback, token


def test_the_repository_under_review_rule_is_stated():
    """C-1042(4): `--repo` when given, the current directory otherwise."""
    assert re.search(r"--repo.{0,400}?current\s+(working\s+)?director", BODY, re.S | re.I) or re.search(
        r"current\s+(working\s+)?director.{0,400}?--repo", BODY, re.S | re.I
    )


def test_the_documented_invocation_resolves_the_repository_from_repo_and_from_the_cwd(tmp_path):
    """C-1042(4)'s acceptance clause, run against the real zipapp rather than grepped.

    "from a cwd outside both the repo and the skill directory with `--repo`, and
    from the repo root without it". Repository resolution runs ahead of harness
    validation, so one deliberately invalid `--harness`/`--exclude` pair
    separates the two answers with no harness installed, no network and no skip:
    `invalid_config` is the refusal only a *resolved* repository reaches, and
    `isolation_failed` is what an unresolved one gives instead.

    The archive is built into `tmp_path`, never read off `nox/nox-review/scripts/`
    — the release gate builds that *after* `task nox:verify`, so a suite that
    depended on it would be green-by-skip on exactly the run that matters.
    """
    pyz = tmp_path / "nox.pyz"
    build_pyz.build(NOX / "src" / "nox", pyz)

    harness, other = sorted(ADAPTERS)[:2]
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
        "GIT_AUTHOR_NAME": "nox",
        "GIT_AUTHOR_EMAIL": "noreply@nox",
        "GIT_COMMITTER_NAME": "nox",
        "GIT_COMMITTER_EMAIL": "noreply@nox",
    }
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    for arguments in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-qm", "c")):
        done = subprocess.run(["git", *arguments], cwd=str(repo), env=env, capture_output=True, text=True, check=False)
        assert done.returncode == 0, done.stderr

    def reason(cwd: Path, *arguments: str) -> str:
        result = subprocess.run(
            [sys.executable, str(pyz), "review", "--scope", "code-diff", *arguments],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        match = re.search(r"reason: (\S+)", result.stdout)
        assert match, result.stdout + result.stderr
        return match.group(1)

    # `--exclude` equal to `--harness` (C-1042(6)) is a refusal reached only once
    # the repository is resolved, so it is what proves each resolution path works.
    assert reason(outside, "--repo", str(repo), "--harness", harness, "--exclude", harness) == "invalid_config"
    assert reason(repo, "--harness", harness, "--exclude", harness) == "invalid_config"
    # The same run against a directory that is not a repository stops earlier.
    assert reason(outside, "--repo", str(outside), "--harness", harness, "--exclude", other) == "isolation_failed"
    assert reason(outside, "--harness", harness, "--exclude", other) == "isolation_failed"


def test_harness_precedence_points_at_the_generated_list_and_ships_no_default():
    """C-1042(5) + E14: the refusal names every registered key, and it GENERATES that list.

    The body may not carry its own copy of the registry. C-1042(5) puts the
    enumeration in the error message precisely so a fifth adapter needs no edit,
    and a hand-written copy in a shipped doc is false from the moment it lands.
    Naming a key as *guidance* (C-1042(9)'s `copilot`/`opencode` same-backend
    point) stays legal; enumerating the registry where the precedence is
    explained does not.
    """
    harness = _where("--harness")
    assert "[review] harness" in harness
    assert re.search(r"no\s+(shipped\s+)?default", harness, re.I)
    assert re.search(r"(every|all)\s+harness(es)?\s+registered|registered harness(es)?", harness, re.I)
    copied = sorted(key for key in ADAPTERS if re.search(rf"\b{key}\b", harness))
    assert copied == [], copied


def test_both_nox_toml_layers_are_named_as_harness_sources():
    """`config.load` reads two files; a body naming only the repository's hides the trusted one."""
    harness = _where("[review] harness")
    assert CONFIG_NAME in harness
    assert "user-level" in harness
    assert re.search(r"upward|above", harness)


def test_the_containment_claim_does_not_outrun_the_mechanism():
    """H11: the minimal environment deliberately forwards `HOME` and the config-dir vars.

    "not your credentials" shipped here while `ALLOWLIST` carried `HOME` and
    `CLAUDE_SECURESTORAGE_CONFIG_DIR` — without which every claude review refused
    `UNAUTHENTICATED`. In a security product the sentence may not outrun the
    mechanism, so the body has to name the forwarding and the enforcement levels
    rather than promise a containment nothing establishes.
    """
    assert "HOME" in ALLOWLIST
    # `nox/README.md` is the OCI package description, so it carries the same
    # sentence to the same reader and is held to the same standard.
    readme = (NOX / "README.md").read_text(encoding="utf-8")
    for text in (BODY, readme):
        assert re.search(r"\bHOME\b", text)
        for level in get_args(Enforcement):
            assert f"`{level}`" in text, level
    assert not re.search(r"(not|never|nor)\s+your\s+credential", TEXT + readme, re.I)


def test_the_call_log_is_documented_rather_than_denied():
    """C-1021: every run appends to it, so "it never edits anything" was false."""
    assert CALL_LOG_NAME in BODY
    assert not re.search(r"never\s+(edits|writes|changes)\s+anything", BODY, re.I)


def test_the_prerequisites_a_first_run_needs_are_stated():
    """D-s and D-j: the launcher route and the platform cut are discoverable nowhere else.

    `launcher` is trust-gated, so the *user-level* file is its only home — a
    reader told to put it in the repository's `nox.toml` watches it get dropped
    with a warning and no launcher.
    """
    assert "launcher" in PERMISSION_KEYS
    launcher = _where("launcher")
    assert "user-level" in launcher
    assert CONFIG_NAME in launcher
    assert "POSIX" in BODY
    assert "Windows" in BODY


def test_the_timeout_expectation_and_the_caller_side_trap_are_stated():
    """C-1010: a caller's own 120 s subprocess bound kills a review nox would have finished."""
    assert str(DEFAULT_TIMEOUT_S) in BODY
    assert str(SILENCE_S[Liveness.SEMANTIC]) in BODY
    assert str(MIN_TIMEOUT_S) in BODY
    assert re.search(r"(caller|your own|subprocess)[^.]{0,120}timeout[^.]{0,160}kill", BODY, re.I | re.S)


def test_the_documented_output_shape_carries_every_line_the_renderer_prints():
    """H14: `detail:` is the only actionable content on every failure path, and `counts:` the enumerations.

    H9: the label set is READ OUT OF `cli.render`, never listed here. A literal
    tuple is invisible to exactly the drift it exists to catch — `confidence:`
    and `recommendation:` were printed to every consumer while this test iterated
    eight labels that did not include them and passed. `_render_labels` returns
    what the renderer can emit, so a ninth label fails here until the shipped
    doc names it.
    """
    labels = _render_labels()
    assert labels, "no labelled line was found in cli.render"
    for label in sorted(labels):
        assert f"`{label}:`" in BODY, label


def test_every_word_the_counts_line_prints_is_defined_where_it_is_printed():
    """W8: the row defined only `omitted`, and one of the other two had a second meaning.

    `neutralized` is the by-NAME drop (instruction, hook and agent-config files);
    `filtered` is the by-MODE one (symlinks and submodules). The opening paragraph
    called the by-name drop "filtered", so on a repository whose symlink is present
    on both ends — `filtered_changed` empty, no `[*/nox]` completeness finding —
    `counts: filtered=1 of 1` was the only channel that word reached the consumer
    on, and it read as "one instruction file removed".

    The names come out of `cli.render`, and the second half is the guard that
    actually holds the vocabulary: `filter` may appear in no section but the one
    that defines it, and not in the catalog `description` either.
    """
    names = _count_names()
    counts = _where("`counts:`")
    assert len(names) == 3, sorted(names)
    for name in sorted(names):
        assert f"`{name}` is" in counts, name

    defining = [section for section, body in _sections().items() if "`filtered` is" in body]
    assert len(defining) == 1, defining
    for section, body in _sections().items():
        assert section in defining or not re.search(r"filter", body, re.I), section
    assert not re.search(r"filter", TOP["description"], re.I)


def test_the_finding_tag_names_its_two_origins_and_which_one_is_untrusted():
    """C-1019: the blanket notice wrongly covers `origin=nox`, which is nox's own finding."""
    origins = get_args(get_type_hints(Finding)["origin"])
    tag = _where("[severity/origin]")
    for origin in origins:
        assert f"`{origin}`" in tag, origin


def test_a_non_ok_status_is_the_skip_and_the_whole_failure_vocabulary_is_listed():
    """B2: with the harness absent, nox answers `error`/`absent` with zero findings.

    A consumer that gates on "triage is complete" passed that gate with nothing
    triaged and no skip logged, because the contract never said an empty finding
    list can mean no review happened.
    """
    assert re.search(r"other than\s+`ok`[^.]{0,160}skip", BODY, re.S | re.I)
    for status in get_args(Status):
        assert f"`{status}`" in BODY, status
    for reason in FailureReason:
        assert f"`{reason.value}`" in BODY, reason.value


def test_the_exit_code_contract_is_stated():
    """`cli.EXIT_CODES` is what a caller's automation branches on."""
    for status, code in EXIT_CODES.items():
        # `[\s\S]` rather than `[^\n]`: the body is wrapped prose, so the pair
        # straddles a line break as often as not.
        assert re.search(rf"`{code}`[\s\S]{{0,60}}`{status}`", BODY), status


def test_the_body_states_no_numeric_count_of_harnesses():
    """E14: a fifth adapter must need no edit here, so "four" may not appear.

    Both directions, because "four harnesses" and "harnesses (four today)" are
    the same mistake. "one" is deliberately absent from the pattern: C-1042(9)'s
    guidance says "any harness other than the one you are running as", which is
    a reference, not a count.
    """
    number = r"(?:\d+|two|three|four|five|six|seven|eight|nine)"
    assert not re.search(rf"\b{number}\b[\w\s,]{{0,24}}harness", BODY, re.I)
    assert not re.search(rf"harness(?:es)?\b[\w\s,]{{0,24}}\b{number}\b", BODY, re.I)


def test_the_three_exclude_outcomes_and_the_undetectable_client_are_stated():
    """C-1042(6): unknown ⇒ refusal, equal to `--harness` ⇒ refusal, absent ⇒ warning."""
    exclude = _where("--exclude").lower()
    assert "unknown" in exclude
    assert re.search(r"same|equal|identical", exclude)
    assert "warn" in exclude
    assert re.search(
        r"(cannot|can't|no way to|does not|doesn't|unable to)[^.]{0,80}detect[^.]{0,100}client",
        BODY,
        re.I | re.S,
    )


def test_the_pick_a_harness_guidance_prefers_a_different_model():
    """C-1042(9): `copilot` and `opencode` can resolve to the same backend (D-ab)."""
    guidance = _where("different model")
    assert re.search(r"different\s+model", guidance, re.I)
    assert "harness" in guidance


def test_findings_are_declared_untrusted_prose_rather_than_json():
    """C-1019 + C-1042(7): the caller gets prose, and it is reviewer output."""
    assert "untrusted reviewer output" in BODY.lower()
    assert re.search(r"prose", BODY, re.I)
    assert re.search(r"(no|not|never)\s+\w*\s*json", BODY, re.I)


@pytest.mark.skipif(shutil.which("grim") is None, reason="grim is not installed")
def test_grim_build_accepts_the_skill():
    """C-1042(8): grim exits 65 on a validation failure."""
    result = subprocess.run(
        ["grim", "build", "nox/nox-review"],
        cwd=str(NOX.parent),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("grim") is None, reason="grim is not installed")
def test_grim_packs_the_pyz_asset_into_the_skill_layer(tmp_path):
    """The published skill must carry the interpreter payload, not just the prose.

    The plan asked for this to be read off `task publish -- --dry-run`, which is
    not implementable: grim 0.14.0 emits no member list in either `--format
    json` output. The layer digest is the observable that does move — build the
    same skill directory with and without a non-empty `scripts/nox.pyz` and the
    two digests differ iff the asset is packed. Never skipped when grim is
    present: in CI this is the only proof the shipped skill is executable.
    """

    def layer_digest() -> str:
        result = subprocess.run(
            ["grim", "build", "nox-review", "--format", "json"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)["layer_digest"]

    staged = tmp_path / "nox-review"
    shutil.copytree(SKILL_DIR, staged)
    shutil.rmtree(staged / "scripts", ignore_errors=True)
    without_asset = layer_digest()

    (staged / "scripts").mkdir()
    (staged / "scripts" / "nox.pyz").write_bytes(b"#!/usr/bin/env python3\n" + b"payload" * 64)
    assert without_asset != layer_digest()
