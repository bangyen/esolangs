"""Complete old bounded raw-command cases and full allocated-tape accounting."""

import pytest

from esolangs.languages.brainfuck.interpreter import _Machine
from esolangs.languages.brainfuck.tests.full_oracle import legacy_prediction, predict
from tests.interpreters.semantic_oracles import STDINS, bracket_pairs
from tests.support import workspace_oracle as workspace

MODEL = workspace.workspace_model(
    "brainfuck-v1", "instruction pointer tape input_cursor"
)


def cases(corpus):
    """Retain1670 old invocations, every old tail literal, and the old hint."""
    for stdin in [*STDINS, "Ā", "ā"]:
        for source in corpus():
            yield source, stdin, 200
    yield from (
        ("+" * 256 + ".", "", 257),
        ("-.", "", 200),
        (",.", "λ", 200),
        ("+[]", "", 200),
        (",", "", 200),
        ("][", "", 200),
        ("[", "", 200),
    )


def check(factory, source, stdin, cap=200):
    """Require exact independent code, allocation, cursor and snapshot types."""
    expected = legacy_prediction(source, stdin, cap)
    brackets = None if expected[0] == "syntax" else bracket_pairs(source)

    def state(machine):
        assert type(machine.code) is str
        assert machine.code == source
        assert type(machine.size) is int
        assert machine.size == len(source)
        assert type(machine.brackets) is dict
        assert all(
            type(k) is int and type(v) is int for k, v in machine.brackets.items()
        )
        assert machine.brackets == brackets
        assert type(machine.state) is tuple
        pc, ptr, tape = machine.state
        assert type(pc) is int
        assert type(ptr) is int
        assert type(tape) is tuple
        assert all(type(v) is int for v in tape)
        pc, ptr, tape, cursor = machine.workspace_snapshot().parts
        assert type(pc) is int
        assert type(ptr) is int
        assert type(tape) is tuple
        assert all(type(v) is int for v in tape)
        assert type(cursor) is int
        return machine.state

    return workspace.agrees(
        expected,
        (factory, source, stdin),
        (MODEL, lambda row: (*row[0], row[-1])),
        state,
        cap=cap,
    )


def _boolean_capture(factory, field):
    class Fault(factory):
        def workspace_snapshot(self):
            saved = super().workspace_snapshot()
            values = list(saved.parts)
            values[field] = (False, *values[field][1:]) if field == 2 else False
            return type(saved)(saved.model, tuple(values))

    return Fault


def check_workspace_brainfuck(corpus):
    """Preserve every old case and reject all four real field-type corruptions."""
    for source, stdin, cap in cases(corpus):
        check(_Machine, source, stdin, cap)
    source, stdin = ",>+<.", "\x81"
    check(_Machine, source, stdin)
    error, rows = predict(source, stdin)
    assert error is None
    assert rows[-1].output == "\x81"
    assert workspace.charged_bits(MODEL, (row.parts for row in rows)) == 14
    workspace.check_erasures(MODEL, check, _Machine, source, stdin)
    for field in range(4):
        with pytest.raises(AssertionError):
            check(_boolean_capture(_Machine, field), source, stdin)
