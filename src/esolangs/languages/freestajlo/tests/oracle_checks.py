"""Linear stack model of Freestajlo's instruction table, revision 184252.

https://esolangs.org/wiki/Freestajlo. Arithmetic, stack selection/transfer,
character and numeric I/O; blocks, functions and strings remain in raw tests.
Undefined depths and surrogate output follow the public Decisions.
"""

import re
from itertools import product

import pytest

from esolangs.languages.freestajlo.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _cells(cells):
    values = []
    while cells is not None:
        value, cells = cells
        values.append(value)
    return tuple(reversed(values))


def _view(machine):
    return (
        machine.ind,
        tuple(machine.stack),
        machine.index,
        tuple(sorted((i, _cells(s[1])) for i, s in machine.others.items() if s[0])),
        _cells(machine.state.transfer[1]),
    )


def _pop(stack):
    return stack.pop() if stack else 0


def _arithmetic(operation, left, right):
    if operation == "+":
        return left + right
    if operation == "-":
        return left - right
    if operation == "*":
        return left * right
    if operation == "/":
        return abs(left) // abs(right) * (-1 if (left < 0) != (right < 0) else 1)
    if operation == "%":
        return left % right
    if operation == "^":
        return 0 if right < 0 else left**right
    if operation == "=":
        return -int(left == right)
    if operation == "<":
        return -int(left > right)
    if operation == ">":
        return -int(left < right)
    return ~(left | right)


def _local(token, stack):
    if token in "+-*/%^=<>`":
        right, left = _pop(stack), _pop(stack)
        stack.append(_arithmetic(token, left, right))
    elif token == "_":
        stack.append(-_pop(stack))
    elif token == "$":
        value = _pop(stack)
        stack.extend((value, value))
    elif token == "#":
        _pop(stack)
    elif token == "\\":
        first, second = _pop(stack), _pop(stack)
        stack.extend((first, second))
    elif token == "|":
        stack.append(len(stack))
    elif token in "&~":
        depth = _pop(stack)
        value = _pop(stack) if token == "~" else None
        if depth < 0 or depth > len(stack) - (token == "&"):
            raise IndexError(depth)
        if token == "&":
            stack.append(stack[-depth - 1])
        else:
            stack.insert(len(stack) - depth, value)
    elif token in ":.)!":
        return token, _pop(stack)
    else:
        raise AssertionError(token)
    return None


def _model(source, stdin):
    tokens = [
        (m.group(), m.start()) for m in re.finditer(r"[0-9]+|'[\s\S]|[^\s]", source)
    ]
    at = cursor = index = 0
    stacks, transfer, output, trace = {0: []}, [], "", []

    def row():
        return (
            (
                tokens[at][1] if at < len(tokens) else len(source),
                tuple(stacks[index]),
                index,
                tuple(
                    sorted((i, tuple(s)) for i, s in stacks.items() if i != index and s)
                ),
                tuple(transfer),
            ),
            at == len(tokens),
            output,
            cursor,
            cursor,
        )

    while True:
        trace.append(row())
        if at == len(tokens):
            return None, trace + [row()] * 3
        token = tokens[at][0]
        stack = stacks[index].copy()
        effect = None
        if token.isdecimal():
            stack.append(int(token))
        elif token.startswith("'"):
            stack.append(ord(token[1]))
        elif token == ",":
            stack.append(ord(stdin[cursor]) if cursor < len(stdin) else -1)
            cursor += cursor < len(stdin)
        elif token == ";":
            match = re.search(r"-?[0-9]+", stdin[cursor:])
            stack.append(int(match.group()) if match else 0)
            cursor = min(len(stdin), cursor + match.end() + 1) if match else len(stdin)
        elif token == "(":
            stack.append(transfer.pop() if transfer else 0)
        else:
            try:
                effect = _local(token, stack)
            except (ZeroDivisionError, IndexError):
                return "halt", [*trace, trace[-1]]
        stacks[index] = stack
        at += 1
        if effect is not None:
            operation, value = effect
            if operation == ")":
                transfer.append(value)
            elif operation == "!":
                index = value
                stacks.setdefault(index, [])
            elif operation == ":":
                output += str(value)
            else:
                point = value % 0x10FFFF
                if 0xD800 <= point <= 0xDFFF:
                    return "halt", [*trace, row()]
                output += chr(point)


def _check(factory, source, stdin="unused"):
    assert observed(factory, source, stdin, _view, cap=64) == _model(source, stdin), (
        source,
        stdin,
    )


def check_raw_freestajlo():
    def literal(value):
        return str(abs(value)) + (" _" if value < 0 else "")

    for left, right, operation in product(range(-2, 4), range(-2, 4), "+-*/%^=<>`"):
        _check(_Machine, f"{literal(left)} {literal(right)} {operation} $ : .")
    for size in range(4):
        for operations in product(
            ("$", "#", "\\", "|", "(", ")", "0 !", "1 !", "0 &", "1 ~"), repeat=size
        ):
            _check(_Machine, "1 2 " + " ".join(operations) + " : : :")
    for source in ("$ : :", "# :", "\\ : :", "| :", "( :", "0 &", "0 ~"):
        _check(_Machine, source)
    for source, stdin in product(
        (", , : :", "; ; : :", "'λ .", "55296 ."), ("", "a\nλ", "junk -12x+3!", "--7-2")
    ):
        _check(_Machine, source, stdin)
    for source in ("?", "@", "{", "}", "[", '"', "'"):
        assert observed(_Machine, source, "", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class Skips(_Machine):
        def step(self):
            pass

    class WrongOutput(_Machine):
        def __init__(self, source, io):
            write = io.print_num
            io.print_num = lambda n: write(n + 1)
            super().__init__(source, io)

    class ReadsTwice(_Machine):
        def step(self):
            self.io.input_char()
            super().step()

    for factory, code in ((Skips, "1 2 +"), (WrongOutput, "1 :"), (ReadsTwice, ", :")):
        with pytest.raises(AssertionError):
            _check(factory, code, "ab")
