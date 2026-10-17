"""The source skeleton the twelve-input mixer builds run in."""

from __future__ import annotations

from functools import cache
from typing import NamedTuple

from .isa import _OPS, _addr_of, _apply, _first_free, _g

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


def _step(
    state: tuple[int, ...],
    a: int,
    schedule: tuple[tuple[int, int], ...] = _SCHEDULE,
) -> tuple[int, ...]:
    """Apply ``schedule`` once, returning the new cell values."""
    cells = list(state)
    _apply(cells, a, schedule)
    return tuple(cells)


class _Layout(NamedTuple):
    """Where the skeleton's walked cells sit."""

    x: int  #: mixer cell 0, the readout and the entry's ``X``
    cells: list[int]  #: the five mixer cells
    value_cell: int  #: the preload value cell
    operands: list[int]  #: the preload's two operand cells
    modified: set[int]  #: every cell the code writes, which ``d`` must not land on


def _layout() -> _Layout:
    """Place the mixer, stub operand and preload cells among the walked ``g`` values."""
    x = _addr_of(_INITS[0], (), low=35)
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
    return _Layout(x, cells, vc, operands, {*cells, vc, operand_cell, *operands})


class _Skeleton:
    """Code emitter tracking ``d`` below the entry ``j`` at ``s``."""

    def __init__(self, layout: _Layout) -> None:
        # The entry ``j`` reads its own cell, so its address fixes ``X``: the
        # character at ``S`` must be ``X - 2`` and decipher to ``j``.  ``S`` is
        # set past every navigation cell so the initial walk sets their ``g``
        # values before the mixer reads them.
        self.s = 222 + (42 - layout.x - 222) % 94
        self.code: dict[int, str] = dict.fromkeys(range(self.s), "o")
        self.code[self.s] = "j"
        self.c = self.s + 1
        self.d = layout.x - 1
        self.modified = layout.modified

    def set_d(self, target: int) -> None:
        """Emit ``o``s and a ``j`` so that ``d`` becomes ``target``."""
        if self.d == target:
            return
        address = _first_free(target - 1, max(self.d, 34), self.s, self.modified)
        while self.d < address:
            self.code[self.c] = "o"
            self.c += 1
            self.d += 1
        self.code[self.c] = "j"
        self.c += 1
        self.d = target

    def emit(self, op: str, cell: int | None = None) -> None:
        if cell is not None:
            self.set_d(cell)
        self.code[self.c] = op
        self.c += 1
        self.d += 1  # every Malbolge instruction increments ``d``


def _skeleton_code(n: int, layout: _Layout) -> dict[int, str]:
    """Return the code: ``n`` mixer rounds, the preload, then the closing ``i``."""
    sk = _Skeleton(layout)
    for i in range(n):
        sk.emit("/")
        schedule = _SCHEDULE if i < n - 1 else _SCHEDULE + _POST
        for kind, index in schedule:
            sk.emit(_OPS[kind], layout.cells[index])
        if i < n - 1:
            sk.set_d(layout.x - 1)
    sk.emit("*", layout.value_cell)
    for _ in range(_PRELOAD_ROTATIONS - 1):
        sk.set_d(layout.value_cell)
        sk.emit("*", layout.value_cell)
    for cell in layout.operands:
        sk.set_d(cell)
        sk.emit("p")
    sk.set_d(layout.x)
    sk.code[sk.c] = "i"
    return sk.code


def _row_addresses(n: int) -> tuple[int, ...]:
    """Return each row's readout cell, in MSB-first row order.

    The fold is a prefix computation, so expanding the levels breadth first
    computes each distinct prefix once: refolding from ``_INITS`` per row
    costs ``n`` steps a row and so ``Theta(T log T)``, while the shared
    levels total ``2**(n+1) - 2`` steps and so ``Theta(T)``.  Branching
    ``48`` before ``49`` leaves the list in the order the caller indexes by.
    """
    states: list[tuple[int, ...]] = [_INITS]
    for i in range(n):
        schedule = _SCHEDULE if i < n - 1 else _SCHEDULE + _POST
        states = [_step(state, a, schedule) for state in states for a in (48, 49)]
    addresses = tuple(state[0] for state in states)
    if len(set(addresses)) != len(addresses):
        raise AssertionError("mixer collided")
    return addresses


@cache
def _skeleton(n: int) -> tuple[dict[int, str], tuple[int, ...]]:
    """Return the table-independent source cells and the row address map."""
    return _skeleton_code(n, _layout()), _row_addresses(n)
