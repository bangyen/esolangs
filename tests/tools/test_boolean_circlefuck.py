"""Circlefuck boolean generation: the deleting lookup and its index."""

import random

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import run_circlefuck


def _rows(program: str, table: str, n: int) -> None:
    for combo in range(2**n):
        bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
        got = run_circlefuck(program, bits)
        assert got == table[combo], f"inputs {bits}"


class TestCirclefuck:
    def test_the_index_survives_more_than_one_digit(self) -> None:
        """Past 128 entries the index needs a carry, and it is spent right."""
        from esolangs.tools.circlefuck import _DIGIT_BITS

        n = 9
        table = "".join("1" if row % 3 == 0 else "0" for row in range(2**n))
        program = boolean.circlefuck(table)
        assert program.count("+" * (1 << _DIGIT_BITS)) == 1  # one carry gadget
        for row in (0, 127, 128, 129, 255, 256, 257, 383, 384, 511):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_circlefuck(program, bits) == table[row], row

    @pytest.mark.parametrize("fed", ["", "1\n", "x\ny\nz\n", "9\n9\n9\n"])
    def test_a_byte_outside_the_alphabet_still_lands_in_the_table(
        self, fed: str
    ) -> None:
        """Whatever is read, the index stays inside the table."""
        from esolangs.interpreters.tape_based.circlefuck import run
        from tests.interpreters.runner import run_program

        table = "01101001"
        got = run_program(run, boolean.circlefuck(table), fed)
        assert got in set(table), got

    def test_the_table_is_one_character_an_entry(self) -> None:
        """Doubling the arity doubles the program's table and nothing else."""
        rng = random.Random(11)
        sizes = {}
        for n in (10, 11, 12):
            table = "".join(rng.choice("01") for _ in range(2**n))
            sizes[n] = len(boolean.circlefuck(table))
        grew = sizes[11] - sizes[10]
        assert abs(grew - 2**10) < 0.1 * 2**10, grew
        assert abs((sizes[12] - sizes[11]) - 2 * grew) < 0.1 * 2**10

    def test_an_inessential_input_is_read_but_not_tabulated(self) -> None:
        """A degenerate table is the smaller table it really is."""
        assert len(boolean.circlefuck("11111111")) < len(
            boolean.circlefuck("10101010"),
        )
        assert len(boolean.circlefuck("10101010")) < len(
            boolean.circlefuck("10010110"),
        )
        assert len(boolean.circlefuck("11110000")) < len(
            boolean.circlefuck("10010110"),
        )
        _rows(boolean.circlefuck("11111111"), "11111111", 3)
        _rows(boolean.circlefuck("11110000"), "11110000", 3)
