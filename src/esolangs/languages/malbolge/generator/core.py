"""Hubs, stubs, label chains and the planner helpers of the digit build.

A row's table cell holds a source character ``T``; the stub does ``j`` to
the table cell, ``j`` to the pointer cell ``T + 1``, ``j`` to the *hub*
``V + 1`` the pointer names, ``i`` through the hub to the stub it holds.
``d`` is then ``V + 2`` whatever the row.  The pointer region ``34..127``
holds the labels, but they are written last: until then the working cells
dead by that point (the setup helpers and the gadget's) sit there, where
every ``j`` through an unwritten cell lands, and the rest in the walked
cells ``128..281``. Navigation uses the indexed landing intervals
in :mod:`.emitter`.

The readouts are a product set: each two-trit digit of ``S`` misses one
value, digit 1 (trits 2, 3) missing ``(2, 2)`` and digit 3 (trits 6, 7)
``(1, 2)``.  A cell whose predecessor has such a digit is no table cell,
so hubs and stubs are placed by their trits, not by a fit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from esolangs.languages.malbolge.interpreter import _XLAT1, _crazy

from .emitter import _Planner, _valid_chars
from .isa import (
    _ACTIVE,
    _ALL1,
    _ALL2,
    _CONSTS,
    _ONE_OPERAND,
    _ROTATE,
    _WORD_TRITS,
    _WORDS,
    _ZERO_OPERAND,
    _char_for,
    _first_free,
    _g,
    _program,
    _progression,
    _render,
    _rot,
)

_ENCODING_PERIOD = len(_XLAT1)
#: The labels in seed order (:func:`_seed_g`).
_T_HUB_LABELS = "n01x"
# Repeat over two equal halves of the encoding period. In each half,
# four pointer cells advance the label coordinate by one.
_LABEL_PERIOD = _ENCODING_PERIOD // 2
_LABEL_STEP = pow(len(_T_HUB_LABELS), -1, _LABEL_PERIOD)
_LABEL_CYCLE = "-" + _T_HUB_LABELS
_T_LABELS = "".join(
    _LABEL_CYCLE[_LABEL_STEP * t % _LABEL_PERIOD % len(_LABEL_CYCLE)]
    for t in range(_ENCODING_PERIOD)
)
#: Every stub reads the last input (a program consumes all ``n`` whatever
#: the table) and prints only after it.  ``x`` prints the character read;
#: ``0``, ``1`` and ``n`` are :func:`_operand_stub`.
_T_STUBS = {"x": "/<v"}
#: ``K0 K2`` sends trits 0 and 1 to 2 and 2 to 1; three rotations then put
#: the five former zeros of ``g`` at trits 2..6 and ``g``'s trits 0..2 at
#: 7..9.  With ``g``'s trit 3 at 2 and trit 4 at 0, trits 0, 1 are ``(1, 2)``,
#: so both of a label's hubs, the value and its 0/1 swap, own two cells of
#: a block no table cell enters.
_SEED_CHAIN = "K0 K2 rot rot rot"
# The hub and its return byte fit below the first fixed all-2 digit.
_HUB_LOW_TRITS = 2
# Fill the word from three adjacent blocks. Put the remainder in the
# low block, and shift the reusable seed one trit up so its first
# rotation run lands it at the high end.
_BOOTSTRAP_BLOCK_TRITS, _BOOTSTRAP_REMAINDER = divmod(_WORD_TRITS, 3)
_BOOTSTRAP_LOW_TRITS = _BOOTSTRAP_BLOCK_TRITS + _BOOTSTRAP_REMAINDER
_BOOTSTRAP_W = 3**_BOOTSTRAP_LOW_TRITS - 1
_BOOTSTRAP_V = 3 * (3**_BOOTSTRAP_BLOCK_TRITS - 1)
_BOOTSTRAP_Z1 = _BOOTSTRAP_W // 2
# Distinguish the two binary-trit seeds by clearing the lowest
# non-unit trit. The constant-building operations accept either bit.
_BOOTSTRAP_Z0 = _BOOTSTRAP_Z1 - 3
# Use the ASCII inverse's upper trits to preserve the input's upper
# trits across the middle operand. At the units trit, 2 merges both
# inputs to 2, then the middle unit 1 keeps 2 and the final 2 makes 1.
# For negation all three units are binary and each flips the input.
# Place unit 1 before the middle and unit 0 after it.
_OPERAND_G = {
    "1": (_ONE_OPERAND, _ONE_OPERAND),
    "n": (_ZERO_OPERAND + 1, _ZERO_OPERAND),
}
_OPERAND_CHAIN = "K0 K2"
# A half-word rotation maps the lane number straight to its base address.
_LANE_TRITS = _WORD_TRITS // 2
_LANE_WIDTH = 3**_LANE_TRITS
_LANE_CHAIN = " ".join(["rot"] * _LANE_TRITS)
# The missing digit (trits 6, 7) gives one 3**6-cell gap per top digit.
_STUB_GAP_DIGIT = 1 + 2 * 3
_STUB_GAP_WIDTH = 3**6
# A printable jump lands at most at 127. The constants take the first
# two walked cells immediately above that region.
_WALKED_START = 128
_T_LOW = (_WALKED_START, _WALKED_START + 1)
# The bridge in top band 7 and the lower n operand both need g = 70.
# Walk through the second occurrence, then align the reset to a period.
_SHARED_BRIDGE_SEED = 7 * 3**2 + _STUB_GAP_DIGIT
_LAST_REQUIRED = _progression(
    _SHARED_BRIDGE_SEED, _WALKED_START, _WALKED_START + 2 * _ENCODING_PERIOD
)[1]
_ENTRY = (_LAST_REQUIRED // _ENCODING_PERIOD + 1) * _ENCODING_PERIOD
_START_D = _char_for("j", _ENTRY) + 1
#: ``g`` values of the constant-building cells; only ``z0`` (``K0``) is read
#: after the setup.
_T_HELPERS = {
    "z1": _BOOTSTRAP_Z1,
    "z0": _BOOTSTRAP_Z0,
    "w": _BOOTSTRAP_W,
    "v": _BOOTSTRAP_V,
}
#: The helper cell each chain constant (0, all-1, all-2) names.
_K_CELL = {"K0": "z0", "K1": "all1", "K2": "all2"}
_CHAIN_A = dict(zip(_K_CELL, _CONSTS, strict=True))
#: The label each pair of table entries (``f(x=0), f(x=1)``) reads as.
_ANSWER = {"00": "0", "11": "1", "01": "x", "10": "n"}


def _main_planner(data: dict[int, int]) -> tuple[_Planner, dict[int, int | None]]:
    """Return the main-code planner (entry ``j`` placed) and its walked memory."""
    mem: dict[int, int | None] = {a: _g(a) for a in range(_ENTRY)}
    # ``A`` is 0 when the entry ``j`` runs: the initial walk is all nops.
    main = _Planner(_ENTRY + 1, _START_D, mem, data, ceiling=_ENTRY, a=0)
    main.code[_ENTRY] = "j"
    return main, mem


def _build_constants(main: _Planner, helper: dict[str, int]) -> None:
    """Run the op chain the build opens with.

    ``A`` starts at 0, so a ``{0,1}``-trit cell becomes all-1 and the next
    one 0. Two rotation runs fill the middle and high blocks of all-2.
    The closing ``*`` leaves ``A`` at all-1, from which ``p`` twice maps any
    walked value to all-1.
    """
    main.op("p", helper["z1"])
    main.op("p", helper["z0"])
    main.op("p", helper["w"])
    for _ in range(_BOOTSTRAP_LOW_TRITS):
        main.op("*", helper["v"])
    main.op("p", helper["w"])
    for _ in range(_BOOTSTRAP_BLOCK_TRITS):
        main.op("*", helper["v"])
    main.op("p", helper["w"])
    main.op("*", helper["z1"])


_SOURCE_MASK = sum(1 << _XLAT1.index(op) for op in _ACTIVE)
_LABEL_MASKS = {
    label: sum(1 << i for i, x in enumerate(_T_LABELS) if x == label)
    for label in "01xn"
}


def _table_char(h: int, label: str) -> int:
    """Rotate the label mask into instruction coordinates and take its low bit."""
    shift = h % 94
    mask = _LABEL_MASKS[label]
    valid = ((mask << shift) | (mask >> (94 - shift))) & _SOURCE_MASK
    if not valid:
        raise AssertionError(f"no {label} character at {h}")
    offset = (valid & -valid).bit_length() - 1
    return 33 + (offset - shift) % 94


def _render_answers(
    code: dict[int, str],
    data: dict[int, int],
    answers: Iterable[tuple[int, str]],
    words: int = _WORDS,
) -> str:
    """Fill the template's cells with glyphs for pairs of output bits."""
    program = _program(code)
    program.update(data)
    for cell, pair in answers:
        program[cell] = _table_char(cell, _ANSWER[pair])
    return _render(program, words)


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
            path.op("*", helper[_K_CELL[op]])
            path.op("p", target)


