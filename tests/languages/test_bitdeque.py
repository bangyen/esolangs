"""Bitdeque through the shared API, CLI and machinery."""

import json
import pickle

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from esolangs.interpreters.queue_based.bitdeque import (
    suggest_corrections as _bitdeque_corrections,
)
from tests.cli.test_cli_suggest import _repaired
from tests.cli_support import call_both


@pytest.mark.parametrize(
    ("source", "output"),
    [
        ("inverT pussh", "1"),
        ("INVERT PUSH INVERT INJEC", "0 1"),
    ],
)
def test_bitdeque_proposed_repairs_execute(source, output):
    corrections = _bitdeque_corrections(source)
    assert corrections
    assert esolangs.run("Bitdeque", _repaired(source, corrections), timeout=5) == output


def test_bitdeque_multiline_cli_preview_preserves_target_and_file(tmp_path, capsys):
    path = tmp_path / "program.bd"
    source = "inverT\r\nGOT 2\r\n  pussh\r\n"
    path.write_bytes(source.encode())
    out, err = call_both(["suggest", "Bitdeque", str(path)], capsys)
    assert err == ""
    assert f"{path}:1:1: 'inverT' -> 'INVERT'" in out
    assert f"{path}:2:1: 'GOT' -> 'GOTO'" in out
    assert f"{path}:3:3: 'pussh' -> 'PUSH'" in out
    assert "'2' ->" not in out
    assert path.read_bytes() == source.encode()


class TestEveryDumpSaysWhereTheAnswerIs:
    """A dump prints the whole final state, so "where" is the question."""

    def test_a_dump_has_a_pattern_or_a_note(self) -> None:
        """Either a regex that finds the answer, or prose that locates it."""
        silent = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["answer_mode"] == "dump"
            and not esolangs.describe(name)["answer_pattern"]
            and not esolangs.describe(name)["answer_convention"]
        ]
        assert not silent, (
            f"dump languages that never say where the answer is: {silent}"
        )

    def test_bitdeques_note_is_true(self) -> None:
        """It claims the whole dump is the answer bit.  Check that, do not trust it."""
        note = str(esolangs.describe("Bitdeque")["answer_convention"])
        assert "the whole dump is the answer" in note
        template = esolangs.generate("Bitdeque", "0110")
        for combo in range(4):
            bits = [(combo >> (1 - i)) & 1 for i in range(2)]
            program = esolangs.instantiate("Bitdeque", template, bits)
            dump = esolangs.run("Bitdeque", program, stdin="", timeout=10)
            assert dump == "0110"[combo], bits
            assert len(dump) == 1, dump


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


def test_plain_text_needs_explicit_settings():
    settings = DialectSettings()
    template = esolangs.generate("Bitdeque", "0110", settings=settings)
    assert not hasattr(str(template), "settings")
    filled = esolangs.instantiate("Bitdeque", str(template), [1, 0], settings=settings)
    assert filled.settings is settings
    assert esolangs.run("Bitdeque", filled) == "1"


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


@pytest.mark.medium
def test_filled_template_becomes_portable_text():
    source = esolangs.generate("Bitdeque", "0110", settings=DialectSettings())
    filled = esolangs.instantiate("Bitdeque", source, [1, 0])
    document = esolangs.dump_program("Bitdeque", filled)
    assert json.loads(document)["kind"] == "text"
    assert esolangs.run("Bitdeque", esolangs.load_program("Bitdeque", document)) == "1"


def test_foreign_language_is_rejected():
    source = esolangs.generate("Bitdeque", "0110", settings=DialectSettings())
    with pytest.raises(esolangs.ProgramError):
        esolangs.dump_program("Brainfuck", source)
    with pytest.raises(esolangs.ProgramError, match="program language"):
        esolangs.load_program("Brainfuck", esolangs.dump_program("Bitdeque", source))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("char", 1),
        ("char", "$$"),
        ("setters", None),
        ("setters", [["x"]]),
        ("setters", [["x", "yy"]]),
        ("setters", []),
    ],
)
def test_invalid_template_fields(field, value):
    document = json.loads(
        esolangs.dump_program("Bitdeque", esolangs.generate("Bitdeque", "0110"))
    )
    document[field] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Bitdeque", json.dumps(document))


@pytest.mark.medium
def test_bound_language_round_trip():
    language = esolangs.Language("Bitdeque")
    source = language.generate("0110", settings=DialectSettings())
    document = language.dump_program(source)
    restored = language.load_program(document)
    assert _evaluate(language.name, restored, inputs=2) == "0110"
    filled = language.instantiate(source, [1, 0])
    document = language.dump_program(filled, settings=DialectSettings())
    assert language.run(language.load_program(document)) == "1"


class TestBitdeque:
    def test_cursor_deque_and_register(self) -> None:
        vm = debugger_api.make_vm("Bitdeque", "PUSH INVERT")
        assert (vm.ip, vm.memory, vm.stack) == (0, [], [0])
        vm.step()  # PUSH appends the register
        assert (vm.ip, vm.memory) == (1, [0])
        vm.step()  # INVERT flips the register
        assert vm.stack == [1]
        assert vm.halted
        assert vm.output == ""  # the deque is not rendered until the next step
        vm.step()  # the post-halt step renders it, as run's own last step does
        assert vm.output == "0"
        vm.step()  # and rendering happens once, not once per step past the halt
        assert vm.output == "0"
