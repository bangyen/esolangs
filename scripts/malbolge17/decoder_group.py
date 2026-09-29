"""Emit the five-state group decoder as real Malbolge source.

States come from ``decoder_s5_norepeat.p``.  State ``q`` reads group cell
``POS[q][s]`` under view constant ``VIEW[2 * q + parity]`` and routes through a
trampoline to one of four shared hubs (print 0, print 1, state 3, state 4).
``main`` builds one program per margin row and runs every meaning triple of the
group in process.  The group base is a parameter: the committed address fold
supplies it once the decoder is wired in.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

from esolangs.interpreters.other.malbolge import (
    _WORDS,
    _advance,
    _crazy,
    _initial_memory,
)
from esolangs.tools._malbolge_core import (
    _ENTRY,
    _build_constants,
    _char_for,
    _g,
    _rot,
)
from esolangs.tools.malbolge import (
    _T_HELPERS,
    _T_LABELS,
    _emit_chain,
    _Planner,
    _rotations,
    _valid_chars,
)

_VIEW = (242, 728, 1700, 2186, 4616, 5102, 6074, 6560, 13364, 13850)
_BASES = (364, 1093, 2551, 3280, 6925)
_PARITY = (58318, 59047)
_MASK = 729
_INSTR = frozenset({6, 7, 29, 35, 48, 65, 66, 84})
_PART = (
    frozenset({0, 2, 4, 6, 9, 11, 14, 26, 51, 72, 84, 91, 93}),
    frozenset({7, 16, 25, 30, 37, 40, 49, 54, 60, 63, 67, 70, 81}),
    frozenset({10, 17, 19, 20, 22, 24, 29, 31, 34, 44, 46, 71, 92}),
    frozenset({5, 13, 15, 23, 33, 38, 47, 57, 62, 65, 75, 86, 89}),
    frozenset({1, 12, 21, 28, 35, 39, 42, 53, 61, 68, 74, 77, 79, 82}),
    frozenset({3, 18, 27, 32, 41, 43, 45, 48, 50, 52, 56, 59, 83, 88}),
    frozenset({8, 36, 55, 58, 64, 66, 69, 73, 76, 78, 80, 85, 87, 90}),
)
_TARGET = {-1: "p0", -2: "p1", 3: "s3", 4: "s4"}
_KEY = {"0": "p0", "1": "p1", "x": "s3", "n": "s4"}
_LABEL_OF = {value: key for key, value in _KEY.items()}
_LABELS = {
    index + 34: label for index, label in enumerate(_T_LABELS) if label in "01xn"
}
_OTHERS = sorted(set(range(34, 128)) - set(_LABELS))
_DECODER = Path(__file__).resolve().parent / "decoder_s5_norepeat.p"


def _load_decoder(path: Path) -> tuple[list[int], list[list[int]], list[list[int]]]:
    """Read ``decoder_s5_norepeat.p`` into start states, deltas, and positions."""
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    start = [int(token) for token in lines[1].split()[1:]]
    delta: list[list[int]] = []
    positions: list[list[int]] = []
    for line in lines[2:7]:
        head, tail = line.split("| pos")
        delta.append([int(token) for token in head.split("|")[1].split()])
        positions.append([int(token) for token in tail.split()])
    return start, delta, positions


_START, _DELTA, _POS = _load_decoder(_DECODER)


def _admissible(address: int) -> list[int]:
    """Every character that is one of the eight operations at ``address``."""
    return sorted(33 + ((char - address) % 94) for char in _INSTR)


def _admits(address: int, char: int) -> bool:
    """Whether ``char`` is a valid operation at ``address``."""
    return (char - 33 + address) % 94 in _INSTR


def _landing(constant: int, char: int) -> int:
    """Return the cell an instruction at ``char`` lands on after ``crazy``."""
    return _crazy(constant, char) + 1


def _meaning(char: int, parity: int) -> int:
    """Return the seven-way meaning of an admissible character at a parity."""
    value = (char - 33 - parity) % 94
    for index, part in enumerate(_PART):
        if value in part:
            return index
    raise AssertionError("no meaning class")


def _bfs(start: int, depth: int = 11) -> dict[int, list[str]]:
    """Every value reachable from ``start`` and the ops that reach it."""
    seen: dict[int, list[str]] = {start: []}
    frontier = [start]
    for _ in range(depth):
        following: list[int] = []
        for value in frontier:
            moves = (
                ("rot", _rot(value)),
                ("K0", _crazy(0, value)),
                ("K1", _crazy(29524, value)),
                ("K2", _crazy(59048, value)),
            )
            for name, moved in moves:
                if moved not in seen:
                    seen[moved] = [*seen[value], name]
                    following.append(moved)
        frontier = following
    return seen


def _expected(row: int, triple: tuple[int, ...]) -> str:
    """Return the character the five-state decoder prints on ``triple``."""
    state = _START[row]
    while True:
        target = _DELTA[state][triple[_POS[state][row]]]
        if target < 0:
            return "0" if target == -1 else "1"
        state = target


@dataclass(frozen=True)
class _Emission:
    """One row's source, code and data maps, and movable block positions."""

    source: list[int]
    code_cells: int
    code: dict[int, str]
    data: dict[int, int]
    row_start: int
    copy_windows: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True)
