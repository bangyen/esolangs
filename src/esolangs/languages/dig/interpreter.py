"""Interpreter for Dig.

2D esoteric language with a mole that moves on a grid and can dig underground.
Movement commands work overground, work commands function underground.  The
mole holds one integer (a letter is its code).

The wiki only lists ``@`` as a halt; this interpreter also stops cleanly when
the mole walks off the grid.

Input/output:
    ``:`` prints the mole.  ``=`` reads one character and ``~`` an integer.
    Exhausted input raises (the repo-wide convention).

Errors:
    ProgramError: An empty program; a ``~`` token that is not an integer.
    InputExhaustedError: ``=`` or ``~`` at EOF.
    HaltError: A work command that needs an adjacent digit but finds none;
        division by an adjacent zero; a negative ``$`` digging distance.

Decisions:
    * ``#`` reads its steer from an adjacent digit and the wiki covers every
      case ("Rotates Mole to left when value beside it is 0, and right when
      1.  When it's neither of those, keep straight.").
    * ``%`` is specified only for 0 and 1 ("Overrides current value with
      space when 0, and newline when 1"); the other eight digits leave the
      mole unchanged rather than get an invented meaning.
    * ``:`` prints a value below 10 as a decimal and any other as a
      character, as the page has no types.
    * ``;`` copies the mole into its cell and keeps it ("the ``;`` is given
      the Moles current value"), so the truth machine prints ``2111...`` on
      1, as drawn; zeroing the mole would print ``111...``.
"""

from collections.abc import Callable
from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.memory import format_integer, parse_integer
from esolangs.runtime.source_hints import syntax_error

# Headings as (drow, dcol), in the order the ``^>'<`` glyphs select
# them: up, right, down, left.  Row grows downward.
_DIRECT = [(-1, 0), (0, 1), (1, 0), (0, -1)]
_CONTROL = frozenset("^>'<#$@")


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
type _Cell = str | int
type _Grid = tuple[tuple[_Cell, ...], ...]
type _State = tuple[_Grid, int, int, int, int, int, bool]


def _padded_grid(code: tuple[str, ...]) -> _Grid:
    """Return the initial rows padded to one width; stores replace tuples."""
    size = max(map(len, code))
    return tuple(tuple(line.ljust(size)) for line in code)


def _value(code: _Grid, row: int, col: int, size: int) -> int:
    """Return the first numeric cell adjacent to ``(row, col)``.

    A work command that needs a digit and finds none is an invalid runtime
    operation, so this halts rather than inventing a default.
    """
    for d_row, d_col in _DIRECT:
        if 0 <= row + d_row < len(code) and 0 <= col + d_col < size:
            val = code[row + d_row][col + d_col]
            if isinstance(val, int):
                # A stored12 is one operand; it must not become two cells.
                return val
            if val.isdigit():
                return int(val)
    raise HaltError(
        f"the operator at row {row}, column {col} has no digit beside it "
        f"to use as its operand",
        hint="put a digit beside the operator to supply its operand",
    )


def _write(code: _Grid, row: int, col: int, value: int) -> _Grid:
    """Return a grid with one cell replaced by the mole's integer value."""
    line = code[row]
    return (*code[:row], (*line[:col], value, *line[col + 1 :]), *code[row + 1 :])


class _Work(NamedTuple):
    """What one underground work command may read, and where it sits.

    ``value`` is the caller's read for ``=``/``~``, with ``None`` the empty
    read.  A handler returns the grid and the mole it leaves behind: the
    grid is a return because ``;`` rewrites the cell under the mole.
    """

    code: _Grid
    row: int
    col: int
    char: str
    size: int
    mole: int
    value: int | None


#: What a work handler returns: the grid (``;`` may have rewritten it)
#: and the mole after the command.
type _WorkResult = tuple[_Grid, int]


def _operand(work: _Work) -> int:
    """Return the adjacent digit the work command uses as its operand."""
    return _value(work.code, work.row, work.col, work.size)


