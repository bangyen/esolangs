"""packlang generator tests."""

from esolangs import tools as boolean


class TestPacklangPaintedArray:
    """Fast structural coverage for Packlang's painted array."""

    def test_a_constant_table_paints_per_block_not_per_row(self) -> None:
        """Both fold routes: an all-zero block writes nothing, a full one fills."""
        assert "INCR t(" not in boolean.packlang("0000")
        assert "While q^4Do{" in boolean.packlang("1111")
        assert "While q^128Do{" in boolean.packlang("1" * 128 + "0" * 128)
        # A painted row costs eleven characters, so two per row is well
        # under the cheapest per-row program either constant could have.
        biggest = max(len(boolean.packlang(bit * 1024)) for bit in "01")
        assert biggest < 2 * 1024, "a constant table is paying per row"

    def test_the_per_row_cost_does_not_grow_with_the_table(self) -> None:
        """Doubling parity's table doubles what the rows cost, no more."""
        sizes = []
        for n in (9, 10, 11):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.packlang(table)))
        first, second = sizes[1] - sizes[0], sizes[2] - sizes[1]
        assert 1.9 < second / first < 2.1, sizes
