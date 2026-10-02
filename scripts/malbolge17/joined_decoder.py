"""Execute one shared decoder after its native three-input row selector.

Controls inject the address/parity/table interface; they do not emit the
seventeen-input address producer or tile the complete truth table.
"""

import itertools
from dataclasses import replace

from address17 import group_cells
from combined_helpers import _Chunk, _room, _route, place_chunks
from compact_decoder import mask
from decoder_group import (
    _POS,
    _START,
    _build,
    _Emission,
    _emit_field,
    _expected,
    _setup,
)
from planner import _Planner
from row_projection import pointer_slots
from runtime_decoder import _prefill, _prepare

from esolangs.interpreters.other.malbolge import _advance, _op
from esolangs.tools.malbolge.core import _char_for, _rot
from esolangs.tools.malbolge.digits import _D_INITS, _GADGET


def build() -> tuple[_Emission, dict[int, int]]:
    """Return the joined source and its dynamically initialized pointer records."""
    group = _setup(
        frozenset({142, 145, 139, 144}),
        external_pointer=True,
        runtime_base=True,
        table_free_hubs=True,
    )
    emission = _build(
        0,
        group,
        external_pointer=True,
        external_parity=True,
        compact=True,
        common_setup=True,
    )
    setup = emission.setup
    code = dict(setup.code)
    data = dict(setup.data)
    z0 = next(iter(group.hub_values["N"])) + 1
    # Keep the two print continuations; replace the state continuations by dispatchers.
    blocked = set(code) | set(data)
    windows = {k: (a, n) for k, a, n in emission.copy_windows}
    for key, (a, n) in windows.items():
        blocked.update(range(a, a + n))
        if key[0] == "p":
            code.update({c: op for c, op in emission.code.items() if a <= c < a + n})
    used = (
        set(group.used)
        | set(setup.helpers.values())
        | set(setup.state_masks.values())
        | {142, 145, 139, 144}
    )

    def fresh(value: int | None = None) -> int:
        a = next(
            a
            for a, v in setup.memory.items()
            if 130 <= a < 420 and a not in used and (value is None or v == value)
        )
        used.add(a)
        return a

    cells = [fresh(v) for v in _D_INITS[0]]
    tmp = fresh()
    rowword = fresh()
    projection = fresh(53)

    def decoder(p: _Planner, row: int, state: int) -> None:
        offset = _POS[state][row]
        _emit_field(
            p,
            base=group.base,
            offset=offset,
            view_cell=group.view_cells[state],
            parity_cell=setup.parity_fields[offset],
            pointer_cell=142,
            z0=z0,
            all2=129,
            compact_mask=(setup.state_masks[state], mask(state)),
        )

    def place(row: int, state: int, preferred: int | None = None) -> int:
        ordered = sorted(
            candidates, key=lambda candidate: setup.memory[candidate[1]] != preferred
        )
        for a, root, turns in ordered:
            if a in blocked or a - 1 in blocked:
                continue
            p = _Planner(a, 0, dict(setup.memory), data)
            for op in "jjoojj":
                p.raw(op)
            p.d = z0
            decoder(p, row, state)
            assert max(p.code) < a + 700
            if set(p.code) & blocked:
                continue
            code.update(p.code)
            blocked.update(p.code)
            blocked.add(a - 1)
            recipes[a] = (root, turns)
            return a
        raise AssertionError("no decoder continuation window")

    recipes: dict[int, tuple[int, int]] = {}
    candidates = []
    for root, value in setup.memory.items():
        if root < 130 or root in used or value is None or not 33 <= value <= 126:
            continue
        # N labels also return through the initialized neighbour escape.
        for turns in range(10):
            if turns == 5 and 7000 <= value + 1 < 40500:
                candidates.append((value + 1, root, turns))
            value = _rot(value)
    candidates.sort()
    initial = [place(r, _START[r], setup.memory[pointer_slots()[r]]) for r in range(8)]
    classes: dict[tuple[int, int], int] = {}
    for state in (3, 4):
        for row in range(8):
            class_key = (state, _POS[state][row])
            if class_key not in classes:
                classes[class_key] = place(
                    row, state, setup.memory[pointer_slots()[row] + state - 2]
                )
    assert len(classes) == 5
    records: dict[int, int] = {}
    for row, slot in enumerate(pointer_slots()):
        for field, entry in enumerate(
            (initial[row], classes[3, _POS[3][row]], classes[4, _POS[4][row]])
        ):
            records[slot + field] = entry - 1
    for gap in (9, 30):
        records[gap] = initial[0] - 1
    assert len(recipes) == 13
    assert len(records) == 26
    used.update(root for root, _ in recipes.values())
    copy_cell = 1
    used.update({1, 31, 32, 33})
    plan = _Planner(
        setup.c, setup.d, dict(setup.memory), data, accumulator=setup.accumulator
    )
    chunks: list[_Chunk] = []

    def chunk(ops: list[tuple[str, int]]) -> None:
        trial = _Planner(0, plan.d, dict(plan.mem), data)
        facts: _Chunk = []
        for op, target in ops:
            trial.op(op, target)
            facts.append((op, target, trial.mem[target]))
        plan.mem.update(trial.mem)
        chunks.append(facts)

    for target in (31, 32, 33):
        chunk([("*", 128), ("p", target), ("p", target)])
    chunk([("*", 129), ("p", 32)])
    chunk([("*", 31), ("p", 33)])
    # Retaining matching walked seeds removes 3,621 initializer cells.
    for target, entry in records.items():
        record_seed = setup.memory[recipes[entry + 1][0]]
        assert record_seed is not None
        if plan.mem[target] != record_seed:
            chunk([("*", 31), ("p", target), ("p", target)])
    for entry, (root, _turns) in recipes.items():
        targets = [
            a
            for a, v in records.items()
            if v == entry - 1 and plan.mem[a] != setup.memory[root]
        ]
        if not targets:
            continue
        chunk(
            [
                ("*", 31),
                ("p", copy_cell),
                ("p", copy_cell),
                ("*", 129),
                ("p", root),
                ("*", 129),
                ("p", root),
                ("p", copy_cell),
                ("p", targets[0]),
            ]
        )
        # Nearby ALL2 saves 2138 code cells for copies through cell 1.
        for target in targets[1:]:
            chunk(
                [
                    ("*", 32),
                    ("p", copy_cell),
                    ("*", 32),
                    ("p", copy_cell),
                    ("p", target),
                ]
            )
        for target in targets:
            assert plan.mem[target] == setup.memory[root]
    for a in (tmp, rowword):
        chunk([("*", 128), ("p", a), ("p", a)])
    constants = {"K0": 198, "K1": 128, "K2": 129}
    # Keep accumulator-dependent operations in one relocation chunk.
    ops: list[tuple[str, int]] = []
    for op in _GADGET:
        if op == "/" or op.startswith("K"):
            if ops:
                chunk(ops)
            ops = [("/", tmp)] if op == "/" else [("*", constants[op])]
        else:
            ops.append(("p", cells[int(op)]))
    ops.extend(
        [("p", tmp), ("*", tmp), ("p", cells[1]), ("*", cells[1]), ("p", rowword)]
    )
    chunk(ops)
    for _ in range(7):
        chunk([("*", rowword)])
    chunk([("*", 198), ("p", projection)])
    for _ in range(2):
        chunk([("*", 129), ("p", rowword)])
        chunk(
            [
                ("*", 129),
                ("p", projection),
                ("*", 129),
                ("p", projection),
                ("p", rowword),
            ]
        )
    plan = _Planner(
        setup.c, setup.d, dict(setup.memory), data, accumulator=setup.accumulator
    )
    protected = (
        used | set(records) | {rowword, tmp, projection, copy_cell, 128, 129, 198}
    )
    plan, emitted, _routes = place_chunks(plan, chunks, blocked, protected)

    def select(p: _Planner, field: int) -> None:
        # Only the selected record rotates; its unvisited neighbour stays ASCII.
        for _ in range(5):
            p.goto(rowword)
            p.raw("j")
            # The row-dependent D is unknown until the neighbour escape resets it.
            p.d = 420
            for _ in range(field):
                p.raw("o")
            p.raw("*")
            for op in "jjoojj":
                p.raw(op)
            p.d = z0
        p.goto(rowword)
        p.raw("j")
        for _ in range(field):
            p.raw("o")
        p.raw("i")

    if _room(plan.c, sorted(blocked)) < 1000:
        header, plan, sentinel = _route(
            plan, [("*", 129, 59048)], blocked, protected, 1000
        )
        emitted.update(header.code)
        blocked.update(header.code)
        blocked.add(sentinel)
        emitted.update(plan.code)
    existing = set(plan.code)
    select(plan, 0)
    assert not (set(plan.code) - existing) & blocked
    code.update(emitted)
    code.update(plan.code)
    for state, key in ((3, "s3"), (4, "s4")):
        a, n = windows[key]
        p = _Planner(a, 0, dict(setup.memory), data)
        for op in "ojj":
            p.raw(op)
        p.d = z0
        select(p, state - 2)
        assert max(p.code) < a + n
        code.update(p.code)
    source = [_char_for("o", a) for a in range(59049)]
    for a, op in code.items():
        source[a] = _char_for(op, a)
    for a, v in data.items():
        assert a not in code, (a, v)
        source[a] = v
    seeds: dict[int, int] = {}
    for address, value in records.items():
        pointer_seed = setup.memory[recipes[value + 1][0]]
        assert pointer_seed is not None
        seeds[address] = pointer_seed
    return replace(
        emission, source=source, code=code, data=data, code_cells=len(code)
    ), seeds


