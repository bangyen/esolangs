"""Malbolge boolean program builder: one source stub per table row.

``malbolge(truth_table)`` reads one ``0``/``1`` line per input and folds them
through a fixed four-cell branch-free mixer into a distinct address ``h(row)``.
The runtime then jumps to a three-cell stub at ``h(row)`` that prints the
row's answer.  The whole 59049-cell source is the program: the mixer inits,
the navigation constants and the stubs are all source characters, so there is
no initializer.

``i``/``j`` let the pointer revisit a cell, but Malbolge re-enciphers every
cell it executes, so a data cell's value after the instruction pointer has
walked over it is ``g(a) = XLAT2[f(a) - 33]``, not the source character;
``f(a) = 33 + ((35 - a) % 94)`` is the unique NOP character at address ``a``.
Every data cell is placed at the address whose ``g`` value is wanted.

That stub construction covers ``n <= 10``: its readout cell is injective
with pairwise gap at least three only through ten bits.  ``n == 11`` uses the
pointer cascade below instead, which needs only *distinct* readouts: each row
owns one table cell holding a source character that points at a pointer cell
in the walked region, and the rows a first readout cannot separate are sent
through a second decoder that reads a second cell.  ``n == 12`` runs the
same fold over the first eleven inputs and lets the twelfth pick which of two
paths reads the readout (see below), and ``n == 13`` keeps that build and
lets the answer stub read the thirteenth.  ``n > 13`` is refused.
"""

from __future__ import annotations

from collections import Counter
from functools import cache

from esolangs.exceptions import GeneratorCapError
from esolangs.interpreters.other.malbolge import _XLAT1, _XLAT2, _crazy
from esolangs.tools.helpers import _validate_truth_table

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
    # Constants: A starts at 0, so a {0,1}-trit cell becomes all-1, the next
    # one 0; all-2 is two rotated 2-blocks folded into op(0, 80).
    main.op("p", helper["z1"])
    main.op("p", helper["z0"])
    main.op("p", helper["w"])
    for _ in range(4):
        main.op("*", helper["v"])
    main.op("p", helper["w"])
    for _ in range(3):
        main.op("*", helper["v"])
    main.op("p", helper["w"])
    # Every pointer cell to all-1: p twice maps any walked value there.
    main.op("*", helper["z1"])
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


# ---------------------------------------------------------------------------
# Thirteen inputs: the twelve-input core, with input thirteen read by the stub.
#
# The core's table cells are kept, one per twelve-bit prefix, and each cell's
# label now names one of four answers as a function of the last input -- 0,
# 1, ``x`` or ``not x`` -- or ``N``.  Five labels need five characters of the
# eight at every residue, which the ``[P0, P1]`` pairs and NEXT runs cannot
# afford; so every label is a single pointer cell, and the decoder takes one
# more hop: ``j`` to the table cell, ``j`` to its pointer cell ``T + 1``, ``j``
# to the *hub* ``V + 1`` the pointer names, ``i`` through the hub.  ``d`` is
# then ``V + 2`` whatever the row, so a stub may read the source characters
# after its hub.  The pointer region holds nothing but labels and the mixer:
# helpers, selectors and seeds move to the walked cells 128..419, reached by
# walking up from a ``j``; navigation is a shortest path over ``o`` and ``j``
# through every cell whose value is known.
#
# A class's pointer cells are filled by one chained ``p`` over all-1 cells
# from a seed ``s`` (a walked cell rotated ``k`` times), so they hold ``s`` and
# ``f(s)`` alternately, ``f`` swapping 0/1 trits; each value owns a hub.  A hub
# holds a source character rotated until it names a free stub; the N hubs hold
# all-1 twice and reach the decoder at 29525 as before.
_THIRTEEN_N = 13
#: Label of the pointer cell ``T + 1`` for ``T`` in ``33..126`` (``n`` is
#: ``not x``, ``-`` a mixer cell or unused).  Every ``h mod 94`` admits a
#: character of each label; found by CP-SAT with the mixer cells blocked.
_T_LABELS = (
    "nxnnnnNx01N1n--0101xNx0101nxx0x01xN-Nn01NxnNnNnNxNnnNxN11N1NNx0101nNx0101"
    "xNx0-01NxN-010NnNn0nx"
)
#: Per label, in chain order: the seed's walked value and its rotations.
_T_SEEDS = {"0": (53, 3), "1": (103, 5), "x": (70, 5), "N": (48, 4), "n": (59, 4)}
#: ``'0'`` prints the preloaded ``A``; ``x`` reads the last input and prints
#: it; ``'1'`` runs ``p`` over the two characters after the hub (a pair with
#: ``crazy(crazy(48, a), b) & 0xFF == ord("1")``); ``not x`` runs ``p`` over two
#: characters and then, through a third that names a pointer cell, over that
#: cell's chain value, which swaps ``'0'`` and ``'1'`` (a flip needs a large
#: operand: over small ones the last input's trit leaves ``A`` odd).
_T_STUBS = {"0": "<v", "x": "/<v", "1": "pp<v", "n": "/ppjp<v"}
#: Hub cells each label reads, from ``V + 1``, including the ``j`` target the
#: builder escapes through after writing the hub.
_T_HUB_CELLS = {"0": 2, "x": 2, "1": 3, "N": 3, "n": 5}
#: Fresh all-1 and all-2 cells just past the pointer region, for the paths.
_T_LOW = (128, 129)
_T_HELPERS = {"z1": 40, "z0": 37, "w": 80, "v": 78, "a1": 69}


