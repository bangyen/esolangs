"""Unit tests for the Streetcode interpreter.

Streetcode is a 2D esolang where a car drives along two-way streets,
executing the instruction it passes over.  ``^``/``~`` increment/decrement
the CPth cell, ``=``/``_`` move CP right/left, ``I``/``O`` read/write the
CPth cell as a character, ``U`` turns the car around, ``;`` halts, and
space is a no-op.  See ``docs/streetcode.md`` for the spec-gap decisions
this interpreter makes (initial heading, "Nth register", the
drive-on-the-right geometry, and so on) -- these tests exercise and confirm
them, including all four of the wiki's worked examples.
"""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.streetcode import _Machine, run
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.vm import run_until_halt_or_cycle


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    """Run a Streetcode program (patching input) and return its stdout."""
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, io=IO())
    return buffer.getvalue()


class TestStreetcodeSingleCommands:
    """Each instruction in isolation."""

    def test_halt_immediately(self) -> None:
        assert run_and_capture(["C;"]) == ""

    def test_increment_then_output(self) -> None:
        assert run_and_capture(["C^O;"]) == chr(1)

    def test_decrement_below_zero_then_output_is_invalid(self) -> None:
        """A cell of -1 is a valid signed int, but not a valid code point."""
        with pytest.raises(HaltError):
            run(["C~O;"], io=IO())

    def test_decrement_then_increment_then_output(self) -> None:
        """~ and ^ both touch the same CPth cell, unbounded and signed."""
        assert run_and_capture(["C~^O;"]) == chr(0)

    def test_space_is_a_nop(self) -> None:
        """A space between C and O is skipped over; the cell is still 0."""
        assert run_and_capture(["C O;"]) == chr(0)

    def test_undefined_character_is_a_nop(self) -> None:
        """Box-drawing and other undefined characters act like space."""
        assert run_and_capture(["C#O;"]) == chr(0)

    def test_u_reverses_heading(self) -> None:
        """In a one-wide corridor -- narrower than any spec street, but
        tolerated -- a 'U' has no opposite lane to end in, so it turns the
        car around in place."""
        # Two rows so the car has room to move south from C before the U.
        machine = _Machine(["C", "U"], IO())
        assert machine.heading == "S"
        machine.step()  # 'C' nop; only non-backward neighbor is south
        assert (machine.row, machine.col) == (1, 0)
        machine.step()  # 'U': reverses heading to North in place, then drives
        assert (machine.row, machine.col, machine.heading) == (0, 0, "N")

    def test_u_on_a_two_way_street_ends_in_the_opposite_lane(self) -> None:
        """Streets are two wide and the car drives on the right, so after
        turning around it belongs in the lane now on its right: the U-turn
        ends there, and that lane cell is executed on the next step."""
        code = [
            "|  |",
            "|C |",
            "|  |",
            "|U^|",
            "|  |",
            "+--+",
        ]
        machine = _Machine(code, IO())
        # Southbound in the west lane (wall on the right), down to the U.
        for _ in range(2):
            machine.step()
        assert (machine.row, machine.col, machine.heading) == (3, 1, "S")
        machine.step()  # 'U': turn around, sliding east into the northbound lane
        assert (machine.row, machine.col, machine.heading) == (3, 2, "N")
        machine.step()  # the lane cell's '^' runs before the car moves on
        assert machine.cells[0] == 1
        assert (machine.row, machine.col, machine.heading) == (2, 2, "N")

    def test_u_in_place_would_leave_the_car_driving_on_the_left(self) -> None:
        """The reason the lane change is not optional: turned around in
        place, the car sits in the oncoming lane, and the right-hand hug
        then takes two right turns to get out of it -- ending up on the
        *original* heading one lane over, the U-turn cancelled.  Drive the
        same street to the U and confirm the car really is northbound in
        the east lane two steps later, not westbound and then southbound."""
        code = [
            "|  |",
            "|C |",
            "|  |",
            "|U |",
            "|  |",
            "+--+",
        ]
        machine = _Machine(code, IO())
        for _ in range(3):
            machine.step()
        headings = []
        for _ in range(3):
            machine.step()
            headings.append(machine.heading)
        assert headings == ["N", "N", "N"]
        assert machine.col == 2

    def test_cp_increment_and_decrement(self) -> None:
        """Move CP right onto a fresh cell, increment it, then move back."""
        assert run_and_capture(["C=^O_O;"]) == chr(1) + chr(0)


