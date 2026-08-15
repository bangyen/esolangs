r"""Interpreter for LaserFuck.

A laser (starting at ``o`` with a random initial heading) travels a grid.
``>``/``<``/``+``/``-``/``,`` work on a brainfuck-style tape, ``\`` and ``/``
reflect the laser, ``_``/``|`` and ``(``/``)`` reflect it when the current
cell is nonzero (or always for the unconditional forms), ``^v{}`` set the
heading directly, ``#`` skips the next command, ``x`` deletes the laser, and
``*`` duplicates it in a random perpendicular direction.  Execution ends when
no lasers remain; the tape is then printed, with the first grid cell ``\xff``
selecting byte mode (no separators) over the default decimal mode, and
negative cells excluded from the output.

The initial heading is chosen uniformly at random, matching the reference; a
run may therefore produce one of several outputs, so tests set a fixed
heading through :func:`run`.
"""

import random
import sys

from esolangs.interpreters.io import IO


def run(code: list[str], io: IO, heading: int | None = None) -> None:
    """Run a LaserFuck program, printing the tape when it halts.

    ``heading`` forces the laser's initial direction (0=up, 1=down, 2=left,
    3=right); when None it is drawn uniformly at random, matching the
    reference implementation.
    """
    text = [list(ln) for ln in code]
    size = max(len(ln) for ln in text) if text else 0
    text = [ln + [" "] * (size - len(ln)) for ln in text]
    rows = len(text)

    lsrs: list[list[int]] = []
    for x, line in enumerate(text):
        for y, c in enumerate(line):
            if c == "o":
                if lsrs:
                    return  # a second start marker halts immediately
                # The random heading is part of LaserFuck's spec, not a secret.
                d = (
                    heading if heading is not None else random.randrange(4)  # nosec B311
                )
                lsrs.append([x, y, d])

    ptr = 0
    tape: list[list[int]] = [[0, 0]]  # value, touched
    jmp = False
    ind = 0

    while lsrs:
        x, y, d = lsrs[ind]

        # move one step in the current direction
        if (x == 0 and d == 0) or (y == 0 and d == 2):
            x = rows  # step off the grid (top/left edges)
        elif d == 0:
            x -= 1
        elif d == 1:
            x += 1
        elif d == 2:
            y -= 1
        elif d == 3:
            y += 1

        if jmp:
            jmp = False
            lsrs[ind] = [x, y, d]
            ind = (ind + 1) % len(lsrs)
            continue

        op = text[x][y] if 0 <= x < rows and 0 <= y < size else "x"

        if op == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append([0, 0])
        elif op == "<":
            if ptr > 0:
                ptr -= 1
            else:
                tape.insert(0, [0, 0])
        elif op == ",":
            line_val = io.input_str()
            # an empty (or blank) input line reads a zero, per the reference
            tape[ptr] = [ord(line_val[0]) if line_val else 0, 1]
        elif op == "x":
            lsrs.pop(ind)
            if lsrs:
                ind %= len(lsrs)
            continue
        elif op == "*":
            lsrs.append([x, y, 2 * (1 - d // 2) + random.randrange(2)])  # nosec B311
        elif op in "_(":
            if d < 2 and (tape[ptr][0] != 0 or op == "_"):
                d = 1 - d
        elif op in "|)":
            if d > 1 and (tape[ptr][0] != 0 or op == "|"):
                d = 5 - d
        elif op == "/":
            d = 3 - d
        elif op in "^v{}":
            d = "^v{}".find(op)
        elif op == "\\":
            d = (d + 2) % 4
        elif op == "+":
            tape[ptr][0] += 1
            tape[ptr][1] = 1
        elif op == "-":
            tape[ptr][0] -= 1
            tape[ptr][1] = 1
        elif op == "#":
            jmp = True

        lsrs[ind] = [x, y, d]
        ind = (ind + 1) % len(lsrs)

    # -- output ---------------------------------------------------------
    out = bool(text) and bool(text[0]) and text[0][0] == "\u00ff"
    first = True
    for val, touched in tape:
        if touched and val >= 0:
            if out:
                io.print_char(chr(val))
            elif first:
                io.print_num(val)
                first = False
            else:
                io.print_line()
                io.print_num(val)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
