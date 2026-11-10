"""Full independent Object disoriented IO-family state and resource observer."""

# ruff: noqa: PT017
from dataclasses import fields, is_dataclass
from io import StringIO
from typing import NamedTuple

import esolangs
from esolangs.debugger import make_debugger
from esolangs.results import Completion, CompletionReport, ExecutionResult
from esolangs.runtime._json import worker_dumps, worker_loads
from esolangs.runtime._result_wire import _state_from_wire, _state_wire
from esolangs.vm import _capture_observation, _capture_workspace, make_vm

from . import full_oracle as engine


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


def check_io(port, case, row):
    actual = vars(port).copy()
    assert type(actual["_buffer"]) is StringIO
    assert actual["_buffer"].closed is False
    actual["_buffer"] = actual["_buffer"].__getstate__()
    expected = engine.io_values(case, row)
    assert actual.keys() == expected.keys()
    for key, value in expected.items():
        exact(actual[key], value)


def raw_of(machine, route):
    return (
        machine
        if route in ("raw", "prepare")
        else machine._machine
        if route == "vm"
        else machine.vm._machine
    )


SCHEMA = (
    "object-disoriented-v1",
    ("frames", "store", "extent", "input_bits", "output_bits", "input_cursor"),
)
HALTED = CompletionReport(Completion.HALTED)


def wanted_capture(row, context):
    return context.snapshot(context.model(*SCHEMA), row.parts())


def observation(row, *, finished=False, steps=None):
    return ExecutionResult(
        row.output, row.cursor, row.reads, row.past, HALTED if finished else None, steps
    )


def readonly(raw, program, context):
    assert set(vars(raw)) == {"io", "program", "state"}
    assert type(raw.program) is context.native._Program
    exact(raw.program.codes, program.codes)
    exact(raw.program.one, (1, 0, 0))


def construct(case, route, context):
    source = engine._source(case.operations, case.zero)
    if route in ("raw", "prepare"):
        port = context.io(case.stdin)
        machine = (
            context.native._Machine(source, port)
            if route == "raw"
            else context.native.prepare_machine(source, {})(port)
        )
    else:
        create = make_vm if route == "vm" else make_debugger
        machine = create(
            "Object disoriented",
            esolangs.ProgramArtifact(source, "Object disoriented"),
            stdin=case.stdin,
        )
        port = raw_of(machine, route).io
    return machine, port


class Observer:
    """Full actual snapshots, allocation extent and exact held immutable histories."""

    def __init__(self, case, program, context):
        """Keep one independently declared program and per-trajectory meters."""
        self.case, self.program, self.context, self.held = case, program, context, []
        self.meter = self.oracle = None

    def observe(self, raw, row):
        """Validate semantic fields before sampling any real capture."""
        context = self.context
        readonly(raw, self.program, context)
        assert type(raw.state) is context.native._State
        exact(tuple(raw.state), row.state())
        exact(raw.halted, row.halted)
        exact(raw.ip, None if row.halted else row.frames[0][:2])
        exact(raw.stack, [frame[0] for frame in reversed(row.frames)])
        check_io(raw.io, self.case, row)
        capture = raw.workspace_snapshot()
        expected = wanted_capture(row, context)
        assert type(capture) is context.snapshot
        exact(capture, expected)
        key = raw.snapshot()
        exact(key, row.key())
        restored = _state_from_wire(worker_loads(worker_dumps(_state_wire(key))))
        exact(restored, key)
        assert hash(restored) == hash(key)
        self.held.append(
            Held(capture, hash(capture), key, hash(key), expected, row.key())
        )
        for held in self.held:
            exact(held.capture, held.expected_capture)
            exact(held.cycle, held.expected_cycle)
        assert all(
            hash(h.capture) == h.capture_hash and hash(h.cycle) == h.cycle_hash
            for h in self.held
        )
        if self.meter is None:
            self.meter, self.oracle = context.written(capture), context.oracle(expected)
        else:
            self.meter.sample(capture)
            self.oracle.sample(expected)
        exact(self.meter.bits, self.oracle.bits)
        exact(self.meter._written, self.oracle.written)
        exact(
            self.meter._peaks,
            [
                p if w else 0
                for p, w in zip(self.oracle.peaks, self.oracle.written, strict=True)
            ],
        )


def wrappers(machine, route, row, context):
    vm = machine if route == "vm" else machine.vm
    exact(_capture_workspace(vm), wanted_capture(row, context))
    exact(machine.snapshot(), row.key())
    exact(_capture_observation(vm), observation(row))
    exact(
        (vm.ip, vm.memory, vm.stack, vm.ptr, vm.views),
        (
            None if row.halted else row.frames[0][:2],
            [],
            [frame[0] for frame in reversed(row.frames)],
            None,
            (),
        ),
    )
    exact(
        (
            vm.self_halts,
            vm.steppable_to_answer,
            vm.eof_is_a_value,
            vm.dumps_on_the_post_halt_step,
            vm.ip_shape,
        ),
        (True, True, False, False, "opaque"),
    )
    if route == "debug":
        exact(
            machine.result,
            observation(
                row, finished=row.halted and row.error is None, steps=row.successful
            ),
        )


