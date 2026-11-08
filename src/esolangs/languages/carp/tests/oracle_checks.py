"""Revision 168701 nibble registers; regex assembly and a mutable register array."""

import itertools
import random
import re
import sys

import pytest

from esolangs.languages.carp.interpreter import _Machine
from tests.support import workspace_oracle as workspace
from tests.support.model_input import decimal_value as _decimal

_WORKSPACE = workspace.workspace_model("carp-v1", "instruction registers input_cursor")


def _parse(source):
    program = []
    for line in source.splitlines():
        text = line.partition("#")[0].strip()
        if not text:
            continue
        match = re.fullmatch(r"(\S+)\s+[rR]([0-9]+)\s+([0-9]+)", text)
        if not match or match[1].upper() not in {"INC", "DEC", "CLR", "OUT", "INP"}:
            raise ValueError("instruction")
        register = _decimal(match[2])
        if not 1 <= register <= 15:
            raise ValueError("register")
        program.append((match[1].upper(), register - 1, _decimal(match[3])))
    if not program:
        raise ValueError("empty")
    return program


def _number(stdin, cursor):
    while cursor < len(stdin) and stdin[cursor].isspace():
        cursor += 1
    if cursor == len(stdin):
        return 0, cursor, "input"
    start = cursor
    while cursor < len(stdin) and not stdin[cursor].isspace():
        cursor += 1
    token = stdin[start:cursor]
    digits = token[1:] if token[:1] in "+-" else token
    if not digits or any(c not in "0123456789" for c in digits):
        return 0, cursor, "argument"
    value = _decimal(token)
    if 0 <= value <= 15:
        return value, cursor, None
    limit = sys.get_int_max_str_digits()
    error = "syntax" if limit and abs(value) >= 10**limit else "halt"
    return value, cursor, error


def _model(source, stdin):
    try:
        program = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    registers, pc, consumed, output, error = [0] * 15, 0, 0, "", None

    def view():
        return (
            (pc, tuple(registers), tuple(registers)),
            pc < 0,
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if pc < 0:
            break
        op, register, line = program[pc]
        next_pc = pc + 1
        if op == "INC":
            if registers[register] == 15:
                next_pc = line - 1
            else:
                registers[register] += 1
        elif op == "DEC":
            if registers[register] != 0:
                registers[register] -= 1
                next_pc = line - 1
        elif op == "CLR":
            registers[register] = 0
        elif op == "OUT":
            output += str(registers[register])
        else:
            value, consumed, error = _number(stdin, consumed)
            if not error:
                registers[register] = value
        if not error:
            pc = next_pc if 0 <= next_pc < len(program) else -1
        trace.append(view())
        if error:
            break
    if pc < 0 and not error:
        trace.extend([view()] * 3)
    return error, trace


_agrees = workspace.checker(
    _model,
    (_WORKSPACE, lambda row: (row[0][0], row[0][1], row[-1])),
    lambda m: (*m.state, tuple(m.registers)),
)


def check_raw_carp():
    atoms = (
        "INC r1 0",
        "INC r15 1",
        "DEC r1 0",
        "DEC r15 3",
        "CLR r1 99",
        "OUT r1 99",
        "INP r15 0",
    )
    corpus = [
        "\n".join(p) for n in range(3) for p in itertools.product(atoms, repeat=n)
    ]
    rng = random.Random(20261103)
    corpus += ["\n".join(rng.choices(atoms, k=8)) for _ in range(128)]
    corpus += [
        "INC r1 0\n" * 17,
        "INP r1 99\nINC r1 0",
        "INP r1 0\nDEC r1 0",
        "inc r1 2 # comment\n out R1 0",
        "# blank\n",
        "OUT r0 0",
        "OUT r16 0",
        "1 r1 0",
        "INC r1 -1",
        "INC r1",
        "INP r\u0661 0",
        "INC r1 \u0661",
        "\u0131NP r1 0",
        "CLR r1 0\nOUT r1 0",
        "INP r1 0\nOUT r1 0\nINP r2 0\nOUT r2 0",
    ]
    inputs = ("", "0 15\n7", "16", "-1", "x", "+01\t-0", "\u0661", "1_0", " \n")
    results = [
        _agrees(_Machine, source, stdin) for source in corpus for stdin in inputs
    ]
    assert {error for error, _ in results} == {
        None,
        "syntax",
        "input",
        "argument",
        "halt",
    }
    assert any(not trace[-1][1] for error, trace in results if not error)
    _agrees(_Machine, "OUT r1 " + "0" * 4301, "")
    _agrees(_Machine, "INP r1 0", "0" * 4301 + "1")
    _agrees(_Machine, "INP r1 0", "1" * 4301)
    controls = {
        "inc": ("INP r1 0\nINC r1 0", "15"),
        "dec": ("DEC r1 1", ""),
        "clear": ("INC r1 0\nCLR r1 0", ""),
        "write": ("INP r15 0", "7"),
        "syntax": ("OUT r0 0", ""),
        "output": ("OUT r1 0", ""),
        "cursor": ("INP r1 0", " 7 "),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "output":
                    write = io.print_str
                    io.print_str = lambda text: write(text + "\n")
                super().__init__(
                    code.replace("r0", "r1") if self.mode == "syntax" else code, io
                )

            def step(self):
                if self.halted:
                    super().step()
                    return
                pc, values = self.state
                command, register, _ = self.program[pc]
                if self.mode == "dec" and command == "DEC":
                    return  # incorrectly jump on zero
                super().step()
                after, values_after = self.state
                if (
                    self.mode == "inc"
                    and command == "INC"
                    and values[register - 1] == 15
                ):
                    self.state = after, (0, *values_after[1:])
                elif (self.mode == "clear" and command == "CLR") or (
                    self.mode == "write" and command == "INP"
                ):
                    self.state = after, values
                elif self.mode == "cursor" and command == "INP":
                    self.io.input_char()

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    workspace.check_erasures(_WORKSPACE, _agrees, _Machine, "INC r1 0", "")
    return len(results), len(controls) + 3
