"""Dialect settings: public surface, provenance, evaluation and per-language rules."""

import pickle
from dataclasses import FrozenInstanceError
from io import StringIO
from unittest.mock import patch

import pytest

import esolangs
from esolangs import DialectSettings, Raster
from esolangs._grapheme import GraphemeDialect
from esolangs.interpreters.grid_based import alight
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other import packlang
from esolangs.interpreters.stack_based.grapheme import run
from esolangs.tagged import _Tagged
from esolangs.tools.alight import alight as build_alight
from esolangs.tools.alight.balance import _balance_postfix
from esolangs.tools.grapheme import _grapheme_literal, _grapheme_push65
from esolangs.tools.packlang import packlang as build_packlang
from esolangs.tools.rotfuck import rotfuck as build_rotfuck
from esolangs.vm import make_vm
from tests.cli_support import call_both
from tests.interpreters.test_packlang import DEPENDENCY

CASES = [
    ("Alight", DialectSettings(expression_syntax="postfix")),
    ("Packlang", DialectSettings(literal_policy="binary_digits")),
    ("ROTfuck", DialectSettings(rotation="backward")),
    ("Grapheme", DialectSettings(integer_conversion="after_each_letter")),
    ("SLOW ACV MAMMALIAN", DialectSettings(cell_modulus=255, io_modulus=256)),
]


class Unreadable(StringIO):
    """Fail if argument validation consumes the source or input."""

    def read(self, *_args, **_kwargs):
        raise AssertionError("read before dialect validation")


@pytest.mark.parametrize(
    ("language", "settings", "options"),
    [
        ("Brainfuck", DialectSettings(cell_modulus=256), {}),
        ("Brainfuck", DialectSettings(cell_modulus=256), {"isolated": True}),
        ("Alight", DialectSettings(list_update="deep"), {}),
        ("Packlang", DialectSettings(literal_policy="octal"), {}),
        ("ROTfuck", DialectSettings(rotation="sideways"), {}),
        ("SLOW ACV MAMMALIAN", DialectSettings(io_modulus=257), {}),
    ],
)
def test_invalid_settings_fail_before_reading(language, settings, options):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(
            language, Unreadable(), stdin=Unreadable(), settings=settings, **options
        )
    with pytest.raises(esolangs.ArgumentError):
        make_vm(language, Unreadable(), stdin=Unreadable(), settings=settings)
    with pytest.raises(esolangs.ArgumentError):
        esolangs.generate(language, "01", settings=settings)


def test_settings_are_immutable_and_do_not_change_defaults():
    settings = DialectSettings(integer_conversion="after_each_letter")
    with pytest.raises(FrozenInstanceError):
        settings._items = ()  # noqa: SLF001 - test frozen storage
    options = settings.options("Grapheme")
    options["integer_conversion"] = "between_letters"
    assert esolangs.run("Grapheme", "FAFY", settings=settings) == "10"
    assert esolangs.run("Grapheme", "FAFY") == "1"
    assert DialectSettings().options("Unary") == {}


def test_constructor_refuses_a_bool_integer():
    with pytest.raises(esolangs.ArgumentError):
        DialectSettings(cell_modulus=True)


def test_settings_require_the_public_object():
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.run(
            "Brainfuck",
            Unreadable(),
            settings={"integer_conversion": "after_each_letter"},
        )


def test_cli_help_shows_literal_settings_json(capsys):
    with pytest.raises(SystemExit) as caught:
        call_both(["generate", "--help"], capsys)
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    assert '{"expression_syntax":"postfix"}' in help_text


@pytest.mark.parametrize("key", ["index_base", "eof", "input_framing"])
def test_omission_policies_are_not_public_choices(key):
    with pytest.raises(esolangs.ArgumentError, match="unknown dialect setting"):
        DialectSettings(**{key: "default"})


def test_only_conflicting_specs_publish_choices():
    languages = {
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["dialect_settings"]
    }
    assert languages == {name for name, _ in CASES}