def main() -> None:
    """Execute all eight rows and seven meanings at both address parities."""
    emission, records = build()
    state, prepared = _prepare(emission)
    assert state[1] == emission.setup.c
    for _ in range(100000):
        if _op(prepared[state[1]], state[1]) == "/":
            break
        state, writes, effect = _advance(state, prepared)
        assert effect is None
        assert not state[3]
        for a, v in writes:
            prepared[a] = v
    else:
        raise AssertionError("did not reach row input")
    assert all(prepared[a] == v for a, v in records.items())

    occupied = set(emission.code) | set(emission.data)
    bases: list[int] = []
    for bits in itertools.product((0, 1), repeat=14):
        base = group_cells(bits)[0]
        if not set(range(base, base + 4)) & occupied and base % 2 not in [
            b % 2 for b in bases
        ]:
            bases.append(base)
        if len(bases) == 2:
            break
    assert len(bases) == 2
    count = 0
    for row, tail in enumerate(itertools.product((0, 1), repeat=3)):
        for base in bases:
            for triple in itertools.product(range(7), repeat=3):
                m = list(prepared)
                for a, v in _prefill(base, triple).items():
                    m[a] = v
                inputs = iter(48 + b for b in tail)
                st = state
                out = []
                for _step in range(100000):
                    char = next(inputs) if _op(m[st[1]], st[1]) == "/" else None
                    st, writes, effect = _advance(st, m, char)
                    for a, v in writes:
                        m[a] = v
                    if effect is not None:
                        out.append(effect)
                    if st[3]:
                        break
                assert st[3]
                assert out == [ord(_expected(row, triple))], (
                    row,
                    base,
                    triple,
                    st,
                    out,
                    _step,
                )
                assert next(inputs, None) is None
                count += 1
        print("joined row", row, count, flush=True)
    assert count == 5488
    print(
        "joined shared setup and real row-tail:",
        count,
        "injected address/table controls;",
        emission.code_cells,
        "code cells;",
        len(emission.source),
        "source characters",
        flush=True,
    )


if __name__ == "__main__":
    main()
