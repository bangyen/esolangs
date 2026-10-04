"""Vector geometry and mutable sparse fields for the B-tapemark profile."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    real: int
    imag: int

    def __add__(self, vector):
        return Point(self.real + int(vector.real), self.imag + int(vector.imag))


class Reference:
    def __init__(self, source, stdin=""):
        self.fields = [{}, {}]
        starts = []
        quoted = False
        directions = {">": 1, "v": -1j, "<": -1, "^": 1j}
        commands = set(" \\/!+-*|?%0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        for row, line in enumerate(re.split(r"\r\n?|\n", source)):
            for column, symbol in enumerate(line):
                point = Point(column, -row)
                if symbol == '"':
                    quoted = not quoted
                elif quoted:
                    continue
                elif symbol in directions:
                    starts.append((point, directions[symbol]))
                elif symbol not in commands:
                    raise ValueError("invalid symbol")
                elif symbol != " ":
                    self.fields[0][point] = symbol
        if quoted:
            raise ValueError("unclosed comment")
        if len(starts) != 1:
            raise ValueError("one starting marker required")
        point, self.heading = starts[0]
        self.points = [point, point]
        self.active = 0
        self.halted = False
        self.stdin = stdin
        self.offset = 0
        self.past_end = 0
        self.stdout = ""
        self.writes = []

    def input(self):
        if self.offset == len(self.stdin):
            self.past_end += 1
            raise EOFError()
        symbol = self.stdin[self.offset]
        self.offset += 1
        return symbol

    def paint(self, field, point, symbol):
        self.writes.append((field, point, symbol))
        if symbol == " ":
            self.fields[field].pop(point, None)
        else:
            self.fields[field][point] = symbol

    def step(self):
        self.writes = []
        if self.halted:
            return
        data = 1 - self.active
        opcode = self.fields[self.active].get(self.points[self.active], " ")
        symbol = self.fields[data].get(self.points[data], " ")
        if opcode == "!":
            self.halted = True
            return
        if opcode == "\\":
            self.heading = -1j * self.heading.conjugate()
        elif opcode == "/":
            self.heading = 1j * self.heading.conjugate()
        elif opcode == "+":
            self.stdout += symbol
        elif opcode == "-" and symbol == " ":
            self.paint(data, self.points[data], self.input())
        elif opcode == "*":
            self.points[self.active] += self.heading
            if symbol == " ":
                skipped = self.fields[self.active].get(self.points[self.active], " ")
                self.paint(data, self.points[data], skipped)
        elif opcode == "|":
            self.points[data] += self.heading
        elif (opcode == "?" and symbol == " ") or (opcode == "%" and symbol != " "):
            self.active = data
        elif opcode in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if not self.heading.imag:
                self.stdout += opcode
            elif symbol == opcode:
                self.active = data
        self.points[self.active] += self.heading

    def native_view(self):
        def point(z):
            return z.real, -z.imag

        heading = (1, -1j, -1, 1j).index(self.heading)
        return (
            self.active,
            tuple(map(point, self.points)),
            heading,
            tuple(
                frozenset((point(z), symbol) for z, symbol in field.items())
                for field in self.fields
            ),
            self.halted,
            self.offset,
            self.past_end,
            self.stdout,
        )
