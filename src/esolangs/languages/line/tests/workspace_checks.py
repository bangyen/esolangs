"""Line's two hand-derived fixture graphs, full bounded state and workspace."""

from typing import NamedTuple

import pytest

from esolangs.exceptions import ArgumentError, InputExhaustedError
from esolangs.languages.line.interpreter import _Machine
from esolangs.languages.line.interpreter.simulate import _Frame
from esolangs.runtime._state import WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import assert_exact
from tests.support.workspace_oracle import (
    WorkspaceWitness,
    check_erasures,
    workspace_model,
)

from .full_oracle import GRAPHS, model, provider_refusal_history, writer_refusal_history
from .oracle_checks import _fixture, arithmetic_terminal, fixture_cases

_WORKSPACE = workspace_model("line-v1", "node instruction pointer cells input_cursor")


class _Held(NamedTuple):
    state: tuple
    hashed: int
    captured: WorkspaceSnapshot
    capture_hash: int


def _boundary(machine, frames, row, stdin, witness, held):
    assert type(machine.program) is tuple
    assert len(machine.program) == len(frames)
    for actual, expected in zip(machine.program, frames, strict=True):
        assert type(actual) is _Frame
        values = (
            actual.ops[actual.offset :],
            actual.positions[actual.offset :],
            actual.end,
            actual.zero,
            actual.nonzero,
            actual.goto,
        )
        assert_exact(values, tuple(expected))
    assert_exact(
        (*machine.cursor, tuple(sorted(machine.tape.items()))), tuple(row["raw"])
    )
    assert_exact(machine.snapshot(), row["cycle"])
    assert_exact(machine.ip, row["ip"])
    assert_exact(machine.memory, row["memory"])
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
    assert_exact(values, expected)
    assert_exact(
        io._buffer.__getstate__(), (row["output"], "\n", len(row["output"]), None)
    )
    captured = machine.workspace_snapshot()
    assert type(captured) is WorkspaceSnapshot
    assert captured.model == _WORKSPACE
    assert_exact(captured.parts, row["workspace"])
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
    last = rows[-1]
    cursor = last["position"]
    assert (
        error,
        (last["raw"][2:], last["halted"], last["output"], cursor, cursor),
    ) == (arithmetic_terminal(example, stdin))
    return _drive(factory, example, stdin, rows, error)


def _refusals(example):
    stdin = "5\n5 99"
    for rows in writer_refusal_history(GRAPHS[example], stdin):
        failed = next(i for i, row in enumerate(rows) if "raised" in row)
        ordinary = model(GRAPHS[example], stdin)[1]
        payload = int(ordinary[failed]["output"][len(ordinary[failed - 1]["output"]) :])
        prefix = rows[failed]["output"][len(ordinary[failed - 1]["output"]) :]
        writes = []

        class Refusal(_Machine):
            def __init__(self, source, io, *, expected_prefix=prefix, calls=writes):
                super().__init__(source, io)
                original = io._write

                def write(value):
                    calls.append(value)
                    if len(calls) == 1:
                        io._buffer.write(expected_prefix)
                        raise ValueError("physical numeric write refused")
                    return original(value)

                io._write = write

        _drive(Refusal, example, stdin, rows, None)
        text = str(payload)
        retry = [text[len(prefix) :] if prefix else payload] if prefix != text else []
        assert_exact(tuple(writes), (payload, *retry))
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
    cases = tuple(fixture_cases())
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
