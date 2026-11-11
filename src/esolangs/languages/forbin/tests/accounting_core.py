"""Root-only finite Forbin workspace preflight; exact cycle wire remains pending."""

# Actual private records/callbacks are deliberate observer and corruption controls.
# ruff: noqa: N806, PT017
from copy import deepcopy
from io import StringIO
from types import MappingProxyType
from typing import NamedTuple
from unittest.mock import patch

from .accounting_grammar import Reader
from .accounting_model import Closure, Machine, Port
from .accounting_projections import io_blueprint


class Context(NamedTuple):
    """Runtime names bound only after the fatal startup guard and package pins."""

    native: object
    scripted_io: object
    variant: object
    snapshot: object
    model: object
    input_eof: object
    written: object
    oracle: object


class NativeTypes(NamedTuple):
    """Actual record classes; never used to derive expected state."""

    state: object
    frame: object
    scope: object
    closure: object


class Row(NamedTuple):
    """Independent state/IO after one constructor, command, or post-halt idle."""

    machine: object
    port: object
    error: str | None


class Held(NamedTuple):
    """Only actual immutable workspace captures; no raw snapshot side effects."""

    capture: object
    digest: int


def exact(actual, expected):
    assert type(actual) is type(expected), (type(actual), type(expected))
    if type(expected) in (tuple, list):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected, strict=True):
            exact(left, right)
    elif type(expected) is frozenset:
        # Recursive tags preserve primitive types inside unordered bindings.
        assert frozenset(tagged(v) for v in actual) == frozenset(
            tagged(v) for v in expected
        )
    else:
        assert type(expected) in (int, bool, str, type(None)), type(expected)
        assert actual == expected, (actual, expected)


def tagged(value):
    if type(value) in (int, bool, str, type(None)):
        return type(value).__name__, value
    if type(value) in (tuple, list):
        return type(value).__name__, tuple(tagged(v) for v in value)
    if type(value) is frozenset:
        return "frozenset", frozenset(tagged(v) for v in value)
    raise TypeError(type(value))


def expected_parts(parts, variant):
    """Hydrate declared variant positions, preserving user binding tuples."""

    def node(pair):
        kind, payload = pair
        if kind in ("global", "function", "reference", "input", "output"):
            return variant(kind, payload)
        if kind == "closure":
            return variant(kind, (node(payload[0]), node(payload[1])))
        if kind == "loop":
            rows, names, index, started, position = payload
            return variant(
                kind,
                (
                    tuple(tuple(value(v) for v in row) for row in rows),
                    names,
                    index,
                    started,
                    position,
                ),
            )
        if kind == "frame":
            function, reference, position, loop = payload
            return variant(
                kind,
                (
                    node(function),
                    node(reference),
                    position,
                    None if loop is None else node(loop),
                ),
            )
        if kind == "environment":
            function, parent, bindings = payload
            return variant(
                kind,
                (
                    node(function),
                    None if parent is None else node(parent),
                    frozenset((name, value(v)) for name, v in bindings),
                ),
            )
        raise ValueError(kind)

    def value(item):
        return item if type(item) is int else node(item)

    frames, environments, cursor, bits, reads = parts
    return (
        tuple(node(frame) for frame in frames),
        tuple(node(environment) for environment in environments),
        cursor,
        bits,
        reads,
    )


def check_parts(actual, expected, variant):
    assert type(actual) is type(expected)
    if type(expected) is variant:
        exact(actual.kind, expected.kind)
        check_parts(actual.values, expected.values, variant)
    elif type(expected) is tuple:
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected, strict=True):
            check_parts(left, right, variant)
    elif type(expected) is frozenset:

        def token(item):
            if type(item) is variant:
                return "variant", item.kind, token(item.values)
            if type(item) is tuple:
                return "tuple", tuple(token(v) for v in item)
            return tagged(item)

        assert frozenset(token(v) for v in actual) == frozenset(
            token(v) for v in expected
        )
    else:
        exact(actual, expected)


