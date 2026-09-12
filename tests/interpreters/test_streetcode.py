r"""Unit tests for the Streetcode interpreter."""

import io
import re
from contextlib import redirect_stdout
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.streetcode import (
    _NO_LATCHES,
    _VOID,
    _WALLS,
    _Car,
    _choose_heading,
    _crossing_mouth,
    _drive,
    _Grid,
    _junction_choices,
    _junction_kind,
    _junction_shape,
    _lane_bounded,
    _Latches,
    _lawful_turn,
    _left,
    _Machine,
    _matches,
    _Merge,
    _open_toward,
    _plus_dist,
    _ReachableCell,
    _right,
    _road_mouth,
    _rotate,
    _rotations,
    _State,
    _turn_of,
    run,
)
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.vm import _StepMachine, run_until_halt_or_cycle
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def street(instructions: str) -> list[str]:
    r"""Box a one-line program into a street, the way the wiki draws one."""
    wall = "+" + "-" * len(instructions) + "+"
    return [wall, "|" + " " * len(instructions) + "|", f"|{instructions}|", wall]


def machine_unvalidated(code: list[str]) -> _Machine:
    r"""Build a ``_Machine`` from a wall-shape fixture, skipping validation."""
    with patch.object(_Machine, "_validate", lambda *_: None):
        return _Machine(code, IO())


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    r"""Run a Streetcode program and return its stdout."""
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


def run_street(instructions: str, inputs: list[str] | None = None) -> str:
    r"""Run a one-line program inside a proper two-lane street."""
    return run_and_capture(street(instructions), inputs)


class TestStreetcodeSingleCommands:
    r"""Each instruction in isolation."""

    def test_halt_immediately(self) -> None:
        assert run_street("C;") == ""

    def test_increment_then_output(self) -> None:
        assert run_street("C^O;") == chr(1)

    def test_decrement_below_zero_then_output_is_invalid(self) -> None:
        r"""A cell of -1 is a valid signed int, but not a valid code point."""
        with pytest.raises(HaltError):
            run(["C~O;"], io=IO())

    def test_decrement_then_increment_then_output(self) -> None:
        r"""~ and ^ both touch the same CPth cell, unbounded and signed."""
        assert run_street("C~^O;") == chr(0)

    def test_space_is_a_nop(self) -> None:
        r"""A space between C and O is skipped over; the cell is still 0."""
        assert run_street("C O;") == chr(0)

    def test_undefined_character_is_a_nop(self) -> None:
        r"""Box-drawing and other undefined characters act like space."""
        assert run_street("C#O;") == chr(0)

    def test_u_without_an_opposite_lane_is_invalid(self) -> None:
        r"""A one-wide corridor is narrower than the spec's two-character."""
        # Two rows so the car has room.
        machine = _Machine(["C", "U"], IO())
        assert machine.heading == "S"
        machine.step()  # 'C' nop; only non-backward.
        assert (machine.row, machine.col) == (1, 0)
        with pytest.raises(HaltError):
            machine.step()  # 'U' with no lane to the new.

    def test_u_on_a_two_way_street_ends_in_the_opposite_lane(self) -> None:
        r"""Streets are two wide and the car drives on the right, so after."""
        code = [
            "|  |",
            "|C |",
            "|  |",
            "|U^|",
            "|  |",
            "+--+",
        ]
        machine = machine_unvalidated(code)
        # Southbound in the west lane.
        for _ in range(2):
            machine.step()
        assert (machine.row, machine.col, machine.heading) == (3, 1, "S")
        machine.step()  # 'U': turn around, sliding.
        assert (machine.row, machine.col, machine.heading) == (3, 2, "N")
        machine.step()  # the lane cell's '^' runs.
        assert machine.cells[0] == 1
        assert (machine.row, machine.col, machine.heading) == (2, 2, "N")

    def test_u_in_place_would_leave_the_car_driving_on_the_left(self) -> None:
        r"""The reason the lane change is not optional: turned around in place,."""
        code = [
            "|  |",
            "|C |",
            "|  |",
            "|U |",
            "|  |",
            "+--+",
        ]
        machine = machine_unvalidated(code)
        for _ in range(3):
            machine.step()
        headings = []
        for _ in range(3):
            machine.step()
            headings.append(machine.heading)
        assert headings == ["N", "N", "N"]
        assert machine.col == 2

    def test_cp_increment_and_decrement(self) -> None:
        r"""Move CP right onto a fresh cell, increment it, then move back."""
        assert run_street("C=^O_O;") == chr(1) + chr(0)


class TestStreetcodeHalt:
    def test_semicolon_halts_immediately(self) -> None:
        assert run_street("C;^O") == ""

    def test_program_without_semicolon_runs_until_dead_end(self) -> None:
        r"""No halt instruction: a dead-end corridor still stops."""
        assert run_and_capture(["C"]) == ""


class TestStreetcodeDeadEndsAndTurns:
    def test_single_cell_program_is_an_immediate_dead_end(self) -> None:
        r"""A lone C with nowhere to go halts without executing twice."""
        machine = _Machine(["C"], IO())
        assert not machine.halted
        machine.step()
        assert machine.halted

    def test_corridor_bends_naturally_without_a_u(self) -> None:
        r"""A single non-backward neighbor is just driven onto (rule 8)."""
        # Heading East with only one.
        # cell behind (West) out of.
        # so the car simply continues.
        machine = _Machine(["CY"], IO())
        machine.place(machine.row, machine.col, "E")
        machine.step()  # 'C' is a nop; the only.
        assert (machine.row, machine.col, machine.heading) == (0, 1, "E")

    def test_dead_end_forces_a_u_turn(self) -> None:
        r"""A true cul-de-sac (no non-backward neighbor) reverses heading."""
        # C moves south onto 'X' (its.
        # orthogonal neighbor except.
        # bounds, so it must reverse.
        code = ["C", "X"]
        machine = _Machine(code, IO())
        machine.step()  # 'C': only non-backward.
        assert (machine.row, machine.col, machine.heading) == (1, 0, "S")
        machine.step()  # 'X': true dead end ->.
        assert (machine.row, machine.col, machine.heading) == (0, 0, "N")
        assert not machine.halted


