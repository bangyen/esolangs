"""Revision 189070 rational operations; mutable stacks, bindings and scanned loops."""

import itertools
import random
from fractions import Fraction

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.three_x.interpreter import _Machine
from tests.support.model_input import token_span
from tests.support.workspace_oracle import check_erasures, workspace_model
from tests.support.workspace_oracle import checker as workspace_checker

_WORKSPACE = workspace_model(
    "three-x-v1", "instruction operands loop_returns variables input_cursor"
)


def _input(stdin, consumed):
    start, consumed = token_span(stdin, consumed)
    if start == consumed:
        return None, consumed, "input"
    numerator, slash, denominator = stdin[start:consumed].partition("/")
    sign = -1 if numerator.startswith("-") else 1
    digits = numerator[1:] if numerator[:1] in "+-" else numerator
    if not digits.isdecimal() or (slash and not denominator.isdecimal()):
        return None, consumed, "syntax"
    divisor = int(denominator) if slash else 1
    if not divisor:
        return None, consumed, "syntax"
    return Fraction(sign * int(digits), divisor), consumed, None


def _data(command, stack, bindings):
    needs = {"3": 0, "x": 3, "v": 2, "^": 1, "#": 2}
    if len(stack) < needs[command] or (command == "x" and not stack[-3]):
        return "halt"
    if command == "3":
        stack.append(Fraction(3))
    elif command == "x":
        a, b, c = stack.pop(), stack.pop(), stack.pop()
        stack.append((a - b) / c)
    elif command == "v":
        value, key = stack.pop(), stack.pop()
        bindings[key] = value
    elif command == "^":
        stack.append(bindings.get(stack.pop(), Fraction(3)))
    else:
        stack[-1], stack[-2] = stack[-2], stack[-1]
    return None


def _closing(source, pc):
    at, level = pc + 1, 1
    while at < len(source):
        char = source[at]
        if char == "[" and (end := source.find("]", at + 1)) >= 0:
            at = end + 1
            continue
        level += (char == "(") - (char == ")")
        if not level:
            return at
        at += 1
    return None


def _loop(command, pc, source, stack, loops):
    if not stack:
        return pc, "halt"
    if command == "(":
        close = _closing(source, pc)
        if close is None:
            return len(source), "halt"  # the failed scan leaves the cursor at EOF
        if stack[-1]:
            loops.append(pc)
            return pc + 1, None
        return close + 1, None
    if stack[-1]:
        return (loops[-1] + 1, None) if loops else (pc, "halt")
    if loops:
        loops.pop()
    return pc + 1, None  # the repo permits a stray close on zero


def _model(source, stdin):
    stack, loops, bindings, pc, consumed, output, error = [], [], {}, 0, 0, "", None

    def view():
        variables = tuple(sorted(bindings.items()))
        return (
            (pc, tuple(stack), tuple(loops), variables, variables, pc),
            pc >= len(source),
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    for _ in range(64):
        if pc >= len(source):
            break
        command, next_pc = source[pc], pc + 1
        if command in "3xv^#":
            error = _data(command, stack, bindings)
        elif command == "?":
            value, consumed, error = _input(stdin, consumed)
            if not error:
                stack.append(value)
        elif command == "!":
            if not stack:
                error = "halt"
            else:
                value = stack.pop()
                output += (
                    str(value.numerator)
                    if value.denominator == 1
                    else f"{value.numerator}/{value.denominator}"
                )
        elif command in "()":
            next_pc, error = _loop(command, pc, source, stack, loops)
            if error:
                pc = next_pc
        elif command == "[":
            close = source.find("]", pc + 1)
            if close >= 0:
                output += source[pc + 1 : close]
                next_pc = close + 1
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if pc >= len(source) and not error:
        trace.extend([view()] * 3)
    return error, trace


_agrees = workspace_checker(
    _model,
    (_WORKSPACE, lambda row: (*row[0][:3], frozenset(row[0][3]), row[-1])),
    lambda m: (*m.state, tuple(sorted(m.variables.items())), m.ip),
)


def check_raw_three_x():
    atoms = "3x!?v^#()[]a"
    corpus = ["".join(p) for n in range(3) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += [
        "".join(
            rng.choices(("3", "333x", "?", "!", "3^", "33v", "#", "[x]", "(3)"), k=8)
        )
        for _ in range(128)
    ]
    corpus += [
        "3333x3x!",
        "333(33x#)!",
        "?(!?)!",
        "?()",
        "?(3)",
        "?(?",
        "3(",
        "3([)])",
        "[3!",
        "[[x]z]",
        "[λ\n]",
        "???x!",
        "??v?^!",
        "?^!",
        "?)",
        "[before]?",
        "3^",
        "33v3^",
    ]
    inputs = ("", "1 2 0", "-3/2 1/3", "x 1/0")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    for code, stdin in [
        ("?)", "0"),
        ("?33x", "0"),
        ("???x!", "1/2 -1/3 4"),
        ("??v?^!", "2/3 5/7 2/3"),
        ("?", "1_0"),
        ("?", "1/-2"),
        ("?", "1/0"),
        ("?", "\u0661/\u0662"),
        ("?(!?)!", "1 " * 80),
    ]:
        results.append(_agrees(_Machine, code, stdin))
    assert {error for error, _ in results} == {None, "syntax", "input", "halt"}
    assert any(not trace[-1][1] for error, trace in results if not error)
    assert _model("???x!", "1/2 -1/3 4")[1][-1][2] == "26/3"
    assert _model("??v?^!", "2/3 5/7 2/3")[1][-1][2] == "5/7"
    controls = {
        "x": ("???x", "1 2 4"),
        "division": ("?33x", "0"),
        "open": ("3(", ""),
        "eof": ("?", ""),
        "literal": ("[x]", ""),
        "close": ("?(!?)", "1 0"),
        "variable": ("??v", "3 2"),
        "default": ("3^", ""),
        "cursor": ("?", " 1 "),
        "underflow": ("!", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_token = lambda: "0"
                elif self.mode == "literal":
                    io.print_str = lambda _text: None
                super().__init__(code, io)

            def step(self):
                if self.halted:
                    super().step()
                    return
                pc, stack, jumps, variables = self.state
                char = self.code[pc]
                if self.mode == "x" and char == "x":
                    a, b, c = stack[-3:]
                    self.state = pc + 1, (*stack[:-3], (a - b) / c), jumps, variables
                elif self.mode == "division" and char == "x":
                    self.state = pc, (), jumps, variables
                    raise HaltError("popped before checking divisor")
                elif self.mode == "open" and char == "(":
                    self.state = pc + 1, stack, jumps, variables
                elif self.mode == "underflow" and char == "!":
                    self.state = pc + 1, (), jumps, variables
                else:
                    super().step()
                    at, values, returns, stored = self.state
                    if self.mode == "close" and char == ")" and not stack[-1]:
                        self.state = at, values, jumps, stored
                    elif self.mode == "variable" and char == "v":
                        self.state = (
                            at,
                            values,
                            returns,
                            tuple((key, Fraction(0)) for key, _ in stored),
                        )
                    elif self.mode == "default" and char == "^":
                        self.state = at, (*values[:-1], Fraction(0)), returns, stored
                    elif self.mode == "cursor" and char == "?":
                        self.io.input_char()

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin)
    check_erasures(_WORKSPACE, _agrees, _Machine, "??v?^", "2/3 5/7 2/3")
    return len(results), len(controls) + 5
