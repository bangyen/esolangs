"""Unit tests for the Back interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.back import run


def run_and_capture(code: list[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestBack:
    def test_halt_prints_tape(self) -> None:
        assert run_and_capture(["*"]) == "0"

    def test_flip_bit(self) -> None:
        assert run_and_capture(["-*"]) == "1"

    def test_move_right(self) -> None:
        assert run_and_capture([">-*"]) == "0 1"

    def test_flip_twice(self) -> None:
        assert run_and_capture([">--*"]) == "0 0"

    def test_skip_instruction_on_zero(self) -> None:
        """+ skips the next cell when the current bit is 0."""
        assert run_and_capture([">+-*"]) == "0 0"

    def test_reflect_backslash(self) -> None:
        """\\ reflects the direction."""
        assert run_and_capture(["\\-*"]) == "1"

    def test_reflect_slash(self) -> None:
        """/ reflects the direction."""
        assert run_and_capture(["/-*"]) == "1"

    def test_move_left(self) -> None:
        """< moves the tape head left when it is not at zero."""
        assert run_and_capture([">>-<*"]) == "0 0 1"

    def test_move_left_lands_on_the_previous_cell(self) -> None:
        """< steps back exactly one cell, and the cell it lands on is used.

        ``test_move_left`` halts straight after the ``<``, so the pointer's
        landing place is never read: moving back one, back two, or jumping
        to cell 1 all print the same tape.  Flipping the bit after the move
        shows which cell the head actually reached.
        """
        assert run_and_capture([">-<-*"]) == "1 1"

    def test_beam_travels_down_a_column(self) -> None:
        """The beam moves by rows too, not only along one line.

        Every other program here is a single row, where the row index stays
        0 whatever is added to it -- so the row half of the beam's step was
        unconstrained.  Here ``\\`` turns the beam downward and it crosses
        two more rows before halting.
        """
        assert run_and_capture(["\\", "-", "*"]) == "1"

    def test_slash_reflects_the_beam(self) -> None:
        """/ turns the beam, rather than letting it carry straight on.

        ``test_reflect_slash`` runs on one row, where a beam that keeps
        going reaches the same cells in the same order as one that turns --
        so the reflection could have done nothing.  On two rows the turn
        decides which row the beam prints from.
        """
        assert run_and_capture(["/*", "--"]) == "1"

    def test_skip_moves_the_beam_by_a_whole_row(self) -> None:
        """+ steps the beam along its heading, rows included.

        ``test_skip_instruction_on_zero`` is a single row, so the row half
        of the skip was free to be anything.  Here the beam is heading
        downward when it meets the ``+``, and skipping upward instead never
        reaches the ``*``.
        """
        assert run_and_capture(["\\", "+", "-", "*"]) == "0"

    def test_blank_only_program_is_empty(self) -> None:
        """Programs of only blank lines are rejected, not crashed on."""
        import pytest

        with pytest.raises(ValueError, match="empty"):
            run_and_capture(["\n"])
        with pytest.raises(ValueError, match="empty"):
            run_and_capture(["   ", "\t"])


class TestStepMachine:
    def test_step_tracks_beam_tape_and_direction(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine

        machine = _Machine(["-*"], ScriptedIO())
        assert (machine.row, machine.col, machine.a, machine.b) == (0, 0, 0, 1)
        assert machine.tape == [0]
        machine.step()  # - flips the current bit
        assert machine.tape == [1]
        machine.step()  # * prints the tape and halts
        assert machine.io.getvalue() == "1"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.row == 0

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine

        assert hash(_Machine(["-*"], ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine(["-*"], ScriptedIO())) is True

    def test_beam_without_star_is_detected_as_a_cycle(self) -> None:
        """A beam that bounces forever revisits a snapshot and is proven."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine(["-"], ScriptedIO())) is False

    def test_short_lines_pad_on_the_right(self) -> None:
        """A short line keeps its content at the left, and is padded right.

        Padding the other way shifts every short row's commands sideways.
        Here that decides whether the program terminates at all: with the
        ``\\`` at column 0 the beam bounces forever, and moved to column 1
        it drops onto the ``*`` and halts.  The cycle detector settles it
        without a time limit -- the grid has no ``>``, so the state space is
        finite either way.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine(["\\", "-*"], ScriptedIO())) is False