class TestStreetcodeAmbiguousTurns:
    r"""A real junction: ``_junction_kind`` fires and offers >= 2 options."""

    def _junction_code(self) -> list[str]:
        # A north-south corridor.
        # branch peeling off to the.
        # `+` at both of those rows,.
        # `_junction_kind` requires for.
        # docstring), while the near.
        return [
            "XC  ",
            "X   ",
            "X  +",
            "X   ",
            "X   ",
            "X  +",
        ]

    def _machine_at_junction(self) -> _Machine:
        machine = machine_unvalidated(self._junction_code())
        machine.place(1, 1, "S")
        return machine

    def test_leftmost_branch_taken_when_cell_is_zero(self) -> None:
        # If _junction_kind failed to.
        # wall-following would hug the.
        # instead -- landing East.
        machine = self._machine_at_junction()
        machine.step()  # cell is 0 -> leftmost of [E,.
        assert (machine.row, machine.col, machine.heading) == (1, 2, "E")

    def test_second_leftmost_branch_taken_when_cell_is_nonzero(self) -> None:
        machine = self._machine_at_junction()
        machine.cells[0] = 1  # force the CPth cell nonzero.
        machine.step()  # cell is nonzero ->.
        assert (machine.row, machine.col, machine.heading) == (2, 1, "S")

    def test_plus_pair_with_a_wall_in_the_gap_is_not_a_mouth(self) -> None:
        r"""A `+` pair whose floor is not all open between them bounds no road:."""
        grid = _Grid(["C       ", "-+ |+   ", "        "])
        assert _road_mouth(grid, _Car(0, 0, "E"), "S") is None

    def test_four_way_junction_detects_4(self) -> None:
        r"""Mouths on both sides at once, road continuing ahead: 4 ways."""
        grid = _Grid([" C ", "+ +", "   ", "+ +", " | "])
        assert _junction_shape(grid, _Car(0, 1, "S")) == 4

    def test_t_junction_detects_3(self) -> None:
        r"""Mouths on both sides with straight ahead blocked: a T whose."""
        grid = _Grid([" C ", "+|+", "   ", "+ +", " | "])
        assert _junction_shape(grid, _Car(0, 1, "S")) == 3

    def test_one_mouth_with_road_ahead_detects_3(self) -> None:
        r"""A branch to *one* side, road continuing ahead: three ways."""
        left_only = _Grid([" C ", "+ +", "  |", "+ +", " | "])
        right_only = _Grid([" C ", "+ +", "|  ", "+ +", " | "])
        assert _junction_shape(left_only, _Car(0, 1, "S")) == 3
        assert _junction_shape(right_only, _Car(0, 1, "S")) == 3

    def test_one_mouth_with_the_road_ahead_blocked_is_no_junction(self) -> None:
        r"""One branch and nowhere to go straight is not a junction at all."""
        left_only = _Grid([" C ", "+|+", "  |", "+ +", " | "])
        right_only = _Grid([" C ", "+|+", "|  ", "+ +", " | "])
        assert _junction_shape(left_only, _Car(0, 1, "S")) == 0
        assert _junction_shape(right_only, _Car(0, 1, "S")) == 0

    def test_a_plain_corridor_is_no_junction(self) -> None:
        r"""No mouth on either side, and not driving out through one."""
        grid = _Grid([" C ", "| |", "| |", "| |", " | "])
        car = _Car(0, 1, "S")
        assert not _crossing_mouth(grid, car)
        assert _junction_shape(grid, car) == 0

    def test_turn_into_the_oncoming_lane_is_not_a_road(self) -> None:
        r"""A turn whose destination has the wall on its left and open road on."""
        grid = _Grid(self._counting_loop_code())
        car = _Car(5, 9, "E")
        # South from (5,9) enters the.
        assert not _lawful_turn(grid, car, "S")
        # North keeps that wall on the.
        assert _lawful_turn(grid, car, "N")

    def test_narrow_arms_are_not_roads(self) -> None:
        r"""The same shape is not a junction when its arms are one cell:."""
        grid = _Grid([" C ", "+ +", "   ", "+ +", " | "])
        assert _junction_kind(grid, _Car(0, 1, "S")) == 0

    def test_a_side_road_with_walls_past_its_plus_pair_is_lane_bounded(
        self,
    ) -> None:
        r"""``_lane_bounded`` reads one cell *past* each ``+``, further out."""
        bounded = _Grid(["        ", "C       ", "-+  +---", " |  |   ", " |  |   "])
        bare = _Grid(["        ", "C       ", "-+  +---", "        ", "        "])
        car = _Car(1, 0, "E")
        mouth = _road_mouth(bounded, car, "S")
        assert mouth is not None
        assert _road_mouth(bare, car, "S") == mouth, "the mouths must match"
        assert _lane_bounded(bounded, car, "S", mouth)
        assert not _lane_bounded(bare, car, "S", mouth)

    def test_every_road_a_junction_offers_is_open_ahead(self) -> None:
        r"""A junction never offers a road the car cannot step onto."""
        root = Path(__file__).resolve().parents[2]
        for path in (
            "tests/fixtures/streetcode_hello.txt",
            "examples/boolean/streetcode.txt",
        ):
            code = (root / path).read_text().split("\n")
            if code and code[-1] == "":
                code = code[:-1]
            machine = _Machine(code, IO())
            assert machine._graph is not None  # noqa: SLF001
            for state in machine._graph:  # noqa: SLF001
                car = _Car(state.row, state.col, state.heading)
                for road in _junction_choices(machine.grid, car):
                    assert _open_toward(machine.grid, car, road), (path, state, road)

    def test_the_examples_reach_exactly_these_drive_states(self) -> None:
        r"""The size of each example's drive graph is pinned."""
        root = Path(__file__).resolve().parents[2]
        for path, expected in (
            ("tests/fixtures/streetcode_hello.txt", 384),
            ("examples/boolean/streetcode.txt", 268),
        ):
            code = (root / path).read_text().split("\n")
            if code and code[-1] == "":
                code = code[:-1]
            machine = _Machine(code, IO())
            assert machine._graph is not None  # noqa: SLF001
            assert len(machine._graph) == expected, path  # noqa: SLF001

    # A mouth whose gap opens ahead.
    # depth 0 or +1) and whose far.
    # ``_lane_bounded`` is False.
    # turn's next cell is still the.
    # turn must wait until the car.
    # openness guard in.
    # drove *inside* the wall, and.
    # lower room forever.
    def _counting_loop_code(self) -> list[str]:
        r"""A hand-written counting loop: nine laps of an island, then out."""
        return [
            "+------------+",
            "|            |",
            "|C^        O;|",
            "+--+  ++  +--+",
            "   |      |",
            "   | ^_~ =|",
            "   | ^++= |",
            "   |^^++^U|",
            "   |^^^^^=|",
            "   |^^^^^^|",
            "   +------+",
        ]

    def _early_mouth_code(self) -> list[str]:
        return [
            "+---------+",
            "|         |",
            "|C^      ;|",
            "+--+  ++--+",
            "   |      |",
            "   |;     |",
            "   +------+",
        ]

    def test_early_sighted_mouth_defers_the_turn_to_the_gap(self) -> None:
        machine = _Machine(self._early_mouth_code(), IO())
        positions = [(machine.row, machine.col)]
        for _ in range(7):
            machine.step()
            positions.append((machine.row, machine.col))
        # The `^` makes the cell.
        # branch -- but the car carries.
        # turning, never occupying a.
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
        code = [line.replace("^", " ") for line in self._early_mouth_code()]
        machine = _Machine(code, IO())
        for _ in range(9):
            machine.step()
        assert machine.halted
        assert (machine.row, machine.col) == (2, 9)


class TestStreetcodeCrossingMouthDecision:
    r"""A head-on junction decides at the mouth, not at the far lane."""

    def _code(self) -> list[str]:
        r"""Two rooms of a folded corridor, the shape a width-6 fold draws."""
        return [
            "+----+",
            "|    |",
            "|    |",
            "+-+  |",
            "|    |",
            "|C ^ |",
            "+-+  |",
            "|;   |",
            "|    |",
            "+----+",
        ]

    def test_the_instruction_on_the_way_out_does_not_change_the_road(
        self,
    ) -> None:
        r"""The car climbs the road it chose instead of orbiting the tip."""
        machine = _Machine(self._code(), IO())
        seen: set[tuple[int, int]] = set()
        for _ in range(400):
            seen.add((machine.row, machine.col))
            machine.step()
            if machine.halted:
                break
        # The chosen road runs North up.
        # and the car goes on to reach.
        # leaves the six cells around.
        assert (1, 4) in seen, sorted(seen)
        assert machine.halted

    def test_a_detected_but_unreachable_road_defers_the_crossing(self) -> None:
        r"""A crossing does not offer the oncoming lane in a closed road's."""
        # A generated boolean program.
        # street whose leaf row carries.
        # sights the next fork while.
        # fragments of this shape do.
        # their own, which is why the.
        # program rather than a.
        from esolangs.tools.boolean import streetcode as gen

        machine = _Machine(gen("00110100").split("\n"), ScriptedIO("1\n0\n1\n"))
        grid = machine.grid
        hits = []
        for _ in range(2000):
            if machine.halted:
                break
            car = _Car(machine.row, machine.col, machine.heading)
            heading = car.heading
            if _crossing_mouth(grid, car):
                blocked = any(
                    _road_mouth(grid, car, side) is not None
                    and not _open_toward(grid, car, side)
                    for side in (_left(heading), _right(heading))
                )
                if blocked:
                    hits.append((car.row, car.col, _junction_choices(grid, car)))
            machine.step()
        # the case has to actually.
        assert hits, "no crossing sighted an unreachable road"
        # and wherever it does, the.
        # out with whatever else.
        assert all(choices == [] for _, _, choices in hits), hits


