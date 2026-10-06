"""unsquare generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_unsquare,
)
from tests.witness_tables import witnesses


class TestUnsquare:
    """The table lives on the stack; the reads pop down to the answer."""

    @staticmethod
    def _rows(table: str) -> list[str]:
        """Every row of ``table`` as the generated program answers it."""
        n = (len(table) - 1).bit_length()
        program = boolean.unsquare(table)
        return [
            run_unsquare(program, list(format(row, f"0{n}b"))) for row in range(2**n)
        ]

    def test_program_shape(self) -> None:
        """The table is pushed first, then one read an input, then the print."""
        program = boolean.unsquare("0110")
        assert program.startswith("OIIO")  # the table, reversed, one cell a row
        assert program.count("i") == 2  # one read an input
        assert program.endswith("o")

        for value in range(256):
            assert boolean.unsquare(format(value, "08b")).count("i") == 3

    def test_two_bytes_a_row(self) -> None:
        """Size is the table plus its addressing, not a tree over it."""
        for n in range(2, 11):
            table = "".join("01"[(row * row) % 3 % 2] for row in range(2**n))
            size = len(boolean.unsquare(table))
            assert size - 2 * 2**n == 10 * n + 26, n

    @pytest.mark.medium
    def test_every_row_of_every_small_table(self) -> None:
        """The witness tables at n <= 3, every row executed."""
        for n in (1, 2, 3):
            for table in witnesses(n):
                assert "".join(self._rows(table)) == table, table

    def test_a_program_answers_its_own_table_only(self) -> None:
        """The positive control: XOR's program disagrees with XNOR everywhere."""
        assert "".join(self._rows("0110")) != "1001"

    def test_inessential_inputs_cost_a_read_not_a_table(self) -> None:
        """An ignored input is consumed by ``iA`` and never widens the table."""
        program = boolean.unsquare("01010101")  # depends on the last input alone
        assert program.count("i") == 3
        assert program.startswith("IOiA")  # two cells, then the first skip
        assert "".join(self._rows("01010101")) == "01010101"

    def test_the_program_is_only_unsquare_commands(self) -> None:
        """Only the characters Unsquare reads are emitted."""
        for table in ("10", "0110", "0001", "11111110"):
            assert set(boolean.unsquare(table)) <= set("+-<>AIOPiox"), table
