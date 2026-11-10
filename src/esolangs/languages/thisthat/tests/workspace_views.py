"""Root-only full seven-field thisthat state/history observer for fixed wiki cases."""

# ruff: noqa: PT018, FBT003, PT017
from dataclasses import fields, is_dataclass
from io import StringIO
from operator import itemgetter
from types import MappingProxyType
from typing import NamedTuple
from unittest.mock import patch

import esolangs
from esolangs.debugger import make_debugger
from esolangs.results import Completion, CompletionReport, ExecutionResult
from esolangs.runtime._json import worker_dumps, worker_loads
from esolangs.runtime._result_wire import _state_from_wire, _state_wire
from esolangs.runtime.randomness import FirstDraw, Seeded
from esolangs.vm import _capture_observation, _capture_workspace, make_vm

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


def observation(row, *, final=False, steps=None):
    return ExecutionResult(
        row.output,
        row.offset,
        row.reads,
        row.past,
        CompletionReport(Completion.HALTED) if final else None,
        steps,
    )


def io(port, case, row):
    values = vars(port).copy()
    assert type(values["_buffer"]) is StringIO
    assert not values["_buffer"].closed
    values["_buffer"] = values["_buffer"].__getstate__()
    exact(values, model.io_values(case, row))


def raw_of(machine, route):
    return (
        machine
        if route in ("raw", "prepare")
        else machine._machine
        if route == "vm"
        else machine.vm._machine
    )


def construct(case, route, context):
    if route in ("raw", "prepare"):
        port = context.io(case.stdin)
        provider = FirstDraw(0)
        machine = (
            context.native._Machine(list(case.source), port, provider)
            if route == "raw"
            else context.native.prepare_machine(list(case.source), {"rng": provider})(
                port
            )
        )
        assert machine.rng is provider
    else:
        factory = make_vm if route == "vm" else make_debugger
        machine = factory(
            "thisthat",
            esolangs.ProgramArtifact("\n".join(case.source), "thisthat"),
            stdin=case.stdin,
        )
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


def normalized_key(key, context):
    assert type(key) is tuple and len(key) == 8
    return (pointer_values(key[0], context), *key[1:])


def view_text(value):
    if type(value) is tuple and len(value) > 8:
        return repr(value[:8]) + f" +{len(value) - 8} more"
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def pointer_repr(pointer):
    return (
        f"_Pointer(position={pointer.position!r}, previous={pointer.previous!r}, "
        f"channel={pointer.channel!r}, value={pointer.value!r}, "
        f"paused={pointer.paused!r})"
    )


