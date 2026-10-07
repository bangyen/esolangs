"""modulous generator tests."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
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
            sum(len(boolean.modulous(format(v, "08b"), 1)) for v in range(256)) == 94976
        )

    def test_fitting_bracket_layout_keeps_its_source(self) -> None:
        from esolangs.tools.wrap import _bracket_literal

        natural = boolean.modulous("01101001")
        assert boolean.modulous("01101001", 80) == _bracket_literal(natural, 80)

    def test_structure(self) -> None:
        """The table is one literal and the program prints one of its bytes."""
        program = boolean.modulous("10010110")
        assert program.startswith('[PSH STR "10010110"]')
        assert program.count("[INP INT]") == 3
        assert program.endswith("[PRT][END]")

    def test_size_is_the_table_plus_a_fixed_frame(self) -> None:
        """No branch reads the table, so its contents cannot change the size."""
        sizes = {
            len(boolean.modulous(table))
            for table in ("11111111", "10010110", "00000000", "11110000")
        }
        assert len(sizes) == 1
        assert len(boolean.modulous("1" * 16)) - sizes.pop() == 16 - 8 + 49
