"""Compact trampoline initialization and executed five-state decoder controls."""

import argparse
import itertools

from address17 import table_cells
from decoder_group import (
    _VIEW,
    _admissible,
    _build,
    _expected,
    _Group,
    _meaning,
    _run,
    _setup,
)
from planner import _Planner

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools.malbolge import _chain, _emit_chain
from esolangs.tools.malbolge.core import _g, _rot

ALL1, ALL2 = 29524, 59048


def emit_navigation(
    plan: _Planner, group: _Group, used: set[int], helpers: dict[str, int]
) -> None:
    """Initialize view and constant-load pointers through crazy compositions."""
    for target in sorted(group.view_cells):
        seed = _crazy(ALL2, target - 1)
        source = next(
            (
                cell
                for cell in range(130, 420)
                if cell not in used and plan.mem.get(cell) == seed
            ),
            None,
        )
        if source is None:
            continue
        used.add(source)
        group.used.add(source)
        plan.op("*", helpers["all2"])
        plan.op("p", source)
        assert plan.mem[source] == target - 1

    source = next(
        cell for cell in range(130, 420) if cell not in used and plan.mem[cell] == 109
    )
    load(plan, source, 109, helpers["all2"])
    mixer = helpers["all1"]
    plan.op("p", mixer)
    value = _crazy(109, ALL1)
    assert plan.mem[mixer] == value
    for index, (seed, target) in enumerate(((45, 128), (47, 129))):
        cell = next(
            cell
            for cell in range(130, 420)
            if cell not in used and plan.mem[cell] == seed
        )
        used.add(cell)
        group.used.add(cell)
        if index:
            load(plan, mixer, value, helpers["all2"])
        plan.op("p", cell)
        assert plan.mem[cell] == target - 1
    # Binary 109 permits restoring ALL1; these bridges save 108 code cells.
    plan.op("*", helpers["all2"])
    plan.op("p", mixer)
    plan.op("p", mixer)
    assert plan.mem[mixer] == ALL1


def mask(state: int) -> int:
    """Return the operand preserving six low trits and tagging the state."""
    shifts = (3**6, -(3**6), -(3**7), -(3**6) - 3**7, 3**6 + 3**7)
    return ALL1 + (3**6 - 1) // 2 + shifts[state]


def emit_low_neighbour(
    plan: _Planner, group: _Group, used: set[int], helpers: dict[str, int]
) -> None:
    """Initialize D127's return edge without changing bootstrap source cells."""
    source = next(
        cell for cell in group.reach if cell not in used and 153 in group.reach[cell]
    )
    used.add(source)
    group.used.add(source)
    _emit_chain(plan, source, " ".join(group.reach[source][153]), helpers)
    assert plan.accumulator == 153
    plan.op("p", helpers["all1"])
    plan.op("p", 365)
    assert plan.mem[365] == 126
    # ALL2 + pp produces binary trits; zero + p restores ALL1.
    plan.op("*", helpers["all2"])
    plan.op("p", helpers["all1"])
    plan.op("p", helpers["all1"])
    plan.op("*", helpers["z0"])
    plan.op("p", helpers["all1"])
    assert plan.mem[helpers["all1"]] == ALL1


def landing(state: int, parity: int, char: int) -> int:
    """Return one of 940 distinct addresses below the truth-table tiling."""
    return _crazy(mask(state), _crazy(_VIEW[2 * state + parity], char)) + 1


def begin(plan: _Planner, used: set[int]) -> _Planner:
    """Jump beyond low trampolines and clear the accumulator for initialization."""
    pointer = next(a for a in range(130, 420) if a not in used and plan.mem[a] == 46)
    used.add(pointer)
    value = 46
    for _ in range(3):
        plan.op("*", pointer)
        value = _rot(value)
        plan.mem[pointer] = value
    assert value == 41554
    plan.goto(pointer)
    plan.raw("i")
    assert plan.c < 763
    body = _Planner(value + 1, plan.d, dict(plan.mem), plan.data)
    body.code.update(plan.code)
    zeros = []
    for choices in ((72, 78, 80), (37, 39, 40)):
        cell = next(
            a for a in range(130, 420) if a not in used and body.mem[a] in choices
        )
        used.add(cell)
        zeros.append(cell)
    word = body.mem[zeros[0]]
    assert word is not None
    body.op("*", zeros[0])
    body.mem[zeros[0]] = _rot(word)
    body.op("p", zeros[0])
    body.mem[zeros[0]] = ALL1
    body.op("p", zeros[1])
    body.mem[zeros[1]] = 0
    return body


def load(plan: _Planner, cell: int, value: int, all2: int) -> None:
    """Load a preserved constant through two involutive ALL2 crazy passes."""
    for _ in range(2):
        plan.op("*", all2)
        plan.mem[all2] = ALL2
        plan.op("p", cell)
        value = _crazy(ALL2, value)
        plan.mem[cell] = value


