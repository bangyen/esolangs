"""Executed terminal transfers and the Factor tree's leading coefficient."""

import itertools
import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import run as run_brainfuck
from esolangs.interpreters.tape_based.factor import run
from esolangs.tools.factor import _program, factor


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
        witness = _program(table)
        for bits in itertools.product("01", repeat=n):
            io = ScriptedIO("\n".join(bits))
            run(program, io)
            assert io.getvalue() == table[int("".join(bits), 2)]
            io = ScriptedIO("\n".join(bits))
            run_brainfuck(witness, io)
            assert io.getvalue() == table[int("".join(bits), 2)]


@pytest.mark.medium
def test_three_input_digit_total() -> None:
    total = sum(len(factor(format(i, "08b"))) for i in range(256))
    assert total == 111004
    assert total * 100 < 106465 * 105


def test_terminal_tree_character_bound() -> None:
    rng = random.Random(918)
    for n in range(2, 13):
        bound = 27 * 2 ** (n - 1) + 16 * n + 14
        assert len(_program("10" * 2 ** (n - 1))) == bound
        tables = (
            [format(i, f"0{2**n}b") for i in range(2 ** (2**n))]
            if n <= 3
            else ["".join(rng.choice("01") for _ in range(2**n)) for _ in range(8)]
        )
        for table in tables:
            assert len(_program(table)) <= bound


def test_constant_bracket_is_below_three() -> None:
    import math

    from tests.proofs._factor_normal import prefix_growth

    lower = math.log(2) ** 2 / (math.log(prefix_growth()) * math.log(10))
    upper = (29 / 32) * (15 / 14) * math.log10(2)
    assert upper / lower == pytest.approx(2.535422861779615)
    assert upper < 3 * lower
