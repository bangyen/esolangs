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
6561..59039, and no cell wraps past 59048. Continuation pages use missing digit blocks.

Up to fifteen inputs the last group's held reads are chosen so the tables
pack low (``'1','0','1'`` to thirteen: 6562..13113; fourteen ``'1','0'``:
..19674; fifteen ``'0'``: 19684..52479), and each label has one hub and a
stub in the gaps or just past the tables (:func:`_short_layout`): the source
ends at its highest live cell, including any continuation page.

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

from collections.abc import Callable, Iterator
from functools import cache
from typing import NamedTuple

from esolangs.generation.helpers import read_at
from esolangs.languages.malbolge.descriptor import _DIGITS_N as _DIGITS_N
from esolangs.languages.malbolge.interpreter import _crazy

from .core import (
    _ANSWER,
    _K_CELL,
    _LANE_CHAIN,
    _OPERAND_CHAIN,
    _SEED_CHAIN,
    _T_HELPERS,
    _T_HUB_LABELS,
    _T_LABELS,
    _T_LOW,
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
from .emitter import _Page, _Planner, _valid_chars
from .isa import (
    _CONSTS,
    _WORDS,
    _printable_slot,
    _program,
    _render,
    _rot,
)

#: The largest input count the generator builds: fifteen positional reads
#: and the last input read by the stub.
#: Reads per gadget group.
_READS = 3
#: The ``_GADGET`` token index before which a discarded read drops a
#: group's slot (1-based): the read lands where the next read or constant
#: overwrites ``A``, so the gadget's cells never see the ignored input.
#: Slot 4 is the read past the group -- the next group's first slot, or
#: the stub's own input when the last group drops it.
_DROP_TOKEN = {1: 0, 2: 2, 3: 4, 4: 13}


def _digit_gadget() -> tuple[str, ...]:
    """Factor the two output trits into accumulator operations."""
    x_cell, y_cell, z_cell = "0", "1", "2"
    # At trit 0 the prefix leaves X = 2(1-x), Y = 2(1-y), Z = 1-z,
    # with A = Z. Here C(a, b) is crazy modulo 3.
    prefix = ("/", x_cell, "/", y_cell, "K2", x_cell, "K2", y_cell, "/", z_cell)
    # F = C(Z, X) = 2(1-x) + xz. Then U = C(F, Y) = 1+x-y-xyz.
    fold_u = (x_cell, y_cell)
    # Keep F in x_cell so Q = C(U, F) can recover the other digit.
    # If x=0, F=2 and U is 0 or 1, so Q=2. If x=1, F=z and
    # U is 2 for y=0, else 1-z. Thus Q=2 iff x=0 or (z=1 and y=0).
    # C(1, Q) retains 2 and maps 0 and 1 to 0. Applying C to that
    # result and Z gives 2-x for z=0 and xy for z=1.
    fold_v = (x_cell, "K1", x_cell, z_cell)
    return (*prefix, *fold_u, *fold_v)


_GADGET = _digit_gadget()

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
#: 11664..12392 or past 13113. Arities up to
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


class _Layout(NamedTuple):
    """Each label's ``(g, chain)``: its seed (hub) and its stub address."""

    seeds: dict[str, tuple[int, str]]
    stubs: dict[str, tuple[int, str]]


def _lane_mid_stub(lane: int) -> tuple[int, str]:
    """Place a stub at the midpoint of a 243-cell lane."""
    # Five rotations move the five seed trits above five zero trits.
    # The hub swap turns those zeros into the lane's midpoint.
    return _s01(lane) % 3**5, _LANE_CHAIN


def _block_mid_stub(block: int) -> tuple[int, str]:
    """Use three rotations near the middle of a free 729-cell block."""
    # The gap is the middle third of a 3**7 band. Three rotations put
    # the low three seed trits in the band's number. The other seven
    # trits are all ones after swapping, except for the seed quotient.
    # Use the largest printable quotient (4 = 11 ternary) to clear
    # the lowest two ones and leave the most room after the stub.
    band = block // 3
    prefix = 126 // 3**3
    return prefix * 3**3 + _s01(band) % 3**3, "rot rot rot"


@cache
def _short_layout(arity: int = _SHORT_N) -> _Layout:
    """Place four hubs and their stubs in the held-read layout's gaps."""
    if arity == 14:
        # K0 K2 makes 2 except at input trits set to 2, which make 0.
        # Keep n just below block 21, then vary the low two trits of
        # the three other hubs immediately below 3**9.
        seeds = {"n": (2 + 3 + 2 * 3**2 + 2 * 3**3, "K0 K2 rot rot rot")}
        for slot, label in enumerate("01x"):
            g = 3**3 + 2 + 6 * (not slot & 1) + 18 * (not slot & 2)
            seeds[label] = g, "K0 K2 rot"
    else:
        # K0 keeps just the 2s after the hub swap. Rotate trit 0 to
        # position 8, and place the slot's two bits at positions 0, 1.
        seeds = {
            label: (
                3**3 + 3**2 + 3 + 2 + 9 * (slot & 1) + 27 * (slot >> 1),
                "K0 rot rot",
            )
            for slot, label in enumerate(_T_HUB_LABELS)
        }

    # The missing readout digit (1, 2) cuts a 729-cell gap out of
    # each top-digit band. Use the first nonzero band for shared stubs.
    missing = 1 + 2 * 3
    block = 9 + missing
    lane = 3 * block
    one = _lane_mid_stub(lane)
    negated = _block_mid_stub(block)
    # The two long stubs and the three-character identity fit at the
    # three lane centers. Reserve another lane or block for zero.
    identity = _lane_mid_stub(lane + 2)
    if arity == 15:
        # With top digits 0..2 unoccupied, the next lane is free too.
        zero, identity = identity, _lane_mid_stub(lane + 3)
    elif arity == 14:
        zero = _block_mid_stub(2 * 9 + missing)
    else:
        # The tables stop before top digit 2. Its low two trits hold
        # the hubs and their return bytes. Use the next binary mask
        # bit (trit 2) for zero. K2 K0 and the hub swap keep only seed
        # ones as twos; two rotations lift trit 0 and lower trit 4.
        hub_trits = 2
        zero = (1 + 3 ** (hub_trits + 2), "K2 K0 rot rot")
    return _Layout(seeds, {"1": one, "n": negated, "0": zero, "x": identity})


def _full_layout(*, weight_fold: bool = False) -> _Layout:
    """Pack the operand stubs in the three lanes of the first free block."""
    seeds = {label: (g, _SEED_CHAIN) for label, g in _D_SEEDS.items()}
    identity = (113, "rot K2")
    if weight_fold:
        # Rotating the readout moves a table onto the ordinary n hub.
        seeds["n"] = _seed_g(5), _SEED_CHAIN
        identity = 51, _LANE_CHAIN
    return _Layout(
        seeds,
        {
            "x": identity,
            **{label: (48 + lane, _LANE_CHAIN) for lane, label in enumerate("01n")},
        },
    )


def _longest_stub(n: int) -> int:
    """Return the commands of the longest short-layout stub at ``n`` inputs.

    A ``1`` or ``n`` stub runs every character; ``0`` and ``x`` run three.
    """
    hubs = _hubs(_short_layout(max(n, _SHORT_N)))
    cells = _operand_cells()
    return max(
        len(_operand_stub(min(_valid_chars(hubs[lab][0] + 2)) + 1, cells[lab]))
        for lab in "01n"
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
    _, s1, s2, s3 = s[:4]
    trit1 = (0, 1) if s1 == 2 else (2, 2) if s2 == 2 else (1, 2)
    if s2 == _DIGIT:
        v2 = 2
    elif s2 == 2:
        v2 = 0
    else:
        v2 = int(group != _D_SWAP_V)
    u2 = int(group != _D_SWAP_U) if s3 == _DIGIT else 2 * int(s3 != 0)
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


def _gadget_preimage(
    read: int, output: tuple[int, int], occurrence: int
) -> tuple[int, int, int]:
    """Invert the gadget on the output pairs used by the positional fold."""
    u, v = output
    if read == 1:
        if u == 1:
            # Cell 2 must be 2; cells 0 and 1 give six free choices.
            outer, inner = divmod(occurrence % 6, 3)
            return 1 - outer, 2 - inner, 2
        return 2, 2, v

    if u == 0:
        return 1, 1, 0
    if u == 1:
        return 2, 2, 2
    if v == 0:
        return 1, 2, 0
    # The two occurrences of (2, 1) swap the last two cells.
    return 2, 2 - occurrence, 1 + occurrence


@cache
def _d_inits() -> tuple[tuple[int, ...], ...]:
    """Return per group the ``g`` values of its three gadget cells.

    Trits 1..3 give :func:`_d_outputs`: the ``j``-th group to need an output
    at a read trit takes that output's ``j``-th preimage, cycling, so few
    cells share trits 1..3.  Trit 0 is 0 or 1, since a 2 lets two reads
    collide, and any such triple misses ``(2, 2)`` as the swaps need.  A
    cell's slot, the count of earlier cells sharing its trits 1..3, picks
    trit 0 and then trit 4 inside 33..126.
    """
    uses: dict[tuple[int, tuple[int, int]], int] = {}
    slots: dict[int, int] = {}
    inits = []
    for outputs in _d_outputs():
        trits = []
        for read, uv in zip(_READ_TRITS, outputs, strict=True):
            j = uses.get((read, uv), 0)
            trits.append(_gadget_preimage(read, uv, j))
            uses[read, uv] = j + 1
        group = []
        for t1, t2, t3 in zip(*trits, strict=True):
            group.append(_printable_slot(3 * t1 + 9 * t2 + 27 * t3, slots))
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
    """One arity's build: code, data, table cell per prefix, words."""

    code: dict[int, str]
    data: dict[int, int]
    tables: tuple[int, ...]
    words: int


@cache
def _digits(
    n: int, drop: tuple[int, int] | None = None, *, drain_last: bool = False
) -> _Digits:
    """Return ``(code, data, table cell per prefix, words)`` for ``n`` inputs.

    ``drop`` is a ``(group, token)`` pair naming one discarded read in
    that gadget group (the seventeen-input projection build); the
    readouts, tables and labels are sixteen's either way.  Raises if
    any code, stub, hub or data cell collides with another or with a
    table cell, or if the readouts are not distinct.
    """
    tables = _readouts_cells() if n == _DIGITS_N else tuple(s + 1 for s in _readouts(n))
    if len(set(tables)) != len(tables) or max(tables) >= _WORDS:
        raise AssertionError("readouts collide or wrap")
    short = _short(n)
    layout = _short_layout(max(n, _SHORT_N)) if short else _full_layout()
    cells = _allocate_cells(layout, drain_last=drain_last)
    _, pointer = _pointers(_D_LABEL, _seed_values(layout).items(), single=True)
    occupied = set(tables)
    claimed: set[int] = set()
    data, stubs = _hub_layout(
        _hubs(layout),
        occupied,
        _D_FLOOR,
        cells.builds,
        packed=not short,
        claimed=claimed,
    )

    main, _ = _main_planner(data)
    _emit_digit_setup(main, cells)
    if drain_last:
        # Prepare the recovery operand while the data pointer is near it.
        _emit_zero(main, cells)
    walked = _continuation_cells(cells)
    _paginate(main, cells, walked, n, min(tables), claimed | occupied)
    _emit_digit_groups(main, n, cells, drop)
    swap_cell = None if short else walked()
    _emit_digit_jump(
        main, cells, pointer, layout, drain_last=drain_last, swap_cell=swap_cell
    )
    if drain_last:
        stubs = {a: "o" if op == "/" else op for a, op in stubs.items()}
    code = _merge_code(main.code, stubs, data, occupied, claimed)
    words = max(*code, *data, *tables) + 1 if short else _WORDS
    return _Digits(code, data, tables, words)


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


def _allocate_cells(
    layout: _Layout | None = None,
    *,
    inits: tuple[tuple[int, ...], ...] | None = None,
    drain_last: bool = False,
) -> _DCells:
    """Allocate the working cells, each the least free one of its ``g`` value.

    Cells dead before the labels are written -- the setup helpers, the
    gadget's, ``s`` and ``two`` -- take pointer cells, where every ``j``
    through an unwritten cell lands, so a back jump is a short walk.  ``g``
    has period 94, so a value has one cell there.  The rest take walked
    cells ``128..``, past the operand cells.  With every cell walked the
    main line would end past the tables.
    """
    operands = _operand_cells()
    used = {*_T_LOW, *(cell for cells in operands.values() for cell in cells)}
    helper = _helper_cells(used)
    low, walked = _walker(used, 34), _walker(used)
    gadget = [
        [low(v) for v in init] for init in (_d_inits() if inits is None else inits)
    ]
    s_cell = low()
    # ``p`` under ``A = all-1`` takes 38 to 2 and keeps 2.
    two = low(38)
    # ``p`` under ``A = all-2`` swaps 69 and 48.
    if drain_last:
        to_48 = walked(69)
        # Restoring the saved byte can step straight into the readout.
        z_cell = to_48 + 1
        assert z_cell not in used
        used.add(z_cell)
    else:
        z_cell, to_48 = walked(), walked(69)
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


def _continuation_cells(cells: _DCells) -> Callable[..., int]:
    """Allocate bridge words after reserving the fold's live operands."""
    used = {
        *cells.helper.values(),
        *cells.builders,
        *cells.seeds.values(),
        cells.s_cell,
        cells.z_cell,
        cells.to_48,
        cells.to_49,
        cells.two,
        cells.operand,
        *(v for group in cells.gadget for v in group),
        *(v for group in _operand_cells().values() for v in group),
    }
    return _walker(used)


def _paginate(
    main: _Planner,
    cells: _DCells,
    walked: Callable[..., int],
    n: int,
    limit: int,
    occupied: set[int],
) -> None:
    """Put continuation pages in the held-read tail or in empty radix blocks."""
    if n == _DIGITS_N:
        # Top digits 2 through 8 have a free 729-cell block at digit 7.
        specs = [(75, 5, 3**6)] + [(9 * top + 7, 4, 3**6) for top in range(3, 9)]
    elif n in (12, 13, 14):
        specs = [(82 if n == 14 else 55, 5, 3001)]
    else:
        return
    pages = []
    for seed, rotations, width in specs:
        pointer = walked(seed)
        chain = " ".join(["rot"] * rotations)
        _emit_chain(main, pointer, chain, cells.helper)
        base = _chain(seed, chain)
        if main.mem[pointer] != base or any(
            a in occupied for a in range(base, base + width)
        ):
            raise AssertionError("continuation page collides with occupied cells")
        pages.append(_Page(pointer, base + 1, base + width))
    main.paginate(limit, pages)


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
    swap_cell: int | None = None,
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
    _write_hubs(main, helper, pointer, cells.builds, cells.builders, swap_cell)
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
    *,
    drain_last: bool = False,
    swap_cell: int | None = None,
    rotate_readout: bool = False,
) -> None:
    """Emit the finish: the readout, the labels, then the jump to the row's stub."""
    main.op("p", cells.z_cell)
    _emit_labels(main, cells, pointer, layout, swap_cell)
    if drain_last:
        # Label setup is finished with all-1. Save the essential read
        # there across the ignored byte. Stubs receive A directly.
        helper = cells.helper
        scratch = helper["all1"]
        main.op("/", scratch - 1)
        main.raw("p")
        main.op("/", helper["all2"] - 1)
        main.raw("*")
        main.op("p", scratch)
        # After the all-2 operation the low trit is 2 for zero and 0
        # for one. Crazy over ASCII 48 maps those to 0 and 1 and
        # restores the fixed upper trits of the input byte.
        main.op("p", cells.to_48)
    else:
        _emit_zero(main, cells)
    if rotate_readout:
        main.op("*", cells.z_cell)
        main.op("*", cells.z_cell)
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
    code, data, tables, words = build
    program = _program(code)
    program.update(data)
    for row, h in enumerate(tables):
        label = _ANSWER[truth_table[2 * row : 2 * row + 2]]
        program[h] = _table_char(h, label)
    return _render(program, words)


def _digits_program(truth_table: str, n: int) -> str:
    return _render_build(truth_table, _digits(n))


def _seventeen_program(truth_table: str) -> str | None:
    """Return a program for a seventeen-input table ignoring an input.

    The projection's sixteen build computes the table, once the stream
    is aligned: dropping the last input saves and restores the preceding read, and
    dropping stream position ``p`` (counting from 1) discards one read
    in the gadget group that would have folded position ``p``.  Returns
    ``None`` when the table uses all seventeen inputs.
    """
    packed = int(truth_table, 2)
    rows = (1 << len(truth_table)) - 1
    ignored_mask = 0
    for bit in range(_DIGITS_N + 1):
        half = 1 << bit
        # Dividing by 2**half + 1 leaves alternating runs of half ones.
        # Keep one XOR per pair of rows that differ only in this input.
        lower = rows // ((1 << half) + 1)
        equal = not ((packed ^ (packed >> half)) & lower)
        ignored_mask |= int(equal) << bit
    if not ignored_mask:
        return None
    # The low row-index bit is the last input in stream order.
    ignored = _DIGITS_N + 1 - (ignored_mask & -ignored_mask).bit_length()
    projected = read_at(
        truth_table, [i for i in range(_DIGITS_N + 1) if i != ignored], _DIGITS_N + 1
    )
    if ignored == _DIGITS_N:
        return _render_build(projected, _digits(_DIGITS_N, drain_last=True))
    position = ignored + 1
    if position == _DIGITS_N:
        drop = (_D_GROUPS - 1, _DROP_TOKEN[4])
    else:
        group, slot = divmod(position - 1, _READS)
        drop = (group, _DROP_TOKEN[slot + 1])
    return _render_build(projected, _digits(_DIGITS_N, drop))
