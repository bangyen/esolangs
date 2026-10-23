"""Polynomial's execution: ``C - 2`` at n = 3, 4, ``C - 3`` at n = 5, else ``C``.

Each formula was derived from its generator, not fitted.  An ``exact`` formula
must also be reached by the corpus; ``bound`` only never exceeded.

The root's span is always 1, so it runs 2 of its 3 commands; a level whose
states double (n = 5: levels 1 and 2) has disjoint child pairs, which chain to
span 1 and skip the ``*=``.  A missing state costs 2, so none recovers a loss.
"""

from esolangs.languages.polynomial.proof_formulas import steps


def _execution(n: int, _: str) -> int:
    """The worst row runs ``C - 2`` commands at n <= 4, ``C - 3`` at n = 5."""
    if n <= 4:
        return steps(n) - 2
    return steps(n) - 3 if n == 5 else steps(n)


FORMULAS = {"execution": (_execution, frozenset({3, 4, 5}), (3, 4, 5))}
