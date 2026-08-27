"""Unit tests for the Minifuck interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.minifuck import run


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

    def test_empty_program(self) -> None:
        assert run_and_capture("") == ""

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

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine

        assert hash(_Machine(".", ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.minifuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # the tape never rewinds, so every Minifuck program halts
        assert run_until_halt_or_cycle(_Machine(".", ScriptedIO())) is True
