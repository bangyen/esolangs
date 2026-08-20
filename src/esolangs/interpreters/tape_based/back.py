r"""Interpreter for Back.

A beam bounces across a grid at right angles: \\ and / reflect its direction,
< and > move the tape pointer, - flips the current bit, + steps the beam
forward when the current bit is 0, and * halts, printing the tape.

The interpreter runs on a :class:`_Machine` (the beam's position and
direction, the bit tape, and the tape pointer), so it is step-capable:
``step()`` executes one cell, printing the tape and setting ``halted`` when
the beam reaches a ``*``.  A program with no ``*`` bounces the beam forever,
but the beam lives in a finite grid, so it eventually revisits a snapshot
and the state-cycle hang detector can prove the loop.

Malformed programs raise :class:`ValueError`.
"""

import sys

from esolangs.interpreters.io import IO


class _Machine:
    """Per-run Back state: the beam, the bit tape, and the tape pointer.

    ``step()`` executes one cell, printing the tape and setting ``halted``
    when the beam reaches a ``*``.  The VM and the state-cycle hang detector
    expose this object.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Pad ``code`` to a rectangle and start the beam at the top-left."""
        if not code or not any(line.strip() for line in code):
            raise ValueError("Back program cannot be empty")
        self.io = io
        self.size = max(len(line) for line in code)
        self.code = [line.ljust(self.size) for line in code]
        self.x = 0
        self.y = 0
        self.a, self.b = 0, 1
        self.tape: list[int] = [0]
        self.cell = 0
        self._done = False

    @property
    def halted(self) -> bool:
        """Whether the beam has reached a ``*``."""
        return self._done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.x,
            self.y,
            self.a,
            self.b,
            tuple(self.tape),
            self.cell,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one cell, moving the beam."""
        if self.halted:
            return
        c = self.code[self.x][self.y]
        if c == "\\":
            self.a, self.b = self.b, self.a
        elif c == "/":
            self.a, self.b = -self.b, -self.a
        elif c == "<":
            if self.cell:
                self.cell -= 1
        elif c == ">":
            self.cell += 1
            if self.cell == len(self.tape):
                self.tape.append(0)
        elif c == "-":
            self.tape[self.cell] ^= 1
        elif c == "+" and not self.tape[self.cell]:
            self.x, self.y = self.x + self.a, self.y + self.b
        elif c == "*":
            self.io.print_line(" ".join(map(str, self.tape)))
            self._done = True
            return

        self.x = (self.x + self.a) % len(self.code)
        self.y = (self.y + self.b) % self.size


def run(code: list[str], io: IO) -> None:
    """Run a Back program, printing the tape when it halts."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
