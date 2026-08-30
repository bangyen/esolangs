"""Unit tests for the LaserFuck interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.grid_based.laserfuck import run
from esolangs.interpreters.io import IO


def run_and_capture(code: list[str], heading: int | None = 3) -> str:
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

    def test_every_start_heading_reaches_its_own_arm(self) -> None:
        """The heading is random, so a symmetric grid pins all four outcomes.

        Every other test passes ``heading=`` to make the run repeatable,
        which means the branch that *draws* a heading is never taken.  A
        cross with a different number of ``+`` down each arm does not need
        to: whichever direction the laser leaves in, it halts, and the
        count it prints says which arm it took.
        """
        cross = ["   x", "   +", "x++o++++x", "   +", "   +", "   +", "   x"]
        assert [run_and_capture(cross, heading=h) for h in range(4)] == [
            "1",
            "3",
            "2",
            "4",
        ]

    def test_a_split_beam_leaves_on_the_perpendicular_axis(self) -> None:
        """``*`` splits the beam, and only its *direction* is random.

        The new laser's axis is computed -- perpendicular to the incoming
        beam -- and the random draw picks which way along it.  Putting an
        ``x`` at both ends makes the two draws equivalent, so the program
        is deterministic while the arithmetic that chose the axis is still
        exercised.
        """
        split = [" /\\ x", "|o}+*+x", " \\/ x"]
        assert [run_and_capture(split, heading=h) for h in range(4)] == ["2"] * 4

    def test_the_pointer_moves_within_tape_that_already_exists(self) -> None:
        """``<`` and ``>`` move rather than grow, once the tape is there.

        Both were only ever run at an edge -- ``>`` at the last cell, where
        it appends, and ``<`` at cell 0, where it prepends -- so the move
        itself was never separated from the growth.  Going right, left,
        then right again lands twice on tape that already exists.
        """
        assert run_and_capture([" /\\", "|o}><>+x", " \\/"]) == "1"

    def test_a_split_beam_runs_on_after_its_sibling_dies(self) -> None:
        """``x`` removes one laser and leaves the other running.

        The split grid above kills its second laser immediately; here the
        two arms are different lengths, so one reaches its ``x`` while the
        other still has cells to cross.
        """
        assert run_and_capture([" /\\x", "|o}*  +x", " \\/", "   x"]) == "1"

    def test_conditional_mirrors_pass_a_zero_cell(self) -> None:
        """The other half of each conditional mirror: it does *not* deflect.

        Command coverage is not branch coverage.  Every mirror above runs
        on a cell that has already been incremented, so only the deflecting
        half of ``(`` and ``|`` was ever taken -- and a guard that stopped
        consulting the tape at all, or joined its two conditions with
        ``or`` instead of ``and``, still deflected in every case the suite
        could see.

        These two swap the order so the beam meets the mirror first: the
        ``(`` grid increments *after* its mirror, and the ``|`` one sends a
        beam down onto a mirror whose cell is set, which is the reverse of
        the covered case.
        """
        assert run_and_capture([" _", "/o\\", "\\v/", " #", " }x", " (", " +"]) == "1"
        assert run_and_capture(["\xff}o+v", "    |", "    x"]) == "\x01"


class TestSurvivorGaps:
    r"""Programs that separate a mutated interpreter from the original.

    A mutation run left 59 survivors -- edits no test objected to.
    Categorising them found that most were not equivalent mutants but a
    few untested *shapes*, each covering several edits at once: the
    pointer only ever moved at an edge, conditional mirrors were only ever
    met head-on, the command set could widen without any test noticing,
    and the random heading was never drawn at all.  Every grid below was
    run against the mutated code and prints something different there.
    """

    def test_the_random_heading_is_actually_drawn(self) -> None:
        """``run`` with no heading draws one; every other test passes one.

        The helper above takes ``heading: int = 3``, so the branch calling
        ``secrets.randbelow`` is never reached -- not even by
        ``test_every_start_heading_reaches_its_own_arm``, which loops over
        ``range(4)`` and passes each value explicitly, though its docstring
        says the cross "does not need to".  The cross halts whatever it
        draws, so the draw can be exercised without pinning its result.
        """
        cross = ["   x", "   +", "x++o++++x", "   +", "   +", "   +", "   x"]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(cross, IO())  # no heading: the interpreter draws one
        assert buffer.getvalue() in {"1", "2", "3", "4"}

    def test_rows_are_padded_to_equal_width(self) -> None:
        """Padding makes every row as wide as the widest.

        The bounds check reads ``len(self.text[0])`` -- row 0's width -- so
        a beam on a row left *shorter* than row 0 would pass the check and
        index past that row's end.  A short row under a long one catches
        it; every other grid here is uniform or has its beam on row 0.
        """
        assert run_and_capture(["xxxx", "o"]) == ""

    def test_the_beam_leaves_by_the_right_edge(self) -> None:
        """Walking off the right edge is a miss, not an index.

        Every other grid dies on an ``x`` or off the top, so the column
        bound is only ever approached from one side.
        """
        assert run_and_capture(["o+"]) == "1"

    def test_skip_across_the_top_edge_wraps(self) -> None:
        r"""``#`` before a step off the top: the beam wraps to the bottom.

        Stepping off the top sets ``row`` to ``self.rows``, one past the
        last row, and because ``#`` defers the next move the beam comes
        back at ``rows - 1`` -- the bottom of the same column -- instead of
        dying there.  No other program here shows the wrap.
        """
        assert run_and_capture([" # ", "o^ ", " /+x"]) == "1"

    def test_the_pointer_moves_over_cells_it_already_wrote(self) -> None:
        """Moving back onto a written cell, and writing a second one.

        ``<`` at cell 0 prepends; the increments before and after it must
        land on *different* cells.  An off-by-one in either the guard or
        the insert index puts both on the same one, and the two values
        collapse into a single larger one.
        """
        assert run_and_capture(["o+<+x"]) == "1\n1"
        assert run_and_capture(["o+>>+<<+x"]) == "2\n1"

    def test_a_character_outside_the_command_set_does_nothing(self) -> None:
        r"""An unknown character inside the grid is a no-op.

        Every command is matched against a literal, and widening any of
        them makes some other character live.  ``X`` stands in for every
        non-command: crossing it changes neither tape nor heading.  The
        last grid is the sharpest -- were ``X`` to join ``"^v{}"``, the
        lookup would return ``-1``, and a beam heading ``-1`` still moves
        rightward but answers the mirror guards backwards.
        """
        assert run_and_capture(["\xff}oX+x", "     x"]) == "\x01"
        assert run_and_capture(["o+X>+x"]) == "1\n1"
        assert run_and_capture(["o+Xx", "   x"]) == "1"
        assert run_and_capture(["o+X)x", "   x"]) == "2"

    def test_a_horizontal_beam_turns_at_a_vertical_mirror(self) -> None:
        r"""``|`` sends a rightward beam back the way it came.

        ``d = 5 - d`` appears nowhere else, and the other ``|`` test
        approaches vertically, where the guard refuses.  Re-crossing the
        ``+`` on the way out is what makes the turn visible: a beam that
        carried on rightward would cross the two beyond it instead.
        """
        assert run_and_capture(["o+|++x"]) == "2"

    def test_a_downward_beam_passes_a_vertical_mirror(self) -> None:
        r"""``|`` refuses a vertical beam even when the cell is set.

        The guard is ``d > 1``; loosening it deflects a downward beam.
        The arm to the right of the mirror is what tells the two apart --
        with nothing there, both beams die on the same ``x``.
        """
        assert run_and_capture(["}o+v  ", "   |+x", "   x  "]) == "1"

    def test_a_leftward_beam_passes_a_horizontal_mirror(self) -> None:
        r"""``_`` and ``(`` take only *vertical* beams.

        The guard is ``d < 2``.  Widening it catches leftward beams, which
        the cage produces: ``{`` turns the beam left across the ``_`` and
        into the ``+`` beyond.  Were the ``_`` to deflect, the beam would
        bounce between it and the ``{`` forever.
        """
        assert run_and_capture(["x+_ o{", "     "]) == "1"

    def test_a_mirror_reads_the_value_not_the_written_flag(self) -> None:
        """A cell that was written *and* is zero does not deflect.

        Each tape cell carries a value and a flag saying it was written,
        and the mirrors must consult the value.  Reading the flag instead
        looks right everywhere a cell was incremented; ``,`` on an empty
        line writes a zero, which is the case that separates them.
        """

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
            run(["o,v", "  (", "  x"], io_obj, heading=3)
        assert io_obj.buf.getvalue() == "0"

    def test_byte_mode_prints_every_value(self) -> None:
        r"""Byte mode runs the characters together; it does not stop at one.

        Two written cells are needed to see it -- every other byte-mode
        grid here writes exactly one, where a dump that quit after the
        first character would look correct.
        """
        assert run_and_capture(["\xff}o+>+x", "      x"]) == "\x01\x01"

    def test_a_written_zero_still_prints(self) -> None:
        """Zero is a value; only *unwritten* cells are skipped.

        The dump keeps ``val >= 0``, which admits zero and drops the
        negatives.  The suite tested the negative side of that bound and
        never the zero on it.
        """
        assert run_and_capture(["o+-x"]) == "0"

    def test_a_split_beam_entered_leftward_leaves_vertically(self) -> None:
        r"""``*`` entered *leftward* sends its child up or down.

        The axis is ``2 * (1 - d // 2)``, and every other ``*`` here is
        entered rightward -- the one case where a wrong divisor gives the
        same answer as the right one.  Mirrors fold all four start
        headings onto one track, so the program is deterministic even
        though the split *direction* along the axis is drawn at random.
        """
        cage = ["  x/\\", "x+*{o|", "  x\\/"]
        for heading in range(4):
            assert run_and_capture(cage, heading=heading) == "1", heading

    def test_a_zero_cell_passes_the_other_conditional_mirror(self) -> None:
        r"""``)`` on a written zero: it does not deflect, and the guard holds.

        The companion to the ``(`` case above, and the one that pins the
        guard's *shape*.  ``,`` on an empty line writes a zero, so a beam
        arriving at ``)`` must carry straight on; joining the two
        conditions with ``or``, comparing the value the wrong way round,
        or reading the written-flag instead all deflect it into the second
        ``,``, which has no input left and raises.
        """

        class TestIO(IO):
            def __init__(self) -> None:
                self.buf = io.StringIO()
                self.reads = 0

            def input_str(self, _prompt: str = "Input: ") -> str:
                self.reads += 1
                if self.reads > 1:  # a deflected beam comes back for more
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
            run(["}o,)x", "    x"], io_obj, heading=3)
        assert io_obj.buf.getvalue() == "0"

    def test_two_lasers_run_in_turn(self) -> None:
        r"""``*`` leaves two live beams, and they alternate.

        With one laser the index arithmetic ``(ind + 1) % len(lsrs)`` is
        the identity, so nothing here distinguishes a step forward from a
        step back until a second beam exists.  The second grid adds a
        ``#``, so a scheduler that advanced by the wrong amount would
        defer the wrong beam's command.

        Both grids are symmetric about the ``*``: the split direction is
        drawn at random, and only arms that do the same work whichever way
        the draw goes make the program deterministic.  An asymmetric grid
        here passes most of the time and fails the rest, which is worse
        than not testing it.
        """
        assert run_and_capture([" +x", "o*+x", " +x"]) == "2"
        assert run_and_capture([" #+x ", "o*#+x", " #+x "]) == "1"

    def test_the_drawn_heading_is_one_of_four(self) -> None:
        r"""The initial draw is ``randbelow(4)``, not some wider range.

        Pinning the draw is the only way to see this: a fifth heading
        would be chosen one run in five, and because it falls through the
        movement chain it travels like ``3`` -- so the outputs it produces
        overlap the real ones and no grid separates them.

        The stub must read its *argument* rather than return a constant: a
        constant is returned whatever range is asked for, which hides the
        very widening this is checking.  Asking for the largest heading in
        whatever range the interpreter requests makes the bound exact, and
        ``\`` is what tells 3 from 4 -- it reverses ``(d + 2) % 4``, which
        is 1 for the real heading and 2 for a fifth one.
        """
        with patch("secrets.randbelow", side_effect=lambda n: n - 1):
            assert run_and_capture(["o\\ ", " +x"], heading=None) == "1"

    def test_the_split_direction_is_drawn_along_the_new_axis(self) -> None:
        r"""``*`` draws only *which way* along the perpendicular axis.

        The axis itself is arithmetic -- ``2 * (1 - d // 2)`` -- and the
        draw adds 0 or 1 to it.  Left and right are therefore headings 2
        and 3 for a vertical beam, and an axis computed even slightly
        differently would offer 3 and 4 instead: still a valid pair of
        moves, still overlapping the real ones, invisible to any grid.
        Pinning the draw to 0 asks for the *first* heading on the axis,
        which must be left, and the ``+`` on the left arm reports it.
        """
        cage = ["  x", "  +", "x+*x", "/ ^\\", "\\ o/", "  _"]
        with patch("secrets.randbelow", return_value=0):
            for heading in range(4):
                assert run_and_capture(cage, heading=heading) == "2", heading


class TestStepMachine:
    def test_snapshot_is_hashable_and_tracks_progress(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import _Machine

        machine = _Machine(["ÿ}o+x\n   x"], IO(), heading=3)
        before = machine.snapshot()
        hash(before)  # must not raise
        machine.step()
        assert machine.snapshot() != before
