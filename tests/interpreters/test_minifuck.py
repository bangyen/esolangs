"""Unit tests for the Minifuck interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.minifuck import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestMinifuck:
    def test_cat_program(self) -> None:
        """The canonical cat program echoes its input."""
        assert run_and_capture("<[<.[<.", inputs=["A"]) == "A"
        assert run_and_capture("<[<.[<.", inputs=["B"]) == "B"

    def test_comment_characters_ignored(self) -> None:
        """Non-command characters are ignored."""
        assert run_and_capture("abc", inputs=["A"]) == ""

    def test_tape_grows_past_the_initial_eight_cells(self) -> None:
        """The tape extends once the pointer nears its end, and . reads 8 cells.

        Every other test stays inside the first few cells, where the tape
        never has to grow: the eight it starts with are enough.  Seven ``[``
        walk the pointer to 8, which appends past the initial eight, and the
        ``.`` then prints cells 0-7 only -- 0b01111111 -- so the print window
        stays eight wide no matter how long the tape has become.
        """
        assert run_and_capture("[[[[[[[.") == "\x7f"


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine(".", ScriptedIO())
        assert (machine.ind, machine.ptr) == (0, 0)
        machine.step()  # . advances, flips the second cell, prints the byte
        assert machine.io.getvalue() == "@"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 1

    def test_tape_state_when_the_pointer_runs_deep(self) -> None:
        """The grown tape's exact contents, not just the byte it prints.

        ``test_tape_grows_past_the_initial_eight_cells`` asserts the printed
        byte, which only reads cells 0-7 -- so where the tape *ends* and what
        the appended cells hold went unchecked.  Seven ``[`` leave the
        pointer at 8 on a ten-cell tape: one cell past the pointer, and the
        rest flipped to 1 on the way.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine("[[[[[[[", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.ptr == 7
        assert machine.tape == [0, 1, 1, 1, 1, 1, 1, 1, 0]

    def test_skip_flips_the_next_cell_away_from_the_origin(self) -> None:
        """[ on a cell that flips to 0 skips ahead and flips the cell after it.

        The cat program exercises this branch only at the origin, where
        ``ptr + 1`` and ``ptr - 1`` are hard to tell apart and the skipped
        instruction is the last one anyway.  Walking out to cell 7 and back
        with ``<`` lands ``[`` on a cell already holding 1, so the flip goes
        1 -> 0, the skip fires deep in the tape, and the cell it touches is
        unambiguously the one *after* the pointer.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine("[[[[[[[<<<[", ScriptedIO())
        while not machine.halted:
            machine.step()
        # cell 5 flipped back to 0, and the skip flipped cell 6 with it
        assert machine.tape == [0, 1, 1, 1, 1, 0, 0, 1, 0]
        assert machine.ptr == 5

    def test_the_tape_starts_eight_cells_wide(self) -> None:
        """Eight is the width the print window reads, so it is asserted.

        Every other test looks at the tape after something has run, by
        which point growth has already changed its length -- so the tape
        could start one cell too long and only the untouched trailing zero
        would show it.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        assert _Machine("", ScriptedIO()).tape == [0] * 8

    def test_only_the_two_commands_reach_the_pointer(self) -> None:
        """A character that is neither ``<`` nor ``.`` nor ``[`` does nothing.

        ``test_comment_characters_ignored`` uses ``abc``, and every letter
        in it is outside the command set no matter how that set is spelled.
        A stray ``X`` is the same kind of comment, but it catches a command
        set widened to include it: as a command it would advance the
        pointer and flip a cell, so the byte the following ``.`` prints
        changes.
        """
        assert run_and_capture("X.") == "@"
        assert run_and_capture("X") == ""

    def test_the_skip_passes_exactly_one_instruction(self) -> None:
        """``[`` that flips a cell to 0 skips one instruction, not two.

        The skip is an ``ind`` bump on top of the one every step does, so
        skipping two lands a whole instruction further on.  It needs a
        program where the difference is reachable: the ``<`` after the skip
        moves the pointer only if it is executed, so where the pointer ends
        up says how far the skip went.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine("[<[<<", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.ptr == 0
        assert machine.tape == [0, 0, 1, 0, 0, 0, 0, 0]

    def test_a_read_keeps_the_tape_past_the_print_window(self) -> None:
        """Reading input replaces cells 0-7 and keeps everything after them.

        The eight bits of the byte are spliced in front of ``tape[8:]``, so
        the boundary is exactly the print window: taking the tail from 9
        instead would silently drop cell 8.  It only shows on a program
        that reads while the tape has already grown past the window, which
        needs the pointer to walk out and the first eight cells to be zero
        again by the time a ``.`` comes round.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        machine = _Machine(".<<[<<<.[<<.<<<..[<[.[.[..", ScriptedIO("ABCDEFGH"))
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "@`p0\x10"
        assert machine.tape == [0, 1, 0, 0, 0, 0, 0, 1, 0]


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    stepping_program = "."
    halting_program = "."
