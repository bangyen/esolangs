"""Independent LaserFuck scheduler with coordinate tape and beam-local skips."""

from dataclasses import dataclass, field


@dataclass
class Beam:
    row: int
    col: int
    direction: str
    skip: bool = False


@dataclass
class Reference:
    grid: tuple[str, ...]
    beams: list[Beam]
    cells: dict[int, int] = field(default_factory=lambda: {0: 0})
    touched: set[int] = field(default_factory=set)
    pointer: int = 0
    active: int = 0
    input_text: str = "A" * 100
    reads: int = 0
    position: tuple[int, int, str] = (0, 0, "U")

    def step(self, byte=0, split=0):
        beam = self.beams[self.active]
        delta = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}[beam.direction]
        beam.row += delta[0]
        beam.col += delta[1]
        self.position = (beam.row, beam.col, beam.direction)
        inside = 0 <= beam.row < len(self.grid) and 0 <= beam.col < len(self.grid[0])
        if beam.skip:
            beam.skip = False
        else:
            op = self.grid[beam.row][beam.col] if inside else "x"
            value = self.cells[self.pointer]
            if op == "x":
                self.beams.pop(self.active)
                self.active = (
                    self.active % len(self.beams) if self.beams else self.active
                )
                return
            if op in "><":
                self.pointer += 1 if op == ">" else -1
                self.cells.setdefault(self.pointer, 0)
            elif op in "+-,":
                if op == ",":
                    if self.reads == len(self.input_text):
                        raise EOFError
                    byte = ord(self.input_text[self.reads])
                    self.reads += 1
                number = byte if op == "," else value + (1 if op == "+" else -1)
                self.cells[self.pointer] = (number + 2**31) % 2**32 - 2**31
                self.touched.add(self.pointer)
            elif op == "#":
                beam.skip = True
            elif op == "*":
                direction = (
                    ("L", "R")[split] if beam.direction in "UD" else ("U", "D")[split]
                )
                self.beams.append(Beam(beam.row, beam.col, direction))
            elif op in "^v{}":
                beam.direction = {"^": "U", "v": "D", "{": "L", "}": "R"}[op]
            elif op == "/":
                beam.direction = {"U": "R", "R": "U", "D": "L", "L": "D"}[
                    beam.direction
                ]
            elif op == "\\":
                beam.direction = {"U": "L", "L": "U", "D": "R", "R": "D"}[
                    beam.direction
                ]
            elif op == "_" or (op == "(" and value != 0):
                beam.direction = {"U": "D", "D": "U", "L": "L", "R": "R"}[
                    beam.direction
                ]
            elif op == "|" or (op == ")" and value != 0):
                beam.direction = {"U": "U", "D": "D", "L": "R", "R": "L"}[
                    beam.direction
                ]
        self.active = (self.active + 1) % len(self.beams)
