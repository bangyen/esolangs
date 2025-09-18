"""
Minsky Swap interpreter implementation.

Turing-complete language based on Minsky machines.
Uses two unbounded registers with a register pointer that can be swapped.
"""

import re
import sys


def run(text: str) -> None:
    """Execute a Minsky Swap program."""
    ind = ptr = val = 0
    reg = [0, 0]
    nums = []
    code = ""

    if re.search(r"(inc|swap|decnz)\(", text):
        pattern = r"(inc|swap|decnz)\((\d*)\);"
        cmp = re.compile(pattern)
        for m in cmp.findall(text):
            if (s := m[0][0]) == "i":
                code += "+"
            elif s == "s":
                code += "*"
            else:
                code += "~"
                skip = int(m[1]) if m[1] else 1
                nums.append(skip)
        # Also process any remaining compact notation
        compact_part = re.sub(r"(inc|swap|decnz)\([^)]*\);", "", text)
        compact_part = re.sub("[^+~*]", "", compact_part)
        code += compact_part
    else:
        code = (s := text.split("\n"))[0]
        code = re.sub("[^+~*]", "", code)
        if len(s) > 1:
            nums = re.findall(r"\d+", s[1])
            nums = [int(k) for k in nums]

    while ind < len(code):
        if (op := code[ind]) == "+":
            reg[ptr] += 1
        elif op == "~":
            if reg[ptr]:
                reg[ptr] -= 1
            else:
                if val < len(nums):
                    ind = nums[val] - 1
            val += 1
        elif op == "*":
            ptr ^= 1

        ind += 1
    print(*reg)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
