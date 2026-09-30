"""Emit all ten decoder helper initializers in one address-fold source."""

import argparse
import itertools
from bisect import bisect_left

from address_gadget import execute_state
from decoder_group import _Group, _setup
from helper_consumer import helper_chunks, helper_values
from setup_consumer import check_setup_memory, control_inputs
from shared_fold import build_shared_fold

from esolangs.tools._malbolge_core import _char_for, _g, _rot
from esolangs.tools.malbolge import _Planner

_Chunk = list[tuple[str, int, int | None]]


def _copy(plan: _Planner, start: int | None = None) -> _Planner:
    return _Planner(
        plan.c if start is None else start,
        plan.d,
        dict(plan.mem),
        dict(plan.data),
    )


def _emit(plan: _Planner, chunk: _Chunk, incoming: int | None = None) -> None:
    for index, (operation, target, value) in enumerate(chunk):
        if (
            index == 0
            and operation == "*"
            and value is not None
            and incoming == value == plan.mem[target]
        ):
            continue
        plan.op(operation, target)
        plan.mem[target] = value


def place_chunks(
    plan: _Planner,
    chunks: list[_Chunk],
    blocked: set[int],
    protected: set[int],
    *,
    continuation: _Chunk | None = None,
) -> tuple[_Planner, dict[int, str], int]:
    """Place accumulator-independent chunks, retaining an escape for each."""
    emitted: dict[int, str] = {}
    routes = 0
    for index, chunk in enumerate(chunks):
        trial = _copy(plan)
        _emit(trial, chunk)
        following = chunks[index + 1] if index + 1 < len(chunks) else continuation
        stranded = False
        if following is not None and not set(trial.code) & blocked:
            try:
                _route(trial, following, blocked | set(trial.code), protected, 1)
            except AssertionError:
                stranded = True
        if set(trial.code) & blocked or _room(trial.c, sorted(blocked)) < 1 or stranded:
            header, trial, sentinel = _route(
                plan, chunk, blocked, protected, 1, following
            )
            emitted.update(header.code)
            blocked.update(header.code)
            blocked.add(sentinel)
            routes += 1
        assert not set(trial.code) & blocked
        emitted.update(trial.code)
        blocked.update(trial.code)
        plan = trial
    return plan, emitted, routes


def _room(start: int, blocked: list[int]) -> int:
    index = bisect_left(blocked, start)
    return (blocked[index] if index < len(blocked) else 59049) - start


def _route(
    plan: _Planner,
    chunk: _Chunk,
    blocked: set[int],
    protected: set[int],
    tail: int,
    next_chunk: _Chunk | None = None,
) -> tuple[_Planner, _Planner, int]:
    """Rotate a disposable known word into an unused code entry and jump there."""
    ordered = sorted(blocked)
    candidates = []
    for address, known in plan.mem.items():
        if (
            not (0 <= address < 34 or 128 <= address < 400)
            or address in protected
            or known is None
        ):
            continue
        value = known
        for turns in range(10):
            entry = value + 1
            if (
                420 < entry < 59049
                and entry - 1 not in blocked
                and _room(entry, ordered) >= tail + 100
            ):
                candidates.append((-_room(entry, ordered), turns, address, value))
            value = _rot(value)
    for _, turns, pointer, value in sorted(candidates):
        header = _copy(plan)
        word = header.mem[pointer]
        assert word is not None
        for _ in range(turns):
            header.op("*", pointer)
            word = _rot(word)
            header.mem[pointer] = word
        assert word == value
        header.goto(pointer)
        header.raw("i")
        if set(header.code) & blocked:
            continue
        entry = value + 1
        reserved = blocked | set(header.code) | {entry - 1}
        body = _copy(header, entry)
        _emit(body, chunk)
        if set(body.code) & reserved or _room(body.c, sorted(reserved)) < tail:
            continue
        if next_chunk is not None:
            try:
                _route(body, next_chunk, reserved | set(body.code), protected, 1)
            except AssertionError:
                continue
        assert header.data == plan.data == body.data
        return header, body, entry - 1
    raise AssertionError(f"no non-overlapping helper route from C{plan.c}, D{plan.d}")


