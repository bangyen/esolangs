"""Mutable Painfuck execution with independent suffix translation."""

from tests.interpreters.painfuck_translation import translate


class InvalidOperationError(Exception):
    pass


class Reference:
    def __init__(self, source, text="", coins=()):
        self.program = translate(source)
        self.tape = [0]
        self.loops = []
        self.pointer = 0
        self.cursor = 0
        self.repeat = 1
        self.text = text
        self.offset = 0
        self.reads = 0
        self.output = ""
        self.coins = list(coins)
        self.draws = 0

    @property
    def halted(self):
        return self.cursor >= len(self.program)

    def input(self, numeric):
        if numeric:
            while self.offset < len(self.text) and self.text[self.offset].isspace():
                self.offset += 1
            start = self.offset
            while self.offset < len(self.text) and (
                not self.text[self.offset].isspace()
            ):
                self.offset += 1
            if start == self.offset:
                raise EOFError
            value = self.text[start : self.offset]
            self.reads += 1
            try:
                return int(value)
            except ValueError:
                raise InvalidOperationError("invalid numeric input") from None
        if self.offset == len(self.text):
            raise EOFError
        value = ord(self.text[self.offset])
        self.offset += 1
        self.reads += 1
        return value

    def step(self):
        if self.halted:
            return
        command = self.program[self.cursor]
        self.cursor += 1
        remaining = self.repeat
        while remaining:
            remaining -= 1
            self.repeat = remaining
            pointer = self.pointer
            cell = self.tape[pointer]
            if command == "p":
                self.tape[pointer] = cell + 2
            elif command == "s":
                self.tape[pointer] = cell - 1
            elif command == "r":
                self.pointer += 2
                self.tape.extend([0] * max(0, self.pointer + 1 - len(self.tape)))
            elif command == "l":
                self.pointer = max(0, pointer - 1)
            elif command == "k":
                self.tape[pointer] = cell * cell
            elif command == "z":
                self.tape[pointer] = 0
            elif command == "h":
                self.tape[pointer] = cell // 2
            elif command == "w":
                self.tape[pointer] = (
                    self.tape[pointer + 1] if pointer + 1 < len(self.tape) else 0
                )
            elif command == "q":
                if pointer:
                    self.tape[pointer] = self.tape[pointer - 1]
            elif command == "d":
                self.pointer = 0
            elif command == "e":
                self.cursor = len(self.program)
                self.repeat = 0
                return
            elif command in ("i", "j"):
                self.tape[pointer] = self.input(command == "i")
                if command == "j":
                    command = "\n"
            elif command == "o":
                self.output += str(cell)
            elif command == "u":
                self.output += chr(cell % 256)
            elif command == "a":
                remaining = 0
                if cell:
                    self.loops.append(self.cursor - 1)
                else:
                    balance = 1
                    while self.cursor < len(self.program) and balance:
                        token = self.program[self.cursor]
                        self.cursor += 1
                        balance += int(token == "a") - int(token == "b")
            elif command == "b":
                remaining = 0
                if not self.loops:
                    self.repeat = 0
                    raise InvalidOperationError("unmatched closing loop")
                self.cursor = self.loops.pop()
            elif command == "v":
                if cell == 0 and self.cursor < len(self.program):
                    command = self.program[self.cursor]
                    self.cursor += 1
                    remaining = 1
            elif command == "y":
                flips = remaining + 1
                chosen = self.coins[self.draws : self.draws + flips]
                if len(chosen) != flips:
                    raise RuntimeError("insufficient deterministic coins")
                self.draws += flips
                remaining = flips - sum(chosen)
                if self.cursor < len(self.program):
                    command = self.program[self.cursor]
                    self.cursor += 1
            elif command == "c":
                run = 1
                while (
                    self.cursor < len(self.program) and self.program[self.cursor] == "c"
                ):
                    run += 1
                    self.cursor += 1
                base = 7**run
                trailing = 0
                while (
                    self.cursor < len(self.program) and self.program[self.cursor] == "t"
                ):
                    trailing += 1
                    self.cursor += 1
                remaining = base ** ((3 ** (trailing + 1) - 1) // 2)
                command = (
                    self.program[self.cursor]
                    if self.cursor < len(self.program)
                    else "\x00"
                )
                self.cursor += 1
            elif command == "t":
                count = 1
                previous = self.cursor - 2
                while previous >= 0 and self.program[previous] == "t":
                    count += 1
                    previous -= 1
                remaining = 3**count
                command = self.program[previous] if previous >= 0 else "\x00"
        self.repeat = 1
