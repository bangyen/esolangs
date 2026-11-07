"""Revision 196168 deque rules; repo conventions supply jump-0 errors and dumps."""

import itertools
import random

import pytest

from esolangs.languages.bitdeque.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.oracle_support import observed
from tests.support.workspace_oracle import (
    charged_bits,
    missing_workspace,
    workspace_view,
)

_WORKSPACE = WorkspaceModel(
    "bitdeque-v2", ("instruction", "register", "deque", "rendered", "input_cursor")
)

_CAP = 64


def _model(code, _stdin="λ\nunused", cap=_CAP):
    words, commands = code.split(), []
    while words:
        word = words.pop(0)
        if word == "GOTO" and words and words[0].isdecimal():
            commands.append((word, words.pop(0)))
        elif word in {"PUSH", "INJECT", "POP", "EJECT", "INVERT"}:
            commands.append((word, None))
        else:
            return "syntax", []
    queue, register, pc, rendered, output = [], False, 0, False, ""

    def view():
        return (
            pc,
            int(register),
            tuple(queue),
            pc >= len(commands),
            rendered,
            output,
            0,
            0,
        )

    trace, error = [view()], None
    for _ in range(cap):
        if pc >= len(commands):
            break
        command, operand = commands[pc]
        next_pc = pc + 1
        if command == "INVERT":
            register = not register
        elif command == "PUSH":
            queue.append(int(register))
        elif command == "INJECT":
            queue.insert(0, int(register))
        elif command == "POP":
            register = bool(queue.pop()) if queue else False
        elif command == "EJECT":
            register = bool(queue.pop(0)) if queue else False
        elif register:
            try:
                target = int(operand)
            except ValueError:
                trace.append(view())
                return "syntax", trace
            if target == 0:
                error = "target"
            else:
                next_pc = target - 1
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if not error and pc >= len(commands):
        for _ in range(3):
            if not rendered:
                output = " ".join(str(bit) for bit in queue)
                rendered = True
            trace.append(view())
    return error, trace


def _observed(machine_type, code, predicted, stdin, cap):
    standard = [((*r[:3], r[4]), r[3], *r[5:]) for r in predicted]

    def state(machine):
        assert machine.io.reads == machine.io.past_end == 0
        return tuple(machine.state)

    checked = workspace_view(standard, _WORKSPACE, lambda r: (*r[0], r[-1]), state)
    error, rows = observed(machine_type, code, stdin, checked, cap=cap)
    trace = [(*r[0][:3], r[1], r[0][3], *r[2:]) for r in rows if r[0] is not None]
    return "target" if error == "halt" else error, trace


def _agrees(machine_type, code, stdin="λ\nunused", cap=_CAP):
    expected = _model(code, stdin, cap)
    assert _observed(machine_type, code, expected[1], stdin, cap) == expected, code
    return expected


def corpus():
    atoms = (
        "PUSH",
        "INJECT",
        "POP",
        "EJECT",
        "INVERT",
        "GOTO 0",
        "GOTO 1",
        "GOTO 2",
        "GOTO 9",
    )
    codes = [" ".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    codes += [
        rng.choice((" ", "\t", "\n")).join(rng.choices(atoms, k=12)) for _ in range(256)
    ]
    codes += [
        "INVERT PUSH INVERT INJECT",
        "INVERT PUSH PUSH INVERT INJECT",
        "INVERT PUSH PUSH INVERT PUSH",
        "INVERT PUSH INVERT PUSH EJECT PUSH",
        "INVERT PUSH INVERT PUSH POP PUSH",
        "INVERT PUSH INVERT PUSH POP",
        "GOTO",
        "GOTO -1",
        "GOTO +1",
        "GOTO1",
        "PUSHPOP",
        "push",
        "PUSH FROB",
        "PUSH GOTO",
        "GOTO 1x",
        "INVERT GOTO \u0660",
        "INVERT GOTO \u0662",
        "GOTO\n\uff19",
        "INVERT GOTO " + "9" * 100,
        "\n\t",
    ]
    yield from ((code, "λ\nunused", _CAP) for code in codes)
    for code in (
        "PUSH " * 81,
        "INVERT " + "INJECT " * 81,
        "INVERT " + "PUSH " * 81 + "POP EJECT " * 41,
        "GOTO " + "9" * 5000,
        "INVERT GOTO " + "9" * 5000,
        "GOTO\u2028٢ PUSH",
        "INVERT GOTO 2",
    ):
        yield code, "\U0001f600\r\n", 192


def check_raw_bitdeque():
    results = [_agrees(_Machine, *case) for case in corpus()]
    assert {error for error, _ in results} == {None, "syntax", "target"}
    assert any(not trace[-1][3] for error, trace in results if not error)
    assert _model("INVERT PUSH INVERT INJECT")[1][-1][2:6] == (
        (0, 1),
        True,
        True,
        "0 1",
    )
    assert _model("INVERT PUSH INVERT PUSH POP")[1][-1][1:3] == (0, (1,))
    for code, bits in (("", 1), ("PUSH", 3), ("INVERT PUSH", 5), ("PUSH " * 81, 89)):
        trace = _model(code, cap=192)[1]
        assert charged_bits(_WORKSPACE, ((*r[:3], r[4], r[-1]) for r in trace)) == bits
    probe = _Machine("PUSH", ScriptedIO("unused"))
    probe.step()
    cycle_key = probe.snapshot()
    assert probe.io.getvalue() == ""
    probe.step()
    assert (probe.snapshot(), probe.io.getvalue()) == (cycle_key, "0")
    probe.step()
    assert (probe.snapshot(), probe.io.getvalue()) == (cycle_key, "0")

    controls = {
        "end": "INVERT PUSH INVERT PUSH",
        "empty": "INVERT POP",
        "jump": "INVERT GOTO 3 PUSH",
        "dump": "INVERT PUSH",
        "input": "PUSH",
        "syntax": "FROB PUSH",
    }
    for fault, code in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                super().__init__(
                    code.replace("FROB", "") if self.mode == "syntax" else code, io
                )

            def step(self):
                if self.halted:
                    super().step()
                    if self.mode == "dump":
                        self.render()
                    return
                command = self.tokens[self.ind]
                if self.mode == "end" and command == "PUSH":
                    self.state = self.state._replace(
                        ind=self.ind + 1, deq=(self.reg, *self.deq)
                    )
                elif self.mode == "empty" and command == "POP" and not self.deq:
                    self.state = self.state._replace(ind=self.ind + 1)
                elif self.mode == "jump" and command.startswith("GOTO") and self.reg:
                    self.state = self.state._replace(ind=int(command.split()[1]))
                else:
                    if self.mode == "input":
                        self.io.input_char()
                    super().step()

        with pytest.raises(AssertionError):
            _agrees(Fault, code)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), "INVERT PUSH")
