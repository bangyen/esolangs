"""Specification overrides survive public generation and every execution path."""

from dataclasses import FrozenInstanceError
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs.debugger import make_debugger
from esolangs.vm import complete_vm, make_vm
from tests.cli_support import call_both

CASES = [
    ("Bitdeque", DialectSettings(index_base=1)),
    ("Alight", DialectSettings(expression_syntax="postfix")),
    ("Packlang", DialectSettings(literal_policy="binary_digits")),
    (
        "FALSE",
        DialectSettings(pick_base=1, unset_variables="zero", unknown_commands="error"),
    ),
    ("Line", DialectSettings(cell_modulus=255, tape_size=8, boundary="wrap")),
    ("Flowchart", DialectSettings(scheduling="reverse", deque_cursor="shared")),
    (
        "Brainfuck",
        DialectSettings(cell_modulus=65536, tape_size=8, boundary="wrap", eof="zero"),
    ),
    (
        "Factor",
        DialectSettings(
            cell_modulus=None, tape_size=8, boundary="error", eof="unchanged"
        ),
    ),
    ("SLOW ACV MAMMALIAN", DialectSettings(cell_modulus=255, io_modulus=256)),
]


@pytest.mark.medium
@pytest.mark.parametrize(("language", "settings"), CASES)
def test_generated_rows_match_across_execution_paths(language, settings):
    table = "0110"
    program = esolangs.generate(language, table, settings=settings)
    for row, answer in enumerate(table):
        bits = tuple(map(int, format(row, "02b")))
        if esolangs.describe(language)["parameterized"]:
            source = esolangs.instantiate(
                language, str(program), bits, truth_table=table, settings=settings
            )
            stdin = ""
        else:
            source = program
            stdin = esolangs.encode_inputs(language, bits, table)
        direct = esolangs.run(language, source, stdin, settings=settings)
        assert esolangs.read_answer(language, direct) == answer
        assert (
            esolangs.run(language, source, stdin, settings=settings, max_steps=100_000)
            == direct
        )
        assert (
            esolangs.run(
                language,
                source,
                stdin,
                settings=settings,
                isolated=True,
                max_output=1000,
            )
            == direct
        )
        vm = make_vm(language, source, stdin, settings=settings)
        assert complete_vm(vm, 100_000) == direct


@pytest.mark.parametrize(
    ("eof", "expected"),
    [("zero", "\x00"), ("minus_one", chr(255)), ("unchanged", "\x01")],
)
def test_exhausted_input_policy_reaches_debugger_and_bound_language(eof, expected):
    settings = DialectSettings(eof=eof)
    language = esolangs.Language("Brainfuck")
    assert language.run("+,.", settings=settings) == expected
    debugger = make_debugger("Brainfuck", "+,.", settings=settings)
    debugger.run(max_steps=10)
    assert debugger.vm.output == expected
    program = language.generate("01", settings=settings)
    assert language.run(program, "1", settings=settings) == "1"


class Unreadable(StringIO):
    """Fail if argument validation consumes the source or input."""

    def read(self, *_args, **_kwargs):
        raise AssertionError("read before dialect validation")


@pytest.mark.parametrize("options", [{}, {"max_steps": 10}, {"isolated": True}])
@pytest.mark.parametrize(
    ("language", "settings"),
    [
        ("Brainfuck", DialectSettings(boundary="wrap")),
        ("Brainfuck", DialectSettings(cell_modulus=1)),
        ("Brainfuck", DialectSettings(index_base=1)),
        ("Alight", DialectSettings(expression_syntax="prefix")),
        ("Packlang", DialectSettings(literal_policy="octal")),
        ("FALSE", DialectSettings(unset_variables="ignore")),
        ("Line", DialectSettings(tape_size=0)),
        ("Flowchart", DialectSettings(scheduling="random")),
        ("Fargo", DialectSettings(eof="zero")),
        ("SLOW ACV MAMMALIAN", DialectSettings(io_modulus=257)),
    ],
)
def test_invalid_settings_fail_before_reading(language, settings, options):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(language, Unreadable(), Unreadable(), settings=settings, **options)
    with pytest.raises(esolangs.ArgumentError):
        make_vm(language, Unreadable(), Unreadable(), settings=settings)
    with pytest.raises(esolangs.ArgumentError):
        esolangs.generate(language, "01", settings=settings)


def test_settings_are_immutable_and_do_not_change_defaults():
    settings = DialectSettings(eof="zero")
    with pytest.raises(FrozenInstanceError):
        settings._items = ()  # noqa: SLF001 - test frozen storage
    options = settings.options("Brainfuck")
    options["eof"] = "error"
    assert esolangs.run("Brainfuck", ",.", settings=settings) == "\x00"
    with pytest.raises(esolangs.InputExhaustedError):
        esolangs.run("Brainfuck", ",.")
    assert DialectSettings().options("Unary") == {}
    assert esolangs.run("Unary", "0", settings=DialectSettings()) == ""


@pytest.mark.parametrize(
    "choices", [{"surprise": 1}, {"eof": []}, {"cell_modulus": True}, {"eof": None}]
)
def test_constructor_refuses_unknown_or_untyped_choices(choices):
    with pytest.raises(esolangs.ArgumentError):
        DialectSettings(**choices)


