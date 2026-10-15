"""Tests for the Rubic Boolean generator."""

import pytest

import esolangs
from esolangs.languages.rubic.generator import _OPENING, _TABLE

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Rubic", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Rubic", bits)
        got = esolangs.run("Rubic", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Rubic", got) == table[row], (table, row)


def test_the_table_holds_on_both_cube_states() -> None:
    """The totality certificate: the cube is the opening's X or X·r2, and
    every expression the generator emits has its stated value on both."""

    def out(*tokens: str) -> str:
        return esolangs.run("Rubic", " ".join(tokens))

    for store in ((), ("r2",)):
        state = (*_OPENING, *store)
        assert out(*state, *_TABLE["read"][:2], "!") == chr(127)  # V = -1
        assert out(*state, *_TABLE["print0"]) == "0"
        assert out(*state, *_TABLE["print1"]) == "1"
        for bit in (0, 1):
            setter = _TABLE[f"print{bit}"][:-1]
            assert out(*state, *setter, *_TABLE["bit"], "!") == chr(bit)
        y = len(store)
        assert out(*state, *_TABLE["P"], "!") == chr(y)
        assert out(*state, *_TABLE["Q"], "!") == chr(1 - y)
