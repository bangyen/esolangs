"""Independent known-instruction semantics for the What!? specification.

Blueprints emit source and offsets; they never parse native tokens or stores.
The original closed-form oracle remains complementary terminal evidence.
"""

import re
from itertools import product
from typing import NamedTuple


class _Guard(NamedTuple):
    literal: int | str
    operators: str
    after: int


class _Op(NamedTuple):
    kind: str
    argument: int | str | _Guard
    offset: int


class _Case(NamedTuple):
    source: str
    stdin: str
    operations: tuple[_Op, ...] | None


class _Moved(NamedTuple):
    instruction: int
    pointer: int
    integers: list[int]
    strings: list[str]
    output: str


def _quote(text):
    assert '"' not in text
    assert "\\" not in text
    return '"' + text.replace("\n", "\\n") + '"'


def _assemble(specs, stdin=""):
    source, operations = "", []
    for kind, argument in specs:
        if kind == "num":
            assert type(argument) is int
            assert 0 <= argument < 65536
            fragment = str(argument)
        elif kind == "str":
            fragment = _quote(argument)
        elif kind == "sub":
            fragment = "'" + argument + "'"
        elif kind == "out":
            fragment = "!" * argument
        elif kind == "in":
            fragment = "?" * argument
        elif kind == "cond":
            literal = argument.literal
            fragment = (
                "["
                + (_quote(literal) if type(literal) is str else str(literal))
                + argument.operators
            )
        else:
            assert kind in ",.+-*/()]"
            fragment = kind
        if source and fragment and source[-1] == fragment[0] and fragment[0] in "!?":
            source += " "
        operations.append(_Op(kind, argument, len(source)))
        source += fragment
    return _Case(source, stdin, tuple(operations))


def _metadata(case):
    answer = []
    for kind, arg, offset in case.operations:
        value, text, literal, ops = 0, "", 0, ""
        if kind in ("num", "out", "in", ")"):
            value = arg
        elif kind == "sub":
            value = len(arg)
        elif kind == "str":
            text = arg
        elif kind == "cond":
            value, literal, ops = arg.after, arg.literal, arg.operators
        answer.append((kind, offset, value, text, literal, ops))
    return tuple(answer)


class _Input:
    def __init__(self, text):
        self.text, self.cursor = text, 0
        self.reads = self.past = self.lines = 0
        self.character = self.newline = False

    def read(self, size):
        start = self.cursor
        if size == 2:
            while self.cursor < len(self.text) and self.text[self.cursor].isspace():
                self.character = True
                self.cursor += 1
            if self.cursor == len(self.text):
                self.character = True
                self.past += 1
                return 0, None
            begin = self.cursor
            while self.cursor < len(self.text) and not self.text[self.cursor].isspace():
                self.cursor += 1
            self.character = True
            token = self.text[begin : self.cursor]
            self.reads += 1
            self.newline = False
            if re.fullmatch(r"[+-]?[0-9]+", token) is None:
                return None, "argument"
            negative = token[0] == "-"
            digits = token[1:] if token[0] in "+-" else token
            value = 0
            for digit in digits:
                value = value * 10 + ord(digit) - ord("0")
            return -value if negative else value, None
        if size == 1:
            self.character = True
        if start == len(self.text):
            self.past += 1
            return ("" if size == 3 else 0), None
        if size == 1:
            value = ord(self.text[start])
            self.cursor += 1
        else:
            end = self.text.find("\n", start)
            stop = len(self.text) if end < 0 else end
            value = self.text[start:stop].removesuffix("\r")
            self.cursor = stop if end < 0 else stop + 1
            self.lines += 1
        self.reads += 1
        self.newline = False
        return value, None


def _holds(guard, integer, text):
    value = text if type(guard.literal) is str else integer
    choices = {
        ":": guard.literal == value,
        "<": guard.literal < value,
        ">": guard.literal > value,
    }
    positive = (
        any(choices[op] for op in guard.operators if op != ";")
        if guard.operators != ";"
        else choices[":"]
    )
    return not positive if ";" in guard.operators else positive


