"""Unit tests for the LaserFuck interpreter."""

import io
from contextlib import redirect_stdout
from pathlib import Path
from typing import ClassVar

import pytest

from esolangs.interpreters.grid_based.laserfuck import run
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.randomness import FirstDraw
from tests.interpreters.contract import SnapshotContract


def run_and_capture(code: list[str], heading: int | None = 3) -> str:
    """Run ``code`` with its laser started in ``heading``."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code, IO(), rng=None if heading is None else FirstDraw(heading))
    return buffer.getvalue()


_OUTPUT = {
    "no_start_marker_prints_nothing": (["+"], ""),
    # \xff selects byte mode; + touches cell 0 -> prints \x01
    "plus_then_die_byte_mode": (["\u00ff}o+x\n   x"], "\x01"),
    # a second 'o' halts before any output
    "two_starts_halt_immediately": (["\u00ff}oo\n   x"], ""),
    # '#' skips the next command, so the '+' after it does not run
    "skip": (["\u00ff}o#+x\n     x"], ""),
    # without \xff, values print as decimals (one value, no newline)
    "decimal_mode": (["}o+x\n   x"], "1"),
    # '-' on zero makes -1, which is excluded from output
    "negative_cells_are_excluded": (["\u00ff}o-x\n   x"], ""),
    # ``(`` deflects a horizontal beam only when the cell is nonzero.
    "conditional_horizontal_mirror": (
        [" _", "/o\\", "\\v/", " #", " }x", " +", " ("],
        "2",
    ),
    # ``\`` turns the beam around: ``d`` becomes ``(d + 2) % 4``.
    "reverse": ([" _", "/o\\", "\\v/", " \\+x"], "1"),
    # ``{`` sets the heading to left, as ``}`` sets it to right.
    "absolute_steer_left": ([" /\\", "|o}\\", " \\/", " x+{"], "1"),
    # ``x`` removes one laser and leaves the other running.
    "a_split_beam_runs_on_after_its_sibling_dies": (
        [" /\\x", "|o}*  +x", " \\/", "   x"],
        "1",
    ),
    # Walking off the right edge is a miss, not an index.
    "the_beam_leaves_by_the_right_edge": (["o+"], "1"),
    # ``#`` before a step off the top: the beam still leaves and dies.
    "skip_across_the_top_edge_dies": ([" # ", "o^ ", " /+x"], ""),
    # ``|`` sends a rightward beam back the way it came.
    "a_horizontal_beam_turns_at_a_vertical_mirror": (["o+|++x"], "2"),
    # ``|`` refuses a vertical beam even when the cell is set.
    "a_downward_beam_passes_a_vertical_mirror": (["}o+v  ", "   |+x", "   x  "], "1"),
    # ``_`` and ``(`` take only *vertical* beams.
    "a_leftward_beam_passes_a_horizontal_mirror": (["x+_ o{", "     "], "1"),
    # Zero is a value; only *unwritten* cells are skipped.
    "a_written_zero_still_prints": (["o+-x"], "0"),
}


@pytest.mark.parametrize(("code", "expected"), _OUTPUT.values(), ids=list(_OUTPUT))
def test_output(code, expected) -> None:
    assert run_and_capture(code) == expected


class TestLaserFuck:
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

            def input_char(self, _prompt: str = "Input: ") -> int:
                return ord("1")

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
        # '_' always reflects a vertical beam; heading 1 (down) bounces up and
        # off the top, touching nothing
        assert run_and_capture(["\u00ff}\n|o_", "  x"], heading=1) == ""

    def test_cells_wrap_at_signed_32_bit_bounds(self) -> None:
        """The fixed-width tape wraps in signed two's-complement order."""
        from esolangs.interpreters.grid_based.laserfuck import _advance
        from esolangs.interpreters.persistent import chunked, flatten

        def advance(value: int, op: str) -> int:
            state = (chunked(((value, 0),)), 0, ((0, 0, 3),), 0, False, (0, 0, 0))
            tape = _advance(state, op, 0, 0, 3)[0]
            return next(iter(flatten(tape)))[0]

        assert advance((1 << 31) - 1, "+") == -(1 << 31)
        assert advance(-(1 << 31), "-") == (1 << 31) - 1

    def test_input_reads_whole_line_first_char(self) -> None:
        prog = ["\u00ff}o,x\n   x"]

        class TestIO(IO):
            def __init__(self) -> None:
                self.buf = io.StringIO()

            def input_char(self, _prompt: str = "Input: ") -> int:
                return ord("4")

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
        assert io_obj.buf.getvalue() == "4"  # ord('4') = 52 = '4'

    def test_step_on_an_already_halted_machine(self) -> None:
        # a second start halts the machine before any step; stepping is a no-op
        from esolangs.interpreters.grid_based.laserfuck import _Machine

        machine = _Machine(["oo"], IO(), rng=FirstDraw(3))
        assert machine.halted
        machine.step()  # must not raise


