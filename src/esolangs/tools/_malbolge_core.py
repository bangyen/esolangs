"""Malbolge's shared machinery and the builds through twelve inputs.

Split out of :mod:`esolangs.tools.malbolge`, which had grown past the
repository's file-size cap.  This half is the address arithmetic, the source
skeleton, the pointer cascade and the twelve-input selector; it is the older
and lower half, and it refers to nothing in the module it came from, so the
import runs one way.
"""

from __future__ import annotations

from collections import Counter
from functools import cache
from typing import Protocol

from esolangs.interpreters.other.malbolge import _XLAT1, _XLAT2, _crazy

_WORDS = 3**10
_ROTATE = 3**9

#: The mixer's five cells and the operation schedule applied once per input
#: bit.  Cells are ``(kind, index)`` pairs (0 = ``p``, 1 = ``*``); the schedule
#: makes the readout cell injective over ten bits with pairwise gap at least
#: three, range ``[1083, 59048]``.
_SCHEDULE = (
    (0, 1),
    (0, 2),
    (0, 1),
    (0, 0),
    (0, 1),
    (0, 1),
    (1, 0),
    (0, 4),
    (0, 4),
    (1, 1),
    (1, 4),
    (1, 4),
    (0, 2),
)
#: ``g``-value of the five cells, found by search over source characters and
#: pinned here; the readout cell is cell 0.
_INITS = (52, 90, 83, 70, 92)
#: Operations applied once after the last input bit, spreading the final bit's
#: difference so the ten-bit map keeps pairwise gap at least three.
_POST: tuple[tuple[int, int], ...] = (
    (0, 3),
    (1, 2),
    (1, 2),
    (1, 2),
    (1, 1),
    (0, 2),
    (0, 3),
    (0, 1),
    (1, 1),
    (1, 1),
    (0, 1),
    (1, 0),
    (1, 3),
    (0, 0),
    (1, 0),
    (1, 0),
)
#: The preload tail leaves ``A = 28464`` (low byte ``'0'``) in every row: a
#: cell holding 39 rotated four times, then ``p`` with operands 54 and 60.
_PRELOAD_VALUE = 39
_PRELOAD_ROTATIONS = 4
_PRELOAD_OPERANDS = (54, 60)
#: ``crazy(28464, 101) & 0xFF == ord("1")``, so the answer-1 stub's ``p``
#: (with ``d`` on the value-101 cell) prints ``1`` and the answer-0 stub's
#: ``o`` prints the preloaded ``0``.
_STUB_OPERAND = 101


def _f(address: int) -> int:
    """Return the unique NOP character at ``address``."""
    return 33 + ((35 - address) % 94)


def _g(address: int) -> int:
    """Return a cell's value after the instruction pointer has executed it."""
    return ord(_XLAT2[_f(address) - 33])


def _char_for(op: str, address: int) -> int:
    """Return a source character that deciphers to ``op`` at ``address``."""
    return 33 + ((_XLAT1.index(op) - address) % 94)


#: ``value -> addresses with that ``g`` value``; ``g`` has period 94 and
#: every value in 33..126 occurs, so each value has one or two addresses.
_G_ADDRESSES: dict[int, tuple[int, ...]] = {}
for _address in range(127):
    _G_ADDRESSES.setdefault(_g(_address), ())
    _G_ADDRESSES[_g(_address)] += (_address,)


def _addr_of(value: int, avoid: tuple[int, ...], low: int = 34) -> int:
    """Return an address whose ``g`` value is ``value``, clear of ``avoid``.

    Addresses below ``low`` are skipped because ``value - 1`` has to be a
    source character too, so the address the navigation reaches must exceed
    the value it names.
    """
    candidates = [
        address
        for address in _G_ADDRESSES.get(value, ())
        if low <= address <= 126 and address not in avoid
    ]
    if not candidates:  # pragma: no cover - the first pass always finds one
        candidates = [
            address
            for address in _G_ADDRESSES.get(value, ())
            if address + 94 <= 126 and address + 94 not in avoid
        ]
    if not candidates:  # pragma: no cover - the layout always has one
        raise AssertionError(f"no address for value {value}")
    return candidates[0]


