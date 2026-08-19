"""Interpreter for 123.

A bit-tape language: ``1`` flips the current bit and moves the pointer left
(wrapping from -3 back to 0), ``2`` reads a character when the pointer is at
-3 or writes one when at -2 (otherwise it moves the pointer right), and
``3`` is a jump symbol: when the current bit is TRUE the pointer skips back
to the previous ``3`` (or the start), when FALSE it skips forward to the
next ``3`` (or the end).  Bits start FALSE, the program halts only when the
end is reached with the pointer below 0 (otherwise it loops from the start),
and unrecognized characters are NOPs.

The pointer is tracked as a bitmask: 1024 = -3 (the read position), 512 = -2
(the write position), 256 = -1, 128 = 0, then halving to 1 = position 7 and
0 = position 8.  Flipping XORs the mask into the data byte, so position 0
holds the *most* significant bit: the cross-check interpreters and the
repository's generator are MSB-first, which is the opposite of the wiki's
little-endian note.

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

# Pointer position encoded as a bitmask: the read/write positions sit above
# the data bits and the data bits halve from 128 (position 0, bit 7) to 1
# (position 7, bit 0); 0 is position 8, where the pointer is stuck.
_READ = 1024  # position -3
_WRITE = 512  # position -2
_START = 128  # position 0


class _Machine:
    """Per-run 123 state: data byte, pointer mask, and the code cursor.

    ``step()`` executes one command and ``halted`` says whether the program
    ended — the shape the VM wrapper and the state-cycle hang detector
    expect.  :meth:`snapshot` returns the cursor, mask, data byte, and
    input cursor, so a repeated snapshot proves a deterministic run loops
    forever (the state is bounded, so every 123 loop is a cycle).
    """

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and reset the tape; a command-less program halts."""
        self.code = code
        self.io = io
        self.n = len(code)
        self.data = 0
        self.mask = _START
        self.ip = 0
        self._done = not any(c in "123" for c in code)

    @property
    def halted(self) -> bool:
        """Whether the run has ended (or has no commands to run)."""
        return self._done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ip, self.mask, self.data, self.io.position())

    def step(self) -> None:
        """Execute one command (or the loop-or-halt check), advancing."""
        if self.halted:
            return
        if self.ip >= self.n:
            if self.mask > _START:
                self._done = True
            else:
                self.ip = 0
            return
        char = self.code[self.ip]
        if char == "1":
            self.data ^= self.mask
            self.mask = _START if self.mask >= _READ else self.mask << 1
        elif char == "2":
            if self.mask == _READ:
                self.data = self.io.input_char()
                self.mask = _START
            elif self.mask == _WRITE:
                self.io.print_char(chr(self.data & 0xFF))
                self.mask = _START
            else:
                self.mask >>= 1
        elif char == "3":
            if self.mask <= _START:
                if self.data & self.mask:
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
