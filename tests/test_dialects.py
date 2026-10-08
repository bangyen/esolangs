"""Dialect settings: public surface, provenance, evaluation and per-language rules."""

import json
import pickle
from dataclasses import FrozenInstanceError
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import DialectSettings, Raster
from esolangs._evaluate import _evaluate
from esolangs._grapheme import GraphemeDialect
from esolangs.cli_debug import _run_tui_session
from esolangs.debugger import make_debugger
from esolangs.interpreters.grid_based import alight
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other import packlang
from esolangs.interpreters.stack_based.grapheme import _Machine, run
from esolangs.tagged import _Tagged
from esolangs.tools.alight import alight as build_alight
from esolangs.tools.alight.balance import _balance_postfix
from esolangs.tools.grapheme import _grapheme_literal, _grapheme_push65
from esolangs.tools.packlang import packlang as build_packlang
from esolangs.tools.rotfuck import rotfuck as build_rotfuck
from esolangs.tui import History, replay
from esolangs.vm import complete_vm, make_vm
from tests.cli_support import call_both
from tests.interpreters.test_packlang import DEPENDENCY
from tests.witness_tables import witnesses

CASES = [
    ("Alight", DialectSettings(expression_syntax="postfix")),
    ("Packlang", DialectSettings(literal_policy="binary_digits")),
    ("ROTfuck", DialectSettings(rotation="backward")),
    ("Grapheme", DialectSettings(integer_conversion="after_each_letter")),
    ("SLOW ACV MAMMALIAN", DialectSettings(cell_modulus=255, io_modulus=256)),
]


def test_conversion_reaches_debugger_and_bound_language():
    settings = DialectSettings(integer_conversion="after_each_letter")
    language = esolangs.Language("Grapheme")
    assert language.run("FAFY", settings=settings) == "10"
    debugger = make_debugger("Grapheme", "FAFY", settings=settings)
    debugger.run(max_steps=10)
    assert debugger.vm.output == "10"


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


@pytest.mark.parametrize("inputs", [1, 6])
def test_balanced_postfix_chunks_execute(inputs):
    table = "01" * (1 << (inputs - 1))
    settings = DialectSettings(expression_syntax="postfix")
    program = esolangs.generate("Alight", table, balance=True, settings=settings)
    assert _evaluate("Alight", program, inputs=inputs, settings=settings) == table


@pytest.mark.medium
def test_cli_generate_and_run_share_settings(tmp_path: Path, capsys):
    choices = '{"expression_syntax":"postfix"}'
    generated, _ = call_both(
        ["generate", "--settings", choices, "Alight", "0110"], capsys
    )
    path = tmp_path / "alight.txt"
    path.write_text(generated)
    for isolated in ([], ["--isolated"]):
        output, _ = call_both(
            ["run", "--settings", choices, *isolated, "Alight", str(path)],
            capsys,
            stdin="10",
        )
        assert output.strip() == "1"


@pytest.mark.parametrize("choices", ["[]", "no json", '{"eof":true}'])
def test_cli_invalid_settings_precede_io(choices, capsys):
    with (
        patch("esolangs.cli_run._read_program", side_effect=AssertionError("read")),
        pytest.raises(SystemExit) as caught,
    ):
        call_both(["run", "--settings", choices, "Fargo", "missing"], capsys)
    assert caught.value.code == 2


def test_cli_help_shows_literal_settings_json(capsys):
    with pytest.raises(SystemExit) as caught:
        call_both(["generate", "--help"], capsys)
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    assert '{"expression_syntax":"postfix"}' in help_text


def test_single_choice_languages_refuse_other_keys():
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("Alight", Unreadable(), settings=DialectSettings(cell_modulus=255))


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


@pytest.mark.medium
def test_postfix_one_entry_chunks():
    # Width 1 forces 64 one-entry chunks; parity would hide reversed inputs.
    table = "".join(str(((row * 37) ^ (row >> 1)).bit_count() % 2) for row in range(64))
    settings = DialectSettings(expression_syntax="postfix")
    source = esolangs.generate("Alight", table, width=1, settings=settings)
    assert _evaluate("Alight", source, inputs=6, settings=settings) == table


