"""Tests for the Shakespeare Boolean generator."""

import random

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


def _wrong_rows(table: str, program: str) -> int:
    n = len(table).bit_length() - 1
    wrong = 0
    for row in range(len(table)):
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Shakespeare", bits)
        got = esolangs.run("Shakespeare", program, stdin=stdin, timeout=5)
        wrong += esolangs.read_answer("Shakespeare", got) != table[row]
    return wrong


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    assert _wrong_rows(table, esolangs.generate("Shakespeare", table)) == 0


@pytest.mark.parametrize("n", [5, 6])
def test_random_tables_past_the_chunk_width_compute_their_rows(n: int) -> None:
    """A 64-row table packs in one sentence; 128 and up need several."""
    rng = random.Random(n)
    for table in (format(rng.getrandbits(2**n), f"0{2**n}b"), "01" * 2 ** (n - 1)):
        assert _wrong_rows(table, esolangs.generate("Shakespeare", table)) == 0


def test_a_flipped_bit_is_caught() -> None:
    """Positive control: a program built for another table fails some row."""
    table = "01101001"
    flipped = "01101011"
    assert _wrong_rows(flipped, esolangs.generate("Shakespeare", table)) > 0


def test_the_majority_polarity_packs_the_complement() -> None:
    """OR has one zero: its complement is the number 1, not 255 set bits."""
    assert len(esolangs.generate("Shakespeare", "01111111")) < len(
        esolangs.generate("Shakespeare", "01101001")
    )
