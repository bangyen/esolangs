"""bit_tilde generator tests."""

from esolangs import tools as boolean


class TestBitTilde:
    def test_full_table_growth_is_linear(self) -> None:
        """Parity folds nothing; emitted size stays linear in the table."""
        sizes = []
        for n in (7, 8):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.bit_tilde(table)))
        assert sizes[1] < 2 * sizes[0] + 256

    def test_single_read_and_output(self) -> None:
        """One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        # The prologue paints the table and walks to the top of it, so the
        # opening is moves and flips -- no loop, read or print among them.
        assert set(program[: program.index(")")]) <= {">", "~"}
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")
