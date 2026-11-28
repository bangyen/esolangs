"""INTERCAL's size ceiling: every diagram node named, each reference at the widest name.

Naming never shortens the program: a node is inlined only when
``(c - 1) * inline <= statement + c * spelled`` for its ``c`` diagram
readers.  Name the topmost inlined node first; its parents are named, so it
is rendered exactly ``c`` times and naming it adds
``statement + inline + c * spelled - c * inline >= 0``.  A spilled name only
lengthens the named side.  Repeating top-down names every node but the root,
so the emitted program is at most the all-named one, which this prices.
"""

from __future__ import annotations

from math import isqrt

from esolangs.languages.intercal.generator import _ONE, _ZERO, _Expr, _mux

_VARIABLE_MAX = 65535
#: ``DO `` plus `` <- `` plus the newline; PLEASE is priced per statement apart.
_STATEMENT = 3 + 4 + 1
_POLITE = 4


def _nodes(n: int) -> int:
    """Most reduced-diagram nodes: a level k node is a cofactor that reads input k."""
    # 2^2^r - 2^2^(r-1) >= 2^2^(r-1) >= 2^k once 2^(r-1) >= k: skip huge ints.
    return sum(
        1 << k
        if 1 << (n - k - 1) >= k
        else min(1 << k, (1 << (1 << (n - k))) - (1 << (1 << (n - k - 1))))
        for k in range(n)
    )


def _reference(top: int) -> tuple[int, int, int]:
    """Return the widest name spelling, the array count and the array width."""
    if top <= _VARIABLE_MAX:
        return 1 + len(str(top)), 0, 0
    spilled = top - _VARIABLE_MAX
    width = isqrt(spilled - 1) + 1
    arrays = (spilled - 1) // width + 1
    return 7 + len(str(arrays)) + len(str(width)), arrays, width


def _widest_mux(n: int, level: int, ref: int) -> int:
    """Return the longest branching mux at ``level`` over aliases and child kinds."""
    selector = _Expr("input", n - 1 - level)
    child = _Expr("element", text="x" * ref)
    negations = (None, _Expr("input", 2 * n + 1))
    masks = (None, _Expr("element", text=f":{n}"))
    kinds = (_ZERO, _ONE, child)
    return max(
        len(_mux(selector, zero, one, negated, mask).render())
        for negated in negations
        for mask in masks
        for zero in kinds
        for one in kinds
        if zero is not one or zero is child
    )


def size_bound(n: int) -> int:
    """Return the all-named program's most characters at arity ``n``."""
    nodes = _nodes(n)
    top = 2 * n + 1 + nodes
    ref, arrays, width = _reference(top)
    widest = max(_widest_mux(n, level, ref) for level in range(n))
    selector = 1 + len(str(n))
    negation = len(_Expr("not", children=(_Expr("input", n - 1),)).render())
    mask = 4 + 2 * selector + negation
    statements = n + arrays + 2 * n + nodes + 3
    total = sum(_STATEMENT + 1 + len(str(i)) + 2 for i in range(1, n + 1))
    total += arrays * (_STATEMENT + 2 + len(str(arrays)) + len(str(width)))
    total += n * (_STATEMENT + 1 + len(str(2 * n + 2)) + negation)
    total += n * (_STATEMENT + 1 + len(str(n)) + mask)
    total += nodes * (_STATEMENT + ref + widest)
    total += _STATEMENT + 1 + len(str(n + 1)) + widest
    total += 3 + 9 + 1 + len(str(n + 1)) + 1 + 3 + 7
    return total + _POLITE * max(1, (statements + 4) // 5)


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Price the all-named diagram."""
    return {"F": size_bound(n)}
