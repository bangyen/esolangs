"""Tests for the Rubic interpreter."""

import pytest

from esolangs.languages.rubic.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.contract import CycleContract, EmptyProgramContract

HELLO = (
    ".ww ( +ww ) ! +ww +ww +ww +ww r -wg ! +oo b -og ! ! +wo' ! b' .wg "
    "*oo +oo ! *wg -oo b -og ! b' +oo +oo +oo ! +wg ! l' -wg ! -oo ! .wg "
    "*wg r -wg ! .oo +ww !"
)


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _machine(code: str) -> _Machine:
    return _Machine(code, ScriptedIO(""))


def _cube(code: str) -> object:
    machine = _machine(code)
    while not machine.halted:
        machine.step()
    return machine.state.cube


def test_the_wiki_hello_world() -> None:
    assert _run(HELLO) == "Hello World!\n"


def test_the_wiki_cat_never_reads_and_its_repair_echoes() -> None:
    """After ``r b``, ``go`` is 0; ``og`` is the 1 the cat needs."""
    assert _run("r b -go ( ! ) !", "A") == "\x00"
    assert _run("r b -og ( ! ) !", "A") == "A"


@pytest.mark.parametrize("face", "rulfdbmes")
def test_four_quarter_turns_restore_the_cube(face: str) -> None:
    assert _cube(f"{face} {face} {face} {face}") == _cube("")
    assert _cube(f"{face} {face}'") == _cube("")
    assert _cube(f"{face}2") == _cube(f"{face} {face}")


def test_the_middle_slice_turns_as_r() -> None:
    """``m`` carries the white centre to the back, whose middle column is
    white and the rest blue; turned as ``l`` it would show six green."""
    assert _run("m .wg !") == "\x00"
    assert _run("r .wg !") == "\x03"


def test_commands_are_case_insensitive() -> None:
    assert _run("R .WG !") == "\x03"


def test_division_floors_and_zero_divisors() -> None:
    assert _run("r -wg /ww !") == chr(-1 % 128)  # -3 // 6 floors to -1
    assert _run(".ww /w'w !") == "\x00"  # w'w is 0: V becomes 0
    assert _run(".ww %w'w !") == "\x08"  # ... and % leaves V


def test_a_negative_loop_runs_backwards_and_inverted() -> None:
    assert _cube("-ww ( r u )") == _cube(".ww ( u' r' )")
    assert _cube("-ww ( r u )") != _cube(".ww ( r' u' )")
    assert _run("-ww ( +ww ) !") == chr(-72 % 128)  # +ww became -ww
    assert _run("-ww ( .ww ) !") == chr(-8 % 128)  # .ww set -8
    assert _run("-ww ( %oo ) !") == chr(-8 % 128)  # % is skipped
    assert _run("-ww %oo !") == "\x00"


def test_a_backwards_bang_reads_one_character() -> None:
    assert _run("-ww ( ! ) !", "abcdefgh") == "h"


def test_reading_past_the_input_raises_eoferror() -> None:
    with pytest.raises(EOFError):
        _run("-ww ( ! )", "ab")


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("x", "'x' is not a Rubic command"),
        ("r3", "'r3' is not a Rubic command"),
        ("+wx", "not a Rubic colour pair"),
        ("+wgo", "not a Rubic colour pair"),
        ("( r", "never closed"),
        ("r )", "no matching"),
    ],
)
def test_malformed_programs_are_refused(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _run(code)


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    run = _run
    machine = _machine
    halting_program = "r"
    no_cycle_reason = "Rubic is total: a loop's count is fixed on entry."