@pytest.mark.parametrize("balance", [False, True])
def test_raster_scaling_retains_settings(balance):
    settings = DialectSettings()
    source = esolangs.generate(
        "Line", "01", scale=2, balance=balance, settings=settings
    )
    assert source.settings is settings
    assert source.tagged(source.language).settings is settings
    assert source.upscaled(1).settings is settings
    assert source.upscaled(2).settings is settings
    assert esolangs.run("Line", source, stdin="1") == "1"
    assert Raster.from_png(source.to_png()).settings is None
    assert source.tagged("Piet").settings is None


def test_inherited_choices_are_checked_before_input():
    source = _Tagged("+.", "brainfuck", DialectSettings(cell_modulus=255))
    with pytest.raises(esolangs.ArgumentError, match="dialect settings"):
        esolangs.run("Brainfuck", source, stdin=Unreadable())


def test_default_pickle_has_no_retained_choices():
    source = esolangs.generate("Brainfuck", "01")
    restored = pickle.loads(pickle.dumps(source))
    assert restored.settings is None
    assert esolangs.run("Brainfuck", restored, stdin="1") == "1"


def test_generation_rejects_untyped_settings():
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.generate("Brainfuck", "01", settings={})


@pytest.mark.medium
def test_every_reported_default_and_choice_is_accepted():
    for language in esolangs.list_languages():
        schema = esolangs.describe(language)["dialect_settings"]
        defaults = {key: item["default"] for key, item in schema.items()}
        DialectSettings(**defaults).options(language)
        for key, item in schema.items():
            values = item["choices"]
            if values is None:
                values = (item["minimum"], None)
            for value in values:
                selected = defaults | {key: value}
                for dependency in item["requires"].get(str(value), ()):
                    selected[dependency] = 8
                DialectSettings(**selected).options(language)
            if item["minimum"] is not None:
                with pytest.raises(esolangs.ArgumentError):
                    DialectSettings(**(defaults | {key: item["minimum"] - 1})).options(
                        language
                    )


# The default mode's readings are pinned in tests/interpreters/test_grapheme.py.
@pytest.mark.parametrize(
    ("source", "expected"),
    [("FAFY", "10"), ("FABFY", "120"), ("FZFY", "0"), ("EABFCEJY", "120")],
)
def test_literal_and_string_conversion(source, expected):
    io = ScriptedIO("")
    run(source, io, integer_conversion="after_each_letter")
    assert io.getvalue() == expected


@pytest.mark.parametrize("mode", ["between_letters", "after_each_letter"])
def test_generator_literals_are_exact(mode):
    dialect = GraphemeDialect(integer_conversion=mode)
    for value in (0, 1, 2, 5, 13, 16, 106, 1006, 1263460, 5666666, 9999996):
        io = ScriptedIO("")
        run(_grapheme_literal(value, dialect) + "Y", io, integer_conversion=mode)
        assert io.getvalue() == str(value)
    io = ScriptedIO("")
    run(_grapheme_push65(dialect) + "Y", io, integer_conversion=mode)
    assert io.getvalue() == "65"


# Default notation and literals are covered by the registry-wide generator
# contracts; these pin the alternative dialect on an irregular 5-input table.
_TABLE = "00110110011010100101110010100110"


@pytest.mark.medium
@pytest.mark.parametrize("width", [None, 100])
def test_alight_generated(width):
    source = build_alight(_TABLE, width, expression_syntax="postfix")
    if width is not None:
        assert max(map(len, source.splitlines())) <= width
    for row in range(len(_TABLE)):
        io = ScriptedIO(format(row, "05b"))
        alight.run(source, io, expression_syntax="postfix")
        assert io.getvalue() == _TABLE[row]


@pytest.mark.medium
@pytest.mark.parametrize("table", ["0110", _TABLE])
def test_packlang_generated(table):
    source = build_packlang(table, 32, literal_policy="binary_digits")
    n = (len(table) - 1).bit_length()
    for row in range(len(table)):
        io = ScriptedIO(format(row, f"0{n}b"))
        packlang.run(source, io, literal_policy="binary_digits")
        assert io.getvalue() == table[row]


