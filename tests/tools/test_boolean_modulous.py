"""modulous generator tests."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from tests.generator_support import assert_an_ignored_input_costs
from tests.tools.boolean_runners import (
    run_modulous,
)
from tests.witness_tables import witnesses


class TestModulous:
    @pytest.mark.parametrize("width", [1, 4, 7, 13, 40, 80])
    def test_narrow_chunks_execute_every_small_table(self, width: int) -> None:
        for n in range(1, 4):
            for table in witnesses(n):
                program = esolangs.generate("Modulous", table, width=width)
                assert max(map(len, program.splitlines())) <= max(width, 4)
                for row in range(2**n):
                    bits = list(format(row, f"0{n}b"))
                    assert run_modulous(program, bits) == table[row]

    @pytest.mark.medium
    @pytest.mark.parametrize("n", [5, 8])
    def test_narrow_chunks_and_relative_jumps_at_larger_arity(self, n: int) -> None:
        rng = random.Random(20260930 + n)
        for table in (
            "".join(str(row.bit_count() & 1) for row in range(2**n)),
            format(rng.getrandbits(2**n), f"0{2**n}b"),
        ):
            for width in (1, 4, 13, 80):
                program = esolangs.generate("Modulous", table, width=width)
                for row in [0, 2**n - 1, *rng.sample(range(2**n), 12)]:
                    assert (
                        run_modulous(program, list(format(row, f"0{n}b"))) == table[row]
                    )

    def test_narrow_literal_floor_and_corpus_size(self) -> None:
        assert max(map(len, boolean.modulous("0110", 1).splitlines())) == 3
        assert (
            sum(len(boolean.modulous(format(v, "08b"), 1)) for v in range(256))
            == 100922
        )


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """``[INP INT][POP]``."""
    assert_an_ignored_input_costs("Modulous", 6, 14)
