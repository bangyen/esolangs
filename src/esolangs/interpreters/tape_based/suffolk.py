"""Interpreter for Suffolk.

``>`` moves right, ``<`` sums the cell into the accumulator and rewinds,
``!`` writes the cell a value from the accumulator clamped at zero, ``,``
reads a byte, ``.`` prints the accumulator minus one; the code reruns
forever.  The wiki has ``,`` read one character with EOF zeroing the
accumulator; this reads a line (first byte) and raises :class:`EOFError`
on exhausted input.  An empty program raises :class:`ValueError`.
:func:`run` stops on a proof -- a repeated state or that ``EOFError`` --
never a pass count; growth with no input to run out of is left to
``esolangs.run``'s ``timeout``.  ``halted`` is ``False`` until a read
exhausts input; a repeated :meth:`_Machine.snapshot` proves a loop.
The transition :func:`_advance` is pure over an immutable ``_State``
(a tuple tape, so ``run`` can put states straight into a set).
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

#: ``(ind, ptr, acc, tape)``: an immutable value, rebound per step.  No
#: halted flag: Suffolk never halts, ``run`` stops on a repeated state or
#: EOF.  The code is a parameter, not a field (``run`` stores one state per step).
type _State = tuple[int, int, int, tuple[int, ...]]


def _advance(state: _State, code: str, byte: int | None = None) -> _State:
    """Return the state after executing one command.

    ``,``'s read and ``.``'s print are the caller's: the read arrives as
    ``byte`` already summed or zeroed.  ``<`` sums and rewinds; ``!`` writes
    the clamped value and clears pointer and accumulator; the cursor wraps.
    """
    ind, ptr, acc, tape = state
    sym = code[ind]
    if sym == ">":
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
    elif sym == "<":
        acc += tape[ptr]
        ptr = 0
    elif sym == "!":
        tape = (*tape[:ptr], max(0, tape[ptr] + 1 - acc), *tape[ptr + 1 :])
        ptr = acc = 0
    elif sym == ",":
        acc = byte if byte is not None else 0
    ind += 1
    return (0 if ind == len(code) else ind, ptr, acc, tape)


class _Machine:
    """Per-run Suffolk state: the code, tape, and accumulator."""

    #: ``while not vm.halted`` never returns; :func:`run` needs no bound
    #: (a reader hits :class:`EOFError`, a non-reader repeats its start state).
    self_halts = False

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and start the tape and accumulator at zero.

        ``code`` must be non-empty.
        """
        if not code:
            raise ValueError("Suffolk program cannot be empty")
        self.io = io
        self.code = code
        self.state: _State = (0, 0, 0, (0,))
        self._exhausted = False

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def acc(self) -> int:
        return self.state[2]

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state[3]

    @property
    def halted(self) -> bool:
        """True once a read has run past the end of the input.

        For a while this was constant ``False`` with the exhausted read escaping
        as :class:`EOFError`, so ``run("Suffolk", p, s)`` returned ``'1'`` while
        ``make_debugger(...).run()`` raised on the same program.  The output is
        complete when the read fires, so exhaustion is a halt on both paths.
        ``self_halts`` stays ``False``: a program that never reads ends only by
        repeating a state.
        """
        return self._exhausted

    # ``_AffineMachine`` (growing-cell hang certificate): control never
    # reads a value, and every write is affine but ``!``'s ``max(0, ...)``,
    # which ``clamp_slack`` exposes.

    @property
    def key(self) -> tuple[int, int, int]:
        """The equality-compared state: cursor, pointer, and tape width."""
        ind, ptr, _acc, tape = self.state
        return (ind, ptr, len(tape))

    @property
    def values(self) -> tuple[int, ...]:
        """The unbounded values: the accumulator, then the cells."""
        _ind, _ptr, acc, tape = self.state
        return (acc, *tape)

    @property
    def clamp_slack(self) -> int | None:
        """``!``'s clamped quantity before it is clamped, else ``None``.

        ``max(0, tape[ptr] + 1 - acc)``: the one place a value steers the machine.
        """
        ind, ptr, acc, tape = self.state
        if self.code[ind] != "!":
            return None
        return tape[ptr] + 1 - acc

    def input_position(self) -> int:
        """Return the input cursor, so a reading loop is not a repeat."""
        return self.io.position()

    # The VM's language-shaped view: Tape + accumulator; ip the cursor, memory the tape.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.state[3])

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        No pass count (it never steers, and would reduce the detector to a step
        budget).  The input cursor is required: without it two generated
        programs that read once more and hit EOF were called periodic.
        """
        ind, ptr, acc, tape = self.state
        return (ind, ptr, acc, tape, self.io.position())

    def step(self) -> None:
        """Execute one command, wrapping to the start at the end of the code.

        ``,`` hands the transition the new accumulator: the sum on a character,
        zero on a blank line (the package convention; the wiki's "at EOF set the
        integer to 0" is about EOF, which still raises).
        """
        if self._exhausted:
            return
        ind, _ptr, acc, _tape = self.state
        sym = self.code[ind]
        byte = None
        if sym == ",":
            # The read past the end of the input is this language's stop,
            # so it ends the machine here rather than escaping to whoever
            # happens to be driving.  Nothing has advanced yet, so the
            # state stays the one that produced the finished output.
            try:
                inp = self.io.input_str()
            except EOFError:
                self._exhausted = True
                return
            byte = acc + ord(inp[0]) if inp else 0
        elif sym == "." and acc:
            self.io.print_char(chr(acc - 1))
        self.state = _advance(self.state, self.code, byte)


def run(code: str, io: IO) -> None:
    """Run a Suffolk program until it repeats a state or runs out of input.

    Both stops are decidable: a reading program hits :class:`EOFError`
    part-way through its second pass, before a second ``.``; a non-reading
    one ends where it began (the generator's tail restores every cell) and
    the repeat proves the loop.  Both *return*: re-raising the exhausted read
    once made ``esolangs.run("Suffolk", ...)`` fail on every generated
    program, the committed example included.  The halt now lives in
    :meth:`_Machine.step`, so every driver agrees.
    """
    machine = _Machine(code, io)
    seen: set[tuple[object, ...]] = set()
    while not machine.halted:
        state = machine.snapshot()
        if state in seen:
            return
        seen.add(state)
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
