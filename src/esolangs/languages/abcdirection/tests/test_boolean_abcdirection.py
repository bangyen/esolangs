"""Tests for the ABCDirection Boolean generator."""

import random

import pytest

import esolangs
from esolangs.generation.token_balance import rendered_side
from esolangs.generation.wrap import balance_score
from esolangs.languages.abcdirection.generator import _floor, _plan, abcdirection

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("ABCDirection", table)
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("ABCDirection", bits)
        got = esolangs.run("ABCDirection", program, stdin=stdin, timeout=5)
        # The answer as the contract reads it, not the raw output.
        assert esolangs.read_answer("ABCDirection", got) == table[row], (table, row)


def _swept_side(table: str) -> int:
    """The squarest side over every helix width and the flat layout: the oracle."""
    n = len(table).bit_length() - 1
    flat = abcdirection(table)
    widths = range(_floor(table, n), len(flat.split("\n")[0]))
    helix = (rendered_side(w, _plan(table, n, w).height) for w in widths)
    return min(balance_score(flat)[0], *helix)


def test_balance_is_near_the_swept_optimum() -> None:
    """Two named widths stay within 10% of the best of every width (sum)."""
    rng = random.Random(3)
    tables = [
        "".join(rng.choice("01") for _ in range(1 << n))
        for n in range(2, 7)
        for _ in range(8)
    ]
    got = swept = 0
    for table in tables:
        program = str(esolangs.generate("ABCDirection", table, balance=True))
        got += balance_score(program)[0]
        swept += _swept_side(table)
    assert swept <= got <= 1.1 * swept