def build_combined_helpers(
    *, reserved: set[int] | None = None
) -> tuple[str, tuple[tuple[int, int, int], ...], dict[str, int], _Planner]:
    """Return one real source, fold interface, metadata and the live helper exit."""
    group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    outputs: dict[str, int] = {}
    plans: list[_Planner] = []
    occupied: set[int] = set()
    source, groups, _, prefix_size = build_shared_fold(
        decoder_constants=True, decoder_plans=plans, outputs=outputs, occupied=occupied
    )
    plan = plans[0]
    replaced_halt = plan.c
    constants = {
        "all1": outputs["decoder_all1"],
        "all2": outputs["decoder_all2"],
        "z0": outputs["decoder_zero"],
    }
    values = helper_values(group)
    direct: dict[int, int] = {}
    for cell, wanted in values.items():
        known = plan.mem[cell]
        if known is not None and any(
            _g(seed) == known and wanted in reach for seed, reach in group.reach.items()
        ):
            direct[cell] = known
    values = dict(sorted(values.items(), key=lambda item: item[0] not in direct))
    protected = set(values) | set(constants.values()) | {19, 142, 145, 139, 144}
    roots = {
        cell: next(
            address
            for address, value in plan.mem.items()
            if 130 <= address < 400 and address not in protected and value == _g(cell)
        )
        for cell in values
    }
    chunks = []
    protections = []
    finished: set[int] = set()
    remaining_roots = set(roots.values())
    fixed = set(constants.values()) | {19, 142, 145, 139, 144} | set(direct)
    for cell, wanted in values.items():
        copy_cell = min(
            (
                address
                for address in range(130, 400)
                if address not in protected and address not in roots.values()
            ),
            key=lambda address: (abs(address + 1 - cell), address),
        )
        for chunk in helper_chunks(
            group,
            cell,
            wanted,
            roots[cell],
            constants,
            initial=direct.get(cell),
            copy_cell=copy_cell,
        ):
            chunks.append(chunk)
            protections.append(fixed | finished | {cell, copy_cell} | remaining_roots)
        finished.add(cell)
        remaining_roots.discard(roots[cell])
    blocked = (occupied - {replaced_halt}) | set(plan.data) | set(range(420))
    emitted: dict[int, str] = {}
    routes = 0
    accumulator: int | None = None
    for index, chunk in enumerate(chunks):
        protected = protections[index]
        tail = 1
        trial = _copy(plan)
        _emit(trial, chunk, accumulator)
        stranded = False
        if index + 1 < len(chunks) and not set(trial.code) & blocked:
            try:
                _route(
                    trial, chunks[index + 1], blocked | set(trial.code), protected, 1
                )
            except AssertionError:
                stranded = True
        if (
            set(trial.code) & blocked
            or _room(trial.c, sorted(blocked)) < tail
            or stranded
        ):
            header, trial, sentinel = _route(
                plan,
                chunk,
                blocked,
                protected,
                tail,
                chunks[index + 1] if index + 1 < len(chunks) else None,
            )
            emitted.update(header.code)
            blocked.update(header.code)
            blocked.add(sentinel)
            routes += 1
        assert not set(trial.code) & blocked
        emitted.update(trial.code)
        blocked.update(trial.code)
        plan = trial
        accumulator = chunk[-1][2]
    assert all(plan.mem[cell] == wanted for cell, wanted in values.items())
    exit_plan = _copy(plan)
    plan.raw("v")
    assert plan.c - 1 not in blocked
    emitted[plan.c - 1] = "v"
    if reserved is not None:
        reserved.update(blocked)
        reserved.add(plan.c - 1)
    assert set(emitted) & occupied == {replaced_halt}
    assert plan.data == plans[0].data
    rendered = list(source)
    for address, operation in emitted.items():
        rendered[address] = chr(_char_for(operation, address))
    outputs.update(
        helper_halt=plan.c - 1,
        helper_routes=routes,
        helper_code_cells=prefix_size - 1 + len(emitted),
    )
    return "".join(rendered), groups, outputs, exit_plan


def main(*, full: bool = False) -> None:
    """Execute the combined setup and compare every helper with decoder entry."""
    source, groups, outputs, _ = build_combined_helpers()
    group: _Group = _setup(
        frozenset({142, 145, 139, 144}), external_pointer=True, runtime_base=True
    )
    cases = itertools.product((0, 1), repeat=14) if full else control_inputs()
    total = 0
    for bits in cases:
        printed: list[int] = []
        state, memory = execute_state(source, bits, printed)
        assert state[1] == outputs["helper_halt"]
        assert not printed
        assert all(
            memory[cell] == wanted for cell, wanted in helper_values(group).items()
        )
        check_setup_memory(memory, groups, outputs, group, bits)
        total += 1
    print(
        f"combined helpers: {total} source runs; {outputs['helper_routes']} routes; "
        f"{outputs['helper_code_cells']} code cells"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="check all address inputs")
    main(full=parser.parse_args().full)
