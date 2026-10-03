"""Unary sentinel, command order and delegated Brainfuck dialect controls."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.unary import _Machine, decode, run
from tests.interpreters.runner import run_program


def _source(brainfuck: str) -> str:
    number = 1
    for command in brainfuck:
        number = 8 * number + "><+-.,[]".index(command)
    return "0" * number


@pytest.mark.parametrize(("number", "command"), list(enumerate("><+-.,[]", start=8)))
def test_all_eight_codes(number: int, command: str) -> None:
    assert decode("0" * number) == command


def test_wiki_echo_and_command_order() -> None:
    assert decode("0" * 108) == ",."
    assert run_program(run, "0" * 108, "Z") == "Z"
    assert run_program(run, "0" * 84) == "\x01"
    assert run_program(run, "0" * 92) == "ÿ"


@pytest.mark.parametrize("code", ["", "0", " \n\t"])
def test_empty_decoded_program(code: str) -> None:
    assert run_program(run, code) == ""


def test_formatted_source_counts_only_zeros() -> None:
    assert run_program(run, "00\n" + "0" * 106, "A") == "A"


@pytest.mark.parametrize("code", ["1", "O", "0x00", "0☃", "00", "0" * 16])
def test_invalid_encoding(code: str) -> None:
    with pytest.raises(ValueError, match="Unary"):
        _Machine(code, ScriptedIO())


@pytest.mark.parametrize("command", ["[", "]"])
def test_unmatched_decoded_brackets(command: str) -> None:
    with pytest.raises(ValueError, match="unmatched"):
        _Machine(_source(command), ScriptedIO())


def test_byte_wrap_pointer_clamp_and_right_growth() -> None:
    assert run_program(run, _source("<+.")) == "\x01"
    assert run_program(run, _source(">+.")) == "\x01"
    assert run_program(run, _source("-+.")) == "\x00"
    assert run_program(run, _source(",."), "😀") == "\x00"


def test_loop_and_eof_rules() -> None:
    assert run_program(run, _source("-[-].")) == "\x00"
    assert run_program(run, _source("[]")) == ""
    assert run_program(run, _source("+,."), suppress_eof=False) == "\x00"


def test_input_cursor_is_in_snapshot() -> None:
    io = ScriptedIO("A")
    machine = _Machine(_source(",."), io)
    assert machine.ptr == 0
    assert machine.tape == (0,)
    assert machine.input_position() == 0
    machine.step()
    assert machine.ptr == 0
    assert machine.tape == (65,)
    assert machine.input_position() == 1
    assert machine.memory == [65]
    assert io.position() == 1
    assert machine.snapshot()[-1] == 1
    machine.step()
    assert machine.halted
    assert io.getvalue() == "A"


def test_eof_clears_a_previously_read_cell() -> None:
    assert run_program(run, _source(",,."), "A", suppress_eof=False) == "\x00"
