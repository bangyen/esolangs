"""Qoibl (Qwerty oriented impractical bicharacter language) interpreter.

Qoibl is an esoteric programming language with 8 instructions and a 256-variable list.
It uses only the characters 'e', 'r', 't', 'w', 'q', 'y' for programming constructs.

The wiki specifies a 256-entry variable list; this interpreter uses an
unbounded dictionary and does not enforce the cap.  Division by zero is an
invalid operation and halts the program with
:class:`~esolangs.exceptions.HaltError`; a comparison or arithmetic expression
with an unrecognized operator is a malformed program and is rejected with
:class:`ValueError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import re
import sys
from dataclasses import dataclass, field

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


@dataclass
class State:
    """Per-run state for a Qoibl interpreter: variables and the code cursor."""

    var: dict[int, int] = field(default_factory=dict)
    io: IO = field(default_factory=IO)
    code: list[str] = field(default_factory=list, init=False)
    ind: int = 0

    @property
    def halted(self) -> bool:
        """Whether the expression pointer has run off the program."""
        return self.ind >= len(self.code)

    def _parse(self, expr: str | list[str]) -> int:
        """Parse and execute a single Qoibl expression."""
        if not expr:
            raise ValueError("malformed expression")
        if (op := expr[0]) == "tt":
            self.io.print_char(chr(self._parse(expr[1:-1])))
        elif op == "we":
            ind = expr.index("we", 1)
            self.var[self._parse(expr[1:ind])] = self._parse(expr[ind + 1 : -1])
        elif op == "rr":
            ind = expr.index("rr", 1)
            while self._parse(expr[1:ind]):
                self._parse(expr[ind + 1 : -1])
        elif "yr" in expr:
            beg = expr.index("yr")
            if beg + 1 >= len(expr):
                raise ValueError("malformed comparison")
            num = expr[beg + 1]
            x = self._parse(expr[:beg])
            y = self._parse(expr[beg + 3 :])

            if num == "ee":
                return x == y
            if num == "ey":
                return x > y
            if num == "ye":
                return x < y
            if num == "yy":
                return x != y
            raise ValueError("unrecognized comparison operator")
        elif "ry" in expr:
            beg = expr.index("ry")
            if beg + 1 >= len(expr):
                raise ValueError("malformed arithmetic")
            num = expr[beg + 1]
            x = self._parse(expr[:beg])
            y = self._parse(expr[beg + 3 :])

            if num == "ee":
                return x + y
            if num == "ey":
                return x - y
            if num == "ye":
                return x * y
            if num == "yy":
                if y == 0:
                    raise HaltError
                return x // y
            raise ValueError("unrecognized arithmetic operator")
        elif op == "qe":
            return self.var.get(self._parse(expr[1:-1]), 0)
        elif op == "et":
            return self.io.input_char()
        elif re.fullmatch("[ey]+", op):
            op = op.replace("e", "0").replace("y", "1")
            return int(op, 2)
        return 0

    def step(self) -> None:
        """Execute one expression, advancing the cursor."""
        tokens = self.code[self.ind].split()
        self.ind += 1
        if tokens:
            self._parse(tokens)


def run(code: list[str], io: IO) -> None:
    """Execute Qoibl program code."""
    state = State(io=io)
    state.code = code

    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
