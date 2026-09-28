"""Malbolge's fifteen- and sixteen-input builds: an address with no collisions.

The builds through fourteen inputs fold the row into a hashed readout and
resolve the rows that share a cell with an ``N`` cascade, and the cascade's
depth is what stops them.  These builds hash nothing.  A readout word has ten
trits, five two-trit *digits*, and three input bits have eight values, so a
digit can hold three bits outright: fifteen address bits fill the word and
every row owns its own cell, with no ``N`` label and no decoder.

A 16-op *gadget* over three fresh walked cells reads three inputs and leaves
them injectively in trit 0 of cells 1 and 2 (``u`` and ``v``); ``crazy`` works
trit by trit, so trits 1..9 of those cells stay constant whatever the input.
The accumulator ``S`` then takes one digit per group: ``p`` over ``S`` with
``A = v`` (bijective in ``v`` because ``S``'s trit 0 is 1), ``*`` rotates ``S``,
``p`` over cell 1 with ``A = S`` (bijective in ``u`` because the rotated trit 0
is 2), ``*`` again.  At trits already holding digits the constants are 2 and
1 -- ``crazy``'s two bijective rows -- so no earlier digit is lost, and the
cells' walked ``g`` values are chosen so that every untouched trit of ``S``
arrives at trit 0 holding exactly the 1 or 2 it needs.  After five groups
``S`` is back in its own alignment: digit ``k`` is input group ``k``.

Each digit misses one of its nine values.  A ``swap12`` on group 4's ``v``
and on group 1's ``u`` and a final ``swap01`` of the whole word make the top
digit miss ``(0, 0)`` and digit 1 miss ``(2, 2)``: every readout lies in
6561..59039, so the code fits below the table and no cell wraps past 59048.
Fifteen inputs run the same build with group 4's first read replaced by the
constant ``'0'``, so their cells are a subset of sixteen's.

The row's cell ``S + 1`` holds a label character as at thirteen inputs, and
the answer stub reads the last input.  Only the labels ``0 1 x n`` exist, and
at 55% occupancy their hubs are placed by seed chains searched to land in
holes; the ``n`` stub's large operand is a dedicated pointer-region cell.
Seventeen inputs would need 65,536 cells, more than the store.
"""

from __future__ import annotations

from functools import cache

from esolangs.interpreters.other.malbolge import _crazy

from ._malbolge_core import (
    _ENTRY,
    _WORDS,
    _build_constants,
    _char_for,
    _g,
    _rot,
    _table_char,
)
from .malbolge import (
    _DIGITS_N,
    _T_HELPERS,
    _T_HUB_CELLS,
    _T_LABELS,
    _T_LOW,
    _chain,
    _emit_chain,
    _Planner,
    _rotations,
    _t_jump,
    _valid_chars,
)

#: The gadget: ``/`` reads an input, ``K`` sets ``A`` to 0 / all-1 / all-2 and
#: a digit names the cell a ``p`` runs over.  Found by breadth-first search
#: over trit 0; cells 1 and 2 end injective in the three inputs.
_GADGET = tuple("/ 0 / 1 K2 0 K2 1 / 2 0 1 0 K1 0 2".split())  # noqa: SIM905
#: Per group, the ``g`` values of the three gadget cells.  Trits 1..3 of each
#: were solved for so that ``S``'s untouched trits arrive right and the
#: digits' constants stay 2 (``v``) and 1 (``u``); trits 4..9 need 0 or 1.
_D_INITS = (
    (63, 64, 34),
    (58, 82, 88),
    (108, 120, 111),
    (46, 39, 60),
    (48, 49, 79),
)
#: The groups whose ``v`` and ``u`` are ``swap12``-ed before they are folded in.
_D_SWAP_V = 4
_D_SWAP_U = 1
#: Label seeds: a walked ``g`` value and the chain that makes it the first
#: pointer value; a label's cells then alternate it and its 0/1 swap.
_D_SEEDS = {
    "0": (109, "rot K2"),
    "1": (116, "rot K2"),
    "x": (118, "rot K2"),
    "n": (80, "rot rot K0 K2"),
}
#: Pointer-region cells the ``n`` stubs ``j`` to, and the chain on each.
_D_OPERANDS = {86: "rot K2", 101: "rot K2"}
#: Stubs, hub characters and the navigation's data cells sit at or above this.
_D_FLOOR = 6000
_D_STUBS = {"0": "<v", "x": "/<v", "1": "pp<v", "n": "/ppjp<v"}
_K = (0, 29524, 59048)


def _swap12(value: int) -> int:
    """``p`` with ``A = 2``: trit 0 swaps 1 and 2, constant 1s and 2s stay."""
    return _crazy(2, value)