def _seed_label_chains(
    main: _Planner,
    helper: dict[str, int],
    chains: dict[str, str],
    seeds: dict[str, int],
    label: dict[int, str],
    *,
    single: bool = False,
) -> None:
    """Run each label's seed chain, then ``p`` every pointer cell of that label.

    ``chains[lab]`` is the op string :func:`_emit_chain` runs on
    ``seeds[lab]``; a class's pointer cells then alternate that value and
    its 0/1 swap.  ``single`` re-swaps every second cell (``A = all-1``,
    ``p``), so the whole class holds the first value and needs one hub.
    """
    for lab, chain in chains.items():
        _emit_chain(main, seeds[lab], chain, helper)
        cells = [p for p in sorted(label) if label[p] == lab]
        for p in cells:
            main.op("p", p)
        for p in cells[1::2] if single else ():
            main.op("*", helper["all1"])
            main.op("p", p)


def _walker(used: set[int], lo: int = 128, hi: int = _ENTRY) -> Callable[..., int]:
    """Return an allocator of the least unused cell in ``lo..hi``.

    ``value`` asks for that ``g`` value; without one any cell will do.
    """

    def walked(value: int | None = None) -> int:
        address = _first_free(value, lo, hi, used)
        used.add(address)
        return address

    return walked


def _pointers(
    label: dict[int, str], starts: Iterable[tuple[str, int]], *, single: bool = False
) -> tuple[dict[int, int], dict[int, int]]:
    """Return each label cell's pointer value and the first cell per value.

    ``starts`` gives each label's first chain value in order; a label's cells
    then alternate it and its 0/1 swap, one ``p`` over all-1 each (``single``:
    all hold the first).
    """
    values: dict[int, int] = {}
    for lab, start in starts:
        a = start
        first = _crazy(a, _ALL1)
        for p in sorted(label):
            if label[p] == lab:
                a = _crazy(a, _ALL1)
                values[p] = first if single else a
    pointer: dict[int, int] = {}
    for p in sorted(values):
        pointer.setdefault(values[p], p)
    return values, pointer


