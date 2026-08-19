"""Interpreter for AlbaBet.

A tiny two-register language: an accumulator ``x`` and a secondary register
``y`` both start at 0.  ``a``/``b`` move ``x`` by +1/-1 (``b`` clamps at 0,
as a natural number), ``c``/``d`` set ``x`` to 0 and move the old ``x`` into
0 or ``y``, ``e``/``f`` copy ``x`` into ``y`` or clear ``y``, ``j`` adds
``x`` into ``y``, ``g``/``h`` multiply ``x`` by ``y`` or square ``x``, and
``i`` prints ``x`` as the Unicode character whose code point it is.  Any
other character is ignored.

``i`` prints ``Char.ofNat x``: when ``x`` is not a valid Unicode scalar
value (the surrogate range 0xD800-0xDFFF, or 0x110000 and above) it prints
NUL instead.  The values are unbounded natural numbers and the output is
that character's UTF-8 encoding.  Every character is a defined operation or
a no-op, so there is no malformed program (no :class:`ValueError`) and no
invalid runtime operation (no :class:`~esolangs.exceptions.HaltError`).

The interpreter runs on a :class:`_Machine` (the two registers and the code
cursor), so it is step-capable: ``step()`` executes one character and
``halted`` is true once the cursor reaches the end of the code (execution is
linear, so every program halts).
"""

import sys

from esolangs.interpreters.io import IO


class _Machine:
    """Per-run AlbaBet state: the two registers and the code cursor.

    ``step()`` executes one character; ``halted`` is true once the cursor
    reaches the end of the code.  The VM and the state-cycle hang detector
    expose this object (execution is linear, so every program halts).
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with both registers at zero."""
        self.io = io
        self.code = code
        self.x = 0
        self.y = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.x, self.y, self.ind, self.io.position())

    def step(self) -> None:
        """Execute one character, advancing the cursor."""
        if self.halted:
            return
        c = self.code[self.ind]
        self.ind += 1
        if c == "a":
            self.x += 1
        elif c == "b":
            if self.x:
                self.x -= 1  # natural-number subtraction clamps at 0
        elif c == "c":
            self.x = 0
        elif c == "d":
            self.x, self.y = 0, self.x
        elif c == "e":
            self.y = self.x
        elif c == "f":
            self.y = 0
        elif c == "j":
            self.y += self.x
        elif c == "g":
            self.x *= self.y
        elif c == "h":
            self.x *= self.x
        elif c == "i":
            if not (self.x < 0xD800 or 0xDFFF < self.x < 0x110000):
                self.x = 0  # invalid scalar -> Char.ofNat yields NUL
            self.io.print_char(chr(self.x))


def run(code: str, io: IO) -> None:
    """Run an AlbaBet program, printing each ``i`` as a character."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
