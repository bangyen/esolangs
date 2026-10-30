"""Malbolge's boolean build: a positional address, so no row collides.

A readout word has ten trits, five two-trit *digits*, and three input bits
have eight values, so a digit can hold three bits outright: fifteen address
bits fill the word and every row pair owns its own cell, with no hashing, no
shared cells and no decoder.

A 16-op *gadget* over three fresh walked cells reads three inputs and leaves
them injectively in trit 0 of cells 1 and 2 (``u`` and ``v``); ``crazy`` works
trit by trit, so trits 1..9 of those cells stay constant whatever the input.
The accumulator ``S`` then takes one digit per group: ``p`` over ``S`` with
``A = v`` (bijective in ``v`` because ``S``'s trit 0 is 1), ``*`` rotates ``S``,
``p`` over cell 1 with ``A = S`` (bijective in ``u`` because the rotated trit 0
is 2), ``*`` again.  At trits already holding digits the constants are 2 and
1 -- ``crazy``'s two bijective rows -- so no earlier digit is lost, and the
cells' walked ``g`` values are chosen so that every untouched trit of ``S``
arrives at trit 0 holding exactly the 1 or 2 it needs (:func:`_d_outputs`,
:func:`_d_inits`).  After five groups
``S`` is back in its own alignment: digit ``k`` is input group ``k``.

Each digit misses one of its nine values.  A ``swap12`` on group 4's ``v``
and on group 1's ``u`` and a final ``swap01`` of the whole word make the top
digit miss ``(0, 0)`` and digit 1 miss ``(2, 2)``: every readout lies in
6561..59039, so the code fits below the table and no cell wraps past 59048.

Up to fifteen inputs the last group's held reads are chosen so the tables
pack low (``'1','0','1'`` to thirteen: 6562..13113; fourteen ``'1','0'``:
..19674; fifteen ``'0'``: 19684..52479), and each label has one hub and a
stub in the gaps or just past the tables (:func:`_short_layout`): the source
ends at its highest live cell, 13,144 characters to thirteen inputs, 19,683
at fourteen, 52,480 at fifteen, instead of the 59,049-cell store.

Fewer than sixteen inputs hold ``16 - n`` of the fifteen reads at a
constant, ``'0'`` unless the arity's tables need the ``'1'`` above: three per
group from the last group, a group's leading reads first.  A held read is
``p`` with ``A = all-2`` over a cell holding 69 (``crazy(all-2, 69) == 48``),
which leaves 48 there and 69 again after the next such ``p``, so one cell
serves every held read.  Without the short layout every build's cells are a
subset of sixteen's and the hubs and stubs are placed once for all.

The row's cell ``S + 1`` holds a label character naming one of four answers
as a function of the last input -- ``0``, ``1``, ``x`` or ``not x`` -- and
the answer stub reads that input.  Hubs and stubs sit where a missing
digit keeps every table cell out (:mod:`.core`).
Seventeen inputs would need 65,536 cells, more than the store.  Two
restricted families are the exceptions: a table that ignores an input
is the sixteen build over its projection, with the ignored input's
read discarded in the gadget group that would have folded it, so the
stream stays aligned and the stub still reads the last input; a table
constant on Hamming-weight classes is the popcount build in
:mod:`.symmetric`, whose first group folds four inputs into their
weight, so one cell serves every row of a weight.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import cache
from itertools import product
from typing import NamedTuple

from esolangs.languages.malbolge.interpreter import _crazy

from .core import (
    _ANSWER,
    _ENTRY,
    _K_CELL,
    _OPERAND_CHAIN,
    _SEED_CHAIN,
    _T_HELPERS,
    _T_HUB_LABELS,
    _T_LABELS,
    _T_LOW,
    _T_STUBS,
    _Build,
    _build_constants,
    _chain,
    _emit_chain,
    _hub_layout,
    _main_planner,
    _merge_code,
    _operand_cells,
    _operand_stub,
    _pointers,
    _prime,
    _s01,
    _seed_g,
    _seed_label_chains,
    _stub_builds,
    _t_jump,
    _table_char,
    _walker,
    _write_hubs,
)
from .emitter import _Planner, _valid_chars
from .isa import (
    _ALL1,
    _CONSTS,
    _WORDS,
    _first_free,
    _program,
    _render,
    _rot,
)

#: The largest input count the generator builds: fifteen positional reads
#: and the last input read by the stub.
_DIGITS_N = 16
#: Reads per gadget group.
_READS = 3
#: The ``_GADGET`` token index before which a discarded read drops a
#: group's slot (1-based): the read lands where the next read or constant
#: overwrites ``A``, so the gadget's cells never see the ignored input.
#: Slot 4 is the read past the group -- the next group's first slot, or
#: the stub's own input when the last group drops it.
_DROP_TOKEN = {1: 0, 2: 2, 3: 4, 4: 13}

#: The gadget: ``/`` reads an input, ``K`` sets ``A`` to 0 / all-1 / all-2 and
#: a digit names the cell a ``p`` runs over.  The unique shortest injective
#: suffix after the wipe prefix (``test_suffix_is_unique_shortest``); cells 1, 2
#: are ``u = 1+x-y-xyz``, ``v = (2-x)(1-z)+zxy`` mod 3 (trit 0).
_GADGET = tuple("/ 0 / 1 K2 0 K2 1 / 2 0 1 0 K1 0 2".split())  # noqa: SIM905
#: Gadget groups, one digit each.
_D_GROUPS = 5
#: Trits 1..3 of the reads ``'0'`` and ``'1'`` (48, 49), which agree there.
_READ_TRITS = (1, 2, 1)
#: A trit of ``S`` already holding a digit, in :func:`_fold`.
_DIGIT = -1
#: A group's ``(u, v)`` at trits 1, 2 and 3.
type _Choice = tuple[tuple[int, int], ...]
#: The groups whose ``v`` and ``u`` are ``swap12``-ed before they are folded in.
_D_SWAP_V = 4
_D_SWAP_U = 1
#: Stubs, hub characters and the navigation's data cells sit at or above
#: this, the code below: no readout has top digit ``(0, 0)``.
_D_FLOOR = 3**8
#: The labelled pointer cells.
_D_LABEL = {t + 34: lab for t, lab in enumerate(_T_LABELS) if lab in "01xn"}
#: Each label's seed ``g`` (:func:`~.core._seed_g`).
_D_SEEDS = {lab: _seed_g(m) for m, lab in enumerate(_T_HUB_LABELS, 1)}

#: Up to ``_SHORT_N`` inputs share one short layout: the last group's three
#: held reads are ``'1','0','1'`` (49, 48, 49), which puts every table in
#: 6562..13113.  Each label has one hub (pointer value ``s01(chain(g))``, all
#: its cells equal) at 13122..13130; its stub sits in the table-free run
#: 11664..12392 or past 13113, so the source ends at 13,144.  Arities up to
#: ``_SHORT_MAX`` get their own layout over their own tables: 14 holds
#: ``'1','0'`` (tables 6562..19674), 15 holds ``'0'`` (tables 19684..52479;
#: ``'1'`` would reach 59,039); 16 fills the store.
_SHORT_N = 13
_SHORT_MAX = 15
#: Arities up to this hold the last group's reads at ``_TOP_HELD``.
_TOP_HELD_N = 14
_TOP_HELD = (49, 48, 49)
#: ``p`` under ``A = all-2`` swaps 71 and 49 as it does 69 and 48.
_ONE_CELL_G = 71
#: Short layout: seeds and stubs are chains of at most this many ops on a
#: pointer-region ``g`` (:func:`_short_layout`).
_SHORT_DEPTH = 5
_SHORT_G = range(33, 127)
#: Stubs sit in the table-free run 11664..12392 (3**6 cells) or past the tables.
_SHORT_STUB_FLOOR = 11664


class _Layout(NamedTuple):
    """Each label's ``(g, chain)``: its seed (hub) and its stub address."""

    seeds: dict[str, tuple[int, str]]
    stubs: dict[str, tuple[int, str]]