class TestStreetcodeLaneMerge:
    r"""A genuinely multi-cell-wide junction: turning must land in the new."""

    def _lane_merge_code(self) -> list[str]:
        # A vertical 2-wide corridor.
        # (column 0), with two branches.
        # each with a genuine wall arm.
        # east-west corridor between.
        return [
            "|C |",
            "|  +--",
            "|",
            "|",
            "|  +--",
            "|  |",
        ]

    def test_merge_lands_in_the_right_hand_lane(self) -> None:
        # Ground-truth trace.
        # the car hugs column 1 south.
        # then turns East at row 3 --.
        # east-west road relative to.
        # immediately upon first.
        machine = machine_unvalidated(self._lane_merge_code())
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
        r"""A 'U' during the phase-1 approach must not wedge the latch open."""
        code = [
            "|C  |",
            "|   |",
            "|   +---",
            "|       ",
            "|U      ",
            "|   +---",
            "|   |",
            "|   |",
        ]
        machine = machine_unvalidated(code)
        for _ in range(4):
            machine.step()  # down the west lane; the latch.
        assert machine._state.latches.merge is not None  # noqa: SLF001
        machine.step()  # 'U' at (4,1): turns around.
        assert machine._state.latches.merge is None  # noqa: SLF001

    def test_wall_at_the_turn_destination_falls_back_to_plain_rules(self) -> None:
        r"""The phase-1 turn must not step onto a wall that appears at the."""
        grid = _Grid(self._lane_merge_code())
        row = grid[3]
        grid[3] = row[:2] + "+" + row[3:]  # wall directly East.
        latches = _NO_LATCHES._replace(merge=_Merge(3, 1, "left", "S", crossing=False))
        steer = _choose_heading(grid, _Car(3, 1, "S"), latches, 0, 0)
        assert steer is not None
        assert steer.heading != "E"
        assert steer.latches.merge is None

    def test_wall_after_merge_turn_falls_back_to_plain_rules(self) -> None:
        r"""The phase-2 straight-through suppression must not drive through a."""
        grid = _Grid(self._lane_merge_code())
        row = grid[3]
        grid[3] = row[:3] + "+" + row[4:]  # wall directly ahead.
        latches = _NO_LATCHES._replace(merging_heading="E")
        steer = _choose_heading(grid, _Car(3, 2, "E"), latches, 0, 0)
        assert steer is not None
        assert steer.heading != "E"

    def test_merge_target_reread_can_carry_straight_on(self) -> None:
        r"""The branch is re-read at the latched turn cell, not trusted from."""
        grid = _Grid(self._lane_merge_code())
        latches = _NO_LATCHES._replace(merge=_Merge(3, 1, "left", "S", crossing=False))
        # 1 = the cell as the approach.
        # the latch was taken under.
        steer = _choose_heading(grid, _Car(3, 1, "S"), latches, 1, 1)
        assert steer is not None
        assert steer.heading == "S"
        assert steer.latches.merging_heading is None

    def test_wall_mid_approach_abandons_the_merge_latch(self) -> None:
        r"""A wall appearing straight ahead while still approaching the latched."""
        grid = _Grid(self._lane_merge_code())
        row = grid[2]
        grid[2] = row[:1] + "+" + row[2:]  # wall directly ahead.
        latches = _NO_LATCHES._replace(merge=_Merge(3, 1, "left", "S", crossing=False))
        steer = _choose_heading(grid, _Car(1, 1, "S"), latches, 0, 0)
        assert steer is not None
        assert steer.latches.merge is None
        assert steer.heading == "E"  # falls back to plain.

    def test_a_merge_recovers_the_heading_it_turns_to(self) -> None:
        r"""``_Merge`` stores the turn; the destination is derived from it."""
        for heading in ("N", "E", "S", "W"):
            left = _Merge(0, 0, "left", heading, crossing=False)
            right = _Merge(0, 0, "right", heading, crossing=False)
            assert left.new_heading == _left(heading)
            assert right.new_heading == _right(heading)

    def test_a_merge_turn_is_only_ever_a_left_or_a_right(self) -> None:
        r"""``_turn_of`` refuses a straight-ahead or reversing "turn"."""
        assert _turn_of("S", "E") == "left"
        assert _turn_of("S", "W") == "right"
        for impossible in ("S", "N"):  # straight ahead, and the.
            with pytest.raises(AssertionError, match="neither a left nor a right"):
                _turn_of("S", impossible)

    def test_turn_lands_in_the_lane_without_an_approach(self) -> None:
        r"""When the junction fires while the car already sits in the new."""
        grid = _Grid(["|+  ", "  C ", "    ", "|+  "])
        # current cell nonzero ->.
        steer = _choose_heading(grid, _Car(1, 2, "S"), _NO_LATCHES, 0, 1)
        assert steer is not None
        assert steer.heading == "W"
        assert steer.latches.merge is None

    def test_four_way_junction_also_merges(self) -> None:
        r"""A four-way junction (``+`` at all four detection-window corners,."""
        code = [
            " |C  |",
            " |   |",
            "-+   +-",
            "       ",
            "       ",
            "-+   +-",
            " |   |",
            " |   |",
        ]
        machine = machine_unvalidated(code)
        positions = [(machine.row, machine.col)]
        for _ in range(7):
            machine.step()
            positions.append((machine.row, machine.col))
        assert positions == [
            (0, 2),
            (1, 2),
            (2, 2),
            (3, 2),
            (4, 2),
            (4, 3),
            (4, 4),
            (4, 5),
        ]


class TestStreetcodeCountingLoop:
    r"""A counting loop: a ring the car laps under the control of a cell."""

    def _code(self) -> list[str]:
        return TestStreetcodeAmbiguousTurns()._counting_loop_code()  # noqa: SLF001

    def test_counting_loop_prints_its_character(self) -> None:
        assert run_and_capture(self._code()) == "H"

    def test_counting_loop_halts(self) -> None:
        machine = _Machine(self._code(), IO())
        for _ in range(500):
            machine.step()
            if machine.halted:
                break
        assert machine.halted

    def test_counting_loop_laps_nine_times(self) -> None:
        r"""The counter is nine on entry and falls by one per lap, so the car."""
        machine = _Machine(self._code(), IO())
        counters = []
        for _ in range(500):
            if (machine.row, machine.col, machine.heading) == (5, 8, "E"):
                counters.append(machine.cells.get(0, 0))
            machine.step()
            if machine.halted:
                break
        assert counters == [8, 7, 6, 5, 4, 3, 2, 1, 0]

    def test_counting_loop_accumulates_seventy_two(self) -> None:
        r"""Eight per lap into cell 1, which is what makes the 'H'."""
        machine = _Machine(self._code(), IO())
        for _ in range(500):
            machine.step()
            if machine.halted:
                break
        assert machine.cells[1] == ord("H")