class TestStreetcodeHalt:
    def test_semicolon_halts_immediately(self) -> None:
        assert run_and_capture(["C;^O"]) == ""

    def test_program_without_semicolon_runs_until_dead_end(self) -> None:
        """No halt instruction: a straight dead-end corridor still stops."""
        assert run_and_capture(["C"]) == ""


class TestStreetcodeDeadEndsAndTurns:
    def test_single_cell_program_is_an_immediate_dead_end(self) -> None:
        """A lone C with nowhere to go halts without executing twice."""
        machine = _Machine(["C"], IO())
        assert not machine.halted
        machine.step()
        assert machine.halted

    def test_corridor_bends_naturally_without_a_u(self) -> None:
        """A single non-backward neighbor is just driven onto (rule 8)."""
        # Heading East with only one row (no north/south neighbors) and the
        # cell behind (West) out of bounds: forward is the only candidate,
        # so the car simply continues -- no ambiguous-turn choice is made.
        machine = _Machine(["CY"], IO())
        machine.heading = "E"
        machine.step()  # 'C' is a nop; the only non-backward neighbor is East
        assert (machine.row, machine.col, machine.heading) == (0, 1, "E")

    def test_dead_end_forces_a_u_turn(self) -> None:
        """A true cul-de-sac (no non-backward neighbor) reverses heading."""
        # C moves south onto 'X' (its only option); from there every
        # orthogonal neighbor except the way it came (North) is out of
        # bounds, so it must reverse fully around rather than halt.
        code = ["C", "X"]
        machine = _Machine(code, IO())
        machine.step()  # 'C': only non-backward neighbor is South
        assert (machine.row, machine.col, machine.heading) == (1, 0, "S")
        machine.step()  # 'X': true dead end -> reverses to North
        assert (machine.row, machine.col, machine.heading) == (0, 0, "N")
        assert not machine.halted


