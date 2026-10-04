"""Dig's mole, adjacent operands and underground tile budget, independently."""

import re
from typing import ClassVar
from unicodedata import decimal


def integer(text):
    if re.fullmatch(r"[+-]?\d(?:_?\d)*", text) is None:
        raise ValueError("invalid integer")
    sign = -1 if text.startswith("-") else 1
    digits = text[1:] if text[:1] in "+-" else text
    if not digits:
        raise ValueError("empty integer")
    total = 0
    for digit in digits.replace("_", ""):
        total = 10 * total + decimal(digit)
    return sign * total


def decimal_text(value):
    if value == 0:
        return "0"
    digits = []
    magnitude = abs(value)
    while magnitude:
        magnitude, digit = divmod(magnitude, 10)
        digits.append(chr(48 + digit))
    return ("-" if value < 0 else "") + "".join(reversed(digits))


class MissingOperandError(Exception):
    pass


class NegativeDistanceError(Exception):
    pass


class ZeroDivisorError(Exception):
    pass


class Reference:
    headings = (1j, 1, -1j, -1)
    arrows: ClassVar[dict[str, complex]] = dict(zip("^>'<", headings, strict=True))

    def __init__(self, code, stdin=""):
        if not code or not any(row.strip() for row in code):
            raise ValueError("empty program")
        self.width = max(map(len, code))
        self.height = len(code)
        self.rows = [list(row.ljust(self.width)) for row in code]
        self.point = 0j
        self.heading = 1
        self.value = 0
        self.depth = 0
        self.done = False
        self.stdin = stdin
        self.offset = self.reads = self.past_end = 0
        self.output = ""
        self._rows_for_code = None
        self._code = ()

    @property
    def code(self):
        if self._rows_for_code is not self.rows:
            old_rows = self._rows_for_code
            self._code = tuple(
                self._code[index]
                if old_rows is not None and row is old_rows[index]
                else tuple(row)
                for index, row in enumerate(self.rows)
            )
            self._rows_for_code = self.rows
        return self._code

    def at(self, point):
        return self.rows[-int(point.imag)][int(point.real)]

    def inside(self, point):
        return 0 <= point.real < self.width and -self.height < point.imag <= 0

    def operand(self):
        for direction in (1j, 1, -1j, -1):
            point = self.point + direction
            if self.inside(point):
                value = self.at(point)
                if isinstance(value, int):
                    return value
                if value in "0123456789":
                    return ord(value) - 48
        raise MissingOperandError

    def input(self, *, token=False):
        if token:
            while self.offset < len(self.stdin) and self.stdin[self.offset].isspace():
                self.offset += 1
        if self.offset == len(self.stdin):
            self.past_end += 1
            raise EOFError
        start = self.offset
        if token:
            while (
                self.offset < len(self.stdin) and not self.stdin[self.offset].isspace()
            ):
                self.offset += 1
        else:
            self.offset += 1
        self.reads += 1
        text = self.stdin[start : self.offset]
        return integer(text) if token else ord(text)

    def step(self):
        if self.done:
            return
        char = self.at(self.point)
        heading, value, depth = self.heading, self.value, self.depth
        rows = self.rows
        if isinstance(char, int):
            if depth > 0:
                value = char
                depth -= 1
        elif depth > 0:
            if char == "%":
                operand = self.operand()
                if operand in (0, 1):
                    value = (32, 10)[operand]
            elif char in "=~":
                value = self.input(token=char == "~")
            elif char == ":":
                self.output += decimal_text(value) if value < 10 else chr(value)
                value = 0
            elif char in "+-*/":
                operand = self.operand()
                if char == "+":
                    value = value + operand
                elif char == "-":
                    value = value - operand
                elif char == "*":
                    value = value * operand
                elif operand == 0:
                    raise ZeroDivisorError
                else:
                    quotient, _remainder = divmod(value, operand)
                    value = quotient
            elif char == ";":
                rows = list(rows)
                row = -int(self.point.imag)
                rows[row] = list(rows[row])
                rows[row][int(self.point.real)] = value
            elif char in "0123456789":
                value = ord(char) - 48
            elif char.isalpha() or char in ".,!?":
                value = ord(char)
            depth -= 1
        elif char in self.arrows:
            heading = self.arrows[char]
        elif char == "#":
            operand = self.operand()
            if operand in (0, 1):
                heading *= (1j, -1j)[operand]
        elif char == "$":
            depth = self.operand()
            if depth < 0:
                raise NegativeDistanceError
        elif char == "@":
            self.done = True
            return
        self.point += heading
        self.heading, self.value, self.depth, self.rows = heading, value, depth, rows
        self.done = not self.inside(self.point)

    def snapshot(self):
        return (
            -int(self.point.imag),
            int(self.point.real),
            self.headings.index(self.heading),
            self.value,
            self.depth,
            self.code,
            self.offset,
            self.reads,
        )
