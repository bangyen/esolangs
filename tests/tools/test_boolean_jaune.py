"""Covers :mod:`esolangs.tools.jaune`: the tree, its sharing, the linear lookup."""

import contextlib
import random

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import best_input_order
from esolangs.tools.jaune import _jaune_ordered
from tests.tools.boolean_runners import run_jaune
from tests.tools.plain_oracles import _jaune_linear
from tests.tools.sample_tables import five_input_sample


class TestJaune:
    @pytest.mark.parametrize("table", ["00", "11"])
    def test_plain_constant_consumes_clobbered_input(self, table: str) -> None:
        program = _jaune_ordered(table, (0,))
        for bit in ("0", "1"):
            assert run_jaune(program, [bit]) == table[int(bit)]

    def test_reads_every_input_whatever_the_table(self) -> None:
        """Every table consumes exactly ``n`` inputs, folds included."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.jaune import run

        n = 3
        for table in ("11111111", "00000000", "11110000", "10101010", "10010110"):
            io = ScriptedIO("0\n" * n)
            with contextlib.suppress(Exception, SystemExit):
                run(boolean.jaune(table), io=io)
            assert io.reads == n, (
                f"{table} consumed {io.position()} inputs, expected {n}"
            )

    def test_unused_inputs_are_clobbered_not_stored(self) -> None:
        """An input no node branches on is read without keeping a cell."""
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
        """Halves ``0``/``1`` print the tested cell with no branch."""
        assert boolean.jaune("0110") == "v>v<2?>^.2:>3?++3:-^."
        assert boolean.jaune("0001") == "v>v<2?^.2:>^."
        assert boolean.jaune("0000") == "vv>^."

    def test_a_one_zero_node_prints_the_inverted_cell(self) -> None:
        """Halves ``1``/``0`` print ``1 - x``, and mostly-``10`` inputs read so."""
        assert boolean.jaune("10") == "+v-^."
        assert boolean.jaune("10101010") == "vv%+v-^."
        assert boolean.jaune("1110") == "v>+v-<2?+^.2:>^."
        total = sum(len(boolean.jaune(f"{value:08b}")) for value in range(256))
        assert total == 7199

    def test_spatial_lookup_executes_wide_rows(self) -> None:
        """The travelling counter returns sampled six-input rows."""
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = _jaune_linear(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_jaune(program, bits) == table[row]


class TestJauneSharing:
    """A repeated subtree is laid out once and jumped to with ``?`` or ``!``."""

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
        """200 seeded five-input tables: 47,973 to 19,568 characters, 59.2%."""
        assert self._totals(five_input_sample()) == (47973, 19568)
        plain_tree = sum(
            len(best_input_order(table, _jaune_ordered))
            for table in five_input_sample()
        )
        assert plain_tree == 29291

    @pytest.mark.medium
    def test_five_input_sample_runs(self) -> None:
        """Every row of the five-input sample's shared programs computes its bit."""
        for table in five_input_sample():
            program = boolean.jaune(table)
            for combo in range(32):
                bits = [str((combo >> (4 - i)) & 1) for i in range(5)]
                assert run_jaune(program, bits) == table[combo], (table, combo)

    def test_parity_shares_two_subtrees_a_level(self) -> None:
        """Parity's then arm at each level is the else arm one level on."""
        table = "".join(str(row.bit_count() & 1) for row in range(64))
        program = boolean.jaune(table)
        assert len(program) == 85
        assert len(_jaune_linear(table)) == 431
        for row in range(64):
            bits = [str((row >> (5 - i)) & 1) for i in range(6)]
            assert run_jaune(program, bits) == table[row]

    def test_eight_inputs_run_every_row(self) -> None:
        """Past 16 entries the shared tree wins on seeded random tables."""
        rng = random.Random(8)
        for _ in range(3):
            table = format(rng.getrandbits(256), "0256b")
            program = boolean.jaune(table)
            assert len(program) < len(_jaune_linear(table))
            for row in range(256):
                bits = [str((row >> (7 - i)) & 1) for i in range(8)]
                assert run_jaune(program, bits) == table[row]
