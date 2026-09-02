"""Unit tests for the Collatz Multiverse interpreter.

Tests cover the Collatz rule (odd/even branches, 0 treated as odd), DO/NOT
printing, variables, arrays, the special variables (negativeOne, lineNumber,
input), and the documented error cases.
"""

import re

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.collatz_multiverse import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


# Sets up one=1, two=2, three=3 from the auto-initialized 0 and negativeOne=-1.
CONSTANTS = "\n".join(
    [
        "one = negativeOne x + negativeOne, NOT PRINT.",
        "one = negativeOne x + zero, NOT PRINT.",
        "two = negativeOne x + negativeOne, NOT PRINT.",
        "two = negativeOne x + one, NOT PRINT.",
        "three = negativeOne x + one, NOT PRINT.",
        "three = one x + two, NOT PRINT.",
    ]
)


class TestCollatzRule:
    def test_odd_rule_multiplies_and_adds(self) -> None:
        # n: 0 -> 3 (copy) -> 7 (3*2+1), then 7 is odd -> 7*3+1 = 22
        program = CONSTANTS + "\n".join(
            [
                "",
                "n = negativeOne x + three, NOT PRINT.",
                "n = two x + one, NOT PRINT.",
                "n = three x + one, DO PRINT.",
                "n = three x + one, DO PRINT.",
            ]
        )
        # 22 (odd branch), then 22 is even -> halved to 11
        assert run_program(program) == "\x16\x0b"

    def test_even_rule_halves(self) -> None:
        # x: 0 -> -1, then -1 is odd -> (-1)*(-1)+1 = 2
        # then 2 is even -> halved to 1
        program = CONSTANTS + "\n".join(
            [
                "",
                "x = negativeOne x + negativeOne, NOT PRINT.",
                "x = negativeOne x + one, NOT PRINT.",
                "x = one x + one, DO PRINT.",
            ]
        )
        assert run_program(program) == "\x01"

    def test_zero_is_treated_as_odd(self) -> None:
        # x starts 0, treated as odd: 0*(-1)+(-1) = -1
        assert run_program("x = negativeOne x + negativeOne, DO PRINT.") == "\xff"

    def test_copy_from_a_variable(self) -> None:
        # x starts 0, treated as odd: 0*(-1)+one = 1
        assert run_program(CONSTANTS + "\nx = negativeOne x + one, DO PRINT.") == "\x01"


class TestPrinting:
    def test_not_suppresses_output(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "x = negativeOne x + one, NOT PRINT.",
                "x = one x + zero, DO PRINT.",
            ]
        )
        # x = 1, then 1 is odd -> 1*1+0 = 1
        assert run_program(program) == "\x01"

    def test_print_wraps_to_byte(self) -> None:
        # x = 0*(-1)+(-1) = -1 -> low byte is 255
        assert run_program("x = negativeOne x + negativeOne, DO PRINT.") == "\xff"
        assert run_program("x = negativeOne x + negativeOne, NOT PRINT.") == ""


class TestVariables:
    def test_variables_auto_init_to_zero(self) -> None:
        # y and z start 0, x starts 0 (odd) -> 0*0+0 = 0
        assert run_program("x = y x + z, DO PRINT.") == "\x00"

    def test_negative_one_constant(self) -> None:
        assert run_program("x = negativeOne x + negativeOne, DO PRINT.") == "\xff"


