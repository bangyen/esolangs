"""Full declared Packlang scalar workspace, readonly program and IO observer."""

# Private actual fields are the subject of these independent controls.
from dataclasses import fields, is_dataclass
from io import StringIO
from types import MappingProxyType
from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.results import Completion, CompletionReport
from esolangs.runtime._json import worker_dumps, worker_loads
from esolangs.runtime._result_wire import _state_from_wire, _state_wire

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
    """Actual history paired with independent complete values and old hashes."""

    capture: object
    expected_capture: object
    capture_plan: object
    capture_hash: int
    cycle: object
    expected_cycle: object
    cycle_plan: object
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


def readonly(raw, case, context, expected_plan=None):
    if expected_plan is None:
        expected_plan = compile_readonly(case)
    native = context.native
    assert set(vars(raw)) == {"io", "program", "_input_reads", "_program_key", "frames"}
    assert type(raw.program) is native._Program
    program = raw.program
    assert type(program.functions) is MappingProxyType
    assert type(program.dependencies) is MappingProxyType
    assert type(program.globals) is MappingProxyType
    exact(list(program.functions), [("scope", "main")])
    exact(list(program.globals), [("scope", "cell")])
    exact(dict(program.dependencies), {"scope": frozenset({"IO"})})
    function = program.functions[("scope", "main")]
    assert type(function) is native._Function
    assert program.entry is function
    assert type(function.locals) is MappingProxyType
    assert function.locals == {}
    assert value_matches(
        (
            function.name,
            function.package,
            function.params,
            function.body,
            function.uses,
        ),
        expected_plan.function_plan,
    )
    kind = program.globals[("scope", "cell")]
    assert type(kind) is native._Type
    assert value_matches(
        (kind.low, kind.high, kind.under, kind.over, kind.length),
        expected_plan.bounds_plan,
    )
    assert value_matches(raw._program_key, expected_plan.key_plan)
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


def construct(case, context):
    port = context.io(case.stdin)
    machine = context.native._Machine(engine._source(case.kind, case.statements), port)
    return machine, port


class Observer:
    """Recount every modeled part and retain real immutable histories."""

    def __init__(self, case, context):
        """Start one independent complete-history resource meter."""
        self.case, self.context, self.held = case, context, []
        self.meter = self.oracle = None
        self.readonly_plan = compile_readonly(case)

    def observe(self, raw, row):
        """Check actual state before metering or retaining its immutable values."""
        context = self.context
        function = readonly(raw, self.case, context, self.readonly_plan)
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
        capture_plan = compile_capture(expected, context)
        assert capture_matches(actual, capture_plan)
        key = raw.snapshot()
        expected_cycle = cycle_reference(row, self.readonly_plan.program_key)
        cycle_plan = compile_cycle(expected_cycle, self.readonly_plan.key_plan)
        assert value_matches(key, cycle_plan)
        restored = _state_from_wire(worker_loads(worker_dumps(_state_wire(key))))
        assert value_matches(restored, cycle_plan)
        assert hash(restored) == hash(key)
        self.held.append(
            Held(
                actual,
                expected,
                capture_plan,
                hash(actual),
                key,
                expected_cycle,
                cycle_plan,
                hash(key),
            )
        )
        check_held(self.held)
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


def trace(case, context):
    error, rows = engine.plan(case)
    machine, port = construct(case, context)
    observer = Observer(case, context)
    assert machine.io is port
    for index, row in enumerate(rows):
        caught = None
        if index:
            try:
                machine.step()
            except HaltError as failure:
                caught = failure
        if row.error:
            assert type(caught) is HaltError
        else:
            assert caught is None
        observer.observe(machine, row)
    return {
        "boundaries": len(rows),
        "error": error,
        "steps": rows[-1].successful,
        "peak_bits": observer.oracle.bits,
        "written": observer.oracle.written,
    }


def check_held(values):
    """Re-read every old field against its independent model at this boundary."""
    for held in values:
        assert capture_matches(held.capture, held.capture_plan)
        assert value_matches(held.cycle, held.cycle_plan)
        assert hash(held.capture) == held.capture_hash
        assert hash(held.cycle) == held.cycle_hash


