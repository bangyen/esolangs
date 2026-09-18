r"""Interpreter for LaserFuck.

A laser starts at ``o`` with a random heading.  ``>``/``<``/``+``/``-``/
``,`` work a brainfuck tape, ``\`` and ``/`` reflect, ``_``/``|`` and
``(``/``)`` reflect when the cell is nonzero (or always), ``^v{}`` set the
heading, ``#`` skips, ``x`` deletes the laser, ``*`` splits it
perpendicular at random.  When no lasers remain the tape is printed:
decimal by default, byte mode (no separators) when the first grid cell is
``\xff``; negative cells are excluded.

The initial heading and every ``*`` split are drawn from ``rng``, so one
argument makes a run reproducible; ``None`` draws for real, as the
cross-check does.  Exhausted input raises :class:`EOFError`.
"""

import sys
from typing import cast

from esolangs.interpreters.io import IO
from esolangs.interpreters.persistent import (
    Chunked,
    append,
    chunked,
    flatten,
    get,
    length,
    prepend,
    put,
)
from esolangs.interpreters.randomness import Randomness, draw

#: One instant of a run: ``(tape, ptr, lsrs, ind, jmp, pos)`` -- the cells
#: with their touched flags, the cell pointer, the live beams as
#: ``(row, col, heading)`` triples, which beam moves next, whether the
#: previous cell was a ``#``, and where the active beam now sits.
#:
#: The beams are the reason this is a list rather than a position: ``*``
#: appends one and ``x`` removes one, so the round-robin index has to
#: survive a store that grows and shrinks under it.
#:
#: The grid is not here -- LaserFuck never writes to its own text -- so a
#: step is handed it rather than carrying it.
type _Beams = tuple[tuple[int, int, int], ...]
type _Tape = Chunked[tuple[int, int]]
type _State = tuple[_Tape, int, _Beams, int, bool, tuple[int, int, int]]

#: One instant as the all-outcomes search sees it: ``_State`` without the
#: reported position, and with ``None`` beams standing for a laser whose
#: heading has not been drawn yet.
type _BranchState = tuple[_Tape, int, _Beams | None, int, bool]

#: The position handed to a transition during a branching search.  Every
#: caller strips the result's copy, so the value only has to be constant.
_NO_POS = (0, 0, 0)


def _strip_pos(state: _State) -> _BranchState:
    """Drop the reported position from a transition's result."""
    tape, ptr, lsrs, ind, jmp, _pos = state
    return (tape, ptr, lsrs, ind, jmp)


def _write(tape: _Tape, ptr: int, value: int, touched: int) -> _Tape:
    """Return ``tape`` with the cell at ``ptr`` set and marked."""
    return put(tape, ptr, (value, touched))


def _move(row: int, col: int, d: int, rows: int) -> tuple[int, int]:
    """Return the cell one step along heading ``d``.

    Off the top or left edge is spelled as a row past the bottom, so a
    leaving beam dies rather than wraps.
    """
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
    """Return the state after the active beam executes ``op``.

    Pure; ``,``'s byte arrives as ``byte`` and ``*``'s coin as ``split``.
    ``x`` renormalises the index rather than advancing it.  ``pos`` is
    carried through untouched: it is the position reported for this step,
    recorded at the arrival heading.
    """
    tape, ptr, lsrs, ind, jmp, pos = state

    if op == ">":
        ptr += 1
        if ptr == length(tape):
            tape = append(tape, (0, 0))
    elif op == "<":
        if ptr > 0:
            ptr -= 1
        else:
            tape = prepend(tape, (0, 0))
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
        if d < 2 and (get(tape, ptr)[0] != 0 or op == "_"):
            d = 1 - d
    elif op in "|)":
        if d > 1 and (get(tape, ptr)[0] != 0 or op == "|"):
            d = 5 - d
    elif op == "/":
        d = 3 - d
    elif op in "^v{}":
        d = "^v{}".find(op)
    elif op == "\\":
        d = (d + 2) % 4
    elif op == "+":
        tape = _write(tape, ptr, get(tape, ptr)[0] + 1, 1)
    elif op == "-":
        tape = _write(tape, ptr, get(tape, ptr)[0] - 1, 1)
    elif op == "#":
        jmp = True

    lsrs = (*lsrs[:ind], (row, col, d), *lsrs[ind + 1 :])
    return (tape, ptr, lsrs, (ind + 1) % len(lsrs), jmp, pos)