def _chains(values: dict[int, int], depth: int) -> Iterator[tuple[str, dict[int, int]]]:
    """Yield every chain of at most ``depth`` ops with its result per ``g``."""
    yield "", values
    if depth:
        for op in ("K0", "K1", "K2", "rot"):
            moved = {g: _chain(v, op) for g, v in values.items()}
            for ops, out in _chains(moved, depth - 1):
                yield f"{op} {ops}".strip(), out


@cache
def _short_layout(arity: int = _SHORT_N) -> _Layout:
    """Return the seeds and stubs for ``arity`` inputs (``n <= 13`` share 13's).

    Greedy, hubs in ``n01x`` order then stubs in ``1n0x``: each takes the
    lowest address that clears the tables and the picks before it, by the
    shortest chain, then the ``g`` whose walked cell is nearest the first: each
    op walks to its cell, and the main code must end below the lowest table
    cell (6532 against 6562).  A hub is any seedable address whose two data
    cells are free, below the top table cell too (14's land in its gaps).
    """
    tables = {s + 1 for s in _readouts(arity)}
    chains: dict[int, list[tuple[int, str, int]]] = {}
    for ops, out in _chains({g: g for g in _SHORT_G}, _SHORT_DEPTH):
        for g, v in out.items():
            chains.setdefault(v, []).append((len(ops.split()), ops, g))
    reach: dict[int, list[tuple[int, str, int]]] = {}
    seedable: set[int] = set()
    for v, picks in chains.items():
        reach.setdefault(_s01(v), []).extend(picks)
        # A label's second cell is re-swapped by ``p`` under ``A = all-1``, which
        # is ``s01`` only if ``crazy(all-1, v) == s01(v)``: ``v`` has no 0 trit.
        if _crazy(_ALL1, v) == _s01(v):
            seedable.add(_s01(v))
    addresses = sorted(reach)
    taken: set[int] = set()
    at: dict[tuple[str, str], int] = {}
    for lab in _T_HUB_LABELS:
        hub = next(
            a
            for a in addresses
            if a > _D_FLOOR and a in seedable and not {a + 1, a + 2} & (tables | taken)
        )
        at["seed", lab] = hub
        taken |= {hub + 1, hub + 2}
    operands = _operand_cells()
    for lab in "1n0x":
        hub = at["seed", lab]
        stub = _T_STUBS.get(lab) or _operand_stub(
            min(_valid_chars(hub + 2)) + 1, operands[lab]
        )
        busy = tables | taken
        address = next(
            a
            for a in addresses
            if a >= _SHORT_STUB_FLOOR and busy.isdisjoint(range(a, a + 1 + len(stub)))
        )
        at["stub", lab] = address
        taken |= set(range(address, address + 1 + len(stub)))

    def pick(address: int) -> tuple[int, str]:
        """Return the ``(g, chain)``: fewest ops, then the nearest walked cell."""
        _, ops, g = min(
            reach[address],
            key=lambda c: (c[0], _first_free(c[2], 128, _ENTRY, set()), c[1]),
        )
        return g, ops

    return _Layout(
        {lab: pick(at["seed", lab]) for lab in _T_HUB_LABELS},
        {lab: pick(at["stub", lab]) for lab in "1n0x"},
    )


