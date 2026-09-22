"""Tests for the pure Crement interpreter."""

import pytest

from esolangs.exceptions import HaltError, ProgramError
from esolangs.interpreters.other.crement import (
    _advance,
    _Instruction,
    _Machine,
    _number,
    _parse,
    _State,
)
from esolangs.vm import run_until_halt_or_cycle


def _halts(program: str) -> bool:
    return run_until_halt_or_cycle(_Machine(program))


def test_positive_and_negative_jump_conditions() -> None:
    assert not _halts("+J 0 1")
    assert _halts("+J 0 0")
    assert not _halts("-J 0 -1")
    assert _halts("-J 0 1")


def test_data_instruction_rewrites_the_target_data() -> None:
    machine = _Machine("+D 1 4\n+J 2 0")
    machine.step()
    assert machine.state.program[1].data == 5
    assert machine.state.program[1].address == 2
    assert _advance(machine.state).ip == 2


def test_address_instruction_rewrites_the_target_address() -> None:
    machine = _Machine("+A 1 0\n+J 2 1")
    machine.step()
    assert machine.state.program[1].address == 1
    assert not run_until_halt_or_cycle(machine)


def test_negative_write_and_write_past_end() -> None:
    machine = _Machine("-D 1 4\n+D 9 7")
    machine.step()
    assert machine.state.program[1].data == 3
    machine.step()
    assert machine.halted


def test_labels_here_and_signed_sums_resolve() -> None:
    program = _parse(":start +J end-start 0 * forward\n:end -D @-1 start+2")
    assert (program[0].address, program[0].data) == (1, 0)
    assert (program[1].address, program[1].data) == (0, 2)


def test_transition_is_pure_over_immutable_state() -> None:
    machine = _Machine("+D 0 4")
    initial = machine.state
    advanced = _advance(initial)

    assert _advance(initial) == advanced
    assert machine.state is initial
    assert initial.program[0].data == 4
    assert advanced.program[0].data == 5
    assert hash(initial)


@pytest.mark.parametrize(
    ("program", "message"),
    [
        (":1bad +J 0 0", "invalid label"),
        (":x +J 0 0\n:x +J 0 0", "duplicate label"),
        ("+J nowhere 0", "undefined label"),
        ("J 0 0", "invalid opcode"),
        ("+J 0", "three fields"),
        ("+J 1x 0", "invalid number"),
    ],
)
def test_malformed_source_is_rejected(program: str, message: str) -> None:
    with pytest.raises(ProgramError, match=message):
        _Machine(program)


@pytest.mark.parametrize("program", ["+J -1 1", "+D -1 0"])
def test_negative_target_is_an_explicit_undefined_operation(program: str) -> None:
    machine = _Machine(program)
    with pytest.raises(HaltError, match="negative address"):
        machine.step()


def test_a_number_with_no_terms_is_rejected() -> None:
    """An empty operand parses as a sum of nothing, not as zero."""
    with pytest.raises(ProgramError, match="at least one term"):
        _number("", {}, 0)


def test_a_negative_pointer_halts() -> None:
    """``_Machine`` cannot start below zero, so the guard is the transition's."""
    state = _State(ip=-1, program=(_Instruction("J", 1, 0, 0),))
    with pytest.raises(HaltError, match="negative address"):
        _advance(state)
