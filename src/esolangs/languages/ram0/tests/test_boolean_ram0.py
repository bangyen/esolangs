"""Covers :mod:`esolangs.languages.ram0.generator`: the shared tree."""

import random
import re

import pytest

from esolangs.languages import generators as boolean
from tests.support.generator_support import assert_parity_at_most_doubles
from tests.support.witness_tables import row_bits


class TestParameterizedRam0:
    """Input-by-substitution boolean generator for the no-input language RAM0."""

    def run_ram0(self, prog: str) -> str:

        from esolangs.languages.ram0.interpreter import run
        from esolangs.runtime.io import ScriptedIO

        io = ScriptedIO()
        run(prog, io)
        m = re.search(r"^z: (\d+)", io.getvalue(), re.MULTILINE)
        assert m is not None
        return m.group(1)

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill through the shipped filler, not a copy of it."""
        from tests.generators.fills import fill

        _fill_ram0 = fill("RAM0")

        return _fill_ram0(tpl, bits)

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.generation.helpers import TEMPLATE_CHAR, runs
        from esolangs.languages import generators
        from esolangs.languages.ram0.generator import PAIR as RAM0_PAIR

        template = generators.ram0("0110")
        assert "{X" not in template
        assert len(runs(template, TEMPLATE_CHAR, (RAM0_PAIR,) * 2)) == 2

    def test_leaves_share_a_low_address_halt_trampoline(self) -> None:
        """Every leaf jumps to 2; only the trampoline names the end."""
        from esolangs.languages import generators
        from esolangs.languages.ram0.generator import _ram0_ordered

        tokens = generators.ram0("01101001").split()
        assert tokens[0] == "C"
        assert tokens.count("2") == 2
        plain = _ram0_ordered("01101001", (0, 1, 2)).split()
        assert plain.count("2") == 8

    @staticmethod
    def _sharing_totals(tables: list[str]) -> tuple[int, int]:
        """(before, shipped) totals, each table checked not to grow."""
        from esolangs.languages import generators
        from esolangs.languages.ram0.generator import _ram0_ordered

        before = after = 0
        for table in tables:
            old = len(_ram0_ordered(table, tuple(range(len(table).bit_length() - 1))))
            new = len(generators.ram0(table))
            before, after = before + old, after + new
        return before, after

    def test_sharing_three_input_total(self) -> None:
        """All 256 three-input tables: 27,554 to 22,318 characters, 19.0%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._sharing_totals(tables) == (27554, 22318)

    def test_shared_tree_executes_wide_rows(self) -> None:
        """A seeded seven-input table, every row, through the shared tree."""
        from esolangs.languages import generators

        n = 7
        table = format(random.Random(7).getrandbits(2**n), f"0{2**n}b")
        template = generators.ram0(table)
        for row in range(2**n):
            bits = row_bits(row, n)
            assert self.run_ram0(self.instantiate(template, bits)) == table[row]


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.ram0, range(11, 15))
