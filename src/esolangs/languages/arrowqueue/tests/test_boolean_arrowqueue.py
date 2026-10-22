"""Covers :mod:`esolangs.languages.arrowqueue.generator`."""

import random

import pytest

from esolangs.generation.helpers import TEMPLATE_CHAR, runs
from esolangs.languages.arrowqueue.generator import PAIR
from tests.generators.fills import fill
from tests.support.witness_tables import row_bits

_instantiate_arrowqueue = fill("ArrowQueue")


class TestParameterizedArrowQueue:
    """Input-by-substitution boolean generator for the no-input language ArrowQueue."""

    def run_arrowqueue(self, prog: str) -> str:
        from esolangs.languages.arrowqueue.interpreter import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        return "0" if run_until_halt_or_cycle(_Machine(prog.splitlines())) else "1"

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        return _instantiate_arrowqueue(tpl, bits)

    def test_random_tables(self) -> None:
        """Seeded random tables through five inputs produce the right result."""
        from esolangs.languages import generators

        random.seed(13)
        for n in (1, 2, 3, 4, 5):
            for _ in range(2):
                table = "".join(random.choice("01") for _ in range(2**n))
                template = generators.arrowqueue(table)
                for combo in range(2**n):
                    bits = row_bits(combo, n)
                    got = self.run_arrowqueue(self.instantiate(template, bits))
                    assert got == table[combo], f"{table} inputs {bits}"

    @pytest.mark.parametrize("n", range(1, 7))
    def test_rows_reach_but_never_pass_the_ledger_bound(self, n: int) -> None:
        """At most 2T + 6n + 7 lines; a lone zero second to last reaches it.

        Measured exhaustively through n=3, and to n=8 over these families.
        The cascade reaches it; past n=3 the default folds the witness
        into fewer, wider rows.
        """
        from esolangs.languages import generators
        from esolangs.languages.arrowqueue.generator import _program

        width = 2**n
        bound = 2 * width + 6 * n + 7
        rng = random.Random(n)
        tables = [
            *("1" * i + "0" + "1" * (width - 1 - i) for i in range(width)),
            *("0" * i + "1" + "0" * (width - 1 - i) for i in range(width)),
            *("".join(rng.choice("01") for _ in range(width)) for _ in range(8)),
        ]
        for table in tables:
            rows = generators.arrowqueue(table).count("\n") + 1
            assert rows <= bound, f"{table}: {rows} > {bound}"
        witness = "1" * (width - 2) + "01"
        assert _program(witness).count("\n") + 1 == bound

    @pytest.mark.parametrize("table", ["0110", "0110100110010110" * 2])
    def test_every_input_is_the_same_one_cell(self, table: str) -> None:
        """Both routes spell every input as one cell, ``.`` against ``~``."""
        from esolangs.languages import generators

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
        from esolangs.languages import generators

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
    from esolangs.runtime._evaluate import _evaluate

    n = 8
    table = bit * (1 << n)
    template = esolangs.generate("ArrowQueue", table)
    assert template.count(TEMPLATE_CHAR) == n
    for options in ({}, {"width": 1}, {"width": 5}, {"width": 6}, {"balance": True}):
        program = esolangs.generate("ArrowQueue", table, **options)
        assert _evaluate("ArrowQueue", program, inputs=n) == table


def test_ring_pops_rdlu_then_sustains() -> None:
    """A ``1`` row pops R, D, L, U at its corners then sustains; a ``0`` row exits."""
    from esolangs.languages.arrowqueue.generator import _ROWS
    from esolangs.languages.arrowqueue.interpreter import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    right, down, left, up = range(4)

    def verdict(rows: list[str], queue: tuple[int, ...]) -> str:
        machine = _Machine(rows)
        machine.state = (0, 1, down, queue, False)
        return "0" if run_until_halt_or_cycle(machine) else "1"

    # Entered down column 1 with the sentinel R: the queue is then R D L U.
    entry = (right, right, down, left, up)
    machine = _Machine(_ROWS["1"])
    machine.state = (0, 1, down, entry, False)
    pops = []
    for _ in range(12):
        row, col, _d, queue, _done = machine.state
        if machine.grid[row][col] == "+":
            pops.append(((row, col), queue[0]))
        machine.step()
    assert pops[:5] == [
        ((0, 1), right),
        ((0, 3), right),
        ((0, 5), down),
        ((1, 5), left),
        ((1, 3), up),
    ]
    assert verdict(_ROWS["1"], entry) == "1"
    assert verdict(_ROWS["0"], entry) == "0"
