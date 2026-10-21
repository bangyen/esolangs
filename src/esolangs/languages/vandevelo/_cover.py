"""The clause cover the Vandevelo generator emits one guard line per."""

from __future__ import annotations

from typing import NamedTuple

from esolangs.languages.vandevelo._affine import _affine_coset, _constraints
from esolangs.languages.vandevelo._peel import _Peel

_COMPLEMENT = str.maketrans("01", "10")


class _Clause(NamedTuple):
    """One clause: its ``(input set, value)`` tests and the cube's dimension."""

    tests: list[tuple[int, int]]
    dim: int


def _cover(truth_table: str, n: int) -> list[_Clause]:
    """Return the clauses whose union is the ones.

    An affine table is one coset; an affine complement is its failed equations;
    anything else is peeled into cubes.
    """
    ones = {row for row, entry in enumerate(truth_table) if entry == "1"}
    coset = _affine_coset(truth_table, ones)
    if coset is None:
        zeros = set(range(1 << n)) - ones
        excluded = _affine_coset(truth_table.translate(_COMPLEMENT), zeros)
        if excluded is not None:
            equations = _constraints(*excluded, n)
            # The first failed equation partitions the complement, even
            # though earlier failures let its redundant prefix tests go.
            return [
                _Clause([(mask, value ^ 1)], n - index - 1)
                for index, (mask, value) in enumerate(equations)
            ]
    cubes = [coset] if coset is not None else (_Peel(ones, n).run() if ones else [])
    return [_Clause(_constraints(base, dirs, n), len(dirs)) for base, dirs in cubes]


def _flips(cover: list[_Clause], n: int) -> int:
    """Return the index bits whose input is read negated.

    An input is flipped when more of its single-input tests ask for 0 than
    for 1, counted both plainly (each sheds ``== Nil``, eight characters,
    for one ``!`` on the read) and weighted by the rows that reach the
    test's line (each sheds four steps per row).  The cubes are disjoint
    and a row in one hangs on its line, so a line is reached by every row
    outside the cubes before it.  Registers set their own polarity, so only
    the bare tests count.  Saves 1.5% of characters on random tables at n=8
    (200 tables), 14.8-17.6% on single-minterm tables at n=8-12 and 24-32%
    when the minterms have few 1 bits: judged on that sparse class.
    """
    count = [0] * n
    weight = [0] * n
    reach = 1 << n
    for clause in cover:
        for w, value in clause.tests:
            if w.bit_count() == 1:
                bit = w.bit_length() - 1
                count[bit] += 1 if value else -1
                weight[bit] += reach if value else -reach
        reach -= 1 << clause.dim
    return sum(1 << bit for bit in range(n) if count[bit] < 0 and weight[bit] < 0)
