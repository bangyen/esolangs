"""The planner and hub placement the builds from thirteen inputs up share."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from esolangs.languages.malbolge.interpreter import _crazy

from .cascade import _ENTRY, _START_D
from .isa import _ACTIVE, _ALL1, _CONSTS, _WORDS, _char_for, _g, _rot

# ---------------------------------------------------------------------------
# Shared by the builds from thirteen inputs up: a planner that navigates by
# shortest path, and hub placement.

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


def _valid_chars(address: int) -> list[int]:
    return [_char_for(op, address) for op in _ACTIVE]


class _Planner:
    """Code emitter that navigates by shortest path over ``o`` and ``j``.

    ``mem`` maps walked addresses to their known values (``None`` once
    written to an unknown value); ``a`` is the accumulator ``A`` when the ops
    so far have determined it, else ``None``; ``data`` maps store addresses
    above the code to source characters, which a ``j`` from there reads to
    come back below 128.  Knowing ``mem``/``a`` is only an optimisation: a
    cell whose value is still known stays usable as a ``j`` target, so the
    shortest-path search sees the shortcuts the run-time pointers provide.
    """

    def __init__(
        self,
        start: int,
        d: int,
        mem: dict[int, int | None],
        data: dict[int, int],
        a: int | None = None,
    ) -> None:
        self.code: dict[int, str] = {}
        self.c = start
        self.d = d
        self.mem = mem
        self.data = data
        self.a = a

    def raw(self, op: str) -> None:
        cell = self.d
        self.code[self.c] = op
        self.c += 1
        self.d += 1
        if op in "p*":
            self.mem[cell] = self._written(op, cell)
        elif op == "/":
            self.a = None

    def _written(self, op: str, cell: int) -> int | None:
        """Return the new value of ``cell`` after ``op``, or ``None`` if unknown."""
        old = self.mem.get(cell)
        if op == "*":
            if isinstance(old, int):
                self.a = _rot(old)
            else:
                self.a = None
        elif isinstance(old, int) and isinstance(self.a, int):
            self.a = _crazy(self.a, old)
        else:
            self.a = None
        return self.a

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

    def hub(self, pointer: int, value: int, offset: int = 1) -> None:
        """``j`` through ``pointer`` (holding ``value``) to ``value + offset``."""
        self.goto(pointer)
        self.raw("j")
        self.d = value + 1
        while self.d < value + offset:
            self.raw("o")


def _main_planner(data: dict[int, int]) -> tuple[_Planner, dict[int, int | None]]:
    """Return the main-code planner (entry ``j`` placed) and its walked memory."""
    mem: dict[int, int | None] = {a: _g(a) for a in range(_ENTRY)}
    # ``A`` is 0 when the entry ``j`` runs: the initial walk is all nops.
    main = _Planner(_ENTRY + 1, _START_D, mem, data, a=0)
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
        candidates = [
            a
            for a in range(128, _ENTRY)
            if a not in used and (value is None or _g(a) == value)
        ]
        preferred = (layout or {}).get(key)
        address = preferred if preferred in candidates else candidates[0]
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


def _t_hubs(
    values: dict[int, int],
    label: dict[int, str],
    avoid: set[int],
    *,
    hub_cells: dict[str, int | tuple[int, ...]],
    options_of: Callable[[int, str], list[dict[int, int]]],
    floor: int,
    ceiling: int = _WORDS,
    hub_floor: int = 0,
) -> tuple[dict[int, int], dict[int, str], dict[int, int]]:
    """Return hub and data characters, stub code and rotations per hub.

    ``hub_cells`` gives, per label, how many cells past a hub are reserved
    or exactly which offsets are; ``options_of(v, label)`` the data cells a
    hub's stub reads, tried in order.  A stub lands in ``floor <= s <
    ceiling`` and a hub at or above ``hub_floor``.
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
        if v < hub_floor or cells & (avoid | reserved):
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
                for option in options_of(v, lab)
                for char in _valid_chars(v + 1)
                for k, s in _rotations(char)
                if floor <= s < ceiling
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