def _s01(value: int) -> int:
    """Return ``value`` with its 0 and 1 trits swapped: ``p`` over all-1."""
    return _crazy(value, _ALL1)


def _identity_stub_seed() -> int:
    """Invert the chain for the identity stub at the end of a hub-sized block."""
    block = 3**_HUB_LOW_TRITS
    # Use the first nonzero top digit. Printable seeds have zero high
    # trits, which become ones after the hub swap. The all-2 hub digit
    # clears this block, and the final three cells hold the stub.
    upper = (_ALL1 % _ROTATE) // block**2
    base = (upper * block + block - 1) * block + block - 1 - len(_T_STUBS["x"])
    rotated = _crazy(_ALL2, _s01(base))
    return 3 * (rotated % _ROTATE) + rotated // _ROTATE


_IDENTITY_STUB = _identity_stub_seed(), "rot K2"


def _seed_g(m: int) -> int:
    """Return the ``m``-th label's seed ``g`` (:data:`_SEED_CHAIN`).

    Trits 0..2 are 2 where ``m``'s bits are 1.  ``m`` in 1..6 sets some but
    not all, so no label's hubs reach the top block or fall below 6561.
    """
    return 54 + sum(two for k, two in enumerate((2, 6, 18)) if m >> k & 1)


def _operand_cells() -> dict[str, tuple[int, ...]]:
    """Return the cells each operand stub ``p``s over, in address order."""
    middle = _progression(_BOOTSTRAP_W, _WALKED_START, _ENTRY)[0]
    cells = {
        lab: (
            _progression(below, 128, middle)[-1],
            middle,
            _progression(above, middle + 1, _ENTRY)[0],
        )
        for lab, (below, above) in _OPERAND_G.items()
    }
    # ``p`` over 1's last and n's last cell sends '0' and '1' alike to '0'.
    return {"0": (cells["1"][2], cells["n"][2]), **cells}


