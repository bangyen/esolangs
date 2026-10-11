"""Covers :mod:`esolangs.tools.arrowqueue`."""

import random

import pytest

from esolangs.tools.arrowqueue import PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from tests.support.witness_tables import row_bits
from tests.tools.fills import fill

_instantiate_arrowqueue = fill("ArrowQueue")


class TestParameterizedArrowQueue:
    """Input-by-substitution boolean generator for the no-input language ArrowQueue."""

    def run_arrowqueue(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        return "0" if run_until_halt_or_cycle(_Machine(prog.splitlines())) else "1"

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        return _instantiate_arrowqueue(tpl, bits)

    def test_random_tables(self) -> None:
        """Seeded random tables through five inputs produce the right result."""
        from esolangs import tools as generators

        random.seed(13)
        for n in (1, 2, 3, 4, 5):
            for _ in range(2):
                table = "".join(random.choice("01") for _ in range(2**n))
                template = generators.arrowqueue(table)
                for combo in range(2**n):
                    bits = row_bits(combo, n)
                    got = self.run_arrowqueue(self.instantiate(template, bits))
                    assert got == table[combo], f"{table} inputs {bits}"

    @pytest.mark.parametrize("table", ["0110", "0110100110010110" * 2])
    def test_every_input_is_the_same_one_cell(self, table: str) -> None:
        """Both routes spell every input as one cell, ``.`` against ``~``."""
        from esolangs import tools as generators

        n = len(table).bit_length() - 1
        template = generators.arrowqueue(table)
        setters = (PAIR,) * n
        assert setters == ((".", "~"),) * n
        assert template.count(TEMPLATE_CHAR) == n
        assert len(runs(template, TEMPLATE_CHAR, setters)) == n
        filled = self.instantiate(template, [1] * n)
        assert filled.count("\n") == template.count("\n")
        assert len(filled) == len(template)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("1" * 16, 4),
            ("0" * 16, 4),
            ("1111111100000000", 4),
            ("1111000000000000", 4),
            ("1" * 32, 5),
            ("1" * 16 + "0" * 16, 5),
        ],
    )
    def test_folded_tables_past_three_inputs(self, table: str, n: int) -> None:
        """Folded leaves stay correct deeper than the exhaustive n <= 3 sweep."""
        from esolangs import tools as generators

        template = generators.arrowqueue(table)
        for combo in range(2**n):
            bits = row_bits(combo, n)
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"


@pytest.mark.medium
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_balance_and_setters_off_path(bit: str) -> None:
    """Constant roots keep their setters off the halt/ring path, balanced."""
    import esolangs
    from esolangs._evaluate import _evaluate
    from esolangs.tools.arrowqueue import _program
    from esolangs.tools.wrap import balance_score

    n = 8
    table = bit * (1 << n)
    template = esolangs.generate("ArrowQueue", table)
    assert template.count(TEMPLATE_CHAR) == n
    assert len(template) < len(_program(table, keep_constant_cascade=True))
    for options in ({}, {"width": 1}, {"width": 5}, {"width": 6}, {"balance": True}):
        program = esolangs.generate("ArrowQueue", table, **options)
        assert _evaluate("ArrowQueue", program, inputs=n) == table
        if options.get("balance"):
            old = min(
                (
                    _program(table, width, keep_constant_cascade=True)
                    for width in (None, 1, 5, 6)
                ),
                key=balance_score,
            )
            assert balance_score(program) <= balance_score(old)
