"""Interprogck8's emitted characters: a max-plus recursion over the window layout."""

from __future__ import annotations

from functools import cache

from esolangs.languages.interprogck8.generator import (
    _FREE as FREE,
)
from esolangs.languages.interprogck8.generator import (
    _PERIOD as PERIOD,
)
from esolangs.languages.interprogck8.generator import (
    _RUNG as RUNG,
)
from esolangs.languages.interprogck8.generator import (
    _SLOT as SLOT,
)
from esolangs.languages.interprogck8.generator import (
    _VALUE as VALUE,
)
from esolangs.languages.interprogck8.generator import (
    _arith as arith,
)
from esolangs.languages.interprogck8.generator import (
    _block as block_of,
)
from esolangs.languages.interprogck8.generator import (
    _columns as columns,
)
from esolangs.languages.interprogck8.generator import (
    _read as read,
)

#: Best options kept per layout state (distinct tables); 2 is as good as 13 to n = 12.
_KEEP = 3
#: A window costs its 126 lines (2 characters each) and its closing rung's 11 extra.
_WINDOW = 2 * PERIOD + len(RUNG) - 1

Options = list[tuple[int, str]]


def _extra(lines: list[str]) -> int:
    """Characters past the line's one and its newline."""
    return sum(len(line) - 1 for line in lines)


def _push(options: dict, key: object, value: int, table: str) -> None:
    """Keep the ``_KEEP`` best distinct tables under ``key``."""
    kept: Options = options.setdefault(key, [])
    if all(table != other for _, other in kept):
        kept.append((value, table))
        kept.sort(key=lambda option: -option[0])
        del kept[_KEEP:]


def _place(offset: int, size: int, extra: int) -> tuple[int, bool, int]:
    """Lay ``size`` lines at the cursor: its offset, same window, extras and bump."""
    if 1 <= offset <= FREE - size + 1:
        return offset + size, True, extra
    return 1 + size, False, extra + _WINDOW


@cache
def _clusters(height: int) -> dict[int, Options]:
    """Size to the best (extras, table) clusters of that height, size <= 40."""
    out: dict[int, Options] = {}
    if height == 1:
        for low in (0, 1):
            for high in (0, 1):
                lines = (
                    [read(1), VALUE[low], RUNG] if low == high else [read(low), RUNG]
                )
                _push(out, len(lines), _extra(lines), f"{low}{high}")
        return out
    below = _clusters(height - 1)
    lead = _extra([read(1)])
    for size, options in below.items():
        for extra, table in options:
            if size < FREE:
                _push(out, size + 1, extra + lead, table + table)
    for near, firsts in below.items():
        block = block_of(near)
        for far, seconds in below.items():
            if len(block) + near + far <= FREE:
                for one, first in firsts:
                    for two, second in seconds:
                        if first != second:
                            size = len(block) + near + far
                            _push(out, size, _extra(block) + one + two, first + second)
    return out


def _clustered(height: int, offset: int) -> dict[int, list[tuple[int, bool, int, str]]]:
    """Size to cluster layouts at ``offset``: (offset, same window, value, table)."""
    return {
        size: [(*_place(offset, size, extra), table) for extra, table in options]
        for size, options in _clusters(height).items()
    }


@cache
def _flights(n: int, height: int, offset: int) -> dict[tuple[int, bool], Options]:
    """Layouts of the subtrees of ``height`` that are not clusters, at ``offset``.

    A fold over a 40-line cluster or a big subtree, or a flight: block, near
    child, stop one past the column, far child entered at column + 2.  A flight
    always advances a window.
    """
    out: dict[tuple[int, bool], Options] = {}
    if height == 1:
        return out
    mid, same, value = _place(offset, 2, _extra([read(1), "NnNn"]))
    for end, again, extra, table in _clustered(height - 1, mid).get(FREE, []):
        _push(out, (end, same and again), value + extra, table + table)
    for key, options in _flights(n, height - 1, mid).items():
        for extra, table in options:
            _push(out, (key[0], same and key[1]), value + extra, table + table)
    column = columns(n)[n - height]
    block = block_of(column)
    start, _, value = _place(offset, len(block), _extra(block))
    prefix: list[tuple[int, str | None, int, str]] = []
    nears = [
        (end, again, extra, table, size)
        for size, options in _clustered(height - 1, start).items()
        for end, again, extra, table in options
    ] + [
        (end, again, extra, table, None)
        for (end, again), options in _flights(n, height - 1, start).items()
        for extra, table in options
    ]
    for end, again, extra, table, size in nears:
        stop = _WINDOW if again or end > column + 1 else 0
        prefix.append((value + extra + stop + 3, size, table))
    prefix.sort(key=lambda option: -option[0])
    fars = [
        (end, extra, size, table)
        for size, options in _clustered(height - 1, column + 2).items()
        for end, _, extra, table in options
    ] + [
        (end, extra, None, table)
        for (end, _), options in _flights(n, height - 1, column + 2).items()
        for extra, table in options
    ]
    for end, extra, far, table in fars:
        taken = 0
        for total, near, other in prefix:
            if other == table or (
                near is not None
                and far is not None
                and len(block_of(near)) + near + far <= FREE
            ):
                continue
            _push(out, (end, False), total + extra, other + table)
            taken += 1
            if taken == _KEEP:
                break
    return out


def _best(n: int) -> tuple[int, str]:
    """The dearest layout value and its table: the root entered at line 4."""
    offset = len(SLOT) + 1
    options = [
        (value, table)
        for found in _clustered(n, offset).values()
        for _, _, value, table in found
    ]
    options += [pair for found in _flights(n, n, offset).values() for pair in found]
    return max(options)


def _chars(n: int, _: str) -> int:
    """The most characters of any table: the layout's value plus its fixed parts.

    A table lays out as a deterministic walk of the cursor through 126-line
    windows, so the characters are a sum over the placed pieces and one
    window's cost per window.  A cluster is fixed by its size and extras, a
    flight by its entry offset, so a recursion over (height, entry offset,
    exit offset) keeping the best distinct halves finds the dearest table
    (the root enters at line 4, the tail adds 263 and 2 * 82 + its lines).
    """
    tail = ["@nd", "@nd", "x", *arith(-35), "div"]
    fixed = _WINDOW + 2 * (82 + len(tail)) - 1 + _extra(tail) + 11 + 3
    return _best(n)[0] + fixed


def witness(n: int) -> str:
    """The table reaching :func:`_chars`."""
    return _best(n)[1]


FORMULAS = {"scaling": (_chars, True, tuple(range(3, 11)))}
