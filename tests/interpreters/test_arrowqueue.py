"""Unit tests for the ArrowQueue interpreter.

ArrowQueue has no output commands.  Its interpreter dumps the queue when
the program halts -- the repo convention for interpreter-only languages --
so a run that halts on an empty pop prints nothing, that being the halt
condition, and only one that walks off the grid with headings still queued
has anything to show.  The tests therefore assert termination (halting on
an off-grid move or an empty-queue pop) alongside that dump.  Because
halting is what the boolean generator reads, a program can act as a truth
machine: the presence of a command in a chosen cell decides whether the IP
loops forever or runs out of queue and halts.
The truth-machine branch is decided deterministically by state-cycle
detection — the sustaining ring is a finite cycle — so the tests need no
wall-clock bound.
"""

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
        # ``~`` queues heading 0 and ``*`` turns the IP down, which walks it
        # off this one-row grid before ``+`` is ever reached -- so the queue
        # still holds that 0 at the halt, and the dump prints it.
        assert esolangs.run("ArrowQueue", "~*+") == "0"

    def test_the_dump_separates_headings_with_a_space(self) -> None:
        """Two queued headings, so the separator itself is asserted.

        ``~*+`` leaves one heading, which prints the same however the join
        is spelled: a mutation replacing the separator survived the whole
        suite because no program here queued two.
        """
        assert esolangs.run("ArrowQueue", "~~") == "0 0"

    def test_the_dump_goes_to_the_caller_s_io(self) -> None:
        """``run`` must write through the ``io`` it is handed.

        ``_Machine`` defaults ``io`` to a fresh :class:`IO` for callers that
        only step the grid, so a ``run`` that dropped its own argument would
        still print -- to real stdout, past whatever the caller passed.
        ``esolangs.run`` captures through a :class:`ScriptedIO`, so that
        would return the empty string while the text leaked to the console.
        """
        io = ScriptedIO("")
        run(["~~"], io)
        assert io.getvalue() == "0 0"

    def test_the_dump_fires_once_however_often_a_halted_machine_is_stepped(
        self,
    ) -> None:
        """``dumped`` is load-bearing: the queue prints on one step only.

        Every mutation of that flag -- forcing it true or false at either
        end -- survived until this test, since nothing stepped a machine
        past the step that dumps.
        """
        io = ScriptedIO("")
        machine = _Machine(["~~"], io)
        while not machine.halted:
            machine.step()
        assert io.getvalue() == ""  # the dump is the next step's
        machine.step()
        assert io.getvalue() == "0 0"
        machine.step()
        machine.step()
        assert io.getvalue() == "0 0"  # and not once more


class TestMachineState:
    """Assertions on where the IP ends up, which output cannot show.

    The end-of-run dump reports the queue, so the position and heading
    never reach the output at all, and a run halting on an empty pop
    reports nothing whatever it did on the way -- turning the wrong way or
    padding the grid on the wrong side can still look alike.  These pin the
    state the dump does not carry.
    """

    def final(self, code: list[str]) -> tuple[int, int, int, list[int]]:
        machine = _Machine(code)
        while not machine.halted:
            machine.step()
        return machine.row, machine.col, machine.d, list(machine.queue)

    def steps(self, code: list[str]) -> int:
        """Return how many steps the program takes before it halts."""
        machine = _Machine(code)
        count = 0
        while not machine.halted:
            count += 1
            machine.step()
        return count

    def test_leaving_the_grid_halts_on_the_step_that_leaves(self) -> None:
        """The move that goes out of bounds is the last step, not the one after.

        The bounds are checked twice -- once before reading a cell, once
        after moving -- and the second check is what makes the departing
        move final.  Without it the machine takes one more step, whose only
        job is to notice it is already outside; the IP ends up in the same
        place either way, so the *count* is the only thing that separates
        them.  Both axes are covered because the row and column halves of
        the condition are separate comparisons: three cells to the right
        edge, and one down through a single-column grid.
        """
        assert self.steps(["..."]) == 3
        assert self.steps(["*"]) == 1

    def test_a_pointer_placed_off_the_grid_halts_without_reading(self) -> None:
        """The bounds check before the cell read is what makes this safe.

        Nothing a program does reaches it -- the check after each move
        halts the machine first, so the IP never *begins* a step outside --
        but the VM and the hang detector drive ``step()`` directly, and a
        machine positioned past the last row must halt rather than index a
        row that is not there.  ``row == len(grid)`` is the case that
        separates a strict bound from a non-strict one.
        """
        machine = _Machine(["...", "..."])
        machine.place(2, 0)
        machine.step()
        assert machine.halted
        assert (machine.row, machine.col) == (2, 0)

    def test_a_fresh_machine_reports_a_boolean(self) -> None:
        """``halted`` starts as False itself, not merely as something falsey.

        Every other check of it is a truthiness test, which ``None`` passes
        just as well -- so the flag could start un-set rather than unset and
        no test would notice, while ``halted`` is annotated as returning a
        bool.  The identity comparison is the part that pins it.
        """
        assert _Machine(["..."]).halted is False

    def test_short_lines_pad_on_the_right(self) -> None:
        """A short line is padded to the right, keeping its content in place.

        ``ljust`` and ``rjust`` agree whenever the short line is the last one
        or holds only no-ops, which is every ragged grid the suite had.  Here
        the ``*`` on the short first row must stay at column 0: padding on
        the left would shift it under the ``+`` and change where the IP goes.
        """
        assert self.final(["*", "~+"]) == (2, 0, 1, [1])

    def test_heading_wraps_after_four_turns(self) -> None:
        """Four turns come back to the start; the heading is one of four.

        Every other program leaves the grid before the fourth ``*``, so a
        heading counted modulo 5 was never reached -- and a fifth heading has
        no delta, so this grid raises IndexError under that mutation instead
        of walking off the edge.
        """
        assert self.final(["~**", "*~*", "***"]) == (-1, 0, 3, [0, 1, 0, 3, 2, 3])

    def test_empty_program_has_no_grid(self) -> None:
        """Code with no lines halts at once on a zero-width, empty grid."""
        machine = _Machine([])
        assert machine.halted
        assert (machine.width, machine.grid) == (0, ())


class TestStepMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        machine = _Machine(["..."])
        while not machine.halted:
            machine.step()
        state = machine.snapshot()
        machine.step()  # stepping a halted machine must not raise
        assert machine.halted
        assert machine.snapshot() == state


def _machine(code: object) -> object:
    from esolangs.interpreters.grid_based.arrowqueue import _Machine

    return _Machine(code)


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    empty_program: ClassVar[list[str]] = []
    # The same ring either way; the ~ in the middle row is what sustains it.
    halting_program: ClassVar[list[str]] = [" ~*", "+ *", "*~+"]
    looping_program: ClassVar[list[str]] = [" ~*", "+~*", "*~+"]
