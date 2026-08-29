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
import re
from contextlib import redirect_stdout
from pathlib import Path
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


def street(instructions: str) -> list[str]:
    """Box a one-line program into a street, the way the wiki draws one.

    The spec's streets are two characters wide, so a bare instruction row
    is not a street: the instructions become the southern lane (the wall
    below them on the car's right is what sends it East) with a blank
    oncoming lane above, inside a wall.  This is exactly the shape of the
    wiki's own "simple example", ``+----+`` / ``|    |`` / ``|CIO;|`` /
    ``+----+``, and it lets these tests pin instruction semantics on
    conformant geometry rather than on a one-wide corridor.
    """
    wall = "+" + "-" * len(instructions) + "+"
    return [wall, "|" + " " * len(instructions) + "|", f"|{instructions}|", wall]


def machine_unvalidated(code: list[str]) -> _Machine:
    """Build a ``_Machine`` from a wall-shape fixture, skipping validation.

    The junction and lane-merge tests probe ``_junction_kind`` and the merge
    latches directly, on deliberately skeletal geometry -- bare wall arms and
    gaps, with assertions keyed to exact coordinates.  Such a fixture is not a
    legal street and is not meant to be one, so it is constructed with
    ``_validate`` disabled rather than redrawn, which would change what the
    test measures.  Whole-program tests use the real constructor.
    """
    with patch.object(_Machine, "_validate", lambda *_: None):
        return _Machine(code, IO())


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    """Run a Streetcode program (patching input) and return its stdout."""
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, io=IO())
    return buffer.getvalue()


def run_street(instructions: str, inputs: list[str] | None = None) -> str:
    """Run a one-line program inside a proper two-lane street."""
    return run_and_capture(street(instructions), inputs)


class TestStreetcodeSingleCommands:
    """Each instruction in isolation."""

    def test_halt_immediately(self) -> None:
        assert run_street("C;") == ""

    def test_increment_then_output(self) -> None:
        assert run_street("C^O;") == chr(1)

    def test_decrement_below_zero_then_output_is_invalid(self) -> None:
        """A cell of -1 is a valid signed int, but not a valid code point."""
        with pytest.raises(HaltError):
            run(["C~O;"], io=IO())

    def test_decrement_then_increment_then_output(self) -> None:
        """~ and ^ both touch the same CPth cell, unbounded and signed."""
        assert run_street("C~^O;") == chr(0)

    def test_space_is_a_nop(self) -> None:
        """A space between C and O is skipped over; the cell is still 0."""
        assert run_street("C O;") == chr(0)

    def test_undefined_character_is_a_nop(self) -> None:
        """Box-drawing and other undefined characters act like space."""
        assert run_street("C#O;") == chr(0)

    def test_u_without_an_opposite_lane_is_invalid(self) -> None:
        """A one-wide corridor is narrower than the spec's two-character
        streets, so a 'U' there has nowhere legal to end its turn: that is
        a malformed street met at run time, not a manoeuvre with a
        fallback."""
        # Two rows so the car has room to move south from C before the U.
        machine = _Machine(["C", "U"], IO())
        assert machine.heading == "S"
        machine.step()  # 'C' nop; only non-backward neighbor is south
        assert (machine.row, machine.col) == (1, 0)
        with pytest.raises(HaltError):
            machine.step()  # 'U' with no lane to the new right

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
        machine = machine_unvalidated(code)
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
        """Move CP right onto a fresh cell, increment it, then move back."""
        assert run_street("C=^O_O;") == chr(1) + chr(0)


