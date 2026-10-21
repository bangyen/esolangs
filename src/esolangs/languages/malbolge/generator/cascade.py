"""Eleven inputs: the two-level pointer cascade."""

from __future__ import annotations

from collections import Counter
from functools import cache
from typing import Protocol

from esolangs.languages.malbolge.interpreter import _XLAT1, _XLAT2

from .emitter import _Walker
from .isa import (
    _ACTIVE,
    _ALL2,
    _CONSTS,
    _OPS,
    _apply,
    _char_for,
    _first_free,
    _program,
    _render,
)

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
#: ``d`` after the entry ``j`` at ``_ENTRY``: the walked cell its character names.
_START_D = 34 + (7 - _ENTRY) % 94
#: Pointer-region cells (all inside ``34..127`` so a ``j`` can reach them):
#: pair starts hold ``[P0, P1]``, NEXT cells hold all-1.  Every ``h mod 94``
#: must admit a ``T`` of each label among the eight characters the loader
#: accepts at ``h``.  The pairs are the fewest that do so beside the mixer,
#: helper and NEXT cells -- seventeen, and the only cover of that size
#: (``test_pointer_pairs.py``).  The NEXT cells were annealed with them: the
#: fewest covering ``N`` would be the 23 cells ``76..98``, so no rule names
#: this set, which skips 79 and adds 101 and 102.
_PAIRS = (34, 36, 39, 41, 51, 53, 55, 59, 61, 63, 65, 67, 72, 105, 107, 109, 115)
_NEXTS = (*range(76, 79), *range(80, 99), 101, 102)
#: Helper inits: ``{0,1}``-trit cells become all-1 / 0 under ``A = 0`` and
#: ``A = all-1``; 80 and 78 build all-2; 113 seeds the pair chain; 69 and 48
#: give ``A = tau(69) = 48`` before each level's jump (48 -> 69 -> 48 on the
#: second).
_C_HELPERS = {"z1": 40, "z0": 37, "w": 80, "v": 78, "seed": 113, "a1": 69, "a2": 48}


def _jump(walker: _Walker, readout: int, offset: int) -> None:
    """``j`` to the row's table cell ``offset`` past the readout, ``j``, ``i``."""
    walker.op("j", readout)
    for _ in range(offset):
        walker.raw("o")
    walker.raw("j")
    walker.raw("i")


_Cascade = tuple[
    dict[int, str], tuple[int, ...], tuple[tuple[int, ...], ...], dict[int, str]
]


class _OpTarget(Protocol):
    """What :func:`_build_constants` needs of a walker or a planner."""

    d: int

    def op(self, op: str, target: int) -> None:
        """Run ``op`` against ``target``."""

    def raw(self, op: str) -> None:
        """Emit ``op`` at the code pointer."""


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
        address = _first_free(value, 34, 128, modified)
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

    main = _Walker(_ENTRY + 1, _START_D, frozen, ceiling=_ENTRY)
    main.code[_ENTRY] = "j"
    _build_constants(main, helper)
    for a in sorted({*pair_cells, *_NEXTS}):
        main.op("p", a)
        main.op("p", a)
    main.op("*", helper["seed"])
    for a in _PAIRS:
        main.op("p", a)
        main.op("p", a + 1)

    _emit_fold(main, cell)
    return main, cell, helper, frozen


def _ops(target: _OpTarget, cell: list[int], ops: tuple[tuple[int, int], ...]) -> None:
    """Emit ``ops`` (``(kind, index)`` pairs) over ``cell``."""
    for kind, index in ops:
        target.op(_OPS[kind], cell[index])


def _emit_fold(target: _OpTarget, cell: list[int]) -> None:
    """Emit the eleven-bit fold over ``cell``: the cascade, then its post-step."""
    for _ in range(_CASCADE_N):
        target.raw("/")
        _ops(target, cell, _C_SCHEDULE)
    _ops(target, cell, _C_POST[0])


def _decoder_entry(dec: _OpTarget, start: int) -> None:
    """Emit the two ``j`` that carry a decoder at ``start`` to its second pass.

    The first reads the NEXT cell and lands on the decoder itself; the second
    reads the decoder's first cell, already re-enciphered by its own execution.
    """
    dec.raw("j")
    dec.raw("j")
    dec.d = ord(_XLAT2[_char_for("j", start) - 33]) + 1


def _fold(row: int) -> tuple[list[int], int]:
    """Return the cells and ``A`` after the eleven-bit fold of ``row``."""
    cells = [*_C_INITS, *_CONSTS]
    a = 0
    for i in range(_CASCADE_N):
        bit = (row >> (_CASCADE_N - 1 - i)) & 1
        a = _apply(cells, 49 if bit else 48, _C_SCHEDULE)
    return cells, a


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

    # The second decoder: its first ``j`` reads the NEXT cell after the pointer
    # (all-1).
    dec = _Walker(_NEXT + 1, 0, frozen, ceiling=_ENTRY)
    _decoder_entry(dec, _NEXT + 1)
    dec.op("*", helper["w"])
    _ops(dec, cell, _C_POST[1])
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
        cells, a = _fold(row)
        _apply(cells, a, _C_POST[0])
        readouts[0].append(cells[_C_READOUT[0]])
        _apply(cells, _ALL2, _C_POST[1])
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


def _table_char(h: int, label: str, labels: dict[int, str]) -> int:
    """Return the source character at ``h`` that points at a ``label`` cell."""
    for op in _ACTIVE:
        t = 33 + (_XLAT1.index(op) - h) % 94
        if labels.get(t) == label:
            return t
    raise AssertionError(f"no {label} character at {h}")  # pragma: no cover


def _cascade_program(truth_table: str) -> str:
    code, level, tables, labels = _cascade()
    program = _program(code)
    for row, h in enumerate(tables[0]):
        label = truth_table[row] if level[row] == 0 else "N"
        program[h] = _table_char(h, label, labels)
    for row, h in enumerate(tables[1]):
        if level[row] == 1:
            program[h] = _table_char(h, truth_table[row], labels)
    return _render(program)
