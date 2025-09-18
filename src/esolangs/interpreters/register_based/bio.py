"""
BIO (Binary IO) interpreter implementation.

BIO is an esoteric programming language that uses three memory blocks (x, y, z)
and only two letters (I, O) and two numbers (0, 1) to create commands.
Each command is ended by a semicolon.

Command format: [0|1][O|I][x|y|z];

Commands:
- 0O[xyz]: Increment the specified block
- 1O[xyz]: Decrement the specified block
- 0I[xyz]: While the block is not 0, execute the following block until }
- 1I[xyz]: Output the block as a character
- }: End of while loop block

The language is case-insensitive and inspired by ABCDXYZ.
"""

import re
import sys
from typing import List


def run(code: str) -> None:
    """
    Execute BIO code and produce output.

    This function parses and executes BIO (Binary IO) esoteric programming language
    code. BIO uses three memory registers (x, y, z) and a minimal command set
    consisting of increment/decrement operations, conditional loops, and output.

    Args:
        code: The BIO source code as a string. Commands should be separated by
              semicolons and follow the pattern [0|1][O|I][x|y|z].

    Raises:
        No explicit exceptions are raised, but malformed code may cause unexpected
        behavior or infinite loops.

    Example:
        >>> run("0ox;1ix;")  # Increment x, then output x
        A
    """
    # Parse BIO commands using regex
    lang = "([01][oOiI][xXyYzZ]|})"
    commands = re.findall(lang, code)
    commands = [k.lower() for k in commands]

    reg: List[int] = [0] * 3
    stk: List[int] = []
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
        else:  # 0I[xyz]: While loop
            if reg[r]:
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
