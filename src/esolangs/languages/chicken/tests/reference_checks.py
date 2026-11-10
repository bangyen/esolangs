"""Check the independent bounded shared-array trajectories and capture types."""

import math

import pytest

from esolangs.languages.chicken import interpreter as native
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from scripts.benchmark import WrittenState
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import WorkspaceWitness, missing_workspace

from .reference_cases import corpus
from .reference_model import Marker, _typed, model

_MODEL = WorkspaceModel(
    "chicken-v2", ("instruction", "cells", "stopped", "input_cursor")
)
_NAN = float("nan")


def _normalize(value):
    if isinstance(value, float) and math.isnan(value):
        return _NAN
    return tuple(map(_normalize, value)) if isinstance(value, tuple) else value


def _parts(row):
    state, _halted, _output, _position, progress = row
    pointer, values, stopped = state
    cells = tuple(
        ()
        if kind == "marker" and value == "self"
        else _NAN
        if kind == "marker" and value == "nan"
        else value
        for kind, value in values
    )
    return pointer, cells, stopped, progress


def _same(left, right):
    """Keep bool/int distinctions while treating modeled NaN as one value."""
    assert type(left) is type(right)
    if type(left) is tuple:
        assert len(left) == len(right)
        for actual, expected in zip(left, right, strict=True):
            _same(actual, expected)
    elif type(left) is float and math.isnan(left):
        assert math.isnan(right)
    else:
        assert left == right


def agrees(factory, source, stdin, cap, output, error):
    expected, trace = model(source, stdin, cap)
    assert (expected, trace[-1][2]) == (error, output)
    witness, raw_history, raw_meter = WorkspaceWitness(_MODEL), [], None
    predicted = iter(trace)

    def view(machine):
        nonlocal raw_meter
        row = next(predicted)
        captured = machine.workspace_snapshot()
        normalized = WorkspaceSnapshot(captured.model, _normalize(captured.parts))
        raw_history.append((captured, normalized))
        assert type(captured.model) is WorkspaceModel
        _same(captured.model.name, _MODEL.name)
        _same(captured.model.components, _MODEL.components)
        _same(normalized.parts, _parts(row))
        witness.sample(normalized, _parts(row))
        if raw_meter is None:
            raw_meter = WrittenState(captured)
        else:
            raw_meter.sample(captured)
        assert raw_meter.bits == witness.expected.bits
        assert (machine.io.reads, machine.io.past_end) == (1, 0)
        values = tuple(
            Marker.SELF
            if value is native.SELF
            else Marker.NAN
            if isinstance(value, float) and math.isnan(value)
            else value
            for value in machine.cells
        )
        return machine.pointer, tuple(map(_typed, values)), machine.done

    assert observed(factory, source, stdin, view, cap=cap) == (expected, trace)
    witness.finish()
    assert all(
        WorkspaceSnapshot(old.model, _normalize(old.parts)) == saved
        for old, saved in raw_history
    )
    for old, saved in raw_history:
        _same(_normalize(old.parts), saved.parts)
    return expected, trace


def check_raw_chicken_reference():
    cases = list(corpus())
    assert len(cases) <= 200
    results = [agrees(native._Machine, *case) for case in cases]
    assert any(not rows[-1][1] for error, rows in results if error is None)
    witness = ("chicken", "sentinel", 64, "chicken", None)
    agrees(native._Machine, *witness)
    for component in _MODEL.components:
        with pytest.raises(AssertionError):
            agrees(missing_workspace(native._Machine, component), *witness)

    class WrongOutput(native._Machine):
        def __init__(self, code, io):
            write = io.print_str
            io.print_str = lambda text: write("?" * len(text))
            super().__init__(code, io)

    class Overread(native._Machine):
        def __init__(self, code, io):
            io.input_char()
            super().__init__(code, io)

    for factory in (WrongOutput, Overread):
        with pytest.raises(AssertionError):
            agrees(factory, *witness)
    typed_witness = ("chicken", "", 64, "chicken", None)
    agrees(native._Machine, *typed_witness)

    class FalseCursor(native._Machine):
        def workspace_snapshot(self):
            saved = super().workspace_snapshot()
            return WorkspaceSnapshot(saved.model, (*saved.parts[:3], False))

    class IntStopped(native._Machine):
        def workspace_snapshot(self):
            saved = super().workspace_snapshot()
            parts = (*saved.parts[:2], int(saved.parts[2]), saved.parts[3])
            return WorkspaceSnapshot(saved.model, parts)

    for factory in (FalseCursor, IntStopped):
        with pytest.raises(AssertionError):
            agrees(factory, *typed_witness)
    return len(cases), 8
