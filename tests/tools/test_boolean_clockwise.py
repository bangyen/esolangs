"""Covers :mod:`esolangs.tools.clockwise`."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_clockwise,
)


def _bits(combo: int, n: int) -> list[str]:
    """The input digits for a table row, MSB first."""
    return [str((combo >> (n - 1 - i)) & 1) for i in range(n)]


class TestClockwise:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),
            ("10", 1),
            ("00", 1),
            ("11", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("00000001", 3),  # AND3
            ("1000000000000000", 4),  # AND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination prints the result as an ASCII digit."""
        program = boolean.clockwise(table)
        for combo in range(2**n):
            bits = _bits(combo, n)
            got = run_clockwise(program, bits)
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.medium
    def test_the_lookup_computes_every_row_at_five_and_six_inputs(self) -> None:
        """The indexed table answers two dense five- and six-input tables."""
        for n in (5, 6):
            size = 1 << n
            tables = (
                ("01101001" * (size // 8))[:size],
                "".join(str((i * 73 + i // 3) & 1) for i in range(size)),
            )
            for table in tables:
                program = boolean.clockwise(table)
                for combo in range(size):
                    assert run_clockwise(program, _bits(combo, n)) == table[combo]

    def test_ring_starts_at_origin(self) -> None:
        """The program is a closed ring whose pointer starts at (0, 0)."""
        program = boolean.clockwise("0110")
        lines = program.splitlines()
        assert lines[0][0] == " "
        assert run_clockwise(program, ["1", "0"]) == "1"  # XOR(1, 0)

    def test_the_table_is_one_cell_per_entry(self) -> None:
        """The construction's signature: the answer row holds the table itself.

        A tree spends a node per level per leaf; this spends one ``+`` per
        set entry on a single row, and the countdown row above it one ``!``
        per entry whatever the table says.  Flipping one row of the table
        therefore moves exactly one character, which is what says the table
        is stored rather than routed.
        """
        n = 5
        size = 1 << n
        table = ["0"] * size
        base = boolean.clockwise("".join(table))
        for entry in (0, 1, 7, size - 1):
            table[entry] = "1"
            flipped = boolean.clockwise("".join(table))
            table[entry] = "0"
            differ = [
                (row, col)
                for row, (before, after) in enumerate(
                    zip(base.splitlines(), flipped.splitlines(), strict=True)
                )
                for col, (old, new) in enumerate(
                    zip(before.ljust(len(after)), after, strict=True)
                )
                if old != new
            ]
            assert len(differ) == 1, (entry, differ)
            assert flipped.splitlines()[differ[0][0]][differ[0][1]] == "+"

    def test_every_run_reads_each_input_exactly_once(self) -> None:
        """Clockwise's input queue rotates, so a run must consume 7n bits.

        The reads do not drain the queue, they rotate it; a program that read
        a different number of bits on different rows would leave the queue
        somewhere else each time and desync a caller feeding several
        programs from one stream.  Seven reads an input, every input, is
        what makes the rotation a whole turn -- so the queue at the end is
        the queue at the start, for every row of the table.
        """
        from esolangs.interpreters.grid_based.clockwise import _Machine
        from esolangs.interpreters.io import IO

        class _Quiet(IO):
            def __init__(self, text: str) -> None:
                self._text = text

            def input_str(self) -> str:
                return self._text

            def print_char(self, char: str) -> None:
                pass

        for n in (1, 2, 3):
            table = "01101001"[: 2**n].ljust(2**n, "1")
            program = boolean.clockwise(table)
            for combo in range(2**n):
                machine = _Machine(
                    program.splitlines(), _Quiet("".join(_bits(combo, n)))
                )
                start = machine.inp
                steps = 0
                while not machine.halted:
                    machine.step()
                    steps += 1
                    assert steps < 100_000, "run did not close the ring"
                assert machine.inp == start, (n, combo)

    def test_size_is_linear_in_the_table(self) -> None:
        """Four table rows and a doubling chain: both linear, so size is.

        The chain's gadgets double in width as the level rises, so the whole
        chain costs a constant times its top gadget; the table costs its five
        rows.  Doubling the table therefore roughly doubles the program,
        which a tree's per-level rows would not do.
        """
        sizes = [len(boolean.clockwise("01101001" * (2 ** (n - 3)))) for n in (5, 7, 9)]
        rise = (sizes[2] - sizes[1]) / (sizes[1] - sizes[0])
        assert 3.5 < rise < 4.4, sizes
        assert sizes[2] / 2**9 < 20, sizes
