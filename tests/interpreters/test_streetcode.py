"""Streetcode's instructions, its I/O, and the wiki's own programs.

The larger subjects are siblings: test_streetcode_movement for the steering
rules, test_streetcode_validation for what a malformed street is, and
test_streetcode_states for the drive-state graph.
"""

import io
import re
from contextlib import redirect_stdout

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.streetcode import (
    _VOID,
    _WALLS,
    _Grid,
    _Machine,
    _ReachableCell,
    run,
)
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.streetcode_support import (
    _RING_PROGRAM,
    machine_unvalidated,
    run_and_capture,
    run_street,
)


class TestStreetcodeSingleCommands:
    """Each instruction in isolation."""

    def test_halt_immediately(self) -> None:
        assert run_street("C;") == ""

    def test_increment_then_output(self) -> None:
        assert run_street("C^O;") == chr(1)

    def test_repeated_runs_reuse_validated_geometry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from esolangs.interpreters.grid_based import streetcode

        streetcode._Machine._compile.cache_clear()  # noqa: SLF001
        calls = 0
        validate = streetcode._Machine._validate  # noqa: SLF001

        def counted(machine: _Machine, start: tuple[int, int]) -> None:
            nonlocal calls
            calls += 1
            validate(machine, start)

        monkeypatch.setattr(streetcode._Machine, "_validate", counted)  # noqa: SLF001
        assert run_street("C^O;") == chr(1)
        assert run_street("C^O;") == chr(1)
        assert calls == 1
        streetcode._Machine._compile.cache_clear()  # noqa: SLF001

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
        fallback.
        """
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
        ends there, and that lane cell is executed on the next step.
        """
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
        the east lane two steps later, not westbound and then southbound.
        """
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
    def test_cp_decrement_below_zero_is_clamped(self) -> None:
        """``_`` at CP 0 moves nothing rather than raising.

        The wiki bounds CP on the left ("The CP is unsigned and
        right-unbounded") but never says what a below-zero ``_`` does -- no
        example uses ``_``, and the page has no error-handling text.  An
        unsigned quantity that cannot go lower saturates, which is also how
        brainfuck's ``<`` and CVNC's accumulator behave.  This used to
        raise ``HaltError``.
        """
        assert run_street("C_^O;") == chr(1)
        # repeated clamping stays on cell 0 rather than drifting
        assert run_street("C___^O;") == chr(1)

    def test_cp_can_move_right_and_back_to_zero(self) -> None:
        assert run_street("C=_^O;") == chr(1)

    def test_output_of_out_of_range_cell_halts(self) -> None:
        """A cell value that isn't a valid code point is invalid, not a crash."""
        with pytest.raises(HaltError):
            run(["C~~~~~~~~~~~~~O;"], io=IO())  # cell reaches a large negative


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


def test_a_counting_ring_program_drives_its_whole_lap() -> None:
    """The lap follows the latched merge through to the turn."""
    assert run_and_capture(_RING_PROGRAM) == "Hi"
