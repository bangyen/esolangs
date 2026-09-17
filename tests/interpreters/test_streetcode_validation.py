"""What a malformed street looks like, and what the refusal says.

Two-wide streets, walls that enclose the road, the three neighbourhood forms,
and the message each violation names itself with.
"""

from pathlib import Path
from typing import ClassVar

import pytest

from esolangs.interpreters.grid_based.streetcode import (
    _VOID,
    _Machine,
    _matches,
    _rotate,
    _rotations,
    run,
)
from esolangs.interpreters.io import IO
from tests.interpreters.streetcode_support import run_street
from tests.raises import raises_message


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
    """Every rejection paired with the message it must raise.

    The tests elsewhere use ``pytest.raises(match=...)``, a *substring*
    search, so a rejection firing in the wrong place still passes: all
    four width failures share the prefix ``not two-wide``, and the shape
    label in parentheses is the only part that says which arm fired.  The
    coordinates each message quotes were never asserted at all.

    One case shows the hazard directly.  The wall-hole program is asserted
    against ``not two-wide|malformed wall``, and it resolves to the width
    check -- so the second half of that alternation has never fired, and a
    mutant moving the rejection between the two would not be noticed.
    """

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
    """One open cell with no neighbour is not a street to drive on.

    The network is built by flooding outward from each open cell; a cell
    that reaches nothing else is a hole in the walls rather than a lane,
    so it is not registered as a street at all.
    """
    _Machine([" + ", "+C+", " + "], IO())


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