class _Group:
    """The fixed group cells and shared setup the decoder build reads."""

    base: int
    z_cells: tuple[int, int, int]
    clear: tuple[tuple[int, int], tuple[int, int]]
    view_cells: tuple[int, ...]
    mask_cells: tuple[int, ...]
    group_pointer: int
    reach: dict[int, dict[int, list[str]]]
    seeds: dict[str, tuple[int, list[str]]]
    hub_values: dict[str, tuple[int, ...]]
    near_cells: list[int]
    used: set[int]
    taken: set[int]


def _setup() -> _Group:
    """Choose the group base and every shared walked cell, as the prototype did."""
    helpers = {128, 129}
    for value in _T_HELPERS.values():
        helpers.add(
            next(
                cell
                for cell in range(130, _ENTRY)
                if cell not in helpers and _g(cell) == value
            )
        )
    order = [cell for cell in range(130, 300) if cell not in helpers]
    order += list(range(300, _ENTRY))
    used = {*_LABELS, *_OTHERS}
    reach = {cell: _bfs(_g(cell)) for cell in order}

    def cell_for(value: int) -> int:
        for cell in order:
            if cell not in used and value in reach[cell]:
                used.add(cell)
                return cell
        raise RuntimeError(f"no cell for {value}")

    reachable = set().union(*(entry for entry in reach.values()))
    base = next(
        group
        for group in range(15000, 21000)
        if all((group - 1 + k) in reachable for k in range(3))
    )
    z_cells = (cell_for(base - 1), cell_for(base), cell_for(base + 1))
    clear0, clear0_value = next(
        (cell, value)
        for cell in order
        if cell not in used
        for value in reach[cell]
        if _rot(value) & 0xFF == 48
    )
    used.add(clear0)
    clear1, clear1_value = next(
        (cell, value)
        for cell in order
        if cell not in used
        for value in reach[cell]
        if _rot(value) & 0xFF == 49
    )
    used.add(clear1)
    view_cells = tuple(cell_for(value) for value in _BASES)
    mask_cells = tuple(cell_for(_MASK) for _ in range(3))
    group_pointer = cell_for(base - 1)
    taken = set(range(base - 2, base + 5))
    for constant in _VIEW:
        taken |= {_landing(constant, char) for char in range(33, 127)}

    seeds: dict[str, tuple[int, list[str]]] = {}
    hub_values: dict[str, tuple[int, ...]] = {}
    for label in "01xn":
        label_cells = sorted(q for q in _LABELS if _LABELS[q] == label)
        seed_cell = _seed_cell(order, used, reach, taken, label_cells)
        assert seed_cell is not None
        cell, path, hub = seed_cell
        used.add(cell)
        seeds[label] = (cell, path)
        hub_values[label] = (hub,)
        taken |= {hub, hub + 1, hub + 2, hub + 3}

    near_cells = sorted(
        {
            *(t + 1 for t in _admissible(base + 3) if t + 1 in _OTHERS),
            *(
                next(e for e in _OTHERS if _admits(hub + 3, e - 1))
                for hubs in hub_values.values()
                for hub in hubs
            ),
        }
    )
    neighbour = _neighbour_cell(order, used, reach, taken, near_cells)
    assert neighbour is not None
    cell, path, hub = neighbour
    used.add(cell)
    seeds["N"] = (cell, path)
    hub_values["N"] = (hub,)
    taken |= {hub, hub + 1, hub + 2, hub + 3}
    return _Group(
        base=base,
        z_cells=z_cells,
        clear=((clear0, clear0_value), (clear1, clear1_value)),
        view_cells=view_cells,
        mask_cells=mask_cells,
        group_pointer=group_pointer,
        reach=reach,
        seeds=seeds,
        hub_values=hub_values,
        near_cells=near_cells,
        used=used,
        taken=taken,
    )