class Code:
    """Compare independently parsed code to actual readonly fields and aliases."""

    def __init__(self, native_function):
        """Retain the independently bound function/site alias correspondence."""
        self.native_function = native_function
        self.by_site = {}
        self.by_identity = {}
        self.checked = set()
        self.closures = set()

    def function(self, actual, expected):
        assert type(actual) is self.native_function
        site = None if expected is None else expected.site
        assert self.by_site.setdefault(site, actual) is actual
        assert self.by_identity.setdefault(id(actual), site) == site
        if id(actual) in self.checked:
            return
        self.checked.add(id(actual))
        exact(actual.site, site)
        exact(actual.name, "$globals" if expected is None else expected.name)
        exact(actual.args, () if expected is None else tuple(expected.args))
        assert type(actual.body) is tuple
        assert type(actual.nested) is MappingProxyType
        wanted_body = () if expected is None else expected.body
        wanted_nested = () if expected is None else expected.nested
        assert len(actual.body) == len(wanted_body)
        for left, right in zip(actual.body, wanted_body, strict=True):
            self.statement(left, right)
        exact(list(actual.nested), [name for name, _ in wanted_nested])
        for name, function in wanted_nested:
            self.function(actual.nested[name], function)

    def value(self, actual, expected):
        assert type(actual) is tuple
        kind = expected[0]
        exact(
            actual[0],
            {"bit": "lit", "name": "var", "function": "fnlit"}.get(kind, kind),
        )
        if kind in ("bit", "name"):
            exact(actual, (actual[0], expected[1]))
        elif kind == "function":
            assert len(actual) == 2
            self.function(actual[1], expected[1])
        elif kind == "not":
            assert len(actual) == 2
            self.value(actual[1], expected[1])
        elif kind == "call":
            assert len(actual) == 3
            self.value(actual[1], expected[1])
            assert type(actual[2]) is tuple
            assert len(actual[2]) == len(expected[2])
            for left, right in zip(actual[2], expected[2], strict=True):
                self.value(left, right)
        else:
            raise ValueError(kind)

    def pattern(self, actual, expected):
        if expected is None:
            exact(actual, ("*",))
        else:
            assert type(actual) is tuple
            assert len(actual) == 2
            exact(actual[0], "value")
            self.value(actual[1], expected)

    def spec(self, actual, expected):
        assert type(actual) is tuple
        if expected[0] == "range":
            assert len(actual) == 4
            exact(actual[:2], expected[:2])
            self.value(actual[2], expected[2])
            self.value(actual[3], expected[3])
            return
        assert expected[0] == "rows"
        _, names, groups = expected
        assert len(actual) == 3
        exact(actual[0], "iter")
        exact(actual[1], tuple(names))
        assert type(actual[2]) is tuple
        assert len(actual[2]) == len(groups)
        for left, right in zip(actual[2], groups, strict=True):
            if len(names) == 1:
                assert len(right) == 1
                self.pattern(left, right[0])
            else:
                assert type(left) is tuple
                assert len(left) == 2
                exact(left[0], "group")
                assert type(left[1]) is tuple
                assert len(left[1]) == len(right)
                for item, wanted in zip(left[1], right, strict=True):
                    self.pattern(item, wanted)

    def statement(self, actual, expected):
        assert type(actual) is tuple
        assert len(actual) == len(expected)
        exact(actual[0], expected[0])
        if expected[0] == "return":
            self.value(actual[1], expected[1])
        elif expected[0] == "assign":
            exact(actual[1], tuple(expected[1]))
            assert type(actual[2]) is tuple
            assert len(actual[2]) == len(expected[2])
            for left, right in zip(actual[2], expected[2], strict=True):
                self.value(left, right)
        elif expected[0] == "for":
            self.spec(actual[1], expected[1])
            assert type(actual[2]) is tuple
            assert len(actual[2]) == len(expected[2])
            for left, right in zip(actual[2], expected[2], strict=True):
                self.statement(left, right)
        elif expected[0] == "call":
            self.value(actual, expected)
        else:
            raise ValueError(expected[0])


def check_io(actual, expected):
    wanted = io_blueprint(expected)
    assert set(vars(actual)) == set(wanted)
    for name, value in wanted.items():
        if name == "_buffer":
            assert type(actual._buffer) is StringIO
            assert not actual._buffer.closed
            exact(actual._buffer.__getstate__(), value)
        else:
            exact(getattr(actual, name), value)


