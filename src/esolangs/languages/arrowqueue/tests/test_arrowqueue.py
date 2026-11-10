"""Unit tests for the ArrowQueue interpreter."""

from functools import partial
from typing import ClassVar

import pytest

from esolangs.languages.arrowqueue import interpreter as native
from esolangs.languages.arrowqueue.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.contract import CycleContract, EmptyProgramContract
from tests.interpreters.runner import run_printing
from tests.support.evaluation import _row_answerer
from tests.support.prepared_support import check_image_reuse

run_and_capture = partial(run_printing, run)


class TestArrowQueue:
    def test_noop_ignored_until_off_grid(self) -> None:
        from esolangs.languages.arrowqueue.tests.oracle_checks import (
            check_raw_arrowqueue,
        )

        check_raw_arrowqueue()
        assert run_and_capture(["   "]) == ""

        import esolangs

        declared = esolangs.Language("ArrowQueue").from_source("file.qq")
        for isolated in (False, True):
            answer = _row_answerer(
                "ArrowQueue",
                terminating=True,
                isolated=isolated,
                settings=None,
                scale=None,
                max_output=None,
                max_memory=None,
            )
            assert answer(declared, "", 3) == "0"

    def test_the_dump_goes_to_the_caller_s_io(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``run`` must write through the ``io`` it is handed."""
        io = ScriptedIO("")
        run(["~~"], io)
        assert io.getvalue() == "0 0"
        check_image_reuse(
            "ArrowQueue",
            "~~\n ",
            native,
            "_prepare_grid",
            monkeypatch,
            cases=(("", "0 0"),) * 3,
        )

    def test_workspace_finalizes_without_counting_another_command(self) -> None:
        from tests.proofs.execution import measure

        assert measure("ArrowQueue", "00", written=True) == (1, 2)

    def test_the_dump_fires_once_however_often_a_halted_machine_is_stepped(
        self,
    ) -> None:
        """``dumped`` is load-bearing: the queue prints on one step only."""
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
    """Assertions on where the IP ends up, which output cannot show."""

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
        """The move that goes out of bounds is the last step, not the one after."""
        assert self.steps(["..."]) == 3
        assert self.steps(["*"]) == 1

    def test_a_pointer_placed_off_the_grid_halts_without_reading(self) -> None:
        """The bounds check before the cell read is what makes this safe."""
        machine = _Machine(["...", "..."])
        machine.place(2, 0)
        machine.step()
        assert machine.halted
        assert (machine.row, machine.col) == (2, 0)

    def test_short_lines_pad_on_the_right(self) -> None:
        """A short line is padded to the right, keeping its content in place."""
        assert self.final(["*", "~+"]) == (2, 0, 1, [1])

    def test_empty_program_has_no_grid(self) -> None:
        """Code with no lines halts at once on a zero-width, empty grid."""
        machine = _Machine([])
        assert machine.halted
        assert (machine.width, machine.grid) == (0, ())


def _machine(code: object) -> object:
    return _Machine(code)


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    empty_program: ClassVar[list[str]] = []
    # The same ring either way; the ~ in the middle row is what sustains it.
    halting_program: ClassVar[list[str]] = [" ~*", "+ *", "*~+"]
    looping_program: ClassVar[list[str]] = [" ~*", "+~*", "*~+"]
