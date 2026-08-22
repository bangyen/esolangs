"""Interpreter for 123.

A bit-tape language: the pointer starts at location 0 over an unbounded
array of bits (all initially FALSE, indexed 0, 1, 2, ... to the right, with
no upper bound).  ``1`` flips the current bit and moves the pointer left,
wrapping from -4 back to 0.  ``2`` reads a character into locations 0-7 when
the pointer is at -3, writes locations 0-7 as a character when at -2 (both
then reset the pointer to 0), and otherwise just moves the pointer right.
``3`` is a jump symbol: below location 0 it is a NOP; otherwise, when the
current bit is TRUE the pointer skips back to the previous ``3`` (or the
start), and when FALSE it skips forward to the next ``3`` (or the end).  The
program halts only when the end is reached with the pointer below 0
(otherwise it loops from the start), and unrecognized characters are NOPs.

Locations 0-7 are read as an 8-bit character MSB-first (location 0 is bit
7): the cross-check interpreters and the repository's generator agree on
this order, which is the opposite of the wiki's little-endian note.

Decisions for gaps in the wiki spec (documented):
- ``,`` reads a whole input line and takes its first byte, raising
  :class:`EOFError` when input runs out (like the other tape interpreters);
- a ``3`` with no next ``3`` skips to the end, where the normal loop-or-halt
  check applies;
- a program with no ``1``/``2``/``3`` commands halts with no output (the
  spec would loop forever on the empty program).
"""

import sys

from esolangs.interpreters.io import IO

_READ = -3
_WRITE = -2
_START = 0


class _Machine:
    """Per-run 123 state: an unbounded bit tape, pointer, and code cursor.

    ``step()`` executes one command and ``halted`` says whether the program
    ended — the shape the VM wrapper and the state-cycle hang detector
    expect.  :meth:`snapshot` returns the cursor, pointer, tape contents,
    and input cursor, so a repeated snapshot proves a deterministic run
    loops forever; programs that only ever touch a bounded prefix of the
    tape are bounded-state and always resolve as a cycle, while a program
    that marches the pointer right forever grows the tape without repeating
    a state (the state-cycle detector's documented "unbounded growth" case,
    left to the caller's timeout backstop).
    """

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and reset the tape; a command-less program halts."""
        self.code = code
        self.io = io
        self.n = len(code)
        self.bits: dict[int, bool] = {}
        self.pos = _START
        self.ip = 0
        self._done = not any(c in "123" for c in code)

    @property
    def halted(self) -> bool:
        """Whether the run has ended (or has no commands to run)."""
        return self._done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        bits = tuple(sorted(k for k, v in self.bits.items() if v))
        return (self.ip, self.pos, bits, self.io.position())

    def byte(self) -> int:
        """Read locations 0-7 as an MSB-first byte (location 0 is bit 7)."""
        return sum((1 << (7 - i)) for i in range(8) if self.bits.get(i, False))

    def _set_byte(self, value: int) -> None:
        """Write ``value`` into locations 0-7, MSB-first."""
        for i in range(8):
            self.bits[i] = bool(value & (1 << (7 - i)))

    def step(self) -> None:
        """Execute one command (or the loop-or-halt check), advancing."""
        if self.halted:
            return
        if self.ip >= self.n:
            if self.pos < 0:
                self._done = True
            else:
                self.ip = 0
            return
        char = self.code[self.ip]
        if char == "1":
            self.bits[self.pos] = not self.bits.get(self.pos, False)
            self.pos -= 1
            if self.pos == -4:
                self.pos = _START
        elif char == "2":
            if self.pos == _READ:
                self._set_byte(self.io.input_char())
                self.pos = _START
            elif self.pos == _WRITE:
                self.io.print_char(chr(self.byte()))
                self.pos = _START
            else:
                self.pos += 1
        elif char == "3":
            if self.pos >= 0:
                if self.bits.get(self.pos, False):
                    j = self.ip - 1
                    while j >= 0 and self.code[j] != "3":
                        j -= 1
                    self.ip = j + 1
                else:
                    j = self.ip + 1
                    while j < self.n and self.code[j] != "3":
                        j += 1
                    self.ip = j + 1
                return
        self.ip += 1


def run(code: str, io: IO) -> None:
    """Run a 123 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
