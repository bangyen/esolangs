"""
BIO (Binary IO) interpreter implementation.

Register-based esoteric language with three memory blocks (x, y, z).
Uses commands in format [0|1][O|I][x|y|z] for increment/decrement, loops, and output.
"""

import re
import sys


def run(code: str) -> None:
    """Execute BIO code and produce output."""
    # Parse BIO commands using regex
    lang = "([01][oOiI][xXyYzZ]|})"
    commands = re.findall(lang, code)
    commands = [k.lower() for k in commands]

    reg: list[int] = [0] * 3
    stk: list[int] = []
    ind = 0

    while ind < len(commands):
        r = "xyz".find(commands[ind][-1])
        c = commands[ind][:2]

        if c == "0o":
            reg[r] += 1
        elif c == "1o":
            reg[r] -= 1
        elif c == "1i":
            # Handle negative values by converting to unsigned 8-bit
            char_code = reg[r] % 256
            print(chr(char_code), end="")
        elif c == "}":
            ind = stk.pop() - 1
        elif reg[r]:
            stk.append(ind)
        else:
            # Skip the loop block
            mat = 1
            while mat:
                ind += 1
                if ind == len(commands):
                    break
                else:
                    c = commands[ind][:2]
                    if c == "0i":
                        mat += 1
                    elif c == "}":
                        mat -= 1
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
