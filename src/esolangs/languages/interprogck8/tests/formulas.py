"""Interprogck8: max-plus recursions over the window layout for size and commands."""

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


#: Commands before the first window's code: the line-0 rung and the slot's capture.
_START = 2
#: A read's commands on its 0 arm (the slot's NnNn runs) and, plus its body, its 1 arm.
_NEAR, _FAR = 7, 6
_TAIL = ["@nd", "@nd", "x", *arith(-35), "div"]
#: The walker a leaf leaves, Q (81) or T (84), and the tail commands it runs.
_WALKERS = ((81, len(_TAIL)), (84, len(_TAIL) - 3))
_NONE = -(10**9)
#: Distinct-table options kept per state (the near and far halves must differ).
_SEEN = 2
#: Arities where the witness is measured to reach the relaxed bound.
_EXACT = 10

#: Per walker the dearest (value, table) options, and any tables of the layout.
Seen = tuple[list[list[tuple[int, str]]], list[str]]
#: (exit offset, windows opened, cluster size or None) to its options.
Layouts = dict[tuple[int, int, int | None], Seen]
Paths = dict[int, dict[tuple[int, int], list[str]]]


@cache
def _lead(target: int) -> int:
    """Lines of the block hopping ``target``."""
    return len(block_of(target))


@cache
def _body(target: int) -> int:
    """Commands of the body a 1 arm calls (the block's other nine lines are fixed)."""
    return _lead(target) - 9


def _seat(offset: int, size: int) -> tuple[int, int, int, int]:
    """Lay ``size`` lines: first line, exit offset, windows opened, blanks walked."""
    if 1 <= offset <= FREE - size + 1:
        return offset, offset + size, 0, 0
    return 1, 1 + size, 1, PERIOD + 1 - offset


def _note(layouts: Layouts, key: tuple[int, int, int | None], table: str) -> Seen:
    """The options under ``key``, with ``table`` recorded as one that lays out so."""
    seen = layouts.setdefault(key, ([[], []], []))
    if table not in seen[1] and len(seen[1]) < _SEEN:
        seen[1].append(table)
    return seen


def _floor(layouts: Layouts, key: tuple[int, int, int | None], walker: int) -> int:
    """The value a candidate must beat to enter ``key``'s kept options."""
    seen = layouts.get(key)
    if seen and len(seen[0][walker]) == _SEEN:
        return seen[0][walker][-1][0]
    return _NONE * 2


def _keep(
    layouts: Layouts,
    key: tuple[int, int, int | None],
    walker: int,
    value: int,
    table: str,
) -> None:
    """Keep the ``_SEEN`` dearest distinct tables that end in ``walker``."""
    seen = layouts.get(key)
    if seen and len(seen[0][walker]) == _SEEN and value <= seen[0][walker][-1][0]:
        return
    kept = _note(layouts, key, table)[0][walker]
    if all(table != other for _, other in kept):
        kept.append((value, table))
        kept.sort(key=lambda option: -option[0])
        del kept[_SEEN:]


@cache
def _paths(height: int) -> Paths:
    """Cluster size to {(Q, T): tables}: a row's commands less its leaf rung's line.

    A row's cluster commands are the reads it runs and the leaf; the leaf
    rung's offset is taken off because its walker hops from there.
    """
    out: Paths = {}

    def add(size: int, pair: tuple[int, int], table: str) -> None:
        tables = out.setdefault(size, {}).setdefault(pair, [])
        if table not in tables and len(tables) < _SEEN:
            tables.append(table)

    if height == 1:
        add(2, (1, 1), "01")
        add(2, (1, 1), "10")
        add(3, (1, _NONE), "00")
        add(3, (_NONE, 1), "11")
        return out
    below = _paths(height - 1)
    for size, found in below.items():
        if size < FREE:
            for pair, tables in found.items():
                for table in tables:
                    add(size + 1, pair, table + table)
    for near, firsts in below.items():
        lead = _lead(near)
        for far, seconds in below.items():
            if lead + near + far > FREE:
                continue
            for one, near_tables in firsts.items():
                for two, far_tables in seconds.items():
                    pair = (
                        max(
                            _NEAR - lead + one[0],
                            _FAR + _body(near) - lead - near + two[0],
                        ),
                        max(
                            _NEAR - lead + one[1],
                            _FAR + _body(near) - lead - near + two[1],
                        ),
                    )
                    for first in near_tables:
                        for second in far_tables:
                            if first != second:
                                add(lead + near + far, pair, first + second)
    return out


