"""Grapheme conversion choices are observable and preserve Boolean generation."""

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from esolangs._grapheme import GraphemeDialect
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.grapheme import _Machine, run
from esolangs.tagged import _Tagged
from esolangs.tools.grapheme import _grapheme_literal, _grapheme_push65
from esolangs.vm import complete_vm, make_vm
from tests.cli_support import call_both


@pytest.mark.parametrize("mode", ["between_letters", "after_each_letter"])
@pytest.mark.parametrize(
    ("source", "value"),
    [
        ("FAFY", 1),
        ("FABFY", 12),
        ("FZFY", 0),
        ("FFY", 0),
        ("EABFCEJY", 12),
        ("EZEJY", 0),
        ("EEJY", 0),
    ],
)
def test_literal_and_string_conversion(source, value, mode):
    io = ScriptedIO("")
    run(source, io, integer_conversion=mode)
    assert io.getvalue() == str(value * (10 if mode == "after_each_letter" else 1))


@pytest.mark.parametrize("mode", ["between_letters", "after_each_letter"])
def test_unterminated_modes_flush_in_called_frames(mode):
    options = {"integer_conversion": mode}
    machine = _Machine("FA", ScriptedIO(""), **options)
    while not machine.halted:
        machine.step()
    assert machine.stack == [10 if mode == "after_each_letter" else 1]
    assert esolangs.run("Grapheme", "HFAHIY", settings=DialectSettings(**options)) == (
        "10" if mode == "after_each_letter" else "1"
    )


@pytest.mark.parametrize("source", ["EFAFYEG", "HFAFYHI", "FZFTHFAFYHQ", "FZFHFAFYMHZ"])
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


@pytest.mark.parametrize("source", ["FAFDY", "EABEDY", "HEABEDYHI"])
def test_unset_names(source):
    with pytest.raises(esolangs.HaltError, match="undeclared variable"):
        esolangs.run("Grapheme", source)


def test_function_names_still_fail():
    with pytest.raises(esolangs.HaltError, match="function cannot name"):
        esolangs.run("Grapheme", "HHD")


@pytest.mark.parametrize(
    "choices",
    [
        {"integer_conversion": "bad"},
        {"unset_variables": "bad"},
        {"integer_conversion": 1},
    ],
)
def test_invalid_settings_precede_source_reads(choices):
    class Unreadable:
        def read(self):
            raise AssertionError("invalid settings acquired source")

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
@pytest.mark.parametrize("mode", ["between_letters", "after_each_letter"])
def test_generated_corpus(mode):
    settings = DialectSettings(integer_conversion=mode)
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
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


def test_cli_portable_settings(tmp_path, capsys):
    document, _ = call_both(
        [
            "generate",
            "--portable",
            "--settings",
            '{"integer_conversion":"after_each_letter"}',
            "Grapheme",
            "0110",
        ],
        capsys,
    )
    path = tmp_path / "grapheme.json"
    path.write_text(document)
    restored = esolangs.load_program("Grapheme", path.read_text())
    assert _evaluate("Grapheme", restored, inputs=2) == "0110"


def test_metadata():
    settings = esolangs.describe("Grapheme")["dialect_settings"]
    assert settings["integer_conversion"]["default"] == "between_letters"
    assert settings["integer_conversion"]["choices"] == (
        "between_letters",
        "after_each_letter",
    )
    assert set(settings) == {"integer_conversion"}