class TestStreetcodeIO:
    def test_input_echoed_via_cpth_cell(self) -> None:
        assert run_street("CIO;", inputs=["X"]) == "X"

    def test_input_reads_only_first_character_of_line(self) -> None:
        assert run_street("CIO;", inputs=["hello"]) == "h"

    def test_empty_input_line_reads_zero(self) -> None:
        assert run_street("CIO;", inputs=[""]) == chr(0)

    def test_exhausted_input_raises_eof(self) -> None:
        machine = _Machine(["CI;"], ScriptedIO(""))
        machine.step()  # 'C'.
        with pytest.raises(EOFError):
            machine.step()  # 'I' with no input left at all.


class TestStreetcodeCPBounds:
    def test_cp_decrement_below_zero_is_clamped(self) -> None:
        r"""``_`` at CP 0 moves nothing rather than raising."""
        assert run_street("C_^O;") == chr(1)
        # repeated clamping stays on.
        assert run_street("C___^O;") == chr(1)

    def test_cp_can_move_right_and_back_to_zero(self) -> None:
        assert run_street("C=_^O;") == chr(1)

    def test_output_of_out_of_range_cell_halts(self) -> None:
        r"""A cell value that isn't a valid code point is invalid, not a crash."""
        with pytest.raises(HaltError):
            run(["C~~~~~~~~~~~~~O;"], io=IO())  # cell reaches a large negative.


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


class TestStreetcodeRejectionMessages:
    r"""Every rejection paired with the message it must raise."""

    REJECTIONS: ClassVar[list[tuple[str, list[str], str]]] = [
        ("empty", [], "Streetcode program cannot be empty"),
        ("blank", ["   ", ""], "Streetcode program cannot be empty"),
        (
            "no car",
            ["   ", " ; "],
            "Streetcode program must have exactly one C, found 0",
        ),
        (
            "two cars",
            ["C  ", "  C"],
            "Streetcode program must have exactly one C, found 2",
        ),
        (
            "dead end",
            ["+----+", "|C^O;|", "+----+"],
            "not two-wide at (1, 1) (dead end)",
        ),
        ("horizontal", ["C^O;", "+---+"], "not two-wide at (0, 1) (horizontal)"),
        (
            "vertical",
            [
                "+-+    ",
                "|C|    ",
                "|^+-+  ",
                "|^^^|  ",
                "+-+^|  ",
                "  |;|  ",
                "  +-+  ",
            ],
            "not two-wide at (2, 1) (vertical)",
        ),
        (
            "wider than two",
            ["+------+", "|C^^^O;|", "|      |", "|      |", "+------+"],
            "not two-wide at (1, 2) (wider than two)",
        ),
        (
            "wider than two, open block",
            ["+------+", "|      |", "|C^    |", "|      |", "+------+"],
            "not two-wide at (1, 2) (wider than two)",
        ),
        (
            "wall fragment",
            ["+---+", "|C  |", "+---+"],
            "not two-wide at (1, 1) (dead end)",
        ),
        (
            "wall hole",
            ["+----+", "|C   |", "|    |", "+- --+"],
            "not two-wide at (3, 2) (dead end)",
        ),
        (
            "detached box",
            ["+----+   +--+", "|C   |   |  |", "|    |   |  |", "+----+   +--+"],
            "geometry not connected to the street at (0, 9) ('+')",
        ),
        (
            "stray fragment",
            ["+----+", "|C   |", "|    |", "+----+", "   -- "],
            "geometry not connected to the street at (4, 3) ('-')",
        ),
        (
            "solid island",
            [
                "+--------+",
                "|C       |",
                "|        |",
                "|  ++++  |",
                "|  ++++  |",
                "|  ++++  |",
                "|        |",
                "|        |",
                "+--------+",
            ],
            "geometry not connected to the street at (4, 4) ('+')",
        ),
        (
            "two-wide hole",
            ["+------+", "|C     |", "|      |", "+--  --+"],
            "street reaches the edge of the grid at (3, 4): "
            "the road is not enclosed by walls",
        ),
        (
            "open to edge",
            ["+-----", "|C    ", "|     ", "+-----"],
            "street reaches the edge of the grid at (1, 5): "
            "the road is not enclosed by walls",
        ),
        (
            "corner missing east",
            ["+----+", "|C   |", "|    |", "+--|-+"],
            "wall turns without a corner at (3, 2): '-' beside '|' at (3, 3)",
        ),
        (
            "corner missing south",
            ["+--+", "|C |", "|  |", "-  |", "|  |", "+--+"],
            "wall turns without a corner at (2, 0): '|' beside '-' at (3, 0)",
        ),
    ]

    @pytest.mark.parametrize(("label", "program", "message"), REJECTIONS)
    def test_rejection_message_is_exact(
        self, label: str, program: list[str], message: str
    ) -> None:
        with raises_message(ValueError, message, label):
            _Machine(program, IO())


