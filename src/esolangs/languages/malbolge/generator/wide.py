"""Twelve inputs: the eleven-bit cascade with a selector for the last bit."""

from __future__ import annotations

from collections import Counter
from functools import cache
from typing import NamedTuple

from .cascade import (
    _C_POST,
    _CASCADE_N,
    _ENTRY,
    _NEXT,
    _decoder_entry,
    _fold,
    _head,
    _jump,
    _labels,
    _ops,
    _reserved,
    _stubs,
    _table_char,
)
from .emitter import _Walker
from .isa import _OPS, _WORDS, _apply, _g, _program, _render

# ---------------------------------------------------------------------------
# Twelve inputs: the eleven-bit cascade with a selector for the last bit.
#
# The fold above never sees input twelve.  After the level-1 post-map a ``/``
# reads it and ``p`` writes it into a selector cell ``B``; one ``*`` moves the
# difference to the top trit, so the two values of ``B`` lie 19683 or 39366
# apart, and ``p`` carries it into a second selector ``B2``.  ``i`` through
# ``B`` then runs one of two level-1 *paths*, stored at ``B + 1`` for each
# value -- code that is never walked, only jumped to.  A path may rewrite the
# readout before the table jump and picks its own table offset, so the two
# halves of the rows land on disjoint table cells without a twelve-bit mixer:
# ``x = 0`` reads cell 0 as the eleven-input build does, ``x = 1`` reads
# ``neg(cell 0)`` (``p`` with ``A = all-2`` negates every trit) 1945 cells on.
# The decoder at 29525 selects through ``B2`` the same way, and each level-2
# path runs its own post-map, searched to separate its half's colliding rows.
_WIDE_N = 12


class _WidePath(NamedTuple):
    """A twelve-input path: ops before the jump, readout cell, table offset."""

    ops: tuple[tuple[int, int], ...]
    readout: int
    offset: int


#: Per level, per ``x``.  Cell index 7 is the all-2 cell, so ``(1, 7)`` sets
#: ``A = all-2``.  Level 1 reads cell 0 for both halves, negated for ``x = 1``;
#: each level-2 path carries its own searched post-map (not derivable by rule).
_W_PATHS: tuple[tuple[_WidePath, _WidePath], tuple[_WidePath, _WidePath]] = (
    (_WidePath((), 0, 0), _WidePath(((1, 7), (0, 0)), 0, 543)),
    (
        _WidePath(((1, 7), (1, 7), (0, 3), (0, 6), (0, 2), (1, 0), (0, 6)), 6, 4),
        _WidePath(
            ((1, 7), (1, 0), (1, 1), (0, 2), (1, 2), (0, 0), (0, 3), (1, 0), (1, 3)),
            0,
            2,
        ),
    ),
)
#: Selector cells, all free pointer-region cells: ``B`` (level 1), ``B2``
#: (level 2) and a scratch cell, and the ops that fold input twelve into
#: them, ``(kind, index)`` run from ``A = '0' + x``.  They were searched so
#: that the four paths land in free runs of the store, 3**9 apart.
_W_SELECT = (38, 44, 58, 57)
_W_SELECT_OPS: tuple[tuple[int, int], ...] = (
    (0, 0),
    (0, 0),
    (1, 0),
    (1, 2),
    (0, 0),
    (1, 0),
    (0, 3),
    (0, 1),
    (1, 1),
    (1, 1),
)

_Wide = tuple[
    dict[int, str],
    tuple[tuple[int, ...], ...],
    tuple[tuple[tuple[int, ...], ...], ...],
    dict[int, str],
]


