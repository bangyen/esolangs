"""Streetcode 78016: right-hand driving on junction-free two-lane boxes."""

from dataclasses import dataclass, field

from esolangs.exceptions import HaltError


@dataclass
class Rectangle:
    rows: tuple[str, ...]
    stdin: str = ""
    row: int = 2
    col: int = 1
    direction: int = 1
    cp: int = 0
    cells: dict[int, int] = field(default_factory=dict)
    offset: int = 0
    reads: int = 0
    output: str = ""
    halted: bool = False

    def position(self, direction):
        dr, dc = ((-1, 0), (0, 1), (1, 0), (0, -1))[direction]
        return self.row + dr, self.col + dc

    def open(self, point):
        r, c = point
        return (
            0 <= r < len(self.rows)
            and 0 <= c < len(self.rows[r])
            and self.rows[r][c] not in "+-|"
        )

    def state(self):
        return (
            self.row,
            self.col,
            self.direction,
            self.cp,
            tuple(sorted(self.cells.items())),
            self.offset,
            self.halted,
        )

    def step(self):
        if self.halted:
            return
        op = self.rows[self.row][self.col]
        value = self.cells.get(self.cp, 0)
        if op == ";":
            self.halted = True
            return
        if op == "^":
            self.cells[self.cp] = value + 1
        elif op == "~":
            self.cells[self.cp] = value - 1
        elif op == "=":
            self.cp += 1
        elif op == "_":
            self.cp = max(0, self.cp - 1)
        elif op == "I":
            if self.offset == len(self.stdin):
                raise EOFError
            self.cells[self.cp] = ord(self.stdin[self.offset])
            self.offset += 1
            self.reads += 1
        elif op == "O":
            if not 0 <= value <= 0x10FFFF:
                raise HaltError
            self.output += chr(value)
        elif op == "U":
            lane = self.position((self.direction - 1) % 4)
            if not self.open(lane):
                raise HaltError
            self.row, self.col = lane
            self.direction = (self.direction + 2) % 4
            return
        for direction in (
            (self.direction + 1) % 4,
            self.direction,
            (self.direction - 1) % 4,
            (self.direction + 2) % 4,
        ):
            point = self.position(direction)
            if self.open(point):
                self.row, self.col = point
                self.direction = direction
                return
        self.halted = True