@pytest.mark.parametrize("template", [False, True])
def test_text_pickle_retains_settings(template):
    settings = DialectSettings()
    source = esolangs.generate("Bitdeque", "0110", settings=settings)
    if not template:
        source = esolangs.instantiate("Bitdeque", source, [1, 0])
    restored = pickle.loads(pickle.dumps(source))
    assert restored.settings == settings
    assert type(restored) is type(source)
    if template:
        restored = esolangs.instantiate("Bitdeque", restored, [1, 0])
    assert esolangs.run("Bitdeque", restored) == "1"


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


def test_partial_overrides_merge_and_validate():
    settings = DialectSettings(cell_modulus=256, io_modulus=255)
    source = _Tagged("SEED " * 255 + "DIGEST PRONOUNCE", "SLOW ACV MAMMALIAN", settings)
    assert esolangs.run("SLOW ACV MAMMALIAN", source) == chr(0)
    assert esolangs.run(
        "SLOW ACV MAMMALIAN", source, settings=DialectSettings(io_modulus=256)
    ) == chr(255)
    assert source.settings is settings
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(
            "SLOW ACV MAMMALIAN", source, settings=DialectSettings(cell_modulus=257)
        )
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.run("SLOW ACV MAMMALIAN", source, settings={})


@pytest.mark.parametrize(
    "isolated", [False, pytest.param(True, marks=pytest.mark.medium)]
)
def test_loaded_text_tag_is_respected(isolated):
    source = _Tagged(
        "FAFY", "Grapheme", DialectSettings(integer_conversion="after_each_letter")
    )
    stream = StringIO()
    stream.read = lambda: source
    assert esolangs.run("Grapheme", stream, isolated=isolated) == "10"
    stream = StringIO()
    stream.read = lambda: source
    assert complete_vm(make_vm("Grapheme", stream), 10) == "10"


def test_plain_text_needs_explicit_settings():
    settings = DialectSettings()
    template = esolangs.generate("Bitdeque", "0110", settings=settings)
    assert not hasattr(str(template), "settings")
    filled = esolangs.instantiate("Bitdeque", str(template), [1, 0], settings=settings)
    assert filled.settings is settings
    assert esolangs.run("Bitdeque", filled) == "1"


def test_foreign_language_guard_precedes_retained_choices():
    source = esolangs.generate(
        "Alight", "01", settings=DialectSettings(expression_syntax="postfix")
    )
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        esolangs.run("Brainfuck", source)


def test_empty_tag_metadata_and_template_override():
    source = esolangs.generate("Brainfuck", "01")
    assert source.settings is None
    assert (
        esolangs.run("Brainfuck", source, stdin="1", settings=DialectSettings()) == "1"
    )
    settings = DialectSettings()
    template = esolangs.generate("Bitdeque", "0110", settings=settings)
    filled = esolangs.instantiate(
        "Bitdeque", template, [1, 0], settings=DialectSettings()
    )
    assert filled.settings == settings
    assert esolangs.run("Bitdeque", filled) == "1"


def test_inherited_choices_are_checked_before_input():
    source = _Tagged("+.", "brainfuck", DialectSettings(cell_modulus=255))
    with pytest.raises(esolangs.ArgumentError, match="dialect settings"):
        esolangs.run("Brainfuck", source, stdin=Unreadable())


def test_evaluation_inherits_loaded_metadata():
    source = esolangs.generate(
        "Grapheme",
        "01",
        settings=DialectSettings(integer_conversion="after_each_letter"),
    )
    stream = StringIO()
    stream.read = lambda: source
    assert _evaluate("Grapheme", stream, inputs=1) == "01"


def test_default_pickle_has_no_retained_choices():
    source = esolangs.generate("Brainfuck", "01")
    restored = pickle.loads(pickle.dumps(source))
    assert restored.settings is None
    assert esolangs.run("Brainfuck", restored, stdin="1") == "1"


def test_generation_rejects_untyped_settings():
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.generate("Brainfuck", "01", settings={})