@cache
def _seated(height: int, offset: int) -> Layouts:
    """The clusters of ``height`` laid at ``offset``, per walker."""
    out: Layouts = {}
    for size, found in _paths(height).items():
        line, end, opened, walked = _seat(offset, size)
        for pair, tables in found.items():
            for table in tables:
                _note(out, (end, opened, size), table)
                for walker, (accumulator, _) in enumerate(_WALKERS):
                    if pair[walker] > _NONE // 2:
                        value = walked - line + pair[walker]
                        value -= (PERIOD - accumulator) * opened
                        _keep(out, (end, opened, size), walker, value, table)
    return out


@cache
def _layouts(n: int, height: int, offset: int) -> Layouts:
    """Clusters and flights of ``height`` entered at ``offset``."""
    return {**_seated(height, offset), **_flown(n, height, offset)}


def _merge(members: list[Seen]) -> Seen:
    """One state standing for ``members``: their dearest distinct options."""
    if len(members) == 1:
        return members[0]
    options: list[list[tuple[int, str]]] = [[], []]
    notes: list[str] = []
    for member in members:
        for walker in range(2):
            options[walker] += member[0][walker]
        notes += [table for table in member[1] if table not in notes]
    for walker in range(2):
        options[walker].sort(key=lambda option: -option[0])
        kept: list[tuple[int, str]] = []
        for value, table in options[walker]:
            if all(table != other for _, other in kept):
                kept.append((value, table))
        options[walker] = kept[:_SEEN]
    return options, notes[:_SEEN]


@cache
def _flown(n: int, height: int, offset: int) -> Layouts:
    """The flights of ``height`` at ``offset``: value = commands less the leaf's offset.

    A row's value is its commands to the leaf rung, less (walker's window
    length) * (the leaf's window) and the rung's offset; the walker then
    adds its window length for every window to the last.  A near child
    laid before the stop sets how many windows the far arm's flight crosses.
    """
    out: Layouts = {}
    if height == 1:
        return out
    line, there, opened, walked = _seat(offset, 2)
    for (end, more, size), seen in _layouts(n, height - 1, there).items():
        if size in (None, FREE):
            for walker, (accumulator, _) in enumerate(_WALKERS):
                for value, table in seen[0][walker]:
                    total = walked + 2 - (PERIOD - accumulator) * opened + value
                    _keep(out, (end, opened + more, None), walker, total, table * 2)
    column = columns(n)[n - height]
    lead = len(block_of(column))
    line, there, opened, walked = _seat(offset, lead)
    rung = PERIOD * opened + line + lead - 1
    fars = _layouts(n, height - 1, column + 2)
    nears: dict[tuple[int, int | None], list[Seen]] = {}
    for (end, more, near), seen in _layouts(n, height - 1, there).items():
        first = max(PERIOD * (opened + more) + end, PERIOD * (opened + 1))
        stop = first + (column + 1 - first) % PERIOD
        windows = stop // PERIOD
        nears.setdefault((windows, near), []).append(seen)
    for (windows, near), members in nears.items():
        seen = _merge(members)
        flight = PERIOD * (opened + 1) - (rung + 1 + column) + 1
        flight += (windows - opened - 1) * (PERIOD - column) + 1
        for (exit_, extra, far), seen_far in fars.items():
            if (
                near is not None
                and far is not None
                and _lead(near) + near + far <= FREE
            ):
                continue
            key = (exit_, windows + extra, None)
            for walker, (accumulator, _) in enumerate(_WALKERS):
                for value, table in seen[0][walker]:
                    total = walked + _NEAR - (PERIOD - accumulator) * opened + value
                    if total <= _floor(out, key, walker):
                        continue
                    for other in seen_far[1]:
                        if table != other:
                            _keep(out, key, walker, total, table + other)
                            break
                for value, table in seen_far[0][walker]:
                    total = walked + _FAR + _body(column) + flight
                    total += value - (PERIOD - accumulator) * windows
                    if total <= _floor(out, key, walker):
                        continue
                    for other in seen[1]:
                        if table != other:
                            _keep(out, key, walker, total, other + table)
                            break
    return out


@cache
def _worst(n: int) -> tuple[int, str]:
    """The most commands of any table and row, and that table."""
    best = (0, "")
    for (_, opened, _), seen in _layouts(n, n, len(SLOT) + 1).items():
        for walker, (accumulator, tail) in enumerate(_WALKERS):
            for value, table in seen[0][walker]:
                total = _START + value + (PERIOD - accumulator) * (opened + 1) + tail
                best = max(best, (total, table))
    return best


#: Per walker the dearest value of a layout state (tables dropped).
Bound = dict[tuple[int, int, int | None], list[int]]


