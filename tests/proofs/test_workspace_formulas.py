"""The Workspace column's bit formulas hold at small n, over every row.

Each was derived from the interpreter's snapshot and the generator, not
fitted.  ``L`` is the program's length, ``T`` is 2^n; ``exact`` formulas must be reached
on some table here, ``bound`` ones only never exceeded.
"""

import pytest

import esolangs
from tests.proofs._formula import exact_at
from tests.proofs._ledger import load as load_ledger
from tests.proofs._witnesses import band_marks
from tests.proofs.execution import FORMULAS as EXECUTION_FORMULAS
from tests.proofs.execution import measure as _measure
from tests.proofs.execution import tables as _tables
from tests.proofs.workspace import FORMULAS
from tests.support.generator_support import CHECK

# language-owners: ["6-5", "Container", "Fargo", "Malbolge", "Subleq"]
#: Smallest-arity cases that still measure past the medium band run alone
#: (Container-7 5.7s and Fargo-6 4.6s overrun under load; the 6-5 walk
#: now starts in the eight-input witness corpus; Subleq-9, its first packed
#: decoder, 28s with written state; Malbolge-3 5.3s, 16s on CI): the
#: per-step state measurement dominates, so they run in the slow band.
_SLOW_AT_MIN: frozenset[tuple[str, int]] = frozenset(
    {("Container", 7), ("6-5", 8), ("Fargo", 6), ("Malbolge", 3), ("Subleq", 9)}
)


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
    # Arities above the first per push reach no code it misses (coverage
    # over Interprogck8, Polynomial and Unary, 2026-10-28) and only back the
    # ledger's ranges, 77% of the slow band's ~1,020 s: they run weekly.
    return [
        pytest.param(
            name,
            n,
            marks=pytest.mark.slow
            if (name, n) in _SLOW_AT_MIN
            else pytest.mark.medium
            if n <= 2
            or any(
                name in ledger and n == _first_above_two(ledger[name][2])
                for ledger in ledgers
            )
            else band_marks("weekly", f"{name} formulas exact at n = {n}"),
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
            claim = formula(n, program.source)
            actual = measurements[int(written)]
            assert actual <= claim, f"{name} n={n} {table}: {actual} > {claim}"
            reached[i] |= actual == claim
    for found, (_, _, exact) in zip(reached, formulas, strict=True):
        assert found or not exact_at(exact, n), (
            f"{name} n={n}: no table reaches the formula"
        )


def test_every_formula_cell_is_checked() -> None:
    """Every bounded or exact Workspace clause in bits has a formula here."""
    stated = {
        row.generator for row in load_ledger().rows if row.resources.workspace.bounded
    }
    unchecked = sorted(stated - set(FORMULAS))
    assert not unchecked, f"{unchecked} state a bound with no FORMULAS row; {CHECK}"
    orphaned = sorted(set(FORMULAS) - stated)
    assert not orphaned, f"remove {orphaned} from FORMULAS: no stated bound"
