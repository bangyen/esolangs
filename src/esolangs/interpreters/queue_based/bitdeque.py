"""Interpreter for Bitdeque.

PUSH/INJECT append a register value to the deque, POP/EJECT pop it (0 when
empty), INVERT flips the register, and GOTO jumps to a numbered command when
the register is nonzero.

The wiki says of this language that "there is (currently) no I/O", so
following the repo convention for interpreter-only languages (Minsky Swap
prints its registers), the deque contents are printed when the program ends
-- space-separated on one line.  Both the choice to print and the format are
this interpreter's, not the spec's.

The wiki says GOTO goes to the Nth operation but does not pin down the
indexing; this interpreter treats N as 0-based (GOTO 2 lands on the third
command, skipping the GOTO itself), matching its reference test.

The interpreter runs on a :class:`_Machine` (token cursor, register, and
deque), so it is step-capable: ``step()`` executes one token and ``halted``
is true once the cursor runs past the last token, making a GOTO loop a
finite-state cycle the state cycle detector can prove.
"""

import re
import sys

from esolangs.interpreters.io import IO


class _Machine:
    """Per-run Bitdeque state: the token cursor, register, and deque.

    ``step()`` executes one token; ``halted`` is true once the cursor passes
    the last token.  The VM and the state-cycle hang detector expose this
    object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Tokenize ``code`` and reset the register, deque, and cursor."""
        self.io = io
        lst = ("INJECT", "PUSH", "EJECT", "POP", "INVERT", r"GOTO *(\d+)")
        join = f"({'|'.join(lst)})"
        self.tokens = re.findall(join, code)
        self.ind = 0
        self.reg = 0
        self.deq: list[int] = []

    @property
    def halted(self) -> bool:
        """Whether the cursor has passed the last token."""
        return self.ind >= len(self.tokens)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(self.tokens),
            self.ind,
            self.reg,
            tuple(self.deq),
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one token, advancing the cursor."""
        if self.halted:
            return
        sym = self.tokens[self.ind][0]
        if sym == "PUSH":
            self.deq.append(self.reg)
        elif sym == "INJECT":
            self.deq.insert(0, self.reg)
        elif sym == "POP":
            self.reg = self.deq.pop() if self.deq else 0
        elif sym == "EJECT":
            self.reg = self.deq.pop(0) if self.deq else 0
        elif sym == "INVERT":
            self.reg ^= 1
        elif self.reg:
            num = int(sym[4:])
            self.ind = num - 1

        self.ind += 1

    def render(self) -> None:
        """Print the deque contents, one value per space."""
        self.io.print_line(" ".join(map(str, self.deq)))


def run(code: str, io: IO) -> None:
    """Run a Bitdeque program and print the deque at the end."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.render()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
