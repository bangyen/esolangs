"""Unexecuted populated resource/schema controls for the full Fargo predictor."""

from unittest.mock import patch

from esolangs.runtime._state import WorkspaceSnapshot, WorkspaceVariant
from tests.support.workspace_oracle import WorkspaceOracle

from . import fargo_projections as projections
from . import oracle_checks as checker
from .fargo_corpus import Case, cases
from .fargo_model import CallableValue, model


def expect_mismatch(case, captured):
    checker.check_case(case, wrapped=False, run_public=False)

    class Fault(checker._Machine):
        def workspace_snapshot(self):
            return captured(super().workspace_snapshot())

    try:
        checker.check_case(case, Fault, wrapped=False, run_public=False)
    except AssertionError:
        return
    raise AssertionError("populated capture fault was not rejected")


def rewrite(value, change):
    if isinstance(value, WorkspaceVariant):
        updated = change(value)
        if updated != value:
            return updated
        return WorkspaceVariant(
            value.kind, tuple(rewrite(child, change) for child in value.values)
        )
    if type(value) is tuple:
        return tuple(rewrite(child, change) for child in value)
    if type(value) is frozenset:
        return frozenset(rewrite(child, change) for child in value)
    return value


def check_resources():
    corpus = cases()
    trajectories = []
    for case in corpus:
        rows = model(case.source, case.stdin, case.cap)
        if rows[0].state is not None:
            trajectories.append(
                (case, rows, [projections.snapshot(row) for row in rows])
            )
    counts = {
        "schema": 0,
        "frozen": 0,
        "frame_fields": 0,
        "callables": 0,
        "arrays": 0,
        "caller": 0,
        "pending_order": 0,
        "io": 0,
    }
    schema_case = Case("$", "7 trailing")
    component_controls(trajectories, counts, schema_case)
    frame_controls(trajectories, counts)
    callable_controls(trajectories, counts)
    structure_controls(corpus, counts)
    value_controls(trajectories)
    io_controls(schema_case, counts)
    return counts


def component_controls(trajectories, counts, schema_case):
    for component in range(5):

        def omitted(saved, component=component):
            values = list(saved.parts)
            values[component] = None
            return WorkspaceSnapshot(saved.model, tuple(values))

        expect_mismatch(schema_case, omitted)
        counts["schema"] += 1
    # input_number/input_cursor are readonly after construction. Only these
    # three components have legitimate late writes to freeze.
    for component in (0, 2, 3):
        case, _rows, _captures = next(
            entry
            for entry in trajectories
            if any(
                saved.parts[component] != entry[2][0].parts[component]
                for saved in entry[2][1:]
            )
        )
        held_initial = []

        def frozen(saved, component=component, held_initial=held_initial):
            if not held_initial:
                held_initial.append(saved.parts[component])
            values = list(saved.parts)
            values[component] = held_initial[0]
            return WorkspaceSnapshot(saved.model, tuple(values))

        expect_mismatch(case, frozen)
        counts["frozen"] += 1


def frame_controls(trajectories, counts):
    defaults = ((), 0, "", 0, (), frozenset())
    for field, default in enumerate(defaults):
        case, _rows, _captures = next(
            entry
            for entry in trajectories
            if any(
                frame.values[field] != default
                for saved in entry[2]
                for frame in saved.parts[3]
            )
        )

        def field_changed(node, field=field, default=default):
            if node.kind == "frame" and node.values[field] != default:
                values = list(node.values)
                values[field] = default
                return WorkspaceVariant("frame", tuple(values))
            return node

        def erase_field(saved):
            return WorkspaceSnapshot(saved.model, rewrite(saved.parts, field_changed))

        expect_mismatch(case, erase_field)
        counts["frame_fields"] += 1