class TestUncoveredSteering:
    r"""``(``, ``\`` and ``{``, which no other program here reaches."""

    def test_every_start_heading_reaches_its_own_arm(self) -> None:
        """The heading is random, so a symmetric grid pins all four outcomes."""
        cross = ["   x", "   +", "x++o++++x", "   +", "   +", "   +", "   x"]
        assert [run_and_capture(cross, heading=h) for h in range(4)] == [
            "1",
            "3",
            "2",
            "4",
        ]

    def test_a_split_beam_leaves_on_the_perpendicular_axis(self) -> None:
        """``*`` splits the beam, and only its *direction* is random."""
        split = [" /\\ x", "|o}+*+x", " \\/ x"]
        assert [run_and_capture(split, heading=h) for h in range(4)] == ["2"] * 4

    def test_conditional_mirrors_pass_a_zero_cell(self) -> None:
        """The other half of each conditional mirror: it does *not* deflect."""
        assert run_and_capture([" _", "/o\\", "\\v/", " #", " }x", " (", " +"]) == "1"
        assert run_and_capture(["\xff}o+v", "    |", "    x"]) == "\x01"


class TestSurvivorGaps:
    r"""Programs that separate a mutated interpreter from the original."""

    def test_the_random_heading_is_actually_drawn(self) -> None:
        """``run`` with no heading draws one; every other test passes one."""
        cross = ["   x", "   +", "x++o++++x", "   +", "   +", "   +", "   x"]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(cross, IO())  # no heading: the interpreter draws one
        assert buffer.getvalue() in {"1", "2", "3", "4"}

    def test_a_character_outside_the_command_set_does_nothing(self) -> None:
        r"""An unknown character inside the grid is a no-op."""
        assert run_and_capture(["\xff}oX+x", "     x"]) == "\x01"
        assert run_and_capture(["o+X>+x"]) == "1\n1"
        assert run_and_capture(["o+Xx", "   x"]) == "1"
        assert run_and_capture(["o+X)x", "   x"]) == "2"

    def test_a_mirror_reads_the_value_not_the_written_flag(self) -> None:
        """A supplied NUL marks a zero cell, which the conditional mirror skips."""

        class TestIO(IO):
            def __init__(self) -> None:
                self.buf = io.StringIO()

            def input_char(self, _prompt: str = "Input: ") -> int:
                return 0

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

    def test_the_tape_dumps_once_however_far_it_is_stepped(self) -> None:
        """The post-halt step dumps the tape, and only the first one does."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO

        io_obj = ScriptedIO()
        machine = _Machine(["o+x"], io_obj, rng=FirstDraw(3))
        while not machine.halted:
            machine.step()
        assert io_obj.getvalue() == ""  # nothing until the step past the halt
        machine.step()
        first = io_obj.getvalue()
        assert first  # the dump actually produced something to repeat
        for _ in range(3):
            machine.step()
        assert io_obj.getvalue() == first

    def test_a_split_beam_entered_leftward_leaves_vertically(self) -> None:
        r"""``*`` entered *leftward* sends its child up or down."""
        cage = ["  x/\\", "x+*{o|", "  x\\/"]
        for heading in range(4):
            assert run_and_capture(cage, heading=heading) == "1", heading

    def test_a_zero_cell_passes_the_other_conditional_mirror(self) -> None:
        """A supplied NUL writes zero, so the beam passes the mirror straight."""

        class TestIO(IO):
            def __init__(self) -> None:
                self.buf = io.StringIO()
                self.reads = 0

            def input_char(self, _prompt: str = "Input: ") -> int:
                self.reads += 1
                if self.reads > 1:  # a deflected beam comes back for more
                    raise EOFError
                return 0

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
        # '#' skips the next command of the laser that hit it (wiki spec):
        # each beam skips its own '+', so one '+' runs; a shared flag gave 3.
        assert run_and_capture([" +  ", " #  ", "o*#++x", " #  ", " +  "]) == "1"

    def test_the_split_direction_is_drawn_along_the_new_axis(self) -> None:
        r"""``*`` draws only *which way* along the perpendicular axis."""
        cage = ["  x", "  +", "x+*x", "/ ^\\", "\\ o/", "  _"]
        for heading in range(4):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                run(cage, IO(), rng=FirstDraw(heading, rest=0))
            assert buffer.getvalue() == "2", heading


class TestSnapshotProgress:
    """Reads and draws count in the snapshot, so a repeat is a real cycle."""

    def test_a_cursorless_read_ring_is_not_a_cycle(self) -> None:
        """``,`` re-reading ``a`` round a ring runs to EOF, not a false cycle."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle
        from tests.interpreters.cursorless_io import CursorlessIO

        ring = ["/o,\\", "\\  /"]
        machine = _Machine(ring, CursorlessIO("aaaaaaaa"), rng=FirstDraw(3, rest=0))
        with pytest.raises(EOFError):
            run_until_halt_or_cycle(machine)

    def test_a_ring_that_escapes_on_a_later_draw_halts(self) -> None:
        """Six splits die upward, the seventh goes down to ``+``; ``)`` then ends it."""
        from esolangs.interpreters.grid_based.laserfuck import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_cycle

        class Draws:
            def __init__(self, values: list[int]) -> None:
                self.values = values

            def randbelow(self, _upper: int) -> int:
                return self.values.pop(0)

        ring = ["/o#x)*\\", "     + ", "\\     /"]
        machine = _Machine(ring, ScriptedIO(), rng=Draws([3, 0, 0, 0, 0, 0, 0, 1]))
        assert run_until_halt_or_cycle(machine) is True


def _machine(code: object) -> object:
    from esolangs.interpreters.grid_based.laserfuck import _Machine
    from esolangs.interpreters.io import IO

    return _Machine(code, IO(), rng=FirstDraw(3))


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["ÿ}o+x\n x"]


#: The wiki's Hello world rows are wider than a source line.
FIXTURES = Path(__file__).parents[1] / "fixtures"


def _wiki_run(code: str, stdin: str, heading: int) -> str:
    io_ = ScriptedIO(stdin)
    run(code.split("\n"), io_, rng=FirstDraw(heading))
    return io_.getvalue()


@pytest.mark.parametrize("heading", range(4))
def test_the_wiki_hello_world_prints_its_spent_counter(heading: int) -> None:
    """Every used cell prints, so the loop counter left at 0 comes out as NUL."""
    code = (FIXTURES / "laserfuck_hello.txt").read_text(encoding="utf-8").rstrip("\n")
    assert _wiki_run(code, "", heading) == "\x00Hello, world!"


def test_the_wiki_cat_prints_the_nul_it_stopped_on() -> None:
    """The NUL was read into a cell, so it is a used cell and prints too."""
    assert _wiki_run("ÿ/\\\n|o},#/)x\n _\\> /", "hi\x00", 0) == "hi\x00"
