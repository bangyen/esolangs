"""Executed terminal transfers and the Factor tree's leading coefficient."""

import itertools
import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.factor import run
from esolangs.tools.factor import _digit_cost, _encode, _program, factor
from esolangs.tools.helpers import _greedy_input_order, permute_truth_table


@pytest.mark.medium
@pytest.mark.parametrize("n", range(1, 7))
@pytest.mark.parametrize("partition", range(2))
def test_terminal_transfer_corpus(n: int, partition: int) -> None:
    rng = random.Random(917 + n)
    tables = (
        [format(i, f"0{2**n}b") for i in range(2 ** (2**n))]
        if n <= 3
        else ["0" * 2**n, "1" * 2**n]
        + ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(8)]
    )
    for table in tables[partition::2]:
        program = factor(table)
        for bits in itertools.product("01", repeat=n):
            io = ScriptedIO("\n".join(bits))
            run(program, io)
            assert io.getvalue() == table[int("".join(bits), 2)]


@pytest.mark.medium
def test_three_input_digit_total() -> None:
    total = 0
    for i in range(256):
        table = format(i, "08b")
        greedy = _greedy_input_order(table, 3)
        old = [_program(table, (0, 1, 2))]
        if greedy != (0, 1, 2):
            old.append(_program(permute_truth_table(table, greedy), greedy))
        program = factor(table)
        assert len(program) <= len(str(_encode(min(old, key=_digit_cost))))
        total += len(program)
    # Parent: 125018 digits over all three-input tables.
    assert total == 115712


def test_terminal_tree_character_bound() -> None:
    rng = random.Random(918)
    for n in range(2, 13):
        perm = tuple(range(n))
        bound = 31 * 2 ** (n - 1) + 16 * n + 21
        assert len(_program("10" * 2 ** (n - 1), perm, binary_leaves=True)) == bound
        tables = (
            [format(i, f"0{2**n}b") for i in range(2 ** (2**n))]
            if n <= 3
            else ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(8)]
        )
        for table in tables:
            assert len(_program(table, perm, binary_leaves=True)) <= bound
