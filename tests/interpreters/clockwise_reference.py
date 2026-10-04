"""Clockwise revision 153954: complex coordinates and signed arithmetic."""

from collections import deque


class Reference:
    def __init__(self, lines, stdin=""):
        if not lines:
            raise ValueError("empty program")
        width = max(map(len, lines))
        self.cells = {
            complex(x, y): (row[x] if x < len(row) else " ")
            for y, row in enumerate(lines)
            for x in range(width)
        }
        self.width = width
        self.height = len(lines)
        self.position = 0j
        self.direction = 1 + 0j
        self.accumulator = 0
        self.pending = []
        self.queue = deque()
        self.output = ""
        self.halted = False
        self.requires_input = any("." in row for row in lines)
        self.load_input(stdin)

    def load_input(self, stdin):
        self.queue = deque()
        self.offset = len(stdin) if self.requires_input else 0
        self.reads = int(self.requires_input)
        if self.requires_input:
            for char in stdin:
                value = ord(char)
                length = max(7, value.bit_length())
                self.queue.extend(
                    (value // 2**place) % 2 for place in range(length - 1, -1, -1)
                )

    def step(self):
        if self.halted:
            return
        if self.position not in self.cells:
            raise ValueError("ring is not closed")
        char = self.cells[self.position]
        if char == "." and not self.queue:
            raise EOFError("input queue is empty")
        if (
            char == "R"
            or (char == "?" and self.accumulator != 0)
            or (char == "!" and self.accumulator == 0)
        ):
            self.direction *= 1j
        elif char == "+":
            self.accumulator += 1
        elif char == "-":
            self.accumulator -= 1
        elif char == "S":
            self.accumulator = 0
        elif char == ".":
            bit = self.queue.popleft()
            self.queue.append(bit)
            self.accumulator = 2 * (self.accumulator // 2) + bit
        elif char == ";":
            self.pending.append(self.accumulator % 2)
            if len(self.pending) == 7:
                self.output += chr(
                    sum(
                        bit * 2 ** (6 - index) for index, bit in enumerate(self.pending)
                    )
                )
                self.pending.clear()
        self.position += self.direction
        self.halted = self.position == 0

    def state(self):
        headings = (1 + 0j, 1j, -1 + 0j, -1j)
        return (
            int(self.position.imag),
            int(self.position.real),
            headings.index(self.direction),
            self.accumulator,
            tuple(map(str, self.pending)),
            tuple(map(str, self.queue)),
            self.halted,
        )