def retained_controls(context):
    """Real old captures expose cached-hash and bool/int historical corruption."""
    case = engine.Case("Integer", (("INIT", "cell"), ("write", "cell")), "")
    error, rows = engine.plan(case)
    assert error is None
    positives = corruptions = hash_only_accepts = restored = 0
    for field, replacement in ((2, 1), (4, False)):
        trace(case, context)
        positives += 1
        raw, _ = construct(case, context)
        observer = Observer(case, context)
        observer.observe(raw, rows[0])
        saved = observer.held[0]
        variant = saved.capture.parts[0][0]
        assert type(variant) is context.variant
        assert variant is not saved.expected_capture.parts[0][0]
        original_values = variant.values
        changed = list(original_values)
        changed[field] = replacement
        object.__setattr__(variant, "values", tuple(changed))
        try:
            # These are the exact previous hash-only predicates on the genuine
            # retained object. Neither native state nor model state is assigned.
            assert hash(saved.capture) == saved.capture_hash
            assert hash(saved.cycle) == saved.cycle_hash
            hash_only_accepts += 1
            if field == 4:
                assert saved.capture == saved.expected_capture
            raw.step()
            try:
                observer.observe(raw, rows[1])
            except AssertionError:
                assert len(observer.held) == 2
                corruptions += 1
            else:
                raise AssertionError("old capture corruption escaped full recheck")
        finally:
            object.__setattr__(variant, "values", original_values)
        check_held(observer.held)
        restored += 1
    assert restored == 2
    assert positives == corruptions == hash_only_accepts == 2
    return {
        "canonical_positives": positives,
        "old_capture_corruptions": corruptions,
        "old_hash_only_accepts": hash_only_accepts,
        "restored_positives": restored,
    }


def prepared_siblings(context):
    """One genuine factory supplies two independently modeled full histories."""
    cases = tuple(
        engine.Case("Integer", (("read", "cell"), ("write", "cell")), value)
        for value in ("A", "B")
    )
    predictions = [engine.plan(case) for case in cases]
    assert all(error is None for error, _ in predictions)
    factory = context.native.prepare_machine(
        engine._source(cases[0].kind, cases[0].statements), {}
    )
    ports = [context.io(case.stdin) for case in cases]
    machines = [factory(port) for port in ports]
    first, second = machines
    assert first is not second
    assert first.io is not second.io
    assert first.frames[0] is not second.frames[0]
    observers = [Observer(case, context) for case in cases]
    for index, row in enumerate(predictions[0][1]):
        if index:
            first.step()
        observers[0].observe(first, row)
        observers[1].observe(second, predictions[1][1][0])
    for index, row in enumerate(predictions[1][1]):
        if index:
            second.step()
        observers[1].observe(second, row)
    return {
        "siblings": 2,
        "full_histories": 2,
        "modeled_boundaries": sum(len(rows) for _, rows in predictions),
        "unchanged_sibling_checks": len(predictions[0][1]),
    }


class FramePlan(NamedTuple):
    """All seven scalar-family frame fields and the independent variant hash."""

    package: str
    name: str
    pc: int
    store: object
    result: int
    pending: object
    returned: object
    digest: int


class CapturePlan(NamedTuple):
    """Complete expected schema, declared classes and three components."""

    snapshot_type: type
    model_type: type
    variant_type: type
    name: str
    components: tuple
    frames: tuple
    cursor: int
    reads: int


def compile_capture(expected, context):
    """Compile independently built scalar frames, retaining every field."""
    assert type(expected) is context.snapshot
    assert type(expected.model) is context.model
    assert expected.model.name == SCHEMA[0]
    assert expected.model.components == SCHEMA[1]
    frames, cursor, reads = expected.parts
    assert type(frames) is tuple
    assert type(cursor) is int
    assert type(reads) is int
    plans = []
    for frame in frames:
        assert type(frame) is context.variant
        assert frame.kind == "frame"
        assert type(frame.values) is tuple
        package, name, pc, store, result, pending, returned = frame.values
        assert type(package) is str
        assert type(name) is str
        assert type(pc) is int
        assert type(result) is int
        assert pending is returned is None
        assert type(store) is frozenset
        entries = {}
        for key, value in store:
            assert type(key) is str
            assert type(value) is int
            assert key not in entries
            entries[key] = value
        plans.append(
            FramePlan(
                package,
                name,
                pc,
                MappingProxyType(entries),
                result,
                pending,
                returned,
                hash(frame),
            )
        )
    return CapturePlan(
        context.snapshot,
        context.model,
        context.variant,
        expected.model.name,
        expected.model.components,
        tuple(plans),
        cursor,
        reads,
    )