def _valid_chars(address: int) -> list[int]:
    return [_char_for(op, address) for op in "ji*p</vo"]


class _Planner:
    """Code emitter that navigates by shortest path over ``o`` and ``j``.

    ``mem`` maps walked addresses to their known values (``None`` once
    written); ``data`` maps store addresses above the code to source
    characters, which a ``j`` from there reads to come back below 128.
    """

    def __init__(
        self, start: int, d: int, mem: dict[int, int | None], data: dict[int, int]
    ) -> None:
        self.code: dict[int, str] = {}
        self.c = start
        self.d = d
        self.mem = mem
        self.data = data

    def raw(self, op: str) -> None:
        self.code[self.c] = op
        self.c += 1
        self.d += 1

    def goto(self, target: int) -> None:
        if self.d >= _ENTRY:
            char = self.data.setdefault(self.d, min(_valid_chars(self.d)))
            self.raw("j")
            self.d = char + 1
        previous: dict[int, tuple[int, str] | None] = {self.d: None}
        frontier = [self.d]
        while target not in previous:
            following = []
            for d in frontier:
                moves = [(d + 1, "o")]
                value = self.mem.get(d)
                if value is not None:
                    moves.append((value + 1, "j"))
                for step, op in moves:
                    if step < _ENTRY and step not in previous:
                        previous[step] = (d, op)
                        following.append(step)
            if not following:  # pragma: no cover - the walked cells cover all
                raise AssertionError(f"cannot reach {target}")
            frontier = following
        path = []
        node = target
        while (link := previous[node]) is not None:
            node, op = link
            path.append(op)
        for op in reversed(path):
            self.code[self.c] = op
            self.c += 1
        self.d = target

    def op(self, op: str, target: int) -> None:
        self.goto(target)
        self.raw(op)
        self.mem[target] = None

    def hub(self, pointer: int, value: int, offset: int = 1) -> None:
        """``j`` through ``pointer`` (holding ``value``) to ``value + offset``."""
        self.goto(pointer)
        self.raw("j")
        self.d = value + 1
        while self.d < value + offset:
            self.raw("o")


_Thirteen = tuple[
    dict[int, str],
    dict[int, int],
    tuple[tuple[int, ...], ...],
    tuple[tuple[tuple[int, ...], ...], ...],
    dict[int, str],
]


def _t_hubs(
    values: dict[int, int], label: dict[int, str], avoid: set[int]
) -> tuple[dict[int, int], dict[int, str], dict[int, int]]:
    """Return hub and data characters, stub code and rotations per hub."""
    hubs = {values[p]: label[p] for p in sorted(values)}
    reserved: set[int] = set()
    for v, lab in sorted(hubs.items()):
        cells = set(range(v + 1, v + 1 + _T_HUB_CELLS[lab]))
        if cells & (avoid | reserved):
            raise AssertionError(f"hub {v} collides")
        reserved |= cells
    data: dict[int, int] = {}
    stubs: dict[int, str] = {}
    turns: dict[int, int] = {}
    for v, lab in sorted(hubs.items()):
        if lab == "N":
            continue
        options: list[dict[int, int]] = [{}]
        if lab == "1":
            options = [
                {v + 2: a, v + 3: b}
                for a in _valid_chars(v + 2)
                for b in _valid_chars(v + 3)
                if _crazy(_crazy(48, a), b) & 0xFF == ord("1")
            ]
        elif lab == "n":
            options = [
                {v + 3: a, v + 4: b, v + 5: q}
                for a in _valid_chars(v + 3)
                for b in _valid_chars(v + 4)
                for q in _valid_chars(v + 5)
                if q + 1 in values
                and all(
                    _crazy(_crazy(_crazy(48 + x, a), b), values[q + 1]) & 0xFF == 49 - x
                    for x in (0, 1)
                )
            ]
        placed = next(
            (
                (option, char, k, s)
                for option in options
                for char in _valid_chars(v + 1)
                for k, s in _rotations(char)
                if s >= _T_FLOOR
                and not set(range(s, s + 1 + len(_T_STUBS[lab])))
                & (avoid | reserved | set(option))
            ),
            None,
        )
        if placed is None:
            raise AssertionError(f"no stub for hub {v}")
        option, char, k, s = placed
        data.update(option)
        data[v + 1] = char
        turns[v] = k
        for i, op in enumerate(_T_STUBS[lab]):
            stubs[s + 1 + i] = op
        reserved |= set(range(s, s + 1 + len(_T_STUBS[lab])))
    return data, stubs, turns


