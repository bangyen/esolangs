"""Fourteen-input tier: readout segments, allocation and placement over four copies."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import cache
from itertools import product
from typing import Literal, NamedTuple

from esolangs.languages.malbolge.interpreter import _XLAT1, _XLAT2, _crazy

from .cascade import (
    _C_INITS,
    _C_POST,
    _CASCADE_N,
    _ENTRY,
    _build_constants,
    _decoder_entry,
    _emit_fold,
    _fold,
)
from .core import (
    _K_CELL,
    _T_HELPERS,
    _T_HUB_CELLS,
    _T_LABELS,
    _T_SEEDS,
    _chain,
    _emit_chain,
    _main_planner,
    _merge_code,
    _n_hub_pass,
    _Planner,
    _pointers,
    _prime,
    _seed_label_chains,
    _t_jump,
    _turn_hubs,
    _valid_chars,
)
from .isa import (
    _ALL2,
    _CONSTS,
    _WORDS,
    _apply,
    _char_for,
    _g,
    _rot,
)
from .thirteen import (
    _Layout,
    _seed_values,
    _t_place,
)

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
# and the third level's own region gives those room.  The decoder at
# ``_T_DECODER`` (29525) would sit among the level-1 and level-2 cells, so
# the N hubs hold 13168 and
# it runs from 13169 -- the same residue, so its second pass is unchanged.
# The walked cells the readout ops touch are packed into 163..243 with ten
# trampolines (``p`` with ``A = all-2`` over a walked cell whose ``g`` is at
# least 81 leaves a value that ``j`` lands inside the window); that keeps the
# main code under the level-3 region.
_FOURTEEN_N = 14
#: ``g`` values of the extra state cells 5, 6 and 7.
_F_EXTRA = (57, 75, 119)


# ---------------------------------------------------------------------------
# Readout op language: one typed op per step of the searched readout search.
_Kind = Literal["mix", "rot", "const", "snap"]


class _SegmentOp(NamedTuple):
    """One readout op.

    ``mix``: ``p`` with mixer cell ``arg``; ``rot``: ``*`` on it; ``const``:
    ``*`` on ``_CONSTS[arg]``, setting ``A``; ``snap``: snapshot ``A`` into
    copy ``arg``'s readout at the segment's level.
    """

    kind: _Kind
    arg: int


_KINDS: dict[str, _Kind] = {"m": "mix", "r": "rot", "c": "const", "s": "snap"}


def _segment(spec: str) -> tuple[_SegmentOp, ...]:
    """Parse ``"s0 r6 m2"`` into ops: a kind letter, then ``arg``."""
    return tuple(_SegmentOp(_KINDS[w[0]], int(w[1:])) for w in spec.split())


#: The readout ops, in three segments run after the eleven-bit post-map.
_F_SEGMENTS = tuple(
    map(
        _segment,
        (
            "s0 r6 m2 m1 m6 m6 r7 c1 m7 r7 m2 r0 m2 m5 m6 m1 m3 m7 c0 m2 r1 m2 "
            "r7 r7 r7 r6 m2 r5 m7 m2 r0 m5 m2 m0 s2 s1 s3",
            "s0 m7 s2 s1 r6 m3 r6 c2 m2 r2 m3 r7 r3 r7 r6 m4 r7 r7 m4 c0 m5 m3 "
            "r6 m4 r5 m4 r4 m1 r3 m1 r1 r0 m1 s3",
            "m5 s0 r2 s1 s3 r2 r2 s2",
        ),
    )
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
#: The level-3 readout pair: ``crazy(crazy(A, _L3_CELL_A), _L3_CELL_B)`` has top
#: trits 0 and 2.  Each pair of cells is prepared by one chained ``p`` over
#: all-1 cells, from ``A = 45927`` (``g`` 63 rotated four times) and
#: ``A = 32805`` (45, four); spare all-1 cells between them swap ``A`` back.
_L3_CELL_A = 42646
_L3_CELL_B = 16402
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
        cells, a = _fold(row)
        a = _apply(cells, a, _C_POST[0])
        state = [*cells[:5], *_F_EXTRA]
        for lvl, segment in enumerate(_F_SEGMENTS):
            for op in segment:
                if op.kind == "mix":
                    a = state[op.arg] = _crazy(a, state[op.arg])
                elif op.kind == "rot":
                    a = state[op.arg] = _rot(state[op.arg])
                elif op.kind == "const":
                    a = _CONSTS[op.arg]
                elif op.kind == "snap":
                    if lvl < 2:
                        a = _crazy(a, prep[op.arg][lvl])
                    else:
                        a = _crazy(_crazy(a, _L3_CELL_A), _L3_CELL_B)
                    tables[lvl][op.arg][row] = a + 1 + _F_OFFSETS[op.arg][lvl]
                else:
                    raise ValueError(op.kind)
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


@dataclass
class _FAllocation:
    """Walked cells and label tables for the fourteen-input build.

    Allocation order is load-bearing: ``_Window.take`` hands out the first
    free cell with the wanted ``g`` value, so reordering these allocations
    would move every address that follows.
    """

    window: _Window
    mix: list[int]
    xcell: int
    helper: dict[str, int]
    extras: list[int]
    readout: dict[tuple[int, int], int]
    select: list[int]
    triples: list[int]
    spares: list[int]
    singles: list[int]
    level3_seeds: list[int]
    hub_a: int
    hub_prep: int
    seeds: dict[str, int]
    label: dict[int, str]


@dataclass
class _FPlacement:
    """Hub, stub and data placement for the fourteen-input build."""

    values: dict[int, int]
    pointer: dict[int, int]
    decoder: set[int]
    avoid: set[int]
    data: dict[int, int]
    stubs: dict[int, str]
    hub_turns: dict[int, int]


@dataclass
class _FMain:
    """The walked main code of the fourteen-input build."""

    main: _Planner
    mem: dict[int, int | None]
    handlers: dict[int, str]
    code_end: int


_FTableCells = tuple[tuple[tuple[int, ...], ...], ...]
_FRowLevels = tuple[tuple[int, ...], ...]


def _f_check_tables(tables: _FTableCells, level: _FRowLevels) -> set[int]:
    """Check the resolved tables; return the set of table cells.

    Every resolved cell must be read by exactly one row, and every cell must
    lie inside the store.
    """
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
    return cells_of_tables


def _f_allocate() -> _FAllocation:
    """Allocate every walked cell of the fourteen-input build, in order.

    ``_Window.take`` returns the first free cell with the wanted ``g`` value,
    so this order fixes every address the build that follows finds.
    """
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
    return _FAllocation(
        window,
        mix,
        xcell,
        helper,
        extras,
        readout,
        select,
        triples,
        spares,
        singles,
        level3_seeds,
        hub_a,
        hub_prep,
        seeds,
        label,
    )


def _f_place(alloc: _FAllocation, cells_of_tables: set[int]) -> _FPlacement:
    """Place the hubs, stubs and data cells, keeping the tables clear.

    The decoder runs from ``_F_DECODER``; its first cell is read while the N
    hubs still hold one less, so that address stays avoided too.
    """
    values, pointer = _pointers(alloc.label, _seed_values(alloc.seeds, _F_SEEDS))
    decoder = set(range(_F_DECODER - 1, _F_DECODER + _F_DECODER_SPAN))
    avoid = cells_of_tables | decoder
    data, stubs, hub_turns = _t_place(values, alloc.label, avoid, _F_HUB_CELLS)
    return _FPlacement(values, pointer, decoder, avoid, data, stubs, hub_turns)


def _f_emit_constants(
    main: _Planner, mem: dict[int, int | None], alloc: _FAllocation
) -> None:
    """Emit the mixer inits: constants, priming, trampolines, label chains."""
    helper = alloc.helper
    _build_constants(main, helper)
    _prime(
        main,
        helper,
        (
            helper["all1"],
            helper["all2"],
            *sorted(alloc.label),
            *alloc.triples,
            *alloc.spares,
        ),
    )
    for a in alloc.singles[:_F_TRAMPOLINES]:
        main.op("*", helper["all2"])
        main.op("p", a)
        mem[a] = _crazy(_ALL2, _g(a))
    _seed_label_chains(
        main,
        helper,
        {lab: " ".join(["rot"] * turns) for lab, (_, turns) in _F_SEEDS.items()},
        alloc.seeds,
        alloc.label,
    )
    for pair, seed, (_, turns) in zip(
        (0, 4), alloc.level3_seeds, _F_LEVEL3_SEEDS, strict=True
    ):
        for _ in range(turns):
            main.op("*", seed)
        for k in range(4):
            main.op("p", alloc.triples[pair + k])
            if k < 3:
                main.op("p", alloc.spares[pair // 4 * 3 + k])
    for (c, lvl), target in sorted(alloc.readout.items()):
        if lvl < 2:
            _emit_chain(main, target, _F_PREP[c][lvl][1], helper)
    for target, (_, chain) in zip(alloc.select, _F_SELECT_PREP, strict=True):
        _emit_chain(main, target, chain, helper)


def _f_emit_hubs(
    main: _Planner,
    mem: dict[int, int | None],
    alloc: _FAllocation,
    place: _FPlacement,
) -> dict[int, str]:
    """Emit the hub passes, the N-hub decoder cells and the level-3 handlers."""
    helper, pointer, label = alloc.helper, place.pointer, alloc.label
    main.op("*", helper["z1"])
    nhubs = [v for v in sorted(pointer) if label[pointer[v]] == "N"]
    for v in nhubs:
        _n_hub_pass(main, pointer[v], v)
    # A = 36066, and each p over an all-1 cell swaps it with 13168.
    _emit_chain(main, alloc.hub_prep, _F_HUB_A[1][1], helper)
    main.op("*", alloc.hub_a)
    main.op("p", alloc.hub_prep)
    flips = iter(alloc.spares[6:])
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
    reserved = set(place.stubs) | set(place.data) | place.avoid | set(range(_F_DECODER))
    for v in nhubs:
        chain, code_of = _f_handler(
            v, reserved | set(handlers), alloc.select[4], mem, place.data
        )
        reserved |= set(place.data)
        handlers.update(code_of)
        for op in chain.split():
            if op != "rot":
                main.op("*", helper[_K_CELL[op]])
            main.hub(pointer[v], v, 11)
            main.raw("*" if op == "rot" else "p")
    _turn_hubs(main, pointer, place.hub_turns)
    return handlers


def _f_emit_segment(
    main: _Planner,
    lvl: int,
    segment: tuple[_SegmentOp, ...],
    cell: list[int],
    konst: tuple[int, int, int],
    readout: dict[tuple[int, int], int],
    triples: list[int],
) -> None:
    """Emit one readout segment's typed ops over the mixer and state cells."""
    for op in segment:
        if op.kind == "mix":
            main.op("p", cell[op.arg])
        elif op.kind == "rot":
            main.op("*", cell[op.arg])
        elif op.kind == "const":
            main.op("*", konst[op.arg])
        elif op.kind == "snap":
            if lvl < 2:
                main.op("p", readout[op.arg, lvl])
            else:
                main.op("p", triples[op.arg])
                main.op("p", readout[op.arg, 2])
        else:
            raise ValueError(op.kind)


