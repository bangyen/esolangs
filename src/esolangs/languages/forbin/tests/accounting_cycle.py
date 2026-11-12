"""Root-only exact Forbin raw-key observer with an independent serial schedule."""

# Raw snapshot tuples deliberately retain the existing six/eight-field wire shape.
# ruff: noqa: N806
from types import MappingProxyType
from typing import NamedTuple

from . import accounting_core as core
from .accounting_model import Closure


class RawClosure(NamedTuple):
    """A validated native closure identity, not its rendering or environment data."""

    function_site: int | None
    environment: int


class Held(NamedTuple):
    """Keep actual raw snapshots, their hashes and the independently checked form."""

    snapshot: tuple
    digest: int
    canonical: tuple


def function_site(function):
    return None if function is None else function.site


def raw_value(value):
    if type(value) is Closure:
        return RawClosure(function_site(value.function), value.environment)
    assert type(value) in (int, str), type(value)
    return value


class Schedule:
    """Allocate fn/site and scope/model-id labels in the declared observation order."""

    def __init__(self):
        """Start once per natural machine, never once per snapshot."""
        self.serials = {}

    def serial(self, kind, identity):
        key = kind, identity
        if key not in self.serials:
            self.serials[key] = len(self.serials)
        return self.serials[key]

    def render(self, value):
        if type(value) is Closure:
            fn = self.serial("fn", function_site(value.function))
            scope = self.serial("scope", value.environment)
            return f"<{value.function.name or 'literal'} {fn}@{scope}>"
        assert type(value) in (int, str), type(value)
        return repr(value)

    def bindings(self, values):
        # Rendering allocates labels while iterating insertion order, BEFORE sort.
        return tuple(
            sorted((name, self.render(value)) for name, value in values.items())
        )

    def scopes(self, machine):
        seen = {}
        pending = [frame.environment for frame in machine.state.frames]
        pending.append(0)
        while pending:
            environment = pending.pop()
            while environment is not None:
                node = machine.state.environments[environment]
                key = self.serial("scope", environment)
                if key in seen:
                    break
                seen[key] = environment
                pending.extend(
                    value.environment
                    for value in node.values.values()
                    if type(value) is Closure
                )
                environment = node.parent
        return tuple(
            (key, self.bindings(machine.state.environments[seen[key]].values))
            for key in sorted(seen)
        )

    def snapshot(self, machine):
        frames = []
        for frame in machine.state.frames:
            # Keep this evaluation sequence: locals, dormant-loop cursor, fn label,
            # then unrendered row records. Neither row conversion nor hashing draws
            # labels or traverses the captured environment's bindings.
            locals_ = self.bindings(
                machine.state.environments[frame.environment].values
            )
            index = frame.index if frame.rows is not None else -1
            position = frame.body_position if frame.rows is not None else -1
            fn = self.serial("fn", function_site(frame.function))
            rows = (
                None
                if frame.rows is None
                else tuple(
                    tuple(raw_value(value) for value in row) for row in frame.rows
                )
            )
            frames.append(
                (
                    frame.function.name,
                    frame.position,
                    locals_,
                    index,
                    position,
                    fn,
                    rows,
                    () if frame.rows is None else frame.names,
                )
            )
        globals_ = self.bindings(machine.state.environments[0].values)
        scopes = self.scopes(machine)
        return (
            tuple(frames),
            machine.port.position,
            machine.state.bits,
            machine.state.reads,
            globals_,
            scopes,
        )


class Bijection:
    """Persistent native identities matched to model identities, never label oracles."""

    def __init__(self, code, types):
        """Retain both directions so identity reuse cannot hide a raw-key change."""
        self.code, self.types = code, types
        self.native_for_model = {}
        self.model_for_native = {}

    def bind(self, raw, expected):
        # Validate full actual fields/code before using any identity as an adapter.
        core.check_state(raw, expected, self.code, self.types)
        pending = []

        def reference(native_id, model_id):
            assert type(native_id) is int
            assert type(model_id) is int
            assert self.native_for_model.setdefault(model_id, native_id) == native_id
            assert self.model_for_native.setdefault(native_id, model_id) == model_id
            if (native_id, model_id) not in pending:
                pending.append((native_id, model_id))

        def value(actual, wanted):
            if type(wanted) is Closure:
                assert type(actual) is self.types.closure
                self.code.function(actual.fn, wanted.function)
                reference(actual.scope, wanted.environment)
            else:
                core.exact(actual, wanted)

        reference(raw._global_scope, 0)
        for actual, wanted in zip(raw.state.frames, expected.state.frames, strict=True):
            reference(actual.scope, wanted.environment)
            if wanted.rows is not None:
                for row, wanted_row in zip(actual.for_rows, wanted.rows, strict=True):
                    for item, wanted_item in zip(row, wanted_row, strict=True):
                        value(item, wanted_item)
        cursor = 0
        while cursor < len(pending):
            native_id, model_id = pending[cursor]
            actual, wanted = (
                raw.state.scopes[native_id],
                expected.state.environments[model_id],
            )
            if wanted.parent is not None:
                reference(actual.parent, wanted.parent)
            for name, item in wanted.values.items():
                value(actual.locals[name], item)
            cursor += 1

    def normalize(self, value):
        if type(value) is self.types.closure:
            assert type(value.fn) is self.code.native_function
            assert id(value.fn) in self.code.by_identity
            assert type(value.scope) is int
            assert value.scope in self.model_for_native
            return RawClosure(
                self.code.by_identity[id(value.fn)], self.model_for_native[value.scope]
            )
        if type(value) is tuple:
            return tuple(self.normalize(item) for item in value)
        assert type(value) in (int, bool, str, type(None)), type(value)
        return value

    def serials(self, raw):
        assert type(raw._serials) is dict
        result = []
        for key, label in raw._serials.items():
            assert type(key) is tuple
            assert len(key) == 2
            kind, identity = key
            assert type(kind) is str
            assert type(identity) is int
            assert type(label) is int
            if kind == "fn":
                assert identity in self.code.by_identity
                canonical = kind, self.code.by_identity[identity]
            else:
                assert kind == "scope"
                assert identity in self.model_for_native
                canonical = kind, self.model_for_native[identity]
            result.append((canonical, label))
        return tuple(result)