@cache
def _pairs(height: int) -> dict[int, set[tuple[int, int]]]:
    """Cluster size to its (Q, T) row-command pairs; halves may coincide."""
    if height == 1:
        return {2: {(1, 1)}, 3: {(1, _NONE), (_NONE, 1)}}
    below = _pairs(height - 1)
    out: dict[int, set[tuple[int, int]]] = {}
    for size, found in below.items():
        if size < FREE:
            out.setdefault(size + 1, set()).update(found)
    for near, firsts in below.items():
        lead = _lead(near)
        for far, seconds in below.items():
            if lead + near + far > FREE:
                continue
            for one in firsts:
                for two in seconds:
                    out.setdefault(lead + near + far, set()).add(
                        tuple(
                            max(
                                _NEAR - lead + one[w],
                                _FAR + _body(near) - lead - near + two[w],
                            )
                            for w in range(2)
                        )
                    )
    return out


def _raise(
    bound: Bound, key: tuple[int, int, int | None], walker: int, value: int
) -> None:
    """Keep the dearest ``value`` of ``walker`` under ``key``."""
    best = bound.setdefault(key, [_NONE, _NONE])
    best[walker] = max(best[walker], value)


@cache
def _bounds(n: int, height: int, offset: int) -> Bound:
    """:func:`_layouts` with every table kept: the relaxation that bounds it above."""
    out: Bound = {}
    for size, found in _pairs(height).items():
        line, end, opened, walked = _seat(offset, size)
        for pair in found:
            for walker, (accumulator, _) in enumerate(_WALKERS):
                if pair[walker] > _NONE // 2:
                    value = walked - line + pair[walker]
                    _raise(
                        out,
                        (end, opened, size),
                        walker,
                        value - (PERIOD - accumulator) * opened,
                    )
    if height == 1:
        return out
    line, there, opened, walked = _seat(offset, 2)
    for (end, more, size), best in _bounds(n, height - 1, there).items():
        if size in (None, FREE):
            for walker, (accumulator, _) in enumerate(_WALKERS):
                if best[walker] > _NONE // 2:
                    total = walked + 2 - (PERIOD - accumulator) * opened + best[walker]
                    _raise(out, (end, opened + more, None), walker, total)
    column = columns(n)[n - height]
    lead = len(block_of(column))
    line, there, opened, walked = _seat(offset, lead)
    rung = PERIOD * opened + line + lead - 1
    fars = _bounds(n, height - 1, column + 2)
    nears: dict[tuple[int, int | None], list[int]] = {}
    for (end, more, near), seen in _bounds(n, height - 1, there).items():
        first = max(PERIOD * (opened + more) + end, PERIOD * (opened + 1))
        windows = (first + (column + 1 - first) % PERIOD) // PERIOD
        best = nears.setdefault((windows, near), [_NONE, _NONE])
        best[:] = [max(old, new) for old, new in zip(best, seen, strict=True)]
    for (windows, near), seen in nears.items():
        flight = PERIOD * (opened + 1) - (rung + 1 + column) + 1
        flight += (windows - opened - 1) * (PERIOD - column) + 1
        for (exit_, extra, far), seen_far in fars.items():
            if (
                near is not None
                and far is not None
                and _lead(near) + near + far <= FREE
            ):
                continue
            key = (exit_, windows + extra, None)
            for walker, (accumulator, _) in enumerate(_WALKERS):
                if seen[walker] > _NONE // 2:
                    total = (
                        walked + _NEAR - (PERIOD - accumulator) * opened + seen[walker]
                    )
                    _raise(out, key, walker, total)
                if seen_far[walker] > _NONE // 2:
                    total = walked + _FAR + _body(column) + flight + seen_far[walker]
                    _raise(out, key, walker, total - (PERIOD - accumulator) * windows)
    return out


@cache
def _bound(n: int) -> int:
    """The most commands of any table and row, halves allowed to coincide."""
    best = 0
    for (_, opened, _), seen in _bounds(n, n, len(SLOT) + 1).items():
        for walker, (accumulator, tail) in enumerate(_WALKERS):
            if seen[walker] > _NONE // 2:
                best = max(
                    best,
                    _START
                    + seen[walker]
                    + (PERIOD - accumulator) * (opened + 1)
                    + tail,
                )
    return best


def _steps(n: int, _: str) -> int:
    """The relaxed recursion's worst, a proved upper bound.

    Reached over all rows to n = ``_EXACT``, and at 11 by one named row.

    The shipped ``_worst`` keeps ``_SEEN`` distinct tables a state and is a
    witnessed lower bound; the two agree to 11.
    """
    return _bound(n)


def steps_witness(n: int) -> str:
    """The table reaching :func:`_steps`."""
    return _worst(n)[1]


FORMULAS = {
    "scaling": (_chars, True, tuple(range(3, 11))),
    "execution": (_steps, True, tuple(range(3, _EXACT + 1))),
}