def _step(
    state: tuple[int, ...],
    a: int,
    schedule: tuple[tuple[int, int], ...] = _SCHEDULE,
) -> tuple[int, ...]:
    """Apply ``schedule`` once, returning the new cell values."""
    cells = list(state)
    for kind, index in schedule:
        value = _crazy(a, cells[index]) if kind == 0 else _rot(cells[index])
        a = value
        cells[index] = value
    return tuple(cells)


def _rot(value: int) -> int:
    return value // 3 + (value % 3) * _ROTATE


@cache
def _skeleton(n: int) -> tuple[dict[int, str], tuple[int, ...]]:
    """Return the table-independent source cells and the row address map."""
    starts = _INITS[0]
    x = _addr_of(starts, (), low=35)
    cells = [x]
    for init in _INITS[1:]:
        cells.append(_addr_of(init, (x + 1, *cells)))
    operand_cell = x + 1
    if _g(operand_cell) != _STUB_OPERAND:
        raise AssertionError("stub operand moved")

    vc = _addr_of(_PRELOAD_VALUE, (operand_cell,))
    operands: list[int] = []
    avoid = {operand_cell, vc}
    for value in _PRELOAD_OPERANDS:
        cell = _addr_of(value, tuple(avoid))
        operands.append(cell)
        avoid.add(cell)
    modified = {*cells, vc, operand_cell, *operands}

    # The entry ``j`` reads its own cell, so its address fixes ``X``: the
    # character at ``S`` must be ``X - 2`` and decipher to ``j``.  ``S`` is
    # set past every navigation cell so the initial walk sets their ``g``
    # values before the mixer reads them.
    s = next(
        candidate for candidate in range(222, 800) if candidate % 94 == (42 - x) % 94
    )
    code: dict[int, str] = dict.fromkeys(range(s), "o")
    code[s] = "j"
    c = s + 1
    d = x - 1

    def set_d(target: int) -> None:
        """Emit ``o``s and a ``j`` so that ``d`` becomes ``target``."""
        nonlocal c, d
        if d == target:
            return
        address = _addr_of(target - 1, ())
        while address < d or address in modified or address >= s:
            address += 94
        while d < address:
            code[c] = "o"
            c += 1
            d += 1
        code[c] = "j"
        c += 1
        d = target

    def emit(op: str, cell: int | None = None) -> None:
        nonlocal c, d
        if cell is not None:
            set_d(cell)
        code[c] = op
        c += 1
        d += 1  # every Malbolge instruction increments ``d``

    for i in range(n):
        emit("/")
        schedule = _SCHEDULE if i < n - 1 else _SCHEDULE + _POST
        for kind, index in schedule:
            emit("p" if kind == 0 else "*", cells[index])
        if i < n - 1:
            set_d(x - 1)
    emit("*", vc)
    for _ in range(_PRELOAD_ROTATIONS - 1):
        set_d(vc)
        emit("*", vc)
    for cell in operands:
        set_d(cell)
        emit("p")
    set_d(x)
    code[c] = "i"

    addresses = []
    for row in range(1 << n):
        state: tuple[int, ...] = _INITS
        for i in range(n):
            schedule = _SCHEDULE if i < n - 1 else _SCHEDULE + _POST
            state = _step(state, 49 if (row >> (n - 1 - i)) & 1 else 48, schedule)
        addresses.append(state[0])
    if len(set(addresses)) != len(addresses):
        raise AssertionError("mixer collided")
    return code, tuple(addresses)


