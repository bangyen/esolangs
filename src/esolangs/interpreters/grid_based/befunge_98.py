r"""Interpreter for Befunge-98, the unbounded two-dimensional Funge-98 core.

Funge-space is unbounded: unset cells read as space (32), and cells hold
unbounded integers.  The IP starts at the origin heading east and wraps by
Lahey-space: leaving the bounding box of non-space cells, it re-enters at
the box's far side along its own line.  String mode pushes one space per run
of spaces.  ``/`` and ``%`` by zero push 0; ``%`` truncates like ``/``.  A
pop off an empty stack reads 0.  ``&`` and ``~`` reflect at EOF, as do
unknown cells, ``A``-``Z`` (no fingerprints load), ``(`` and ``)`` (after
popping their operands), and the optional ``t i o = h l m``.  ``q`` halts
with the popped exit code; ``.`` prints the integer and a space.

Judgment calls, each where the specification leaves a gap:

- ``&`` reads one whitespace-delimited integer token, the convention every
  numeric reader here shares, rather than skipping non-digits.
- ``,`` writes the low byte, as Befunge does.
- ``k`` executes its target ``n`` times in place, then the IP moves on and
  meets the target once more: "0 or n+1 times", as the wiki table states.
- The bounding box only grows; ``p`` of a space does not shrink it.
- ``y`` reports a sandbox: no ``t i o =``, unbounded cells (0 bytes per
  cell), no command line, no environment, and a zero date and time.
- Space and the cells between ``;`` markers take one step each.

An empty program raises :class:`ValueError`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.randomness import Randomness, draw
from esolangs.interpreters.source_hints import syntax_error

#: ``?`` picks one, in the order the shell's draw maps to: right, down, left, up.
_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
_SPACE = 32
#: ``y`` item 3, the handprint: "ESOL" in ASCII.
_HANDPRINT = 0x45534F4C
_VERSION = 1

type _Vector = tuple[int, int]
#: pos, delta, offset, stacks, space, low, high, string, skip, spaced, done.
#: ``space`` is shared between branch states and never written in place.
type _Branch = tuple[
    _Vector,
    _Vector,
    _Vector,
    tuple[tuple[int, ...], ...],
    dict[_Vector, int],
    _Vector,
    _Vector,
    bool,
    bool,
    bool,
    bool,
]


class _Fixed:
    """A draw that always answers one direction, for forking ``?``."""

    def __init__(self, value: int) -> None:
        self.value = value

    def randbelow(self, upper: int) -> int:
        """Return the fixed direction."""
        return self.value % upper


def _char(value: int) -> str:
    """Return a cell's command; NUL stands in for values outside Unicode.

    NUL is no command, and unlike "" it is not a substring of every
    command set it is tested against.
    """
    return chr(value) if 0 <= value < 0x110000 else "\0"


def _block(stack: list[int], count: int) -> list[int]:
    """Remove and return ``stack``'s top ``count`` cells, zero-padded below.

    A count past the bottom takes the whole stack: slicing from
    ``len - count`` there would wrap to a negative index and drop cells.
    """
    start = max(len(stack) - max(count, 0), 0)
    block = [0] * max(count - len(stack), 0) + stack[start:]
    del stack[start:]
    return block


def _range(p: int, d: int, lo: int, hi: int) -> tuple[int | None, int | None] | None:
    """Return the ``t`` interval with ``lo <= p + t*d <= hi``; ``None`` is empty."""
    if d == 0:
        return (None, None) if lo <= p <= hi else None
    first, last = (lo - p, hi - p) if d > 0 else (hi - p, lo - p)
    return -(-first // d), last // d


class _Machine:
    """One IP over a sparse Funge-space dictionary."""

    reproducible_seed = 0
    #: ``ip`` is a column, a row and the heading; cells may lie outside the
    #: loaded rectangle, at any integer coordinate.
    ip_shape = "grid"

    def __init__(
        self, code: Sequence[str], io: IO, rng: Randomness | None = None
    ) -> None:
        if not any(code):
            raise syntax_error(
                "Befunge-98 program cannot be empty",
                "provide at least one cell; @ halts immediately",
            )
        #: Set while ``space`` is shared with a branch state; cleared by
        #: the copy that the next write makes.
        self.shared = False
        self.space: dict[_Vector, int] = {}
        self.low, self.high = (0, 0), (-1, -1)
        for y, line in enumerate(code):
            for x, char in enumerate(line):
                self._put((x, y), ord(char))
        self.code, self.io, self.rng = code, io, rng
        self.pos: _Vector = (0, 0)
        self.delta: _Vector = (1, 0)
        self.offset: _Vector = (0, 0)
        self.stacks: list[list[int]] = [[]]
        self.string = self.skip = self.spaced = self.done = False
        self.exit_code = 0

    @property
    def halted(self) -> bool:
        return self.done

    @property
    def ip(self) -> tuple[int, ...] | None:
        (x, y), (dx, dy) = self.pos, self.delta
        return None if self.done else (y, x, dx, dy)

    @property
    def stack(self) -> list[object]:
        return list(self.stacks[-1])

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.pos,
            self.delta,
            self.offset,
            tuple(map(tuple, self.stacks)),
            tuple(sorted(self.space.items())),
            self.string,
            self.skip,
            self.spaced,
            self.done,
            self.io.position(),
        )

    def cell(self, cell: _Vector) -> int:
        return self.space.get(cell, _SPACE)

    def branching_snapshot(self) -> _Branch:
        """Return the current state as the hang search's starting point."""
        self.shared = True
        return self.freeze()

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has reached ``@`` or ``q``."""
        return cast(_Branch, state)[10]

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_Branch, ...] | None:
        """Return one state per direction ``?`` could take.

        ``None`` where a step reads input, or ``k`` iterates a read or a
        draw, since neither can be forked here.
        """
        current = cast(_Branch, state)
        if current[10]:
            return (current,)
        machine = self._thaw(current)
        command = "" if current[7] or current[8] else _char(machine.cell(machine.pos))
        if command == "k":
            command = _char(machine.cell(machine.k_target())) + "k"
        if command[:1] in ("&", "~") or command == "?k":
            return None
        draws = range(4) if command == "?" else (0,)
        successors = []
        for direction in draws:
            branch = self._thaw(current)
            branch.rng = _Fixed(direction)
            branch.step()
            successors.append(branch.freeze())
        return tuple(successors)

    def freeze(self) -> _Branch:
        return (
            self.pos,
            self.delta,
            self.offset,
            tuple(map(tuple, self.stacks)),
            self.space,
            self.low,
            self.high,
            self.string,
            self.skip,
            self.spaced,
            self.done,
        )

    def _thaw(self, state: _Branch) -> _Machine:
        machine = _Machine.__new__(_Machine)
        (
            machine.pos,
            machine.delta,
            machine.offset,
            stacks,
            machine.space,
            machine.low,
            machine.high,
            machine.string,
            machine.skip,
            machine.spaced,
            machine.done,
        ) = state
        machine.stacks = [list(stack) for stack in stacks]
        machine.code, machine.io, machine.rng = self.code, ScriptedIO(), None
        machine.shared = True
        return machine

    def _put(self, cell: _Vector, value: int) -> None:
        if self.shared:
            # Copy on the first write: branch states share one space.
            self.space, self.shared = dict(self.space), False
        if value == _SPACE:
            self.space.pop(cell, None)
            return
        self.space[cell] = value
        if self.high[0] < self.low[0]:
            self.low = self.high = cell
        else:
            self.low = (min(self.low[0], cell[0]), min(self.low[1], cell[1]))
            self.high = (max(self.high[0], cell[0]), max(self.high[1], cell[1]))

    def _next(self, pos: _Vector) -> _Vector:
        """Return the cell after ``pos`` along the delta, Lahey-wrapped."""
        (x, y), (dx, dy) = pos, self.delta
        if dx == dy == 0:
            return pos
        across = _range(x, dx, self.low[0], self.high[0])
        down = _range(y, dy, self.low[1], self.high[1])
        if across is None or down is None:
            return x + dx, y + dy
        # One axis moves, so each side has at least one finite bound.
        first = max(low for low in (across[0], down[0]) if low is not None)
        last = min(high for high in (across[1], down[1]) if high is not None)
        if first > last:
            # The line misses the box: the IP is lost and keeps going.
            return x + dx, y + dy
        # Inside the box, or outside it heading in, skip the empty gap;
        # leaving it, re-enter at its far side along the same line.
        t = max(1, first) if last >= 1 else first
        return x + t * dx, y + t * dy

    def _pop(self) -> int:
        stack = self.stacks[-1]
        return stack.pop() if stack else 0

    def _pop_vector(self) -> _Vector:
        y = self._pop()
        return self._pop(), y

    def _push(self, *values: int) -> None:
        self.stacks[-1].extend(values)

    def _reflect(self) -> None:
        self.delta = (-self.delta[0], -self.delta[1])

    def k_target(self) -> _Vector:
        """Return ``k``'s target: the next cell that is not space or ``;``-skipped.

        The walk ends: ``k`` lies in the box, where Lahey wrapping cycles
        along one line through ``k``'s own cell, and two laps undo any
        ``;`` parity -- so ``k`` itself is the target at worst.
        """
        pos, skipping = self.pos, False
        while True:
            pos = self._next(pos)
            value = self.cell(pos)
            if value == ord(";"):
                skipping = not skipping
            elif not skipping and value != _SPACE:
                return pos

    def step(self) -> None:
        if self.done:
            return
        value = self.cell(self.pos)
        if self.string:
            if value == ord('"'):
                self.string = False
            elif value != _SPACE or not self.spaced:
                self._push(value)
            self.spaced = value == _SPACE
        elif self.skip:
            self.skip = value != ord(";")
        else:
            self._execute(value)
        if not self.done:
            self.pos = self._next(self.pos)

    def _execute(self, value: int) -> None:
        """Execute one instruction with the IP at its current cell."""
        command = _char(value)
        if value == _SPACE or command == "z":
            return
        if command.isdigit() and command.isascii():
            self._push(int(command))
        elif "a" <= command <= "f":
            self._push(ord(command) - ord("a") + 10)
        elif command in ("+", "-", "*", "/", "%", "`", "w"):
            b, a = self._pop(), self._pop()
            self._binary(command, a, b)
        elif command == "!":
            self._push(0 if self._pop() else 1)
        elif command in "><^v":
            self.delta = _DIRECTIONS[">v<^".index(command)]
        elif command == "?":
            self.delta = _DIRECTIONS[draw(self.rng, 4)]
        elif command == "_":
            self.delta = (1, 0) if self._pop() == 0 else (-1, 0)
        elif command == "|":
            self.delta = (0, 1) if self._pop() == 0 else (0, -1)
        elif command == "[":
            self.delta = (self.delta[1], -self.delta[0])
        elif command == "]":
            self.delta = (-self.delta[1], self.delta[0])
        elif command == "x":
            self.delta = self._pop_vector()
        elif command == "#":
            self.pos = self._next(self.pos)
        elif command == "j":
            steps = self._pop()
            (x, y), (dx, dy) = self.pos, self.delta
            self.pos = (x + steps * dx, y + steps * dy)
        elif command == ";":
            self.skip = True
        elif command == '"':
            self.string, self.spaced = True, False
        elif command == "'":
            self.pos = self._next(self.pos)
            self._push(self.cell(self.pos))
        elif command == "s":
            self.pos = self._next(self.pos)
            self._put(self.pos, self._pop())
        elif command == "k":
            self._iterate()
        else:
            self._execute_stack_or_io(command)

    def _binary(self, command: str, a: int, b: int) -> None:
        if command == "w":
            if a < b:
                self.delta = (self.delta[1], -self.delta[0])
            elif a > b:
                self.delta = (-self.delta[1], self.delta[0])
            return
        if command in "/%":
            if not b:
                self._push(0)
                return
            quotient = abs(a) // abs(b)
            if (a < 0) != (b < 0):
                quotient = -quotient
            self._push(quotient if command == "/" else a - quotient * b)
            return
        results = {"+": a + b, "-": a - b, "*": a * b, "`": int(a > b)}
        self._push(results[command])

    def _iterate(self) -> None:
        count = self._pop()
        target = self.k_target()
        if count <= 0:
            self.pos = target
            return
        instruction = self.cell(target)
        for _ in range(count):
            self._execute(instruction)
            if self.done:
                return

    def _execute_stack_or_io(self, command: str) -> None:
        stack = self.stacks[-1]
        if command == ":":
            top = self._pop()
            self._push(top, top)
        elif command == "\\":
            b, a = self._pop(), self._pop()
            self._push(b, a)
        elif command == "$":
            self._pop()
        elif command == "n":
            stack.clear()
        elif command == "g":
            x, y = self._pop_vector()
            self._push(self.cell((x + self.offset[0], y + self.offset[1])))
        elif command == "p":
            x, y = self._pop_vector()
            self._put((x + self.offset[0], y + self.offset[1]), self._pop())
        elif command == ".":
            self.io.print_str(f"{self._pop()} ")
        elif command == ",":
            self.io.print_char(chr(self._pop() & 0xFF))
        elif command == "&":
            try:
                self._push(self.io.input_num())
            except EOFError:
                self._reflect()
        elif command == "~":
            try:
                self._push(self.io.input_char())
            except EOFError:
                self._reflect()
        elif command == "@":
            self.done = True
        elif command == "q":
            self.exit_code, self.done = self._pop(), True
        elif command in "{}u":
            self._stack_stack(command)
        elif command == "y":
            self._sysinfo()
        elif command in "()":
            for _ in range(max(self._pop(), 0)):
                self._pop()
            self._reflect()
        else:
            # ``r`` itself, and what acts like it: A-Z (no fingerprint
            # loads), the optional t i o = and Trefunge's h l m.
            self._reflect()

    def _stack_stack(self, command: str) -> None:
        count = self._pop()
        if command == "{":
            toss = self.stacks[-1]
            moved = _block(toss, count)
            # A negative count pushes zeros onto what becomes the SOSS.
            toss.extend([0] * -count)
            toss.extend(self.offset)
            self.stacks.append(moved)
            self.offset = (self.pos[0] + self.delta[0], self.pos[1] + self.delta[1])
        elif len(self.stacks) < 2:
            # Spec: ``}`` and ``u`` with no SOSS reflect.
            self._reflect()
        elif command == "}":
            moved = _block(self.stacks.pop(), count)
            self.offset = self._pop_vector()
            # A negative count pops that many cells off the SOSS instead.
            for _ in range(-count):
                self._pop()
            self._push(*moved)
        else:
            toss, soss = self.stacks[-1], self.stacks[-2]
            for _ in range(abs(count)):
                source, sink = (soss, toss) if count > 0 else (toss, soss)
                sink.append(source.pop() if source else 0)

    def _sysinfo(self) -> None:
        """Push ``y``'s table, or only its ``n``-th cell for ``n > 0``."""
        which = self._pop()
        sizes = [len(stack) for stack in reversed(self.stacks)]
        cells = [0, 0, 0]  # environment, then the command line's two nulls
        cells += reversed(sizes)
        cells += [len(self.stacks), 0, 0]  # stack count, time, date
        span = (self.high[0] - self.low[0], self.high[1] - self.low[1])
        for vector in (span, self.low, self.offset, self.delta, self.pos):
            cells += vector
        cells += [0, 0, 2, 0, 0, _VERSION, _HANDPRINT, 0, 0]
        if which <= 0:
            self._push(*cells)
        elif which <= len(cells):
            self._push(cells[-which])
        else:
            stack = self.stacks[-1]
            depth = which - len(cells)
            self._push(stack[-depth] if depth <= len(stack) else 0)


def run(code: list[str], io: IO, rng: Randomness | None = None) -> int:
    """Execute a Befunge-98 program and return its ``q`` exit code."""
    machine = _Machine(code, io, rng)
    drive(machine)
    return machine.exit_code


if __name__ == "__main__":
    script_main(run, shape="strip")