def callable_controls(trajectories, counts):
    for field in range(3):

        def eligible(node, field=field):
            return (
                isinstance(node, WorkspaceVariant)
                and node.kind == "callable"
                and (field != 2 or bool(node.values[2]))
            )

        def contains(value):
            if eligible(value):
                return True
            if isinstance(value, WorkspaceVariant):
                return any(contains(child) for child in value.values)
            if type(value) in (tuple, frozenset):
                return any(contains(child) for child in value)
            return False

        case, _rows, _captures = next(
            entry
            for entry in trajectories
            if any(contains(saved.parts) for saved in entry[2])
        )

        def changed_callable(node, field=field):
            if not eligible(node):
                return node
            values = list(node.values)
            values[field] = (
                values[0] + "!" if field == 0 else values[1] + 1 if field == 1 else ()
            )
            return WorkspaceVariant("callable", tuple(values))

        expect_mismatch(
            case,
            lambda saved: WorkspaceSnapshot(
                saved.model, rewrite(saved.parts, changed_callable)
            ),
        )
        counts["callables"] += 1


def structure_controls(corpus, counts):
    array_case = next(case for case in corpus if case.name == "callable-array")

    def lost_array(node):
        return (
            WorkspaceVariant("array", ())
            if node.kind == "array" and node.values
            else node
        )

    expect_mismatch(
        array_case,
        lambda saved: WorkspaceSnapshot(saved.model, rewrite(saved.parts, lost_array)),
    )
    counts["arrays"] += 1
    nested = next(case for case in corpus if case.name == "nested-binds")

    def lost_caller(saved):
        values = list(saved.parts)
        if len(values[3]) > 1:
            values[3] = values[3][1:]
        return WorkspaceSnapshot(saved.model, tuple(values))

    expect_mismatch(nested, lost_caller)
    counts["caller"] += 1
    ordered = next(case for case in corpus if case.name == "three-args-ordered")

    def reordered(node):
        if node.kind != "frame":
            return node
        values = list(node.values)
        values[4] = tuple(
            (fn, tuple(reversed(args)) if len(args) > 1 else args)
            for fn, args in values[4]
        )
        return WorkspaceVariant("frame", tuple(values))

    expect_mismatch(
        ordered,
        lambda saved: WorkspaceSnapshot(saved.model, rewrite(saved.parts, reordered)),
    )
    counts["pending_order"] += 1


def value_controls(trajectories):
    # Own typed values prove empty arrays are not an alias for numeric zero.
    assert projections.resource_value(()) != projections.resource_value(0)
    deep, expected = 1, 1
    for _ in range(5000):
        deep = (deep,)
        expected = WorkspaceVariant("array", (expected,))
    assert projections.resource_value(deep) == expected
    # Resource projection cannot depend on cycle/callable rendering.
    callable_frame = next(
        row
        for _case, rows, _captures in trajectories
        for row in rows
        if any(
            frame.bindings
            and any(isinstance(value, CallableValue) for _, value in frame.bindings)
            for frame in row.state.continuations
        )
    )
    expected_capture = projections.snapshot(callable_frame)
    with patch.object(
        projections, "value_repr", side_effect=AssertionError("render reached resource")
    ):
        assert projections.snapshot(callable_frame) == expected_capture
    literal = Case("$", "0\n")
    rows, native_bits = checker.check_case(literal)
    width = WorkspaceOracle(projections.snapshot(rows[0]))
    for row in rows:
        width.sample(projections.snapshot(row))
    assert width.bits == native_bits == 11


def io_controls(schema_case, counts):
    # Wrong output and a pre-constructor unauthorized read must be visible even
    # when the interpreter's transition data otherwise remains valid.
    changed = []

    class WrongOutput(checker._Machine):
        def __init__(self, source, io):
            original = io.print_num

            def wrong(value):
                changed.append("output")
                return original(value + 1)

            io.print_num = wrong
            super().__init__(source, io)

    class ConstructorRead(checker._Machine):
        def __init__(self, source, io):
            io.input_char()
            changed.append("input")
            super().__init__(source, io)

    checker.check_case(schema_case, wrapped=False, run_public=False)
    for factory in (WrongOutput, ConstructorRead):
        changed.clear()
        try:
            checker.check_case(schema_case, factory, wrapped=False, run_public=False)
        except AssertionError:
            assert changed
            counts["io"] += 1
        else:
            raise AssertionError("output/input observation fault was not rejected")
