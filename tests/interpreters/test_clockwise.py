from typing import ClassVar

import pytest

from esolangs.interpreters.grid_based.clockwise import run
from tests.interpreters.contract import (
    EmptyProgramContract,
)
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestClockwise:
    def test_unclosed_ring_rejected(self) -> None:
        with raises_message(ValueError, "Clockwise ring is not closed"):
            run_and_capture(["+;S"])

    def test_leaving_the_grid_is_rejected_rather_than_turned(self) -> None:
        """The edge does not turn a pointer that would otherwise leave.

        The one-row program above cannot say which happens, because a turn
        at that edge leaves the grid as well.  Here a clockwise turn would
        land on row 1 and close the ring, and the pointer walks off anyway.
        """
        with raises_message(ValueError, "Clockwise ring is not closed"):
            run_and_capture(["  ?", "R  "])


class TestMove:
    """``move`` decides the turn, the step, and whether the ring goes on.

    Every other test drives it through a whole program, where a ring that
    stays closed hides which of its answers were right.  These call it at
    the positions a program cannot reach without already having failed.
    """

    def test_a_position_off_the_grid_is_a_malformed_ring(self) -> None:
        """Each side of both bounds is rejected before the cell is read.

        Reaching past the last row has to be refused rather than indexed:
        a non-strict bound there raises IndexError from inside instead of
        the ring's own error.
        """
        from esolangs.interpreters.grid_based.clockwise import move

        grid = ["  R", "R R"]
        for row, col in ((2, 0), (-1, 0), (0, 3), (0, -1)):
            with raises_message(ValueError, "Clockwise ring is not closed"):
                move(row, col, 0, grid, 0)


class TestContract(EmptyProgramContract):
    run = staticmethod(run_and_capture)
    empty_program: ClassVar[list[str]] = []
    empty_raises = "Clockwise program cannot be empty"