def check_state(actual, expected, code, scope_types):
    """Validate live reachable graph; dead backing-store allocations stay out."""
    NativeState, NativeFrame, NativeScope, NativeClosure = scope_types
    state = actual.state
    assert type(state) is NativeState
    assert type(state.frames) is tuple
    assert type(state.scopes) is MappingProxyType
    assert len(state.frames) == len(expected.state.frames)
    exact(state.bits, expected.state.bits)
    exact(state.reads, expected.state.reads)
    pending, forward, reverse = [], {}, {}

    def reference(native_id, model_id):
        assert type(native_id) is int
        assert type(model_id) is int
        assert forward.setdefault(model_id, native_id) == native_id
        assert reverse.setdefault(native_id, model_id) == model_id
        if (native_id, model_id) not in pending:
            pending.append((native_id, model_id))

    def value(left, right):
        if type(right) is Closure:
            assert type(left) is NativeClosure
            code.closures.add(id(left))
            code.function(left.fn, right.function)
            reference(left.scope, right.environment)
        else:
            exact(left, right)

    reference(actual._global_scope, 0)
    for left, right in zip(state.frames, expected.state.frames, strict=True):
        assert type(left) is NativeFrame
        code.function(left.fn, right.function)
        reference(left.scope, right.environment)
        exact(
            (
                left.pos,
                left.for_names,
                left.for_ind,
                left.for_started,
                left.for_body_pos,
            ),
            (
                right.position,
                right.names,
                right.index,
                right.started,
                right.body_position,
            ),
        )
        if right.rows is None:
            assert left.for_rows is None
        else:
            assert type(left.for_rows) is tuple
            assert len(left.for_rows) == len(right.rows)
            for row, wanted in zip(left.for_rows, right.rows, strict=True):
                assert type(row) is tuple
                assert len(row) == len(wanted)
                for item, entry in zip(row, wanted, strict=True):
                    value(item, entry)
    cursor = 0
    while cursor < len(pending):
        native_id, model_id = pending[cursor]
        left, right = state.scopes[native_id], expected.state.environments[model_id]
        assert type(left) is NativeScope
        assert type(left.locals) is MappingProxyType
        code.function(left.fn, right.function)
        if right.parent is None:
            assert left.parent is None
        else:
            reference(left.parent, right.parent)
        exact(list(left.locals), list(right.values))
        for name, item in right.values.items():
            value(left.locals[name], item)
        cursor += 1
    return len(pending)


def predict(record):
    """Finish independent bounded prediction before native construction."""
    program, port = Reader(record["source"]).program(), Port(record["stdin"])
    machine, rows = None, []
    try:
        machine = Machine(program, port)
    except EOFError:
        exact(port.output, record["output"])
        return program, [Row(None, deepcopy(port), "EOFError")]
    rows.append(Row(deepcopy(machine), deepcopy(port), None))
    for _ in range(200):
        if machine.halted:
            break
        try:
            machine.step()
        except EOFError:
            rows.append(Row(deepcopy(machine), deepcopy(port), "EOFError"))
            break
        rows.append(Row(deepcopy(machine), deepcopy(port), None))
    else:
        raise AssertionError(("unproved finite fixture", record))
    if machine.halted:
        for _ in range(3):
            machine.step()
            rows.append(Row(deepcopy(machine), deepcopy(port), None))
    exact(port.output, record["output"])
    return program, rows


def run(records, route, context):
    """Run one raw/prepared leaf; context is bound after guarded target import."""
    native, ScriptedIO, Variant, Snapshot, Model, InputEOF, Written, Oracle = context
    from esolangs.languages.forbin.interpreter._parse import _Function
    from esolangs.languages.forbin.interpreter._scope import (
        _Closure,
        _Frame,
        _Scope,
        _State,
    )

    assert route in ("raw", "prepare")
    schema = Model(
        "forbin-v1",
        ("frames", "scopes", "input_cursor", "buffered_bits", "input_reads"),
    )
    details, all_held = [], []
    for record in records:
        program, rows = predict(record)
        if "name" in record:
            exact(rows[-1].error, record.get("error"))
        port = ScriptedIO(record["stdin"])
        raw, constructor_error = None, None
        try:
            raw = (
                native._Machine(record["source"], port)
                if route == "raw"
                else native.prepare_machine(record["source"], {})(port)
            )
        except InputEOF as error:
            assert type(error) is InputEOF
            constructor_error = "EOFError"
        if rows[0].machine is None:
            assert constructor_error == rows[0].error
            check_io(port, rows[0].port)
            details.append({"boundaries": 0, "constructor_error": constructor_error})
            continue
        assert constructor_error is None
        assert raw is not None
        code = Code(_Function)
        exact(list(raw.globals), [function.name for function in program.functions])
        for function in program.functions:
            code.function(raw.globals[function.name], function)
        meter, oracle, held = None, None, []
        reachable = 0
        for index, row in enumerate(rows):
            error_kind = None
            if index:
                try:
                    raw.step()
                except InputEOF as error:
                    assert type(error) is InputEOF
                    error_kind = "EOFError"
            exact(error_kind, row.error)
            expected = row.machine
            code.checked.clear()
            assert type(raw.globals) is MappingProxyType
            exact(list(raw.globals), [function.name for function in program.functions])
            for function in program.functions:
                code.function(raw.globals[function.name], function)
            assert set(vars(raw)) == {
                "io",
                "_length",
                "_serials",
                "_next_serial",
                "globals",
                "_global_scope",
                "state",
            }
            assert raw.io is port
            exact(raw._length, len(record["source"]))
            # This observer deliberately never invokes snapshot/_render.
            assert raw._serials == {}
            assert type(raw._serials) is dict
            exact(raw._next_serial, 0)
            exact(raw.halted, expected.halted)
            reachable = max(
                reachable,
                check_state(
                    raw, expected, code, NativeTypes(_State, _Frame, _Scope, _Closure)
                ),
            )
            check_io(port, row.port)
            exact(
                raw.ip,
                tuple(frame.position for frame in expected.state.frames)
                or (len(record["source"]),),
            )
            wanted_memory = (
                []
                if expected.halted
                else [
                    v
                    for v in expected.state.environments[
                        expected.state.frames[-1].environment
                    ].values.values()
                    if type(v) is int
                ]
            )
            exact(raw.memory, wanted_memory)
            wanted = Snapshot(schema, expected_parts(expected.parts(), Variant))
            capture = raw.workspace_snapshot()
            assert type(capture) is Snapshot
            assert type(capture.model) is Model
            exact(capture.model.name, schema.name)
            exact(capture.model.components, schema.components)
            check_parts(capture.parts, wanted.parts, Variant)
            held.append(Held(capture, hash(capture)))
            assert all(hash(item.capture) == item.digest for item in held)
            if meter is None:
                meter, oracle = Written(capture), Oracle(wanted)
            else:
                meter.sample(capture)
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
        all_held.extend(held)
        assert all(hash(item.capture) == item.digest for item in all_held)
        details.append(
            {
                "boundaries": len(rows),
                "constructor_error": None,
                "reachable_environments": reachable,
                "peak_bits": oracle.bits,
                "written": oracle.written,
                "populated_closures": len(code.closures),
                "function_identities": len(code.by_identity),
            }
        )
    return {
        "route": route,
        "records": len(records),
        "details": details,
        "raw_cycle_wire_verified": False,
        "all78_owners": False,
        "accounting_closure": False,
    }


