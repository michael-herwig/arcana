"""Config, the trust gate and the minimal environment (C-1002, C-1008, C-1016, C-1017, C-1034).

Two halves, one module, because both are about what a hostile repository is
allowed to influence. The load half is dominated by one ordering rule — drop
untrusted keys first, validate what survives (SD § 5.7) — and the environment
half by one shape: allowlist, then denylist, then inbound rejection, then nox's
own values written last.
"""

import hashlib
import json
import os
import pwd
import subprocess
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from nox import config
from nox.capability import Launcher, ModelSpecT
from nox.config import (
    ALLOWLIST,
    AUTH_ENV_HINTS,
    AUTH_HINT_TRAILER,
    CONFIG_NAME,
    DEFAULT_MAX_PROMPT_BYTES,
    DEFAULT_TIMEOUT_S,
    DENY_PATTERNS,
    GIT_CONFIG_OVERRIDES,
    GIT_PLAIN_ENV,
    INBOUND_PATH_VARS,
    MAX_SEARCH_DEPTH,
    MIN_TIMEOUT_S,
    NEVER_FORWARD,
    NEVER_FORWARD_GLOBS,
    PERMISSION_KEYS,
    REQUIRED_ENV,
    TRUST_GATED_KEYS,
    WORLD_WRITABLE_EXEMPT,
    ConfigError,
    HarnessConfig,
    NoxConfig,
    auth_hint,
    is_trusted,
    load,
    matches_any,
    minimal_env,
    narrow_tools,
    sanitize_path,
    trust_store_path,
    world_writable_forwards,
)
from nox.outcome import NoxError

# Resolved from this file, never from the cwd: pytest may be invoked from the
# repo root or from nox/, and the C-1002 scan is about the nox subtree either way.
NOX = Path(__file__).resolve().parents[2]

