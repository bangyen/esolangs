"""Unit tests for the Collatz Multiverse interpreter."""

import re
from functools import partial

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.collatz_multiverse import _Machine, run
from tests.interpreters import runner
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)

run_program = partial(runner.run_program, run, suppress_eof=False)


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


def _lines(*lines: str) -> str:
    """``CONSTANTS`` followed by ``lines``."""
    return "\n".join([CONSTANTS, *lines])


_ARR_TWO_IS_THREE = "arr[two] = negativeOne x + three, NOT PRINT."


@pytest.mark.parametrize(
    ("program", "stdin", "expected"),
    [
        pytest.param(
            # n: 0 -> 3 (copy) -> 7 (3*2+1), then 7 is odd -> 22, then
            # 22 is even -> halved to 11
            _lines(
                "n = negativeOne x + three, NOT PRINT.",
                "n = two x + one, NOT PRINT.",
                "n = three x + one, DO PRINT.",
                "n = three x + one, DO PRINT.",
            ),
            "",
            "\x16\x0b",
            id="odd_rule_multiplies_and_adds",
        ),
        pytest.param(
            # x: 0 -> -1, -1 is odd -> (-1)*(-1)+1 = 2, 2 is even -> 1
            _lines(
                "x = negativeOne x + negativeOne, NOT PRINT.",
                "x = negativeOne x + one, NOT PRINT.",
                "x = one x + one, DO PRINT.",
            ),
            "",
            "\x01",
            id="even_rule_halves",
        ),
        pytest.param(
            # x = 1, then 1 is odd -> 1*1+0 = 1
            _lines(
                "x = negativeOne x + one, NOT PRINT.", "x = one x + zero, DO PRINT."
            ),
            "",
            "\x01",
            id="not_suppresses_output",
        ),
        # x starts 0, treated as odd: 0*(-1)+(-1) = -1 -> low byte is 255
        pytest.param(
            "x = negativeOne x + negativeOne, DO PRINT.", "", "\xff", id="wraps"
        ),
        pytest.param(
            "x = negativeOne x + negativeOne, NOT PRINT.", "", "", id="silent"
        ),
        pytest.param(
            # arr[-1] = 1, arr[0] = 0
            _lines(
                "arr[negativeOne] = negativeOne x + one, DO PRINT.",
                "arr = negativeOne x + zero, DO PRINT.",
            ),
            "",
            "\x01\x00",
            id="indexed_and_zero_elements_are_distinct",
        ),
        pytest.param(
            # Wiki: "arr can also be used as a variable, but it acts like arr[0]".
            _lines(
                "arr = negativeOne x + one, NOT PRINT.",
                "x = negativeOne x + arr[zero], DO PRINT.",
                "brr[zero] = negativeOne x + two, NOT PRINT.",
                "y = negativeOne x + brr, DO PRINT.",
            ),
            "",
            "\x01\x02",
            id="bare_name_is_cell_zero",
        ),
        pytest.param(
            # line 1 -> a = 1, line 2 -> b = 2
            "a = negativeOne x + lineNumber, DO PRINT.\n"
            "b = negativeOne x + lineNumber, DO PRINT.",
            "",
            "\x01\x02",
            id="reads_current_line",
        ),
        pytest.param(
            # Wiki: "moves it to that line number, but doesn't execute it".
            # line 7 (odd) -> 7*1+1 = 8; line 8 is skipped, line 9 runs
            _lines(
                "lineNumber = one x + one, NOT PRINT.",
                "x = negativeOne x + zero, DO PRINT.",
                "x = negativeOne x + one, DO PRINT.",
            ),
            "",
            "\x01",
            id="assignment_skips_the_target_line",
        ),
        pytest.param(
            # line 1 (odd) -> 1*1+1 = 2, the last line; advancing leaves
            "lineNumber = lineNumber x + lineNumber, NOT PRINT.\n"
            "x = negativeOne x + negativeOne, DO PRINT.",
            "",
            "",
            id="moving_to_the_last_line_halts",
        ),
        # ``arr[input]`` takes the subscript from stdin, not just the value.
        *[
            pytest.param(
                _lines(_ARR_TWO_IS_THREE, "y = negativeOne x + arr[input], DO PRINT."),
                stdin,
                expected,
                id=f"index_read_from_input_{stdin}",
            )
            for stdin, expected in (("2", chr(3)), ("0", chr(0)))
        ],
        pytest.param(
            _lines(
                "arr[input] = negativeOne x + three, NOT PRINT.",
                "y = negativeOne x + arr[two], DO PRINT.",
            ),
            "2",
            chr(3),
            id="index_written_from_input",
        ),
        pytest.param(
            # One line can name ``input`` twice: the index is read first.
            _lines(_ARR_TWO_IS_THREE, "y = input x + arr[input], DO PRINT."),
            "5\n2",
            chr(3),
            id="index_read_before_the_operand",
        ),
        pytest.param(
            CONSTANTS + "\n\nx = negativeOne x + one, DO PRINT.\n",
            "",
            "\x01",
            id="blank_lines_are_skipped",
        ),
    ],
)
def test_output(program: str, stdin: str, expected: str) -> None:
    assert run_program(program, stdin) == expected


