"""Dotlang interpreter implementation.

2D esoteric language where dots (instruction pointers) move through a grid.
Each dot can carry values and execute commands based on its position.

The interpreter skips over string and warp-name tokens after parsing them,
so printing a string containing spaces works (the whole literal is consumed
as one token).
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


def run(code: list[str], io: IO) -> None:
    """Execute a Dotlang program with 2D dot movement and command execution."""
    if code == [" "]:
        io.print_str(" ")
        return

    size = max(len(lne) for lne in code)
    code = [c.ljust(size) for c in code]
    dots: list[Dot] = []
    curr = 0

    for num, val in enumerate(code):
        if "•" in val:
            k = val.find("•")
            d = "^>v<".find(v) if k and (v := val[k - 1]) in "^>v<" else 1
            dots.append(Dot(num, k, d))
            Dot.set(code)
            break
    else:
        return

    while dots:
        dot = dots[curr]
        val = code[dot.x][dot.y]

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
                io.print_value(dot.val)
            else:
                return
        elif val == "~":
            dot.new(io.input_str())
        elif val == "(":
            if g := dot.match(r"\(`\w+"):
                name = ")" + g[0][1:]
                dest = dot.find(name, return_dot=True)
                if not dest:
                    return
                if not isinstance(dest, Dot):
                    raise RuntimeError("warp destination not found")  # pragma: no cover
                dots.append(dest)
            else:
                match = 1
                x, y = dot.x, dot.y
                while match:
                    if dot.dir % 2:
                        y += 1
                        if y == size:
                            return
                    else:
                        x += 1
                        if x == Dot.mx:
                            return
                    if (c := code[x][y]) == "(":
                        match += 1
                    elif c == ")":
                        match -= 1
                dots.append(Dot(x, y, dot.dir))
        elif val == "W":
            if dot.match("W~"):
                warp = io.input_str("Warp: ")
                if not dot.find(f"W{warp}`s"):
                    return
            elif g := dot.match(r"W\w+`s"):
                warp = g[0][:-1] + "e"
                if not dot.find(warp):
                    return
        elif val in "!?:":
            t = (str, float, int)["!?:".find(val)]
            if isinstance(dot.val, t):
                if dot.dir % 2:
                    dot.dir -= 1
                else:
                    dot.dir += 1

        if val not in " \n" and dot.move():
            curr = (curr + 1) % len(dots)
        else:
            dots.pop(curr)
            if dots:
                curr %= len(dots)


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        data = f.readlines()

    run(data, IO())
