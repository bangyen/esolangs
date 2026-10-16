"""qoibl generator tests."""

import random

import pytest

import esolangs
from esolangs.languages import generators as boolean
from tests.generators.boolean_runners import _runner
from tests.support.generator_support import (
    assert_an_ignored_input_costs,
    assert_parity_at_most_doubles,
)
from tests.support.witness_tables import witnesses

run_qoibl = _runner("qoibl", lines=True)


class TestQoibl:
    @pytest.mark.parametrize("width", [1, 3, 80])
    def test_narrow_horner_literals_execute_small_tables(self, width: int) -> None:
        for table in witnesses(3):
            program = esolangs.generate("Qoibl", table, width=width)
            assert max(map(len, program.splitlines())) <= max(width, 2)
            for row in range(8):
                assert run_qoibl(program, list(format(row, "03b"))) == table[row]

    @pytest.mark.medium
    @pytest.mark.parametrize(
        ("n", "width"), [(5, 3), (5, 13), pytest.param(8, 1, marks=pytest.mark.slow)]
    )
    def test_narrow_horner_larger_literals(self, n: int, width: int) -> None:
        rng = random.Random(20260930 + n)
        for table in (
            "".join(str(row.bit_count() & 1) for row in range(2**n)),
            format(rng.getrandbits(2**n), f"0{2**n}b"),
        ):
            program = boolean.qoibl(table, width)
            for row in rng.sample(range(2**n), 4):
                assert run_qoibl(program, list(format(row, f"0{n}b"))) == table[row]

    def test_narrow_horner_floor_and_corpus_size(self) -> None:
        assert max(map(len, boolean.qoibl("0110", 1).splitlines())) == 2
        assert (
            sum(len(boolean.qoibl(format(v, "08b"), 1)) for v in range(256)) == 508676
        )

    def test_the_table_is_one_literal(self) -> None:
        """The whole table rides in a single binary literal, bit k for row k."""
        program = boolean.qoibl("0001")
        # 0b1000: row 3 is the only one set, and it is bit 3.
        assert program.count(" yeee ") == 1
        assert program.endswith("tt")

    def test_the_reads_are_one_statement_each(self) -> None:
        """Only the input count scales the statements; the table does not."""
        counts = [
            boolean.qoibl(
                "".join(str(row.bit_count() & 1) for row in range(2**n))
            ).count("\n")
            for n in range(1, 6)
        ]
        assert counts == [2, 3, 4, 5, 6]

    def test_a_constant_table_still_reads_its_inputs(self) -> None:
        """A constant function packs to zero but keeps the reads it owes."""
        program = boolean.qoibl("0000")
        assert program.count(" et ") == 2
        assert "we y we e ry yy ry" in program


def test_constant_table_reads_cost_one_line_each() -> None:
    """Past the first read a constant's inputs are ignored reads, not Horner steps."""
    for bit in "01":
        sizes = [len(boolean.qoibl(bit * 2**n)) for n in (4, 6, 8)]
        assert sizes[2] - sizes[1] == sizes[1] - sizes[0] < 80 * 2
        for n in (1, 3, 5):
            program = boolean.qoibl(bit * 2**n)
            for row in (0, 2**n - 1):
                assert run_qoibl(program, list(f"{row:0{n}b}")) == bit


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """One read into a register the next write clears."""
    assert_an_ignored_input_costs("Qoibl", 6, 30)


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.qoibl, range(7, 11), 800)


def test_qoibl_affine_row_envelope_minima() -> None:
    from itertools import product

    from esolangs.generation.wrap import balance_score
    from esolangs.languages.qoibl.tests.balance_oracle import _best_width

    for negative, constant, positive, extra in product(
        [32, 45, 60], [1, 5, 15], [-1, 4, 12], [0, 10, 30]
    ):
        rows = [(-2, negative), (0, constant), (1, positive)] + [(0, 1)] * extra
        length = (
            sum(slope for slope, _ in rows),
            sum(offset for _, offset in rows) + len(rows) - 1,
        )
        width = _best_width(rows, length, 1, 15)
        layouts = [
            "\n".join("x" * (slope * columns + offset) for slope, offset in rows)
            for columns in range(1, 16)
        ]
        assert balance_score(layouts[width - 1]) == min(map(balance_score, layouts))


@pytest.mark.parametrize("seed", range(6))
def test_balance_stays_within_five_percent_of_the_retired_sweep(seed: int) -> None:
    from esolangs.generation.wrap import balance_score
    from esolangs.languages.qoibl.tests.balance_oracle import sweep_balance_qoibl

    rng = random.Random(seed)
    for inputs in range(1, 8):
        table = format(rng.getrandbits(1 << inputs), f"0{1 << inputs}b")
        default = esolangs.generate("Qoibl", table)
        balanced = esolangs.generate("Qoibl", table, balance=True)
        oracle = sweep_balance_qoibl(table, default)
        assert balance_score(balanced)[0] <= 1.05 * balance_score(oracle)[0]
        for row in (0, (1 << inputs) - 1, rng.randrange(1 << inputs)):
            bits = list(format(row, f"0{inputs}b"))
            assert run_qoibl(balanced, bits) == table[row]
