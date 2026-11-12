"""Root-only full seven-field thisthat state/history observer for fixed wiki cases."""

# ruff: noqa: PT018
from dataclasses import fields, is_dataclass
from io import StringIO
from operator import itemgetter
from types import MappingProxyType
from typing import NamedTuple
from unittest.mock import patch

from esolangs.runtime._json import worker_dumps, worker_loads
from esolangs.runtime._result_wire import _state_from_wire, _state_wire
from esolangs.runtime.randomness import FirstDraw, Seeded

from . import full_oracle as model
from . import policy_checks as policies


class Context(NamedTuple):
    """Actual classes bound after the fatal startup guard."""

    native: object
    io: object
    variant: object
    snapshot: object
    model: object
    written: object
    oracle: object


class Held(NamedTuple):
    """Immutable actual capture, complete raw key and their original hashes."""

    capture: object
    capture_hash: int
    cycle: object
    cycle_hash: int
    expected_capture: object
    expected_cycle: object
    parts_plan: object
    cycle_plan: object
    pointer_plans: tuple


def exact(actual, expected):
    pending = [(actual, expected)]
    while pending:
        left, right = pending.pop()
        assert type(left) is type(right), (type(left), type(right))
        if type(right) in (int, bool, str, type(None)):
            assert left == right
        elif hasattr(right, "kind") and hasattr(right, "values"):
            pending.extend(((left.kind, right.kind), (left.values, right.values)))
            assert hash(left) == hash(right)
        elif is_dataclass(right):
            pending.extend(
                (getattr(left, f.name), getattr(right, f.name)) for f in fields(right)
            )
        elif isinstance(right, (tuple, list)):
            assert len(left) == len(right)
            pending.extend(zip(left, right, strict=True))
        elif type(right) is dict:
            assert left.keys() == right.keys()
            pending.extend(((left[key], value) for key, value in right.items()))
        elif type(right) is frozenset:
            assert len(left) == len(right)
            remaining = list(left)
            for item in right:
                matches = [
                    i
                    for i, value in enumerate(remaining)
                    if type(value) is type(item) and value == item
                ]
                assert matches
                pending.append((remaining.pop(matches[0]), item))
        else:
            assert left is right


class Shape(NamedTuple):
    """Expected-only primitive container shape; no actual observations are cached."""

    cls: type
    children: tuple
    uniform: object = None


def cell_shape(value):
    """Recognize only independently predicted coordinate/bit cell sequences."""
    return all(
        type(item) is tuple
        and len(item) == 2
        and type(item[0]) is tuple
        and len(item[0]) == 2
        and set(map(type, item[0])) == {int}
        and type(item[1]) is int
        for item in value
    )


def shape(value):
    cls = type(value)
    if cls in (int, bool, str, type(None)):
        return Shape(cls, ())
    assert cls in (tuple, frozenset)
    if cls is tuple and value and type(value[0]) in (int, bool, str):
        primitive = type(value[0])
        if set(map(type, value)) == {primitive}:
            return Shape(tuple, (), (len(value), primitive))
    if cls is tuple and value and cell_shape(value):
        return Shape(tuple, (), ("cells", len(value)))
    if cls is frozenset:
        assert cell_shape(value)
        return Shape(frozenset, (), "cells")
    return Shape(tuple, tuple(map(shape, value)))


def typed_cells(value):
    """Visit every actual pair, coordinate and bit before whole value comparison."""
    if value:
        assert set(map(type, value)) == {tuple}
        assert set(map(len, value)) == {2}
        points = tuple(map(itemgetter(0), value))
        assert set(map(type, points)) == {tuple}
        assert set(map(len, points)) == {2}
        assert set(map(type, map(itemgetter(0), points))) == {int}
        assert set(map(type, map(itemgetter(1), points))) == {int}
        assert set(map(type, map(itemgetter(1), value))) == {int}


def typed_value(actual, expected, plan):
    """Fresh full type walks precede builtin equality; no actual values are cached."""
    pending = [(actual, plan)]
    while pending:
        value, node = pending.pop()
        assert type(value) is node.cls
        if node.cls is tuple:
            if node.uniform is not None and node.uniform[0] == "cells":
                assert len(value) == node.uniform[1]
                typed_cells(value)
            elif node.uniform is not None:
                size, primitive = node.uniform
                assert len(value) == size
                assert set(map(type, value)) == {primitive}
            else:
                assert len(value) == len(node.children)
                pending.extend(zip(value, node.children, strict=True))
        elif node.cls is frozenset:
            assert node.uniform == "cells"
            typed_cells(value)
    assert actual == expected


