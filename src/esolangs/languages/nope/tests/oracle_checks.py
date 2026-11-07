"""Revision 193999: one constant-output transition, regardless of source or input."""

import random

import pytest

from esolangs.languages.nope.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import WorkspaceWitness, missing_workspace

_WORKSPACE = WorkspaceModel("nope-v1", ("emitted", "input_cursor"))


def _agrees(factory, source, stdin):
    initial = ((False, 0), False, "", 0, 0)
    final = ((True, 1), True, "Nope.", 0, 0)
    expected = None, [initial, *([final] * 4)]
    views = iter(expected[1])
    witness = WorkspaceWitness(_WORKSPACE)

    def state(m):
        view, _halted, _output, _position, progress = next(views)
        witness.sample(m.workspace_snapshot(), (view[0], progress))
        return m.state, m.ip

    assert observed(factory, source, stdin, state) == expected, (
        source,
        stdin,
    )
    witness.finish()


def check_raw_nope():
    rng = random.Random(20261103)
    sources = ["", "Nope.", "\x00λ\n", "()[]{}", "+-*/", "NOPE."]
    sources += [
        "".join(rng.choices("abcXYZ09[]\x00λ\n", k=length)) for length in range(64)
    ]
    inputs = ("", "unused", "λ\n")
    for source in sources:
        for stdin in inputs:
            _agrees(_Machine, source, stdin)
    for fault in ("empty", "newline", "input", "repeat", "stop"):

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "newline":
                    write = io.print_str
                    io.print_str = lambda text: write(text + "\n")
                super().__init__(code, io)
                if self.mode == "empty" and not code:
                    self.state = True

            def step(self):
                previous = self.state
                if self.mode == "input" and not previous:
                    self.io.input_char()
                super().step()
                if self.mode == "repeat" and previous:
                    self.io.print_str("Nope.")
                elif self.mode == "stop":
                    self.state = False

        with pytest.raises(AssertionError):
            _agrees(Fault, "", "unused")
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), "", "unused")
    return len(sources) * len(inputs), 7
