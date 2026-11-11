"""Smallfuck's emitted characters: the plain banded tree, priced node by node."""

from collections.abc import Callable
from functools import cache

#: An exit cell -> the most characters reaching it.
_Paths = dict[int, int]


def _leaf(n: int, result: int, at: int) -> _Paths:
    """All coefficient subsets, retaining each possible continuation cell."""
    cells = [result, *range(3 * max(1, n - 3) + 2, 3 * n, 3)]
    if len(cells) < 4:
        cells += [3 * k + 1 for k in reversed(range(n))][: 4 - len(cells)]
    paths = {at: 0}
    for cell in cells:
        moved = max(
            cost + abs(exit_cell - cell) + 1 for exit_cell, cost in paths.items()
        )
        paths[cell] = max(paths.get(cell, -1), moved)
    return paths


def _plain(n: int, band: int) -> int:
    """At-most prefix length, preserving every possible continuation cell.

    Equal/constant halves and general splits use the emitter's movements;
    the retired two-input leaf independently prices all coefficient flips.
    Independent halves and coefficients make this an upper bound, not an
    attainable maximum. Band-five movements are bounded per tree edge.
    """

    def owner(level: int) -> bool:
        return level >= 0 and (n - band - level - 1) % band == 0

    def result(level: int) -> int:
        owned = [3 * (k + 1) + 2 for k in range(level) if owner(k)]
        return owned[-1] if owned else 2

    def go(paths: _Paths, then: Callable[[int], _Paths]) -> _Paths:
        out: _Paths = {}
        for cell, cost in paths.items():
            for cell2, cost2 in then(cell).items():
                out[cell2] = max(out.get(cell2, -1), cost + cost2)
        return out

    def step(to: int, text: int) -> Callable[[int], _Paths]:
        return lambda at: {to: abs(at - to) + text}

    def flip(level: int) -> Callable[[int], _Paths]:
        r = result(level)
        return lambda at: {at: 0, r: abs(at - r) + 1}

    def below(level: int) -> Callable[[int], _Paths]:
        def run(at: int) -> _Paths:
            paths = node(level + 1, at)
            if not owner(level):
                return paths
            own, r = 3 * (level + 1) + 2, result(level)
            move = abs(own - r)
            worst = max(cost + abs(cell - own) for cell, cost in paths.items())
            return {own: worst + 2 + 2 * move + 2}

        return run

    def best(*options: _Paths) -> _Paths:
        out: _Paths = {}
        for paths in options:
            for cell, cost in paths.items():
                out[cell] = max(out.get(cell, -1), cost)
        return out

    @cache
    def node(level: int, at: int) -> _Paths:
        if n >= 2 and level == n - 2:
            return _leaf(n, result(level), at)
        bit, flag = 3 * level, 3 * level + 1
        last = level == n - 1
        upper = (
            flip(level) if last else lambda at: best(flip(level)(at), below(level)(at))
        )
        # a constant lower half: [* on the bit around the upper half
        paths = go(go(go(flip(level)(at), step(bit, 2)), upper), step(bit, 1))
        if last:
            return paths
        # the general split: a nonconstant lower half, a flag around two loops
        general = go(step(flag, 1)(at), step(bit, 2))
        for part in (step(flag, 1), upper, step(bit, 1), step(flag, 2)):
            general = go(general, part)
        for part in (below(level), step(flag, 1)):
            general = go(general, part)
        return best(below(level)(at), paths, general)  # equal halves, then these

    return 4 * n + max(node(0, 3 * n).values())


def scaling_terms(n: int, _: str) -> dict[str, int]:
    """Price the coefficient prefix for its most expensive continuation."""
    return {"P": _plain(n, 5)}
