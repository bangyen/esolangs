"""Interpreter for Bitdeque.

PUSH/INJECT append a register value to the deque, POP/EJECT pop it (0 when
empty), INVERT flips the register, and GOTO jumps to a numbered command when
the register is nonzero.  The deque contents are printed at the end.

The wiki says GOTO goes to the Nth operation but does not pin down the
indexing; this interpreter treats N as 0-based (GOTO 2 lands on the third
command, skipping the GOTO itself), matching its reference test.
"""

import re
import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run a Bitdeque program and print the deque at the end."""
    lst = ("INJECT", "PUSH", "EJECT", "POP", "INVERT", r"GOTO *(\d+)")

    join = f"({'|'.join(lst)})"
    tokens = re.findall(join, code)
    ind = reg = 0
    deq: list[int] = []

    while ind < len(tokens):
        sym = tokens[ind][0]
        if sym == "PUSH":
            deq.append(reg)
        elif sym == "INJECT":
            deq.insert(0, reg)
        elif sym == "POP":
            reg = deq.pop() if deq else 0
        elif sym == "EJECT":
            reg = deq.pop(0) if deq else 0
        elif sym == "INVERT":
            reg ^= 1
        elif reg:
            num = int(sym[4:])
            ind = num - 1

        ind += 1
    io.print_line(" ".join(map(str, deq)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
