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
        assert run_and_capture(["*"]) == "0\n"

    def test_flip_bit(self) -> None:
        assert run_and_capture(["-*"]) == "1\n"

    def test_move_right(self) -> None:
        assert run_and_capture([">-*"]) == "0 1\n"

    def test_flip_twice(self) -> None:
        assert run_and_capture([">--*"]) == "0 0\n"

    def test_skip_instruction_on_zero(self) -> None:
        """+ skips the next cell when the current bit is 0."""
        assert run_and_capture([">+-*"]) == "0 0\n"

    def test_reflect_backslash(self) -> None:
        """\\ reflects the direction."""
        assert run_and_capture(["\\-*"]) == "1\n"

    def test_reflect_slash(self) -> None:
        """/ reflects the direction."""
        assert run_and_capture(["/-*"]) == "1\n"

    def test_move_left(self) -> None:
        """< moves the tape head left when it is not at zero."""
        assert run_and_capture([">>-<*"]) == "0 0 1\n"

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
        assert (machine.x, machine.y, machine.a, machine.b) == (0, 0, 0, 1)
        assert machine.tape == [0]
        machine.step()  # - flips the current bit
        assert machine.tape == [1]
        machine.step()  # * prints the tape and halts
        assert machine.io.getvalue() == "1\n"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.x == 0

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