# Everything `minimal_env` writes itself at step 7. Subtracted before any
# "only allowlisted names survived" assertion, because nox's own C-1031 set is
# constructed, never forwarded, and is deliberately not on the allowlist.
_NOX_OWNED = (
    frozenset(GIT_PLAIN_ENV)
    | {"GIT_CONFIG_COUNT"}
    | {f"GIT_CONFIG_KEY_{i}" for i in range(len(GIT_CONFIG_OVERRIDES))}
    | {f"GIT_CONFIG_VALUE_{i}" for i in range(len(GIT_CONFIG_OVERRIDES))}
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _tree(tmp_path):
    """A repo, a user config dir and a state dir, none of them inside another.

    Every path is under `tmp_path`: the real `$HOME` is never read and never
    written, which is the whole point of `load`'s two override arguments.
    """
    repo, user, state = tmp_path / "repo", tmp_path / "config", tmp_path / "state"
    for path in (repo, user, state):
        path.mkdir(parents=True, exist_ok=True)
    return repo, user, state


def _load(tmp_path, *, repo_toml=None, user_toml=None):
    repo, user, state = _tree(tmp_path)
    if repo_toml is not None:
        (repo / CONFIG_NAME).write_text(repo_toml)
    if user_toml is not None:
        (user / CONFIG_NAME).write_text(user_toml)
    return load(repo, user_dir=user, state_dir=state)


def _mentions(warnings, needle):
    return [w for w in warnings if needle in w]


def _env_tree(tmp_path):
    """A repo, a *reserved* worktree path, and a home outside both.

    The worktree is deliberately never created: `minimal_env` runs at step 0,
    before `workspace()` exists, and resolves the path without stat-ing it.
    """
    repo, home = tmp_path / "repo", tmp_path / "home"
    for path in (repo, home):
        path.mkdir(parents=True, exist_ok=True)
    return repo, tmp_path / "wt", home


def _parent(home, **extra):
    return {"PATH": os.pathsep.join(["/usr/bin", "/bin"]), "HOME": str(home), **extra}


def _src_files():
    """Every file git accounts for under `src/nox`, tracked or untracked-not-ignored.

    `git ls-files` rather than a hand-rolled walk, for `test_hygiene.py`'s
    reason: a prune list wide enough to avoid a stray virtualenv can also hide
    a real hit.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "src/nox"],
        cwd=NOX,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [NOX / name for name in listed.split("\0") if name]


# ── The shipped literals ─────────────────────────────────────────────────────


def test_config_error_is_a_nox_error():
    # C-1029: `review()` catches `NoxError` and never lets one escape, so a
    # `ConfigError` outside that hierarchy would be an uncaught exception.
    assert issubclass(ConfigError, NoxError)


def test_permission_keys_is_the_shipped_five():
    # C-1016 fixes the fail-hard surface at exactly these five. A literal, not a
    # heuristic, or the asymmetry degrades into a judgment call at every new key.
    assert PERMISSION_KEYS == frozenset({"read_only", "tools_allowed", "passthrough", "isolation", "launcher"})


def test_model_is_deliberately_not_a_permission_key():
    # C-1030 rule 5: every default for `model` is a real model rather than a
    # guess about a control, so failing hard there would hand `model = "garbage"`
    # the same denial of service C-1017 closes.
    assert "model" not in PERMISSION_KEYS


def test_trust_gated_keys_is_the_permission_set_plus_the_model_channel():
    # The two sets are genuinely different (C-1030 rule 5's second half), and
    # `effort` joins the literal because it is the same argv-word channel.
    assert TRUST_GATED_KEYS == PERMISSION_KEYS | {"model_literal", "effort"}


def test_harness_config_fields():
    assert tuple(f.name for f in fields(HarnessConfig)) == (
        "model",
        "model_literal",
        "effort",
        "read_only",
        "timeout",
        "tools_allowed",
        "launcher",
        "passthrough",
    )


def test_isolation_is_a_config_key_but_not_a_stored_field():
    # A stored value no branch consults is a control nothing enforces; the key
    # still exists so a trusted file supplying anything but "worktree" raises.
    assert "isolation" in PERMISSION_KEYS
    assert "isolation" not in {f.name for f in fields(HarnessConfig)}


def test_harness_config_defaults_are_the_restrictive_ones():
    cfg = HarnessConfig()
    assert (cfg.model, cfg.model_literal, cfg.effort) == (None, None, None)
    assert cfg.read_only is True
    assert cfg.timeout == DEFAULT_TIMEOUT_S
    assert (cfg.tools_allowed, cfg.launcher, cfg.passthrough) == (None, None, ())


def test_harness_config_is_frozen():
    with pytest.raises(FrozenInstanceError):
        setattr(HarnessConfig(), "read_only", False)  # noqa: B010 — a direct assignment is a type error, not a runtime one


def test_nox_config_fields_and_defaults():
    cfg = NoxConfig()
    assert tuple(f.name for f in fields(NoxConfig)) == ("review_harness", "max_prompt_bytes", "harnesses")
    assert cfg.review_harness is None
    assert cfg.max_prompt_bytes == DEFAULT_MAX_PROMPT_BYTES
    assert dict(cfg.harnesses) == {}


def test_nox_config_is_frozen_all_the_way_down():
    # `frozen=True` on the dataclass is undone by a live handle to the mapping,
    # which is why the field is wrapped rather than merely typed as a Mapping.
    cfg = NoxConfig()
    with pytest.raises(FrozenInstanceError):
        setattr(cfg, "review_harness", "codex")  # noqa: B010 — a direct assignment is a type error, not a runtime one
    with pytest.raises(TypeError):
        cfg.harnesses["claude"] = HarnessConfig()  # pyright: ignore[reportIndexIssue]


def test_for_harness_returns_the_defaults_for_an_absent_section():
    assert NoxConfig().for_harness("claude") == HarnessConfig()


# ── load: unknown keys, and the C-1017 order ─────────────────────────────────


def test_no_config_files_yields_defaults_and_no_warnings(tmp_path):
    cfg, warnings = _load(tmp_path)
    assert cfg == NoxConfig()
    assert warnings == ()


def test_an_unknown_key_warns_and_is_ignored(tmp_path):
    # C-1016 fail-soft: an unknown key is a forward-compatibility signal that
    # changes nothing about the enforced boundary.
    cfg, warnings = _load(tmp_path, repo_toml='[harness.claude]\nfrobnicate = "yes"\n')
    assert cfg.for_harness("claude") == HarnessConfig()
    assert _mentions(warnings, "frobnicate")


def test_an_unknown_top_level_key_warns_and_is_ignored(tmp_path):
    cfg, warnings = _load(tmp_path, repo_toml='frobnicate = "yes"\n')
    assert cfg == NoxConfig()
    assert _mentions(warnings, "frobnicate")


def test_an_unknown_key_in_the_review_section_warns_and_is_ignored(tmp_path):
    # A third scope, and the only one no other scan reaches: `review` is itself
    # a known top-level key, so the whole-file scan passes it and says nothing
    # about what is inside it. Without this the `[review]` scan is a line the
    # suite cannot tell from a deletion.
    cfg, warnings = _load(tmp_path, repo_toml='[review]\nfrobnicate = "yes"\n')
    assert cfg == NoxConfig()
    assert _mentions(warnings, "frobnicate")
    assert _mentions(warnings, "[review]")


def test_an_unknown_key_in_the_trusted_user_file_warns_rather_than_raising(tmp_path):
    # Fail-soft is a property of the key, not of the file's trust: only a
    # *permission* key fails hard.
    cfg, warnings = _load(tmp_path, user_toml='[harness.claude]\nfrobnicate = "yes"\n')
    assert cfg.for_harness("claude") == HarnessConfig()
    assert _mentions(warnings, "frobnicate")


_MALFORMED_PERMISSION_VALUES = {
    "read_only": '"yes"',
    "tools_allowed": '"Read"',
    "passthrough": "3",
    "isolation": '"in-tree"',
    "launcher": "7",
}


def test_the_malformed_permission_cases_cover_every_permission_key():
    # C-1016 fixes the set at five; a sixth key must fail here rather than ship
    # with no fail-hard test of its own.
    assert set(_MALFORMED_PERMISSION_VALUES) == PERMISSION_KEYS


@pytest.mark.parametrize(("key", "value"), sorted(_MALFORMED_PERMISSION_VALUES.items()))
def test_a_malformed_permission_value_in_the_trusted_user_file_raises(tmp_path, key, value):
    # CWE-1188: every possible default on this surface is a guess about a
    # security control, and the user expressed an intent nox cannot read.
    with pytest.raises(ConfigError) as excinfo:
        _load(tmp_path, user_toml=f"[harness.claude]\n{key} = {value}\n")
    assert key in str(excinfo.value)


@pytest.mark.parametrize(("key", "value"), sorted(_MALFORMED_PERMISSION_VALUES.items()))
def test_a_malformed_permission_value_in_a_repo_local_file_is_dropped_not_raised(tmp_path, key, value):
    """The C-1017 / SD § 5.7 order test — drop first, then validate what survives.

    Validating first reopens T6 completely: `read_only = "yes"` in a hostile
    repo `nox.toml` is a malformed value on a permission key, so `ConfigError`
    fires and nox never runs, and a review that never runs is a review that
    never objects. The drop is the fail-closed direction because nox's own
    defaults are the restrictive ones.
    """
    cfg, warnings = _load(tmp_path, repo_toml=f"[harness.claude]\n{key} = {value}\n")
    assert cfg.for_harness("claude") == HarnessConfig()
    assert _mentions(warnings, key)


_TRUST_GATED_VALUES = {
    "read_only": "true",
    "tools_allowed": '["Read"]',
    "passthrough": '["--dangerously-skip-permissions"]',
    "isolation": '"worktree"',
    "launcher": '["ocx", "package", "exec", "pkg", "--"]',
    "model_literal": '"sonnet"',
    "effort": '"high"',
}


def test_the_trust_gated_cases_cover_every_gated_key():
    assert set(_TRUST_GATED_VALUES) == TRUST_GATED_KEYS


@pytest.mark.parametrize(("key", "value"), sorted(_TRUST_GATED_VALUES.items()))
def test_every_trust_gated_key_is_dropped_and_warned_from_a_repo_local_file(tmp_path, key, value):
    """D-w: v1 ships no trust-granting command, so there is no path to trust it.

    The value used here is *well-formed* in every case — the drop is
    unconditional on the file's trust, not a consequence of the value being
    malformed. `is_trusted`'s store route is exercised on its own below; nothing
    in v1 writes an entry, so at load time the answer is always "dropped".
    """
    cfg, warnings = _load(tmp_path, repo_toml=f"[harness.claude]\n{key} = {value}\n")
    assert cfg.for_harness("claude") == HarnessConfig()
    assert _mentions(warnings, key)


def test_a_repo_local_file_may_supply_the_non_gated_keys_freely(tmp_path):
    cfg, warnings = _load(
        tmp_path,
        repo_toml='[review]\nharness = "codex"\n\n[harness.claude]\nmodel = "deep-reasoning"\ntimeout = 60\n',
    )
    assert cfg.review_harness == "codex"
    assert cfg.for_harness("claude").model == "deep-reasoning"
    assert cfg.for_harness("claude").timeout == 60
    assert warnings == ()


def test_repo_local_non_gated_keys_override_the_user_level_ones(tmp_path):
    cfg, _warnings = _load(
        tmp_path,
        user_toml="[harness.claude]\ntimeout = 111\n",
        repo_toml="[harness.claude]\ntimeout = 222\n",
    )
    assert cfg.for_harness("claude").timeout == 222


def test_the_user_level_file_keeps_its_trust_gated_keys_when_the_repo_supplies_none(tmp_path):
    # D-s: the launcher lives in the user-level file, and requiring a separate
    # blessing there would make it unusable out of the box.
    cfg, warnings = _load(
        tmp_path,
        user_toml='[harness.opencode]\nlauncher = ["ocx", "package", "exec", "pkg", "--"]\n',
    )
    assert cfg.for_harness("opencode").launcher == ("ocx", "package", "exec", "pkg", "--")
    assert warnings == ()


def test_a_repo_local_gated_key_does_not_override_the_trusted_one(tmp_path):
    # The drop must not degrade into "the repo wins by emptying the field".
    cfg, warnings = _load(
        tmp_path,
        user_toml='[harness.opencode]\nlauncher = ["ocx", "--"]\n',
        repo_toml='[harness.opencode]\nlauncher = ["/tmp/evil", "--"]\n',
    )
    assert cfg.for_harness("opencode").launcher == ("ocx", "--")
    assert _mentions(warnings, "launcher")


def test_read_only_false_raises_naming_c1003_and_c1007(tmp_path):
    # There is no in-tree mode in v1, so the only alternatives were refusing
    # every launch and silently ignoring the key. A loud refusal beats both.
    with pytest.raises(ConfigError) as excinfo:
        _load(tmp_path, user_toml="[harness.claude]\nread_only = false\n")
    assert "C-1003" in str(excinfo.value)
    assert "C-1007" in str(excinfo.value)


def test_read_only_false_in_a_repo_local_file_is_dropped_before_it_can_raise(tmp_path):
    # Same ordering rule: the raise applies "wherever it survives the drop",
    # and in an untrusted file it never does.
    cfg, warnings = _load(tmp_path, repo_toml="[harness.claude]\nread_only = false\n")
    assert cfg.for_harness("claude").read_only is True
    assert _mentions(warnings, "read_only")


def test_the_dropped_read_only_warning_points_at_no_file_that_would_accept_it(tmp_path):
    # W9: `read_only` is the one trust-gated key with no trusted home — v1's domain
    # is `{True}` on BOTH tiers — so the shared "an untrusted nox.toml may not supply
    # it" wording read as "put it in the user-level file", which is exactly where
    # the test two above proves the same value raises instead.
    _, warnings = _load(tmp_path, repo_toml="[harness.claude]\nread_only = false\n")
    (warning,) = _mentions(warnings, "read_only")
    assert "may not supply it" not in warning
    assert "no in-tree mode" in warning
    assert "cannot supply one either" in warning


# ── load: models, effort, timeout ────────────────────────────────────────────


@pytest.mark.parametrize("model_class", ["fast-balanced", "deep-reasoning"])
def test_a_known_model_class_is_kept(tmp_path, model_class):
    cfg, warnings = _load(tmp_path, repo_toml=f'[harness.claude]\nmodel = "{model_class}"\n')
    assert cfg.for_harness("claude").model == model_class
    assert warnings == ()


@pytest.mark.parametrize("value", ['"gpt-5.4"', '"sonnet"', "3", "true"])
def test_an_unrecognized_model_class_warns_and_falls_back_to_the_default(tmp_path, value):
    # C-1030: never a ConfigError here — `model` is not a permission key, and
    # failing hard would hand `model = "garbage"` a one-character DoS.
    cfg, warnings = _load(tmp_path, repo_toml=f"[harness.claude]\nmodel = {value}\n")
    assert cfg.for_harness("claude").model is None
    assert _mentions(warnings, "model")


@pytest.mark.parametrize("value", ["0", "-1", "-900", '"900"', "1.5", "true"])
def test_a_timeout_outside_the_positive_ints_warns_and_falls_back(tmp_path, value):
    """C-1016 fail-soft, and the only gate `TimeoutPolicy.for_kind` does not carry.

    `for_kind(kind, -1)` accepts a negative wall clock silently — a TOML `-1` is
    a well-typed int — so this is the single thing standing between the config
    file and a supervisor whose deadline has already elapsed.
    """
    cfg, warnings = _load(tmp_path, repo_toml=f"[harness.claude]\ntimeout = {value}\n")
    assert cfg.for_harness("claude").timeout == DEFAULT_TIMEOUT_S
    assert _mentions(warnings, "timeout")


def test_a_positive_timeout_above_the_floor_is_kept(tmp_path):
    cfg, warnings = _load(tmp_path, repo_toml=f"[harness.claude]\ntimeout = {MIN_TIMEOUT_S * 2}\n")
    assert cfg.for_harness("claude").timeout == MIN_TIMEOUT_S * 2
    assert warnings == ()


def test_a_repo_local_raise_of_the_timeout_still_works(tmp_path):
    # The floor clamps a value *down* into the domain and never caps one: a
    # repository asking for a longer wall clock is the legitimate case.
    cfg, warnings = _load(tmp_path, repo_toml=f"[harness.claude]\ntimeout = {DEFAULT_TIMEOUT_S * 3}\n")
    assert cfg.for_harness("claude").timeout == DEFAULT_TIMEOUT_S * 3
    assert warnings == ()


@pytest.mark.parametrize("value", [1, MIN_TIMEOUT_S - 1])
def test_a_timeout_below_the_floor_is_clamped_and_warned_not_refused(tmp_path, value):
    """T6 through the one key the C-1017 drop rule does not cover.

    `timeout = 1` is a well-typed positive int, so fail-soft never sees it, and
    it denies every review of the branch that ships it. Refusing it would hand
    the same one-character denial of service straight back, so the value is
    raised to the floor and the correction is stamped.
    """
    cfg, warnings = _load(tmp_path, repo_toml=f"[harness.claude]\ntimeout = {value}\n")
    assert cfg.for_harness("claude").timeout == MIN_TIMEOUT_S
    assert _mentions(warnings, "timeout")


def test_the_floor_is_below_the_default_so_it_never_caps(tmp_path):
    assert 0 < MIN_TIMEOUT_S < DEFAULT_TIMEOUT_S


# TOML source fragments, not Python values: `"model"` has to survive the
# parser to reach the guard at all, and `"model\x00"` — the case that shipped —
# does not, because a raw NUL is not valid TOML.
_SMUGGLED_LITERALS = ('"-c"', '"--model"', '"sonnet high"', '" sonnet"', '"sonnet\\t"', '"model\\u0007"', '""')


@pytest.mark.parametrize("literal", _SMUGGLED_LITERALS)
def test_a_smuggled_model_literal_is_refused_at_load(tmp_path, literal):
    """C-1030's "rejected wherever it is supplied", on the load leg alone.

    A leading `-` or a whitespace/non-printable character can only be an attempt
    to push argv through a value slot, and Codex's effort knob rides `-c` —
    which C-1023 refuses from passthrough. Deferring the check to `model_spec()`
    left `load()` returning `HarnessConfig(model_literal='-c')` with no warning
    at all, and `.model_literal` is a public field an adapter reads straight
    into argv.
    """
    with pytest.raises(ConfigError):
        _load(tmp_path, user_toml=f"[harness.claude]\nmodel_literal = {literal}\n")


def test_a_raw_nul_in_a_model_literal_dies_in_the_parser_before_the_guard(tmp_path):
    # Kept as its own case, because it is what proved the guard was not being
    # tested: this refusal comes from `tomllib`, not from C-1030.
    with pytest.raises(ConfigError):
        _load(tmp_path, user_toml='[harness.claude]\nmodel_literal = "model\x00"\n')


@pytest.mark.parametrize("effort", ('"-c model_reasoning_effort=high"', '"very high"', '""', '"high\\u0007"'))
def test_a_smuggled_effort_is_refused_at_load(tmp_path, effort):
    with pytest.raises(ConfigError):
        _load(tmp_path, user_toml=f'[harness.claude]\nmodel_literal = "o3"\neffort = {effort}\n')


def test_a_smuggled_effort_with_no_literal_beside_it_is_refused_too(tmp_path):
    # `model_spec()` answers `None` without a literal, so the deferred guard
    # never ran on this shape at all — while `.effort` stayed public and
    # readable, one `--effort` away from argv.
    with pytest.raises(ConfigError):
        _load(tmp_path, user_toml='[harness.claude]\neffort = "very high"\n')


@pytest.mark.parametrize("key", ["model_literal", "effort"])
def test_a_non_string_on_the_model_channel_warns_and_falls_back(tmp_path, key):
    # Not a permission key: a wrong *type* says nothing about the boundary, so
    # it warns where a smuggled argv word raises.
    cfg, warnings = _load(tmp_path, user_toml=f"[harness.claude]\n{key} = 3\n")
    assert getattr(cfg.for_harness("claude"), key) is None
    assert _mentions(warnings, key)


def test_an_empty_launcher_word_in_a_trusted_file_fails_hard(tmp_path):
    # C-1016: `launcher` is a permission key, and an empty argv word reaches
    # execve verbatim. `launcher_for` refuses it too — but only if something
    # calls it, and a malformed permission value is refused at load.
    with pytest.raises(ConfigError) as excinfo:
        _load(tmp_path, user_toml='[harness.opencode]\nlauncher = ["", "ocx"]\n')
    assert "launcher" in str(excinfo.value)


def test_an_empty_launcher_word_in_a_repo_local_file_is_dropped_before_it_can_raise(tmp_path):
    # The C-1017 order holds for the new refusal exactly as for the old ones.
    cfg, warnings = _load(tmp_path, repo_toml='[harness.opencode]\nlauncher = ["", "ocx"]\n')
    assert cfg.for_harness("opencode").launcher is None
    assert _mentions(warnings, "launcher")


def test_the_s1010_literal_payload_is_dropped_from_a_repo_local_file(tmp_path):
    # S-1010: `-c sandbox_mode=danger-full-access` is Codex's own escape hatch,
    # and `passthrough` is the slot it rides. Trust-gated, so a branch cannot
    # supply it at all; C-1023's per-adapter allowlist is the second belt.
    cfg, warnings = _load(
        tmp_path,
        repo_toml='[harness.codex]\npassthrough = ["-c", "sandbox_mode=danger-full-access"]\n',
    )
    assert cfg.for_harness("codex").passthrough == ()
    assert _mentions(warnings, "passthrough")


def test_a_trusted_model_literal_and_effort_survive(tmp_path):
    cfg, warnings = _load(tmp_path, user_toml='[harness.codex]\nmodel_literal = "o3"\neffort = "high"\n')
    assert cfg.for_harness("codex").model_spec() == ModelSpecT(model="o3", effort="high")
    assert warnings == ()


# ── load: the upward search ──────────────────────────────────────────────────


def test_the_first_nox_toml_found_upward_wins(tmp_path):
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    (repo / "a" / CONFIG_NAME).write_text('[review]\nharness = "opencode"\n')
    cfg, _warnings = load(sub, user_dir=user, state_dir=state)
    assert cfg.review_harness == "opencode"


def test_the_search_reaches_a_file_well_inside_the_depth_bound(tmp_path):
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    deep = repo.joinpath(*[f"d{i}" for i in range(MAX_SEARCH_DEPTH - 1)])
    deep.mkdir(parents=True)
    cfg, _warnings = load(deep, user_dir=user, state_dir=state)
    assert cfg.review_harness == "codex"


def test_the_search_stops_exactly_at_the_depth_bound(tmp_path):
    # The boundary itself. `MAX_SEARCH_DEPTH` directories below the file is one
    # parent step too far; the ±1 cases either side leave the off-by-one here
    # unasserted, which is the one thing a bound test is for.
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    deep = repo.joinpath(*[f"d{i}" for i in range(MAX_SEARCH_DEPTH)])
    deep.mkdir(parents=True)
    cfg, _warnings = load(deep, user_dir=user, state_dir=state)
    assert cfg.review_harness is None


def test_a_relative_cwd_does_not_truncate_the_upward_search(tmp_path, monkeypatch):
    # `Path("sub").parent` is `Path(".")` and *its* parent is `Path(".")` again,
    # so an unresolved relative path ends the walk one level in.
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    (repo / "sub").mkdir()
    monkeypatch.chdir(repo)
    cfg, _warnings = load(Path("sub"), user_dir=user, state_dir=state)
    assert cfg.review_harness == "codex"


@pytest.mark.parametrize("kind", ["a file", "absent"])
def test_a_cwd_that_is_not_a_directory_says_so_rather_than_blaming_the_file(tmp_path, kind):
    # The old warning sent the user looking for an unreadable `nox.toml` that
    # was never there: nothing failed to read, the search never started.
    repo, user, state = _tree(tmp_path)
    target = repo / "notadir"
    if kind == "a file":
        target.write_text("")
    cfg, warnings = load(target, user_dir=user, state_dir=state)
    assert cfg == NoxConfig()
    assert _mentions(warnings, "not an existing directory")
    assert not _mentions(warnings, "unreadable")


def test_a_scalar_member_of_the_harness_table_warns(tmp_path):
    # `[harness]\nread_only = false` names a phantom section: a scalar read as
    # an empty table configured nothing and, until this warning, said nothing.
    cfg, warnings = _load(tmp_path, repo_toml="[harness]\nread_only = false\n")
    assert dict(cfg.harnesses) == {}
    assert _mentions(warnings, "read_only")


def test_the_search_is_bounded_by_max_search_depth(tmp_path):
    # Deliberately past the bound rather than exactly on it: C-1017 fixes the
    # depth at 20 and leaves the off-by-one to the implementation.
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    deep = repo.joinpath(*[f"d{i}" for i in range(MAX_SEARCH_DEPTH + 1)])
    deep.mkdir(parents=True)
    cfg, _warnings = load(deep, user_dir=user, state_dir=state)
    assert cfg.review_harness is None


def test_the_search_never_crosses_a_device_boundary(tmp_path, monkeypatch):
    """C-1017, through the seam `load`'s docstring documents.

    A unit test cannot mount a second filesystem, so `_device_of` is the one
    module-private this file patches — the alternative is a contract with no
    test at all.
    """
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    sub = repo / "sub"
    sub.mkdir()
    monkeypatch.setattr(config, "_device_of", lambda path: 1 if Path(path) == sub else 2)
    cfg, _warnings = load(sub, user_dir=user, state_dir=state)
    assert cfg.review_harness is None


def test_one_device_everywhere_finds_the_same_file(tmp_path, monkeypatch):
    # The control for the test above: the fake seam itself must not be what
    # ends the search.
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    sub = repo / "sub"
    sub.mkdir()
    monkeypatch.setattr(config, "_device_of", lambda _path: 7)
    cfg, _warnings = load(sub, user_dir=user, state_dir=state)
    assert cfg.review_harness == "codex"


def test_the_name_being_a_directory_is_tolerated(tmp_path):
    # uv#7351: a directory called `nox.toml` must neither raise nor end the
    # search — the real file one level up still answers.
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    sub = repo / "sub"
    sub.mkdir()
    (sub / CONFIG_NAME).mkdir()
    cfg, _warnings = load(sub, user_dir=user, state_dir=state)
    assert cfg.review_harness == "codex"


def test_a_directory_named_nox_toml_in_the_user_config_dir_is_tolerated(tmp_path):
    repo, user, state = _tree(tmp_path)
    (user / CONFIG_NAME).mkdir()
    cfg, _warnings = load(repo, user_dir=user, state_dir=state)
    assert cfg == NoxConfig()


def test_malformed_toml_in_the_user_level_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, user_toml="[harness.claude\ntimeout = 1\n")


def test_an_unreadable_user_level_file_raises(tmp_path):
    # Presumes a non-root runner; as root `chmod 000` is not a barrier and this
    # is the one branch that cannot be provoked without one.
    repo, user, state = _tree(tmp_path)
    target = user / CONFIG_NAME
    target.write_text("[harness.claude]\ntimeout = 1\n")
    target.chmod(0o000)
    with pytest.raises(ConfigError):
        load(repo, user_dir=user, state_dir=state)


def test_malformed_toml_in_a_repo_local_file_warns_rather_than_raising(tmp_path):
    # T6 again: a one-character edit in a branch must not deny the review of
    # that branch. The Raises clause scopes the abort to the user-level file.
    cfg, warnings = _load(tmp_path, repo_toml="[harness.claude\ntimeout = 1\n")
    assert cfg == NoxConfig()
    assert warnings != ()


# ── load: no hash/read TOCTOU (C-1017) ───────────────────────────────────────


def _serve_once_then_swap(monkeypatch, path, first, second):
    """Serve `first` on the first read of `path`, `second` on every later one.

    C-1017's no-TOCTOU rule is only observable as an absence: if the hashed
    bytes and the parsed bytes came from two reads, the swap shows up as a
    config built from `second`. `_read_bytes` is the module-private seam that
    performs *the* read — the same kind of seam as `_device_of`, and patched for
    the same reason: a rule with no observable positive needs the one call site
    it is a property of. Every other path falls through to the real function, so
    the trust store still reads normally.
    """
    target = os.path.realpath(path)
    reads = []
    real_read_bytes = config._read_bytes

    def fake_read_bytes(candidate):
        if os.path.realpath(candidate) != target:
            return real_read_bytes(candidate)
        reads.append(target)
        return first if len(reads) == 1 else second

    monkeypatch.setattr(config, "_read_bytes", fake_read_bytes)
    return reads


def test_the_trusted_file_is_read_once_and_the_hashed_bytes_are_the_parsed_bytes(tmp_path, monkeypatch):
    repo, user, state = _tree(tmp_path)
    first = b"[harness.claude]\ntimeout = 111\n"
    second = b"[harness.claude]\ntimeout = 222\n"
    target = user / CONFIG_NAME
    target.write_bytes(first)
    reads = _serve_once_then_swap(monkeypatch, target, first, second)
    cfg, _warnings = load(repo, user_dir=user, state_dir=state)
    assert cfg.for_harness("claude").timeout == 111
    assert len(reads) == 1


def test_the_repo_local_file_is_read_once_too(tmp_path, monkeypatch):
    # The repo-local file is the one an attacker can rewrite mid-run, so its
    # stat-then-reopen would be the exploitable half of the same rule.
    repo, user, state = _tree(tmp_path)
    first = b"[harness.claude]\ntimeout = 111\n"
    second = b"[harness.claude]\ntimeout = 222\n"
    target = repo / CONFIG_NAME
    target.write_bytes(first)
    reads = _serve_once_then_swap(monkeypatch, target, first, second)
    cfg, _warnings = load(repo, user_dir=user, state_dir=state)
    assert cfg.for_harness("claude").timeout == 111
    assert len(reads) == 1


# ── load: the default user and state directories ─────────────────────────────


def test_the_user_and_state_directories_default_to_the_xdg_variables(tmp_path, monkeypatch):
    repo, _user, _state = _tree(tmp_path)
    xdg_config, xdg_state = tmp_path / "xdgconfig", tmp_path / "xdgstate"
    (xdg_config / "nox").mkdir(parents=True)
    (xdg_config / "nox" / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    monkeypatch.setenv("XDG_STATE_HOME", str(xdg_state))
    cfg, _warnings = load(repo)
    assert cfg.review_harness == "codex"


def test_the_user_and_state_directories_fall_back_under_home(tmp_path, monkeypatch):
    repo, _user, _state = _tree(tmp_path)
    fake_home = tmp_path / "fakehome"
    (fake_home / ".config" / "nox").mkdir(parents=True)
    (fake_home / ".config" / "nox" / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(fake_home))
    cfg, _warnings = load(repo)
    assert cfg.review_harness == "codex"


# ── The trust store (C-1017, D-w) ────────────────────────────────────────────


def test_trust_store_path_uses_the_explicit_state_dir(tmp_path):
    assert trust_store_path(tmp_path) == tmp_path / "trust.json"


def test_trust_store_path_defaults_to_xdg_state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdgstate"))
    assert trust_store_path() == tmp_path / "xdgstate" / "nox" / "trust.json"


def test_trust_store_path_falls_back_under_home(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))
    assert trust_store_path() == tmp_path / "fakehome" / ".local" / "state" / "nox" / "trust.json"


def test_the_user_level_file_is_trusted_by_its_location(tmp_path):
    # Route 1, and the digest is deliberately nonsense: the user authored the
    # file in their own config directory, so no content check applies.
    user_config = (tmp_path / "config" / CONFIG_NAME).resolve()
    assert is_trusted(user_config, "not-a-digest", user_config=user_config, state_dir=tmp_path / "state") is True


def test_a_repo_local_file_is_untrusted_with_no_store(tmp_path):
    # D-w: nothing in v1 writes the store, so this is the answer in practice.
    repo_config = (tmp_path / "repo" / CONFIG_NAME).resolve()
    user_config = (tmp_path / "config" / CONFIG_NAME).resolve()
    assert is_trusted(repo_config, "abc", user_config=user_config, state_dir=tmp_path / "state") is False


def _store(tmp_path, payload):
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "trust.json").write_text(payload)
    return state


def test_the_store_grants_trust_for_the_recorded_digest(tmp_path):
    repo_config = (tmp_path / "repo" / CONFIG_NAME).resolve()
    user_config = (tmp_path / "config" / CONFIG_NAME).resolve()
    state = _store(tmp_path, json.dumps({str(repo_config): "abc"}))
    assert is_trusted(repo_config, "abc", user_config=user_config, state_dir=state) is True


def test_the_store_grants_nothing_once_the_content_changes(tmp_path):
    # Content-scoped, not path-scoped — mise's paranoid model, and deliberately
    # the opposite of Codex's project trust (GHSA-436v-8fw5-4mj8).
    repo_config = (tmp_path / "repo" / CONFIG_NAME).resolve()
    user_config = (tmp_path / "config" / CONFIG_NAME).resolve()
    state = _store(tmp_path, json.dumps({str(repo_config): "abc"}))
    assert is_trusted(repo_config, "def", user_config=user_config, state_dir=state) is False


def test_a_store_entry_for_another_path_grants_nothing(tmp_path):
    repo_config = (tmp_path / "repo" / CONFIG_NAME).resolve()
    user_config = (tmp_path / "config" / CONFIG_NAME).resolve()
    state = _store(tmp_path, json.dumps({str(tmp_path / "elsewhere" / CONFIG_NAME): "abc"}))
    assert is_trusted(repo_config, "abc", user_config=user_config, state_dir=state) is False


@pytest.mark.parametrize("payload", ["{", "[]", '"a string"', ""])
def test_a_malformed_store_is_not_trust(tmp_path, payload):
    # `is_trusted` documents no Raises clause: the fail-closed answer is False,
    # and raising here would let a corrupt store deny every review.
    repo_config = (tmp_path / "repo" / CONFIG_NAME).resolve()
    user_config = (tmp_path / "config" / CONFIG_NAME).resolve()
    state = _store(tmp_path, payload)
    assert is_trusted(repo_config, "abc", user_config=user_config, state_dir=state) is False


# ── The environment may not name the trusted file (T4b) ──────────────────────


def test_an_xdg_config_home_inside_the_repository_is_refused(tmp_path, monkeypatch):
    """T4b's premise is that the branch controls the environment nox runs under.

    `mise.toml [env]` and `.envrc` are declarative and are sourced in the user's
    own shell when they check the branch out to look at it — no code execution
    needed. `XDG_CONFIG_HOME=<repo>/.config` then makes a branch-authored file
    *the trusted user file*, and every `TRUST_GATED_KEYS` member — `launcher`
    included, which is argv — is accepted from it, silently.
    """
    repo, _user, state = _tree(tmp_path)
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    planted = repo / ".config" / "nox"
    planted.mkdir(parents=True)
    (planted / CONFIG_NAME).write_text('[harness.opencode]\nlauncher = ["/tmp/evil", "--"]\n')
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(repo / ".config"))
    cfg, warnings = load(repo, state_dir=state)
    assert cfg.for_harness("opencode").launcher is None
    assert _mentions(warnings, "XDG_CONFIG_HOME")
    # Names only: the warning must not publish the path it refused.
    assert str(repo) not in "\n".join(warnings)


def test_an_xdg_state_home_inside_the_repository_is_refused(tmp_path, monkeypatch):
    # The same route one hop further out: a branch-authored `trust.json` grants
    # a branch-authored `nox.toml` every trust-gated key by content digest.
    repo, _user, _state = _tree(tmp_path)
    fake_home = tmp_path / "fakehome"
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("XDG_STATE_HOME", str(repo / ".state"))
    assert trust_store_path(repo=repo) == fake_home / ".local" / "state" / "nox" / "trust.json"


def test_a_repo_authored_trust_store_cannot_grant_the_repos_own_file(tmp_path, monkeypatch):
    """The whole chain, end to end: `XDG_STATE_HOME=<repo>/.state` plus a
    branch-authored `trust.json` naming the branch's own `nox.toml` and the
    digest of its content.

    Content-scoped trust is no defence here — the attacker wrote both files, so
    the digest matches by construction. The only thing standing between this and
    an arbitrary `launcher` argv is refusing to read a state directory the
    repository controls.
    """
    repo, _user, _state = _tree(tmp_path)
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    body = '[harness.opencode]\nlauncher = ["/tmp/evil", "--"]\n'
    (repo / CONFIG_NAME).write_text(body)
    planted = repo / ".state" / "nox"
    planted.mkdir(parents=True)
    digest = hashlib.sha256(body.encode()).hexdigest()
    (planted / "trust.json").write_text(json.dumps({str(repo / CONFIG_NAME): digest}))
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(repo / ".state"))
    cfg, warnings = load(repo)
    assert cfg.for_harness("opencode").launcher is None
    assert _mentions(warnings, "launcher")


def test_a_state_directory_outside_the_repository_is_still_honoured(tmp_path, monkeypatch):
    repo, _user, _state = _tree(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdgstate"))
    assert trust_store_path(repo=repo) == tmp_path / "xdgstate" / "nox" / "trust.json"


def test_a_home_inside_the_repository_falls_back_to_the_passwd_database(tmp_path, monkeypatch):
    # `Path.home()` and `expanduser` read `$HOME` first, so both are steerable
    # by exactly the attacker the fallback exists to escape. The passwd database
    # is the one answer the environment cannot rewrite.
    repo, _user, _state = _tree(tmp_path)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(repo / "home"))
    store = trust_store_path(repo=repo)
    assert repo not in store.parents
    assert store == Path(pwd.getpwuid(os.getuid()).pw_dir) / ".local" / "state" / "nox" / "trust.json"


def test_no_home_and_no_passwd_entry_is_a_nox_error(monkeypatch):
    # `docker run -u 1234`: `$HOME` unset and the uid absent from /etc/passwd.
    # `Path.home()` raises `RuntimeError` there — not a `NoxError`, and raised
    # outside every `try` in `load`, so it escaped `review()` entirely (C-1029).
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(os, "getuid", lambda: 0x7FFFFFFE)
    with pytest.raises(ConfigError):
        trust_store_path()


def test_a_user_config_inside_the_repository_is_not_trusted_by_its_location(tmp_path):
    # Belt over `_xdg`'s brace: the path arrives from a caller, and a "user"
    # file inside the tree under review is the whole of T4b however it was
    # derived.
    repo = tmp_path / "repo"
    planted = (repo / ".config" / "nox" / CONFIG_NAME).resolve()
    assert is_trusted(planted, "abc", user_config=planted, state_dir=tmp_path / "state", repo=repo) is False


def test_an_explicit_user_dir_inside_the_repository_is_not_trusted_either(tmp_path, monkeypatch):
    # `_xdg` refuses an environment-derived directory, and the override argument
    # is not a second way in: containment is a property of the answer, not of
    # the channel the answer arrived on. The planted file is not merely
    # untrusted here, it is never read at all, so no key of its can be dropped.
    repo, _user, state = _tree(tmp_path)
    fake_home = tmp_path / "fakehome"
    (fake_home / ".config" / "nox").mkdir(parents=True)
    planted = repo / ".config" / "nox"
    planted.mkdir(parents=True)
    (planted / CONFIG_NAME).write_text('[harness.opencode]\nlauncher = ["/tmp/evil", "--"]\n')
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(fake_home))
    cfg, warnings = load(repo, user_dir=planted, state_dir=state)
    assert cfg.for_harness("opencode").launcher is None
    assert _mentions(warnings, "XDG_CONFIG_HOME")
    # Names only: the warning must not publish the path it refused.
    assert str(repo) not in "\n".join(warnings)


def test_an_explicit_state_dir_inside_the_repository_grants_no_trust(tmp_path, monkeypatch):
    """The same override hole one hop further out — and the one that pays.

    `$XDG_STATE_HOME` inside the repository is already refused, so the whole
    chain rides on the override argument instead: a branch-authored
    `trust.json` under `<repo>/state` names the branch's own `nox.toml` and the
    digest of its content, and content-scoped trust is no defence when the
    attacker wrote both files. What it buys is `launcher`, which is the argv of
    the executable nox spawns — C-1005 and C-1025 exist to stop exactly this.

    `is_trusted`'s belt guards `user_config` alone, so nothing downstream
    catches the store: the refusal has to happen where the directory is
    resolved.
    """
    repo, user, _state = _tree(tmp_path)
    body = '[harness.opencode]\nlauncher = ["/tmp/evil", "--"]\n'
    (repo / CONFIG_NAME).write_text(body)
    planted = repo / "state"
    planted.mkdir()
    digest = hashlib.sha256(body.encode()).hexdigest()
    (planted / "trust.json").write_text(json.dumps({str((repo / CONFIG_NAME).resolve()): digest}))
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))
    cfg, warnings = load(repo, user_dir=user, state_dir=planted)
    assert cfg.for_harness("opencode").launcher is None
    assert _mentions(warnings, "launcher")


def test_an_explicit_state_dir_outside_the_repository_is_still_honoured(tmp_path):
    # The refusal is containment, not a ban on the argument: `load`'s own tests
    # and every consumer pass a state directory of their own.
    repo, _user, state = _tree(tmp_path)
    assert trust_store_path(state, repo=repo) == state / "trust.json"


def test_a_user_config_outside_the_repository_is_trusted_by_its_location(tmp_path):
    repo = tmp_path / "repo"
    user_config = (tmp_path / "config" / CONFIG_NAME).resolve()
    assert is_trusted(user_config, "abc", user_config=user_config, state_dir=tmp_path / "state", repo=repo) is True


# ── load: what a config file is allowed to be (C-1029 totality) ──────────────

# Two kilobytes, and `tomllib`'s recursive descent runs out of stack: a
# `RecursionError` is a `RuntimeError`, caught by neither the `OSError` nor the
# `ValueError` clause the read paths ship.
_NESTING_BOMB = "a = " + "[" * 2000 + "]" * 2000 + "\n"


def test_a_nesting_bomb_in_the_repository_file_is_ignored_rather_than_fatal(tmp_path):
    # T6: the repository layer must be fatal to nothing at all.
    cfg, warnings = _load(tmp_path, repo_toml=_NESTING_BOMB)
    assert cfg == NoxConfig()
    assert warnings != ()


def test_a_nesting_bomb_in_the_user_level_file_is_a_nox_error(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, user_toml=_NESTING_BOMB)


def test_a_nesting_bomb_in_the_trust_store_is_not_trust(tmp_path):
    # `json.loads` raises `RecursionError` too, and a corrupt store must never
    # deny every review — the fail-closed answer is the same word, "no".
    repo_config = (tmp_path / "repo" / CONFIG_NAME).resolve()
    user_config = (tmp_path / "config" / CONFIG_NAME).resolve()
    state = _store(tmp_path, "[" * 100_000)
    assert is_trusted(repo_config, "abc", user_config=user_config, state_dir=state) is False


@pytest.mark.parametrize("special", ["/dev/zero", "/dev/null"])
def test_a_nox_toml_symlinked_at_a_device_is_not_configuration(tmp_path, special):
    # git stores symlinks, so `ln -s /dev/zero nox.toml` is committable, and
    # `read_bytes()` follows it and reads until the machine is out of memory.
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).symlink_to(special)
    cfg, warnings = load(repo, user_dir=user, state_dir=state)
    assert cfg == NoxConfig()
    assert warnings == ()


def test_a_fifo_named_nox_toml_neither_blocks_nor_reads(tmp_path):
    # `open(2)` on a FIFO with no writer blocks forever without `O_NONBLOCK`,
    # and a review that hangs is the same denial of service as one that raises.
    repo, user, state = _tree(tmp_path)
    os.mkfifo(repo / CONFIG_NAME)
    cfg, warnings = load(repo, user_dir=user, state_dir=state)
    assert cfg == NoxConfig()
    assert warnings == ()


def test_the_descriptor_is_closed_once_the_bytes_are_read(tmp_path, monkeypatch):
    """`closefd=False` hands the descriptor's whole lifetime to the `finally`.

    Nothing else closes it — that is the point of the flag, and it is why the
    close is a line rather than a `with`. Drop it and every config read leaks a
    descriptor for the life of the process, which no assertion on the parsed
    result would ever notice. `os.open` is the module's single acquisition
    point, so spying on it names every descriptor `_read_bytes` took.
    """
    repo, user, state = _tree(tmp_path)
    (user / CONFIG_NAME).write_text("")
    (repo / CONFIG_NAME).write_text('[review]\nharness = "codex"\n')
    opened: list[int] = []
    real_open = os.open

    def spy(*args, **kwargs):
        descriptor = real_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    # `builtins.open` reaches the syscall through `_io`, never through this
    # name, so the only calls recorded are `_read_bytes`'s own.
    monkeypatch.setattr(os, "open", spy)
    cfg, _warnings = load(repo, user_dir=user, state_dir=state)
    monkeypatch.undo()

    assert cfg.review_harness == "codex"
    assert opened
    for descriptor in set(opened):
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_a_config_over_the_size_cap_is_refused_rather_than_truncated(tmp_path):
    # The key is first and the padding second: a truncating read would parse
    # the head and answer "codex", which is a config the user never wrote.
    repo, user, state = _tree(tmp_path)
    (repo / CONFIG_NAME).write_bytes(b'[review]\nharness = "codex"\n# ' + b"x" * (1 << 20))
    cfg, warnings = load(repo, user_dir=user, state_dir=state)
    assert cfg.review_harness is None
    assert warnings != ()


def test_a_utf8_bom_in_the_user_level_file_is_not_an_error(tmp_path):
    # Every Windows editor writes one, and a hard refusal of the user's own file
    # over three invisible bytes is not a security control.
    repo, user, state = _tree(tmp_path)
    (user / CONFIG_NAME).write_bytes(b"\xef\xbb\xbf" + b'[review]\nharness = "codex"\n')
    cfg, warnings = load(repo, user_dir=user, state_dir=state)
    assert cfg.review_harness == "codex"
    assert warnings == ()


# ── load: names are attacker-controlled too (C-1035(1)) ──────────────────────


def test_a_section_name_cannot_forge_a_line_or_repaint_the_terminal(tmp_path):
    """A `[harness.<name>]` name is as attacker-controlled as a value, and both
    `Review.warnings` and `Review.detail` reach a terminal.

    Reproduced: a name carrying `\\x1b[2J\\x1b[31m` repainted the screen, and one
    carrying a newline forged a second warning line under nox's own name.
    """
    hostile = "claude\\u001B[2J\\u001B[31m\\nlauncher: dropped from [harness.claude]"
    cfg, warnings = _load(tmp_path, repo_toml=f'[harness."{hostile}"]\nfrobnicate = 1\nread_only = true\n')
    # The section itself is kept — it configures a harness key nothing registers,
    # which is fail-soft's business, not this test's.
    assert len(cfg.harnesses) == 1
    assert _mentions(warnings, "frobnicate")
    assert _mentions(warnings, "read_only")
    for warning in warnings:
        assert "\x1b" not in warning
        assert "\n" not in warning


def test_a_giant_key_name_cannot_pad_a_warning(tmp_path):
    # Reproduced: a 200 KB key produced a 200 KB warning, and `Review.warnings`
    # is a channel a human reads.
    cfg, warnings = _load(tmp_path, repo_toml=f"[harness.claude]\n{'k' * 200_000} = 1\n")
    assert cfg.for_harness("claude") == HarnessConfig()
    assert warnings
    assert all(len(warning) < 200 for warning in warnings)


def test_a_hostile_name_renders_to_exactly_its_printable_characters():
    """C-1035(1): the rendering `_safe_name` owes, pinned character for character.

    The categories in one string, because the control range is only the loudest
    quarter: a NUL and an ESC, a bidi override that reorders what a human reads
    while the bytes stay put, a lone surrogate that raises `UnicodeEncodeError`
    in whatever writes the warning out, a line separator every renderer honours,
    and a newline that forges a second line under nox's own name. A rewrite that
    keeps the *policy* but changes the rendering fails here.
    """
    hostile = "har\x00ness.\x1b[2Jop\u202een\ud800co\u2028de\n"
    rendered = config._safe_name(hostile)
    assert rendered == "harness.[2Jopencode"
    assert rendered.encode()  # the channel that prints it cannot be made to raise


def test_a_name_is_cut_after_its_non_printables_are_dropped_and_never_before():
    """C-1035(1): `_MAX_NAME_CHARS` counts what survives the filter, not what the branch typed.

    The pin that forbids bounding the input first. Interleaving one control
    character per printable one halves an input-side cut, so a name of `4 * cap`
    characters would render `cap / 2` long and a 200 KB key would still render —
    the cap is on the *printable* characters, and it is the same cap either side
    of it. The exact-cap case pins the boundary the ellipsis hangs on: `cap`
    printable characters are the name, `cap + 1` are a cut one.
    """
    assert config._safe_name("\x1ba" * (config._MAX_NAME_CHARS * 4)) == "a" * config._MAX_NAME_CHARS + "…"
    assert config._safe_name("\x1ba" * config._MAX_NAME_CHARS) == "a" * config._MAX_NAME_CHARS
    assert config._safe_name("\x1ba" * (config._MAX_NAME_CHARS + 1)) == "a" * config._MAX_NAME_CHARS + "…"


# ── launcher_for, model_spec, narrow_tools ───────────────────────────────────


def test_launcher_for_puts_the_configured_prefix_before_the_adapter_binary(tmp_path):
    prefix = ("ocx", "package", "exec", "ocx.sh/anomalyco/opencode:1.18.22", "--")
    launcher = HarnessConfig(launcher=prefix).launcher_for("opencode")
    assert launcher == Launcher(binary="opencode", prefix=prefix)
    assert launcher is not None
    assert launcher.argv("-p") == (*prefix, "opencode", "-p")


def test_launcher_for_is_none_when_no_launcher_is_configured():
    assert HarnessConfig().launcher_for("claude") is None


@pytest.mark.parametrize(
    ("prefix", "binary"),
    [(("",), "claude"), (("ocx", "exec", ""), "claude"), (("ocx",), "")],
)
def test_launcher_for_maps_the_bare_value_error_to_config_error(prefix, binary):
    # C-1029 totality: `Launcher.__post_init__` raises a bare `ValueError`, and
    # an escaping `ValueError` is an uncaught exception out of `review()`.
    with pytest.raises(ConfigError):
        HarnessConfig(launcher=prefix).launcher_for(binary)


def test_model_spec_is_none_without_a_literal():
    assert HarnessConfig().model_spec() is None


def test_model_spec_is_none_when_only_an_effort_is_configured():
    # The adapter's shipped MODELS answers; an effort with nothing to pair it
    # with is not a selection.
    assert HarnessConfig(effort="high").model_spec() is None


def test_model_spec_pairs_the_literal_with_the_effort():
    assert HarnessConfig(model_literal="o3", effort="high").model_spec() == ModelSpecT(model="o3", effort="high")


def test_model_spec_without_an_effort():
    assert HarnessConfig(model_literal="sonnet").model_spec() == ModelSpecT(model="sonnet", effort=None)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model_literal": "-c"},
        {"model_literal": "sonnet high"},
        {"model_literal": ""},
        {"model_literal": "o3", "effort": "-c x=1"},
        {"model_literal": "o3", "effort": ""},
    ],
)
def test_model_spec_maps_the_bare_value_error_to_config_error(kwargs):
    # Load-bearing for C-1029: `ModelSpecT.of` raises `ValueError`, and this is
    # the only place it can be turned into a `FailureReason.INVALID_CONFIG`.
    with pytest.raises(ConfigError):
        HarnessConfig(**kwargs).model_spec()


def test_narrow_tools_passes_none_through():
    assert narrow_tools(None, ["Read", "Grep"]) is None


@pytest.mark.parametrize("requested", [(), ("Read",), ("Read", "Grep")])
def test_narrow_tools_accepts_a_subset_unchanged(requested):
    assert narrow_tools(requested, ["Read", "Grep"]) == requested


def test_narrow_tools_reads_an_arbitrary_iterable():
    assert narrow_tools(("Read",), frozenset({"Read", "Grep"})) == ("Read",)


@pytest.mark.parametrize("requested", [("Bash",), ("Read", "Bash"), ("read",)])
def test_narrow_tools_refuses_to_widen(requested):
    # C-1016: config can never restore Bash on the tool-removal leg. The
    # lowercase case is deliberate — a case-folded match would widen too.
    with pytest.raises(ConfigError) as excinfo:
        narrow_tools(requested, ["Read", "Grep"])
    assert requested[-1] in str(excinfo.value)


# ── matches_any ──────────────────────────────────────────────────────────────

_DENY_CASES = (
    ("*_TOKEN", "MY_TOKEN", "TOKEN_VALUE"),
    ("*_KEY", "SECRET_KEY", "KEYRING"),
    ("*_SECRET", "APP_SECRET", "SECRET_APP"),
    ("*_PASSWORD", "DB_PASSWORD", "PASSWORD_DB"),
    ("AWS_*", "AWS_REGION", "aws_region"),
    ("GITHUB_*", "GITHUB_ACTOR", "MY_GITHUB"),
    ("GH_*", "GH_HOST", "GHOST"),
    ("NPM_*", "NPM_CONFIG_REGISTRY", "NPMRC"),
    ("PYPI_*", "PYPI_URL", "PYPIRC"),
    ("OPENAI_*", "OPENAI_BASE_URL", "OPENAIBASE"),
    ("DATABASE_*", "DATABASE_URL", "DATABASEURL"),
    ("ANTHROPIC_*", "ANTHROPIC_AUTH_TOKEN", "MY_ANTHROPIC"),
    ("*APIKEY", "OPENCODE_ANTHROPIC_APIKEY", "APIKEYS"),
    ("*_CREDENTIALS", "VAULT_CREDENTIALS", "CREDENTIALS_FILE"),
    ("*_PAT", "AZURE_PAT", "PATH"),
)


def test_the_deny_cases_cover_every_shipped_pattern():
    # C-1034: a positive and a negative name per pattern, and a new pattern
    # must fail here rather than ship with neither.
    assert tuple(pattern for pattern, _, _ in _DENY_CASES) == DENY_PATTERNS


def test_every_shipped_auth_hint_name_is_denied_by_a_pattern():
    """The denylist's job is to survive the next `ALLOWLIST` widening.

    `AUTH_ENV_HINTS` is the module's own list of names that are credentials, so
    a hint name no `DENY_PATTERNS` entry claims is a name the belt would not
    catch if the braces ever slipped — which is exactly how `*APIKEY` was
    missing while `OPENCODE_*_APIKEY` shipped one constant away.
    """
    hints = sorted({name for names in AUTH_ENV_HINTS.values() for name in names})
    assert hints  # a shrunk-to-empty hints table must not pass silently
    assert [name for name in hints if not matches_any(name.replace("*", "X"), DENY_PATTERNS)] == []


@pytest.mark.parametrize(("pattern", "positive", "negative"), _DENY_CASES)
def test_each_deny_pattern_matches_its_positive_and_not_its_negative(pattern, positive, negative):
    assert matches_any(positive, [pattern]) is True
    assert matches_any(negative, [pattern]) is False


_GLOB_CASES = (("BUN_*", "BUN_INSTALL", "BUNX"),)


def test_the_never_forward_glob_cases_cover_every_shipped_pattern():
    assert tuple(pattern for pattern, _, _ in _GLOB_CASES) == NEVER_FORWARD_GLOBS


@pytest.mark.parametrize(("pattern", "positive", "negative"), _GLOB_CASES)
def test_each_never_forward_glob_matches_its_positive_and_not_its_negative(pattern, positive, negative):
    assert matches_any(positive, [pattern]) is True
    assert matches_any(negative, [pattern]) is False


def test_matching_is_case_sensitive():
    # `fnmatchcase`, not `fnmatch`: environment names are case-sensitive, and a
    # case-insensitive match would drop `path` alongside `PATH`.
    assert matches_any("path", ["PATH"]) is False
    assert matches_any("PATH", ["PATH"]) is True


def test_a_literal_pattern_does_not_glob():
    assert matches_any("NODE_OPTIONS_EXTRA", ["NODE_OPTIONS"]) is False


def test_no_patterns_matches_nothing():
    assert matches_any("ANYTHING", []) is False


def test_any_matching_pattern_is_enough():
    assert matches_any("AWS_SECRET", ["GH_*", "AWS_*"]) is True


# ── The shipped environment literals ─────────────────────────────────────────


def test_never_forward_is_disjoint_from_the_allowlist():
    # C-1034(1): every member is already dropped by construction, and this is
    # what keeps that true after the next "just add one more" edit.
    assert NEVER_FORWARD & ALLOWLIST == frozenset()


def test_the_claude_credential_store_is_forwarded_and_guarded_as_a_trust_input():
    """C-1008/T4b: dropping it made every claude review refuse `UNAUTHENTICATED` while signed in.

    Both halves, because either alone is a defect. Forwarded, or `auth status`
    reports `loggedIn: false` on a harness that is logged in. Guarded, because
    it names the directory the harness reads its CREDENTIAL store out of, which
    is the sharpest thing a branch-authored `.envrc` could repoint.
    """
    assert "CLAUDE_SECURESTORAGE_CONFIG_DIR" in ALLOWLIST
    assert "CLAUDE_SECURESTORAGE_CONFIG_DIR" in INBOUND_PATH_VARS


def test_no_allowlisted_name_matches_a_deny_pattern():
    # The denylist is belt over the allowlist's braces; the belt must not be
    # what silently removes an infrastructure variable.
    assert [name for name in sorted(ALLOWLIST) if matches_any(name, DENY_PATTERNS)] == []


def test_no_allowlisted_name_matches_a_never_forward_glob():
    assert [name for name in sorted(ALLOWLIST) if matches_any(name, NEVER_FORWARD_GLOBS)] == []


def test_required_env_is_allowlisted():
    # A required variable that is not forwarded would raise on every run.
    assert REQUIRED_ENV <= ALLOWLIST
    assert REQUIRED_ENV == frozenset({"PATH", "HOME"})


def test_the_inbound_path_vars_are_every_forwarded_trust_input():
    """T4b: every variable whose value names a path the harness reads or trusts.

    The axis is trust, not execution, which is what puts the CA-bundle set here:
    a PEM committed to the branch plus a proxy is a TLS session the attacker
    terminates, and the harness crosses it authenticating as itself — so the
    user's own API key is what travels. `TMPDIR` joins them because a harness
    stages files there and reads them back.

    The proxy set is deliberately absent and deliberately still allowlisted:
    C-1008 enumerates it, and an attacker-chosen proxy is an ADR-level residual
    rather than something a path test can judge.

    `CLAUDE_SECURESTORAGE_CONFIG_DIR` is here for the sharpest reason in the set:
    it names the directory Claude Code reads its CREDENTIAL store out of, so an
    `.envrc` repointing it is a store the branch supplies.

    `OPENCODE_AUTH_JSON` is absent because it does not exist (E19/D-ad): WP7c
    pinned the name against the real binary and the variable that carries
    OpenCode's store is `OPENCODE_AUTH_CONTENT`, which carries it inline. A
    value is not a path, so it is a `NEVER_FORWARD` member rather than a guarded
    forward.
    """
    assert INBOUND_PATH_VARS == frozenset(
        {
            "HOME",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_CACHE_HOME",
            "CLAUDE_CONFIG_DIR",
            "CLAUDE_SECURESTORAGE_CONFIG_DIR",
            "CODEX_HOME",
            "TMPDIR",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "REQUESTS_CA_BUNDLE",
            "CURL_CA_BUNDLE",
            "NODE_EXTRA_CA_CERTS",
        }
    )
    # A guard over a name nothing forwards guards nothing.
    assert INBOUND_PATH_VARS <= ALLOWLIST


def test_shell_is_deliberately_absent_from_the_allowlist():
    # It names an executable, no v1 containment plan reads it, and a `.envrc`
    # sourced in the user's own shell is exactly the T4b route that sets it.
    assert "SHELL" not in ALLOWLIST


# ── minimal_env ──────────────────────────────────────────────────────────────


def test_only_allowlisted_names_survive(tmp_path):
    repo, wt, home = _env_tree(tmp_path)
    environ = _parent(home, TERM="xterm", LANG="C.UTF-8", EDITOR="vim", MY_APP_URL="https://x")
    env, dropped = minimal_env(repo, wt, environ=environ)
    assert set(env) - _NOX_OWNED <= ALLOWLIST
    assert env["TERM"] == "xterm"
    assert env["LANG"] == "C.UTF-8"
    assert "EDITOR" not in env
    assert "MY_APP_URL" not in env
    assert set(dropped) == {"EDITOR", "MY_APP_URL"}


def test_the_parent_environment_defaults_to_os_environ(tmp_path, monkeypatch):
    # The `environ=None` leg, exercised without ever reading the real `$HOME`:
    # every name the assertions touch is overridden first.
    repo, wt, home = _env_tree(tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("LD_PRELOAD", str(tmp_path / "evil.so"))
    env, dropped = minimal_env(repo, wt)
    assert env["HOME"] == str(home)
    assert "LD_PRELOAD" not in env
    assert "LD_PRELOAD" in dropped


@pytest.mark.parametrize("name", sorted(NEVER_FORWARD))
def test_every_never_forward_member_is_absent_from_the_built_env(tmp_path, name):
    # C-1034(1): each member is an *execution* channel rather than a credential
    # — `NODE_OPTIONS --require` injects into any Node harness, and
    # `SSH_AUTH_SOCK` is load-bearing against C-1007's AF_UNIX residual.
    repo, wt, home = _env_tree(tmp_path)
    env, dropped = minimal_env(repo, wt, environ=_parent(home, **{name: "/tmp/hostile"}))
    assert name not in env
    assert name in dropped


@pytest.mark.parametrize(("_pattern", "positive", "_negative"), _GLOB_CASES)
def test_every_never_forward_glob_drops_a_matching_name(tmp_path, _pattern, positive, _negative):
    repo, wt, home = _env_tree(tmp_path)
    env, dropped = minimal_env(repo, wt, environ=_parent(home, **{positive: "/tmp/hostile"}))
    assert positive not in env
    assert positive in dropped


@pytest.mark.parametrize(("_pattern", "positive", "_negative"), _DENY_CASES)
def test_every_deny_pattern_drops_a_matching_name(tmp_path, _pattern, positive, _negative):
    repo, wt, home = _env_tree(tmp_path)
    env, dropped = minimal_env(repo, wt, environ=_parent(home, **{positive: "s3cr3t"}))
    assert positive not in env
    assert positive in dropped
    assert "s3cr3t" not in "\n".join(dropped)


def test_the_deny_belt_still_drops_a_wrongly_allowlisted_name(tmp_path, monkeypatch):
    """Steps 2 and 3 share one leg, and step 3 is unreachable while the two sets
    are disjoint — so the whole suite passes with `or _denied(name)` deleted.

    A widened `ALLOWLIST` is the regression the belt exists for: this is the
    "just add one more" edit C-1034(1) is written against, and the belt has to
    survive it. Without this test, 100% branch coverage over `_survives` is
    arc-honest and assertion-empty.
    """
    repo, wt, home = _env_tree(tmp_path)
    hostile = {"GITHUB_TOKEN": "ghp_x", "NODE_OPTIONS": "--require /tmp/evil.js", "BUN_INSTALL": "/tmp/bun"}
    monkeypatch.setattr(config, "ALLOWLIST", ALLOWLIST | set(hostile))
    env, dropped = minimal_env(repo, wt, environ=_parent(home, **hostile))
    assert set(hostile) & set(env) == set()
    assert set(hostile) <= set(dropped)


def test_the_ca_bundle_names_are_forwarded_on_named_cause(tmp_path):
    """E48: the two CA names measurement cannot judge, and why they stay anyway.

    Every other widening past C-1008 was settled by asking whether a shipped
    harness reads the name. That question is unanswerable for these two on any
    ordinary machine: the environment they exist for is a TLS-inspecting
    corporate proxy with a private CA, and a machine using the stock trust store
    is structurally unable to produce it. The read measurement therefore returns
    a false negative — "no harness reads it" — for a cause that is real, and
    acting on it would ship a nox that cannot complete a single request exactly
    where these names are load-bearing.

    So the justification is named rather than measured, and this is the test
    that makes the naming cost something: delete either member from `ALLOWLIST`
    and it fails. The oracle in `tests/acceptance/test_adversarial_fixture.py`
    bounds the set from ABOVE (no unrecorded widening); this bounds these two
    from below. Both directions are needed — `SSL_CERT_DIR` is *also* read by
    codex, so it would survive a deletion sweep on measurement alone, and
    `CURL_CA_BUNDLE` would not.
    """
    repo, wt, home = _env_tree(tmp_path)
    outside = tmp_path / "ca"
    outside.mkdir()
    names = {"SSL_CERT_DIR": str(outside), "CURL_CA_BUNDLE": str(outside / "bundle.pem")}
    env, dropped = minimal_env(repo, wt, environ=_parent(home, **names))
    assert {name: env.get(name) for name in names} == names
    assert set(names) & set(dropped) == set()


# The inbound rejection (T4b). `HOME` is split out: dropping it leaves a
# `REQUIRED_ENV` member missing, so the run refuses instead of proceeding with
# a repository-controlled home.
_INBOUND_NON_HOME = sorted(INBOUND_PATH_VARS - {"HOME"})


@pytest.mark.parametrize("name", _INBOUND_NON_HOME)
@pytest.mark.parametrize("where", ["repo", "worktree", "repo-itself"])
def test_an_inbound_path_var_resolving_inside_the_tree_is_dropped(tmp_path, name, where):
    """T4b: `CODEX_HOME=/tmp/x` is exported by the branch's own `.envrc` in the
    user's shell before nox is ever invoked, and Codex then reads `/tmp/x`'s
    hooks *and* its trust store. Deleting `.envrc` from the worktree covers
    only the copy nobody reads.
    """
    repo, wt, home = _env_tree(tmp_path)
    value = {"repo": repo / "planted", "worktree": wt / "planted", "repo-itself": repo}[where]
    env, dropped = minimal_env(repo, wt, environ=_parent(home, **{name: str(value)}))
    assert name not in env
    assert name in dropped


@pytest.mark.parametrize("name", _INBOUND_NON_HOME)
def test_an_inbound_path_var_outside_the_tree_is_forwarded(tmp_path, name):
    repo, wt, home = _env_tree(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    env, _dropped = minimal_env(repo, wt, environ=_parent(home, **{name: str(outside)}))
    assert env[name] == str(outside)


def test_an_inbound_path_var_is_resolved_before_it_is_judged(tmp_path):
    # A symlink outside the tree pointing back into it is the same attack with
    # one more hop; the rule is about the resolved value.
    repo, wt, home = _env_tree(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(repo)
    env, dropped = minimal_env(repo, wt, environ=_parent(home, CODEX_HOME=str(link / "planted")))
    assert "CODEX_HOME" not in env
    assert "CODEX_HOME" in dropped


@pytest.mark.parametrize("value", ["planted", "./planted", "~/planted", ".."])
def test_a_relative_inbound_path_var_is_dropped(tmp_path, value):
    """`_inside` resolves against **nox's** working directory, and the child's
    is the worktree.

    So `CODEX_HOME=planted` resolves outside the roots here, is forwarded
    verbatim, and is read from inside the worktree there — the inbound test
    passing on a path the harness never uses. `sanitize_path` already refuses a
    non-absolute `PATH` entry for the same reason.
    """
    repo, wt, home = _env_tree(tmp_path)
    env, dropped = minimal_env(repo, wt, environ=_parent(home, CODEX_HOME=value))
    assert "CODEX_HOME" not in env
    assert "CODEX_HOME" in dropped


def test_an_inbound_path_var_with_an_embedded_nul_is_dropped(tmp_path):
    # `Path.resolve()` raises a bare `ValueError` on a NUL, reachable straight
    # through `minimal_env(environ=…)`; an escaping `ValueError` is an uncaught
    # exception out of `review()` (C-1029). A value nox cannot resolve is a
    # value it will not forward.
    repo, wt, home = _env_tree(tmp_path)
    env, dropped = minimal_env(repo, wt, environ=_parent(home, CODEX_HOME="/tmp/a\x00b"))
    assert "CODEX_HOME" not in env
    assert "CODEX_HOME" in dropped


def test_an_empty_home_refuses_the_run(tmp_path):
    # `REQUIRED_ENV` checked presence, not usability: an empty `HOME` survives
    # every step above and expands `~` to `/` in the child.
    repo, wt, _home = _env_tree(tmp_path)
    with pytest.raises(ConfigError) as excinfo:
        minimal_env(repo, wt, environ={"PATH": "/usr/bin", "HOME": ""})
    assert "HOME" in str(excinfo.value)


def test_a_home_inside_the_repository_refuses_the_run(tmp_path):
    # `HOME` is in REQUIRED_ENV *and* INBOUND_PATH_VARS precisely so this
    # composition refuses rather than proceeding with a repo-controlled home.
    repo, wt, _home = _env_tree(tmp_path)
    with pytest.raises(ConfigError) as excinfo:
        minimal_env(repo, wt, environ={"PATH": "/usr/bin", "HOME": str(repo / "home")})
    assert "HOME" in str(excinfo.value)


@pytest.mark.parametrize("name", sorted(REQUIRED_ENV))
def test_a_missing_required_variable_raises_naming_it(tmp_path, name):
    # C-1008: dropping a credential degrades safely, dropping infrastructure
    # fails confusingly, and users answer confusing failures by turning
    # scrubbing off entirely.
    repo, wt, home = _env_tree(tmp_path)
    environ = _parent(home)
    del environ[name]
    with pytest.raises(ConfigError) as excinfo:
        minimal_env(repo, wt, environ=environ)
    assert name in str(excinfo.value)


# ── sanitize_path (C-1034(2)) ────────────────────────────────────────────────


def test_sanitize_path_preserves_the_surviving_entries_and_their_order(tmp_path):
    repo, wt, _home = _env_tree(tmp_path)
    first, second = tmp_path / "binA", tmp_path / "binB"
    value = os.pathsep.join([str(first), str(second)])
    assert sanitize_path(value, repo, wt) == value


@pytest.mark.parametrize("hostile", ["", ".", "relative/bin", "~/bin"])
def test_sanitize_path_drops_empty_and_non_absolute_entries(tmp_path, hostile):
    # An empty entry means "the current directory" to most shells, and the
    # child's cwd is the attacker's worktree.
    repo, wt, _home = _env_tree(tmp_path)
    keep = str(tmp_path / "binA")
    assert sanitize_path(os.pathsep.join([hostile, keep]), repo, wt) == keep


@pytest.mark.parametrize("where", ["repo", "worktree"])
def test_sanitize_path_drops_entries_inside_the_tree_under_review(tmp_path, where):
    repo, wt, _home = _env_tree(tmp_path)
    hostile = str({"repo": repo, "worktree": wt}[where] / "bin")
    keep = str(tmp_path / "binA")
    assert sanitize_path(os.pathsep.join([hostile, keep]), repo, wt) == keep


def test_sanitize_path_resolves_an_entry_before_judging_it(tmp_path):
    repo, wt, _home = _env_tree(tmp_path)
    (repo / "bin").mkdir()
    link = tmp_path / "linkbin"
    link.symlink_to(repo / "bin")
    keep = str(tmp_path / "binA")
    assert sanitize_path(os.pathsep.join([str(link), keep]), repo, wt) == keep


@pytest.mark.parametrize("value", ["", ":", "relative"])
def test_sanitize_path_raises_naming_path_when_everything_is_dropped(tmp_path, value):
    # C-1008's missing-infrastructure rule: an empty PATH is not a degraded
    # run, it is a run that cannot find its own harness.
    repo, wt, _home = _env_tree(tmp_path)
    with pytest.raises(ConfigError) as excinfo:
        sanitize_path(value.replace(":", os.pathsep), repo, wt)
    assert "PATH" in str(excinfo.value)


def test_minimal_env_rebuilds_path(tmp_path):
    repo, wt, home = _env_tree(tmp_path)
    keep = str(tmp_path / "binA")
    hostile = os.pathsep.join(["", "rel", str(repo / "bin"), str(wt / "bin"), keep])
    env, _dropped = minimal_env(repo, wt, environ={"PATH": hostile, "HOME": str(home)})
    assert env["PATH"] == keep


def test_minimal_env_refuses_a_path_that_sanitizes_to_nothing(tmp_path):
    repo, wt, home = _env_tree(tmp_path)
    with pytest.raises(ConfigError) as excinfo:
        minimal_env(repo, wt, environ={"PATH": str(repo / "bin"), "HOME": str(home)})
    assert "PATH" in str(excinfo.value)


# ── The git set: drop first, write after (C-1031, C-1034(3)) ─────────────────


def _hostile_git_env():
    return {
        "GIT_CONFIG_COUNT": "9",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": "/tmp/evil-hooks",
        "GIT_CONFIG_KEY_1": "core.fsmonitor",
        "GIT_CONFIG_VALUE_1": "/tmp/evil-monitor",
        "GIT_CONFIG_KEY_8": "core.pager",
        "GIT_CONFIG_VALUE_8": "/tmp/evil-pager",
        "GIT_ATTR_NOSYSTEM": "0",
    }


def test_the_inherited_git_config_is_dropped_and_noxs_own_set_is_written_after(tmp_path):
    """C-1034(3): these are the keys that decide whether a child-issued git runs
    a hook, so a parent-supplied value is an inbound channel of the T4b shape.

    The count/key/value triple binds every git in the child's process tree,
    which a per-call `-c core.hooksPath=/dev/null` never did.
    """
    repo, wt, home = _env_tree(tmp_path)
    hostile = _hostile_git_env()
    env, dropped = minimal_env(repo, wt, environ=_parent(home, **hostile))

    assert env["GIT_CONFIG_COUNT"] == str(len(GIT_CONFIG_OVERRIDES))
    for index, (key, value) in enumerate(GIT_CONFIG_OVERRIDES):
        assert env[f"GIT_CONFIG_KEY_{index}"] == key
        assert env[f"GIT_CONFIG_VALUE_{index}"] == value
    # The hostile n=8 slot must not survive above nox's own count, or a git
    # that reads a higher count than nox wrote picks it up.
    assert [name for name in env if name.startswith("GIT_CONFIG_KEY_")] == [
        f"GIT_CONFIG_KEY_{i}" for i in range(len(GIT_CONFIG_OVERRIDES))
    ]
    assert [value for value in env.values() if value.startswith("/tmp/evil")] == []
    assert dict(GIT_PLAIN_ENV).items() <= env.items()
    assert set(hostile) <= set(dropped)


def test_the_git_plain_env_is_written_even_with_nothing_git_ish_inherited(tmp_path):
    # An unset identity fails every synthetic commit in a hermetic fixture
    # (D-p), so the pair is nox's own, not a passthrough.
    repo, wt, home = _env_tree(tmp_path)
    env, _dropped = minimal_env(repo, wt, environ=_parent(home))
    assert dict(GIT_PLAIN_ENV).items() <= env.items()
    assert env["GIT_ATTR_NOSYSTEM"] == "1"


def test_a_system_gitconfig_never_reaches_a_child(tmp_path):
    # ALLOWLIST carries no GIT_* name, so without nox SETTING this a system
    # /etc/gitconfig reaches every git nox runs. The three GIT_CONFIG_OVERRIDES
    # keys outranking it is not enough: a system filter.<x>.smudge bound through
    # $GIT_DIR/info/attributes is a different key, and it runs at `worktree add`.
    repo, wt, home = _env_tree(tmp_path)
    env, _dropped = minimal_env(repo, wt, environ=_parent(home))
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"


def test_an_inherited_git_config_nosystem_is_replaced_not_forwarded(tmp_path):
    # It must be a value nox sets, never one the caller chooses: a parent
    # turning it off is exactly how a system config would be let back in.
    repo, wt, home = _env_tree(tmp_path)
    env, dropped = minimal_env(repo, wt, environ=_parent(home, GIT_CONFIG_NOSYSTEM="0"))
    assert "GIT_CONFIG_NOSYSTEM" in dropped
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"


def test_dropped_names_a_hostile_git_variable_even_though_step_seven_resets_it(tmp_path):
    # `dropped` answers "what did nox refuse to carry through", not "what is
    # absent from the result".
    repo, wt, home = _env_tree(tmp_path)
    env, dropped = minimal_env(repo, wt, environ=_parent(home, GIT_ATTR_NOSYSTEM="0"))
    assert "GIT_ATTR_NOSYSTEM" in dropped
    assert env["GIT_ATTR_NOSYSTEM"] == "1"


def test_dropped_is_sorted_deduplicated_names_only(tmp_path):
    # C-1035(1): `dropped` travels into an error detail (C-1034(4)) and must not
    # be able to carry a secret.
    repo, wt, home = _env_tree(tmp_path)
    environ = _parent(home, ANTHROPIC_API_KEY="sk-s3cr3t", EDITOR="vim", **_hostile_git_env())
    _env, dropped = minimal_env(repo, wt, environ=environ)
    assert list(dropped) == sorted(dropped)
    assert len(set(dropped)) == len(dropped)
    assert set(dropped) <= set(environ)
    assert "sk-s3cr3t" not in "\n".join(dropped)
    assert "ANTHROPIC_API_KEY" in dropped


def test_a_forwarded_variable_is_not_reported_as_dropped(tmp_path):
    repo, wt, home = _env_tree(tmp_path)
    _env, dropped = minimal_env(repo, wt, environ=_parent(home, TERM="xterm"))
    assert "TERM" not in dropped
    assert "PATH" not in dropped
    assert "HOME" not in dropped


# ── Every C-1031 row, proved by a git that would otherwise execute (C-1031) ──


def _payload_repo(tmp_path):
    """A real repository, a marker directory its payloads write into, and the
    ambient environment nox would run git under **minus** the C-1031 triple.

    `GIT_PLAIN_ENV` is in the ambient environment on purpose: the two runs in
    each test then differ in `GIT_CONFIG_OVERRIDES` and in nothing else, so a
    marker that fires under one and not the other isolates the row rather than
    the fixture. A row asserted only by `env[...] == ...` is a row that can be
    deleted from the tuple without any git noticing.
    """
    repo, worktree, home = _env_tree(tmp_path)
    markers = tmp_path / "markers"
    markers.mkdir()
    ambient = {"PATH": os.pathsep.join(["/usr/bin", "/bin"]), "HOME": str(home), **GIT_PLAIN_ENV}
    return repo, worktree, markers, ambient


def _git(repo, env, *args):
    subprocess.run(["git", "-C", str(repo), *args], env=dict(env), capture_output=True, text=True, check=True)


def test_core_attributes_file_is_pinned_against_a_repository_that_binds_a_filter(tmp_path):
    """Row 3. A committed `.gitattributes` is dropped by name (C-1005), so
    `core.attributesFile` is how a repository's own config still binds
    `*.py filter=evil` — and the smudge driver is a shell command git runs on
    checkout, in the child's process tree, with no hook directory involved.

    The unprotected run is asserted first: a control that cannot fire proves
    nothing about the override that stops it.
    """
    repo, worktree, markers, ambient = _payload_repo(tmp_path)
    attributes = tmp_path / "attributes"
    attributes.write_text("*.py filter=evil\n")
    _git(repo, ambient, "init", "-q", "-b", "main", ".")
    _git(repo, ambient, "config", "core.attributesFile", str(attributes))
    _git(repo, ambient, "config", "filter.evil.smudge", f"sh -c 'touch \"{markers}/attrfile-smudge\"; cat'")
    (repo / "a.py").write_text("print(1)\n")
    _git(repo, ambient, "add", "-A")
    _git(repo, ambient, "commit", "-qm", "base")

    (repo / "a.py").unlink()
    _git(repo, ambient, "checkout", "-q", "--", "a.py")
    assert [path.name for path in markers.iterdir()] == ["attrfile-smudge"]

    (markers / "attrfile-smudge").unlink()
    (repo / "a.py").unlink()
    env, _dropped = minimal_env(repo, worktree, environ=ambient)
    _git(repo, env, "checkout", "-q", "--", "a.py")
    assert list(markers.iterdir()) == []


def test_core_fsmonitor_is_pinned_against_a_repository_that_names_a_hook(tmp_path):
    """Row 2. `core.fsmonitor` names a command git runs to ask what changed, so
    a repository's own config gets an executable invoked by every `git status`
    in the child's process tree — no checkout and no working-tree change needed,
    which is what makes it the cheapest of the three to reach.
    """
    repo, worktree, markers, ambient = _payload_repo(tmp_path)
    monitor = tmp_path / "fsmonitor-hook"
    # `/\0` is the "assume everything changed" reply; git only has to invoke the
    # command for the marker to land, but a reply it can parse keeps the run clean.
    monitor.write_text(f'#!/bin/sh\ntouch "{markers}/fsmonitor"\nprintf "/\\0"\n')
    monitor.chmod(0o755)
    _git(repo, ambient, "init", "-q", "-b", "main", ".")
    (repo / "a.py").write_text("print(1)\n")
    _git(repo, ambient, "add", "-A")
    _git(repo, ambient, "commit", "-qm", "base")
    _git(repo, ambient, "config", "core.fsmonitor", str(monitor))

    _git(repo, ambient, "status", "--porcelain")
    assert [path.name for path in markers.iterdir()] == ["fsmonitor"]

    (markers / "fsmonitor").unlink()
    env, _dropped = minimal_env(repo, worktree, environ=ambient)
    _git(repo, env, "status", "--porcelain")
    assert list(markers.iterdir()) == []


# ── world_writable_forwards (C-1008 rule 2) ──────────────────────────────────


def _dir(tmp_path, name, mode):
    path = tmp_path / name
    path.mkdir()
    path.chmod(mode)
    return path


def test_a_non_sticky_world_writable_directory_warns(tmp_path):
    shared = _dir(tmp_path, "shared", 0o777)
    (warning,) = world_writable_forwards({"CODEX_HOME": str(shared)})
    assert "CODEX_HOME" in warning


def test_the_warning_names_the_variable_and_never_its_value(tmp_path):
    """C-1035(1): a warning carries names, never values — and the resolved
    directory *is* the forwarded value of `CODEX_HOME`.

    The rule is not about secrecy grades. `HOME` and `CODEX_HOME` are values
    exactly as much as a token is, and a warning that interpolates one is a
    warning that has to be re-audited every time the set widens.
    """
    shared = _dir(tmp_path, "s3cr3t-shared", 0o777)
    (warning,) = world_writable_forwards({"CODEX_HOME": str(shared)})
    assert "CODEX_HOME" in warning
    assert str(shared) not in warning
    assert "s3cr3t-shared" not in warning


def test_a_world_writable_ancestor_warns_even_when_the_directory_itself_is_sound(tmp_path):
    # C-1008 rule 2 says "under a world-writable directory", and one level of
    # inspection sees nothing here: `/shared777` is 0777, `cfg` inside it is
    # 0755, and any local user can rename `cfg` away and put their own there.
    shared = _dir(tmp_path, "shared777", 0o777)
    cfg = shared / "cfg"
    cfg.mkdir()
    cfg.chmod(0o755)
    (warning,) = world_writable_forwards({"CODEX_HOME": str(cfg)})
    assert "CODEX_HOME" in warning


def test_a_sticky_world_writable_ancestor_is_exempt(tmp_path):
    # S_ISVTX is what `/tmp` is: another user cannot replace or remove an entry
    # that is not theirs, so a private directory *inside* one is sound — and
    # warning on every `$TMPDIR`-shaped path would burn the C-1035 channel.
    sticky = _dir(tmp_path, "sticky", 0o1777)
    private = sticky / "mine"
    private.mkdir()
    private.chmod(0o700)
    assert world_writable_forwards({"CODEX_HOME": str(private)}) == ()


def test_the_sticky_exemption_does_not_cover_the_directory_config_is_read_from(tmp_path):
    # Sticky stops another user replacing an entry that is not theirs; it does
    # not stop them *creating* one. A harness config file is usually a file that
    # does not exist yet, so `CODEX_HOME=/tmp` is a hole and not an exemption.
    sticky = _dir(tmp_path, "sticky", 0o1777)
    (warning,) = world_writable_forwards({"CODEX_HOME": str(sticky)})
    assert "CODEX_HOME" in warning


def test_a_private_directory_does_not_warn(tmp_path):
    private = _dir(tmp_path, "private", 0o755)
    assert world_writable_forwards({"CODEX_HOME": str(private)}) == ()


def test_a_value_that_does_not_exist_does_not_warn(tmp_path):
    # This composes an advisory, and an advisory path is the worst place to
    # raise on a stat of a path the user simply has not created yet.
    assert world_writable_forwards({"CODEX_HOME": str(tmp_path / "absent")}) == ()


def test_the_scan_is_scoped_to_the_inbound_path_vars(tmp_path):
    # The proxy set and everything off the allowlist are out of scope: neither
    # value is a path this rule can judge.
    shared = _dir(tmp_path, "shared", 0o777)
    assert world_writable_forwards({"HTTPS_PROXY": str(shared), "EDITOR": str(shared)}) == ()


def test_a_file_under_a_world_writable_directory_warns(tmp_path):
    # SSL_CERT_FILE names a file, and a file in a world-writable directory is a
    # file any local user can replace — here, with a CA the harness then trusts.
    shared = _dir(tmp_path, "shared", 0o777)
    target = shared / "ca-bundle.pem"
    target.write_text("{}")
    (warning,) = world_writable_forwards({"SSL_CERT_FILE": str(target)})
    assert "SSL_CERT_FILE" in warning


def test_a_warning_carries_no_other_variables_value(tmp_path):
    shared = _dir(tmp_path, "shared", 0o777)
    private = _dir(tmp_path, "s3cr3t-home", 0o700)
    (warning,) = world_writable_forwards({"CODEX_HOME": str(shared), "HOME": str(private)})
    assert "CODEX_HOME" in warning
    assert "s3cr3t-home" not in warning


def test_one_warning_per_offending_variable(tmp_path):
    shared = _dir(tmp_path, "shared", 0o777)
    other = _dir(tmp_path, "other", 0o777)
    warnings = world_writable_forwards({"CODEX_HOME": str(shared), "CLAUDE_CONFIG_DIR": str(other)})
    assert len(warnings) == 2
    assert {name for name in ("CODEX_HOME", "CLAUDE_CONFIG_DIR") for w in warnings if name in w} == {
        "CODEX_HOME",
        "CLAUDE_CONFIG_DIR",
    }


def test_an_empty_environment_warns_about_nothing():
    assert world_writable_forwards({}) == ()


# ── auth_hint (C-1034(4)) ────────────────────────────────────────────────────


def test_auth_env_hints_names_only_registered_harnesses_and_never_forces_a_core_edit():
    """H12: `==` against a hand-written four made a fifth adapter a core edit.

    The equality this replaces asserted the extension point false — registering a
    fifth adapter would have failed here until someone edited `config.py`, which
    is exactly the claim `adapters/__init__.py` makes and H12 found untrue. The
    live property is the containment one: every key must name a *registered*
    harness (a typo'd key would silently hint nothing forever), while an
    unnamed registered harness is fine because `auth_hint` reads the map with
    `.get(harness, frozenset())` and contributes no names for it.

    Importing `ADAPTERS` is safe here and not in `config.py`: the module cycle
    (`nox.config` ← `nox.harness` ← `nox.adapters`) only exists inside `src/`.
    """
    from nox.adapters import ADAPTERS

    assert set(AUTH_ENV_HINTS) <= set(ADAPTERS)
    assert set(AUTH_ENV_HINTS)  # a shrunk-to-empty table must not pass silently


def test_copilot_is_deliberately_empty_until_a_fixture_pins_it():
    # C-1034(4) names GITHUB_TOKEN/GH_TOKEN as candidates *and* says the entry
    # stays empty until a recorded fixture proves the shape; the second clause
    # is the operative one — a guess in a security-adjacent message is worse
    # than silence. WP7d pins it from the real binary.
    assert AUTH_ENV_HINTS["copilot"] == frozenset()


@pytest.mark.parametrize(
    ("harness", "names"),
    [
        ("claude", ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]),
        ("codex", ["OPENAI_API_KEY"]),
        ("opencode", ["ANTHROPIC_API_KEY", "GITHUB_TOKEN"]),
    ],
)
def test_the_hint_names_the_intersection_sorted_and_ends_with_the_trailer(harness, names):
    # A harness that refused for want of credentials is usually a harness whose
    # key nox declined to forward, and saying so is the difference between a
    # bug report and a one-line fix.
    detail = auth_hint(harness, [*reversed(names), "EDITOR", "LD_PRELOAD"])
    assert detail.endswith(AUTH_HINT_TRAILER)
    assert [detail.index(name) for name in sorted(names)] == sorted(detail.index(n) for n in names)
    for name in names:
        assert name in detail
    assert "EDITOR" not in detail
    assert "LD_PRELOAD" not in detail


def test_the_opencode_pattern_entry_matches_with_fnmatchcase():
    detail = auth_hint("opencode", ["OPENCODE_ANTHROPIC_APIKEY"])
    assert "OPENCODE_ANTHROPIC_APIKEY" in detail
    assert detail.endswith(AUTH_HINT_TRAILER)


@pytest.mark.parametrize("name", ["OPENCODE_ANTHROPIC_APIKEYX", "opencode_anthropic_apikey", "OPENCODE_APIKEY_X"])
def test_a_name_outside_the_pattern_contributes_nothing(name):
    assert auth_hint("opencode", [name]) == AUTH_HINT_TRAILER


def test_an_empty_intersection_is_the_trailer_alone():
    assert auth_hint("claude", ["EDITOR", "OPENAI_API_KEY"]) == AUTH_HINT_TRAILER


def test_no_dropped_names_at_all_is_the_trailer_alone():
    assert auth_hint("claude", []) == AUTH_HINT_TRAILER


def test_an_unknown_harness_key_contributes_nothing_and_does_not_raise():
    # This composes an error message, and an error path is the worst place to
    # raise a second error.
    assert auth_hint("gemini", ["ANTHROPIC_API_KEY"]) == AUTH_HINT_TRAILER


def test_the_empty_copilot_entry_yields_the_trailer_alone():
    assert auth_hint("copilot", ["GITHUB_TOKEN", "GH_TOKEN"]) == AUTH_HINT_TRAILER


# ── C-1002 static scan ───────────────────────────────────────────────────────

_CREDENTIAL_NEEDLES = (
    b"~/.claude/.credentials.json",
    b"~/.codex/auth.json",
    b"~/.local/share/opencode/auth.json",
    b".credentials.json",
    b".credentials",
    b"auth.json",
)


def test_no_file_under_src_names_a_harness_credential_store():
    """C-1002: nox spawns the official binary and lets it authenticate as itself.

    Violating this is not a bug, it is a different product — it is what
    separates nox from the tools Anthropic blocked on 2026-04-04. A file cannot
    be opened without being named somewhere, so the store names are the
    testable proxy for "opens a credential file". Modelled on
    `test_hygiene.py`: `git ls-files`, and a floor on the listing so an empty
    result cannot pass silently. The needles are case-sensitive, so the
    uppercase environment names nox does ship — `OPENCODE_AUTH_CONTENT` among
    them — cannot false-positive against the lowercase store filenames.
    """
    sources = _src_files()
    assert len(sources) >= 4, f"an empty listing would pass silently: {sources}"
    offenders = []
    for path in sources:
        if not path.is_file():
            continue
        data = path.read_bytes()
        offenders += [f"{path.relative_to(NOX)}: {needle!r}" for needle in _CREDENTIAL_NEEDLES if needle in data]
    assert offenders == []


def test_tmpdir_is_exempt_from_the_scan_even_when_world_writable(tmp_path):
    """A shared scratch directory is world-writable by design, so scanning it
    warns on essentially every run — and a warning that always fires carries
    nothing. `/tmp` is 0o1777 on every POSIX machine.

    The exemption is about the shape of the variable, not its mode: names in a
    scratch directory are minted by whoever writes them, so there is nothing an
    attacker can pre-create and have read back by name. Both modes are asserted
    so the exemption cannot be mistaken for the sticky rule.
    """
    sticky = _dir(tmp_path, "sticky-tmp", 0o1777)
    plain = _dir(tmp_path, "plain-tmp", 0o777)
    assert world_writable_forwards({"TMPDIR": str(sticky)}) == ()
    assert world_writable_forwards({"TMPDIR": str(plain)}) == ()


def test_the_exemption_is_a_subset_of_the_scanned_set(tmp_path):
    # An exemption for a variable the scan never reaches is a dead line, and one
    # that grows past a single member is the scan quietly turning itself off.
    assert WORLD_WRITABLE_EXEMPT < INBOUND_PATH_VARS
    assert WORLD_WRITABLE_EXEMPT == {"TMPDIR"}


# ── `[review] max_prompt_bytes` — the E53 delivery bound ─────────────────────
#
# The bound exists because the diff rides the prompt (E29) and the prompt is
# built in RAM: peak resident set is a multiple of the diff, so an unbounded
# diff is an unbounded allocation. The multiplier below is the oracle, spelled
# out rather than imported — a test that reads its expectation off the code
# under test proves only self-consistency.


MEASURED_RSS_MULTIPLIER = 8.4
"""Peak RSS over diff bytes, worst case, measured on this tree (E53).

32 MiB of non-ASCII diff through `prompt.render` and the prompt write: 281.8 MB
peak against 33.55 MB of diff. Non-ASCII is the worst case because `_fence`'s
`str.isascii()` fast path does not fire and the `str.translate` copy is real.
"""


def test_the_default_bound_keeps_a_worst_case_run_under_a_gibibyte():
    """The default is traceable to the measurement, not to taste (E53)."""
    assert DEFAULT_MAX_PROMPT_BYTES * MEASURED_RSS_MULTIPLIER <= 1 << 30


def test_the_default_bound_still_spends_most_of_that_budget():
    """The other side of the same sum: a bound made tiny "to be safe" refuses real branches.

    Without this, `max_prompt_bytes = 1` satisfies the ceiling above and denies
    every review nox exists to run.
    """
    assert DEFAULT_MAX_PROMPT_BYTES * MEASURED_RSS_MULTIPLIER >= (1 << 30) / 2


def test_max_prompt_bytes_defaults_to_the_measured_bound():
    assert NoxConfig().max_prompt_bytes == DEFAULT_MAX_PROMPT_BYTES


def test_a_trusted_file_may_set_max_prompt_bytes(tmp_path):
    cfg, warnings = _load(tmp_path, user_toml=f"[review]\nmax_prompt_bytes = {1 << 20}\n")
    assert cfg.max_prompt_bytes == 1 << 20
    assert _mentions(warnings, "max_prompt_bytes") == []


def test_an_untrusted_file_may_not_lower_max_prompt_bytes(tmp_path):
    """T6: a one-character edit in a branch must not deny the review of that branch."""
    cfg, warnings = _load(tmp_path, repo_toml="[review]\nmax_prompt_bytes = 1\n")
    assert cfg.max_prompt_bytes == DEFAULT_MAX_PROMPT_BYTES
    assert _mentions(warnings, "max_prompt_bytes")


def test_an_untrusted_file_may_not_raise_max_prompt_bytes_either(tmp_path):
    """The other direction, and the reason this key is gated where `[review] harness` is not.

    `harness` picks which shipped adversary runs and can express nothing worse.
    This key is a memory bound: a branch that raises it re-opens exactly the
    allocation the bound was measured to close.
    """
    cfg, warnings = _load(tmp_path, repo_toml=f"[review]\nmax_prompt_bytes = {1 << 40}\n")
    assert cfg.max_prompt_bytes == DEFAULT_MAX_PROMPT_BYTES
    assert _mentions(warnings, "max_prompt_bytes")


def test_the_drop_names_the_key_and_never_its_value(tmp_path):
    """C-1035(1): a warning reaches a terminal, and the value is branch-authored."""
    _cfg, warnings = _load(tmp_path, repo_toml="[review]\nmax_prompt_bytes = 1234567\n")
    assert not _mentions(warnings, "1234567")


@pytest.mark.parametrize("literal", ['"big"', "0", "-1", "true", "1.5"])
def test_an_out_of_domain_max_prompt_bytes_falls_back_to_the_default(literal, tmp_path):
    """`true` is in the list on purpose: `isinstance(True, int)` is `True` in Python."""
    cfg, warnings = _load(tmp_path, user_toml=f"[review]\nmax_prompt_bytes = {literal}\n")
    assert cfg.max_prompt_bytes == DEFAULT_MAX_PROMPT_BYTES
    assert _mentions(warnings, "max_prompt_bytes")
