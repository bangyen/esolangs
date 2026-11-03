"""Revision 198541 Aprknia, using mutable stacks and exact rational division."""

import itertools
import random
from fractions import Fraction

import pytest

from esolangs.languages.aprknia.interpreter import _Machine
from tests.interpreters.oracle_support import observed


def _balanced(source):
    depth = 0
    for char in source:
        depth += (char == "[") - (char == "]")
        if depth < 0:
            return False
    return depth == 0


def _model(source, stdin, cap=16):
    if not _balanced(source):
        return "syntax", [(None, False, "", 0, 0)]
    pc, stack, consumed, output, error = 0, [], 0, "", None

    def view():
        return (
            (pc, tuple(stack), tuple(stack)),
            pc == len(source),
            output,
            consumed,
            consumed,
        )

    trace = [view()]
    # Sixteen operations bound the integer growth of the random corpus.
    for _ in range(cap):
        if pc == len(source):
            break
        command, next_pc = source[pc], pc + 1
        need = 2 if command in "*~" else 1 if command in "![]," else 0
        mode = stack[-1] % 3 if stack and command == "," else 0
        if command == "," and mode:
            need = 2
        if len(stack) < need or (
            command == "," and mode == 1 and not 0 <= stack[-2] <= 0x10FFFF
        ):
            error = "halt"
        elif command == "1":
            stack.append(1)
        elif command == "!":
            stack.pop()
        elif command == "~":
            stack[-2], stack[-1] = stack[-1], stack[-2]
        elif command == "*":
            a, b = stack.pop(), stack.pop()
            quotient = int(Fraction(b, a)) if a else 0
            stack.extend((b + a, b - a, b * a, quotient, b - a * quotient if a else 0))
        elif command == ",":
            if mode == 0 and consumed == len(stdin):
                error = "input"
            else:
                stack.pop()
                if mode == 0:
                    stack.append(ord(stdin[consumed]))  # repo character-input adapter
                    consumed += 1
                elif mode == 1:
                    output += chr(stack.pop())
                else:
                    output += str(stack[-1])
        elif (command == "[" and stack[-1] <= 0) or (command == "]" and stack[-1] > 0):
            at, level, step = pc, 1, 1 if command == "[" else -1
            other = "]" if command == "[" else "["
            while level:
                at += step
                level += (source[at] == command) - (source[at] == other)
            next_pc = at + 1
        if not error:
            pc = next_pc
        trace.append(view())
        if error:
            break
    if not error and pc == len(source):
        trace.extend([view()] * 3)
    return error, trace


def _agrees(factory, source, stdin, cap=16):
    expected = _model(source, stdin, cap)
    assert (
        observed(factory, source, stdin, lambda m: (*m.state, tuple(m.stack)), cap=cap)
        == expected
    ), (source, stdin)
    return expected


def check_raw_aprknia():
    atoms = "1*!~[],x"
    corpus = ["".join(p) for n in range(4) for p in itertools.product(atoms, repeat=n)]
    rng = random.Random(20261103)
    corpus += ["".join(rng.choices(atoms, k=12)) for _ in range(128)]
    corpus += [
        "11*",
        "11*,",
        "11*,,",
        "1[]",
        "11*[1]",
        "1[!]",
        "11*1,",
        "1" * 80,
        "λ\n",
        "1[[]]",
        "[",
        "]",
        "11*!!!!,",
        "111*!!!!,",
    ]
    inputs = ("", "A\n", "λ", "\xff\x00", "\U0010ffff")
    results = [_agrees(_Machine, code, stdin) for code in corpus for stdin in inputs]
    negative, two, zero = "111*!!!!*!!!~!", "11*!!!!", "11*~!~!~!~!"
    finite = [
        negative + two + "*",
        "1" + zero + "*",
        negative + "1,",
        negative + "[]",
        zero + ",1,",
        zero + "," + zero + ",*",
    ]
    results += [
        _agrees(_Machine, code, stdin, 64) for code in finite for stdin in inputs
    ]
    assert {error for error, _ in results} == {None, "syntax", "halt", "input"}
    assert any(not trace[-1][1] for error, trace in results if error is None)
    assert _model(negative + two + "*", "", 64)[1][-1][0][1] == (1, -3, -2, 0, -1)
    assert _model("1" + zero + "*", "", 64)[1][-1][0][1][-2:] == (0, 0)
    controls = {
        "order": ("11*", ""),
        "division": (negative + two + "*", ""),
        "zero": ("1" + zero + "*", ""),
        "swap": ("111*!!!!~", ""),
        "pop": ("1!", ""),
        "loop": (zero + "[1]", ""),
        "input": ("11*,", "λ"),
        "eof": ("11*,", ""),
        "integer": ("111*!!!!,", ""),
        "character": ("11,", ""),
        "syntax": ("[", ""),
        "posthalt": ("", ""),
    }
    for fault, (source, stdin) in controls.items():

        class Fault(_Machine):
            mode = fault

            def __init__(self, code, io):
                if self.mode == "eof":
                    io.input_char = lambda: 0
                super().__init__(
                    code.replace("[", "x") if self.mode == "syntax" else code, io
                )

            def step(self):
                if self.halted:
                    if self.mode == "posthalt":
                        self.io.print_str("extra")
                    return
                pc, stack = self.state
                command = self.code[pc]
                super().step()
                at, values = self.state
                changed = list(values)
                if command == "*" and self.mode == "order":
                    changed[-5:] = reversed(changed[-5:])
                elif command == "*" and self.mode == "division" and stack[-1]:
                    changed[-2] = stack[-2] // stack[-1]
                elif command == "*" and self.mode == "zero" and not stack[-1]:
                    changed[-1] = stack[-2]
                elif (command == "~" and self.mode == "swap") or (
                    command == "!" and self.mode == "pop"
                ):
                    changed = list(stack)
                elif command == "[" and self.mode == "loop":
                    at = pc + 1
                elif command == "," and self.mode == "input":
                    changed[-1] %= 256
                elif command == "," and self.mode == "integer":
                    changed.pop()
                elif command == "," and self.mode == "character":
                    self.io.print_str("\n")
                self.state = type(self.state)(at, tuple(changed))

        with pytest.raises(AssertionError):
            _agrees(Fault, source, stdin, 64)
    return len(results), len(controls)
