r"""Unit tests for the ArrowQueue interpreter."""

import io
from contextlib import redirect_stdout
from typing import ClassVar

import esolangs
from esolangs.interpreters.grid_based.arrowqueue import _Machine, run
from esolangs.interpreters.io import IO, ScriptedIO
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
)


def run_and_capture(code: list[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestArrowQueue:
    def test_empty_line_halts_immediately(self) -> None:
        assert run_and_capture([""]) == ""

    def test_noop_ignored_until_off_grid(self) -> None:
        assert run_and_capture(["   "]) == ""

    def test_registered_interpreter_runs(self) -> None:
        # ``~`` queues heading 0 and.
        # off this one-row grid before.
        # still holds that 0 at the.
        assert esolangs.run("ArrowQueue", "~*+") == "0"

    def test_the_dump_separates_headings_with_a_space(self) -> None:
        r"""Two queued headings, so the separator itself is asserted."""
        assert esolangs.run("ArrowQueue", "~~") == "0 0"

    def test_the_dump_goes_to_the_caller_s_io(self) -> None:
        r"""``run`` must write through the ``io`` it is handed."""
        io = ScriptedIO("")
        run(["~~"], io)
        assert io.getvalue() == "0 0"

    def test_the_dump_fires_once_however_often_a_halted_machine_is_stepped(
        self,
    ) -> None:
        r"""``dumped`` is load-bearing: the queue prints on one step only."""
        io = ScriptedIO("")
        machine = _Machine(["~~"], io)
        while not machine.halted:
            machine.step()
        assert io.getvalue() == ""  # the dump is the next step's.
        machine.step()
        assert io.getvalue() == "0 0"
        machine.step()
        machine.step()
        assert io.getvalue() == "0 0"  # and not once more.


class TestMachineState:
    r"""Assertions on where the IP ends up, which output cannot show."""

    def final(self, code: list[str]) -> tuple[int, int, int, list[int]]:
        machine = _Machine(code)
        while not machine.halted:
            machine.step()
        return machine.row, machine.col, machine.d, list(machine.queue)

    def steps(self, code: list[str]) -> int:
        r"""Return how many steps the program takes before it halts."""
        machine = _Machine(code)
        count = 0
        while not machine.halted:
            count += 1
            machine.step()
        return count

    def test_leaving_the_grid_halts_on_the_step_that_leaves(self) -> None:
        r"""The move that goes out of bounds is the last step, not the one."""
        assert self.steps(["..."]) == 3
        assert self.steps(["*"]) == 1

    def test_a_pointer_placed_off_the_grid_halts_without_reading(self) -> None:
        r"""The bounds check before the cell read is what makes this safe."""
        machine = _Machine(["...", "..."])
        machine.place(2, 0)
        machine.step()
        assert machine.halted
        assert (machine.row, machine.col) == (2, 0)

    def test_a_fresh_machine_reports_a_boolean(self) -> None:
        r"""``halted`` starts as False itself, not merely as something falsey."""
        assert _Machine(["..."]).halted is False

    def test_short_lines_pad_on_the_right(self) -> None:
        r"""A short line is padded to the right, keeping its content in place."""
        assert self.final(["*", "~+"]) == (2, 0, 1, [1])

    def test_heading_wraps_after_four_turns(self) -> None:
        r"""Four turns come back to the start; the heading is one of four."""
        assert self.final(["~**", "*~*", "***"]) == (-1, 0, 3, [0, 1, 0, 3, 2, 3])

    def test_empty_program_has_no_grid(self) -> None:
        r"""Code with no lines halts at once on a zero-width, empty grid."""
        machine = _Machine([])
        assert machine.halted
        assert (machine.width, machine.grid) == (0, ())


def _machine(code: object) -> object:
    from esolangs.interpreters.grid_based.arrowqueue import _Machine

    return _Machine(code)


class TestContract(EmptyProgramContract, CycleContract):
    r"""The shared shapes, with this language's own programs."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    empty_program: ClassVar[list[str]] = []
    # The same ring either way; the.
    halting_program: ClassVar[list[str]] = [" ~*", "+ *", "*~+"]
    looping_program: ClassVar[list[str]] = [" ~*", "+~*", "*~+"]
