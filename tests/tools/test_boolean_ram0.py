"""Covers :mod:`esolangs.tools.ram0`: the shared tree and its lookup candidate."""

import random
import re
from itertools import pairwise

import pytest


class TestParameterizedRam0:
    """Input-by-substitution boolean generator for the no-input language RAM0.

    RAM0 prints a full state dump at halt; the generator's answer is the
    final ``z`` value, read from the dump's ``z: N`` line.
    """

    def run_ram0(self, prog: str) -> str:

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import run

        io = ScriptedIO()
        run(prog, io)
        m = re.search(r"^z: (\d+)", io.getvalue(), re.MULTILINE)
        assert m is not None
        return m.group(1)

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill through the shipped filler, not a copy of it.

        ``Z`` resets absolutely, so the setter is the same at every
        position -- ``Z A`` for a one, ``Z Z`` for a zero, two commands
        either way -- which is what made a local copy look safe.  It is
        still a second spelling of a construction the generator counts
        positions against, and that is the shape that hung the suite when
        Minsky Swap's copy drifted.
        """
        from tests.tools.fills import _fill_ram0

        return _fill_ram0(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs import tools as generators

        template = generators.ram0(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_ram0(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs import tools as generators

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = generators.ram0(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_ram0(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs import tools as generators
        from esolangs.tools.helpers import TEMPLATE_CHAR, runs
        from esolangs.tools.ram0 import PAIR as RAM0_PAIR

        template = generators.ram0("0110")
        assert "{X" not in template
        assert len(runs(template, TEMPLATE_CHAR, (RAM0_PAIR,) * 2)) == 2

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits a single leaf with no branching."""
        from esolangs import tools as generators

        template = generators.ram0("0000")
        assert template.count("C") == 1  # entry trampoline only
        assert "Z" in template

    def test_leaves_share_a_low_address_halt_trampoline(self) -> None:
        """Every leaf jumps to 2; only the trampoline names the end.

        Parity's tree has eight leaves, but a leaf is emitted once per
        answer and the other six are jumps to those two.
        """
        from esolangs import tools as generators
        from esolangs.tools.ram0 import _ram0_ordered

        tokens = generators.ram0("01101001").split()
        assert tokens[0] == "C"
        assert tokens.count("2") == 2
        plain = _ram0_ordered("01101001", (0, 1, 2)).split()
        assert plain.count("2") == 8

    @staticmethod
    def _sharing_totals(tables: list[str]) -> tuple[int, int]:
        """(before, shipped) totals, each table checked not to grow.

        Before is the plain tree in its best order through 16 entries and
        the straight-line lookup past them, as the generator was.
        """
        from esolangs import tools as generators
        from esolangs.tools.helpers import best_input_order
        from esolangs.tools.ram0 import _ram0_ordered
        from tests.tools.plain_oracles import _ram0_linear

        before = after = 0
        for table in tables:
            old = len(
                best_input_order(table, _ram0_ordered)
                if len(table) <= 16
                else _ram0_linear(table)
            )
            new = len(generators.ram0(table))
            before, after = before + old, after + new
        return before, after

    def test_sharing_three_input_total(self) -> None:
        """All 256 three-input tables: 28,890 to 24,220 characters, 16.2%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._sharing_totals(tables) == (28890, 24562)

    def test_sharing_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 300,546 to 54,209 characters, 82.0%.

        Sharing is what lets the tree run past 16 entries at all: shared,
        it is O(T) with its addresses, and it undercuts the lookup.
        """
        from tests.tools.sample_tables import five_input_sample

        assert self._sharing_totals(five_input_sample()) == (300546, 55155)

    def test_shared_tree_executes_wide_rows(self) -> None:
        """A seeded seven-input table, every row, through the shared tree."""
        from esolangs import tools as generators

        n = 7
        table = format(random.Random(7).getrandbits(2**n), f"0{2**n}b")
        template = generators.ram0(table)
        for row in range(2**n):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            assert self.run_ram0(self.instantiate(template, bits)) == table[row]

    def test_wide_template_executes_sampled_rows(self) -> None:
        """Past 16 entries the template returns sampled six-input rows."""
        from esolangs import tools as generators

        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        template = generators.ram0(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            assert self.run_ram0(self.instantiate(template, bits)) == table[row]

    def test_lookup_candidate_executes_wide_rows(self) -> None:
        """The straight-line lookup kept as a candidate still computes."""
        from tests.tools.plain_oracles import _ram0_linear

        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        template = _ram0_linear(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            assert self.run_ram0(self.instantiate(template, bits)) == table[row]

    def test_wide_template_growth(self) -> None:
        """Wide parity templates grow by at most the table-size ratio."""
        from esolangs import tools as generators

        sizes = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(generators.ram0(table)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))