def value_matches(actual, plan):
    """Read all actual types first, then compare only proven primitive values."""
    if type(plan) is CyclePlan:
        return (
            cycle_types(actual, plan.value, plan.program.body) and actual == plan.value
        )
    if type(plan) is ProgramPlan:
        return program_types(actual, plan.body) and actual == plan.value
    if type(plan) is FunctionPlan:
        return function_types(actual, plan.body) and actual == plan.value
    if type(plan) is BoundsPlan:
        return bounds_types(actual) and actual == plan.value
    pending = [(actual, plan)]
    while pending:
        value, expected = pending.pop()
        kind, payload, _reference = expected
        if type(value) is not kind:
            return False
        if kind is tuple:
            if len(value) != len(payload):
                return False
            pending.extend(zip(value, payload, strict=True))
        elif kind is frozenset:
            if len(value) != len(expected.value):
                return False
            if type(payload) is frozenset:
                if any(type(child) is not str for child in value):
                    return False
            else:
                for pair in value:
                    if type(pair) is not tuple or len(pair) != 2:
                        return False
                    if type(pair[0]) is not str or type(pair[1]) is not int:
                        return False
    # Exact builtin leaf types exclude bool/int aliases and user equality hooks.
    # Thus native tuple/set equality checks every declared value equivalently.
    return actual == plan.value


def store_matches(actual, expected):
    """Read every typed name/value pair; equal bools cannot stand in for ints."""
    if type(actual) is not frozenset or len(actual) != len(expected):
        return False
    names = set()
    for pair in actual:
        if type(pair) is not tuple or len(pair) != 2:
            return False
        key, value = pair
        if type(key) is not str or key not in expected or key in names:
            return False
        names.add(key)
        if type(value) is not int or value != expected[key]:
            return False
    return names == expected.keys()


def frame_matches(actual, plan, variant_type):
    """Read all actual variant and seven logical frame fields each time."""
    if type(actual) is not variant_type:
        return False
    if type(actual.kind) is not str or actual.kind != "frame":
        return False
    if type(actual._hash) is not int or actual._hash != plan.digest:
        return False
    if type(actual.values) is not tuple or len(actual.values) != 7:
        return False
    package, name, pc, store, result, pending, returned = actual.values
    return (
        type(package) is str
        and package == plan.package
        and type(name) is str
        and name == plan.name
        and type(pc) is int
        and pc == plan.pc
        and store_matches(store, plan.store)
        and type(result) is int
        and result == plan.result
        and pending is plan.pending
        and returned is plan.returned
    )


def capture_matches(actual, plan):
    """Read the complete actual schema/capture with no actual/equality cache."""
    if (
        type(actual) is not plan.snapshot_type
        or type(actual.model) is not plan.model_type
    ):
        return False
    if type(actual.model.name) is not str or actual.model.name != plan.name:
        return False
    components = actual.model.components
    if type(components) is not tuple or len(components) != len(plan.components):
        return False
    if (
        any(type(name) is not str for name in components)
        or components != plan.components
    ):
        return False
    if type(actual.parts) is not tuple or len(actual.parts) != 3:
        return False
    frames, cursor, reads = actual.parts
    if (
        type(cursor) is not int
        or cursor != plan.cursor
        or type(reads) is not int
        or reads != plan.reads
    ):
        return False
    if type(frames) is not tuple or len(frames) != len(plan.frames):
        return False
    return all(
        frame_matches(frame, expected, plan.variant_type)
        for frame, expected in zip(frames, plan.frames, strict=True)
    )


class ReadonlyPlan(NamedTuple):
    """One independent immutable program expectation, shared only within a case."""

    program_key: tuple
    key_plan: object
    function_plan: object
    bounds_plan: object


def compile_readonly(case):
    """Compile only the independently declared readonly program once per case."""
    key = engine.program_key(case)
    body = key[0][0][3]
    bounds = key[2][0][1:]
    assert program_types(key, body)
    return ReadonlyPlan(
        key,
        ProgramPlan(key, body),
        FunctionPlan(("main", "scope", (), body, ()), body),
        BoundsPlan(bounds),
    )


def cycle_reference(row, program_key):
    """Keep the exact old independent cycle shape with its readonly tail shared."""
    frames = ()
    if not row.halted:
        pc, store, result = row.frame
        frames = ((("scope", "main", pc, store, result), "None", None),)
    return frames, row.cursor, row.reads, program_key


def compile_cycle(expected, key_plan):
    """Retain the full independent row and precompiled constant program shape."""
    assert expected[3] is key_plan.value
    return CyclePlan(expected, key_plan)


class ProgramPlan(NamedTuple):
    """The independently declared single-function scalar program and body."""

    value: tuple
    body: tuple


