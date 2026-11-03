"""Structured expressions evaluated over a sparse register file."""

import re
from itertools import product

import pytest

from esolangs.languages.collatz_multiverse.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _source(program):
    return "\n\n".join(
        f"{dest} = {factor} x + {addend}, {'DO' if emit else 'NOT'} PRINT."
        for dest, factor, addend, emit in program
    )


def _model(program, stdin):
    registers = {"negativeOne": -1}
    arrays = {}
    pc = 1
    cursor = 0
    output = ""
    failure = None
    trace = []

    def operand(spec):
        name, _, subscript = spec.rstrip("]").partition("[")
        index = read(subscript) if subscript else 0
        if name == "input" or name == "lineNumber":
            value = read(name)
        elif index:
            value = arrays.get(name, {}).get(index, 0)
        else:
            value = registers.get(name, 0)
        return name, index, value

    def read(name):
        nonlocal cursor
        if name == "lineNumber":
            return pc
        if name != "input":
            return registers.get(name, 0)
        remainder = stdin[cursor:].lstrip()
        cursor = len(stdin) - len(remainder)
        if not remainder:
            raise EOFError
        word = remainder.split(maxsplit=1)[0]
        cursor += len(word)
        if not re.fullmatch(r"[+-]?[0-9]+", word):
            raise ValueError
        return int(word)

    for step in range(17):
        halted = not 1 <= pc <= len(program)
        state = pc, dict(registers), {k: dict(v) for k, v in arrays.items()}
        row = state, halted, output, cursor, cursor
        trace.append(row)
        if failure:
            break
        if halted:
            trace.extend([row] * 3)
            break
        if step == 16:
            break
        dest, factor, addend, emit = program[pc - 1]
        try:
            name, index, current = operand(dest)
            multiplier = operand(factor)[2]
            offset = operand(addend)[2]
        except EOFError:
            failure = "input"
            continue
        except ValueError:
            failure = "argument"
            continue
        value = (
            current // 2
            if current and current % 2 == 0
            else current * multiplier + offset
        )
        if name == "lineNumber":
            pc = value
        elif index:
            arrays.setdefault(name, {})[index] = value
        else:
            registers[name] = value
        pc += 1
        if emit:
            output += chr(value % 256)
    return failure, trace


def _check(factory, program, stdin):
    def state(machine):
        return machine.ip, machine.registers, machine.arrays

    assert observed(factory, _source(program), stdin, state, cap=16) == _model(
        program, stdin
    ), (program, stdin)


def check_raw_collatz_multiverse():
    operands = ("x", "input", "lineNumber", "negativeOne", "x[input]", "x[negativeOne]")
    for dest, factor, addend, stdin in product(
        ("x", "x[input]", "lineNumber"), operands, operands, ("", " -1 2 4 3", "2 nope")
    ):
        program = (("x", "x", "input", False), (dest, factor, addend, True))
        _check(_Machine, program, stdin)
    _check(
        _Machine, (("x", "x", "input", False), ("x", "x", "negativeOne", True)), "-4"
    )
    _check(_Machine, (), "")
    _check(_Machine, (("x", "x", "lineNumber", True),), "")

    class OmittedRead(_Machine):
        def _collect_reads(self, _line):
            return (0, 0, 0)

    with pytest.raises(AssertionError):
        _check(OmittedRead, (("x", "x", "input", True),), "42")
