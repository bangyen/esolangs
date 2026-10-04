"""Independent flat torus for the rel_2_25 Befunge-93 specification.

https://github.com/catseye/Befunge-93/blob/rel_2_25/doc/Befunge-93.markdown
Unrepresentable results abort; byte signedness follows the declared profile.
"""

import struct
import unicodedata


class ArithmeticFaultError(Exception):
    pass


class MissingInputError(EOFError):
    pass


class BadNumberError(ValueError):
    pass


class Reference:
    def __init__(self, rows, stdin=""):
        if not rows or not max(map(len, rows)):
            raise ValueError("empty program")
        if len(rows) > 25 or max(map(len, rows)) > 80:
            raise ValueError("oversized torus")
        if any(ord(char) > 255 for row in rows for char in row):
            raise ValueError("not byte source")
        self.cells = tuple(
            ord(char)
            for row in (*rows, *([""] * (25 - len(rows))))
            for char in row.ljust(80)
        )
        self.position = 0j
        self.direction = 1 + 0j
        self.values = ()
        self.string = False
        self.done = False
        self.stdin = stdin
        self.offset = 0
        self.past_end = 0
        self.output = ""
        self.draws = []
        self.word_bits = struct.calcsize("l") * 8
        self.lower = -(1 << (self.word_bits - 1))
        self.upper = (1 << (self.word_bits - 1)) - 1
        self._grid_source = None
        self._grid = ()

    def pop(self):
        if not self.values:
            return 0
        item = self.values[-1]
        self.values = self.values[:-1]
        return item

    def push(self, *values):
        if any(value < self.lower or value > self.upper for value in values):
            raise ArithmeticFaultError("signed-long overflow")
        self.values = (*self.values, *values)

    def character(self):
        if self.offset == len(self.stdin):
            self.past_end += 1
            raise MissingInputError()
        value = ord(self.stdin[self.offset]) % 256
        self.offset += 1
        return value

    def number(self):
        while self.offset < len(self.stdin) and self.stdin[self.offset].isspace():
            self.offset += 1
        if self.offset == len(self.stdin):
            self.past_end += 1
            raise MissingInputError()
        begin = self.offset
        while self.offset < len(self.stdin) and not self.stdin[self.offset].isspace():
            self.offset += 1
        token = self.stdin[begin : self.offset]
        sign = -1 if token[0] == "-" else 1
        if token[0] in "+-":
            token = token[1:]
        result = 0
        previous_digit = False
        for char in token:
            if char == "_":
                if not previous_digit:
                    raise BadNumberError()
                previous_digit = False
                continue
            try:
                digit = unicodedata.decimal(char)
            except ValueError:
                raise BadNumberError() from None
            result = 10 * result + digit
            previous_digit = True
        if not previous_digit:
            raise BadNumberError()
        return sign * result

    def move(self, count=1):
        target = self.position + count * self.direction
        self.position = complex(int(target.real) % 80, int(target.imag) % 25)

    def step(self, choice=0):
        if self.done:
            return
        index = int(self.position.imag) * 80 + int(self.position.real)
        char = chr(self.cells[index])
        if self.string and char != '"':
            self.push(self.cells[index])
            self.move()
            return
        number = None
        if char == "~":
            number = self.character()
        elif char == "&" or (
            char in "/%" and (not self.values or self.values[-1] == 0)
        ):
            try:
                number = self.number()
            except MissingInputError:
                if char == "&":
                    raise
        if char == '"':
            self.string = not self.string
        elif char in "0123456789":
            self.push(ord(char) - 48)
        elif char in "+-*/%`":
            right, left = self.pop(), self.pop()
            if char == "+":
                result = left + right
            elif char == "-":
                result = left - right
            elif char == "*":
                result = left * right
            elif char == "`":
                result = int(left > right)
            elif right == 0:
                if number is None:
                    raise ArithmeticFaultError("undefined quotient")
                result = number
            else:
                quotient, remainder = divmod(left, right)
                if remainder and ((left < 0) != (right < 0)):
                    quotient += 1
                result = quotient if char == "/" else left - quotient * right
            self.push(result)
        elif char == "!":
            self.push(int(self.pop() == 0))
        elif char in "><v^":
            self.direction = {">": 1, "<": -1, "v": 1j, "^": -1j}[char]
        elif char == "?":
            self.draws.append(4)
            self.direction = 1j**choice
        elif char in "_|":
            axis = 1 if char == "_" else 1j
            self.direction = axis if self.pop() == 0 else -axis
        elif char == ":":
            value = self.pop()
            self.push(value, value)
        elif char == "\\":
            top, next_value = self.pop(), self.pop()
            self.push(top, next_value)
        elif char == "$":
            self.pop()
        elif char == ".":
            self.output += str(self.pop()) + " "
        elif char == ",":
            self.output += chr(self.pop() % 256)
        elif char == "#":
            self.move()
        elif char in "gp":
            y, x = self.pop(), self.pop()
            inside = 0 <= x < 80 and 0 <= y < 25
            if char == "g":
                self.push(self.cells[y * 80 + x] if inside else 0)
            else:
                value = self.pop() % 256
                if inside:
                    at = y * 80 + x
                    self.cells = (*self.cells[:at], value, *self.cells[at + 1 :])
        elif char in "&~":
            self.push(number)
        elif char == "@":
            self.done = True
        self.move()

    def grid(self):
        if self._grid_source is not self.cells:
            self._grid_source = self.cells
            self._grid = tuple(
                tuple(chr(value) for value in self.cells[at : at + 80])
                for at in range(0, 2000, 80)
            )
        return self._grid

    def view(self):
        return (
            int(self.position.real),
            int(self.position.imag),
            int(self.direction.real),
            int(self.direction.imag),
            self.grid(),
            self.values,
            self.string,
            self.done,
            self.offset,
        )
