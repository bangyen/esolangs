"""
RAM0 interpreter implementation.

RAM0 is a computational model created by Schönhage in 1990, featuring:
- Two registers: z (accumulator) and n (address register)
- Unbounded RAM for storing nonnegative integers
- Seven commands: Z, A, N, C, L, S, and goto
- Turing complete with minimal instruction set

This implementation provides a Python interpreter for RAM0 programs.
"""

import re
import sys


def init():
    """
    Initialize RAM0 machine state and return the command execution function.

    Creates a closure with the machine state (registers z, n and RAM memory)
    and returns a function that can execute RAM0 commands.

    Returns:
        function: Command execution function that takes an operation and returns
                 True if z register is zero after execution, False otherwise.
    """
    z = n = 0
    ram: dict = {}

    def output():
        """Print the current state of all registers and RAM memory."""
        res = f"z: {z}\n" f"n: {n}\n" "ram: {"

        for x, y in ram.items():
            res += f"\n    {x}: {y},"
        if ram:
            res = res[:-1] + "\n"
        print(res + "}")

    def change(op):
        """
        Execute a single RAM0 command and return whether z register is zero.

        Args:
            op: Command to execute ('Z', 'A', 'N', 'C', 'L', 'S', or goto number)
                Special case: 0 triggers output and program termination.

        Returns:
            bool: True if z register is zero after command execution, False otherwise.
        """
        nonlocal z, n
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
        elif op == 0:
            output()
        return not z

    return change


def run(code):
    """
    Execute a RAM0 program by parsing commands and running them sequentially.

    Parses the input code using regex to extract valid RAM0 commands:
    - Single letter commands: Z, A, N, C, L, S
    - Goto commands: decimal numbers (1-based indexing)
    - All other characters are ignored as comments

    Args:
        code (str): RAM0 program code containing commands and optional comments.
    """
    expr = r"([ZANCLS]|[1-9]\d*)"
    code = re.findall(expr, code)
    func = init()
    ind = 0

    while ind < len(code):
        skip = func(c := code[ind])
        if c == "C" and skip:
            ind += 1
        elif c.isdigit():
            ind = int(c) - 2
        ind += 1

    func(0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
