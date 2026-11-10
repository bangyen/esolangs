"""Full declared Packlang scalar workspace, readonly program and IO observer."""

# Private actual fields are the subject of these independent controls.
# ruff: noqa: PT017
from dataclasses import fields, is_dataclass
from io import StringIO
from typing import NamedTuple

import esolangs
from esolangs.debugger import make_debugger
from esolangs.exceptions import HaltError
from esolangs.results import Completion, CompletionReport, ExecutionResult
from esolangs.runtime._json import worker_dumps, worker_loads
from esolangs.runtime._result_wire import _state_from_wire, _state_wire
from esolangs.vm import _capture_observation, _capture_workspace, make_vm

from . import full_oracle as engine

SCHEMA = ("packlang-v1", ("frames", "input_cursor", "input_reads"))
HALTED = CompletionReport(Completion.HALTED)


class Context(NamedTuple):
    """Actual constructor and immutable resource classes after guarded bootstrap."""

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
            pending.extend((left[key], value) for key, value in right.items())
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


def wanted_capture(row, context):
    return context.snapshot(
        context.model(*SCHEMA),
        (
            tuple(context.variant("frame", frame) for frame in row.frame_values()),
            row.cursor,
            row.reads,
        ),
    )


def observation(row, *, finished=False, steps=None):
    return ExecutionResult(
        row.output,
        row.cursor,
        row.cursor,
        row.past,
        HALTED if finished else None,
        steps,
    )


def readonly(raw, case, context):
    native = context.native
    assert set(vars(raw)) == {"io", "program", "_input_reads", "_program_key", "frames"}
    assert type(raw.program) is native._Program
    program = raw.program
    assert type(program.functions) is dict
    assert type(program.dependencies) is dict
    assert type(program.globals) is dict
    exact(list(program.functions), [("scope", "main")])
    exact(list(program.globals), [("scope", "cell")])
    exact(program.dependencies, {"scope": frozenset({"IO"})})
    function = program.functions[("scope", "main")]
    assert type(function) is native._Function
    assert program.entry is function
    assert type(function.locals) is dict
    assert function.locals == {}
    exact(
        (
            function.name,
            function.package,
            function.params,
            function.body,
            function.uses,
        ),
        ("main", "scope", (), engine.body(case), ()),
    )
    kind = program.globals[("scope", "cell")]
    assert type(kind) is native._Type
    exact(
        (kind.low, kind.high, kind.under, kind.over, kind.length),
        engine.bounds(case.kind),
    )
    exact(raw._program_key, engine.program_key(case))
    return function


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
        else (machine._machine if route == "vm" else machine.vm._machine)
    )


def construct(case, route, context):
    source = engine._source(case.kind, case.statements)
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
            "Packlang", esolangs.ProgramArtifact(source, "Packlang"), stdin=case.stdin
        )
        port = raw_of(machine, route).io
    return machine, port


class Observer:
    """Recount every modeled part and retain real immutable histories."""

    def __init__(self, case, context):
        """Start one independent complete-history resource meter."""
        self.case, self.context, self.held = case, context, []
        self.meter = self.oracle = None

    def observe(self, raw, row):
        """Check actual state before metering or retaining its immutable values."""
        context = self.context
        function = readonly(raw, self.case, context)
        assert type(raw.frames) is tuple
        assert len(raw.frames) == (0 if row.halted else 1)
        if not row.halted:
            frame = raw.frames[0]
            assert type(frame) is context.native._Frame
            assert frame.func is function
            pc, store, result = row.frame
            exact(
                (frame.pc, frame.store, frame.result, frame.pending, frame.returned),
                (pc, store, result, None, None),
            )
        exact(raw._input_reads, row.reads)
        exact(raw.halted, row.halted)
        exact(raw.ip, 0 if row.halted else row.frame[0])
        exact(raw.memory, [] if row.halted else [value for _, value in row.frame[1]])
        exact(raw.stack, [])
        check_io(raw.io, self.case, row)
        expected = wanted_capture(row, context)
        actual = raw.workspace_snapshot()
        assert type(actual) is context.snapshot
        exact(actual, expected)
        key = raw.snapshot()
        exact(key, engine.cycle(self.case, row))
        restored = _state_from_wire(worker_loads(worker_dumps(_state_wire(key))))
        exact(restored, key)
        assert hash(restored) == hash(key)
        self.held.append(Held(actual, hash(actual), key, hash(key)))
        assert all(
            hash(h.capture) == h.capture_hash and hash(h.cycle) == h.cycle_hash
            for h in self.held
        )
        if self.meter is None:
            self.meter, self.oracle = context.written(actual), context.oracle(expected)
        else:
            self.meter.sample(actual)
            self.oracle.sample(expected)
        exact(self.meter.bits, self.oracle.bits)
        exact(self.meter._written, self.oracle.written)
        exact(
            self.meter._peaks,
            [
                v if w else 0
                for v, w in zip(self.oracle.peaks, self.oracle.written, strict=True)
            ],
        )


