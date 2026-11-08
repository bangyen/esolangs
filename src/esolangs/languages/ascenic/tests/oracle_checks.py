"""Revision 169232 Ascenic, using mutable stacks and scripted random draws."""

import itertools
import random
from decimal import Decimal

import pytest

from esolangs.languages.ascenic.interpreter import _Machine
from esolangs.runtime._state import WorkspaceModel
from tests.support.workspace_oracle import agrees as workspace_agrees
from tests.support.workspace_oracle import missing_workspace

_WORKSPACE = WorkspaceModel("ascenic-v1", ("instruction", "stack", "input_cursor"))


class _Draws:
    used = 0

    def randbelow(self, upper):
        assert upper == 2
        value = (0, 1, 1, 0)[self.used % 4]
        self.used += 1
        return value


def _parse(source):
    ops, previous = [], 0
    for line, raw in enumerate(source.split("\n")):
        text = raw.strip()
        if not text:
            continue
        opcode = len(text) - len(text.lstrip("A"))
        tail = text[opcode:]
        if (
            opcode > 19
            or not tail
            or any(c != "s" for c in tail)
            or len(tail) <= previous
        ):
            raise ValueError
        previous = len(tail)
        ops.append((opcode, previous, line))
    return ops


def _input(stdin, at, numeric):
    if not numeric:
        return (
            (ord(stdin[at]), at + 1, None) if at < len(stdin) else (None, at, "input")
        )
    while at < len(stdin) and stdin[at].isspace():
        at += 1
    start = at
    while at < len(stdin) and not stdin[at].isspace():
        at += 1
    token = stdin[start:at]
    if not token:
        return None, at, "input"
    digits = token[1:] if token[:1] in "+-" else token
    if not digits or any(c not in "0123456789" for c in digits):
        return None, at, "argument"
    return int(Decimal(token)), at, None


def _arithmetic(stack, opcode, argument):
    a = stack.pop() if stack else 0
    if opcode in range(4, 9):
        operations = (
            lambda a, b: a + b,
            lambda a, b: a - b,
            lambda a, b: a * b,
            lambda a, b: a // b,
            lambda a, b: a % b,
        )
        stack.append(operations[opcode - 4](a, argument))
    elif opcode == 10:
        pass
    else:
        b = stack.pop() if stack else 0
        if opcode == 9:
            stack.extend((a, b))
        else:
            operations = (
                lambda a, b: a + b,
                lambda a, b: b - a,
                lambda a, b: a * b,
                lambda a, b: b // a if a else 0,
            )
            stack.append(operations[opcode - 16](a, b))


def _model(source, stdin):
    try:
        ops = _parse(source)
    except ValueError:
        return "syntax", [(None, False, "", 0, 0)]
    stack, pc, consumed, draws, output, error = [], 0, 0, 0, "", None

    def view():
        line = ops[-1][2] + 1 if ops else 0
        ip = (line,) if pc >= len(ops) else (ops[pc][2],)
        return (
            (pc, tuple(stack), ip, draws),
            pc >= len(ops),
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if pc >= len(ops):
            break
        opcode, argument, _ = ops[pc]
        next_pc, top = pc + 1, stack[-1] if stack else 0
        if opcode == 1:
            if argument % 2:
                output += str(Decimal(top))
            elif 0 <= top <= 0x10FFFF and not 0xD800 <= top <= 0xDFFF:
                output += chr(top)
            else:
                error = "halt"
        elif opcode == 2:
            value, consumed, error = _input(stdin, consumed, argument % 2)
            if not error:
                stack.append(value)
        elif opcode == 3:
            stack.append(argument)
        elif opcode in (4, 5, 6, 7, 8, 9, 10, 16, 17, 18, 19):
            _arithmetic(stack, opcode, argument)
        elif opcode in (11, 12) and top:
            if opcode == 11:
                error = "halt"
            else:
                next_pc = pc + argument
        elif opcode == 13:
            stack.append(int(top < argument))
        elif opcode == 14:
            stack.append(int(top < (stack[-2] if len(stack) > 1 else 0)))
        elif opcode == 15:
            stack.append((0, 1, 1, 0)[draws % 4])
            draws += 1
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if not error and pc >= len(ops):
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin):
    expected, rng = _model(source, stdin), _Draws()
    return workspace_agrees(
        expected,
        (lambda code, io: factory(code, io, rng), source, stdin),
        (_WORKSPACE, lambda row: (row[0][0], row[0][1], row[-1])),
        lambda m: (m.state[0], tuple(m.stack), m.ip, rng.used),
    )


def _source(pairs):
    return "\n".join("A" * opcode + "s" * arg for opcode, arg in pairs)


def check_raw_ascenic():
    corpus = [
        _source(((a, start), (b, start + 1)))
        for a, b in itertools.product(range(20), repeat=2)
        for start in (1, 2)
    ]
    rng = random.Random(20261103)
    corpus += [_source((rng.randrange(20), i + 1) for i in range(8)) for _ in range(64)]
    corpus += [
        _source(((5, 1), (4, 73), (1, 74))),
        _source(((2, 1), (2, 3), (16, 4), (1, 5))),
        "",
        "\n ",
        _source((0, i + 1) for i in range(80)),
    ]
    inputs = ("", "3 -2\n", "x", "λ", "\x00\xff")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    results.extend(
        _agrees(_Machine, code, "unread")
        for code in ("A", "aS", "A s", "A" * 20 + "s", "As\nAs", "As\nAss\nAs")
    )
    results += [
        _agrees(_Machine, _source(((2, 1), (6, 99), (1, arg))), "9" * 4300)
        for arg in (100, 101)
    ]
    results.extend(
        _agrees(_Machine, _source(((2, 1), (1, 2))), value)
        for value in ("55296", "1114111", "1114112")
    )
    assert {error for error, _ in results} == {
        None,
        "syntax",
        "input",
        "argument",
        "halt",
    }
    assert _model(_source(((5, 1), (4, 73), (1, 74))), "")[1][-1][2] == "H"
    controls = {
        "subtract": (_source(((5, 1),)), ""),
        "swap": (_source(((9, 1),)), ""),
        "draw": (_source(((15, 1), (15, 2))), ""),
        "jump_backward": (_source(((3, 1), (11, 2))), ""),
        "posthalt": ("", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                opcode = self.ops[self.state[0]][0]
                before = self.state
                if self.mode == "jump_backward" and opcode == 11:
                    self.state = len(self.ops), before[1]
                    return
                super().step()
                at, stack = self.state
                if self.mode == "subtract" and opcode == 5:
                    stack = (-stack[0], stack[1])
                elif self.mode == "swap" and opcode == 9:
                    stack = None
                elif self.mode == "draw" and opcode == 15:
                    stack = (0, stack[1])
                self.state = at, stack

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    for component in _WORKSPACE.components:
        with pytest.raises(AssertionError):
            _agrees(missing_workspace(_Machine, component), _source(((3, 1),)), "")
    return len(results), len(controls) + 3