class TestStreetcodeStreetWidth:
    r"""Construction-time rejection of one-wide streets."""

    def test_one_wide_dead_end_is_rejected(self) -> None:
        r"""A single instruction row between two walls has no second lane."""
        with pytest.raises(ValueError, match="not two-wide"):
            run(["+----+", "|C^O;|", "+----+"], io=IO())

    def test_one_wide_against_grid_edge_is_rejected(self) -> None:
        r"""Off-grid counts as closed, so an edge row is still one-wide."""
        with pytest.raises(ValueError, match="not two-wide"):
            run(["C^O;", "+---+"], io=IO())

    def test_one_wide_staircase_is_rejected(self) -> None:
        r"""Every cell is a corner, so no cell has an opposite-pair of."""
        with pytest.raises(ValueError, match="not two-wide"):
            run(
                [
                    "+-+    ",
                    "|C|    ",
                    "|^+-+  ",
                    "|^^^|  ",
                    "+-+^|  ",
                    "  |;|  ",
                    "  +-+  ",
                ],
                io=IO(),
            )

    def test_two_wide_street_is_accepted(self) -> None:
        r"""An instruction lane with an oncoming lane beside it is legal."""
        assert run_street("C^O;") == chr(1)

    def test_wider_than_two_is_rejected(self) -> None:
        r"""Streets are two wide, so a three-lane corridor is malformed."""
        with pytest.raises(ValueError, match="wider than two"):
            run(
                ["+------+", "|C^^^O;|", "|      |", "|      |", "+------+"],
                io=IO(),
            )

    def test_three_by_two_room_is_accepted(self) -> None:
        r"""The deliberate boundary of the three-by-three rule: a three-by-two."""
        _Machine(["+---+", "|C^;|", "|~~~|", "+---+"], IO())

    def test_crossing_of_two_streets_is_accepted(self) -> None:
        r"""The critical case: where two legal two-wide streets cross, the open."""
        _Machine(
            [
                "+--+  +--+",
                "|  |  |  |",
                "|  +--+  |",
                "|   C    |",
                "|        |",
                "|  +--+  |",
                "|  |  |  |",
                "+--+  +--+",
            ],
            IO(),
        )

    def test_wall_fragment_without_instructions_is_rejected(self) -> None:
        r"""The content-sniffing exemption is closed: a one-wide grid is."""
        with pytest.raises(ValueError, match="not two-wide"):
            _Machine(["+---+", "|C  |", "+---+"], IO())

    def test_grid_without_walls_is_exempt(self) -> None:
        r"""With no walls there is no street network to measure."""
        _Machine(["CU"], IO())

    def test_wall_hole_is_rejected(self) -> None:
        r"""A wall that stops and resumes one cell later leaves a gap too."""
        with pytest.raises(ValueError, match=r"not two-wide|malformed wall"):
            _Machine(["+----+", "|C   |", "|    |", "+- --+"], IO())

    def test_uncapped_divider_end_is_accepted(self) -> None:
        r"""Whether a divider must end in a '+' is a spec question the wiki."""
        _Machine(
            [
                "+------+",
                "|C     |",
                "|      |",
                "+  ----+",
                "|      |",
                "|      |",
                "+------+",
            ],
            IO(),
        )

    def test_road_mouth_is_accepted(self) -> None:
        r"""A mouth is at least two cells across, so its '+' markers never."""
        _Machine(
            [
                "+--------+",
                "|C       |",
                "|        |",
                "+--+  +--+",
                "   |  |   ",
                "   |  |   ",
                "   +--+   ",
            ],
            IO(),
        )

    def test_detached_geometry_is_rejected(self) -> None:
        r"""A second box the car can never reach belongs to no street."""
        with pytest.raises(ValueError, match="not connected"):
            _Machine(
                ["+----+   +--+", "|C   |   |  |", "|    |   |  |", "+----+   +--+"],
                IO(),
            )

    def test_stray_wall_fragment_is_rejected(self) -> None:
        r"""A scribble of wall outside the program bounds no road."""
        with pytest.raises(ValueError, match="not connected"):
            _Machine(["+----+", "|C   |", "|    |", "+----+", "   -- "], IO())

    def test_island_inside_a_ring_is_accepted(self) -> None:
        r"""An island is legal geometry -- a block the car drives around -- so."""
        _Machine(
            [
                "+-------+",
                "|C      |",
                "|       |",
                "|  +-+  |",
                "|  | |  |",
                "|  +-+  |",
                "|       |",
                "|       |",
                "+-------+",
            ],
            IO(),
        )

    def test_solid_island_is_rejected(self) -> None:
        r"""A block thick enough to have an interior: its outer ring bounds the."""
        with pytest.raises(ValueError, match="not connected"):
            _Machine(
                [
                    "+--------+",
                    "|C       |",
                    "|        |",
                    "|  ++++  |",
                    "|  ++++  |",
                    "|  ++++  |",
                    "|        |",
                    "|        |",
                    "+--------+",
                ],
                IO(),
            )

    def test_two_wide_hole_in_a_wall_is_rejected(self) -> None:
        r"""A hole two cells across is a legal-width passage, so the width."""
        with pytest.raises(ValueError, match="reaches the edge"):
            _Machine(["+------+", "|C     |", "|      |", "+--  --+"], IO())

    def test_street_open_to_the_grid_edge_is_rejected(self) -> None:
        r"""A street is bounded by walls, so the road never touches the border:."""
        with pytest.raises(ValueError, match="reaches the edge"):
            _Machine(["+-----", "|C    ", "|     ", "+-----"], IO())

    def test_horizontal_wall_beside_a_vertical_one_is_rejected(self) -> None:
        r"""Where a wall changes direction it turns a corner, and a corner is."""
        with pytest.raises(ValueError, match="turns without a corner"):
            _Machine(["+----+", "|C   |", "|    |", "+--|-+"], IO())

    def test_vertical_wall_above_a_horizontal_one_is_rejected(self) -> None:
        r"""The same slip a quarter turn round."""
        with pytest.raises(ValueError, match="turns without a corner"):
            _Machine(["+--+", "|C |", "|  |", "-  |", "|  |", "+--+"], IO())

    def test_instruction_sealed_inside_an_island_is_rejected(self) -> None:
        r"""Code the car can never drive is not part of the program."""
        with pytest.raises(ValueError, match="not connected"):
            _Machine(
                [
                    "+-------+",
                    "|C      |",
                    "|       |",
                    "|  +-+  |",
                    "|  |^|  |",
                    "|  +-+  |",
                    "|       |",
                    "|       |",
                    "+-------+",
                ],
                IO(),
            )

    def test_text_beside_the_program_is_rejected(self) -> None:
        r"""Strictness means prose beside a program is malformed too, not a."""
        with pytest.raises(ValueError, match="not connected"):
            _Machine(["+----+  counts up", "|C   |", "|    |", "+----+"], IO())

    def test_blank_padding_is_not_geometry(self) -> None:
        r"""A ragged program squared off by ``ljust``, and the background."""
        _Machine(["+----+", "|C   |", "|    |", "+----+", "      "], IO())

    @pytest.mark.parametrize(
        "path",
        ["tests/fixtures/streetcode_hello.txt", "examples/boolean/streetcode.txt"],
    )
    def test_shipped_examples_are_accepted(self, path: str) -> None:
        r"""The repo's own programs must survive the check."""
        root = Path(__file__).resolve().parents[2]
        code = (root / path).read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        _Machine(code, IO())


class TestStreetcodeGrid:
    r"""The drawing as a total map from coordinates to characters."""

    def _grid(self) -> _Grid:
        return _Grid(["+--+", "|C;|", "+--+"])

    @pytest.mark.parametrize(
        "where", [(-1, 0), (0, -1), (3, 0), (0, 4), (-5, -5), (99, 99)]
    )
    def test_a_read_off_the_drawing_is_void(self, where: tuple[int, int]) -> None:
        r"""Any coordinate at all answers, so no caller range-checks first."""
        assert self._grid()[where] == _VOID

    def test_void_is_neither_a_wall_nor_a_glyph(self) -> None:
        r"""The property the mouth scans depend on."""
        assert _VOID not in _WALLS
        for glyph in "+-|C;^~=_IOU":
            assert glyph != _VOID

    def test_off_the_grid_is_not_drivable(self) -> None:
        r"""``open_at`` reads the bounds, not the character."""
        grid = self._grid()
        assert not grid.open_at(-1, 0)
        assert not grid.open_at(0, 0)  # a real wall.
        assert grid.open_at(1, 1)  # the 'C'.

    def test_a_ragged_program_is_squared_off(self) -> None:
        r"""Short rows are padded, so every row is ``width`` long."""
        grid = _Grid(["+---+", "|C;"])
        assert grid.width == 5
        assert grid[1] == "|C;  "
        assert grid[1, 4] == " "

    def test_a_row_can_be_redrawn(self) -> None:
        r"""The fixtures build geometry by assigning whole rows."""
        grid = self._grid()
        grid[1] = "|CX|"
        assert grid[1, 2] == "X"


class TestStreetcodeOps:
    r"""What a square does, as a closed set rather than a character."""

    def _grid(self) -> _Grid:
        return _Grid(["+----+", "|C^~=|", "|_IOU|", "+--;#+"])

    @pytest.mark.parametrize(
        ("where", "op"),
        [
            ((1, 2), "INC"),
            ((1, 3), "DEC"),
            ((1, 4), "RIGHT"),
            ((2, 1), "LEFT"),
            ((2, 2), "IN"),
            ((2, 3), "OUT"),
            ((2, 4), "TURN"),
            ((3, 3), "HALT"),
        ],
    )
    def test_each_glyph_maps_to_its_op(self, where: tuple[int, int], op: str) -> None:
        assert self._grid().op_at(*where) == op

    @pytest.mark.parametrize("where", [(1, 1), (3, 4), (0, 0), (-1, -1)])
    def test_everything_undefined_is_a_nop(self, where: tuple[int, int]) -> None:
        r"""``C``, a stray ``#``, a wall and the void all do nothing."""
        assert self._grid().op_at(*where) == "NOP"

    def test_an_undefined_glyph_is_a_nop_but_still_drawn(self) -> None:
        r"""The op is folded; the character is not."""
        grid = self._grid()
        assert grid.op_at(3, 4) == "NOP"
        assert grid[3, 4] == "#"

    def test_stray_ink_is_still_rejected_by_its_glyph(self) -> None:
        r"""The end-to-end version: a '#' off the street fails validation."""
        with pytest.raises(ValueError, match=re.escape("('#')")):
            _Machine(["+---+", "|C  |", "|   |", "+---+", "  #  "], IO())


