"""Unary diagnostics and snapshot input cursor; semantics are in the oracle."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.unary import _Machine
from tests.interpreters.views import view as vm_view


def _source(brainfuck: str) -> str:
    number = 1
    for command in brainfuck:
        number = 8 * number + "><+-.,[]".index(command)
    return "0" * number


@pytest.mark.parametrize("code", ["1", "O", "0x00", "0☃", "00", "0" * 16])
def test_invalid_encoding(code: str) -> None:
    with pytest.raises(ValueError, match="Unary"):
        _Machine(code, ScriptedIO())


@pytest.mark.parametrize("command", ["[", "]"])
def test_unmatched_decoded_brackets(command: str) -> None:
    with pytest.raises(ValueError, match="unmatched"):
        _Machine(_source(command), ScriptedIO())


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
    assert vm_view(machine, "memory") == [65]
    assert io.position() == 1
    assert machine.snapshot()[-1] == 1
    machine.step()
    assert machine.halted
    assert io.getvalue() == "A"