def _work_override(work: _Work) -> _WorkResult:
    """Apply ``%``: load a space or a newline, keyed by the adjacent digit."""
    # "Overrides current value with space when 0, and newline when
    # 1."  The wiki stops there, unlike ``#``, which spells out its third
    # case -- so the other eight digits are a gap in the spec, and the
    # choice here is to leave the mole alone.
    if (n := _operand(work)) == 1:
        return work.code, 10
    if n == 0:
        return work.code, 32
    return work.code, work.mole


def _work_read(work: _Work) -> _WorkResult:
    """Apply ``=``/``~``: the read the caller took becomes the mole."""
    return work.code, work.value if work.value is not None else 0


def _work_printed(work: _Work) -> _WorkResult:
    """Apply ``:``: the shell already printed the mole, so clear it."""
    return work.code, 0


def _work_add(work: _Work) -> _WorkResult:
    """Apply ``+``: add the adjacent digit to the mole."""
    return work.code, work.mole + _operand(work)


def _work_subtract(work: _Work) -> _WorkResult:
    """Apply ``-``: subtract the adjacent digit from the mole."""
    return work.code, work.mole - _operand(work)


def _work_multiply(work: _Work) -> _WorkResult:
    """Apply ``*``: multiply the mole by the adjacent digit."""
    return work.code, work.mole * _operand(work)


def _work_divide(work: _Work) -> _WorkResult:
    """Apply ``/``: divide the mole by the adjacent digit, refusing zero."""
    if (n := _operand(work)) == 0:
        raise HaltError(
            f"division by zero at row {work.row}, column {work.col}",
            hint="ensure the divisor is nonzero before dividing",
        )
    return work.code, work.mole // n


def _work_store(work: _Work) -> _WorkResult:
    """Apply ``;``: copy the mole into the cell under it, and keep it."""
    return _write(work.code, work.row, work.col, work.mole), work.mole


#: The underground work commands, by cell.  Digits and letters are
#: ranges rather than single cells, so :func:`_work_command` handles
#: those two after consulting this table, plus any other cell, which is
#: scenery that merely spends the armed counter.
_WORK_HANDLERS: dict[str, Callable[[_Work], _WorkResult]] = {
    "%": _work_override,
    ":": _work_printed,
    "+": _work_add,
    "-": _work_subtract,
    "*": _work_multiply,
    "/": _work_divide,
    ";": _work_store,
    **dict.fromkeys("=~", _work_read),
}


def _work_command(work: _Work) -> _WorkResult:
    """Execute the underground work command under the mole."""
    handler = _WORK_HANDLERS.get(work.char)
    if handler is not None:
        return handler(work)
    if work.char.isdigit():
        return work.code, int(work.char)
    if work.char.isalpha() or work.char in ".,!?":
        return work.code, ord(work.char)
    return work.code, work.mole


def _steer(code: _Grid, row: int, col: int, size: int, move: int) -> int:
    """Apply ``#``: rotate the heading by the adjacent digit."""
    # The adjacent digit steers, and the wiki spells out all three
    # cases: "Rotates Mole to left when value beside it is 0, and right
    # when 1.  When it's neither of those, keep straight."  So the
    # third arm is specified behaviour, not a fall-through.
    if (n := _value(code, row, col, size)) == 1:
        move += 1
    elif n == 0:
        move -= 1
    # The modulo is required, not defensive: a grid that keeps
    # turning drives the heading past the ends of _DIRECT.
    return move % 4


def _dig(code: _Grid, row: int, col: int, size: int) -> int:
    """Apply ``$``: arm the underground counter from the adjacent digit."""
    num = _value(code, row, col, size)
    if num < 0:
        raise HaltError(f"negative digging distance at row {row}, column {col}")
    return num


def _move_on(
    code: _Grid,
    row: int,
    col: int,
    move: int,
    mole: int,
    num: int,
    size: int,
    *,
    done: bool,
) -> _State:
    """Return the state with the mole moved one cell along its heading."""
    row += _DIRECT[move][0]
    col += _DIRECT[move][1]

    # Walking off the grid stops the program, without error.
    if row < 0 or row >= len(code) or col < 0 or col >= size:
        done = True
    return (code, row, col, move, mole, num, done)


