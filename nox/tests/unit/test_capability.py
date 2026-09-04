"""The closed capability enum (C-1013/E4), the launcher prefix and model-literal validation."""

from dataclasses import FrozenInstanceError, fields

import pytest

from nox.capability import REQUIRED, Capability, Launcher, ModelSpecT


def test_capability_has_exactly_three_members():
    # E4/D-f: a fourth member must fail here — an unread member of a security
    # enum invites a gate nothing checks.
    assert set(Capability) == {
        Capability.ENUMERABLE_DENY,
        Capability.ENFORCED_READ_ONLY,
        Capability.STRUCTURED_OUTPUT,
    }


def test_capability_values_are_the_wire_literals():
    assert {m.name: m.value for m in Capability} == {
        "ENUMERABLE_DENY": "enumerable_deny",
        "ENFORCED_READ_ONLY": "enforced_read_only",
        "STRUCTURED_OUTPUT": "structured_output",
    }


def test_required_is_the_shipped_literal_set():
    # C-1013: the required set is itself a literal, or "raises on a missing
    # required capability" is a contract no test can be written against.
    assert REQUIRED == frozenset({Capability.ENUMERABLE_DENY})


def test_enforced_read_only_is_deliberately_not_required():
    # OpenCode ships without it and still launches, with the absence stamped
    # into Containment.enforced_read_only rather than papered over (C-1013).
    assert Capability.ENFORCED_READ_ONLY not in REQUIRED


@pytest.mark.parametrize(
    ("prefix", "args", "expected"),
    [
        ((), (), ("claude",)),
        ((), ("-p", "review"), ("claude", "-p", "review")),
        (
            ("ocx", "package", "exec", "ocx.sh/anomalyco/opencode:1.18.22", "--"),
            ("-p",),
            ("ocx", "package", "exec", "ocx.sh/anomalyco/opencode:1.18.22", "--", "claude", "-p"),
        ),
    ],
)
def test_argv_puts_the_prefix_before_the_binary(prefix, args, expected):
    argv = Launcher(binary="claude", prefix=prefix).argv(*args)
    assert argv == expected
    assert isinstance(argv, tuple)


def test_launcher_prefix_defaults_to_no_words():
    # Every parametrized case above passes `prefix` explicitly, so the default
    # itself is unpinned there: a default carrying argv words would silently
    # prepend them to every spawn.
    launcher = Launcher(binary="claude")
    assert launcher.prefix == ()
    assert launcher.argv("-p") == ("claude", "-p")


@pytest.mark.parametrize(
    ("binary", "prefix"),
    [
        ("", ()),
        ("", ("ocx",)),
        ("claude", ("",)),
        ("claude", ("ocx", "package", "exec", "")),
    ],
)
def test_launcher_rejects_an_empty_argv_word(binary, prefix):
    # An empty word reaches execve as an empty argument; `--` and other
    # leading-dash words are legitimate in a wrapper prefix and stay allowed.
    with pytest.raises(ValueError):
        Launcher(binary=binary, prefix=prefix)


@pytest.mark.parametrize("literal", ["sonnet", "anthropic/claude-sonnet-4", "gpt-5.4"])
def test_of_normalizes_a_bare_str(literal):
    assert ModelSpecT.of(literal) == ModelSpecT(model=literal, effort=None)


@pytest.mark.parametrize("spec", [ModelSpecT(model="o3"), ModelSpecT(model="o3", effort="high")])
def test_of_returns_an_existing_spec_unchanged(spec):
    assert ModelSpecT.of(spec) is spec


@pytest.mark.parametrize(
    "literal",
    [
        "-c",
        "--model",
        "-",
        "sonnet high",
        " sonnet",
        "sonnet ",
        "son\tnet",
        "\xa0sonnet",  # NBSP — isspace() true, and not printable either
        "model\x00",  # NUL — reaches Popen verbatim
        "\x1b[2Jsonnet",  # ESC — reaches a log verbatim
        "sonnet\u200b",  # zero-width space — invisible in every review of the config
    ],
)
def test_of_rejects_literals_that_would_smuggle_an_argv_fragment(literal):
    # C-1030 guard: Codex's effort knob rides `-c`, which C-1023 refuses from
    # passthrough, and a non-printable character reaches Popen or a log as-is.
    with pytest.raises(ValueError):
        ModelSpecT.of(literal)


def test_of_rejects_the_empty_string_because_an_empty_literal_is_not_a_model():
    # Specified here: "" is neither a harness-local model name nor a usable
    # argv word, and `of` is the one place the str arm is unwrapped.
    with pytest.raises(ValueError):
        ModelSpecT.of("")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model": "--dangerously-bypass-approvals-and-sandbox"},
        {"model": ""},
        {"model": "o3", "effort": "-c model_reasoning_effort=high"},
        {"model": "o3", "effort": ""},
        {"model": "o3", "effort": "high\x00"},
    ],
)
def test_direct_construction_is_guarded_too(kwargs):
    # `of()` is not the boundary — an adapter's MODELS table constructs the
    # dataclass directly, so the guard lives in __post_init__ and `effort`
    # is checked on every path rather than never.
    with pytest.raises(ValueError):
        ModelSpecT(**kwargs)


def test_the_guard_normalizes_before_it_asks():
    # A str subclass can lie about its own prefix; str() makes the guard read
    # the characters rather than the object's opinion of them.
    class Liar(str):
        def startswith(self, *args: object, **kwargs: object) -> bool:
            return False

    with pytest.raises(ValueError):
        ModelSpecT(model=Liar("--dangerously-skip-permissions"))


def test_model_spec_is_frozen():
    spec = ModelSpecT(model="sonnet")
    with pytest.raises(FrozenInstanceError):
        setattr(spec, "model", "other")  # noqa: B010 — a direct assignment is a type error, not a runtime one


def test_model_spec_fields():
    # The frozen check above fires for any attribute name, so the field set is
    # pinned here or not at all.
    assert tuple(f.name for f in fields(ModelSpecT)) == ("model", "effort")


def test_launcher_is_frozen():
    launcher = Launcher(binary="claude")
    with pytest.raises(FrozenInstanceError):
        setattr(launcher, "binary", "other")  # noqa: B010 — a direct assignment is a type error, not a runtime one


def test_launcher_fields():
    assert tuple(f.name for f in fields(Launcher)) == ("binary", "prefix")
