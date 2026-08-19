"""Interpreter for bit~.

An 8-cell bit pool with a pointer: ``~`` flips the current bit, ``>`` moves
the pointer right (extending the pool when the 8-cell window would run past
the end), ``<`` moves it left (a no-op at the first cell), ``)`` reads a
byte of input into the pool as 8 bits (MSB first, starting at the current
cell, extending the pool to hold the full window), ``(`` prints the 8-bit
window at the pointer as a byte, and ``{``/``}`` are a loop bracket pair:
``{`` jumps forward to the matching ``}`` when the current bit is zero and
``}`` jumps back to the matching ``{`` when it is nonzero.  Any other
character is ignored.

The pool is a single array that only ever grows: ``>`` appends a cell
whenever ``cell + 8`` would exceed the pool's length, and ``)`` pads the
pool to fit its window.  A ``(`` at a pointer with fewer than 8 cells left
prints just the available bits.

Semantics match the Rust cross-check (``extra/rust/bit_tilde.rs``):
- ``)`` raises :class:`EOFError` when input runs out, where the cross-check
  exits with status 3 (the wiki leaves EOF undefined);
- a ``{``/``}`` whose match is missing raises :class:`ValueError` when it
  would have jumped (the Rust cross-check agrees; the former Ruby port
  looped forever);
- an empty input line yields no character (the cross-check would read a
  newline), so ``)`` on an empty line raises :class:`IndexError` through
  :meth:`esolangs.interpreters.io.IO.input_char`.

The interpreter runs on a :class:`_Machine` (the bit pool, the pointer, and
the code cursor), so it is step-capable: ``step()`` executes one character
and ``halted`` is true once the cursor reaches the end of the code.  A
bracket loop that returns to an exact state is a cycle the state-cycle hang
detector proves; the ``run()`` backstop stays for the unbounded-growth class
(a loop whose body keeps extending the pool).
"""

import sys

from esolangs.interpreters.io import IO


def _match(code: str, ind: int, step: int) -> int:
    """Return the index of the bracket matching ``code[ind]``.

    ``step`` is 1 to find the forward ``}`` for a ``{`` and -1 to find the
    backward ``{`` for a ``}``; a bracket with no match is a malformed
    program (``ValueError``) — the cross-check loops forever instead.
    """
    depth = step
    while depth:
        ind += step
        if not 0 <= ind < len(code):
            raise ValueError("unmatched bit~ bracket")
        if code[ind] == "{":
            depth += 1
        elif code[ind] == "}":
            depth -= 1
    return ind


class _Machine:
    """Per-run bit~ state: the bit pool, the pointer, and the cursor.

    ``step()`` executes one character; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with an eight-cell pool at the origin."""
        self.io = io
        self.code = code
        self.tape: list[int] = [0] * 8
        self.cell = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (tuple(self.tape), self.cell, self.ind, self.io.position())

    def step(self) -> None:
        """Execute one character, advancing the cursor."""
        if self.halted:
            return
        c = self.code[self.ind]
        if c == "~":
            self.tape[self.cell] ^= 1
        elif c == ">":
            if self.cell + 8 > len(self.tape):
                self.tape.append(0)
            self.cell += 1
        elif c == "<":
            if self.cell:
                self.cell -= 1
        elif c == ")":
            byte = self.io.input_char()
            bits = [int(b) for b in f"{byte:08b}"]
            if self.cell + 8 > len(self.tape):
                self.tape.extend([0] * (self.cell + 8 - len(self.tape)))
            self.tape[self.cell : self.cell + 8] = bits
        elif c == "(":
            val = self.tape[self.cell : self.cell + 8]
            self.io.print_char(chr(int("".join(map(str, val)), 2)))
        elif c == "{":
            if not self.tape[self.cell]:
                self.ind = _match(self.code, self.ind, 1)
        elif c == "}" and self.tape[self.cell]:
            self.ind = _match(self.code, self.ind, -1)
        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a bit~ program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
