"""Interpreter for NoComment.

The full wiki language (not a subset): a byte tape with a movable pointer,
plus a byte stack.  ``i``/``d`` increment/decrement the current cell, ``c``
clears it, ``l``/``r`` move the pointer left/right, ``n`` pushes the current
cell onto the stack, ``f`` pops the stack into the current cell, ``s``/``b``
jump forward/backward by a peeked stack value when the current cell is
nonzero (``s`` skips X instructions, ``b`` jumps back X-1), and ``o`` prints
the current cell as a byte.  The tape is static and the pointer wraps at both
ends (per the wiki, pointer overflow is legal and moves to the opposite end).
Its size defaults to 4096, matching the RISC-V cross-check, and ``run`` takes
a ``tape`` argument for programs that need a longer one.

Per the wiki, any character that is not a command is an error (there are no
comments), and popping an empty stack is an error.  A malformed program
(unrecognized character) raises :class:`ValueError`; an invalid operation
(stack underflow) raises :class:`~esolangs.exceptions.HaltError`.

The interpreter runs on a :class:`_Machine` (the byte tape, the stack, and
the code cursor), so it is step-capable: ``step()`` executes one command and
``halted`` is true once the cursor reaches the end of the code.  A jump back
to a command that never changes state is a cycle the state-cycle hang
detector proves; the ``run()`` backstop stays for the unbounded-growth class.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The default static tape size.  The tape is finite by specification, not for
# want of an unbounded Python list: the wiki makes pointer overflow and underflow
# legal and defines them as moving "to the opposite end of memory", then says
# outright that "this is the reason why the memory space needs to be static".  A
# tape with no opposite end could not implement that wrap, so no size at all is
# not an option -- only which finite size.
#
# The wiki leaves the size open, so it is a host choice, and callers may pass
# their own.  The default stays 4096 (matching the RISC-V cross-check's buffer)
# because the size is *observable*: cell 0 steps left to ``tape - 1``, so moving
# the default would change what existing wrapping programs do.
_TAPE = 4096


class _Machine:
    """Per-run NoComment state: the byte tape, the stack, and the cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object.
    """

    def __init__(self, code: str, io: IO, tape: int = _TAPE) -> None:
        """Start with a cleared tape of ``tape`` cells at the origin."""
        if tape < 1:
            raise ValueError(f"the NoComment tape needs at least one cell, got {tape}")
        self.io = io
        self.code = code
        self.size = tape
        self.tape: list[int] = [0] * tape
        self.stack: list[int] = []
        self.ptr = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple(self.tape),
            tuple(self.stack),
            self.ptr,
            self.ind,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, advancing the cursor."""
        if self.halted:
            return
        c = self.code[self.ind]
        if c == "i":
            self.tape[self.ptr] = (self.tape[self.ptr] + 1) % 256
        elif c == "d":
            self.tape[self.ptr] = (self.tape[self.ptr] - 1) % 256
        elif c == "c":
            self.tape[self.ptr] = 0
        elif c == "l":
            self.ptr = (self.ptr - 1) % self.size  # overflow wraps per the wiki
        elif c == "r":
            self.ptr = (self.ptr + 1) % self.size
        elif c == "n":
            self.stack.append(self.tape[self.ptr])
        elif c == "f":
            if not self.stack:
                raise HaltError
            self.tape[self.ptr] = self.stack.pop()
        elif c in "sb":
            if self.tape[self.ptr] and self.stack:
                # ``s`` skips X forward and ``b`` jumps back X-1, which is the
                # same move in opposite directions: the next command is at
                # ind ± X + 1.  Kept as one check because each half of the
                # bound is dead in one direction -- a forward target is always
                # at least 1, and a backward one rarely reaches the end -- so
                # separate copies leave unreachable branches behind.
                delta = self.stack[-1] if c == "s" else -self.stack[-1]
                target = self.ind + delta + 1
                if not 0 <= target < len(self.code):
                    raise HaltError
                self.ind += delta
        elif c == "o":
            self.io.print_char(chr(self.tape[self.ptr]))
        else:
            raise ValueError(f"unrecognized NoComment command {c!r}")
        self.ind += 1


def run(code: str, io: IO, tape: int = _TAPE) -> None:
    """Run a NoComment program on a tape of ``tape`` cells."""
    machine = _Machine(code, io, tape)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
