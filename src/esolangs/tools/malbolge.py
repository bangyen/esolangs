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
the answer stub read the thirteenth, and ``n == 14`` folds inputs twelve and
thirteen into a four-way selector over a three-level cascade.  ``n > 14`` is
refused.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
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
# Fourteen inputs: two selectors, three levels, the stub reads the last input.
#
# Input twelve selects one of two paths as the twelve-input build does; each
# path reads input thirteen into a shared selector cell and selects one of
# four *sub-paths*, one per copy ``2 * x12 + x13``.  A copy transforms the
# readout by searched ops over the mixer cells and three mask constants, and
# 5,525 of the 8,192 rows own their level-1 cell.  A shared cell holds ``N``
# whoever reads it, at whatever level: the sharers read a second cell, and a
# third, until each owns one (2,185 resolve at level 2, 482 at level 3).
# Level-2 cells may therefore land on level-1 cells, which is what the
# one-shot level-2 post-maps could not afford, and a row's third read passes
# the decoder at 29525 a second time.  Its cells have been re-enciphered by
# then: at residues 9 through 17 ``j`` and ``o`` both image to nops and at
# residue 18 ``o`` images to ``i``, so the second pass runs nine nops and
# jumps through ``mem[V + 11]`` for the N hub ``V`` it came through -- a
# handler that selects the level-3 copy.  The selector cell serves every
# level: a sub-path rewrites it by a searched chain of constant ``p`` and
# ``*`` to its copy's level-2 address, and a level-2 path likewise to the
# level-3 address, so the decoder and the handler both jump through the one
# cell.
#
# Paths are jumped to, never walked, so every cell they touch is navigated to
# by ``o`` and ``j`` from wherever ``d`` was left.  The cells they use are
# packed into 163..243, and the free addresses there hold *trampolines*:
# ``p`` with ``A = all-2`` over a walked cell whose ``g`` is at least 81
# leaves a value in 162..242, so a ``j`` through it lands inside the window.
# That cuts a path's navigation from ~56 cells per op to ~20.
_FOURTEEN_N = 14
_Selector = tuple[tuple[int, ...], tuple[tuple[int, int], ...], int]
#: Input twelve's selector: four walked cells' ``g`` values, the ops run from
#: ``A = '0' + x`` and the output cell.
_F_SELECT12: _Selector = ((), (), 0)
#: Input thirteen's: the shared output cell's ``g`` value, then per input-twelve
#: path three scratch cells' ``g`` values and the ops over cells 0 (output)
#: to 3.
_F_SELECT13: tuple[
    int, tuple[tuple[tuple[int, ...], tuple[tuple[int, int], ...]], ...]
] = (
    0,
    (((), ()), ((), ())),
)
#: Mask constants as state cells 8, 9 and 10: ``*`` on the first gives
#: ``A = 52487``, whose ``p`` swaps the top trit and the low eight and fixes
#: the second, so the readout stays in blocks 3, 5, 6 and 8 -- clear of the
#: code and the decoder with no offset.  Each is a walked ``g`` value run
#: through ``p`` with ``A = 0``, ``p`` with ``A = all-2`` and ``*``.
_F_CONSTS = ((38, "K0 K2 rot"), (47, "K0 K2 rot"), (35, "K0 K2 rot rot"))
#: Per copy ``2 * x12 + x13``, per level: ops, readout cell and table offset,
#: searched by annealing under the shared-cell rule (0 rows left of 8,192).
_F_LEVELS: tuple[tuple[tuple[tuple[tuple[int, int], ...], int, int], ...], ...] = (
    (),
    (),
    (),
)
#: Path code budgets: the input-twelve paths, then per level, copy and
#: segment; every selector, chain and link value was cleared for its length.
#: A sub-path or level-2 path is one segment per run of the copy's ops --
#: the first at the address the selector or the chain derives -- then the
#: chain for the next level with the preload, then the table jump; a level-3
#: path folds the last two together.  The tables leave few free runs long
#: enough to link into, and a link costs a window cell that nothing else can
#: then use, so the ops are cut into as many segments as this tuple gives.
_F_PATH_LEN12 = 0
_F_SEG_LEN: tuple[tuple[tuple[int, ...], ...], ...] = ((), (), ())
#: Segment links, in order: per copy the sub-path's second to fourth
#: segment, then the level-2 path's, then the level-3 path's second and
#: third.  Each is
#: a window cell's ``g`` value (below 81, so never a trampoline), the constant
#: ``p`` run over it first (``K2``/``K1``/``K0`` from an adjacent supply cell
#: holding all-2, all-1 or 0; empty for none) and the rotations after; the
#: cell then holds the segment's address minus one, and the segment before
#: ends with ``i`` through it.
_F_LINKS: tuple[tuple[int, str, int], ...] = ()
#: Per input-twelve path, the chain (``K0``/``K1``/``K2`` are ``p`` with
#: ``A`` 0, all-1, all-2; ``rot`` is ``*``) it runs on the selector cell once
#: input thirteen is folded in, so both values start free runs holding the
#: sub-paths; then per level 2 and 3, per copy, the chain the previous
#: level's path runs on the cell for the copy's next path.
_F_SUB_CHAINS: tuple[str, str] = ("", "")
_F_LEVEL_CHAINS: tuple[tuple[str, ...], tuple[str, ...]] = ((), ())
_F_SEEDS = _T_SEEDS
#: N hubs hold all-1 twice, then the handler pointer at ``V + 11`` and the
#: handler's own ``j`` character at ``V + 12``; the second pass only walks
#: ``d`` over the cells between, so those stay free for anything.
_F_HUB_CELLS: dict[str, int | tuple[int, ...]] = {**_T_HUB_CELLS, "N": (1, 2, 11, 12)}
_F_DECODER_NOPS = 8
#: Handlers may sit in the free band between the main code and the tables.
_F_HANDLER_FLOOR = 8600
#: The window path cells and trampolines are packed into.
_F_WINDOW = (163, 244)


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


