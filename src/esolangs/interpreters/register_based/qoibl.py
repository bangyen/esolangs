"""Qoibl (Qwerty oriented impractical bicharacter language) interpreter.

Qoibl is an esoteric programming language with 8 instructions and a 256-variable list.
It uses only the characters 'e', 'r', 't', 'w', 'q', 'y' for programming constructs.
"""

import re
import sys
from dataclasses import dataclass

from esolangs.interpreters.io import IO


@dataclass
class State:
    """Per-run state for a Qoibl interpreter."""


def run(code: list[str], io: IO) -> None:
    """Execute Qoibl program code."""
    var: dict[int, int] = {}
    state = State()

    def parse(state: State, expr: str | list[str]) -> int:
        """Parse and execute a single Qoibl expression."""
        if (op := expr[0]) == "tt":
            io.print_char(chr(parse(state, expr[1:-1])))
        elif op == "we":
            ind = expr.index("we", 1)
            var[parse(state, expr[1:ind])] = parse(state, expr[ind + 1 : -1])
        elif op == "rr":
            ind = expr.index("rr", 1)
            while parse(state, expr[1:ind]):
                parse(state, expr[ind + 1 : -1])
        elif "yr" in expr:
            beg = expr.index("yr")
            num = expr[beg + 1]
            x = parse(state, expr[:beg])
            y = parse(state, expr[beg + 3 :])

            if num in {"ee", "ey", "ye", "yy"}:
                return {"ee": x == y, "ey": x > y, "ye": x < y, "yy": x != y}[num]
        elif "ry" in expr:
            beg = expr.index("ry")
            num = expr[beg + 1]
            x = parse(state, expr[:beg])
            y = parse(state, expr[beg + 3 :])

            if num == "ee":
                return x + y
            if num == "ey":
                return x - y
            if num == "ye":
                return x * y
            if num == "yy":
                return x // y
        elif op == "qe":
            return var.get(parse(state, expr[1:-1]), 0)
        elif op == "et":
            return io.input_char()
        elif re.fullmatch("[ey]+", op):
            op = op.replace("e", "0").replace("y", "1")
            return int(op, 2)
        return 0

    for exp in code:
        parse(state, exp.split())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
