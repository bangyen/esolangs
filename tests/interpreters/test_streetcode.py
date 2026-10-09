"""Streetcode's instructions, its I/O, and the wiki's own programs."""

import io
import re
from contextlib import redirect_stdout

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.streetcode import _Machine, run
from esolangs.interpreters.grid_based.streetcode.geometry import (
    _ReachableCell,
)
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.streetcode_support import (
    _RING_PROGRAM,
    machine_unvalidated,
    run_and_capture,
    run_street,
)
from tests.raises import assert_rejected_with_hint


class TestStreetcodeSingleCommands:
    """Each instruction in isolation."""

    def test_decrement_below_zero_then_output_is_invalid(self) -> None:
        """A cell of -1 is a valid signed int, but not a valid code point."""
        with pytest.raises(HaltError):
            run(["C~O;"], io=IO())

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


class TestStreetcodeHalt:
    def test_semicolon_halts_immediately(self) -> None:
        assert run_street("C;^O") == ""

    def test_program_without_semicolon_runs_until_dead_end(self) -> None:
        """No halt instruction: a dead-end corridor still stops."""
        assert run_and_capture(["C"]) == ""


class TestStreetcodeIO:
    def test_input_echoed_via_cpth_cell(self) -> None:
        assert run_street("CIO;", inputs=["X"]) == "X"

    def test_input_reads_only_first_character_of_line(self) -> None:
        assert run_street("CIO;", inputs=["hello"]) == "h"

    def test_newline_input_is_preserved(self) -> None:
        assert run_street("CIO;", inputs=[""]) == chr(10)

    def test_exhausted_input_raises_eof(self) -> None:
        machine = _Machine(["CI;"], ScriptedIO(""))
        machine.step()  # 'C'
        with pytest.raises(EOFError):
            machine.step()  # 'I' with no input left at all


class TestStreetcodeCPBounds:
    def test_cp_decrement_below_zero_raises(self) -> None:
        """``_`` at CP 0 aborts: the CP is unsigned, no cell lies left of 0."""
        with pytest.raises(HaltError, match="unsigned CP below zero"):
            run_street("C_^O;")
        with pytest.raises(HaltError, match="unsigned CP below zero"):
            run_street("C=__^O;")

    def test_cp_can_move_right_and_back_to_zero(self) -> None:
        assert run_street("C=_^O;") == chr(1)

    def test_output_of_out_of_range_cell_halts(self) -> None:
        """A cell value that isn't a valid code point is invalid, not a crash."""
        with pytest.raises(HaltError):
            run(["C~~~~~~~~~~~~~O;"], io=IO())  # cell reaches a large negative


class TestStreetcodeStatedInvariants:
    """The invariants the interpreter relies on, as executable checks."""

    def _street(self) -> list[str]:
        return ["+----+", "|C  ;|", "|    |", "+----+"]

    def test_a_border_cell_trips_the_block_precondition(self) -> None:
        """``_block`` states what it needs rather than trusting the caller."""
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
        """The rule and the rejection are one statement, not two."""
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
        """The U-turn cat echoes input characters in order, then hangs on EOF."""
        code = ["UOI ", "CIOU"]
        scripted = ScriptedIO("A\nB\nC")
        with pytest.raises(EOFError):
            run(code, io=scripted)
        assert scripted.getvalue() == "A\nB\nC"

    def test_infinite_cat_runs_with_its_us_replaced_by_spaces(self) -> None:
        """The wiki: "The Us can be replaced with spaces" -- dead ends turn."""
        scripted = ScriptedIO("A\nB\nC")
        with pytest.raises(EOFError):
            run([" OI ", "CIO "], io=scripted)
        assert scripted.getvalue() == "A\nB\nC"

    def test_a_cursorless_cat_is_not_a_cycle(self) -> None:
        """Reads count in the snapshot: the cat runs to EOF, not a false cycle."""
        from tests.interpreters.cursorless_io import CursorlessIO

        machine = _Machine(["UOI ", "CIOU"], CursorlessIO("aaaaaaaa"))
        with pytest.raises(EOFError):
            run_until_halt_or_cycle(machine)

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
        """The loop's lap, pinned cell by cell against a hand-checked trace."""
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
        """The wiki's rhetorical "Why wouldn't this be a cat?" -- it is one."""
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
        assert io_obj.getvalue() == "A\nB"


def test_a_counting_ring_program_drives_its_whole_lap() -> None:
    """The lap follows the latched merge through to the turn."""
    assert run_and_capture(_RING_PROGRAM) == "Hi"


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Streetcode", "zzz", "exactly one C")