# ---------------------------------------------------------------------------
# Eleven inputs: a two-level pointer cascade.
#
# The stub family needs gap-3 injective readouts, and no searched mixer gives
# that at eleven bits (best 1836 of 2048 rows over ~40k full-state-distinct
# schedules; distinct-only readouts top out at 1862).  The cascade drops the
# spacing: a row's table cell at ``X + 1 + k`` holds a source character ``T``
# (one of the eight the loader admits at that address), the decoder does
# ``j``, ``j``, ``i`` -- ``d = T + 1``, then ``c = mem[T + 1]`` -- and the
# pointer cell ``T + 1`` in the walked region names where to go.  A pair
# ``[P0, P1]`` at ``a, a + 1`` serves both answers: ``T = a - 1`` lands on
# ``P0``, whose stub rotates the next cell (``rot(P1) & 0xFF == ord("1")``);
# ``T = a`` lands on ``P1``, whose stub prints ``A`` as preloaded (``48``).
# Rows sharing a level-1 readout point at an all-1 cell instead (``29524``,
# the second decoder), which reads a second mixer cell that separates them.
_CASCADE_N = 11
#: Five data cells and the constant cells 0, all-1 and all-2 as cells 5..7.
_C_INITS = (82, 125, 41, 119, 98)
_C_SCHEDULE: tuple[tuple[int, int], ...] = (
    (0, 0),
    (0, 2),
    (0, 0),
    (0, 1),
    (1, 4),
    (1, 0),
    (0, 1),
    (0, 0),
    (0, 1),
)
#: Post-maps and readout cells per level; level 2 starts from ``A = all-2``.
_C_POST: tuple[tuple[tuple[int, int], ...], ...] = (
    ((0, 3), (0, 0), (0, 1), (0, 0), (0, 1), (0, 1), (0, 1), (0, 0), (0, 1), (0, 0)),
    ((0, 1), (0, 2), (0, 0), (0, 3), (0, 0), (0, 3)),
)
_C_READOUT = (0, 3)
#: ``o`` runs before the table ``j``: level 2's cells would otherwise hit
#: the answer-0 stub's ``v`` (row 1918 at 39405).
_C_OFFSETS = (0, 4)
#: ``P1 = rot(113)``; ``P0 = crazy(P1, all-1)`` swaps its 0/1 trits.  A
#: chained ``p`` over all-1 cells alternates the two, so a pair costs no
#: navigation between its cells.
_P1, _P0 = 39403, 49170
_NEXT = 29524
_ENTRY = 420
#: Pointer-region cells (all inside ``34..127`` so a ``j`` can reach them):
#: pair starts hold ``[P0, P1]``, NEXT cells hold all-1.  Found by annealing
#: the residue cover: every ``h mod 94`` must admit a ``T`` of each label
#: among the eight characters the loader accepts at ``h``.
_PAIRS = (34, 36, 39, 41, 51, 53, 55, 59, 61, 63, 65, 67, 72, 105, 107, 109, 115)
_NEXTS = (
    76,
    77,
    78,
    80,
    81,
    82,
    83,
    84,
    85,
    86,
    87,
    88,
    89,
    90,
    91,
    92,
    93,
    94,
    95,
    96,
    97,
    98,
    101,
    102,
)
#: Helper inits: ``{0,1}``-trit cells become all-1 / 0 under ``A = 0`` and
#: ``A = all-1``; 80 and 78 build all-2; 113 seeds the pair chain; 69 and 48
#: give ``A = tau(69) = 48`` before each level's jump (48 -> 69 -> 48 on the
#: second).
_C_HELPERS = {"z1": 40, "z0": 37, "w": 80, "v": 78, "seed": 113, "a1": 69, "a2": 48}


class _Walker:
    """Code emitter tracking ``d`` through the walked region."""

    def __init__(self, start: int, d: int, modified: frozenset[int]) -> None:
        self.code: dict[int, str] = {}
        self.c = start
        self.d = d
        self.modified = modified

    def raw(self, op: str) -> None:
        self.code[self.c] = op
        self.c += 1
        self.d += 1

    def set_d(self, target: int) -> None:
        """Walk ``d`` up to a cell whose value is ``target - 1``, then ``j``."""
        if self.d == target:
            return
        address = next(
            a
            for a in range(self.d, _ENTRY)
            if _g(a) == target - 1 and a not in self.modified
        )
        while self.d < address:
            self.raw("o")
        self.raw("j")
        self.d = target

    def op(self, op: str, target: int) -> None:
        self.set_d(target)
        self.raw(op)


