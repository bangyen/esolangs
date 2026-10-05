"""Covers :mod:`esolangs.tools.flowchart`."""

from itertools import pairwise

import pytest

from esolangs import tools as boolean
from esolangs.interpreters.io import IO
from esolangs.tools.flowchart import (
    _flowchart_cells,
    _flowchart_deque,
    _flowchart_render,
    _flowchart_stacked,
)


class TestFlowchart:
    """The Flowchart boolean generator (works for arbitrary n)."""

    @pytest.mark.parametrize(
        "table",
        ["00", "01", "0000", "0110", "11111111", "01101001", "0110100110010110"],
    )
    def test_an_unconstrained_call_uses_the_deque(self, table: str) -> None:
        """Tree layouts remain available for width requests."""
        assert boolean.flowchart(table) == _flowchart_deque(table)

    def test_a_stacked_parity_tree_beats_the_flat_one(self) -> None:
        """From three inputs the stacked orientation is the shorter tree."""
        table = "01101001"
        flat = _flowchart_render(_flowchart_cells(table))
        stacked = _flowchart_render(_flowchart_stacked(table))
        assert len(stacked) < len(flat)
        assert boolean.flowchart(table, 1) == stacked

    def test_wide_deque_lookup_scales_linearly(self) -> None:
        """The two-row layout grows no faster than its table doubles."""
        sizes = [
            len(
                boolean.flowchart(
                    "".join(str(row.bit_count() % 2) for row in range(1 << n))
                )
            )
            for n in range(7, 11)
        ]
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    def test_a_repeated_answer_is_set_once_and_pushed_twice(self) -> None:
        """A run of equal entries shares one set node and still answers.

        Neither the push nor the deque step touches the register, so the
        preload only re-sets it where the table changes; an alternating
        table (the one the scaling test uses) never exercises that, which is
        why this one repeats.
        """
        table = "0011" * 8
        program = boolean.flowchart(table)
        assert program.count("[ }") + program.count("{ ]") < len(table)

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice is one leaf, and takes one column band.

        The leaves keep their pitch but are handed out as the walk reaches
        them, so a folded subtree narrows the drawing rather than leaving a
        gap where its rows would have been.
        """

        def tree(table: str) -> str:
            return _flowchart_render(_flowchart_cells(table))

        assert tree("11111111").count("(( ))") == 1
        assert tree("11110000").count("(( ))") == 2
        assert tree("10010110").count("(( ))") == 8  # no fold
        # a constant table needs no switch at all
        assert tree("11111111").count("< >") == 0
        assert tree("11110000").count("< >") == 1
        # a width request retains the folded tree
        assert boolean.flowchart("11111111", 80) == tree("11111111")

    @pytest.mark.parametrize(
        "table", ["01", "0001", "01101001", "0110100110010110", "1000000000000000"]
    )
    def test_vertical_rails_meet_node_middles(self, table: str) -> None:
        """Every ``│`` connects to the middle of the node above and below it.

        The wiki asks that "vertical paths connecting into a node are expected
        to connect to the middle of the node", and all three of its worked
        examples honour it.  The interpreter is deliberately lenient about
        this -- it enters a node through any cell of its box, which is why an
        earlier, misdrawn version of this tree still computed the right table
        -- so nothing else would catch the drawing drifting off centre.

        The rule is about vertical rails only: the Kolakoski example's top row
        chains nodes horizontally (``( )─[ }─\\[ ]/``), attaching at their end
        cells rather than their middles.
        """
        from esolangs.interpreters.grid_based.flowchart import _Machine

        drawing = _flowchart_render(_flowchart_cells(table))
        machine = _Machine(drawing.splitlines(), IO())
        for row, line in enumerate(machine.grid):
            for col, char in enumerate(line):
                if char != "│":
                    continue
                for neighbour in (row - 1, row + 1):
                    node = machine.nodes.get((neighbour, col))
                    if node is None:
                        continue
                    spelling, start = node
                    middle = start + len(spelling) // 2
                    assert col == middle, (
                        f"rail at ({col}, {row}) meets {spelling!r} at column {col}, "
                        f"but its middle is column {middle}"
                    )

    def test_rejects_a_malformed_table(self) -> None:
        """A table whose length is not a power of two is rejected."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.flowchart("011")

    def test_a_width_stacks_the_tree_onto_one_column(self) -> None:
        """A narrower drawing is the same tree, separated by rows not columns.

        Neither branch may simply continue down -- a switch entered
        travelling down sends 1 east and 0 west -- so both are caught by
        corners and routed, and only running it says the routing kept every
        path on its own leaf.
        """
        for table in ("0110", "01101001", "0110100110010110"):
            flat = _flowchart_render(_flowchart_cells(table))
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.flowchart(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 12, 20, wide):
                narrow = boolean.flowchart(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)

    def test_stacking_costs_rows_and_stops_tracking_the_table(self) -> None:
        """The stacked drawing is ``n + 5`` columns whatever the table.

        That is the whole of the trade: the flat drawing gives every leaf a
        column and grows as ``2 ** n``, and stacking puts every node on one
        column and grows as ``2 ** n`` in *rows* instead.
        """
        for n in (2, 3, 4):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            flat = _flowchart_render(_flowchart_cells(table))
            stacked = boolean.flowchart(table, 1)
            assert max(len(row) for row in stacked.splitlines()) == n + 5, n
            assert max(len(row) for row in flat.splitlines()) == 6 * 2**n - 1, n
            assert len(stacked.splitlines()) > len(flat.splitlines()), n
        # A table that folds to a single leaf is already as wide as one
        # ``(( ))``, and stacking spends a corridor column per level on top
        # of that -- so there the flat drawing is the narrower of the two
        # and asking for any width keeps it.
        assert boolean.flowchart("1111", 1) == _flowchart_render(
            _flowchart_cells("1111")
        )

    def test_a_stacked_corridor_belongs_to_its_depth(self) -> None:
        """Depth ``d``'s zero-branch falls down column ``d``, and nothing else.

        That is what makes the corridors crossing-free: everything below a
        node is deeper, and so further east, while the rail that reaches
        the corridor runs on the switch's own row, above every descendant.
        So the left ``n`` columns carry only line, never a node -- a rail
        reaching a further-left corridor does pass through them -- and no
        cell ever has to be a ``┼``, which is the check that says a rail and
        a corridor never meet.
        """
        table = "0110100110010110"
        n = 4
        drawing = boolean.flowchart(table, 1)
        rows = drawing.splitlines()
        width = max(len(row) for row in rows)
        grid = [row.ljust(width) for row in rows]
        for x in range(n):
            column = {row[x] for row in grid} - {" "}
            assert column <= set("│┌└─"), (x, column)
        assert "┼" not in drawing, "a rail crossed a corridor"
