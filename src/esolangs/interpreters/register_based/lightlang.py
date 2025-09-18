"""
Lightlang interpreter implementation.

Lightlang is an esoteric programming language that uses only 1 bit as memory.
Each character is an instruction, and invalid instructions are ignored.
"""

import secrets
import sys
import time


def run(code: str) -> None:
    """
    Execute Lightlang code using a single bit of memory.

    Lightlang is a minimal esoteric language with the following commands:
    ^ - Toggle the bit
    ! - Print the bit state (0 or 1)
    ? - Input: set bit to 0 if input given, 1 if empty
    @ - Set bit to random state
    & - Skip next instruction if bit is 1
    # - Halt the program
    < - Jump to start of program
    / - Reverse instruction pointer direction
    _ - Sleep for 1 second

    Args:
        code: The Lightlang program to execute
    """
    bit = ind = 0
    vel = new = 1

    while ind < len(code):
        sym = code[ind]
        if sym == "^":
            bit ^= 1
        elif sym == "!":
            print(bit, end="")
            new = 0
        elif sym == "?":
            val = input("\nInput: "[new:])
            bit = (not val) + 0
            new = 1
        elif sym == "@":
            bit = secrets.randbelow(2)
        elif sym == "&" and bit:
            ind += vel
        elif sym == "#":
            return
        elif sym == "<":
            ind = -vel
        elif sym == "/":
            vel *= -1
        elif sym == "_":
            time.sleep(1)

        ind += vel


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