def views(row):
    mapping = dict(row.cells)
    cells = {point: mapping[point] for point in row.cell_order}
    cell_text = "mappingproxy(" + repr(cells) + ")"
    cell_text = cell_text if len(cell_text) <= 60 else cell_text[:57] + "..."
    pointers = (
        "("
        + ", ".join(pointer_repr(p) for p in row.pointers)
        + ("," if len(row.pointers) == 1 else "")
        + ")"
    )
    if len(row.pointers) > 8:
        pointers = (
            "("
            + ", ".join(pointer_repr(p) for p in row.pointers[:8])
            + ")"
            + f" +{len(row.pointers) - 8} more"
        )
    else:
        pointers = pointers if len(pointers) <= 60 else pointers[:57] + "..."
    return (("cells", cell_text), ("cursor", str(row.cursor)), ("pointers", pointers))


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

    def observe(self, machine, raw, route, row):
        """Check every declared field before sampling the real producer."""
        case, grid, context = self.case, self.grid, self.context
        held = self.held
        meter, oracle = self.meter, self.oracle
        assert set(vars(raw)) == {"io", "rng", "grid", "state", "_input_reads"}
        typed_value(raw.grid, grid, self.grid_plan)
        profile = policies.profile_for(route)
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
        if route in ("vm", "debug"):
            vm = machine if route == "vm" else machine.vm
            exact(_capture_workspace(vm), wanted)
            exact(_capture_observation(vm), observation(row))
            exact(normalized_key(machine.snapshot(), context), raw_key(row, grid))
            exact(
                (vm.ip, vm.memory, vm.ptr, vm.stack, vm.views),
                (
                    ip,
                    [value for point, value in sorted(row.cells)],
                    None,
                    [row.cursor, *sorted(row.cells)],
                    views(row),
                ),
            )
            exact(
                (
                    vm.ip_shape,
                    vm.self_halts,
                    vm.eof_is_a_value,
                    vm.dumps_on_the_post_halt_step,
                ),
                ("grid", True, True, False),
            )
            if route == "debug":
                exact(
                    machine.result,
                    observation(
                        row,
                        final=row.halted and row.error is None,
                        steps=row.successful,
                    ),
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


def trace(case, route, context, *, history=None, window=None, wire=True):
    profile = policies.profile_for(route)
    grid, rows, plan = policies.predict(case, profile)
    calls = []
    original = context.native.draw

    def audited(source, upper):
        value = original(source, upper)
        assert type(value) is int and 0 <= value < upper
        calls.append((source, upper, value))
        return value

    with patch.object(context.native, "draw", audited):
        machine = construct(case, route, context)
        raw = raw_of(machine, route)
        if history is None:
            history = "final" if case.name == "kolakoski" else "all"
        observer = Observer(
            case, grid, context, plan, history=history, window=window, wire=wire
        )
        for index, row in enumerate(rows):
            if index:
                machine.step()
            assert all(source is raw.rng for source, _upper, _value in calls)
            exact(tuple((upper, value) for _source, upper, value in calls), row.draws)
            observer.observe(machine, raw, route, row)
    result = observer.finish()
    result.update(
        profile=profile, draw_log=[[upper, value] for _source, upper, value in calls]
    )
    return result


def dispatch(route, context):
    if route == "pure":
        import importlib.util
        from pathlib import Path

        path = Path(__file__).with_name("price-pure.py")
        spec = importlib.util.spec_from_file_location("_thisthat_pure_price", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(
            context.native,
            "_Machine",
            side_effect=AssertionError("pure attempted native"),
        ):
            return module.main()
    assert route in ("raw", "prepare", "vm", "debug")
    return [trace(case, route, context) for case in model.cases()]


def prepared_siblings(context):
    """One genuine source factory owns two complete independent Cat histories."""
    base = model.cases()[1]
    cases = [model.Case("sibling-" + bit, base.source, bit, 256, True) for bit in "01"]
    predictions = [model.predict(case) for case in cases]
    provider = FirstDraw(0)
    factory = context.native.prepare_machine(list(base.source), {"rng": provider})
    ports = [context.io(case.stdin) for case in cases]
    machines = [factory(port) for port in ports]
    assert machines[0] is not machines[1]
    assert machines[0].rng is provider
    assert machines[1].rng is provider
    assert machines[0].io is ports[0]
    assert machines[1].io is ports[1]
    observers = [
        Observer(case, grid, context)
        for case, (grid, _rows) in zip(cases, predictions, strict=True)
    ]
    histories = [rows for _grid, rows in predictions]
    for i in range(2):
        observers[i].observe(machines[i], machines[i], "prepare", histories[i][0])
    for active, peer in ((0, 1), (1, 0)):
        other = histories[peer][0] if active == 0 else histories[peer][-1]
        for row in histories[active][1:]:
            machines[active].step()
            observers[active].observe(
                machines[active], machines[active], "prepare", row
            )
            observers[peer].observe(machines[peer], machines[peer], "prepare", other)
    for active, peer in ((0, 1), (1, 0)):
        machines[active].step()
        observers[active].observe(
            machines[active], machines[active], "prepare", histories[active][-1]
        )
        observers[peer].observe(
            machines[peer], machines[peer], "prepare", histories[peer][-1]
        )
    results = [observer.finish() for observer in observers]
    exact([port.getvalue() for port in ports], ["0", "1"])
    return {
        "same_factory_builds": 2,
        "inputs": ["0", "1"],
        "outputs": ["0", "1"],
        "model_boundaries": [len(rows) for rows in histories],
        "observations": [len(observer.rows) for observer in observers],
        "peak_bits": [result["peak_bits"] for result in results],
        "active_and_idle_peer_holds": True,
    }


def auditor_control(context):
    """Old synthetic two-pointer merge calibrates model request and real delegate."""
    from esolangs.runtime.randomness import FirstDraw

    case = model.Case("manual-merge-auditor", ("▣═◘═◇",), "", 1, False)
    points = (
        model.Pointer((2, 0), (1, 0), "data", 0),
        model.Pointer((2, 0), (3, 0), "data", 1),
    )
    refused = []

    def no_draw(upper):
        refused.append(upper)
        raise AssertionError("independent draw calibration")

    negative = model.Model(case, choose=no_draw)
    negative.pointers = points
    try:
        negative.step()
    except AssertionError as error:
        assert str(error) == "independent draw calibration"
    else:
        raise AssertionError("independent forbidden draw did not fire")
    exact(refused, [2])
    positive = model.Model(case, choose=lambda _upper: 1)
    positive.pointers = points
    positive.step()
    wanted = positive.row()
    exact(
        tuple(tuple(p) for p in wanted.pointers), (((1, 0), (2, 0), "data", 1, False),)
    )
    provider = FirstDraw(1)
    port = context.io("")
    raw = context.native._Machine(list(case.source), port, provider)
    raw.pointers = (
        context.native._Pointer((2, 0), (1, 0), "data", 0),
        context.native._Pointer((2, 0), (3, 0), "data", 1),
    )
    original = context.native.draw
    calls = []

    def audited(rng, upper):
        value = original(rng, upper)
        calls.append((upper, value))
        return value

    with patch.object(context.native, "draw", audited):
        raw.step()
    assert raw.rng is provider
    exact(calls, [(2, 1)])
    exact(normalized_key(raw.snapshot(), context), raw_key(wanted, positive.grid))
    exact(raw.workspace_snapshot(), capture(wanted, context))
    io(port, case, wanted)
    return {
        "scope": "old synthetic calibration, not natural corpus",
        "model_refused_bounds": refused,
        "native_calls": [list(v) for v in calls],
        "expected_next_pointer": [[1, 0], [2, 0], "data", 1, False],
    }


def detached_pointer_control(context):
    """A detached old pointer's False/0 alias must fail fresh typed inspection."""
    case = model.cases()[1]
    grid, rows, _plan = policies.predict(case, "first0seed0")
    machine = construct(case, "raw", context)
    wanted = capture(rows[0], context)
    key = machine.snapshot()
    actual = machine.workspace_snapshot()
    entry = Held(
        actual,
        hash(actual),
        key,
        hash(key),
        wanted,
        raw_key(rows[0], grid),
        shape(wanted.parts),
        shape(raw_key(rows[0], grid)[1:]),
        tuple(shape(tuple(p)) for p in rows[0].pointers),
    )
    held_capture(entry, context, shape(SCHEMA))
    held_cycle(entry, context)
    pointer = key[0][0]
    assert pointer.paused is False
    for _index in range(1, len(rows)):
        machine.step()
        if all(current is not pointer for current in machine.state[0]):
            break
    else:
        raise AssertionError("natural old pointer never detached")
    held_cycle(entry, context)
    before = hash(key)
    object.__setattr__(pointer, "paused", 0)
    try:
        assert hash(key) == before
        try:
            held_cycle(entry, context)
        except AssertionError:
            rejected = True
        else:
            raise AssertionError("paused False/0 alias escaped typed held check")
    finally:
        object.__setattr__(pointer, "paused", False)
    held_cycle(entry, context)
    assert hash(key) == before
    return {
        "canonical_before": True,
        "detached": True,
        "same_hash_alias_rejected": rejected,
        "restored_positive": True,
    }
