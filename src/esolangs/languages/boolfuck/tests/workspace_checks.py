"""Full existing bounded bit-tape corpus, buffers, IO history and typed captures."""

import pytest

from esolangs.languages.boolfuck.interpreter import _Machine
from esolangs.languages.boolfuck.tests.full_oracle import legacy_prediction, predict
from esolangs.runtime.bit_tape import _State
from tests.interpreters.semantic_oracles import STDINS, bracket_pairs
from tests.support import workspace_oracle as workspace

MODEL = workspace.workspace_model("boolfuck-v1", "control ones input_cursor")


def cases(corpus):
    """Keep all695 old oracle invocations, then19 existing literal/lifecycle cases."""
    for stdin in STDINS:
        for code in corpus():
            yield code, stdin, 200
    for code in ("[", "]", ",;" * 8, "+;"):
        yield code, "\x81", 200
        yield "+[]", "", 200
    yield from (
        ("+;", "", 200),
        ("<+;>;<;", "", 200),
        (",;" * 8, "A", 200),
        (",;" * 8, "", 200),
        ("+[,];", "", 200),
        ("ignored text", "", 200),
        ("[", "", 200),
    )
    for bits in range(1, 10):
        yield "+" + ";" * bits + " ", "", bits + 2
    yield from (("+,;", "", 100), (",;" * 9, "\x80", 100), (",;", "Ā", 100))


def check(factory, source, stdin, cap=200):
    """Bind expected code/brackets independently, never copy native program data."""
    expected = legacy_prediction(source, stdin, cap)
    brackets = None if expected[0] else bracket_pairs(source)

    def state(machine):
        assert machine.code == source
        assert type(machine.brackets) is dict
        assert all(
            type(at) is int and type(target) is int
            for at, target in machine.brackets.items()
        )
        assert machine.brackets == brackets
        assert type(machine.state) is _State
        assert all(type(value) is int for value in machine.state)
        assert type(machine.ones) is set
        assert all(type(value) is int for value in machine.ones)
        control, ones, cursor = machine.workspace_snapshot().parts
        assert type(control) is tuple
        assert len(control) == 6
        assert all(type(value) is int for value in control)
        assert type(ones) is frozenset
        assert all(type(value) is int for value in ones)
        assert type(cursor) is int
        return tuple(machine.state), frozenset(machine.ones)

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
            captured = super().workspace_snapshot()
            control, ones, cursor = captured.parts
            if field == 0:
                control = (False, *control[1:])
            elif field == 1 and 0 in ones:
                ones = frozenset(False if at == 0 else at for at in ones)
            elif field == 2:
                cursor = False
            return type(captured)(captured.model, (control, ones, cursor))

    return Fault


def check_workspace_boolfuck(corpus):
    """Preserve714 source/input/bound rows and all three real component controls."""
    for code, stdin, cap in cases(corpus):
        check(_Machine, code, stdin, cap)
    error, rows = predict(",;", "\x81")
    assert error is None
    assert rows[-1].output == "\x01"
    assert workspace.charged_bits(MODEL, (row.parts for row in rows)) == 17
    workspace.check_erasures(MODEL, check, _Machine, ",;", "\x81")
    for field in range(3):
        with pytest.raises(AssertionError):
            check(_boolean_capture(_Machine, field), ",;", "\x81")