class TestStreetcodeAmbiguousTurns:
    """A real junction: ``_junction_kind`` fires and offers >= 2 options."""

    def _junction_code(self) -> list[str]:
        # A north-south corridor hugging a West wall (column 0), with a
        # branch peeling off to the East at row 2 and another at row 5 --
        # `+` at both of those rows, column 3, is exactly the far-side pair
        # `_junction_kind` requires for a 3-way junction (see its
        # docstring), while the near side (column 0) stays plain wall.
        return [
            "XC  ",
            "X   ",
            "X  +",
            "X   ",
            "X   ",
            "X  +",
        ]

    def _machine_at_junction(self) -> _Machine:
        machine = _Machine(self._junction_code(), IO())
        machine.row, machine.col, machine.heading = 1, 1, "S"
        return machine

    def test_leftmost_branch_taken_when_cell_is_zero(self) -> None:
        # If _junction_kind failed to detect the intersection here, plain
        # wall-following would hug the West wall and go straight South
        # instead -- landing East instead confirms the junction rule fired.
        machine = self._machine_at_junction()
        machine.step()  # cell is 0 -> leftmost of [E, S] = East
        assert (machine.row, machine.col, machine.heading) == (1, 2, "E")

    def test_second_leftmost_branch_taken_when_cell_is_nonzero(self) -> None:
        machine = self._machine_at_junction()
        machine.cells[0] = 1  # force the CPth cell nonzero before stepping
        machine.step()  # cell is nonzero -> second-leftmost of [E, S] = South
        assert (machine.row, machine.col, machine.heading) == (2, 1, "S")

    def test_plus_pair_with_a_wall_in_the_gap_is_not_a_mouth(self) -> None:
        """A `+` pair whose floor is not all open between them bounds no
        road: the far `+` is found, the gap check fails, and the scan
        stops rather than reporting a mouth through solid wall."""
        machine = _Machine(["C       ", "-+ |+   ", "        "], IO())
        machine.row, machine.col, machine.heading = 0, 0, "E"
        assert machine._road_mouth("E", "S") is None  # noqa: SLF001

    def test_four_way_junction_detects_4(self) -> None:
        """Mouths on both sides at once, road continuing ahead: 4 ways."""
        machine = _Machine([" C ", "+ +", "   ", "+ +", " | "], IO())
        machine.row, machine.col, machine.heading = 0, 1, "S"
        assert machine._junction_kind("S") == 4  # noqa: SLF001

    def test_t_junction_detects_3(self) -> None:
        """Mouths on both sides with straight ahead blocked: a T whose
        crossbar the car is driving into, still three ways."""
        machine = _Machine([" C ", "+|+", "   ", "+ +", " | "], IO())
        machine.row, machine.col, machine.heading = 0, 1, "S"
        assert machine._junction_kind("S") == 3  # noqa: SLF001

    # A mouth whose gap opens ahead of the car (its near ``+`` sighted at
    # depth 0 or +1) and whose far ``+`` has open interior beneath it (so
    # ``_lane_bounded`` is False and no merge latch is taken): the chosen
    # turn's next cell is still the wall the gap opens through, and the
    # turn must wait until the car is level with the gap.  Before the
    # openness guard in ``_choose_heading``, the car turned immediately,
    # drove *inside* the wall, and wall-followed around the outside of the
    # lower room forever.
    _EARLY_MOUTH = [
        "+---------+",
        "|         |",
        "|C^      ;|",
        "+--+  ++--+",
        "   |      |",
        "   |;     |",
        "   +------+",
    ]

    def test_early_sighted_mouth_defers_the_turn_to_the_gap(self) -> None:
        machine = _Machine(self._EARLY_MOUTH, IO())
        positions = [(machine.row, machine.col)]
        for _ in range(7):
            machine.step()
            positions.append((machine.row, machine.col))
        # The `^` makes the cell nonzero, so the junction chooses the South
        # branch -- but the car carries on to the gap at column 4 before
        # turning, never occupying a wall cell.
        assert positions == [
            (2, 1),
            (2, 2),
            (2, 3),
            (2, 4),
            (3, 4),
            (4, 4),
            (5, 4),
            (5, 4),
        ]
        assert machine.halted

    def test_early_sighted_mouth_still_declines_on_zero(self) -> None:
        code = [line.replace("^", " ") for line in self._EARLY_MOUTH]
        machine = _Machine(code, IO())
        for _ in range(9):
            machine.step()
        assert machine.halted
        assert (machine.row, machine.col) == (2, 9)


