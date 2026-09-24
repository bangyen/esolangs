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
paths reads the readout (see below), ``n == 13`` keeps that build and lets
the answer stub read the thirteenth.  ``n == 14`` computes four copies'
readouts in the main code, lets inputs twelve and thirteen pick a copy and
the stub read the fourteenth, and resolves shared cells over three levels;
``n > 14`` is refused.
"""

from __future__ import annotations

from collections import Counter
from functools import cache
from itertools import product

from esolangs.exceptions import GeneratorCapError
from esolangs.interpreters.other.malbolge import _XLAT1, _XLAT2, _crazy
from esolangs.tools.helpers import _validate_truth_table

from ._malbolge_core import (  # noqa: F401  (re-exported for the tests)
    _C_INITS,
    _C_POST,
    _C_SCHEDULE,
    _CASCADE_N,
    _ENTRY,
    _NEXT,
    _W_OFFSETS,
    _W_OPS,
    _W_READOUT,
    _W_SELECT,
    _W_SELECT_OPS,
    _WIDE_N,
    _WORDS,
    _apply,
    _build_constants,
    _cascade,
    _cascade_program,
    _char_for,
    _g,
    _rot,
    _skeleton,
    _table_char,
    _wide,
    _wide_program,
)

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
_T_HUB_CELLS: dict[str, int | tuple[int, ...]] = {
    "0": 2,
    "x": 2,
    "1": 3,
    "N": 3,
    "n": 5,
}
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
    values: dict[int, int],
    label: dict[int, str],
    avoid: set[int],
    hub_cells: dict[str, int | tuple[int, ...]] = _T_HUB_CELLS,
) -> tuple[dict[int, int], dict[int, str], dict[int, int]]:
    """Return hub and data characters, stub code and rotations per hub.

    ``hub_cells`` gives, per label, how many cells past a hub are reserved
    or exactly which offsets are.
    """
    hubs = {values[p]: label[p] for p in sorted(values)}
    reserved: set[int] = set()
    for v, lab in sorted(hubs.items()):
        span = hub_cells[lab]
        cells = (
            set(range(v + 1, v + 1 + span))
            if isinstance(span, int)
            else {v + o for o in span}
        )
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
    # all-2 is one more ``p`` with ``A = all-2`` (``crazy(all-2, all-1)``).
    _build_constants(main, helper)
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


_Ops = tuple[tuple[int, int], ...]


def _t_ops(path: _Planner, cell: list[int], ops: _Ops) -> None:
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


# ---------------------------------------------------------------------------
# Fourteen inputs: four copies, three levels, every readout computed up front.
#
# Inputs twelve and thirteen pick one of four *copies* of the eleven-bit
# table, and input fourteen is read by the answer stub as at thirteen.  Each
# copy reads one cell per level; a cell read by two rows holds ``N``, and the
# readers go on to their next level.  The copies differ only in which readout
# cell they jump through, so every readout -- four copies, three levels -- is
# computed by the walked main code before the last two inputs are read: a
# searched run of ops over the mixer and three extra cells, which now and
# then ``p``s ``A`` into a prepared readout cell.  A level-1 or level-2 cell
# is prepared with a top trit of 2, so its readout lies at or above 19683,
# clear of the code; a level-3 readout goes through two cells, 42646 and
# 16402, which leave its two top trits at 0 and 2, in 13122..19682 where no
# other level reads.  The selector then only picks a four-way jump per level:
# the two inputs are folded into one cell, and ``p`` over three prepared cells
# (the second and third through a scratch cell first) turns it into the
# address of each level's *stub*, a few cells that walk ``d`` to the readout
# cell and make the table jump.  ``A`` is set to ``'0'`` once, before the
# first stub: nothing between there and the answer stub touches it.
#
# Levels resolve bottom-up: every row reads its level-1 cell; a row whose
# cell is shared moves on and reads its next one, which may in turn push
# another row on.  Levels one and two resolve all but 80 of the 8,192 copies,
# and the third level's own region gives those room.  The decoder at 29525
# would sit among the level-1 and level-2 cells, so the N hubs hold 13168 and
# it runs from 13169 -- the same residue, so its second pass is unchanged.
# The walked cells the readout ops touch are packed into 163..243 with ten
# trampolines (``p`` with ``A = all-2`` over a walked cell whose ``g`` is at
# least 81 leaves a value that ``j`` lands inside the window); that keeps the
# main code under the level-3 region.
_FOURTEEN_N = 14
#: ``g`` values of the extra state cells 5, 6 and 7.
_F_EXTRA = (57, 75, 119)
#: The readout ops, in three segments run after the eleven-bit post-map:
#: ``(0, i)`` is ``p`` and ``(1, i)`` is ``*`` on state cell ``i``, ``(2, k)``
#: is ``*`` on the constant 0, all-1 or all-2 (setting ``A`` to it), and
#: ``(3, c)`` snapshots ``A`` into copy ``c``'s readout at the segment's level.
_F_SEGMENTS: tuple[tuple[tuple[int, int], ...], ...] = (
    (
        *((3, 0), (1, 6), (0, 2), (0, 1), (0, 6), (0, 6), (1, 7), (2, 1)),
        *((0, 7), (1, 7), (0, 2), (1, 0), (0, 2), (0, 5), (0, 6), (0, 1)),
        *((0, 3), (0, 7), (2, 0), (0, 2), (1, 1), (0, 2), (1, 7), (1, 7)),
        *((1, 7), (1, 6), (0, 2), (1, 5), (0, 7), (0, 2), (1, 0), (0, 5)),
        *((0, 2), (0, 0), (3, 2), (3, 1), (3, 3)),
    ),
    (
        *((3, 0), (0, 7), (3, 2), (3, 1), (1, 6), (0, 3), (1, 6), (2, 2)),
        *((0, 2), (1, 2), (0, 3), (1, 7), (1, 3), (1, 7), (1, 6), (0, 4)),
        *((1, 7), (1, 7), (0, 4), (2, 0), (0, 5), (0, 3), (1, 6), (0, 4)),
        *((1, 5), (0, 4), (1, 4), (0, 1), (1, 3), (0, 1), (1, 1), (1, 0)),
        *((0, 1), (3, 3)),
    ),
    ((0, 5), (3, 0), (1, 2), (3, 1), (3, 3), (1, 2), (1, 2), (3, 2)),
)
#: Per copy, the ``o`` run before each level's table ``j``.
_F_OFFSETS = ((3, 18, 18), (22, 19, 1), (14, 16, 15), (14, 24, 18))
#: Per copy, the level-1 and level-2 readout cells: a walked ``g`` value and
#: the chain that prepares it (``_chain``), each with a top trit of 2.
_F_PREP = (
    ((122, "rot"), (38, "rot K0")),
    ((83, "rot K0"), (92, "rot K0")),
    ((95, "rot K0"), (56, "rot rot rot rot K0")),
    ((59, "rot rot rot rot K0"), (110, "rot K0")),
)
#: The level-3 pair: ``crazy(crazy(A, 42646), 16402)`` has top trits 0 and 2.
#: Each pair of cells is prepared by one chained ``p`` over all-1 cells, from
#: ``A = 45927`` (``g`` 63 rotated four times) and ``A = 32805`` (45, four);
#: spare all-1 cells between them swap ``A`` back.
_F_LEVEL3 = (42646, 16402)
_F_LEVEL3_SEEDS = ((63, 4), (45, 4))
#: The selector: a cell (``g`` 33) takes ``p`` with each input, rotated
#: eight and then six times, and ``p`` over the prepared cells then gives
#: each level's stub address -- the first directly, the others each through
#: a scratch cell (``g`` 33) first.
_F_SELECT = (33, 8, 6)
_F_SELECT_PREP = (
    (34, "rot rot rot"),
    (33, ""),
    (102, "rot rot rot K2"),
    (33, ""),
    (56, "rot rot rot rot rot"),
)
#: The decoder's first cell.  The N hubs hold one less, 13168, which is
#: ``crazy(36066, all-1)``; ``A = 36066`` is ``p`` with ``A = rot(84)`` over a
#: cell prepared from ``g`` 82.
_F_DECODER = 13169
_F_DECODER_SPAN = 150
_F_HUB_A = (84, (82, "rot rot K2"))
#: Label seeds: the ``1`` hubs move to 40095 and 48478, out of the code band.
_F_SEEDS = {**_T_SEEDS, "1": (55, 4)}
#: N hubs hold the decoder address twice, then the handler pointer at
#: ``V + 11`` and the handler's own ``j`` character at ``V + 12``; the second
#: pass only walks ``d`` over the cells between, so those stay free for
#: anything.
_F_HUB_CELLS: dict[str, int | tuple[int, ...]] = {**_T_HUB_CELLS, "N": (1, 2, 11, 12)}
_F_DECODER_NOPS = 8
#: Handlers may sit in the free band between the main code and the tables.
_F_HANDLER_FLOOR = 8600
#: The window the readout ops' cells are packed into, and its trampolines.
_F_WINDOW = (163, 244)
_F_TRAMPOLINES = 10


def _second_pass(op: str, address: int) -> str:
    """Return what a cell holding ``op`` deciphers to once it has run.

    Anything but the seven active instructions is a nop, reported as ``o``.
    """
    char = ord(_XLAT2[_char_for(op, address) - 33])
    decoded = _XLAT1[(char - 33 + address) % 94]
    return decoded if decoded in "ji*p</v" else "o"


_CHAIN_A = {"K0": 0, "K1": 29524, "K2": 59048}


def _chain(value: int, ops: str) -> int:
    """Return ``value`` after a chain of constant ``p`` ops and rotations."""
    for op in ops.split():
        value = _rot(value) if op == "rot" else _crazy(_CHAIN_A[op], value)
    return value


def _emit_chain(path: _Planner, target: int, ops: str, helper: dict[str, int]) -> None:
    """Run ``ops`` on ``target``: ``*`` on a constant cell sets ``A``, then ``p``."""
    for op in ops.split():
        if op == "rot":
            path.op("*", target)
        else:
            path.op("*", helper[{"K0": "z0", "K1": "all1", "K2": "all2"}[op]])
            path.op("p", target)


def _f_select() -> tuple[tuple[int, ...], ...]:
    """Return each level's four selector values, by copy ``2 * x12 + x13``."""
    g, first, second = _F_SELECT
    prep = [_chain(*spec) for spec in _F_SELECT_PREP]
    levels: list[list[int]] = [[], [], []]
    for c in range(4):
        x = _crazy(48 + (c >> 1), g)
        for _ in range(first):
            x = _rot(x)
        x = _crazy(48 + (c & 1), x)
        for _ in range(second):
            x = _rot(x)
        x = _crazy(x, prep[0])
        levels[0].append(x)
        for lvl in (1, 2):
            x = _crazy(_crazy(x, prep[2 * lvl - 1]), prep[2 * lvl])
            levels[lvl].append(x)
    return tuple(tuple(per) for per in levels)


