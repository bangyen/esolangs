"""An interpreter-faithful Minifuck simulator that runs code incrementally.

The shipped interpreter takes its whole program up front, which a search or
an emitter cannot do -- both need to advance a machine one instruction at a
time and branch on the result.  :class:`Sim` mirrors
``_Machine.step`` exactly (checked against it on every program this module's
callers produce) while accepting instructions one at a time.

The one addition is ``dead``: a ``.`` that would print a zero pool reads a
byte of input instead, which a *parameterized* generator must never do, so
that transition is marked as a dead end rather than simulated.
"""


class Sim:
    """A Minifuck machine fed one instruction at a time.

    ``tape``/``ptr`` mirror the interpreter's state, ``out`` accumulates
    printed characters, ``skip`` records that ``[`` consumed its guard slot,
    and ``dead`` marks a machine that tried to read input.
    """

    __slots__ = ("dead", "out", "ptr", "skip", "tape")

    def __init__(self) -> None:
        """Start with an eight-cell tape at the origin, as the interpreter does."""
        self.tape = [0] * 8
        self.ptr = 0
        self.out: list[str] = []
        self.dead = False
        self.skip = False

    def copy(self) -> "Sim":
        """Return an independent copy, for branching a search or a probe."""
        clone = Sim.__new__(Sim)
        clone.tape = list(self.tape)
        clone.ptr = self.ptr
        clone.out = list(self.out)
        clone.dead = self.dead
        clone.skip = self.skip
        return clone

    def key(self) -> tuple[object, ...]:
        """Return the whole state, hashable, so a search can dedup on it."""
        return (tuple(self.tape), self.ptr, tuple(self.out), self.dead, self.skip)

    def exec(self, ins: str) -> None:
        """Execute one instruction, mirroring ``_Machine.step``."""
        if self.dead:
            return
        if self.skip:
            self.skip = False
            return
        if ins == "<":
            if self.ptr:
                self.ptr -= 1
        elif ins in ".[":
            self.ptr += 1
            if self.ptr + 1 >= len(self.tape):
                self.tape.append(0)
            self.tape[self.ptr] ^= 1
            if ins == ".":
                value = int("".join(map(str, self.tape[:8])), 2)
                if value:
                    self.out.append(chr(value))
                else:
                    # A zero pool makes ``.`` read input; a parameterized
                    # program must never do that, so this path is a dead end.
                    self.dead = True
            elif not self.tape[self.ptr]:
                self.tape[self.ptr + 1] ^= 1
                self.skip = True


def setter(bit: int) -> str:
    """Return the ``{Xi}`` fill writing ``bit`` at ``ptr+1``.

    Both spellings are two characters and leave the pointer where they found
    it, so every instantiation of a template has the same length -- without
    that, the program's length leaks the inputs it is meant to be computing.
    """
    return "[<" if bit else "xx"
