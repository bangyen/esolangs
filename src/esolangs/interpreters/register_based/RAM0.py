"""
RAM0 interpreter implementation.

Computational model with two registers (z, n) and unbounded RAM.
Seven commands: Z, A, N, C, L, S, and goto.
"""

import re
import sys


def output(z, n, ram):
    """Print the current state of all registers and RAM memory."""
    res = f"z: {z}\n" f"n: {n}\n" "ram: {"

    for x, y in ram.items():
        res += f"\n    {x}: {y},"
    if ram:
        res = res[:-1] + "\n"
    print(res + "}")


def change(z, n, ram, op):
    """Execute a single RAM0 command and return the updated registers."""
    if op == "Z":
        z = 0
    elif op == "A":
        z += 1
    elif op == "N":
        n = z
    elif op == "L":
        z = ram.get(z, 0)
    elif op == "S":
        ram[n] = z
    return z, n, not z


def run(code):
    """Execute a RAM0 program by parsing commands and running them sequentially."""
    expr = r"([ZANCLS]|[1-9]\d*)"
    code = re.findall(expr, code)
    z = n = 0
    ram: dict = {}
    ind = 0

    while ind < len(code):
        c = code[ind]
        z, n, skip = change(z, n, ram, c)
        if c == "C" and skip:
            ind += 1
        elif c.isdigit():
            ind = int(c) - 2
        ind += 1

    output(z, n, ram)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
