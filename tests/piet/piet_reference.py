"""Piet raster execution with an independent character/token cursor."""

from contextlib import suppress

from tests.piet.piet_raster import BLACK, advance, colour


class Reference:
    def __init__(self, rows, text=""):
        self.rows = rows
        self.text = text
        self.position = 0
        self.reads = 0
        self.output = ""
        self.past_end = 0
        self.state = ((0, 0), 0, -1, (), colour(rows[0][0]) == BLACK)

    def read(self, numeric):
        if numeric:
            while self.position < len(self.text) and self.text[self.position].isspace():
                self.position += 1
            begin = self.position
            while self.position < len(self.text) and (
                not self.text[self.position].isspace()
            ):
                self.position += 1
            if begin == self.position:
                self.past_end += 1
                raise EOFError
            self.reads += 1
            return int(self.text[begin : self.position])
        if self.position == len(self.text):
            self.past_end += 1
            raise EOFError
        char = self.text[self.position]
        self.position += 1
        self.reads += 1
        return ord(char)

    def step(self):
        state, effect = advance(self.state, self.rows)
        point, heading, chooser, values, halted = state
        if effect:
            operation, value = effect
            if operation in ("number", "char"):
                with suppress(EOFError, ValueError):
                    values = (*values, self.read(operation == "number"))
            elif operation == "out_number":
                self.output += str(value)
            else:
                with suppress(ValueError):
                    self.output += chr(value)
        self.state = (point, heading, chooser, values, halted)
