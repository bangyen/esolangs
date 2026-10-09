"""Tests for the Subleq interpreter."""

import random

import pytest

from esolangs.interpreters.tape_based.subleq import _Machine
from tests.interpreters.semantic_oracles import STDINS, agrees
from tests.interpreters.semantic_oracles import subleq as oracle
from tests.raises import assert_halts_with_hint, assert_rejected_with_hint


@pytest.mark.medium
def test_bad_programs_carry_a_repair_hint() -> None:
    assert_rejected_with_hint("Subleq", "x", "decimal integers")
    assert_halts_with_hint("Subleq", "0 0", "incomplete Subleq", "three addresses")


def _corpus():
    yield from ["", "12 13 -1", "3 -1 0 321", "-1 9 0 9 -1 0 9 9 -1 0", "0 0 0"]
    yield from ["9 3 3 9 -1 6 9 9 -1 3", "12 13 6 12 -1 9 13 -1 9 12 12 -1 3 2"]
    yield "12 13 6 12 -1 9 13 -1 9 12 12 -1 1 2"
    rng = random.Random(1702)
    for _ in range(96):
        cells = []
        for _ in range(3):
            a, b = rng.choice([9, 10, 11]), rng.choice([9, 10, 11])
            mode = rng.randrange(3)
            if mode == 1:
                a = -1
            elif mode == 2:
                b = -1
            cells.extend([a, b, rng.choice([-1, 0, 3, 6, 12])])
        cells.extend(rng.choices([-257, -1, 0, 1, 256, 321], k=3))
        yield " ".join(map(str, cells))


@pytest.mark.parametrize("stdin", STDINS)
def test_bounded_programs_match_the_oracle(stdin):
    for code in _corpus():
        agrees(_Machine, oracle, code, stdin)


@pytest.mark.parametrize(
    ("code", "outcome"),
    [
        ("x", ValueError),
        ("0", RuntimeError),
        ("-2 0 -1", ValueError),
        ("6 -1 0 6 6 -1 -1", "\xff"),
    ],
)
def test_oracle_controls(code, outcome):
    result = agrees(_Machine, oracle, code, "\x81")
    if isinstance(outcome, str):
        assert (result.halted, result.output) == (True, outcome)
    else:
        assert isinstance(result, outcome)
    assert not agrees(_Machine, oracle, "0 0 0", "").halted
