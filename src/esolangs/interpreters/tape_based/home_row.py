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
  unbounded registers), so ``k`` prints the low byte and ``s`` on a 0 cell
  yields -1 (the wiki's talk page asks whether decrementing 0 should be a
  no-op, but the language's author never ruled; the main page says ``s``
  subtracts 1, so the cell goes negative);
- reaching the end of the source without ``;`` halts (the pointer has no
  direction to keep moving);
- ``l`` pairs alternate by their order in the program (the first and second
  ``l`` form a loop, the third and fourth form another, and so on), matching
  the RISC-V compiler's ``loop // 2`` numbering rather than BF-style
  nesting; an unbalanced trailing ``l`` is a malformed program
  (:class:`ValueError`).

The interpreter runs on a :class:`_Machine` (the fixed 25-cell grid, the
pointer, and the code cursor), so it is step-capable: ``step()`` executes
one command and ``halted`` is true once the cursor reaches the end of the
program or hits ``;``.  A loop whose body never changes the tested cell
(e.g. ``all``: increment once, then loop on a cell the body never touches)
is a genuine state cycle a repeated :meth:`_Machine.snapshot` proves; a
loop that keeps incrementing the tested cell is unbounded growth and needs
the wall-clock backstop instead.
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


class _Machine:
    """Per-run Home Row state: the grid, pointer, and code cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the program or hits ``;``.  The state-cycle hang
    detector and the VM expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Match ``code``'s loop pairs and start the grid at all zeros."""
        self.io = io
        self.code = code
        self.match, self.open_l = _matches(code)
        self.grid = [0] * 25
        self.ptr = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has run off the program or hit ``;``."""
        return self.ind >= len(self.code) or self.code[self.ind] == ";"

    # The VM's language-shaped view: 5x5 torus grid + pointer; ip the cursor, memory
    # the 25 cells.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.grid)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, self.ptr, tuple(self.grid))

    def step(self) -> None:
        """Execute one command, advancing the cursor."""
        if self.halted:
            return
        c = self.code[self.ind]
        if c == "a":
            self.grid[self.ptr] += 1
        elif c == "s":
            self.grid[self.ptr] -= 1
        elif c == "d":
            self.ptr = (self.ptr + 5) % 25
        elif c == "f":
            self.ptr += 1
            if self.ptr % 5 == 0:
                self.ptr -= 5
        elif c == "j":
            if self.grid[self.ptr] == 0:
                self.ind += 1
        elif c == "k":
            self.io.print_char(chr(self.grid[self.ptr] & 0xFF))
            self.grid[self.ptr] = 0
        elif c == "l":
            partner = self.match[self.ind]
            if self.ind in self.open_l:
                if self.grid[self.ptr] == 0:
                    self.ind = partner
            elif self.grid[self.ptr] != 0:
                self.ind = partner
        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a Home Row program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