class TestArrays:
    def test_bare_array_is_element_zero(self) -> None:
        # arr acts as arr[0]: 0 (odd) -> 0*(-1)+one = 1
        program = CONSTANTS + "\narr = negativeOne x + one, DO PRINT."
        assert run_program(program) == "\x01"

    def test_indexed_and_zero_elements_are_distinct(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "arr[negativeOne] = negativeOne x + one, DO PRINT.",
                "arr = negativeOne x + zero, DO PRINT.",
            ]
        )
        # arr[-1] = 1, arr[0] = 0
        assert run_program(program) == "\x01\x00"

    def test_index_uses_variable_value(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "i = negativeOne x + one, NOT PRINT.",
                "arr[i] = negativeOne x + one, DO PRINT.",
                "arr = negativeOne x + zero, DO PRINT.",
            ]
        )
        # arr[1] = 1, arr[0] = 0 (different cells)
        assert run_program(program) == "\x01\x00"

    def test_read_from_array(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "arr[negativeOne] = negativeOne x + one, NOT PRINT.",
                "x = negativeOne x + arr[negativeOne], DO PRINT.",
            ]
        )
        # x = 0*(-1)+1 = 1
        assert run_program(program) == "\x01"

    def test_input_cannot_be_assigned(self) -> None:
        """``input`` is read-only; assigning to it is a malformed program.

        Nothing else in the suite reaches this branch, so the message went
        unasserted.  It is compared whole, and by identity rather than
        ``match=``: a substring search still passes a message that has been
        widened around the original text.
        """
        message = "input cannot be redefined"
        program = "input = negativeOne x + negativeOne, NOT PRINT."
        with pytest.raises(ValueError, match=re.escape(message)) as caught:
            run(program, ScriptedIO("5"))
        assert str(caught.value) == message

    def test_unreachable_input_assignment_is_still_malformed(self) -> None:
        """The check is on the program text, not on the lines that run.

        Assigning to ``lineNumber`` jumps, so line 2 here never executes.
        While the check lived in ``step()`` this program ran to completion
        and printed, which made a *malformed* program legal whenever the
        offending line was skipped -- unlike the two sibling malformed
        cases, both rejected at construction.
        """
        program = "\n".join(
            [
                "lineNumber = x x + arr, DO PRINT.",
                "input = two x + three, DO PRINT.",
            ]
        )
        with pytest.raises(ValueError, match="input cannot be redefined"):
            run(program, ScriptedIO("5"))

    def test_acceptance_does_not_depend_on_input(self) -> None:
        """The same program text is malformed whatever is on stdin.

        A ``lineNumber`` jump target can be *read from input*, so while the
        check was made at execution time this program's validity varied
        with stdin: it ran on ``2`` and raised on ``3``.
        """
        program = "\n".join(
            [
                "lineNumber = input x + negativeOne, NOT PRINT.",
                "negativeOne = negativeOne x + negativeOne, NOT PRINT.",
                "input = negativeOne x + negativeOne, NOT PRINT.",
            ]
        )
        for stdin in ("2", "3", "9"):
            with pytest.raises(ValueError, match="input cannot be redefined"):
                run(program, ScriptedIO(stdin))

    def test_malformed_cases_agree_on_unreachable_lines(self) -> None:
        """All three documented malformed cases are rejected alike.

        The docstring lists a malformed line, a numeric literal, and an
        ``input`` target as equally malformed; each is checked over the
        whole program, so an unreachable offending line is rejected
        whichever kind it is.
        """
        jump = "lineNumber = x x + arr, DO PRINT."
        # Each malformed kind has its own message; pairing them keeps the
        # assertion specific rather than accepting any ValueError.
        for bad, message in (
            ("this is not a valid line at all", "malformed line"),
            ("foo = 3 x + one, NOT PRINT.", "malformed line"),
            ("input = two x + three, DO PRINT.", "input cannot be redefined"),
        ):
            with pytest.raises(ValueError, match=message):
                run(f"{jump}\n{bad}", ScriptedIO("5"))


class TestLineNumber:
    def test_reads_current_line(self) -> None:
        program = "\n".join(
            [
                "a = negativeOne x + lineNumber, DO PRINT.",
                "b = negativeOne x + lineNumber, DO PRINT.",
            ]
        )
        # line 1 -> a = 1, line 2 -> b = 2
        assert run_program(program) == "\x01\x02"

    def test_assignment_jumps(self) -> None:
        program = CONSTANTS + "\n".join(
            [
                "",
                "lineNumber = one x + two, NOT PRINT.",
                "x = negativeOne x + zero, DO PRINT.",
                "x = negativeOne x + one, DO PRINT.",
            ]
        )
        # line 7 (odd) -> 7*1+2 = 9, jumping over line 8
        assert run_program(program) == "\x01"

    def test_jump_off_program_halts(self) -> None:
        program = "\n".join(
            [
                "lineNumber = negativeOne x + negativeOne, NOT PRINT.",
                "x = negativeOne x + one, DO PRINT.",
            ]
        )
        # line 1 (odd) -> 1*(-1)+(-1) = -2, out of range, halts
        assert run_program(program) == ""