@cache
def _readouts(n: int) -> tuple[int, ...]:
    """Return each ``n - 1``-bit prefix's readout, by prefix.

    Built group by group over the distinct states, so each group's work is
    done once per state rather than once per row.  Fifteen's constant read is
    a group-4 top bit held at 0.
    """
    states = [29524]
    for group, init in enumerate(_D_INITS):
        last = n < _DIGITS_N and group == len(_D_INITS) - 1
        following = []
        for s in states:
            for bits in range(4 if last else 8):
                reads = iter(48 + ((bits >> k) & 1) for k in (2, 1, 0))
                cells, a = list(init), 0
                for op in _GADGET:
                    if op == "/":
                        a = next(reads)
                    elif op[0] == "K":
                        a = _K[int(op[1])]
                    else:
                        a = cells[int(op)] = _crazy(a, cells[int(op)])
                u, v = cells[1], cells[2]
                if group == _D_SWAP_V:
                    v = _swap12(v)
                if group == _D_SWAP_U:
                    u = _swap12(u)
                following.append(_rot(_crazy(_rot(_crazy(v, s)), u)))
        states = following
    return tuple(_crazy(s, 29524) for s in states)


def _n_options(v: int, operand: dict[int, int]) -> list[dict[int, int]]:
    """Return data for an ``n`` hub at ``v``: ``p``, ``p``, ``j`` to an operand."""
    return [
        {v + 3: a, v + 4: b, v + 5: q}
        for q in _valid_chars(v + 5)
        if q + 1 in operand
        for a in _valid_chars(v + 3)
        for b in _valid_chars(v + 4)
        if all(
            _crazy(_crazy(_crazy(48 + x, a), b), operand[q + 1]) & 0xFF == 49 - x
            for x in (0, 1)
        )
    ]


