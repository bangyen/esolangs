"""Unexecuted bounded shared-array reference; no native semantic helpers."""

import re
from enum import Enum


class Marker(Enum):
    SELF = "self"
    NAN = "nan"


class ModelError(Exception):
    pass


def _parse(source):
    rows = source.split("\n")
    if rows[-1] == "":
        rows.pop()
    counts = []
    for row in rows:
        words = [word for word in row.replace("\r", " ").split(" ") if word]
        if any(word != "chicken" for word in words):
            raise ModelError("syntax")
        counts.append(len(words))
    return counts


def _numeric(value):
    if value is Marker.SELF:
        raise ModelError("halt")
    if value is None or value is Marker.NAN:
        return Marker.NAN
    if isinstance(value, (int, bool)):
        return int(value)
    text = value.strip()
    if not text:
        return 0
    return int(text) if re.fullmatch(r"[+-]?[0-9]+", text) else Marker.NAN


def _string(value):
    if value is Marker.SELF:
        raise ModelError("halt")
    if value is Marker.NAN:
        return "NaN"
    if value is None:
        return "undefined"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _index(value):
    if type(value) is int:
        return value if value >= 0 else None
    if isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value):
        return int(value)
    return None


def _equal(left, right):
    if left is Marker.SELF or right is Marker.SELF:
        if left is right:
            return True
        raise ModelError("halt")
    if left is None or right is None:
        return left is right
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    a, b = _numeric(left), _numeric(right)
    return a is not Marker.NAN and b is not Marker.NAN and a == b


def _truth(value):
    return value is not None and value is not Marker.NAN and bool(value)


def _typed(value):
    if isinstance(value, Marker):
        return "marker", value.value
    return type(value).__name__, value


def _source(counts):
    source = "\n".join(" ".join(["chicken"] * count) for count in counts)
    return source + ("\n" if counts and counts[-1] == 0 else "")


class Reference:
    def __init__(self, source, stdin):
        counts = _parse(source)
        self.cells = [Marker.SELF, stdin, *counts, 0]
        self.pc, self.stopped, self.output = 2, False, ""
        self.consumed = len(stdin)

    def pop(self):
        return self.cells.pop() if self.cells else None

    def get(self, address):
        return (
            self.cells[address]
            if address is not None and address < len(self.cells)
            else None
        )

    def snapshot(self):
        return self.pc, tuple(map(_typed, self.cells)), self.stopped

    def exit(self):
        text = _string(self.pop())
        self.stopped = True

        def entity(match):
            codepoint = int(match[1])
            if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                raise ModelError("halt")
            return chr(codepoint)

        rendered = re.sub(r"&#([0-9]+);", entity, text)
        self.output += rendered

    def arithmetic(self, opcode):
        top = self.pop()
        below = top if opcode == 9 else self.pop()
        if opcode == 9:
            result = "&#" + _string(top) + ";"
        elif opcode == 5:
            result = _equal(below, top)
        elif opcode == 2 and (isinstance(below, str) or isinstance(top, str)):
            result = _string(below) + _string(top)
        else:
            left, right = _numeric(below), _numeric(top)
            if left is Marker.NAN or right is Marker.NAN:
                result = Marker.NAN
            elif opcode == 2:
                result = left + right
            elif opcode == 3:
                result = left - right
            else:
                result = left * right
        self.cells.append(result)

    def load(self):
        address = _index(self.pop())
        source = self.get(_index(self.get(self.pc)))
        self.pc += 1
        if source is None:
            raise ModelError("halt")
        if source is Marker.SELF:
            result = self.get(address)
        elif isinstance(source, str) and address is not None and address < len(source):
            result = source[address]
        else:
            result = None
        self.cells.append(result)

    def store(self):
        address, value = self.pop(), self.pop()
        index = _index(address)
        if index is None:
            raise ModelError("halt")
        if index >= 1 << 24:
            raise ModelError("limit")
        if index >= 512:
            raise AssertionError("bounded model allocation envelope exceeded")
        if index >= len(self.cells):
            self.cells.extend([None] * (index + 1 - len(self.cells)))
        self.cells[index] = value

    def jump(self):
        offset, condition = self.pop(), self.pop()
        if _truth(condition):
            if not isinstance(offset, int):
                raise ModelError("halt")
            self.pc += offset

    def step(self):
        if self.stopped:
            return
        if not 0 <= self.pc < len(self.cells):
            self.exit()
            return
        instruction = self.cells[self.pc]
        self.pc += 1
        if type(instruction) is int and 0 <= instruction <= 9:
            operations = {
                0: self.exit,
                1: lambda: self.cells.append("chicken"),
                6: self.load,
                7: self.store,
                8: self.jump,
            }
            if instruction in operations:
                operations[instruction]()
            else:
                self.arithmetic(instruction)
        else:
            value = _numeric(instruction)
            self.cells.append(Marker.NAN if value is Marker.NAN else value - 10)


def model(source, stdin, cap):
    try:
        machine = Reference(source, stdin)
    except ModelError as error:
        return error.args[0], [(None, False, "", 0, 0)]

    def row():
        return (
            machine.snapshot(),
            machine.stopped,
            machine.output,
            machine.consumed,
            machine.consumed,
        )

    trace, error = [row()], None
    for _ in range(cap):
        if machine.stopped:
            break
        try:
            machine.step()
        except ModelError as failure:
            error = failure.args[0]
        except ValueError:
            error = "syntax"
        trace.append(row())
        if error:
            break
    if error is None and machine.stopped:
        trace.extend([row()] * 3)
    return error, trace
