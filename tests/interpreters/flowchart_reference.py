"""Independent graph/complex-coordinate Flowchart model, wiki175580 profile."""

import copy
import re
from collections import deque
from dataclasses import dataclass, field
from unicodedata import name

SPELLINGS = (
    "( )",
    "(( ))",
    "[ ]",
    "{ ]",
    "[ }",
    "{ }",
    "< >",
    "/ /",
    "\\ \\",
    "\\[ ]/",
    "/[ ]\\",
    "\\{ }/",
    "/{ }\\",
    "< ]",
    "[ >",
)
TOKEN = re.compile(
    "|".join(re.escape(s) for s in sorted(SPELLINGS, key=len, reverse=True))
)
DIRECTIONS = (1, -1j, -1, 1j)
RAILS = "─│┌┐└┘┬┴├┤┼"


def arms(glyph):
    words = set(name(glyph).split())
    result = set()
    for word, direction in [("RIGHT", 1), ("LEFT", -1), ("UP", 1j), ("DOWN", -1j)]:
        if word in words:
            result.add(direction)
    if "VERTICAL" in words:
        result.update([1j, -1j])
    if "HORIZONTAL" in words:
        result.update([-1, 1])
    return result


def coordinate(point):
    return (int(-point.imag), int(point.real))


@dataclass
class Pointer:
    point: complex
    heading: complex
    value: int | None = None
    tape: int = 0
    done: bool = False
    previous: complex | None = None
    history: dict = field(default_factory=dict)
    coordinate_history: dict = field(default_factory=dict)
    snapshot_history: tuple = ()

    def remember(self, point, heading):
        key, value = coordinate(point), coordinate(heading)
        if point in self.history:
            self.snapshot_history = tuple(
                (cell, value if cell == key else old)
                for cell, old in self.snapshot_history
            )
        else:
            self.snapshot_history = tuple(
                sorted((*self.snapshot_history, (key, value)))
            )
        self.history = {**self.history, point: heading}
        self.coordinate_history = {**self.coordinate_history, key: value}

    def snapshot(self):
        history = self.snapshot_history
        assert len(history) == len(self.history)
        return (
            *coordinate(self.point),
            coordinate(self.heading),
            self.value,
            self.tape,
            self.done,
            None if self.previous is None else coordinate(self.previous),
            history,
        )


