"""Hubs, stubs, label chains and the planner helpers of the digit build.

A row's table cell holds a source character ``T``; the stub does ``j`` to
the table cell, ``j`` to the pointer cell ``T + 1``, ``j`` to the *hub*
``V + 1`` the pointer names, ``i`` through the hub to the stub it holds.
``d`` is then ``V + 2`` whatever the row.  The pointer region ``34..127``
holds the labels, but they are written last: until then the working cells
dead by that point (the setup helpers and the gadget's) sit there, where
every ``j`` through an unwritten cell lands, and the rest in the walked
cells ``128..419``.  Navigation is a shortest path over ``o`` and ``j``
through every cell whose value is known.

The readouts are a product set: each two-trit digit of ``S`` misses one
value, digit 1 (trits 2, 3) missing ``(2, 2)`` and digit 3 (trits 6, 7)
``(1, 2)``.  A cell whose predecessor has such a digit is no table cell,
so hubs and stubs are placed by their trits, not by a fit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from esolangs.languages.malbolge.interpreter import _XLAT1, _crazy

from .emitter import _Planner, _valid_chars
from .isa import _ACTIVE, _ALL1, _CONSTS, _first_free, _g, _progression, _rot

_ENTRY = 420
#: ``d`` after the entry ``j`` at ``_ENTRY``: the walked cell its character names.
_START_D = 34 + (7 - _ENTRY) % 94
#: Label of the pointer cell ``T + 1`` for ``T`` in ``33..126`` (``n`` is
#: ``not x``; ``-`` is unlabelled).  A function of ``T mod 47``, so it wraps
#: cleanly mod 94: the active ops' ``_XLAT1`` offsets, scaled by 23 mod 47
#: and read mod 10, meet every label's class at every ``h``.
_T_LABELS = "".join("--0n1xn1x0"[23 * t % 47 % 10] for t in range(94))
#: Every stub reads the last input (a program consumes all ``n`` whatever
#: the table).  ``A`` arrives as ``'0'``, so ``0`` prints before it reads and
#: ``x`` after; ``1`` and ``n`` are :func:`_operand_stub`.
_T_STUBS = {"0": "</v", "x": "/<v"}
#: The labels in seed order (:func:`_seed_g`).
_T_HUB_LABELS = "n01x"
#: ``K0 K2`` sends trits 0 and 1 to 2 and 2 to 1; three rotations then put
#: the five former zeros of ``g`` at trits 2..6 and ``g``'s trits 0..2 at
#: 7..9.  With ``g``'s trit 3 at 2 and trit 4 at 0, trits 0, 1 are ``(1, 2)``,
#: so both of a label's hubs, the value and its 0/1 swap, own two cells of
#: a block no table cell enters.
_SEED_CHAIN = "K0 K2 rot rot rot"
#: ``p`` over these cells' values takes ``'0' + x`` to the answer exactly,
#: trit by trit: a ``p`` over 0 or 1 swaps trit 0's 0 and 1 and over 2
#: merges them, so ``n`` takes three swaps and ``1`` a merge; over 69..71 and
#: 59008 every other trit of 48 comes back.  59008 is ``K0 K2`` on 80 (four
#: 2-trits); the others are unwritten walked cells, the nearest of their
#: ``g`` either side of the first walked 80.
_OPERAND_G = {"1": (71, 80, 71), "n": (70, 80, 69)}
_OPERAND_CHAIN = "K0 K2"
#: Stub address chains.  ``rot K2`` on ``g`` = 108 + 3 + ``g0`` (trits ``g0``,
#: 1, 0, 1, 1) is ``(2, 0, 2, 2, 0, .., 0, s)`` with ``s`` 2 or 1: it and its
#: 0/1 swap start three-cell stubs in clear nine-cell blocks, so one chain
#: serves both hubs of ``0`` (``g0`` 1) or ``x`` (2).  ``rot`` three times on
#: ``g`` = 83 + 3 * ``k`` (trits 2, ``k`` in base 3, 0, 0, 1) swaps to 361
#: cells into the 729-cell run of trits 6, 7 = ``(1, 2)`` that trits 1, 2
#: pick, room for an operand stub; each ``1`` and ``n`` hub takes its own.
_SHORT_STUB_G = {"0": 112, "x": 113}
_SHORT_STUB_CHAIN = "rot K2"
_LONG_STUB_G = {"1": (83, 86), "n": (89, 92)}
_LONG_STUB_CHAIN = "rot rot rot"
#: Fresh all-1 and all-2 cells just past the pointer region, for the paths.
_T_LOW = (128, 129)
#: ``g`` values of the constant-building cells; only ``z0`` (``K0``) is read
#: after the setup.
_T_HELPERS = {"z1": 40, "z0": 37, "w": 80, "v": 78}
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


def _table_char(h: int, label: str, labels: dict[int, str]) -> int:
    """Return the source character at ``h`` that points at a ``label`` cell."""
    for op in _ACTIVE:
        t = 33 + (_XLAT1.index(op) - h) % 94
        if labels.get(t) == label:
            return t
    raise AssertionError(f"no {label} character at {h}")  # pragma: no cover


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
) -> None:
    """Run each label's seed chain, then ``p`` every pointer cell of that label.

    ``chains[lab]`` is the op string :func:`_emit_chain` runs on
    ``seeds[lab]``; a class's pointer cells then alternate that value and
    its 0/1 swap.
    """
    for lab, chain in chains.items():
        _emit_chain(main, seeds[lab], chain, helper)
        for p in sorted(label):
            if label[p] == lab:
                main.op("p", p)


def _t_jump(path: _Planner, readout: int) -> None:
    """``j`` to the table cell, ``j`` to its pointer, ``j`` to the hub, ``i``."""
    path.op("j", readout)
    path.raw("j")
    path.raw("j")
    path.raw("i")


def _walker(used: set[int], lo: int = 128, hi: int = _ENTRY) -> Callable[..., int]:
    """Return an allocator of the least unused cell in ``lo..hi``.

    ``value`` asks for that ``g`` value; without one any cell will do.
    """

    def walked(value: int | None = None) -> int:
        if value is None:
            address = next(a for a in range(lo, hi) if a not in used)
        else:
            address = _first_free(value, lo, hi, used)
        used.add(address)
        return address

    return walked


def _pointers(
    label: dict[int, str], starts: Iterable[tuple[str, int]]
) -> tuple[dict[int, int], dict[int, int]]:
    """Return each label cell's pointer value and the first cell per value.

    ``starts`` gives each label's first chain value in order; a label's cells
    then alternate it and its 0/1 swap, one ``p`` over all-1 each.
    """
    values: dict[int, int] = {}
    for lab, a in starts:
        for p in sorted(label):
            if label[p] == lab:
                a = _crazy(a, _ALL1)
                values[p] = a
    pointer: dict[int, int] = {}
    for p in sorted(values):
        pointer.setdefault(values[p], p)
    return values, pointer


def _s01(value: int) -> int:
    """Return ``value`` with its 0 and 1 trits swapped: ``p`` over all-1."""
    return _crazy(value, _ALL1)


def _seed_g(m: int) -> int:
    """Return the ``m``-th label's seed ``g`` (:data:`_SEED_CHAIN`).

    Trits 0..2 are 2 where ``m``'s bits are 1.  ``m`` in 1..6 sets some but
    not all, so no label's hubs reach the top block or fall below 6561.
    """
    return 54 + sum(two for k, two in enumerate((2, 6, 18)) if m >> k & 1)


def _operand_cells() -> dict[str, tuple[int, ...]]:
    """Return the cells each operand stub ``p``s over, in address order."""
    middle = _progression(80, 128, _ENTRY)[0]
    return {
        lab: (
            _progression(below, 128, middle)[-1],
            middle,
            _progression(above, middle + 1, _ENTRY)[0],
        )
        for lab, (below, _, above) in _OPERAND_G.items()
    }


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


def _stub_builds(hubs: dict[str, tuple[int, ...]]) -> list[_Build]:
    """Return each stub-address build: ``g``, chain, and the hubs it writes.

    The chain value ``C`` leaves ``A = C``; the build's hubs, primed to
    all-1, then take ``s01(C)``, ``C``, ... in turn.
    """
    builds = [(g, _SHORT_STUB_CHAIN, hubs[lab]) for lab, g in _SHORT_STUB_G.items()]
    for lab, gs in _LONG_STUB_G.items():
        pairs = zip(gs, hubs[lab], strict=True)
        builds += [(g, _LONG_STUB_CHAIN, (v,)) for g, v in pairs]
    return builds


def _hub_layout(
    hubs: dict[str, tuple[int, ...]], avoid: set[int], floor: int
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
    for g, chain, vs in _stub_builds(hubs):
        address = _chain(g, chain)
        for v in vs:
            address = _s01(address)
            lab = hub_label[v]
            data[v + 2] = min(_valid_chars(v + 2))
            stub = _T_STUBS.get(lab) or _operand_stub(data[v + 2] + 1, operands[lab])
            stubs.update({address + 1 + i: op for i, op in enumerate(stub)})
            reserved += [v + 1, v + 2, *range(address, address + 1 + len(stub))]
    if len(set(reserved)) != len(reserved) or set(reserved) & avoid:
        raise AssertionError("a hub or stub collides")
    if min(reserved) < floor:
        raise AssertionError("a hub or stub sits below the floor")
    return data, stubs


def _write_hubs(
    main: _Planner,
    helper: dict[str, int],
    pointer: dict[int, int],
    builds: list[_Build],
    builders: list[int],
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
        _emit_chain(main, cell, chain, helper)
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
    parts: Iterable[dict[int, str]],
    data: dict[int, int],
    tables: set[int],
    code_end: int,
    ceiling: int | None = None,
) -> dict[int, str]:
    """Return ``parts`` laid over ``o``; raises on any collision.

    No part may overlap another or ``data``, and no table cell may sit on
    code or data or at or below ``code_end``; ``ceiling`` caps ``code_end``.
    """
    code = dict.fromkeys(range(_ENTRY), "o")
    for part in parts:
        if set(part) & set(code):
            raise AssertionError(f"code overlaps at {min(set(part) & set(code))}")
        code.update(part)
    if set(data) & set(code):
        raise AssertionError("a data cell overlaps code")
    hits = tables & (set(code) | set(data))
    if hits or min(tables) <= code_end or (ceiling is not None and code_end >= ceiling):
        raise AssertionError("a table cell collides with code")
    return code