class _Machine:
    """A LaserFuck run: the grid, the live lasers, and the tape."""

    #: Whether the tape is written on the step *after* the halt.  It
    #: belongs to the language, not to whoever is stepping it: ``run`` ends
    #: its loop with one more ``step()``, so a caller who stops at
    #: ``halted`` has driven the program correctly and still holds none of
    #: its output.
    #:
    #: The dump lives on the machine rather than in ``run`` because the VM
    #: adapter used to replicate it and drifted: its copy fired on ``not
    #: lsrs`` where ``run`` fires on ``halted``, so a program stopped by a
    #: second start marker printed under one and not the other.
    dumps_on_the_post_halt_step = True

    #: The seed a reproducible run starts from.  It belongs to the
    #: language, not to whoever is stepping it: 2 draws the initial
    #: heading 0, up, which is the direction this language's examples
    #: are written for.
    reproducible_seed = 2

    def __init__(
        self,
        code: list[str],
        io: IO,
        rng: Randomness | None = None,
    ) -> None:
        """Start a laser at ``o``, drawing its heading from ``rng``.

        ``rng`` is the whole source of chance; ``None`` draws for real.
        There is no ``heading`` argument: a source answering the first draw
        does that job and the splits' too.
        """
        self.io = io
        self._rng = rng
        text = [list(ln) for ln in code]
        size = max(len(ln) for ln in text) if text else 0
        self.text = tuple((*ln, *[" "] * (size - len(ln))) for ln in text)
        self.rows = len(text)

        self.ptr = 0
        self.tape: _Tape = chunked(((0, 0),))  # value, touched
        self.jmp = False
        self.ind = 0
        self.pos = (0, 0, 0)
        self._second_start = False
        self._dumped = False
        #: Where the ``o`` marker sits, kept so a branching search can place
        #: the beam itself under each of the four headings.
        self.start = (0, 0)

        # Beams are held as the tuples ``_Beams`` is made of, not as
        # lists.  The list store meant ``_state`` rebuilt every beam as a
        # tuple and ``_restore`` rebuilt every one back as a list, once
        # per step each -- a measured 46% of a run over a long generated
        # program -- to hold a value nothing mutates in place: ``*`` and
        # ``x`` add and drop whole beams, and a moved beam is assigned
        # over, never edited.  The list around them stays, since the
        # round-robin index has to survive that growing and shrinking.
        self.lsrs: list[tuple[int, int, int]] = []
        for row, line in enumerate(self.text):
            for col, c in enumerate(line):
                if c == "o":
                    if self.lsrs:
                        self._second_start = True  # a second marker halts
                        return
                    # The random heading is part of LaserFuck's spec, not a
                    # secret.
                    d = draw(rng, 4)
                    self.start = (row, col)
                    self.lsrs.append((row, col, d))
                    self.pos = (row, col, d)

    @property
    def halted(self) -> bool:
        return self._second_start or not self.lsrs

    # The VM's language-shaped view.  Dumping the tape once the last laser
    # dies is *not* here -- that is what ``run()`` does after the final
    # step, so the VM's adapter drives it rather than ``step()``.

    #: ``ip`` is a cell of the program's own rectangle: the first two
    #: parts are a row and a column, and the rest is a heading.  Without
    #: this a caller cannot tell the pair from a call depth or a frame
    #: stack, which look identical and mean somewhere else entirely.
    ip_shape = "grid"

    @property
    def ip(self) -> tuple[int, ...]:
        """The active laser's ``(row, col, heading)``."""
        return self.pos

    @property
    def memory(self) -> list[int]:
        """The tape's cell values, without their paint flags."""
        return [v for v, _ in flatten(self.tape)]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ptr,
            self.tape,
            self.jmp,
            self.ind,
            tuple(self.lsrs),
            self.io.position(),
        )

    # The all-random-outcomes search.  Its state deliberately drops ``pos``
    # and the input cursor that ``snapshot`` carries: ``pos`` is what the VM
    # reports for a step and no transition ever reads it, so keeping it would
    # split behaviourally identical states, and input is declined below.

    def branching_snapshot(self) -> _BranchState:
        """Return the pre-heading start state for a branching search.

        The initial heading is a draw, so ``None`` marks the beam unplaced
        and :meth:`branching_successors` opens it into the four headings.  A
        grid that never placed a laser reports its own empty beams instead,
        so the ordinary emptiness test halts it.
        """
        unplaced = None if self.lsrs else ()
        return (self.tape, self.ptr, unplaced, self.ind, self.jmp)

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has no live beam left.

        The unplaced start state is never halted; a grid with no laser
        reports empty beams, which this halts on directly.
        """
        lsrs = cast(_BranchState, state)[2]
        return lsrs is not None and not lsrs

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_BranchState, ...] | None:
        """Return the state for every draw this state could make.

        Mirrors :meth:`step`, since the move, off-grid death and ``#`` skip
        live there.  Fanout is two at ``*`` and four at the unplaced start.
        ``,`` returns ``None`` (each branch would need its own input
        cursor), so the caller reports undecided.
        """
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
        """The machine's fields as the value the transition works on."""
        return (
            self.tape,
            self.ptr,
            tuple(self.lsrs),
            self.ind,
            self.jmp,
            self.pos,
        )

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        tape, self.ptr, lsrs, self.ind, self.jmp, self.pos = state
        self.tape = tape
        self.lsrs = list(lsrs)

    def step(self) -> None:
        """Move the active laser one step, dumping the tape once halted.

        The dump is the step after the halt, as in Minsky Swap and RAM0, so
        stepping to a standstill writes what ``run`` writes; the VM adapter
        once dumped on ``not lsrs`` where ``run`` dumped on ``halted``, so a
        program stopped by a second ``o`` printed under one and not the
        other.  ``,``'s line and ``*``'s coin are read here, only when the
        cell under the beam is that command.
        """
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
            # An empty (or blank) input line reads a zero -- the package
            # convention, not the language's.  The wiki says nothing about
            # input at all, and the cross-check is this repo's own harness,
            # so neither sources this value.
            line_val = self.io.input_str()
            byte = ord(line_val[0]) if line_val else 0
        split = draw(self._rng, 2) if op == "*" else 0

        self._restore(_advance(self._state, op, row, col, d, byte, split))

    def dump(self) -> None:
        r"""Print the tape, honoring the ``\xff`` byte-mode marker.

        The wiki says decimal mode prints "with line breaks" and byte mode
        "with no line breaks", so decimal puts a newline *between* values
        (never trailing) -- the spec's separator, unlike the other
        interpreter-only languages' spaces.
        """
        first_row = self.text[0] if self.text else []
        byte_mode = bool(first_row) and first_row[0] == "\u00ff"
        shown = [val for val, touched in flatten(self.tape) if touched and val >= 0]
        for index, val in enumerate(shown):
            if byte_mode:
                self.io.print_char(chr(val))
                continue
            if index:
                self.io.print_str("\n")  # between values, never trailing
            self.io.print_num(val)


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Run a LaserFuck program, printing the tape when it halts.

    ``rng`` supplies the initial direction (``randbelow(4)``: 0=up, 1=down,
    2=left, 3=right) and each ``*`` split; ``None`` draws for real.  Same
    signature as COD.
    """
    machine = _Machine(code, io, rng)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step dumps the tape


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
