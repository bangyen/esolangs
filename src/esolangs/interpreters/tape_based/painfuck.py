"""Interpreter for Painfuck.

The program file is *not* executed directly: its source text is first
translated through a fixed substitution, the ``trans`` table.  Each source
character that appears in one of the two cycles ``pevkjzwr`` and
``yuctsobqihald`` is replaced by the character ``k`` steps further along
that cycle, where ``k`` is the number of characters translated so far (so
the substitution is a position-dependent Caesar shift per cycle); characters
in no cycle are dropped.  This mirrors the Rust cross-check
(``extra/rust/painfuck.rs``) exactly and is
the inverse of the generator's own cycle rotation, so a generated program
round-trips.

The translated program runs over a tape of unbounded integers starting as a
single 0 cell.  ``p``/``s`` add 2/subtract 1 from the current cell,
``r``/``l`` move the pointer two right/one left (``l`` clamps at cell 0,
``r`` grows the tape), ``i``/``j`` read a number/byte from input,
``o``/``u`` print the cell as a decimal number/byte, ``a``/``b`` open/close
a while-nonzero loop, ``k`` squares the cell, ``z`` zeroes it, ``h``
halves it (truncating toward zero), ``w``/``q`` copy from the right/left
neighbor, ``c`` repeats the next command ``7``^run-length times, ``y``
skips the next command, ``v`` skips the next command when the cell is
nonzero, ``d`` resets the pointer to cell 0, ``t`` repeats the previous
command ``3``^run-length times, and ``e`` halts.  A ``c``/``t`` run also
re-fetches the command it repeats: ``c`` consumes the whole ``c`` run and
repeats the following command, ``t`` consumes the whole ``t`` run and
repeats the preceding command.  Both interact with the repetition count in
the same way as the reference.

Documented divergences from the C++ cross-check:

- ``y`` is nondeterministic in the reference (a random skip) and the wiki
  specifies it that way, so it skips the next command with probability 1/2
  here too; the generator and the differential corpus never use it.
- Reads at exhausted input raise :class:`EOFError` (the repo-wide
  convention), where the reference exits with status 3.
- ``i`` parses the whole input line as an integer with ``int()``, so each
  line must be a single integer (the reference tokenizes with ``>>``).
- A ``t`` run that reaches the start of the program repeats a NUL in place
  of the command it walks before the program, in both implementations (the
  reference used to read out of bounds there; it now bounds the walk).
- The reference's reads before/after the program are modeled as NUL, so an
  unmatched ``a`` on a zero cell skips to the end and the program halts.
- ``u`` prints ``chr(cell & 0xFF)``, matching the reference's ``(char)``
  cast for cell values outside the byte range.

Invalid runtime operations halt with :class:`~esolangs.exceptions.HaltError`.
"""

import random
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The two substitution cycles, in the order the reference scans them.
_CYCLES = ("pevkjzwr", "yuctsobqihald")

# "Past the end" (or before the start) of a program reads as NUL: the
# reference's program string is NUL-terminated, so an out-of-range read
# yields a command that matches no case.
_NUL = "\0"


def _translate(code: str) -> str:
    """Translate the source text into an executable program.

    Mirrors the reference ``trans`` table: each source character found in
    one of the two cycles is replaced by the character ``k`` steps further
    along that cycle, where ``k`` counts the characters translated so far.
    Characters in no cycle are dropped.
    """
    prog: list[str] = []
    k = 0
    for char in code:
        for cycle in _CYCLES:
            p = cycle.find(char)
            if p != -1:
                prog.append(cycle[(p + k) % len(cycle)])
                k += 1
                break
    return "".join(prog)


def _trunc2(n: int) -> int:
    """Half of ``n``, truncating toward zero (C++ ``/= 2`` semantics)."""
    return n // 2 if n >= 0 else -((-n) // 2)


def run(code: str, io: IO) -> None:
    """Run a Painfuck program."""
    prog = _translate(code)
    n = len(prog)

    tape: list[int] = [0]
    loop: list[int] = []
    ptr = ind = 0
    rep = 1

    while ind < n:
        c = prog[ind]
        ind += 1

        while rep > 0:
            rep -= 1

            if c == "p":
                tape[ptr] += 2
            elif c == "s":
                tape[ptr] -= 1
            elif c == "r":
                ptr += 2
                while ptr >= len(tape):
                    tape.append(0)
            elif c == "l":
                if ptr:
                    ptr -= 1
            elif c == "i":
                tape[ptr] = int(io.input_str("Input: "))
            elif c == "j":
                tape[ptr] = io.input_char()
                # The reference's discard-to-end-of-line loop leaves the
                # main command variable holding '\n', so a ``c``/``t``-repeated
                # ``j`` only reads once and then no-ops.
                c = "\n"
            elif c == "o":
                io.print_num(tape[ptr])
            elif c == "u":
                io.print_char(chr(tape[ptr] & 0xFF))
            elif c == "a":
                if tape[ptr] != 0:
                    loop.append(ind - 1)
                else:
                    val = 1
                    while val != 0 and ind < n:
                        ch = prog[ind]
                        ind += 1
                        if ch == "a":
                            val += 1
                        elif ch == "b":
                            val -= 1
            elif c == "b":
                if not loop:
                    raise HaltError("unmatched 'b': the loop stack is empty")
                ind = loop.pop()
            elif c == "k":
                tape[ptr] = tape[ptr] * tape[ptr]
            elif c == "z":
                tape[ptr] = 0
            elif c == "h":
                tape[ptr] = _trunc2(tape[ptr])
            elif c == "w":
                tape[ptr] = tape[ptr + 1] if ptr + 1 < len(tape) else 0
            elif c == "q":
                if ptr:
                    tape[ptr] = tape[ptr - 1]
            elif c == "c":
                rep = 1
                while c == "c":
                    c = prog[ind] if ind < n else _NUL
                    ind += 1
                    rep *= 7
            elif c == "y":
                # The wiki specifies a random skip; match the reference's
                # coin flip (the generator and differential avoid `y`).
                if random.randrange(2) and ind < n:  # nosec B311
                    c = prog[ind]
                    ind += 1
            elif c == "e":
                return
            elif c == "v" and tape[ptr] != 0 and ind < n:
                c = prog[ind]
                ind += 1
            elif c == "d":
                ptr = 0
            elif c == "t":
                val = ind
                rep = 1
                found = False
                while ind > 0:
                    ind -= 1
                    if prog[ind] != "t":
                        found = True
                        break
                    rep *= 3
                c = prog[ind] if found else _NUL
                ind = val

        rep += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
