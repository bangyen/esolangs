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


def test_balance_of_the_constant_zero_n3_is_exact() -> None:
    """The helix's print units are priced at their real width: (side, length, width)."""
    program = str(esolangs.generate("ABCDirection", "00000000", balance=True))
    assert balance_score(program) == (42, 839, 39)


def test_balance_of_xor_n2_is_exact() -> None:
    """The tight width charges reads and band cells, not the write: 40x16."""
    program = str(esolangs.generate("ABCDirection", "0110", balance=True))
    assert balance_score(program) == (40, 655, 40)


def test_balance_of_a_four_input_table_is_exact() -> None:
    """The width model prices each print unit at five columns; pricing
    one at six widens the helix a full lap: (side, length, width)."""
    program = str(esolangs.generate("ABCDirection", "1010010010000110", balance=True))
    assert balance_score(program) == (49, 1049, 49)


def test_balance_of_parity_n8_cuts_the_long_runs() -> None:
    """Runs over 2 * sqrt(T) split into gadgets; uncut, the 136-column first
    gadget held the side at 140: (side, length, width)."""
    table = "".join(str(bin(row).count("1") & 1) for row in range(256))
    program = str(esolangs.generate("ABCDirection", table, balance=True))
    assert balance_score(program) == (86, 3566, 86)


def test_balance_of_not_n1_is_exact() -> None:
    """The tight width's slack is four columns, for the lap's landing
    and drop; a fifth widens even the one-input helix: (35, 575, 35)."""
    program = str(esolangs.generate("ABCDirection", "01", balance=True))
    assert balance_score(program) == (35, 575, 35)
