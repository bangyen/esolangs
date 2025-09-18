"""
Qoibl (Qwerty oriented impractical bicharacter language) interpreter.

Qoibl is an esoteric programming language with 8 instructions and a 256-variable list.
It uses only the characters 'e', 'r', 't', 'w', 'q', 'y' for programming constructs.
"""

import re
import sys


def run(code):
    """
    Execute Qoibl program code.

    Processes a list of Qoibl expressions, maintaining a variable store and
    executing instructions like printing, assignment, conditionals, and loops.

    Args:
        code: List of strings, each containing a Qoibl expression to execute
    """
    line = False
    var = {}

    def parse(expr):
        """
        Parse and execute a single Qoibl expression.

        Handles all Qoibl instructions: tt (print), we (assign), qe (access),
        et (input), yr (conditionals), ry (math), rr (loops), and binary numbers.

        Args:
            expr: List of tokens representing a Qoibl expression

        Returns:
            Result value for expressions that return values, None for statements
        """
        nonlocal line

        if (op := expr[0]) == "tt":
            print(chr(parse(expr[1:-1])), end="")
            line = True
        elif op == "we":
            ind = expr.index("we", 1)
            var[parse(expr[1:ind])] = parse(expr[ind + 1 : -1])
        elif op == "rr":
            ind = expr.index("rr", 1)
            while parse(expr[1:ind]):
                parse(expr[ind + 1 : -1])
        elif "yr" in expr:
            beg = expr.index("yr")
            num = expr[beg + 1]
            x = parse(expr[:beg])
            y = parse(expr[beg + 3 :])

            if num == "ee":
                return x == y
            elif num == "ey":
                return x > y
            elif num == "ye":
                return x < y
            elif num == "yy":
                return x != y
        elif "ry" in expr:
            beg = expr.index("ry")
            num = expr[beg + 1]
            x = parse(expr[:beg])
            y = parse(expr[beg + 3 :])

            if num == "ee":
                return x + y
            elif num == "ey":
                return x - y
            elif num == "ye":
                return x * y
            elif num == "yy":
                return x // y
        elif op == "qe":
            return var.get(parse(expr[1:-1]), 0)
        elif op == "et":
            n = input("\n" * line + "Input: ")
            line = False
            return ord(n[0])
        elif re.fullmatch("[ey]+", op):
            op = op.replace("e", "0").replace("y", "1")
            return int(op, 2)

    for exp in code:
        parse(exp.split())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data)
