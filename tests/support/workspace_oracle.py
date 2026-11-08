"""Full component recounts, independent of benchmark delta accounting."""

from dataclasses import fields, is_dataclass
from fractions import Fraction

import pytest

from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from scripts.benchmark import WrittenState
from tests.interpreters.oracle_support import observed


class WorkspaceOracle:
    """Sum each written component's largest complete width, including its start."""

    def __init__(self, snapshot):
        self.start = snapshot.parts
        self.model = snapshot.model
        self.memo = {}
        self.peaks = [self.width(part) for part in self.start]
        self.written = [False] * len(self.start)

    def width(self, value):
        """Count only semantic payload; never inspect Python backing capacity."""
        if value is None:
            return 0
        if isinstance(value, int):
            return 1 if value == 0 else abs(value).bit_length() + (value < 0)
        if isinstance(value, (str, bytes)):
            return 8 * len(value)
        if isinstance(value, float):
            return 64
        hit = self.memo.get(id(value))
        if hit is not None and hit[0] is value:
            return hit[1]
        if isinstance(value, WorkspaceVariant):
            children = value.values
        elif isinstance(value, Fraction):
            children = (value.numerator, value.denominator)
        elif isinstance(value, (tuple, frozenset)):
            children = value
        elif hasattr(value, "delta"):
            children = tuple(value.items())
        elif is_dataclass(value) and value.__dataclass_params__.frozen:
            children = tuple(getattr(value, field.name) for field in fields(value))
        else:
            raise TypeError(f"undeclared workspace payload: {type(value)}")
        total = sum(self.width(child) for child in children)
        self.memo[id(value)] = (value, total)
        return total

    def sample(self, snapshot):
        """Recount complete components without deltas or previous-sample shortcuts."""
        assert snapshot.model == self.model
        for index, part in enumerate(snapshot.parts):
            self.written[index] |= part != self.start[index]
            self.peaks[index] = max(self.peaks[index], self.width(part))

    @property
    def bits(self):
        return sum(
            peak
            for peak, written in zip(self.peaks, self.written, strict=True)
            if written
        )


def charged_bits(model, parts):
    """Recount a predicted trace with the same component validation as capture."""
    snapshots = (
        model.capture(**dict(zip(model.components, row, strict=True))) for row in parts
    )
    oracle = WorkspaceOracle(next(snapshots))
    for snapshot in snapshots:
        oracle.sample(snapshot)
    return oracle.bits


class WorkspaceWitness:
    """Compare captures and charged peaks against an independently stepped model."""

    def __init__(self, model):
        self.model = model
        self.measured = None
        self.expected = None
        self.previous = None
        self.history = []

    def sample(self, captured, parts):
        reference = WorkspaceSnapshot(self.model, parts)
        if self.previous is not None:
            previous, saved = self.previous
            assert previous == saved
        assert captured == reference
        if self.measured is None:
            self.measured = WrittenState(captured)
            self.expected = WorkspaceOracle(reference)
        else:
            self.measured.sample(captured)
            self.expected.sample(reference)
        assert self.measured.bits == self.expected.bits
        self.previous = captured, reference
        self.history.append(self.previous)

    def finish(self):
        """Check all retained captures after the final modeled boundary."""
        assert all(captured == reference for captured, reference in self.history)


def missing_workspace(factory, component):
    """Erase one charged component without changing execution or state views."""

    class Fault(factory):
        def workspace_snapshot(self):
            captured = super().workspace_snapshot()
            parts = list(captured.parts)
            parts[captured.model.components.index(component)] = None
            return WorkspaceSnapshot(captured.model, tuple(parts))

    return Fault


def workspace_view(trace, model, parts, view):
    """Check predicted resources alongside each independently modeled state view."""
    expected = iter(trace)
    witness = WorkspaceWitness(model)
    pending = next(expected, None)

    def observe(machine):
        nonlocal pending
        predicted = pending
        assert predicted is not None, "machine exceeded its independently modeled trace"
        assert predicted[0] is not None or predicted[1]
        witness.sample(machine.workspace_snapshot(), parts(predicted))
        pending = next(expected, None)
        if pending is None:
            witness.finish()
        return view(machine)

    return observe


def workspace_model(name, components):
    """Declare ordered component names separated by spaces."""
    return WorkspaceModel(name, tuple(components.split()))


def agrees(expected, execution, workspace, state, *, context=None, **options):
    factory, code, stdin = execution
    model, parts = workspace
    checked = workspace_view(expected[1], model, parts, state)
    assert observed(factory, code, stdin, checked, **options) == expected, (
        (code, stdin) if context is None else context
    )
    return expected


def check_erasures(model, check, factory, *args, **options):
    for component in model.components:
        with pytest.raises(AssertionError):
            check(missing_workspace(factory, component), *args, **options)


def checker(predict, workspace, state):
    """Bind a two-input predictor to fixed independent component and state views."""

    def check(factory, source, stdin):
        expected = predict(source, stdin)
        return agrees(expected, (factory, source, stdin), workspace, state)

    return check
