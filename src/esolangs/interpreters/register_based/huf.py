"""Huf interpreter implementation.

Register-based language with two variables: num and mul.
Processes code segments enclosed in #...#@ patterns.
"""

import re
import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Execute a Huf program."""
    segments = re.findall("#[^#@]+@", code)
    code = "".join(segments)
    num = mul = 0

    for sym in code:
        if sym == "#":
            num = mul = 0
        elif sym == ">":
            val = chr(num)
            io.print_char(val)
            num = 0
        elif sym == "|":
            mul = 1
        elif sym == "!":
            num *= mul - 1
            mul = 0
        elif sym == "+":
            if mul:
                mul += 1
            else:
                num += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
