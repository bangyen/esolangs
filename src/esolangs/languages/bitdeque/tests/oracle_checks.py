"""Revision 196168 deque rules; repo conventions supply jump-0 errors and dumps."""

import itertools
import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.bitdeque.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO

_CAP = 64


def _model(code):
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
    for _ in range(_CAP):
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
            if int(operand) == 0:
                error = "target"
            else:
                next_pc = int(operand) - 1
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


def _observed(machine_type, code):
    io = ScriptedIO("λ\nunused")
    try:
        machine = machine_type(code, io)
    except ValueError:
        return "syntax", []

    def view():
        return (
            machine.ind,
            machine.reg,
            tuple(machine.deq),
            machine.halted,
            machine.rendered,
            io.getvalue(),
            io.position(),
            io.progress(),
        )

    trace, error = [view()], None
    for _ in range(_CAP):
        if machine.halted:
            break
        try:
            machine.step()
        except HaltError:
            error = "target"
        except EOFError:
            error = "input"
        trace.append(view())
        if error:
            break
    if not error and machine.halted:
        for _ in range(3):
            machine.step()
            trace.append(view())
    return error, trace


def _agrees(machine_type, code):
    expected = _model(code)
    assert _observed(machine_type, code) == expected, code
    return expected


def check_raw_bitdeque():
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
    corpus = [" ".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += [
        rng.choice((" ", "\t", "\n")).join(rng.choices(atoms, k=12)) for _ in range(256)
    ]
    corpus += [
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
    results = [_agrees(_Machine, code) for code in corpus]
    assert {error for error, _ in results} == {None, "syntax", "target"}
    assert any(not trace[-1][3] for error, trace in results if not error)
    assert _model("INVERT PUSH INVERT INJECT")[1][-1][2:6] == (
        (0, 1),
        True,
        True,
        "0 1",
    )
    assert _model("INVERT PUSH INVERT PUSH POP")[1][-1][1:3] == (0, (1,))
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
    return len(corpus), len(controls)
