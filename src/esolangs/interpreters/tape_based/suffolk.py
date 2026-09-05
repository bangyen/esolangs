"""Interpreter for Suffolk.

> moves right, < sums the current cell into the accumulator and rewinds the
pointer, ! zeroes a cell computed from the accumulator, , reads a byte of
input, and . prints the accumulator minus one.  Execution loops over the
code until the run decides itself; see :func:`run`.

The wiki describes ``,`` as reading one character, with EOF setting the
accumulator to zero; this interpreter reads a whole line (using only its
first byte) and raises :class:`EOFError` on exhausted input instead.  An
empty program is malformed and rejected with :class:`ValueError`.

The wiki's rerun is infinite, so there is no halt to run to.  :func:`run`
used to count whole passes and stop after one, which answered the question
without deciding it: one pass was chosen because the programs were believed
to be finished by then, not shown to be.  It now stops on a *proof* instead
-- a repeated state, or the ``EOFError`` from reading past the end of the
input, whichever the program reaches.  Both are properties of the run, so
nothing is left to choose.  A program that does neither -- cells growing
without bound, and no input to run out of -- runs forever, which is what
``esolangs.run``'s ``timeout`` is for; the interpreter carries no cap of
its own.

The interpreter runs on a :class:`_Machine` (the code, tape, and
accumulator), so it is step-capable: ``step()`` executes one command.  The
language never halts, so ``halted`` is always ``False`` and the budget lives
in :func:`run`'s driver; a repeated :meth:`_Machine.snapshot` is what proves
a program loops, via ``esolangs.vm.run_until_halt_or_cycle``.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the code to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  The
tape is a tuple, so a state is a value that can be stored, compared, and
hashed as it stands -- which matters more here than anywhere else, because
``run`` puts these values straight into a set to prove a repeat.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what Suffolk *does* stays in
the pure layer.  ``,``'s read and ``.``'s print are done by ``step`` before
it calls the pure transition.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, ptr, acc, tape)`` -- the code cursor, the
#: pointer, the accumulator, and the tape.  A value, not a record: every
#: transition below returns a new one rather than editing one in place, and
#: the tape is a ``tuple`` for the same reason.
#:
#: There is no halted flag: Suffolk never halts.  ``run`` stops on a proof
#: -- a repeated state or the EOF from reading past the end of the input --
#: so "stopped" is a fact about the *run*, not about any state.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value ``run`` stores, and
#: it stores one per step until the program repeats.
type _State = tuple[int, int, int, tuple[int, ...]]


def _advance(state: _State, code: str, byte: int | None = None) -> _State:
    """Return the state after executing one command.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so ``,``'s read and ``.``'s print are the caller's business --
    the print changes no state at all, and the read's value arrives as
    ``byte`` already summed onto the accumulator or zeroed.

    ``<`` sums the current cell into the accumulator and rewinds the pointer
    to zero; ``!`` writes a cell computed from the accumulator, clamped at
    zero, and then clears both the pointer and the accumulator.

    The cursor wraps to the start at the end of the code, which is the
    wiki's infinite rerun -- there is no end to reach.
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

    #: Whether the program can reach a halt of its own.  It belongs to the
    #: language, not to whoever is stepping it: the wiki's rerun is
    #: infinite, so ``while not vm.halted: vm.step()`` never returns.  A
    #: caller stepping this one has to bound the run itself -- with a hang
    #: detector, or :func:`esolangs.run`'s ``timeout``.
    #:
    #: :func:`run` stops it from outside, and takes no bound to do it: a
    #: program that reads hits :class:`EOFError` past the end of its input,
    #: and one that reads nothing returns to the state it began in.
    self_halts = False

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and start the tape and accumulator at zero.

        ``code`` must be non-empty; an empty program is malformed.
        """
        if not code:
            raise ValueError("Suffolk program cannot be empty")
        self.io = io
        self.code = code
        self.state: _State = (0, 0, 0, (0,))

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
        """The wiki's rerun never halts; only a repeated state proves a loop."""
        return False

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

        The pass count is deliberately absent: it never steers ``step()``, so
        two states that differ only in how many passes preceded them run
        identically from here on.  Counting it would make every state unique
        by construction and reduce the cycle detector to a step budget --
        Suffolk's programs are periodic, and this is what lets that be proved.

        The input cursor, by contrast, is *not* optional, and leaving it out
        was a soundness bug.  ``,`` reads a byte, so two states with the same
        tape but different input remaining do not run identically -- one has
        a byte left to consume and the other raises.  Without the cursor the
        detector called two boolean-generator programs periodic when they in
        fact read once more and hit EOF, which is a hang reported where none
        exists.
        """
        ind, ptr, acc, tape = self.state
        return (ind, ptr, acc, tape, self.io.position())

    def step(self) -> None:
        """Execute one command, wrapping to the start at the end of the code.

        The two I/O commands are here rather than in the transition: this
        is the shell, so it is where an effect belongs.  ``,`` reads a line
        and hands the transition what the accumulator should become -- the
        sum when there was a character, and zero on a blank line, which is
        the rule the original spelled inline.
        """
        ind, _ptr, acc, _tape = self.state
        sym = self.code[ind]
        byte = None
        if sym == ",":
            inp = self.io.input_str()
            byte = acc + ord(inp[0]) if inp else 0
        elif sym == "." and acc:
            self.io.print_char(chr(acc - 1))
        self.state = _advance(self.state, self.code, byte)


def run(code: str, io: IO) -> None:
    """Run a Suffolk program until it repeats a state or runs out of input.

    The wiki's rerun is infinite, so a program is stopped from outside --
    but not by *counting*.  Both of the things a generated program does are
    decidable stops in their own right:

    * a program that reads runs out of input, and ``,`` raises
      :class:`EOFError` on the read past the end.  That fires part-way
      through the second pass, before the ``.`` that would print a second
      answer, so the output is the one the program computed from its real
      input.
    * a program that reads nothing ends where it began -- the text
      generator appends a tail that puts every cell back -- so its state
      repeats, and the repeat proves the loop at the end of the first pass,
      with the output written once.

    A program that does neither -- cells growing without bound, and no input
    to run out of -- runs forever, and that is left to the caller: it is
    what :func:`esolangs.run`'s ``timeout`` is for.  A step cap here would
    be a second bound at the wrong layer, and no other interpreter carries
    one except the OISCs, whose self-modifying memory rules out proving a
    loop from a repeated state at all.
    """
    machine = _Machine(code, io)
    seen: set[tuple[object, ...]] = set()
    while True:
        state = machine.snapshot()
        if state in seen:
            return
        seen.add(state)
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
