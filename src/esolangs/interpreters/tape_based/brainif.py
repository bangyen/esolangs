"""Interpreter for BrainIf.

Line-based: each ``if <value> <command>`` runs only when the cell equals
<value>.  Commands increment, move right/left, goto a line, read a byte of
input, or output the current cell.
"""

import sys

from esolangs.interpreters.io import IO


def run(code: list[str], io: IO) -> None:
    """Run a BrainIf program."""
    cells: list[int] = [0]
    ind = ptr = 0

    while ind < len(code):
        line = code[ind].strip()
        arr = line.split()

        if line and cells[ptr] == int(arr[1]):
            if "inc" in line:
                cells[ptr] += 1
            elif "right" in line:
                ptr += 1
                if ptr == len(cells):
                    cells.append(0)
            elif "left" in line:
                ptr = max(0, ptr - 1)
            elif "goto" in line:
                ind = int(arr[3]) - 2
            elif "input" in line:
                s = ""

                while not s:
                    s = io.input_str()

                cells[ptr] = ord(s[0])
            elif "output" in line:
                io.print_char(chr(cells[ptr]))

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
