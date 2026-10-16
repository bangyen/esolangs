"""Tests for the Blindfolded Arithmetic interpreter."""

import pytest

from esolangs.languages.blindfolded_arithmetic.interpreter import _Machine, _quotient
from esolangs.runtime.io import ScriptedIO


@pytest.mark.parametrize(
    ("dividend", "divisor", "quotient"),
    [(7, 2, 3), (-7, 2, -3), (7, -2, -3), (-7, -2, 3), (6, 3, 2)],
)
def test_division_truncates_toward_zero(
    dividend: int, divisor: int, quotient: int
) -> None:
    assert _quotient(dividend, divisor) == quotient


def test_an_empty_program_is_refused_before_reading() -> None:
    """Blank lines and bare separators are no instruction; stdin stays unread."""
    io = ScriptedIO("")
    with pytest.raises(ValueError, match="at least one instruction"):
        _Machine("\n;  \n", io)


def test_ip_is_the_next_instructions_source_offset() -> None:
    machine = _Machine("a=i/i;  b=a+a", ScriptedIO("1\n"))
    assert machine.ip == 0
    machine.step()
    assert machine.ip == 8
    machine.step()
    assert machine.ip == 0
    assert machine.memory == [1, 2, 0, 0, 0, 1]
