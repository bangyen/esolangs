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
  of the codel grid; the grid's scale is detected when omitted
  (so enlarged images such as ``generate(..., scale=2)`` read correctly),
  and an explicit ``scale`` overrides detection.
- Add with a stack keeps stack order: an integer above a stack goes on its
  top, below it on its bottom, and stack ``B`` below stack ``T`` makes
  ``B``'s elements the bottom of ``T``.
- ``Down`` makes a nested stack the current one, and both see the same
  value: the page's aliasing.
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
from collections.abc import Callable, Mapping
from contextlib import suppress
from types import MappingProxyType
from typing import Any, NamedTuple

from esolangs.raster import Raster
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._source import raster_source as load_source
from esolangs.runtime.codels import (
    BLACK,
    WHITE,
    exit_step,
    find_block,
    slide,
)
from esolangs.runtime.io import IO
from esolangs.runtime.memory import parse_integer

__all__ = ["load_source", "run"]

supports_scale = True

Pixel = tuple[int, int, int]
Point = tuple[int, int]
#: An integer or a nested stack, held as an immutable tuple (bottom first).
#: ``Any`` spares the casts around the recursive stack tree.
type Element = Any
type _Stack = tuple[Element, ...]
type _Rows = tuple[tuple[Pixel, ...], ...]


class _Core(NamedTuple):
    """One immutable machine state; ``writes`` holds the pixels ``Write`` changed."""

    current: Point
    dp: int
    cc: int
    root: _Stack
    path: tuple[int, ...]
    halted: bool
    rows: _Rows
    writes: Mapping[Point, Pixel]


#: ``("out", values, number)``: print each value as a number or a character.
type _Effect = tuple[str, tuple[int, ...], bool] | None

#: Channel bytes per colour level: 00/55/AA/FF are levels 0-3.
_STEP = 0x55
_LEVELS = {_STEP * level: level for level in range(4)}
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


class _NeedInputError(Exception):
    """The transition reached an ``in`` command and needs its value.

    One command per step, so nothing was output before the read.
    """

    def __init__(self, *, number: bool) -> None:
        super().__init__(number)
        self.number = number


class _FaultError(Exception):
    """A transition fault; one command per step, so it follows no output."""

    def __init__(self, cause: BaseException) -> None:
        super().__init__(cause)
        self.cause = cause


def _colour(pixel: Pixel) -> Pixel:
    """Return a palette colour, treating any other pixel as white."""
    return pixel if all(channel in _LEVELS for channel in pixel) else WHITE


def _ints(stack: _Stack, count: int) -> bool:
    return len(stack) >= count and all(type(v) is int for v in stack[-count:])


def _get(node: _Stack, path: tuple[int, ...]) -> _Stack:
    """Return the stack ``path`` selects from the nested root."""
    for index in path:
        node = node[index]
    return node


def _set(node: _Stack, path: tuple[int, ...], value: _Stack) -> _Stack:
    """Return ``node`` with the stack ``path`` selects replaced by ``value``."""
    if not path:
        return value
    index = path[0]
    return (
        *node[:index],
        _set(node[index], path[1:], value),
        *node[index + 1 :],
    )


def _out_values(value: Element) -> tuple[int, ...]:
    """Return the integers ``Out`` prints from ``value``, in print order."""
    result: list[int] = []
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is tuple:
            pending.extend(item)  # top first: the top is popped next
        else:
            result.append(item)
    return tuple(result)


def _roll_context(root: _Stack, path: tuple[int, ...]) -> _Stack:
    """Rotate the data of the linked stack levels, as the page's examples do."""
    stack = _get(root, path)
    depth, rolls = stack[-2], stack[-1]
    if depth < 0:
        return root
    base = stack[:-2]
    levels: list[_Stack] = [base]
    while len(levels) < depth and levels[-1] and type(levels[-1][-1]) is tuple:
        levels.append(levels[-1][-1])
    if len(levels) < depth:
        return _set(root, path, (*base, depth, rolls))
    links = [
        level[-1:] if level and type(level[-1]) is tuple else ()
        for level in levels[:depth]
    ]
    data = [
        level[: len(level) - len(link)]
        for level, link in zip(levels, links, strict=False)
    ]
    rotated = [data[(i + rolls) % depth] + links[i] for i in range(len(levels))]
    node = rotated[-1]
    for index in range(len(rotated) - 2, -1, -1):
        node = (*rotated[index][:-1], node)
    return _set(root, path, node)


def _written_rows(rows: _Rows, x: int, y: int, pixel: Pixel) -> _Rows:
    row = (*rows[y][:x], pixel, *rows[y][x + 1 :])
    return (*rows[:y], row, *rows[y + 1 :])


def _restack(core: _Core, stack: _Stack) -> _Core:
    """Return ``core`` with the current stack replaced by ``stack``."""
    return core._replace(root=_set(core.root, core.path, stack))