class TestInput:
    def test_input_reads_an_integer(self) -> None:
        # x = 0*(-1)+input = 65 -> 'A'
        assert run_program("x = negativeOne x + input, DO PRINT.", "65") == "A"

    def test_input_running_out_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run_program("x = negativeOne x + input, NOT PRINT.", "")

    def test_input_cannot_be_redefined(self) -> None:
        with pytest.raises(ValueError, match="redefined"):
            run_program("input = negativeOne x + zero, NOT PRINT.")

    def test_an_array_index_can_be_read_from_input(self) -> None:
        """``arr[input]`` takes the subscript from stdin, not just the value.

        Which cell is read has to depend on what was typed: storing 3 at
        index 2 and then reading ``arr[input]`` gives 3 for an input of 2
        and the empty default for an input of 0.  A shell that pre-read
        only the *bare* ``input`` operands would leave the index unread.
        """
        program = "\n".join(
            [
                CONSTANTS,
                "arr[two] = negativeOne x + three, NOT PRINT.",
                "y = negativeOne x + arr[input], DO PRINT.",
            ]
        )
        assert run_program(program, "2") == chr(3)
        assert run_program(program, "0") == chr(0)

    def test_an_index_is_read_before_the_operand_it_subscripts(self) -> None:
        """One line can name ``input`` twice, and the order is fixed.

        The operands are read left to right, so the bare ``input`` in the
        ``var2`` slot consumes the first line and the index in ``var3``
        consumes the second: ``0 * 5 + arr[2]`` is 3, where swapping the
        two reads would index with 5 and find an empty cell.
        """
        program = "\n".join(
            [
                CONSTANTS,
                "arr[two] = negativeOne x + three, NOT PRINT.",
                "y = input x + arr[input], DO PRINT.",
            ]
        )
        assert run_program(program, "5\n2") == chr(3)


class TestMalformed:
    def test_numeric_literals_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_program("x = 3 x + 1, DO PRINT.")
        with pytest.raises(ValueError, match="malformed"):
            run_program("x = y x + 3, DO PRINT.")

    def test_missing_boolean(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_program("x = y x + z.")

    def test_bad_boolean(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_program("x = y x + z, MAYBE PRINT.")

    def test_garbage_line(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            run_program("hello world")

    def test_blank_lines_are_skipped(self) -> None:
        program = CONSTANTS + "\n\nx = negativeOne x + one, DO PRINT.\n"
        assert run_program(program) == "\x01"


class TestStepMachine:
    def test_step_tracks_registers_and_pointer(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.collatz_multiverse import _Machine

        machine = _Machine("x = negativeOne x + negativeOne, DO PRINT.", ScriptedIO())
        assert (machine.ip, machine.registers) == (1, {"negativeOne": -1})
        machine.step()  # x = 0*(-1)+(-1) = -1, printed as a byte
        assert machine.io.getvalue() == "\xff"
        assert machine.registers == {"negativeOne": -1, "x": -1}
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ip == 2

    def test_snapshot_carries_the_array_cells(self) -> None:
        """A populated array reaches the snapshot, and distinguishes states.

        The program above holds no arrays, so the arrays half of the tuple
        was always empty and its contents went unread -- hashable either
        way.  Running a machine that writes two cells pins it: the snapshot
        has to change as the cells do, so a snapshot that dropped or
        constant-folded them would collide with the state before the write.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.collatz_multiverse import _Machine

        program = CONSTANTS + "\n".join(
            [
                "",
                "arr[negativeOne] = negativeOne x + one, NOT PRINT.",
                "arr[one] = negativeOne x + one, NOT PRINT.",
            ]
        )
        machine = _Machine(program, ScriptedIO())
        seen = [machine.snapshot()]
        while not machine.halted:
            machine.step()
            seen.append(machine.snapshot())

        assert machine.arrays == {"arr": {-1: 1, 1: 1}}
        assert hash(seen[-1]) is not None
        assert seen[-1] != seen[0]
        assert len(set(seen)) == len(seen)


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.collatz_multiverse import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    stepping_program = "x = y x + z, DO PRINT."
    halting_program = "x = y x + z, DO PRINT."
    # A line that jumps to itself, so the state repeats rather than advancing.
    looping_program = (
        "z = z x + z, NOT PRINT.\nlineNumber = lineNumber x + z, NOT PRINT."
    )
