"""Interpreter for Unsquare.

A stack-based language with an accumulator.  ``O``/``I`` push 0/1, ``A``
pops the stack into the accumulator, ``S`` swaps the top two, ``+``/``-``/
``x`` add 2/subtract 2/double the accumulator, ``P`` pushes it, ``o`` prints
the top of the stack (without popping) as a character -- or as a decimal
value when it is not a valid code point -- and ``i`` reads a line of input,
re-prompting on blank lines, and pushes its first character.  ``>``/``<``
are a loop bracket pair: ``>`` skips forward to the matching ``<`` when the
accumulator is 0 or 1, otherwise it records its position and ``<`` jumps
back to it.

Semantics:
- an empty-stack pop, a swap with fewer than two elements, an ``o`` on an
  empty stack, an unmatched ``<``, or a ``>`` with no matching ``<`` raise
  :class:`HaltError` (the cross-check exits with status 3);
- ``i`` raises :class:`EOFError` when input runs out, where the cross-check
  exits with status 3;
- ``i`` re-prompts on blank input lines.

The interpreter runs on a :class:`_Machine` (the stack, jump-return stack,
accumulator, and code cursor), so it is step-capable: ``step()`` executes
one command and ``halted`` is true once the cursor reaches the end of the
program.  A ``>``/``<`` loop whose body leaves the accumulator, stack, and
jump stack exactly as they were (e.g. ``><`` with the accumulator outside
``{0, 1}``) is a genuine state cycle a repeated :meth:`_Machine.snapshot`
proves; a loop that keeps pushing to the stack is unbounded growth and
needs the wall-clock backstop instead.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the code to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  Both
stacks are tuples, so a state is a value that can be stored, compared, and
hashed as it stands.

Keeping the transition total takes two pieces here, because Unsquare has
five ways to fail.  :func:`_needs` says how many stack elements a command
requires, so the shell can reject an underflow before calling the
transition; and :func:`_forward` returns ``None`` for a ``>`` with no
matching ``<``, so the shell turns that into the error rather than the
transition raising mid-scan.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what Unsquare *does* stays in
the pure layer.
"""

from __future__ import annotations

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

#: The largest value ``o`` can print as a character, and the surrogate range
#: it must not hand to ``chr``.  Anything else prints as a decimal instead.
_MAX_CHAR = 0x10FFFF
_SURROGATES = range(0xD800, 0xE000)

#: How many stack elements each command needs to run.  ``S`` is the only
#: one that needs two; the other two need one.  A command absent from
#: this mapping needs none.
_NEEDS = {"A": 1, "o": 1, "S": 2}

#: One instant of a run: ``(ind, acc, stack, jumps)`` -- the code cursor,
#: the accumulator, the data stack, and the jump-return stack.  A value, not
#: a record: every transition below returns a new one rather than editing
#: one in place, and both stacks are tuples for the same reason.
#:
#: The jump stack is state, not a scratch register: a ``<`` reads the
#: position a matching ``>`` pushed, so two runs sitting on the same command
#: with different jump stacks will go different places next.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
type _State = tuple[int, int, tuple[int, ...], tuple[int, ...]]


def _needs(char: str) -> int:
    """Return how many stack elements ``char`` requires to run."""
    return _NEEDS.get(char, 0)


def _forward(code: str, ind: int) -> int | None:
    """Return the position of the ``<`` matching the ``>`` at ``ind``.

    ``None`` when the bracket is unmatched, which the caller turns into a
    :class:`HaltError` -- returning it rather than raising is what keeps
    the transition below free of error cases.
    """
    depth = 1
    while depth:
        ind += 1
        if ind >= len(code):
            return None
        if code[ind] == ">":
            depth += 1
        elif code[ind] == "<":
            depth -= 1
    return ind


