"""Interpreter for Painfuck.

The program file is *not* executed directly: its source text is first
translated through a fixed substitution, the ``trans`` table.  Each source
character that appears in one of the two cycles ``pevkjzwr`` and
``yuctsobqihald`` is replaced by the character ``k`` steps further along
that cycle, where ``k`` is the number of characters translated so far (so
the substitution is a position-dependent Caesar shift per cycle); characters
in no cycle are dropped.  This is
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
the same way as the cross-check.

Documented divergences from the cross-check:

- ``y`` is nondeterministic in the cross-check (a random skip) and the wiki
  specifies it that way, so it skips the next command with probability 1/2
  here too; the generator and the differential corpus never use it.
- Reads at exhausted input raise :class:`EOFError` (the repo-wide
  convention), where the cross-check exits with status 3.
- ``i`` parses the whole input line as an integer with ``int()``; a line
  that is not a single integer raises :class:`HaltError` (the cross-check
  exits with status 3 on the same input).
- A ``t`` run that reaches the start of the program repeats a NUL in place
  of the command it walks before the program, in both implementations (the
  cross-check used to read out of bounds there; it now bounds the walk).
- The cross-check's reads before/after the program are modeled as NUL, so an
  unmatched ``a`` on a zero cell skips to the end and the program halts.
- ``u`` prints ``chr(cell & 0xFF)``, matching the cross-check's ``(char)``
  cast for cell values outside the byte range.

Invalid runtime operations halt with :class:`~esolangs.exceptions.HaltError`.

The interpreter runs on a :class:`_Machine` (the tape, the loop stack, the
pointer, and the code cursor), so it is step-capable: ``step()`` executes one
command and ``halted`` is true once the cursor reaches the end of the code.
``y`` draws a random skip, so like LaserFuck and WII2D the machine is
non-deterministic and is excluded from the state-cycle hang check.
"""

import secrets
import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The two substitution cycles, in the order the cross-check scans them.
_CYCLES = ("pevkjzwr", "yuctsobqihald")

# "Past the end" (or before the start) of a program reads as NUL: the
# cross-check's program string is NUL-terminated, so an out-of-range read
# yields a command that matches no case.
_NUL = "\0"


def _translate(code: str) -> str:
    """Translate the source text into an executable program.

    Mirrors the cross-check ``trans`` table: each source character found in
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


class _Machine:
    """Per-run Painfuck state: the tape, loop stack, pointer, and cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object (``y`` makes the machine non-deterministic, so the
    hang detector must exclude it).
    """

    def __init__(self, code: str, io: IO) -> None:
        """Translate ``code`` and start at the first command."""
        self.io = io
        self.prog = _translate(code)
        self.n = len(self.prog)
        self.tape: list[int] = [0]
        self.loop: list[int] = []
        self.ptr = 0
        self.ind = 0
        self.rep = 1

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= self.n

    # The VM's language-shaped view: Translated tape + cursor; ip the cursor, memory
    # the tape.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.loop)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(self.tape),
            tuple(self.loop),
            self.ptr,
            self.ind,
            self.rep,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, advancing the cursor."""
        if self.halted:
            return
        c = self.prog[self.ind]
        self.ind += 1

        while self.rep > 0:
            self.rep -= 1

            if c == "p":
                self.tape[self.ptr] += 2
            elif c == "s":
                self.tape[self.ptr] -= 1
            elif c == "r":
                self.ptr += 2
                while self.ptr >= len(self.tape):
                    self.tape.append(0)
            elif c == "l":
                if self.ptr:
                    self.ptr -= 1
            elif c == "i":
                line = self.io.input_str()
                try:
                    self.tape[self.ptr] = int(line)
                except ValueError:
                    raise HaltError from None
            elif c == "j":
                self.tape[self.ptr] = self.io.input_char()
                # The cross-check's discard-to-end-of-line loop leaves the
                # main command variable holding '\n', so a ``c``/``t``-repeated
                # ``j`` only reads once and then no-ops.
                c = "\n"
            elif c == "o":
                self.io.print_num(self.tape[self.ptr])
            elif c == "u":
                self.io.print_char(chr(self.tape[self.ptr] & 0xFF))
            elif c == "a":
                if self.tape[self.ptr] != 0:
                    self.loop.append(self.ind - 1)
                else:
                    val = 1
                    while val != 0 and self.ind < self.n:
                        ch = self.prog[self.ind]
                        self.ind += 1
                        if ch == "a":
                            val += 1
                        elif ch == "b":
                            val -= 1
            elif c == "b":
                if not self.loop:
                    raise HaltError("unmatched 'b': the loop stack is empty")
                self.ind = self.loop.pop()
            elif c == "k":
                self.tape[self.ptr] = self.tape[self.ptr] * self.tape[self.ptr]
            elif c == "z":
                self.tape[self.ptr] = 0
            elif c == "h":
                self.tape[self.ptr] = _trunc2(self.tape[self.ptr])
            elif c == "w":
                self.tape[self.ptr] = (
                    self.tape[self.ptr + 1] if self.ptr + 1 < len(self.tape) else 0
                )
            elif c == "q":
                if self.ptr:
                    self.tape[self.ptr] = self.tape[self.ptr - 1]
            elif c == "c":
                self.rep = 1
                while c == "c":
                    c = self.prog[self.ind] if self.ind < self.n else _NUL
                    self.ind += 1
                    self.rep *= 7
            elif c == "y":
                # The wiki specifies a random skip; match the cross-check's
                # coin flip (the generator and differential avoid `y`).
                if secrets.randbelow(2) and self.ind < self.n:
                    c = self.prog[self.ind]
                    self.ind += 1
            elif c == "e":
                self.ind = self.n
                self.rep = 0
                return
            elif c == "v" and self.tape[self.ptr] != 0 and self.ind < self.n:
                c = self.prog[self.ind]
                self.ind += 1
            elif c == "d":
                self.ptr = 0
            elif c == "t":
                val = self.ind
                self.rep = 1
                found = False
                while self.ind > 0:
                    self.ind -= 1
                    if self.prog[self.ind] != "t":
                        found = True
                        break
                    self.rep *= 3
                c = self.prog[self.ind] if found else _NUL
                self.ind = val

        self.rep += 1


def run(code: str, io: IO) -> None:
    """Run a Painfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
