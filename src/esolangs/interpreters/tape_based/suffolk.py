"""Interpreter for Suffolk.

> moves right, < sums the current cell into the accumulator and rewinds the
pointer, ! zeroes a cell computed from the accumulator, , reads a byte of
input, and . prints the accumulator minus one.  Execution loops over the
code until the run decides itself; see :func:`run`.

The wiki describes ``,`` as reading one character, with EOF setting the
accumulator to zero; this interpreter reads a whole line (using only its
first byte) and raises :class:`EOFError` on exhausted input instead.  An
empty program is malformed and rejected with :class:`ValueError`.

The wiki's rerun is infinite, so there is no halt to run to.  :func:`run`
used to count whole passes and stop after one, which answered the question
without deciding it: one pass was chosen because the programs were believed
to be finished by then, not shown to be.  It now stops on a *proof* instead
-- a repeated state, or the ``EOFError`` from reading past the end of the
input, whichever the program reaches.  Both are properties of the run, so
nothing is left to choose.  A program that does neither -- cells growing
without bound, and no input to run out of -- runs forever, which is what
``esolangs.run``'s ``timeout`` is for; the interpreter carries no cap of
its own.

The interpreter runs on a :class:`_Machine` (the code, tape, and
accumulator), so it is step-capable: ``step()`` executes one command.  The
language never halts, so ``halted`` is always ``False`` and the budget lives
in :func:`run`'s driver; a repeated :meth:`_Machine.snapshot` is what proves
a program loops, via ``esolangs.vm.run_until_halt_or_cycle``.
"""

import sys

from esolangs.interpreters.io import IO


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

    # The VM's language-shaped view: Tape + accumulator; ip the cursor, memory the tape.

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
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        The pass count is deliberately absent: it never steers ``step()``, so
        two states that differ only in how many passes preceded them run
        identically from here on.  Counting it would make every state unique
        by construction and reduce the cycle detector to a step budget --
        Suffolk's programs are periodic, and this is what lets that be proved.

        The input cursor, by contrast, is *not* optional, and leaving it out
        was a soundness bug.  ``,`` reads a byte, so two states with the same
        tape but different input remaining do not run identically -- one has
        a byte left to consume and the other raises.  Without the cursor the
        detector called two boolean-generator programs periodic when they in
        fact read once more and hit EOF, which is a hang reported where none
        exists.
        """
        return (self.ind, self.ptr, self.acc, tuple(self.tape), self.io.position())

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


def run(code: str, io: IO) -> None:
    """Run a Suffolk program until it repeats a state or runs out of input.

    The wiki's rerun is infinite, so a program is stopped from outside --
    but not by *counting*.  Both of the things a generated program does are
    decidable stops in their own right:

    * a program that reads runs out of input, and ``,`` raises
      :class:`EOFError` on the read past the end.  That fires part-way
      through the second pass, before the ``.`` that would print a second
      answer, so the output is the one the program computed from its real
      input.
    * a program that reads nothing ends where it began -- the text
      generator appends a tail that puts every cell back -- so its state
      repeats, and the repeat proves the loop at the end of the first pass,
      with the output written once.

    A program that does neither -- cells growing without bound, and no input
    to run out of -- runs forever, and that is left to the caller: it is
    what :func:`esolangs.run`'s ``timeout`` is for.  A step cap here would
    be a second bound at the wrong layer, and no other interpreter carries
    one except the OISCs, whose self-modifying memory rules out proving a
    loop from a repeated state at all.
    """
    machine = _Machine(code, io)
    seen: set[tuple[object, ...]] = set()
    while True:
        state = machine.snapshot()
        if state in seen:
            return
        seen.add(state)
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
