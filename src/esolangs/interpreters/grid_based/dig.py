"""Dig interpreter implementation.

2D esoteric language with a mole that moves on a grid and can dig underground.
Movement commands work overground, work commands function underground.

The wiki only lists ``@`` as a halt; this interpreter also stops the program
(without error) when the mole walks off the grid.  A work command that needs a
digit from an adjacent cell but finds none, or divides by an adjacent zero, is
an invalid runtime operation and halts the program with
:class:`~esolangs.exceptions.HaltError`; an empty program is malformed and
rejected with :class:`ValueError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys
from collections.abc import Callable

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_DIRECT = [(-1, 0), (0, 1), (1, 0), (0, -1)]


class _Machine:
    """Per-run Dig state: the mole, its heading, and the underground counter.

    ``step()`` executes the cell under the mole and advances it one cell in
    the current heading; ``halted`` is true once the mole hits ``@``, walks
    off the grid, or the ``$`` callback returns true.  The VM and the
    state-cycle hang detector expose this object.
    """

    def __init__(
        self,
        code: list[str],
        io: IO,
        func: Callable[[], bool] = lambda: False,
    ) -> None:
        """Pad ``code`` to a square grid, like :func:`run`."""
        if not code or not any(line.strip() for line in code):
            raise ValueError("Dig program cannot be empty")
        self.io = io
        self.func = func
        self.size = max(len(lne) for lne in code)
        self.code = [c.ljust(self.size) for c in code]
        self.mole = self.num = self.x = self.y = 0
        self.move = 1
        self._done = False

    @property
    def halted(self) -> bool:
        """Whether the mole has halted or left the grid."""
        return self._done

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        The grid is included because ``;`` writes the mole back into it.
        """
        return (
            self.x,
            self.y,
            self.move,
            self.mole,
            self.num,
            tuple(self.code),
            self.io.position(),
        )

    def _value(self) -> int:
        """Get the first digit value from cells adjacent to the mole."""
        lst = []
        for i, j in _DIRECT:
            if 0 <= self.x + i < len(self.code) and 0 <= self.y + j < self.size:
                val = self.code[self.x + i][self.y + j]
                if val.isdigit():
                    lst.append(int(val))
        if not lst:
            raise HaltError
        return lst[0]

    def step(self) -> None:
        """Execute the cell under the mole, then move it one cell."""
        if self._done:
            return
        char = self.code[self.x][self.y]
        if self.num:
            if char == "%":
                if (n := self._value()) == 1:
                    self.mole = 10
                elif n == 0:
                    self.mole = 32
            elif char in "=~":
                temp = self.io.input_str()

                if not temp:
                    self.mole = 0
                elif char == "=":
                    self.mole = ord(temp[0])
                else:
                    self.mole = int(temp[0])
            elif char == ":":
                if self.mole < 10:
                    self.io.print_num(self.mole)
                else:
                    self.io.print_char(chr(self.mole))

                self.mole = 0
            elif char == "+":
                self.mole += self._value()
            elif char == "-":
                self.mole -= self._value()
            elif char == "*":
                self.mole *= self._value()
            elif char == "/":
                n = self._value()
                if n == 0:
                    raise HaltError
                self.mole //= n
            elif char == ";":
                self.code[self.x] = (
                    self.code[self.x][: self.y]
                    + str(self.mole)
                    + self.code[self.x][self.y + 1 :]
                )
            elif char.isdigit():
                self.mole = int(char)
            elif char.isalpha() or char in ".,!?":
                self.mole = ord(char)
            self.num -= 1
        elif char in "^>'<":
            self.move = "^>'<".find(char)
        elif char == "#":
            if (n := self._value()) == 1:
                self.move += 1
            elif n == 0:
                self.move -= 1
            self.move %= 4
        elif char == "$":
            if self.func():
                self._done = True
                return
            self.num = self._value()
        elif char == "@":
            self._done = True
            return

        self.x += _DIRECT[self.move][0]
        self.y += _DIRECT[self.move][1]

        # Bounds checking to prevent IndexError
        if self.x < 0 or self.x >= len(self.code) or self.y < 0 or self.y >= self.size:
            self._done = True


def run(
    code: list[str],
    io: IO,
    func: Callable[[], bool] = lambda: False,
) -> None:
    """Execute a Dig program with mole movement and underground work commands."""
    machine = _Machine(code, io, func)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
