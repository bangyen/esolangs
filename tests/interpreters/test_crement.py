"""Direct transition and operand guards for Crement."""

import pytest

from esolangs.exceptions import HaltError, ProgramError
from esolangs.interpreters.other.crement import (
    _advance,
    _Instruction,
    _Machine,
    _number,
    _State,
)


def test_transition_is_pure_over_immutable_state() -> None:
    machine = _Machine("+D 0 4")
    initial = machine.state
    advanced = _advance(initial)

    assert _advance(initial) == advanced
    assert machine.state is initial
    assert initial.program[0].data == 4
    assert advanced.program[0].data == 5


def test_a_number_with_no_terms_is_rejected() -> None:
    """An empty operand parses as a sum of nothing, not as zero."""
    with pytest.raises(ProgramError, match="at least one term"):
        _number("", {}, 0)


def test_a_negative_pointer_halts() -> None:
    """``_Machine`` cannot start below zero, so the guard is the transition's."""
    state = _State(ip=-1, program=(_Instruction("J", 1, 0, 0),))
    with pytest.raises(HaltError, match="negative address"):
        _advance(state)
