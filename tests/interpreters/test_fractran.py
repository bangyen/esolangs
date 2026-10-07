"""Execution tests for the FRACTRAN interpreter."""

import re

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import _choose, _Machine, _parse, run
from tests.interpreters.runner import run_program

#: Conway's PRIMEGAME.  The powers of two it passes through are the primes.
PRIMEGAME = (
    "17/91 78/85 19/51 23/38 29/33 77/29 95/23 77/19 1/17 11/13 13/11 15/14 15/2 55/1"
)


def test_the_two_fraction_adder() -> None:
    """``3/2`` moves every 2 in the value over to a 3: 2**3 * 3**4 -> 3**7."""
    assert run_program(run, "2^3*3^4 3/2") == str(3**7)


def test_a_value_no_fraction_divides_is_printed_at_once() -> None:
    assert run_program(run, "7") == "7"


def test_prime_power_notation_is_only_notation() -> None:
    start, fractions, _offsets = _parse("2^3*5 7/2")
    assert start == 40
    assert fractions == ((7, 2),)


def test_the_first_matching_fraction_wins() -> None:
    """Both divide 6, so the order decides -- the language's only control flow."""
    first = _Machine("6 5/2 7/3", ScriptedIO(""))
    first.step()
    assert first.value == 15
    second = _Machine("6 7/3 5/2", ScriptedIO(""))
    second.step()
    assert second.value == 14


def test_primegame_passes_through_the_primes() -> None:
    machine = _Machine("2 " + PRIMEGAME, ScriptedIO(""))
    seen = []
    for _ in range(60_000):
        if machine.halted:
            break
        value, power = machine.value, 0
        while value % 2 == 0:
            value //= 2
            power += 1
        if value == 1 and power > 1:
            seen.append(power)
        machine.step()
    assert seen[:8] == [2, 3, 5, 7, 11, 13, 17, 19]


@pytest.mark.parametrize(
    ("program", "message"),
    [
        ("", "needs a starting value"),
        ("2 3/x", "not a FRACTRAN number or power"),
        ("0 3/2", "must be positive"),
        ("2 3/0", "divides by zero"),
    ],
)
def test_a_malformed_program_is_refused(program: str, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        run_program(run, program)


def test_the_pointer_is_the_offset_of_the_fraction_about_to_fire() -> None:
    source = "6 5/2 7/3"
    machine = _Machine(source, ScriptedIO(""))
    assert machine.ip == source.index("5/2")
    machine.step()
    assert machine.ip == source.index("7/3")


def test_the_final_print_is_its_own_step() -> None:
    """``halted`` stays false until the value has been printed."""
    machine = _Machine("7", ScriptedIO(""))
    assert not machine.halted
    assert _choose(machine.value, machine.fractions) is None
    machine.step()
    assert machine.halted
    assert machine.ip is None


def test_a_non_positive_numerator_is_refused() -> None:
    with pytest.raises(ValueError, match="is not positive"):
        run_program(run, "5 0/3")
