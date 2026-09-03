"""Interpreter for BFStack.

Brainfuck-style commands on a stack: > pushes 0, < pops, + and - adjust the
top, . prints it, , pushes a byte of input, and [ ] loop while the top is
nonzero.  A pop or output on an empty stack is invalid and halts the program.

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and a command to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  Both
stacks are tuples, so a state is a value that can be stored, compared, and
hashed as it stands.

Keeping the transition *total* takes one extra piece here, because six of
BFStack's commands can fail on an empty stack.  :func:`_needs_operand` says
which commands require one, so the shell can reject an invalid step before
calling the transition -- rather than the transition having a raise in six
branches.  The scan for a matching ``]`` can likewise fail, so
:func:`_forward` returns ``None`` for an unmatched ``[`` and the shell
turns that into the error.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what BFStack *does* stays in
the pure layer.

The wiki does not specify the cell width for ``+``/``-``; this interpreter
wraps at 8 bits (mod 256).  It also raises :class:`EOFError` on exhausted
input, :class:`HaltError` on an invalid empty-stack operation, and
:class:`ValueError` on an unmatched ``[``.

``step()`` executes one command and ``halted`` is true once the cursor
reaches the end of the code, making a ``[`` loop whose top never zeroes a
finite-state cycle the state cycle detector can prove.
"""

from __future__ import annotations

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

#: One instant of a run: ``(ind, stk, lst)`` -- the code cursor, the data
#: stack, and the loop stack.  A value, not a record: every transition below
#: returns a new one rather than editing one in place, and both stacks are
#: tuples for the same reason.
#:
#: The loop stack is state, not a scratch register: a ``]`` reads the
#: position a matching ``[`` pushed, so two runs sitting on the same
#: command with different loop stacks will go different places next.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
type _State = tuple[int, tuple[int, ...], tuple[int, ...]]

#: The commands that read the top of the data stack, and so cannot run on
#: an empty one.  ``>`` pushes and ``,`` pushes, so neither needs an
#: operand; ``]`` needs a *loop* stack entry, which is checked separately.
_NEEDS_OPERAND = frozenset("<+-.[")


def _needs_operand(char: str) -> bool:
    """Whether ``char`` requires a non-empty data stack to run."""
    return char in _NEEDS_OPERAND


def _forward(code: str, ind: int) -> int | None:
    """Return the position of the ``]`` matching the ``[`` at ``ind``.

    ``None`` when the bracket is unmatched, which the caller turns into a
    :class:`ValueError` -- returning it rather than raising is what keeps
    the transition below free of error cases.
    """
    match = 1
    while match:
        ind += 1
        if ind == len(code):
            return None
        if (char := code[ind]) == "[":
            match += 1
        elif char == "]":
            match -= 1
    return ind


def _advance(state: _State, code: str, byte: int | None = None) -> _State:
    """Return the state after executing the command at the cursor.

    Pure, and total: every command it can be handed has a defined successor
    state, because the shell has already rejected the empty-stack cases and
    resolved the unmatched-bracket one.  It takes no ``io`` argument, so
    ``.`` and ``,`` are the caller's business -- ``.`` changes no state at
    all, and ``,``'s byte arrives as ``byte``, already read.

    ``]`` jumps to one before the position the matching ``[`` pushed, so
    the shared increment below lands back *on* the ``[`` and re-tests it.
    Anything that is not a command is a comment and falls through to that
    same increment.
    """
    ind, stk, lst = state
    char = code[ind]
    if char == ">":
        stk = (*stk, 0)
    elif char == "<":
        stk = stk[:-1]
    elif char == "+":
        stk = (*stk[:-1], (stk[-1] + 1) % 256)
    elif char == "-":
        stk = (*stk[:-1], (stk[-1] - 1) % 256)
    elif char == ",":
        stk = (*stk, byte if byte is not None else 0)
    elif char == "[":
        if stk[-1]:
            lst = (*lst, ind)
        else:
            # Skipping the loop: the shell resolved the match, so this
            # cannot fail here.  ``_forward`` is called again rather than
            # threaded through, which keeps the signature to one value.
            target = _forward(code, ind)
            ind = target if target is not None else ind
    elif char == "]":
        ind, lst = lst[-1] - 1, lst[:-1]
    return (ind + 1, stk, lst)


class _Machine:
    """A BFStack run: one immutable ``_State``, rebound per step.

    The protocol the rest of the library expects (``step``, ``halted``,
    ``snapshot``, and the ``stk``/``lst``/``ind`` attributes) is mutable by
    construction, so this class supplies it.  All it does is hold the
    current state and the code; the rules themselves are the pure functions
    above.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with an empty data stack and loop stack."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = (0, (), ())

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def stk(self) -> tuple[int, ...]:
        return self.state[1]

    @property
    def lst(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # The VM's language-shaped view.  BFStack's store *is* its data stack, so
    # ``stack`` carries it and ``memory`` is empty -- the loop stack is
    # control flow, not addressable state, and stays out of both.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """BFStack addresses no cells; its store is the stack."""
        return []

    @property
    def stack(self) -> list[int]:
        """The data stack, bottom first."""
        # A list, because that is the shape the VM's view is defined in.
        # It is a fresh one every time now, so a caller can no longer write
        # into a running machine -- the state's own tuple is unreachable.
        return list(self.state[1])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Both stacks are already tuples, so they go in as they stand.
        ind, stk, lst = self.state
        return (stk, lst, ind, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the cursor.

        The two I/O effects and all three error cases live here rather than
        in the transition: this is the shell, so it is where an effect or a
        raise belongs, and it leaves :func:`_advance` total.
        """
        if self.halted:
            return
        ind, stk, lst = self.state
        char = self.code[ind]
        if _needs_operand(char) and not stk:
            raise HaltError
        if char == "]" and not lst:
            raise HaltError
        if char == "[" and not stk[-1] and _forward(self.code, ind) is None:
            # The original scanned the cursor to the end before it noticed
            # the bracket was unmatched, leaving the machine halted.  A
            # caller that catches the error still sees that, so the cursor
            # is moved here rather than left where the scan began.
            self.state = (self.size, stk, lst)
            raise ValueError("unmatched '['")
        byte = None
        if char == ".":
            self.io.print_char(chr(stk[-1]))
        elif char == ",":
            byte = self.io.input_char()
        self.state = _advance(self.state, self.code, byte)


def run(code: str, io: IO) -> None:
    """Run a BFStack program, halting on an invalid empty-stack operation."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