def _f_state() -> list[int]:
    return [*_C_INITS, 0, 29524, 59048, *(_chain(g, ops) for g, ops in _F_CONSTS)]


@cache
def _f_tables() -> tuple[
    tuple[tuple[tuple[int, ...], ...], ...], tuple[tuple[int, ...], ...]
]:
    """Return the table cell per level, copy and prefix, and each row's level.

    A cell read by two rows holds ``N``; a row resolves at the first level
    where its cell is read by no other row that gets that far.  Raises if a
    row never resolves.
    """
    rows = 1 << _CASCADE_N
    tables = [[[0] * rows for _ in range(4)] for _ in _F_LEVELS]
    for row in range(rows):
        cells = _f_state()
        a = 0
        for i in range(_CASCADE_N):
            bit = (row >> (_CASCADE_N - 1 - i)) & 1
            a = _apply(cells, 49 if bit else 48, _C_SCHEDULE)
        _apply(cells, a, _C_POST[0])
        for c in range(4):
            state = list(cells)
            for lvl, spec in enumerate(_F_LEVELS):
                ops, readout, offset = spec[c]
                _apply(state, 0, ops)
                tables[lvl][c][row] = state[readout] + 1 + offset
    reach = [[len(_F_LEVELS)] * rows for _ in range(4)]
    level = [[-1] * rows for _ in range(4)]
    changed = True
    while changed:
        changed = False
        count = Counter(
            tables[lvl][c][row]
            for c in range(4)
            for row in range(rows)
            for lvl in range(reach[c][row])
        )
        for c in range(4):
            for row in range(rows):
                k = next(
                    (
                        lvl
                        for lvl in range(reach[c][row])
                        if count[tables[lvl][c][row]] == 1
                    ),
                    -1,
                )
                level[c][row] = k
                new = len(_F_LEVELS) if k < 0 else k + 1
                if new != reach[c][row]:
                    reach[c][row] = new
                    changed = True
    if any(k < 0 for per_copy in level for k in per_copy):
        raise AssertionError("a row never resolves")
    return (
        tuple(tuple(tuple(t) for t in tl) for tl in tables),
        tuple(tuple(lv) for lv in level),
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


def _link_value(g: int, kind: str, rotations: int) -> int:
    """Return what a link cell holds: ``rot**rotations`` of ``K(g)`` or ``g``."""
    return _chain(g, " ".join(([kind] if kind else []) + ["rot"] * rotations))


def _f_selected(x12: int, x13: int) -> int:
    """Return the shared selector cell's value for copy ``2 * x12 + x13``."""
    scratch, ops = _F_SELECT13[1][x12]
    state = [_F_SELECT13[0], *scratch]
    _apply(state, 48 + x13, ops)
    return state[0]


@cache
def _fourteen() -> _Thirteen:
    """Return ``(code, data, level, tables, labels)`` for fourteen inputs.

    ``level[c][row]`` is the level (0-based) at which copy ``c`` of the
    eleven-bit prefix ``row`` resolves and ``tables[level][c][row]`` its
    cells.  Raises if any code, stub, hub, handler or data cell collides with
    another or with a table cell, if a path overruns the budget its selector
    value was cleared for, or if the decoder's second pass breaks.
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

    used: set[int] = set()
    helper: dict[str, int] = {}
    low, high = _F_WINDOW

    def walked(value: int, *, packed: bool = True) -> int:
        """Allocate a walked cell with ``g == value``, inside the window if asked."""
        ranges = [range(low, high)] if packed else []
        for span in [*ranges, range(128, _ENTRY)]:
            for a in span:
                if _g(a) == value and a not in used:
                    used.add(a)
                    return a
        raise AssertionError(f"no walked cell with g {value}")  # pragma: no cover

    # Cells the paths touch go into the window, most-used first: the mixer,
    # the constants, the selector and its scratch, the preload cell.
    mix = [walked(v) for v in _C_INITS]
    helper["all1"] = walked(_g(low))
    helper["all2"] = walked(_g(low + 1))
    consts = [walked(g) for g, _ in _F_CONSTS]
    helper["a1"] = walked(_T_HELPERS["a1"])
    helper["z0"] = walked(_T_HELPERS["z0"])
    out = walked(_F_SELECT13[0])
    scratch = [[walked(g) for g in per_path[0]] for per_path in _F_SELECT13[1]]
    links = []
    supplies: dict[int, str] = {}
    for g, link_kind, _ in _F_LINKS:
        link = walked(g)
        if link_kind:
            # A supply cell must sit just before the link: take the next
            # address with this ``g`` if the first one's predecessor is used.
            while link - 1 in used:
                link = walked(g, packed=False)
            used.add(link - 1)
            supplies[link] = link_kind.split()[0]
        links.append(link)
    for name in ("z1", "w", "v"):
        helper[name] = walked(_T_HELPERS[name], packed=False)
    select12 = [walked(v, packed=False) for v in _F_SELECT12[0]]
    seeds = {lab: walked(value, packed=False) for lab, (value, _) in _F_SEEDS.items()}
    # Trampolines: pairs of free cells from 130 up through the window, the
    # first an all-2 supply, the second holding ``K2(g)`` once ``p`` runs over
    # it with ``A = all-2``.  The pointer cells the mixer no longer needs are
    # trampolines too, written one by one.
    trampolines: list[tuple[int, int]] = []
    label = {t + 34: lab for t, lab in enumerate(_T_LABELS) if lab != "-"}
    singles = [a for a in range(34, 128) if a not in label and _g(a) >= 81]
    singles += [a for a in range(130, 257) if a not in used and _g(a) >= 81]
    used.update(singles)
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

    twelve = []
    for x in (0, 1):
        state = list(_F_SELECT12[0])
        _apply(state, 48 + x, _F_SELECT12[1])
        twelve.append(state[_F_SELECT12[2]])
    # ``targets[c][lvl]``: the segment starts of copy ``c``'s path at ``lvl``.
    link_of: dict[tuple[int, int, int], int] = {}
    for lvl in range(3):
        for c in range(4):
            for k in range(len(_F_SEG_LEN[lvl][c]) - 1):
                link_of[lvl, c, k] = len(link_of)
    targets: list[list[list[int]]] = []
    for c in range(4):
        v = _chain(_f_selected(c >> 1, c & 1), _F_SUB_CHAINS[c >> 1])
        v2 = _chain(v, _F_LEVEL_CHAINS[0][c])
        firsts = [v, v2, _chain(v2, _F_LEVEL_CHAINS[1][c])]
        targets.append(
            [
                [first]
                + [
                    _link_value(*_F_LINKS[link_of[lvl, c, k]])
                    for k in range(len(_F_SEG_LEN[lvl][c]) - 1)
                ]
                for lvl, first in enumerate(firsts)
            ]
        )
    regions: list[tuple[int, int]] = [(v, _F_PATH_LEN12) for v in twelve]
    for c in range(4):
        for lvl in range(3):
            for start, length in zip(targets[c][lvl], _F_SEG_LEN[lvl][c], strict=True):
                regions.append((start, length))
    paths_region: set[int] = set()
    for start, length in regions:
        span = set(range(start + 1, start + 1 + length))
        if span & paths_region:
            raise AssertionError("path regions overlap")
        paths_region |= span
    avoid = cells_of_tables | set(range(29520, 29800)) | paths_region
    data, stubs, hub_turns = _t_hubs(values, label, avoid, _F_HUB_CELLS)

    cell = [*mix, helper["z0"], helper["all1"], helper["all2"], *consts]
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
    main.op("*", helper["z1"])
    supply_cells: list[int] = sorted(link - 1 for link in supplies)
    for p in (helper["all1"], helper["all2"], *supply_cells, *sorted(label)):
        main.op("p", p)
        main.op("p", p)
    main.op("*", helper["w"])
    for p in (helper["all2"], *(q for q in supply_cells if supplies[q + 1] == "K2")):
        main.op("p", p)  # ``crazy(all-2, all-1)`` is all-2, so ``A`` holds
    for supply in supply_cells:
        if supplies[supply + 1] == "K0":
            main.op("*", helper["z1"])
            main.op("p", supply)  # ``crazy(all-1, all-1)`` is 0
    del trampolines
    for a in singles:
        main.op("*", helper["all2"])
        main.op("p", a)
        mem[a] = _crazy(59048, _g(a))
    for target, (_, chain) in zip(consts, _F_CONSTS, strict=True):
        _emit_chain(main, target, chain, helper)
    for link, (_, link_kind, _) in sorted(zip(links, _F_LINKS, strict=True)):
        if link_kind:
            main.op("*", link - 1)
            main.op("p", link)
            _emit_chain(main, link, " ".join(link_kind.split()[1:]), helper)
    for turn in range(1, 10):
        for link, (_, _, rotations) in sorted(zip(links, _F_LINKS, strict=True)):
            if rotations >= turn:
                main.op("*", link)
    for lab, (_, turns) in _F_SEEDS.items():
        for _ in range(turns):
            main.op("*", seeds[lab])
        for p in sorted(label):
            if label[p] == lab:
                main.op("p", p)
    main.op("*", helper["z1"])
    handlers: dict[int, str] = {}
    reserved = set(stubs) | set(data) | avoid
    for v in sorted(pointer):
        if label[pointer[v]] == "N":
            main.hub(pointer[v], v)
            main.raw("p")
            main.hub(pointer[v], v)
            main.raw("p")
            main.raw("p")
            main.hub(pointer[v], v, 2)
            main.raw("p")
            chain, code_of = _f_handler(v, reserved | set(handlers), out, mem, data)
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
            main.op("p" if kind == 0 else "*", cell[index])
    for kind, index in _C_POST[0]:
        main.op("p" if kind == 0 else "*", cell[index])
    main.raw("/")
    for kind, index in _F_SELECT12[1]:
        main.op("p" if kind == 0 else "*", select12[index])
    main.goto(select12[_F_SELECT12[2]])
    main.raw("i")
    code_end = main.c

    parts = [main.code, handlers]
    lengths: dict[str, int] = {}
    budget_of: dict[str, int] = {}
    for x in (0, 1):
        _, sel_ops = _F_SELECT13[1][x]
        cells13 = [out, *scratch[x]]
        path = _Planner(twelve[x] + 1, select12[_F_SELECT12[2]] + 1, mem, data)
        path.raw("/")
        for kind, index in sel_ops:
            path.op("p" if kind == 0 else "*", cells13[index])
        _emit_chain(path, out, _F_SUB_CHAINS[x], helper)
        path.goto(out)
        path.raw("i")
        lengths[f"twelve {x}"] = path.c - twelve[x] - 1
        budget_of[f"twelve {x}"] = _F_PATH_LEN12
        parts.append(path.code)
    for lvl in range(3):
        if lvl == 1:
            dec = _Planner(_NEXT + 1, 0, mem, data)
            dec.raw("j")
            dec.raw("j")
            dec.d = ord(_XLAT2[_char_for("j", _NEXT + 1) - 33]) + 1
            for _ in range(_F_DECODER_NOPS):
                dec.raw("o")
            dec.goto(out)
            dec.raw("i")
            second = [_second_pass(op, a) for a, op in sorted(dec.code.items())]
            if second[: _F_DECODER_NOPS + 2] != ["o"] * (_F_DECODER_NOPS + 1) + ["i"]:
                raise AssertionError("the decoder's second pass changed")
            parts.append(dec.code)
        for c in range(4):
            ops, readout, offset = _F_LEVELS[lvl][c]

            def piece(part: _Ops) -> Callable[[_Planner], None]:
                """Return a step running part of the copy's ops."""

                def run_ops(seg: _Planner) -> None:
                    _t_ops(seg, cell, part)

                return run_ops

            def chain_and_preload(path: _Planner, lvl: int = lvl, c: int = c) -> None:
                if lvl < 2:
                    _emit_chain(path, out, _F_LEVEL_CHAINS[lvl][c], helper)
                for _ in range(1 if lvl == 0 else 2):
                    path.op("*", helper["all2"])
                    path.op("p", helper["a1"])

            def jump(
                path: _Planner, readout: int = readout, offset: int = offset
            ) -> None:
                _t_jump(path, cell[readout], offset)

            def preload_and_jump(path: _Planner) -> None:
                chain_and_preload(path)
                jump(path)

            runs = len(_F_SEG_LEN[lvl][c]) - (2 if lvl < 2 else 1)
            pieces = [
                piece(ops[k * len(ops) // runs : (k + 1) * len(ops) // runs])
                for k in range(runs)
            ]
            steps: list[Callable[[_Planner], None]] = (
                [*pieces, chain_and_preload, jump]
                if lvl < 2
                else [*pieces, preload_and_jump]
            )
            d = out + 1
            for k, step in enumerate(steps):
                start = targets[c][lvl][k]
                path = _Planner(start + 1, d, mem, data)
                step(path)
                if k + 1 < len(steps):
                    link = links[link_of[lvl, c, k]]
                    path.goto(link)
                    path.raw("i")
                    d = link + 1
                name = f"level {lvl + 1} copy {c} segment {k + 1}"
                lengths[name] = path.c - start - 1
                budget_of[name] = _F_SEG_LEN[lvl][c][k]
                parts.append(path.code)
    if any(lengths[k] > budget_of[k] for k in lengths):
        raise AssertionError(f"path lengths {lengths} exceed budgets {budget_of}")

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
    last input read by the answer stub, fourteen two selectors and a
    three-level cascade; ``n > 14`` is refused.  Every build is the full
    59049-cell store.
    """
    n = _validate_truth_table(truth_table)
    if n > _FOURTEEN_N:
        raise GeneratorCapError(
            f"Malbolge builds at most {_FOURTEEN_N} inputs, got {n}: a third "
            "selector's eight copies would need a fourth cascade level, and "
            "the decoder's second pass is the last one its cells afford"
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
