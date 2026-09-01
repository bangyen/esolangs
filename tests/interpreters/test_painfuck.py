"""Unit tests for the Painfuck interpreter."""

import importlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)

run = importlib.import_module("esolangs.interpreters.tape_based.painfuck").run

# The source text is translated through a position-dependent shift per cycle
# before execution.  _encode builds a source program whose translation is
# exactly ``targets`` (the inverse of the module's _translate), so the tests
# can express commands directly.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def _encode(targets: str) -> str:
    out: list[str] = []
    k = 0
    for tc in targets:
        for cycle in _CYCLES:
            if tc in cycle:
                out.append(cycle[(cycle.index(tc) - k) % len(cycle)])
                k += 1
                break
    return "".join(out)


def run_program(targets: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(_encode(targets), io)
    return io.getvalue()


class TestPainfuck:
    def test_increment_and_print(self) -> None:
        assert run_program("pue") == "\x02"
        assert run_program("ppue") == "\x04"

    def test_decrement(self) -> None:
        assert run_program("sue") == "\xff"  # -1 as a byte

    def test_zero(self) -> None:
        assert run_program("pzue") == "\x00"

    def test_square(self) -> None:
        assert run_program("pkue") == "\x04"  # 2*2
        assert run_program("ppkue") == "\x10"  # 4*4

    def test_half(self) -> None:
        assert run_program("pphue") == "\x02"  # 4 // 2 = 2

    def test_copy_neighbor(self) -> None:
        assert run_program("ppwue") == "\x00"  # copy 0 from the right neighbor
        assert run_program("ppwque") == "\x00"  # copy back

    def test_pointer_reset(self) -> None:
        # p at cell 0, r moves right, pp, then d resets and p adds again
        assert run_program("prppdpue") == "\x04"

    def test_read_byte(self) -> None:
        assert run_program("jue", "A\n") == "A"

    def test_read_number(self) -> None:
        assert run_program("jiue", "6\n65\n") == "A"

    def test_read_number_rejects_garbage(self) -> None:
        with pytest.raises(HaltError):
            run_program("ip", "12x\n")

    def test_loop(self) -> None:
        # pp a (cell 2 nonzero, open), s b (0 -> close), u prints 0
        assert run_program("ppas b ue".replace(" ", "")) == "\x00"

    def test_repeat_next(self) -> None:
        # c repeats the next command 7 times; s subtracts 1 each -> -5
        assert run_program("pcsu") == "\xfb"
        # c repeating u prints 7 times
        assert run_program("pcue") == "\x02\x02\x02\x02\x02\x02\x02"

    def test_repeat_previous(self) -> None:
        # t repeats the previous command 3 times
        assert run_program("ptpue") == "\n"

    def test_repeat_previous_with_nothing_before_it(self) -> None:
        """A leading ``t`` has no earlier command, so it repeats nothing.

        The backward scan walks off the start of the program rather than
        finding a command, and execution carries on: the ``u`` still prints
        the untouched cell.  A ``t`` preceded only by more ``t``s is the
        same case, since the scan skips those looking for a real command.
        """
        assert run_program("tue") == "\x00"
        assert run_program("t") == ""

    def test_halt(self) -> None:
        assert run_program("pe") == ""
        assert run_program("p") == ""

    def test_print_number(self) -> None:
        assert run_program("ppoe") == "4"

    def test_copy_from_left_neighbor(self) -> None:
        # q copies the left neighbor into the current cell when ptr > 0
        assert run_program("pprpplque") == "\x04"

    def test_conditional_skip(self) -> None:
        # v skips the next command when the cell is nonzero
        assert run_program("pvpu") == "\x02"

    def test_random_skip(self) -> None:
        from unittest.mock import patch

        # y skips the next command on a coin flip; pin both outcomes
        with patch("secrets.randbelow", return_value=1):
            assert run_program("pyu") == ""
        with patch("secrets.randbelow", return_value=0):
            assert run_program("pyu") == "\x02"

    def test_error(self) -> None:
        with pytest.raises(HaltError):
            run_program("b")  # loop close with an empty stack


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.painfuck import _Machine

        machine = _Machine("pp", ScriptedIO())
        assert (machine.ind, list(machine.tape)) == (0, [0])
        machine.step()  # p adds 2
        assert list(machine.tape) == [2]
        machine.step()  # e halts
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2

    def test_skipping_a_loop_steps_over_a_nested_one(self) -> None:
        """A zero cell skips to the loop's own 'b', not to a nested one."""
        # cell 0 is zero, so the outer 'a' skips forward; the inner 'a...b'
        # pair must be consumed as a unit, leaving 'u' to print cell 0.
        assert run_program("aabbue") == "\x00"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.painfuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    stepping_program = "pp"
    halting_program = "pp"
