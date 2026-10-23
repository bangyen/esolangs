"""Smallfuck's emitted characters: the plain banded tree, priced node by node."""

from collections.abc import Callable
from functools import cache

#: An exit cell -> the most characters reaching it.
_Paths = dict[int, int]


def _plain(n: int, band: int) -> int:
    """The most characters of the plain tree with result cells banded ``band`` levels.

    A level-k node tests cell 3k, flags at 3k + 1 and writes into its band's
    cell.  Its kinds are the generator's: equal halves (pass to one half), a
    constant lower half (one loop on the bit) and the general split (a flag
    around two loops); a constant half is a flip of the result or nothing,
    a nonconstant one a node below, moved into the parent's band when this
    level owns one.  The pointer entering a child is where the last move
    ended, so a node returns the most characters per exit cell and the
    parent continues from each.  Halves are priced independently, which a
    bottom-level node cannot always realise (n = 4 exhaustive: 319 of 339).
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


def _chars(n: int, _: str) -> int:
    """The shipped text is at most the plain tree at either band width."""
    return min(_plain(n, 3), _plain(n, 5))


FORMULAS = {"scaling": (_chars, False, tuple(range(2, 10)))}
