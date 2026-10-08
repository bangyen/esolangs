"""packlang generator tests."""

import random

import pytest

from esolangs import tools as boolean
from esolangs._evaluate import _evaluate


class TestPacklangPaintedArray:
    """Fast structural coverage for Packlang's painted array."""

    def test_a_constant_table_paints_per_block_not_per_row(self) -> None:
        """Both fold routes: an all-zero block writes nothing, a full one fills."""
        assert "INCR t(" not in boolean.packlang("0000")
        assert "While q^7Do{" in boolean.packlang("11111110")
        assert "While q^127Do{" in boolean.packlang("1" * 127 + "0" * 129)
        # A painted row costs eleven characters, so two per row is well
        # under the cheapest per-row program either constant could have.
        biggest = max(len(boolean.packlang(bit * 1024)) for bit in "01")
        assert biggest < 2 * 1024, "a constant table is paying per row"

    def test_the_per_row_cost_does_not_grow_with_the_table(self) -> None:
        """Doubling a random table doubles what the rows cost, no more.

        Parity repeats its 128-row blocks, which are aliased and cost nothing.
        """
        rng = random.Random(0)
        sizes = []
        for n in (9, 10, 11):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            sizes.append(len(boolean.packlang(table)))
        first, second = sizes[1] - sizes[0], sizes[2] - sizes[1]
        assert 1.8 < second / first < 2.2, sizes

    def test_a_run_of_ones_is_a_loop_and_a_lone_one_a_write(self) -> None:
        """Runs of ones loop; a lone one stays a single write."""
        table = "1" + "0" * 20 + "1" * 30 + "0" * 77
        program = boolean.packlang(table)
        assert "While q^51Do{INCR t(q);INCR q;}" in program
        assert "INCR t(0);" in program
        assert _evaluate("Packlang", program, inputs=7) == table

    @staticmethod
    def _blocks() -> list[str]:
        rng = random.Random(1)
        return ["".join(rng.choice("01") for _ in range(128)) for _ in range(4)]

    def test_a_repeated_block_is_aliased_to_its_first_copy(self) -> None:
        """Equal 128-row blocks cost less than distinct ones.

        ``f * 2`` would not do: it ignores its first input and is one block.
        """
        f, g, h, k = self._blocks()
        assert len(boolean.packlang(f + g + f + h)) < len(
            boolean.packlang(f + g + k + h)
        )

    @pytest.mark.medium
    def test_an_aliased_block_runs(self) -> None:
        f, g, h, _ = self._blocks()
        same = f + g + f + h
        assert _evaluate("Packlang", boolean.packlang(same), inputs=9) == same

    def test_an_alias_dearer_than_the_writes_is_not_taken(self) -> None:
        """A one-write block three blocks on repeats by writing again."""
        block = "0" * 127 + "1"
        zero = "0" * 128
        table = block + zero + zero + block
        assert boolean.packlang(table).count("INCR t(127);") == 2
