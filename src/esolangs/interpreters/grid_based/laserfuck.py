r"""Interpreter for LaserFuck."""

import sys
from typing import cast

from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw

# : One instant of a run:.
# : with their touched flags,.
# : ``(row, col, heading)``.
# : previous cell was a ``#``,.
# :.
# : The beams are the reason.
# : appends one and ``x``.
# : survive a store that grows.
# :.
# : The grid is not here --.
# : step is handed it rather.
type _Beams = tuple[tuple[int, int, int], ...]
type _Tape = tuple[tuple[int, int], ...]
type _State = tuple[_Tape, int, _Beams, int, bool, tuple[int, int, int]]

# : One instant as the.
# : reported position, and with.
# : heading has not been drawn.
type _BranchState = tuple[_Tape, int, _Beams | None, int, bool]

# : The position handed to a.
# : caller strips the result's.
_NO_POS = (0, 0, 0)


def _strip_pos(state: _State) -> _BranchState:
    r"""Drop the reported position from a transition's result."""
    tape, ptr, lsrs, ind, jmp, _pos = state
    return (tape, ptr, lsrs, ind, jmp)


def _write(tape: _Tape, ptr: int, value: int, touched: int) -> _Tape:
    r"""Return ``tape`` with the cell at ``ptr`` set and marked."""
    return (*tape[:ptr], (value, touched), *tape[ptr + 1 :])


def _move(row: int, col: int, d: int, rows: int) -> tuple[int, int]:
    r"""Return the cell one step along heading ``d``."""
    if (row == 0 and d == 0) or (col == 0 and d == 2):
        return (rows, col)
    if d == 0:
        return (row - 1, col)
    if d == 1:
        return (row + 1, col)
    if d == 2:
        return (row, col - 1)
    return (row, col + 1)