@pytest.mark.medium
def test_packlang_dependency_readings():
    for policy, expected in (("decimal", "°±±°"), ("binary_digits", "0110")):
        io = ScriptedIO("")
        packlang.run(DEPENDENCY, io, literal_policy=policy)
        assert io.getvalue() == expected


@pytest.mark.medium
@pytest.mark.parametrize(
    ("source", "syntax"),
    [("65 1 +", "postfix"), ("65+1", "infix"), ("[65, 66] 0.5", "bad")],
)
def test_alight_notation(source, syntax):
    io = ScriptedIO("")
    if syntax == "bad":
        with pytest.raises(ValueError, match="one value"):
            alight.run(
                f"begin;var a;set a {source};end;", io, expression_syntax="postfix"
            )
    else:
        alight.run(
            f"begin;var a;set a {source};out a;end;", io, expression_syntax=syntax
        )
        assert io.getvalue() == "B"


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 11])
def test_packlang_hybrid_multiple_blocks(n):
    table = "00110110" * (2**n // 8)
    source = build_packlang(table, literal_policy="binary_digits")
    for row in (0, 127, 128, 2**n - 1):
        io = ScriptedIO(format(row, f"0{n}b"))
        packlang.run(source, io, literal_policy="binary_digits")
        assert io.getvalue() == table[row]


@pytest.mark.parametrize(
    ("build", "table", "options", "message"),
    [
        (build_alight, "01", {"expression_syntax": "mixed"}, "expression_syntax"),
        (build_packlang, "01", {"literal_policy": "binary"}, "literal_policy"),
        (build_rotfuck, "01", {"rotation": "sideways"}, "rotation"),
    ],
)
def test_invalid_dialects_are_rejected(build, table, options, message):
    with pytest.raises(ValueError, match=message):
        build(table, **options)


@pytest.mark.medium
def test_settings_do_not_leak_between_runs():
    for build, options in (
        (build_alight, {"expression_syntax": "postfix"}),
        (build_packlang, {"literal_policy": "binary_digits"}),
    ):
        before = build("0110")
        build("0110", **options)
        assert build("0110") == before


@pytest.mark.medium
@pytest.mark.parametrize(
    ("expr", "expected"),
    [("right !", "A"), ("left !", "B"), ("at{[65, 66], 1.5}", "B")],
)
def test_postfix_unary_and_nested_lists(expr, expected):
    io = ScriptedIO("")
    command = (
        f"set a {expr}" if expr.startswith("at") else f"set a 65;skip {expr};set a 66"
    )
    alight.run(f"begin;var a;{command};out a;end;", io, expression_syntax="postfix")
    assert io.getvalue() == expected


@pytest.mark.medium
@pytest.mark.parametrize("expr", ["65 +", "!"])
def test_postfix_operator_requires_operands(expr):
    with pytest.raises(ValueError, match="lacks operands"):
        alight.run(
            f"begin;var a;set a {expr};end;",
            ScriptedIO(""),
            expression_syntax="postfix",
        )


def test_postfix_width_must_be_positive():
    with pytest.raises(ValueError, match="width"):
        build_alight("01", 0, expression_syntax="postfix")


@pytest.mark.parametrize("policy", ["decimal", "binary_digits"])
def test_packlang_literal_roundtrip(policy):
    from esolangs._dialects import PacklangLiterals

    literals = PacklangLiterals(policy)
    for value in (0, 1, 2, 10, 48, 128, 255):
        assert literals.parse(literals.emit(value)) == value
    assert literals.parse("255") == 255


def test_postfix_balance_model_checks_rendering():
    with (
        patch("esolangs.tools.alight.balance._alight_folded", return_value="bad"),
        pytest.raises(AssertionError, match="postfix fold model"),
    ):
        _balance_postfix("0110", 2, "x" * 100)
    assert _balance_postfix("01", 1, "x") == "x"
