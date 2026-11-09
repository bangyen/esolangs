"""Line's two hand-derived fixture graphs, full bounded state and workspace."""

from itertools import product
from typing import NamedTuple

import pytest

from esolangs.exceptions import ArgumentError, InputExhaustedError
from esolangs.languages.line.interpreter import _Machine
from esolangs.languages.line.interpreter.simulate import _Frame
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from tests.support.workspace_oracle import (
    WorkspaceWitness,
    check_erasures,
    workspace_model,
)

from .full_oracle import GRAPHS, model, provider_refusal_history, writer_refusal_history
from .oracle_checks import _fixture

_WORKSPACE = workspace_model("line-v1", "node instruction pointer cells input_cursor")


class _Held(NamedTuple):
    state: tuple
    hashed: int
    captured: WorkspaceSnapshot
    capture_hash: int


def _typed(value):
    if type(value) in (int, bool, str, type(None)):
        return type(value), value
    if type(value) is tuple:
        return tuple, tuple(map(_typed, value))
    if type(value) is frozenset:
        return frozenset, frozenset(map(_typed, value))
    raise TypeError(type(value))


def _boundary(machine, frames, row, stdin, witness, held):
    assert type(machine.program) is tuple
    assert len(machine.program) == len(frames)
    for actual, expected in zip(machine.program, frames, strict=True):
        assert type(actual) is _Frame
        values = (
            actual.ops,
            actual.positions,
            actual.end,
            actual.zero,
            actual.nonzero,
            actual.goto,
        )
        assert _typed(values) == _typed(tuple(expected))
    assert _typed(machine.state) == _typed(tuple(row["raw"]))
    assert _typed(machine.snapshot()) == _typed(row["cycle"])
    assert _typed(machine.ip) == _typed(row["ip"])
    assert _typed(machine.memory) == _typed(row["memory"])
    assert machine.halted is row["halted"]
    io = machine.io
    values = (
        io.getvalue(),
        io.position(),
        io.progress(),
        io.reads,
        io.past_end,
        io._character_reads,
        io._newline,
        io._line_reads,
        io._pending,
        io._consumed,
        io._source,
        io.supplied,
    )
    expected = (
        row["output"],
        row["position"],
        row["position"],
        row["reads"],
        row["past_end"],
        row["character_reads"],
        row["newline"],
        0,
        "",
        row["position"],
        stdin,
        stdin.count("\n") + int(bool(stdin) and not stdin.endswith("\n")),
    )
    assert _typed(values) == _typed(expected)
    assert _typed(io._buffer.__getstate__()) == _typed(
        (row["output"], "\n", len(row["output"]), None)
    )
    captured = machine.workspace_snapshot()
    assert type(captured) is WorkspaceSnapshot
    assert captured.model == _WORKSPACE
    assert _typed(captured.parts) == _typed(row["workspace"])
    witness.sample(captured, row["workspace"])
    snapshot = machine.snapshot()
    held.append(_Held(snapshot, hash(snapshot), captured, hash(captured)))
    assert all(
        hash(item.state) == item.hashed and hash(item.captured) == item.capture_hash
        for item in held
    )


def _drive(factory, example, stdin, rows, error):
    machine = factory(_fixture(example), ScriptedIO(stdin))
    witness, held = WorkspaceWitness(_WORKSPACE), []
    for index, row in enumerate(rows):
        if index:
            if "raised" in row:
                with pytest.raises(
                    ValueError,
                    match=r"write refused|input refused",
                ) as caught:
                    machine.step()
                assert type(caught.value) is ValueError
            elif error is not None and index == len(rows) - 1:
                kind = InputExhaustedError if error == "input" else ArgumentError
                with pytest.raises(kind) as caught:
                    machine.step()
                assert type(caught.value) is kind
            else:
                machine.step()
        _boundary(machine, GRAPHS[example], row, stdin, witness, held)
    witness.finish()
    return witness.expected


def _check(factory, example, stdin):
    error, rows = model(GRAPHS[example], stdin, cap=1000)
    if error is None:
        assert rows[-1]["halted"]
    return _drive(factory, example, stdin, rows, error)


def _refusals(example):
    stdin = "3\n2 99"
    for rows in writer_refusal_history(GRAPHS[example], stdin):
        failed = next(i for i, row in enumerate(rows) if "raised" in row)
        ordinary = model(GRAPHS[example], stdin)[1]
        payload = int(ordinary[failed]["output"][len(ordinary[failed - 1]["output"]) :])
        prefix = rows[failed]["output"]

        class Refusal(_Machine):
            def __init__(
                self, source, io, *, expected_payload=payload, expected_prefix=prefix
            ):
                super().__init__(source, io)
                original, calls = io._write, []

                def write(value):
                    assert type(value) is int
                    assert value == expected_payload
                    calls.append(value)
                    if len(calls) == 1:
                        io._buffer.write(expected_prefix)
                        raise ValueError("physical numeric write refused")
                    return original(value)

                io._write = write

        _drive(Refusal, example, stdin, rows, None)
    _, rows = provider_refusal_history(GRAPHS[example], stdin)

    class Provider(_Machine):
        def __init__(self, source, io):
            super().__init__(source, io)
            original, calls = io.input_num, []

            def read(*args, **kwargs):
                calls.append(None)
                if len(calls) == 1:
                    raise ValueError("input refused before delegate")
                return original(*args, **kwargs)

            io.input_num = read

    _drive(Provider, example, stdin, rows, None)


def check_accounting_line():
    """Check all92 full traces, five erasures and physical IO commit/retry."""
    cases = [
        (name, f"{a}\n{b} 99")
        for name, a, b in product(("addition", "multiplication"), range(6), range(6))
    ]
    cases.extend(
        product(
            ("addition", "multiplication"),
            (
                "",
                " \n",
                "1",
                "1\n",
                "bad",
                "1 bad",
                "1_0 2",
                "٣ 2",
                "0 0",
                " 5\t+5\r\n",
            ),
        )
    )
    assert len(cases) == 92
    for example, stdin in cases:
        oracle = _check(_Machine, example, stdin)
        if stdin == "3\n2 99":
            assert oracle.written == [True] * 5
            assert oracle.bits == (14 if example == "addition" else 25)
            assert oracle.peaks == (
                [2, 3, 1, 6, 2] if example == "addition" else [4, 3, 2, 14, 2]
            )
    check_erasures(_WORKSPACE, _check, _Machine, "addition", "3\n2 99")
    for example in ("addition", "multiplication"):
        _refusals(example)
