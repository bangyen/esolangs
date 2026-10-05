"""Covers :mod:`esolangs.tools.streetcode`.

Named for the generator, not the interpreter: tests/interpreters/test_streetcode
covers the car that drives what this emits.
"""

from importlib import import_module

import pytest

from esolangs import tools as boolean
from esolangs.tools.wrap import shortest


def _columns(program: str) -> int:
    """The widest row of a grid program, which is what a width bounds."""
    return max(len(line) for line in program.split("\n"))


@pytest.mark.medium
class TestStreetcode:
    def test_the_flat_lookup_is_nine_rows_at_every_arity(self) -> None:
        """The layout is a street, so the rectangle is linear by its height.

        The tree it replaced spent area on both axes; this spends it on one.
        Nine rows is the shape -- a room's roof, its two lanes, its floor,
        the stalk, the street's kerb, its two lanes and its sill -- and the
        columns are the fill plus the rooms, so the rectangle is the
        per-entry constant times a fixed height.
        """
        for n in range(6, 12):
            table = "".join(str(index.bit_count() & 1) for index in range(2**n))
            program = boolean.streetcode(table)
            rows = program.splitlines()
            assert len(rows) == 9, n
            assert len(rows) * max(map(len, rows)) <= 18 * 2**n + 3200, n
            assert len(program) <= 11 * 2**n + 3000, n

    def test_compact_layout_compares_both_rotations(self) -> None:
        """Rotation strips the dense tree's leading triangular padding."""
        from esolangs.tools.streetcode import _streetcode_rotate

        table = "01101001"
        original = boolean.streetcode(table, width=10_000)
        rotated = _streetcode_rotate(original)
        assert len(rotated) < len(original)
        assert boolean.streetcode(table) == rotated

    def test_default_uses_only_shared_layouts(self) -> None:
        """Through five inputs, defaults choose only shared layouts."""
        module = import_module("esolangs.tools.streetcode")

        for n in (1, 2, 3, 5):
            values = (0x9466E472,) if n == 5 else range(1 << (1 << n))
            for value in values:
                table = format(value, f"0{1 << n}b")
                tree = module._streetcode_tree(table)  # noqa: SLF001
                shared = module._streetcode_shared_programs(table, n, tree)  # noqa: SLF001
                all_programs = [
                    *shared,
                    *(module._streetcode_rotate(p) for p in shared),  # noqa: SLF001
                ]
                assert boolean.streetcode(table) == shortest(*all_programs)

    def test_constant_subtrees_fold(self) -> None:
        """A subtree whose rows agree prints instead of driving down halls.

        Streetcode splits most-significant-first, so a subtree is a
        contiguous run: ``11110000`` is two constant halves and collapses,
        while ``10101010`` is constant over no run and keeps every hall.
        """
        constant = len(boolean.streetcode("11111111"))
        halves = len(boolean.streetcode("11110000"))
        scattered = len(boolean.streetcode("10101010"))
        assert constant < scattered
        assert halves < scattered

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        """The tree splits in whichever order folds most, not input order.

        ``10101010`` depends on the last input alone, so it folds nothing
        splitting most-significant-first and everything once that input is
        tested at the root.  Reordering is what lets it be emitted as the
        cheap shape, and it costs only the walk that puts the bit in the
        cell the root's hall tests.
        """
        scattered = len(boolean.streetcode("10101010"))
        aligned = len(boolean.streetcode("11110000"))
        parity = len(boolean.streetcode("01101001"))
        # Both are one-dependency tables, so reordering brings the scattered
        # one down to the aligned one's shape.  It stays a few characters
        # longer, and those characters are the walk that puts its bit in the
        # cell the root's hall tests -- the price of the reorder, paid once
        # in the prefix rather than per hall.
        assert aligned < scattered < parity
        assert scattered - aligned < 0.05 * aligned

    def test_input_reordering_never_grows_a_program(self) -> None:
        """The identity order is built first and ties keep it.

        A table no reorder improves has to emit exactly what it emitted
        before, so reordering can only ever shrink a program.  ``01101001``
        is parity, which folds under no order at all.
        """
        parity = boolean.streetcode("01101001")
        # Parity is the table where every order is equally bad, so the
        # program is the identity one and carries no reordering walks.
        assert "_I" not in parity

    def test_width_is_a_shape_choice(self) -> None:
        """A width picks a narrower shape, and that shape still computes.

        The hallway trades columns for rows, so a width the default overruns
        is met by a shape that was built anyway, at the cost of rows. A
        Streetcode program cannot
        be reflowed after the fact, so this is the only way a width is met.
        """
        table = "10"
        default = boolean.streetcode(table)
        narrow = boolean.streetcode(table, 25)
        assert _columns(narrow) <= 25 < _columns(default)
        assert narrow.count("\n") > default.count("\n")

    def test_width_takes_the_narrowest_when_none_fits(self) -> None:
        """Below every shape's width the narrowest one is returned.

        The nine-row indexed street becomes the nine-column width floor.
        """
        table = "10"
        program = boolean.streetcode(table, 1)
        assert _columns(program) == min(
            _columns(boolean.streetcode(table, w)) for w in (1, 25, 100)
        )

    def test_a_requested_width_is_never_overrun(self) -> None:
        """A width that *can* be met is met, measured on the emitted columns.

        The width is a promise about the widest row, and the only way to
        keep it is to pick a shape that already fits, so measuring the
        wrong thing -- splitting the program on whitespace rather than on
        newlines, say -- selects a shape that overruns while every
        truth-table check still passes.  ``0001`` at 33 is the tight case:
        the winning shape is exactly 33 columns, so a column count that
        drifts either way changes which shape is returned.
        """
        for table, width in (("0001", 33), ("0110", 33), ("01", 29)):
            program = boolean.streetcode(table, width)
            assert _columns(program) <= width, (table, width)

    def test_the_narrowest_fallback_is_really_the_narrowest(self) -> None:
        """Below every shape's width, the narrowest shape comes back.

        ``0100`` previously returned a 33-column hallway; the rotated
        indexed street shares its kerb and needs seven, with the same answers.
        """
        program = boolean.streetcode("0100", 1)
        assert _columns(program) == 7

    def test_a_width_equal_to_a_shape_is_wide_enough(self) -> None:
        """The fit test is inclusive: exactly the shape's width fits it.

        At its own column count the default shape still fits, so asking for
        exactly that many columns must return it rather than falling
        through to a narrower, longer one.  One column more is the same
        program; the suite otherwise only asks for 1, 25 and 100, none of
        which lands on a boundary.
        """
        default = boolean.streetcode("01")
        assert _columns(default) == 29
        assert boolean.streetcode("01", 29) == default
        assert boolean.streetcode("01", 30) == default

    def test_no_trailing_blank_row(self) -> None:
        """The grid ends on its last real row.

        The row count is one plus the deepest row written, and an off-by-one
        there appends an empty row that the interpreter walks over
        harmlessly -- invisible to every behavioural check.
        """
        for table in ("01", "0101", "0110", "11111110"):
            program = boolean.streetcode(table)
            assert not program.endswith("\n"), table
            assert program.split("\n")[-1].strip(), table

    def test_the_program_is_only_streetcode_characters(self) -> None:
        """Only the glyphs Streetcode reads, plus layout space.

        Measured over every table through three inputs and a spread of
        widths rather than read off the spec: the generator uses a subset,
        and asserting the spec's full set would pass vacuously.
        """
        allowed = set(" +-;=CIOU^_|~\n")
        for table in ("01", "0000", "0110", "11111110"):
            assert set(boolean.streetcode(table)) <= allowed, table
        for width in (1, 20, 29, 33):
            assert set(boolean.streetcode("0110", width)) <= allowed, width

    def test_only_identity_and_greedy_orders_are_offered(self) -> None:
        """Streetcode never renders more than two order candidates."""
        from esolangs.tools.helpers import input_orders

        table = "01011010"
        assert input_orders(table)[0] == (0, 1, 2)
        assert len(input_orders(table)) <= 2


def test_a_width_past_the_crossover_still_chooses_a_shape() -> None:
    """Past the crossover a quarter turn gives the shared seven-column floor."""
    table = "0110100110010110" * 4
    both = (boolean.streetcode(table), _columns(boolean.streetcode(table)))
    assert boolean.streetcode(table, 10_000) == both[0]
    assert _columns(boolean.streetcode(table, 1)) == 7


def test_quarter_turned_rendered_size_is_linear() -> None:
    from itertools import pairwise

    sizes = [
        len(boolean.streetcode("01101001" * (2 ** (n - 3)), 1)) for n in (5, 6, 7, 8)
    ]
    assert all(later < 2 * earlier for earlier, later in pairwise(sizes))