def _seed_cell(
    order: list[int],
    used: set[int],
    reach: dict[int, dict[int, list[str]]],
    taken: set[int],
    label_cells: list[int],
) -> tuple[int, list[str], int] | None:
    """Find a walked seed whose label cells map to one free hub value."""
    for cell in order:
        if cell in used:
            continue
        for seed, path in reach[cell].items():
            walk = seed
            collected = []
            for point in label_cells:
                walk = _crazy(walk, _g(point))
                walk = _crazy(walk, walk)
                collected.append(walk)
            if len(set(collected)) != 1:
                continue
            hub = collected[0]
            if not 10000 <= hub < 59000:
                continue
            if not any(_admits(hub + 3, e - 1) for e in _OTHERS):
                continue
            if not any(_admits(hub + 2, point - 1) for point in label_cells):
                continue
            if {hub, hub + 1, hub + 2, hub + 3} & taken:
                continue
            return cell, path, hub
    return None


def _neighbour_cell(
    order: list[int],
    used: set[int],
    reach: dict[int, dict[int, list[str]]],
    taken: set[int],
    near_cells: list[int],
) -> tuple[int, list[str], int] | None:
    """Find the seed for the shared neighbour-escape hub."""
    for cell in order:
        if cell in used:
            continue
        for seed, path in reach[cell].items():
            walk = seed
            collected = []
            for point in near_cells:
                walk = _crazy(walk, _g(point))
                walk = _crazy(walk, walk)
                collected.append(walk)
            if len(set(collected)) != 1:
                continue
            hub = collected[0]
            if not 10000 <= hub < 59000:
                continue
            if not any(_admits(hub + 3, e - 1) for e in near_cells):
                continue
            if {hub, hub + 1, hub + 2, hub + 3} & taken:
                continue
            return cell, path, hub
    return None