def _change(op, pc, pointer, integers, strings, supplied):
    kind, arg, _offset = op
    numbers, texts = integers.copy(), strings.copy()
    next_pc, text = pc + 1, ""
    if kind == "num":
        numbers[pointer] = arg
    elif kind == "str" or (kind == "in" and arg == 3):
        addition = arg if kind == "str" else supplied
        texts[pointer] += addition
        if len(texts[pointer]) > 256:
            raise ValueError("string limit")
    elif kind == "sub":
        numbers[pointer] = (numbers[pointer] - len(arg)) % 65536
    elif kind == "in":
        if not 0 <= supplied <= 65535:
            raise ValueError("word limit")
        numbers[pointer] = supplied
    elif kind == "out":
        if arg == 1:
            if 55296 <= numbers[pointer] <= 57343:
                raise ValueError("surrogate")
            text = chr(numbers[pointer])
        elif arg == 2:
            text = str(numbers[pointer])
        else:
            text = texts[pointer] if arg == 3 else "\n"
    elif kind in ("+", "-", "*", "/"):
        if pointer == 0:
            raise ValueError("no left slot")
        previous, current = numbers[pointer - 1], numbers[pointer]
        if kind == "+":
            result = current + previous
        elif kind == "-":
            result = current - previous
        elif kind == "*":
            result = current * previous
        else:
            result = current // previous
        numbers[pointer] = result % 65536
    elif kind in (",", "."):
        pointer += 1 if kind == "." else -1
        if not 0 <= pointer <= 255:
            raise ValueError("pointer limit")
    elif kind == ")" and numbers[pointer] != 0:
        next_pc = arg + 1
    elif kind == "cond" and not _holds(arg, numbers[pointer], texts[pointer]):
        next_pc = arg.after
    return _Moved(next_pc, pointer, numbers, texts, text)


def _model(case, *, cap=128):
    if case.operations is None:
        return "syntax", [(None, False, "", 0, 0)]
    pc = pointer = 0
    integers, strings = [0] * 256, [""] * 256
    io = _Input(case.stdin)
    output, rows = "", []

    def row():
        halted = pc >= len(case.operations)
        offset = -1 if halted else case.operations[pc].offset
        state = (
            pc,
            pointer,
            tuple(integers),
            tuple(strings),
            offset,
            io.reads,
            io.past,
            io.lines,
            io.character,
            io.newline,
        )
        return state, halted, output, io.cursor, io.cursor

    for tick in range(cap + 1):
        rows.append(row())
        if pc >= len(case.operations):
            return None, rows + [row()] * 3
        if tick == cap:
            return None, rows
        op = case.operations[pc]
        supplied = None
        if op.kind == "in":
            supplied, error = io.read(op.argument)
            if error:
                return error, [*rows, row()]
        try:
            moved = _change(op, pc, pointer, integers, strings, supplied)
        except (ValueError, ZeroDivisionError):
            return "halt", [*rows, row()]
        pc, pointer, integers, strings, text = moved
        output += text
        if text:
            io.newline = not text.endswith("\n")
    raise AssertionError("bounded model did not return")


def _cases():
    cases = []
    for left, right, token in product((0, 1, 11, 65535), (0, 2, 10, 65534), "+-*/"):
        case = _assemble(
            (
                ("num", left),
                (".", 0),
                ("str", "tag"),
                ("num", right),
                (token, 0),
                ("out", 2),
                ("str", "!"),
                ("out", 3),
            )
        )
        assert case.source == f'{left}."tag"{right}{token}!!"!"!!!'
        cases.append(case)
    for count, value in product(range(1, 9), ("A", "Ω", "\n")):
        case = _assemble(
            (
                ("num", 1),
                (".", 0),
                ("num", count),
                ("(", 0),
                ("str", "x"),
                ("-", 0),
                (")", 3),
                ("out", 3),
                (".", 0),
                ("in", 1),
                ("out", 2),
            ),
            value,
        )
        assert case.source == f'1.{count}("x"-)!!!.?!!'
        cases.append(case)
    for literal, current, op in product(
        (0, 2, 9), (0, 3, 9), (":", "<", ">", ";", ":;", "<>")
    ):
        case = _assemble(
            (
                ("num", current),
                ("cond", _Guard(literal, op, 4)),
                ("str", "yes"),
                ("]", 0),
                ("str", "end"),
                ("out", 3),
            )
        )
        assert case.source == f'{current}[{literal}{op}"yes"]"end"!!!'
        cases.append(case)
    assert len(cases) == 142
    return cases


def _parts(row):
    return *row[0][:4], row[-1]
