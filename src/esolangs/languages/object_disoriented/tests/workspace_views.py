"""Full independent Object disoriented IO-family state and resource observer."""

from dataclasses import fields, is_dataclass
from io import StringIO
from typing import NamedTuple

from esolangs.results import Completion, CompletionReport
from esolangs.runtime._json import worker_dumps, worker_loads
from esolangs.runtime._result_wire import _state_from_wire, _state_wire

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


SCHEMA = (
    "object-disoriented-v1",
    ("frames", "store", "extent", "input_bits", "output_bits", "input_cursor"),
)
HALTED = CompletionReport(Completion.HALTED)


def wanted_capture(row, context):
    return context.snapshot(context.model(*SCHEMA), row.parts())


def readonly(raw, program, context):
    assert set(vars(raw)) == {"io", "program", "state"}
    assert type(raw.program) is context.native._Program
    exact(raw.program.codes, program.codes)
    exact(raw.program.one, (1, 0, 0))


def construct(case, context):
    port = context.io(case.stdin)
    machine = context.native._Machine(engine._source(case.operations, case.zero), port)
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

    def finish(self):
        """Require every held capture and key unchanged by later steps."""
        # Once per trajectory: re-checking every held value at each step was
        # quadratic, 117,084 comparisons and 9 s profiled for table 0011; a
        # later step's mutation persists to the end, where this catches it.
        for held in self.held:
            exact(held.capture, held.expected_capture)
            exact(held.cycle, held.expected_cycle)
        assert all(
            hash(h.capture) == h.capture_hash and hash(h.cycle) == h.cycle_hash
            for h in self.held
        )


def input_error(error, case, row):
    from esolangs.exceptions import InputExhaustedError

    assert type(error) is InputExhaustedError
    exact(
        (error.reads, error.supplied, error.unit),
        (row.cursor, len(case.stdin), "character"),
    )


def trace(case, context):
    from esolangs.exceptions import InputExhaustedError

    program, rows = engine.plan(case)
    machine, port = construct(case, context)
    observer = Observer(case, program, context)
    assert machine.io is port
    for index, row in enumerate(rows):
        caught = None
        if index:
            try:
                machine.step()
            except InputExhaustedError as failure:
                caught = failure
        if row.error:
            input_error(caught, case, row)
        else:
            assert caught is None
        observer.observe(machine, row)
    observer.finish()
    return {
        "boundaries": len(rows),
        "error": rows[-1].error,
        "steps": rows[-1].successful,
        "peak_bits": observer.oracle.bits,
        "written": observer.oracle.written,
    }
