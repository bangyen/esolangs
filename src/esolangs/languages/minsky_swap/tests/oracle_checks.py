"""Revision 97869 commands; independent compact and readable parsers."""

import itertools
import random

import pytest

from esolangs.languages.minsky_swap.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _parse(source):
    commands = []
    if any(name + "(" in source for name in ("inc", "swap", "decnz")):
        for raw_text in source.splitlines():
            text = raw_text.strip()
            if not text:
                continue
            name, separator, rest = text.partition("(")
            if (
                name not in {"inc", "swap", "decnz"}
                or not separator
                or not rest.endswith(");")
            ):
                raise ValueError("line")
            number = rest[:-2]
            if number and not number.isdecimal():
                raise ValueError("number")
            commands.append((name, int(number or "1") if name == "decnz" else 0))
    else:
        code, _, rest = source.partition("\n")
        numbers = [
            int("".join(group))
            for digits, group in itertools.groupby(
                rest.partition("\n")[0], str.isdecimal
            )
            if digits
        ]
        cursor = 0
        for char in code:
            if char == "+":
                commands.append(("inc", 0))
            elif char == "*":
                commands.append(("swap", 0))
            elif char == "~":
                if cursor == len(numbers):
                    raise ValueError("target")
                commands.append(("decnz", numbers[cursor]))
                cursor += 1
    return commands


def _model(source):
    try:
        program = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    registers, pointer, pc, dumped, output = [0, 0], 0, 0, False, ""

    def view():
        return (
            (pc, pointer, tuple(registers), dumped, tuple(registers)),
            pc >= len(program),
            output,
            0,
            0,
        )

    trace = [view()]
    for _ in range(64):
        if pc >= len(program):
            break
        command, target = program[pc]
        next_pc = pc + 1
        if command == "inc":
            registers[pointer] += 1
        elif command == "swap":
            pointer = 1 - pointer
        elif registers[pointer]:
            registers[pointer] -= 1
        elif target:
            next_pc = target - 1
        pc = next_pc
        trace.append(view())
    if pc >= len(program):
        output, dumped = f"{registers[0]} {registers[1]}", True
        trace.extend([view()] * 3)
    return None, trace


def _agrees(factory, source):
    expected = _model(source)
    assert (
        observed(factory, source, "λ\nunused", lambda m: (*m.state, tuple(m.memory)))
        == expected
    ), source
    return expected


def check_raw_minsky():
    corpus = []
    for n in range(4):
        for ops in itertools.product("+~*x", repeat=n):
            code = "".join(ops)
            corpus.extend(
                code + "\n" + " ".join([str(target)] * code.count("~"))
                for target in (0, 1, 2, 9)
            )
    rng = random.Random(20261103)
    for _ in range(128):
        ops = rng.choices("+~*", k=12)
        targets = [rng.randrange(15) for c in ops if c == "~"]
        corpus.append("".join(ops) + "\n" + ", ".join(map(str, targets)))
        values = iter(targets)
        corpus.append(
            "\n".join(
                "inc();"
                if c == "+"
                else "swap();"
                if c == "*"
                else f"decnz({next(values)});"
                for c in ops
            )
        )
    corpus += [
        "~",
        "~~\n1",
        "inc();swap();",
        "inc(1+2);",
        "inc();\n+",
        "decnz();",
        "decnz(0);\ninc();",
        "inc(9);\nswap(5);\ninc();",
        "x~ +\n\u0662",
        "~+\n-2",
        "+\n1\n~",
        "INC();",
        "λ\n",
        "~+\n0",
    ]
    results = [_agrees(_Machine, code) for code in corpus]
    assert {error for error, _ in results} == {None, "syntax"}
    assert any(not trace[-1][1] for error, trace in results if not error)
    assert _model("~+\n0")[1][-1][2] == "1 0"  # repo's zero-target fallthrough
    controls = {
        "swap": "*+",
        "decrement": "+~\n1",
        "jump": "~+\n2",
        "zero": "~+\n0",
        "syntax": "~",
        "dump": "+",
        "input": "+",
    }
    for fault, source in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                super().__init__(code + "\n1" if self.mode == "syntax" else code, io)

            def step(self):
                pc, pointer, regs, dumped = self.state
                if self.halted:
                    super().step()
                    if self.mode == "dump":
                        self.io.print_str("extra")
                    return
                command = self.prog[pc]
                if (self.mode == "swap" and command == "*") or (
                    self.mode == "decrement" and command == "~"
                ):
                    self.state = pc + 1, pointer, regs, dumped
                elif self.mode == "jump" and command == "~":
                    self.state = self.targets[pc], pointer, regs, dumped
                elif self.mode == "zero" and command == "~":
                    self.state = 0, pointer, regs, dumped
                else:
                    if self.mode == "input":
                        self.io.input_char()
                    super().step()

        with pytest.raises(AssertionError):
            _agrees(Fault, source)
    return len(corpus), len(controls)