def test_sparse_register_and_array_lookups_return_zero() -> None:
    """Absent names and cells are semantic zeroes, not stored entries."""
    from esolangs.interpreters.register_based.collatz_multiverse import (
        _arr_get,
        _arr_set,
        _reg_get,
    )

    arrays = _arr_set((("before", ((0, 1),)), ("a", ((1, 9),))), "a", 3, 7)
    assert _reg_get((("x", 4),), "missing") == 0
    assert _arr_get(arrays, "a", 2) == 0
    assert _arr_get(arrays, "missing", 0) == 0
    assert _arr_get(arrays, "before", 0) == 1


def test_input_cannot_be_assigned() -> None:
    """``input`` is read-only; assigning to it is a malformed program."""
    message = "input cannot be redefined"
    program = "input = negativeOne x + negativeOne, NOT PRINT."
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        run(program, ScriptedIO("5"))
    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ("this is not a valid line at all", "malformed line"),
        ("foo = 3 x + one, NOT PRINT.", "malformed line"),
        ("input = two x + three, DO PRINT.", "input cannot be redefined"),
    ],
)
def test_malformed_cases_agree_on_unreachable_lines(bad: str, message: str) -> None:
    """All three documented malformed cases are rejected, even past a jump."""
    with pytest.raises(ValueError, match=message):
        run(f"lineNumber = x x + arr, DO PRINT.\n{bad}", ScriptedIO("5"))


@pytest.mark.parametrize(
    "program",
    [
        "x = 3 x + 1, DO PRINT.",
        "x = y x + 3, DO PRINT.",
        "x = y x + z.",
        "x = y x + z, MAYBE PRINT.",
        "hello world",
    ],
)
def test_malformed(program: str) -> None:
    with pytest.raises(ValueError, match="malformed"):
        run_program(program)


def test_input_running_out_raises_eof() -> None:
    with pytest.raises(EOFError):
        run_program("x = negativeOne x + input, NOT PRINT.", "")


class TestStepMachine:
    def test_step_tracks_registers_and_pointer(self) -> None:
        machine = _Machine("x = negativeOne x + negativeOne, DO PRINT.", ScriptedIO())
        assert (machine.ip, machine.registers) == (1, {"negativeOne": -1})
        machine.step()  # x = 0*(-1)+(-1) = -1, printed as a byte
        assert machine.io.getvalue() == "\xff"
        assert machine.registers == {"negativeOne": -1, "x": -1}
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ip == 2

    def test_snapshot_carries_the_array_cells(self) -> None:
        """A populated array reaches the snapshot, and distinguishes states."""
        program = _lines(
            "arr[negativeOne] = negativeOne x + one, NOT PRINT.",
            "arr[one] = negativeOne x + one, NOT PRINT.",
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