def _jump(walker: _Walker, readout: int, offset: int) -> None:
    """``j`` to the row's table cell ``offset`` past the readout, ``j``, ``i``."""
    walker.op("j", readout)
    for _ in range(offset):
        walker.raw("o")
    walker.raw("j")
    walker.raw("i")


def _apply(cells: list[int], a: int, ops: tuple[tuple[int, int], ...]) -> int:
    for kind, index in ops:
        value = _crazy(a, cells[index]) if kind == 0 else _rot(cells[index])
        a = cells[index] = value
    return a


_Cascade = tuple[
    dict[int, str], tuple[int, ...], tuple[tuple[int, ...], ...], dict[int, str]
]


class _OpTarget(Protocol):
    """What :func:`_build_constants` needs of a walker or a planner."""

    def op(self, op: str, target: int) -> None:
        """Run ``op`` against ``target``."""


def _build_constants(main: _OpTarget, helper: dict[str, int]) -> None:
    """Run the op chain both builds open with.

    ``A`` starts at 0, so a ``{0,1}``-trit cell becomes all-1 and the next
    one 0; all-2 is two rotated 2-blocks folded into ``op(0, 80)``.  The
    closing ``*`` leaves ``A`` at all-1, from which ``p`` twice maps any
    walked value to all-1.
    """
    main.op("p", helper["z1"])
    main.op("p", helper["z0"])
    main.op("p", helper["w"])
    for _ in range(4):
        main.op("*", helper["v"])
    main.op("p", helper["w"])
    for _ in range(3):
        main.op("*", helper["v"])
    main.op("p", helper["w"])
    main.op("*", helper["z1"])


def _head(
    extra: tuple[int, ...] = (),
) -> tuple[_Walker, list[int], dict[str, int], frozenset[int]]:
    """Build the pointer region and the main code through the eleven-bit fold.

    Returns the main walker (``d`` just past the level-1 post-map), the mixer
    and constant cells, the helper cells and the frozen modified set.  The
    ``extra`` pointer-region cells are reserved as well.
    """
    modified: set[int] = set(extra)

    def place(value: int) -> int:
        address = next(
            a for a in range(34, 128) if _g(a) == value and a not in modified
        )
        modified.add(address)
        return address

    cell = [place(v) for v in _C_INITS]
    helper = {name: place(v) for name, v in _C_HELPERS.items()}
    cell += [helper["z0"], helper["z1"], helper["w"]]
    pair_cells = [a for p in _PAIRS for a in (p, p + 1)]
    for a in (*pair_cells, *_NEXTS):
        if a in modified:
            raise AssertionError(f"pointer cell {a} clashes")
        modified.add(a)
    frozen = frozenset(modified)

    main = _Walker(_ENTRY + 1, 34 + (7 - _ENTRY) % 94, frozen)
    main.code[_ENTRY] = "j"
    _build_constants(main, helper)
    for a in sorted({*pair_cells, *_NEXTS}):
        main.op("p", a)
        main.op("p", a)
    main.op("*", helper["seed"])
    for a in _PAIRS:
        main.op("p", a)
        main.op("p", a + 1)

    for _ in range(_CASCADE_N):
        main.raw("/")
        for kind, index in _C_SCHEDULE:
            main.op("p" if kind == 0 else "*", cell[index])
    for kind, index in _C_POST[0]:
        main.op("p" if kind == 0 else "*", cell[index])
    return main, cell, helper, frozen


def _ops(walker: _Walker, cell: list[int], ops: tuple[tuple[int, int], ...]) -> None:
    for kind, index in ops:
        walker.op("p" if kind == 0 else "*", cell[index])


def _reserved(code: dict[int, str]) -> frozenset[int]:
    return frozenset(code) - frozenset(range(_ENTRY))


def _labels() -> dict[int, str]:
    labels: dict[int, str] = {}
    for a in _PAIRS:
        labels[a - 1] = "1"
        labels[a] = "0"
    nexts = set(_NEXTS)
    for b in _NEXTS:
        if b + 1 in nexts:
            labels[b - 1] = "N"
    return labels