@pytest.mark.parametrize("language", ["Brainfuck", "123"])
def test_evaluation_refuses_settings_before_source_reads(language):
    settings = DialectSettings(cell_modulus=255)
    with pytest.raises(esolangs.ArgumentError):
        _evaluate(language, Unreadable(), inputs=1, settings=settings)


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_empty_settings_survive_termination_evaluation(isolated):
    source = esolangs.generate("123", "01")
    assert (
        _evaluate(
            "123", source, inputs=1, settings=DialectSettings(), isolated=isolated
        )
        == "01"
    )


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


def test_metadata_is_a_fresh_copy():
    info = esolangs.describe("Grapheme")["dialect_settings"]
    info["integer_conversion"]["default"] = "after_each_letter"
    again = esolangs.describe("Grapheme")["dialect_settings"]
    assert again["integer_conversion"]["default"] == "between_letters"


def test_cli_json_describes_dialect_choices(capsys):
    output, _ = call_both(["describe", "--json", "Grapheme"], capsys)
    schema = json.loads(output)["dialect_settings"]
    assert schema["integer_conversion"]["default"] == "between_letters"
    assert schema["integer_conversion"]["requires"] == {}


# The default mode's readings are pinned in tests/interpreters/test_grapheme.py.
@pytest.mark.parametrize(
    ("source", "expected"),
    [("FAFY", "10"), ("FABFY", "120"), ("FZFY", "0"), ("EABFCEJY", "120")],
)
def test_literal_and_string_conversion(source, expected):
    io = ScriptedIO("")
    run(source, io, integer_conversion="after_each_letter")
    assert io.getvalue() == expected


def test_unterminated_modes_flush_in_called_frames():
    options = {"integer_conversion": "after_each_letter"}
    machine = _Machine("FA", ScriptedIO(""), **options)
    while not machine.halted:
        machine.step()
    assert machine.stack == [10]
    settings = DialectSettings(**options)
    assert esolangs.run("Grapheme", "HFAHIY", settings=settings) == "10"


# The dialect is machine-wide; one string call and one Z rewind witness it.
@pytest.mark.parametrize("source", ["EFAFYEG", "FZFHFAFYMHZ"])
def test_called_code_uses_selected_conversion(source):
    assert (
        esolangs.run(
            "Grapheme",
            source,
            settings=DialectSettings(integer_conversion="after_each_letter"),
        )
        == "10"
    )


def test_numeric_and_function_conversion_remain_literal():
    assert (
        esolangs.run(
            "Grapheme",
            "FAFJYHABHJY",
            settings=DialectSettings(integer_conversion="after_each_letter"),
        )
        == "102"
    )


def test_string_skip_count_uses_conversion():
    source = "FZFEAEFZFV" + "P" * 9 + "TY"
    settings = DialectSettings(integer_conversion="after_each_letter")
    assert esolangs.run("Grapheme", source, settings=settings) == "0"
    assert esolangs.run("Grapheme", source) == "1"


@pytest.mark.parametrize(("source", "expected"), [("FAFDY", "1"), ("EABEDY", "AB")])
def test_unset_names_read_as_themselves(source, expected):
    assert esolangs.run("Grapheme", source) == expected


@pytest.mark.parametrize(
    "choices", [{"integer_conversion": "bad"}, {"integer_conversion": 1}]
)
def test_invalid_settings_precede_source_reads(choices):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("Grapheme", Unreadable(), settings=DialectSettings(**choices))


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


@pytest.mark.medium
def test_generated_corpus():
    settings = DialectSettings(integer_conversion="after_each_letter")
    for n in range(1, 4):
        for table in witnesses(n):
            for balance in (False, True):
                source = esolangs.generate(
                    "Grapheme", table, settings=settings, balance=balance
                )
                assert _evaluate("Grapheme", source, inputs=n) == table