class TestStreetcodeHalt:
    def test_semicolon_halts_immediately(self) -> None:
        assert run_street("C;^O") == ""

    def test_program_without_semicolon_runs_until_dead_end(self) -> None:
        """No halt instruction: a dead-end corridor still stops.

        A *street* with no halt does not -- the car circles it forever --
        so the dead end has to be a genuine cul-de-sac, which is what this
        pins: the single-cell program with nowhere to drive at all.
        """
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
        machine.place(machine.row, machine.col, "E")
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
        machine = machine_unvalidated(self._junction_code())
        machine.place(1, 1, "S")
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
        grid = _Grid(["C       ", "-+ |+   ", "        "])
        assert _road_mouth(grid, _Car(0, 0, "E"), "S") is None

    def test_four_way_junction_detects_4(self) -> None:
        """Mouths on both sides at once, road continuing ahead: 4 ways.

        ``_junction_shape`` reads the wall shape alone; ``_junction_kind``
        additionally requires two roads the car could drive down, which
        this narrow fixture's one-cell arms are not (see
        :func:`_road_deep`).
        """
        grid = _Grid([" C ", "+ +", "   ", "+ +", " | "])
        assert _junction_shape(grid, _Car(0, 1, "S")) == 4

    def test_t_junction_detects_3(self) -> None:
        """Mouths on both sides with straight ahead blocked: a T whose
        crossbar the car is driving into, still three ways."""
        grid = _Grid([" C ", "+|+", "   ", "+ +", " | "])
        assert _junction_shape(grid, _Car(0, 1, "S")) == 3

    def test_turn_into_the_oncoming_lane_is_not_a_road(self) -> None:
        """A turn whose destination has the wall on its left and open road
        on its right would leave the car driving on the left, so it is not
        a road the junction may offer, however open it looks."""
        grid = _Grid(self._counting_loop_code())
        car = _Car(5, 9, "E")
        # South from (5,9) enters the lane with the outer wall on its left.
        assert not _lawful_turn(grid, car, "S")
        # North keeps that wall on the right, and is offered.
        assert _lawful_turn(grid, car, "N")

    def test_narrow_arms_are_not_roads(self) -> None:
        """The same shape is not a junction when its arms are one cell:
        streets are two wide, so a single open cell before a wall is the
        width of the road, not a road leading off it."""
        grid = _Grid([" C ", "+ +", "   ", "+ +", " | "])
        assert _junction_kind(grid, _Car(0, 1, "S")) == 0

    def test_every_road_a_junction_offers_is_open_ahead(self) -> None:
        """A junction never offers a road the car cannot step onto.

        This is what retired the deferral guard ``701de45`` added at the
        turn (see :func:`_heading_from_junction`).  ``_road_deep``'s first
        test is the very cell that turn would step onto, and the crossing
        branch tests ``_open_toward`` directly, so an offered road is open
        by construction and the "sighted too early" case cannot arise.
        Weakening either check brings the bug back with nothing to catch
        it, so the invariant is asserted rather than left implied: over
        every reachable drive state of the committed examples, every road
        offered is open ahead.
        """
        root = Path(__file__).resolve().parents[2]
        for path in (
            "examples/hello-world/streetcode.txt",
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

    # A mouth whose gap opens ahead of the car (its near ``+`` sighted at
    # depth 0 or +1) and whose far ``+`` has open interior beneath it (so
    # ``_lane_bounded`` is False and no merge latch is taken): the chosen
    # turn's next cell is still the wall the gap opens through, and the
    # turn must wait until the car is level with the gap.  Before the
    # openness guard in ``_choose_heading``, the car turned immediately,
    # drove *inside* the wall, and wall-followed around the outside of the
    # lower room forever.
    def _counting_loop_code(self) -> list[str]:
        """A hand-written counting loop: nine laps of an island, then out.

        The car counts cell 0 up to nine on the way in, U-turns onto the
        island, and laps it; each lap adds eight to cell 1 and takes one
        off cell 0.  At the island's top-right corner the roads are north
        (out through the gap in the outer wall) and south (on around the
        island), so the countdown steers the loop: nonzero laps again,
        zero leaves.  Nine laps put 72 in cell 1, and the ``=`` on the way
        out moves CP onto it so the ``O`` at the top prints ``H``.
        """
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
        code = [line.replace("^", " ") for line in self._early_mouth_code()]
        machine = _Machine(code, IO())
        for _ in range(9):
            machine.step()
        assert machine.halted
        assert (machine.row, machine.col) == (2, 9)


class TestStreetcodeCrossingMouthDecision:
    """A head-on junction decides at the mouth, not at the far lane.

    Driving out through a mouth the car is level with both ``+`` when it
    chooses; the run across to the far lane is only lane positioning for a
    road already taken.  Re-reading the cell on arrival there lets an
    instruction *on that positioning run* overturn the choice -- the same
    "preparation must not double as the decision" the arrival read exists
    to prevent (see ``TestStreetcodeAmbiguousTurns``).

    A side mouth keeps the re-read: the car drives its approach as
    ordinary road, so the cell at the turning square is the one the spec's
    choice is about.  The counting loop's nine laps depend on that.
    """

    def _code(self) -> list[str]:
        """Two rooms of a folded corridor, the shape a width-6 fold draws.

        The car drives East out of ``C`` into the mouth bounded by the
        divider tips at ``(3,2)`` and ``(6,2)``.  The CPth cell is zero --
        it starts that way, no ``=`` is needed -- so the junction chooses
        the leftmost road, North.  The single ``^`` at ``(5,3)`` lies on
        the run out to that road's lane and makes the cell nonzero before
        the car gets there.

        Everything else is blank, so the geometry alone drives the car:
        remove that one ``^`` and the grid behaves identically either way,
        because there is then nothing to change the cell between choosing
        the road and reaching it.
        """
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
        """The car climbs the road it chose instead of orbiting the tip.

        Re-reading the cell at the far lane made the ``^`` overturn the
        choice, and the car circled the four cells around the divider tip
        forever, re-running that ``^`` on every lap -- never reaching the
        corridor it had turned into.
        """
        machine = _Machine(self._code(), IO())
        seen: set[tuple[int, int]] = set()
        for _ in range(400):
            seen.add((machine.row, machine.col))
            machine.step()
            if machine.halted:
                break
        # The chosen road runs North up the corridor to the top street,
        # and the car goes on to reach the ';'.  An orbiting car never
        # leaves the six cells around the divider's tip.
        assert (1, 4) in seen, sorted(seen)
        assert machine.halted

    def test_a_detected_but_unreachable_road_defers_the_crossing(self) -> None:
        """A crossing does not offer the oncoming lane in a closed road's place.

        Driving out through a mouth, ``_junction_choices`` takes whichever
        way is open, because a perpendicular road's extent cannot be probed
        from inside the mouth.  That is sound only while the open sides are
        the road being joined.  ``_road_mouth`` anchors a mouth up to one
        cell ahead, so a junction fires as the car *arrives* -- and one
        cell short of the gap the road it found is detected but not yet
        drivable.  Taking whatever is open there fills that road's slot
        with the oncoming lane of the two-wide street the car is already
        on, and the car decides a junction the drawing never offered.

        Below, the car drives East along the southern lane.  The gap in the
        wall beneath it at ``(3,4)``/``(3,5)`` is the road; one cell short
        of it, at ``(2,3)``, the mouth is already detected while South is
        still the ``+``.  The choice there must be deferred rather than
        made between North (the blank oncoming lane) and East.
        """
        # A generated boolean program supplies the geometry: a two-wide
        # street whose leaf row carries several junctions, so a crossing
        # sights the next fork while still a cell short of it.  Hand-drawn
        # fragments of this shape do not validate as street networks on
        # their own, which is why the case is pinned through a real
        # program rather than a cut-down grid.
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
        # the case has to actually arise, or the assertion below is vacuous
        assert hits, "no crossing sighted an unreachable road"
        # and wherever it does, the choice is deferred rather than filled
        # out with whatever else happens to be open
        assert all(choices == [] for _, _, choices in hits), hits


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
        """A 'U' during the phase-1 approach must not wedge the latch open.

        Without invalidating ``_merge`` on a heading change, the
        latch would wait forever for a (row, col) the car no longer visits
        (it U-turned away), permanently disabling junction detection for
        the rest of the run.
        """
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
            machine.step()  # down the west lane; the latch forms en route
        assert machine._state.latches.merge is not None  # noqa: SLF001
        machine.step()  # 'U' at (4,1): turns around into the opposite lane
        assert machine._state.latches.merge is None  # noqa: SLF001

    def test_wall_at_the_turn_destination_falls_back_to_plain_rules(self) -> None:
        """The phase-1 turn must not step onto a wall that appears at the
        latched target's chosen heading -- it should fall back to ordinary
        wall-following instead of blindly trusting the stale latch."""
        grid = _Grid(self._lane_merge_code())
        row = grid[3]
        grid[3] = row[:2] + "+" + row[3:]  # wall directly East
        latches = _NO_LATCHES._replace(merge=_Merge(3, 1, "left", "S", crossing=False))
        steer = _choose_heading(grid, _Car(3, 1, "S"), latches, 0, 0)
        assert steer is not None
        assert steer.heading != "E"
        assert steer.latches.merge is None

    def test_wall_after_merge_turn_falls_back_to_plain_rules(self) -> None:
        """The phase-2 straight-through suppression must not drive through
        a wall that appears directly ahead while merging out."""
        grid = _Grid(self._lane_merge_code())
        row = grid[3]
        grid[3] = row[:3] + "+" + row[4:]  # wall directly ahead
        latches = _NO_LATCHES._replace(merging_heading="E")
        steer = _choose_heading(grid, _Car(3, 2, "E"), latches, 0, 0)
        assert steer is not None
        assert steer.heading != "E"

    def test_merge_target_reread_can_carry_straight_on(self) -> None:
        """The branch is re-read at the latched turn cell, not trusted from
        latch time: a cell that went nonzero while approaching reverses the
        decision and the car carries straight on, abandoning the merge.

        The re-read is of the cell as the car *arrives* at that square (see
        ``arrival_cell``), which is what a real approach would have left
        behind it.
        """
        grid = _Grid(self._lane_merge_code())
        latches = _NO_LATCHES._replace(merge=_Merge(3, 1, "left", "S", crossing=False))
        # 1 = the cell as the approach left it, on arrival at the turn;
        # the latch was taken under cell == 0
        steer = _choose_heading(grid, _Car(3, 1, "S"), latches, 1, 1)
        assert steer is not None
        assert steer.heading == "S"
        assert steer.latches.merging_heading is None

    def test_wall_mid_approach_abandons_the_merge_latch(self) -> None:
        """A wall appearing straight ahead while still approaching the
        latched lane drops the latch, like a heading change does: the
        latch must not wait forever for a target it can no longer reach."""
        grid = _Grid(self._lane_merge_code())
        row = grid[2]
        grid[2] = row[:1] + "+" + row[2:]  # wall directly ahead
        latches = _NO_LATCHES._replace(merge=_Merge(3, 1, "left", "S", crossing=False))
        steer = _choose_heading(grid, _Car(1, 1, "S"), latches, 0, 0)
        assert steer is not None
        assert steer.latches.merge is None
        assert steer.heading == "E"  # falls back to plain wall-following

    def test_a_merge_recovers_the_heading_it_turns_to(self) -> None:
        """``_Merge`` stores the turn; the destination is derived from it.

        The latch holds a :data:`_Turn` rather than a second
        :data:`_Heading` so the two direction fields cannot be swapped
        (see the class docstring).  That only works if ``new_heading``
        recovers exactly what the old field held, for every heading.
        """
        for heading in ("N", "E", "S", "W"):
            left = _Merge(0, 0, "left", heading, crossing=False)
            right = _Merge(0, 0, "right", heading, crossing=False)
            assert left.new_heading == _left(heading)
            assert right.new_heading == _right(heading)

    def test_a_merge_turn_is_only_ever_a_left_or_a_right(self) -> None:
        """``_turn_of`` refuses a straight-ahead or reversing "turn".

        A merge latch is only set for a turn onto a detected side road,
        so those two are unreachable; classifying one silently as a
        right turn would latch a road the junction never offered and
        steer the car into a wall several steps later.
        """
        assert _turn_of("S", "E") == "left"
        assert _turn_of("S", "W") == "right"
        for impossible in ("S", "N"):  # straight ahead, and the reverse
            with pytest.raises(AssertionError, match="neither a left nor a right"):
                _turn_of("S", impossible)

    def test_turn_lands_in_the_lane_without_an_approach(self) -> None:
        """When the junction fires while the car already sits in the new
        road's right-hand lane (a mouth whose near ``+`` is one cell
        behind, near == -1), there is nothing to drive to: turn now."""
        grid = _Grid(["|+  ", "  C ", "    ", "|+  "])
        # current cell nonzero -> second-leftmost of [S, W] = West
        steer = _choose_heading(grid, _Car(1, 2, "S"), _NO_LATCHES, 0, 1)
        assert steer is not None
        assert steer.heading == "W"
        assert steer.latches.merge is None

    def test_four_way_junction_also_merges(self) -> None:
        """A four-way junction (``+`` at all four detection-window corners,
        each with genuine wall arms) exercises ``_junction_kind``'s other
        branch through the same lane-merge machinery. This pins current
        behavior on the four-way corner pattern -- unlike the three-way
        case in ``test_merge_lands_in_the_right_hand_lane``, no hand-drawn,
        user-confirmed trace exists for a four-way junction (see the "Still
        open" section of ``docs/streetcode.md``).

        The arms are two characters wide, per the spec: with one-cell arms
        the shape is drawn but there are no roads to drive down, so
        ``_junction_kind`` reports no junction (see :meth:`_road_deep`).
        """
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
    """A counting loop: a ring the car laps under the control of a cell.

    ``docs/streetcode.md`` recorded that no such geometry had been found --
    every attempt leaked, because a junction on the ring offered the wrong
    roads and steered the car off it.  This one works, and the rules that
    make it work (a road must be two cells deep, a turn may not enter the
    oncoming lane, a junction reads the cell as the car arrives) are pinned
    individually above; this is the end-to-end program.
    """

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
        """The counter is nine on entry and falls by one per lap, so the
        car passes the island's corner nine times: eight laps that carry
        on around, and the ninth that leaves."""
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
        """Eight per lap into cell 1, which is what makes the 'H'."""
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
        machine.step()  # 'C'
        with pytest.raises(EOFError):
            machine.step()  # 'I' with no input left at all


class TestStreetcodeCPBounds:
    def test_cp_decrement_below_zero_halts(self) -> None:
        with pytest.raises(HaltError):
            run(["C_;"], io=IO())

    def test_cp_can_move_right_and_back_to_zero(self) -> None:
        assert run_street("C=_^O;") == chr(1)

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


class TestStreetcodeStreetWidth:
    """Construction-time rejection of one-wide streets (``_validate_width``).

    The spec's streets are two-way and two characters wide, so a one-wide
    corridor has no opposite lane for ``U`` to end its turn in.  The
    geometry is static, so the check runs before the car moves.  Remember
    that a blank row or column is a lane -- space is a drivable no-op --
    so an instruction row paired with a blank row is a legal street, not a
    one-wide one.
    """

    def test_one_wide_dead_end_is_rejected(self) -> None:
        """A single instruction row between two walls has no second lane."""
        with pytest.raises(ValueError, match="not two-wide"):
            run(["+----+", "|C^O;|", "+----+"], io=IO())

    def test_one_wide_against_grid_edge_is_rejected(self) -> None:
        """Off-grid counts as closed, so an edge row is still one-wide."""
        with pytest.raises(ValueError, match="not two-wide"):
            run(["C^O;", "+---+"], io=IO())

    def test_one_wide_staircase_is_rejected(self) -> None:
        """Every cell is a corner, so no cell has an opposite-pair of
        neighbours -- the dead-end and vertical arms still catch it."""
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
        """An instruction lane with an oncoming lane beside it is legal."""
        assert run_street("C^O;") == chr(1)

    def test_wider_than_two_is_rejected(self) -> None:
        """Streets are two wide, so a three-lane corridor is malformed.

        Cross-section runs cannot measure this -- through an intersection a
        run reports the crossing street's *length* -- so the rule is a fully
        open three-by-three block, which a two-wide network never contains.
        """
        with pytest.raises(ValueError, match="wider than two"):
            run(
                ["+------+", "|C^^^O;|", "|      |", "|      |", "+------+"],
                io=IO(),
            )

    def test_three_by_two_room_is_accepted(self) -> None:
        """The deliberate boundary of the three-by-three rule: a three-by-two
        room is a two-wide street of length three seen sideways."""
        _Machine(["+---+", "|C^;|", "|~~~|", "+---+"], IO())

    def test_crossing_of_two_streets_is_accepted(self) -> None:
        """The load-bearing case: where two legal two-wide streets cross, the
        open centre is two-by-two with walls at the diagonals, so no fully
        open three-by-three block exists."""
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
        """The content-sniffing exemption is closed: a one-wide grid is
        malformed whether or not it happens to contain an instruction."""
        with pytest.raises(ValueError, match="not two-wide"):
            _Machine(["+---+", "|C  |", "+---+"], IO())

    def test_grid_without_walls_is_exempt(self) -> None:
        """With no walls there is no street network to measure."""
        _Machine(["CU"], IO())

    def test_wall_hole_is_rejected(self) -> None:
        """A wall that stops and resumes one cell later leaves a gap too
        narrow to drive.  The width check happens to catch this shape
        first, since the hole is a reachable one-wide stub; the wall forms
        reject it independently."""
        with pytest.raises(ValueError, match=r"not two-wide|malformed wall"):
            _Machine(["+----+", "|C   |", "|    |", "+- --+"], IO())

    def test_uncapped_divider_end_is_accepted(self) -> None:
        """Whether a divider must end in a '+' is a spec question the wiki
        does not settle, and the forms deliberately leave it open: the
        hello-world example draws bare ends and runs correctly."""
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
        """A mouth is at least two cells across, so its '+' markers never
        sandwich a single open cell the way a hole does."""
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
        """A second box the car can never reach belongs to no street."""
        with pytest.raises(ValueError, match="not connected"):
            _Machine(
                ["+----+   +--+", "|C   |   |  |", "|    |   |  |", "+----+   +--+"],
                IO(),
            )

    def test_stray_wall_fragment_is_rejected(self) -> None:
        """A scribble of wall outside the program bounds no road."""
        with pytest.raises(ValueError, match="not connected"):
            _Machine(["+----+", "|C   |", "|    |", "+----+", "   -- "], IO())

    def test_island_inside_a_ring_is_accepted(self) -> None:
        """An island is legal geometry -- a block the car drives around --
        so neither its wall nor the pocket it seals is a leftover."""
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
        """A block thick enough to have an interior: its outer ring bounds
        the road, but the cells inside bound nothing.  Permitting this
        would cost a second flood-fill to tell an enclosed hole from the
        outside, and nothing the repo draws needs it."""
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
        """A hole two cells across is a legal-width passage, so the width
        check has no reason to fire: what marks it as a gap is that the
        road escapes through it to the edge of the grid."""
        with pytest.raises(ValueError, match="reaches the edge"):
            _Machine(["+------+", "|C     |", "|      |", "+--  --+"], IO())

    def test_street_open_to_the_grid_edge_is_rejected(self) -> None:
        """A street is bounded by walls, so the road never touches the
        border: there is always a wall between it and the outside."""
        with pytest.raises(ValueError, match="reaches the edge"):
            _Machine(["+-----", "|C    ", "|     ", "+-----"], IO())

    def test_horizontal_wall_beside_a_vertical_one_is_rejected(self) -> None:
        """Where a wall changes direction it turns a corner, and a corner
        is drawn '+'.  A '-' next to a '|' is that turn without the mark."""
        with pytest.raises(ValueError, match="turns without a corner"):
            _Machine(["+----+", "|C   |", "|    |", "+--|-+"], IO())

    def test_vertical_wall_above_a_horizontal_one_is_rejected(self) -> None:
        """The same slip a quarter turn round."""
        with pytest.raises(ValueError, match="turns without a corner"):
            _Machine(["+--+", "|C |", "|  |", "-  |", "|  |", "+--+"], IO())

    def test_instruction_sealed_inside_an_island_is_rejected(self) -> None:
        """Code the car can never drive is not part of the program.

        The check is strict: anything off the street is rejected, not
        only walls.  Allowing the rest to stand as comments would cost no
        detection, but is left unimplemented -- see ``_validate_connected``.
        """
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
        """Strictness means prose beside a program is malformed too, not
        a comment."""
        with pytest.raises(ValueError, match="not connected"):
            _Machine(["+----+  counts up", "|C   |", "|    |", "+----+"], IO())

    def test_blank_padding_is_not_geometry(self) -> None:
        """A ragged program squared off by ``ljust``, and the background
        around an L-shaped layout, are blank rather than drawn, so they do
        not count as disconnected geometry."""
        _Machine(["+----+", "|C   |", "|    |", "+----+", "      "], IO())

    @pytest.mark.parametrize(
        "path",
        ["examples/hello-world/streetcode.txt", "examples/boolean/streetcode.txt"],
    )
    def test_shipped_examples_are_accepted(self, path: str) -> None:
        """The repo's own programs must survive the check."""
        root = Path(__file__).resolve().parents[2]
        code = (root / path).read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        _Machine(code, IO())


class TestStreetcodeGrid:
    """The drawing as a total map from coordinates to characters."""

    def _grid(self) -> _Grid:
        return _Grid(["+--+", "|C;|", "+--+"])

    @pytest.mark.parametrize(
        "where", [(-1, 0), (0, -1), (3, 0), (0, 4), (-5, -5), (99, 99)]
    )
    def test_a_read_off_the_drawing_is_void(self, where: tuple[int, int]) -> None:
        """Any coordinate at all answers, so no caller range-checks first."""
        assert self._grid()[where] == _VOID

    def test_void_is_neither_a_wall_nor_a_glyph(self) -> None:
        """The property the mouth scans depend on.

        A border of real wall characters would have them sight junctions
        that were never drawn, so what lies off the drawing has to match
        no rule rather than look like a wall.
        """
        assert _VOID not in _WALLS
        for glyph in "+-|C;^~=_IOU":
            assert glyph != _VOID

    def test_off_the_grid_is_not_drivable(self) -> None:
        """``open_at`` reads the bounds, not the character.

        ``_VOID`` is not a wall, so asking "is this a wall?" would call
        the void open road; there is no road out there at all.
        """
        grid = self._grid()
        assert not grid.open_at(-1, 0)
        assert not grid.open_at(0, 0)  # a real wall
        assert grid.open_at(1, 1)  # the 'C'

    def test_a_ragged_program_is_squared_off(self) -> None:
        """Short rows are padded, so every row is ``width`` long."""
        grid = _Grid(["+---+", "|C;"])
        assert grid.width == 5
        assert grid[1] == "|C;  "
        assert grid[1, 4] == " "

    def test_a_row_can_be_redrawn(self) -> None:
        """The fixtures build geometry by assigning whole rows."""
        grid = self._grid()
        grid[1] = "|CX|"
        assert grid[1, 2] == "X"


class TestStreetcodeOps:
    """What a square does, as a closed set rather than a character."""

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
        """``C``, a stray ``#``, a wall and the void all do nothing.

        The fold is what closes the set: ``step`` has no arm for "some
        other character", because there is no such case left.
        """
        assert self._grid().op_at(*where) == "NOP"

    def test_an_undefined_glyph_is_a_nop_but_still_drawn(self) -> None:
        """The op is folded; the character is not.

        ``_validate_connected`` rejects ink off the street and names the
        glyph it found, so a ``#`` has to stay a ``#`` even though it
        executes as nothing.  Folding the character too would lose that.
        """
        grid = self._grid()
        assert grid.op_at(3, 4) == "NOP"
        assert grid[3, 4] == "#"

    def test_stray_ink_is_still_rejected_by_its_glyph(self) -> None:
        """The end-to-end version: a '#' off the street fails validation."""
        with pytest.raises(ValueError, match=re.escape("('#')")):
            _Machine(["+---+", "|C  |", "|   |", "+---+", "  #  "], IO())


class TestStreetcodeStatedInvariants:
    """The invariants the interpreter relies on, as executable checks.

    Each validator's rule is a ``_*_violation`` method returning the
    offending cell, and the validator raises on whatever it returns; the
    tests below pin that the two cannot drift apart, and that ``_block``'s
    precondition really fires rather than being decoration.
    """

    def _street(self) -> list[str]:
        return ["+----+", "|C  ;|", "|    |", "+----+"]

    def test_a_border_cell_trips_the_block_precondition(self) -> None:
        """``_block`` states what it needs rather than trusting the caller.

        ``_ReachableCell`` records that a cell came from the flood fill;
        it cannot record that the fill never yields a border cell, which
        is the property the unchecked read actually depends on.  Forging
        one (the type is erased at run time) must raise rather than read
        off the grid.
        """
        machine = _Machine(self._street(), IO())
        with pytest.raises(AssertionError, match="on the border"):
            machine._block(_ReachableCell((0, 0)))  # noqa: SLF001

    @pytest.mark.parametrize("cell", [(1, 1), (2, 4)])
    def test_an_interior_cell_reads_its_neighbourhood(
        self, cell: tuple[int, int]
    ) -> None:
        """The precondition admits every cell the enclosure check allows."""
        machine = _Machine(self._street(), IO())
        assert len(machine._block(_ReachableCell(cell))) == 9  # noqa: SLF001

    def test_a_valid_street_violates_nothing(self) -> None:
        """Every stated rule holds of a program the validator accepted."""
        machine = _Machine(self._street(), IO())
        reachable = machine._validate_width((machine.row, machine.col))  # noqa: SLF001
        assert reachable is not None
        assert machine._width_violation(reachable) is None  # noqa: SLF001
        assert machine._enclosure_violation(reachable) is None  # noqa: SLF001
        assert machine._glyph_violation() is None  # noqa: SLF001
        assert machine._connection_violation(reachable) is None  # noqa: SLF001

    def test_a_violation_is_what_the_validator_raises(self) -> None:
        """The rule and the rejection are one statement, not two.

        A grid whose road runs off the edge: the finder names the cell,
        and the message it returns is the one construction fails with.
        """
        code = ["+---", "|C  ", "|   ", "+---"]
        machine = machine_unvalidated(code)
        reachable = machine._validate_width((machine.row, machine.col))  # noqa: SLF001
        assert reachable is not None
        violation = machine._enclosure_violation(reachable)  # noqa: SLF001
        assert violation is not None
        with pytest.raises(ValueError, match=re.escape(violation)):
            _Machine(code, IO())


class TestStreetcodeWikiExamples:
    """The wiki's own worked examples (interior grid, borders stripped)."""

    def test_whole_right_hand_side_example(self) -> None:
        """``CIO;`` echoes one input character then halts."""
        assert run_street("CIO;", inputs=["Q"]) == "Q"

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

    def test_the_machine_satisfies_the_vm_step_protocol(self) -> None:
        """``run_until_halt_or_cycle`` steps this, so it must conform.

        ``_StepMachine`` is ``runtime_checkable``, so the structural
        check is the contract itself rather than a restatement of it.
        """
        assert isinstance(_Machine(["C;"], IO()), _StepMachine)

    def test_snapshot_separates_every_state_the_machine_carries(self) -> None:
        """No two distinct states may share a snapshot, and it must hash.

        The hang detector's verdict is only sound if a repeat is a real
        repeat: two states that differ anywhere must differ here, or a
        program that is still making progress looks like a proven cycle.
        The state is one :class:`_State` record beside the tape, CP, I/O
        and halted flag, so this walks every field of it -- including
        each latch separately, which a snapshot that dropped the record
        or flattened it carelessly would be the way to get wrong.
        """
        code = ["+----+", "|C  ;|", "|    |", "+----+"]
        merge = _Merge(1, 1, "left", "S", crossing=False)
        # The fixture starts heading South, so "N" and "W" are both real
        # changes; using "S" here would silently retest the base state.
        latch_sets = [
            _NO_LATCHES._replace(merge=merge),
            _NO_LATCHES._replace(merging_heading="N"),
            _NO_LATCHES._replace(skip_hug=3),
        ]
        states = [
            _State(1, 1, "S", _NO_LATCHES),  # the machine's own start
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
        # ...and the three fields that are not part of the drive state.
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
        machine.step()  # 'C', moves onto ';'
        machine.step()  # ';' halts
        assert machine.halted
        before = machine.snapshot()
        machine.step()  # calling step() again must not raise or move further
        assert machine.snapshot() == before


def test_an_isolated_cell_is_not_a_street() -> None:
    """One open cell with no neighbour is not a street to drive on.

    The network is built by flooding outward from each open cell; a cell
    that reaches nothing else is a hole in the walls rather than a lane,
    so it is not registered as a street at all.
    """
    _Machine([" + ", "+C+", " + "], IO())


def test_the_generated_ring_program_runs() -> None:
    """The counting-ring program the generator emits drives its whole lap.

    The ring latches a merge as the car approaches the junction, and the
    lap is where that latch is followed through to the turn -- so running a
    generated program is what exercises the merge bookkeeping end to end.
    """
    import esolangs
    from esolangs.registry import LANGUAGES

    generate = LANGUAGES["Streetcode"].text
    assert generate is not None
    for text in ("Hi", "Hello, World!"):
        assert esolangs.run("Streetcode", generate(text)) == text


class TestStreetcodeDriveStates:
    """The drive-state graph (``_drive_states``) and its two uses.

    The graph is the movement half of ``snapshot`` enumerated over the
    whole grid, built by driving the real helpers.  It backs the
    construction-time totality check and ``step`` itself, and in tests it
    pins the mouth-depth bound to the behaviour it produces rather than
    to the cells it scans.
    """

    def _corridor(self) -> list[str]:
        return ["+----+", "|C  ;|", "|    |", "+----+"]

    def test_every_state_has_a_successor(self) -> None:
        """A validated street is total: no reachable state wedges the car."""
        machine = _Machine(self._corridor(), IO())
        graph = machine._drive_states((1, 1))  # noqa: SLF001
        # ``None`` means only "ran out of road" now -- a deliberate stop at
        # ``;`` reports itself as ``"halt"`` -- so a wedge needs no check
        # against the square underneath.
        wedged = [
            state
            for state, edges in graph.items()
            if any(succ is None for succ in edges.values())
        ]
        assert wedged == []

    def test_exploring_leaves_the_machine_untouched(self) -> None:
        """``_drive_states`` drives the live machine, so it must restore it."""
        machine = _Machine(self._corridor(), IO())
        before = machine.snapshot()
        machine._drive_states((1, 1))  # noqa: SLF001
        assert machine.snapshot() == before

    def test_each_state_is_keyed_by_both_branch_bits(self) -> None:
        """Both tape reads a step can make are probed, so all four pairs."""
        machine = _Machine(self._corridor(), IO())
        graph = machine._drive_states((1, 1))  # noqa: SLF001
        assert graph
        for edges in graph.values():
            assert set(edges) == {(0, 0), (0, 1), (1, 0), (1, 1)}

    def test_a_wedging_phase_is_rejected_at_construction(self) -> None:
        """The check fires when the movement rules do run out of road.

        Ordinary wall-following cannot wedge on a validated street (see
        ``_validate_total``), so the state this rejects is reached by
        breaking a phase rather than by drawing one: the check is a
        regression net over the phases, and this is what tripping it
        looks like.

        The phase is patched through the imported module object rather
        than by its dotted string path: ``scripts/mutate_one.py`` bundles
        the interpreter into a single module to mutate it, and a string
        target naming the package still resolves to the *unbundled*
        interpreter there, so the patch lands on a function the bundled
        machine never calls and the wedge never happens.  Patching the
        module object works either way, because the bundler rewrites the
        import that produced it.
        """
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
        ["examples/hello-world/streetcode.txt", "examples/boolean/streetcode.txt"],
    )
    def test_mouth_depth_bound_does_not_change_the_driving(self, path: str) -> None:
        """``_MOUTH_MAX_DEPTH`` is pinned by behaviour, not by its scans.

        The bound is two-sided -- raising it makes the scan run past the
        box it is reading and pair up two ``+`` that bound nothing, which
        is what happens in the 1-arity boolean programs -- so the check
        that matters is not "the same mouths are found" but "the car
        drives the same way".  Comparing the whole drive-state graph at
        the shipped bound against a generous one says exactly that.
        """
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
    """What holds of a drive state under every reading of the spec.

    The geometry rules are reverse-engineered and several remain
    judgement calls; these are not.  A car inside a wall, or one that
    teleports rather than driving a cell at a time, is wrong however the
    spec is read, so ``_check_state_invariants`` asserts them over the
    whole drive-state graph at construction.  Each test drives the
    checker with a state the enumeration cannot currently produce --
    that is the point, since a reachable breach would be a live bug.
    """

    def _machine(self) -> _Machine:
        """The grid from ``701de45``, whose lower room the car drove into."""
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
        """The regression from ``701de45``, as a construction-time failure.

        A junction fired while its gap still opened a cell ahead, and the
        turn drove the car inside the wall the mouth opens through --
        ``(3, 2)`` on this very grid, which is the ``-`` of the lower
        room's top wall.  That was found by hand-drawing a program and
        watching the car misbehave; the invariant names the square.
        """
        machine = self._machine()
        assert not machine.grid.open_at(3, 2)
        with pytest.raises(AssertionError, match="not open floor"):
            machine._check_state_invariants(  # noqa: SLF001
                _State(3, 2, "S", _NO_LATCHES), {}
            )

    def test_a_teleporting_step_is_caught(self) -> None:
        """A successor two cells away is the car skipping a square."""
        machine = self._machine()
        state = _State(2, 1, "E", _NO_LATCHES)
        edges = {(0, 0): _State(2, 3, "E", _NO_LATCHES)}
        with pytest.raises(AssertionError, match="not one orthogonal step"):
            machine._check_state_invariants(state, edges)  # noqa: SLF001

    def test_a_step_into_a_wall_is_caught(self) -> None:
        """A successor on a wall cell, one step away or not."""
        machine = self._machine()
        state = _State(2, 2, "S", _NO_LATCHES)
        edges = {(0, 0): _State(3, 2, "S", _NO_LATCHES)}
        with pytest.raises(AssertionError, match="which is not open"):
            machine._check_state_invariants(state, edges)  # noqa: SLF001

    def test_a_merge_target_off_the_travel_axis_is_caught(self) -> None:
        """The approach holds its lane, so the target is straight ahead."""
        machine = self._machine()
        # Heading East from (2, 1), so the axis is row 2; row 1 is beside it.
        merge = _Merge(1, 4, "right", "E", crossing=False)
        state = _State(2, 1, "E", _Latches(merge, None, 0))
        with pytest.raises(AssertionError, match="off the axis"):
            machine._check_state_invariants(state, {})  # noqa: SLF001

    def test_a_merge_target_behind_the_car_is_caught(self) -> None:
        """The car drives forwards onto the target; it cannot reverse to it."""
        machine = self._machine()
        merge = _Merge(2, 1, "right", "E", crossing=False)
        state = _State(2, 3, "E", _Latches(merge, None, 0))
        with pytest.raises(AssertionError, match="behind it"):
            machine._check_state_invariants(state, {})  # noqa: SLF001

    def test_a_stale_latch_is_not_checked(self) -> None:
        """A latch the next step abandons describes no geometry.

        Once the heading no longer matches the one the latch was taken
        under, ``_heading_from_merge_target`` drops it; its target is
        stale by construction, and holding it to the axis rule would
        reject states the enumeration really does reach (1,116 of them
        across the example and generated programs).
        """
        machine = self._machine()
        # Off-axis and behind -- but latched under a heading the state no
        # longer holds, so neither rule applies.
        merge = _Merge(5, 4, "right", "S", crossing=False)
        state = _State(2, 1, "E", _Latches(merge, None, 0))
        machine._check_state_invariants(state, {})  # noqa: SLF001

    def test_every_shipped_program_satisfies_them(self) -> None:
        """The invariants hold over every program the repo ships.

        Construction runs the check, so this passing means the whole
        drive-state graph of each example is clean -- not just the paths
        a particular input drives.
        """
        root = Path(__file__).resolve().parents[2]
        paths = sorted((root / "examples").glob("**/streetcode.txt"))
        # A relative glob silently matches nothing from another working
        # directory, which would leave this passing over no programs at all.
        assert paths
        for path in paths:
            _Machine(path.read_text().split("\n"), IO())


class TestStreetcodeGraphBackedStepping:
    """Graph-backed stepping must agree with the movement rules exactly.

    ``step`` looks the next state up in the graph enumerated at
    construction, falling back to calling the phases when there is no
    graph or the state is outside it.  Those two paths are two ways of
    computing the same thing, so the test that matters is that they
    never disagree: drive both in lockstep and compare the whole
    ``snapshot`` after every step.
    """

    def _lockstep(self, code: list[str], stdin: str = "", limit: int = 20000) -> int:
        """Run one machine on the graph and one on the phases, in step."""
        fast = _Machine(code, ScriptedIO(stdin))
        slow = _Machine(code, ScriptedIO(stdin))
        # Emptying the graph forces every step down the fallback path.
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
        """The early-sighted mouth fixture, which defers a turn to the gap."""
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
        ["examples/hello-world/streetcode.txt", "examples/boolean/streetcode.txt"],
    )
    def test_the_shipped_examples_agree(self, path: str) -> None:
        root = Path(__file__).resolve().parents[2]
        code = (root / path).read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        assert self._lockstep(code, stdin="1\n") > 1

    @pytest.mark.parametrize("text", ["Hi", "Hello, World!"])
    def test_a_generated_ring_agrees(self, text: str) -> None:
        """The ring program latches a merge, so it drives the latch path."""
        from esolangs.registry import LANGUAGES

        generate = LANGUAGES["Streetcode"].text
        assert generate is not None
        assert self._lockstep(generate(text).split("\n")) > 1

    def test_an_off_graph_state_falls_back(self) -> None:
        """A state the search never reached still drives, via the phases.

        Setting the heading by hand is how the interpreter's own tests
        reach such a state; the graph has no entry for it, and ``step``
        must not fail looking for one.
        """
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
        """A ``"halt"`` edge stops the car rather than driving it nowhere.

        Every edge without a successor in a real program sits on ``;``,
        and ``;`` halts before the lookup is reached, so this arm is the
        graph's own guard rather than a path a validated street takes.
        Blanking the ``;`` after construction leaves the recorded
        ``"halt"`` in place and lets the lookup answer for it.
        """
        machine = _Machine(["+----+", "|C  ;|", "|    |", "+----+"], IO())
        assert machine._graph is not None  # noqa: SLF001
        state = _State(1, 4, "N", _NO_LATCHES)
        assert all(v == "halt" for v in machine._graph[state].values())  # noqa: SLF001

        machine.place(1, 4, "N")
        machine.grid[1] = list("|C   |")  # the ';' would halt one arm earlier
        machine.step()
        assert machine.halted

    def test_a_wedged_edge_raises_rather_than_halting(self) -> None:
        """A ``None`` edge is a validator bug, and must not pass for a stop.

        ``_validate_total`` rejects a street with a wedged state, so a
        ``None`` surviving into the lookup means the graph and the check
        disagree.  Halting on it would hand back a truncated run as though
        the program had finished; the two are told apart precisely so this
        can raise instead.  Only forging the edge reaches it.
        """
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
        """``U`` needs a lane to turn into; without one the state is a dead end.

        A one-row grid has nothing north or south of the ``U``, so heading
        East the reversed lane is off the grid.  ``step`` reports that as a
        width violation at run time; the search just declines to drive on.
        """
        grid = _Grid(["CU;"])
        assert _drive(grid, _State(0, 1, "E", _NO_LATCHES), 0, 0) is None
        assert _drive(grid, _State(0, 1, "W", _NO_LATCHES), 0, 0) is None
        # ...while a lane that is on the grid does produce a successor.
        assert _drive(grid, _State(0, 1, "N", _NO_LATCHES), 0, 0) is not None