def _f_emit_readouts(
    main: _Planner,
    alloc: _FAllocation,
    cell: list[int],
    konst: tuple[int, int, int],
) -> None:
    """Emit the eleven-bit fold, the readout segments and the selector jump."""
    helper = alloc.helper
    _emit_fold(main, alloc.mix)
    for lvl, segment in enumerate(_F_SEGMENTS):
        _f_emit_segment(main, lvl, segment, cell, konst, alloc.readout, alloc.triples)
    for rotations in _F_SELECT[1:]:
        main.raw("/")
        main.op("p", alloc.xcell)
        for _ in range(rotations):
            main.op("*", alloc.xcell)
    for target in alloc.select:
        main.op("p", target)
    main.op("*", helper["all2"])
    main.op("p", helper["a1"])
    main.goto(alloc.select[0])
    main.raw("i")


def _f_emit_main(alloc: _FAllocation, place: _FPlacement) -> _FMain:
    """Walk the main code: inits, hubs, readouts.  Return it with its end."""
    cell = [*alloc.mix, *alloc.extras]
    konst = (alloc.helper["z0"], alloc.helper["all1"], alloc.helper["all2"])
    main, mem = _main_planner(place.data)
    _f_emit_constants(main, mem, alloc)
    handlers = _f_emit_hubs(main, mem, alloc, place)
    _f_emit_readouts(main, alloc, cell, konst)
    return _FMain(main, mem, handlers, main.c)