@cache
def _f_tables() -> tuple[
    tuple[tuple[tuple[int, ...], ...], ...], tuple[tuple[int, ...], ...]
]:
    """Return the table cell per level, copy and prefix, and each row's level.

    Rows resolve bottom-up: a row whose cell is read by another row reads its
    next level's cell, which counts against every other reader of that cell
    too.  Raises if a row never resolves.
    """
    rows = 1 << _CASCADE_N
    prep = [[_chain(*spec) for spec in per_copy] for per_copy in _F_PREP]
    tables = [[[0] * rows for _ in range(4)] for _ in range(3)]
    for row in range(rows):
        cells = [*_C_INITS, 0, 29524, 59048]
        a = 0
        for i in range(_CASCADE_N):
            bit = (row >> (_CASCADE_N - 1 - i)) & 1
            a = _apply(cells, 49 if bit else 48, _C_SCHEDULE)
        a = _apply(cells, a, _C_POST[0])
        state = [*cells[:5], *_F_EXTRA]
        for lvl, segment in enumerate(_F_SEGMENTS):
            for kind, index in segment:
                if kind == 0:
                    a = state[index] = _crazy(a, state[index])
                elif kind == 1:
                    a = state[index] = _rot(state[index])
                elif kind == 2:
                    a = (0, 29524, 59048)[index]
                else:
                    if lvl < 2:
                        a = _crazy(a, prep[index][lvl])
                    else:
                        a = _crazy(_crazy(a, _F_LEVEL3[0]), _F_LEVEL3[1])
                    tables[lvl][index][row] = a + 1 + _F_OFFSETS[index][lvl]
    reach = [[1] * rows for _ in range(4)]
    count = Counter(tables[0][c][row] for c in range(4) for row in range(rows))
    changed = True
    while changed:
        changed = False
        for c in range(4):
            for row in range(rows):
                k = reach[c][row]
                if k <= 3 and count[tables[k - 1][c][row]] > 1:
                    reach[c][row] = k + 1
                    changed = True
                    if k < 3:
                        count[tables[k][c][row]] += 1
    if any(k > 3 for per_copy in reach for k in per_copy):
        raise AssertionError("a row never resolves")
    return (
        tuple(tuple(tuple(t) for t in tl) for tl in tables),
        tuple(tuple(k - 1 for k in per_copy) for per_copy in reach),
    )


