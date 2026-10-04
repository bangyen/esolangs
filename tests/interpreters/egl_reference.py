"""Independent EGL semantics from wiki revision 46755."""

import re
from unicodedata import decimal


def integer(text):
    value = 0
    for digit in text:
        value = value * 10 + decimal(digit)
    return value


def display(value):
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    value = abs(value)
    digits = []
    while value:
        value, digit = divmod(value, 10)
        digits.append(chr(48 + digit))
    return sign + "".join(reversed(digits))


class Reference:
    def __init__(self, source, stdin=""):
        header, separator, self.program = source.partition(":")
        dimensions = header.split(",")
        if (
            not separator
            or len(dimensions) != 2
            or any(re.fullmatch(r"\d+", d) is None for d in dimensions)
        ):
            raise ValueError("dimensions")
        self.width, self.height = map(integer, dimensions)
        if min(self.width, self.height) <= 0:
            raise ValueError("dimensions")
        self.close = {}
        pending = []
        for position, char in enumerate(self.program):
            if char == "(":
                pending.append(position)
            elif char == ")":
                if not pending:
                    raise ValueError("loops")
                self.close[pending.pop()] = position
        if pending:
            raise ValueError("loops")
        self.cells = {(x, y): 0 for y in range(self.height) for x in range(self.width)}
        self.point = (0, 0)
        self.pc = 0
        self.frames = []
        self.stdin = stdin
        self.offset = self.reads = self.past_end = 0
        self.output = ""
        self._values = None

    @property
    def done(self):
        return self.pc >= len(self.program)

    @property
    def values(self):
        if self._values is None:
            self._values = tuple(
                self.cells[x, y] for y in range(self.height) for x in range(self.width)
            )
        return self._values

    def snapshot(self):
        x, y = self.point
        return (
            self.pc,
            y,
            x,
            self.values,
            tuple((p, q[1], q[0]) for p, q in self.frames),
            self.offset,
            self.reads,
        )

    def step(self):
        if self.done:
            return
        op = self.program[self.pc]
        x, y = self.point
        point = self.point
        cell = self.cells[point]
        pc = self.pc + 1
        if op in "><^v":
            dx, dy = {">": (1, 0), "<": (-1, 0), "^": (0, -1), "v": (0, 1)}[op]
            x, y = x + dx, y + dy
        elif op in "_|%":
            if op in "|%":
                x = self.width - 1 - x
            if op in "_%":
                y = self.height - 1 - y
        if not 0 <= x < self.width or not 0 <= y < self.height:
            raise ValueError("off grid")
        if op == "x":
            if self.offset == len(self.stdin):
                self.past_end += 1
                raise EOFError
            cell = ord(self.stdin[self.offset])
            self.offset += 1
            self.reads += 1
        elif op == "+":
            cell += 1
        elif op == "-":
            cell -= 1
        elif op == "=":
            self.output += display(cell)
        elif op == "#":
            self.output += "".join(
                "|"
                + "|".join(display(self.cells[a, b]) for a in range(self.width))
                + "|\n"
                for b in range(self.height)
            )
        elif op == "(":
            if cell:
                self.frames.append((self.pc, point))
            else:
                pc = self.close[self.pc] + 1
        elif op == ")":
            opening, anchor = self.frames[-1]
            if self.cells[anchor]:
                pc = opening + 1
            else:
                self.frames.pop()
        if self.cells[point] != cell:
            self.cells[point] = cell
            if self._values is not None:
                index = point[1] * self.width + point[0]
                self._values = (*self._values[:index], cell, *self._values[index + 1 :])
        self.point = x, y
        self.pc = pc
