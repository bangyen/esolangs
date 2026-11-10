"""Compare every retained Fargo capture with a compiled independent expectation.

Only expected immutable projections are compiled. Actual captures are re-read on
all comparisons; no actual snapshot, equality result or native value is cached.
"""

from types import MappingProxyType
from typing import NamedTuple

from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant


class CallablePlan(NamedTuple):
    """All three declared callable fields and its construction-time hash."""

    name: str
    arity: int
    raw: tuple
    digest: int


class ArrayPlan(NamedTuple):
    """Ordered child plans; sharing is preserved for the array DAG."""

    children: tuple
    digest: int


class FramePlan(NamedTuple):
    """All six declared frame fields, plus the derived variant hash."""

    tokens: tuple
    position: int
    name: str
    result: object
    pending: tuple
    bindings: object
    digest: int


class CapturePlan(NamedTuple):
    """The complete schema and five predicted components."""

    name: str
    components: tuple
    parts: tuple


def _compile_value(value, memo):
    if type(value) is int:
        return value
    assert type(value) is WorkspaceVariant
    hit = memo.get(id(value))
    if hit is not None:
        assert hit[0] is value
        return hit[1]
    if value.kind == "callable":
        name, arity, raw = value.values
        assert type(name) is str
        assert type(arity) is int
        assert type(raw) is tuple
        assert all(type(index) is int for index in raw)
        result = CallablePlan(name, arity, raw, value._hash)
    else:
        assert value.kind == "array"
        result = ArrayPlan(
            tuple(_compile_value(child, memo) for child in value.values), value._hash
        )
    memo[id(value)] = value, result
    return result


def _compile_frame(value, memo):
    assert type(value) is WorkspaceVariant
    assert value.kind == "frame"
    tokens, position, name, result, pending, bindings = value.values
    assert type(tokens) is tuple
    assert all(type(token) is str for token in tokens)
    assert type(position) is int
    assert type(name) is str
    assert type(pending) is tuple
    assert type(bindings) is frozenset
    entries = {}
    for key, item in bindings:
        assert type(key) is str
        assert key not in entries
        entries[key] = _compile_value(item, memo)
    return FramePlan(
        tokens,
        position,
        name,
        _compile_value(result, memo),
        tuple(
            (_compile_value(fn, memo), tuple(_compile_value(v, memo) for v in args))
            for fn, args in pending
        ),
        MappingProxyType(entries),
        value._hash,
    )


def compile_capture(expected):
    """Compile only the independently predicted, full Fargo resource projection."""
    assert type(expected) is WorkspaceSnapshot
    assert type(expected.model) is WorkspaceModel
    assert expected.model.name == "fargo-v1"
    assert expected.model.components == (
        "instruction",
        "input_number",
        "output_number",
        "frames",
        "input_cursor",
    )
    instruction, number, output, frames, cursor = expected.parts
    assert all(type(v) is int for v in (instruction, number, output, cursor))
    assert type(frames) is tuple
    memo = {}
    return CapturePlan(
        expected.model.name,
        expected.model.components,
        (
            instruction,
            number,
            output,
            tuple(_compile_frame(frame, memo) for frame in frames),
            cursor,
        ),
    )


def _header(actual, kind, digest, size):
    return (
        type(actual) is WorkspaceVariant
        and type(actual.kind) is str
        and actual.kind == kind
        and type(actual._hash) is int
        and actual._hash == digest
        and type(actual.values) is tuple
        and len(actual.values) == size
    )


def _scalars(actual, expected, kind):
    return (
        type(actual) is tuple
        and len(actual) == len(expected)
        and all(type(value) is kind for value in actual)
        and actual == expected
    )


def _callable_matches(actual, plan):
    if not _header(actual, "callable", plan.digest, 3):
        return False
    name, arity, raw = actual.values
    return (
        type(name) is str
        and name == plan.name
        and type(arity) is int
        and arity == plan.arity
        and _scalars(raw, plan.raw, int)
    )


def _value_matches(actual, plan, seen):
    if type(plan) is int:
        return type(actual) is int and actual == plan
    if type(plan) is CallablePlan:
        return _callable_matches(actual, plan)
    assert type(plan) is ArrayPlan
    if not _header(actual, "array", plan.digest, len(plan.children)):
        return False
    pair = id(actual), id(plan)
    if pair in seen:
        return True
    seen.add(pair)
    return all(
        _value_matches(child, wanted, seen)
        for child, wanted in zip(actual.values, plan.children, strict=True)
    )


def _pending_matches(actual, expected, seen):
    if type(actual) is not tuple or len(actual) != len(expected):
        return False
    for pair, (function, arguments) in zip(actual, expected, strict=True):
        if type(pair) is not tuple or len(pair) != 2:
            return False
        fn, args = pair
        if not _callable_matches(fn, function):
            return False
        if type(args) is not tuple or len(args) != len(arguments):
            return False
        if not all(
            _value_matches(value, plan, seen)
            for value, plan in zip(args, arguments, strict=True)
        ):
            return False
    return True


def _bindings_match(actual, expected, seen):
    if type(actual) is not frozenset or len(actual) != len(expected):
        return False
    if not actual:
        return True
    seen_names = set()
    for pair in actual:
        if type(pair) is not tuple or len(pair) != 2:
            return False
        name, value = pair
        if type(name) is not str or name not in expected or name in seen_names:
            return False
        seen_names.add(name)
        if not _value_matches(value, expected[name], seen):
            return False
    return seen_names == expected.keys()


def _frame_matches(actual, plan, seen):
    if not _header(actual, "frame", plan.digest, 6):
        return False
    tokens, position, name, result, pending, bindings = actual.values
    return (
        _scalars(tokens, plan.tokens, str)
        and type(position) is int
        and position == plan.position
        and type(name) is str
        and name == plan.name
        and _value_matches(result, plan.result, seen)
        and _pending_matches(pending, plan.pending, seen)
        and _bindings_match(bindings, plan.bindings, seen)
    )


def capture_matches(actual, plan):
    """Re-read every actual component and field, including retained captures."""
    if (
        type(actual) is not WorkspaceSnapshot
        or type(actual.model) is not WorkspaceModel
    ):
        return False
    if type(actual.model.name) is not str or actual.model.name != plan.name:
        return False
    if not _scalars(actual.model.components, plan.components, str):
        return False
    if type(actual.parts) is not tuple or len(actual.parts) != 5:
        return False
    instruction, number, output, frames, cursor = actual.parts
    if not all(type(value) is int for value in (instruction, number, output, cursor)):
        return False
    if (instruction, number, output, cursor) != (
        plan.parts[0],
        plan.parts[1],
        plan.parts[2],
        plan.parts[4],
    ):
        return False
    if type(frames) is not tuple or len(frames) != len(plan.parts[3]):
        return False
    seen = set()
    return all(
        _frame_matches(frame, wanted, seen)
        for frame, wanted in zip(frames, plan.parts[3], strict=True)
    )
