"""Interpreter for Suffolk.

> moves right, < sums the current cell into the accumulator and rewinds the
pointer, ! zeroes a cell computed from the accumulator, , reads a byte of
input, and . prints the accumulator minus one.  Execution loops for a
fixed number of passes over the code.

The wiki describes ``,`` as reading one character, with EOF setting the
accumulator to zero; this interpreter reads a whole line (using only its
first byte) and raises :class:`EOFError` on exhausted input instead.  An
empty program is malformed and rejected with :class:`ValueError`.

The wiki's rerun is infinite, so there is no halt to run to and the budget
is a *unit*, not a safety limit: :func:`run` executes ``limit`` whole passes
over the code and returns.  A pass is the language's own unit -- the pointer
runs off the end of the code and wraps -- so a whole number of them always
leaves the machine at a line boundary, where a raw instruction budget would
stop wherever it happened to land, mid-pass.  This matches A Painter Ant,
whose implicit loop is metered the same way.  The count can be overridden as
a second command-line argument (or the ``limit`` parameter to :func:`run`).

The interpreter runs on a :class:`_Machine` (the code, tape, and
accumulator), so it is step-capable: ``step()`` executes one command.  The
language never halts, so ``halted`` is always ``False`` and the budget lives
in :func:`run`'s driver; a repeated :meth:`_Machine.snapshot` is what proves
a program loops, via ``esolangs.vm.run_until_halt_or_cycle``.
"""

from esolangs.interpreters.io import IO
from esolangs.interpreters.oisc_cli import main_with_limit


class _Machine:
    """Per-run Suffolk state: the code, tape, and accumulator."""

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and start the tape and accumulator at zero.

        ``code`` must be non-empty; an empty program is malformed.
        """
        if not code:
            raise ValueError("Suffolk program cannot be empty")
        self.io = io
        self.code = code
        self.tape: list[int] = [0]
        self.ind = self.ptr = self.acc = 0

    @property
    def halted(self) -> bool:
        """The wiki's rerun never halts; only a repeated state proves a loop."""
        return False

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        The pass count is deliberately absent: it never steers ``step()``, so
        two states that differ only in how many passes preceded them run
        identically from here on.  Counting it would make every state unique
        by construction and reduce the cycle detector to a step budget --
        Suffolk's programs are periodic, and this is what lets that be proved.
        """
        return (self.ind, self.ptr, self.acc, tuple(self.tape))

    def step(self) -> None:
        """Execute one command, wrapping to the start at the end of the code."""
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


def run(code: str, io: IO, limit: int = 10) -> None:
    """Run a Suffolk program for ``limit`` whole passes over the code."""
    machine = _Machine(code, io)
    for _ in range(limit * len(machine.code)):
        machine.step()


if __name__ == "__main__":
    main_with_limit(run)
