r"""Unit tests for the 3D Brainfuck interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine, run
from tests.interpreters.contract import CycleContract, SnapshotContract


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

    def test_cell_wraps_below_zero(self) -> None:
        r"""One decrement from 0 is 255, which pins the width and direction."""
        assert run_program("-.") == "\xff"
        assert run_program("--.") == "\xfe"

    def test_array_moves(self) -> None:
        # n/e/u move the array pointer.
        assert run_program("n+.") == "\x01"
        assert run_program("ne+.") == "\x01"
        assert run_program("neu+.") == "\x01"

    def test_three_dimensional_cells_are_distinct(self) -> None:
        # n, e, u point at three.
        assert run_program("n+.e+.u+.") == "\x01\x01\x01"

    def test_each_axis_has_an_inverse(self) -> None:
        r"""s, w and d undo n, e and u."""
        assert run_program("+ns.") == "\x01"
        assert run_program("+ew.") == "\x01"
        assert run_program("+ud.") == "\x01"
        # the cell stepped onto is not.
        # origin alone.
        assert run_program("n+s.") == "\x00"
        assert run_program("e+w.") == "\x00"
        assert run_program("u+d.") == "\x00"

    def test_each_move_goes_the_way_its_axis_points(self) -> None:
        r"""The array pointer lands on the named coordinate, not its mirror."""
        for program, cell in (
            ("n+", (1, 0, 0)),
            ("s+", (-1, 0, 0)),
            ("u+", (0, 1, 0)),
            ("d+", (0, -1, 0)),
            ("e+", (0, 0, 1)),
            ("w+", (0, 0, -1)),
        ):
            machine = _Machine(program, ScriptedIO())
            while not machine.halted:
                machine.step()
            assert machine.ap == cell, program
            assert machine.cells == {cell: 1}, program

    def test_the_instruction_pointer_advances_along_its_heading(self) -> None:
        r"""The instruction pointer moves the way the heading points."""
        for block, heading in (
            ("U", (0, 1, 0)),
            ("D", (0, -1, 0)),
            ("E", (0, 0, 1)),
            ("W", (0, 0, -1)),
        ):
            machine = _Machine(block + "+", ScriptedIO())
            machine.step()  # the heading block, then one.
            assert machine.heading == heading, block
            # the block at the origin is.
            # the pointer steps straight.
            assert machine.pos == heading, block
            assert machine.halted, block

    def test_loop(self) -> None:
        assert run_program("++[-].") == "\x00"
        assert run_program("n+[-].") == "\x00"

    def test_a_zero_cell_skips_the_loop_body(self) -> None:
        r"""``[`` jumps past its ``]`` when the cell is 0, rather than in."""
        assert run_program("[+].") == "\x00"
        assert run_program("[.]") == ""
        # The jump reads the bracket.
        # index.
        # into it happens to give the.
        # tested from further along the.
        assert run_program("n[+].") == "\x00"
        assert run_program("+-[+].") == "\x00"

    def test_an_untouched_cell_reads_as_zero(self) -> None:
        r"""Cells are created on demand, and one never written holds 0."""
        assert run_program(".") == "\x00"
        assert run_program("n.") == "\x00"
        assert run_program("nu.") == "\x00"

    def test_a_loop_ends_on_a_cell_it_never_wrote(self) -> None:
        r"""``]`` reads the same on-demand default that everything else does."""
        assert run_program("+[n].") == "\x00"
        assert run_program("++[-n].") == "\x00"

    def test_input(self) -> None:
        assert run_program(",.", "X\n") == "X"

    def test_heading_default_is_plus_x(self) -> None:
        assert run_program("N+.") == "\x01"

    def test_heading_off_line_halts(self) -> None:
        # U sets heading +Y; the.
        assert run_program("U+.") == ""

    def test_generation_blocks_are_noops(self) -> None:
        # ^/V/>/</"/' set the.
        assert run_program("^+.") == "\x01"
        assert run_program("'n+.") == "\x01"

    def test_comment_characters_are_noops(self) -> None:
        assert run_program("a+b.c") == "\x01"
        # An X is a comment too.
        # set however it is spelled, so.
        # include one -- and as a.
        assert run_program("X+X.X") == "\x01"

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
        assert (machine.pos, machine.ap, machine.heading) == (
            (0, 0, 0),
            (0, 0, 0),
            (1, 0, 0),
        )
        machine.step()  # + sets the origin cell to 1.
        assert machine.cells == {(0, 0, 0): 1}
        machine.step()  # .
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.pos == (2, 0, 0)


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "+."
    halting_program = "+."
    looping_program = "+[]"