class TestStreetcodeLaneMerge:
    """A genuinely multi-cell-wide junction: turning must land in the new
    road's right-hand lane, not just the first open cell (see
    ``docs/streetcode.md`` for the derivation of this trace)."""

    def _lane_merge_code(self) -> list[str]:
        # A vertical 2-wide corridor (columns 1-2) hugging a West wall
        # (column 0), with two branches peeling off East at rows 1 and 4 --
        # each with a genuine wall arm (`--`) bounding a real 2-row-tall
        # east-west corridor between them (rows 2-3).
        return [
            "|C |",
            "|  +--",
            "|",
            "|",
            "|  +--",
            "|  |",
        ]

    def test_merge_lands_in_the_right_hand_lane(self) -> None:
        # Ground-truth trace (user-confirmed, see docs/streetcode.md):
        # the car hugs column 1 south through rows 0-3 (its own lane),
        # then turns East at row 3 -- the right-hand lane of the new
        # east-west road relative to heading East -- not row 2, and not
        # immediately upon first detecting the junction at row 0.
        machine = _Machine(self._lane_merge_code(), IO())
        positions = [(machine.row, machine.col)]
        for _ in range(6):
            machine.step()
            positions.append((machine.row, machine.col))
        assert positions == [
            (0, 1),
            (1, 1),
            (2, 1),
            (3, 1),
            (3, 2),
            (3, 3),
            (3, 4),
        ]

    def test_diverting_before_the_target_abandons_the_merge_latch(self) -> None:
        """A 'U' during the phase-1 approach must not wedge the latch open.

        Without invalidating ``_merge_target`` on a heading change, the
        latch would wait forever for a (row, col) the car no longer visits
        (it U-turned away), permanently disabling junction detection for
        the rest of the run.
        """
        code = [
            "|C |",
            "|  +--",
            "|U",
            "|",
            "|  +--",
            "|  |",
        ]
        machine = _Machine(code, IO())
        machine.step()  # 'C' -> (1,1), latches _merge_target for (3,1)
        assert machine._merge_target is not None  # noqa: SLF001
        machine.step()  # -> (2,1), still approaching
        machine.step()  # 'U' at (2,1) flips heading to North before choosing
        assert machine._merge_target is None  # noqa: SLF001

    def test_wall_at_the_turn_destination_falls_back_to_plain_rules(self) -> None:
        """The phase-1 turn must not step onto a wall that appears at the
        latched target's chosen heading -- it should fall back to ordinary
        wall-following instead of blindly trusting the stale latch."""
        machine = _Machine(self._lane_merge_code(), IO())
        machine.row, machine.col, machine.heading = 3, 1, "S"
        machine._merge_target = (3, 1, "E", "S")  # noqa: SLF001
        row = machine.grid[3]
        machine.grid[3] = row[:2] + "+" + row[3:]  # wall directly East
        heading = machine._choose_heading()  # noqa: SLF001
        assert heading != "E"
        assert machine._merge_target is None  # noqa: SLF001

    def test_wall_after_merge_turn_falls_back_to_plain_rules(self) -> None:
        """The phase-2 straight-through suppression must not drive through
        a wall that appears directly ahead while merging out."""
        machine = _Machine(self._lane_merge_code(), IO())
        machine.row, machine.col, machine.heading = 3, 2, "E"
        machine._merging_heading = "E"  # noqa: SLF001
        row = machine.grid[3]
        machine.grid[3] = row[:3] + "+" + row[4:]  # wall directly ahead
        heading = machine._choose_heading()  # noqa: SLF001
        assert heading != "E"

    def test_merge_target_reread_can_carry_straight_on(self) -> None:
        """The branch is re-read at the latched turn cell, not trusted from
        latch time: a cell that went nonzero while approaching reverses the
        decision and the car carries straight on, abandoning the merge."""
        machine = _Machine(self._lane_merge_code(), IO())
        machine.row, machine.col, machine.heading = 3, 1, "S"
        machine._merge_target = (3, 1, "E", "S")  # noqa: SLF001
        machine.cells[0] = 1  # latch was taken under cell == 0
        heading = machine._choose_heading()  # noqa: SLF001
        assert heading == "S"
        assert machine._merging_heading is None  # noqa: SLF001

    def test_wall_mid_approach_abandons_the_merge_latch(self) -> None:
        """A wall appearing straight ahead while still approaching the
        latched lane drops the latch, like a heading change does: the
        latch must not wait forever for a target it can no longer reach."""
        machine = _Machine(self._lane_merge_code(), IO())
        machine.row, machine.col, machine.heading = 1, 1, "S"
        machine._merge_target = (3, 1, "E", "S")  # noqa: SLF001
        row = machine.grid[2]
        machine.grid[2] = row[:1] + "+" + row[2:]  # wall directly ahead
        heading = machine._choose_heading()  # noqa: SLF001
        assert machine._merge_target is None  # noqa: SLF001
        assert heading == "E"  # falls back to plain wall-following

    def test_turn_lands_in_the_lane_without_an_approach(self) -> None:
        """When the junction fires while the car already sits in the new
        road's right-hand lane (a mouth whose near ``+`` is one cell
        behind, near == -1), there is nothing to drive to: turn now."""
        machine = _Machine(["|+  ", "  C ", "    ", "|+  "], IO())
        machine.row, machine.col, machine.heading = 1, 2, "S"
        machine.cells[0] = 1  # nonzero -> second-leftmost of [S, W] = West
        heading = machine._choose_heading()  # noqa: SLF001
        assert heading == "W"
        assert machine._merge_target is None  # noqa: SLF001

    def test_four_way_junction_also_merges(self) -> None:
        """A four-way junction (``+`` at all four detection-window corners,
        each with genuine wall arms) exercises ``_junction_kind``'s other
        branch through the same lane-merge machinery. This pins current
        behavior on the four-way corner pattern -- unlike the three-way
        case in ``test_merge_lands_in_the_right_hand_lane``, no hand-drawn,
        user-confirmed trace exists for a four-way junction (see the "Still
        open" section of ``docs/streetcode.md``)."""
        code = [
            " |C |",
            "-+  +--",
            " |",
            " |",
            "-+  +--",
            " |  |",
        ]
        machine = _Machine(code, IO())
        positions = [(machine.row, machine.col)]
        for _ in range(7):
            machine.step()
            positions.append((machine.row, machine.col))
        assert positions == [
            (0, 2),
            (1, 2),
            (2, 2),
            (3, 2),
            (3, 3),
            (3, 4),
            (3, 5),
            (3, 6),
        ]


