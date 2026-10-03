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
from esolangs.interpreters.io import IO
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
    def test_registered_interpreter_runs(self) -> None:
        # ``~`` queues heading 0 and ``*`` turns the IP down, which walks it
        # off this one-row grid before ``+`` is ever reached -- so the queue
        # still holds that 0 at the halt, and the dump prints it.
        assert esolangs.run("ArrowQueue", "~*+") == "0"


class TestMachineState:
    """Assertions on where the IP ends up, which output cannot show.

    The end-of-run dump reports the queue, so the position and heading
    never reach the output at all, and a run halting on an empty pop
    reports nothing whatever it did on the way -- turning the wrong way or
    padding the grid on the wrong side can still look alike.  These pin the
    state the dump does not carry.
    """

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

    def test_empty_program_has_no_grid(self) -> None:
        """Code with no lines halts at once on a zero-width, empty grid."""
        machine = _Machine([])
        assert machine.halted
        assert (machine.width, machine.grid) == (0, ())


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