def _f_emit_epilogue(
    alloc: _FAllocation, place: _FPlacement, emitted: _FMain
) -> list[dict[int, str]]:
    """Emit the per-level selector stubs and the decoder; check its second pass."""
    main, mem = emitted.main, emitted.mem
    parts: list[dict[int, str]] = [main.code, emitted.handlers]
    for lvl, per_copy in enumerate(_f_select()):
        entry = alloc.select[2 * lvl] + 1
        for c, value in enumerate(per_copy):
            stub = _Planner(value + 1, entry, mem, place.data)
            _t_jump(stub, alloc.readout[c, lvl], _F_OFFSETS[c][lvl])
            parts.append(stub.code)
    dec = _Planner(_F_DECODER, 0, mem, place.data)
    _decoder_entry(dec, _F_DECODER)
    for _ in range(_F_DECODER_NOPS):
        dec.raw("o")
    dec.goto(alloc.select[2])
    dec.raw("i")
    second = [_second_pass(op, a) for a, op in sorted(dec.code.items())]
    if second[: _F_DECODER_NOPS + 2] != ["o"] * (_F_DECODER_NOPS + 1) + ["i"]:
        raise AssertionError("the decoder's second pass changed")
    if not set(dec.code) <= place.decoder:
        raise AssertionError("the decoder overran its span")
    parts.append(dec.code)
    return parts


@cache
def _fourteen() -> _Layout:
    """Return ``(code, data, level, tables, labels)`` for fourteen inputs.

    ``level[c][row]`` is the level (0-based) at which copy ``c`` of the
    eleven-bit prefix ``row`` resolves and ``tables[level][c][row]`` its
    cells.  Raises if any code, stub, hub, handler or data cell collides with
    another or with a table cell, or if the decoder's second pass breaks.
    """
    tables, level = _f_tables()
    cells_of_tables = _f_check_tables(tables, level)
    alloc = _f_allocate()
    place = _f_place(alloc, cells_of_tables)
    emitted = _f_emit_main(alloc, place)
    parts = _f_emit_epilogue(alloc, place, emitted)
    code = _merge_code(
        (*parts, place.stubs), place.data, cells_of_tables, emitted.code_end
    )
    labels = {p - 1: lab for p, lab in alloc.label.items()}
    return _Layout(code, place.data, level, tables, labels)