def held_capture(entry, context, schema_plan):
    actual = entry.capture
    assert type(actual) is context.snapshot
    assert type(actual.model) is context.model
    typed_value((actual.model.name, actual.model.components), SCHEMA, schema_plan)
    typed_value(actual.parts, entry.expected_capture.parts, entry.parts_plan)


def held_cycle(entry, context):
    actual, expected = entry.cycle, entry.expected_cycle
    assert type(actual) is tuple and len(actual) == 8
    pointers = actual[0]
    assert type(pointers) is tuple and len(pointers) == len(expected[0])
    for pointer, wanted, plan in zip(
        pointers, expected[0], entry.pointer_plans, strict=True
    ):
        assert type(pointer) is context.native._Pointer
        assert vars(pointer).keys() == POINTER_FIELDS
        typed_value(
            (
                pointer.position,
                pointer.previous,
                pointer.channel,
                pointer.value,
                pointer.paused,
            ),
            wanted,
            plan,
        )
    typed_value(actual[1:], expected[1:], entry.cycle_plan)


POINTER_FIELDS = frozenset(("position", "previous", "channel", "value", "paused"))


SCHEMA = (
    "thisthat-v1",
    (
        "pointers",
        "cells",
        "cursor",
        "stopped",
        "input_cursor",
        "input_reads",
        "set_ended",
    ),
)


def pointer_values(actual, context):
    assert type(actual) is tuple
    result = []
    for pointer in actual:
        assert type(pointer) is context.native._Pointer
        assert set(vars(pointer)) == {
            "position",
            "previous",
            "channel",
            "value",
            "paused",
        }
        result.append(
            (
                pointer.position,
                pointer.previous,
                pointer.channel,
                pointer.value,
                pointer.paused,
            )
        )
    return tuple(result)


def capture(row, context):
    return context.snapshot(context.model(*SCHEMA), row.parts())


def io(port, case, row):
    values = vars(port).copy()
    assert type(values["_buffer"]) is StringIO
    assert not values["_buffer"].closed
    values["_buffer"] = values["_buffer"].__getstate__()
    exact(values, model.io_values(case, row))


def construct(case, context):
    provider = FirstDraw(0)
    machine = context.native._Machine(
        list(case.source), context.io(case.stdin), provider
    )
    assert machine.rng is provider
    return machine


def raw_key(row, grid):
    return (
        tuple(tuple(p) for p in row.pointers),
        tuple(sorted(row.cells)),
        row.cursor,
        row.stopped,
        row.offset,
        row.reads,
        grid,
        row.set_ended,
    )


