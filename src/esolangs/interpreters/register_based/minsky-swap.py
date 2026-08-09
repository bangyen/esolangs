"""Minsky Swap interpreter implementation.

Turing-complete language based on Minsky machines.
Uses two unbounded registers with a register pointer that can be swapped.

Jump targets are 1-based and fixed by the tilde's position in the code line:
the Nth ``~`` jumps to the Nth number on the jump line, so ``decnz(N)`` (and
its compact ``~``) restarts execution at line N.  The wiki describes targets
as 1-based ("line N"), which this interpreter follows.
"""

import re
import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Execute a Minsky Swap program."""
    ind = ptr = 0
    reg = [0, 0]
    nums = []
    prog = ""

    if re.search(r"(inc|swap|decnz)\(", code):
        pattern = r"(inc|swap|decnz)\((\d*)\);"
        cmp = re.compile(pattern)
        for m in cmp.findall(code):
            if (s := m[0][0]) == "i":
                prog += "+"
            elif s == "s":
                prog += "*"
            else:
                prog += "~"
                skip = int(m[1]) if m[1] else 1
                nums.append(skip)
        # Also process any remaining compact notation
        compact_part = re.sub(r"(inc|swap|decnz)\([^)]*\);", "", code)
        compact_part = re.sub("[^+~*]", "", compact_part)
        prog += compact_part
    else:
        prog = (s := code.split("\n"))[0]
        prog = re.sub("[^+~*]", "", prog)
        if len(s) > 1:
            nums = re.findall(r"\d+", s[1])
            nums = [int(k) for k in nums]

    # Each tilde's jump target is fixed by its position in the code line:
    # the Nth tilde jumps to the Nth number on the jump line, and targets
    # are 1-based (so a jump to N runs the (N-1)th command).
    targets: dict[int, int] = {}
    for i, ch in enumerate(prog):
        if ch == "~":
            targets[i] = nums[len(targets)] if len(targets) < len(nums) else 0

    while ind < len(prog):
        if (op := prog[ind]) == "+":
            reg[ptr] += 1
        elif op == "~":
            if reg[ptr]:
                reg[ptr] -= 1
            elif target := targets[ind]:
                ind = target - 2
        elif op == "*":
            ptr ^= 1

        ind += 1
    io.print_line(" ".join(map(str, reg)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
