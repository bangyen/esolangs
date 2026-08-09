"""
Minsky Swap interpreter implementation.

Turing-complete language based on Minsky machines.
Uses two unbounded registers with a register pointer that can be swapped.
"""

import re
import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Execute a Minsky Swap program."""
    ind = ptr = val = 0
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

    while ind < len(prog):
        if (op := prog[ind]) == "+":
            reg[ptr] += 1
        elif op == "~":
            if reg[ptr]:
                reg[ptr] -= 1
            elif val < len(nums):
                ind = nums[val] - 1
            val += 1
        elif op == "*":
            ptr ^= 1

        ind += 1
    io.print_line(" ".join(map(str, reg)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