def _longest_stub(n: int) -> int:
    """Return the commands of the longest short-layout stub at ``n`` inputs.

    A ``1`` or ``n`` stub runs every character; ``0`` and ``x`` run three.
    """
    hubs = _hubs(_short_layout(max(n, _SHORT_N)))
    cells = _operand_cells()
    return max(
        len(_operand_stub(min(_valid_chars(hubs[lab][0] + 2)) + 1, cells[lab]))
        for lab in "1n"
    )


def _held(n: int, group: int) -> int:
    """Return how many of ``group``'s leading reads ``n`` inputs hold at ``'0'``.

    ``16 - n`` reads are held in all, three per group from the last group.
    """
    spare = _DIGITS_N - n - _READS * (_D_GROUPS - 1 - group)
    return max(0, min(_READS, spare))


def _short(n: int) -> bool:
    """Return whether ``n`` inputs build the short layout."""
    return n <= _SHORT_MAX


def _held_read(n: int, group: int, index: int) -> int:
    """Return the value of ``group``'s ``index``-th held read."""
    if n <= _TOP_HELD_N and group == _D_GROUPS - 1:
        return _TOP_HELD[index]
    return 48


def _swap12(value: int) -> int:
    """``p`` with ``A = 2``: trit 0 swaps 1 and 2, constant 1s and 2s stay."""
    return _crazy(2, value)


