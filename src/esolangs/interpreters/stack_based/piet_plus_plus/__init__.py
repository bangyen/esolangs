"""Piet++ raster interpreter following https://esolangs.org/wiki/Piet%2B%2B.

Piet's traversal (blocks, DP/CC, white slides, black walls, halting) over a
64-colour space: channel bytes 00/55/AA/FF are levels 0-3, and a transition
runs the command at (red delta mod 4, green delta mod 2, blue delta mod 4),
each delta new minus old.  Elements are integers or nested stacks; the stack
pointer starts at the top stack, depth 0.  A command whose operands are
missing or of the wrong type, or that needs a parent the top stack lacks, is
ignored without popping, as the page recommends.

Both wiki programs with stated outputs pin the semantics: XKCD Random Number
prints ``4`` (push-stack, push-int 4, push-down, recursive out-integer) and
User:Miui/Nah.'s 1x330 column prints ``Nah.``.  Old minus new prints nothing
in either, which settles the delta's sign.

Judgment calls for what the page leaves open:

- Read and Write pop their x operand: Write's "the third value is popped"
  reaches the third value only if x left first.  The offsets add to the
  codel just entered, where the transition's command runs.  An off-image
  target, or a Write value outside 0..0xFFFFFF, ignores the command whole.
- Colours are packed 0xRRGGBB; alpha is dropped.  A pixel outside the 64
  colours (Write may store one) slides like white, as Piet's module treats
  non-standard colours.
- A Write lands at once; the next step reads the updated image, so a
  rewritten current codel changes its own block, and one written black
  halts the run (the page gives no way off a black codel).
- A codel is one pixel ("a block of color equivalent to a single pixel")
  of the codel grid; like Piet, the grid's scale is detected when omitted
  (so enlarged images such as ``generate(..., scale=2)`` read correctly),
  and an explicit ``scale`` overrides detection.
- Add with a stack keeps stack order: an integer above a stack goes on its
  top, below it on its bottom, and stack ``B`` below stack ``T`` makes
  ``B``'s elements the bottom of ``T``.
- Size pushes without popping ("pushes the size of the top item").
- Out on a stack prints its elements top first, recursing into stacks.
- Roll-Context follows the page's first three examples: levels 0..y-1 are
  linked by each level's top stack, every level but the deepest needs one,
  a level's data is everything but that link, and level ``i`` takes level
  ``i + x``'s data.  The fourth example's "insufficient depth" contradicts
  the second, which has the same shape and rolls; it is not followed.
- Roll and Roll-Context of depth 0 pop both operands and move nothing;
  Divide and Mod by zero are ignored; both floor.  An In at EOF is ignored,
  and In Integer consumes a token that is not an integer.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import suppress
from copy import deepcopy
from typing import Any

from esolangs._drive import drive
from esolangs._source import raster_source as load_source
from esolangs.interpreters.codels import DIRECTIONS, find_block, leave, slide
from esolangs.interpreters.io import IO
from esolangs.interpreters.memory import parse_integer
from esolangs.raster import Raster

__all__ = ["load_source", "run"]

supports_scale = True

Pixel = tuple[int, int, int]
Point = tuple[int, int]
#: An int or a nested stack (a list, bottom first); ``Any`` spares the casts.
Element = Any

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
_LEVELS = {0: 0, 85: 1, 170: 2, 255: 3}
_INTEGER = re.compile(r"[+-]?[0-9]+")

# (red delta mod 4, green delta mod 2, blue delta mod 4) -> command.
_COMMANDS = {
    (red, green, blue): name
    for green, rows in enumerate(
        (
            (
                ("noop", "push_int", "push_stack", "pop"),
                ("dup", "roll", "roll_context", "push_up"),
                ("push_down", "pull_up", "up", "down"),
                ("add", "subtract", "multiply", "divide"),
            ),
            (
                ("mod", "negate", "not", "greater"),
                ("equal", "lesser", "size", "in_integer"),
                ("in_character", "out_integer", "out_character", "depth"),
                ("read", "write", "pointer", "toggle"),
            ),
        )
    )
    for blue, row in enumerate(rows)
    for red, name in enumerate(row)
}

_BINARY: dict[str, Callable[[int, int], int | None]] = {
    "subtract": lambda left, right: left - right,
    "multiply": lambda left, right: left * right,
    "divide": lambda left, right: left // right if right else None,
    "mod": lambda left, right: left % right if right else None,
    "greater": lambda left, right: int(left > right),
    "equal": lambda left, right: int(left == right),
    "lesser": lambda left, right: int(left < right),
}


def _colour(pixel: Pixel) -> Pixel:
    """Return a palette colour, treating any other pixel as white."""
    return pixel if all(channel in _LEVELS for channel in pixel) else WHITE


def _ints(stack: list[Element], count: int) -> bool:
    return len(stack) >= count and all(type(v) is int for v in stack[-count:])


def _freeze(value: Element) -> object:
    return tuple(map(_freeze, value)) if isinstance(value, list) else value


class _Machine:
    """A Piet++ run: a mutable image, the stack tree, and the pointer chain."""

    ip_shape = "grid"

    def __init__(self, program: Raster, io: IO, *, scale: int | None = None) -> None:
        rows = program._normalized(scale)  # noqa: SLF001
        self.rows = [list(row) for row in rows]
        self._program_key = (
            len(rows[0]),
            bytes(channel for row in rows for pixel in row for channel in pixel),
        )
        self.io = io
        self.current: Point = (0, 0)
        self.dp, self.cc = 0, -1
        # chain[-1] is the current stack; each is the top element of the last.
        self.chain: list[list[Element]] = [[]]
        self.halted = _colour(self.rows[0][0]) == BLACK
        self._writes: dict[Point, Pixel] = {}
        self._input_reads = 0

    @property
    def stack(self) -> list[Element]:
        return self.chain[-1]

    @property
    def ip(self) -> tuple[int, ...] | None:
        x, y = self.current
        return None if self.halted else (y, x, self.dp, self.cc)

    def snapshot(self) -> tuple[object, ...]:
        path = tuple(
            next(i for i, item in enumerate(parent) if item is child)
            for parent, child in zip(self.chain, self.chain[1:], strict=False)
        )
        return (
            self.current,
            self.dp,
            self.cc,
            _freeze(self.chain[0]),
            path,
            frozenset(self._writes.items()),
            self.io.progress(),
            self.halted,
            self._program_key,
            self._input_reads,
        )

    def step(self) -> None:
        if self.halted:
            return
        colour = _colour(self.rows[self.current[1]][self.current[0]])
        if colour == BLACK:
            self.halted = True
            return
        if colour == WHITE:
            self._slide(self.current)
            return
        block = find_block(self.rows, self.current, _colour)
        for attempt in range(8):
            x, y = leave(block, self.dp, self.cc)
            dx, dy = DIRECTIONS[self.dp]
            target = x + dx, y + dy
            tx, ty = target
            if 0 <= tx < len(self.rows[0]) and 0 <= ty < len(self.rows):
                seen = _colour(self.rows[ty][tx])
                if seen == WHITE:
                    self._slide(target)
                    return
                if seen != BLACK:
                    self.current = target
                    (r, g, b), (r0, g0, b0) = seen, colour
                    change = (
                        (r // 85 - r0 // 85) % 4,
                        (g // 85 - g0 // 85) % 2,
                        (b // 85 - b0 // 85) % 4,
                    )
                    self._command(_COMMANDS[change], len(block))
                    return
            if attempt % 2 == 0:
                self.cc *= -1
            else:
                self.dp = (self.dp + 1) % 4
        self.halted = True

    def _slide(self, start: Point) -> None:
        slid = slide(self.rows, start, self.dp, self.cc, _colour)
        if slid is None:
            self.halted = True
        else:
            self.current, self.dp, self.cc = slid

    def _command(self, name: str, size: int) -> None:
        stack = self.stack
        if name == "push_int":
            stack.append(size)
        elif name == "push_stack":
            stack.append([])
        elif name in {"pop", "dup", "size"} and stack:
            if name == "pop":
                stack.pop()
            elif name == "dup":
                stack.append(deepcopy(stack[-1]))
            else:
                top = stack[-1]
                stack.append(-1 if type(top) is int else len(top))
        elif name == "roll" and _ints(stack, 2):
            depth, rolls = stack[-2:]
            if 0 <= depth <= len(stack) - 2:
                del stack[-2:]
                rolls = rolls % depth if depth else 0
                if rolls:
                    stack[-depth:] = stack[-rolls:] + stack[-depth:-rolls]
        elif name == "roll_context" and _ints(stack, 2):
            self._roll_context()
        elif name == "push_up" and len(self.chain) > 1 and stack:
            self.chain[-2].append(stack.pop())
        elif name == "push_down" and len(stack) > 1 and type(stack[-2]) is list:
            stack[-2].append(stack.pop())
        elif name == "pull_up" and stack and type(stack[-1]) is list and stack[-1]:
            stack.append(stack[-1].pop())
        elif name == "up" and len(self.chain) > 1:
            self.chain.pop()
        elif name == "down" and stack and type(stack[-1]) is list:
            self.chain.append(stack[-1])
        elif name == "add" and len(stack) > 1:
            below, above = stack[-2:]
            del stack[-2:]
            if type(below) is int and type(above) is int:
                stack.append(below + above)
            else:
                # Keep stack order: ``below`` ends under ``above``.
                low = [below] if type(below) is int else below
                high = [above] if type(above) is int else above
                stack.append([*low, *high])
        elif name in _BINARY and _ints(stack, 2):
            result = _BINARY[name](*stack[-2:])
            if result is not None:
                stack[-2:] = [result]
        elif name in {"negate", "not"} and _ints(stack, 1):
            stack[-1] = -stack[-1] if name == "negate" else int(stack[-1] == 0)
        elif name in {"pointer", "toggle"} and _ints(stack, 1):
            turns = stack.pop()
            if name == "pointer":
                self.dp = (self.dp + turns) % 4
            elif turns % 2:
                self.cc *= -1
        elif name == "depth":
            stack.append(len(self.chain) - 1)
        elif name in {"read", "write"}:
            self._bitmap(name)
        elif name in {"out_integer", "out_character"} and stack:
            self._out(stack.pop(), number=name == "out_integer")
        elif name in {"in_integer", "in_character"}:
            self._in(number=name == "in_integer")

    def _roll_context(self) -> None:
        stack = self.stack
        depth, rolls = stack[-2:]
        if depth < 0:
            return
        del stack[-2:]
        levels = [stack]
        while len(levels) < depth and levels[-1] and type(levels[-1][-1]) is list:
            levels.append(levels[-1][-1])
        if len(levels) < depth:
            stack.extend((depth, rolls))
            return
        # A level's top stack is its link down and stays; the rest is data.
        links = [
            level[-1:] if level and type(level[-1]) is list else []
            for level in levels[:depth]
        ]
        data = [
            level[: len(level) - len(link)]
            for level, link in zip(levels, links, strict=False)
        ]
        for i, (level, link) in enumerate(zip(levels, links, strict=False)):
            level[:] = data[(i + rolls) % depth] + link

    def _bitmap(self, name: str) -> None:
        stack = self.stack
        operands = 2 if name == "read" else 3
        if not _ints(stack, operands):
            return
        x, y = self.current[0] + stack[-2], self.current[1] + stack[-1]
        if not (0 <= x < len(self.rows[0]) and 0 <= y < len(self.rows)):
            return
        if name == "read":
            r, g, b = self.rows[y][x]
            stack[-2:] = [r << 16 | g << 8 | b]
        elif 0 <= stack[-3] <= 0xFFFFFF:
            value = stack[-3]
            del stack[-3:]
            pixel = (value >> 16, value >> 8 & 0xFF, value & 0xFF)
            self.rows[y][x] = self._writes[(x, y)] = pixel

    def _out(self, value: Element, *, number: bool) -> None:
        pending = [value]
        while pending:
            item = pending.pop()
            if type(item) is list:
                pending.extend(item)  # top first: the top is popped next
            elif number:
                self.io.print_num(item)
            else:
                with suppress(ValueError, OverflowError):
                    self.io.print_char(chr(item))

    def _in(self, *, number: bool) -> None:
        try:
            read = self.io.input_token() if number else chr(self.io.input_char())
        except EOFError:
            return
        self._input_reads += 1
        if not number:
            self.stack.append(ord(read))
        elif _INTEGER.fullmatch(read):
            self.stack.append(parse_integer(read))


def run(program: Raster, io: IO, *, scale: int | None = None) -> None:
    """Execute a Piet++ image; detecting its codel scale unless ``scale`` is given."""
    drive(_Machine(program, io, scale=scale))