def controls(context, anchor):
    """Natural populated state and actual-producer/code/IO mutation positives."""
    native, scripted, _variant, snapshot, _, _, _, _ = context
    _, rows = predict(anchor)
    initial = rows[0].machine.parts()
    assert all(
        any(row.machine.parts()[field] != initial[field] for row in rows)
        for field in range(5)
    )
    positives, erasures, io_controls, readonly_controls = [], 0, 0, 0
    for route in ("raw", "prepare"):
        positive = run([anchor], route, context)
        assert positive["details"][0]["populated_closures"] > 0
        assert positive["details"][0]["function_identities"] > 1
        assert positive["details"][0]["written"] == [True] * 5
        positives.append(positive)
        original = native._Machine.workspace_snapshot
        for field in range(5):
            saved = []

            def frozen_part(machine, field=field, saved=saved, original=original):
                captured = original(machine)
                if not saved:
                    saved.append(captured.parts[field])
                parts = list(captured.parts)
                parts[field] = saved[0]
                return snapshot(captured.model, tuple(parts))

            with patch.object(native._Machine, "workspace_snapshot", frozen_part):
                try:
                    run([anchor], route, context)
                except AssertionError:
                    erasures += 1
                else:
                    raise AssertionError(
                        ("semantic capture control did not fire", field)
                    )

        source = "main { x=(in 0); }"
        port = scripted("A")
        raw = (
            native._Machine(source, port)
            if route == "raw"
            else native.prepare_machine(source, {})(port)
        )
        expected = Machine(Reader(source).program(), Port("A"))
        raw.step()
        expected.step()
        check_io(port, expected.port)
        saved_reads = port._reads
        exact(saved_reads, 1)
        port._reads = True
        try:
            check_io(port, expected.port)
        except AssertionError:
            io_controls += 1
        else:
            raise AssertionError("bool/int IO corruption was accepted")
        finally:
            port._reads = saved_reads
        check_io(port, expected.port)

        source = "main { out 0,0,0,0,0,0,0,0; }"
        port = scripted("")
        raw = (
            native._Machine(source, port)
            if route == "raw"
            else native.prepare_machine(source, {})(port)
        )
        expected = Reader(source).program()
        code = Code(type(raw.globals["main"]))
        code.function(raw.globals["main"], expected.functions[0])
        raw.globals["main"].body[0][2][-1] = ("lit", 1)
        code.checked.clear()
        try:
            code.function(raw.globals["main"], expected.functions[0])
        except AssertionError:
            readonly_controls += 1
        else:
            raise AssertionError("readonly future mutation was accepted")
        raw.step()
        exact(port.getvalue(), "\x01")
    exact((erasures, io_controls, readonly_controls), (10, 2, 2))
    return {
        "positive_trajectories": positives,
        "actual_capture_erasures": erasures,
        "typed_io_controls": io_controls,
        "readonly_future_controls": readonly_controls,
        "raw_cycle_wire_verified": False,
        "all78_owners": False,
        "accounting_closure": False,
    }