def emit_masks(
    plan: _Planner,
    group: _Group,
    used: set[int],
    helpers: dict[str, int],
    states: list[int],
    *,
    derived: bool = False,
) -> dict[int, int]:
    """Initialize state masks; zero-prefix variants use pure powers of three."""
    facts = {
        helpers["all1"]: ALL1,
        helpers["all2"]: ALL2,
        helpers["z0"]: 0,
    }
    plan.mem.update(facts)
    if derived:
        cells = {}
        for state in states:
            cell = next(a for a in range(130, 420) if a not in used)
            used.add(cell)
            wanted = mask(state)
            digits = (wanted // 3**6 % 3, wanted // 3**7 % 3)
            # Binary bases select tag 0 or 2; two zero bits yield tag 1.
            first = sum((digit == 0) * 2**i for i, digit in enumerate(digits))
            second = sum((digit == 2) * 2**i for i, digit in enumerate(digits))
            source = group.view_cells[second]
            value = plan.mem[source]
            assert value is not None
            if first == 0:
                # ALL2 doubles a binary base; one pass back restores it.
                plan.op("*", helpers["all1"])
                plan.op("p", cell)
                plan.op("p", cell)
                plan.op("*", helpers["all2"])
                plan.op("p", source)
                plan.op("p", cell)
                plan.op("*", helpers["all2"])
                plan.op("p", source)
                assert plan.mem[source] == value
            else:
                initial = plan.mem[cell]
                # Binary bases have six low 1-trits, so pp copies over low words.
                if initial is None or not 0 <= initial < 3**6:
                    plan.op("*", helpers["all1"])
                    plan.op("p", cell)
                    plan.op("p", cell)
                load(plan, source, value, helpers["all2"])
                plan.op("p", cell)
                plan.op("p", cell)
                plan.op("*", helpers["all2"])
                plan.op("p", cell)
                source = group.view_cells[first]
                value = plan.mem[source]
                assert value is not None
                load(plan, source, value, helpers["all2"])
                plan.op("p", cell)
            assert plan.mem[cell] == wanted
            cells[state] = cell
        return cells

    def constant(wanted: int) -> int:
        cell = next(
            a
            for a in group.reach
            if a not in used and plan.mem[a] == _g(a) and wanted in group.reach[a]
        )
        used.add(cell)
        value = _g(cell)
        for token in group.reach[cell][wanted]:
            _emit_chain(plan, cell, token, helpers)
            value = _chain(value, token)
            plan.mem[cell] = value
            plan.mem.update(facts)
        assert value == wanted
        return cell

    cells = {}
    for state in states:
        if state in (0, 4):
            cells[state] = constant(mask(state))
            continue
        anchor = ALL1 + (3**6 - 1) // 2
        cell = constant(anchor)
        power = {1: 3**6, 2: 3**7, 3: 3**6 + 3**7}[state]
        source = constant(power)
        load(plan, source, power, helpers["all2"])
        plan.op("p", cell)
        plan.mem[cell] = _crazy(power, anchor)
        assert plan.mem[cell] == mask(state)
        cells[state] = cell
    return cells


def main(*, table_free_hubs: bool = False, common_setup: bool = False) -> None:
    """Run all 2744 row/meaning cases as standalone, uninjected sources."""
    addresses = {
        landing(state, parity, char)
        for state in range(5)
        for parity in range(2)
        for char in range(33, 127)
    }
    assert len(addresses) == 940
    assert all(420 < a < 6561 for a in addresses)
    group = _setup(frozenset(), table_free_hubs=table_free_hubs)
    if table_free_hubs:
        table = table_cells()
        old_group = _setup(frozenset())
        assert any(
            hub + offset in table
            for hubs in old_group.hub_values.values()
            for hub in hubs
            for offset in range(4)
        )
        assert (
            not {
                hub + offset
                for hubs in group.hub_values.values()
                for hub in hubs
                for offset in range(4)
            }
            & table
        )
    total = 0
    shared = None
    for row in range(8):
        emission = _build(row, group, compact=True, common_setup=common_setup)
        assert not set(emission.code) & set(emission.data)
        if common_setup:
            from runtime_decoder import _prepare

            state, memory = _prepare(emission)
            assert state[1:3] == (emission.setup.c, emission.setup.d)
            assert all(
                memory[address] == value
                for address, value in emission.setup.memory.items()
                if value is not None
            )
            if emission.setup.accumulator is not None:
                assert state[0] == emission.setup.accumulator
            if shared is None:
                shared = emission.setup
            assert emission.setup == shared
        if table_free_hubs:
            assert set(emission.data) & table <= set(range(group.base, group.base + 3))
        for triple in itertools.product(range(7), repeat=3):
            program = list(emission.source)
            for offset, meaning in enumerate(triple):
                cell = group.base + offset
                program[cell] = next(
                    char
                    for char in _admissible(cell)
                    if _meaning(char, cell % 2) == meaning
                )
            cell = group.base + 3
            program[cell] = _admissible(cell)[
                (49 * triple[0] + 7 * triple[1] + triple[2]) % 8
            ]
            source = "".join(map(chr, program))
            assert len(source) == 59049
            assert _run(source) == [ord(_expected(row, triple))], (row, triple)
            total += 1
        print(f"row {row}: 343 standalone runs; {emission.code_cells} code cells")
    assert total == 2744
    print("compact decoder: 2744 standalone executions; no host initialization")
    if shared is not None:
        print(
            f"common setup: {len(shared.code)} code cells, "
            f"{len(shared.data)} data cells; C={shared.c}, D={shared.d}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table-free-hubs", action="store_true")
    parser.add_argument("--common-setup", action="store_true")
    args = parser.parse_args()
    main(table_free_hubs=args.table_free_hubs, common_setup=args.common_setup)
