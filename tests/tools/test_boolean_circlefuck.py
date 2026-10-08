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
    @pytest.mark.parametrize(
        ("values", "n"),
        [
            ([0, 255], 1),
            ([48, 49, 50, 51], 2),
        ],
    )
    def test_byte_values(self, values: list[int], n: int) -> None:
        """The table under the generator holds arbitrary bytes."""
        from esolangs.tools.circlefuck import _circlefuck_table

        program = _circlefuck_table(values)
        for combo in range(2**n):
            bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
            got = run_circlefuck(program, bits)
            assert got == chr(values[combo]), f"inputs {bits}"

    def test_the_index_survives_more_than_one_digit(self) -> None:
        """Past 128 entries the index needs a carry, and it is spent right."""
        from esolangs.tools.circlefuck import _DIGIT_BITS, _circlefuck_table

        n = 9
        table = "".join("1" if row % 3 == 0 else "0" for row in range(2**n))
        program = boolean.circlefuck(table)
        assert program.count("+" * (1 << _DIGIT_BITS)) == 1  # one carry gadget
        for row in (0, 127, 128, 129, 255, 256, 257, 383, 384, 511):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_circlefuck(program, bits) == table[row], row
        assert _circlefuck_table([48] * 2) == boolean.circlefuck("00")

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


@pytest.mark.parametrize("seed", range(3))
def test_circlefuck_essential_inputs_are_the_ones_flipping_changes(seed: int) -> None:
    """The sibling-block scan finds exactly the inputs the table depends on."""
    from esolangs.tools.circlefuck import _essential_byte_inputs

    rng = random.Random(seed)
    n = rng.randint(1, 8)
    # A function of a random subset of the inputs, so most are inessential.
    subset = sorted(rng.sample(range(n), rng.randint(0, n)))
    values = [rng.choice((48, 49, 7)) for _ in range(2 ** len(subset))]
    table = []
    for row in range(2**n):
        index = 0
        for i in subset:
            index = (index << 1) | ((row >> (n - 1 - i)) & 1)
        table.append(values[index])
    expected = [
        i
        for i in range(n)
        if any(table[row] != table[row ^ (1 << (n - 1 - i))] for row in range(2**n))
    ]
    assert _essential_byte_inputs(table, n) == expected


@pytest.mark.parametrize("seed", range(4))
def test_circlefuck_projection_is_the_table_over_its_essential_inputs(
    seed: int,
) -> None:
    """Projecting and then re-expanding gives the table back."""
    from esolangs.tools.circlefuck import _essential_byte_inputs, _projected

    rng = random.Random(seed)
    n = rng.randint(1, 7)
    subset = sorted(rng.sample(range(n), rng.randint(1, n)))
    values = [rng.choice((48, 49)) for _ in range(2 ** len(subset))]
    table = []
    for row in range(2**n):
        key = 0
        for i in subset:
            key = (key << 1) | ((row >> (n - 1 - i)) & 1)
        table.append(values[key])
    essential = _essential_byte_inputs(table, n)
    rows = _projected(table, n, essential)
    assert len(rows) == 2 ** len(essential)
    for row in range(2**n):
        key = 0
        for i in essential:
            key = (key << 1) | ((row >> (n - 1 - i)) & 1)
        assert rows[key] == table[row], row
