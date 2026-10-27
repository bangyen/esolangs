"""The Workspace column's bit formulas hold at small n, over every row.

Each was derived from the interpreter's snapshot and the generator, not
fitted.  ``L`` is the program's length, ``T`` is 2^n; ``exact`` formulas must be reached
on some table here, ``bound`` ones only never exceeded.
"""

from collections.abc import Callable

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from tests.proofs._arities import formula_arities
from tests.proofs._formula import exact_at, ledger_formulas
from tests.proofs._ledger import load as load_ledger
from tests.proofs._witnesses import band_marks
from tests.proofs.test_execution_formulas import FORMULAS as EXECUTION_FORMULAS
from tests.proofs.test_execution_formulas import _measure, _tables
from tests.support.generator_support import CHECK

#: Formulas the ledger notation cannot state: a case split, a definition,
#: a count taken from the program.  Each lives on its language's
#: ``proof_workspace`` (``proof_formulas.py`` in its package); this table
#: holds only entries that cannot relocate, with the reason.
_HAND: dict[str, tuple[Callable[[int, str], int], bool, tuple[int, ...]]] = {}

#: Arities where the default (see ``ledger_formulas``) is too slow or too
#: shallow for the construction, aggregated from each package's
#: ``[formula_arities]`` section.
_ARITIES = formula_arities("workspace")
#: Generator -> (formula, exact?, arities): the ledger's own clause where
#: it parses (``tests/proofs/_formula.py``), else ``_HAND``.
_HAND.update(
    (name, lang.proof_workspace)
    for name, lang in LANGUAGES.items()
    if lang.proof_workspace is not None
)
FORMULAS = ledger_formulas(
    lambda row: row.workspace_clause if " bits" in row.workspace_clause else "",
    _HAND,
    _ARITIES,
    column="workspace",
)


# language-owners: ["6-5", "Container", "Fargo", "Malbolge", "Subleq"]
#: Smallest-arity cases that still measure past the medium band run alone
#: (Container-7 5.7s and Fargo-6 4.6s overrun under load; the 6-5 walk
#: now starts in the eight-input witness corpus; Subleq-9, its first packed
#: decoder, 28s with written state; Malbolge-3 5.3s, 16s on CI): the
#: per-step state measurement dominates, so they run in the slow band.
_SLOW_AT_MIN: frozenset[tuple[str, int]] = frozenset(
    {("Container", 7), ("6-5", 8), ("Fargo", 6), ("Malbolge", 3), ("Subleq", 9)}
)

# language-owners: ["B-tapemark"]
#: Range tops past the slow band's 600 s stop on CI: B-tapemark-8 ran 316 s,
#: then 540 s, then was killed (40570971132); locally two dense tables take
#: 61 s each of its ten.
_WEEKLY: frozenset[tuple[str, int]] = frozenset({("B-tapemark", 8)})


def _first_above_two(arities: tuple[int, ...]) -> int:
    return min((a for a in arities if a > 2), default=0)


def _formula_cases() -> list[object]:
    ledgers = (EXECUTION_FORMULAS, FORMULAS)
    cases = sorted(
        {
            (name, n)
            for ledger in ledgers
            for name, (_, _, arities) in ledger.items()
            for n in arities
        }
    )
    return [
        pytest.param(
            name,
            n,
            marks=band_marks("weekly", f"{name} formulas exact at n = {n}")
            if (name, n) in _WEEKLY
            else pytest.mark.medium
            if (name, n) not in _SLOW_AT_MIN
            and (
                n <= 2
                or any(
                    name in ledger and n == _first_above_two(ledger[name][2])
                    for ledger in ledgers
                )
            )
            else pytest.mark.slow,
        )
        for name, n in cases
    ]


@pytest.mark.parametrize(("name", "n"), _formula_cases())
def test_execution_and_workspace_formulas_hold(name: str, n: int) -> None:
    formulas = [
        (written, formula, exact)
        for written, ledger in ((False, EXECUTION_FORMULAS), (True, FORMULAS))
        if name in ledger
        for formula, exact, arities in (ledger[name],)
        if n in arities
    ]
    reached = [False] * len(formulas)
    for table in _tables(name, n):
        program = esolangs.generate(name, table)
        measurements = _measure(
            name,
            table,
            written=any(written for written, _, _ in formulas),
            program=program,
        )
        for i, (written, formula, _) in enumerate(formulas):
            claim = formula(n, program)
            actual = measurements[int(written)]
            assert actual <= claim, f"{name} n={n} {table}: {actual} > {claim}"
            reached[i] |= actual == claim
    for found, (_, _, exact) in zip(reached, formulas, strict=True):
        assert found or not exact_at(exact, n), (
            f"{name} n={n}: no table reaches the formula"
        )


def test_every_formula_cell_is_checked() -> None:
    """A ``worst``/``at most`` Workspace clause in bits has a formula here."""
    stated = {
        row.generator
        for row in load_ledger().rows
        if row.workspace_clause.startswith(("worst ", "at most "))
        and " bits" in row.workspace_clause
    }
    unchecked = sorted(stated - set(FORMULAS))
    assert not unchecked, f"{unchecked} state a bound with no FORMULAS row; {CHECK}"
    orphaned = sorted(set(FORMULAS) - stated)
    assert not orphaned, f"remove {orphaned} from FORMULAS: no stated bound"
