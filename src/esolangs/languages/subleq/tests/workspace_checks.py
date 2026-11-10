"""All old raw-oracle sources retain independently predicted workspace/history."""

import pytest

from esolangs.languages.subleq.interpreter import _Machine
from esolangs.languages.subleq.tests.full_oracle import legacy_prediction, predict
from tests.interpreters.semantic_oracles import STDINS
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model("subleq-v1", "memory instruction input_cursor")
_WITNESS = "-1 9 0 9 -1 0 9 9 -1 0"
_STDIN = "\x81\x02"


def _state(machine):
    assert type(machine.pc) is int
    assert type(machine.cells) is list
    assert all(type(value) is int for value in machine.cells)
    captured = machine.workspace_snapshot()
    memory, instruction, cursor = captured.parts
    assert type(memory) is tuple
    assert all(type(value) is int for value in memory)
    assert type(instruction) is int
    assert type(cursor) is int
    return tuple(machine.cells), machine.pc


_check = workspace.checker(
    legacy_prediction,
    (_WORKSPACE, lambda row: (*row[0], row[-1])),
    _state,
    cap=200,
)


def cases(corpus):
    """Preserve309 raw rows and all eight old control invocations, in order."""
    for stdin in STDINS:
        for source in corpus():
            yield source, stdin
    for source in ("x", "0", "-2 0 -1", "6 -1 0 6 6 -1 -1"):
        yield source, "\x81"
        yield "0 0 0", ""


def manual_cases():
    """Retain every additional existing literal constructor/run source fixture."""
    yield "x", ""
    yield "0 0", ""
    yield "9 -1 3 10 -1 6 0 0 -1 72 105", ""
    code = "-1 9 3 9 -1 6 0 0 -1 0"
    yield code, "A"
    yield code, ""
    yield "-1 9 3 9 -1 6 10 10 -1 0 0", "A"
    for code in ("-1 -2 0", "-2 0 0", "0 -2 0"):
        yield code, "A"
    yield "10 10 -1", ""


def check_workspace_subleq(corpus):
    """Check the full327-source cohort and three genuine erasures."""
    for source, stdin in (*cases(corpus), *manual_cases()):
        _check(_Machine, source, stdin)
    error, rows = predict(_WITNESS, _STDIN)
    assert error is None
    assert rows[-1].halted
    # Initial memory25bits grows to32, pc peaks3, cursor1; allthree written.
    assert workspace.charged_bits(_WORKSPACE, (row.parts for row in rows)) == 36
    workspace.check_erasures(_WORKSPACE, _check, _Machine, _WITNESS, _STDIN)
    for component in range(3):
        with pytest.raises(AssertionError):
            _check(_boolean_capture(_Machine, component), _WITNESS, _STDIN)


def _boolean_capture(factory, component):
    """Replace an actual initial zero by bool without changing execution."""

    class Fault(factory):
        def workspace_snapshot(self):
            captured = super().workspace_snapshot()
            parts = list(captured.parts)
            if component == 0:
                values = list(parts[0])
                values[values.index(0)] = False
                parts[0] = tuple(values)
            else:
                parts[component] = False
            return type(captured)(captured.model, tuple(parts))

    return Fault