class TestStreetcodeMutationSurvivors:
    """Four conditions a mutation survived, each pinned by behaviour.

    Mutation testing (mutmut against a ``bundle_one`` build of this module)
    reported these as changeable without any test noticing.  Two are the
    bounds of the isolated-cell exemption in :meth:`_Machine._validate_width`,
    one is the halt the shipped example reaches, and one is the ``+`` search
    the junction rules steer by.  Each was confirmed by loading the mutant
    and the original side by side and diffing their behaviour.
    """

    def test_a_single_walled_cell_is_not_a_street(self) -> None:
        """One reachable cell is exempt: there is no street to measure.

        The exemption reads ``len(visited) <= 1``.  A mutant that tightened
        it to ``< 1`` stopped exempting the one-cell case, and the wall
        check behind it then rejected a grid the interpreter accepts.
        """
        machine = _Machine(["+-+", "|C|", "+-+"], IO())
        assert (machine.row, machine.col) == (1, 1)

    def test_a_one_wide_corridor_is_still_rejected(self) -> None:
        """The exemption covers one cell, not two: a corridor is a street.

        A mutant that loosened the bound to ``len(visited) <= 2`` exempted
        this grid instead of measuring it, and a one-wide street -- which
        has no opposite lane for ``U`` to end in -- was accepted.
        """
        with pytest.raises(ValueError, match="not two-wide"):
            _Machine(["+-+", "|C|", "|U|", "+-+"], IO())

    def test_the_hello_world_example_halts(self) -> None:
        """The example halts, and in a bounded number of steps.

        Asserting only on the output leaves the halt untested: a mutant of
        ``step`` printed ``Hello, World!`` in full and then drove on for
        ever, parked on one cell.  The step count pins the termination the
        output alone does not.
        """
        root = Path(__file__).resolve().parents[2]
        code = (root / "examples/hello-world/streetcode.txt").read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        scripted = ScriptedIO("")
        machine = _Machine(code, scripted)
        steps = 0
        # 426 is the real count; the cap is headroom, and a tight one keeps
        # a mutant that stops the example halting cheap to reject.
        while not machine.halted and steps < 1000:
            machine.step()
            steps += 1
        assert machine.halted
        assert steps == 426
        assert scripted.getvalue() == "Hello, World!"

    def test_plus_dist_measures_the_nearest_plus_on_a_side(self) -> None:
        """The scan reports the distance, and ``None`` when there is no ``+``.

        ``_crossing_mouth`` reads this to find the two ``+`` bounding a
        mouth, so a mutant that always returned ``None`` unpacked nothing
        and crashed both shipped examples.  Pinning one hit and the misses
        keeps the search itself under test.
        """
        root = Path(__file__).resolve().parents[2]
        code = (root / "examples/hello-world/streetcode.txt").read_text().split("\n")
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
    """The wall-form machinery, asserted directly rather than through a run.

    Mutation testing left 17 survivors in :func:`_rotate`,
    :func:`_rotations` and :func:`_matches` -- the densest cluster in the
    module -- and 14 of them provably change how the car drives or crash
    the drive-state search outright.  They survived because nothing tested
    the forms directly: they are only ever exercised through whole-program
    validation, where a broken rotation still happens to accept every
    committed program.  These pin the pieces themselves.
    """

    def test_a_rotation_is_a_quarter_turn_clockwise(self) -> None:
        """``_rotate`` permutes a 3x3 form, and which permutation matters.

        Ten mutants perturbing a single index of that permutation
        survived.  Labelling the cells makes the mapping checkable, which
        pins all nine indices at once.
        """
        form = tuple("012345678")
        # Clockwise: the bottom-left corner becomes the top-left, and the
        # top-left becomes the top-right.
        assert _rotate(form) == tuple("630741852")  # type: ignore[arg-type]
        # Four quarter turns are the identity -- a property no
        # single-index perturbation of the permutation can satisfy.
        turned = form
        for _ in range(4):
            turned = _rotate(turned)  # type: ignore[arg-type]
        assert turned == form

    def test_rotations_returns_all_four_and_validates_the_alphabet(self) -> None:
        """``_rotations`` is four turns of one written form, no more.

        Seven mutants here survived: the loop count, the accumulation, and
        the alphabet lookup.  A wall form is written as a string and must
        come back as :data:`_Pattern` characters, four distinct ways
        round, so ``_matches`` sees every orientation of a corner.
        """
        rots = _rotations("?W?W..?..")
        assert len(rots) == 4
        assert len(set(rots)) == 4  # a corner is not symmetric
        # The written string is validated into the pattern alphabet rather
        # than asserted to be it: every cell is one of the three.
        assert all(set(rot) <= {"?", "W", "."} for rot in rots)
        # Four turns return the form as written.
        assert rots[-1] == tuple("?W?W..?..")

    def test_matches_honours_each_letter_of_the_form_alphabet(self) -> None:
        """``?`` matches anything, ``W`` a wall, ``.`` a non-wall.

        Six ``_matches`` mutants survived by flipping one of those three
        rules, which whole-program validation absorbs.  Checking each
        letter against both a wall and a non-wall pins the alphabet.
        """
        wall, floor = "+", " "
        # '?' accepts either.
        assert _matches((wall,), ("?",))
        assert _matches((floor,), ("?",))
        # 'W' accepts only a wall, and every wall glyph counts.
        assert _matches((wall,), ("W",))
        assert _matches(("-",), ("W",))
        assert _matches(("|",), ("W",))
        assert not _matches((floor,), ("W",))
        # '.' accepts only a non-wall.
        assert _matches((floor,), (".",))
        assert not _matches((wall,), (".",))
        # Off the grid is not a wall, so the void satisfies '.'.
        assert _matches((_VOID,), (".",))
        assert not _matches((_VOID,), ("W",))

    def test_a_form_and_a_block_of_different_lengths_is_a_bug(self) -> None:
        """``_matches`` zips strictly, so a size mismatch raises.

        Three mutants relaxing that ``strict=True`` survived, because
        every real call passes a 3x3 block against a nine-cell form and a
        relaxed zip is then identical.  It stops being identical the
        moment a form is written with the wrong number of cells -- which
        is the mistake ``strict`` exists to catch, and it would otherwise
        be silently truncated into a rule that matches on a prefix.
        """
        with pytest.raises(ValueError, match="argument"):
            _matches(("+", " "), ("W",))
        with pytest.raises(ValueError, match="argument"):
            _matches(("+",), ("W", "."))
