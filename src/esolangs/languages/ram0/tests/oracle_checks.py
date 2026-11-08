"""Revision 142358 commands; scanned source and insertion-ordered dictionary RAM."""

import itertools
import random

import pytest

from esolangs.languages.ram0.interpreter import _Machine
from tests.support.workspace_oracle import (
    charged_bits,
    missing_workspace,
    source_checker,
    workspace_model,
)

_WORKSPACE = workspace_model(
    "ram0-v2", "instruction zero_register number_register cells input_cursor dumped"
)


def _model(source):
    commands, digits = [], ""
    for char in source + " ":
        if char.isdecimal():
            digits += char
            continue
        if digits:
            commands.append(digits)
            digits = ""
        if char in "ZANCLS":
            commands.append(char)
    pc = z = n = 0
    ram, dumped, output, error = {}, False, "", None

    def view():
        state = (
            pc,
            z,
            n,
            tuple(ram.items()),
            dumped,
            (z, n, *(ram[k] for k in sorted(ram))),
        )
        return state, pc >= len(commands), output, 0, 0

    trace = [view()]
    for _ in range(64):
        if pc >= len(commands):
            break
        command, next_pc = commands[pc], pc + 1
        if command.isdecimal():
            try:
                target = int(command)
            except ValueError:
                return "syntax", [*trace, view()]
            if target:
                next_pc = target - 1
            else:
                error = "halt"
        elif command == "A":
            z += 1
        elif command == "Z":
            z = 0
        elif command == "N":
            n = z
        elif command == "L":
            z = ram.get(z, 0)
        elif command == "S":
            ram[n] = z
        elif command == "C" and z == 0:
            next_pc += 1
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if not error and pc >= len(commands):
        entries = [f"    {key}: {value}" for key, value in ram.items()]
        output = (
            f"z: {z}\nn: {n}\nram: {{"
            + ("\n" + ",\n".join(entries) + "\n" if entries else "")
            + "}"
        )
        dumped = True
        trace.extend([view()] * 3)
    return error, trace


def _state(machine):
    return (
        machine.ind,
        machine.z,
        machine.n,
        tuple(machine.ram.items()),
        machine.dumped,
        tuple(machine.memory),
    )


def _parts(row):
    return (*row[0][:4], row[-1], row[0][4])


_agrees = source_checker(_model, (_WORKSPACE, _parts), _state, "λ\nunused")


def check_raw_ram0():
    atoms = ("Z", "A", "N", "C", "L", "S", "0", "1", "4", "99")
    corpus = [" ".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += [" ".join(rng.choices(atoms, k=16)) for _ in range(256)]
    corpus += [
        "AAANASZNASANASZLS",
        "AANAZSNAAASZAL",
        "AANSAANSZANAS",
        "AcommentA",
        "AAZC0A",
        "0",
        "00",
        "C0A",
        "A004AA",
        "xA12b3Z",
        "A\u0664AA",
        "\u0660",
        "\uff19",
        "A-1",
        "ANASNZNSS",
        "ASASL",
        "A " + "9" * 100,
        "\nλ\t",
        "A A N A A S Z N A S A N Z S",
    ]
    results = [_agrees(_Machine, code) for code in corpus]
    assert {error for error, _ in results} == {None, "halt"}
    assert any(not trace[-1][1] for error, trace in results if not error)
    assert _model("A N A S Z N A S")[1][-1][0][3] == ((1, 2), (0, 1))
    for source, bits in (("", 1), ("A", 3), ("A N A S", 10)):
        trace = _model(source)[1]
        assert charged_bits(_WORKSPACE, map(_parts, trace)) == bits
    trace = _agrees(_Machine, "")[1]
    assert not trace[0][0][4]
    assert all(row[0][4] for row in trace[1:])

    class MissingDump(missing_workspace(_Machine, "dumped")):
        def workspace_snapshot(self):
            if not self.dumped:
                return _Machine.workspace_snapshot(self)
            return super().workspace_snapshot()

    with pytest.raises(AssertionError):
        _agrees(MissingDump, "")
    wide = "1" * 4301
    for source in (
        "C " + wide + " A",
        "0 " + wide,
        "3 " + wide + " A",
        "A " + wide,
        "\u0661" * 4301,
        "C " + "0" * 4301 + " A",
    ):
        _agrees(_Machine, source)
    controls = {
        "skip": "C A",
        "load": "A N A S Z A L",
        "store": "A N A S",
        "goto": "4 A",
        "dump": "A",
        "input": "A",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def step(self):
                if self.halted:
                    super().step()
                    if self.mode == "dump":
                        self._dump(self.z, self.n, self.state.ram)
                    return
                command = self.tokens[self.ind]
                if self.mode == "skip" and command == "C":
                    self.state = self.state._replace(ind=self.ind + 1)
                elif self.mode == "load" and command == "L":
                    self.state = self.state._replace(ind=self.ind + 1, z=0)
                elif self.mode == "goto" and command.isdecimal():
                    self.state = self.state._replace(ind=int(command))
                else:
                    if self.mode == "input":
                        self.io.input_char()
                    super().step()
                    if self.mode == "store" and command == "S":
                        self.state = self.state._replace(z=0)

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    return len(corpus), len(controls)
