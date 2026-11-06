"""Full component recounts, independent of benchmark delta accounting."""

from dataclasses import fields, is_dataclass
from fractions import Fraction

from esolangs.runtime._state import WorkspaceSnapshot, WorkspaceVariant
from scripts.benchmark import WrittenState


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
            return max(1, abs(value).bit_length()) + (value < 0)
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


class WorkspaceWitness:
    """Compare captures and charged peaks against an independently stepped model."""

    def __init__(self, model):
        self.model = model
        self.measured = None
        self.expected = None
        self.previous = None

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

    def observe(machine):
        predicted = next(expected)
        assert predicted[0] is not None
        witness.sample(machine.workspace_snapshot(), parts(predicted))
        return view(machine)

    return observe
