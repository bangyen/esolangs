"""Run-level string evaluator using explicit bit streams."""

import re
from itertools import product

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.smu.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO


def _instructions(code):
    """Yield literal contents or individual commands."""
    start = None
    depth = 0
    for index, char in enumerate(code):
        if char == "(":
            if not depth:
                start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError
            if not depth:
                yield True, code[start:index]
        elif not depth:
            yield False, char
    if depth:
        raise ValueError


def _model(code, stdin):
    stack = []
    variables = {}
    output = []
    bits = ["|+"[(ord(char) >> shift) & 1] for char in stdin for shift in range(8)]
    reads = 0
    steps = 0
    error = None
    while steps < 64:
        try:
            instructions = list(_instructions(code))
        except ValueError:
            error = "halt"
            break
        stack.append(bits[reads] if reads < len(bits) else "=")
        reads += reads < len(bits)
        steps += len(instructions) + 2
        for literal, token in instructions:
            if literal:
                stack.append(token)
            elif token == "|" and stack:
                text = stack.pop()
                if text:
                    stack.extend((text[1:], text[0]))
            elif token in "=+" and len(stack) >= 2:
                right, left = stack.pop(), stack.pop()
                if token == "=":
                    variables[right] = left
                else:
                    stack.append(variables.get(left, "") + variables.get(right, ""))
        text = stack.pop() if stack else ""
        if re.search(r"[^|+=]", text):
            error = "halt"
            break
        output.extend(int(char == "+") for char in text if char != "=")
        if not stack:
            break
        code = stack.pop()
    else:
        raise AssertionError("oracle corpus must terminate")
    packed = "".join(
        chr(sum(bit << shift for shift, bit in enumerate(output[i : i + 8])))
        for i in range(0, len(output) - (len(output) % 8 if error else 0), 8)
    )
    return error, packed, (reads + 7) // 8, stack, variables


def _check(factory, source, expanded, stdin):
    io = ScriptedIO(stdin)
    machine = factory(source, io)
    error = None
    try:
        for _ in range(64):
            if machine.halted:
                break
            machine.step()
        else:
            raise AssertionError("interpreter exceeded the corpus bound")
    except HaltError:
        error = "halt"
    actual = error, io.getvalue(), io.position(), machine.stack, machine.values
    assert actual == _model(expanded, stdin), (source, stdin)


def check_raw_smu():
    tokens = ("()", "(+)", "(|)", "(=)", "((+))", "|", "+", "=")
    for commands, stdin in product(product(tokens, repeat=3), ("", "A", "ÿ")):
        code = "".join(commands)
        _check(_Machine, code, code, stdin)
    for source, expanded in (
        ("9x(+++++++++)9x 9x & ignored\n= ", "(+++++++++)="),
        ("a(+)a b a (|) b b", "(+)(|)"),
        ("(+)()=()()+=()", "(+)()=()()+=()"),
        ("((+))((|))", "((+))((|))"),
    ):
        _check(_Machine, source, expanded, "A")

    _check(_Machine, "()()()", "()()()", "Ā")

    class MissingOutput(_Machine):
        def _write(self, _text):
            pass

    with pytest.raises(AssertionError):
        _check(MissingOutput, "(+)", "(+)", "")