def test_settings_require_the_public_object():
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.run("Brainfuck", Unreadable(), settings={"eof": "zero"})


@pytest.mark.medium
def test_isolation_preserves_large_integer_settings():
    settings = DialectSettings(cell_modulus=10**5000)
    assert esolangs.run("Brainfuck", "+.", settings=settings, isolated=True) == "\x01"


def test_scaled_raster_keeps_dialect_settings():
    settings = DialectSettings(cell_modulus=2, tape_size=2, boundary="wrap")
    program = esolangs.generate("Line", "01", scale=2, settings=settings)
    assert esolangs.run("Line", program, "1", settings=settings) == "1"


def test_settings_and_balance_are_refused_explicitly():
    with pytest.raises(esolangs.ArgumentError, match="balance"):
        esolangs.generate(
            "Alight",
            "0110",
            balance=True,
            settings=DialectSettings(expression_syntax="postfix"),
        )


@pytest.mark.medium
def test_cli_generate_and_run_share_settings(tmp_path: Path, capsys):
    choices = '{"index_base":1}'
    generated, _ = call_both(
        ["generate", "--settings", choices, "--bits", "10", "Bitdeque", "0110"], capsys
    )
    path = tmp_path / "bitdeque.txt"
    path.write_text(generated)
    for isolated in ([], ["--isolated"]):
        output, _ = call_both(
            ["run", "--settings", choices, "--judge", *isolated, "Bitdeque", str(path)],
            capsys,
        )
        assert output.strip() == "1"


@pytest.mark.parametrize("choices", ["[]", "no json", '{"eof":true}', '{"eof":"zero"}'])
def test_cli_invalid_settings_precede_io(choices, capsys):
    with (
        patch("esolangs.cli_run._read_program", side_effect=AssertionError("read")),
        pytest.raises(SystemExit) as caught,
    ):
        call_both(["run", "--settings", choices, "Fargo", "missing"], capsys)
    assert caught.value.code == 2


@pytest.mark.parametrize(
    ("language", "settings"),
    [
        ("Brainfuck", DialectSettings(cell_modulus=49)),
        ("Factor", DialectSettings(tape_size=3)),
        ("Line", DialectSettings(tape_size=1)),
    ],
)
def test_generation_refuses_insufficient_dialect_storage(language, settings):
    with pytest.raises(esolangs.ArgumentError, match="requires"):
        esolangs.generate(language, "0110", settings=settings)


@pytest.mark.parametrize("width", [1, 40])
def test_bitdeque_settings_survive_tagged_and_plain_templates(width):
    settings = DialectSettings(index_base=1)
    table = "10010110"
    language = esolangs.Language("Bitdeque")
    template = language.generate(table, width, settings=settings)
    for row, expected in enumerate(table):
        bits = tuple(map(int, format(row, "03b")))
        for source in (template, str(template)):
            filled = language.instantiate(source, bits, width, table, settings=settings)
            assert language.run(filled, settings=settings) == expected


@pytest.mark.parametrize("isolated", [[], ["--isolated", "--max-output", "1"]])
def test_cli_eof_setting_changes_execution(tmp_path: Path, capsys, isolated):
    path = tmp_path / "eof.bf"
    path.write_text("+,.")
    output, _ = call_both(
        ["run", "--settings", '{"eof":"unchanged"}', *isolated, "Brainfuck", str(path)],
        capsys,
    )
    assert output == "\x01"


def test_cli_help_shows_literal_settings_json(capsys):
    with pytest.raises(SystemExit) as caught:
        call_both(["generate", "--help"], capsys)
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    assert '{"index_base":1}' in help_text


@pytest.mark.parametrize("language", ["Bitdeque", "Alight", "Packlang"])
def test_single_choice_languages_refuse_other_keys(language):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(language, Unreadable(), settings=DialectSettings(eof="zero"))


@pytest.mark.medium
@pytest.mark.parametrize(
    ("choices", "source", "expected"),
    [
        ({"pick_base": 1}, "7 8 1ø.", "8"),
        ({"unset_variables": "zero"}, "a;.", "0"),
        ({"unknown_commands": "error"}, '"`"{`}', "`"),
    ],
)
def test_false_choices_are_observable_through_public_paths(choices, source, expected):
    settings = DialectSettings(**choices)
    assert esolangs.run("FALSE", source, settings=settings) == expected
    assert esolangs.run("FALSE", source, settings=settings, max_steps=20) == expected
    assert esolangs.run("FALSE", source, settings=settings, isolated=True) == expected


@pytest.mark.medium
def test_unary_uses_its_own_default_eof_and_accepts_overrides():
    source = "0" * 108  # Unary's sentinel and comma/dot codes encode ,.
    assert esolangs.run("Unary", source, settings=DialectSettings()) == "\x00"
    settings = DialectSettings(cell_modulus=255, eof="minus_one")
    expected = chr(254)
    assert esolangs.run("Unary", source, settings=settings) == expected
    assert esolangs.run("Unary", source, settings=settings, max_steps=2) == expected
    assert esolangs.run("Unary", source, settings=settings, isolated=True) == expected
    assert complete_vm(make_vm("Unary", source, settings=settings), 2) == expected
