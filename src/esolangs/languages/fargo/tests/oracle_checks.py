"""Unexecuted raw/VM/debug/public checker for the independent Fargo model."""

# ruff: noqa: PT017 -- Exact raw/wrapped failure phases share one direct observer.

from dataclasses import fields, is_dataclass
from io import StringIO
from types import MappingProxyType

import esolangs
from esolangs.debugger import make_debugger
from esolangs.languages.fargo.interpreter import (
    _Def,
    _Frame,
    _Func,
    _Machine,
    _State,
)
from esolangs.results import Completion, CompletionReport
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_observation, _capture_workspace, make_vm
from tests.support.workspace_oracle import WorkspaceWitness

from . import fargo_projections as projections
from .fargo_capture_comparison import capture_matches, compile_capture
from .fargo_corpus import cases
from .fargo_model import CallableValue, Continuation, State, model, parse

REPORT = CompletionReport(Completion.HALTED)
PUBLIC_TYPE_CONTROLS: list[int] = []


def assert_exact(actual, expected):
    """Compare complete owned records, rejecting bool/int substitutions."""
    pending = [(actual, expected)]
    while pending:
        left, right = pending.pop()
        assert type(left) is type(right)
        if type(right) in (str, int, bool, type(None)):
            assert left == right
        elif is_dataclass(right):
            pending.extend(
                (getattr(left, field.name), getattr(right, field.name))
                for field in fields(right)
            )
        elif isinstance(right, (tuple, list)):
            assert len(left) == len(right)
            pending.extend(zip(left, right, strict=True))
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
            # Only enum members remain in declared completion reports.
            assert left is right


def assert_io(actual, row, stdin):
    """Compare every owned IO field with the independent constructor/output phase."""
    expected = {
        "_source": stdin,
        "_supplied": stdin.count("\n") + int(bool(stdin) and not stdin.endswith("\n")),
        "_offset": row.cursor,
        "_line_reads": 0,
        "_character_reads": row.state is not None,
        "_past_end": row.past_end,
        "_pending": "",
        "_reads": row.reads,
        "_consumed": row.cursor,
        "_newline": bool(row.output),
        "_buffer": (row.output, "\n", len(row.output), None),
    }
    values = vars(actual).copy()
    # WrongOutput deliberately overrides this method; no other extra fields pass.
    if "print_num" in values:
        assert callable(values.pop("print_num"))
    assert values.keys() == expected.keys()
    assert type(values["_buffer"]) is StringIO
    assert not values["_buffer"].closed
    values["_buffer"] = values["_buffer"].__getstate__()
    for key in expected:
        assert_exact(values[key], expected[key])


def actual_value(value):
    """Read exact actual value types; never feed them into the predictor."""
    if type(value) is int:
        return value
    if type(value) is tuple:
        return tuple(actual_value(child) for child in value)
    assert type(value) is _Func
    assert type(value.name) is str
    assert type(value.arity) is int
    assert type(value.raw) is tuple
    assert all(type(index) is int for index in value.raw)
    return CallableValue(value.name, value.arity, value.raw)


def actual_frame(frame):
    assert type(frame) is _Frame
    assert type(frame.tokens) is tuple
    assert all(type(token) is str for token in frame.tokens)
    assert type(frame.pos) is int
    assert type(frame.fn_name) is str
    assert type(frame.pending) is tuple
    pending = []
    for pair in frame.pending:
        assert type(pair) is tuple
        assert len(pair) == 2
        fn, args = pair
        assert type(fn) is _Func
        assert type(args) is tuple
        pending.append((actual_value(fn), tuple(actual_value(arg) for arg in args)))
    assert type(frame.binds) is tuple
    bindings = []
    for pair in frame.binds:
        assert type(pair) is tuple
        assert len(pair) == 2
        name, value = pair
        assert type(name) is str
        bindings.append((name, actual_value(value)))
    return Continuation(
        frame.tokens,
        frame.pos,
        frame.fn_name,
        actual_value(frame.result),
        tuple(pending),
        tuple(bindings),
    )


def public_type_control(actual):
    if type(actual.input_reads) is int and actual.input_reads == 1:
        altered = actual._replace(input_reads=True)
        assert altered == actual
        try:
            assert_exact(altered, actual)
        except AssertionError:
            PUBLIC_TYPE_CONTROLS.append(1)
        else:
            raise AssertionError("real public bool substitution was accepted")


def same_property(expected, actual):
    try:
        value = expected()
    except ValueError as policy_error:
        assert str(policy_error).startswith("Exceeds the limit (")
        try:
            actual()
        except ValueError as caught:
            assert type(caught) is ValueError
            assert str(caught) == str(policy_error)
        else:
            raise AssertionError("expected a host-limited rendering")
    else:
        assert_exact(actual(), value)


