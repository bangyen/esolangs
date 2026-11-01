"""Tests for the HQ9+ with headers Boolean generator."""

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("HQ9+ with headers", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("HQ9+ with headers", bits)
        got = esolangs.run("HQ9+ with headers", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("HQ9+ with headers", got) == table[row], (
            table,
            row,
        )


@pytest.mark.parametrize("bit", ["0", "1"])
@pytest.mark.parametrize("n", [1, 8])
def test_constant_output_consumes_every_input(bit: str, n: int) -> None:
    """Direct output still consumes exactly one number per input."""
    from esolangs.languages.hq9_with_headers.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    program = esolangs.generate("HQ9+ with headers", bit * (1 << n))
    stdin = esolangs.encode_inputs("HQ9+ with headers", [1] * n)
    io = ScriptedIO(stdin + "7\n")
    run(str(program), io)
    assert io.getvalue() == bit
    assert io.position() == len(stdin)
    assert io.input_num() == 7
    if n == 8:
        assert len(str(program)) == 180
