"""Mutable single-register execution using independent integer transitions."""

from tests.interpreters.polynomial_transition import transition


class Reference:
    def __init__(self, program, text=""):
        self.program = program
        self.text = text
        self.offset = 0
        self.reads = 0
        self.register = 0
        self.cursor = 0
        self.output = ""

    @property
    def halted(self):
        return self.cursor >= len(self.program)

    def step(self):
        if self.halted:
            return
        instruction = self.program[self.cursor]
        byte = None
        if (
            len(instruction) == 2
            and instruction[0] == 0
            and instruction[1] != 1
            and self.offset < len(self.text)
        ):
            byte = ord(self.text[self.offset])
            self.offset += 1
            self.reads += 1
        state, output = transition((self.register, self.cursor), self.program, byte)
        self.register, self.cursor = state
        if output is not None:
            self.output += output