def _stubs() -> dict[int, str]:
    return {_P0 + 1: "*", _P0 + 2: "<", _P0 + 3: "v", _P1 + 1: "<", _P1 + 2: "v"}


@cache
def _cascade() -> _Cascade:
    """Return the table-independent cascade.

    ``(code, level per row, table address per level and row, label per
    pointer character)``.  Raises if a table cell lands on code, a stub or
    another level's cell, or if the second readout fails to separate the
    rows the first left together.
    """
    main, cell, helper, frozen = _head()
    main.op("*", helper["w"])
    main.op("p", helper["a1"])
    _jump(main, cell[_C_READOUT[0]], _C_OFFSETS[0])
    code_end = main.c

    # The second decoder: the first j reads the NEXT cell after the pointer
    # (all-1) and lands on the decoder itself; the second reads the decoder's
    # first cell, already re-enciphered by its own execution.
    dec = _Walker(_NEXT + 1, 0, frozen)
    dec.raw("j")
    dec.raw("j")
    dec.d = ord(_XLAT2[_char_for("j", _NEXT + 1) - 33]) + 1
    dec.op("*", helper["w"])
    for kind, index in _C_POST[1]:
        dec.op("p" if kind == 0 else "*", cell[index])
    for _ in range(2):
        dec.op("*", helper["w"])
        dec.op("p", helper["a2"])
    _jump(dec, cell[_C_READOUT[1]], _C_OFFSETS[1])

    code = dict.fromkeys(range(_ENTRY), "o")
    code.update(main.code)
    code.update(dec.code)
    code.update(_stubs())
    reserved = _reserved(code)

    readouts: list[list[int]] = [[], []]
    for row in range(1 << _CASCADE_N):
        cells = [*_C_INITS, 0, 29524, 59048]
        a = 0
        for i in range(_CASCADE_N):
            bit = (row >> (_CASCADE_N - 1 - i)) & 1
            a = _apply(cells, 49 if bit else 48, _C_SCHEDULE)
        _apply(cells, a, _C_POST[0])
        readouts[0].append(cells[_C_READOUT[0]])
        _apply(cells, 59048, _C_POST[1])
        readouts[1].append(cells[_C_READOUT[1]])
    counts = Counter(readouts[0])
    level = tuple(0 if counts[x] == 1 else 1 for x in readouts[0])
    tables = tuple(
        tuple(x + 1 + _C_OFFSETS[lvl] for x in readouts[lvl]) for lvl in range(2)
    )
    first = set(tables[0])
    second = [h for row, h in enumerate(tables[1]) if level[row] == 1]
    if len(set(second)) != len(second):
        raise AssertionError("second readout collided")
    for lvl, cells_of_level in ((0, tables[0]), (1, second)):
        for h in cells_of_level:
            if h < code_end or h in reserved or (lvl == 1 and h in first):
                raise AssertionError(f"table cell {h} collides at level {lvl + 1}")

    return code, level, tables, _labels()


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
#: Per level, per ``x``: the ops the path runs before the jump (cell index 7
#: is the all-2 cell, so ``(1, 7)`` sets ``A = all-2``), the readout cell and
#: the table offset.  Level 1 reads cell 0 for both halves, negated for
#: ``x = 1``; each level-2 path carries its own searched post-map.
_W_OPS: tuple[tuple[tuple[tuple[int, int], ...], ...], ...] = (
    ((), ((1, 7), (0, 0))),
    (
        ((1, 7), (1, 7), (0, 3), (0, 6), (0, 2), (1, 0), (0, 6)),
        ((1, 7), (1, 0), (1, 1), (0, 2), (1, 2), (0, 0), (0, 3), (1, 0), (1, 3)),
    ),
)
_W_READOUT = ((0, 0), (6, 0))
_W_OFFSETS = ((0, 543), (4, 2))
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