#: Stubs and hubs stay above the main code.
_T_FLOOR = 12000


def _rotations(char: int) -> list[tuple[int, int]]:
    out = []
    value = char
    for k in range(1, 10):
        value = _rot(value)
        out.append((k, value))
    return out


@cache
def _thirteen() -> _Thirteen:
    """Return ``(code, data, level, tables, labels)`` for thirteen inputs.

    ``level`` and ``tables`` are the twelve-input core's, indexed by the
    twelfth input and the eleven-bit prefix.  Raises if any code, stub, hub
    or data cell collides with another or with a table cell.
    """
    _, level, tables, _ = _wide()
    cells_of_tables = set(tables[0][0] + tables[0][1])
    for x in (0, 1):
        cells_of_tables.update(h for row, h in enumerate(tables[1][x]) if level[x][row])

    used = set(_T_LOW)
    helper = {"all1": _T_LOW[0], "all2": _T_LOW[1]}

    def walked(value: int) -> int:
        address = next(
            a for a in range(128, _ENTRY) if _g(a) == value and a not in used
        )
        used.add(address)
        return address

    for name, value in _T_HELPERS.items():
        helper[name] = walked(value)
    select = [walked(_g(a)) for a in _W_SELECT]
    seeds = {lab: walked(value) for lab, (value, _) in _T_SEEDS.items()}
    label = {t + 34: lab for t, lab in enumerate(_T_LABELS) if lab != "-"}
    mix = [
        next(a for a in range(34, 128) if _g(a) == v and a not in label)
        for v in _C_INITS
    ]
    values: dict[int, int] = {}
    for lab, (_, turns) in _T_SEEDS.items():
        a = _g(seeds[lab])
        for _ in range(turns):
            a = _rot(a)
        for p in sorted(label):
            if label[p] == lab:
                a = _crazy(a, 29524)
                values[p] = a
    pointer: dict[int, int] = {}
    for p in sorted(values):
        pointer.setdefault(values[p], p)
    data, stubs, hub_turns = _t_hubs(
        values, label, cells_of_tables | set(range(29520, 29800))
    )

    cell = [*mix, helper["z0"], helper["all1"], helper["all2"]]
    mem: dict[int, int | None] = {a: _g(a) for a in range(_ENTRY)}
    main = _Planner(_ENTRY + 1, 34 + (7 - _ENTRY) % 94, mem, data)
    main.code[_ENTRY] = "j"
    main.op("p", helper["z1"])
    main.op("p", helper["z0"])
    main.op("p", helper["w"])
    for _ in range(4):
        main.op("*", helper["v"])
    main.op("p", helper["w"])
    for _ in range(3):
        main.op("*", helper["v"])
    main.op("p", helper["w"])
    # A = all-1: ``p`` twice sets any cell to all-1; all-2 is then one more
    # ``p`` with ``A = all-2`` (``crazy(all-2, all-1) = all-2``).
    main.op("*", helper["z1"])
    for p in (helper["all1"], helper["all2"], *sorted(label)):
        main.op("p", p)
        main.op("p", p)
    main.op("*", helper["w"])
    main.op("p", helper["all2"])
    for lab, (_, turns) in _T_SEEDS.items():
        for _ in range(turns):
            main.op("*", seeds[lab])
        for p in sorted(label):
            if label[p] == lab:
                main.op("p", p)
    main.op("*", helper["z1"])
    for v in sorted(pointer):
        if label[pointer[v]] == "N":
            main.hub(pointer[v], v)
            main.raw("p")
            main.hub(pointer[v], v)
            main.raw("p")
            main.raw("p")
            main.hub(pointer[v], v, 2)
            main.raw("p")
    for v, turns in sorted(hub_turns.items()):
        for _ in range(turns):
            main.hub(pointer[v], v)
            main.raw("*")
    for _ in range(_CASCADE_N):
        main.raw("/")
        for kind, index in _C_SCHEDULE:
            main.op("p" if kind == 0 else "*", cell[index])
    for kind, index in _C_POST[0]:
        main.op("p" if kind == 0 else "*", cell[index])
    main.raw("/")
    for kind, index in _W_SELECT_OPS:
        main.op("p" if kind == 0 else "*", select[index])
    main.goto(select[0])
    main.raw("i")
    code_end = main.c

    targets = []
    for x in (0, 1):
        state = [_g(a) for a in _W_SELECT]
        _apply(state, 48 + x, _W_SELECT_OPS)
        targets.append(state[:2])
    parts = [main.code]
    for x in (0, 1):
        path = _Planner(targets[x][0] + 1, select[0] + 1, mem, data)
        _t_ops(path, cell, _W_OPS[0][x])
        path.op("*", helper["all2"])
        path.op("p", helper["a1"])
        _t_jump(path, cell[_W_READOUT[0][x]], _W_OFFSETS[0][x])
        parts.append(path.code)
    dec = _Planner(_NEXT + 1, 0, mem, data)
    dec.raw("j")
    dec.raw("j")
    dec.d = ord(_XLAT2[_char_for("j", _NEXT + 1) - 33]) + 1
    dec.goto(select[1])
    dec.raw("i")
    parts.append(dec.code)
    for x in (0, 1):
        path = _Planner(targets[x][1] + 1, select[1] + 1, mem, data)
        _t_ops(path, cell, _W_OPS[1][x])
        # Level 1 left ``a1`` at 48: two rounds give 69 and then 48 again.
        for _ in range(2):
            path.op("*", helper["all2"])
            path.op("p", helper["a1"])
        _t_jump(path, cell[_W_READOUT[1][x]], _W_OFFSETS[1][x])
        parts.append(path.code)

    code = dict.fromkeys(range(_ENTRY), "o")
    for part in (*parts, stubs):
        if set(part) & set(code):
            raise AssertionError(f"code overlaps at {min(set(part) & set(code))}")
        code.update(part)
    if set(data) & set(code):
        raise AssertionError("a data cell overlaps code")
    hits = cells_of_tables & (set(code) | set(data))
    if hits or min(cells_of_tables) <= code_end or code_end >= _T_FLOOR:
        raise AssertionError("a table cell collides with code")
    labels = {p - 1: lab for p, lab in label.items()}
    return code, data, level, tables, labels


