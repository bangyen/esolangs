"""Independent single-row model of Super SNUSP's command table, rev 116460.

https://esolangs.org/wiki/Super_SNUSP. Tape, stack, arithmetic, skips,
scripted random ranges, numeric/character I/O and halt; mirrors remain in
raw grid tests. Character output retains the explicit public dialect choice.
"""

import re
from itertools import product

import pytest

from esolangs.languages.super_snusp.interpreter import _Machine
from tests.interpreters.oracle_support import observed, overread, stalled


class _Draw:
    def __init__(self, choice):
        self.choice = choice

    def randbelow(self, upper):
        return self.choice % upper


def _root(number, degree):
    if degree <= 0 or (number < 0 and degree % 2 == 0):
        raise ValueError("halt")
    if degree == 1:
        return number
    # The corpus bounds abs(number) by 15: this is literal arithmetic,
    # independent of production's exponential/binary root search.
    for value in range(-abs(number) - 1, abs(number) + 1):
        if value**degree <= number < (value + 1) ** degree:
            return value
    raise AssertionError((number, degree))


def _math(command, cell, operand):
    if command == "+":
        return cell + operand
    if command == "-":
        return cell - operand
    if command == "*":
        return cell * operand
    if command == "&":
        return cell & operand
    if command == "|":
        return cell | operand
    if command == "^":
        return cell ^ operand
    if command == ":":
        return cell // operand
    if command == "%":
        remainder = abs(cell) % abs(operand)
        return -remainder if cell < 0 else remainder
    if command == ";":
        return _root(cell, operand)
    if operand < 0:
        raise ValueError("halt")
    return cell << operand if command == "[" else cell >> operand


def _read(command, stdin, cursor):
    if command == ",":
        if cursor == len(stdin):
            return None, cursor, "input"
        return ord(stdin[cursor]), cursor + 1, None
    while cursor < len(stdin) and stdin[cursor].isspace():
        cursor += 1
    begin = cursor
    while cursor < len(stdin) and not stdin[cursor].isspace():
        cursor += 1
    if cursor == begin:
        return None, cursor, "input"
    token = stdin[begin:cursor]
    if re.fullmatch(r"[+-]?[0-9]+", token) is None:
        return None, cursor, "argument"
    return int(token), cursor, None


def _local(command, value, stack, choice):
    if command in "+-*%&|^:;[]":
        return _math(command, value, stack[-1])
    if command == "$":
        stack.pop()
    elif command == "{":
        stack.append(value)
    elif command == "}":
        return stack[-1]
    elif command == "(":
        return value - 1
    elif command == ")":
        return value + 1
    elif command == "_":
        return -value
    elif command == "~":
        return ~value
    elif command == "=":
        operand = stack.pop()
        return min(value, operand) + choice % (abs(value - operand) + 1)
    return value


def _model(source, stdin, choice):
    col = source.index('"') if '"' in source else len(source.rstrip()) - 1
    pointer = cursor = 0
    cells, stack, output, trace = {}, [], "", []
    digit = done = False

    def row():
        state = (
            (0, col, 0),
            (pointer, tuple(sorted((i, v) for i, v in cells.items() if v))),
            tuple(stack),
            digit,
            done,
        )
        return state, done, output, cursor, cursor

    for tick in range(65):
        trace.append(row())
        if done:
            return None, trace + [row()] * 3
        if tick == 64:
            break
        command, value, advance = source[col], cells.get(pointer, 0), 1
        changed, position, next_digit, text = stack.copy(), pointer, False, ""
        if command in ",@":
            value, cursor, error = _read(command, stdin, cursor)
            if error:
                return error, [*trace, row()]
        try:
            if command in "0123456789":
                value, next_digit = (value * 10 if digit else 0) + int(command), True
            elif command == "'":
                digit, done = False, True
                continue
            elif command == ">":
                position += 1
            elif command == "<":
                position -= 1
            elif command in "!?`":
                advance = (
                    2
                    if command == "!"
                    or (command == "?" and value == 0)
                    or (command == "`" and value < 0)
                    else 1
                )
            elif command == "#":
                text = str(value)
            elif command == ".":
                if not 0 <= value <= 0x10FFFF or 0xD800 <= value <= 0xDFFF:
                    raise ValueError("halt")
                text = chr(value)
            elif ("A" <= command <= "Z" or "a" <= command <= "z") and command != "@":
                value = ord(command)
            else:
                value = _local(command, value, changed, choice)
        except (IndexError, ZeroDivisionError):
            return "halt", [*trace, row()]
        except ValueError as error:
            return str(error), [*trace, row()]
        cells[pointer] = value
        pointer, stack, digit = position, changed, next_digit
        col += advance
        done = col >= len(source)
        output += text
    return None, trace


def _check(factory, source, stdin="unused", choice=0):
    assert not any(c in source for c in "/\\"), (
        "mirrors are outside the single-row model"
    )

    def build(code, io):
        return factory([code], io, _Draw(choice))

    assert observed(build, source, stdin, lambda m: tuple(m.state), cap=64) == _model(
        source, stdin, choice
    ), (source, stdin, choice)


def check_raw_super_snusp():
    def number(value):
        return str(abs(value)) + ("_" if value < 0 else "")

    for left, right, command in product((-7, 0, 3, 15), (-2, 0, 2, 5), "+-*%&|^:;[]"):
        _check(_Machine, '"' + number(right) + "{" + number(left) + command + "#'")
    for code in (
        '"1{2}',
        '"{>$<}',
        '"()~#',
        '"12 3#',
        '"0?!9#',
        '"1_`9#',
        '"!9#',
        '"$',
        '"}',
        '"+',
        '"',
        "'",
    ):
        _check(_Machine, code)
    for left, right, choice in product((0, 2, 5), (0, 3), (0, 1, 4)):
        _check(
            _Machine, '"' + number(right) + "{" + number(left) + "=#'", choice=choice
        )
    for code, stdin in product(
        ('"@#,.', '",.#', '"@#'), ("", " -12 x", "λ\n", "2 3", "\n")
    ):
        _check(_Machine, code, stdin)
    for source in ([], [""]):
        assert observed(_Machine, source, "", lambda m: tuple(m.state)) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class WrongDraw(_Machine):
        def __init__(self, code, io, _rng):
            super().__init__(code, io, _Draw(1))

    for factory, code in (
        (stalled(_Machine), '"1'),
        (WrongDraw, '"1{0=#'),
        (overread(_Machine), '",.#'),
    ):
        with pytest.raises(AssertionError):
            _check(factory, code, "ab")