class TestStreetcodeStatedInvariants:
    r"""The invariants the interpreter relies on, as executable checks."""

    def _street(self) -> list[str]:
        return ["+----+", "|C  ;|", "|    |", "+----+"]

    def test_a_border_cell_trips_the_block_precondition(self) -> None:
        r"""``_block`` states what it needs rather than trusting the caller."""
        machine = _Machine(self._street(), IO())
        with pytest.raises(AssertionError, match="on the border"):
            machine._block(_ReachableCell((0, 0)))  # noqa: SLF001

    @pytest.mark.parametrize("cell", [(1, 1), (2, 4)])
    def test_an_interior_cell_reads_its_neighbourhood(
        self, cell: tuple[int, int]
    ) -> None:
        r"""The precondition admits every cell the enclosure check allows."""
        machine = _Machine(self._street(), IO())
        assert len(machine._block(_ReachableCell(cell))) == 9  # noqa: SLF001

    def test_a_valid_street_violates_nothing(self) -> None:
        r"""Every stated rule holds of a program the validator accepted."""
        machine = _Machine(self._street(), IO())
        reachable = machine._validate_width((machine.row, machine.col))  # noqa: SLF001
        assert reachable is not None
        assert machine._width_violation(reachable) is None  # noqa: SLF001
        assert machine._enclosure_violation(reachable) is None  # noqa: SLF001
        assert machine._glyph_violation() is None  # noqa: SLF001
        assert machine._connection_violation(reachable) is None  # noqa: SLF001

    def test_a_violation_is_what_the_validator_raises(self) -> None:
        r"""The rule and the rejection are one statement, not two."""
        code = ["+---", "|C  ", "|   ", "+---"]
        machine = machine_unvalidated(code)
        reachable = machine._validate_width((machine.row, machine.col))  # noqa: SLF001
        assert reachable is not None
        violation = machine._enclosure_violation(reachable)  # noqa: SLF001
        assert violation is not None
        with pytest.raises(ValueError, match=re.escape(violation)):
            _Machine(code, IO())


class TestStreetcodeWikiExamples:
    r"""The wiki's own worked examples (interior grid, borders stripped)."""

    def test_whole_right_hand_side_example(self) -> None:
        r"""``CIO;`` echoes one input character then halts."""
        assert run_street("CIO;", inputs=["Q"]) == "Q"

    def test_infinite_cat_example(self) -> None:
        r"""The U-turn cat echoes input characters in order, then hangs on EOF."""
        code = ["UOI ", "CIOU"]
        scripted = ScriptedIO("A\nB\nC")
        with pytest.raises(EOFError):
            run(code, io=scripted)
        assert scripted.getvalue() == "ABC"

    def test_infinite_loop_example_hangs(self) -> None:
        r"""The ambiguous-turn infinite loop is a genuine cycle, not a halt."""
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
        assert not machine.halted  # confirmed a genuine cycle.

    def test_infinite_loop_example_traces_its_17_cell_lap(self) -> None:
        r"""The loop's lap, pinned cell by cell against a hand-checked trace."""
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
            (2, 1),
            (2, 2),
            (2, 3),
            (2, 4),
            (2, 5),
            (2, 6),
            (3, 6),
            (4, 6),
            (5, 6),
            (5, 5),
            (5, 4),
            (5, 3),
            (4, 3),
            (3, 3),
            (2, 3),
            (1, 3),
            (1, 2),
            (1, 1),
        ]  # fmt: skip
        machine = _Machine(code, IO())
        path = []
        for _ in range(len(lap) * 3):
            path.append((machine.row, machine.col))
            machine.step()
        # The lap repeats exactly: same.
        assert path == lap * 3
        assert len(set(lap)) == 17  # (2, 3) is driven through.

    def test_infinite_cat_for_single_characters_example(self) -> None:
        r"""The wiki's rhetorical "Why wouldn't this be a cat?" -- it is one."""
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
        # A single row: wall South (out.
        # resolves the initial heading.
        assert (machine.row, machine.col, machine.heading) == (0, 0, "E")
        machine.step()  # 'C' is a nop; drives onto 'I'.
        assert (machine.row, machine.col) == (0, 1)

    def test_snapshot_includes_input_cursor(self) -> None:
        machine = _Machine(["CIO;"], ScriptedIO("A"))
        before = machine.snapshot()
        machine.step()  # 'C'.
        machine.step()  # 'I' consumes the input line.
        after = machine.snapshot()
        assert before != after
        assert machine.io.position() == 1

    def test_the_machine_satisfies_the_vm_step_protocol(self) -> None:
        r"""``run_until_halt_or_cycle`` steps this, so it must conform."""
        assert isinstance(_Machine(["C;"], IO()), _StepMachine)

    def test_snapshot_separates_every_state_the_machine_carries(self) -> None:
        r"""No two distinct states may share a snapshot, and it must hash."""
        code = ["+----+", "|C  ;|", "|    |", "+----+"]
        merge = _Merge(1, 1, "left", "S", crossing=False)
        # The fixture starts heading.
        # changes; using "S" here would.
        latch_sets = [
            _NO_LATCHES._replace(merge=merge),
            _NO_LATCHES._replace(merging_heading="N"),
            _NO_LATCHES._replace(skip_hug=3),
        ]
        states = [
            _State(1, 1, "S", _NO_LATCHES),  # the machine's own start.
            _State(2, 1, "S", _NO_LATCHES),
            _State(1, 2, "S", _NO_LATCHES),
            _State(1, 1, "N", _NO_LATCHES),
            _State(1, 1, "W", _NO_LATCHES),
            *[_State(1, 1, "S", latches) for latches in latch_sets],
        ]

        snapshots = []
        for state in states:
            machine = _Machine(code, IO())
            machine._state = state  # noqa: SLF001
            snapshots.append(machine.snapshot())
        # ...and the three fields that.
        for mutate in (
            lambda m: setattr(m, "cp", 5),
            lambda m: m.cells.__setitem__(0, 9),
            lambda m: setattr(m, "_done", True),
        ):
            machine = _Machine(code, IO())
            mutate(machine)
            snapshots.append(machine.snapshot())

        assert len(set(snapshots)) == len(snapshots)
        assert all(hash(s) is not None for s in snapshots)

    def test_halting_program_is_detected_as_halted(self) -> None:
        assert run_until_halt_or_cycle(_Machine(["C;"], IO())) is True

    def test_step_on_an_already_halted_machine_is_a_no_op(self) -> None:
        machine = _Machine(["C;"], IO())
        machine.step()  # 'C', moves onto ';'.
        machine.step()  # ';' halts.
        assert machine.halted
        before = machine.snapshot()
        machine.step()  # calling step() again must not.
        assert machine.snapshot() == before


def test_an_isolated_cell_is_not_a_street() -> None:
    r"""One open cell with no neighbour is not a street to drive on."""
    _Machine([" + ", "+C+", " + "], IO())


# A counting-ring program.
# approaches the junction, so a.
# latch path end to end -- both.
_RING_PROGRAM = [
    "+----------------------------------------------+",
    "|                                              |",
    "|C^        O^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^O;|",
    "+--+  ++  +------------------------------------+",
    "   |      |",
    "   | ^_~ =|",
    "   | ^++= |",
    "   |^^++^U|",
    "   |^^^^^=|",
    "   |^^^^^^|",
    "   +------+",
]


