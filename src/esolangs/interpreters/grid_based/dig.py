"""Dig interpreter implementation.

2D esoteric language with a mole that moves on a grid and can dig underground.
Movement commands work overground, work commands function underground.

The wiki only lists ``@`` as a halt; this interpreter also stops the program
(without error) when the mole walks off the grid.  A work command that needs a
digit from an adjacent cell but finds none, or divides by an adjacent zero, is
an invalid runtime operation and halts the program with
:class:`~esolangs.exceptions.HaltError`; an empty program is malformed and
rejected with :class:`ValueError`.

``#`` reads its steer from an adjacent digit and the wiki covers every case
("Rotates Mole to left when value beside it is 0, and right when 1.  When
it's neither of those, keep straight.").  ``%`` is specified only for 0 and
1 ("Overrides current value with space when 0, and newline when 1"); the
other eight digits leave the mole unchanged here rather than being assigned
a meaning the wiki does not give them.

Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys
from collections.abc import Callable

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# Headings as (drow, dcol), in the order the ``^>'<`` glyphs select
# them: up, right, down, left.  Row grows downward.
_DIRECT = [(-1, 0), (0, 1), (1, 0), (0, -1)]


#: One instant of a run: ``(code, row, col, move, mole, num, done)`` -- the
#: grid, where the mole is and which way it faces, the value it carries,
#: how many work commands remain armed, and whether it has stopped.  A
#: value :func:`_advance` maps forward, with the grid as a ``tuple`` of
#: rows for the same reason.
#:
#: The grid is state, not a fixed program: ``;`` writes the mole back into
#: the cell under it, so what a later pass reads is something an earlier
#: step wrote.  ``snapshot`` already included it for that reason.
#:
#: ``num`` is the underground counter ``$`` arms.  Every work command is
#: inert unless it is positive, so it is what decides whether a cell is an
#: instruction or scenery.
type _State = tuple[tuple[str, ...], int, int, int, int, int, bool]


def _value(code: tuple[str, ...], row: int, col: int, size: int) -> int:
    """Return the first digit adjacent to ``(row, col)``.

    A work command that needs a digit and finds none is an invalid runtime
    operation, so this halts rather than inventing a default.
    """
    for d_row, d_col in _DIRECT:
        if 0 <= row + d_row < len(code) and 0 <= col + d_col < size:
            val = code[row + d_row][col + d_col]
            if val.isdigit():
                return int(val)
    raise HaltError


def _write(code: tuple[str, ...], row: int, col: int, text: str) -> tuple[str, ...]:
    """Return ``code`` with the cell at ``(row, col)`` replaced by ``text``."""
    line = code[row]
    return (*code[:row], line[:col] + text + line[col + 1 :], *code[row + 1 :])


def _advance(
    state: _State,
    size: int,
    value: int | None = None,
    *,
    armed: bool = False,
) -> _State:
    """Return the state after executing the cell under the mole.

    Pure: it reads ``state`` and returns a new one.  Two effects stay with
    the caller.  ``:`` prints the mole -- this only clears it -- and the
    reads ``=``/``~`` arrive as ``value``, already taken from the port,
    with ``None`` standing for the empty read that zeroes the mole.

    ``armed`` is the ``$`` hook's answer, consulted only when the cell is
    ``$``: a true answer halts before the counter is set.

    A work command fires only while ``num`` is positive, and every one that
    fires spends one.  Outside that, a cell is scenery the mole walks over
    -- which is what lets a Dig grid carry its data in plain sight.
    """
    code, row, col, move, mole, num, done = state
    char = code[row][col]

    if num:
        if char == "%":
            # "Overrides current value with space when 0, and newline when
            # 1."  The wiki stops there, unlike ``#`` below, which spells
            # out its third case -- so the other eight digits are a gap in
            # the spec, and the choice here is to leave the mole alone.
            if (n := _value(code, row, col, size)) == 1:
                mole = 10
            elif n == 0:
                mole = 32
        elif char in "=~":
            mole = value if value is not None else 0
        elif char == ":":
            mole = 0  # the print itself already happened in the shell
        elif char == "+":
            mole += _value(code, row, col, size)
        elif char == "-":
            mole -= _value(code, row, col, size)
        elif char == "*":
            mole *= _value(code, row, col, size)
        elif char == "/":
            if (n := _value(code, row, col, size)) == 0:
                raise HaltError
            mole //= n
        elif char == ";":
            code = _write(code, row, col, str(mole))
        elif char.isdigit():
            mole = int(char)
        elif char.isalpha() or char in ".,!?":
            mole = ord(char)
        num -= 1
    elif char in "^>'<":
        move = "^>'<".find(char)
    elif char == "#":
        # The adjacent digit steers, and the wiki spells out all three
        # cases: "Rotates Mole to left when value beside it is 0, and right
        # when 1.  When it's neither of those, keep straight."  So the
        # third arm is specified behaviour, not a fall-through.
        if (n := _value(code, row, col, size)) == 1:
            move += 1
        elif n == 0:
            move -= 1
        # The modulo is load-bearing, not defensive: a grid that keeps
        # turning drives the heading past the ends of _DIRECT.
        move %= 4
    elif char == "$":
        if armed:
            return (code, row, col, move, mole, num, True)
        num = _value(code, row, col, size)
    elif char == "@":
        return (code, row, col, move, mole, num, True)

    row += _DIRECT[move][0]
    col += _DIRECT[move][1]

    # Walking off the grid stops the program, without error.
    if row < 0 or row >= len(code) or col < 0 or col >= size:
        done = True
    return (code, row, col, move, mole, num, done)


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
        self.mole = self.num = self.row = self.col = 0
        self.move = 1
        self._done = False

    @property
    def halted(self) -> bool:
        """Whether the mole has halted or left the grid."""
        return self._done

    # The VM's language-shaped view.  Dig is a 2D grid walked by a mole, so
    # the instruction position is where the mole is *and* which way it faces
    # -- a bare index would not say where the next step lands.  ``memory`` is
    # the one value the mole carries; there is no stack.

    @property
    def ip(self) -> tuple[int, ...]:
        """The mole's ``(row, col, heading)``."""
        return (self.row, self.col, self.move)

    @property
    def memory(self) -> list[int]:
        """The value the mole is carrying."""
        return [self.mole]

    @property
    def stack(self) -> list[object]:
        """Dig has no stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        The grid is included because ``;`` writes the mole back into it.
        """
        return (
            self.row,
            self.col,
            self.move,
            self.mole,
            self.num,
            tuple(self.code),
            self.io.position(),
        )

    def _value(self) -> int:
        """Get the first digit value from cells adjacent to the mole."""
        return _value(tuple(self.code), self.row, self.col, self.size)

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (
            tuple(self.code),
            self.row,
            self.col,
            self.move,
            self.mole,
            self.num,
            self._done,
        )

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- the VM's views and
        the tests read them -- so they stay; the one assignment a step
        makes is here rather than scattered through the rules above.
        """
        code, self.row, self.col, self.move, self.mole, self.num, self._done = state
        self.code = list(code)

    def step(self) -> None:
        """Execute the cell under the mole, then move it one cell.

        The three effects live here rather than in the transition: this is
        the shell.  ``:`` prints the mole the transition then clears, the
        reads ``=`` and ``~`` take a byte here -- ``=`` as a character and
        ``~`` as a digit -- and ``$`` asks the caller's hook whether to
        stop.  All three are consulted only when they would actually fire,
        which for a work command means the underground counter is armed.
        """
        if self._done:
            return
        char = self.code[self.row][self.col]

        value: int | None = None
        armed = False
        if self.num and char in "=~":
            temp = self.io.input_str()
            if temp:
                value = ord(temp[0]) if char == "=" else int(temp[0])
        elif self.num and char == ":":
            if self.mole < 10:
                self.io.print_num(self.mole)
            else:
                self.io.print_char(chr(self.mole))
        elif not self.num and char == "$":
            armed = self.func()

        self._restore(_advance(self._state, self.size, value, armed=armed))


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
