"""Covers :mod:`esolangs.tools.clockwise`."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_clockwise,
)


class TestClockwise:
    def test_compact_layout_uses_a_partial_stack_past_the_crossover(self) -> None:
        """Alternating composition beats both old eight-input layouts."""
        table = "01101001" * 32
        flat = boolean.clockwise(table, width=10_000)
        partially_stacked = boolean.clockwise(table, width=8 * 8)
        assert len(partially_stacked) < len(flat)
        assert len(boolean.clockwise(table)) < len(partially_stacked)

    @pytest.mark.medium
    def test_alternating_layout_executes_every_row(self) -> None:
        """The linear layout computes two dense five- and six-input tables."""
        for n in (5, 6):
            size = 1 << n
            tables = (
                ("01101001" * (size // 8))[:size],
                "".join(str((i * 73 + i // 3) & 1) for i in range(size)),
            )
            for table in tables:
                program = boolean.clockwise(table)
                for combo in range(size):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    assert run_clockwise(program, bits) == table[combo]

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),
            ("10", 1),
            ("00", 1),
            ("11", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("00000001", 3),  # AND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination prints the result as an ASCII digit."""
        program = boolean.clockwise(table)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_clockwise(program, bits)
            assert got == table[combo], f"inputs {bits}"

    def test_ring_starts_at_origin(self) -> None:
        """The program is a closed ring whose pointer starts at (0, 0)."""
        program = boolean.clockwise("0110")
        lines = program.splitlines()
        assert lines[0][0] == " "
        assert run_clockwise(program, ["1", "0"]) == "1"  # XOR(1, 0)

    @pytest.mark.parametrize(("table", "n"), [("0001", 2), ("01101001", 3)])
    def test_tree_sits_against_the_left_edge(self, table: str, n: int) -> None:
        """No column is dead: the spine starts as far left as it can.

        The tree's turns are relative, so its absolute column never
        matters; a spine further right is pure padding.  It only has to
        clear the columns its leftward branches span -- three for the pair
        of leaves at the bottom and twice the child's for every level above
        -- or the hoist's eight, leaving column 0 for the closing corner.
        """
        program = boolean.clockwise(table)
        rows = program.splitlines()
        width = max(len(row) for row in rows)
        grid = [row.ljust(width) for row in rows]
        dead = [x for x in range(width) if all(row[x] == " " for row in grid)]
        assert not dead, f"dead columns {dead}"
        assert width == max(3 * 2 ** (n - 1), 8) + 1

    def test_constant_subtrees_narrow_the_ring(self) -> None:
        """A folded subtree spends no displacement, so the grid narrows.

        Width grows as ``2 ** (n + 1)``, and a node only displaces its
        one-branch when it actually branches -- so a table whose subtrees
        collapse needs fewer columns.  A scattered table folds nothing and
        must be unchanged.
        """
        scattered = boolean.clockwise("10010110")
        for table in ("11111111", "11110000"):
            folded = boolean.clockwise(table)
            assert len(folded) < len(scattered), table
        assert len(boolean.clockwise("11001100")) < len(scattered)

    def test_folded_column_still_reads_every_input(self) -> None:
        """A folded column keeps the reads it skipped branching on.

        Clockwise reads *inside* the tree -- seven ``.`` per level -- so a
        folded leaf that dropped them would consume fewer inputs than an
        unfolded one and desync a caller feeding several programs from one
        stream.  Every column therefore carries ``7 * n`` reads.
        """
        for table in ("11111111", "11110000", "11001100"):
            n = len(table).bit_length() - 1
            program = boolean.clockwise(table)
            rows = program.splitlines()
            width = max(len(row) for row in rows)
            grid = [row.ljust(width) for row in rows]
            columns = [sum(1 for row in grid if row[x] == ".") for x in range(width)]
            # the deepest column reads every input; none reads more
            assert max(columns) <= 7 * n, table
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_clockwise(program, bits) == table[combo], (table, bits)

    def test_folding_never_grows_the_program(self) -> None:
        """The hoist floor: narrowing must not cost more than it saves.

        Hoisting the root's seven reads onto row 0 retires seven rows, but
        needs seven free columns left of the root.  At ``n == 2`` a tree
        folded to seven columns loses that and comes out *larger* than the
        unfolded program, so the width never narrows below what the hoist
        needs.
        """
        for n in (1, 2, 3):
            # the alternating table folds nothing at any level, so it is the
            # full-size program every other table must come in at or under
            unfolded = len(boolean.clockwise("10" * (2 ** (n - 1))))
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                assert len(boolean.clockwise(table)) <= unfolded, table

    def test_a_width_stacks_the_tree_and_it_still_computes(self) -> None:
        """A narrower ring is the same function, laid out down instead of across.

        Stacking moves a level's separation from columns into rows, so the
        two subtrees no longer share a bottom row -- which is the whole of
        what could go wrong, since the ring used to close through one.  The
        answer is what says it did not.
        """
        for table in ("01101001", "0110100110010110", "00010111"):
            n = len(table).bit_length() - 1
            flat = boolean.clockwise(table)
            wide = max(len(row) for row in flat.splitlines())
            for width in (8, 10, 14, 20):
                narrow = boolean.clockwise(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                floor = max(
                    len(row) for row in boolean.clockwise(table, 1).splitlines()
                )
                assert columns <= max(width, floor), (table, width, columns)
                if columns < wide:
                    assert len(narrow.splitlines()) > len(flat.splitlines()), (
                        f"{table} at {width} narrowed without spending rows"
                    )
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    assert run_clockwise(narrow, bits) == table[combo], (
                        table,
                        width,
                        bits,
                    )

    def test_stacked_leaves_leave_by_rows_of_their_own(self) -> None:
        """A stacked tree's leaves finish on different rows, and column 0 closes.

        The flat ring funnels its leaves into the corner along the two rows
        a pair shares, one per sibling.  Stacking breaks that by
        construction -- a leaf below another ends lower -- so the exits are
        per-row instead: each ends at a ``!`` in column 0, which only turns
        a path whose accumulator the ``S`` to its left dropped to zero, and
        the ``+`` above it puts the accumulator back so the climb passes the
        exits above without turning on them.
        """
        table = "01101001"
        flat = boolean.clockwise(table)
        stacked = boolean.clockwise(table, 10)

        def exit_rows(program: str) -> list[int]:
            rows = program.splitlines()
            return sorted({y for y, row in enumerate(rows) if row[:1] == "!"})

        assert len(exit_rows(flat)) == 2, "a flat ring closes through a pair's rows"
        assert len(exit_rows(stacked)) > 2, "stacking must spread the exits"
        for y in exit_rows(flat) + exit_rows(stacked):
            assert stacked.splitlines()[y - 1][:1] == "+", (
                f"exit row {y} has no '+' above it to re-arm the climb"
            )
