"""Interpreter for %^2^-1.

A single accumulator holding the magnitude ``x`` of a value ``10^x`` (the
wiki's workaround for avoiding huge numbers; the magnitude starts at 0).
``s``/``i`` subtract 2/3 (divide by 100/1000), ``m`` doubles (square), ``p``
negates (reciprocate), ``'`` zeroes it (set to 1), ``l``/``e`` print it
(decimal / as a byte), ``n`` reads one byte of input, and ``t`` rewinds to
the start of the program when the magnitude is nonzero.  The magnitude is
reset to zero whenever it exceeds 3003 (before each command).

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and a command to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.

The state is two integers, so it is already a value that can be stored,
compared, and hashed as it stands -- which is what ``snapshot`` returns
directly rather than rebuilding.  Unlike the brainfuck tape there is
nothing to copy, so the immutability costs nothing here.

:class:`_Machine` is the mutable shell the interpreter protocol requires
(``esolangs.vm`` wraps it and ``run_until_halt_or_cycle`` steps it).  It
holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what %^2^-1 *does* stays in the
pure layer.  The effects three commands have -- ``l``/``e``'s printing and
``n``'s read -- are done by ``step`` before it calls the pure transition:
effects in the shell, rules in the core.

Semantics:
- ``e`` prints the low byte, and ``l`` prints the signed magnitude;
- ``n`` raises :class:`EOFError` when input runs out, where the cross-check
  exits with status 3;
- ``t`` on a nonzero magnitude loops the program forever (the only loop).
"""

from __future__ import annotations

import sys

from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, acc)`` -- the code position and the
#: accumulator.  A value, not a record: every transition below returns a new
#: one rather than editing one in place.
#:
#: This is exactly what ``snapshot`` returns, and always has been.  The
#: state and its hashable view are the same tuple, so unlike brainfuck --
#: whose tape needs committing before an observer may see it -- there is no
#: second spelling of a logical state for the cycle detector to trip over.
#:
#: A plain tuple rather than a ``NamedTuple``: the two fields are read by
#: unpacking in the functions that use them, so the names buy little, and
#: ``NamedTuple.__new__`` is Python-level where the tuple constructor is
#: C-level.
#:
#: The code is deliberately *not* in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
type _State = tuple[int, int]


def _reset(state: _State) -> _State:
    """Return ``state`` with an over-3003 accumulator zeroed.

    The magnitude is clamped before each command, and both the transition
    and the shell's prints need the clamped value, so the rule is defined
    here once rather than spelled out in each of them.
    """
    ind, acc = state
    return (ind, 0) if acc > 3003 else state


def _advance(state: _State, code: str) -> _State:
    """Return the state after executing the command at the code position.

    Pure: it reads ``state`` and returns a new one, and every command that
    is not I/O is decided entirely here.  It takes no ``io`` argument, so
    ``l``, ``e``, and ``n`` are necessarily the caller's business; this
    function sees only what they leave behind -- the two prints change no
    state at all, and ``n``'s byte arrives already in the accumulator.

    The over-3003 reset is applied *before* the command, which is where the
    original loop applied it: a command reads the already-reset accumulator,
    so ``m`` on 4000 doubles 0, not 4000.  :func:`_reset` is the single
    definition of that rule -- the shell calls it too, because the prints
    must report the same reset value this transition will act on.

    ``t`` is the one command that does not fall through to the shared
    increment -- on a nonzero accumulator it rewinds to position 0, and
    position 0 is where the next command must be read from, not 1.  On a
    zero accumulator it is inert and advances like anything else.

    Anything that is not a command is a comment and falls through to the
    shared increment, which is what makes the code position advance exactly
    once per call.
    """
    ind, acc = _reset(state)
    char = code[ind]
    if char == "s":
        acc -= 2
    elif char == "i":
        acc -= 3
    elif char == "m":
        acc *= 2
    elif char == "p":
        acc *= -1
    elif char == "'":
        acc = 0
    elif char == "t" and acc != 0:
        # The rewind lands on position 0 and is read from there next step,
        # so it returns directly rather than taking the increment below.
        return (0, acc)
    return (ind + 1, acc)


class _Machine:
    """A %^2^-1 run: one immutable ``_State``, rebound per step.

    The protocol the rest of the library expects (``step``, ``halted``,
    ``snapshot``, and the ``ind``/``acc`` attributes) is mutable by
    construction, so this class supplies it.  All it does is hold the
    current state and the two constants a transition needs; the rules
    themselves are the pure function above.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and start the accumulator at zero."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here
        # rather than recomputed on every one of those reads.
        self.size = len(code)
        self.state: _State = (0, 0)

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def acc(self) -> int:
        return self.state[1]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: Accumulator + cursor; ip the cursor, memory the
    # accumulator.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.state[1]]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The state as it stands: it is already the (ind, acc) pair this
        # returned before the split, and it is already hashable.
        return self.state

    def step(self) -> None:
        """Execute one command, resetting the accumulator first if too large.

        The three I/O commands are done here rather than in a function of
        their own: this is the shell, so it is where an effect belongs, and
        it keeps :func:`_advance` reachable in one call per step.  ``l`` and
        ``e`` write and change no state; ``n`` reads and leaves the byte in
        the accumulator, so the pure transition then runs on what they left
        behind and never needs the ``io`` object at all.

        The prints must report the *reset* accumulator, since they read it
        before :func:`_advance` runs, so this goes through :func:`_reset`
        first -- the same function the transition uses, rather than a second
        copy of the rule.
        """
        if self.state[0] >= self.size:
            return
        state = _reset(self.state)
        ind, acc = state
        char = self.code[ind]
        if char == "l":
            self.io.print_num(acc)
        elif char == "e":
            self.io.print_char(chr(acc & 0xFF))
        elif char == "n":
            state = (ind, self.io.input_char())
        self.state = _advance(state, self.code)


def run(code: str, io: IO) -> None:
    """Run a %^2^-1 program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
