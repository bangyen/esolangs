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

The construction caps at nine inputs: the ten-input branch needs an operand
built at run time (the two comparator targets differ only in di-trit 0, which
no ``p`` chain can lift), and :func:`malbolge` refuses ``n > 9``.
"""

from __future__ import annotations

from functools import cache

from esolangs.exceptions import GeneratorCapError
from esolangs.interpreters.other.malbolge import _XLAT1, _XLAT2, _crazy
from esolangs.tools.helpers import _validate_truth_table

_WORDS = 3**10
_ROTATE = 3**9

#: The mixer's four cells and the operation schedule applied once per input
#: bit.  Cells are ``(kind, index)`` pairs; the schedule runs twice around the
#: four cells and rotates cell 0, which makes cell 0 injective over nine bits
#: with pairwise gap at least three and range ``[9828, 59034]``.
_SCHEDULE = (
    (0, 0),
    (0, 1),
    (0, 2),
    (0, 3),
    (0, 0),
    (0, 1),
    (0, 2),
    (0, 3),
    (1, 0),
)
#: ``g``-value of the four cells, found by search over source characters and
#: pinned here; the readout cell is cell 0.
_INITS = (52, 88, 34, 77)
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
    if not candidates:
        candidates = [
            address
            for address in _G_ADDRESSES.get(value, ())
            if address + 94 <= 126 and address + 94 not in avoid
        ]
    if not candidates:  # pragma: no cover - the layout always has one
        raise AssertionError(f"no address for value {value}")
    return candidates[0]


def _step(state: tuple[int, ...], a: int) -> tuple[int, ...]:
    """Apply the schedule once, returning the new cell values."""
    cells = list(state)
    for kind, index in _SCHEDULE:
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
    y = _addr_of(_INITS[1], (x + 1,))
    z = _addr_of(_INITS[2], (x + 1, y))
    w = _addr_of(_INITS[3], (x + 1, y, z))
    cells = (x, y, z, w)
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
        if op in "*p/<voi":
            d += 1

    for i in range(n):
        emit("/")
        for kind, index in _SCHEDULE:
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
            state = _step(state, 49 if (row >> (n - 1 - i)) & 1 else 48)
        addresses.append(state[0])
    if len(set(addresses)) != len(addresses):
        raise AssertionError("mixer collided")
    return code, tuple(addresses)


def malbolge(truth_table: str) -> str:
    """Return a Malbolge program computing ``truth_table``.

    ``n`` is recovered from the table; ``n > 9`` is refused because the
    ten-input branch needs a run-time operand builder.  The program is the
    full 59049-cell store, one source stub per row.
    """
    n = _validate_truth_table(truth_table)
    if n > 9:
        raise GeneratorCapError(
            f"Malbolge builds at most 9 inputs, got {n}: the ten-input "
            "branch needs a run-time operand builder, which its executed-cell "
            "re-encipherment does not admit"
        )
    code, addresses = _skeleton(n)
    program = dict(code)
    for row, address in enumerate(addresses):
        program[address + 1] = "p" if truth_table[row] == "1" else "o"
        program[address + 2] = "<"
        program[address + 3] = "v"
    return "".join(
        chr(_char_for(program.get(address, "o"), address)) for address in range(_WORDS)
    )
