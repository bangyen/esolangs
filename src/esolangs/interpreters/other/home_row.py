"""Interpreter for Home Row.

A BF-like language over a 5x5 wrapping grid of unbounded cells (the torus
the wiki describes).  ``a``/``s`` add/subtract 1 to the current cell,
``d``/``f`` move the pointer down/right (wrapping mod 5), ``j`` skips the
next instruction when the current cell is zero, ``k`` prints the current
cell as a byte and resets it to zero, a pair of ``l``s is a while-nonzero
loop ("runs if the current memory spot is nonzero and reruns after the
second l each time if the current memory spot is nonzero"), and ``;`` ends
the program.  The pointer starts at the top-left cell.

Documented decisions for gaps and divergences:
- cells are unbounded integers (the wiki's Minsky-machine construction needs
  unbounded registers), so ``k`` prints the low byte;
- reaching the end of the source without ``;`` halts (the pointer has no
  direction to keep moving);
- ``l`` pairs alternate by their order in the program (the first and second
  ``l`` form a loop, the third and fourth form another, and so on), matching
  the RISC-V compiler's ``loop // 2`` numbering rather than BF-style
  nesting; an unbalanced trailing ``l`` is a malformed program
  (:class:`ValueError`);
- the RISC-V compiler diverges from the wiki in two ways the interpreter
  follows the wiki over: it wraps the pointer mod 4 (``andi ..., 3``) rather
  than mod 5, and its ``l`` loop reruns while the cell is *zero* rather than
  nonzero.
"""

import sys

from esolangs.interpreters.io import IO


def _matches(code: str) -> tuple[dict[int, int], set[int]]:
    """Return ``{l: partner}`` and the set of loop-open indices."""
    stack: list[int] = []
    match: dict[int, int] = {}
    open_l: set[int] = set()
    for i, char in enumerate(code):
        if char != "l":
            continue
        if not stack:
            stack.append(i)
            open_l.add(i)
        else:
            j = stack.pop()
            match[i] = j
            match[j] = i
    if stack:
        raise ValueError(f"unmatched 'l' at position {stack[-1]}")
    return match, open_l


def run(code: str, io: IO) -> None:
    """Run a Home Row program."""
    match, open_l = _matches(code)
    grid = [0] * 25
    ptr = 0
    i = 0
    n = len(code)

    while i < n:
        c = code[i]
        if c == "a":
            grid[ptr] += 1
        elif c == "s":
            grid[ptr] -= 1
        elif c == "d":
            ptr = (ptr + 5) % 25
        elif c == "f":
            ptr += 1
            if ptr % 5 == 0:
                ptr -= 5
        elif c == "j":
            if grid[ptr] == 0:
                i += 1
        elif c == "k":
            io.print_char(chr(grid[ptr] & 0xFF))
            grid[ptr] = 0
        elif c == "l":
            partner = match[i]
            if i in open_l:
                if grid[ptr] == 0:
                    i = partner
            elif grid[ptr] != 0:
                i = partner
        elif c == ";":
            return
        i += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
