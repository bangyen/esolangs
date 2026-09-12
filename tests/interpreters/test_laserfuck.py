r"""Unit tests for the LaserFuck interpreter."""

import io
from contextlib import redirect_stdout
from typing import ClassVar
from unittest.mock import patch

from esolangs.interpreters.grid_based.laserfuck import run
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import FirstDraw
from tests.interpreters.contract import SnapshotContract


def run_and_capture(code: list[str], heading: int | None = 3) -> str:
    r"""Run ``code`` with its laser started in ``heading``."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO(), rng=None if heading is None else FirstDraw(heading))
    return buffer.getvalue()


class TestLaserFuck:
    def test_no_start_marker_prints_nothing(self) -> None:
        assert run_and_capture(["+"]) == ""

    def test_plus_then_die_byte_mode(self) -> None:
        # \xff selects byte mode; +.
        assert run_and_capture(["\u00ff}o+x\n   x"]) == "\x01"

    def test_two_starts_halt_immediately(self) -> None:
        # a second 'o' halts before any.
        assert run_and_capture(["\u00ff}oo\n   x"]) == ""

    def test_right_heading_is_deterministic(self) -> None:
        # heading 3 (right) runs the +.
        assert run_and_capture(["\u00ff}o+x\n   x"], heading=3) == "\x01"

    def test_conditional_mirror(self) -> None:
        # ',' reads '1' (49); ')'.
        # cell, 'v' turns it down to.
        # Only the input cell is.

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
                run(prog, io_obj, rng=FirstDraw(heading))
            assert io_obj.buf.getvalue() == "1", f"heading {heading}"

    def test_unconditional_vertical_mirror(self) -> None:
        # '_' always reflects a.
        # off the top, touching nothing.
        assert run_and_capture(["\u00ff}\n|o_", "  x"], heading=1) == ""

    def test_skip(self) -> None:
        # '#' skips the next command,.
        assert run_and_capture(["\u00ff}o#+x\n     x"]) == ""

    def test_decimal_mode(self) -> None:
        # without \xff, values print as.
        assert run_and_capture(["}o+x\n   x"]) == "1"

    def test_negative_cells_are_excluded(self) -> None:
        # '-' on zero makes -1, which.
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
            run(prog, io_obj, rng=FirstDraw(3))
        assert io_obj.buf.getvalue() == "4"  # ord('4') = 52 = '4'.

    def test_steps_off_the_top(self) -> None:
        # heading 0 (up) from the top.
        assert run_and_capture(["o"], heading=0) == ""

    def test_move_left_below_cell_zero(self) -> None:
        # '<' at cell 0 inserts a fresh.
        assert run_and_capture(["o<x"]) == ""

    def test_slash_reflects_up(self) -> None:
        # '/' reflects right (3) to up.
        assert run_and_capture(["o/"], heading=3) == ""

    def test_star_duplicates_laser(self) -> None:
        # '*' duplicates the laser.
        assert run_and_capture([" x ", "o*x", " x "], heading=3) == ""

    def test_decimal_mode_multiple_values(self) -> None:
        # two touched cells print one.
        assert run_and_capture(["o+>+x"]) == "1\n1"

    def test_step_on_an_already_halted_machine(self) -> None:
        # a second start halts the.
        from esolangs.interpreters.grid_based.laserfuck import _Machine

        machine = _Machine(["oo"], IO(), rng=FirstDraw(3))
        assert machine.halted
        machine.step()  # must not raise.


class TestUncoveredSteering:
    r"""``(``, ``\`` and ``{``, which no other program here reaches."""

    def test_conditional_horizontal_mirror(self) -> None:
        r"""``(`` deflects a horizontal beam only when the cell is nonzero."""
        assert run_and_capture([" _", "/o\\", "\\v/", " #", " }x", " +", " ("]) == "2"

    def test_reverse(self) -> None:
        r"""``\`` turns the beam around: ``d`` becomes ``(d + 2) % 4``."""
        assert run_and_capture([" _", "/o\\", "\\v/", " \\+x"]) == "1"

    def test_absolute_steer_left(self) -> None:
        r"""``{`` sets the heading to left, as ``}`` sets it to right."""
        assert run_and_capture([" /\\", "|o}\\", " \\/", " x+{"]) == "1"

    def test_every_start_heading_reaches_its_own_arm(self) -> None:
        r"""The heading is random, so a symmetric grid pins all four outcomes."""
        cross = ["   x", "   +", "x++o++++x", "   +", "   +", "   +", "   x"]
        assert [run_and_capture(cross, heading=h) for h in range(4)] == [
            "1",
            "3",
            "2",
            "4",
        ]

    def test_a_split_beam_leaves_on_the_perpendicular_axis(self) -> None:
        r"""``*`` splits the beam, and only its *direction* is random."""
        split = [" /\\ x", "|o}+*+x", " \\/ x"]
        assert [run_and_capture(split, heading=h) for h in range(4)] == ["2"] * 4

    def test_the_pointer_moves_within_tape_that_already_exists(self) -> None:
        r"""``<`` and ``>`` move rather than grow, once the tape is there."""
        assert run_and_capture([" /\\", "|o}><>+x", " \\/"]) == "1"

    def test_a_split_beam_runs_on_after_its_sibling_dies(self) -> None:
        r"""``x`` removes one laser and leaves the other running."""
        assert run_and_capture([" /\\x", "|o}*  +x", " \\/", "   x"]) == "1"

    def test_conditional_mirrors_pass_a_zero_cell(self) -> None:
        r"""The other half of each conditional mirror: it does *not* deflect."""
        assert run_and_capture([" _", "/o\\", "\\v/", " #", " }x", " (", " +"]) == "1"
        assert run_and_capture(["\xff}o+v", "    |", "    x"]) == "\x01"


class TestSurvivorGaps:
    r"""Programs that separate a mutated interpreter from the original."""

    def test_the_random_heading_is_actually_drawn(self) -> None:
        r"""``run`` with no heading draws one; every other test passes one."""
        cross = ["   x", "   +", "x++o++++x", "   +", "   +", "   +", "   x"]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(cross, IO())  # no heading: the interpreter.
        assert buffer.getvalue() in {"1", "2", "3", "4"}

    def test_rows_are_padded_to_equal_width(self) -> None:
        r"""Padding makes every row as wide as the widest."""
        assert run_and_capture(["xxxx", "o"]) == ""

    def test_the_beam_leaves_by_the_right_edge(self) -> None:
        r"""Walking off the right edge is a miss, not an index."""
        assert run_and_capture(["o+"]) == "1"

    def test_skip_across_the_top_edge_wraps(self) -> None:
        r"""``#`` before a step off the top: the beam wraps to the bottom."""
        assert run_and_capture([" # ", "o^ ", " /+x"]) == "1"

    def test_the_pointer_moves_over_cells_it_already_wrote(self) -> None:
        r"""Moving back onto a written cell, and writing a second one."""
        assert run_and_capture(["o+<+x"]) == "1\n1"
        assert run_and_capture(["o+>>+<<+x"]) == "2\n1"

    def test_a_character_outside_the_command_set_does_nothing(self) -> None:
        r"""An unknown character inside the grid is a no-op."""
        assert run_and_capture(["\xff}oX+x", "     x"]) == "\x01"
        assert run_and_capture(["o+X>+x"]) == "1\n1"
        assert run_and_capture(["o+Xx", "   x"]) == "1"
        assert run_and_capture(["o+X)x", "   x"]) == "2"

    def test_a_horizontal_beam_turns_at_a_vertical_mirror(self) -> None:
        r"""``|`` sends a rightward beam back the way it came."""
        assert run_and_capture(["o+|++x"]) == "2"

    def test_a_downward_beam_passes_a_vertical_mirror(self) -> None:
        r"""``|`` refuses a vertical beam even when the cell is set."""
        assert run_and_capture(["}o+v  ", "   |+x", "   x  "]) == "1"

    def test_a_leftward_beam_passes_a_horizontal_mirror(self) -> None:
        r"""``_`` and ``(`` take only *vertical* beams."""
        assert run_and_capture(["x+_ o{", "     "]) == "1"

    def test_a_mirror_reads_the_value_not_the_written_flag(self) -> None:
        r"""A cell that was written *and* is zero does not deflect."""

        class TestIO(IO):
            def __init__(self) -> None:
                self.buf = io.StringIO()

            def input_str(self, _prompt: str = "Input: ") -> str:
                return ""

            def print_char(self, char: str) -> None:
                self.buf.write(char)

            def print_str(self, text: str) -> None:
                self.buf.write(text)

            def print_num(self, num: int) -> None:
                self.buf.write(str(num))

        io_obj = TestIO()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(["o,v", "  (", "  x"], io_obj, rng=FirstDraw(3))
        assert io_obj.buf.getvalue() == "0"

    def test_byte_mode_prints_every_value(self) -> None:
        r"""Byte mode runs the characters together; it does not stop at one."""
        assert run_and_capture(["\xff}o+>+x", "      x"]) == "\x01\x01"

    def test_a_written_zero_still_prints(self) -> None:
        r"""Zero is a value; only *unwritten* cells are skipped."""
        assert run_and_capture(["o+-x"]) == "0"

    def test_the_tape_dumps_once_however_far_it_is_stepped(self) -> None:
        r"""The post-halt step dumps the tape, and only the first one does."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO

        io_obj = ScriptedIO()
        machine = _Machine(["o+x"], io_obj, rng=FirstDraw(3))
        while not machine.halted:
            machine.step()
        assert io_obj.getvalue() == ""  # nothing until the step past.
        machine.step()
        first = io_obj.getvalue()
        assert first  # the dump actually produced.
        for _ in range(3):
            machine.step()
        assert io_obj.getvalue() == first

    def test_a_split_beam_entered_leftward_leaves_vertically(self) -> None:
        r"""``*`` entered *leftward* sends its child up or down."""
        cage = ["  x/\\", "x+*{o|", "  x\\/"]
        for heading in range(4):
            assert run_and_capture(cage, heading=heading) == "1", heading

    def test_a_zero_cell_passes_the_other_conditional_mirror(self) -> None:
        r"""``)`` on a written zero: it does not deflect, and the guard holds."""

        class TestIO(IO):
            def __init__(self) -> None:
                self.buf = io.StringIO()
                self.reads = 0

            def input_str(self, _prompt: str = "Input: ") -> str:
                self.reads += 1
                if self.reads > 1:  # a deflected beam comes back.
                    raise EOFError
                return ""

            def print_char(self, char: str) -> None:
                self.buf.write(char)

            def print_str(self, text: str) -> None:
                self.buf.write(text)

            def print_num(self, num: int) -> None:
                self.buf.write(str(num))

        io_obj = TestIO()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(["}o,)x", "    x"], io_obj, rng=FirstDraw(3))
        assert io_obj.buf.getvalue() == "0"

    def test_two_lasers_run_in_turn(self) -> None:
        r"""``*`` leaves two live beams, and they alternate."""
        assert run_and_capture([" +x", "o*+x", " +x"]) == "2"
        assert run_and_capture([" #+x ", "o*#+x", " #+x "]) == "1"

    def test_the_drawn_heading_is_one_of_four(self) -> None:
        r"""The initial draw is ``randbelow(4)``, not some wider range."""
        with patch("secrets.randbelow", side_effect=lambda n: n - 1):
            assert run_and_capture(["o\\ ", " +x"], heading=None) == "1"

    def test_the_split_direction_is_drawn_along_the_new_axis(self) -> None:
        r"""``*`` draws only *which way* along the perpendicular axis."""
        cage = ["  x", "  +", "x+*x", "/ ^\\", "\\ o/", "  _"]
        for heading in range(4):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                run(cage, IO(), rng=FirstDraw(heading, rest=0))
            assert buffer.getvalue() == "2", heading

    def test_the_jump_flag_starts_false(self) -> None:
        r"""``jmp`` begins ``False``, and the snapshot carries that value."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine(["+"], ScriptedIO(), rng=FirstDraw(3))
        assert machine.jmp is False
        assert machine.snapshot()[2] is False


def _machine(code: object) -> object:
    from esolangs.interpreters.grid_based.laserfuck import _Machine
    from esolangs.interpreters.io import IO

    return _Machine(code, IO(), rng=FirstDraw(3))


class TestContract(SnapshotContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["ÿ}o+x\n x"]
