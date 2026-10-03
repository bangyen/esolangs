"""Three-input dispatch on real Malbolge sources.

Reads three inputs, folds them with the shipped one-group gadget, and jumps
through a prepared readout to one of eight destinations.  The destinations and
the hub values are written at run time (a source byte is at most 126, so a
stub cannot sit in a byte address); this is the row selector the
seventeen-input decoder needs.
"""

from __future__ import annotations

from dataclasses import dataclass

from planner import _Planner

from esolangs.interpreters.other.malbolge import (
    _advance,
    _crazy,
    _initial_memory,
    _op,
)
from esolangs.tools.malbolge import _T_HELPERS, _T_LOW, _chain, _emit_chain
from esolangs.tools.malbolge.core import (
    _ENTRY,
    _WORDS,
    _build_constants,
    _char_for,
    _g,
    _rot,
)
from esolangs.tools.malbolge.digits import (
    _D_FLOOR,
    _D_INITS,
    _GADGET,
    _K,
    _hubs,
)

_OPS = "ji*p</vo"


@dataclass(frozen=True)
class _Emission:
    """Dispatcher source, route entries, and exact code and data maps."""

    source: str
    entries: tuple[int, ...]
    code: dict[int, str]
    data: dict[int, int]


def _readouts() -> list[int]:
    """Return the eight one-group readouts, by input triple."""
    out = []
    for bits in range(8):
        reads = iter(48 + ((bits >> k) & 1) for k in (2, 1, 0))
        cells, a = list(_D_INITS[0]), 0
        for op in _GADGET:
            if op == "/":
                a = next(reads)
            elif op[0] == "K":
                a = _K[int(op[1])]
            else:
                cells[int(op)] = _crazy(a, cells[int(op)])
                a = cells[int(op)]
        u, v = cells[1], cells[2]
        following = _rot(_crazy(_rot(_crazy(v, 29524)), u))
        out.append(_crazy(following, 29524))
    return out


def emit() -> _Emission:
    """Emit the dispatcher and expose each row's executable stub entry."""
    used = {*_T_LOW}
    helper = {"all1": _T_LOW[0], "all2": _T_LOW[1]}
    for name, value in _T_HELPERS.items():
        helper[name] = _walked(used, value)
    cell = [_walked(used, v) for v in _D_INITS[0]]
    s_cell = _walked(used)
    z_cell = _walked(used)
    to_48 = _walked(used, 69)
    used.add(to_48)
    data: dict[int, int] = {}
    mem: dict[int, int | None] = {a: _g(a) for a in range(_ENTRY)}
    main = _Planner(_ENTRY + 1, 34 + (7 - _ENTRY) % 94, mem, data)
    main.code[_ENTRY] = "j"
    _build_constants(main, helper)

    readouts = _readouts()
    pointers, values, seed_specs = _choose_targets(used, readouts)
    label = dict.fromkeys(pointers, "0")
    hub_data, stubs, turns = _hubs(values, label, set())
    data.update(hub_data)
    entries = []
    for pointer in pointers:
        value = values[pointer]
        stub = data[value + 1]
        for _ in range(turns[value]):
            stub = _rot(stub)
        entry = stub + 1
        assert stubs[entry] == "<"
        assert stubs[entry + 1] == "v"
        entries.append(entry)

    for p in (helper["all1"], helper["all2"], s_cell, z_cell, *pointers):
        main.op("p", p)
        main.op("p", p)
    main.op("*", helper["w"])
    main.op("p", helper["all2"])
    for seed, ops, pointer in seed_specs:
        _emit_chain(main, seed, ops, helper)
        main.op("p", pointer)
    pointer_of = {value: p for p, value in values.items()}
    for v, count in sorted(turns.items()):
        for _ in range(count):
            main.hub(pointer_of[v], v)
            main.raw("*")

    konst = {"K0": helper["z0"], "K1": helper["all1"], "K2": helper["all2"]}
    s = s_cell
    for op in _GADGET:
        if op == "/":
            main.raw("/")
        elif op[0] == "K":
            main.op("*", konst[op])
        else:
            main.op("p", cell[int(op)])
    main.op("p", s)
    main.op("*", s)
    main.op("p", cell[1])
    main.op("*", cell[1])
    main.op("p", z_cell)
    main.op("*", helper["all2"])
    main.op("p", to_48)
    main.op("j", z_cell)
    main.raw("j")
    main.raw("j")
    main.raw("i")

    routing: dict[int, str] = {}
    for i, readout in enumerate(readouts):
        table_cell = readout + 1
        pointer = pointers[i]
        placed = None
        for op in _OPS:
            if _char_for(op, table_cell) + 1 == pointer:
                placed = op
                break
        assert placed is not None, i
        data[table_cell] = _char_for(placed, table_cell)
    for address, op in stubs.items():
        routing[address] = op

    source = [_char_for("o", a) for a in range(_WORDS)]
    for a, op in main.code.items():
        source[a] = _char_for(op, a)
    for a, op in routing.items():
        source[a] = _char_for(op, a)
    for a, ch in data.items():
        source[a] = ch
    return _Emission(
        "".join(chr(v) for v in source),
        tuple(entries),
        {**main.code, **routing},
        dict(data),
    )