def tagged(value):
    if type(value) is RawClosure:
        return "raw_closure", tagged(value.function_site), tagged(value.environment)
    if type(value) is tuple:
        return "tuple", tuple(tagged(item) for item in value)
    assert type(value) in (int, bool, str, type(None)), type(value)
    return type(value).__name__, value


def same(actual, expected):
    assert tagged(actual) == tagged(expected), (actual, expected)


class Observer:
    """Check one actual snapshot call against model-derived labels and raw fields."""

    def __init__(self, program, context):
        """Bind readonly code, one serial schedule and two identity directions."""
        from esolangs.languages.forbin.interpreter._parse import _Function
        from esolangs.languages.forbin.interpreter._scope import (
            _Closure,
            _Frame,
            _Scope,
            _State,
        )

        self.program, self.context = program, context
        self.code = core.Code(_Function)
        self.bijection = Bijection(
            self.code, core.NativeTypes(_State, _Frame, _Scope, _Closure)
        )
        self.schedule = Schedule()
        self.held = []
        self.canonical_seen, self.native_seen = {}, {}
        self.captures = []
        self.meter = self.oracle = None
        self.raw_closure_rows = self.stale_rows = 0

    def check_cache(self, raw):
        core.exact(self.bijection.serials(raw), tuple(self.schedule.serials.items()))
        core.exact(raw._next_serial, len(self.schedule.serials))

    def observe(self, raw, row):
        _, _, Variant, Snapshot, Model, _, Written, Oracle = self.context
        expected = row.machine
        assert expected is not None
        assert set(vars(raw)) == {
            "io",
            "_length",
            "_serials",
            "_next_serial",
            "globals",
            "_global_scope",
            "state",
        }
        core.exact(raw._length, len(self.program.source))
        assert type(raw.globals) is MappingProxyType
        core.exact(list(raw.globals), [fn.name for fn in self.program.functions])
        self.code.checked.clear()
        for function in self.program.functions:
            self.code.function(raw.globals[function.name], function)
        self.bijection.bind(raw, expected)
        core.check_io(raw.io, row.port)
        core.exact(raw.halted, expected.halted)
        core.exact(
            raw.ip,
            tuple(f.position for f in expected.state.frames)
            or (len(self.program.source),),
        )
        memory = (
            []
            if expected.halted
            else [
                item
                for item in expected.state.environments[
                    expected.state.frames[-1].environment
                ].values.values()
                if type(item) is int
            ]
        )
        core.exact(raw.memory, memory)
        schema = Model(
            "forbin-v1",
            ("frames", "scopes", "input_cursor", "buffered_bits", "input_reads"),
        )
        wanted_capture = Snapshot(
            schema, core.expected_parts(expected.parts(), Variant)
        )
        capture = raw.workspace_snapshot()
        assert type(capture) is Snapshot
        assert type(capture.model) is Model
        core.exact(
            (capture.model.name, capture.model.components),
            (schema.name, schema.components),
        )
        core.check_parts(capture.parts, wanted_capture.parts, Variant)
        self.captures.append(core.Held(capture, hash(capture)))
        assert all(hash(saved.capture) == saved.digest for saved in self.captures)
        if self.meter is None:
            self.meter, self.oracle = Written(capture), Oracle(wanted_capture)
        else:
            self.meter.sample(capture)
            self.oracle.sample(wanted_capture)
        core.exact(self.meter.bits, self.oracle.bits)
        core.exact(self.meter._written, self.oracle.written)
        core.exact(
            self.meter._peaks,
            [
                peak if written else 0
                for peak, written in zip(
                    self.oracle.peaks, self.oracle.written, strict=True
                )
            ],
        )
        # Expected allocation is computed before the genuine native observation.
        self.check_cache(raw)
        wanted = self.schedule.snapshot(expected)
        actual = raw.snapshot()
        assert type(actual) is tuple
        canonical = self.bijection.normalize(actual)
        same(canonical, wanted)
        self.check_cache(raw)
        digest = hash(actual)
        if canonical in self.canonical_seen:
            previous = self.canonical_seen[canonical]
            assert actual == previous.snapshot
            assert digest == previous.digest
        if actual in self.native_seen:
            same(canonical, self.native_seen[actual])
        self.held.append(Held(actual, digest, canonical))
        self.canonical_seen[canonical] = self.held[-1]
        self.native_seen[actual] = canonical
        assert all(hash(saved.snapshot) == saved.digest for saved in self.held)
        self.raw_closure_rows += sum(
            type(value) is Closure
            for frame in expected.state.frames
            if frame.rows is not None
            for row_ in frame.rows
            for value in row_
        )
        self.stale_rows += sum(
            frame.rows is not None and not frame.started and frame.body_position > 0
            for frame in expected.state.frames
        )
        return actual