def _f_handler(
    v: int,
    avoid: set[int],
    target: int,
    mem: dict[int, int | None],
    data: dict[int, int],
) -> tuple[str, dict[int, str]]:
    """Place the level-3 handler an N hub ``v`` reaches on the second pass.

    Returns the chain of constant ``p`` and ``*`` that turns the character
    at ``v + 11`` into the handler's address minus one, and the handler's
    code.  Rotations alone land on block boundaries, where the tables are
    dense, so short chains are tried in order of length.
    """
    chains = [""]
    for length in range(1, 5):
        chains += [
            " ".join(ops) for ops in product(("rot", "K2", "K1", "K0"), repeat=length)
        ]
    for chain in chains:
        for char in _valid_chars(v + 11):
            s = _chain(char, chain)
            if s < _F_HANDLER_FLOOR or s + 60 >= _WORDS:
                continue
            handler = _Planner(s + 1, v + 12, mem, dict(data))
            handler.goto(target)
            handler.raw("i")
            cells = set(range(s, handler.c))
            if cells & avoid:
                continue
            data.update(handler.data)
            data[v + 11] = char
            return chain, handler.code
    raise AssertionError(f"no handler for hub {v}")  # pragma: no cover


class _Window:
    """Walked-cell allocator that packs the busiest cells into the window."""

    def __init__(self) -> None:
        self.used: set[int] = set()

    def take(self, value: int | None = None, *, packed: bool = True) -> int:
        """Allocate a walked cell with ``g == value`` (any, if ``None``)."""
        spans = [range(*_F_WINDOW)] if packed else []
        for span in [*spans, range(128, _ENTRY)]:
            for a in span:
                if (value is None or _g(a) == value) and a not in self.used:
                    self.used.add(a)
                    return a
        raise AssertionError(f"no walked cell with g {value}")  # pragma: no cover


