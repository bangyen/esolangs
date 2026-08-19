"""Unit tests for the 3D Brainfuck interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.three_d_brainfuck import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class Test3DBrainfuck:
    def test_increment_and_print(self) -> None:
        assert run_program("+.") == "\x01"

    def test_cell_wraps(self) -> None:
        assert run_program("+" * 255 + ".") == "\xff"
        assert run_program("+" * 256 + ".") == "\x00"

    def test_array_moves(self) -> None:
        # n/e/u move the array pointer along the X/Z/Y axes
        assert run_program("n+.") == "\x01"
        assert run_program("ne+.") == "\x01"
        assert run_program("neu+.") == "\x01"

    def test_three_dimensional_cells_are_distinct(self) -> None:
        # n, e, u point at three distinct array cells; each + sets that cell
        assert run_program("n+.e+.u+.") == "\x01\x01\x01"

    def test_loop(self) -> None:
        assert run_program("++[-].") == "\x00"
        assert run_program("n+[-].") == "\x00"

    def test_input(self) -> None:
        assert run_program(",.", "X\n") == "X"

    def test_heading_default_is_plus_x(self) -> None:
        assert run_program("N+.") == "\x01"

    def test_heading_off_line_halts(self) -> None:
        # U sets heading +Y; the pointer walks off the source line and halts
        assert run_program("U+.") == ""

    def test_generation_blocks_are_noops(self) -> None:
        # ^/V/>/</"/' set the generation heading only
        assert run_program("^+.") == "\x01"
        assert run_program("'n+.") == "\x01"

    def test_comment_characters_are_noops(self) -> None:
        assert run_program("a+b.c") == "\x01"

    def test_malformed_brackets(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run_program("[")
        with pytest.raises(ValueError, match="unmatched"):
            run_program("]")

    def test_empty_program(self) -> None:
        assert run_program("") == ""


class TestStepMachine:
    def test_step_tracks_pointer_and_cells(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine

        machine = _Machine("+.", ScriptedIO())
        assert (machine.ip, machine.ap, machine.heading) == (
            (0, 0, 0),
            (0, 0, 0),
            (1, 0, 0),
        )
        machine.step()  # + sets the origin cell to 1
        assert machine.cells == {(0, 0, 0): 1}
        machine.step()  # . prints it
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ip == (2, 0, 0)

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine

        assert hash(_Machine("+.", ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("+.", ScriptedIO())) is True

    def test_bracket_loop_is_detected_as_a_cycle(self) -> None:
        """A bracket pair around a cell that never clears loops forever."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("+[]", ScriptedIO())) is False