def _hubs(
    values: dict[int, int], label: dict[int, str], avoid: set[int]
) -> tuple[dict[int, int], dict[int, str], dict[int, int]]:
    """Return hub and stub data, stub code and rotations per hub.

    As :func:`~esolangs.tools.malbolge._t_hubs`, but the ``n`` stubs flip
    through the prepared operand cells rather than a hub value.
    """
    operand = {f: _chain(_g(f), ops) for f, ops in _D_OPERANDS.items()}
    hubs = {values[p]: label[p] for p in sorted(values)}
    reserved: set[int] = set()
    for v, lab in sorted(hubs.items()):
        cells = set(range(v + 1, v + 1 + _span(lab)))
        if v < _D_FLOOR or cells & (avoid | reserved):
            raise AssertionError(f"hub {v} collides")
        reserved |= cells
    data: dict[int, int] = {}
    stubs: dict[int, str] = {}
    turns: dict[int, int] = {}
    for v, lab in sorted(hubs.items()):
        options: list[dict[int, int]] = [{}]
        if lab == "1":
            options = [
                {v + 2: a, v + 3: b}
                for a in _valid_chars(v + 2)
                for b in _valid_chars(v + 3)
                if _crazy(_crazy(48, a), b) & 0xFF == ord("1")
            ]
        elif lab == "n":
            options = _n_options(v, operand)
        placed = next(
            (
                (option, char, k, s)
                for option in options
                for char in _valid_chars(v + 1)
                for k, s in _rotations(char)
                if _D_FLOOR <= s < _WORDS - 10
                and not set(range(s, s + 1 + len(_D_STUBS[lab])))
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
        for i, op in enumerate(_D_STUBS[lab]):
            stubs[s + 1 + i] = op
        reserved |= set(range(s, s + 1 + len(_D_STUBS[lab])))
    return data, stubs, turns


def _span(lab: str) -> int:
    span = _T_HUB_CELLS[lab]
    if not isinstance(span, int):  # pragma: no cover - only N lists offsets
        raise TypeError(f"label {lab} has no plain span")
    return span


_Digits = tuple[dict[int, str], dict[int, int], tuple[int, ...], dict[int, str]]


@cache
def _digits(n: int) -> _Digits:
    """Return ``(code, data, table cell per prefix, labels)`` for ``n`` inputs.

    Raises if any code, stub, hub or data cell collides with another or with
    a table cell, or if the readouts are not distinct.
    """
    tables = tuple(s + 1 for s in _readouts(n))
    if len(set(tables)) != len(tables) or max(tables) >= _WORDS:
        raise AssertionError("readouts collide or wrap")
    # Sixteen's cells hold fifteen's, so both avoid the same set.
    cells_of_tables = set(_readouts_cells())
    label = {t + 34: lab for t, lab in enumerate(_T_LABELS) if lab in "01xn"}
    used = {*_T_LOW, *label, *_D_OPERANDS}

    def walked(value: int | None = None) -> int:
        address = next(
            a
            for a in range(128, _ENTRY)
            if a not in used and (value is None or _g(a) == value)
        )
        used.add(address)
        return address

    helper = {"all1": _T_LOW[0], "all2": _T_LOW[1]}
    for name, value in _T_HELPERS.items():
        helper[name] = walked(value)
    gadget = [[walked(v) for v in init] for init in _D_INITS]
    s_cell, z_cell = walked(), walked()
    twos = [walked(38) for _ in range(2)]  # ``crazy(all-1, 38) == 2``
    to_48 = [walked(69) for _ in range(2)]  # ``crazy(all-2, 69) == 48``
    seeds = {lab: walked(value) for lab, (value, _) in _D_SEEDS.items()}

    values: dict[int, int] = {}
    for lab, (value, ops) in _D_SEEDS.items():
        a = _chain(value, ops)
        for p in sorted(label):
            if label[p] == lab:
                a = _crazy(a, 29524)
                values[p] = a
    pointer: dict[int, int] = {}
    for p in sorted(values):
        pointer.setdefault(values[p], p)
    data, stubs, hub_turns = _hubs(values, label, cells_of_tables)

    mem: dict[int, int | None] = {a: _g(a) for a in range(_ENTRY)}
    main = _Planner(_ENTRY + 1, 34 + (7 - _ENTRY) % 94, mem, data)
    main.code[_ENTRY] = "j"
    _build_constants(main, helper)
    for p in (helper["all1"], helper["all2"], s_cell, z_cell, *sorted(label)):
        main.op("p", p)
        main.op("p", p)
    main.op("*", helper["w"])
    main.op("p", helper["all2"])
    for lab, (_, ops) in _D_SEEDS.items():
        _emit_chain(main, seeds[lab], ops, helper)
        for p in sorted(label):
            if label[p] == lab:
                main.op("p", p)
    for v, turns in sorted(hub_turns.items()):
        for _ in range(turns):
            main.hub(pointer[v], v)
            main.raw("*")
    for f, ops in sorted(_D_OPERANDS.items()):
        _emit_chain(main, f, ops, helper)

    konst = {"K0": helper["z0"], "K1": helper["all1"], "K2": helper["all2"]}

    def swap12(target: int, two: int) -> None:
        main.op("*", helper["all1"])
        main.op("p", two)
        main.op("p", target)

    s = s_cell
    for group, cell in enumerate(gadget):
        first = True
        for op in _GADGET:
            if op == "/":
                if first and n == _DIGITS_N - 1 and group == len(gadget) - 1:
                    main.op("*", helper["all2"])
                    main.op("p", to_48[1])
                else:
                    main.raw("/")
                first = False
            elif op[0] == "K":
                main.op("*", konst[op])
            else:
                main.op("p", cell[int(op)])
        if group == _D_SWAP_V:
            swap12(cell[2], twos[1])
        main.op("p", s)
        if group == _D_SWAP_U:
            swap12(cell[1], twos[0])
        main.op("*", s)
        main.op("p", cell[1])
        main.op("*", cell[1])
        s = cell[1]
    main.op("p", z_cell)
    main.op("*", helper["all2"])
    main.op("p", to_48[0])
    _t_jump(main, z_cell, 0)
    code_end = main.c

    code = dict.fromkeys(range(_ENTRY), "o")
    for part in (main.code, stubs):
        if set(part) & set(code):
            raise AssertionError(f"code overlaps at {min(set(part) & set(code))}")
        code.update(part)
    if set(data) & set(code):
        raise AssertionError("a data cell overlaps code")
    if cells_of_tables & (set(code) | set(data)) or code_end >= _D_FLOOR:
        raise AssertionError("a table cell collides with code")
    return code, data, tables, {p - 1: lab for p, lab in label.items()}


@cache
def _readouts_cells() -> tuple[int, ...]:
    return tuple(s + 1 for s in _readouts(_DIGITS_N))


def _digits_program(truth_table: str) -> str:
    n = len(truth_table).bit_length() - 1
    code, data, tables, labels = _digits(n)
    program = {a: _char_for(op, a) for a, op in code.items()}
    program.update(data)
    answer = {"00": "0", "11": "1", "01": "x", "10": "n"}
    for row, h in enumerate(tables):
        label = answer[truth_table[2 * row : 2 * row + 2]]
        program[h] = _table_char(h, label, labels)
    return "".join(chr(program.get(a, _char_for("o", a))) for a in range(_WORDS))
