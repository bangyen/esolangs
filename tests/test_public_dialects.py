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
    ("Alight", DialectSettings(expression_syntax="postfix")),
    ("Packlang", DialectSettings(literal_policy="binary_digits")),
    ("Grapheme", DialectSettings(integer_conversion="after_each_letter")),
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


@pytest.mark.parametrize("options", [{}, {"max_steps": 10}, {"isolated": True}])
@pytest.mark.parametrize(
    ("language", "settings"),
    [
        ("Brainfuck", DialectSettings(cell_modulus=256)),
        ("Alight", DialectSettings(expression_syntax="prefix")),
        ("Packlang", DialectSettings(literal_policy="octal")),
        ("FALSE", DialectSettings(integer_conversion="after_each_letter")),
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
    settings = DialectSettings(integer_conversion="after_each_letter")
    with pytest.raises(FrozenInstanceError):
        settings._items = ()  # noqa: SLF001 - test frozen storage
    options = settings.options("Grapheme")
    options["integer_conversion"] = "between_letters"
    assert esolangs.run("Grapheme", "FAFY", settings=settings) == "10"
    assert esolangs.run("Grapheme", "FAFY") == "1"
    assert DialectSettings().options("Unary") == {}


@pytest.mark.parametrize(
    "choices", [{"surprise": 1}, {"eof": []}, {"cell_modulus": True}, {"eof": None}]
)
def test_constructor_refuses_unknown_or_untyped_choices(choices):
    with pytest.raises(esolangs.ArgumentError):
        DialectSettings(**choices)


def test_settings_require_the_public_object():
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        esolangs.run(
            "Brainfuck",
            Unreadable(),
            settings={"integer_conversion": "after_each_letter"},
        )


@pytest.mark.parametrize(("language", "settings"), CASES)
def test_balanced_settings_compute_every_row(language, settings):
    table = "0110"
    program = esolangs.generate(language, table, balance=True, settings=settings)
    assert esolangs.evaluate(language, program, inputs=2, settings=settings) == table


@pytest.mark.parametrize("inputs", [1, 3, 6])
def test_balanced_postfix_chunks_execute(inputs):
    table = "01" * (1 << (inputs - 1))
    settings = DialectSettings(expression_syntax="postfix")
    program = esolangs.generate("Alight", table, balance=True, settings=settings)
    assert (
        esolangs.evaluate("Alight", program, inputs=inputs, settings=settings) == table
    )


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
            ["run", "--settings", choices, "--judge", *isolated, "Alight", str(path)],
            capsys,
            stdin="10",
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


def test_cli_help_shows_literal_settings_json(capsys):
    with pytest.raises(SystemExit) as caught:
        call_both(["generate", "--help"], capsys)
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    assert '{"expression_syntax":"postfix"}' in help_text


@pytest.mark.parametrize("language", ["Bitdeque", "Alight", "Packlang"])
def test_single_choice_languages_refuse_other_keys(language):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(language, Unreadable(), settings=DialectSettings(cell_modulus=255))


@pytest.mark.parametrize(
    "key",
    [
        "index_base",
        "pick_base",
        "unset_variables",
        "unknown_commands",
        "tape_size",
        "boundary",
        "eof",
        "scheduling",
        "deque_cursor",
        "junction_tie_break",
        "undefined_targets",
        "input_framing",
    ],
)
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
