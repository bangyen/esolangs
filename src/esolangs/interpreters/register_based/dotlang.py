"""
Dotlang interpreter implementation.

2D esoteric language where dots (instruction pointers) move through a grid.
Each dot can carry values and execute commands based on its position.
"""

from __future__ import annotations

import re
import sys


class Dot:
    """Represents a dot (instruction pointer) in the Dotlang programming language."""

    DIRS: tuple[tuple[int, int], ...] = (
        (-1, 0),
        (0, 1),
        (1, 0),
        (0, -1),
    )  # Direction vectors: up, right, down, left
    mx = my = 0  # Maximum x and y coordinates of the code grid
    code: list[str] = []  # The 2D code grid as a list of strings

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

    def find(self, warp: str, ret: bool = False) -> Dot | bool:
        """Find a warp destination in the code grid."""
        for num, val in enumerate(Dot.code):
            if warp in val:
                x, y = num, val.find(warp)
                if self.dir == 1:
                    y += len(warp) - 1
                if ret:
                    return Dot(x, y, self.dir)
                else:
                    self.x, self.y = x, y
                    return True
        return False


def run(code: list[str]) -> None:
    """Execute a Dotlang program with 2D dot movement and command execution."""
    if code == [" "]:
        print(" ", end="")
        return

    size = max(len(lne) for lne in code)
    code = [c.ljust(size) for c in code]
    line = 0
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
                print(dot.val, end="")
                line = 1
            else:
                return
        elif val == "~":
            dot.new(input("\n" * line + "Input: "))
            line = 0
        elif val == "(":
            if g := dot.match(r"\(`\w+"):
                name = ")" + g[0][1:]
                dest = dot.find(name, True)
                if not dest:
                    return
                assert isinstance(dest, Dot)
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
                warp = input("\n" * line + "Warp: ")
                if not dot.find(f"W{warp}`s"):
                    return
                line = False
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

    run(data)
