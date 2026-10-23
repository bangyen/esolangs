"""Polynomial's execution: ``C - 2, 2, 3, 4`` at n = 3-6, else ``C``.

Each formula was derived from its generator, not fitted.  An ``exact`` formula
must also be reached by the corpus; ``bound`` only never exceeded.

The root's span is always 1, so it runs 2 of its 3 commands; a level whose
states double has disjoint child pairs, which chain to span 1 and skip the
``*=``: n = 6 has doublings at levels 0-3.  A missing state costs 2 and forces
2 more below it, so none recovers a loss.  Hybrids add 6 a tree level to a
smaller machine: at most 69 against 95 at n = 6.
"""

from esolangs.languages.polynomial.proof_formulas import steps


def _execution(n: int, _: str) -> int:
    """The worst row runs ``C - 2`` at n = 3, 4, ``C - 3`` at 5, ``C - 4`` at 6."""
    if n <= 4:
        return steps(n) - 2
    return steps(n) - (n - 2) if n <= 6 else steps(n)


FORMULAS = {"execution": (_execution, frozenset({3, 4, 5, 6}), (3, 4, 5, 6))}
