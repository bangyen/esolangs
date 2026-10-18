"""Hub placement and planner helpers the builds from thirteen inputs up share."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from esolangs.languages.malbolge.interpreter import _crazy

from .cascade import _ENTRY, _START_D
from .emitter import _Planner, _valid_chars
from .isa import _ALL1, _CONSTS, _WORDS, _first_free, _g, _rot

# ---------------------------------------------------------------------------
# Shared by the builds from thirteen inputs up: hub placement and the
# helpers that drive the shared shortest-path planner (see emitter.py).

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
#: Stubs and hubs stay above the main code.
_T_FLOOR = 12000
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


def _rotations(char: int) -> list[tuple[int, int]]:
    out = []
    value = char
    for k in range(1, 10):
        value = _rot(value)
        out.append((k, value))
    return out


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


def _t_jump(path: _Planner, readout: int, offset: int) -> None:
    """``j`` to the table cell, ``j`` to its pointer, ``j`` to the hub, ``i``."""
    path.op("j", readout)
    for _ in range(offset):
        path.raw("o")
    path.raw("j")
    path.raw("j")
    path.raw("i")


def _one_options(v: int) -> list[dict[int, int]]:
    """Return the character pairs after a ``1`` hub at ``v`` that give ``'1'``."""
    return [
        {v + 2: a, v + 3: b}
        for a in _valid_chars(v + 2)
        for b in _valid_chars(v + 3)
        if _crazy(_crazy(48, a), b) & 0xFF == ord("1")
    ]


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


def _options_of(operand: dict[int, int]) -> Callable[[int, str], list[dict[int, int]]]:
    """Return the ``options_of`` of :func:`_t_hubs`: ``1`` and ``n`` hubs read data."""

    def options_of(v: int, lab: str) -> list[dict[int, int]]:
        if lab == "1":
            return _one_options(v)
        return _n_options(v, operand) if lab == "n" else [{}]

    return options_of


def _walker(used: set[int], layout: dict[int, int] | None = None) -> Callable[..., int]:
    """Return an allocator of unused walked cells (``128..``) by ``g`` value.

    ``layout`` maps the allocation index to a preferred address, taken when
    free and of the right ``g`` value.
    """
    count = [0]

    def walked(value: int | None = None) -> int:
        key = count[0]
        count[0] += 1
        preferred = (layout or {}).get(key)
        if (
            preferred is not None
            and 128 <= preferred < _ENTRY
            and preferred not in used
            and (value is None or _g(preferred) == value)
        ):
            address = preferred
        else:
            # A no-value call always takes its layout cell above: the only
            # ones are the digit build's ``s``/``z``, whose cells are free.
            assert value is not None
            address = _first_free(value, 128, _ENTRY, used)
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


@dataclass(frozen=True)
class _HubRequest:
    """One hub placement's policy, bundled: what :func:`_t_hubs` searches with.

    ``hub_cells`` gives, per label, how many cells past a hub are reserved
    or exactly which offsets are; ``options_of(v, label)`` the data cells a
    hub's stub reads, tried in order.  A stub lands in ``floor <= s <
    ceiling`` and a hub at or above ``hub_floor``.
    """

    hub_cells: dict[str, int | tuple[int, ...]]
    options_of: Callable[[int, str], list[dict[int, int]]]
    floor: int
    ceiling: int = _WORDS
    hub_floor: int = 0


def _t_hubs(
    values: dict[int, int],
    label: dict[int, str],
    avoid: set[int],
    request: _HubRequest,
) -> tuple[dict[int, int], dict[int, str], dict[int, int]]:
    """Return hub and data characters, stub code and rotations per hub."""
    hubs = {values[p]: label[p] for p in sorted(values)}
    reserved: set[int] = set()
    for v, lab in sorted(hubs.items()):
        span = request.hub_cells[lab]
        cells = (
            set(range(v + 1, v + 1 + span))
            if isinstance(span, int)
            else {v + o for o in span}
        )
        if v < request.hub_floor or cells & (avoid | reserved):
            raise AssertionError(f"hub {v} collides")
        reserved |= cells
    data: dict[int, int] = {}
    stubs: dict[int, str] = {}
    turns: dict[int, int] = {}
    for v, lab in sorted(hubs.items()):
        if lab == "N":
            continue
        placed = next(
            (
                (option, char, k, s)
                for option in request.options_of(v, lab)
                for char in _valid_chars(v + 1)
                for k, s in _rotations(char)
                if request.floor <= s < request.ceiling
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


def _prime(main: _Planner, helper: dict[str, int], cells: Iterable[int]) -> None:
    """Send each of ``cells`` to all-1 (``p`` twice), then ``A = all-2`` via ``w``."""
    for p in cells:
        main.op("p", p)
        main.op("p", p)
    main.op("*", helper["w"])
    main.op("p", helper["all2"])


def _turn_hubs(
    main: _Planner, pointer: dict[int, int], hub_turns: dict[int, int]
) -> None:
    """Turn each hub ``V`` its ``hub_turns[V]`` times, in ``V`` order."""
    for v, turns in sorted(hub_turns.items()):
        for _ in range(turns):
            main.hub(pointer[v], v)
            main.raw("*")


def _n_hub_pass(main: _Planner, pointer: int, v: int) -> None:
    """First pass over an ``N`` hub: all-1 written twice, then at ``V + 2``."""
    main.hub(pointer, v)
    main.raw("p")
    main.hub(pointer, v)
    main.raw("p")
    main.raw("p")
    main.hub(pointer, v, 2)
    main.raw("p")


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
