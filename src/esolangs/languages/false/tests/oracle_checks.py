"""Independent linear FALSE model from its command table and public Decisions.

https://esolangs.org/wiki/FALSE. Signed 32-bit arithmetic, shuffles,
variables, literals and I/O; lambda/control cases remain in the raw suite.
"""

import re
from itertools import product

import pytest

from esolangs.languages.false.interpreter import _Machine
from tests.interpreters.oracle_support import decorate_io, observed, overread, stalled
from tests.interpreters.semantic_oracles import signed32 as _signed


def _math(command, left, right):
    if command == "+":
        value = left + right
    elif command == "-":
        value = left - right
    elif command == "*":
        value = left * right
    elif command == "/":
        value = abs(left) // abs(right) * (-1 if (left < 0) != (right < 0) else 1)
    elif command == "&":
        value = left & right
    elif command == "|":
        value = left | right
    elif command == ">":
        value = -int(left > right)
    else:
        value = -int(left == right)
    return _signed(value)


def _stack(command, stack, variables):
    effect = None
    if command in "+-*/&|>=":
        right, left = stack.pop(), stack.pop()
        stack.append(_math(command, left, right))
    elif command in "_~":
        value = stack.pop()
        stack.append(_signed(-value if command == "_" else ~value))
    elif command == "$":
        stack.append(stack[-1])
    elif command == "%":
        stack.pop()
    elif command == "\\":
        stack[-2], stack[-1] = stack[-1], stack[-2]
    elif command == "@":
        last = [stack.pop(), stack.pop(), stack.pop()]
        stack.extend((last[1], last[0], last[2]))
    elif command in "Oø":
        depth = stack.pop()
        if not 0 <= depth < len(stack):
            raise IndexError(depth)
        stack.append(stack[-depth - 1])
    elif command in ":;":
        address = stack.pop()
        if not 0 <= address < 26:
            raise IndexError(address)
        if command == ":":
            variables[address] = stack.pop()
        else:
            if variables[address] is None:
                raise IndexError(address)
            stack.append(variables[address])
    elif command in ".,":
        value = stack.pop()
        effect = str(value) if command == "." else chr(value % 256)
    return effect


def _model(source, stdin):
    pc = cursor = 0
    stack, variables, output, trace = [], [None] * 26, "", []

    def row():
        halted = pc == len(source)
        return (
            (None if halted else pc, tuple(stack), tuple(variables)),
            halted,
            output,
            cursor,
            cursor,
        )

    while True:
        trace.append(row())
        if pc == len(source):
            return None, trace + [row()] * 3
        command = source[pc]
        changed, memory, next_pc, text = stack.copy(), variables.copy(), pc + 1, None
        try:
            if "0" <= command <= "9":
                number = re.match(r"[0-9]+", source[pc:]).group()
                changed.append(_signed(int(number)))
                next_pc = pc + len(number)
            elif command == "'":
                changed.append(ord(source[pc + 1]))
                next_pc = pc + 2
            elif command == "{":
                next_pc = source.index("}", pc) + 1
            elif command == '"':
                next_pc = source.index('"', pc + 1) + 1
                text = source[pc + 1 : next_pc - 1]
            elif "a" <= command <= "z":
                changed.append(ord(command) - ord("a"))
            elif command == "^":
                changed.append(ord(stdin[cursor]) if cursor < len(stdin) else -1)
                cursor += cursor < len(stdin)
            else:
                text = _stack(command, changed, memory)
        except (IndexError, ZeroDivisionError):
            return "halt", [*trace, row()]
        pc, stack, variables = next_pc, changed, memory
        if text is not None:
            output += text


def _check(factory, source, stdin="unused"):
    def state(machine):
        return machine.ip, tuple(machine.stack), machine.state[1]

    assert observed(factory, source, stdin, state, cap=64) == _model(source, stdin), (
        source,
        stdin,
    )


def check_raw_false():
    def literal(value):
        return str(abs(value)) + ("_" if value < 0 else "")

    for left, right, command in product(
        (-(2**31), -7, 0, 3, 2**31 - 1), (-2, 0, 5), "+-*/&|>="
    ):
        _check(_Machine, literal(left) + " " + literal(right) + command + "$.,")
    for prefix, command in product(
        ("", "1 ", "1 2 ", "1 2 3 "),
        ("$", "%", "\\", "@", "0O", "1ø", "2O", "_", "~", "a;", "a:", ".", ","),
    ):
        _check(_Machine, prefix + command)
    for value, name in product((-1, 0, 17, 2**32 + 1), "abz"):
        _check(_Machine, literal(value) + name + ":" + name + ";$.,")
    for code, stdin in product(
        ("^^$.,", '"λ\n"^,', "'λ,", "{comment}42."), ("", "A\nλ", "\x00", "Ā")
    ):
        _check(_Machine, code, stdin)
    _check(_Machine, "")
    for source in ("[", '"', "{", "'"):
        assert observed(_Machine, source, "unused", lambda m: m.ip) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    wrong_output = decorate_io(
        _Machine, "print_num", lambda write: lambda n: write(n + 1)
    )

    for factory, code in (
        (stalled(_Machine), "12+"),
        (wrong_output, "1."),
        (overread(_Machine), "^,"),
    ):
        with pytest.raises(AssertionError):
            _check(factory, code, "ab")