def _command(  # noqa: C901
    core: _Core,
    name: str,
    size: int,
    value: str | int | None,
    *,
    ready: bool = False,
) -> tuple[_Core, _Effect]:
    """Run ``name`` on the current stack; return the next core and any output."""
    path = core.path
    stack = _get(core.root, path)
    effect: _Effect = None

    if name == "push_int":
        core = _restack(core, (*stack, size))
    elif name == "push_stack":
        core = _restack(core, (*stack, ()))
    elif name in {"pop", "dup", "size"} and stack:
        if name == "pop":
            core = _restack(core, stack[:-1])
        elif name == "dup":
            core = _restack(core, (*stack, stack[-1]))
        else:
            top = stack[-1]
            core = _restack(core, (*stack, -1 if type(top) is int else len(top)))
    elif name == "roll" and _ints(stack, 2):
        depth, rolls = stack[-2:]
        if 0 <= depth <= len(stack) - 2:
            base = stack[:-2]
            rolls = rolls % depth if depth else 0
            if rolls:
                base = (*base[:-depth], *(base[-rolls:] + base[-depth:-rolls]))
            core = _restack(core, base)
    elif name == "roll_context" and _ints(stack, 2):
        core = core._replace(root=_roll_context(core.root, path))
    elif name == "push_up" and path and stack:
        parent = _get(core.root, path[:-1])
        moved = stack[-1]
        core = core._replace(root=_set(core.root, path[:-1], (*parent, moved)))
        core = _restack(core, stack[:-1])
    elif name == "push_down" and len(stack) > 1 and type(stack[-2]) is tuple:
        core = _restack(core, (*stack[:-2], (*stack[-2], stack[-1])))
    elif name == "pull_up" and stack and type(stack[-1]) is tuple and stack[-1]:
        nested = stack[-1]
        core = _restack(core, (*stack[:-1], nested[:-1], nested[-1]))
    elif name == "up" and path:
        core = core._replace(path=path[:-1])
    elif name == "down" and stack and type(stack[-1]) is tuple:
        core = core._replace(path=(*path, len(stack) - 1))
    elif name == "add" and len(stack) > 1:
        below, above = stack[-2:]
        if type(below) is int and type(above) is int:
            core = _restack(core, (*stack[:-2], below + above))
        else:
            low = (below,) if type(below) is int else below
            high = (above,) if type(above) is int else above
            core = _restack(core, (*stack[:-2], (*low, *high)))
    elif name in _BINARY and _ints(stack, 2):
        result = _BINARY[name](*stack[-2:])
        if result is not None:
            core = _restack(core, (*stack[:-2], result))
    elif name in {"negate", "not"} and _ints(stack, 1):
        core = _restack(
            core,
            (
                *stack[:-1],
                -stack[-1] if name == "negate" else int(stack[-1] == 0),
            ),
        )
    elif name in {"pointer", "toggle"} and _ints(stack, 1):
        turns = stack[-1]
        core = _restack(core, stack[:-1])
        if name == "pointer":
            core = core._replace(dp=(core.dp + turns) % 4)
        elif turns % 2:
            core = core._replace(cc=-core.cc)
    elif name == "depth":
        core = _restack(core, (*stack, len(path)))
    elif name in {"read", "write"}:
        operands = 2 if name == "read" else 3
        if _ints(stack, operands):
            x = core.current[0] + stack[-2]
            y = core.current[1] + stack[-1]
            if 0 <= x < len(core.rows[0]) and 0 <= y < len(core.rows):
                if name == "read":
                    r, g, b = core.rows[y][x]
                    core = _restack(core, (*stack[:-2], r << 16 | g << 8 | b))
                elif 0 <= stack[-3] <= 0xFFFFFF:
                    pixel = (
                        stack[-3] >> 16,
                        stack[-3] >> 8 & 0xFF,
                        stack[-3] & 0xFF,
                    )
                    core = _restack(core, stack[:-3])
                    core = core._replace(
                        rows=_written_rows(core.rows, x, y, pixel),
                        writes=MappingProxyType({**core.writes, (x, y): pixel}),
                    )
    elif name in {"out_integer", "out_character"} and stack:
        effect = ("out", _out_values(stack[-1]), name == "out_integer")
        core = _restack(core, stack[:-1])
    elif name in {"in_integer", "in_character"}:
        if not ready:
            raise _NeedInputError(number=name == "in_integer")
        if value is not None:
            if name == "in_integer":
                if _INTEGER.fullmatch(str(value)):
                    core = _restack(core, (*stack, parse_integer(str(value))))
            else:
                core = _restack(core, (*stack, int(value)))
    return core, effect


def _slide(core: _Core, start: Point) -> _Core:
    slid = slide(core.rows, start, core.dp, core.cc, _colour)
    if slid is None:
        return core._replace(halted=True)
    target, dp, cc = slid
    return core._replace(current=target, dp=dp, cc=cc)