@cache
def _fourteen() -> _Thirteen:
    """Return ``(code, data, level, tables, labels)`` for fourteen inputs.

    ``level[c][row]`` is the level (0-based) at which copy ``c`` of the
    eleven-bit prefix ``row`` resolves and ``tables[level][c][row]`` its
    cells.  Raises if any code, stub, hub, handler or data cell collides with
    another or with a table cell, or if the decoder's second pass breaks.
    """
    tables, level = _f_tables()
    read = Counter(
        tables[lvl][c][row]
        for c in range(4)
        for row, k in enumerate(level[c])
        for lvl in range(k + 1)
    )
    for c in range(4):
        for row, k in enumerate(level[c]):
            if read[tables[k][c][row]] != 1:
                raise AssertionError("a resolved cell is shared")
    cells_of_tables = set(read)
    if max(cells_of_tables) >= _WORDS:
        raise AssertionError("a table cell is past the store")

    window = _Window()
    walked = window.take
    mix = [walked(v) for v in _C_INITS]
    xcell = walked(_F_SELECT[0])
    helper = {"all1": walked(_g(_F_WINDOW[0])), "all2": walked(_g(_F_WINDOW[0] + 1))}
    extras = [walked(v) for v in _F_EXTRA]
    helper["z0"] = walked(_T_HELPERS["z0"])
    helper["a1"] = walked(_T_HELPERS["a1"])
    readout = {
        (c, lvl): walked(g) for c in range(4) for lvl, (g, _) in enumerate(_F_PREP[c])
    }
    select = [walked(g) for g, _ in _F_SELECT_PREP]
    triples = [walked() for _ in range(8)]
    for name in ("z1", "w", "v"):
        helper[name] = walked(_T_HELPERS[name], packed=False)
    seeds = {lab: walked(g, packed=False) for lab, (g, _) in _F_SEEDS.items()}
    spares = [walked(packed=False) for _ in range(9)]
    level3_seeds = [walked(g, packed=False) for g, _ in _F_LEVEL3_SEEDS]
    hub_a = walked(_F_HUB_A[0], packed=False)
    hub_prep = walked(_F_HUB_A[1][0], packed=False)
    label = {t + 34: lab for t, lab in enumerate(_T_LABELS) if lab != "-"}
    singles = [a for a in range(34, 128) if a not in label and _g(a) >= 81]
    singles += [a for a in range(*_F_WINDOW) if a not in window.used and _g(a) >= 81]
    readout.update({(c, 2): triples[4 + c] for c in range(4)})

    values: dict[int, int] = {}
    for lab, (_, turns) in _F_SEEDS.items():
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
    decoder = set(range(_F_DECODER - 1, _F_DECODER + _F_DECODER_SPAN))
    avoid = cells_of_tables | decoder
    data, stubs, hub_turns = _t_hubs(values, label, avoid, _F_HUB_CELLS)

    cell = [*mix, *extras]
    konst = (helper["z0"], helper["all1"], helper["all2"])
    mem: dict[int, int | None] = {a: _g(a) for a in range(_ENTRY)}
    main = _Planner(_ENTRY + 1, 34 + (7 - _ENTRY) % 94, mem, data)
    main.code[_ENTRY] = "j"
    _build_constants(main, helper)
    for p in (helper["all1"], helper["all2"], *sorted(label), *triples, *spares):
        main.op("p", p)
        main.op("p", p)
    main.op("*", helper["w"])
    main.op("p", helper["all2"])
    for a in singles[:_F_TRAMPOLINES]:
        main.op("*", helper["all2"])
        main.op("p", a)
        mem[a] = _crazy(59048, _g(a))
    for lab, (_, turns) in _F_SEEDS.items():
        for _ in range(turns):
            main.op("*", seeds[lab])
        for p in sorted(label):
            if label[p] == lab:
                main.op("p", p)
    for pair, seed, (_, turns) in zip(
        (0, 4), level3_seeds, _F_LEVEL3_SEEDS, strict=True
    ):
        for _ in range(turns):
            main.op("*", seed)
        for k in range(4):
            main.op("p", triples[pair + k])
            if k < 3:
                main.op("p", spares[pair // 4 * 3 + k])
    for (c, lvl), target in sorted(readout.items()):
        if lvl < 2:
            _emit_chain(main, target, _F_PREP[c][lvl][1], helper)
    for target, (_, chain) in zip(select, _F_SELECT_PREP, strict=True):
        _emit_chain(main, target, chain, helper)
    main.op("*", helper["z1"])
    nhubs = [v for v in sorted(pointer) if label[pointer[v]] == "N"]
    for v in nhubs:
        main.hub(pointer[v], v)
        main.raw("p")
        main.hub(pointer[v], v)
        main.raw("p")
        main.raw("p")
        main.hub(pointer[v], v, 2)
        main.raw("p")
    # A = 36066, and each p over an all-1 cell swaps it with 13168.
    _emit_chain(main, hub_prep, _F_HUB_A[1][1], helper)
    main.op("*", hub_a)
    main.op("p", hub_prep)
    flips = iter(spares[6:])
    for i, v in enumerate(nhubs):
        main.hub(pointer[v], v, 2)
        main.raw("p")
        main.op("p", next(flips))
        main.hub(pointer[v], v)
        main.raw("p")
        main.raw("o")  # d passes V + 2, whose value has changed, without a j
        if i + 1 < len(nhubs):
            main.op("p", next(flips))
    handlers: dict[int, str] = {}
    reserved = set(stubs) | set(data) | avoid | set(range(_F_DECODER))
    for v in nhubs:
        chain, code_of = _f_handler(v, reserved | set(handlers), select[4], mem, data)
        reserved |= set(data)
        handlers.update(code_of)
        for op in chain.split():
            if op != "rot":
                main.op("*", helper[{"K0": "z0", "K1": "all1", "K2": "all2"}[op]])
            main.hub(pointer[v], v, 11)
            main.raw("*" if op == "rot" else "p")
    for v, turns in sorted(hub_turns.items()):
        for _ in range(turns):
            main.hub(pointer[v], v)
            main.raw("*")
    for _ in range(_CASCADE_N):
        main.raw("/")
        for kind, index in _C_SCHEDULE:
            main.op("p" if kind == 0 else "*", mix[index])
    for kind, index in _C_POST[0]:
        main.op("p" if kind == 0 else "*", mix[index])
    for lvl, segment in enumerate(_F_SEGMENTS):
        for kind, index in segment:
            if kind < 2:
                main.op("p*"[kind], cell[index])
            elif kind == 2:
                main.op("*", konst[index])
            elif lvl < 2:
                main.op("p", readout[index, lvl])
            else:
                main.op("p", triples[index])
                main.op("p", readout[index, 2])
    for rotations in _F_SELECT[1:]:
        main.raw("/")
        main.op("p", xcell)
        for _ in range(rotations):
            main.op("*", xcell)
    for target in select:
        main.op("p", target)
    main.op("*", helper["all2"])
    main.op("p", helper["a1"])
    main.goto(select[0])
    main.raw("i")
    code_end = main.c

    parts = [main.code, handlers]
    for lvl, per_copy in enumerate(_f_select()):
        entry = select[2 * lvl] + 1
        for c, value in enumerate(per_copy):
            stub = _Planner(value + 1, entry, mem, data)
            _t_jump(stub, readout[c, lvl], _F_OFFSETS[c][lvl])
            parts.append(stub.code)
    dec = _Planner(_F_DECODER, 0, mem, data)
    dec.raw("j")
    dec.raw("j")
    dec.d = ord(_XLAT2[_char_for("j", _F_DECODER) - 33]) + 1
    for _ in range(_F_DECODER_NOPS):
        dec.raw("o")
    dec.goto(select[2])
    dec.raw("i")
    second = [_second_pass(op, a) for a, op in sorted(dec.code.items())]
    if second[: _F_DECODER_NOPS + 2] != ["o"] * (_F_DECODER_NOPS + 1) + ["i"]:
        raise AssertionError("the decoder's second pass changed")
    if not set(dec.code) <= decoder:
        raise AssertionError("the decoder overran its span")
    parts.append(dec.code)

    code = dict.fromkeys(range(_ENTRY), "o")
    for part in (*parts, stubs):
        if set(part) & set(code):
            raise AssertionError(f"code overlaps at {min(set(part) & set(code))}")
        code.update(part)
    if set(data) & set(code):
        raise AssertionError("a data cell overlaps code")
    hits = cells_of_tables & (set(code) | set(data))
    if hits or min(cells_of_tables) <= code_end:
        raise AssertionError("a table cell collides with code")
    labels = {p - 1: lab for p, lab in label.items()}
    return code, data, level, tables, labels


def _fourteen_program(truth_table: str) -> str:
    code, data, level, tables, labels = _fourteen()
    program = {a: _char_for(op, a) for a, op in code.items()}
    program.update(data)
    answer = {"00": "0", "11": "1", "01": "x", "10": "n"}
    for c in range(4):
        for row, k in enumerate(level[c]):
            i = 8 * row + 2 * c
            for lvl in range(k):
                h = tables[lvl][c][row]
                program[h] = _table_char(h, "N", labels)
            h = tables[k][c][row]
            program[h] = _table_char(h, answer[truth_table[i : i + 2]], labels)
    return "".join(chr(program.get(a, _char_for("o", a))) for a in range(_WORDS))


def malbolge(truth_table: str) -> str:
    """Return a Malbolge program computing ``truth_table``.

    ``n`` is recovered from the table.  Through ten inputs the program is one
    source stub per row; eleven inputs use the pointer cascade, twelve the
    cascade with a selector on the last input, thirteen that build with the
    last input read by the answer stub, fourteen four copies of that table
    picked by inputs twelve and thirteen.  ``n > 14`` is refused.  Every
    build is the full 59049-cell store.
    """
    n = _validate_truth_table(truth_table)
    if n > _FOURTEEN_N:
        raise GeneratorCapError(
            f"Malbolge builds at most {_FOURTEEN_N} inputs, got {n}: eight "
            "copies would put 16,384 first reads in the 39,366 cells above "
            "the code, and the decoder's second pass is the last level its "
            "cells afford"
        )
    if n == _FOURTEEN_N:
        return _fourteen_program(truth_table)
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
