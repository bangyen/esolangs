"""Tests for the Interprogck8 Boolean generator."""

import random

import pytest

import esolangs

#: Every one- and two-input table; a tree's folding bugs show here first.
TABLES = [format(i, f"0{2**n}b") for n in (1, 2) for i in range(2**2**n)]


def _answer(program: str, n: int, row: int) -> str:
    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
    stdin = esolangs.encode_inputs("Interprogck8", bits)
    got = esolangs.run("Interprogck8", program, stdin=stdin, timeout=30)
    return esolangs.read_answer("Interprogck8", got)


@pytest.mark.parametrize("table", [*TABLES, "00010111", "01101001", "11101000"])
def test_every_row_prints_its_answer(table: str) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    n = len(table).bit_length() - 1
    program = esolangs.generate("Interprogck8", table)
    for row in range(len(table)):
        assert _answer(program, n, row) == table[row], (table, row)


@pytest.mark.medium
@pytest.mark.parametrize("one", [1, 1071414])
def test_a_deep_path_keeps_its_flights_apart(one: int) -> None:
    """A one-hot table keeps a flight pending at every height of its path.

    Each flight's stop must sit at its own column, in a window past the
    rung's, so no flight lands on a shallower one's stop.
    """
    n = 22
    table = "0" * one + "1" + "0" * ((1 << n) - one - 1)
    program = esolangs.generate("Interprogck8", table)
    for row in (one, one ^ 1, one ^ (1 << (n - 1)), 0):
        assert _answer(program, n, row) == table[row], row


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(2))
def test_flights_land_on_their_stops_across_windows(seed: int) -> None:
    """Sparse eight-input tables put flights over several windows and clusters."""
    rng = random.Random(seed)
    n = 8
    table = "".join("1" if rng.random() < 0.1 else "0" for _ in range(1 << n))
    program = esolangs.generate("Interprogck8", table)
    assert len(str(program).split("\n")) > 126 * 4
    for row in range(1 << n):
        assert _answer(program, n, row) == table[row], (seed, row)


def test_three_input_program_keeps_its_measured_length() -> None:
    """Three inputs take one cluster window and a tail: 472 lines."""
    table = "00011110"
    program = esolangs.generate("Interprogck8", table)
    assert len(str(program).split("\n")) == 472
    for row in range(8):
        assert _answer(program, 3, row) == table[row], row


def test_parity_costs_the_same_per_entry_at_every_arity() -> None:
    """Windows are 126 lines whatever ``n``: a rung every 126 lines, and a flat size."""
    sizes = {}
    for n in (8, 10, 12):
        parity = "".join(str(bin(i).count("1") % 2) for i in range(1 << n))
        program = str(esolangs.generate("Interprogck8", parity))
        lines = program.split("\n")
        assert all(lines[k] == "DownAccLines" for k in range(0, len(lines) - 82, 126))
        sizes[n] = len(program) / (1 << n)
    assert max(sizes.values()) - min(sizes.values()) < 0.5, sizes