def _trit_gadget(cells: tuple[int, ...], read: int) -> tuple[int, int]:
    """Return ``(u, v)`` at one trit from the cells' trits and the reads' trit."""
    c, a = list(cells), 0
    for op in _GADGET:
        if op == "/":
            a = read
        elif op[0] == "K":
            a = int(op[1])
        else:
            a = c[int(op)] = _crazy(a, c[int(op)]) % 3
    return c[1], c[2]


def _fold(s: tuple[int, ...], choice: _Choice, group: int) -> tuple[int, ...] | None:
    """Return ``S``'s trits after ``group`` folds in, or ``None`` if it fails.

    ``choice`` is the cells' ``(u, v)`` at trits 1..3; above, every trit
    pattern of 0s and 1s gives the digit constants ``(1, 2)``.  The fold
    needs ``S_0 = 1``, the rotated trit 0 to be 2, ``v_k = 2`` under each
    digit of ``S`` and ``u_k = 1`` under each digit of the rotated ``S``.
    """
    u = [0, *(uv[0] for uv in choice), *[1] * 6]
    v = [0, *(uv[1] for uv in choice), *[2] * 6]
    # swap12 is crazy(2, .): A's trits above 0 are 0, which keeps 1s and 2s.
    if group == _D_SWAP_V:
        v = [_crazy(0, x) % 3 for x in v]
    if group == _D_SWAP_U:
        u = [_crazy(0, x) % 3 for x in u]
    if s[0] != 1 or any(x == _DIGIT and v[k] != 2 for k, x in enumerate(s) if k):
        return None
    s1 = [
        _DIGIT,
        *(x if x == _DIGIT else _crazy(v[k], x) % 3 for k, x in enumerate(s) if k),
    ]
    r = s1[1:] + s1[:1]
    if r[0] != 2 or any(x == _DIGIT and u[k] != 1 for k, x in enumerate(r) if k):
        return None
    s2 = [
        _DIGIT,
        *(x if x == _DIGIT else _crazy(x, u[k]) % 3 for k, x in enumerate(r) if k),
    ]
    return tuple(s2[1:] + s2[:1])


def _d_choice(s: tuple[int, ...], group: int) -> _Choice:
    """Return ``group``'s ``(u, v)`` at trits 1..3, solving each trit's equation.

    The fold maps ``S_k`` to ``crazy(crazy(v_{k+2}, S_{k+2}), u_{k+1})`` at
    ``k - 2``.  Trit 3 keeps the digit constants.  Trit 1 turns ``S_1`` to 2
    (``v_1 = 1`` under a 2, else 2) and takes ``u_1 = 2`` only when ``S_2 = 2``,
    which no ``v_2`` sends to 0.  Trit 2 makes the next ``S_0`` 1 and the next
    ``S_1`` 1, or 2 when ``S_3 = 2``, from which 1 is out of reach.  Digits of
    ``S`` need ``v = 2`` above them and ``u = 1`` one trit lower.
    """
    swap_u, swap_v = group == _D_SWAP_U, group == _D_SWAP_V
    us = [_crazy(0, a) % 3 if swap_u else a for a in range(3)]
    vs = [_crazy(0, a) % 3 if swap_v else a for a in range(3)]
    _, s1, s2, s3 = s[:4]
    trit1 = (0, 1) if s1 == 2 else (2, 2) if s2 == 2 else (1, 2)
    if s2 == _DIGIT:
        v2 = vs.index(2)
    else:
        target = 2 if us[trit1[0]] == 2 else 0
        v2 = [_crazy(v, s2) % 3 for v in vs].index(target)
    if s3 == _DIGIT:
        u2 = us.index(1)
    else:
        a = _crazy(vs[2], s3) % 3
        u2 = [_crazy(a, u) % 3 for u in us].index(2 if s3 == 2 else 1)
    return trit1, (u2, v2), (1, 2)