def _advance(
    state: _State,
    op: str,
    row: int,
    col: int,
    d: int,
    byte: int | None = None,
    split: int = 0,
) -> _State:
    r"""Return the state after the active beam executes ``op``."""
    tape, ptr, lsrs, ind, jmp, pos = state

    if op == ">":
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, (0, 0))
    elif op == "<":
        if ptr > 0:
            ptr -= 1
        else:
            tape = ((0, 0), *tape)
    elif op == ",":
        tape = _write(tape, ptr, byte if byte is not None else 0, 1)
    elif op == "x":
        lsrs = (*lsrs[:ind], *lsrs[ind + 1 :])
        if lsrs:
            ind %= len(lsrs)
        return (tape, ptr, lsrs, ind, jmp, pos)
    elif op == "*":
        lsrs = (*lsrs, (row, col, 2 * (1 - d // 2) + split))
    elif op in "_(":
        if d < 2 and (tape[ptr][0] != 0 or op == "_"):
            d = 1 - d
    elif op in "|)":
        if d > 1 and (tape[ptr][0] != 0 or op == "|"):
            d = 5 - d
    elif op == "/":
        d = 3 - d
    elif op in "^v{}":
        d = "^v{}".find(op)
    elif op == "\\":
        d = (d + 2) % 4
    elif op == "+":
        tape = _write(tape, ptr, tape[ptr][0] + 1, 1)
    elif op == "-":
        tape = _write(tape, ptr, tape[ptr][0] - 1, 1)
    elif op == "#":
        jmp = True

    lsrs = (*lsrs[:ind], (row, col, d), *lsrs[ind + 1 :])
    return (tape, ptr, lsrs, (ind + 1) % len(lsrs), jmp, pos)


class _Machine:
    r"""A LaserFuck run: the grid, the live lasers, and the tape."""

    # : Whether the tape is written.
    # : belongs to the language,.
    # : its loop with one more.
    # : ``halted`` has driven the.
    #: its output.
    # :.
    # : The dump lives on the.
    # : adapter used to replicate.
    # : lsrs`` where ``run`` fires.
    # : second start marker printed.
    dumps_on_the_post_halt_step = True

    # : The seed a reproducible run.
    # : language, not to whoever is.
    # : heading 0, up, which is the.
    #: are written for.
    reproducible_seed = 2

    def __init__(
        self,
        code: list[str],
        io: IO,
        rng: Randomness | None = None,
    ) -> None:
        r"""Start a laser at ``o``, drawing its heading from ``rng``."""
        self.io = io
        self._rng = rng
        text = [list(ln) for ln in code]
        size = max(len(ln) for ln in text) if text else 0
        self.text = tuple((*ln, *[" "] * (size - len(ln))) for ln in text)
        self.rows = len(text)

        self.ptr = 0
        self.tape: _Tape = ((0, 0),)  # value, touched.
        self.jmp = False
        self.ind = 0
        self.pos = (0, 0, 0)
        self._second_start = False
        self._dumped = False
        # : Where the ``o`` marker.
        # : the beam itself under each.
        self.start = (0, 0)

        # Beams are held as the tuples.
        # lists.
        # tuple and ``_restore``.
        # per step each -- a measured.
        # program -- to hold a value.
        # ``x`` add and drop whole.
        # over, never edited.
        # round-robin index has to.
        self.lsrs: list[tuple[int, int, int]] = []
        for row, line in enumerate(self.text):
            for col, c in enumerate(line):
                if c == "o":
                    if self.lsrs:
                        self._second_start = True  # a second marker halts.
                        return
                    # The random heading is part of.
                    # secret.
                    d = draw(rng, 4)
                    self.start = (row, col)
                    self.lsrs.append((row, col, d))
                    self.pos = (row, col, d)

    @property
    def halted(self) -> bool:
        return self._second_start or not self.lsrs

    # The VM's language-shaped view.
    # dies is *not* here -- that is.
    # step, so the VM's adapter.

    # : ``ip`` is a cell of the.
    # : parts are a row and a.
    # : this a caller cannot tell.
    # : stack, which look identical.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""The active laser's ``(row, col, heading)``."""
        return self.pos

    @property
    def memory(self) -> list[int]:
        r"""The tape's cell values, without their paint flags."""
        return [v for v, _ in self.tape]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.ptr,
            self.tape,
            self.jmp,
            self.ind,
            tuple(self.lsrs),
            self.io.position(),
        )

    # The all-random-outcomes.
    # and the input cursor that.
    # reports for a step and no.
    # split behaviourally identical.

    def branching_snapshot(self) -> _BranchState:
        r"""Return the pre-heading start state for a branching search."""
        unplaced = None if self.lsrs else ()
        return (self.tape, self.ptr, unplaced, self.ind, self.jmp)

    def branching_halted(self, state: object) -> bool:
        r"""Report whether ``state`` has no live beam left."""
        lsrs = cast(_BranchState, state)[2]
        return lsrs is not None and not lsrs

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_BranchState, ...] | None:
        r"""Return the state for every draw this state could make."""
        tape, ptr, lsrs, ind, jmp = cast(_BranchState, state)
        if lsrs is None:
            return tuple(
                (tape, ptr, ((self.start[0], self.start[1], d),), ind, jmp)
                for d in range(4)
            )

        row, col, d = lsrs[ind]
        row, col = _move(row, col, d, self.rows)

        if jmp:
            moved = (*lsrs[:ind], (row, col, d), *lsrs[ind + 1 :])
            return ((tape, ptr, moved, (ind + 1) % len(moved), False),)

        op = (
            self.text[row][col]
            if 0 <= row < self.rows and 0 <= col < len(self.text[0])
            else "x"
        )
        if op == ",":
            return None

        splits = (0, 1) if op == "*" else (0,)
        return tuple(
            _strip_pos(
                _advance(
                    (tape, ptr, lsrs, ind, jmp, _NO_POS),
                    op,
                    row,
                    col,
                    d,
                    None,
                    split,
                )
            )
            for split in splits
        )

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (
            self.tape,
            self.ptr,
            tuple(self.lsrs),
            self.ind,
            self.jmp,
            self.pos,
        )

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        tape, self.ptr, lsrs, self.ind, self.jmp, self.pos = state
        self.tape = tape
        self.lsrs = list(lsrs)

    def step(self) -> None:
        r"""Move the active laser one step, dumping the tape once halted."""
        if self.halted:
            if not self._dumped:
                self.dump()
                self._dumped = True
            return
        row, col, d = self.lsrs[self.ind]
        row, col = _move(row, col, d, self.rows)
        self.pos = (row, col, d)

        if self.jmp:
            self.jmp = False
            self.lsrs[self.ind] = (row, col, d)
            self.ind = (self.ind + 1) % len(self.lsrs)
            return

        op = (
            self.text[row][col]
            if 0 <= row < self.rows and 0 <= col < len(self.text[0])
            else "x"
        )

        byte = None
        if op == ",":
            # An empty (or blank) input.
            # convention, not the.
            # input at all, and the.
            # so neither sources this value.
            line_val = self.io.input_str()
            byte = ord(line_val[0]) if line_val else 0
        split = draw(self._rng, 2) if op == "*" else 0

        self._restore(_advance(self._state, op, row, col, d, byte, split))

    def dump(self) -> None:
        r"""Print the tape, honoring the ``\xff`` byte-mode marker."""
        first_row = self.text[0] if self.text else []
        byte_mode = bool(first_row) and first_row[0] == "\u00ff"
        shown = [val for val, touched in self.tape if touched and val >= 0]
        for index, val in enumerate(shown):
            if byte_mode:
                self.io.print_char(chr(val))
                continue
            if index:
                self.io.print_str("\n")  # between values, never.
            self.io.print_num(val)


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    r"""Run a LaserFuck program, printing the tape when it halts."""
    machine = _Machine(code, io, rng)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step dumps the.


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