class TestStreetcodeIO:
    def test_input_echoed_via_cpth_cell(self) -> None:
        assert run_and_capture(["CIO;"], inputs=["X"]) == "X"

    def test_input_reads_only_first_character_of_line(self) -> None:
        assert run_and_capture(["CIO;"], inputs=["hello"]) == "h"

    def test_empty_input_line_reads_zero(self) -> None:
        assert run_and_capture(["CIO;"], inputs=[""]) == chr(0)

    def test_exhausted_input_raises_eof(self) -> None:
        machine = _Machine(["CI;"], ScriptedIO(""))
        machine.step()  # 'C'
        with pytest.raises(EOFError):
            machine.step()  # 'I' with no input left at all


class TestStreetcodeCPBounds:
    def test_cp_decrement_below_zero_halts(self) -> None:
        with pytest.raises(HaltError):
            run(["C_;"], io=IO())

    def test_cp_can_move_right_and_back_to_zero(self) -> None:
        assert run_and_capture(["C=_^O;"]) == chr(1)

    def test_output_of_out_of_range_cell_halts(self) -> None:
        """A cell value that isn't a valid code point is invalid, not a crash."""
        with pytest.raises(HaltError):
            run(["C~~~~~~~~~~~~~O;"], io=IO())  # cell reaches a large negative


class TestStreetcodeMalformedPrograms:
    def test_empty_program_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            run([], io=IO())

    def test_blank_only_program_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            run(["   ", ""], io=IO())

    def test_no_car_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="exactly one C"):
            run(["   ", " ; "], io=IO())

    def test_multiple_cars_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="exactly one C"):
            run(["C  ", "  C"], io=IO())


