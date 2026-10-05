"""Unsquare author rules with an explicit Unicode and output profile."""


class InvalidOperationError(Exception):
    pass


class Reference:
    def __init__(self, source, text=""):
        self.source = source
        self.text = text
        self.offset = 0
        self.reads = 0
        self.past_end = 0
        self.output = ""
        self.pc = 0
        self.accumulator = 0
        self.values = []
        self.loops = []
        self.ends = {}
        opens = []
        for address, command in enumerate(source):
            if command == ">":
                opens.append(address)
            elif command == "<" and opens:
                self.ends[opens.pop()] = address

    @property
    def halted(self):
        return self.pc >= len(self.source)

    def snapshot(self):
        return (
            self.pc,
            self.accumulator,
            tuple(self.values),
            tuple(start - 1 for start in self.loops),
            self.offset,
            self.source,
            self.reads,
        )

    def step(self):
        if self.halted:
            return
        op = self.source[self.pc]
        following = self.pc + 1
        if op in ("A", "o") and not self.values:
            raise InvalidOperationError("empty stack")
        if op == "S" and len(self.values) < 2:
            raise InvalidOperationError("swap needs two elements")
        if op == "<" and not self.loops:
            raise InvalidOperationError("unmatched <")
        if op == "O":
            self.values.append(0)
        elif op == "I":
            self.values.append(1)
        elif op == "A":
            self.accumulator = self.values.pop()
        elif op == "S":
            self.values[-2:] = self.values[-2:][::-1]
        elif op == "+":
            self.accumulator += 2
        elif op == "-":
            self.accumulator -= 2
        elif op == "x":
            self.accumulator *= 2
        elif op == "P":
            self.values.append(self.accumulator)
        elif op == "o":
            scalar = self.values[-1] % (1 << 32)
            self.output += (
                chr(scalar)
                if scalar <= 0x10FFFF and not 0xD800 <= scalar < 0xE000
                else str(self.values[-1])
            )
        elif op == "i":
            if self.offset == len(self.text):
                self.past_end += 1
                raise EOFError
            self.values.append(ord(self.text[self.offset]))
            self.offset += 1
            self.reads += 1
        elif op == ">":
            if self.pc not in self.ends:
                self.pc = len(self.source)
                raise InvalidOperationError("unmatched >")
            if self.accumulator in (0, 1):
                following = self.ends[self.pc] + 1
            else:
                self.loops.append(self.pc)
        elif op == "<":
            opening = self.loops.pop()
            if self.accumulator not in (0, 1):
                following = opening
        self.pc = following
