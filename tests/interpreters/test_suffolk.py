"""Unit tests for the Suffolk interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.suffolk import run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, io=IO())
    return buffer.getvalue()


class TestSuffolk:
    def test_count_and_output(self) -> None:
        """66 increments of the counter then a print yields 'A'."""
        assert run_and_capture("!" * 66 + "<.") == "A"

    def test_output_requires_accumulator(self) -> None:
        """A . with no accumulated value prints nothing."""
        assert run_and_capture("!.<<!") == ""

    def test_move_right(self) -> None:
        """> moves the pointer to a new tape cell."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        program = "!!!!!!!!>!><<<<<<<<<.!"
        machine = _Machine(program, ScriptedIO())
        for _ in range(len(program)):
            machine.step()
        assert machine.io.getvalue() == "@"

    def test_input(self) -> None:
        """, reads input into the accumulator."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",.", ScriptedIO("B\n"))
        machine.step()
        machine.step()
        assert machine.io.getvalue() == "A"

    def test_a_repeated_state_ends_the_run(self) -> None:
        """``run`` stops on a proof, not a count."""
        assert run_and_capture("!<.<<!") == "\x00"

    def test_cell_clamps_at_zero(self) -> None:
        """! floors the cell at 0 when the accumulator overshoots."""
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!!!<>!", IO())
        for _ in range(6):
            machine.step()
        assert machine.tape == (3, 0)

    def test_accumulator_is_subtracted_at_the_cell(self) -> None:
        """! subtracts the accumulator rather than adding it."""
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!!<!", IO())
        for _ in range(4):
            machine.step()
        assert machine.tape == (1,)

    def test_newline_input_adds_its_code(self) -> None:
        """Comma adds a newline's character code to the accumulator."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",.", ScriptedIO("\n"))
        machine.step()
        assert machine.acc == 10


class TestStepMachine:
    def test_step_wraps_at_code_end(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine("!.", IO())
        machine.step()  # !
        assert machine.ind == 1
        assert machine.tape == (1,)
        machine.step()  # .
        assert machine.ind == 0  # wrapped past the last instruction

    def test_cycle_is_detected(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        # "." never changes state, so the snapshot repeats immediately
        assert run_until_halt_or_cycle(_Machine(".", IO())) is False
        assert run_until_halt_or_cycle(_Machine("<", IO())) is False

    def test_snapshot_includes_the_input_cursor(self) -> None:
        """Reading a byte changes the state, even when nothing else does."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",", ScriptedIO("\x00\n\x00\n"))
        before = machine.snapshot()
        machine.step()  # consumes a line; acc stays 0 because the byte is NUL
        assert machine.acc == before[2]  # nothing else moved
        assert machine.snapshot() != before

    def test_eof_zeroes_the_accumulator(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.suffolk import _Machine

        machine = _Machine(",.", ScriptedIO("A"))
        machine.step()
        assert machine.acc == ord("A")
        machine.step()
        machine.step()
        assert machine.acc == 0
        assert machine.halted

    def test_snapshot_excludes_pass_count(self) -> None:
        from esolangs.interpreters.tape_based.suffolk import _Machine

        # "." is a no-op when acc is 0, so the state after one whole pass
        # (len(code) steps) equals the initial state -- the pass count must
        # not be part of snapshot, or every state would be unique and the
        # cycle detector would never fire.
        machine = _Machine("..", IO())
        before = machine.snapshot()
        machine.step()
        machine.step()  # one whole pass
        assert machine.snapshot() == before


def test_eof_changes_the_snapshot() -> None:
    """Pins ``_exhausted`` in the snapshot: ``,`` at EOF wraps to the same
    cursor, tape and accumulator, yet the machine is now halted."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.suffolk import _Machine

    machine = _Machine(",", ScriptedIO(""))
    before = machine.snapshot()
    machine.step()
    assert machine.halted
    assert machine.snapshot() != before