def _advance(
    state: _State,
    code: str,
    byte: int | None = None,
    target: int | None = None,
) -> _State:
    """Return the state after executing the command at the cursor.

    Pure, and total: the shell has already rejected the stack underflows,
    read any input character, and resolved any forward jump, so every
    command it can be handed has a defined successor state.  It takes no
    ``io`` argument, so ``o`` and ``i`` are the caller's business -- ``o``
    changes no state at all, and ``i``'s character arrives as ``byte``.

    ``>`` records ``ind - 1`` rather than ``ind``, so the shared increment
    below leaves the jump stack holding one *before* the bracket; ``<``
    then pops that and the increment lands back on the ``>`` to re-test it.

    Anything that is not a command is a comment and falls through to the
    shared increment.
    """
    ind, acc, stack, jumps = state
    char = code[ind]
    if char == "O":
        stack = (*stack, 0)
    elif char == "I":
        stack = (*stack, 1)
    elif char == "A":
        acc, stack = stack[-1], stack[:-1]
    elif char == "S":
        stack = (*stack[:-2], stack[-1], stack[-2])
    elif char == "+":
        acc += 2
    elif char == "-":
        acc -= 2
    elif char == "x":
        acc *= 2
    elif char == "P":
        stack = (*stack, acc)
    elif char == "i":
        stack = (*stack, byte if byte is not None else 0)
    elif char == ">":
        # The accumulator decides: 0 or 1 skips the loop, anything else
        # enters it and records where to come back to.
        if acc in (0, 1):
            ind = target if target is not None else ind
        else:
            jumps = (*jumps, ind - 1)
    elif char == "<":
        ind, jumps = jumps[-1], jumps[:-1]
    return (ind + 1, acc, stack, jumps)


class _Machine:
    """Per-run Unsquare state: the stack, jump stack, accumulator, cursor.

    ``step()`` executes one command; ``halted`` is true once the cursor
    reaches the end of the program.  The state-cycle hang detector and the
    VM expose this object.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with empty stacks, a zero accumulator, at the first token."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = (0, 0, (), ())

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def acc(self) -> int:
        return self.state[1]

    @property
    def stack(self) -> tuple[int, ...]:
        """The data stack, bottom first."""
        return self.state[2]

    @property
    def jumps(self) -> tuple[int, ...]:
        return self.state[3]

    def load(self, stack: tuple[int, ...]) -> None:
        """Put ``stack`` under the machine without running anything.

        Callers seed a stack to watch what a short op-string does to it --
        the swap-and-sink orderings the boolean generator relies on are
        only distinguishable from a stack that already has depth.
        """
        ind, acc, _stack, jumps = self.state
        self.state = (ind, acc, tuple(stack), jumps)

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: accumulator + loop stack.  ``stack``
    # above already is the view.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """The accumulator, the only cell this language addresses."""
        return [self.state[1]]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Both stacks are already tuples, so they go in as they stand, in
        # the order this returned before the fields moved into a state.
        ind, acc, stack, jumps = self.state
        return (ind, acc, stack, jumps, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        The two I/O effects and all five error cases live here rather than
        in the transition: this is the shell, so it is where an effect or a
        raise belongs, and it leaves :func:`_advance` total.

        The unmatched ``>`` leaves the cursor at the end of the code, which
        is where the original's scan had walked it before noticing.  A
        caller that catches the error still sees a halted machine.
        """
        if self.halted:
            return
        ind, acc, stack, jumps = self.state
        char = self.code[ind]
        if len(stack) < _needs(char):
            raise HaltError(
                "empty stack" if _needs(char) == 1 else "swap needs two elements"
            )
        if char == "<" and not jumps:
            raise HaltError("unmatched <")
        target = None
        byte = None
        if char == ">" and acc in (0, 1):
            target = _forward(self.code, ind)
            if target is None:
                self.state = (self.size, acc, stack, jumps)
                raise HaltError("unmatched >")
        elif char == "o":
            value = stack[-1]
            codepoint = value & 0xFFFFFFFF
            if codepoint <= _MAX_CHAR and codepoint not in _SURROGATES:
                self.io.print_char(chr(codepoint))
            else:
                self.io.print_num(value)
        elif char == "i":
            line = self.io.input_str()
            while not line.strip():
                line = self.io.input_str()
            byte = ord(line[0])
        self.state = _advance(self.state, self.code, byte, target)


def run(code: str, io: IO) -> None:
    """Run an Unsquare program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
