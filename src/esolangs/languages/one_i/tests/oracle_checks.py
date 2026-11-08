"""Gaussian-rational and frame model of https://esolangs.org/wiki/1_%2B_i.

Exact arithmetic, integer powers, stack rolls, function selection/tail calls,
integer/character I/O and formatting, bounded to 64 steps. Inexact l/e and
non-integer powers, real/complex input parsers remain in the raw suite.
"""

from fractions import Fraction
from itertools import product

import pytest

from esolangs.languages.one_i.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled
from tests.support.model_input import token_span
from tests.support.workspace_oracle import agrees as workspace_agrees
from tests.support.workspace_oracle import missing_workspace, workspace_model

_ZERO, _I = (Fraction(0), Fraction(0)), (Fraction(0), Fraction(1))
_WORKSPACE = workspace_model("one-i-v2", "frames values input_cursor")


def _multiply(left, right):
    a, b = left
    c, d = right
    return a * c - b * d, a * d + b * c


def _reciprocal(value):
    a, b = value
    magnitude = a * a + b * b
    return a / magnitude, -b / magnitude


def _numeric(value):
    if value[0] == "fn":
        raise ValueError("halt")
    return value


def _math(command, operands):
    values = [_numeric(v) for v in operands]
    a, b = values[0]
    if command == "c":
        return a, -b
    if command == "/":
        return _reciprocal((a, b))
    c, d = values[1]
    if command == "+":
        return a + c, b + d
    if command == "*":
        return _multiply((a, b), (c, d))
    if command in "><":
        if b or d:
            raise ValueError("halt")
        return Fraction(not (a > c if command == ">" else a < c)), Fraction(0)
    assert not d, "only real exponents are in scope"
    assert c.denominator == 1, "only integer exponents are in scope"
    result = Fraction(1), Fraction(0)
    for _ in range(abs(int(c))):
        result = _multiply(result, (a, b))
    return _reciprocal(result) if c < 0 else result


def _decimal(value):
    return str(value.numerator) if value.denominator == 1 else str(float(value))


def _text(value):
    a, b = _numeric(value)
    if not b:
        return _decimal(a)
    imaginary = "i" if abs(b) == 1 else _decimal(abs(b)) + "i"
    if not a:
        return ("-" if b < 0 else "") + imaginary
    return _decimal(a) + (" - " if b < 0 else " + ") + imaginary


