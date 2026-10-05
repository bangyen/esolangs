"""Measured Unsquare size contracts, with independent execution."""

import pytest

from esolangs.tools.unsquare import unsquare
from tests.interpreters.unsquare_observer import check


@pytest.mark.parametrize("n", range(2, 11))
def test_two_bytes_a_row(n):
    table = "".join("01"[(row * row) % 3 % 2] for row in range(1 << n))
    source = unsquare(table)
    assert len(source) - 2 * (1 << n) == 10 * n + 26
    for row in (0, (1 << n) // 2, (1 << n) - 1):
        result = check(source, format(row, f"0{n}b"))
        assert result["halted"]
        assert result["error"] is None
        assert result["output"] == table[row]
        assert result["reads"] == n


@pytest.mark.parametrize("table", ["01010101", "00110011", "00001111"])
def test_inessential_inputs_reduce_emitted_size(table):
    source = unsquare(table)
    assert len(source) < len(unsquare("01101001"))
    for row, answer in enumerate(table):
        result = check(source, format(row, "03b"))
        assert result["output"] == answer
        assert result["reads"] == 3
