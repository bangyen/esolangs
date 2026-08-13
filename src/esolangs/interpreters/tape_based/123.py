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
holds the *most* significant bit: the reference interpreters and the
repository's generator are MSB-first, which is the opposite of the wiki's
little-endian note.

Decisions for gaps in the wiki spec (documented):
- ``,`` reads a whole input line and takes its first byte, raising
  :class:`EOFError` when input runs out (like the other tape interpreters);
- a ``3`` with no next ``3`` skips to the end, where the normal loop-or-halt
  check applies; the x86/RISC-V references instead run off the end of the
  program into their I/O buffer, which is undefined behavior;
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


def run(code: str, io: IO) -> None:
    """Run a 123 program."""
    if not any(c in "123" for c in code):
        return

    data = 0
    mask = _START
    ip = 0
    n = len(code)

    while True:
        if ip >= n:
            if mask > _START:
                return
            ip = 0
            continue

        char = code[ip]
        if char == "1":
            data ^= mask
            mask = _START if mask >= _READ else mask << 1
        elif char == "2":
            if mask == _READ:
                data = io.input_char()
                mask = _START
            elif mask == _WRITE:
                io.print_char(chr(data & 0xFF))
                mask = _START
            else:
                mask >>= 1
        elif char == "3":
            if mask <= _START:
                if data & mask:
                    j = ip - 1
                    while j >= 0 and code[j] != "3":
                        j -= 1
                    ip = j + 1
                else:
                    j = ip + 1
                    while j < n and code[j] != "3":
                        j += 1
                    ip = j + 1
                continue
        ip += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
