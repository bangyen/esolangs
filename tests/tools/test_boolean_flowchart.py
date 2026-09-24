"""Covers :mod:`esolangs.tools.flowchart`."""

from itertools import pairwise

import pytest

from esolangs import tools as boolean
from esolangs.interpreters.io import IO
from esolangs.tools.flowchart import _flowchart_deque
from esolangs.tools.other import (
    _flowchart_cells,
    _flowchart_render,
    _flowchart_stacked,
)
from tests.tools.boolean_runners import (
    run_flowchart,
)


class TestFlowchart:
    """The Flowchart boolean generator (works for arbitrary n)."""

    @pytest.mark.parametrize(
        "table",
        ["00", "01", "0000", "0110", "11111111", "01101001", "0110100110010110"],
    )
    def test_an_unconstrained_call_returns_the_shortest_layout(
        self, table: str
    ) -> None:
        """Without a width every candidate is built and the shortest wins.

        Three layouts compete: the flat tree, its stacked form, and the
        deque lookup.  The deque takes the small arities too (it is about
        six times shorter than the tree at ``n = 4``), but a table that
        folds to one or two leaves still goes to the tree, so the contract
        is the minimum rather than any one construction.
        """
        candidates = [
            _flowchart_render(_flowchart_cells(table)),
            _flowchart_render(_flowchart_stacked(table)),
            _flowchart_deque(table),
        ]
        chosen = boolean.flowchart(table)
        assert len(chosen) == min(len(c) for c in candidates)
        assert chosen in candidates

    def test_a_stacked_parity_tree_beats_the_flat_one(self) -> None:
        """From three inputs the stacked orientation is the shorter tree."""
        table = "01101001"
        flat = _flowchart_render(_flowchart_cells(table))
        stacked = _flowchart_render(_flowchart_stacked(table))
        assert len(stacked) < len(flat)
        assert boolean.flowchart(table, 1) == stacked

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0111", 2),  # OR
            ("0110", 2),  # XOR
            ("1110", 2),  # NAND
            ("01101001", 3),  # XOR3
            ("11111110", 3),  # NAND3
            ("0110100110010110", 4),  # XOR4
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result.

        The read count is checked alongside the answer: a folded leaf
        carries the reads of the levels it skipped, so a heavily folding
        table (the constants, AND4) must still consume all ``n`` inputs.
        Without those the drawing would be correct and the program would
        still leave the caller's remaining bits on the stream.
        """
        import contextlib

        from esolangs.interpreters.grid_based.flowchart import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_cycle

        program = boolean.flowchart(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_flowchart(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"
        io = ScriptedIO("0\n" * (n + 4))
        with contextlib.suppress(Exception, SystemExit):
            run_until_halt_or_cycle(_Machine(program.splitlines(), io))
        assert io.position() == n, (
            f"table {table} consumed {io.position()} inputs, expected {n}"
        )

    @pytest.mark.medium
    def test_wide_deque_lookup_executes_every_row(self) -> None:
        """The cursor walk lands on exactly the indexed answer's deque."""
        n = 6
        table = "".join(str((row.bit_count() ^ (row >> 2)) & 1) for row in range(2**n))
        program = boolean.flowchart(table)
        for row in range(2**n):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_flowchart(program, bits) == table[row], row

    def test_wide_deque_lookup_scales_linearly(self) -> None:
        """The two-row layout grows no faster than its table doubles."""
        sizes = [len(boolean.flowchart("01" * (2 ** (n - 1)))) for n in range(7, 11)]
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
        for row in (0, 1, 2, 3, 17, 30, 31):
            bits = [str((row >> (4 - i)) & 1) for i in range(5)]
            assert run_flowchart(program, bits) == table[row], row

    def test_tree_depth_matches_input_count(self) -> None:
        """One ``/ /`` read node sits on each path from entry to a leaf."""
        program = _flowchart_render(_flowchart_cells("0110100110010110"))
        assert program.count("< >") == 15  # 2**4 - 1 internal nodes
        assert program.count("(( ))") == 16  # 2**4 leaves

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
        # the fold is deep enough that a constant table keeps the tree
        assert boolean.flowchart("11111111") == tree("11111111")

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

    def test_each_run_reads_exactly_n_bits(self) -> None:
        """The drawn read nodes outnumber the reads any one run performs.

        A depth-4 tree draws 15 ``/ /`` nodes, but a run walks a single
        root-to-leaf path and consumes exactly 4 bits, so the duplication is
        spatial rather than a bit being read more than once (see the
        generator's docstring on why the parameterized once-only embedding
        rule does not apply to an input-reading generator).
        """
        program = _flowchart_render(_flowchart_cells("0110100110010110"))
        assert program.count("/ /") == 15

        consumed = 0

        class _CountingIO(IO):
            def input_str(self, _prompt: str = "Input: ") -> str:
                nonlocal consumed
                consumed += 1
                return "1"

            def print_str(self, text: str) -> None:
                pass

        from esolangs.interpreters.grid_based.flowchart import run as fc_run

        fc_run(program.splitlines(), _CountingIO())
        assert consumed == 4

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
            n = len(table).bit_length() - 1
            flat = _flowchart_render(_flowchart_cells(table))
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.flowchart(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 12, 20, wide):
                narrow = boolean.flowchart(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = run_flowchart(narrow, [str(b) for b in bits])
                    assert got == table[combo], (table, width, bits)

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
            assert max(len(row) for row in flat.splitlines()) == 5 * 2**n, n
            assert len(stacked.splitlines()) > len(flat.splitlines()), n
        # A table that folds to a single leaf is already as wide as one
        # ``(( ))``, and stacking spends a corridor column per level on top
        # of that -- so there the flat drawing is the narrower of the two
        # and asking for any width keeps it.
        assert boolean.flowchart("1111", 1) == boolean.flowchart("1111")

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
