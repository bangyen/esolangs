"""Independent assignment and snapshot regressions."""

import itertools

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.vandevelo import _Machine
from tests.interpreters import vandevelo_observer as probe


@pytest.mark.parametrize("shard", range(20))
def test_finite_assignments(shard):
    arrows = ("->", "-!>", "~>", "~!>")
    expressions = (
        "Nil?",
        "Inp?",
        "Inp? == Nil?",
        "Inp? != Nil?",
        "Inp? == Inp?",
        "Inp? != Inp?",
        "Inp? != Nil? == Inp?",
    )
    inputs = tuple(itertools.product(("", "0", " ", "1", "yes"), repeat=2))
    cases = []
    for arrow, expression, values in itertools.product(arrows, expressions, inputs):
        cases.append((f"x {arrow} {expression}\nx? :: missing?", values))
    for a, b, values in itertools.product(arrows, arrows, inputs):
        cases.append((f"x {a} Inp?\ny {b} x?\nx ~!> Nil?\ny? :: missing?", values))
    for source, values in cases[shard::20]:
        probe.check(source, values)


def test_program_identity():
    left = _Machine("Nil?", ScriptedIO())
    right = _Machine("missing?", ScriptedIO())
    assert left.snapshot() != right.snapshot()
    left.step()
    assert left.halted
    with pytest.raises(ValueError, match="undefined"):
        right.step()


def test_cursorless_input_progress():
    class Cursorless(ScriptedIO):
        def position(self):
            return 0

    machine = _Machine("Inp?\nInp?", Cursorless("0\n1\n"))
    before = machine.snapshot()
    machine.step()
    one = machine.snapshot()
    machine.step()
    assert len({before, one, machine.snapshot()}) == 3
    assert machine.snapshot()[2] == 2


@pytest.mark.parametrize(
    "values", itertools.product(("", "0", " ", "1", "yes"), repeat=2)
)
def test_lazy_access_rereads_input(values):
    probe.check("x -> Inp?\nx? == x? :: missing?", values)


@pytest.mark.parametrize("name", ["0", "_", "&", "*", "$", "a9_&*$"])
def test_names_and_comments(name):
    probe.check(f"-- ignored\n{name}~!>Nil? -- true\n{name}? :: missing?", ())