@pytest.mark.medium
def test_prose_conversion_at_six_inputs():
    table = "".join(str(row.bit_count() & 1) for row in range(64))
    source = esolangs.generate(
        "Grapheme",
        table,
        settings=DialectSettings(integer_conversion="after_each_letter"),
    )
    assert _evaluate("Grapheme", source, inputs=6) == table


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_portable_settings_vm_and_override(isolated):
    settings = DialectSettings(integer_conversion="after_each_letter")
    source = _Tagged("FAFY", "Grapheme", settings)
    restored = esolangs.load_program(
        "Grapheme", esolangs.dump_program("Grapheme", source)
    )
    assert esolangs.run("Grapheme", restored, isolated=isolated) == "10"
    assert esolangs.run("Grapheme", restored, max_steps=20) == "10"
    assert complete_vm(make_vm("Grapheme", restored), 20) == "10"
    assert (
        esolangs.run(
            "Grapheme",
            restored,
            settings=DialectSettings(integer_conversion="between_letters"),
        )
        == "1"
    )
    assert source.settings == settings


def test_metadata():
    settings = esolangs.describe("Grapheme")["dialect_settings"]
    assert settings["integer_conversion"]["default"] == "between_letters"
    assert settings["integer_conversion"]["choices"] == (
        "between_letters",
        "after_each_letter",
    )
    assert set(settings) == {"integer_conversion"}


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


@pytest.mark.parametrize(
    "isolated", [False, pytest.param(True, marks=pytest.mark.medium)]
)
def test_rotfuck_rotation_reaches_every_execution_path(isolated):
    """The wiki cat ``,[`` echoes backward; forward, ``,,`` does instead."""
    forward = DialectSettings(rotation="forward")
    assert esolangs.run("ROTfuck", ",[", stdin="x", isolated=isolated) == "x"
    assert (
        esolangs.run("ROTfuck", ",,", stdin="x", settings=forward, isolated=isolated)
        == "x"
    )
    assert (
        complete_vm(make_vm("ROTfuck", ",,", stdin="x", settings=forward), 100) == "x"
    )
    assert complete_vm(make_vm("ROTfuck", ",,", stdin="x"), 100) == ""
    with pytest.raises(esolangs.ArgumentError, match="backward"):
        esolangs.generate("ROTfuck", "01", settings=forward)


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


def test_cli_debug_uses_settings(tmp_path: Path, capsys):
    source = tmp_path / "conversion.grapheme"
    source.write_text("FAFY")
    output, _ = call_both(
        [
            "debug",
            "--settings",
            '{"integer_conversion":"after_each_letter"}',
            "Grapheme",
            str(source),
        ],
        capsys,
    )
    assert "halted: yes" in output
    assert "output: '10'" in output


def test_tui_settings_reach_wrapper():
    settings = DialectSettings(integer_conversion="after_each_letter")
    with patch("esolangs.cli_debug.run_tui") as run:
        _run_tui_session("Grapheme", "FAFY", "", {}, None, settings)
    assert run.call_args.kwargs["settings"] is settings


def test_tui_replay_retains_settings():
    settings = DialectSettings(integer_conversion="after_each_letter")
    history = History("Grapheme", "FAFYPPPP", settings=settings)
    history.budget = 1
    assert history.at(8).output == "10"
    assert history.at(4).output == "10"
    assert history.at(2) == replay("Grapheme", "FAFYPPPP", "", 2, settings=settings)


def test_postfix_balance_model_checks_rendering():
    with (
        patch("esolangs.tools.alight.balance._alight_folded", return_value="bad"),
        pytest.raises(AssertionError, match="postfix fold model"),
    ):
        _balance_postfix("0110", 2, "x" * 100)
    assert _balance_postfix("01", 1, "x") == "x"


@pytest.mark.parametrize("plain", [False, True])
def test_balanced_bitdeque_setters(plain):
    settings = DialectSettings()
    table = "10010110"
    program = esolangs.generate("Bitdeque", table, balance=True, settings=settings)
    for row, expected in enumerate(table):
        source = str(program) if plain else program
        bits = tuple(map(int, format(row, "03b")))
        filled = esolangs.instantiate(
            "Bitdeque", source, bits, truth_table=table, settings=settings
        )
        assert esolangs.run("Bitdeque", filled, settings=settings) == expected
