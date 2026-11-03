"""Direct byte-tape model for straight-line Pointless programs."""

from itertools import product

import pytest

from esolangs.languages.pointless.interpreter import _Machine
from tests.interpreters.oracle_support import observed

_COMMANDS = "<>:!=+-.,"


def _model(code, stdin):
    tape = {}
    pointer = cursor = 0
    incremented = False
    output = ""
    trace = []
    ops = [(offset, char) for offset, char in enumerate(code) if char in _COMMANDS]

    def view(offset, *, halted=False):
        return (
            (offset, pointer, incremented, {k: v for k, v in tape.items() if v}),
            halted,
            output,
            cursor,
            cursor,
        )

    for offset, command in ops:
        trace.append(view(offset))
        cell = tape.get(pointer, 0)
        indirect = tape.get(cell, 0)
        if (command == "<" and pointer == 0) or (command == "!" and incremented):
            return "halt", [*trace, trace[-1]]
        match command:
            case "<":
                pointer -= 1
            case ">":
                pointer += 1
            case ":":
                pointer = cell
            case ".":
                output += chr(cell)
            case ",":
                if cursor == len(stdin):
                    return "input", [*trace, trace[-1]]
                tape[pointer] = ord(stdin[cursor]) % 256
                cursor += 1
            case _:
                value = {
                    "!": cell + 1,
                    "=": indirect,
                    "+": cell + indirect,
                    "-": cell - indirect,
                }[command]
                if value % 256:
                    tape[pointer] = value % 256
                else:
                    tape.pop(pointer, None)
                incremented |= command == "!"
    return None, [*trace, *([view(len(code), halted=True)] * 4)]


def check_raw_pointless():
    def check(factory, code, stdin):
        def state(machine):
            cells = {i: value for i, value in enumerate(machine.memory) if value}
            return machine.ip, machine.pointer, machine.banged, cells

        assert observed(factory, code, stdin, state) == _model(code, stdin)

    corpus = [" xyz ".join(chars) for chars in product(_COMMANDS, repeat=3)]
    corpus += [",>,<:.", ",>,<+.", ",>,<-.", "!>+>+:=", "comment"]
    for code, stdin in product(corpus, ("", "\x01ÿ", "Ł\n\0")):
        check(_Machine, code, stdin)

    class LostWrite(_Machine):
        def step(self):
            super().step()
            self.tape[:] = bytes(len(self.tape))

    with pytest.raises(AssertionError):
        check(LostWrite, "!>+.", "")