def test_a_counting_ring_program_drives_its_whole_lap() -> None:
    r"""The lap follows the latched merge through to the turn."""
    assert run_and_capture(_RING_PROGRAM) == "Hi"


class TestStreetcodeDriveStates:
    r"""The drive-state graph (``_drive_states``) and its two uses."""

    def _corridor(self) -> list[str]:
        return ["+----+", "|C  ;|", "|    |", "+----+"]

    def test_every_state_has_a_successor(self) -> None:
        r"""A validated street is total: no reachable state wedges the car."""
        machine = _Machine(self._corridor(), IO())
        graph = machine._drive_states((1, 1))  # noqa: SLF001
        # ``None`` means only "ran out.
        # ``;`` reports itself as.
        # against the square underneath.
        wedged = [
            state
            for state, edges in graph.items()
            if any(succ is None for succ in edges.values())
        ]
        assert wedged == []

    def test_exploring_leaves_the_machine_untouched(self) -> None:
        r"""``_drive_states`` drives the live machine, so it must restore it."""
        machine = _Machine(self._corridor(), IO())
        before = machine.snapshot()
        machine._drive_states((1, 1))  # noqa: SLF001
        assert machine.snapshot() == before

    def test_each_state_is_keyed_by_both_branch_bits(self) -> None:
        r"""Both tape reads a step can make are probed, so all four pairs."""
        machine = _Machine(self._corridor(), IO())
        graph = machine._drive_states((1, 1))  # noqa: SLF001
        assert graph
        for edges in graph.values():
            assert set(edges) == {(0, 0), (0, 1), (1, 0), (1, 1)}

    def test_a_wedging_phase_is_rejected_at_construction(self) -> None:
        r"""The check fires when the movement rules do run out of road."""
        from esolangs.interpreters.grid_based import streetcode as module

        with (
            patch.object(
                module,
                "_heading_from_hug",
                lambda _grid, _car, latches: (None, latches),
            ),
            pytest.raises(ValueError, match="cannot drive out of"),
        ):
            _Machine(self._corridor(), IO())

    @pytest.mark.parametrize(
        "path",
        ["tests/fixtures/streetcode_hello.txt", "examples/boolean/streetcode.txt"],
    )
    def test_mouth_depth_bound_does_not_change_the_driving(self, path: str) -> None:
        r"""``_MOUTH_MAX_DEPTH`` is pinned by behaviour, not by its scans."""
        from esolangs.interpreters.grid_based import streetcode as module

        root = Path(__file__).resolve().parents[2]
        code = (root / path).read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        machine = _Machine(code, IO())
        start = (machine.row, machine.col)
        shipped = machine._drive_states(start)  # noqa: SLF001

        original = module._MOUTH_MAX_DEPTH  # noqa: SLF001
        module._MOUTH_MAX_DEPTH = machine.grid.height + machine.grid.width  # noqa: SLF001
        try:
            generous = machine._drive_states(start)  # noqa: SLF001
        finally:
            module._MOUTH_MAX_DEPTH = original  # noqa: SLF001
        assert shipped == generous


class TestStreetcodeDriveInvariants:
    r"""What holds of a drive state under every reading of the spec."""

    def _machine(self) -> _Machine:
        r"""The grid from ``701de45``, whose lower room the car drove into."""
        return _Machine(
            [
                "+---------+",
                "|         |",
                "|C^      ;|",
                "+--+  ++--+",
                "   |      |",
                "   |;     |",
                "   +------+",
            ],
            IO(),
        )

    def test_a_car_inside_a_wall_is_caught(self) -> None:
        r"""The regression from ``701de45``, as a construction-time failure."""
        machine = self._machine()
        assert not machine.grid.open_at(3, 2)
        with pytest.raises(AssertionError, match="not open floor"):
            machine._check_state_invariants(  # noqa: SLF001
                _State(3, 2, "S", _NO_LATCHES), {}
            )

    def test_a_teleporting_step_is_caught(self) -> None:
        r"""A successor two cells away is the car skipping a square."""
        machine = self._machine()
        state = _State(2, 1, "E", _NO_LATCHES)
        edges = {(0, 0): _State(2, 3, "E", _NO_LATCHES)}
        with pytest.raises(AssertionError, match="not one orthogonal step"):
            machine._check_state_invariants(state, edges)  # noqa: SLF001

    def test_a_step_into_a_wall_is_caught(self) -> None:
        r"""A successor on a wall cell, one step away or not."""
        machine = self._machine()
        state = _State(2, 2, "S", _NO_LATCHES)
        edges = {(0, 0): _State(3, 2, "S", _NO_LATCHES)}
        with pytest.raises(AssertionError, match="which is not open"):
            machine._check_state_invariants(state, edges)  # noqa: SLF001

    def test_a_merge_target_off_the_travel_axis_is_caught(self) -> None:
        r"""The approach holds its lane, so the target is straight ahead."""
        machine = self._machine()
        # Heading East from (2, 1), so.
        merge = _Merge(1, 4, "right", "E", crossing=False)
        state = _State(2, 1, "E", _Latches(merge, None, 0))
        with pytest.raises(AssertionError, match="off the axis"):
            machine._check_state_invariants(state, {})  # noqa: SLF001

    def test_a_merge_target_behind_the_car_is_caught(self) -> None:
        r"""The car drives forwards onto the target; it cannot reverse to it."""
        machine = self._machine()
        merge = _Merge(2, 1, "right", "E", crossing=False)
        state = _State(2, 3, "E", _Latches(merge, None, 0))
        with pytest.raises(AssertionError, match="behind it"):
            machine._check_state_invariants(state, {})  # noqa: SLF001

    def test_a_stale_latch_is_not_checked(self) -> None:
        r"""A latch the next step abandons describes no geometry."""
        machine = self._machine()
        # Off-axis and behind -- but.
        # longer holds, so neither rule.
        merge = _Merge(5, 4, "right", "S", crossing=False)
        state = _State(2, 1, "E", _Latches(merge, None, 0))
        machine._check_state_invariants(state, {})  # noqa: SLF001

    def test_every_shipped_program_satisfies_them(self) -> None:
        r"""The invariants hold over every program the repo ships."""
        root = Path(__file__).resolve().parents[2]
        paths = sorted((root / "examples").glob("**/streetcode.txt"))
        # A relative glob silently.
        # directory, which would leave.
        assert paths
        for path in paths:
            _Machine(path.read_text().split("\n"), IO())


