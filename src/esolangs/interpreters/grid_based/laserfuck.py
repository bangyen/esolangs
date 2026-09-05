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
a run may therefore produce one of several outputs, so a caller that needs a
particular one passes an ``rng`` whose first draw is the heading it wants.
That source also decides each ``*`` split, so one argument makes the whole
run reproducible.


Exhausted input raises :class:`EOFError` (the repo-wide convention).
"""

import sys
from typing import cast

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

        ``rng`` is the language's whole source of chance: the initial
        heading here, and the coin ``*`` flips every time it splits a beam.
        ``None`` draws for real, which is the spec's behaviour.

        There is deliberately no ``heading`` argument.  One existed, pinning
        the initial direction so a test could choose it -- but a source that
        answers the first draw does the same thing, and does it for the
        splits too, so the two mechanisms were one job.  A caller wanting a
        particular direction hands in a stub that returns it.
        """
        self.io = io
        self._rng = rng
        text = [list(ln) for ln in code]
        size = max(len(ln) for ln in text) if text else 0
        self.text = tuple((*ln, *[" "] * (size - len(ln))) for ln in text)
        self.rows = len(text)

        self.ptr = 0
        self.tape: _Tape = ((0, 0),)  # value, touched
        self.jmp = False
        self.ind = 0
        self.pos = (0, 0, 0)
        self._second_start = False
        self._dumped = False
        #: Where the ``o`` marker sits, kept so a branching search can place
        #: the beam itself under each of the four headings.
        self.start = (0, 0)

        self.lsrs: list[list[int]] = []
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

    # The all-random-outcomes search.  Its state deliberately drops ``pos``
    # and the input cursor that ``snapshot`` carries: ``pos`` is what the VM
    # reports for a step and no transition ever reads it, so keeping it would
    # split behaviourally identical states, and input is declined below.

    def branching_snapshot(self) -> _BranchState:
        """Return the pre-heading start state for a branching search.

        The initial heading is a draw like any other, so it belongs to the
        search rather than to the machine that starts it: a verdict of "every
        sequence of draws runs forever" has to quantify over all four
        headings, and a live machine has already committed to one.  ``None``
        marks the beam as unplaced, and :meth:`branching_successors` opens it
        into the four headings ``__init__`` chooses between.

        A grid that never placed a laser -- no ``o``, or the second ``o``
        that stops a run at construction -- has no heading to quantify over,
        so it reports its own empty beams instead and the ordinary
        emptiness test halts it.  Handing those the sentinel would invent a
        beam at the grid's origin and search a run the language never has.
        """
        unplaced = None if self.lsrs else ()
        return (self.tape, self.ptr, unplaced, self.ind, self.jmp)

    def branching_halted(self, state: object) -> bool:
        """Report whether ``state`` has no live beam left.

        The unplaced start state is never halted: :meth:`branching_snapshot`
        only spells a beam ``None`` when there is one to place, so an
        unplaced state always has a whole run ahead of it.  A grid with no
        laser reports empty beams instead, which this halts on directly.
        """
        lsrs = cast(_BranchState, state)[2]
        return lsrs is not None and not lsrs

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_BranchState, ...] | None:
        """Return the state for every draw this state could make.

        Mirrors :meth:`step` rather than :func:`_advance` alone, because the
        move, the off-grid death and the ``#`` skip all live in the step: a
        successor calling the transition directly would execute the cell the
        beam is leaving instead of the one it arrives at.

        Fanout is two at a ``*`` and four at the unplaced start, so ``limit``
        needs no consulting here -- the caller's cap on distinct states is
        what bounds the search.  ``,`` returns ``None``: forking it would need
        an independent input cursor per branch, so the caller reports an
        undecided result rather than sharing one branch's input with another.
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


def run(code: list[str], io: IO, rng: Randomness | None = None) -> None:
    """Run a LaserFuck program, printing the tape when it halts.

    ``rng`` supplies every choice the language makes: the laser's initial
    direction (drawn as ``randbelow(4)`` -- 0=up, 1=down, 2=left, 3=right)
    and each ``*`` split.  ``None`` draws for real, matching the
    cross-check, so the public behaviour is the spec's.

    This is the same signature COD and WII2D take, for the same reason: a
    language with a random instruction accepts the source of it, and a
    caller that needs a particular outcome supplies one that decides.
    """
    machine = _Machine(code, io, rng)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step dumps the tape


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.readlines(), IO())
