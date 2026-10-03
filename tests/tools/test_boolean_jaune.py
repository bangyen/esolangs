"""Covers :mod:`esolangs.tools.jaune`: the tree, its sharing, the linear lookup."""

from itertools import pairwise

from esolangs import tools as boolean
from esolangs.tools.helpers import best_input_order
from esolangs.tools.jaune import _jaune_ordered
from tests.tools.plain_oracles import _jaune_linear
from tests.tools.sample_tables import five_input_sample


class TestJaune:
    def test_unused_inputs_are_clobbered_not_stored(self) -> None:
        """An input no node branches on is read without keeping a cell.

        ``01010101`` depends only on its last input, so the first two
        reads need no cell of their own and the tree navigates a
        one-cell block instead of a three-cell one.
        """
        assert boolean.jaune("01010101").startswith("vvv")
        # every input matters here, so every read keeps its cell (the last
        # needs no step: the tree walks back from it)
        assert boolean.jaune("10010110").startswith("v>v>v<<")

    def test_each_leaf_terminates_without_a_shared_label(self) -> None:
        """Leaves use ``.`` instead of repeating a widening end label."""
        program = boolean.jaune("0110")
        assert program.count(".") == 2  # the ``10`` node's two leaves share one
        assert program.endswith("^.")

    def test_a_zero_one_node_prints_its_cell_and_the_reads_stay_put(self) -> None:
        """Halves ``0``/``1`` print the tested cell with no branch.

        ``1`` on then and ``0`` on else are the cell itself, so the node is
        its move and ``^.``; and a table that is not constant never prints
        from the cell the reads end on, so the last read does not step off
        its cell only to walk back.  Over every three-input table the
        program falls from 10,261 characters to 8,331.
        """
        assert boolean.jaune("0110") == "v>v<2?>^.2:>3?++3:-^."
        assert boolean.jaune("0001") == "v>v<2?^.2:>^."
        assert boolean.jaune("0000") == "vv>^."

    def test_a_one_zero_node_prints_the_inverted_cell(self) -> None:
        """Halves ``1``/``0`` print ``1 - x``, and mostly-``10`` inputs read so.

        ``L?++L:-^.`` is one under branching to two leaves: a 1 jumps to
        the ``-``, a 0 adds two first.  An input with more ``10`` nodes than
        ``01`` reads as ``+v-`` (``%+v-`` over a clobbered read), which
        swaps its halves so each ``10`` is a bare print.  No table grows
        through four inputs, and over every three-input table the program
        falls from 8,331 characters to 7,437 (7,199 once repeated subtrees
        are jumped to, :class:`TestJauneSharing`).
        """
        assert boolean.jaune("10") == "+v-^."
        assert boolean.jaune("10101010") == "vv%+v-^."
        assert boolean.jaune("1110") == "v>+v-<2?+^.2:>^."
        total = sum(len(boolean.jaune(f"{value:08b}")) for value in range(256))
        assert total == 7199

    def test_spatial_lookup_growth_is_linear(self) -> None:
        """Wide parity programs grow by at most the table-size ratio."""
        sizes = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(_jaune_linear(table)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))


class TestJauneSharing:
    """A repeated subtree is laid out once and jumped to with ``?`` or ``!``.

    Through 16 entries sharing alone wins or ties for every table; wider
    shared trees handle larger tables too. The plain constructor remains
    an oracle for these size comparisons.
    """

    @staticmethod
    def _plain(table: str) -> str:
        """The dispatch before sharing: the plain tree, the lookup past 16."""
        if len(table) <= 16:
            return best_input_order(table, _jaune_ordered)
        return _jaune_linear(table)

    def _totals(self, tables: list[str]) -> tuple[int, int]:
        """(plain, shipped) character totals."""
        before = after = 0
        for table in tables:
            plain = len(self._plain(table))
            shipped = len(boolean.jaune(table))
            before, after = before + plain, after + shipped
        return before, after

    def test_three_input_total(self) -> None:
        """All 256 three-input tables: 7,437 to 7,199 characters, 3.2%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._totals(tables) == (7437, 7199)

    def test_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 47,973 to 19,568 characters, 59.2%.

        The unshared tree would give 29,291, but its labels make it
        O(T log T), so it was never raced past 16 entries.
        """
        assert self._totals(five_input_sample()) == (47973, 19568)
        plain_tree = sum(
            len(best_input_order(table, _jaune_ordered))
            for table in five_input_sample()
        )
        assert plain_tree == 29291

    def test_parity_shares_two_subtrees_a_level(self) -> None:
        """Parity's then arm at each level is the else arm one level on.

        So each test jumps (``?`` to a labelled then arm, ``!`` to the else
        copy) rather than laying the level out twice: six inputs in 85
        characters where the lookup takes 431.
        """
        table = "".join(str(row.bit_count() & 1) for row in range(64))
        program = boolean.jaune(table)
        assert len(program) == 85
        assert len(_jaune_linear(table)) == 431