@cache
def _d_outputs() -> tuple[_Choice, ...]:
    """Return each group's ``(u, v)`` at trits 1..3 (:func:`_d_choice`).

    ``S`` starts all-1 (29524) and must end all digits; the test checks the
    result is one of the 2,464 sequences that complete.
    """
    s: tuple[int, ...] | None = (1,) * 10
    outputs: list[_Choice] = []
    for group in range(_D_GROUPS):
        assert s is not None, group
        outputs.append(_d_choice(s, group))
        s = _fold(s, outputs[-1], group)
    assert s is not None
    assert all(x == _DIGIT for x in s), s
    return tuple(outputs)


def _helper_cells(used: set[int]) -> dict[str, int]:
    """Allocate the helper cells, each the least free one of its ``g`` value."""
    low, walked = _walker(used, 34), _walker(used)
    helper = {"all1": _T_LOW[0], "all2": _T_LOW[1]}
    for name, value in _T_HELPERS.items():
        helper[name] = (walked if name == "z0" else low)(value)
    return helper


@cache
def _preimages(read: int) -> dict[tuple[int, int], list[tuple[int, ...]]]:
    """Return each gadget output's cell trit triples at ``read``, descending."""
    preimages: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for cells in reversed(list(product(range(3), repeat=3))):
        preimages.setdefault(_trit_gadget(cells, read), []).append(cells)
    return preimages


@cache
def _d_inits() -> tuple[tuple[int, ...], ...]:
    """Return per group the ``g`` values of its three gadget cells.

    Trits 1..3 give :func:`_d_outputs`: the ``j``-th group to need an output
    at a read trit takes that output's ``j``-th preimage, cycling, so few
    cells share trits 1..3.  Trit 0 is 0 or 1, since a 2 lets two reads
    collide, and any such triple misses ``(2, 2)`` as the swaps need.  A
    cell's slot, the count of earlier cells sharing its trits 1..3, picks
    trit 0 and then trit 4 inside 33..126.  The least-address-sum triples
    took 2.8-4.7% fewer steps, but only by search.
    """
    uses: dict[tuple[int, tuple[int, int]], int] = {}
    slots: dict[int, int] = {}
    inits = []
    for outputs in _d_outputs():
        trits = []
        for read, uv in zip(_READ_TRITS, outputs, strict=True):
            preimages, j = _preimages(read)[uv], uses.get((read, uv), 0)
            trits.append(preimages[j % len(preimages)])
            uses[read, uv] = j + 1
        group = []
        for cell in range(_READS):
            low = sum(t[cell] * 3**k for k, t in enumerate(trits, 1))
            values = [v for v in (low, low + 1, low + 81, low + 82) if 33 <= v <= 126]
            group.append(values[slots.get(low, 0)])
            slots[low] = slots.get(low, 0) + 1
        inits.append(tuple(group))
    return tuple(inits)


def _fold_state(
    gadget: tuple[str, ...],
    init: tuple[int, ...],
    reads: Iterator[int],
    group: int,
    s: int,
) -> int:
    """Return the readout state after one gadget group folds into ``s``.

    The gadget runs over a copy of the group's init cells: ``/`` takes
    the next read, ``K<n>`` a constant, a digit a ``crazy`` over that
    cell.  Cells 1 and 2 leave ``u`` and ``v`` -- the group's swap
    applied -- and the state advances through ``crazy``'s two
    bijective rows.  The positional readouts and the popcount build's
    are this same fold, over different gadgets and read counts.
    """
    cells, a = list(init), 0
    for op in gadget:
        if op == "/":
            a = next(reads)
        elif op[0] == "K":
            a = _CONSTS[int(op[1])]
        else:
            a = cells[int(op)] = _crazy(a, cells[int(op)])
    u, v = cells[1], cells[2]
    if group == _D_SWAP_V:
        v = _swap12(v)
    if group == _D_SWAP_U:
        u = _swap12(u)
    return _rot(_crazy(_rot(_crazy(v, s)), u))


