r"""Dig interpreter implementation."""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# Headings as (drow, dcol), in.
# them: up, right, down, left.
_DIRECT = [(-1, 0), (0, 1), (1, 0), (0, -1)]


# : One instant of a run:.
# : grid, where the mole is and.
# : how many work commands.
# : value :func:`_advance` maps.
#: rows for the same reason.
# :.
# : The grid is state, not a.
# : the cell under it, so what.
# : step wrote.
# :.
# : ``num`` is the underground.
# : inert unless it is.
#: instruction or scenery.
type _State = tuple[tuple[str, ...], int, int, int, int, int, bool]


def _value(code: tuple[str, ...], row: int, col: int, size: int) -> int:
    r"""Return the first digit adjacent to ``(row, col)``."""
    for d_row, d_col in _DIRECT:
        if 0 <= row + d_row < len(code) and 0 <= col + d_col < size:
            val = code[row + d_row][col + d_col]
            if val.isdigit():
                return int(val)
    raise HaltError(
        f"the operator at row {row}, column {col} has no digit beside it "
        f"to use as its operand"
    )


def _write(code: tuple[str, ...], row: int, col: int, text: str) -> tuple[str, ...]:
    r"""Return ``code`` with the cell at ``(row, col)`` replaced by."""
    line = code[row]
    return (*code[:row], line[:col] + text + line[col + 1 :], *code[row + 1 :])


def _advance(
    state: _State,
    size: int,
    value: int | None = None,
) -> _State:
    r"""Return the state after executing the cell under the mole."""
    code, row, col, move, mole, num, done = state
    char = code[row][col]

    if num:
        if char == "%":
            # "Overrides current value with.
            # 1." The wiki stops there,.
            # out its third case -- so the.
            # the spec, and the choice here.
            if (n := _value(code, row, col, size)) == 1:
                mole = 10
            elif n == 0:
                mole = 32
        elif char in "=~":
            mole = value if value is not None else 0
        elif char == ":":
            mole = 0  # the print itself already.
        elif char == "+":
            mole += _value(code, row, col, size)
        elif char == "-":
            mole -= _value(code, row, col, size)
        elif char == "*":
            mole *= _value(code, row, col, size)
        elif char == "/":
            if (n := _value(code, row, col, size)) == 0:
                raise HaltError(f"division by zero at row {row}, column {col}")
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
        # The adjacent digit steers,.
        # cases: "Rotates Mole to left.
        # when 1.
        # third arm is specified.
        if (n := _value(code, row, col, size)) == 1:
            move += 1
        elif n == 0:
            move -= 1
        # The modulo is required, not.
        # turning drives the heading.
        move %= 4
    elif char == "$":
        num = _value(code, row, col, size)
    elif char == "@":
        return (code, row, col, move, mole, num, True)

    row += _DIRECT[move][0]
    col += _DIRECT[move][1]

    # Walking off the grid stops.
    if row < 0 or row >= len(code) or col < 0 or col >= size:
        done = True
    return (code, row, col, move, mole, num, done)


class _Machine:
    r"""Per-run Dig state: the mole, its heading, and the underground."""

    def __init__(
        self,
        code: list[str],
        io: IO,
    ) -> None:
        r"""Pad ``code`` to a square grid, like :func:`run`."""
        if not code or not any(line.strip() for line in code):
            raise ValueError("Dig program cannot be empty")
        self.io = io
        self.size = max(len(lne) for lne in code)
        self.code = tuple(c.ljust(self.size) for c in code)
        self.mole = self.num = self.row = self.col = 0
        self.move = 1
        self._done = False

    @property
    def halted(self) -> bool:
        r"""Whether the mole has halted or left the grid."""
        return self._done

    # The VM's language-shaped view.
    # the instruction position is.
    # -- a bare index would not say.
    # the one value the mole.

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""The mole's ``(row, col, heading)``."""
        return (self.row, self.col, self.move)

    @property
    def memory(self) -> list[int]:
        r"""The value the mole is carrying."""
        return [self.mole]

    @property
    def stack(self) -> list[object]:
        r"""Dig has no stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.row,
            self.col,
            self.move,
            self.mole,
            self.num,
            self.code,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
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
        r"""Write a transition's result back onto the machine's fields."""
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
        r"""Execute the cell under the mole, then move it one cell."""
        if self._done:
            return
        char = self.code[self.row][self.col]

        value: int | None = None
        if self.num and char in "=~":
            temp = self.io.input_str()
            if temp:
                value = ord(temp[0]) if char == "=" else int(temp[0])
        elif self.num and char == ":":
            if self.mole < 10:
                self.io.print_num(self.mole)
            else:
                self.io.print_char(chr(self.mole))

        self._restore(_advance(self._state, self.size, value))


def run(
    code: list[str],
    io: IO,
) -> None:
    r"""Execute a Dig program with mole movement and underground work."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