def _t_ops(path: _Planner, cell: list[int], ops: tuple[tuple[int, int], ...]) -> None:
    for kind, index in ops:
        path.op("p" if kind == 0 else "*", cell[index])


def _t_jump(path: _Planner, readout: int, offset: int) -> None:
    """``j`` to the table cell, ``j`` to its pointer, ``j`` to the hub, ``i``."""
    path.op("j", readout)
    for _ in range(offset):
        path.raw("o")
    path.raw("j")
    path.raw("j")
    path.raw("i")


def _thirteen_program(truth_table: str) -> str:
    code, data, level, tables, labels = _thirteen()
    program = {a: _char_for(op, a) for a, op in code.items()}
    program.update(data)
    answer = {"00": "0", "11": "1", "01": "x", "10": "n"}
    for x in (0, 1):
        for row, h in enumerate(tables[0][x]):
            i = 4 * row + 2 * x
            label = answer[truth_table[i : i + 2]]
            if level[x][row]:
                program[h] = _table_char(h, "N", labels)
                h2 = tables[1][x][row]
                program[h2] = _table_char(h2, label, labels)
            else:
                program[h] = _table_char(h, label, labels)
    return "".join(chr(program.get(a, _char_for("o", a))) for a in range(_WORDS))


def malbolge(truth_table: str) -> str:
    """Return a Malbolge program computing ``truth_table``.

    ``n`` is recovered from the table.  Through ten inputs the program is one
    source stub per row; eleven inputs use the pointer cascade, twelve the
    cascade with a selector on the last input, thirteen that build with the
    last input read by the answer stub; ``n > 13`` is refused.  Every build is
    the full 59049-cell store.
    """
    n = _validate_truth_table(truth_table)
    if n > _THIRTEEN_N:
        raise GeneratorCapError(
            f"Malbolge builds at most {_THIRTEEN_N} inputs, got {n}: a table "
            "cell's eight characters hold N and the four one-input answers, "
            "and no searched mixer folds twelve bits"
        )
    if n == _THIRTEEN_N:
        return _thirteen_program(truth_table)
    if n == _WIDE_N:
        return _wide_program(truth_table)
    if n == _CASCADE_N:
        return _cascade_program(truth_table)
    code, addresses = _skeleton(n)
    program = dict(code)
    for row, address in enumerate(addresses):
        program[address + 1] = "p" if truth_table[row] == "1" else "o"
        program[address + 2] = "<"
        program[address + 3] = "v"
    return "".join(
        chr(_char_for(program.get(address, "o"), address)) for address in range(_WORDS)
    )