def _wide_build(
    select: tuple[int, ...], select_ops: tuple[tuple[int, int], ...]
) -> _Wide:
    """Return ``(code, level, tables, labels)`` for twelve inputs.

    ``level[x][row]`` and ``tables[level][x][row]`` are indexed by the last
    input ``x`` and the eleven-bit prefix ``row``.  Raises if any path, table
    cell or stub collides.
    """
    b, b2 = select[:2]
    main, cell, helper, frozen = _head(select)
    main.raw("/")
    for kind, which in select_ops:
        main.op("p" if kind == 0 else "*", select[which])
    main.set_d(b)
    main.raw("i")
    code_end = main.c

    values = []
    for x in (0, 1):
        state = [_g(a) for a in select]
        _apply(state, 48 + x, select_ops)
        values.append(tuple(state[:2]))

    dec = _Walker(_NEXT + 1, 0, frozen)
    dec.raw("j")
    dec.raw("j")
    dec.d = ord(_XLAT2[_char_for("j", _NEXT + 1) - 33]) + 1
    dec.set_d(b2)
    dec.raw("i")

    walkers = [dict(main.code), dict(dec.code)]
    for lvl, preload in ((0, ("a1",)), (1, ("a2", "a2"))):
        for x in (0, 1):
            path = _Walker(values[x][lvl] + 1, (b2 if lvl else b) + 1, frozen)
            _ops(path, cell, _W_OPS[lvl][x])
            for name in preload:
                path.op("*", helper["w"])
                path.op("p", helper[name])
            _jump(path, cell[_W_READOUT[lvl][x]], _W_OFFSETS[lvl][x])
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
    reserved = _reserved(code)

    level: list[list[int]] = [[], []]
    tables: list[list[list[int]]] = [[[], []], [[], []]]
    for row in range(1 << _CASCADE_N):
        cells = [*_C_INITS, 0, 29524, 59048]
        a = 0
        for i in range(_CASCADE_N):
            bit = (row >> (_CASCADE_N - 1 - i)) & 1
            a = _apply(cells, 49 if bit else 48, _C_SCHEDULE)
        _apply(cells, a, _C_POST[0])
        for x in (0, 1):
            state = list(cells)
            for lvl in (0, 1):
                _apply(state, 0, _W_OPS[lvl][x])
                readout = state[_W_READOUT[lvl][x]]
                tables[lvl][x].append(readout + 1 + _W_OFFSETS[lvl][x])
    counts = Counter(tables[0][0] + tables[0][1])
    for x in (0, 1):
        level[x] = [0 if counts[h] == 1 else 1 for h in tables[0][x]]
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
        code,
        tuple(tuple(lv) for lv in level),
        tuple(tuple(tuple(t) for t in tl) for tl in tables),
        _labels(),
    )


@cache
def _wide() -> _Wide:
    return _wide_build(_W_SELECT, _W_SELECT_OPS)


def _wide_program(truth_table: str) -> str:
    code, level, tables, labels = _wide()
    program = {a: _char_for(op, a) for a, op in code.items()}
    for x in (0, 1):
        for row, h in enumerate(tables[0][x]):
            answer = truth_table[2 * row + x]
            program[h] = _table_char(h, answer if level[x][row] == 0 else "N", labels)
            if level[x][row]:
                h2 = tables[1][x][row]
                program[h2] = _table_char(h2, answer, labels)
    return "".join(chr(program.get(a, _char_for("o", a))) for a in range(_WORDS))


def _table_char(h: int, label: str, labels: dict[int, str]) -> int:
    """Return the source character at ``h`` that points at a ``label`` cell."""
    for op in "ji*p</vo":
        t = 33 + (_XLAT1.index(op) - h) % 94
        if labels.get(t) == label:
            return t
    raise AssertionError(f"no {label} character at {h}")  # pragma: no cover


def _cascade_program(truth_table: str) -> str:
    code, level, tables, labels = _cascade()
    program = {a: _char_for(op, a) for a, op in code.items()}
    for row, h in enumerate(tables[0]):
        label = truth_table[row] if level[row] == 0 else "N"
        program[h] = _table_char(h, label, labels)
    for row, h in enumerate(tables[1]):
        if level[row] == 1:
            program[h] = _table_char(h, truth_table[row], labels)
    return "".join(chr(program.get(a, _char_for("o", a))) for a in range(_WORDS))