def _operand_stub(landing: int, cells: Iterable[int]) -> str:
    """Return a ``1`` or ``n`` stub: ``j`` to ``landing``, read, ``p`` over ``cells``.

    The ``j`` runs at ``V + 2``, whose character names ``landing``.
    """
    ops, d = ["j/"], landing + 1
    for cell in cells:
        ops.append("o" * (cell - d) + "p")
        d = cell + 1
    return "".join(ops) + "<v"


type _Build = tuple[int, str, tuple[int, ...]]


def _stub_builds(
    hubs: dict[str, tuple[int, ...]], stubs: dict[str, tuple[int, str]]
) -> list[_Build]:
    """Return each stub's seed, chain and hub in layout order."""
    return [(g, chain, hubs[lab]) for lab, (g, chain) in stubs.items()]


def _hub_layout(
    hubs: dict[str, tuple[int, ...]],
    avoid: set[int],
    floor: int,
    builds: list[_Build],
    *,
    packed: bool = False,
    claimed: set[int],
) -> tuple[dict[int, int], dict[int, str]]:
    """Return the hubs' ``j`` characters and the stub code, by label's hubs.

    Raises if a hub or stub cell meets a table cell, another hub's or
    stub's, or falls below ``floor``.
    """
    hub_label = {v: lab for lab, vs in hubs.items() for v in vs}
    operands = _operand_cells()
    data: dict[int, int] = {}
    stubs: dict[int, str] = {}
    reserved: list[int] = []
    for g, chain, vs in builds:
        address = _chain(g, chain)
        for v in vs:
            if not packed or chain != _LANE_CHAIN:
                address = _s01(address)
            lab = hub_label[v]
            data[v + 2] = (max if packed else min)(_valid_chars(v + 2))
            stub = _T_STUBS.get(lab) or _operand_stub(data[v + 2] + 1, operands[lab])
            stubs.update(enumerate(stub, address + 1))
            reserved += [v + 1, v + 2, *range(address, address + 1 + len(stub))]
    if len(set(reserved)) != len(reserved) or set(reserved) & avoid:
        raise AssertionError("a hub or stub collides")
    if min(reserved) < floor:
        raise AssertionError("a hub or stub sits below the floor")
    claimed.update(reserved)
    return data, stubs


def _write_hubs(
    main: _Planner,
    helper: dict[str, int],
    pointer: dict[int, int],
    builds: list[_Build],
    builders: list[int],
    swap_cell: int | None = None,
) -> None:
    """Prime every hub cell to all-1, then run each build and write its hubs.

    ``builders[k]`` is the walked cell build ``k``'s chain runs on.
    """
    main.op("*", helper["all1"])
    for v in sorted(v for _, _, vs in builds for v in vs):
        for _ in range(2):
            main.hub(pointer[v], v)
            main.raw("p")
    for (_, chain, vs), cell in zip(builds, builders, strict=True):
        swap = swap_cell is not None and chain == _LANE_CHAIN
        if swap and swap_cell is not None:
            main.op("*", helper["all1"])
            main.op("p", swap_cell)
            main.op("p", swap_cell)
        _emit_chain(main, cell, chain, helper)
        if swap and swap_cell is not None:
            main.op("p", swap_cell)
        for v in vs:
            main.hub(pointer[v], v)
            main.raw("p")


def _prime(main: _Planner, helper: dict[str, int], cells: Iterable[int]) -> None:
    """Send each of ``cells`` to all-1 (``p`` twice), then ``A = all-2`` via ``w``."""
    for p in cells:
        main.op("p", p)
        main.op("p", p)
    main.op("*", helper["w"])
    main.op("p", helper["all2"])


def _merge_code(
    main: dict[int, str],
    stubs: dict[int, str],
    data: dict[int, int],
    tables: set[int],
    claimed: set[int],
) -> dict[int, str]:
    """Combine the code only after checking every occupied address."""
    code = dict.fromkeys(range(_ENTRY), "o") | main
    if code.keys() & claimed:
        raise AssertionError("a main instruction overlaps a hub or stub")
    code.update(stubs)
    if data.keys() & code.keys():
        raise AssertionError("a data cell overlaps code")
    if tables & (code.keys() | data.keys()):
        raise AssertionError("a table cell collides with code")
    return code
