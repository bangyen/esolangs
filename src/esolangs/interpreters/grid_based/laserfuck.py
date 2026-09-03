r"""Interpreter for LaserFuck.

A laser (starting at ``o`` with a random initial heading) travels a grid.
``>``/``<``/``+``/``-``/``,`` work on a brainfuck-style tape, ``\`` and ``/``
reflect the laser, ``_``/``|`` and ``(``/``)`` reflect it when the current
cell is nonzero (or always for the unconditional forms), ``^v{}`` set the
heading directly, ``#`` skips the next command, ``x`` deletes the laser, and
``*`` duplicates it in a random perpendicular direction.  Execution ends when
no lasers remain; the tape is then printed, with the first grid cell ``\xff``
selecting byte mode (no separators) over the default decimal mode, and
negative cells excluded from the output.

The initial heading is chosen uniformly at random, matching the cross-check;
a run may therefore produce one of several outputs, so tests set a fixed
heading through :func:`run`.


Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys

from esolangs.interpreters.io import IO
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
type _Tape = tuple[tuple[int, int], ...]
type _State = tuple[_Tape, int, _Beams, int, bool, tuple[int, int, int]]


def _write(tape: _Tape, ptr: int, value: int, touched: int) -> _Tape:
    """Return ``tape`` with the cell at ``ptr`` set and marked."""
    return (*tape[:ptr], (value, touched), *tape[ptr + 1 :])


def _move(row: int, col: int, d: int, rows: int) -> tuple[int, int]:
    """Return the cell one step along heading ``d``.

    Stepping off the top or left edge is spelled as a row past the bottom,
    which the grid read then treats as off-grid -- the same fate as any
    other exit, and what makes a beam that leaves die rather than wrap.
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

    Pure: it reads ``state`` and returns a new one.  ``,``'s byte arrives
    as ``byte``, and ``*``'s coin as ``split``, so the two things a step
    cannot decide for itself are decided by the caller.

    ``x`` kills the active beam, which is why the index is renormalised
    rather than advanced: the beam that was next has just shifted down one.
    Every other command hands the turn on in round-robin order.

    ``pos`` is carried through untouched.  It is the position the VM
    reports for *this* step, recorded by the caller at the arrival heading,
    so a turn steers the beam without rewriting where it just was.
    """
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
    """A LaserFuck run: the grid, the live lasers, and the tape."""

    #: The seed a reproducible run starts from.  It belongs to the
    #: language, not to whoever is stepping it: 2 draws the initial
    #: heading 0, up, which is the direction this language's examples
    #: are written for.
    reproducible_seed = 2

    def __init__(
        self,
        code: list[str],
        io: IO,
        heading: int | None = None,
        rng: Randomness | None = None,
    ) -> None:
        """Start a laser at ``o``, heading ``heading`` if one is given.

        ``heading`` pins only the *initial* direction.  ``*`` splits a beam
        with a fresh draw every time it runs, so reproducible stepping
        needs ``rng`` as well; ``None`` draws for real.
        """
        self.io = io
        self._rng = rng
        text = [list(ln) for ln in code]
        size = max(len(ln) for ln in text) if text else 0
        self.text = [ln + [" "] * (size - len(ln)) for ln in text]
        self.rows = len(text)

        self.ptr = 0
        self.tape: _Tape = ((0, 0),)  # value, touched
        self.jmp = False
        self.ind = 0
        self.pos = (0, 0, 0)
        self._second_start = False
        self._dumped = False

        self.lsrs: list[list[int]] = []
        for row, line in enumerate(self.text):
            for col, c in enumerate(line):
                if c == "o":
                    if self.lsrs:
                        self._second_start = True  # a second marker halts
                        return
                    # The random heading is part of LaserFuck's spec, not a
                    # secret.
                    d = heading if heading is not None else draw(rng, 4)
                    self.lsrs.append([row, col, d])
                    self.pos = (row, col, d)

    @property
    def halted(self) -> bool:
        return self._second_start or not self.lsrs

    # The VM's language-shaped view.  Dumping the tape once the last laser
    # dies is *not* here -- that is what ``run()`` does after the final
    # step, so the VM's adapter drives it rather than ``step()``.

    @property
    def ip(self) -> tuple[int, ...]:
        """The active laser's ``(row, col, heading)``."""
        return self.pos

    @property
    def memory(self) -> list[int]:
        """The tape's cell values, without their paint flags."""
        return [v for v, _ in self.tape]

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
            tuple(tuple(laser) for laser in self.lsrs),
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (
            self.tape,
            self.ptr,
            tuple((r, c, d) for r, c, d in self.lsrs),
            self.ind,
            self.jmp,
            self.pos,
        )

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- ``dump`` walks the
        tape and the VM reads the beams -- so they stay; the one assignment
        a step makes is here rather than in the rules above.
        """
        tape, self.ptr, lsrs, self.ind, self.jmp, self.pos = state
        self.tape = tape
        self.lsrs = [list(laser) for laser in lsrs]

    def step(self) -> None:
        """Move the active laser one step, dumping the tape once halted.

        The dump belongs to the step *after* the halt, as Minsky Swap and
        RAM0 already spell it, so that stepping a machine to a standstill
        writes what ``run`` writes.  Keeping it in ``run`` instead left the
        VM adapter to replicate it, and the two had drifted: the adapter
        dumped on ``not lsrs`` where ``run`` dumps on ``halted``, so a
        program stopped by the second start marker printed its tape under
        ``run`` and nothing at all under the VM.  Guarding on ``halted``
        covers both ways of stopping, and ``lsrs`` is the wrong test
        besides -- a beam splitter appends to it, so it grows as well as
        shrinks.

        The two things a step cannot decide for itself are decided here:
        ``,`` takes a line from the input port, and ``*`` draws the coin
        that picks the new beam's heading.  Both are read only when the
        cell under the beam is actually that command.
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
            self.lsrs[self.ind] = [row, col, d]
            self.ind = (self.ind + 1) % len(self.lsrs)
            return

        op = (
            self.text[row][col]
            if 0 <= row < self.rows and 0 <= col < len(self.text[0])
            else "x"
        )

        byte = None
        if op == ",":
            # an empty (or blank) input line reads a zero, per the cross-check
            line_val = self.io.input_str()
            byte = ord(line_val[0]) if line_val else 0
        split = draw(self._rng, 2) if op == "*" else 0

        self._restore(_advance(self._state, op, row, col, d, byte, split))

    def dump(self) -> None:
        r"""Print the tape, honoring the ``\xff`` byte-mode marker.

        The separator is the spec's, not a house style: the wiki says the
        used cells print "in decimal with line breaks", and that a leading
        ``\xff`` "outputs unicode with no line breaks".  So decimal mode
        puts a newline *between* values (never a trailing one) and byte mode
        runs the characters together.  The other interpreter-only languages
        here space-separate their dumps, but their specs say nothing about
        output at all; this one does.
        """
        first_row = self.text[0] if self.text else []
        byte_mode = bool(first_row) and first_row[0] == "\u00ff"
        shown = [val for val, touched in self.tape if touched and val >= 0]
        for index, val in enumerate(shown):
            if byte_mode:
                self.io.print_char(chr(val))
                continue
            if index:
                self.io.print_str("\n")  # between values, never trailing
            self.io.print_num(val)


def run(code: list[str], io: IO, heading: int | None = None) -> None:
    """Run a LaserFuck program, printing the tape when it halts.

    ``heading`` forces the laser's initial direction (0=up, 1=down, 2=left,
    3=right); when None it is drawn uniformly at random, matching the
    cross-check.
    """
    machine = _Machine(code, io, heading)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step dumps the tape


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