def wrappers(machine, route, row, context, case):
    vm = machine if route == "vm" else machine.vm
    exact(_capture_workspace(vm), wanted_capture(row, context))
    exact(machine.snapshot(), engine.cycle(case, row))
    exact(_capture_observation(vm), observation(row))
    exact(vm.ip, 0 if row.halted else row.frame[0])
    exact(vm.memory, [] if row.halted else [value for _, value in row.frame[1]])
    exact(vm.stack, [])
    assert vm.ptr is None
    exact(
        (
            vm.self_halts,
            vm.steppable_to_answer,
            vm.eof_is_a_value,
            vm.dumps_on_the_post_halt_step,
            vm.ip_shape,
        ),
        (True, True, True, False, "offset"),
    )
    if row.halted:
        exact(vm.views, ())
    else:
        raw = raw_of(machine, route)
        function_repr = (
            "<esolangs.languages.packlang.interpreter._parse._Function object at "
            + hex(id(raw.program.entry))
            + ">"
        )
        pc, store, result = row.frame
        text = (
            f"_Frame(func={function_repr}, store={store!r}, pc={pc}, result={result}, "
            "pending=None, returned=None)"
        )
        exact(vm.views, (("frame", text if len(text) <= 60 else text[:57] + "..."),))
    if route == "debug":
        exact(
            machine.result,
            observation(
                row, finished=row.halted and row.error is None, steps=row.successful
            ),
        )


def trace(case, route, context):
    error, rows = engine.plan(case)
    machine, port = construct(case, route, context)
    raw, observer = raw_of(machine, route), Observer(case, context)
    assert raw.io is port
    for index, row in enumerate(rows):
        caught = None
        if index:
            try:
                machine.step()
            except HaltError as failure:
                caught = failure
        if row.error:
            assert type(caught) is HaltError
            if route in ("vm", "debug"):
                exact(caught.partial_output, row.output)
                exact(
                    caught.execution,
                    observation(
                        row, steps=row.successful if route == "debug" else None
                    ),
                )
        else:
            assert caught is None
        observer.observe(raw, row)
        if route in ("vm", "debug"):
            wrappers(machine, route, row, context, case)
    return {
        "boundaries": len(rows),
        "error": error,
        "steps": rows[-1].successful,
        "peak_bits": observer.oracle.bits,
        "written": observer.oracle.written,
    }


def endpoint(case):
    _error, rows = engine.plan(case)
    return next(row for row in rows if row.error is not None or row.halted)


def public(case, *, bounded, isolated=False):
    row = endpoint(case)
    kwargs = {"max_steps": 48} if bounded else {}
    try:
        result = esolangs.run(
            "Packlang",
            engine._source(case.kind, case.statements),
            stdin=case.stdin,
            timeout=2.0,
            isolated=isolated,
            **kwargs,
        )
    except HaltError as error:
        assert row.error == "halt"
        assert type(error) is HaltError
        exact(error.partial_output, row.output)
        exact(
            error.execution, observation(row, steps=row.successful if bounded else None)
        )
        return {"error": "HaltError", "steps": row.successful if bounded else None}
    assert row.error is None
    exact(
        result,
        observation(row, finished=True, steps=row.successful if bounded else None),
    )
    return {"error": None, "steps": row.successful if bounded else None}
