"""How the car steers: the ambiguous-turn rule, and the two-phase lane merge.

The part of Streetcode the wiki does not spell out, so every rule here is an
interpretation with the examples that corroborate it.
"""

from pathlib import Path

import pytest

from esolangs.interpreters.grid_based.streetcode import (
    _NO_LATCHES,
    _Car,
    _choose_heading,
    _crossing_mouth,
    _Grid,
    _junction_choices,
    _junction_kind,
    _junction_shape,
    _lane_bounded,
    _lawful_turn,
    _left,
    _Machine,
    _Merge,
    _open_toward,
    _right,
    _road_mouth,
    _turn_of,
)
from esolangs.interpreters.io import IO, ScriptedIO
from tests.interpreters.streetcode_support import machine_unvalidated, run_and_capture


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
        stops rather than reporting a mouth through solid wall.
        """
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
        crossbar the car is driving into, still three ways.
        """
        grid = _Grid([" C ", "+|+", "   ", "+ +", " | "])
        assert _junction_shape(grid, _Car(0, 1, "S")) == 3

    def test_one_mouth_with_road_ahead_detects_3(self) -> None:
        """A branch to *one* side, road continuing ahead: three ways.

        The two tests above both have mouths on either side, so they
        only ever reach the first arm of ``_junction_shape``.  Nothing
        asked what a single mouth classifies as, which left the ``and``
        joining the two sides free to be an ``or``.
        """
        left_only = _Grid([" C ", "+ +", "  |", "+ +", " | "])
        right_only = _Grid([" C ", "+ +", "|  ", "+ +", " | "])
        assert _junction_shape(left_only, _Car(0, 1, "S")) == 3
        assert _junction_shape(right_only, _Car(0, 1, "S")) == 3

    def test_one_mouth_with_the_road_ahead_blocked_is_no_junction(self) -> None:
        """One branch and nowhere to go straight is not a junction at all.

        Counting the road behind, that leaves two ways -- a bend, which
        the driving rules handle without a junction choice.  This is the
        ``0`` the one-sided arm returns, and the case that separates it
        from the T above.
        """
        left_only = _Grid([" C ", "+|+", "  |", "+ +", " | "])
        right_only = _Grid([" C ", "+|+", "|  ", "+ +", " | "])
        assert _junction_shape(left_only, _Car(0, 1, "S")) == 0
        assert _junction_shape(right_only, _Car(0, 1, "S")) == 0

    def test_a_plain_corridor_is_no_junction(self) -> None:
        """No mouth on either side, and not driving out through one."""
        grid = _Grid([" C ", "| |", "| |", "| |", " | "])
        car = _Car(0, 1, "S")
        assert not _crossing_mouth(grid, car)
        assert _junction_shape(grid, car) == 0

    def test_turn_into_the_oncoming_lane_is_not_a_road(self) -> None:
        """A turn whose destination has the wall on its left and open road
        on its right would leave the car driving on the left, so it is not
        a road the junction may offer, however open it looks.
        """
        grid = _Grid(self._counting_loop_code())
        car = _Car(5, 9, "E")
        # South from (5,9) enters the lane with the outer wall on its left.
        assert not _lawful_turn(grid, car, "S")
        # North keeps that wall on the right, and is offered.
        assert _lawful_turn(grid, car, "N")

    def test_narrow_arms_are_not_roads(self) -> None:
        """The same shape is not a junction when its arms are one cell:
        streets are two wide, so a single open cell before a wall is the
        width of the road, not a road leading off it.
        """
        grid = _Grid([" C ", "+ +", "   ", "+ +", " | "])
        assert _junction_kind(grid, _Car(0, 1, "S")) == 0

    def test_a_side_road_with_walls_past_its_plus_pair_is_lane_bounded(
        self,
    ) -> None:
        """``_lane_bounded`` reads one cell *past* each ``+``, further out.

        Both grids below present the identical mouth, so the verdict
        turns only on what lies beyond the two ``+``: wall arms
        continuing the side road's own bounding walls, or open ground.
        Only a pair like this separates that read from the neighbouring
        cells a perturbed offset would reach instead -- the counting-loop
        program exercises the function but never contrasts the two.
        """
        bounded = _Grid(["        ", "C       ", "-+  +---", " |  |   ", " |  |   "])
        bare = _Grid(["        ", "C       ", "-+  +---", "        ", "        "])
        car = _Car(1, 0, "E")
        mouth = _road_mouth(bounded, car, "S")
        assert mouth is not None
        assert _road_mouth(bare, car, "S") == mouth, "the mouths must match"
        assert _lane_bounded(bounded, car, "S", mouth)
        assert not _lane_bounded(bare, car, "S", mouth)

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
            "tests/fixtures/streetcode_hello.txt",
            "examples/streetcode.txt",
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
        """The size of each example's drive graph is pinned.

        The junction, merge and heading helpers decide which states are
        reachable, and *no program's output distinguishes them* -- the car
        still reaches its ``;`` and prints the same bytes whichever way a
        turn is resolved.  The graph is what those helpers actually build,
        so it is the observable that can tell them apart: a rule that turns
        one cell early, hugs the wrong wall, or reads a junction's shape
        from the wrong neighbour opens or closes states and moves the
        count.

        The numbers are properties of the committed examples.  If an
        example is redrawn they change with it, and the fix is to re-derive
        them rather than to loosen the assertion.

        They fell from 469 and 316 when the search stopped walking into
        *wrong-side* states -- the oncoming lane travelled backwards, which
        the geometry admits but the car can never occupy (see
        :func:`_drives_on_the_right`).  Those states have no successor of
        their own, so they used to look like wedged streets and made
        ``_validate_total`` reject correct programs.  Every state the car
        actually visits in these examples is right-hand-side, so nothing
        the run needs was pruned.
        """
        root = Path(__file__).resolve().parents[2]
        for path, expected in (
            ("tests/fixtures/streetcode_hello.txt", 384),
            ("examples/streetcode.txt", 268),
        ):
            code = (root / path).read_text().split("\n")
            if code and code[-1] == "":
                code = code[:-1]
            machine = _Machine(code, IO())
            assert machine._graph is not None  # noqa: SLF001
            assert len(machine._graph) == expected, path  # noqa: SLF001

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
        from esolangs.tools import streetcode as gen

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
    the interpreter tests for this trace).
    """

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
        # Ground-truth trace (user-confirmed, see the implementation):
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
        wall-following instead of blindly trusting the stale latch.
        """
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
        a wall that appears directly ahead while merging out.
        """
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
        latch must not wait forever for a target it can no longer reach.
        """
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
        behind, near == -1), there is nothing to drive to: turn now.
        """
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
        user-confirmed trace exists for a four-way junction, and none can
        be taken from the page: neither of the wiki's junction-bearing
        examples contains a four-way at any cell or heading, so this
        fixture is the definition rather than a check against one.

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

    Such a geometry is easy to get wrong: a junction on the ring can offer
    the wrong roads and steer the car off it, leaking out of the lap.  This
    one works, and the rules that make it work (a road must be two cells
    deep, a turn may not enter the oncoming lane, a junction reads the cell
    as the car arrives) are pinned individually above; this is the
    end-to-end program.
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
        on around, and the ninth that leaves.
        """
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
