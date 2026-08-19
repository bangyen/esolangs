"""Dotlang interpreter implementation.

2D esoteric language where dots (instruction pointers) move through a grid.
Each dot can carry values and execute commands based on its position.

The interpreter skips over string and warp-name tokens after parsing them,
so printing a string containing spaces works (the whole literal is consumed
as one token).

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

from __future__ import annotations

import re
import sys
from typing import ClassVar

from esolangs.interpreters.io import IO


class Dot:
    """Represents a dot (instruction pointer) in the Dotlang programming language."""

    DIRS: tuple[tuple[int, int], ...] = (
        (-1, 0),
        (0, 1),
        (1, 0),
        (0, -1),
    )  # Direction vectors: up, right, down, left
    mx = my = 0  # Maximum x and y coordinates of the code grid
    code: ClassVar[list[str]] = []  # The 2D code grid as a list of strings

    def __init__(self, x: int, y: int, d: int) -> None:
        """Initialize a new dot at the specified position and direction."""
        self.val: int | float | str | None = None  # value carried by this dot
        self.dir: int = d  # Current direction of movement
        self.x: int = x  # Current x-coordinate
        self.y: int = y  # Current y-coordinate

    @staticmethod
    def set(code: list[str]) -> None:
        """Set the global code grid and calculate its dimensions."""
        Dot.code = code
        Dot.mx = len(code)
        Dot.my = len(code[0])

    def new(self, val: str) -> None:
        """Set the dot's value, automatically determining the appropriate type."""
        if re.match(r"\d+\.\d+", val):
            self.val = float(val)
        elif re.match(r"\d+", val):
            self.val = int(val)
        else:
            self.val = val

    def move(self) -> bool:
        """Move the dot one step in its current direction."""
        x, y = Dot.DIRS[self.dir]
        self.x += x
        self.y += y
        if x:
            return 0 <= self.x < Dot.mx
        return 0 <= self.y < Dot.my

    def match(self, regex: str) -> re.Match[str] | None:
        """Check if the current position matches a regular expression pattern."""
        line = Dot.code[self.x][self.y :]
        return re.match(regex, line)

    def find(self, warp: str, *, return_dot: bool = False) -> Dot | bool:
        """Find a warp destination, moving this dot or returning a new one.

        With ``return_dot`` true, a new :class:`Dot` at the destination is
        returned; otherwise the destination is followed in place and ``True``
        is returned on success.
        """
        for num, val in enumerate(Dot.code):
            if warp in val:
                x, y = num, val.find(warp)
                if self.dir == 1:
                    y += len(warp) - 1
                if return_dot:
                    return Dot(x, y, self.dir)
                self.x, self.y = x, y
                return True
        return False


class _Machine:
    """Per-run Dotlang state: the grid, the live dots, and the current dot.

    ``step()`` executes one command for the current dot and advances it;
    ``halted`` is true once no dots remain (the program ended, the last dot
    left the grid, or a warp was not found).  The VM and the state-cycle
    hang detector expose this object.
    """

    def __init__(self, code: list[str], io: IO) -> None:
        """Pad ``code``, find the starting ``•``, and spawn its dot."""
        self.io = io
        self.size = max(len(lne) for lne in code)
        self.code = [c.ljust(self.size) for c in code]
        self.dots: list[Dot] = []
        self.curr = 0

        for num, val in enumerate(self.code):
            if "•" in val:
                k = val.find("•")
                d = "^>v<".find(v) if k and (v := val[k - 1]) in "^>v<" else 1
                self.dots.append(Dot(num, k, d))
                Dot.set(self.code)
                break

    @property
    def halted(self) -> bool:
        """Whether every dot has been consumed."""
        return not self.dots

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            tuple((d.x, d.y, d.dir, d.val) for d in self.dots),
            self.curr,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command for the current dot, then advance it."""
        if not self.dots:
            return
        dot = self.dots[self.curr]
        val = self.code[dot.x][dot.y]

        if val in "^>v<":
            dot.dir = "^>v<".find(val)
        elif val == "#":
            if g := dot.match(r"#(\d+(\.\d+)?|`.*`)"):
                content = g[0][1:]
                if content.startswith("`"):
                    # a backtick literal is always a string
                    dot.val = content[1:-1]
                else:
                    dot.new(content)
                if dot.dir == 1:
                    dot.y += len(g[0]) - 1
            elif dot.val is not None:
                self.io.print_value(dot.val)
            else:
                self.dots.clear()
                return
        elif val == "~":
            dot.new(self.io.input_str())
        elif val == "(":
            if g := dot.match(r"\(`\w+"):
                name = ")" + g[0][1:]
                dest = dot.find(name, return_dot=True)
                if not dest:
                    self.dots.clear()
                    return
                if not isinstance(dest, Dot):
                    raise RuntimeError("warp destination not found")  # pragma: no cover
                self.dots.append(dest)
            else:
                match = 1
                x, y = dot.x, dot.y
                while match:
                    if dot.dir % 2:
                        y += 1
                        if y == self.size:
                            self.dots.clear()
                            return
                    else:
                        x += 1
                        if x == Dot.mx:
                            self.dots.clear()
                            return
                    if (c := self.code[x][y]) == "(":
                        match += 1
                    elif c == ")":
                        match -= 1
                self.dots.append(Dot(x, y, dot.dir))
        elif val == "W":
            if dot.match("W~"):
                warp = self.io.input_str("Warp: ")
                if not dot.find(f"W{warp}`s"):
                    self.dots.clear()
                    return
            elif g := dot.match(r"W\w+`s"):
                warp = g[0][:-1] + "e"
                if not dot.find(warp):
                    self.dots.clear()
                    return
        elif val in "!?:":
            t = (str, float, int)["!?:".find(val)]
            if isinstance(dot.val, t):
                if dot.dir % 2:
                    dot.dir -= 1
                else:
                    dot.dir += 1

        if val not in " \n" and dot.move():
            self.curr = (self.curr + 1) % len(self.dots)
        else:
            self.dots.pop(self.curr)
            if self.dots:
                self.curr %= len(self.dots)


def run(code: list[str], io: IO) -> None:
    """Execute a Dotlang program with 2D dot movement and command execution."""
    if code == [" "]:
        io.print_str(" ")
        return

    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        data = f.readlines()

    run(data, IO())
