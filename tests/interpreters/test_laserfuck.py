"""Unit tests for the LaserFuck interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.grid_based.laserfuck import run
from esolangs.interpreters.io import IO


def run_and_capture(code: list[str], heading: int = 3) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO(), heading=heading)
    return buffer.getvalue()


class TestLaserFuck:
    def test_no_start_marker_prints_nothing(self) -> None:
        assert run_and_capture(["+"]) == ""

    def test_plus_then_die_byte_mode(self) -> None:
        # \xff selects byte mode; + touches cell 0 -> prints \x01
        assert run_and_capture(["\u00ff}o+x\n   x"]) == "\x01"

    def test_two_starts_halt_immediately(self) -> None:
        # a second 'o' halts before any output
        assert run_and_capture(["\u00ff}oo\n   x"]) == ""

    def test_right_heading_is_deterministic(self) -> None:
        # heading 3 (right) runs the + and dies on x
        assert run_and_capture(["\u00ff}o+x\n   x"], heading=3) == "\x01"

    def test_conditional_mirror(self) -> None:
        # ',' reads '1' (49); ')' reflects a right-moving beam on a nonzero
        # cell, 'v' turns it down to the 'x' on the bottom row, where it dies.
        # Only the input cell is touched and prints as '1'.

        class TestIO(IO):
            def __init__(self) -> None:
                self.buf = io.StringIO()

            def input_str(self, _prompt: str = "Input: ") -> str:
                return "1"

            def print_char(self, char: str) -> None:
                self.buf.write(char)

            def print_str(self, text: str) -> None:
                self.buf.write(text)

            def print_num(self, num: int) -> None:
                self.buf.write(str(num))

        prog = ["\u00ff}},#v)x", "|o^", " _ x"]
        for heading in range(4):
            io_obj = TestIO()
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                run(prog, io_obj, heading=heading)
            assert io_obj.buf.getvalue() == "1", f"heading {heading}"

    def test_unconditional_vertical_mirror(self) -> None:
        # '_' always reflects a vertical beam; heading 1 (down) bounces up and
        # off the top, touching nothing
        assert run_and_capture(["\u00ff}\n|o_", "  x"], heading=1) == ""

    def test_skip(self) -> None:
        # '#' skips the next command, so the '+' after it does not run
        assert run_and_capture(["\u00ff}o#+x\n     x"]) == ""

    def test_decimal_mode(self) -> None:
        # without \xff, values print as decimals (one value, no newline)
        assert run_and_capture(["}o+x\n   x"]) == "1"

    def test_negative_cells_are_excluded(self) -> None:
        # '-' on zero makes -1, which is excluded from output
        assert run_and_capture(["\u00ff}o-x\n   x"]) == ""

    def test_input_reads_whole_line_first_char(self) -> None:
        prog = ["\u00ff}o,x\n   x"]

        class TestIO(IO):
            def __init__(self) -> None:
                self.buf = io.StringIO()

            def input_str(self, _prompt: str = "Input: ") -> str:
                return "42"

            def print_char(self, char: str) -> None:
                self.buf.write(char)

            def print_str(self, text: str) -> None:
                self.buf.write(text)

            def print_num(self, num: int) -> None:
                self.buf.write(str(num))

        io_obj = TestIO()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(prog, io_obj, heading=3)
        assert io_obj.buf.getvalue() == "4"  # ord('4') = 52 = '4'

    def test_steps_off_the_top(self) -> None:
        # heading 0 (up) from the top row steps off the grid and dies
        assert run_and_capture(["o"], heading=0) == ""

    def test_move_left_below_cell_zero(self) -> None:
        # '<' at cell 0 inserts a fresh cell to the left
        assert run_and_capture(["o<x"]) == ""

    def test_slash_reflects_up(self) -> None:
        # '/' reflects right (3) to up (0), which steps off the top edge
        assert run_and_capture(["o/"], heading=3) == ""

    def test_star_duplicates_laser(self) -> None:
        # '*' duplicates the laser perpendicularly; both copies die on 'x'
        assert run_and_capture([" x ", "o*x", " x "], heading=3) == ""

    def test_decimal_mode_multiple_values(self) -> None:
        # two touched cells print one value per line in decimal mode
        assert run_and_capture(["o+>+x"]) == "1\n1"

    def test_step_on_an_already_halted_machine(self) -> None:
        # a second start halts the machine before any step; stepping is a no-op
        from esolangs.interpreters.grid_based.laserfuck import _Machine

        machine = _Machine(["oo"], IO(), heading=3)
        assert machine.halted
        machine.step()  # must not raise


class TestUncoveredSteering:
    r"""``(``, ``\`` and ``{``, which no other program here reaches.

    Instrumenting the suite -- recording the cell under the beam at every
    step, over every program and all four headings -- shows fifteen of the
    eighteen commands running and these three never.  Each has a covered
    sibling that hides it: ``_`` is the same mirror as ``(`` but
    unconditional, and ``}`` is the same absolute steer as ``{`` but
    rightward, so a mutation to the uncovered half changed nothing any
    program could see.

    All three grids cage the laser in mirrors, so they halt whatever
    heading it starts on -- which matters because the heading is otherwise
    drawn at random.  Reaching these commands the naive way does not
    terminate: a bare ``\`` bounces the beam between the reverse and
    whatever sent it there, and a bare ``{`` walks off the grid to the left
    while the tape grows to meet it, which is the unbounded-growth case the
    cycle detector documents itself as unable to prove.
    """

    def test_conditional_horizontal_mirror(self) -> None:
        r"""``(`` deflects a horizontal beam only when the cell is nonzero.

        The ``#`` skips the cell after it, so the beam arrives at the ``(``
        with the tape already incremented; the deflection sends it back
        over the ``+`` a second time, and the two increments are what
        separates a mirror that consulted the tape from one that did not.
        """
        assert run_and_capture([" _", "/o\\", "\\v/", " #", " }x", " +", " ("]) == "2"

    def test_reverse(self) -> None:
        r"""``\`` turns the beam around: ``d`` becomes ``(d + 2) % 4``."""
        assert run_and_capture([" _", "/o\\", "\\v/", " \\+x"]) == "1"

    def test_absolute_steer_left(self) -> None:
        """``{`` sets the heading to left, as ``}`` sets it to right."""
        assert run_and_capture([" /\\", "|o}\\", " \\/", " x+{"]) == "1"