def error_type(kind, raw):
    return {
        "syntax": ValueError if raw else esolangs.ProgramError,
        "halt": esolangs.HaltError,
        "limit": ValueError if raw else esolangs.InterpreterLimitError,
        "bounded": esolangs.ExecutionTimeoutError,
    }[kind]


def public(case, rows, *, isolated=False, cap=None):
    cap = case.cap if cap is None else cap
    constructor = rows[0].state is None
    failure = next((i for i, row in enumerate(rows) if row.error), None)
    halt = next((i for i, row in enumerate(rows) if row.halted), None)
    if constructor:
        kind, index, steps = rows[0].error, 0, None
    elif failure is not None and failure <= cap:
        kind, index, steps = rows[failure].error, failure, failure - 1
    elif halt is not None and halt <= cap:
        kind, index, steps = None, halt, halt
    else:
        kind, index, steps = "bounded", cap, cap
    row = rows[index]
    try:
        seen = esolangs.run(
            "Fargo",
            esolangs.ProgramArtifact(case.source, "Fargo"),
            stdin=case.stdin,
            limits=esolangs.ExecutionLimits(
                max_steps=cap, execution_timeout=5 if isolated else None
            ),
            # A timeout selects a worker, which keeps its own digit limit.
            isolated=isolated,
        )
    except esolangs.EsolangError as caught:
        assert kind is not None
        assert type(caught) is error_type(kind, raw=False)
        if kind != "bounded":
            assert str(caught) == row.message
        else:
            assert caught.bound == "max_steps"
        if constructor:
            assert caught.observation is None
            assert caught.partial_output == ""
        else:
            assert caught.partial_output == row.output
            assert_exact(
                caught.observation,
                esolangs.ExecutionResult(
                    row.output, row.cursor, row.reads, row.past_end, None
                )._replace(steps=steps),
            )
        return (
            type(caught).__name__,
            str(caught),
            caught.partial_output,
            caught.observation,
        )
    assert kind is None
    assert_exact(
        seen,
        esolangs.ExecutionResult(
            row.output, row.cursor, row.reads, row.past_end, REPORT
        )._replace(steps=steps),
    )
    public_type_control(seen)
    return seen


def advance_machines(machines, row, successful, routes):
    for route, machine in zip(routes, machines, strict=True):
        try:
            machine.step()
        except Exception as caught:
            assert row.error is not None
            assert type(caught) is error_type(row.error, route == 0)
            assert str(caught) == row.message
            if route:
                seen = caught.observation
                assert caught.partial_output == row.output
                assert seen is not None
                assert_exact(
                    seen,
                    esolangs.ExecutionResult(
                        row.output,
                        row.cursor,
                        row.reads,
                        row.past_end,
                        None,
                        successful if route == 2 else None,
                    ),
                )
        else:
            assert row.error is None


def machine_factories(case, factory, wrapped, wrapped_route):
    """Keep actual route identities separate from contiguous observer positions."""
    io = ScriptedIO(case.stdin)
    factories = [lambda: factory(case.source, io)]
    routes = [0]
    if wrapped:
        artifact = esolangs.ProgramArtifact(case.source, "Fargo")
        if wrapped_route in (None, "vm"):
            factories.append(lambda: make_vm("Fargo", artifact, stdin=case.stdin))
            routes.append(1)
        if wrapped_route in (None, "debug"):
            factories.append(lambda: make_debugger("Fargo", artifact, stdin=case.stdin))
            routes.append(2)
    return io, factories, routes


