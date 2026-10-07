"""The Workspace column's bit formulas hold at small n, over every row.

Each was derived from the interpreter's snapshot and the generator, not
fitted.  ``L`` is the program's length; ``exact`` formulas must be reached
on some table here, ``bound`` ones only never exceeded.
"""

from collections.abc import Callable

import pytest

import esolangs
from tests.proofs._ledger import load as load_ledger
from tests.proofs.test_execution_formulas import _tables, _worst

bl = int.bit_length

#: Generator -> (bits from n and the program, exact?, arities).  Mirrors the ledger.
FORMULAS: dict[str, tuple[Callable[[int, str], int], bool, tuple[int, ...]]] = {
    "Fish": (lambda n, _: n + 13 + bl(9 * n + 8) + bl(n), True, (3, 6)),
    "Home Row": (lambda n, _: n + 32 + bl(14 * 2**n + 10 * n + 15), True, (3, 5)),
    "Minsky Swap": (lambda n, _: n + 3 + bl(2 ** (n + 1) + 6 * n + 5), True, (3, 6)),
    "Factor": (
        lambda n, _: (
            7 * n + 12 + bl(2 * n + 1) + bl(n) + bl(27 * 2 ** (n - 1) + 16 * n + 14)
        ),
        True,
        (4,),
    ),
    "Clockwise": (
        lambda n, _: 57 * n + 50 + bl(2 * n + 14) + bl(2 ** (n + 1) + 9 * n + 1),
        True,
        (3, 6),
    ),
    "CV(N)(C)": (lambda n, _: 2 * n + 20 + bl(2 * n - 1), True, (4, 6)),
    "Container": (lambda n, _: 25 * n + 154 + bl(2 * n + 2) + 2 * bl(n), True, (7,)),
    "BF-PDA": (lambda n, _: 3 * n + 4, True, (3, 6)),
    "Back": (
        lambda n, _: n + 5 + bl(max(6 * n - 2, 2**n - 1)) + bl(3 * n + 4) + bl(n),
        True,
        (3, 6),
    ),
    "Alight": (lambda n, _: 72 * n + 762 + bl(6 * n + 12) + bl(n), True, (3, 5)),
    "brainfuck": (
        lambda n, p: 2 * n + 6 + bl(2 * n) + bl(n) + bl(len(p)),
        True,
        (3, 6),
    ),
    "BrainIf": (lambda n, p: 13 + bl(len(p.splitlines())) + bl(n), True, (3, 6)),
    "Jaune": (
        lambda n, _: n + 1 + bl(5 * 2**n + 5 * n - 4) + bl(n - 1) + bl(2 * n - 1),
        False,
        (3, 6),
    ),
    "FALSE": (lambda n, _: (2 * n + 56) * (n + 4) + n + 1 + bl(n), False, (3, 5)),
    "Sophie": (lambda n, p: bl(len(p)) + bl(n) + 7, False, (3, 6)),
}


@pytest.mark.medium
@pytest.mark.parametrize("name", sorted(FORMULAS))
def test_the_workspace_formula_holds(name: str) -> None:
    formula, exact, arities = FORMULAS[name]
    for n in arities:
        reached = False
        for table in _tables(name, n):
            claim = formula(n, esolangs.generate(name, table))
            bits = _worst(name, table, written=True)
            assert bits <= claim, f"{name} n={n} {table}: {bits} > {claim}"
            reached |= bits == claim
        assert reached or not exact, f"{name} n={n}: no table reaches the formula"


def test_every_formula_cell_is_checked() -> None:
    """A ``worst``/``at most`` Workspace clause in bits has a formula here."""
    stated = {
        row.generator
        for row in load_ledger().rows
        if row.workspace_clause.startswith(("worst ", "at most "))
        and " bits" in row.workspace_clause
    }
    assert stated == set(FORMULAS)
