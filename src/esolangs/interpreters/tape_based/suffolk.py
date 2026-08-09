"""Interpreter for Suffolk.

> moves right, < sums the current cell into the accumulator and rewinds the
pointer, ! zeroes a cell computed from the accumulator, , reads a byte of
input, and . prints the accumulator minus one.  Execution loops until the
step limit is reached.
"""

import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO, limit: int = 10) -> None:
    """Run a Suffolk program, looping at most ``limit`` times."""
    tape: list[int] = [0]
    num = ind = 0
    ptr = acc = 0

    while num < limit:
        if (sym := code[ind]) == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif sym == "<":
            acc += tape[ptr]
            ptr = 0
        elif sym == "!":
            val = tape[ptr] + 1 - acc
            tape[ptr] = max(0, val)
            ptr = acc = 0
        elif sym == ",":
            inp = io.input_str()
            acc = acc + ord(inp[0]) if inp else 0
        elif sym == "." and acc:
            output_val: str = chr(acc - 1)
            io.print_char(output_val)

        ind += 1
        if ind == len(code):
            ind = 0
            num += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, IO(), limit=int(sys.argv[2]))
            else:
                run(data, IO())