def input_error(error, case, row, route):
    from esolangs.exceptions import InputExhaustedError

    assert type(error) is InputExhaustedError
    exact(
        (error.reads, error.supplied, error.unit),
        (row.cursor, len(case.stdin), "character"),
    )
    if route not in ("raw", "prepare"):
        exact(error.partial_output, row.output)
        exact(
            error.execution,
            observation(row, steps=row.successful if route == "debug" else None),
        )


def trace(case, route, context):
    from esolangs.exceptions import InputExhaustedError

    program, rows = engine.plan(case)
    machine, port = construct(case, route, context)
    raw, observer = raw_of(machine, route), Observer(case, program, context)
    assert raw.io is port
    for index, row in enumerate(rows):
        caught = None
        if index:
            try:
                machine.step()
            except InputExhaustedError as failure:
                caught = failure
        if row.error:
            input_error(caught, case, row, route)
        else:
            assert caught is None
        observer.observe(raw, row)
        if route in ("vm", "debug"):
            wrappers(machine, route, row, context)
    return {
        "boundaries": len(rows),
        "error": rows[-1].error,
        "steps": rows[-1].successful,
        "peak_bits": observer.oracle.bits,
        "written": observer.oracle.written,
    }


def endpoint(case):
    _program, rows = engine.plan(case)
    return next(row for row in rows if row.error or row.halted)


def public(case, *, bounded, isolated=False):
    from esolangs.exceptions import InputExhaustedError

    row = endpoint(case)
    options = {"max_steps": 512} if bounded else {}
    try:
        result = esolangs.run(
            "Object disoriented",
            engine._source(case.operations, case.zero),
            stdin=case.stdin,
            isolated=isolated,
            timeout=2.0,
            **options,
        )
    except InputExhaustedError as error:
        assert row.error == "input"
        assert type(error) is InputExhaustedError
        exact(
            (error.reads, error.supplied, error.unit),
            (row.cursor, len(case.stdin), "character"),
        )
        exact(error.partial_output, row.output)
        exact(
            error.execution, observation(row, steps=row.successful if bounded else None)
        )
        return {
            "error": "InputExhaustedError",
            "steps": row.successful if bounded else None,
        }
    assert row.error is None
    exact(
        result,
        observation(row, finished=True, steps=row.successful if bounded else None),
    )
    return {"error": None, "steps": row.successful if bounded else None}


def prepared_siblings(context):
    """Two live builds from one factory retain independent full histories and IO."""
    operations = (("write", "input"),) * 8
    cases = [engine.Case(operations, "U"), engine.Case(operations, "\xaa")]
    predictions = [engine.plan(case) for case in cases]
    source = engine._source(operations, "z")
    factory = context.native.prepare_machine(source, {})
    ports = [context.io(case.stdin) for case in cases]
    machines = [factory(port) for port in ports]
    assert machines[0] is not machines[1]
    assert machines[0].io is ports[0]
    assert machines[1].io is ports[1]
    observers = [
        Observer(case, program, context)
        for case, (program, _rows) in zip(cases, predictions, strict=True)
    ]
    histories = [rows for _program, rows in predictions]
    for machine, observer, rows in zip(machines, observers, histories, strict=True):
        observer.observe(machine, rows[0])
    for active, peer in ((0, 1), (1, 0)):
        peer_row = histories[peer][0] if active == 0 else histories[peer][-1]
        for row in histories[active][1:]:
            machines[active].step()
            observers[active].observe(machines[active], row)
            observers[peer].observe(machines[peer], peer_row)
    for active, peer in ((0, 1), (1, 0)):
        machines[active].step()
        observers[active].observe(machines[active], histories[active][-1])
        observers[peer].observe(machines[peer], histories[peer][-1])
    for i in range(2):
        exact(ports[i].getvalue(), cases[i].stdin)
        exact(observers[i].oracle.written, [True] * 6)
    return {
        "same_factory_builds": 2,
        "inputs": [case.stdin for case in cases],
        "outputs": [port.getvalue() for port in ports],
        "successful_commands": [rows[-1].successful for rows in histories],
        "observation_counts": [len(observer.held) for observer in observers],
        "peak_bits": [observer.oracle.bits for observer in observers],
        "written": [observer.oracle.written for observer in observers],
        "active_and_idle_peer_holds": True,
    }