class TestStreetcodeWikiExamples:
    """The wiki's own worked examples (interior grid, borders stripped)."""

    def test_whole_right_hand_side_example(self) -> None:
        """``CIO;`` echoes one input character then halts."""
        assert run_and_capture(["CIO;"], inputs=["Q"]) == "Q"

    def test_infinite_cat_example(self) -> None:
        """The U-turn cat echoes input characters in order, then hangs on EOF.

        The program never halts on its own (it is a genuine infinite cat),
        so exhausting the scripted input is what stops the run, via
        :class:`EOFError` on the next ``I``.  Output collected before that
        point must be exactly the input, echoed in order with nothing
        dropped, garbled, or reordered.
        """
        code = ["UOI ", "CIOU"]
        scripted = ScriptedIO("A\nB\nC")
        with pytest.raises(EOFError):
            run(code, io=scripted)
        assert scripted.getvalue() == "ABC"

    def test_infinite_loop_example_hangs(self) -> None:
        """The ambiguous-turn infinite loop is a genuine cycle, not a halt."""
        code = [
            "+-------+",
            "|       |",
            "|C      |",
            "++  ++  |",
            " |  ++  |",
            " |      |",
            " |      |",
            " +------+",
        ]
        machine = _Machine(code, IO())
        assert run_until_halt_or_cycle(machine) is False

    def test_infinite_loop_example_produces_no_output(self) -> None:
        code = [
            "+-------+",
            "|       |",
            "|C      |",
            "++  ++  |",
            " |  ++  |",
            " |      |",
            " |      |",
            " +------+",
        ]
        buffer = io.StringIO()
        machine = _Machine(code, IO())
        with redirect_stdout(buffer):
            for _ in range(500):
                if machine.halted:
                    break
                machine.step()
        assert buffer.getvalue() == ""
        assert not machine.halted  # confirmed a genuine cycle above

    def test_infinite_loop_example_traces_its_17_cell_lap(self) -> None:
        """The loop's lap, pinned cell by cell against a hand-checked trace.

        The car's cell is 0 for the whole run (nothing in this program ever
        increments), so at every junction it takes the leftmost road.  From
        ``C`` it declines the side road opening south, runs the top corridor
        east, follows the wall down and back west along row 5, turns north up
        column 3 -- and meets that same junction again head-on, driving out
        through the gap between the two ``+`` at ``(3,1)`` and ``(3,4)``.
        There it merges across to the far lane of the corridor it is joining
        before turning left, reaching ``(1,3)`` and running west along row 1
        back to ``C``, where it corners south-then-east and repeats.
        """
        code = [
            "+-------+",
            "|       |",
            "|C      |",
            "++  ++  |",
            " |  ++  |",
            " |      |",
            " |      |",
            " +------+",
        ]
        lap = [
            (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6),
            (3, 6), (4, 6), (5, 6),
            (5, 5), (5, 4), (5, 3),
            (4, 3), (3, 3), (2, 3), (1, 3),
            (1, 2), (1, 1),
        ]  # fmt: skip
        machine = _Machine(code, IO())
        path = []
        for _ in range(len(lap) * 3):
            path.append((machine.row, machine.col))
            machine.step()
        # The lap repeats exactly: same cells, same order, indefinitely.
        assert path == lap * 3
        assert len(set(lap)) == 17  # (2, 3) is driven through twice per lap

    def test_infinite_cat_for_single_characters_example(self) -> None:
        """The wiki's rhetorical "Why wouldn't this be a cat?" -- it is one.

        This diagram's outer ring loops back through the same ``I``/``O``
        pair (never reaching the inner ``+-+IO++``/``|OI++`` branch under
        plain wall-following), but it still echoes input characters in
        order with nothing dropped or garbled, hanging on exhausted input
        like the other infinite-cat example rather than halting cleanly.
        """
        code = [
            "+--------+",
            "|        |",
            "|C^      |",
            "+-+IO++  |",
            "  |OI++  |",
            "  |      |",
            "  |      |",
            "  +------+",
        ]
        io_obj = ScriptedIO("A\nB")
        with pytest.raises(EOFError):
            run(code, io=io_obj)
        assert io_obj.getvalue() == "AB"


class TestStreetcodeStepMachine:
    def test_step_tracks_position_and_heading(self) -> None:
        machine = _Machine(["CIO;"], ScriptedIO("Z"))
        # A single row: wall South (out of bounds) and open East at 'C'
        # resolves the initial heading straight to East, no dead end.
        assert (machine.row, machine.col, machine.heading) == (0, 0, "E")
        machine.step()  # 'C' is a nop; drives onto 'I'
        assert (machine.row, machine.col) == (0, 1)

    def test_snapshot_includes_input_cursor(self) -> None:
        machine = _Machine(["CIO;"], ScriptedIO("A"))
        before = machine.snapshot()
        machine.step()  # 'C'
        machine.step()  # 'I' consumes the input line
        after = machine.snapshot()
        assert before != after
        assert machine.io.position() == 1

    def test_halting_program_is_detected_as_halted(self) -> None:
        assert run_until_halt_or_cycle(_Machine(["C;"], IO())) is True

    def test_step_on_an_already_halted_machine_is_a_no_op(self) -> None:
        machine = _Machine(["C;"], IO())
        machine.step()  # 'C', moves onto ';'
        machine.step()  # ';' halts
        assert machine.halted
        before = machine.snapshot()
        machine.step()  # calling step() again must not raise or move further
        assert machine.snapshot() == before
