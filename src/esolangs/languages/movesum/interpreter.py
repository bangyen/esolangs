"""Interpreter for Movesum (esolangs.org oldid 189501).

The first line seeds a right-unbounded array of unsigned integers with
``Key=Value`` pairs; every other cell is 0.  The remaining lines are
``move A B`` and ``sum``, run cyclically.  The program halts once two
consecutive commands leave the array unchanged.

Commands:
    ``move A B``    cell B := cell A
    ``move -k B``   cell B := the next input number
    ``move A -k``   print cell A
    ``move -k -m``  nothing
    ``sum``         cell 0 := cells 1 + 2 + 3 + 4

Input/output:
    Numbers are whitespace-delimited; a read at EOF is 0 (as the page says
    for a ``42`` too).  Printed numbers are separated by one space, no
    trailing one.

Errors:
    ProgramError: an empty program, a first line that is not ``Key=Value``
        pairs, no instruction, or a line that is not ``move A B`` or ``sum``.
    ArgumentError: an input that is not an integer.
    HaltError: a negative input, which the unsigned array cannot hold.

Decisions:
    * "The array doesn't change" compares values: copying a cell's value to
      a cell that already holds it (an unset cell holds 0) is no change.  A
      comparison of the stored keys would count a write of 0 to a fresh cell
      as one.  The truth machine halts on 0 only so.
    * A print is a command that leaves the array unchanged.  The Hello World
      example ends ``move 7 -1``, ``move 0 0`` and halts on that pair.
    * The page gives no separator; numbers print space-separated.
    * ``Key`` and ``Value`` of ``42`` read the key first, then the value.
    * A blank line is skipped; any other line must parse, so a typo is not
      silently a no-op.  A negative index counts only in sign, so
      ``move -7 3`` reads like ``move -1 3``.
    * A negative input cannot be unsigned: it halts rather than wrap.

Cost: the array is a sparse map copied on a changing write, so a step costs
the cells the program has touched, bounded by its text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: ``(ind, array, quiet, printed)``: the next command, the touched cells, the
#: unchanged commands in a row (the run halts at 2), whether a number printed.
type _State = tuple[int, Mapping[int, int], int, bool]
#: ``(source, destination)`` of a ``move``, or ``None`` for ``sum``.
type _Command = tuple[int, int] | None

_PAIR = re.compile(r"(\d+)=(\d+)")
_MOVE = re.compile(r"move\s+(-?\d+)\s+(-?\d+)")


def _parse(code: str) -> tuple[list[tuple[str, str]], list[_Command]]:
    """Return the first line's pairs and the instruction list."""
    lines = [ln.strip() for ln in code.splitlines() if ln.strip()]
    if not lines:
        raise syntax_error("Movesum program is empty", "start with a line like 0=0")
    pairs: list[tuple[str, str]] = []
    for token in lines[0].split():
        if (pair := _PAIR.fullmatch(token)) is None:
            raise syntax_error(
                f"first line must be Key=Value pairs, got {token!r}",
                "seed the array with a line like 0=0 3=8",
            )
        pairs.append((pair[1], pair[2]))
    if not pairs:
        raise syntax_error("first line has no Key=Value pair", "use 0=0 for none")
    program: list[_Command] = []
    for line in lines[1:]:
        if line == "sum":
            program.append(None)
        elif move := _MOVE.fullmatch(line):
            program.append((int(move[1]), int(move[2])))
        else:
            raise syntax_error(
                f"not a Movesum instruction: {line!r}", "write 'move A B' or 'sum'"
            )
    if not program:
        raise syntax_error("Movesum program has no instruction", "add 'move A B'")
    return pairs, program


# Keep the name: the purity test finds the core by it.
def _advance(
    state: _State, program: list[_Command], value: int | None = None
) -> tuple[_State, int | None]:
    """Return the state after one command, and the number to print.

    Pure: an input arrives as ``value``, a print leaves as the return value.
    """
    ind, array, quiet, printed = state
    command = program[ind]
    out = None
    write: tuple[int, int] | None
    if command is None:
        write = (0, sum(array.get(k, 0) for k in (1, 2, 3, 4)))
    elif command[0] < 0:
        write = (command[1], value) if command[1] >= 0 and value is not None else None
    elif command[1] < 0:
        write, out = None, array.get(command[0], 0)
    else:
        write = (command[1], array.get(command[0], 0))
    if write is not None and array.get(write[0], 0) != write[1]:
        array = MappingProxyType({**array, write[0]: write[1]})
        quiet = 0
    else:
        quiet += 1
    return ((ind + 1) % len(program), array, quiet, printed or out is not None), out


class _Machine:
    """The seeded array, the cursor, and the unchanged-command count."""

    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.pairs, self.program = _parse(code)
        self.state: _State | None = None

    @property
    def halted(self) -> bool:
        return self.state is not None and self.state[2] >= 2

    @property
    def ip(self) -> int:
        return self.state[0] if self.state else 0

    @property
    def memory(self) -> dict[int, int]:
        return dict(self.state[1]) if self.state else {}

    def snapshot(self) -> tuple[object, ...]:
        if self.state is None:
            return (-1, frozenset(), 0, False, self.io.progress())
        ind, array, quiet, printed = self.state
        return (ind, frozenset(array.items()), quiet, printed, self.io.progress())

    def _number(self) -> int:
        try:
            number = self.io.input_num()
        except EOFError:
            return 0
        if number < 0:
            raise HaltError(f"negative input {number} in an unsigned array")
        return number

    def _seed(self) -> _State:
        """Read the first line, replacing each ``42`` by an input number."""
        array: dict[int, int] = {}
        for key, value in self.pairs:
            k = self._number() if key == "42" else int(key)
            array[k] = self._number() if value == "42" else int(value)
        return (0, MappingProxyType(array), 0, False)

    def step(self) -> None:
        if self.state is None:
            self.state = self._seed()
            return
        if self.halted:
            return
        command = self.program[self.state[0]]
        value = self._number() if command and command[0] < 0 <= command[1] else None
        spaced = self.state[3]
        self.state, out = _advance(self.state, self.program, value)
        if out is not None:
            self.io.print_str(f" {out}" if spaced else str(out))


def run(code: str, io: IO) -> None:
    """Execute a Movesum program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