def build() -> str:
    """Return the dispatcher source."""
    return emit().source


def _choose_targets(
    used: set[int], readouts: list[int]
) -> tuple[list[int], dict[int, int], list[tuple[int, str, int]]]:
    """Pick eight low pointer cells, eight hub values, and their seed chains."""
    free = set(range(34, 128)) - used
    pointers: list[int] = []
    values: dict[int, int] = {}
    seeds: list[tuple[int, str, int]] = []
    seen_values: set[int] = set()
    for index, readout in enumerate(readouts):
        table_cell = readout + 1
        placed = None
        for cell in sorted(free):
            for op in _OPS:
                if _char_for(op, table_cell) + 1 != cell:
                    continue
                for seed in range(128, _ENTRY):
                    if seed in used:
                        continue
                    value = _crazy(_chain(_g(seed), "rot K2"), 29524)
                    if value < _D_FLOOR or value in seen_values:
                        continue
                    if any(abs(value - other) <= 4 for other in seen_values):
                        continue
                    placed = (cell, seed, value)
                    break
                if placed:
                    break
            if placed:
                break
        assert placed is not None, index
        cell, seed, value = placed
        free.discard(cell)
        used.add(cell)
        used.add(seed)
        pointers.append(cell)
        values[cell] = value
        seen_values.add(value)
        seeds.append((seed, "rot K2", cell))
    return pointers, values, seeds


def _walked(used: set[int], value: int | None = None) -> int:
    address = next(
        a
        for a in range(128, _ENTRY)
        if a not in used and (value is None or _g(a) == value)
    )
    used.add(address)
    return address


def _execute(
    program: str, bits: int, limit: int = 20_000
) -> tuple[tuple[int, int, int, bool], list[int], list[int]]:
    """Run the dispatcher on ``bits`` and return state, memory, and output."""
    memory = list(_initial_memory(program))
    state = (0, 0, 0, False)
    inputs = iter(48 + ((bits >> k) & 1) for k in (2, 1, 0))
    output: list[int] = []
    for _ in range(limit):
        char = next(inputs, None) if _op(memory[state[1]], state[1]) == "/" else None
        state, writes, effect = _advance(state, memory, char)
        for address, value in writes:
            memory[address] = value
        if effect is not None:
            output.append(effect)
        if state[3]:
            return state, memory, output
    raise AssertionError(f"no halt on {bits}")


def main() -> int:
    """Check every triple reaches its executable output and halt stub."""
    emission = emit()
    for bits in range(8):
        state, _, output = _execute(emission.source, bits)
        assert output == [48], (bits, output)
        assert state[1] - 1 == emission.entries[bits], (bits, state)
    assert len(set(emission.entries)) == 8, emission.entries
    print(f"three-input dispatch: 8 / 8 output stubs at {sorted(emission.entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