class Observer:
    """Retain exact full observations with independently supplied failure-phase rows."""

    def __init__(
        self,
        case,
        grid,
        context,
        rng_plan=None,
        *,
        history="all",
        window=None,
        wire=True,
    ):
        """Keep one prediction context and actual immutable histories."""
        self.case, self.grid, self.context = case, grid, context
        assert history in ("all", "final", "window")
        assert history != "window" or (type(window) is int and 0 <= window < 8)
        self.history, self.window, self.wire = history, window, wire
        self.rng_plan = rng_plan
        self.schema_plan = shape(SCHEMA)
        self.grid_plan = shape(grid)
        self.random_plan = None
        self.history_pairs = 0
        self.held, self.rows = [], []
        self.meter = self.oracle = None

    def observe(self, raw, row):
        """Check every declared field before sampling the real producer."""
        case, grid, context = self.case, self.grid, self.context
        held = self.held
        meter, oracle = self.meter, self.oracle
        assert set(vars(raw)) == {"io", "rng", "grid", "state", "_input_reads"}
        typed_value(raw.grid, grid, self.grid_plan)
        profile = policies.profile_for("raw")
        if self.rng_plan is not None:
            exact(self.rng_plan.profile, profile)
            exact(tuple(self.rng_plan.events[: len(row.draws)]), row.draws)
            first, state = self.rng_plan.states[len(row.draws)]
        else:
            independent = policies.DrawPlan(profile)
            for upper, value in row.draws:
                exact(independent(upper), value)
            first = independent.first
            state = (
                None if independent.random is None else independent.random.getstate()
            )
        if profile == "none_no_draw":
            assert raw.rng is None
            exact(row.draws, ())
        elif profile == "first0seed0":
            assert type(raw.rng) is FirstDraw
            exact(raw.rng._first, first)
            assert raw.rng._fixed is None
            assert type(raw.rng._rest) is Seeded
            if self.random_plan is None:
                self.random_plan = shape(state)
            typed_value(raw.rng._rest._random.getstate(), state, self.random_plan)
        else:
            assert type(raw.rng) is Seeded
            if self.random_plan is None:
                self.random_plan = shape(state)
            typed_value(raw.rng._random.getstate(), state, self.random_plan)
        assert type(raw.state) is tuple and len(raw.state) == 5
        actual_pointers, actual_cells, actual_cursor, actual_stopped, actual_ended = (
            raw.state
        )
        assert type(actual_cells) is MappingProxyType
        exact(
            pointer_values(actual_pointers, context),
            tuple(tuple(p) for p in row.pointers),
        )
        exact(dict(actual_cells), dict(row.cells))
        exact(tuple(actual_cells), row.cell_order)
        exact(
            (actual_cursor, actual_stopped, actual_ended),
            (row.cursor, row.stopped, row.set_ended),
        )
        exact(raw._input_reads, row.reads)
        exact(raw.halted, row.halted)
        ip = () if not row.pointers else tuple(reversed(row.pointers[0].position))
        exact(raw.ip, ip)
        exact(raw.memory, [value for point, value in sorted(row.cells)])
        exact(raw.stack, [row.cursor, *sorted(row.cells)])
        io(raw.io, case, row)
        actual = raw.workspace_snapshot()
        wanted = capture(row, context)
        key = raw.snapshot()
        expected_key = raw_key(row, grid)
        entry = Held(
            actual,
            hash(actual),
            key,
            hash(key),
            wanted,
            expected_key,
            shape(wanted.parts),
            Shape(
                tuple,
                tuple(
                    self.grid_plan if i == 5 else shape(value)
                    for i, value in enumerate(expected_key[1:])
                ),
            ),
            tuple(shape(tuple(p)) for p in row.pointers),
        )
        held_capture(entry, context, self.schema_plan)
        held_cycle(entry, context)
        if self.wire:
            restored = _state_from_wire(worker_loads(worker_dumps(_state_wire(key))))
            held_cycle(entry._replace(cycle=restored), context)
            assert hash(restored) == hash(key)
        held.append(entry)
        origins = (
            range(len(held))
            if self.history == "all"
            else range(self.window, len(held), 8)
            if self.history == "window"
            else ()
        )
        for origin in origins:
            prior = held[origin]
            held_capture(prior, context, self.schema_plan)
            held_cycle(prior, context)
            exact(hash(prior.capture), prior.capture_hash)
            exact(hash(prior.cycle), prior.cycle_hash)
            self.history_pairs += 1
        if meter is None:
            meter, oracle = context.written(actual), context.oracle(wanted)
        else:
            meter.sample(actual)
            oracle.sample(wanted)
        exact(meter.bits, oracle.bits)
        exact(meter._written, oracle.written)
        exact(
            meter._peaks,
            [
                peak if written else 0
                for peak, written in zip(oracle.peaks, oracle.written, strict=True)
            ],
        )
        self.meter, self.oracle = meter, oracle
        self.rows.append(row)

    def finish(self):
        """Recheck held originals and report the actual meter."""
        held, rows = self.held, self.rows
        case, context = self.case, self.context
        oracle = self.oracle
        for entry, _row in zip(held, rows, strict=True):
            held_capture(entry, context, self.schema_plan)
            held_cycle(entry, context)
            exact(hash(entry.capture), entry.capture_hash)
            exact(hash(entry.cycle), entry.cycle_hash)
        return {
            "history_mode": self.history,
            "history_window": self.window,
            "history_windows": 8 if self.history == "window" else None,
            "native_wire_boundaries": len(rows) if self.wire else 0,
            "history_pairs": self.history_pairs,
            "current_and_final_retention": True,
            "final_held_pairs": len(held),
            "name": case.name,
            "boundaries": len(rows),
            "steps": rows[-1].successful,
            "output": rows[-1].output,
            "halted": rows[-1].halted,
            "peak_bits": oracle.bits,
            "peaks": oracle.peaks,
            "written": oracle.written,
        }


def trace(case, context, *, history=None, window=None, wire=True):
    profile = policies.profile_for("raw")
    grid, rows, plan = policies.predict(case, profile)
    calls = []
    original = context.native.draw

    def audited(source, upper):
        value = original(source, upper)
        assert type(value) is int and 0 <= value < upper
        calls.append((source, upper, value))
        return value

    with patch.object(context.native, "draw", audited):
        raw = construct(case, context)
        if history is None:
            history = "final" if case.name == "kolakoski" else "all"
        observer = Observer(
            case, grid, context, plan, history=history, window=window, wire=wire
        )
        for index, row in enumerate(rows):
            if index:
                raw.step()
            assert all(source is raw.rng for source, _upper, _value in calls)
            exact(tuple((upper, value) for _source, upper, value in calls), row.draws)
            observer.observe(raw, row)
    result = observer.finish()
    result.update(
        profile=profile, draw_log=[[upper, value] for _source, upper, value in calls]
    )
    return result
