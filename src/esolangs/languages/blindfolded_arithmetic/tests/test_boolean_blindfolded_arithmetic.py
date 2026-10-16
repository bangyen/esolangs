"""Tests for the Blindfolded Arithmetic Boolean generator."""

import pytest

import esolangs
from tests.support.stdin_check import _check_stdin

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Blindfolded Arithmetic", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Blindfolded Arithmetic", bits)
        got = esolangs.run("Blindfolded Arithmetic", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("Blindfolded Arithmetic", got) == table[row], (
            table,
            row,
        )


def test_the_input_is_the_row_number() -> None:
    """The input must be positive, so row 0 is fed as 1."""
    assert esolangs.describe("Blindfolded Arithmetic")["input_shape"] == "row_number"
    assert esolangs.encode_inputs("Blindfolded Arithmetic", [0, 0]) == "1\n"
    assert esolangs.encode_inputs("Blindfolded Arithmetic", [1, 0]) == "3\n"


@pytest.mark.parametrize("stdin", ["0\n", "5\n"])
def test_a_row_number_outside_one_to_t_is_refused(stdin: str) -> None:
    with pytest.raises(esolangs.ArgumentError, match=r"out of range.*\(1\.\.4\)"):
        _check_stdin("Blindfolded Arithmetic", stdin, "0110")