def _build(row: int, group: _Group, row_offset: int = 0) -> _Emission:
    """Emit one row's real-source group decoder and its code-cell count."""
    base = group.base
    used = {128, 129} | group.used
    memory: dict[int, int | None] = {address: _g(address) for address in range(_ENTRY)}
    states = [_START[row]]
    if states[0] in (0, 2):
        states.append(4)
    elif states[0] == 1:
        states.extend((3, 4))
    # Fixed copies keep the setup identical across all eight rows.
    parity_sources: dict[int, list[tuple[int, int]]] = {0: [], 1: []}
    for parity in (0, 0, 1):
        target = _PARITY[parity]
        cell = next(
            cell
            for cell in group.reach
            if cell not in used and target in group.reach[cell]
        )
        used.add(cell)
        parity_sources[parity].append((cell, target))
    parity_counts = {0: 0, 1: 0}
    parity_cells: list[tuple[int, int]] = []
    for state in states:
        parity = _POS[state][row] % 2
        parity_cells.append(parity_sources[parity][parity_counts[parity]])
        parity_counts[parity] += 1
    helpers = {"all1": 128, "all2": 129}
    for name, value in _T_HELPERS.items():
        cell = next(
            cell
            for cell in range(130, _ENTRY)
            if cell not in used and _g(cell) == value
        )
        used.add(cell)
        helpers[name] = cell
    data = {base + k: _char_for("o", base + k) for k in range(3)}
    planner = _Planner(_ENTRY + 1, 34 + (7 - _ENTRY) % 94, memory, data)
    planner.code[_ENTRY] = "j"
    _build_constants(planner, helpers)
    for cell in (helpers["all1"], helpers["all2"]):
        planner.op("p", cell)
        planner.op("p", cell)
    planner.op("*", helpers["w"])
    planner.op("p", helpers["all2"])
    phases = [len(planner.code)]
    values: dict[int, int] = {}
    for label in "01xnN":
        seed, seed_ops = group.seeds[label]
        _emit_chain(planner, seed, " ".join(seed_ops), helpers)
        points = (
            group.near_cells
            if label == "N"
            else sorted(q for q in _LABELS if _LABELS[q] == label)
        )
        for point in points:
            planner.op("p", point)
            planner.op("p", point)
            values[point] = group.hub_values[label][0]
    phases.append(len(planner.code))
    chains: list[tuple[str, int, int]] = [
        (f"z{k}", group.z_cells[k], base - 1 + k) for k in range(3)
    ]
    chains += [
        ("C0", group.clear[0][0], group.clear[0][1]),
        ("C1", group.clear[1][0], group.clear[1][1]),
    ]
    chains += [(f"B{i}", group.view_cells[i], _BASES[i]) for i in range(5)]
    chains += [(f"M{i}", cell, _MASK) for i, cell in enumerate(group.mask_cells)]
    chains += [("R", group.group_pointer, base - 1)]
    chains += [
        (f"P{parity}{index}", cell, target)
        for parity, cells in parity_sources.items()
        for index, (cell, target) in enumerate(cells)
    ]
    for _, cell, value in chains:
        ops = _bfs(_g(cell))
        assert value in ops, (cell, value)
        _emit_chain(planner, cell, " ".join(ops[value]), helpers)
    phases.append(len(planner.code))
    planner.op("*", helpers["all2"])
    planner.op("p", group.group_pointer)
    planner.op("*", helpers["all1"])
    planner.op("p", group.group_pointer)
    for _ in range(10):
        planner.op("*", group.group_pointer)
        planner.op("p", helpers["w"])
    ordered = [*parity_sources[0], *parity_sources[1]]
    for index, (mask, (cell, _)) in enumerate(
        zip(group.mask_cells, ordered, strict=True)
    ):
        if index == 0:
            planner.op("*", helpers["z0"])
            planner.op("p", helpers["w"])
        planner.op("p", mask)
        planner.op("p", cell)
    phases.append(len(planner.code))
    z0 = values[group.near_cells[0]] + 1
    pointer: dict[int, int] = {}
    for point in sorted(values):
        hub = values[point]
        if _admits(hub + 2, point - 1):
            pointer.setdefault(hub, point)
    avoid = set(group.taken) | set(data)
    for hub in set(values.values()):
        if hub in pointer:
            data[hub + 2] = pointer[hub] - 1
            assert _admits(hub + 2, pointer[hub] - 1)
        escape = next(e for e in group.near_cells if _admits(hub + 3, e - 1))
        data[hub + 3] = escape - 1
    copies: list[tuple[str, int, int, list[int]]] = []
    for label in "01xn":
        key = _KEY[label]
        room = 140 if key[0] == "p" else 300
        hubs = sorted({values[p] for p in values if _LABELS.get(p) == label})
        options: list[dict[int, tuple[int, int]]] = []
        for hub in hubs:
            by_address: dict[int, tuple[int, int]] = {}
            for char in _valid_chars(hub + 1):
                for steps, sample in _rotations(char):
                    by_address.setdefault(sample + 1, (char, steps))
            options.append(by_address)
        common = set(options[0]).intersection(*options[1:])
        address = next(
            a
            for a in sorted(common, key=lambda a: sum(o[a][1] for o in options))
            if a >= 7000
            and a + room < _WORDS
            and not any((a + offset) in avoid for offset in range(room))
        )
        turns: list[int] = []
        for hub, option in zip(hubs, options, strict=True):
            char, turn = option[address]
            data[hub + 1] = char
            turns.append(turn)
            planner.hub(pointer[hub], hub)
            for step in range(turn):
                planner.raw("*")
                if step + 1 < turn:
                    planner.raw("j")
                    planner.d = pointer[hub]
                    planner.raw("j")
                    planner.d = hub + 1
            planner.d = hub + 2
        avoid |= set(range(address, address + room))
        copies.append((key, address, room, turns))
    phases.append(len(planner.code))

    def view(state: int) -> tuple[int, int, int, int]:
        offset = _POS[state][row]
        parity = (base + offset) % 2
        return offset, group.view_cells[state], _VIEW[2 * state + parity], parity

    for state in range(5):
        offset, _view_cell, constant, parity = view(state)
        cell = base + offset
        for char in _admissible(cell):
            label = _LABEL_OF[_TARGET[_DELTA[state][_meaning(char, parity)]]]
            landing = _landing(constant, char)
            landing_char = next(
                ch for ch in _valid_chars(landing) if _LABELS.get(ch + 1) == label
            )
            assert data.get(landing, landing_char) == landing_char, (
                "landing clash",
                landing,
            )
            data[landing] = landing_char
    cleared = {a for a in range(_ENTRY) if planner.mem.get(a) is None}
    fresh: dict[int, int | None] = {a: _g(a) for a in range(_ENTRY)}
    planner.mem = fresh
    for address in cleared:
        planner.mem[address] = None

    def decoder(block: _Planner, state: int, depth: int) -> None:
        offset, view_cell, _constant, _parity = view(state)
        cell = base + offset
        z_cell = group.z_cells[offset]
        block.op("*", parity_cells[depth][0])
        block.op("p", view_cell)
        block.goto(z_cell)
        block.raw("j")
        block.d = cell
        block.raw("p")
        block.d = cell + 1
        for _ in range(2 - offset):
            block.raw("o")
        for op in "jjoojj":
            block.raw(op)
        block.d = z0
        block.goto(z_cell)
        block.raw("j")
        block.d = cell
        block.raw("j")
        block.raw("j")
        block.raw("j")
        block.raw("i")

    if row_offset < 0:
        raise ValueError(row_offset)
    assert not any(planner.c <= address < planner.c + row_offset for address in data)
    planner.c += row_offset
    planner.d += row_offset
    row_start = planner.c
    decoder(planner, _START[row], 0)
    for key, address, room, _turns in copies:
        if key == "s3" and 3 not in states:
            continue
        block = _Planner(address, 0, dict(planner.mem), data)
        block.raw("o")
        block.raw("j")
        block.raw("j")
        block.d = z0
        if key == "s3":
            decoder(block, 3, 1)
        elif key == "s4":
            decoder(block, 4, states.index(4))
        else:
            block.op("*", group.clear[0][0] if key == "p0" else group.clear[1][0])
            block.raw("<")
            block.raw("v")
        assert all(address <= a < address + room for a in block.code)
        for a, op in block.code.items():
            planner.code[a] = op
    source = [_char_for("o", a) for a in range(_WORDS)]
    for a, op in planner.code.items():
        source[a] = _char_for(op, a)
    for a, ch in data.items():
        source[a] = ch
    phases.append(len(planner.code))
    return _Emission(
        source=source,
        code_cells=len(planner.code),
        code=dict(planner.code),
        data=dict(data),
        row_start=row_start,
        copy_windows=tuple((key, address, room) for key, address, room, _ in copies),
    )


