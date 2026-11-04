"""Tests for the Parenthesys Boolean generator."""

import pytest

import esolangs
from esolangs.languages.parenthesys.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.event_io import ReadFirstIO

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


#: n=5 and 6 take the packed route, whose bit test reads every position.
PACKED = ["0110100110010110" * 2, "00010111" * 8, "1" + "0" * 63, "0" * 63 + "1"]


@pytest.mark.parametrize(
    "table", [*TABLES, "00010111", "01101001", "11101000", *PACKED]
)
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1

    program = esolangs.generate("Parenthesys", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Parenthesys", bits)
        io = ReadFirstIO(stdin + "Q", expected=n)
        run(program, io)
        got = io.getvalue()
        assert io.past_end == 0
        assert io.input_token() == "Q"
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Parenthesys", got) == table[row], (table, row)


@pytest.mark.parametrize("n", range(1, 13))
@pytest.mark.parametrize("bit", "01")
def test_constants_read_every_input_and_leave_the_next(n: int, bit: str) -> None:
    for row in sorted({0, (1 << n) // 3, (1 << n) - 1}):
        program = esolangs.generate("Parenthesys", bit * (1 << n))
        if n == 8:
            assert len(program) == 11
        io = ScriptedIO("\n".join(f"{row:0{n}b}") + "\n9\n")
        run(program, io)
        assert io.getvalue() == bit
        assert io.reads == n
        assert io.input_token() == "9"