def _advance(
    state: _State,
    size: int,
    value: int | None = None,
) -> _State:
    """Return the state after executing the cell under the mole.

    Pure; two effects stay with the caller.  ``:`` prints the mole (this only
    clears it), and the reads ``=``/``~`` arrive as ``value``, already taken
    from the port, with ``None`` the empty read that zeroes the mole.

    A work command fires only while ``num`` is positive, and each spends one;
    otherwise a cell is scenery, so a grid can carry data in plain sight.
    """
    code, row, col, move, mole, num, done = state
    char = code[row][col]

    if isinstance(char, int):
        if num:
            mole = char
            num -= 1
    elif num:
        code, mole = _work_command(_Work(code, row, col, char, size, mole, value))
        num -= 1
    elif char in "^>'<":
        move = "^>'<".find(char)
    elif char == "#":
        move = _steer(code, row, col, size, move)
    elif char == "$":
        num = _dig(code, row, col, size)
    elif char == "@":
        return (code, row, col, move, mole, num, True)

    return _move_on(code, row, col, move, mole, num, size, done=done)


class _Machine:
    """Per-run Dig state: the mole, its heading, and the underground counter.

    ``step()`` executes the cell under the mole and advances it one cell in
    the current heading; ``halted`` is true once the mole hits ``@`` or
    walks off the grid.  The VM and the state-cycle hang detector expose
    this object.
    """

    def __init__(
        self,
        code: list[str],
        io: IO,
    ) -> None:
        """Pad ``code`` to a rectangular grid, like :func:`run`."""
        if not code or not any(line.strip() for line in code):
            raise syntax_error(
                "Dig program cannot be empty",
                "provide a nonempty grid; @ halts immediately",
            )
        self.io = io
        self.code = _padded_grid(tuple(code))
        self.size = len(self.code[0])
        self.mole = self.num = self.row = self.col = 0
        self.move = 1
        self._done = False
        self._input_reads = 0

    @property
    def halted(self) -> bool:
        """Whether the mole has halted or left the grid."""
        return self._done

    # The VM's language-shaped view.  Dig is a 2D grid walked by a mole, so
    # the instruction position is where the mole is *and* which way it faces
    # -- a bare index would not say where the next step lands.  ``memory`` is
    # the one value the mole carries; there is no stack.

    #: ``ip`` is a cell of the program's own rectangle: the first two
    #: parts are a row and a column, and the rest is a heading.  Without
    #: this a caller cannot tell the pair from a call depth or a frame
    #: stack, which look identical and mean somewhere else entirely.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        """The mole's ``(row, col, heading)``."""
        return (self.row, self.col, self.move)

    @property
    def memory(self) -> list[int]:
        """The value the mole is carrying."""
        return [self.mole]

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
            self.code,
            self.io.progress(),
            self._input_reads,  # IO providers may expose no cursor.
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (
            self.code,
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
        (
            self.code,
            self.row,
            self.col,
            self.move,
            self.mole,
            self.num,
            self._done,
        ) = state

    def step(self) -> None:
        """Execute the cell under the mole, then move it one cell.

        The two effects live here rather than in the transition: this is
        the shell.  ``:`` prints the mole the transition then clears, and
        the reads ``=`` and ``~`` take a line here -- ``=`` as its first
        character and ``~`` as an integer.  They are consulted only when
        they can fire, which requires the underground counter to be armed.
        """
        if self._done:
            return
        char = self.code[self.row][self.col]

        # Scenery only moves the mole; avoid rebuilding its whole state.
        if not self.num and char not in _CONTROL:
            self.row += _DIRECT[self.move][0]
            self.col += _DIRECT[self.move][1]
            self._done = not (
                0 <= self.row < len(self.code) and 0 <= self.col < self.size
            )
            return

        value: int | None = None
        if self.num:
            if char == "=":
                value = self.io.input_char()
                self._input_reads += 1
            elif char == "~":
                temp = self.io.input_token()
                self._input_reads += 1
                value = parse_integer(temp)
            elif char == ":":
                if self.mole < 10:
                    self.io.print_str(format_integer(self.mole))
                else:
                    self.io.print_char(chr(self.mole))

        self._restore(_advance(self._state, self.size, value))


def run(
    code: list[str],
    io: IO,
) -> None:
    """Execute a Dig program with mole movement and underground work commands."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run, shape="keep")
