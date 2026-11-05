"""Streetcode through the shared API, CLI and machinery."""

import pytest

from esolangs import compat, generate
from esolangs.generation.wrap import balance_score
from tests.support.evaluation import _evaluate
from tests.support.generator_support import evaluate_generated


@pytest.mark.medium
@pytest.mark.parametrize("table", ["01" * 32, "0" * 64])
def test_streetcode_indexed_regimes_are_balanced_and_execute(table) -> None:
    default = compat.generate("Streetcode", table)
    balanced = compat.generate("Streetcode", table, balance=True)
    widest = max(map(len, default.split("\n")))
    optimum = min(
        [default]
        + [
            compat.generate("Streetcode", table, width=width)
            for width in range(1, widest + 1)
        ],
        key=balance_score,
    )
    # The fold, which no width selects, may beat every width.
    assert balance_score(balanced) <= balance_score(optimum)
    assert _evaluate("Streetcode", balanced, inputs=6) == table


@pytest.mark.slow
@pytest.mark.parametrize("width", [2, 5, 11, 20, 27, 35, 36, 60])
def test_streetcode_lays_out_every_two_input_table(width: int) -> None:
    """The regression itself, kept separate so it names the language."""
    for table in ("0001", "0010", "1101", "1110", "0110"):
        assert evaluate_generated("Streetcode", table, timeout=30, width=width) == table


def test_fitting_narrow_lookup_still_shares_its_kerb() -> None:
    table = "00000011"
    program = generate("Streetcode", table, width=40).source
    rows = program.splitlines()
    assert len(rows) == 165
    assert max(map(len, rows)) == 7
    assert evaluate_generated("Streetcode", table, width=40) == table
