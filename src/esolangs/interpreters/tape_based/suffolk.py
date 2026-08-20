"""Interpreter for Suffolk.

> moves right, < sums the current cell into the accumulator and rewinds the
pointer, ! zeroes a cell computed from the accumulator, , reads a byte of
input, and . prints the accumulator minus one.  Execution loops until the
step limit is reached.

The wiki describes ``,`` as reading one character, with EOF setting the
accumulator to zero; this interpreter reads a whole line (using only its
first byte) and raises :class:`EOFError` on exhausted input instead.  The
wiki's infinite rerun is capped at 10 passes so programs terminate, and an
empty program is a malformed program rejected with :class:`ValueError`.
The loop cap can be overridden as a second command-line argument (or the
``limit`` parameter to :func:`run`).

The interpreter runs on a :class:`_Machine` (the code, tape, accumulator,
and pass counter), so it is step-capable: ``step()`` executes one command
and ``halted`` is true once ``limit`` full passes over the code complete.
"""

import sys

from esolangs.interpreters.io import IO


class _Machine:
    """Per-run Suffolk state: the code, tape, accumulator, and pass count."""

    def __init__(self, code: str, io: IO, limit: int = 10) -> None:
        """Store ``code`` and start the tape and accumulator at zero.

        ``code`` must be non-empty; an empty program is malformed.
        """
        if not code:
            raise ValueError("Suffolk program cannot be empty")
        self.io = io
        self.code = code
        self.limit = limit
        self.tape: list[int] = [0]
        self.ind = self.ptr = self.acc = self.num = 0

    @property
    def halted(self) -> bool:
        """Whether ``limit`` full passes over the code have completed."""
        return self.num >= self.limit

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, self.ptr, self.acc, self.num, tuple(self.tape))

    def step(self) -> None:
        """Execute one command, advancing the pass counter at line-end."""
        if self.halted:
            return
        if (sym := self.code[self.ind]) == ">":
            self.ptr += 1
            if self.ptr == len(self.tape):
                self.tape.append(0)
        elif sym == "<":
            self.acc += self.tape[self.ptr]
            self.ptr = 0
        elif sym == "!":
            val = self.tape[self.ptr] + 1 - self.acc
            self.tape[self.ptr] = max(0, val)
            self.ptr = self.acc = 0
        elif sym == ",":
            inp = self.io.input_str()
            self.acc = self.acc + ord(inp[0]) if inp else 0
        elif sym == "." and self.acc:
            self.io.print_char(chr(self.acc - 1))

        self.ind += 1
        if self.ind == len(self.code):
            self.ind = 0
            self.num += 1


def run(code: str, io: IO, limit: int = 10) -> None:
    """Run a Suffolk program, looping at most ``limit`` times."""
    machine = _Machine(code, io, limit)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            if len(sys.argv) > 2:
                run(data, IO(), limit=int(sys.argv[2]))
            else:
                run(data, IO())