class FunctionPlan(NamedTuple):
    """All five independently expected readonly function fields."""

    value: tuple
    body: tuple


class BoundsPlan(NamedTuple):
    """All five independently expected scalar type bounds."""

    value: tuple


class CyclePlan(NamedTuple):
    """The full independent cycle and its readonly scalar program plan."""

    value: tuple
    program: object


def expression_types(actual, expected):
    """Read every exact actual expression type in the admitted scalar grammar."""
    if type(actual) is not tuple or len(actual) != len(expected):
        return False
    if type(actual[0]) is not str:
        return False
    tag = expected[0]
    if tag == "lit":
        return type(actual[1]) is int
    if tag == "var":
        return type(actual[1]) is str
    if tag == "not":
        return expression_types(actual[1], expected[1])
    assert tag == "xor"
    return expression_types(actual[1], expected[1]) and expression_types(
        actual[2], expected[2]
    )


def body_types(actual, expected):
    """Visit all statement fields; primitive equality checks their exact values."""
    if type(actual) is not tuple or len(actual) != len(expected):
        return False
    for statement, reference in zip(actual, expected, strict=True):
        if type(statement) is not tuple or len(statement) != len(reference):
            return False
        if type(statement[0]) is not str:
            return False
        if reference[0] in ("init", "incr", "decr", "read"):
            if type(statement[1]) is not str or statement[2] is not None:
                return False
        elif not expression_types(statement[1], reference[1]):
            return False
    return True


def string_pair(value):
    """Keep both declared name components typed and present."""
    return (
        type(value) is tuple
        and len(value) == 2
        and type(value[0]) is str
        and type(value[1]) is str
    )


def bounds_types(actual):
    """Read all four numeric bounds and the scalar-only length marker."""
    return (
        type(actual) is tuple
        and len(actual) == 5
        and all(type(value) is int for value in actual[:4])
        and actual[4] is None
    )


def function_types(actual, body):
    """Read all readonly function fields without a generic traversal stack."""
    if type(actual) is not tuple or len(actual) != 5:
        return False
    name, package, params, statements, uses = actual
    return (
        type(name) is str
        and type(package) is str
        and type(params) is tuple
        and not params
        and body_types(statements, body)
        and type(uses) is tuple
        and not uses
    )


def program_types(actual, body):
    """Read the complete fixed scalar ProgramKey shape, including every body node."""
    if type(actual) is not tuple or len(actual) != 3:
        return False
    functions, dependencies, globals_ = actual
    if type(functions) is not tuple or len(functions) != 1:
        return False
    function = functions[0]
    if type(function) is not tuple or len(function) != 6:
        return False
    name, package, params, statements, uses, locals_ = function
    if not string_pair(name) or type(package) is not str:
        return False
    if type(params) is not tuple or params:
        return False
    if not body_types(statements, body):
        return False
    if type(uses) is not tuple or uses or type(locals_) is not tuple or locals_:
        return False
    if type(dependencies) is not tuple or len(dependencies) != 1:
        return False
    dependency = dependencies[0]
    if type(dependency) is not tuple or len(dependency) != 2:
        return False
    scope, names = dependency
    if type(scope) is not str or type(names) is not frozenset or len(names) != 1:
        return False
    if any(type(value) is not str for value in names):
        return False
    if type(globals_) is not tuple or len(globals_) != 1:
        return False
    global_type = globals_[0]
    if type(global_type) is not tuple or len(global_type) != 6:
        return False
    return string_pair(global_type[0]) and bounds_types(global_type[1:])


def cycle_types(actual, expected, body):
    """Read all frame, IO and readonly key fields on every retained comparison."""
    if type(actual) is not tuple or len(actual) != 4:
        return False
    frames, cursor, reads, program = actual
    if type(cursor) is not int or type(reads) is not int:
        return False
    if type(frames) is not tuple or len(frames) != len(expected[0]):
        return False
    for frame, reference in zip(frames, expected[0], strict=True):
        if type(frame) is not tuple or len(frame) != 3:
            return False
        key, pending, returned = frame
        if type(pending) is not str or returned is not None:
            return False
        if type(key) is not tuple or len(key) != 5:
            return False
        package, name, pc, store, result = key
        if type(package) is not str or type(name) is not str:
            return False
        if type(pc) is not int or type(result) is not int:
            return False
        if type(store) is not tuple or len(store) != len(reference[0][3]):
            return False
        for pair in store:
            if type(pair) is not tuple or len(pair) != 2:
                return False
            if type(pair[0]) is not str or type(pair[1]) is not int:
                return False
    return program_types(program, body)
