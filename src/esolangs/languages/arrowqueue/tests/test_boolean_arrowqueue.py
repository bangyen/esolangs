"""Covers :mod:`esolangs.languages.arrowqueue.generator`."""

import random

import pytest

import esolangs
from esolangs.generation.helpers import TEMPLATE_CHAR, runs
from esolangs.languages.arrowqueue.descriptor import PAIR
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import run_until_halt_or_cycle
from tests.support.evaluation import _evaluate
from tests.support.witness_tables import row_bits


def _instantiate_arrowqueue(template: str, bits: list[int]) -> str:
    """Bind native source with explicitly declared setters."""
    bindings = esolangs.TemplateBindings(setters=(PAIR,) * len(bits))
    artifact = esolangs.TemplateArtifact(template, "ArrowQueue", bindings)
    return esolangs.instantiate("ArrowQueue", artifact, bits).source


class TestParameterizedArrowQueue:
    """Input-by-substitution boolean generator for the no-input language ArrowQueue."""

    def run_arrowqueue(self, prog: str) -> str:
        from esolangs.languages.arrowqueue.interpreter import _Machine

        return "0" if run_until_halt_or_cycle(_Machine(prog.splitlines())) else "1"

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        return _instantiate_arrowqueue(tpl, bits)

    def test_random_tables(self) -> None:
        """Seeded random tables through five inputs produce the right result."""
        from esolangs.languages.arrowqueue import generator as generators

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
        from esolangs.languages.arrowqueue import generator as generators
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
        assert _program(witness).source.count("\n") + 1 == bound

    @pytest.mark.parametrize("table", ["0110", "0110100110010110" * 2])
    def test_every_input_is_the_same_one_cell(self, table: str) -> None:
        """Both routes spell every input as one cell, ``.`` against ``~``."""
        from esolangs.languages.arrowqueue import generator as generators

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
        from esolangs.languages.arrowqueue import generator as generators

        template = generators.arrowqueue(table)
        for combo in range(2**n):
            bits = row_bits(combo, n)
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"


@pytest.mark.medium
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_balance_and_setters_off_path(bit: str) -> None:
    """Constant roots keep their setters off the halt/ring path, balanced."""
    if bit == "0":
        _check_constants()
    n = 8
    table = bit * (1 << n)
    template = esolangs.generate("ArrowQueue", table)
    assert template.source.count(TEMPLATE_CHAR) == n
    for options in ({}, {"width": 1}, {"width": 5}, {"width": 6}, {"balance": True}):
        program = esolangs.generate("ArrowQueue", table, **options)
        assert _evaluate("ArrowQueue", program, inputs=n) == table


def test_ring_pops_rdlu_then_sustains() -> None:
    """A ``1`` row pops R, D, L, U at its corners then sustains; a ``0`` row exits."""
    from esolangs.languages.arrowqueue.generator import _ROWS
    from esolangs.languages.arrowqueue.interpreter import _Machine

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

    from esolangs.languages.arrowqueue.generator import _LEAF, _LEAF_END

    # Zero-after-zero has no preceding ring; a one still needs its lower half.
    for pair in ("00", "01", "10", "11"):
        rows = [
            " +++" if i and bit == pair[i - 1] == "0" else _LEAF[bit]
            for i, bit in enumerate(pair)
        ]
        rows.append(_LEAF_END[pair[-1]])
        for index, bit in enumerate(pair):
            assert verdict(rows, (down,) * index + entry) == bit
    assert verdict([_LEAF["1"], "  ++"], entry) == "0"  # wrong-ring control


def _check_constants() -> None:
    from esolangs.languages.arrowqueue.interpreter import _Machine

    for n in range(1, 13):
        for bit in "01":
            table = bit * (1 << n)
            default = esolangs.generate("ArrowQueue", table)
            span = max(map(len, default.source.splitlines()))
            assert esolangs.generate("ArrowQueue", table, width=span) == default
            for options in (
                {},
                {"width": 1},
                {"width": 4},
                {"width": 7},
                {"balance": True},
            ):
                template = esolangs.generate("ArrowQueue", table, **options)
                rows = template.source.splitlines()
                slots = {
                    (r, c)
                    for r, row in enumerate(rows)
                    for c, char in enumerate(row)
                    if char == "$"
                }
                assert len(slots) == n
                if "width" in options:
                    assert max(map(len, rows)) <= max(4, options["width"])
                for bits in ([0] * n, [1] * n):
                    io = ScriptedIO("7")
                    program = esolangs.instantiate("ArrowQueue", template, bits)
                    machine = _Machine(program.source.splitlines(), io)
                    seen = set()
                    for _ in range(32):
                        if machine.halted or machine.snapshot() in seen:
                            break
                        assert (machine.row, machine.col) not in slots
                        seen.add(machine.snapshot())
                        machine.step()
                    assert machine.halted == (bit == "0")
                    if bit == "1":
                        assert machine.snapshot() in seen
                    assert not io.getvalue()
                    assert io.reads == 0
                    assert io.input_char() == ord("7")