def check_case(
    case, factory=_Machine, *, wrapped=True, run_public=True, wrapped_route=None
):
    rows = model(case.source, case.stdin, case.cap)
    io, factories, routes = machine_factories(case, factory, wrapped, wrapped_route)
    if rows[0].state is None:
        for route, construct in zip(routes, factories, strict=True):
            try:
                construct()
            except Exception as caught:
                assert type(caught) is error_type(rows[0].error, route == 0)
                assert str(caught) == rows[0].message
                if route:
                    assert caught.observation is None
                    assert caught.partial_output == ""
            else:
                raise AssertionError("invalid definitions read input or constructed")
        assert (io.position(), io.progress(), io.reads, io.past_end, io.getvalue()) == (
            0,
            0,
            0,
            0,
            "",
        )
        assert_io(io, rows[0], case.stdin)
        if run_public:
            public(case, rows)
        return rows, 0
    machines = [construct() for construct in factories]
    raw = machines[0]
    definitions, calls = parse(case.source)
    assert tuple(raw.calls) == calls
    assert {key: (value.params, value.code) for key, value in raw.defs.items()} == {
        key: (value.parameters, value.expression) for key, value in definitions.items()
    }
    witnesses = [WorkspaceWitness(projections.WORKSPACE) for _ in machines]
    held = []
    successful = 0
    for index, row in enumerate(rows):
        if index:
            advance_machines(machines, row, successful, routes)
            if not rows[index - 1].halted and row.error is None:
                successful += 1
        predicted = projections.snapshot(row)
        retained_reference = compile_capture(predicted)
        actual_state = State(
            raw.number, raw.output, raw.ind, tuple(actual_frame(f) for f in raw.frames)
        )
        assert_exact(actual_state, row.state)
        captures = [raw.workspace_snapshot()]
        for wrapped_machine in machines[1:]:
            vm = (
                wrapped_machine.vm
                if hasattr(wrapped_machine, "vm")
                else wrapped_machine
            )
            captures.append(_capture_workspace(vm))
        for route, machine, capture, witness in zip(
            routes, machines, captures, witnesses, strict=True
        ):
            inner = (
                machine.vm._machine
                if route == 2
                else machine._machine
                if route == 1
                else machine
            )
            assert type(inner.state) is _State
            assert type(inner.state.frames) is tuple
            assert type(inner.frames) is list
            assert type(inner.defs) is MappingProxyType
            assert all(type(value) is _Def for value in inner.defs.values())
            assert type(inner.calls) is tuple
            assert_exact(tuple(inner.calls), calls)
            assert_exact(
                tuple(
                    (key, value.name, value.params, value.code)
                    for key, value in inner.defs.items()
                ),
                tuple(
                    (key, value.name, value.parameters, value.expression)
                    for key, value in definitions.items()
                ),
            )
            assert_io(inner.io, row, case.stdin)
            assert machine.halted == row.halted
            same_property(lambda row=row: projections.cycle(row), machine.snapshot)
            assert_exact(capture, predicted)
            witness.sample(capture, predicted.parts)
        for frame, expected in zip(raw.frames, row.state.continuations, strict=True):
            same_property(
                lambda expected=expected, row=row: projections.entry_key(
                    expected, row.cursor
                ),
                lambda frame=frame: raw.frame_entry_key(frame),
            )
        assert (io.getvalue(), io.position(), io.progress(), io.reads, io.past_end) == (
            row.output,
            row.cursor,
            row.cursor,
            row.reads,
            row.past_end,
        )
        for route, wrapped_machine in zip(routes[1:], machines[1:], strict=True):
            vm = (
                wrapped_machine.vm
                if hasattr(wrapped_machine, "vm")
                else wrapped_machine
            )
            seen = _capture_observation(vm)
            assert_exact(
                seen,
                esolangs.ExecutionResult(
                    row.output, row.cursor, row.reads, row.past_end
                ),
            )
            assert type(vm.memory) is list
            assert type(vm.stack) is list
            assert_exact(
                (vm.ip, vm.memory, vm.ptr, [actual_frame(f) for f in vm.stack]),
                (
                    row.state.line,
                    [row.state.number, row.state.output],
                    None,
                    list(row.state.continuations),
                ),
            )
            same_property(
                lambda row=row: projections.debug(row)["views"], lambda vm=vm: vm.views
            )
            if route == 2:
                assert_exact(
                    wrapped_machine.observation,
                    esolangs.ExecutionResult(
                        row.output,
                        row.cursor,
                        row.reads,
                        row.past_end,
                        REPORT if row.halted and row.error is None else None,
                        successful,
                    ),
                )
        assert all(capture_matches(saved, reference) for saved, reference in held)
        held.extend((capture, retained_reference) for capture in captures)
    assert all(capture_matches(saved, reference) for saved, reference in held)
    for witness in witnesses:
        witness.finish()
    if case.legacy_answer is not None:
        last = rows[-1]
        assert last.error is None
        assert last.halted
        assert (
            last.state.number,
            last.state.output,
            last.state.line,
            last.state.continuations,
        ) == (0, case.legacy_answer, 7, ())
        assert (last.output, last.cursor, last.reads, last.past_end) == (
            str(case.legacy_answer),
            1,
            1,
            0,
        )
    if run_public:
        public(case, rows)
    assert witnesses[0].measured is not None
    return rows, witnesses[0].measured.bits


def check_raw_fargo(start=0, stop=266):
    corpus = cases()
    assert len(corpus) == 266
    assert type(start) is int
    assert type(stop) is int
    assert 0 <= start <= stop <= 266
    assert len(corpus[:192]) == 192
    assert all(c.legacy_answer is not None for c in corpus[:192])
    boundaries = 0
    for case in corpus[start:stop]:
        rows, _bits = check_case(case)
        boundaries += len(rows)
    # Existing terminal/fixture/generator assertions remain in their own tests.
    return stop - start, boundaries