@cache
def _readouts(n: int) -> tuple[int, ...]:
    """Return each ``n - 1``-bit prefix's readout, by prefix.

    Built group by group over the distinct states, so each group's work is
    done once per state rather than once per row; a held read is ``'0'``.
    """
    states = [29524]
    for group, init in enumerate(_d_inits()):
        held = _held(n, group)
        free = _READS - held
        following = []
        for s in states:
            for bits in range(1 << free):
                reads = iter(
                    [_held_read(n, group, k) for k in range(held)]
                    + [48 + ((bits >> k) & 1) for k in reversed(range(free))]
                )
                following.append(_fold_state(_GADGET, init, reads, group, s))
        states = following
    return tuple(_crazy(s, 29524) for s in states)


class _Digits(NamedTuple):
    """One arity's build: code, data, table cell per prefix, labels."""

    code: dict[int, str]
    data: dict[int, int]
    tables: tuple[int, ...]
    labels: dict[int, str]
    words: int


@cache
def _digits(n: int, drop: tuple[int, int] | None = None) -> _Digits:
    """Return ``(code, data, table cell per prefix, labels)`` for ``n`` inputs.

    ``drop`` is a ``(group, token)`` pair naming one discarded read in
    that gadget group (the seventeen-input projection build); the
    readouts, tables and labels are sixteen's either way.  Raises if
    any code, stub, hub or data cell collides with another or with a
    table cell, or if the readouts are not distinct.
    """
    tables = tuple(s + 1 for s in _readouts(n))
    if len(set(tables)) != len(tables) or max(tables) >= _WORDS:
        raise AssertionError("readouts collide or wrap")
    # Sixteen's cells hold every arity's, so every build avoids the same set.
    arity = max(n, _SHORT_N)
    layout = _short_layout(arity) if _short(n) else None
    if layout:
        # Smaller arities' cells are a subset of the largest short one's.
        cells_of_tables = {s + 1 for s in _readouts(arity)}
    else:
        cells_of_tables = set(_readouts_cells())
    cells = _allocate_cells(layout)
    _, pointer = _pointers(
        _D_LABEL, _seed_values(layout).items(), single=layout is not None
    )
    builds = _stub_builds(_hubs(layout), layout.stubs) if layout else None
    data, stubs = _hub_layout(_hubs(layout), cells_of_tables, _D_FLOOR, builds)

    main, _ = _main_planner(data)
    _emit_digit_setup(main, cells)
    _emit_digit_groups(main, n, cells, drop)
    _emit_digit_jump(main, cells, pointer, layout)
    code_end = main.c

    code = _merge_code(
        (main.code, stubs), data, cells_of_tables, code_end, ceiling=_D_FLOOR
    )
    labels = {p - 1: lab for p, lab in _D_LABEL.items()}
    words = _WORDS
    if layout:
        words = max(max(code), max(data), max(tables)) + 1
    return _Digits(code, data, tables, labels, words)


class _DCells(NamedTuple):
    """The digit build's working cells."""

    helper: dict[str, int]
    gadget: list[list[int]]
    s_cell: int
    z_cell: int
    two: int
    to_48: int
    seeds: dict[str, int]
    builds: list[_Build]
    builders: list[int]
    operand: int
    to_49: int = -1


def _allocate_cells(layout: _Layout | None = None) -> _DCells:
    """Allocate the working cells, each the least free one of its ``g`` value.

    Cells dead before the labels are written -- the setup helpers, the
    gadget's, ``s`` and ``two`` -- take pointer cells, where every ``j``
    through an unwritten cell lands, so a back jump is a short walk.  ``g``
    has period 94, so a value has one cell there.  The rest take walked
    cells ``128..``, past the operand cells.  With every cell walked, n=16's
    main line ends at 9,977 against 5,487 and n=1's at 16,414 against
    6,013, past the tables.
    """
    operands = _operand_cells()
    used = {*_T_LOW, *(cell for cells in operands.values() for cell in cells)}
    helper = _helper_cells(used)
    low, walked = _walker(used, 34), _walker(used)
    gadget = [[low(v) for v in init] for init in _d_inits()]
    s_cell, z_cell = low(), walked()
    # ``p`` under ``A = all-1`` takes 38 to 2 and keeps 2.
    two = low(38)
    # ``p`` under ``A = all-2`` swaps 69 and 48.
    to_48 = walked(69)
    if layout:
        seeds = {lab: walked(g) for lab, (g, _) in layout.seeds.items()}
        builds = _stub_builds(_hubs(layout), layout.stubs)
    else:
        seeds = {lab: walked(g) for lab, g in _D_SEEDS.items()}
        builds = _stub_builds(_hubs())
    builders = [walked(g) for g, _, _ in builds]
    # Every operand stub shares the middle cell.
    operand = operands["1"][1]
    to_49 = low(_ONE_CELL_G) if layout else -1
    return _DCells(
        helper,
        gadget,
        s_cell,
        z_cell,
        two,
        to_48,
        seeds,
        builds,
        builders,
        operand,
        to_49,
    )


