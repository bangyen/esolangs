"""Covers :mod:`esolangs.tools.ram0`: the shared tree and its lookup candidate."""

import random
import re

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import _validate_truth_table
from tests.generator_support import assert_parity_at_most_doubles
from tests.witness_tables import row_bits


class TestParameterizedRam0:
    """Input-by-substitution boolean generator for the no-input language RAM0."""

    def run_ram0(self, prog: str) -> str:

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import run

        io = ScriptedIO()
        run(prog, io)
        m = re.search(r"^z: (\d+)", io.getvalue(), re.MULTILINE)
        assert m is not None
        return m.group(1)

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill through the shipped filler, not a copy of it."""
        from tests.tools.fills import fill

        _fill_ram0 = fill("RAM0")

        return _fill_ram0(tpl, bits)

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs import tools as generators
        from esolangs.tools.helpers import TEMPLATE_CHAR, runs
        from esolangs.tools.ram0 import PAIR as RAM0_PAIR

        template = generators.ram0("0110")
        assert "{X" not in template
        assert len(runs(template, TEMPLATE_CHAR, (RAM0_PAIR,) * 2)) == 2

    def test_leaves_share_a_low_address_halt_trampoline(self) -> None:
        """Every leaf jumps to 2; only the trampoline names the end."""
        from esolangs import tools as generators
        from esolangs.tools.ram0 import _ram0_ordered

        tokens = generators.ram0("01101001").split()
        assert tokens[0] == "C"
        assert tokens.count("2") == 2
        plain = _ram0_ordered("01101001", (0, 1, 2)).split()
        assert plain.count("2") == 8

    @staticmethod
    def _sharing_totals(tables: list[str]) -> tuple[int, int]:
        """(before, shipped) totals, each table checked not to grow."""
        from esolangs import tools as generators
        from esolangs.tools.helpers import best_input_order
        from esolangs.tools.ram0 import _ram0_ordered

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
        """All 256 three-input tables: 28,890 to 24,562 characters, 15.0%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._sharing_totals(tables) == (28890, 24562)

    def test_sharing_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 300,546 to 55,155 characters, 81.6%."""
        from tests.tools.sample_tables import five_input_sample

        assert self._sharing_totals(five_input_sample()) == (300546, 55155)

    def test_shared_tree_executes_wide_rows(self) -> None:
        """A seeded seven-input table, every row, through the shared tree."""
        from esolangs import tools as generators

        n = 7
        table = format(random.Random(7).getrandbits(2**n), f"0{2**n}b")
        template = generators.ram0(table)
        for row in range(2**n):
            bits = row_bits(row, n)
            assert self.run_ram0(self.instantiate(template, bits)) == table[row]

    def test_wide_template_executes_sampled_rows(self) -> None:
        """Past 16 entries the template returns sampled six-input rows."""
        from esolangs import tools as generators

        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        template = generators.ram0(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = row_bits(row, n)
            assert self.run_ram0(self.instantiate(template, bits)) == table[row]

    def test_lookup_candidate_executes_wide_rows(self) -> None:
        """The straight-line lookup kept as a candidate still computes."""

        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        template = _ram0_linear(table)
        for row in (0, 1, 2, 7, 31, 32, 62, 63):
            bits = row_bits(row, n)
            assert self.run_ram0(self.instantiate(template, bits)) == table[row]


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.ram0, range(11, 15))


def _ram0_linear(truth_table: str) -> str:
    """Emit a linear straight-line RAM initializer and indexed lookup."""
    from esolangs.tools.ram0 import _RAM0_INPUT

    n = _validate_truth_table(truth_table)
    tokens: list[str] = []
    labels: dict[str, int] = {}
    jumps: list[tuple[int, str]] = []

    def emit(*commands: str) -> None:
        tokens.extend(commands)

    def mark(name: str) -> None:
        labels[name] = len(tokens)

    def jump(target: str) -> None:
        jumps.append((len(tokens), target))
        tokens.append("@")

    def unary(value: int) -> None:
        emit("Z", *("A" for _ in range(value)))

    def store_constant(address: int, value: int) -> None:
        unary(address)
        emit("N")
        unary(value)
        emit("S")

    # Cells 0/1 hold the initializer's address counter and the selected table
    # pointer; cells 2..n+1 hold the parameterized inputs.
    for i in range(n):
        unary(i + 2)
        emit("N", "Z", _RAM0_INPUT, "S")

    table_base = n + 2
    store_constant(0, table_base - 1)
    store_constant(1, table_base)

    # Advance cell 0, using the new address as a temporary copy of itself,
    # then store one table bit there.  This is constant work per row.
    for bit in truth_table:
        emit("Z", "L", "A", "N", "S")
        emit("Z", "N", "Z", "L", "A", "L", "S")
        emit("Z", "L", "N", "Z")
        if bit == "1":
            emit("A")
        emit("S")

    # Add each set bit's weight to the selected table pointer.  Across all
    # inputs the unary runs contain 2T-2 commands.
    for i in range(n):
        unary(i + 2)
        emit("L", "C")
        one = f"input_{i}_one"
        after = f"input_{i}_after"
        jump(one)
        jump(after)
        mark(one)
        unary(1)
        emit("N", "Z", "A", "L")
        emit(*("A" for _ in range(1 << (n - 1 - i))))
        emit("S")
        mark(after)

    emit("Z", "A", "L", "L")
    for at, target in jumps:
        target_at = labels[target]
        tokens[at] = str(target_at + 1)
    return " ".join(tokens)
