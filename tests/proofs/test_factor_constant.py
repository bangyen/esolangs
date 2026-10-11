"""Executed terminal transfers and the Factor tree's leading coefficient."""

import itertools
import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import run as run_brainfuck
from esolangs.interpreters.tape_based.factor import run
from esolangs.tools.factor import _program, factor
from tests.proofs._factor_counter import counter_program
from tests.proofs._factor_normal import FORBIDDEN, prefix_normalize
from tests.proofs._factor_semantic import (
    behaviour,
    corpus,
    delete_pattern,
    first_output,
)
from tests.support.witness_tables import witnesses


@pytest.mark.parametrize("n", range(1, 6))
def test_terminal_transfer_corpus(n: int) -> None:
    for table in witnesses(n):
        program = factor(table)
        witness = _program(table)
        for bits in itertools.product("01", repeat=n):
            io = ScriptedIO("".join(bits))
            run(program, io)
            assert io.getvalue() == table[int("".join(bits), 2)]
            io = ScriptedIO("".join(bits))
            run_brainfuck(witness, io)
            assert io.getvalue() == table[int("".join(bits), 2)]


@pytest.mark.medium
def test_three_input_digit_total() -> None:
    total = sum(len(factor(format(i, "08b"))) for i in range(256))
    # Skipping normalization in the two constants removes 138 digits.
    assert total == 102719
    assert total * 100 < 106465 * 105


def test_terminal_tree_character_bound() -> None:
    rng = random.Random(918)
    for n in range(2, 13):
        # Siblings that agree go untested, so at most half the bottom pairs
        # are the costlier "10"; parity reaches that with "10" and "01".
        bound = 51 * 2 ** (n - 2) + 16 * n + 14
        parity = "".join(str(r.bit_count() & 1) for r in range(2**n))
        assert len(_program(parity)) == bound
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
    assert upper / lower == pytest.approx(2.4979448548959384)
    assert upper < 3 * lower


@pytest.mark.medium
def test_normalization_collapse_corpus() -> None:
    """Prefix normalization is behaviour-preserving but only 2-to-1 here."""
    descriptions: dict[str, tuple[tuple[object, ...], ...]] = {}
    behaviours: set[tuple[tuple[object, ...], ...]] = set()
    for n, table in corpus(parity_to=6):
        code = counter_program(table)
        for description in (code, prefix_normalize(code)):
            signature = behaviour(description, n)
            assert all(row[0] == "out" for row in signature)
            assert "".join(str(row[1]) for row in signature) == table
            descriptions[description] = signature
            behaviours.add(signature)
    # 279 tables give 558 raw/prefix-normal descriptions but only 279
    # behaviours: each table's two forms collapse to one, a constant factor.
    assert (len(descriptions), len(behaviours)) == (558, 279)
    assert len(behaviours) / len(descriptions) == 0.5


@pytest.mark.medium
def test_pointer_pair_rule_holds_on_a_growing_tape() -> None:
    """`<>` is a no-op even at cell zero, since the tape grows left."""
    assert "<>" in FORBIDDEN
    for n, table in corpus(parity_to=6):
        code = counter_program(table)
        assert "<>" not in prefix_normalize(code)
        deleted = delete_pattern(code, "<>")
        for row in range(2**n):
            bits = format(row, f"0{n}b")
            assert first_output(code, bits) == first_output(deleted, bits)

    # The clamped edge's counterexample: `,<>.` now prints what `,` read.
    assert first_output(",<>.", "0") == first_output(",.", "0") == ("out", "0", 1)