def _advance(
    core: _Core,
    value: str | int | None = None,
    *,
    ready: bool = False,
) -> tuple[_Core, _Effect]:
    """Return the next core and any output effect for one Piet++ step.

    Pure.  ``value`` is the shell's input for an ``in`` command; ``ready``
    says whether it has been supplied (``value is None`` then means EOF).
    An input request carries no prefix (one command per step); any other
    fault is wrapped in :class:`_FaultError` so the shell can flush and re-raise.
    """
    try:
        return _advance_core(core, value, ready=ready)
    except _NeedInputError:
        raise
    except Exception as error:
        raise _FaultError(error) from error


def _advance_core(
    core: _Core,
    value: str | int | None,
    *,
    ready: bool,
) -> tuple[_Core, _Effect]:
    """Run the pure traversal and command dispatch behind :func:`_advance`."""
    current, dp, cc, rows = core.current, core.dp, core.cc, core.rows
    if core.halted:
        return core, None
    colour = _colour(rows[current[1]][current[0]])
    if colour == BLACK:
        return core._replace(halted=True), None
    if colour == WHITE:
        return _slide(core, current), None
    block = find_block(rows, current, _colour)
    exit_ = exit_step(rows, block, dp, cc, _colour)
    if exit_ is None:
        return core._replace(halted=True), None
    target, dp, cc, seen = exit_
    if seen == WHITE:
        # Slides with the dp and cc the exit search settled on, as in Piet.
        return _slide(core._replace(dp=dp, cc=cc), target), None
    (r, g, b), (r0, g0, b0) = seen, colour
    change = (
        (r // _STEP - r0 // _STEP) % 4,
        (g // _STEP - g0 // _STEP) % 2,
        (b // _STEP - b0 // _STEP) % 4,
    )
    moved = core._replace(current=target, dp=dp, cc=cc)
    return _command(moved, _COMMANDS[change], len(block), value, ready=ready)


# The stack tree is one immutable nested value with an explicit path to the current
# stack, which preserves the page's aliasing (``Down`` makes a nested stack the
# current one, and both see the same value).  :func:`_advance` is the pure transition;
# :meth:`_Machine.step` is the shell that reads input, applies it, and writes the
# returned :data:`_Effect`.  When an ``in`` command needs a value the transition raises
# :class:`_NeedInputError`; the shell reads one (or records EOF) and retries, which is
# sound because the transition is pure.
class _Machine:
    """Piet++ shell: one immutable :data:`_Core`, rebound per step."""

    ip_shape = "grid"

    def __init__(self, program: Raster, io: IO, *, scale: int | None = None) -> None:
        rows = program._normalized(scale)  # noqa: SLF001
        self.rows: _Rows = tuple(tuple(row) for row in rows)
        self._program_key = (
            len(rows[0]),
            bytes(channel for row in rows for pixel in row for channel in pixel),
        )
        self.io = io
        self.state = _Core(
            (0, 0),
            0,
            -1,
            (),
            (),
            _colour(rows[0][0]) == BLACK,
            self.rows,
            MappingProxyType({}),
        )
        self._input_reads = 0

    @property
    def stack(self) -> list[Element]:
        return list(_get(self.state[3], self.state[4]))

    @property
    def ip(self) -> tuple[int, ...] | None:
        x, y = self.state[0]
        return None if self.halted else (y, x, self.state[1], self.state[2])

    @property
    def halted(self) -> bool:
        return self.state[5]

    def snapshot(self) -> tuple[object, ...]:
        current, dp, cc, root, path, halted, _rows, writes = self.state
        return (
            current,
            dp,
            cc,
            root,
            path,
            frozenset(writes.items()),
            self.io.progress(),
            halted,
            self._program_key,
            self._input_reads,
        )

    def _write_effect(self, effect: _Effect) -> None:
        """Write one output effect exactly once."""
        if effect is None:
            return
        _kind, values, number = effect
        for item in values:
            if number:
                self.io.print_num(item)
            else:
                with suppress(ValueError, OverflowError):
                    self.io.print_char(chr(item))

    def step(self) -> None:
        """Execute one step, reading input and writing output as the shell.

        One command per step, so neither an input request nor a fault
        follows any output: the read happens, or the cause is re-raised.
        """
        if self.halted:
            return
        value: str | int | None = None
        ready = False
        while True:
            try:
                core, effect = _advance(self.state, value, ready=ready)
            except _NeedInputError as need:
                try:
                    value = (
                        self.io.input_token() if need.number else self.io.input_char()
                    )
                    self._input_reads += 1
                except EOFError:
                    value = None
                ready = True
            except _FaultError as fault:
                raise fault.cause from None
            else:
                self.state = core
                self._write_effect(effect)
                return


def run(program: Raster, io: IO, *, scale: int | None = None) -> None:
    """Execute a Piet++ image; detecting its codel scale unless ``scale`` is given."""
    drive(_Machine(program, io, scale=scale))


if __name__ == "__main__":
    script_main(run, loader=load_source)