class TestStreetcodeGraphBackedStepping:
    r"""Graph-backed stepping must agree with the movement rules exactly."""

    def _lockstep(self, code: list[str], stdin: str = "", limit: int = 20000) -> int:
        r"""Run one machine on the graph and one on the phases, in step."""
        fast = _Machine(code, ScriptedIO(stdin))
        slow = _Machine(code, ScriptedIO(stdin))
        # Emptying the graph forces.
        slow._graph = None  # noqa: SLF001
        assert fast._graph is not None, "the fixture needs a validated street"  # noqa: SLF001

        steps = 0
        for steps in range(1, limit + 1):
            fast_error = slow_error = None
            try:
                fast.step()
            except Exception as exc:
                fast_error = type(exc).__name__
            try:
                slow.step()
            except Exception as exc:
                slow_error = type(exc).__name__
            assert fast_error == slow_error, (
                f"step {steps}: {fast_error} vs {slow_error}"
            )
            assert fast.snapshot() == slow.snapshot(), f"diverged at step {steps}"
            if fast.halted or fast_error:
                break
        return steps

    def test_a_plain_corridor_agrees(self) -> None:
        assert self._lockstep(["+----+", "|C^O;|", "|    |", "+----+"]) > 1

    def test_a_junction_agrees(self) -> None:
        r"""The early-sighted mouth fixture, which defers a turn to the gap."""
        code = [
            "+---------+",
            "|         |",
            "|C^      ;|",
            "+--+  ++--+",
            "   |      |",
            "   |;     |",
            "   +------+",
        ]
        assert self._lockstep(code) > 1

    @pytest.mark.parametrize(
        "path",
        ["tests/fixtures/streetcode_hello.txt", "examples/boolean/streetcode.txt"],
    )
    def test_the_shipped_examples_agree(self, path: str) -> None:
        root = Path(__file__).resolve().parents[2]
        code = (root / path).read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        assert self._lockstep(code, stdin="1\n") > 1

    def test_a_ring_program_agrees(self) -> None:
        r"""The ring program latches a merge, so it drives the latch path."""
        assert self._lockstep(_RING_PROGRAM) > 1

    def test_an_off_graph_state_falls_back(self) -> None:
        r"""A state the search never reached still drives, via the phases."""
        machine = _Machine(["+----+", "|C  ;|", "|    |", "+----+"], IO())
        assert machine._graph is not None  # noqa: SLF001
        state = _State(
            machine.row,
            machine.col,
            "N",
            _NO_LATCHES._replace(merging_heading="N"),
        )
        machine._state = state  # noqa: SLF001
        assert state not in machine._graph  # noqa: SLF001
        machine.step()
        assert not machine.halted

    def test_a_halt_edge_stops_the_car(self) -> None:
        r"""A ``"halt"`` edge stops the car rather than driving it nowhere."""
        machine = _Machine(["+----+", "|C  ;|", "|    |", "+----+"], IO())
        assert machine._graph is not None  # noqa: SLF001
        state = _State(1, 4, "N", _NO_LATCHES)
        assert all(v == "halt" for v in machine._graph[state].values())  # noqa: SLF001

        machine.place(1, 4, "N")
        machine.grid[1] = list("|C   |")  # the ';' would halt one arm.
        machine.step()
        assert machine.halted

    def test_a_wedged_edge_raises_rather_than_halting(self) -> None:
        r"""A ``None`` edge is a validator bug, and must not pass for a stop."""
        machine = _Machine(["+----+", "|C  ;|", "|    |", "+----+"], IO())
        assert machine._graph is not None  # noqa: SLF001
        state = _State(1, 1, "E", _NO_LATCHES)
        machine._graph[state] = dict.fromkeys(  # noqa: SLF001
            ((0, 0), (0, 1), (1, 0), (1, 1))
        )

        machine.place(1, 1, "E")
        with pytest.raises(AssertionError, match="outlived"):
            machine.step()
        assert not machine.halted

    def test_a_u_turn_without_an_opposite_lane_has_no_successor(self) -> None:
        r"""``U`` needs a lane to turn into; without one the state is a dead."""
        grid = _Grid(["CU;"])
        assert _drive(grid, _State(0, 1, "E", _NO_LATCHES), 0, 0) is None
        assert _drive(grid, _State(0, 1, "W", _NO_LATCHES), 0, 0) is None
        # ...while a lane that is on.
        assert _drive(grid, _State(0, 1, "N", _NO_LATCHES), 0, 0) is not None


class TestStreetcodeMutationSurvivors:
    r"""Four conditions a mutation survived, each pinned by behaviour."""

    def test_a_single_walled_cell_is_not_a_street(self) -> None:
        r"""One reachable cell is exempt: there is no street to measure."""
        machine = _Machine(["+-+", "|C|", "+-+"], IO())
        assert (machine.row, machine.col) == (1, 1)

    def test_a_one_wide_corridor_is_still_rejected(self) -> None:
        r"""The exemption covers one cell, not two: a corridor is a street."""
        with pytest.raises(ValueError, match="not two-wide"):
            _Machine(["+-+", "|C|", "|U|", "+-+"], IO())

    def test_the_hello_world_example_halts(self) -> None:
        r"""The example halts, and in a bounded number of steps."""
        root = Path(__file__).resolve().parents[2]
        code = (root / "tests/fixtures/streetcode_hello.txt").read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        scripted = ScriptedIO("")
        machine = _Machine(code, scripted)
        steps = 0
        # 426 is the real count; the.
        # a mutant that stops the.
        while not machine.halted and steps < 1000:
            machine.step()
            steps += 1
        assert machine.halted
        assert steps == 426
        assert scripted.getvalue() == "Hello, World!"

    def test_plus_dist_measures_the_nearest_plus_on_a_side(self) -> None:
        r"""The scan reports the distance, and ``None`` when there is no ``+``."""
        root = Path(__file__).resolve().parents[2]
        code = (root / "tests/fixtures/streetcode_hello.txt").read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        machine = _Machine(code, IO())
        assert (machine.row, machine.col) == (5, 3)
        car = _Car(machine.row, machine.col, machine.heading)
        assert _plus_dist(machine.grid, car, "S") == 1
        assert _plus_dist(machine.grid, car, "N") is None
        assert _plus_dist(machine.grid, car, "E") is None
        assert _plus_dist(machine.grid, car, "W") is None


class TestStreetcodeWallForms:
    r"""The wall-form machinery, asserted directly rather than through a."""

    def test_a_rotation_is_a_quarter_turn_clockwise(self) -> None:
        r"""``_rotate`` permutes a 3x3 form, and which permutation matters."""
        form = tuple("012345678")
        # Clockwise: the bottom-left.
        # top-left becomes the.
        assert _rotate(form) == tuple("630741852")  # type: ignore[arg-type]
        # Four quarter turns are the.
        # single-index perturbation of.
        turned = form
        for _ in range(4):
            turned = _rotate(turned)  # type: ignore[arg-type]
        assert turned == form

    def test_rotations_returns_all_four_and_validates_the_alphabet(self) -> None:
        r"""``_rotations`` is four turns of one written form, no more."""
        rots = _rotations("?W?W..?..")
        assert len(rots) == 4
        assert len(set(rots)) == 4  # a corner is not symmetric.
        # The written string is.
        # than asserted to be it: every.
        assert all(set(rot) <= {"?", "W", "."} for rot in rots)
        # Four turns return the form as.
        assert rots[-1] == tuple("?W?W..?..")

    def test_matches_honours_each_letter_of_the_form_alphabet(self) -> None:
        r"""``?`` matches anything, ``W`` a wall, ``.`` a non-wall."""
        wall, floor = "+", " "
        # '?' accepts either.
        assert _matches((wall,), ("?",))
        assert _matches((floor,), ("?",))
        # 'W' accepts only a wall, and.
        assert _matches((wall,), ("W",))
        assert _matches(("-",), ("W",))
        assert _matches(("|",), ("W",))
        assert not _matches((floor,), ("W",))
        # '.' accepts only a non-wall.
        assert _matches((floor,), (".",))
        assert not _matches((wall,), (".",))
        # Off the grid is not a wall,.
        assert _matches((_VOID,), (".",))
        assert not _matches((_VOID,), ("W",))

    def test_a_form_and_a_block_of_different_lengths_is_a_bug(self) -> None:
        r"""``_matches`` zips strictly, so a size mismatch raises."""
        with pytest.raises(ValueError, match="argument"):
            _matches(("+", " "), ("W",))
        with pytest.raises(ValueError, match="argument"):
            _matches(("+",), ("W", "."))
