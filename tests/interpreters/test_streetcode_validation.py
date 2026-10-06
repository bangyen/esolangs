"""What a malformed street looks like, and what the refusal says."""

from pathlib import Path

import pytest

from esolangs.interpreters.grid_based.streetcode import _Machine, run
from esolangs.interpreters.io import IO
from tests.interpreters.streetcode_support import run_street


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
    """Construction-time rejection of one-wide streets (``_validate_width``)."""

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
        neighbours -- the dead-end and vertical arms still catch it.
        """
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
        """Streets are two wide, so a three-lane corridor is malformed."""
        with pytest.raises(ValueError, match="wider than two"):
            run(
                ["+------+", "|C^^^O;|", "|      |", "|      |", "+------+"],
                io=IO(),
            )

    def test_three_by_two_room_is_accepted(self) -> None:
        """The deliberate boundary of the three-by-three rule: a three-by-two
        room is a two-wide street of length three seen sideways.
        """
        _Machine(["+---+", "|C^;|", "|~~~|", "+---+"], IO())

    def test_crossing_of_two_streets_is_accepted(self) -> None:
        """The critical case: where two legal two-wide streets cross, the
        open centre is two-by-two with walls at the diagonals, so no fully
        open three-by-three block exists.
        """
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
        malformed whether or not it happens to contain an instruction.
        """
        with pytest.raises(ValueError, match="not two-wide"):
            _Machine(["+---+", "|C  |", "+---+"], IO())

    def test_grid_without_walls_is_exempt(self) -> None:
        """With no walls there is no street network to measure."""
        _Machine(["CU"], IO())

    def test_wall_hole_is_rejected(self) -> None:
        """A wall that stops and resumes one cell later leaves a gap too
        narrow to drive.  The width check happens to catch this shape
        first, since the hole is a reachable one-wide stub; the wall forms
        reject it independently.
        """
        with pytest.raises(ValueError, match=r"not two-wide|malformed wall"):
            _Machine(["+----+", "|C   |", "|    |", "+- --+"], IO())

    def test_uncapped_divider_end_is_accepted(self) -> None:
        """Whether a divider must end in a '+' is a spec question the wiki
        does not settle, and the forms deliberately leave it open: the
        ring program in tests/fixtures/streetcode_hello.txt draws bare ends
        and runs correctly.
        """
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
        sandwich a single open cell the way a hole does.
        """
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
        so neither its wall nor the pocket it seals is a leftover.
        """
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
        outside, and nothing the repo draws needs it.
        """
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
        road escapes through it to the edge of the grid.
        """
        with pytest.raises(ValueError, match="reaches the edge"):
            _Machine(["+------+", "|C     |", "|      |", "+--  --+"], IO())

    def test_street_open_to_the_grid_edge_is_rejected(self) -> None:
        """A street is bounded by walls, so the road never touches the
        border: there is always a wall between it and the outside.
        """
        with pytest.raises(ValueError, match="reaches the edge"):
            _Machine(["+-----", "|C    ", "|     ", "+-----"], IO())

    def test_horizontal_wall_beside_a_vertical_one_is_rejected(self) -> None:
        """Where a wall changes direction it turns a corner, and a corner
        is drawn '+'.  A '-' next to a '|' is that turn without the mark.
        """
        with pytest.raises(ValueError, match="turns without a corner"):
            _Machine(["+----+", "|C   |", "|    |", "+--|-+"], IO())

    def test_vertical_wall_above_a_horizontal_one_is_rejected(self) -> None:
        """The same slip a quarter turn round."""
        with pytest.raises(ValueError, match="turns without a corner"):
            _Machine(["+--+", "|C |", "|  |", "-  |", "|  |", "+--+"], IO())

    def test_instruction_sealed_inside_an_island_is_rejected(self) -> None:
        """Code the car can never drive is not part of the program."""
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
        a comment.
        """
        with pytest.raises(ValueError, match="not connected"):
            _Machine(["+----+  counts up", "|C   |", "|    |", "+----+"], IO())

    def test_blank_padding_is_not_geometry(self) -> None:
        """A ragged program squared off by ``ljust``, and the background
        around an L-shaped layout, are blank rather than drawn, so they do
        not count as disconnected geometry.
        """
        _Machine(["+----+", "|C   |", "|    |", "+----+", "      "], IO())

    @pytest.mark.parametrize(
        "path",
        ["tests/fixtures/streetcode_hello.txt", "examples/streetcode.txt"],
    )
    def test_shipped_examples_are_accepted(self, path: str) -> None:
        """The repo's own programs must survive the check."""
        root = Path(__file__).resolve().parents[2]
        code = (root / path).read_text().split("\n")
        if code and code[-1] == "":
            code = code[:-1]
        _Machine(code, IO())


def test_an_isolated_cell_is_not_a_street() -> None:
    """One open cell with no neighbour is not a street to drive on."""
    _Machine([" + ", "+C+", " + "], IO())
