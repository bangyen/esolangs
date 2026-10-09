"""Streetcode through the shared API, CLI and machinery."""

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.tools.wrap import balance_score
from tests.generator_support import evaluate_generated


@pytest.mark.medium
@pytest.mark.parametrize("table", ["01" * 32, "0" * 64])
def test_streetcode_indexed_regimes_are_balanced_and_execute(table):
    default = esolangs.generate("Streetcode", table)
    balanced = esolangs.generate("Streetcode", table, balance=True)
    widest = max(map(len, default.split("\n")))
    optimum = min(
        [default]
        + [
            esolangs.generate("Streetcode", table, width=width)
            for width in range(1, widest + 1)
        ],
        key=balance_score,
    )
    assert balance_score(balanced) == balance_score(optimum)
    assert _evaluate("Streetcode", balanced, inputs=6) == table


@pytest.mark.slow
@pytest.mark.parametrize("width", [2, 5, 11, 20, 27, 35, 36, 60])
def test_streetcode_lays_out_every_two_input_table(width: int) -> None:
    """The regression itself, kept separate so it names the language."""
    for table in ("0001", "0010", "1101", "1110", "0110"):
        assert evaluate_generated("Streetcode", table, timeout=30, width=width) == table
