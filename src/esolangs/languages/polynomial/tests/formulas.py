"""Polynomial's execution: ``C - 2`` at n = 3, 4 (every table), else at most ``C``.

Each formula was derived from its generator, not fitted.  An ``exact`` formula
must also be reached by the corpus; ``bound`` only never exceeded.
"""

from esolangs.languages.polynomial.proof_formulas import steps


def _execution(n: int, _: str) -> int:
    """The worst row of n <= 4 runs ``C - 2`` commands; ``C`` bounds the rest."""
    return steps(n) - 2 if n <= 4 else steps(n)


FORMULAS = {"execution": (_execution, frozenset({3, 4}), (3, 4, 5))}
