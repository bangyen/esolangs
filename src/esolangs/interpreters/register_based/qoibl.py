"""
Qoibl (Qwerty oriented impractical bicharacter language) interpreter.

Qoibl is an esoteric programming language with 8 instructions and a 256-variable list.
It uses only the characters 'e', 'r', 't', 'w', 'q', 'y' for programming constructs.
"""

import re
import sys
from dataclasses import dataclass


@dataclass
class State:
    line: bool = False


def run(code):
    """Execute Qoibl program code."""
    var: dict = {}
    state = State()

    def parse(state, expr):
        """Parse and execute a single Qoibl expression."""
        if (op := expr[0]) == "tt":
            print(chr(parse(state, expr[1:-1])), end="")
            state.line = True
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
            elif num == "ey":
                return x - y
            elif num == "ye":
                return x * y
            elif num == "yy":
                return x // y
        elif op == "qe":
            return var.get(parse(state, expr[1:-1]), 0)
        elif op == "et":
            n = input("\n" * state.line + "Input: ")
            state.line = False
            return ord(n[0])
        elif re.fullmatch("[ey]+", op):
            op = op.replace("e", "0").replace("y", "1")
            return int(op, 2)

    for exp in code:
        parse(state, exp.split())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
