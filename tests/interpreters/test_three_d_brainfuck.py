"""Unit tests for the 3D Brainfuck interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine, run


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
        """One decrement from 0 is 255, which pins the width and direction.

        Wrapping upward lands on 0 under any modulus, and the decrement was
        only ever run on a cell holding more than it subtracts -- so the
        step down could have been an addition, or the modulus anything at
        all, and every program still agreed.
        """
        assert run_program("-.") == "\xff"
        assert run_program("--.") == "\xfe"

    def test_array_moves(self) -> None:
        # n/e/u move the array pointer along the X/Z/Y axes
        assert run_program("n+.") == "\x01"
        assert run_program("ne+.") == "\x01"
        assert run_program("neu+.") == "\x01"

    def test_three_dimensional_cells_are_distinct(self) -> None:
        # n, e, u point at three distinct array cells; each + sets that cell
        assert run_program("n+.e+.u+.") == "\x01\x01\x01"

    def test_each_axis_has_an_inverse(self) -> None:
        """s, w and d undo n, e and u.

        Only the three positive directions were used anywhere, and every
        program walked outward from the origin -- so which axis a move
        actually took never mattered, the cells being distinct either way.
        Marking the origin and returning to it says the move came back to
        the same cell, and reading a neighbour says it went somewhere else
        on the way.
        """
        assert run_program("+ns.") == "\x01"
        assert run_program("+ew.") == "\x01"
        assert run_program("+ud.") == "\x01"
        # the cell stepped onto is not the origin: marking it leaves the
        # origin alone
        assert run_program("n+s.") == "\x00"
        assert run_program("e+w.") == "\x00"
        assert run_program("u+d.") == "\x00"

    def test_each_move_goes_the_way_its_axis_points(self) -> None:
        """The array pointer lands on the named coordinate, not its mirror.

        Output cannot show this.  ``_ARRAY`` is closed under negation, so
        flipping the sign of any component relabels a pair of moves --
        ``n``/``s``, ``u``/``d``, ``e``/``w`` -- and every program that walks
        out and back returns to the origin either way, while one that only
        walks out lands on a cell that is distinct either way.  The
        coordinate itself is the thing that differs, so it is what these
        assert: one move per axis, each naming the cell it wrote.
        """
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
        """The instruction pointer moves the way the heading points.

        The same negation symmetry sits on the advance: flipping a component
        of the heading sends the pointer the other way along that axis.  On
        the default +X heading the program simply runs, so the flip shows
        only off-axis -- where the pointer leaves the source line and the
        program halts either way, at the same step count.  The *position* it
        stops at is what separates them.
        """
        for block, heading in (
            ("U", (0, 1, 0)),
            ("D", (0, -1, 0)),
            ("E", (0, 0, 1)),
            ("W", (0, 0, -1)),
        ):
            machine = _Machine(block + "+", ScriptedIO())
            machine.step()  # the heading block, then one move along it
            assert machine.heading == heading, block
            # the block at the origin is replaced as the advance vector, so
            # the pointer steps straight off the +X line and stops
            assert machine.ip == heading, block
            assert machine.halted, block

    def test_loop(self) -> None:
        assert run_program("++[-].") == "\x00"
        assert run_program("n+[-].") == "\x00"

    def test_a_zero_cell_skips_the_loop_body(self) -> None:
        """``[`` jumps past its ``]`` when the cell is 0, rather than in.

        Every loop tested entered its body at least once, so a ``[`` that
        stopped jumping entirely -- or jumped somewhere other than one past
        the match -- still produced the same output.  These two say where
        it went: the body must not run, and what follows the loop must.
        """
        assert run_program("[+].") == "\x00"
        assert run_program("[.]") == ""
        # The jump reads the bracket table at the *instruction pointer's*
        # index.  A `[` at index 0 is the one case where any other index
        # into it happens to give the same answer, so the skip is also
        # tested from further along the line.
        assert run_program("n[+].") == "\x00"
        assert run_program("+-[+].") == "\x00"

    def test_an_untouched_cell_reads_as_zero(self) -> None:
        """Cells are created on demand, and one never written holds 0.

        The array is a dict, so every read needs a default; without one it
        yields None and the print raises instead of emitting a NUL.  Only a
        cell the program has never written reaches that path.
        """
        assert run_program(".") == "\x00"
        assert run_program("n.") == "\x00"
        assert run_program("nu.") == "\x00"

    def test_a_loop_ends_on_a_cell_it_never_wrote(self) -> None:
        """``]`` reads the same on-demand default that everything else does.

        Every loop so far closed over the cell it had been counting down,
        which is written by definition.  Moving the array pointer inside
        the body leaves ``]`` reading a cell that was never written, and
        the loop only terminates if that reads as 0 -- a missing or
        non-zero default spins here forever.
        """
        assert run_program("+[n].") == "\x00"
        assert run_program("++[-n].") == "\x00"

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
        # An X is a comment too.  The letters above are outside the command
        # set however it is spelled, so they do not catch a set widened to
        # include one -- and as a command X would read input and raise.
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
