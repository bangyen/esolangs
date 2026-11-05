"""The Execution column's command formulas hold at small n, over every row.

Each was derived from its generator, not fitted: a fit from parity data
(brainfuck 69n + 41) was beaten by random tables, 458 > 455 at n=6.  An
``exact`` formula must also be reached here; ``bound`` only never exceeded.
"""

from tests.proofs._ledger import load as load_ledger
from tests.proofs.execution import FORMULAS
from tests.support.generator_support import CHECK


def test_every_formula_cell_is_checked() -> None:
    """Every bounded or exact Execution clause has a formula here, and back."""
    stated = {
        row.generator
        for row in load_ledger().rows
        if row.execution_clause.startswith(("worst ", "at most ", "exact "))
    }
    unchecked = sorted(stated - set(FORMULAS))
    assert not unchecked, f"{unchecked} state a bound with no FORMULAS row; {CHECK}"
    orphaned = sorted(set(FORMULAS) - stated)
    assert not orphaned, f"remove {orphaned} from FORMULAS: no stated bound"