def _run(source: str, limit: int = 100_000) -> list[int]:
    """Execute a real source and return its emitted characters up to the halt."""
    return _run_traced(source, limit)[0]


def _run_traced(source: str, limit: int = 100_000) -> tuple[list[int], set[int]]:
    """Execute a real source, returning its output and the cells it runs."""
    memory = list(_initial_memory(source))
    state = (0, 0, 0, False)
    output: list[int] = []
    executed: set[int] = set()
    for _ in range(limit):
        executed.add(state[1])
        state, writes, effect = _advance(state, memory)
        for address, value in writes:
            memory[address] = value
        if effect is not None:
            output.append(effect)
        if state[3]:
            return output, executed
    raise AssertionError("group decoder did not halt")


def main() -> int:
    """Rebuild every row and reproduce the 2,744 real-source group cases."""
    group = _setup()
    total = 0
    executed: set[int] = set()
    live_rows: list[tuple[list[int], set[int]]] = []
    emissions: list[_Emission] = []
    for row in range(8):
        emission = _build(row, group, row_offset=200 * row)
        emissions.append(emission)
        source = emission.source
        default = [_char_for("o", a) for a in range(_WORDS)]
        set_cells = sum(1 for a in range(_WORDS) if source[a] != default[a])
        row_executed: set[int] = set()
        for triple in itertools.product(range(7), repeat=3):
            program = list(source)
            for index in range(3):
                cell = group.base + index
                parity = cell % 2
                program[cell] = next(
                    char
                    for char in _admissible(cell)
                    if _meaning(char, parity) == triple[index]
                )
            neighbour = group.base + 3
            program[neighbour] = _admissible(neighbour)[
                (triple[0] * 49 + triple[1] * 7 + triple[2]) % 8
            ]
            char, seen = _run_traced("".join(chr(value) for value in program))
            executed |= seen
            row_executed |= seen
            got = chr(char[0]) if char else None
            assert got == _expected(row, triple), (row, triple, got)
            total += 1
        live_rows.append((source, row_executed))
        print(f"row {row}: {emission.code_cells} written, {set_cells} set cells")
    common = set.intersection(*(seen for _, seen in live_rows))
    variants = {
        address
        for address in executed
        if len({source[address] for source, seen in live_rows if address in seen}) > 1
    }
    owners: dict[int, set[str]] = {}
    for emission in emissions:
        for address, op in emission.code.items():
            owners.setdefault(address, set()).add(op)
    conflicts = {address for address, ops in owners.items() if len(ops - {"o"}) > 1}
    live_conflicts = {
        address: {
            row: emissions[row].code.get(address, "o")
            for row, (_, seen) in enumerate(live_rows)
            if address in seen
        }
        for address in conflicts
    }
    copy_classes: dict[str, list[list[int]]] = {}
    for label in ("s3", "s4"):
        classes: dict[tuple[str, ...], list[int]] = {}
        for row, emission in enumerate(emissions):
            _, address, room = next(
                window for window in emission.copy_windows if window[0] == label
            )
            if not any(a in live_rows[row][1] for a in range(address, address + room)):
                continue
            signature = tuple(
                emission.code.get(a, "o") for a in range(address, address + room)
            )
            classes.setdefault(signature, []).append(row)
        copy_classes[label] = list(classes.values())
    print(f"five-state group decoder: {total} / {total}")
    print(f"executed cells across all rows: {len(executed)}")
    print(f"common executed cells: {len(common)}; live row variants: {len(variants)}")
    print(f"row starts: {[emission.row_start for emission in emissions]}")
    print(f"non-nop opcode conflicts: {len(conflicts)} at {sorted(conflicts)}")
    print(f"live conflict owners: {dict(sorted(live_conflicts.items()))}")
    print(f"live copy classes: {copy_classes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