def _wide_code(
    select: tuple[int, ...], select_ops: tuple[tuple[int, int], ...]
) -> tuple[dict[int, str], int]:
    """Return the code (main, decoder, four paths, stubs) and the main code's end."""
    b, b2 = select[:2]
    main, cell, helper, frozen = _head(select)
    main.raw("/")
    for kind, which in select_ops:
        main.op(_OPS[kind], select[which])
    main.set_d(b)
    main.raw("i")
    code_end = main.c

    values = []
    for x in (0, 1):
        state = [_g(a) for a in select]
        _apply(state, 48 + x, select_ops)
        values.append(tuple(state[:2]))

    dec = _Walker(_NEXT + 1, 0, frozen, ceiling=_ENTRY)
    _decoder_entry(dec, _NEXT + 1)
    dec.set_d(b2)
    dec.raw("i")

    walkers = [dict(main.code), dict(dec.code)]
    for lvl, preload in ((0, ("a1",)), (1, ("a2", "a2"))):
        for x in (0, 1):
            path = _Walker(
                values[x][lvl] + 1, (b2 if lvl else b) + 1, frozen, ceiling=_ENTRY
            )
            spec = _W_PATHS[lvl][x]
            _ops(path, cell, spec.ops)
            for name in preload:
                path.op("*", helper["w"])
                path.op("p", helper[name])
            _jump(path, cell[spec.readout], spec.offset)
            walkers.append(path.code)

    code = dict.fromkeys(range(_ENTRY), "o")
    for part in walkers:
        if set(part) & set(code):
            raise AssertionError(f"paths overlap at {min(set(part) & set(code))}")
        code.update(part)
    stubs = _stubs()
    if set(stubs) & set(code):
        raise AssertionError("a path overlaps a stub")
    code.update(stubs)
    return code, code_end


def _wide_tables(
    code: dict[int, str], code_end: int
) -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[tuple[int, ...], ...], ...]]:
    """Return ``(level, tables)`` per last input ``x``, raising on a collision."""
    reserved = _reserved(code)
    tables: list[list[list[int]]] = [[[], []], [[], []]]
    for row in range(1 << _CASCADE_N):
        cells, a = _fold(row)
        _apply(cells, a, _C_POST[0])
        for x in (0, 1):
            state = list(cells)
            for lvl in (0, 1):
                spec = _W_PATHS[lvl][x]
                _apply(state, 0, spec.ops)
                tables[lvl][x].append(state[spec.readout] + 1 + spec.offset)
    counts = Counter(tables[0][0] + tables[0][1])
    level = [[0 if counts[h] == 1 else 1 for h in tables[0][x]] for x in (0, 1)]
    first = set(counts)
    second = [
        tables[1][x][row]
        for x in (0, 1)
        for row in range(1 << _CASCADE_N)
        if level[x][row]
    ]
    if len(set(second)) != len(second):
        raise AssertionError("second readout collided")
    for lvl, cells_of_level in ((0, first), (1, second)):
        for h in cells_of_level:
            if h < code_end or h >= _WORDS or h in reserved or (lvl and h in first):
                raise AssertionError(f"table cell {h} collides at level {lvl + 1}")
    return (
        tuple(tuple(lv) for lv in level),
        tuple(tuple(tuple(t) for t in tl) for tl in tables),
    )


def _wide_build(
    select: tuple[int, ...], select_ops: tuple[tuple[int, int], ...]
) -> _Wide:
    """Return ``(code, level, tables, labels)`` for twelve inputs.

    ``level[x][row]`` and ``tables[level][x][row]`` are indexed by the last
    input ``x`` and the eleven-bit prefix ``row``.  Raises if any path, table
    cell or stub collides.
    """
    code, code_end = _wide_code(select, select_ops)
    level, tables = _wide_tables(code, code_end)
    return code, level, tables, _labels()


@cache
def _wide() -> _Wide:
    return _wide_build(_W_SELECT, _W_SELECT_OPS)


def _wide_program(truth_table: str) -> str:
    code, level, tables, labels = _wide()
    program = _program(code)
    for x in (0, 1):
        for row, h in enumerate(tables[0][x]):
            answer = truth_table[2 * row + x]
            program[h] = _table_char(h, answer if level[x][row] == 0 else "N", labels)
            if level[x][row]:
                h2 = tables[1][x][row]
                program[h2] = _table_char(h2, answer, labels)
    return _render(program)