def _emit_digit_setup(main: _Planner, cells: _DCells) -> None:
    """Emit the setup: the constants, then priming the working cells."""
    helper = cells.helper
    _build_constants(main, helper)
    _prime(
        main,
        helper,
        (helper["all1"], helper["all2"], cells.s_cell, cells.z_cell),
    )


def _emit_labels(
    main: _Planner,
    cells: _DCells,
    pointer: dict[int, int],
    layout: _Layout | None = None,
) -> None:
    """Emit the label cells, the hubs' stub addresses and the middle operand.

    Run after the gadget, so the pointer region holds walked ``g`` values
    and dead working cells until the last stub needs it.  ``p`` twice under
    ``A = all-1`` sends any cell to all-1.
    """
    helper = cells.helper
    main.op("*", helper["all1"])
    for p in sorted(_D_LABEL):
        main.op("p", p)
        main.op("p", p)
    chains = (
        {lab: chain for lab, (_, chain) in layout.seeds.items()}
        if layout
        else dict.fromkeys(_D_SEEDS, _SEED_CHAIN)
    )
    _seed_label_chains(
        main, helper, chains, cells.seeds, _D_LABEL, single=layout is not None
    )
    _write_hubs(main, helper, pointer, cells.builds, cells.builders)
    _emit_chain(main, cells.operand, _OPERAND_CHAIN, helper)


def _emit_swap12(main: _Planner, target: int, two: int, helper: dict[str, int]) -> None:
    """Emit a ``swap12`` on ``target``: make ``A`` 2 via ``two``, then ``p``."""
    main.op("*", helper["all1"])
    main.op("p", two)
    main.op("p", target)


def _emit_zero(main: _Planner, cells: _DCells, *, one: bool = False) -> None:
    """Emit ``A = '0'`` (``'1'``): ``p`` under ``A = all-2`` over the to-48 (49) cell.

    One ``p`` while it holds 69 (71), two once it holds 48 (49).
    """
    cell, fresh = (cells.to_49, 71) if one else (cells.to_48, 69)
    for _ in range(1 if main.mem[cell] == fresh else 2):
        main.op("*", cells.helper["all2"])
        main.op("p", cell)


def _emit_gadget_reads(
    main: _Planner,
    n: int,
    group: int,
    cell: list[int],
    cells: _DCells,
    drop_token: int | None = None,
) -> None:
    """Emit one group's gadget ops over its three cells.

    A held read is the constant ``'0'`` (:func:`_emit_zero`).  A dropped
    read (``drop_token``) is a bare ``/`` before that gadget token: it
    consumes one stream input and nothing else, since the token after
    it reloads ``A`` (a read or a constant).
    """
    helper = cells.helper
    held, taken = _held(n, group), 0
    for index, op in enumerate(_GADGET):
        if index == drop_token:
            main.raw("/")
        if op == "/":
            if held:
                held -= 1
                _emit_zero(main, cells, one=_held_read(n, group, taken) == 49)
                taken += 1
            else:
                main.raw("/")
        elif op[0] == "K":
            main.op("*", helper[_K_CELL[op]])
        else:
            main.op("p", cell[int(op)])


