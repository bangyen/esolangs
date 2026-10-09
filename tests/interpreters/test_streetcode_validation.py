"""What a malformed street looks like, and what the refusal says."""

from pathlib import Path

import pytest

from esolangs.interpreters.grid_based.streetcode import _Machine, run
from esolangs.interpreters.io import IO
from tests.interpreters.streetcode_support import run_street


class TestStreetcodeMalformedPrograms:
    @pytest.mark.parametrize(
        ("code", "match"),
        [
            pytest.param([], "empty", id="empty_program_is_malformed"),
            pytest.param(["   ", ""], "empty", id="blank_only_program_is_malformed"),
            pytest.param(["   ", " ; "], "exactly one C", id="no_car_is_malformed"),
            pytest.param(
                ["C  ", "  C"], "exactly one C", id="multiple_cars_is_malformed"
            ),
            # A single instruction row between two walls has no second lane.
            pytest.param(
                ["+----+", "|C^O;|", "+----+"],
                "not two-wide",
                id="one_wide_dead_end_is_rejected",
            ),
            # Off-grid counts as closed, so an edge row is still one-wide.
            pytest.param(
                ["C^O;", "+---+"],
                "not two-wide",
                id="one_wide_against_grid_edge_is_rejected",
            ),
            # Every cell is a corner, so no cell has an opposite pair of
            # neighbours -- the dead-end and vertical arms still catch it.
            pytest.param(
                [
                    "+-+    ",
                    "|C|    ",
                    "|^+-+  ",
                    "|^^^|  ",
                    "+-+^|  ",
                    "  |;|  ",
                    "  +-+  ",
                ],
                "not two-wide",
                id="one_wide_staircase_is_rejected",
            ),
            # Streets are two wide, so a three-lane corridor is malformed.
            pytest.param(
                ["+------+", "|C^^^O;|", "|      |", "|      |", "+------+"],
                "wider than two",
                id="wider_than_two_is_rejected",
            ),
        ],
    )
    def test_refused(self, code: list[str], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            run(code, io=IO())


class TestStreetcodeStreetWidth:
    """Construction-time rejection of one-wide streets (``_validate_width``)."""

    def test_two_wide_street_is_accepted(self) -> None:
        """An instruction lane with an oncoming lane beside it is legal."""
        assert run_street("C^O;") == chr(1)

    @pytest.mark.parametrize(
        "code",
        [
            # The boundary of the three-by-three rule: a three-by-two room is a
            # two-wide street of length three seen sideways.
            pytest.param(
                ["+---+", "|C^;|", "|~~~|", "+---+"], id="three_by_two_room_is_accepted"
            ),
            # Where two legal streets cross, the open centre is two-by-two with
            # walls at the diagonals: no fully open three-by-three block.
            pytest.param(
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
                id="crossing_of_two_streets_is_accepted",
            ),
            # With no walls there is no street network to measure.
            pytest.param(["CU"], id="grid_without_walls_is_exempt"),
            # Whether a divider must end in a '+' the wiki does not settle; the
            # ring in tests/fixtures/streetcode_hello.txt draws bare ends.
            pytest.param(
                [
                    "+------+",
                    "|C     |",
                    "|      |",
                    "+  ----+",
                    "|      |",
                    "|      |",
                    "+------+",
                ],
                id="uncapped_divider_end_is_accepted",
            ),
            # A mouth is at least two cells across, so its '+' markers never
            # sandwich a single open cell the way a hole does.
            pytest.param(
                [
                    "+--------+",
                    "|C       |",
                    "|        |",
                    "+--+  +--+",
                    "   |  |   ",
                    "   |  |   ",
                    "   +--+   ",
                ],
                id="road_mouth_is_accepted",
            ),
            # An island is a block the car drives around, so neither its wall
            # nor the pocket it seals is a leftover.
            pytest.param(
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
                id="island_inside_a_ring_is_accepted",
            ),
            # ``ljust`` padding and the background around an L-shaped layout
            # are blank, not drawn, so not disconnected geometry.
            pytest.param(
                ["+----+", "|C   |", "|    |", "+----+", "      "],
                id="blank_padding_is_not_geometry",
            ),
            # One open cell with no neighbour is not a street to drive on.
            pytest.param([" + ", "+C+", " + "], id="an_isolated_cell_is_not_a_street"),
        ],
    )
    def test_accepted(self, code: list[str]) -> None:
        _Machine(code, IO())

    @pytest.mark.parametrize(
        ("code", "match"),
        [
            # A one-wide grid is malformed whether or not it holds an instruction.
            pytest.param(
                ["+---+", "|C  |", "+---+"],
                "not two-wide",
                id="wall_fragment_without_instructions_is_rejected",
            ),
            # A wall that stops and resumes one cell later leaves a gap too
            # narrow to drive; the width check catches it first (a reachable
            # one-wide stub), and the wall forms reject it independently.
            pytest.param(
                ["+----+", "|C   |", "|    |", "+- --+"],
                r"not two-wide|malformed wall",
                id="wall_hole_is_rejected",
            ),
            # A second box the car can never reach belongs to no street.
            pytest.param(
                ["+----+   +--+", "|C   |   |  |", "|    |   |  |", "+----+   +--+"],
                "not connected",
                id="detached_geometry_is_rejected",
            ),
            # A scribble of wall outside the program bounds no road.
            pytest.param(
                ["+----+", "|C   |", "|    |", "+----+", "   -- "],
                "not connected",
                id="stray_wall_fragment_is_rejected",
            ),
            # A block thick enough to have an interior: its outer ring bounds the
            # road, but the cells inside bound nothing.  Permitting it would cost
            # a second flood-fill, and nothing the repo draws needs it.
            pytest.param(
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
                "not connected",
                id="solid_island_is_rejected",
            ),
            # A two-cell hole is a legal-width passage, so the width check has no
            # reason to fire: the road escaping through it to the edge does.
            pytest.param(
                ["+------+", "|C     |", "|      |", "+--  --+"],
                "reaches the edge",
                id="two_wide_hole_in_a_wall_is_rejected",
            ),
            # Walls bound a street, so the road never touches the border.
            pytest.param(
                ["+-----", "|C    ", "|     ", "+-----"],
                "reaches the edge",
                id="street_open_to_the_grid_edge_is_rejected",
            ),
            # A wall that changes direction turns a corner, drawn '+'; a '-'
            # next to a '|' is that turn without the mark.
            pytest.param(
                ["+----+", "|C   |", "|    |", "+--|-+"],
                "turns without a corner",
                id="horizontal_wall_beside_a_vertical_one_is_rejected",
            ),
            # The same slip a quarter turn round.
            pytest.param(
                ["+--+", "|C |", "|  |", "-  |", "|  |", "+--+"],
                "turns without a corner",
                id="vertical_wall_above_a_horizontal_one_is_rejected",
            ),
            # Code the car can never drive is not part of the program.
            pytest.param(
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
                "not connected",
                id="instruction_sealed_inside_an_island_is_rejected",
            ),
            # Strictness: prose beside a program is malformed, not a comment.
            pytest.param(
                ["+----+  counts up", "|C   |", "|    |", "+----+"],
                "not connected",
                id="text_beside_the_program_is_rejected",
            ),
        ],
    )
    def test_refused(self, code: list[str], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            _Machine(code, IO())

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
