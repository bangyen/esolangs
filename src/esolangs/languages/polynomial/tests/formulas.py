"""Polynomial's execution: ``C - d`` at n = 3-9, ``d`` the doubling levels; else ``C``.

Each formula was derived from its generator, not fitted.  An ``exact`` formula
must also be reached by the corpus; ``bound`` only never exceeded.

A level of ``s`` chained blocks runs ``2(s - 1) + 6`` at most (a block that
fires runs 6, one that does not 2), so ``C`` is the sum over the maximal
``s_k``.  A level whose states double has disjoint child pairs, which chain to
span 1 and skip the ``*=``: every row loses 1 there (``d`` levels, 0 to 3 at
n = 6, 7).  A missing state at level k loses 2 and, while the maximum still
doubles, leaves at least ``2a + 1`` missing at the next (``a`` there), so the
first undoubled level costs more than the 1 it saves.  A non-doubling level
chains at most ``s - 1`` of its pairs and keeps a ``*=`` block on some row
(n = 7: 16 parents over 16 children).  Hybrids add 6 a tree level to a smaller
machine: at most 6k + C(n - k), 105 against 131 at n = 7.
"""

from esolangs.languages.polynomial.proof_formulas import states, steps


def doublings(n: int) -> int:
    """Levels k < n whose maximal state count doubles: the loss against ``C``."""
    return sum(states(n, k + 1) == 2 * states(n, k) for k in range(n))


def _execution(n: int, _: str) -> int:
    """The worst row runs ``C - d`` for n <= 9, else at most ``C``."""
    return steps(n) - doublings(n) if n <= 9 else steps(n)


def witness(n: int) -> str:
    """Worst table: 2^(n-2) four-row blocks, every level at its maximal states.

    n <= 6: block m is the binary of m.  Past 6 the blocks are the 16 values in
    pairs ``(j, j + 1 + j // 16)`` mod 16, all distinct, so the pair levels
    keep their maximal states and the 16 four-row tables all occur.  n = 3 is
    four blocks of two rows.
    """
    if n == 3:
        return "".join(f"{block:02b}" for block in range(4))
    blocks = 1 << n - 2
    values = (
        range(blocks)
        if n <= 6
        else [
            value
            for j in range(blocks // 2)
            for value in (j % 16, (j + 1 + j // 16) % 16)
        ]
    )
    return "".join(f"{value:04b}" for value in values)


FORMULAS = {"execution": (_execution, frozenset(range(3, 10)), tuple(range(3, 10)))}