def _emit_digit_groups(
    main: _Planner, n: int, cells: _DCells, drop: tuple[int, int] | None = None
) -> None:
    """Emit the five gadget groups, folding one digit per group into ``S``.

    ``S`` starts in the s cell and each group rotates it through its own
    cell 1, so the accumulator cell alternates per group.
    """
    helper = cells.helper
    s = cells.s_cell
    for group, cell in enumerate(cells.gadget):
        token = drop[1] if drop is not None and drop[0] == group else None
        _emit_gadget_reads(main, n, group, cell, cells, token)
        if group == _D_SWAP_V:
            _emit_swap12(main, cell[2], cells.two, helper)
        main.op("p", s)
        if group == _D_SWAP_U:
            _emit_swap12(main, cell[1], cells.two, helper)
        main.op("*", s)
        main.op("p", cell[1])
        main.op("*", cell[1])
        s = cell[1]


def _emit_digit_jump(
    main: _Planner,
    cells: _DCells,
    pointer: dict[int, int],
    layout: _Layout | None = None,
) -> None:
    """Emit the finish: the readout, the labels, then the jump to the row's stub."""
    main.op("p", cells.z_cell)
    _emit_labels(main, cells, pointer, layout)
    _emit_zero(main, cells)
    _t_jump(main, cells.z_cell)


@cache
def _readouts_cells() -> tuple[int, ...]:
    return tuple(s + 1 for s in _readouts(_DIGITS_N))


def _seed_values(layout: _Layout | None = None) -> dict[str, int]:
    """Return each label's seed chain value, the second hub its cells name."""
    if layout:
        return {lab: _chain(g, chain) for lab, (g, chain) in layout.seeds.items()}
    return {lab: _chain(g, _SEED_CHAIN) for lab, g in _D_SEEDS.items()}


def _hubs(layout: _Layout | None = None) -> dict[str, tuple[int, ...]]:
    """Return each label's hubs: its seed value and that value's 0/1 swap.

    The short layout's cells all hold the swap, its one hub.
    """
    if layout:
        return {lab: (_s01(a),) for lab, a in _seed_values(layout).items()}
    return {lab: tuple(sorted((a, _s01(a)))) for lab, a in _seed_values().items()}


def _render_build(truth_table: str, build: _Digits) -> str:
    """Return ``build``'s program with ``truth_table``'s answer cells filled."""
    code, data, tables, labels, words = build
    program = _program(code)
    program.update(data)
    for row, h in enumerate(tables):
        label = _ANSWER[truth_table[2 * row : 2 * row + 2]]
        program[h] = _table_char(h, label, labels)
    return _render(program, words)


def _digits_program(truth_table: str, n: int) -> str:
    return _render_build(truth_table, _digits(n))


def _ignored_bit(truth_table: str) -> int | None:
    """Return the lowest input bit ``truth_table`` ignores, or ``None``.

    Bit 0 is the last input (the table is MSB first).  A table ignores
    bit ``b`` when every block of ``2**b`` rows is followed by its twin:
    the bit's two halves of each ``2**(b + 1)``-row block agree.
    """
    size = len(truth_table)
    for bit in range(size.bit_length() - 1):
        step = 1 << bit
        if all(
            truth_table[i : i + step] == truth_table[i + step : i + 2 * step]
            for i in range(0, size, 2 * step)
        ):
            return bit
    return None


def _project(truth_table: str, bit: int) -> str:
    """Return the table got by dropping ``bit``: each block's first half."""
    step = 1 << bit
    return "".join(
        truth_table[i : i + step] for i in range(0, len(truth_table), 2 * step)
    )


def _seventeen_program(truth_table: str) -> str | None:
    """Return a program for a seventeen-input table ignoring an input.

    The projection's sixteen build computes the table, once the stream
    is aligned: dropping the last input is that build unchanged, and
    dropping stream position ``p`` (counting from 1) discards one read
    in the gadget group that would have folded position ``p``.  Returns
    ``None`` when the table uses all seventeen inputs.
    """
    bit = _ignored_bit(truth_table)
    if bit is None:
        return None
    projected = _project(truth_table, bit)
    if bit == 0:
        return _digits_program(projected, _DIGITS_N)
    position = _DIGITS_N + 1 - bit
    if position == _DIGITS_N:
        drop = (_D_GROUPS - 1, _DROP_TOKEN[4])
    else:
        group, slot = divmod(position - 1, _READS)
        drop = (group, _DROP_TOKEN[slot + 1])
    return _render_build(projected, _digits(_DIGITS_N, drop))
