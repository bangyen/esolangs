"""The Scaling column's size bounds hold at small n, over every row.

A cell stating ``at most <formula> characters`` (or ``lines``/``rows``; a
``worst`` one must also be reached) is measured on the generated text:
characters are ``len``, lines and rows are newline-separated.  Two such
bounds were false while nothing measured them: one 14T where parity reaches
15T - 14, one 6n + 3T rows reaching 17 at n=1.
"""

import re

import pytest

import esolangs
from tests.proofs._formula import ledger_formulas
from tests.proofs._ledger import load as load_ledger
from tests.proofs.test_execution_formulas import _tables
from tests.support.generator_support import CHECK

#: A stated size bound: the unit follows its formula.
_SIZE = re.compile(r"^(?:at most|worst) (.+?) (characters|lines|rows)\b")

FORMULAS = ledger_formulas(lambda row: row.scaling_clause, {}, {})
_UNIT = {
    row.generator: match.group(2)
    for row in load_ledger().rows
    if (match := _SIZE.match(row.scaling_clause))
}


@pytest.mark.parametrize(
    ("name", "n"), [(name, n) for name in sorted(FORMULAS) for n in FORMULAS[name][2]]
)
def test_size_formulas_hold(name: str, n: int) -> None:
    formula, exact, _ = FORMULAS[name]
    reached = False
    for table in _tables(name, n):
        text = str(esolangs.generate(name, table))
        size = len(text) if _UNIT[name] == "characters" else text.count("\n") + 1
        claim = formula(n, text)
        assert size <= claim, f"{name} n={n} {table}: {size} > {claim} {_UNIT[name]}"
        reached |= size == claim
    assert reached or not exact, f"{name} n={n}: no table reaches the formula"


def test_every_size_cell_is_checked() -> None:
    """A Scaling clause stating a size bound has a formula here, and back."""
    assert set(FORMULAS) == set(_UNIT), CHECK
