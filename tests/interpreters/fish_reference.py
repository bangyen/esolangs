"""Fish rules: https://esolangs.org/wiki/Fish?oldid=190300.

Immutable scopes and compass transforms use the declared rectangular profile.
Author IO/jump controls: https://gist.github.com/anonymous/6392418.
"""

import math
from fractions import Fraction


class FishError(Exception):
    pass


def integer(value):
    if type(value) is float and (not math.isfinite(value) or int(value) != value):
        raise FishError("nonintegral operand")
    return int(value)


def decimal(value):
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    value = abs(value)
    chunks = []
    while value:
        value, digit = divmod(value, 10000)
        chunks.append(digit)
    return (
        sign
        + str(chunks[-1])
        + "".join(f"{digit:04d}" for digit in reversed(chunks[:-1]))
    )


class Reference:
    def __init__(self, rows, stdin=""):
        if not rows or not max(map(len, rows)):
            raise ValueError("empty codebox")
        self.cells = {
            (column, row): ord(char)
            for row, line in enumerate(rows)
            for column, char in enumerate(line)
        }
        self.bounds = (max(map(len, rows)), len(rows))
        self.position = (0, 0)
        self.heading = 0
        self.scopes = ((),)
        self.registers = (None,)
        self.quote = None
        self.done = False
        self.stdin = stdin
        self.offset = 0
        self.past_end = 0
        self.output = ""
        self.draws = []
        self._packed_source = None
        self._packed = ()

    def take(self):
        if not self.scopes[-1]:
            raise FishError("empty scope")
        value = self.scopes[-1][-1]
        self.scopes = (*self.scopes[:-1], self.scopes[-1][:-1])
        return value

    def push(self, *values):
        self.scopes = (*self.scopes[:-1], (*self.scopes[-1], *values))

    def movement(self):
        if self.heading % 2 == 0:
            return (1 if self.heading == 0 else -1, 0)
        return (0, -1 if self.heading == 1 else 1)

    def move(self, count=1):
        x, y = self.position
        dx, dy = self.movement()
        width, height = self.bounds
        self.position = ((x + dx * count) % width, (y + dy * count) % height)

    def instruction(self):
        value = self.cells.get(self.position, 0)
        if not 0 <= value <= 0x10FFFF:
            raise FishError("invalid character")
        return chr(value)

    def step(self, choice=0):
        if self.done:
            return
        op = self.instruction()
        skip = 1
        if self.quote is not None:
            if op == self.quote:
                self.quote = None
            else:
                self.push(self.cells.get(self.position, 0))
            self.move()
            return
        if op in "'\"":
            self.quote = op
        elif op in "0123456789abcdef":
            self.push("0123456789abcdef".index(op))
        elif op in "+-*,%()=":
            right = self.take()
            left = self.take()
            try:
                if op == "+":
                    result = left + right
                elif op == "-":
                    result = left - right
                elif op == "*":
                    result = left * right
                elif op == ",":
                    if right == 0:
                        raise FishError("zero divisor")
                    if type(left) is float or type(right) is float:
                        left, right = float(left), float(right)
                    result = float(Fraction(left) / Fraction(right))
                elif op == "%":
                    if right == 0:
                        raise FishError("zero divisor")
                    result = divmod(left, right)[1]
                elif op == "(":
                    result = int(left < right)
                elif op == ")":
                    result = int(left > right)
                else:
                    result = int(left == right)
            except (OverflowError, ValueError):
                raise FishError("numeric overflow") from None
            if type(result) is float and not math.isfinite(result):
                raise FishError("numeric overflow")
            self.push(result)
        elif op in "><^v":
            self.heading = {">": 0, "^": 1, "<": 2, "v": 3}[op]
        elif op in "/\\|_#":
            if op == "/":
                self.heading = (1 - self.heading) % 4
            elif op == "\\":
                self.heading = (3 - self.heading) % 4
            elif op == "|":
                self.heading = (2 - self.heading) % 4
            elif op == "_":
                self.heading = (-self.heading) % 4
            else:
                self.heading = (self.heading + 2) % 4
        elif op == "x":
            self.draws.append(4)
            self.heading = (-choice) % 4
        elif op == "!":
            skip = 2
        elif op == "?":
            skip = 2 if self.take() == 0 else 1
        elif op == ".":
            y = integer(self.take())
            x = integer(self.take())
            if x < 0 or y < 0:
                raise FishError("negative jump")
            self.position = (x, y)
        elif op == ":":
            value = self.take()
            self.push(value, value)
        elif op == "~":
            self.take()
        elif op == "$":
            first = self.take()
            second = self.take()
            self.push(first, second)
        elif op == "@":
            first = self.take()
            second = self.take()
            third = self.take()
            self.push(first, third, second)
        elif op in "}{r":
            values = self.scopes[-1]
            if not values and op != "r":
                raise FishError("empty rotation")
            moved = (
                values[-1:] + values[:-1]
                if op == "}"
                else values[1:] + values[:1]
                if op == "{"
                else values[::-1]
            )
            self.scopes = (*self.scopes[:-1], moved)
        elif op == "l":
            self.push(len(self.scopes[-1]))
        elif op == "[":
            count = integer(self.take())
            values = self.scopes[-1]
            if count < 0 or count > len(values):
                raise FishError("invalid scope size")
            old = values[:-count] if count else values
            new = values[-count:] if count else ()
            self.scopes = (*self.scopes[:-1], old, new)
            self.registers = (*self.registers, None)
        elif op == "]":
            if len(self.scopes) == 1:
                self.scopes = ((),)
                self.registers = (None,)
            else:
                self.scopes = (*self.scopes[:-2], self.scopes[-2] + self.scopes[-1])
                self.registers = self.registers[:-1]
        elif op == "&":
            value = self.registers[-1]
            if value is None:
                value = self.take()
            else:
                self.push(value)
                value = None
            self.registers = (*self.registers[:-1], value)
        elif op in "gp":
            y = integer(self.take())
            x = integer(self.take())
            if op == "g":
                self.push(self.cells.get((x, y), 0))
            else:
                value = integer(self.take())
                self.cells = {**self.cells, (x, y): value}
                self.bounds = (max(self.bounds[0], x + 1), max(self.bounds[1], y + 1))
        elif op == "i":
            if self.offset == len(self.stdin):
                self.past_end += 1
                self.push(-1)
            else:
                self.push(ord(self.stdin[self.offset]))
                self.offset += 1
        elif op == "o":
            value = integer(self.take())
            if not 0 <= value <= 0x10FFFF:
                raise FishError("invalid output character")
            self.output += chr(value)
        elif op == "n":
            value = self.take()
            if type(value) is float and not math.isfinite(value):
                raise FishError("numeric overflow")
            self.output += decimal(int(value)) if int(value) == value else str(value)
        elif op == ";":
            self.done = True
            return
        elif op not in " \t\r\n\0":
            raise FishError("unknown instruction")
        self.move(skip)

    def packed_cells(self):
        if self._packed_source is not self.cells:
            self._packed_source = self.cells
            self._packed = tuple(sorted(self.cells.items()))
        return self._packed

    def view(self):
        dx, dy = self.movement()
        x, y = self.position
        return (
            x,
            y,
            dx,
            dy,
            self.packed_cells(),
            self.scopes,
            self.registers,
            self.quote,
            self.done,
            self.bounds[0],
            self.bounds[1],
            self.offset,
        )