def _bytes(value):
    a, b = _numeric(value)
    result = chr((a.numerator // a.denominator) % 256)
    return result + (chr((b.numerator // b.denominator) % 256) if b >= 256 else "")


def _read(command, stdin, cursor):
    if command == "A":
        if cursor == len(stdin):
            return _I, cursor, None
        return (Fraction(ord(stdin[cursor])), Fraction(0)), cursor + 1, None
    start, cursor = token_span(stdin, cursor)
    if start == cursor:
        return None, cursor, "input"
    try:
        value = int(stdin[start:cursor])
    except ValueError:
        return None, cursor, "argument"
    return (Fraction(value), Fraction(0)), cursor, None


def _stack_command(command, stack):
    if command == ":":
        stack.append(stack[-1])
    elif command == "$":
        stack.pop()
    elif command == "(" and len(stack) > 1:
        stack.append(stack.pop(0))
    elif command == ")" and len(stack) > 1:
        stack.insert(0, stack.pop())
    elif command == "%" and len(stack) > 1:
        stack[0], stack[-1] = stack[-1], stack[0]


def _invoke(stack, frames, pc, end):
    decider = _numeric(stack.pop())
    chosen = stack[-2] if decider == _ZERO else stack[-1]
    if chosen[0] != "fn":
        raise ValueError("halt")
    if pc + 1 == end:
        frames.pop()
    frames.append((chosen[1], chosen[2], chosen[1] + 1, 0))


def _model(source, stdin):
    tokens = [(i, c) for i, c in enumerate(source) if not c.isspace()]
    code = "".join(c for _, c in tokens)
    closes, opens = {}, []
    for i, c in enumerate(code):
        if c == "[":
            opens.append(i)
        elif c == "]":
            closes[opens.pop()] = i
    frames, stack, output, trace = ([(-1, len(code), 0, 0)] if code else []), [], "", []
    cursor = 0

    def offset(start):
        return tokens[start][0] if start >= 0 else -1

    def row():
        values = tuple(("fn", offset(v[1])) if v[0] == "fn" else v for v in stack)
        state = (
            tuple((offset(start), pc, nth) for start, _, pc, nth in reversed(frames)),
            values,
            tokens[frames[-1][2]][0] if frames else len(source),
        )
        return state, not frames, output, cursor, cursor

    for tick in range(65):
        trace.append(row())
        if not frames:
            return None, trace + [row()] * 3
        if tick == 64:
            break
        start, end, pc, nth = frames[-1]
        command = code[pc]
        changed, calls, text = stack.copy(), frames.copy(), None
        calls[-1] = start, end, pc + 1, nth + 1
        try:
            if command == "[":
                changed.append(("fn", pc, closes[pc]))
                calls[-1] = start, end, closes[pc] + 1, nth + 1
            elif command == "i":
                changed.append(_I)
            elif command in "AB":
                value, cursor, error = _read(command, stdin, cursor)
                if error:
                    return error, [*trace, row()]
                changed.append(value)
            elif command in ":$()%":
                _stack_command(command, changed)
            elif command == "?":
                _invoke(changed, calls, pc, end)
            elif command in "po":
                value = changed.pop()
                text = (_text if command == "p" else _bytes)(value)
            else:
                count = 1 if command in "c/" else 2
                if len(changed) < count:
                    raise IndexError(command)
                operands, changed = changed[-count:], changed[:-count]
                changed.append(_math(command, operands))
        except (IndexError, ZeroDivisionError, ValueError):
            return "halt", [*trace, row()]
        while calls and calls[-1][2] >= calls[-1][1]:
            calls.pop()
        stack, frames = changed, calls
        if text is not None:
            output += text
    return None, trace


def _view(machine):
    frames, current = [], machine.frames
    while current is not None:
        (fn, pc, nth), current = current
        frames.append((fn.offset, pc, nth))
    stack = tuple(
        v if isinstance(v, tuple) else ("fn", v.offset) for v in machine.stack
    )
    return tuple(frames), stack, machine.ip


def _check(factory, code, stdin="unused"):
    assert all(c.isspace() or c in "ic+*/^><%:()$ABpo?[]" for c in code)
    workspace_agrees(
        _model(code, stdin),
        (factory, code, stdin),
        (
            _WORKSPACE,
            lambda row: (
                tuple(((start, nth) for start, _, nth in row[0][0])),
                row[0][1],
                row[-1],
            ),
        ),
        _view,
        cap=64,
    )


def check_raw_one_i():
    for size in range(4):
        for commands in product(
            ("i", "c", ":", "+", "*", "/", "$", "(", ")", "%"), repeat=size
        ):
            _check(_Machine, " ".join(commands))
    for left, right, command in product((-2, 0, 3), (-2, 0, 3), "+*^><"):
        _check(_Machine, "BB" + command + "p", f"{left} {right}")
    for code, stdin in product(
        ("Ap", "AA+o", "Bp", "BA+po", "Bi+cp", "B/p"),
        ("", "-2\n", "256 256", "bad", "λ\n", "3"),
    ):
        _check(_Machine, code, stdin)
    for code in (
        "ici*i+p",
        "[i][ic]i?p",
        "[i][ic]iic+?p",
        "[i?]i?",
        "[][]i?",
        "[]p",
        "[]ii?",
        "iic+?",
    ):
        _check(_Machine, code)
    for stdin in ("0", "1"):
        _check(_Machine, "[$$[(:p)i?]i?][$$p]B:)ii*+?", stdin)
    for source in ("x", "[", "]", "[[i]"):
        assert observed(_Machine, source, "unused", _view) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class WrongOutput(_Machine):
        def __init__(self, code, io):
            write = io.print_str
            io.print_str = lambda text: write(text + "!")
            super().__init__(code, io)

    for factory, code in (
        (stalled(_Machine), "ii+"),
        (WrongOutput, "ip"),
        (overread(_Machine), "Ap"),
        *(
            (missing_workspace(_Machine, field), "Ap")
            for field in _WORKSPACE.components
        ),
    ):
        with pytest.raises(AssertionError):
            _check(factory, code, "ab")