class Reference:
    def __init__(self, lines, stdin=""):
        rows = [line.rstrip("\n") for line in lines]
        self.width = max(map(len, rows), default=0)
        self.grid = {
            x - y * 1j: char
            for y, row in enumerate(rows)
            for x, char in enumerate(row.ljust(self.width))
        }
        self.owner = {}
        self.nodes = {}
        for y, row in enumerate(rows):
            for token in TOKEN.finditer(row):
                anchor = token.start() - y * 1j
                kind = token.group()
                self.nodes[anchor] = kind
                for x in range(token.start(), token.end()):
                    self.owner[x - y * 1j] = anchor
        for point, glyph in self.grid.items():
            if point in self.owner:
                for direction in DIRECTIONS:
                    other = self.owner.get(point + direction)
                    if other is not None and other != self.owner[point]:
                        raise ValueError("touching nodes")
            elif glyph != " ":
                if glyph not in RAILS:
                    raise ValueError("unknown glyph")
                for direction in arms(glyph) & {1j, -1j}:
                    anchor = self.owner.get(point + direction)
                    if (
                        anchor is not None
                        and point.real != anchor.real + len(self.nodes[anchor]) // 2
                    ):
                        raise ValueError("vertical alignment")
        starts = [a for a, kind in self.nodes.items() if kind == "( )"]
        if not starts:
            raise ValueError("start")
        first = min(starts, key=coordinate)
        exits = sorted(self.ports(first, None), key=lambda item: coordinate(item[0]))
        if not exits:
            raise ValueError("exit")
        self.pointers = [
            Pointer(point, direction, previous=first) for point, direction in exits
        ]
        self.tapes = {}
        self.stdin = stdin
        self.offset = self.reads = self.past_end = self.bit_reads = 0
        self.output = ""
        self._tape_snapshot = None

    def accepts(self, point, direction):
        return point in self.owner or (
            self.grid.get(point, " ") in RAILS and -direction in arms(self.grid[point])
        )

    def ports(self, anchor, previous):
        result = []
        for offset in range(len(self.nodes[anchor])):
            cell = anchor + offset
            for direction in DIRECTIONS:
                neighbor = cell + direction
                if neighbor == previous or self.owner.get(neighbor) == anchor:
                    continue
                if self.accepts(neighbor, direction):
                    result.append((neighbor, direction))
        return result

    @property
    def done(self):
        return all(p.done for p in self.pointers)

    @property
    def tape_snapshot(self):
        if self._tape_snapshot is None:
            self._tape_snapshot = tuple(
                sorted((k, tuple(v)) for k, v in self.tapes.items() if v)
            )
        return self._tape_snapshot

    def snapshot(self):
        return (
            tuple(p.snapshot() for p in self.pointers),
            self.tape_snapshot,
            self.offset,
            self.bit_reads,
        )

    def read(self):
        while True:
            if self.offset == len(self.stdin):
                self.past_end += 1
                return None
            char = self.stdin[self.offset]
            self.offset += 1
            self.reads += 1
            if char.isspace():
                continue
            if char not in "01":
                raise ValueError("bit")
            self.bit_reads += 1
            return ord(char) - 48

    def leave(self, pointer, prefer=None):
        anchor = self.owner[pointer.point]
        exits = self.ports(anchor, pointer.previous)
        if not exits:
            raise ValueError("exit")
        rank = [pointer.heading, pointer.heading * -1j, pointer.heading * 1j]
        exits.sort(key=lambda item: rank.index(item[1]))
        choices = (
            [item for item in exits if item[1] == prefer] if prefer is not None else []
        )
        if not choices and prefer is None:
            old = pointer.history.get(anchor)
            if old != -pointer.heading:
                choices = [item for item in exits if item[1] == old]
            if not choices:
                choices = [item for item in exits if item[1] == pointer.heading]
        point, heading = (choices or exits)[0]
        self.go(pointer, point, heading, anchor)

    def go(self, pointer, point, heading, anchor):
        pointer.remember(anchor, heading)
        pointer.previous = pointer.point
        pointer.point = point
        pointer.heading = heading

    def one(self, pointer):
        anchor = self.owner.get(pointer.point)
        if anchor is None:
            allowed = arms(self.grid[pointer.point]) - {-pointer.heading}
            remembered = pointer.history.get(pointer.point)
            priority = [
                remembered,
                pointer.heading,
                pointer.heading * -1j,
                pointer.heading * 1j,
            ]
            heading = next(d for d in priority if d in allowed)
            pointer.remember(pointer.point, heading)
            if not self.accepts(pointer.point + heading, heading):
                pointer.done = True
                return
            pointer.previous = pointer.point
            pointer.point += heading
            pointer.heading = heading
            return
        kind = self.nodes[anchor]
        if kind == "(( ))":
            pointer.done = True
            return
        if kind == "( )":
            exits = sorted(
                self.ports(anchor, pointer.previous),
                key=lambda item: coordinate(item[0]),
            )
            if not exits:
                raise ValueError("exit")
            for point, heading in exits[1:]:
                child = copy.copy(pointer)
                child.point = point
                child.heading = heading
                child.previous = pointer.point
                self.pointers.append(child)
            self.go(pointer, *exits[0], anchor)
            return
        if kind == "< >":
            prefer = (
                pointer.heading
                if pointer.value is None
                else pointer.heading * (1j if pointer.value else -1j)
            )
            if not any(d == prefer for _, d in self.ports(anchor, pointer.previous)):
                prefer = pointer.heading
            self.leave(pointer, prefer)
            return
        if kind == "[ ]":
            pointer.value = 1 if pointer.value is None else 1 - pointer.value
        elif kind == "{ ]":
            pointer.value = 0
        elif kind == "[ }":
            pointer.value = 1
        elif kind == "{ }":
            pointer.value = None
        elif kind == "/ /":
            pointer.value = self.read()
        elif kind == "\\ \\":
            if pointer.value is not None:
                self.output += str(pointer.value)
        elif kind in ("\\[ ]/", "/[ ]\\"):
            if pointer.value is not None:
                cells = self.tapes.setdefault(pointer.tape, deque())
                (cells.append if kind == "\\[ ]/" else cells.appendleft)(pointer.value)
                self._tape_snapshot = None
        elif kind in ("\\{ }/", "/{ }\\"):
            cells = self.tapes.setdefault(pointer.tape, deque())
            pointer.value = (
                (cells.pop() if kind == "\\{ }/" else cells.popleft())
                if cells
                else None
            )
            self._tape_snapshot = None
        elif kind == "< ]":
            pointer.tape -= 1
        elif kind == "[ >":
            pointer.tape += 1
        self.leave(pointer)

    def step(self):
        for pointer in self.pointers[:]:
            if not pointer.done:
                self.one(pointer)
